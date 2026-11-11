"""DECISIONS D144 (the review of D131-D134, round5c/review_currency3.json problems 0, 1, 4 and 7), SYNTHETIC: a same-day
word an anteriority word governs places nothing; an anaphoric frame is no same-day word for a verified other's act; an
act done on the date but for its procedure sets the visit apart; three kept pins are named by what they assert.

DECISIONS D151 (round 5e, narrowing only; the review of D144, round5d 'review:currency4' problems 0-5) WITHDREW
D144's first three rules below: the anteriority rule made 99213 READY where e5628be56 and c2e53f8e hold it, the
anaphoric hiding made it READY where e5628be56 holds it, and ``unidentified`` set the visit apart where e5628be56 and
c2e53f8e list it (tests/test_interpretation_r5e_currency.py pins the review's own inputs). Each pin here whose
expectation D151 changes back asserts e5628be56's outcome again and is named by what it asserts (its docstring names
its former name); the costs D144 had cured - Inputs A, B and C, D112's 'Earlier that same day', D81's banding whose
procedure Gemini left 'unknown' - are held or listed again where c2e53f8e is READY or sets the visit apart. The
problem-7 renames stand.

- Problem 0: D131 turns every character that is not a letter or a digit into a space, so "today's" holds "today" and a
  VERIFIED earlier act whose own time words say "prior to today's visit" was placed ON the date: the RUQ note's CT
  (finding 16's class) and prompt.py's occasion sentence "Prior to today's visit, she had undergone the following
  procedures:" held 99213 with separate_em, and "I performed her last colonoscopy two years prior to today's visit" was
  read as a colonoscopy done today, which set the visit item apart. c2e53f8e is READY on all three and lists the visit.
  Now a SAME_DAY_WORDS entry whose words immediately before it are 'prior to', 'before', 'previous to', 'preceding',
  'ahead of', 'until' or 'till' (facts.ANTERIORITY_WORDS) places nothing, and the act's own time value decides as
  before D131.
- Problem 4: 'earlier that same day', 'later that same day' and 'that same day' are anaphoric frames (D132), yet
  SAME_DAY_WORDS' 'same day' placed them ON the date for every performer, so D112's outside EGD worded "Earlier that
  same day ... at that hospital" (other_facility verified) held 99213 where c2e53f8e is READY. Now, for an act whose
  performer IS verified other, the words of every lexicon.ANAPHORIC_FRAMES entry are not read as SAME_DAY_WORDS.
- Problem 1: D134 set the visit apart only on ProcedureDay.labels, so D81's banding 'Rubber band ligation of one
  internal hemorrhoid was performed in the office today.' whose procedure Gemini left 'unknown' (status, performer and
  time usable and positive) left the visit listed, where c2e53f8e and 46e461e7f set it apart. ProcedureDay.unidentified
  now holds such an act (done but for its PROCEDURE), and only coverage.reconcile's office-visit rule reads it. An act
  read by its statement (D130: only ever possible) and an act otherwise only possibly done keep the visit listed.
- Problem 7: three kept pins renamed by what they assert (names and docstrings only).

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). The installed release's outputs (c2e53f8e: engine.assess with gi_context.extract_context,
merge_user_values office/established and detect.route on 2026-11-09, as tests/test_harness_engine.py drives it) quoted
in the docstrings were measured on byte-identical texts. Nothing is sent."""
from __future__ import annotations

import inspect

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, facts, lexicon, overlay
from studio.validation import checks
from tests import test_interpretation_r5_em, test_interpretation_r5_em2
from tests.test_interpretation_events import asked, check, inventory, proposal, response, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_families import MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r4_em_same_day import (MRCP_PLAN, OTHER_GI_LABEL, RUQ_VISIT, THIRTY,
                                                      held_for_separate_em, ready_with_no_procedure_day)
from tests.test_interpretation_r5_em import CYST, MELENA_VISIT, NO_PROPOSAL, NON_GI_LABEL, excision, office
from tests.test_interpretation_r5_em2 import POSSIBLY, VISIT_WORDS, note, other
from tests.test_interpretation_r5c_currency import (EGD_LABEL, FLEX_SIG_LABEL, NOT_LISTED, SEPARATE, SEPARATE_LINE,
                                                    day_of, em, melena, no_em, procedure_day, reading_of)

DAY = '2026-11-09'
HEM = tg('', 'anal_canal', 'one internal hemorrhoid', ['P2'])
BAND = 'Rubber band ligation of one internal hemorrhoid was performed in the office today.'
HEADING = "Prior to today's visit, she had undergone the following procedures:"
LAST_COLONOSCOPY = "I performed her last colonoscopy two years prior to today's visit, which was normal."
OUTSIDE_ADMISSION = 'On 10/30/2026 she was admitted to another hospital for melena.'


