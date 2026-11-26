"""studio.jobs (BUILD-SPEC 3): stage_code with a fake coder - the happy path, reuse of a paid read after a crash, an
unknown outcome, the spending ceiling, holds, a Stop between the sends, the provider slot locks and the worker's
threads; and the money rules of the fix pass (FIX-SPEC 4): a send's worst case counts its fallback attempt, a crash
after a recorded outcome never leads to the read being sent again, an unknown outcome waits for the operator's
reconcile, both paid reads are reused after a crash, the ceiling counts every earlier run of the revision (checker runs
and billed failures included), a read reserved but never sent is sent on Resume, and a slot whose database session ended
mid-send is not taken by another send; and the money rules of the second fix pass (FIX-SPEC-2 section 6): a job queued
again and taken over by another thread stays the worker's own, so its checker is paid once, and an answer whose outcome
could not be written stays unknown - in the stage, while it is left sending, and after the stale sweep - so nothing
sends it again before an operator's reconcile. Synthetic documents only; nothing reaches the network."""
import hashlib
import io
import signal
import tempfile
import threading
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import anthropic
from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.db.models.query import QuerySet
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from studio import decisions, jobs, models, storage
from studio.fable import client as fable_client
from studio.fable import document as fable_document
from studio.fable import pricing, prompts
from studio.fable import result as fable_result
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
CHECKER = f.checker_result([f.review('45385', 'agree', line='L1'),
                            f.review('45380', 'agree', line='L2', status='needs_answer')],
                           missed=[{'code': '45378', 'units': 1, 'modifiers': [], 'status': 'ready',
                                    'reason': 'A diagnostic colonoscopy is documented.', 'evidence': [],
                                    'question': None}])


class _Crash(BaseException):
    """A worker that dies: nothing catches it."""


def unknown():
    """A send that timed out after it started: it may have reached the vendor and been billed."""
    return fable_client.unknown_outcome(anthropic.APITimeoutError(request=object()), latency_ms=900_000.0)


def too_long(input_tokens=12_000):
    """A read that stopped at max_tokens: answered, so billed, and failed (too_long)."""
    return f.succeeded(f.message([f.text_block('cut')], stop='max_tokens',
                                 used=f.usage(input_tokens, fable_client.MAX_TOKENS)))


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

    def fresh_document(self):
        """Move this test on to an encounter and revision of its own (for a loop of cases)."""
        self.enc = f.encounter(self.ws, self.user, service_date='2026-10-05', insurance='medicare')
        self.rev = f.upload(self.enc, self.user)

    def dies_at(self, event, nth=1):
        """The worker dies at the ``nth`` audit event named ``event`` (nothing catches it); everything committed before
        it stays, as when the process is killed there."""
        real, seen = jobs.audit.record, []

        def record(workspace, name, **data):
            if name == event:
                seen.append(name)
                if len(seen) == nth:
                    raise _Crash()
            return real(workspace, name, **data)
        return mock.patch.object(jobs.audit, 'record', side_effect=record)


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
        self.assertEqual(set(round_.citations), {'L1', 'L2', 'M1'})  # by line (FIX-SPEC 1)
        self.assertEqual(round_.citations['L1'][0], {'text': 'removed by cold snare', 'page': 1, 'source': 'reader'})
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
                             (str(round_.pk), False, 'high'))  # the coder's effort: R2-33's (D434), 'max' in release 1
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
        with self.assertRaises(jobs.Refused) as waits:  # a human retry waits for the operator's reconcile (FIX-SPEC 4)
            jobs.retry(self.enc, self.user)
        self.assertEqual(str(waits.exception), jobs.RECONCILE_FIRST)
        self.assertEqual(Round.objects.filter(encounter=self.enc).count(), 1)
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


