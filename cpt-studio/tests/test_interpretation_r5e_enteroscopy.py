"""DECISIONS D153 (the round-5d review of D148: gemini-migration/round5d/results-wf_2cb07bb8-45e.json
'review:enteroscopy4' problems 0, 1, 2 and 6, and 'repair:enteroscopy4' disagreement 2), SYNTHETIC, rebuilt from the
review's own documents as it describes them (its tools/refute5d.py was lost with /tmp: the EGD to the second portion and
the push enteroscopy to the proximal jejunum, with celiac biopsies 'of the distal duodenum', an angioectasia 'in the
second portion of the duodenum, just proximal to the third portion', the exchange sentence, and the biopsies at the
second portion's landmark whose words do not verify it) and from D148's disagreement 2 (an 'ileal J-pouch' beside a
'Roux-en-Y gastric bypass' or a 'small gastric pouch', and the Roux-en-Y enteroscopy 'through the small gastric pouch').
NARROWING ONLY - studio/interpretation/coverage.py (beyond_reach, coding_family) and classes.py (gastric_beside,
route_phrase's gastric word):
- (1, problems 0-2) an act's own target words never place it beyond the EGD's verified reach (the act-words arm of
  D148 is withdrawn; its reach-words arm and its removal of D141's shared-passage test stay): only the act's verified
  landmark does, as D141 reads it;
- (2, problem 6) an act Gemini files under the enteroscopy whose place is not verified is a doubt of family beside a
  done EGD: the EGD session's for coding, so it never makes an enteroscopy code READY by itself;
- (3, D148's disagreement 2) with the verified small-intestinal pouch beside a gastric pouch or bypass entry, a route
  phrase that names a gastric pouch is never the small-intestinal pouch's route.
Every outcome this repair moves is a hold, an added question or e5628be56's outcome restored, against 4f82e5056 and
e5628be56; the controls named are unchanged. The installed release c2e53f8e's outputs are named in each test
(engine.assess as tests/test_harness_engine.py drives it, and jobs._assess_child: they agree on every probe row).
Nothing is sent."""
from __future__ import annotations

import inspect

from django.test import SimpleTestCase

from studio.interpretation import classes, coverage, events
from tests.test_interpretation_events import asked, check, proposal
from tests.test_interpretation_identity import a, tg
from tests.test_interpretation_r5_enteroscopy_route import held, ready
from tests.test_interpretation_r5d_enteroscopy import (BASE, D3_LINE, D3_WORDS, ELSEWHERE, J_POUCH, PEG_ENTRY, PEG_LINE,
                                                       POUCH, RYGB_ENTRY, RYGB_EXAM, code_of, egd_push, family_of_e3,
                                                       picked, pouch_entry, pouchoscopy, routes_of, rygb_exam)

DISTAL_BX = 'Biopsies of the distal duodenum were taken with cold forceps to evaluate for celiac disease.'
DISTAL = 'the distal duodenum'
EXCHANGE_BX = ('Biopsies of the distal duodenum were taken with cold forceps, and the gastroscope was then exchanged '
               'for the enteroscope, which was advanced to the proximal jejunum.')
D3_PART = ('Push enteroscopy: The enteroscope was then advanced to the proximal jejunum, and an angioectasia in the '
           'third portion of the duodenum was treated with argon plasma coagulation.')
J_AND_RYGB = 'The patient has an ileal J-pouch and a Roux-en-Y gastric bypass.'
J_AND_GASTRIC_POUCH = 'The patient has an ileal J-pouch and a Roux-en-Y gastric bypass with a small gastric pouch.'


