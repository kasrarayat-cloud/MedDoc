"""DECISIONS D131-D134 and the D130 record (the reviews of round 5b: review-committed_em problems 0-5, review_em2
problems 0-3), SYNTHETIC: the same-day E/M rule's currency, its anaphoric frames, the statement arm's date and head, and
the visit item beside a procedure only possibly done.

- D131 (em problem 0): facts._same_day_word matched SAME_DAY_WORDS on words that still carried their punctuation, so
  "Earlier today, excision ..." (a verified earlier_encounter time worded by the whole sentence) never held "today", its
  "earlier" made it OFF and 99213 was READY where c2e53f8e holds it. The words are now matched at word boundaries
  whatever punctuation touches them.
- D132 (em problems 2, 4 and 5): D112 removed the anaphoric frames ("Earlier that day", "Later that morning"), which
  released finding 14's G2 and "Earlier that morning, I performed a flexible sigmoidoscopy ..." (by 'I') and asked
  event_time instead of separate_em for problem 2's banding. They are back as lexicon.ANAPHORIC_FRAMES, read for every
  act whose performer is NOT verified to another clinician or facility; D112's own source (the outside EGD "Earlier that
  day ... at that hospital", other_facility verified) is read without them and stays READY.
- D133 (em2 problems 0 and 1): an act read by its statement (D130) that is UNDATABLE is listed for the E/M's time
  question like every other act ("During this visit, excision ..."), the history-mention exception kept; and the
  never-counted classes are read in the KIND words' head only, never in the target words ("seen on ultrasound"), and
  never set an imaging-guided procedure apart ("Ultrasound-guided paracentesis").
- D134 (em2 problem 3, em problem 1): an office visit with no supported proposal is set apart (not_listed) only beside
  a procedure DONE on the date of service (ProcedureDay.labels, or another family's done session); beside one only
  POSSIBLY done it stays listed, 'has no supported proposal', as c2e53f8e lists it beside the DRE, the complete physical
  examination and the stool guaiac filed under the visit, and beside the CT "obtained earlier today". The separate_em
  hold those inputs put on 99213 stays: a recorded cost.
- The D130 record (em2 problem 2): a possible label makes a procedure day, and a procedure day with a documented
  separately identifiable statement asks neither separate_em nor event_time, so beside an undatable act it can make a
  held E/M READY (with the modifier 25 consideration) - as c2e53f8e is READY on that input.

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). The installed release's outputs (c2e53f8e: engine.assess with gi_context.extract_context,
merge_user_values office/established and detect.route on 2026-11-09, as tests/test_harness_engine.py drives it) quoted
in the docstrings were measured on byte-identical texts. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.gi import profiles
from studio.interpretation import combination, coverage, events, facts, lexicon, overlay
from studio.validation import checks
from tests.test_interpretation_events import asked, check, inventory, proposal, response, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_families import MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r4_em_same_day import (OTHER_GI_LABEL, THAT_DAY_LINE, earlier_act, held_for_separate_em,
                                                      ready_with_no_procedure_day)
from tests.test_interpretation_r5_em import (BAND, CYST, ED_LINE, MELENA_VISIT, NO_PROPOSAL, NON_GI_LABEL,
                                             OUTSIDE_EGD, banding, excision, office)
from tests.test_interpretation_r5_em2 import OFFICE_WORD, POSSIBLY, VISIT_WORDS, note, other

DAY = '2026-11-09'
CYST_KIND = 'Excision of a 1 cm sebaceous cyst'
EXCISION_TODAY = 'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office today.'
FLEX_SIG_LABEL = profiles.PROFILES['gi.flex_sig'].label  # 'Flexible sigmoidoscopy'
EGD_LABEL = profiles.PROFILES['gi.egd'].label
NOT_LISTED = 'office / outpatient visit beside a procedure done or possibly done the same day'
TIME_QUESTION = 'Was the act (“was performed”) done at this encounter?'


def reading_of(inv):
    return events.Reading.of(inv)


def procedure_day(inv):
    return combination.procedure_day(reading_of(inv), DAY)


def em(inv, text, visit_line=VISIT, user_values=MEMBER):
    return proposal(run(inv, text, [('99213', visit_line)], user_values=user_values), '99213')


def day_of(inv, eid='E1'):
    return facts.day_of(reading_of(inv).events[eid], DAY)


def no_em(inv, text):
    """The completeness with no E/M code proposed: (the unresolved item labels, the not_listed labels)."""
    completeness = run(inv, text, [], user_values=MEMBER).completeness
    return ([str(item.get('label')) for item in completeness['unresolved_items']],
            [str(item.get('label')) for item in completeness['not_listed']])


def melena(words: str, performer=None) -> tuple:
    """(inventory, text) of D112's source (the review of D109, problem 3): the melena follow-up (E0, V1), the ED visit
    on 10/30/2026 (P1) and the outside EGD (E1, P2), earlier_encounter worded ``words``, its performer ``performer``
    (other_facility 'at that hospital' by default) - the text byte-identical to tests/test_interpretation_r5_em.py's."""
    egd = act('E1', 'P2', 'examination', 'upper endoscopy', status_words='had undergone',
              procedure=a('egd', 'upper endoscopy', ['P2']), time=a('earlier_encounter', words, ['P2']),
              performer=performer if performer is not None else a('other_facility', 'at that hospital', ['P2']))
    return inventory({'V1': MELENA_VISIT, 'V2': TIME, 'P1': ED_LINE, 'P2': OUTSIDE_EGD.format(words=words), 'P3': PLAN},
                     events=[act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                                 procedure=a('office_em', 'Office visit', ['V1'])), egd], visits=[visit_facts()])


