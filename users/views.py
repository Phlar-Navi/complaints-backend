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
"""
Ajouter ces vues à votre fichier users/views.py existant
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import authenticate

from rest_framework.exceptions import ValidationError
from django.db import connection

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # 1️⃣ Identifier le tenant de l'utilisateur
        try:
            # Chercher l'utilisateur et son tenant depuis le schéma public
            user = CustomUser.objects.select_related("tenant").get(email=email)
            tenant = user.tenant
        except CustomUser.DoesNotExist:
            return Response({"detail": "Identifiants incorrects."}, status=400)

        if not tenant or tenant.schema_name == "public":
            return Response({"detail": "Utilisateur non associé à un tenant."}, status=400)

        # 2️⃣ Authentifier dans le schéma correct
        with schema_context(tenant.schema_name):
            user = authenticate(username=email, password=password)
            if not user or not user.is_active:
                return Response({"detail": "Identifiants incorrects."}, status=400)

        # 3️⃣ Créer tokens JWT
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name
            },
            "tenant": {
                "schema_name": tenant.schema_name,
                "name": tenant.name,
                "domain": f"{tenant.schema_name}.16.16.202.86"
            },
            "redirect_domain": f"{tenant.schema_name}.16.16.202.86"
        })


class UpdateProfileView(APIView):
    """
    Mettre à jour le profil de l'utilisateur connecté
    PUT /api/users/profile/
    """
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        user = request.user
        data = request.data
        
        # Champs modifiables
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        
        if 'email' in data:
            # Vérifier que l'email n'est pas déjà pris
            from users.models import CustomUser
            if CustomUser.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response(
                    {'error': 'Cet email est déjà utilisé'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.email = data['email']
        
        user.save()
        
        # Retourner le profil mis à jour
        from users.serializers import UserSerializer
        serializer = UserSerializer(user)
        return Response(serializer.data)


class UploadAvatarView(APIView):
    """
    Upload photo de profil
    POST /api/users/profile/avatar/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if 'avatar' not in request.FILES:
            return Response(
                {'error': 'Aucun fichier fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        avatar = request.FILES['avatar']
        
        # Valider la taille (max 2MB)
        if avatar.size > 2 * 1024 * 1024:
            return Response(
                {'error': 'Le fichier est trop volumineux (max 2MB)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valider le type
        if not avatar.content_type.startswith('image/'):
            return Response(
                {'error': 'Le fichier doit être une image'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Sauvegarder (nécessite d'ajouter un champ avatar au modèle)
        user.avatar = avatar
        user.save()
        
        from users.serializers import UserSerializer
        serializer = UserSerializer(user)
        return Response(serializer.data)


class UpdatePasswordView(APIView):
    """
    Changer le mot de passe
    POST /api/users/profile/password/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        data = request.data
        
        # Vérifier l'ancien mot de passe
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not old_password or not new_password or not confirm_password:
            return Response(
                {'error': 'Tous les champs sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user.check_password(old_password):
            return Response(
                {'error': 'Mot de passe actuel incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_password != confirm_password:
            return Response(
                {'error': 'Les mots de passe ne correspondent pas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(new_password) < 8:
            return Response(
                {'error': 'Le mot de passe doit contenir au moins 8 caractères'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Changer le mot de passe
        user.set_password(new_password)
        user.save()
        
        # Mettre à jour la session
        update_session_auth_hash(request, user)
        
        return Response({'message': 'Mot de passe mis à jour avec succès'})


class UserPreferencesView(APIView):
    """
    Gérer les préférences utilisateur
    GET/PUT /api/users/preferences/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Récupérer ou créer les préférences
        from users.models import UserPreferences
        preferences, created = UserPreferences.objects.get_or_create(user=user)
        
        return Response({
            'email_notifications': preferences.email_notifications,
            'push_notifications': preferences.push_notifications,
            'language': preferences.language,
            'theme': preferences.theme,
        })
    
    def put(self, request):
        user = request.user
        data = request.data
        
        from users.models import UserPreferences
        preferences, created = UserPreferences.objects.get_or_create(user=user)
        
        if 'email_notifications' in data:
            preferences.email_notifications = data['email_notifications']
        
        if 'push_notifications' in data:
            preferences.push_notifications = data['push_notifications']
        
        if 'language' in data:
            preferences.language = data['language']
        
        if 'theme' in data:
            preferences.theme = data['theme']
        
        preferences.save()
        
        return Response({
            'email_notifications': preferences.email_notifications,
            'push_notifications': preferences.push_notifications,
            'language': preferences.language,
            'theme': preferences.theme,
        })
    

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
    serializer_class = UserCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        if user.role not in ['SUPER_ADMIN', 'TENANT_ADMIN']:
            raise permissions.PermissionDenied(
                "Seuls les administrateurs peuvent créer des utilisateurs."
            )

        # 🔒 TENANT_ADMIN → tenant imposé
        if user.role == 'TENANT_ADMIN':
            serializer.save(tenant=user.tenant)
            return

        # 🔓 SUPER_ADMIN → tenant fourni explicitement
        serializer.save()


class LoginView_obsolete(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        tenant = getattr(request, 'tenant', None)

        tenant_info = None
        redirect_domain = None

        if tenant and tenant.schema_name != 'public':
            tenant_info = {
                'id': str(tenant.id),
                'name': tenant.name,
                'schema_name': tenant.schema_name,
            }

            primary_domain = tenant.domains.filter(is_primary=True).first()
            if primary_domain:
                redirect_domain = primary_domain.domain

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'tenant': tenant_info,
            'redirect_domain': redirect_domain,
        })


class LoginView_notWorking(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        tenant_info = None
        tenant_domain = None

        # 🔥 C’EST ICI qu’on résout le tenant
        if user.role != "SUPER_ADMIN":
            if not user.tenant:
                raise ValidationError("Utilisateur sans tenant")

            tenant = user.tenant
            domain = tenant.get_primary_domain()

            tenant_info = {
                "id": str(tenant.id),
                "name": tenant.name,
                "schema_name": tenant.schema_name,
            }
            tenant_domain = domain.domain if domain else None

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "tenant": tenant_info,
            "redirect_domain": tenant_domain,
        })


class LoginView_legacy(APIView):
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