import time
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Customer, Contact, Project, MSR, User, Role, AuditEvent, Document, SigningPlan
from .services import EDITORS, create_project, transition, revise, audit, change_project_state
from .rules import PAYMENT_OPTIONS, SIGNATURE_WORKFLOWS

class Page(PageNumberPagination):
    page_size = 50

class AuditPage(Page):
    def bounded_link(self, link):
        from rest_framework.utils.urls import replace_query_param
        return replace_query_param(link, 'through_sequence', self.request.audit_snapshot_sequence) if link else None
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data['next'] = self.bounded_link(response.data['next'])
        response.data['previous'] = self.bounded_link(response.data['previous'])
        response.data['snapshot_sequence'] = self.request.audit_snapshot_sequence
        return response

def list_filters(request, choices):
    """Validate list-only filters; detail routes keep their usual access scope."""
    values = {}
    term = request.query_params.get('search', '').strip()
    if len(term) > 200:
        raise ValidationError({'search': 'Use at most 200 characters.'})
    values['search'] = term
    for name, allowed in choices.items():
        value = request.query_params.get(name, '')
        if value and value not in allowed:
            raise ValidationError({name: 'Choose one of: ' + ', '.join(allowed)})
        values[name] = value
    return values

def project_scope(user):
    qs = Project.objects.select_related('current_approved', 'pending')
    if user.role == Role.COMPTROLLER:
        return qs
    if user.role == Role.SALES_ASSOCIATE:
        return qs.filter(sales_associate=user)
    if user.role == Role.SALES_MANAGER:
        return qs.filter(reviewer=user)
    return qs.none()

def customer_scope(user):
    if user.role == Role.COMPTROLLER:
        return Customer.objects.all()
    if user.role not in EDITORS:
        return Customer.objects.none()
    return Customer.objects.filter(Q(created_by=user) | Q(project__in=project_scope(user))).distinct()

def record_values(item):
    fields = ['legal_name', 'billing_address', 'email', 'phone', 'archived'] if isinstance(item, Customer) else ['name', 'relationship', 'email', 'phone', 'primary']
    result = {field: getattr(item, field) for field in fields}
    if isinstance(item, Contact): result['customer'] = str(item.customer_id)
    return result


def record_revision(item):
    from .documents import canonical_hash
    return canonical_hash({'id': str(item.id), **record_values(item)})


def record_editor(actor, lock=False):
    qs = User.objects.select_for_update() if lock else User.objects
    current = qs.get(pk=actor.pk)
    if not current.is_active or current.role not in EDITORS:
        raise PermissionDenied('Customer and contact changes require an active authorized commercial user.')
    return current


class RecordChangeSerializer(serializers.ModelSerializer):
    revision = serializers.SerializerMethodField()
    expected_revision = serializers.CharField(write_only=True, required=False, max_length=64)
    change_note = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)
    def get_revision(self, instance): return record_revision(instance)
    def validate(self, attrs):
        if self.instance:
            if attrs.get('expected_revision') != record_revision(self.instance):
                raise ValidationError('This record changed. Refresh and reopen it before saving.')
            if not attrs.get('change_note', '').strip():
                raise ValidationError({'change_note': 'Explain this record change.'})
        return attrs


class CustomerSerializer(RecordChangeSerializer):
    duplicate_reason = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)
    primary_contact = serializers.SerializerMethodField()
    def get_primary_contact(self, instance):
        item = instance.contacts.filter(primary=True).first()
        return {'id':str(item.id), 'name':item.name} if item else None
    class Meta:
        model = Customer
        fields = ['id', 'legal_name', 'billing_address', 'email', 'phone', 'archived', 'created_at', 'duplicate_reason', 'revision', 'expected_revision', 'change_note', 'primary_contact']
        read_only_fields = ['id', 'created_at']

class ContactSerializer(RecordChangeSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), pk_field=serializers.UUIDField())
    replace_primary_confirmed = serializers.BooleanField(write_only=True, required=False)
    expected_primary_id = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=36)
    class Meta:
        model = Contact
        fields = ['id', 'customer', 'name', 'relationship', 'email', 'phone', 'primary', 'revision', 'expected_revision', 'change_note', 'replace_primary_confirmed', 'expected_primary_id']
        validators = []
        read_only_fields = ['id']
    def validate_customer(self, value):
        if not customer_scope(self.context['request'].user).filter(pk=value.pk).exists():
            raise ValidationError('Customer is unavailable.')
        if self.instance and value.pk != self.instance.customer_id:
            raise ValidationError('Contacts cannot be moved to another customer.')
        return value