SEPARATE_LINE = 'A significant, separately identifiable E/M service was provided.'
SEPARATE = 'A significant, separately identifiable E/M service was provided'


def stated_note(line: str, item: dict) -> tuple:
    """(inventory, text) of the families review's office document with the visit's separately identifiable statement
    (P5, stated, before the act line P2) and the act ``item``."""
    lines = {'V1': VISIT, 'V2': TIME, 'P5': SEPARATE_LINE, 'P2': line, 'P3': PLAN}
    return inventory(lines, events=[visit(), item], visits=[
        {**visit_facts(), 'separately_identifiable': a('stated', SEPARATE, ['P5'])}])


def cyst_with_time(words: str, line: str = None) -> tuple:
    """Problem 0's excision (kind other, procedure not_gi, by the documenting team) on D81's office lines, its time
    earlier_encounter worded ``words`` (the P2 line ``line``, by default ``words`` followed by the excision)."""
    line = line if line is not None else f'{words}, {CYST}.'
    return office(line, excision('not_gi', a('earlier_encounter', words, ['P2'])))


# --- D131: a same-day word is read whatever punctuation touches it ----------------------------------------------------

class D131SameDayWordsWhateverTouchesThem(SimpleTestCase):
    """D131 (em problem 0): SAME_DAY_WORDS at word boundaries, punctuation and all."""

    def test_d131_problem_0_earlier_today_with_a_comma_is_on_the_date(self):
        """The review's problem 0, byte-identical: D81's office lines with 'Earlier today, excision of a 1 cm sebaceous
        cyst on the upper back was performed in the office.' (E1 kind other, procedure not_gi, performed, by the
        documenting team), Gemini's time earlier_encounter worded by the whole sentence (FRESH-2 attests whole-line time
        words), and by 'Earlier today, excision'. 46e461e7f: day_of OFF (its verified 'earlier'), 99213 READY;
        c2e53f8e: held, separate_em ('Other GI service is documented as performed on the same date'). Now ON, the
        act a done non-GI service, 99213 held with separate_em."""
        line = f'Earlier today, {CYST}.'
        for words in (line, 'Earlier today, excision'):
            with self.subTest(words=words):
                inv, text = cyst_with_time(words, line)
                self.assertEqual(reading_of(inv).events['E1']['time']['state'], 'verified')
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(labels=(NON_GI_LABEL,)))
                held_for_separate_em(self, em(inv, text), NON_GI_LABEL)

    def test_d131_problem_0_its_variants_a_to_e(self):
        """Problem 0's (a)-(e), each READY at 46e461e7f and held with separate_em at c2e53f8e: (a) the banding with
        procedure 'unknown' and whole-sentence words; (b) 'Earlier today, before her visit'; (c) 'Earlier today, at
        8:30'; (d) the flexible sigmoidoscopy 'Earlier today, before the visit' by 'I' (gi.flex_sig); (e) 'This
        morning, before clinic' (no earlier marker: UNDATABLE at 46e461e7f, and then the history-mention exception
        skipped it). Each is now ON and held with separate_em."""
        band_line = 'Earlier today, rubber band ligation of one internal hemorrhoid was performed in the office.'
        before = 'Earlier today, before the visit'
        flex = act('E1', 'P2', 'examination', 'flexible sigmoidoscopy', status_words='I performed',
                   procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P2']),
                   time=a('earlier_encounter', before, ['P2']), performer=a('documenting_team', 'I', ['P2']))
        cases = (
            ("(a) the banding, procedure 'unknown'",
             office(band_line, banding('unknown', a('earlier_encounter', band_line, ['P2']))), OTHER_GI_LABEL),
            ("(b) 'Earlier today, before her visit'", cyst_with_time('Earlier today, before her visit'), NON_GI_LABEL),
            ("(c) 'Earlier today, at 8:30'", cyst_with_time('Earlier today, at 8:30'), NON_GI_LABEL),
            ('(d) the flexible sigmoidoscopy by I', office(
                f'{before}, I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.', flex),
             FLEX_SIG_LABEL),
            ("(e) 'This morning, before clinic'", cyst_with_time('This morning, before clinic'), NON_GI_LABEL),
        )
        for label, (inv, text), family_label in cases:
            with self.subTest(label):
                self.assertEqual(day_of(inv), facts.ON)
                found = procedure_day(inv)
                self.assertIn(family_label, found.labels + found.possible)
                held_for_separate_em(self, em(inv, text), family_label)

    def test_d131_the_no_comma_control_is_unchanged(self):
        """The review's control: 'Earlier today before her visit' (no comma) was ON at 46e461e7f and is ON now, held
        with separate_em as c2e53f8e holds it. What holds no same-day word is unchanged, OFF and READY as at
        46e461e7f: 'Earlier this year, at 8:30' and 'Previously, at 8:30' (another date; c2e53f8e holds both, its
        routing reading the excision line as performed whatever its time words), and 'earlier in the day, before her
        visit' - D109's recorded residual (no whole frame; c2e53f8e holds it)."""
        inv, text = cyst_with_time('Earlier today before her visit')
        self.assertEqual(day_of(inv), facts.ON)
        held_for_separate_em(self, em(inv, text), NON_GI_LABEL)
        for words in ('earlier in the day, before her visit', 'Earlier this year, at 8:30', 'Previously, at 8:30'):
            with self.subTest(words=words):
                inv, text = cyst_with_time(words)
                self.assertEqual(day_of(inv), facts.OFF)
                ready_with_no_procedure_day(self, em(inv, text))

    def test_d131_same_day_words_are_word_bounded_whatever_punctuation_touches_them(self):
        """facts._same_day_word over the time's own words: every character that is not a letter or a digit is a word
        boundary - a comma, a full stop, a bracket, a colon, a semicolon, an apostrophe, a dash, a line break - and a
        same-day word inside a longer word is none ('todays', 'yesterday', 'this mornings'). As the rule reads every
        such character as a space, punctuation between the words of a two-word entry joins them too ('this, morning':
        recorded in DECISIONS D131; it only places more on the date)."""
        for words in ('Earlier today, excision', 'Earlier today, at 8:30', 'This morning, before clinic', '(today)',
                      'today.', 'today;', 'today:', 'TODAY,', "at today's visit", 'this\nmorning,', 'same-day',
                      'on the same date.', 'this evening—late', 'tonight!', 'this, morning'):
            with self.subTest(words=words):
                self.assertTrue(facts._same_day_word(words))
        for words in ('todays visit', 'yesterday, at 8:30', 'this mornings', 'heretoday', 'to-day', '', ',;',
                      'earlier in the day, before her visit', 'the same', 'this year, at 8:30'):
            with self.subTest(words=words):
                self.assertFalse(facts._same_day_word(words))


