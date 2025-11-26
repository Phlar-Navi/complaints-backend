from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import logout
from django_tenants.utils import schema_context, get_tenant_model
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import CustomUser
from users.serializers import (
    UserSerializer, UserCreateSerializer, LoginSerializer,
    TenantCreateSerializer, ChangePasswordSerializer
)
from tenants.models import Tenant

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

class TenantCreateView(generics.CreateAPIView):
    """
    Créer un nouveau tenant avec son admin
    POST /api/tenants/create/
    """
    serializer_class = TenantCreateSerializer
    permission_classes = [AllowAny]  # Ou restreindre aux SUPER_ADMIN

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        return Response({
            'message': 'Tenant créé avec succès',
            'tenant': {
                'id': str(tenant.id),
                'schema_name': tenant.schema_name,
                'name': tenant.name,
            }
        }, status=status.HTTP_201_CREATED)


class UserCreateView(generics.CreateAPIView):
    """
    Créer un nouvel utilisateur pour un tenant
    POST /api/users/create/
    Nécessite d'être TENANT_ADMIN ou SUPER_ADMIN
    """
    serializer_class = UserCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        
        # Vérifier les permissions
        if user.role not in ['SUPER_ADMIN', 'TENANT_ADMIN']:
            raise permissions.PermissionDenied(
                "Seuls les administrateurs peuvent créer des utilisateurs."
            )
        
        # Si TENANT_ADMIN, ne peut créer que pour son propre tenant
        if user.role == 'TENANT_ADMIN':
            tenant = serializer.validated_data.get('tenant')
            if tenant != user.tenant:
                raise permissions.PermissionDenied(
                    "Vous ne pouvez créer des utilisateurs que pour votre tenant."
                )
        
        serializer.save()


class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Créer des tokens JWT
        refresh = RefreshToken.for_user(user)
        
        # Préparer les informations du tenant
        tenant_info = None
        tenant_domain = None
        
        if user.tenant:
            tenant_info = {
                'id': str(user.tenant.id),
                'name': user.tenant.name,
                'schema_name': user.tenant.schema_name,
            }
            
            # Récupérer le domaine principal du tenant
            primary_domain = user.tenant.get_primary_domain()
            if primary_domain:
                tenant_domain = primary_domain.domain
        
        response_data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'tenant': tenant_info,
            'redirect_domain': tenant_domain,  # Le frontend utilisera cela pour rediriger
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()

        logout(request)
        return Response({"message": "Déconnexion réussie"})


class CurrentUserView(APIView):
    """
    Récupérer les informations de l'utilisateur connecté
    GET /api/auth/me/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Générer de nouveaux tokens JWT
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Mot de passe changé avec succès',
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """
    Lister les utilisateurs du tenant
    GET /api/users/
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # SUPER_ADMIN voit tous les utilisateurs
        if user.role == 'SUPER_ADMIN':
            return CustomUser.objects.all()
        
        # Les autres ne voient que les utilisateurs de leur tenant
        if user.tenant:
            return CustomUser.objects.filter(tenant=user.tenant)
        
        return CustomUser.objects.none()


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Récupérer, modifier ou supprimer un utilisateur
    GET/PUT/PATCH/DELETE /api/users/<uuid>/
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'SUPER_ADMIN':
            return CustomUser.objects.all()
        
        if user.role == 'TENANT_ADMIN' and user.tenant:
            return CustomUser.objects.filter(tenant=user.tenant)
        
        # Les autres utilisateurs ne peuvent voir que leur propre profil
        return CustomUser.objects.filter(id=user.id)
    
    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        
        # Les utilisateurs ne peuvent modifier que leur propre profil
        # sauf les admins
        if user.role not in ['SUPER_ADMIN', 'TENANT_ADMIN']:
            if instance.id != user.id:
                raise permissions.PermissionDenied()
        
        serializer.save()
    
    def perform_destroy(self, instance):
        user = self.request.user
        
        # Seuls les admins peuvent supprimer des utilisateurs
        if user.role not in ['SUPER_ADMIN', 'TENANT_ADMIN']:
            raise permissions.PermissionDenied()
        
        # TENANT_ADMIN ne peut supprimer que dans son tenant
        if user.role == 'TENANT_ADMIN':
            if instance.tenant != user.tenant:
                raise permissions.PermissionDenied()
        
        instance.delete()