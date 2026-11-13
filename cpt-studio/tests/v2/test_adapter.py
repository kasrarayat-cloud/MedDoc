"""studio/interpretation/adapter.py, design v2's adapter (docs/gemini-migration/FINAL-V2.md 2.4, 2.5, 7.3-7.5, as
AMENDMENT-1.md 7.3 and A11 amend them; step 3b of 8.1). TEXT-ONLY and SYNTHETIC: tests/v2/test_claims.py's synthetic
note and its hand-built pass-1 answer (step 2c's fixtures, written for those tests and checked there against the
acceptance set's DEV-EXCLUSION hashes), appraisal answers built here for that answer's claims, and the synthetic error
bodies of tests/test_interpretation_adapter.py with the trial's recorded 429. Every send goes to a fake session behind
the network guard of tests/test_participants_support, every key is fake, and nothing is sent anywhere.

What is proved, item by item against the done-when of 8.1 step 3b, amendment 1's A11 and the triage's hand-offs:
- the envelope rules for both purposes: modelVersion exactly gemini-4-argon and checked first, no block reason, exactly
  one candidate, finishReason STOP, text parts only, thinking excluded, strict JSON - the same rule and the same
  refusal for a pass-1 and a pass-2 request, at stage 'envelope', in contract/extract_read's Refusal (EnvelopeTests);
- the model pin: the URL names it, the body carries none, another model or none named is a HOLD (model) for both
  passes (EnvelopeTests, ClassificationTests);
- MAX_TOKENS is TOO_LONG for both passes (ClassificationTests, EnvelopeTests);
- a bare 429 holds both passes - a spending cap's 429 carries no quota detail - and is never retried in a loop: one
  exchange, then the run ends (ClassificationTests, SendTests);
- a 402 holds as quota (A11), with its test vector (ClassificationTests, SendTests);
- the claim bound is checked before a request is built: an over-bound claim set gives TOO_LONG and no body, at the
  bound itself a request is built (ClaimBoundTests);
- the appraisal request kind from the revision plus the stored extraction bytes, a pure function of them, its sha256
  the appraise key's source (hand-off 2c:R5), the stored answer bound to this revision's pass-1 request
  (AppraisalRequestTests); pass 1's request (ExtractionRequestTests);
- a text that cannot be framed is ``refused: unbuilt`` with contract/extract_prompt's Unframed reason, never
  participants.http.framed_text's sentence (hand-offs 1a:R2, 2a#5, 2a:R2; UnbuiltTests);
- per-purpose timeouts, pass 2 at D49's 480 and 510 s, from settings.APPRAISER_* (TimeoutTests);
- v1's prompt and read imports removed: the module imports neither, importing it loads neither, and the v2 path
  executes no line of any retired module nor of the v1 surface (ImportTests, TraceTests); v1's surface is unchanged
  (tests/test_interpretation_adapter.py, which no step edits, stays green).
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from studio import interpretation
from studio.interpretation import adapter, holds
from studio.interpretation.contract import (appraise_prompt, appraise_read, claims, extract_prompt, extract_read,
                                            extract_schema, jsonschema)
from studio.interpretation.contract.extract_read import FactKey
from studio.interpretation.contract.types import Attribute, Reason
from studio.interpretation.replay import ReplayInterpreterV2
from studio.participants import http as participants_http
from studio.participants import loop as participants_loop
from studio.participants import prompt as participant_prompt
from studio.providers.base import ProviderUnavailable, canonical_body, request_sha256
from studio.types import PageSpan, ProviderRequest
from tests.test_interpretation_adapter import (ENDPOINT, GEMINI_KEY, PER_MINUTE, TRIAL_429, encoded, envelope,
                                               error_body, error_info, gemini_env, quota_failure, retry_info,
                                               violation, with_parts)
from tests.test_participants_support import FakeClock, FakeResponse, FakeSession, OfflineTestCase, write_file
from tests.v2 import test_claims as fixtures

APP = Path(__file__).resolve().parents[2]
ADAPTER = APP / 'studio' / 'interpretation' / 'adapter.py'
REPLAY = APP / 'studio' / 'interpretation' / 'replay.py'
STUDIO = APP / 'studio'
TEXT = fixtures.NOTE  # step 2c's synthetic colonoscopy note
PAGES = (PageSpan(page=1, start=0, end=len(TEXT)),)
KIND = 'txt'
NAMES = ('gemini', 'google', 'argon')  # no refusal or sentence of this module names a provider or model (D22)
# The 17 retired v1 modules (FINAL-V2 5.0): nothing on the v2 path executes a line of any of them.
RETIRED = ('prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations',
           'mapping', 'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess')
# The v1 surface (adapter's module docstring): what design v2's section never executes.
V1_SURFACE = {'build_request', 'body_problem', 'answer_text', 'get_interpreter', '_v1_prompt', '_v1_read'}
V1_CLASSES = ('Interpreter.', 'GeminiInterpreter.', 'ReplayInterpreter.')


def measured_pins() -> dict:
    """Every pin of FINAL-V2 2.5 a v2 request is built and read under, set to the sha its owning step's own function
    measures on this tree (as the integration owner writes them, DECISIONS D202): the adapter's tests do not depend on
    when the pins are written; the pin tests of steps 0b, 2a and 2c judge the written values."""
    return {**appraise_prompt.pins(),
            'INSTRUCTIONS_SHA256_V2': jsonschema.sha256_of(extract_prompt.INSTRUCTIONS_2),
            'LOCAL_SCHEMA_SHA256_V2': jsonschema.sha256_of(extract_schema.LOCAL_SCHEMA_2),
            'RESPONSE_SCHEMA_SHA256_V2': jsonschema.sha256_of(extract_schema.RESPONSE_SCHEMA_2)}


def no_findings(text, pages, answer):
    """A check that finds nothing (DECISIONS D206's check orchestration is step 3a's; its findings pass through)."""
    return {}


def stored_answer() -> bytes:
    """Pass 1's answer to TEXT as Gemini's envelope stores it: step 2c's hand-built answer, one text part."""
    return encoded(envelope(json.dumps(fixtures.note_answer())))


def appraisal_answer(built: appraise_prompt.Request, verdict: str = 'supports') -> bytes:
    """A synthetic pass-2 answer to ``built``: one verdict per claim, citing the claim's first unit."""
    verdicts = [{'claim': claim.id, 'verdict': verdict, 'attached': 'yes', 'qualifiers': [],
                 'evidence': list(claim.units[:1])} for claim in built.claim_set.claims]
    return encoded(envelope(json.dumps({'verdicts': verdicts, 'unlisted': []})))


def cut_off() -> bytes:
    return encoded(with_parts({'text': '{"verdicts": ['}, finish='MAX_TOKENS'))


def substituted() -> bytes:
    return encoded(envelope(modelVersion='gemini-4-argon-preview'))


def bare_429s() -> dict:
    """The 429s that carry no QuotaFailure (D39: the project's monthly spending cap answered so on 2026-11-10, with only
    a message), each a quota HOLD whatever else it says."""
    return {'RESOURCE_EXHAUSTED, a message alone (the spending cap)': encoded(
                {'error': {'code': 429, 'message': 'Synthetic: your project has exceeded its monthly spending cap.',
                           'status': 'RESOURCE_EXHAUSTED'}}),
            'RESOURCE_EXHAUSTED, an empty detail list': error_body(429, 'RESOURCE_EXHAUSTED'),
            'a QuotaFailure with no violation': error_body(429, 'RESOURCE_EXHAUSTED', quota_failure()),
            'a RetryInfo alone': error_body(429, 'RESOURCE_EXHAUSTED', retry_info('30s')),
            'an empty body': b'', 'a body that is not JSON': b'<html>Too Many Requests</html>'}


