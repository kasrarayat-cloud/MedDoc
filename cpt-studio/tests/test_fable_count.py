"""The spend check's input (BUILD-SPEC 3.2, FIX-SPEC 4): a request's input tokens are counted by the API's free token
count (client.beta.messages.count_tokens, the same model, system, messages, output_config and betas) and the worst case
uses that count, for every attempt the send may make (its server-side fallback's included); when the count cannot be
had nothing is sent and the round fails busy - no estimate from the bytes stands in (a PDF is billed by its pages, which
its bytes do not bound). A coder that calls nothing (a replay) bills nothing and counts nothing. Fake SDK objects and
fake coders only; nothing reaches the network."""
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models
from studio.fable import client, pricing, prompts
from studio.fable import document as fable_document
from tests.support import coding as f
from tests.test_fable_client import request, status_error

KEY = 'sk-ant-synthetic-key-never-sent'
Run, Round = models.ProviderRun, models.CodingRound


class FakeCountSDK:
    def __init__(self, answer, made, **kwargs):
        self.kwargs, self.counts, self.closed, self.answer = kwargs, [], False, answer
        self.beta = SimpleNamespace(messages=SimpleNamespace(count_tokens=self.count_tokens))
        made.append(self)

    def count_tokens(self, **params):
        self.counts.append(params)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer

    def close(self):
        self.closed = True


class CountTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'anthropic.env'
        self.path.write_text(f'ANTHROPIC_API_KEY={KEY}\n')
        os.chmod(self.path, 0o600)
        self.made = []

    def count(self, answer, path=None):
        coder = client.LiveCoder(credentials_file=str(path or self.path), read_timeout=900,
                                 sdk=lambda **kwargs: FakeCountSDK(answer, self.made, **kwargs))
        return coder.count_input_tokens(request())

    def test_the_count_is_the_same_request_without_max_tokens_or_fallbacks(self):
        self.assertEqual(self.count(SimpleNamespace(input_tokens=4321)), 4321)
        sdk = self.made[0]
        (params,) = sdk.counts
        req = request()
        self.assertEqual(set(params), {'model', 'system', 'messages', 'output_config', 'betas', 'timeout'})
        self.assertEqual(params['model'], 'claude-fable-5-2')
        self.assertEqual(params['system'], prompts.READER_SYSTEM)
        self.assertEqual(params['messages'], req.params['messages'])  # the document's data included
        self.assertEqual(params['output_config'], {'effort': 'max'})
        self.assertEqual(params['betas'], ['server-side-fallback-2026-07-01'])
        self.assertIsInstance(params['timeout'], anthropic.Timeout)
        self.assertEqual(params['timeout'].read, client.COUNT_READ_SECONDS)
        self.assertEqual((sdk.kwargs['api_key'], sdk.kwargs['max_retries']), (KEY, 0))
        self.assertTrue(sdk.closed)
        self.assertEqual(client.count_params(req), {key: req.params[key] for key in client.COUNT_KEYS})

    def test_a_count_that_cannot_be_had_is_none(self):
        refused = status_error(anthropic.BadRequestError, 400, 'invalid_request_error')
        for answer in (refused, anthropic.APIConnectionError(request=mock.Mock()), RuntimeError('synthetic'),
                       SimpleNamespace(input_tokens='12'), SimpleNamespace(input_tokens=0), SimpleNamespace(),
                       SimpleNamespace(input_tokens=True)):
            with self.subTest(answer=repr(answer)[:60]):
                self.assertIsNone(self.count(answer))
        self.assertTrue(all(sdk.closed for sdk in self.made))
        self.assertIsNone(self.count(SimpleNamespace(input_tokens=10), path=Path(self.path.parent) / 'missing.env'))

    def test_the_worst_case_covers_every_attempt_a_send_may_make(self):
        top, counted = 96_000, 4_000
        one, two = pricing.worst_case_usd(counted, top), pricing.worst_case_usd(counted, top, attempts=2)
        # one attempt: the counted input and the margin at the input rate, max_tokens at the output rate
        self.assertEqual(one, (Decimal(counted + 2_000) * 8 + Decimal(top) * 40) / 1_000_000)
        # with a fallback, the most two attempts bill, both at claude-fable-5-2's rates (no fallback model costs more):
        # the requested model's, then the fallback's, which reads the first attempt's partial answer as well
        most = pricing.cost_usd({'iterations': [
            {'type': 'message', 'input_tokens': counted + 2_000, 'output_tokens': top},
            {'type': 'fallback_message', 'input_tokens': counted + 2_000 + top, 'output_tokens': top}]})
        self.assertEqual(two, most)
        self.assertGreater(two, 2 * one)

    def test_the_worst_case_needs_a_counted_input(self):
        for unusable in (None, 0, -5, '1000', 1.5, True):
            with self.subTest(unusable=unusable), self.assertRaises(ValueError):
                pricing.worst_case_usd(unusable, 96_000)
        for attempts in (0, -1, 1.5, True, None):
            with self.subTest(attempts=attempts), self.assertRaises(ValueError):
                pricing.worst_case_usd(4_000, 96_000, attempts=attempts)


