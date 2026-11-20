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
from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models
from studio.fable import client, pricing, prompts
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


class SpendCheckTests(TestCase):
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
