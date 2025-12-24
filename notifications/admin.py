from django.contrib import admin
from notifications.models import Notification, UserPreferences


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__email']
    readonly_fields = ['id', 'created_at', 'read_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Si pas super admin, filtrer par tenant
        if not request.user.is_superuser:
            return qs.filter(tenant=request.user.tenant)
        return qs


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'language', 'email_notifications']
    search_fields = ['user__email']
