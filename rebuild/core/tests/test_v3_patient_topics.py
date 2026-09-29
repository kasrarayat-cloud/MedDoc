"""Retained patient-context repair: complete synthetic sources, no provider calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from core.jobs import enqueue, run_one
from core.models import Encounter
from core.security import private_path
from .test_v3_ordinary_notes import LIVE, run, unit_response
from .test_v3_ordinary_input import ordinary_input_form
from .test_word_v3_workflow import V3EncounterFixture, part_text


def retained(name='r1-note4'):
    path = Path(__file__).resolve().parents[3] / 'docs/rebuild/v1/ordinary-input-20260927/evidence/known-results.json'
    return next(case for case in json.loads(path.read_text())['cases'] if case['name'] == name)


VALUES = {'Allergies': 'No known drug allergies.', 'Examination': 'Neurological examination is normal.',
          'Assessment': 'tension-type headache.',
          'Plan': 'to start amitriptyline 10 mg at night.\nShe will follow up in six weeks.'}
AUTOMATIC = {label: value for label, value in VALUES.items() if label != 'Allergies'}
#: ⚠️ DELIBERATE CHANGE 2026-09-29 (notes usefulness, G-A + G-B1): the form title is no longer read as a field
#: qualifier, and a typed unit of the complete actor ledger may be selected ALONE for its destination, so these are
#: released too (they were held with the rest of the note). Smoker (an option from prose, G-G) and Allergies (G-I) stay.
LEDGER = {'Chief complaint': 'This is a 30-year-old female seen for headaches.',
          'History of present illness': 'The headaches started two months ago and are worse in the morning.\n'
                                        'She denies visual changes, nausea, or weakness.',
          'Medications': 'She takes ibuprofen as needed.'}
RELEASED = {**AUTOMATIC, **LEDGER}


class PatientSourceTopics(SimpleTestCase):
    def test_retained_complete_note_keeps_exact_named_answers_and_unresolved_values(self):
        case = retained()
        answers = run(case['notes'], case['unchanged_picks'], fields=case['fields'])
        for label, value in RELEASED.items():
            with self.subTest(label=label):
                self.assertEqual((answers[label]['status'], answers[label]['text']), ('supported', value))
                quotes = case['unchanged_picks'][label]
                self.assertEqual(answers[label]['evidence'], [
                    {'quote': quote, 'start': case['notes'].index(quote),
                     'end': case['notes'].index(quote) + len(quote)} for quote in quotes])
                key = next(f['key'] for f in case['fields'] if f['label'] == label)
                self.assertEqual(g.governed_decisions(case['notes'], case['fields'],
                    {key: {**answers[label], 'reviewed': True}}), [])
        for label in ('Smoker', 'Allergies'):
            self.assertEqual((answers[label]['status'], answers[label]['text']), ('conflict', ''), label)

    def assert_named_hold(self, notes, labels=('Allergies', 'Examination', 'Assessment')):
        case = retained()
        answers = run(notes, {label: case['unchanged_picks'][label] for label in labels}, fields=case['fields'])
        for label in labels:
            with self.subTest(label=label, notes=notes):
                self.assertEqual((answers[label]['status'], answers[label]['text']), ('conflict', ''))
                quotes = case['unchanged_picks'][label]
                stored = {'status': 'supported', 'text': VALUES[label], 'reviewed': True,
                    'evidence': [{'quote': quote, 'start': notes.index(quote),
                                 'end': notes.index(quote) + len(quote)} for quote in quotes]}
                key = next(f['key'] for f in case['fields'] if f['label'] == label)
                reading = g.governance_for(notes, case['fields'])
                shown = g.as_currently_governed(reading, notes, {**stored, 'label': label})
                self.assertEqual((shown['status'], shown['text']), ('conflict', ''))
                self.assertIsNotNone(g.governed_supported(reading, notes, stored, label))
                self.assertEqual(g.governed_decisions(notes, case['fields'], {key: stored}), [label])

    def assert_named_released(self, notes, labels=('Examination', 'Assessment')):
        """2026-09-29: an encounter topic whose actor resolves to the patient and that nothing later LINKS to is
        released without the complete ledger; generation, page and finalization agree."""
        case = retained()
        answers = run(notes, {label: case['unchanged_picks'][label] for label in labels}, fields=case['fields'])
        for label in labels:
            with self.subTest(label=label, notes=notes):
                self.assertEqual((answers[label]['status'], answers[label]['text']), ('supported', VALUES[label]))
                key = next(f['key'] for f in case['fields'] if f['label'] == label)
                self.assertEqual(g.governed_decisions(notes, case['fields'], {key: {**answers[label], 'reviewed': True}}), [])

    def test_new_subject_or_unparsed_relationship_breaks_the_chain(self):
        notes = retained()['notes']
        for changed in (
            notes.replace('She takes ibuprofen as needed.', 'Her father is here. He takes ibuprofen as needed.'),
            notes.replace('She takes ibuprofen as needed.', 'The donor is here. She takes ibuprofen as needed.'),
            notes.replace('She takes ibuprofen as needed.', 'She takes ibuprofen for the donor.'),
            notes.replace('She takes ibuprofen as needed.', 'She takes ibuprofen as needed, according to the donor.'),
            notes.replace('She takes ibuprofen as needed.', 'She takes ibuprofen and he takes aspirin.'),
            notes.replace('She takes ibuprofen as needed.', '"She takes ibuprofen as needed," the donor said.'),
            notes.replace('in the morning.', 'in the donor.'),
        ):
            self.assert_named_hold(changed)
        # ⚠️ DELIBERATE CHANGE 2026-09-29: a LATER plan naming another person holds the plan itself (b''), not the
        # examination and assessment before it, which nothing links to it (they were held with the whole chain).
        changed = notes.replace('at night.', 'on the donor.')
        self.assert_named_hold(changed, ('Allergies',))
        self.assert_named_released(changed)
        plan = run(changed, {'Plan': ['Plan is to start amitriptyline 10 mg on the donor.', 'She will follow up in six weeks.']},
                   fields=retained()['fields'])['Plan']
        self.assertEqual((plan['status'], plan['text']), ('conflict', ''))

    def test_negation_correction_question_and_scoped_source_do_not_become_independent(self):
        notes = retained()['notes']
        for changed in (
            'Family history:\n' + notes,
            'For the donor only:\n' + notes,
            notes.replace('two months ago', 'two months ago, actually yesterday'),
            notes.replace('at night.', 'at night?'),
            notes.replace('at night.', 'at night, if symptoms continue.'),
            notes + ' Correction: the earlier answers are wrong.',
        ):
            self.assert_named_hold(changed)
        # ⚠️ DELIBERATE CHANGE 2026-09-29: an earlier DENIAL of the assessment's own word holds the assessment (an earlier
        # linked unit); the examination, which nothing links to, and the reworded denials that link to neither, no
        # longer hold them (they were held with the whole chain). Allergies (G-I) stays held throughout.
        changed = notes.replace('visual changes, nausea, or weakness', 'headaches, nausea, or weakness')
        self.assert_named_hold(changed, ('Allergies', 'Assessment'))
        self.assert_named_released(changed, ('Examination',))
        for changed in (notes.replace('visual changes, nausea, or weakness', 'visual changes or has nausea'),
                        notes.replace('visual changes, nausea, or weakness', 'visual changes, nausea, or not weakness')):
            self.assert_named_hold(changed, ('Allergies',))
            self.assert_named_released(changed)

    def test_plan_cannot_lose_its_followup_or_borrow_a_different_patient(self):
        case = retained()
        first, followup = case['unchanged_picks']['Plan']
        answer = run(case['notes'], {'Plan': [first]}, fields=case['fields'])['Plan']
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
        start = case['notes'].index(first)
        old = {'status': 'supported', 'text': first.removeprefix('Plan is '), 'reviewed': True,
               'evidence': [{'quote': first, 'start': start, 'end': start + len(first)}]}
        key = next(f['key'] for f in case['fields'] if f['label'] == 'Plan')
        self.assertEqual(g.governed_decisions(case['notes'], case['fields'], {key: old}), ['Plan'])
        # ⚠️ DELIBERATE CHANGE 2026-09-29: a follow-up that belongs to another person holds the PLAN it continues (b''
        # and the owned block), not the examination and assessment before it (they were held with the whole chain).
        for other in ('Her father will follow up in six weeks.', 'She will follow up in six weeks for the donor.'):
            changed = case['notes'].replace(followup, other)
            self.assert_named_hold(changed, ('Allergies',))
            self.assert_named_released(changed)
            plan = run(changed, {'Plan': [first, other]}, fields=case['fields'])['Plan']
            self.assertEqual((plan['status'], plan['text']), ('conflict', ''), other)

    def test_source_relation_cannot_grant_a_scoped_or_duplicate_destination(self):
        case = retained()
        for label in VALUES:
            for context in ('Mother', 'Left knee', 'Previous visit'):
                fields = copy.deepcopy(case['fields'])
                next(f for f in fields if f['label'] == label)['context'] = context
                answer = run(case['notes'], {label: case['unchanged_picks'][label]}, fields=fields)[label]
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''), (label, context))

    def test_retained_ambiguous_and_implicit_patient_cases_are_not_reinterpreted(self):
        for name, held in (('r1-note1', ('Past medical history', 'Medications')),
                           ('r1-note8', ('Chief complaint', 'History of present illness', 'Medications', 'Plan')),
                           ('r1-note10', ('Past medical history', 'Medications'))):
            case = retained(name)
            answers = run(case['notes'], case['unchanged_picks'], fields=case['fields'])
            for label in held:
                self.assertEqual((answers[label]['status'], answers[label]['text']), ('conflict', ''), (name, label))
        # ⚠️ DELIBERATE CHANGE 2026-09-29 (notes usefulness, G-B): r1-note1's presentation is the Chief complaint and the
        # History of present illness on its own; nothing later links to it (it was held by position).
        case = retained('r1-note1')
        answers = run(case['notes'], case['unchanged_picks'], fields=case['fields'])
        for label in ('Chief complaint', 'History of present illness'):
            self.assertEqual((answers[label]['status'], answers[label]['text']),
                             ('supported', case['unchanged_picks'][label][0]), label)

    def test_literal_source_ledger_preserves_positions_and_sentence_boundaries(self):
        case = retained()
        for notes in (case['notes'], case['notes'].replace('. ', '.\n')):
            answers = run(notes, case['unchanged_picks'], fields=case['fields'])
            self.assertEqual({label: answers[label]['text'] for label in RELEASED}, RELEASED)
            reading = g.governance_for(notes, case['fields'])[11]['preceding']
            relations = reading['actor_relations']
            self.assertEqual(set(relations['units']), {u['id'] for u in reading['units']})
            for unit in reading['units']:
                relation = relations['units'][unit['id']]
                self.assertEqual(notes[relation['start']:relation['end']], unit['quote'])
                self.assertEqual(relation['anchor'], 1)
            self.assertEqual([notes[low:high] for spans in relations['qualifiers'].values() for low, high in spans],
                             ['ago', 'or', 'nonsmoker', 'to'])
        # ⚠️ DELIBERATE CHANGE 2026-09-29: a missing full stop breaks the ledger, but the examination and assessment
        # resolve to the patient without it and nothing links to them; Allergies (G-I) stays held.
        changed = case['notes'].replace('headaches. The headaches', 'headaches The headaches')
        self.assert_named_hold(changed, ('Allergies',))
        self.assert_named_released(changed)
        self.assert_named_hold(case['notes'].replace('She denies', 'He denies'))

    def test_negative_allergy_cannot_drop_a_clinically_related_assessment(self):
        case = retained()
        for assessment in ('penicillin anaphylaxis.', 'penicillin hypersensitivity.'):
            notes = case['notes'].replace('tension-type headache.', assessment)
            self.assert_named_hold(notes, ('Allergies',))


@override_settings(**LIVE)
class CompletePatientTopicWorkflow(V3EncounterFixture, TestCase):
    def setUp(self):
        case = retained()
        labels = [f['label'] for f in case['fields']]
        with patch('core.tests.test_word_v3_workflow.build_intake_form',
                   side_effect=lambda path: ordinary_input_form(path, labels)):
            super().setUp()
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied'))
        deny.start(); self.addCleanup(deny.stop)

    def test_whole_original_note_worker_review_correction_finalize_and_export(self):
        case = retained()
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/notes/',
            {'revision': self.encounter.revision, 'notes': case['notes']}).status_code, 302)
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = lambda **kw: unit_response(
                json.loads(kw['messages'][0]['content']), case['unchanged_picks'])
            job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            self.assertTrue(run_one())
            self.assertEqual(client.return_value.messages.create.call_count, 1)
        job.refresh_from_db(); self.assertEqual(job.state, 'succeeded', job.error)
        self.encounter.refresh_from_db()
        automatic = copy.deepcopy(self.encounter.answers)
        page = self.client.get(f'/encounters/{self.encounter.pk}/')
        rows = {row['label']: row for row in page.context['answer_rows']}
        for label in case['unchanged_picks']:
            expected = ('supported', RELEASED[label]) if label in RELEASED else ('conflict', '')
            self.assertEqual((rows[label]['status'], rows[label]['text']), expected, label)
        self.finalize(); self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status, 'finalized')
        self.assertFalse(self.encounter.export_path)
        # These explicit clinician decisions are assisted completion, never automatic recognition or source-selection
        # successes. ⚠️ 2026-09-29: Chief complaint, HPI and Medications are now automatic (RELEASED); two remain.
        manual = {'Allergies': '\n'.join(case['unchanged_picks']['Allergies']), 'Smoker': 'No'}
        payload = self.answers_payload({**RELEASED, **manual})
        for label in manual: payload['held_shown_' + self.key(label)] = '1'
        for field in self.version.fields:
            if field['label'] not in case['unchanged_picks'] and field['kind'] not in ('signature', 'initials'):
                payload['blank_' + field['key']] = 'on'
        saved = self.client.post(f'/encounters/{self.encounter.pk}/save/', payload)
        self.assertEqual(saved.status_code, 302, saved.content.decode())
        self.encounter.refresh_from_db()
        for label, value in {**RELEASED, **manual}.items():
            self.assertEqual(self.encounter.answers[self.key(label)]['text'], value)
        self.finalize(); self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, 'finalized')
        exported = private_path(self.encounter.export_path).read_bytes()
        body = part_text(exported)
        for value in (*RELEASED.values(), *manual.values()):
            for line in value.splitlines():
                if line != 'No': self.assertIn(line, body)
        self.assertIn('Smoker  ☐ Yes  ☒ No', body)
        self.assertEqual(hashlib.sha256(exported).hexdigest(), self.encounter.export_sha256)
        self.assertEqual(private_path(self.template.original_path).read_bytes(), self.original)
        if (capture := os.environ.get('QUILLMD_PATIENT_ARTIFACTS')):
            path = Path(capture); path.mkdir(parents=True, exist_ok=True)
            (path / 'synthetic-original.docx').write_bytes(self.original)
            (path / 'synthetic-final.docx').write_bytes(exported)
            (path / 'workflow.json').write_text(json.dumps({'notes': case['notes'], 'automatic_answers': automatic,
                'manual_decisions': manual, 'final_answers': self.encounter.answers,
                'original_sha256': hashlib.sha256(self.original).hexdigest(),
                'final_sha256': self.encounter.export_sha256}, indent=2) + '\n')

    def test_forced_stored_answer_does_not_ignore_a_new_source_actor_on_page_save_finalize(self):
        case = retained()
        notes = case['notes'].replace('She takes ibuprofen as needed.', 'The donor is here. She takes ibuprofen as needed.')
        self.encounter.notes = notes
        self.encounter.answers = {}
        for label, value in VALUES.items():
            quotes = case['unchanged_picks'][label]
            self.encounter.answers[self.key(label)] = {'status': 'supported', 'text': value, 'reviewed': True,
                'evidence': [{'quote': quote, 'start': notes.index(quote), 'end': notes.index(quote) + len(quote)} for quote in quotes]}
        self.encounter.save(update_fields=['notes', 'answers'])
        rows = {row['label']: row for row in self.client.get(f'/encounters/{self.encounter.pk}/').context['answer_rows']}
        for label in VALUES:
            self.assertEqual((rows[label]['status'], rows[label]['text']), ('conflict', ''))
        self.finalize(); self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
        self.assertEqual(self.save(VALUES).status_code, 302)
        self.finalize(); self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)

    def test_negative_allergy_and_related_assessment_refuse_actual_stored_routes(self):
        case = retained()
        quote = case['unchanged_picks']['Allergies'][0]
        for assessment in ('penicillin anaphylaxis.', 'penicillin hypersensitivity.'):
            notes = case['notes'].replace('tension-type headache.', assessment)
            self.encounter.refresh_from_db()
            self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/notes/',
                {'revision': self.encounter.revision, 'notes': notes}).status_code, 302)
            # Resolve every other answer explicitly so the negative test cannot
            # pass only because some unrelated field is missing/unreviewed.
            payload = self.answers_payload({})
            for field in self.version.fields:
                if field['kind'] not in ('signature', 'initials'):
                    payload['blank_' + field['key']] = 'on'
            self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/save/', payload).status_code, 302)
            self.encounter.refresh_from_db()
            start = notes.index(quote)
            self.encounter.answers[self.key('Allergies')] = {'status': 'supported', 'text': quote,
                'reviewed': True, 'evidence': [{'quote': quote, 'start': start, 'end': start + len(quote)}]}
            self.encounter.save(update_fields=['answers'])
            self.assertEqual(g.governed_decisions(notes, self.version.fields, self.encounter.answers), ['Allergies'])
            rows = {row['label']: row for row in self.client.get(f'/encounters/{self.encounter.pk}/').context['answer_rows']}
            self.assertEqual((rows['Allergies']['status'], rows['Allergies']['text']), ('conflict', ''))
            self.finalize(); self.encounter.refresh_from_db()
            self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
            self.assertEqual(self.save({'Allergies': quote}).status_code, 302)
            self.finalize(); self.encounter.refresh_from_db()
            self.assertNotEqual(self.encounter.status, 'finalized'); self.assertFalse(self.encounter.export_path)
