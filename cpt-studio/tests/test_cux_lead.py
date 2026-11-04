"""Core repair and customer interface (2026-11-03), the lead's integration reader repairs (declared before code in
tests/fixtures/gi4/declarations/cux-lead.json): L1 wires P2's labelled single-service heading into P1's parts() (R8 D7),
L2 reads a procedure-line title only in a physician part (R8 D6), L3 makes the own-passage release read act mentions
with services._acts_in, so an attributive act compound is no act (P1 rule 2 at P2's release). Hold-only."""
from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import services as gi_services
from studio.gi.services import Span, _Part
from tests.test_cux_bind import acts, inventory
from tests.test_cux_hold import READY, proposal, row, run, sel, span, state

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations' / 'cux-lead.json')
                         .read_text(encoding='utf-8'))
DECLARED = {(name, code): (before, after) for name, code, before, after in DECLARATION['battery']}
# the lead rows' codes the declaration does not move, measured on d43d1e363 (the rows added, the code unchanged)
UNMOVED = {
    ('R8 D7 H1 separate same-day note', '45385'): READY,
    ('R8 L3 control, biopsy-proven Barrett and a biopsy today', '43239'): READY,
}

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
CO_SNARE = 'A 7 mm polyp in the ascending colon was removed with a cold snare.'
FS_BIOPSY = 'Biopsies of the rectal mucosa were taken with cold forceps.'
COLON = (B + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
         'Procedure: Colonoscopy\n' + CECUM + '\n')


def colon_then(heading):
    """R8's H1 shape: a colonoscopy with its snare, then ``heading`` over a flexible sigmoidoscopy and its biopsy."""
    return (COLON + CO_SNARE + '\n\n' + heading + '\nThe flexible sigmoidoscope was advanced to 60 cm in the descending '
            'colon.\n' + FS_BIOPSY + '\n')


TODAY_BX = 'A 4 mm polyp in the transverse colon was biopsied with cold forceps.'
PATH_HEADING = 'PATHOLOGY ADDENDUM - 2026-09-02 hot snare polypectomy specimen, sigmoid colon'
F4C = COLON + TODAY_BX + '\n\n' + PATH_HEADING + '\nSigmoid colon, polypectomy: tubular adenoma.\n'
EGD = (B + 'Upper endoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
       'Procedure: EGD\nThe gastroscope was advanced to the second portion of the duodenum.\n')
BARRETT = 'Surveillance of biopsy-proven Barrett esophagus was performed.'


class LeadRowsTests(SimpleTestCase):
    """Every lead battery row ends where the declaration says, with no violation; its other codes keep their base
    state."""

    def test_the_rows(self):
        names = DECLARATION['battery_rows_added']
        self.assertEqual(sorted(names), sorted(n for n in battery.CASES if n.startswith(('R8 D7 ', 'R8 L3 '))))
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    expected = DECLARED[(name, code)][1] if (name, code) in DECLARED else UNMOVED[(name, code)]
                    self.assertEqual(state(result, code), expected)
                    self.assertEqual(result['proposals'][code]['violations'], [])


class LabelledNotePartTests(SimpleTestCase):
    """L1 (R8 D7): a 'Label: <service>' heading of one service opens a report part, so a separate same-day note's acts
    are its own service's - never the report above it."""

    def test_the_separate_note_s_biopsy_is_the_flexible_sigmoidoscopy_s(self):
        text = colon_then('Separate note: Flexible sigmoidoscopy (fictional), 2026-10-14')
        inv = inventory(text)
        self.assertEqual([a.kind for a in acts(inv, 'gi.colonoscopy')], ['snare'])
        self.assertEqual([a.kind for a in acts(inv, 'gi.flex_sig')], ['biopsy'])
        result = run(text, [sel('45385', span(text, CO_SNARE)), sel('45380', span(text, FS_BIOPSY))])
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assertEqual(proposal(result, '45380').status, 'needs_clarification')

    def test_a_line_the_helper_refuses_opens_no_part(self):
        # must-stay (the helper's own refusals, read through parts()): another time, a plan, two services
        for heading in ('Separate note: Flexible sigmoidoscopy planned next year', 'Separate note: EGD and colonoscopy',
                        'Second procedure: Flexible sigmoidoscopy (2023-05-02)'):
            with self.subTest(heading):
                text = colon_then(heading)
                self.assertFalse([p for p in gi_services.parts(text) if p.title is not None and p.title.text == heading])

    def test_a_bare_procedure_field_is_still_no_title(self):
        # the trap R8 1.3 records: "Procedure: Flexible sigmoidoscopy" is a field of today's report, never a new part
        text = colon_then('Procedure: Flexible sigmoidoscopy')
        self.assertFalse([p for p in gi_services.parts(text) if p.title is not None
                          and p.title.text == 'Procedure: Flexible sigmoidoscopy'])


class PhysicianTitleTests(SimpleTestCase):
    """L2 (R8 D6): a procedure-line title is read only in a physician part."""

    def test_a_pathology_heading_states_no_act_of_today_s_report(self):
        inv = inventory(F4C)
        self.assertEqual(sorted(a.kind for a in acts(inv, 'gi.colonoscopy')), ['biopsy'])
        result = run(F4C, [sel('45380', span(F4C, TODAY_BX)), sel('45385', span(F4C, PATH_HEADING))])
        self.assertEqual(proposal(result, '45380').status, 'ready')
        self.assertEqual(proposal(result, '45385').status, 'needs_clarification')

    def test_the_title_branch_by_role(self):
        text = 'Colonoscopy with hot snare polypectomy report\nThe colonoscope was advanced to the cecum.\n'
        title = Span(0, text.index('\n'), text[:text.index('\n')])
        pos = text.index('snare')
        physician = _Part(0, len(text), 'gi.colonoscopy', 'physician', title, 'report')
        pathology = _Part(0, len(text), 'gi.colonoscopy', 'pathology', title, 'report')
        self.assertTrue(gi_services._on_procedure_line(text, pos, physician))
        self.assertFalse(gi_services._on_procedure_line(text, pos, pathology))


class AttributiveCompoundReleaseTests(SimpleTestCase):
    """L3 (P1 rule 2 at the own-passage release): an attributive act compound presupposes an earlier act and states
    none today, so it never releases the code's act_missing hold; an act stated today still does."""

    def test_an_attributive_compound_never_stands_for_today_s_act(self):
        for line in (BARRETT, 'Follow-up of a biopsy-confirmed gastric adenoma was performed.'):
            with self.subTest(line):
                text = EGD + line + '\n'
                self.assertEqual(acts(inventory(text), 'gi.egd'), [])
                self.assertEqual(proposal(run(text, [sel('43239', span(text, line))]), '43239').status,
                                 'needs_clarification')

    def test_a_stated_biopsy_beside_it_still_reads(self):
        stated = 'Cold forceps biopsies were taken from the distal esophagus.'
        text = EGD + BARRETT + '\n' + stated + '\n'
        self.assertEqual(proposal(run(text, [sel('43239', span(text, stated))]), '43239').status, 'ready')

    def test_the_release_test_itself(self):
        # _states_unread_act over a passage: the attributive compound names no act; a predicate does
        text = EGD + BARRETT + '\nThe distal esophagus was biopsied.\n'
        self.assertEqual([k for k, _, _ in gi_services._acts_in(text, text.index(BARRETT), text.index(BARRETT)
                                                                + len(BARRETT))], [])
        stated = 'The distal esophagus was biopsied.'
        self.assertEqual([k for k, _, _ in gi_services._acts_in(text, text.index(stated), text.index(stated)
                                                                + len(stated))], ['biopsy'])
