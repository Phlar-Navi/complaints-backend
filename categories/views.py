from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count

from categories.models import Category, SubCategory
from categories.serializers import (
    CategoryListSerializer, CategoryDetailSerializer,
    CategoryCreateSerializer, SubCategorySerializer,
    SubCategoryCreateSerializer
)


class IsSuperAdminOrTenantAdmin(permissions.BasePermission):
    """Permission pour SUPER_ADMIN ou TENANT_ADMIN"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Lecture autorisée pour tous
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Écriture pour SUPER_ADMIN, TENANT_ADMIN, RECEPTION
        return request.user.role in ['SUPER_ADMIN', 'TENANT_ADMIN', 'RECEPTION']
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # SUPER_ADMIN peut tout faire
        if request.user.role == 'SUPER_ADMIN':
            return True
        
        # Les autres ne peuvent accéder qu'aux catégories de leur tenant
        return obj.tenant == request.user.tenant


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des catégories
    """
    permission_classes = [IsSuperAdminOrTenantAdmin]
    
    def get_queryset(self):
        user = self.request.user
        
        # SUPER_ADMIN voit toutes les catégories
        if user.role == 'SUPER_ADMIN':
            queryset = Category.objects.all()
            
            # Filtrer par tenant si paramètre fourni
            tenant_id = self.request.query_params.get('tenant')
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            return queryset.order_by('name')
        
        # Les autres ne voient que les catégories de leur tenant
        return Category.objects.filter(tenant=user.tenant).order_by('name')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CategoryListSerializer
        elif self.action == 'create':
            return CategoryCreateSerializer
        return CategoryDetailSerializer
    
    def perform_create(self, serializer):
        user = self.request.user
        
        # Si ce n'est pas un SUPER_ADMIN, forcer le tenant
        if user.role != 'SUPER_ADMIN':
            serializer.save(tenant=user.tenant)
        else:
            serializer.save()
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Statistiques d'une catégorie"""
        category = self.get_object()
        
        try:
            from complaints.models import Complaint
            complaints = Complaint.objects.filter(category=category)
            
            stats = {
                'total_complaints': complaints.count(),
                'by_status': {},
                'by_urgency': {}
            }
            
            # Par statut
            status_counts = complaints.values('status').annotate(count=Count('id'))
            for item in status_counts:
                stats['by_status'][item['status']] = item['count']
            
            # Par urgence
            urgency_counts = complaints.values('urgency').annotate(count=Count('id'))
            for item in urgency_counts:
                stats['by_urgency'][item['urgency']] = item['count']
        except:
            stats = {'total_complaints': 0}
        
        return Response(stats)


class SubCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des sous-catégories
    """
    serializer_class = SubCategorySerializer
    permission_classes = [IsSuperAdminOrTenantAdmin]
    
    def get_queryset(self):
        user = self.request.user
        
        # SUPER_ADMIN voit toutes les sous-catégories
        if user.role == 'SUPER_ADMIN':
            queryset = SubCategory.objects.all()
            
            # Filtrer par catégorie si paramètre fourni
            category_id = self.request.query_params.get('category')
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            return queryset.order_by('name')
        
        # Les autres ne voient que les sous-catégories de leur tenant
        return SubCategory.objects.filter(tenant=user.tenant).order_by('name')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SubCategoryCreateSerializer
        return SubCategorySerializer
    
    def perform_create(self, serializer):
        user = self.request.user
        
        # Si ce n'est pas un SUPER_ADMIN, forcer le tenant
        if user.role != 'SUPER_ADMIN':
            serializer.save(tenant=user.tenant)
        else:
            serializer.save()