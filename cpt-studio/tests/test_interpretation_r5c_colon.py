"""DECISIONS D139 (the Gemini migration's round 5c: the round-5b review of D124, review_colon.json problems 0-4 and 9),
SYNTHETIC, each built from its source's own input. Nothing is sent.
- A role's entry heading is read as the installed release's services.ROLE_HEADINGS reads it: an entry phrase opening its
  line and followed by at most 60 characters of anything heads an entry ('Pathology Report: Final', 'Nursing note -
  recovery'); 'checklist' is an entry word and 'Procedure checklist' an entry form; so the entry's own heading line is
  never read as the next heading (problems 0-2).
- The next heading's shape is services.GENERIC_HEADING's, which allows no apostrophe (problem 4).
- Each role label the D124 entry lists holds its act: 'RN:', 'Pathology:', 'Anesthesia:', 'Anesthesia record',
  'Radiology report' (problem 3).
- A code D124 holds lists its act in its support, as engine._another_roles_hold's held match does (problem 9).
The installed release's outputs on these inputs (c2e53f8e, engine.assess as tests/test_harness_engine.py drives it, on
the same texts and codes) are in each test's docstring. 46e461e7f READYs every input the first two classes hold and
lists no act for a held code; it already holds the labels' inputs, which no round-5b pin read. Each test asserts in
independent subtests, so a regression shows every one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events
from tests.test_interpretation_events import asked, check, inventory, proposal, run
from tests.test_interpretation_r5_colon import (CECUM_DONE, NURSE_BIOPSY, NURSE_CLAUSE, NURSE_SNARE, PATH_BIOPSY,
                                                SNARE_LINE, above_the_act, after_the_entry, cexam, creach, csnare,
                                                head, items, lesion, nursing_question, overlay_status,
                                                t02_nursing_snare, t03_pathology_biopsy, u05_nursing_biopsy)
from tests.test_interpretation_identity import a, act, tg

TOLERATED = 'Nurse: Patient tolerated the procedure well.'
NURSING_HEADINGS = ('Nursing note - recovery', 'Nursing note, recovery room', 'Nursing note by Jo Rowe, RN',
                    'Nursing note.', 'Nursing checklist', 'Procedure checklist', 'NURSING NOTE (Jo Rowe, RN) 08:30')
PATHOLOGY_HEADINGS = ('Pathology report - final', 'Pathology Report: Final', 'Pathology report dated 11/12/2026',
                      'Pathology report, final diagnosis', 'Surgical pathology report - received 11/12/2026')
# what follows 'Pathology report' on its line, in the line's own characters
TAIL_60 = ' - received 11/12/2026 from the regional laboratory, finalxx'
TAIL_61 = TAIL_60 + 'y'
TAIL_SHARP = ' - received from the Weißbach Straße lab on 11/12/2026 final'  # 60 characters; case folded, 62


def under_the_heading(heading: str, between=(TOLERATED,)) -> tuple:
    """The review's first shape (after_the_entry): the role's heading, a nursing line, then the physician-worded snare
    line, which carries no label of its own."""
    return after_the_entry(list(between), SNARE_LINE, heading=heading)


def clause_under(heading: str) -> tuple:
    """The review's second shape: T02 with only the nursing line's clause (no 'Nurse:' label) directly under
    ``heading``, so the heading alone places the snare in the entry."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': heading, 'P6': NURSE_CLAUSE}
    inv, text = inventory(lines, events=[cexam(), csnare('E2', 'P6', 'L1', 'sigmoid_colon',
                                                         '6 mm polyp in the sigmoid colon')],
                          lesions=[lesion('L1', '6 mm polyp', 'P6', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                          reach=[creach()])
    return inv, text, [('45385', NURSE_CLAUSE)]


def t03_under(heading: str) -> tuple:
    """The audit's T03 with ``heading`` in place of 'Pathology report': the biopsy line carries no label."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': heading, 'P6': PATH_BIOPSY}
    biopsy = act('E2', 'P6', 'biopsy', 'biopsy', status_words='cold forceps biopsy',
                 technique=a('cold_forceps', 'cold forceps', ['P6']),
                 target=tg('L1', 'sigmoid_colon', 'Sigmoid colon polyp', ['P6']))
    inv, text = inventory(lines, events=[cexam(), biopsy],
                          lesions=[lesion('L1', 'Sigmoid colon polyp', 'P6', 'sigmoid_colon', 'Sigmoid colon')],
                          reach=[creach()])
    return inv, text, [('45380', PATH_BIOPSY)]


class Held(SimpleTestCase):
    def held(self, result, code: str, question: str, **where) -> None:
        """``code`` held by D124 ([performed_status], ``question`` word for word, reason another_role), still held by
        the read-time overlay, its act listed nowhere as uncovered."""
        p = proposal(result, code)
        with self.subTest(part='assess', **where):
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']))
            self.assertEqual(p.clarifications[0].question, question)
            self.assertEqual((p.support['state'], p.support['reason']), ('uncertain', events.ANOTHER_ROLE))
            self.assertEqual(check(p, 'events.match').status, 'warn')
        with self.subTest(part='overlay', **where):
            overlay_status(self, result, code, 'needs_clarification')
        with self.subTest(part='coverage', **where):
            self.assertEqual([entry for entry in items(result) if entry[2] not in ('', 'examination')], [])

    def ready(self, result, code: str, **where) -> None:
        p = proposal(result, code)
        with self.subTest(**where):
            self.assertEqual((p.status, asked(p), p.support['reason']), ('ready', [], events.SUPPORTED))


class ARoleHeadingWithTrailingWordsHeadsItsEntry(Held):
    """D139 (1), review_colon.json problems 0-2. 46e461e7f READYs every input here; c2e53f8e holds every one
    [performed_status] but the 61-character control, which is READY on all three engines."""

    def test_d139_a_nursing_heading_with_trailing_words_heads_its_entry(self):
        """Problem 0's seven nursing headings, each in both shapes (a nursing line then the snare line; the snare
        clause directly under the heading). c2e53f8e: all fourteen needs_clarification [performed_status], its
        another-role question word for word as asserted. 46e461e7f: all fourteen READY (supported)."""
        for heading in NURSING_HEADINGS:
            for shape, build, passage in (('after a nursing line', under_the_heading, SNARE_LINE),
                                          ('the clause under it', clause_under, NURSE_CLAUSE)):
                inv, text, codes = build(heading)
                self.held(run(inv, text, codes), '45385', nursing_question('snare removal', passage),
                          heading=heading, shape=shape)

    def test_d139_a_pathology_heading_with_trailing_words_heads_its_entry(self):
        """Problem 0's five pathology headings over T03's biopsy line. c2e53f8e: all five needs_clarification
        [performed_status], act_missing ('CPT Studio could not find a forceps biopsy in the documented colonoscopy.
        ...', its reader reads no biopsy act there, as on T03 itself). 46e461e7f: all five READY."""
        for heading in PATHOLOGY_HEADINGS:
            inv, text, codes = t03_under(heading)
            self.held(run(inv, text, codes), '45380', nursing_question('forceps biopsy', PATH_BIOPSY, 'pathology'),
                      heading=heading)

    def test_d139_checklist_is_an_entry_word_and_procedure_checklist_an_entry_form(self):
        """'Nursing checklist' (the entry word 'checklist') and 'Procedure checklist' (an entry form with no role
        name: services.ROLE_HEADINGS' own procedure\\s+checklist), in both shapes, each with nothing after it - so the
        60-character reading alone does not hold them. c2e53f8e: all four held, its another-role question.
        46e461e7f: all four READY."""
        for heading in ('Nursing checklist', 'Procedure checklist'):
            for shape, build, passage in (('after a nursing line', under_the_heading, SNARE_LINE),
                                          ('the clause under it', clause_under, NURSE_CLAUSE)):
                inv, text, codes = build(heading)
                self.held(run(inv, text, codes), '45385', nursing_question('snare removal', passage),
                          heading=heading, shape=shape)

    def test_d139_at_most_60_characters_follow_the_entry_phrase(self):
        """'Pathology report' followed by 60 characters heads the entry (held); by 61 it heads nothing, is too long to
        be the next heading either, and the snare clause under it is READY - as c2e53f8e reads both (its
        [^\\n]{0,60}$ after the entry word): held [performed_status] with its another-role question, and READY."""
        inv, text, codes = clause_under('Pathology report' + TAIL_60)
        self.assertEqual(len(TAIL_60), 60)
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', NURSE_CLAUSE, 'pathology'),
                  tail=60)
        inv, text, codes = clause_under('Pathology report' + TAIL_61)
        self.ready(run(inv, text, codes), '45385', tail=61)

    def test_d139_the_tail_is_counted_in_the_lines_own_characters(self):
        """60 characters after 'Pathology report', two of them 'ß', which case folding makes 'ss' (62 folded): the
        line's own count is what c2e53f8e's ROLE_HEADINGS reads, so it still heads the entry. c2e53f8e: held
        [performed_status], its another-role question. Without the allowance: READY."""
        self.assertEqual((len(TAIL_SHARP), len(TAIL_SHARP.casefold())), (60, 62))
        inv, text, codes = clause_under('Pathology report' + TAIL_SHARP)
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', NURSE_CLAUSE, 'pathology'))

    def test_d139_an_apostrophe_after_the_entry_word_does_not_join_it(self):
        """ROLE_HEADINGS ends an entry phrase at its \\b: "Nursing note's addendum" and "Pathology report’s addendum"
        (a curly apostrophe) head entries there. c2e53f8e: both held [performed_status], its another-role question.
        D124's whole label refused them (an apostrophe joined the word): READY."""
        for heading, entry, build, passage in (("Nursing note's addendum", 'nursing', clause_under, NURSE_CLAUSE),
                                               ('Pathology report’s addendum', 'pathology',
                                                lambda h: under_the_heading(h, ()), SNARE_LINE)):
            inv, text, codes = build(heading)
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', passage, entry),
                      heading=heading)


