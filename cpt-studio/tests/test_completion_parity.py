"""Layout parity (completion repair, refutation cycle 2, 2026-11-06; HARNESS.md "Completion repair (2026-11-06)").

The owner's rule of 2026-11-06: a cycle-1 patch that cycle 2 refuted is abandoned and the approach changes; the
requirement stays. For the labelled procedure paragraphs (studio/gi/structure.py) and the instrument rule
(studio/gi/detect.py, I12) the approach is layout parity: an under-specified layout reads as its fully specified twin
does, and never more permissively than the installed engine reads that twin.

- A labelled paragraph's heading twin is the same text with each label line "Colonoscopy: <narrative>" written
  "Procedure: Colonoscopy" and the narrative on the line under it (heading_twin).
- An unnamed family's twin (the instrument rule) is the same text with its "Procedure: <narrative>" line written
  "Procedure: Colonoscopy" and the narrative under it (named_twin).

Each check runs the engine as the website reads it (tests.test_harness_engine.run with Corti's picks; the document's own
date where a corpus entry is measured so) on the text and on its twin, and asserts that a code READY on the text is
READY on the twin: (a) over every corpus text with a labelled paragraph candidate, (b) over both refutation cycles'
structure inputs, (c) over the instrument rule's unnamed-family inputs. Where this change releases an input, the
converse is pinned too (it reads exactly as its twin), so a later re-tightening is visible.

One recorded exception, measured on this tree and on the installed release alike: the H2|LABELLED acceptance shape (a
food-bolus EGD paragraph beside a colonoscopy paragraph, corpus text 137) reads 43247 READY, as its corpus entry
requires, while its heading twin holds 43247. The documented-service reader opens no report part under "Procedure: Upper
endoscopy" and drops "the bolus was removed through the mouth" there (two families present and no site in the
sentence: stage 1's U1 binding cause, the installed release's own false hold in the heading layout); the released
paragraph is a report part of its own family and binds it. The checks allow a code READY on the text and not on the
twin only where the input's meaning requires that code READY (the corpus's ``required`` R), and they list exactly the
ones they see, so any other is a failure.

Synthetic documents only."""
from __future__ import annotations

from collections import defaultdict

from django.test import SimpleTestCase

from ops.gi4 import completion
from studio import jobs
from studio.gi import context as gi_context
from studio.gi import detect, structure
from studio.types import NormalizedResponse, to_jsonable
from studio.validation.engine import assess
from tests.test_harness_engine import DAY, REFERENCE, corti, run, span

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
REPORT_HEAD = BANNER + ('Gastroenterology Procedure Report\nDate of service: 2026-10-14\n'
                        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
UNDATED_HEAD = BANNER + 'Gastroenterology Procedure Report\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
EGD = ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus and to the second '
       'portion of the duodenum. Cold forceps biopsies were obtained from the distal esophagus.')
COL = ('Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. A 6 mm polyp in the '
       'sigmoid colon was removed with a cold snare.')
BX = 'Cold forceps biopsies were obtained from the distal esophagus.'
SN = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
COURSE = 'The colonoscope was introduced through the anus and advanced to the cecum.'
IMP = '\nImpression: Sigmoid polyp removed.\n'
BOTH_IMP = '\nImpression: Esophageal biopsies; sigmoid polyp removed.\n'
SN_ONLY = [('45385', SN)]
BOTH = [('43239', BX), ('45385', SN)]

# The H2|LABELLED acceptance shape (corpus text 137, entries H2|LABELLED-43239/-45385/-43247, each required READY).
H2_IND = ('Indications: Food impaction after a meal the evening before, intermittent dysphagia, and surveillance after '
          'prior adenomas.')
H2_BODY = ('Risks and benefits of upper endoscopy with possible foreign-body removal and colonoscopy with possible '
           'intervention were discussed.\n'
           'Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. A large impacted '
           'meat bolus was found at 34 cm.\n'
           'A retrieval net was passed through the working channel and the bolus was removed through the mouth.\n'
           'Cold forceps biopsies were obtained from the mid esophagus.\n'
           'The stomach and the second portion of the duodenum were then examined and were normal.\n'
           'Colonoscopy: A colonoscope was introduced through the anus and advanced to the cecum.\n'
           'A 9 mm sessile polyp in the transverse colon was removed with a cold snare.\n')