class CountingCoder(f.FakeCoder):
    """A fake live coder that also counts: ``counted`` is the count, or an exception the count raises."""

    def __init__(self, counted, **answers):
        super().__init__(**answers)
        self.counted, self.counted_requests = counted, []

    def count_input_tokens(self, request):
        self.counted_requests.append(request)
        if isinstance(self.counted, BaseException):
            raise self.counted
        return self.counted


class CountCase(TestCase):
    """A synthetic workspace, member and large uploaded document, on an originals directory of its own."""

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
        # a large document: its bytes alone put a send's estimate far above what its tokens cost
        self.rev = f.upload(self.enc, self.user, data=f.PDF_BYTES + b'%' + b'x' * 3_000_000)

    def run_round(self, coder):
        with mock.patch.object(client, 'coder', return_value=coder):
            round_ = jobs.start_round(self.enc, self.rev, Round.UPLOAD, self.user)
            job = jobs.claim_next()
            jobs.run_job(job)
        round_.refresh_from_db()
        return round_

    def answers(self):
        return {'reader': f.succeeded(f.reader_message(f.reader_result([f.code('45385', 'ready')]))),
                'checker': f.succeeded(f.checker_message(f.checker_result([f.review('45385', 'agree', line='L1')])))}


class SpendCheckTests(CountCase):
    def test_a_counted_send_is_held_to_its_counted_worst_case(self):
        coder = CountingCoder(20_000, **self.answers())
        with override_settings(DOCUMENT_CEILING_USD='10'):  # the 3 MB document's bytes would say more than 11 dollars
            round_ = self.run_round(coder)
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(len(coder.counted_requests), 2)
        reader = Run.objects.get(encounter=self.enc, purpose=jobs.READER)
        request = coder.calls[0][1]
        self.assertIs(coder.counted_requests[0], request)
        expected = pricing.worst_case_usd(20_000, client.MAX_TOKENS, attempts=2)  # its fallback's attempt included
        self.assertEqual((reader.scope['worst_basis'], reader.scope['input_tokens_counted'], reader.scope['attempts'],
                          reader.scope['worst_usd']), ('count', 20_000, 2, pricing.usd(expected)))

    def test_a_count_that_fails_sends_nothing_and_the_round_fails_busy(self):
        for counted in (None, RuntimeError('synthetic count failure')):
            with self.subTest(counted=repr(counted)):
                enc = f.encounter(self.ws, self.user, title=f'Synthetic {counted!r}')
                self.enc, self.rev = enc, f.upload(enc, self.user)  # a small PDF: no estimate would have stopped it
                coder = CountingCoder(counted, **self.answers())
                round_ = self.run_round(coder)
                self.assertEqual((round_.state, round_.failure_kind, round_.error),
                                 (Round.FAILED, 'busy', jobs.FAILURE_TEXT['busy']))
                self.assertEqual(coder.calls, [])  # nothing was sent
                self.assertFalse(Run.objects.filter(encounter=enc).exists())
                self.assertEqual(list(models.AuditEvent.objects.filter(encounter=enc, event='provider.count_failed')
                                      .values_list('data__purpose', flat=True)), [jobs.READER])

    def test_a_coder_that_calls_the_api_and_cannot_count_sends_nothing(self):
        coder = f.FakeCoder(**self.answers())
        coder.count_input_tokens = None  # it has an endpoint and no count
        round_ = self.run_round(coder)
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, 'busy'))
        self.assertEqual(coder.calls, [])
        self.assertFalse(Run.objects.filter(encounter=self.enc).exists())

    def test_a_coder_that_calls_nothing_bills_nothing_and_needs_no_count(self):
        reader = replayed(f.reader_message(f.reader_result([f.code('45385', 'ready')])))
        checker = replayed(f.checker_message(f.checker_result([f.review('45385', 'agree', line='L1')])))
        coder = f.FakeCoder(reader=reader, checker=checker)
        coder.endpoint = ''  # a replay: it answers from a recording and calls nothing
        round_ = self.run_round(coder)
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(coder.counts, [])
        run = Run.objects.get(encounter=self.enc, purpose=jobs.READER)
        self.assertEqual((run.endpoint, run.sent, run.scope['worst_basis'], run.scope['worst_usd']),
                         ('', False, 'replay', '0.000000'))
        self.assertEqual(jobs.spent_usd(self.rev), 0)


