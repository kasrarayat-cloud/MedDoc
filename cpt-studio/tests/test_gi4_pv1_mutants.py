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
_DATES = '    for d in an.dates_in(cs, ce):  # GI round 4 (C1): a date in an activity list still governs (see the docstring)\n'
_SKIP = '        if activities is not None and cue.start >= activities and _pv1_activity_work(cue):'
# C4's session-2 synonyms in cues.NOT_IN_PERSON, from the line before them to the pattern's end (exact source text)
_NO_SHOW = (' ' * 19 + r'''r"|\bno[- ]?show(?:s|ed)?\b|\b(?:did\s+not|didn't|failed\s+to)'''
            r'''\s+(?:arrive|attend|show\s+up)\b"''')
_SYNONYMS = _NO_SHOW + r'''
                   # session 2: "The patient was not seen.", a visit-type field naming the telephone ("Visit type:
                   # Telephone", "Type of encounter: phone"), "missed her appointment", "left without being seen"
                   r'|\b(?:patient|pt|she|he)\s+(?:was|is)\s+not\s+seen\b|\b(?:(?:visit|encounter|appointment|contact|'
                   r'consult(?:ation)?)\s+(?:type|mode|modality|method)|(?:type|mode|modality|method)\s+of\s+(?:visit|'
                   r'encounter|appointment|contact|consult(?:ation)?))[ \t]*[:\-][ \t]*(?:tele)?phone\b'
                   r"|\bmissed\s+(?:her|his|their|the|this|today'?s)\s+(?:scheduled\s+)?(?:appointment|visit)\b"
                   r'|\bleft\s+without\s+being\s+seen\b|\bLWBS\b')'''

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
                   _SKIP, '        if activities is not None and _pv1_activity_work(cue):', UNIT),
    mutants.Mutant('pv1-c1-plan-work', 'C1 (session 2): after the activity word only a planned cue is skipped (a '
                   'cancellation or a history still re-times the statement)', DETECT, _SKIP,
                   '        if activities is not None and cue.start >= activities:', UNIT),
    mutants.Mutant('pv1-c1-planned-time', 'C1 (session 2): a planned time after the activity word still re-times the '
                   'statement (only the plan words of the visit\'s work are skipped)', DETECT,
                   "    return cue.name in _PV1_PLAN_WORK_CUES or (cue.name == 'next' and "
                   "_PV1_NEXT_STEPS.match(cue.text) is not None)", '    return True', UNIT),
    mutants.Mutant('pv1-c1-dates-count', "C1: a date in an activity list still re-times the time statement", DETECT,
                   _DATES, _DATES + '        if activities is not None and d.start >= activities:\n            continue\n',
                   UNIT),
    mutants.Mutant('pv1-c1-time-only', "C1: only a time statement has an activity list (a visit statement's cues count)",
                   DETECT, _TIME_ONLY, _TIME_ONLY.replace("if m.kind != 'em-time':",
                                                          "if m.kind not in ('em-time', 'em-visit'):"), UNIT),
    mutants.Mutant('pv1-c2-shared', '"shared decision making" never gives an MDM level (a label and its separator)', CUES,
                   r"               r'|\b(?:complexity|level)\s+of\s+decision[- ]making[ \t]*[:\-][ \t]*)'",
                   r"               r'|\b(?:\w+\s+)?(?:of\s+)?decision[- ]making\b[^.;\n]{0,60}?)'", UNIT),
    mutants.Mutant('pv1-v3-ultrasound', "V3: an ultrasound named in an E/M code's negative passage holds the E/M", CHECKS,
                   'labs?|ultrasounds?|sonograms?|', 'labs?|sonograms?|', UNIT),
    mutants.Mutant('pv1-c4-synonyms', 'C4 (session 2): "the patient was not seen", a visit-type field naming the '
                   'telephone, "missed her appointment" and "left without being seen" hold every E/M reading', CUES,
                   _SYNONYMS, _NO_SHOW + ')', UNIT),
    mutants.Mutant('pv1-c2-opens-sentence', "C2 (session 2): the new label reads a level only when it opens its "
                   'sentence', DETECT, '        if label and not _pv1_opens_its_sentence(an.text, m.start, s):',
                   '        if False:', UNIT),
    mutants.Mutant('pv1-other-visit', 'C2 and C4-time (session 2): another visit named by a preposition, with or '
                   'without a determiner, holds a time statement or the new label', DETECT,
                   '        other = _pv1_other_visit(an, s, max(e, m.end), label)', '        other = None', UNIT),
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