def ruq_ct(words: str) -> tuple:
    """(inventory, text) of problem 0's Input A (finding 16's class): the RUQ office note - the visit (E0, V1) and its
    total time (V2), the indication P2 'a CT abdomen obtained <words> showed a dilated common bile duct.' (E1: kind
    other 'CT abdomen', procedure not_gi, 'obtained', earlier_encounter worded ``words``, performer unknown) and the
    plan (P3) - byte-identical to the review's rv_cases5.py."""
    e0 = act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
             procedure=a('office_em', 'Office visit', ['V1']))
    study = act('E1', 'P2', 'other', 'CT abdomen', status_words='obtained', procedure=a('not_gi', 'CT abdomen', ['P2']),
                time=a('earlier_encounter', words, ['P2']), performer=a('unknown'))
    line = f'Indication: right upper quadrant pain; a CT abdomen obtained {words} showed a dilated common bile duct.'
    return inventory({'V1': RUQ_VISIT, 'V2': THIRTY, 'P2': line, 'P3': MRCP_PLAN}, events=[e0, study], visits=[
        {'event': 'E0', 'basis': a('total_time', '30 minutes', ['V2']), 'separately_identifiable': a('not_stated')}])


def history_list(performer: dict, stated: bool = False) -> tuple:
    """(inventory, text) of problem 0's Input B (prompt.py's occasion sentence): the visit lines, H1 HEADING and two
    history acts - a colonoscopy (E1, P2) and an upper endoscopy (E2, P4) - each timed earlier_encounter by H1's
    sentence, by ``performer``; with ``stated``, the visit's separately identifiable statement (P5) - byte-identical to
    the review's rv_cases2.py."""
    time = a('earlier_encounter', HEADING, ['H1'])
    e1 = act('E1', 'P2', 'examination', 'Colonoscopy', status_words='had undergone',
             procedure=a('colonoscopy', 'Colonoscopy', ['P2']), time=time, performer=performer)
    e2 = act('E2', 'P4', 'examination', 'Upper endoscopy', status_words='had undergone',
             procedure=a('egd', 'Upper endoscopy', ['P4']), time=time, performer=performer)
    lines = {'V1': VISIT, 'V2': TIME, **({'P5': SEPARATE_LINE} if stated else {}), 'H1': HEADING,
             'P2': 'Colonoscopy, which was normal.', 'P4': 'Upper endoscopy, which showed mild gastritis.', 'P3': PLAN}
    facts_ = {**visit_facts(), **({'separately_identifiable': a('stated', SEPARATE, ['P5'])} if stated else {})}
    return inventory(lines, events=[visit(), e1, e2], visits=[facts_])


def last_colonoscopy(performer: dict, status_words: str = 'I performed', line: str = LAST_COLONOSCOPY) -> tuple:
    """(inventory, text) of problem 0's Input C: D81's office lines with P2 ``line`` (E1: gi.colonoscopy, kind
    examination, earlier_encounter "two years prior to today's visit", by ``performer``) - byte-identical to the
    review's rv_cases.py R1b."""
    return office(line, act('E1', 'P2', 'examination', 'colonoscopy', status_words=status_words,
                            procedure=a('colonoscopy', 'colonoscopy', ['P2']),
                            time=a('earlier_encounter', "two years prior to today's visit", ['P2']),
                            performer=performer))


def flex_sig_by_i(words: str, line: str) -> tuple:
    """(inventory, text) of D81's office lines with the documenting team's flexible sigmoidoscopy (E1, P2, by 'I'),
    earlier_encounter worded ``words``."""
    return office(line, act('E1', 'P2', 'examination', 'flexible sigmoidoscopy', status_words='I performed',
                            procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P2']),
                            time=a('earlier_encounter', words, ['P2']), performer=a('documenting_team', 'I', ['P2'])))


def banding(procedure: dict, **changes) -> dict:
    """D81's office banding (E1, P2): kind band_ligation, 'was performed', its procedure ``procedure``; the current
    encounter and the documenting team by the frame defaults unless ``changes`` say."""
    return act('E1', 'P2', 'band_ligation', 'Rubber band ligation', status_words='was performed', procedure=procedure,
               target=HEM, **changes)


def second_review(inv, text):
    """The assessment with no E/M proposed and a second review (fable) selecting 99213 for the visit item."""
    return run(inv, text, [], user_values=MEMBER, second=response(text, [('99213', VISIT)], provider='fable'),
               second_scope={'items': [NO_PROPOSAL]})


# --- problem 0: a same-day word an anteriority word governs places nothing -------------------------------------------