class ALineWithAnApostropheEndsNoEntry(Held):
    """D139 (2), review_colon.json problem 4: the next heading is GENERIC_HEADING's shape, [A-Za-z0-9 /&,()\\-] - no
    apostrophe."""

    def test_d139_a_line_with_an_apostrophe_is_not_the_next_heading(self):
        """'Nursing note' / "Patient's vital signs stable throughout" (straight, then curly) / the snare line: the
        line is no heading, so the snare is still the nursing note's. c2e53f8e: held [performed_status], its
        another-role question (both). 46e461e7f: READY (the line ended the entry). Without the apostrophe the line is a
        heading and ends the entry: READY on both engines (D124's residual 4)."""
        for line in ("Patient's vital signs stable throughout", 'Patient’s vital signs stable throughout'):
            inv, text, codes = under_the_heading('Nursing note', [line])
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', SNARE_LINE), line=line)
        inv, text, codes = under_the_heading('Nursing note', ['Patient vital signs stable throughout'])
        self.ready(run(inv, text, codes), '45385', line='no apostrophe')


class EachRoleLabelHoldsItsAct(Held):
    """D139 (3), review_colon.json problem 3: the labels D124 lists that no pin read - each pin killed by its own
    mutant (the review's MF, MG, MH and MI survived the round-5b pins). The labels stand on the act's own line under a
    'Findings' heading (the review's inputs); the entry headings stand alone above it."""

    def test_d139_the_rn_label(self):
        """'Findings' / 'RN: A 6 mm sessile polyp ... cold snare.' c2e53f8e: held [performed_status], its another-role
        question quoting the whole line, as here."""
        inv, text, codes = after_the_entry([], 'RN: ' + SNARE_LINE, heading='Findings')
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', 'RN: ' + SNARE_LINE))

    def test_d139_the_pathology_label(self):
        """'Findings' / 'Pathology: A 6 mm sessile polyp ... cold snare.' D124's own label (its spec's 'Pathology:'),
        held here. c2e53f8e: READY - its ROLE_LABEL has no pathology label, so this hold is a COST, recorded (DECISIONS
        D139, with problem 7's bare 'Pathology:' heading)."""
        inv, text, codes = after_the_entry([], 'Pathology: ' + SNARE_LINE, heading='Findings')
        self.held(run(inv, text, codes), '45385',
                  nursing_question('snare removal', 'Pathology: ' + SNARE_LINE, 'pathology'))

    def test_d139_the_anesthesia_label(self):
        """'Findings' / 'Anesthesia: A 6 mm sessile polyp ... cold snare.' c2e53f8e: held [performed_status], its
        another-role question naming the anesthesia entry."""
        inv, text, codes = after_the_entry([], 'Anesthesia: ' + SNARE_LINE, heading='Findings')
        self.held(run(inv, text, codes), '45385',
                  nursing_question('snare removal', 'Anesthesia: ' + SNARE_LINE, 'anesthesia'))

    def test_d139_the_anesthesia_record_heading(self):
        """'Anesthesia record' / the snare line. c2e53f8e: held [performed_status], its another-role question."""
        inv, text, codes = after_the_entry([], SNARE_LINE, heading='Anesthesia record')
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', SNARE_LINE, 'anesthesia'))

    def test_d139_the_radiology_report_heading(self):
        """'Radiology report' / the snare line. c2e53f8e: held [performed_status], its another-role question."""
        inv, text, codes = after_the_entry([], SNARE_LINE, heading='Radiology report')
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', SNARE_LINE, 'radiology'))


