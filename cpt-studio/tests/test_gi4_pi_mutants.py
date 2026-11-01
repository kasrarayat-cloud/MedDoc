"""GI round 4, package PI: H6's mutant registry - one killing mutant per guard the package adds
(tests/test_gi4_pi.py pins each guard). The H6 battery applies each to a copy of a sealed export with ops.gi4.mutants
(ops/gi4/mutants.py is outside the package; its runner takes these entries as they are) and runs the detector,
tests.test_gi4_pi, which must fail on the mutant and pass without it. This module is kept apart from that detector:
its anchor check below fails on every mutated copy by construction, and would otherwise kill every mutant whatever
the behaviour. Each anchor must occur exactly once in this tree, so the registry cannot rot silently.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot

# (name, guard, path, old, new, detector)
_T = 'unit:tests.test_gi4_pi'
PI_MUTANTS = (
    ('pi-reach-head', 'the reach needs a procedure report head', 'studio/gi/services.py',
     '    return _sections.procedure_report_head(text) and not _sections.around_procedure_title(text)',
     '    return not _sections.around_procedure_title(text)', _T),
    ('pi-reach-around-title', 'the reach is never read in a note written around a procedure', 'studio/gi/services.py',
     '    return _sections.procedure_report_head(text) and not _sections.around_procedure_title(text)',
     '    return _sections.procedure_report_head(text)', _T),
    ('pi-reach-occurrence', 'the reach is never read under another occurrence', 'studio/gi/services.py',
     '                            and not _sections.under_another_occurrence(_ORIGINAL.get() or text, m.start()):',
     '                            and True:', _T),
    ('pi-reach-date', 'the reach is never read in a clause carrying a date', 'studio/gi/services.py',
     '                    if own_report[0] and not _dates_in(dates, cs, ce) \\',
     '                    if own_report[0] \\', _T),
    ('pi-carry-part', 'a paragraph carries its service within its own part only', 'studio/gi/services.py',
     "    if part_start != part.start or part.kind in ('history', 'plan', 'indication'):",
     "    if part.kind in ('history', 'plan', 'indication'):", _T),
    ('pi-carry-part-kind', 'never into a history, plan or indication part', 'studio/gi/services.py',
     "    if part_start != part.start or part.kind in ('history', 'plan', 'indication'):",
     '    if part_start != part.start:', _T),
    ('pi-carry-performed', 'the carried family is one documented performed', 'studio/gi/services.py',
     '    if len(done) < 2 or family not in done:', '    if len(done) < 2:', _T),
    ('pi-carry-region', 'every site the statement names is one the carried family reaches', 'studio/gi/services.py',
     '    if named and not named <= FAMILY_REGIONS.get(family, frozenset()):', '    if False:', _T),
    ('pi-carry-reach', 'within CARRY_REACH characters', 'studio/gi/services.py',
     'CARRY_REACH = 1500  # A1:', 'CARRY_REACH = 10 ** 9  # A1:', _T),
    ('pi-carry-paragraph', 'no blank line between', 'studio/gi/services.py',
     '    if pos - end > CARRY_REACH or (pos > end and PARAGRAPH_BREAK.search(text, end, pos)):',
     '    if pos - end > CARRY_REACH:', _T),
    ('pi-carry-field', 'never a field or check-box row', 'studio/gi/services.py',
     '                                      field_row=_field_or_box_line(text, ms, me))',
     '                                      field_row=False)', _T),
    ('pi-carry-two-named', 'a sentence naming two families clears the carry', 'studio/gi/services.py',
     '            elif named_here:\n                carry = None',
     '            elif False:\n                carry = None', _T),
    ('pi-e1-section', 'E1: never from a history or plan section of the layout', 'studio/gi/services.py',
     "        if _sections.layout(t).section_at(pos).kind in ('history', 'plan') \\\n"
     '                or _sections.under_another_occurrence(t, pos):',
     '        if _sections.under_another_occurrence(t, pos):', _T),
    ('pi-e1-occurrence', 'E1: never under another occurrence', 'studio/gi/services.py',
     "        if _sections.layout(t).section_at(pos).kind in ('history', 'plan') \\\n"
     '                or _sections.under_another_occurrence(t, pos):',
     "        if _sections.layout(t).section_at(pos).kind in ('history', 'plan'):", _T),
    ('pi-e1-extent-word', 'E1: never from a statement carrying an extent word', 'studio/gi/services.py',
     '        if EXTENT_WORD.search(span.text) or (text and _pi_not_today_place(text, span.start)):',
     '        if text and _pi_not_today_place(text, span.start):', _T),
    ('pi-e1-occurrence-word', 'E1: never a landmark an earlier-occurrence word leads in its statement',
     'studio/gi/services.py',
     '            if any(not _sections.ANOTHER_OCCURRENCE_HEAD.search(span.text, 0, m.start())\n'
     '                   for m in pattern.finditer(span.text)):',
     '            if any(True for m in pattern.finditer(span.text)):', _T),
    ('pi-e1-routing-positive', "E1: never where routing reads the family done today", 'studio/validation/checks.py',
     '                    and (finding is None or finding.status not in POSITIVE):', '                    and True:', _T),
    ('pi-w1-another-stent', 'W1: dropped only beside another stent performed (hold-only)', 'studio/gi/services.py',
     "            if any(a.kind == 'stent' and a.status == 'performed' and a.id not in phantom for a in d.acts):",
     '            if True:', _T),
)


class MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for name, guard, path, old, new, detector in PI_MUTANTS:
            text = (boot.HARNESS_TREE / path).read_text(encoding='utf-8')
            self.assertEqual(text.count(old), 1, name)
            self.assertNotEqual(old, new, name)
            self.assertTrue(guard and detector == _T, name)
        self.assertEqual(len({m[0] for m in PI_MUTANTS}), len(PI_MUTANTS))