def replayed(message):
    """A replay's outcome of ``message``: it was not sent."""
    return client.message_outcome(message, sent=False)


# --- release 1, D4: a token count is a disclosure, recorded before it is made ---------------------------------------------

def _worst_case_before_d4(round_, purpose, request, coder):
    """studio.jobs._worst_case exactly as it was before release 1's D4 (Lane 1's head, bd7587cc3): the reference the
    byte-identity test hands the same request to, so the request the count receives is proven unchanged by the record."""
    if not coder.endpoint:
        return None, Decimal(0)
    counted = jobs._counted_input(coder, request)
    if counted is None:
        jobs.log.warning('round %s: the %s request could not be counted; nothing was sent', round_.pk, purpose)
        jobs.audit.record(round_.encounter.workspace, 'provider.count_failed', encounter=round_.encounter,
                          round=str(round_.pk), purpose=purpose)
        jobs._fail(round_, jobs.BUSY)
    return counted, pricing.worst_case_usd(counted, request.params['max_tokens'], attempts=request.attempts)


class RecordingCountCoder(CountingCoder):
    """A counting coder that reads, at the moment each count is asked for, the provider.counting rows the database holds
    for that request: what a count call can see is what was written before it."""

    def __init__(self, counted, **answers):
        super().__init__(counted, **answers)
        self.seen_at_count = []

    def count_input_tokens(self, request):
        rows = list(models.AuditEvent.objects.filter(event='provider.counting', data__request_sha256=request.sha256)
                    .values_list('data', flat=True))
        self.seen_at_count.append((request.sha256, rows))
        return super().count_input_tokens(request)


