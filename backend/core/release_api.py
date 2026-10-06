import base64
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from .api import project_scope
from .docusign_api import private
from .models import MSR, ProjectEvidence, ReleasePackage
from .sandbox_api import scoped_plan
from . import release


def scoped_package(request,package_id):
    return get_object_or_404(ReleasePackage.objects.select_related('plan__msr__project'),pk=package_id,plan__msr__project__in=project_scope(request.user))


@api_view(['GET','POST'])
def evidence(request,msr_id):
    record=get_object_or_404(MSR,pk=msr_id,project__in=project_scope(request.user))
    if request.method=='POST':
        item,created=release.record_evidence(request.user,record.id,request.data)
        return private(Response({'id':str(item.id),'kind':item.kind,'digest':item.digest},status=201 if created else 200))
    rows=ProjectEvidence.objects.filter(msr=record).order_by('-created_at','-id')
    return private(Response([{'id':str(e.id),'kind':e.kind,'created_by':str(e.created_by_id),'created_at':e.created_at.isoformat(),'data':e.data,'digest':e.digest} for e in rows]))


@api_view(['GET','POST'])
def packages(request,plan_id):
    plan=scoped_plan(request,plan_id)
    if request.method=='POST':
        package,created=release.prepare_package(request.user,plan.id)
        return private(Response(release.describe(package),status=201 if created else 200))
    return private(Response([release.describe(p) for p in ReleasePackage.objects.select_related('plan__msr__project').filter(plan=plan).order_by('-created_at','-id')]))


@api_view(['POST'])
def decision(request,package_id):
    package=scoped_package(request,package_id)
    result,_=release.decide(request.user,package.id,request.data)
    return private(Response({'decision_id':str(result.id),**release.describe(package)}))


@api_view(['GET'])
def download(request,package_id,document_index):
    package=scoped_package(request,package_id);release.validate_package(package,check_current=False)
    if document_index>=len(package.payload['documents']):raise NotFound()
    entry=package.payload['documents'][document_index]
    response=HttpResponse(base64.b64decode(entry['documentBase64'],validate=True),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="{entry["filename"]}"'
    return private(response)
