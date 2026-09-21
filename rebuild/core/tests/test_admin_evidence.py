"""Operational navigation and financial-only access; no live provider calls."""
from decimal import Decimal
from django.test import TestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from core.models import User, AuditEvent, Membership, Wallet, Job, LedgerEntry, Reservation, Usage
from core.billing import reserve, settle
from core.tests.test_security import SyntheticFixture


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AdminEvidenceTests(SyntheticFixture, TestCase):
    def setUp(self):
        self.scope=self.make_scope('charge-reader')
        self.user,self.org,self.department,self.patient,self.template,self.encounter,_=self.scope
        self.encounter.notes='SENSITIVE_CLINICAL_MARKER'
        self.encounter.save(update_fields=['notes'])
        self.admin=User.objects.create_user(username='finance-review',email='finance-review@synthetic.invalid',verified_at=timezone.now(),is_staff=True)
        self.device=TOTPDevice.objects.create(user=self.admin,name='Synthetic authenticator',confirmed=True)
        self.job=Job.objects.create(encounter=self.encounter,user=self.user,config={'pricing_version':'configured-fixture-v1'})
        reserve(self.job,Decimal('1'))
        settle(self.job,Decimal('0.2'),{'input_tokens':100},{'input_per_million':'2000'},'anthropic:synthetic-fixture','req_isolated_admin_fixture',False)

    def admin_login(self):
        self.client.force_login(self.admin)
        session=self.client.session;session['otp_device_id']=self.device.persistent_id;session.save()

    def test_audit_pages_reach_older_records_and_preserve_filter(self):
        self.admin_login()
        for i in range(61):AuditEvent.objects.create(action='synthetic.filter',target=str(i))
        first=self.client.get('/console/audit/',{'q':'synthetic.filter'})
        second=self.client.get('/console/audit/',{'q':'synthetic.filter','page':2})
        self.assertEqual(len(first.context['audit_events']),50)
        self.assertEqual(len(second.context['audit_events']),11)
        self.assertFalse(set(e.pk for e in first.context['audit_events']) & set(e.pk for e in second.context['audit_events']))
        self.assertIn('q=synthetic.filter',first.context['navigation']['next'])
        self.assertContains(second,'Page 2 of 2')

    def test_admin_filters_and_totals_use_all_matching_usage(self):
        self.admin_login()
        response=self.client.get('/console/',{'q':'charge-reader'})
        self.assertContains(response,'charge-reader@synthetic.invalid')
        self.assertNotContains(response,'SENSITIVE_CLINICAL_MARKER')
        self.assertEqual(response.context['usage_totals']['cost'],Decimal('0.2'))
        self.assertEqual(response.context['usage_totals']['charge'],Decimal('0.3'))
        response=self.client.get('/console/',{'account_status':'inactive','job_state':'running'})
        self.assertEqual(response.context['users'].paginator.count,0)
        self.assertEqual(response.context['jobs'].paginator.count,0)

    def test_admin_account_pagination_does_not_truncate_at_100(self):
        self.admin_login()
        User.objects.bulk_create([User(username=f'page-{i}',email=f'page-{i}@synthetic.invalid') for i in range(105)])
        response=self.client.get('/console/',{'q':'page-','users_page':5})
        self.assertEqual(response.context['users'].paginator.count,105)
        self.assertEqual(len(response.context['users']),5)
        self.assertContains(response,'Records 101–105 of 105')

    def test_financial_administrator_has_evidence_but_no_clinical_payload(self):
        self.admin_login()
        response=self.client.get(f'/console/jobs/{self.job.pk}/')
        self.assertEqual(response.status_code,200)
        # ⚠️ THE MARKERS CHANGED WITH THE RENDERING, AND THE ASSERTION IS NOW STRICTLY STRONGER.
        # The page used to print the raw twelve-place Decimal ('0.200000000000'); it now prints
        # the exact value trimmed to at least cents. Rather than swap one literal for another,
        # these derive the expected text FROM THE STORED VALUES, so the test fails if the figure
        # changes, if the rendering loses precision, or if the row stops being displayed at all.
        from core.templatetags.console import usd
        usage=Usage.objects.get(job=self.job)
        for marker in ['configured-fixture-v1',
                       f'{usd(usage.actual_cost)} — configured estimate',
                       f'<dt>Cost × 1.5</dt><dd>{usd(usage.actual_cost*Decimal("1.5"))}</dd>',
                       f'<dt>Original user charge</dt><dd>{usd(usage.charged_cost)}</dd>',
                       'Promotional','Ledger agrees']:
            self.assertContains(response,marker,html=False)
        self.assertNotContains(response,'SENSITIVE_CLINICAL_MARKER')
        self.assertNotContains(response,self.patient.display_name)
        self.assertEqual(self.client.get(f'/api/encounters/{self.encounter.pk}/').status_code,404)
        self.assertEqual(self.client.get('/api/patients/').json()['patients'],[])
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin,action='admin.job_financial_read',target=self.job.pk).exists())

    def test_staff_without_mfa_and_nonstaff_cannot_read_admin_charge(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f'/console/jobs/{self.job.pk}/').status_code,302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/console/jobs/{self.job.pk}/').status_code,404)

    def test_own_billing_and_foreign_billing_are_separate(self):
        self.client.force_login(self.user)
        response=self.client.get(f'/billing/jobs/{self.job.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'SENSITIVE_CLINICAL_MARKER')
        other=self.make_scope('billing-foreign')[0]
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/billing/jobs/{self.job.pk}/').status_code,404)

    def test_other_payer_balances_remain_private(self):
        # An employee can explain their organization-paid usage, but cannot read
        # the organization's total or the balance recorded alongside its debit.
        self.department.organization_pays=True;self.department.save(update_fields=['organization_pays'])
        wallet=Wallet.objects.create(organization=self.org,kind='paid',balance=Decimal('123.456'))
        LedgerEntry.objects.create(wallet=wallet,amount=wallet.balance,balance_after=wallet.balance,kind='payment',key='synthetic-org-opening')
        self.job.payer=f'organization:{self.org.pk}'
        # The original authorized job is immutable: create a separate fixture job.
        job=Job.objects.create(encounter=self.encounter,user=self.user,payer=self.job.payer,request_key='isolated-org-balance-privacy')
        Reservation.objects.create(job=job,wallet=wallet,amount=Decimal('1'),state='settled')
        LedgerEntry.objects.create(wallet=wallet,job=job,amount=Decimal('-0.3'),balance_after=Decimal('123.156'),kind='usage',key=f'usage:{job.pk}:{wallet.pk}')
        self.client.force_login(self.user)
        response=self.client.get(f'/billing/jobs/{job.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'123.456');self.assertNotContains(response,'123.156')
        self.assertContains(response,'Restricted')

    def test_account_access_change_has_attribution_and_immediate_denial(self):
        from django.test import Client
        old=Client();old.force_login(self.user)
        self.admin_login();self.client.post(f'/console/accounts/{self.user.pk}/',{})
        self.assertEqual(old.get('/api/patients/').status_code,302)
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin,action='admin.account_access',target=self.user.pk,details__active=False).exists())
        self.client.post(f'/console/accounts/{self.user.pk}/',{'active':'on'})
        self.user.refresh_from_db();self.assertTrue(self.user.is_active)

    def test_filter_text_is_escaped_and_invalid_pages_are_safe(self):
        self.admin_login()
        response=self.client.get('/console/',{'q':'<script>unsafe</script>','users_page':'-9'})
        self.assertEqual(response.status_code,200);self.assertNotContains(response,'<script>unsafe</script>')
        self.assertContains(response,'&lt;script&gt;unsafe&lt;/script&gt;')
