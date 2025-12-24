from django.urls import path, include
from rest_framework.routers import DefaultRouter
from categories.views import CategoryViewSet, SubCategoryViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubCategoryViewSet, basename='subcategory')

urlpatterns = [
    path('', include(router.urls)),
]