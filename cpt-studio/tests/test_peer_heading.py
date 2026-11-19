"""The peer request's heading of CPT Studio's reading (design/FINAL.md 6.6 and 16.10; DECISIONS D9; slice S10).

prompt.peer_document takes ``reading_heading``, one of a closed list of two: the legacy heading every peer request
carried before the Gemini migration - its default, so a legacy peer request is byte-identical - and "CPT Studio's
reading after its first assessment", which a peer review of a new-path assess #1 carries (jobs.stage_peer, through
prompt.using_reading_heading: an adapter's build_peer_request passes no heading). The adapter versions are not bumped (a
recorded exception to prompt.py's version rule): the rollback image reads stored participant runs by adapter version,
and the response format and its readers are unchanged.

THE PINS. The legacy sha256s below were computed with the pre-migration studio/participants/prompt.py (the file at
395a46c96, loaded in a separate process as studio.participants.prompt before the adapters imported it), over the fixed
synthetic inputs of ``inputs``: the peer document, and the whole peer request of each real adapter. The events pins were
computed with this slice's prompt.py. Synthetic data only; nothing is sent."""
import contextvars
import hashlib
import threading
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from studio import interpretation, jobs, review
from studio.participants import anthropic_fable, openai_astra, peer, prompt
from studio.participants.replay import ReplayParticipant
from studio.types import EvidenceSpan, LocatedQuote, PageSpan, ParticipantCode, ParticipantReading, sha256_json
from tests.legacy_chain import legacy_chain
from tests.test_pipeline_assess_events import EventsCase, MODULES as SCRIPTED_MODULES

LEGACY = "CPT Studio's rule-based reading - it can be wrong"
EVENTS = "CPT Studio's reading after its first assessment - it can be wrong"
TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 11/09/2026.\n'
        'EGD: cold forceps biopsies were taken from the gastric antrum.\n')
QUOTE = 'cold forceps biopsies were taken from the gastric antrum'
MODULES = {'astra': openai_astra, 'fable': anthropic_fable}
# computed with the pre-migration prompt.py (module docstring)
LEGACY_DOCUMENT_SHA256 = 'ffedae99eea623f536105a7c3eb8c6eaf877067a4f53adabe5701832357d5032'
LEGACY_REQUEST_SHA256 = {'astra': 'c61aa31bb76e01f406bee6caf8bc6612b72cfde96c6d9075bf45f534ad03b909',
                         'fable': 'f3f20370bb8cbce2675c27fe4f42a552bfa04ee1acbbf0205f1b3dca6738b3ae'}
# computed with this slice's prompt.py
EVENTS_DOCUMENT_SHA256 = '12f23ad2d9da983ee8dd32e0810137123897cfacddd81839d9729723e35682a6'
EVENTS_REQUEST_SHA256 = {'astra': 'c2a998af3135f22130c9ea19bcecc2c5a1237faa2f74274faa4817dbb1bcb909',
                         'fable': '1d5a3a35715c86ba50f58fadfd446f62418d9dab9740abf48d9f5acff72c19d9'}


def inputs(name):
    """(text, pages, own, peers, cpt_studio, frozen) of a peer request of ``name``: a fixed synthetic own reading, a
    Corti conclusion, CPT Studio's reading with one open question and one held code, and the frozen list they make."""
    start = TEXT.index(QUOTE)
    located = LocatedQuote(QUOTE, (EvidenceSpan(0, start, start + len(QUOTE), QUOTE, True),))
    module = MODULES[name]
    own = ParticipantReading(provider=name, adapter_version=module.ADAPTER_VERSION, reading_version='harness-reading@2',
                             requested_model=module.MODEL, returned_model=module.MODEL,
                             codes=(ParticipantCode(code='43239', evidence=(located,), confidence='high'),))
    peers = {'corti': {'codes': [{'code': '43239', 'modifiers': [], 'units': 1, 'evidence': [QUOTE]}]}}
    cpt_studio = {'open_questions': [{'question_id': 'q-1', 'scope': 'proposal', 'fact': 'extent', 'family': 'gi.egd',
                                      'proposal_key': 'sel:0', 'question': 'How far was the endoscope advanced?',
                                      'reason': 'The extent is not stated.'}],
                  'held': [{'key': 'sel:0', 'code': '43239', 'status': 'needs_clarification',
                            'reasons': ['The extent is not stated.']}],
                  'excluded': []}
    frozen = [['corti', 'a' * 64], [name, sha256_json(own)],
              ['revision', hashlib.sha256(TEXT.encode()).hexdigest()], ['cpt_studio', sha256_json(cpt_studio)]]
    return TEXT, (PageSpan(1, 0, len(TEXT)),), own, peers, cpt_studio, frozen


