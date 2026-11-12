"""Refutation round 5, R5-SENDS: what the installer says when an access check does not pass (ops/install.py
participant_access_check and access_check_failure; ops/INSTALL.md, the app phase and Recovery notes).

- sends-1: a check that exited non-zero was reported as "it exited 1." whatever it had said, and every failure was
  given one cause and one remedy: "fix the credentials or the vendor account and run --phase app again with
  --access-check, or install with that participant disabled". The installer knows no cause. Refutation round 4 made the
  check print its receipt when its loop stops at the provider-lock question, and that receipt records that the vendor
  answered (HTTP 200, req_turn_1) and that CPT Studio stopped the loop; the in-flight refusal sends nothing at all, and
  says so on stderr. Now a non-zero exit's problem is what the check's output says: its receipt's error, or, when its
  receipt gives none or there is none, the last non-empty line of its stderr. Each is repeated only whole and only
  up to 300 characters, otherwise named and never cut, and only once the credential scan has found no credential value
  in what it wrote. The phase's failure names no cause: the pair stays installed with those participants live, this
  phase's receipt records each check (its JSON receipt, if it wrote one, and the path of its log, where what it wrote
  was recorded), and the operator runs --phase app again with --access-check once the cause is known, or installs with
  that participant disabled.

The inputs are the access check's own output, as the round-5 refutation lens and its verifier captured it at
0ca5e6623 from `manage.py participant_access_check --participant astra` (the command as the one-shot runs it, through
BaseCommand.run_from_argv), with the suite's synthetic key and a fake vendor session: the lock-stop receipt as printed
(the check's database session ended after exchange 1, tests.test_harness2_r4_sends AccessCheckLockTests' path), the
lock-lost, vendor-refusal and passing receipts but for the times and client request ids each run makes afresh, and
what it wrote on stderr. Every other input (a refused reading's receipt, a long error, a traceback, a long line, a
long stderr, nothing at all) is written here. A guard reads the captured sentences back from the command and from
studio/jobs.py, so they stay the command's.

Refutation round 6, R6-SENDS (parity-1): the vendor-refusal receipt's error is no longer the captured one, "OpenAI
answered HTTP 401; the response body is retained." - whose last clause is the adapters' for the pipeline, which
keeps the answer, and false in the access check, which keeps no copy of it - but what the command prints for the
captured answer since round 6: the error code that answer gives, and that the access check keeps no copy of the
response body. The guard reads that sentence back from the command's own constants, and
tests.test_harness2_r6_sends has the command print it for the captured answer and compares it with VENDOR_401_ERROR
here. Run from cpt-studio/ (no Docker, sudo, network or database):

    python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import ast
import hashlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402
from test_install_harness import OPENAI_VALUE, OTHER, REVISION, RULING, AppWorld, app_args  # noqa: E402
from test_install_harness2 import module_constants  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


APP_ROOT = Path(__file__).resolve().parents[1]
COMMAND = APP_ROOT / 'studio' / 'management' / 'commands' / 'participant_access_check.py'
JOBS = APP_ROOT / 'studio' / 'jobs.py'
HTTP = APP_ROOT / 'studio' / 'participants' / 'http.py'
CORTI = APP_ROOT / 'studio' / 'providers' / 'corti.py'

# What the command wrote on stderr (Django's run_from_argv: the CommandError's class name, its message, a newline).
DID_NOT_PASS = b'CommandError: The Astra access check did not pass: see the receipt.\n'
IN_FLIGHT_SENTENCE = 'Another provider request is in flight; nothing was sent. Try again once it has finished.'
IN_FLIGHT = f'CommandError: {IN_FLIGHT_SENTENCE}\n'.encode()

LOCK_UNCHECKED_ERROR = ('CPT Studio could not check that its database session still holds the provider lock '
                        '(OperationalError), after 1 exchange; nothing more was sent, and the run has no final answer.')
LOCK_LOST_ERROR = ('The database session that held the provider lock, which keeps every other provider request '
                   'waiting, ended while the tool loop ran, after 1 exchange; nothing more was sent, and the run has '
                   'no final answer.')
# Refutation round 6, R6-SENDS (parity-1): moved from the capture's 'OpenAI answered HTTP 401; the response body is
# retained.' to what the command prints for the captured answer (VENDOR_401_BODY) since the round-6 repair.
VENDOR_401_ERROR = ('OpenAI answered HTTP 401 with the error code invalid_api_key; the access check keeps no copy of '
                    "the response body (its sha256 is the receipt's response_sha256).")
# The captured answer (verify-harness-r5/v3-sends-rest, test_zz_v3sends_capture.py's VENDOR_401): its sha256 is the
# receipt's response_sha256 below.
VENDOR_401_BODY = json.dumps({'error': {'message': 'Incorrect API key provided (synthetic).',
                                        'type': 'invalid_request_error', 'param': None,
                                        'code': 'invalid_api_key'}}).encode()

# The lens's capture (refute-harness-r5/sends/logs/access-receipt-capture.json), as the command printed it: the access
# check's session ended right after its executor answered exchange 1's tool call, so the lock question failed; it
# exited 1 with DID_NOT_PASS. The three receipts after it are the verifier's captures of their cases
# (verify-harness-r5/v3-sends-rest/logs/access-captures.json), written as this one with every field that differs
# replaced, but for the times and client request ids each run makes afresh (checked_at, latency_ms, client_request_id).
LOCK_STOP_RECEIPT = {
    'adapter_version': 'openai-responses@cptstudio-harness-2',
    'authorization_ref': 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md',
    'checked_at': '2026-11-02T21:06:20+00:00',
    'client_request_id': 'cptstudio-access-check-c1e01153-831e-4b1f-a525-0328b82c056c',
    'endpoint': 'https://api.openai.com/v1/responses',
    'error': LOCK_UNCHECKED_ERROR,
    'estimated_cost': {'basis': 'estimated from published rates as of 2026-11-01; not reconciled to an invoice',
                       'estimated_usd': '0.031000',
                       'rates': {'as_of': '2026-11-01', 'long_context': False, 'model': 'gpt-6-astra',
                                 'multipliers': {'input': '1', 'output': '1'},
                                 'priced_tokens': {'cached_input': 0, 'input': 2500, 'output': 120},
                                 'usd_per_million_tokens': {'cached_input': '1', 'input': '10', 'output': '50'}}},
    'exchange_count': 1,
    'exchanges': [{'client_request_id': 'cptstudio-access-check-c1e01153-831e-4b1f-a525-0328b82c056c',
                   'http_status': 200, 'latency_ms': 0.158, 'outcome': 'succeeded', 'request_id': 'req_turn_1',
                   'request_sha256': '1b4425d36b43ebc32f206592b97249ad108704d61c26c64eea0f1e00346e8f25',
                   'response_id': 'resp_synthetic_tool_0001',
                   'response_sha256': '30bb684aae7ac2f27916b20d01ffc71f47ca828270e5451f8a3da2e429c676d9',
                   'tool_calls': [{'call_id': 'call_access_1', 'tool': 'cms_code_facts'}], 'turn': 1}],
    'http_status': 200,
    'latency_ms': 0.158,
    'outcome': 'failed',
    'participant': 'astra',
    'reading': None,
    'request_id': 'req_turn_1',
    'request_sha256': '1b4425d36b43ebc32f206592b97249ad108704d61c26c64eea0f1e00346e8f25',
    'requested_model': 'gpt-6-astra',
    'response_id': 'resp_synthetic_tool_0001',
    'response_sha256': '30bb684aae7ac2f27916b20d01ffc71f47ca828270e5451f8a3da2e429c676d9',
    'returned_model': 'gpt-6-astra',
    'sent': True,
    'usage': {'input_tokens': 2500, 'input_tokens_details': {'cached_tokens': 0}, 'output_tokens': 120,
              'output_tokens_details': {'reasoning_tokens': 64}, 'total_tokens': 2620},
    'usage_basis': 'provider_reported_tokens',
}
# The verifier's 'lock_lost_replaced' capture: the session ended and Django opened another, which never took the lock.
LOCK_LOST_RECEIPT = {**LOCK_STOP_RECEIPT, 'error': LOCK_LOST_ERROR}
# The verifier's 'vendor_401' capture: a credentials refusal, for comparison (exit 1, DID_NOT_PASS), its error as the
# command prints it since refutation round 6 (VENDOR_401_ERROR).
VENDOR_401_RECEIPT = {
    **LOCK_STOP_RECEIPT, 'error': VENDOR_401_ERROR, 'estimated_cost': None, 'http_status': 401, 'request_id': 'req_401',
    'response_id': '', 'returned_model': '', 'usage': {}, 'usage_basis': '',
    'response_sha256': '2c6a3aa64330943275ed2cccfbefed0db3adc802c760cf758f06999e9b60e379',
    'exchanges': [{**LOCK_STOP_RECEIPT['exchanges'][0], 'http_status': 401, 'outcome': 'failed',
                   'request_id': 'req_401', 'response_id': '', 'tool_calls': [],
                   'response_sha256': '2c6a3aa64330943275ed2cccfbefed0db3adc802c760cf758f06999e9b60e379'}],
}
# The verifier's 'control_ok' capture: the loop's two exchanges answered and its reading used; it exited 0, no stderr.
PASSING_RECEIPT = {
    **LOCK_STOP_RECEIPT, 'error': '', 'outcome': 'succeeded', 'exchange_count': 2, 'request_id': 'req_turn_2',
    'response_id': 'resp_synthetic_fixture_0001',
    'response_sha256': 'f544bc0a2b76299c4f9b367d028411f3cc2b710c75daa17d43e59f7451a781e1',
    'estimated_cost': {'basis': 'estimated from published rates as of 2026-11-01; not reconciled to an invoice',
                       'estimated_usd': '0.100670',
                       'rates': {'as_of': '2026-11-01', 'exchanges': 2, 'exchanges_priced': 2,
                                 'long_context_exchanges': 0, 'model': 'gpt-6-astra',
                                 'priced_tokens': {'cached_input': 0, 'input': 4912, 'output': 1031},
                                 'usd_per_million_tokens': {'cached_input': '1', 'input': '10', 'output': '50'}}},
    'exchanges': [LOCK_STOP_RECEIPT['exchanges'][0],
                  {'client_request_id': 'cptstudio-access-check-c1e01153-831e-4b1f-a525-0328b82c056c-2',
                   'http_status': 200, 'latency_ms': 0.158, 'outcome': 'succeeded', 'request_id': 'req_turn_2',
                   'request_sha256': '1285fb77c3370980618c8c9ad4adcf2daf0370c05d40e482a9da944ea5cce602',
                   'response_id': 'resp_synthetic_fixture_0001',
                   'response_sha256': 'f544bc0a2b76299c4f9b367d028411f3cc2b710c75daa17d43e59f7451a781e1',
                   'tool_calls': [], 'turn': 2}],
    'reading': {'codes': ['45385', '45380'], 'problems': [], 'refused': False, 'unverified_quotes': 4},
    'usage': {'input_tokens': 4912, 'input_tokens_details': {'cached_tokens': 0}, 'output_tokens': 1031,
              'output_tokens_details': {'reasoning_tokens': 512}, 'total_tokens': 5943},
    'usage_basis': 'provider_reported_tokens_summed_over_exchanges',
}

PAIR_STAYS = 'The pair stays installed with those participants live.'
RECORDED_WHERE = ("Under access_checks, this phase's receipt records each check and, where what it wrote was recorded, "
                  'its JSON receipt (if it wrote one) and the path of its log.')
RERUN = 'Once the cause is known, run --phase app again with --access-check, or install with that participant disabled.'
LINE_SAYS = 'it exited 1, and the last line of text on its stderr says: '
CUT = ('it exited 1, and only the end of its stderr was kept, with no whole line of text in it, so no line is '
       'repeated here.')


def stdout_of(receipt) -> bytes:
    """The command's stdout: its one JSON receipt (json.dumps, sort_keys), then the newline Django's OutputWrapper
    adds."""
    return json.dumps(receipt, sort_keys=True).encode() + b'\n'


def answer(returncode, stdout=b'', stderr=b''):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class AccessCheckFailureTests(TemporaryDirectoryTest):
    """sends-1, through the REAL phase_app in the installer suite's AppWorld (Docker, the database and the in-image
    scripts replaced; participant_access_check, credential_free - its helper body run in-process on synthetic files -
    and access_check_failure run as they are): Astra live and access-checked, Fable disabled."""

    def setUp(self):
        super().setUp()
        self.world = AppWorld(self.tmp)

    def app(self, astra):
        """phase_app with Astra's access check answering ``astra``: the InstallError it raised (or its details)."""
        self.world.answers[('access', 'astra')] = astra
        patches = self.world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_app(install.Context(app_args(self.tmp, fable='disabled', access=True), self.tmp))
        except install.InstallError as error:
            return error
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def failed(self, astra):
        """(the phase's message, Astra's entry) for an access check that did not pass."""
        error = self.app(astra)
        self.assertIsInstance(error, install.InstallError, 'the access check passed')
        return str(error), error.details['access_checks']['astra']

    def assert_names_no_cause(self, message):
        self.assertNotIn('credential', message.lower())
        self.assertNotIn('vendor account', message)
        self.assertNotIn('it exited 1.', message)  # never the exit status alone
        self.assertIn(PAIR_STAYS, message)
        self.assertIn(RECORDED_WHERE, message)
        self.assertTrue(message.endswith(RERUN), message)

    def test_the_lock_stop_receipt_gives_its_own_error_and_no_credentials_advice(self):
        # pin (a): the vendor answered HTTP 200 (req_turn_1); CPT Studio stopped the loop at its lock question
        message, check = self.failed(answer(1, stdout_of(LOCK_STOP_RECEIPT), DID_NOT_PASS))
        self.assertEqual(check['problem'], f'it exited 1, and its receipt says: {LOCK_UNCHECKED_ERROR}')
        self.assertEqual((check['ok'], check['exit'], check['recorded']), (False, 1, True))
        self.assertEqual(check['receipt'], LOCK_STOP_RECEIPT)  # recorded whole: HTTP 200, req_turn_1, the error
        self.assertEqual(Path(check['log']).read_bytes(), stdout_of(LOCK_STOP_RECEIPT) + DID_NOT_PASS)
        self.assertEqual(message, (
            'web and worker running sha256:cccccccccccc (provider disabled, astra live, fable disabled), the stored '
            'list states recomputed (0 changed) and the previous pair removed, but the access check did not pass for '
            f'astra (it exited 1, and its receipt says: {LOCK_UNCHECKED_ERROR}) {PAIR_STAYS} {RECORDED_WHERE} '
            f'{RERUN}'))
        self.assert_names_no_cause(message)

    def test_the_lock_lost_receipt_gives_its_own_error(self):
        message, check = self.failed(answer(1, stdout_of(LOCK_LOST_RECEIPT), DID_NOT_PASS))
        self.assertEqual(check['problem'], f'it exited 1, and its receipt says: {LOCK_LOST_ERROR}')
        self.assertIn(f'(it exited 1, and its receipt says: {LOCK_LOST_ERROR})', message)
        self.assert_names_no_cause(message)

    def test_a_vendor_refusal_gives_its_own_error_and_the_installer_adds_no_cause(self):
        message, check = self.failed(answer(1, stdout_of(VENDOR_401_RECEIPT), DID_NOT_PASS))
        self.assertEqual(check['problem'], f'it exited 1, and its receipt says: {VENDOR_401_ERROR}')
        self.assertEqual(check['receipt']['http_status'], 401)
        self.assert_names_no_cause(message)

    def test_the_in_flight_refusal_gives_its_own_sentence(self):
        # pin (b): it sent nothing and wrote no receipt; its stderr says why
        message, check = self.failed(answer(1, b'', IN_FLIGHT))
        self.assertEqual(check['problem'], f'{LINE_SAYS}CommandError: {IN_FLIGHT_SENTENCE}')
        self.assertEqual((check['ok'], check['exit'], check['recorded'], check['receipt']), (False, 1, True, None))
        self.assertEqual(Path(check['log']).read_bytes(), IN_FLIGHT)
        self.assertIn('Another provider request is in flight; nothing was sent.', message)
        self.assert_names_no_cause(message)

    def test_a_receipt_less_exit_gives_the_last_non_empty_stderr_line_bounded(self):
        # pin (c): the last non-empty line of a multi-line stderr, repeated whole only up to 300 characters
        traceback = (b'Traceback (most recent call last):\n  File "/app/manage.py", line 22, in <module>\n    main()\n'
                     b'RuntimeError: the synthetic check ended here\n\n   \n')
        message, check = self.failed(answer(1, b'', traceback))
        self.assertEqual(check['problem'], f'{LINE_SAYS}RuntimeError: the synthetic check ended here')
        self.assert_names_no_cause(message)
        for size, repeated in ((300, True), (301, False)):
            line = 'E' * (size - 4) + ' end'
            with self.subTest(size=size):
                message, check = self.failed(answer(1, b'not a receipt\n', b'first line\n' + line.encode() + b'\n'))
                if repeated:
                    self.assertEqual(check['problem'], f'{LINE_SAYS}{line}')
                else:
                    self.assertEqual(check['problem'], 'it exited 1, and the last line of text on its stderr is longer '
                                                       'than 300 characters, so it is not repeated here.')
                    self.assertNotIn('EEEE', message)  # never cut: no part of it is repeated
                self.assert_names_no_cause(message)

    def test_only_a_whole_line_of_the_kept_end_of_stderr_is_repeated(self):
        # the installer keeps (and scans) only stderr's last 8,192 bytes: a line that began before them is not whole
        whole = b'x' * 9000 + b'\nRuntimeError: the last line, whole\n'
        message, check = self.failed(answer(1, b'', whole))
        self.assertEqual(check['problem'], f'{LINE_SAYS}RuntimeError: the last line, whole')
        cut = b'RuntimeError: the start of a long line ' + b'y' * 9000 + b'\n'
        message, check = self.failed(answer(1, b'', cut))
        self.assertEqual(check['problem'], CUT)
        self.assertNotIn('yyyy', message)
        # a short end of a line, then blank lines: it is not the line it ends, so it is not repeated either
        short_end = b'RuntimeError: a line of which only the end ' + b'is kept\n' + b'\n' * (8192 - 8)
        self.assertEqual(len(short_end) - short_end.index(b'is kept'), 8192)
        message, check = self.failed(answer(1, b'', short_end))
        self.assertEqual(check['problem'], CUT)
        self.assertNotIn('is kept', message)
        # a last line followed by 8 KiB of blank lines: the kept end is whole lines with no text, and that is said
        blank_end = b'RuntimeError: written before the kept end\n' + b'\n' * 8192
        message, check = self.failed(answer(1, b'', blank_end))
        self.assertEqual(check['problem'], CUT)
        self.assertNotIn('written before', message)  # never kept, never scanned
        # the kept end starts exactly at a line: that line is whole, and is repeated
        at_a_line = b'w' * 9 + b'\n' + b'RuntimeError: kept whole\n' + b'\n' * (8192 - 25)
        self.assertEqual(len(at_a_line) - at_a_line.index(b'RuntimeError'), 8192)
        message, check = self.failed(answer(1, b'', at_a_line))
        self.assertEqual(check['problem'], f'{LINE_SAYS}RuntimeError: kept whole')

    def test_a_receipt_without_an_error_gives_the_stderr_line(self):
        # a refused reading: its exchange succeeded, so the receipt's error is '' and its reading says why
        refused = {**PASSING_RECEIPT, 'reading': {'codes': [], 'problems': ['The reading was refused: synthetic.'],
                                                  'refused': True, 'unverified_quotes': 0}}
        message, check = self.failed(answer(1, stdout_of(refused), DID_NOT_PASS))
        self.assertEqual(check['problem'], LINE_SAYS + DID_NOT_PASS.decode().strip())
        self.assertEqual(check['receipt'], refused)
        self.assert_names_no_cause(message)

    def test_a_receipt_error_over_the_bound_is_named_never_cut(self):
        long_error = 'A sentence of CPT Studio\'s own ' + 'q' * 300 + '.'
        message, check = self.failed(answer(1, stdout_of({**LOCK_STOP_RECEIPT, 'error': long_error}), DID_NOT_PASS))
        self.assertEqual(check['problem'], "it exited 1, and its receipt's error is longer than 300 characters, so it "
                                           'is not repeated here.')
        self.assertNotIn('qqqq', message)
        self.assertNotIn('see the receipt', message)  # the receipt's error stands for what it said
        self.assert_names_no_cause(message)

    def test_an_exit_that_wrote_nothing_says_so(self):
        message, check = self.failed(answer(137))
        self.assertEqual(check['problem'], 'it exited 137, and there is no JSON receipt and no text on its stderr.')
        self.assert_names_no_cause(message)
        message, check = self.failed(answer(3, stdout_of({'participant': 'astra', 'http_status': 401}), b' \n'))
        self.assertEqual(check['problem'], 'it exited 3, and there is no text on its stderr.')

    def test_a_credential_value_on_stderr_is_never_repeated(self):
        # the scan runs first: what it finds keeps the whole output out of the phase's receipt, the problem included
        stderr = f'RuntimeError: 401 for Authorization: Bearer {OPENAI_VALUE}\n'.encode()
        message, check = self.failed(answer(1, b'', stderr))
        self.assertEqual((check['ok'], check['recorded']), (False, False))
        self.assertEqual(check['problem'], 'what it wrote carries a value from its credentials file, or that could not '
                                           'be told; nothing it wrote was recorded.')
        self.assertNotIn(OPENAI_VALUE, message + json.dumps(check))

    def test_a_passing_check_is_unchanged(self):
        # pin (d): exit 0 with its receipt passes, as before
        details = self.app(answer(0, stdout_of(PASSING_RECEIPT)))
        self.assertIsInstance(details, dict)
        check = details['access_checks']['astra']
        self.assertEqual(set(check), {'ok', 'exit', 'recorded', 'receipt', 'log'})  # no problem
        self.assertEqual((check['ok'], check['exit'], check['recorded'], check['receipt']),
                         (True, 0, True, PASSING_RECEIPT))
        self.assertEqual(Path(check['log']).read_bytes(), stdout_of(PASSING_RECEIPT))
        self.assertTrue(details['summary'].endswith('; access checked: astra'), details['summary'])