class CrashRecoveryTests(CodingCase):
    """A worker that dies between a send's recorded outcome and the round's write (MONEY-2, FG-1), or between a send's
    reservation and its sending (FG-7): the stale sweep settles the round as the stage would have, nothing paid for is
    sent again, and nothing that was never sent is taken for paid."""

    def crash(self, patcher):
        job = jobs.claim_next()
        with patcher, self.assertRaises(_Crash):
            jobs.run_job(job)
        self.assertEqual(Job.objects.get(pk=job.pk).state, Job.RUNNING)  # the worker died mid-stage
        return job

    # MONEY-2: an outcome recorded, then the crash

    def test_an_unknown_outcome_recorded_before_a_crash_fails_the_round_and_nothing_is_sent_again(self):
        fake = self.use(f.FakeCoder(reader=unknown(), checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        job = self.crash(self.dies_at('provider.finished'))
        jobs.mark_stale(startup=True)
        round_.refresh_from_db()
        self.enc.refresh_from_db()
        (run,) = self.runs()
        self.assertEqual((run.purpose, run.state, run.sent), (jobs.READER, Run.UNKNOWN, True))  # never made not sent
        self.assertEqual((Job.objects.get(pk=job.pk).state, round_.state, round_.failure_kind, round_.error,
                          self.enc.state),
                         (Job.UNKNOWN, Round.FAILED, 'unknown', jobs.FAILURE_TEXT['unknown'], 'failed'))
        self.assertIsNone(jobs.resume(self.enc, self.user))
        with self.assertRaises(jobs.Refused):
            jobs.retry(self.enc, self.user)  # until an operator reconciles the unknown outcome
        self.assertEqual(fake.roles(), ['reader'])
        self.assertTrue(jobs.reconcile(self.enc, run, self.user, 'Checked the console: no charge recorded.'))
        retried = jobs.retry(self.enc, self.user)
        self.assertEqual((retried.number, retried.trigger), (2, Round.RETRY))

    def test_a_billed_failure_recorded_before_a_crash_fails_the_round_with_its_own_kind(self):
        fake = self.use(f.FakeCoder(reader=too_long()))
        round_ = self.start()
        job = self.crash(self.dies_at('provider.finished'))
        jobs.mark_stale(startup=True)
        round_.refresh_from_db()
        (run,) = self.runs()
        self.assertEqual((run.state, run.sent, run.scope['failure_kind']), (Run.FAILED, True, 'too_long'))
        self.assertEqual((Job.objects.get(pk=job.pk).state, round_.state, round_.failure_kind, round_.error),
                         (Job.FAILED, Round.FAILED, 'too_long', jobs.FAILURE_TEXT['too_long']))
        self.assertIsNone(jobs.resume(self.enc, self.user))
        self.assertEqual(fake.roles(), ['reader'])
        self.assertEqual(jobs.retry(self.enc, self.user).number, 2)  # its outcome is known: a human may retry at once

    def test_an_unknown_checker_outcome_recorded_before_a_crash_is_not_sent_again(self):
        for startup in (True, False):  # the worker's first sweep, and the periodic one once the job is stale
            with self.subTest(startup=startup):
                self.fresh_document()
                fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)), checker=unknown()))
                round_ = self.start()
                job = self.crash(self.dies_at('provider.finished', nth=2))
                if not startup:
                    Job.objects.filter(pk=job.pk).update(
                        started_at=timezone.now() - timedelta(seconds=jobs.CODE_STALE_SECONDS + 60))
                jobs.mark_stale(startup=startup)
                round_.refresh_from_db()
                self.assertEqual((Job.objects.get(pk=job.pk).state, round_.state, round_.failure_kind),
                                 (Job.UNKNOWN, Round.FAILED, 'unknown'))
                self.assertIsNone(jobs.resume(self.enc, self.user))
                self.assertEqual(fake.roles(), ['reader', 'checker'])

    def test_a_round_left_running_after_an_unknown_outcome_is_failed_by_the_sweep_not_cancelled(self):
        self.use(f.FakeCoder(reader=unknown()))
        round_ = self.start()
        job = self.crash(self.dies_at('provider.finished'))
        Job.objects.filter(pk=job.pk).update(state=Job.FAILED)  # its stage ended; the round's write did not happen
        Round.objects.filter(pk=round_.pk).update(created_at=round_.created_at - timedelta(hours=1))
        jobs.mark_stale()
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unknown'))
        self.assertIsNone(jobs.resume(self.enc, self.user))

    def test_resume_waits_for_the_reconcile_of_an_unknown_outcome(self):
        self.use(f.FakeCoder(reader=unknown()))
        round_ = self.start()
        self.run_next()
        # the round closed as stopped while a send of it has no known outcome (a close that counted only the sends
        # still in flight, say): a Resume would send that read again
        Round.objects.filter(pk=round_.pk).update(state=Round.CANCELLED, failure_kind='', error='')
        with self.assertRaises(jobs.Refused) as waits:
            jobs.resume(self.enc, self.user)
        self.assertEqual(str(waits.exception), jobs.RECONCILE_FIRST)
        self.assertFalse(Job.objects.filter(encounter=self.enc, state=Job.QUEUED).exists())
        (run,) = self.runs()
        self.assertTrue(jobs.reconcile(self.enc, run, self.user, 'Checked the console: no charge recorded.'))
        self.assertIsNotNone(jobs.resume(self.enc, self.user))  # a human's choice, once the operator has looked

    def test_resume_never_sends_again_a_read_whose_billed_failure_was_closed_as_stopped(self):
        fake = self.use(f.FakeCoder(reader=too_long()))
        round_ = self.start()
        self.run_next()
        Round.objects.filter(pk=round_.pk).update(state=Round.CANCELLED, failure_kind='', error='')  # a close, say
        self.assertIsNone(jobs.resume(self.enc, self.user))
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind, round_.error),
                         (Round.FAILED, 'too_long', jobs.FAILURE_TEXT['too_long']))
        self.assertFalse(Job.objects.filter(encounter=self.enc, state=Job.QUEUED).exists())
        self.assertEqual(fake.roles(), ['reader'])
        self.assertEqual(jobs.retry(self.enc, self.user).number, 2)  # a new round, which a human asked for

    def test_an_error_after_an_unknown_outcome_was_recorded_fails_the_round_as_unknown(self):
        self.use(f.FakeCoder(reader=unknown()))
        round_ = self.start()
        real = jobs.audit.record

        def record(workspace, name, **data):
            if name == 'provider.finished':
                raise RuntimeError('synthetic audit failure')
            return real(workspace, name, **data)
        with mock.patch.object(jobs.audit, 'record', side_effect=record):
            job = self.run_next()
        round_.refresh_from_db()
        self.assertEqual((job.state, round_.state, round_.failure_kind, round_.error),
                         (Job.FAILED, Round.FAILED, 'unknown', jobs.FAILURE_TEXT['unknown']))
        with self.assertRaises(jobs.Refused):
            jobs.retry(self.enc, self.user)

    # FG-1: both reads answered, then the crash

    def test_a_crash_after_the_checker_answered_pays_for_one_checker_only(self):
        for point in ('the combine', "the checker's recorded outcome"):
            with self.subTest(point=point):
                self.fresh_document()
                fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                            checker=f.succeeded(f.checker_message(CHECKER))))
                round_ = self.start()
                self.crash(mock.patch.object(jobs.fable_result, 'combine', side_effect=_Crash())
                           if point == 'the combine' else self.dies_at('provider.finished', nth=2))
                jobs.mark_stale(startup=True)
                round_.refresh_from_db()
                self.assertEqual(round_.state, Round.CANCELLED)  # nothing of it is unsettled: a Resume continues it
                self.assertIsNotNone(jobs.resume(self.enc, self.user))
                self.run_next()
                round_.refresh_from_db()
                checkers = self.runs(jobs.CHECKER)
                self.assertEqual(round_.state, Round.DONE)
                self.assertEqual(fake.roles(), ['reader', 'checker'])  # neither read was paid for twice
                self.assertEqual([(run.state, run.sent) for run in checkers], [(Run.SUCCEEDED, True)])
                self.assertEqual(round_.checker_run_id, checkers[0].pk)
                self.assertEqual(len(self.runs(jobs.READER)), 1)

    # FG-7: a read reserved and never sent

    def stop_during_the_spend_check(self, nth):
        """A member's Stop recorded during the ``nth`` send's spend check: seen after the send's reservation, before it
        is sent."""
        real, seen = jobs.spent_usd, []

        def spent(revision):
            seen.append(revision)
            if len(seen) == nth:
                jobs.stop_encounter(self.enc, self.user)
            return real(revision)
        return mock.patch.object(jobs, 'spent_usd', side_effect=spent)

    def test_a_reader_stopped_after_its_reservation_is_sent_on_resume(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        with self.stop_during_the_spend_check(1):
            job = self.run_next()
        round_.refresh_from_db()
        self.assertEqual((job.state, round_.state, fake.roles()), (Job.CANCELLED, Round.CANCELLED, []))
        self.assertEqual([(run.state, run.sent) for run in self.runs()], [(Run.CANCELLED, False)])
        self.assertIsNotNone(jobs.resume(self.enc, self.user))
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, fake.roles()), (Round.DONE, ['reader', 'checker']))
        self.assertEqual([(run.state, run.sent) for run in self.runs(jobs.READER)],
                         [(Run.CANCELLED, False), (Run.SUCCEEDED, True)])

    def test_a_reader_left_reserved_by_a_dead_worker_is_sent_on_resume(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        real, looks = jobs._stop_requested, []

        def dies_after_the_reservation(job, encounter):  # the third look for a Stop is the one after the reservation
            looks.append(job)
            if len(looks) == 3:
                raise _Crash()
            return real(job, encounter)
        self.crash(mock.patch.object(jobs, '_stop_requested', side_effect=dies_after_the_reservation))
        self.assertEqual([(run.state, run.sent) for run in self.runs()], [(Run.RESERVED, False)])
        jobs.mark_stale(startup=True)
        round_.refresh_from_db()
        self.assertEqual(round_.state, Round.CANCELLED)
        self.assertEqual([(run.state, run.sent) for run in self.runs()], [(Run.NOT_SENT, False)])
        self.assertIsNotNone(jobs.resume(self.enc, self.user))
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, fake.roles()), (Round.DONE, ['reader', 'checker']))
        self.assertEqual([(run.state, run.sent) for run in self.runs(jobs.READER)],
                         [(Run.NOT_SENT, False), (Run.SUCCEEDED, True)])

    def test_a_checker_stopped_after_its_reservation_is_sent_on_resume_and_the_reader_reused(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER))))
        round_ = self.start()
        with self.stop_during_the_spend_check(2):
            self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, fake.roles()), (Round.CANCELLED, ['reader']))
        self.assertIsNotNone(jobs.resume(self.enc, self.user))
        self.run_next()
        round_.refresh_from_db()
        self.assertEqual((round_.state, fake.roles()), (Round.DONE, ['reader', 'checker']))
        self.assertEqual(len(self.runs(jobs.READER)), 1)
        self.assertEqual([(run.state, run.sent) for run in self.runs(jobs.CHECKER)],
                         [(Run.CANCELLED, False), (Run.SUCCEEDED, True)])


