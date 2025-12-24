from rest_framework import serializers
from tenants.models import Tenant, Domain
from users.models import CustomUser


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'domain', 'is_primary', 'tenant']
        read_only_fields = ['id']


class TenantListSerializer(serializers.ModelSerializer):
    """Serializer léger pour la liste des tenants"""
    primary_domain = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    complaint_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'schema_name', 'name', 'zone', 'is_active', 
            'is_premium', 'created_at', 'primary_domain',
            'user_count', 'complaint_count'
        ]
    
    def get_primary_domain(self, obj):
        domain = obj.get_primary_domain()
        return domain.domain if domain else None
    
    def get_user_count(self, obj):
        return CustomUser.objects.filter(tenant=obj).count()
    
    def get_complaint_count(self, obj):
        try:
            from complaints.models import Complaint
            return Complaint.objects.filter(tenant=obj).count()
        except:
            return 0


class TenantDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour les détails d'un tenant"""
    domains = DomainSerializer(many=True, read_only=True)
    user_count = serializers.SerializerMethodField()
    complaint_count = serializers.SerializerMethodField()
    admin_users = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'schema_name', 'name', 'zone', 'contact_info',
            'is_active', 'is_premium', 'created_at',
            'domains', 'user_count', 'complaint_count', 'admin_users'
        ]
        read_only_fields = ['id', 'schema_name', 'created_at']
    
    def get_user_count(self, obj):
        return CustomUser.objects.filter(tenant=obj).count()
    
    def get_complaint_count(self, obj):
        try:
            from complaints.models import Complaint
            return Complaint.objects.filter(tenant=obj).count()
        except:
            return 0
    
    def get_admin_users(self, obj):
        admins = CustomUser.objects.filter(
            tenant=obj, 
            role='TENANT_ADMIN'
        )[:5]  # Limiter à 5
        return [{
            'id': str(admin.id),
            'email': admin.email,
            'full_name': admin.full_name
        } for admin in admins]


class TenantUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mise à jour d'un tenant"""
    
    class Meta:
        model = Tenant
        fields = ['name', 'zone', 'contact_info', 'is_active', 'is_premium']
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