# --- D132: the anaphoric frames, by performer -------------------------------------------------------------------------

ANAPHORIC = ('earlier that day', 'later that day', 'earlier that same day', 'later that same day',
             'earlier that morning', 'earlier that afternoon', 'later that morning', 'later that afternoon',
             'later that evening', 'that same day')  # D112's removed list: d353e64df's SAME_DAY_FRAMES less 46e461e7f's
MORNING_FLEX = 'Earlier that morning, I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.'
LATER_BAND = 'Later that morning, rubber band ligation of one internal hemorrhoid was performed in the office.'


class D132AnaphoricFramesByPerformer(SimpleTestCase):
    """D132: the anaphoric frames are read for an act whose performer is not verified other."""

    def test_d132_g2_and_problem_4_this_notes_own_act_earlier_that_day_or_morning_is_on_the_date(self):
        """Finding 14's G2 ('Earlier that day, I performed a flexible sigmoidoscopy, which showed internal
        hemorrhoids.') and the review's problem 4 ('Earlier that morning, I performed a flexible sigmoidoscopy, ...'):
        earlier_encounter verified by its 'earlier', the act by 'I' (documenting_team verified). 46e461e7f: OFF, 99213
        READY; c2e53f8e and d353e64df: held, separate_em ('Flexible sigmoidoscopy is documented as performed on the
        same date'). Now ON, the sigmoidoscopy documented as performed, 99213 held with separate_em, and the routing
        stand-in reads the family performed."""
        cases = (('G2', earlier_act(THAT_DAY_LINE, 'examination', 'flexible sigmoidoscopy',
                                    a('flex_sig', 'flexible sigmoidoscopy', ['P1']), 'Earlier that day')),
                 ('problem 4', office(MORNING_FLEX, act(
                     'E1', 'P2', 'examination', 'flexible sigmoidoscopy', status_words='I performed',
                     procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P2']),
                     time=a('earlier_encounter', 'Earlier that morning', ['P2']),
                     performer=a('documenting_team', 'I', ['P2'])))))
        for label, (inv, text) in cases:
            with self.subTest(label):
                stored = reading_of(inv).events['E1']
                self.assertTrue(events.usable(stored, 'time'))
                self.assertFalse(events.verified_other_performer(stored))
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv).labels, (FLEX_SIG_LABEL,))
                p = em(inv, text)
                held_for_separate_em(self, p, FLEX_SIG_LABEL)
                self.assertIn(f'{FLEX_SIG_LABEL} is documented as performed on the same date',
                              check(p, 'em.same_day_procedure').detail)
                self.assertIn({'family': 'gi.flex_sig', 'status': 'performed', 'mentions': [], 'facts': [],
                               'missing': []}, facts.routing_stand_in(inv, DAY)['findings'])

    def test_d132_problem_2_later_that_morning_filed_under_the_visit_asks_separate_em(self):
        """The review's problem 2: 'Later that morning, rubber band ligation of one internal hemorrhoid was performed
        in the office.' filed under the visit (office_em 'office', findings 13/23's filing), current_encounter 'Later
        that morning' (unverified: other_occasion). 46e461e7f: UNDATABLE, 99213 asks event_time ('Was the band
        ligation ...'); c2e53f8e and d353e64df: held, separate_em ('Other GI service is documented as performed on
        the same date'). Now ON, a possible other GI service (its time unverified), 99213 held with separate_em and
        no event_time."""
        item = act('E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='was performed',
                   procedure=a('office_em', 'office', ['P2']),
                   time=a('current_encounter', 'Later that morning', ['P2']),
                   target=tg('', 'anal_canal', 'one internal hemorrhoid', ['P2']))
        inv, text = office(LATER_BAND, item)
        self.assertFalse(events.usable(reading_of(inv).events['E1'], 'time'))
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
        held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)

    def test_d132_with_a_documented_statement_problem_2s_banding_releases_the_e_m(self):
        """An effect, recorded: problem 2's banding 'Later that morning' beside 'A significant, separately identifiable
        E/M service was provided.' (stated). 46e461e7f: UNDATABLE, 99213 held with event_time; c2e53f8e: READY with the
        modifier 25 consideration. Now ON, a possible procedure day whose documented statement releases the E/M:
        READY with the modifier 25 consideration, as c2e53f8e gives it - a held E/M made READY, equal to the installed
        release's, through the documented statement only (assess: separate_em only with no statement)."""
        band = act('E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='was performed',
                   procedure=a('office_em', 'office', ['P2']),
                   time=a('current_encounter', 'Later that morning', ['P2']),
                   target=tg('', 'anal_canal', 'one internal hemorrhoid', ['P2']))
        inv, text = stated_note(LATER_BAND, band)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
        p = em(inv, text)
        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
        self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
        self.assertIn('The documentation states', check(p, 'em.same_day_procedure').detail)

    def test_d132_d112s_source_stays_ready_through_its_verified_other_facility(self):
        """D112's own source (the review of D109, problem 3): 'On 10/30/2026 she was seen in the emergency department of
        another hospital for melena.' / 'Earlier that day she had undergone an upper endoscopy at that hospital, ...',
        the EGD earlier_encounter 'Earlier that day' (verified), performer other_facility 'at that hospital'
        (verified). Its performer IS verified other, so it is read without the anaphoric frames - by its own value and
        marker, OFF - and 99213 is READY with the visit item listed, as c2e53f8e and 46e461e7f give it. 'Later that
        morning' there stays UNDATABLE (event_time, as at 46e461e7f: D112's recorded cost, c2e53f8e READY)."""
        inv, text = melena('Earlier that day')
        stored = reading_of(inv).events['E1']
        self.assertTrue(events.verified_other_performer(stored))
        self.assertEqual((stored['time']['state'], day_of(inv)), ('verified', facts.OFF))
        self.assertEqual(procedure_day(inv), combination.ProcedureDay())
        ready_with_no_procedure_day(self, em(inv, text, MELENA_VISIT))
        self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
        inv, text = melena('Later that morning')
        self.assertEqual(day_of(inv), facts.UNDATABLE)
        self.assertEqual(asked(em(inv, text, MELENA_VISIT)), ['event_time'])

    def test_d132_an_outside_act_whose_performer_is_not_verified_other_reads_the_frames(self):
        """The rule's other side, on D112's text: the same outside EGD with its performer other_facility WITHOUT words
        (unverified: no facility named), or left 'unknown', is no verified other's act, so 'Earlier that day' places it
        on the date: a possible EGD, 99213 held with separate_em. THE COST, recorded: c2e53f8e reads the same text
        READY."""
        for label, performer in (('other_facility, no words', a('other_facility')), ("'unknown'", a('unknown'))):
            with self.subTest(label):
                inv, text = melena('Earlier that day', performer)
                stored = reading_of(inv).events['E1']
                self.assertFalse(events.verified_other_performer(stored))
                self.assertEqual(day_of(inv), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(EGD_LABEL,)))
                held_for_separate_em(self, em(inv, text, MELENA_VISIT), EGD_LABEL)

    def test_d132_day_of_reads_the_performer_as_events_verified_other_performer(self):
        """day_of's performer reading (written with verify, as facts imports no events) equals
        events.verified_other_performer: over a verified other clinician (an outside gastroenterologist), one whose name
        cannot be told from the team's (unverified: name_not_other), a verified and an unverified other facility, the
        documenting team by its words and by the frame default, and 'unknown', an act worded 'Earlier that day' is OFF
        exactly when its performer is verified other, ON otherwise."""
        performers = (('other_clinician, verified', a('other_clinician', 'an outside gastroenterologist', ['P2'])),
                      ('other_clinician, named', a('other_clinician', 'Dr. Lena Park', ['P2'])),
                      ('other_facility, named', a('other_facility', 'at that hospital', ['P2'])),
                      ('other_facility, no words', a('other_facility')),
                      ('documenting_team', a('documenting_team', 'I', ['P2'])),
                      ('the frame default', None), ("'unknown'", a('unknown')))
        line = ('Earlier that day an upper endoscopy was performed by Dr. Lena Park, an outside gastroenterologist, at '
                'that hospital, I noted.')
        seen = {}
        for label, performer in performers:
            with self.subTest(label):
                changes = {'performer': performer} if performer is not None else {}
                item = act('E1', 'P2', 'examination', 'upper endoscopy', status_words='was performed',
                           procedure=a('egd', 'upper endoscopy', ['P2']),
                           time=a('earlier_encounter', 'Earlier that day', ['P2']), **changes)
                inv, _ = office(line, item)
                seen[label] = other = events.verified_other_performer(reading_of(inv).events['E1'])
                self.assertEqual(day_of(inv), facts.OFF if other else facts.ON)
        self.assertEqual({label for label, other in seen.items() if other},
                         {'other_clinician, verified', 'other_facility, named'})

    def test_d132_the_anaphoric_frames_are_d112s_list_in_their_own_tuple(self):
        """lexicon.ANAPHORIC_FRAMES is exactly the list D112 removed (d353e64df's SAME_DAY_FRAMES less 46e461e7f's),
        kept apart from SAME_DAY_FRAMES; facts reads it folded and only when asked to, whole (never 'Earlier that day,
        before her visit'), and never a bare 'that day' or 'that morning'. 'earlier that evening' was never in
        d353e64df's list and is no frame."""
        self.assertEqual(lexicon.ANAPHORIC_FRAMES, ANAPHORIC)
        self.assertFalse(set(lexicon.ANAPHORIC_FRAMES) & set(lexicon.SAME_DAY_FRAMES))
        self.assertEqual(facts._ANAPHORIC_FRAMES, frozenset(lexicon.fold(f) for f in lexicon.ANAPHORIC_FRAMES))
        for frame in ANAPHORIC:
            with self.subTest(frame=frame):
                self.assertTrue(facts._same_day_frame(frame.capitalize() + ',', anaphoric=True))
                self.assertFalse(facts._same_day_frame(frame))
        for words in ('Earlier that day, before her visit', 'that day', 'that morning', 'earlier that evening',
                      'earlier that week'):
            with self.subTest(words=words):
                self.assertFalse(facts._same_day_frame(words, anaphoric=True))
        self.assertTrue(facts._same_day_frame('Earlier that day; later today', anaphoric=True))


