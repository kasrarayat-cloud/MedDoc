"""Release 1, D1: destroying one document or a whole practice's data (studio.disposal and the dispose command), and the
closed practice it starts from. Synthetic practices only, on a test database and an originals folder of the tests' own;
nothing here can reach another database or folder."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import audit, disposal, intake, jobs, maintenance, models, storage
from studio.fable import document as fable_document
from tests.support import coding as f
from tests.support import rounds

Round, Job, Event = models.CodingRound, models.Job, models.DisposalEvent
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
DOCX_BYTES = b'PK\x03\x04 synthetic word bytes, never opened by the tests'
CONVERTED = b'%PDF-1.7\n% the synthetic conversion of a Word file\n%%EOF\n'
MARKERS = ('ZZ-TITLE-MARKER', 'ZZ-TEXT-MARKER', 'ZZ-ANSWER-MARKER', 'zz-file-marker')  # what must never be printed


def close(workspace):
    models.Workspace.objects.filter(pk=workspace.pk).update(closed_at=timezone.now())


class ClosedPracticeTests(rounds.CustomerCase, TestCase):
    """D1 step 1: a closed practice takes no new upload and starts no coding; reading stays on."""

    def files(self):
        return sorted(path for path in Path(self._originals.name).rglob('*') if path.is_file())

    def test_an_upload_to_a_closed_practice_is_refused_and_stores_nothing(self):
        close(self.ws)
        client, before = self.client_for(self.reviewer), self.files()
        for fields in ({'text': f.NOTE}, {'file': SimpleUploadedFile('synthetic.pdf', f.PDF_BYTES)}):
            with self.subTest(fields=sorted(fields)):
                answer = client.post('/api/encounters', {**fields, 'synthetic_attestation': 'yes'})
                self.assertEqual((answer.status_code, answer.json()['error']), (400, intake.CLOSED_TEXT))
        self.assertFalse(models.Encounter.objects.exists())
        self.assertEqual(self.files(), before)

    def test_reading_stays_on_in_a_closed_practice(self):
        enc = self.done()
        close(self.ws)
        client = self.client_for(self.reviewer)
        self.assertEqual(client.get(f'/api/encounters/{enc.pk}').status_code, 200)
        self.assertEqual(client.get(f'/api/encounters/{enc.pk}/original').content, f.PDF_BYTES)
        self.assertIn(str(enc.pk), json.dumps(client.get('/api/encounters').json()))

    def test_no_coding_starts_in_a_closed_practice(self):
        failed = self.encounter()
        rounds.write_round(failed, state_=Round.FAILED, failure_kind='failed', error='Coding did not finish.')
        stopped = self.started(title='Synthetic stopped note')
        jobs.stop_encounter(stopped, self.reviewer)
        close(self.ws)
        for label, act in (('a new round', lambda: jobs.start_round(failed, failed.current_revision, Round.ANSWERS,
                                                                    self.reviewer)),
                           ('a retry', lambda: jobs.retry(failed, self.reviewer)),
                           ('a resume', lambda: jobs.resume(stopped, self.reviewer))):
            with self.subTest(act=label):
                with self.assertRaisesMessage(jobs.Refused, jobs.CLOSED_MESSAGE):
                    act()
        self.assertFalse(Job.objects.filter(state=Job.QUEUED).exists())

    def test_a_job_queued_before_the_close_never_starts_and_nothing_is_sent(self):
        enc = self.started()
        close(self.ws)
        fake = self.use(f.FakeCoder())  # any send would fail the test: no answer is expected
        job = jobs.claim_next()
        self.assertEqual((job.state, job.error), (Job.CANCELLED, jobs.CLOSED_JOB_ERROR))
        self.assertEqual(models.CodingRound.objects.get(encounter=enc).state, Round.CANCELLED)
        self.assertEqual((fake.calls, fake.counts), ([], []))
        self.assertFalse(models.ProviderRun.objects.exists())
        self.assertIsNone(jobs.claim_next())

    def test_an_open_practice_uploads_and_codes_as_before(self):
        client = self.client_for(self.reviewer)
        answer = client.post('/api/encounters', {'text': f.NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(answer.status_code, 201)
        enc = models.Encounter.objects.get(pk=answer.json()['id'])
        self.code_round(enc)
        self.assertEqual(models.CodingRound.objects.get(encounter=enc).state, Round.DONE)



# --- shared helpers ------------------------------------------------------------------------------------------------------

@contextmanager
def installer_idle():
    """The installer's answer that no install or switch-back is under way (disposal.switch_in_progress)."""
    with mock.patch.object(disposal, 'switch_in_progress', return_value=''):
        yield


def reason_file(folder, text='Synthetic: the practice ended its contract and chose destruction in writing.'):
    path = Path(folder) / f'reason-{uuid.uuid4().hex}.txt'
    path.write_text(text, encoding='utf-8')
    return str(path)


