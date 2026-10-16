"""Focused clinical-boundary checks. Synthetic source; no provider or database."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import date
import hashlib
import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import corti_coding, corti_semantics as semantics, coding_engine as engine
from core.coding_terminology import parse_reference, search_index
from core.corti_response import CatalogRelease, DatedTerminology

SOURCE = (Path(__file__).parent/'fixtures/rowan/source.txt').read_bytes().decode()


class SourceTimeChecks(SimpleTestCase):
    def test_documented_time_is_practitioner_total_not_symptom_episode(self):
        result = semantics.office_time_facts(SOURCE)
        self.assertEqual(result['status'], 'documented', result['blockers'])
        self.assertFalse(result['clinician_confirmed'])
        self.assertEqual({f['key'] for f in result['facts']}, set(semantics.REQUIRED_TIME_FACTS))
        self.assertEqual(next(f['value'] for f in result['facts'] if f['key']=='time_minutes'), 24)
        for fact in result['facts']:
            self.assertEqual(SOURCE[fact['start']:fact['end']], fact['quote'])
        self.assertEqual(semantics.office_time_facts(SOURCE.replace('24 minutes','37 minutes'))['facts'][2]['value'],37)

    def test_missing_or_conflicting_facts_never_borrow_symptom_minutes(self):
        for note in [SOURCE.replace('was 24 minutes','was not 24 minutes'),
                     SOURCE.replace('Total physician time','Total staff time'),
                     SOURCE.replace(' on the date of service',''),
                     SOURCE.replace('This total excludes clinical staff time and time for separately reported services.',''),
                     SOURCE + '\r\nTotal physician time on the date of service was 40 minutes.',
                     SOURCE + '\r\nThis is a new patient.',
                     SOURCE.replace('excludes clinical staff','includes clinical staff'),
                     SOURCE.replace('excludes clinical staff','does not exclude clinical staff'),
                     SOURCE.replace('based on total physician time','not based on total physician time')]:
            with self.subTest(note=note[-200:]):
                self.assertEqual(semantics.office_time_facts(note)['status'],'requires_clarification')

    def test_examples_other_patients_and_future_services_cannot_supply_facts(self):
        for prefix in ['Example:\r\n', 'Quoted example note:\r\n']:
            self.assertEqual(semantics.office_time_facts(prefix+SOURCE)['status'],'requires_clarification')
        for replacement in ['For another patient, total physician time', 'Yesterday, total physician time',
                            'The quoted text says "Total physician time', "The nurse's total physician time"]:
            self.assertEqual(semantics.office_time_facts(SOURCE.replace('Total physician time',replacement))['status'],
                             'requires_clarification')

    def test_time_prefix_cannot_hide_another_person_or_an_unqualified_remainder(self):
        for suffix in (' for Jane Doe', ' for the nurse', ' for another patient', ' or 40 minutes'):
            note=SOURCE.replace('was 24 minutes, including', 'was 24 minutes'+suffix+', including')
            with self.subTest(suffix=suffix):
                result=semantics.office_time_facts(note)
                self.assertEqual(result['status'],'requires_clarification')
                self.assertNotIn('time_minutes',[f['key'] for f in result['facts']])

    def test_exclusion_cannot_cross_into_a_later_inclusion_predicate(self):
        original='excludes clinical staff time and time for separately reported services'
        for predicate in (
            'excludes clinical staff time but includes time for separately reported services',
            'excludes clinical staff time and includes time for separately reported services',
            'excludes time for separately reported services but includes clinical staff time',
            'includes clinical staff time but excludes time for separately reported services'):
            with self.subTest(predicate=predicate):
                result=semantics.office_time_facts(SOURCE.replace(original,predicate))
                self.assertEqual(result['status'],'requires_clarification')
                self.assertIn('The documented total includes staff time or separately reported services.',result['blockers'])
                self.assertFalse({'time_excludes_staff','time_excludes_separately_reported'} <=
                                 {f['key'] for f in result['facts']})

    def test_neither_and_exceptions_cannot_establish_complete_exclusions(self):
        original='excludes clinical staff time and time for separately reported services'
        for predicate in (
            'excludes neither clinical staff time nor time for separately reported services',
            'excludes clinical staff time except five minutes and time for separately reported services'):
            with self.subTest(predicate=predicate):
                result=semantics.office_time_facts(SOURCE.replace(original,predicate))
                self.assertEqual(result['status'],'requires_clarification')
                self.assertIn('The time-exclusion assertion is negated or qualified.',result['blockers'])
                self.assertFalse({'time_excludes_staff','time_excludes_separately_reported'} &
                                 {f['key'] for f in result['facts']})

    def test_exact_citations_are_not_semantic_proof(self):
        facts=semantics.office_time_facts(SOURCE)['facts']
        quote='Blood pressure 118/74 mmHg';start=SOURCE.index(quote)
        spans,status=semantics.checked_spans([{'contextIndex':0,'start':start,'end':start+len(quote),'text':quote}],SOURCE)
        self.assertEqual(status,'valid')
        self.assertEqual(semantics.citation_adequacy(spans,facts)['status'],'insufficient_for_time_review')
        self.assertEqual(set(semantics.citation_adequacy(spans,facts)['missing_facts']),set(semantics.REQUIRED_TIME_FACTS))
        spans=[{'status':'valid','context_index':0,'start':0,'end':len(SOURCE)}]
        self.assertEqual(semantics.citation_adequacy(spans,facts)['status'],'complete_for_time_review')
        self.assertFalse(semantics.office_time_facts(SOURCE)['clinician_confirmed'])

    def test_procedure_system_is_independent_of_provider_label(self):
        for code in ('G8752','G8754','J1234','A1234'):
            classification=semantics.classify_selected({'system':'cpt','code':code})
            self.assertEqual(classification['system'],'HCPCS Level II')
            self.assertTrue(classification['mismatch'])
            self.assertEqual(classification['dated_membership'],'not_established_by_syntax')
        self.assertEqual(semantics.classify_selected({'system':'cpt','code':'99213'})['system'],'CPT')
        self.assertEqual(semantics.classify_selected({'system':'cpt','code':'9921X'})['system'],'unknown')
        self.assertEqual(semantics.classify_selected({'system':'icd10cm-outpatient','code':'R1013'})['system'],'ICD-10-CM')


class OfficialRouteVocabularyChecks(SimpleTestCase):
    def setUp(self):
        # Exact reduced FY2027 Index routes and Tabular descriptions. This unit
        # fixture tests vocabulary joining, not an installed-release claim.
        parsed=parse_reference('''<ICD10CM.index><version>2027</version><letter><mainTerm><title>Pain(s)</title>
          <term level="1"><title>abdominal</title><term level="2"><title>upper</title>
            <term level="3"><title>epigastric</title><code>R10.13</code></term></term></term>
          <term level="1"><title>epigastric, epigastrium</title><code>R10.13</code></term>
          </mainTerm><mainTerm><title>Bloating</title><code>R14.0</code></mainTerm></letter></ICD10CM.index>''',
          '''<ICD10CM.tabular><version>2027</version><chapter><name>unit</name><section id="unit">
          <diag><name>R10.13</name><desc>Epigastric pain</desc></diag>
          <diag><name>R14.0</name><desc>Abdominal distension (gaseous)</desc></diag>
          </section></chapter></ICD10CM.tabular>''',
          {'R10.13':'Epigastric pain','R14.0':'Abdominal distension (gaseous)'})
        self.reference=SimpleNamespace(**parsed,release_id='unit',release=SimpleNamespace(version='FY2027-unit'))
        self.lookup=engine.index_lookup(self.reference)
        self.entry=next(e for e in parsed['index'] if e['term']=='epigastric, epigastrium')
        self.quote='Synthetic Rowan Blake reports intermittent epigastric pain after large meals for 10 days.'
        self.concept={'id':'c1','kind':'symptom','term':'Epigastric pain','subject':'patient',
                      'evidence':self.quote,'relevant':True,'certainty':'confirmed','index_terms':['Pain, epigastric'],
                      'integral_to':'','temporality':'current','missing_detail':''}

    def test_index_synonym_requires_independent_tabular_correspondence(self):
        self.assertIn(self.entry,search_index(self.reference,['Pain, epigastric']))
        self.assertTrue(engine.index_route_errors(self.entry,self.concept,self.lookup))
        self.assertEqual(engine.index_route_errors(self.entry,self.concept,self.lookup,
            code_description='Epigastric pain'),[])
        for evidence,description in [('The patient has epigastric pain.','Left epigastric pain'),
                                     ('The patient denies epigastric pain.','Epigastric pain'),
                                     ('The patient has pain in the chest.','Epigastric pain')]:
            with self.subTest(evidence=evidence):
                self.assertTrue(engine.index_route_errors(self.entry,{**self.concept,'evidence':evidence},self.lookup,
                    code_description=description))

    def test_other_index_ancestors_are_not_waived(self):
        abdominal=next(e for e in self.reference.index if e['term']=='epigastric')
        self.assertTrue(engine.index_route_errors(abdominal,self.concept,self.lookup,code_description='Epigastric pain'))

    def test_comma_alias_cannot_join_unrelated_site_and_symptom_words(self):
        for evidence in ('The patient reports epigastric fullness and shoulder pain.',
                         'The patient reports epigastric fullness. The patient reports shoulder pain.',
                         'The fullness is epigastric. Pain is in the shoulder.',
                         'The patient denies epigastric pain and reports shoulder pain.'):
            with self.subTest(evidence=evidence):
                self.assertTrue(engine.index_route_errors(self.entry,
                    {**self.concept,'evidence':evidence},self.lookup,code_description='Epigastric pain'))
                proposal={'id':'selected:0','code':'R10.13','terminology':{'description':'Epigastric pain'},
                    'evidence':[{'text':evidence,'status':'valid','context_index':0,'start':0,'end':len(evidence)}]}
                run=SimpleNamespace(inputs={'notes':evidence},context={'setting':'outpatient_office'})
                with patch.object(engine,'contextual_validation',return_value={'valid':True,'instructions':[]}):
                    concept,candidate,check=corti_coding._icd_source(run,self.reference,proposal,['R10.13'])
                self.assertIsNone(candidate)

    def test_direct_bridge_joins_same_selected_code_without_promoting_alternatives(self):
        at=SOURCE.index(self.quote)
        run=SimpleNamespace(inputs={'notes':SOURCE},context={'setting':'outpatient_office'})
        proposal={'id':'selected:0','code':'R10.13','terminology':{'description':'Epigastric pain'},
                  'evidence':[{'text':self.quote,'status':'valid','context_index':0,'start':at,'end':at+len(self.quote)}]}
        with patch.object(engine,'contextual_validation',return_value={'valid':True,'instructions':[]}):
            concept,candidate,check=corti_coding._icd_source(run,self.reference,proposal,['R10.13','R14.0'])
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate['code'],'R10.13')
        self.assertEqual(candidate['path'],['Pain(s)','epigastric, epigastrium'])
        self.assertEqual(concept['term'],'Epigastric pain')
        self.assertEqual(check['disposition'],'eligible')

    def bridge(self, extra=()):
        def selected(code, system, quote):
            at=SOURCE.index(quote)
            return {'code':code,'system':system,'display':'provider text',
                    'evidences':[{'contextIndex':0,'start':at,'end':at+len(quote),'text':quote}]}
        rows=[selected('R10.13','icd10cm-outpatient',self.quote),
              selected('R14.0','icd10cm-outpatient','The patient also reports abdominal bloating for three weeks.'),
              selected('99213','cpt','This is an established patient who was seen by this same gastroenterologist five months ago.'),
              selected('G8752','cpt','Blood pressure 118/74 mmHg'),
              selected('G8754','cpt','Blood pressure 118/74 mmHg')]
        rows[2]['display']='+PR OFFICE OUTPATIENT VISIT 15 MINUTES'
        rows.extend(extra)
        response={'codes':rows,'candidates':[{'code':'99999','system':'cpt'}]}
        original=deepcopy(response)
        terms=DatedTerminology([CatalogRelease('icd10cm-outpatient','FY2027-unit',date(2026,10,1),date(2027,9,30),
            'https://www.cms.gov/unit','a'*64,{'R10.13':'Epigastric pain','R14.0':'Abdominal distension (gaseous)'},'unit')])
        request={'system':['icd10cm-outpatient','cpt'],'context':[{'type':'text','text':SOURCE}]}
        run=SimpleNamespace(inputs={'engine_contract':corti_coding.CONTRACT,'notes':SOURCE,'service_date':'2026-10-16'},
                            context={'setting':'outpatient_office'},config={'mode':'live'},
                            requests=[{'response_sha256':hashlib.sha256(json.dumps(response).encode()).hexdigest()}])
        with patch.object(corti_coding,'terminology',return_value=(terms,{'available':False})), \
             patch.object(corti_coding,'identity_blockers',return_value=[]), \
             patch.object(corti_coding.corti_prediction,'payload',return_value=request), \
             patch.object(corti_coding.corti_prediction,'execute',return_value=response), \
             patch.object(engine,'reference_for',return_value=self.reference), \
             patch.object(engine,'contextual_validation',return_value={'valid':True,'instructions':[]}):
            run.result=corti_coding.generate(run)
        self.assertEqual(response,original)
        return run,terms

    def test_mislabelled_hcpcs_are_held_without_blocking_supported_icd(self):
        run,terms=self.bridge()
        rows=run.result['suggestions']
        self.assertEqual([r['system'] for r in rows],['ICD-10-CM','ICD-10-CM','CPT','HCPCS Level II','HCPCS Level II'])
        self.assertEqual([r['eligible'] for r in rows],[True,True,False,False,False])
        self.assertEqual(run.result['global_blockers'],[])
        self.assertEqual(rows[2]['description'],'')
        self.assertIn('15 MINUTES',rows[2]['provider_display'])
        self.assertEqual(rows[2]['semantic_support']['provider_citation_adequacy']['status'],'insufficient_for_time_review')
        self.assertEqual(run.result['adapter']['diagnostics']['provider_response']['codes'][3]['system'],'cpt')
        self.assertNotIn('selected:3',run.result['candidates'])
        self.assertNotIn('99999',[r['code'] for r in rows])
        # Forging the cached eligibility bit still cannot put a quarantined
        # identifier through selected-code revalidation at approval/export.
        rows[3]['eligible']=True
        with patch.object(corti_coding,'identity_blockers',return_value=[]), \
             patch.object(corti_coding,'terminology',return_value=(terms,{'available':False})), \
             self.assertRaises(ValidationError):
            corti_coding.validate_selection(run,{'selected_ids':['selected:3'],'overrides':{}})

    def test_unclassified_selected_objects_still_raise_global_review_block(self):
        run,_=self.bridge([{'code':'bad-code','system':'cpt','evidences':[]}])
        self.assertIn('Malformed or duplicate provider selections require diagnostic review.',run.result['global_blockers'])
