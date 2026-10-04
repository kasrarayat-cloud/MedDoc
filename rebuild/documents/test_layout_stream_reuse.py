"""Invocation-local painting order remains authoritative for every destination."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from pypdf.generic import NameObject

from . import layout_geometry as g
from . import test_layout_containment as fixtures


class PaintingStreamOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SequenceContainment.setUpClass()

    def setUp(self):
        self.fixture = fixtures.SequenceContainment()

    def candidate(self, title='Head summary', identity='head'):
        f = self.fixture
        header = [[], f.glyphs('Normal'), f.glyphs('Abnormal')]
        return f.candidate(identity, [[f.glyphs(title)], header, f.row('')], header_index=1)

    def test_one_current_stream_serves_all_candidates_with_exact_single_reader_results(self):
        f = self.fixture; pages = f.page(f.summary('Head summary', 300) + f.summary('Neck summary', 200))
        candidates = [self.candidate(), self.candidate('Neck summary', 'neck')]
        with patch.object(g, 'painting_stream', wraps=g.painting_stream) as compile_stream:
            result = g.containment(pages, candidates)
            self.assertEqual(compile_stream.call_count, 1)
        lines = [g.geometry(page) for page in pages]
        expected = [row for candidate in candidates for row in g.measure(lines, candidate)]
        self.assertEqual(result['measurements'], expected)
        self.assertTrue(result['passed']); self.assertEqual(result['held'], [])
        reverse = g.containment(pages, list(reversed(candidates)))
        self.assertEqual(reverse['measurements'], expected[2:] + expected[:2])

    def test_different_originals_and_call_order_cannot_reuse_a_verified_stream(self):
        f = self.fixture; candidate = self.candidate()
        valid = f.page(f.summary('Head summary', 300))
        duplicate = f.page(f.summary('Head summary', 300) + f.summary('Head summary', 200))
        wrong = f.page(f.summary('Head summary', 300, shift=80))
        for order in ((valid, duplicate, wrong, valid), (wrong, valid, duplicate, valid)):
            for pages in order:
                if pages is duplicate:
                    with self.assertRaises(ValueError): g.containment(pages, [candidate])
                else:
                    self.assertEqual(g.containment(pages, [candidate])['passed'], pages is valid)

    def test_same_page_object_mutation_is_reparsed_and_candidate_state_is_current(self):
        f = self.fixture; pages = f.page(f.summary('Head summary', 300)); candidate = self.candidate()
        original = pages[0]['/Contents']
        self.assertTrue(g.containment(pages, [candidate])['passed'])
        changed = f.page(f.summary('Head summary', 300) + f.summary('Head summary', 200))
        pages[0][NameObject('/Contents')] = changed[0]['/Contents']
        with self.assertRaises(ValueError): g.containment(pages, [candidate])
        pages[0][NameObject('/Contents')] = original
        self.assertTrue(g.containment(pages, [candidate])['passed'])
        selected = deepcopy(candidate)
        selected['rendered_source']['sequence'][-1]['segments'][1][-1]['checked'] = True
        with self.assertRaises(ValueError): g.containment(pages, [selected])
        self.assertTrue(g.containment(pages, [candidate])['passed'])

    def test_standalone_reader_keeps_whole_document_painting_order_and_duplicates(self):
        sequence = [{'segments': [[{'text': 'Named'}], [{'text': '1'}]]},
                    {'segments': [[{'text': 'Answer'}], [{'text': '2'}]]}]
        own_text = 'Named1Answer2'
        def page(text, backwards=False):
            records = [{'type': 'glyph', 'order': at, 'text': char} for at, char in enumerate(text)]
            return [{'records': list(reversed(records)) if backwards else records}]
        own = set(range(len(own_text)))
        for reverse in (False, True):
            lines = [page(own_text, reverse)]
            self.assertFalse(g.rendered_elsewhere(lines, 0, own, sequence))
            lines.append(page('Named.1 Answer_2', reverse))
            self.assertTrue(g.rendered_elsewhere(lines, 0, own, sequence))
            self.assertTrue(g.rendered_elsewhere(lines, 1, own, sequence))
            lines.pop()
            self.assertFalse(g.rendered_elsewhere(lines, 0, own, sequence))
        self.assertTrue(g.rendered_elsewhere([page(own_text)], 0, own - {0}, sequence))
        self.assertTrue(g.rendered_elsewhere([page(own_text)], 0, own, [{'segments': [[]]}]))

    def test_public_readers_do_not_accept_foreign_precompiled_authority(self):
        pages = self.fixture.page(self.fixture.summary('Head summary', 300)); candidate = self.candidate()
        lines = [g.geometry(page) for page in pages]
        with self.assertRaises(TypeError): g.containment(pages, [candidate], stream=())
        with self.assertRaises(TypeError): g.measure(lines, candidate, source_run_check=lambda *args: False)
        with self.assertRaises(TypeError): g.rendered_elsewhere(lines, 0, set(), [], cache=())
        self.assertTrue(g.containment(pages, [candidate])['passed'])
