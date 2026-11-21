"""Model family names (refutation L3-3, then round 2, 2026-11-21): a family's name (Opus, Sonnet, Haiku) is a vendor or
model name only where it continues a vendor's name, and customer.shown() then replaces the whole run ("Claude 3 Opus"
read "the system", never "the system the system" or "the system Opus"). Alone, a family's name is an ordinary or a clinical word - the OPUS trial of cetuximab, a
MED-EL SONNET 2 or OPUS 2 audio processor, a haiku - and another company's product named in a note ("the patient asked
ChatGPT") is clinical context: neither is replaced, and neither is a hit of the shared denylist (ops/verification/
customer-denylist.json; tests/test_api_customer.py pins its name rules equal to the filter's). A bare GPT, or GPT and a
number, is not a name - GPT is also the liver enzyme ALT. Through the API, a round written that way gives a page JSON and
a physician PDF (the only report since the owner's direction of 2026-11-21: no more TXT or CSV) that carry no vendor
name, keep the clinical words, and pass the customer scanner. Synthetic data only; nothing reaches the network."""
import io
import json
import re

from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader

from studio import customer
from tests.support import rounds as r

VENDOR = re.compile(r'(?<![a-z0-9])(?:claude|gemini|anthropic|openai|fable)', re.ASCII | re.IGNORECASE)


class FamilyNameFilterTests(SimpleTestCase):
    REPLACED = {
        'Claude Opus 4.5 read the snare; Claude Sonnet 5 agreed.': 'The system read the snare; the system agreed.',
        'Claude 3 Opus read the note.': 'The system read the note.',
        'Claude 3.5 Sonnet read it.': 'The system read it.',
        'Did Claude Haiku miss the site?': 'Did the system miss the site?',
        'Claude 3.5 Sonnet read the snare; Gemini 2.5 agrees.': 'The system read the snare; the system agrees.',
        'Read by claude-opus-4-5 and gpt-4o.': 'Read by the system and the system.',
        'Claude Fable 5.2 read it.': 'The system read it.',
    }
    UNCHANGED = (
        'Programming of the MED-EL SONNET 2 audio processor is documented; the OPUS 2 processor was checked as the '
        'backup.',
        'Enrolled in the OPUS trial of cetuximab.',
        'Is the SONNET 2 a replacement processor (L8619)?',
        'Wrote a haiku about the prep.',
        'The patient had asked ChatGPT about the bowel preparation.',
        'GPT 45 U/L, SGPT 52 U/L and ALT (GPT) within normal limits; GPT 5 days later was normal.',
        'Three haikus, two sonnets and an opuscule.',
        'Erythema in the gastric corpus; a corticosteroid was given by an affable nurse.',
    )

    def test_a_family_name_that_continues_a_vendor_name_goes_with_it(self):
        for text, expected in self.REPLACED.items():
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), expected)

    def test_a_family_name_alone_and_other_clinical_words_are_left_alone(self):
        for text in self.UNCHANGED:
            with self.subTest(text=text):
                self.assertEqual(customer.shown(text), text)

    def test_the_shared_denylist_finds_the_vendor_names_and_leaves_the_clinical_words(self):
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

    def made(self, enc, kind):
        shown = self.client.get(f'/api/encounters/{enc.pk}').json()['round']['number']
        made = self.client.post(f'/api/encounters/{enc.pk}/reports', content_type='application/json',
                                data=json.dumps({'kind': kind, 'fmt': 'pdf', 'round': shown}))
        self.assertEqual(made.status_code, 201, made.content)
        got = self.client.get(made.json()['download_url'])
        self.assertEqual(got.status_code, 200)
        return got

    def test_no_customer_surface_names_a_vendor_and_the_clinical_words_stay(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row(
            '45385', 'ready', reason='Claude 3 Opus read the snare; the MED-EL SONNET 2 processor was checked.',
            check_reason='Claude 3.5 Sonnet agrees; the patient had asked ChatGPT about the prep.',
            question='Did Claude Haiku miss the site?')],
            problems=['Gemini 2.5 could not tell the site; the patient is in the OPUS trial.'],
            citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}]})
        payload = self.client.get(f'/api/encounters/{enc.pk}').json()
        code = payload['codes'][0]
        self.assertEqual(code['reason'], 'The system read the snare; the MED-EL SONNET 2 processor was checked.')
        self.assertEqual(code['second_check']['reason'], 'The system agrees; the patient had asked ChatGPT about the prep.')
        self.assertEqual(code['question'], 'Did the system miss the site?')
        self.assertEqual(payload['notes'], ['The system could not tell the site; the patient is in the OPUS trial.'])
        ctx = self.sc.scan_context(self.sc.quotations(payload))
        self.assertEqual(self.sc.scan_json(payload, ctx), [])
        got = self.made(enc, 'draft')
        text = ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(got.content)).pages).split())
        self.assertIsNone(VENDOR.search(text), text)
        self.assertIn('Reason: The system read the snare; the MED-EL SONNET 2 processor was checked.', text)
        for kept in ('asked ChatGPT', 'OPUS trial'):
            self.assertIn(kept, text)
        hits = self.sc.scan_pdf(self.sc.read_pdf(got.content), ctx, 'draft.pdf')
        self.sc.scan_headers(dict(got.items()), ctx, 'draft.pdf', hits)
        self.assertEqual(hits, [])
