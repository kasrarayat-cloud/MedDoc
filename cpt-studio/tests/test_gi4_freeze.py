"""GI round 4 harness, H2: the request-side freeze (ops/gi4/freeze.py), pinned against installed 80df1831d168.

A request is the document's text plus one "Date of service" line, so the date it carries is the only interpretation it
sends. (a) Every cue pattern context.py and sections.py read is byte-identical to installed (tests/fixtures/gi4/pins/
cues.json); a pattern may only be ADDED, and only when a package declaration names it (tests/fixtures/gi4/declarations/).
(b)-(d) Over the CI corpus (the regression texts, a slice of the generated corpus and seeded families, the repository's
own test texts) the layout, the date channel in every member state, every request's bytes and the mention counts equal
installed's (pins/freeze.json). The classifier and the gate are pinned on hand-made records: NEW-SEND and NEW-TAKE always
fail, and any other movement fails unless declared.
"""
import collections
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import freeze, observe, pins

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi4'
CUES = json.loads((FIXTURES / 'pins' / 'cues.json').read_text())
DIGESTS = json.loads((FIXTURES / 'pins' / 'freeze.json').read_text())
DECLARED = sorted({name for path in (FIXTURES / 'declarations').glob('*.json')
                   for name in json.loads(path.read_text()).get('cues_added', ())})


class CuePatternFreezeTests(SimpleTestCase):
    def test_every_pattern_the_request_side_reads_is_unchanged(self):
        now = freeze.cue_inventory()
        moved = freeze.compare_cues(CUES['cues'], now)
        self.assertEqual(moved['changed'], [], 'a constant context.py or sections.py reads changed')
        self.assertEqual(moved['removed'], [])
        self.assertEqual(sorted(set(moved['added']) - set(DECLARED)), [], 'an added pattern no declaration names')

    def test_the_inventory_reads_cues_and_module_constants(self):
        now = freeze.cue_inventory()
        self.assertGreater(len([k for k in now if k.startswith('cues.')]), 20)
        self.assertIn('context.SERVICE_DATE', now)
        self.assertIn('sections.HEADINGS', now)
        self.assertIn('cues.PROCEDURE_TITLE', now)

    def test_a_pattern_change_is_seen_flags_included(self):
        a = freeze._canon(re.compile('date', re.I))
        self.assertNotEqual(a, freeze._canon(re.compile('date')))
        self.assertNotEqual(a, freeze._canon(re.compile('dates', re.I)))
        self.assertEqual(freeze._canon(frozenset({'b', 'a'})), freeze._canon(frozenset({'a', 'b'})))
        self.assertIsNone(freeze._canon(object()))


class CorpusFreezeTests(SimpleTestCase):
    def test_layout_date_channel_requests_and_mentions_equal_installed(self):
        docs = pins.ci_corpus()
        now = pins.freeze_digests(docs, observe._modules())
        self.assertEqual(len(now), DIGESTS['texts'])
        moved = sorted(k for k in DIGESTS['digests'] if now.get(k) != DIGESTS['digests'][k])
        self.assertEqual(moved, [], 'texts whose request side moved against installed (run python -m ops.gi4.freeze '
                                    'for the classes)')


def _rec(sends='2026-10-19', taken=False, held=False, request='r1', layout='L', fact=None, mentions=(1, 1),
         answer=None, label='none'):
    return {'layout': layout, 'fact': fact or ['document', '2026-10-19', [], ''], 'mentions': list(mentions),
            'states': {label: {'answer': answer, 'sends': sends, 'taken': taken, 'held': held, 'request': request}}}


class ClassifierAndGateTests(SimpleTestCase):
    def classes(self, base, head):
        counts, _ = freeze.classify({'t': base}, {'t': head})
        return {k: v for k, v in counts.items() if v}

    def test_movements(self):
        self.assertEqual(self.classes(_rec(), _rec()), {})
        self.assertEqual(self.classes(_rec('DATELESS', request='r0'), _rec('2026-10-19')),
                         {'NEW-SEND': 1})
        self.assertEqual(self.classes(_rec('2026-10-18', request='r0'), _rec('2026-10-19')), {'NEW-SEND': 1})
        self.assertEqual(self.classes(_rec('HELD', held=True, request=None, answer='1998-01-01', label='far'),
                                      _rec('1998-01-01', taken=True, answer='1998-01-01', label='far')),
                         {'NEW-SEND': 1, 'NEW-TAKE': 1})
        self.assertEqual(self.classes(_rec('1998-01-01', taken=True, answer='1998-01-01', label='far'),
                                      _rec('HELD', held=True, request=None, answer='1998-01-01', label='far')),
                         {'NEW-HELD': 1})
        self.assertEqual(self.classes(_rec(), _rec('DATELESS', request='r0')), {'SEND->ASK': 1})
        self.assertEqual(self.classes(_rec(), _rec(request='r2')), {'REQUEST-CHANGED': 1})
        self.assertEqual(self.classes(_rec(), _rec(layout='M')), {'LAYOUT-CHANGED': 1})
        self.assertEqual(self.classes(_rec(), _rec(mentions=(2, 1))), {'MENTIONS-CHANGED': 1})

    def test_the_gate(self):
        cues = {'changed': [], 'removed': [], 'added': []}
        self.assertEqual(freeze.gate(cues, collections.Counter(), {}), [])
        self.assertTrue(freeze.gate(cues, collections.Counter({'NEW-SEND': 1}), {'movements': {'NEW-SEND': 9}}))
        self.assertTrue(freeze.gate(cues, collections.Counter({'NEW-TAKE': 1}), {'movements': {'NEW-TAKE': 9}}))
        self.assertTrue(freeze.gate(cues, collections.Counter({'NEW-HELD': 2}), {'movements': {'NEW-HELD': 1}}))
        self.assertEqual(freeze.gate(cues, collections.Counter({'NEW-HELD': 2}), {'movements': {'NEW-HELD': 2}}), [])
        self.assertTrue(freeze.gate(dict(cues, changed=['cues.X']), collections.Counter(), {}))
        self.assertTrue(freeze.gate(dict(cues, added=['sections.Y']), collections.Counter(), {}))
        self.assertEqual(freeze.gate(dict(cues, added=['sections.Y']), collections.Counter(),
                                     {'cues_added': ['sections.Y']}), [])
