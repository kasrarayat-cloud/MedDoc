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


# --- release 2, R2-23: the indexes for the lists, a round's runs and the sweeps (migrations 0019 to 0021) ---------------

from django.core.management import call_command  # noqa: E402 - this section's own imports
from django.db import connection  # noqa: E402
from django.db.models import Q  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from studio import customer, jobs  # noqa: E402

R2_23_PLAN_ROWS = 20_000  # RELEASE-2-SPEC R2-23: plans read at 20,000 runs and rounds


def r2_23_index(model, name):
    return next(index for index in model._meta.indexes if index.name == name)


def r2_23_condition(index):
    """An index's condition as {lookup: value}, refusing anything but a plain AND of lookups."""
    condition = index.condition
    assert isinstance(condition, Q) and condition.connector == Q.AND and not condition.negated, condition
    assert all(isinstance(child, tuple) for child in condition.children), condition
    return dict(condition.children)


class R2IndexDeclarationTests(TestCase):
    """The five indexes are declared once, in the models, with conditions that name the code's own values - so a state, a
    purpose or a queue state added to the code without its index fails here - and the migrations hold exactly them."""

    def test_the_models_and_their_migrations_agree(self):
        call_command('makemigrations', 'studio', check=True, dry_run=True, verbosity=0)  # a difference exits 1

    def test_each_condition_names_the_codes_own_values(self):
        time, queue = (r2_23_index(models.Encounter, name) for name in ('studio_enc_ws_time', 'studio_enc_ws_queue'))
        self.assertEqual((time.fields, queue.fields), (['workspace', 'created_at', 'id'], ['workspace', 'created_at', 'id']))
        self.assertEqual(r2_23_condition(time), {'destroyed_at__isnull': True})
        self.assertEqual(r2_23_condition(queue), {'destroyed_at__isnull': True, 'state__in': list(customer.QUEUE_STATES)})
        by_round = r2_23_index(models.ProviderRun, 'studio_run_round')
        self.assertEqual([str(expression) for expression in by_round.expressions], ["F(scope__round)"])
        self.assertEqual(r2_23_condition(by_round), {'purpose__in': list(jobs.PURPOSES)})
        in_flight = r2_23_index(models.ProviderRun, 'studio_run_in_flight')
        self.assertEqual((in_flight.fields, r2_23_condition(in_flight)),
                         (['created_at'], {'state__in': [models.ProviderRun.SENDING, models.ProviderRun.RESERVED]}))
        open_rounds = r2_23_index(models.CodingRound, 'studio_round_open')
        self.assertEqual((open_rounds.fields, r2_23_condition(open_rounds)),
                         (['created_at'], {'state__in': [models.CodingRound.QUEUED, models.CodingRound.RUNNING]}))
        for index in (time, queue, by_round, in_flight, open_rounds):  # Django's own non-unique Index, nothing else
            self.assertIs(type(index), django_models.Index, index.name)

    def test_the_database_holds_each_index_as_declared(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT indexname, tablename, indexdef FROM pg_indexes WHERE indexname = ANY(%s)",
                           [['studio_enc_ws_time', 'studio_enc_ws_queue', 'studio_run_round', 'studio_run_in_flight',
                             'studio_round_open']])
            found = {name: (table, definition) for name, table, definition in cursor.fetchall()}
        self.assertEqual({name: table for name, (table, _) in found.items()}, {
            'studio_enc_ws_time': 'studio_encounter', 'studio_enc_ws_queue': 'studio_encounter',
            'studio_run_round': 'studio_providerrun', 'studio_run_in_flight': 'studio_providerrun',
            'studio_round_open': 'studio_codinground'})
        for name, (_table, definition) in found.items():
            self.assertTrue(definition.startswith('CREATE INDEX '), definition)  # never UNIQUE
        self.assertIn('(workspace_id, created_at, id) WHERE (destroyed_at IS NULL)', found['studio_enc_ws_time'][1])
        self.assertIn("ARRAY['awaiting_answer'", found['studio_enc_ws_queue'][1])
        self.assertIn("((scope -> 'round'::text))", found['studio_run_round'][1])
        self.assertIn("ARRAY['coding_reader'", found['studio_run_round'][1])
        self.assertIn("ARRAY['sending'", found['studio_run_in_flight'][1])
        self.assertIn("ARRAY['queued'", found['studio_round_open'][1])


from django.db import models as django_models  # noqa: E402 - Django's Index class, for the identity check above


