"""DECISIONS D142 (round 5c; the round-5b review of D115-D119, review_egd.json problems 0, 1, 2 and 4, and the listing
half of the committed eus2 review's problems 1 and 2), SYNTHETIC, each built from its source's own input with the round-5
EGD builders (tests/test_interpretation_r5_egd.py: a document, a Gemini answer written to prompt.py's contract, the
proposer's citations replayed) and its controls:
- (1) problem 0, critical: an event whose OWN kind is the bleeding control (Gemini's bleeding_control) named only by the
  adjective - "Hemostatic cautery was applied to the ulcer base." beside a clean-based ulcer (RF1), the hemostatic
  injection filed as bleeding_control (variant a), the same cautery in a colonoscopy (variant b) - is a bleeding control
  in DOUBT, read by the same five attribute words as D115's clip and injection: 43255 (45382) is held, never READY.
- (2) problem 1: coverage.in_doubt_questions asks once per (family, fact); an act no proposed code accounts for (its
  question decides a missing code) is asked before an act a proposed code already holds on - RF11's biopsy "done at this
  encounter?" is asked again, beside the clip in doubt 43255 holds on. DECISIONS D149 (round 5d) replaced that order: it
  reads the events the proposed codes read or hold on, never a profile, and no record ties 43255 to RF11's clip, so the
  reading's order asks the clip's question (the two tests below CHANGED with D149; its pins are in
  tests/test_interpretation_r5d_egd.py).
- (3) problem 2 and the eus2 listing: reconcile lists as not covered a done act of a kind its session's family does not
  list among its acts, when the act is reportable and no proposed code covers it - the EGD's stent removal and stent
  exchange (RF5) and the EUS-guided gastroenterostomy stent beside 43259 - never an act a proposed code covers, D117's
  umbrella or D115's bleeding control in doubt.
- (4) problem 4: the D119 H1 pin asserts 43246's own state (tests/test_interpretation_r5_egd.py, changed there).
CASES (the round-5 module's) holds every input, so the installed release (c2e53f8e) can be run on the very same texts and
citations. Nothing is sent."""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, mapping, overlay
from studio.types import to_jsonable
from tests import test_interpretation_r5_egd as e5
from tests.test_interpretation_events import asked, proposal

at, tgt, event, lesion, report, case = e5.at, e5.tgt, e5.event, e5.lesion, e5.report, e5.case
built, assessed, reviewed, items, service_facts = e5.built, e5.assessed, e5.reviewed, e5.items, e5.service_facts
held, held_base, ready = e5.held, e5.held_base, e5.ready
EGD, ADV, NORMAL, CLEAN_ULCER, ULCER = e5.EGD, e5.ADV, e5.NORMAL, e5.CLEAN_ULCER, e5.ULCER
NAMES: list = []  # the inputs of this module, in order (dumped for the installed release's runner)


def mine(name: str) -> str:
    NAMES.append(name)
    return name


# --- (1) problem 0: the bleeding_control kind named only by the adjective -------------------------------------------------

# RF1 (review_egd.json problem 0): the attested FRESH-2 filing of 'hemostatic cautery' (note8, C2MEM-023/029/031/032,
# N8-CF*: kind bleeding_control, words 'Hemostatic cautery', technique electrocautery, purpose hemostasis worded
# 'Hemostatic'), here stated done on a clean-based ulcer
CAUTERY = 'Hemostatic cautery was applied to the ulcer base.'


def cautery(procedure=EGD, landmark: str = 'gastric_antrum') -> dict:
    return event('E2', procedure, at('bleeding_control', 'Hemostatic cautery', ['P7']),
                 status=at('performed', 'was applied', ['P7']), technique=at('electrocautery', 'cautery', ['P7']),
                 target=tgt('L1', landmark, 'the ulcer base', ['P7']), purpose=at('hemostasis', 'Hemostatic', ['P7']))


