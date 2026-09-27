"""Ordinary (unlabelled) typed or dictated notes on a contract v3 Word form: synthetic notes, no provider requests.

The provider's choice is simulated by unit selections, exactly the shape the live complete-sentence contract returns.
What is asserted is what the application does with it: complete source sentences are adopted, options are filled
only from their own labelled statement, and governance, fragments and corrections are held, never discarded.
"""
import time
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core import generation as g


def field(key, label, kind='text', options=None):
    f = {'key': key, 'label': label, 'kind': kind, 'context': '',
         'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[%d]' % len(key),
                     'target': {'type': 'span', 'start': 0, 'end': 0, 'shape': 'after_label'}, 'fingerprint': '0' * 64}}
    if options is not None:
        f['options'] = options
    return f


FIELDS = [field('v3_1', 'Chief complaint'), field('v3_2', 'Allergies'), field('v3_3', 'Plan', 'long_text'),
          field('v3_4', 'Smoker', 'choice', ['Yes', 'No']), field('v3_5', 'Consent obtained', 'checkbox', ['Consent obtained']),
          field('v3_6', 'Clinician signature', 'signature')]


def run(notes, picks, conflicts=(), fields=None):
    """Simulate the provider selecting unit ids per label, then validate and adopt as the application does."""
    fields = FIELDS if fields is None else fields
    asked, context, v3_fields = g.v3_generation_fields(fields)
    units, _ = g.source_units(notes, asked, context_labels=context)
    by_quote = {u['quote']: u['id'] for u in units}
    selections = g.UnitSelections(fields=[
        g.UnitSelection(key=f['key'], unit_ids=[by_quote[q] for q in picks.get(f['label'], [])],
                        conflict=f['label'] in conflicts) for f in asked])
    selections = g.unit_selections(notes, asked, selections, context_labels=context)
    answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
    adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
    return {f['label']: adopted[f['key']] for f in fields}


