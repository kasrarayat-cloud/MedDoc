"""Ordinary (unlabelled) typed or dictated notes on a contract v3 Word form: synthetic notes, no provider requests.

The provider's choice is simulated by unit selections, exactly the shape the live complete-sentence contract returns.
What is asserted is what the application does with it: complete source sentences are adopted, options are filled
only from their own labelled statement, and governance, fragments and corrections are held, never discarded.
"""
import random
import re
import time
from unittest.mock import patch

import json
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from core.models import Encounter, Job, Reservation
from .test_word_v3_workflow import V3, V3EncounterFixture


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
        # Round 3 (R3-1/R3-2): each statement in its own paragraph. Written as one paragraph, the 'Plan is ...' sentence
        # is an ordinary sentence that may change the two before it, and the sentence before it may change it: all held.
        picks = {'Chief complaint': ['Patient presents with right knee pain for three weeks.'],
                 'Allergies': ['Allergies: penicillin.'], 'Plan': ['Plan is physiotherapy twice weekly and review in six weeks.']}
        notes = ('Patient presents with right knee pain for three weeks.\n\nAllergies: penicillin.\n\n'
                 'Plan is physiotherapy twice weekly and review in six weeks.')
        out = run(notes, picks)
        self.assertEqual(out['Chief complaint']['status'], 'supported')
        self.assertEqual(out['Chief complaint']['text'], 'Patient presents with right knee pain for three weeks.')
        self.assertEqual(out['Allergies']['text'], 'penicillin.')
        self.assertEqual(out['Plan']['status'], 'supported')
        out = run(notes.replace('\n\n', ' '), picks)
        self.assertEqual({label: out[label]['status'] for label in picks}, dict.fromkeys(picks, 'conflict'))

    def test_an_option_is_filled_only_from_its_own_labelled_line(self):
        notes = 'Smoker: No.\n\nThe patient drinks socially.'
        out = run(notes, {'Smoker': ['Smoker: No.']})
        self.assertEqual(out['Smoker']['text'], 'No')
        self.assertEqual(out['Smoker']['status'], 'supported')
        # Round 2 (F2): the next line of its paragraph may change it ('I mean yes.'), so there it is held.
        smoker = run('Smoker: No.\nThe patient drinks socially.', {'Smoker': ['Smoker: No.']})['Smoker']
        self.assertEqual((smoker['status'], smoker['text'], smoker['held_candidate']['text']), ('conflict', '', 'No.'))

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
        # Round 2 (F2): a value of more than one sentence is held, never adopted; the candidate is the whole remainder.
        self.assertEqual((allergies['status'], allergies['text']), ('conflict', ''))
        self.assertEqual(allergies['held_candidate']['text'], 'penicillin. Sorry, I mean amoxicillin.',
                         'the whole remainder, never penicillin alone')
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
        # Alone on its line it is still HELD, never offered for one click (F8: without R4's list 'as listed;' was offered,
        # the note-wide scope word making it a suggestion rather than a hold).
        for line in ('Findings: as follows.', 'Findings: see below.', 'Findings: listed below.', 'Findings: as listed;'):
            findings = run(line, {'Findings': [line]}, fields=fields)['Findings']
            self.assertEqual((findings['status'], findings['text'], findings.get('suggestion')), ('conflict', '', None), line)
            self.assertEqual(findings['held_candidate']['text'], line.split(': ', 1)[1], line)
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
        # Round 2 (F2): the next sentence of its paragraph may change it, so it is held with its candidate.
        self.assertEqual((answers['v3_0']['status'], answers['v3_0']['held_candidate']['text']), ('conflict', 'Pain is 0.'))


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
        # Round 2 (F5): 'Plan: rest.' is its own unit (the line's next form label starts another); it is still held,
        # because the correction line governs the whole line as the page and finalization read it.
        self.assertEqual(by_label['Plan']['held_candidate']['text'], 'rest.')
        self.assertTrue(by_label['Plan']['held_candidate']['context'])
        self.assertNotEqual(by_label['Allergies']['status'], 'supported')

    def test_generation_reads_the_same_governance_the_page_reads(self):
        asked, context, _ = g.v3_generation_fields(self.fields)
        for notes in GOVERNED_NOTES:
            self.assertEqual(g.governance_for(notes, asked, context), g.governance_for(notes, self.fields), notes)


class ScopeInOrdinarySentences(SimpleTestCase):
    """R12 WITHDRAWN (round 2, F1/F3): contract v3 reads scope note-wide and completeness by the verb list, exactly as
    the tab contract does. Reading scope only from heading-like lines, and 'four words and a closing mark' as complete,
    adopted denied, conditional and other people's findings as `supported`."""

    fields = FIELDS + [field('v3_7', 'Family history', 'long_text'), field('v3_8', 'Social history')]

    def test_a_scope_word_or_a_quotation_anywhere_holds_every_answer_in_the_note(self):
        base = 'Patient presents with right knee pain for three weeks. Plan is physiotherapy twice weekly.'
        for extra in (' Return if symptoms worsen.', ' Swelling is noted below the knee.', ' He might need surgery.',
                      ' These symptoms are worse at night.', ' "It gives way," he says.',
                      ' He takes no medications other than those listed.', ' His family history is noncontributory.'):
            notes = base + extra
            with self.subTest(extra=extra):
                units, inherited = g.source_units(notes, g.v3_generation_fields(self.fields)[0])
                self.assertTrue(inherited)
                out = run(notes, {'Chief complaint': ['Patient presents with right knee pain for three weeks.'],
                                  'Plan': ['Plan is physiotherapy twice weekly.']}, fields=self.fields)
                for label in ('Chief complaint', 'Plan'):
                    self.assertEqual((out[label]['status'], out[label]['text']), ('conflict', ''), label)
        held = run('Plan: physiotherapy if pain persists.', {'Plan': ['Plan: physiotherapy if pain persists.']})['Plan']
        self.assertEqual((held['status'], held['text']), ('conflict', ''))
        notes = 'Family history: father had an MI at 50.'
        held = run(notes, {'Family history': [notes]}, fields=self.fields)['Family history']
        self.assertEqual((held['status'], held['text']), ('conflict', ''), "the tab contract reads the label's words too")
        self.assertEqual(held['held_candidate']['text'], 'father had an MI at 50.')

    def test_a_heading_like_line_still_holds_the_whole_note(self):
        for notes in ('Family history:\nFather had an MI.', 'If symptoms recur:\nPatient presents with knee pain.',
                      'The following were denied\nPatient presents with knee pain.', 'Hypothetical case for teaching'):
            _, inherited = g.source_units(notes, g.v3_generation_fields(self.fields)[0])
            self.assertTrue(inherited, notes)

    def test_a_complete_statement_needs_a_listed_verb(self):
        for label, sentence in (('Chief complaint', 'Patient presents with right knee pain for three weeks.'),
                                ('Allergies', 'She reported a rash after amoxicillin.'),
                                ('Social history', 'She has smoked ten cigarettes a day for years.')):
            answer = run(sentence, {label: [sentence]}, fields=self.fields)[label]
            self.assertEqual((answer['status'], answer['text']), ('supported', sentence), sentence)
        # No verb from the list: held with the candidate, never adopted, however many words and whatever it closes with.
        for label, fragment in (('Chief complaint', 'He fell from a ladder yesterday and hurt his left wrist.'),
                                ('Allergies', 'She developed a rash after amoxicillin.'),
                                ('Social history', 'She smokes ten cigarettes a day.'),
                                ('Chief complaint', 'Mother brings in her son with ear pain.'),
                                ('Allergies', 'No known drug allergies.'), ('Allergies', 'NKDA.'),
                                ('Chief complaint', 'Right knee.'), ('Chief complaint', 'Follow-up for hypertension.'),
                                ('Chief complaint', 'Knee pain after a fall')):
            answer = run(fragment, {label: [fragment]}, fields=self.fields)[label]
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''), fragment)
            self.assertEqual(answer['held_candidate']['text'], fragment, fragment)


