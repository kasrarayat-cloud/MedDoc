"""DECISIONS D111, D112 and D113 (the reviews of D109 and the family parity audit of d353e64df), SYNTHETIC: the same-day
E/M rule reads every act's date by one currency rule, places only today-anchored frames on the date, and takes the
separately identifiable statement from today's visit only.

- D111 (the review of D109, problems 0, 1 and 2): D109 counted an act of gi.unsupported or of no family only when
  Gemini gave its time as current_encounter, and its kind arm never reached such an act. So an office excision or
  banding whose own words place it on the date ("Earlier today", "Earlier in the day") with an earlier_encounter time,
  and one whose time Gemini left 'unknown', made no procedure day and asked nothing: 99213 READY, where c2e53f8e and
  437b708bb hold it. Every act the rule reads now has its date read by facts.day_of: ON counts, done or possible; an
  undatable time ('unknown', a current time that does not verify) is listed, so the E/M asks event_time; OFF never
  counts. An act outside the procedure families and gi.other that Gemini places at another encounter with no marker
  (finding 16's history mention) and one whose performer is verified to another clinician or facility (finding 15's
  radiology read) still never count, so both stay READY.
- D112 (the review of D109, problem 3): the anaphoric frames ("Earlier that day", "Later that morning") name whatever
  day the sentence before them names, so they are no same-date frames: the melena note's outside EGD "Earlier that
  day" (after "On 10/30/2026 she was seen in the emergency department of another hospital") is OFF the date again, and
  99213 is READY with the visit item unresolved, as at 437b708bb.
- D113 (the parity audit of the modifiers review, gap 0): the separately identifiable statement is today's visit's
  only - the code's own visit events, then a visit event of this encounter (a usable current_encounter time, no
  performer verified to another clinician or facility) - and a denial, or a statement whose own words are negated,
  releases nothing.

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). The installed release's outputs (c2e53f8e, engine.assess as tests/test_harness_engine.py
drives it) quoted in the docstrings were measured on byte-identical texts. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, events, facts, lexicon
from studio.validation import checks
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_families import MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r4_em_same_day import (CBD_VISIT, INDICATION, OTHER_GI_LABEL, RUQ_VISIT, SURVEILLANCE,
                                                      THAT_DAY_LINE, earlier_act, held_for_separate_em, history_study,
                                                      interpreted, ready_with_no_procedure_day)

DAY = '2026-11-09'
NON_GI_LABEL = 'Service outside the GI profiles'  # profiles.PROFILES['gi.unsupported'].label
HEMORRHOID = tg('', 'anal_canal', 'one internal hemorrhoid', ['P2'])
BAND = 'rubber band ligation of one internal hemorrhoid was performed in the office'
CYST = 'excision of a 1 cm sebaceous cyst on the upper back was performed in the office'


def em(inv, text, visit_line=VISIT, user_values=MEMBER, codes=()):
    return proposal(run(inv, text, [('99213', visit_line), *codes], user_values=user_values), '99213')


def reading_of(inv):
    return events.Reading.of(inv)


def procedure_day(inv):
    return combination.procedure_day(reading_of(inv), DAY)


def office(line: str, act_: dict, **lines) -> tuple:
    """(inventory, text) of D81's office note - the visit (E0, V1) and its total time (V2), the act line P2 (E1) and
    the plan (P3) - with ``lines`` added."""
    return inventory({'V1': VISIT, 'V2': TIME, **lines, 'P2': line, 'P3': PLAN}, events=[visit(), act_],
                     visits=[visit_facts()])


def procedure(value: str, words: str) -> dict:
    """Gemini's procedure attribute: 'unknown' carries no words; any other value its words in P2."""
    return a('unknown') if value == 'unknown' else a(value, words, ['P2'])


def banding(value: str, time: dict) -> dict:
    """The office band ligation (E1, P2), performed by the documenting team, its procedure ``value``."""
    return act('E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='was performed',
               procedure=procedure(value, 'office' if value == 'office_em' else 'rubber band ligation'), time=time,
               target=HEMORRHOID)