class OrdinaryNotesOnV3Forms(SimpleTestCase):
    def test_prose_notes_are_adopted_as_complete_sentences_not_returned_as_conflicts(self):
        notes = ('Patient presents with right knee pain for three weeks. Allergies: penicillin. '
                 'Plan is physiotherapy twice weekly and review in six weeks.')
        out = run(notes, {'Chief complaint': ['Patient presents with right knee pain for three weeks.'],
                          'Allergies': ['Allergies: penicillin.'],
                          'Plan': ['Plan is physiotherapy twice weekly and review in six weeks.']})
        self.assertEqual(out['Chief complaint']['status'], 'supported')
        self.assertEqual(out['Chief complaint']['text'], 'Patient presents with right knee pain for three weeks.')
        self.assertEqual(out['Allergies']['text'], 'penicillin.')
        self.assertEqual(out['Plan']['status'], 'supported')

    def test_an_option_is_filled_only_from_its_own_labelled_line(self):
        notes = 'Smoker: No.\nThe patient drinks socially.'
        out = run(notes, {'Smoker': ['Smoker: No.']})
        self.assertEqual(out['Smoker']['text'], 'No')
        self.assertEqual(out['Smoker']['status'], 'supported')

    def test_a_line_that_begins_with_a_form_label_is_one_unit_and_its_answer_is_the_rest_of_the_line(self):
        """R2/R3: split into sentences, the labelled sentence alone ticked the box and dropped what followed it."""
        for notes in ('Consent obtained: yes. To be obtained tomorrow.',
                      'Consent obtained: yes. Patient withdrew consent before the procedure.'):
            units, _ = g.source_units(notes, g.v3_generation_fields(FIELDS)[0], context_labels=['Clinician signature'])
            self.assertEqual([u['quote'] for u in units], [notes])
            consent = run(notes, {'Consent obtained': [notes]})['Consent obtained']
            self.assertEqual((consent['status'], consent['text']), ('conflict', ''), notes)
            self.assertEqual(consent['held_candidate']['text'], notes.split(': ', 1)[1], notes)
        for notes in ('Smoker: Yes. Quit in 2015.', 'Smoker: No. The patient drinks socially.', 'Smoker: Yes. Corrected to no.'):
            smoker = run(notes, {'Smoker': [notes]})['Smoker']
            self.assertEqual((smoker['status'], smoker['text']), ('conflict', ''), notes)
            self.assertEqual(smoker['held_candidate']['text'], notes.split(': ', 1)[1], notes)
        notes = 'Allergies: penicillin. Sorry, I mean amoxicillin.'
        allergies = run(notes, {'Allergies': [notes]})['Allergies']
        self.assertEqual(allergies['text'], 'penicillin. Sorry, I mean amoxicillin.', 'the whole remainder, never penicillin alone')
        self.assertEqual(allergies['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}])

    def test_an_option_is_never_read_from_a_labelled_sentence_inside_another_line(self):
        """R2: the complete-sentence clause read 'Smoker: yes.' out of a line about the patient's father."""
        for notes in ('Father: MI at 50. Smoker: yes.', 'Family hx: father had an MI. Smoker: yes.',
                      'Seen today. Consent obtained: yes.'):
            label = 'Smoker' if 'Smoker' in notes else 'Consent obtained'
            quote = notes[notes.index(label):]
            answer = run(notes, {label: [quote]})[label]
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''), notes)
            self.assertEqual(answer['held_candidate']['evidence'][0]['quote'], quote, notes)
        # A line of its own still names its option.
        self.assertEqual(run('Father: MI at 50.\nSmoker: yes.', {'Smoker': ['Smoker: yes.']})['Smoker']['text'], 'Yes')

    def test_an_unlabelled_sentence_never_becomes_an_option(self):
        notes = 'The patient does not smoke. Allergies: none known.'
        out = run(notes, {'Smoker': ['The patient does not smoke.']})
        self.assertNotEqual(out['Smoker']['status'], 'supported')
        self.assertEqual(out['Smoker']['text'], '')

    def test_a_negated_or_qualified_value_is_not_an_option(self):
        for notes in ('Smoker: no longer.', 'Smoker: not yes.', 'Smoker: No, former smoker.'):
            out = run(notes, {'Smoker': [notes]})
            self.assertEqual(out['Smoker']['text'], '', notes)

    def test_a_labelled_option_under_a_governing_line_is_held_not_filled(self):
        for notes in ('If symptoms recur:\nSmoker: yes.', 'Family history:\nSmoker: yes.',
                      'Denies the following:\nSmoker: yes.'):
            out = run(notes, {'Smoker': ['Smoker: yes.']})
            self.assertNotEqual(out['Smoker']['status'], 'supported', notes)
            self.assertEqual(out['Smoker']['text'], '', notes)

    def test_only_one_closing_full_stop_is_removed_from_an_option_value(self):
        """R1: a question mark, an exclamation mark or an ellipsis is part of the value; it names no option."""
        for notes in ('Smoker: yes?', 'Smoker: no?', 'Smoker: Yes?!', 'Smoker: Yes!', 'Smoker: No...', 'Smoker: No..'):
            smoker = run(notes, {'Smoker': [notes]})['Smoker']
            self.assertEqual((smoker['status'], smoker['text']), ('conflict', ''), notes)
            self.assertEqual(smoker['held_candidate']['text'], notes.split(': ', 1)[1], notes)
        for notes in ('Consent obtained: yes?', 'Consent obtained: present?', 'Consent obtained: yes...'):
            consent = run(notes, {'Consent obtained': [notes]})['Consent obtained']
            self.assertEqual((consent['status'], consent['text']), ('conflict', ''), notes)
        for notes, text in (('Smoker: No.', 'No'), ('Smoker: yes', 'Yes'), ('Smoker: Yes .', 'Yes')):
            self.assertEqual(run(notes, {'Smoker': [notes]})['Smoker']['text'], text, notes)
        self.assertEqual(run('Consent obtained: yes.', {'Consent obtained': ['Consent obtained: yes.']})
                         ['Consent obtained']['text'], 'checked')

    def test_a_labelled_value_that_only_points_elsewhere_is_held_never_adopted(self):
        """R4: 'Findings: as follows.' was adopted as the findings; the findings it introduced were not."""
        fields = FIELDS + [field('v3_7', 'Findings', 'long_text')]
        for line in ('Findings: as follows.', 'Findings: as follows', 'Findings: see below.', 'Findings: As below!',
                     'Findings: listed below.', 'Findings: below.', 'Findings: the following.', 'Findings: as listed;'):
            notes = line + '\nEffusion is present.\nNo fracture is seen.'
            findings = run(notes, {'Findings': [line]}, fields=fields)['Findings']
            self.assertEqual((findings['status'], findings['text']), ('conflict', ''), line)
            self.assertEqual((findings.get('own_evidence') or findings['evidence'])[0]['quote'], line, line)
        for notes in ('Plan: as follows.\nIce and rest.', 'Plan: see below.'):
            line = notes.split('\n')[0]
            self.assertEqual(run(notes, {'Plan': [line]})['Plan']['status'], 'conflict', notes)
        notes = 'Findings: small effusion is present.'
        self.assertEqual(run(notes, {'Findings': [notes]}, fields=fields)['Findings']['text'], 'small effusion is present.')

    def test_a_unit_the_notes_label_as_another_questions_answer_is_held_not_a_failed_job(self):
        """R6: selecting it raised, and the whole job failed with every other answer."""
        fields = FIELDS + [field('v3_7', 'Findings', 'long_text'), field('v3_8', 'Impression'),
                           field('v3_9', 'History'), field('v3_10', 'Past medical history', 'long_text')]
        cases = (('Findings are consistent with a medial meniscus tear.', 'Impression'),
                 ('History is significant for diabetes and hypertension.', 'Past medical history'),
                 ('Allergies: penicillin. Plan is rest.', 'Plan'))
        for notes, label in cases:
            out = run(notes, {label: [notes], 'Chief complaint': []}, fields=fields)
            answer = out[label]
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''), notes)
            self.assertEqual(answer['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}], notes)
        # An unknown unit is still a provider error.
        asked, context, _ = g.v3_generation_fields(fields)
        selections = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=[7] if f['label'] == 'Impression' else [],
                                                              conflict=False) for f in asked])
        with self.assertRaisesMessage(g.ValidationError, 'unknown source evidence unit'):
            g.unit_selections('Findings are normal.', asked, selections, context_labels=context)

    def test_a_checkbox_is_ticked_only_by_an_explicit_yes(self):
        self.assertEqual(run('Consent obtained: yes.', {'Consent obtained': ['Consent obtained: yes.']})
                         ['Consent obtained']['text'], 'checked')
        self.assertEqual(run('Consent obtained: verbal.', {'Consent obtained': ['Consent obtained: verbal.']})
                         ['Consent obtained']['text'], '')

    def test_a_verbless_fragment_is_held_not_adopted(self):
        out = run('Right knee. Allergies: none.', {'Chief complaint': ['Right knee.']})
        self.assertNotEqual(out['Chief complaint']['status'], 'supported')

    def test_a_denial_heading_governs_what_follows_and_is_held(self):
        notes = 'Denies the following:\nChest pain.\nShortness of breath.'
        out = run(notes, {'Chief complaint': ['Chest pain.']})
        self.assertNotEqual(out['Chief complaint']['status'], 'supported')

    def test_a_statement_repeated_into_numbered_looking_labels_is_held_not_a_failed_job(self):
        fields = [field('v3_a', 'Visit — 1'), field('v3_b', 'Visit — 2')]
        notes = 'The wound is healing well.'
        units, _ = g.source_units(notes, fields)
        selections = g.UnitSelections(fields=[g.UnitSelection(key='v3_a', unit_ids=[units[0]['id']], conflict=False),
                                              g.UnitSelection(key='v3_b', unit_ids=[units[0]['id']], conflict=False)])
        answers = g.validate_selections(notes, fields, selections, evidence_contract=g.TAB_CONTRACT)
        self.assertEqual({a['status'] for a in answers.values()} - {'supported'}, {'conflict'})

    def test_signature_is_never_generated(self):
        out = run('Clinician signature: Dr Example.', {})
        self.assertEqual(out['Clinician signature']['text'], '')

    @override_settings(QUILLMD_AI_MODE='fixture')
    def test_non_v3_forms_keep_the_labelled_contract(self):
        legacy = [{'key': 'q1', 'label': 'Allergies', 'locator': {'table': 0, 'row': 0, 'col': 1}}]
        self.assertFalse(g.natural_v3(legacy))
        self.assertFalse(g.tab_evidence_contract(legacy))
        self.assertTrue(g.natural_v3(FIELDS))


