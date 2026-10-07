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
    actor = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
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


class SigningPlan(Entity):
    """Immutable recipient/routing review; never evidence of sending or signing."""
    msr = models.ForeignKey(MSR, on_delete=models.PROTECT, related_name='signing_plans')
    group = models.CharField(max_length=32)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    review = models.JSONField()
    digest = models.CharField(max_length=64)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['msr', 'group', 'digest'], name='signing_review_unique')]
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Signing reviews are immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Signing reviews cannot be deleted.')


class DocusignChallenge(Entity):
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    state_digest = models.CharField(max_length=64, unique=True)
    session_digest = models.CharField(max_length=64)
    configuration_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    context = models.JSONField(default=dict)


class DocusignVerification(Entity):
    """Account verification evidence only; access/refresh tokens are never stored."""
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    challenge = models.OneToOneField(DocusignChallenge, on_delete=models.PROTECT)
    identity = models.JSONField()
    digest = models.CharField(max_length=64)
    class Meta:
        ordering = ['-created_at']
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Docusign verification evidence is immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Docusign verification evidence cannot be deleted.')


class SandboxPackage(Entity):
    """Immutable test-only PDFs and routing; never authorization for live signing."""
    plan = models.OneToOneField(SigningPlan, on_delete=models.PROTECT, related_name='sandbox_package')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    payload = models.JSONField()
    digest = models.CharField(max_length=64)
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Sandbox packages are immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Sandbox packages cannot be deleted.')


class SandboxAttempt(Entity):
    package = models.OneToOneField(SandboxPackage, on_delete=models.PROTECT, related_name='attempt')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    challenge = models.OneToOneField(DocusignChallenge, null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=32, default='AUTH_PENDING')
    account_id = models.CharField(max_length=36)
    envelope_id = models.CharField(max_length=36, blank=True)
    evidence = models.JSONField(default=dict)


class ProjectEvidence(Entity):
    msr = models.ForeignKey(MSR, on_delete=models.PROTECT, related_name='verification_evidence')
    kind = models.CharField(max_length=32)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    data = models.JSONField()
    digest = models.CharField(max_length=64)
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Verification evidence is immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Verification evidence cannot be deleted.')


class ReleasePackage(Entity):
    plan = models.ForeignKey(SigningPlan, on_delete=models.PROTECT, related_name='release_packages')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    payload = models.JSONField()
    digest = models.CharField(max_length=64)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan', 'digest'], name='release_package_unique')]
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Release packages are immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Release packages cannot be deleted.')


class ReleaseApproval(Entity):
    package = models.ForeignKey(ReleasePackage, on_delete=models.PROTECT, related_name='decisions')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20)
    note = models.TextField()
    package_digest = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Release decisions are immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Release decisions cannot be deleted.')


class SandboxObservation(Entity):
    """Immutable read-only provider check; never proof of signed work or permission to send."""
    attempt = models.ForeignKey(SandboxAttempt, on_delete=models.PROTECT, related_name='observations')
    challenge = models.OneToOneField(DocusignChallenge, on_delete=models.PROTECT)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    evidence = models.JSONField()
    digest = models.CharField(max_length=64)

    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Sandbox observations are immutable.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Sandbox observations cannot be deleted.')


class ImmutableSigningTestRecord(Entity):
    class Meta:
        abstract = True
    def save(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Signing-test records are immutable.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Signing-test records cannot be deleted.')


class SigningTestPackage(ImmutableSigningTestRecord):
    source = models.ForeignKey(ReleasePackage, on_delete=models.PROTECT, related_name='signing_tests')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    payload = models.JSONField()
    digest = models.CharField(max_length=64)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','digest'], name='signing_test_package_unique')]


class SigningTestDecision(ImmutableSigningTestRecord):
    package = models.ForeignKey(SigningTestPackage, on_delete=models.PROTECT, related_name='decisions')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20)
    note = models.TextField()
    digest = models.CharField(max_length=64)


class SigningTestAttempt(Entity):
    package = models.OneToOneField(SigningTestPackage, on_delete=models.PROTECT, related_name='attempt')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    challenge = models.OneToOneField(DocusignChallenge, null=True, on_delete=models.PROTECT)
    account_id = models.CharField(max_length=36)
    envelope_id = models.CharField(max_length=36, blank=True)
    state = models.CharField(max_length=32, default='AUTH_PENDING')
    first_send_started_at = models.DateTimeField(null=True)


class SigningTestObservation(ImmutableSigningTestRecord):
    attempt = models.ForeignKey(SigningTestAttempt, on_delete=models.PROTECT, related_name='observations')
    challenge = models.OneToOneField(DocusignChallenge, on_delete=models.PROTECT)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    evidence = models.JSONField()
    digest = models.CharField(max_length=64)


class SigningTestDocument(ImmutableSigningTestRecord):
    attempt = models.ForeignKey(SigningTestAttempt, on_delete=models.PROTECT, related_name='retained_documents')
    observation = models.ForeignKey(SigningTestObservation, on_delete=models.PROTECT)
    document_id = models.CharField(max_length=20)
    kind = models.CharField(max_length=32)
    filename = models.CharField(max_length=250)
    content = models.BinaryField()
    pdf_sha256 = models.CharField(max_length=64)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt','document_id'], name='signing_test_document_unique')]
