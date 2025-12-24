from django.urls import path
#from .views import SignupView, LoginView
from django.urls import path
from users.views import (
    LoginView, LogoutView, CurrentUserView, ChangePasswordView,
    UserCreateView, UserListView, UserDetailView, TenantCreateView,
    UpdateProfileView,
    UploadAvatarView,
    UpdatePasswordView,
    UserPreferencesView,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Authentication
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # NOUVEAUX : Profil
    path('users/profile/', UpdateProfileView.as_view(), name='update-profile'),
    path('users/profile/avatar/', UploadAvatarView.as_view(), name='upload-avatar'),
    path('users/profile/password/', UpdatePasswordView.as_view(), name='update-password'),
    path('users/preferences/', UserPreferencesView.as_view(), name='user-preferences'),

    # User Management
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/create/', UserCreateView.as_view(), name='user-create'),
    path('users/<uuid:id>/', UserDetailView.as_view(), name='user-detail'),
    
    # Tenant Management
    path('tenants/create/', TenantCreateView.as_view(), name='tenant-create'),

    # Refresh token
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
