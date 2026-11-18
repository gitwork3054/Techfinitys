"""Billing regression tests. Execute: python manage.py test workspace.test_billing -v 2."""
import json
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from .billing import generate_due_schedules, advance_months
from .models import ClientAccount, Member
from .billing_models import Invoice, InvoiceLine, InvoicePayment, BillingProfile, BillingSchedule


class InvoiceSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a=ClientAccount.objects.create(code='bill-alpha',name='Bill Alpha',company='Alpha Pvt Ltd',email='alpha@example.com')
        cls.b=ClientAccount.objects.create(code='bill-beta',name='Bill Beta',company='Beta Ltd',email='beta@example.com')
        def member(name,role,client=None):
            u=User.objects.create_user(username=name,password='safe-password-super-long-123',email=f'{name}@example.com')
            return Member.objects.create(user=u,role=role,client_account=client)
        cls.manager=member('bill-manager','manager')
        cls.admin=member('bill-admin','admin')
        cls.client_a=member('bill-client-a','client',cls.a)
        cls.client_b=member('bill-client-b','client',cls.b)
        cls.employee=member('bill-employee','employee')

    def act_as(self,actor):
        self.client.force_login(actor.user)

    def call(self,action,**data):
        return self.client.post('/api/billing/',json.dumps({'action':action,**data}),content_type='application/json')

    def base(self,client=None):
        return dict(clientId=str((client or self.a).pk),packageName='Social media campaign',quantity='1',
                    amount='10000',taxLabel='GST',taxRate='18',discount='500',billToAddress='Vadodara, Gujarat',
                    issueDate='2026-11-18',dueDate='2026-11-28',
                    items=[{'description':'Monthly package','quantity':'1','unitPrice':'10000'},
                           {'description':'Extra creative','quantity':'2','unitPrice':'1000'}])

    def draft(self,client=None):
        response=self.call('save_draft',**self.base(client))
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['invoice']

    def test_computed_totals_and_tenant_isolation(self):
        self.act_as(self.manager)
        draft=self.draft()
        self.assertEqual(Decimal(draft['subtotal']),Decimal('12000.00'))
        self.assertEqual(Decimal(draft['taxAmount']),Decimal('2070.00'))
        self.assertEqual(Decimal(draft['total']),Decimal('13570.00'))
        self.act_as(self.client_a)
        self.assertEqual(self.client.get('/api/billing/').json()['invoices'],[])
        self.assertEqual(self.client.get(f"/api/billing/pdf/{draft['id']}/").status_code,404)
        self.assertEqual(self.call('save_draft',**self.base()).status_code,403)
        self.act_as(self.manager)
        issued=self.call('issue',id=draft['id'])
        self.assertEqual(issued.status_code,200,issued.content)
        self.assertRegex(issued.json()['invoice']['number'],r'^TF-2026-\d{5}$')
        self.assertEqual(self.call('issue',id=draft['id']).status_code,400)
        self.assertEqual(self.call('save_draft',id=draft['id'],**self.base()).status_code,400)
        self.act_as(self.client_b)
        self.assertEqual(self.client.get('/api/billing/').json()['invoices'],[])
        self.assertEqual(self.client.get(f"/api/billing/pdf/{draft['id']}/").status_code,404)
        self.act_as(self.client_a)
        mine=self.client.get('/api/billing/').json()['invoices']
        self.assertEqual(len(mine),1)
        self.assertEqual(mine[0]['total'],'13570.00')
        pdf=self.client.get(f"/api/billing/pdf/{draft['id']}/")
        self.assertEqual(pdf.status_code,200)
        self.assertEqual(pdf['Content-Type'],'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF-'))

    def test_partial_and_full_payments_cannot_be_duplicated(self):
        self.act_as(self.manager)
        inv=self.draft()
        self.call('issue',id=inv['id'])
        result=self.call('payment',id=inv['id'],amount='1000',paidOn='2026-11-20',method='upi',reference='UPI-ABC')
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['invoice']['status'],'partially_paid')
        self.assertEqual(result.json()['invoice']['balanceDue'],'12570.00')
        self.assertEqual(self.call('payment',id=inv['id'],amount='1000',paidOn='2026-11-20',method='upi',reference='UPI-ABC').status_code,400)
        self.assertEqual(self.call('payment',id=inv['id'],amount='12571',paidOn='2026-11-20').status_code,400)
        last=self.call('payment',id=inv['id'],amount='12570',paidOn='2026-11-22',method='bank_transfer',reference='BANK-DEF')
        self.assertEqual(last.json()['invoice']['status'],'paid')
        self.assertEqual(last.json()['invoice']['balanceDue'],'0.00')
        self.assertEqual(InvoicePayment.objects.filter(invoice_id=inv['id']).count(),2)
        self.assertEqual(self.call('void',id=inv['id'],reason='Error').status_code,400)

    def test_admin_letterhead_and_issue_snapshot_are_immutable(self):
        self.act_as(self.admin)
        updated=self.call('profile',company_name='Techfinitys Private Limited',footer_text='Payment for agreed services',gstin='24ABCDE1234F1Z5')
        self.assertEqual(updated.status_code,200,updated.content)
        draft=self.draft()
        self.call('issue',id=draft['id'])
        self.call('profile',company_name='Different Name')
        issued=Invoice.objects.get(pk=draft['id'])
        self.assertEqual(issued.seller_snapshot['company_name'],'Techfinitys Private Limited')
        self.assertEqual(issued.seller_snapshot['gstin'],'24ABCDE1234F1Z5')
        self.act_as(self.manager)
        self.assertEqual(self.call('profile',company_name='Unauthorized').status_code,403)
        self.act_as(self.client_a)
        self.assertEqual(self.call('profile',company_name='Unauthorized').status_code,403)

    def test_employee_cannot_read_invoice_or_create_invoices(self):
        self.act_as(self.employee)
        self.assertEqual(self.client.get('/api/billing/').status_code,403)
        self.assertEqual(self.call('save_draft',**self.base()).status_code,403)

    def test_bad_values_rejected_without_partial_rows(self):
        self.act_as(self.manager)
        self.assertEqual(self.call('save_draft',**(self.base() | {'taxRate':'200'})).status_code,400)
        self.assertEqual(self.call('save_draft',**(self.base() | {'discount':'15000'})).status_code,400)
        self.assertEqual(Invoice.objects.count(),0)

    def test_void_retains_number_and_is_visible_to_original_client(self):
        self.act_as(self.manager)
        invoice=self.draft()
        self.call('issue',id=invoice['id'])
        void=self.call('void',id=invoice['id'],reason='Replaced invoice')
        self.assertEqual(void.status_code,200,void.content)
        self.act_as(self.client_a)
        self.assertEqual(self.client.get('/api/billing/').json()['invoices'][0]['status'],'void')
        self.assertTrue(self.client.get(f"/api/billing/pdf/{invoice['id']}/").content.startswith(b'%PDF-'))

    def test_recurring_generation_is_idempotent_and_issues_only_when_opted_in(self):
        self.act_as(self.manager)
        created=self.call('schedule',clientId=str(self.a.id),packageName='Monthly retainer',amount='9500',
                          quantity='1',months=1,nextRunOn='2026-01-31',dueDays=7,autoIssue=False)
        self.assertEqual(created.status_code,200,created.content)
        self.assertEqual(advance_months(date(2026,1,31),1,31),date(2026,2,28))
        first=generate_due_schedules(today=date(2026,2,28))
        self.assertEqual(len(first),2)
        self.assertEqual([i.status for i in first],['draft','draft'])
        self.assertEqual(generate_due_schedules(today=date(2026,2,28)),[])
        plan=BillingSchedule.objects.get(pk=created.json()['schedule']['id'])
        self.assertEqual(plan.next_run_on,date(2026,3,31))
        self.assertEqual(Invoice.objects.filter(recurring_schedule=plan).count(),2)
        self.assertEqual(InvoiceLine.objects.count(),2)
        self.assertEqual(self.call('schedule',id=str(plan.id),active=False).status_code,200)
        self.assertEqual(generate_due_schedules(today=date(2026,5,31)),[])

    def test_recurring_plan_can_be_paused_before_first_cycle_and_limits_amounts(self):
        self.act_as(self.manager)
        created=self.call('schedule',clientId=str(self.a.id),packageName='Monthly support',amount='1250',
                          quantity='1',months=1,nextRunOn='2027-01-10',dueDays=14)
        self.assertEqual(created.status_code,200,created.content)
        plan_id=created.json()['schedule']['id']
        paused=self.call('schedule',id=plan_id,active=False)
        self.assertEqual(paused.status_code,200,paused.content)
        self.assertFalse(paused.json()['schedule']['active'])
        resumed=self.call('schedule',id=plan_id,active=True)
        self.assertEqual(resumed.status_code,200,resumed.content)
        self.assertTrue(resumed.json()['schedule']['active'])
        huge=self.call('schedule',clientId=str(self.a.id),packageName='Too much',amount='999999999',
                       quantity='30',months=1,nextRunOn='2027-01-01')
        self.assertEqual(huge.status_code,400,huge.content)
