from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les notifications
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """L'utilisateur ne voit que ses propres notifications"""
        return Notification.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """
        Récupérer uniquement les notifications non lues
        GET /api/notifications/unread/
        """
        unread = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(unread, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def count_unread(self, request):
        """
        Compter les notifications non lues
        GET /api/notifications/count_unread/
        """
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Marquer une notification comme lue
        POST /api/notifications/{id}/mark_read/
        """
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Marquer toutes les notifications comme lues
        POST /api/notifications/mark_all_read/
        """
        notifications = self.get_queryset().filter(is_read=False)
        for notif in notifications:
            notif.mark_as_read()
        
        return Response({
            'message': f'{notifications.count()} notifications marquées comme lues'
        })
    
    @action(detail=False, methods=['delete'])
    def delete_read(self, request):
        """
        Supprimer toutes les notifications lues
        DELETE /api/notifications/delete_read/
        """
        deleted_count, _ = self.get_queryset().filter(is_read=True).delete()
        return Response({
            'message': f'{deleted_count} notifications supprimées'
        })


class NotificationStatsView(APIView):
    """
    Statistiques des notifications
    GET /api/notifications/stats/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        notifications = Notification.objects.filter(user=user)
        
        total = notifications.count()
        unread = notifications.filter(is_read=False).count()
        by_type = {}
        
        for notif_type, _ in Notification.TYPE_CHOICES:
            count = notifications.filter(type=notif_type).count()
            if count > 0:
                by_type[notif_type] = count
        
        return Response({
            'total': total,
            'unread': unread,
            'read': total - unread,
            'by_type': by_type
        })


# ==================== notifications/urls.py ====================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from notifications.views import NotificationViewSet, NotificationStatsView

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('notifications/stats/', NotificationStatsView.as_view(), name='notification-stats'),
    path('', include(router.urls)),
]