def excision(value: str, time: dict, words: str = 'excision of a 1 cm sebaceous cyst') -> dict:
    """D94's office excision (E1, P2): kind other, performed by the documenting team, its procedure ``value``."""
    return act('E1', 'P2', 'other', words, status_words='was performed', procedure=procedure(value, words), time=time)


def label_of(kind: str, value: str) -> str:
    """The same-day label: an act of a procedural kind is another GI service (D109, D111), an act of kind 'other' its
    family's (D94)."""
    if kind == 'band_ligation':
        return OTHER_GI_LABEL
    return NON_GI_LABEL if value == 'not_gi' else combination.UNIDENTIFIED_PROCEDURE


# --- D111: one currency rule ------------------------------------------------------------------------------------------

class D111OneCurrencyRule(SimpleTestCase):
    """D111: every act the same-day rule reads has its date read by facts.day_of - never by Gemini's time value
    alone."""

    def test_d111_problem_0_an_act_its_own_words_place_on_the_date_makes_a_procedure_day(self):
        """The review's problem 0: D81's office lines with 'Earlier today, excision of a 1 cm sebaceous cyst on the
        upper back was performed in the office.' (kind other) or 'Earlier today, rubber band ligation of one internal
        hemorrhoid was performed in the office.', Gemini's time earlier_encounter worded 'Earlier today' (verified by
        its 'earlier'; its own words place it ON the date), procedure not_gi or 'unknown'. d353e64df: READY, 'No
        same-day procedure is documented'; c2e53f8e and 437b708bb: held, separate_em. Now held, separate_em, naming the
        act's label; with no member values separate_em beside setting and patient_status."""
        for kind, rest, make in (('other', CYST, excision), ('band_ligation', BAND, banding)):
            for value in ('not_gi', 'unknown'):
                with self.subTest(kind=kind, procedure=value):
                    inv, text = office(f'Earlier today, {rest}.', make(value, a('earlier_encounter', 'Earlier today',
                                                                                ['P2'])))
                    stored = reading_of(inv).events['E1']
                    self.assertEqual((stored['family'], stored['time']['value'], stored['time']['state']),
                                     ('gi.unsupported' if value == 'not_gi' else '', 'earlier_encounter', 'verified'))
                    self.assertEqual(facts.day_of(stored, DAY), facts.ON)
                    found = procedure_day(inv)
                    self.assertIn(label_of(kind, value), found.labels + found.possible)
                    held_for_separate_em(self, em(inv, text), label_of(kind, value))
                    self.assertEqual(sorted(asked(em(inv, text, user_values=None))),
                                     ['patient_status', 'separate_em', 'setting'])

    def test_d111_problem_2_earlier_in_the_day_whatever_the_procedure(self):
        """The review's problem 2: the kind arm never reached an act of no family, so 'Earlier in the day, rubber band
        ligation of one internal hemorrhoid was performed in the office.' with procedure 'unknown' and earlier_encounter
        'Earlier in the day' (ON by D109's frames) was READY at d353e64df (and at 437b708bb, before the frames);
        c2e53f8e holds it with separate_em ('Other GI service is documented as performed on the same date'). The same
        for procedure not_gi and for the excision. Each now asks separate_em; the banding of no family is a POSSIBLE
        other GI service (its procedure is unusable), the not_gi banding a done one."""
        expected = {('band_ligation', 'unknown'): 'possible', ('band_ligation', 'not_gi'): 'labels',
                    ('other', 'unknown'): 'possible', ('other', 'not_gi'): 'labels'}
        for kind, rest, make in (('band_ligation', BAND, banding), ('other', CYST, excision)):
            for value in ('unknown', 'not_gi'):
                with self.subTest(kind=kind, procedure=value):
                    inv, text = office(f'Earlier in the day, {rest}.',
                                       make(value, a('earlier_encounter', 'Earlier in the day', ['P2'])))
                    self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), facts.ON)
                    self.assertEqual(getattr(procedure_day(inv), expected[(kind, value)]), (label_of(kind, value),))
                    held_for_separate_em(self, em(inv, text), label_of(kind, value))

    def test_d111_problem_1_an_unknown_time_asks_event_time(self):
        """The review's problem 1 (and the D109 residual): 'Excision of a 1 cm sebaceous cyst on the upper back was
        performed in the office.' (not_gi or 'unknown') or 'Rubber band ligation of one internal hemorrhoid was
        performed in the office.' ('unknown', not_gi, or office_em - filed under the visit) with Gemini's time
        'unknown': d353e64df READY with no question; c2e53f8e held (separate_em); 437b708bb event_time, but READY for
        the banding filed under the visit. An undatable act is UNRESOLVED(time) (C-3): 99213 asks the act's
        event_time, never READY."""
        acts = (
            ('the excision, not_gi', CYST,
             lambda: excision('not_gi', a('unknown'), 'Excision of a 1 cm sebaceous cyst'),
             'Was the act (“was performed”) done at this encounter?'),
            ("the excision, procedure 'unknown'", CYST,
             lambda: excision('unknown', a('unknown'), 'Excision of a 1 cm sebaceous cyst'),
             'Was the act (“was performed”) done at this encounter?'),
            ("the banding, procedure 'unknown'", BAND, lambda: banding('unknown', a('unknown')),
             'Was the band ligation (“was performed”) done at this encounter?'),
            ('the banding, not_gi', BAND, lambda: banding('not_gi', a('unknown')),
             'Was the band ligation (“was performed”) done at this encounter?'),
            ('the banding filed under the visit', BAND, lambda: banding('office_em', a('unknown')),
             'Was the band ligation (“was performed”) done at this encounter?'),
        )
        for label, rest, make, question in acts:
            with self.subTest(label):
                inv, text = office(rest[0].upper() + rest[1:] + '.', make())
                stored = reading_of(inv).events['E1']
                self.assertEqual((stored['time']['value'], facts.day_of(stored, DAY)), ('unknown', facts.UNDATABLE))
                self.assertEqual(procedure_day(inv), combination.ProcedureDay(undatable=('E1',)))
                p = em(inv, text)
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['event_time']))
                self.assertEqual(p.clarifications[0].question, question)
                self.assertIn('A procedure done on the date of service would need a significant, separately '
                              'identifiable visit beside it.', p.clarifications[0].reason)

    def test_d111_the_kind_arm_reads_an_unidentified_or_non_gi_act_too(self):
        """The kind arm applies to an act of no family or of gi.unsupported: a band ligation 'today' whose procedure
        Gemini left 'unknown' is a possible OTHER GI service (d353e64df: 'A procedure CPT Studio could not identify');
        a not_gi skin biopsy today is a done one, as c2e53f8e words it ('Other GI service is documented as performed').
        An act of kind 'other' keeps its family's label (D94's pinned excision)."""
        biopsy = act('E1', 'P2', 'biopsy', 'Skin biopsy', status_words='was performed',
                     procedure=a('not_gi', 'Skin biopsy', ['P2']), time=a('current_encounter', 'today', ['P2']))
        cases = (
            ("a banding of no family, 'today'", f'{BAND[0].upper()}{BAND[1:]} today.',
             banding('unknown', a('current_encounter', 'today', ['P2'])), ((), (OTHER_GI_LABEL,))),
            ('a not_gi skin biopsy today', 'Skin biopsy of the left forearm was performed in the office today.', biopsy,
             ((OTHER_GI_LABEL,), ())),
            ("D94's excision, kind 'other', today", f'{CYST[0].upper()}{CYST[1:]} today.',
             excision('not_gi', a('current_encounter', 'today', ['P2'])), ((NON_GI_LABEL,), ())),
        )
        for label, line, item, (done, possible) in cases:
            with self.subTest(label):
                inv, text = office(line, item)
                found = procedure_day(inv)
                self.assertEqual((found.labels, found.possible), (done, possible))
                held_for_separate_em(self, em(inv, text), (done + possible)[0])

    def test_d111_findings_15_and_16_stay_ready(self):
        """What the one rule must NOT move: finding 15's CT read by the radiology service (performer verified to
        another clinician: never counted, whatever its date) and finding 16's history mentions (an earlier time with no
        marker, UNDATABLE, of an act outside the procedure families: never counted) - the 'unknown' polypectomy,
        which the kind arm now reads, included - and an excision verified 'in 2024' (OFF). Each is READY with no
        question, as at d353e64df and c2e53f8e."""
        readings = (
            ('finding 15: the CT, current', interpreted(), RUQ_VISIT),
            ("finding 15: the CT, procedure 'unknown'", interpreted(procedure=a('unknown')), RUQ_VISIT),
            ("finding 15: a CT 'earlier today', ON the date, read by the radiology service", interpreted(
                'CT abdomen obtained earlier today was read by the radiology service.', 'CT abdomen',
                kind_words='CT abdomen', status_words='obtained',
                time=a('earlier_encounter', 'earlier today', ['P2'])), RUQ_VISIT),
            ("finding 16: fb14 r2, 'Indication:'", history_study(INDICATION), CBD_VISIT),
            ('finding 16: fb14 r3, an examination', history_study(INDICATION, kind='examination'), CBD_VISIT),
            ("finding 16: the polypectomy, procedure 'unknown'", history_study(
                SURVEILLANCE, kind='removal', kind_words='polypectomy', procedure=a('unknown'),
                status_words='polypectomy'), CBD_VISIT),
            ("an excision verified 'in 2024'", office(
                'Excision of a 1 cm sebaceous cyst on the upper back was performed in 2024.',
                excision('not_gi', a('earlier_encounter', 'in 2024', ['P2']))), VISIT),
        )
        for label, (inv, text), visit_line in readings:
            with self.subTest(label):
                if label.startswith('finding 15: a CT'):
                    self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), facts.ON)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                ready_with_no_procedure_day(self, em(inv, text, visit_line))

    def test_d111_an_act_of_a_procedure_family_keeps_c3s_question(self):
        """Control: an act of a procedure family or gi.other whose earlier time has no marker is UNDATABLE and asks
        the E/M's event_time (C-3, D81: a hold, never a READY), as at d353e64df - the history-mention exception is the
        other arms' only."""
        line = 'Indication: rectal bleeding after rubber band ligation of an internal hemorrhoid.'
        item = act('E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='rubber band ligation',
                   procedure=a('other_gi'), time=a('earlier_encounter', 'Indication:', ['P2']))
        inv, text = office(line, item)
        self.assertEqual(reading_of(inv).events['E1']['family'], 'gi.other')
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(undatable=('E1',)))
        self.assertEqual(asked(em(inv, text)), ['event_time'])


