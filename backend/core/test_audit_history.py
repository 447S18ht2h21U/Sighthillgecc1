from datetime import datetime
from unittest.mock import patch
from django.db import transaction
from django.test import TestCase, override_settings
from . import tests as foundation
from .models import User, Role, AuditEvent
from .services import audit


@override_settings(DEBUG=True)
class AuditHistoryTests(TestCase):
    setUp = foundation.FoundationTests.setUp

    def record(self, action='customer.updated', payload=None, instant=None):
        with transaction.atomic():
            if instant:
                with patch('django.utils.timezone.now',return_value=datetime.fromisoformat(instant)):
                    return audit(self.sales,action,self.customer.id,payload or {'note':'Synthetic audit note.'})
            return audit(self.sales,action,self.customer.id,payload or {'note':'Synthetic audit note.'})

    def read(self, params=None):
        self.client.force_authenticate(self.comptroller)
        return self.client.get('/api/audit/',params or {})

    def test_readable_actor_values_original_evidence_and_private_headers(self):
        event=self.record(payload={'before':{'phone':'old'},'after':{'phone':'new'},'note':'Synthetic correction.'})
        response=self.read();self.assertEqual(response.status_code,200);item=response.data['results'][0]
        self.assertEqual(item['actor'],str(self.sales.id));self.assertEqual(item['actor_username'],'sales');self.assertEqual(item['actor_name'],'sales')
        self.assertEqual(item['payload'],event.payload);self.assertEqual(item['digest'],event.digest)
        self.assertEqual(response['Cache-Control'],'private, no-store');self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertNotIn('actor_email',item)

    def test_current_names_are_not_fabricated_as_historical_identity(self):
        event=self.record();User.objects.filter(pk=self.sales.id).update(first_name='Current',last_name='Profile')
        item=self.read().data['results'][0];self.assertEqual(item['actor_name'],'Current Profile');self.assertEqual(item['actor'],str(event.actor_id))
        event.refresh_from_db();self.assertNotIn('actor_name',event.payload)

    def test_all_other_roles_and_anonymous_are_denied(self):
        for role in Role.values:
            if role==Role.COMPTROLLER:continue
            User.objects.filter(pk=self.other.id).update(role=role);self.other.refresh_from_db();self.client.force_authenticate(self.other)
            self.assertEqual(self.client.get('/api/audit/').status_code,403)
        self.client.force_authenticate(None);self.assertEqual(self.client.get('/api/audit/').status_code,403)

    def test_stale_actor_role_or_inactive_state_is_rechecked(self):
        self.client.force_authenticate(self.comptroller);User.objects.filter(pk=self.comptroller.id).update(role=Role.SALES_MANAGER)
        self.assertEqual(self.client.get('/api/audit/').status_code,403)
        User.objects.filter(pk=self.comptroller.id).update(role=Role.COMPTROLLER,is_active=False)
        self.assertEqual(self.client.get('/api/audit/').status_code,403)

    def test_search_category_note_reason_person_and_record_id(self):
        first=self.record('contact.updated',{'note':'Unique contact correction.'});self.record('customer.updated',{'reason':'Separate customer reason.'})
        for params in [{'search':'unique CONTACT'},{'category':'contact'},{'search':'sales','category':'contact'},{'search':str(self.customer.id),'category':'contact'}]:
            response=self.read(params);self.assertEqual(response.status_code,200);self.assertEqual([r['id'] for r in response.data['results']],[str(first.id)])
        self.assertEqual(self.read({'search':'Separate customer reason.'}).data['count'],1)
        self.assertEqual(self.read({'search':'not recorded'}).data['count'],0)
        self.assertEqual(self.read({'category':'signing'}).data['count'],0)

    def test_eastern_date_boundaries_across_spring_dst(self):
        self.record(instant='2026-03-08T04:59:59+00:00')
        included=self.record(instant='2026-03-08T05:00:00+00:00')
        included2=self.record(instant='2026-03-09T03:59:59+00:00')
        self.record(instant='2026-03-09T04:00:00+00:00')
        response=self.read({'from':'2026-03-08','to':'2026-03-08','category':'customer'})
        self.assertEqual([r['id'] for r in response.data['results']],[str(included2.id),str(included.id)])

    def test_invalid_date_category_and_search_inputs_detail_ignores_list_filters(self):
        event=self.record()
        for params in [{'category':'invalid'},{'search':'x'*201},{'from':'bad'},{'to':'2026-02-30'},{'from':'2026-10-08','to':'2026-10-07'},{'to':'9999-12-31'}]:
            self.assertEqual(self.read(params).status_code,400)
        response=self.client.get(f'/api/audit/{event.id}/?category=invalid&search=missing')
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['id'],str(event.id))

    def test_pagination_newest_sequence_and_reads_preserve_original_history(self):
        for n in range(51):self.record(payload={'note':f'Pagination fixture {n}'})
        before=list(AuditEvent.objects.order_by('sequence').values_list('id','digest','payload'))
        first=self.read({'category':'customer'});second=self.read({'category':'customer','page':2})
        self.assertEqual(first.data['count'],51);self.assertEqual(len(first.data['results']),50);self.assertEqual(len(second.data['results']),1)
        sequences=[r['sequence'] for r in first.data['results']+second.data['results']];self.assertEqual(sequences,sorted(sequences,reverse=True))
        self.assertIn('category=customer',first.data['next']);self.assertIn('through_sequence=',first.data['next'])
        self.assertEqual(list(AuditEvent.objects.filter(id__in=[r[0] for r in before]).order_by('sequence').values_list('id','digest','payload')),before)
        self.assertEqual(AuditEvent.objects.filter(action='access.read').count(),2)
        event=first.data['results'][0]
        for method in ['post','patch','delete']:
            url='/api/audit/' if method=='post' else f"/api/audit/{event['id']}/"
            self.assertEqual(getattr(self.client,method)(url,{},format='json').status_code,405)

    def test_account_password_never_exposed_in_history(self):
        self.client.force_authenticate(self.comptroller);password='SyntheticAuditPassword2026!'
        response=self.client.post('/api/accounts/',{'username':'synthetic-audit-user','first_name':'Synthetic','last_name':'User','email':'audit@example.invalid','initials':'AU','role':'TECHNICIAN','password':password,'change_note':'Synthetic local provisioning.'},format='json');self.assertEqual(response.status_code,201)
        reset=self.client.patch(f"/api/accounts/{response.data['id']}/",{'password':password+'Reset','expected_revision':response.data['revision'],'change_note':'Synthetic local password reset.'},format='json');self.assertEqual(reset.status_code,200)
        item=self.read({'category':'account'}).data['results'][0]
        self.assertTrue(item['payload']['password_changed']);self.assertNotIn(password,str(item));self.assertNotIn(password+'Reset',str(item));self.assertNotIn('pbkdf2',str(item));self.assertNotIn('password',item['payload']['after'])