# --- D133: the statement arm's date and its head ----------------------------------------------------------------------

def statement_act(line: str, kind_words: str, procedure=None, status='was performed', **changes) -> tuple:
    """(inventory, text) of the families review's office document with an act of kind 'other' filed under the visit."""
    return note(line, other(kind_words, status, procedure, **changes))


class D133TheStatementArm(SimpleTestCase):
    """D133: an act read by its statement is dated by the one currency rule, and named by its kind words' head."""

    def test_d133_problem_0_an_undatable_act_read_by_its_statement_asks_event_time(self):
        """The review's problem 0: 'During this visit, excision of a 1 cm sebaceous cyst on the upper back was
        performed.' (kind other, 'was performed', filed under the visit by 'Office visit', current_encounter 'During
        this visit' - no D54 frame, so unverified: UNDATABLE), its sibling 'during the office visit', and D130's own
        pin input with Gemini's time 'unknown'. 46e461e7f: READY (the arm dropped an undatable act: neither counted
        nor listed); c2e53f8e: held, separate_em. Now listed undatable: 99213 asks the act's event_time (held), as the
        author's mutant M3 showed."""
        cases = (
            ("'During this visit'", statement_act(
                'During this visit, excision of a 1 cm sebaceous cyst on the upper back was performed.',
                'excision of a 1 cm sebaceous cyst', VISIT_WORDS,
                time=a('current_encounter', 'During this visit', ['P2']))),
            ("'during the office visit'", statement_act(
                'Excision of a 1 cm sebaceous cyst on the upper back was performed during the office visit.', CYST_KIND,
                a('office_em', 'office visit', ['P2']),
                time=a('current_encounter', 'during the office visit', ['P2']))),
            ("D130's time 'unknown'", statement_act(
                'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office.', CYST_KIND,
                time=a('unknown'))),
        )
        for label, (inv, text) in cases:
            with self.subTest(label):
                self.assertEqual(day_of(inv), facts.UNDATABLE)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(undatable=('E1',)))
                p = em(inv, text)
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['event_time']))
                self.assertEqual(p.clarifications[0].question, TIME_QUESTION)

    def test_d133_at_todays_visit_is_on_the_date_by_d131(self):
        """Problem 0's "at today's visit" (current_encounter, no D54 frame): its "today's" holds 'today' at a word
        boundary (D131), so it is ON - a possible other GI service, 99213 held with separate_em, the question c2e53f8e
        asks - not the event_time the spec expected for it (recorded in DECISIONS D133)."""
        inv, text = statement_act("Excision of a 1 cm sebaceous cyst on the upper back was performed at today's visit.",
                                  CYST_KIND, a('office_em', "today's visit", ['P2']),
                                  time=a('current_encounter', "at today's visit", ['P2']))
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
        held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)

    def test_d133_the_history_mention_exception_stays(self):
        """Control: an act read by its statement that Gemini places at another encounter with no marker ('Indication:',
        earlier_encounter unverified: time_marker_missing, UNDATABLE) is a history mention and never counts (D109,
        D111); one worded 'History:' (its marker verifies it) and one verified 'in 2024' are OFF. Each is READY with
        no question, as at 46e461e7f. c2e53f8e is READY on the 'History:' and 'in 2024' texts and holds the
        'Indication:' one (its routing reads the excision line as performed): unchanged by D133, as the spec keeps the
        exception, and recorded in DECISIONS D133."""
        cases = (
            ("'Indication:'", statement_act(
                'Indication: excision of a 1 cm sebaceous cyst on the upper back was performed in the office.',
                'excision of a 1 cm sebaceous cyst', time=a('earlier_encounter', 'Indication:', ['P2'])),
             facts.UNDATABLE),
            ("'History:'", statement_act(
                'History: excision of a 1 cm sebaceous cyst on the upper back was performed in the office.',
                'excision of a 1 cm sebaceous cyst', time=a('earlier_encounter', 'History:', ['P2'])), facts.OFF),
            ("'in 2024'", statement_act('Excision of a 1 cm sebaceous cyst on the upper back was performed in 2024.',
                                        CYST_KIND, time=a('earlier_encounter', 'in 2024', ['P2'])), facts.OFF),
        )
        for label, (inv, text), day in cases:
            with self.subTest(label):
                self.assertEqual(day_of(inv), day)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                ready_with_no_procedure_day(self, em(inv, text))

    def test_d133_with_a_documented_statement_an_undatable_act_still_asks_event_time(self):
        """THE COST, recorded: problem 0's 'During this visit, excision ...' beside 'A significant, separately
        identifiable E/M service was provided.' (stated). 46e461e7f: READY, no question (the act dropped); c2e53f8e:
        READY with the modifier 25 consideration (it reads the excision as performed today). Now the undatable act is
        listed, and an undatable act asks the E/M's event_time with no procedure day whatever the statement: held -
        a hold where c2e53f8e is READY."""
        inv, text = stated_note('During this visit, excision of a 1 cm sebaceous cyst on the upper back was performed.',
                                other('excision of a 1 cm sebaceous cyst', 'was performed', VISIT_WORDS,
                                      time=a('current_encounter', 'During this visit', ['P2'])))
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(undatable=('E1',)))
        p = em(inv, text)
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['event_time']))

    def test_d133_problem_1_a_class_word_outside_the_kind_words_head_sets_nothing_apart(self):
        """The review's problem 1: 'Excision of a 2 cm lipoma on the upper back, seen on ultrasound, was performed in
        the office today.' (kind words 'Excision', target words '2 cm lipoma on the upper back, seen on ultrasound') and
        the spec's own cost in another shape, kind words 'Excision of the lipoma seen on CT'. 46e461e7f: READY (the
        target's 'ultrasound', the kind's 'CT', set the act apart); c2e53f8e: held, separate_em. Now possible other GI
        services, 99213 held with separate_em."""
        cases = (
            ('the target words', statement_act(
                'Excision of a 2 cm lipoma on the upper back, seen on ultrasound, was performed in the office today.',
                'Excision', target=tg('', 'other', '2 cm lipoma on the upper back, seen on ultrasound', ['P2']))),
            ('the kind words', statement_act('Excision of the lipoma seen on CT was performed in the office today.',
                                             'Excision of the lipoma seen on CT')),
        )
        for label, (inv, text) in cases:
            with self.subTest(label):
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
                p = em(inv, text)
                held_for_separate_em(self, p, OTHER_GI_LABEL)
                self.assertIn(f'{OTHER_GI_LABEL} is {POSSIBLY}', check(p, 'em.same_day_procedure').detail)

    def test_d133_an_imaging_guided_procedure_is_counted(self):
        """'Ultrasound-guided paracentesis was performed in the office today.' (D130's recorded cost, READY at
        46e461e7f), 'CT-guided drainage ...' and 'Excision under ultrasound guidance ...': a head holding 'guided',
        'guidance' or 'assisted' names a procedure done with imaging, or the head ends before the imaging ('under'),
        so each is a possible other GI service and 99213 is held with separate_em, as c2e53f8e holds each."""
        guided = ('Ultrasound-guided paracentesis', 'CT-guided drainage', 'Excision under ultrasound guidance')
        for kind_words in guided:
            with self.subTest(kind_words=kind_words):
                inv, text = statement_act(f'{kind_words} was performed in the office today.', kind_words)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
                held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)

    def test_d133_a_class_in_the_kind_words_head_still_never_counts(self):
        """Control, D130's pins in the spec's shapes: 'CT abdomen', 'An ECG', 'Labs', 'Abdominal ultrasound' filed
        under the visit as kind other, and an interpretation, an order and counseling, each named in its kind words'
        head - never counted: READY with no procedure day at 46e461e7f, at c2e53f8e and now."""
        cases = (('CT abdomen was performed in the office today.', 'CT abdomen', VISIT_WORDS, 'was performed'),
                 ('An ECG was performed in the office today.', 'An ECG', VISIT_WORDS, 'was performed'),
                 ('Labs were done in the office today.', 'Labs', None, 'were done'),
                 ('Abdominal ultrasound was performed in the office today.', 'Abdominal ultrasound', None,
                  'was performed'),
                 ('Interpretation of the outside CT images was performed today.',
                  'Interpretation of the outside CT images', VISIT_WORDS, 'was performed'),
                 ('An order for a colonoscopy was done today.', 'order for a colonoscopy', VISIT_WORDS, 'was done'),
                 ('Counseling on a high-fiber diet was done today.', 'Counseling on a high-fiber diet', VISIT_WORDS,
                  'was done'))
        for line, kind_words, procedure, status in cases:
            with self.subTest(kind_words=kind_words):
                inv, text = statement_act(line, kind_words, procedure, status)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                ready_with_no_procedure_day(self, em(inv, text))

    def stated(self, kind_words='Excision', target_words=''):
        line = f'{kind_words} was performed {target_words}.'
        target = tg('', 'other', target_words, ['P2']) if target_words else tg()
        item = other(kind_words, 'was performed', target=target)
        inv, _ = note(line, item)
        return combination._stated_procedure(reading_of(inv).events['E1'])

    def test_d133_the_head_reader(self):
        """combination._stated_procedure reads the kind words only (NAMING_WORDS), folded, cut at the first comma, colon
        or semicolon and before the first HEAD_ENDS word (its edge punctuation stripped), word-bounded; a head holding a
        GUIDED word is never set apart."""
        self.assertEqual(combination.NAMING_WORDS, ('kind',))
        self.assertEqual(combination.HEAD_MARKS, (',', ':', ';'))
        self.assertEqual(combination.HEAD_ENDS, ('of', 'on', 'in', 'at', 'for', 'with', 'under', 'by', 'from', 'to',
                                                 'after', 'before', 'during', 'seen', 'shown', 'noted', 'which',
                                                 'that', 'who', 'performed', 'done', 'was', 'were'))
        self.assertEqual(combination.GUIDED, ('guided', 'guidance', 'assisted'))
        set_apart = ('CT abdomen', 'An ECG', 'Labs', 'Abdominal ultrasound', 'CT: abdomen', 'Labs; drawn',
                     'Lab (seen on CT)', 'X-ray', 'MRI scan of the liver', 'Imaging', 'The stool test kit')
        for words in set_apart:
            with self.subTest(set_apart=words):
                self.assertFalse(self.stated(kind_words=words))
        counted = ('Excision', 'Excision of the lipoma seen on CT', 'Excision, CT', 'Excision; ultrasound',
                   'Excision: ECG', 'Excision (shown on ultrasound)', 'Excision which the CT showed',
                   'Excision (which CT showed)',
                   'Ultrasound-guided paracentesis', 'CT-assisted biopsy', 'Image guidance biopsy',
                   'Labial cyst excision', 'Protest lesion excision', 'Scanty lesion excision',
                   'Drainage under CT', 'Excision, ultrasound-guided')
        for words in counted:
            with self.subTest(counted=words):
                self.assertTrue(self.stated(kind_words=words))
        # the target words are never read: they say what the act was done to
        self.assertTrue(self.stated(target_words='2 cm lipoma, seen on ultrasound'))
        self.assertTrue(self.stated(target_words='CT'))


