"""DECISIONS D130 (the round-4 em-same-day repair's parity notes (a) and (e), measured on 437b708bb), SYNTHETIC: an
act of kind 'other' that Gemini files under the visit makes a possible same-day procedure when its own status words
state it was performed on the date of service; the routine pre-procedure visit's performed_status question is a
recorded residual.

- Note (a): detect's procedure-word routing reads "Excision of a 1 cm sebaceous cyst on the upper back was performed in
  the office today." as gi.other performed, so c2e53f8e holds 99213 with separate_em ("Other GI service is documented as
  performed on the same date"). Gemini may file that act under the visit (procedure office_em by its own word "office",
  the visit line's "Office visit", or em_other), kind 'other': it had family gi.office_em, which no arm of
  combination.procedure_day read (D81's families, D94's gi.unsupported and no family, D109's procedural kinds), so 99213
  was READY: "No same-day procedure is documented". Such an act is now a POSSIBLE same-day procedure, labelled "Other GI
  service" as the installed routing reads it, never a done one (D87: its kind names no procedure), when facts.day_of
  places it ON the date of service and its own status words state that it was performed ("was performed", "was done",
  "underwent", and their plurals: combination.DONE_STATEMENTS). An act whose naming words (its kind and target words,
  combination.NAMING_WORDS) name a test, an order, an interpretation, a lab or imaging, or counseling
  (combination.NOT_PROCEDURES) never counts; one whose status words state neither ("was excised", "I performed", "was
  completed") is not counted - a recorded cost where c2e53f8e holds.
- Note (e): a colonoscopy report with "History and physical: routine pre-procedure assessment; no separate E/M service
  was provided." and 99213 - c2e53f8e asks performed_status (services.EM_ROUTINE negates the documented visit), em_basis
  and separate_em; the new path asks no performed_status when Gemini reads the visit as performed or not performed. The
  question is the visit code's own (its supporting event, events.evaluate and assess), outside procedure_day, so it is
  RECORDED, NOT REPAIRED: the pin holds 99213 held in all three readings, as it is, so the residual stays visible.

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). The installed release's outputs (c2e53f8e, engine.assess as tests/test_harness_engine.py
drives it, member values office and established) quoted in the docstrings were measured on byte-identical texts.
Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, events, facts
from studio.validation import checks
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_families import ANOSCOPY, MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r3_integration_d90_d92_d94 import EXCISION
from tests.test_interpretation_r4_em_same_day import OTHER_GI_LABEL, held_for_separate_em, ready_with_no_procedure_day
from tests.test_interpretation_r5_em import NO_PROPOSAL

DAY = '2026-11-09'
CYST = 'Excision of a 1 cm sebaceous cyst'
POSSIBLY = 'possibly performed on the same date (its performance is not established)'
OFFICE_WORD = a('office_em', 'office', ['P2'])  # filed under the visit by the act's own word "office"
VISIT_WORDS = a('office_em', 'Office visit', ['V1'])  # by the visit line's words


def reading_of(inv):
    return events.Reading.of(inv)


def procedure_day(inv):
    return combination.procedure_day(reading_of(inv), DAY)


def em(inv, text, user_values=MEMBER):
    return proposal(run(inv, text, [('99213', VISIT)], user_values=user_values), '99213')


def other(kind_words: str, status_words: str, procedure=None, **changes) -> dict:
    """E1 (P2): an act of kind 'other', performed, filed under the visit by its own word 'office' unless ``procedure``
    says otherwise; the current encounter and the documenting team by the frame defaults unless ``changes`` say."""
    return act('E1', 'P2', 'other', kind_words, status_words=status_words,
               procedure=procedure if procedure is not None else OFFICE_WORD, **changes)


def note(line: str, item: dict, *, anoscopy: bool = False) -> tuple:
    """(inventory, text) of the families review's office document (D94's CYST_TEXT): the visit (E0, V1), its total time
    (V2), the act line P2 (E1) and the plan (P3); with ``anoscopy``, finding 20's office lines (the anoscopy line P1,
    which no event reads)."""
    lines = {'V1': VISIT, 'V2': TIME, **({'P1': ANOSCOPY} if anoscopy else {}), 'P2': line, 'P3': PLAN}
    return inventory(lines, events=[visit(), item], visits=[visit_facts()])


def held_as_possible(test, inv, text):
    """The act is a POSSIBLE other GI service (never a done one), and 99213 is held with separate_em naming it."""
    test.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,)))
    p = em(inv, text)
    held_for_separate_em(test, p, OTHER_GI_LABEL)
    test.assertIn(f'{OTHER_GI_LABEL} is {POSSIBLY}', check(p, 'em.same_day_procedure').detail)
    return p


# --- note (a): an act of kind 'other' filed under the visit ----------------------------------------------------------

class D130KindOtherFiledUnderTheVisit(SimpleTestCase):
    """D130: an act of kind 'other' filed under the visit, whose own status words state it was performed and whose date
    of service is its own, is a possible same-day procedure."""

    def test_d130_note_a_the_office_excision_filed_under_the_visit_asks_separate_em(self):
        """Note (a)'s input: D94's office excision line filed under the visit (procedure office_em, its words 'office'),
        kind other 'Excision of a 1 cm sebaceous cyst', performed 'was performed', current by the frame default - on
        the families review's document and on finding 20's office lines. 1caaf0609: READY, 'No same-day procedure is
        documented'; c2e53f8e: held, separate_em, 'Other GI service is documented as performed on the same date'. Now
        held, separate_em, the excision a possible other GI service; with no member values separate_em beside setting
        and patient_status (1caaf0609: the first two only)."""
        for label, anoscopy in (("the families review's document", False), ("finding 20's office lines", True)):
            with self.subTest(label):
                inv, text = note(EXCISION, other(CYST, 'was performed'), anoscopy=anoscopy)
                self.assertEqual(reading_of(inv).events['E1']['family'], 'gi.office_em')
                held_as_possible(self, inv, text)
                self.assertEqual(sorted(asked(em(inv, text, user_values=None))),
                                 ['patient_status', 'separate_em', 'setting'])

    def test_d130_however_gemini_files_it_under_the_visit(self):
        """The same excision filed under the visit by the visit line's words ('Office visit'), as em_other with no
        words, or with its current time verified by 'today': each READY at 1caaf0609, held at c2e53f8e, now held."""
        variants = (
            ("the visit line's words", other(CYST, 'was performed', VISIT_WORDS), 'gi.office_em'),
            ('em_other, no words', other(CYST, 'was performed', a('em_other')), 'gi.em_other'),
            ("its time verified by 'today'", other(CYST, 'was performed', time=a('current_encounter', 'today',
                                                                                  ['P2'])), 'gi.office_em'),
        )
        for label, item, family in variants:
            with self.subTest(label):
                inv, text = note(EXCISION, item)
                self.assertEqual(reading_of(inv).events['E1']['family'], family)
                held_as_possible(self, inv, text)

    def test_d130_its_own_status_words_state_it_performed_on_the_date(self):
        """The status words the rule reads - 'was done', 'underwent', the plural 'were performed', and 'was performed'
        within longer words ('was performed without complication': no negator is read, so a hold is never lifted by
        one; 'was performed in order to relieve pain': the status words are never read for what the act is) - and a
        date its own words place it on ('Earlier today', 'Earlier in the day': earlier_encounter, ON by
        facts.day_of). Each READY at 1caaf0609 and held at c2e53f8e; now held."""
        cases = (
            ("'was done'", 'Excision of a 1 cm sebaceous cyst on the upper back was done in the office today.',
             other(CYST, 'was done')),
            ("'underwent'", 'She underwent excision of a 1 cm sebaceous cyst on the upper back in the office today.',
             other('excision of a 1 cm sebaceous cyst', 'underwent')),
            ("'were performed'", 'Excisions of two sebaceous cysts on the upper back were performed in the office '
             'today.', other('Excisions of two sebaceous cysts', 'were performed')),
            ("'was performed without complication'", 'Excision of a 1 cm sebaceous cyst on the upper back was '
             'performed without complication in the office today.',
             other(CYST, 'was performed without complication')),
            ("'was performed in order to relieve pain'", 'Excision of a 1 cm sebaceous cyst on the upper back was '
             'performed in order to relieve pain today.', other(CYST, 'was performed in order to relieve pain')),
            ("'Earlier today'", 'Earlier today, excision of a 1 cm sebaceous cyst on the upper back was performed in '
             'the office.', other('excision of a 1 cm sebaceous cyst', 'was performed',
                                  time=a('earlier_encounter', 'Earlier today', ['P2']))),
            ("'Earlier in the day'", 'Earlier in the day, excision of a 1 cm sebaceous cyst on the upper back was '
             'performed in the office.', other('excision of a 1 cm sebaceous cyst', 'was performed',
                                               time=a('earlier_encounter', 'Earlier in the day', ['P2']))),
        )
        for label, line, item in cases:
            with self.subTest(label):
                inv, text = note(line, item)
                self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), facts.ON)
                held_as_possible(self, inv, text)

    def test_d130_it_is_only_ever_possible(self):
        """D87: an act read by its words is a doubt, never a fact - even with every attribute verified (its time by
        'today') it is possible, never documented as performed; an uncertain status is possible too (a doubt is never
        an absence, D62). And it is labelled as the installed routing reads it, 'Other GI service', never the visit's
        family ('Office / outpatient evaluation and management')."""
        for label, item in (("every attribute verified", other(CYST, 'was performed',
                                                               time=a('current_encounter', 'today', ['P2']))),
                            ('status uncertain', other(CYST, 'was performed', status='uncertain'))):
            with self.subTest(label):
                inv, text = note(EXCISION, item)
                found = procedure_day(inv)
                self.assertEqual((found.labels, found.possible), ((), (OTHER_GI_LABEL,)))
                self.assertNotIn('documented as performed', check(em(inv, text), 'em.same_day_procedure').detail)

    def test_d130_with_no_e_m_proposed_the_visit_item_is_listed(self):
        """An effect: with no E/M code proposed, 46e461e7f set the visit's 'has no supported proposal' item apart
        (not_listed) beside the excision. DECISIONS D134 (the review of D130, em2 problem 3): beside a procedure only
        POSSIBLY done - and an act read by its statement is never more - the visit stays listed, as 1caaf0609 listed
        it. c2e53f8e sets it apart here (its routing reads the excision as a performed other GI service): a listing
        where c2e53f8e lists nothing, never a READY (recorded in DECISIONS D134). Named '..._is_not_pushed' until
        DECISIONS D144 (currency3 review problem 7) named it by what it asserts."""
        inv, text = note(EXCISION, other(CYST, 'was performed'))
        result = run(inv, text, [], user_values=MEMBER)
        self.assertIn(NO_PROPOSAL, [str(item.get('label')) for item in result.completeness['unresolved_items']])
        self.assertEqual(result.completeness['not_listed'], [])

    def test_d130_beside_an_undatable_act_the_e_m_asks_separate_em(self):
        """An effect of assess's existing order (a procedure day asks separate_em; only without one does an undatable
        act ask event_time): the excision beside a banding filed under the visit whose time Gemini left 'unknown'.
        1caaf0609: 99213 asks the banding's event_time; c2e53f8e: separate_em; now separate_em, and the banding stays
        listed undatable. Without the excision the banding still asks event_time (D111)."""
        band_line = 'Rubber band ligation of one internal hemorrhoid was performed.'
        band = act('E2', 'P4', 'band_ligation', 'Rubber band ligation', status_words='was performed',
                   procedure=VISIT_WORDS, time=a('unknown'), target=tg('', 'anal_canal', 'one internal hemorrhoid',
                                                                     ['P4']))
        lines = {'V1': VISIT, 'V2': TIME, 'P2': EXCISION, 'P4': band_line, 'P3': PLAN}
        inv, text = inventory(lines, events=[visit(), other(CYST, 'was performed'), band], visits=[visit_facts()])
        self.assertEqual(procedure_day(inv), combination.ProcedureDay(possible=(OTHER_GI_LABEL,), undatable=('E2',)))
        self.assertEqual(asked(em(inv, text)), ['separate_em'])
        alone = {pid: line for pid, line in lines.items() if pid != 'P2'}
        inv, text = inventory(alone, events=[visit(), band], visits=[visit_facts()])
        self.assertEqual(asked(em(inv, text)), ['event_time'])


# --- note (a): what never counts, and what is not counted ------------------------------------------------------------

class D130WhatTheStatementNeverCounts(SimpleTestCase):
    """D130's controls and recorded costs: what an act of kind 'other' filed under the visit still does NOT make."""

    def test_d130_a_test_an_order_an_interpretation_a_lab_imaging_or_counseling_never_counts(self):
        """An act whose own words name a test, an order, an interpretation, a lab or imaging, or counseling never
        counts, whatever its status words: each READY with no procedure day at 1caaf0609, at c2e53f8e and now. Nor
        does an act of another kind outside SAME_DAY_KINDS (moderate sedation 'was performed', D109's control)."""
        controls = (
            ('a test (ECG)', 'A 12-lead ECG was performed in clinic today.',
             other('12-lead ECG', 'was performed', VISIT_WORDS)),
            ('a test (breath test)', 'A hydrogen breath test was performed in the office today.',
             other('hydrogen breath test', 'was performed')),
            ('an order', 'An order for a colonoscopy was done today.',
             other('order for a colonoscopy', 'was done', VISIT_WORDS)),
            ('an interpretation', 'Interpretation of the outside CT images was performed today.',
             other('Interpretation of the outside CT images', 'was performed', VISIT_WORDS)),
            ('a lab', 'Labs were done in the office today.', other('Labs', 'were done')),
            ('imaging (ultrasound)', 'An abdominal ultrasound was performed in the office today.',
             other('abdominal ultrasound', 'was performed')),
            ('imaging (CT)', 'A CT of the abdomen was done today.', other('CT of the abdomen', 'was done',
                                                                          VISIT_WORDS)),
            ('counseling', 'Counseling on a high-fiber diet was done today.',
             other('Counseling on a high-fiber diet', 'was done', VISIT_WORDS)),
            ("moderate sedation filed under the visit (no kind 'other')", 'Moderate sedation was performed today.',
             act('E1', 'P2', 'moderate_sedation', 'Moderate sedation', status_words='was performed',
                 procedure=VISIT_WORDS)),
        )
        for label, line, item in controls:
            with self.subTest(label):
                inv, text = note(line, item)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                ready_with_no_procedure_day(self, em(inv, text))

    def test_d130_words_that_cannot_tell_are_not_counted(self):
        """When the status words do not state a procedure was performed, the act is not counted (THE SPEC'S COST,
        recorded): 'was excised', 'I performed', 'was completed' - READY at 1caaf0609 and now; c2e53f8e holds each
        with separate_em (its _DONE and _OTHER_OBJECT_CUE read 'completed' and 'I performed', and 'excised' reads
        gi.other uncertain). D109's control ('Counseling was provided.') is READY on all three."""
        cases = (
            ("'was excised'", 'A 1 cm sebaceous cyst on the upper back was excised in the office today.',
             other('excised', 'was excised')),
            ("'I performed'", 'I performed excision of a 1 cm sebaceous cyst on the upper back today.',
             other('excision of a 1 cm sebaceous cyst', 'I performed', VISIT_WORDS)),
            ("'was completed'", 'Excision of a 1 cm sebaceous cyst on the upper back was completed in the office '
             'today.', other(CYST, 'was completed')),
            ("D109's control: 'was provided'", 'Counseling was provided.',
             act('E1', 'P2', 'other', 'counseling', status_words='was provided', procedure=VISIT_WORDS)),
        )
        for label, line, item in cases:
            with self.subTest(label):
                inv, text = note(line, item)
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                ready_with_no_procedure_day(self, em(inv, text))

    def test_d130_only_on_the_date_of_service(self):
        """'Placed on the date': an excision verified 'in 2024' (OFF) and a planned one are READY with no question, as
        at 1caaf0609. One whose time Gemini left 'unknown' (UNDATABLE) was READY too (the recorded residual: c2e53f8e
        holds it with separate_em); DECISIONS D133 (the review of D130, em2 problem 0) dates the statement arm by the
        one currency rule, so it is listed undatable and 99213 asks its event_time (held), as mutant M3 showed."""
        cases = (
            ("verified 'in 2024'", 'Excision of a 1 cm sebaceous cyst on the upper back was performed in 2024.',
             other(CYST, 'was performed', time=a('earlier_encounter', 'in 2024', ['P2'])), facts.OFF),
            ("time 'unknown'", 'Excision of a 1 cm sebaceous cyst on the upper back was performed in the office.',
             other(CYST, 'was performed', time=a('unknown')), facts.UNDATABLE),
            ('planned', 'Excision of a 1 cm sebaceous cyst on the upper back will be performed at the next visit.',
             other(CYST, 'will be performed', status='planned', time=a('future', 'at the next visit', ['P2'])),
             facts.OFF),
        )
        for label, line, item, day in cases:
            with self.subTest(label):
                inv, text = note(line, item)
                self.assertEqual(facts.day_of(reading_of(inv).events['E1'], DAY), day)
                if day == facts.UNDATABLE:  # D133
                    self.assertEqual(procedure_day(inv), combination.ProcedureDay(undatable=('E1',)))
                    p = em(inv, text)
                    self.assertEqual((p.status, asked(p)), ('needs_clarification', ['event_time']))
                    self.assertEqual(p.clarifications[0].question,
                                     'Was the act (“was performed”) done at this encounter?')
                    continue
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                ready_with_no_procedure_day(self, em(inv, text))

    def test_d130_only_under_the_visit(self):
        """The statement arm reads office_em and em_other only (the spec's 'filed under the visit'): the excision filed
        as sedation is READY (RECORDED RESIDUAL: c2e53f8e holds it). D94's arm is unchanged: not_gi keeps 'Service
        outside the GI profiles' (done), 'unknown' 'A procedure CPT Studio could not identify' (possible; DECISIONS
        D151 withdrew D144's ``unidentified``, which this subtest had also asserted)."""
        inv, text = note(EXCISION, other(CYST, 'was performed', a('sedation')))
        self.assertEqual(procedure_day(inv), combination.ProcedureDay())
        ready_with_no_procedure_day(self, em(inv, text))
        for value, expected in (('not_gi', combination.ProcedureDay(labels=('Service outside the GI profiles',))),
                                ('unknown', combination.ProcedureDay(possible=(combination.UNIDENTIFIED_PROCEDURE,)))):
            with self.subTest(procedure=value):
                inv, _ = note(EXCISION, other(CYST, 'was performed', a(value, CYST, ['P2']) if value == 'not_gi'
                                              else a(value)))
                self.assertEqual(procedure_day(inv), expected)

    def test_d130_the_recorded_costs_are_holds(self):
        """THE SPEC'S COST on constructed inputs, recorded: an act of kind 'other' filed under the visit whose status
        words say 'was performed' and whose words name none of the never-counted classes is held, where c2e53f8e is
        READY ('removal' is no procedure word of detect's; 'history' and 'reconciliation' are not procedures): a
        perianal skin-tag removal, a history and physical, a medication reconciliation, and an answer off the contract
        (status performed, words 'No excision was performed'). The spec's 'names imaging' never counted an
        ultrasound-guided paracentesis, READY where c2e53f8e holds it; DECISIONS D133 (the review of D130, em2
        problem 1) never sets apart a head holding 'guided', so it is held now, as c2e53f8e holds it."""
        holds = (
            ('a skin-tag removal', 'Removal of a perianal skin tag was performed in the office today.',
             other('Removal of a perianal skin tag', 'was performed')),
            ('a history and physical', 'A history and physical was performed today.',
             other('history and physical', 'was performed', VISIT_WORDS)),
            ('a medication reconciliation', 'Medication reconciliation was performed today.',
             other('Medication reconciliation', 'was performed', VISIT_WORDS)),
            ("words 'No excision was performed'", 'No excision was performed today.',
             other('excision', 'No excision was performed')),
        )
        for label, line, item in holds:
            with self.subTest(label):
                inv, text = note(line, item)
                held_as_possible(self, inv, text)
        inv, text = note('Ultrasound-guided paracentesis was performed in the office today.',
                         other('Ultrasound-guided paracentesis', 'was performed'))
        held_as_possible(self, inv, text)  # D133


