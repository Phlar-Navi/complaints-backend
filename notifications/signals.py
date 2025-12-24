"""
notifications/signals.py - Créer automatiquement des notifications
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from complaints.models import Complaint, ComplaintComment
from notifications.models import Notification


@receiver(post_save, sender=Complaint)
def create_complaint_notification(sender, instance, created, **kwargs):
    """
    Créer des notifications lors de la création/modification d'une plainte
    """
    
    # Nouvelle plainte assignée à un agent
    if instance.assigned_user and not created:
        # Vérifier si l'assignation a changé
        if instance.tracker.has_changed('assigned_user'):
            Notification.create_notification(
                user=instance.assigned_user,
                tenant=instance.tenant,
                title="Nouvelle plainte assignée",
                message=f"La plainte {instance.reference} vous a été assignée : {instance.title}",
                notification_type='COMPLAINT_ASSIGNED',
                link=f"/complaints/{instance.id}",
                complaint_id=instance.id
            )
    
    # Alerte SLA proche
    if instance.is_overdue and not created:
        if instance.assigned_user:
            Notification.create_notification(
                user=instance.assigned_user,
                tenant=instance.tenant,
                title="⚠️ SLA dépassé",
                message=f"La plainte {instance.reference} a dépassé le délai SLA !",
                notification_type='SLA_WARNING',
                link=f"/complaints/{instance.id}",
                complaint_id=instance.id
            )


@receiver(post_save, sender=ComplaintComment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    Notifier lors d'un nouveau commentaire
    """
    if created:
        complaint = instance.complaint
        
        # Notifier l'agent assigné (si ce n'est pas lui qui commente)
        if complaint.assigned_user and complaint.assigned_user != instance.user:
            Notification.create_notification(
                user=complaint.assigned_user,
                tenant=complaint.tenant,
                title="Nouveau commentaire",
                message=f"Nouveau commentaire sur {complaint.reference} par {instance.user.full_name}",
                notification_type='COMPLAINT_COMMENT',
                link=f"/complaints/{complaint.id}",
                complaint_id=complaint.id
            )
        
        # Notifier le créateur de la plainte (si différent)
        if complaint.submitted_by and complaint.submitted_by != instance.user:
            Notification.create_notification(
                user=complaint.submitted_by,
                tenant=complaint.tenant,
                title="Nouveau commentaire",
                message=f"Nouveau commentaire sur votre plainte {complaint.reference}",
                notification_type='COMPLAINT_COMMENT',
                link=f"/complaints/{complaint.id}",
                complaint_id=complaint.id
            )


# ==================== notifications/apps.py ====================

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    
    def ready(self):
        # Importer les signals
        import notifications.signals