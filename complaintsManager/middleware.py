# complaintsManager/middleware.py

from django.db import connection
import logging
from django_tenants.middleware.main import TenantMainMiddleware
from tenants.models import Domain

logger = logging.getLogger(__name__)

class CustomTenantMiddleware(TenantMainMiddleware):
    """
    Middleware qui supporte les tirets dans les hostnames
    en les convertissant en underscores pour chercher le schema
    """
    
    def get_tenant(self, domain_model, hostname):
        # 1. Essayer d'abord avec le hostname tel quel
        try:
            domain = domain_model.objects.select_related('tenant').get(domain=hostname)
            return domain.tenant
        except domain_model.DoesNotExist:
            pass
        
        # 2. Si pas trouvé, essayer avec underscores
        hostname_with_underscores = hostname.replace('-', '_')
        if hostname_with_underscores != hostname:
            try:
                domain = domain_model.objects.select_related('tenant').get(domain=hostname_with_underscores)
                return domain.tenant
            except domain_model.DoesNotExist:
                pass
        
        # 3. Si toujours pas trouvé, vérifier si un tenant a ce schema_name avec underscores
        # Extraire le sous-domaine
        subdomain = hostname.split('.')[0] if '.' in hostname else hostname
        schema_with_underscores = subdomain.replace('-', '_')
        
        try:
            # Chercher un domaine du tenant qui a ce schema
            from tenants.models import Tenant
            tenant = Tenant.objects.get(schema_name=schema_with_underscores)
            # Vérifier qu'il a au moins un domaine
            if tenant.domains.exists():
                return tenant
        except Tenant.DoesNotExist:
            pass
        
        # 4. Aucun tenant trouvé
        raise domain_model.DoesNotExist(
            f"No tenant found for hostname: {hostname}"
        )

class DebugTenantMiddleware:
    """Middleware pour débugger les problèmes de tenant et CORS"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log avant le traitement
        logger.info(f"""
=== REQUEST DEBUG ===
Method: {request.method}
Path: {request.path}
Host header: {request.META.get('HTTP_HOST')}
Origin: {request.META.get('HTTP_ORIGIN', 'N/A')}
Schema: {getattr(connection, 'schema_name', 'NOT SET YET')}
Tenant: {getattr(request, 'tenant', 'NOT SET YET')}
User: {request.user if hasattr(request, 'user') else 'NOT SET YET'}
===================""")
        
        response = self.get_response(request)
        
        # Log après le traitement
        logger.info(f"""
=== RESPONSE DEBUG ===
Status: {response.status_code}
Schema (after): {connection.schema_name}
CORS headers: {response.get('Access-Control-Allow-Origin', 'NOT SET')}
=====================""")
        
        return response


class TenantDebugMiddleware:
    """Alternative: log uniquement pour les requêtes échouées"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Log seulement si erreur 404 ou 403
        if response.status_code in [403, 404]:
            print(f"""
🔴 ERREUR {response.status_code}
   Method: {request.method}
   Path: {request.path}
   Host: {request.META.get('HTTP_HOST')}
   Origin: {request.META.get('HTTP_ORIGIN')}
   Schema: {connection.schema_name}
   Tenant: {getattr(request, 'tenant', None)}
""")
        
        return response