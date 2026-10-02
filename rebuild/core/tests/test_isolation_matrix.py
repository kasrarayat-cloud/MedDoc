"""Tenant isolation, enumerated from the URL resolver (inventory 7A, ISOLATION).

Every route the application mounts is CLASSIFIED below — public, the signed-in account's own pages, a creation that
names a department, a route that addresses one department's object by id, or the administration console — and a route
nobody classified fails `test_every_route_is_classified`, so a new route cannot arrive without an isolation decision.

For every route that addresses a department's object, two intruders are tried, by GET and by POST: a clinician of a
SIBLING department of the same clinic, and a clinician of ANOTHER clinic. Each gets the route's documented refusal
(404 wherever the code scopes its lookup; 403 where it looks the object up and then refuses the membership; 405 for a
method the route does not take), and the whole core database is compared before and after: nothing changes. A positive
control signs the department's own owner in and requires every one of those routes to resolve its object, so a 404
above is the tenancy rule and not a broken fixture.
"""
import hashlib
import json
import re
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import (Code, CodeSet, CodeSuggestion, Department, Invitation, Job, Membership, Organization,
                         Patient, ProviderReceipt, Template, TemplateVersion, User)
from core.security import digest, private_path
from core.tests.test_security import SyntheticFixture

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}

#: Reachable without a session, or only for the caller's own credentials / tokens; no department object by id.
PUBLIC = {'preview_sign_in', 'preview_sign_out', 'recovery_request', 'recovery_confirm', 'recovery_complete',
          'verification_resend', 'health', 'login', 'register', 'verify', 'invite_accept', 'clinic_invite_accept',
          'webhook'}
#: The signed-in account's own pages: lists scoped to its memberships, its own wallet and session.
OWN = {'logout', 'mfa_setup', 'dashboard', 'billing', 'checkout', 'api_patients'}
#: Creations that name the department (or its patient/template) they write into.
CREATE = {'patients', 'template_upload', 'encounter_new', 'team', 'create_department'}
#: route name -> (object the id addresses, {method: documented refusal for an intruder})
P404 = {'GET': 405, 'POST': 404}         # @require_POST and a scoped lookup
G404 = {'GET': 404, 'POST': 404}         # any method, scoped lookup
OBJECT = {
    'template_detail': ('template', G404), 'template_original': ('template', G404),
    'mapping_assistance': ('mapping', G404),
    'encounter_detail': ('encounter', G404), 'generate': ('encounter', P404), 'save_answers': ('encounter', P404),
    'finalize': ('encounter', P404), 'export': ('final', G404), 'voice': ('encounter', P404),
    'voice_approve': ('encounter', P404), 'coding': ('encounter', P404), 'accept_code': ('code', P404),
    'api_encounter': ('encounter', G404), 'encounter_notes': ('encounter', P404),
    'clear_review': ('encounter', P404), 'job_cancel': ('queued_job', P404), 'job_result': ('result_job', G404),
    'billing_job_detail': ('result_job', G404), 'invitation_revoke': ('invitation', P404),
    # Looked up unscoped, then membership(..., roles=['owner']) raises PermissionDenied: 403, documented.
    'membership_update': ('membership', {'GET': 405, 'POST': 403}),
}

#: Each classified route by its URL PATTERN as the resolver holds it, and its name (refutation R9: keyed by the name
#: alone, a new unscoped pattern reusing a classified name passed the gate). A new pattern is a new (route, name)
#: pair, so it fails test_every_route_is_classified until it is given an isolation decision here.
ROUTES = {
    'preview_sign_in': 'preview/sign-in/',
    'preview_sign_out': 'preview/sign-out/',
    'mapping_assistance': 'templates/<uuid:pk>/assistance/',
    'recovery_request': 'recovery/',
    'recovery_confirm': 'recovery/confirm/<uidb64>/<token>/',
    'recovery_complete': 'recovery/complete/',
    'verification_resend': 'verification/resend/',
    'health': 'health/',
    'login': 'login/',
    'logout': 'logout/',
    'register': 'register/',
    'mfa_setup': 'mfa/',
    'verify': 'verify/<str:raw>/',
    'invite_accept': 'invite/<str:raw>/',
    'webhook': 'billing/webhook/',
    'dashboard': '',
    'template_upload': 'templates/upload/',
    'template_detail': 'templates/<uuid:pk>/',
    'template_original': 'templates/<uuid:pk>/original/',
    'encounter_new': 'encounters/new/',
    'encounter_detail': 'encounters/<uuid:pk>/',
    'generate': 'encounters/<uuid:pk>/generate/',
    'save_answers': 'encounters/<uuid:pk>/save/',
    'finalize': 'encounters/<uuid:pk>/finalize/',
    'export': 'encounters/<uuid:pk>/export/',
    'voice': 'encounters/<uuid:pk>/voice/',
    'voice_approve': 'encounters/<uuid:pk>/voice/approve/',
    'coding': 'encounters/<uuid:pk>/coding/',
    'accept_code': 'encounters/<uuid:pk>/coding/<uuid:code_pk>/accept/',
    'patients': 'patients/',
    'team': 'team/',
    'create_department': 'team/departments/',
    'membership_update': 'team/membership/<uuid:pk>/',
    'billing': 'billing/',
    'checkout': 'billing/checkout/',
    'api_patients': 'api/patients/',
    'api_encounter': 'api/encounters/<uuid:pk>/',
    'encounter_notes': 'encounters/<uuid:pk>/notes/',
    'clear_review': 'encounters/<uuid:pk>/clear-review/',
    'job_cancel': 'encounters/<uuid:pk>/jobs/<uuid:job_pk>/cancel/',
    'job_result': 'jobs/<uuid:pk>/result/',
    'invitation_revoke': 'team/invitations/<uuid:pk>/revoke/',
    'billing_job_detail': 'billing/jobs/<uuid:pk>/',
    'clinic_invite_accept': 'invite/clinic/<str:raw>/',
}