class WhatTheOperatorSeesTests(TemporaryDirectoryTest):
    """sends-1 end to end through main(): the line the installer prints and the receipt it writes. Each run has its
    own receipts directory: main keeps the directory's lock for the rest of the process, so a second run on the same
    one is refused ("another phase is running on these receipts") and writes no receipt."""

    def run_main(self, astra):
        world = AppWorld(self.tmp)
        world.answers = {('access', 'astra'): astra}
        receipts = self.tmp / f'receipts-{len(list(self.tmp.glob("receipts-*")))}'
        stdout = io.StringIO()
        umask = os.umask(0o077)
        os.umask(umask)
        patches = world.patches() + [
            mock.patch.object(install, 'check_door', return_value={'declaration_commit': OTHER}),
            mock.patch.object(install, 'check_tree', return_value={'mode': 'exact'}),
            mock.patch('sys.stdout', stdout), mock.patch('sys.stderr', io.StringIO())]
        for patcher in patches:
            patcher.start()
        try:
            code = install.main(['--phase', 'app', '--revision', REVISION, '--receipts', str(receipts),
                                 '--provider-mode', 'disabled', '--astra-mode', 'live', '--fable-mode', 'disabled',
                                 '--authorization-ref', RULING, '--access-check'])
        finally:
            for patcher in reversed(patches):
                patcher.stop()
            os.umask(umask)
        printed = json.loads(stdout.getvalue().strip().splitlines()[-1])
        self.assertEqual(Path(printed['receipt']).parent, receipts)  # this run's own receipt
        record = json.loads(Path(printed['receipt']).read_text())
        return code, printed, record

    def test_the_operator_reads_the_check_s_own_words_and_where_they_are(self):
        code, printed, record = self.run_main(answer(1, stdout_of(LOCK_STOP_RECEIPT), DID_NOT_PASS))
        self.assertEqual((code, printed['ok']), (1, False))
        self.assertIn(f'(it exited 1, and its receipt says: {LOCK_UNCHECKED_ERROR})', printed['summary'])
        self.assertNotIn('credential', printed['summary'].lower())
        astra = record['details']['access_checks']['astra']
        self.assertEqual(astra['receipt'], LOCK_STOP_RECEIPT)  # where the summary says it is
        self.assertTrue(Path(astra['log']).exists())
        self.assertEqual(record['error'], printed['summary'])
        code, printed, record = self.run_main(answer(1, b'', IN_FLIGHT))
        self.assertIn(f'({LINE_SAYS}CommandError: {IN_FLIGHT_SENTENCE})', printed['summary'])

    def test_the_operator_reads_what_the_check_says_of_a_vendor_s_refusal(self):
        # refutation round 6, R6-SENDS (parity-1): the error code the vendor's answer gives, and that the access check
        # keeps no copy of the response body - never that the body is retained, which nothing did
        code, printed, record = self.run_main(answer(1, stdout_of(VENDOR_401_RECEIPT), DID_NOT_PASS))
        self.assertEqual((code, printed['ok']), (1, False))
        self.assertIn(f'(it exited 1, and its receipt says: {VENDOR_401_ERROR})', printed['summary'])
        astra = record['details']['access_checks']['astra']
        self.assertEqual(astra['receipt'], VENDOR_401_RECEIPT)
        self.assertNotIn('retained', (printed['summary'] + json.dumps(astra)).lower())


