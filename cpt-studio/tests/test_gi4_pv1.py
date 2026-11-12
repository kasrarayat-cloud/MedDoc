"""GI round 4, package PV1: the E/M reading fixes C1 and C2, the C4 holds, and V3's hold-only nouns (declared before any
code in tests/fixtures/gi4/declarations/pv1.json). Every case is synthetic.

- C1: an E/M time statement followed directly by "covering", "including" or "spent on" lists the visit's own work;
  a plan word after that word never re-times the statement (h4-01's "52 minutes, covering ..., the orders, ...").
  Everything else after it still does (session 2): a planned time ("in 2 weeks"), a cancellation, a history ("two days
  ago"), a doubt, and a date, since each may say the minutes were another day's or the visit never happened.
- C2: an inline "Complexity / Level of decision making: X" gives MDM level X; "shared decision making" never does.
- C4: a performed E/M reading of any kind is held when the note says the patient was not seen in person, was seen by
  telephone or phone call, was a no-show or did not arrive; video and telehealth visits are not held. Installed's
  _another_time now holds a performed E/M time statement ("Total time at her last visit was 40 minutes."), and C2's new
  label takes the same hold.
- V3: an imaging or laboratory noun in an E/M code's negative passage holds the E/M instead of excluding it.

Each 'pv1-*' mutant of tests/test_gi4_pv1_mutants.py is killed here (H6): a test below fails when that guard is removed.

Repair cycle 1 (2026-11-01, the corrections of the declaration): C1 and C2 release only where the note positively
documents today's in-person office visit (VISIT below has the exam and the office setting OFFICE lacks), and a refused
label is not read at all; C1 skips only a noun of the visit's planning work; C4 holds only on a statement of today's
encounter type and then counts the statements it holds as the documented basis, quoting the line. The cycle's own
tests, one per refutation finding, are tests/test_gi4_pv1_cycle1.py.

Repair cycle 2 (2026-11-01, pv1.json amendment_20261101_cycle2): C1 and C2 are DROPPED (the second refutation of a
releasing family; findings PV1C2-01, -02 and -03). Every test below that pinned a C1 or C2 release now pins installed's
reading of its own input, and says so where it changed; the C4, C4-time, EMR-9 and V3 tests are unchanged. The mutants
that guarded C1 and C2 are retired with their code. The cycle's own tests are tests/test_gi4_pv1_cycle2.py.
"""
import inspect
import datetime as dt
import time

from django.test import SimpleTestCase

from ops.gi4 import battery, regression, replay
from studio import jobs
from studio.gi import cues, detect
from studio.validation import checks

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = dt.date(2026, 10, 26)
OFFICE = B + ('Office visit note\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\nEstablished patient\n'
              'Chief complaint\nHeartburn.\nAssessment and plan\nGERD. Continue omeprazole.\n')
TELEPHONE = B + ('Telephone encounter\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\nEstablished patient\n'
                 'The patient was not seen in the office; we spoke by telephone about her reflux.\nTotal time: 15 minutes.\n')
# repair cycle 1: the office note with the evidence C1 and C2 need (an exam with content beside the office setting)
VISIT = OFFICE.replace('Assessment and plan\n', 'Physical exam\nAbdomen soft, nontender.\nAssessment and plan\n')


def route(text, day=DAY):
    jobs.release_routing_caches()
    return detect.route(text, day)


def em(text, day=DAY):
    """routing's gi.office_em finding (None when routing reads no E/M documentation)."""
    return next((f for f in route(text, day).findings if f.family == 'gi.office_em'), None)


def facts(finding):
    return {f.name: f.value for f in (finding.facts if finding else ())}


def mention(finding, words):
    """The E/M mention of ``finding`` whose span reads ``words``."""
    return next(m for m in finding.mentions if m.span.text == words)


