"""Reader-bind round 2 (2026-11-04): the refutation round's reproduced regressions of the release-side reader rules,
repaired so each fails closed (declared before code in tests/fixtures/gi4/declarations/cux-r2-bind.json).

- L1 (the lead's 'Label: <service>' part, cux-lead.json): a labelled line in a plan, a later procedure, a list of
  today's procedures or a numbered procedure field opens no part (F01, F03); the heading line reads as installed (F01's
  cancelled note); a note label the heading reader refuses still ends the running part's claim on the text after it
  (R10, R8 D7's fail-closed half); an act beyond a sigmoidoscope's reach is the part's the note interrupted (R07).
- P1 rule 1: a label or specimen never moves an act to another service's lesion (F04 a, b), never resolves over a
  site-less second definition (F04 c), never binds a clause naming another site (F06).
- P1 rule 2: a compound in a field label or a negated predicate is no attributive compound when it denies (F05).
- P1 rule 4: a combined report's dated or history-worded denial is never dropped (F02).

Every document is synthetic. No database, nothing sent.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import services
from studio.providers import corti
from tests.test_cux_bind import (HEAD, MARA, READY, acts, conflicts, held, inventory, outcomes, run, service)
from tests.test_cux_hold import row, state

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations' / 'cux-r2-bind.json')
                         .read_text(encoding='utf-8'))
DECLARED = {(name, code): (before, after) for name, code, before, after in DECLARATION['battery']}
HELD = 'selected/needs_clarification'
# The new rows' codes the declaration does not move, measured on c47d71a34 with the rows added (none may move).
UNMOVED = {
    ('R8 R2 R07a cecal snare after a separate note', '45378'): HELD,
    ('R8 R2 R07v4 cecal snare inside the separate note', '45378'): HELD,
    ('R8 R2 R07v3 control, sigmoid snare inside the separate note', '45378'): HELD,
    ('R8 R2 R07v3 control, sigmoid snare inside the separate note', '45385'): HELD,
    ('R8 R2 R07v3 control, sigmoid snare inside the separate note', '45338'): 'selected/ready',
    ('R8 R2 R10a separate note on the service date', '45385'): 'selected/ready',
    ('R8 R2 R10b separate same-day note', '45385'): 'selected/ready',
    ('R8 R2 R10c separate note for rectal bleeding', '45385'): 'selected/ready',
    ('R8 R2 R10h7 addendum by another physician', '45385'): 'selected/ready',
    ('R8 R2 F02 control, undated combined denial', '43239'): HELD,
    ('R8 R2 F03a numbered procedure lines', '43239'): HELD,
    ('R8 R2 F03b numbered procedure lines, dashes', '43239'): HELD,
    ('R8 R2 F04c label reused under the upper endoscopy', '43251'): HELD,
    ('R8 R2 F05 control, an attributive compound', '45385'): 'selected/ready',
    ('R8 R2 F06 control, a denial on a label alone', '45385'): 'selected/ready',
}

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
COLON = (B + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
         'Procedure: Colonoscopy\n' + CECUM + '\n')
CO_SNARE = 'A 7 mm polyp in the ascending colon was removed with a cold snare.'
FS_BIOPSY = 'Biopsies of the rectal mucosa were taken with cold forceps.'
NOTE = 'Separate note: Flexible sigmoidoscopy (fictional), 2026-10-14'
SCOPE_60 = 'The flexible sigmoidoscope was advanced to 60 cm in the descending colon.'


def colon_then(heading, *lines):
    """R8's H1 shape: a colonoscopy with its snare, then ``heading`` over a flexible sigmoidoscopy and its biopsy."""
    return COLON + CO_SNARE + '\n\n' + heading + '\n' + SCOPE_60 + '\n' + ''.join(line + '\n' for line in lines)


