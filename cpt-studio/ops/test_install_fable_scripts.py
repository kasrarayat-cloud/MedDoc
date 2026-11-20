"""The Fable coding build's in-image scripts (ops/install.py; the build specification, sections 2, 3, 5 and 11), run as
`manage shell -c` runs them, on a disposable PostgreSQL with this tree's code (test_install_harness2's DatabaseTest:
skipped, never passed, without one), and the installer's readers of their answers:

  INSTALL_COUNTS     encounters, stages by kind and state, provider runs by purpose and state, unknown and in-flight
                     runs, the four tables of migration 0016 and the standing holds - never a refusal;
  RECOMPUTE_STATES   studio.state.refresh for the encounters with a coding round; every other stored state left;
  CLOSE_STAGES       an undo's close: the coding jobs an earlier worker cannot run cancelled (their rounds stopped and
                     resumable), one left sending recorded unknown, a round whose send is unknown or failed failed as
                     its own stage would have (studio.jobs.abandoned_outcome), nothing finished touched, no row of
                     the four tables removed and none written but the closed rounds, and the encounters whose state
                     the next pair derives named ('relabel');
  UNDO_HAZARDS_READ  'unknown': a coding run whose outcome is unknown and not reconciled - and nothing else;
  TOUCHED_SINCE_READ the encounters with a record created since a time, the four tables' included;
  CODING_MADE        the declared note: what this revision coded, and that its answers, decisions and exports are not
                     carried back;
  PUT_BACK_STATES    the state the pair the rows go to derives, with its own derivation: studio.state here, and an
                     earlier image's studio.review.refresh_state - proven on a stand-in, since this tree has no
                     earlier pipeline to run (lane E removes it), so the earlier image's own run is the rollback
                     rehearsal's (ops/INSTALL.md).

Every script that runs in this revision's image is read for the modules it imports: none of the earlier pipeline's.
Synthetic data only: every encounter, round, run and value is made in the test.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_install_fable_scripts.py' -v
"""
import ast
import datetime as dt
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import guard_host, release_host  # noqa: E402
from test_install_harness2 import DatabaseTest, run_in_image  # noqa: E402

IMAGE = 'sha256:' + 'c' * 64
OLDER_IMAGE = 'sha256:' + 'd' * 64
# the close's notes for a coding job (close_undone_stages writes the real ones): its round reads stopped, or failed
CODE_NOTE = 'Stopped by the installer: synthetic undo.'
FAILED_NOTE = 'Stopped by the installer, its round closed as failed: synthetic undo.'
# the kinds the installed revision e426c747's worker runs (its studio.jobs.STAGES): no coding stage among them
EARLIER_KINDS = sorted(['extract', 'analyze', 'predict', 'assess', 'review2', 'astra', 'fable', 'astra_peer',
                        'fable_peer', 'interpret', 'appraise', 'question'])
# the modules the Fable coding build removes (BUILD-SPEC section 10): no script run in its image imports one
REMOVED = ('studio.interpretation', 'studio.gi', 'studio.validation', 'studio.ingest', 'studio.participants',
           'studio.providers', 'studio.candidates', 'studio.code_shapes', 'studio.context_facts', 'studio.evaluation',
           'studio.answers', 'studio.progress', 'studio.review', 'studio.reports', 'studio.customer_api',
           'studio.serializers', 'studio.provider_holds')
THIS_IMAGE = ('INSTALL_COUNTS', 'V1_ROWS', 'RECOMPUTE_STATES', 'UNDO_HAZARDS_READ', 'TOUCHED_SINCE_READ', 'CLOSE_STAGES',
              'CODING_MADE', 'UNRUNNABLE_STAGES', 'TARGET_MODEL_READS', 'LICENSE_NOTE_FIX', 'OPERATOR_ACCOUNTS',
              'OPERATOR_CHECK', 'CODING_CREDENTIALS_CHECK', 'CONVERSION_GATE')


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


