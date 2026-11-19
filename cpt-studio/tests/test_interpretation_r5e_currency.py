"""DECISIONS D151 (round 5e, narrowing only; the review of D144, round5d 'review:currency4' problems 0-5), SYNTHETIC:
D144 is withdrawn whole - its anteriority rule, its anaphoric hiding and ProcedureDay.unidentified - so
facts._same_day_word reads every SAME_DAY_WORDS entry as D131 does, for every performer, and coverage.reconcile's
office-visit rule reads ProcedureDay.labels alone (D134), exactly as e5628be56 (round 5c) does.

- Problems 0-2 (critical, critical-class, medium; introduced by D144 (1)): a same-day word right after 'prior to' or
  'before' placed nothing, so "Earlier in the day, prior to today's visit, rubber band ligation ..." - a same-date frame
  beside the governed word - was OFF the date and 99213 READY with no separate_em question, where e5628be56 and
  c2e53f8e hold it with separate_em; "before this morning's visit" likewise; an unverified time asked event_time in
  place of separate_em. Now each is ON the date and held with separate_em, as at e5628be56.
- Problem 3 (medium; introduced by D144 (3)): ProcedureDay.unidentified took any positive current act by the team whose
  procedure is unusable, so 'Labs were drawn in the office today.', a stool guaiac test or a vaccine set the visit
  apart where e5628be56 and c2e53f8e list it. Now the visit is listed.
- D144 (2), measured (DECISIONS D151): hiding an anaphoric frame's words for a verified other's act made 99213 READY
  beside D112's 'Earlier that same day ... at that hospital' and the outside gastroenterologist, where e5628be56 holds
  it, so it is withdrawn too; problem 5 (the two readers' opposite defaults) is moot: _same_day_word takes no such
  argument.
- The costs D144 had cured return (recorded, DECISIONS D151): its Inputs A, B and C and D112's source are held where
  c2e53f8e is READY, and D81's banding whose procedure Gemini left 'unknown' lists the visit where c2e53f8e sets it
  apart (tests/test_interpretation_r5d_currency.py, whose expectations change back).

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). The installed release's outputs (c2e53f8e: engine.assess with gi_context.extract_context,
merge_user_values office/established and detect.route on 2026-11-09, as tests/test_harness_engine.py drives it, the same
synthetic reference rows) and e5628be56's quoted in the docstrings were measured on byte-identical texts
(round5e/currency5/out/census-cases.tsv). Every input is constructed. Nothing is sent."""
from __future__ import annotations

import dataclasses
import inspect

from django.test import SimpleTestCase

from studio.interpretation import combination, facts, lexicon
from studio.validation import checks
from tests.test_interpretation_events import asked, inventory, proposal, response, run
from tests.test_interpretation_identity import a, act
from tests.test_interpretation_r3_families import MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r4_em_same_day import OTHER_GI_LABEL, held_for_separate_em
from tests.test_interpretation_r5_em import ED_LINE, MELENA_VISIT, NO_PROPOSAL, OUTSIDE_EGD, banding, office
from tests.test_interpretation_r5c_currency import (EGD_LABEL, FLEX_SIG_LABEL, NOT_LISTED, SEPARATE, SEPARATE_LINE,
                                                    day_of, melena, procedure_day)
from tests.test_interpretation_r5d_currency import OUTSIDE_ADMISSION, flex_sig_by_i

DAY = '2026-11-09'
LISTED = ([NO_PROPOSAL], [])
APART = ([], [NOT_LISTED])
SECOND_HELD = ('selected', 'needs_clarification', ['separate_em'])
SECOND_INFORMATIONAL = ('alternative', 'informational', [])
FRAME = "Earlier in the day, prior to today's visit"
FRAME_BANDING = f'{FRAME}, rubber band ligation of one internal hemorrhoid was performed in the office.'
UNIDENTIFIED = combination.UNIDENTIFIED_PROCEDURE


