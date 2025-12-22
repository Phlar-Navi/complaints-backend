# complaintsManager/middleware.py

from django.db import connection
import logging

logger = logging.getLogger(__name__)

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