class OneReadingPerUnit(SimpleTestCase):
    """R7: each unit is read once per validation, never once per question (a pure caching change)."""

    def test_a_hundred_questions_over_999_units_read_each_unit_once(self):
        fields = [field('v3_%d' % i, 'Pain %d' % i) for i in range(100)]
        notes = ' '.join('Pain is %d.' % i for i in range(999))
        units, _ = g.source_units(notes, fields)
        self.assertEqual(len(units), 999)
        selections = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=[units[0]['id']] if i == 0 else [],
                                                              conflict=False) for i, f in enumerate(fields)])
        real, calls = g.tab_source_value, []

        def counted(*args):
            calls.append(1)
            return real(*args)

        with patch.object(g, 'tab_source_value', side_effect=counted):
            started = time.monotonic()
            answers = g.validate_selections(notes, fields, selections, evidence_contract=g.TAB_CONTRACT)
            elapsed = time.monotonic() - started
        self.assertEqual(len(calls), len(units), 'one reading per unit, however many questions the form asks')
        self.assertLess(elapsed, 2.0)
        self.assertEqual(answers['v3_0']['text'], 'Pain is 0.')


GOVERNED_NOTES = (
    'Plan: rest. Allergies: none.\nAllergies: correction, penicillin.',
    'Plan: rest and ice. Allergies: none known.\nAllergies: correction, penicillin.',
    'Chief complaint: knee pain. Findings: as follows.\nEffusion is present.',
    'Allergies: none.\nSmoker: yes.\nCorrection: former smoker.',
    'Review of systems: negative for the following:\nChest pain.\nAllergies: none.',
    'Patient presents with knee pain. The patient denies the following.\nChest pain.\nPlan: rest.',
    'Chief complaint: knee pain.\nAllergies: penicillin.\nPlan: ice. Smoker: no.',
)