def listing(inv, text):
    """The visit item with no code proposed: (the unresolved labels, the not_listed labels)."""
    completeness = run(inv, text, [], user_values=MEMBER).completeness
    return ([str(item.get('label')) for item in completeness['unresolved_items']],
            [str(item.get('label')) for item in completeness['not_listed']])


def second_99213(inv, text, visit_line=VISIT):
    """A second review (fable) selecting 99213 for the visit item, no code proposed: its 99213 (bucket, status,
    asked)."""
    result = run(inv, text, [], user_values=MEMBER, second=response(text, [('99213', visit_line)], provider='fable'),
                 second_scope={'items': [NO_PROPOSAL]})
    return [(p.bucket, p.status, asked(p)) for p in result.proposals if p.code == '99213']


def em(inv, text, visit_line=VISIT):
    return proposal(run(inv, text, [('99213', visit_line)], user_values=MEMBER), '99213')


def held_on_the_date(test, inv, text, label, *, done, visit_line=VISIT):
    """ON the date, the act ``label`` done (labels) or only possible, 99213 held with separate_em and the modifier 25
    consideration; with no code proposed the visit is set apart beside a done act and listed beside a possible one
    (D134); a second review's 99213 is then an informational alternative or added held."""
    test.assertEqual(day_of(inv), facts.ON)
    test.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=(label,)) if done
                     else combination.ProcedureDay(possible=(label,)))
    held_for_separate_em(test, em(inv, text, visit_line), label)
    test.assertEqual(listing(inv, text), APART if done else LISTED)
    test.assertEqual(second_99213(inv, text, visit_line), [SECOND_INFORMATIONAL if done else SECOND_HELD])


def other_kind(line: str, kind_words: str, status_words: str) -> tuple:
    """D81's office lines with an act of kind 'other' (E1, P2), procedure 'unknown', by the team, the current
    encounter - D94's 'A procedure CPT Studio could not identify'."""
    return office(line, act('E1', 'P2', 'other', kind_words, status_words=status_words, procedure=a('unknown')))


# --- (1) problems 0-2: D144 (1), the anteriority rule, is withdrawn ---------------------------------------------------

