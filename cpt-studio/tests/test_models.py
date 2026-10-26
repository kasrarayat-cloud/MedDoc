from django.core.exceptions import ValidationError
from django.test import TestCase

from studio import models
from studio.types import ExtractionResult
from tests.support import factories as f


class ImmutabilityTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.usr = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.usr)

    def test_revision_rows_refuse_updates_and_deletes(self):
        rev = f.pasted_revision(self.enc, self.usr, 'Synthetic note text.')
        rev.text = 'changed'
        with self.assertRaises(ValidationError):
            rev.save()
        with self.assertRaises(ValidationError):
            rev.delete()
        rev.refresh_from_db()
        self.assertEqual(rev.text, 'Synthetic note text.')

    def test_extraction_is_recorded_exactly_once(self):
        rev = f.pasted_revision(self.enc, self.usr, 'First text.', extract=False)
        f.record(rev, ExtractionResult(status='ok', method='paste', text='First text.'))
        with self.assertRaises(ValidationError):
            f.record(rev, ExtractionResult(status='ok', method='paste', text='Second text.'))
        rev.refresh_from_db()
        self.assertEqual(rev.text, 'First text.')

    def test_extraction_must_finish_in_a_final_state(self):
        rev = f.pasted_revision(self.enc, self.usr, 'Text.', extract=False)
        with self.assertRaises(ValidationError):
            models.SourceRevision.record_extraction(rev.pk, extraction_status='pending')

    def test_bulk_update_and_delete_are_refused_on_immutable_models(self):
        f.pasted_revision(self.enc, self.usr, 'Text.')
        models.AuditEvent.objects.create(workspace=self.ws, actor_kind='system', event='probe')
        with self.assertRaises(ValidationError):
            models.AuditEvent.objects.all().update(event='rewritten')
        with self.assertRaises(ValidationError):
            models.AuditEvent.objects.all().delete()
        self.assertEqual(models.AuditEvent.objects.get().event, 'probe')

    def test_agent_users_are_labelled(self):
        agent = f.user('reviewbot', actor_kind=models.User.AGENT)
        self.assertIn('automated agent', agent.label())