class OneGovernanceReader(SimpleTestCase):
    """R9: v3 generation reads governance exactly as the page, save and finalization do."""

    fields = FIELDS + [field('v3_7', 'Findings', 'long_text')]

    def test_nothing_generation_adopts_or_offers_is_refused_at_finalization_for_governance(self):
        config = {**g.configuration(), 'mode': 'fixture'}
        for notes in GOVERNED_NOTES:
            answers = g.generate(notes, self.fields, config)[0]
            accepted = {key: ({**answer, 'text': answer['suggestion'], 'status': 'edited', 'accepted_suggestion': True}
                              if answer.get('suggestion') else answer) for key, answer in answers.items()}
            self.assertEqual(g.governed_decisions(notes, self.fields, accepted), [], notes)
            governance = g.governance_for(notes, self.fields)
            for f in self.fields:
                self.assertIsNone(g.governed_supported(governance, notes, answers[f['key']], f['label']), (notes, f['label']))

    def test_the_correction_line_holds_what_it_may_correct(self):
        notes = GOVERNED_NOTES[0]
        answers = g.generate(notes, self.fields, {**g.configuration(), 'mode': 'fixture'})[0]
        by_label = {f['label']: answers[f['key']] for f in self.fields}
        self.assertEqual(by_label['Plan']['status'], 'conflict')
        self.assertEqual(by_label['Plan']['held_candidate']['text'], 'rest. Allergies: none.')
        self.assertNotEqual(by_label['Allergies']['status'], 'supported')

    def test_generation_reads_the_same_governance_the_page_reads(self):
        asked, context, _ = g.v3_generation_fields(self.fields)
        for notes in GOVERNED_NOTES:
            self.assertEqual(g.governance_for(notes, asked, context), g.governance_for(notes, self.fields), notes)


