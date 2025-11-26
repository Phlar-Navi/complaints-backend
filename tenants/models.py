import uuid
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=255)
    zone = models.CharField(max_length=255, blank=True)
    contact_info = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_premium = models.BooleanField(default=False)

    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    def __str__(self):
        return f"{self.name}"
    
    def get_primary_domain(self):
        """Retourne le domaine principal du tenant"""
        try:
            # django-tenants utilise 'domains' comme related_name
            return self.domains.filter(is_primary=True).first()
        except Exception:
            return None


class Domain(DomainMixin):
    pass