def payment_vector() -> dict:
    """A11's vector: HTTP 402 and what it holds, by status and by the names its body carries (P-3: the ErrorInfo
    reasons first, then error.status, then the status)."""
    return {'an empty body': (b'', adapter.QUOTA, 'A payment is required'),
            'an HTML body': (b'<html>Payment Required</html>', adapter.QUOTA, 'A payment is required'),
            'a JSON error naming no hold': (error_body(402, 'FAILED_PAYMENT'), adapter.QUOTA, 'A payment is required'),
            'INVALID_ARGUMENT': (error_body(402, 'INVALID_ARGUMENT'), adapter.QUOTA, 'A payment is required'),
            'BILLING_DISABLED named': (error_body(402, 'PERMISSION_DENIED', error_info('BILLING_DISABLED')),
                                       adapter.QUOTA, 'Billing is not enabled'),
            'API_KEY_INVALID named': (error_body(402, 'INVALID_ARGUMENT', error_info('API_KEY_INVALID')),
                                      adapter.AUTH, 'The key was refused')}


class Pinned:
    """The pins of 2.5 set to the measured shas (measured_pins) for every test of a v2 request."""

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.multiple(interpretation, **measured_pins()))

    def extraction(self, text=TEXT, pages=PAGES, kind=KIND) -> ProviderRequest:
        return adapter.build_extraction_request(text, pages, kind)

    def appraisal(self, *, check=no_findings, data=None) -> adapter.AppraisalRequest:
        return adapter.build_appraisal_request(TEXT, PAGES, KIND, self.extraction(), stored_answer() if data is None
                                               else data, check=check)


def request_with(request: ProviderRequest, body=None, **fields) -> ProviderRequest:
    """``request`` with a changed body (rehashed, as a stored body that was built that way would be) or fields."""
    values = dict(provider=request.provider, adapter_version=request.adapter_version, body=request.body,
                  canonical_sha256=request.canonical_sha256, contexts=request.contexts)
    if body is not None:
        values.update(body=body, canonical_sha256=request_sha256(body))
    values.update(fields)
    return ProviderRequest(**values)


# --- the labels and the body keys -------------------------------------------------------------------------------------

