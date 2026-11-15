"""The FRESH recordings, replayed (design/FINAL.md 14.2; slice S16).

Every answer gemini-4-argon gave on 2026-11-10 to the FRESH-A (the trial's seven texts), FRESH-B (the owner-example
classes) and FRESH-C (a stratified sample of the U32 registry) inputs - recorded through the production adapter on a
TEST instance under the live gate, and frozen before any evaluation - is kept in tests/fixtures/interpretation
(MANIFEST.json, FREEZE.sha256, documents/, gemini/, variance/). Labels: each recording is FRESH; reading one here is
REPLAY, and nothing is ever sent. Since DECISIONS D230 (2026-11-13) the interpreter's model is gemini-4-carbon; these
recordings stay labelled gemini-4-argon and are replayed as Argon's (D272): the read path checks each against the model
its own request named, which for a v1 request (gemini-generate@cptstudio-1) of record is Argon (adapter.READ_MODELS),
never by changing MODEL for the test.

What is asserted is the READING's structure, never a code:
- the fixture files are the frozen ones (FREEZE.sha256);
- each document, pasted, still frames the request that was recorded (its canonical sha256) - so a prompt, schema or
  framing change fails loudly here, and the recordings must then be made again before anything is re-pinned;
- the replay interpreter finds run 1 of each document by that request's own key, and replays it without sending (a
  document whose text another one shares - the registry has identical inputs under different claims - keeps its run 1
  under variance/, since a request has one replayed answer);
- every recorded answer is read (adapter.answer_text, interpretation.read) and normalized (interpretation.normalize) to
  exactly the verification counts, relation types, event count and open-question count the manifest pins. A change to
  reading, normalization or verification that moves a pin must move it deliberately: once anything is recorded in the
  product, under a new INVENTORY_VERSION and a re-normalization with no resend (FINAL 5.7).
"""
import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from studio import interpretation
from studio.ingest.extract import extract_paste
from studio.interpretation import MODEL, adapter, normalize
from studio.interpretation import read as interpretation_read
from studio.interpretation.replay import ReplayInterpreter
from studio.types import PageSpan, ProviderRequest

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'interpretation'
MANIFEST = json.loads((FIXTURES / 'MANIFEST.json').read_text(encoding='utf-8'))
DOCUMENTS = MANIFEST['documents']


def text_and_pages(entry):
    """The revision text and pages of a PASTE of the recorded input, as stage_extract and jobs._participant_pages make
    them (one canonical page, tiled to the end of the text)."""
    result = extract_paste((FIXTURES / entry['document']).read_bytes().decode('utf-8'))
    spans = sorted(result.pages, key=lambda span: span.start)
    tiled = []
    for index, span in enumerate(spans):
        end = spans[index + 1].start if index + 1 < len(spans) else len(result.text)
        tiled.append(PageSpan(page=span.page, start=tiled[-1].end if tiled else 0, end=end))
    return result.text, tuple(tiled)


def relation_types(content):
    return sorted(f"{r.get('type')}:{r.get('attribute')}:{r.get('reason')}"
                  for r in (content.get('events') or {}).get('relations') or [])