class ScopeInOrdinarySentences(SimpleTestCase):
    """R12: scope words and quotations hold a whole v3 note only from a heading-like line; complete statements."""

    fields = FIELDS + [field('v3_7', 'Family history', 'long_text'), field('v3_8', 'Social history')]

    def test_a_scope_word_in_an_ordinary_sentence_holds_only_that_sentence_when_selected(self):
        base = 'Patient presents with right knee pain for three weeks. Plan is physiotherapy twice weekly.'
        for extra in (' Return if symptoms worsen.', ' Swelling is noted below the knee.', ' He might need surgery.',
                      ' These symptoms are worse at night.', ' "It gives way," he says.',
                      ' He takes no medications other than those listed.', ' His family history is noncontributory.'):
            notes = base + extra
            units, inherited = g.source_units(notes, g.v3_generation_fields(self.fields)[0])
            self.assertFalse(inherited, extra)
            out = run(notes, {'Chief complaint': ['Patient presents with right knee pain for three weeks.'],
                              'Plan': ['Plan is physiotherapy twice weekly.', extra.strip()]}, fields=self.fields)
            self.assertEqual(out['Chief complaint']['status'], 'supported', extra)
            self.assertEqual(out['Plan']['status'], 'conflict', extra)
            self.assertEqual(run(notes, {'Plan': ['Plan is physiotherapy twice weekly.']}, fields=self.fields)
                             ['Plan']['status'], 'supported', extra)
        held = run('Plan: physiotherapy if pain persists.', {'Plan': ['Plan: physiotherapy if pain persists.']})['Plan']
        self.assertEqual((held['status'], held['text']), ('conflict', ''))
        notes = 'Family history: father had an MI at 50.'
        self.assertEqual(run(notes, {'Family history': [notes]}, fields=self.fields)['Family history']['text'],
                         'father had an MI at 50.', "the form's own label is not a scope word in its answer")

    def test_a_heading_like_line_still_holds_the_whole_note(self):
        for notes in ('Family history:\nFather had an MI.', 'If symptoms recur:\nPatient presents with knee pain.',
                      'The following were denied\nPatient presents with knee pain.', 'Hypothetical case for teaching'):
            _, inherited = g.source_units(notes, g.v3_generation_fields(self.fields)[0])
            self.assertTrue(inherited, notes)

    def test_a_complete_statement_needs_a_listed_verb_or_four_words_and_a_closing_mark(self):
        for label, sentence in (('Chief complaint', 'He fell from a ladder yesterday and hurt his left wrist.'),
                                ('Allergies', 'She developed a rash after amoxicillin.'),
                                ('Social history', 'She smokes ten cigarettes a day.'),
                                ('Chief complaint', 'Mother brings in her son with ear pain.'),
                                ('Allergies', 'No known drug allergies.')):
            answer = run(sentence, {label: [sentence]}, fields=self.fields)[label]
            self.assertEqual((answer['status'], answer['text']), ('supported', sentence), sentence)
        for label, fragment in (('Allergies', 'NKDA.'), ('Chief complaint', 'Right knee.'),
                                ('Chief complaint', 'Follow-up for hypertension.'),
                                ('Chief complaint', 'Knee pain after a fall')):
            answer = run(fragment, {label: [fragment]}, fields=self.fields)[label]
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''), fragment)
