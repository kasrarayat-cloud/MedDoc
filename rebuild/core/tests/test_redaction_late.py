"""Refutation F2 (dc33e094): a provider result that arrives after its document was redacted must not persist clinical
content. The late-receipt path (core.jobs.run_one) wrote receipts/<new>.json with the quoted notes, which the tombstone
never listed and the backup's file query still copied. The receipt's accounting facts are still recorded.

Synthetic only; the provider call is patched (no network), as in the refuter's P9.
"""
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.db import DatabaseError, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core import disposition_journal as j, disposition_policy as p, models as m, redaction
from core.tests import test_settlement_single_worker as ssw
from core.tests.test_billing_boundary import LIVE
from core.tests.test_billing_policy import STORAGES
from core.tests.test_settlement_database_error import HeldSettlementFixture
from ops.backup_restore import FILE_QUERIES

QUOTE = 'no chest pain'


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class LateResultAfterRedaction(ssw.Console, HeldSettlementFixture, TransactionTestCase):
    second_worker_during_the_call = ssw.SecondWorkerDuringALiveProviderCall.second_worker_during_the_call
    wallets = ssw.SecondWorkerDuringALiveProviderCall.wallets
    document = ssw.SecondWorkerDuringALiveProviderCall.document

    def journal(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ck = Ed25519PrivateKey.generate(); writer = Ed25519PrivateKey.generate(); self.ns = str(uuid.uuid4())
        config = dict(DISPOSITION_ENABLED=True, DISPOSITION_NAMESPACE=self.ns,
                      DISPOSITION_CHECKPOINT_KEYS={'checkpoint': self.ck.public_key().public_bytes_raw().hex()},
                      DISPOSITION_JOURNAL_KEYS={'writer': writer.public_key().public_bytes_raw().hex()},
                      DISPOSITION_JOURNAL_KEY_ID='writer', DISPOSITION_JOURNAL_PRIVATE_KEY=writer.private_bytes_raw().hex(),
                      DISPOSITION_JOURNAL_PATH=str(Path(self.tmp.name) / 'journal.jsonl'))
        override = override_settings(**config); override.enable(); self.addCleanup(override.disable)
        j.initialize(self.checkpoint())
        self.c1 = m.User.objects.create_user(username='late-a', email='late-a@synthetic.invalid', verified_at=timezone.now(), is_staff=True)
        self.c2 = m.User.objects.create_user(username='late-b', email='late-b@synthetic.invalid', verified_at=timezone.now(), is_staff=True)

    def checkpoint(self, entries=None):
        entries = entries or []
        now = timezone.now()
        body = {'contract': 'disposition-journal-checkpoint-v1', 'namespace': self.ns, 'sequence': len(entries),
                'head_sha256': p.digest(entries[-1]) if entries else p.ZERO, 'issued_at': now.isoformat(),
                'expires_at': (now + timedelta(days=1)).isoformat()}
        return {'key_id': 'checkpoint', 'body': body, 'signature': self.ck.sign(p.signed_bytes(body)).hex()}

    def test_a_late_provider_result_for_a_redacted_document_keeps_its_accounting_and_no_content(self):
        self.journal()
        seen = {}

        def redact(job, draft):
            requested = redaction.request(self.c1, draft.pk, 'c' * 64, uuid.uuid4())
            seen['tombstone'] = redaction.execute(self.c2, requested.pk, self.checkpoint(j.verified()))
        real = ssw.adopted_live_result
        def sdk_like(notes, fields, request_id, *args, **kwargs):
            value = real(notes, fields, request_id, *args, **kwargs)
            response = value[0]['anthropic_response']
            response.model_dump = lambda **kw: {'id': response.id, 'content': [{'type': c.type, 'text': c.text}
                                                                               for c in response.content]}
            return value
        with patch.object(ssw, 'adopted_live_result', sdk_like):
            job, draft, _before, _document, _seen = self.second_worker_during_the_call(
                'late-redacted', resolve_form=ssw.RELEASE, then=redact)
        job.refresh_from_db()
        self.assertEqual(m.Encounter.objects.get(pk=draft.pk).status, 'redacted')
        # The receipt's accounting facts stand: provider, request id, cost.
        receipt = m.ProviderReceipt.objects.get(job=job)
        self.assertEqual(receipt.provider_request_id, 'req_two_workers_late-redacted')
        self.assertEqual(job.state, 'reconciliation')
        # No content: no result file was written (dc33e094: receipts/<new>.json with the quoted notes), none is referenced
        # for a backup to copy, and nothing under the private state root holds the quote.
        self.assertEqual(job.result_path, '')
        self.assertTrue(m.AuditEvent.objects.filter(action='provider.output_withheld', target=str(job.pk)).exists())
        files = [path for path in Path(settings.MEDIA_ROOT).rglob('*.json') if QUOTE.encode() in path.read_bytes()]
        self.assertEqual(files, [])
        with connection.cursor() as cursor:
            keys = set()
            for _kind, statement in FILE_QUERIES:
                cursor.execute(statement); keys |= {row[0] for row in cursor.fetchall()}
        self.assertFalse(any(key.startswith('receipts/') for key in keys))
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    def test_a_redaction_committing_while_the_late_result_is_written_still_leaves_no_bytes(self):
        """The race: the result file is written while the redaction has not committed yet (the first check reads no
        tombstone), and the redaction commits before the result's own check afterwards. That check removes the file it
        wrote and clears the job's reference to it (round 2: it no longer sweeps the whole document, so a redaction that is
        only journaled keeps its content fingerprint for its exact retry)."""
        self.journal()
        seen = {}

        def redact(job, draft):
            requested = redaction.request(self.c1, draft.pk, 'c' * 64, uuid.uuid4())
            seen['tombstone'] = redaction.execute(self.c2, requested.pk, self.checkpoint(j.verified()))
        with patch('core.redaction.withheld', side_effect=self.first_check_misses()):
            job, draft, _before, _document, _seen = self.second_worker_during_the_call(
                'late-race', resolve_form=ssw.RELEASE, then=redact)
        job.refresh_from_db()
        self.assertEqual((job.result_path, job.result_sha256), ('', ''))  # round 1: the key stayed, its bytes swept
        self.assertEqual(self.holding_the_quote(), [])
        self.assertTrue(m.AuditEvent.objects.filter(action='provider.output_withheld', target=str(job.pk)).exists())
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    def first_check_misses(self):
        real = redaction.withheld
        calls = []
        def check(encounter_id):
            calls.append(encounter_id)
            return False if len(calls) == 1 else real(encounter_id)
        return check

    def holding_the_quote(self):
        return [path for path in Path(settings.MEDIA_ROOT).rglob('*.json') if QUOTE.encode() in path.read_bytes()]

    def sdk_like(self):
        real = ssw.adopted_live_result
        def result(notes, fields, request_id, *args, **kwargs):
            value = real(notes, fields, request_id, *args, **kwargs)
            response = value[0]['anthropic_response']
            response.model_dump = lambda **kw: {'id': response.id, 'content': [{'type': c.type, 'text': c.text}
                                                                               for c in response.content]}
            return value
        return patch.object(ssw, 'adopted_live_result', result)

    def journaled_only(self, seen):
        """A redaction journaled and fsynced whose database commit then failed (F3's state): the window of R2D-L1."""
        def redact(job, draft):
            requested = redaction.request(self.c1, draft.pk, 'c' * 64, uuid.uuid4())
            seen['request'] = requested
            with patch('core.redaction.apply', side_effect=DatabaseError('SYNTHETIC lost connection')):
                with self.assertRaises(DatabaseError):
                    redaction.execute(self.c2, requested.pk, self.checkpoint(j.verified()))
        return redact

    def assert_withheld_then_the_exact_retry_commits(self, job, draft, seen):
        job.refresh_from_db()
        self.assertFalse(m.RedactionTombstone.objects.filter(target_id=draft.pk).exists())   # journaled, not committed
        self.assertEqual((job.result_path, job.result_sha256), ('', ''))   # 4cfa4301: receipts/<new>.json with the quote
        self.assertEqual(self.holding_the_quote(), [])
        self.assertTrue(m.AuditEvent.objects.filter(action='provider.output_withheld', target=str(job.pk)).exists())
        self.assertEqual(self.resolve(job).status_code, 302)               # the administrator resolves the late receipt
        redaction.execute(self.c2, seen['request'].pk, self.checkpoint(j.verified()))   # 4cfa4301: CONTENT_CHANGED for good
        self.assertEqual(m.Encounter.objects.get(pk=draft.pk).status, 'redacted')
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    def test_L1_a_late_result_after_a_redaction_that_is_only_journaled_is_withheld_and_the_retry_commits(self):
        """Refutation R2D-L1 (4cfa4301): withheld() read only the database tombstone, so while a journaled redaction waited
        for its retried commit, a late provider result wrote the quoted notes to receipts (and backups copied it), and the
        new file changed the content: the exact retry refused for good and the journal refused any other request."""
        self.journal()
        seen = {}
        with self.sdk_like():
            job, draft, *_ = self.second_worker_during_the_call('late-journaled', resolve_form=ssw.RELEASE,
                                                               then=self.journaled_only(seen))
        self.assert_withheld_then_the_exact_retry_commits(job, draft, seen)

    def test_L1_race_a_redaction_journaled_while_the_late_result_is_written(self):
        self.journal()
        seen = {}
        with self.sdk_like(), patch('core.redaction.withheld', side_effect=self.first_check_misses()):
            job, draft, *_ = self.second_worker_during_the_call('late-journaled-race', resolve_form=ssw.RELEASE,
                                                               then=self.journaled_only(seen))
        self.assert_withheld_then_the_exact_retry_commits(job, draft, seen)
