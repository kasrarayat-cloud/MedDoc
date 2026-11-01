"""GI round 4, package PV1, H6: one killing mutant per guard PV1 adds, each detected by tests/test_gi4_pv1.py (a unit
test, no database). They are registered here rather than in ops/gi4/mutants.py, which is stage A's registry and no
package of the round edits; the integrator merges them into it. ops.gi4.mutants.applied runs them unchanged once they are
in its registry: a sealed copy is mutated, the sha256 is printed after the mutation is applied and again after it is
restored, and an anchor that does not occur exactly once is NOT RUN, never killed. Each anchor is checked against this
tree below, so the registry cannot rot silently.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

DETECT, CUES, CHECKS = 'studio/gi/detect.py', 'studio/gi/cues.py', 'studio/validation/checks.py'
UNIT = 'unit:tests.test_gi4_pv1'
_HOLD = "        return Reading('uncertain', (f\"{EM_NOT_IN_PERSON}: '{words}'\",), 'cue', doubt=True)"
_TIME_HOLD = "    if m.kind == 'em-time' or _pv1_decision_label(an, m):"
_TIME_ONLY = "    if m.kind != 'em-time':\n        return None\n    listed = cues.EM_TIME_ACTIVITIES"

MUTANTS = (
    mutants.Mutant('pv1-c4-hold', 'C4: a performed E/M reading is held when the note may document no in-person visit',
                   DETECT, '    if words is not None:\n' + _HOLD, '    if False:\n' + _HOLD, UNIT),
    mutants.Mutant('pv1-c4-head', "C4: the head's title lines are read whatever section they fall in", DETECT,
                   '            title = cues.NOT_IN_PERSON_TITLE.search(text, 0, gi_sections.head_lines_end(text, '
                   '_PV1_HEAD_LINES))', '            title = None', UNIT),
    mutants.Mutant('pv1-c4-own-sentence', "C4: the E/M statement's own sentence is read whatever its section", DETECT,
                   '    if i < len(spans) and spans[i][1] <= e:', '    if False:', UNIT),
    mutants.Mutant('pv1-another-time', "C4: installed's _another_time holds a performed E/M time statement", DETECT,
                   _TIME_HOLD, '    if _pv1_decision_label(an, m):', UNIT),
    mutants.Mutant('pv1-c2-another-time', "C2: the new decision-making label takes the time statement's hold", DETECT,
                   _TIME_HOLD, "    if m.kind == 'em-time':", UNIT),
    mutants.Mutant('pv1-c1-after-only', 'C1: a cue before the activity word still re-times the time statement', DETECT,
                   '        if activities is not None and cue.start >= activities:', '        if activities is not None:',
                   UNIT),
    mutants.Mutant('pv1-c1-time-only', "C1: only a time statement has an activity list (a visit statement's cues count)",
                   DETECT, _TIME_ONLY, _TIME_ONLY.replace("if m.kind != 'em-time':",
                                                          "if m.kind not in ('em-time', 'em-visit'):"), UNIT),
    mutants.Mutant('pv1-c2-shared', '"shared decision making" never gives an MDM level (a label and its separator)', CUES,
                   r"               r'|\b(?:complexity|level)\s+of\s+decision[- ]making[ \t]*[:\-][ \t]*)'",
                   r"               r'|\b(?:\w+\s+)?(?:of\s+)?decision[- ]making\b[^.;\n]{0,60}?)'", UNIT),
    mutants.Mutant('pv1-v3-ultrasound', "V3: an ultrasound named in an E/M code's negative passage holds the E/M", CHECKS,
                   'labs?|ultrasounds?|sonograms?|', 'labs?|sonograms?|', UNIT),
)
BY_NAME = {m.name: m for m in MUTANTS}


class PV1MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for m in MUTANTS:
            text = (boot.HARNESS_TREE / m.path).read_text(encoding='utf-8')
            self.assertEqual(text.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
            self.assertIn(m.new, text.replace(m.old, m.new, 1), m.name)

    def test_names_detectors_and_guards(self):
        names = [m.name for m in MUTANTS]
        self.assertEqual(len(set(names)), len(names))
        self.assertTrue(all(n.startswith('pv1-') for n in names))
        self.assertEqual(set(names) & set(mutants.BY_NAME), set())  # never a stage A name
        for m in MUTANTS:
            self.assertEqual(m.detector, UNIT, m.name)
            self.assertTrue(m.guard, m.name)
