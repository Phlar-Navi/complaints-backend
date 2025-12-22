from rest_framework import serializers
from complaints.models import (
    Complaint, ComplaintAttachment, ComplaintComment, 
    SLAConfig, ComplaintHistory
)
from users.serializers import UserSerializer


class ComplaintAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.full_name', 
        read_only=True
    )
    
    class Meta:
        model = ComplaintAttachment
        fields = [
            'id', 'filename', 'file', 'uploaded_at', 
            'uploaded_by', 'uploaded_by_name'
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']


class ComplaintCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = ComplaintComment
        fields = [
            'id', 'type', 'note', 'created_at',
            'user', 'user_name', 'user_email'
        ]
        read_only_fields = ['id', 'created_at', 'user']


class ComplaintListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_user_name = serializers.CharField(
        source='assigned_user.full_name', 
        read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)
    is_urgent_unhandled = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Complaint
        fields = [
            'id', 'reference', 'title', 'status', 'urgency',
            'category', 'category_name', 'assigned_user', 
            'assigned_user_name', 'submitted_at', 'sla_deadline',
            'is_overdue', 'is_urgent_unhandled', 'location'
        ]


class ComplaintDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour les détails"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(
        source='subcategory.name', 
        read_only=True
    )
    submitted_by_name = serializers.CharField(
        source='submitted_by.full_name',
        read_only=True
    )
    assigned_user_name = serializers.CharField(
        source='assigned_user.full_name',
        read_only=True
    )
    
    attachments = ComplaintAttachmentSerializer(many=True, read_only=True)
    comments = ComplaintCommentSerializer(many=True, read_only=True)
    
    is_overdue = serializers.BooleanField(read_only=True)
    is_urgent_unhandled = serializers.BooleanField(read_only=True)
    resolution_time = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Complaint
        fields = [
            'id', 'tenant', 'reference', 'title', 'description',
            'status', 'urgency', 'location', 'phone_number',
            'category', 'category_name', 'subcategory', 'subcategory_name',
            'submitted_by', 'submitted_by_name',
            'assigned_user', 'assigned_user_name',
            'submitted_at', 'closed_at', 'updated_at', 'sla_deadline',
            'is_overdue', 'is_urgent_unhandled', 'resolution_time',
            'attachments', 'comments'
        ]
        read_only_fields = [
            'id', 'reference', 'tenant', 'submitted_at', 
            'updated_at', 'submitted_by'
        ]


class ComplaintCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une plainte"""
    
    class Meta:
        model = Complaint
        fields = [
            'title', 'description', 'urgency', 'location',
            'phone_number', 'category', 'subcategory'
        ]
    
    def create(self, validated_data):
        # Ajouter automatiquement le tenant et l'utilisateur
        request = self.context.get('request')
        validated_data['tenant'] = request.tenant
        validated_data['submitted_by'] = request.user
        
        complaint = Complaint.objects.create(**validated_data)
        
        # Créer l'entrée d'historique
        ComplaintHistory.objects.create(
            tenant=complaint.tenant,
            complaint=complaint,
            complaint_reference=complaint.reference,
            action='CREATED',
            user=request.user,
            new_value={
                'title': complaint.title,
                'status': complaint.status,
                'urgency': complaint.urgency
            },
            description=f"Complaint created: {complaint.reference}"
        )
        
        return complaint


class ComplaintUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour une plainte"""
    
    class Meta:
        model = Complaint
        fields = [
            'title', 'description', 'status', 'urgency',
            'location', 'phone_number', 'category', 'subcategory',
            'assigned_user'
        ]
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        
        # Sauvegarder les anciennes valeurs pour l'historique
        old_values = {
            'status': instance.status,
            'urgency': instance.urgency,
            'assigned_user_id': str(instance.assigned_user.id) if instance.assigned_user else None,
        }
        
        # Mise à jour
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Si le statut passe à CLOSED ou RESOLVED, enregistrer closed_at
        if instance.status in ['CLOSED', 'RESOLVED'] and not instance.closed_at:
            from django.utils import timezone
            instance.closed_at = timezone.now()
        
        instance.save()
        
        # Nouvelles valeurs
        new_values = {
            'status': instance.status,
            'urgency': instance.urgency,
            'assigned_user_id': str(instance.assigned_user.id) if instance.assigned_user else None,
        }
        
        # Déterminer l'action
        action = 'UPDATED'
        description = f"Complaint {instance.reference} updated"
        
        if old_values['status'] != new_values['status']:
            action = 'STATUS_CHANGED'
            description = f"Status changed from {old_values['status']} to {new_values['status']}"
        elif old_values['assigned_user_id'] != new_values['assigned_user_id']:
            action = 'REASSIGNED' if old_values['assigned_user_id'] else 'ASSIGNED'
            description = f"Complaint assigned to {instance.assigned_user.full_name if instance.assigned_user else 'unassigned'}"
        
        # Créer l'entrée d'historique
        ComplaintHistory.objects.create(
            tenant=instance.tenant,
            complaint=instance,
            complaint_reference=instance.reference,
            action=action,
            user=request.user,
            old_value=old_values,
            new_value=new_values,
            description=description
        )
        
        return instance


class SLAConfigSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = SLAConfig
        fields = [
            'id', 'tenant', 'category', 'category_name',
            'urgency_level', 'delay_hours', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['tenant'] = request.tenant
        return super().create(validated_data)


class ComplaintHistorySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = ComplaintHistory
        fields = [
            'id', 'complaint_reference', 'action', 'user', 'user_name',
            'old_value', 'new_value', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']