class FreezeTests(SimpleTestCase):
    def test_the_fixture_files_are_the_frozen_ones(self):
        lines = (FIXTURES / 'FREEZE.sha256').read_text(encoding='utf-8').splitlines()
        self.assertGreater(len(lines), len(DOCUMENTS))
        for line in lines:
            digest, _, name = line.partition('  ')
            with self.subTest(name):
                self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), digest)

    def test_the_manifest_covers_the_three_corpora_and_names_its_model(self):
        # the model the recordings' requests named: gemini-4-argon, the interpreter's model until DECISIONS D230, and a
        # model v1's requests named (adapter.READ_MODELS); MODEL, the model a request built now names, is Carbon
        self.assertEqual(MANIFEST['model'], 'gemini-4-argon')
        self.assertEqual(MANIFEST['model'], adapter.ARGON)
        self.assertIn(MANIFEST['model'], adapter.READ_MODELS[interpretation.ADAPTER_VERSION])
        self.assertEqual(MODEL, 'gemini-4-carbon')
        self.assertEqual({entry['corpus'] for entry in DOCUMENTS}, {'A', 'B', 'C'})
        self.assertTrue(all(entry['label'] == 'FRESH' for entry in DOCUMENTS))

    def test_every_recording_is_argons_and_is_read_only_as_a_v1_answer(self):
        # D272: the Argon recordings stay as recorded and are replayed as Argon's. Each body names gemini-4-argon, as
        # the manifest says; the read path takes it for the v1 request it answers, and the same bytes, read as an answer
        # to a request of design v2 (which names MODEL), are refused - so a replay reads them as Argon's, never as Carbon's
        v2_request = ProviderRequest(provider=adapter.NAME, adapter_version=adapter.ADAPTER_VERSION_V2, body={},
                                     canonical_sha256='0' * 64, contexts=())
        bodies = 0
        for entry in DOCUMENTS:
            for run, recorded in sorted(entry['runs'].items()):
                body = (FIXTURES / recorded['body']).read_bytes()
                with self.subTest(f"{entry['corpus']}/{entry['id']}/{run}"):
                    self.assertEqual(json.loads(body)['modelVersion'], MANIFEST['model'])
                    self.assertEqual(recorded.get('returned_model', MANIFEST['model']), MANIFEST['model'])
                    refused = adapter.answer_text_v2(v2_request, body)
                    self.assertEqual((refused.stage, refused.reason),
                                     ('envelope', 'The interpretation was not used: the response names a model other '
                                                  'than the one requested.'))
                    bodies += 1
        self.assertGreater(bodies, len(DOCUMENTS))


class RequestTests(SimpleTestCase):
    def test_each_document_still_frames_the_request_it_answers(self):
        interpreter = adapter.Interpreter()
        for entry in DOCUMENTS:
            with self.subTest(f"{entry['corpus']}/{entry['id']}"):
                text, pages = text_and_pages(entry)
                request = interpreter.build_request(text, pages, 'paste')
                self.assertEqual(request.canonical_sha256, entry['request_sha256'],
                                 'the request this document frames is no longer the one recorded: the prompt, the '
                                 'schema or the framing changed - record the FRESH corpora again before re-pinning')

    def test_the_replay_interpreter_answers_run_1_by_the_requests_own_key_and_sends_nothing(self):
        interpreter = ReplayInterpreter(FIXTURES)
        for entry in DOCUMENTS:
            run = entry['runs'].get('r1') or {}
            if not str(run.get('body', '')).startswith('gemini/'):
                continue  # a document whose text another one shares: its run 1 is kept under variance/
            with self.subTest(f"{entry['corpus']}/{entry['id']}"):
                text, pages = text_and_pages(entry)
                exchange = interpreter.send(interpreter.build_request(text, pages, 'paste'), deadline_s=30)
                self.assertEqual((exchange.outcome, exchange.sent), ('succeeded', False))
                self.assertEqual(exchange.response_sha256, run['body_sha256'])
                self.assertEqual(exchange.returned_model, MANIFEST['model'])  # the recording's own: Argon (D272)


class ReadingTests(SimpleTestCase):
    def test_every_recorded_answer_reads_and_normalizes_to_its_pins(self):
        interpreter = adapter.Interpreter()
        checked = 0
        for entry in DOCUMENTS:
            text, pages = text_and_pages(entry)
            request = interpreter.build_request(text, pages, 'paste')
            for run, recorded in sorted(entry['runs'].items()):
                if 'pins' not in recorded:
                    continue
                with self.subTest(f"{entry['corpus']}/{entry['id']}/{run}"):
                    body = (FIXTURES / recorded['body']).read_bytes()
                    self.assertEqual(hashlib.sha256(body).hexdigest(), recorded['body_sha256'])
                    answer = adapter.answer_text(request, body)
                    self.assertNotIsInstance(answer, interpretation_read.Refusal)
                    parsed = interpretation_read.read(answer)
                    self.assertNotIsInstance(parsed, interpretation_read.Refusal, getattr(parsed, 'reason', ''))
                    content = normalize.normalize(parsed, text).content()
                    pins = recorded['pins']
                    self.assertEqual((content.get('verification') or {}).get('counts'), pins['verification_counts'])
                    self.assertEqual(relation_types(content), pins['relation_types'])
                    self.assertEqual(len((content.get('events') or {}).get('events') or []), pins['events'])
                    self.assertEqual(len(content.get('open_questions') or []), pins['open_questions'])
                    checked += 1
        self.assertGreaterEqual(checked, len(DOCUMENTS))