class MSRSerializer(serializers.ModelSerializer):
    class Meta:
        model = MSR
        fields = ['id', 'number', 'status', 'snapshot', 'created_by', 'source', 'revision_reason', 'edit_sequence', 'submitted_at', 'approved_at', 'approved_by']

class ProjectSerializer(serializers.ModelSerializer):
    current_approved = MSRSerializer(read_only=True)
    pending = MSRSerializer(read_only=True)
    class Meta:
        model = Project
        fields = ['id', 'code', 'customer', 'location', 'sales_associate', 'reviewer', 'state', 'current_approved', 'pending', 'created_at']
        read_only_fields = fields

class ProjectInput(serializers.Serializer):
    customer = serializers.UUIDField()
    location = serializers.CharField(max_length=2000)
    sales_associate = serializers.UUIDField()
    reviewer = serializers.UUIDField()
    duplicate_reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)

class PrivateRecordViewSet(viewsets.ModelViewSet):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class CustomerViewSet(PrivateRecordViewSet):
    serializer_class = CustomerSerializer
    pagination_class = Page
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    def get_queryset(self):
        actor = User.objects.get(pk=self.request.user.pk)
        qs = customer_scope(actor).order_by('legal_name', 'id') if actor.is_active else Customer.objects.none()
        if self.action != 'list': return qs
        values = list_filters(self.request, {'status': ['ACTIVE', 'ARCHIVED']})
        if values['status']: qs = qs.filter(archived=values['status'] == 'ARCHIVED')
        term = values['search']
        if term:
            qs = qs.filter(Q(legal_name__icontains=term) | Q(email__icontains=term) | Q(phone__icontains=term) | Q(billing_address__icontains=term) | Q(contacts__name__icontains=term) | Q(contacts__email__icontains=term) | Q(contacts__phone__icontains=term)).distinct()
        return qs
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        record_editor(request.user, lock=True)
        return super().create(request, *args, **kwargs)
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        record_editor(request.user, lock=True)
        item = self.get_object()
        Customer.objects.select_for_update().get(pk=item.pk)
        return super().update(request, *args, **kwargs)
    def duplicate_check(self, values, instance=None):
        name = values.get('legal_name', instance.legal_name if instance else '')
        address = values.get('billing_address', instance.billing_address if instance else '')
        qs = Customer.objects.filter(legal_name__iexact=name, billing_address__iexact=address)
        if instance: qs = qs.exclude(pk=instance.pk)
        reason = values.pop('duplicate_reason', '')
        if instance and name.casefold() == instance.legal_name.casefold() and address.casefold() == instance.billing_address.casefold(): return reason
        if qs.exists() and not reason.strip():
            raise ValidationError({'duplicate_warning': 'Possible duplicate customer. Supply a duplicate override reason to continue.'})
        return reason
    def perform_create(self, serializer):
        reason = self.duplicate_check(serializer.validated_data)
        note = serializer.validated_data.pop('change_note', '')
        serializer.validated_data.pop('expected_revision', None)
        customer = serializer.save(created_by=self.request.user)
        audit(self.request.user, 'customer.created', customer.id, {'duplicate_override': reason, 'note':note, 'fields': serializer.data})
    def perform_update(self, serializer):
        reason = self.duplicate_check(serializer.validated_data, serializer.instance)
        before = record_values(serializer.instance)
        note = serializer.validated_data.pop('change_note')
        serializer.validated_data.pop('expected_revision')
        customer = serializer.save()
        audit(self.request.user, 'customer.updated', customer.id, {'before':before, 'after':record_values(customer), 'note':note, 'duplicate_override':reason})


