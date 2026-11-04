"""Refutation round 3, R3-SENDS: how a participant's exchanges are sent and recorded under the provider lock, and how a
run a dead worker left sending is settled (HARNESS.md 2, 11.2 and 12.7 "Recording a participant's exchanges"; I8).

- sends-1: an exchange recorded as it ended (refutation round 2, D5) whose database session had ended let Django open a
  new session - transaction.atomic reconnects when its rollback fails - and that session never took the
  installation-wide provider lock, so the tool loop sent its next exchange while any other session could take the lock
  and send (the installer's access check, a second worker). Once the session that holds the lock is gone, no further
  exchange is sent: the run is recorded failed and sent, with the exchanges sent so far and CPT Studio's own sentence,
  never as a member's Stop. The worker's session really ends here - the client side of its socket is shut down, or the
  server ends the idle session itself; no process is signalled - outside any test transaction, as in the worker.
- sends-3: the installer's undo (ops/install.py CLOSE_STAGES, run in the undone revision's own image) settles a run
  left sending as the stale sweep settles one, sent included: it had recorded a run whose answered exchange is on record
  as never sent.
- sends-4: a replayed exchange reached nothing (the replay records sent False and calls no endpoint), so it never marks
  a run sent, in the sweep or in the undo.
- sends-2, recorded as a known limit (HARNESS.md 12.7): a worker that dies after the loop's final answer was recorded
  and before the run's outcome was leaves a run the sweep settles as unknown beside that answer, and a reconciliation
  sends the identical request again. Pinned so the recorded limit, and its cost, stay true until it is repaired.

falsegreen-5 (the sweep's rule for a recorded failed or unknown exchange) is pinned in tests.test_harness2_r2_peer
RecordedAsItEndsTests. Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake; Astra and
Fable are the real replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline), their
tool calls answered by CPT Studio's real CMS tool executor over a synthetic reference store; sends-4 uses the real
ReplayParticipant with a recording.

Refutation round 4 (R4-SENDS) adds to LockedSessionTests:
- sends-2, falsegreen-1: the lock check asks whether THIS session holds the lock (jobs._holds_provider_lock, pid =
  pg_backend_pid()), and only a race pinned that condition. Here another session - a second worker's, or the access
  check's - takes the lock once the worker's session has ended and keeps it while the loop asks: the loop still sends
  nothing more. The access check's own loop, and the check itself, are pinned in tests.test_harness2_r4_sends.
- sends-3: _finish_loop's fallback (the run's outcome could not be written) settles sent by the rule the sweep and the
  undo use (jobs.may_have_reached_vendor): a replayed run, whose reservation names no endpoint, called no vendor and is
  never recorded sent, whether its loop answered or ended at the lock check.

Refutation round 5 (R5-SENDS, falsegreen-3): the sentence that fallback records for a replay was pinned only through its
own constant (jobs.UNRECORDED_REPLAY_MESSAGE), so the mutant `UNRECORDED_REPLAY_MESSAGE = UNRECORDED_MESSAGE` - round
4's defect wording, "what reached the vendor is not known", false of a replay - passed both tests. It is written out
here (REPLAY_UNRECORDED): the replay called no vendor, so nothing was sent.
"""
import os
import socket
import time
from datetime import timedelta
from unittest import mock

from django.db import DatabaseError, connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from studio import jobs, models, participants, serializers
from studio.participants.replay import ReplayParticipant
from studio.reference import tools as reference_tools
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.test_harness2_pipeline import (ASTRA_READING, EMPTY_PEER, FABLE_READING, Harness2Case, LoopParticipant,
                                          answered, asks, facts_call, install_reference_store)
from tests.test_harness_pipeline import BOTH, ScriptedCorti, _WorkerDied
from tests.test_participants_support import OfflineMixin
from tests.test_pipeline_api import _OtherSession, drain
from tests.test_repairs_pipeline import LIVE, RECONCILE_NOTE
from tests.test_repairs_r1_m import install, run_app_script