def snapshot():
    """Every row of every table, by table and primary key: what "untouched" is measured against."""
    out = {}
    for model in apps.get_models():
        out[model._meta.db_table] = {row[model._meta.pk.attname]: row for row in model._base_manager.values()}
    return out


def changed_rows(before, after) -> set:
    """(table, pk) of every row added, removed or changed between two snapshots."""
    found = set()
    for table in set(before) | set(after):
        old, new = before.get(table, {}), after.get(table, {})
        for pk in set(old) | set(new):
            if old.get(pk) != new.get(pk):
                found.add((table, pk))
    return found


def folder_digests(workspace_id) -> dict:
    folder = storage.workspace_folder(workspace_id)
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.glob('*'))
            if path.is_file()}


def legacy(enc, user, marker):
    """One row of every table of the earlier system, tied to ``enc``, in the shapes those tables take - with the cycles
    the disposal must break (an addendum revision answering a clarification answered by it; a context naming an earlier
    assessment; the encounter pointing at its context and assessment) and the holds its runs set, released."""
    rev, now = enc.current_revision, timezone.now()
    run = models.ProviderRun.objects.create(encounter=enc, revision=rev, provider='synthetic', adapter_version='legacy@1',
                                            request_sha256='0' * 64, request_body={'text': f'ZZ-TEXT-MARKER {marker}'},
                                            contexts=[], state=models.ProviderRun.SUCCEEDED)
    exchange = models.ProviderExchange.objects.create(run=run, turn=1, request_body={}, request_sha256='1' * 64,
                                                      state='succeeded')
    models.ToolCall.objects.create(exchange=exchange, call_id='call-1', tool='synthetic', arguments={}, result={},
                                   result_sha256='2' * 64, executed_at=now)
    inventory = models.EventInventory.objects.create(
        encounter=enc, revision=rev, provider_run=run, interpretation_version='v', inventory_version='v',
        text_sha256='3' * 64, request_sha256='3' * 64, response_sha256='3' * 64, state='read', events={},
        encounter_facts={}, open_questions={}, verification={}, sha256='4' * 64)
    context = models.EncounterContext.objects.create(encounter=enc, revision=rev, facts={}, version='v',
                                                     sha256='5' * 64, event_inventory=inventory)
    routing = models.RoutingRun.objects.create(revision=rev, version='v', result={}, sha256='6' * 64)
    assessment = models.Assessment.objects.create(encounter=enc, revision=rev, context=context, routing=routing,
                                                  provider_run=run, profiles_version='v', engine_version='v',
                                                  sha256='7' * 64, event_inventory=inventory)
    models.EncounterContext.objects.create(encounter=enc, revision=rev, facts={}, version='v', sha256='5' * 64,
                                           earlier_assessment=assessment)
    proposal = models.Proposal.objects.create(assessment=assessment, key='k1', bucket='selected', code='45385',
                                              code_kind='cpt', family='f', profile_version='v', status='ready',
                                              fingerprint='8' * 64)
    answer = models.MemberAnswer.objects.create(encounter=enc, revision=rev, assessment=assessment, fact='f',
                                                value='not_documented', answered_by=user)
    models.MemberAnswerRevocation.objects.create(answer=answer, reason='withdrawn', revoked_by=user)
    clarification = models.Clarification.objects.create(encounter=enc, assessment=assessment, proposal=proposal,
                                                        scope='proposal', fact='f', question='Synthetic question?',
                                                        reason='r', answer=answer)
    addendum = models.SourceRevision.objects.create(
        encounter=enc, number=rev.number + 1, kind=models.SourceRevision.ADDENDUM, parent=rev,
        addendum_text=f'ZZ-TEXT-MARKER addendum {marker}', answers_clarification=clarification,
        synthetic_attested_by=user, synthetic_attested_at=now, created_by=user)
    models.Clarification.objects.filter(pk=clarification.pk).update(answered_by_revision=addendum)
    models.FindingConfirmation.objects.create(encounter=enc, revision=rev, clarification=clarification, scope='proposal',
                                              fact='f', family='f', value='v', spans=[], confirmed_by=user,
                                              attestation='a')
    decision = models.Decision.objects.create(encounter=enc, assessment=assessment, revision=rev, proposal=proposal,
                                              action='approve', reviewer=user, reviewer_kind='human',
                                              profile_version='v', proposal_fingerprint='8' * 64)
    models.DecisionInvalidation.objects.create(decision=decision, reason='r', by_revision=addendum, by_context=context)
    models.ReportArtifact.objects.create(encounter=enc, assessment=assessment, kind='draft', fmt='pdf',
                                         filename='legacy.pdf', content=b'%PDF-1.7 legacy report', sha256='9' * 64,
                                         snapshot_sha256='9' * 64, generated_by=user)
    hold = models.InterpreterHold.objects.create(reason='auth', run=run)
    models.InterpreterHoldRelease.objects.create(hold=hold, released_by=user, note='Synthetic release.')
    provider_hold = models.ProviderHold.objects.create(provider='synthetic', reason='auth', run=run)
    models.ProviderHoldRelease.objects.create(hold=provider_hold, released_by=user, note='Synthetic release.')
    models.Encounter.objects.filter(pk=enc.pk).update(current_context=context, current_assessment=assessment)
    return run


