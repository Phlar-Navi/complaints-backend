import uuid
from django.db import models
from django.conf import settings

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

    category = models.ForeignKey("categories.Category", on_delete=models.SET_NULL, null=True, blank=True)
    subcategory = models.ForeignKey("categories.SubCategory", on_delete=models.SET_NULL, null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_complaints")
    assigned_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_complaints")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "reference"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.title}"
    
class ComplaintAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="attachments")
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="complaints/attachments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "complaint"])]

class ComplaintComment(models.Model):
    COMMENT_TYPE = [
        ("INTERNAL", "Internal"),
        ("PUBLIC", "Public"),
        ("SYSTEM", "System"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE)
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=20, choices=COMMENT_TYPE, default="INTERNAL")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "complaint"])]