def document(name='astra', **heading):
    _, _, own, peers, cpt_studio, frozen = inputs(name)
    return prompt.peer_document(own, peers, cpt_studio, frozen, **heading)


def request(name):
    text, pages, own, peers, cpt_studio, frozen = inputs(name)
    return ReplayParticipant(name, '/nonexistent-replay-dir').build_peer_request(text, pages, 'paste', own, peers,
                                                                                 cpt_studio, frozen)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class HeadingTests(SimpleTestCase):
    def test_both_headings_are_pinned(self):
        self.assertEqual((prompt.READING_HEADING, prompt.EVENTS_READING_HEADING), (LEGACY, EVENTS))
        self.assertEqual(prompt.READING_HEADINGS, (LEGACY, EVENTS))

    def test_a_legacy_peer_document_is_byte_identical_to_the_one_before_the_migration(self):
        self.assertEqual(sha256(document()), LEGACY_DOCUMENT_SHA256)
        self.assertEqual(document(reading_heading=prompt.READING_HEADING), document())
        self.assertIn(f'== {LEGACY} ==', document().split('\n'))

    def test_legacy_peer_request_bytes_are_unchanged_through_the_real_adapters(self):
        for name in MODULES:
            with self.subTest(name=name):
                self.assertEqual(request(name).canonical_sha256, LEGACY_REQUEST_SHA256[name])

    def test_the_events_heading_changes_that_one_line_and_nothing_else(self):
        legacy, events = document().split('\n'), document(reading_heading=EVENTS).split('\n')
        self.assertEqual(sha256('\n'.join(events)), EVENTS_DOCUMENT_SHA256)
        self.assertEqual(len(legacy), len(events))
        self.assertEqual([(old, new) for old, new in zip(legacy, events) if old != new],
                         [(f'== {LEGACY} ==', f'== {EVENTS} ==')])
        # what the readers take back from a stored request - its question ids and frozen inputs - is the same
        self.assertEqual(prompt.peer_document_inputs('\n'.join(events)), prompt.peer_document_inputs('\n'.join(legacy)))
        with prompt.using_reading_heading(EVENTS):
            for name in MODULES:
                with self.subTest(name=name):
                    built = request(name)
                    self.assertEqual(built.canonical_sha256, EVENTS_REQUEST_SHA256[name])
                    self.assertEqual(peer.request_inputs(built, MODULES[name]._peer_document),
                                     prompt.peer_document_inputs(document(name, reading_heading=EVENTS)))

    def test_the_heading_is_a_closed_list(self):
        for wrong in ('', "CPT Studio's reading", 'Gemini reading', LEGACY.upper(), f'{EVENTS}\n== injected =='):
            with self.subTest(heading=wrong):
                with self.assertRaises(ValueError):
                    document(reading_heading=wrong)
                with self.assertRaises(ValueError):
                    with prompt.using_reading_heading(wrong):
                        pass
        self.assertEqual(sha256(document()), LEGACY_DOCUMENT_SHA256)  # a refused heading set nothing

    def test_the_heading_a_block_sets_holds_in_that_context_only(self):
        with prompt.using_reading_heading(EVENTS):
            self.assertEqual(sha256(document()), EVENTS_DOCUMENT_SHA256)
            self.assertEqual(sha256(document(reading_heading=LEGACY)), LEGACY_DOCUMENT_SHA256)  # an explicit one wins
            seen = []
            thread = threading.Thread(target=lambda: seen.append(sha256(document())))
            thread.start()
            thread.join()
            self.assertEqual(seen, [LEGACY_DOCUMENT_SHA256])  # another thread's requests are untouched
            self.assertEqual(sha256(contextvars.copy_context().run(document)), EVENTS_DOCUMENT_SHA256)
        self.assertEqual(sha256(document()), LEGACY_DOCUMENT_SHA256)
        with self.assertRaises(RuntimeError):
            with prompt.using_reading_heading(EVENTS):
                raise RuntimeError('a build that fails')
        self.assertEqual(sha256(document()), LEGACY_DOCUMENT_SHA256)  # reset on the way out of a failure too

    def test_the_adapter_versions_are_not_bumped(self):
        # the recorded exception (FINAL 6.6, 16.10): stored participant runs stay readable by the readers keyed on them
        self.assertEqual((openai_astra.ADAPTER_VERSION, anthropic_fable.ADAPTER_VERSION),
                         ('openai-responses@cptstudio-harness-2', 'anthropic-messages@cptstudio-harness-4'))
        self.assertEqual((prompt.READING_VERSION, prompt.PEER_VERSION), ('harness-reading@2', 'harness-peer@1'))

    def test_the_peer_stage_heads_only_a_new_path_first_assessment_with_the_events_heading(self):
        self.assertEqual(jobs._peer_reading_heading(SimpleNamespace(engine_version=interpretation.ENGINE_VERSION)),
                         EVENTS)
        for legacy in ('cpt-studio-validation@10', 'cpt-studio-validation@9', '', None):
            with self.subTest(engine=legacy):
                self.assertEqual(jobs._peer_reading_heading(SimpleNamespace(engine_version=legacy)), LEGACY)


