"""DECISIONS D162 (round 5f, narrowing only; the round-5e currency review's problem 5, round5e
'review:currency5' - D109's recorded residual, restated in D131), SYNTHETIC: a same-day frame standing whole anywhere in
an act's own time words places an act OFF by its own time on the date of service.

- Problem 5 (critical class): D81's office lines with "Earlier in the day, before her visit, rubber band ligation of one
  internal hemorrhoid was performed in the office." (gi.other, earlier_encounter verified) and D109's own "I performed
  an upper endoscopy earlier in the day, before her visit." (by 'I'). facts.day_of read both OFF the date - their words
  are not made only of whole frames (D109) - so 99213 was READY with no question and the visit listed on e5628be56,
  4f82e5056 and f9013e12e, where c2e53f8e holds 99213 with separate_em and sets the visit apart, and the document places
  the act on the date of service. Now a lexicon.SAME_DAY_FRAMES entry standing whole anywhere in the words places such
  an act ON (facts._same_day_frame with ``anywhere``; the frame's own folded words, no letter or digit touching either
  end), for an act whose performer is not verified other (D132's condition) and whose words carry no date literal.
- Built narrower than the literal reading, and why: only an act whose own usable earlier or future time would place it
  OFF moves. An UNDATABLE act keeps C-3's event_time question: read ON it would drop that question and, beside a
  documented statement, make 99213 READY - also where other words of the phrase name another day ("Yesterday, later in
  the evening, she underwent an upper endoscopy": v0 in round5f/currency6/out/census-cases.md).
- Recorded (D162Recorded): other words in the phrase can name another day beside a whole frame ("Last week, earlier in
  the day, I performed an upper endoscopy"): read ON as c2e53f8e reads it - a hold and the visit set apart that the
  document does not support; D109's own control "earlier in the morning of her admission" is one of them.

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). The installed release's outputs (c2e53f8e: engine.assess with gi_context.extract_context,
merge_user_values office/established and detect.route on 2026-11-09, as tests/test_harness_engine.py drives it, the same
synthetic reference rows) and e5628be56's, 4f82e5056's and f9013e12e's quoted in the docstrings were measured on
byte-identical texts (round5f/currency6/out/census-cases.tsv). Every input is constructed. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, facts
from tests.test_interpretation_events import asked, inventory, proposal, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_families import MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r4_em_same_day import OFFICE_14, OTHER_GI_LABEL, held_for_separate_em
from tests.test_interpretation_r5_em import ED_LINE, MELENA_VISIT, NON_GI_LABEL, OUTSIDE_EGD
from tests.test_interpretation_r5c_currency import EGD_LABEL, FLEX_SIG_LABEL, SEPARATE, SEPARATE_LINE, day_of
from tests.test_interpretation_r5e_currency import (APART, LISTED, SECOND_HELD, SECOND_INFORMATIONAL, em,
                                                    held_on_the_date, listing, second_99213)

DAY = '2026-11-09'
W5 = 'earlier in the day, before her visit'
BW = 'Earlier in the day, before her visit'
BAND_TAIL = 'rubber band ligation of one internal hemorrhoid was performed in the office.'
BLINE = f'{BW}, {BAND_TAIL}'
EGD5 = 'I performed an upper endoscopy earlier in the day, before her visit.'
UNIDENTIFIED = combination.UNIDENTIFIED_PROCEDURE


def office(line: str, item: dict, stated: bool = False, visit_line: str = VISIT, **lines) -> tuple:
    """(inventory, text) of D81's office note as the round-5e reviewer built it: the visit (E0, V1) and its total time
    (V2), the visit's separately identifiable statement P5 when ``stated``, ``lines``, the act line P2 (E1), the plan
    (P3)."""
    separate = {'separately_identifiable': a('stated', SEPARATE, ['P5'])} if stated else {}
    base = {'V1': visit_line, 'V2': TIME, **({'P5': SEPARATE_LINE} if stated else {}), **lines, 'P2': line, 'P3': PLAN}
    return inventory(base, events=[visit(), item], visits=[{**visit_facts(), **separate}])


def procedure(value: str, words: str) -> dict:
    return a('unknown') if value == 'unknown' else a(value, words, ['P2'])


def band(value: str, time: dict, performer=None) -> dict:
    """r5_em.banding: band_ligation 'rubber band ligation' (E1, P2), procedure ``value``, by the team by default."""
    extra = {} if performer is None else {'performer': performer}
    return act('E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='was performed',
               procedure=procedure(value, 'office' if value == 'office_em' else 'rubber band ligation'), time=time,
               target=tg('', 'anal_canal', 'one internal hemorrhoid', ['P2']), **extra)


def egd(time: dict, performer: dict, status_words: str = 'I performed', pid: str = 'P2') -> dict:
    return act('E1', pid, 'examination', 'upper endoscopy', status_words=status_words,
               procedure=a('egd', 'upper endoscopy', [pid]), time=time, performer=performer)


def flex(time: dict, performer: dict) -> dict:
    return act('E1', 'P2', 'examination', 'flexible sigmoidoscopy', status_words='I performed',
               procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P2']), time=time, performer=performer)


def by_i(pid: str = 'P2') -> dict:
    return a('documenting_team', 'I', [pid])


def ready_with_the_consideration(test, p):
    """99213 READY beside a documented statement on a procedure day: no question, the modifier 25 consideration."""
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
    test.assertTrue(any('Modifier 25' in m for m in p.modifier_considerations))


def stated_on_the_date(test, inv, text, label, *, done):
    """The '+S' twin (the visit documents a significant, separately identifiable E/M service): ON, 99213 READY with
    the modifier 25 consideration (as c2e53f8e), the visit set apart beside a done act or listed beside a possible one,
    a second review's 99213 an informational alternative or READY with the consideration."""
    test.assertEqual(day_of(inv), facts.ON)
    ready_with_the_consideration(test, em(inv, text))
    test.assertEqual(listing(inv, text), APART if done else LISTED)
    second = second_99213(inv, text)
    if done:
        test.assertEqual(second, [SECOND_INFORMATIONAL])
    else:
        test.assertEqual(second, [('selected', 'ready', [])])