H2_TAIL = 'Impression: Food impaction cleared; esophageal biopsies; transverse colon polyp removed.\nPlan: Await pathology.\n'
H2 = REPORT_HEAD + H2_IND + '\n' + H2_BODY + H2_TAIL
H2_PICKS = [('43239', 'Cold forceps biopsies were obtained from the mid esophagus.'),
            ('45385', 'A 9 mm sessile polyp in the transverse colon was removed with a cold snare.'),
            ('43247', 'A retrieval net was passed through the working channel and the bolus was removed through the mouth.')]
H2_CODES = frozenset(code for code, _ in H2_PICKS)
BOLUS = '43247'  # the recorded exception (see the module docstring)


def _labels(text: str) -> list:
    """(line start, label span, narrative start) of each labelled paragraph candidate of ``text``, released or not."""
    out = []
    for paragraph, _ in structure.decisions(text):
        body = paragraph.label.end
        while body < len(text) and text[body] in ' \t*_#':
            body += 1
        out.append((paragraph.start, paragraph.label, body))
    return out


def heading_twin(text: str) -> str:
    """``text`` with each labelled paragraph candidate's label line "Name: <narrative>" written "Procedure: Name" and the
    narrative on the line under it."""
    out = text
    for start, label, body in reversed(_labels(text)):
        out = out[:start] + 'Procedure: ' + label.text[:-1].strip() + '\n' + out[body:]
    return out


def twin_quote(text: str, quote: str) -> str:
    """A quote of ``text`` as its heading twin writes it: a label's "Name: " inside the quote becomes "Name" and a line
    break (the twin's heading content)."""
    for _, label, body in _labels(text):
        quote = quote.replace(text[label.start:body], label.text[:-1].strip() + '\n')
    return quote


def named_twin(text: str, name: str) -> str:
    """The instrument rule's twin: the text's one "Procedure: <narrative>" line written "Procedure: <name>" and the
    narrative under it."""
    assert text.count('\nProcedure: ') == 1, text
    return text.replace('\nProcedure: ', f'\nProcedure: {name}\n')


def outcome(text: str, picks, *, dated: bool = False, member_day: bool = False) -> dict:
    """{code: (bucket, status)} of Corti's ``picks`` read on ``text`` (alternatives left out): through
    tests.test_harness_engine.run, or for ``dated`` on the document's own date of service (as ops.gi4.completion measures
    a dated entry), or for ``member_day`` on the member-supplied date of service (an undated document)."""
    codes = corti(*[(code, span(text, quote)) for code, quote in picks])
    if not (dated or member_day):
        result = run(text, codes)
    else:
        facts = gi_context.extract_context(text)
        if member_day:
            facts, day = gi_context.merge_user_values(facts, {'service_date': DAY.isoformat()}), DAY
        else:
            day = jobs._service_date_of(to_jsonable(facts))
        result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                        normalized=NormalizedResponse('corti', 'test@1', tuple(codes)), reference=REFERENCE,
                        service_date=day, provider_status='succeeded', participants=())
    return {p.code: (p.bucket, p.status) for p in result.proposals if p.bucket != 'alternative'}


def ready(reading: dict) -> set:
    return {code for code, state in reading.items() if state == ('selected', 'ready')}


def _corpus_picks(entry: dict) -> list:
    """An entry's Corti picks: its code and quote with the primary codes beside it, or a multi entry's primary codes, or
    an admission entry's base code."""
    if entry['kind'] in ('both', 'dated'):
        return [tuple(row) for row in entry.get('primary', [])] + [(entry['code'], entry['quote'])]
    if entry['kind'] in ('multi', 'dated_multi'):
        return [tuple(row[:2]) for row in entry['primary']]
    return [(entry['base'], entry['base_quote'])]


def _required_ready(entry: dict) -> set:
    required = entry['required']
    if isinstance(required, dict):
        return {code for code, value in required.items() if value == 'R'}
    return {entry['code']} if required == 'R' and entry.get('code') else set()


