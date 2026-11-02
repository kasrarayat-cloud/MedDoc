"""Refutation round 3, R3-SENDS: how a run a dead worker left sending is settled (HARNESS.md 12.7 "Recording a
participant's exchanges").

- sends-3: the installer's undo (ops/install.py CLOSE_STAGES, run in the undone revision's own image) settles a run
  left sending as the stale sweep settles one, sent included: it had recorded a run whose answered exchange is on record
  as never sent.
- sends-4: a replayed exchange reached nothing (the replay records sent False and calls no endpoint), so it never marks
  a run sent, in the sweep or in the undo.

falsegreen-5 (the sweep's rule for a recorded failed or unknown exchange) is pinned in tests.test_harness2_r2_peer
RecordedAsItEndsTests. Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake; Astra and
Fable are the real replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline), their
tool calls answered by CPT Studio's real CMS tool executor over a synthetic reference store; sends-4 uses the real
ReplayParticipant with a recording.
"""
from datetime import timedelta
from unittest import mock

from django.utils import timezone

from studio import jobs, models, serializers
from studio.participants.replay import ReplayParticipant
from tests.test_harness2_pipeline import Harness2Case, asks, facts_call
from tests.test_harness_pipeline import _WorkerDied
from tests.test_repairs_r1_m import install, run_app_script

IN_FLIGHT = 'The worker stopped while the request was in flight.'
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