def live_config(**extra):
    return {**g.configuration(), 'mode': 'live', 'provider': 'anthropic', 'model': 'synthetic-no-network',
            'input_rate': '3', 'output_rate': '15', 'cached_rate': '0.3', **extra}


def sent_request(notes, fields, config):
    """generate() against a patched Anthropic client that records the request and stops before any response."""
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        raise RuntimeError('stop before any request')

    with patch('anthropic.Anthropic') as client:
        client.return_value.messages.create.side_effect = create
        try:
            g.generate(notes, fields, config)
        except RuntimeError:
            pass
    return sent


class QueuedContractAttribution(SimpleTestCase):
    """R10: a v3 job runs under the evidence contract its quoted configuration names."""

    def test_the_current_configuration_names_the_complete_sentence_contract(self):
        self.assertEqual(g.configuration()['v3_evidence_contract'], 'natural-v1')

    def test_a_v3_job_quoted_before_the_contract_existed_is_sent_the_labelled_line_request(self):
        config = {k: v for k, v in live_config().items() if k != 'v3_evidence_contract'}
        sent = sent_request('Patient seen today.\nSmoker: yes', FIELDS, config)
        payload = json.loads(sent['messages'][0]['content'])
        self.assertNotIn('source_units', payload)
        self.assertIn('Selection', sent['output_config']['format']['schema']['$defs'])
        self.assertNotIn('UnitSelection', sent['output_config']['format']['schema']['$defs'])
        self.assertTrue(sent['system'].startswith('Map source documentation to questions.'))
        fixture = g.generate('Patient seen today.\nSmoker: yes', FIELDS, {**config, 'mode': 'fixture'})[0]
        smoker = fixture['v3_4']
        self.assertEqual((smoker['status'], smoker['text'], smoker.get('suggestion')), ('conflict', '', 'Yes'),
                         'the labelled-line contract holds an answer beside an unlabelled line, as it was quoted')

    def test_a_v3_job_quoted_under_the_contract_is_sent_the_complete_sentence_request(self):
        sent = sent_request('Patient seen today.\nSmoker: yes', FIELDS, live_config())
        self.assertIn('source_units', json.loads(sent['messages'][0]['content']))
        self.assertIn('UnitSelection', sent['output_config']['format']['schema']['$defs'])
        fixture = g.generate('Patient seen today.\nSmoker: yes', FIELDS, {**live_config(), 'mode': 'fixture'})[0]
        self.assertEqual((fixture['v3_4']['status'], fixture['v3_4']['text']), ('supported', 'Yes'))
        # Round 2 (F2): above an unlabelled line of its paragraph the labelled answer is held under this contract too.
        fixture = g.generate('Smoker: yes\nPatient seen today.', FIELDS, {**live_config(), 'mode': 'fixture'})[0]
        self.assertEqual((fixture['v3_4']['status'], fixture['v3_4']['text']), ('conflict', ''))


@override_settings(**V3)
class EnqueuedContractAttribution(V3EncounterFixture, TestCase):
    """R10 through the worker: enqueue snapshots the quoted contract; the job runs as it was quoted."""

    def run_generation(self, notes, config=None):
        from core.jobs import enqueue, run_one
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        saved = self.client.post(f"/encounters/{encounter.pk}/notes/", {"revision": encounter.revision, "notes": notes})
        self.assertEqual(saved.status_code, 302)
        job = enqueue(Encounter.objects.get(pk=encounter.pk), self.user, config=config)
        self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        return job, Encounter.objects.get(pk=encounter.pk).answers[self.key('Smoker?')]

    def test_a_new_job_records_the_contract_it_runs_under(self):
        job, smoker = self.run_generation('Patient seen today.\nSmoker: yes')
        self.assertEqual(job.config['v3_evidence_contract'], 'natural-v1')
        self.assertEqual((smoker['status'], smoker['text']), ('supported', 'Yes'))

    def test_a_job_queued_before_the_contract_existed_runs_as_it_was_quoted(self):
        quoted = {k: v for k, v in g.configuration().items() if k != 'v3_evidence_contract'}
        job, smoker = self.run_generation('Patient seen today.\nSmoker: yes', config=quoted)
        self.assertNotIn('v3_evidence_contract', job.config)
        self.assertEqual((smoker['status'], smoker['text'], smoker.get('suggestion')), ('conflict', '', 'Yes'))


LARGE_NOTES = (
    ('short', 'Patient presents with knee pain. Allergies: none.'),
    ('prose-50k', ('The patient reports mild knee pain after walking today. ' * 1000)[:49990]),
    ('prose-990-units', 'Pain is 1. ' * 990),
    ('lines-999', '\n'.join('Pain is %d.' % i for i in range(999))),
    ('cjk-999', '\n'.join(['\u60a3\u8005\u306f\u819d\u306e\u75db\u307f\u3092\u8a34\u3048\u3066\u3044\u307e\u3059\u3002'] * 999)),
)
TEN = [field('v3_%d' % i, 'Question %d' % i) for i in range(1, 11)] + [field('v3_s', 'Clinician signature', 'signature')]


class CostBoundCoversTheRequest(SimpleTestCase):
    """R5: a v3 job is held for the bytes its request carries, and too many units are refused before any hold."""

    def test_the_bytes_sent_never_exceed_the_bytes_held_for(self):
        config = live_config(input_rate='1', output_rate='1', cached_rate='0.1')
        for name, notes in LARGE_NOTES:
            sent = sent_request(notes, TEN, config)
            sent_bytes = (len(sent['system'].encode()) + len(sent['messages'][0]['content'].encode())
                          + len(json.dumps(sent['output_config']).encode()))
            held_bytes = (g.maximum_cost(notes, TEN, config) - g.Decimal(6000) / 1000000) * 1000000
            self.assertIn('source_units', json.loads(sent['messages'][0]['content']), name)
            self.assertLessEqual(sent_bytes / held_bytes, 1, name)

    def test_more_than_a_thousand_units_or_a_hundred_questions_are_refused_at_the_quote(self):
        config = live_config()
        with self.assertRaisesMessage(g.ValidationError, '1,000 complete statements'):
            g.maximum_cost(' '.join(['Okay.'] * 1001), TEN, config)
        many = [field('v3_%d' % i, 'Question %d' % i) for i in range(101)]
        with self.assertRaisesMessage(g.ValidationError, 'supported limits'):
            g.maximum_cost('Patient seen.', many, config)


LIVE = dict(V3, QUILLMD_AI_MODE='live', AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='synthetic-no-network',
            AI_INPUT_RATE='3', AI_OUTPUT_RATE='15', AI_CACHED_RATE='0.3')