class R2RunPlanTests(TestCase):
    """At 20,000 rounds and 20,000 runs: every lookup of a round's runs reads studio_run_round (studio.jobs'
    awaiting_reconcile, _reused, abandoned_outcome and the console's round_runs), and the sweep's two reads read
    studio_run_in_flight and studio_round_open - never a sequential scan of either table."""

    @classmethod
    def setUpTestData(cls):
        ws = f.workspace('Synthetic plan practice')
        by = f.member(ws)
        now = timezone.now()
        encounters = models.Encounter.objects.bulk_create(
            [models.Encounter(workspace=ws, title=f'Synthetic plan note {n}', created_by=by) for n in range(200)])
        revisions = models.SourceRevision.objects.bulk_create(
            [models.SourceRevision(encounter=enc, number=1, kind=models.SourceRevision.PASTE, pasted_text='Synthetic.',
                                   synthetic_attested_by=by, synthetic_attested_at=now, created_by=by)
             for enc in encounters])
        per = R2_23_PLAN_ROWS // len(encounters)
        rounds = models.CodingRound.objects.bulk_create(
            [models.CodingRound(encounter=enc, revision=rev, number=number, trigger=models.CodingRound.UPLOAD,
                                context={}, state=models.CodingRound.DONE if number > 1 or n % 50 else
                                models.CodingRound.RUNNING)
             for n, (enc, rev) in enumerate(zip(encounters, revisions)) for number in range(1, per + 1)],
            batch_size=5000)
        runs = []
        for index, round_ in enumerate(rounds):
            purpose = (jobs.READER, jobs.CHECKER, models.ProviderRun.PRIMARY)[index % 3]
            run_state = models.ProviderRun.SUCCEEDED if index % 400 else models.ProviderRun.SENDING
            runs.append(models.ProviderRun(
                encounter_id=round_.encounter_id, revision_id=round_.revision_id, provider='fable',
                adapter_version='synthetic@1', request_sha256='0' * 64, request_body={}, contexts={},
                state=run_state, purpose=purpose, scope={'round': str(round_.pk)} if purpose != 'primary' else {}))
        models.ProviderRun.objects.bulk_create(runs, batch_size=5000)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE studio_providerrun')
            cursor.execute('ANALYZE studio_codinground')
        cls.round = rounds[len(rounds) // 2]

    def plan(self, sql):
        with connection.cursor() as cursor:
            cursor.execute('EXPLAIN ' + sql)
            return '\n'.join(row[0] for row in cursor.fetchall())

    def reads(self, call, table):
        with CaptureQueriesContext(connection) as seen:
            call()
        return [item['sql'] for item in seen.captured_queries if f'FROM "{table}"' in item['sql']]

    def test_every_lookup_of_a_rounds_runs_reads_studio_run_round(self):
        self.assertEqual(models.ProviderRun.objects.count(), R2_23_PLAN_ROWS)
        round_ = self.round
        for name, call in (('awaiting_reconcile', lambda: jobs.awaiting_reconcile(round_)),
                           ('_reused', lambda: jobs._reused(round_, jobs.READER)),
                           ('abandoned_outcome', lambda: jobs.abandoned_outcome(round_)),
                           ('operator.round_runs', lambda: operator.round_runs(round_))):
            with self.subTest(lookup=name):
                found = self.reads(call, 'studio_providerrun')
                self.assertEqual(len(found), 1, found)
                self.assertIn(""""scope" -> 'round'""", found[0])
                plan = self.plan(found[0])
                self.assertIn('studio_run_round', plan)
                self.assertNotIn('Seq Scan on studio_providerrun', plan)

    def test_the_sweeps_reads_use_their_partial_indexes(self):
        found_runs = self.reads(jobs.mark_stale, 'studio_providerrun')
        found_rounds = self.reads(jobs.mark_stale, 'studio_codinground')
        sweeps = {'sending': [sql for sql in found_runs if """"state" = 'sending'""" in sql],
                  'reserved': [sql for sql in found_runs if """"state" = 'reserved'""" in sql],
                  'open rounds': [sql for sql in found_rounds if '"state" IN (' in sql]}
        for name, index, table in (('sending', 'studio_run_in_flight', 'studio_providerrun'),
                                   ('reserved', 'studio_run_in_flight', 'studio_providerrun'),
                                   ('open rounds', 'studio_round_open', 'studio_codinground')):
            with self.subTest(sweep=name):
                self.assertEqual(len(sweeps[name]), 1, sweeps)
                plan = self.plan(sweeps[name][0])
                self.assertIn(index, plan)
                self.assertNotIn(f'Seq Scan on {table}', plan)
