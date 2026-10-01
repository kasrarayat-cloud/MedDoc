"""Ordinary notes on the DEFAULT path, refutation rounds 5 and 6 (2026-10-01): the D30 ordinary case's held answers.

Round 5 traced the D30 ordinary note's seven held answers to the hold rules (the workflow stream's d30-holds-findings:
six unjustified, one appropriate) and added three readings that released five of them. Refutation round 6 withdrew all
three, and the default path is the base's again (f5fe720f), because each released wrong answers in the same shape:
  - L1:F2 / L2:F1: a line's own 'this ...' frame ('during this admission', 'at this visit', 'during this reporting
    period') lifting an earlier paragraph's past event - the earlier event may fall inside that frame and contradict it
    ('The patient stopped taking the prescribed medication last month.' before 'The patient has taken every prescribed
    dose during this reporting period.');
  - L1:F1 / L2:F2: two 'plain' lines repeating one core word joining nothing - any noun passed as plain ('The warfarin is
    recorded for discontinuation.', '... prescribed for the dog.', 'The staff record the refusal of the warfarin.'), and
    on the base a shared word may only ADD a hold;
  - the parser's syntax-only completeness for a thing subject or the patient as object (v3_21, v3_53) - this round's
    first refuter's batteries had it adopt 'The warfarin belongs to the dog.' as Medications, 'The physiotherapy ended
    last year.' as a Plan and 'The apixaban replaces the warfarin.', each of v3_21's or v3_53's own shape: only meaning
    tells them apart.
So D30's v3_21, v3_24, v3_25, v3_46, v3_48, v3_50 and v3_53 are held, as on the base; only v3_44 is answered."""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core import generation as g
from core.tests.test_v3_notes_floors import DEFAULT, clinic_form
from core.tests.test_v3_notes_repair import adopt
from core.tests.test_v3_ordinary_notes import field

FIXTURE = json.loads(Path(__file__).with_name('fixtures').joinpath('ordinary_literal_cases.json').read_text())
#: The D30 question the fixture does not carry (its compliance question), label as printed on the dev form.
V3_48 = ('Has the patient fully complied with treatment including taking prescribed medication? If not, please detail '
         'the action taken to address this.')
V3_48_QUOTE = 'The patient has taken every prescribed dose during this reporting period.'
GAPS = ('\n\n', '\r\n\r\n', '\n \n')


def d30_fields():
    result = []
    for row in FIXTURE['cases']:
        target = field(row['key'], row['label']); target['context'] = row['context']
        if row['source_questions']:
            target['source_questions'] = copy.deepcopy(row['source_questions'])
        result.append(target)
    extra = field('v3_48', V3_48); extra['context'] = 'Part B > Social Supervisor’s Report > Treatment'
    result.append(extra)
    return result


@override_settings(**DEFAULT)
class D30OnTheDefaultPath(SimpleTestCase):
    #: held on the default path, as on the base: v3_25 (another person, appropriately) and six the trace called
    #: unjustified - recovering them needs a reader of meaning (refutation round 6)
    HELD = ('v3_21', 'v3_24', 'v3_25', 'v3_46', 'v3_48', 'v3_50', 'v3_53')

    def test_d30_is_answered_as_on_the_base(self):
        # the fixture's seven questions and the compliance question v3_48
        fields = d30_fields()
        picks = {row['label']: [row['quote']] for row in FIXTURE['cases']}
        picks[V3_48] = [V3_48_QUOTE]
        quotes = {row['label']: row['quote'] for row in FIXTURE['cases']}
        quotes[V3_48] = V3_48_QUOTE
        by_key = {f['label']: f['key'] for f in fields}
        for gap in GAPS:
            notes = FIXTURE['notes'].replace('\n\n', gap)
            out = adopt(notes, picks, fields)
            supported = {}
            for row in FIXTURE['cases'] + [{'key': 'v3_48', 'label': V3_48}]:
                label = row['label']; answer = out[label]
                with self.subTest(key=row['key'], gap=gap):
                    if row['key'] in self.HELD:
                        self.assertEqual(answer['status'], 'conflict', answer)
                    else:
                        self.assertEqual((answer['status'], answer['text']), ('supported', quotes[label]), answer)
                        supported[by_key[label]] = answer
            self.assertEqual(sorted(supported), ['v3_44'], gap)
            # the page and finalization read the same: nothing answered is refused, nothing shown held
            self.assertEqual(g.governed_decisions(notes, fields, supported), [])
            governance = g.governance_for(notes, fields)
            for f in fields:
                if f['key'] in supported:
                    row = g.as_currently_governed(governance, notes, {**f, **supported[f['key']]})
                    self.assertEqual((row['status'], row['text']), ('supported', supported[f['key']]['text']))


