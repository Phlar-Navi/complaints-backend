from django.contrib import admin
from django.urls import path, include
from users.views import TenantCreateView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin-tenant/', admin.site.urls),
    path('api/tenants/create/', TenantCreateView.as_view(), name='tenant-create'),
    path("api/", include("users.urls")),
    path("api/", include("complaints.urls")),
    # Gestion des tenants (PUBLIC SEULEMENT)
    path('api/', include('tenants.urls')),
    path("api/auth/token/refresh/", TokenRefreshView.as_view()),
]