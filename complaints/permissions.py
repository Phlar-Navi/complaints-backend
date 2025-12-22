from rest_framework import permissions


class IsTenantUser(permissions.BasePermission):
    """
    Permission pour vérifier que l'utilisateur appartient au tenant
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # SUPER_ADMIN peut tout faire
        if request.user.role == 'SUPER_ADMIN':
            return True
        
        # Les autres doivent avoir un tenant
        return request.user.tenant is not None
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # SUPER_ADMIN peut tout voir
        if request.user.role == 'SUPER_ADMIN':
            return True
        
        # Vérifier que l'objet appartient au même tenant
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.user.tenant
        
        return False


class IsAgentOrAdmin(permissions.BasePermission):
    """
    Permission pour les actions qui nécessitent d'être agent ou admin
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Lecture autorisée pour tous
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Écriture seulement pour certains rôles
        return request.user.role in [
            'SUPER_ADMIN', 
            'TENANT_ADMIN', 
            'AGENT'
        ]


class CanAssignComplaint(permissions.BasePermission):
    """
    Permission pour assigner des plaintes
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.role in [
            'SUPER_ADMIN',
            'TENANT_ADMIN',
            'RECEPTION'
        ]


class CanDeleteComplaint(permissions.BasePermission):
    """
    Permission pour supprimer des plaintes (seulement admins)
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if view.action != 'destroy':
            return True
        
        return request.user.role in [
            'SUPER_ADMIN',
            'TENANT_ADMIN'
        ]