class R2RowsTests(SimpleTestCase):
    """Every round-2 battery row ends where the declaration says, with no violation; its other codes keep their base
    state (measured on c47d71a34)."""

    def test_the_rows(self):
        names = DECLARATION['battery_rows_added']
        # the reader-em rows (R8 R2 EM, cux-r2-em.json) and the variants' (R8 R2 V, cux-r2-variants.json) are their own
        others = ('R8 R2 EM ', 'R8 R2 V ')
        self.assertEqual(sorted(names), sorted(n for n in battery.CASES if n.startswith('R8 R2 ') and not n.startswith(others)))
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    expected = DECLARED[(name, code)][1] if (name, code) in DECLARED else UNMOVED[(name, code)]
                    self.assertEqual(state(result, code), expected)
                    self.assertEqual(result['proposals'][code]['violations'], [])


# --- L1: the 'Label: <service>' part ------------------------------------------------------------------------------

LEFT = (HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum. A 12 mm sessile polyp was seen in the '
        'sigmoid colon and was left in place because the patient takes clopidogrel.\n')
LEFT_Q = [('45385', 'A 12 mm sessile polyp was seen in the sigmoid colon')]


class PlanAndLaterProcedureLabelTests(SimpleTestCase):
    """L1a, L1c (F01): a labelled line in a plan, or one naming a later procedure, is no report of today's."""

    def test_a_labelled_line_in_a_plan_or_for_a_later_procedure_is_no_report_of_today(self):
        for tail in ('Plan:\nSecond procedure: Colonoscopy with cold snare polypectomy\n',
                     'Recommendations:\nFollow-on procedure: colonoscopy with cold snare polypectomy\n',
                     'Subsequent procedure: colonoscopy with cold snare polypectomy\n',
                     'Impression and Recommendations:\nSecond procedure: Colonoscopy with cold snare polypectomy\n',
                     'Plan:\nSeparate note: Colonoscopy with cold snare polypectomy\n',
                     'Plan:\nAdditional procedure: Colonoscopy with hot snare polypectomy\n'):
            with self.subTest(tail):
                text = LEFT + tail
                self.assertEqual(acts(inventory(text), 'gi.colonoscopy', 'snare', 'performed'), [])
                self.assertEqual(outcomes(run(text, LEFT_Q))['45385'], held('performed_status'))

    def test_the_text_after_a_labelled_line_in_a_plan_or_a_history_stays_that_plan_s_or_history_s(self):
        # L1a alone decides these (L1b already reads the label line as installed): the line after it is the plan's or
        # the history's, never a report of today's colonoscopy
        for tail in ('Plan:\nSecond procedure: Colonoscopy with cold snare polypectomy\nCold snare polypectomy of the 12 '
                     'mm sigmoid polyp.\n',
                     'Plan:\nSeparate note: Colonoscopy\nThe 12 mm sigmoid polyp was removed with a cold snare.\n',
                     'Impression and Recommendations:\nSecond procedure: Colonoscopy\nThe 12 mm sigmoid polyp was removed '
                     'with a cold snare.\n',
                     'History:\nSeparate note: Colonoscopy\nA 12 mm sigmoid polyp was removed with a cold snare.\n'):
            with self.subTest(tail):
                self.assertEqual(outcomes(run(LEFT + tail, LEFT_Q))['45385'], held('performed_status'))

    def test_the_heading_line_reads_as_installed(self):
        # F01's second effect: the label line gave the cancelled colonoscopy a performed title reading
        text = (HEAD + 'EGD report\nThe gastroscope was advanced to the second part of the duodenum. Cold forceps '
                'biopsies were taken from the gastric antrum.\nSeparate note: Colonoscopy\nThe colonoscopy was cancelled '
                'because of inadequate preparation.\n')
        self.assertEqual(service(inventory(text), 'gi.colonoscopy').status, 'cancelled')
        self.assertEqual(outcomes(run(text, [('45378', 'Separate note: Colonoscopy')]))['45378'][:2],
                         ('excluded', 'excluded'))
        self.assertFalse([p for p in services.parts(text) if p.title is not None and p.title.text.startswith('Separate')])


LISTED = ('Findings:\nThe gastroscope was advanced to the second part of the duodenum. Biopsies were taken with cold '
          'forceps. A clip was placed at the biopsy site.\nThe colonoscope was advanced to the cecum. The colon was '
          'normal.\n')