class ContactViewSet(PrivateRecordViewSet):
    serializer_class = ContactSerializer
    pagination_class = Page
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    def get_queryset(self):
        actor = User.objects.get(pk=self.request.user.pk)
        qs = Contact.objects.filter(customer__in=customer_scope(actor)).order_by('name', 'id') if actor.is_active else Contact.objects.none()
        customer = self.request.query_params.get('customer')
        if customer: qs = qs.filter(customer_id=serializers.UUIDField().run_validation(customer))
        return qs
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        record_editor(request.user, lock=True)
        return super().create(request, *args, **kwargs)
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        record_editor(request.user, lock=True)
        item = self.get_object()
        Customer.objects.select_for_update().get(pk=item.customer_id)
        Contact.objects.select_for_update().get(pk=item.pk)
        return super().update(request, *args, **kwargs)
    def primary_change(self, serializer, customer, note):
        confirmed = serializer.validated_data.pop('replace_primary_confirmed', False)
        expected = serializer.validated_data.pop('expected_primary_id', '')
        if not serializer.validated_data.get('primary', False): return
        current = Contact.objects.select_for_update().filter(customer=customer, primary=True).first()
        current_id = str(current.id) if current else ''
        if expected != current_id:
            raise ValidationError('The primary contact changed. Refresh contacts and review your selection.')
        if current and (not serializer.instance or current.pk != serializer.instance.pk):
            if confirmed is not True:
                raise ValidationError('Confirm replacement of the current primary contact.')
            before = record_values(current); current.primary = False; current.save(update_fields=['primary'])
            audit(self.request.user, 'contact.primary_replaced', customer.id, {'contact_id':str(current.id), 'before':before, 'after':record_values(current), 'note':note})
    def perform_create(self, serializer):
        customer = Customer.objects.select_for_update().get(pk=serializer.validated_data['customer'].pk)
        if not customer_scope(record_editor(self.request.user)).filter(pk=customer.pk).exists(): raise PermissionDenied()
        if customer.archived: raise ValidationError('Restore the archived customer before adding a contact.')
        note = serializer.validated_data.pop('change_note', '')
        if not note.strip(): raise ValidationError({'change_note':'Explain this contact addition.'})
        serializer.validated_data.pop('expected_revision', None)
        self.primary_change(serializer, customer, note)
        item = serializer.save()
        audit(self.request.user, 'contact.created', item.customer_id, {'contact_id':str(item.id), 'fields':serializer.data, 'note':note})
    def perform_update(self, serializer):
        before = record_values(serializer.instance)
        note = serializer.validated_data.pop('change_note')
        serializer.validated_data.pop('expected_revision')
        self.primary_change(serializer, serializer.instance.customer, note)
        item = serializer.save()
        audit(self.request.user, 'contact.updated', item.customer_id, {'contact_id':str(item.id), 'before':before, 'after':record_values(item), 'note':note})

