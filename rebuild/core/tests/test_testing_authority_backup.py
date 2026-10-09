"""PostgreSQL backup checks qualify sponsorship without trusting write guards."""
from contextlib import contextmanager
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import uuid

from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import billing, testing_authority as authority
from core.models import (Department, Encounter, Job, Membership, Organization, Patient,
    PlatformCost, ProviderReceipt, Template, TemplateVersion, Usage, User)
from core.tests.test_testing_authority import SETTINGS


spec = importlib.util.spec_from_file_location('standing_backup_restore',
    Path(__file__).resolve().parents[2] / 'ops' / 'backup_restore.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class LegacyBackupQueryTests(SimpleTestCase):
    def test_pre_0024_dispatch_uses_exact_legacy_statements_and_manifest_keys(self):
        seen = []
        def query(statement):
            seen.append(statement)
            return [(None,)] if statement.startswith('SELECT to_regclass(') else [(0,)]
        self.assertEqual(backup.invariant_counts(query), dict.fromkeys(backup.INVARIANTS, 0))
        self.assertEqual(seen[1:], list(backup.INVARIANTS.values()))


@override_settings(**SETTINGS)
class StandingBackupPostgresTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires actual PostgreSQL invariant queries.')
        self.organization = Organization.objects.create(name='Synthetic backup qualification')
        self.doctor = User.objects.create(id=next(iter(authority.ACTORS)), username='backup-synthetic',
            email='backup@example.invalid', verified_at=timezone.now())
        self.department = Department.objects.create(id=authority.ACTORS[str(self.doctor.pk)],
            organization=self.organization, name='Synthetic backup scope')
        Membership.objects.create(user=self.doctor, department=self.department, role='owner')
        patient = Patient.objects.create(department=self.department, created_by=self.doctor,
            display_name='Synthetic only', reference='backup-synthetic')
        template = Template.objects.create(department=self.department, created_by=self.doctor,
            name='Synthetic blank', format='docx', original_name='blank.docx',
            original_path='synthetic-not-read.docx', sha256='a'*64)
        version = TemplateVersion.objects.create(template=template, number=1, created_by=self.doctor)
        self.encounter = Encounter.objects.create(patient=patient, department=self.department,
            created_by=self.doctor, template_version=version, service_date=timezone.now().date())

    def query(self, statement):
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall()

    def sponsored(self, kind='generation', simulated=False):
        config = authority.active_config({'mode':'fixture' if simulated else 'live',
            'provider':'anthropic', 'model':SETTINGS['AI_MODEL']}, kind)
        quote = Decimal('0') if simulated else Decimal('0.01')
        config['testing_quote_usd'] = str(quote)
        job = Job.objects.create(encounter=self.encounter, user=self.doctor, kind=kind,
            request_key=str(uuid.uuid4()), config=config)
        billing.reserve(job, quote)
        job.refresh_from_db()
        actual = Decimal('0') if simulated else Decimal('0.10')
        provider = 'deepgram:returned-asr-model' if kind == 'transcription' else 'anthropic:returned-model'
        units = {'seconds':'10.060'} if kind == 'transcription' else {'input_tokens':100, 'output_tokens':20}
        rates = {'per_minute':'0.0043'} if kind == 'transcription' else {'input_per_million':'3', 'output_per_million':'15'}
        request_id, resource_id = 'req-'+str(job.pk), 'resource-'+str(job.pk)
        ProviderReceipt.objects.create(job=job, provider=provider, provider_request_id=request_id,
            provider_resource_id=resource_id, units=units, rates=rates, actual_cost=actual, simulated=simulated)
        usage = billing.settle(job, actual, units, rates, provider, request_id, simulated, resource_id)
        return job, usage

    def assert_clean(self):
        self.assertEqual(backup.invariant_counts(self.query), dict.fromkeys(backup.INVARIANTS, 0))

    @contextmanager
    def shadow(self, *tables):
        # Independent corrupt-restored-data fixtures: temporary table copies
        # have no application triggers or constraints. Real public guards stay
        # enabled, and rollback discards every temporary mutation.
        with transaction.atomic():
            with connection.cursor() as cursor:
                for table in tables:
                    self.assertIn(table, {'core_job','core_usage','core_encounter','core_providerreceipt',
                        'core_testingreservation','core_reservation','core_ledgerentry','core_platformcost',
                        'core_costreconciliation'})
                    cursor.execute(f'CREATE TEMP TABLE {table} AS TABLE public.{table}')
            try:
                yield
            finally:
                transaction.set_rollback(True)

    def corrupt(self, table, statement, params=()):
        with self.shadow(table):
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
            self.assertEqual(self.query(backup._STANDING_USAGE_INVARIANT)[0][0], 1)
            with self.assertRaisesMessage(RuntimeError, 'Database invariants failed'):
                backup.invariant_counts(self.query)
        self.assert_clean()

    def test_valid_generation_asr_and_fixture_survive_current_authority_revocation(self):
        for kind, simulated in [('generation',False),('transcription',False),('generation',True)]:
            self.sponsored(kind, simulated)
        # Actual provider cost is ten times the recorded estimate; it is not a
        # funding ceiling. ASR's returned provider differs from AI config.
        with override_settings(TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='',
                TESTING_AUTHORITY_SHA256='', AI_PROVIDER='unrelated-current-setting'):
            self.doctor.is_active=False
            self.doctor.save(update_fields=['is_active'])
            Membership.objects.all().delete()
            self.assert_clean()

    def test_actual_pre_0024_schema_and_plain_and_capped_legacy_rules(self):
        from django.db.migrations.executor import MigrationExecutor
        for actual, charged in [('0.10','0.15'),('0.10','0.12')]:
            job = Job.objects.create(encounter=self.encounter, user=self.doctor,
                request_key=str(uuid.uuid4()), config={})
            Usage.objects.create(job=job, user=self.doctor, department=self.department,
                organization=self.organization, payer='user:'+str(self.doctor.pk), provider='legacy:recorded',
                actual_cost=Decimal(actual), charged_cost=Decimal(charged))
            if charged == '0.12':
                from core.models import Reservation, Wallet
                wallet=Wallet.objects.create(user=self.doctor,kind='paid',balance=0,reserved=0)
                Reservation.objects.create(job=job,wallet=wallet,amount=Decimal('0.12'),state='settled')
                PlatformCost.objects.create(job=job,kind='absorbed_over_limit',amount=Decimal('0.03'))
        self.assert_clean()
        with transaction.atomic():
            MigrationExecutor(connection).migrate([('core','0023_delivery_campaign')])
            self.assert_clean()
            transaction.set_rollback(True)
        self.assert_clean()
        with self.shadow('core_usage'):
            with connection.cursor() as cursor:
                cursor.execute('UPDATE core_usage SET charged_cost=0.01')
            self.assertEqual(self.query(backup.INVARIANTS['usage_multiplier'])[0][0],2)
            self.assertEqual(self.query(backup._STANDING_USAGE_INVARIANT)[0][0],2)

    def test_malformed_partial_mixed_or_wrong_purpose_cannot_claim_exemption(self):
        job, _ = self.sponsored()
        for config in [[], {'testing_authority_id':authority.AUTHORITY_ID},
                {**job.config,'testing_authority_sha256':'0'*64},
                {**job.config,'testing_purpose':authority.PURPOSES['transcription']},
                {**job.config,'campaign':'consumed-finite-approval'},
                {**job.config,'model':123}, {**job.config,'mode':'fixture'}]:
            with self.subTest(config=config):
                self.corrupt('core_job','UPDATE core_job SET config=%s::jsonb',(json.dumps(config),))
        for quote in [None, 1, '-1', 'NaN', '1e200', '1.0000000000001', '1234567890123', '0.02']:
            with self.subTest(quote=quote):
                config={**job.config,'testing_quote_usd':quote}
                self.corrupt('core_job','UPDATE core_job SET config=%s::jsonb',(json.dumps(config),))

    def test_receipt_and_reservation_are_required_and_every_metered_field_matches(self):
        self.sponsored()
        self.corrupt('core_testingreservation','DELETE FROM core_testingreservation')
        for field, value in [('state','held'),('state','released'),('authority_id','other'),
                ('quoted_provider_cost',Decimal('0.02'))]:
            with self.subTest(field=field,value=value):
                self.corrupt('core_testingreservation',f'UPDATE core_testingreservation SET {field}=%s',(value,))
        self.corrupt('core_providerreceipt','DELETE FROM core_providerreceipt')
        for field, value in [('provider','deepgram:wrong'),('provider_request_id','wrong'),
                ('provider_resource_id','wrong'),('actual_cost',Decimal('0.11')),('simulated',True)]:
            with self.subTest(field=field):
                self.corrupt('core_providerreceipt',f'UPDATE core_providerreceipt SET {field}=%s',(value,))
        for field in ['units','rates']:
            self.corrupt('core_providerreceipt',f'UPDATE core_providerreceipt SET {field}=\'{{"changed":1}}\'::jsonb')

    def test_wrong_identity_nonzero_charge_and_wallet_or_absorption_rows_are_refused(self):
        job, _ = self.sponsored()
        for field in ['user_id','department_id','organization_id']:
            self.corrupt('core_usage',f'UPDATE core_usage SET {field}=%s',(uuid.uuid4(),))
        self.corrupt('core_encounter','UPDATE core_encounter SET created_by_id=%s',(uuid.uuid4(),))
        self.corrupt('core_job','UPDATE core_job SET user_id=%s',(uuid.uuid4(),))
        self.corrupt('core_job',"UPDATE core_job SET payer='user:other'")
        self.corrupt('core_usage',"UPDATE core_usage SET payer='standing:other'")
        self.corrupt('core_usage','UPDATE core_usage SET charged_cost=0.15')
        for table, columns, values in [
                ('core_reservation','wallet_id,amount,state',"%s,0,'held'"),
                ('core_ledgerentry','wallet_id,amount,kind,key,description,balance_after',"%s,0,'usage','synthetic-forbidden','',0"),
                ('core_platformcost','kind,amount,description,evidence_reference',"'absorbed_over_limit',0,'',''")]:
            params=[uuid.uuid4(),job.pk]
            if 'wallet_id' in columns:
                params.append(uuid.uuid4())
            self.corrupt(table,f'INSERT INTO {table} (id,created_at,job_id,{columns}) VALUES (%s,now(),%s,{values})',params)

    def fail_and_absorb(self, job):
        Job.objects.filter(pk=job.pk).update(state='failed',error='platform_failure: synthetic unusable result')
        return billing.absorb_failed_job(job, actor=self.doctor, note='synthetic qualification')

    def test_exact_failure_absorption_and_prior_or_later_labelled_reconciliation(self):
        job, usage=self.sponsored()
        absorbed=self.fail_and_absorb(job)
        self.assertEqual(absorbed.amount,usage.actual_cost)
        self.assert_clean()
        # A later invoice does not rewrite the immutable original absorption.
        later=billing.reconcile_usage(usage,Decimal('0.17'),'synthetic-later-invoice',self.doctor,evidence_kind='invoice')
        self.assertEqual(later.ledger_status,'absorbed')
        self.assert_clean()
        for kind in ['invoice','provider_report']:
            job,usage=self.sponsored('transcription')
            reconciled=billing.reconcile_usage(usage,Decimal('0.15'),'synthetic-before-'+kind,self.doctor,evidence_kind=kind)
            absorbed=self.fail_and_absorb(job)
            self.assertEqual(absorbed.amount,reconciled.reconciled_cost)
            self.assert_clean()
        # The existing default is explicitly unclassified. Preserve that
        # recorded amount and uncertainty without claiming confirmed charges.
        job,usage=self.sponsored()
        unclassified=billing.reconcile_usage(usage,Decimal('0.14'),'synthetic-unclassified',self.doctor)
        self.assertEqual(unclassified.evidence_kind,'unclassified')
        self.assertFalse(unclassified.provider_evidence_reconciled)
        self.assertFalse(unclassified.invoice_reconciled)
        absorbed=self.fail_and_absorb(job)
        self.assertEqual(absorbed.amount,unclassified.reconciled_cost)
        self.assert_clean()

    def test_failure_exemption_rejects_wrong_state_evidence_amount_kind_and_duplicates(self):
        job,usage=self.sponsored('transcription')
        self.fail_and_absorb(job)
        self.assert_clean()
        self.corrupt('core_job',"UPDATE core_job SET state='succeeded'")
        self.corrupt('core_job',"UPDATE core_job SET error='not_adopted: successful output declined'")
        self.corrupt('core_job',"UPDATE core_job SET error='unknown historical error'")
        self.corrupt('core_platformcost','UPDATE core_platformcost SET amount=0.11')
        self.corrupt('core_platformcost',"UPDATE core_platformcost SET kind='absorbed_over_limit'")
        self.corrupt('core_platformcost',"UPDATE core_platformcost SET kind='fixed_overhead'")
        self.corrupt('core_platformcost',"UPDATE core_platformcost SET evidence_reference='usage:wrong'")
        self.corrupt('core_platformcost','UPDATE core_platformcost SET evidence_reference=%s',('usage:'+str(usage.pk)+'WRONG',))
        self.corrupt('core_platformcost',"UPDATE core_platformcost SET created_at=created_at-interval '1 day'")
        self.corrupt('core_platformcost','INSERT INTO core_platformcost SELECT %s,created_at,kind,amount,description,period_start,period_end,evidence_reference,job_id,recorded_by_id FROM core_platformcost',(uuid.uuid4(),))

    def test_reconciliation_exemption_rejects_unknown_or_inconsistent_evidence(self):
        job,usage=self.sponsored()
        billing.reconcile_usage(usage,Decimal('0.15'),'synthetic-invoice',self.doctor,evidence_kind='invoice')
        self.fail_and_absorb(job)
        self.assert_clean()
        for field,value in [('evidence_kind','invented'),('evidence_reference',''),
                ('charge_delta',Decimal('0.01')),('over_limit_delta',Decimal('0.01')),
                ('ledger_status','pending_funds'),('reconciled_cost',Decimal('0.16'))]:
            with self.subTest(field=field):
                self.corrupt('core_costreconciliation',f'UPDATE core_costreconciliation SET {field}=%s',(value,))
        self.corrupt('core_platformcost','UPDATE core_platformcost SET amount=%s',(usage.actual_cost,))

    def test_unknown_preparation_hold_is_preserved_without_provider_replay(self):
        from core.models import PreparationReceipt, TemplatePreparation
        prep=TemplatePreparation.objects.create(template=self.encounter.template_version.template,
            requested_by=self.doctor,config={'mode':'live','provider':'anthropic','model':'historical-label'})
        receipt=PreparationReceipt.objects.create(preparation=prep,role='proposer',provider='anthropic',
            requested_model='historical-label',request_sha256='b'*64,quote_maximum=Decimal('0.10'),
            state='unknown',finished_at=timezone.now())
        before=PreparationReceipt.objects.get(pk=receipt.pk).__dict__.copy()
        self.sponsored()
        self.assert_clean()
        after=PreparationReceipt.objects.get(pk=receipt.pk).__dict__.copy()
        before.pop('_state');after.pop('_state')
        self.assertEqual(after,before)
        self.assertEqual(after['state'],'unknown')
        self.assertEqual(after['quote_maximum'],Decimal('0.10'))

