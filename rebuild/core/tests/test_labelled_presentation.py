"""Literal approved labels need independently positioned source roles."""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation, labelled_presentation as presentation
from core import semantic_generation as semantic
from core.tests.test_semantic_generation import fact, assignments
from documents.semantic_preparation_roles import default_definitions


class LabelledPresentationTests(SimpleTestCase):
    meaning = ('Narrative encounter summary with each documented component labelled: '
        'patient age and sex, service date, treating clinician, country, setting, modality, '
        'and whether the patient is established or new. '
        'Include only documented facts; leave undocumented components blank.')
    header = ('Patient: Synthetic Ada Tern\nService date: 21 October 2027\n'
              'Treating clinician: Dr. Milo Venn\n')
    visit = ('Ada is a 38-year-old woman attending a new-patient, video visit '
             'in a U.K. rheumatology clinic.')
    values = {'age': '38-year-old woman', 'date': '21 October 2027', 'doctor': 'Milo Venn',
              'country': 'U.K.', 'setting': 'rheumatology clinic', 'mode': 'video', 'status': 'new-patient'}

    def build(self, *, meaning=None, selected=None, body=None, header=None,
              scope=None, profile=None, raw_change=None, reverse=False):
        notes = (self.header if header is None else header)+(self.visit if body is None else body)
        field = {'key': 'summary', 'kind': 'text', 'label': 'Encounter summary', 'locator': {'cell': 0}}
        definition = default_definitions([field])['summary']
        definition.update(version=2, answer_mode='narrative', meaning=meaning or self.meaning,
            scope=scope or {'subject': 'encounter', 'temporality': 'current', 'polarity': 'any'})
        raw = [fact(notes, [field], key, value, concept='irrelevant provider concept',
                    subject='clinician' if key == 'doctor' else 'patient')
               for key, value in self.values.items() if value in notes]
        if raw_change:
            raw_change(raw, notes)
        if reverse:
            raw.reverse()
        units, _ = generation.source_units(notes, [field])
        profile = profile or semantic.LABELLED_PRESENTATION_SCOPE_CONTRACT
        facts = semantic.validate_facts(notes, units, {'facts': raw}, scope_contract=profile)
        ids = [row['id'] for row in raw] if selected is None else selected
        answer = semantic._assign(notes, [field], {'summary': definition}, facts,
            assignments([field], {'summary': ids}), scope_contract=profile)['summary']
        answer['independent_check'] = {'verdict': 'pass', 'fact_ids': ids, 'reason': ''}
        return notes, field, definition, facts, answer

    def test_approved_order_and_literal_label_spans_do_not_follow_fact_order(self):
        first = self.build()
        reverse = self.build(reverse=True)
        for notes, field, definition, facts, answer in (first, reverse):
            self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
            self.assertEqual(answer['text'], first[-1]['text'])
            proof = answer['derived_presentation']
            self.assertEqual(proof['state'], 'resolved')
            for part in proof['parts']:
                label = part['label']
                self.assertEqual(label['quote'], definition['meaning'][label['start']:label['end']])
                source = part['source_role']['value']
                self.assertEqual(source['quote'], notes[source['start']:source['end']])
            self.assertEqual(proof['parts'][1]['fact_id'], 'date')
            self.assertEqual(proof['parts'][2]['fact_id'], 'doctor')
            semantic.validate_stored_answer(notes, field, definition, answer)

    def test_unknown_complete_metadata_requirement_is_a_hold_even_without_selected_facts(self):
        meanings = [self.meaning+' Omit dates.', self.meaning+' Preserve its complete meaning.',
                    self.meaning.replace('country,', 'country of citizenship,'),
                    self.meaning.replace('country,', 'country, country,'),
                    self.meaning.replace('Narrative encounter', 'Concise narrative encounter')]
        for meaning in meanings:
            for selected in (None, []):
                with self.subTest(meaning=meaning, selected=selected):
                    answer = self.build(meaning=meaning, selected=selected)[-1]
                    self.assertEqual(answer['status'], 'conflict')
                    self.assertEqual(answer['text'], '')
                    self.assertEqual(answer['derived_presentation']['state'], 'unresolved')

    def test_selected_fact_concepts_cannot_swap_roles(self):
        def change(raw, notes):
            for row in raw:
                row['concept'] = 'clinician' if row['id'] == 'date' else 'service_date'
        answer = self.build(raw_change=change)[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        self.assertIn('service date: 21 October 2027', answer['text'])
        self.assertIn('treating clinician: Milo Venn', answer['text'])

    def test_missing_selected_documented_component_stays_held(self):
        for omitted in self.values:
            with self.subTest(omitted=omitted):
                answer = self.build(selected=[key for key in self.values if key != omitted])[-1]
                self.assertEqual(answer['status'], 'conflict')

    def test_undocumented_component_remains_empty_without_inventing_value(self):
        header = 'Patient: Synthetic Ada Tern\nService date: 21 October 2027\n'
        answer = self.build(header=header)[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        self.assertNotIn('treating clinician:', answer['text'])
        self.assertIsNone(answer['derived_presentation']['parts'][2]['fact_id'])

    def test_time_account_prose_is_not_an_ambiguous_encounter_metadata_assertion(self):
        body = self.visit+'\nP\nI spent 29 minutes counseling the patient and documenting the visit.'
        answer = self.build(body=body)[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])

    def test_future_follow_up_does_not_describe_the_current_encounter(self):
        for future in ('She is scheduled for a follow-up visit in the office in four weeks.',
                       'She will attend a video visit at the clinic next month.',
                       'The visit will be in-person in the office next week.'):
            with self.subTest(future=future):
                notes, field, definition, facts, answer = self.build(body=self.visit+'\nP\n'+future)
                self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
                self.assertEqual(answer['text'], self.build()[-1]['text'])
                semantic.validate_stored_answer(notes, field, definition, answer)

    def test_other_objects_in_patient_prose_do_not_claim_patient_metadata(self):
        for prose in ('She is worried about a woman who works in the office.',
                      'She is caring for an elderly woman in the clinic.',
                      'She is a teacher who sees a woman in the office.',
                      'Setting goals is helpful to her.'):
            with self.subTest(prose=prose):
                notes, field, definition, facts, answer = self.build(body=self.visit+'\nS\n'+prose)
                self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
                self.assertEqual(answer['text'], self.build()[-1]['text'])
                semantic.validate_stored_answer(notes, field, definition, answer)

    def test_punctuation_free_metadata_headers_remain_documented_obligations(self):
        for body in ('Patient age 38 years.\nSex female.',
                     'Country U.K.\nSetting rheumatology clinic.',
                     'Visit date 21 October 2027.',
                     'Visit modality video.\nPatient status new-patient.',
                     'Treating clinician Dr. Milo Venn.'):
            with self.subTest(body=body):
                notes, field, definition, facts, answer = self.build(body=body, selected=['date', 'doctor'])
                self.assertEqual(answer['status'], 'conflict')
                self.assertEqual(answer['derived_presentation']['state'], 'unresolved')
                self.assertTrue(answer['derived_presentation']['source_candidates'])
                forged = deepcopy(answer)
                forged.update(status='supported', text='21 October 2027; Milo Venn', value='21 October 2027; Milo Venn')
                forged['semantic_proof_sha256'] = semantic._fact_proof(forged)
                with self.assertRaises(ValidationError):
                    semantic.validate_stored_answer(notes, field, definition, forged)

    def test_direct_age_or_status_predicate_is_not_erased_by_qualification(self):
        for body in ('She is possibly a woman.', 'She is a young woman.',
                     'She may be 38 years old.', 'She is not a new-patient.',
                     'She has an age of 38 years and sex female.'):
            with self.subTest(body=body):
                answer = self.build(body=body, selected=['date', 'doctor'])[-1]
                self.assertEqual(answer['status'], 'conflict')
                self.assertEqual(answer['derived_presentation']['state'], 'unresolved')

    def test_bare_header_unknown_tails_and_coordination_never_delete_the_obligation(self):
        for body in ('Sex female (unverified).', 'Country U.K. unless verified.',
                     'Visit modality video or telephone.', 'Age 38 years, sex woman.',
                     'Setting rheumatology clinic according to an unknown reporter.',
                     'Patient status new-patient except when recorded otherwise.'):
            with self.subTest(body=body):
                notes, field, definition, facts, answer = self.build(body=body, selected=['date', 'doctor'])
                self.assertEqual(answer['status'], 'conflict')
                proof = answer['derived_presentation']
                self.assertEqual(proof['state'], 'unresolved')
                self.assertTrue(any(body.rstrip('.') in candidate['source']['quote']
                                    for candidate in proof['source_candidates']))
                forged = deepcopy(answer)
                forged.update(status='supported', text='21 October 2027; Milo Venn', value='21 October 2027; Milo Venn')
                forged['semantic_proof_sha256'] = semantic._fact_proof(forged)
                with self.assertRaises(ValidationError):
                    semantic.validate_stored_answer(notes, field, definition, forged)

    def test_role_header_discovery_does_not_depend_on_recognizing_its_value(self):
        for body in ('Patient age reportedly 38 years.', 'Sex reportedly female.',
                     'Country reportedly U.K.', 'Age unexpectedly thirty-eight.',
                     'Sex an unfamiliar description.', 'Country an unknown literal value.',
                     'Visit modality a new description or telephone.',
                     'Setting reportedly an unfamiliar facility, not yet confirmed.',
                     'Patient status disputed and unresolved.'):
            with self.subTest(body=body):
                notes, field, definition, facts, answer = self.build(body=body, selected=['date', 'doctor'])
                self.assertEqual(answer['status'], 'conflict')
                proof = answer['derived_presentation']
                self.assertEqual(proof['state'], 'unresolved')
                self.assertTrue(any(body.rstrip('.') in candidate['source']['quote']
                                    for candidate in proof['source_candidates']))
                forged = deepcopy(answer)
                forged.update(status='supported', text='21 October 2027; Milo Venn', value='21 October 2027; Milo Venn')
                forged['semantic_proof_sha256'] = semantic._fact_proof(forged)
                with self.assertRaises(ValidationError):
                    semantic.validate_stored_answer(notes, field, definition, forged)

    def test_action_clause_exclusion_requires_the_complete_clause(self):
        answer = self.build(body=self.visit+'\nSetting priorities can be useful for the patient.')[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        for tail in (' except the setting is unconfirmed.', ' but country is disputed.'):
            answer = self.build(body=self.visit+'\nSetting goals is helpful'+tail)[-1]
            self.assertEqual(answer['status'], 'conflict')

    def test_complete_age_statement_is_documented_even_without_a_visit_frame(self):
        for body in ('Ada is a 38-year-old woman.', 'Reportedly, Ada is a 38-year-old woman.'):
            answer = self.build(body=body, selected=['date', 'doctor'])[-1]
            self.assertEqual(answer['status'], 'conflict')

    def test_unparsed_documented_metadata_cannot_be_an_undocumented_blank(self):
        bodies = ['Patient age: 38 years.\nSex: woman.',
                  'Patient age is 38 years.\nSex is woman.',
                  'Ada is 38 years old and is a woman.',
                  'Her age is thirty-eight and her sex is female.',
                  'Encounter setting: rheumatology clinic.',
                  'The encounter setting is rheumatology clinic.',
                  'Visit modality: video.', 'Encounter country: U.K.']
        for body in bodies:
            with self.subTest(body=body):
                notes, field, definition, facts, answer = self.build(body=body, selected=['date', 'doctor'])
                self.assertEqual(answer['status'], 'conflict')
                proof = answer['derived_presentation']
                self.assertEqual(proof['state'], 'unresolved')
                self.assertTrue(proof['source_candidates'])
                for candidate in proof['source_candidates']:
                    source = candidate['source']
                    self.assertEqual(source['quote'], notes[source['start']:source['end']])
                forged = deepcopy(answer)
                forged.update(status='supported', text='21 October 2027; Milo Venn', value='21 October 2027; Milo Venn')
                forged['semantic_proof_sha256'] = semantic._fact_proof(forged)
                with self.assertRaises(ValidationError):
                    semantic.validate_stored_answer(notes, field, definition, forged)

    def test_unparsed_visit_date_alias_stays_a_source_obligation(self):
        for name in ('Visit date', 'Consultation date'):
            answer = self.build(header=self.header.replace('Service date', name), body='', selected=['doctor'])[-1]
            self.assertEqual(answer['status'], 'conflict')
            self.assertTrue(any('service date' in reason for reason in answer['review_reasons']))

    def test_unresolved_scope_is_not_positive_proof_of_absence(self):
        headings = [('Prior encounter on 21 October 2027 for an unverified person', '\nCurrent encounter'),
                    ('Prior encounter on 31 February 2027', ''), ('Hypothetical encounter:', '\nCurrent encounter')]
        for heading, reset in headings:
            with self.subTest(heading=heading):
                body = heading+reset+'\nCountry: U.K.\nSetting: rheumatology clinic.'
                answer = self.build(body=body, selected=['date', 'doctor'])[-1]
                self.assertEqual(answer['status'], 'conflict')
                proof = answer['derived_presentation']
                self.assertEqual(proof['state'], 'unresolved')
                self.assertTrue(any(row['scope']['issues'] or row['scope']['subject'] == 'ambiguous'
                                    for row in proof['source_candidates']))

    def test_explicit_current_reset_resolves_date_only_ambiguity_without_changing_old_reader(self):
        body = 'Prior encounter on 31 February 2027\nCurrent encounter\nCountry: U.K.\nSetting: rheumatology clinic.'
        answer = self.build(body=body, selected=['date', 'doctor', 'country', 'setting'])[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])

    def test_definite_foreign_and_past_metadata_do_not_fill_or_poison_current_blanks(self):
        for heading in ("Mother's history:", 'Prior encounter on 21 October 2026', 'Future encounter:'):
            body = heading+'\nCountry: U.K.\nSetting: rheumatology clinic.\nPatient age: 38 years.\nSex: woman.'
            answer = self.build(body=body, selected=['date', 'doctor'])[-1]
            self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
            self.assertNotIn('country:', answer['text'])
            self.assertNotIn('patient age and sex:', answer['text'])

    def test_genuinely_absent_roles_remain_blank(self):
        answer = self.build(body='', selected=['date', 'doctor'])[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        self.assertEqual(answer['text'], 'service date: 21 October 2027; treating clinician: Milo Venn')

    def test_new_source_candidate_floor_does_not_change_historical_v23(self):
        answer = self.build(body='Patient age: 38 years.\nSex: woman.', selected=['date', 'doctor'],
                            profile=semantic.ORDER_EVENT_SCOPE_CONTRACT)[-1]
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        self.assertNotIn('derived_presentation', answer)

    def test_unparsed_metadata_frame_and_qualifications_stay_held(self):
        variants = ['Reportedly, '+self.visit, 'Assume '+self.visit,
                    self.visit[:-1]+' unless verified.',
                    self.visit.replace(' is a ', ' was a '),
                    self.visit.replace('rheumatology clinic', 'unverified rheumatology clinic')]
        for body in variants:
            with self.subTest(body=body):
                answer = self.build(body=body)[-1]
                self.assertNotEqual(answer['status'], 'supported')

    def test_same_literal_at_a_different_source_position_cannot_fill_role(self):
        from core.tests.test_semantic_generation import span
        for key, extra in [('date', 'Medication start date: 21 October 2027.'),
                           ('doctor', 'The mother is named Milo Venn.')]:
            def change(raw, notes):
                row = next(row for row in raw if row['id'] == key)
                row['value_span'] = span(notes, self.values[key], 1)
                units, _ = generation.source_units(notes, [])
                row['source_unit_ids'] = [u['id'] for u in units if u['start'] <= row['value_span']['start'] < row['value_span']['end'] <= u['end']]
            answer = self.build(body=self.visit+'\nS\n'+extra, raw_change=change)[-1]
            self.assertNotEqual(answer['status'], 'supported')

    def test_duplicate_current_source_headers_are_ambiguous(self):
        answer = self.build(body=self.visit+'\nService date: 21 October 2027')[-1]
        self.assertNotEqual(answer['status'], 'supported')

    def test_clipped_or_compound_selected_values_do_not_gain_role_by_substring(self):
        def compound(raw, notes):
            from core.tests.test_semantic_generation import span
            row = next(row for row in raw if row['id'] == 'age')
            row['value_span'] = span(notes, '38-year-old woman attending a new-patient')
        answer = self.build(raw_change=compound)[-1]
        self.assertNotEqual(answer['status'], 'supported')

    def test_source_role_cannot_change_subject_time_or_polarity(self):
        for property, value in [('subject', {'kind': 'clinician', 'name_span': None}),
                                ('timing', {'kind': 'past', 'span': None}), ('polarity', 'negated')]:
            def change(raw, notes):
                next(row for row in raw if row['id'] == 'age')[property] = value
            answer = self.build(raw_change=change)[-1]
            self.assertNotEqual(answer['status'], 'supported')

    def test_resigned_saved_proof_is_rederived_not_trusted(self):
        notes, field, definition, facts, answer = self.build()
        def swap(proof):
            proof['parts'][1]['fact_id'], proof['parts'][2]['fact_id'] = 'doctor', 'date'
        changes = [swap, lambda p: p['parts'][0]['label'].update(quote='Invented label'),
                   lambda p: p.update(source_sha256='0'*64),
                   lambda p: p['parts'][0]['source_role']['value'].update(start=0)]
        for change in changes:
            altered = deepcopy(answer)
            change(altered['derived_presentation'])
            altered['semantic_proof_sha256'] = semantic._fact_proof(altered)
            with self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, field, definition, altered)
        altered = deepcopy(answer)
        del altered['derived_presentation']
        altered['semantic_proof_sha256'] = semantic._fact_proof(altered)
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(notes, field, definition, altered)

    def test_copied_proof_binds_exact_destination_question(self):
        notes, field, definition, facts, answer = self.build()
        changed = {**field, 'label': 'A different approved question', 'locator': {'cell': 8}}
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(notes, changed, definition, answer)

    def test_legacy_v23_keeps_plain_join_and_has_no_new_proof(self):
        notes, field, definition, facts, answer = self.build(profile=semantic.ORDER_EVENT_SCOPE_CONTRACT)
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        self.assertNotIn('derived_presentation', answer)
        self.assertNotIn('service date:', answer['text'])
        semantic.validate_stored_answer(notes, field, definition, answer)

    def test_unlabelled_narrative_has_no_new_requirement(self):
        self.assertIsNone(presentation.requirements({'meaning': 'Documented narrative.'}))

    def test_wrong_scope_and_atomic_label_requirements_do_not_silently_fall_back(self):
        for scope in ({'subject': 'other', 'temporality': 'current', 'polarity': 'any'},
                      {'subject': 'encounter', 'temporality': 'past', 'polarity': 'any'},
                      {'subject': 'encounter', 'temporality': 'current', 'polarity': 'negative'}):
            answer = self.build(scope=scope)[-1]
            self.assertNotEqual(answer['status'], 'supported')
            self.assertEqual(answer['derived_presentation']['state'], 'unresolved')
        definition = self.build()[2]
        definition['answer_mode'] = 'atomic'
        self.assertEqual(presentation.requirements(definition)['state'], 'unresolved')

    def test_existing_source_labelled_measurements_are_not_prefixed_again(self):
        field = {'key': 'vitals', 'label': 'Vital signs', 'kind': 'text', 'locator': {'cell': 1}}
        definition = default_definitions([field])['vitals']
        definition.update(version=2, answer_mode='narrative', meaning=(
            'Narrative of the documented vital signs for this encounter as complete labelled measurement phrases: '
            'blood pressure, pulse, temperature and weight, each with its documented unit and scale. '
            'No common unit or normal range is implied; bare numbers are not sufficient.'),
            scope={'subject': 'patient', 'temporality': 'current', 'polarity': 'any'})
        values = ['Blood pressure is 124/76 mmHg', 'Pulse 72 beats per minute',
                  'Temperature 36.8 degrees Celsius', 'Weight 64.3 kg']
        notes = self.header+'O\n'+'. '.join(values)+'.'
        units, _ = generation.source_units(notes, [field])
        raw = [fact(notes, [field], 'v'+str(i), value) for i, value in enumerate(values)]
        facts = semantic.validate_facts(notes, units, {'facts': raw}, scope_contract=semantic.LABELLED_PRESENTATION_SCOPE_CONTRACT)
        answer = semantic._assign(notes, [field], {'vitals': definition}, facts,
            assignments([field], {'vitals': list(facts)}), scope_contract=semantic.LABELLED_PRESENTATION_SCOPE_CONTRACT)['vitals']
        self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
        self.assertEqual(answer['text'], '; '.join(values))
        self.assertNotIn('derived_presentation', answer)