class ConstantsTests(SimpleTestCase):
    def test_the_synthetic_texts_are_no_acceptance_document(self):
        exclusion = APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256'
        with open(exclusion, encoding='ascii') as file:
            excluded = {line.strip() for line in file if line.strip()}
        self.assertEqual(len(excluded), 288)
        for text in (TEXT, fixtures.SHARED, UnbuiltTests.LABEL, 'A [S1] note.', 'Synthetic note.',
                     'Synthetic\x00 note.', json.dumps(fixtures.note_answer())):
            with self.subTest(text=text[:30]):
                for data in (text.encode('utf-8'), text.strip().encode('utf-8')):
                    self.assertNotIn(hashlib.sha256(data).hexdigest(), excluded)

    def test_the_v2_labels(self):
        self.assertEqual((adapter.ADAPTER_VERSION_V2, adapter.READ_VERSIONS_V2),
                         (interpretation.ADAPTER_VERSION_V2, (interpretation.ADAPTER_VERSION_V2,)))
        self.assertEqual(adapter.ADAPTER_VERSION_V2, 'gemini-generate@cptstudio-2')
        self.assertLessEqual(len(adapter.ADAPTER_VERSION_V2), 40)  # ProviderRun.adapter_version
        self.assertNotEqual(adapter.ADAPTER_VERSION_V2, adapter.ADAPTER_VERSION)  # v1's runs keep their own version
        self.assertEqual((adapter.EXTRACTION, adapter.APPRAISAL, adapter.PURPOSES),
                         ('interpretation', 'appraisal', ('interpretation', 'appraisal')))
        self.assertEqual((adapter.EXTRACTION, adapter.APPRAISAL),
                         (interpretation.PURPOSE, interpretation.APPRAISAL_PURPOSE))
        for interpreter in (adapter.InterpreterV2, adapter.GeminiInterpreterV2, ReplayInterpreterV2):
            with self.subTest(interpreter=interpreter.__name__):
                self.assertEqual((interpreter.name, interpreter.adapter_version, interpreter.requested_model),
                                 ('gemini', 'gemini-generate@cptstudio-2', 'gemini-4-argon'))
        self.assertEqual((adapter.GeminiInterpreterV2.endpoint, ReplayInterpreterV2.endpoint), (ENDPOINT, ''))
        self.assertEqual((adapter.GeminiInterpreterV2.mode, ReplayInterpreterV2.mode), ('live', 'replay'))

    def test_the_body_keys_are_v1s_three_for_both_kinds(self):
        from studio.interpretation import prompt as v1_prompt  # the test reads v1's tuple; the adapter never does

        self.assertEqual(adapter.BODY_KEYS, frozenset(v1_prompt.BODY_KEYS))
        self.assertEqual(adapter.BODY_KEYS, frozenset(extract_prompt.BODY_KEYS))
        self.assertEqual(adapter.BODY_KEYS, frozenset(appraise_prompt.BODY_KEYS))
        self.assertEqual(adapter.BODY_KEYS, {'systemInstruction', 'contents', 'generationConfig'})

    def test_the_not_built_reasons(self):
        self.assertEqual(adapter.UNFRAMED_REASONS, ('marker', 'label', 'pages', 'empty'))
        self.assertEqual(adapter.UNFRAMED_REASONS, tuple(reason.value for reason in extract_prompt.Unframed))
        self.assertEqual(adapter.NOT_BUILT_REASONS, ('marker', 'label', 'pages', 'empty', 'nul', 'encoding', 'size',
                                                     'stored', 'claims'))
        from studio import jobs

        self.assertEqual(adapter.UNBUILT, jobs.UNBUILT)  # 'unbuilt': the not-sent run's refusal the stage records
        self.assertEqual(adapter.TOO_LONG, holds.TOO_LONG)  # the claim bound's effect is the cut-off answer's
        for bad in (dict(reason='other'), dict(reason='claims'), dict(reason='label', effect=adapter.TOO_LONG),
                    dict(reason='label', effect='hold')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter.NotBuilt('Synthetic.', **bad)
        refused = adapter.NotBuilt('Synthetic.', reason='claims', effect=adapter.TOO_LONG, claims=7)
        self.assertIsInstance(refused, ProviderUnavailable)  # "the provider cannot take this request; nothing sent"
        self.assertEqual((refused.unframed, refused.claims, adapter.NotBuilt('S.', reason='pages').unframed),
                         ('', 7, 'pages'))


# --- pass 1's request -------------------------------------------------------------------------------------------------

class ExtractionRequestTests(Pinned, OfflineTestCase):
    def test_the_request_is_contract_extract_prompts_body_of_the_revision_alone(self):
        request = self.extraction()
        self.assertEqual(request.body, extract_prompt.build_request(TEXT, PAGES, KIND))
        self.assertEqual((request.provider, request.adapter_version), ('gemini', 'gemini-generate@cptstudio-2'))
        self.assertEqual(request.canonical_sha256, hashlib.sha256(canonical_body(request.body)).hexdigest())
        self.assertEqual(request.contexts, (TEXT,))
        self.assertEqual(adapter.body_kind(request.body), (adapter.EXTRACTION, ''))
        self.assertEqual(list(request.body), ['systemInstruction', 'contents', 'generationConfig'])
        self.assertNotIn('model', request.body)  # the URL names the model (D13)
        self.assertEqual(list(inspect.signature(adapter.build_extraction_request).parameters),
                         ['text', 'pages', 'kind', 'max_bytes'])  # no member value, file or reading can be passed (D1)
        # building needs no credentials, settings or network: the interpreter's file does not exist
        live = adapter.GeminiInterpreterV2(self.tmp / 'absent.env')
        self.assertEqual(live.build_extraction_request(TEXT, PAGES, KIND), request)
        self.assertEqual(self.extraction(TEXT, list(PAGES), KIND), request)  # a list of pages is the same pages

    def test_what_cannot_be_sent_is_never_built(self):
        with self.assertRaises(adapter.NotBuilt) as caught:
            self.extraction('Synthetic\x00 note.', ())
        self.assertEqual((caught.exception.reason, caught.exception.effect, str(caught.exception)),
                         ('nul', 'unbuilt', 'The document text contains NUL characters; nothing was sent.'))
        size = len(canonical_body(self.extraction().body))
        with self.assertRaises(adapter.NotBuilt) as caught:
            adapter.build_extraction_request(TEXT, PAGES, KIND, max_bytes=size - 1)
        self.assertEqual(caught.exception.reason, 'size')
        self.assertIn(f'over the {size - 1:,}-byte limit; nothing was truncated or sent', str(caught.exception))
        self.assertEqual(len(canonical_body(adapter.build_extraction_request(TEXT, PAGES, KIND,
                                                                              max_bytes=size).body)), size)
        for wrong in ((None, PAGES, KIND, TypeError), (TEXT, 'pages', KIND, TypeError),
                      (TEXT, ({'page': 1, 'start': 0, 'end': len(TEXT)},), KIND, TypeError),
                      (TEXT, PAGES, 'image', ValueError)):
            with self.subTest(wrong=wrong[-1].__name__, at=repr(wrong[1])[:20]), self.assertRaises(wrong[-1]):
                adapter.build_extraction_request(*wrong[:3])

    def test_no_request_is_built_under_an_empty_or_changed_pin(self):
        for value in ('', '0' * 64):
            with self.subTest(value=value or 'empty'), \
                    mock.patch.object(interpretation, 'INSTRUCTIONS_SHA256_V2', value), \
                    self.assertRaises(RuntimeError):
                self.extraction()


# --- the unframed text: hand-offs 1a:R2, 2a#5, 2a:R2 ------------------------------------------------------------------

class UnbuiltTests(Pinned, OfflineTestCase):
    """A text that cannot be framed is ``refused: unbuilt`` with the reason contract/extract_prompt names - its Unframed
    value, read from its Unbuilt - never participants.http.framed_text's sentence (triage 1a:R2, 2a#5, 2a:R2)."""
    LABEL = 'Synthetic note. The polyp is described under [S2] below.\n'

    def cases(self):
        return {'label': (self.LABEL, ()), 'pages': (TEXT, (PageSpan(page=1, start=0, end=5),)),
                'pages (numbered 0)': (TEXT, (PageSpan(page=0, start=0, end=len(TEXT)),)),
                'empty': ('', ()), 'empty (blank)': ('   \n  ', ())}

    def test_each_unframed_reason_is_extract_prompts_own(self):
        for name, (text, pages) in self.cases().items():
            with self.subTest(name), self.assertRaises(adapter.NotBuilt) as caught:
                self.extraction(text, pages)
            expected = extract_prompt.unframed(text, pages)
            self.assertIsNotNone(expected)
            refused = caught.exception
            self.assertEqual((refused.reason, refused.unframed, refused.effect, refused.claims, refused.refusal),
                             (expected.value, expected.value, adapter.UNBUILT, None, None))
            self.assertEqual(str(refused), adapter.UNFRAMED_MESSAGE.format(why=adapter._UNFRAMED_WHY[expected]))
            self.assertTrue(str(refused).endswith('; nothing was sent.'))
            self.assertFalse([named for named in NAMES if named in str(refused).lower()])
        # the marker: the text's own sha256 prefix, so no real text holds it; planted as tests/test_interpretation_*
        with mock.patch.object(participant_prompt, 'marker', return_value='DOCUMENT-0000000000000000'), \
                self.assertRaises(adapter.NotBuilt) as caught:
            self.extraction(TEXT + ' DOCUMENT-0000000000000000', ())
        self.assertEqual((caught.exception.reason, caught.exception.unframed), ('marker', 'marker'))
        self.assertIn('it contains its own framing marker', str(caught.exception))

    def test_a_label_collision_is_never_reported_as_a_page_cover_failure(self):
        with self.assertRaises(adapter.NotBuilt) as caught:
            self.extraction(self.LABEL, ())
        self.assertEqual(caught.exception.unframed, 'label')
        self.assertIn('unit label', str(caught.exception))
        self.assertNotIn('pages', str(caught.exception))
        # the defect the hand-off names, shown on the participants' framing check: it calls the same text a page-cover
        # failure, which is why the reason is read from extract_prompt and never from that sentence
        with self.assertRaises(ProviderUnavailable) as misread:
            participants_http.framed_text(self.LABEL, (), KIND, extract_prompt.framed)
        self.assertIn('its pages do not cover it exactly', str(misread.exception))

    def test_the_appraisal_builder_refuses_the_same_text_the_same_way(self):
        request = self.extraction()
        for name, (text, pages) in self.cases().items():
            with self.subTest(name), self.assertRaises(adapter.NotBuilt) as caught:
                adapter.build_appraisal_request(text, pages, KIND, request, stored_answer(), check=no_findings)
            self.assertEqual(caught.exception.unframed, extract_prompt.unframed(text, pages).value)


# --- pass 2's request: the revision plus the stored extraction bytes (hand-off 2c:R5) ---------------------------------

class AppraisalRequestTests(Pinned, OfflineTestCase):
    def test_the_request_is_built_from_the_revision_plus_the_stored_extraction_bytes(self):
        found = self.appraisal()
        unit_count = len(appraise_prompt.segment.units(TEXT, PAGES))
        answer = extract_read.read(json.dumps(fixtures.note_answer()), unit_count)
        built = appraise_prompt.build_request(TEXT, PAGES, KIND, answer, findings={})
        self.assertEqual(found.request.body, built.body)
        self.assertEqual(found.built.body, built.body)
        self.assertEqual(found.answer, answer)
        self.assertEqual((found.unit_count, found.findings), (unit_count, {}))
        self.assertEqual([claim.content for claim in found.built.claim_set.claims],
                         [claim.content for claim in built.claim_set.claims])
        request = found.request
        self.assertEqual((request.provider, request.adapter_version, request.contexts),
                         ('gemini', 'gemini-generate@cptstudio-2', (TEXT,)))
        # the appraise key's source (7.4 [R:MO-5]; hand-off 2c:R5): the request's canonical sha256 is request_sha256
        # of its body, so 'appraise:<revision>:<run>:' + its first 16 hex changes whenever the claim set does
        self.assertEqual(request.canonical_sha256, request_sha256(request.body))
        self.assertEqual(adapter.body_kind(request.body), (adapter.APPRAISAL, ''))
        self.assertNotIn('model', request.body)
        self.assertNotEqual(request.canonical_sha256, self.extraction().canonical_sha256)

    def test_identical_inputs_give_a_byte_identical_request(self):
        first, second = self.appraisal(), self.appraisal()
        self.assertEqual(canonical_body(first.request.body), canonical_body(second.request.body))
        self.assertEqual(first.request, second.request)
        # its inputs are the revision, its pages and kind, the stored request and bytes, and the check: no member value
        self.assertEqual(list(inspect.signature(adapter.build_appraisal_request).parameters),
                         ['text', 'pages', 'kind', 'extraction', 'extraction_bytes', 'check', 'max_bytes'])

    def test_the_findings_are_the_checks_of_the_answer_read_here(self):
        seen, findings = [], {}

        def check(text, pages, answer):
            seen.append((text, pages, answer))
            return findings

        with mock.patch.object(appraise_prompt, 'build_request', wraps=appraise_prompt.build_request) as built:
            found = self.appraisal(check=check)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][:2], (TEXT, PAGES))
        self.assertIs(seen[0][2], found.answer)  # the check reads the answer read from the stored bytes
        self.assertIs(built.call_args.kwargs['findings'], findings)  # and its findings are what pass 2 is built from
        self.assertIs(found.findings, findings)
        # a finding drops its fact's claims (3.2.1): the findings decide the claim set
        failed = {FactKey(extract_schema.Family.EVENT, 'E2', Attribute.TECHNIQUE_DEVICE, 0): (Reason.UNIT_UNKNOWN,)}
        fewer = self.appraisal(check=lambda text, pages, answer: failed)
        self.assertLess(len(fewer.built.claim_set.claims), len(found.built.claim_set.claims))
        self.assertNotEqual(fewer.request.canonical_sha256, found.request.canonical_sha256)

    def test_the_check_is_required(self):
        with self.assertRaises(TypeError):
            adapter.build_appraisal_request(TEXT, PAGES, KIND, self.extraction(), stored_answer())  # no check at all
        with self.assertRaises(TypeError) as caught:
            adapter.build_appraisal_request(TEXT, PAGES, KIND, self.extraction(), stored_answer(), check=None)
        self.assertEqual(str(caught.exception), adapter.NO_CHECK)

    def test_the_stored_answer_must_answer_this_revisions_pass_1_request(self):
        request = self.extraction()
        altered = copy.deepcopy(request.body)
        altered['contents'][0]['parts'][0]['text'] += '\n'
        cases = {
            'another revision': adapter.build_extraction_request(fixtures.SHARED, (), KIND),
            'another kind of document': self.extraction(TEXT, PAGES, 'paste'),
            'a body altered after it was hashed': request_with(request, body=altered,
                                                               canonical_sha256=request.canonical_sha256),
            "v1's request": adapter.build_request(TEXT, PAGES, KIND),
            'another provider': request_with(request, provider='astra'),
            'a body that is not JSON': ProviderRequest(provider=request.provider,
                                                       adapter_version=request.adapter_version, body={'x': object()},
                                                       canonical_sha256=request.canonical_sha256,
                                                       contexts=request.contexts),
        }
        for name, stored in cases.items():
            with self.subTest(name), self.assertRaises(adapter.NotBuilt) as caught:
                adapter.build_appraisal_request(TEXT, PAGES, KIND, stored, stored_answer(), check=no_findings)
            self.assertEqual((caught.exception.reason, caught.exception.effect, caught.exception.refusal),
                             ('stored', 'unbuilt', None))
            self.assertEqual(str(caught.exception), adapter.STORED_OTHER)

    def test_a_stored_answer_that_cannot_be_read_builds_nothing(self):
        broken = fixtures.note_answer()
        del broken['events']
        cases = {'cut off': (cut_off(), 'envelope'), 'another model': (substituted(), 'envelope'),
                 'not JSON inside': (encoded(envelope('{"x": ')), 'json'),
                 'outside the schema': (encoded(envelope(json.dumps(broken))), 'schema'),
                 'no bytes': (None, 'envelope')}
        for name, (data, stage) in cases.items():
            with self.subTest(name), self.assertRaises(adapter.NotBuilt) as caught:
                adapter.build_appraisal_request(TEXT, PAGES, KIND, self.extraction(), data, check=no_findings)
            refused = caught.exception
            self.assertEqual((refused.reason, refused.effect, refused.refusal.stage), ('stored', 'unbuilt', stage))
            self.assertEqual(str(refused), adapter.STORED_REFUSED.format(stage=stage))
            self.assertIsInstance(refused.refusal, extract_read.Refusal)


