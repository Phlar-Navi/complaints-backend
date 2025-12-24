from rest_framework import serializers
from categories.models import Category, SubCategory


class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class CategoryListSerializer(serializers.ModelSerializer):
    """Serializer léger pour la liste"""
    subcategory_count = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'tenant', 'tenant_name',
            'subcategory_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_subcategory_count(self, obj):
        return obj.subcategories.count()


class CategoryDetailSerializer(serializers.ModelSerializer):
    """Serializer complet avec sous-catégories"""
    subcategories = SubCategorySerializer(many=True, read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    complaint_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'tenant', 'tenant_name',
            'subcategories', 'complaint_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_complaint_count(self, obj):
        try:
            return obj.complaints.count()
        except:
            return 0


class CategoryCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une catégorie"""
    
    class Meta:
        model = Category
        fields = ['name', 'description', 'tenant']
    
    def create(self, validated_data):
        return Category.objects.create(**validated_data)


class SubCategoryCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une sous-catégorie"""
    
    class Meta:
        model = SubCategory
        fields = ['name', 'description', 'category', 'tenant']
    
    def create(self, validated_data):
        return SubCategory.objects.create(**validated_data)