class PracticeCase(rounds.CustomerCase):
    """Two synthetic practices with full data: A (self.ws) and B (self.other_ws). Each has a coded PDF document with
    decisions, answers, a second round and a report, a coded Word document with its converted PDF, one row of every
    table of the earlier system, an orphan file in its folder, sign-in rows and a live session. A's reviewer is also a
    member of B, so that account keeps its other access when A is destroyed."""

    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, role=models.Membership.OWNER)
        models.Membership.objects.create(user=self.reviewer, workspace=self.other_ws, role=models.Membership.REVIEWER)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)

    def seed_practice(self, ws, member, marker):
        enc = f.encounter(ws, member, service_date='2026-11-02', insurance='medicare',
                          title=f'ZZ-TITLE-MARKER {marker} note')
        f.upload(enc, member, data=f.PDF_BYTES + marker.encode(), filename=f'zz-file-marker-{marker}.pdf')
        audit.record(ws, 'encounter.created', encounter=enc, actor=member, kind='upload')
        jobs.start_round(enc, enc.current_revision, Round.UPLOAD, member)
        self.code_round(enc)
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve', user=member).status_code, 201)
        client = self.client_for(member)
        question = client.get(f'/api/encounters/{enc.pk}').json()['questions'][0]['id']
        answered = client.post(f'/api/encounters/{enc.pk}/answers', json.dumps(
            {'answers': [{'question_id': question, 'text': f'ZZ-ANSWER-MARKER {marker}'}]}),
            content_type='application/json')
        self.assertEqual(answered.status_code, 201)
        self.code_round(enc)
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve', user=member).status_code, 201)
        report = client.post(f'/api/encounters/{enc.pk}/reports', json.dumps({'kind': 'draft', 'fmt': 'pdf', 'round': 2}),
                             content_type='application/json')
        self.assertEqual(report.status_code, 201)
        word = f.encounter(ws, member, title=f'ZZ-TITLE-MARKER {marker} word')
        f.upload(word, member, data=DOCX_BYTES + marker.encode(), filename=f'zz-file-marker-{marker}.docx',
                 media_type=DOCX)
        jobs.start_round(word, word.current_revision, Round.UPLOAD, member)
        with mock.patch.object(fable_document, 'convert_docx', return_value=CONVERTED + marker.encode()):
            self.code_round(word)
        legacy(enc, member, marker)
        storage.store_original(ws.pk, b'%PDF-1.7 an upload that failed before release 1 %%EOF', 'orphan.pdf')
        for name in (member.username, member.username.upper()):
            models.LoginAttempt.objects.create(username=name, client='192.0.2.20', succeeded=False)
        self.client_for(member)  # a live session
        return enc, word

    def seed(self):
        self.a_note, self.a_word = self.seed_practice(self.ws, self.owner, 'A')
        self.b_note, self.b_word = self.seed_practice(self.other_ws, self.outsider, 'B')
        for user in (self.reviewer, self.viewer, self.agent):
            self.client_for(user)
        models.LoginAttempt.objects.create(username=self.viewer.username, client='192.0.2.21', succeeded=True)

    def command(self, *args):
        out = io.StringIO()
        call_command('dispose', *args, stdout=out)
        return out.getvalue()

    def close_and_plan(self, ws=None):
        ws = ws or self.ws
        self.command('--close', '--workspace', str(ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.scratch.name))
        self.command('--plan', '--workspace', str(ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.scratch.name))
        return Event.objects.filter(stage=Event.PLANNED).latest('created_at')

    def execute(self, plan, by='Synthetic Operator', approved='Synthetic Approver'):
        with installer_idle():
            return self.command('--execute', '--plan', str(plan.pk), '--by', by, '--approved-by', approved,
                                '--authorization-ref', 'docs/foundation/mutations/synthetic-disposal.md@0000000')


# --- the model graph -------------------------------------------------------------------------------------------------------

