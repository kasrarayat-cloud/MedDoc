"""GI round 4, package PO, H6: the registry of PO's mutants - at least one per guard in validation/engine.py's _po_
helpers, the amendment's holds (A1-A5, declaration amendment_20261101) included - each killed by tests/test_gi4_po.py
(the detector, which holds no check of this registry: an anchor check fails on every mutated copy and would kill every
mutant by construction). Here every anchor is checked against this tree, so the
registry cannot rot silently. The harness applies a mutant to a COPY of a sealed export and prints the sha256 after it
is applied and again after it is restored (ops.gi4.mutants.applied); these entries use the same Mutant record and are
registered with that machinery at run time, not in ops/gi4/mutants.py.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

ENGINE = 'studio/validation/engine.py'
UNIT = 'unit:tests.test_gi4_po'
PO_MUTANTS = (
    mutants.Mutant('po-document-head', "PO: the document's head carries a procedure report's own fields (PS guard)",
                   ENGINE, '    return (gi_sections.procedure_report_head(text)\n', '    return (True\n', UNIT),
    mutants.Mutant('po-document-sedation', 'PO A1: a head field labelled sedation or anaesthesia', ENGINE,
                   '            and _po_sedation_field(text)\n', '            and True\n', UNIT),
    mutants.Mutant('po-sedation-label', 'PO A1: the label, not a word anywhere in a head line, names sedation', ENGINE,
                   '    return end > 0 and _PO_SEDATION_FIELD.search(text, 0, end) is not None',
                   '    return end > 0 and gi_sections.PROCEDURE_HEAD.search(text, 0, end) is not None', UNIT),
    mutants.Mutant('po-document-around', 'PO: no head line is the title of a note written around a procedure', ENGINE,
                   '            and not gi_sections.around_procedure_title(text)\n', '            and True\n', UNIT),
    mutants.Mutant('po-document-not-done', 'PO A5: no unnamed statement that a procedure was called off or not done',
                   ENGINE, '            and not _po_procedure_not_done(text))', '            and True)', UNIT),
    mutants.Mutant('po-not-done-other', 'PO A5: "no other procedures were performed" says nothing was not done',
                   ENGINE, r'    r"\bno\s+(?!(?:other|further|additional|more|separate|extra|second)\b)(?:[\w-]+\s+){1,2}?"',
                   r'    r"\bno\s+(?:[\w-]+\s+){1,2}?"', UNIT),
    mutants.Mutant('po-family-on-title', 'PO A2: routing names the family on a title line of the head', ENGINE,
                   '    if not named:  # A2', '    if not mentions:  # A2', UNIT),
    mutants.Mutant('po-title-before-fields', "PO A2: a title stands before the head's first field line", ENGINE,
                   "                break  # the head's first field line: the title stands before it",
                   "                pass  # mutant: the head's fields are read through", UNIT),
    mutants.Mutant('po-unreadable-passage', 'PO: a passage outside the text never reads as saying nothing', ENGINE,
                   '            return False\n        readings.append(', '            continue\n        readings.append(',
                   UNIT),
    mutants.Mutant('po1-family-silent', 'PO-1: every mention of the family is silent', ENGINE,
                   '    if all(_po_silent(m.status, m.cues) for m in mentions):  # PO-1', '    if True:  # PO-1', UNIT),
    mutants.Mutant('po1-evidence-says-nothing', "PO-1: no passage of the item reads as not today or doubted", ENGINE,
                   '        return all(_po_says_nothing(status, cues) for _, status, cues in readings)',
                   '        return True', UNIT),
    mutants.Mutant('po2-family-contradicts', 'PO-2: no mention of the family contradicts', ENGINE,
                   '        return False\n    if not any(_po_on_title(titles, pos)',
                   '        continue\n    if not any(_po_on_title(titles, pos)', UNIT),
    mutants.Mutant('po2-evidence-on-title', "PO A3: a passage of the item on a title line says nothing", ENGINE,
                   '    if not any(_po_on_title(titles, pos) and _po_says_nothing(status, cues)\n'
                   '               for pos, status, cues in readings):  # A3',
                   '    if False:  # A3', UNIT),
    mutants.Mutant('po2-at-least-one', "PO-2: at least one passage of the item is a runaway section's", ENGINE,
                   '    return any(runaway) and all(', '    return all(', UNIT),
    mutants.Mutant('po-says-nothing-worded', 'PO: a worded doubt says something', ENGINE,
                   '    return status == \'uncertain\' and bool(cues) and all(\n'
                   '        c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX, checks.SILENT_CUE_PREFIX))\n'
                   '        or c == UNESTABLISHED for c in cues)',
                   "    return status == 'uncertain'", UNIT),
    mutants.Mutant('po2-another-occasion-clean', "PO-2: another occasion's mention carries no doubt or denial", ENGINE,
                   '    return any(c.startswith(_PO_OWN_TIME) for c in cues) and all(\n'
                   '        c.startswith(_PO_OWN_TIME + (checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in '
                   'cues)',
                   '    return any(c.startswith(_PO_OWN_TIME) for c in cues)', UNIT),
    mutants.Mutant('po-runaway-section-only', 'PO-2: the not-today reading takes its time only from its section', ENGINE,
                   '            or not all(c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in '
                   'cues) \\\n            or not any(c.startswith(checks.SECTION_CUE_PREFIX) for c in cues):',
                   '            or False:', UNIT),
    mutants.Mutant('po-runaway-within-reach', "PO-2: the section's heading lies within the helper's reach", ENGINE,
                   "    if lo < 0 or lo >= pos or pos - lo > gi_sections.HEADING_REACH_CHARS \\\n"
                   "            or text.count('\\n', lo, pos) > gi_sections.HEADING_REACH_LINES:",
                   '    if lo < 0 or lo >= pos:', UNIT),
    mutants.Mutant('po-runaway-unread-heading', 'PO-2: an unread heading-like line stands between heading and passage',
                   ENGINE, '    return (gi_sections.beyond_heading_reach(text, lay, pos)\n', '    return (True\n', UNIT),
    mutants.Mutant('po-runaway-occurrence', 'PO-2: the nearest short line above names no other occurrence', ENGINE,
                   '            and not gi_sections.under_another_occurrence(text, pos)\n', '            and True\n', UNIT),
    mutants.Mutant('po-runaway-occurrence-between', 'PO A4: no unread heading-like line within the reach names another '
                   'occurrence', ENGINE, '            and not _po_unread_line_names_another_occurrence(text, lo, pos))',
                   '            and True)', UNIT),
)


class MutantRegistryTests(SimpleTestCase):
    def test_every_po_mutant_applies_exactly_once_and_names_its_guard(self):
        source = (boot.HARNESS_TREE / ENGINE).read_text(encoding='utf-8')
        for m in PO_MUTANTS:
            self.assertEqual(source.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
            self.assertTrue(m.guard and m.detector == UNIT, m.name)
        self.assertEqual(len({m.name for m in PO_MUTANTS}), len(PO_MUTANTS))
        self.assertFalse({m.name for m in PO_MUTANTS} & set(mutants.BY_NAME))