def biopsied(act_line: str = DISTAL_BX, landmark: str = 'duodenum', words: str = DISTAL, *, act_pid: str = 'P7',
             status: str = 'performed', status_words: str = 'were taken', target=None, then=None, **options):
    """round 5d's egd_push with E3 a cold-forceps biopsy (no lesion) at ``landmark`` with target words ``words``
    (``target`` replaces the target record whole; ``then`` edits the answer afterwards)."""
    def as_biopsy(value):
        e3 = value['events'][2]
        e3.update(kind=a('biopsy', 'Biopsies', [act_pid]), technique=a('cold_forceps', 'cold forceps', [act_pid]),
                  status=a(status, status_words, [act_pid]),
                  target=target if target is not None else tg('', landmark, words, [act_pid]))
        value['lesions'] = []
        if then is not None:
            then(value)
    return egd_push(act_line, act_pid, landmark=landmark, words=words, edit=as_biopsy, **options)


def exchanged(value):
    """The exchange shape (round 5d's problem-1 pin): the push examination's status and both procedures in P6."""
    value['events'][1]['status'] = a('performed', 'was advanced', ['P6'])
    value['events'][1]['procedure'] = a('enteroscopy', 'enteroscope', ['P6'])
    value['events'][2]['procedure'] = a('enteroscopy', 'enteroscope', ['P6'])


class Held(SimpleTestCase):
    def moved(self, inv, text, code: str, act_pid: str = 'P7', egd_facts=('base_included',)):
        """The act is the EGD session's for coding: ``code`` held (service.act_elsewhere, performed_status), and 43235
        held base_included alone and beside it."""
        self.assertEqual(family_of_e3(inv), 'gi.egd')
        p = code_of(inv, text, code, act_pid)
        self.assertEqual((p.bucket, p.status, asked(p), check(p, ELSEWHERE).status),
                         ('selected', 'needs_clarification', ['performed_status'], 'warn'))
        for chosen in ((('43235', 'P5'),), ((code, act_pid), ('43235', 'P5'))):
            p = proposal(picked(inv, text, chosen), '43235')
            with self.subTest(picks=[item for item, _ in chosen]):
                self.assertEqual((p.status, asked(p), check(p, BASE).status),
                                 ('needs_clarification', list(egd_facts), 'warn'))


# --- (1) problems 0, 1 and 2: an act's own words never place it beyond the EGD's verified reach -----------------------

