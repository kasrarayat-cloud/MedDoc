"""The models' own guards that the coding path relies on: an original's revision and the audit trail are immutable, and an
automated agent is labelled as one wherever its name is shown. Synthetic data only."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from studio import models
from tests.support import coding as f


class ImmutabilityTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.usr = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.usr)

    def test_revision_rows_refuse_updates_and_deletes(self):
        rev = f.paste(self.enc, self.usr, 'Synthetic note text.')
        rev.pasted_text = 'changed'
        with self.assertRaises(ValidationError):
            rev.save()
        with self.assertRaises(ValidationError):
            rev.delete()
        rev.refresh_from_db()
        self.assertEqual(rev.pasted_text, 'Synthetic note text.')

    def test_bulk_update_and_delete_are_refused_on_immutable_models(self):
        f.paste(self.enc, self.usr, 'Text.')
        models.AuditEvent.objects.create(workspace=self.ws, actor_kind='system', event='probe')
        with self.assertRaises(ValidationError):
            models.AuditEvent.objects.all().update(event='rewritten')
        with self.assertRaises(ValidationError):
            models.AuditEvent.objects.all().delete()
        self.assertEqual(models.AuditEvent.objects.get().event, 'probe')

    def test_agent_users_are_labelled(self):
        agent = models.User.objects.create_user(username='reviewbot', password='synthetic-pass-123!',
                                                actor_kind=models.User.AGENT, display_name='Reviewbot')
        self.assertIn('automated agent', agent.label())
