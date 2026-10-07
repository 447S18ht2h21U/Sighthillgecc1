import copy
from unittest.mock import patch
from django.test import TestCase, override_settings
from . import tests as foundation
from .models import Customer, Contact, User, Role, AuditEvent


@override_settings(DEBUG=True)
class CustomerManagementTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def customer_change(self, **fields):
        self.client.force_authenticate(self.sales)
        url=f'/api/customers/{self.customer.id}/'
        revision=self.client.get(url).data['revision']
        return self.client.patch(url,{'expected_revision':revision,'change_note':'Synthetic customer correction.',**fields},format='json')

    def contact_create(self, **fields):
        self.client.force_authenticate(self.sales)
        return self.client.post('/api/contacts/',{'customer':str(self.customer.id),'name':'Synthetic Contact','email':'contact@example.invalid','change_note':'Synthetic contact addition.',**fields},format='json')

    def contact_change(self, item, **fields):
        self.client.force_authenticate(self.sales)
        url=f'/api/contacts/{item.id}/';revision=self.client.get(url).data['revision']
        return self.client.patch(url,{'expected_revision':revision,'change_note':'Synthetic contact correction.',**fields},format='json')

    def test_master_edit_keeps_approved_snapshot_and_records_before_after(self):
        approved=self.approve();before=copy.deepcopy(approved.snapshot)
        response=self.customer_change(legal_name='Corrected Customer',billing_address='20 Revised Street',email='corrected@example.invalid',phone='301-555-0199')
        self.assertEqual(response.status_code,200)
        approved.refresh_from_db();self.assertEqual(approved.snapshot,before)
        event=AuditEvent.objects.get(action='customer.updated')
        self.assertEqual(event.payload['before']['legal_name'],'Example Customer')
        self.assertEqual(event.payload['after']['legal_name'],'Corrected Customer')
        self.assertEqual(event.payload['note'],'Synthetic customer correction.')

    def test_customer_stale_edit_and_note_are_required(self):
        self.client.force_authenticate(self.sales);url=f'/api/customers/{self.customer.id}/'
        old=self.client.get(url).data['revision'];self.assertEqual(self.customer_change(phone='301-555-0101').status_code,200)
        for values in [{'expected_revision':old,'change_note':'Stale correction.'},{'change_note':'No revision.'},{'expected_revision':self.client.get(url).data['revision']}]:
            self.assertEqual(self.client.patch(url,{'phone':'301-555-9999',**values},format='json').status_code,400)
        self.customer.refresh_from_db();self.assertEqual(self.customer.phone,'301-555-0101')

    def test_duplicate_identity_edit_requires_explicit_override(self):
        Customer.objects.create(legal_name='Existing Customer',billing_address='30 Existing Street',created_by=self.sales)
        self.assertEqual(self.customer_change(legal_name='Existing Customer',billing_address='30 Existing Street').status_code,400)
        response=self.customer_change(legal_name='Existing Customer',billing_address='30 Existing Street',duplicate_reason='Synthetic duplicate reviewed and retained separately.')
        self.assertEqual(response.status_code,200)
        self.assertIn('Synthetic duplicate',AuditEvent.objects.get(action='customer.updated').payload['duplicate_override'])
        self.assertEqual(self.customer_change(phone='301-555-0101').status_code,200)

    def test_archive_preserves_history_and_blocks_new_projects_and_contacts(self):
        self.approve();self.assertEqual(self.customer_change(archived=True).status_code,200)
        data={'customer':str(self.customer.id),'location':'40 New Street','sales_associate':str(self.sales.id),'reviewer':str(self.manager.id)}
        self.assertEqual(self.client.post('/api/projects/',data,format='json').status_code,400)
        self.assertEqual(self.contact_create().status_code,400)
        self.project.refresh_from_db();self.assertIsNotNone(self.project.current_approved_id)
        self.assertEqual(self.customer_change(archived=False).status_code,200)
        self.assertEqual(self.contact_create().status_code,201)

    def test_contacts_can_be_created_edited_and_filtered_by_customer(self):
        response=self.contact_create(primary=True,expected_primary_id='');self.assertEqual(response.status_code,201)
        item=Contact.objects.get(pk=response.data['id'])
        self.assertEqual(self.contact_change(item,relationship='Owner',phone='301-555-0123').status_code,200)
        other=Customer.objects.create(legal_name='Other Customer',billing_address='Other Street',created_by=self.sales)
        Contact.objects.create(customer=other,name='Other Contact')
        results=self.client.get(f'/api/contacts/?customer={self.customer.id}').data['results'];self.assertEqual([r['id'] for r in results],[str(item.id)])
        current=self.client.get(f'/api/customers/{self.customer.id}/').data
        self.assertEqual(current['primary_contact'],{'id':str(item.id),'name':item.name})

    def test_primary_replacement_requires_current_identity_and_confirmation(self):
        first=Contact.objects.create(customer=self.customer,name='First',primary=True)
        for values in [{'primary':True},{'primary':True,'expected_primary_id':str(first.id)},{'primary':True,'expected_primary_id':str(self.sales.id),'replace_primary_confirmed':True}]:
            self.assertEqual(self.contact_create(**values).status_code,400)
        response=self.contact_create(primary=True,expected_primary_id=str(first.id),replace_primary_confirmed=True)
        self.assertEqual(response.status_code,201);first.refresh_from_db();self.assertFalse(first.primary)
        self.assertEqual(Contact.objects.filter(customer=self.customer,primary=True).count(),1)
        self.assertTrue(Contact.objects.filter(pk=first.id).exists())
        self.assertEqual(AuditEvent.objects.filter(action='contact.primary_replaced').count(),1)

    def test_primary_can_transfer_to_an_existing_contact_or_be_cleared(self):
        first=Contact.objects.create(customer=self.customer,name='First',primary=True)
        second=Contact.objects.create(customer=self.customer,name='Second')
        self.assertEqual(self.contact_change(second,primary=True,expected_primary_id=str(first.id),replace_primary_confirmed=True).status_code,200)
        self.assertEqual(self.contact_change(second,primary=False).status_code,200)
        self.assertFalse(Contact.objects.filter(customer=self.customer,primary=True).exists())

    def test_contacts_cannot_move_customer_or_accept_stale_edits(self):
        item=Contact.objects.create(customer=self.customer,name='Contact')
        other=Customer.objects.create(legal_name='Other',billing_address='Street',created_by=self.sales)
        self.assertEqual(self.contact_change(item,customer=str(other.id)).status_code,400)
        url=f'/api/contacts/{item.id}/';old=self.client.get(url).data['revision']
        self.assertEqual(self.contact_change(item,phone='Updated').status_code,200)
        self.assertEqual(self.client.patch(url,{'expected_revision':old,'change_note':'Stale update.','name':'Stale'},format='json').status_code,400)
        item.refresh_from_db();self.assertEqual(item.name,'Contact');self.assertEqual(item.customer_id,self.customer.id)

    def test_record_scope_and_noncommercial_roles_block_changes(self):
        item=Contact.objects.create(customer=self.customer,name='Private Contact')
        self.client.force_authenticate(self.other)
        for url in [f'/api/customers/{self.customer.id}/',f'/api/contacts/{item.id}/']:
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.patch(url,{},format='json').status_code,404)
        for role in [Role.INSTALLATION_MANAGER,Role.TECHNICIAN,Role.ACCOUNTS_PAYABLE_ASSOCIATE,Role.DATABASE_ADMINISTRATOR]:
            self.other.role=role;self.other.save();self.client.force_authenticate(self.other)
            self.assertEqual(self.client.get('/api/customers/').data['results'],[])
            self.assertEqual(self.client.post('/api/customers/',{'legal_name':'Forbidden','billing_address':'Street'},format='json').status_code,403)
            self.assertEqual(self.client.post('/api/contacts/',{'customer':str(self.customer.id),'name':'Forbidden'},format='json').status_code,403)

    def test_assigned_manager_and_comptroller_can_edit_scoped_customers(self):
        for actor in [self.manager,self.comptroller]:
            self.client.force_authenticate(actor);url=f'/api/customers/{self.customer.id}/'
            revision=self.client.get(url).data['revision']
            self.assertEqual(self.client.patch(url,{'expected_revision':revision,'change_note':'Authorized scoped correction.','phone':actor.username},format='json').status_code,200)

    def test_inactive_actor_is_rechecked(self):
        self.sales.is_active=False;self.sales.save();self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.patch(f'/api/customers/{self.customer.id}/',{},format='json').status_code,403)
        self.assertEqual(self.client.post('/api/contacts/',{},format='json').status_code,403)

    def test_audit_failure_rolls_back_primary_transfer_and_customer_edit(self):
        first=Contact.objects.create(customer=self.customer,name='First',primary=True)
        with patch('core.api.audit',side_effect=RuntimeError('Synthetic audit failure')),self.assertRaises(RuntimeError):
            self.contact_create(primary=True,expected_primary_id=str(first.id),replace_primary_confirmed=True)
        first.refresh_from_db();self.assertTrue(first.primary);self.assertEqual(Contact.objects.count(),1)
        with patch('core.api.audit',side_effect=RuntimeError('Synthetic audit failure')),self.assertRaises(RuntimeError):self.customer_change(legal_name='Rolled back')
        self.customer.refresh_from_db();self.assertEqual(self.customer.legal_name,'Example Customer')

    def test_no_delete_api_and_private_paginated_contacts(self):
        Contact.objects.bulk_create([Contact(customer=self.customer,name=f'Contact {i}') for i in range(51)])
        self.client.force_authenticate(self.sales)
        response=self.client.get(f'/api/contacts/?customer={self.customer.id}')
        self.assertEqual(response.data['count'],51);self.assertEqual(len(response.data['results']),50)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(self.client.get(f'/api/contacts/?customer={self.customer.id}&page=2').data['results'].__len__(),1)
        item=Contact.objects.first()
        self.assertEqual(self.client.delete(f'/api/contacts/{item.id}/').status_code,405)
        self.assertEqual(self.client.delete(f'/api/customers/{self.customer.id}/').status_code,405)
        self.assertEqual(self.client.get('/api/contacts/?customer=invalid').status_code,400)

    def test_csrf_protects_customer_and_contact_mutations(self):
        from rest_framework.test import APIClient
        client=APIClient(enforce_csrf_checks=True);token=client.get('/api/csrf/').json()['csrfToken']
        self.assertEqual(client.post('/api/dev-login/',{'username':'sales','password':'LocalPassword123!'},format='json',HTTP_X_CSRFTOKEN=token).status_code,200)
        self.assertEqual(client.patch(f'/api/customers/{self.customer.id}/',{},format='json').status_code,403)
        self.assertEqual(client.post('/api/contacts/',{},format='json').status_code,403)