class D130TheStatementReader(SimpleTestCase):
    """combination._stated_procedure reads the act's own words, whole and word-bounded (lexicon.holds)."""

    def stated(self, kind_words='Excision', status_words='was performed', target_words=''):
        line = f'{kind_words} {status_words} {target_words}.'
        item = other(kind_words, status_words, target=tg('', 'other', target_words, ['P2']) if target_words else tg())
        inv, _ = note(line, item)
        return combination._stated_procedure(reading_of(inv).events['E1'])

    def test_d130_the_done_statements_are_read_in_the_status_words_only(self):
        for words in ('was performed', 'Was Performed', 'were performed', 'was done', 'were done', 'underwent',
                      'was performed in the office today', 'was  performed'):
            with self.subTest(words=words):
                self.assertTrue(self.stated(status_words=words))
        for words in ('performed', 'was not performed', 'was reperformed', 'I performed', 'was excised',
                      'was completed', 'had undergone', 'done'):
            with self.subTest(words=words):
                self.assertFalse(self.stated(status_words=words))
        # a done statement in the kind words is not the status words'
        self.assertFalse(self.stated(kind_words='Excision was performed', status_words='today'))

    def test_d130_the_never_counted_classes_are_read_in_the_kind_words_head(self):
        """The words that name the act (NAMING_WORDS): DECISIONS D133 (the review of D130, em2 problem 1) - its kind
        words only, in their head; never its target words (they say what the act was done to: 'under ultrasound' sets
        nothing apart now) nor its status words, which state its status ('in order to' names no order). A head holding
        'guided' is never set apart (D133: 'CT-guided drainage' is counted now). Named
        '..._in_the_kind_and_target_words' until DECISIONS D144 (currency3 review problem 7) named it by what it
        asserts."""
        self.assertEqual(combination.NAMING_WORDS, ('kind',))
        self.assertFalse(self.stated(kind_words='ECG'))
        self.assertTrue(self.stated(target_words='under ultrasound'))  # D133
        self.assertTrue(self.stated(status_words='was performed in order to relieve pain'))
        self.assertTrue(self.stated(status_words='ECG was performed'))  # a name in the status words is not read
        self.assertFalse(self.stated(kind_words='X-ray'))
        self.assertTrue(self.stated(kind_words='CT-guided drainage'))  # D133
        for named in ('test', 'order', 'interpretation', 'lab', 'imaging', 'counseling'):
            phrases = dict(combination.NOT_PROCEDURES)[named]
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    self.assertFalse(self.stated(kind_words=f'the {phrase} thing'))
        self.assertEqual([name for name, _ in combination.NOT_PROCEDURES],
                         ['test', 'order', 'interpretation', 'lab', 'imaging', 'counseling'])

    def test_d130_the_words_are_word_bounded(self):
        """Never inside a longer word: a labial cyst is no lab, a protest no test, a scanty lesion no scan."""
        for words in ('Excision of a labial cyst', 'Excision of a protest lesion', 'Excision of a scanty lesion',
                      'Excision of a borderline lesion'):
            with self.subTest(words=words):
                self.assertTrue(self.stated(kind_words=words))
        inv, text = note('Excision of a labial cyst was performed in the office today.',
                         other('Excision of a labial cyst', 'was performed'))
        held_as_possible(self, inv, text)

    def test_d130_the_visit_families_are_office_em_and_em_other(self):
        self.assertEqual(combination.VISIT_FAMILIES, {'gi.office_em', 'gi.em_other'})
        self.assertFalse(combination.VISIT_FAMILIES & combination.SAME_DAY_FAMILIES)