LISTED_Q = [('43239', 'Biopsies were taken with cold forceps.'), ('45380', 'Biopsies were taken with cold forceps.')]


class ProcedureListTests(SimpleTestCase):
    """L1c (F03): numbered procedure lines and a list of labelled lines are fields of today's report, never parts."""

    def test_numbered_procedure_lines_open_no_part(self):
        for head in ('Upper endoscopy and colonoscopy report\nProcedure 1: EGD\nProcedure 2: Colonoscopy\n',
                     'EGD and colonoscopy report\nProcedure 1 - EGD\nProcedure 2 - Colonoscopy\n',
                     'Upper endoscopy and colonoscopy report\nProcedure 2: Colonoscopy\nProcedure 1: EGD\n',
                     'Upper endoscopy and colonoscopy report\nProcedure 2: Colonoscopy\n',
                     'Upper endoscopy and colonoscopy report\nNote 1: EGD\nNote 2: Colonoscopy\n',
                     'Upper endoscopy and colonoscopy report\nPart 1 - EGD\nPart 2 - Colonoscopy\n'):
            with self.subTest(head):
                text = HEAD + head + LISTED
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'biopsy'), [])
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'clip'), [])
                self.assertEqual(outcomes(run(text, LISTED_Q))['45380'][:2], ('selected', 'needs_clarification'))

    def test_a_list_of_note_labels_over_findings_naming_no_instrument(self):
        # the list guard alone decides these (no instrument tells another examination, so L1f does not apply)
        findings = ('Findings:\nBiopsies were taken with cold forceps. A clip was placed at the biopsy site.\nThe colon '
                    'was normal.\n')
        for head in ('Upper endoscopy and colonoscopy report\nNote 1: EGD\nNote 2: Colonoscopy\n',
                     'Upper endoscopy and colonoscopy report\nPart 1 - EGD\nPart 2 - Colonoscopy\n'):
            with self.subTest(head):
                text = HEAD + head + findings
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'biopsy'), [])  # (the upper endoscopy, the one service
                # read performed, takes it as installed)
                self.assertIn('performed_status', outcomes(run(text, LISTED_Q))['45380'][2])

    def test_the_helper_refuses_a_numbered_procedure_field(self):
        for line in ('Procedure 2: Colonoscopy', 'Procedure 1 - EGD', 'Subsequent procedure: colonoscopy',
                     'Follow-on procedure: colonoscopy'):
            with self.subTest(line):
                self.assertIsNone(services.LABELLED_NOTE.match(line))
        for line in ('Note 2: Flexible sigmoidoscopy (fictional)', 'Separate same-day note: Flexible sigmoidoscopy',
                     'Second procedure: Flexible sigmoidoscopy', 'Addendum - flexible sigmoidoscopy'):
            with self.subTest(line):
                self.assertIsNotNone(services.LABELLED_NOTE.match(line))