class ActivityListTests(SimpleTestCase):
    """C1 (DROPPED in repair cycle 2): an E/M time statement's activity list re-times it as installed reads it - a plan
    word there ("the orders") reads 'planned' again. Each test pins installed's reading of its own input; the ones that
    pinned C1's release changed (named below), the ones that pinned a hold C1 kept are unchanged but for the retired
    mutants' names."""

    def test_h4_01_reads_neither_its_time_nor_its_decision_making_as_installed(self):
        # repair cycle 2: was test_h4_01_reads_its_time_and_its_decision_making (C1 and C2's release: time+mdm, 52,
        # moderate). Installed's reading, measured on 80df1831d168: no basis, 'planned: orders' beside 'performed'
        text = regression.load_fixtures()['h4-01']['text']
        finding = em(text)
        self.assertEqual(finding.status, 'performed')
        got = facts(finding)
        self.assertFalse({'em_basis', 'time_minutes', 'mdm_level'} & set(got), got)
        self.assertEqual(finding.missing, ('em_basis',))
        self.assertEqual({m.status for m in finding.mentions}, {'performed', 'planned'})
        self.assertNotIn('Complexity of decision making: moderate', [m.span.text for m in finding.mentions])

    def test_each_activity_word_no_longer_releases_the_orders(self):
        # repair cycle 2: was test_each_activity_word (C1's release: 40 minutes read); installed re-times each
        for word in ('covering', 'including', 'spent on', 'which included'):
            text = VISIT + f'Total time: 40 minutes, {word} her history, the examination, the orders and documentation.\n'
            self.assertNotIn('time_minutes', facts(em(text)), word)

    def test_without_an_activity_word_the_orders_still_retime_the_statement(self):
        text = VISIT + 'Total time: 40 minutes, the orders and documentation.\n'
        self.assertNotIn('time_minutes', facts(em(text)))  # as installed: 'planned: orders'

    def test_a_cue_before_the_activity_word_still_retimes_it(self):  # (pv1-c1-after-only retired in repair cycle 2)
        text = VISIT + 'Total time scheduled: 30 minutes, including counseling and documentation.\n'
        self.assertNotIn('time_minutes', facts(em(text)))
        text = VISIT + 'Total time for the orders: 30 minutes, including counseling and documentation.\n'
        self.assertNotIn('time_minutes', facts(em(text)))

    def test_a_date_in_the_activity_list_still_retimes_it(self):  # (pv1-c1-dates-count retired in repair cycle 2)
        # another visit's date may place the minutes on another day: held, as installed
        text = VISIT + 'Total time: 30 minutes, including the visit on 10/20/2026.\n'
        self.assertNotIn('time_minutes', facts(em(text)))
        text = VISIT + 'Total time: 30 minutes, including\nthe visit on 10/20/2026.\n'
        self.assertNotIn('time_minutes', facts(em(text)))

    def test_a_denial_or_another_days_time_in_the_list_still_retimes_it(self):  # (pv1-c1-plan-work retired)
        # session 2: each is held on installed, and read READY when every cue after the activity word was skipped
        for line in ('Total time: 15 minutes, spent on chart review, as the visit was cancelled.',
                     'Total time: 15 minutes, spent on her visit, which was cancelled.',
                     'Total time: 20 minutes, including the visit that was postponed.',
                     'Total time: 20 minutes, covering a visit that was not done.',
                     'Total time: 60 minutes, including 30 minutes of care coordination two days ago.',
                     'Total time: 30 minutes, including time spent in the past on her care.'):
            self.assertNotIn('time_minutes', facts(em(VISIT + line + '\n')), line)

    def test_a_planned_time_in_the_list_still_retimes_it(self):  # (pv1-c1-planned-time retired in repair cycle 2)
        for line in ('Total time: 30 minutes, including the follow-up visit in 2 weeks.',
                     'Total time: 30 minutes, including 10 minutes with her tomorrow.'):
            self.assertNotIn('time_minutes', facts(em(VISIT + line + '\n')), line)

    def test_no_plan_word_of_the_visits_own_work_is_skipped(self):
        # repair cycle 2: was test_each_plan_word_of_the_visits_own_work (C1's release of the four nouns: 40 minutes
        # read); installed reads each as 'planned' and the statement gives no time
        for words in ('the orders', 'the referral to surgery', 'her recommendations', 'next steps'):
            text = VISIT + f'Total time: 40 minutes, covering her history, {words} and documentation.\n'
            self.assertNotIn('time_minutes', facts(em(text)), words)

    def test_a_time_at_another_visit_stays_held(self):  # the diagnosis's C1 counterexample, as installed
        text = VISIT + 'Total time 30 minutes at the follow-up visit next month.\n'
        self.assertNotIn('time_minutes', facts(em(text)))

    def test_a_visit_statement_never_skips_its_own_cues(self):  # (pv1-c1-time-only retired in repair cycle 2)
        # a plan-work noun after a visit statement's "including" ('the orders'): planned, as installed
        text = VISIT.replace('Chief complaint\n', 'Follow-up office visit, including the orders.\nChief complaint\n')
        self.assertEqual(mention(em(text), 'Follow-up office visit').status, 'planned')

    def test_the_cue_readers_take_no_activity_list_and_only_c4_time_finds_one(self):
        # repair cycle 2: was test_only_a_time_statement_has_an_activity_list (read through _pv1_activities, removed with
        # C1). The cue readers are installed's again (no 'activities' parameter, no C1 helper), and the activity word is
        # found only for a time statement, by C4-time's EMR-7 reading (_pv1_activity_word, kept)
        self.assertEqual(list(inspect.signature(detect._clause_reading_cues).parameters),
                         ['an', 'clause', 'ts', 'te', 'em'])
        self.assertEqual(list(inspect.signature(detect._cue_reading).parameters), ['an', 'start', 'end', 'em'])
        for gone in ('_pv1_activities', '_pv1_activity_work', '_PV1_PLAN_WORK'):
            self.assertFalse(hasattr(detect, gone), gone)
        an = detect._analysis(VISIT + 'Total time: 40 minutes, covering the orders.\n', DAY)[0]
        kinds = {m.kind: detect._pv1_activity_word(an, m) for m in an.em}
        self.assertIsNotNone(kinds['em-time'])
        self.assertIsNone(kinds['em-heading'])
        self.assertIsNone(kinds['em-visit'])


