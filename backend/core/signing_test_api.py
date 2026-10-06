import base64
import hashlib
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from .api import project_scope
from .docusign_api import private
from .release_api import scoped_package as scoped_source
from .models import SigningTestPackage, SigningTestDocument
from . import signing_test as tests


def scoped_test(request,package_id):
    return get_object_or_404(SigningTestPackage.objects.select_related('source__plan__msr__project'),pk=package_id,
                            source__plan__msr__project__in=project_scope(request.user))


@api_view(['GET','POST'])
def packages(request,source_id):
    tests.development();source=scoped_source(request,source_id)
    if request.method=='POST':
        result,created=tests.prepare(request.user,source.id,request.data)
        return private(Response(tests.describe(result),status=201 if created else 200))
    return private(Response([tests.describe(p) for p in SigningTestPackage.objects.select_related('source__plan__msr__project').filter(source=source).order_by('-created_at','-id')]))


@api_view(['POST'])
def decision(request,package_id):
    package=scoped_test(request,package_id)
    result,_=tests.decide(request.user,package.id,request.data)
    return private(Response({'decision_id':str(result.id),**tests.describe(package)}))


@api_view(['POST'])
def connect(request,package_id):
    package=scoped_test(request,package_id)
    if not isinstance(request.data,dict):raise ValidationError('Provide an explicit sandbox test confirmation.')
    action=request.data.get('operation')
    if not isinstance(action,str) or action not in {'SEND','READ'}:raise ValidationError('Choose send or read.')
    return private(Response(tests.begin(request.user,request.session.session_key,package.id,
        tests.OP_SEND if action=='SEND' else tests.OP_READ,request.data.get('confirmed'))))


@api_view(['GET'])
def download(request,package_id,document_index):
    package=scoped_test(request,package_id);tests.validate(package,current=False)
    if document_index>=len(package.payload['documents']):raise NotFound()
    entry=package.payload['documents'][document_index]
    response=HttpResponse(base64.b64decode(entry['documentBase64'],validate=True),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="{entry["filename"]}"'
    return private(response)


@api_view(['GET'])
def retained(request,document_id):
    tests.development()
    document=get_object_or_404(SigningTestDocument.objects.select_related('attempt__package__source__plan__msr__project'),
        pk=document_id,attempt__package__source__plan__msr__project__in=project_scope(request.user))
    content=bytes(document.content)
    if hashlib.sha256(content).hexdigest()!=document.pdf_sha256:raise ValidationError('Retained signing-test PDF integrity verification failed.')
    response=HttpResponse(content,content_type='application/pdf');response['Content-Disposition']=f'attachment; filename="{document.filename}"'
    return private(response)
