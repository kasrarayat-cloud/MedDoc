"""Bounded offline checks for the inspection-only synthetic Word variant."""
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from lxml import etree

from core import coding_service as service
from core.coding_draft_export import TITLE, draft_review, export_synthetic_coding_draft
from core.coding_export import DRAFT_TAG, TAG, W, append_codes, append_review
from core.models import AuditEvent, CodingDecision, CodingRun, Encounter, Job, Membership, User
from core.tests.test_coding_export import document_bytes, texts
from core.tests import test_corti_workflow as replay_fixture


class SyntheticDraftAssembly(SimpleTestCase):
    def test_both_variants_refuse_reappending_and_preserve_clinical_members(self):
        original = document_bytes()
        draft = append_review(original, [(TITLE, True), ('CPT 00000 — unverified synthetic example', False)], tag=DRAFT_TAG)
        approved = append_codes(original, [{'system': 'ICD-10-CM', 'code': 'Z00.00', 'description': 'Synthetic example'}])
        for variant in (draft, approved):
            with self.assertRaisesMessage(ValidationError, 'already contains'):
                append_review(variant, [(TITLE, True)], tag=DRAFT_TAG)
            with self.assertRaisesMessage(ValidationError, 'already contains'):
                append_codes(variant, [])
        with ZipFile(BytesIO(original)) as source, ZipFile(BytesIO(draft)) as target:
            self.assertEqual(source.namelist(), target.namelist())
            for name in source.namelist():
                if name == 'word/document.xml':
                    before = source.read(name)
                    self.assertTrue(target.read(name).startswith(before[:before.rindex(b'<w:sectPr')]))
                    xml = etree.fromstring(target.read(name))
                    self.assertEqual(xml.xpath('//w:tag/@w:val', namespaces={'w': W}), [DRAFT_TAG])
                else:
                    self.assertEqual(source.read(name), target.read(name))
        self.assertEqual(texts(draft)[:len(texts(original))], texts(original))
        self.assertNotIn(TAG, draft.decode('latin1'))


@override_settings(CODING_PROVIDER='corti', CORTI_CODING_MODE='replay', CODING_ALLOW_TEST_FIXTURES=True,
                   CORTI_REPLAY_FIXTURE=replay_fixture.FIXTURE, SYNTHETIC_ONLY=True, ADMIN_SITE=False, STORAGES=replay_fixture.STORAGES,
                   CPT_ENTITLEMENT_MANIFEST='/missing-corti-test-entitlement.json')