class DecisionMakingLabelTests(SimpleTestCase):
    """C2 (DROPPED in repair cycle 2): cues.MDM_LEVEL is installed's pattern again, so no "Complexity / Level of decision
    making: X" label gives a level, with or without the visit's evidence; installed's MDM readings are unchanged and
    shared decision making still gives none."""

    def levels(self, line):
        return [(m.group(0), (m.group('level') or m.group('level2')).lower()) for m in cues.MDM_LEVEL.finditer(line)]

    def test_complexity_and_level_labels_give_no_level_as_installed(self):
        # repair cycle 2: was test_complexity_and_level_labels (C2's third prefix read both; VISIT read 'low', 'mdm')
        self.assertEqual(self.levels('Complexity of decision making: moderate.'), [])
        self.assertEqual(self.levels('Level of decision-making - high'), [])
        for note in (VISIT, OFFICE):
            finding = em(note + 'Complexity of decision making: low.\n')
            self.assertFalse({'mdm_level', 'em_basis'} & set(facts(finding)))
            self.assertNotIn('Complexity of decision making: low', [m.span.text for m in finding.mentions])

    def test_shared_decision_making_never_gives_a_level(self):  # (pv1-c2-shared retired in repair cycle 2)
        for line in ('Shared decision making about colonoscopy, given a bleeding risk that is high.',
                     'Shared decision making about colonoscopy; she accepts the high risk of bleeding.',
                     'Shared decision-making level: high.'):
            self.assertEqual(self.levels(line), [], line)
            self.assertNotIn('mdm_level', facts(em(OFFICE + line + '\n')), line)

    def test_a_label_without_its_separator_or_with_a_list_of_levels_gives_none(self):
        for line in ('Complexity of decision making moderate.', 'Complexity of decision making: low/moderate/high',
                     'Complexity of decision making: low to moderate.', 'Complexity of decision making at the last visit: '
                                                                         'high.'):
            self.assertEqual(self.levels(line), [], line)

    def test_installed_readings_are_unchanged(self):
        self.assertEqual(self.levels('Medical decision making: moderate.'),
                         [('Medical decision making: moderate', 'moderate')])
        self.assertEqual(self.levels('Level of medical decision making: moderate.'),
                         [('medical decision making: moderate', 'moderate')])  # the first branch's span, as installed
        self.assertEqual(self.levels('MDM: high. Moderate complexity MDM.'),
                         [('MDM: high', 'high'), ('Moderate complexity MDM', 'moderate')])

    def test_a_label_inside_another_sentence_gives_no_level(self):
        # session 2: each read 99215 READY through the new label, where installed reads no level at all; repair cycle 1:
        # the label must open its LINE, and a refused label is no mention at all (installed's reading)
        for line in ('Previous note: complexity of decision making: high.',
                     'At last visit, complexity of decision making: high.',
                     'Seen today. Complexity of decision making: low.'):
            finding = em(VISIT + line + '\n')
            self.assertNotIn('mdm_level', facts(finding), line)
            self.assertFalse([m for m in finding.mentions if 'omplexity of decision making' in m.span.text], line)

    def test_a_label_that_opens_its_line_gives_no_level_as_installed(self):
        # repair cycle 2: was test_a_label_that_opens_its_line_is_read (C2's release: 'low', 'moderate')
        for line in ('- Complexity of decision making: low.', '2. Level of decision making: moderate.'):
            self.assertNotIn('mdm_level', facts(em(VISIT + line + '\n')), line)

    def test_a_label_naming_another_visit_is_not_read(self):
        # session 2 held these; repair cycle 1 did not read them; repair cycle 2 reads no label at all (installed)
        for line in ('Complexity of decision making: high (at last visit).',
                     'Complexity of decision making: high, from the prior visit.',
                     'Complexity of decision making: high (at her last visit).',
                     # repair cycle 2: this comparison was read as today's level 'high' (C2's release); installed reads
                     # no level
                     'Complexity of decision making: high, as at her prior visit.'):
            finding = em(VISIT + line + '\n')
            self.assertNotIn('mdm_level', facts(finding), line)
            self.assertFalse([m for m in finding.mentions if m.span.text.startswith('Complexity')], line)


