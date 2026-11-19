"""DECISIONS D160 (the round-5e review of D153: gemini-migration/round5e/results-wf_ec2ec26b-bed.json
'review:enteroscopy5' problems 4 and 5), SYNTHETIC, rebuilt from the review's own documents as its tools/rv_refute.py
builds them (the 'ileal J-pouch' beside a 'Roux-en-Y gastric bypass', the Roux-en-Y enteroscopy 'through the pouch and
the Roux limb', and the EGD to the second portion with the push enteroscopy whose biopsies' place is not verified).
NARROWING ONLY - studio/interpretation/classes.py (gastric_beside, route_phrase, elsewhere_hold) and wording.py
(procedure_question):
- (2, problem 4) beside the verified small-intestinal pouch and a gastric pouch or gastric bypass entry, ANY pouch route
  phrase is a doubted route, whatever its words: the pouch class is held with the route question (extent);
- (3, problem 5) the place question never names an empty place: an act whose place is not verified is placed by its own
  target words, else 'an unverified place', and the procedure question never quotes empty words.
D160 (1) - D153 (2) rebuilt as a non-moving hold - is NOT built here: inside its ownership it releases 44361 and 43235
(a STOP; see DECISIONS D160), so D153 (2)'s move and its pins stand. Every outcome this repair moves is a hold, an added
question or a wording change against f9013e12e, and no outcome it moves drops a question or a listing against
e5628be56 or 4f82e5056. The installed release c2e53f8e's outputs are named in each test (engine.assess as
tests/test_harness_engine.py drives it, and jobs._assess_child: they agree on every probe row). Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import classes, events, wording
from tests.test_interpretation_events import asked, check, proposal
from tests.test_interpretation_identity import tg
from tests.test_interpretation_r5_enteroscopy_route import held, ready
from tests.test_interpretation_r5d_enteroscopy import (ELSEWHERE, J_POUCH, PEG_ENTRY, PEG_LINE, POUCH, RYGB_ENTRY,
                                                       code_of, family_of_e3, picked, pouch_entry, pouchoscopy,
                                                       routes_of, small_bowel)
from tests.test_interpretation_r5e_enteroscopy import DISTAL, J_AND_RYGB, biopsied

THROUGH_THE_POUCH = 'The enteroscope was advanced through the pouch and the Roux limb into the proximal ileum.'
ROUTED = 'was advanced through the anus into the J-pouch'
SMALL_GASTRIC_POUCH = 'The patient has an ileal J-pouch and a small gastric pouch.'


def routed_exam(anatomy_line: str, anatomy, exam_line: str = THROUGH_THE_POUCH):
    """round 5d's rygb_exam with the examination's own sentence ``exam_line`` as its kind words (B/fb07's attested
    shape: the whole sentence), the review's rv_cases.rygb_exam."""
    return small_bowel('SINGLE-BALLOON ENTEROSCOPY REPORT', 'Procedure: Single-balloon enteroscopy.',
                       'Single-balloon enteroscopy', anatomy_line, exam_line, 'ileum', 'proximal ileum',
                       'Biopsies of an ulcer in the proximal ileum were taken with cold forceps.',
                       'an ulcer in the proximal ileum', anatomy=anatomy, scope_words='enteroscope',
                       kind_words=exam_line)


def unverified(words: str) -> dict:
    """An altered entry Gemini filed whose words do not verify its landmark (state unverified)."""
    return {'state': 'altered', 'landmark': 'stomach' if words == 'RYGB' else 'jejunum', 'words': words,
            'passages': ['P5']}


# --- (2) problem 4: beside a gastric pouch or bypass, any pouch route phrase is a doubted route ------------------------

