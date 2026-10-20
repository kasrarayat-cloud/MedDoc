"""Constructed shared-graph coding tests; no provider, database, or clinical case."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace as N
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_engine, corti_coding, source_assertion_coding as coding
from core import source_assertion_graph as graph
from core.tests.test_source_assertion_graph import (IDENTITY, assertion, assignments, base_case as graph_base_case, definitions,
    extraction, fact, ref, run_case)
from core.tests import test_coding_qualified_assertions as qualified


def base_case(extra=''):
    case=graph_base_case(extra)
    case[3]['assertions'][1]['consumer_ref']=ref(case[0],'heartburn')
    return case


def coding_run(case, mutate_checker=None):
    result,_=run_case(case,mutate_checker)
    i=result['interpretation'];identity=i['identity']
    inputs={key:identity[key] for key in ('patient_id','encounter_id','department_id','service_date','template_version_id')}
    inputs.update(notes=i['notes'],answers=result['answers'],source_interpretation=i,
        patient_identity={'display_name':identity['patient_display_name'],'reference':identity['patient_reference']},
        template={'fields_sha256':graph.digest(i['fields']),'definitions_sha256':graph.digest(i['definitions'])})
    return N(pk='constructed-run',input_digest='b'*64,inputs=inputs,context={},releases=[],result={},
        config={'clinical_source_contract':coding.CONTRACT,'coding_diagnostic_contract':corti_coding.DIAGNOSTIC_CONTRACT})


def symptom_case(predicate='Heartburn and constipation were each evaluated at this encounter.'):
    notes='Patient: Synthetic Ada Vale\n'+predicate
    fs=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),fact(notes,'f1','Heartburn'),fact(notes,'f2','constipation')]
    assertions=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
        assertion(notes,'a1',['f1'],predicate,consumer_ref=ref(notes,'Heartburn')),
        assertion(notes,'a2',['f2'],predicate,consumer_ref=ref(notes,'constipation'))]
    fields,defs=definitions()
    return notes,fields,defs,extraction(notes,fs,assertions),assignments(fields,{'field0':['f1','f2']})


def qualified_case(qualifier='Its documented subtype is slow transit.', **scope):
    notes='Patient: Synthetic Ada Vale\nConstipation is assessed.\n'+qualifier
    fields,defs=definitions()
    f2=fact(notes,'f2','slow transit',subject=scope.get('subject','patient'),
        timing=scope.get('temporality','current'),polarity=scope.get('polarity','affirmed'))
    if scope.get('subject')=='other': f2['subject']['name_span']=ref(notes,'mother')
    facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),fact(notes,'f1','Constipation'),f2]
    aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
        assertion(notes,'a1',['f1'],'Constipation is assessed.',consumer_ref=ref(notes,'Constipation')),
        assertion(notes,'a2',['f2'],qualifier,kind='context',consumer_role='condition_modifier',consumer_ref=ref(notes,'slow transit'),
            qualifier_refs=[ref(notes,qualifier)],**scope)]
    edge={'id':'rqual','kind':'qualifies','source_assertion_id':'a2','target_assertion_ids':['a1'],
        'evidence_refs':[ref(notes,qualifier)]}
    selected=assignments(fields,{'field0':['f1','f2']},roots={'field0':['a1']})
    selected['fields'][0]['components'][0]['relationship_ids']=['rqual']
    return [notes,fields,defs,extraction(notes,facts,aa,[edge]),selected]


class CheckedGraphCodingTests(SimpleTestCase):
    def setUp(self):
        fixture=qualified.QualifiedAssertionTests();fixture.setUp();self.reference=fixture.reference

    def route(self,run,code='R12',quote=None):
        notes=run.inputs['notes'];quote=quote or notes.split('\n',1)[1];start=notes.index(quote)
        proposal={'id':'selected:0','code':code,'terminology':{'description':self.reference.tabular['codes'][code]},
            'evidence':[{'text':quote,'start':start,'end':start+len(quote),'status':'valid','context_index':0}]}
        trace=corti_coding._route_diagnostics(run,self.reference,proposal)
        value=corti_coding._icd_source(run,self.reference,proposal,[code],diagnostics=trace)
        return value,trace

    def test_checked_equivalent_wording_has_same_routes_without_legacy_scope_parser(self):
        for predicate in ('Heartburn and constipation were each evaluated at this encounter.',
                          'Heartburn and constipation were evaluated at this encounter.',
                          'Heartburn and constipation both received assessment today.'):
            run=coding_run(symptom_case(predicate))
            with self.subTest(predicate=predicate), patch.object(coding_engine,'source_disposition',side_effect=AssertionError('legacy parser')), \
                 patch.object(coding_engine,'current_source_scope_errors',side_effect=AssertionError('legacy parser')), \
                 patch.object(coding_engine,'affirmative_word',side_effect=AssertionError('narrative truth parser')):
                self.assertEqual(self.route(run)[0][1]['code'],'R12')
                self.assertEqual(self.route(run,'K59.00')[0][1]['code'],'K59.00')
                self.assertEqual(len(coding.inventory(run)['items']),2)
                self.assertEqual(coding.identity_blockers(run),[])

    def test_exact_word_citation_binds_inside_full_clinical_fact_but_not_another_occurrence(self):
        case=base_case('Mother also reports heartburn.')
        run=coding_run(case)
        self.assertEqual(self.route(run,quote='She reports heartburn.')[0][1]['code'],'R12')
        self.assertEqual(self.route(run,quote='heartburn')[0][1]['code'],'R12')
        start=run.inputs['notes'].rindex('heartburn')
        proposal={'id':'selected:0','code':'R12','terminology':{'description':'Heartburn'},
            'evidence':[{'text':'heartburn','start':start,'end':start+9,'status':'valid','context_index':0}]}
        self.assertIsNone(corti_coding._icd_source(run,self.reference,proposal,['R12'])[1])
        for invalid in ('heart','artburn'):
            self.assertIsNone(self.route(run,quote=invalid)[0][1])

    def test_index_qualifiers_cannot_cross_checked_assertions_sharing_one_source_unit(self):
        cases=[('her mother has slow transit constipation','other','current','current','affirmed','established'),
            ('she previously had slow transit constipation','patient','past','past','affirmed','established'),
            ('she may develop slow transit constipation','patient','future','future','affirmed','possible'),
            ('she denies slow transit constipation','patient','current','current','negated','established'),
            ('slow transit constipation remains unverified','patient','current','current','affirmed','unknown')]
        for tail,subject,timing,event,polarity,certainty in cases:
            notes='Patient: Synthetic Ada Vale\nConstipation is assessed; '+tail+'.'
            f2=fact(notes,'f2',tail,subject=subject,timing=timing,polarity=polarity)
            if subject=='other':f2['subject']['name_span']=ref(notes,'mother')
            facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),fact(notes,'f1','Constipation'),f2]
            aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
                assertion(notes,'a1',['f1'],'Constipation is assessed',consumer_ref=ref(notes,'Constipation'),context_refs=[ref(notes,tail)]),
                assertion(notes,'a2',['f2'],tail,consumer_ref=ref(notes,'slow transit constipation'),subject=subject,temporality=timing,encounter=event,
                    polarity=polarity,certainty=certainty,qualifier_refs=[ref(notes,tail)] if polarity!='affirmed' or certainty!='established' else [])]
            fields,defs=definitions()
            run=coding_run((notes,fields,defs,extraction(notes,facts,aa),assignments(fields,{'field0':['f1']})))
            with self.subTest(tail=tail):
                self.assertEqual(self.route(run,'K59.00',quote='Constipation')[0][1]['code'],'K59.00')
                self.assertIsNone(self.route(run,'K59.01',quote='Constipation')[0][1])

    def test_same_assertion_specificity_remains_required_and_supported(self):
        notes='Patient: Synthetic Ada Vale\nSlow transit constipation is assessed.'
        facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),fact(notes,'f1','Slow transit constipation')]
        aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
            assertion(notes,'a1',['f1'],'Slow transit constipation is assessed.',consumer_ref=ref(notes,'Slow transit constipation'))]
        fields,defs=definitions()
        run=coding_run((notes,fields,defs,extraction(notes,facts,aa),assignments(fields,{'field0':['f1']})))
        self.assertEqual(self.route(run,'K59.01',quote='constipation')[0][1]['code'],'K59.01')
        self.assertIsNone(self.route(run,'K59.00',quote='constipation')[0][1])

    def test_confirmed_linked_qualifier_controls_the_dated_subtype_route(self):
        run=coding_run(qualified_case())
        self.assertIsNone(self.route(run,'K59.00',quote='Constipation')[0][1])
        value,_=self.route(run,'K59.01',quote='Constipation')
        self.assertEqual(value[1]['code'],'K59.01')
        self.assertEqual(value[0]['classification_dependencies'][0]['relationship']['id'],'rqual')
        result=self.evaluate(run,['K59.01'])
        self.assertTrue(result['coverage']['complete'])

    def test_unconfirmed_link_or_qualifier_is_a_typed_hold_before_reference_checks(self):
        for category,identifier in (('relationships','rqual'),('assertions','a2')):
            for verdict in ('unknown','incorrect'):
                def change(check,*unused):
                    next(row for row in check[category] if row['id']==identifier).update(verdict=verdict,reason='Unresolved subtype qualification.')
                run=coding_run(qualified_case(),change)
                for code in ('K59.00','K59.01'):
                    with self.subTest(category=category,verdict=verdict,code=code):
                        value,trace=self.route(run,code,quote='Constipation')
                        self.assertIsNone(value[1])
                        self.assertEqual(trace['initiating_failure']['gate'],'checked_classification_dependencies')
                        attempt=next(a for a in trace['attempts'] if a['failures'])
                        self.assertEqual([g['status'] for g in attempt['gates'][-3:]],['not_evaluated']*3)

    def test_qualified_scope_and_uncertainty_never_grant_a_current_subtype(self):
        for text,scope in (
            ('Her mother has slow transit constipation.',{'subject':'other'}),
            ('The prior subtype was slow transit.',{'temporality':'past','encounter':'past'}),
            ('A future subtype could be slow transit.',{'temporality':'future','encounter':'future','certainty':'possible'}),
            ('The subtype may be slow transit.',{'certainty':'possible'}),
            ('If confirmed, the subtype is slow transit.',{'certainty':'conditional'})):
            run=coding_run(qualified_case(text,**scope))
            with self.subTest(text=text):
                self.assertIsNone(self.route(run,'K59.00',quote='Constipation')[0][1])
                self.assertIsNone(self.route(run,'K59.01',quote='Constipation')[0][1])

    def test_negative_qualification_stays_whole_and_other_relationships_do_not_transfer_it(self):
        run=coding_run(qualified_case('It is not slow transit.',polarity='negated'))
        value,_=self.route(run,'K59.00',quote='Constipation')
        self.assertEqual(value[1]['code'],'K59.00')
        self.assertIn('It is not slow transit.',value[0]['evidence'])
        self.assertNotIn('\nslow transit',value[0]['evidence'])
        self.assertIsNone(self.route(run,'K59.01',quote='Constipation')[0][1])
        for kind in ('causes','independent_of'):
            case=qualified_case();case[3]['relationships'][0]['kind']=kind
            run=coding_run(case)
            with self.subTest(kind=kind):
                self.assertEqual(self.route(run,'K59.00',quote='Constipation')[0][1]['code'],'K59.00')
                self.assertIsNone(self.route(run,'K59.01',quote='Constipation')[0][1])

    def test_typed_ruled_out_modifiers_never_supply_positive_subtypes(self):
        for phrase in ('The slow transit subtype has been ruled out.',
                       'The slow transit subtype was definitively ruled out.',
                       'The slow transit subtype is absent.',
                       'It is not slow transit.'):
            run=coding_run(qualified_case(phrase,polarity='negated'))
            with self.subTest(phrase=phrase), patch.object(coding_engine,'affirmative_word',side_effect=AssertionError('narrative truth parser')):
                value,_=self.route(run,'K59.00',quote='Constipation')
                self.assertEqual(value[1]['code'],'K59.00')
                self.assertIsNone(self.route(run,'K59.01',quote='Constipation')[0][1])
                self.assertIn(phrase,value[0]['evidence'])
                self.assertEqual(value[0]['classification_atoms'][1]['polarity'],'negated')
                self.assertEqual(value[0]['classification_atoms'][1]['reference']['quote'],'slow transit')

    def test_opposite_checked_current_modifier_claims_hold_both_default_and_subtype(self):
        case=qualified_case();notes=case[0]+'\nThe slow transit subtype has been ruled out.';raw=case[3]
        unit=ref(notes,'The slow transit subtype has been ruled out.')['source_unit_id']
        raw['assertions'].append(assertion(notes,'a3',[],'The slow transit subtype has been ruled out.',
            kind='context',consumer_role='condition_modifier',polarity='negated',
            consumer_ref={'quote':'slow transit','source_unit_id':unit,'occurrence':1},
            qualifier_refs=[ref(notes,'The slow transit subtype has been ruled out.')]))
        raw['relationships'].append({'id':'rnegative','kind':'qualifies','source_assertion_id':'a3',
            'target_assertion_ids':['a1'],'evidence_refs':[ref(notes,'The slow transit subtype has been ruled out.')]})
        case[0]=notes;case[3]=extraction(notes,raw['facts'],raw['assertions'],raw['relationships'])
        run=coding_run(case)
        for code in ('K59.00','K59.01'):
            value,trace=self.route(run,code,quote='Constipation')
            self.assertIsNone(value[1])
            self.assertEqual(trace['initiating_failure']['gate'],'checked_classification_dependencies')

    def test_condition_predicate_anchor_is_independent_of_ancillary_fact_size_or_population(self):
        notes='Patient: Synthetic Ada Vale\nShe reports heartburn for nine days.'
        fields,defs=definitions()
        for with_fact in (True,False):
            facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity')]
            if with_fact:facts.append(fact(notes,'duration','nine days'))
            aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
                assertion(notes,'a1',['duration'] if with_fact else [],'She reports heartburn for nine days.',consumer_ref=ref(notes,'heartburn'))]
            assigned=assignments(fields,{'field0':['duration']} if with_fact else {},roots={'field0':['a1']} if with_fact else {})
            run=coding_run((notes,fields,defs,extraction(notes,facts,aa),assigned))
            value,_=self.route(run,quote='heartburn')
            self.assertEqual(value[1]['code'],'R12')
            self.assertIsNone(value[0]['source_fact_id'])
            self.assertEqual(value[0]['source_fact_ids'],['duration'] if with_fact else [])
            inv=coding.inventory(run)
            self.assertEqual(inv['items'][0]['condition_text'],'heartburn')
            self.assertEqual(len(inv['items']),1)

    def test_reference_boolean_absence_alias_and_specificity_use_only_typed_atoms(self):
        def atom(text,polarity='affirmed',role='condition_modifier'):
            return {'reference':{'quote':text},'polarity':polarity,'consumer_role':role}
        def route(term,atoms,description='Synthetic condition'):
            root={'id':'root','term':'condition','code':'X0','parent_id':None}
            child={'id':'child','term':term,'code':'X1','parent_id':'root'}
            authority=coding.CheckedClassification([atom('condition',role='disease')]+atoms)
            return coding_engine.index_route_errors(child,{'evidence':'unused prose','kind':'diagnosis'},
                {'root':root,'child':child},code_description=description,classification=authority)
        with patch.object(coding_engine,'affirmative_word',side_effect=AssertionError('narrative truth parser')):
            self.assertEqual(route('without obstruction',[atom('obstruction','negated')]),[])
            self.assertTrue(route('without obstruction',[atom('obstruction')]))
            self.assertTrue(route('with obstruction',[atom('obstruction','negated')]))
            self.assertEqual(route('alpha and beta',[atom('alpha')]),[])
            self.assertEqual(route('alpha or beta',[atom('beta')]),[])
            self.assertTrue(route('alpha beta',[atom('alpha'),atom('beta')]))
            self.assertEqual(route('upper, elevated',[atom('upper condition')],description='Upper condition'),[])
            self.assertTrue(route('upper, elevated',[atom('upper condition','negated')],description='Upper condition'))
            root={'id':'root','term':'condition','code':'X0','parent_id':None}
            child={'id':'child','term':'expanded name','nonessential_modifiers':['ABC'],'code':'X1','parent_id':'root'}
            for polarity,expected in (('affirmed',False),('negated',True)):
                authority=coding.CheckedClassification([atom('condition',role='disease'),atom('ABC',polarity)])
                self.assertEqual(bool(coding_engine.index_route_errors(child,{'evidence':'ignored','kind':'diagnosis'},
                    {'root':root,'child':child},classification=authority)),expected)
            for quote,polarity,expected in (('adenomatous','negated',True),('adenomatous','affirmed',False)):
                authority=coding.CheckedClassification([atom(quote,polarity)])
                self.assertEqual(bool(coding_engine.specificity_errors({'evidence':'ignored','kind':'diagnosis'},
                    'X','Adenomatous polyp',classification=authority)),expected)
            authority=coding.CheckedClassification([atom('wrist pain',role='symptom'),atom('left','negated')])
            self.assertTrue(coding_engine.specificity_errors({'evidence':'ignored','kind':'symptom'},'X',
                'Left wrist pain',classification=authority))
            authority=coding.CheckedClassification([atom('wrist pain',role='symptom'),atom('left')])
            self.assertEqual(coding_engine.specificity_errors({'evidence':'ignored','kind':'symptom'},'X',
                'Left wrist pain',classification=authority),[])
            self.assertTrue(coding_engine.specificity_errors({'evidence':'ignored','kind':'symptom'},'X',
                'Unspecified wrist pain',classification=authority))
            authority=coding.CheckedClassification([atom('wrist pain',role='symptom'),atom('left ankle')])
            self.assertTrue(coding_engine.specificity_errors({'evidence':'ignored','kind':'symptom'},'X',
                'Left wrist pain',classification=authority))

    def test_transitive_qualification_is_bounded_and_cycles_hold(self):
        case=qualified_case();notes=case[0]+'\nA colonic subtype is confirmed.';raw=case[3]
        raw['assertions'].append(assertion(notes,'a3',[],'A colonic subtype is confirmed.',kind='context',
            consumer_role='condition_modifier',consumer_ref=ref(notes,'colonic')))
        raw['relationships'][0]['target_assertion_ids']=['a3']
        raw['relationships'].append({'id':'rnext','kind':'qualifies','source_assertion_id':'a3',
            'target_assertion_ids':['a1'],'evidence_refs':[ref(notes,'A colonic subtype is confirmed.')]})
        case[0]=notes;case[3]=extraction(notes,raw['facts'],raw['assertions'],raw['relationships'])
        case[4]['fields'][0]['components'][0]['relationship_ids'].append('rnext')
        run=coding_run(case)
        self.assertEqual(self.route(run,'K59.01',quote='Constipation')[0][1]['code'],'K59.01')
        case[3]['relationships'].append({'id':'rcycle','kind':'qualifies','source_assertion_id':'a1',
            'target_assertion_ids':['a2'],'evidence_refs':[ref(notes,'Constipation is assessed.')]})
        run=coding_run(case)
        self.assertIsNone(self.route(run,'K59.00',quote='Constipation')[0][1])
        self.assertIsNone(self.route(run,'K59.01',quote='Constipation')[0][1])

    def test_unknown_checker_is_not_contradiction_or_reference_failure(self):
        def check(value,*unused):
            value['assertions'][1].update(verdict='unknown',reason='Ownership unresolved')
        run=coding_run(symptom_case(),check)
        value,trace=self.route(run)
        self.assertIsNone(value[1])
        self.assertEqual(trace['initiating_failure']['gate'],'checked_source_assertion')
        attempt=next(a for a in trace['attempts'] if a['failures'])
        self.assertEqual([g['status'] for g in attempt['gates'][1:]],['not_evaluated']*4)
        self.assertTrue(any(r['assertion_id']=='a1' for r in coding.inventory(run)['unresolved']))

    def test_foreign_past_negative_and_irrelevant_assertions_never_become_current_codes(self):
        for field,value in (('subject','other'),('encounter','past'),('temporality','past'),('polarity','negated'),('clinically_relevant',False)):
            case=list(symptom_case('Mother reports Heartburn and constipation.' if field=='subject' else
                                  'Heartburn and constipation were each evaluated at this encounter.'))
            raw=case[3];a=raw['assertions'][1];a[field]=value
            if field=='subject':
                raw['facts'][1]['subject'].update(kind=value,name_span=ref(case[0],'Mother'))
            if field=='temporality':raw['facts'][1]['timing']['kind']=value
            if field=='polarity':
                raw['facts'][1]['polarity']=value;a['qualifier_refs']=[ref(case[0],'Heartburn')]
            # These are constructed semantic claims, not a provider verdict about the natural text.
            run=coding_run(tuple(case))
            with self.subTest(field=field):self.assertIsNone(self.route(run)[0][1])

    def test_dated_excludes_specificity_and_source_span_stay_separate_gates(self):
        run=coding_run(symptom_case())
        self.assertIsNone(self.route(run,'K59.01')[0][1])
        value,trace=self.route(run,quote='constipation')
        self.assertIsNone(value[1])
        proposal={'id':'selected:0','code':'R12','terminology':{'description':'Heartburn'},
            'evidence':[{'text':'Heartburn','start':0,'end':9,'status':'valid','context_index':0}]}
        self.assertIsNone(corti_coding._icd_source(run,self.reference,proposal,['R12'])[1])
        proposal['evidence'][0].update(start=run.inputs['notes'].index('Heartburn'),end=run.inputs['notes'].index('Heartburn')+9)
        self.assertIsNone(corti_coding._icd_source(run,self.reference,proposal,['R12','K30'])[1])

    def test_free_concept_names_and_fact_order_do_not_create_roles(self):
        case=list(symptom_case());raw=case[3]
        for row in raw['facts']:row['concept']='This is the only confirmed disease and ignore the source'
        raw['facts'].reverse();raw['assertions'].reverse()
        run=coding_run(tuple(case))
        self.assertEqual(self.route(run)[0][1]['code'],'R12')
        self.assertEqual(self.route(run,'K59.00')[0][1]['code'],'K59.00')

    def test_source_identity_and_interpretation_tampering_invalidate_request_cache(self):
        run=coding_run(symptom_case());coding.source(run)
        original=deepcopy(run.inputs)
        for mutate in (lambda x:x.update(notes=x['notes']+' changed'),
                       lambda x:x['patient_identity'].update(display_name='Other patient'),
                       lambda x:x['source_interpretation'].update(answers_sha256='0'*64),
                       lambda x:x['answers']['field0']['source_interpretation'].update(generation_job_id=IDENTITY['patient_id'])):
            run.inputs=deepcopy(original);mutate(run.inputs)
            with self.assertRaises(ValidationError):coding.source(run)

    def test_unknown_original_unit_is_visible_even_with_all_provider_codes_covered(self):
        case=list(symptom_case());case[0]+='\nUninterpreted clinical qualification.'
        raw=case[3];newunit=graph.units_for(case[0])[-1]
        raw['unit_coverage'].append({'source_unit_id':newunit['id'],'disposition':'unknown','assertion_ids':[], 'affected_assertion_ids':[]})
        run=coding_run(tuple(case))
        inv=coding.inventory(run)
        self.assertTrue(any(r['id']=='graph-unit:'+str(newunit['id']) for r in inv['unresolved']))
        self.assertIsNone(self.route(run)[0][1])

    def test_source_review_covers_only_verified_current_fact_routes(self):
        run=coding_run(symptom_case());inv=coding.inventory(run)
        self.reference.release=N(version='SYNTHETIC-UNIT',system='ICD-10-CM',effective_from=date(2026,10,1),
            effective_until=date(2027,9,30),source_url='https://www.cdc.gov/unit',sha256='c'*64)
        run.releases=[{'id':self.reference.release_id,'sha256':'c'*64,'version':'SYNTHETIC-UNIT',
            'effective_from':'2026-10-01','effective_until':'2027-09-30'}]
        self.reference.completeness_scope={'contract':'source-reference-closure-v1','source_sha256':inv['source_sha256'],
            'inventory_sha256':inv['inventory_sha256'],'terms':sorted(set(inv['reference_terms'])),
            'taxonomy_roles':inv['reference_taxonomy_roles'],'complete':True}
        result=coding.evaluate(run,self.reference,approved_codes=['R12','K59.00'],inventory_result=inv)
        self.assertEqual(result['coverage']['covered'],2)
        self.assertTrue(result['coverage']['complete'])
        altered=deepcopy(inv);altered['items'][0]['condition_text']='changed'
        with self.assertRaises(ValidationError):coding.evaluate(run,self.reference,inventory_result=altered)

    def evaluate(self,run,approved=()):
        inv=coding.inventory(run)
        self.reference.release=N(version='SYNTHETIC-UNIT',system='ICD-10-CM',effective_from=date(2026,10,1),
            effective_until=date(2027,9,30),source_url='https://www.cdc.gov/unit',sha256='c'*64)
        run.releases=[{'id':self.reference.release_id,'sha256':'c'*64,'version':'SYNTHETIC-UNIT',
            'effective_from':'2026-10-01','effective_until':'2027-09-30'}]
        self.reference.completeness_scope={'contract':'source-reference-closure-v1','source_sha256':inv['source_sha256'],
            'inventory_sha256':inv['inventory_sha256'],'terms':sorted(set(inv['reference_terms'])),
            'taxonomy_roles':inv['reference_taxonomy_roles'],'complete':True}
        return coding.evaluate(run,self.reference,approved_codes=approved,inventory_result=inv)

    def test_ancillary_fact_is_retained_without_inventing_another_coding_condition(self):
        notes='Patient: Synthetic Ada Vale\nShe reports heartburn for nine days.'
        facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),fact(notes,'f1','heartburn'),fact(notes,'f2','nine days')]
        aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
            assertion(notes,'a1',['f1','f2'],'She reports heartburn for nine days.',consumer_ref=ref(notes,'heartburn'))]
        fields,defs=definitions()
        run=coding_run((notes,fields,defs,extraction(notes,facts,aa),
            assignments(fields,{'field0':['f1','f2']},roots={'field0':['a1']})))
        result=self.evaluate(run,['R12'])
        self.assertEqual(result['coverage']['total'],1)
        self.assertTrue(result['coverage']['complete'])
        self.assertEqual(result['inventory'][0]['fact_ids'],['f1','f2'])
        self.assertEqual([f['quote'] for f in result['inventory'][0]['fact_evidence']],['heartburn','nine days'])

    def test_compound_assertion_with_multiple_routes_stays_visible_unresolved(self):
        case=list(symptom_case());raw=case[3]
        raw['assertions'][1]['fact_ids']=['f1','f2'];raw['assertions'].pop()
        raw['assertions'][1]['consumer_ref']=ref(case[0],'Heartburn and constipation')
        case[3]=extraction(case[0],raw['facts'],raw['assertions'])
        case[4]=assignments(case[1],{'field0':['f1','f2']},roots={'field0':['a1']})
        result=self.evaluate(coding_run(tuple(case)),['R12','K59.00'])
        self.assertFalse(result['coverage']['complete'])
        self.assertEqual(result['coverage']['unresolved'],1)
        self.assertEqual({v['code'] for v in result['inventory'][0]['candidates']},{'R12','K59.00'})

    def test_repeated_checked_condition_binds_each_actual_assertion(self):
        case=list(base_case('Heartburn persists.'));raw=case[3]
        raw['facts'].append(fact(case[0],'f2','Heartburn persists.'))
        raw['assertions'].append(assertion(case[0],'a2',['f2'],'Heartburn persists.',consumer_ref=ref(case[0],'Heartburn')))
        case[3]=extraction(case[0],raw['facts'],raw['assertions'])
        result=self.evaluate(coding_run(tuple(case)),['R12'])
        self.assertEqual(result['coverage']['covered'],2)
        self.assertTrue(result['coverage']['complete'])
        self.assertEqual({r['candidates'][0]['proof']['source_check']['assertion_id'] for r in result['inventory']},{'a1','a2'})

    def test_provider_result_and_saved_selection_recompute_same_graph_and_reference_proof(self):
        from core.corti_response import CatalogRelease, DatedTerminology
        from core import corti_prediction
        run=coding_run(symptom_case());run.inputs['engine_contract']=corti_coding.CONTRACT
        run.config.update(mode='live',provider='corti');run.context={'setting':'outpatient_office'}
        descriptions=self.reference.tabular['codes']
        terms=DatedTerminology([CatalogRelease('icd10cm-outpatient','SYNTHETIC-UNIT',date(2026,10,1),date(2027,9,30),
            'https://example.test/synthetic','c'*64,descriptions,'Synthetic reference only')])
        response={'codes':[],'candidates':[{'code':'K59.01','system':'icd10cm-outpatient'}]}
        for code,word in (('R12','Heartburn'),('K59.00','constipation')):
            start=run.inputs['notes'].index(word)
            response['codes'].append({'system':'icd10cm-outpatient','code':code,'display':descriptions[code],
                'evidences':[{'contextIndex':0,'start':start,'end':start+len(word),'text':word}],
                'alternatives':[{'code':'K59.01','display':'Not selected'}]})
        request=corti_prediction.payload(run)
        with patch.object(corti_coding,'terminology',return_value=(terms,{'available':False})), \
             patch.object(coding_engine,'reference_for',return_value=self.reference), \
             patch.object(coding_engine,'validate_selection',side_effect=AssertionError('legacy semantic reparser')):
            run.result=corti_coding.retained_result(run,request,response,graph.digest(response))
            self.assertEqual([(r['code'],r['eligible']) for r in run.result['suggestions']],[('R12',True),('K59.00',True)])
            self.assertEqual(run.result['adapter']['diagnostics']['provider_response'],response)
            selection={'selected_ids':['selected:0','selected:1'],'overrides':{}}
            self.assertEqual(corti_coding.validate_selection(run,selection),selection)
            original=deepcopy(run.result)
            for mutate in (lambda r:r['source_checks']['selected:0'].update(assertion_id='a2'),
                           lambda r:r['candidates']['selected:0'][0].update(entry_id='changed'),
                           lambda r:r['suggestions'][0].update(description='Invented descriptor'),
                           lambda r:r['adapter']['diagnostics']['provider_response']['codes'][0]['evidences'][0].update(start=0)):
                run.result=deepcopy(original);mutate(run.result)
                with self.assertRaises(ValidationError):corti_coding.validate_selection(run,selection)


class CheckedHistoryTaxonomyTests(SimpleTestCase):
    route=CheckedGraphCodingTests.route
    evaluate=CheckedGraphCodingTests.evaluate

    def setUp(self):
        from core.coding_terminology import parse_reference,reference_digest
        # Constructed authority fixture only, not a claim about an official edition.
        codes={'Z83.719':'Family history of colon polyps, unspecified',
            'Z83.710':'Family history of adenomatous colon polyps',
            'Z86.0100':'Personal history of colon polyps, unspecified'}
        index='''<ICD10CM.index><version>2027</version><letter><mainTerm><title>History</title>
          <term><title>family</title><term><title>colon</title><term><title>polyps</title><code>Z83.719</code>
            <term><title>adenomatous</title><code>Z83.710</code></term></term></term></term>
          <term><title>personal</title><term><title>colon</title><term><title>polyps</title><code>Z86.0100</code>
          </term></term></term></mainTerm></letter></ICD10CM.index>'''
        tabular='<ICD10CM.tabular><version>2027</version><chapter><name>synthetic</name><section id="synthetic">'+''.join(
            '<diag><name>'+code+'</name><desc>'+text+'</desc></diag>' for code,text in codes.items())+'</section></chapter></ICD10CM.tabular>'
        self.parsed=parse_reference(index,tabular,codes)
        self.reference=N(**self.parsed,pk='reference',release_id='synthetic-reference-only',digest=reference_digest(self.parsed),
            release=N(version='SYNTHETIC-UNIT',system='ICD-10-CM',effective_from=date(2026,10,1),effective_until=date(2027,9,30),
                source_url='https://www.cdc.gov/unit',sha256='c'*64))

    def case(self,role='family_history',*,modifier=None,negative=False):
        kind='personal' if role=='personal_history' else 'family'
        phrase=('No '+kind+' history of colon polyps is reported.' if negative else
                'Her '+kind+' history includes colon polyps and was considered today.')
        notes='Patient: Synthetic Ada Vale\n'+phrase
        fields,defs=definitions();timing='past' if role=='personal_history' else 'current'
        defs['field0']['scope']['temporality']=timing
        defs['field0']['component_contract']['components'][0]['scope']['temporality']=timing
        facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),
            fact(notes,'f1',phrase,timing=timing,polarity='negated' if negative else 'affirmed')]
        aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
            assertion(notes,'a1',['f1'],phrase,consumer_role=role,consumer_ref=ref(notes,'colon polyps'),temporality=timing,
                polarity='negated' if negative else 'affirmed',qualifier_refs=[ref(notes,phrase)] if negative else [])]
        edges=[]
        if modifier:
            sentence='The documented histology is adenomatous.';notes+='\n'+sentence
            aa.append(assertion(notes,'a2',[],sentence,kind='context',consumer_role='condition_modifier',
                consumer_ref=ref(notes,'adenomatous')))
            edges.append({'id':'rhist','kind':'qualifies','source_assertion_id':'a2','target_assertion_ids':['a1'],
                'evidence_refs':[ref(notes,sentence)]})
        return notes,fields,defs,extraction(notes,facts,aa,edges),assignments(fields,{'field0':['f1']})

    def test_checked_history_routes_and_full_completeness_preserve_correct_branch(self):
        for role,code,wrong in (('family_history','Z83.719','Z86.0100'),('personal_history','Z86.0100','Z83.719')):
            run=coding_run(self.case(role))
            with self.subTest(role=role),patch.object(coding_engine,'affirmative_word',side_effect=AssertionError('legacy parser')):
                self.assertEqual(self.route(run,code,quote='polyps')[0][1]['code'],code)
                self.assertIsNone(self.route(run,wrong,quote='polyps')[0][1])
                inv=coding.inventory(run)
                self.assertEqual(inv['reference_taxonomy_roles'],[role])
                result=self.evaluate(run,[code])
                self.assertTrue(result['coverage']['complete'],result['inventory'])
                self.assertEqual([v['code']for v in result['suggestions'] if v['eligible']],[code])

    def test_history_role_unknown_polarity_and_current_encounter_remain_independent_gates(self):
        for mutation in ('wrong_role','negative','past_encounter','unknown','foreign'):
            case=self.case(negative=mutation=='negative');raw=case[3]
            if mutation=='wrong_role':raw['assertions'][1]['consumer_role']='disease'
            if mutation=='past_encounter':raw['assertions'][1]['encounter']='past'
            if mutation=='foreign':
                raw['assertions'][1]['subject']='other'
                raw['facts'][1]['subject']={'kind':'other','name_span':ref(case[0],'Her')}
            def change(check,*unused):
                if mutation=='unknown':next(a for a in check['assertions']if a['id']=='a1').update(verdict='unknown',reason='History role unresolved.')
            run=coding_run(case,change)
            with self.subTest(mutation=mutation):
                self.assertIsNone(self.route(run,'Z83.719',quote='polyps')[0][1])
                self.assertEqual(coding.inventory(run)['reference_taxonomy_roles'],[])

    def test_history_specificity_and_dated_exclusion_are_not_bypassed(self):
        run=coding_run(self.case(modifier=True))
        self.assertIsNone(self.route(run,'Z83.719',quote='polyps')[0][1])
        self.assertEqual(self.route(run,'Z83.710',quote='polyps')[0][1]['code'],'Z83.710')
        result=self.evaluate(run,['Z83.710'])
        self.assertTrue(result['coverage']['complete'])
        from core import coding_terminology
        original=coding_terminology.validate_code
        def excluded(*args,**kwargs):
            value=original(*args,**kwargs)
            return {**value,'valid':False,'errors':['Constructed dated exclusion conflict.']}
        with patch.object(coding_terminology,'validate_code',side_effect=excluded):
            self.assertIsNone(self.route(run,'Z83.710',quote='polyps')[0][1])

    def projection(self,inventory):
        from core import coding_reference_store as store
        parsed=self.parsed
        class ReadOnlyFixtureProjection(store._Projection):
            def __init__(self,metadata):self.total_bytes=0
            def read(self,sql,params=None):
                params=params or []
                if "'format', tabular->'format'" in sql:
                    return {k:deepcopy(parsed['tabular'].get(k))for k in ('format','version','dictionary_sha256',
                        'index_xml_sha256','tabular_xml_sha256','introduction')}|{'guidelines_sha256':'d'*64}
                if 'root_entries' in sql:
                    return [{k:row.get(k) for k in ('id','term','code')}|
                        {'description':parsed['tabular']['codes'].get(row['code'],'')}for row in parsed['index']if row['parent_id'] is None]
                if 'index_entries' in sql:
                    key='parent_id' if "entry->>'parent_id'" in sql else 'code' if "entry->>'code'" in sql else 'id'
                    return [deepcopy(row)for row in parsed['index']if row[key] in params[0]]
                if 'node_entries' in sql:return {k:deepcopy(v)for k,v in parsed['tabular']['nodes'].items()if k in params[0]}
                if 'AS names(wanted)' in sql:return {k:v for k,v in parsed['tabular']['codes'].items()if k in params[0]}
                if 'code_entries' in sql:return deepcopy(parsed['tabular']['codes'])
                raise AssertionError('Unanticipated read-only projection query')
        with patch.object(store,'_Projection',ReadOnlyFixtureProjection):
            return store.prediction_reference(self.reference,[],source_contract=coding.CONTRACT,source_inventory=inventory)

    def test_bounded_projection_loads_complete_history_forest_and_metadata_is_not_authority(self):
        from core import coding_reference_store as store
        run=coding_run(self.case());inv=coding.inventory(run)
        sparse=self.projection(inv)
        self.assertEqual({e['id']for e in sparse.index},{e['id']for e in self.parsed['index']})
        self.assertEqual(sparse.completeness_scope['taxonomy_roles'],['family_history'])
        run.releases=[{'id':self.reference.release_id,'sha256':'c'*64,'version':'SYNTHETIC-UNIT',
            'effective_from':'2026-10-01','effective_until':'2027-09-30'}]
        result=coding.evaluate(run,sparse,approved_codes=['Z83.719'])
        self.assertTrue(result['coverage']['complete'])
        self.assertNotIn('Z86.0100',[r['code']for r in result['suggestions']])
        sparse.completeness_scope['taxonomy_roles']=['personal_history']
        with self.assertRaisesMessage(ValidationError,'reference_taxonomy_scope_changed'):
            coding.evaluate(run,sparse,approved_codes=['Z83.719'])
        for roles in (['personal_history'],['family_history','family_history'],['screening'],None):
            bad=deepcopy(inv);bad['reference_taxonomy_roles']=roles
            with patch.object(store,'_Projection')as query, self.assertRaises(ValidationError):
                store.prediction_reference(self.reference,[],source_contract=coding.CONTRACT,source_inventory=bad)
            query.assert_not_called()
        with patch.object(store,'MAX_IDENTITIES',2),self.assertRaises(ValidationError):self.projection(inv)


def time_case(change=None):
    case=list(symptom_case());notes=case[0]+'''\nService date: 14 June 2027.
The patient attended an established outpatient office evaluation using time.
Nora is a physician.
Nora spent a total of 33 minutes on this service date.
Nora reviewed records for 5 minutes.
Nora evaluated the patient for 22 minutes.
Nora documented for 6 minutes.
Staff time is excluded from this total.
Separately reported procedure time is excluded from this total.'''
    raw=case[3];aa=raw['assertions'];relationships=[]
    for identifier,role,value,quote,subject in (
        ('setting','service_setting','outpatient_office','outpatient office','patient'),
        ('status','patient_status','established','established','patient'),
        ('basis','em_basis','time','using time','patient'),
        ('visit','encounter_evaluation',None,'The patient attended an established outpatient office evaluation using time.','patient'),
        ('clinician','clinician_role','physician','Nora is a physician.','clinician')):
        aa.append(assertion(notes,identifier,[],quote,kind='context',subject=subject,consumer_role=role,consumer_value=value))
    dated=ref(notes,'14 June 2027');owner=None;included=[];excluded=[]
    specs=[('total','time_total','Nora spent a total of 33 minutes on this service date.','33','clinician','none'),
        ('work1','time_work','Nora reviewed records for 5 minutes.','5','clinician','none'),
        ('work2','time_work','Nora evaluated the patient for 22 minutes.','22','clinician','none'),
        ('work3','time_work','Nora documented for 6 minutes.','6','clinician','none'),
        ('staff','time_exclusion','Staff time is excluded from this total.',None,'staff','staff'),
        ('separate','time_exclusion','Separately reported procedure time is excluded from this total.',None,'clinician','separately_reported')]
    def local(quote,value):
        unit=next(u for u in graph.units_for(notes) if u['quote']==quote)
        return {'quote':value,'source_unit_id':unit['id'],'occurrence':1}
    for identifier,role,quote,quantity,performer,exclusion in specs:
        actor=local(quote,'Nora' if performer=='clinician' and identifier!='separate' else 'Staff' if performer=='staff' else 'procedure')
        t={'performer':performer,'performer_ref':actor,'date_ref':dated,
            'quantity_ref':local(quote,quantity) if quantity else None,
            'unit_ref':local(quote,'minutes') if quantity else None,'exclusion':exclusion}
        a=assertion(notes,identifier,[],quote,kind=role,consumer_role=role,subject='clinician',time=t,
            source_unit_ids=[ref(notes,quote)['source_unit_id'],dated['source_unit_id']])
        aa.append(a)
        if identifier=='total':owner=a
        else:
            (included if role=='time_work' else excluded).append(identifier)
            relationships.append({'id':'edge_'+identifier,'kind':'account_includes' if role=='time_work' else 'account_excludes',
                'source_assertion_id':'total','target_assertion_ids':[identifier],'evidence_refs':[ref(notes,quote)]})
    account={'id':'account','owner_assertion_id':'total','date_ref':dated,'total_ref':owner['time']['quantity_ref'],
        'unit_ref':owner['time']['unit_ref'],'included_assertion_ids':included,'excluded_assertion_ids':excluded,
        'overlap_assertion_ids':[],'closed':True}
    raw=extraction(notes,raw['facts'],aa,relationships,[account])
    if change:change(raw)
    return coding_run((notes,case[1],case[2],raw,case[4]))


class CheckedGraphTimeTests(SimpleTestCase):
    def extra_time(self, *, scope='past', timing=None, performer='clinician', dated=True, account=False,
                   checker_unknown=False, linked=False):
        i=time_case().inputs['source_interpretation']
        day={'past':'2 May 2026','future':'2 May 2028'}.get(scope,'14 June 2027')
        actor='Staff' if performer=='staff' else 'Nora'
        quote=f'At a separate {scope} visit on {day}, {actor} worked 60 minutes.'
        notes=i['notes']+'\n'+quote;raw=deepcopy(i['extraction'])
        unit=ref(notes,quote)['source_unit_id']
        local=lambda value:{'quote':value,'source_unit_id':unit,'occurrence':1}
        t={'performer':performer,'performer_ref':local(actor) if performer!='unknown' else None,
            'date_ref':local(day) if dated else None,'quantity_ref':local('60'),'unit_ref':local('minutes'),'exclusion':'none'}
        raw['assertions'].append(assertion(notes,'extra_time',[],quote,subject='clinician',encounter=scope,
            temporality=timing or scope,kind='time_total' if account else 'time_work',
            consumer_role='time_total' if account else 'time_work',time=t,clinically_relevant=False))
        if account:
            raw['time_accounts'].append({'id':'other_account','owner_assertion_id':'extra_time',
                'date_ref':local(day),'total_ref':local('60'),'unit_ref':local('minutes'),
                'included_assertion_ids':[],'excluded_assertion_ids':[],'overlap_assertion_ids':[],'closed':False})
        if linked:
            raw['time_accounts'][0]['included_assertion_ids'].append('extra_time')
            raw['relationships'].append({'id':'extra_member','kind':'account_includes','source_assertion_id':'total',
                'target_assertion_ids':['extra_time'],'evidence_refs':[ref(notes,quote)]})
        raw=extraction(notes,raw['facts'],raw['assertions'],raw['relationships'],raw['time_accounts'])
        def change(check,*unused):
            if checker_unknown:next(a for a in check['assertions'] if a['id']=='extra_time').update(
                verdict='unknown',reason='Account ownership unresolved.')
        return coding_run((notes,i['fields'],i['definitions'],raw,i['attempts'][0]['assignment']),change)

    def test_exact_account_generates_eight_facts_without_code_authority(self):
        run=time_case();support=coding.office_time_facts(run)
        self.assertEqual(support['status'],'documented',support['blockers'])
        self.assertEqual(len(support['facts']),8)
        self.assertEqual(next(f['value'] for f in support['facts'] if f['key']=='time_minutes'),33)
        self.assertEqual(coding.office_service_eligibility(run),[])
        self.assertNotIn('code',support)

    def test_explicit_separate_time_domains_do_not_redefine_current_closed_account(self):
        for options in ({'scope':'past'},{'scope':'future'},{'scope':'current','performer':'staff'},
                        {'scope':'past','account':True}):
            with self.subTest(options=options):
                support=coding.office_time_facts(self.extra_time(**options))
                self.assertEqual(support['status'],'documented',support['blockers'])
                self.assertEqual(next(f['value'] for f in support['facts'] if f['key']=='time_minutes'),33)

    def test_unresolved_or_current_work_remains_account_obligation_and_linked_scope_still_checked(self):
        for options in ({'scope':'current'},{'scope':'unknown','timing':'unspecified'},
                        {'scope':'past','performer':'unknown'},{'scope':'past','dated':False},
                        {'scope':'past','checker_unknown':True},{'scope':'past','linked':True},
                        {'scope':'current','performer':'staff','linked':True}):
            with self.subTest(options=options):
                support=coding.office_time_facts(self.extra_time(**options))
                self.assertEqual(support['status'],'needs_detail')

    def test_account_scope_membership_exclusions_and_closedness_are_required(self):
        changes=[lambda raw:raw['time_accounts'][0].update(closed=False),
            lambda raw:raw['time_accounts'][0]['included_assertion_ids'].remove('work3'),
            lambda raw:raw['time_accounts'][0]['excluded_assertion_ids'].remove('staff'),
            lambda raw:next(a for a in raw['assertions'] if a['id']=='work1')['time'].update(performer='staff'),
            lambda raw:next(a for a in raw['assertions'] if a['id']=='work2').update(encounter='past')]
        for change in changes:
            with self.subTest(change=change):
                support=coding.office_time_facts(time_case(change))
                self.assertNotEqual(support['status'],'documented')

    def test_licensed_mdm_is_not_inferred_from_graph_time(self):
        run=time_case();run.context={'em_basis':'mdm'}
        rule={'kind':'office_em','requirements':{},'reference':'synthetic','instructions':[],'description':'Synthetic'}
        self.assertFalse(coding.licensed_cpt_rule(run,'unit','source',rule)['valid'])

    def test_checked_context_survives_missing_time_account_but_never_attests_time(self):
        run=time_case(lambda raw:raw['time_accounts'][0].update(closed=False))
        self.assertNotEqual(coding.office_time_facts(run)['status'],'documented')
        self.assertEqual(coding.context_suggestions(run),
            {'setting':'outpatient_office','patient_status':'established','em_basis':'time'})

    def test_supplied_licensed_time_terms_bounds_and_exclusion_instructions_are_preserved(self):
        run=time_case()
        run.context={**coding.context_suggestions(run),'time_minutes':'33',
            'time_evidence':'Nora spent a total of 33 minutes on this service date.',
            'time_same_day':True,'time_qualified_clinician':True,'time_excludes_separately_reported':True}
        rule={'kind':'office_em','reference':'synthetic rule only','description':'Synthetic only','instructions':[],
            'requirements':{'setting':'outpatient_office','patient_status':'established','mdm':None,
                'time':{'minimum':30,'maximum':39,'basis':'total_practitioner_same_day',
                    'total_time_terms':['total'],'excluded_activities':['nonqualifying activities']}}}
        good=coding.licensed_cpt_rule(run,'unit',run.context['time_evidence'],rule)
        self.assertTrue(good['valid'],good['errors'])
        self.assertEqual(good['instructions'][0]['text'],'Exclude from time: nonqualifying activities')
        bad=deepcopy(rule);bad['requirements']['time']['total_time_terms']=['unmentioned licensed phrase']
        self.assertFalse(coding.licensed_cpt_rule(run,'unit',run.context['time_evidence'],bad)['valid'])
        bad=deepcopy(rule);bad['requirements']['time']['minimum']=34
        self.assertFalse(coding.licensed_cpt_rule(run,'unit',run.context['time_evidence'],bad)['valid'])

    def test_licensed_procedure_citation_requires_same_checked_occurrence(self):
        notes='Patient: Synthetic Ada Vale\nA puncture was performed; her mother underwent incision.'
        fields,defs=definitions()
        facts=[fact(notes,'f0','Synthetic Ada Vale',kind='identity'),fact(notes,'f1','A puncture was performed')]
        aa=[assertion(notes,'a0',['f0'],'Synthetic Ada Vale',kind='identity',identity_role='patient_name',consumer_role='none'),
            assertion(notes,'a1',['f1'],'A puncture was performed',consumer_role='procedure_performed')]
        run=coding_run((notes,fields,defs,extraction(notes,facts,aa),assignments(fields,{'field0':['f1']})))
        def judge(word):
            start=notes.index(word)
            rule={'kind':'procedure','reference':'synthetic only','description':'Synthetic only','instructions':[],
                'requirements':{'performed_terms':[word],'required_details':[]}}
            spans=[{'text':word,'start':start,'end':start+len(word),'context_index':0,'status':'valid'}]
            return coding.licensed_cpt_rule(run,'unit',word,rule,evidence_spans=spans)
        self.assertTrue(judge('puncture')['valid'])
        self.assertFalse(judge('incision')['valid'])
        rule={'kind':'procedure','reference':'synthetic only','description':'Synthetic only','instructions':[],
            'requirements':{'performed_terms':['puncture'],'required_details':[]}}
        self.assertFalse(coding.licensed_cpt_rule(run,'unit','puncture',rule)['valid'])


def encounter_for(run):
    i=run.inputs['source_interpretation'];identity=i['identity']
    patient=N(pk=identity['patient_id'],display_name=identity['patient_display_name'],reference=identity['patient_reference'])
    version=N(fields=i['fields'],semantic_definitions=i['definitions'],prepared_sha256='d'*64,
              template=N(sha256='e'*64))
    return N(pk=identity['encounter_id'],patient_id=patient.pk,department_id=identity['department_id'],
        template_version_id=identity['template_version_id'],service_date=date.fromisoformat(identity['service_date']),
        patient=patient,template_version=version,notes=i['notes'],answers=run.inputs['answers'],revision=1,status='review')


class GraphCodingIntegrationTests(SimpleTestCase):
    def test_inline_graph_marker_resolves_only_authoritative_approved_components(self):
        from core import semantic_review, word_contract
        from core import source_interpretation_store as store
        run = coding_run(symptom_case())
        encounter = encounter_for(run)
        approved = deepcopy(encounter.template_version.semantic_definitions)
        encounter.template_version.semantic_definitions = {}
        encounter.template_version.preparation_id = 'inline-preparation'
        encounter.template_version.preparation = N(config={word_contract.CONFIG_KEY:word_contract.GRAPH_PROFILE},
            candidate_info={word_contract.INFO_KEY:{'definitions':approved}})
        with patch.object(semantic_review, 'definitions_for', return_value=approved), \
             patch.object(semantic_review, 'validate_answer'), \
             patch.object(store, 'load_for_answer', return_value=run.inputs[coding.INPUT_KEY]):
            self.assertEqual(coding.snapshot(encounter),run.inputs[coding.INPUT_KEY])
        # Neither answer markers nor an inline marker can manufacture approval.
        with patch.object(semantic_review, 'definitions_for', return_value={}):
            with self.assertRaisesMessage(ValidationError,'graph_requires_approved_components'):
                coding.snapshot(encounter)
        encounter.answers = {}
        with patch.object(semantic_review, 'definitions_for', side_effect=AssertionError('No generation exists')):
            self.assertIsNone(coding.snapshot(encounter))

    def test_snapshot_validates_every_saved_answer_and_cannot_fall_back_when_scope_removed(self):
        from core import semantic_review, source_interpretation_store
        run=coding_run(symptom_case());encounter=encounter_for(run);i=run.inputs['source_interpretation']
        field=deepcopy(encounter.template_version.fields[0]);field['key']='field1'
        encounter.template_version.fields.append(field)
        encounter.template_version.semantic_definitions['field1']=deepcopy(i['definitions']['field0'])
        encounter.answers['field1']=deepcopy(encounter.answers['field0'])
        with patch.object(semantic_review,'definitions_for',return_value=encounter.template_version.semantic_definitions), \
             patch.object(semantic_review,'validate_answer',return_value={}) as validate, \
             patch.object(source_interpretation_store,'load_for_answer',return_value=i):
            self.assertEqual(coding.snapshot(encounter),i)
            self.assertEqual([call.args[1]['key'] for call in validate.call_args_list],['field0','field1'])
            encounter.answers['field1'].pop('fact_scope_contract')
            with self.assertRaisesMessage(ValidationError,'mixed_generation_contracts'):coding.snapshot(encounter)

    def test_snapshot_keeps_graph_once_and_context_is_only_suggested_metadata(self):
        from core import coding_service, coding_dispatch
        run=time_case();encounter=encounter_for(run);i=run.inputs['source_interpretation']
        with patch.object(coding,'snapshot',return_value=i) as stored, \
             patch.object(coding_dispatch,'contract',return_value=corti_coding.CONTRACT), \
             patch.object(coding_dispatch,'provider',return_value='corti'), \
             patch.object(coding_service.CodingContext.objects,'filter') as contexts, \
             patch.object(coding_service,'release_snapshot',return_value=[]), \
             patch.object(coding_service,'patient_name_inputs',side_effect=AssertionError('legacy identity parser')):
            contexts.return_value.first.return_value=None
            inputs,context,releases,digest=coding_service.input_snapshot(encounter)
        stored.assert_called_once_with(encounter)
        self.assertEqual(inputs['source_interpretation'],i)
        self.assertEqual(inputs['notes'],i['notes'])
        self.assertEqual(context['setting'],'outpatient_office')
        self.assertEqual(context['patient_status'],'established')
        self.assertEqual(context['em_basis'],'time')
        self.assertEqual(context['time_minutes'],'')
        self.assertFalse(context['time_qualified_clinician'])
        self.assertFalse(context['time_same_day'])
        self.assertFalse(context['time_excludes_separately_reported'])
        self.assertEqual(digest,coding_service.digest({'inputs':inputs,'context':context,'releases':releases}))

    def test_new_lineage_activates_standalone_contract_without_relabelling_first_run(self):
        from core import coding_dispatch, corti_prediction
        from core.models import CodingRun
        encounter=encounter_for(coding_run(symptom_case()))
        first=N(config={'clinical_source_contract':coding_engine.QUALIFIED_SOURCE_CONTRACT})
        with patch.object(coding_dispatch,'provider',return_value='corti'), \
             patch.object(corti_prediction,'configuration',return_value={'provider':'corti'}), \
             patch.object(CodingRun.objects,'filter') as runs, patch.object(coding,'snapshot',return_value={'checked':True}) as stored:
            runs.return_value.order_by.return_value.first.return_value=first
            result=coding_dispatch.configuration(N(),encounter)
        self.assertEqual(result['clinical_source_contract'],coding.CONTRACT)
        self.assertEqual(result['coding_diagnostic_contract'],corti_coding.DIAGNOSTIC_CONTRACT)
        self.assertEqual(first.config,{'clinical_source_contract':coding_engine.QUALIFIED_SOURCE_CONTRACT})
        stored.assert_called_once_with(encounter)
        self.assertNotIn(coding.CONTRACT,coding_engine.SOURCE_CONTRACTS)

    def test_legacy_configuration_never_loads_graph_or_adds_diagnostics(self):
        from core import coding_dispatch, corti_prediction
        from core.models import CodingRun
        encounter=N(answers={'old':{'text':'legacy'}},template_version=N(semantic_definitions={}))
        first=N(config={'clinical_source_contract':coding_engine.QUALIFIED_SOURCE_CONTRACT})
        with patch.object(coding_dispatch,'provider',return_value='corti'), \
             patch.object(corti_prediction,'configuration',return_value={'provider':'corti'}), \
             patch.object(coding_dispatch,'source_context_enabled',return_value=True), \
             patch.object(CodingRun.objects,'filter') as runs, patch.object(coding,'snapshot',side_effect=AssertionError('legacy read')):
            runs.return_value.order_by.return_value.first.return_value=first
            result=coding_dispatch.configuration(N(),encounter)
        self.assertEqual(result['clinical_source_contract'],coding_engine.QUALIFIED_SOURCE_CONTRACT)
        self.assertNotIn('coding_diagnostic_contract',result)

    def test_unsupported_provider_persists_actionable_failed_run_without_prediction(self):
        from core import coding_dispatch, coding_provider, coding_service, coding_recovery
        encounter=encounter_for(coding_run(symptom_case()));actor=N()
        with patch.object(coding_dispatch,'provider',return_value='existing'), \
             patch.object(coding_provider,'configuration',return_value={'provider':'fixture'}), \
             patch.object(coding,'snapshot',side_effect=AssertionError('no provider switch')):
            with self.assertRaisesMessage(ValidationError,'requires Corti'):
                coding_dispatch.configuration(actor,encounter)
        with patch.object(coding_service,'locked_encounter',return_value=encounter), \
             patch.object(coding_service,'eligible',return_value=True), \
             patch.object(coding_service,'input_snapshot',return_value=({'source_interpretation':{}},{},[{'coding_digest':'bound'}],'a'*64)), \
             patch.object(coding_service.CodingRun.objects,'filter') as rows, \
             patch.object(coding_recovery,'reuse_for_context',return_value=None), \
             patch.object(coding_dispatch,'configuration',side_effect=ValidationError('Coding requires Corti; no prediction sent.')), \
             patch.object(coding_service.CodingRun.objects,'create',return_value=N(pk='failed')) as create, \
             patch.object(coding_service,'audit'):
            rows.return_value.first.return_value=None
            encounter.department=N()
            coding_service.ensure_run.__wrapped__(encounter,actor,automatic=True)
        self.assertEqual(create.call_args.kwargs['state'],'failed')
        self.assertEqual(create.call_args.kwargs['error_code'],'service_unavailable')
        self.assertIn('requires Corti',create.call_args.kwargs['error'])
        self.assertEqual(create.call_args.kwargs['actual_cost'],0)
