import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from model_utils import FieldTracker

# Dans la classe Complaint, ajouter :
# tracker = FieldTracker(fields=['assigned_user', 'status'])

class Complaint(models.Model):
    STATUS_CHOICES = [
        ("NEW", "New"),
        ("RECEIVED", "Received"),
        ("ASSIGNED", "Assigned"),
        ("IN_PROGRESS", "In Progress"),
        ("INVESTIGATION", "Investigation"),
        ("ACTION", "Action In Progress"),
        ("RESOLVED", "Resolved"),
        ("ARCHIVED", "Archived"),
        ("CLOSED", "Closed"),
    ]
    URGENCY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    reference = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="NEW")
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default="MEDIUM")
    location = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    sla_deadline = models.DateTimeField(null=True, blank=True)
    
    category = models.ForeignKey(
        "categories.Category", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="complaints"
    )
    subcategory = models.ForeignKey(
        "categories.SubCategory", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="complaints"
    )
    
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_complaints"
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaints"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    tracker = FieldTracker(fields=['assigned_user', 'status'])
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant", "reference"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "submitted_at"]),
            models.Index(fields=["tenant", "urgency"]),
            models.Index(fields=["assigned_user", "status"]),
            models.Index(fields=["sla_deadline"]),
        ]
        ordering = ["-submitted_at"]
    
    def __str__(self):
        return f"{self.reference} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Générer la référence si elle n'existe pas
        if not self.reference:
            self.reference = self.generate_reference()
        
        # Si c'est une nouvelle plainte, définir submitted_at maintenant
        is_new = self._state.adding
        if is_new and not self.submitted_at:
            from django.utils import timezone
            self.submitted_at = timezone.now()
        
        # Calculer le SLA deadline si pas déjà défini
        if not self.sla_deadline and self.category and self.urgency and self.submitted_at:
            self.calculate_sla_deadline()
        
        super().save(*args, **kwargs)
    
    def generate_reference(self):
        """Génère une référence unique pour la plainte"""
        from datetime import datetime
        year = datetime.now().year
        
        # Compter les plaintes du tenant pour cette année
        count = Complaint.objects.filter(
            tenant=self.tenant,
            submitted_at__year=year
        ).count() + 1
        
        return f"{self.tenant.schema_name.upper()}-{year}-{count:05d}"
    
    def calculate_sla_deadline(self):
        """Calcule la deadline SLA basée sur la config"""
        if not self.submitted_at:
            # Si submitted_at n'est pas encore défini, on ne peut pas calculer
            return
        
        try:
            from complaints.models import SLAConfig
            sla_config = SLAConfig.objects.get(
                tenant=self.tenant,
                category=self.category,
                urgency_level=self.urgency
            )
            self.sla_deadline = self.submitted_at + timedelta(hours=sla_config.delay_hours)
        except SLAConfig.DoesNotExist:
            # SLA par défaut si pas de config
            default_hours = {"LOW": 72, "MEDIUM": 48, "HIGH": 24}
            self.sla_deadline = self.submitted_at + timedelta(
                hours=default_hours.get(self.urgency, 48)
            )
    
    @property
    def is_overdue(self):
        """Vérifie si la plainte a dépassé le SLA"""
        if self.sla_deadline and self.status not in ["RESOLVED", "CLOSED", "ARCHIVED"]:
            return timezone.now() > self.sla_deadline
        return False
    
    @property
    def is_urgent_unhandled(self):
        """Vérifie si c'est une plainte urgente non traitée"""
        return self.urgency == "HIGH" and self.status in ["NEW", "RECEIVED"]
    
    @property
    def resolution_time(self):
        """Calcule le temps de résolution en heures"""
        if self.closed_at:
            delta = self.closed_at - self.submitted_at
            return delta.total_seconds() / 3600  # en heures
        return None


class ComplaintAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="attachments"
    )
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="complaints/attachments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        indexes = [models.Index(fields=["tenant", "complaint"])]
    
    def __str__(self):
        return f"{self.filename} - {self.complaint.reference}"


class ComplaintComment(models.Model):
    COMMENT_TYPE = [
        ("INTERNAL", "Internal"),
        ("PUBLIC", "Public"),
        ("SYSTEM", "System"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="comments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    type = models.CharField(max_length=20, choices=COMMENT_TYPE, default="INTERNAL")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [models.Index(fields=["tenant", "complaint"])]
        ordering = ["created_at"]
    
    def __str__(self):
        return f"Comment on {self.complaint.reference} by {self.user}"


class SLAConfig(models.Model):
    URGENCY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        related_name="sla_configs"
    )
    urgency_level = models.CharField(max_length=10, choices=URGENCY_CHOICES)
    delay_hours = models.PositiveIntegerField(
        help_text="Allowed hours to respect SLA for this combo"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ("tenant", "category", "urgency_level")
        indexes = [
            models.Index(fields=["tenant", "category", "urgency_level"])
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.category.name} - {self.urgency_level}"


class ComplaintHistory(models.Model):
    """Traçabilité des modifications importantes"""
    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("STATUS_CHANGED", "Status Changed"),
        ("ASSIGNED", "Assigned"),
        ("REASSIGNED", "Reassigned"),
        ("COMMENT_ADDED", "Comment Added"),
        ("ATTACHMENT_ADDED", "Attachment Added"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="history",
        null=True  # null si la plainte est supprimée
    )
    complaint_reference = models.CharField(max_length=64)  # Garder même si supprimée
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["tenant", "complaint"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["action"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.action} on {self.complaint_reference} at {self.created_at}"
    