class ModelGraphTests(SimpleTestCase):
    TARGETS = (models.Encounter, models.SourceRevision, models.ProviderRun)

    @staticmethod
    def forward(model):
        return [fk.related_model for fk in model._meta.concrete_fields if fk.many_to_one or fk.one_to_one]

    def reaches(self, model) -> bool:
        seen, todo = set(), [model]
        while todo:
            current = todo.pop()
            for target in self.forward(current):
                if target in self.TARGETS:
                    return True
                if target not in seen:
                    seen.add(target)
                    todo.append(target)
        return False

    def test_every_model_with_a_path_to_the_phi_tables_is_destroyed_or_kept_by_name(self):
        listed = {model for model, _ in disposal.DISPOSAL_TABLES} | set(disposal.KEPT_MODELS)
        reaching = {model for model in apps.get_models() if self.reaches(model)}
        self.assertTrue(reaching)  # the control: the walk finds the graph
        self.assertEqual(sorted(model.__name__ for model in reaching - listed), [])
        disposed = [model for model, _ in disposal.DISPOSAL_TABLES]
        self.assertEqual(len(disposed), len(set(disposed)))
        self.assertEqual(set(disposed) & set(disposal.KEPT_MODELS), set())  # a table is destroyed or kept, never both

    def test_every_path_leads_to_the_encounter(self):
        for model, path in disposal.DISPOSAL_TABLES:
            with self.subTest(model=model.__name__):
                current = model
                for name in path.split('__'):
                    current = current._meta.get_field(name).related_model
                self.assertIs(current, models.Encounter)

    def test_children_come_before_their_parents_except_inside_a_cycle(self):
        order = [model for model, _ in disposal.DISPOSAL_TABLES]
        for index, model in enumerate(order):
            for parent in self.forward(model):
                if parent in order and parent is not model and model not in self.forward(parent):
                    with self.subTest(child=model.__name__, parent=parent.__name__):
                        self.assertLess(index, order.index(parent))


class DeferredKeyTests(TestCase):
    def test_the_foreign_keys_the_disposal_relies_on_are_deferred(self):
        # one transaction deletes parents and children in an order cycles prevent from being strict: the database checks
        # every foreign key once, at SET CONSTRAINTS ALL IMMEDIATE, only because Django made them all deferred
        with connection.cursor() as cursor:
            cursor.execute("SELECT conname, condeferrable, condeferred FROM pg_constraint WHERE contype = 'f' AND "
                           "conrelid::regclass::text LIKE 'studio_%%'")
            rows = cursor.fetchall()
        self.assertGreater(len(rows), 40)
        self.assertEqual([name for name, deferrable, deferred in rows if not (deferrable and deferred)], [])


# --- destroying a whole practice -----------------------------------------------------------------------------------------

