"""DECISIONS D149 (round 5d; the round-5c review of D142, review_egd3.json problems 0, 1 and 4), SYNTHETIC, each built
from its source's own input with the round-5 EGD builders (tests/test_interpretation_r5_egd.py: a document, a Gemini
answer written to prompt.py's contract, the proposer's citations replayed) and its controls:
- (1) problem 0: coverage.in_doubt_questions orders its acts by which ones a proposed code READS or HOLDS ON (the events
  assess records for the codes), never by a profile that covers the act's kind: F1's doubted esophageal dilation, which
  43245 (READY on the pyloric dilation) neither reads nor holds on, is asked before the doubted biopsy, as 46e461e7f
  asked it. RF11's clip in doubt is held on by no record (43255 is held not_documented, naming no event), so the reading's
  order asks the clip's question there too.
- (2) problem 1: D142's arm reads an event of the bleeding_control kind whose purpose is not a verified hemostasis only
  when its own kind, technique or purpose words name the control by the adjective ('hemostatic', 'hemostasis'), as
  c2e53f8e keys its rule: "Epinephrine was injected into the ulcer base, followed by bipolar cautery." and "Bipolar
  cautery was applied to the ulcer base." beside an oozing visible vessel keep the bleeding control (43255 READY, as
  c2e53f8e); RF1 and variants (a) and (b) (a verified hemostasis purpose, read as D115 reads a clip) and RF1's cautery
  with no purpose (named by the adjective) stay in doubt.
- (3) problem 4: the gallbladder drainage beside 43240 is held by D136 (43240's defining target, eus3) on e5628be56.
CASES (the round-5 module's) holds every input, so the installed release (c2e53f8e) can be run on the very same texts and
citations. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, mapping
from tests import test_interpretation_r5_egd as e5
from tests import test_interpretation_r5c_egd as e5c
from tests.test_interpretation_events import proposal

at, tgt, event, lesion, report, case = e5.at, e5.tgt, e5.event, e5.lesion, e5.report, e5.case
built, assessed, reviewed, items = e5.built, e5.assessed, e5.reviewed, e5.items
held, held_base, ready = e5.held, e5.held_base, e5.ready
EGD, ADV, NORMAL, CLEAN_ULCER, ULCER = e5.EGD, e5.ADV, e5.NORMAL, e5.CLEAN_ULCER, e5.ULCER
NAMES: list = []  # the inputs this module asserts on, in order (dumped for the installed release's runner)


def mine(name: str) -> str:
    NAMES.append(name)
    return name


# --- (1) problem 0: the order reads the records, never a profile ----------------------------------------------------------

# F1 (review_egd3.json problem 0): 43245 is READY on the pyloric dilation (E2); the distal esophageal dilation (E3) and the
# biopsy (E4) are both in doubt for their time ('At that time'); 43245 reads neither (E3 fails events.supports) and asks no
# question. D142 read E3 as accounted for by 43245's profile (its covers hold the dilation kind) and asked E4's question.
PYLORUS = 'The pyloric stricture was dilated with a 15 mm balloon.'
ESO_LATER = 'At that time, the distal esophageal stricture was dilated with an 18 mm balloon.'
BX_LATER = 'At that time, biopsies of the gastric antrum were taken with cold forceps.'
PYLORIC = event('E2', EGD, at('dilation', 'dilated', ['P6']), status=at('performed', 'was dilated', ['P6']),
                technique=at('balloon', '15 mm balloon', ['P6']),
                target=tgt('', 'pylorus', 'The pyloric stricture', ['P6']))


def esophageal(line: str, timed: bool = True) -> dict:
    return event('E3', EGD, at('dilation', 'dilated', ['P7']), status=at('performed', 'was dilated', ['P7']),
                 technique=at('balloon', '18 mm balloon', ['P7']),
                 target=tgt('', 'distal_esophagus', 'the distal esophageal stricture' if timed
                            else 'The distal esophageal stricture', ['P7']),
                 time=at('current_encounter', 'At that time', ['P7']) if timed else None)


TIMED_BX = event('E4', EGD, at('biopsy', 'biopsies', ['P8']), status=at('performed', 'were taken', ['P8']),
                 technique=at('cold_forceps', 'cold forceps', ['P8']),
                 target=tgt('', 'gastric_antrum', 'the gastric antrum', ['P8']),
                 time=at('current_encounter', 'At that time', ['P8']))
F1 = mine(case('d149_f1_43245_ready_the_doubted_dilation_beside_a_doubted_biopsy',
               report(P5=ADV, P6=PYLORUS, P7=ESO_LATER, P8=BX_LATER, P9=NORMAL),
               [e5.examination(), PYLORIC, esophageal(ESO_LATER), TIMED_BX], [('43245', (PYLORUS,))]))
# its done twin (the reviewer's rv2_f1_done_twin): what the dilation's answer decides - told done, it is a done dilation no
# proposed code reads, listed not covered (the missing code is the esophageal dilation's)
ESO_NOW = 'The distal esophageal stricture was dilated with an 18 mm balloon.'
F1_DONE = mine(case('d149_f1_done_twin_the_esophageal_dilation_beside_43245',
                    report(P5=ADV, P6=PYLORUS, P7=ESO_NOW, P9=NORMAL),
                    [e5.examination(), PYLORIC, esophageal(ESO_NOW, timed=False)], [('43245', (PYLORUS,))]))
DILATION_QUESTION = 'Was the dilation (balloon) at the distal esophagus (\u201cwas dilated\u201d) done at this encounter?'
BIOPSY_QUESTION = ('Was the forceps biopsy (cold forceps) at the gastric antrum (\u201cwere taken\u201d) done at this '
                   'encounter?')
RF11, RF11_ALONE, RF11_BASE = e5c.RF11, e5c.RF11_ALONE, e5c.RF11_BASE
NAMES.extend((RF11, RF11_ALONE, RF11_BASE))

# --- (2) problem 1: the bleeding_control kind is read in doubt only when its own words name it by the adjective -----------

VESSEL = 'A 12 mm ulcer with an oozing visible vessel was seen in the gastric antrum.'
VESSEL_ULCER = lesion('L1', '12 mm ulcer with an oozing visible vessel', 'gastric_antrum', 'gastric antrum', '12 mm',
                      ['P6', 'P7'])


def control(line: str, *, kind_words: str, technique_words: str, target_words: str, status_words: str = 'was applied',
            technique: str = 'electrocautery', purpose: str = '', purpose_words: str = '', eid: str = 'E2',
            procedure=EGD, landmark: str = 'gastric_antrum') -> dict:
    """A performed bleeding_control event (P7) of lesion L1, its words each a part of ``line``; purpose not_stated unless
    given (the attested FRESH-2 'cautery' filing: kind bleeding_control, purpose not_stated)."""
    for words in (kind_words, technique_words, target_words, status_words) + ((purpose_words,) if purpose_words else ()):
        assert words in line, (words, line)
    return event(eid, procedure, at('bleeding_control', kind_words, ['P7']), status=at('performed', status_words, ['P7']),
                 technique=at(technique, technique_words, ['P7']), target=tgt('L1', landmark, target_words, ['P7']),
                 purpose=at(purpose, purpose_words, ['P7']) if purpose else at('not_stated'))


# A6 (review_egd3.json problem 1): the dual therapy of a bleeding ulcer - Gemini's E2 injection, E3 the cautery filed as
# bleeding_control worded 'bipolar cautery', purpose not_stated; 43255 cites P7
DUAL = 'Epinephrine was injected into the ulcer base, followed by bipolar cautery.'
INJECTED = event('E2', EGD, at('injection', 'injected', ['P7']), status=at('performed', 'was injected', ['P7']),
                 technique=at('injection', 'Epinephrine', ['P7']),
                 target=tgt('L1', 'gastric_antrum', 'the ulcer base', ['P7']))
CAUTERY_AFTER = event('E3', EGD, at('bleeding_control', 'bipolar cautery', ['P7']),
                      status=at('performed', 'followed by', ['P7']),
                      technique=at('electrocautery', 'bipolar cautery', ['P7']),
                      target=tgt('L1', 'gastric_antrum', 'the ulcer base', ['P7']))
A6 = mine(case('d149_a6_dual_therapy_beside_the_oozing_vessel_43255', report(P5=ADV, P6=VESSEL, P7=DUAL, P8=NORMAL),
               [e5.examination(), INJECTED, CAUTERY_AFTER], [('43255', (DUAL,))], lesions=[VESSEL_ULCER]))
BIPOLAR = 'Bipolar cautery was applied to the ulcer base.'
BIPOLAR_ACT = control(BIPOLAR, kind_words='Bipolar cautery', technique_words='Bipolar cautery',
                      target_words='the ulcer base')
A3 = mine(case('d149_a3_bipolar_cautery_beside_the_oozing_vessel_43255', report(P5=ADV, P6=VESSEL, P7=BIPOLAR, P8=NORMAL),
               [e5.examination(), BIPOLAR_ACT], [('43255', (BIPOLAR,))], lesions=[VESSEL_ULCER]))
A3_BASE = mine(case('d149_a3_bipolar_cautery_beside_the_oozing_vessel_43255_43235',
                    report(P5=ADV, P6=VESSEL, P7=BIPOLAR, P8=NORMAL), [e5.examination(), BIPOLAR_ACT],
                    [('43255', (BIPOLAR,)), ('43235', (ADV,))], lesions=[VESSEL_ULCER]))
TO_VESSEL = 'Bipolar cautery was applied to the vessel.'
A3_VESSEL = mine(case('d149_a3_bipolar_cautery_applied_to_the_vessel_43255',
                      report(P5=ADV, P6=VESSEL, P7=TO_VESSEL, P8=NORMAL),
                      [e5.examination(), control(TO_VESSEL, kind_words='Bipolar cautery',
                                                 technique_words='Bipolar cautery', target_words='the vessel')],
                      [('43255', (TO_VESSEL,))], lesions=[VESSEL_ULCER]))
# the colonoscopy twin (45382 beside 45378)
CECUM = 'The colonoscope was advanced to the cecum.'
COLON_VESSEL = 'A 6 mm ulcer with an oozing visible vessel was seen in the ascending colon.'
A3_COLON = mine(case('d149_a3_colonoscopy_bipolar_cautery_45382_45378',
                     report('COLONOSCOPY REPORT', P5=CECUM, P6=COLON_VESSEL, P7=BIPOLAR, P8='No other lesion was seen.'),
                     [e5c.COLON_EXAM, control(BIPOLAR, kind_words='Bipolar cautery', technique_words='Bipolar cautery',
                                              target_words='the ulcer base', procedure=e5c.COLON,
                                              landmark='ascending_colon')],
                     [('45382', (BIPOLAR,)), ('45378', (CECUM,))],
                     lesions=[lesion('L1', '6 mm ulcer with an oozing visible vessel', 'ascending_colon',
                                     'ascending colon', '6 mm', ['P6', 'P7'])],
                     reach=('E1', 'cecum', 'cecum', 'P5')))
# in doubt: RF1, variants (a) and (b) (a verified hemostasis purpose, read as D115 reads a clip), and - with no verified
# hemostasis purpose - named by the adjective: RF1's cautery with no purpose (the reviewer's rv4: its kind words), the
# British spelling (its kind words), and the adjective in its device words alone
RF1, RF1_ALONE, RF_A, RF_B = e5c.RF1, e5c.RF1_ALONE, e5c.RF_A, e5c.RF_B
NAMES.extend((RF1, RF1_ALONE, RF_A, RF_B))
CAUTERY = e5c.CAUTERY
RV4 = mine(case('d149_rv4_hemostatic_cautery_kind_words_no_purpose_43255',
                report(P5=ADV, P6=CLEAN_ULCER, P7=CAUTERY, P8=NORMAL),
                [e5.examination(), control(CAUTERY, kind_words='Hemostatic cautery', technique_words='cautery',
                                           target_words='the ulcer base')],
                [('43255', (CAUTERY,))], lesions=[ULCER]))
BRITISH = 'Haemostatic cautery was applied to the ulcer base.'
BRITISH_CASE = mine(case('d149_haemostatic_cautery_no_purpose_clean_ulcer_43255',
                         report(P5=ADV, P6=CLEAN_ULCER, P7=BRITISH, P8=NORMAL),
                         [e5.examination(), control(BRITISH, kind_words='Haemostatic cautery', technique_words='cautery',
                                                    target_words='the ulcer base')],
                         [('43255', (BRITISH,))], lesions=[ULCER]))
CLIPS = e5.CLIPS  # 'Two hemostatic clips were placed across the ulcer.'
DEVICE_ONLY = mine(case('d149_clips_filed_as_bleeding_control_adjective_in_device_words_43255',
                        report(P5=ADV, P6=CLEAN_ULCER, P7=CLIPS, P8=NORMAL),
                        [e5.examination(), control(CLIPS, kind_words='clips were placed', technique='clip',
                                                   technique_words='hemostatic clips', target_words='the ulcer',
                                                   status_words='were placed')],
                        [('43255', (CLIPS,))], lesions=[ULCER]))


def record(value: str, text: str = '', state: str = 'verified') -> dict:
    return {'value': value, 'state': state, 'open': False, 'basis': 'stated',
            'words': {'text': text, 'start': 0, 'end': len(text)} if text else None}


def stored(kind: str = 'bleeding_control', *, kind_words: str = 'Bipolar cautery', technique_words: str = 'Bipolar cautery',
           target_words: str = 'the ulcer base', status: str = 'performed', status_words: str = 'was applied',
           purpose: str = 'not_stated', purpose_words: str = '', words_state: str = 'verified',
           purpose_state: str = 'verified') -> dict:
    """An event in its stored shape, as far as catalogue_kind reads it (``words_state``: its kind's and technique's
    words' state; ``purpose_state``: its purpose's)."""
    return {'id': 'E2', 'family': 'gi.egd', 'kind': record(kind, kind_words, words_state),
            'status': record(status, status_words), 'target': record('gastric_antrum', target_words),
            'technique': record('electrocautery', technique_words, words_state),
            'purpose': (record(purpose, purpose_words, purpose_state) if purpose_words
                        else record('not_stated', '', 'absent'))}


# --- (3) problem 4: the gallbladder drainage beside 43240 -------------------------------------------------------------

GALLBLADDER = e5c.GALLBLADDER
NAMES.append(GALLBLADDER)


class D149OrderReadsTheRecords(SimpleTestCase):
    """D149 (1): c2e53f8e asks no service question on F1 (43245 READY; the biopsy listed not covered); 46e461e7f asked the
    dilation's "done at this encounter?"; e5628be56 (D142's profile order) asked the biopsy's."""

    def test_d149_f1_the_doubted_dilation_no_code_reads_or_holds_on_is_asked(self):
        result = assessed(F1)
        ready(self, result, '43245')
        with self.subTest(part='both acts listed in doubt'):
            self.assertEqual(items(result), [('dilation', 'in_doubt'), ('biopsy', 'in_doubt')])
        with self.subTest(part="the reading's order: the dilation's question"):
            self.assertEqual([(spec.fact, spec.question) for spec in result.clarifications],
                             [('event_time', DILATION_QUESTION)])
        with self.subTest(part='43245 reads only the pyloric dilation and asks nothing'):
            p = proposal(result, '43245')
            self.assertEqual(([act['id'] for act in p.support['acts']], p.support.get('question_events')), (['E2'], None))

    def test_d149_f1_control_what_the_dilation_answer_decides(self):
        """Told done (the done twin), the esophageal dilation is a done act no proposed code reads: listed not covered,
        with the second-review mark - its question decides a code that is missing."""
        result = assessed(F1_DONE)
        ready(self, result, '43245')
        self.assertEqual([(item['act'], item['reason'], item['second_review'])
                          for item in result.completeness['unresolved_items']], [('dilation', 'not_covered', True)])

    def test_d149_rf11_no_code_holds_on_the_clip_so_the_reading_order_asks_it(self):
        """RF11 (CHANGED from D142's outcome): 43255 is held not_documented - D115's possible bleeding control matches no
        code, so 43255 reads no event and its question names none (support['acts'] and support['question_events'] are
        empty). No record holds on either act, and the reading's order asks the clip's question, as 46e461e7f did."""
        for name in (RF11, RF11_ALONE):
            result = assessed(name)
            with self.subTest(case=name):
                held(self, result, '43255', ['performed_status'])
                p = proposal(result, '43255')
                self.assertEqual((p.support['acts'], p.support['question_events']), ([], []))
                self.assertEqual([(spec.fact, spec.question) for spec in result.clarifications],
                                 [('event_time', e5c.CLIP_QUESTION)])
                self.assertEqual(items(result), [(mapping.POSSIBLE_BLEEDING_CONTROL, 'in_doubt'), ('biopsy', 'in_doubt')])

    def test_d149_the_order_reads_the_events_held_never_a_profile(self):
        """coverage.in_doubt_questions over F1's and RF11's readings: the act a proposed code holds on (``holding``) is
        asked after the other; with nothing held, the reading's order - whatever codes are counted, and whatever their
        profiles cover (the profile and its family are not read: the reviewer's mutant J has nothing left to drop)."""
        item = {'service': 'gi.egd', 'family': 'gi.egd'}
        f1 = events.Reading.of(built(F1)[0])
        rf11 = events.Reading.of(built(RF11)[0])
        rows = (
            ('F1, nothing held', f1, ['E3', 'E4'], ['43245'], (), DILATION_QUESTION),
            ('F1, 43249 and 43239 counted, nothing held', f1, ['E3', 'E4'], ['43249', '43239'], (), DILATION_QUESTION),
            ('F1, a code holds on the dilation', f1, ['E3', 'E4'], ['43245'], ('E3',), BIOPSY_QUESTION),
            ('F1, a code holds on the biopsy', f1, ['E3', 'E4'], ['43245'], ('E4',), DILATION_QUESTION),
            ('F1, both held', f1, ['E3', 'E4'], ['43245'], ('E3', 'E4'), DILATION_QUESTION),
            ('RF11, 43255 and 43235 counted, nothing held', rf11, ['E2', 'E3'], ['43255', '43235'], (),
             e5c.CLIP_QUESTION),
            ('RF11, a colonoscopy code counted in the session', rf11, ['E2', 'E3'], ['45382'], (), e5c.CLIP_QUESTION),
            ('RF11, a code holds on the clip', rf11, ['E2', 'E3'], ['43255'], ('E2',), e5c.BIOPSY_QUESTION),
            ('RF11, only an event not in doubt held (the examination)', rf11, ['E2', 'E3'], ['43255'], ('E1',),
             e5c.CLIP_QUESTION),
        )
        for name, reading, doubted, codes, holding, expected in rows:
            with self.subTest(case=name):
                found = coverage.in_doubt_questions(
                    reading, coverage.Coverage(in_doubt=[(item, eid) for eid in doubted], covered={'gi.egd': codes}),
                    holding=holding)
                self.assertEqual([spec.question for spec in found], [expected])

    def test_d149_the_order_never_changes_which_facts_are_asked(self):
        """The order decides only which act each (family, fact) question names: F1's two acts share event_time, so one
        question is asked whatever is held."""
        item = {'service': 'gi.egd', 'family': 'gi.egd'}
        reading = events.Reading.of(built(F1)[0])
        for holding in ((), ('E3',), ('E4',), ('E3', 'E4')):
            with self.subTest(holding=holding):
                found = coverage.in_doubt_questions(
                    reading, coverage.Coverage(in_doubt=[(item, 'E3'), (item, 'E4')], covered={'gi.egd': ['43245']}),
                    holding=holding)
                self.assertEqual([(spec.scope, spec.fact, spec.family) for spec in found],
                                 [('service', 'event_time', 'gi.egd')])