def imported(source) -> set:
    """Every module ``source`` imports ('from studio import jobs' imports studio.jobs)."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f'{node.module}.{alias.name}' for alias in node.names)
    return found


class ScriptImportTests(unittest.TestCase):
    def test_no_script_run_in_this_revisions_image_imports_a_module_the_build_removes(self):
        for name in THIS_IMAGE:
            with self.subTest(script=name):
                modules = imported(getattr(install, name))
                self.assertEqual(sorted(module for module in modules if module.startswith(REMOVED)), [])
        # the control: the reader finds an import of a removed module where there is one
        self.assertIn('studio.providers.credentials', imported(install.CREDENTIALS_CHECK))

    def test_only_the_put_back_reads_the_earlier_derivation_and_only_where_this_designs_is_absent(self):
        tree = ast.parse(install.PUT_BACK_STATES)
        (guarded,) = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
        self.assertEqual(imported(ast.unparse(guarded.body[0])), {'studio', 'studio.state'})
        (handler,) = guarded.handlers
        self.assertEqual(ast.unparse(handler.type), 'ImportError')
        self.assertEqual(imported(ast.unparse(handler.body[0])), {'studio', 'studio.review'})
        self.assertEqual(imported(install.PUT_BACK_STATES) & set(REMOVED), {'studio.review'})

    def test_the_earlier_pairs_credentials_checks_are_never_run_in_this_revisions_image(self):
        # app starts Corti, the participants and the interpreter disabled: only the coder's loader runs there
        run = []

        def oneshot(image_id, command, env, **kwargs):
            run.append(command[-1])
            return types.SimpleNamespace(returncode=0, stdout=b'coding-credentials-parse-ok\n', stderr=b'')
        with mock.patch.object(install, 'oneshot', oneshot):
            install.check_credential_parsing(IMAGE, b'', 'disabled', [], coding='live')
            install.check_credential_parsing(IMAGE, b'', 'disabled', [], coding='disabled')
        self.assertEqual(run, [install.CODING_CREDENTIALS_CHECK])


class FableRows(DatabaseTest):
    """Synthetic rows of the Fable coding build and of the pipeline before it."""

    def coded(self, tag, *, state='done', codes=(), number=1, stored=None):
        """An encounter with a coding round of ``state`` (its codes ``codes``), its stored state ``stored``."""
        from studio import models
        encounter = self.encounter(tag)
        round_ = self.round(encounter, state=state, codes=codes, number=number)
        if stored is not None:
            models.Encounter.objects.filter(pk=encounter.pk).update(state=stored)
        return models.Encounter.objects.get(pk=encounter.pk), round_

    def round(self, encounter, *, state='done', codes=(), number=1):
        """A coding round; a code row without a line is given L1.., in order (FIX-SPEC 1: every row has one)."""
        from studio import models
        rows = [code if 'line' in code else {'line': f'L{place}', **code} for place, code in enumerate(codes, start=1)]
        return models.CodingRound.objects.create(
            encounter=encounter, revision=encounter.current_revision, number=number, trigger='upload',
            context={'service_date': None, 'insurance': 'unknown', 'answers': []}, state=state, codes=rows)

    def code_job(self, encounter, round_, state, *, started=None, created=None):
        from django.utils import timezone
        from studio import models
        job = models.Job.objects.create(
            encounter=encounter, revision=round_.revision, kind='code', state=state,
            idempotency_key=f'code:{round_.pk}', deadline_at=timezone.now() + dt.timedelta(minutes=120),
            started_at=started or (timezone.now() - dt.timedelta(seconds=5) if state == models.Job.RUNNING else None))
        if created is not None:
            models.Job.objects.filter(pk=job.pk).update(created_at=created)
        return models.Job.objects.get(pk=job.pk)

    def earlier_job(self, encounter, kind, state):
        from django.utils import timezone
        from studio import models
        return models.Job.objects.create(
            encounter=encounter, revision=encounter.current_revision, kind=kind, state=state,
            idempotency_key=f'{kind}:{encounter.pk}:{state}', deadline_at=timezone.now() + dt.timedelta(minutes=9),
            started_at=timezone.now() - dt.timedelta(seconds=5) if state == models.Job.RUNNING else None)

    def coding_run(self, encounter, round_, *, purpose='coding_reader', state='succeeded', endpoint='https://synthetic',
                   reconciled=False, sent=True):
        from django.utils import timezone
        from studio import models
        return models.ProviderRun.objects.create(
            encounter=encounter, revision=round_.revision, provider='anthropic', adapter_version='cptstudio-fable-coder@1',
            purpose=purpose, request_sha256='e' * 64, request_body={}, contexts=[], state=state, sent=sent,
            endpoint=endpoint, scope={'round': str(round_.pk)}, started_at=timezone.now(),
            reconciled_at=timezone.now() if reconciled else None)

    def decision(self, encounter, round_, code, action, line=None):
        """A reviewer's decision on the line of ``round_`` holding ``code`` (or on ``line``): one line each."""
        from studio import models
        line = line or next((row['line'] for row in round_.codes if row.get('code') == code), 'L1')
        return models.CodeDecision.objects.create(encounter=encounter, round=round_, line=line, code=code,
                                                  action=action, reviewer=encounter.created_by, reviewer_kind='human')

    def close(self, kinds, since=None, note='Closed by the installer: synthetic undo.'):
        from django.utils import timezone
        return run_in_image(install.CLOSE_STAGES, {
            'since': (since or timezone.now()).isoformat(), 'note': note, 'code_note': CODE_NOTE,
            'failed_note': FAILED_NOTE, 'kinds': kinds})

    def table_rows(self) -> dict:
        from studio import models
        return {name: getattr(models, name).objects.count() for name in install.COUNTED_TABLES}

    def table_snapshot(self) -> dict:
        """Every field of every row of the four tables of migration 0016: {table: {pk: {field: value}}}."""
        from studio import models
        snapshot = {}
        for name in install.COUNTED_TABLES:
            rows = {}
            for row in getattr(models, name).objects.order_by('pk').values():
                rows[str(row['id'])] = {key: bytes(value) if isinstance(value, memoryview) else value
                                        for key, value in row.items()}
            snapshot[name] = rows
        return snapshot