@override_settings(**LIVE)
class NothingStrandsAHold(V3EncounterFixture, TestCase):
    """R5/R8 through enqueue and the worker, live mode, the provider client patched and never reached."""

    def save_notes(self, notes):
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        saved = self.client.post(f"/encounters/{encounter.pk}/notes/", {"revision": encounter.revision, "notes": notes})
        self.assertEqual(saved.status_code, 302)

    def test_a_note_of_more_than_a_thousand_units_is_refused_at_enqueue_before_any_hold(self):
        from core.jobs import enqueue
        self.save_notes('Referring physician: Dr Example\n' + ' '.join(['Okay.'] * 1001))
        with patch('anthropic.Anthropic') as client:
            with self.assertRaisesMessage(g.ValidationError, '1,000 complete statements'):
                enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            self.assertFalse(client.return_value.messages.create.called)
        self.assertFalse(Job.objects.filter(encounter=self.encounter).exists())
        self.assertFalse(Reservation.objects.exists())

    def assert_not_processed_and_released(self, job, client):
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertIn('held funds were released', job.error)
        self.assertFalse(client.return_value.messages.create.called)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['released'])

    def test_a_refusal_after_the_hold_ends_not_processed_with_the_hold_released(self):
        from core.jobs import enqueue, run_one
        self.save_notes('Referring physician: Dr Example\nPatient seen today.')
        job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['held'])
        refusal = g.ValidationError('Source exceeds 1,000 complete statements; split explicitly. Nothing was truncated.')
        with patch('anthropic.Anthropic') as client, patch.object(g, 'source_units', side_effect=refusal):
            self.assertTrue(run_one())
        self.assert_not_processed_and_released(job, client)
        self.assertIn('1,000 complete statements', job.error)

    def test_a_client_that_cannot_be_built_ends_not_processed_with_the_hold_released(self):
        from core.jobs import enqueue, run_one
        self.save_notes('Referring physician: Dr Example')
        job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
        with patch('anthropic.Anthropic', side_effect=RuntimeError('client could not be built')) as client:
            self.assertTrue(run_one())
        self.assert_not_processed_and_released(job, client)


def unit_response(payload, picks, request_id='synthetic-no-provider'):
    """A synthetic completed provider response selecting source units BY THEIR QUOTE from the request it was sent."""
    by_quote = {unit['quote']: unit['id'] for unit in payload['source_units']}
    body = {'fields': [{'key': q['key'], 'unit_ids': [by_quote[quote] for quote in picks.get(q['label'], [])],
                        'conflict': False} for q in payload['questions']]}
    return SimpleNamespace(id='msg_' + request_id, _request_id=request_id, stop_reason='end_turn',
                           usage=SimpleNamespace(input_tokens=100, output_tokens=10, cache_read_input_tokens=0,
                                                 cache_creation_input_tokens=0),
                           content=[SimpleNamespace(type='text', text=json.dumps(body))],
                           model_dump=lambda **kwargs: {'id': 'msg_' + request_id})


class LiveCompleteSentencePath(SimpleTestCase):
    """R11: the live path for a v3 form, the Anthropic client patched: what is sent, and what is adopted from the reply."""

    # Round 3 (R3-1/R3-2): the 'Plan is ...' sentence in its own paragraph; in the same paragraph it holds every answer
    # above it (it is not a plain value) and is held by the line before it.
    notes = ('Patient presents with right knee pain for three weeks.\nAllergies: penicillin.\nSmoker: No.\n\n'
             'Plan is physiotherapy twice weekly and review in six weeks.')
    picks = {'Chief complaint': ['Patient presents with right knee pain for three weeks.'],
             'Allergies': ['Allergies: penicillin.'], 'Smoker': ['Smoker: No.'],
             'Plan': ['Plan is physiotherapy twice weekly and review in six weeks.']}

    def test_a_v3_form_is_sent_source_units_and_the_unit_schema_and_its_selections_are_adopted(self):
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = (
                lambda **kwargs: unit_response(json.loads(kwargs['messages'][0]['content']), self.picks))
            raw, *_ = g.generate(self.notes, FIELDS, live_config())
            sent = client.return_value.messages.create.call_args.kwargs
        asked, context, _ = g.v3_generation_fields(FIELDS)
        payload = json.loads(sent['messages'][0]['content'])
        self.assertEqual(payload['source_units'], g.source_units(self.notes, asked, context_labels=context)[0])
        self.assertEqual(sent['output_config']['format']['schema'], g.UnitSelections.model_json_schema())
        self.assertTrue(sent['system'].startswith('Map the complete source documentation to the approved form questions.'))
        self.assertNotIn('options', json.dumps(payload))
        self.assertEqual(raw['evidence_contract'], g.TAB_CONTRACT)
        answers = {f['label']: g.validated(raw)[f['key']] for f in FIELDS}
        self.assertEqual((answers['Chief complaint']['status'], answers['Chief complaint']['text']),
                         ('supported', 'Patient presents with right knee pain for three weeks.'))
        self.assertEqual(answers['Allergies']['text'], 'penicillin.')
        self.assertEqual((answers['Smoker']['status'], answers['Smoker']['text']), ('supported', 'No'))
        self.assertEqual(answers['Plan']['text'], 'physiotherapy twice weekly and review in six weeks.',
                         "'Plan is ...' names its question as the tab form reads it: the label is removed")
        self.assertEqual(answers['Clinician signature']['status'], 'missing')


@override_settings(**LIVE)
class LiveCompleteSentenceWorker(V3EncounterFixture, TestCase):
    """R11 through enqueue and the worker, live mode: the patched client is sent units and its selections are adopted."""

    def test_the_worker_adopts_a_live_unit_selection_for_a_v3_form(self):
        from core.jobs import enqueue, run_one
        # Round 2 (F2): each answer's paragraph neighbour after it is another labelled line, and the unlabelled sentence
        # opens its paragraph (in the earlier order both the physician and the reason were held).
        notes = 'Patient presents with right knee pain.\nReferring physician: Dr Example\nSmoker: yes'
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/notes/",
                                          {"revision": encounter.revision, "notes": notes}).status_code, 302)
        picks = {'Referring physician': ['Referring physician: Dr Example'], 'Smoker?': ['Smoker: yes'],
                 'Reason for visit': ['Patient presents with right knee pain.']}
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = (
                lambda **kwargs: unit_response(json.loads(kwargs['messages'][0]['content']), picks))
            job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            self.assertTrue(run_one())
            sent = client.return_value.messages.create.call_args.kwargs
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(job.config['v3_evidence_contract'], 'natural-v1')
        self.assertIn('source_units', json.loads(sent['messages'][0]['content']))
        answers = Encounter.objects.get(pk=self.encounter.pk).answers
        self.assertEqual(answers[self.key('Referring physician')]['text'], 'Dr Example')
        self.assertEqual(answers[self.key('Reason for visit')]['text'], 'Patient presents with right knee pain.')
        self.assertEqual((answers[self.key('Smoker?')]['status'], answers[self.key('Smoker?')]['text']), ('supported', 'Yes'))
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['settled'])


# Round-2 refutation of 2ecf3f75: the refuter's own inputs, the provider simulated by unit selection exactly as `run`
# does. Each input adopted a clinically wrong or ungoverned statement as `supported` (or, F4/F5, could never fill).
# Where the finding quoted '…' the missing line is reconstructed as the finding's sibling input ('Fever and night
# sweats.'); 'I mean no.' completes 'I mean no…'.
REFUTED = FIELDS + [field('v3_7', 'Findings', 'long_text'), field('v3_8', 'Medications', 'long_text'),
                    field('v3_9', 'Past medical history', 'long_text'), field('v3_10', 'Review of systems', 'long_text')]