class D151TheAnteriorityRuleIsWithdrawn(SimpleTestCase):
    """D151 (1): a same-day word right after an anteriority word is read as D131 reads it."""

    def test_d151_problem_0_a_same_date_frame_beside_prior_to_todays_visit_holds_99213(self):
        """The review's problem 0, byte-identical: D81's office lines with P2 "Earlier in the day, prior to today's
        visit, rubber band ligation of one internal hemorrhoid was performed in the office." (band_ligation, filed under
        gi.other 'rubber band ligation' or under the visit 'office', performed, by the team, earlier_encounter worded
        "Earlier in the day, prior to today's visit", verified), and its probes: the whole sentence as the time words,
        and "Earlier in the day, before today's visit". c2e53f8e and e5628be56: ON, a done Other GI service, 99213 held
        with separate_em and the modifier 25 consideration, the visit set apart, a second review's 99213 an
        informational alternative. 4f82e5056 (D144): OFF, 99213 READY, the visit listed, a second review's 99213 READY.
        Now as e5628be56 and c2e53f8e."""
        before = "Earlier in the day, before today's visit"
        for value in ('other_gi', 'office_em'):
            for label, words, line in (('frame', FRAME, FRAME_BANDING),
                                       ('whole sentence', FRAME_BANDING, FRAME_BANDING),
                                       ("before today's visit", before, FRAME_BANDING.replace(FRAME, before))):
                with self.subTest(procedure=value, words=label):
                    inv, text = office(line, banding(value, a('earlier_encounter', words, ['P2'])))
                    held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=True)

    def test_d151_problem_0_performer_unknown_is_held_as_possible(self):
        """Problem 0's probe with the banding's performer 'unknown': e5628be56 ON, a possible Other GI service, 99213
        held with separate_em, the visit listed and a second review's 99213 added held; c2e53f8e the same hold, the
        visit set apart (D134's recorded difference: a listing, never a READY). 4f82e5056: OFF, 99213 READY, a second
        review's 99213 READY. Now as e5628be56."""
        for value in ('other_gi', 'office_em'):
            with self.subTest(procedure=value):
                item = dict(banding(value, a('earlier_encounter', FRAME, ['P2'])), performer=a('unknown'))
                inv, text = office(FRAME_BANDING, item)
                held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=False)

    def test_d151_problem_0_the_documenting_teams_flexible_sigmoidoscopy_and_egd(self):
        """Problem 0's probes by 'I' (earlier_encounter, verified): a flexible sigmoidoscopy "Earlier in the day, before
        today's visit", "Earlier in the morning, prior to today's visit", "Earlier in the day, prior to this
        afternoon's visit", "Earlier that morning, prior to today's visit" or "Earlier in the day, prior to today's
        visit", and an upper endoscopy "Earlier in the day, prior to today's visit". c2e53f8e and e5628be56: ON, done,
        99213 held with separate_em, the visit set apart; 4f82e5056: OFF, READY. Now as e5628be56 and c2e53f8e."""
        for words in ("Earlier in the day, before today's visit", "Earlier in the morning, prior to today's visit",
                      "Earlier in the day, prior to this afternoon's visit",
                      "Earlier that morning, prior to today's visit", FRAME):
            with self.subTest(words=words):
                inv, text = flex_sig_by_i(words, f'{words}, I performed a flexible sigmoidoscopy, which showed '
                                                 'internal hemorrhoids.')
                held_on_the_date(self, inv, text, FLEX_SIG_LABEL, done=True)
        line = f'{FRAME}, I performed an upper endoscopy, which showed a clean-based duodenal ulcer.'
        inv, text = office(line, act('E1', 'P2', 'examination', 'upper endoscopy', status_words='I performed',
                                     procedure=a('egd', 'upper endoscopy', ['P2']),
                                     time=a('earlier_encounter', FRAME, ['P2']),
                                     performer=a('documenting_team', 'I', ['P2'])))
        held_on_the_date(self, inv, text, EGD_LABEL, done=True)

    def test_d151_problem_1_before_this_mornings_visit_and_prior_to_todays_visit(self):
        """The review's problem 1 (verified earlier times): "I performed a flexible sigmoidoscopy before this
        morning's visit, ..." (verified by 'before this'), "Prior to today's visit, I performed a flexible
        sigmoidoscopy, ...", "Before this morning's visit, rubber band ligation ... was performed in the office."
        (gi.other) and "Prior to today's visit, rubber band ligation ... was performed in the office." (filed under the
        visit). c2e53f8e and e5628be56: ON, done, 99213 held with separate_em, the visit set apart; 4f82e5056: OFF,
        READY, the visit listed. Now as both."""
        flex = (("before this morning's visit", "I performed a flexible sigmoidoscopy before this morning's visit, "
                                                "which showed internal hemorrhoids."),
                ("Prior to today's visit", "Prior to today's visit, I performed a flexible sigmoidoscopy, which showed "
                                           'internal hemorrhoids.'))
        for words, line in flex:
            with self.subTest(words=words):
                inv, text = flex_sig_by_i(words, line)
                self.assertEqual(day_of(inv), facts.ON)
                held_on_the_date(self, inv, text, FLEX_SIG_LABEL, done=True)
        for value, words in (('other_gi', "Before this morning's visit"), ('office_em', "Prior to today's visit")):
            with self.subTest(procedure=value, words=words):
                inv, text = office(f'{words}, rubber band ligation of one internal hemorrhoid was performed in the '
                                   'office.', banding(value, a('earlier_encounter', words, ['P2'])))
                held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=True)

    def test_d151_problem_1_before_todays_visit_unverified_is_held_with_separate_em(self):
        """The review's problem 1, second path: "Before today's visit, rubber band ligation ... was performed in the
        office." ('before' is no earlier marker: unverified), filed under the visit ('office'), with procedure
        'unknown', or under gi.other. 4f82e5056: UNDATABLE - 99213 READY under the visit or 'unknown' (skipped as a
        history mention), event_time under gi.other. e5628be56: ON, a possible Other GI service, 99213 held with
        separate_em, the visit listed, a second review's 99213 added held; c2e53f8e: held with separate_em, the visit
        set apart (D134's recorded difference). Now as e5628be56."""
        line = "Before today's visit, rubber band ligation of one internal hemorrhoid was performed in the office."
        for value in ('office_em', 'unknown', 'other_gi'):
            with self.subTest(procedure=value):
                inv, text = office(line, banding(value, a('earlier_encounter', "Before today's visit", ['P2'])))
                held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=False)

    def test_d151_problem_2_the_frame_as_current_encounter_words_asks_separate_em(self):
        """The review's problem 2: problem 0's banding with time current_encounter worded "Earlier in the day, prior to
        today's visit" (unverified, D35's other occasion). 4f82e5056: UNDATABLE, 99213 asks event_time ('done at this
        encounter?') about an act the document places on the date. e5628be56: ON, possible, 99213 held with
        separate_em (and a second review's 99213 added held); c2e53f8e: held with separate_em. Now separate_em, as
        both."""
        for value in ('other_gi', 'office_em'):
            with self.subTest(procedure=value):
                inv, text = office(FRAME_BANDING, banding(value, a('current_encounter', FRAME, ['P2'])))
                p = em(inv, text)
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['separate_em']))
                held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=False)

    def test_d151_same_day_word_reads_every_entry_as_d131(self):
        """facts._same_day_word is D131's reader again: one argument, every SAME_DAY_WORDS entry matched whole after
        D131's folding, wherever it stands; ANTERIORITY_WORDS is gone. The words D144 read as governed hold a same-day
        word again."""
        self.assertFalse(hasattr(facts, 'ANTERIORITY_WORDS'))
        self.assertEqual(list(inspect.signature(facts._same_day_word).parameters), ['text'])
        for text in ("Prior to today's visit, she had undergone the following procedures:", 'PRIOR TO TODAY',
                     "two years prior to today's visit", 'Until today', 'before\ttoday', FRAME,
                     "before this morning's visit", "Earlier in the day, prior to this afternoon's visit",
                     'previous to today', 'preceding this evening', 'ahead of tonight', 'till today'):
            with self.subTest(text=text):
                self.assertTrue(facts._same_day_word(text))
        self.assertFalse(facts._same_day_word('prior to this visit'))