class RefusedNoteLabelTests(SimpleTestCase):
    """L1d (R10, R8 D7's fail-closed half): a note label naming another service that the heading reader refuses still
    ends the running part's claim on the text after it - its biopsy is never the colonoscopy's."""

    CODES = [('45385', CO_SNARE), ('45380', FS_BIOPSY)]

    def test_the_note_s_biopsy_is_not_the_colonoscopy_s(self):
        for heading in ('Separate note: Flexible sigmoidoscopy (fictional) on 2026-10-14',
                        'Separate same-day note: Flexible sigmoidoscopy (fictional), 2026-10-14',
                        'Separate note: Flexible sigmoidoscopy for rectal bleeding (fictional), 2026-10-14',
                        'Addendum - flexible sigmoidoscopy performed the same day by Dr. Vale',
                        'Separate note: Colonoscopy and flexible sigmoidoscopy on 2026-10-14'):
            with self.subTest(heading):
                text = colon_then(heading, FS_BIOPSY)
                inv = inventory(text)
                self.assertEqual([a.kind for a in acts(inv, 'gi.colonoscopy')], ['snare'])
                found = outcomes(run(text, self.CODES))
                self.assertEqual(found['45385'], READY)
                self.assertEqual(found['45380'][:2], ('selected', 'needs_clarification'))

    def test_controls_a_note_of_another_time_reads_as_installed(self):
        # the note names no flexible sigmoidoscopy of today, so the colonoscopy is the one procedure the document
        # documents and the biopsy is read as installed (its own hold keeps 45380 from READY on both trees)
        for heading in ('Separate note: history of flexible sigmoidoscopy',
                        'Second procedure: Flexible sigmoidoscopy (2023-05-02)'):
            with self.subTest(heading):
                text = colon_then(heading, FS_BIOPSY)
                self.assertEqual(outcomes(run(text, self.CODES))['45380'], held('performed_status'))

    def test_twin_a_denial_after_a_refused_label_still_pairs(self):
        # the unplaced part keeps rule 4's extension: a site-less denial is set beside every service documenting the act
        text = (COLON + 'A 3 mm polyp in the ascending colon was removed with cold forceps.\n\nSeparate note: Flexible '
                'sigmoidoscopy (fictional) on 2026-10-14\n' + SCOPE_60 + '\nNo biopsies were taken.\n')
        self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'biopsy'))
        result = run(text, [('45380', 'A 3 mm polyp in the ascending colon was removed with cold forceps.')])
        self.assertEqual(outcomes(result)['45380'], held('conflict:biopsy'))

    def test_controls_a_label_of_the_running_service_or_of_none_changes_nothing(self):
        for heading in ('Addendum - colonoscopy findings reviewed with the patient', 'Addendum - pathology pending'):
            with self.subTest(heading):
                text = COLON + CO_SNARE + '\n\n' + heading + '\nA 4 mm polyp in the sigmoid colon was removed with cold ' \
                                                             'forceps.\n'
                self.assertEqual(sorted(a.kind for a in acts(inventory(text), 'gi.colonoscopy')), ['biopsy', 'snare'])


class AnotherExaminationInTheNoteTests(SimpleTestCase):
    """L1f (self-refutation of L1c): a labelled part ends where its text turns to another examination, told by that
    examination's instrument ("The gastroscope was advanced ...") - one labelled line over a combined report's shared
    findings never makes the upper endoscopy's biopsy and clip the colonoscopy's."""

    def test_one_labelled_line_over_shared_findings(self):
        for label in ('Part 2: Colonoscopy', 'Note 2: Colonoscopy', 'Second procedure: Colonoscopy',
                      'Separate note: Colonoscopy'):
            with self.subTest(label):
                text = HEAD + 'Upper endoscopy and colonoscopy report\n' + label + '\n' + LISTED
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'biopsy'), [])
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'clip'), [])
                self.assertEqual(outcomes(run(text, LISTED_Q))['45380'][:2], ('selected', 'needs_clarification'))

    def test_the_note_s_own_instrument_and_an_act_its_sentence_places_still_read(self):
        inv = inventory(colon_then(NOTE, FS_BIOPSY))  # H1: the note's own sigmoidoscope keeps its part
        self.assertEqual([a.kind for a in acts(inv, 'gi.flex_sig')], ['biopsy'])
        text = (COLON + '\nSeparate note: EGD (fictional), 2026-10-14\nThe gastroscope was advanced to the second '
                'part of the duodenum.\nThe colonoscope was then reinserted and a 3 mm polyp was removed with cold '
                'forceps.\n')
        self.assertEqual([a.kind for a in acts(inventory(text), 'gi.colonoscopy')], ['biopsy'])
        self.assertEqual(acts(inventory(text), 'gi.egd'), [])


CECAL = 'A 5 mm polyp in the cecum was removed with a cold snare.'
SIGMOID = 'A 5 mm polyp in the sigmoid colon was removed with a cold snare.'