class RoundTwoRefutation(SimpleTestCase):
    """A hold keeps the candidate and its own source for the clinician; nothing below may be adopted as `supported`."""

    def held(self, notes, label, quote, candidate, fields=REFUTED):
        answer = run(notes, {label: [quote]}, fields=fields)[label]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), notes)
        kept = answer.get('held_candidate') or {}
        self.assertEqual(kept.get('text'), candidate, notes)
        self.assertEqual([entry['quote'] for entry in kept.get('evidence', [])], [quote], notes)
        return answer

    def test_f1_a_denial_pointer_conditional_or_attribution_holds_what_it_governs(self):
        for notes, label, quote in (
                ('Findings: none of the following were seen.\nPolyp in the sigmoid colon.\nMass in the rectum.',
                 'Findings', 'Polyp in the sigmoid colon.'),
                ('The patient denies all of the following symptoms today.\nChest pain on exertion.\nFever and night sweats.',
                 'Chief complaint', 'Chest pain on exertion.'),
                ('Review of systems is negative for the following items today.\nChest pain on exertion.\n'
                 'Fever and night sweats.', 'Chief complaint', 'Chest pain on exertion.'),
                ('Fever, chills and night sweats. All of these were denied.', 'Chief complaint', 'Fever, chills and night sweats.'),
                ('If the wound looks infected at review, start cephalexin. Cephalexin 500 mg four times daily for seven days.',
                 'Plan', 'Cephalexin 500 mg four times daily for seven days.'),
                ('Family history is significant for her father. He had a myocardial infarction at age 50 and has diabetes.',
                 'Past medical history', 'He had a myocardial infarction at age 50 and has diabetes.')):
            with self.subTest(notes=notes):
                self.held(notes, label, quote, quote)

    def test_f2_a_correction_after_a_labelled_value_or_sentence_holds_it(self):
        for notes, label, quote, candidate in (
                ('Allergies: penicillin.\nSorry, I mean amoxicillin.', 'Allergies', 'Allergies: penicillin.', 'penicillin.'),
                ('Consent obtained: yes.\nTo be obtained tomorrow.', 'Consent obtained', 'Consent obtained: yes.', 'yes.'),
                ('Consent obtained: yes.\nPatient withdrew consent before the procedure.', 'Consent obtained',
                 'Consent obtained: yes.', 'yes.'),
                ('Seen today. Allergies: penicillin. Sorry, I mean amoxicillin.', 'Allergies', 'Allergies: penicillin.',
                 'penicillin.'),
                ('Allergies are penicillin. Sorry, I mean amoxicillin.', 'Allergies', 'Allergies are penicillin.', 'penicillin.'),
                ('Plan is to start lisinopril 10 mg daily. Sorry, I mean amlodipine 5 mg daily.', 'Plan',
                 'Plan is to start lisinopril 10 mg daily.', 'to start lisinopril 10 mg daily.'),
                ('Medications: warfarin 5 mg daily.\nActually, warfarin was stopped last month.', 'Medications',
                 'Medications: warfarin 5 mg daily.', 'warfarin 5 mg daily.'),
                ('Smoker: yes.\nI mean no.', 'Smoker', 'Smoker: yes.', 'yes.')):
            with self.subTest(notes=notes):
                self.held(notes, label, quote, candidate)

    def test_f3_a_fragment_whose_predicate_is_the_next_sentence_is_held(self):
        for notes, label, quote in (
                ('Warfarin 5 mg daily. Stopped last month.', 'Medications', 'Warfarin 5 mg daily.'),
                ('Mass in the right breast. Ruled out on ultrasound.', 'Findings', 'Mass in the right breast.'),
                ('Chest pain on exertion and palpitations. All denied.', 'Chief complaint',
                 'Chest pain on exertion and palpitations.'),
                ('Polyp in the sigmoid colon. Not seen on this examination.', 'Findings', 'Polyp in the sigmoid colon.'),
                ('History of type 2 diabetes. In her sister, not the patient.', 'Past medical history',
                 'History of type 2 diabetes.'),
                ('Nausea, vomiting or abdominal pain? None.', 'Review of systems', 'Nausea, vomiting or abdominal pain?')):
            with self.subTest(notes=notes):
                self.held(notes, label, quote, quote)

    def test_the_paragraph_rule_holds_by_structure_not_by_words(self):
        """Not the refuter's inputs: the F1-F3 shapes with no scope word, correction word or verbless fragment for a list
        to find. The paragraph rule holds them by position alone."""
        for notes, label, quote in (
                ('Her father has heart disease. He had a myocardial infarction at age 50 and has diabetes.',
                 'Past medical history', 'He had a myocardial infarction at age 50 and has diabetes.'),
                ('Warfarin 5 mg daily. Stopped last month.', 'Medications', 'Stopped last month.'),
                ('Warfarin 5 mg daily. stopped last month.', 'Medications', 'Warfarin 5 mg daily. stopped last month.'),
                ('Does she have chest pain?', 'Chief complaint', 'Does she have chest pain?')):
            with self.subTest(notes=notes):
                self.held(notes, label, quote, quote)
        # What the rule reads as a boundary: another question's labelled value, a blank line, the end of the note.
        out = run('Chest pain on exertion is present.\nAllergies: penicillin.\n\nThe patient is well today.',
                  {'Chief complaint': ['Chest pain on exertion is present.'], 'Allergies': ['Allergies: penicillin.'],
                   'Plan': ['The patient is well today.']}, fields=REFUTED)
        self.assertEqual({label: out[label]['status'] for label in ('Chief complaint', 'Allergies', 'Plan')},
                         {'Chief complaint': 'supported', 'Allergies': 'supported', 'Plan': 'supported'})

    def test_a_correction_anywhere_later_in_its_paragraph_holds_it(self):
        """Not the refuter's inputs: the F2 shape one labelled value further on, and a paragraph 'ended' by breaks the page
        may show inline. Only a blank line of spaces, tabs or carriage returns between two line feeds ends a paragraph."""
        for notes, label, quote, candidate in (
                ('Smoker: yes. Allergies: none. Sorry, smoker is no.', 'Smoker', 'Smoker: yes.', 'yes.'),
                ('Smoker: yes.\nAllergies: none.\nSorry, I meant smoker no.', 'Smoker', 'Smoker: yes.', 'yes.'),
                ('Allergies: penicillin.\u2028\u2028Sorry, I mean amoxicillin.', 'Allergies', 'Allergies: penicillin.',
                 'penicillin.'),
                ('Allergies: penicillin.\n\u2028\nSorry, I mean amoxicillin.', 'Allergies', 'Allergies: penicillin.',
                 'penicillin.'),
                ('Allergies: penicillin.\n\x0c\nSorry, I mean amoxicillin.', 'Allergies', 'Allergies: penicillin.',
                 'penicillin.')):
            with self.subTest(notes=notes):
                self.held(notes, label, quote, candidate)
        # A blank line written with spaces, tabs or CRLF still ends it.
        for gap in ('\n\n', '\n \t\n', '\r\n\r\n'):
            notes = 'Allergies: penicillin.' + gap + 'The patient is well today.'
            self.assertEqual(run(notes, {'Allergies': ['Allergies: penicillin.']})['Allergies']['text'], 'penicillin.', gap)

    def test_a_self_correction_inside_one_sentence_holds_it(self):
        """Not the refuter's inputs: 'a correction inside the same line must still hold' when it is inside one sentence,
        where no structure can see it. A short list of self-correction phrases that only ever HOLDS."""
        for notes, label in (('Allergies: penicillin, sorry, I mean amoxicillin.', 'Allergies'),
                             ('Medications: warfarin 5 mg daily, actually stopped last month.', 'Medications'),
                             ('Smoker: yes (scratch that, no).', 'Smoker'),
                             ('Plan: start lisinopril, or rather amlodipine, 5 mg daily.', 'Plan'),
                             ('Allergies: penicillin \u2014 no wait, amoxicillin.', 'Allergies')):
            with self.subTest(notes=notes):
                self.held(notes, label, notes, notes.split(': ', 1)[1])

    def test_f4_an_option_printed_with_a_closing_full_stop_is_named_by_its_value(self):
        form = [field('v3_r', 'Right impression', 'choice', ['reflux positive.', 'is absent.']),
                field('v3_s', 'Smoker', 'choice', ['Yes.', 'No.'])]
        for notes, label, option in (('Right impression: reflux positive.', 'Right impression', 'reflux positive.'),
                                     ('Smoker: No.', 'Smoker', 'No.'), ('Smoker: No', 'Smoker', 'No.')):
            with self.subTest(notes=notes):
                answer = run(notes, {label: [notes]}, fields=form)[label]
                self.assertEqual((answer['status'], answer['text']), ('supported', option), notes)
        # At most one closing stop from EACH side, never more: a doubled or trailing-off stop names no option.
        for notes, label in (('Smoker: No..', 'Smoker'), ('Smoker: No...', 'Smoker'),
                             ('Right impression: reflux positive..', 'Right impression')):
            with self.subTest(notes=notes):
                answer = run(notes, {label: [notes]}, fields=form)[label]
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''), notes)
                self.assertEqual(answer['held_candidate']['text'], notes.split(': ', 1)[1], notes)
        # The same reading wherever an option value is judged: directly, and on the labelled-line contract a job quoted
        # before the complete-sentence contract runs under (there nothing else holds 'No..' first).
        self.assertEqual([g.named_option(['Yes.', 'No.'], value) for value in ('No', 'No.', ' no. ', 'No..', 'No...')],
                         ['No.', 'No.', 'No.', None, None])
        self.assertEqual(g.named_option(['Yes', 'No'], 'No.'), 'No')
        quoted = {k: v for k, v in g.configuration().items() if k != 'v3_evidence_contract'}
        for notes, expected in (('Smoker: No.', ('supported', 'No.')), ('Smoker: No..', ('conflict', ''))):
            smoker = g.generate(notes, form, {**quoted, 'mode': 'fixture'})[0]['v3_s']
            self.assertEqual((smoker['status'], smoker['text']), expected, notes)
        # Two printed options that read alike are not named by either reading.
        both = [field('v3_s', 'Smoker', 'choice', ['No', 'No.'])]
        self.assertEqual(run('Smoker: No', {'Smoker': ['Smoker: No']}, fields=both)['Smoker']['status'], 'conflict')

    def test_f5_each_form_label_on_one_line_is_its_own_unit(self):
        vitals = [field('v3_b', 'BP'), field('v3_h', 'HR'), field('v3_t', 'Temp')]
        notes = 'BP: 124/78. HR: 88. Temp: 36.9.'
        self.assertEqual([u['quote'] for u in g.source_units(notes, vitals)[0]], ['BP: 124/78.', 'HR: 88.', 'Temp: 36.9.'])
        out = run(notes, {'BP': ['BP: 124/78.'], 'HR': ['HR: 88.'], 'Temp': ['Temp: 36.9.']}, fields=vitals)
        self.assertEqual({label: (a['status'], a['text']) for label, a in out.items()},
                         {'BP': ('supported', '124/78.'), 'HR': ('supported', '88.'), 'Temp': ('supported', '36.9.')})
        notes = 'Allergies: none. Smoker: No.'
        self.assertEqual([u['quote'] for u in g.source_units(notes, g.v3_generation_fields(FIELDS)[0],
                                                               context_labels=['Clinician signature'])[0]],
                         ['Allergies: none.', 'Smoker: No.'])
        out = run(notes, {'Allergies': ['Allergies: none.'], 'Smoker': ['Smoker: No.']})
        self.assertEqual((out['Allergies']['status'], out['Allergies']['text']), ('supported', 'none.'))
        self.assertEqual((out['Smoker']['status'], out['Smoker']['text']), ('supported', 'No'))
        # Without re-opening R2/R3: a label's answer still runs to the next form label, and more than one sentence holds.
        notes = 'Allergies: none. Smoker: No. Quit in 2015.'
        smoker = run(notes, {'Smoker': ['Smoker: No. Quit in 2015.']})['Smoker']
        self.assertEqual((smoker['status'], smoker['text'], smoker['held_candidate']['text']),
                         ('conflict', '', 'No. Quit in 2015.'))

    def test_f7_a_value_or_sentence_that_only_points_elsewhere_is_held(self):
        for line in ('Findings: to follow.', 'Findings: as follows —', 'Findings: **as follows**',
                     'Findings: see next line.', 'Findings: see beneath.'):
            for notes in (line, line + '\nEffusion is present.\nNo fracture is seen.'):
                with self.subTest(notes=notes):
                    self.held(notes, 'Findings', line, line.split(': ', 1)[1])
        for notes in ('The findings are as follows.', 'The findings are as follows.\nEffusion is present.'):
            with self.subTest(notes=notes):
                self.held(notes, 'Findings', 'The findings are as follows.', 'The findings are as follows.')
        # The shape is read at the end and the start of the value, not anywhere in it.
        for notes, label, text in (('Plan: follow up in two weeks.', 'Plan', 'follow up in two weeks.'),
                                   ('Findings: effusion is seen on the lateral view.', 'Findings',
                                    'effusion is seen on the lateral view.')):
            answer = run(notes, {label: [notes]}, fields=REFUTED)[label]
            self.assertEqual((answer['status'], answer['text']), ('supported', text), notes)