class NotInPersonTests(SimpleTestCase):
    """C4: a note that may document no in-person visit holds every E/M reading; video and telehealth do not."""

    def assert_held(self, text):
        # repair cycle 1 (CTS-2): the statements C4 holds are the note's documented basis, so em_basis is present
        # wherever a time or a decision-making level is stated; the hold is the family's status and every cue
        finding = em(text)
        self.assertIsNotNone(finding)
        self.assertNotIn(finding.status, ('performed', 'incomplete'))
        stated = [m for m in finding.mentions if m.span.text.startswith(('Total time', 'Medical decision'))]
        self.assertEqual('em_basis' in facts(finding), bool(stated))
        for m in finding.mentions:
            self.assertEqual(m.status, 'uncertain', m.span.text)
            self.assertTrue(m.cues[0].startswith(detect.EM_NOT_IN_PERSON + ": '"), m.cues)
        return finding

    def test_a_telephone_only_note_is_held(self):  # kills pv1-c4-hold
        finding = self.assert_held(TELEPHONE)
        # the first words outside a plan or history section are quoted: here the title line
        self.assertEqual(finding.mentions[0].cues[0], f"{detect.EM_NOT_IN_PERSON}: 'Telephone encounter'")

    def test_every_kind_of_e_m_reading_is_held(self):
        text = TELEPHONE.replace('Total time: 15 minutes.\n', 'Medical decision making: low.\nTotal time: 15 minutes.\n'
                                 'Follow-up office visit completed by phone.\n')
        finding = self.assert_held(text)
        self.assertEqual({m.span.text for m in finding.mentions},
                         {'Medical decision making: low', 'Total time: 15 minutes', 'Follow-up office visit'})

    def test_no_show_did_not_arrive_and_did_not_attend(self):
        for words in ('Patient did not arrive; no-show.', 'No-show for this visit.', 'She did not attend.',
                      'He did not show up for the visit.', 'Telephone visit only.', 'Audio-only visit.',
                      'No in-person contact today.', 'Phone f/u about her reflux.', 'Patient no showed.'):
            self.assert_held(OFFICE.replace('Heartburn.\n', words + '\n') + 'Total time: 20 minutes.\n')

    def test_session_two_synonyms(self):  # kills pv1-c4-synonyms
        # each read READY on installed and on PV1's first code in a note that otherwise documents an office visit
        for words in ('The patient was not seen.', 'Visit type: Telephone.', 'Encounter type: phone.',
                      'Type of visit: telephone.', 'Patient missed her appointment.', 'Left without being seen.'):
            self.assert_held(OFFICE.replace('Heartburn.\n', words + '\n') + 'Total time: 20 minutes.\n')

    def test_session_two_synonyms_need_their_own_words(self):
        for words in ('No polyps were seen.', 'Her primary care clinician has not seen her since June.',
                      'Visit type: office.', 'She missed work for two days.', 'He left without his medication list.'):
            text = OFFICE.replace('Heartburn.\n', 'Heartburn. ' + words + '\n') + 'Total time: 20 minutes.\n'
            finding = em(text)
            self.assertEqual((finding.status, facts(finding).get('time_minutes')), ('performed', '20'), words)

    def test_a_head_title_is_read_whatever_its_section(self):  # kills pv1-c4-head
        # the note opens on "Follow-up", a plan heading: the title line under it is in a plan section
        text = B + 'Follow-up\nTelephone visit\nDate of service: 10/26/2026\nEstablished patient\nTotal time: 15 minutes.\n'
        self.assertEqual(detect.layout(text).section_at(text.index('Telephone visit')).kind, 'plan')
        self.assert_held(text)

    def test_the_time_statements_own_sentence_is_read_whatever_its_section(self):
        # repair cycle 1: the visit's own time was by telephone, so the whole document is held (the chief complaint too)
        # and the time is its documented basis (CTS-2); the cue quotes the line
        text = OFFICE.replace('GERD. Continue omeprazole.\n', 'GERD. Continue omeprazole. Total time 25 minutes, by '
                                                                  'telephone.\n')
        self.assertEqual(detect.layout(text).section_at(text.index('by telephone')).kind, 'plan')
        finding = em(text)
        self.assertEqual(facts(finding).get('time_minutes'), '25')
        line = f"{detect.EM_NOT_IN_PERSON}: 'GERD. Continue omeprazole. Total time 25 minutes, by telephone.'"
        self.assertEqual(mention(finding, 'Total time 25 minutes').cues[0], line)
        self.assertEqual(mention(finding, 'Chief complaint').cues[0], line)

    def test_a_plan_or_history_line_about_another_contact_holds_nothing(self):
        for line in ('Telephone follow-up in two weeks.', 'We will call her by phone with the biopsy results.'):
            text = OFFICE.replace('GERD. Continue omeprazole.\n', f'GERD. Continue omeprazole. {line}\n') + \
                'Total time spent on the date of the encounter: 30 minutes.\n'
            finding = em(text)
            self.assertEqual((finding.status, facts(finding).get('time_minutes')), ('performed', '30'), line)
        text = OFFICE.replace('Chief complaint\nHeartburn.\n', 'Chief complaint\nHeartburn.\nPast medical history\n'
                              'Telephone visit in 2024 for reflux.\n') + 'Total time: 30 minutes.\n'
        self.assertEqual(facts(em(text)).get('time_minutes'), '30')

    def test_video_and_telehealth_visits_are_not_held(self):
        for title, line in (('Video visit note', 'Seen by two-way video from her home; she consented to the video visit.'),
                            ('Telehealth visit', 'Seen by telehealth from her home.')):
            text = B + (f'{title}\nDate of service: 10/26/2026\nEstablished patient\nChief complaint\n{line}\n'
                        'Assessment and plan\nGERD.\nTotal time: 20 minutes.\n')
            finding = em(text)
            self.assertEqual((finding.status, facts(finding).get('time_minutes')), ('performed', '20'), title)

    def test_a_phone_number_or_a_call_word_holds_nothing(self):
        text = OFFICE.replace('Office visit note\n', 'Office visit note\nClinic phone: 555-0100\nTelephone: (555) 010-2000\n')
        text = text.replace('Heartburn.\n', 'Heartburn. She called last week to make this appointment.\n')
        finding = em(text + 'Total time: 30 minutes.\n')
        self.assertEqual((finding.status, facts(finding).get('time_minutes')), ('performed', '30'))

    def test_a_reading_that_is_not_performed_is_returned_unchanged(self):
        text = TELEPHONE + 'Assessment and plan\nReturn office visit in three months.\n'
        self.assertEqual(mention(em(text), 'office visit').status, 'planned')

    def test_a_time_in_another_month_is_held(self):  # kills pv1-another-time
        # installed's _another_time alone reads it: no visit is named, so the other-visit words do not
        finding = em(OFFICE + 'Total time spent in August: 40 minutes.\n')
        self.assertNotIn('time_minutes', facts(finding))
        held = mention(finding, 'Total time spent in August: 40 minutes')
        self.assertEqual(held.cues, (detect.EM_ANOTHER_TIME, f"{detect.ANOTHER_TIME_PREFIX}: 'in August' may place it "
                                                              'on another date'))

    def test_a_time_at_the_last_visit_is_held(self):
        text = OFFICE + 'Total time at her last visit was 40 minutes.\n'
        finding = em(text)
        self.assertNotIn('time_minutes', facts(finding))
        held = mention(finding, 'Total time at her last visit was 40 minutes')
        self.assertEqual((held.status, held.cues[0]), ('uncertain', detect.EM_ANOTHER_TIME))
        self.assertTrue(held.cues[1].startswith(detect.ANOTHER_TIME_PREFIX), held.cues)

    def test_a_time_at_another_visit_without_a_determiner_is_held(self):  # kills pv1-other-visit
        # session 2: READY on installed, whose OTHER_TIME needs "her" or "the" before "last visit"
        for line in ('Total time at last visit was 40 minutes.', 'At last visit, total time was 40 minutes.',
                     'Total time: 40 minutes, including 20 minutes at last visit.',
                     'Total time during previous appointment: 40 minutes.',
                     'Total time at recent visit was 40 minutes.'):  # the prepositional words alone read this one
            finding = em(OFFICE + line + '\n')
            self.assertNotIn('time_minutes', facts(finding), line)
        held = mention(em(OFFICE + 'Total time at last visit was 40 minutes.\n'), 'Total time at last visit was 40 minutes')
        self.assertEqual(held.cues, (detect.EM_ANOTHER_TIME,
                                     f"{detect.ANOTHER_TIME_PREFIX}: 'at last visit' may place it on another date"))

    def test_notes_from_the_last_visit_are_the_visits_work(self):
        line = 'Total time: 40 minutes, including review of notes from the last visit.'
        self.assertEqual(facts(em(OFFICE + line + '\n')).get('time_minutes'), '40')

    def test_a_time_on_the_date_of_the_encounter_is_not_held(self):
        text = OFFICE + 'Total time spent on the date of the encounter: 44 minutes.\n'
        self.assertEqual(facts(em(text)).get('time_minutes'), '44')


