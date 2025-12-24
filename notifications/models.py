"""
Créer une nouvelle app Django : python manage.py startapp notifications
Puis créer ce fichier : notifications/models.py
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    """
    Modèle pour les notifications utilisateur
    """
    
    TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('SUCCESS', 'Succès'),
        ('WARNING', 'Avertissement'),
        ('ERROR', 'Erreur'),
        ('COMPLAINT_ASSIGNED', 'Plainte assignée'),
        ('COMPLAINT_UPDATED', 'Plainte mise à jour'),
        ('COMPLAINT_COMMENT', 'Nouveau commentaire'),
        ('SLA_WARNING', 'Alerte SLA'),
        ('SYSTEM', 'Système'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Destinataire
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Contenu
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='INFO')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Métadonnées
    link = models.CharField(max_length=500, blank=True, null=True)  # URL de redirection
    complaint_id = models.UUIDField(null=True, blank=True)  # Référence à une plainte
    
    # État
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['tenant', 'user']),
        ]
    
    def __str__(self):
        return f"{self.type} - {self.user.email} - {self.title}"
    
    def mark_as_read(self):
        """Marquer comme lue"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type='INFO', 
                           link=None, complaint_id=None, tenant=None):
        """
        Méthode helper pour créer une notification
        """
        return cls.objects.create(
            user=user,
            tenant=tenant or user.tenant,
            type=notification_type,
            title=title,
            message=message,
            link=link,
            complaint_id=complaint_id
        )


class UserPreferences(models.Model):
    """
    Préférences utilisateur (pour le profil)
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences'
    )
    
    # Notifications
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Apparence
    theme = models.CharField(
        max_length=20,
        choices=[('light', 'Clair'), ('dark', 'Sombre')],
        default='light'
    )
    language = models.CharField(
        max_length=10,
        choices=[('fr', 'Français'), ('en', 'English')],
        default='fr'
    )
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Préférences de {self.user.email}"