@override_settings(**LIVE)
class RoundTwoThroughTheWorker(V3EncounterFixture, TestCase):
    """F1 through enqueue and the worker, live mode, the Anthropic client patched: the stored answer is held."""

    def test_a_denied_symptom_is_never_stored_as_the_reason_for_visit(self):
        from core.jobs import enqueue, run_one
        notes = 'The patient denies all of the following symptoms today.\nChest pain on exertion.\nFever and night sweats.'
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/notes/",
                                          {"revision": encounter.revision, "notes": notes}).status_code, 302)
        picks = {'Reason for visit': ['Chest pain on exertion.']}
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = (
                lambda **kwargs: unit_response(json.loads(kwargs['messages'][0]['content']), picks))
            job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        answer = Encounter.objects.get(pk=self.encounter.pk).answers[self.key('Reason for visit')]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
        self.assertEqual(answer['held_candidate']['text'], 'Chest pain on exertion.')


class RoundTwoMutantPins(SimpleTestCase):
    """Round 2, F8: each of these mutants survived the suite. Every test here fails on its mutant (the proofs are in the
    commit that adds them); the rules they pin are the ones this release relies on."""

    def by_id(self, notes, picks, fields=REFUTED):
        """The provider selecting units BY ID (a quote that repeats is one exact occurrence)."""
        asked, context, v3_fields = g.v3_generation_fields(fields)
        selections = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=picks.get(f['label'], []),
                                                              conflict=False) for f in asked])
        answers = g.validate_selections(notes, asked, g.unit_selections(notes, asked, selections, context_labels=context),
                                        context_labels=context, evidence_contract=g.TAB_CONTRACT)
        return {f['label']: g.v3_adopted(v3_fields, answers, notes, asked, context)[f['key']] for f in fields}

    def test_r9_generation_holds_exactly_what_the_page_judges_over_every_occurrence(self):
        # Governed where the page reads it: the forward pointer governs the second line group; the repeated sentence
        # there is not a whole line, so the page's reading (line by line, R9) does not count it, and nor may generation.
        notes = 'Allergies: none.\n\nFindings are as follows.\nSeen today. Allergies: none.'
        units, inherited = g.source_units(notes, g.v3_generation_fields(REFUTED)[0], context_labels=['Clinician signature'])
        self.assertFalse(inherited)
        allergies = self.by_id(notes, {'Allergies': [units[0]['id']]})['Allergies']
        self.assertEqual((allergies['status'], allergies['text']), ('supported', 'none.'))
        governance = g.governance_for(notes, REFUTED)
        self.assertIsNone(g.governed_supported(governance, notes, allergies, 'Allergies'))
        # The refuter's probe: the occurrence after 'Denies the following.' is held, with the other place named.
        notes = 'Chest pain on exertion is present.\nSeen today. Denies the following. Chest pain on exertion is present.'
        units, _ = g.source_units(notes, g.v3_generation_fields(REFUTED)[0], context_labels=['Clinician signature'])
        for unit in (units[0], units[-1]):
            answer = self.by_id(notes, {'Chief complaint': [unit['id']]})['Chief complaint']
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''), unit)

    def test_r10_only_the_named_contract_value_selects_the_complete_sentence_request(self):
        for value in ('natural-v0', 'natural-v1 ', 'NATURAL-V1', '', None):
            with self.subTest(value=value):
                sent = sent_request('Patient seen today.\nSmoker: yes', FIELDS, live_config(v3_evidence_contract=value))
                self.assertNotIn('source_units', json.loads(sent['messages'][0]['content']))
                self.assertTrue(sent['system'].startswith('Map source documentation to questions.'))

    def test_r6_a_tab_form_selection_of_another_questions_labelled_unit_still_fails_the_job(self):
        from pathlib import Path
        from documents.engine import docx_inspect
        tab = docx_inspect(Path(__file__).resolve().parents[2] / 'documents/__fixtures__/Colonoscopy_Operative_Template.docx')[3]
        notes = 'Anesthesia: monitored anesthesia care.'
        unit = g.source_units(notes, tab)[0][0]
        selections = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=[unit['id']] if f['label'] == 'PROCEDURE'
                                                              else [], conflict=False) for f in tab])
        with self.assertRaisesMessage(g.ValidationError, 'Evidence must be a complete offered source sentence'):
            g.validate_selections(notes, tab, selections)

    def test_a_stop_inside_a_unit_is_not_a_closing_mark_and_an_abbreviation_is_not_a_stop(self):
        for notes in ('Pain in the knee. after a fall', 'Pain in the knee. after a fall.'):
            answer = run(notes, {'Chief complaint': [notes]}, fields=REFUTED)['Chief complaint']
            self.assertEqual((answer['status'], answer['text']), ('conflict', ''), notes)
        for label, notes in (('Past medical history', 'Dr. Smith has reviewed the scan.'),
                             ('Medications', 'She takes aspirin 81 mg p.o. daily.')):
            answer = run(notes, {label: [notes]}, fields=REFUTED)[label]
            self.assertEqual((answer['status'], answer['text']), ('supported', notes), notes)

    def test_a_held_candidate_shows_the_sentence_that_may_change_it(self):
        notes = 'Allergies: penicillin.\nSorry, I mean amoxicillin.'
        kept = run(notes, {'Allergies': ['Allergies: penicillin.']})['Allergies']['held_candidate']
        self.assertEqual(kept['context'], [{'quote': 'Sorry, I mean amoxicillin.', 'start': 23, 'end': 49, 'after': True,
                                            'same': False}])
        self.assertEqual(kept['reason'], g.HELD_REASON)
        notes = 'Her father has heart disease. He had a myocardial infarction at age 50.'
        kept = run(notes, {'Past medical history': ['He had a myocardial infarction at age 50.']},
                   fields=REFUTED)['Past medical history']['held_candidate']
        self.assertEqual(kept['context'], [{'quote': 'Her father has heart disease.', 'start': 0, 'end': 29, 'after': False,
                                            'same': True}])
        kept = run('Right knee.', {'Chief complaint': ['Right knee.']})['Chief complaint']['held_candidate']
        self.assertEqual((kept['context'], kept['reason']), ([], g.V3_HELD_REASON))