class ActWordsWithdrawn(Held):
    def test_d153_distal_duodenum_biopsies_within_a_second_portion_reach_move(self):
        """Problem 0 (critical, introduced by D148): 'Biopsies of the distal duodenum were taken with cold forceps to
        evaluate for celiac disease.' on its own line, at the generic duodenum (verified), beside an EGD verified to the
        second portion. 'distal duodenum' is the post-bulbar duodenum a standard EGD samples, inside its verified
        reach. 4f82e5056 read it beyond the reach: 44361 and 43235 READY. Now it moves: 44361 held (performed_status),
        43235 base_included, as e5628be56 and c2e53f8e hold them (c2e53f8e READYs 43239; here 43239 stays held, a
        moved act supporting no EGD code - a recorded cost). The author's own form, 'An angioectasia in the distal
        duodenum was treated with argon plasma coagulation.', moves alike (44369 held)."""
        inv, text = biopsied()
        self.moved(inv, text, '44361')
        p = code_of(inv, text, '43239', 'P7')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']))
        words = 'An angioectasia in the distal duodenum'
        inv, text = egd_push(f'{words} was treated with argon plasma coagulation.', words=words)
        self.moved(inv, text, '44369')

    def test_d153_a_second_portion_lesion_whose_words_mention_a_later_portion_moves(self):
        """Problem 1 (critical, introduced by D148): one lesion, at the second portion's verified landmark, whose words
        mention a later portion - 'An angioectasia in the second portion of the duodenum, just proximal to the third
        portion, was treated ...', 'at the D2/D3 junction', 'at the junction of the second and third portion of the
        duodenum'. 4f82e5056: 44369 and 43235 READY. Now each moves: 44369 held, 43235 base_included, as e5628be56 and
        c2e53f8e (which READYs 43270)."""
        for sentence, words in (
                ('An angioectasia in the second portion of the duodenum, just proximal to the third portion, was treated '
                 'with argon plasma coagulation.',
                 'An angioectasia in the second portion of the duodenum, just proximal to the third portion'),
                ('An angioectasia at the D2/D3 junction was treated with argon plasma coagulation.',
                 'An angioectasia at the D2/D3 junction'),
                ('An angioectasia at the junction of the second and third portion of the duodenum was treated with argon '
                 'plasma coagulation.', 'An angioectasia at the junction of the second and third portion of the '
                                        'duodenum')):
            inv, text = egd_push(sentence, landmark='second_portion_duodenum', words=words)
            with self.subTest(words=words):
                self.moved(inv, text, '44369')

    def test_d153_the_distal_duodenum_biopsies_before_the_exchange_move(self):
        """Problem 2 (critical against the document and c2e53f8e, pre-existing): 'Biopsies of the distal duodenum were
        taken with cold forceps, and the gastroscope was then exchanged for the enteroscope, which was advanced to the
        proximal jejunum.' - the gastroscope took them. e5628be56 (by D141's shared passage) and 4f82e5056 (by the
        act's words): 44361 and 43235 READY. Now it moves: 44361 held, 43235 base_included, as c2e53f8e (which READYs
        43239)."""
        inv, text = biopsied(act_pid='P6', push_line=EXCHANGE_BX, then=exchanged)
        self.moved(inv, text, '44361', 'P6')

    def test_d153_the_genuine_third_portion_act_is_held_a_returning_cost(self):
        """The cost the spec names: an act whose words name the third portion, beside an EGD verified to the second
        portion, moves like any act at the duodenum's landmarks - on its own line (44369 held, 43235 base_included, as
        e5628be56 and c2e53f8e hold them), and told in the push enteroscopy's own sentence at the generic duodenum or
        the second portion's landmark (44369 held, 43235 base_included: COSTS - c2e53f8e READYs both there, and
        e5628be56 READYed them at the generic duodenum)."""
        inv, text = egd_push(D3_LINE, words=D3_WORDS)
        self.moved(inv, text, '44369')
        for landmark in ('duodenum', 'second_portion_duodenum'):
            inv, text = egd_push(act_pid='P6', push_line=D3_PART, landmark=landmark,
                                 words='an angioectasia in the third portion of the duodenum')
            with self.subTest(landmark=landmark):
                self.moved(inv, text, '44369', 'P6')

    def test_d153_beyond_reach_reads_the_landmark_and_the_reachs_own_words_only(self):
        """beyond_reach takes no act words (D141's signature); its reach-words arm stays: a reach at the second
        portion's landmark whose own words name the third portion is never short (fail-closed). A reach at the bulb is
        short of the second portion, one in the stomach of the duodenum (D141)."""
        self.assertEqual(list(inspect.signature(coverage.beyond_reach).parameters), ['examination', 'landmark'])
        self.assertEqual(coverage.DUODENAL_PORTIONS, ('duodenal_bulb', 'second_portion_duodenum',
                                                      'beyond_second_portion'))

        def reach(value: str, words: str) -> dict:
            return {'extent': {'value': value, 'state': 'verified', 'open': False, 'words': {'text': words}}}

        for examination, landmark, expected in (
                (reach('duodenal_bulb', 'duodenal bulb'), 'second_portion_duodenum', True),
                (reach('gastric_antrum', 'gastric antrum'), 'duodenum', True),
                (reach('second_portion_duodenum', 'second portion of the duodenum'), 'second_portion_duodenum', False),
                (reach('second_portion_duodenum', 'second portion of the duodenum'), 'duodenum', False),
                (reach('second_portion_duodenum', 'third portion of the duodenum'), 'second_portion_duodenum', False),
                (reach('duodenal_bulb', 'duodenal bulb'), 'duodenum', False)):
            with self.subTest(reach=examination['extent']['value'], landmark=landmark):
                self.assertIs(coverage.beyond_reach(examination, landmark), expected)