class DoubtedPouchRoute(SimpleTestCase):
    def doubted(self, inv, text, *, reached_words='proximal ileum'):
        """44386 held with the route question (extent), 44385 keeping its extent question beside base_included, and
        44386 beside 44377 asking extent beside competing_codes."""
        held(self, code_of(inv, text, '44386', 'P7'), classes.POUCH, 'ileum', reached_words, classes.ROUTE_FORM,
             through=POUCH)
        p = code_of(inv, text, '44385', 'P6')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included', 'extent']))
        p = proposal(picked(inv, text, (('44386', 'P7'), ('44377', 'P7'))), '44386')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['competing_codes', 'extent']))

    def test_d160_any_pouch_phrase_beside_a_j_pouch_and_a_bypass_is_a_doubted_route(self):
        """Problem 4 (critical-class, pre-existing since D148 (1)): 'The patient has an ileal J-pouch and a Roux-en-Y
        gastric bypass.' with 'The enteroscope was advanced through the pouch and the Roux limb into the proximal
        ileum.' - no gastric word between, so D153's cut never fired. f9013e12e and 4f82e5056: 44386 READY, 44385 and
        44386 beside 44377 without the extent question. Now 44386 is held with the route question (extent), as
        e5628be56 and c2e53f8e hold it, and the extent question returns to both. The same for 'via the pouch', 'through
        the J-pouch' and 'into the pouch and on to the proximal ileum'."""
        for exam_line in (THROUGH_THE_POUCH, 'The enteroscope was advanced via the pouch into the proximal ileum.',
                          'The enteroscope was advanced through the J-pouch into the proximal ileum.',
                          'The enteroscope was advanced into the pouch and on to the proximal ileum.'):
            inv, text = routed_exam(J_AND_RYGB, (pouch_entry('ileal J-pouch'), RYGB_ENTRY), exam_line)
            reading = events.Reading.of(inv)
            with self.subTest(exam_line=exam_line):
                self.assertEqual(routes_of(inv), (POUCH, frozenset()))
                self.assertEqual(classes.gastric_beside(reading.encounter), 'bypass')
                self.assertEqual(classes.examination_route(reading.events['E1'], 'bypass'), ('', ''))
                self.assertEqual(classes.examination_route(reading.events['E1'])[0], classes.THROUGH_POUCH)
                self.doubted(inv, text)

    def test_d160_beside_a_small_gastric_pouch_entry_too(self):
        """A gastric pouch entry (the attested 'small gastric pouch', a pouch entry typed gastric by its own words) is
        the other pouch: the same phrase holds 44386 (extent) as e5628be56 and c2e53f8e hold it (f9013e12e READY)."""
        inv, text = routed_exam(SMALL_GASTRIC_POUCH, (pouch_entry('ileal J-pouch'), pouch_entry('small gastric pouch')))
        self.assertEqual(classes.gastric_beside(events.Reading.of(inv).encounter), 'bypass')
        self.doubted(inv, text)

    def test_d160_the_j_pouchs_own_route_beside_a_bypass_is_a_doubted_route(self):
        """'whatever its words': the pouchoscopy whose status words name the J-pouch ('was advanced through the anus
        into the J-pouch') beside the bypass entry, or beside the small gastric pouch entry - 44386 held (extent), as
        e5628be56 holds it and c2e53f8e holds it (performed_status, extent); f9013e12e and 4f82e5056 READY (D148's
        release, withdrawn here for this anatomy only)."""
        for anatomy_line, anatomy in ((J_AND_RYGB, (pouch_entry('ileal J-pouch'), RYGB_ENTRY)),
                                      (SMALL_GASTRIC_POUCH, (pouch_entry('ileal J-pouch'),
                                                             pouch_entry('small gastric pouch')))):
            inv, text = pouchoscopy(anatomy_line, anatomy, pouch_words='J-pouch', status_words=ROUTED)
            with self.subTest(anatomy=[entry['words'] for entry in anatomy]):
                self.assertEqual(classes.gastric_beside(events.Reading.of(inv).encounter), 'bypass')
                held(self, code_of(inv, text, '44386', 'P7'), classes.POUCH, 'ileum', 'pre-pouch ileum',
                     classes.ROUTE_FORM, through=POUCH)
                p = code_of(inv, text, '44385', 'P6')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included', 'extent']))

    def test_d160_a_bypass_entry_not_verified_is_a_doubt_too(self):
        """D87: an altered entry whose words do not verify its landmark ('Roux limb' at the jejunum, 'RYGB' at the
        stomach: state unverified) still names a bypass, so it gates the same hold (fail-closed: it only holds). On
        every new-path tree before D160, 44386 READY; c2e53f8e holds it (extent)."""
        for words in ('Roux limb', 'RYGB'):
            inv, text = routed_exam(f'The patient has an ileal J-pouch and a {words}.',
                                    (pouch_entry('ileal J-pouch'), unverified(words)))
            reading = events.Reading.of(inv)
            with self.subTest(words=words):
                self.assertEqual(reading.encounter['anatomy'][1]['state'], 'unverified')
                self.assertEqual(classes.gastric_beside(reading.encounter), 'bypass')
                held(self, code_of(inv, text, '44386', 'P7'), classes.POUCH, 'ileum', 'proximal ileum',
                     classes.ROUTE_FORM, through=POUCH)

    def test_d160_without_a_gastric_pouch_or_bypass_the_route_reads_as_before(self):
        """The controls, unchanged on every new-path tree: the J-pouch alone ('into the J-pouch': 44386 READY; 'through
        the pouch and the Roux limb': 44386 READY, round 5c's problem 5 residual - c2e53f8e holds both); the J-pouch
        beside the attested PEG entry (no gastric pouch, no bypass: 'gastric', D153's cut only) with the J-pouch's own
        route - D148's release, 44386 READY; and an oral enteroscopy beside the J-pouch and the bypass ('was advanced
        orally'), whose route no pouch phrase states - 44377 READY."""
        inv, text = pouchoscopy(J_POUCH[0], (pouch_entry('ileal J-pouch'),), pouch_words='J-pouch',
                                status_words=ROUTED)
        self.assertEqual(classes.gastric_beside(events.Reading.of(inv).encounter), '')
        ready(self, code_of(inv, text, '44386', 'P7'))
        inv, text = routed_exam(J_POUCH[0], (pouch_entry('ileal J-pouch'),))
        ready(self, code_of(inv, text, '44386', 'P7'))
        inv, text = pouchoscopy(J_POUCH[0], (pouch_entry('ileal J-pouch'), PEG_ENTRY), pouch_words='J-pouch',
                                status_words=ROUTED, extra=(PEG_LINE,))
        self.assertEqual(classes.gastric_beside(events.Reading.of(inv).encounter), 'gastric')
        ready(self, code_of(inv, text, '44386', 'P7'))
        inv, text = small_bowel('SINGLE-BALLOON ENTEROSCOPY REPORT', 'Procedure: Single-balloon enteroscopy.',
                                'Single-balloon enteroscopy', J_AND_RYGB,
                                'The enteroscope was advanced orally to the proximal ileum.', 'ileum', 'proximal ileum',
                                'Biopsies of an ulcer in the proximal ileum were taken with cold forceps.',
                                'an ulcer in the proximal ileum', anatomy=(pouch_entry('ileal J-pouch'), RYGB_ENTRY),
                                scope_words='enteroscope', status_words='was advanced orally',
                                kind_words='The enteroscope was advanced orally to the proximal ileum.')
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1'], 'bypass')[0], classes.ORAL)
        ready(self, code_of(inv, text, '44377', 'P7'))

    def test_d160_route_phrase_with_bypass_states_no_pouch_route(self):
        """route_phrase's ``gastric`` 'bypass': no pouch phrase states the route, whatever its words; the stoma's
        phrase is unchanged; 'gastric' (or D153's True) reads as D153 built it, and '' as D141 did."""
        for text in (THROUGH_THE_POUCH, 'was advanced through the anus into the J-pouch',
                     'The endoscope was advanced via the ileal pouch.', 'by way of the reservoir'):
            with self.subTest(text=text):
                self.assertIs(classes.route_phrase(text, classes.THROUGH_POUCH, 'bypass'), False)
                self.assertIs(classes.route_phrase(text, classes.THROUGH_POUCH, ''), True)
        for gastric in ('gastric', True):
            with self.subTest(gastric=gastric):
                self.assertIs(classes.route_phrase(ROUTED, classes.THROUGH_POUCH, gastric), True)
                self.assertIs(classes.route_phrase('through the small gastric pouch', classes.THROUGH_POUCH, gastric),
                              False)
        self.assertIs(classes.route_phrase('was advanced through the ileostomy', classes.THROUGH_STOMA, 'bypass'), True)


