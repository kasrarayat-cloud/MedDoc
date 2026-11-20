"""studio.jobs (BUILD-SPEC 3): stage_code with a fake coder - the happy path, reuse of a paid read after a crash, an
unknown outcome, the spending ceiling, holds, a Stop between the sends, the provider slot locks and the worker's
threads. Synthetic documents only; nothing reaches the network."""
import io
import signal
import tempfile
import threading
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import anthropic
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings

from studio import jobs, models
from studio.fable import client as fable_client
from studio.fable import document as fable_document
from studio.fable import pricing, prompts
from tests.support import coding as f

Round, Run, Job = models.CodingRound, models.ProviderRun, models.Job


class FakeResponse:
    def __init__(self, status):
        self.status_code, self.headers, self.request = status, {'request-id': 'req_error'}, object()


def refused(cls, status, error_type):
    error = cls(f'Error code: {status}', response=FakeResponse(status),
                body={'type': 'error', 'error': {'type': error_type, 'message': 'synthetic'}})
    return fable_client.status_outcome(error, latency_ms=10.0)


READER = f.reader_result([f.code('45385', 'ready'),
                          f.code('45380', 'needs_answer', question='Was a biopsy taken from a separate site?')],
                         questions=[{'question': 'Was a biopsy taken from a separate site?', 'affects': ['45380']}],
                         problems=['The note is not signed.'])
CHECKER = f.checker_result([f.review('45385', 'agree'), f.review('45380', 'agree', status='needs_answer')],
                           missed=[{'code': '45378', 'units': 1, 'modifiers': [], 'status': 'ready',
                                    'reason': 'A diagnostic colonoscopy is documented.', 'evidence': [],
                                    'question': None}])


class _Crash(BaseException):
    """A worker that dies: nothing catches it."""


class CodingCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.originals = tempfile.TemporaryDirectory()
        cls.override = override_settings(ORIGINALS_DIR=Path(cls.originals.name))
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        cls.originals.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.user, service_date='2026-10-05', insurance='medicare')
        self.rev = f.upload(self.enc, self.user)

    def use(self, fake):
        patcher = mock.patch.object(fable_client, 'coder', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def run_next(self):
        job = jobs.claim_next()
        self.assertIsNotNone(job)
        jobs.run_job(job)
        job.refresh_from_db()
        return job

    def start(self, encounter=None, revision=None, trigger=Round.UPLOAD):
        return jobs.start_round(encounter or self.enc, revision or self.rev, trigger, self.user)

    def runs(self, purpose=None, encounter=None):
        runs = Run.objects.filter(encounter=encounter or self.enc).order_by('created_at')
        return list(runs.filter(purpose=purpose) if purpose else runs)


class HappyPathTests(CodingCase):
    def test_a_round_is_read_checked_combined_and_recorded(self):
        reader_msg, checker_msg = f.reader_message(READER), f.checker_message(CHECKER)
        fake = self.use(f.FakeCoder(reader=f.succeeded(reader_msg), checker=f.succeeded(checker_msg)))
        round_ = self.start()
        self.assertEqual((round_.number, round_.state, round_.trigger), (1, Round.QUEUED, Round.UPLOAD))
        self.assertEqual(round_.context, {'service_date': '2026-10-05', 'insurance': 'medicare', 'answers': []})
        job = self.run_next()
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        self.assertEqual((job.state, job.kind, job.idempotency_key), (Job.SUCCEEDED, 'code', f'code:{round_.pk}'))
        self.assertEqual(fake.roles(), ['reader', 'checker'])
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual([(c['code'], c['status'], c['listed_by']) for c in round_.codes],
                         [('45385', 'ready', 'reader'), ('45380', 'needs_answer', 'reader'),
                          ('45378', 'needs_review', 'checker')])
        self.assertEqual([q['text'] for q in round_.questions], ['Was a biopsy taken from a separate site?'])
        self.assertEqual(round_.problems, ['The note is not signed.'])
        self.assertEqual(set(round_.citations), {'45385', '45380', '45378'})
        self.assertEqual(round_.citations['45385'][0], {'text': 'removed by cold snare', 'page': 1, 'source': 'reader'})
        self.assertEqual(round_.reader_result, READER)
        self.assertEqual(round_.checker_result, CHECKER)
        self.assertEqual(self.enc.state, 'awaiting_answer')
        reader_run, checker_run = self.runs()
        self.assertEqual((round_.reader_run_id, round_.checker_run_id), (reader_run.pk, checker_run.pk))
        for run, purpose, msg in ((reader_run, jobs.READER, reader_msg), (checker_run, jobs.CHECKER, checker_msg)):
            self.assertEqual((run.purpose, run.provider, run.adapter_version, run.state, run.sent),
                             (purpose, 'anthropic', 'cptstudio-fable-coder@1', Run.SUCCEEDED, True))
            self.assertEqual((run.requested_model, run.returned_model, run.http_status),
                             ('claude-fable-5-2', 'claude-fable-5-2', 200))
            self.assertEqual(bytes(run.response_bytes), fable_client.canonical(msg))
            self.assertEqual(run.usage, msg['usage'])
            self.assertEqual(run.provider_request_id, 'req_synthetic')
            self.assertEqual((run.scope['round'], run.scope['fallback'], run.scope['effort']),
                             (str(round_.pk), False, 'max'))
            self.assertEqual(run.service_date.isoformat(), '2026-10-05')
            source = run.request_body['messages'][0]['content'][0]['source']
            self.assertEqual(source['data'], {'$original_sha256': self.rev.source_file.sha256,
                                              '$original_bytes': len(f.PDF_BYTES)})
        checker_text = fake.calls[1][1].params['messages'][0]['content'][1]['text']
        self.assertIn('"code": "45380"', checker_text)
        self.assertIn('date of service: 2026-10-05; insurance: Medicare.', checker_text)
        self.assertEqual(fake.calls[1][1].params['system'], prompts.CHECKER_SYSTEM)
        events = list(models.AuditEvent.objects.filter(encounter=self.enc).values_list('event', flat=True))
        self.assertEqual(events.count('provider.sending'), 2)
        self.assertIn('coding.round_done', events)

    def test_answers_go_into_the_next_rounds_context_and_instruction(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER))))
        first = self.start()
        self.run_next()
        models.CodingAnswer.objects.create(encounter=self.enc, round=first, question='Was a biopsy taken?',
                                           answer='Yes, from the ascending colon.', answered_by=self.user)
        second = self.start(trigger=Round.ANSWERS)
        self.assertEqual(second.number, 2)
        self.assertEqual(second.context['answers'], [{'question': 'Was a biopsy taken?',
                                                      'answer': 'Yes, from the ascending colon.'}])
        self.run_next()
        reader_text = fake.calls[2][1].params['messages'][0]['content'][1]['text']
        self.assertIn('Q: Was a biopsy taken?\nA: Yes, from the ascending colon.', reader_text)
        self.assertEqual(len(self.runs(jobs.READER)), 2)  # a new round reads afresh

    def test_a_round_refuses_to_start_while_another_runs(self):
        self.start()
        with self.assertRaises(jobs.Refused):
            self.start()

    def test_a_message_served_by_a_fallback_is_marked_and_used(self):
        used = f.usage(iterations=[{'type': 'message', 'input_tokens': 5, 'output_tokens': 0},
                                   {'type': 'fallback_message', 'model': 'claude-opus-4-8', 'input_tokens': 5,
                                    'output_tokens': 9}])
        self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER, used=used)),
                             checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual(round_.state, Round.DONE)
        self.assertIs(self.runs(jobs.READER)[0].scope['fallback'], True)
        self.assertIs(self.runs(jobs.CHECKER)[0].scope['fallback'], False)


