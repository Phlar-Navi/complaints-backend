from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tenants.views import TenantViewSet, TenantStatsView, HealthCheckView

router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='tenant')

urlpatterns = [
    # Stats AVANT le router pour éviter les conflits
    path('tenants/global-stats/', TenantStatsView.as_view(), name='tenant-global-stats'),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    # Puis le router
    path('', include(router.urls)),
]