class SigmoidoscopeReachTests(SimpleTestCase):
    """L1e (R07): an act at a site beyond a sigmoidoscope's reach is never the separate note's; the part the note
    interrupted (the colonoscopy's report) places it, as installed. An act the sigmoidoscope reaches stays the note's."""

    def text(self, *lines, heading=NOTE):
        return (COLON + '\n' + heading + '\n' + SCOPE_60 + '\nThe rectum was normal.\n' + ''.join(line + '\n'
                                                                                                 for line in lines))

    def test_a_cecal_act_after_or_inside_the_note_is_the_colonoscopy_s(self):
        for lines in (('', CECAL), (CECAL,), ('', 'A 4 mm polyp in the transverse colon was biopsied with cold forceps.'),
                      ('Cold forceps biopsies of the ascending colon and the cecum were taken.',)):
            with self.subTest(lines):
                text = self.text(*lines)
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.flex_sig'), [])
                self.assertTrue(acts(inv, 'gi.colonoscopy', status='performed'))
        text = self.text('', CECAL)
        found = outcomes(run(text, [('45378', CECUM), ('45385', CECAL), ('45338', CECAL)]))
        self.assertEqual(found['45385'], READY)
        self.assertEqual(found['45338'][:2], ('selected', 'needs_clarification'))
        lesion = next(les for les in service(inventory(text), 'gi.colonoscopy').lesions if les.size == '5 mm')
        self.assertEqual([a.lesion for a in acts(inventory(text), 'gi.colonoscopy', 'snare')], [lesion.id])

    def test_after_a_refused_label_too(self):
        text = self.text('', CECAL, heading='Separate note: Flexible sigmoidoscopy (fictional) on 2026-10-14')
        self.assertEqual(outcomes(run(text, [('45385', CECAL)]))['45385'], READY)

    def test_control_an_act_the_sigmoidoscope_reaches_stays_the_note_s(self):
        text = self.text(SIGMOID)
        inv = inventory(text)
        self.assertEqual([a.kind for a in acts(inv, 'gi.flex_sig')], ['snare'])
        found = outcomes(run(text, [('45378', CECUM), ('45385', SIGMOID), ('45338', SIGMOID)]))
        self.assertEqual(found['45338'], READY)
        self.assertEqual(found['45385'][:2], ('selected', 'needs_clarification'))

    def test_control_h1_is_unchanged(self):
        text = colon_then(NOTE, FS_BIOPSY)
        inv = inventory(text)
        self.assertEqual([a.kind for a in acts(inv, 'gi.colonoscopy')], ['snare'])
        self.assertEqual([a.kind for a in acts(inv, 'gi.flex_sig')], ['biopsy'])


# --- P1 rule 1: lesion labels ---------------------------------------------------------------------------------------

COL_EGD = HEAD + 'Colonoscopy and EGD report\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\n'
UPPER = 'UPPER ENDOSCOPY\nThe gastroscope was advanced to the second part of the duodenum. '


class LabelNeverMovesAnActTests(SimpleTestCase):
    """R1a, R1b (F04): a label or specimen named in an upper endoscopy's clause never moves its act to a colon lesion, and
    a label redefined with no site resolves to nothing."""

    def test_a_label_or_specimen_named_in_passing(self):
        for colon, upper, quote in (
                ('COL-1 - sigmoid colon: an 8 mm polyp was removed with a cold snare.\n',
                 'The antrum showed patchy erythema. Biopsies were then taken with the same cold forceps used to retrieve '
                 'COL-1.\n', 'Biopsies were then taken with the same cold forceps used to retrieve COL-1.'),
                ('A 6 mm polyp in the sigmoid colon was removed with a cold snare and sent as specimen 1.\n',
                 'The stomach showed patchy erythema. Biopsies were obtained with cold forceps (specimen 1).\n',
                 'Biopsies were obtained with cold forceps (specimen 1).')):
            with self.subTest(quote):
                text = COL_EGD + colon + UPPER + upper
                inv = inventory(text)
                self.assertEqual([a.kind for a in acts(inv, 'gi.egd')], ['biopsy'])
                self.assertEqual(acts(inv, 'gi.colonoscopy', 'biopsy'), [])
                found = outcomes(run(text, [('43239', quote), ('45380', quote)]))
                self.assertEqual(found['43239'], READY)
                self.assertEqual(found['45380'][:2], ('selected', 'needs_clarification'))

    def test_a_label_redefined_without_a_site_resolves_to_nothing(self):
        text = (COL_EGD + 'P1 - sigmoid colon: a 4 mm polyp was removed with cold forceps.\n' + UPPER
                + '\nStomach:\nP1: a 9 mm sessile polyp. P1 was removed with a hot snare.\n')
        self.assertNotIn('P1', services._unique_labels(services._label_definitions(text)))
        self.assertEqual(acts(inventory(text), 'gi.colonoscopy', 'snare'), [])
        quote = 'P1 was removed with a hot snare.'
        self.assertEqual(outcomes(run(text, [('43251', quote), ('45385', quote)]))['45385'][:2],
                         ('selected', 'needs_clarification'))

    def test_controls_a_restated_label_with_its_site_still_resolves(self):
        defs = services._label_definitions('COL-1 - ascending colon: a 2 mm polyp\nC\nCOL-1: ascending colon\n')
        self.assertIn('COL-1', services._unique_labels(defs))