class D149AdjectiveKeysTheBleedingControlKind(SimpleTestCase):
    """D149 (2): c2e53f8e and 46e461e7f are READY on A6 and the bipolar cautery beside the oozing vessel (and 45382 on the
    colonoscopy twin); e5628be56 (D142's 'whatever its purpose') held them. c2e53f8e holds RF1, variants (a) and (b) and
    RF1's cautery with no purpose, as here."""

    def test_d149_a6_the_dual_therapy_keeps_the_bleeding_control(self):
        inv, _ = built(A6)
        self.assertEqual(events.Reading.of(inv).events['E3']['catalogue_kind'], mapping.BLEEDING_CONTROL)
        result = assessed(A6)
        ready(self, result, '43255')
        with self.subTest(part='the injection listed not covered, as c2e53f8e lists it'):
            self.assertEqual([(item['act'], item['reason'], item['second_review'])
                              for item in result.completeness['unresolved_items']], [('injection', 'not_covered', True)])

    def test_d149_bipolar_cautery_beside_the_oozing_vessel_keeps_the_bleeding_control(self):
        for name in (A3, A3_VESSEL):
            with self.subTest(case=name):
                ready(self, assessed(name), '43255')
        result = assessed(A3_BASE)
        ready(self, result, '43255')
        held_base(self, result, '43235', '43255')

    def test_d149_the_colonoscopy_twin_keeps_the_bleeding_control(self):
        result = assessed(A3_COLON)
        ready(self, result, '45382')
        held_base(self, result, '45378', '45382')

    def test_d149_named_by_the_adjective_the_control_stays_in_doubt(self):
        for name in (RF1, RF1_ALONE, RF_B, RV4, BRITISH_CASE, DEVICE_ONLY):
            inv, _ = built(name)
            act = events.Reading.of(inv).events['E2']
            with self.subTest(case=name):
                self.assertEqual(act['catalogue_kind'], mapping.POSSIBLE_BLEEDING_CONTROL)
                code = '45382' if name == RF_B else '43255'
                held(self, assessed(name), code, ['performed_status'])
        result = assessed(RF_A)
        for code in ('43255', '43236', '43243'):
            held(self, result, code, ['performed_status'])

    def test_d149_the_catalogue_kind_of_the_bleeding_control_kind(self):
        cases = {
            'named by its device, no purpose': (stored(), mapping.BLEEDING_CONTROL),
            'named by its device, a purpose other than hemostasis': (
                stored(purpose='prophylaxis', purpose_words='to prevent rebleeding'), mapping.BLEEDING_CONTROL),
            'named by its device, a hemostasis purpose whose words do not bind': (
                stored(purpose='hemostasis', purpose_words='to treat the ulcer', purpose_state='unverified'),
                mapping.BLEEDING_CONTROL),
            'the adjective in its kind words': (stored(kind_words='Hemostatic cautery', technique_words='cautery'),
                                                mapping.POSSIBLE_BLEEDING_CONTROL),
            'the adjective in its device words': (stored(kind_words='clips were placed',
                                                         technique_words='hemostatic clips'),
                                                  mapping.POSSIBLE_BLEEDING_CONTROL),
            'the adjective in purpose words that do not bind': (
                stored(purpose='hemostasis', purpose_words='hemostatic', purpose_state='unverified'),
                mapping.POSSIBLE_BLEEDING_CONTROL),
            'the noun with a prevention word, a purpose other than hemostasis': (
                stored(purpose='prophylaxis', purpose_words='to ensure hemostasis'), mapping.POSSIBLE_BLEEDING_CONTROL),
            'the British spelling': (stored(kind_words='Haemostatic cautery', technique_words='cautery'),
                                     mapping.POSSIBLE_BLEEDING_CONTROL),
            'the British noun with a prevention word': (
                stored(purpose='prophylaxis', purpose_words='to ensure haemostasis'), mapping.POSSIBLE_BLEEDING_CONTROL),
            'the adjective in kind and device words that do not bind': (
                stored(kind_words='Hemostatic cautery', technique_words='cautery', words_state='unverified'),
                mapping.POSSIBLE_BLEEDING_CONTROL),
            'the adjective with the bleeding stated': (
                stored(kind_words='Hemostatic cautery', technique_words='cautery', target_words='the oozing vessel'),
                mapping.BLEEDING_CONTROL),
            'the noun stating the act': (stored(purpose='prophylaxis', purpose_words='for hemostasis'),
                                         mapping.BLEEDING_CONTROL),
            'the adjective only in its target words': (stored(target_words='the hemostatic clip site'),
                                                       mapping.BLEEDING_CONTROL),
            'a denial named by the adjective': (stored(kind_words='Hemostatic cautery', status='not_performed',
                                                       status_words='No hemostatic cautery'), mapping.BLEEDING_CONTROL),
            'a verified hemostasis purpose, read as D115 reads a clip, though named by its device': (
                stored(purpose='hemostasis', purpose_words='to treat the ulcer'), mapping.POSSIBLE_BLEEDING_CONTROL),
            'a verified hemostasis purpose, its bleeding stated': (
                stored(purpose='hemostasis', purpose_words='to control the oozing'), mapping.BLEEDING_CONTROL),
            "D115's clip: a verified hemostasis purpose with no adjective is still in doubt": (
                stored('clip', kind_words='clips were placed', technique_words='clips', purpose='hemostasis',
                       purpose_words='to treat the ulcer'), mapping.POSSIBLE_BLEEDING_CONTROL),
        }
        for name, (item, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(mapping.catalogue_kind(item), expected)
                self.assertEqual(mapping.hemostasis_in_doubt(item), expected == mapping.POSSIBLE_BLEEDING_CONTROL)


class D149GallbladderDrainageHeldByD136(SimpleTestCase):
    """D149 (3), review_egd3.json problem 4: 46e461e7f gave 43240 READY beside the gallbladder drainage (complete); on
    e5628be56 D136 (eus3) reads 43240's defining target, so the drainage supports nothing and 43240 is held on it, as
    c2e53f8e holds it [performed_status, target]. Neither lists an item. Round 5d integration: D145 (eus4) makes the
    hold ask the drainage's target (events._target_hold, reason another_site), so 43240 is held [target, target] - the
    second is R6's examination question, the duplicate eus4 recorded as its disagreement 1 - still with no item."""

    def test_d149_problem4_the_gallbladder_drainage_beside_43240_is_held_by_d136(self):
        inv, _ = built(GALLBLADDER)
        reading = events.Reading.of(inv)
        with self.subTest(part="D136: the drainage misses 43240's defining target"):
            self.assertFalse(events.defining_fit(reading, mapping.code_link('43240'), reading.events['E2']))
        result = assessed(GALLBLADDER)
        held(self, result, '43240', ['target', 'target'])
        p = proposal(result, '43240')
        with self.subTest(part='held on the drainage, a positive candidate it reads'):
            self.assertEqual((p.support['reason'], p.support['acts'], p.support['question_events']),
                             (events.ANOTHER_SITE, [], ['E2']))
        with self.subTest(part='no item, coding incomplete'):
            self.assertEqual((items(result), result.completeness['state']), ([], 'incomplete'))
        with self.subTest(part='at read time'):
            self.assertEqual(reviewed(result, '43240').status, 'needs_clarification')
