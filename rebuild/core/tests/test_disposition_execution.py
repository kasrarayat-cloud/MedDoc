"""Only synthetic empty drafts; cryptographic keys never leave these fixtures."""
import copy
import json
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections, DatabaseError, transaction
from django.http import Http404
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import models as m, retention, disposition_execution as x, disposition_policy as p, disposition_journal as j
from core.security import scoped
from core.tests.test_retention_preservation import Fixture, ISOLATED

DURABLE = 'This document has a durable disposition instruction and is unavailable.'


class ExecutionFixture(Fixture):
    def setup_execution(self):
        self.setup_records()
        self.journal_temp = tempfile.TemporaryDirectory(); self.addCleanup(self.journal_temp.cleanup)
        self.path = Path(self.journal_temp.name) / 'instructions.jsonl'
        self.authority = Ed25519PrivateKey.generate(); self.checkpoint_key = Ed25519PrivateKey.generate()
        self.writer = Ed25519PrivateKey.generate(); self.namespace = str(uuid.uuid4())
        config = dict(DISPOSITION_ENABLED=True, DISPOSITION_NAMESPACE=self.namespace,
            DISPOSITION_AUTHORITY_KEYS={'counsel': self.authority.public_key().public_bytes_raw().hex()},
            DISPOSITION_CHECKPOINT_KEYS={'checkpoint': self.checkpoint_key.public_key().public_bytes_raw().hex()},
            DISPOSITION_JOURNAL_KEYS={'writer': self.writer.public_key().public_bytes_raw().hex()},
            DISPOSITION_JOURNAL_KEY_ID='writer', DISPOSITION_JOURNAL_PRIVATE_KEY=self.writer.private_bytes_raw().hex(),
            DISPOSITION_JOURNAL_PATH=str(self.path))
        self.execution_settings = override_settings(**config); self.execution_settings.enable(); self.addCleanup(self.execution_settings.disable)
        self.base = timezone.now(); self.clock_patch = patch('django.utils.timezone.now', return_value=self.base)
        self.clock = self.clock_patch.start(); self.addCleanup(self.clock_patch.stop)
        self.genesis = self.checkpoint()
        j.initialize(self.genesis)
        self.envelope = self.sign(self.authority, 'counsel', {
            'contract': 'disposition-policy-v1', 'policy_id': str(uuid.uuid4()), 'namespace': self.namespace,
            'department_id': str(self.scope[2].pk), 'adapter': p.ADAPTER, 'anchor': 'created_at',
            'minimum_age_seconds': 60, 'not_before': (self.base + timedelta(seconds=1)).isoformat(),
            'expires_at': (self.base + timedelta(days=2)).isoformat(), 'schedule_sha256': 'a'*64,
            'purpose': 'authorize_prospective_empty_draft_disposition'})
        self.admission = x.admit(self.admin, self.envelope)

    def sign(self, key, key_id, body):
        return {'key_id': key_id, 'body': body, 'signature': key.sign(p.signed_bytes(body)).hex()}

    def checkpoint(self, entries=None):
        entries = entries or []
        return self.sign(self.checkpoint_key, 'checkpoint', {'contract': 'disposition-journal-checkpoint-v1',
            'namespace': self.namespace, 'sequence': len(entries), 'head_sha256': p.digest(entries[-1]) if entries else p.ZERO,
            'issued_at': self.base.isoformat(), 'expires_at': (self.base + timedelta(days=2)).isoformat()})

    def empty(self):
        self.clock.return_value = self.base + timedelta(seconds=2)
        row = m.Encounter.objects.create(department=self.scope[2], patient=self.scope[3], template_version=self.encounter.template_version,
            created_by=self.scope[0], notes='', service_date=self.encounter.service_date)
        self.clock.return_value = self.base + timedelta(seconds=100)
        return row

    def approved(self, row=None):
        row = row or self.empty()
        instruction = x.prepare(self.admin, self.admission.pk, row.pk, uuid.uuid4())
        x.approve(self.second, instruction.pk, instruction.snapshot_sha256)
        return row, instruction

    def state(self):
        return {model.__name__: list(model.objects.order_by('pk').values())
                for model in apps.get_app_config('core').get_models()}