# --- the claim bound, checked before a request is built (7.4 door 0; 7.5) ---------------------------------------------

class ClaimBoundTests(Pinned, OfflineTestCase):
    def bound(self, value):
        """claims.CLAIM_BOUND set to ``value``, with its pin (CLAIM_BOUND_SHA256) the sha of that bound, as the
        integration owner would write it."""
        stack = mock.patch.multiple(interpretation, CLAIM_BOUND_SHA256=jsonschema.sha256_of(
            {'claims_per_request': value}))
        return stack, mock.patch.object(claims, 'CLAIM_BOUND', value)

    def kinds_built(self, finished) -> list:
        """The kind of every ProviderRequest body _finished was asked to make (pass 1's, when the appraisal builder
        binds the stored answer to this revision's pass-1 request)."""
        return [adapter.body_kind(call.args[0])[0] for call in finished.call_args_list]

    def test_a_claim_set_over_the_bound_is_too_long_and_no_body_is_built(self):
        count = len(self.appraisal().built.claim_set.claims)
        self.assertGreater(count, 1)
        extraction = self.extraction()
        pin, bound = self.bound(count - 1)
        with pin, bound, mock.patch.object(appraise_prompt, 'user_turn', side_effect=AssertionError('turn')), \
                mock.patch.object(appraise_prompt, 'request_parts', side_effect=AssertionError('body')), \
                mock.patch.object(adapter, '_finished', wraps=adapter._finished) as finished, \
                self.assertRaises(adapter.NotBuilt) as caught:
            adapter.build_appraisal_request(TEXT, PAGES, KIND, extraction, stored_answer(), check=no_findings)
        refused = caught.exception
        self.assertEqual((refused.effect, refused.reason, refused.claims, refused.unframed),
                         (adapter.TOO_LONG, 'claims', count, ''))
        self.assertEqual(str(refused), adapter.CLAIMS_MESSAGE.format(count=count, bound=count - 1))
        self.assertEqual(self.kinds_built(finished), [adapter.EXTRACTION])  # no pass-2 body, no pass-2 request
        self.assertFalse([named for named in NAMES if named in str(refused).lower()])

    def test_a_claim_set_at_the_bound_is_built(self):
        count = len(self.appraisal().built.claim_set.claims)
        pin, bound = self.bound(count)
        with pin, bound:
            found = self.appraisal()
        self.assertEqual(len(found.built.claim_set.claims), count)
        self.assertEqual(adapter.body_kind(found.request.body)[0], adapter.APPRAISAL)

    def test_the_adapter_refuses_an_over_bound_claim_set_even_if_the_builder_did_not(self):
        built = self.appraisal().built
        extraction = self.extraction()
        pin, bound = self.bound(len(built.claim_set.claims) - 1)
        with pin, bound, mock.patch.object(appraise_prompt, 'build_request', return_value=built), \
                mock.patch.object(adapter, '_finished', wraps=adapter._finished) as finished, \
                self.assertRaises(adapter.NotBuilt) as caught:
            adapter.build_appraisal_request(TEXT, PAGES, KIND, extraction, stored_answer(), check=no_findings)
        self.assertEqual((caught.exception.effect, caught.exception.claims),
                         (adapter.TOO_LONG, len(built.claim_set.claims)))
        self.assertEqual(self.kinds_built(finished), [adapter.EXTRACTION])

    def test_the_bound_is_1_8s_640(self):
        self.assertEqual(claims.CLAIM_BOUND, 640)


# --- the shared envelope, for both purposes ---------------------------------------------------------------------------