class InstallCountsOnTheDatabaseTests(FableRows):
    def read(self):
        return run_in_image(install.INSTALL_COUNTS, {'limit': install.NAMED_LIMIT})

    def test_a_clean_target_counts_nothing_and_says_it_in_its_shape(self):
        answer = self.read()
        self.assertEqual(install.counts_problem(answer), '')
        self.assertEqual(answer['tables'], {name: 0 for name in install.COUNTED_TABLES})
        self.assertEqual(install.counts_report(answer), [])
        self.assertEqual(install.install_counts.__name__, 'install_counts')

    def test_every_count_reads_what_the_target_holds_and_the_owner_is_told_each(self):
        from studio import models
        earlier = self.encounter('earlier')
        self.earlier_job(earlier, 'extract', 'queued')
        self.earlier_job(earlier, 'interpret', 'running')
        encounter, round_ = self.coded('coded', codes=[{'code': '43239', 'status': 'ready'}])
        self.code_job(encounter, round_, 'succeeded')
        self.coding_run(encounter, round_)
        self.coding_run(encounter, round_, purpose='coding_checker', state='unknown')
        self.coding_run(encounter, round_, purpose='coding_checker', state='reserved', sent=False)
        self.decision(encounter, round_, '43239', 'approve')
        refused = self.coding_run(encounter, round_, state='failed')
        models.InterpreterHold.objects.create(reason='auth', http_status=401, vendor_status='authentication_error',
                                              violations=[], run=refused)
        answer = self.read()
        self.assertEqual(install.counts_problem(answer), '')
        self.assertEqual(answer['encounters'], {'count': 2, 'coded': 1})
        self.assertEqual(answer['jobs'], {'code': {'succeeded': 1}, 'extract': {'queued': 1},
                                          'interpret': {'running': 1}})
        self.assertEqual(answer['runs'], {'coding_checker': {'reserved': 1, 'unknown': 1},
                                          'coding_reader': {'failed': 1, 'succeeded': 1}})
        self.assertEqual(answer['unknown'], {'count': 1, 'encounter_count': 1, 'encounters': [str(encounter.pk)],
                                             'in_flight': {'reserved': 1, 'sending': 0}})
        self.assertEqual(answer['tables'], {'CodingRound': 1, 'CodingAnswer': 0, 'CodeDecision': 1,
                                            'ExportArtifact': 0})
        self.assertEqual(answer['holds'], {'standing': 1})
        report = ' | '.join(install.counts_report(answer))
        for said in ('1 stage(s) of the earlier pipeline queued and 1 running', '1 provider outcome(s) still unknown',
                     '1 provider run(s) reserved and 0 sending', 'CodeDecision 1, CodingRound 1', '1 hold(s) standing'):
            self.assertIn(said, report)
        self.assertIn('1 coded', install.counts_summary({'counted': True, **answer, 'report': [report]}))

    def test_an_answer_out_of_its_shape_is_recorded_as_not_counted_and_never_refuses(self):
        good = self.read()
        for broken in (None, {}, {**good, 'jobs': {'code': {'queued': 0}}}, {**good, 'tables': {'CodingRound': 1}},
                       {**good, 'unknown': {**good['unknown'], 'count': -1}}, {**good, 'holds': {}},
                       {**good, 'encounters': {'count': 1, 'coded': 2}}):
            with self.subTest(broken=broken), mock.patch.object(install, 'app_script', return_value=broken):
                counted = install.install_counts(IMAGE, b'')
                self.assertFalse(counted['counted'])
                self.assertTrue(counted['report'])
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('Counting failed (exit 1).')):
            self.assertFalse(install.install_counts(IMAGE, b'')['counted'])
        with mock.patch.object(install, 'app_script', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            install.install_counts(IMAGE, b'')


class RecomputeStatesOnTheDatabaseTests(FableRows):
    def test_a_coded_encounter_gets_this_derivations_state_and_every_other_keeps_its_own(self):
        from studio import models
        ready, _ = self.coded('ready', codes=[{'code': '43239', 'status': 'ready'}], stored='processing')
        asked, _ = self.coded('asked', codes=[{'code': '45385', 'status': 'needs_answer'}], stored='awaiting_answer')
        earlier = self.encounter('earlier')
        models.Encounter.objects.filter(pk=earlier.pk).update(state='ready_for_review')  # the earlier pipeline's word
        answer = run_in_image(install.RECOMPUTE_STATES, {})
        self.assertEqual(answer, {'encounters': 2, 'changed': {str(ready.pk): ['processing', 'ready']}, 'kept': 1})
        self.assertEqual(models.Encounter.objects.get(pk=earlier.pk).state, 'ready_for_review')
        self.assertEqual(models.Encounter.objects.get(pk=asked.pk).state, 'awaiting_answer')
        # narrowed: only the encounters named are read
        models.Encounter.objects.filter(pk=ready.pk).update(state='processing')
        narrowed = run_in_image(install.RECOMPUTE_STATES, {'encounters': [str(asked.pk)]})
        self.assertEqual((narrowed['encounters'], narrowed['changed']), (1, {}))
        self.assertEqual(models.Encounter.objects.get(pk=ready.pk).state, 'processing')


class CloseOnTheDatabaseTests(FableRows):
    def test_switching_back_to_an_earlier_worker_cancels_every_open_coding_job_and_touches_nothing_else(self):
        from django.utils import timezone
        from studio import models, state
        Run = models.ProviderRun
        long_ago = timezone.now() - dt.timedelta(days=3)
        queued, queued_round = self.coded('queued', state='queued', stored='processing')
        queued_job = self.code_job(queued, queued_round, 'queued', created=long_ago)  # before the pair: closed anyway
        sending, sending_round = self.coded('sending', state='running', stored='processing')
        sending_job = self.code_job(sending, sending_round, 'running')
        reader = self.coding_run(sending, sending_round, state='sending', sent=False)
        checker = self.coding_run(sending, sending_round, purpose='coding_checker', state='reserved', sent=False)
        done, done_round = self.coded('done', codes=[{'code': '43239', 'status': 'ready'}], stored='ready')
        done_job = self.code_job(done, done_round, 'succeeded')
        self.decision(done, done_round, '43239', 'approve')
        models.CodingAnswer.objects.create(encounter=done, round=done_round, question='Was a biopsy taken?',
                                           answer='Yes, two.', answered_by=done.created_by)
        models.ExportArtifact.objects.create(encounter=done, round=done_round, kind='approved', fmt='txt',
                                             filename='synthetic.txt', content=b'SYNTHETIC', sha256='f' * 64,
                                             created_by=done.created_by)
        earlier = self.encounter('earlier')
        extract = self.earlier_job(earlier, 'extract', 'queued')  # the earlier worker runs it: left to it
        before = self.table_rows()
        snapshot = self.table_snapshot()
        closed = self.close(EARLIER_KINDS)
        self.assertEqual((closed['closed'], closed['stopped'], closed['unknown'], closed['retired'], closed['failed']),
                         (2, 1, 1, 0, 0))
        self.assertEqual((closed['kinds'], closed['encounters']), (['code'], 2))
        self.assertEqual((closed['runs_unknown'], closed['runs_not_sent']), (1, 1))
        self.assertEqual(closed['rounds'], {'cancelled': 1, 'failed': 1})
        # the queued job: failed with the installer's note, its round stopped - so a Resume here continues the round
        queued_job.refresh_from_db()
        self.assertEqual((queued_job.state, queued_job.error), ('failed', 'Stopped by the installer: synthetic undo.'))
        self.assertEqual(models.CodingRound.objects.get(pk=queued_round.pk).state, 'cancelled')
        self.assertEqual(models.Encounter.objects.get(pk=queued.pk).state, state.STOPPED)
        # the one left sending: its request unknown (sent: it called a vendor), the job unknown, the round failed so
        reader.refresh_from_db()
        checker.refresh_from_db()
        self.assertEqual((reader.state, reader.sent, checker.state), (Run.UNKNOWN, True, Run.NOT_SENT))
        sending_job.refresh_from_db()
        self.assertEqual(sending_job.state, 'unknown')
        failed = models.CodingRound.objects.get(pk=sending_round.pk)
        self.assertEqual((failed.state, failed.failure_kind), ('failed', 'unknown'))
        # nothing finished, nothing of the earlier pipeline the next worker runs; no row of the four new tables is
        # deleted (or added), and the closed rounds are the only rows written - in their state, finish time and failure
        self.assertEqual(models.Job.objects.get(pk=done_job.pk).state, 'succeeded')
        self.assertEqual(models.Job.objects.get(pk=extract.pk).state, 'queued')
        self.assertEqual(self.table_rows(), before)
        self.assertEqual(models.CodingRound.objects.get(pk=done_round.pk).state, 'done')
        after = self.table_snapshot()
        self.assertEqual({name: sorted(rows) for name, rows in after.items()},
                         {name: sorted(rows) for name, rows in snapshot.items()})
        for name in ('CodingAnswer', 'CodeDecision', 'ExportArtifact'):
            self.assertEqual(after[name], snapshot[name], name)
        written = {pk: sorted(key for key, value in row.items() if snapshot['CodingRound'][pk][key] != value)
                   for pk, row in after['CodingRound'].items()}
        self.assertEqual({pk: keys for pk, keys in written.items() if keys}, {
            str(queued_round.pk): ['finished_at', 'state'],
            str(sending_round.pk): ['error', 'failure_kind', 'finished_at', 'state']})
        # what the next pair is handed: every coded encounter to derive; the unknown outcome to reconcile first
        self.assertEqual(closed['relabel'], sorted(str(pk) for pk in (queued.pk, sending.pk, done.pk)))
        self.assertEqual(closed['hazards'], {str(sending.pk): ['unknown']})
        # and no stage the earlier worker cannot run is left queued or running
        self.assertFalse(models.Job.objects.filter(state__in=('queued', 'running')).exclude(
            kind__in=EARLIER_KINDS).exists())

    def test_a_round_whose_send_failed_or_stays_unknown_is_closed_failed_as_the_worker_would_never_stopped(self):
        # MONEY-2 (fix lane F2): the close settles each round as its own stage would have (the stale sweep's rule,
        # studio.jobs.abandoned_outcome) - a send that failed (answered and billed) fails the round with that send's
        # kind, a send left unknown that no operator reconciled fails it as unknown - and only a round with nothing
        # unsettled is cancelled for a Resume; nothing was in flight at the close, so no sending count tells them apart
        from studio import jobs, models
        Run = models.ProviderRun
        failed, failed_round = self.coded('failed-send', state='running', stored='processing')
        failed_job = self.code_job(failed, failed_round, 'running')
        self.coding_run(failed, failed_round)  # the reader's read succeeded
        too_long = self.coding_run(failed, failed_round, purpose='coding_checker', state='failed')
        Run.objects.filter(pk=too_long.pk).update(scope={'round': str(failed_round.pk), 'failure_kind': jobs.TOO_LONG})
        unknown, unknown_round = self.coded('unknown-send', state='running', stored='processing')
        unknown_job = self.code_job(unknown, unknown_round, 'running')
        self.coding_run(unknown, unknown_round, state='unknown')  # settled unknown before the close; never reconciled
        looked, looked_round = self.coded('reconciled', state='running', stored='processing')
        looked_job = self.code_job(looked, looked_round, 'running')
        self.coding_run(looked, looked_round, state='unknown', reconciled=True)  # an operator looked: nothing unsettled
        closed = self.close(EARLIER_KINDS)
        self.assertEqual(closed['rounds'], {'cancelled': 1, 'failed': 2})
        self.assertEqual((closed['runs_unknown'], closed['runs_not_sent']), (0, 0))  # nothing was in flight
        self.assertEqual((closed['closed'], closed['stopped'], closed['unknown'], closed.get('code_failed')),
                         (3, 1, 1, 1))
        rounds = {row.pk: row for row in models.CodingRound.objects.filter(
            pk__in=[failed_round.pk, unknown_round.pk, looked_round.pk])}
        self.assertEqual([(rounds[pk].state, rounds[pk].failure_kind, rounds[pk].error)
                          for pk in (failed_round.pk, unknown_round.pk, looked_round.pk)],
                         [('failed', jobs.TOO_LONG, jobs.FAILURE_TEXT[jobs.TOO_LONG]),
                          ('failed', jobs.UNKNOWN, jobs.FAILURE_TEXT[jobs.UNKNOWN]), ('cancelled', '', '')])
        for job, job_state, note in ((failed_job, 'failed', FAILED_NOTE), (unknown_job, 'unknown', FAILED_NOTE),
                                     (looked_job, 'failed', CODE_NOTE)):
            job.refresh_from_db()
            self.assertEqual((job.state, job.error), (job_state, note))
        # what a member is then offered: no Resume of a round whose read must not be sent again by itself
        self.assertTrue(jobs.awaiting_reconcile(rounds[unknown_round.pk]))
        self.assertEqual(closed['hazards'], {str(unknown.pk): ['unknown']})
        self.assertEqual(models.Encounter.objects.get(pk=failed.pk).state, 'failed')
        self.assertEqual(models.Encounter.objects.get(pk=looked.pk).state, 'stopped')

    def test_a_stopped_coding_job_an_earlier_installer_would_refuse_on_is_failed_and_its_round_left_stopped(self):
        from studio import models
        stopped, stopped_round = self.coded('stopped', state='cancelled', stored='stopped')  # a member's Stop
        stopped_job = self.code_job(stopped, stopped_round, 'cancelled')
        retried, first = self.coded('retried', state='failed')
        old_job = self.code_job(retried, first, 'cancelled')  # an earlier stage of the revision: not its latest
        latest = self.round(retried, state='done', number=2)
        models.Job.objects.create(encounter=retried, revision=latest.revision, kind='code', state='succeeded',
                                  idempotency_key=f'code:{latest.pk}', deadline_at=old_job.deadline_at)
        closed = self.close(EARLIER_KINDS)
        self.assertEqual((closed['closed'], closed['retired'], closed['stopped']), (1, 1, 0))
        self.assertEqual(models.Job.objects.get(pk=stopped_job.pk).state, 'failed')
        self.assertEqual(models.CodingRound.objects.get(pk=stopped_round.pk).state, 'cancelled')  # still resumable
        self.assertEqual(models.Job.objects.get(pk=old_job.pk).state, 'cancelled')
        # what the earlier revision's own read now finds: no coding stage it would count as one it cannot run
        with mock.patch.dict(sys.modules['studio.jobs'].STAGES, clear=True):
            from studio import jobs
            for kind in EARLIER_KINDS:
                jobs.STAGES[kind] = None
            self.assertEqual(run_in_image(install.UNRUNNABLE_STAGES, {})['stuck'], 0)
        # a next worker of this design keeps a member's Stop as it is
        again, again_round = self.coded('again', state='cancelled')
        again_job = self.code_job(again, again_round, 'cancelled')
        self.assertEqual(self.close(['code'])['retired'], 0)
        self.assertEqual(models.Job.objects.get(pk=again_job.pk).state, 'cancelled')

    def test_a_coding_job_made_after_a_close_is_closed_by_the_next_one(self):
        from django.utils import timezone
        from studio import models
        first_at = timezone.now()
        self.assertEqual(self.close(EARLIER_KINDS)['closed'], 0)
        late, late_round = self.coded('late', state='queued')  # this revision's web still served (B4 to B6)
        late_job = self.code_job(late, late_round, 'queued')
        self.assertEqual(run_in_image(install.UNDO_HAZARDS_READ, {}), {'hazards': {}})  # an open job is no hazard
        second = self.close(EARLIER_KINDS, since=first_at)  # B7, once that web is drained
        self.assertEqual((second['closed'], second['stopped']), (1, 1))
        self.assertEqual(models.Job.objects.get(pk=late_job.pk).state, 'failed')

    def test_a_next_worker_of_this_design_keeps_the_coding_jobs_made_before_this_pair(self):
        from django.utils import timezone
        from studio import models
        before_pair = timezone.now() - dt.timedelta(hours=2)
        older, older_round = self.coded('older', state='queued')
        older_job = self.code_job(older, older_round, 'queued', created=before_pair - dt.timedelta(hours=1))
        newer, newer_round = self.coded('newer', state='queued')
        newer_job = self.code_job(newer, newer_round, 'queued')
        closed = self.close(sorted(['code']), since=before_pair)
        self.assertEqual(closed['closed'], 1)
        self.assertEqual(models.Job.objects.get(pk=older_job.pk).state, 'queued')
        self.assertEqual(models.Job.objects.get(pk=newer_job.pk).state, 'failed')
        self.assertEqual(models.CodingRound.objects.get(pk=older_round.pk).state, 'queued')

    def test_with_no_next_worker_to_ask_the_earlier_pipelines_other_open_stages_are_failed_as_before(self):
        from studio import models
        earlier = self.encounter('earlier')
        interpret = self.earlier_job(earlier, 'interpret', 'queued')
        extract = self.earlier_job(earlier, 'extract', 'queued')  # one of COMMON_STAGE_KINDS: kept
        other = self.encounter('other')
        appraise = self.earlier_job(other, 'appraise', 'cancelled')  # cancelled as the latest stage: resumable there
        closed = self.close(list(install.COMMON_STAGE_KINDS))
        self.assertEqual((closed['closed'], closed['failed'], closed['stopped']), (2, 2, 0))
        for job in (interpret, appraise):
            job.refresh_from_db()
            self.assertEqual((job.state, job.error), ('failed', 'Closed by the installer: synthetic undo.'))
        self.assertEqual(models.Job.objects.get(pk=extract.pk).state, 'queued')
        self.assertEqual(closed['relabel'], sorted([str(earlier.pk), str(other.pk)]))  # their stages settled now

    def test_the_installer_gives_the_close_both_notes_and_the_next_workers_kinds(self):
        with mock.patch.object(install, 'app_script', return_value={'closed': 0}) as script:
            install.close_undone_stages(IMAGE, b'', dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc), 'a' * 40,
                                        'it was switched back', ['extract', 'predict'])
        (image, env, body, params), kwargs = script.call_args
        self.assertEqual((image, body), (IMAGE, install.CLOSE_STAGES))
        self.assertEqual(sorted(params), ['code_note', 'failed_note', 'kinds', 'note', 'since'])
        self.assertEqual(params['kinds'], ['extract', 'predict'])
        self.assertIn('a Resume continues it', params['code_note'])
        self.assertIn('Its round is closed as failed', params['failed_note'])
        self.assertNotIn('Resume', params['failed_note'])
        self.assertIn('so this stage will not run', params['note'])