RF1 = mine(case('d142_rf1_cautery_43255_43235', report(P5=ADV, P6=CLEAN_ULCER, P7=CAUTERY, P8=NORMAL),
                [e5.examination(), cautery()], [('43255', (CAUTERY,)), ('43235', (ADV,))], lesions=[ULCER]))
RF1_ALONE = mine(case('d142_rf1_cautery_43255_alone', report(P5=ADV, P6=CLEAN_ULCER, P7=CAUTERY, P8=NORMAL),
                      [e5.examination(), cautery()], [('43255', (CAUTERY,))], lesions=[ULCER]))
# variant (a): gap D's own hemostatic injection, Gemini filing it as kind bleeding_control with technique injection (the
# filing FRESH-2 attests once for 'injection for bleeding', C2MEM-031)
INJ = e5.INJECTION_LINE
INJECTION_AS_CONTROL = event('E2', EGD, at('bleeding_control', 'injection', ['P7']),
                             status=at('performed', 'was given', ['P7']), technique=at('injection', 'injection', ['P7']),
                             target=tgt('L1', 'gastric_antrum', 'the ulcer base', ['P7']),
                             purpose=at('hemostasis', 'hemostatic', ['P7']))
RF_A = mine(case('d142_variant_a_injection_filed_as_bleeding_control', report(P5=ADV, P6=CLEAN_ULCER, P7=INJ, P8=NORMAL),
                 [e5.examination(), INJECTION_AS_CONTROL],
                 [('43255', (INJ,)), ('43236', (INJ,)), ('43243', (INJ,)), ('43235', (ADV,))], lesions=[ULCER]))
# variant (b): RF1's act in a colonoscopy (45382)
COLON = at('colonoscopy', 'COLONOSCOPY', ['P2'])
CECUM = 'The colonoscope was advanced to the cecum.'
COLON_ULCER = 'A 6 mm clean-based ulcer was seen in the ascending colon.'
COLON_EXAM = event('E1', COLON, at('examination', 'The colonoscope was advanced', ['P5']),
                   technique=at('endoscope', 'colonoscope', ['P5']), status=at('performed', 'was advanced', ['P5']))
RF_B = mine(case('d142_variant_b_colonoscopy_cautery_45382', report('COLONOSCOPY REPORT', P5=CECUM, P6=COLON_ULCER,
                                                                   P7=CAUTERY, P8='No other lesion was seen.'),
                 [COLON_EXAM, cautery(COLON, 'ascending_colon')], [('45382', (CAUTERY,)), ('45378', (CECUM,))],
                 lesions=[lesion('L1', '6 mm clean-based ulcer', 'ascending_colon', 'ascending colon', '6 mm',
                                 ['P6', 'P7'])],
                 reach=('E1', 'cecum', 'cecum', 'P5')))
# control: the bleeding_control kind whose own words state the bleeding it treats keeps the bleeding control
OOZING_VESSEL = 'A 12 mm ulcer with an oozing visible vessel was seen in the gastric antrum.'
CAUTERY_OOZING = 'Hemostatic cautery was applied to the oozing vessel.'
RF_OWN = mine(case('d142_control_cautery_of_the_oozing_vessel', report(P5=ADV, P6=OOZING_VESSEL, P7=CAUTERY_OOZING,
                                                                      P8=NORMAL),
                   [e5.examination(),
                    event('E2', EGD, at('bleeding_control', 'Hemostatic cautery', ['P7']),
                          status=at('performed', 'was applied', ['P7']),
                          technique=at('electrocautery', 'cautery', ['P7']),
                          target=tgt('L1', 'gastric_antrum', 'the oozing vessel', ['P7']),
                          purpose=at('hemostasis', 'Hemostatic', ['P7']))],
                   [('43255', (CAUTERY_OOZING,))],
                   lesions=[lesion('L1', '12 mm ulcer with an oozing visible vessel', 'gastric_antrum', 'gastric antrum',
                                   '12 mm', ['P6', 'P7'])]))
