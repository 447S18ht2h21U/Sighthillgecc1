import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError

class Role(models.TextChoices):
    SALES_ASSOCIATE = 'SALES_ASSOCIATE', 'Sales Associate'
    SALES_MANAGER = 'SALES_MANAGER', 'Sales Manager'
    COMPTROLLER = 'COMPTROLLER', 'Comptroller'
    INSTALLATION_MANAGER = 'INSTALLATION_MANAGER', 'Installation Manager'
    TECHNICIAN = 'TECHNICIAN', 'Technician'
    ACCOUNTS_PAYABLE_ASSOCIATE = 'ACCOUNTS_PAYABLE_ASSOCIATE', 'Accounts Payable Associate'
    DATABASE_ADMINISTRATOR = 'DATABASE_ADMINISTRATOR', 'Database Administrator'

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=32, choices=Role.choices)
    initials = models.CharField(max_length=8)

class Entity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        abstract = True

class Customer(Entity):
    legal_name = models.CharField(max_length=250)
    billing_address = models.TextField()
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

class Contact(Entity):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='contacts')
    name = models.CharField(max_length=250)
    relationship = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    primary = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['customer'], condition=models.Q(primary=True), name='one_primary_contact')]

class Project(Entity):
    code = models.CharField(max_length=80, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    location = models.TextField()
    sales_associate = models.ForeignKey(User, on_delete=models.PROTECT, related_name='sales_projects')
    reviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='review_projects')
    state = models.CharField(max_length=20, default='DRAFT')
    current_approved = models.ForeignKey('MSR', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    pending = models.ForeignKey('MSR', null=True, blank=True, on_delete=models.PROTECT, related_name='+')

class MSR(Entity):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='versions')
    number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default='DRAFT')
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    prepared_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    source = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    revision_reason = models.TextField(blank=True)
    edit_sequence = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'number'], name='project_version_unique')]
    def save(self, *args, **kwargs):
        old = type(self).objects.filter(pk=self.pk).first()
        if old and old.status == 'APPROVED':
            raise ValidationError('Approved versions are immutable. Create a revision.')
        if old and old.status == 'SUBMITTED' and old.snapshot != self.snapshot:
            raise ValidationError('Submitted commercial fields are frozen.')
        super().save(*args, **kwargs)

class AuditHead(models.Model):
    id = models.PositiveIntegerField(primary_key=True, default=1)
    sequence = models.PositiveBigIntegerField(default=0)
    digest = models.CharField(max_length=64, default='0' * 64)

class AuditEvent(Entity):
    sequence = models.PositiveBigIntegerField(unique=True)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    entity_id = models.UUIDField()
    payload = models.JSONField()
    previous_hash = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Audit events are append-only.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be deleted.')

class Outbox(Entity):
    event = models.OneToOneField(AuditEvent, on_delete=models.PROTECT)
    topic = models.CharField(max_length=80)
    payload = models.JSONField()
    delivered_at = models.DateTimeField(null=True, blank=True)

class LocalCounter(models.Model):
    # Development only. Production uses a PostgreSQL sequence, outside rollback.
    id = models.PositiveIntegerField(primary_key=True, default=1)
    value = models.PositiveIntegerField(default=100)


class Document(Entity):
    class Kind(models.TextChoices):
        CONTRACT = 'CONTRACT', 'Project SOW agreement'
        INVOICE = 'INVOICE', 'HVAC invoice'
        COMPLETION_FINANCED = 'COMPLETION_FINANCED', 'Financed completion certificate'
        COMPLETION_NON_FINANCED = 'COMPLETION_NON_FINANCED', 'Non-financed completion certificate'
    msr = models.ForeignKey(MSR, on_delete=models.PROTECT, related_name='documents')
    kind = models.CharField(max_length=32, choices=Kind.choices)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='PREPARATION')
    filename = models.CharField(max_length=200)
    template_sha256 = models.CharField(max_length=64)
    snapshot_sha256 = models.CharField(max_length=64)
    pdf_sha256 = models.CharField(max_length=64)
    renderer_version = models.CharField(max_length=20)
    values = models.JSONField()
    content = models.BinaryField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['msr', 'kind', 'template_sha256', 'renderer_version'], name='document_generation_unique')]
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Generated documents are immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Generated documents cannot be deleted.')