class SweptMidway(f.FakeCoder):
    """A FakeCoder that runs ``during_checker_count`` once, while the checker's request is being counted - after the
    reader answered, before the checker is reserved or sent: where a stale sweep and a member's Resume can land."""

    def __init__(self, *args, during_checker_count=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.during_checker_count = during_checker_count

    def count_input_tokens(self, request):
        counted = super().count_input_tokens(request)
        if self.during_checker_count is not None and request.stored['system'] == prompts.CHECKER_SYSTEM:
            hook, self.during_checker_count = self.during_checker_count, None
            hook()
        return counted


@override_settings(CONCURRENT_DOCUMENTS=2)
class LiveHandoffTests(CodingCase):
    """money-live-handoff-double-checker (FIX-SPEC-2 section 6): a code job finds no free provider slot and is queued
    again; the thread that queued it sleeps (REQUEUE_SECONDS) still inside its live block while another thread claims
    the job and runs it. The job is the worker's own - never swept - while ANY of its threads runs it: the first thread
    leaving its block must not unmark the job the second still runs, or once the job is an hour old the periodic sweep
    takes it for dead, cancels its round and offers Resume, and the resumed job and the running one both pay for the
    checker. The two threads are played in turn here, exactly interleaved; the mark has no thread of its own."""

    def test_the_live_mark_holds_while_any_thread_still_runs_the_job(self):
        key = uuid.uuid4()
        with jobs._live(key):            # the thread that queued the job again
            second = jobs._live(key)     # the thread that took it over
            second.__enter__()
        self.assertIn(key, jobs._live_ids(), 'the second thread still runs the job')
        second.__exit__(None, None, None)
        self.assertNotIn(key, jobs._live_ids())

    def test_a_job_taken_over_during_its_requeue_stays_live_and_pays_for_its_checker_once(self):
        outcome = {}

        def an_hour_on_the_sweep_runs_and_a_member_presses_resume():
            Job.objects.filter(pk=job.pk).update(
                started_at=timezone.now() - timedelta(seconds=jobs.CODE_STALE_SECONDS + 60))
            jobs.mark_stale()  # the worker's periodic sweep, as its main thread runs it
            try:
                jobs.resume(self.enc, self.user)  # what the page offers once the round reads interrupted
            except jobs.Refused as refused:
                outcome['resume'] = str(refused)
                return
            outcome['resume'] = 'accepted'
            self.run_next()  # a third thread runs the resumed job: it reuses the paid reader and sends the checker
        fake = self.use(SweptMidway(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER)),
                                    during_checker_count=an_hour_on_the_sweep_runs_and_a_member_presses_resume))
        round_ = self.start()
        job = jobs.claim_next()
        taken, here, real_sleep = {}, threading.current_thread(), time.sleep

        def sleep_while_another_thread_takes_the_job(seconds):
            if taken or threading.current_thread() is not here:  # any other sleep is a sleep
                return real_sleep(seconds)
            claimed = jobs.claim_next()  # the job queued again, claimed by another thread
            taken['job'], taken['live'] = claimed, jobs._live(claimed.pk)
            taken['live'].__enter__()   # its own live block, around its own run_job (below)
            return None
        with jobs._live(job.pk):  # the first thread's block (jobs._worker_thread)
            with mock.patch.object(jobs, '_take_slot', side_effect=jobs.Requeue('every provider slot is in use')), \
                    mock.patch.object(jobs.time, 'sleep', side_effect=sleep_while_another_thread_takes_the_job):
                jobs.run_job(job)
        self.assertEqual(taken['job'].pk, job.pk)
        live_after_the_first_left = job.pk in jobs._live_ids()
        try:
            jobs.run_job(taken['job'])
        finally:
            taken['live'].__exit__(None, None, None)
        round_.refresh_from_db()
        self.assertEqual(fake.roles(), ['reader', 'checker'])  # the checker is paid for once
        self.assertEqual([(run.state, run.sent) for run in self.runs(jobs.CHECKER)], [(Run.SUCCEEDED, True)])
        self.assertEqual(outcome['resume'], jobs.BUSY_MESSAGE)  # the job was never swept: nothing to resume
        self.assertTrue(live_after_the_first_left, 'the thread that took the job over still ran it')
        self.assertEqual((Job.objects.get(pk=job.pk).state, round_.state), (Job.SUCCEEDED, Round.DONE))
        self.assertEqual(Job.objects.filter(encounter=self.enc).count(), 1)
        self.assertNotIn(job.pk, jobs._live_ids())


