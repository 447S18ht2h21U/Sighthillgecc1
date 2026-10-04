from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import api
router = DefaultRouter()
for prefix, view in [('customers', api.CustomerViewSet), ('contacts', api.ContactViewSet), ('projects', api.ProjectViewSet), ('msrs', api.MSRViewSet), ('audit', api.AuditViewSet), ('directory', api.DirectoryViewSet), ('accounts', api.AccountViewSet)]:
    router.register(prefix, view, basename=prefix)
urlpatterns = [path('api/csrf/', api.csrf), path('api/dev-login/', api.dev_login), path('api/logout/', api.end_session), path('api/me/', api.me), path('api/activity/', api.activity), path('api/', include(router.urls))]