class ProjectViewSet(PrivateRecordViewSet):
    serializer_class = ProjectSerializer
    pagination_class = Page
    http_method_names = ['get', 'post', 'head', 'options']
    def get_queryset(self):
        actor = User.objects.get(pk=self.request.user.pk)
        qs = project_scope(actor).order_by('-created_at', '-id') if actor.is_active else Project.objects.none()
        if self.action != 'list': return qs
        values = list_filters(self.request, {'state': ['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'REVISED', 'CANCELLED'], 'sort': ['NEWEST', 'OLDEST', 'CODE']})
        if values['state']: qs = qs.filter(state=values['state'])
        term = values['search']
        if term:
            qs = qs.filter(Q(code__icontains=term) | Q(location__icontains=term) | Q(customer__legal_name__icontains=term) | Q(current_approved__snapshot__customer__icontains=term) | Q(pending__snapshot__customer__icontains=term))
        if values['sort'] == 'OLDEST': qs = qs.order_by('created_at', 'id')
        elif values['sort'] == 'CODE': qs = qs.order_by('code', 'id')
        return qs
    def create(self, request):
        input = ProjectInput(data=request.data)
        input.is_valid(raise_exception=True)
        data = input.validated_data
        customer = customer_scope(request.user).filter(pk=data['customer']).first()
        associate = User.objects.filter(pk=data['sales_associate'], is_active=True).first()
        reviewer = User.objects.filter(pk=data['reviewer'], is_active=True).first()
        if not all((customer, associate, reviewer)):
            raise ValidationError('Customer or assigned user is unavailable.')
        project = create_project(request.user, customer, data['location'], associate, reviewer, data.get('duplicate_reason', ''))
        return Response(ProjectSerializer(project).data, status=201)
    @action(detail=True, methods=['post'])
    def revision(self, request, pk=None):
        project = self.get_object()
        reason = request.data.get('reason', '')
        if not isinstance(reason, str) or len(reason) > 2000:
            raise ValidationError('Invalid reason.')
        draft = revise(request.user, project.id, reason, request.data.get('expected_approved_id'))
        return Response(MSRSerializer(draft).data, status=201)
    @action(detail=True, methods=['post'], url_path='state')
    def state_change(self, request, pk=None):
        project = self.get_object()
        reason = request.data.get('reason', '')
        if not isinstance(reason, str) or len(reason) > 2000:
            raise ValidationError('Invalid reason.')
        project = change_project_state(request.user, project.id, request.data.get('action'), reason, request.data.get('expected_state'))
        return Response(ProjectSerializer(project).data)

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        project = self.get_object()
        documents = Document.objects.select_related('msr').defer('content', 'values').filter(msr__project=project).order_by('-created_at')
        return Response(DocumentSerializer(documents, many=True).data)

    @action(detail=True, methods=['get'], url_path='signing-reviews')
    def signing_reviews(self, request, pk=None):
        project = self.get_object()
        plans = SigningPlan.objects.select_related('msr__project').filter(msr__project=project).order_by('-created_at')
        return Response(SigningPlanSerializer(plans, many=True).data)

    @action(detail=True, methods=['get'], url_path='signing-candidates')
    def signing_candidates(self, request, pk=None):
        from .services import authorize
        from .signing import candidates, GROUPS
        project = self.get_object()
        authorize(request.user, project, approval=True)
        group = request.query_params.get('group', 'COMMERCIAL')
        if group not in GROUPS:
            raise ValidationError('Choose a supported signing workflow.')
        return Response([{'id': str(u.id), 'name': u.get_full_name().strip(), 'email': u.email, 'role': u.role} for u in candidates(project, group).order_by('username')])

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        project = self.get_object()
        return Response(MSRSerializer(project.versions.order_by('number'), many=True).data)

class MSRViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MSRSerializer
    def get_queryset(self):
        return MSR.objects.filter(project__in=project_scope(self.request.user)).order_by('-created_at')
    @action(detail=True, methods=['post'], url_path='signing-reviews')
    def prepare_signing(self, request, pk=None):
        from .signing import prepare
        item = self.get_object()
        plan, created = prepare(request.user, item.id, request.data)
        return Response(SigningPlanSerializer(plan).data, status=201 if created else 200)
    @action(detail=True, methods=['post'], url_path='documents')
    def prepare_document(self, request, pk=None):
        from .documents import generate
        item = self.get_object()
        kind = request.data.get('kind')
        if not isinstance(kind, str):
            raise ValidationError('Document type is required.')
        document, created = generate(request.user, item.id, kind)
        return Response(DocumentSerializer(document).data, status=201 if created else 200)

    @action(detail=True, methods=['post'], url_path='transition')
    def change(self, request, pk=None):
        item = self.get_object()
        reason = request.data.get('reason', '')
        if not isinstance(reason, str) or len(reason) > 2000:
            raise ValidationError('Invalid reason.')
        result = transition(request.user, item.id, request.data.get('action'), request.data.get('expected_sequence'), snapshot=request.data.get('snapshot'), reason=reason)
        return Response(MSRSerializer(result).data)

class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = AuditPage
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    def get_queryset(self):
        actor = User.objects.get(pk=self.request.user.pk)
        if not actor.is_active or actor.role != Role.COMPTROLLER:
            raise PermissionDenied('Audit history requires an active Comptroller account.')
        qs = AuditEvent.objects.select_related('actor').order_by('-sequence')
        if self.action != 'list': return qs
        from .models import AuditHead
        current = AuditHead.objects.get(pk=1).sequence
        limit = serializers.IntegerField(min_value=0, max_value=current).run_validation(self.request.query_params.get('through_sequence', current))
        self.request.audit_snapshot_sequence = limit
        qs = qs.filter(sequence__lte=limit)
        values = list_filters(self.request, {'category': ['auth', 'access', 'customer', 'contact', 'account', 'project', 'msr', 'document', 'signing', 'docusign', 'sandbox', 'release', 'signing_test']})
        if values['category']: qs = qs.filter(action__startswith=values['category'] + '.')
        term = values['search']
        if term:
            matches = Q(action__icontains=term) | Q(actor__username__icontains=term) | Q(actor__first_name__icontains=term) | Q(actor__last_name__icontains=term) | Q(payload__note__icontains=term) | Q(payload__reason__icontains=term)
            from uuid import UUID
            try: matches |= Q(entity_id=UUID(term))
            except ValueError: pass
            qs = qs.filter(matches)
        from datetime import datetime, time, timedelta
        from zoneinfo import ZoneInfo
        dates = {}
        for name in ['from', 'to']:
            value = self.request.query_params.get(name, '')
            if value:
                try:
                    dates[name] = serializers.DateField().run_validation(value)
                    if name == 'to': dates[name] + timedelta(days=1)
                except (serializers.ValidationError, OverflowError):
                    raise ValidationError({name: 'Use a valid YYYY-MM-DD date (end date before 9999-12-31).'})
        if 'from' in dates and 'to' in dates and dates['from'] > dates['to']:
            raise ValidationError({'to': 'End date must be on or after start date.'})
        eastern = ZoneInfo('America/New_York')
        if 'from' in dates: qs = qs.filter(created_at__gte=datetime.combine(dates['from'], time.min, eastern))
        if 'to' in dates: qs = qs.filter(created_at__lt=datetime.combine(dates['to'] + timedelta(days=1), time.min, eastern))
        return qs
    class AuditSerializer(serializers.ModelSerializer):
        actor = serializers.PrimaryKeyRelatedField(read_only=True, pk_field=serializers.UUIDField())
        actor_username = serializers.CharField(source='actor.username', read_only=True, allow_null=True)
        actor_name = serializers.SerializerMethodField()
        def get_actor_name(self, event):
            if not event.actor_id: return 'Unauthenticated request'
            return event.actor.get_full_name().strip() or event.actor.username
        class Meta:
            model = AuditEvent
            fields = ['id', 'sequence', 'actor', 'actor_username', 'actor_name', 'action', 'entity_id', 'payload', 'previous_hash', 'digest', 'created_at']
    serializer_class = AuditSerializer

class DirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    class DirectorySerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ['id', 'username', 'first_name', 'last_name', 'role', 'initials']
    serializer_class = DirectorySerializer
    def get_queryset(self):
        if self.request.user.role not in EDITORS:
            return User.objects.none()
        return User.objects.filter(is_active=True, role__in=[Role.SALES_ASSOCIATE, Role.SALES_MANAGER]).order_by('username')

@api_view(['GET'])
def me(request):
    return Response({'id': str(request.user.id), 'username': request.user.username, 'role': request.user.role, 'development_auth': settings.DEBUG, 'payment_options': PAYMENT_OPTIONS, 'signature_workflows': SIGNATURE_WORKFLOWS})

@api_view(['POST'])
def activity(request):
    # The UI calls only on deliberate keyboard/pointer events, never on polling.
    request.session['last_activity'] = time.time()
    return Response({'ok': True})

@require_http_methods(['GET'])
def csrf(request):
    return JsonResponse({'csrfToken': get_token(request)})

@csrf_protect
@require_http_methods(['POST'])
def dev_login(request):
    if not settings.DEBUG:
        return JsonResponse({'detail': 'Development authentication is disabled.'}, status=404)
    import json
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        from .audit_context import NO_RESOURCE
        audit(None, 'auth.login_failed', NO_RESOURCE, {'reason': 'Invalid login request.'})
        return JsonResponse({'detail': 'Invalid JSON.'}, status=400)
    if not isinstance(data.get('username'), str) or not isinstance(data.get('password'), str):
        from .audit_context import NO_RESOURCE
        audit(None, 'auth.login_failed', NO_RESOURCE, {'reason': 'Invalid login request.'})
        return JsonResponse({'detail': 'Invalid credentials.'}, status=400)
    user = authenticate(request, username=data.get('username'), password=data.get('password'))
    if user is None:
        from .audit_context import NO_RESOURCE
        audit(None, 'auth.login_failed', NO_RESOURCE, {'reason': 'Invalid credentials.'})
        return JsonResponse({'detail': 'Invalid credentials.'}, status=400)
    audit(user, 'auth.login_succeeded', user.id, {})
    login(request, user)
    request.session['last_activity'] = time.time()
    return JsonResponse({'ok': True})

@api_view(['POST'])
def end_session(request):
    audit(request.user, 'auth.logout', request.user.id, {})
    logout(request)
    return Response({'ok': True})

def account_revision(user):
    from .documents import canonical_hash
    return canonical_hash({**account_values(user), 'credential_state': user.password})


def account_values(user):
    return {field: getattr(user, field) for field in ['username', 'email', 'first_name', 'last_name', 'role', 'initials', 'is_active']}


class AccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    revision = serializers.SerializerMethodField()
    expected_revision = serializers.CharField(write_only=True, required=False, max_length=64)
    change_note = serializers.CharField(write_only=True, max_length=2000)
    def get_revision(self, instance):
        return account_revision(instance)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'initials', 'is_active', 'password', 'revision', 'expected_revision', 'change_note']
        read_only_fields = ['id']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}
    def validate_initials(self, value):
        import re
        if not re.fullmatch('[A-Z]{1,8}', value):
            raise ValidationError('Use 1–8 uppercase letters.')
        return value
    def validate(self, attrs):
        if self.instance and attrs.get('expected_revision') != account_revision(self.instance):
            raise ValidationError('This account changed. Refresh users, reopen the account and review the latest values.')
        if not attrs.get('change_note', '').strip():
            raise ValidationError({'change_note': 'Explain this account change.'})
        if not self.instance and not attrs.get('password'):
            raise ValidationError('A development password is required.')
        if 'password' in attrs:
            user = self.instance or User(**{k: v for k, v in attrs.items() if k not in {'password', 'change_note', 'expected_revision'}})
            try:
                validate_password(attrs['password'], user)
            except DjangoValidationError as exc:
                raise ValidationError({'password': exc.messages})
        return attrs
    def create(self, validated_data):
        validated_data.pop('expected_revision', None)
        validated_data.pop('change_note')
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)
    def update(self, instance, validated_data):
        validated_data.pop('expected_revision', None)
        validated_data.pop('change_note')
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance

class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    pagination_class = Page
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    def get_queryset(self):
        actor = User.objects.get(pk=self.request.user.pk)
        if not actor.is_active or actor.role != Role.COMPTROLLER:
            raise PermissionDenied('Only the Comptroller administers business accounts.')
        return User.objects.order_by('username')
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        User.objects.select_for_update().get(pk=request.user.pk)
        self.get_queryset()
        return super().create(request, *args, **kwargs)
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        target = self.get_object()
        # Lock both accounts in a stable order before permission/revision validation.
        list(User.objects.select_for_update().filter(pk__in=[request.user.pk, target.pk]).order_by('pk'))
        self.get_queryset()
        return super().update(request, *args, **kwargs)
    def perform_create(self, serializer):
        self.get_queryset()
        if not settings.DEBUG:
            raise ValidationError('Production identity provisioning requires the Cognito adapter.')
        with transaction.atomic():
            note = serializer.validated_data['change_note']
            user = serializer.save()
            audit(self.request.user, 'account.created', user.id, {'role': user.role, 'active': user.is_active, 'after': account_values(user), 'note': note})
    def perform_update(self, serializer):
        if not settings.DEBUG:
            raise ValidationError('Production identity provisioning requires the Cognito adapter.')
        if serializer.instance.pk == self.request.user.pk and ('role' in serializer.validated_data or serializer.validated_data.get('is_active') is False):
            raise ValidationError('Self-demotion or self-deactivation is not allowed.')
        with transaction.atomic():
            before = account_values(serializer.instance)
            note = serializer.validated_data['change_note']
            password_changed = 'password' in serializer.validated_data
            user = serializer.save()
            audit(self.request.user, 'account.updated', user.id, {'role': user.role, 'active': user.is_active, 'before': before, 'after': account_values(user), 'note': note, 'password_changed': password_changed})