LABELS = (HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\nCOL-1 - ascending colon: a 2 mm polyp was '
          'removed with cold forceps.\nCOL-2 - sigmoid colon: an 8 mm polyp was removed with a cold snare.\n')
LABELS_SNARE = [('45385', 'an 8 mm polyp was removed with a cold snare.')]


class LabelAgainstItsClauseSiteTests(SimpleTestCase):
    """R1c (F06): a denial naming a label and another segment of the tract is read as installed - the genuine
    contradiction at the segment it names is kept."""

    def test_a_denial_naming_another_segment_is_not_bound_to_the_label(self):
        for denial in ('No snare was used on COL-1 in the sigmoid colon.',
                       'In the sigmoid colon no snare was used, as for COL-1.',
                       'No snare was used on COL-1 (sigmoid colon).',
                       'No snare was used at the sigmoid colon site of COL-1.',
                       'Sigmoid colon (COL-1): no snare was used.'):
            with self.subTest(denial):
                text = LABELS + denial + '\n'
                self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'snare'))
                self.assertEqual(outcomes(run(text, LABELS_SNARE))['45385'], held('conflict:snare'))
        text = LABELS + 'No forceps were used on COL-2 in the ascending colon.\n'
        self.assertEqual(outcomes(run(text, [('45380', 'a 2 mm polyp was removed with cold forceps.')]))['45380'],
                         held('conflict:biopsy'))

    def test_controls_the_label_alone_or_with_its_own_site_still_binds(self):
        for denial in ('No snare was used on COL-1.', 'No snare was used on COL-1 in the ascending colon.',
                       'No snare was used on COL-1 in the colon.'):
            with self.subTest(denial):
                text = LABELS + denial + '\n'
                inv = inventory(text)
                one = next(les for les in service(inv, 'gi.colonoscopy').lesions if les.size == '2 mm')
                self.assertEqual([a.lesion for a in acts(inv, kind='snare', status='negated')], [one.id])
                self.assertEqual(outcomes(run(text, LABELS_SNARE))['45385'], READY)


# --- P1 rule 2: attributive compounds ------------------------------------------------------------------------------

SNARED = (HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum. A 7 mm polyp in the sigmoid colon was '
          'removed with a cold snare.\n')
SNARED_Q = [('45385', 'A 7 mm polyp in the sigmoid colon was removed with a cold snare.')]