class D144AnteriorityWords(SimpleTestCase):
    """D144 (problem 0), withdrawn by DECISIONS D151: 'prior to today's visit' holds 'today' again, as at D131."""

    def test_d144_problem_0_input_a_the_ct_obtained_prior_to_todays_visit(self):
        """Input A, byte-identical: the RUQ office note, 'a CT abdomen obtained prior to today's visit' (verified by its
        'prior'). c2e53f8e: READY, the visit listed and a second review's 99213 READY. D144 made it OFF and READY;
        DECISIONS D151 withdrew that, so it is e5628be56's (D131) again: ON, a possible service outside the GI
        profiles, 99213 held with separate_em, the visit listed and a second review's 99213 added held - a returning
        cost. Control 'prior to this visit': OFF and READY on c2e53f8e, e5628be56, 4f82e5056 and now. Named
        '..._is_off_the_date' until D151."""
        inv, text = ruq_ct("prior to today's visit")
        self.assertEqual(reading_of(inv).events['E1']['time']['state'], 'verified')
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(NON_GI_LABEL,)))
        held_for_separate_em(self, em(inv, text, RUQ_VISIT), NON_GI_LABEL)
        self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
        p = proposal(run(inv, text, [], user_values=MEMBER, second=response(
            text, [('99213', RUQ_VISIT)], provider='fable'), second_scope={'items': [NO_PROPOSAL]}), '99213')
        self.assertEqual((p.bucket, p.support['origin'], p.status, asked(p)),
                         ('selected', 'second_review', 'needs_clarification', ['separate_em']))
        inv, text = ruq_ct('prior to this visit')
        self.assertEqual(reading_of(inv).events['E1']['time']['state'], 'verified')
        self.assertEqual(day_of(inv), facts.OFF)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay())
        ready_with_no_procedure_day(self, em(inv, text, RUQ_VISIT))
        self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
        p = proposal(run(inv, text, [], user_values=MEMBER, second=response(
            text, [('99213', RUQ_VISIT)], provider='fable'), second_scope={'items': [NO_PROPOSAL]}), '99213')
        self.assertEqual((p.bucket, p.support['origin'], p.status), ('selected', 'second_review', 'ready'))

    def test_d144_problem_0_input_b_the_occasion_sentence_prior_to_todays_visit(self):
        """Input B, byte-identical: "Prior to today's visit, she had undergone the following procedures:" as the time
        words of a colonoscopy and an EGD (performer unknown, or the frame's documenting team). c2e53f8e and 46e461e7f:
        READY. D144 made both OFF and 99213 READY; DECISIONS D151 withdrew that, so it is e5628be56's again: both ON
        and only possible, 99213 held with separate_em ('Colonoscopy and Upper GI endoscopy ... possibly performed');
        with the stated separately identifiable line READY with the modifier 25 consideration, beside a same-day fact
        the document does not support (c2e53f8e: READY without it) - returning costs."""
        for performer in (a('unknown'), a('documenting_team')):
            for stated in (False, True):
                with self.subTest(performer=performer['value'], stated=stated):
                    inv, text = history_list(performer, stated)
                    reading = reading_of(inv)
                    self.assertEqual([facts.day_of(reading.events[eid], DAY) for eid in ('E1', 'E2')],
                                     [facts.ON, facts.ON])
                    self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=('Colonoscopy', EGD_LABEL)))
                    p = em(inv, text)
                    self.assertEqual((p.bucket, p.status, asked(p)),
                                     ('selected', 'ready', []) if stated
                                     else ('selected', 'needs_clarification', ['separate_em']))
                    self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
                    self.assertIn('possibly performed', check(p, 'em.same_day_procedure').detail)

    def test_d144_problem_0_input_c_her_last_colonoscopy_two_years_prior_to_todays_visit(self):
        """Input C, byte-identical: "I performed her last colonoscopy two years prior to today's visit, which was
        normal." (gi.colonoscopy, by 'I'; and its 'She had a colonoscopy ...' twin, performer unknown). c2e53f8e
        (colonoscopy historical) and 46e461e7f: READY, the visit listed. D144 made it OFF and READY; DECISIONS D151
        withdrew that, so it is e5628be56's again: ON, a colonoscopy documented as performed on the same date (by 'I';
        possible with performer unknown), 99213 held with separate_em, with no E/M proposed the visit set apart by 'I'
        and listed for the twin, and the routing stand-in reads the colonoscopy performed - returning costs."""
        twin = "She had a colonoscopy two years prior to today's visit, which was normal."
        for label, (inv, text), done in (("by 'I'", last_colonoscopy(a('documenting_team', 'I', ['P2'])), True),
                                         ('performer unknown', last_colonoscopy(a('unknown'), 'had', twin), False)):
            with self.subTest(label):
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=('Colonoscopy',)) if done
                                 else combination.ProcedureDay(possible=('Colonoscopy',)))
                self.assertEqual(no_em(inv, text), ([], [NOT_LISTED]) if done else ([NO_PROPOSAL], []))
                held_for_separate_em(self, em(inv, text), 'Colonoscopy')
                self.assertIn(['gi.colonoscopy', 'performed'],
                              [[f['family'], f['status']] for f in facts.routing_stand_in(inv, DAY)['findings']])

    def test_d144_withdrawn_no_anteriority_word_governs_a_same_day_word(self):
        """facts._same_day_word after DECISIONS D151: ANTERIORITY_WORDS is gone, and every SAME_DAY_WORDS entry is read
        wherever it stands, as at D131 (e5628be56), so each word D144 read as governed holds a same-day word again, and
        so does each it read as free. Named 'test_d144_the_anteriority_words_govern_only_the_same_day_word_right_after_
        them' until D151."""
        self.assertFalse(hasattr(facts, 'ANTERIORITY_WORDS'))
        for entry in ('prior to', 'before', 'previous to', 'preceding', 'ahead of', 'until', 'till'):
            for word in ("today's visit", 'today', 'this morning', "this afternoon's clinic", 'same day', 'tonight'):
                with self.subTest(governed=f'{entry} {word}'):
                    self.assertTrue(facts._same_day_word(f'{entry} {word}'))
        governed = ("Prior to today's visit, she had undergone the following procedures:", 'PRIOR TO TODAY',
                    'prior, to today', 'prior-to today', "two years prior to today's visit", 'Until today',
                    'before\ttoday')
        free = ('Earlier today, before her visit', 'earlier today', "at today's visit", 'today, prior to her visit',
                'prior to her visit today', 'prior today', 'to today', "Before today's visit, and again earlier today",
                'before her visit this morning', 'beforetoday is no word, today is')
        for text in governed + free:
            with self.subTest(text=text):
                self.assertTrue(facts._same_day_word(text))

    def test_d144_unchanged_the_same_day_words_no_anteriority_word_governs(self):
        """What D144 must NOT move: "at today's visit" (D133's input, kind other filed under the visit) is ON, 99213
        held with separate_em as c2e53f8e holds it; D131's 'Earlier today, excision' (problem 0's source) and 'Earlier
        today, before her visit' are ON, a done non-GI service, 99213 held with separate_em, as c2e53f8e holds them."""
        inv, text = office("Excision of a 1 cm sebaceous cyst on the upper back was performed at today's visit.",
                           other('Excision of a 1 cm sebaceous cyst', 'was performed',
                                 a('office_em', "today's visit", ['P2']),
                                 time=a('current_encounter', "at today's visit", ['P2'])))
        self.assertEqual(day_of(inv), facts.ON)
        held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)
        for words, line in (('Earlier today, excision', f'Earlier today, {CYST}.'),
                            ('Earlier today, before her visit', f'Earlier today, before her visit, {CYST}.')):
            with self.subTest(words=words):
                inv, text = office(line, excision('not_gi', a('earlier_encounter', words, ['P2'])))
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=(NON_GI_LABEL,)))
                held_for_separate_em(self, em(inv, text), NON_GI_LABEL)

    def test_d144_withdrawn_a_formerly_governed_word_places_the_act_on_the_date(self):
        """After DECISIONS D151 a same-day word right after 'before' or 'until' places the act on the date again, as at
        e5628be56 (D131). D131's record "Before today's visit, she had undergone an upper endoscopy at an outside
        hospital" ('before' is no earlier marker: unverified) is ON, a possible EGD, 99213 held with separate_em, as
        c2e53f8e asks it (D144: UNDATABLE, the EGD's event_time). The CT 'obtained before today's visit' and 'until
        today's visit' are ON, a possible service outside the GI profiles, 99213 held with separate_em (D144 and
        c2e53f8e: READY - a returning cost). Named 'test_d144_a_governed_word_leaves_the_act_to_its_own_time_value'
        until D151."""
        line = ("Before today's visit, she had undergone an upper endoscopy at an outside hospital, which showed a "
                'clean-based duodenal ulcer.')
        inv, text = office(line, act('E1', 'P2', 'examination', 'upper endoscopy', status_words='had undergone',
                                     procedure=a('egd', 'upper endoscopy', ['P2']),
                                     time=a('earlier_encounter', "Before today's visit", ['P2']),
                                     performer=a('other_facility', 'at an outside hospital', ['P2'])))
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(EGD_LABEL,)))
        held_for_separate_em(self, em(inv, text), EGD_LABEL)
        for word in ('before', 'until'):
            with self.subTest(word=word):
                inv, text = ruq_ct(f"{word} today's visit")
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(NON_GI_LABEL,)))
                held_for_separate_em(self, em(inv, text, RUQ_VISIT), NON_GI_LABEL)

    def test_d144_withdrawn_what_the_rule_released_is_held_again(self):
        """After DECISIONS D151 what D144 made READY beside the spec inputs is held again, as at e5628be56 and c2e53f8e
        (constructed inputs; none attested).
        - The documents give another date: "Two weeks prior to today's visit, she underwent an upper endoscopy at an
          outside hospital, ..." (other_facility verified) and "Two weeks prior to today's visit, rubber band ligation
          of one internal hemorrhoid was performed in the office." (filed under the visit): ON, a done EGD or Other GI
          service, 99213 held with separate_em, as c2e53f8e holds them (D144: READY, which the document supports - a
          hold e5628be56 and c2e53f8e share).
        - D144's refutation: "Prior to today's visit, I performed a flexible sigmoidoscopy, ..." and "I performed a
          flexible sigmoidoscopy before this morning's visit, ..." (by 'I'): ON, a done flexible sigmoidoscopy, 99213
          held with separate_em, as c2e53f8e holds them.
        Named 'test_d144_recorded_what_the_rule_releases_beside_the_spec_inputs' until D151."""
        egd = ("Two weeks prior to today's visit, she underwent an upper endoscopy at an outside hospital, which "
               'showed a clean-based duodenal ulcer.')
        band = ("Two weeks prior to today's visit, rubber band ligation of one internal hemorrhoid was performed in "
                'the office.')
        cases = (
            ('the outside EGD two weeks prior', office(egd, act(
                'E1', 'P2', 'examination', 'upper endoscopy', status_words='underwent',
                procedure=a('egd', 'upper endoscopy', ['P2']),
                time=a('earlier_encounter', "Two weeks prior to today's visit", ['P2']),
                performer=a('other_facility', 'at an outside hospital', ['P2'])))),
            ('the banding two weeks prior', office(band, act(
                'E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='was performed',
                procedure=a('office_em', 'office', ['P2']),
                time=a('earlier_encounter', "Two weeks prior to today's visit", ['P2']), target=HEM))),
            ("the flexible sigmoidoscopy by 'I' prior to today's visit", flex_sig_by_i(
                "Prior to today's visit", "Prior to today's visit, I performed a flexible sigmoidoscopy, which showed "
                                          'internal hemorrhoids.')),
            ("the flexible sigmoidoscopy by 'I' before this morning's visit", flex_sig_by_i(
                "before this morning's visit", "I performed a flexible sigmoidoscopy before this morning's visit, "
                                               'which showed internal hemorrhoids.')),
        )
        labels = (EGD_LABEL, OTHER_GI_LABEL, FLEX_SIG_LABEL, FLEX_SIG_LABEL)
        for (label, (inv, text)), same_day in zip(cases, labels):
            with self.subTest(label):
                self.assertEqual(reading_of(inv).events['E1']['time']['state'], 'verified')
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=(same_day,)))
                held_for_separate_em(self, em(inv, text), same_day)


