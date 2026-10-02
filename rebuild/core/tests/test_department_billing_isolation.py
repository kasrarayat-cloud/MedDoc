"""Financial authorization stays on the actual request's department, with own-history positives.

Synthetic rows only: distinct markers expose list/detail/aggregate/search leaks without provider calls.
"""
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import (AuditEvent, Department, Encounter, Job, LedgerEntry, Membership,
                         Organization, Patient, Reservation, Template, TemplateVersion,
                         Usage, User, Wallet)
from core.tests.test_workflow import TEST_SETTINGS


@override_settings(**TEST_SETTINGS, QUILLMD_PREVIEW_AUTH_ENABLED=False)
class DepartmentBillingIsolation(TestCase):
    def account(self, name, department, role='clinician', active=True):
        user = User.objects.create_user(username=name, email=name+'@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=user, department=department, role=role, active=active)
        client = Client(); client.force_login(user)
        return user, client

    def setUp(self):
        self.organization = Organization.objects.create(name='Synthetic shared payer')
        self.a = Department.objects.create(organization=self.organization, name='AUTHORIZED_DEPARTMENT', organization_pays=True)
        self.b = Department.objects.create(organization=self.organization, name='FOREIGN_DEPARTMENT_MARKER', organization_pays=True)
        self.owner, self.client = self.account('department-owner', self.a, 'owner')
        self.author, _ = self.account('authorized-requester', self.a)
        self.foreign_author, self.foreign_client = self.account('FOREIGN_REQUESTER_MARKER', self.b)
        self.wallet = Wallet.objects.create(organization=self.organization, kind='paid', balance=Decimal('91.83'), reserved=Decimal('7.91'))
        self.personal = Wallet.objects.create(user=self.owner, kind='promo', balance=Decimal('2.75'))
        self.jobs = {}
        for tag, department, author in [('authorized', self.a, self.author), ('foreign', self.b, self.foreign_author)]:
            template = Template.objects.create(department=department, name=tag, format='docx', original_name='synthetic.docx',
                original_path=tag+'.docx', sha256='a'*64, created_by=author)
            version = TemplateVersion.objects.create(template=template, number=1, fields=[], created_by=author)
            patient = Patient.objects.create(department=department, display_name='SYNTHETIC '+tag,
                reference=tag, created_by=author)
            encounter = Encounter.objects.create(department=department, patient=patient, template_version=version,
                notes='SYNTHETIC_SECRET_NOTES_'+tag, service_date=timezone.localdate(), created_by=author)
            for kind in ['generation', 'transcription', 'mapping']:
                scope = {'mapping_version': version} if kind=='mapping' else {'encounter': encounter}
                job = Job.objects.create(**scope, user=author, kind=kind, payer='organization:'+str(self.organization.pk),
                    request_key=tag+':'+kind, state='reconciliation', config=({'source_sha256': template.sha256,
                    'department_id': str(department.pk), 'mapping_version_id': str(version.pk)} if kind=='mapping' else {}))
                self.jobs[tag, kind] = job
                Reservation.objects.create(job=job, wallet=self.wallet, amount=Decimal('.13') if tag=='authorized' else Decimal('1.97'))
                LedgerEntry.objects.create(wallet=self.wallet, job=job, amount=Decimal('-.03'), kind='usage',
                    key=tag+':'+kind, description=tag.upper()+'_LEDGER_MARKER', balance_after=self.wallet.balance)
                Usage.objects.create(job=job, user=author, department=department, organization=self.organization,
                    payer=job.payer, provider=tag.upper()+'_PROVIDER_MARKER', actual_cost=Decimal('.02'),
                    charged_cost=Decimal('.03'), simulated=True)
        LedgerEntry.objects.create(wallet=self.wallet, amount=Decimal('91.83'), kind='funding', key='foreign:unscoped',
            description='FOREIGN_UNSCOPED_LEDGER_MARKER', balance_after=self.wallet.balance)

    def money(self):
        return {model.__name__: list(model.objects.order_by('pk').values())
                for model in [Job, Reservation, LedgerEntry, Usage, Wallet]}

    def test_list_search_pagination_totals_and_ledger_never_disclose_foreign_requests(self):
        before = self.money()
        for query in ['', '?q=FOREIGN', '?q='+str(self.jobs['foreign', 'mapping'].pk), '?usage_page=100&ledger_page=100']:
            with self.subTest(query=query):
                page = self.client.get('/billing/'+query)
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, 'FOREIGN_')
                self.assertNotContains(page, '91.83')
                self.assertNotContains(page, '7.91')
                self.assertTrue(all(row['job'].department_id==self.a.pk for row in page.context['held_requests']))
                self.assertTrue(all(row['usage'].department_id==self.a.pk for row in page.context['usage']))
                self.assertTrue(all(entry.job_id and entry.job.department_id==self.a.pk for entry in page.context['ledger']))
                expected = Decimal('.06') if not query or query.startswith('?usage_page') else None
                self.assertEqual(page.context['usage_totals']['cost'], expected)
        self.assertEqual(self.money(), before)

    def test_detail_is_authorized_by_the_actual_encounter_or_mapping_department(self):
        before = self.money()
        for kind in ['generation', 'transcription', 'mapping']:
            allowed = self.client.get(f'/billing/jobs/{self.jobs["authorized", kind].pk}/')
            self.assertEqual(allowed.status_code, 200)
            self.assertContains(allowed, self.author.email)
            self.assertNotContains(allowed, 'SYNTHETIC_SECRET_NOTES')
            self.assertEqual(allowed.context['balances'], [])
            self.assertTrue(all(row['before'] is None and row['after'] is None for row in allowed.context['movements']))
            target = f'/billing/jobs/{self.jobs["foreign", kind].pk}/'
            for method in ['get', 'head', 'post']:
                for host in ['testserver', 'localhost', 'app.quillmd.com', 'admin.quillmd.com']:
                    with self.subTest(kind=kind, method=method, host=host):
                        self.assertEqual(getattr(self.client, method)(target, HTTP_HOST=host).status_code, 404)
            self.assertFalse(AuditEvent.objects.filter(action='billing.job_read', target=str(self.jobs['foreign', kind].pk)).exists())
        self.assertEqual(self.money(), before)

    def test_financial_scope_does_not_open_other_departments_clinical_api_or_result_export(self):
        foreign = self.jobs['foreign', 'generation']
        for target in [f'/api/encounters/{foreign.encounter_id}/', f'/encounters/{foreign.encounter_id}/',
                       f'/encounters/{foreign.encounter_id}/export/', f'/jobs/{foreign.pk}/result/']:
            self.assertEqual(self.client.get(target).status_code, 404)
        self.assertEqual(self.client.get(f'/api/encounters/{self.jobs["authorized", "generation"].encounter_id}/').status_code, 200)

    def test_personal_financial_history_survives_department_membership_revocation(self):
        Membership.objects.filter(user=self.foreign_author).update(active=False)
        page = self.foreign_client.get('/billing/')
        self.assertEqual(len(page.context['held_requests']), 3)
        self.assertEqual(len(page.context['usage']), 3)
        for kind in ['generation', 'transcription', 'mapping']:
            self.assertEqual(self.foreign_client.get(f'/billing/jobs/{self.jobs["foreign", kind].pk}/').status_code, 200)
        self.assertEqual(self.foreign_client.get(f'/api/encounters/{self.jobs["foreign", "generation"].encounter_id}/').status_code, 404)

    def test_owner_role_revocation_removes_other_users_financial_access(self):
        for role, active in [('clinician', True), ('manager', True), ('employee', True), ('owner', False)]:
            Membership.objects.filter(user=self.owner).update(role=role, active=active)
            page = self.client.get('/billing/')
            self.assertEqual(page.context['held_requests'], [])
            self.assertEqual(len(page.context['usage']), 0)
            self.assertEqual(len(page.context['ledger']), 0)
            self.assertEqual(self.client.get(f'/billing/jobs/{self.jobs["authorized", "generation"].pk}/').status_code, 404)

    def test_a_second_explicit_department_owner_membership_is_an_authorized_positive(self):
        Membership.objects.create(user=self.owner, department=self.b, role='owner')
        page = self.client.get('/billing/')
        self.assertEqual(len(page.context['held_requests']), 6)
        self.assertEqual(page.context['usage_totals']['cost'], Decimal('.12'))
        for job in self.jobs.values():
            self.assertEqual(self.client.get(f'/billing/jobs/{job.pk}/').status_code, 200)

    @override_settings(ADMIN_SITE=True)
    def test_alternate_admin_surface_denies_the_department_owner(self):
        for target in ['/billing/', '/console/', '/console/usage.csv',
                       f'/billing/jobs/{self.jobs["foreign", "generation"].pk}/',
                       f'/console/jobs/{self.jobs["foreign", "generation"].pk}/']:
            self.assertEqual(self.client.get(target, HTTP_HOST='admin.quillmd.com').status_code, 404)