class CorpusParityTests(SimpleTestCase):
    """(a) Every corpus text for which structure.decisions finds a labelled paragraph candidate: each entry's Corti picks
    on the text and on its heading twin. Cycle 2, structure: every false READY of both cycles had a heading twin the
    installed release reads READY; this is the check that the release never reads more than its twin."""

    # Measured on this tree, 2026-11-06: 46 of the 548 corpus texts have a labelled paragraph candidate, 13 of them a
    # released one (52 entries compared). A reader change that stops finding or releasing labelled paragraphs fails here.
    TEXTS_WITH_A_CANDIDATE = 46
    TEXTS_WITH_A_RELEASE = 13

    def test_a_code_ready_on_the_labelled_text_is_ready_on_its_heading_twin(self):
        """Cycle 2, structure (S1 to S4 and cycle 1's C1-S1 to C1-S5, each READY only as its heading twin is): over the
        whole corpus, no labelled text reads a code READY that its heading twin does not, but the recorded bolus."""
        fixture = completion.load()
        by_text = defaultdict(list)
        for entry in fixture['entries']:
            by_text[entry['text']].append(entry)
        compared, released, extras = 0, 0, set()
        for index, text in enumerate(fixture['texts']):
            decisions = structure.decisions(text)
            if not decisions:
                continue
            compared += 1
            released += any(not why for _, why in decisions)
            twin = heading_twin(text)
            self.assertEqual(structure.released(twin), (), index)
            for entry in by_text[index]:
                picks = _corpus_picks(entry)
                dated = entry['kind'].startswith('dated')
                with self.subTest(entry['id']):
                    here = ready(outcome(text, picks, dated=dated))
                    there = ready(outcome(twin, [(c, twin_quote(text, q)) for c, q in picks], dated=dated))
                    self.assertLessEqual(here - there, _required_ready(entry),
                                         f'READY on the labelled text, not on its heading twin: {sorted(here - there)}')
                    extras |= {(entry['id'], code) for code in here - there}
        self.assertGreaterEqual(compared, self.TEXTS_WITH_A_CANDIDATE)
        self.assertGreaterEqual(released, self.TEXTS_WITH_A_RELEASE)
        self.assertEqual(extras, {('H2|LABELLED-43247', BOLUS)})  # the recorded exception, and no other