def all_patterns(resolver=None, prefix=''):
    resolver = resolver or get_resolver()
    for entry in resolver.url_patterns:
        if isinstance(entry, URLResolver):
            yield from all_patterns(entry, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def classification_problems():
    """Every way the mounted routes and the classification disagree, by route PATTERN and name; [] when they agree."""
    problems = []
    mounted = [(route, pattern.name) for route, pattern in all_patterns() if not route.startswith('console/')]
    if len(mounted) <= 30 or not any(route.startswith('console/') for route, _ in all_patterns()):
        problems.append(('the resolver walk found almost nothing', len(mounted)))
    problems += [('mounted twice', pair) for pair in sorted(set(mounted)) if mounted.count(pair) > 1]
    expected = {(route, name) for name, route in ROUTES.items()}
    problems += [('no isolation decision', pair) for pair in sorted(set(mounted) - expected)]
    problems += [('classified but not mounted', pair) for pair in sorted(expected - set(mounted))]
    groups = (PUBLIC, OWN, CREATE, set(OBJECT))
    problems += [('classified twice', name) for name in sorted(ROUTES)
                 if sum(name in group for group in groups) != 1]
    problems += [('in a class but not in ROUTES', name) for name in sorted(set().union(*groups) - set(ROUTES))]
    return problems

def database_state():
    """Every row of every core model, hashed per model: any write anywhere in the application's tables shows."""
    state = {}
    for model in apps.get_app_config('core').get_models():
        rows = list(model.objects.order_by('pk').values())
        state[model.__name__] = (len(rows), hashlib.sha256(json.dumps(rows, default=str, sort_keys=True)
                                                           .encode()).hexdigest())
    return state


def changed(before, after):
    return sorted(name for name in before if before[name] != after[name])


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False,
                   QUILLMD_MAPPING_ASSISTANCE=True, STORAGES=STORAGES)
