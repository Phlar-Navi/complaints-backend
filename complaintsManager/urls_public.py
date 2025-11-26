from django.contrib import admin
from django.urls import path, include
from users.views import TenantCreateView

urlpatterns = [
    path('admin-tenant/', admin.site.urls),
    path('api/tenants/create/', TenantCreateView.as_view(), name='tenant-create'),
    path("api/", include("users.urls")),
]