# --- (2) problem 6: a place not verified is a doubt of family beside a done EGD ----------------------------------------

class PlaceNotVerified(Held):
    def test_d153_an_unverified_target_beside_a_done_egd_is_a_doubt_of_family(self):
        """Problem 6 (pre-existing, critical-class): the distal-duodenum biopsies at the second portion's landmark,
        whose forms do not take 'distal duodenum' - the target unverified. e5628be56 and 4f82e5056 kept Gemini's family:
        44361 and 43235 READY. Now the act is the EGD session's: 44361 held (performed_status, the place question),
        43235 base_included alone and beside 44361, as c2e53f8e holds both (c2e53f8e READYs 43239, which stays held:
        a cost). 44360 alone asks the base rule's question and the act's in one clarification (fact procedure; c2e53f8e
        READY: a cost)."""
        inv, text = biopsied(landmark='second_portion_duodenum')
        self.assertEqual(events.Reading.of(inv).events['E3']['target']['state'], 'unverified')
        self.moved(inv, text, '44361')
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status),
                         ('needs_clarification', ['procedure'], 'warn'))
        self.assertTrue(p.clarifications[0].question.startswith(
            'Is 44360 reported separately from forceps biopsy for this examination? In which procedure was the forceps '
            'biopsy'))
        self.assertEqual(asked(code_of(inv, text, '43239', 'P7')), ['performed_status'])

    def test_d153_an_act_whose_target_is_absent_is_a_doubt_of_family_too(self):
        """'Not verified' as D114 read it (mapping.target_landmark ''): a target Gemini left absent - 'Biopsies were
        taken with cold forceps.' on its own line, no place - is no verified place either. 4f82e5056 and e5628be56:
        44361 READY and 43235 READY. Now 44361 is held (performed_status), as c2e53f8e holds it, and 43235 base_included
        (c2e53f8e READY: a cost)."""
        inv, text = biopsied('Biopsies were taken with cold forceps.', 'not_stated', '', target=tg())
        self.assertEqual(events.Reading.of(inv).events['E3']['target']['state'], 'absent')
        self.moved(inv, text, '44361')

    def test_d153_an_unverified_small_bowel_target_is_held_a_cost(self):
        """Fail-closed: the place of 'Two jejunal angioectasias were treated with argon plasma coagulation.' filed with
        target words that do not stand in its passage is not verified, so the act is a doubt of family too: 44369 held
        and 43235 base_included, where e5628be56, 4f82e5056 and c2e53f8e READY both - a recorded cost. With the words
        standing, the jejunal act stays the enteroscopy's (44369 READY)."""
        jejunal = 'Two jejunal angioectasias were treated with argon plasma coagulation.'
        inv, text = egd_push(jejunal, landmark='jejunum', words='Two proximal jejunal angioectasias',
                             status_words='were treated')
        self.moved(inv, text, '44369')
        inv, text = egd_push(jejunal, landmark='jejunum', words='Two jejunal angioectasias', status_words='were treated')
        self.assertEqual(family_of_e3(inv), 'gi.enteroscopy')
        ready(self, code_of(inv, text, '44369', 'P7'))

    def test_d153_without_a_done_egd_the_act_keeps_its_family(self):
        """An EGD planned and not done: the unverified act keeps Gemini's family, as before (44361 READY on every tree
        but c2e53f8e, which holds it)."""
        def planned(value):
            value['events'][0]['status'] = a('planned', 'was advanced', ['P5'])
        inv, text = biopsied(landmark='second_portion_duodenum', then=planned)
        self.assertEqual(family_of_e3(inv), 'gi.enteroscopy')
        ready(self, code_of(inv, text, '44361', 'P7'))

    def test_d153_an_uncertain_or_denied_act_releases_and_excludes_nothing(self):
        """The same doubt moves an act of any status, as D114 moves one. An uncertain one ('may have been taken'): 44361
        stays held (performed_status), and 43235 is now held base_included (the act in doubt in the EGD's session;
        e5628be56, 4f82e5056 and c2e53f8e READY: a cost). A denial ('No biopsies of the distal duodenum were taken.')
        changes nothing: 44361 excluded, 43235 and 44360 READY, on every tree."""
        inv, text = biopsied('Biopsies of the distal duodenum may have been taken with cold forceps.',
                             'second_portion_duodenum', status='uncertain', status_words='may have been taken')
        self.assertEqual(family_of_e3(inv), 'gi.egd')
        self.assertEqual(asked(code_of(inv, text, '44361', 'P7')), ['performed_status'])
        p = proposal(picked(inv, text, (('43235', 'P5'),)), '43235')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
        inv, text = biopsied('No biopsies of the distal duodenum were taken.', 'second_portion_duodenum',
                             status='not_performed', status_words='No biopsies of the distal duodenum were taken')
        self.assertEqual(family_of_e3(inv), 'gi.egd')
        p = code_of(inv, text, '44361', 'P7')
        self.assertEqual((p.bucket, p.status), ('excluded', 'excluded'))
        for code, pid in (('43235', 'P5'), ('44360', 'P6')):
            with self.subTest(code=code):
                ready(self, code_of(inv, text, code, pid))