@override_settings(**ISOLATED)
class EmptyDraftExecution(ExecutionFixture, TestCase):
    def setUp(self): self.setup_execution()

    def test_exact_prospective_approval_deletes_only_empty_draft_and_retries_idempotently(self):
        m.Encounter.objects.filter(pk=self.encounter.pk).update(status='finalized', notes='SYNTHETIC prior signature and consent',
            answers={'consent': {'text': 'SYNTHETIC CONSENT'}, 'signature': {'text': 'SYNTHETIC SIGNATURE'}},
            finalized_at=self.base, finalized_by=self.scope[0], export_path='exports/synthetic-preserved.docx', export_sha256='b'*64)
        row = self.empty(); before = self.state(); row, instruction = self.approved(row)
        result = x.execute(self.admin, instruction.pk, self.genesis)
        self.assertEqual(result.outcome, 'empty_draft_deleted'); self.assertFalse(m.Encounter.objects.filter(pk=row.pk).exists())
        self.assertEqual(x.execute(self.admin, instruction.pk, self.genesis).pk, result.pk)
        after = self.state()
        added = {'DispositionPolicyAdmission','DispositionInstruction','DispositionApproval','DispositionTombstone','DispositionCompletion'}
        for name, records in before.items():
            if name in added: continue
            if name == 'AuditEvent':
                ids = {record['id'] for record in records}
                self.assertEqual([r for r in after[name] if r['id'] in ids], records, name)
            else:
                expected = [r for r in records if not (name == 'Encounter' and r['id'] == row.pk)]
                self.assertEqual(after[name], expected, name)
        entries = j.verified(self.checkpoint(j.verified()))
        self.assertEqual(len(entries), 1); self.assertEqual(entries[0]['body']['instruction']['target_id'], str(row.pk))
        self.assertNotIn('SYNTHETIC prior', self.path.read_text())

    def test_unset_untrusted_tampered_expired_or_nonprospective_policy_refuses(self):
        with override_settings(DISPOSITION_ENABLED=False), self.assertRaises(ValidationError): x.admit(self.admin, self.envelope)
        with override_settings(DISPOSITION_AUTHORITY_KEYS={}), self.assertRaises(ValidationError): x.admit(self.admin, self.envelope)
        for field, value in [('department_id', str(self.other[2].pk)), ('minimum_age_seconds', 1)]:
            envelope = copy.deepcopy(self.envelope); envelope['body'][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError): x.admit(self.admin, envelope)
        for changes in [{'not_before': (self.base-timedelta(days=1)).isoformat()},
                        {'expires_at': (self.base-timedelta(seconds=1)).isoformat()}, {'minimum_age_seconds': True}]:
            body = dict(self.envelope['body'], policy_id=str(uuid.uuid4()), **changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError): x.admit(self.admin, self.sign(self.authority, 'counsel', body))
        self.assertEqual(m.DispositionPolicyAdmission.objects.count(), 1)
        self.assertEqual(j.verified(), [])

    def test_age_cohort_and_wrong_department_are_not_eligible(self):
        m.Encounter.objects.filter(pk=self.encounter.pk).update(notes='')
        with self.assertRaises(ValidationError): x.prepare(self.admin, self.admission.pk, self.encounter.pk, uuid.uuid4())
        row = self.empty(); self.clock.return_value = row.created_at + timedelta(seconds=59)
        with self.assertRaises(ValidationError): x.prepare(self.admin, self.admission.pk, row.pk, uuid.uuid4())
        self.clock.return_value = self.base + timedelta(seconds=100)
        m.Encounter.objects.filter(pk=self.other[5].pk).update(notes='')
        with self.assertRaises(ValidationError): x.prepare(self.admin, self.admission.pk, self.other[5].pk, uuid.uuid4())

    def test_any_clinical_review_signing_or_export_payload_refuses(self):
        changes = [{'notes': 'SYNTHETIC consent recorded'}, {'answers': {'signature': 'SYNTHETIC'}},
                   {'template_review': {'accepted': True}}, {'revision': 1}, {'export_path': 'exports/synthetic.docx'},
                   {'export_sha256': 'a'*64}, {'finalized_by': self.scope[0]}, {'finalized_at': self.base},
                   {'status': 'finalized'}]
        for change in changes:
            row = self.empty(); m.Encounter.objects.filter(pk=row.pk).update(**change)
            with self.subTest(change=list(change)), self.assertRaises(ValidationError):
                x.prepare(self.admin, self.admission.pk, row.pk, uuid.uuid4())
        self.assertFalse(m.DispositionInstruction.objects.exists())

    def test_jobs_batches_historical_holds_archives_and_old_review_audit_refuse(self):
        for kind in ('job', 'batch', 'released_hold', 'archive', 'review_audit'):
            row = self.empty()
            if kind == 'job': m.Job.objects.create(encounter=row, user=self.scope[0], request_key=str(uuid.uuid4()), state='failed')
            elif kind == 'batch':
                plan = {'parts': []}
                m.GenerationBatch.objects.create(encounter=row, user=self.scope[0], admission_key=uuid.uuid4(), revision=0,
                    plan=plan, plan_sha256=p.digest(plan), maximum_charge=0, state='failed')
            elif kind == 'released_hold':
                hold = retention.create_hold(self.admin, 'encounter', row.pk, 'a'*64, uuid.uuid4())
                retention.release_hold(self.second, hold.pk, 'b'*64)
            elif kind == 'archive':
                m.PreservedRecord.objects.create(source_table='core_encounter', source_id=row.pk, operation='UPDATE',
                    hold_ids=[], prior_record={'id': str(row.pk), 'notes': 'SYNTHETIC preserved consent'})
            else: m.AuditEvent.objects.create(actor=self.scope[0], action='encounter.answers_saved', target=str(row.pk))
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                x.prepare(self.admin, self.admission.pk, row.pk, uuid.uuid4())
        self.assertFalse(m.DispositionInstruction.objects.exists())

    def test_distinct_review_stale_digest_and_late_change_refuse(self):
        row = self.empty(); instruction = x.prepare(self.admin, self.admission.pk, row.pk, uuid.uuid4())
        with self.assertRaises(PermissionDenied): x.approve(self.admin, instruction.pk, instruction.snapshot_sha256)
        with self.assertRaises(ValidationError): x.approve(self.second, instruction.pk, 'f'*64)
        x.approve(self.second, instruction.pk, instruction.snapshot_sha256)
        m.Encounter.objects.filter(pk=row.pk).update(notes='SYNTHETIC correction')
        with self.assertRaises(ValidationError): x.execute(self.admin, instruction.pk, self.genesis)
        self.assertEqual(j.verified(), []); self.assertFalse(m.DispositionTombstone.objects.exists())

    def test_unknown_catalog_and_untrusted_checkpoint_refuse_before_journal(self):
        row, instruction = self.approved()
        with patch('core.disposition.COLUMNS', {}), self.assertRaises(ValidationError): x.execute(self.admin, instruction.pk, self.genesis)
        broken = copy.deepcopy(self.genesis); broken['signature'] = '0'*128
        with self.assertRaises(ValidationError): x.execute(self.admin, instruction.pk, broken)
        self.assertEqual(j.verified(), []); self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists())

    def test_journal_fsync_failure_preserves_row_and_complete_pending_intent_denies_access(self):
        row, instruction = self.approved()
        with patch('core.disposition_journal.os.fsync', side_effect=OSError('SYNTHETIC fsync failure')):
            with self.assertRaises(ValidationError): x.execute(self.admin, instruction.pk, self.genesis)
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertFalse(m.DispositionTombstone.objects.exists())
        self.assertFalse(scoped(m.Encounter, self.scope[0]).filter(pk=row.pk).exists())
        self.assertEqual(x.execute(self.admin, instruction.pk, self.genesis).outcome, 'empty_draft_deleted')

    def test_db_rollback_after_delete_keeps_journal_intent_enforced_then_exact_retry_completes(self):
        from core import jobs, views
        row, instruction = self.approved()
        with patch.object(m.DispositionCompletion.objects, 'create', side_effect=RuntimeError('SYNTHETIC crash')):
            with self.assertRaises(RuntimeError): x.execute(self.admin, instruction.pk, self.genesis)
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertFalse(m.DispositionTombstone.objects.exists())
        self.assertFalse(scoped(m.Encounter, self.scope[0]).filter(pk=row.pk).exists())
        request = RequestFactory().get('/synthetic/'); request.user = self.scope[0]
        with self.assertRaises(Http404): views.api_encounter(request, row.pk)
        # The durable-intent refusal itself, not any refusal: an empty draft refuses a generation for having no notes
        # anyway, which let this assertion pass with the journal check deleted from jobs.enqueue's lock (RF-R3).
        with self.assertRaisesMessage(ValidationError, DURABLE): jobs.enqueue(row, self.scope[0])
        self.assertFalse(m.Job.objects.filter(encounter=row).exists())
        result = x.execute(self.admin, instruction.pk, self.genesis)
        self.assertEqual(len(j.verified()), 1); self.assertEqual(result.outcome, 'empty_draft_deleted')

    def test_durable_intent_refuses_a_transcription_the_one_request_an_empty_draft_accepts(self):
        """RF-R3. Reproduce (the finding's input): an approved exact empty draft whose execute fails after its journal
        append (DispositionCompletion.objects.create raises), leaving a durable pending intent; then jobs.enqueue(row,
        clinician, 'transcription', <2 s synthetic WAV>) under STANDARD_ENV. With require_access deleted from
        disposition_execution.lock_available, every test passed and this enqueue queued a transcription and held money
        on a draft whose disposal is durably journaled. It must refuse, naming the durable instruction."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core import jobs
        from core.security import store_upload
        from core.tests.audio_fixtures import wav_bytes
        from core.tests.test_recording_limit import STANDARD_ENV

        def recording(tag):
            return store_upload(SimpleUploadedFile(f'{tag}.wav', wav_bytes(seconds=2, tag=tag), content_type='audio/wav'), 'audio')
        row, instruction = self.approved()
        with patch.object(m.DispositionCompletion.objects, 'create', side_effect=RuntimeError('SYNTHETIC crash')):
            with self.assertRaises(RuntimeError): x.execute(self.admin, instruction.pk, self.genesis)
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertEqual(len(j.verified()), 1)
        clinician = self.scope[0]
        with patch.dict(os.environ, STANDARD_ENV):
            with self.assertRaisesMessage(ValidationError, DURABLE):
                jobs.enqueue(row, clinician, 'transcription', recording('rfr3-durable'))
            self.assertFalse(m.Job.objects.exists()); self.assertFalse(m.Reservation.objects.exists())
            # Positive control: an exact empty draft with no instruction queues the same request.
            other = self.empty()
            job = jobs.enqueue(other, clinician, 'transcription', recording('rfr3-control'))
        self.assertEqual((job.kind, job.state, job.encounter_id), ('transcription', 'queued', other.pk))
        self.assertTrue(m.Reservation.objects.filter(job=job, state='held').exists())

    def test_replay_on_older_conflicting_snapshot_only_suppresses_and_never_erases_it(self):
        row, instruction = self.approved()
        with transaction.atomic():
            x.execute(self.admin, instruction.pk, self.genesis)
            transaction.set_rollback(True)  # exact older DB snapshot; independent journal survives
        m.Encounter.objects.filter(pk=row.pk).update(notes='SYNTHETIC restored signature/consent evidence', revision=1)
        before = list(m.Encounter.objects.filter(pk=row.pk).values())
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(uuid.uuid4())):
            report = x.replay(self.admin, self.checkpoint(j.verified()))
            self.assertEqual(x.replay(self.admin, self.checkpoint(j.verified()))['tombstones'], 1)
        self.assertEqual(report['clinical_rows_deleted'], 0); self.assertFalse(report['restore_admission_available'])
        self.assertEqual(list(m.Encounter.objects.filter(pk=row.pk).values()), before)
        self.assertFalse(scoped(m.Encounter, self.scope[0]).filter(pk=row.pk).exists())
        with self.assertRaises(DatabaseError), transaction.atomic(): m.Encounter.objects.filter(pk=row.pk).update(notes='changed')
        with self.assertRaises(DatabaseError), transaction.atomic(): m.Encounter.objects.filter(pk=row.pk).delete()

    def test_replay_requires_quarantine_exact_checkpoint_and_complete_untampered_chain(self):
        row, instruction = self.approved(); x.execute(self.admin, instruction.pk, self.genesis)
        with self.assertRaises(ValidationError): x.replay(self.admin, self.checkpoint(j.verified()))
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(uuid.uuid4())):
            with self.assertRaises(ValidationError): x.replay(self.admin, self.genesis)
            good = self.path.read_bytes(); self.path.write_bytes(good[:-1])
            with self.assertRaises(ValidationError): x.replay(self.admin, self.genesis)
            self.path.write_bytes(good)
            entry = j.verified()[0]; entry['body']['instruction']['target_id'] = str(uuid.uuid4())
            self.path.write_bytes(p.canonical(entry)+b'\n')
            with self.assertRaises(ValidationError): scoped(m.Encounter, self.scope[0])

    def test_sql_cannot_resurrect_or_attach_work_and_new_instruction_history_is_immutable(self):
        row, instruction = self.approved(); result = x.execute(self.admin, instruction.pk, self.genesis)
        with self.assertRaises(DatabaseError), transaction.atomic(): row.save(force_insert=True)
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.Job.objects.create(encounter_id=row.pk, user=self.scope[0], request_key='synthetic late')
        for model in (m.DispositionPolicyAdmission, m.DispositionInstruction, m.DispositionApproval,
                      m.DispositionTombstone, m.DispositionCompletion):
            for operation in ('update', 'delete', 'truncate'):
                with self.subTest(model=model.__name__, operation=operation), self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        table = model._meta.db_table
                        cursor.execute(f'UPDATE {table} SET created_at=created_at' if operation=='update' else
                                       f'DELETE FROM {table}' if operation=='delete' else f'TRUNCATE {table} CASCADE')
        self.assertEqual(m.DispositionCompletion.objects.get().pk, result.pk)

    def test_database_shape_or_hash_claim_does_not_grant_signed_policy_authority(self):
        body = dict(self.envelope['body'], policy_id=str(uuid.uuid4()))
        forged = {'body': body, 'key_id': 'counsel', 'signature': '0'*128}
        row = m.DispositionPolicyAdmission.objects.create(policy_id=body['policy_id'], department=self.scope[2],
            envelope=forged, envelope_sha256=p.digest(forged), created_by=self.admin)
        target = self.empty()
        with self.assertRaises(ValidationError): x.prepare(self.admin, row.pk, target.pk, uuid.uuid4())
        self.assertFalse(m.DispositionInstruction.objects.exists())

    def test_expired_authority_revoked_signer_or_suspended_reviewer_cannot_execute(self):
        row, instruction = self.approved()
        self.clock.return_value = self.base + timedelta(days=3)
        with self.assertRaises(ValidationError): x.execute(self.admin, instruction.pk, self.genesis)
        self.clock.return_value = self.base + timedelta(seconds=100)
        with override_settings(DISPOSITION_AUTHORITY_KEYS={}), self.assertRaises(ValidationError):
            x.execute(self.admin, instruction.pk, self.genesis)
        m.User.objects.filter(pk=self.second.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied): x.execute(self.admin, instruction.pk, self.genesis)
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertEqual(j.verified(), [])

    def test_unknown_or_duplicate_policy_members_and_wrong_namespace_refuse(self):
        for raw in (b'{"key_id":"a","key_id":"b"}', b'{"x":NaN}', b'{'):
            with self.subTest(raw=raw), self.assertRaises(ValidationError): p.decode(raw)
        body = dict(self.envelope['body'], namespace=str(uuid.uuid4()))
        with self.assertRaises(ValidationError): x.admit(self.admin, self.sign(self.authority, 'counsel', body))
        body = dict(self.envelope['body'], unexpected=True)
        with self.assertRaises(ValidationError): x.admit(self.admin, self.sign(self.authority, 'counsel', body))

    def test_next_instruction_needs_new_independent_head_checkpoint(self):
        row, first = self.approved(); x.execute(self.admin, first.pk, self.genesis)
        row, second = self.approved()
        with self.assertRaises(ValidationError): x.execute(self.admin, second.pk, self.genesis)
        result = x.execute(self.admin, second.pk, self.checkpoint(j.verified()))
        self.assertEqual(result.outcome, 'empty_draft_deleted'); self.assertEqual(len(j.verified()), 2)
        # Exact idempotent result retrieval does not rewrite either journal entry.
        self.assertEqual(x.execute(self.admin, first.pk, self.genesis).outcome, 'empty_draft_deleted')
        self.assertEqual(len(j.verified()), 2)

    def test_read_only_journal_can_be_verified_for_quarantined_replay(self):
        row, instruction = self.approved(); x.execute(self.admin, instruction.pk, self.genesis)
        checkpoint = self.checkpoint(j.verified()); self.path.chmod(0o400)
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(uuid.uuid4())):
            self.assertEqual(x.replay(self.admin, checkpoint)['tombstones'], 1)

    def test_reverse_migration_refuses_instruction_history(self):
        import importlib
        reverse = importlib.import_module('core.migrations.0030_empty_draft_disposition').REVERSE
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor: cursor.execute(reverse)
        self.assertEqual(m.DispositionPolicyAdmission.objects.count(), 1)

    def test_journal_inside_any_selected_state_directory_refuses(self):
        before = self.path.read_bytes()
        with override_settings(STATE_DIR=Path(self.journal_temp.name), MEDIA_ROOT=Path(self.journal_temp.name) / 'files'):
            with self.assertRaises(ValidationError): j.verified(self.genesis)
        self.assertEqual(self.path.read_bytes(), before)

    def test_patient_review_keeps_instruction_history_after_empty_row_is_deleted(self):
        from core import disposition as d
        row, instruction = self.approved(); completion = x.execute(self.admin, instruction.pk, self.genesis)
        request = d.submit(self.admin, row.department_id, 'patient', row.patient_id, 'c'*64, uuid.uuid4())
        graph = d.prepare(self.admin, request.pk).graph
        self.assertEqual([r['id'] for r in graph['nodes']['DispositionInstruction']], [str(instruction.pk)])
        self.assertEqual([r['id'] for r in graph['nodes']['DispositionApproval']], [str(instruction.approval.pk)])
        self.assertEqual([r['id'] for r in graph['nodes']['DispositionTombstone']], [str(completion.tombstone_id)])
        self.assertEqual([r['id'] for r in graph['nodes']['DispositionCompletion']], [str(completion.pk)])
        self.assertIn('disposed_target', graph['blockers']); self.assertFalse(graph['deletion_authorized'])


@override_settings(**ISOLATED)
class ExecutionAdministration(ExecutionFixture, TestCase):
    url = '/console/disposition-execution/'

    def setUp(self): self.setup_execution()

    def login(self, user):
        device = TOTPDevice.objects.create(user=user, name='Synthetic execution', confirmed=True)
        self.client.force_login(user)
        session = self.client.session; session['otp_device_id'] = device.persistent_id; session.save()

    def post(self, action, **values):
        return self.client.post(self.url, {'action': action, **{f'{action}-{k}': v for k, v in values.items()}})

    def artifact(self, name, response):
        if directory := os.getenv('QUILLMD_DISPOSITION_ARTIFACT_DIR'):
            folder = Path(directory); folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(response.content)

    def test_default_off_and_clinician_or_unverified_admin_cannot_execute(self):
        for actor in [self.scope[0], self.admin]:
            self.client.force_login(actor)
            self.assertIn(self.client.get(self.url).status_code, [302, 404])
        self.login(self.admin)
        with override_settings(DISPOSITION_ENABLED=False):
            page = self.client.get(self.url)
            self.assertContains(page, 'Execution unavailable.'); self.assertNotContains(page, '<form method="post"')
            self.artifact('execution-unavailable.html', page)
            self.assertEqual(self.post('prepare', target=uuid.uuid4()).status_code, 400)
        self.assertFalse(m.DispositionInstruction.objects.exists())

    def test_authenticated_two_custodian_exact_flow_and_explicit_confirmation(self):
        self.login(self.admin)
        row = self.empty()
        response = self.post('prepare', admission=self.admission.pk, target=row.pk, request_key=uuid.uuid4())
        self.assertEqual(response.status_code, 302, response.content)
        instruction = m.DispositionInstruction.objects.get()
        self.assertEqual(instruction.created_by, self.admin)
        self.assertEqual(self.post('approve', instruction=instruction.pk, digest=instruction.snapshot_sha256,
                                   confirmed='on').status_code, 403)
        self.login(self.second)
        self.assertEqual(self.post('approve', instruction=instruction.pk, digest=instruction.snapshot_sha256,
                                   confirmed='on').status_code, 302)
        page = self.client.get(self.url); self.assertContains(page, str(row.pk)); self.assertContains(page, instruction.snapshot_sha256)
        self.artifact('execution-approved.html', page)
        response = self.post('execute', instruction=instruction.pk, target=row.pk, checkpoint=json.dumps(self.genesis))
        self.assertEqual(response.status_code, 200); self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists())
        response = self.post('execute', instruction=instruction.pk, target=uuid.uuid4(), checkpoint=json.dumps(self.genesis), confirmed='on')
        self.assertContains(response, 'draft ID does not match'); self.assertEqual(j.verified(), [])
        response = self.post('execute', instruction=instruction.pk, target=row.pk, checkpoint=json.dumps(self.genesis), confirmed='on')
        self.assertEqual(response.status_code, 302, response.content)
        self.assertFalse(m.Encounter.objects.filter(pk=row.pk).exists())
        self.assertEqual(m.DispositionCompletion.objects.get().created_by, self.second)
        page = self.client.get(self.url); self.assertContains(page, 'Local deletion recorded')
        self.assertNotContains(page, 'source_snapshot')

    def test_untrusted_duplicate_and_missing_approval_are_visible_refusals(self):
        self.login(self.admin)
        self.assertContains(self.post('initialize', checkpoint='{"a":1,"a":2}'), 'signed authority document is invalid')
        self.assertContains(self.post('admit', policy=json.dumps(dict(self.envelope, signature='0'*128)), confirmed='on'),
                            'authority could not be verified')
        row = self.empty(); instruction = x.prepare(self.admin, self.admission.pk, row.pk, uuid.uuid4())
        response = self.post('execute', instruction=instruction.pk, target=row.pk, checkpoint=json.dumps(self.genesis), confirmed='on')
        self.assertContains(response, 'distinct approval was not found')
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertEqual(j.verified(), [])

    def test_public_envelope_admission_and_checkpoint_flow(self):
        self.login(self.admin)
        self.assertEqual(self.post('initialize', checkpoint=json.dumps(self.genesis)).status_code, 302)
        body = dict(self.envelope['body'], policy_id=str(uuid.uuid4()))
        response = self.post('admit', policy=json.dumps(self.sign(self.authority, 'counsel', body)), confirmed='on')
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(m.DispositionPolicyAdmission.objects.count(), 2)
        page = self.client.get(self.url)
        self.assertNotContains(page, self.writer.private_bytes_raw().hex())

    def test_quarantine_allows_only_verified_suppression_replay(self):
        row, instruction = self.approved(); x.execute(self.admin, instruction.pk, self.genesis)
        checkpoint = self.checkpoint(j.verified()); self.login(self.admin)
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(uuid.uuid4()), DISPOSITION_ENABLED=False):
            page = self.client.get(self.url); self.assertContains(page, 'Replay does not admit this target.')
            self.assertNotContains(page, 'Delete approved empty draft'); self.artifact('execution-replay.html', page)
            self.assertEqual(self.post('execute', instruction=instruction.pk).status_code, 400)
            self.assertEqual(self.post('replay', checkpoint=json.dumps(checkpoint), confirmed='on').status_code, 302)
            self.assertEqual(self.client.get('/patients/').status_code, 503)
            self.assertEqual(m.DispositionTombstone.objects.count(), 1)

    def test_real_csrf_check_rejects_authenticated_submission_without_token(self):
        self.login(self.admin); self.client.handler.enforce_csrf_checks = True
        response = self.post('initialize', checkpoint=json.dumps(self.genesis))
        self.assertEqual(response.status_code, 403); self.assertEqual(j.verified(), [])


@override_settings(**ISOLATED)
class ExecutionConcurrency(ExecutionFixture, TransactionTestCase):
    def setUp(self): self.setup_execution()

    def competing_commits_first(self, kind):
        row, instruction = self.approved(); entered = threading.Event(); release = threading.Event()
        def writer():
            try:
                with transaction.atomic():
                    if kind == 'hold': retention.create_hold(self.admin, 'encounter', row.pk, 'b'*64, uuid.uuid4())
                    else: m.Job.objects.create(encounter=row, user=self.scope[0], request_key='synthetic racing job', state='failed')
                    entered.set(); self.assertTrue(release.wait(5))
            finally: connections.close_all()
        def execution():
            try:
                with self.assertRaises(ValidationError): x.execute(self.admin, instruction.pk, self.genesis)
            finally: connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(writer); self.assertTrue(entered.wait(5)); second = pool.submit(execution)
            time.sleep(.1); self.assertFalse(second.done()); release.set(); first.result(5); second.result(5)
        # No disposition instruction was journaled. The winning hold itself is, before its row committed (1a).
        entries = j.verified()
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertEqual(j.instruction_entries(entries), [])
        self.assertEqual([e['body']['hold']['id'] for e in entries],
                         [str(pk) for pk in m.RetentionHold.objects.filter(encounter_id=row.pk).values_list('pk', flat=True)])
        self.assertFalse(m.DispositionCompletion.objects.exists())

    def test_committed_hold_wins_before_waiting_disposition(self): self.competing_commits_first('hold')
    def test_committed_job_wins_before_waiting_disposition(self): self.competing_commits_first('job')

    def execution_commits_first(self, kind):
        row, instruction = self.approved(); entered = threading.Event(); release = threading.Event()
        actual = j.append
        def paused_append(*args):
            entry = actual(*args); entered.set(); self.assertTrue(release.wait(5)); return entry
        def execute():
            try: x.execute(self.admin, instruction.pk, self.genesis)
            finally: connections.close_all()
        def writer():
            try:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    if kind == 'hold': retention.create_hold(self.admin, 'encounter', row.pk, 'b'*64, uuid.uuid4())
                    else: m.Job.objects.create(encounter=row, user=self.scope[0], request_key='synthetic late job', state='failed')
            except ValidationError:
                if kind != 'hold': raise
                # A hold helper may observe that the exact target vanished after waiting.
            finally: connections.close_all()
        with patch.object(j, 'append', side_effect=paused_append), ThreadPoolExecutor(2) as pool:
            first = pool.submit(execute); self.assertTrue(entered.wait(5)); second = pool.submit(writer)
            time.sleep(.1); self.assertFalse(second.done()); release.set(); first.result(5); second.result(5)
        self.assertFalse(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertEqual(m.DispositionCompletion.objects.count(), 1)
        self.assertFalse(m.Job.objects.filter(encounter_id=row.pk).exists())
        self.assertFalse(m.RetentionHold.objects.filter(encounter_id=row.pk).exists())

    def test_disposition_commits_before_waiting_job_and_reservation_graph(self): self.execution_commits_first('job')
    def test_disposition_commits_before_waiting_target_hold(self): self.execution_commits_first('hold')