# --- problem 4: an anaphoric frame is no same-day word for a verified other's act ------------------------------------

class D144AnaphoricFramesOfAVerifiedOther(SimpleTestCase):
    """D144 (problem 4), withdrawn by DECISIONS D151 (measured: it made 99213 READY where e5628be56 holds it): an
    anaphoric frame's SAME_DAY_WORDS are read for every performer again."""

    def test_d144_problem_4_d112s_source_earlier_that_same_day(self):
        """Problem 4's input, byte-identical: D112's source worded 'Earlier that same day she had undergone an upper
        endoscopy at that hospital, ...' (other_facility 'at that hospital' verified; its 'earlier' verifies the
        time). c2e53f8e: READY, the visit listed. D144 made it OFF and READY; DECISIONS D151 measured that as a release
        against e5628be56 and withdrew it, so it is e5628be56's and 46e461e7f's again: ON by SAME_DAY_WORDS' 'same
        day', a done EGD, 99213 held with separate_em, the visit set apart and a second review's 99213 an informational
        alternative - a returning cost. The same for an outside gastroenterologist (other_clinician verified). Named
        '..._is_off_the_date' until D151."""
        inv, text = melena('Earlier that same day')
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=(EGD_LABEL,)))
        held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)
        self.assertEqual(no_em(inv, text), ([], [NOT_LISTED]))
        result = run(inv, text, [], user_values=MEMBER, second=response(text, [('99213', MELENA_VISIT)],
                                                                         provider='fable'),
                     second_scope={'items': [NO_PROPOSAL]})
        self.assertEqual([(p.bucket, p.status) for p in result.proposals if p.code == '99213'],
                         [('alternative', 'informational')])
        line = ('Earlier that same day, an outside gastroenterologist performed an upper endoscopy, which showed a '
                'clean-based duodenal ulcer.')
        egd = act('E1', 'P2', 'examination', 'upper endoscopy', status_words='performed',
                  procedure=a('egd', 'upper endoscopy', ['P2']),
                  time=a('earlier_encounter', 'Earlier that same day', ['P2']),
                  performer=a('other_clinician', 'an outside gastroenterologist', ['P2']))
        inv, text = inventory({'V1': MELENA_VISIT, 'V2': TIME, 'P1': OUTSIDE_ADMISSION, 'P2': line, 'P3': PLAN},
                              events=[act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                                          procedure=a('office_em', 'Office visit', ['V1'])), egd],
                              visits=[visit_facts()])
        self.assertEqual(day_of(inv), facts.ON)
        held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)

    def test_d144_withdrawn_an_anaphoric_frames_same_day_is_read_for_every_performer(self):
        """facts._same_day_word after DECISIONS D151 takes no ``anaphoric`` argument: 'that same day', 'earlier that
        same day' and 'later that same day' hold 'same day' for every performer, as at e5628be56; the other seven
        anaphoric frames hold no SAME_DAY_WORDS entry; a same-day word beside a frame, 'same day', 'on the same day' and
        'Earlier the same day' are read. Named 'test_d144_every_anaphoric_frame_is_no_same_day_word_without_anaphoric'
        until D151."""
        self.assertEqual(list(inspect.signature(facts._same_day_word).parameters), ['text'])
        holding = [frame for frame in lexicon.ANAPHORIC_FRAMES if facts._same_day_word(frame)]
        self.assertEqual(holding, ['earlier that same day', 'later that same day', 'that same day'])
        for frame in lexicon.ANAPHORIC_FRAMES:
            for text in (frame, frame.upper() + ',', f'{frame.capitalize()} she had undergone an upper endoscopy',
                         f'(at that hospital) {frame}.'):
                with self.subTest(text=text):
                    self.assertEqual(facts._same_day_word(text), frame in holding)
        for text in ('Earlier that same day, and again today', 'that same day; this morning', 'same day',
                     'on the same day', 'Earlier the same day'):
            with self.subTest(text=text):
                self.assertTrue(facts._same_day_word(text))

    def test_d144_that_same_day_frames_at_that_hospital(self):
        """D112's source worded 'That same day' and 'Later that same day' (other_facility verified; no earlier marker,
        so the time is unverified): c2e53f8e READY. D144 made them UNDATABLE (99213 asked the EGD's event_time);
        DECISIONS D151 withdrew that, so they are e5628be56's again: ON, a possible EGD, 99213 held with separate_em - a
        hold either way. Named '..._are_read_by_their_own_value' until D151."""
        for words in ('That same day', 'Later that same day'):
            with self.subTest(words=words):
                inv, text = melena(words)
                self.assertEqual(reading_of(inv).events['E1']['time']['state'], 'unverified')
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(EGD_LABEL,)))
                held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)

    def test_d144_an_act_whose_performer_is_not_verified_other_is_unchanged(self):
        """The rule's other side (D132, unchanged): D112's text 'Earlier that same day' with the EGD's performer
        other_facility WITHOUT words (unverified) or 'unknown' is ON, a possible EGD, 99213 held with separate_em
        (c2e53f8e: READY, D132's recorded cost); 'Earlier that same day, I performed a flexible sigmoidoscopy, ...' (by
        'I') is ON, documented as performed, held with separate_em, as c2e53f8e holds it."""
        for label, performer in (('other_facility unverified', a('other_facility')), ('unknown', a('unknown'))):
            with self.subTest(label):
                inv, text = melena('Earlier that same day', performer=performer)
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(EGD_LABEL,)))
                held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)
        inv, text = flex_sig_by_i('Earlier that same day', 'Earlier that same day, I performed a flexible '
                                                           'sigmoidoscopy, which showed internal hemorrhoids.')
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=(FLEX_SIG_LABEL,)))
        held_for_separate_em(self, em(inv, text), FLEX_SIG_LABEL)