class PracticeDisposalTests(PracticeCase, TestCase):
    def test_one_practice_destroyed_and_the_other_byte_identical(self):
        self.seed()
        plan = self.close_and_plan()
        scope = disposal.workspace_scope(self.ws.pk)
        in_scope = {(model._meta.db_table, pk) for model, _ in disposal.DISPOSAL_TABLES
                    for pk in disposal.scope_rows(model, scope).values_list('pk', flat=True)}
        for model, _ in disposal.DISPOSAL_TABLES:  # the control: every listed table holds rows of A to destroy
            with self.subTest(seeded=model.__name__):
                self.assertTrue(disposal.scope_rows(model, scope).exists())
        closing = [self.owner, self.viewer, self.agent]  # the reviewer keeps B
        logins = {(models.LoginAttempt._meta.db_table, pk) for pk in models.LoginAttempt.objects.filter(
            username__in=[name for user in closing for name in (user.username, user.username.upper())])
            .values_list('pk', flat=True)}
        sessions = {('django_session', session.session_key) for session in Session.objects.all()
                    if str(session.get_decoded().get('_auth_user_id')) in {str(user.pk) for user in closing}}
        self.assertTrue(logins and sessions)
        b_files, before = folder_digests(self.other_ws.pk), snapshot()
        output = self.execute(plan)
        after = snapshot()
        completed = Event.objects.get(stage=Event.COMPLETED)
        expected = (in_scope | logins | sessions | {(models.DisposalEvent._meta.db_table, completed.pk)}
                    | {(models.Encounter._meta.db_table, pk) for pk in scope.encounter_ids}
                    | {(models.Membership._meta.db_table, pk) for pk in models.Membership.objects.filter(
                        workspace=self.ws).values_list('pk', flat=True)}
                    | {(models.User._meta.db_table, user.pk) for user in closing})
        self.assertEqual(changed_rows(before, after), expected)  # nothing outside the scope moved
        self.assertEqual(folder_digests(self.other_ws.pk), b_files)  # B's files byte-identical
        self.assertFalse(storage.workspace_folder(self.ws.pk).exists())  # A's files and folder gone
        for model, _ in disposal.DISPOSAL_TABLES:
            self.assertFalse(disposal.scope_rows(model, scope).exists())
        for pk in scope.encounter_ids:  # the tombstones
            tomb = models.Encounter.objects.get(pk=pk)
            self.assertEqual((tomb.title, tomb.user_values, tomb.current_revision_id, tomb.current_context_id,
                              tomb.current_assessment_id, tomb.state), ('', {}, None, None, None, 'destroyed'))
            self.assertIsNotNone(tomb.destroyed_at)
        self.assertTrue(models.AuditEvent.objects.filter(workspace=self.ws).exists())  # kept (D25), unchanged above
        for user in closing:
            user.refresh_from_db()
            self.assertFalse(user.is_active or user.has_usable_password())
        self.reviewer.refresh_from_db()
        self.assertTrue(self.reviewer.is_active and self.reviewer.has_usable_password())
        hashed = maintenance.hashed_signin_name(self.owner.username)
        self.assertEqual(models.LoginAttempt.objects.filter(username=hashed).count(), 2)
        self.assertEqual(sorted(Event.objects.values_list('stage', flat=True)),
                         sorted([Event.CLOSED, Event.PLANNED, Event.COMPLETED]))
        self.assertEqual((completed.run_by, completed.approved_by, completed.scope, completed.workspace_id),
                         ('Synthetic Operator', 'Synthetic Approver', Event.WORKSPACE, self.ws.pk))
        self.assertEqual(completed.counts['deleted'], plan.counts['rows'])
        self.assertEqual((completed.files['files'], completed.files['deleted'], completed.files['remaining']),
                         (plan.files['files'], plan.files['files'], 0))
        self.assertEqual(completed.notes, f'plan={plan.pk}; vacuum=skipped')  # a test case runs in a transaction
        self.assertIn('CPT Studio destruction certificate', output)
        for text in disposal.CANNOT_REACH:
            self.assertIn(text, output)
        rows = json.dumps(list(Event.objects.values()), default=str)
        for marker in MARKERS:  # no PHI in the certificate or the ledger rows
            self.assertNotIn(marker, output)
            self.assertNotIn(marker, rows)

    def test_the_practice_keeps_reading_until_it_is_destroyed_and_then_reads_nothing(self):
        self.seed()
        plan = self.close_and_plan()
        owner = self.client_for(self.owner)
        self.assertEqual(owner.get(f'/api/encounters/{self.a_note.pk}').status_code, 200)  # closed, still readable
        self.execute(plan)
        self.assertEqual(owner.get(f'/api/encounters/{self.a_note.pk}').status_code, 401)  # its session ended
        self.assertFalse(self.client.login(username=self.owner.username, password='synthetic-pass-123!'))

    def test_a_plan_writes_its_counts_and_manifest_and_changes_nothing(self):
        self.seed()
        self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.scratch.name))
        before = snapshot()
        output = self.command('--plan', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                              '--reason-file', reason_file(self.scratch.name))
        plan = Event.objects.get(stage=Event.PLANNED)
        self.assertEqual(changed_rows(before, snapshot()), {(Event._meta.db_table, plan.pk)})
        self.assertEqual(plan.counts['rows'], disposal.row_counts(disposal.workspace_scope(self.ws.pk)))
        self.assertEqual(plan.manifest_digest, disposal.manifest_digest(disposal.plan_manifest(plan)))
        on_disk = [path for path in storage.workspace_folder(self.ws.pk).iterdir() if path.is_file()]
        self.assertEqual(len(on_disk), 4)  # the two originals, the Word document's converted PDF, the orphan
        self.assertEqual(plan.files, {'files': 4, 'bytes': sum(path.stat().st_size for path in on_disk), 'missing': 0})
        self.assertIn(plan.manifest_digest, output)
        for marker in MARKERS:
            self.assertNotIn(marker, output)


# --- the refusals ----------------------------------------------------------------------------------------------------------