# Round-3 refutation of 1d66c798: the refuter's own inputs, the provider simulated by unit selection exactly as `run`
# does. Each input below was adopted as `supported` (R3-1, R3-2, R3-3), cost seconds under the row lock (R3-4, R3-5), or
# was held although it is a plain value or an instruction (R3-6). Where the finding elided text with '…', the sentence is
# completed and the completion is stated beside it.
ROUND3 = REFUTED + [field('v3_11', 'Diagnosis'), field('v3_12', 'Follow-up'), field('v3_13', 'Blood group'),
                    field('v3_14', 'Urine dipstick'), field('v3_15', 'Temperature'), field('v3_16', 'Heart rate')]


def held_with(test, notes, label, quote, candidate, fields=ROUND3):
    """A hold: nothing adopted or offered for one click, the candidate and its own source kept for the clinician."""
    answer = run(notes, {label: [quote]}, fields=fields)[label]
    test.assertEqual((answer['status'], answer['text'], answer.get('suggestion')), ('conflict', '', None), notes)
    kept = answer.get('held_candidate') or {}
    test.assertEqual(kept.get('text'), candidate, notes)
    test.assertEqual([entry['quote'] for entry in kept.get('evidence', [])], [quote], notes)
    return answer


class RoundThreeRefutation(SimpleTestCase):
    def test_r3_1_a_later_labelled_value_that_is_not_plain_holds_what_comes_before_it(self):
        """R3-1: F5 split a line wherever a form or context label begins, and the split-off tail was exempted as
        'another question's one-sentence labelled value' however much it said."""
        for notes, label, quote, candidate in (
                ('Consent obtained: yes. Plan: to be obtained tomorrow.', 'Consent obtained', 'Consent obtained: yes.', 'yes.'),
                ('Consent obtained: yes. Clinician signature: consent form not yet signed.', 'Consent obtained',
                 'Consent obtained: yes.', 'yes.'),
                ('Smoker: yes. Plan: none, he quit ten years ago.', 'Smoker', 'Smoker: yes.', 'yes.'),
                ("Allergies: none. Plan: avoid penicillin after last week's anaphylaxis.", 'Allergies', 'Allergies: none.',
                 'none.'),
                ('Temperature: 37.2. Heart rate: 104, temperature rechecked at 38.9.', 'Temperature', 'Temperature: 37.2.',
                 '37.2.')):
            with self.subTest(notes=notes):
                held_with(self, notes, label, quote, candidate)

    def test_r3_1_plain_values_after_it_still_leave_an_answer_adopted(self):
        vitals = [field('v3_b', 'BP'), field('v3_h', 'HR'), field('v3_t', 'Temp')]
        out = run('BP: 124/78. HR: 88. Temp: 36.9.', {'BP': ['BP: 124/78.'], 'HR': ['HR: 88.'], 'Temp': ['Temp: 36.9.']},
                  fields=vitals)
        self.assertEqual({label: (a['status'], a['text']) for label, a in out.items()},
                         {'BP': ('supported', '124/78.'), 'HR': ('supported', '88.'), 'Temp': ('supported', '36.9.')})
        out = run('Allergies: none. Smoker: No.', {'Allergies': ['Allergies: none.'], 'Smoker': ['Smoker: No.']})
        self.assertEqual((out['Allergies']['status'], out['Allergies']['text']), ('supported', 'none.'))
        self.assertEqual((out['Smoker']['status'], out['Smoker']['text']), ('supported', 'No'))

    def test_r3_1_the_plain_value_grammar_fails_closed(self):
        """Not the refuter's inputs: each part of the grammar, pinned by a later value only that part makes not plain."""
        for notes, label, quote in (
                ('Consent obtained: yes. Plan: not obtained.', 'Consent obtained', 'Consent obtained: yes.'),       # denial
                ('Consent obtained: yes. Plan: consent was withheld.', 'Consent obtained', 'Consent obtained: yes.'),  # verb
                ('Consent obtained: yes. Plan: surgery if needed.', 'Consent obtained', 'Consent obtained: yes.'),  # scope
                # A pointing scope word also makes the note inherited, where the answer would be OFFERED for one click:
                ('Smoker: yes. Plan: as above.', 'Smoker', 'Smoker: yes.'),                                  # scope
                ('Smoker: yes. Allergies: actually penicillin.', 'Smoker', 'Smoker: yes.'),               # self-correction
                ('Consent obtained: yes. Plan: consent tomorrow.', 'Consent obtained', 'Consent obtained: yes.'),  # unsettled
                ('Smoker: yes. Findings: details overleaf.', 'Smoker', 'Smoker: yes.'),                           # pointer
                ('Consent obtained: yes. Plan: rest.Consent Friday.', 'Consent obtained', 'Consent obtained: yes.'),  # stop
                ('Smoker: yes. Plan: rest ice elevation compression.', 'Smoker', 'Smoker: yes.'),         # four words
                ('Smoker: yes. Allergies: none, penicillin.', 'Smoker', 'Smoker: yes.'),                  # a list
                ('Smoker: yes. Allergies: penicillin, latex.', 'Smoker', 'Smoker: yes.'),                 # a list
                ('Smoker: yes. Allergies: penicillin (rash).', 'Smoker', 'Smoker: yes.'),                 # a bracket
                ('Allergies: none.\nClinician signature: Dr Example.', 'Allergies', 'Allergies: none.')):  # context label
            with self.subTest(notes=notes):
                held_with(self, notes, label, quote, quote.split(': ', 1)[1])
        # A plain 'Label is ...' value passes rule (a) like a colon-labelled one; for rule (b) it is an ordinary sentence.
        out = run('Allergies: penicillin.\nPlan is rest.', {'Allergies': ['Allergies: penicillin.'], 'Plan': ['Plan is rest.']},
                  fields=ROUND3)
        self.assertEqual((out['Allergies']['status'], out['Allergies']['text']), ('supported', 'penicillin.'))
        self.assertEqual((out['Plan']['status'], out['Plan']['held_candidate']['text']), ('conflict', 'rest.'))
        for value in ('none.', 'No', 'NKDA', '124/78.', '36.9', '104 bpm', '98%', 'A+', 'Dr Example', 'Dr. Example',
                      'knee pain.', 'left'):
            self.assertTrue(g.plain_value(value), value)
        for value in ('none, he quit ten years ago.', 'to be obtained tomorrow.', 'consent form not yet signed.', 'yes?',
                      '"yes"', 'so\u00adrry', 'a' * 121, '/', '', 'rest.Consent Friday', 'No..'):
            self.assertFalse(g.plain_value(value), value)

    def test_r3_2_a_label_is_sentence_is_an_ordinary_sentence_for_the_paragraph_rule(self):
        """R3-2: 'Plan is ...' read as a labelled value, so it neither changed what came before it nor was changed."""
        for notes, label, quote, candidate in (
                ('Consent obtained: yes.\nPlan is to proceed once consent is signed tomorrow.', 'Consent obtained',
                 'Consent obtained: yes.', 'yes.'),
                # The finding elided the dose ('Plan is amoxicillin …, as ...'); completed as '500 mg three times daily'.
                ('Allergies: penicillin.\nPlan is amoxicillin 500 mg three times daily, as the penicillin allergy was '
                 'disproven on testing last year.', 'Allergies', 'Allergies: penicillin.', 'penicillin.'),
                ('Smoker: yes.\nAllergies were reviewed today and she quit smoking in 2010.', 'Smoker', 'Smoker: yes.',
                 'yes.'),
                ('Her sister was seen in oncology last month. Diagnosis was breast cancer.', 'Diagnosis',
                 'Diagnosis was breast cancer.', 'breast cancer.')):
            with self.subTest(notes=notes):
                held_with(self, notes, label, quote, candidate)

    def test_r3_3_a_single_letter_before_a_stop_ends_a_sentence_for_a_hold(self):
        """R3-3: 'hepatitis C.' was read as an initial, so the sentence after it hid inside the unit before."""
        held_with(self, 'Smoker: yes.\nPlan: screen for hepatitis C. She is not a smoker; that was her husband.', 'Smoker',
                  'Smoker: yes.', 'yes.')
        for notes, label in (('Plan: screen for hepatitis C. She is not a smoker; that was her husband.', 'Plan'),
                             ('Medications: vitamin K. Warfarin was stopped last month.', 'Medications'),
                             # Not the refuter's: what is read through only before a lower-case word or a digit, and
                             # only after one full stop with nothing closing it.
                             ('Medications: aspirin 81 mg p.o. Stopped last month.', 'Medications'),
                             ('Medications: aspirin 81 mg p.o.) stopped last month.', 'Medications'),
                             ('Medications: aspirin etc. Stopped last month.', 'Medications'),
                             ('Plan: screen for hepatitis C. she is not a smoker.', 'Plan')):
            with self.subTest(notes=notes):
                held_with(self, notes, label, notes, notes.split(': ', 1)[1])
        # Still read through: a title, 'e.g.', and a dotted abbreviation or 'approx.' before a lower-case word or digit.
        for label, notes in (('Past medical history', 'Dr. Smith has reviewed the scan.'),
                             ('Medications', 'She takes aspirin 81 mg p.o. daily.'),
                             ('Findings', 'Effusion is present, approx. 5 mm deep.'),
                             ('Medications', 'She takes analgesics, e.g. Paracetamol, as needed.')):
            with self.subTest(notes=notes):
                answer = run(notes, {label: [notes]}, fields=ROUND3)[label]
                self.assertEqual((answer['status'], answer['text']), ('supported', notes), notes)

    def test_r3_6_a_plain_value_or_an_instruction_is_not_a_pointer(self):
        """R3-6: held although nothing in them points at other lines."""
        for notes, label, text in (('Follow-up: see in clinic in twelve months.', 'Follow-up', 'see in clinic in twelve months.'),
                                   ('Plan: see physiotherapist twice weekly for six weeks.', 'Plan',
                                    'see physiotherapist twice weekly for six weeks.'),
                                   ('Blood group: O-', 'Blood group', 'O-'), ('Blood group: O−.', 'Blood group', 'O−.'),
                                   ('Blood group: A+', 'Blood group', 'A+'),
                                   ('Urine dipstick: nitrites -', 'Urine dipstick', 'nitrites -')):
            with self.subTest(notes=notes):
                answer = run(notes, {label: [notes]}, fields=ROUND3)[label]
                self.assertEqual((answer['status'], answer['text']), ('supported', text), notes)

    def test_an_unpunctuated_run_on_unit_is_held_for_every_question(self):
        """Pre-existing, listed by the previous repair: a single-line unpunctuated dictation was adopted whole as the answer
        to every free-text question asked. More than 25 words with no sentence end is a run-on, held."""
        notes = ('patient is a fifty year old man who comes in with right knee pain for three weeks he has no allergies he '
                 'smokes ten a day and the plan is physiotherapy twice weekly and review in six weeks')
        out = run(notes, {'Chief complaint': [notes], 'Allergies': [notes], 'Plan': [notes]}, fields=ROUND3)
        for label in ('Chief complaint', 'Allergies', 'Plan'):
            with self.subTest(label=label):
                held_with(self, notes, label, notes, notes)