# --- problem 1: an act done on the date but for its procedure sets the visit apart ------------------------------------

class D144VisitBesideAnActDoneButForItsProcedure(SimpleTestCase):
    """D144 (problem 1), withdrawn by DECISIONS D151: ProcedureDay has no ``unidentified``; the office-visit rule reads
    ``labels`` alone again (D134)."""

    def test_d144_problem_1_the_banding_whose_procedure_is_unknown(self):
        """Problem 1's input, byte-identical: D81's office lines with P2 'Rubber band ligation of one internal
        hemorrhoid was performed in the office today.' (band_ligation, procedure 'unknown', performed, by the team,
        the current encounter). c2e53f8e and 46e461e7f: not_listed, and a second review's 99213 an informational
        alternative. D144 matched them; DECISIONS D151 withdrew ``unidentified`` (it also set the visit apart beside
        labs, a stool guaiac test and a vaccine), so it is e5628be56's again: a possible Other GI service, the visit
        listed and a second review's 99213 added, held with separate_em - a returning cost (a listing, never a READY).
        With 99213 proposed it is held with separate_em, worded 'possibly performed'. Named '..._sets_the_visit_apart'
        until D151."""
        inv, text = office(BAND, banding(a('unknown')))
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
        self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
        result = second_review(inv, text)
        self.assertEqual([(p.bucket, p.status) for p in result.proposals if p.code == '99213'],
                         [('selected', 'needs_clarification')])
        p = em(inv, text)
        held_for_separate_em(self, p, OTHER_GI_LABEL)
        self.assertIn(POSSIBLY, check(p, 'em.same_day_procedure').detail)

    def test_d144_problem_1_filed_under_the_visit_or_under_gi_other(self):
        """The same banding filed under the visit (procedure office_em with no words, or words that do not locate:
        unverified, procedure_unsettled) or under gi.other (procedure other_gi with no words, D81's own shape): its
        procedure alone is not usable. c2e53f8e: not_listed. D144 set all three apart; after DECISIONS D151 the two
        filed under the visit are listed again, as at e5628be56 (a returning cost), and the one under gi.other stays
        set apart by gi.other's own done session."""
        for label, procedure, listed in (('office_em with no words', a('office_em'), True),
                                         ('office_em, words not located', a('office_em', 'clinic visit', ['P2']), True),
                                         ('other_gi with no words', a('other_gi'), False)):
            with self.subTest(label):
                inv, text = office(BAND, banding(procedure))
                self.assertEqual(reading_of(inv).events['E1']['procedure']['state'], 'unverified')
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
                self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []) if listed else ([], [NOT_LISTED]))

    def test_d144_problem_1_an_act_read_by_its_statement_or_otherwise_in_doubt_keeps_the_visit_listed(self):
        """What D144 must NOT move (D134): an act read by its statement (D130: only ever possible) - the DRE and the
        office excision today filed under the visit, by the act's own 'office' or by a procedure with no words (its
        procedure alone not usable, as the banding's above: still only possible); an act whose day is only possible -
        the banding 'possibly performed' (status uncertain), 'Later that morning' (current_encounter unverified), the
        banding with performer 'unknown' (with its procedure usable, or 'unknown' too), and D111's CT 'obtained earlier
        today' (performer unknown): the act is only possible and the visit stays listed (D151: ProcedureDay has no
        ``unidentified``). (c2e53f8e sets it apart beside the excision, the bandings with performer 'unknown' and
        'Later that morning' - the recorded D134 difference, a listing, never a READY - and lists it beside the DRE, the
        banding 'possibly performed' and the CTs.)"""
        later = 'Later that morning, rubber band ligation of one internal hemorrhoid was performed in the office.'
        hedged = 'Rubber band ligation of one internal hemorrhoid was possibly performed in the office today.'
        excision_today = 'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office today.'
        cases = (
            ('the DRE by its statement', note(
                'Rectal examination: a digital rectal examination was performed and showed no masses.',
                other('digital rectal examination', 'was performed', VISIT_WORDS)), VISIT),
            ('the excision today by its statement', note(
                excision_today, other('Excision of a 1 cm sebaceous cyst', 'was performed')), VISIT),
            ('the excision by its statement, its procedure with no words', note(
                excision_today, other('Excision of a 1 cm sebaceous cyst', 'was performed', a('office_em'))), VISIT),
            ('the banding possibly performed', office(hedged, act(
                'E1', 'P2', 'band_ligation', 'Rubber band ligation', status='uncertain',
                status_words='possibly performed', procedure=a('unknown'), target=HEM)), VISIT),
            ("'Later that morning'", office(later, act(
                'E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='was performed',
                procedure=a('office_em', 'office', ['P2']), time=a('current_encounter', 'Later that morning', ['P2']),
                target=HEM)), VISIT),
            ('the banding under the visit, performer unknown', office(BAND, banding(
                a('office_em', 'office', ['P2']), performer=a('unknown'))), VISIT),
            ('the banding, procedure and performer unknown', office(BAND, banding(
                a('unknown'), performer=a('unknown'))), VISIT),
        )
        for label, (inv, text), visit_line in cases:
            with self.subTest(label):
                found = procedure_day(inv)
                self.assertEqual((found.labels, found.possible), ((), (OTHER_GI_LABEL,)))  # D151: no unidentified
                self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
        for words in ('earlier today', 'this morning'):
            with self.subTest(ct=words):
                e0 = act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                         procedure=a('office_em', 'Office visit', ['V1']))
                study = act('E1', 'P2', 'other', 'CT abdomen', status_words='obtained',
                            procedure=a('not_gi', 'CT abdomen', ['P2']), time=a('earlier_encounter', words, ['P2']),
                            performer=a('unknown'))
                inv, text = inventory({'V1': RUQ_VISIT, 'V2': THIRTY, 'P2': f'CT abdomen obtained {words} showed a '
                                       'dilated common bile duct.', 'P3': MRCP_PLAN}, events=[e0, study], visits=[
                    {'event': 'E0', 'basis': a('total_time', '30 minutes', ['V2']),
                     'separately_identifiable': a('not_stated')}])
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(NON_GI_LABEL,)))
                self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))

    def test_d144_the_other_readers_of_labels_and_possible_are_unchanged(self):
        """After DECISIONS D151 ProcedureDay is labels, possible and undatable again: procedure_day (labels or possible)
        is as before, so the separate_em and event_time questions and their wording are; the read-time overlay (a bool
        from the items the assessment listed) keeps the banding's visit listed, as the assessment lists it (D144: set
        apart); and possible alone lists the visit (D134)."""
        both = inventory({'V1': VISIT, 'V2': TIME, 'P2': BAND, 'P4': BAND.replace('one internal', 'a second internal'),
                          'P3': PLAN}, events=[visit(), banding(a('unknown')), act(
            'E2', 'P4', 'band_ligation', 'Rubber band ligation', status_words='was performed',
            procedure=a('office_em', 'office', ['P4']), target=tg('', 'anal_canal', 'a second internal hemorrhoid',
                                                                   ['P4']))], visits=[visit_facts()])
        self.assertEqual(procedure_day(both[0]), combination.ProcedureDay(labels=(OTHER_GI_LABEL,)))
        inv, text = office(BAND, banding(a('unknown')))
        found = procedure_day(inv)
        self.assertTrue(found.procedure_day)
        p = em(inv, text)
        self.assertEqual(p.clarifications[0].question, checks.separate_em_clarification(
            (), 'gi.office_em', p.key, (OTHER_GI_LABEL,)).question)
        result = run(inv, text, [], user_values=MEMBER)
        reviewed = overlay.reviewed_completeness(result.completeness, reading_of(inv), [], ())
        self.assertEqual(([str(item['label']) for item in reviewed['unresolved_items']],
                          [str(item['label']) for item in reviewed['not_listed']]), ([NO_PROPOSAL], []))
        self.assertEqual(coverage.reconcile(reading_of(inv), [], procedure_day=combination.ProcedureDay(
            possible=(OTHER_GI_LABEL,))).not_listed, [])  # possible alone: listed (D134)

    def test_d144_recorded_an_act_of_kind_other_whose_procedure_is_unknown(self):
        """RECORDED (constructed; none attested): an act of kind 'other' whose procedure Gemini left 'unknown' (no
        family, D94's 'A procedure CPT Studio could not identify'), performed in the office today by the team. D144 set
        the visit apart beside each; DECISIONS D151 withdrew ``unidentified``, so, as at e5628be56, the visit is listed
        and a second review's 99213 is added, held with separate_em. Beside 'Excision of a 1 cm sebaceous cyst ... was
        performed in the office today.' c2e53f8e sets the visit apart (gi.other performed) and makes the second review's
        99213 an informational alternative - a returning cost, a listing; beside 'A CT abdomen was performed in the
        office today.' and 'An ECG was performed in the office today.' c2e53f8e lists the visit and adds the second
        review's 99213 READY (D94's recorded cost, as at e5628be56). With 99213 proposed every one is held with
        separate_em, as at e5628be56 (c2e53f8e: READY beside the CT and the ECG - D94's recorded cost)."""
        for label, line, kind_words, routed in (
                ('the excision', 'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office '
                 'today.', 'Excision of a 1 cm sebaceous cyst', True),
                ('the CT', 'A CT abdomen was performed in the office today.', 'CT abdomen', False),
                ('the ECG', 'An ECG was performed in the office today.', 'ECG', False)):
            with self.subTest(label):
                inv, text = office(line, act('E1', 'P2', 'other', kind_words, status_words='was performed',
                                             procedure=a('unknown')))
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(
                    possible=(combination.UNIDENTIFIED_PROCEDURE,)))
                self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
                self.assertEqual([(p.bucket, p.status) for p in second_review(inv, text).proposals
                                  if p.code == '99213'], [('selected', 'needs_clarification')])
                held_for_separate_em(self, em(inv, text), combination.UNIDENTIFIED_PROCEDURE)