def _structure_inputs() -> list:
    """(label, text, picks, required READY codes, member_day) for both refutation cycles' structure inputs and the
    sentences the owner session found itself. ``required`` is what the input's meaning requires READY (today's single
    report); an input the findings showed to be another occasion's or another person's account requires nothing."""
    cases = []

    def add(label, text, picks, required=(), member_day=False):
        cases.append((label, text, picks, frozenset(required), member_day))

    # cycle 1, structure (C1-S1 .. C1-S8)
    for ind in ('Her colonoscopy in 2022 is reprinted here for reference.',
                'Her colonoscopy in 2022 is carried forward for reference.',
                'Her 2022 colonoscopy is shown for comparison.'):
        add(f'C1-S1 {ind}', REPORT_HEAD + f'Indications: Surveillance. {ind}\n' + COL + IMP, [('45385', SN), ('45378', COURSE)])
    add('C1-S2', REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\n' + EGD
        + ' The paragraph that follows belongs to her sister.\n' + COL + BOTH_IMP, BOTH)
    add('C1-S3', REPORT_HEAD + 'Indications: Dysphagia.\n' + EGD + '\nImpression: Esophageal biopsies.\nPlan: Await '
        'pathology.\n\nPrior Colonoscopy Report 2022\nIndications: Surveillance.\n' + COL + IMP, BOTH)
    add('C1-S4', REPORT_HEAD + 'Indications: Dysphagia. The next paragraph is from her 2023 visit at another hospital.\n'
        + EGD + '\nImpression: Esophageal biopsies.\n', [('43239', BX)])
    add('C1-S5a', REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL + ' None of this was done today.' + IMP,
        SN_ONLY)
    add('C1-S5b', REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL
        + '\nImpression: Sigmoid polyp removed in 2022.\n', SN_ONLY)
    add('C1-S6', BANNER + 'Colonoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
        '(fictional)\nIndications: Surveillance colonoscopy for personal history of adenomatous polyps.\n' + COL + IMP
        + 'Plan: Await pathology.\n', SN_ONLY, required={'45385'})
    add('C1-S7', REPORT_HEAD + 'Indications: Surveillance after adenomas.\nColonoscopy: ' + COURSE
        + '\nWithdrawal time: 8 minutes.\n' + SN + IMP, SN_ONLY, required={'45385'})
    s8_snare = 'A 5 mm polyp in the transverse colon was removed with a cold snare.'
    add('C1-S8', UNDATED_HEAD + 'Indications: Surveillance; history of adenomatous polyps on colonoscopy in 2022.\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. ' + s8_snare + '\nImpression: Transverse polyp removed.\n',
        [('45385', s8_snare)], required={'45385'}, member_day=True)
    # cycle 2, structure S1 (an appended prior report under its own heading) and its variants
    add('S1', REPORT_HEAD + 'Indications: Dysphagia.\n' + EGD + '\nOutside records (2022):\nIndications: Surveillance.\n'
        + COL + '\nImpression: Esophageal biopsies obtained today.\nPlan: Await pathology.\n', BOTH)
    for heading in ('Prior report:', 'Colonoscopy report from 2022:'):
        add(f'S1 {heading}', REPORT_HEAD + 'Indications: Dysphagia.\n' + EGD + f'\n{heading}\nIndications: '
            'Surveillance.\n' + COL + IMP, BOTH)
    add('S1 sister reproduced', REPORT_HEAD + "History: Her sister's colonoscopy is reproduced after the indications.\n"
        'Indications: Surveillance after adenomas.\n' + COL + IMP, SN_ONLY)
    add('S1 note below', REPORT_HEAD + 'Note: The colonoscopy below was performed in 2022 at another hospital.\n'
        'Indications: Surveillance after adenomas.\n' + COL + IMP, SN_ONLY)
    # S2 (a denial or a dating in the impression; a denial in the paragraph)
    for imp in ('None of the above was performed today.', 'Sigmoid polyp removed. Wrong chart: this belongs to another '
                'patient.', 'Sigmoid polyp removed two years ago.', 'Sigmoid polyp removed at an outside hospital.',
                'Sigmoid polyp previously removed.', 'Sigmoid polyp snared in 2022.', 'Sigmoid polyp removed in March.'):
        add(f'S2 {imp}', REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL + f'\nImpression: {imp}\n',
            SN_ONLY)
    for tail in (' This did not happen today.', ' This never happened.', ' Not done today.'):
        add(f'S2{tail}', REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL + tail + IMP, SN_ONLY)
    # S3 (a dated occasion introducing the narrative)
    for ind in ('Her sister had a colonoscopy in 2022 with these findings.', 'She had a colonoscopy in 2022 with these '
                'findings.', 'Her colonoscopy in 2022 went like this.'):
        add(f'S3 {ind}', REPORT_HEAD + f'Indications: Surveillance. {ind}\n' + COL + IMP, SN_ONLY)
    # S4 (a pro-form or article-led announcement)
    add('S4', REPORT_HEAD + 'Indications: Surveillance after adenomas. The next one was done in 2022.\n' + COL + IMP,
        SN_ONLY)
    add('S4 tail', REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\n' + EGD
        + ' The next one was not done today.\n' + COL + BOTH_IMP, BOTH)
    add("S4 sister's", REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\n' + EGD
        + " The next one is her sister's.\n" + COL + BOTH_IMP, BOTH)
    add('S4 account', REPORT_HEAD + 'Indications: Surveillance after adenomas. A 2022 account is included.\n' + COL + IMP,
        SN_ONLY)
    # S5 (an early assessment or diagnosis line): today's single report, required READY
    for line in ('Pre-procedure assessment: ASA class II.', 'Diagnosis: Personal history of colon polyps.',
                 'Pre-procedure diagnosis: Surveillance after adenomas.\nPost-procedure diagnosis: Sigmoid polyp.'):
        add(f'S5 {line}', REPORT_HEAD + line + '\nIndications: Surveillance after adenomas.\n' + COL + IMP, SN_ONLY,
            required={'45385'})
    add('S5 H2', REPORT_HEAD + 'Pre-procedure assessment: ASA class II; Mallampati class 2.\n' + H2_IND + '\n' + H2_BODY
        + H2_TAIL, H2_PICKS, required=H2_CODES)
    # S6 (ordinary indications and narratives the cycle-1 readers held): required READY
    add('S6', REPORT_HEAD + H2_IND + ' This is a 58-year-old man referred from an outside hospital.\n' + H2_BODY + H2_TAIL,
        H2_PICKS, required=H2_CODES)
    for old, new in ((H2_IND, H2_IND + ' Family history is positive for colon cancer in his father, diagnosed in 2010.'),
                     ('intermittent dysphagia', 'intermittent dysphagia with food sticking beneath the sternum'),
                     ('were then examined', 'were next examined'),
                     ('were then examined and', 'were then examined for completeness and')):
        assert H2.count(old) == 1, old
        add(f'S6 {new[-40:]}', H2.replace(old, new), H2_PICKS, required=H2_CODES)
    for ind in ('Iron deficiency anemia. Hemoglobin is 8.9 g/dL, down from 12.1 in 2024.',
                'Anemia; outside CT is concerning for colitis.',
                'Screening, for the following reasons: average risk and age 50.'):
        add(f'S6 {ind}', REPORT_HEAD + f'Indications: {ind}\n' + COL + IMP, SN_ONLY, required={'45385'})
    add('S6 for comparison', REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\n' + EGD
        + ' Random biopsies of the normal-appearing antrum were taken for comparison.\n' + COL + BOTH_IMP, BOTH,
        required={'43239', '45385'})
    # S7 (ordinary dated history): required READY
    for ind in ('Surveillance. History of adenomatous polyps on colonoscopy in 2022; she is now due for surveillance.',
                'Surveillance; adenomas were removed at colonoscopy in 2022 and three-year surveillance is recommended.'):
        add(f'S7 {ind}', REPORT_HEAD + f'Indications: {ind}\n' + COL + IMP, SN_ONLY, required={'45385'})
    add('S7 scar', REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL + '\nImpression: Sigmoid polyp '
        'removed. Post-polypectomy scar in the ascending colon from 2022, without residual.\n', SN_ONLY, required={'45385'})
    add('S7 H2 scar', H2.replace('transverse colon polyp removed.', 'transverse colon polyp removed; post-polypectomy scar '
        'from 2022 in the ascending colon.'), H2_PICKS, required=H2_CODES)
    # S8 (a generic scope's frame of today's steps), and its named control
    for scope in ('the scope', 'the colonoscope'):
        add(f'S8 {scope}', REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\n' + EGD
            + f'\nColonoscopy: After the upper endoscopy, {scope} was introduced through the anus and advanced to the '
            'cecum. ' + SN + BOTH_IMP, BOTH, required={'43239'})
    # the owner session's own sentences
    for ind in ('This is a 60-year-old woman referred from an outside GI clinic for surveillance.',
                'Screening, for the following reasons: average risk and age 50.'):
        add(f'self {ind}', REPORT_HEAD + f'Indications: {ind}\n' + COL + IMP, SN_ONLY, required={'45385'})
    return cases