class ReuseTests(CodingCase):
    def test_a_crash_between_the_sends_pays_for_one_reader_only(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        job = jobs.claim_next()
        with mock.patch.object(jobs, 'spent_usd', side_effect=[Decimal(0), _Crash()]):
            with self.assertRaises(_Crash):
                jobs.run_job(job)
        self.assertEqual(Job.objects.get(pk=job.pk).state, Job.RUNNING)  # the worker died mid-stage
        jobs.mark_stale(startup=True)
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        self.assertEqual((Job.objects.get(pk=job.pk).state, round_.state, self.enc.state),
                         (Job.CANCELLED, Round.CANCELLED, 'stopped'))
        resumed = jobs.resume(self.enc, self.user)
        self.assertTrue(resumed.idempotency_key.startswith(f'code:{round_.pk}:resume:'))
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(fake.roles(), ['reader', 'checker'])
        readers = self.runs(jobs.READER)
        self.assertEqual([(run.state, run.sent) for run in readers], [(Run.SUCCEEDED, True)])
        self.assertEqual(round_.reader_run_id, readers[0].pk)

    def test_an_unknown_reader_outcome_stops_the_round(self):
        unknown = fable_client.unknown_outcome(anthropic.APITimeoutError(request=object()), latency_ms=900_000.0)
        fake = self.use(f.FakeCoder(reader=unknown))
        round_ = self.start()
        job = self.run_next()
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        self.assertEqual(fake.roles(), ['reader'])
        self.assertEqual((job.state, round_.state, round_.failure_kind, self.enc.state),
                         (Job.FAILED, Round.FAILED, 'unknown', 'failed'))
        self.assertEqual(round_.error, jobs.FAILURE_TEXT['unknown'])
        run = self.runs()[0]
        self.assertEqual((run.state, run.sent), (Run.UNKNOWN, True))
        self.assertEqual(self.runs(jobs.CHECKER), [])
        self.assertIsNone(jobs.resume(self.enc, self.user))  # nothing is sent again by itself
        with self.assertRaises(jobs.Refused):
            jobs.reconcile(self.enc, run, self.user, 'too short')
        self.assertTrue(jobs.reconcile(self.enc, run, self.user, 'Checked the console: no charge recorded.'))
        self.assertIsNone(jobs.reconcile(self.enc, run, self.user, 'Checked the console a second time.'))
        retried = jobs.retry(self.enc, self.user)  # a human retry starts a new round
        self.assertEqual((retried.number, retried.trigger), (2, Round.RETRY))

    def test_a_coder_that_raises_records_an_unknown_outcome_at_once(self):
        def raises(request):
            raise RuntimeError('synthetic adapter failure')
        self.use(f.FakeCoder(reader=raises))
        round_ = self.start()
        self.run_next()
        round_.refresh_from_db()
        run = self.runs()[0]
        self.assertEqual((run.state, run.sent, round_.failure_kind), (Run.UNKNOWN, True, 'unknown'))
        self.assertIn('RuntimeError', run.error)

    def test_a_round_left_running_with_no_job_is_cancelled_by_the_sweep(self):
        round_ = self.start()
        Job.objects.filter(encounter=self.enc).update(state=Job.FAILED)  # its stage ended without settling it
        Round.objects.filter(pk=round_.pk).update(state=Round.RUNNING)
        jobs.mark_stale()
        round_.refresh_from_db()
        self.assertEqual(round_.state, Round.RUNNING)  # too recent to be taken for abandoned
        Round.objects.filter(pk=round_.pk).update(created_at=round_.created_at - timedelta(hours=1))
        jobs.mark_stale()
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        self.assertEqual((round_.state, self.enc.state), (Round.CANCELLED, 'stopped'))
        self.assertIsNotNone(jobs.resume(self.enc, self.user))

    def test_a_worker_that_dies_while_sending_leaves_the_send_unknown(self):
        def dies(request):
            raise _Crash()
        self.use(f.FakeCoder(reader=dies))
        round_ = self.start()
        job = jobs.claim_next()
        with self.assertRaises(_Crash):
            jobs.run_job(job)
        self.assertEqual(self.runs()[0].state, Run.SENDING)
        jobs.mark_stale(startup=True)
        round_.refresh_from_db()
        run = self.runs()[0]
        self.assertEqual((run.state, run.sent), (Run.UNKNOWN, True))
        self.assertEqual((Job.objects.get(pk=job.pk).state, round_.state, round_.failure_kind),
                         (Job.UNKNOWN, Round.FAILED, 'unknown'))


class FailureTests(CodingCase):
    def outcome_of(self, reader, checker=None):
        fake = self.use(f.FakeCoder(reader=reader, checker=checker))
        round_ = self.start()
        job = self.run_next()
        round_.refresh_from_db()
        return fake, round_, job

    def test_an_unreadable_reader_answer_fails_the_round_and_sends_no_checker(self):
        fake, round_, job = self.outcome_of(f.succeeded(f.message([f.text_block('No JSON at all.')])))
        self.assertEqual((round_.state, round_.failure_kind, job.state), (Round.FAILED, 'unreadable', Job.FAILED))
        self.assertEqual(fake.roles(), ['reader'])

    def test_definite_failures_carry_their_kind_and_the_customers_sentence(self):
        cases = [(f.succeeded(f.message([f.text_block('x')], stop='refusal')), 'declined', jobs.FAILURE_TEXT['declined']),
                 (f.succeeded(f.message([f.text_block('x')], stop='max_tokens')), 'too_long',
                  jobs.FAILURE_TEXT['too_long']),
                 (refused(anthropic.BadRequestError, 400, 'invalid_request_error'), 'document',
                  fable_document.REFUSED_TEXT['pdf']),
                 (refused(anthropic.RateLimitError, 429, 'rate_limit_error'), 'busy', jobs.FAILURE_TEXT['busy'])]
        for outcome, kind, text in cases:
            with self.subTest(kind=kind):
                self.enc = f.encounter(self.ws, self.user)  # each case on a document of its own
                self.rev = f.upload(self.enc, self.user)
                _, round_, _ = self.outcome_of(outcome)
                self.assertEqual((round_.state, round_.failure_kind, round_.error), (Round.FAILED, kind, text))
                self.assertFalse(models.InterpreterHold.objects.exists())

    def test_disabled_coding_sends_nothing(self):
        with mock.patch.object(fable_client, 'coder', return_value=None):
            round_ = self.start()
            self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unavailable'))
        self.assertEqual(self.runs(), [])

    def test_a_live_send_needs_the_recorded_authority(self):
        fake = f.FakeCoder(reader=f.succeeded(f.reader_message(READER)))
        fake.mode = fable_client.LIVE
        with override_settings(AUTHORIZATION_REF=''):
            self.use(fake)
            round_ = self.start()
            self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind, round_.error),
                         (Round.FAILED, 'unavailable', 'Coding is not authorized on this installation.'))
        self.assertEqual(fake.calls, [])

    def test_no_free_slot_queues_the_job_again(self):
        self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER))))
        round_ = self.start()
        with mock.patch.object(jobs, '_take_slot', side_effect=jobs.Requeue('busy slots')), \
                mock.patch.object(jobs, 'REQUEUE_SECONDS', 0):
            job = self.run_next()
        round_.refresh_from_db()
        self.assertEqual((job.state, job.attempts, round_.state), (Job.QUEUED, 0, Round.QUEUED))
        self.assertEqual(self.runs(), [])


