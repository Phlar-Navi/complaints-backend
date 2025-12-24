from django.urls import path, include
from rest_framework.routers import DefaultRouter
from notifications.views import NotificationViewSet, NotificationStatsView

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # Statistiques des notifications
    path(
        'notifications/stats/',
        NotificationStatsView.as_view(),
        name='notification-stats'
    ),

    # Routes générées automatiquement par le ViewSet
    path('', include(router.urls)),
]
