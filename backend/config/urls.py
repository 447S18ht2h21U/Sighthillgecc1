from core import catalog_bulk_import_api_4671
from core import ruud_catalog_import_api_4651
from core import msr_named_catalog_choices_api_4551
from core import product_catalog_collections_api_4546
from django.urls import path, include
from core import own_contractor_payment_api
from core import customer_payment_api_4714
from rest_framework.routers import DefaultRouter
from core import completion_provider_oauth_api_4611
from core import receipt_outbox_status_api_prototype_4209
from core import completion_send_oauth_api_4629, completion_envelope_api, installation_schedule_api, api, docusign_api, sandbox_api, release_api, signing_test_api, technical_assignment_api, operational_project_api, dashboard_api, financial_reporting_api, contractor_directory_api
router = DefaultRouter()
for prefix, view in [('customers', api.CustomerViewSet), ('contacts', api.ContactViewSet), ('projects', api.ProjectViewSet), ('msrs', api.MSRViewSet), ('documents', api.DocumentViewSet), ('audit', api.AuditViewSet), ('directory', api.DirectoryViewSet), ('accounts', api.AccountViewSet)]:
    router.register(prefix, view, basename=prefix)
router.register('customer-payments', customer_payment_api_4714.CustomerPaymentViewSet, basename='customer-payments')
router.register('installation-schedules', installation_schedule_api.InstallationScheduleViewSet, basename='installation-schedules')
router.register('installation-managers', installation_schedule_api.InstallationManagerDirectoryViewSet, basename='installation-managers')
router.register('technical-assignments', technical_assignment_api.TechnicalAssignmentViewSet, basename='technical-assignments')
router.register('technicians', technical_assignment_api.TechnicianDirectoryViewSet, basename='technicians')
router.register('technical-assignment-history', technical_assignment_api.TechnicalAssignmentHistoryViewSet, basename='technical-assignment-history')
router.register('operational-projects', operational_project_api.OperationalProjectViewSet, basename='operational-projects')
router.register('contractors', contractor_directory_api.ContractorDirectoryViewSet, basename='contractors')
from core.marketing_msr_api import MarketingMSRViewSet
router.register('marketing-msrs', MarketingMSRViewSet, basename='marketing-msrs')
from core.visible_msr_api import VisibleMSRViewSet
router.register('visible-msrs', VisibleMSRViewSet, basename='visible-msrs')
from core import fictional_document_preview_api_4525
from core import approved_msr_source_api_4530
from core import equipment_catalog_selection_api_4534
from core import equipment_catalog_management_api_4542
urlpatterns = [
    path('api/development-product-catalogs/bulk-csv/', catalog_bulk_import_api_4671.bulk_csv),
    path('api/development-product-catalogs/import-ruud-2026/', ruud_catalog_import_api_4651.import_ruud),
    path('api/development-msr-named-catalogs/', msr_named_catalog_choices_api_4551.msr_named_catalog_choices),
    path('api/development-product-catalogs/', product_catalog_collections_api_4546.collections),
    path('api/development-product-catalogs/<uuid:catalog_id>/', product_catalog_collections_api_4546.collection_detail),
    path('api/development-product-catalogs/<uuid:catalog_id>/products/', product_catalog_collections_api_4546.collection_products),
    path('api/development-product-catalogs/<uuid:catalog_id>/products/<uuid:equipment_id>/', product_catalog_collections_api_4546.collection_product_detail),

    path('api/development-equipment-management/', equipment_catalog_management_api_4542.manage_catalog),
    path('api/development-equipment-management/<uuid:equipment_id>/', equipment_catalog_management_api_4542.manage_catalog_item),
    path('api/development-equipment-catalog/', equipment_catalog_selection_api_4534.equipment_catalog_choices, name='equipment-catalog-4534'),
    path(
        'api/development-approved-msr-source/<uuid:project_id>/',
        approved_msr_source_api_4530.approved_msr_source,
        name='approved-msr-source-4530',
    ),
    path(
        'api/fictional-document-previews/<str:kind>/',
        fictional_document_preview_api_4525.fictional_document_preview,
        name='fictional-document-preview-4525',
    ),

    path(
        'api/own-contractor-payments/',
        own_contractor_payment_api.own_contractor_payment_history,
        name='own-contractor-payments',
    ),

    path(
        'api/financial-reports/',
        financial_reporting_api.financial_reports,
    ),
    path(
        'api/financial-reports/<uuid:report_id>/approve/',
        financial_reporting_api.financial_report_approve,
    ),
    path(
        'api/financial-reports/<uuid:report_id>/',
        financial_reporting_api.financial_report_detail,
    ),
    path(
        'api/completion-envelope-attempts/<uuid:attempt_id>/verify-sandbox/',
        completion_provider_oauth_api_4611.connect,
        name='completion-provider-oauth-4611',
    ),
    path('api/receipt-outboxes/<uuid:outbox_id>/status/', receipt_outbox_status_api_prototype_4209.ReceiptOutboxStatusPrototype.as_view(), name='receipt-outbox-status'),
    path('api/completion-envelope-attempts/<uuid:attempt_id>/', completion_envelope_api.detail),
    path('api/completion-envelope-attempts/<uuid:attempt_id>/sender-oauth/', completion_send_oauth_api_4629.connect),
    path('api/project-dashboard/', dashboard_api.project_dashboard),
    path('api/release-packages/<uuid:source_id>/signing-tests/', signing_test_api.packages),
    path('api/signing-tests/<uuid:package_id>/decisions/', signing_test_api.decision),
    path('api/signing-tests/<uuid:package_id>/connect/', signing_test_api.connect),
    path('api/signing-tests/<uuid:package_id>/documents/<int:document_index>/', signing_test_api.download),
    path('api/signing-test-documents/<uuid:document_id>/', signing_test_api.retained),
path('api/sandbox-packages/<uuid:package_id>/connect-check/', sandbox_api.connect_check), path('api/msrs/<uuid:msr_id>/verification-evidence/', release_api.evidence), path('api/signing-reviews/<uuid:plan_id>/release-packages/', release_api.packages), path('api/release-packages/<uuid:package_id>/decisions/', release_api.decision), path('api/release-packages/<uuid:package_id>/documents/<int:document_index>/', release_api.download), path('api/signing-reviews/<uuid:plan_id>/sandbox-package/', sandbox_api.package), path('api/sandbox-packages/<uuid:package_id>/documents/<int:document_index>/', sandbox_api.download), path('api/sandbox-packages/<uuid:package_id>/connect-draft/', sandbox_api.connect_draft), path('api/docusign/status/', docusign_api.status), path('api/docusign/connect/', docusign_api.connect), path('api/docusign/callback/', docusign_api.callback), path('api/csrf/', api.csrf), path('api/dev-login/', api.dev_login), path('api/logout/', api.end_session), path('api/me/', api.me), path('api/activity/', api.activity), path('api/', include(router.urls))]