STRUCTURE_INPUTS = _structure_inputs()
CASE = {label: (text, picks, member_day) for label, text, picks, _, member_day in STRUCTURE_INPUTS}
# where the heading twin holds the bolus the released paragraph binds (the recorded exception)
H2_SHAPED = frozenset(label for label, _, picks, _, _ in STRUCTURE_INPUTS if picks == H2_PICKS)


def _pair(label: str) -> tuple:
    text, picks, member_day = CASE[label]
    twin = heading_twin(text)
    return (outcome(text, picks, member_day=member_day),
            outcome(twin, [(code, twin_quote(text, quote)) for code, quote in picks], member_day=member_day))


class StructureInputParityTests(SimpleTestCase):
    """(b) Both refutation cycles' structure inputs, written inline: the labelled text never reads a code READY that its
    heading twin does not, but where the input's meaning requires it (the recorded bolus exception)."""

    def test_every_structure_input_reads_no_more_than_its_heading_twin(self):
        """Cycle 1, structure C1-S1 to C1-S8; cycle 2, structure S1 to S8 with the variants their lenses listed; the
        owner session's own sentences."""
        extras = set()
        for label, text, picks, required, _ in STRUCTURE_INPUTS:
            with self.subTest(label):
                self.assertNotEqual(structure.decisions(text), ())  # a labelled paragraph candidate is compared
                here, there = (ready(reading) for reading in _pair(label))
                self.assertLessEqual(here - there, required, f'READY on the labelled text only: {sorted(here - there)}')
                extras |= {(label, code) for code in here - there}
        self.assertEqual(extras, {(label, BOLUS) for label in H2_SHAPED})

    def test_the_cycle_findings_read_exactly_as_their_heading_twins(self):
        """Cycle 1, structure C1-S1 to C1-S4, and cycle 2, structure S1 to S4: the base's own misreading of the heading
        form, carried into the labelled form and no further - each reads exactly as its twin (released, READY)."""
        for label in ('C1-S1 Her colonoscopy in 2022 is reprinted here for reference.', 'C1-S2', 'C1-S3', 'C1-S4', 'S1',
                      'S2 None of the above was performed today.',
                      'S3 Her sister had a colonoscopy in 2022 with these findings.', 'S4'):
            with self.subTest(label):
                here, there = _pair(label)
                self.assertEqual(here, there)

    def test_the_cycle_2_false_holds_are_released(self):
        """Cycle 2, structure S5 (an early "Pre-procedure assessment:", "Diagnosis:" or "Post-procedure diagnosis:"
        line), S6 (each one-line edit of the acceptance shape, and the minimal reports), S7 (a dated history, a scar from
        2022) and the owner session's two sentences ("This is a 60-year-old woman referred from an outside GI clinic for
        surveillance.", "Screening, for the following reasons: average risk and age 50."): today's single report,
        every pick READY, and the minimal ones read exactly as their twins."""
        released = [label for label, *_ in STRUCTURE_INPUTS if label.startswith(('S5', 'S6', 'S7', 'self'))]
        self.assertEqual(len(released), 19)
        for label in released:
            text, picks, member_day = CASE[label]
            with self.subTest(label):
                here, there = _pair(label)
                self.assertEqual(ready(here), {code for code, _ in picks})
                self.assertEqual([why for _, why in structure.decisions(text)], [''] * len(structure.decisions(text)))
                if label not in H2_SHAPED:
                    self.assertEqual(here, there)

    def test_a_generic_scopes_frame_reads_as_the_named_scopes(self):
        """Cycle 2, structure S8: "After the upper endoscopy, the scope was introduced ..." frames today's sequence as
        "... the colonoscope ..." does - both paragraphs released, and the text reads as its heading twin and as the
        named control."""
        generic, named = CASE['S8 the scope'][0], CASE['S8 the colonoscope'][0]
        self.assertEqual([why for _, why in structure.decisions(generic)], ['', ''])
        self.assertEqual(_pair('S8 the scope')[0], _pair('S8 the scope')[1])
        self.assertEqual(_pair('S8 the scope')[0], _pair('S8 the colonoscope')[0])
        self.assertIn('43239', ready(_pair('S8 the scope')[0]))
        self.assertNotEqual(generic, named)

    def test_the_kept_rules_still_hold_more_than_the_twin(self):
        """Cycle 1, structure C1-S5 (N1's negative quantifier, kept: "None of this was done today." inside the paragraph
        holds it) and C1-S7 (a report field line inside the narrative, cycle 1's recorded residual and the base's hold:
        "Withdrawal time:" ends the paragraph, so the snare sentence after it stays in the Indications): the labelled
        form is held where its twin is READY - stricter than the twin, the safe side."""
        for label in ('C1-S5a', 'C1-S7'):
            with self.subTest(label):
                here, there = _pair(label)
                self.assertEqual(ready(here), set())
                self.assertEqual(ready(there), {'45385'})
        self.assertTrue(structure.decisions(CASE['C1-S5a'][0])[0][1].startswith('N1'))
        text = CASE['C1-S7'][0]
        (paragraph,) = structure.released(text)
        self.assertTrue(paragraph.start < text.index(COURSE) < paragraph.end <= text.index(SN))