IN_FLIGHT = 'The worker stopped while the request was in flight.'
# _finish_loop's fallback for Astra's replayed run (jobs.UNRECORDED_REPLAY_MESSAGE), written out (falsegreen-3).
REPLAY_UNRECORDED = ('The Astra outcome could not be recorded whole (logged). It was replayed from a recorded response '
                     'and called no vendor, so nothing was sent. The outcome is unknown; reconcile it before any new '
                     'attempt.')
CLOSE_NOTE = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'


def aged(job):
    """``job`` as the stale sweep finds a stage a dead worker left: started longer ago than STALE_RUNNING_SECONDS."""
    models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))


def recorded(run):
    return [(e.turn, e.state, e.http_status) for e in run.exchanges.order_by('turn')]


def served(encounter, run):
    """(state, sent) of ``run`` as the owner's trace serves it."""
    for participant in serializers.trace_json(encounter)['participants']:
        for item in participant['runs']:
            if item['id'] == str(run.pk):
                return item['state'], item['sent']
    raise AssertionError(f'the trace does not serve run {run.pk}')


# --- sends-1: nothing more is sent once the session that holds the provider lock has ended ----------------------------

def lock_free_elsewhere(other, wait=0.0):
    """Whether another database session can take the installation-wide provider lock (what jobs._send and the access
    check's _single_flight ask) now, or within ``wait`` seconds; released again at once."""
    deadline = time.monotonic() + wait
    while not other.try_lock():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    other.unlock()
    return True


def end_session_by_socket():
    """The worker's database session ends: the client side of its socket is shut down, so its backend sees the
    disconnect and exits, as after pg_terminate_backend or a lost connection. No process is signalled."""
    duplicate = socket.socket(fileno=os.dup(connection.connection.fileno()))
    duplicate.shutdown(socket.SHUT_RDWR)
    duplicate.close()


def end_session_by_server():
    """The worker's database session ends: the server ends it itself once it has been idle (idle_session_timeout)."""
    with connection.cursor() as cursor:
        cursor.execute("SET idle_session_timeout = '150ms'")
    time.sleep(1.5)