def asks_event_time(test, p):
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['event_time']))


# --- (1) problem 5: a frame standing whole anywhere places an act OFF by its own time ON ---------------------------

class D162AFrameAnywherePlacesAnOffActOnTheDate(SimpleTestCase):
    """D162 (1): a lexicon.SAME_DAY_FRAMES entry standing whole anywhere in the time words of an act OFF by its own
    usable time, its performer not verified other, places it ON the date of service."""

    def test_d162_problem_5_the_banding_earlier_in_the_day_before_her_visit(self):
        """The review's problem 5, byte-identical to its input: D81's office lines with P2 "Earlier in the day, before
        her visit, rubber band ligation of one internal hemorrhoid was performed in the office." (band_ligation under
        gi.other 'rubber band ligation', performed, by the team, earlier_encounter worded "Earlier in the day, before
        her visit", verified by 'earlier'). e5628be56, 4f82e5056 and f9013e12e: OFF, 99213 READY with no question, the
        visit listed, a second review's 99213 READY. c2e53f8e: 99213 held with separate_em and the modifier 25
        consideration ("Other GI service is documented as performed on the same date"), the visit set apart, a second
        review's 99213 an informational alternative. Now as c2e53f8e; the stated twin is READY with the consideration
        on both."""
        inv, text = office(BLINE, band('other_gi', a('earlier_encounter', BW, ['P2'])))
        held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=True)
        inv, text = office(BLINE, band('other_gi', a('earlier_encounter', BW, ['P2'])), stated=True)
        stated_on_the_date(self, inv, text, OTHER_GI_LABEL, done=True)

    def test_d162_problem_5_d109s_upper_endoscopy_by_i(self):
        """The review's second input, byte-identical: "I performed an upper endoscopy earlier in the day, before her
        visit." (the EGD by 'I', earlier_encounter worded "earlier in the day, before her visit", verified); D109's
        own pin input (tests/test_interpretation_r4_em_same_day.py, the finding-14 office lines); and the whole
        sentence as the time words (FRESH-2 attests whole-line time words). Every new-path head: OFF, 99213 READY, the
        visit listed. c2e53f8e: held with separate_em ("Upper GI endoscopy ... is documented as performed on the same
        date"), the visit set apart. Now as c2e53f8e. With 43235 proposed beside it, 43235 was excluded on every
        new-path head, before and after D162 (it read its own time, not day_of); DECISIONS D169 (1) (round 5g):
        events.deciding reads the exclusion's time basis with day_of, so the act ON the date is never excluded for its
        time and 43235 is held (not documented as done at this encounter), as c2e53f8e holds it."""
        for label, (inv, text) in (
                ('the review', office(EGD5, egd(a('earlier_encounter', W5, ['P2']), by_i()))),
                ("D109's office lines", inventory({**OFFICE_14, 'P1': EGD5}, events=[visit(), egd(
                    a('earlier_encounter', W5, ['P1']), by_i('P1'), pid='P1')], visits=[visit_facts()])),
                ('the whole sentence', office(EGD5, egd(a('earlier_encounter', EGD5, ['P2']), by_i())))):
            with self.subTest(label):
                held_on_the_date(self, inv, text, EGD_LABEL, done=True)
        inv, text = office(EGD5, egd(a('earlier_encounter', W5, ['P2']), by_i()), stated=True)
        stated_on_the_date(self, inv, text, EGD_LABEL, done=True)
        inv, text = office(EGD5, egd(a('earlier_encounter', W5, ['P2']), by_i()))
        result = run(inv, text, [('99213', VISIT), ('43235', 'upper endoscopy')], user_values=MEMBER)
        self.assertEqual((proposal(result, '43235').bucket, proposal(result, '43235').status),
                         ('selected', 'needs_clarification'))  # D169 (1): was ('excluded', 'excluded')
        held_for_separate_em(self, proposal(result, '99213'), EGD_LABEL)

    def test_d162_the_class_other_frames_and_positions(self):
        """The class, by 'I' (flexible sigmoidoscopy, earlier_encounter verified): a frame first, last or inside the
        words - "Earlier in the morning, before clinic", "Earlier in the afternoon, before her appointment", "Earlier
        in the day, prior to her visit", "Before her visit, earlier in the day", "earlier in the morning in the
        endoscopy suite". Every new-path head: OFF, 99213 READY. c2e53f8e: held with separate_em, the visit set apart.
        Now as c2e53f8e."""
        for words in ('Earlier in the morning, before clinic', 'Earlier in the afternoon, before her appointment',
                      'Earlier in the day, prior to her visit', 'Before her visit, earlier in the day'):
            with self.subTest(words=words):
                inv, text = office(f'{words}, I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.',
                                   flex(a('earlier_encounter', words, ['P2']), by_i()))
                held_on_the_date(self, inv, text, FLEX_SIG_LABEL, done=True)
        words = 'earlier in the morning in the endoscopy suite'
        inv, text = office(f'I performed a flexible sigmoidoscopy {words}, which showed internal hemorrhoids.',
                           flex(a('earlier_encounter', words, ['P2']), by_i()))
        held_on_the_date(self, inv, text, FLEX_SIG_LABEL, done=True)

    def test_d162_the_class_filings_kinds_and_performers(self):
        """Problem 5's banding filed under the visit ('office': done, set apart) or with procedure 'unknown' (read by
        its kind: possible, listed); with performer 'unknown' or other_clinician without words (not verified other:
        possible); D94's excision of kind other "Earlier in the day, before her visit, excision ..." (not_gi: done,
        'Service outside the GI profiles'; 'unknown': possible, 'A procedure CPT Studio could not identify'); the EGD
        by a performer 'unknown' ("She underwent ..."): possible. Every new-path head: OFF, 99213 READY, a second
        review's 99213 READY. c2e53f8e: 99213 held with separate_em on each; it sets the visit apart beside each
        (where the act is only possible here, the visit stays listed and a second review's 99213 is added held - D134's
        recorded difference, a listing kept, never a READY)."""
        excision = ('Earlier in the day, before her visit, excision of a 1 cm sebaceous cyst on the upper back was '
                    'performed in the office.')
        cases = (
            ('under the visit', BLINE, band('office_em', a('earlier_encounter', BW, ['P2'])), OTHER_GI_LABEL, True),
            ("procedure 'unknown'", BLINE, band('unknown', a('earlier_encounter', BW, ['P2'])), OTHER_GI_LABEL, False),
            ("performer 'unknown'", BLINE, band('other_gi', a('earlier_encounter', BW, ['P2']), performer=a('unknown')),
             OTHER_GI_LABEL, False),
            ('other_clinician without words', BLINE,
             band('other_gi', a('earlier_encounter', BW, ['P2']), performer=a('other_clinician')), OTHER_GI_LABEL,
             False),
            ('the excision, not_gi', excision, act(
                'E1', 'P2', 'other', 'excision of a 1 cm sebaceous cyst', status_words='was performed',
                procedure=a('not_gi', 'excision of a 1 cm sebaceous cyst', ['P2']),
                time=a('earlier_encounter', BW, ['P2'])), NON_GI_LABEL, True),
            ("the excision, 'unknown'", excision, act(
                'E1', 'P2', 'other', 'excision of a 1 cm sebaceous cyst', status_words='was performed',
                procedure=a('unknown'), time=a('earlier_encounter', BW, ['P2'])), UNIDENTIFIED, False),
            ("the EGD, performer 'unknown'", 'She underwent an upper endoscopy earlier in the day, before her visit.',
             egd(a('earlier_encounter', W5, ['P2']), a('unknown'), status_words='underwent'), EGD_LABEL, False),
        )
        for label, line, item, family_label, done in cases:
            with self.subTest(label):
                inv, text = office(line, item)
                held_on_the_date(self, inv, text, family_label, done=done)
            with self.subTest(label, stated=True):
                inv, text = office(line, item, stated=True)
                stated_on_the_date(self, inv, text, family_label, done=done)

    def test_d162_the_frame_stands_whole_anywhere(self):
        """facts._same_day_frame with ``anywhere``: a SAME_DAY_FRAMES entry whose own folded words stand whole anywhere
        in the words - a frame first, last or inside them, any case, a dash or punctuation beside it; never inside a
        longer word ('earlier in the daytime', 'earlier in the days before her visit'), never an anaphoric frame
        ('Earlier that day, before her visit': D132's frames are read whole only), never a bare 'that day' or 'in the
        morning'. Without ``anywhere`` D109's whole reading is unchanged: only words made of frames."""
        for words in (W5, BW, EGD5, 'Before her visit, earlier in the day', 'earlier in the morning in the endoscopy '
                      'suite', 'Later in the afternoon, after clinic', 'On the date of service, before the visit',
                      '(earlier in the day)', 'EARLIER IN THE DAY—before her visit', 'earlier in the evening.'):
            with self.subTest(words=words, anywhere=True):
                self.assertTrue(facts._same_day_frame(words, anywhere=True))
        for words in ('earlier in the daytime', 'earlier in the days before her visit', 'Earlier that day, before her '
                      'visit', 'Earlier that morning, before clinic', 'that day', 'in the morning', 'earlier',
                      'previously', 'earlier this year', 'earlier in the dayx', '', ',;'):
            with self.subTest(words=words, anywhere=True):
                self.assertFalse(facts._same_day_frame(words, anywhere=True))
        for words in (W5, EGD5, 'Before her visit, earlier in the day'):
            with self.subTest(words=words, anywhere=False):
                self.assertFalse(facts._same_day_frame(words))
                self.assertFalse(facts._same_day_frame(words, anaphoric=True))
        for words in ('earlier in the day', 'Earlier in the morning,', 'earlier in the day; earlier today'):
            with self.subTest(words=words, whole=True):
                self.assertTrue(facts._same_day_frame(words))
                self.assertTrue(facts._same_day_frame(words, anywhere=True))