KEPT = 'no row of the four new tables is deleted; closed rounds are marked cancelled'


class FourTablesWordingTests(unittest.TestCase):
    """install-2: an undo's close writes the rounds it closes (cancelled; failed as unknown when a request was in
    flight), so nothing may say the four tables are untouched - INSTALL.md, the installer's own comments and the
    receipt's declared note say what the close does."""

    def test_install_md_and_the_installer_say_closed_rounds_are_marked_and_no_row_is_deleted(self):
        guide = ' '.join((Path(install.__file__).resolve().parent / 'INSTALL.md').read_text(encoding='utf-8').split())
        source = ' '.join(Path(install.__file__).read_text(encoding='utf-8').replace('#', ' ').split())
        for text, where in ((guide, 'INSTALL.md'), (source, 'install.py')):
            with self.subTest(where=where):
                self.assertIn(KEPT, text.lower())  # INSTALL.md's (b) opens a sentence with it
                for claim in ('The four tables are left exactly as they are', 'is written, changed or removed by any '
                              'undo', 'the four tables of the Fable coding build are not written', 'stay in them, '
                              'untouched', 'stay in them untouched', 'which stay as they are'):
                    self.assertNotIn(claim, text)

    def test_the_receipts_declared_note_says_it_in_every_form(self):
        counted = {'coding': {'encounters': ['e1'], 'created': ['e1'], 'rounds': 1, 'answers': 0,
                              'decisions': {'approve': 1, 'reject': 0, 'revoke': 0}, 'approved': 1,
                              'exports': {'draft': 0, 'approved': 0}}}
        empty = {'coding': {'encounters': [], 'created': [], 'rounds': 0, 'answers': 0,
                            'decisions': {'approve': 0, 'reject': 0, 'revoke': 0}, 'approved': 0,
                            'exports': {'draft': 0, 'approved': 0}}}
        for answer in (counted, empty, {}):
            with self.subTest(answer=answer), mock.patch.object(install, 'app_script', return_value=answer):
                self.assertIn(KEPT, install.coding_note(IMAGE, b'', 'a' * 40)['note'])
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('Counting failed (exit 1).')):
            self.assertIn(KEPT, install.coding_note(IMAGE, b'', 'a' * 40)['note'])