class CeilingTests(CodingCase):
    def reader_worst(self):
        document = fable_document.prepare(self.rev)
        request = fable_client.build_request(
            system=prompts.READER_SYSTEM, document=document,
            instruction=prompts.reader_instruction(jobs.context_snapshot(self.enc)), effort=settings.CODING_EFFORT)
        return pricing.worst_case_usd(request.input_bytes, fable_client.MAX_TOKENS)

    def test_a_send_whose_worst_case_passes_the_ceiling_is_never_made(self):
        fake = self.use(f.FakeCoder())
        with override_settings(DOCUMENT_CEILING_USD='0.50'):
            round_ = self.start()
            self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind, round_.error),
                         (Round.FAILED, 'ceiling', 'This document reached its spending limit.'))
        self.assertEqual((fake.calls, self.runs()), ([], []))

    def test_the_checker_counts_what_the_reader_cost(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)), checker=None))
        ceiling = self.reader_worst() + Decimal('0.01')
        with override_settings(DOCUMENT_CEILING_USD=str(ceiling)):
            round_ = self.start()
            self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'ceiling'))
        self.assertEqual(fake.roles(), ['reader'])
        self.assertEqual(jobs.spent_usd(self.rev), pricing.cost_usd(f.usage()))

    def test_unknown_and_unpriced_runs_count_at_their_worst_case(self):
        run = Run.objects.create(encounter=self.enc, revision=self.rev, provider='anthropic', adapter_version='x',
                                 request_sha256='0' * 64, request_body={}, contexts=[], state=Run.UNKNOWN, sent=True,
                                 purpose=jobs.READER, scope={'worst_usd': '7.500000'})
        refused_run = Run.objects.create(encounter=self.enc, revision=self.rev, provider='anthropic',
                                         adapter_version='x', request_sha256='1' * 64, request_body={}, contexts=[],
                                         state=Run.FAILED, sent=True, http_status=400, purpose=jobs.CHECKER,
                                         scope={'worst_usd': '9'})
        self.assertEqual(jobs.spent_usd(self.rev), Decimal('7.5'))
        self.assertIsNone(jobs.run_cost(refused_run))
        self.assertEqual(run.purpose, jobs.READER)