class IsolationMatrix(SyntheticFixture, TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        media = override_settings(MEDIA_ROOT=Path(directory.name))
        media.enable()
        self.addCleanup(media.disable)
        self.alpha = self.make_scope('alpha')
        self.beta = self.make_scope('beta', self.alpha[1])      # sibling department, same clinic
        self.gamma = self.make_scope('gamma')                   # another clinic
        owner, org, department, patient, template, encounter, blob = self.alpha
        Membership.objects.filter(user=owner, department=department).update(role='owner')
        # Names nothing else on any page carries, so a list that leaks them is caught by its text.
        Template.objects.filter(pk=template.pk).update(name='ALPHA-ONLY-TEMPLATE')
        template.refresh_from_db()
        Patient.objects.filter(pk=patient.pk).update(display_name='SYNTHETIC ALPHA-ONLY-PATIENT')
        patient.refresh_from_db()
        mapping = Template.objects.create(department=department, name='ALPHA-ONLY-MAPPING', format='docx',
                                          original_name='mapping.docx', original_path=template.original_path,
                                          sha256=template.sha256, created_by=owner)
        TemplateVersion.objects.create(template=mapping, number=1, fields=encounter.template_version.fields,
                                       contract='v3', created_by=owner)
        path = private_path(template.original_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        final = type(encounter).objects.create(department=department, patient=patient,
                                               template_version=encounter.template_version, created_by=owner,
                                               service_date=encounter.service_date, notes=encounter.notes,
                                               status='finalized', export_path='exports/alpha.docx',
                                               export_sha256=hashlib.sha256(blob).hexdigest())
        export = private_path(final.export_path)
        export.parent.mkdir(parents=True, exist_ok=True)
        export.write_bytes(blob)
        queued = Job.objects.create(encounter=encounter, user=owner, kind='transcription', request_key='iso:queued')
        result = Job.objects.create(encounter=encounter, user=owner, request_key='iso:result', state='succeeded',
                                    payer=f'user:{owner.pk}', result_path='results/iso.json')
        output = private_path(result.result_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'{"synthetic": true}')
        result.result_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
        result.save(update_fields=['result_sha256'])
        ProviderReceipt.objects.create(job=result, provider='fixture', actual_cost=Decimal('0'), simulated=True)
        today = timezone.localdate()
        release = CodeSet.objects.create(system='ICD-10-CM', version='synthetic-isolation',
                                         effective_from=today - timedelta(days=1),
                                         effective_until=today + timedelta(days=1),
                                         source_url='https://synthetic.invalid/codes', sha256='0' * 64)
        suggestion = CodeSuggestion.objects.create(
            encounter=encounter, terminology=Code.objects.create(release=release, code='R00.0',
                                                                 description='Synthetic code'),
            explanation='Synthetic explanation', evidence='no chest pain')
        colleague = User.objects.create_user(username='alpha-colleague', email='alpha-colleague@synthetic.invalid',
                                             verified_at=timezone.now())
        member = Membership.objects.create(user=colleague, department=department, role='employee')
        invitation = Invitation.objects.create(email='invitee@synthetic.invalid', department=department,
                                               role='clinician', token_hash=digest('iso-invitation'),
                                               expires_at=timezone.now() + timedelta(days=7), invited_by=owner)
        self.objects = {'template': template, 'mapping': mapping, 'encounter': encounter, 'final': final,
                        'queued_job': queued, 'result_job': result, 'code': suggestion, 'membership': member,
                        'invitation': invitation}
        # A clinician of a sibling department, a clinician of another clinic, and that clinic's OWNER — the strongest
        # outsider for creations, which an owner may make in their own organization. (A sibling department's owner
        # is an owner of THIS organization by construction — owner memberships are never invited — so is no intruder.)
        other_owner = User.objects.create_user(username='gamma-owner', email='gamma-owner@synthetic.invalid',
                                               verified_at=timezone.now())
        Membership.objects.create(user=other_owner, department=self.gamma[2], role='owner')
        self.intruders = {'sibling department': self.beta[0], 'other clinic': self.gamma[0],
                          'other clinic owner': other_owner}

    def url(self, name):
        thing = self.objects[OBJECT[name][0]]
        if name == 'accept_code':
            return reverse(name, kwargs={'pk': thing.encounter_id, 'code_pk': thing.pk})
        if name == 'job_cancel':
            return reverse(name, kwargs={'pk': thing.encounter_id, 'job_pk': thing.pk})
        return reverse(name, kwargs={'pk': thing.pk})

    def client_for(self, user):
        client = Client(raise_request_exception=False)
        client.force_login(user)
        return client

    def test_every_route_is_classified(self):
        self.assertEqual(classification_problems(), [])
        for group in (PUBLIC & OWN, PUBLIC & CREATE, OWN & CREATE, set(OBJECT) & (PUBLIC | OWN | CREATE)):
            self.assertEqual(group, set(), 'a route classified twice')

    def test_intruders_get_the_documented_refusal_and_nothing_changes(self):
        for who, intruder in self.intruders.items():
            client = self.client_for(intruder)
            for name, (_, refusals) in OBJECT.items():
                for method, status in refusals.items():
                    with self.subTest(intruder=who, route=name, method=method):
                        before = database_state()
                        response = getattr(client, method.lower())(self.url(name), {'revision': 0, 'reviewed': 'on',
                                                                                   'role': 'manager', 'active': 'on'})
                        self.assertEqual(response.status_code, status)
                        self.assertEqual(changed(before, database_state()), [])

    def test_the_console_answers_404_to_intruders(self):
        for who, intruder in self.intruders.items():
            client = self.client_for(intruder)
            for route, _ in all_patterns():
                if not route.startswith('console/'):
                    continue
                path = '/' + re.sub(r'<(?:(\w+):)?\w+>', lambda m: str(self.alpha[5].pk), route)
                with self.subTest(intruder=who, route=route):
                    before = database_state()
                    self.assertEqual(client.post(path).status_code, 404)
                    self.assertEqual(client.get(path).status_code, 404)
                    self.assertEqual(changed(before, database_state()), [])

    def test_no_intruder_creates_anything_in_another_department(self):
        owner, org, department, patient, template, encounter, blob = self.alpha
        version = encounter.template_version
        posts = {
            'patients': {'department': department.pk, 'display_name': 'SYNTHETIC intruder', 'reference': 'intrusion',
                         'synthetic_only': 'on'},
            'encounter_new': {'patient': patient.pk, 'template_version': version.pk, 'notes': 'Synthetic',
                              'service_date': timezone.localdate().isoformat(), 'synthetic_only': 'on'},
            'team': {'department': department.pk, 'email': 'intruder-invite@synthetic.invalid', 'role': 'clinician'},
            'create_department': {'name': 'Intruder department', 'organization': org.pk},
        }
        for who, intruder in self.intruders.items():
            client = self.client_for(intruder)
            for name, data in list(posts.items()) + [('template_upload', None)]:
                with self.subTest(intruder=who, route=name):
                    if name == 'template_upload':
                        data = {'department': department.pk, 'name': 'Intruder template',
                                'file': SimpleUploadedFile('intruder.docx', blob)}
                    before = database_state()
                    response = client.post(reverse(name), data)
                    self.assertIn(response.status_code, (200, 302, 403))
                    self.assertEqual(changed(before, database_state()), [], f'{name} wrote for an intruder')
                    self.assertFalse(Department.objects.filter(organization=org, name='Intruder department').exists())

    def test_own_lists_show_nothing_of_another_department(self):
        owner, org, department, patient, template, encounter, blob = self.alpha
        for who, intruder in self.intruders.items():
            client = self.client_for(intruder)
            for path in ('/', '/patients/', '/team/', '/billing/', '/api/patients/', '/api/patients/?q=alpha'):
                with self.subTest(intruder=who, path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    body = response.content.decode()
                    for secret in ('ALPHA-ONLY', str(patient.pk), str(encounter.pk), str(self.objects['final'].pk),
                                   str(self.objects['result_job'].pk), 'alpha-colleague@', 'invitee@'):
                        self.assertNotIn(secret, body)

    def test_positive_control_the_owner_resolves_every_department_object(self):
        """Every OBJECT route finds its object for the department's own owner: no 404, no 403."""
        owner = self.alpha[0]
        client = self.client_for(owner)
        for name, (_, refusals) in OBJECT.items():
            method = 'post' if refusals['GET'] == 405 else 'get'
            with self.subTest(route=name):
                response = getattr(client, method)(self.url(name), {'revision': 0, 'role': 'manager', 'active': 'on'})
                self.assertNotIn(response.status_code, (403, 404, 405), f'{name} did not resolve for its owner')


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class DepartmentCreationNamesItsOrganization(SyntheticFixture, TestCase):
    """create_department took `.first()` of the caller's owner memberships: an owner of two clinics (a personal workspace
    and a clinic accepted by invitation, say) got the new department in whichever organization the database returned
    first — with its owner membership and, for an organization-paid department, the other clinic's wallet as payer."""

    def setUp(self):
        self.owner, self.first_org, first_department, *_ = self.make_scope('first')
        Membership.objects.filter(user=self.owner).update(role='owner')
        self.second_org = Organization.objects.create(name='Second clinic')
        Membership.objects.create(user=self.owner, department=Department.objects.create(
            organization=self.second_org, name='Second front desk'), role='owner')
        self.client.force_login(self.owner)

    def test_the_department_lands_in_the_organization_the_owner_chose(self):
        for org in (self.first_org, self.second_org):
            with self.subTest(organization=org.name):
                name = f'Ultrasound for {org.name}'
                self.client.post('/team/departments/', {'name': name, 'organization': org.pk})
                created = Department.objects.get(name=name)
                self.assertEqual(created.organization, org)
                self.assertTrue(Membership.objects.filter(user=self.owner, department=created, role='owner').exists())

    def test_an_owner_of_two_organizations_must_choose_and_nothing_is_created_otherwise(self):
        before = database_state()
        self.client.post('/team/departments/', {'name': 'Unplaced'})
        self.assertFalse(Department.objects.filter(name='Unplaced').exists())
        self.assertEqual(changed(before, database_state()), [])

    def test_an_organization_the_caller_does_not_own_is_refused(self):
        stranger = Organization.objects.create(name='Stranger clinic')
        Department.objects.create(organization=stranger, name='Stranger front desk')
        before = database_state()
        self.client.post('/team/departments/', {'name': 'Planted', 'organization': stranger.pk})
        self.assertFalse(Department.objects.filter(name='Planted').exists())
        self.assertEqual(changed(before, database_state()), [])

    def test_the_form_offers_and_admits_only_organizations_the_caller_owns(self):
        """The first of two independent guards: the form's own choices."""
        from core.forms import DepartmentForm
        stranger = Organization.objects.create(name='Stranger clinic')
        self.assertEqual(set(DepartmentForm(user=self.owner).fields['organization'].queryset),
                         {self.first_org, self.second_org})
        form = DepartmentForm({'name': 'Planted', 'organization': stranger.pk}, user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('organization', form.errors)

    def test_the_view_rechecks_ownership_of_the_chosen_organization(self):
        """The second guard, alone: a form that admitted any organization still creates nothing in one the caller
        does not own (the view re-reads the owner membership of the chosen organization in its transaction)."""
        from unittest.mock import patch
        from core import forms, views

        class Permissive(forms.DepartmentForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['organization'].queryset = Organization.objects.all()
        stranger = Organization.objects.create(name='Stranger clinic')
        before = database_state()
        with patch.object(views, 'DepartmentForm', Permissive):
            response = self.client.post('/team/departments/', {'name': 'Planted', 'organization': stranger.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Department.objects.filter(name='Planted').exists())
        self.assertEqual(changed(before, database_state()), [])

    def test_a_single_organization_owner_needs_no_choice(self):
        Membership.objects.filter(user=self.owner, department__organization=self.second_org).update(role='clinician')
        self.client.post('/team/departments/', {'name': 'Only clinic department'})
        self.assertEqual(Department.objects.get(name='Only clinic department').organization, self.first_org)

    def test_a_clinician_who_owns_nothing_is_refused(self):
        Membership.objects.filter(user=self.owner).update(role='clinician')
        before = database_state()
        self.assertEqual(self.client.post('/team/departments/', {'name': 'Nope', 'organization': self.first_org.pk})
                         .status_code, 403)
        self.assertEqual(changed(before, database_state()), [])


@override_settings(QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class DepartmentInvitationIsADoctorSurfacePage(SyntheticFixture, TestCase):
    """invite_accept had no administration-surface 404, unlike the clinic-owner invitation (LOW): on the admin host a
    signed-in administrator whose address matched could accept a department invitation into a clinic."""

    def setUp(self):
        self.owner, org, self.department, *_ = self.make_scope('inviting')
        Membership.objects.filter(user=self.owner).update(role='owner')
        self.raw = 'synthetic-department-invitation-token'
        self.admin = User.objects.create_user(username='surface-admin', email='surface-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        TOTPDevice.objects.create(user=self.admin, confirmed=True)
        Invitation.objects.create(email=self.admin.email, department=self.department, role='clinician',
                                  token_hash=digest(self.raw), expires_at=timezone.now() + timedelta(days=7),
                                  invited_by=self.owner)

    @override_settings(ADMIN_SITE=True)
    def test_the_admin_surface_answers_404_and_creates_no_membership(self):
        client = Client()
        client.force_login(self.admin)
        before = database_state()
        self.assertEqual(client.get(f'/invite/{self.raw}/').status_code, 404)
        self.assertEqual(client.post(f'/invite/{self.raw}/', {}).status_code, 404)
        self.assertEqual(changed(before, database_state()), [])
        self.assertFalse(Membership.objects.filter(user=self.admin).exists())

    @override_settings(ADMIN_SITE=False)
    def test_positive_control_the_doctor_surface_still_shows_the_invitation(self):
        self.assertEqual(Client().get(f'/invite/{self.raw}/').status_code, 200)


class ClassificationIsByPattern(SimpleTestCase):
    def test_a_new_pattern_under_a_classified_name_is_unclassified(self):
        """Refutation R9, the refuter's probe as a regression: an unscoped object route mounted under the classified
        name 'api_patients' passed a gate keyed by name. It is a new (pattern, name) pair now, and is reported."""
        from django.http import JsonResponse
        from django.urls import path
        self.assertEqual(classification_problems(), [], 'positive control: the routes as mounted are classified')
        resolver = get_resolver()
        resolver.url_patterns.append(path('api/encounters/<uuid:pk>/raw/', lambda request, pk: JsonResponse({}),
                                          name='api_patients'))
        try:
            problems = classification_problems()
        finally:
            resolver.url_patterns.pop()
        self.assertIn(('no isolation decision', ('api/encounters/<uuid:pk>/raw/', 'api_patients')), problems)
        self.assertEqual(classification_problems(), [])