# --- (3) D144 (2), the anaphoric hiding: measured, and withdrawn ------------------------------------------------------

class D151TheAnaphoricHidingIsWithdrawn(SimpleTestCase):
    """D151 (3): an anaphoric frame's SAME_DAY_WORDS are read for every performer, as at e5628be56."""

    def test_d151_d112s_earlier_that_same_day_at_that_hospital_is_held_again(self):
        """D112's source worded 'Earlier that same day she had undergone an upper endoscopy at that hospital, ...'
        (other_facility verified, the time verified by 'earlier') and its outside gastroenterologist (other_clinician
        verified). e5628be56: ON, a done EGD, 99213 held with separate_em, the visit set apart, a second review's 99213
        an informational alternative. 4f82e5056 (D144 (2)): OFF, 99213 READY, the visit listed, a second review's 99213
        READY - a release against e5628be56, so D144 (2) is withdrawn. c2e53f8e: READY and listed: the cost returns
        (DECISIONS D151)."""
        inv, text = melena('Earlier that same day')
        held_on_the_date(self, inv, text, EGD_LABEL, done=True, visit_line=MELENA_VISIT)
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
        held_on_the_date(self, inv, text, EGD_LABEL, done=True, visit_line=MELENA_VISIT)

    def test_d151_that_same_day_frames_at_that_hospital_ask_separate_em_again(self):
        """D112's source worded 'That same day', 'Later that same day' or 'On that same day' (other_facility verified;
        no earlier marker: the time unverified). 4f82e5056: UNDATABLE, 99213 asks the EGD's event_time. e5628be56: ON,
        a possible EGD, 99213 held with separate_em, the visit listed. c2e53f8e: READY (a cost either way). Now as
        e5628be56."""
        for words in ('That same day', 'Later that same day', 'On that same day'):
            with self.subTest(words=words):
                inv, text = melena(words)
                held_on_the_date(self, inv, text, EGD_LABEL, done=False, visit_line=MELENA_VISIT)

    def test_d151_the_same_day_frames_hold_same_day_for_every_performer(self):
        """The three anaphoric frames that carry SAME_DAY_WORDS' 'same day' hold it - _same_day_word takes no
        performer - so each places D112's outside EGD (other_facility verified) on the date, as at e5628be56 (D144:
        OFF or UNDATABLE); the frames are still read whole by _same_day_frame for an act whose performer is not
        verified other only (D132, unchanged), so 'Earlier that day' places that EGD on no day."""
        holding = [frame for frame in lexicon.ANAPHORIC_FRAMES if facts._same_day_word(frame)]
        self.assertEqual(holding, ['earlier that same day', 'later that same day', 'that same day'])
        for frame in holding:
            with self.subTest(frame=frame):
                self.assertEqual(day_of(melena(frame.capitalize())[0]), facts.ON)
        self.assertTrue(facts._same_day_frame('Earlier that day', anaphoric=True))
        self.assertFalse(facts._same_day_frame('Earlier that day', anaphoric=False))
        self.assertEqual(day_of(melena('Earlier that day')[0]), facts.OFF)