@override_settings(**LIVE, **BOTH)
class LockedSessionTests(OperatorReads, OfflineMixin, TransactionTestCase):
    """HARNESS.md 2 and I8: every provider send takes the one installation-wide advisory lock, a lock of the database
    session that took it (jobs._send). No test transaction wraps the pipeline here, as none wraps the worker, so a write
    that meets an ended session lets Django open another one exactly as it does in the worker. Round 4's sends-3 tests
    are here for that reason too: the worker's session ends as _finish_loop writes a run's outcome."""
    create = Harness2Case.create
    runs_of = Harness2Case.runs_of
    run_until = Harness2Case.run_until
    jobs_of = Harness2Case.jobs_of
    kinds = Harness2Case.kinds

    def setUp(self):
        super().setUp()
        # whatever a test leaves of the worker's session, the flush after it and the next test start on a fresh one
        self.addCleanup(connection.close)
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        install_reference_store()
        self.corti = ScriptedCorti(selections=list(Harness2Case.corti_codes))
        self.adapters = {name: LoopParticipant(name, self.tmp) for name in ('astra', 'fable')}
        self.adapters['fable'].first = [answered('fable', FABLE_READING)]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]

        def adapter(name):
            return None if participants.participant_mode(name) == 'disabled' else self.adapters[name]
        for target, kwargs in (('studio.jobs.get_provider', {'return_value': self.corti}),
                               ('studio.participants.get_participant', {'side_effect': adapter})):
            patcher = mock.patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.other = _OtherSession(self)  # another worker's, or the installer's access check's, session

    def loop(self, *, end_in_flight=None, end_after_tools=None):
        """Astra's exchange 1 asks cms_code_facts(['99213']), which the real executor answers; exchange 2 would be its
        final reading. The worker's session ends while exchange 1 is in flight (``end_in_flight``) or right after the
        executor has answered the tool call (``end_after_tools``), before the exchange is recorded. Returns what each
        exchange saw, the encounter and the stage."""
        seen = {}

        def first(body):
            seen['lock free elsewhere during exchange 1'] = lock_free_elsewhere(self.other)
            if end_in_flight:
                end_in_flight()
            return asks('astra', facts_call('call_astra_1', ['99213']))

        def second(body):  # never reached once the session that holds the lock has ended
            seen['lock free elsewhere during exchange 2'] = lock_free_elsewhere(self.other)
            return answered('astra', ASTRA_READING)
        self.adapters['astra'].first = [first, second]
        real_executor = reference_tools.executor

        def executor(workspace, **kwargs):
            run_tool = real_executor(workspace, **kwargs)

            def execute_tool(name, arguments):
                result = run_tool(name, arguments)
                seen['tool answered'] = 'error' not in result[0]
                if end_after_tools:
                    end_after_tools()
                return result
            return execute_tool
        encounter_id = self.create()
        job = self.run_until('astra')
        with mock.patch('studio.jobs.reference_tools.executor', side_effect=executor), \
                self.assertLogs('studio.jobs', level='ERROR') as logged:
            try:
                jobs.run_job(job)
            except DatabaseError as exc:  # the stage met the ended session again: the worker ends there
                seen['run_job raised'] = type(exc).__name__
        seen['logged'] = logged.output
        seen['posted'] = len(self.adapters['astra'].loops_of('first')[0]['bodies'])
        return seen, encounter_id, job

    def assert_nothing_more_was_sent(self, seen):
        self.assertFalse(seen['lock free elsewhere during exchange 1'])  # the worker's session held the lock
        self.assertEqual(seen['posted'], 1)  # exchange 2 was never sent
        self.assertNotIn('lock free elsewhere during exchange 2', seen)

    def assert_recorded_as_lock_lost(self, seen, encounter_id, job):
        self.assertTrue(seen['tool answered'])  # by the real executor, on the session that held the lock
        self.assertNotIn('run_job raised', seen)
        self.assertIn('exchange 1 of participant run', seen['logged'][0])  # its write met the ended session
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, run.error),
                         ('failed', True, jobs.LOOP_LOCK_LOST_MESSAGE.format(number=1, plural='')))
        self.assertEqual(recorded(run), [(1, 'succeeded', 200)])  # caught up with the run's outcome
        self.assertEqual(models.ToolCall.objects.filter(exchange__run=run).count(), 1)
        # the stage ends as a failed participant's does - never as a member's Stop - and the chain goes on (I10); the
        # next stage takes the lock afresh on the session it has
        job.refresh_from_db()
        self.assertEqual((job.state, job.error, job.result['state']), ('succeeded', '', 'failed'))
        self.assertEqual(self.kinds(encounter_id)[-1], 'fable')
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0))  # the ended session's backend has exited

    def test_a_session_ended_while_the_tool_call_was_answered_sends_nothing_more(self):
        seen, encounter_id, job = self.loop(end_after_tools=end_session_by_socket)
        self.assert_nothing_more_was_sent(seen)
        self.assert_recorded_as_lock_lost(seen, encounter_id, job)

    def test_a_session_the_server_ended_while_idle_sends_nothing_more(self):
        seen, encounter_id, job = self.loop(end_after_tools=end_session_by_server)
        self.assert_nothing_more_was_sent(seen)
        self.assert_recorded_as_lock_lost(seen, encounter_id, job)

    def test_control_a_session_ended_while_the_exchange_was_in_flight_is_left_to_the_stale_sweep(self):
        # as before: the loop's next check meets the ended session itself, nothing more is sent, the stage cannot
        # record anything on that session, and the stale sweep settles the run (refutation round 2's recorded residual:
        # nothing of the exchange is recorded, so sent stays false; its unknown outcome still blocks every send, I8)
        seen, encounter_id, job = self.loop(end_in_flight=end_session_by_socket)
        self.assert_nothing_more_was_sent(seen)
        self.assertIn('run_job raised', seen)
        connection.close()  # the worker's next session, as a restarted worker's
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, recorded(run)), ('sending', False, []))
        aged(job)
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.error), ('unknown', False, IN_FLIGHT))
        self.assertEqual(models.Job.objects.get(pk=job.pk).state, 'unknown')
        self.assertEqual(seen['posted'], 1)

    # refutation round 4, sends-2 and falsegreen-1: a lock another session holds is not this session's

    def taken_elsewhere(self, end):
        """``end`` ends the worker's session; then another session - a second worker's, or the access check's - takes
        the provider lock as soon as the ended backend has let it go, and keeps it while the loop asks. Returns the
        callback and a list that says whether the other session took the lock (asserted after the stage: an assertion
        inside the executor would be answered as a failed tool call)."""
        took = []

        def ended():
            end()
            deadline = time.monotonic() + 5.0
            while not self.other.try_lock():
                if time.monotonic() >= deadline:
                    took.append(False)
                    return
                time.sleep(0.05)
            took.append(True)  # kept until the test ends
            self.addCleanup(self.other.unlock)
        return ended, took

    def assert_lock_held_elsewhere_sends_nothing_more(self, end):
        ended, took = self.taken_elsewhere(end)
        seen, encounter_id, job = self.loop(end_after_tools=ended)
        self.assertEqual(took, [True])  # another session held the lock when the loop asked
        self.assertFalse(seen['lock free elsewhere during exchange 1'])
        self.assertEqual(seen['posted'], 1, 'exchange 2 was sent while another session held the provider lock')
        self.assertNotIn('lock free elsewhere during exchange 2', seen)
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, run.error),
                         ('failed', True, jobs.LOOP_LOCK_LOST_MESSAGE.format(number=1, plural='')))
        self.assertEqual(recorded(run), [(1, 'succeeded', 200)])
        job.refresh_from_db()
        self.assertEqual((job.state, job.result['state']), ('succeeded', 'failed'))

    def test_a_lock_another_session_took_once_the_session_ended_is_not_this_session_s(self):
        self.assert_lock_held_elsewhere_sends_nothing_more(end_session_by_socket)

    def test_a_lock_another_session_took_once_the_server_ended_the_session_is_not_this_session_s(self):
        self.assert_lock_held_elsewhere_sends_nothing_more(end_session_by_server)

    # refutation round 4, sends-3: _finish_loop's fallback never records a replayed run as sent

    def replay_whose_outcome_meets_an_ended_session(self, answer, *, end_after_tools=None):
        """Astra is the real ReplayParticipant (it calls no vendor: each exchange sent False, endpoint ''), replaying
        ``answer`` for its first exchange; ``end_after_tools`` ends the worker's session once the real executor has
        answered a tool call. The worker's session then ends as _finish_loop's own transaction writes the run's
        outcome (its first _finish_run), so the fallback writes the run on the session Django opens next. Returns the
        loop's final (outcome, sent, endpoint, error) and the run, read back on a fresh session."""
        replay = ReplayParticipant('astra', self.tmp / 'replay')
        self.adapters['astra'] = replay
        encounter_id = self.create()
        job = self.run_until('astra')
        kind, original, _ = jobs._participant_document(job.revision)
        request = replay.build_request(job.revision.text, jobs._participant_pages(job.revision), kind, original)
        folder = self.tmp / 'replay' / 'astra'
        folder.mkdir(parents=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(answer)
        real_finish, real_executor, finals = jobs._finish_run, reference_tools.executor, []

        def finish_run(run, exchange):
            finals.append((exchange.outcome, exchange.sent, exchange.endpoint, exchange.error))
            if len(finals) == 1:
                end_session_by_socket()
            return real_finish(run, exchange)

        def executor(workspace, **kwargs):
            run_tool = real_executor(workspace, **kwargs)

            def execute_tool(name, arguments):
                result = run_tool(name, arguments)
                if end_after_tools:
                    end_after_tools()
                return result
            return execute_tool
        with mock.patch('studio.jobs._finish_run', side_effect=finish_run), \
                mock.patch('studio.jobs.reference_tools.executor', side_effect=executor), \
                self.assertLogs('studio.jobs', level='ERROR') as logged:
            jobs.run_job(job)
        self.assertIn('the loop outcome of participant run', '\n'.join(logged.output))  # the fallback wrote the run
        connection.close()  # read back on a fresh session
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        return finals[0], run

    def assert_settled_as_a_replay(self, run):
        """Unknown - its outcome could not be recorded, so the encounter waits for a member's reconciliation, as for a
        replayed run the stale sweep settles - and never sent: one rule with may_have_reached_vendor, and no sentence
        about what reached a vendor."""
        self.assertEqual((run.state, run.sent, run.endpoint, run.scope['mode']), ('unknown', False, '', 'replay'),
                         'a replay that reached nothing is recorded sent')
        self.assertEqual(run.error, jobs.UNRECORDED_REPLAY_MESSAGE.format(label='Astra'))
        self.assertEqual(run.error, REPLAY_UNRECORDED)  # the sentence itself, not only its constant (falsegreen-3)
        self.assertFalse(jobs.may_have_reached_vendor(models.ProviderRun.objects.filter(pk=run.pk)).exists())
        self.assertEqual(served(run.encounter, run), ('unknown', False))  # the trace's "Sent: No"
        self.assertTrue(jobs._unreconciled_unknown(run.encounter))

    def test_a_replayed_answer_whose_outcome_meets_an_ended_session_is_never_recorded_sent(self):
        final, run = self.replay_whose_outcome_meets_an_ended_session(answered('astra', ASTRA_READING))
        self.assertEqual(final, ('succeeded', False, '', ''))  # the loop's own final: nothing reached a vendor
        self.assert_settled_as_a_replay(run)
        self.assertEqual(recorded(run), [(1, 'succeeded', None)])  # recorded as it ended, before the session ended
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0))  # the ended session's backend has exited

    def test_nor_a_replayed_loop_that_ended_at_the_lock_check(self):
        final, run = self.replay_whose_outcome_meets_an_ended_session(
            asks('astra', facts_call('call_astra_1', ['99213'])), end_after_tools=end_session_by_socket)
        self.assertEqual(final, ('failed', False, '', jobs.LOOP_LOCK_LOST_MESSAGE.format(number=1, plural='')))
        self.assert_settled_as_a_replay(run)
        self.assertTrue(lock_free_elsewhere(self.other, wait=5.0))


