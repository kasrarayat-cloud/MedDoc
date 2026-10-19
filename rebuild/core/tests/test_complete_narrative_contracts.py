"""Prospective complete narratives: source ownership, qualifiers and omissions."""
from copy import deepcopy

from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core import complete_narrative_contracts as contracts
from core.tests.test_semantic_generation import fact, assignments
from documents.semantic_preparation_roles import default_definitions


class CompleteNarrativeContractsTests(SimpleTestCase):
    header = 'Patient: Synthetic Ada Tern\nService date: 21 October 2027\nTreating clinician: Dr. Mira Cole\n'
    denial = ('Narrative listing of all documented symptom negatives (symptoms the patient is documented as not having), '
        'each with its exact documented scope such as timing or context. Do not add negatives that are not documented.')
    exam = ('Narrative of the complete documented examination, including both positive and negative findings '
        'with their documented scope. Do not add undocumented findings.')
    medicine = ('Narrative of a stopped historical medicine as documented: name, dose, route, frequency, indication, '
        'dates, response, reason for stopping, and explicit documentation that it is not being used now. '
        'Leave undocumented components blank.')
    exclusions = ('Narrative of documented exclusions from counted time: excluded staff time and prior-day physician '
        'time with minutes, any separately reported service that is excluded, and procedure status today. Include only documented items.')
    history = ('Narrative of the patient’s documented dizziness history: duration, previous and current symptom frequency, '
        'severity and passage of gas. Preserve documented uncertainty and negation; do not infer undocumented details.')

    def run_assignment(self, body, values, meanings, picked, *, profile=None, header=None):
        notes = (self.header if header is None else header) + body
        fields = [{'key': key, 'label': key, 'kind': 'text', 'locator': {'cell': index}}
            for index, key in enumerate(meanings)]
        definitions = default_definitions(fields)
        for key, (meaning, subject, timing, polarity) in meanings.items():
            definitions[key].update(version=2, answer_mode='narrative', meaning=meaning,
                scope={'subject': subject, 'temporality': timing, 'polarity': polarity})
        units, _ = generation.source_units(notes, fields)
        raw = [fact(notes, fields, key, value[0], kind=value[1], polarity=value[2], timing=value[3],
            subject=value[4] if len(value) > 4 else 'patient') for key, value in values.items()]
        before = deepcopy(raw)
        profile = profile or semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT
        validated = semantic.validate_facts(notes, units, {'facts': raw}, scope_contract=profile)
        result = semantic._assign(notes, fields, definitions, validated, assignments(fields, picked), scope_contract=profile)
        self.assertEqual(raw, before)
        return result, validated

    def assert_supported(self, result, key):
        self.assertEqual(result[key]['status'], 'supported', result[key]['review_reasons'])

    def test_denial_unspecified_annotation_requires_complete_current_source(self):
        source = 'She denies fever, painful swallowing and severe abdominal pain'
        meaning = {'negative': (self.denial, 'patient', 'any', 'negative')}
        for value in (source, source.removeprefix('She ')):
            result, facts = self.run_assignment('S\n' + source + '.', {'f': (value, 'finding', 'negated', 'unspecified')}, meaning, {'negative': ['f']})
            self.assert_supported(result, 'negative')
            self.assertEqual(facts['f']['timing']['kind'], 'unspecified')
            self.assertEqual(result['negative']['text'], value[0].upper()+value[1:])
        result, _ = self.run_assignment('S\n' + source + '.', {'f': ('denies fever', 'finding', 'negated', 'unspecified')}, meaning, {'negative': ['f']})
        self.assertNotEqual(result['negative']['status'], 'supported')

    def test_denial_does_not_acquire_current_or_patient_ownership_from_annotations(self):
        meaning = {'negative': (self.denial, 'patient', 'any', 'negative')}
        for body in ('Past medical history\nShe denies fever.', 'Family history\nShe denies fever.', 'Previous encounter\nShe denies fever.', 'Future encounter\nShe denies fever.',
                'S\nIf she denies fever, call tomorrow.', 'S\nShe denies fever except at night.'):
            quote = body.split('\n')[-1].removesuffix('.')
            result, _ = self.run_assignment(body, {'f': (quote, 'finding', 'negated', 'unspecified')}, meaning, {'negative': ['f']})
            self.assertNotEqual(result['negative']['status'], 'supported', body)
        result, _ = self.run_assignment('S\nShe denies fever.', {'f': ('She denies fever', 'finding', 'negated', 'unspecified')},
            meaning, {'negative': ['f']}, header='')
        self.assertNotEqual(result['negative']['status'], 'supported')

    def test_complete_mixed_exam_keeps_every_literal_and_unknown_tail_holds(self):
        source = 'The abdomen is soft and nondistended, with normal bowel sounds and no tenderness, guarding or rebound'
        values = {'f': (source, 'finding', 'mixed', 'current')}
        for meaning in (self.exam, self.exam.replace('Narrative of', 'Narrative description of')):
            result, _ = self.run_assignment('O\n' + source + '.', values,
                {'objective': (meaning, 'patient', 'current', 'any')}, {'objective': ['f']})
            self.assert_supported(result, 'objective')
            self.assertEqual(result['objective']['text'], source)
        for tail in (' Omit normal findings.', ' Except guarding.', ' Use the convenient subset.', ' Include positive findings only.'):
            result, _ = self.run_assignment('O\n' + source + '.', values,
                {'objective': (self.exam + tail, 'patient', 'current', 'any')}, {'objective': ['f']})
            self.assertNotEqual(result['objective']['status'], 'supported', tail)

    def trial(self, meaning=None, selection=None, *, medicine='cetirizine', date='8 October'):
        trial = f'She previously took {medicine} 10 mg by mouth each evening for itching from 2 October through 7 October 2027'
        response = 'It gave no meaningful relief'
        stopped = f'She stopped it on {date} because it was not helping and is no longer taking {medicine}'
        values = {'trial': (trial.removeprefix('She previously took '), 'history', 'affirmed', 'past'),
            'response': (response, 'history', 'negated', 'past'),
            'stop': (stopped.split(' and ')[0], 'history', 'affirmed', 'past'),
            'current': (f'no longer taking {medicine}', 'history', 'negated', 'current')}
        return self.run_assignment('S\n' + trial + '. ' + response + '. ' + stopped + '.', values,
            {'prior': (meaning or self.medicine, 'patient', 'past', 'any')},
            {'prior': list(values) if selection is None else selection})

    def test_historical_trial_support_retains_current_nonuse_and_every_attribute(self):
        for medicine in ('cetirizine', 'Unfamiliarzine'):
            result, facts = self.trial(medicine=medicine)
            self.assert_supported(result, 'prior')
            self.assertEqual(facts['current']['timing']['kind'], 'current')
            self.assertIn('no longer taking ' + medicine.casefold(), result['prior']['text'].casefold())
        for missing in ('trial', 'response', 'stop', 'current'):
            result, _ = self.trial(selection=[key for key in ('trial', 'response', 'stop', 'current') if key != missing])
            self.assertNotEqual(result['prior']['status'], 'supported', missing)

    def test_historical_trial_unknown_meaning_or_invalid_dates_remain_held(self):
        for tail in (' Omit current non-use.', ' Add undocumented details.', ' Leave out response.'):
            result, _ = self.trial(meaning=self.medicine + tail)
            self.assertNotEqual(result['prior']['status'], 'supported')
        for date in ('1 October', '30 October'):
            result, _ = self.trial(date=date)
            self.assertNotEqual(result['prior']['status'], 'supported')

    def test_documentation_only_instruction_preserves_typed_exclusion_scope(self):
        definition = {'meaning': self.exclusions, 'answer_mode': 'narrative', 'value_type': 'text',
            'scope': {'subject': 'encounter', 'temporality': 'any', 'polarity': 'any'}}
        self.assertFalse(contracts.restricted_support_destination(definition))
        self.assertTrue(contracts.support_obligation_requested(definition, 'physician_time_exclusions', ''))
        self.assertTrue(contracts.support_obligation_requested(definition, 'nonperformance', 'No procedure was performed today'))
        self.assertFalse(contracts.support_obligation_requested(definition, 'nonperformance',
            'No blood sample was collected today, the test was not performed today and no result is available'))
        self.assertIsNone(contracts.support_obligation_requested(definition, 'nonperformance', 'No blood test or endoscopy was performed today'))
        for tail in (' Omit staff time.', ' Except procedures.', ' Ignore unknown limitations.'):
            changed = {**definition, 'meaning': self.exclusions + tail}
            self.assertTrue(contracts.restricted_support_destination(changed))
            self.assertIsNone(contracts.support_obligation_requested(changed, 'nonperformance', 'No blood sample was collected today'))

    def test_procedure_only_does_not_require_unrelated_test_nonperformance(self):
        test = 'No blood sample was collected today, the test was not performed today and no result is available'
        procedure = 'No procedure was performed during this encounter'
        result, _ = self.run_assignment('P\n' + test + '. ' + procedure + '.',
            {'procedure': (procedure, 'finding', 'negated', 'current')},
            {'exclusions': (self.exclusions, 'encounter', 'any', 'any')}, {'exclusions': ['procedure']})
        self.assert_supported(result, 'exclusions')
        result, _ = self.run_assignment('P\n' + test + '. ' + procedure + '.', {},
            {'exclusions': (self.exclusions, 'encounter', 'any', 'any')}, {'exclusions': []})
        self.assertEqual(result['exclusions']['status'], 'conflict')
        self.assertTrue(any(procedure in reason for reason in result['exclusions']['review_reasons']))

    def test_narrative_investigation_keeps_order_and_each_actual_status(self):
        meaning = ('Narrative of the investigation ordered: the evaluation purpose, intended collection timing, '
            'and the actual status today of collection, performance and result. '
            'Keep intended and actual status distinct; do not state a result unless documented.')
        order = 'I ordered a urine culture to evaluate for urinary infection, with collection planned tomorrow'
        status = 'No blood sample was collected today, the test was not performed today and no result is available'
        values = {'order': (order, 'plan', 'affirmed', 'current'), 'status': (status, 'finding', 'negated', 'current')}
        for selected in (['order', 'status'], ['status'], ['order']):
            result, _ = self.run_assignment('P\n' + order + '. ' + status + '.', values,
                {'investigation': (meaning, 'patient', 'any', 'any')}, {'investigation': selected})
            if len(selected) == 2:
                self.assert_supported(result, 'investigation')
            else:
                self.assertEqual(result['investigation']['status'], 'conflict')

    def test_documentation_only_time_definition_never_authorizes_excluded_or_negative_time(self):
        meaning = ('Concise narrative of the documented E/M selection basis, total physician time, service date, '
            'and each included activity with its minutes. Include only documented activities and times.')
        d = {'meaning': meaning, 'answer_mode': 'narrative', 'value_type': 'text',
            'scope': {'subject': 'encounter', 'temporality': 'current', 'polarity': 'positive'}}
        before = deepcopy(d)
        self.assertFalse(contracts.restricted_support_destination(d))
        for kind in ('physician_time_basis', 'physician_time_activities', 'physician_time_qualification'):
            self.assertTrue(contracts.support_obligation_requested(d, kind, ''))
        self.assertFalse(contracts.support_obligation_requested(d, 'physician_time_exclusions', ''))
        self.assertFalse(contracts.support_obligation_requested(d, 'nonperformance', 'No procedure was performed today'))
        self.assertEqual(d, before)
        self.assertTrue(contracts.restricted_support_destination({**d, 'meaning': meaning + ' Exclude prior review.'}))

    def test_source_first_separation_holds_even_if_extractor_has_no_fact(self):
        relation = 'The dizziness is a separate concern from the tinnitus'
        body = 'S\nShe reports dizziness. ' + relation + '.'
        meanings = {'history': (self.history, 'patient', 'any', 'any')}
        values = {'symptom': ('dizziness', 'finding', 'affirmed', 'current')}
        result, _ = self.run_assignment(body, values, meanings, {'history': ['symptom']})
        self.assertEqual(result['history']['status'], 'conflict')
        self.assertTrue(any(relation in reason for reason in result['history']['review_reasons']))
        result, _ = self.run_assignment(body, {}, meanings, {'history': []})
        self.assertEqual(result['history']['status'], 'conflict')
        values['relation'] = (relation, 'history', 'affirmed', 'current')
        result, _ = self.run_assignment(body, values, meanings, {'history': ['symptom', 'relation']})
        self.assert_supported(result, 'history')
        self.assertIn(relation, result['history']['text'])

    def test_separation_topic_ownership_qualifiers_and_exact_spans(self):
        from core.clinical_source_context import source_context
        for source, unresolved in (('The dizziness is a separate concern from the tinnitus.', False),
                ('The dizziness may be a separate concern from the tinnitus.', True),
                ('The dizziness is not a separate concern from the tinnitus.', True),
                ('The dizziness is a separate concern from the tinnitus except at night.', True)):
            notes = self.header + 'S\n' + source
            units, _ = generation.source_units(notes, [])
            d = {'meaning': self.history, 'answer_mode': 'narrative', 'value_type': 'text',
                'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
            rows = semantic._separation_inventory(notes, {'h': d}, units,
                source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)))
            self.assertEqual(len(rows), 1, source)
            self.assertEqual(rows[0]['unresolved'], unresolved, source)
            for field in ('source', 'first', 'second', 'predicate'):
                span = rows[0][field]
                self.assertEqual(notes[span['start']:span['end']], span['quote'])
        # A current symptom answer does not inherit a relative's relation.
        result, _ = self.run_assignment('Family history\nThe dizziness is a separate concern from the tinnitus.', {},
            {'history': (self.history, 'patient', 'any', 'any')}, {'history': []})
        self.assertEqual(result['history']['status'], 'missing')

    def test_unparsed_separation_modifiers_cannot_erase_source_obligation(self):
        from core.clinical_source_context import source_context
        meanings = {'history': (self.history, 'patient', 'any', 'any')}
        variants = ('The dizziness is usually a separate concern from the tinnitus.',
            'The dizziness is reportedly a separate concern from the tinnitus.',
            'Apparently, the dizziness is a separate concern from the tinnitus.',
            'According to an unresolved account, the dizziness is a separate problem from the tinnitus.',
            'The dizziness could represent a separate concern from the tinnitus.')
        for source in variants:
            body = 'S\nShe reports dizziness. ' + source
            result, _ = self.run_assignment(body, {'f': ('dizziness', 'finding', 'affirmed', 'current')},
                meanings, {'history': ['f']})
            self.assertEqual(result['history']['status'], 'conflict', source)
            self.assertTrue(any(source in reason for reason in result['history']['review_reasons']), source)
            # Even a full extracted literal cannot promote unresolved syntax.
            result, _ = self.run_assignment(body, {'f': (source.removesuffix('.'), 'history', 'affirmed', 'current')},
                meanings, {'history': ['f']})
            self.assertNotEqual(result['history']['status'], 'supported', source)
            notes = self.header + body
            units, _ = generation.source_units(notes, [])
            d = {'meaning': self.history, 'answer_mode': 'narrative', 'value_type': 'text',
                'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
            rows = semantic._separation_inventory(notes, {'history': d}, units,
                source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertTrue(row['unresolved'])
            self.assertEqual(row['source']['quote'], source)
            self.assertNotIn('first', row)
            for item in [row['source'], *row['topic_mentions'], *row['relation_markers']]:
                self.assertEqual(notes[item['start']:item['end']], item['quote'])

    def test_complete_relation_keeps_its_first_topic_destination(self):
        from core.clinical_source_context import source_context
        notes = self.header + 'S\nThe dizziness is a separate concern from the tinnitus.'
        units, _ = generation.source_units(notes, [])
        d = {'meaning': self.history, 'answer_mode': 'narrative', 'value_type': 'text',
            'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
        rows = semantic._separation_inventory(notes,
            {'first': d, 'second': {**d, 'meaning': self.history.replace('dizziness', 'tinnitus')}}, units,
            source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)))
        self.assertEqual([row['field_key'] for row in rows], ['first'])
        self.assertFalse(rows[0]['unresolved'])

    def test_unknown_history_meaning_cannot_erase_or_discharge_source_relation(self):
        relation = 'The dizziness is a separate concern from the tinnitus'
        body = 'S\nShe reports dizziness. ' + relation + '.'
        symptom = {'symptom': ('dizziness', 'finding', 'affirmed', 'current')}
        all_values = {**symptom, 'relation': (relation, 'history', 'affirmed', 'current')}
        for tail in (' Use the convenient subset.', ' Preserve its complete clinical meaning.',
                ' Omit relationship details.'):
            meaning = {'history': (self.history + tail, 'patient', 'any', 'any')}
            for values, selected in (({}, []), (symptom, ['symptom']),
                    (all_values, ['symptom']), (all_values, ['symptom', 'relation'])):
                with self.subTest(tail=tail, selected=selected, extracted=list(values)):
                    result, _ = self.run_assignment(body, values, meaning, {'history': selected})
                    self.assertEqual(result['history']['status'], 'conflict')
                    self.assertTrue(any(relation in reason for reason in result['history']['review_reasons']))

    def test_unknown_history_prefix_attributes_and_ownership_keep_literal_evidence(self):
        from core.clinical_source_context import source_context
        variants = (self.history.replace('Narrative of', 'Complete narrative of'),
            self.history.replace('Narrative of', 'Concise narrative of'),
            self.history.replace('Narrative of', 'Requested account of'),
            self.history.replace('severity and passage of gas', 'unclassified detail and convenience'),
            self.history.replace('patient’s', 'unresolved narrator’s'))
        for meaning in variants:
            for source in ('The dizziness is a separate concern from the tinnitus.',
                    'Apparently, the dizziness is a separate concern from the tinnitus.'):
                with self.subTest(meaning=meaning, source=source):
                    body = 'S\nShe reports dizziness. ' + source
                    result, _ = self.run_assignment(body,
                        {'relation': (source.removesuffix('.'), 'history', 'affirmed', 'current')},
                        {'h': (meaning, 'patient', 'any', 'any')}, {'h': ['relation']})
                    self.assertEqual(result['h']['status'], 'conflict')
                    notes = self.header + body
                    units, _ = generation.source_units(notes, [])
                    d = {'meaning': meaning, 'answer_mode': 'narrative', 'value_type': 'text',
                        'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
                    rows = semantic._separation_inventory(notes, {'h': d}, units,
                        source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)))
                    self.assertEqual(len(rows), 1)
                    row = rows[0]
                    self.assertTrue(row['unresolved'])
                    self.assertTrue(row['definition_unresolved'])
                    self.assertEqual(row['source']['quote'], source)
                    self.assertEqual(row['definition_meaning'], {'start': 0, 'end': len(meaning), 'quote': meaning})
                    self.assertNotIn('first', row)
                    for item in [row['source'], *row['topic_mentions'], *row['relation_markers']]:
                        self.assertEqual(notes[item['start']:item['end']], item['quote'])
                    for item in [row['definition_history_header'], *row['definition_mentions']]:
                        self.assertEqual(meaning[item['start']:item['end']], item['quote'])

    def test_positive_history_retains_affirmative_relation_completeness(self):
        relation = 'The dizziness is a separate concern from the tinnitus'
        body = 'S\nShe reports dizziness. ' + relation + '.'
        symptom = {'symptom': ('dizziness', 'finding', 'affirmed', 'current')}
        both = {**symptom, 'relation': (relation, 'history', 'affirmed', 'current')}
        for polarity in ('any', 'positive'):
            for tail in ('', ' Use the convenient subset.'):
                meanings = {'h': (self.history + tail, 'patient', 'any', polarity)}
                for values, selected in (({}, []), (symptom, ['symptom']),
                        (both, ['symptom']), (both, ['symptom', 'relation'])):
                    with self.subTest(polarity=polarity, tail=tail, selected=selected, extracted=list(values)):
                        result, _ = self.run_assignment(body, values, meanings, {'h': selected})
                        if not tail and selected == ['symptom', 'relation']:
                            self.assert_supported(result, 'h')
                        else:
                            self.assertEqual(result['h']['status'], 'conflict')
                            self.assertTrue(any(relation in reason for reason in result['h']['review_reasons']))

    def test_positive_history_does_not_promote_negative_or_uncertain_relation(self):
        for predicate, polarity in (('is not', 'negated'), ('may be', 'uncertain'), ('is reportedly', 'affirmed')):
            relation = f'The dizziness {predicate} a separate concern from the tinnitus'
            result, _ = self.run_assignment('S\n' + relation + '.',
                {'relation': (relation, 'history', polarity, 'current')},
                {'h': (self.history, 'patient', 'any', 'positive')}, {'h': ['relation']})
            self.assertNotEqual(result['h']['status'], 'supported', predicate)
            self.assertTrue(any(relation in reason for reason in result['h']['review_reasons']))

    def test_instruction_tail_cannot_add_another_history_topic(self):
        from core.clinical_source_context import source_context
        relation = 'The dizziness is a separate concern from the tinnitus.'
        body = 'S\nShe reports nausea. ' + relation
        notes = self.header + body
        units, _ = generation.source_units(notes, [])
        context = source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT))
        for tail in ('', ' Do not include dizziness history.', ' Omit dizziness history.',
                ' Exclude dizziness history.', ' Preserve its complete clinical meaning.'):
            meaning = self.history.replace('dizziness', 'nausea') + tail
            for polarity in ('any', 'positive'):
                result, _ = self.run_assignment(body, {'n': ('nausea', 'finding', 'affirmed', 'current')},
                    {'h': (meaning, 'patient', 'any', polarity)}, {'h': ['n']})
                self.assert_supported(result, 'h')
                d = {'meaning': meaning, 'answer_mode': 'narrative', 'value_type': 'text',
                    'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': polarity}}
                self.assertEqual(semantic._separation_inventory(notes, {'h': d}, units, context), [])
        for meaning in ('Do not include dizziness history.', 'Exclude dizziness history.'):
            d = {'meaning': meaning, 'answer_mode': 'narrative', 'value_type': 'text',
                'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
            self.assertEqual(semantic._separation_inventory(notes, {'h': d}, units, context), [])

    def test_unknown_definition_floor_keeps_history_topic_and_owner_boundaries(self):
        from core.clinical_source_context import source_context
        meaning = self.history + ' Use the convenient subset.'
        d = {'meaning': meaning, 'answer_mode': 'narrative', 'value_type': 'text',
            'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
        variants = ({**d, 'meaning': meaning.replace('dizziness', 'tinnitus')},
            {**d, 'meaning': meaning.replace('dizziness', 'dizzi')},
            {**d, 'meaning': meaning.replace('history', 'examination')},
            {**d, 'answer_mode': 'concise'},
            {**d, 'value_type': 'person_name'},
            *({**d, 'scope': {**d['scope'], 'subject': owner}} for owner in ('family', 'clinician', 'other')),
            {**d, 'scope': {**d['scope'], 'temporality': 'past'}})
        notes = self.header + 'S\nThe dizziness is a separate concern from the tinnitus.'
        units, _ = generation.source_units(notes, [])
        context = source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT))
        for other in variants:
            self.assertEqual(semantic._separation_inventory(notes, {'h': other}, units, context), [], other)
        for body in ('Family history\nThe dizziness is a separate concern from the tinnitus.',
                'Previous encounter\nThe dizziness is a separate concern from the tinnitus.',
                'S\n"The dizziness is a separate concern from the tinnitus."',
                'S\nHer mother states that the dizziness is a separate concern from the tinnitus.'):
            notes = self.header + body
            units, _ = generation.source_units(notes, [])
            self.assertEqual(semantic._separation_inventory(notes, {'h': d}, units,
                source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT))), [], body)

    def test_unparsed_separation_foreign_past_and_quoted_accounts_supply_no_patient_relation(self):
        from core.clinical_source_context import source_context
        relation = 'The dizziness is reportedly a separate concern from the tinnitus.'
        d = {'meaning': self.history, 'answer_mode': 'narrative', 'value_type': 'text',
            'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}}
        for body in ('Family history\n' + relation, 'Previous encounter\n' + relation,
                'S\n"' + relation + '"', 'S\nHer mother states that the dizziness is a separate concern from the tinnitus.'):
            notes = self.header + body
            units, _ = generation.source_units(notes, [])
            rows = semantic._separation_inventory(notes, {'h': d}, units,
                source_context(notes, units, profile=semantic._source_profile(semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)))
            self.assertEqual(rows, [], body)

    def test_old_v21_retains_original_false_hold_and_no_new_omission(self):
        result, _ = self.run_assignment('S\nShe denies fever.', {'f': ('denies fever', 'finding', 'negated', 'unspecified')},
            {'negative': (self.denial, 'patient', 'any', 'negative')}, {'negative': ['f']}, profile=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        self.assertNotEqual(result['negative']['status'], 'supported')
        result, _ = self.run_assignment('S\nThe dizziness is a separate concern from the tinnitus.', {},
            {'history': (self.history, 'patient', 'any', 'any')}, {'history': []}, profile=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        self.assertEqual(result['history']['status'], 'missing')

    def test_v22_extractor_receives_source_first_inventory_without_synthesized_facts(self):
        notes = self.header + 'S\nThe dizziness is a separate concern from the tinnitus.'
        fields = [{'key': 'h', 'label': 'history', 'kind': 'text', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['h'].update(version=2, answer_mode='narrative', meaning=self.history,
            scope={'subject': 'patient', 'temporality': 'any', 'polarity': 'any'})
        class Stop(Exception): pass
        calls = []
        def send(*args):
            calls.append(args)
            raise Stop
        for profile in (semantic.SOAP_ASSERTION_SCOPE_CONTRACT, semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT):
            with self.assertRaises(Stop):
                semantic.run(notes, fields, definitions, send, scope_contract=profile)
            payload, instructions = calls[-1][2], calls[-1][4]
            if profile == semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT:
                self.assertEqual(len(payload['source_separation_inventory']), 1)
                self.assertIn('cannot be repaired by assignment alone', instructions)
                self.assertNotIn('facts', payload)
            else:
                self.assertNotIn('source_separation_inventory', payload)
                self.assertNotIn('cannot be repaired by assignment alone', instructions)