class UnrecordedOutcomeTests(CodingCase):
    """The reader answered, and its outcome could not be written (_finish_run's write failed): the read may have been
    billed, so it is held UNKNOWN - counted at its worst case against the ceiling, Resume and Retry waiting for an
    operator's reconcile - whichever write records that (money-fg-unrecorded-outcome: _settle_unrecorded's small write;
    money-fg-reconcile-sending-arm: none, the run left 'sending', which blocks Retry as unknown does;
    money-fg-orphan-sweep-not-sent: the stale sweep's orphan loop, which settles it unknown, never not sent)."""

    def setUp(self):
        super().setUp()
        self.fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                         checker=f.succeeded(f.checker_message(CHECKER))))

    def code_with(self, *, settle_fails=False, rounds_fail=False):
        """Run the round's job with the outcome's write failing - and _settle_unrecorded's (``settle_fails``) and the
        round's writes after it (``rounds_fail``) failing too; the job as it ended."""
        broken = {'rounds': False}
        real_update = QuerySet.update

        def refusing_update(queryset, **fields):
            if (settle_fails and queryset.model is Run) or (broken['rounds'] and queryset.model is Round):
                raise DatabaseError('synthetic: the row cannot be written')
            return real_update(queryset, **fields)

        def outcome_not_written(run, outcome, **kwargs):
            broken['rounds'] = rounds_fail
            raise DatabaseError('synthetic: the outcome cannot be written')
        with mock.patch.object(jobs, '_finish_run', side_effect=outcome_not_written), \
                mock.patch.object(QuerySet, 'update', refusing_update), \
                self.assertLogs('studio.jobs', level='ERROR') as logged:
            job = self.run_next()
        self.assertTrue(any('could not be recorded' in line for line in logged.output))
        return job

    def assert_held_until_reconciled(self, round_, run):
        """The read counts at its worst case, and nothing sends it again before an operator has looked."""
        self.assertEqual(jobs._held_cost(run), Decimal(run.scope['worst_usd']))
        self.assertTrue(jobs.awaiting_reconcile(round_), f'a {run.state} read that may have been billed waits for the '
                        'operator\'s reconcile')
        with self.assertRaises(jobs.Refused) as waits:
            jobs.retry(self.enc, self.user)
        self.assertEqual(str(waits.exception), jobs.RECONCILE_FIRST)
        self.assertIsNone(jobs.resume(self.enc, self.user))
        self.assertEqual(self.fake.roles(), ['reader'])

    def test_an_answer_whose_outcome_was_not_written_is_held_unknown(self):
        round_ = self.start()
        job = self.code_with()
        round_.refresh_from_db()
        (run,) = self.runs()
        self.assertEqual((run.state, run.sent, run.error), (Run.UNKNOWN, True, jobs.UNRECORDED_MESSAGE))
        self.assertEqual((job.state, round_.state, round_.failure_kind), (Job.FAILED, Round.FAILED, 'unknown'))
        self.assert_held_until_reconciled(round_, run)
        self.assertTrue(jobs.reconcile(self.enc, run, self.user, 'Checked the console: the charge is listed.'))
        self.assertEqual(jobs.retry(self.enc, self.user).number, 2)  # once the operator has looked, a human may retry

    def test_a_run_left_sending_blocks_a_retry_before_the_sweep_settles_it(self):
        round_ = self.start()
        job = self.code_with(settle_fails=True)
        round_.refresh_from_db()
        (run,) = self.runs()
        self.assertEqual((run.state, job.state, round_.state, round_.failure_kind),
                         (Run.SENDING, Job.FAILED, Round.FAILED, 'unknown'))
        self.assert_held_until_reconciled(round_, run)
        jobs.mark_stale()  # the periodic sweep at once: the orphan loop waits STALE_RUNNING_SECONDS
        run.refresh_from_db()
        self.assertEqual(run.state, Run.SENDING)
        self.assert_held_until_reconciled(round_, run)

    def age(self, *rows):
        for row in rows:
            type(row).objects.filter(pk=row.pk).update(
                created_at=row.created_at - timedelta(seconds=settings.STALE_RUNNING_SECONDS + 60))

    def test_the_sweep_settles_a_run_left_sending_unknown_never_not_sent(self):
        round_ = self.start()
        self.code_with(settle_fails=True)
        (run,) = self.runs()
        self.age(run)
        jobs.mark_stale()
        run.refresh_from_db()
        round_.refresh_from_db()
        self.assertEqual((run.state, run.sent, run.error), (Run.UNKNOWN, True, jobs.ORPHANED_SENDING_MESSAGE))
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unknown'))
        self.assert_held_until_reconciled(round_, run)
        self.assertTrue(jobs.reconcile(self.enc, run, self.user, 'Checked the console: the charge is listed.'))
        self.assertEqual(jobs.retry(self.enc, self.user).number, 2)

    def test_a_round_left_running_with_a_run_left_sending_is_failed_unknown_by_the_sweep(self):
        round_ = self.start()
        job = self.code_with(settle_fails=True, rounds_fail=True)
        round_.refresh_from_db()
        (run,) = self.runs()
        self.assertEqual((run.state, job.state, round_.state), (Run.SENDING, Job.FAILED, Round.RUNNING))
        self.age(run, round_)
        jobs.mark_stale()
        run.refresh_from_db()
        round_.refresh_from_db()
        self.assertEqual((run.state, run.sent), (Run.UNKNOWN, True))
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'unknown'))  # never cancelled for a Resume
        self.assert_held_until_reconciled(round_, run)


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
        return pricing.worst_case_usd(f.COUNTED, request.params['max_tokens'], attempts=request.attempts)

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


