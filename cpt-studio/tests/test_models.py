"""The models' own guards that the coding path relies on: an original's revision and the audit trail are immutable, and an
automated agent is labelled as one wherever its name is shown. Synthetic data only."""
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from studio import audit, models, operator
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


class ReleaseOneRecordTests(TestCase):
    """Release 1's record tables (RELEASE-1-SPEC 3.1): the read trail, the security events and the disposal ledger are
    append-only, and every id in them is a plain value - never a foreign key - so the trail outlives a practice's PHI."""

    def setUp(self):
        self.ws = f.workspace()
        self.usr = f.member(self.ws)

    def rows(self):
        return {
            models.AccessRecord: models.AccessRecord.objects.create(
                host='cpt', view='member.detail', actor_id=self.usr.pk, actor_kind='human', actor_role='reviewer',
                workspace_id=self.ws.pk, encounter_ids=[str(uuid.uuid4())], outcome=models.AccessRecord.SERVED),
            models.SecurityEvent: models.SecurityEvent.objects.create(event='probe.recorded', actor_id=self.usr.pk),
            models.DisposalEvent: models.DisposalEvent.objects.create(
                stage=models.DisposalEvent.PLANNED, scope=models.DisposalEvent.DOCUMENT, workspace_id=self.ws.pk),
        }

    def test_the_record_tables_refuse_updates_and_deletes(self):
        for model, row in self.rows().items():
            with self.subTest(model=model.__name__):
                self.assertTrue(issubclass(model, models.ImmutableModel))
                field = 'view' if model is models.AccessRecord else ('event' if model is models.SecurityEvent
                                                                     else 'stage')
                before = getattr(row, field)
                setattr(row, field, 'rewritten')
                with self.assertRaises(ValidationError):
                    row.save()
                with self.assertRaises(ValidationError):
                    row.delete()
                with self.assertRaises(ValidationError):
                    model.objects.all().update(**{field: 'rewritten'})
                with self.assertRaises(ValidationError):
                    model.objects.all().delete()
                self.assertEqual(getattr(model.objects.get(pk=row.pk), field), before)

    def test_the_record_tables_hold_ids_never_foreign_keys(self):
        for model in (models.AccessRecord, models.SecurityEvent, models.DisposalEvent, models.FileKey):
            with self.subTest(model=model.__name__):
                related = [field.name for field in model._meta.get_fields() if field.is_relation]
                self.assertEqual(related, [])

    def test_an_older_release_s_inserts_leave_the_new_columns_empty(self):
        # what the revision before release 1 writes during the blue/green switch (RELEASE-1-SPEC 2.1): it names none of
        # the new columns, so every one is NULL and none refuses the row
        attempt = models.LoginAttempt.objects.create(username='someone', client='192.0.2.1', succeeded=False)
        event = audit.record(self.ws, 'probe.recorded', actor=self.usr)
        grant, _ = operator.grant(f.user('synthetic-operator'), 'Synthetic test grant for the schema check.', 'tests')
        enc = f.encounter(self.ws, self.usr)
        for row, columns in ((attempt, ('door', 'outcome', 'sign_in_ref')),
                             (event, ('client', 'sign_in_ref', 'request_id')),
                             (grant, ('authorization_ref', 'review_by')),
                             (self.usr, ('password_change_required_at', 'password_changed_at')),
                             (self.ws, ('closed_at',)), (enc, ('destroyed_at',))):
            stored = type(row).objects.filter(pk=row.pk).values(*columns).get()
            for column in columns:
                with self.subTest(table=type(row).__name__, column=column):
                    self.assertIsNone(stored[column])

    def test_one_rate_window_per_scope_key_and_start_and_one_file_key_per_workspace(self):
        start = timezone.now().replace(microsecond=0)
        models.RateWindow.objects.create(scope='probe', key='203.0.113.9', window_start=start, count=1, last_at=start)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.RateWindow.objects.create(scope='probe', key='203.0.113.9', window_start=start, count=1,
                                             last_at=start)
        models.FileKey.objects.create(workspace_id=self.ws.pk, wrapped_key=b'synthetic')
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.FileKey.objects.create(workspace_id=self.ws.pk, wrapped_key=b'synthetic')
