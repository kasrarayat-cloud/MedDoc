"""Ordinary notes on the DEFAULT path, refutation round 5 (2026-10-01): the D30 ordinary case's held answers.

The workflow stream traced the D30 ordinary note's seven held answers to the hold rules (d30-holds-findings.json): six
unjustified, one appropriate. Three readings release five of them, each read POSITIVELY from the source and closed by
lists that only hold when a word is missing (`v3_actors._plain`, `OWN_FRAME`, `_patient_object`, `_thing_subject`):

  - a sentence lacking the finite-word proof is complete by the parser's whole-clause check when its verb takes the
    explicit patient as its object or its subject positively names no person - SYNTAX ONLY, never who it is about
    (v3_21, v3_53);
  - a line stating its own present frame ('during this reporting period') is not framed by an earlier past event
    (v3_50);
  - a core word repeated across a blank line joins nothing when both lines are plain (v3_46, v3_48).

The one appropriate hold (v3_25, another person) stays, and so does v3_24: a later line about other people repeats its
core word and the note named the patient's family just before it, two holds only meaning could lift. Every
must-stay-held counterexample the trace named is held: a stop, a change, a number or a time beside a repeated word; a
family history before a person-less sentence; an earlier past event before a line with no frame of its own."""
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
    def test_five_unjustified_holds_are_answered_and_two_stay_held(self):
        fields = d30_fields()
        picks = {row['label']: [row['quote']] for row in FIXTURE['cases']}
        picks[V3_48] = [V3_48_QUOTE]
        out = adopt(FIXTURE['notes'], picks, fields)
        quotes = {row['label']: row['quote'] for row in FIXTURE['cases']}
        quotes[V3_48] = V3_48_QUOTE
        by_key = {f['label']: f['key'] for f in fields}
        supported = {}
        for row in FIXTURE['cases'] + [{'key': 'v3_48', 'label': V3_48}]:
            label = row['label']; answer = out[label]
            with self.subTest(key=row['key']):
                if row['key'] in ('v3_24', 'v3_25'):
                    self.assertEqual(answer['status'], 'conflict', answer)
                else:
                    # each recovered answer is exactly its own source sentence
                    self.assertEqual((answer['status'], answer['text']), ('supported', quotes[label]), answer)
                    supported[by_key[label]] = answer
        # the page and finalization read the same: nothing recovered is refused, nothing shown held
        self.assertEqual(g.governed_decisions(FIXTURE['notes'], fields, supported), [])
        governance = g.governance_for(FIXTURE['notes'], fields)
        for f in fields:
            if f['key'] in supported:
                row = g.as_currently_governed(governance, FIXTURE['notes'], {**f, **supported[f['key']]})
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
    """The counterexamples the trace named, and the shapes of each new reading a refuter would try first."""

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
                # a plain line beside an answer that is not plain itself (a number), and an adjective that may change it
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
                # an own frame lifts an earlier past event, never a repeated word
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

    def test_a_past_event_never_answers_a_question_about_now_by_the_parser(self):
        # (the earlier refuters' rows CL3, Z3/F4a, F4ctl-now) the parser completes a past clause only for a question
        # that asks about the past ('When was the patient last seen ...'), never for one about what is so now
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

    def test_the_parser_completes_syntax_only(self):
        # a person the lexicons miss, a person named, an animal, a name: the clause is whole, the actor still holds
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
        # a bare noun alone: no determiner, so not positively a thing (a name the lexicon knows)
        _held(self, 'Spot itches.', 'History of present illness', 'Spot itches.')
        _held(self, 'Pain radiates to the arm.', 'History of present illness', 'Pain radiates to the arm.')
        # a person word anywhere in the subject's phrase: not positively a thing
        _held(self, 'The staff room provides privacy.', 'Plan', 'The staff room provides privacy.')
        _held(self, 'The nurse residence provides privacy.', 'Plan', 'The nurse residence provides privacy.')


@override_settings(**DEFAULT)
class TheReadingsRelease(SimpleTestCase):
    """Each reading's own control, outside D30's note."""

    def test_an_own_present_frame_after_an_earlier_past_event(self):
        for second, label, text in (('Examination is normal today.', 'Examination', 'normal today.'),
                                    ('No rash has appeared during this reporting period.', 'History of present illness',
                                     None)):
            _supported(self, 'The patient was seen in A&E yesterday.\n\n' + second, label, second, text)

    def test_two_plain_lines_repeating_one_word(self):
        _supported(self, 'Warfarin is administered by staff.\n\nThe patient takes warfarin.', 'Medications',
                   'Warfarin is administered by staff.')

    def test_a_whole_clause_about_a_thing_or_the_patient_seen(self):
        _supported(self, 'The current supported residence provides staff supervision.', 'Plan',
                   'The current supported residence provides staff supervision.')
        _supported(self, 'The spot itches.', 'History of present illness', 'The spot itches.')
        _supported(self, 'The pain radiates to the arm.', 'History of present illness', 'The pain radiates to the arm.')
        _supported(self, 'The headache wakes the patient at night.', 'History of present illness',
                   'The headache wakes the patient at night.')
        label = 'When was the patient last seen by a clinical professional?'
        fields = [field('v3_1', label)]
        quote = 'The clinical supervisor saw the patient at the community clinic on 20 September 2026.'
        answer = adopt(quote, {label: [quote]}, fields)[label]
        self.assertEqual((answer['status'], answer['text']), ('supported', quote), answer)
