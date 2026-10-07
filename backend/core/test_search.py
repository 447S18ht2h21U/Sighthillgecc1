from django.test import TestCase, override_settings
from . import tests as foundation
from .models import Customer, Contact, Project, User, Role, AuditEvent
from .services import revise, change_project_state


@override_settings(DEBUG=True)
class SearchTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def ids(self, url, actor=None):
        self.client.force_authenticate(actor or self.sales)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return [row['id'] for row in response.data['results']]

    def test_customer_search_fields_contacts_case_and_deduplication(self):
        self.customer.email='person@example.invalid';self.customer.phone='301-555-0111';self.customer.save()
        for name in ['Alternate Contact', 'Alternate Contact Two']:
            Contact.objects.create(customer=self.customer,name=name,email='contact@example.invalid',phone='301-555-0112')
        for term in ['eXaMpLe CuStOmEr', 'Main Street', 'person@example.invalid', '301-555-0111', 'Alternate', 'contact@example.invalid', '301-555-0112', '   Example   ']:
            self.assertEqual(self.ids('/api/customers/',actor=self.sales) if not term else self.ids('/api/customers/?search='+term),[str(self.customer.id)])
        self.assertEqual(self.ids('/api/customers/?search=missing'),[])

    def test_customer_archive_filter_combines_with_search(self):
        other=Customer.objects.create(legal_name='Example Archived',billing_address='20 Main Street',archived=True,created_by=self.sales)
        self.assertEqual(self.ids('/api/customers/?status=ACTIVE&search=Example'),[str(self.customer.id)])
        self.assertEqual(self.ids('/api/customers/?status=ARCHIVED&search=Example'),[str(other.id)])
        self.assertEqual(len(self.ids('/api/customers/?status=')),2)

    def test_project_search_code_location_and_customer_master(self):
        for term in [self.project.code,'12 Main','Example Customer']:
            self.assertEqual(self.ids('/api/projects/?search='+term),[str(self.project.id)])
        self.assertEqual(self.ids('/api/projects/?search=unrelated'),[])
        self.assertEqual(self.ids('/api/projects/?search=example&state=SUBMITTED'),[])
        self.assertEqual(self.ids('/api/projects/?search=example&state=DRAFT'),[str(self.project.id)])

    def test_project_search_preserves_recorded_name_after_master_correction(self):
        approved=self.approve();before=approved.snapshot.copy()
        self.customer.legal_name='Corrected Master';self.customer.save()
        self.assertEqual(self.ids('/api/projects/?search=Example Customer'),[str(self.project.id)])
        self.assertEqual(self.ids('/api/projects/?search=Corrected Master'),[str(self.project.id)])
        approved.refresh_from_db();self.assertEqual(approved.snapshot,before)

    def test_project_search_pending_name_and_revised_state(self):
        approved=self.approve();draft=revise(self.sales,self.project.id,'Synthetic revision',str(approved.id))
        snapshot=draft.snapshot.copy();snapshot['customer']='Pending Customer Name';draft.snapshot=snapshot;draft.save()
        self.assertEqual(self.ids('/api/projects/?search=Pending Customer Name&state=REVISED'),[str(self.project.id)])
        self.assertEqual(self.ids('/api/projects/?state=APPROVED'),[])
        self.assertEqual(self.ids('/api/projects/?search=Example Customer&state=REVISED'),[str(self.project.id)])

    def test_all_project_states_and_cancellation_do_not_hide_history(self):
        self.assertEqual(self.ids('/api/projects/?state=DRAFT'),[str(self.project.id)])
        self.edit_submit();self.assertEqual(self.ids('/api/projects/?state=SUBMITTED'),[str(self.project.id)])
        change_project_state(self.manager,self.project.id,'cancel','Synthetic cancel','SUBMITTED')
        self.assertEqual(self.ids('/api/projects/?state=CANCELLED'),[str(self.project.id)])
        self.assertEqual(self.ids('/api/projects/?state=SUBMITTED'),[])
        self.assertEqual(self.ids('/api/projects/?search=Example'),[str(self.project.id)])

    def test_scope_is_applied_before_all_search_filters(self):
        hidden=Customer.objects.create(legal_name='Secret Customer',billing_address='Secret Street',created_by=self.other)
        Contact.objects.create(customer=hidden,name='Secret Contact')
        hidden_project=Project.objects.create(code='SECRET-PROJECT',customer=hidden,location='Secret Site',sales_associate=self.other,reviewer=self.comptroller)
        for actor in [self.sales,self.manager]:
            for url in ['/api/customers/?search=Secret','/api/projects/?search=Secret','/api/customers/?status=ACTIVE&search=Secret','/api/projects/?state=DRAFT&search=Secret']:
                self.assertEqual(self.ids(url,actor),[])
        self.assertEqual(self.ids('/api/projects/?search=Secret',self.comptroller),[str(hidden_project.id)])
        self.assertEqual(self.ids('/api/customers/?search=Secret',self.comptroller),[str(hidden.id)])

    def test_current_role_and_active_state_are_rechecked(self):
        self.client.force_authenticate(self.sales)
        User.objects.filter(pk=self.sales.id).update(role=Role.TECHNICIAN)
        for url in ['/api/customers/?search=Example','/api/projects/?search=Main']:
            self.assertEqual(self.client.get(url).data['count'],0)
        User.objects.filter(pk=self.sales.id).update(role=Role.COMPTROLLER,is_active=False)
        for url in ['/api/customers/','/api/projects/']:
            self.assertEqual(self.client.get(url).data['count'],0)

    def test_invalid_filters_are_explicit_errors_but_do_not_filter_detail(self):
        self.client.force_authenticate(self.sales)
        for url in ['/api/customers/?status=unknown','/api/projects/?state=unknown','/api/projects/?sort=unknown','/api/customers/?search='+'x'*201,'/api/projects/?search='+'x'*201]:
            self.assertEqual(self.client.get(url).status_code,400)
        for url in [f'/api/customers/{self.customer.id}/?status=ARCHIVED&search=missing',f'/api/projects/{self.project.id}/?state=CANCELLED&search=missing']:
            self.assertEqual(self.client.get(url).status_code,200)

    def test_pagination_order_private_headers_and_no_search_mutation(self):
        for n in range(51):
            Project.objects.create(code=f'SYNTHETIC-{n:03}',customer=self.customer,location='Synthetic Location',sales_associate=self.sales,reviewer=self.manager)
        self.client.force_authenticate(self.sales);before=AuditEvent.objects.count()
        first=self.client.get('/api/projects/?search=SYNTHETIC&sort=CODE');second=self.client.get('/api/projects/?search=SYNTHETIC&sort=CODE&page=2')
        self.assertEqual(first.data['count'],51);self.assertEqual(len(first.data['results']),50);self.assertEqual(len(second.data['results']),1)
        self.assertIn('search=SYNTHETIC',first.data['next']);self.assertEqual(second.data['results'][0]['code'],'SYNTHETIC-050')
        self.assertEqual(first['Cache-Control'],'private, no-store')
        oldest=self.ids('/api/projects/?sort=OLDEST');self.assertEqual(oldest[0],str(self.project.id))
        self.assertEqual(AuditEvent.objects.count(),before)
