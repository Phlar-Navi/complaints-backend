from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q
from datetime import datetime, timedelta

from tenants.models import Tenant, Domain
from tenants.serializers import (
    TenantListSerializer, TenantDetailSerializer, 
    TenantUpdateSerializer, DomainSerializer
)
from users.models import CustomUser

from rest_framework.permissions import AllowAny
from django.db import connection

class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            # Test database
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return Response({
                'status': 'healthy',
                'database': 'connected',
                'schema': connection.schema_name
            })
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'error': str(e)
            }, status=500)


class IsSuperAdmin(permissions.BasePermission):
    """Permission pour vérifier que l'utilisateur est SUPER_ADMIN"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'SUPER_ADMIN'
        )


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion complète des tenants (SUPER_ADMIN uniquement)
    """
    permission_classes = [IsSuperAdmin]
    
    def get_queryset(self):
        return Tenant.objects.all().order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TenantListSerializer
        elif self.action in ['update', 'partial_update']:
            return TenantUpdateSerializer
        return TenantDetailSerializer
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Récupérer tous les utilisateurs d'un tenant"""
        tenant = self.get_object()
        users = CustomUser.objects.filter(tenant=tenant)
        
        from users.serializers import UserSerializer
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Statistiques détaillées d'un tenant"""
        tenant = self.get_object()
        
        # Statistiques utilisateurs
        users = CustomUser.objects.filter(tenant=tenant)
        user_stats = {
            'total': users.count(),
            'by_role': {}
        }
        for role, label in CustomUser.ROLE_CHOICES:
            count = users.filter(role=role).count()
            if count > 0:
                user_stats['by_role'][role] = {
                    'count': count,
                    'label': label
                }
        
        # Statistiques plaintes
        try:
            from complaints.models import Complaint
            complaints = Complaint.objects.filter(tenant=tenant)
            
            # Plaintes ce mois-ci
            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            this_month = complaints.filter(submitted_at__gte=month_start).count()
            
            complaint_stats = {
                'total': complaints.count(),
                'this_month': this_month,
                'by_status': {},
                'by_urgency': {}
            }
            
            # Par statut
            status_counts = complaints.values('status').annotate(count=Count('id'))
            for item in status_counts:
                complaint_stats['by_status'][item['status']] = item['count']
            
            # Par urgence
            urgency_counts = complaints.values('urgency').annotate(count=Count('id'))
            for item in urgency_counts:
                complaint_stats['by_urgency'][item['urgency']] = item['count']
        except:
            complaint_stats = {'total': 0}
        
        return Response({
            'tenant': TenantDetailSerializer(tenant).data,
            'users': user_stats,
            'complaints': complaint_stats
        })
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Activer/Désactiver un tenant"""
        tenant = self.get_object()
        tenant.is_active = not tenant.is_active
        tenant.save()
        
        return Response({
            'message': f"Tenant {'activé' if tenant.is_active else 'désactivé'}",
            'is_active': tenant.is_active
        })
    
    @action(detail=True, methods=['post'])
    def add_domain(self, request, pk=None):
        """Ajouter un domaine à un tenant"""
        tenant = self.get_object()
        
        serializer = DomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        domain = serializer.save(tenant=tenant)
        
        return Response(
            DomainSerializer(domain).data,
            status=status.HTTP_201_CREATED
        )


class TenantStatsView(APIView):
    """
    Statistiques globales de tous les tenants
    GET /api/tenants/global-stats/
    """
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        # Nombre total de tenants
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()
        premium_tenants = Tenant.objects.filter(is_premium=True).count()
        
        # Tenants créés ce mois
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = Tenant.objects.filter(created_at__gte=month_start).count()
        
        # Total utilisateurs tous tenants
        total_users = CustomUser.objects.exclude(role='SUPER_ADMIN').count()
        
        # Total plaintes tous tenants
        try:
            from complaints.models import Complaint
            total_complaints = Complaint.objects.count()
            
            # Plaintes ce mois
            complaints_this_month = Complaint.objects.filter(
                submitted_at__gte=month_start
            ).count()
        except:
            total_complaints = 0
            complaints_this_month = 0
        
        # Top 5 tenants par nombre de plaintes
        try:
            from complaints.models import Complaint
            top_tenants = []
            for tenant in Tenant.objects.all():
                count = Complaint.objects.filter(tenant=tenant).count()
                if count > 0:
                    top_tenants.append({
                        'tenant_id': str(tenant.id),
                        'tenant_name': tenant.name,
                        'complaint_count': count
                    })
            top_tenants.sort(key=lambda x: x['complaint_count'], reverse=True)
            top_tenants = top_tenants[:5]
        except:
            top_tenants = []
        
        return Response({
            'tenants': {
                'total': total_tenants,
                'active': active_tenants,
                'inactive': total_tenants - active_tenants,
                'premium': premium_tenants,
                'new_this_month': new_this_month
            },
            'users': {
                'total': total_users
            },
            'complaints': {
                'total': total_complaints,
                'this_month': complaints_this_month
            },
            'top_tenants': top_tenants
        })