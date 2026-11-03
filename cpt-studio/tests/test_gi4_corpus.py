"""GI round 4 harness, H3: the generated corpus and its truth tables (ops/gi4/gen.py, seeds.py, truth.py).

THE TRUTH TABLES ARE PROVISIONAL AUTHOR EXPECTATIONS; NO QUALIFIED GI CODER HAS REVIEWED THEM. These tests pin the
corpus (deterministic, every document kind the round-4 plan names, a family of at least 100 variants for every
regression document), the second review (a disputed cell is MAY and never judged; every table says no coder reviewed
it) and the judge (no cell passes vacuously: each property fails on an observation that breaks it).
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import corpus, gen, regression, seeds, truth

TABLES = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'pins' / 'tables.json').read_text())


class GeneratedCorpusTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.docs = corpus.generated() + corpus.seeded()

    def test_the_corpus_is_deterministic_and_pinned(self):
        again = [d['text'] for d in corpus.generated()]
        self.assertEqual(again, [d['text'] for d in self.docs if d['kind'] != 'seeded'])
        self.assertEqual(truth.table_counts(self.docs), TABLES['tables'])
        self.assertEqual(len({d['id'] for d in self.docs}), len(self.docs))

    def test_every_document_kind_of_the_plan(self):
        axes = [d['axes'] for d in self.docs]
        self.assertTrue({'call', 'booking', 'consent', 'instructions', 'education'} <= {a.get('around') for a in axes})
        self.assertTrue({'review', 'letter'} <= {a.get('records') for a in axes})
        self.assertEqual({a.get('reach') for a in axes if 'records' in a}, {'near', 'far'})
        self.assertEqual({a.get('named') for a in axes if 'records' in a}, {False, True})
        self.assertEqual({a.get('signed_other') for a in axes if 'records' in a}, {False, True})
        self.assertTrue({'telephone', 'video', 'no_show', 'addendum_time', 'procedure_day_hp'}
                        <= {a.get('mode') for a in axes})
        self.assertIn(True, {a.get('never') for a in axes if 'colon_phrase' in a})  # two services, past negation
        self.assertIn('headless', {a.get('head') for a in axes})
        self.assertEqual({a.get('layout') for a in axes if 'layout' in a}, {'lines', 'docx', 'ocr', 'wrap'})

    def test_a_family_of_at_least_100_for_every_regression_document(self):
        families = {}
        for d in self.docs:
            if d['kind'] == 'seeded':
                families[d['axes']['seed_of']] = families.get(d['axes']['seed_of'], 0) + 1
        self.assertEqual(sorted(families), sorted(regression.ALL_DOCS))
        self.assertTrue(all(n >= 100 for n in families.values()), families)

    def test_every_variant_keeps_the_source_but_its_slots(self):
        docs = regression.load_fixtures()
        for d in (x for x in self.docs if x['kind'] == 'seeded' and all(v == 0 for k, v in x['axes'].items()
                                                                        if k != 'seed_of')):
            self.assertEqual(d['text'], docs[d['axes']['seed_of']]['text'])

    def test_every_table_is_reviewed_and_says_no_coder_reviewed_it(self):
        for d in self.docs:
            review = d['truth']['review']
            self.assertFalse(review['coder_reviewed'])
            self.assertIn('No qualified GI coder', review['note'])
            for c in d['truth']['cells']:
                self.assertIn(c['level'], ('MUST', 'SHOULD', 'MAY'))
                if c.get('disputed'):
                    self.assertEqual(c['level'], 'MAY')
                    self.assertIn(c['author_level'], ('MUST', 'SHOULD'))


class JudgeTests(SimpleTestCase):
    """No property passes vacuously: each fails on an observation that breaks it and passes on one that keeps it."""

    def obs(self, **over):
        base = {'sent_initial': 'DATELESS', 'answers': {'D': {'sends': '2026-10-19', 'taken': True},
                                                       'F': {'sends': 'HELD', 'taken': False}},
                'routing': {'gi.colonoscopy': {'status': 'performed', 'facts': {'extent': ['cecum', 'document']},
                                               'missing': [], 'mentions': ['performed']},
                            'gi.office_em': {'status': 'performed', 'facts': {'time_minutes': ['44', 'document'],
                                                                              'mdm_level': ['moderate', 'document'],
                                                                              'em_basis': ['time', 'document']},
                                             'missing': [], 'mentions': ['performed']}},
                'inventory': [{'family': 'gi.colonoscopy', 'status': 'performed', 'acts': [['biopsy', 'performed', 'colon']],
                               'lesions': []}]}
        base.update(over)
        return base

    DOC = {'kind': 'procedure', 'truth': {'date': '2026-10-19', 'lower_regions': ['rectum', 'colon']}}

    def check(self, name, expect, keeps, breaks):
        c = {'cell': name, 'level': 'MUST', 'expect': expect}
        self.assertTrue(truth.evaluate(c, self.DOC, keeps), f'{name} should pass')
        self.assertFalse(truth.evaluate(c, self.DOC, breaks), f'{name} should fail')

    def test_each_property_can_fail(self):
        o = self.obs
        self.check('date.send', {'allowed': ['2026-10-19']}, o(), o(sent_initial='2026-11-23'))
        self.check('date.no-send-before-answer', 'asked', o(), o(sent_initial='2026-10-19'))
        self.check('date.answer-held[F]', 'not-taken', o(), o(answers={'F': {'sends': '1998-01-01', 'taken': True}}))
        self.check('date.own-read[in]', 'sent', o(sent_initial='2026-10-19'), o())
        self.check('status.not-denied[gi.colonoscopy]', 'x', o(), o(routing={'gi.colonoscopy': {
            'status': 'historical', 'facts': {}, 'missing': [], 'mentions': []}}))
        self.check('status.performed[gi.colonoscopy]', 'performed', o(), o(routing={}))
        self.check('status.not-performed[gi.egd]', 'x', o(), o(routing={'gi.egd': {
            'status': 'uncertain', 'facts': {}, 'missing': [], 'mentions': ['performed']}}))
        self.check('extent.read[gi.colonoscopy]', ['cec'], o(), o(routing={'gi.colonoscopy': {
            'status': 'performed', 'facts': {}, 'missing': [], 'mentions': []}}))
        self.check('extent.never-false-incomplete[gi.colonoscopy]', 'x', o(), o(routing={'gi.colonoscopy': {
            'status': 'performed', 'facts': {'extent': ['incomplete: sigmoid colon', 'document']}, 'missing': [],
            'mentions': []}}))
        self.check('act.today-read[gi.colonoscopy.biopsy]', 'performed', o(), o(inventory=[]))
        self.check('act.not-another-occurrence[gi.colonoscopy.biopsy]', 'x', o(inventory=[]), o())
        self.check('binding.lower-not-on-upper', 'none', o(), o(inventory=[
            {'family': 'gi.egd', 'status': 'performed', 'acts': [['snare', 'negated', 'rectum']], 'lesions': []}]))
        em = o()['routing']['gi.office_em']
        self.check('em.time-read', '44', o(), o(routing={'gi.office_em': dict(em, facts={})}))
        self.check('em.time-not-another-occurrence', '44', o(routing={'gi.office_em': dict(em, facts={})}), o())
        self.check('em.not-office-basis', 'no-basis', o(routing={}), o())
        self.check('em.mdm-read', 'moderate', o(), o(routing={'gi.office_em': dict(em, facts={})}))
        self.check('em.no-level-from-shared-decision', 'x', o(routing={'gi.office_em': dict(em, facts={})}), o())

    def test_a_cell_naming_no_family_is_refused(self):
        with self.assertRaises(KeyError):
            truth.evaluate({'cell': 'status.performed[gi]', 'level': 'MUST', 'expect': 'x'}, self.DOC, self.obs())

    def test_may_cells_are_never_judged(self):
        doc = {'kind': 'procedure', 'truth': {'date': '2026-10-19', 'cells': [
            {'cell': 'date.send', 'level': 'MAY', 'expect': {'allowed': []}}]}}
        self.assertEqual(truth.judge({'d': doc}, {'d': self.obs(sent_initial='1998-01-01')}), {'d': []})

    def test_the_seed_slots_and_the_generator_axes_are_well_formed(self):
        for doc_id, slots in seeds.SLOTS.items():
            for key, (anchor, alternatives) in slots.items():
                self.assertEqual(alternatives[0], anchor, (doc_id, key))
                self.assertEqual(len(set(alternatives)), len(alternatives), (doc_id, key))
        self.assertEqual(gen.render([['a', 'b'], ['c']], 'ocr'), 'a\n\nb\n\nc\n')
        self.assertEqual(gen.render([['a', 'b'], ['c']], 'docx'), 'a\nb\nc\n')
        self.assertEqual(gen.render([['a', 'b'], ['c']], 'lines'), 'a\nb\n\nc\n')
        self.assertTrue(all(len(line) <= 100 for line in gen.render([['x ' * 120]], 'wrap').splitlines()))