# --- D112: only today-anchored frames ---------------------------------------------------------------------------------

MELENA_VISIT = 'Office visit: established patient seen today for follow-up of melena.'
ED_LINE = 'On 10/30/2026 she was seen in the emergency department of another hospital for melena.'
OUTSIDE_EGD = ('{words} she had undergone an upper endoscopy at that hospital, which showed a clean-based duodenal '
               'ulcer.')
NO_PROPOSAL = 'office / outpatient visit (documented as performed) has no supported proposal'


def melena(words: str = 'Earlier that day') -> tuple:
    """(inventory, text) of the review's problem 3: the melena follow-up visit, the ED visit on 10/30/2026 (P1) and the
    outside EGD (E1, P2) Gemini gives earlier_encounter worded ``words``, performer other_facility 'at that
    hospital'."""
    egd = act('E1', 'P2', 'examination', 'upper endoscopy', status_words='had undergone',
              procedure=a('egd', 'upper endoscopy', ['P2']), time=a('earlier_encounter', words, ['P2']),
              performer=a('other_facility', 'at that hospital', ['P2']))
    return inventory({'V1': MELENA_VISIT, 'V2': TIME, 'P1': ED_LINE, 'P2': OUTSIDE_EGD.format(words=words), 'P3': PLAN},
                     events=[act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                                 procedure=a('office_em', 'Office visit', ['V1'])), egd], visits=[visit_facts()])


