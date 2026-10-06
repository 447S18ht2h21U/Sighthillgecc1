from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .api import project_scope
from .docusign_api import private
from .models import SandboxPackage, SigningPlan
from . import sandbox


def scoped_plan(request, plan_id):
    return get_object_or_404(SigningPlan.objects.select_related('msr__project'),
                            pk=plan_id, msr__project__in=project_scope(request.user))


def scoped_package(request, package_id):
    return get_object_or_404(SandboxPackage.objects.select_related('plan__msr__project'),
                            pk=package_id, plan__msr__project__in=project_scope(request.user))


@api_view(['GET', 'POST'])
def package(request, plan_id):
    plan = scoped_plan(request, plan_id)
    if request.method == 'POST':
        result, created = sandbox.prepare_package(request.user, plan.id)
        return private(Response(sandbox.describe(result), status=201 if created else 200))
    result = SandboxPackage.objects.filter(plan=plan).first()
    if result is None:
        return private(JsonResponse(None, safe=False))
    return private(Response(sandbox.describe(result)))


@api_view(['GET'])
def download(request, package_id, document_index):
    result = scoped_package(request, package_id)
    sandbox.validate_package(result, check_current=False)
    if document_index >= len(result.payload['documents']):
        from rest_framework.exceptions import NotFound
        raise NotFound()
    import base64
    entry = result.payload['documents'][document_index]
    response = HttpResponse(base64.b64decode(entry['documentBase64'], validate=True), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{entry["filename"]}"'
    return private(response)


@api_view(['POST'])
def connect_draft(request, package_id):
    result = scoped_package(request, package_id)
    if not isinstance(request.data, dict):
        from rest_framework.exceptions import ValidationError
        raise ValidationError('Provide a sandbox draft confirmation object.')
    return private(Response(sandbox.begin_draft(request.user, request.session.session_key,
                                               result.id, request.data.get('confirm_unsent_sandbox_draft'))))