# --- sends-3 and sends-4: the installer's undo settles a run as the sweep does; a replay reached nothing --------------

class SettledAsSentTests(Harness2Case):
    """HARNESS.md 12.7: a run left sending is settled unknown, and sent when an exchange of it that may have reached the
    vendor is recorded - by the stale sweep (jobs.mark_stale) and by the installer's undo (CLOSE_STAGES) alike, through
    one rule (jobs.may_have_reached_vendor). The undo had settled sent as before D5 (sends-3), and the rule counted a
    replayed exchange, which reached nothing, as one that may have reached the vendor (sends-4)."""

    def died_in_exchange_two(self):
        """Astra's exchange 1 (a tool call) is answered and recorded as it ended; the worker dies while exchange 2 is in
        flight. Returns the run and its stage."""
        def dies(body):  # stands in for a SIGKILL or an OOM kill
            raise _WorkerDied()
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])), dies]
        encounter_id = self.create()
        job = self.run_until('astra')
        with self.assertRaises(_WorkerDied):
            jobs.run_job(job)
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, recorded(run)), ('sending', False, [(1, 'succeeded', 200)]))
        return run, job

    def replayed_then_died(self):
        """Astra is the real ReplayParticipant: exchange 1 is replayed from a recording that asks cms_code_facts, which
        the real executor answers; the worker dies while exchange 2 is replayed. Returns the run and its stage."""
        replay = ReplayParticipant('astra', self.tmp / 'replay')
        self.adapters['astra'] = replay
        encounter_id = self.create()
        job = self.run_until('astra')
        kind, original, _ = jobs._participant_document(job.revision)
        request = replay.build_request(job.revision.text, jobs._participant_pages(job.revision), kind, original)
        folder = self.tmp / 'replay' / 'astra'
        folder.mkdir(parents=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(asks('astra', facts_call('call_astra_1', ['99213'])))
        real, replayed = ReplayParticipant._recorded, []

        def recording(adapter, sha256):
            if replayed:
                raise _WorkerDied()
            replayed.append(real(adapter, sha256))
            return replayed[-1]
        with mock.patch.object(ReplayParticipant, '_recorded', autospec=True, side_effect=recording), \
                self.assertRaises(_WorkerDied):
            jobs.run_job(job)
        (exchange,) = replayed
        # the replay reached nothing: it records sent False and calls no endpoint
        self.assertEqual((exchange.outcome, exchange.sent, exchange.endpoint), ('succeeded', False, ''))
        (run,) = self.runs_of(job.encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, run.endpoint, run.scope['mode'], recorded(run)),
                         ('sending', False, '', 'replay', [(1, 'succeeded', None)]))
        return run, job

    def close(self, since):
        return run_app_script(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': CLOSE_NOTE})

    def test_the_undo_settles_a_run_with_an_answered_exchange_as_the_sweep_does(self):
        since = timezone.now() - timedelta(seconds=1)
        closed, closed_job = self.died_in_exchange_two()
        answer = self.close(since)
        self.assertEqual((answer['closed'], answer['kinds'], answer['runs_unknown'], answer['runs_not_sent']),
                         (1, ['astra'], 1, 0))
        closed.refresh_from_db()
        self.assertEqual((closed.state, closed.sent, closed.error), ('unknown', True, IN_FLIGHT))
        self.assertEqual(served(closed.encounter, closed), ('unknown', True))  # the trace's "Sent: Yes"
        self.assertEqual(models.Job.objects.get(pk=closed_job.pk).state, 'failed')
        # the same state settled by the stale sweep, on another encounter
        swept, swept_job = self.died_in_exchange_two()
        aged(swept_job)
        jobs.mark_stale()
        swept.refresh_from_db()
        self.assertEqual((swept.state, swept.sent, swept.error), (closed.state, closed.sent, closed.error))
        self.assertEqual(recorded(closed), recorded(swept))

    def test_the_undo_leaves_sent_false_where_nothing_may_have_reached_the_vendor(self):
        since = timezone.now() - timedelta(seconds=1)

        def dies(body):
            raise _WorkerDied()
        self.adapters['astra'].first = [dies]  # nothing of the run is recorded
        encounter_id = self.create()
        with self.assertRaises(_WorkerDied):
            jobs.run_job(self.run_until('astra'))
        self.close(since)
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((run.state, run.sent, recorded(run)), ('unknown', False, []))

    def test_a_replayed_exchange_never_marks_a_swept_run_sent(self):
        run, job = self.replayed_then_died()
        aged(job)
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.error), ('unknown', False, IN_FLIGHT))
        self.assertEqual(served(run.encounter, run), ('unknown', False))

    def test_nor_a_run_the_undo_settles(self):
        since = timezone.now() - timedelta(seconds=1)
        run, _ = self.replayed_then_died()
        self.close(since)
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.error), ('unknown', False, IN_FLIGHT))