# --- problem 7: the kept pins are named by what they assert -----------------------------------------------------------

class D144KeptPinsNamedByWhatTheyAssert(SimpleTestCase):
    """D144 (problem 7): names and docstrings only; their assertions are unchanged."""

    def test_d144_the_three_kept_pins_are_renamed(self):
        renamed = (
            (test_interpretation_r5_em2.D130KindOtherFiledUnderTheVisit,
             'test_d130_with_no_e_m_proposed_the_visit_item_is_not_pushed',
             'test_d130_with_no_e_m_proposed_the_visit_item_is_listed'),
            (test_interpretation_r5_em2.D130TheStatementReader,
             'test_d130_the_never_counted_classes_are_read_in_the_kind_and_target_words',
             'test_d130_the_never_counted_classes_are_read_in_the_kind_words_head'),
            (test_interpretation_r5_em.D112TodayAnchoredFrames,
             'test_d112_finding_14s_g2_earlier_that_day_is_read_by_its_marker',
             'test_d112_finding_14s_g2_earlier_that_day_is_read_by_the_anaphoric_frame'),
        )
        for cls, old, new in renamed:
            with self.subTest(new):
                self.assertTrue(callable(getattr(cls, new, None)))
                self.assertFalse(hasattr(cls, old))


# --- recorded, not built (problems 2, 3 and 6) ------------------------------------------------------------------------