# --- (2) problem 3: D144 (3), ProcedureDay.unidentified, is withdrawn -------------------------------------------------

class D151TheUnidentifiedFieldIsWithdrawn(SimpleTestCase):
    """D151 (2): the office-visit rule reads ProcedureDay.labels alone again (D134)."""

    def test_d151_problem_3_labs_a_stool_guaiac_and_a_vaccine_keep_the_visit_listed(self):
        """The review's problem 3: 'Labs were drawn in the office today.', 'A stool guaiac test was performed in the
        office today.' and 'An influenza vaccine was administered in the office today.' (kind other, procedure
        'unknown', performed, by the team, the current encounter). c2e53f8e and e5628be56 list the visit; 4f82e5056
        set it apart. A second review's 99213: c2e53f8e READY, e5628be56 added held with separate_em, 4f82e5056 an
        informational alternative. With 99213 proposed, e5628be56 and 4f82e5056 hold it and c2e53f8e is READY (D94's
        recorded cost). Now as e5628be56: listed, the second review's 99213 added held."""
        for line, kind_words, status_words in (
                ('Labs were drawn in the office today.', 'Labs', 'were drawn'),
                ('A stool guaiac test was performed in the office today.', 'stool guaiac test', 'was performed'),
                ('An influenza vaccine was administered in the office today.', 'influenza vaccine',
                 'was administered')):
            with self.subTest(kind_words):
                inv, text = other_kind(line, kind_words, status_words)
                held_on_the_date(self, inv, text, UNIDENTIFIED, done=False)

    def test_d151_procedure_day_has_no_unidentified_field(self):
        """combination.ProcedureDay is e5628be56's again: labels, possible and undatable."""
        self.assertEqual([field.name for field in dataclasses.fields(combination.ProcedureDay)],
                         ['labels', 'possible', 'undatable'])


# --- recorded: what the withdrawal releases against 4f82e5056 ---------------------------------------------------------

def stated(lines: dict, item: dict) -> tuple:
    """(inventory, text) of an office note whose visit DOCUMENTS a significant, separately identifiable E/M service
    (P5, right after the visit's time line, as r5c_currency.stated_note places it), with the act ``item``."""
    return inventory({'V1': lines.pop('V1', VISIT), 'V2': TIME, 'P5': SEPARATE_LINE, **lines}, events=[visit(), item],
                     visits=[{**visit_facts(), 'separately_identifiable': a('stated', SEPARATE, ['P5'])}])