class D112TodayAnchoredFrames(SimpleTestCase):
    """D112: the same-date frames are anchored to today; the anaphoric ones are removed."""

    def test_d112_problem_3_the_outside_egd_earlier_that_day_is_off_the_date(self):
        """The review's problem 3: d353e64df read 'Earlier that day' as a same-date frame, so the outside EGD of
        10/30/2026 made a procedure day - 99213 asked separate_em ('Upper GI endoscopy ... is documented as performed on
        the same date') and, with no E/M proposed, the visit's unresolved item was dropped. c2e53f8e and 437b708bb:
        99213 READY and the visit item listed. Now OFF the date (verified by its 'earlier'): READY, the item
        listed."""
        inv, text = melena()
        stored = reading_of(inv).events['E1']
        self.assertEqual((stored['time']['state'], facts.day_of(stored, DAY)), ('verified', facts.OFF))
        self.assertEqual(procedure_day(inv), combination.ProcedureDay())
        ready_with_no_procedure_day(self, em(inv, text, MELENA_VISIT))
        result = run(inv, text, [], user_values=MEMBER)
        self.assertIn(NO_PROPOSAL, [str(item.get('label')) for item in result.completeness['unresolved_items']])

    def test_d112_the_anaphoric_frames_are_no_frames(self):
        """SAME_DAY_FRAMES holds no frame anchored to 'that' (the day the sentence before names), and still holds the
        today-anchored ones; an outside EGD worded by an anaphoric frame is read by its own value and marker: OFF
        with an 'earlier' (READY), UNDATABLE with none ('Later that morning': C-3's event_time, as at 437b708bb)."""
        anaphoric = ('earlier that day', 'later that day', 'earlier that same day', 'later that same day',
                     'earlier that morning', 'earlier that afternoon', 'earlier that evening', 'later that morning',
                     'later that afternoon', 'later that evening', 'that same day', 'that day', 'that morning')
        for frame in anaphoric:
            self.assertNotIn(frame, lexicon.SAME_DAY_FRAMES)
            self.assertNotIn(frame, facts._SAME_DAY_FRAMES)
        for frame in ('earlier today', 'later today', 'this morning', 'this afternoon', 'this evening',
                      'earlier in the day', 'later in the day', 'earlier in the morning', 'on the date of service'):
            self.assertIn(frame, lexicon.SAME_DAY_FRAMES)
        cases = (('Earlier that day', facts.OFF, []), ('Earlier that afternoon', facts.OFF, []),
                 ('Later that morning', facts.UNDATABLE, ['event_time']),
                 ('Later that afternoon', facts.UNDATABLE, ['event_time']))
        for words, day, question in cases:
            with self.subTest(words=words):
                inv, text = melena(words)
                self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), day)
                p = em(inv, text, MELENA_VISIT)
                self.assertEqual((p.status, asked(p)), ('needs_clarification' if question else 'ready', question))

    def test_d112_finding_14s_g2_earlier_that_day_is_read_by_its_marker(self):
        """Finding 14's G2 ('Earlier that day, I performed a flexible sigmoidoscopy, which showed internal
        hemorrhoids.', earlier_encounter, by 'I'): D109 placed it ON the date; D112 reads it by its own marker, OFF, so
        99213 is READY. THE SPEC'S COST, recorded: c2e53f8e holds 99213 there with separate_em (an anaphoric frame with
        no other day named reads as the visit's own day to the installed routing)."""
        inv, text = earlier_act(THAT_DAY_LINE, 'examination', 'flexible sigmoidoscopy',
                                a('flex_sig', 'flexible sigmoidoscopy', ['P1']), 'Earlier that day')
        self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), facts.OFF)
        ready_with_no_procedure_day(self, em(inv, text))

    def test_d112_controls_today_anchored_frames_stay_on(self):
        """What D112 must NOT move: today-anchored frames place an earlier_encounter act on the date - 'earlier in the
        day', 'Earlier in the morning' (finding 14's B4-B6), 'later in the day', 'earlier this afternoon' - and
        SAME_DAY_WORDS' 'the same day' is read anywhere, as before."""
        for words in ('earlier in the day', 'Earlier in the morning', 'later in the day', 'earlier this afternoon',
                      'earlier the same day'):
            with self.subTest(words=words):
                inv, text = earlier_act(f'I performed an upper endoscopy {words}, which showed a clean-based duodenal '
                                        'ulcer.', 'examination', 'upper endoscopy', a('egd', 'upper endoscopy', ['P1']),
                                        words)
                self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), facts.ON)
                self.assertEqual(asked(em(inv, text)), ['separate_em'])