# --- D134: the visit item beside a procedure only possibly done -------------------------------------------------------

class D134VisitItemBesideAPossibleProcedure(SimpleTestCase):
    """D134: the office visit with no supported proposal is set apart only beside a procedure done on the date."""

    def test_d134_em2_problem_3_beside_an_act_only_possibly_done_the_visit_stays_listed(self):
        """The review's problem 3: 'Rectal examination: a digital rectal examination was performed and showed no
        masses.' and 'A complete physical examination was performed and was unremarkable.' (kind other, filed under the
        visit by 'Office visit'), and 'A stool guaiac was performed in the office today and was negative.' (by its
        'office'): D130's statement arm reads each as a POSSIBLE other GI service. With no E/M proposed, c2e53f8e (and
        1caaf0609) list the visit, 'has no supported proposal'; 46e461e7f set it apart (not_listed). Now listed, as
        c2e53f8e lists it. With 99213 proposed it stays held with separate_em - THE RECORDED COST (c2e53f8e: READY)."""
        cases = (('the digital rectal examination', 'Rectal examination: a digital rectal examination was performed '
                  'and showed no masses.', 'digital rectal examination', VISIT_WORDS),
                 ('the complete physical examination', 'A complete physical examination was performed and was '
                  'unremarkable.', 'complete physical examination', VISIT_WORDS),
                 ('the stool guaiac', 'A stool guaiac was performed in the office today and was negative.',
                  'stool guaiac', None))
        for label, line, kind_words, procedure in cases:
            with self.subTest(label):
                inv, text = statement_act(line, kind_words, procedure)
                found = procedure_day(inv)
                self.assertEqual((found.labels, found.possible), ((), (OTHER_GI_LABEL,)))
                self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
                held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)

    def test_d134_em_problem_1_the_ct_obtained_earlier_today(self):
        """The review of D111's problem 1: 'CT abdomen obtained earlier today showed a dilated common bile duct.'
        (not_gi, kind other, earlier_encounter 'earlier today', performer unknown) and its 'this morning' twin: a
        POSSIBLE service outside the GI profiles (D111). With no E/M proposed, c2e53f8e and d353e64df list the visit;
        1caaf0609 and 46e461e7f set it apart. Now listed. With 99213 proposed: held, separate_em - THE RECORDED COST
        (c2e53f8e READY)."""
        ruq = 'Office visit: established patient seen today for right upper quadrant pain.'
        for words in ('earlier today', 'this morning'):
            with self.subTest(words=words):
                e0 = act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                         procedure=a('office_em', 'Office visit', ['V1']))
                study = act('E1', 'P2', 'other', 'CT abdomen', status_words='obtained',
                            procedure=a('not_gi', 'CT abdomen', ['P2']), time=a('earlier_encounter', words, ['P2']),
                            performer=a('unknown'))
                lines = {'V1': ruq, 'V2': 'Total time on the date of the encounter: 30 minutes.',
                         'P2': f'CT abdomen obtained {words} showed a dilated common bile duct.',
                         'P3': 'Plan: MRCP; recheck in 4 weeks.'}
                inv, text = inventory(lines, events=[e0, study], visits=[
                    {'event': 'E0', 'basis': a('total_time', '30 minutes', ['V2']),
                     'separately_identifiable': a('not_stated')}])
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(NON_GI_LABEL,)))
                self.assertEqual(no_em(inv, text), ([NO_PROPOSAL], []))
                held_for_separate_em(self, em(inv, text, ruq), NON_GI_LABEL)

    def test_d134_a_second_review_can_add_the_visit_code_through_the_listed_item(self):
        """The effect em2 problem 3 names: beside the DRE the visit item is listed and marked for the second review, so
        a second review selecting 99213 adds it as a proposal (origin second_review), held with separate_em on the
        possible procedure day. c2e53f8e adds it too (READY: it reads no procedure there); 46e461e7f marked nothing
        and listed the code as an informational alternative."""
        inv, text = statement_act('Rectal examination: a digital rectal examination was performed and showed no '
                                  'masses.', 'digital rectal examination', VISIT_WORDS)
        first = run(inv, text, [], user_values=MEMBER)
        marked = [item for item in first.completeness['unresolved_items'] if item['second_review']]
        self.assertEqual([item['label'] for item in marked], [NO_PROPOSAL])
        result = run(inv, text, [], user_values=MEMBER, second=response(text, [('99213', VISIT)], provider='fable'),
                     second_scope={'items': [NO_PROPOSAL]})
        p = proposal(result, '99213')
        self.assertEqual((p.bucket, p.support['origin'], p.status, asked(p)),
                         ('selected', 'second_review', 'needs_clarification', ['separate_em']))

    def test_d134_beside_a_procedure_done_on_the_date_the_visit_is_still_set_apart(self):
        """Control: beside a procedure DONE on the date of service the visit is set apart as before (c2e53f8e and
        46e461e7f): the banding filed under the visit by its own words (done: ProcedureDay.labels); the EGD 'Earlier
        today' by 'I' (done by its labels alone - its time is earlier_encounter, so no session of the EGD is done); and
        D81's other_gi banding, a possible other GI service whose own session is done (another family's done
        session)."""
        band = 'Rubber band ligation of one internal hemorrhoid was performed in the office today.'
        hem = tg('', 'anal_canal', 'one internal hemorrhoid', ['P2'])
        cases = (
            ('the banding filed under the visit', office(band, act(
                'E1', 'P2', 'band_ligation', 'Rubber band ligation', status_words='was performed',
                procedure=OFFICE_WORD, target=hem)), (OTHER_GI_LABEL,), ()),
            ("the EGD 'Earlier today' by I", office(
                'Earlier today I performed an upper endoscopy, which showed a clean-based duodenal ulcer.',
                act('E1', 'P2', 'examination', 'upper endoscopy', status_words='I performed',
                    procedure=a('egd', 'upper endoscopy', ['P2']), time=a('earlier_encounter', 'Earlier today', ['P2']),
                    performer=a('documenting_team', 'I', ['P2']))), (EGD_LABEL,), ()),
            ("D81's other_gi banding", office(band, act(
                'E1', 'P2', 'band_ligation', 'Rubber band ligation', status_words='was performed',
                procedure=a('other_gi'), target=hem)), (), (OTHER_GI_LABEL,)),
        )
        for label, (inv, text), done, possible in cases:
            with self.subTest(label):
                found = procedure_day(inv)
                self.assertEqual((found.labels, found.possible), (done, possible))
                self.assertEqual(no_em(inv, text), ([], [NOT_LISTED]))
        self.assertNotIn('gi.egd', [family for family, session in coverage.sessions(reading_of(cases[1][1][0])).items()
                                    if session.done])

    def test_d134_the_read_time_overlay_keeps_the_assessments_reading(self):
        """overlay.reviewed_completeness re-reads the coverage from the items the assessment listed: beside the DRE the
        visit stays listed, beside the done banding it stays set apart - the reading the assessment made."""
        dre = statement_act('Rectal examination: a digital rectal examination was performed and showed no masses.',
                            'digital rectal examination', VISIT_WORDS)
        band = office('Rubber band ligation of one internal hemorrhoid was performed in the office today.', act(
            'E1', 'P2', 'band_ligation', 'Rubber band ligation', status_words='was performed', procedure=OFFICE_WORD,
            target=tg('', 'anal_canal', 'one internal hemorrhoid', ['P2'])))
        for label, (inv, text), expected in (('the DRE', dre, ([NO_PROPOSAL], [])),
                                             ('the done banding', band, ([], [NOT_LISTED]))):
            with self.subTest(label):
                result = run(inv, text, [], user_values=MEMBER)
                reviewed = overlay.reviewed_completeness(result.completeness, reading_of(inv), [], ())
                self.assertEqual(([str(item['label']) for item in reviewed['unresolved_items']],
                                  [str(item['label']) for item in reviewed['not_listed']]), expected)