# the attested FRESH-2 shapes (the census over f2r5b-int's 179 inventories): every one of the 14 performed
# bleeding_control events, its five attribute words as Gemini gave them - each states the oozing it treats
FRESH2_PERFORMED_BLEEDING_CONTROL = (
    ('brief contact coagulation using the snare tip', 'resolved with brief contact coagulation',
     'Minor oozing from the cut mucosal edge', 'contact coagulation using the snare tip',
     'Minor oozing from the cut mucosal edge resolved'),
    ('contact coagulation', 'resolved with brief contact coagulation', 'cut mucosal edge',
     'contact coagulation using the snare tip', 'Minor oozing from the cut mucosal edge resolved'),
    ('brief contact coagulation using the snare tip', 'resolved with brief contact coagulation', 'cut mucosal edge',
     'brief contact coagulation using the snare tip', 'Minor oozing from the cut mucosal edge resolved with'),
    ('brief contact coagulation', 'resolved with brief contact coagulation', 'the cut mucosal edge', 'snare tip',
     'Minor oozing from the cut mucosal edge resolved'),
    ('brief contact coagulation', 'resolved with brief contact coagulation', 'Minor oozing from the cut mucosal edge',
     'using the snare tip', 'Minor oozing from the cut mucosal edge resolved with brief contact coagulation'),
)


def record(value: str, text: str = '', state: str = 'verified') -> dict:
    return {'value': value, 'state': state, 'open': False, 'basis': 'stated',
            'words': {'text': text, 'start': 0, 'end': len(text)} if text else None}


def stored(kind: str = 'bleeding_control', status: str = 'performed', *, status_state: str = 'verified',
           kind_words: str = 'Hemostatic cautery', status_words: str = 'was applied', target_words: str = 'the ulcer base',
           technique_words: str = 'cautery', purpose: str = 'hemostasis', purpose_words: str = 'Hemostatic') -> dict:
    """An event in its stored shape, as far as catalogue_kind reads it."""
    return {'id': 'E2', 'family': 'gi.egd', 'kind': record(kind, kind_words),
            'status': record(status, status_words, status_state),
            'target': record('gastric_antrum', target_words), 'technique': record('electrocautery', technique_words),
            'purpose': record(purpose, purpose_words) if purpose_words else record('not_stated', '', 'absent')}


# --- (2) problem 1: an act a proposed code holds on is asked after one no proposed code accounts for -------------------

# RF11: the D115 clip in doubt (its time unanchored: gap D's D1_TIME act) beside a biopsy in doubt for the same fact that
# no code reads - 43255 is proposed (it holds on the clip), 43239 is not (the biopsy's question decides it)
TIMED_BIOPSY_LINE = 'At that time, biopsies of the gastric antrum were taken with cold forceps.'
TIMED_BIOPSY = event('E3', EGD, at('biopsy', 'biopsies', ['P8']), status=at('performed', 'were taken', ['P8']),
                     technique=at('cold_forceps', 'cold forceps', ['P8']),
                     target=tgt('', 'gastric_antrum', 'the gastric antrum', ['P8']),
                     time=at('current_encounter', 'At that time', ['P8']))
RF11_LINES = report(P5=ADV, P6=CLEAN_ULCER, P7=e5.AT_THAT_TIME, P8=TIMED_BIOPSY_LINE, P9=NORMAL)
RF11 = mine(case('d142_rf11_clip_in_doubt_beside_a_doubted_biopsy', RF11_LINES,
                 [e5.examination(), copy.deepcopy(e5.TIMED_CLIP), copy.deepcopy(TIMED_BIOPSY)],
                 [('43255', (e5.AT_THAT_TIME,)), ('43235', (ADV,))], lesions=[ULCER]))
RF11_ALONE = mine(case('d142_rf11_43255_alone', RF11_LINES,
                       [e5.examination(), copy.deepcopy(e5.TIMED_CLIP), copy.deepcopy(TIMED_BIOPSY)],
                       [('43255', (e5.AT_THAT_TIME,))], lesions=[ULCER]))
