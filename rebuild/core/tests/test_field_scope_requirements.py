"""Prospective complete-meaning obligations and truthful held-evidence feedback."""
from copy import deepcopy
import unittest
from django.core.exceptions import ValidationError

from core import generation, semantic_generation as semantic, clinical_semantics as model
from core import clinical_field_scope as scope
from core.tests.test_semantic_generation import fact, assignments, FixtureSender
from documents.semantic_preparation_roles import default_definitions


class FieldScopeRequirementsTests(unittest.TestCase):
    header = 'Patient: Synthetic Inez Vale\nDate of service: 21 October 2027\nTreating clinician: Dr. Mira Cole\n'

    def definition(self, meaning):
        fields = [{'key':'answer', 'label':'Arbitrary destination', 'kind':'text', 'locator':{'cell':0}}]
        definitions = default_definitions(fields)
        definitions['answer'].update(version=2, answer_mode='narrative', meaning=meaning,
            scope={'subject':'patient','temporality':'any','polarity':'any'})
        return fields, definitions

    def run_assignment(self, meaning, body, specs, picked, *, profile=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
            polarity='any'):
        notes = self.header + body
        fields, definitions = self.definition(meaning)
        definitions['answer']['scope']['polarity']=polarity
        units, _ = generation.source_units(notes, fields)
        raw = {'facts':[fact(notes, fields, key, quote, kind=kind, polarity=polarity, timing=timing)
            for key, quote, kind, polarity, timing in specs]}
        before = deepcopy(raw)
        facts = semantic.validate_facts(notes, units, raw, scope_contract=profile,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
        answer = semantic._assign(notes, fields, definitions, facts, assignments(fields, {'answer':picked}),
            scope_contract=profile, timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
        self.assertEqual(raw, before)
        return answer, facts, notes, fields, definitions, raw

    def test_explicit_requested_groups_are_union_and_missing_group_still_blocks(self):
        exam, assessment = 'She appears comfortable', 'The cause remains uncertain'
        args = ('Objective: observations, examination findings and assessment.',
            'Objective\n'+exam+'.\nAssessment\n'+assessment+'.',
            [('exam',exam,'finding','affirmed','current'),('assessment',assessment,'assessment','uncertain','current')])
        complete, *_ = self.run_assignment(*args, ['exam','assessment'])
        missing, *_ = self.run_assignment(*args, ['exam'])
        self.assertEqual(complete['status'], 'supported', complete['review_reasons'])
        self.assertNotEqual(missing['status'], 'supported')
        self.assertTrue(any(assessment in reason and 'omits' in reason for reason in missing['review_reasons']))

    def scoped_polarity_assignment(self, polarity, body, specs, picked, *, meaning='Objective: examination findings.'):
        notes=self.header+body
        fields,definitions=self.definition(meaning)
        definitions['answer']['scope']['polarity']=polarity
        units,_=generation.source_units(notes,fields)
        raw={'facts':[fact(notes,fields,key,quote,kind='finding',polarity=tag)
            for key,quote,tag in specs]}
        original=deepcopy(raw)
        facts=semantic.validate_facts(notes,units,raw,scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
        answer=semantic._assign(notes,fields,definitions,facts,assignments(fields,{'answer':picked}),
            scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
        self.assertEqual(raw,original)
        return answer,facts,notes,definitions

    def test_compiled_meaning_polarity_scopes_obligations_exactly_like_scope_flag(self):
        positive,negative='She appears comfortable','No abdominal tenderness is observed'
        body='Objective\n'+positive+'. '+negative+'.'
        specs=[('positive',positive,'affirmed'),('negative',negative,'negated')]
        for polarity,picked,allowed in [('positive',['positive'],['affirmed']),('negative',['negative'],['negated'])]:
            with self.subTest(polarity=polarity):
                flagged,*_=self.scoped_polarity_assignment(polarity,body,specs,picked)
                prose,_,_,definitions=self.scoped_polarity_assignment('any',body,specs,picked,
                    meaning='Objective: examination findings. '+polarity.title()+' findings only.')
                compiled=model.field_requirements(definitions['answer'],contract=scope.CONTRACT)
                self.assertEqual(compiled['allowed_fact_polarities'],allowed)
                self.assertEqual(prose['status'],flagged['status'])
                self.assertEqual(prose['status'],'supported',prose['review_reasons'])
                self.assertEqual(prose['review_reasons'],flagged['review_reasons'])
                wrong,*_=self.scoped_polarity_assignment('any',body,specs,['positive','negative'],
                    meaning=definitions['answer']['meaning'])
                self.assertNotEqual(wrong['status'],'supported')
                self.assertTrue(any('polarity' in reason for reason in wrong['review_reasons']))
        # A genuine flag/meaning conflict remains held by the existing scope
        # readers. Consuming the compiled list cannot normalize it away.
        for picked in (['positive'],['negative']):
            contradictory,*_=self.scoped_polarity_assignment('positive',body,specs,picked,
                meaning='Objective: examination findings. Negative findings only.')
            self.assertNotEqual(contradictory['status'],'supported')
            self.assertTrue(any('polarity' in reason for reason in contradictory['review_reasons']))

    def test_polarity_scopes_source_obligations_and_never_licenses_wrong_selected_facts(self):
        positive,negative,uncertain='She appears comfortable','No abdominal tenderness is observed','The skin may be dry'
        specs=[('positive',positive,'affirmed'),('negative',negative,'negated'),('uncertain',uncertain,'uncertain')]
        body='Objective\n'+positive+'. '+negative+'. '+uncertain+'.'
        for polarity,selected in [('positive',['positive']),('negative',['negative'])]:
            with self.subTest(polarity=polarity):
                answer,*_=self.scoped_polarity_assignment(polarity,body,specs,selected)
                self.assertEqual(answer['status'],'supported',answer['review_reasons'])
                wrong,*_=self.scoped_polarity_assignment(polarity,body,specs,['positive','negative'])
                self.assertNotEqual(wrong['status'],'supported')
                self.assertTrue(any('polarity' in reason for reason in wrong['review_reasons']))
        missing,*_=self.scoped_polarity_assignment('any',body,specs,['positive'])
        self.assertTrue(any(negative in reason and 'omits' in reason for reason in missing['review_reasons']))
        self.assertTrue(any(uncertain in reason and 'omits' in reason for reason in missing['review_reasons']))
        for quote in ('Abdominal tenderness is absent','The skin is not dry'):
            with self.subTest(negative_predicate=quote):
                specs=[('positive',positive,'affirmed'),('negative',quote,'negated')]
                for polarity,picked in [('positive',['positive']),('negative',['negative'])]:
                    answer,*_=self.scoped_polarity_assignment(polarity,'Objective\n'+positive+'. '+quote+'.',specs,picked)
                    self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        report='She reports no abdominal pain'
        self.assertEqual(scope.predicate_scopes({'start':0,'end':len(report),'quote':report})[0]['polarity'],'negated')

    def test_independent_same_unit_predicates_have_separate_polarity_with_exact_source_spans(self):
        first,second='She appears comfortable','no abdominal tenderness is observed'
        for separator in (' and ','; ',' but '):
            with self.subTest(separator=separator):
                body='Objective\n'+first+separator+second+'.'
                for polarity,picked in [('positive',['positive']),('negative',['negative'])]:
                    answer,_,notes,_=self.scoped_polarity_assignment(polarity,body,
                        [('positive',first,'affirmed'),('negative',second,'negated')],picked)
                    self.assertEqual(answer['status'],'supported',answer['review_reasons'])
                evidence={'start':notes.index(first),'end':len(notes),'quote':notes[notes.index(first):]}
                predicates=scope.predicate_scopes(evidence)
                self.assertEqual([item['polarity'] for item in predicates],['affirmed','negated'])
                for item in predicates:
                    own=item['source_evidence'];self.assertEqual(notes[own['start']:own['end']],own['quote'])

    def test_denied_relative_object_cannot_be_reclassified_as_an_independent_affirmed_predicate(self):
        prefix='She denies nausea'
        for tail in ('pain that is severe','vomiting that is frequent','pain which is severe'):
            with self.subTest(tail=tail):
                whole=prefix+' and '+tail
                omitted,*_=self.run_assignment('Subjective: reported symptoms.','Subjective\n'+whole+'.',
                    [('negative',prefix,'history','negated','current')],['negative'],polarity='negative')
                self.assertNotEqual(omitted['status'],'supported')
                self.assertTrue(any('omits' in reason or 'cannot be independently partitioned' in reason
                    for reason in omitted['review_reasons']))
                complete,*_=self.run_assignment('Subjective: reported symptoms.','Subjective\n'+whole+'.',
                    [('negative',whole,'history','negated','current')],['negative'],polarity='negative')
                self.assertEqual(complete['status'],'supported',complete['review_reasons'])
                predicates=scope.predicate_scopes({'start':0,'end':len(whole),'quote':whole})
                self.assertEqual(len(predicates),1)
                self.assertEqual(predicates[0]['polarity'],'negated')
                self.assertEqual(predicates[0]['matrix_evidence']['predicate']['quote'],'denies')
        for tail in ('she reports pain that is severe','the skin is dry','the skin may be dry'):
            with self.subTest(independent=tail):
                whole=prefix+' and '+tail
                answer,*_=self.run_assignment('Subjective: reported symptoms.','Subjective\n'+whole+'.',
                    [('negative',prefix,'history','negated','current')],['negative'],polarity='negative')
                self.assertEqual(answer['status'],'supported',answer['review_reasons'])

    def test_matrix_copula_cannot_absorb_a_relative_clause_or_prior_matrix_predicate(self):
        for quote in ('The skin that is dry is not tender','The skin that is dry may be normal',
                'The skin is dry and the pain that is severe is not present',
                'She reports pain that is not severe'):
            with self.subTest(quote=quote):
                predicates=scope.predicate_scopes({'start':17,'end':17+len(quote),'quote':quote})
                self.assertEqual(len(predicates),1)
                self.assertEqual(predicates[0]['polarity'],'unresolved')
                matrix=predicates[0]['matrix_evidence']
                if quote.startswith('The skin that'):
                    self.assertIsNone(matrix)
                elif quote.startswith('The skin is'):
                    self.assertEqual(matrix['predicate']['quote'],'is')
                else:
                    self.assertEqual(matrix['predicate']['quote'],'reports')
                if matrix:
                    for part in matrix.values():
                        self.assertEqual(quote[part['start']-17:part['end']-17],part['quote'])

    def test_unpartitioned_mixed_predicate_is_scope_hold_and_denial_list_never_becomes_positive(self):
        mixed='The abdomen is soft without guarding'
        for polarity in ('positive','negative'):
            answer,*_=self.scoped_polarity_assignment(polarity,'Objective\n'+mixed+'.',
                [('whole',mixed,'affirmed')],['whole'])
            self.assertNotEqual(answer['status'],'supported')
            self.assertTrue(any('cannot be independently partitioned' in reason for reason in answer['review_reasons']))
            self.assertFalse(any('omits' in reason for reason in answer['review_reasons']))
        evidence={'start':12,'end':12+len('She denies fever, cough and nausea'),'quote':'She denies fever, cough and nausea'}
        predicates=scope.predicate_scopes(evidence)
        self.assertEqual(len(predicates),1)
        self.assertEqual(predicates[0]['polarity'],'negated')
        for quote in ('She may have nausea and reports wrist pain', 'She denies fever or has wrist pain',
                'No doubt she has wrist pain', 'She reports pain if she walks',
                'She reports abdominal pain with possible radiation',
                'No abdominal tenderness is observed with wrist pain'):
            with self.subTest(unresolved=quote):
                self.assertEqual(scope.predicate_scopes({'start':0,'end':len(quote),'quote':quote})[0]['polarity'],'unresolved')
        date='She reports wrist pain since 18 May 2027'
        self.assertEqual(scope.predicate_scopes({'start':0,'end':len(date),'quote':date})[0]['polarity'],'affirmed')
        for quote in ('She reports abdominal pain with possible radiation',
                'No abdominal tenderness is observed with wrist pain'):
            answer,*_=self.scoped_polarity_assignment('positive',
                'Objective\nShe appears comfortable. '+quote+'.',
                [('positive','She appears comfortable','affirmed')],['positive'])
            self.assertNotEqual(answer['status'],'supported')
            self.assertTrue(any('cannot be independently partitioned' in reason for reason in answer['review_reasons']))

    def test_content_exclusion_without_a_domain_blocks_literal_inclusion_and_allows_remaining_exam(self):
        whole = 'The abdomen is soft with normal bowel sounds'
        specs = [('whole',whole,'finding','affirmed','current'),
            ('soft','The abdomen is soft','finding','affirmed','current')]
        meaning = 'Objective: examination findings. Exclude normal bowel sounds.'
        blocked, *_ = self.run_assignment(meaning, 'Objective\n'+whole+'.', specs, ['whole'])
        allowed, *_ = self.run_assignment(meaning, 'Objective\n'+whole+'.', specs, ['soft'])
        self.assertNotEqual(blocked['status'],'supported')
        self.assertTrue(any('explicitly excluded' in reason for reason in blocked['review_reasons']))
        self.assertEqual(allowed['status'],'supported',allowed['review_reasons'])

    def test_every_coordinated_exclusion_survives_mixed_groups_and_literal_objects(self):
        quote = 'The abdomen is soft with normal bowel sounds'
        for exclusion in ('assessment and normal bowel sounds', 'normal bowel sounds and assessment',
                'normal bowel sounds and abdominal tenderness', 'abdominal tenderness, assessment and normal bowel sounds'):
            with self.subTest(exclusion=exclusion):
                answer, *_ = self.run_assignment('Objective: examination findings. Exclude '+exclusion+'.',
                    'Objective\n'+quote+'.',[('exam',quote,'finding','affirmed','current')],['exam'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any('explicitly excluded' in reason for reason in answer['review_reasons']))

    def test_nominal_exclusion_copular_candidate_is_scoped_held_with_exact_role_evidence(self):
        for topic,quote in [('normal bowel sounds','The bowel sounds are normal'),
                ('dry skin','The skin is dry'),('clear lungs','The lungs are clear'),
                ('lower back pain','The back pain is lower')]:
            with self.subTest(topic=topic,quote=quote):
                answer,_,notes,fields,definitions,_ = self.run_assignment('Objective: examination findings. Exclude '+topic+'.',
                    'Objective\n'+quote+'.',[('exam',quote,'finding','affirmed','current')],['exam'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any('interpretation remains unresolved' in reason for reason in answer['review_reasons']))
                units,_ = generation.source_units(notes,fields)
                source = next(unit for unit in units if quote in unit['quote'])
                requirement = model.field_requirements(definitions['answer'],contract=scope.CONTRACT)
                matches = scope.exclusion_spans(requirement,source)
                predicate = next(item for item in matches if item['match_kind']=='attribute_predicate_candidate')
                self.assertEqual(predicate['resolution'],'requires_review')
                self.assertEqual(predicate['polarity'],'affirmed')
                for key in ('head_evidence','attribute_evidence','copula_evidence'):
                    evidence = predicate[key]
                    self.assertEqual(notes[evidence['start']:evidence['end']],evidence['quote'])

    def test_exclusion_predicate_negation_uncertainty_and_nonadjacent_word_order_stay_distinct(self):
        meaning = 'Objective: examination findings. Exclude normal bowel sounds.'
        negative = 'The bowel sounds are not normal'
        answer,*_ = self.run_assignment(meaning,'Objective\n'+negative+'.',
            [('exam',negative,'finding','negated','current')],['exam'])
        # Bare exclusion wording leaves its polarity scope unresolved. The
        # earlier affirmative-only assumption is not an approved requirement.
        self.assertNotEqual(answer['status'],'supported')
        self.assertTrue(any('polarity or attribute/head interpretation remains unresolved' in reason for reason in answer['review_reasons']))
        uncertain = 'The bowel sounds may be normal'
        answer,_,notes,fields,definitions,_ = self.run_assignment(meaning,'Objective\n'+uncertain+'.',
            [('exam',uncertain,'finding','uncertain','current')],['exam'])
        self.assertNotEqual(answer['status'],'supported')
        units,_ = generation.source_units(notes,fields)
        source = next(unit for unit in units if uncertain in unit['quote'])
        requirement = model.field_requirements(definitions['answer'],contract=scope.CONTRACT)
        matches = scope.exclusion_spans(requirement,source)
        self.assertEqual([item['polarity'] for item in matches],['uncertain'])
        for quote in ('The bowel sounds are abnormal','Normal sounds are heard near the bowel'):
            evidence = {'start':17,'end':17+len(quote),'quote':quote}
            self.assertEqual(scope.exclusion_spans(requirement,evidence),[])

    def test_unresolved_nominal_partition_cannot_authorize_omitting_required_source(self):
        first,other = 'The abdomen is soft','The back pain is lower'
        answer,*_ = self.run_assignment('Objective: examination findings. Exclude lower back pain.',
            'Objective\n'+first+'. '+other+'.',[('soft',first,'finding','affirmed','current')],['soft'])
        self.assertNotEqual(answer['status'],'supported')
        self.assertTrue(any('interpretation remains unresolved' in reason and other in reason for reason in answer['review_reasons']))
        self.assertTrue(any('omits' in reason and other in reason for reason in answer['review_reasons']))

    def test_stopped_clinical_event_is_required_but_stopped_medicine_is_optional_context(self):
        first = 'She reports wrist pain'
        for other in ('She stopped vomiting yesterday', 'She reports that her headache stopped yesterday'):
            with self.subTest(other=other):
                answer, *_ = self.run_assignment('Subjective: reported symptoms.',
                    'Subjective\n'+first+'. '+other+'.',[('pain',first,'history','affirmed','current')],['pain'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any('omits' in reason and other in reason for reason in answer['review_reasons']))
        answer, *_ = self.run_assignment('Subjective: reported symptoms.',
            'Subjective\n'+first+'. She stopped taking the medicine yesterday.',
            [('pain',first,'history','affirmed','current')],['pain'])
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])

    def test_nested_therapy_or_dose_object_cannot_hide_a_reported_event_or_qualifier(self):
        first = 'She reports wrist pain'
        for other in ('She reports dizziness after taking a medication',
                'She reports taking 5 mL of water provokes coughing',
                'She reports taking a medicine and developed dizziness',
                'She reports wrist pain after her appendix was removed'):
            with self.subTest(other=other):
                answer,*_ = self.run_assignment('Subjective: reported symptoms.',
                    'Subjective\n'+first+'. '+other+'.',[('first',first,'history','affirmed','current')],['first'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any(other in reason and ('omits' in reason or 'unresolved' in reason) for reason in answer['review_reasons']))
        for other in ('She reports taking a medication', 'She is taking a prescribed medicine',
                'She took a medicine yesterday', 'She is taking a daily medication'):
            with self.subTest(complete_primitive=other):
                answer,*_ = self.run_assignment('Subjective: reported symptoms.',
                    'Subjective\n'+first+'. '+other+'.',[('first',first,'history','affirmed','current')],['first'])
                self.assertEqual(answer['status'],'supported',answer['review_reasons'])

    def test_bare_content_exclusion_keeps_direct_and_reordered_negative_polarity_unresolved(self):
        meaning = 'Objective: examination findings. Exclude dry skin.'
        for quote in ('No dry skin is observed','The skin is not dry'):
            with self.subTest(quote=quote):
                answer,_,notes,fields,definitions,_ = self.run_assignment(meaning,'Objective\n'+quote+'.',
                    [('exam',quote,'finding','negated','current')],['exam'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any('polarity or attribute/head interpretation remains unresolved' in reason for reason in answer['review_reasons']))
                self.assertFalse(any('contains content explicitly excluded' in reason for reason in answer['review_reasons']))
                units,_ = generation.source_units(notes,fields)
                source = next(unit for unit in units if quote in unit['quote'])
                requirement = model.field_requirements(definitions['answer'],contract=scope.CONTRACT)
                spans = scope.exclusion_spans(requirement,source)
                self.assertTrue(spans)
                self.assertTrue(all(span['polarity']=='negated' and span['resolution']=='requires_review' for span in spans))
                for span in spans:
                    evidence = span.get('negative_evidence') or span['polarity_evidence'][0]
                    self.assertEqual(notes[evidence['start']:evidence['end']],evidence['quote'])
        positive = 'Dry skin is observed'
        answer,*_ = self.run_assignment(meaning,'Objective\n'+positive+'.',
            [('exam',positive,'finding','affirmed','current')],['exam'])
        self.assertTrue(any('contains content explicitly excluded' in reason for reason in answer['review_reasons']))

    def test_clinical_management_does_not_require_time_account_but_keeps_actual_plan_obligations(self):
        advice = 'She should continue the documented treatment'
        follow = 'Follow-up in four weeks, or earlier if symptoms worsen'
        total = 'Dr. Cole spent 27 minutes on 21 October 2027: examining and counseling the patient'
        same_day = 'The physician performed all of that work on the service date'
        body = 'Plan\n'+advice+'. '+follow+'. '+total+'. '+same_day+'.'
        specs = [('advice',advice,'plan','affirmed','future'),('follow',follow,'follow_up','affirmed','future')]
        complete, *_ = self.run_assignment('Plan: documented treatment, advice and follow-up.',body,specs,['advice','follow'])
        missing, *_ = self.run_assignment('Plan: documented treatment, advice and follow-up.',body,specs,['advice'])
        self.assertEqual(complete['status'],'supported',complete['review_reasons'])
        self.assertTrue(any(follow in reason and 'omits' in reason for reason in missing['review_reasons']))
        explicit, *_ = self.run_assignment('Plan: documented treatment, advice, follow-up and physician time.',body,specs,['advice','follow'])
        self.assertTrue(any(total in reason and 'omits' in reason for reason in explicit['review_reasons']))

    def test_name_and_reported_symptoms_do_not_require_demographics_or_remote_history(self):
        report = 'She reports wrist pain'
        baseline = 'Before this change, she had no wrist pain'
        background = 'She is an established patient. Her appendix was removed in 2003.'
        body = 'Subjective\n'+background+'\n\n'+report+'. '+baseline+'.'
        specs = [('name','Synthetic Inez Vale','identity','affirmed','current'),
            ('report',report,'history','affirmed','current'),('baseline',baseline,'history','negated','past')]
        meaning = 'Subjective: include the documented patient name and reported symptoms, retaining qualifiers and uncertainty.'
        complete, *_ = self.run_assignment(meaning,body,specs,['name','report','baseline'])
        missing, *_ = self.run_assignment(meaning,body,specs,['name','report'])
        self.assertEqual(complete['status'],'supported',complete['review_reasons'])
        self.assertTrue(any(baseline in reason and 'omits' in reason for reason in missing['review_reasons']))
        self.assertFalse(any('appendix' in reason or 'established patient' in reason for reason in missing['review_reasons']))

    def test_present_held_uncertain_evidence_is_not_reported_as_missing_and_cannot_be_supported(self):
        quote = 'An inflammatory condition is possible, but it has not been established'
        answer, facts, *_ = self.run_assignment('Assessment: documented impression and diagnostic uncertainty.',
            'Assessment\n'+quote+'.', [('uncertain',quote,'assessment','affirmed','current')],['uncertain'])
        self.assertTrue(facts['uncertain']['issues'])
        self.assertNotEqual(answer['status'],'supported')
        self.assertIn(quote,answer['candidate_text'])
        self.assertFalse(any('omits' in reason for reason in answer['review_reasons']),answer['review_reasons'])
        self.assertTrue(any('present in the selected text but remains held' in reason for reason in answer['review_reasons']))

    def test_present_held_does_not_hide_a_separate_missing_assessment(self):
        first, second = 'An inflammatory condition is possible', 'The cause remains uncertain'
        answer, *_ = self.run_assignment('Assessment: documented impression and diagnostic uncertainty.',
            'Assessment\n'+first+'. '+second+'.', [('first',first,'assessment','affirmed','current')], ['first'])
        self.assertTrue(any('omits' in reason and second in reason for reason in answer['review_reasons']))
        self.assertFalse(any('omits' in reason and first in reason for reason in answer['review_reasons']))

    def test_unknown_narrow_meaning_does_not_gain_broad_scope(self):
        quote = 'She reports wrist pain'
        answer, *_ = self.run_assignment('Description of urinary fluid history.',
            'Subjective\n'+quote+'.',[('pain',quote,'history','affirmed','current')],['pain'])
        self.assertNotEqual(answer['status'],'supported')
        self.assertTrue(any('verified scope' in reason for reason in answer['review_reasons']))

    def test_unclassified_unselected_subjective_assertion_cannot_silently_disappear(self):
        first, other = 'She reports wrist pain', 'Activity provokes a new sensation'
        answer, *_ = self.run_assignment('Subjective: reported symptoms.',
            'Subjective\n'+first+'.\n\n'+other+'.',[('pain',first,'history','affirmed','current')],['pain'])
        self.assertNotEqual(answer['status'],'supported')
        self.assertTrue(any('source role is unresolved' in reason for reason in answer['review_reasons']))
        partial, *_ = self.run_assignment('Subjective: reported symptoms.',
            'Subjective\n'+first+'.\n\n'+other+'.',
            [('pain',first,'history','affirmed','current'),('partial','a new sensation','history','affirmed','current')],
            ['pain','partial'])
        self.assertNotEqual(partial['status'],'supported')
        self.assertTrue(any('source role is unresolved' in reason for reason in partial['review_reasons']))

    def test_source_owner_and_time_bound_obligations_without_releasing_selected_source_holds(self):
        first = 'She reports wrist pain'
        def assign(body, timing, extra=()):
            fields,definitions = self.definition('Subjective: reported symptoms.')
            definitions['answer']['scope']['temporality'] = timing
            notes = self.header+'Subjective\n'+first+'.'+body
            units,_ = generation.source_units(notes,fields)
            raw = [fact(notes,fields,'pain',first,kind='history')]
            for key,quote,when in extra: raw.append(fact(notes,fields,key,quote,kind='history',timing=when))
            facts = semantic.validate_facts(notes,units,{'facts':raw},scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
                timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
            answer = semantic._assign(notes,fields,definitions,facts,assignments(fields,{'answer':list(facts)}),
                scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
                timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
            return answer,facts
        prior = '\n\nPrior encounter\nShe reported nausea.'
        local = ' Before this visit, she reported nausea.'
        for body in (prior,local):
            with self.subTest(current_only=body):
                current,_ = assign(body,'current')
                self.assertEqual(current['status'],'supported',current['review_reasons'])
                all_time,_ = assign(body,'any')
                self.assertNotEqual(all_time['status'],'supported')
                self.assertTrue(any('nausea' in reason and 'omits' in reason for reason in all_time['review_reasons']))
                self.assertFalse(any('source role is unresolved' in reason and 'Prior encounter' in reason for reason in all_time['review_reasons']))
        complete,_ = assign(prior,'any',[('past','She reported nausea','past')])
        self.assertEqual(complete['status'],'supported',complete['review_reasons'])
        foreign = '\n\nAnother patient\nShe reports nausea.'
        unrelated,_ = assign(foreign,'any')
        self.assertEqual(unrelated['status'],'supported',unrelated['review_reasons'])
        selected,facts = assign(foreign,'any',[('foreign','She reports nausea','current')])
        self.assertTrue(facts['foreign']['issues'])
        self.assertNotEqual(selected['status'],'supported')
        retracted,facts = assign(' The whole current note belongs to another patient.','any')
        self.assertTrue(facts['pain']['issues'])
        self.assertNotEqual(retracted['status'],'supported')

    def test_bound_symptom_time_disambiguation_is_a_required_literal_qualifier(self):
        report = 'She reports wrist pain'
        duration = 'Each episode lasts approximately 11 minutes'
        caveat = 'These episode lengths describe the symptom, not physician time'
        body = 'Subjective\n'+report+'. '+duration+'. '+caveat+'.'
        specs = [('pain',report,'history','affirmed','current'),('duration',duration,'history','affirmed','current'),
            ('caveat',caveat,'other','affirmed','current')]
        missing, *_ = self.run_assignment('Subjective: reported symptoms, retaining qualifiers.',body,specs,['pain','duration'])
        complete, facts, notes, fields, _, _ = self.run_assignment('Subjective: reported symptoms, retaining qualifiers.',
            body,specs,['pain','duration','caveat'])
        self.assertNotEqual(missing['status'],'supported')
        self.assertTrue(any(caveat in reason and 'omits' in reason for reason in missing['review_reasons']))
        self.assertEqual(complete['status'],'supported',complete['review_reasons'])
        units,_ = generation.source_units(notes,fields)
        frames = model.assertion_frames(notes,units,requirements_contract=scope.CONTRACT)
        qualifier = next(frame for frame in frames if frame['source_evidence']['quote'].rstrip('.')==caveat)
        self.assertEqual(qualifier['content_roles'],['reported_symptoms'])
        self.assertEqual(qualifier['source_relations'][0]['target_evidence']['quote'],'11 minutes')
        self.assertFalse(facts['caveat']['issues'])

    def test_duration_modifier_cannot_cross_paragraph_or_change_its_referent(self):
        report = 'She reports wrist pain lasting approximately 11 minutes'
        for caveat, separator in [('These durations describe the symptom, not physician time','\n\n'),
                ('These waiting intervals describe the symptom, not physician time',' ' )]:
            with self.subTest(caveat=caveat,separator=separator):
                answer, *_ = self.run_assignment('Subjective: reported symptoms.',
                    'Subjective\n'+report+'.'+separator+caveat+'.',
                    [('pain',report,'history','affirmed','current'),('caveat',caveat,'other','affirmed','current')],
                    ['pain','caveat'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any('duration modifier lacks' in reason for reason in answer['review_reasons']))

    def test_express_only_restriction_cannot_gain_optional_background_context(self):
        symptom, medicine = 'She reports wrist pain', 'She is taking a documented medicine'
        answer, *_ = self.run_assignment('Subjective: reported symptoms only.',
            'Subjective\n'+symptom+'. '+medicine+'.',
            [('symptom',symptom,'history','affirmed','current'),('medicine',medicine,'history','affirmed','current')],
            ['symptom','medicine'])
        self.assertNotEqual(answer['status'],'supported')
        self.assertTrue(any('outside' in reason for reason in answer['review_reasons']))

    def test_v25_remains_historically_distinct_including_its_original_findings(self):
        quote = 'The abdomen is soft with normal bowel sounds'
        args = ('Objective: examination findings. Exclude normal bowel sounds.', 'Objective\n'+quote+'.',
            [('exam',quote,'finding','affirmed','current')], ['exam'])
        old, *_ = self.run_assignment(*args,profile=semantic.CLINICAL_SEMANTICS_SCOPE_CONTRACT)
        current, *_ = self.run_assignment(*args)
        self.assertEqual(old['status'],'supported')
        self.assertNotEqual(current['status'],'supported')
        _, definitions = self.definition(args[0])
        self.assertEqual(model.field_requirements(definitions['answer'])['contract'],model.REQUIREMENTS_CONTRACT)
        self.assertEqual(model.field_requirements(definitions['answer'],contract=scope.CONTRACT)['contract'],scope.CONTRACT)

    def test_all_stages_share_new_requirements_and_stored_answer_revalidates_without_upgrading_old(self):
        quote = 'She reports wrist pain'
        answer, facts, notes, fields, definitions, raw = self.run_assignment('Subjective: reported symptoms.',
            'Subjective\n'+quote+'.',[('pain',quote,'history','affirmed','current')],['pain'])
        sender = FixtureSender(raw['facts'], assignments(fields,{'answer':['pain']}))
        answers = semantic.run(notes,fields,definitions,sender,
            scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        expected = model.field_requirements(definitions['answer'],contract=scope.CONTRACT)
        self.assertEqual(len(sender.calls),3)
        for role,attempt,payload,schema,instructions in sender.calls:
            self.assertEqual(payload['approved_field_requirements']['answer'],expected)
            self.assertTrue(all('content_roles' in frame for frame in payload['source_assertions']))
        semantic.validate_stored_answer(notes,fields[0],definitions['answer'],answers['answer'])
        changed = deepcopy(answers['answer']);changed['fact_scope_contract']=semantic.CLINICAL_SEMANTICS_SCOPE_CONTRACT
        with self.assertRaises(ValidationError): semantic.validate_stored_answer(notes,fields[0],definitions['answer'],changed)

    def correction_case(self, *, body=None, mutate=None, new_unit='minutes', profile=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT):
        body = body or 'Physician time was 27 minutes. The above physician time is incorrect. Correction: physician time was 20 minutes.'
        notes = self.header+'Subjective\nShe reports elbow pain.\nObjective\nBlood pressure is 116/72 mmHg.\nPlan\n'+body
        units,_ = generation.source_units(notes,[])
        raw = [fact(notes,[],'identity','Synthetic Inez Vale',kind='identity',name_quote='Synthetic Inez Vale'),
            fact(notes,[],'symptom','She reports elbow pain',kind='history',name_quote='Synthetic Inez Vale'),
            fact(notes,[],'vital','Blood pressure is 116/72 mmHg',kind='finding',name_quote='Synthetic Inez Vale')]
        for identity, quote, unit, supersedes in [('time27','27 minutes','minutes',[]),('time20','20 '+new_unit,new_unit,['time27'])]:
            item = fact(notes,[],identity,quote,kind='measurement',concept='physician time',subject='clinician',
                name_quote='Dr. Mira Cole',unit=unit,unit_quote=quote,supersedes=supersedes)
            end = item['value_span']['end']
            item['value_span']['end'] -= len(' '+unit)
            item['unit_span'] = {'start':end-len(unit),'end':end}
            raw.append(item)
        for item in raw:
            named = item['subject']['name_span']
            owner = next(unit['id'] for unit in units if unit['start'] <= named['start'] < named['end'] <= unit['end'])
            if owner not in item['source_unit_ids']: item['source_unit_ids'].append(owner)
        if mutate: mutate(raw)
        before = deepcopy(raw)
        values = semantic.validate_facts(notes,units,{'facts':raw},scope_contract=profile,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
        self.assertEqual(raw,before)
        return notes, values

    def test_validated_current_correction_has_exact_targets_and_does_not_hold_unrelated_facts(self):
        for body in (None,'Physician time was 27 minutes. Correction: physician time was 20 minutes.'):
            with self.subTest(body=body):
                notes,values = self.correction_case(body=body)
                self.assertTrue(values['time27']['issues'])
                for key in ('identity','symptom','vital','time20'):
                    self.assertEqual(values[key]['issues'],[],(key,values[key]['issues']))
                relations = values['identity']['source_governance_relations']
                correction = next(item for item in relations if item['kind']=='validated_fact_correction')
                self.assertEqual(correction['target_fact_ids'],['time27'])
                evidence = correction['source_evidence']
                self.assertEqual(notes[evidence['start']:evidence['end']],evidence['quote'])
        _,old = self.correction_case(profile=semantic.CLINICAL_SEMANTICS_SCOPE_CONTRACT)
        self.assertTrue(old['identity']['issues'])
        self.assertNotIn('source_governance_relations',old['identity'])

    def test_unbound_or_competing_annotations_cannot_release_time_or_supply_source_scope(self):
        changes = [lambda rows:rows[-1].update(supersedes=['absent']),
            lambda rows:rows[-1].update(supersedes=['identity']),
            lambda rows:rows[-1].update(concept='different time'),
            lambda rows:rows[-1]['subject'].update(kind='other'),
            lambda rows:rows[-1]['timing'].update(kind='past')]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                _,values = self.correction_case(mutate=mutate)
                self.assertTrue(values['time20']['issues'])
                self.assertEqual(values['identity']['issues'],[])
                self.assertTrue(any(proof['kind']=='scoped_time_correction_claim' for proof in values['identity']['source_governance_relations']))
        _,values = self.correction_case(body='Physician time was 27 minutes. Correction: physician time was 20 seconds.',new_unit='seconds')
        self.assertTrue(values['time20']['issues'])
        self.assertEqual(values['identity']['issues'],[])
        with self.assertRaisesRegex(ValidationError,'A measurement unit must be an exact source value.'):
            self.correction_case(mutate=lambda rows:rows[-1].update(unit='seconds'))

    def test_correction_target_requires_valid_source_and_proof_is_independent_of_fact_order(self):
        _,ordinary = self.correction_case()
        _,reversed_facts = self.correction_case(mutate=lambda rows:rows.reverse())
        for key in ordinary:
            self.assertEqual(ordinary[key]['issues'],reversed_facts[key]['issues'])
            self.assertEqual(ordinary[key].get('source_governance_relations'),reversed_facts[key].get('source_governance_relations'))
        _,held = self.correction_case(mutate=lambda rows:rows[-2].update(polarity='uncertain'))
        self.assertTrue(held['time27']['issues'])
        self.assertEqual(held['identity']['issues'],[])

    def test_uncertainty_whole_ownership_and_residual_governors_remain_held(self):
        bodies = ['Physician time was 27 minutes. The whole current note belongs to another patient. Correction: physician time was 20 minutes.',
            'Physician time was 27 minutes. Correction: physician time was 20 minutes; the following:',
            'Physician time was 27 minutes. Correction: physician time was 20 minutes; all of the above is incorrect.']
        for body in bodies:
            with self.subTest(body=body):
                _,values = self.correction_case(body=body)
                self.assertTrue(values['identity']['issues'])
                self.assertTrue(values['time27']['issues'])

    def test_uncertain_value_does_not_make_independently_bound_time_scope_global(self):
        body = 'Physician time was 27 minutes. Correction: physician time may be 20 minutes.'
        _,values = self.correction_case(body=body,mutate=lambda rows:rows[-1].update(polarity='uncertain',supersedes=[]))
        for key in ('identity','symptom','vital'):
            self.assertEqual(values[key]['issues'],[])
        self.assertTrue(values['time27']['issues'])
        self.assertEqual(values['time20']['polarity'],'uncertain')
        proof = next(proof for proof in values['identity']['source_governance_relations'] if proof['kind']=='scoped_time_correction_claim')
        self.assertFalse(proof['retires_facts'])
        self.assertFalse(proof['establishes_time_eligibility'])
        self.assertNotIn('validated_fact_correction',[proof['kind'] for proof in values['identity']['source_governance_relations']])

    def test_negated_or_uncertain_time_value_retains_bound_target_without_retiring_or_coding_it(self):
        from core import corti_semantics
        for clause,polarity in [('was not','negated'),('may not be','uncertain')]:
            with self.subTest(clause=clause):
                body='Physician time was 27 minutes. The above physician time is incorrect. Correction: physician time '+clause+' 20 minutes.'
                notes,values=self.correction_case(body=body,
                    mutate=lambda rows:rows[-1].update(polarity=polarity,supersedes=[]))
                for key in ('identity','symptom','vital'):self.assertEqual(values[key]['issues'],[])
                self.assertTrue(values['time27']['issues'])
                self.assertEqual(values['time20']['polarity'],polarity)
                proofs=values['identity']['source_governance_relations']
                proof=next(item for item in proofs if item['kind']=='scoped_time_correction_claim')
                self.assertFalse(proof['retires_facts']);self.assertFalse(proof['establishes_time_eligibility'])
                self.assertFalse(any(item['kind']=='validated_fact_correction' for item in proofs))
                self.assertEqual(corti_semantics.office_time_facts(notes,contract=corti_semantics.SHARED_TIME_CONTRACT)['status'],'requires_clarification')
                fields,definitions=self.definition('Subjective: documented patient name and reported symptoms.')
                definition=definitions['answer'];definition.update(version=3,patient_name_requirement='documented')
                raw=[]
                for original in values.values():
                    item={key:deepcopy(original[key]) for key in semantic.FACT_SCHEMA['properties']['facts']['items']['required']}
                    item['subject']={key:item['subject'][key] for key in ('kind','name_span')}
                    item['timing']={key:item['timing'][key] for key in ('kind','span')}
                    raw.append(item)
                sender=FixtureSender(raw,assignments(fields,{'answer':['identity','symptom']}))
                answer=semantic.run(notes,fields,definitions,sender,scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
                    reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)['answer']
                self.assertEqual(semantic.current_identity_proof(notes,fields[0],definition,answer)['issues'],[])
                answer['facts']=[answer['facts'][0]]
                self.assertEqual(semantic.current_identity_proof(notes,fields[0],definition,answer)['issues'],[])

    def test_current_identity_bridge_revalidates_complete_v26_inventory_and_keeps_old_policy(self):
        notes,facts = self.correction_case()
        fields,definitions = self.definition('Subjective: documented patient name and reported symptoms.')
        definition = definitions['answer']
        definition.update(version=3,patient_name_requirement='documented')
        raw = []
        for original in facts.values():
            item = {key:deepcopy(original[key]) for key in semantic.FACT_SCHEMA['properties']['facts']['items']['required']}
            item['subject'] = {key:item['subject'][key] for key in ('kind','name_span')}
            item['timing'] = {key:item['timing'][key] for key in ('kind','span')}
            if item['scale'] is not None: item['scale'] = {key:item['scale'][key] for key in ('minimum','maximum','span')}
            raw.append(item)
        sender = FixtureSender(raw,assignments(fields,{'answer':['identity','symptom']}))
        answer = semantic.run(notes,fields,definitions,sender,
            scope_contract=semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)['answer']
        self.assertEqual(len(sender.calls),3)
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        semantic.validate_stored_answer(notes,fields[0],definition,answer)
        before = deepcopy(answer)
        proof = semantic.current_identity_proof(notes,fields[0],definition,answer)
        self.assertEqual(proof['issues'],[],proof['issues'])
        self.assertEqual(proof['contract'],'current-saved-source-identity-v2')
        self.assertEqual(proof['fact_scope_contract'],semantic.CLINICAL_REQUIREMENTS_SCOPE_CONTRACT)
        self.assertEqual(proof['fact_ids'],['identity'])
        self.assertEqual(answer,before)
        old = deepcopy(answer);old['fact_scope_contract'] = semantic.CLINICAL_SEMANTICS_SCOPE_CONTRACT
        old_proof = semantic.current_identity_proof(notes,fields[0],definition,old)
        self.assertTrue(old_proof['issues'])
        self.assertEqual(old_proof['contract'],'current-saved-source-identity-v1')
        self.assertNotIn('retained_fact_inventory_sha256',old_proof)
        identity_only = deepcopy(answer);identity_only['facts'] = [identity_only['facts'][0]]
        self.assertEqual(semantic.current_identity_proof(notes,fields[0],definition,identity_only)['issues'],[])
        changes = [lambda a:a['facts'][-1].pop('value_span'),
            lambda a:a.update(text='The patient is not Synthetic Inez Vale.'),
            lambda a:a.update(source_sha256='0'*64),
            lambda a:a.update(fact_ids=[])]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                changed = deepcopy(answer);mutate(changed)
                held = semantic.current_identity_proof(notes,fields[0],definition,changed)
                self.assertTrue(held['issues'])
                self.assertEqual(held['patient_names'],[])

        original_claim = 'Correction: physician time was 20 minutes.'
        for claim in ('Correction: an unresolved account was 20 minutes.',
                'Correction: physician time may be an unknown amount.',
                'Correction: physician time was 20 minutes; the whole note belongs to another patient.',
                'Her mother\'s note: Correction: physician time was 20 minutes.',
                '"Correction: physician time was 20 minutes."'):
            with self.subTest(unresolved_or_foreign_claim=claim):
                changed_notes = notes.replace(original_claim,claim)
                changed = deepcopy(identity_only)
                changed['source_sha256'] = semantic.hashlib.sha256(changed_notes.encode()).hexdigest()
                held = semantic.current_identity_proof(changed_notes,fields[0],definition,changed)
                self.assertTrue(held['issues'])
                self.assertEqual(held['patient_names'],[])
