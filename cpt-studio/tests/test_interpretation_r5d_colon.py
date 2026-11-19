"""DECISIONS D146 (the Gemini migration's round 5d: the round-5c review of D139, round5c/review_colon2.json problems
0-4), SYNTHETIC, each built from its source's own input. Nothing is sent.
- The nursing names cover services._NURSE (c2e53f8e) in full: each optional lead with each name, so "Recovery nurse's
  note", "Recovery nurse’s notes", "Recovery nurse's record - bay 3" and "Recovery nurse's:" head a nursing entry
  (problem 0).
- role_of trims a line of ASCII whitespace only, as services' re.A patterns read lines, so a line a no-break or other
  Unicode space opens or ends is no next heading (problem 1).
- A role label may follow any characters that are not ASCII letters, digits or '_' (services.ROLE_LABEL's ^\\W* under
  re.A): '– Nurse:', '— Nurse:', '◦ Nurse:', '▪ Nurse:' (problem 2).
- A signature (services.ROLE_SIGNATURE) in the label the act's passage or line opens with, closed by a colon before the
  act's own words, makes the act that role's: 'Documented by Jo Rowe, RN:', 'Per nursing note:' (problem 3).
- A code another_role_hold holds supports nothing, so a rival it competed with is READY (problem 4: the corrected
  jobs._assess_child_events docstring states it; this pins the statement).
The installed release's outputs on these inputs (c2e53f8e, engine.assess as tests/test_harness_engine.py drives it, on
the same texts and codes) are in each test's docstring; e5628be56's are there too. Each test asserts in independent
subtests, so a regression shows every one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events, wording
from tests.test_interpretation_events import asked, exam, inventory, proposal, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r5_colon import (CECUM_DONE, SNARE_LINE, after_the_entry, cexam, creach, csnare,
                                                document, kept, lesion, nursing_question)
from tests.test_interpretation_r5c_colon import NURSE_CLAUSE, TOLERATED, Held, clause_under, under_the_heading

RECOVERY_HEADINGS = ("Recovery nurse's note", 'Recovery nurse’s notes', "Recovery nurse's record - bay 3",
                     "Recovery nurse's:")
LEADS = ('', 'Pre-procedure ', 'Preprocedure ', 'Intra-procedure ', 'Intraprocedure ', 'Post-procedure ',
         'Postprocedure ', 'Recovery ')
NAMES = ('nursing', "nurse's", 'nurses', 'nurse', 'RN')
# c2e53f8e's ROLE_HEADINGS lookahead takes these of the grid's headings (nursing|nurse|RN|recovery\s+nurse|
# pre-?procedure\s+nursing|intra-?procedure\s+nursing, then \b); the other 31 of the 41 are READY there.
INSTALLED_GRID = ('Nursing note', "Nurse's note", 'Nurse note', 'RN note', 'Pre-procedure nursing note',
                  'Preprocedure nursing note', 'Intra-procedure nursing note', 'Intraprocedure nursing note',
                  "Recovery nurse's note", 'Recovery nurse note')
TAIL = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare'
# the reaches, in the label's own characters
G60, G61 = ' ' + 'x' * 58 + ' ', ' ' + 'x' * 59 + ' '  # from the record word to 'by'
H60, H61 = 'x' * 59 + ' ', 'x' * 60 + ' '  # from 'by' and its space to the nurse word
A40, A41 = ' ' + 'x' * 38 + ' ', ' ' + 'x' * 39 + ' '  # from the anesthetist word to the record word


def asks(passage: str, entry: str = 'nursing') -> str:
    """c2e53f8e's another-role question over the snare, its passage quoted as reconcile.quote quotes it: whitespace
    runs one space, cut at 120 characters."""
    return nursing_question('snare removal', wording.quote(passage, 120)[1:-1], entry)


def grid_heading(lead: str, nurse: str) -> str:
    return (lead + nurse if lead else nurse[0].upper() + nurse[1:]) + ' note'


def on_its_line(line: str) -> tuple:
    """The review's shape for problems 2 and 3: 'Findings', then ``line`` (a label, then the physician-worded snare
    sentence), the snare citing the whole line."""
    return after_the_entry([], line, heading='Findings')


def clause_after(label: str) -> tuple:
    """``label`` and the snare sentence on one line under 'Findings', Gemini citing the sentence after the label only:
    the passage carries no label, the line it stands on does (D124's reading 2)."""
    lines = ['Colonoscopy report (fictional)', 'Procedure: Colonoscopy', CECUM_DONE, 'Findings', label + SNARE_LINE]
    passages = {'P1': CECUM_DONE, 'P2': SNARE_LINE}
    inv, text = document(lines, passages, events=[cexam('P1'), csnare('E2', 'P2', 'L1', 'sigmoid_colon',
                                                                      '6 mm sessile polyp in the sigmoid colon')],
                         lesions=[lesion('L1', '6 mm sessile polyp', 'P2', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', SNARE_LINE)]


def cited_on(line: str, passage: str) -> tuple:
    """'Findings', then ``line``, Gemini citing ``passage`` - the line, or a part of it - for the snare."""
    lines = ['Colonoscopy report (fictional)', 'Procedure: Colonoscopy', CECUM_DONE, 'Findings', line]
    passages = {'P1': CECUM_DONE, 'P2': passage}
    inv, text = document(lines, passages, events=[cexam('P1'), csnare('E2', 'P2', 'L1', 'sigmoid_colon',
                                                                      '6 mm sessile polyp in the sigmoid colon')],
                         lesions=[lesion('L1', '6 mm sessile polyp', 'P2', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', passage)]


ERCP = {'P1': 'The duodenoscope was advanced to the major papilla.', 'P2': 'The common bile duct was cannulated.',
        'P4': 'Mechanical lithotripsy of a 15 mm stone was performed.',
        'P3': 'Three stones were extracted from the bile duct with an extraction balloon.'}


def ercp_report(heading: str) -> tuple:
    """The review's problem-4 input: a full ERCP report ('ERCP report (fictional)' / 'Place of service: ...' /
    'Procedure: ERCP' / the duodenoscope, cannulation and lithotripsy lines), ``heading``, then the extraction line;
    43264 citing the extraction, 43265 the lithotripsy (one stone clearance: D55, D74)."""
    lines = {'H1': 'ERCP report (fictional)', 'H2': 'Place of service: Ambulatory surgery center',
             'H3': 'Procedure: ERCP', 'P1': ERCP['P1'], 'P2': ERCP['P2'], 'P4': ERCP['P4']}
    if heading:
        lines['P5'] = heading
    lines['P3'] = ERCP['P3']
    inv, text = inventory(lines, events=[
        exam(words='duodenoscope', procedure=a('ercp')),
        act('E2', 'P2', 'cannulation', 'cannulated', status_words='was cannulated', procedure=a('ercp'),
            target=tg('', 'common_bile_duct', 'common bile duct', ['P2'])),
        act('E3', 'P3', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
            technique=a('extraction_balloon', 'extraction balloon', ['P3'])),
        act('E4', 'P4', 'lithotripsy', 'lithotripsy', status_words='was performed', procedure=a('ercp'))])
    return inv, text, [('43264', ERCP['P3']), ('43265', ERCP['P4'])]


class TheNursingNamesAreTheInstalledReleases(Held):
    """D146 (1), review_colon2.json problem 0: services._NURSE's leads with every name."""

    def test_d146_recovery_nurses_headings_head_their_entry(self):
        """The review's four headings, each in both shapes (a nursing line then the snare line; the snare clause
        directly under the heading). c2e53f8e: all eight needs_clarification [performed_status], its another-role
        question word for word as asserted (services.ROLE_HEADINGS: recovery\\s+nurse\\b, then _NURSE's nurse['’]?s).
        e5628be56: all eight READY (supported) - "recovery nurse's" was no name, and with no apostrophe in the next
        heading's marks the line ended nothing, so role_of read past it."""
        for heading in RECOVERY_HEADINGS:
            for shape, build, passage in (('after a nursing line', under_the_heading, SNARE_LINE),
                                          ('the clause under it', clause_under, NURSE_CLAUSE)):
                inv, text, codes = build(heading)
                self.held(run(inv, text, codes), '45385', nursing_question('snare removal', passage),
                          heading=heading, shape=shape)

    def test_d146_each_lead_with_each_name_heads_a_nursing_entry(self):
        """'<lead><name> note' for each of the eight leads (none, pre-procedure, preprocedure, intra-procedure,
        intraprocedure, post-procedure, postprocedure, recovery) and the five names (nursing, nurse's, nurses, nurse,
        RN), and 'LPN note', over the snare clause: all 41 held. c2e53f8e holds the ten INSTALLED_GRID headings with
        this question and is READY on the other 31, whose lead or name its lookahead does not take ("Recovery RN
        note", "Pre-procedure nurse's note", "Nurses note", every post-procedure one, 'LPN note'): holds where it is
        READY, a cost (DECISIONS D146). e5628be56 held the thirteen whose names it had and was READY on the other 28,
        "Recovery nurse's note" (the review's) among them, so 27 of the new holds are costs."""
        headings = [grid_heading(lead, nurse) for lead in LEADS for nurse in NAMES] + ['LPN note']
        self.assertEqual(len(set(headings)), 41)
        for heading in headings:
            inv, text, codes = clause_under(heading)
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', NURSE_CLAUSE), heading=heading)


class AUnicodeSpaceIsNoHeadingsMark(Held):
    """D146 (2), review_colon2.json problem 1: services.GENERIC_HEADING (re.A) reads ASCII whitespace only."""

    def test_d146_a_line_a_unicode_space_opens_or_ends_is_no_next_heading(self):
        """'Nursing note' / 'Nurse: Patient tolerated the procedure well.' / the line / the snare line, the line
        '\\xa0Findings', 'Findings\\xa0' or 'Findings' indented with an em space: it is no heading, so the snare is
        still the nursing note's. c2e53f8e: all three needs_clarification [performed_status], its another-role
        question. e5628be56: READY (str.strip() took the Unicode space off and the line ended the entry)."""
        for line in ('\xa0Findings', 'Findings\xa0', ' Findings'):
            inv, text, codes = under_the_heading('Nursing note', [TOLERATED, line])
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', SNARE_LINE), line=line)

    def test_d146_controls_ascii_whitespace_still_trims(self):
        """The plain 'Findings', 'Findings\\r' (a CRLF line), 'Findings\\t' and '\\tFindings' end the entry: READY on
        this build, on e5628be56 and on c2e53f8e."""
        for line in ('Findings', 'Findings\r', 'Findings\t', '\tFindings'):
            inv, text, codes = under_the_heading('Nursing note', [TOLERATED, line])
            self.ready(run(inv, text, codes), '45385', line=line)


class ALabelFollowsAnyLeadingMark(Held):
    """D146 (3), review_colon2.json problem 2: services.ROLE_LABEL's ^\\W* under re.A."""

    def test_d146_a_label_after_any_leading_non_word_character(self):
        """'Findings' / '<mark> Nurse: A 6 mm sessile polyp ... cold snare.' with an en dash, an em dash, '◦' or '▪'
        (the review's four), '(' or '→', and '– Nursing note:' (an entry phrase's label): held, the question quoting
        the whole line. c2e53f8e: all seven needs_clarification [performed_status], the identical question.
        e5628be56: READY (fold stripped only _ROLE_LEAD). The '• Nurse:' control was held on all three engines and
        still is."""
        for prefix in ('– Nurse: ', '— Nurse: ', '◦ Nurse: ', '▪ Nurse: ', '(Nurse: ', '→ Nurse: ', '– Nursing note: ',
                       '• Nurse: '):
            inv, text, codes = on_its_line(prefix + SNARE_LINE)
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', prefix + SNARE_LINE),
                      prefix=prefix)

    def test_d146_controls_a_digit_or_underscore_opens_no_label(self):
        """'1) Nurse: ...' and '_Nurse: ...': a digit and '_' are word characters for ^\\W*, so no label opens the
        line. READY on this build, on e5628be56 and on c2e53f8e."""
        for prefix in ('1) Nurse: ', '_Nurse: '):
            inv, text, codes = on_its_line(prefix + SNARE_LINE)
            self.ready(run(inv, text, codes), '45385', prefix=prefix)

    def test_d146_no_label_the_folded_line_held_is_lost(self):
        """'ſedation record: ...' (a long s): fold case-folds it to 'sedation record:', an anesthesia entry phrase
        and its colon, as e5628be56 read it (held); reading the line from its first ASCII letter alone would drop the
        long s and lose that label, so label_of reads both. c2e53f8e: READY (its ROLE_LABEL has no sedation label, and
        re.A does not fold 'ſ'): a hold kept where it is READY, as at e5628be56."""
        inv, text, codes = on_its_line('ſedation record: ' + SNARE_LINE)
        self.held(run(inv, text, codes), '45385',
                  nursing_question('snare removal', 'ſedation record: ' + SNARE_LINE, 'anesthesia'))


class ASignatureLabelMakesTheActItsRoles(Held):
    """D146 (4), review_colon2.json problem 3: services.ROLE_SIGNATURE, read in the label closed by a colon before the
    act's own words."""

    def test_d146_a_signature_label_closed_before_the_act(self):
        """The review's two: 'Findings' / 'Documented by Jo Rowe, RN: A 6 mm sessile polyp ... cold snare.' and
        'Per nursing note: ...'. c2e53f8e: both needs_clarification [performed_status], its another-role question
        quoting the whole line. e5628be56: both READY."""
        for label in ('Documented by Jo Rowe, RN: ', 'Per nursing note: '):
            inv, text, codes = on_its_line(label + SNARE_LINE)
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', label + SNARE_LINE),
                      label=label)

    def test_d146_the_line_of_a_cited_sentence(self):
        """The same lines, Gemini citing only the sentence after the label: the line it stands on opens with the
        signature label. Held, quoting the passage. c2e53f8e: held [performed_status], its question quoting its own
        sentence, the whole line (as D124 reads 'Nurse:' before a cited clause). e5628be56: READY."""
        for label in ('Documented by Jo Rowe, RN: ', 'Per nursing note: '):
            inv, text, codes = clause_after(label)
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', SNARE_LINE), label=label)

    def test_d146_each_signature_form(self):
        """Nursing: each record word with 'by' and a nurse word ('Entered by Jo Rowe, LPN:', 'Charted by the recovery
        nurse:', 'Completed by Jo Rowe RN:', 'Documented by\\tJo Rowe, RN:'), in capitals ('DOCUMENTED BY JO ROWE,
        RN:'), with the signature after an earlier colon ('Note: documented by Jo Rowe, RN:': the label runs to the
        last colon before the act) and with a later colon in the label ('Documented by Jo Rowe, RN: time 08:30:');
        'nursing' with an entry word ('Per nursing entry:', 'Per nursing  note:'). Anesthesia: 'Per CRNA, recorded in
        the record:', 'Anesthesiologist documented:', 'CRNA note documented:'; and both roles' signatures in one label,
        in either order ('Documented by Jo Rowe, RN and CRNA charted:', 'CRNA charted, documented by Jo Rowe, RN:'):
        anesthesia, the installed release's last match. c2e53f8e: every one held [performed_status], naming the same
        entry, with the identical question. e5628be56: READY on all."""
        for label, entry in (('Entered by Jo Rowe, LPN: ', 'nursing'), ('Charted by the recovery nurse: ', 'nursing'),
                             ('Completed by Jo Rowe RN: ', 'nursing'), ('Documented by\tJo Rowe, RN: ', 'nursing'),
                             ('DOCUMENTED BY JO ROWE, RN: ', 'nursing'),
                             ('Note: documented by Jo Rowe, RN: ', 'nursing'),
                             ('Documented by Jo Rowe, RN: time 08:30: ', 'nursing'),
                             ('Per nursing entry: ', 'nursing'), ('Per nursing  note: ', 'nursing'),
                             ('Per CRNA, recorded in the record: ', 'anesthesia'),
                             ('Anesthesiologist documented: ', 'anesthesia'), ('CRNA note documented: ', 'anesthesia'),
                             ('Documented by Jo Rowe, RN and CRNA charted: ', 'anesthesia'),
                             ('CRNA charted, documented by Jo Rowe, RN: ', 'anesthesia')):
            inv, text, codes = on_its_line(label + SNARE_LINE)
            self.held(run(inv, text, codes), '45385', asks(label + SNARE_LINE, entry), label=label)

    def test_d146_the_reaches_are_60_60_and_40_characters(self):
        """'Documented' + 60 characters + 'by Jo Rowe, RN:' and 'Documented by ' + 60 characters + 'RN:' are held;
        61 is READY. 'CRNA' + 40 characters + 'documented:' is held; 41 is READY. c2e53f8e: the same six outcomes (held
        [performed_status], with the identical question; READY). e5628be56: READY on all six."""
        for label, held in (('Documented' + G60 + 'by Jo Rowe, RN: ', 'nursing'),
                            ('Documented' + G61 + 'by Jo Rowe, RN: ', ''),
                            ('Documented by ' + H60 + 'RN: ', 'nursing'), ('Documented by ' + H61 + 'RN: ', ''),
                            ('CRNA' + A40 + 'documented: ', 'anesthesia'), ('CRNA' + A41 + 'documented: ', '')):
            inv, text, codes = on_its_line(label + SNARE_LINE)
            if held:
                self.held(run(inv, text, codes), '45385', asks(label + SNARE_LINE, held), reach=len(label))
            else:
                self.ready(run(inv, text, codes), '45385', reach=len(label))

    def test_d146_a_signature_label_on_a_line_the_physicians_label_opens(self):
        """'Findings' / 'Endoscopist: see below. Documented by Jo Rowe, RN: A 6 mm sessile polyp ... cold snare.', the
        snare citing the whole line, the signed sentence, or the sentence after the signature label: the physician's
        label opens the line, but the signature label closes before the act's own words, so the act is the nurse's.
        Held, quoting the passage. c2e53f8e: all three held [performed_status], its another-role question quoting its
        own sentence ('Documented by Jo Rowe, RN: A 6 mm ...', the second passage's own words). e5628be56: READY on all
        three (the physician's line). Costs, not pinned: 'Endoscopist: documented by Jo Rowe, RN: ...' and 'Physician
        note: Reviewed nursing note: ...' are held here and READY on c2e53f8e, whose physician ROLE_LABEL on the act's
        own sentence comes first (DECISIONS D146)."""
        line = 'Endoscopist: see below. Documented by Jo Rowe, RN: ' + SNARE_LINE
        for passage in (line, 'Documented by Jo Rowe, RN: ' + SNARE_LINE, SNARE_LINE):
            inv, text, codes = cited_on(line, passage)
            self.held(run(inv, text, codes), '45385', asks(passage), passage=passage[:30])

    def test_d146_an_entry_heading_above_still_names_the_entry(self):
        """'Anesthesia record' / 'Documented by Jo Rowe, RN: ...', and 'Pathology report' / 'CRNA documented: ...':
        the heading above names the entry, as the installed release reads a signature only in a physician's part
        (part.role == 'physician'). c2e53f8e: both held, naming the anesthesia and the pathology entry."""
        for heading, label, entry in (('Anesthesia record', 'Documented by Jo Rowe, RN: ', 'anesthesia'),
                                      ('Pathology report', 'CRNA documented: ', 'pathology')):
            inv, text, codes = after_the_entry([], label + SNARE_LINE, heading=heading)
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', label + SNARE_LINE, entry),
                      heading=heading)

    def test_d146_controls_a_signature_anywhere_else_names_no_role(self):
        """READY on this build, on e5628be56 and on c2e53f8e: a signature after the act's own words ('..., placed in
        formalin and documented by Jo Rowe, RN.'; '...; specimen: documented by Jo Rowe, RN.'); 'by' with no space
        after it ('Recorded by: Jo Rowe, RN:', 'Documented byJo Rowe, RN:'); a record or nurse word inside a longer
        word ('Undocumented by Jo Rowe, RN:', 'Documented by Jo Rowe, RNs:', 'Per nursing notes:'); a reach crossing a
        period ('Documented by Jo Rowe. RN team:'); 'anesthetist', which ROLE_SIGNATURE does not list ('Anesthetist
        documented:'); and a letter only Unicode case folding makes ASCII ('Documented by Jo Rowe, nurſe:')."""
        for line in (TAIL + ', placed in formalin and documented by Jo Rowe, RN.',
                     TAIL + '; specimen: documented by Jo Rowe, RN.', 'Recorded by: Jo Rowe, RN: ' + SNARE_LINE,
                     'Documented byJo Rowe, RN: ' + SNARE_LINE, 'Undocumented by Jo Rowe, RN: ' + SNARE_LINE,
                     'Documented by Jo Rowe, RNs: ' + SNARE_LINE, 'Per nursing notes: ' + SNARE_LINE,
                     'Documented by Jo Rowe. RN team: ' + SNARE_LINE, 'Anesthetist documented: ' + SNARE_LINE,
                     'Documented by Jo Rowe, nurſe: ' + SNARE_LINE):
            inv, text, codes = on_its_line(line)
            self.ready(run(inv, text, codes), '45385', line=line[:40])

    def test_d146_a_signature_line_above_the_act_stands_in_its_sentence(self):
        """Formerly test_d146_controls_a_signature_line_above_the_act_names_no_role (READY on 05a881a75, e5628be56 and
        c2e53f8e). DECISIONS D165 (1) changes the expectation: 'Findings' / 'Documented by Jo Rowe, RN:' (or 'Per
        nursing note:', or 'Documented by Jo Rowe, RN: see below') / the snare line, the snare line cited alone. The
        line above ends with no sentence end ('.', '!' or '?' followed by whitespace, the engine's own boundary), so it
        stands in the act's sentence and its signature label is read for the act: held [performed_status] another_role,
        as D158 holds the same lines cited as one passage (colon4's K1). A RECORDED COST: c2e53f8e is READY in both
        configurations (its _sentences cuts after a line a colon ends and before a line that opens a sentence)."""
        for line in ('Documented by Jo Rowe, RN:', 'Per nursing note:', 'Documented by Jo Rowe, RN: see below'):
            inv, text, codes = after_the_entry([line], SNARE_LINE, heading='Findings')
            self.held(run(inv, text, codes), '45385', nursing_question('snare removal', SNARE_LINE), line=line)

    def test_d146_a_reading_without_the_text_reads_the_passages_own_signature_and_label(self):
        """events.evaluate over a Reading with no text (the review overlay's counted codes, a unit test's): the
        passage 'Documented by Jo Rowe, RN: A 6 mm ...' opens with its signature label, and '– Nurse: A 6 mm ...' with
        its label, so both acts are held there too."""
        for line in ('Documented by Jo Rowe, RN: ' + SNARE_LINE, '– Nurse: ' + SNARE_LINE):
            inv, text, _ = on_its_line(line)
            evaluation = events.evaluate('45385', kept(text, line), events.Reading.of(inv))
            with self.subTest(line=line):
                self.assertEqual(evaluation.reason, events.ANOTHER_ROLE)
                self.assertEqual(set(evaluation.supporting) | set(evaluation.read), {'E2'})


class AHeldCodeSupportsNothing(SimpleTestCase):
    """D146 (5), review_colon2.json problem 4: the corrected jobs._assess_child_events docstring - a code
    another_role_hold holds supports nothing, so a rival that competed with it for the same act loses that
    competing_codes hold. DECISIONS D163 (round 5f) withdraws that release: a held code keeps its acts as claims for
    the competition (assess._claims), so the rival stays held."""

    def test_d146_its_rival_for_the_same_act_stays_held(self):
        """Formerly test_d146_its_rival_for_the_same_act_is_ready (43264 held [performed_status], 43265 READY; the
        same on e5628be56; c2e53f8e READY with no participant, both held [competing_codes] with its participants).
        DECISIONS D163: the review's ERCP report with the extraction told under 'Nursing note', 'Nursing note -
        recovery', 'Nursing note, recovery room' or 'Procedure checklist': 43264 held another_role asks
        [performed_status, competing_codes] and 43265 is held [competing_codes]. With no heading, both held
        [competing_codes], as before."""
        for heading in ('Nursing note', 'Nursing note - recovery', 'Nursing note, recovery room',
                        'Procedure checklist'):
            result = run(*ercp_report(heading))
            with self.subTest(heading=heading):
                first, second = proposal(result, '43264'), proposal(result, '43265')
                self.assertEqual((first.status, asked(first), first.support['reason']),
                                 ('needs_clarification', ['performed_status', 'competing_codes'], events.ANOTHER_ROLE))
                self.assertEqual((second.status, asked(second), second.support['reason']),
                                 ('needs_clarification', ['competing_codes'], events.SUPPORTED))
        result = run(*ercp_report(''))
        with self.subTest(heading='none'):
            for code in ('43264', '43265'):
                self.assertEqual((proposal(result, code).status, asked(proposal(result, code))),
                                 ('needs_clarification', ['competing_codes']))