class DocumentSerializer(serializers.ModelSerializer):
    msr_version = serializers.IntegerField(source='msr.number', read_only=True)
    download_url = serializers.SerializerMethodField()
    class Meta:
        model = Document
        fields = ['id', 'msr', 'msr_version', 'kind', 'status', 'filename', 'created_at', 'created_by', 'template_sha256', 'snapshot_sha256', 'pdf_sha256', 'renderer_version', 'download_url']
    def get_download_url(self, obj):
        return f'/api/documents/{obj.id}/download/'


class SigningPlanSerializer(serializers.ModelSerializer):
    release = serializers.SerializerMethodField()
    class Meta:
        model = SigningPlan
        fields = ['id', 'msr', 'group', 'created_at', 'created_by', 'digest', 'review', 'release']
        read_only_fields = fields
    def get_release(self, obj):
        from .signing import status
        return status(obj)

class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentSerializer
    pagination_class = Page
    def get_queryset(self):
        qs = Document.objects.select_related('msr').defer('content', 'values').filter(msr__project__in=project_scope(self.request.user)).order_by('-created_at')
        msr_id = self.request.query_params.get('msr')
        if msr_id:
            from uuid import UUID
            try:
                UUID(msr_id)
            except ValueError:
                raise ValidationError('Invalid MSR identifier.')
            qs = qs.filter(msr_id=msr_id)
        return qs
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        import hashlib
        document = self.get_object()
        content = bytes(document.content)
        if hashlib.sha256(content).hexdigest() != document.pdf_sha256:
            raise ValidationError('Document integrity check failed.')
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{document.filename}"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
