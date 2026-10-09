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

class Contractor(Entity):
    """Permanent identity for a GECC independent contractor."""

    contractor_number = models.CharField(max_length=20, unique=True)
    legal_name = models.CharField(max_length=250)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    mailing_address = models.TextField(blank=True)

    user = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='contractor_profile',
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='contractors_created',
    )

    def __str__(self):
        return f"{self.contractor_number} - {self.legal_name}"

class ContractorEngagement(Entity):
    """A distinct period of service for a GECC contractor."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Onboarding'
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        TERMINATED = 'TERMINATED', 'Terminated'

    contractor = models.ForeignKey(
        Contractor,
        on_delete=models.PROTECT,
        related_name='engagements',
    )

    engagement_code = models.CharField(max_length=30, unique=True)
    role_description = models.CharField(max_length=150)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='contractor_engagements_created',
    )

    class Meta:
        ordering = ['contractor', 'start_date']

    def __str__(self):
        return f"{self.engagement_code} - {self.contractor.legal_name}"

class ContractorOnboardingDocument(Entity):
    """Tracks restricted contractor onboarding documents."""

    class Kind(models.TextChoices):
        W9 = 'W9', 'W-9 Tax Form'
        LICENSE_FRONT = 'LICENSE_FRONT', "Driver's License Front"
        LICENSE_BACK = 'LICENSE_BACK', "Driver's License Back"
        AGREEMENT = 'AGREEMENT', 'Independent Contractor Agreement'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    engagement = models.ForeignKey(
        ContractorEngagement,
        on_delete=models.PROTECT,
        related_name='onboarding_documents',
    )

    kind = models.CharField(max_length=30, choices=Kind.choices)
    storage_reference = models.CharField(max_length=500)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='contractor_documents_reviewed',
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ['engagement', 'kind', '-uploaded_at']

    def __str__(self):
        return f"{self.engagement.engagement_code} - {self.kind}"

class ContractorCompensationPlan(Entity):
    """Versioned compensation terms for a contractor engagement."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        APPROVED = 'APPROVED', 'Approved'
        SUPERSEDED = 'SUPERSEDED', 'Superseded'

    engagement = models.ForeignKey(
        ContractorEngagement,
        on_delete=models.PROTECT,
        related_name='compensation_plans',
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    effective_date = models.DateField()
    compensation_terms = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='contractor_compensation_plans_created',
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='contractor_compensation_plans_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['engagement', 'version'],
                name='contractor_compensation_version_unique',
            ),
        ]
        ordering = ['engagement', '-version']

    def __str__(self):
        return f'{self.engagement.engagement_code} - Compensation v{self.version}'


class CustomerPayment(Entity):
    """Customer payment receipt awaiting or holding verification."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Verification'
        VERIFIED = 'VERIFIED', 'Verified'
        REJECTED = 'REJECTED', 'Rejected'

    class Kind(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        FINAL = 'FINAL', 'Final Payment'
        FULL = 'FULL', 'Full Payment'

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='customer_payments',
    )

    msr = models.ForeignKey(
        MSR,
        on_delete=models.PROTECT,
        related_name='customer_payments',
    )

    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    received_date = models.DateField()

    payment_reference = models.CharField(
        max_length=150,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='customer_payments_recorded',
    )

    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='customer_payments_verified',
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['project', 'received_date', 'created_at']

    def __str__(self):
        return f'{self.project.code} - {self.kind} - ${self.amount}'

class CustomerPaymentAdjustment(Entity):
    """Auditable refund or reversal of a customer payment."""

    class Kind(models.TextChoices):
        REFUND = 'REFUND', 'Refund'
        REVERSAL = 'REVERSAL', 'Payment Reversal'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    payment = models.ForeignKey(
        CustomerPayment,
        on_delete=models.PROTECT,
        related_name='adjustments',
    )

    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    adjustment_date = models.DateField()

    adjustment_reference = models.CharField(
        max_length=150,
    )

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payment_adjustments_recorded',
    )

    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='payment_adjustments_approved',
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['payment', 'adjustment_date', 'created_at']

    def __str__(self):
        return (
            f'{self.payment.payment_reference} - '
            f'{self.kind} - ${self.amount}'
        )

class ProjectCostRecord(Entity):
    """Versioned project costs linked to an approved MSR."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        APPROVED = 'APPROVED', 'Approved'

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='cost_records',
    )
    msr = models.ForeignKey(
        MSR,
        on_delete=models.PROTECT,
        related_name='cost_records',
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    equipment_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    material_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    dealer_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    technician_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    lead_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=3000,
    )
    damon_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=500,
    )
    jerry_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=250,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='project_cost_records_created',
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='project_cost_records_approved',
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'version'],
                name='project_cost_version_unique',
            ),
        ]
        ordering = ['project', '-version']

    def __str__(self):
        return f'{self.project.code} - Costs v{self.version}'

class CommissionRecord(Entity):
    """Versioned earned commission record from approved calculations."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        APPROVED = 'APPROVED', 'Approved'

    class Kind(models.TextChoices):
        RYAN_VARIABLE = 'RYAN_VARIABLE', 'Ryan Variable Commission'
        DOUG_VARIABLE = 'DOUG_VARIABLE', 'Doug Variable Commission'

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='commission_records',
    )

    msr = models.ForeignKey(
        MSR,
        on_delete=models.PROTECT,
        related_name='commission_records',
    )

    kind = models.CharField(
        max_length=32,
        choices=Kind.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='commission_records_received',
    )

    rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
    )

    basis_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    deduction_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    final_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    calculation_snapshot = models.JSONField(
        default=dict,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='commission_records_created',
    )

    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='commission_records_approved',
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'project',
                    'kind',
                ],
                name='project_commission_kind_unique',
            ),
        ]
        ordering = ['project', 'kind']

    def __str__(self):
        return (
            f'{self.project.code} - '
            f'{self.kind} - ${self.final_amount}'
        )