class DoubtfulCompoundTests(SimpleTestCase):
    """R2a (F05): a compound in a field label, a coordinated or negated predicate, or at a clause's end is no
    attributive compound when its clause denies the act - the same-lesion conflict is kept."""

    def test_a_denying_field_or_predicate_compound_keeps_the_conflict(self):
        for denial in ('Polyp 1 - sigmoid colon, 7 mm\nSnare-resected: No\nForceps-removed: Yes',
                       'Hot snare-resected: Not done', 'Cold snare-resected: No', 'Snare-resected: No',
                       'Snare-resected:\nNo', 'The sigmoid polyp was neither snare-resected nor retrieved.',
                       'The sigmoid polyp was not, as planned, snare-resected.'):
            with self.subTest(denial):
                text = SNARED + denial + '\n'
                self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'snare'))
                self.assertEqual(outcomes(run(text, SNARED_Q))['45385'], held('conflict:snare'))

    def test_the_mention_list_of_every_other_reader_is_unchanged(self):
        for line in ('Snare-resected: No', 'was neither snare-resected nor retrieved'):
            with self.subTest(line):
                self.assertEqual(services._acts_in(line, 0, len(line)), [])
                found = []
                services._acts_in(line, 0, len(line), doubtful=found)
                self.assertEqual([k for k, _, _ in found], ['snare'])
        for line in ('the snare-treated sigmoid lesion', 'Biopsy-proven Barrett esophagus.', 'two snare-resected polyps'):
            with self.subTest(line):
                found = []
                self.assertEqual(services._acts_in(line, 0, len(line), doubtful=found), [])
                self.assertEqual(found, [])

    def test_controls_an_attributive_compound_and_a_predicate_compound_read_as_before(self):
        self.assertEqual(outcomes(run(SNARED + 'The snare-resected sigmoid polyp was not retrieved.\n', SNARED_Q))['45385'],
                         READY)
        self.assertEqual(outcomes(run(SNARED + 'The sigmoid polyp was not snare-resected.\n', SNARED_Q))['45385'],
                         held('conflict:snare'))

    def test_control_an_affirming_doubtful_compound_stands_for_no_act(self):
        # never a release: L3's own-passage release and the inventory read no act from it, as on this base
        egd = (HEAD + 'Upper endoscopy report\nProcedure: EGD\nThe gastroscope was advanced to the second portion of the '
               'duodenum.\nBarrett esophagus, 3 cm segment.\nBiopsy-proven: Yes\n')
        self.assertEqual(acts(inventory(egd), 'gi.egd', 'biopsy'), [])
        self.assertEqual(outcomes(run(egd, [('43239', 'Biopsy-proven: Yes')]))['43239'][:2],
                         ('selected', 'needs_clarification'))


# --- P1 rule 4: a combined report's denials --------------------------------------------------------------------------

COMBINED = (HEAD + 'EGD and colonoscopy report\nThe gastroscope was advanced to the second part of the duodenum. Cold '
            'forceps biopsies were taken from the gastric antrum. The colonoscope was advanced to the cecum. A 6 mm polyp '
            'in the transverse colon was removed with a cold snare.\n')


class CombinedDenialTests(SimpleTestCase):
    """R4a (F02): a combined report's site-less denial is never dropped for a date or a history word in its clause."""

    def test_a_dated_or_history_worded_denial_keeps_the_conflict(self):
        for denial in ('No biopsies were taken on 2026-11-03.', 'No biopsies were taken on 11/03/2026.',
                       'On 2026-11-03, no biopsies were taken.', 'No biopsies were taken during the procedure on '
                       '2026-11-03.', 'No biopsies were taken, as previously documented.',
                       'No biopsies were taken on 2026-10-01.'):
            with self.subTest(denial):
                text = COMBINED + denial + '\n'
                self.assertTrue(conflicts(inventory(text), 'gi.egd', 'biopsy'))
                found = outcomes(run(text, [('43239', 'Cold forceps biopsies were taken from the gastric antrum.')]))
                self.assertEqual(found['43239'], held('conflict:biopsy'))

    def test_mara_with_the_service_date_on_its_denial(self):
        text = (MARA / 'rev1.txt').read_text(encoding='utf-8')
        readme = json.loads((MARA / 'README.json').read_text(encoding='utf-8'))
        body = (MARA / 'corti-response.json').read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), readme['corti_response_sha256'])
        old, new = 'No biopsy forceps were used on COL-2.', 'No biopsies were taken on 2026-11-03.'
        self.assertEqual((len(old), text.count(old)), (len(new), 1))  # same length: the response's quotes still locate
        text = text.replace(old, new)
        request = corti.build_coding_request('corti', corti.ADAPTER_VERSION, text, date(2026, 11, 3),
                                             corti.DEFAULT_MAX_REQUEST_BYTES)
        found = outcomes(run(text, normalized=corti.normalize_coding_response('corti', request, body)))
        self.assertEqual(found['43239'], held('conflict:biopsy'))
        self.assertEqual(found['45380'], held('conflict:biopsy'))