class HoldTests(CodingCase):
    def test_an_account_refusal_sets_a_hold_and_every_round_then_fails_fast(self):
        self.use(f.FakeCoder(reader=refused(anthropic.AuthenticationError, 401, 'authentication_error')))
        round_ = self.start()
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'hold'))
        hold = models.InterpreterHold.objects.get()
        self.assertEqual((hold.reason, hold.http_status, hold.vendor_status, hold.run_id),
                         ('auth', 401, 'authentication_error', self.runs()[0].pk))
        other = f.encounter(self.ws, self.user)
        other_rev = f.upload(other, self.user)
        untouched = self.use(f.FakeCoder())
        second = self.start(other, other_rev)
        self.run_next()
        second.refresh_from_db()
        self.assertEqual((second.state, second.failure_kind, second.error),
                         (Round.FAILED, 'hold', jobs.FAILURE_TEXT['hold']))
        self.assertEqual((untouched.calls, self.runs(encounter=other)), ([], []))
        released = jobs.release_holds(user=self.user, note='Synthetic: the key was replaced.')
        self.assertEqual(len(released), 1)
        self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                             checker=f.succeeded(f.checker_message(CHECKER))))
        third = jobs.retry(other, self.user)
        self.run_next()
        third.refresh_from_db()
        self.assertEqual(third.state, Round.DONE)

    def test_a_rate_limit_sets_no_hold(self):
        self.use(f.FakeCoder(reader=refused(anthropic.RateLimitError, 429, 'rate_limit_error')))
        round_ = self.start()
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual(round_.failure_kind, 'busy')
        self.assertFalse(jobs.standing_holds().exists())


