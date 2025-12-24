from rest_framework import serializers
from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'type', 'title', 'message', 'link',
            'complaint_id', 'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'read_at']