class OtherServiceNounTests(SimpleTestCase):
    """V3: an imaging study or a laboratory panel named in an E/M code's negative passage holds the E/M."""

    def test_imaging_and_laboratory_nouns(self):  # kills pv1-v3-ultrasound
        for passage in ('Surveillance ultrasound in six months.', 'Repeat MRI of the liver next year.',
                        'CT scan of the abdomen in three months.', 'Basic metabolic panel in one week.',
                        'Repeat blood work in two weeks.', 'Transient elastography next spring.'):
            text = OFFICE + passage + '\n'
            start = text.index(passage)
            self.assertTrue(checks._VAL_names_other_service(text, start, start + len(passage), DAY), passage)
        text = OFFICE + 'Return in six months.\n'
        start = text.index('Return in six months.')
        self.assertFalse(checks._VAL_names_other_service(text, start, start + len('Return in six months.'), DAY))

    def test_agent08s_variant_of_h2_08_holds_the_visit(self):
        """h2-08 with a return office visit beside its ultrasound: installed EXCLUDED 99215 with the ultrasound cited as
        agreeing (the diagnosis's V3); the ultrasound is another service, so the visit is held."""
        text = regression.load_fixtures()['h2-08']['text'].replace(
            'Surveillance ultrasound in six months.', 'Surveillance ultrasound in six months. Return office visit in six '
                                                      'months.')
        row = battery.run_row(battery.modules(), 'v3', text, [('99215', 'Surveillance ultrasound in six months.', 'MAY')],
                              {'service_date': '2026-10-05'})
        self.assertEqual(row['proposals']['99215']['bucket'], 'selected')
        self.assertEqual(row['proposals']['99215']['status'], 'needs_clarification')