class ClosedStagesSaidTests(FableRows):
    """install-2 residue: CLOSED_STAGES_SAID is what an undo's receipt says of the stages its close already closed (the
    switch-back that refuses after B4's close, every close that raised or gave no answer). It said every coding job
    closed "stays failed, ..., its round stopped, and a Resume continues that round" - false for the round whose request
    was in flight (its job unknown, its round failed as unknown, no Resume, a retry waiting for the reconcile) and for
    one whose send failed (its round failed with that send's kind). The sentence must say what the rows read after the
    real close, for each kind of coding job it closes."""

    def test_the_sentence_says_what_the_close_did_to_each_kind_of_coding_job(self):
        from studio import jobs, models
        Run = models.ProviderRun
        queued, queued_round = self.coded('queued', state='queued', stored='processing')
        queued_job = self.code_job(queued, queued_round, 'queued')
        sending, sending_round = self.coded('sending', state='running', stored='processing')
        sending_job = self.code_job(sending, sending_round, 'running')
        self.coding_run(sending, sending_round, state='sending', sent=False)  # its request in flight at the close
        failed, failed_round = self.coded('failed-send', state='running', stored='processing')
        failed_job = self.code_job(failed, failed_round, 'running')
        self.coding_run(failed, failed_round)  # the reader's read succeeded
        too_long = self.coding_run(failed, failed_round, purpose='coding_checker', state='failed')
        Run.objects.filter(pk=too_long.pk).update(scope={'round': str(failed_round.pk), 'failure_kind': jobs.TOO_LONG})
        closed = self.close(EARLIER_KINDS)
        self.assertEqual(closed['rounds'], {'cancelled': 1, 'failed': 2})
        said = ' '.join(install.CLOSED_STAGES_SAID.split())
        for job, round_ in ((queued_job, queued_round), (sending_job, sending_round), (failed_job, failed_round)):
            job.refresh_from_db()
            round_.refresh_from_db()
        # nothing it sent unsettled: the job failed, its round stopped, and a Resume continues the round
        self.assertEqual((queued_job.state, queued_round.state), ('failed', 'cancelled'))
        self.assertIsNotNone(jobs.resume(queued, queued.created_by))
        self.assertIn('with nothing it sent unsettled, the job reads failed and its round stopped, and a Resume continues '
                      'that round whenever this revision serves again', said)
        # its request in flight: the job unknown, its round failed as unknown, no Resume, a retry waiting for the reconcile
        self.assertEqual((sending_job.state, sending_round.state, sending_round.failure_kind), ('unknown', 'failed', 'unknown'))
        self.assertIsNone(jobs.resume(sending, sending.created_by))
        with self.assertRaises(jobs.Refused) as waits:
            jobs.retry(sending, sending.created_by)
        self.assertEqual(str(waits.exception), jobs.RECONCILE_FIRST)
        self.assertIn('with a request in flight or a send whose unknown outcome no operator has reconciled, the job reads '
                      'unknown and its round failed as unknown, so no Resume continues it and a retry waits for an '
                      'operator\'s reconcile', said)
        # a send that failed: the job failed, its round failed with that send's kind, no Resume, a retry a new round
        self.assertEqual((failed_job.state, failed_round.state, failed_round.failure_kind), ('failed', 'failed', jobs.TOO_LONG))
        self.assertIsNone(jobs.resume(failed, failed.created_by))
        self.assertEqual(jobs.retry(failed, failed.created_by).number, 2)
        self.assertIn('with a send that failed, the job reads failed and its round failed with that send\'s kind, so no '
                      'Resume continues it and a retry starts a new round', said)
        # and never the old blanket claim; a stage of another kind is still said as before
        self.assertNotIn('a coding job it closed stays failed, with the installer\'s note, its round stopped', said)
        self.assertIn('a stage of another kind it closed stays failed, with the installer\'s note', said)

    def test_the_refused_switch_back_and_every_unanswered_close_carry_it(self):
        self.assertIn(install.CLOSED_STAGES_SAID, install.possibly_set_back('2026-11-20T08:00:00Z'))
        self.assertIn(install.CLOSED_STAGES_SAID, install.close_did_not_finish('the stages', RuntimeError('synthetic')))
        source = ' '.join(Path(install.__file__).read_text(encoding='utf-8').split())
        self.assertIn("closing = f'. As for what the close already closed: {CLOSED_STAGES_SAID}.'", source)