# --- (3) problem 5: the place question never names an empty place ------------------------------------------------------

class PlaceWording(SimpleTestCase):
    def test_d160_an_unverified_place_is_named_by_the_acts_own_words(self):
        """Problem 5 (low): problem 6's distal-duodenum biopsies at the second portion's landmark (target unverified),
        moved by D153 (2). f9013e12e asked 'The documented forceps biopsy (“the distal duodenum”) is at the , which the
        upper endoscopy of this encounter examines. ...'. Now the act's own words name the place, and the EGD is said
        only to be one that may examine it; the hold is unchanged (44361 performed_status, service.act_elsewhere)."""
        inv, text = biopsied(landmark='second_portion_duodenum')
        self.assertEqual((events.Reading.of(inv).events['E3']['target']['state'], family_of_e3(inv)),
                         ('unverified', 'gi.egd'))
        p = code_of(inv, text, '44361', 'P7')
        self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status),
                         ('needs_clarification', ['performed_status'], 'warn'))
        self.assertEqual(p.clarifications[0].question,
                         f'The documented forceps biopsy is at “{DISTAL}”, which the upper endoscopy of this encounter '
                         'may examine. Was forceps biopsy performed in the small-bowel enteroscopy on the date of '
                         'service?')
        self.assertEqual(check(p, ELSEWHERE).detail,
                         f'The forceps biopsy (cold forceps) is documented at “{DISTAL}”, which the upper endoscopy of '
                         'this encounter may examine, so CPT Studio reads it as an act of the upper endoscopy; 44361 '
                         'accounts for forceps biopsy in a small-bowel enteroscopy, which CPT Studio could not find in '
                         'the document.')
        p = code_of(inv, text, '44360', 'P6')
        self.assertIn(f'documented at “{DISTAL}”, which the upper endoscopy of this encounter may examine',
                      check(p, ELSEWHERE).detail)
        for spec in p.clarifications:
            self.assertNotIn('at the ,', spec.question + spec.reason)

    def test_d160_an_absent_target_is_an_unverified_place(self):
        """'Biopsies were taken with cold forceps.' with no target: the place is 'an unverified place', and 44360's
        procedure question quotes no empty words ('In which procedure was the forceps biopsy (“”) done?' at
        f9013e12e)."""
        inv, text = biopsied('Biopsies were taken with cold forceps.', 'not_stated', '', target=tg())
        self.assertEqual(events.Reading.of(inv).events['E3']['target']['state'], 'absent')
        p = code_of(inv, text, '44361', 'P7')
        self.assertEqual(p.clarifications[0].question,
                         'The documented forceps biopsy is at an unverified place, which the upper endoscopy of this '
                         'encounter may examine. Was forceps biopsy performed in the small-bowel enteroscopy on the '
                         'date of service?')
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((asked(p), p.clarifications[0].question),
                         (['procedure'], 'Is 44360 reported separately from forceps biopsy for this examination? In '
                                         'which procedure was the forceps biopsy done?'))

    def test_d160_a_verified_place_is_worded_as_before(self):
        """The control: the distal-duodenum biopsies at the generic duodenum's verified landmark (D153 (1)'s move) keep
        D114's words byte for byte."""
        inv, text = biopsied()
        p = code_of(inv, text, '44361', 'P7')
        self.assertEqual(p.clarifications[0].question,
                         f'The documented forceps biopsy (“{DISTAL}”) is at the duodenum, which the upper endoscopy of '
                         'this encounter examines. Was forceps biopsy performed in the small-bowel enteroscopy on the '
                         'date of service?')

    def test_d160_procedure_question_quotes_no_empty_words(self):
        """wording.procedure_question: empty or blank words are never quoted; words are quoted as before."""
        for words in ('', '   ', None):
            with self.subTest(words=words):
                self.assertEqual(wording.procedure_question('forceps biopsy', words),
                                 'In which procedure was the forceps biopsy done?')
        self.assertEqual(wording.procedure_question('ablation', 'Two gastric antral angioectasias'),
                         'In which procedure was the ablation (“Two gastric antral angioectasias”) done?')