def _held(test, notes, label, pick):
    fields = clinic_form()
    answer = adopt(notes, {label: [pick]}, fields)[label]
    test.assertNotEqual(answer['status'], 'supported', (notes, answer.get('text')))
    candidate = answer.get('held_candidate') or {}
    if candidate.get('evidence'):
        key = next(f['key'] for f in fields if f['label'] == label)
        stored = {'text': candidate['text'], 'status': 'supported', 'reviewed': True, 'evidence': candidate['evidence']}
        test.assertIn(label, g.governed_decisions(notes, fields, {key: stored}), notes)


def _supported(test, notes, label, pick, text=None):
    fields = clinic_form()
    answer = adopt(notes, {label: [pick]}, fields)[label]
    test.assertEqual((answer['status'], answer['text']), ('supported', text or pick), (notes, answer.get('held_candidate')))
    key = next(f['key'] for f in fields if f['label'] == label)
    test.assertEqual(g.governed_decisions(notes, fields, {key: {**answer, 'reviewed': True}}), [], notes)


@override_settings(**DEFAULT)
class MustStayHeld(SimpleTestCase):
    """The counterexamples the trace named, and the shapes the earlier refuters tried against round 5's readings: held,
    as on the base."""

    def test_a_repeated_word_beside_a_stop_a_change_a_number_or_a_time(self):
        for first, second, label, pick in (
                ('Warfarin 5 mg daily.', 'Warfarin was stopped yesterday.', 'Medications', 'Warfarin 5 mg daily.'),
                ('The patient takes warfarin 5 mg.', 'Warfarin was stopped yesterday.', 'Medications',
                 'The patient takes warfarin 5 mg.'),
                ('The patient takes warfarin.', 'Warfarin is paused.', 'Medications', 'The patient takes warfarin.'),
                ('The patient takes warfarin.', 'Warfarin is withheld.', 'Medications', 'The patient takes warfarin.'),
                ('The patient takes warfarin 5 mg.', 'Warfarin 10 mg is administered by staff.', 'Medications',
                 'The patient takes warfarin 5 mg.'),
                ('Warfarin is administered by staff.', 'The patient takes warfarin 10 mg.', 'Medications',
                 'Warfarin is administered by staff.'),
                ('The patient takes warfarin.', 'Apixaban is given instead of warfarin.', 'Medications',
                 'The patient takes warfarin.'),
                ('Warfarin was stopped last week.', 'The patient takes warfarin.', 'Medications',
                 'The patient takes warfarin.'),
                ('Warfarin is given by staff on alternate days.', 'The patient takes warfarin.', 'Medications',
                 'The patient takes warfarin.'),
                # a repeated word beside a number, an adjective or a time
                ('The patient takes warfarin 5 mg.', 'Warfarin is administered by staff.', 'Medications',
                 'The patient takes warfarin 5 mg.'),
                ('The patient takes warfarin.', 'Warfarin is given by staff in reduced doses.', 'Medications',
                 'The patient takes warfarin.'),
                ('Warfarin is administered by staff.', 'The patient takes warfarin 10 mg.', 'Medications',
                 'The patient takes warfarin 10 mg.'),
                ('The patient takes warfarin.', 'Warfarin is administered by staff at night.', 'Medications',
                 'The patient takes warfarin.'),
                ('The patient takes warfarin.', 'Warfarin is given by staff in small doses.', 'Medications',
                 'The patient takes warfarin.'),
                # a repeated word beside a line with a frame of its own
                ('Warfarin was stopped last week.', 'The patient has taken warfarin during this reporting period.',
                 'Medications', 'The patient has taken warfarin during this reporting period.')):
            for gap in GAPS:
                with self.subTest(notes=first + gap + second):
                    _held(self, first + gap + second, label, pick)

    def test_a_family_history_before_a_person_less_sentence(self):
        for first, second in (('The patient reports that her mother has diabetes.', 'Insulin was started last year.'),
                              ('Her mother has diabetes.', 'Insulin was started.'),
                              ('Family history: mother has diabetes.', 'Insulin is administered by staff.'),
                              ('The patient lives with her mother.', 'Insulin is administered by staff.')):
            for gap in GAPS:
                with self.subTest(notes=first + gap + second):
                    _held(self, first + gap + second, 'Medications', second)

    def test_an_earlier_past_event_before_a_line_with_no_frame_of_its_own(self):
        for second in ('Examination is normal.', 'Examination at that visit was normal.'):
            for gap in GAPS:
                with self.subTest(notes=second, gap=gap):
                    _held(self, 'The patient was seen in A&E yesterday.' + gap + second, 'Examination', second)
        # a frame pointing back ('that visit') is not the line's own
        second = 'No new rash has appeared during that visit.'
        for gap in GAPS:
            with self.subTest(notes=second, gap=gap):
                _held(self, 'The patient was seen in A&E yesterday.' + gap + second, 'History of present illness', second)

    def test_a_past_event_never_answers_a_question_about_now(self):
        # (the earlier refuters' rows CL3, Z3/F4a, F4ctl-now)
        for label, quote in (('Does a Community Treatment Order (CTO) currently apply to this person?',
                              'The tribunal placed the patient on a community treatment order.'),
                             ('Is the patient subject to a community treatment order?',
                              'The tribunal placed the patient on a community treatment order last year.'),
                             ('Is the patient currently subject to a community treatment order?',
                              'The tribunal placed the patient on a community treatment order last year.')):
            fields = [field('v3_1', label), field('v3_2', 'Plan')]
            for f in fields:
                f['context'] = 'Community care review'
            answer = adopt(quote, {label: [quote]}, fields)[label]
            with self.subTest(label=label):
                self.assertNotEqual(answer['status'], 'supported', answer)

    def test_a_clause_about_another_person_an_animal_or_a_name(self):
        # a person the lexicons miss, a person named, an animal, a name
        for first, second, label in (
                ('The patient presents with cough.', 'The clinical supervisor attends the clinic weekly.', 'Plan'),
                ('The patient presents with cough.', 'The patient advocate attends weekly.', 'Plan'),
                ('The patient presents with itching.', 'The dog itches.', 'History of present illness'),
                ('The patient presents with cough.', 'Her father saw the patient yesterday.', 'History of present illness'),
                ('The patient presents with cough.', 'The neighbour feeds the patient daily.', 'Plan'),
                ('The patient presents with cough.', 'The nurse injects the patient with insulin.', 'Medications'),
                ('The patient presents with itching.', 'Spot itches.', 'History of present illness')):
            for gap in (' ', '\n\n'):
                with self.subTest(notes=first + gap + second):
                    _held(self, first + gap + second, label, second)
        # a bare noun alone (a name the lexicon may know), and a person word in the subject's phrase
        _held(self, 'Spot itches.', 'History of present illness', 'Spot itches.')
        _held(self, 'Pain radiates to the arm.', 'History of present illness', 'Pain radiates to the arm.')
        _held(self, 'The staff room provides privacy.', 'Plan', 'The staff room provides privacy.')
        _held(self, 'The nurse residence provides privacy.', 'Plan', 'The nurse residence provides privacy.')