class HazardsOnTheDatabaseTests(FableRows):
    def test_only_an_unreconciled_unknown_coding_run_is_a_hazard(self):
        encounter, round_ = self.coded('unknown')
        self.coding_run(encounter, round_, state='unknown')
        settled, settled_round = self.coded('reconciled')
        self.coding_run(settled, settled_round, state='unknown', reconciled=True)
        earlier = self.encounter('earlier')
        from django.utils import timezone
        from studio import models
        models.ProviderRun.objects.create(  # the earlier pipeline's own unknown outcome: its status quo, not this one's
            encounter=earlier, revision=earlier.current_revision, provider='corti', adapter_version='synthetic@1',
            purpose='primary', request_sha256='a' * 64, request_body={}, contexts=[], state='unknown', sent=True,
            started_at=timezone.now())
        self.assertEqual(run_in_image(install.UNDO_HAZARDS_READ, {}), {'hazards': {str(encounter.pk): ['unknown']}})

    def test_the_touched_read_names_every_encounter_with_a_record_made_since_its_time_the_new_tables_included(self):
        from django.utils import timezone
        from studio import models
        day_before = timezone.now() - dt.timedelta(days=1)
        old = self.encounter('old')
        decided, round_ = self.coded('decided')
        for encounter in (old, decided):  # every record of both made the day before (rows these models let change)
            models.Encounter.objects.filter(pk=encounter.pk).update(created_at=day_before)
            models.SourceRevision.objects.filter(encounter=encounter).update(created_at=day_before)
        models.CodingRound.objects.filter(pk=round_.pk).update(created_at=day_before)
        since = timezone.now()
        self.assertEqual(run_in_image(install.TOUCHED_SINCE_READ, {'since': since.isoformat()}), {'touched': []})
        self.decision(decided, round_, '43239', 'approve')  # a reviewer's act since then
        touched = run_in_image(install.TOUCHED_SINCE_READ, {'since': since.isoformat()})
        self.assertEqual(touched, {'touched': [str(decided.pk)]})


