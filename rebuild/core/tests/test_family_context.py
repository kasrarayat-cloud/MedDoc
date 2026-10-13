"""Positioned family history does not taint an otherwise independent fact."""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import semantic_generation as semantic
from core.tests.test_semantic_generation import fact, assignments, FixtureSender
from documents.semantic_preparation_roles import default_definitions


class FamilyContextTests(SimpleTestCase):
    def prepare(self, notes, history='family history of colon polyps', *, timing='current', polarity='affirmed'):
        fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                  for i, (key, label) in enumerate((('name', 'Patient name'), ('history', 'Impression')))]
        definitions = default_definitions(fields)
        for definition in definitions.values():
            definition.update(version=2, answer_mode='atomic')
        values = [fact(notes, fields, 'name', 'Synthetic Morgan Ellis', kind='identity',
                       name_quote='Synthetic Morgan Ellis', timing='unspecified'),
                  fact(notes, fields, 'history', history, kind='assessment', timing=timing, polarity=polarity)]
        selected = assignments(fields, {'name': ['name'], 'history': ['history']})
        return fields, definitions, values, selected

    def generate(self, notes, *, profile=semantic.FAMILY_SCOPE_CONTRACT, **kwargs):
        fields, definitions, values, selected = self.prepare(notes, **kwargs)
        sender = FixtureSender(values, selected)
        answers = semantic.run(notes, fields, definitions, sender, scope_contract=profile)
        for field in fields:
            semantic.validate_stored_answer(notes, field, definitions[field['key']], answers[field['key']])
        self.assertEqual(len(sender.calls), 3)
        return answers, sender

    def test_complete_impression_and_unrelated_identity_pass_without_disease_reassignment(self):
        notes = ('Synthetic Morgan Ellis attended today. The clinician\'s impression was '
                 'no current gastrointestinal symptoms and a family history of colon polyps.')
        value = 'no current gastrointestinal symptoms and a family history of colon polyps'
        answers, sender = self.generate(notes, history=value, polarity='negated')
        self.assertEqual(answers['name']['text'], 'Synthetic Morgan Ellis')
        self.assertEqual(answers['history']['text'], value.capitalize())
        self.assertEqual([a['status'] for a in answers.values()], ['supported', 'supported'])
        self.assertEqual(answers['history']['fact_scope_contract'], semantic.FAMILY_SCOPE_CONTRACT)
        self.assertIn('family_history_review', sender.calls[0][2])
        retained = next(f for f in answers['history']['facts'] if f['id'] == 'history')
        self.assertEqual(retained['value_evidence']['quote'], value)

    def test_disease_only_span_never_becomes_patient_disease(self):
        notes = 'Synthetic Morgan Ellis attended today. The patient has a family history of colon polyps.'
        answers, _ = self.generate(notes, history='colon polyps', timing='unspecified')
        self.assertEqual(answers['history']['status'], 'conflict')
        self.assertIn('The source may describe another person, rather than the patient.', answers['history']['review_reasons'])
        self.assertEqual(answers['history']['text'], '')

    def test_each_occurrence_needs_its_own_complete_ungoverned_fact(self):
        for prefix in ('Family history:\n', 'Family history is documented here. ',
                       'Family hi\u200bstory is documented here. ',
                       'The following findings are denied:\n', 'These findings are hypothetical. ',
                       '"The patient has diabetes." ', 'All facts are incorrect. ',
                       'Example: ', 'This is an example. ', 'This is a fictional case. '):
            notes = prefix+'Synthetic Morgan Ellis attended today. The patient has a family history of colon polyps.'
            with self.subTest(prefix=prefix):
                answers, _ = self.generate(notes)
                self.assertNotEqual(answers['name']['status'], 'supported')
                self.assertNotEqual(answers['history']['status'], 'supported')

    def test_other_past_context_is_not_erased(self):
        for prefix in ('Previously ', 'Formerly ', 'Last year ', 'The patient used to have '):
            notes = 'Synthetic Morgan Ellis attended today. '+prefix+'a family history of colon polyps was documented.'
            with self.subTest(prefix=prefix):
                answers, _ = self.generate(notes)
                self.assertNotEqual(answers['history']['status'], 'supported')
                self.assertTrue(any('past time' in reason or 'historical scope' in reason
                                    for reason in answers['history']['review_reasons']))

    def test_qualification_after_a_clipped_history_is_not_erased(self):
        for suffix in ('is not confirmed', 'was ruled out', 'is unconfirmed'):
            notes = 'Synthetic Morgan Ellis attended today. The patient\'s family history of colon polyps '+suffix+'.'
            with self.subTest(suffix=suffix):
                answers, _ = self.generate(notes)
                self.assertEqual(answers['history']['status'], 'conflict')
        for suffix in ('remains unconfirmed', 'needs confirmation', 'requires further verification',
                       'is uncertain', 'was ruled out'):
            value = 'family history of colon polyps '+suffix
            notes = 'Synthetic Morgan Ellis attended today. The clinician\'s impression was '+value+'.'
            with self.subTest(complete_qualified_value=value):
                answers, _ = self.generate(notes, history=value)
                self.assertEqual(answers['history']['status'], 'conflict')

    def test_clinician_owned_history_cannot_become_patient_history(self):
        for owner in ('The clinician', 'The doctor', 'Dr. Synthetic Avery Cole', 'Synthetic Avery Cole'):
            source = owner+' has a family history of colon polyps'
            notes = 'Synthetic Morgan Ellis attended today. '+source+'.'
            for selected in ('family history of colon polyps', source):
                with self.subTest(owner=owner, selected=selected):
                    answers, _ = self.generate(notes, history=selected)
                    self.assertEqual(answers['history']['status'], 'conflict')

    def test_separate_personal_history_time_is_not_discharged_by_a_family_phrase(self):
        value = 'family history of colon polyps and a history of melanoma'
        notes = 'Synthetic Morgan Ellis attended today. The clinician\'s impression was '+value+'.'
        answers, _ = self.generate(notes, history=value)
        self.assertEqual(answers['history']['status'], 'conflict')
        self.assertIn('The value source contains an explicit past time; current attribution needs review.',
                      answers['history']['review_reasons'])

    def test_questions_and_embedded_other_ownership_are_not_assertions_about_patient(self):
        for statement, value in (
                ('The patient has a family history of colon polyps?', 'family history of colon polyps'),
                ('The patient has a family history of colon polyps?', 'family history of colon polyps?'),
                ("The clinician's impression was family history of colon polyps？", 'family history of colon polyps？'),
                ("The clinician's impression was family history of colon polyps؟", 'family history of colon polyps؟'),
                ("The clinician's impression was family history of colon polyps‽", 'family history of colon polyps‽'),
                ("The clinician's impression was family history of colon polyps⸘", 'family history of colon polyps⸘'),
                ("The clinician's impression was my family history of colon polyps.", 'my family history of colon polyps'),
                ("The clinician's impression was his family history of colon polyps.", 'his family history of colon polyps'),
                ("The clinician's impression was Avery's family history of colon polyps.", "Avery's family history of colon polyps"),
                ("The clinician's impression was the clinician's own family history of colon polyps.", "the clinician's own family history of colon polyps"),
                ("The clinician's impression was family history of colon polyps in the clinician's father.", "family history of colon polyps in the clinician's father"),
                ("The clinician's impression was family history of colon polyps in another patient.", "family history of colon polyps in another patient")):
            notes = 'Synthetic Morgan Ellis attended today. '+statement
            with self.subTest(statement=statement, value=value):
                answers, _ = self.generate(notes, history=value)
                self.assertEqual(answers['history']['status'], 'conflict')

    def test_profiles_are_immutable_and_unknown_profile_sends_nothing(self):
        notes = 'Synthetic Morgan Ellis attended today. The patient has a family history of colon polyps.'
        for profile in (semantic.LEGACY_SCOPE_CONTRACT, semantic.POSITIONED_SCOPE_CONTRACT, semantic.DURATION_SCOPE_CONTRACT):
            with self.subTest(profile=profile):
                answers, sender = self.generate(notes, profile=profile)
                self.assertEqual(answers['name']['status'], 'conflict')
                self.assertEqual(answers['history']['status'], 'conflict')
                self.assertNotIn('family_history_review', sender.calls[0][2])
        fields, definitions, values, selected = self.prepare(notes)
        sender = FixtureSender(values, selected)
        with self.assertRaises(ValidationError):
            semantic.run(notes, fields, definitions, sender, scope_contract='unknown')
        self.assertEqual(sender.calls, [])
        answers, _ = self.generate(notes)
        for profile in (semantic.DURATION_SCOPE_CONTRACT, None, 'unknown'):
            bad = deepcopy(answers['history'])
            if profile is None:
                bad.pop('fact_scope_contract')
            else:
                bad['fact_scope_contract'] = profile
            with self.subTest(tampered=profile), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, fields[1], definitions['history'], bad)

    def test_duration_dimension_guard_still_applies(self):
        from core.tests.test_cedar_duration import CedarDurationTests
        duration = CedarDurationTests()
        answer = duration.run_case('She describes right knee stiffness that began four days ago.',
                                   'four days', semantic.FAMILY_SCOPE_CONTRACT)
        self.assertEqual((answer['status'], answer['text']), ('supported', 'Four days'))
        answer = duration.run_case('Right knee stiffness has lasted about four days.',
                                   'four days', semantic.FAMILY_SCOPE_CONTRACT)
        self.assertEqual(answer['status'], 'conflict')