class SpendCeilingTests(CodingCase):
    """The per-revision ceiling (BUILD-SPEC 3.2, FIX-SPEC 4): a send's worst case covers every attempt it may make, its
    server-side fallback's included (MONEY-1), and every run already on the revision counts - the checker runs and the
    billed failures of earlier rounds included (FG-2, FG-3)."""

    def most_of_two_attempts(self, counted=f.COUNTED):
        """The most a send with server-side fallbacks can use: the requested model writes max_tokens and declines; the
        fallback reads the request and that partial answer (a streamed fallback continues from the partial's text) and
        writes max_tokens itself."""
        top = fable_client.MAX_TOKENS
        return f.usage(counted + top, top, iterations=[
            {'type': 'message', 'model': fable_client.MODEL, 'input_tokens': counted, 'output_tokens': top},
            {'type': 'fallback_message', 'model': 'claude-opus-4-8', 'input_tokens': counted + top,
             'output_tokens': top}])

    # MONEY-1

    def test_a_send_served_by_a_fallback_never_costs_more_than_it_reserved(self):
        self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER, used=self.most_of_two_attempts())),
                             checker=f.succeeded(f.checker_message(CHECKER))))
        self.start()
        self.run_next()
        (reader,) = self.runs(jobs.READER)
        self.assertIs(reader.scope['fallback'], True)
        self.assertLessEqual(jobs.run_cost(reader), Decimal(reader.scope['worst_usd']))

    def test_the_ceiling_is_never_passed_by_a_send_served_by_a_fallback(self):
        self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                             checker=f.succeeded(f.checker_message(CHECKER))))
        self.start()
        self.run_next()
        spent = jobs.spent_usd(self.rev)
        one_attempt = ((f.COUNTED + pricing.MARGIN_TOKENS) * pricing.RATES['input']
                       + fable_client.MAX_TOKENS * pricing.RATES['output']) / Decimal(1_000_000)
        ceiling = spent + one_attempt + Decimal('0.01')  # room for one attempt, not for the fallback's as well
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER, used=self.most_of_two_attempts())),
                                    checker=f.succeeded(f.checker_message(CHECKER))))
        with override_settings(DOCUMENT_CEILING_USD=str(ceiling)):
            second = self.start(trigger=Round.ANSWERS)
            self.run_next()
        second.refresh_from_db()
        self.assertLessEqual(jobs.spent_usd(self.rev), ceiling)
        self.assertEqual((second.state, second.failure_kind, fake.roles()), (Round.FAILED, 'ceiling', []))

    # FG-2

    def test_the_ceiling_counts_the_billed_checker_of_an_earlier_round(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)),
                                    checker=f.succeeded(f.checker_message(CHECKER, used=f.usage(12_000, 60_000)))))
        self.start()
        self.run_next()
        (reader,), (checker,) = self.runs(jobs.READER), self.runs(jobs.CHECKER)
        reader_cost, checker_cost = jobs.run_cost(reader), jobs.run_cost(checker)
        self.assertEqual((reader_cost, checker_cost), (Decimal('0.216'), Decimal('2.496')))
        # round 2's reader has room for itself and half of round 1's checker: the whole checker counts, so it is refused
        ceiling = reader_cost + Decimal(reader.scope['worst_usd']) + checker_cost / 2
        with override_settings(DOCUMENT_CEILING_USD=str(ceiling)):
            second = self.start(trigger=Round.ANSWERS)
            self.run_next()
        second.refresh_from_db()
        self.assertEqual((second.state, second.failure_kind), (Round.FAILED, 'ceiling'))
        self.assertEqual(fake.roles(), ['reader', 'checker'])
        self.assertEqual(jobs.spent_usd(self.rev), reader_cost + checker_cost)

    def test_the_ceiling_counts_an_unknown_checker_at_its_worst_case(self):
        fake = self.use(f.FakeCoder(reader=f.succeeded(f.reader_message(READER)), checker=unknown()))
        first = self.start()
        self.run_next()
        first.refresh_from_db()
        self.assertEqual(first.failure_kind, 'unknown')
        (reader,), (checker,) = self.runs(jobs.READER), self.runs(jobs.CHECKER)
        self.assertTrue(jobs.reconcile(self.enc, checker, self.user, 'Checked the console: the charge is pending.'))
        held = Decimal(checker.scope['worst_usd'])
        ceiling = jobs.run_cost(reader) + Decimal(reader.scope['worst_usd']) + held / 2
        with override_settings(DOCUMENT_CEILING_USD=str(ceiling)):
            retried = jobs.retry(self.enc, self.user)
            self.run_next()
        retried.refresh_from_db()
        self.assertEqual((retried.state, retried.failure_kind), (Round.FAILED, 'ceiling'))
        self.assertEqual(fake.roles(), ['reader', 'checker'])
        self.assertEqual(jobs.spent_usd(self.rev), jobs.run_cost(reader) + held)

    # FG-3

    def test_the_ceiling_counts_a_billed_failure(self):
        fake = self.use(f.FakeCoder(reader=too_long()))
        first = self.start()
        self.run_next()
        first.refresh_from_db()
        (reader,) = self.runs()
        self.assertEqual((first.failure_kind, reader.state, reader.sent, reader.http_status),
                         ('too_long', Run.FAILED, True, 200))
        billed = jobs.run_cost(reader)
        self.assertEqual(billed, Decimal('3.936'))
        ceiling = Decimal(reader.scope['worst_usd']) + 1  # room for the next read, not for it and what was billed
        with override_settings(DOCUMENT_CEILING_USD=str(ceiling)):
            retried = jobs.retry(self.enc, self.user)
            self.run_next()
        retried.refresh_from_db()
        self.assertEqual((retried.state, retried.failure_kind), (Round.FAILED, 'ceiling'))
        self.assertEqual(fake.roles(), ['reader'])
        self.assertEqual(jobs.spent_usd(self.rev), billed)

    def test_a_failed_send_with_no_usage_and_no_error_status_counts_at_its_worst_case(self):
        Run.objects.create(encounter=self.enc, revision=self.rev, provider='anthropic', adapter_version='x',
                           request_sha256='2' * 64, request_body={}, contexts=[], state=Run.FAILED, sent=True,
                           http_status=200, purpose=jobs.CHECKER, scope={'worst_usd': '6.250000'})
        self.assertEqual(jobs.spent_usd(self.rev), Decimal('6.25'))


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

    @override_settings(CONCURRENT_DOCUMENTS=1)
    def test_a_slot_whose_database_session_ended_mid_send_is_not_taken_by_another_send(self):
        """MONEY-4: a slot is a session lock of the sending thread's connection. When that session ends mid-send (a
        database restart, a terminated backend) the lock goes with it while the send goes on; the worker's own count of
        the sends it has in flight keeps another of its threads from sending in that slot until the send ends."""
        self.rounds(2)
        lock = threading.Lock()
        seen = {'in_flight': 0, 'peak': 0, 'sends': 0, 'ended': []}
        first_in_flight, ended = threading.Event(), threading.Event()

        def answer(message):
            def send(request):
                with lock:
                    seen['in_flight'] += 1
                    seen['peak'] = max(seen['peak'], seen['in_flight'])
                    seen['sends'] += 1
                    first = seen['sends'] == 1
                try:
                    if first:
                        first_in_flight.set()
                        ended.wait(30)
                        deadline = time.monotonic() + 3
                        while time.monotonic() < deadline:  # stay in flight while the other thread tries to send
                            with lock:
                                if seen['peak'] > 1:
                                    break
                            time.sleep(0.02)
                    return f.succeeded(message)
                finally:
                    with lock:
                        seen['in_flight'] -= 1
            return send

        def end_the_slot_holders_session():
            try:
                if not first_in_flight.wait(30):
                    return
                key = jobs.PROVIDER_LOCK_KEY  # a bigint advisory lock shows as classid (high half), objid (low half)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pid FROM pg_locks WHERE locktype = 'advisory' AND classid = %s AND objid = %s"
                                   " AND objsubid = 1 AND database = (SELECT oid FROM pg_database"
                                   " WHERE datname = current_database())", [key >> 32, key & 0xFFFFFFFF])
                    for (pid,) in cursor.fetchall():
                        cursor.execute('SELECT pg_terminate_backend(%s)', [pid])
                        seen['ended'].append(cursor.fetchone()[0])
            finally:
                connection.close()
                ended.set()

        fake = f.FakeCoder(reader=answer(f.reader_message(READER)), checker=answer(f.checker_message(CHECKER)))
        controller = threading.Thread(target=end_the_slot_holders_session)
        controller.start()
        deadline = time.monotonic() + 60

        def should_stop():
            return Round.objects.filter(state=Round.DONE).count() == 2 or time.monotonic() > deadline
        with mock.patch.object(fable_client, 'coder', return_value=fake), \
                mock.patch.object(jobs, 'REQUEUE_SECONDS', 0.05):
            jobs.work(should_stop, poll_seconds=0.05, threads=2)
        controller.join(30)
        self.assertEqual(seen['ended'], [True])  # the slot holder's session did end while its send was in flight
        self.assertEqual(seen['peak'], 1)
        self.assertEqual(sorted(Round.objects.values_list('state', flat=True)), [Round.DONE] * 2)
        first = Run.objects.filter(purpose=jobs.READER).order_by('started_at').first()
        self.assertIs(first.scope.get('slot_lost'), True)  # recorded on the run, for the operator