class D144Recorded(SimpleTestCase):
    """The review's problems 2, 3 and 6, recorded and not built: their outcomes as they stand."""

    def test_d144_recorded_problems_2_3_and_6(self):
        """Problem 2 (a cost): 'Earlier that day, Dr. Lena Park performed an upper endoscopy, ...' after 'On 10/30/2026
        she was admitted to another hospital for melena.' - other_clinician 'Dr. Lena Park' is unverified
        (name_not_other), so the anaphoric frame places the act on the date: a possible EGD, 99213 held with
        separate_em where c2e53f8e is READY ('an outside gastroenterologist', verified, is READY on both). Problem 3 (a
        cost): 'Review of the outside CT images was performed today.' filed under the visit is a possible other GI
        service (its head 'Review' names no class), 99213 held with separate_em where c2e53f8e is READY. Problem 6
        (accepted): "at today's visit" asks separate_em, as c2e53f8e does
        (D144AnteriorityWords.test_d144_unchanged_the_same_day_words_no_anteriority_word_governs)."""
        line = ('Earlier that day, Dr. Lena Park performed an upper endoscopy, which showed a clean-based duodenal '
                'ulcer.')
        egd = act('E1', 'P2', 'examination', 'upper endoscopy', status_words='performed',
                  procedure=a('egd', 'upper endoscopy', ['P2']),
                  time=a('earlier_encounter', 'Earlier that day', ['P2']),
                  performer=a('other_clinician', 'Dr. Lena Park', ['P2']))
        inv, text = inventory({'V1': MELENA_VISIT, 'V2': TIME, 'P1': OUTSIDE_ADMISSION, 'P2': line, 'P3': PLAN},
                              events=[act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                                          procedure=a('office_em', 'Office visit', ['V1'])), egd],
                              visits=[visit_facts()])
        self.assertEqual(reading_of(inv).events['E1']['performer']['state'], 'unverified')
        self.assertEqual(day_of(inv), facts.ON)
        held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)
        inv, text = office('Review of the outside CT images was performed today.',
                           other('Review of the outside CT images', 'was performed', VISIT_WORDS))
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
        held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)