class SyntheticDraftExport(TestCase):
    def setUp(self):
        # Reuse the already-qualified tiny, explicitly synthetic reference fixture;
        # do not inherit or rerun the earlier workflow test campaign.
        replay_fixture.CortiWorkflowTests.setUp(self)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        override = override_settings(MEDIA_ROOT=self.root)
        override.enable(); self.addCleanup(override.disable)
        self.original = document_bytes()
        self.path = self.root / 'exports/finalized.docx'
        self.path.parent.mkdir(mode=0o700)
        self.path.write_bytes(self.original)
        self.encounter.status = 'finalized'
        self.encounter.finalized_by = self.actor
        self.encounter.finalized_at = timezone.now()
        self.encounter.export_path = 'exports/finalized.docx'
        self.encounter.export_sha256 = hashlib.sha256(self.original).hexdigest()
        self.encounter.save()
        self.run = replay_fixture.CortiWorkflowTests.complete(self)
        self.run = service.update_selection(self.run, self.actor,
            {'selected_ids': ['selected:0'], 'overrides': {}}, self.run.selection_revision)
        self.decision = service.approve(self.run, self.actor, self.run.input_digest, service.selection_digest(self.run))

    def download(self, user=None):
        request = RequestFactory().get('/synthetic/export-coding-draft/?selected_ids=selected:2')
        request.user = self.actor if user is None else user
        return export_synthetic_coding_draft(request, self.encounter.pk)

    def test_draft_selected_only_all_spans_statuses_and_no_defective_description(self):
        run, decision, rows, paragraphs = draft_review(self.encounter)
        self.assertEqual([row['code'] for row in rows], ['R12', 'K59.00', '99213'])
        self.assertEqual([row['valid_evidence_count'] for row in rows], [2, 2, 3])
        self.assertEqual(rows[0]['decision_status'], 'Accepted in the separate saved approval.')
        self.assertEqual(rows[1]['decision_status'], 'Rejected in the saved review.')
        self.assertEqual(rows[2]['decision_status'], 'Held — excluded from approved export.')
        self.assertEqual(rows[2]['terminology_status'], 'unavailable')
        content = '\n'.join(text for text, _ in paragraphs)
        self.assertIn(TITLE, content)
        self.assertIn('Description withheld — unverified.', content)
        self.assertIn('E/M selection criteria', content)
        self.assertNotIn('15 MINUTES', content)
        self.assertNotIn('K21.9', content)
        self.assertNotIn('/missing', content)
        self.assertIn('15 MINUTES', run.result['suggestions'][2]['provider_display'])
        for row in run.result['suggestions']:
            for span in row['evidence_spans']:
                self.assertIn(span['text'], content)
        self.send.assert_not_called()

    def test_download_is_distinct_repeatable_and_changes_only_files_and_audit(self):
        before = {model.__name__: list(model.objects.values()) for model in (Encounter, CodingRun, CodingDecision, Job)}
        first = self.download(); self.assertEqual(first.status_code, 200)
        self.assertIn('synthetic-draft-not-approved.docx', first['Content-Disposition'])
        data = b''.join(first.streaming_content); first.file_to_stream.close()
        second = self.download(); repeated = b''.join(second.streaming_content); second.file_to_stream.close()
        self.assertEqual(data, repeated)
        self.assertEqual(self.path.read_bytes(), self.original)
        for model in (Encounter, CodingRun, CodingDecision, Job):
            self.assertEqual(before[model.__name__], list(model.objects.values()))
        self.assertEqual(AuditEvent.objects.filter(action='encounter.export_synthetic_coding_draft').count(), 2)
        files = list((self.root / 'exports/coding-draft').rglob('*.docx'))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / 'exports/coding').exists())
        self.assertEqual(texts(data).count(TITLE), 1)
        self.assertIn('CPT 99213 — provider-selected suggestion', texts(data))
        self.send.assert_not_called()

    def test_authentication_synthetic_role_and_tenant_boundaries(self):
        self.assertEqual(self.download(AnonymousUser()).status_code, 302)
        outsider = User.objects.create_user(username='draft-outsider', email='draft-outsider@synthetic.invalid', verified_at=timezone.now())
        with self.assertRaises(Http404): self.download(outsider)
        with override_settings(SYNTHETIC_ONLY=False):
            with self.assertRaises(Http404): self.download()
        member = Membership.objects.get(user=self.actor, department=self.department)
        member.role = 'employee'; member.save(update_fields=['role'])
        with self.assertRaises(PermissionDenied): self.download()
        self.assertFalse((self.root / 'exports/coding-draft').exists())

    def test_live_stale_and_original_integrity_fail_closed(self):
        changed = deepcopy(self.run)
        changed.config['mode'] = 'live'
        with patch('core.coding_draft_export.CodingRun.objects.filter') as query:
            query.return_value.first.return_value = changed
            self.assertEqual(self.download().status_code, 409)
        for field, value in [('revision', self.encounter.revision + 1), ('notes', 'Changed synthetic source.')]:
            encounter = deepcopy(self.encounter); setattr(encounter, field, value)
            with patch('core.coding_draft_export.get_object_or_404', return_value=encounter):
                self.assertEqual(self.download().status_code, 409)
        self.path.write_bytes(self.original + b'corrupt')
        self.assertEqual(self.download().status_code, 409)
        self.assertFalse(AuditEvent.objects.filter(action='encounter.export_synthetic_coding_draft').exists())

    def test_missing_evidence_withholds_invalid_span_and_cannot_create_acceptance(self):
        changed = deepcopy(self.run)
        changed.result['adapter']['diagnostics']['provider_response']['codes'][2]['evidences'][0]['text'] = 'Invented evidence'
        # Defensive parsing is tested with returned copies; immutable historical
        # results and approvals are never rewritten to manufacture this case.
        with patch('core.coding_draft_export.CodingRun.objects.filter') as query, \
                patch('core.coding_draft_export.CodingDecision.objects.filter', return_value=[]):
            query.return_value.first.return_value = changed
            _, _, rows, paragraphs = draft_review(self.encounter)
        content = '\n'.join(text for text, _ in paragraphs)
        self.assertNotIn('Invented evidence', content)
        self.assertEqual(rows[2]['valid_evidence_count'], 2)
        self.assertEqual(rows[2]['decision_status'], 'Held — excluded from approved export.')
        self.assertIn('incomplete or invalid', content)
        self.assertEqual(CodingDecision.objects.count(), 1)
        self.run.refresh_from_db()
        self.assertEqual(self.run.selection['selected_ids'], ['selected:0'])