class RefusalTests(PracticeCase, TestCase):
    def setUp(self):
        super().setUp()
        self.seed()

    def refused(self, *args, expect):
        """The command refuses with ``expect`` in its sentence and changes nothing."""
        before = snapshot()
        with self.assertRaises(CommandError) as raised:
            self.command(*args)
        self.assertIn(expect, str(raised.exception))
        self.assertEqual(changed_rows(before, snapshot()), set())
        return raised.exception

    def plan_args(self, **scope):
        key, value = next(iter(scope.items()))
        return ['--plan', f'--{key}', str(value), '--by', 'Synthetic Operator', '--reason-file',
                reason_file(self.scratch.name)]

    def execute_args(self, plan, by='Synthetic Operator', approved='Synthetic Approver'):
        return ['--execute', '--plan', str(plan.pk), '--by', by, '--approved-by', approved,
                '--authorization-ref', 'docs/foundation/mutations/synthetic-disposal.md@0000000']

    def test_a_practice_that_was_not_closed_is_not_planned(self):
        self.refused(*self.plan_args(workspace=self.ws.pk), expect='was not closed first')

    def test_the_same_person_cannot_run_and_approve(self):
        plan = self.close_and_plan()
        with installer_idle():
            self.refused(*self.execute_args(plan, by='Synthetic Operator', approved=' synthetic  OPERATOR '),
                         expect='two different people')

    def test_a_destruction_during_an_install_or_switch_back_is_refused(self):
        plan = self.close_and_plan()
        for state, expect in ((None, 'did not say that no install'), ('switching', 'is under way')):
            with self.subTest(state=state):
                environment = {} if state is None else {disposal.SWITCH_STATE_VARIABLE: state}
                with mock.patch.dict(os.environ, environment, clear=False):
                    if state is None:
                        os.environ.pop(disposal.SWITCH_STATE_VARIABLE, None)
                    self.refused(*self.execute_args(plan), expect=expect)
        with mock.patch.dict(os.environ, {disposal.SWITCH_STATE_VARIABLE: disposal.SWITCH_IDLE}):
            self.assertEqual(disposal.switch_in_progress(), '')  # only the installer's 'idle' lets it run

    def test_a_stale_plan_is_refused(self):
        plan = self.close_and_plan()
        later = SimpleNamespace(now=lambda: timezone.now() + disposal.PLAN_MAX_AGE + timedelta(minutes=1))
        with installer_idle(), mock.patch.object(disposal, 'timezone', later):
            self.refused(*self.execute_args(plan), expect='older than 24 hours')
        models.CodingAnswer.objects.create(encounter=self.a_note, round=Round.objects.filter(encounter=self.a_note)
                                           .latest('number'), question='Synthetic?', answer='A new answer.',
                                           answered_by=self.owner)
        with installer_idle():
            self.refused(*self.execute_args(plan), expect='The plan is stale')

    def test_a_plan_whose_files_changed_is_refused(self):
        plan = self.close_and_plan()
        name = self.a_note.files.get().storage_name
        storage.stored_path(name).write_bytes(b'%PDF-1.7 changed after the plan %%EOF')
        with installer_idle():
            self.refused(*self.execute_args(plan), expect='The plan is stale')

    def test_open_work_in_scope_is_refused(self):
        self.started(title='Synthetic queued note')  # a queued job and round of A
        self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.scratch.name))
        self.refused(*self.plan_args(workspace=self.ws.pk), expect='job(s) are queued or running')

    def test_a_standing_hold_set_by_a_run_in_scope_is_refused(self):
        run = models.ProviderRun.objects.filter(encounter=self.a_note).first()
        models.InterpreterHold.objects.create(reason='quota', run=run)
        self.refused(*self.plan_args(encounter=self.a_note.pk), expect='coding hold(s) set by its runs still stand')

    def test_a_row_outside_the_scope_that_refers_to_it_is_refused(self):
        inside = models.ProviderRun.objects.filter(encounter=self.a_note).first()
        outside = models.ProviderRun.objects.filter(encounter=self.a_word).first()
        models.ProviderRun.objects.filter(pk=outside.pk).update(reused_from=inside)
        self.refused(*self.plan_args(encounter=self.a_note.pk),
                     expect='row(s) of studio_providerrun outside the scope refer to it through reused_from_id')

    def test_a_file_in_scope_named_outside_it_is_refused(self):
        name = self.a_note.files.get().storage_name
        Round.objects.filter(encounter=self.a_word).update(view_pdf_storage_name=name)
        self.refused(*self.plan_args(encounter=self.a_note.pk), expect='also named by a row outside the scope')

    def test_a_plan_is_carried_out_once(self):
        plan = self.close_and_plan()
        self.execute(plan)
        with installer_idle():
            self.refused(*self.execute_args(plan), expect='already carried out')

    def test_a_destroyed_document_is_not_planned_again(self):
        self.command(*self.plan_args(encounter=self.a_note.pk))
        self.execute(Event.objects.get(stage=Event.PLANNED))
        self.refused(*self.plan_args(encounter=self.a_note.pk), expect='already destroyed')

    def test_a_closed_practice_is_not_closed_again(self):
        self.command('--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.scratch.name))
        self.refused('--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.scratch.name), expect='already closed')


# --- destroying one misfiled document --------------------------------------------------------------------------------------

class DocumentDisposalTests(PracticeCase, TestCase):
    def test_one_document_is_destroyed_and_everything_else_is_untouched(self):
        self.seed()
        output = self.command('--plan', '--encounter', str(self.a_note.pk), '--by', 'Synthetic Operator',
                              '--reason-file', reason_file(self.scratch.name, 'Synthetic: uploaded to the wrong practice.'))
        self.assertIn(disposal.MISFILED_REMINDER, output)
        plan = Event.objects.get(stage=Event.PLANNED)
        scope = disposal.document_scope(self.a_note.pk)
        in_scope = {(model._meta.db_table, pk) for model, _ in disposal.DISPOSAL_TABLES
                    for pk in disposal.scope_rows(model, scope).values_list('pk', flat=True)}
        names = disposal.scope_files(scope)
        self.assertEqual(len(names), 1)  # its original (a PDF has no converted copy)
        before, word_files = snapshot(), folder_digests(self.ws.pk)
        output = self.execute(plan)
        completed = Event.objects.get(stage=Event.COMPLETED)
        self.assertEqual(changed_rows(before, snapshot()),
                         in_scope | {(Event._meta.db_table, completed.pk), (models.Encounter._meta.db_table, self.a_note.pk)})
        word_files.pop(names[0].split('/')[1])
        self.assertEqual(folder_digests(self.ws.pk), word_files)  # the practice's other files, byte for byte
        self.assertIsNone(models.Workspace.objects.get(pk=self.ws.pk).closed_at)  # the practice stays open
        self.assertIn(disposal.MISFILED_REMINDER, output)
        self.assertEqual(completed.scope, Event.DOCUMENT)
        self.assertEqual(completed.encounter_ids, [str(self.a_note.pk)])
        for marker in MARKERS:
            self.assertNotIn(marker, output)


# --- real commits: the files after the commit, and the vacuum ---------------------------------------------------------------

@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class CommittedDisposalTests(TransactionTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        override = override_settings(ORIGINALS_DIR=self.root / 'originals')
        override.enable()
        self.addCleanup(override.disable)
        self.ws, self.other = f.workspace('Synthetic A'), f.workspace('Synthetic B')
        self.member, self.keeper = f.member(self.ws), f.member(self.other)
        for ws, user in ((self.ws, self.member), (self.other, self.keeper)):
            enc = f.encounter(ws, user, title='ZZ-TITLE-MARKER committed')
            f.upload(enc, user, data=f.PDF_BYTES + str(ws.pk).encode(), filename='zz-file-marker.pdf')

    def test_a_committed_destruction_deletes_the_files_and_vacuums_the_tables_it_touched(self):
        reason = reason_file(self.root)
        call_command('dispose', '--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason, stdout=io.StringIO())
        call_command('dispose', '--plan', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason, stdout=io.StringIO())
        plan = Event.objects.get(stage=Event.PLANNED)
        keep = folder_digests(self.other.pk)
        out = io.StringIO()
        with installer_idle(), mock.patch.object(disposal, '_vacuum', wraps=disposal._vacuum) as vacuum:
            call_command('dispose', '--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator',
                         '--approved-by', 'Synthetic Approver', '--authorization-ref', 'synthetic@0000000', stdout=out)
        completed = Event.objects.get(stage=Event.COMPLETED)
        self.assertEqual(completed.notes, f'plan={plan.pk}; vacuum=done')
        (tables,), _ = vacuum.call_args
        self.assertEqual(set(tables), set(disposal.touched_tables(disposal.workspace_scope(self.ws.pk))))
        self.assertFalse(storage.workspace_folder(self.ws.pk).exists())
        self.assertEqual(folder_digests(self.other.pk), keep)
        self.assertEqual(models.SourceFile.objects.filter(encounter__workspace=self.other).count(), 1)
        self.assertIn('CPT Studio destruction certificate', out.getvalue())

    def test_a_refused_destruction_rolls_back_everything(self):
        call_command('dispose', '--close', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.root), stdout=io.StringIO())
        call_command('dispose', '--plan', '--workspace', str(self.ws.pk), '--by', 'Synthetic Operator',
                     '--reason-file', reason_file(self.root), stdout=io.StringIO())
        plan = Event.objects.get(stage=Event.PLANNED)
        before, files = snapshot(), folder_digests(self.ws.pk)
        real = disposal._delete_rows

        def failing(model, scope):  # the last table's delete fails, after every other one ran
            if model is models.SourceFile:
                raise RuntimeError('synthetic: the last delete fails')
            return real(model, scope)
        with installer_idle(), mock.patch.object(disposal, '_delete_rows', side_effect=failing):
            with self.assertRaises(RuntimeError):
                call_command('dispose', '--execute', '--plan', str(plan.pk), '--by', 'Synthetic Operator',
                             '--approved-by', 'Synthetic Approver', '--authorization-ref', 'synthetic@0000000',
                             stdout=io.StringIO())
        self.assertEqual(changed_rows(before, snapshot()), set())  # one transaction: nothing was destroyed
        self.assertEqual(folder_digests(self.ws.pk), files)


# --- the ledger and its replay after a restore -------------------------------------------------------------------------------

class LedgerTests(PracticeCase, TestCase):
    def destroyed_with_ledger(self):
        self.seed()
        self.execute(self.close_and_plan())
        ledger = Path(self.scratch.name) / 'ledger.jsonl'
        ledger.write_text(self.command('--ledger'), encoding='utf-8')
        return ledger

    def restore_older_backup(self):
        """What a restore from a backup older than the disposal brings back, simulated on the test database: the
        practice open again with a document's rows and file, its memberships on - and none of the ledger's rows."""
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM studio_disposalevent')  # the backup predates every ledger row
        models.Workspace.objects.filter(pk=self.ws.pk).update(closed_at=None)
        models.Membership.objects.filter(workspace=self.ws).update(active=True)
        models.Encounter.objects.filter(pk=self.a_note.pk).update(title='ZZ-TITLE-MARKER restored', destroyed_at=None,
                                                                 state='reviewed')
        revision = f.upload(models.Encounter.objects.get(pk=self.a_note.pk), self.owner,
                            data=f.PDF_BYTES + b' restored', filename='zz-file-marker-restored.pdf')
        return revision

    def test_the_ledger_prints_every_disposal_event_signed(self):
        ledger = self.destroyed_with_ledger()
        entries = disposal.read_ledger(ledger.read_text().splitlines())
        self.assertEqual([entry['stage'] for entry in entries], [Event.CLOSED, Event.PLANNED, Event.COMPLETED])
        self.assertEqual({entry['id'] for entry in entries}, {str(pk) for pk in Event.objects.values_list('pk', flat=True)})
        for marker in MARKERS:
            self.assertNotIn(marker, ledger.read_text())

    def test_a_changed_ledger_line_is_refused_before_anything_is_touched(self):
        ledger = self.destroyed_with_ledger()
        lines = ledger.read_text().splitlines()
        item = json.loads(lines[-1])
        item['entry']['workspace_id'] = str(self.other_ws.pk)  # a forged line aimed at the other practice
        ledger.write_text('\n'.join(lines[:-1] + [json.dumps(item)]), encoding='utf-8')
        before = snapshot()
        with installer_idle(), self.assertRaises(CommandError) as raised:
            self.command('--replay-ledger', str(ledger), '--execute', '--by', 'Synthetic Operator',
                         '--approved-by', 'Synthetic Approver', '--authorization-ref', 'synthetic@0000000')
        self.assertIn('was changed or written by another installation', str(raised.exception))
        self.assertEqual(changed_rows(before, snapshot()), set())

    def test_a_replay_after_a_restore_destroys_the_scope_again_and_writes_the_ledger_back(self):
        ledger = self.destroyed_with_ledger()
        original = disposal.read_ledger(ledger.read_text().splitlines())
        revision = self.restore_older_backup()
        stored = storage.stored_path(revision.source_file.storage_name)
        before = snapshot()
        dry = self.command('--replay-ledger', str(ledger))
        self.assertIn('Dry run: nothing was changed', dry)
        self.assertIn('Ledger rows missing: 3', dry)
        self.assertEqual(changed_rows(before, snapshot()), set())
        self.assertTrue(stored.exists())
        with installer_idle():
            output = self.command('--replay-ledger', str(ledger), '--execute', '--by', 'Synthetic Operator',
                                  '--approved-by', 'Synthetic Approver', '--authorization-ref', 'synthetic@0000000')
        self.assertIn('Ledger rows restored: 3', output)
        for entry in original:  # written back exactly: their own ids and times
            row = Event.objects.get(pk=entry['id'])
            self.assertEqual(disposal._entry(row), entry)
        replayed = Event.objects.get(stage=Event.COMPLETED, notes__startswith=f'replay={original[-1]["id"]};')
        self.assertEqual(replayed.scope, Event.WORKSPACE)
        self.assertFalse(stored.exists())
        tomb = models.Encounter.objects.get(pk=self.a_note.pk)
        self.assertEqual((tomb.title, tomb.state), ('', 'destroyed'))
        self.assertIsNotNone(models.Workspace.objects.get(pk=self.ws.pk).closed_at)
        self.assertFalse(models.Membership.objects.filter(workspace=self.ws, active=True).exists())
        self.assertFalse(models.SourceRevision.objects.filter(encounter__workspace=self.ws).exists())
        for marker in MARKERS:
            self.assertNotIn(marker, output)

    def test_a_replay_while_the_worker_beats_is_refused(self):
        ledger = self.destroyed_with_ledger()
        self.restore_older_backup()
        jobs.beat()
        with installer_idle(), self.assertRaises(CommandError) as raised:
            self.command('--replay-ledger', str(ledger), '--execute', '--by', 'Synthetic Operator',
                         '--approved-by', 'Synthetic Approver', '--authorization-ref', 'synthetic@0000000')
        self.assertIn('The worker is running', str(raised.exception))
        self.assertTrue(models.SourceRevision.objects.filter(encounter__workspace=self.ws).exists())