class CodingNoteOnTheDatabaseTests(FableRows):
    def test_the_note_counts_what_this_revision_coded_and_says_it_is_not_carried_back(self):
        from studio import models
        created, round_ = self.coded('created', codes=[{'code': '43239', 'status': 'ready'},
                                                     {'code': '45385', 'status': 'ready'}])
        self.decision(created, round_, '43239', 'approve')
        self.decision(created, round_, '45385', 'approve')
        self.decision(created, round_, '45385', 'revoke')  # cleared: no longer approved
        models.CodingAnswer.objects.create(encounter=created, round=round_, question='Was a biopsy taken?',
                                           answer='Yes.', answered_by=created.created_by)
        models.ExportArtifact.objects.create(encounter=created, round=round_, kind='approved', fmt='txt',
                                             filename='x.txt', content=b'SYNTHETIC', sha256='f' * 64,
                                             created_by=created.created_by)
        recoded = self.encounter('recoded')
        self.earlier_job(recoded, 'extract', 'succeeded')  # the earlier pipeline read it first
        first = self.round(recoded, codes=[{'code': '45378', 'status': 'ready'}])
        self.decision(recoded, first, '45378', 'approve')  # on an earlier round: not the current approval
        self.round(recoded, number=2, codes=[{'code': '45378', 'status': 'ready'}])
        answer = run_in_image(install.CODING_MADE, {})
        self.assertEqual(answer['coding'], {
            'encounters': sorted([str(created.pk), str(recoded.pk)]), 'created': [str(created.pk)], 'rounds': 3,
            'answers': 1, 'decisions': {'approve': 3, 'reject': 0, 'revoke': 1}, 'approved': 1,
            'exports': {'draft': 0, 'approved': 1}})
        with mock.patch.object(install, 'app_script', return_value=answer):
            note = install.coding_note(IMAGE, b'', 'a' * 40)
        self.assertEqual((note['approved'], note['answers']), (1, 1))
        for said in ('this revision coded 2 encounters in 3 rounds (1 created here, 1 of the earlier review coded again)',
                     '1 answer, 4 code decisions (1 code approved now) and 1 export made here are not carried back',
                     'an accepted loss of a rollback', 'processes none of them unless the document is uploaded again'):
            self.assertIn(said, note['note'])

    def test_a_note_that_does_not_say_what_it_read_is_said_so_and_never_stops_the_undo(self):
        good = {'coding': {'encounters': ['e1'], 'created': ['e1'], 'rounds': 1, 'answers': 0,
                           'decisions': {'approve': 1, 'reject': 0, 'revoke': 0}, 'approved': 1,
                           'exports': {'draft': 0, 'approved': 0}}}
        with mock.patch.object(install, 'app_script', return_value=good):
            self.assertEqual(install.coding_note(IMAGE, b'', 'a' * 40)['encounters'], ['e1'])
        for broken in ({}, {'coding': None}, {'coding': {**good['coding'], 'created': ['e2']}},
                       {'coding': {**good['coding'], 'rounds': 0}}, {'coding': {**good['coding'], 'approved': 2}},
                       {'coding': {**good['coding'], 'decisions': {'approve': 1}}},
                       {'coding': {**good['coding'], 'exports': {'draft': -1, 'approved': 0}}}):
            with self.subTest(broken=broken), mock.patch.object(install, 'app_script', return_value=broken):
                note = install.coding_note(IMAGE, b'', 'a' * 40)
                self.assertIsNone(note['encounters'])
                self.assertIn('was not counted (the count did not say what it read)', note['note'])
                self.assertIn('none of them is carried back', note['note'])
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('Counting failed (exit 1).')):
            self.assertIn('Counting failed', install.coding_note(IMAGE, b'', 'a' * 40)['note'])
        with mock.patch.object(install, 'app_script', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            install.coding_note(IMAGE, b'', 'a' * 40)
        empty = {'coding': {'encounters': [], 'created': [], 'rounds': 0, 'answers': 0,
                            'decisions': {'approve': 0, 'reject': 0, 'revoke': 0}, 'approved': 0,
                            'exports': {'draft': 0, 'approved': 0}}}
        with mock.patch.object(install, 'app_script', return_value=empty):
            self.assertIn('coded no encounter', install.coding_note(IMAGE, b'', 'a' * 40)['note'])


class PutBackStatesOnTheDatabaseTests(FableRows):
    def test_in_an_image_of_this_design_the_put_back_is_its_own_derivation(self):
        encounter, _ = self.coded('ready', codes=[{'code': '43239', 'status': 'ready'}], stored='awaiting_answer')
        answer = run_in_image(install.PUT_BACK_STATES, {'encounters': [str(encounter.pk)]})
        self.assertEqual(answer, {'encounters': 1, 'changed': {str(encounter.pk): ['awaiting_answer', 'ready']},
                                  'derivation': 'studio.state'})

    def test_in_an_earlier_image_it_is_that_images_own_review_refresh_state(self):
        # A stand-in for the earlier image: studio.state absent (as in e426c747) and a studio.review whose
        # refresh_state records each encounter it derives - the earlier pipeline's own code is not in this tree.
        from studio import models
        encounter, _ = self.coded('ready', codes=[{'code': '43239', 'status': 'ready'}], stored='ready')
        derived = []

        def refresh_state(row):
            derived.append(str(row.pk))
            models.Encounter.objects.filter(pk=row.pk).update(state='processing')
            return 'processing'
        review = types.ModuleType('studio.review')
        review.refresh_state = refresh_state
        import studio
        saved = {name: sys.modules.get(name) for name in ('studio.state', 'studio.review')}
        saved_attrs = {name: getattr(studio, name, None) for name in ('state', 'review')}
        sys.modules['studio.state'] = None  # `from studio import state` raises ImportError, as in an earlier image
        sys.modules['studio.review'] = review
        if hasattr(studio, 'state'):
            delattr(studio, 'state')
        studio.review = review
        try:
            answer = run_in_image(install.PUT_BACK_STATES, {'encounters': [str(encounter.pk)]})
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
            for name, value in saved_attrs.items():
                if value is None:
                    if hasattr(studio, name):
                        delattr(studio, name)
                else:
                    setattr(studio, name, value)
        self.assertEqual(derived, [str(encounter.pk)])
        self.assertEqual(answer, {'encounters': 1, 'changed': {str(encounter.pk): ['ready', 'processing']},
                                  'derivation': 'studio.review'})
        from studio import state  # restored: the rest of the suite reads this tree's own module
        self.assertTrue(callable(state.refresh))

    def test_the_installer_runs_it_in_the_next_pairs_image_and_with_none_puts_nothing_back(self):
        closed = {'relabel': ['e1', 'e2']}
        with mock.patch.object(install, 'app_script', return_value={'encounters': 2, 'changed': {}}) as script:
            self.assertEqual(install.put_back_states(closed, OLDER_IMAGE, IMAGE, b''), {'encounters': 2, 'changed': {}})
        (image, env, body, params), _ = script.call_args
        self.assertEqual((image, body, params), (OLDER_IMAGE, install.PUT_BACK_STATES, {'encounters': ['e1', 'e2']}))
        with mock.patch.object(install, 'app_script') as script:
            found = install.put_back_states(closed, None, IMAGE, b'')
            self.assertFalse(script.called)
        self.assertEqual((found['put_back'], found['encounters'], found['changed']), (False, 2, {}))
        self.assertEqual(install.put_back_states({'relabel': []}, OLDER_IMAGE, IMAGE, b''), {'encounters': 0, 'changed': {}})
        with self.assertRaises(install.InstallError):
            install.put_back_states({}, OLDER_IMAGE, IMAGE, b'')


class NothingSetBackTests(unittest.TestCase):
    def test_this_revisions_close_sets_nothing_back_so_nothing_is_put_back_and_nothing_runs(self):
        with mock.patch.object(install, 'app_script') as script:
            done = install.reapply_reverted(IMAGE, b'', [{'closed': 2, 'relabel': []}])
            self.assertFalse(script.called)
        self.assertEqual((done['asked'], done['problem'], done['sentence']), ({}, '', ''))
        # a close that names a set-back value is not this revision's: nothing is put back, and that is said
        with mock.patch.object(install, 'app_script') as script:
            done = install.reapply_reverted(IMAGE, b'', [{'update_pending': {'e1': ['values_saved']},
                                                          'reverted': {'e1': {'setting': {'saved': 'a', 'restored': 'b'}}}}])
            self.assertFalse(script.called)
        self.assertEqual(done['problem'], install.NO_PUT_BACK)
        self.assertIn('which this revision\'s own close never does, so nothing was put back', done['sentence'])
        self.assertFalse(hasattr(install, 'REAPPLY_REVERTED'))
        self.assertIn('set no member\'s details back', install.possibly_set_back('2026-11-20T00:00:00+00:00'))


if __name__ == '__main__':
    unittest.main()
