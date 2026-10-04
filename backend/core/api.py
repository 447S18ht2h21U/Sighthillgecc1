import time
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Customer, Contact, Project, MSR, User, Role, AuditEvent
from .services import EDITORS, create_project, transition, revise, audit, change_project_state
from .rules import PAYMENT_OPTIONS, SIGNATURE_WORKFLOWS

class Page(PageNumberPagination):
    page_size = 50

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

class CustomerSerializer(serializers.ModelSerializer):
    duplicate_reason = serializers.CharField(write_only=True, required=False, allow_blank=True)
    class Meta:
        model = Customer
        fields = ['id', 'legal_name', 'billing_address', 'email', 'phone', 'archived', 'created_at', 'duplicate_reason']
        read_only_fields = ['id', 'created_at']

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'customer', 'name', 'relationship', 'email', 'phone', 'primary']
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

class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    pagination_class = Page
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    def get_queryset(self):
        qs = customer_scope(self.request.user).order_by('legal_name')
        term = self.request.query_params.get('search', '')[:200]
        return qs.filter(Q(legal_name__icontains=term) | Q(email__icontains=term)) if term else qs
    def perform_create(self, serializer):
        if self.request.user.role not in EDITORS:
            raise PermissionDenied()
        reason = serializer.validated_data.pop('duplicate_reason', '')
        if Customer.objects.filter(legal_name__iexact=serializer.validated_data['legal_name'], billing_address__iexact=serializer.validated_data['billing_address']).exists() and not reason.strip():
            raise ValidationError({'duplicate_warning': 'Possible duplicate customer. Supply duplicate_reason to continue.'})
        with transaction.atomic():
            customer = serializer.save(created_by=self.request.user)
            audit(self.request.user, 'customer.created', customer.id, {'duplicate_override': reason, 'fields': serializer.data})
    def perform_update(self, serializer):
        serializer.validated_data.pop('duplicate_reason', None)
        with transaction.atomic():
            Customer.objects.select_for_update().get(pk=serializer.instance.pk)
            customer = serializer.save()
            audit(self.request.user, 'customer.updated', customer.id, {'fields': serializer.data})

class ContactViewSet(viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    pagination_class = Page
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    def get_queryset(self):
        return Contact.objects.filter(customer__in=customer_scope(self.request.user)).order_by('name')
    def perform_create(self, serializer):
        if self.request.user.role not in EDITORS:
            raise PermissionDenied()
        with transaction.atomic():
            item = serializer.save()
            audit(self.request.user, 'contact.created', item.customer_id, {'fields': serializer.data})
    def perform_update(self, serializer):
        with transaction.atomic():
            item = serializer.save()
            audit(self.request.user, 'contact.updated', item.customer_id, {'fields': serializer.data})

class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectSerializer
    pagination_class = Page
    def get_queryset(self):
        qs = project_scope(self.request.user).order_by('-created_at')
        term = self.request.query_params.get('search', '')[:200]
        return qs.filter(Q(code__icontains=term) | Q(location__icontains=term)) if term else qs
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
    def history(self, request, pk=None):
        project = self.get_object()
        return Response(MSRSerializer(project.versions.order_by('number'), many=True).data)

class MSRViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MSRSerializer
    def get_queryset(self):
        return MSR.objects.filter(project__in=project_scope(self.request.user)).order_by('-created_at')
    @action(detail=True, methods=['post'], url_path='transition')
    def change(self, request, pk=None):
        item = self.get_object()
        reason = request.data.get('reason', '')
        if not isinstance(reason, str) or len(reason) > 2000:
            raise ValidationError('Invalid reason.')
        result = transition(request.user, item.id, request.data.get('action'), request.data.get('expected_sequence'), snapshot=request.data.get('snapshot'), reason=reason)
        return Response(MSRSerializer(result).data)

class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = Page
    def get_queryset(self):
        if self.request.user.role != Role.COMPTROLLER:
            raise PermissionDenied('Audit history requires Comptroller access.')
        return AuditEvent.objects.order_by('-sequence')
    class AuditSerializer(serializers.ModelSerializer):
        class Meta:
            model = AuditEvent
            fields = ['id', 'sequence', 'actor', 'action', 'entity_id', 'payload', 'previous_hash', 'digest', 'created_at']
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
        return JsonResponse({'detail': 'Invalid JSON.'}, status=400)
    user = authenticate(request, username=data.get('username'), password=data.get('password'))
    if user is None:
        return JsonResponse({'detail': 'Invalid credentials.'}, status=400)
    login(request, user)
    request.session['last_activity'] = time.time()
    return JsonResponse({'ok': True})

@api_view(['POST'])
def end_session(request):
    logout(request)
    return Response({'ok': True})

class AccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'initials', 'is_active', 'password']
        read_only_fields = ['id']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}
    def validate_initials(self, value):
        import re
        if not re.fullmatch('[A-Z]{1,8}', value):
            raise ValidationError('Use 1–8 uppercase letters.')
        return value
    def validate(self, attrs):
        if not self.instance and not attrs.get('password'):
            raise ValidationError('A development password is required.')
        if 'password' in attrs:
            user = self.instance or User(**{k: v for k, v in attrs.items() if k != 'password'})
            try:
                validate_password(attrs['password'], user)
            except DjangoValidationError as exc:
                raise ValidationError({'password': exc.messages})
        return attrs
    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)
    def update(self, instance, validated_data):
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
    def get_queryset(self):
        if self.request.user.role != Role.COMPTROLLER:
            raise PermissionDenied('Only the Comptroller administers business accounts.')
        return User.objects.order_by('username')
    def perform_create(self, serializer):
        self.get_queryset()
        if not settings.DEBUG:
            raise ValidationError('Production identity provisioning requires the Cognito adapter.')
        with transaction.atomic():
            user = serializer.save()
            audit(self.request.user, 'account.created', user.id, {'role': user.role, 'active': user.is_active})
    def perform_update(self, serializer):
        if not settings.DEBUG:
            raise ValidationError('Production identity provisioning requires the Cognito adapter.')
        if serializer.instance.pk == self.request.user.pk and ('role' in serializer.validated_data or serializer.validated_data.get('is_active') is False):
            raise ValidationError('Self-demotion or self-deactivation is not allowed.')
        with transaction.atomic():
            user = serializer.save()
            audit(self.request.user, 'account.updated', user.id, {'role': user.role, 'active': user.is_active})
