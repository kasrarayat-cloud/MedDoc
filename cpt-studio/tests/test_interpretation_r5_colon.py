"""DECISIONS D124 and D125 (the Gemini migration's round 5: the round-4 family parity audit's colon-sig gaps 0 and 1,
its egd gap I, and the round-4 enteroscopy review's parity note 2), SYNTHETIC, each built from its source's own input.
Nothing is sent.
- D124 (colon-sig gap 0): a code whose every act is documented only in another role's entry - a passage that begins
  with a role label ("Nurse:", "Pathology report", ...), or a line in the lines after a role's heading line and before
  the next heading - is held with performed_status naming that entry, never READY, as the installed release's
  engine._another_roles_hold holds it (owner directive 2026-11-06, item 2). An act with any statement passage outside
  such entries is unaffected. Sources: the audit's T02 (a snare in a nursing note), U05 (a biopsy in a nursing note),
  T03 (a biopsy under a pathology report heading), controls U06 and U07.
- D125 (colon-sig gap 1, egd gap I, enteroscopy parity note 2): a documented colonoscopy, flexible sigmoidoscopy, upper
  endoscopy or enteroscopy session whose done examinations state neither a reach nor a completion, for which no
  proposal of the family already asks the extent, gets the service-scope extent question in the catalogue's words, as
  the installed release's reconcile.documentation_clarifications asks it. Sources: the audit's T04, T05 and T06, the
  egd audit's I2 and I3, the enteroscopy review's push-enteroscopy document.
The installed release's outputs on these inputs (c2e53f8e, engine.assess as tests/test_harness_engine.py drives it, on
the same texts and codes) are in each test's docstring. Each test asserts in independent subtests, so a regression
shows every one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import coverage, events, normalize
from studio.types import ClarificationSpec, EvidenceSpan
from tests.test_interpretation_events import asked, check, inventory, proposal, run
from tests.test_interpretation_identity import DATE_LINE, a, accepted, act, answer, les, sc, snare, tg
from tests.test_interpretation_r3_integration_d88_d93 import reviewed

# --- the audit's structured report (the installed reader reads it as its own harness's COLON fixture does) -----------

CECUM_DONE = 'The colonoscope was advanced to the cecum and the examination was completed.'
SNARE_LINE = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
NURSE_SNARE = 'Nurse: A 6 mm polyp in the sigmoid colon was removed with a cold snare and retrieved.'
NURSE_BIOPSY = 'Nurse: Cold forceps biopsies of the sigmoid colon polyp were obtained and sent to pathology.'
PATH_BIOPSY = 'Sigmoid colon polyp, cold forceps biopsy: tubular adenoma.'
EXTENT = dict(catalogue.ENDOSCOPIC_QUESTIONS)['extent']  # 'How far was the instrument advanced (the landmark reached)?'


def head(kind: str = 'Colonoscopy', heading: str = '') -> dict:
    return {'P1': f'{kind} report (fictional)', 'P2': 'Place of service: Ambulatory surgery center',
            'P3': f'Procedure: {heading or kind}'}


def cexam(passage: str = 'P4', words: str = 'colonoscope', status_words: str = 'was advanced', **changes) -> dict:
    return act('E1', passage, 'examination', words, status_words=status_words,
               technique=a('endoscope', words, [passage]), **changes)


def creach(landmark: str = 'cecum', words: str = 'cecum', passage: str = 'P4', completion=None) -> dict:
    return {'event': 'E1', 'landmark': landmark, 'words': words, 'passages': [passage],
            'completion': completion or a('complete', 'the examination was completed', [passage])}


def lesion(lid: str, words: str, passage: str, landmark: str, site: str, size: str = '') -> dict:
    return les(lid, words, passage, landmark=landmark, site_words=site, size_words=size)


def csnare(eid: str, passage: str, lid: str, landmark: str, words: str, **changes) -> dict:
    return snare(eid, passage, target=tg(lid, landmark, words, [passage]), **changes)


def document(lines, passages: dict, **options) -> tuple:
    """(the inventory, the text) of an answer citing ``passages`` ({id: text}) over a document whose lines are DATE_LINE
    then ``lines`` - a passage need not be a whole line (a clause after a label), and a line need not be a passage (a
    heading no event cites, a blank line)."""
    reach = options.pop('reach', ())
    value, _ = answer(dict(passages), reach=list(reach), **options)
    text = '\n'.join([DATE_LINE, *lines]) + '\n'
    assert all(record['text'] in text for record in value['passages']), 'every passage is in the document'
    return normalize.normalize(accepted(value), text), text


def overlay_status(test, result, code: str, status: str) -> None:
    """The read-time overlay keeps ``code`` at ``status``, releasing and recomputing nothing."""
    view = reviewed(result, code)
    test.assertEqual((view.status, view.released, view.recomputed), (status, (), ()))


def service_questions(result) -> list:
    return [(spec.scope, spec.fact, spec.family, spec.question) for spec in result.clarifications]


def items(result) -> list:
    return [(item['service'], item['reason'], item['act']) for item in result.completeness['unresolved_items']]


# --- D124: the gap's inputs ------------------------------------------------------------------------------------------

def t02_nursing_snare(codes=(('45385', NURSE_SNARE),)) -> tuple:
    """The audit's T02: the physician's report states the colonoscopy to the cecum; the snare is told only in the
    nursing note ('Nursing note' / 'Nurse: A 6 mm polyp ...')."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': 'Nursing note', 'P6': NURSE_SNARE}
    inv, text = inventory(lines, events=[cexam(), csnare('E2', 'P6', 'L1', 'sigmoid_colon',
                                                         '6 mm polyp in the sigmoid colon')],
                          lesions=[lesion('L1', '6 mm polyp', 'P6', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                          reach=[creach()])
    return inv, text, list(codes)


def u05_nursing_biopsy() -> tuple:
    """The audit's U05: a biopsy told only in the nursing note."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': 'Nursing note', 'P6': NURSE_BIOPSY}
    inv, text = inventory(lines, events=[cexam(), act('E2', 'P6', 'biopsy', 'biopsies', status_words='were obtained',
                                                      technique=a('cold_forceps', 'Cold forceps', ['P6']),
                                                      target=tg('L1', 'sigmoid_colon', 'sigmoid colon polyp', ['P6']))],
                          lesions=[lesion('L1', 'sigmoid colon polyp', 'P6', 'sigmoid_colon', 'sigmoid colon')],
                          reach=[creach()])
    return inv, text, [('45380', NURSE_BIOPSY)]


def t03_pathology_biopsy() -> tuple:
    """The audit's T03: a biopsy told only under the 'Pathology report' heading, its own line carrying no label."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': 'Pathology report', 'P6': PATH_BIOPSY}
    biopsy = act('E2', 'P6', 'biopsy', 'biopsy', status_words='cold forceps biopsy',
                 technique=a('cold_forceps', 'cold forceps', ['P6']),
                 target=tg('L1', 'sigmoid_colon', 'Sigmoid colon polyp', ['P6']))
    inv, text = inventory(lines, events=[cexam(), biopsy],
                          lesions=[lesion('L1', 'Sigmoid colon polyp', 'P6', 'sigmoid_colon', 'Sigmoid colon')],
                          reach=[creach()])
    return inv, text, [('45380', PATH_BIOPSY)]


def u06_physician_too(restated: bool = False) -> tuple:
    """The audit's U06 control: the physician's own line states the snare, and the nursing note repeats it - cited by
    the snare event (``restated``: its kind and status passages are both lines) or not."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': SNARE_LINE, 'P6': 'Nursing note', 'P7': NURSE_SNARE}
    e2 = csnare('E2', 'P5', 'L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon')
    if restated:
        e2.update(kind=a('snare', 'removed', ['P5', 'P7']),
                  status=a('performed', 'was removed with a cold snare', ['P5', 'P7']))
    inv, text = inventory(lines, events=[cexam(), e2],
                          lesions=[lesion('L1', '6 mm sessile polyp', 'P5', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                          reach=[creach()])
    return inv, text, [('45385', SNARE_LINE)]


def u07_unknown_performer() -> tuple:
    """The audit's U07: T02's nursing line, its performer given 'unknown' (the contract's other answer)."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': 'Nursing note', 'P6': NURSE_SNARE}
    inv, text = inventory(lines, events=[cexam(), csnare('E2', 'P6', 'L1', 'sigmoid_colon',
                                                         '6 mm polyp in the sigmoid colon', performer=a('unknown'))],
                          lesions=[lesion('L1', '6 mm polyp', 'P6', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                          reach=[creach()])
    return inv, text, [('45385', NURSE_SNARE)]


NURSE_CLAUSE = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare and retrieved.'


def clause_after_the_label() -> tuple:
    """T02's nursing line with no heading above it, Gemini citing the clause after its 'Nurse:' label: the passage does
    not begin with the label, the line it stands on does."""
    lines = ['Colonoscopy report (fictional)', 'Place of service: Ambulatory surgery center', 'Procedure: Colonoscopy',
             CECUM_DONE, NURSE_SNARE]
    passages = {'P1': CECUM_DONE, 'P2': NURSE_CLAUSE}
    inv, text = document(lines, passages, events=[cexam('P1'), csnare('E2', 'P2', 'L1', 'sigmoid_colon',
                                                                      '6 mm polyp in the sigmoid colon')],
                         lesions=[lesion('L1', '6 mm polyp', 'P2', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', NURSE_CLAUSE)]


FINDINGS_POLYP = 'Findings: A 6 mm sessile polyp in the sigmoid colon.'
NURSE_REMOVED = 'Nurse: The polyp was removed with a cold snare and retrieved.'
ENDOSCOPIST_SNARE = 'Endoscopist: A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'


def lesion_described_by_the_physician() -> tuple:
    """The physician's findings describe the polyp (the snare's TARGET passage); the removal itself - its kind and
    status - is told only in the nursing note."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': FINDINGS_POLYP, 'P6': 'Nursing note', 'P7': NURSE_REMOVED}
    e2 = snare('E2', 'P7', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P5']))
    inv, text = inventory(lines, events=[cexam(), e2],
                          lesions=[lesion('L1', '6 mm sessile polyp', 'P5', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                          reach=[creach()])
    return inv, text, [('45385', NURSE_REMOVED)]


CECUM_BIOPSY = 'A 4 mm polyp in the cecum was biopsied with cold forceps.'


def two_biopsies() -> tuple:
    """45380 over two biopsies: the physician's own (the cecal polyp) and one told only in the nursing note (U05's)."""
    lines = {**head(), 'P4': CECUM_DONE, 'P5': CECUM_BIOPSY, 'P6': 'Nursing note', 'P7': NURSE_BIOPSY}
    inv, text = inventory(lines, events=[
        cexam(),
        act('E2', 'P5', 'biopsy', 'biopsied', status_words='was biopsied',
            technique=a('cold_forceps', 'cold forceps', ['P5']),
            target=tg('L1', 'cecum', '4 mm polyp in the cecum', ['P5'])),
        act('E3', 'P7', 'biopsy', 'biopsies', status_words='were obtained',
            technique=a('cold_forceps', 'Cold forceps', ['P7']),
            target=tg('L2', 'sigmoid_colon', 'sigmoid colon polyp', ['P7']))],
        lesions=[lesion('L1', '4 mm polyp', 'P5', 'cecum', 'cecum', '4 mm'),
                 lesion('L2', 'sigmoid colon polyp', 'P7', 'sigmoid_colon', 'sigmoid colon')],
        reach=[creach()])
    return inv, text, [('45380', (CECUM_BIOPSY, NURSE_BIOPSY))]


def after_the_entry(between: list, act_line: str = SNARE_LINE, heading: str = 'Nursing note') -> tuple:
    """A role's heading, then the lines ``between``, then the snare on ``act_line``: whether the act is in the entry is
    what lies between."""
    lines = ['Colonoscopy report (fictional)', 'Procedure: Colonoscopy', CECUM_DONE, heading, *between, act_line]
    passages = {'P1': CECUM_DONE, 'P2': act_line}
    inv, text = document(lines, passages, events=[cexam('P1'), csnare('E2', 'P2', 'L1', 'sigmoid_colon',
                                                                      '6 mm sessile polyp in the sigmoid colon')],
                         lesions=[lesion('L1', '6 mm sessile polyp', 'P2', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', act_line)]


def above_the_act(line: str) -> tuple:
    """T02's physician report with ``line`` (a staff field, a section heading, a plan line) above the physician's own
    snare line, and no role heading anywhere."""
    lines = ['Colonoscopy report (fictional)', 'Procedure: Colonoscopy', CECUM_DONE, line, SNARE_LINE]
    passages = {'P1': CECUM_DONE, 'P2': SNARE_LINE}
    inv, text = document(lines, passages, events=[cexam('P1'), csnare('E2', 'P2', 'L1', 'sigmoid_colon',
                                                                      '6 mm sessile polyp in the sigmoid colon')],
                         lesions=[lesion('L1', '6 mm sessile polyp', 'P2', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', SNARE_LINE)]


def kept(text: str, phrase: str) -> tuple:
    start = text.index(phrase)
    return (EvidenceSpan(0, start, start + len(phrase), phrase, True),)


def nursing_question(what: str, passage: str, entry: str = 'nursing') -> str:
    """c2e53f8e engine._another_roles_hold's question (engine.py:971-973), for a colonoscopy."""
    return (f'The {what} is documented only in the {entry} entry (“{passage}”). Was it performed in this colonoscopy '
            'on the date of service?')


class AnActToldOnlyInAnotherRolesEntryIsHeld(SimpleTestCase):
    """D124 (colon-sig gap 0). c2e53f8e holds every one of these with its another-role question (T02, U05) or
    act_missing (T03); 1caaf0609 READYs them all with no question and coding complete_pending_review."""

    def held(self, result, code: str, question: str, events_=('E2',)) -> None:
        p = proposal(result, code)
        with self.subTest(code=code, part='assess'):
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']))
            self.assertEqual(p.clarifications[0].question, question)
            self.assertEqual((p.support['state'], p.support['reason']), ('uncertain', events.ANOTHER_ROLE))
            self.assertEqual(p.support['question_events'], list(events_))
            self.assertEqual(check(p, 'events.match').status, 'warn')
            self.assertIn('not by the physician performing the colonoscopy. Held for the reviewer, not excluded.',
                          check(p, 'service.status').detail)
        with self.subTest(code=code, part='overlay'):
            overlay_status(self, result, code, 'needs_clarification')
        with self.subTest(code=code, part='coverage'):  # the act stays the code's: listed nowhere as uncovered
            self.assertEqual([entry for entry in items(result) if entry[2] not in ('', 'examination')], [])

    def test_d124_a_snare_told_only_in_a_nursing_note_is_held(self):
        """T02. c2e53f8e: 45385 needs_clarification [performed_status], this question word for word."""
        inv, text, codes = t02_nursing_snare()
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', NURSE_SNARE))

    def test_d124_a_biopsy_told_only_in_a_nursing_note_is_held(self):
        """U05. c2e53f8e: 45380 needs_clarification [performed_status], this question word for word."""
        inv, text, codes = u05_nursing_biopsy()
        self.held(run(inv, text, codes), '45380', nursing_question('forceps biopsy', NURSE_BIOPSY))

    def test_d124_a_biopsy_told_only_under_a_pathology_report_heading_is_held(self):
        """T03: its own line carries no label; the 'Pathology report' heading line above it opens the entry. c2e53f8e:
        45380 needs_clarification [performed_status] (act_missing: its reader reads no biopsy act there)."""
        inv, text, codes = t03_pathology_biopsy()
        self.held(run(inv, text, codes), '45380', nursing_question('forceps biopsy', PATH_BIOPSY, 'pathology'))

    def test_d124_the_label_opening_the_line_of_a_cited_clause(self):
        """Gemini cites the clause after 'Nurse:' (prompt.py: a passage is a sentence, a clause or a line): the line
        it stands on opens with the label, so the act is still the nursing note's. c2e53f8e: 45385 held
        [performed_status], its another-role question quoting the whole line."""
        inv, text, codes = clause_after_the_label()
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', NURSE_CLAUSE))

    def test_d124_a_lesion_the_physician_describes_does_not_release_the_nurses_removal(self):
        """The snare's target passage is the physician's findings line; its kind and status - the removal itself -
        are only the nurse's. c2e53f8e: 45385 held [performed_status]. 1caaf0609: READY."""
        inv, text, codes = lesion_described_by_the_physician()
        self.held(run(inv, text, codes), '45385', nursing_question('snare removal', NURSE_REMOVED))

    def test_d124_beside_its_base_code(self):
        """T02 with 45378 citing the examination: 45378 keeps its base_included hold beside 45385, which is held as
        above. c2e53f8e: both needs_clarification (45378 [base_included], 45385 [performed_status])."""
        inv, text, codes = t02_nursing_snare((('45378', CECUM_DONE), ('45385', NURSE_SNARE)))
        result = run(inv, text, codes)
        self.held(result, '45385', nursing_question('snare removal', NURSE_SNARE))
        with self.subTest(code='45378'):
            self.assertEqual((proposal(result, '45378').status, asked(proposal(result, '45378'))),
                             ('needs_clarification', ['base_included']))


class TheEntryIsWhatItsLabelsAndHeadingsSay(SimpleTestCase):
    """D124's reading of a role's entry: an act with a statement passage outside it is unaffected, the next heading
    ends it, a blank line does not, and a staff field or a section that names a role is no entry."""

    def test_d124_controls_the_physicians_own_line_states_the_act(self):
        """U06: the snare cites the physician's own line only, or that line and the nursing note's restatement. Both
        READY, as on c2e53f8e."""
        for restated in (False, True):
            inv, text, codes = u06_physician_too(restated)
            result = run(inv, text, codes)
            p = proposal(result, '45385')
            with self.subTest(restated=restated):
                self.assertEqual((p.status, asked(p), p.support['reason']), ('ready', [], events.SUPPORTED))
                overlay_status(self, result, '45385', 'ready')

    def test_d124_controls_one_act_of_the_physicians_beside_one_of_the_nurses(self):
        """45380 over the physician's own cecal biopsy and the nurse's sigmoid one: an act outside the entry leaves the
        code as it is (c2e53f8e: any act of an own role, READY; the same here)."""
        inv, text, codes = two_biopsies()
        result = run(inv, text, codes)
        p = proposal(result, '45380')
        self.assertEqual((p.status, asked(p), p.support['reason']), ('ready', [], events.SUPPORTED))
        self.assertEqual([act_['id'] for act_ in p.support['acts']], ['E2', 'E3'])

    def test_d124_controls_an_unknown_performer_keeps_its_own_question(self):
        """U07: the nursing line with the performer Gemini leaves unknown. 1caaf0609 and this build: event_performer
        (C6: an unknown performer is never a match), so D124's hold is never reached. c2e53f8e: performed_status, its
        another-role question (its role reader reads no performer). Held on all three."""
        inv, text, codes = u07_unknown_performer()
        p = proposal(run(inv, text, codes), '45385')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['event_performer']))

    def test_d124_the_next_heading_ends_the_entry_and_a_blank_line_does_not(self):
        """'Nursing note' then a 'Findings' heading: the physician's snare line after it is READY. 'Pathology report',
        a blank line, the snare line: held; so is a snare line after a nursing line. A line the physician's own label
        opens ("Endoscopist: ...") inside the nursing note is the physician's: READY. c2e53f8e: the same four outcomes
        (READY, held [performed_status] twice, READY)."""
        cases = (('heading', ['Nurse: Patient tolerated the procedure well.', 'Findings'], 'Nursing note', 'ready',
                  SNARE_LINE),
                 ('blank line', [''], 'Pathology report', 'needs_clarification', SNARE_LINE),
                 ('nursing lines', ['Nurse: Patient tolerated the procedure well.'], 'Nursing note',
                  'needs_clarification', SNARE_LINE),
                 ("the physician's own label", ['Nurse: Patient tolerated the procedure well.'], 'Nursing note',
                  'ready', ENDOSCOPIST_SNARE))
        for name, between, heading, status, act_line in cases:
            inv, text, codes = after_the_entry(between, act_line, heading=heading)
            p = proposal(run(inv, text, codes), '45385')
            with self.subTest(case=name):
                self.assertEqual(p.status, status)
                self.assertEqual(p.support['reason'],
                                 events.SUPPORTED if status == 'ready' else events.ANOTHER_ROLE)

    def test_d124_a_staff_field_or_a_section_naming_a_role_is_no_entry(self):
        """Lines that name a role and head nothing (services.ROLE_HEADINGS' own refutation, r1 missed-1, and FRESH's
        own section names), above the physician's snare line: READY on this build, and on c2e53f8e but under 'Recovery
        instructions and management plan', which c2e53f8e holds for its own reading of that section (performed_status,
        "a passage it cites about this service reads as uncertain"), not as another role's."""
        for line in ('Nurse: Jo Rowe, RN', 'RN: Jo Rowe', 'Nursing staff: Jo Rowe, RN; Sam Lee, LPN',
                     'Nurse present throughout the procedure.', 'Anesthesia, equipment, and quality measures',
                     'Anesthesia: Monitored anesthesia care (MAC) by the anesthesia service.',
                     'Recovery instructions and management plan',
                     '- Pathology from jars 1-3 will be sent to her and to her primary care'):
            inv, text, codes = above_the_act(line)
            p = proposal(run(inv, text, codes), '45385')
            with self.subTest(line=line):
                self.assertEqual((p.status, p.support['reason']), ('ready', events.SUPPORTED))

    def test_d124_a_reading_without_the_text_reads_the_passages_own_labels(self):
        """events.evaluate over a Reading with no text (the review overlay's counted codes, a unit test's): T02's act
        is still held - its passage opens with 'Nurse:' - while T03's, which only its heading places in the pathology
        entry, is supported. The overlay reads only the counted code's events from it, which are the same either way
        (the held code's read event is that act)."""
        for build, code, phrase, reason in ((t02_nursing_snare, '45385', NURSE_SNARE, events.ANOTHER_ROLE),
                                            (t03_pathology_biopsy, '45380', PATH_BIOPSY, events.SUPPORTED)):
            inv, text, _ = build()
            evaluation = events.evaluate(code, kept(text, phrase), events.Reading.of(inv))
            with self.subTest(code=code):
                self.assertEqual(evaluation.reason, reason)
                self.assertEqual(set(evaluation.supporting) | set(evaluation.read), {'E2'})


# --- D125: the service-scope extent question --------------------------------------------------------------------------

PERFORMED = 'Colonoscopy was performed with good preparation.'
SIG_SNARE = 'A 4 mm polyp in the rectum was removed with a cold snare.'
NO_BIOPSIES = 'No biopsies were taken.'


def t04_colonoscopy(*more, lines=None, codes=(), reach=(), examination=None) -> tuple:
    """The audit's T04: 'Colonoscopy was performed with good preparation.' (E1, no reach entry: the document states
    none) and the cold snare of the sigmoid polyp (E2)."""
    base = {**head(), 'P4': PERFORMED, 'P5': SNARE_LINE, **(lines or {})}
    exam = examination or act('E1', 'P4', 'examination', 'Colonoscopy', status_words='was performed')
    inv, text = inventory(base, events=[exam, csnare('E2', 'P5', 'L1', 'sigmoid_colon',
                                                     '6 mm sessile polyp in the sigmoid colon'), *more],
                          lesions=[lesion('L1', '6 mm sessile polyp', 'P5', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                          reach=list(reach))
    return inv, text, list(codes)


def t05_sigmoidoscopy() -> tuple:
    """The audit's T05: the same for a flexible sigmoidoscopy (a rectal polyp, cold snare)."""
    lines = {**head('Flexible sigmoidoscopy'), 'P4': 'Flexible sigmoidoscopy was performed with good preparation.',
             'P5': SIG_SNARE}
    inv, text = inventory(lines, events=[act('E1', 'P4', 'examination', 'Flexible sigmoidoscopy',
                                             status_words='was performed', procedure=a('flex_sig')),
                                         csnare('E2', 'P5', 'L1', 'rectum', '4 mm polyp in the rectum',
                                                procedure=a('flex_sig'))],
                          lesions=[lesion('L1', '4 mm polyp', 'P5', 'rectum', 'rectum', '4 mm')])
    return inv, text, []


def i2_upper_endoscopy(codes=()) -> tuple:
    """The egd audit's I2 (and, with 43239, its control I3): 'The gastroscope was introduced through the mouth under
    direct vision.' (no reach entry) and cold forceps biopsies of the gastric antrum, under 'UPPER ENDOSCOPY REPORT'."""
    egd = a('egd', 'UPPER ENDOSCOPY', ['P1'])
    lines = {'P1': 'UPPER ENDOSCOPY REPORT', 'P2': 'Endoscopist: Tomas Reyes, MD (fictional)',
             'P3': 'The gastroscope was introduced through the mouth under direct vision.',
             'P4': 'Biopsies of the gastric antrum were taken with cold forceps.'}
    inv, text = inventory(lines, events=[
        act('E1', 'P3', 'examination', 'The gastroscope was introduced', status_words='was introduced', procedure=egd,
            technique=a('endoscope', 'gastroscope', ['P3'])),
        act('E2', 'P4', 'biopsy', 'Biopsies', status_words='were taken', procedure=egd,
            technique=a('cold_forceps', 'cold forceps', ['P4']), target=tg('', 'gastric_antrum', 'the gastric antrum',
                                                                            ['P4']))])
    return inv, text, list(codes)


ENTERO_BIOPSY = 'Biopsies of the jejunum were taken with cold forceps.'


def push_enteroscopy(codes=(('43239', ENTERO_BIOPSY),)) -> tuple:
    """The round-4 enteroscopy review's parity note 2: 'PUSH ENTEROSCOPY REPORT' / 'Procedure: Push enteroscopy.' / 'The
    enteroscope was introduced and the small bowel was examined.' / the jejunal biopsies, no reach entry, and only
    43239 (an upper endoscopy biopsy code) proposed."""
    entero = a('enteroscopy', 'Push enteroscopy', ['P2'])
    lines = {'P1': 'PUSH ENTEROSCOPY REPORT', 'P2': 'Procedure: Push enteroscopy.',
             'P3': 'The enteroscope was introduced and the small bowel was examined.', 'P4': ENTERO_BIOPSY}
    inv, text = inventory(lines, events=[
        act('E1', 'P3', 'examination', 'enteroscope', status_words='was introduced', procedure=entero,
            technique=a('endoscope', 'enteroscope', ['P3'])),
        act('E2', 'P4', 'biopsy', 'Biopsies', status_words='were taken', procedure=entero,
            technique=a('cold_forceps', 'cold forceps', ['P4']), target=tg('', 'jejunum', 'the jejunum', ['P4']))])
    return inv, text, list(codes)


def extent_question(family: str, label: str) -> ClarificationSpec:
    return ClarificationSpec(scope='service', fact='extent', question=EXTENT, family=family,
                             reason=f"CPT Studio's reading of the documented {label} does not establish how far the "
                                    'instrument was advanced or whether the examination was completed.')


class TheServiceAsksItsExtent(SimpleTestCase):
    """D125. c2e53f8e asks the service-scope extent question on every input here but the controls; 1caaf0609 asks none,
    and its coding completeness lists only the no_proposal item."""

    def asks(self, result, family: str, label: str, open_questions: str = '1 open question') -> None:
        """The one service-scope extent question of ``family``, counted among the open questions (``open_questions``:
        the completeness reason, the proposals' own questions included)."""
        with self.subTest(family=family, part='question'):
            self.assertEqual([spec for spec in result.clarifications if spec.fact == 'extent'],
                             [extent_question(family, label)])
        with self.subTest(family=family, part='open questions'):
            self.assertIn(open_questions, result.completeness['reasons'])
            self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d125_a_colonoscopy_with_no_reach_and_no_proposal(self):
        """T04. c2e53f8e: extent [gi.colonoscopy], 'How far was the instrument advanced (the landmark reached)?';
        reasons ['1 documented service or act without a supported proposal', '1 open question']."""
        inv, text, codes = t04_colonoscopy()
        result = run(inv, text, codes)
        self.asks(result, 'gi.colonoscopy', 'colonoscopy')
        self.assertEqual(result.completeness['reasons'],
                         ['1 documented service or act without a supported proposal', '1 open question'])

    def test_d125_a_flexible_sigmoidoscopy_with_no_reach_and_no_proposal(self):
        """T05. c2e53f8e: extent [gi.flex_sig]."""
        inv, text, codes = t05_sigmoidoscopy()
        self.asks(run(inv, text, codes), 'gi.flex_sig', 'flexible sigmoidoscopy')

    def test_d125_its_only_proposal_excluded(self):
        """T06: T04 with 'No biopsies were taken.' and 45380 citing it - excluded on both engines, and an excluded
        proposal asks nothing. c2e53f8e: extent [gi.colonoscopy]."""
        inv, text, codes = t04_colonoscopy(
            act('E3', 'P6', 'biopsy', 'biopsies', status='not_performed', status_words='No biopsies were taken',
                scope=sc('all_of_kind', 'No biopsies', ['P6'])),
            lines={'P6': NO_BIOPSIES}, codes=[('45380', NO_BIOPSIES)])
        result = run(inv, text, codes)
        with self.subTest(part='45380'):
            self.assertEqual(proposal(result, '45380').status, 'excluded')
        self.asks(result, 'gi.colonoscopy', 'colonoscopy')

    def test_d125_an_upper_endoscopy_with_no_reach_and_no_proposal(self):
        """The egd audit's I2. c2e53f8e: extent [gi.egd]; the EGD listed no_proposal on both."""
        inv, text, codes = i2_upper_endoscopy()
        result = run(inv, text, codes)
        self.asks(result, 'gi.egd', 'upper endoscopy')
        self.assertIn(('gi.egd', 'no_proposal', ''), items(result))

    def test_d125_an_enteroscopy_beside_an_upper_endoscopy_code(self):
        """The enteroscopy review's parity note 2: only 43239 is proposed, so no proposal of the enteroscopy asks its
        extent. c2e53f8e: the service question [gi.enteroscopy] and 43239 held [extent]; 1caaf0609 and this build hold
        43239 [performed_status, extent] - unchanged."""
        inv, text, codes = push_enteroscopy()
        result = run(inv, text, codes)
        self.asks(result, 'gi.enteroscopy', 'enteroscopy', '3 open questions')  # 43239's two, and the service's
        p = proposal(result, '43239')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status', 'extent']))

    def test_d125_controls_a_proposal_of_the_family_asks_it_itself(self):
        """S05 (T04 with 45385), I3 (I2 with 43239) and the push enteroscopy with 44361: the code asks the extent (R6),
        so the service does not, on both engines."""
        for name, (inv, text, codes), code in (
                ('S05', t04_colonoscopy(codes=[('45385', SNARE_LINE)]), '45385'),
                ('I3', i2_upper_endoscopy([('43239', 'Biopsies of the gastric antrum were taken with cold forceps.')]),
                 '43239'),
                ('44361', push_enteroscopy([('44361', ENTERO_BIOPSY)]), '44361')):
            result = run(inv, text, codes)
            with self.subTest(case=name):
                self.assertIn('extent', asked(proposal(result, code)))
                self.assertEqual([spec for spec in result.clarifications if spec.fact == 'extent'], [])

    def test_d125_controls_a_stated_reach_or_an_undocumented_session(self):
        """T04 with the cecum stated (its reach verified): no question, on both engines. A colonoscopy stated only as
        planned ('A colonoscopy is planned for next week.' under 'Procedure: Colonoscopy') is no documented session -
        no done event: no question and no item. c2e53f8e reads its 'Procedure: Colonoscopy' heading as a documented
        colonoscopy, lists it no_proposal and asks the extent (recorded in DECISIONS D125 as a difference: the extent of
        a procedure stated not yet done is no genuine question)."""
        inv, text, codes = t04_colonoscopy(lines={'P4': CECUM_DONE}, reach=[creach(completion=a('not_stated'))],
                                           examination=cexam())
        with self.subTest(case='reach'):
            self.assertEqual(service_questions(run(inv, text, codes)), [])
        lines = {**head(), 'P4': 'A colonoscopy is planned for next week.'}
        inv, text = inventory(lines, events=[act('E1', 'P4', 'examination', 'colonoscopy', status='planned',
                                                 status_words='is planned', time=a('future', 'next week', ['P4']))])
        with self.subTest(case='planned'):
            self.assertEqual(service_questions(run(inv, text, [])), [])

    def test_d125_controls_a_stated_incomplete_completion(self):
        """T04 with 'The examination was incomplete because of poor preparation.' (a reach entry naming no landmark,
        its completion 'incomplete': normalize keeps it, D93): the completion is stated, so no question, as on c2e53f8e
        (its completion is not 'unknown')."""
        reach = {'event': 'E1', 'landmark': 'not_stated', 'words': '', 'passages': [],
                 'completion': a('incomplete', 'The examination was incomplete', ['P6'])}
        inv, text, codes = t04_colonoscopy(reach=[reach],
                                           lines={'P6': 'The examination was incomplete because of poor preparation.'})
        exam = events.Reading.of(inv).events['E1']
        with self.subTest(part='fixture'):
            self.assertEqual((exam['completion']['value'], events.verify.usable(exam['completion'])),
                             ('incomplete', True))
        self.assertEqual(service_questions(run(inv, text, codes)), [])

    def test_d125_an_unverified_reach_establishes_no_extent(self):
        """T04's text, Gemini giving the examination a reach to the sigmoid colon whose words stand only in the snare's
        sentence (D36: reach_inferred), or a reach to the cecum whose words its passage does not hold
        (words_unlocated): each is attached unverified, its examination naming its endoscope - a doubt, never a fact
        (D87), so the extent is asked. c2e53f8e reads the same text (T04) and asks it."""
        examination = act('E1', 'P4', 'examination', 'Colonoscopy', status_words='was performed',
                          technique=a('endoscope', 'Colonoscopy', ['P4']))
        inferred = {'event': 'E1', 'landmark': 'sigmoid_colon', 'words': 'sigmoid colon', 'passages': ['P5'],
                    'completion': a('not_stated')}
        for name, reach, landmark, why in (
                ('inferred', inferred, 'sigmoid_colon', 'reach_inferred'),
                ('not located', creach(passage='P4', completion=a('not_stated')), 'cecum', 'words_unlocated')):
            inv, text, codes = t04_colonoscopy(reach=[reach], examination=examination)
            exam = events.Reading.of(inv).events['E1']
            with self.subTest(case=name, part='fixture'):
                self.assertEqual((exam['extent']['value'], exam['extent']['state']), (landmark, 'unverified'))
                self.assertIn(why, exam['extent']['reasons'])
            with self.subTest(case=name):
                self.asks(run(inv, text, codes), 'gi.colonoscopy', 'colonoscopy')

    def test_d125_once_per_family(self):
        """Two colonoscopy examinations, neither stating a reach (an unresolved session): one question."""
        inv, text, codes = t04_colonoscopy(
            act('E3', 'P6', 'examination', 'colonoscopy', status_words='was performed'),
            lines={'P6': 'A second colonoscopy was performed after lavage.'})
        result = run(inv, text, codes)
        with self.subTest(part='fixture'):
            self.assertTrue(coverage.sessions(events.Reading.of(inv))['gi.colonoscopy'].unresolved)
        self.assertEqual([spec.family for spec in result.clarifications if spec.fact == 'extent'], ['gi.colonoscopy'])
