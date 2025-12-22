from django.urls import path, include
from rest_framework.routers import DefaultRouter
from complaints.views import (
    ComplaintViewSet,
    DashboardStatsView,
    SLAConfigViewSet,
    ComplaintHistoryViewSet,
    HealthCheckView
)

router = DefaultRouter()
router.register(r'complaints', ComplaintViewSet, basename='complaint')
router.register(r'sla-configs', SLAConfigViewSet, basename='sla-config')
router.register(r'history', ComplaintHistoryViewSet, basename='complaint-history')

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('', include(router.urls)),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]