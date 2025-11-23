from django.http import JsonResponse
from tenants.models import Tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.headers.get("X-Tenant-ID")

        if not tenant_id:
            return JsonResponse(
                {"detail": "Missing X-Tenant-ID header"},
                status=400
            )

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return JsonResponse(
                {"detail": "Invalid tenant"},
                status=403
            )

        # On attache le tenant à la requête
        request.tenant = tenant

        return self.get_response(request)