# --- (c) the instrument rule: an unnamed family read as the twin naming it on its procedure heading ------------------
COURSE_COL = 'The colonoscope was advanced to the cecum'
COURSE_UP = 'The gastroscope was advanced to the second portion of the duodenum'


def _head(title: str) -> str:
    return BANNER + f'{title}\nDate of service: 2026-10-14\n'


def _instrument_inputs() -> list:
    """(label, unnamed text, family name, picks) for cycle 1's outcome F1/F2 inputs and cycle 2's O1, O3, O4, O7 with
    the variants their lenses listed."""
    cases = []

    def add(label, ind, procedure, after, pick, title='Colonoscopy', name='Colonoscopy'):
        cases.append((label, _head(title) + ind + 'Procedure: ' + procedure + '\n' + after, name, [pick]))

    col = ('45378', COURSE_COL)
    up = ('43235', COURSE_UP)
    add('F1 cancelled', 'Indications: Surveillance.\n', COURSE_COL + '.', 'Status: Cancelled - inadequate bowel '
        'preparation.\n', col)
    add('F2 prior occasion', 'Indications: Screening.\n', COURSE_COL + ' on a prior occasion.', '',
        ('45378', COURSE_COL + ' on a prior occasion'))
    add('F2 states that', 'Indications: Screening.\n', 'The patient states that the colonoscope was advanced to the '
        'cecum.', '', ('45378', 'the colonoscope was advanced to the cecum'))
    add('F2 presumably', 'Indications: Screening.\n', 'Presumably, the colonoscope was advanced to the cecum.', '',
        ('45378', 'the colonoscope was advanced to the cecum'))
    for status in ('Abandoned - inadequate bowel preparation.', 'Refused by the patient.', 'Not carried out - inadequate '
                   'bowel preparation.', 'Withdrawn by the patient before sedation.'):
        add(f'O1 status {status}', 'Indications: Surveillance.\n', COURSE_COL + '.', f'Status: {status}\n', col)
    add('O1 abandoned in the body', 'Indications: Surveillance.\n', COURSE_COL + '. The procedure was abandoned because '
        'of poor preparation.', '', col)
    add('O1 never carried out', 'Indications: Surveillance.\n', COURSE_COL + '. The examination itself was never carried '
        'out.', '', col)
    add('O1 refused in the indications', 'Indications: Surveillance. The patient refused the procedure.\n',
        COURSE_COL + '.', '', col)
    add('O1 EGD abandoned', 'Indications: Dysphagia.\n', COURSE_UP + '.', 'Status: Abandoned - the patient could not '
        'tolerate sedation.\n', up, title='EGD', name='EGD')
    for lead in ('Perhaps the', 'Maybe the', 'Supposedly, the', 'I believe the', 'It seems the', 'I assume the',
                 "The patient's husband says the"):
        add(f'O3 {lead}', 'Indications: Screening.\n', f'{lead} colonoscope was advanced to the cecum.', '',
            ('45378', 'colonoscope was advanced to the cecum'))
    add("O3 partner's note", 'Indications: Screening.\n', "My partner's note says the colonoscope was advanced to the "
        'cecum.', '', ('45378', 'the colonoscope was advanced to the cecum'))
    add('O3 recollection', 'Indications: Screening.\n', "The patient's recollection is that the colonoscope was advanced "
        'to the cecum.', '', ('45378', 'the colonoscope was advanced to the cecum'))
    add('O3 EGD perhaps', 'Indications: Dysphagia.\n', 'Perhaps the gastroscope was advanced to the second portion of the '
        'duodenum.', '', ('43235', 'the gastroscope was advanced to the second portion of the duodenum'), title='EGD',
        name='EGD')
    add('O4 three years ago', 'Indications: Screening.\n', COURSE_COL + '. That was at her examination three years ago.',
        '', col)
    add('O4 the same day as her upper endoscopy', 'Indications: Screening.\n', COURSE_COL + '. This was done on '
        '2023-03-02, the same day as her upper endoscopy.', '', col)
    add('O4 control dated', 'Indications: Screening.\n', COURSE_COL + '. This was done on 2023-03-02.', '', col)
    add('O7 aspirin', 'Indications: Screening. Aspirin was discontinued five days before the procedure.\n',
        COURSE_COL + '.', '', col)
    for sentence in ('Retroflexion of the scope in the rectum was not performed.', 'Retroflexion in the rectum was not '
                     'performed.', 'Biopsies were deferred to a later procedure.', 'Intubation of the terminal ileum was '
                     'not attempted.'):
        add(f'O7 {sentence}', 'Indications: Screening.\n', COURSE_COL + '. ' + sentence, '', col)
    add('O7 previous examination aborted', 'Indications: Screening; her previous examination was aborted because of poor '
        'preparation.\n', COURSE_COL + '.', '', col)
    add('O7 clopidogrel', 'Indications: Screening.\n', COURSE_COL + '.', 'Plan: Resume diet; clopidogrel remains '
        'discontinued.\n', col)
    add('O7 EGD omeprazole', 'Indications: Dysphagia. Omeprazole was discontinued two weeks before the procedure.\n',
        COURSE_UP + '.', '', up, title='EGD', name='EGD')
    add('O7 per rectum', 'Indications: Screening.\n', 'The colonoscope was inserted per rectum and advanced to the cecum.',
        '', ('45378', 'The colonoscope was inserted per rectum and advanced to the cecum'))
    for tail in (', as documented by photographs of the appendiceal orifice.', ' after abdominal pressure was applied.',
                 ' and the previous polypectomy site in the ascending colon was examined.'):
        add(f'O7{tail[:30]}', 'Indications: Screening.\n', COURSE_COL + tail, '', col)
    return cases