# --- (1) built narrower: what the reading never moves -----------------------------------------------------------------

class D162WhatTheReadingNeverMoves(SimpleTestCase):
    """D162: only an act OFF by its own usable time moves; never an UNDATABLE act, never a verified other's act, never
    words that carry a date literal."""

    def test_d162_an_undatable_act_keeps_its_event_time_question(self):
        """The literal reading's counterexample (v0, measured): an act whose time is not usable keeps C-3's event_time
        question, with or without a documented statement. "Yesterday, later in the evening, she underwent an upper
        endoscopy" (earlier_encounter, no earlier marker: unverified; the document gives yesterday): every new-path
        head asks event_time; read ON (v0) it asked separate_em and, beside the statement, made 99213 READY - a
        released question and a READY the document does not support (c2e53f8e: separate_em / READY). Also the EGD by
        'I' given current_encounter "earlier in the day, before her visit" (D35's other occasion: unverified),
        "Later in the day, after her visit" (earlier_encounter, unverified) and "On the date of service, before the
        visit" (unverified): event_time on every new-path head and here; c2e53f8e asks separate_em, and beside the
        statement is READY with the consideration (a cost, as on f9013e12e)."""
        line = 'Yesterday, later in the evening, she underwent an upper endoscopy, which showed gastritis.'
        words = 'Yesterday, later in the evening'
        cases = (
            ('yesterday, unverified', line, egd(a('earlier_encounter', words, ['P2']), a('unknown'),
                                                status_words='underwent')),
            ('current_encounter, unverified', EGD5, egd(a('current_encounter', W5, ['P2']), by_i())),
            ('later in the day, unverified', 'Later in the day, after her visit, I performed a flexible sigmoidoscopy, '
                                             'which showed internal hemorrhoids.',
             flex(a('earlier_encounter', 'Later in the day, after her visit', ['P2']), by_i())),
            ('on the date of service, unverified', 'On the date of service, before the visit, I performed a flexible '
                                                   'sigmoidoscopy, which showed internal hemorrhoids.',
             flex(a('earlier_encounter', 'On the date of service, before the visit', ['P2']), by_i())),
        )
        for label, text_line, item in cases:
            for stated in (False, True):
                with self.subTest(label, stated=stated):
                    inv, text = office(text_line, item, stated=stated)
                    self.assertEqual(day_of(inv), facts.UNDATABLE)
                    asks_event_time(self, em(inv, text))

    def test_d162_a_verified_other_and_a_date_literal_decide(self):
        """D132's condition kept: "Earlier in the day, before her visit, she had undergone an upper endoscopy at an
        outside hospital." with the performer verified other_facility is OFF and 99213 READY on every tree, c2e53f8e
        included. Words with a date literal are decided by the literal, never by a frame: "On 10/30/2026, earlier in
        the day" and "earlier in the day in 2024" are OFF and READY (c2e53f8e READY)."""
        outside = 'Earlier in the day, before her visit, she had undergone an upper endoscopy at an outside hospital.'
        cases = (
            ('a verified other facility', outside,
             egd(a('earlier_encounter', BW, ['P2']), a('other_facility', 'at an outside hospital', ['P2']),
                 status_words='had undergone')),
            ('another date', 'On 10/30/2026, earlier in the day, I performed an upper endoscopy, which showed '
                             'gastritis.', egd(a('earlier_encounter', 'On 10/30/2026, earlier in the day', ['P2']),
                                               by_i())),
            ('another year', 'Earlier in the day in 2024, I performed an upper endoscopy, which showed gastritis.',
             egd(a('earlier_encounter', 'earlier in the day in 2024', ['P2']), by_i())),
        )
        for label, line, item in cases:
            with self.subTest(label):
                inv, text = office(line, item)
                self.assertEqual(day_of(inv), facts.OFF)
                p = em(inv, text)
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
                self.assertEqual(listing(inv, text), LISTED)

    def test_d162_an_anaphoric_frame_beside_other_words_is_not_read(self):
        """Recorded residual, not built (the spec names lexicon.SAME_DAY_FRAMES): "Earlier that day, before her visit,
        I performed an upper endoscopy" and "Earlier that morning, before clinic, ..." (by 'I', verified) stay OFF and
        99213 READY on every new-path head and here; c2e53f8e holds 99213 with separate_em. D132's anaphoric frames are
        read whole only."""
        for words in ('Earlier that day, before her visit', 'Earlier that morning, before clinic'):
            with self.subTest(words=words):
                inv, text = office(f'{words}, I performed an upper endoscopy, which showed gastritis.',
                                   egd(a('earlier_encounter', words, ['P2']), by_i()))
                self.assertEqual(day_of(inv), facts.OFF)
                p = em(inv, text)
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))