class EnvelopeTests(Pinned, SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.extracted = self.extraction()
        self.appraised = self.appraisal()
        self.requests = {adapter.EXTRACTION: self.extracted, adapter.APPRAISAL: self.appraised.request}

    def reader(self, purpose, raw):
        if purpose == adapter.EXTRACTION:
            return adapter.read_extraction(self.extracted, raw, self.appraised.unit_count)
        return adapter.read_appraisal(self.appraised, self.appraised.request, raw)

    def refusals(self):
        """(label, raw, the reason's own words): each envelope rule of the module docstring."""
        good = json.dumps(fixtures.note_answer())
        two = envelope(good)
        two['candidates'].append(copy.deepcopy(two['candidates'][0]))
        none = envelope(good)
        del none['modelVersion']
        blocked_too = with_parts({'text': good}, finish='MAX_TOKENS', modelVersion='gemini-4-argon-preview',
                                 promptFeedback={'blockReason': 'SAFETY'})
        return (
            ('another model, checked first', encoded(blocked_too), 'names a model other than the one requested'),
            ('no model named', encoded(none), 'does not name the model that answered'),
            ('a blocked request', encoded(envelope(good, promptFeedback={'blockReason': 'OTHER'})),
             'the request was blocked'),
            ('no candidate', encoded(envelope(good, candidates=[])), 'holds no candidate answer'),
            ('two candidates', encoded(two), 'holds 2 candidate answers, not exactly one'),
            ('a refused finish reason', encoded(with_parts({'text': good}, finish='SAFETY')), 'stopped for'),
            ('cut off (MAX_TOKENS)', cut_off(), 'cut off at the output limit'),
            ('a function call', encoded(with_parts({'functionCall': {'name': 'lookup', 'args': {}}})),
             'carries content other than text'),
            ('thinking only', encoded(with_parts({'text': good, 'thought': True})),
             'carries no text outside its thinking'),
            ('a repeated key', b'{"modelVersion": "gemini-4-argon", "modelVersion": "gemini-4-argon"}',
             'the response'),
            ('not bytes', None, 'there are no response bytes'),
        )

    def test_every_envelope_rule_refuses_alike_for_both_purposes(self):
        for label, raw, words in self.refusals():
            reasons = {}
            for purpose, request in self.requests.items():
                with self.subTest(label, purpose=purpose):
                    direct = adapter.answer_text_v2(request, raw)
                    self.assertIsInstance(direct, extract_read.Refusal)
                    self.assertEqual(direct.stage, 'envelope')
                    self.assertIn(words, direct.reason)
                    self.assertEqual(self.reader(purpose, raw), direct)  # the reader refuses before reading on
                    self.assertFalse([named for named in NAMES if named in direct.reason.lower()])
                    reasons[purpose] = direct.reason
            self.assertEqual(reasons[adapter.EXTRACTION], reasons[adapter.APPRAISAL])

    def test_a_usable_envelope_is_read_on_for_both_purposes(self):
        for purpose, raw in ((adapter.EXTRACTION, stored_answer()),
                             (adapter.APPRAISAL, appraisal_answer(self.appraised.built))):
            with self.subTest(purpose=purpose):
                request = self.requests[purpose]
                text = adapter.answer_text_v2(request, raw)
                self.assertEqual(text, json.loads(raw)['candidates'][0]['content']['parts'][0]['text'])
                found = self.reader(purpose, raw)
                self.assertNotIsInstance(found, extract_read.Refusal)
        read = self.reader(adapter.APPRAISAL, appraisal_answer(self.appraised.built))
        self.assertIsInstance(read, appraise_read.ReadAppraisal)
        self.assertEqual(len(read.verdicts), len(self.appraised.built.claim_set.claims))

    def test_the_answer_is_the_text_parts_that_are_not_thinking_joined_in_order(self):
        good = json.dumps(fixtures.note_answer())
        split = encoded(with_parts({'text': 'planning', 'thought': True}, {'text': good[:40]},
                                   {'thoughtSignature': 'c2ln'}, {'text': good[40:]}))
        for request in self.requests.values():
            self.assertEqual(adapter.answer_text_v2(request, split), good)
        self.assertNotIsInstance(adapter.read_extraction(self.extracted, split, self.appraised.unit_count),
                                 extract_read.Refusal)

    def test_an_answer_is_read_only_as_a_design_v2_version_recorded_it(self):
        v1_request = adapter.build_request(TEXT, PAGES, KIND)
        raw = stored_answer()
        refused = adapter.answer_text_v2(v1_request, raw)
        self.assertEqual((refused.stage, refused.reason), ('envelope', extract_read.refuse(
            'envelope', adapter.STORED_VERSION).reason))
        self.assertEqual(adapter.read_extraction(v1_request, raw, 7).reason, refused.reason)
        self.assertEqual(adapter.read_appraisal(self.appraised, v1_request, raw).reason, refused.reason)
        self.assertEqual(adapter.answer_text_v2(request_with(self.extracted, provider='fable'), raw).reason,
                         refused.reason)
        # and v1's reader never reads a design v2 answer either
        from studio.interpretation import read as v1_read  # the test reads v1's class; the v2 path never does

        self.assertIsInstance(adapter.answer_text(self.extracted, raw), v1_read.Refusal)

    def test_each_reader_reads_only_its_own_kind_and_its_own_request(self):
        raw = appraisal_answer(self.appraised.built)
        refused = adapter.read_extraction(self.appraised.request, stored_answer(), self.appraised.unit_count)
        self.assertEqual(refused.reason, extract_read.refuse('envelope', adapter.OTHER_KIND).reason)
        other = self.appraisal(check=lambda text, pages, answer: {
            FactKey(extract_schema.Family.EVENT, 'E2', Attribute.TECHNIQUE_DEVICE, 0): (Reason.UNIT_UNKNOWN,)})
        self.assertNotEqual(other.request.canonical_sha256, self.appraised.request.canonical_sha256)
        # an answer recorded for another claim set is never read against this one: K1 there is not K1 here (3.2.4)
        refused = adapter.read_appraisal(self.appraised, other.request, raw)
        self.assertEqual(refused.reason, extract_read.refuse('envelope', adapter.OTHER_APPRAISAL).reason)
        self.assertIsInstance(adapter.read_appraisal(self.appraised, self.appraised.request, raw),
                              appraise_read.ReadAppraisal)


# --- the classifier: one, for both purposes ---------------------------------------------------------------------------

class ClassificationTests(SimpleTestCase):
    def assertKind(self, result, kind, hold=''):
        self.assertIsNotNone(result)
        self.assertEqual((result.kind, result.hold), (kind, hold))
        self.assertFalse([named for named in NAMES if named in result.why.lower()])
        return result

    def test_one_classifier_reads_the_response_alone(self):
        self.assertEqual(list(inspect.signature(adapter.classify).parameters),
                         ['outcome', 'http_status', 'response_bytes'])  # no request, no purpose: both passes alike

    def test_max_tokens_is_too_long(self):
        for raw in (cut_off(), encoded(with_parts({'text': '{'}, {'text': '"x"'}, finish='MAX_TOKENS'))):
            result = self.assertKind(adapter.classify('succeeded', 200, raw), adapter.TOO_LONG)
            self.assertEqual(result.why, 'The answer was cut off at the output limit: the document is too long to be '
                                         'read in one piece.')
        self.assertEqual(holds.classify('succeeded', 200, cut_off()).effect, holds.TOO_LONG)
        self.assertFalse(holds.classify('succeeded', 200, cut_off()).retry)  # never re-sent for a member (C5)

    def test_the_model_pin(self):
        self.assertEqual(adapter.MODEL, 'gemini-4-argon')
        self.assertEqual(adapter.ENDPOINT, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:'
                                           'generateContent')
        self.assertKind(adapter.classify('succeeded', 200, substituted()), adapter.HOLD, adapter.MODEL_HOLD)
        none = envelope()
        del none['modelVersion']
        self.assertKind(adapter.classify('succeeded', 200, encoded(none)), adapter.HOLD, adapter.MODEL_HOLD)
        self.assertKind(adapter.classify('succeeded', 200, encoded(envelope())), adapter.ANSWERED)

    def test_a_bare_429_holds(self):
        for label, raw in bare_429s().items():
            with self.subTest(label):
                result = self.assertKind(adapter.classify('failed', 429, raw), adapter.HOLD, adapter.QUOTA)
                self.assertEqual(result.http_status, 429)
                self.assertEqual(result.violations, ())
                self.assertIn('no per-minute limit was named', result.why)
        # the cap's RESOURCE_EXHAUSTED holds whatever status carries it
        self.assertKind(adapter.classify('failed', 400, error_body(400, 'RESOURCE_EXHAUSTED')), adapter.HOLD,
                        adapter.QUOTA)
        # the control: a per-minute paid-tier rate limit that states its limit fails the attempt only (P-4)
        rate = error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(violation(PER_MINUTE, quotaValue='1000')))
        self.assertKind(adapter.classify('failed', 429, rate), adapter.FAILED)
        self.assertKind(adapter.classify('failed', 429, TRIAL_429.read_bytes()), adapter.HOLD, adapter.QUOTA)

    def test_a_402_holds_as_quota(self):
        self.assertEqual(adapter.HOLD_STATUSES, {401: adapter.AUTH, 402: adapter.QUOTA, 403: adapter.PERMISSION})
        for label, (raw, hold, words) in payment_vector().items():
            with self.subTest(label):
                result = self.assertKind(adapter.classify('failed', 402, raw), adapter.HOLD, hold)
                self.assertEqual(result.http_status, 402)
                self.assertIn(words, result.why)
                self.assertIn('HTTP 402', result.why)
        self.assertEqual(adapter.classify('failed', 402, b'').why,
                         'A payment is required for the key (HTTP 402): every request would be refused until an '
                         'operator acts.')
        self.assertEqual(holds.classify('failed', 402, b'').reason, holds.QUOTA)
        self.assertFalse(holds.classify('failed', 402, b'').retry)
        # 401 and 403 keep their sentences: only a bare 402's names a payment
        self.assertIn('The key was refused', adapter.classify('failed', 401, b'').why)
        self.assertIn('may not use the model', adapter.classify('failed', 403, b'').why)