# --- the D130 record: a documented statement beside a possible procedure ----------------------------------------------


class D130RecordDocumentedStatement(SimpleTestCase):
    """The D130 record (em2 problem 2): a possible label can make a held E/M READY, through a documented statement."""

    def test_d130_record_a_possible_procedure_with_a_documented_statement_releases_the_e_m(self):
        """The review's problem 2: the visit lines, then 'A significant, separately identifiable E/M service was
        provided.' (stated), note (a)'s excision filed under the visit, then a banding filed under the visit whose time
        Gemini leaves 'unknown' (or current_encounter 'During this visit'), then the plan. 1caaf0609: 99213 held,
        event_time ('Was the band ligation ...'); c2e53f8e: READY. Now READY with the modifier 25 consideration: the
        excision is a possible procedure, so the procedure day's documented statement releases the E/M and the
        banding's event_time is never asked (assess: separate_em only with no statement; event_time only with no
        procedure day). D130's 'it can make nothing READY that was held' is false here; the READY equals
        c2e53f8e's. Without the excision 99213 still asks the banding's event_time."""
        band_lines = {'unknown': 'Rubber band ligation of one internal hemorrhoid was performed.',
                      'During this visit': 'During this visit, rubber band ligation of one internal hemorrhoid was '
                                           'performed.'}
        for words, band_line in band_lines.items():
            band = act('E2', 'P4', 'band_ligation', 'Rubber band ligation' if words == 'unknown'
                       else 'rubber band ligation', status_words='was performed', procedure=VISIT_WORDS,
                       time=a('unknown') if words == 'unknown' else a('current_encounter', words, ['P4']),
                       target=tg('', 'anal_canal', 'one internal hemorrhoid', ['P4']))
            separate = {**visit_facts(), 'separately_identifiable': a('stated', SEPARATE, ['P5'])}
            for label, line, item in (('with the excision', EXCISION_TODAY, other(CYST_KIND, 'was performed')),
                                      ('without it', 'Plan reviewed.', act('E1', 'P2', 'other', 'Plan reviewed',
                                                                           status_words='reviewed',
                                                                           procedure=VISIT_WORDS))):
                with self.subTest(banding=words, case=label):
                    lines = {'V1': VISIT, 'V2': TIME, 'P5': SEPARATE_LINE, 'P2': line, 'P4': band_line, 'P3': PLAN}
                    inv, text = inventory(lines, events=[visit(), item, band], visits=[separate])
                    found = procedure_day(inv)
                    self.assertEqual(found.undatable, ('E2',))
                    p = em(inv, text)
                    if label == 'with the excision':
                        self.assertEqual(found.possible, (OTHER_GI_LABEL,))
                        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
                        self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
                        self.assertIn('The documentation states', check(p, 'em.same_day_procedure').detail)
                    else:
                        self.assertEqual(found.possible + found.labels, ())
                        self.assertEqual(asked(p), ['event_time'])