# --- D113: the separately identifiable statement is today's visit's ---------------------------------------------------

GASTRIC = {'V1': 'Office visit: established patient seen today for dyspepsia.', 'V2': TIME,
           'G1': 'EGD: the gastroscope was advanced to the second portion of the duodenum.',
           'G2': 'EGD: cold forceps biopsies were taken from the gastric antrum.'}
EARLIER_VISIT = 'At her office visit on 10/01/2026, a significant, separately identifiable E/M service was provided.'
STATEMENT = 'a significant, separately identifiable E/M service was provided'
DENIAL = 'The E/M service today was not separately identifiable from the procedure.'
TODAY_STATEMENT = "At today's office visit, a significant, separately identifiable E/M service was provided."
ADDENDUM = 'Addendum: a significant, separately identifiable E/M service was provided today.'
BY_PARK = 'Addendum by Dr. Lena Park: a significant, separately identifiable E/M service was provided today.'


def dyspepsia(own=None, *others, named=False, **lines) -> tuple:
    """(inventory, text) of the parity audit's gap-0 document: today's visit E0 (V1, its total time V2, its
    separately_identifiable ``own``), the EGD to the second portion of the duodenum (E1) and its antrum biopsy (E2),
    plus ``others``: (visit event, its separately_identifiable)."""
    acts = [act('E0', 'V1', 'em_visit', 'Office visit', status_words='seen today',
                procedure=a('office_em', 'Office visit', ['V1'])),
            exam('E1', 'G1', words='gastroscope', procedure=a('egd', 'EGD', ['G1'])),
            act('E2', 'G2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['G2']),
                technique=a('cold_forceps', 'cold forceps', ['G2']),
                target=tg('', 'gastric_antrum', 'gastric antrum', ['G2']))]
    visits = [{'event': 'E0', 'basis': a('total_time', '25 minutes', ['V2']),
               'separately_identifiable': own or a('not_stated')}]
    for event, separate in others:
        acts.append(event)
        visits.append({'event': event['id'], 'basis': a('not_stated'), 'separately_identifiable': separate})
    return inventory({**GASTRIC, **lines}, events=acts, visits=visits, named=named,
                     reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')])


def earlier_visit() -> tuple:
    """Gap 0's E3: the office visit of 10/01/2026 (earlier_encounter, its date literal verifies), stated separately
    identifiable."""
    return (act('E3', 'H1', 'em_visit', 'office visit', status_words='was provided',
                procedure=a('office_em', 'office visit', ['H1']), time=a('earlier_encounter', 'on 10/01/2026', ['H1'])),
            a('stated', STATEMENT, ['H1']))


def addendum(passage: str = 'A1', **changes) -> dict:
    return act('E4', passage, 'em_visit', 'Addendum', status_words='was provided today',
               procedure=a('office_em', 'Addendum', [passage]), **changes)


def gastric_em(inv, text, user_values=MEMBER):
    return em(inv, text, GASTRIC['V1'], user_values, codes=[('43239', GASTRIC['G2'])])


class D113TodaysVisitStatement(SimpleTestCase):
    """D113: separate_statement reads today's visit only, and a denial releases nothing."""

    def assert_held(self, inv, text):
        p = gastric_em(inv, text)
        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['separate_em']))
        same_day = check(p, 'em.same_day_procedure')
        self.assertIn('a significant, separately identifiable E/M service is not established', same_day.detail)
        self.assertNotIn('The documentation states', same_day.detail)
        self.assertIsNone(combination.separate_statement(reading_of(inv), ('E0',)))
        return p

    def test_d113_gap_0_another_encounters_statement_never_releases(self):
        """Gap 0's input (C1): 'At her office visit on 10/01/2026, a significant, separately identifiable E/M service
        was provided.' (E3, earlier_encounter, stated) beside today's EGD and biopsy, today's visit E0 not_stated; Corti
        proposes 99213 and 43239. d353e64df: 99213 READY, em.same_day_procedure quoting the 10/01/2026 visit as this
        one's; c2e53f8e: held, separate_em. Now held, separate_em; with no member values separate_em beside setting
        and patient_status (d353e64df: the first two only)."""
        inv, text = dyspepsia(None, earlier_visit(), H1=EARLIER_VISIT)
        self.assert_held(inv, text)
        self.assertEqual(sorted(asked(gastric_em(inv, text, user_values=None))),
                         ['patient_status', 'separate_em', 'setting'])

    def test_d113_gap_0_todays_denial_beside_another_encounters_statement(self):
        """Gap 0's variant C6: today's visit DENIES it ('The E/M service today was not separately identifiable from the
        procedure.', verified by its negator) and the 10/01/2026 visit states it. d353e64df: READY; c2e53f8e: held.
        Now held, separate_em."""
        inv, text = dyspepsia(a('denied', 'was not separately identifiable', ['D1']), earlier_visit(),
                              H1=EARLIER_VISIT, D1=DENIAL)
        self.assertTrue(events.usable(reading_of(inv).events['E0']['visit'], 'separately_identifiable'))
        self.assert_held(inv, text)

    def test_d113_a_statement_whose_own_words_are_negated_never_releases(self):
        """A 'stated' value whose own words are negated ('not separately identifiable', an answer off the contract:
        the words verify as words, and 'stated' needs no marker) is no statement. d353e64df: READY; c2e53f8e: held."""
        inv, text = dyspepsia(a('stated', 'not separately identifiable', ['D1']), D1=DENIAL)
        self.assertEqual(reading_of(inv).events['E0']['visit']['separately_identifiable']['state'], 'verified')
        self.assert_held(inv, text)

    def test_d113_fb10_a_denial_never_silences_another_of_todays_statements(self):
        """What D113 must NOT move. FRESH-2 B/fb10's attested shape (r1-r3): two visit events today - the GERD visit
        E1, 'The GERD evaluation and management is a significant, separately identifiable E/M service.' (stated), and
        the rectal bleeding assessment E2, 'The rectal bleeding assessment is part of the procedure and is not a
        separate E/M service.' (denied) - beside the flexible sigmoidoscopy; the registry expects 99214 READY. The
        E/M code's events are both visits, and E2's denial is about another service: the GERD statement still
        releases, as at d353e64df (a denial that silenced it added separate_em to 99204 and 99214 in all three runs).
        The same on the gap-0 document: E0 states it and an addendum of today denies it, or E0 denies it and the
        addendum states it - READY as at d353e64df (c2e53f8e holds the first: a recorded residual)."""
        lines = {'V1': 'Seen today in the office for two problems: worsening heartburn and new rectal bleeding.',
                 'S1': 'The GERD evaluation and management is a significant, separately identifiable E/M service.',
                 'B1': 'GERD E/M: moderate medical decision making; 32 minutes spent on GERD care alone.',
                 'S2': 'The rectal bleeding assessment is part of the procedure and is not a separate E/M service.',
                 'F1': 'Procedure: After two enemas, the flexible sigmoidoscope was advanced to 50 cm.'}
        gerd = act('E1', 'S1', 'em_visit', 'GERD evaluation and management',
                   status_words='GERD evaluation and management', procedure=a('office_em'))
        bleeding = act('E2', 'S2', 'em_visit', 'rectal bleeding assessment', status_words='rectal bleeding assessment',
                       procedure=a('office_em'))
        sigmoidoscopy = exam('E3', 'F1', words='flexible sigmoidoscope',
                             procedure=a('flex_sig', 'flexible sigmoidoscope', ['F1']))
        visits = [{'event': 'E1', 'basis': a('medical_decision_making', 'moderate medical decision making', ['B1']),
                   'separately_identifiable': a('stated', 'significant, separately identifiable E/M service', ['S1'])},
                  {'event': 'E2', 'basis': a('not_stated'),
                   'separately_identifiable': a('denied', 'is part of the procedure and is not a separate E/M service',
                                                ['S2'])}]
        inv, text = inventory(lines, events=[gerd, bleeding, sigmoidoscopy], visits=visits)
        reading = reading_of(inv)
        for own in (('E1', 'E2'), ('E2', 'E1'), ('E2',)):  # the E/M code's events are both visits, in either order
            self.assertEqual(combination.separate_statement(reading, own),
                             'significant, separately identifiable E/M service')
        p = proposal(run(inv, text, [('99214', lines['S1']), ('45330', lines['F1'])], user_values=MEMBER), '99214')
        self.assertNotIn('separate_em', asked(p))
        self.assertIn('The documentation states a significant, separately identifiable E/M service',
                      check(p, 'em.same_day_procedure').detail)
        contradicted = (
            ('E0 states it, the addendum denies it', dyspepsia(
                a('stated', STATEMENT, ['H2']), (addendum(), a('denied', 'was not separately identifiable', ['A1'])),
                H2=TODAY_STATEMENT, A1='Addendum: the E/M service today was not separately identifiable.')),
            ('E0 denies it, the addendum states it', dyspepsia(
                a('denied', 'was not separately identifiable', ['D1']), (addendum(), a('stated', STATEMENT, ['A1'])),
                D1=DENIAL, A1=ADDENDUM)),
        )
        for label, (inv, text) in contradicted:
            with self.subTest(label):
                self.assertEqual(combination.separate_statement(reading_of(inv), ('E0',)), STATEMENT)
                p = gastric_em(inv, text)
                self.assertEqual((p.status, asked(p)), ('ready', []))

    def test_d113_a_visit_by_another_clinician_or_of_an_unverified_time_never_releases(self):
        """Today's other visit events are read only with a usable current time and no performer verified to another
        clinician or facility: an addendum by Dr. Lena Park, verified other (the documenting endoscopist is named:
        c2e53f8e and d353e64df READY), or an addendum whose current time is unverified ('previously': D35's marker) -
        each stated - releases nothing, and 99213 asks separate_em."""
        other = addendum(performer=a('other_clinician', 'Dr. Lena Park', ['A1']))
        unverified = addendum(time=a('current_encounter', 'previously', ['A1']))
        readings = (
            ('by another clinician, verified', dyspepsia(None, (other, a('stated', STATEMENT, ['A1'])), named=True,
                                                         A1=BY_PARK), 'E4', 'performer'),
            ('its current time unverified', dyspepsia(None, (unverified, a('stated', STATEMENT, ['A1'])),
                                                      A1='Addendum: a significant, separately identifiable E/M service '
                                                         'was provided previously.'), 'E4', 'time'),
        )
        for label, (inv, text), eid, name in readings:
            with self.subTest(label):
                stored = reading_of(inv).events[eid]
                if name == 'performer':
                    self.assertTrue(events.verified_other_performer(stored))
                else:
                    self.assertFalse(events.usable(stored, 'time'))
                self.assertEqual(stored['visit']['separately_identifiable']['state'], 'verified')
                self.assert_held(inv, text)

    def test_d113_controls_todays_statement_still_releases(self):
        """What D113 must NOT move: today's visit's own statement (C4: c2e53f8e READY), and another of today's visits'
        statement (an addendum of this encounter whose performer is not verified other) release 99213 - READY with the
        statement quoted; gap 0's C2 (the earlier visit not_stated) and C3 (no other visit) still ask separate_em."""
        released = (
            ("C4: today's visit states it", dyspepsia(a('stated', STATEMENT, ['H2']), H2=TODAY_STATEMENT)),
            ("an addendum of today's encounter", dyspepsia(None, (addendum(), a('stated', STATEMENT, ['A1'])),
                                                            A1=ADDENDUM)),
            ('an addendum naming a clinician whose name does not verify as another', dyspepsia(
                None, (addendum(performer=a('other_clinician', 'Dr. Lena Park', ['A1'])),
                       a('stated', STATEMENT, ['A1'])),
                A1=BY_PARK)),
        )
        for label, (inv, text) in released:
            with self.subTest(label):
                p = gastric_em(inv, text)
                self.assertEqual((p.status, asked(p)), ('ready', []))
                self.assertIn('The documentation states a significant, separately identifiable E/M service '
                              f'(“{STATEMENT}”)', check(p, 'em.same_day_procedure').detail)
                self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
        held = (('C2: the earlier visit not_stated', dyspepsia(None, (earlier_visit()[0], a('not_stated')),
                                                               H1=EARLIER_VISIT)),
                ('C3: no other visit', dyspepsia()))
        for label, (inv, text) in held:
            with self.subTest(label):
                self.assert_held(inv, text)