# --- the send: one exchange, per purpose ------------------------------------------------------------------------------

class SendTests(Pinned, OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.clock = FakeClock()
        for module in (participants_http, adapter, participants_loop):
            self.enterContext(mock.patch.object(module, 'monotonic', self.clock))
        self.credentials = write_file(self.tmp / 'gemini.env', gemini_env())
        self.extracted = self.extraction()
        self.appraised = self.appraisal()
        self.requests = {adapter.EXTRACTION: self.extracted, adapter.APPRAISAL: self.appraised.request}

    def make(self, session, **options):
        return adapter.GeminiInterpreterV2(self.credentials, session_factory=lambda: session, **options)

    def run_loop(self, request, *steps, **options):
        session = FakeSession(*steps)
        interpreter = options.pop('interpreter', None) or self.make(session)
        recorded = []
        options.setdefault('deadline_s', 540)
        with participants_loop.recording(recorded.append):
            outcome = interpreter.send_loop(request, client_request_id='cptstudio-run-0001', original_bytes=None,
                                            **options)
        for text in (repr(outcome.final), outcome.final.error, outcome.final.endpoint):
            self.assertNotIn(GEMINI_KEY, text)
        return outcome, session, recorded

    def test_each_kind_is_one_exchange_with_its_own_read_timeout(self):
        interpreter_options = {'read_timeout': 470, 'appraisal_read_timeout': 475}  # apart, so each is seen to apply
        for purpose, request in self.requests.items():
            with self.subTest(purpose=purpose):
                session = FakeSession(FakeResponse(200, encoded(envelope())))
                exchange = self.make(session, **interpreter_options).send(request, deadline_s=600)
                self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status), ('succeeded', True, 200))
                (call,) = session.calls
                read = 470 if purpose == adapter.EXTRACTION else 475
                self.assertEqual(call, {'url': ENDPOINT, 'data': canonical_body(request.body),
                                        'headers': {'x-goog-api-key': GEMINI_KEY, 'content-type': 'application/json'},
                                        'timeout': (10, read), 'allow_redirects': False, 'stream': True})
                self.assertEqual(hashlib.sha256(call['data']).hexdigest(), request.canonical_sha256)
                self.assertNotIn(GEMINI_KEY, call['url'])

    def test_a_bare_429_is_one_exchange_never_retried_and_holds(self):
        for purpose, request in self.requests.items():
            for label, raw in bare_429s().items():
                with self.subTest(label, purpose=purpose):
                    outcome, session, recorded = self.run_loop(request, FakeResponse(429, raw),
                                                               FakeResponse(200, encoded(envelope())))
                    self.assertEqual((outcome.outcome, outcome.final.http_status, outcome.final.response_bytes),
                                     ('failed', 429, raw))
                    self.assertEqual((len(outcome.exchanges), len(recorded), len(session.calls)), (1, 1, 1))
                    self.assertEqual(len(session.steps), 1)  # the queued 200 was never asked for
                    verdict = adapter.classify(outcome.outcome, outcome.final.http_status, outcome.final.response_bytes)
                    self.assertEqual((verdict.kind, verdict.hold), (adapter.HOLD, adapter.QUOTA))

    def test_a_402_is_one_exchange_and_holds(self):
        for purpose, request in self.requests.items():
            with self.subTest(purpose=purpose):
                outcome, session, _ = self.run_loop(request, FakeResponse(402, b''), FakeResponse(200, b'{}'))
                self.assertEqual((outcome.outcome, outcome.final.http_status, len(session.calls)), ('failed', 402, 1))
                verdict = adapter.classify(outcome.outcome, outcome.final.http_status, outcome.final.response_bytes)
                self.assertEqual((verdict.kind, verdict.hold), (adapter.HOLD, adapter.QUOTA))

    def test_a_cut_off_answer_is_read_as_too_long_inside_the_read(self):
        for purpose, request in self.requests.items():
            with self.subTest(purpose=purpose):
                outcome, _, _ = self.run_loop(request, FakeResponse(200, cut_off()))
                self.assertEqual(outcome.outcome, 'succeeded')
                verdict = adapter.classify(outcome.outcome, outcome.final.http_status, outcome.final.response_bytes)
                self.assertEqual(verdict.kind, adapter.TOO_LONG)

    def test_each_purposes_send_deadline_bounds_its_run(self):
        for purpose, request in self.requests.items():
            with self.subTest(purpose=purpose):
                session = FakeSession(FakeResponse(200, encoded(envelope())))

                def slow():
                    self.clock.advance(295)
                    return session
                interpreter = adapter.GeminiInterpreterV2(self.credentials, session_factory=slow, send_deadline=500,
                                                          appraisal_send_deadline=300)
                outcome, _, _ = self.run_loop(request, interpreter=interpreter, deadline_s=540)
                self.assertEqual(outcome.outcome, 'succeeded')
                # 500 s less the 295 s the session took leaves 205 s for pass 1; 300 s leaves 5 s for pass 2
                self.assertEqual(session.calls[0]['timeout'],
                                 (10, 205.0) if purpose == adapter.EXTRACTION else (5.0, 5.0))

    def test_refusals_before_anything_is_sent(self):
        for purpose, request in self.requests.items():
            tools = dict(copy.deepcopy(request.body), tools=[])
            altered = copy.deepcopy(request.body)
            altered['contents'][0]['parts'][0]['text'] += ' Synthetic addition.'
            second_turn = copy.deepcopy(request.body)
            second_turn['contents'].append({'role': 'user', 'parts': [{'text': 'Synthetic.'}]})
            cases = ((request_with(request, body=tools), {}, adapter.NOT_BUILT),
                     (request_with(request, body=second_turn), {}, adapter.NOT_BUILT),
                     (request_with(request, body=altered, canonical_sha256=request.canonical_sha256), {},
                      'does not match its recorded hash'),
                     (request_with(request, adapter_version=adapter.ADAPTER_VERSION), {}, 'different provider'),
                     (request_with(request, provider='astra'), {}, 'different provider'),
                     (request, {'deadline_s': 0}, adapter.INVALID_DEADLINE),
                     (request, {'carried': (participants_loop.ExchangeRecord(
                         turn=1, request_body={}, request_sha256='0' * 64, outcome='succeeded'),)},
                      adapter.NOT_CONTINUED),
                     (request, {'should_stop': lambda: True}, adapter.STOPPED_BEFORE),
                     (request, {'should_stop': 'yes'}, adapter.NOT_CALLABLE))
            for refused, options, expect in cases:
                with self.subTest(expect, purpose=purpose):
                    outcome, session, recorded = self.run_loop(refused, FakeResponse(200, b'{}'), **options)
                    self.assertEqual((outcome.outcome, outcome.exchanges, recorded, session.calls),
                                     ('not_sent', (), [], []))
                    self.assertIn(expect, outcome.final.error)
                    if set(options) <= {'deadline_s'}:  # send() takes no Stop and no continuation
                        session = FakeSession()
                        exchange = self.make(session).send(refused, deadline_s=options.get('deadline_s', 30))
                        self.assertEqual((exchange.outcome, session.calls), ('not_sent', []))
                        self.assertIn(expect, exchange.error)
        # v1's request is never sent by design v2's interpreter, nor design v2's by v1's
        v1_request = adapter.build_request(TEXT, PAGES, KIND)
        outcome, session, _ = self.run_loop(v1_request, FakeResponse(200, b'{}'))
        self.assertEqual((outcome.outcome, session.calls), ('not_sent', []))
        v1_interpreter = adapter.GeminiInterpreter(self.credentials, session_factory=lambda: FakeSession())
        self.assertEqual(v1_interpreter.send(self.extracted, deadline_s=30).outcome, 'not_sent')

    def test_a_body_built_under_a_changed_pin_is_never_sent(self):
        with mock.patch.object(interpretation, 'APPRAISAL_INSTRUCTIONS_SHA256', '0' * 64):
            self.assertEqual(adapter.body_kind(self.appraised.request.body), ('', adapter.UNPINNED_V2))
            self.assertEqual(adapter.body_kind(self.extracted.body), (adapter.EXTRACTION, ''))  # pass 1's pins stand
            outcome, session, _ = self.run_loop(self.appraised.request, FakeResponse(200, b'{}'))
        self.assertEqual((outcome.outcome, outcome.final.error, session.calls), ('not_sent', adapter.UNPINNED_V2, []))
        with mock.patch.object(interpretation, 'INSTRUCTIONS_SHA256_V2', ''):
            self.assertEqual(adapter.body_kind(self.extracted.body), ('', adapter.UNPINNED_V2))

    def test_no_answer_asks_for_a_tool_and_the_executor_is_never_called(self):
        executor = mock.Mock(return_value=({}, []))
        calling = encoded(with_parts({'functionCall': {'name': 'lookup_codes', 'args': {}}}))
        for request in self.requests.values():
            outcome, session, _ = self.run_loop(request, FakeResponse(200, calling), execute_tool=executor)
            self.assertEqual((outcome.outcome, len(outcome.exchanges), len(session.calls)), ('succeeded', 1, 1))
        executor.assert_not_called()

    def test_the_kind_of_a_body(self):
        interpreter = self.make(FakeSession())
        self.assertEqual((interpreter.purpose(self.extracted), interpreter.purpose(self.appraised.request)),
                         (adapter.EXTRACTION, adapter.APPRAISAL))
        turn = self.appraised.request.body['contents'][0]['parts'][0]['text']
        framed = self.extracted.body['contents'][0]['parts'][0]['text']
        others = {'not a body': None, 'no turn': {'contents': []},
                  "pass 2's turn with pass 1's instruction": dict(copy.deepcopy(self.extracted.body), contents=[
                      {'role': 'user', 'parts': [{'text': turn}]}]),
                  "pass 1's document with pass 2's instruction": appraise_prompt.request_parts(framed),
                  'the claims without the cards': appraise_prompt.request_parts(turn.replace(
                      f'\n\n{claims.CARDS_HEADING}\n', '\n\n')),
                  'text after the claims': appraise_prompt.request_parts(turn + '\n\nSynthetic addition.'),
                  'the cards first': appraise_prompt.request_parts(
                      turn[len(framed) + 2:] + '\n\n' + framed)}
        for name, body in others.items():
            with self.subTest(name):
                self.assertEqual(adapter.body_kind(body), ('', adapter.NOT_BUILT))
                if isinstance(body, dict) and 'systemInstruction' in body:
                    self.assertEqual(interpreter.purpose(request_with(self.extracted, body=body)), '')


