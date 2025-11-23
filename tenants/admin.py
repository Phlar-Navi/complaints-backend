from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from tenants.models import Tenant

@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'zone', 'is_premium', 'is_active')