class TheHeldCodeListsItsAct(SimpleTestCase):
    """D139 (4), review_colon.json problem 9: assess._support lists the acts of a code D124 holds (its question's
    events), as engine._another_roles_hold's held match keeps its acts."""

    def test_d139_the_another_role_hold_lists_the_act(self):
        """T02 and U05. c2e53f8e: support['acts'] lists the one act - kind 'snare', 'snare removal (cold snare) of the
        6 mm polyp in the sigmoid colon' (T02); kind 'biopsy', 'forceps biopsy at the sigmoid colon' (U05, its
        reader's words). 46e461e7f: [] for both."""
        for build, code, kind, label in (
                (t02_nursing_snare, '45385', 'snare',
                 'snare removal (cold snare) of the 6 mm polyp in the sigmoid colon'),
                (u05_nursing_biopsy, '45380', 'biopsy', 'forceps biopsy (cold forceps) of the sigmoid colon polyp')):
            inv, text, codes = build()
            p = proposal(run(inv, text, codes), code)
            with self.subTest(code=code):
                self.assertEqual(p.support['reason'], events.ANOTHER_ROLE)
                self.assertEqual(p.support['acts'], [{'id': 'E2', 'kind': kind, 'label': label, 'status': 'performed'}])
                self.assertEqual(p.support['question_events'], ['E2'])