# control: with no code holding on either act (43235 alone), the first act in doubt keeps the family's question (D89)
RF11_BASE = mine(case('d142_rf11_control_43235_alone', RF11_LINES,
                      [e5.examination(), copy.deepcopy(e5.TIMED_CLIP), copy.deepcopy(TIMED_BIOPSY)],
                      [('43235', (ADV,))], lesions=[ULCER]))
BIOPSY_QUESTION = ('Was the forceps biopsy (cold forceps) at the gastric antrum (\u201cwere taken\u201d) done at this '
                   'encounter?')
CLIP_QUESTION = ('Was the possible bleeding control (clip) of the 12 mm clean-based ulcer in the gastric antrum '
                 '(\u201cwere placed\u201d) done at this encounter?')

# --- (3) problem 2 and the eus2 listing: a done act of a kind its family does not list ------------------------------------

BIOPSIES = 'Biopsies of the gastric antrum were taken with cold forceps.'
BIOPSY = event('E3', EGD, at('biopsy', 'Biopsies', ['P7']), status=at('performed', 'were taken', ['P7']),
               technique=at('cold_forceps', 'cold forceps', ['P7']),
               target=tgt('', 'gastric_antrum', 'the gastric antrum', ['P7']))
RF5 = mine(case('d142_rf5_stent_removal_and_43239', report(P5=ADV, P6=e5.REMOVED_STENT, P7=BIOPSIES, P8=e5.RESOLVED),
                [e5.examination(), copy.deepcopy(e5.STENT_REMOVAL), copy.deepcopy(BIOPSY)], [('43239', (BIOPSIES,))]))
STENT_EXCHANGE = event('E2', EGD, at('stent_exchange', 'was exchanged', ['P6']),
                       status=at('performed', 'was exchanged', ['P6']),
                       technique=at('stent', 'fully covered esophageal stent', ['P6']),
                       target=tgt('', 'esophagus', 'esophageal', ['P6']))
RF5_EXCHANGE = mine(case('d142_rf5_stent_exchange_and_43239', report(P5=ADV, P6=e5.EXCHANGED_STENT, P7=BIOPSIES,
                                                                    P8=e5.RESOLVED),
                         [e5.examination(), copy.deepcopy(STENT_EXCHANGE), copy.deepcopy(BIOPSY)],
                         [('43239', (BIOPSIES,))]))
# gap A's A1 itself (43235 alone): held base_included as before, and now listed as c2e53f8e lists its stent
A1 = mine(case('d142_a1_stent_removal_43235', report(P5=ADV, P6=e5.REMOVED_STENT, P7=e5.RESOLVED),
               [e5.examination(), copy.deepcopy(e5.STENT_REMOVAL)], [('43235', (ADV,))]))
# the eus2 review's problem 2 input (audit g4_eusge_stent_43259): an EUS-guided gastroenterostomy, the stent filed as
# kind stent under the EUS, whose catalogue acts hold no stent
EUS_TITLE = 'ENDOSCOPIC ULTRASOUND REPORT'
EUS = at('eus', 'EUS-guided gastroenterostomy', ['P5'])
EUSGE_PROC = 'Procedure: EUS-guided gastroenterostomy.'
EUSGE_ADV = 'The linear echoendoscope was advanced to the second portion of the duodenum.'
EUSGE_MASS = 'The pancreatic head mass causing the duodenal obstruction was examined.'
EUSGE_STENT = 'From the gastric body, a 20 mm lumen-apposing metal stent was deployed into a distended jejunal loop.'
EUS_EXAM = event('E1', EUS, at('examination', 'The linear echoendoscope was advanced', ['P6']),
                 technique=at('endoscope', 'linear echoendoscope', ['P6']),
                 target=tgt('', 'pancreas', 'The pancreatic head mass', ['P7']),
                 status=at('performed', 'was advanced', ['P6']))