@override_settings(**DEFAULT)
class OwnFrameAndPlainPairHoldAsOnTheBase(SimpleTestCase):
    """Refutation round 6 (L1:F1, L1:F2, L2:F1, L2:F2): round 5's two releases of rules (a)/(b) are withdrawn. Every row
    the refuters adopted on c6b9b492's default path, and round 5's own release controls, are held - as on the base."""

    def test_a_this_frame_does_not_lift_an_earlier_past_event(self):
        for first, second, label in (
                ('The patient was admitted to hospital in 2019.',
                 'The patient was started on warfarin during this admission.', 'Medications'),
                ('The patient was seen in A&E on 3 March.', 'The knee is swollen at this visit.', 'Examination'),
                ('The patient was seen in A&E yesterday.', 'The knee is swollen at this visit.', 'Examination'),
                ('The patient attended the fracture clinic in 2019.', 'The knee is swollen at this appointment.',
                 'Examination'),
                ('The patient was reviewed in the anticoagulation clinic last year.',
                 'The patient takes warfarin at this review.', 'Medications'),
                ('The patient was admitted with pneumonia last week.',
                 'No new illness has appeared during this reporting period.', 'History of present illness'),
                ('The patient was admitted with a fractured wrist last week.',
                 'No injury has occurred during this reporting period.', 'History of present illness'),
                ('The patient was seen in A&E yesterday.', 'Examination is normal today.', 'Examination'),
                ('The patient was seen in A&E yesterday.', 'No rash has appeared during this reporting period.',
                 'History of present illness')):
            for gap in GAPS:
                with self.subTest(notes=first + gap + second):
                    _held(self, first + gap + second, label, second)
        notes = ('A 45-year-old woman presents for review.\n\nThe patient was diagnosed with type 2 diabetes yesterday.'
                 '\n\nThe patient has no medical conditions at present.')
        for gap in GAPS:
            with self.subTest(notes='OF3', gap=gap):
                _held(self, notes.replace('\n\n', gap), 'Past medical history',
                      'The patient has no medical conditions at present.')

    def test_a_repeated_word_joins_two_lines_whatever_their_words(self):
        for notes, pick in (
                ('The patient takes warfarin.\n\nThe warfarin is recorded for discontinuation.',
                 'The patient takes warfarin.'),
                ('The patient takes warfarin.\n\nThe warfarin is prescribed for withdrawal.', 'The patient takes warfarin.'),
                ('The patient takes warfarin.\n\nThe warfarin is prescribed for the dog.', 'The patient takes warfarin.'),
                ('The patient takes warfarin.\n\nThe warfarin is prescribed for the prisoner.',
                 'The patient takes warfarin.'),
                ('The patient takes the tablets.\n\nThe tablets are prescribed for the cat.',
                 'The patient takes the tablets.'),
                ('The warfarin is prescribed for the dog.\n\nThe patient takes warfarin.', 'The patient takes warfarin.'),
                ('The patient presents for review.\n\nThe patient takes warfarin.\n\nThe warfarin is prescribed for the '
                 'dog.', 'The patient takes warfarin.'),
                ('Warfarin is administered by staff.\n\nThe patient takes warfarin.\n\nThe staff record the refusal of '
                 'the warfarin.', 'The patient takes warfarin.'),
                ('A 45-year-old woman presents for review.\n\nWarfarin is administered by staff.\n\nThe patient takes '
                 'warfarin.\n\nThe staff record the refusal of the warfarin.', 'The patient takes warfarin.'),
                # round 5's own release controls: held, as on the base
                ('The patient takes warfarin.\n\nThe warfarin is administered by staff.', 'The patient takes warfarin.'),
                ('Warfarin is administered by staff.\n\nThe patient takes warfarin.', 'Warfarin is administered by staff.')):
            for gap in GAPS:
                with self.subTest(notes=notes, gap=gap):
                    _held(self, notes.replace('\n\n', gap), 'Medications', pick)

    def test_d30_with_a_contradicting_line(self):
        fields = d30_fields()
        a46 = 'The prescribed medication is administered by residence staff and each administered dose is recorded.'
        a48 = V3_48_QUOTE
        a50 = 'No new physical illness has affected treatment attendance during this reporting period.'
        q46 = next(row['label'] for row in FIXTURE['cases'] if row['key'] == 'v3_46')
        q50 = next(row['label'] for row in FIXTURE['cases'] if row['key'] == 'v3_50')
        self.assertEqual(FIXTURE['notes'].count(a46), 1)
        self.assertEqual(FIXTURE['notes'].count(a50), 1)
        rows = []
        for stop in ('The patient stopped taking the prescribed medication last month.',
                     'The patient refused the prescribed medication last week.',
                     'The patient missed several doses last week.'):
            rows.append((FIXTURE['notes'].replace(a46, stop), {V3_48: [a48]}, (V3_48,)))
        rows.append((FIXTURE['notes'].replace(a50, 'The patient was admitted to hospital with pneumonia and missed every '
                                                    'clinic appointment.\n\n' + a50), {q50: [a50]}, (q50,)))
        rows.append((FIXTURE['notes'].replace(a48, a48 + '\n\nThe staff record the refusal of each prescribed dose.'),
                     {q46: [a46], V3_48: [a48]}, (q46, V3_48)))
        rows.append((FIXTURE['notes'] + '\n\nThe residence records the discontinuation of the prescribed medication.',
                     {q46: [a46], V3_48: [a48]}, (q46, V3_48)))
        rows.append((FIXTURE['notes'].replace(a46, 'The residence records the cessation of the prescribed medication.\n\n'
                                              + a46), {q46: [a46], V3_48: [a48]}, (q46, V3_48)))
        for notes, picks, targets in rows:
            for gap in GAPS:
                variant = notes.replace('\n\n', gap)
                out = adopt(variant, picks, fields)
                for label in targets:
                    with self.subTest(notes=variant[-160:], label=label[:40], gap=gap):
                        self.assertEqual(out[label]['status'], 'conflict', out[label])