class CountRecordTests(CountCase):
    """D4 (ORG-9 (6), ORG-13 (7)): the worker hands the whole request, the document included, to the provider's token
    count before each send, which is a disclosure to the subcontractor; jobs._worst_case writes the AuditEvent
    provider.counting (document, round, purpose, the request's sha256) BEFORE the count runs, for every coder with an
    endpoint, and nothing about what is sent changes."""

    def test_the_count_record_is_written_before_the_count_is_asked_for(self):
        coder = RecordingCountCoder(20_000, **self.answers())
        round_ = self.run_round(coder)
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(len(coder.seen_at_count), 2)  # the reader's count, then the checker's
        for (sha256, rows), purpose, (_, sent) in zip(coder.seen_at_count, (jobs.READER, jobs.CHECKER), coder.calls):
            with self.subTest(purpose=purpose):
                self.assertEqual(sha256, sent.sha256)
                self.assertEqual(rows, [{'round': str(round_.pk), 'purpose': purpose, 'request_sha256': sent.sha256}])
        events = models.AuditEvent.objects.filter(event='provider.counting').order_by('created_at', 'pk')
        self.assertEqual([(event.workspace_id, event.encounter_id, event.actor_id, event.actor_kind) for event in events],
                         [(self.ws.pk, self.enc.pk, None, 'system')] * 2)
        # each count's record precedes its send's record (provider.sending), in the order they were written
        names = list(models.AuditEvent.objects.filter(encounter=self.enc, event__startswith='provider.')
                     .order_by('created_at', 'pk').values_list('event', flat=True))
        self.assertEqual(names, ['provider.counting', 'provider.sending', 'provider.finished'] * 2)

    def test_a_coder_that_calls_nothing_records_no_count(self):
        reader = replayed(f.reader_message(f.reader_result([f.code('45385', 'ready')])))
        checker = replayed(f.checker_message(f.checker_result([f.review('45385', 'agree', line='L1')])))
        coder = f.FakeCoder(reader=reader, checker=checker)
        coder.endpoint = ''  # a replay: no endpoint, so no count and no disclosure
        round_ = self.run_round(coder)
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(coder.counts, [])
        self.assertFalse(models.AuditEvent.objects.filter(event='provider.counting').exists())

    def test_a_count_whose_record_cannot_be_written_is_never_made(self):
        coder = RecordingCountCoder(20_000, **self.answers())
        real = jobs.audit.record

        def record(workspace, event, **data):
            if event == 'provider.counting':
                raise RuntimeError('synthetic: the audit row could not be written')
            return real(workspace, event, **data)
        with mock.patch.object(jobs.audit, 'record', side_effect=record):
            round_ = self.run_round(coder)
        self.assertEqual(round_.state, Round.FAILED)
        self.assertEqual((coder.seen_at_count, coder.calls), ([], []))  # nothing counted, nothing sent
        self.assertFalse(Run.objects.filter(encounter=self.enc).exists())

    def test_the_request_handed_to_the_count_is_byte_identical_to_the_one_built_before_d4(self):
        coder = RecordingCountCoder(20_000, **self.answers())
        round_ = self.run_round(coder)
        self.assertEqual(round_.state, Round.DONE)
        reader_counted = coder.counted_requests[0]
        # 1. the same request, built from the same inputs by the function the stage calls, untouched by D4
        document = fable_document.prepare(self.rev)
        built = client.build_request(system=prompts.READER_SYSTEM, document=document,
                                     instruction=prompts.reader_instruction(round_.context),
                                     effort=settings.CODING_EFFORT)
        for label, value in (('params', lambda r: r.params), ('stored', lambda r: r.stored),
                             ('count body', client.count_params)):
            with self.subTest(label=label):
                self.assertEqual(client.canonical(value(reader_counted)), client.canonical(value(built)))
        self.assertEqual((reader_counted.sha256, reader_counted.attempts), (built.sha256, built.attempts))
        # 2. the code path before D4 and the one after, on the same request: the count receives the same object, the
        # same bytes, and gives the same figures
        before, after = RecordingCountCoder(20_000), RecordingCountCoder(20_000)
        old = _worst_case_before_d4(round_, jobs.READER, built, before)
        new = jobs._worst_case(round_, jobs.READER, built, after)
        self.assertEqual(old, new)
        self.assertIs(before.counted_requests[0], built)
        self.assertIs(after.counted_requests[0], built)
        self.assertEqual(client.canonical(client.count_params(before.counted_requests[0])),
                         client.canonical(client.count_params(after.counted_requests[0])))
        # and only the new path left its record, before its count
        self.assertEqual(before.seen_at_count[0][1], after.seen_at_count[0][1][:-1])
        self.assertEqual(after.seen_at_count[0][1][-1], {'round': str(round_.pk), 'purpose': jobs.READER,
                                                         'request_sha256': built.sha256})