class D151Recorded(SimpleTestCase):
    """RECORDED, constructed inputs: the withdrawal restores e5628be56's READY where 4f82e5056 held."""

    def test_d151_recorded_releases_against_4f82e5056_beside_a_documented_statement(self):
        """RECORDED (DECISIONS D151, the census's RELEASE rows; constructed, none attested): beside a visit that
        documents a significant, separately identifiable E/M service, a procedure day asks neither separate_em nor
        event_time (D130's record), so where D144 had made the act UNDATABLE (99213 asked event_time) or set the visit
        apart (a second review's 99213 an informational alternative), the withdrawal makes 99213 READY with the modifier
        25 consideration, exactly as e5628be56. The document supports READY either way (the visit is documented
        separately identifiable, whatever the act's date), and c2e53f8e makes 99213 READY on each text when Corti
        proposes it (with the consideration, except D112's 'That same day' and the labs, where it shows none).
        - Problem 1's "Before today's visit, rubber band ligation ..." under gi.other and problem 2's banding (current
          encounter worded by the frame; under gi.other or the visit), D131's "Before today's visit, she had undergone
          an upper endoscopy at an outside hospital" and D112's "That same day ... at that hospital": 4f82e5056 held
          with event_time; now READY with the consideration.
        - Problem 3's "Labs were drawn in the office today." with a second review: 4f82e5056 set the visit apart and
          its 99213 was an informational alternative; now added, READY with the consideration (c2e53f8e: READY)."""
        egd = ("Before today's visit, she had undergone an upper endoscopy at an outside hospital, which showed a "
               'clean-based duodenal ulcer.')
        cases = (
            ("problem 1, under gi.other", stated(
                {'P2': "Before today's visit, rubber band ligation of one internal hemorrhoid was performed in the "
                       'office.', 'P3': PLAN},
                banding('other_gi', a('earlier_encounter', "Before today's visit", ['P2']))), VISIT),
            ('problem 2, under gi.other', stated({'P2': FRAME_BANDING, 'P3': PLAN},
                                                 banding('other_gi', a('current_encounter', FRAME, ['P2']))), VISIT),
            ('problem 2, under the visit', stated({'P2': FRAME_BANDING, 'P3': PLAN},
                                                  banding('office_em', a('current_encounter', FRAME, ['P2']))), VISIT),
            ("D131's record", stated({'P2': egd, 'P3': PLAN}, act(
                'E1', 'P2', 'examination', 'upper endoscopy', status_words='had undergone',
                procedure=a('egd', 'upper endoscopy', ['P2']),
                time=a('earlier_encounter', "Before today's visit", ['P2']),
                performer=a('other_facility', 'at an outside hospital', ['P2']))), VISIT),
            ("D112's 'That same day'", stated(
                {'V1': MELENA_VISIT, 'P1': ED_LINE, 'P2': OUTSIDE_EGD.format(words='That same day'), 'P3': PLAN},
                act('E1', 'P2', 'examination', 'upper endoscopy', status_words='had undergone',
                    procedure=a('egd', 'upper endoscopy', ['P2']), time=a('earlier_encounter', 'That same day', ['P2']),
                    performer=a('other_facility', 'at that hospital', ['P2']))), MELENA_VISIT),
        )
        for label, (inv, text), visit_line in cases:
            with self.subTest(label):
                self.assertEqual(day_of(inv), facts.ON)
                p = em(inv, text, visit_line)
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
                self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
        inv, text = stated({'P2': 'Labs were drawn in the office today.', 'P3': PLAN},
                           act('E1', 'P2', 'other', 'Labs', status_words='were drawn', procedure=a('unknown')))
        self.assertEqual(listing(inv, text), LISTED)
        self.assertEqual(second_99213(inv, text), [('selected', 'ready', [])])