# --- release 1, refutation finding 6 on the coding path: one practice's files only ------------------------------------------

WORD = b'PK\x03\x04 synthetic word bytes, never opened by anything'
CONVERTED = b'%PDF-1.7\n% the synthetic conversion of this practice\'s own Word file\n%%EOF\n'
FOREIGN = b'%PDF-1.7\n% ZZ-FOREIGN-MARKER: a file in another practice\'s folder\n%%EOF\n'


class OwnFolderTests(CodingCase):
    """A row of one practice that names another practice's file (a corrupted or crafted row) never has that file read on
    the coding path: the original is read through storage.read_own_original bound to the encounter's practice - a refusal
    fails the round 'storage', as an unreadable original does, before anything is counted or sent - the stored
    conversion is never read and the Word file is converted again, and no new round takes the crafted name. For
    legitimate documents every request sent and counted is byte for byte what it was."""

    def foreign_file(self, data=FOREIGN):
        other = f.workspace('Another practice')
        name, digest, _ = storage.store_original(other.pk, data, 'far.pdf')
        return name, digest

    def answers(self):
        return {'reader': f.succeeded(f.reader_message(READER)), 'checker': f.succeeded(f.checker_message(CHECKER))}

    def test_an_original_named_in_another_practices_folder_is_refused_before_anything_is_sent(self):
        name, digest = self.foreign_file()
        with connection.cursor() as cursor:  # SourceFile refuses updates through the ORM: a crafted row
            cursor.execute('UPDATE studio_sourcefile SET storage_name = %s, sha256 = %s WHERE id = %s',
                           [name, digest, self.rev.source_file_id])
        fake = self.use(f.FakeCoder(**self.answers()))  # it would answer, if anything were sent
        with mock.patch.object(storage, '_read_bytes', wraps=storage._read_bytes) as read:
            self.start()
            self.run_next()
        round_ = Round.objects.get(encounter=self.enc)
        crafted = (round_.state, round_.failure_kind, round_.error)
        self.assertEqual(crafted, (Round.FAILED, 'storage', fable_document.STORAGE_TEXT))
        self.assertEqual((fake.counts, fake.calls), ([], []))  # nothing counted, nothing sent
        self.assertFalse(Run.objects.filter(encounter=self.enc).exists())
        self.assertEqual(read.call_count, 0)  # no file was read at all (the store's one read)
        self.assertTrue(decisions.retry_offered(self.enc, round_))
        # exactly how an original of its own practice that no longer reads back fails today
        self.fresh_document()
        storage.stored_path(self.rev.source_file.storage_name).write_bytes(b'%PDF-1.7 changed on the disk %%EOF')
        self.start()
        self.run_next()
        unreadable = Round.objects.get(encounter=self.enc)
        self.assertEqual((unreadable.state, unreadable.failure_kind, unreadable.error), crafted)

    def test_a_name_that_leaves_the_folder_through_dotdot_is_refused_before_anything_is_sent(self):
        # the lens's probe (refute-lane4 repairs, R6): '<A>/../<B>/<file>' passed the first-segment test, and B's bytes
        # were sent and counted for A's document
        name, digest = self.foreign_file()
        for crafted in (f'{self.ws.pk}/../{name}', f'{self.ws.pk}/./../{name}'):
            with self.subTest(crafted=crafted):
                self.fresh_document()
                with connection.cursor() as cursor:  # a crafted row, as above
                    cursor.execute('UPDATE studio_sourcefile SET storage_name = %s, sha256 = %s WHERE id = %s',
                                   [crafted, digest, self.rev.source_file_id])
                fake = self.use(f.FakeCoder(**self.answers()))
                with mock.patch.object(storage, '_read_bytes', wraps=storage._read_bytes) as read:
                    self.start()
                    self.run_next()
                round_ = Round.objects.get(encounter=self.enc)
                self.assertEqual((round_.state, round_.failure_kind, round_.error),
                                 (Round.FAILED, 'storage', fable_document.STORAGE_TEXT))
                self.assertEqual((fake.counts, fake.calls, read.call_count), ([], [], 0))

    def word_document(self):
        """A Word document coded once: its conversion stored in its own practice's folder by round 1."""
        self.enc = f.encounter(self.ws, self.user, service_date='2026-10-05', insurance='medicare')
        self.rev = f.upload(self.enc, self.user, data=WORD, filename='synthetic.docx', media_type=fable_document.DOCX)
        self.use(f.FakeCoder(**self.answers()))
        self.start()
        self.run_next()
        first = Round.objects.get(encounter=self.enc, number=1)
        self.assertEqual(first.view_pdf_sha256, hashlib.sha256(CONVERTED).hexdigest())
        return first

    def code_again(self):
        fake = self.use(f.FakeCoder(**self.answers()))
        self.start(trigger=Round.ANSWERS)
        self.run_next()
        return Round.objects.get(encounter=self.enc, number=2), fake

    def test_a_stored_conversion_named_in_another_practices_folder_is_never_read(self):
        with mock.patch.object(fable_document, 'convert_docx', return_value=CONVERTED) as convert:
            first = self.word_document()
            name, digest = self.foreign_file()
            Round.objects.filter(pk=first.pk).update(view_pdf_storage_name=name, view_pdf_sha256=digest)
            with mock.patch.object(storage, '_read_bytes', wraps=storage._read_bytes) as read:
                second, fake = self.code_again()
        self.assertEqual(second.state, Round.DONE)
        self.assertEqual(convert.call_count, 2)  # converted again, from this practice's own original
        self.assertTrue(read.call_args_list)  # the practice's own original was read
        self.assertNotIn(storage.stored_path(name), [call.args[0] for call in read.call_args_list])
        sent = {request.stored['messages'][0]['content'][0]['source']['data']['$original_sha256']
                for _, request in fake.calls}
        self.assertEqual(sent, {hashlib.sha256(CONVERTED).hexdigest()})  # never the other practice's bytes

    def test_a_new_round_never_takes_a_crafted_rounds_foreign_name(self):
        with mock.patch.object(fable_document, 'convert_docx', return_value=CONVERTED):
            first = self.word_document()
            name, _ = self.foreign_file()
            # the crafted row names another practice's file under the very sha256 the fresh conversion will have
            Round.objects.filter(pk=first.pk).update(view_pdf_storage_name=name)
            second, _ = self.code_again()
        self.assertEqual(second.state, Round.DONE)
        self.assertTrue(storage.in_practice_folder(self.ws.pk, second.view_pdf_storage_name))
        self.assertEqual(storage.stored_path(second.view_pdf_storage_name).read_bytes(), CONVERTED)

    def test_legitimate_documents_send_and_count_the_same_bytes_as_before(self):
        # before this change prepare read the original with its default reader, storage.read_original: the requests built
        # that way, from the same inputs, are the ones the stage now sends and counts, byte for byte
        kinds = {'pdf': dict(), 'txt': dict(data='Synthetic note.\r\nColonoscopy, cold snare.\n'.encode(),
                                            filename='synthetic.txt', media_type='text/plain'),
                 'docx': dict(data=WORD, filename='synthetic.docx', media_type=fable_document.DOCX), 'paste': None}
        for kind, upload in kinds.items():
            with self.subTest(kind=kind):
                self.enc = f.encounter(self.ws, self.user, service_date='2026-10-05', insurance='medicare')
                self.rev = f.paste(self.enc, self.user) if upload is None else f.upload(self.enc, self.user, **upload)
                fake = self.use(f.FakeCoder(**self.answers()))
                with mock.patch.object(fable_document, 'convert_docx', return_value=CONVERTED):
                    self.start()
                    self.run_next()
                    round_ = Round.objects.get(encounter=self.enc)
                    document = fable_document.prepare(self.rev, converter=lambda data: CONVERTED)
                built = [fable_client.build_request(system=prompts.READER_SYSTEM, document=document,
                                                    instruction=prompts.reader_instruction(round_.context),
                                                    effort=settings.CODING_EFFORT),
                         fable_client.build_request(system=prompts.CHECKER_SYSTEM, document=document,
                                                    instruction=prompts.checker_instruction(
                                                        round_.context, fable_result.listing(round_.reader_result)),
                                                    effort=settings.CODING_EFFORT)]
                self.assertEqual(round_.state, Round.DONE)
                self.assertEqual([(fable_client.canonical(request.params), request.sha256) for _, request in fake.calls],
                                 [(fable_client.canonical(request.params), request.sha256) for request in built])
                self.assertEqual([fable_client.canonical(fable_client.count_params(request)) for request in fake.counts],
                                 [fable_client.canonical(fable_client.count_params(request)) for request in built])