@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class LegacyChainPeerRequestTests(EventsCase):
    """Through the pipeline: a peer review of a LEGACY assess #1 - the test-only legacy chain - is built by the stage
    with the legacy heading, byte-identical to the request the adapter builds with no heading named."""

    def test_a_legacy_first_assessments_peer_request_is_built_as_before(self):
        with legacy_chain(), mock.patch.object(jobs, '_legacy_reading_allowed', return_value=True):
            encounter, revision = self.upload()
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran],
                         [('analyze', 'succeeded'), ('predict', 'succeeded'), ('astra', 'succeeded'),
                          ('fable', 'succeeded'), ('assess', 'succeeded'), ('astra_peer', 'succeeded'),
                          ('fable_peer', 'succeeded'), ('assess', 'succeeded')])
        first, final = self.assessments(encounter)
        self.assertFalse(interpretation.is_new_assessment(first) or interpretation.is_new_assessment(final))
        self.assertEqual(ran[5].idempotency_key, f'astra_peer:{jobs._digest(first.pk)}')
        for name in SCRIPTED_MODULES:
            with self.subTest(name=name):
                [stored] = self.adapters[name].sent('peer')
                lines = MODULES[name]._peer_document(stored.body).split('\n')
                self.assertIn(f'== {LEGACY} ==', lines)
                self.assertNotIn(f'== {EVENTS} ==', lines)
                own, peers, cpt_studio, frozen = jobs._peer_material(revision, first, name, review.model_records(first))
                rebuilt = self.adapters[name].build_peer_request(revision.text, jobs._participant_pages(revision),
                                                                 'paste', own, peers, cpt_studio, frozen)
                self.assertEqual(rebuilt.canonical_sha256, stored.canonical_sha256)
                self.assertEqual(rebuilt.body, stored.body)