# --- (3) D148's disagreement 2: a gastric pouch's route phrase is never the small-intestinal pouch's route --------------

class GastricPouchRoute(SimpleTestCase):
    def test_d153_a_gastric_pouch_phrase_beside_a_j_pouch_and_a_bypass_is_no_pouch_route(self):
        """D148's disagreement 2 (a READY on the wrong act, introduced by D148 (1)): 'The patient has an ileal J-pouch and
        a Roux-en-Y gastric bypass.' (an 'ileal J-pouch' entry and a 'Roux-en-Y gastric bypass' entry), or the J-pouch
        beside a 'small gastric pouch' entry, with the Roux-en-Y enteroscopy 'The enteroscope was advanced through the
        small gastric pouch and the Roux limb into the proximal ileum.' 4f82e5056: 44386 READY, and 44385 (beside its
        biopsy) and 44386 beside 44377 without the extent question. Now the phrase states no route: 44386 is held with
        the route question (extent), as e5628be56 and c2e53f8e hold it (both: extent), and the extent question returns
        to 44385 and to 44386 beside 44377."""
        for anatomy_line, anatomy in ((J_AND_RYGB, (pouch_entry('ileal J-pouch'), RYGB_ENTRY)),
                                      (J_AND_GASTRIC_POUCH, (pouch_entry('ileal J-pouch'),
                                                             pouch_entry('small gastric pouch')))):
            inv, text = rygb_exam(anatomy_line, anatomy)
            reading = events.Reading.of(inv)
            with self.subTest(anatomy=[entry['words'] for entry in anatomy]):
                self.assertEqual(routes_of(inv), (POUCH, frozenset()))
                self.assertTrue(classes.gastric_beside(reading.encounter))
                self.assertEqual(classes.examination_route(reading.events['E1'], True), ('', ''))
                self.assertEqual(classes.examination_route(reading.events['E1'])[0], classes.THROUGH_POUCH)
                held(self, code_of(inv, text, '44386', 'P7'), classes.POUCH, 'ileum', 'proximal ileum',
                     classes.ROUTE_FORM, through=POUCH)
                held(self, code_of(inv, text, '44377', 'P7'), classes.ILEAL, 'ileum', 'proximal ileum',
                     classes.ROUTE_FORM, through=POUCH)
                p = code_of(inv, text, '44385', 'P6')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included', 'extent']))
                p = proposal(picked(inv, text, (('44386', 'P7'), ('44377', 'P7'))), '44386')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['competing_codes', 'extent']))

    def test_d153_the_phrase_reads_gastric_words_between_the_route_word_and_the_pouch(self):
        """route_phrase's ``gastric``: a pouch phrase whose words between name a gastric pouch ends there; the J-pouch's
        own phrase and the stoma's are unchanged, and without ``gastric`` the phrase reads as D141 built it."""
        for text, route, gastric, expected in (
                (RYGB_EXAM, classes.THROUGH_POUCH, True, False),
                (RYGB_EXAM, classes.THROUGH_POUCH, False, True),
                ('The enteroscope was advanced via the stomach pouch.', classes.THROUGH_POUCH, True, False),
                ('The enteroscope was advanced through the bypass pouch.', classes.THROUGH_POUCH, True, False),
                ('was advanced through the anus into the J-pouch', classes.THROUGH_POUCH, True, True),
                ('was advanced through the anus into the ileal pouch', classes.THROUGH_POUCH, True, True),
                ('was advanced through the gastric stoma', classes.THROUGH_STOMA, True, True)):
            with self.subTest(text=text, gastric=gastric):
                self.assertIs(classes.route_phrase(text, route, gastric), expected)
        self.assertTrue(all(' ' not in word for word in classes.GASTRIC_POUCH_WORDS))  # read token by token

    def test_d153_the_j_pouchs_own_route_beside_a_bypass_is_unchanged(self):
        """The control D148 released and D153 keeps (D148's own-words typing stands): the pouchoscopy whose status words
        state the J-pouch's route ('was advanced through the anus into the J-pouch') beside the bypass entry - 44386
        READY, the code the document supports (c2e53f8e and e5628be56 hold it)."""
        routed = 'was advanced through the anus into the J-pouch'
        inv, text = pouchoscopy(J_AND_RYGB, (pouch_entry('ileal J-pouch'), RYGB_ENTRY), pouch_words='J-pouch',
                                status_words=routed)
        self.assertTrue(classes.gastric_beside(events.Reading.of(inv).encounter))
        ready(self, code_of(inv, text, '44386', 'P7'))

    def test_d153_without_both_entries_the_route_phrase_reads_as_before(self):
        """The narrowest form: the J-pouch alone (round 5c's problem 5: 44386 READY on every new-path tree, c2e53f8e
        holds it - recorded, unchanged), an untyped pouch beside the bypass (a doubt: 44377 the class question naming
        the route, as D148 pinned it), and the bypass's 'small gastric pouch' alone (no pouch route) read the phrase as
        before; gastric_beside needs the verified small-intestinal pouch and an entry naming a gastric pouch or
        bypass."""
        inv, text = rygb_exam(J_POUCH[0], (pouch_entry('ileal J-pouch'),))
        self.assertFalse(classes.gastric_beside(events.Reading.of(inv).encounter))
        ready(self, code_of(inv, text, '44386', 'P7'))
        inv, text = rygb_exam('The patient has a Roux-en-Y gastric bypass with a small gastric pouch.',
                              (RYGB_ENTRY, pouch_entry('pouch')))
        self.assertFalse(classes.gastric_beside(events.Reading.of(inv).encounter))
        held(self, code_of(inv, text, '44377', 'P7'), classes.ILEAL, 'ileum', 'proximal ileum', classes.CLASS_FORM,
             route=classes.THROUGH_POUCH, route_words=RYGB_EXAM)
        inv, _ = rygb_exam('The patient has a Roux-en-Y gastric bypass with a small gastric pouch.',
                           (RYGB_ENTRY, pouch_entry('small gastric pouch')))
        self.assertFalse(classes.gastric_beside(events.Reading.of(inv).encounter))
        inv, _ = pouchoscopy(J_POUCH[0], (pouch_entry('ileal J-pouch'), PEG_ENTRY), extra=(PEG_LINE,))
        self.assertTrue(classes.gastric_beside(events.Reading.of(inv).encounter))  # the PEG's 'gastric': fail-closed