EUS_STENT = event('E2', EUS, at('stent', 'lumen-apposing metal stent', ['P8']),
                  status=at('performed', 'was deployed', ['P8']),
                  technique=at('stent', 'lumen-apposing metal stent', ['P8']),
                  target=tgt('', 'jejunum', 'a distended jejunal loop', ['P8']))
EUSGE_LINES = report(EUS_TITLE, P5=EUSGE_PROC, P6=EUSGE_ADV, P7=EUSGE_MASS, P8=EUSGE_STENT)
EUSGE_REACH = ('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P6')
EUSGE = mine(case('d142_eus_gastroenterostomy_stent_43259', EUSGE_LINES, [EUS_EXAM, EUS_STENT],
                  [('43259', (EUSGE_ADV,))], reach=EUSGE_REACH))
# beside Corti's unlisted 43999 citing the stent (audit g4c): coverage not established is never coverage
EUSGE_43999 = mine(case('d142_eus_gastroenterostomy_stent_43259_43999', EUSGE_LINES,
                        [copy.deepcopy(EUS_EXAM), copy.deepcopy(EUS_STENT)],
                        [('43259', (EUSGE_ADV,)),
                         ('43999', ('a 20 mm lumen-apposing metal stent was deployed into a distended jejunal loop',))],
                        reach=EUSGE_REACH))
# the eus2 review's problem 1 input (audit g1_gallbladder_43240): the drainage is a kind the EUS lists, and 43240 reads it
GB_PROC = 'Procedure: EUS-guided gallbladder drainage.'
GB_ADV = 'The linear echoendoscope was advanced to the duodenal bulb.'
GB_FINDING = 'The gallbladder was distended with sludge and a thickened wall, consistent with acute cholecystitis.'
GB_DRAIN = ('EUS-guided transmural drainage of the gallbladder was performed from the duodenal bulb with a 15 mm '
            'lumen-apposing metal stent.')
GB = at('eus', 'EUS-guided gallbladder drainage', ['P5'])
GALLBLADDER = mine(case('d142_eus_gallbladder_drainage_43240', report(EUS_TITLE, P5=GB_PROC, P6=GB_ADV, P7=GB_FINDING,
                                                                     P8=GB_DRAIN),
                        [event('E1', GB, at('examination', 'The linear echoendoscope was advanced', ['P6']),
                               technique=at('endoscope', 'linear echoendoscope', ['P6']),
                               status=at('performed', 'was advanced', ['P6'])),
                         event('E2', at('eus', 'EUS-guided', ['P8']), at('drainage', 'transmural drainage', ['P8']),
                               status=at('performed', 'was performed', ['P8']),
                               technique=at('stent', 'lumen-apposing metal stent', ['P8']),
                               target=tgt('', 'gallbladder', 'the gallbladder', ['P8']))],
                        [('43240', (GB_DRAIN,))], reach=('E1', 'duodenal_bulb', 'duodenal bulb', 'P6')))


def read_time_items(result, name: str) -> list:
    """The unresolved items as the review leaves them: coverage.reconcile re-run at read time over the frozen inventory
    (overlay.reviewed_completeness, as readers.EventReader calls it), with nothing reinstated."""
    stored = [overlay.stored_from(p) for p in result.proposals]
    reading = events.Reading.of(built(name)[0])
    found = overlay.reviewed_completeness(to_jsonable(result.completeness), reading,
                                          overlay.counted_codes(stored, set(), reading), [])
    return [(item['act'], item['reason'], item['second_review']) for item in found['unresolved_items']]