class TheInputsAreTheCommandsOwnTests(unittest.TestCase):
    """The sentences these tests feed the installer are the command's and jobs.py's own, read back with ast (no Django
    code is imported here), so a change to them is seen here."""

    def test_the_captured_sentences_are_the_command_s(self):
        constants = module_constants(COMMAND, ('LOCK_UNCHECKED',))
        self.assertEqual(constants['LOCK_UNCHECKED'].format(error='OperationalError', number=1, plural=''),
                         LOCK_UNCHECKED_ERROR)
        lock_lost = module_constants(JOBS, ('LOOP_LOCK_LOST_MESSAGE',))['LOOP_LOCK_LOST_MESSAGE']
        self.assertEqual(lock_lost.format(number=1, plural=''), LOCK_LOST_ERROR)
        source = COMMAND.read_text(encoding='utf-8')
        strings = {node.value for node in ast.walk(ast.parse(source))
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertIn(IN_FLIGHT_SENTENCE, strings)  # _single_flight's refusal, before anything is sent
        self.assertIn(" access check did not pass: see the receipt.", strings)  # the f-string's tail

    def test_the_vendor_refusal_s_sentence_is_the_command_s(self):
        # refutation round 6, R6-SENDS (parity-1): VENDOR_401_ERROR read back from the command's constants. RETAINED
        # is the clause the adapters end their sentence with (the tail of an f-string in studio/participants/http.py
        # and in studio/providers/corti.py); the command says KEPT in its place, after NAMED for the code the answer
        # gives (VENDOR_401_BODY, the captured answer).
        constants = module_constants(COMMAND, ('RETAINED', 'KEPT', 'NAMED'))
        for path in (HTTP, CORTI):
            tails = {node.values[-1].value for node in ast.walk(ast.parse(path.read_text(encoding='utf-8')))
                     if isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[-1], ast.Constant)}
            self.assertIn(constants['RETAINED'], tails, path)
        self.assertEqual(hashlib.sha256(VENDOR_401_BODY).hexdigest(), VENDOR_401_RECEIPT['response_sha256'])
        self.assertEqual(json.loads(VENDOR_401_BODY)['error']['code'], 'invalid_api_key')
        self.assertEqual('OpenAI answered HTTP 401' + constants['NAMED'].format(field='code', value='invalid_api_key')
                         + constants['KEPT'], VENDOR_401_ERROR)
        self.assertNotIn('retained', (VENDOR_401_ERROR + json.dumps(VENDOR_401_RECEIPT)).lower())


