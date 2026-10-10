"""Prospective personal clinician enrollment, with no provider or production access."""
from decimal import Decimal
from types import SimpleNamespace
import importlib
import json
import uuid
from unittest.mock import patch
from unittest.mock import Mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import billing, jobs, testing_authority as authority
from core.models import (Department, Encounter, Job, LedgerEntry, Membership, Organization, Patient,
    PreparationReceipt, ProviderReceipt, Reservation, Template, TemplatePreparation, TemplateVersion,
    TestingReservation, User, Wallet)
from core.tests import test_preparation_campaign_pg as campaign_tests
from core.tests import test_testing_authority as authority_tests

SETTINGS = authority_tests.SETTINGS


@override_settings(**SETTINGS)
class PersonalSyntheticTestingTests(SimpleTestCase):
    def config(self, kind="preparation"):
        return authority.active_config({"mode":"live", "provider":"anthropic", "model":SETTINGS["AI_MODEL"]}, kind)

    def actor(self):
        return SimpleNamespace(pk=authority.ENROLLED_ACTOR, is_active=True, verified_at='synthetic-verified')

    def department(self):
        return authority.ACTORS[authority.ENROLLED_ACTOR]

    def test_marker_only_partial_null_and_spoofed_metadata_never_fall_back(self):
        key = authority.ACTOR_ENROLLMENT_KEY
        for value in (authority.ACTOR_ENROLLMENT, None, '', 'other', 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                authority.identity({key: value})
        for value in (None, 'other', 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                authority.identity({**self.config(), key: value})

    def test_new_personal_requests_bind_marker_without_mutating_input(self):
        actor = self.actor()
        with patch('core.security.membership'):
            for kind in ('generation', 'transcription'):
                original = self.config(kind)
                result = authority.job_config(original, kind, actor, self.department(), '1.25')
                self.assertEqual(result[authority.ACTOR_ENROLLMENT_KEY], authority.ACTOR_ENROLLMENT)
                self.assertNotIn(authority.ACTOR_ENROLLMENT_KEY, original)
                self.assertEqual(result['testing_purpose'], authority.PURPOSES[kind])
            original = self.config()
            template = SimpleNamespace(department_id=self.department(), format='docx')
            with patch('core.models.TemplatePreparation.objects.create') as create:
                authority.create_preparation(template, actor, original)
            self.assertEqual(create.call_args.kwargs['config'][authority.ACTOR_ENROLLMENT_KEY], authority.ACTOR_ENROLLMENT)
            self.assertNotIn(authority.ACTOR_ENROLLMENT_KEY, original)

    def test_old_actors_retain_their_original_configs_and_refuse_personal_marker(self):
        old = SimpleNamespace(pk=next(iter(authority.ACTORS)), is_active=True)
        dep = authority.ACTORS[str(old.pk)]
        with patch('core.security.membership'):
            self.assertEqual(authority.bind_actor_config(self.config(), old, dep), self.config())
            for value in (None, authority.ACTOR_ENROLLMENT):
                with self.subTest(value=value), self.assertRaises(ValidationError):
                    authority.bind_actor_config({**self.config(), authority.ACTOR_ENROLLMENT_KEY: value}, old, dep)

    def test_retained_personal_config_without_marker_is_not_relabelled_at_reserve_or_send(self):
        actor = self.actor()
        encounter = SimpleNamespace(department_id=self.department(), created_by_id=actor.pk)
        prep = SimpleNamespace(config=self.config(), requested_by=actor,
                               template=SimpleNamespace(department_id=self.department()))
        with patch('core.security.membership'):
            with self.assertRaises(ValidationError):
                authority.reserve_role(prep, 'proposer', 'a' * 64, '0.1')
            for call in (authority.reserve_job, authority.admit_job_send):
                job = SimpleNamespace(config=self.config('generation'), kind='generation', user=actor, encounter=encounter)
                with self.subTest(call=call.__name__), self.assertRaises(ValidationError):
                    call(job, '0.1') if call is authority.reserve_job else call(job)
                self.assertNotIn(authority.ACTOR_ENROLLMENT_KEY, job.config)

    def test_personal_actor_requires_exact_scope_active_verification_and_role(self):
        actor = self.actor()
        for candidate, dep in ((actor, 'other-department'),
                (SimpleNamespace(pk=actor.pk, is_active=False, verified_at='verified'), self.department()),
                (SimpleNamespace(pk='unlisted', is_active=True), self.department())):
            with self.subTest(candidate=candidate.pk, dep=dep), self.assertRaises(ValidationError):
                authority.admit_actor(candidate, dep)
        with patch('core.security.membership', side_effect=PermissionDenied), self.assertRaises(PermissionDenied):
            authority.bind_actor_config(self.config(), actor, self.department())

    def test_personal_encounters_must_be_created_by_the_actual_actor(self):
        actor = self.actor()
        authority.admit_encounter(actor, SimpleNamespace(created_by_id=actor.pk))
        with self.assertRaisesRegex(ValidationError, 'Create your own synthetic document'):
            authority.admit_encounter(actor, SimpleNamespace(created_by_id='2247e403-a830-4807-9a34-6903b95a0f50'))
        # The new condition does not alter existing actor behavior.
        authority.admit_encounter(SimpleNamespace(pk=next(iter(authority.ACTORS))), SimpleNamespace(created_by_id='other'))

    def test_migration_preserves_finite_preparation_branches_and_actor_helper(self):
        migration = importlib.import_module('core.migrations.0025_personal_synthetic_testing_actor')
        for name, token in (('quillmd_preparation_pilot_guard', ' IF quillmd_delivery_config(NEW.config) THEN'),
                            ('quillmd_preparation_send_guard', ' IF quillmd_delivery_config(configuration) THEN')):
            self.assertEqual(migration.ORIGINALS[name].split(token, 1)[1],
                             migration.REPLACEMENTS[name].split(token, 1)[1])
        self.assertNotIn('CREATE OR REPLACE FUNCTION quillmd_delivery_actor', migration.SQL)
        self.assertEqual(set(migration.REPLACEMENTS), {'quillmd_standing_config', 'quillmd_standing_job_guard',
            'quillmd_testing_reservation_guard', 'quillmd_preparation_pilot_guard', 'quillmd_preparation_send_guard'})


@override_settings(**SETTINGS)
class PersonalSyntheticTestingPostgresTests(TransactionTestCase):
    raw_insert = campaign_tests.DeliveryCampaignPostgresTests.raw_insert
    refusal = campaign_tests.DeliveryCampaignPostgresTests.refusal

    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires actual PostgreSQL enrollment guards.')
        self.organization = Organization.objects.create(name='Synthetic personal actor fixture')
        self.department = Department.objects.create(id=authority.ACTORS[authority.ENROLLED_ACTOR],
            organization=self.organization, name='Synthetic X-ray fixture')
        self.owner = User.objects.create(id='2247e403-a830-4807-9a34-6903b95a0f50',
            username='synthetic-existing-owner', email='owner@synthetic.invalid', verified_at=timezone.now())
        self.actor = User.objects.create(id=authority.ENROLLED_ACTOR,
            username='synthetic-personal-clinician', email='personal@synthetic.invalid', verified_at=timezone.now())
        self.owner.refresh_from_db(); self.actor.refresh_from_db()
        Membership.objects.create(user=self.owner, department=self.department, role='owner')
        self.member = Membership.objects.create(user=self.actor, department=self.department, role='clinician')
        self.patient = Patient.objects.create(department=self.department, created_by=self.owner,
            display_name='Synthetic fixture only', reference='SYNTH-PERSONAL')

    def config(self, kind='preparation', enrolled=True, **extra):
        result = authority.active_config({'mode':'live', 'provider':'anthropic', 'model':SETTINGS['AI_MODEL']}, kind)
        if enrolled:
            result[authority.ACTOR_ENROLLMENT_KEY] = authority.ACTOR_ENROLLMENT
        return {**result, **extra}

    def template(self, creator=None):
        return Template.objects.create(department=self.department, created_by=creator or self.actor,
            name='SYNTHETIC personal blank fixture', format='docx', original_name='synthetic.docx',
            original_path='synthetic-fixture-not-read.docx', sha256='a' * 64)

    def encounter(self, creator=None, approved_shared=False):
        template = self.template(self.owner)
        preparation = None
        if approved_shared:
            preparation = authority.create_preparation(template, self.owner, self.config(enrolled=False))
            # Complete fictional approval metadata satisfies the retained DB
            # guards; this fixture makes no provider or fidelity claim.
            TemplatePreparation.objects.filter(pk=preparation.pk).update(state='approved',
                approved_at=timezone.now(), approved_by=self.owner, approval_sha256='c' * 64,
                candidate_path='synthetic-prepared-not-read.docx', candidate_sha256='b' * 64)
        version = TemplateVersion.objects.create(template=template, created_by=self.owner, number=1,
            preparation=preparation, prepared_path='synthetic-prepared-not-read.docx' if preparation else '',
            prepared_sha256='b' * 64 if preparation else '')
        return Encounter.objects.create(patient=self.patient, department=self.department,
            created_by=creator or self.actor, template_version=version,
            notes='History: Synthetic fixture only.', service_date=timezone.localdate())

    def job(self, kind='generation', config=None, encounter=None, user=None):
        return self.raw_insert(Job, encounter=encounter or self.encounter(), user=user or self.actor,
            kind=kind, request_key=str(uuid.uuid4()), config=config or self.config(kind, testing_quote_usd='0.100000000000'))

    def sql_actor(self, actor=None, department=None, config=None, finite=False):
        with connection.cursor() as cursor:
            if finite:
                cursor.execute('SELECT quillmd_delivery_actor(%s::uuid,%s::uuid)',
                    [str((actor or self.actor).pk), str((department or self.department).pk)])
            else:
                cursor.execute('SELECT quillmd_standing_actor(%s::uuid,%s::uuid,%s::jsonb)',
                    [str((actor or self.actor).pk), str((department or self.department).pk), json.dumps(config or self.config())])
            cursor.fetchone()

    def receipt(self, preparation):
        return self.raw_insert(PreparationReceipt, preparation=preparation, role='proposer',
            provider='anthropic', requested_model=SETTINGS['AI_MODEL'], request_sha256='e' * 64,
            quote_maximum=Decimal('0.10'), state='running', started_at=timezone.now())

    def assert_no_wallet_or_provider_records(self):
        for model in (Wallet, Reservation, LedgerEntry, ProviderReceipt):
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.exists())

    def test_actual_actor_preparation_and_both_job_purposes_admit_without_wallet_funds(self):
        prep = authority.create_preparation(self.template(), self.actor, self.config(enrolled=False))
        self.assertEqual(prep.config[authority.ACTOR_ENROLLMENT_KEY], authority.ACTOR_ENROLLMENT)
        receipt = authority.reserve_role(prep, 'proposer', 'c' * 64, Decimal('0.10'))
        self.assertEqual(receipt.state, 'running')
        PreparationReceipt.objects.filter(pk=receipt.pk).update(state='succeeded', computed_cost=0, finished_at=timezone.now())
        self.assertEqual(authority.reserve_role(prep, 'checker', 'd' * 64, Decimal('0.10')).role, 'checker')
        for kind in ('generation', 'transcription'):
            with self.subTest(kind=kind):
                job = self.job(kind)
                billing.reserve(job, Decimal('0.10'))
                job.refresh_from_db()
                authority.admit_job_send(job)
                self.assertEqual(TestingReservation.objects.get(job=job).state, 'held')
                self.sql_actor(config=job.config)
        self.assert_no_wallet_or_provider_records()

    def test_ordinary_enqueue_binds_both_purposes_on_own_new_document_using_shared_approved_form(self):
        encounter = self.encounter(approved_shared=True)
        config = self.config('generation', enrolled=False)
        with patch('core.template_source.source_for_version') as source, \
                patch('core.generation.maximum_cost', return_value=Decimal('0.10')):
            job = jobs.enqueue(encounter, self.actor, config=config)
        source.assert_called_once()
        self.assertEqual(job.config[authority.ACTOR_ENROLLMENT_KEY], authority.ACTOR_ENROLLMENT)
        self.assertEqual(job.encounter.created_by_id, self.actor.pk)
        self.assertEqual(job.encounter.template_version.created_by_id, self.owner.pk)
        audio = Mock(); audio.read_bytes.return_value = b'synthetic-only-fixture'
        bounds = SimpleNamespace(measured=Decimal('1'), confirmed=Decimal('1'), ambiguity='')
        config = self.config('transcription', enrolled=False, voice_rate_minute='0.1', voice_rate_second='0')
        with patch('core.jobs.private_path', return_value=audio), \
                patch('core.jobs.recording_charge_limit', return_value=(bounds, Decimal('0.15'), {})), \
                patch('core.jobs.describe_submission', return_value={'submission_streams':'1','submitted_seconds':'1'}):
            voice = jobs.enqueue(self.encounter(), self.actor, kind='transcription', input_path='synthetic.wav', config=config)
        self.assertEqual(voice.config[authority.ACTOR_ENROLLMENT_KEY], authority.ACTOR_ENROLLMENT)
        self.assertEqual(TestingReservation.objects.get(job=voice).quoted_provider_cost, Decimal('0.10'))
        self.assert_no_wallet_or_provider_records()

    def test_owner_created_encounter_refuses_before_job_hold_or_provider_and_sql_bypass(self):
        encounter = self.encounter(self.owner)
        with patch('core.generation.generate') as provider, self.assertRaisesRegex(ValidationError, 'Create your own'):
            jobs.enqueue(encounter, self.actor, config=self.config('generation', enrolled=False))
        provider.assert_not_called()
        self.refusal(lambda:self.job(encounter=encounter))
        self.assertFalse(Job.objects.exists())
        self.assertFalse(TestingReservation.objects.exists())

    @override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
        'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
    def test_shared_record_does_not_advertise_personal_sponsorship_and_http_enqueue_refuses(self):
        from django.test import Client
        encounter = self.encounter(self.owner)
        client = Client(); client.force_login(self.actor)
        response = client.get(f'/encounters/{encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['standing_testing'])
        with patch('core.views.usage_quote', return_value=self.config('generation', enrolled=False)), \
                patch('core.generation.generate') as provider:
            response = client.post(f'/encounters/{encounter.pk}/generate/', {'revision':encounter.revision}, follow=True)
        self.assertContains(response, 'Create your own synthetic document')
        provider.assert_not_called()
        self.assertFalse(Job.objects.exists())
        self.assertFalse(TestingReservation.objects.exists())
        own = self.encounter()
        self.assertTrue(client.get(f'/encounters/{own.pk}/').context['standing_testing'])

    def test_marker_only_spoofed_missing_and_mixed_configs_are_sql_refusals(self):
        key = authority.ACTOR_ENROLLMENT_KEY
        for config in ({key:authority.ACTOR_ENROLLMENT}, {key:None},
                self.config(enrolled=False), self.config(**{key:None}), self.config(**{key:'other'}),
                self.config(campaign='old-finite-approval')):
            self.refusal(lambda:self.raw_insert(TemplatePreparation, template=self.template(), requested_by=self.actor, config=config))
        for kind in ('generation','transcription'):
            self.refusal(lambda:self.job(kind, config=self.config(kind, enrolled=False, testing_quote_usd='0.1')))
        self.assertFalse(TemplatePreparation.objects.exists())
        self.assertFalse(Job.objects.exists())

    def test_marker_is_immutable_for_preparations_and_jobs_and_reverse_refuses_retained_requests(self):
        prep = authority.create_preparation(self.template(), self.actor, self.config(enrolled=False))
        job = self.job()
        for value in (None, 'other'):
            self.refusal(lambda:TemplatePreparation.objects.filter(pk=prep.pk).update(config={**prep.config, authority.ACTOR_ENROLLMENT_KEY:value}))
            self.refusal(lambda:Job.objects.filter(pk=job.pk).update(config={**job.config, authority.ACTOR_ENROLLMENT_KEY:value}))
        self.refusal(lambda:TemplatePreparation.objects.filter(pk=prep.pk).update(config=self.config(enrolled=False)))
        self.refusal(lambda:Job.objects.filter(pk=job.pk).update(config=self.config('generation', enrolled=False, testing_quote_usd='0.1')))
        migration = importlib.import_module('core.migrations.0025_personal_synthetic_testing_actor')
        def reverse():
            with connection.cursor() as cursor:cursor.execute(migration.REVERSE)
        self.refusal(reverse)

    def test_wrong_tenant_unlisted_inactive_unverified_and_employee_actor_refuse(self):
        other = Department.objects.create(organization=self.organization, name='Other synthetic scope')
        Membership.objects.create(user=self.actor, department=other, role='clinician')
        stranger = User.objects.create(username='unlisted-personal', email='unlisted@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=stranger, department=self.department, role='clinician')
        self.refusal(lambda:self.sql_actor(department=other))
        self.refusal(lambda:self.sql_actor(actor=stranger))
        for changes in ({'active':False}, {'role':'employee'}):
            Membership.objects.filter(pk=self.member.pk).update(**changes)
            self.refusal(self.sql_actor)
            with self.assertRaises(PermissionDenied):authority.bind_actor_config(self.config(), self.actor, self.department.pk)
            Membership.objects.filter(pk=self.member.pk).update(active=True, role='clinician')
        User.objects.filter(pk=self.actor.pk).update(verified_at=None)
        self.refusal(self.sql_actor)
        with self.assertRaises(PermissionDenied):authority.bind_actor_config(self.config(), self.actor, self.department.pk)

    def test_raw_preparation_job_and_receipt_recheck_actor_access_at_admission(self):
        prep = authority.create_preparation(self.template(), self.actor, self.config(enrolled=False))
        for changes in ({'active':False}, {'role':'employee'}):
            Membership.objects.filter(pk=self.member.pk).update(**changes)
            self.refusal(lambda:self.raw_insert(TemplatePreparation, template=self.template(), requested_by=self.actor, config=self.config()))
            self.refusal(self.job)
            self.refusal(lambda:self.receipt(prep))
            Membership.objects.filter(pk=self.member.pk).update(active=True, role='clinician')
        User.objects.filter(pk=self.actor.pk).update(verified_at=None)
        self.refusal(lambda:self.raw_insert(TemplatePreparation, template=self.template(), requested_by=self.actor, config=self.config()))
        self.refusal(self.job)
        self.refusal(lambda:self.receipt(prep))
        self.assertFalse(PreparationReceipt.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assert_no_wallet_or_provider_records()

    def test_stale_actor_verification_revoked_after_reservation_refuses_before_provider(self):
        job = self.job(); billing.reserve(job, Decimal('0.10'))
        User.objects.filter(pk=self.actor.pk).update(verified_at=None)
        with patch('core.generation.generate') as provider:
            self.assertTrue(jobs.run_one())
        provider.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(TestingReservation.objects.get(job=job).state, 'released')

    def test_existing_actors_remain_unmarked_and_new_actor_never_enters_finite_campaign(self):
        self.sql_actor(actor=self.owner, config=self.config(enrolled=False))
        self.refusal(lambda:self.sql_actor(actor=self.owner))
        self.refusal(lambda:self.sql_actor(finite=True))
        self.refusal(lambda:self.sql_actor(actor=self.owner, config=self.config(**{authority.ACTOR_ENROLLMENT_KEY:None})))

    def test_runtime_admission_pins_new_helper_and_complete_revised_bodies(self):
        result = authority.runtime_admission(self.actor, self.department.pk)
        self.assertEqual(result['actor_enrollment'], authority.ACTOR_ENROLLMENT)
        self.assertEqual(result['database_function_definitions_verified'], 10)
        self.assertEqual(result['provider_calls'], 0)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('CREATE OR REPLACE FUNCTION quillmd_standing_actor(actor uuid,department uuid,config jsonb) RETURNS void LANGUAGE plpgsql AS $$ BEGIN RETURN; END; $$;')
            with self.assertRaises(ValidationError):authority.runtime_admission(self.actor, self.department.pk)
            transaction.set_rollback(True)
