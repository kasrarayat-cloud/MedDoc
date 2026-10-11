"""Actual PostgreSQL cohort guards against direct SQL and concurrent admission.

All document/provider rows here are deliberately fictional guard fixtures. No
provider runs, prepared-document fidelity or genuine doctor approval is claimed.
The suite runs in a disposable test database, never the retained private demo.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import threading
import uuid
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from psycopg.types.json import Jsonb
from psycopg import sql

from core import preparation_campaign as campaign
from core.models import (Department, Encounter, Job, Membership, Organization, Patient,
                         PreparationReceipt, ProviderReceipt, Template, TemplatePreparation,
                         TemplateVersion, User)

WM = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
SHORT = 'b2b78348f8735bddb75433d7b0cd720d1a0f416c1fbae7ac51b896fbf0fa5193'
UNDERSCORE = 'a2a70a3b087077e55401030fd9a592958d0064402a3b12d107b132f563111102'


@override_settings(WORD_PREPARATION_CAMPAIGN=campaign.CAMPAIGN,
                   WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256=campaign.SCOPE_SHA256, SYNTHETIC_ONLY=True)
class DeliveryCampaignPostgresTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('These independent guard controls require PostgreSQL.')
        self.organization = Organization.objects.create(name='Synthetic PostgreSQL guard fixture')
        self.doctor = User.objects.create(id='71dc60e3-ca1e-40c7-ad49-4a2612ed8d1a',
            username='synthetic-campaign-guard', email='guard-doctor@example.invalid',
            is_active=True, verified_at=timezone.now())
        self.department = Department.objects.create(id='d41ad441-987c-4e68-bb0e-b885ec4b642a',
            organization=self.organization, name='Synthetic guard fixtures')
        Membership.objects.create(user=self.doctor, department=self.department, role='owner')
        self.patient = Patient.objects.create(department=self.department, created_by=self.doctor,
            display_name='Synthetic guard fixture', reference='synthetic-guard')

    def config(self, **extra):
        return {'mode': 'live', 'provider': 'anthropic', 'model': 'synthetic-guard-configured-label',
                'campaign': campaign.CAMPAIGN, 'campaign_scope_sha256': campaign.SCOPE_SHA256,
                'campaign_actor_scope_sha256': campaign.ACTOR_SCOPE_SHA256, **extra}

    def template(self, source=SHORT, department=None):
        return Template.objects.create(department=department or self.department, created_by=self.doctor,
            name='Synthetic SQL-only guard original', format='docx', original_name='guard.docx',
            original_path='guard-fixture-does-not-exist.docx', sha256=source)

    def raw_insert(self, model, **values):
        """Bypass application save/helpers; let actual database triggers judge."""
        value = model(**values)
        columns = []
        params = []
        for field in model._meta.concrete_fields:
            columns.append(connection.ops.quote_name(field.column))
            item = getattr(value, field.attname)
            if field.name == 'created_at' and item is None:
                item = timezone.now()
            if field.get_internal_type() == 'JSONField':
                item = Jsonb(item)
            params.append(item)
        table = connection.ops.quote_name(model._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join(["%s"] * len(params))})', params)
        return model.objects.get(pk=value.pk)

    def preparation(self, source=SHORT, config=None, actor=None, department=None):
        return self.raw_insert(TemplatePreparation, template=self.template(source, department),
            requested_by=actor or self.doctor, config=self.config() if config is None else config)

    def wm_inventory(self, prep):
        inventory = {'source_sha256': WM, 'anchors': [{'kind': 'existing'} for _ in range(90)],
            'fields': [{} for _ in range(90)], 'stories': [{} for _ in range(16)],
            'document_backend': {'backend': 'wm-iov-foss-v2', 'source_sha256': WM}}
        TemplatePreparation.objects.filter(pk=prep.pk).update(inventory=inventory)
        prep.refresh_from_db()

    def receipt(self, prep, role='proposer', **extra):
        quote = Decimal('0.16') if prep.template.sha256 == WM else Decimal('0.10')
        return self.raw_insert(PreparationReceipt, preparation=prep, role=role,
            provider='anthropic', requested_model='synthetic-guard-configured-label', request_sha256='a' * 64,
            quote_maximum=extra.pop('quote_maximum', quote), **extra)

    def encounter(self, version_model=TemplateVersion):
        template = self.template()
        version = version_model.objects.create(template_id=template.pk, number=1, created_by_id=self.doctor.pk)
        return Encounter.objects.create(patient=self.patient, department=self.department,
            created_by=self.doctor, template_version_id=version.pk, notes='Synthetic guard fixture only',
            service_date=timezone.now().date())

    def job(self, kind='generation', **extra):
        version_model=extra.pop('version_model',TemplateVersion)
        return self.raw_insert(Job, encounter=self.encounter(version_model), user=extra.pop('user', self.doctor),
            kind=kind, request_key=str(uuid.uuid4()), config=extra.pop('config', self.config(campaign_quote_usd='0.20')), **extra)

    def refusal(self, call, message=None):
        with self.assertRaises(DatabaseError) as error:
            with transaction.atomic():call()
        if message:
            self.assertIn(message, str(error.exception))

    def test_raw_sql_cannot_misclassify_partial_unknown_scope_or_actor_as_legacy(self):
        invalid = [{'campaign': None}, {'campaign_scope_sha256': campaign.SCOPE_SHA256},
                   {'campaign_actor_scope_sha256': campaign.ACTOR_SCOPE_SHA256},
                   self.config(campaign='invented'), self.config(campaign_scope_sha256='0' * 64),
                   self.config(campaign_actor_scope_sha256='0' * 64)]
        for config in invalid:
            with self.subTest(config=config):self.refusal(lambda: self.preparation(config=config), 'authority')
        outsider = User.objects.create(username='outsider', email='outsider@example.invalid',
            verified_at=timezone.now(), is_active=True)
        Membership.objects.create(user=outsider, department=self.department, role='owner')
        self.refusal(lambda: self.preparation(actor=outsider), 'exact active synthetic doctor')
        other_department = Department.objects.create(name='Wrong department', organization=self.organization)
        Membership.objects.create(user=self.doctor, department=other_department, role='owner')
        self.refusal(lambda: self.preparation(department=other_department), 'exact active synthetic doctor')
        self.assertEqual(TemplatePreparation.objects.count(), 0)

    def test_raw_sql_legacy_configuration_must_still_be_an_object(self):
        for config in [[], 'opaque', 1, None]:
            # None is used literally through raw_insert, not helper defaulting.
            template = self.template()
            with self.subTest(config=config):
                self.refusal(lambda: self.raw_insert(TemplatePreparation,
                    template=template, requested_by=self.doctor, config=config))

    def test_one_attempt_per_exact_original_and_three_total_enforced_by_sql(self):
        self.preparation(SHORT)
        self.refusal(lambda: self.preparation(SHORT), 'one attempt per original')
        self.preparation(UNDERSCORE)
        self.preparation(WM)
        self.refusal(lambda: self.preparation('0' * 64), 'exact three delivery forms')
        self.refusal(lambda: self.preparation(WM), 'one attempt per original')
        self.assertEqual(TemplatePreparation.objects.count(), 3)

    def test_role_order_one_send_caps_and_exact_wm_shape_are_enforced_by_sql(self):
        prep = self.preparation(SHORT)
        self.refusal(lambda: self.receipt(prep, 'checker'), 'successful proposal')
        for quote in [Decimal('-0.01'), Decimal('0'), Decimal('0.11')]:
            with self.subTest(quote=quote):self.refusal(lambda: self.receipt(prep, quote_maximum=quote), 'exact cap')
        proposer = self.receipt(prep, state='succeeded', finished_at=timezone.now())
        self.refusal(lambda: self.receipt(prep), 'preparation_role_once')
        self.receipt(prep, 'checker')
        wm = self.preparation(WM)
        self.refusal(lambda: self.receipt(wm), 'exact WM90 purpose')
        self.wm_inventory(wm)
        self.receipt(wm)
        self.assertEqual(proposer.quote_maximum, Decimal('0.10'))

    def test_six_preparation_role_receipts_cannot_expand_with_relabeling(self):
        for source in [SHORT, UNDERSCORE, WM]:
            prep = self.preparation(source)
            if source == WM:self.wm_inventory(prep)
            self.receipt(prep, state='succeeded', finished_at=timezone.now())
            self.receipt(prep, 'checker')
        self.assertEqual(PreparationReceipt.objects.count(), 6)
        prep = TemplatePreparation.objects.first()
        self.refusal(lambda: self.receipt(prep, role='extra'), 'exact cap')
        self.refusal(lambda: self.receipt(prep), 'six delivery preparation sends')

    def test_global_legacy_eight_fourteen_wm_gates_remain_and_unknown_is_retained(self):
        legacy = {'mode': 'live', 'provider': 'anthropic', 'model': 'older-label'}
        sources = [SHORT, UNDERSCORE, WM, '1' * 64, '2' * 64, '3' * 64]
        rows = [self.preparation(source, legacy) for source in sources]
        rows.append(self.preparation(SHORT, legacy))
        self.refusal(lambda: self.preparation(SHORT, legacy), 'eighth legacy attempt')
        rows.append(self.preparation(WM, legacy))
        self.refusal(lambda: self.preparation(WM, legacy), 'eight recorded')
        original_config = [p.config for p in rows]
        unknown = None
        for prep in rows[:6]:
            if prep.template.sha256 == WM:self.wm_inventory(prep)
            for role in ['proposer', 'checker']:
                receipt = self.receipt(prep, role, quote_maximum=Decimal('0.10'),
                    state='unknown' if unknown is None else 'succeeded', finished_at=timezone.now())
                if unknown is None:unknown = receipt
        self.refusal(lambda: self.receipt(rows[6]), 'exact qualified WM follow-up')
        self.wm_inventory(rows[7]);self.receipt(rows[7]);self.receipt(rows[7], 'checker')
        self.refusal(lambda: self.receipt(rows[6]), 'fourteen recorded')
        new = self.preparation(SHORT)
        self.receipt(new)
        unknown.refresh_from_db()
        self.assertEqual(unknown.quote_maximum, Decimal('0.10'))
        self.assertIsNone(unknown.computed_cost)
        self.assertEqual(unknown.state, 'unknown')
        self.assertEqual([TemplatePreparation.objects.get(pk=p.pk).config for p in rows], original_config)
        self.refusal(lambda: PreparationReceipt.objects.filter(pk=unknown.pk).update(computed_cost=Decimal('0')), 'immutable')
        self.assertEqual(campaign.legacy_preparations(TemplatePreparation.objects.all()).count(), 8)
        self.assertEqual(campaign.legacy_receipts(PreparationReceipt.objects.all()).count(), 14)

    def test_job_kind_count_quote_scope_and_actor_limits_are_enforced_by_sql(self):
        for config in [self.config(), self.config(campaign_quote_usd='0.21'),
                       self.config(campaign_quote_usd='NaN'), self.config(campaign_quote_usd=0.2)]:
            with self.subTest(config=config):self.refusal(lambda: self.job(config=config), 'exact recorded exposure')
        self.refusal(lambda: self.job(kind='other'), 'not authorized')
        for _ in range(3):self.job()
        self.refusal(lambda: self.job(), 'request count')
        self.job('transcription')
        self.refusal(lambda: self.job('transcription'), 'request count')
        outsider = User.objects.create(username='job-outsider', email='job-outsider@example.invalid', verified_at=timezone.now())
        self.refusal(lambda: self.job(user=outsider), 'exact active synthetic doctor')

    def test_actual_over_quote_and_unknown_reservations_are_retained_then_block_new_sends(self):
        prep = self.preparation(SHORT)
        unknown = self.receipt(prep, state='unknown', finished_at=timezone.now())
        job = self.job()
        actual = self.raw_insert(ProviderReceipt, job=job, provider='anthropic', actual_cost=Decimal('1.70'))
        self.assertEqual(campaign.exposure(), Decimal('1.80'))
        self.refusal(lambda: self.job(), 'exposure exceeds')
        self.assertEqual(ProviderReceipt.objects.get(pk=actual.pk).actual_cost, Decimal('1.70'))
        self.assertEqual(PreparationReceipt.objects.get(pk=unknown.pk).quote_maximum, Decimal('0.10'))

    def test_preparation_returned_over_quote_cost_is_retained_not_normalized(self):
        prep = self.preparation(SHORT)
        receipt = self.receipt(prep)
        PreparationReceipt.objects.filter(pk=receipt.pk).update(computed_cost=Decimal('1.80'))
        receipt.refresh_from_db()
        self.assertEqual(receipt.computed_cost, Decimal('1.80'))
        self.refusal(lambda: self.job(), 'exposure exceeds')

    def test_already_queued_request_cannot_send_after_an_actual_exposure_overrun(self):
        first = self.job()
        queued = self.job()
        self.raw_insert(ProviderReceipt, job=first, provider='anthropic', actual_cost=Decimal('1.70'))
        self.assertEqual(campaign.exposure(), Decimal('1.90'))
        with self.assertRaises(ValidationError):
            with campaign.provider_slot(queued.config):
                self.fail('A queued provider request entered after the actual campaign exposure exceeded $1.75.')

    def test_unknown_failed_and_finished_receipts_do_not_buy_a_second_send(self):
        prep = self.preparation(SHORT)
        unknown = self.receipt(prep, state='unknown', finished_at=timezone.now())
        self.refusal(lambda: self.receipt(prep), 'preparation_role_once')
        self.refusal(lambda: self.receipt(prep, 'checker'), 'successful proposal')
        self.refusal(lambda: PreparationReceipt.objects.filter(pk=unknown.pk).update(state='succeeded'), 'immutable')

    def test_approval_configuration_and_source_are_still_immutable(self):
        prep = self.preparation(SHORT, config={'mode': 'fixture', 'model': 'older-label'})
        self.refusal(lambda: TemplatePreparation.objects.filter(pk=prep.pk).update(config=self.config()), 'immutable')
        self.refusal(lambda: Template.objects.filter(pk=prep.template_id).update(sha256=WM), 'immutable')
        # A fictional shape seal checks SQL immutability only, not a real approval.
        TemplatePreparation.objects.filter(pk=prep.pk).update(state='approved', approved_at=timezone.now(),
            approved_by=self.doctor, approval_sha256='b' * 64, candidate_path='synthetic-sql-candidate.docx', candidate_sha256='c' * 64)
        seal = TemplatePreparation.objects.get(pk=prep.pk).approval_sha256
        self.refusal(lambda: TemplatePreparation.objects.filter(pk=prep.pk).update(approval_sha256='d' * 64), 'immutable')
        self.assertEqual(TemplatePreparation.objects.get(pk=prep.pk).approval_sha256, seal)

    def test_actual_parallel_sql_cannot_create_two_attempts_for_one_original(self):
        first = self.template(SHORT);second = self.template(SHORT)
        barrier = threading.Barrier(2)
        config = self.config()
        doctor = self.doctor
        def insert(template):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        self.raw_insert(TemplatePreparation, template=template, requested_by=doctor, config=config)
                    return 'inserted'
                except DatabaseError:return 'refused'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(insert, [first, second]))
        self.assertEqual(sorted(results), ['inserted', 'refused'])
        self.assertEqual(TemplatePreparation.objects.count(), 1)

    def test_actual_provider_lock_contention_refuses_second_send_and_releases(self):
        self.preparation(SHORT)
        with campaign.provider_slot(self.config()):
            def contend():
                close_old_connections()
                try:
                    try:
                        with campaign.provider_slot(self.config()):return 'entered'
                    except ValidationError:return 'refused'
                finally:connections['default'].close()
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(contend).result(timeout=10), 'refused')
        with campaign.provider_slot(self.config()):pass

    def test_worker_records_proved_local_provider_refusal_as_unsent(self):
        from core import jobs
        job = self.job()
        def run_worker():
            close_old_connections()
            try:return jobs.run_one()
            finally:connections['default'].close()
        with campaign.provider_slot(self.config()), patch('core.generation.generate') as provider:
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertTrue(pool.submit(run_worker).result(timeout=10))
            provider.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertIn('No provider request was made', job.error)

    def test_worker_keeps_actual_provider_slot_until_returned_cost_is_committed(self):
        from core import jobs
        first = self.job()
        queued = self.job()
        accounting_started = threading.Event()
        accounting_allowed = threading.Event()
        original_insert = ProviderReceipt.objects.get_or_create
        def insert_returned_cost(*args, **kwargs):
            accounting_started.set()
            if not accounting_allowed.wait(timeout=10):
                raise AssertionError('The accounting qualification stalled.')
            return original_insert(*args, **kwargs)
        def run_worker():
            close_old_connections()
            try:return jobs.run_one()
            finally:connections['default'].close()
        # Only the provider result is fictional. Receipt insertion, triggers,
        # transaction commit, exposure and cross-connection locks are real.
        returned = ({}, Decimal('1.70'), {}, {}, 'anthropic', 'synthetic-lock-proof', False)
        with patch('core.generation.generate', return_value=returned) as provider, \
             patch.object(ProviderReceipt.objects, 'get_or_create', side_effect=insert_returned_cost), \
             patch('core.jobs.private_path', side_effect=OSError('Synthetic post-receipt IO refusal')):
            with ThreadPoolExecutor(max_workers=1) as pool:
                worker = pool.submit(run_worker)
                try:
                    self.assertTrue(accounting_started.wait(timeout=10))
                    with self.assertRaises(campaign.CampaignProviderRefusal):
                        with campaign.provider_slot(queued.config):
                            self.fail('Another provider entered before returned cost was committed.')
                finally:accounting_allowed.set()
                self.assertTrue(worker.result(timeout=10))
            provider.assert_called_once()
        self.assertEqual(ProviderReceipt.objects.get(job=first).actual_cost, Decimal('1.70'))
        self.assertEqual(campaign.exposure(), Decimal('1.90'))
        with self.assertRaises(campaign.CampaignProviderRefusal):
            with campaign.provider_slot(queued.config):
                self.fail('A queued request entered after the actual overrun was committed.')

    def test_actual_native_schema_default_policy_supports_restricted_runtime_trigger_calls(self):
        # Replay the ACTUAL schema-scoped policy, not an invented global default
        # revocation. PostgreSQL global PUBLIC EXECUTE and schema ACLs differ.
        # This entire reversible role/schema probe is rolled back in this DB.
        role = 'quillmd_guard_runtime_' + uuid.uuid4().hex[:12]
        with transaction.atomic():
            executor = MigrationExecutor(connection)
            executor.migrate([('core', '0022_wm_output_followup')])
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_user')
                owner = cursor.fetchone()[0]
                cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(role)))
                cursor.execute('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC')
                cursor.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC').format(sql.Identifier(owner)))
            MigrationExecutor(connection).migrate([('core', '0023_delivery_campaign')])
            # This probe intentionally runs the actual 0023 schema. Use its
            # historical model so later additive columns are not sent to it.
            historical_version=executor.loader.project_state([('core','0023_delivery_campaign')]).apps.get_model('core','TemplateVersion')
            self.assertNotIn('semantic_definitions',{field.name for field in historical_version._meta.fields})
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
                cursor.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
                cursor.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
                cursor.execute("SELECT has_function_privilege(%s,'quillmd_delivery_config(jsonb)','EXECUTE'),has_function_privilege(%s,'quillmd_delivery_actor(uuid,uuid)','EXECUTE'),has_function_privilege(%s,'quillmd_delivery_exposure()','EXECUTE')", [role] * 3)
                self.assertEqual(cursor.fetchone(), (True, True, True))
                cursor.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
                cursor.execute('SELECT current_user,rolsuper,rolcreaterole FROM pg_roles WHERE rolname=current_user')
                self.assertEqual(cursor.fetchone(), (role, False, False))
                prep = self.preparation(SHORT)
                self.receipt(prep)
                self.job(version_model=historical_version)
                self.refusal(lambda: self.preparation(SHORT), 'one attempt per original')
                cursor.execute('RESET ROLE')
            self.assertEqual(TemplatePreparation.objects.count(), 1)
            self.assertEqual(PreparationReceipt.objects.count(), 1)
            self.assertEqual(Job.objects.count(), 1)
            transaction.set_rollback(True)
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s', [role])
            self.assertEqual(cursor.fetchone()[0], 0)