class TheAccessCheckRequestCountTests(unittest.TestCase):
    """Refutation round 6, R6-SENDS (parity-2): how many real requests --access-check sends, where the operator reads it
    before passing the flag - its help (ops/install.py parse_args) and INSTALL.md's Known limits - with the count
    install.py's own comments and INSTALL.md's app phase already give: for Corti one request, its coding request, and
    for Astra and for Fable one run of the pipeline's tool loop, one request per exchange and at most
    PARTICIPANT_MAX_EXCHANGES, read back here from cptstudio/settings.py. Both said one request per participant; the
    passing Astra check above made two exchanges."""

    def exchanges(self):
        return module_constants(APP_ROOT / 'cptstudio' / 'settings.py',
                                ('PARTICIPANT_MAX_EXCHANGES',))['PARTICIPANT_MAX_EXCHANGES']

    def test_the_flag_s_help_gives_the_count(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'COLUMNS': '400'}), mock.patch('sys.stdout', out), \
                self.assertRaises(SystemExit):
            install.parse_args(['--help'])
        (line,) = [line for line in out.getvalue().splitlines() if line.strip().startswith('--access-check')]
        self.assertEqual(' '.join(line.split()), (
            '--access-check after the app phase, check each live participant with real requests: one coding request '
            'for Corti, and for Astra and for Fable one run of the tool loop, one request per exchange and at most '
            f'PARTICIPANT_MAX_EXCHANGES ({self.exchanges()})'))

    def test_install_md_s_known_limits_give_the_count(self):
        text = (APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8')
        limits = text.split('\n## Known limits\n', 1)[1].split('\n## ', 1)[0]
        (bullet,) = [' '.join(item.split()) for item in limits.split('\n- ') if 'access check' in item]
        self.assertEqual(bullet, (
            "The installer reads a participant's credentials by key NAME only; whether a key works is known only from "
            'the opt-in access check (for each live participant: one real, paid coding request for Corti, and for '
            'Astra and for Fable one run of the tool loop, one real, paid request per exchange and at most '
            f'`PARTICIPANT_MAX_EXCHANGES` ({self.exchanges()})), or from the first live send. A check that fails '
            'leaves the pair installed: retrying it means running `app` again, which switches to a new pair beside '
            'the running one.'))

    def test_install_md_s_app_phase_gives_the_count(self):
        """Refutation round 7, parity-2: the app phase's own paragraph, which R6-SENDS named, still said "one request
        for Corti" after the integration corrected four of the five places it named; Corti's adapter sends its OAuth
        token request before its one coding request."""
        said = ' '.join((APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())
        self.assertIn('`manage participant_access_check --participant <corti|astra|fable>`: one coding request for '
                      'Corti (after the OAuth token request its adapter sends first), and for Astra or Fable one run of '
                      "the pipeline's tool loop, one request per exchange and at most `PARTICIPANT_MAX_EXCHANGES` "
                      f'({self.exchanges()}), whose receipt counts its exchanges.', said)
        self.assertNotIn('one request for Corti', said)

    def test_the_command_s_docstring_and_help_give_the_count(self):
        """Refutation round 7, parity-2: the command's docstring and its --help said "one minimal synthetic request"
        and named no request count for Corti."""
        tree = ast.parse(COMMAND.read_text(encoding='utf-8'))
        doc = ' '.join(ast.get_docstring(tree).split())
        self.assertTrue(doc.startswith("Prove one participant's live access with one minimal synthetic request - for "
                                       'Corti one coding request, after the OAuth token request its adapter sends '
                                       'first; for Astra and Fable, one run of the pipeline\'s tool loop, one request '
                                       'per exchange'), doc)
        (command,) = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Command']
        (value,) = [node.value for node in command.body if isinstance(node, ast.Assign)
                    and [target.id for target in node.targets if isinstance(target, ast.Name)] == ['help']]
        self.assertEqual(ast.literal_eval(value), (
            'Send one minimal synthetic request (for Corti one coding request, after its OAuth token request; for Astra '
            'and Fable, one tool-loop run) to one participant and print a JSON receipt (no secret, no database '
            'write).'))