class AStaffFieldOrARoleNameHeadsNoEntry(Held):
    """D139's controls: lines that name a role or carry an entry word but open with no entry phrase head nothing, so
    the physician's snare line under them stays READY (problem 2: the staff-field controls carry no entry phrase)."""

    def test_d139_controls_no_entry_phrase_opens_the_line(self):
        """Above the physician's own snare line, no role heading anywhere: READY on this build and on c2e53f8e for all
        five ('Nursing - recovery' and 'Pathology - specimens to follow' are a role's name and a dash, which
        ROLE_HEADINGS does not read as a heading either: they are GENERIC_HEADING's next heading)."""
        for line in ('Nurse: Jo Rowe, RN (recovery note to follow)', 'Staff: Jo Rowe, RN - nursing note to follow',
                     'Nursing: Jo Rowe, RN', 'Pathology - specimens to follow', 'Nursing - recovery'):
            inv, text, codes = above_the_act(line)
            self.ready(run(inv, text, codes), '45385', line=line)

    def test_d139_controls_the_round_5b_staff_fields_stay_ready(self):
        """The round-5b controls (test_interpretation_r5_colon's eight lines), read again here: READY. c2e53f8e: READY
        but under 'Recovery instructions and management plan' (held for its own reading of that section)."""
        for line in ('Nurse: Jo Rowe, RN', 'RN: Jo Rowe', 'Nursing staff: Jo Rowe, RN; Sam Lee, LPN',
                     'Nurse present throughout the procedure.', 'Anesthesia, equipment, and quality measures',
                     'Anesthesia: Monitored anesthesia care (MAC) by the anesthesia service.',
                     'Recovery instructions and management plan',
                     '- Pathology from jars 1-3 will be sent to her and to her primary care'):
            inv, text, codes = above_the_act(line)
            self.ready(run(inv, text, codes), '45385', line=line)

    def test_d139_controls_t02_t03_and_the_clause_are_held_as_before(self):
        """The round-5b holds, unchanged: T02, U05, T03, each with its question as test_interpretation_r5_colon pins
        it."""
        for build, code, question in (
                (t02_nursing_snare, '45385', nursing_question('snare removal', NURSE_SNARE)),
                (u05_nursing_biopsy, '45380', nursing_question('forceps biopsy', NURSE_BIOPSY)),
                (t03_pathology_biopsy, '45380', nursing_question('forceps biopsy', PATH_BIOPSY, 'pathology'))):
            inv, text, codes = build()
            self.held(run(inv, text, codes), code, question, held=code)
