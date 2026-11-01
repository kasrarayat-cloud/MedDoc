"""GI round 4, package PE: one killing mutant per guard PE adds, and the release itself (H6).

Each mutant names its guard, one exact anchor in studio/gi/detect.py and its replacement; its detector is
tests.test_gi4_pe, which holds the behaviour the guard keeps and no registry check (a mutant removes its own anchor, so a
registry check in the detector module would kill every mutant whatever the behaviour tests saw). The registry check is
here: every anchor occurs exactly once in this tree. The mutants are run on COPIES of a sealed export with
ops.gi4.mutants.applied (sha256 printed after the mutation and after the restore) and ops.gi4.mutants.detect, after the
detector passes on the unmutated export; the integrator may move them into ops/gi4/mutants.MUTANTS.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot
from ops.gi4.mutants import Mutant

_D = 'studio/gi/detect.py'
_UNIT = 'unit:tests.test_gi4_pe'
PE_MUTANTS = (
    Mutant('pe-vocabulary', "routing's own reach verbs are read (the release)", _D,
           '    found = cues.REACHED_BEFORE_ROUTING.search(pre)\n', '    found = cues.REACHED_BEFORE.search(pre)\n', _UNIT),
    Mutant('pe-endpoint', "a routing-only verb reads only the family's endpoint or beyond", _D,
           "    if depth < _S2_expected_depth(an, table):\n        return False  # short of the family's endpoint",
           "    if False:\n        return False  # short of the family's endpoint", _UNIT),
    Mutant('pe-doubt-governs', 'a negation, modal, infinitive, hedge or present tense governing the verb', _D,
           '    if re.search(r"(?:\\b(?:not|never|cannot|unable[ \\t\\n]+to|',
           '    if False and re.search(r"(?:\\b(?:not|never|cannot|unable[ \\t\\n]+to|', _UNIT),
    Mutant('pe-doubt-falling-short', 'a falling-short adverb before the verb', _D,
           '        return True  # it fell short', '        return False  # it fell short', _UNIT),
    Mutant('pe-doubt-plan', 'a wish, plan, attempt or condition before the verb', _D,
           '        return True  # a wish, a plan, an attempt or a condition',
           '        return False  # a wish, a plan, an attempt or a condition', _UNIT),
    Mutant('pe-doubt-span', 'a negation, hedge or attempt between the verb and the landmark', _D,
           '        return True  # denied or doubted between the verb and the landmark',
           '        return False  # denied or doubted between the verb and the landmark', _UNIT),
    Mutant('pe-doubt-post', 'another time or a condition after the landmark', _D,
           "    return re.search(r'\\b(?:later|tomorrow|upcoming|future|",
           "    return False and re.search(r'\\b(?:later|tomorrow|upcoming|future|", _UNIT),
    Mutant('pe-endoscope', 'the endoscope moved, never an accessory', _D,
           '    if not _pe_endoscope_moved(before, span):\n        return False', '    if False:\n        return False', _UNIT),
    Mutant('pe-around-procedure', 'no routing-only reach in a note written around a procedure', _D,
           '    if _pe_around_procedure(an):\n        return False', '    if False:\n        return False', _UNIT),
    Mutant('pe-another-occurrence', "no routing-only reach under a line naming another occurrence's record", _D,
           '    return not gi_sections.under_another_occurrence(an.text, at - len(pre) + found.start())',
           '    return True', _UNIT),
)


class MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for m in PE_MUTANTS:
            text = (boot.HARNESS_TREE / m.path).read_text(encoding='utf-8')
            self.assertEqual(text.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
        self.assertEqual(len({m.name for m in PE_MUTANTS}), len(PE_MUTANTS))
