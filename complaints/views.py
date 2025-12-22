from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from complaints.models import (
    Complaint, ComplaintAttachment, ComplaintComment,
    SLAConfig, ComplaintHistory
)
from complaints.serializers import (
    ComplaintListSerializer, ComplaintDetailSerializer,
    ComplaintCreateSerializer, ComplaintUpdateSerializer,
    ComplaintAttachmentSerializer, ComplaintCommentSerializer,
    SLAConfigSerializer, ComplaintHistorySerializer
)
from complaints.services.statistics import ComplaintStatisticsService
from complaints.permissions import IsAgentOrAdmin, IsTenantUser

from django.db import connection
import logging

logger = logging.getLogger(__name__)


class ComplaintViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les plaintes (CRUD)
    """
    permission_classes = [permissions.IsAuthenticated, IsTenantUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'urgency', 'assigned_user', 'category']
    search_fields = ['reference', 'title', 'description', 'phone_number']
    ordering_fields = ['submitted_at', 'updated_at', 'sla_deadline', 'urgency']
    ordering = ['-submitted_at']
    
    def get_queryset(self):
        user = self.request.user
        
        # SUPER_ADMIN voit toutes les plaintes
        if user.role == 'SUPER_ADMIN':
            return Complaint.objects.all()
        
        # Les autres ne voient que les plaintes de leur tenant
        base_qs = Complaint.objects.filter(tenant=user.tenant)
        
        # AGENT ne voit que ses plaintes assignées
        if user.role == 'AGENT':
            return base_qs.filter(assigned_user=user)
        
        # TENANT_ADMIN, RECEPTION, AUDITOR voient tout leur tenant
        return base_qs
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ComplaintListSerializer
        elif self.action == 'create':
            return ComplaintCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ComplaintUpdateSerializer
        return ComplaintDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save()
    
    def perform_update(self, serializer):
        serializer.save()
    
    def perform_destroy(self, instance):
        # Créer une entrée d'historique avant suppression
        ComplaintHistory.objects.create(
            tenant=instance.tenant,
            complaint=None,  # La plainte sera supprimée
            complaint_reference=instance.reference,
            action='DELETED',
            user=self.request.user,
            old_value={
                'title': instance.title,
                'status': instance.status,
            },
            description=f"Complaint {instance.reference} deleted by {self.request.user.email}"
        )
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assigner une plainte à un agent"""
        complaint = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from users.models import CustomUser
        try:
            agent = CustomUser.objects.get(
                id=user_id,
                tenant=complaint.tenant,
                role__in=['AGENT', 'TENANT_ADMIN']
            )
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'Invalid user or user is not an agent'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_user = complaint.assigned_user
        complaint.assigned_user = agent
        complaint.status = 'ASSIGNED'
        complaint.save()
        
        # Créer l'entrée d'historique
        ComplaintHistory.objects.create(
            tenant=complaint.tenant,
            complaint=complaint,
            complaint_reference=complaint.reference,
            action='ASSIGNED' if not old_user else 'REASSIGNED',
            user=request.user,
            old_value={'assigned_user_id': str(old_user.id) if old_user else None},
            new_value={'assigned_user_id': str(agent.id)},
            description=f"Assigned to {agent.full_name}"
        )
        
        serializer = ComplaintDetailSerializer(complaint)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Ajouter un commentaire à une plainte"""
        complaint = self.get_object()
        
        serializer = ComplaintCommentSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        comment = serializer.save(
            tenant=complaint.tenant,
            complaint=complaint,
            user=request.user
        )
        
        # Créer l'entrée d'historique
        ComplaintHistory.objects.create(
            tenant=complaint.tenant,
            complaint=complaint,
            complaint_reference=complaint.reference,
            action='COMMENT_ADDED',
            user=request.user,
            description=f"Comment added by {request.user.full_name}"
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_attachment(self, request, pk=None):
        """Ajouter un fichier à une plainte"""
        complaint = self.get_object()
        
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attachment = ComplaintAttachment.objects.create(
            tenant=complaint.tenant,
            complaint=complaint,
            filename=file.name,
            file=file,
            uploaded_by=request.user
        )
        
        # Créer l'entrée d'historique
        ComplaintHistory.objects.create(
            tenant=complaint.tenant,
            complaint=complaint,
            complaint_reference=complaint.reference,
            action='ATTACHMENT_ADDED',
            user=request.user,
            description=f"Attachment '{file.name}' added"
        )
        
        serializer = ComplaintAttachmentSerializer(attachment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Récupérer l'historique d'une plainte"""
        complaint = self.get_object()
        history = ComplaintHistory.objects.filter(complaint=complaint)
        
        serializer = ComplaintHistorySerializer(history, many=True)
        return Response(serializer.data)


class DashboardStatsView(APIView):
    """
    GET /api/dashboard/
    """
    def get(self, request):
        try:
            user = request.user

            if user.role != 'SUPER_ADMIN' and not user.tenant:
                return Response(
                    {'error': 'User has no tenant assigned'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # ========================
            # SUPER ADMIN
            # ========================
            if user.role == 'SUPER_ADMIN':
                stats_service = ComplaintStatisticsService(
                    tenant=None,
                    user=user
                )

                return Response({
                    "stats": stats_service.get_global_platform_stats(),
                    "meta": {
                        "role": user.role,
                        "tenant": None,
                        "scope": "global"
                    }
                })

            # ========================
            # TENANT USERS
            # ========================
            if connection.schema_name != user.tenant.schema_name:
                return Response(
                    {'error': 'Tenant schema mismatch'},
                    status=status.HTTP_403_FORBIDDEN
                )

            stats_service = ComplaintStatisticsService(
                tenant=user.tenant,
                user=user
            )

            return Response({
                "stats": stats_service.get_dashboard_stats(),
                "meta": {
                    "role": user.role,
                    "tenant": user.tenant.name,
                    "schema": connection.schema_name
                }
            })

        except Exception as e:
            logger.exception("Dashboard stats error")
            return Response(
                {
                    "error": "Internal server error",
                    "detail": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    

class HealthCheckView(APIView):
    """Endpoint simple pour tester le routing"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        from django.db import connection
        return Response({
            'status': 'ok',
            'schema': connection.schema_name,
            'host': request.get_host(),
            'path': request.path,
        })
    
    
class SLAConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les configurations SLA
    """
    serializer_class = SLAConfigSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgentOrAdmin]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'SUPER_ADMIN':
            return SLAConfig.objects.all()
        
        return SLAConfig.objects.filter(tenant=user.tenant)
    
    def perform_destroy(self, instance):
        # Créer une entrée d'historique pour les changements critiques
        ComplaintHistory.objects.create(
            tenant=instance.tenant,
            complaint=None,
            complaint_reference='SLA_CONFIG',
            action='UPDATED',
            user=self.request.user,
            old_value={
                'category': instance.category.name,
                'urgency': instance.urgency_level,
                'delay_hours': instance.delay_hours,
            },
            description=f"SLA Config deleted for {instance.category.name} - {instance.urgency_level}"
        )
        instance.delete()


class ComplaintHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour consulter l'historique (lecture seule)
    """
    serializer_class = ComplaintHistorySerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['action', 'complaint']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'SUPER_ADMIN':
            return ComplaintHistory.objects.all()
        
        return ComplaintHistory.objects.filter(tenant=user.tenant)