@override_settings(**DEFAULT)
class SyntaxOnlyHoldsAsOnTheBase(SimpleTestCase):
    """Refutation round 6: a sentence lacking the finite-word proof stays a fragment, as on the base - this round's first
    refuter's rows and round 5's own release controls (v3_21's and v3_53's shapes) alike."""

    def test_a_thing_subject_or_the_patient_as_object_is_not_completed_by_the_parser(self):
        for quote, label in (
                ('The warfarin belongs to the dog.', 'Medications'),
                ('The warfarin goes to the dog.', 'Medications'),
                ('The tablets belong to the dog.', 'Medications'),
                ('The inhaler belongs to the inmate.', 'Medications'),
                ('The rash belongs to the dog.', 'Examination'),
                ('The cough affects the dog.', 'History of present illness'),
                ('The warfarin starts next week.', 'Medications'),
                ('The apixaban replaces the warfarin.', 'Medications'),
                ('The apixaban replaces the warfarin next week.', 'Medications'),
                ('The insulin begins in January.', 'Medications'),
                ('The physiotherapy ended last year.', 'Plan'),
                ('The amitriptyline ended in 2019.', 'Plan'),
                ('The physiotherapist saw the patient last year.', 'Plan'),
                ('The surgeon reviewed the patient in 2019.', 'Plan'),
                ('The headache woke the patient in 2019.', 'Chief complaint'),
                # round 5's own release controls
                ('The current supported residence provides staff supervision.', 'Plan'),
                ('The spot itches.', 'History of present illness'),
                ('The pain radiates to the arm.', 'History of present illness'),
                ('The headache wakes the patient at night.', 'History of present illness')):
            for notes in (quote, 'The patient presents with right knee pain.\n\n' + quote):
                with self.subTest(notes=notes, label=label):
                    _held(self, notes, label, quote)
        label = 'When was the patient last seen by a clinical professional?'
        fields = [field('v3_1', label)]
        quote = 'The clinical supervisor saw the patient at the community clinic on 20 September 2026.'
        self.assertEqual(adopt(quote, {label: [quote]}, fields)[label]['status'], 'conflict')