# --- the per-purpose timeouts and the configured interpreter --------------------------------------------------------

class TimeoutTests(SimpleTestCase):
    def test_pass_2_takes_d49s_deadlines(self):
        from studio import jobs

        self.assertEqual((adapter.APPRAISAL_READ_TIMEOUT_SECONDS, adapter.APPRAISAL_SEND_DEADLINE_SECONDS), (480, 510))
        self.assertEqual((settings.APPRAISER_READ_TIMEOUT_SECONDS, settings.APPRAISER_SEND_DEADLINE_SECONDS),
                         (adapter.APPRAISAL_READ_TIMEOUT_SECONDS, adapter.APPRAISAL_SEND_DEADLINE_SECONDS))
        self.assertEqual((settings.INTERPRETER_READ_TIMEOUT_SECONDS, settings.INTERPRETER_SEND_DEADLINE_SECONDS),
                         (adapter.READ_TIMEOUT_SECONDS, adapter.SEND_DEADLINE_SECONDS))
        appraise = settings.JOB_DEADLINE_SECONDS['appraise']
        self.assertEqual(appraise, 560)
        self.assertLess(settings.APPRAISER_READ_TIMEOUT_SECONDS, settings.APPRAISER_SEND_DEADLINE_SECONDS)
        self.assertLess(settings.APPRAISER_SEND_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS, appraise)
        self.assertLess(appraise, settings.STALE_RUNNING_SECONDS)
        # FINAL-V2 7.4: a cut-off answer of 32,768 tokens at 82.4 tokens per second fits the read, so it is TOO_LONG
        self.assertLess(32_768 / 82.4, settings.APPRAISER_READ_TIMEOUT_SECONDS)
        interpreter = adapter.InterpreterV2()
        self.assertEqual(interpreter.send_deadlines, {'interpretation': 510, 'appraisal': 510})
        live = adapter.GeminiInterpreterV2('/nonexistent/gemini.env')
        self.assertEqual((live.connect_timeout, live.read_timeouts), (10, {'interpretation': 480, 'appraisal': 480}))

    def test_every_deadline_and_limit_is_validated(self):
        for option in ('send_deadline', 'appraisal_send_deadline'):
            for value in (0, -1, float('inf'), True, '510'):
                with self.subTest(option=option, value=value), self.assertRaises(ValueError):
                    adapter.InterpreterV2(**{option: value})
        for option in ('connect_timeout', 'read_timeout', 'appraisal_read_timeout'):
            with self.subTest(option=option), self.assertRaises(ValueError):
                adapter.GeminiInterpreterV2('/x.env', **{option: 0})
        for option in ('max_request_bytes', 'max_response_bytes'):
            with self.subTest(option=option), self.assertRaises(ValueError):
                adapter.InterpreterV2(**{option: 0})

    def test_the_configured_interpreter_reads_each_purposes_settings(self):
        with override_settings(GEMINI_MODE='disabled'):
            self.assertIsNone(adapter.get_interpreter_v2())
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE=''):
            with self.assertRaisesMessage(ProviderUnavailable, 'Live interpretation needs '
                                                               'CPT_STUDIO_GEMINI_CREDENTIALS_FILE.'):
                adapter.get_interpreter_v2()
        apart = dict(INTERPRETER_READ_TIMEOUT_SECONDS=470, INTERPRETER_SEND_DEADLINE_SECONDS=500,
                     APPRAISER_READ_TIMEOUT_SECONDS=460, APPRAISER_SEND_DEADLINE_SECONDS=490)
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE='/nonexistent/gemini.env', **apart):
            live = adapter.get_interpreter_v2()  # the file is read at send time, never here
        self.assertIsInstance(live, adapter.GeminiInterpreterV2)
        self.assertEqual((live.mode, live.endpoint, live.credentials_path, live.connect_timeout),
                         ('live', ENDPOINT, '/nonexistent/gemini.env', 10))
        self.assertEqual((live.read_timeouts, live.send_deadlines), ({'interpretation': 470, 'appraisal': 460},
                                                                     {'interpretation': 500, 'appraisal': 490}))
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE='/nonexistent/gemini.env'):
            live = adapter.get_interpreter_v2()
        self.assertEqual((live.read_timeouts, live.send_deadlines), ({'interpretation': 480, 'appraisal': 480},
                                                                     {'interpretation': 510, 'appraisal': 510}))
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR=''):
            with self.assertRaisesMessage(ProviderUnavailable, 'Replay interpretation needs '
                                                               'CPT_STUDIO_GEMINI_REPLAY_DIR.'):
                adapter.get_interpreter_v2()
        with override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR='/nonexistent/recordings', **apart):
            replayed = adapter.get_interpreter_v2()
        self.assertIsInstance(replayed, ReplayInterpreterV2)
        self.assertEqual((replayed.mode, replayed.endpoint, replayed.replay_dir, replayed.send_deadlines),
                         ('replay', '', Path('/nonexistent/recordings'), {'interpretation': 500, 'appraisal': 490}))
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE='/x.env'):
            self.assertIsNone(adapter.get_interpreter_v2('disabled'))  # an explicit mode wins
        with self.assertRaises(ValueError):
            adapter.get_interpreter_v2('bogus')
        # v1's configured interpreter is v1's until step 5b switches the pipeline (FINAL-V2 8.0)
        with override_settings(GEMINI_MODE='live', GEMINI_CREDENTIALS_FILE='/x.env'):
            self.assertEqual(adapter.get_interpreter().adapter_version, adapter.ADAPTER_VERSION)