# --- recorded ---------------------------------------------------------------------------------------------------------

class D162Recorded(SimpleTestCase):
    """D162's recorded outcomes: a frame read anywhere beside words that name another day (constructed; equal to
    c2e53f8e, not what the document supports), the cost it adds on D112's text, and problems 1-2 unchanged."""

    def test_d162_recorded_another_day_named_beside_a_frame(self):
        """RECORDED: other words of the phrase can name another day beside a whole frame. "Last week, earlier in the
        day", "At her prior visit, earlier in the day", "Two weeks ago, later in the afternoon" and "earlier in the
        morning of her admission" (the EGD by 'I', verified), and the banding "At her last visit, earlier in the day":
        f9013e12e OFF, 99213 READY, the visit listed; now ON, done, 99213 held with separate_em, the visit set apart, a
        second review's 99213 informational - exactly c2e53f8e's outcome on each, which the document does not support
        (the act is another day's). D109's own control "earlier in the morning of her admission" is the unit form."""
        for words in ('Last week, earlier in the day', 'At her prior visit, earlier in the day',
                      'Two weeks ago, later in the afternoon'):
            with self.subTest(words=words):
                inv, text = office(f'{words}, I performed an upper endoscopy, which showed gastritis.',
                                   egd(a('earlier_encounter', words, ['P2']), by_i()))
                held_on_the_date(self, inv, text, EGD_LABEL, done=True)
        words = 'earlier in the morning of her admission'
        inv, text = office(f'I performed an upper endoscopy {words}, which showed gastritis.',
                           egd(a('earlier_encounter', words, ['P2']), by_i()))
        held_on_the_date(self, inv, text, EGD_LABEL, done=True)
        words = 'At her last visit, earlier in the day'
        inv, text = office(f'{words}, {BAND_TAIL}', band('other_gi', a('earlier_encounter', words, ['P2'])))
        held_on_the_date(self, inv, text, OTHER_GI_LABEL, done=True)

    def test_d162_recorded_cost_d112s_melena_note_with_an_unknown_performer(self):
        """RECORDED COST: D112's melena note (the ED visit on 10/30/2026) with "Earlier in the day, before her ED visit,
        she had undergone an upper endoscopy at that hospital, ..." and the performer 'unknown' (no verified other):
        f9013e12e OFF, 99213 READY; now ON, a possible EGD, 99213 held with separate_em, the visit listed. c2e53f8e is
        READY; the document places the EGD on 10/30 (D132's recorded class: no verified other's act)."""
        line = ('Earlier in the day, before her ED visit, she had undergone an upper endoscopy at that hospital, which '
                'showed a clean-based duodenal ulcer.')
        item = egd(a('earlier_encounter', 'Earlier in the day, before her ED visit', ['P2']), a('unknown'),
                   status_words='had undergone')
        inv, text = inventory({'V1': MELENA_VISIT, 'V2': TIME, 'P1': ED_LINE, 'P2': line, 'P3': PLAN},
                              events=[act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                                          procedure=a('office_em', 'Office visit', ['V1'])), item],
                              visits=[visit_facts()])
        self.assertEqual(day_of(inv), facts.ON)
        held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)
        self.assertEqual(listing(inv, text), LISTED)
        self.assertEqual(second_99213(inv, text, MELENA_VISIT), [SECOND_HELD])

    def test_d162_recorded_problems_1_and_2_do_not_move(self):
        """RECORD, do not build: problem 1's "I performed her last upper endoscopy three months prior to today's
        visit, ..." is ON by 'today's' (D131) on every new-path head and here - held, the visit set apart, where
        c2e53f8e is READY and lists it (a cost equal to e5628be56); problem 2's other-facility frames (D112's melena
        note, the EGD 'at that hospital', verified): "Earlier that same day" and "That same day" ON by 'same day',
        "Earlier that day" OFF (D132: no anaphoric frame for a verified other), "Earlier in the day" ON (a whole
        frame: D132's recorded em problem 3) - each as on f9013e12e and e5628be56."""
        words = "three months prior to today's visit"
        inv, text = office(f"I performed her last upper endoscopy {words}, which showed gastritis.",
                           egd(a('earlier_encounter', words, ['P2']), by_i()))
        held_on_the_date(self, inv, text, EGD_LABEL, done=True)
        for words, expected in (('Earlier that same day', facts.ON), ('That same day', facts.ON),
                                ('Earlier that day', facts.OFF), ('Earlier in the day', facts.ON)):
            with self.subTest(words=words):
                inv, _ = inventory({'V1': MELENA_VISIT, 'V2': TIME, 'P1': ED_LINE,
                                    'P2': OUTSIDE_EGD.format(words=words), 'P3': PLAN},
                                   events=[act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                                               procedure=a('office_em', 'Office visit', ['V1'])),
                                           egd(a('earlier_encounter', words, ['P2']),
                                               a('other_facility', 'at that hospital', ['P2']),
                                               status_words='had undergone')], visits=[visit_facts()])
                self.assertEqual(day_of(inv), expected)