class StopTests(CodingCase):
    def test_a_stop_between_the_sends_ends_the_round_and_resume_reuses_the_reader(self):
        reader = f.succeeded(f.reader_message(READER))

        def reader_then_stop(request):
            jobs.stop_encounter(self.enc, self.user)  # a member presses Stop while the reader runs
            return reader
        fake = self.use(f.FakeCoder(reader=reader_then_stop, checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        job = self.run_next()
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        self.assertEqual((job.state, round_.state, self.enc.state), (Job.CANCELLED, Round.CANCELLED, 'stopped'))
        self.assertEqual(fake.roles(), ['reader'])
        self.assertEqual([run.purpose for run in self.runs()], [jobs.READER])
        jobs.resume(self.enc, self.user)
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(fake.roles(), ['reader', 'checker'])
        self.assertEqual(len(self.runs(jobs.READER)), 1)

    def test_a_stop_before_the_job_starts_cancels_the_round(self):
        round_ = self.start()
        jobs.stop_encounter(self.enc, self.user)
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        self.assertEqual((round_.state, self.enc.state), (Round.CANCELLED, 'stopped'))
        self.assertIsNone(jobs.claim_next())


@override_settings(CONCURRENT_DOCUMENTS=2)
class ConcurrencyTests(TransactionTestCase):
    """Real threads on their own connections: the provider slots cap concurrent sends at N, and SKIP LOCKED gives each
    thread its own job."""

    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)

    def rounds(self, count):
        made = []
        for index in range(count):
            enc = f.encounter(self.ws, self.user, title=f'Synthetic note {index}')
            made.append(jobs.start_round(enc, f.paste(enc, self.user), Round.UPLOAD, self.user))
        return made

    def test_threads_claim_distinct_jobs(self):
        self.rounds(4)
        barrier, results, lock = threading.Barrier(6), [], threading.Lock()

        def claim():
            try:
                barrier.wait(timeout=20)
                job = jobs.claim_next()
                with lock:
                    results.append(job.pk if job else None)
            finally:
                connection.close()
        threads = [threading.Thread(target=claim) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        claimed = [pk for pk in results if pk is not None]
        self.assertEqual((len(claimed), len(set(claimed)), results.count(None)), (4, 4, 2))

    def test_run_worker_once_drains_with_its_threads_and_exits(self):
        handlers = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGINT, handlers[0])
        self.addCleanup(signal.signal, signal.SIGTERM, handlers[1])
        self.rounds(3)
        names = set()

        def answer(message):
            def send(request):
                names.add(threading.current_thread().name)
                return f.succeeded(message)
            return send
        fake = f.FakeCoder(reader=answer(f.reader_message(READER)), checker=answer(f.checker_message(CHECKER)))
        with mock.patch.object(fable_client, 'coder', return_value=fake):
            call_command('run_worker', once=True, threads=2, stdout=io.StringIO())
        self.assertEqual(sorted(Round.objects.values_list('state', flat=True)), [Round.DONE] * 3)
        self.assertFalse(Job.objects.filter(state__in=[Job.QUEUED, Job.RUNNING]).exists())
        self.assertTrue(names and all(name.startswith('cpt-studio-coder-') for name in names))
        self.assertTrue(models.WorkerBeat.objects.exists())  # one heartbeat for the process

    def test_slot_locks_cap_concurrent_sends_and_every_round_finishes(self):
        made = self.rounds(3)
        lock, state = threading.Lock(), {'in_flight': 0, 'peak': 0, 'requeues': 0, 'threads': set()}
        take = jobs._take_slot

        def counted_take():
            try:
                return take()
            except jobs.Requeue:
                with lock:
                    state['requeues'] += 1
                raise

        def answer(message):
            def send(request):
                with lock:
                    state['in_flight'] += 1
                    state['peak'] = max(state['peak'], state['in_flight'])
                    state['threads'].add(threading.current_thread().name)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:  # hold the slot until both were taken and a third job turned away
                    with lock:
                        if state['peak'] >= 2 and state['requeues'] >= 1:
                            break
                    time.sleep(0.02)
                time.sleep(0.05)
                with lock:
                    state['in_flight'] -= 1
                return f.succeeded(message)
            return send
        fake = f.FakeCoder(reader=answer(f.reader_message(READER)), checker=answer(f.checker_message(CHECKER)))
        deadline = time.monotonic() + 60

        def should_stop():
            return Round.objects.filter(state=Round.DONE).count() == 3 or time.monotonic() > deadline
        with mock.patch.object(fable_client, 'coder', return_value=fake), \
                mock.patch.object(jobs, '_take_slot', counted_take), mock.patch.object(jobs, 'REQUEUE_SECONDS', 0.05):
            jobs.work(should_stop, poll_seconds=0.05, threads=3)
        self.assertEqual(sorted(Round.objects.values_list('state', flat=True)), [Round.DONE] * 3)
        self.assertEqual(state['peak'], 2)
        self.assertGreaterEqual(state['requeues'], 1)
        self.assertGreaterEqual(len(state['threads']), 2)
        self.assertEqual(sorted(fake.roles()), ['checker'] * 3 + ['reader'] * 3)
        self.assertEqual(Run.objects.filter(purpose=jobs.READER).count(), 3)
        self.assertEqual({str(r.pk) for r in made}, set(Run.objects.values_list('scope__round', flat=True)))