class RoundThreeCost(SimpleTestCase):
    """R3-4/R3-5: the refuter's inputs, bounded in time (each was seconds to minutes on 1d66c798)."""

    def test_r3_4_a_run_of_stops_is_read_in_linear_time(self):
        for count in (2000, 4000, 8000):
            started = time.monotonic()
            g.inner_sentence_end('.' * count)
            self.assertLess(time.monotonic() - started, 0.05, count)

    def test_r3_4_the_linear_pattern_reads_what_the_original_read(self):
        """The rewrite changes cost, not readings: the same `.!?…` matches (spans) and the same answer on every text,
        realistic notes and 20,000 random strings over the characters the pattern reads."""
        original = re.compile(r'[.!?\u2026]+["\'\u201d\u2019)\]]*\s+(?=\S)|[\u3002\uff0e\uff01\uff1f\uff61]+(?=\S)')
        rng = random.Random(20260927)
        alphabet = 'aB1 .!?\u2026"\')]\u3002\uff0e\uff01\uff1f\uff61\n\t'
        texts = [notes for notes, *_ in GOVERNED_NOTES] + [notes for _, notes in LARGE_NOTES] + [
            'Warfarin 5 mg daily (since May.) Stopped last month.', 'penicillin. sorry, I mean amoxicillin.',
            'She takes aspirin 81 mg p.o. daily.', 'none\u3002Sorry, smoker is no.', 'Really?! Yes... "Fine." (Ok.) Done']
        texts += [''.join(rng.choice(alphabet) for _ in range(rng.randint(0, 40))) for _ in range(20000)]
        for text in texts:
            ascii_spans = [[m.span() for m in pattern.finditer(text) if text[m.start()] in '.!?\u2026']
                           for pattern in (original, g.INNER_SENTENCE_END)]
            self.assertEqual(ascii_spans[0], ascii_spans[1], repr(text))
            self.assertEqual(bool(original.search(text)), bool(g.INNER_SENTENCE_END.search(text)), repr(text))

    def test_r3_4_an_unlabelled_unit_of_20k_stops_selected_by_three_questions(self):
        unit = 'Patient seen today' + '.' * 20000
        fields = [field('a', 'Chief complaint'), field('b', 'History'), field('c', 'Plan')]
        started = time.monotonic()
        out = run(unit, {'Chief complaint': [unit], 'History': [unit], 'Plan': [unit]}, fields=fields)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual({a['status'] for a in out.values()}, {'conflict'})

    def test_r3_4_each_unit_is_read_for_sentence_ends_once_however_many_questions_select_it(self):
        """Once per unit, shared by the paragraph rule and every question that selects the unit."""
        notes = 'Patient presents with knee pain. She reports it is worse at night.\nAllergies: penicillin.'
        fields = [field('a', 'Chief complaint'), field('b', 'History'), field('c', 'Plan'), field('d', 'Allergies')]
        real, calls = g.inner_sentence_end, []

        def counted(text):
            calls.append(text)
            return real(text)

        units, _ = g.source_units(notes, fields)
        self.assertEqual(len(units), 3)
        real_shape, shapes = g.v3_shape_holds, []

        def counted_shape(quote, value):
            shapes.append(quote)
            return real_shape(quote, value)

        with patch.object(g, 'inner_sentence_end', side_effect=counted), \
                patch.object(g, 'v3_shape_holds', side_effect=counted_shape):
            run(notes, {'Chief complaint': [units[0]['quote']], 'History': [u['quote'] for u in units[:2]],
                        'Plan': [units[1]['quote']], 'Allergies': [units[2]['quote']]}, fields=fields)
        self.assertLessEqual(len(calls), len(units), calls)
        self.assertLessEqual(len(shapes), len(units), shapes)

    def test_r3_5_a_line_of_999_labelled_segments_is_split_once(self):
        notes = ' '.join(['Q1: No.'] * 999)
        fields = [field('q', 'Q1', 'choice', ['Yes', 'No'])]
        units, _ = g.source_units(notes, fields)
        self.assertEqual(len(units), 999)
        asked, context, v3_fields = g.v3_generation_fields(fields)
        selections = g.UnitSelections(fields=[g.UnitSelection(key='q', unit_ids=[u['id'] for u in units], conflict=False)])
        answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
        real, calls = g.sentence_boundaries, []

        def counted(*args):
            calls.append(1)
            return real(*args)

        started = time.monotonic()
        with patch.object(g, 'sentence_boundaries', side_effect=counted):
            adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertLessEqual(len(calls), 1, 'one line, split once')
        self.assertEqual((adopted['q']['status'], adopted['q']['text']), ('supported', 'No'))
        # Split once for every option question of the adoption, not once per question.
        notes = ' '.join(['Q1: No. Q2: Yes.'] * 400)
        fields = [field('q', 'Q1', 'choice', ['Yes', 'No']), field('r', 'Q2', 'choice', ['Yes', 'No'])]
        asked, context, v3_fields = g.v3_generation_fields(fields)
        units, _ = g.source_units(notes, fields)
        selections = g.UnitSelections(fields=[
            g.UnitSelection(key=key, unit_ids=[u['id'] for u in units if u['quote'] == quote], conflict=False)
            for key, quote in (('q', 'Q1: No.'), ('r', 'Q2: Yes.'))])
        answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
        calls.clear()
        with patch.object(g, 'sentence_boundaries', side_effect=counted):
            adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
        self.assertLessEqual(len(calls), 1, 'one line, split once for both questions')
        self.assertEqual((adopted['q']['text'], adopted['r']['text']), ('No', 'Yes'))


