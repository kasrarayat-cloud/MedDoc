"""The model family names (refutation L3-3, 2026-11-21): Opus, Sonnet, Haiku and ChatGPT are vendor or model names like
Claude and Gemini. customer.shown() replaces them in the coding review's own text ("Claude Opus 4.5" was shown as "The
system Opus 4.5"), and the shared denylist (ops/verification/customer-denylist.json, the same rules: tests/
test_api_customer.py pins them equal) finds them on every surface. A bare GPT, or GPT and a number, is not a name - GPT
is also the liver enzyme ALT ("GPT 45 U/L", "SGPT") - and neither is a word that only holds a name (haikus, sonnets,
opuscule, the gastric corpus, corticosteroid, affable). Through the API, a round whose reason, second-check reason,
question and note name them gives a page JSON, a TXT, a CSV and a physician PDF that carry none of them and pass the
customer scanner. Synthetic data only; nothing reaches the network."""
import io
import json
import re

from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader

from studio import customer
from tests.support import rounds as r

FAMILY = re.compile(r'(?<![a-z0-9])(?:opus|sonnet|haiku|chatgpt)(?![a-z0-9])', re.ASCII | re.IGNORECASE)


class FamilyNameFilterTests(SimpleTestCase):
    REPLACED = {
        'Claude Opus 4.5 read the snare; Claude Sonnet 5 agreed.': 'The system read the snare; the system agreed.',
        'Haiku and ChatGPT agree.': 'The system and the system agree.',
        'Did Claude Haiku miss the site?': 'Did the system miss the site?',
        'Opus could not tell the site.': 'The system could not tell the site.',
        'Read by chatgpt-4o-latest and claude-opus-4-5.': 'Read by the system and the system.',
        'held: SonnetTimeout': 'held: the systemTimeout',
        'the readingHaiku step': 'the readingthe system step',
        'OPUS and sonnet_unknown': 'The system and the system_unknown',
    }
    UNCHANGED = (
        'GPT 45 U/L, SGPT 52 U/L and ALT (GPT) within normal limits; GPT 5 days later was normal.',
        'Three haikus, two sonnets and an opuscule.',
        'Erythema in the gastric corpus; a corticosteroid was given by an affable nurse.',
    )

    def test_the_family_names_become_the_system(self):
        for text, expected in self.REPLACED.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)
                self.assertIsNone(FAMILY.search(customer.shown(text)))

    def test_gpt_as_the_liver_enzyme_and_words_that_only_hold_a_name_are_left_alone(self):
        for text in self.UNCHANGED:
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), text)

    def test_the_shared_denylist_finds_the_family_names_and_leaves_the_rest(self):
        sc = r.scan_customer()
        name_rules = {'provider_name', 'provider_name_joined', 'model_id', 'interpreter_model'}
        for text in self.REPLACED:
            with self.subTest(text=text):
                self.assertTrue({hit['id'] for hit in sc.scan_text(text, sc.scan_context(), 'file')} & name_rules)
        for text in self.UNCHANGED:
            with self.subTest(text=text):
                self.assertEqual(sc.scan_text(text, sc.scan_context(), 'file'), [])


class FamilyNameSurfaceTests(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.sc = r.scan_customer()
        self.client = self.client_for(self.reviewer)

    def made(self, enc, kind, fmt):
        shown = self.client.get(f'/api/encounters/{enc.pk}').json()['round']['number']
        made = self.client.post(f'/api/encounters/{enc.pk}/reports', content_type='application/json',
                                data=json.dumps({'kind': kind, 'fmt': fmt, 'round': shown}))
        self.assertEqual(made.status_code, 201, made.content)
        got = self.client.get(made.json()['download_url'])
        self.assertEqual(got.status_code, 200)
        return got

    def test_no_customer_surface_names_a_model_family(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row(
            '45385', 'ready', reason='Claude Opus 4.5 read the snare; Claude Sonnet 5 agreed.',
            check_reason='Haiku and ChatGPT agree; the GPT 45 U/L was normal.',
            question='Did Claude Haiku miss the site?')],
            problems=['Opus could not tell the site.'],
            citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}]})
        payload = self.client.get(f'/api/encounters/{enc.pk}').json()
        code = payload['codes'][0]
        self.assertEqual(code['reason'], 'The system read the snare; the system agreed.')
        self.assertEqual(code['second_check']['reason'], 'The system and the system agree; the GPT 45 U/L was normal.')
        self.assertEqual(code['question'], 'Did the system miss the site?')
        self.assertEqual(payload['notes'], ['The system could not tell the site.'])
        ctx = self.sc.scan_context(self.sc.quotations(payload))
        self.assertEqual(self.sc.scan_json(payload, ctx), [])
        for fmt in ('txt', 'csv'):
            with self.subTest(fmt=fmt):
                text = self.made(enc, 'draft', fmt).content.decode('utf-8')
                self.assertIsNone(FAMILY.search(text), text)
                self.assertIn('GPT 45 U/L', text)  # the liver enzyme is the coding review's clinical wording, kept
                self.assertEqual(self.sc.scan_file(text, ctx, f'draft.{fmt}', fmt), [])
        got = self.made(enc, 'draft', 'pdf')
        text = ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(got.content)).pages).split())
        self.assertIsNone(FAMILY.search(text), text)
        self.assertIn('Reason: The system read the snare; the system agreed.', text)
        self.assertIn('GPT 45 U/L', text)
        hits = self.sc.scan_pdf(self.sc.read_pdf(got.content), ctx, 'draft.pdf')
        self.sc.scan_headers(dict(got.items()), ctx, 'draft.pdf', hits)
        self.assertEqual(hits, [])
