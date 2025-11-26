from rest_framework import serializers
from django.contrib.auth import authenticate
from users.models import CustomUser
from tenants.models import Tenant, Domain


class UserSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'role', 'tenant', 'tenant_name', 'is_active', 
            'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un utilisateur pour un tenant existant"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = [
            'email', 'password', 'password_confirm', 'first_name', 
            'last_name', 'phone', 'role', 'tenant'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Les mots de passe ne correspondent pas."
            })
        
        # Vérifier que le tenant existe et est actif
        tenant = attrs.get('tenant')
        if tenant and not tenant.is_active:
            raise serializers.ValidationError({
                "tenant": "Ce tenant n'est pas actif."
            })
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = CustomUser.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer pour l'authentification - simplifié sans tenant_schema"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # Authentifier sur le schéma public
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    "Identifiants incorrects.",
                    code='authorization'
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "Ce compte est désactivé.",
                    code='authorization'
                )
            
            # Vérifier que l'utilisateur a un tenant (sauf SUPER_ADMIN)
            if user.role != 'SUPER_ADMIN' and not user.tenant:
                raise serializers.ValidationError(
                    "Utilisateur non associé à un tenant.",
                    code='authorization'
                )

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                "Email et mot de passe requis.",
                code='authorization'
            )
        

class TenantCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un nouveau tenant avec son admin"""
    domain_url = serializers.CharField(
        write_only=True,
        help_text="Domaine principal du tenant (ex: tenant1.example.com)"
    )
    admin_email = serializers.EmailField(write_only=True)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_password_confirm = serializers.CharField(write_only=True, min_length=8)
    admin_first_name = serializers.CharField(write_only=True)
    admin_last_name = serializers.CharField(write_only=True)

    class Meta:
        model = Tenant
        fields = [
            'schema_name', 'name', 'zone', 'contact_info', 
            'is_premium', 'domain_url', 'admin_email', 
            'admin_password', 'admin_password_confirm',
            'admin_first_name', 'admin_last_name'
        ]

    def validate_schema_name(self, value):
        """Valider que le schema_name est valide"""
        if not value.islower() or not value.replace('_', '').isalnum():
            raise serializers.ValidationError(
                "Le schema_name doit être en minuscules et ne contenir que des lettres, chiffres et underscores."
            )
        if value in ['public', 'information_schema', 'pg_catalog']:
            raise serializers.ValidationError(
                "Ce nom de schéma est réservé."
            )
        return value

    def validate_domain_url(self, value):
        """Valider que le domaine n'existe pas déjà"""
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError(
                "Ce domaine est déjà utilisé."
            )
        return value

    def validate(self, attrs):
        if attrs['admin_password'] != attrs['admin_password_confirm']:
            raise serializers.ValidationError({
                "admin_password": "Les mots de passe ne correspondent pas."
            })
        return attrs

    def create(self, validated_data):
        # Extraire les données de l'admin
        domain_url = validated_data.pop('domain_url')
        admin_email = validated_data.pop('admin_email')
        admin_password = validated_data.pop('admin_password')
        validated_data.pop('admin_password_confirm')
        admin_first_name = validated_data.pop('admin_first_name')
        admin_last_name = validated_data.pop('admin_last_name')

        # Créer le tenant
        tenant = Tenant.objects.create(**validated_data)

        # Créer le domaine
        Domain.objects.create(
            domain=domain_url,
            tenant=tenant,
            is_primary=True
        )

        # Créer l'utilisateur admin du tenant
        admin_user = CustomUser.objects.create_user(
            email=admin_email,
            password=admin_password,
            first_name=admin_first_name,
            last_name=admin_last_name,
            tenant=tenant,
            role='TENANT_ADMIN',
            is_staff=False,
            is_active=True
        )

        return tenant


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour changer le mot de passe"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "Les mots de passe ne correspondent pas."
            })
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value