# --- v1's prompt and read imports removed (FINAL-V2 5.7) --------------------------------------------------------------

def _imports(path: Path) -> list:
    """(the enclosing function or '', the module named) for every import in ``path``."""
    found = []

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else scope
            if isinstance(child, ast.Import):
                found.extend((scope, alias.name) for alias in child.names)
            elif isinstance(child, ast.ImportFrom):
                found.extend((scope, f'{child.module}.{alias.name}') for alias in child.names)
            visit(child, inner)
    visit(ast.parse(path.read_text(encoding='utf-8')), '')
    return found


class ImportTests(SimpleTestCase):
    def test_neither_module_imports_v1s_prompt_or_read_but_the_v1_surfaces_call_time_import(self):
        for path in (ADAPTER, REPLAY):
            found = _imports(path)
            with self.subTest(module=path.name):
                self.assertTrue([name for _, name in found if name.startswith('studio.interpretation.')])  # control
                retired = [(scope, name) for scope, name in found
                           if name.split('.')[:2] == ['studio', 'interpretation'] and name.split('.')[-1] in RETIRED]
                expected = ([('_v1_prompt', 'studio.interpretation.prompt'), ('_v1_read', 'studio.interpretation.read')]
                            if path == ADAPTER else [])
                self.assertEqual(retired, expected)

    def test_importing_the_adapter_loads_neither_and_reads_no_settings(self):
        code = ('import sys\nimport studio.interpretation.adapter, studio.interpretation.replay\n'
                'loaded = sorted(m for m in sys.modules if m.startswith("studio.interpretation."))\n'
                'from django.conf import settings\nassert not settings.configured\n'
                'print(",".join(loaded))\n'
                'from studio.interpretation import adapter\n'
                'adapter.build_request("Synthetic note.", (), "paste")\n'
                'print("prompt" if "studio.interpretation.prompt" in sys.modules else "none")\n')
        completed = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                    + code], capture_output=True, text=True, timeout=120, cwd=APP,
                                   env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        loaded_line, after = completed.stdout.strip().split('\n')
        loaded = set(loaded_line.split(','))
        contract = 'studio.interpretation.contract.'
        self.assertLessEqual({'studio.interpretation.adapter', 'studio.interpretation.replay',
                              contract + 'extract_prompt', contract + 'appraise_prompt', contract + 'extract_read',
                              contract + 'appraise_read'}, loaded)  # the control: the listing sees what is loaded
        self.assertEqual(sorted(loaded & {f'studio.interpretation.{name}' for name in RETIRED}), [])
        self.assertEqual(after, 'prompt')  # the control: v1's surface still reaches v1's prompt, at call time


def traced(work) -> list:
    """(file, first line, qualified name) of every Python function ``work`` executes."""
    calls = []

    def profile(frame, event, _):
        if event == 'call':
            code = frame.f_code
            calls.append((code.co_filename, code.co_firstlineno, code.co_qualname))

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        work()
    finally:
        sys.setprofile(previous)
    return calls


class TraceTests(Pinned, OfflineTestCase):
    def v1_surface(self, calls):
        return sorted({(Path(path).name, name) for path, _, name in calls if path in (str(ADAPTER), str(REPLAY))
                       and (name in V1_SURFACE or name.startswith(V1_CLASSES))})

    def retired(self, calls):
        package = STUDIO / 'interpretation'
        return sorted({Path(path).name for path, _, _ in calls
                       if Path(path).parent == package and Path(path).stem in RETIRED})

    def test_the_v2_path_executes_no_retired_module_and_no_line_of_the_v1_surface(self):
        folder = self.tmp / 'gemini'
        folder.mkdir()
        data = stored_answer()
        extracted = self.extraction()
        built = self.appraisal()
        (folder / f'{extracted.canonical_sha256}.json').write_bytes(data)
        (folder / f'{built.request.canonical_sha256}.json').write_bytes(appraisal_answer(built.built))
        replay = ReplayInterpreterV2(self.tmp)
        live = adapter.GeminiInterpreterV2(self.tmp / 'gemini.env', session_factory=lambda: FakeSession(
            FakeResponse(429, error_body(429, 'RESOURCE_EXHAUSTED'))))
        write_file(self.tmp / 'gemini.env', gemini_env())
        found = {}

        def work():
            request = adapter.build_extraction_request(TEXT, PAGES, KIND)
            first = replay.send_loop(request, deadline_s=60)
            appraisal = adapter.build_appraisal_request(TEXT, PAGES, KIND, request, first.final.response_bytes,
                                                        check=no_findings)
            second = replay.send_loop(appraisal.request, deadline_s=60)
            found['extraction'] = adapter.read_extraction(request, first.final.response_bytes, appraisal.unit_count)
            found['appraisal'] = adapter.read_appraisal(appraisal, appraisal.request, second.final.response_bytes)
            refused = live.send_loop(appraisal.request, deadline_s=60)
            for exchange in (first.final, second.final, refused.final):
                found.setdefault('verdicts', []).append(holds.classify(
                    exchange.outcome, exchange.http_status, exchange.response_bytes or b'').effect)
            adapter.answer_text_v2(request, cut_off())
            try:
                adapter.build_extraction_request('A [S1] note.', (), KIND)
            except adapter.NotBuilt:
                pass

        calls = traced(work)
        self.assertIsInstance(found['extraction'], extract_read.ReadAnswer)
        self.assertIsInstance(found['appraisal'], appraise_read.ReadAppraisal)
        self.assertEqual(found['verdicts'], [holds.ANSWERED, holds.ANSWERED, holds.HOLD])
        self.assertEqual(self.retired(calls), [])
        self.assertEqual(self.v1_surface(calls), [])
        names = {(Path(path).name, name) for path, _, name in calls}
        # the unframed text's reason is extract_prompt's own: participants.http.framed_text never runs (1a:R2, 2a#5)
        self.assertNotIn(('http.py', 'framed_text'), names)
        self.assertIn(('extract_prompt.py', 'unframed'), names)
        # positive controls: the trace sees the v2 section and contract/ run
        self.assertLessEqual({('adapter.py', 'build_appraisal_request'), ('adapter.py', 'InterpreterV2.send_loop'),
                              ('adapter.py', 'body_kind'), ('adapter.py', '_envelope'), ('adapter.py', 'classify'),
                              ('replay.py', '_Recordings.recorded'), ('extract_prompt.py', 'build_request'),
                              ('appraise_prompt.py', 'build_request'), ('extract_read.py', 'read'),
                              ('appraise_read.py', 'read')}, names)

    def test_the_trace_sees_v1s_modules_when_v1s_surface_runs(self):
        def work():
            request = adapter.build_request(TEXT, PAGES, KIND)
            adapter.answer_text(request, cut_off())  # a refusal: v1's read.refuse runs
            adapter.body_problem(request.body)
        calls = traced(work)
        self.assertLessEqual({'prompt.py', 'read.py'}, set(self.retired(calls)))
        self.assertEqual(self.v1_surface(calls), [('adapter.py', '_v1_prompt'), ('adapter.py', '_v1_read'),
                                                  ('adapter.py', 'answer_text'), ('adapter.py', 'body_problem'),
                                                  ('adapter.py', 'build_request')])