class D142BleedingControlKindInDoubt(SimpleTestCase):
    """D142 (1): c2e53f8e holds 43255 on RF1 ("leaves the bleeding control in doubt"), and 45382 on its colonoscopy
    twin; 46e461e7f read Gemini's bleeding_control kind as a bleeding control done and gave both READY."""

    def test_d142_rf1_hemostatic_cautery_named_only_by_the_adjective_holds_43255(self):
        inv, _ = built(RF1)
        act = events.Reading.of(inv).events['E2']
        with self.subTest(part='the event: a bleeding control in doubt'):
            self.assertEqual((act['catalogue_kind'], mapping.hemostasis_in_doubt(act)),
                             (mapping.POSSIBLE_BLEEDING_CONTROL, True))
        result = assessed(RF1)
        held(self, result, '43255', ['performed_status'])
        held_base(self, result, '43235', '43255')
        with self.subTest(part='the act is listed in doubt'):
            self.assertEqual(items(result), [(mapping.POSSIBLE_BLEEDING_CONTROL, 'in_doubt')])
        alone = assessed(RF1_ALONE)
        held(self, alone, '43255', ['performed_status'])
        with self.subTest(part='43255 alone: coding is never complete on it'):
            self.assertEqual(alone.completeness['state'], 'incomplete')

    def test_d142_variant_a_the_hemostatic_injection_filed_as_bleeding_control_takes_no_code(self):
        result = assessed(RF_A)
        for code in ('43255', '43236', '43243'):
            held(self, result, code, ['performed_status'])
        held_base(self, result, '43235', '43255, 43236, 43243')

    def test_d142_variant_b_the_colonoscopy_cautery_holds_45382(self):
        result = assessed(RF_B)
        held(self, result, '45382', ['performed_status'])
        held_base(self, result, '45378', '45382')

    def test_d142_control_the_bleeding_control_kind_that_states_its_bleeding_is_ready(self):
        inv, _ = built(RF_OWN)
        self.assertEqual(events.Reading.of(inv).events['E2']['catalogue_kind'], mapping.BLEEDING_CONTROL)
        ready(self, assessed(RF_OWN), '43255')

    def test_d142_the_catalogue_kind_of_the_bleeding_control_kind(self):
        cases = {
            'named only by the adjective': (stored(), mapping.POSSIBLE_BLEEDING_CONTROL),
            'whatever its purpose: none stated': (stored(purpose_words=''), mapping.POSSIBLE_BLEEDING_CONTROL),
            'a purpose stating the bleeding': (stored(purpose_words='to control the bleeding'), mapping.BLEEDING_CONTROL),
            'the noun': (stored(purpose_words='for hemostasis'), mapping.BLEEDING_CONTROL),
            'kind words stating it': (stored(kind_words='control of bleeding'), mapping.BLEEDING_CONTROL),
            'a prevention': (stored(purpose_words='to prevent delayed bleeding'), mapping.POSSIBLE_BLEEDING_CONTROL),
            'a denial': (stored(status='not_performed', status_words='No hemostatic cautery'), mapping.BLEEDING_CONTROL),
            'planned': (stored(status='planned', status_words='will be applied'), mapping.BLEEDING_CONTROL),
            'uncertain': (stored(status='uncertain', status_words='may have been applied'), mapping.BLEEDING_CONTROL),
            'attempted': (stored(status='attempted_not_completed', status_words='could not be applied'),
                          mapping.BLEEDING_CONTROL),
            'status words unbound': (stored(status_state='unverified'), mapping.BLEEDING_CONTROL),
            'a clip with no hemostasis purpose is a clip': (stored('clip', purpose_words=''), 'clip'),
        }
        for name, (item, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(mapping.catalogue_kind(item), expected)

    def test_d142_measured_the_fresh2_performed_bleeding_control_events_each_state_their_bleeding(self):
        """The census over f2r5b-int's FRESH-2 inventories: 14 performed bleeding_control events, every one stating the
        oozing it treats in its own purpose words - so none of them is put in doubt (cost 0 on FRESH-2)."""
        for kind_words, status_words, target_words, technique_words, purpose_words in FRESH2_PERFORMED_BLEEDING_CONTROL:
            with self.subTest(purpose=purpose_words, target=target_words):
                item = stored(kind_words=kind_words, status_words=status_words, target_words=target_words,
                              technique_words=technique_words, purpose_words=purpose_words)
                self.assertEqual(mapping.catalogue_kind(item), mapping.BLEEDING_CONTROL)


class D142QuestionForTheMissingCode(SimpleTestCase):
    """D142 (2): 1caaf0609 asked RF11's biopsy "done at this encounter?" at service scope; 46e461e7f asked the clip's
    instead (one question per family and fact, in the reading's order), so the question that decides a missing 43239 was
    gone. c2e53f8e lists the biopsy not covered and asks no service question."""

    def test_d142_rf11_d149_the_reading_order_asks_the_clips_question(self):
        """CHANGED with DECISIONS D149 (was test_d142_rf11_the_biopsys_question_is_asked_beside_the_clip_43255_holds_on,
        asserting BIOPSY_QUESTION): 43255 is held not_documented and its records name no event, so no proposed code reads
        or holds on either act and the reading's order asks the clip's question, as 46e461e7f did."""
        for name in (RF11, RF11_ALONE):
            result = assessed(name)
            with self.subTest(case=name):
                held(self, result, '43255', ['performed_status'])
                self.assertEqual([(spec.fact, spec.question) for spec in result.clarifications],
                                 [('event_time', CLIP_QUESTION)])
                self.assertEqual(items(result), [(mapping.POSSIBLE_BLEEDING_CONTROL, 'in_doubt'), ('biopsy', 'in_doubt')])

    def test_d142_control_with_no_code_accounting_for_either_act_the_reading_order_stands(self):
        result = assessed(RF11_BASE)
        self.assertEqual([(spec.fact, spec.question) for spec in result.clarifications],
                         [('event_time', CLIP_QUESTION)])

    def test_d142_d149_the_order_reads_no_profile(self):
        """CHANGED with DECISIONS D149 (was test_d142_the_order_reads_which_proposed_code_accounts_for_the_act, where
        ['43255', '43235'] asked BIOPSY_QUESTION): coverage.in_doubt_questions over RF11's reading reads no profile that
        covers an act's kind - with nothing held (assess's records), every set of counted codes keeps the reading's
        order."""
        reading = events.Reading.of(built(RF11)[0])
        item = {'service': 'gi.egd', 'family': 'gi.egd'}
        in_doubt = [(item, 'E2'), (item, 'E3')]
        for codes, expected in ((['43255', '43235'], CLIP_QUESTION), (['43239'], CLIP_QUESTION),
                                (['43235'], CLIP_QUESTION), (['43255', '43239'], CLIP_QUESTION)):
            with self.subTest(codes=codes):
                found = coverage.in_doubt_questions(
                    reading, coverage.Coverage(in_doubt=in_doubt, covered={'gi.egd': codes}))
                self.assertEqual([spec.question for spec in found], [expected])


class D142ListedNotCovered(SimpleTestCase):
    """D142 (3): c2e53f8e lists RF5's stent not covered (coding incomplete); 46e461e7f skipped a kind its session's
    family does not list, so 43239 was READY with coding complete and the stent removal invisible."""

    def test_d142_rf5_a_stent_removal_beside_43239_is_listed_not_covered(self):
        result = assessed(RF5)
        ready(self, result, '43239')
        with self.subTest(part='listed not covered, with the second-review mark'):
            self.assertEqual([(item['act'], item['reason'], item['second_review'])
                              for item in result.completeness['unresolved_items']],
                             [('stent_removal', 'not_covered', True)])
            self.assertEqual(result.completeness['state'], 'incomplete')
        with self.subTest(part='and at read time'):
            self.assertEqual(read_time_items(result, RF5), [('stent_removal', 'not_covered', True)])

    def test_d142_rf5_a_stent_exchange_too(self):
        result = assessed(RF5_EXCHANGE)
        ready(self, result, '43239')
        self.assertEqual(items(result), [('stent_exchange', 'not_covered')])
        self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d142_gap_a1_43235_stays_held_and_the_stent_removal_is_listed(self):
        result = assessed(A1)
        held_base(self, result, '43235', 'stent removal')
        self.assertEqual(items(result), [('stent_removal', 'not_covered')])

    def test_d142_the_eus_gastroenterostomy_stent_beside_43259_is_listed(self):
        """The eus2 review's problem 2 (listing half): the EUS lists no stent among its acts. 43259 itself is D122's,
        recorded and not built here."""
        for name in (EUSGE, EUSGE_43999):
            result = assessed(name)
            with self.subTest(case=name):
                self.assertEqual([(item['act'], item['reason'], item['second_review'])
                                  for item in result.completeness['unresolved_items']], [('stent', 'not_covered', True)])
                self.assertEqual(result.completeness['state'], 'incomplete')
                self.assertEqual(read_time_items(result, name), [('stent', 'not_covered', True)])

    def test_d142_never_an_act_a_proposed_code_covers(self):
        """The eus2 review's problem 1 input: the gallbladder drainage is a kind the EUS lists, and 43240 reads it (D120's
        defining target is read by nothing): no item, as before - recorded, not listed. And an act of a kind its family
        does not list that a counted code reads is never listed."""
        result = assessed(GALLBLADDER)
        self.assertEqual(items(result), [])
        reading = events.Reading.of(built(EUSGE)[0])
        reads_it = coverage.Counted(key='sel:0', code='43259', family='gi.eus', supporting=('E1',), read=('E2',))
        self.assertEqual(coverage.reconcile(reading, [reads_it]).unresolved, [])

    def test_d142_never_the_umbrella_or_the_bleeding_control_in_doubt(self):
        """D117's removal of unstated method and D115's bleeding control in doubt stay listed in doubt only."""
        for name, expected in ((e5.B1, [('removal', 'in_doubt')]), (e5.B4, [('removal', 'in_doubt')]),
                               (e5.D1, [(mapping.POSSIBLE_BLEEDING_CONTROL, 'in_doubt')]),
                               (RF1, [(mapping.POSSIBLE_BLEEDING_CONTROL, 'in_doubt')])):
            with self.subTest(case=name):
                self.assertEqual(items(assessed(name)), expected)

    def test_d142_what_the_arm_lists(self):
        """RF5's stent removal, its catalogue kind replaced: a kind a supported family lists is listed; an E/M visit,
        moderate sedation (a recognised family's only), a kind no family lists and an act whose kind or procedure is not
        usable are not (an FNA, of no EGD kind, so that no other rule lists it in doubt)."""
        counted = [coverage.Counted(key='sel:0', code='43239', family='gi.egd', supporting=('E3',), read=('E3',))]
        unusable = {'value': 'x', 'state': 'unverified', 'open': False, 'basis': 'stated', 'words': None}
        for name, change, expected in (
                ('a tube replacement', {'catalogue_kind': 'tube_replacement'}, [('tube_replacement', 'not_covered')]),
                ('an FNA', {'catalogue_kind': 'fna'}, [('fna', 'not_covered')]),
                ('an E/M visit', {'catalogue_kind': 'em_visit'}, []),
                ('moderate sedation', {'catalogue_kind': 'moderate_sedation'}, []),
                ('a balloon expulsion (no family lists it)', {'catalogue_kind': 'balloon_expulsion'}, []),
                ('its kind not usable', {'catalogue_kind': 'fna', 'kind': {**unusable, 'value': 'fna'}}, []),
                ('its procedure not usable', {'catalogue_kind': 'fna', 'procedure': {**unusable, 'value': 'egd'}}, [])):
            reading = events.Reading.of(built(RF5)[0])
            reading.events['E2'].update(change)
            with self.subTest(case=name):
                found = coverage.reconcile(reading, counted).unresolved
                self.assertEqual([(item['act'], item['reason']) for item in found], expected)