@override_settings(**LIVE)
class RoundThreeThroughTheWorker(V3EncounterFixture, TestCase):
    """R3-1/R3-2/R3-4 through enqueue and the worker, live mode, the Anthropic client patched and selecting by quote."""

    def generate(self, notes, picks):
        from core.jobs import enqueue, run_one
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/notes/",
                                          {"revision": encounter.revision, "notes": notes}).status_code, 302)
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = (
                lambda **kwargs: unit_response(json.loads(kwargs['messages'][0]['content']), picks))
            job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            started = time.monotonic()
            self.assertTrue(run_one())
            elapsed = time.monotonic() - started
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        return Encounter.objects.get(pk=self.encounter.pk).answers, elapsed

    def held_option(self, notes, label, quote, other):
        answers, _ = self.generate(notes, {label: [quote], 'Reason for visit': [other]})
        answer = answers[self.key(label)]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), notes)
        self.assertEqual(answer['held_candidate']['text'], 'yes.', notes)

    def test_r3_1_a_split_off_reason_that_is_not_a_plain_value_holds_the_checkbox(self):
        self.held_option('Diabetes: yes. Reason for visit: review; diabetes was excluded on repeat HbA1c.', 'Diabetes',
                         'Diabetes: yes.', 'Reason for visit: review; diabetes was excluded on repeat HbA1c.')

    def test_r3_1_a_split_off_reason_that_is_not_a_plain_value_holds_the_choice(self):
        self.held_option('Smoker: yes. Reason for visit: cough; he quit smoking ten years ago.', 'Smoker?', 'Smoker: yes.',
                         'Reason for visit: cough; he quit smoking ten years ago.')

    def test_r3_2_a_reason_is_sentence_holds_the_checkbox_before_it(self):
        self.held_option('Diabetes: yes.\nReason for visit is review, as diabetes was excluded on repeat testing.', 'Diabetes',
                         'Diabetes: yes.', 'Reason for visit is review, as diabetes was excluded on repeat testing.')

    def test_r3_4_a_value_of_49900_stops_is_validated_in_linear_time_under_the_lock(self):
        notes = 'Reason for visit: knee pain.\nAllergies: ' + '.' * 49900
        answers, elapsed = self.generate(notes, {'Allergies': ['Allergies: ' + '.' * 49900],
                                                 'Reason for visit': ['Reason for visit: knee pain.']})
        self.assertLess(elapsed, 5.0)
        self.assertEqual(answers[self.key('Allergies')]['status'], 'conflict')
