from rest_framework.permissions import BasePermission
from tenants.models import Tenant

class HasValidTenant(BasePermission):
    """Vérifie que le tenant existe et est actif"""
    message = "Tenant invalide ou inactif"
    
    def has_permission(self, request, view):
        tenant_id = request.headers.get("X-Tenant-ID")
        
        if not tenant_id:
            return False
        
        try:
            tenant = Tenant.objects.get(id=tenant_id, is_active=True)
            request.tenant = tenant
            
            # Vérifier que l'utilisateur appartient bien à ce tenant
            if request.user.is_authenticated:
                if request.user.role == "SUPER_ADMIN":
                    return True
                return request.user.tenant_id == tenant.id
            
            return True  # Pour signup/login
        except Tenant.DoesNotExist:
            return False
        
class IsReceptionOrAbove(BasePermission):
    """Reception, Admin, Super Admin"""
    def has_permission(self, request, view):
        return request.user.role in ["RECEPTION", "TENANT_ADMIN", "SUPER_ADMIN"]

class IsTenantAdmin(BasePermission):
    """Tenant Admin ou Super Admin"""
    def has_permission(self, request, view):
        return request.user.role in ["TENANT_ADMIN", "SUPER_ADMIN"]