class QuoteBoundTests(SimpleTestCase):
    """Session 2, H7: the quotes of the label-inside and other-visit holds are cut from a bounded window
    (detect._PV1_QUOTE_WINDOW), never from the sentence's start or a whole match: one sentence may hold thousands of
    labels or time statements."""

    def test_a_label_after_a_run_of_blanks_gives_no_level_as_installed(self):
        # repair cycle 2: was test_a_label_after_a_run_of_blanks_on_its_line_does_not_open_it, whose second case pinned
        # C2's release ('high' for a label opening its line after the blanks); installed reads no label either way
        text = VISIT + 'Copied words' + ' ' * (detect._PV1_QUOTE_WINDOW + 40) + 'complexity of decision making: high.\n'
        self.assertNotIn('mdm_level', facts(em(text)))
        text = VISIT + ' ' * (detect._PV1_QUOTE_WINDOW + 40) + 'Complexity of decision making: high.\n'
        self.assertNotIn('mdm_level', facts(em(text)))

    def test_the_other_visit_quote_is_cut_from_the_head_of_its_match(self):  # kills pv1-other-visit-window
        text = OFFICE + 'Total time 40 minutes at' + ' ' * (detect._PV1_QUOTE_WINDOW + 40) + 'last visit.\n'
        held = mention(em(text), 'Total time 40 minutes')
        self.assertEqual(held.cues, (detect.EM_ANOTHER_TIME, f"{detect.ANOTHER_TIME_PREFIX}: 'at' may place it on another "
                                                              'date'))

    def test_one_sentence_of_many_labels_routes_in_linear_time(self):
        # 3800 labels in one 198,000-character sentence: 6.4 s of CPU on 3a6a5e77d (each quote cut from the sentence's
        # start), about 2 s with the window (installed reads no label here: 0.9 s). CPU time, so another process's load
        # does not count. Repair cycle 2 dropped C2, so no label is read here (installed's cost); the bound stays.
        text = OFFICE + 'complexity of decision making: high, at last visit, ' * 3800 + 'end.\n'
        jobs.release_routing_caches()
        started = time.process_time()
        detect.route(text, DAY)
        self.assertLess(time.process_time() - started, 5.0)


