"""The completion repair's regression corpus (owner directive 2026-11-06, checklist item 1), pinned: every counterexample
that defeated a withdrawn releasing rule, the installed base's recorded false READYs and false holds, the stage-1
lenses' minimal pairs and the two fictional retained walk documents (tests/fixtures/gi4/completion/corpus.json, built and
measured by ops.gi4.completion; HARNESS.md "Completion repair (2026-11-06)").

Two pins, deliberately separate:
- every entry reads exactly as pinned on this tree. A repair that moves an entry re-pins it beside its declaration
  (``python -m ops.gi4.completion --repin``) and says which movement each is;
- no entry is a false READY (READY where its meaning lists or holds it, or before a coding ruling it waits on) unless it
  already was one on the installed release fd8040d71e44 (``baseline``, never re-pinned). Repairs may only remove false
  READYs.
Synthetic documents only."""
from django.test import SimpleTestCase

from ops.gi4 import completion

FIXTURE = completion.load()


class CompletionCorpusTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = completion.ledger(FIXTURE)

    def test_every_entry_reads_as_pinned(self):
        for entry, reading, verdict in self.rows:
            with self.subTest(entry['id']):
                self.assertEqual((verdict, reading), (entry['pinned']['verdict'], entry['pinned']['reading']),
                                 f"required {entry['required']}: {entry['why']}")

    def test_no_false_ready_beyond_the_installed_baseline(self):
        for entry, _, verdict in self.rows:
            with self.subTest(entry['id']):
                if verdict in completion.FALSE_READY:
                    self.assertIn(entry['baseline']['verdict'], completion.FALSE_READY,
                                  f"a new false READY: required {entry['required']}: {entry['why']}")

    def test_the_corpus_is_synthetic(self):
        import re
        identifiers = re.compile(r'\bMRN\b|\bDOB\b|date of birth', re.I)
        for i, text in enumerate(FIXTURE['texts']):
            with self.subTest(i):
                self.assertIsNone(identifiers.search(text))