# --- note (e): the routine pre-procedure visit, recorded --------------------------------------------------------------

ROUTINE = 'History and physical: routine pre-procedure assessment; no separate E/M service was provided.'
COLONOSCOPY = {'P4': 'Procedure: Colonoscopy',
               'P1': 'The colonoscope was advanced to the cecum and the examination was completed.', 'P2': ROUTINE}


class D130RoutineVisitRecorded(SimpleTestCase):
    """Note (e), RECORDED, NOT REPAIRED: the routine-visit performed_status question is the visit code's own."""

    def test_d130_note_e_the_routine_visit_is_held_in_every_reading(self):
        """Note (e)'s input: the colonoscopy report with 'History and physical: routine pre-procedure assessment; no
        separate E/M service was provided.', Corti proposing 45378 and 99213 citing that line. c2e53f8e asks
        performed_status, em_basis and separate_em in every reading. The new path, at 1caaf0609 and now: Gemini reads
        the visit as performed - em_basis and separate_em; as not performed - statement_scope, em_basis and
        separate_em; no visit event - performed_status, em_basis and separate_em. 99213 is held in every case and
        45378 READY; the missing performed_status question is the recorded residual (outside procedure_day: the E/M
        code's own supporting event, events.evaluate and assess)."""
        readings = (
            ('the visit performed', act('E2', 'P2', 'em_visit', 'pre-procedure assessment',
                                        status_words='routine pre-procedure assessment',
                                        procedure=a('office_em', 'History and physical', ['P2'])),
             ['em_basis', 'separate_em']),
            ('the visit not performed', act('E2', 'P2', 'em_visit', 'E/M service', status='not_performed',
                                            status_words='no separate E/M service was provided',
                                            procedure=a('office_em', 'E/M service', ['P2'])),
             ['statement_scope', 'em_basis', 'separate_em']),
            ('no visit event', None, ['performed_status', 'em_basis', 'separate_em']),
        )
        for label, visit_event, questions in readings:
            with self.subTest(label):
                items = [exam()] + ([visit_event] if visit_event is not None else [])
                inv, text = inventory(COLONOSCOPY, events=items, reach=[reached(words='cecum', passage='P1')])
                result = run(inv, text, [('45378', 'The colonoscope was advanced to the cecum'), ('99213', ROUTINE)],
                             user_values=MEMBER)
                p = proposal(result, '99213')
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', questions))
                self.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)
                self.assertEqual(proposal(result, '45378').status, 'ready')