INSTRUMENT_INPUTS = _instrument_inputs()


def _instrument_pair(label: str) -> tuple:
    _, text, name, picks = next(case for case in INSTRUMENT_INPUTS if case[0] == label)
    return outcome(text, picks), outcome(named_twin(text, name), picks)


class InstrumentRuleParityTests(SimpleTestCase):
    """(c) The instrument rule (detect.py I12): the instrument's course names its family as a procedure heading names it,
    and an unnamed family is read no more permissively than that named twin."""

    def test_every_unnamed_input_reads_no_more_than_its_named_twin(self):
        """Cycle 1, outcome F1 and F2; cycle 2, outcome O1, O3, O4 and O7 with their variants."""
        for label, text, name, picks in INSTRUMENT_INPUTS:
            with self.subTest(label):
                here, there = (ready(reading) for reading in _instrument_pair(label))
                self.assertLessEqual(here, there)

    def test_the_findings_read_exactly_as_their_named_twins(self):
        """Cycle 2, outcome O1 (a status of "Abandoned", "Refused", "Not carried out" ...), O3 (a hedged or second-hand
        course) and O4 (a course a later sentence dates), and cycle 1's F1 and F2: each reads exactly as the twin that
        names the family on its procedure heading - held where the twin holds it ("Cancelled", "Refused by the
        patient", "The patient refused the procedure."), and READY where the installed engine reads the twin READY."""
        exact = [label for label, *_ in INSTRUMENT_INPUTS if label.startswith(('F1', 'F2', 'O1', 'O3', 'O4'))
                 and label != 'O4 control dated']
        self.assertEqual(len(exact), 24)
        for label in exact:
            with self.subTest(label):
                here, there = _instrument_pair(label)
                self.assertEqual(here, there)
        for label in ('F1 cancelled', 'O1 status Refused by the patient.', 'O1 refused in the indications',
                      'O1 status Not carried out - inadequate bowel preparation.'):
            with self.subTest(label):
                self.assertEqual(ready(_instrument_pair(label)[0]), set())

    def test_the_ordinary_sentences_no_longer_hold_the_examination(self):
        """Cycle 2, outcome O7: a drug discontinued before the procedure, a sub-act's denial naming the scope, a course
        "per rectum", "as documented by photographs", "after abdominal pressure was applied" or past "the previous
        polypectomy site" - today's plain account of an examination that took place: READY, as its twin."""
        for label, *_ in INSTRUMENT_INPUTS:
            if not label.startswith('O7'):
                continue
            with self.subTest(label):
                here, there = _instrument_pair(label)
                self.assertEqual(ready(here), {'45378'} if 'EGD' not in label else {'43235'})
                self.assertEqual(here, there)

    def test_a_course_dated_by_a_later_sentence_stays_stricter_than_the_twin(self):
        """Cycle 2, outcome O4's control: "This was done on 2023-03-02." after the course - I5 keeps the base reading
        (held) where the named twin is READY: stricter, the safe side."""
        here, there = _instrument_pair('O4 control dated')
        self.assertEqual((ready(here), ready(there)), (set(), {'45378'}))

    def test_the_heading_twin_reading_is_routings_own_reading_of_the_named_heading(self):
        """I12 against routing itself: for every input, the instrument's heading twin is qualified exactly where routing,
        reading the named twin, qualifies the family's name on the procedure heading ("uncertain: section silent: the
        text after it (...) qualifies it"). I12 reads routing's sentences with routing's predicates; this catches the
        two drifting apart."""
        for label, text, name, _ in INSTRUMENT_INPUTS:
            with self.subTest(label):
                an, _ = detect._analysis(text, DAY)
                candidates = detect._instrument_candidates(an)
                self.assertTrue(candidates)
                mine = {detect._heading_twin_qualified(an, m) for m in candidates}
                self.assertEqual(len(mine), 1)
                twin = named_twin(text, name)
                heading = [m for f in detect.route(twin, DAY).findings for m in f.mentions
                           if m.section == 'procedure' and m.span.text == name]
                self.assertEqual(len(heading), 1, heading)
                routing_qualifies = any(cue.startswith(detect.SILENT_SECTION_PREFIX + ' the text after it')
                                        for cue in heading[0].cues)
                self.assertEqual(mine.pop(), routing_qualifies)