class DeclaredOutcomeTests(SimpleTestCase):
    """The outcomes the PV1 declaration names, read as the stages read them."""

    def test_the_two_battery_rows_are_held(self):
        rows = battery.run('time')
        self.assertEqual(rows['telephone-only time']['proposals']['99212']['status'], 'needs_clarification')
        self.assertEqual(rows['last visit time']['proposals']['99213']['status'], 'needs_clarification')
        self.assertEqual([v for row in rows.values() for p in row['proposals'].values() for v in p['violations']], [])

    def test_h4_01s_99204_is_held_after_the_walks_date_a_software_false_hold(self):
        # repair cycle 2: was test_h4_01s_99204_is_ready_after_the_walks_date (C1 and C2's release). With both dropped,
        # 99204 reads as installed reads it after 10-26: held, asking the basis and warning 'planned: orders' - a
        # SOFTWARE false hold (pv1.json amendment_20261101_cycle2, known limits): L39 states 52 minutes and L40 a
        # moderate level, and the reader can read neither. The walk's date and send are PD's, unchanged.
        record = replay.replay_document(replay.modules(), regression.load_fixtures()['h4-01'])
        walk = record['states']['walk']
        self.assertEqual(walk['sends'], '2026-10-26')
        self.assertTrue(walk['response'].startswith('retained'), walk['response'])
        code = next(p for p in walk['proposals'] if p['code'] == '99204')
        self.assertEqual((code['bucket'], code['status'], code['checks']),
                         ('selected', 'needs_clarification', [['service.status', 'warn'], ['facts.required', 'warn']]))
        self.assertEqual(walk['routing']['gi.office_em']['missing'], ['em_basis'])
        self.assertEqual(walk['routing']['gi.office_em']['mentions'], ['performed', 'planned'])
        none = next(p for p in record['states']['none']['proposals'] if p['code'] == '99204')
        self.assertEqual((none['status'], none['checks']),
                         ('needs_clarification', [['service.status', 'warn'], ['facts.required', 'warn'],
                                                  ['context.service_date', 'fail']]))