# --- sends-2: recorded as a known limit (HARNESS.md 12.7) -------------------------------------------------------------

class FinalAnswerSweptTests(Harness2Case):
    """sends-2, a known limit recorded in HARNESS.md 12.7 with its cost: a worker that dies after the loop's final
    answer was recorded as it ended and before the run's outcome was recorded (_finish_loop) leaves a run the stale
    sweep settles as unknown, in flight, beside that answer; the encounter waits for a member's reconciliation, which
    sends the identical request again. Pinned so the recorded limit stays true; a repair moves this test with 12.7."""

    def test_known_limit_a_final_answer_recorded_before_the_outcome_is_swept_unknown_and_sent_again(self):
        encounter_id = self.create()
        job = self.run_until('astra')
        with mock.patch('studio.jobs._finish_loop', side_effect=_WorkerDied()), self.assertRaises(_WorkerDied):
            jobs.run_job(job)
        (run,) = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual(recorded(run), [(1, 'succeeded', 200), (2, 'succeeded', 200)])
        final = run.exchanges.get(turn=2)
        self.assertEqual((bytes(final.response_bytes), final.tool_calls.count()), (answered('astra', ASTRA_READING), 0))
        aged(job)
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.error), ('unknown', True, IN_FLIGHT))
        drain()
        self.assertEqual((self.encounter(encounter_id).state, self.sent('fable', 'first')), ('provider_unknown', 0))
        response = self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(run.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        loops = self.adapters['astra'].loops_of('first')
        self.assertEqual(([len(item['bodies']) for item in loops], len({item['request'] for item in loops})),
                         ([2, 2], 1))  # the identical request, sent and paid for again
