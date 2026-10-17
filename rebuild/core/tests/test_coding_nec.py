"""Retained and adversarial clinical specificity/conditional-instruction proofs."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from types import SimpleNamespace as N
from unittest.mock import patch
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from core import coding_engine as engine, coding_nec as nec, coding_reference_store as store, corti_coding,corti_prediction
from core.coding_terminology import reference_digest
from core.corti_response import CatalogRelease,DatedTerminology
from core.models import CodeSet, CodingRelease
from core.tests.test_coding_prediction_reference import MemoryProjection
from core.tests.test_coding_source_governance import SourceGovernanceCodingTests as Retained, NOTES,FIXTURE


def retained_case():
    """Reuse fixture methods without invoking another TestCase's lifecycle."""
    case=Retained();raw=deepcopy(FIXTURE['reference']);raw['release']=N(**raw['release'])
    case.reference=N(**raw);release=case.reference.release
    case.terms=DatedTerminology([CatalogRelease('icd10cm-outpatient',release.version,
        date(2026,10,1),date(2027,9,30),release.source_url,release.sha256,
        case.reference.tabular['codes'],release.source_url)],unavailable_reasons={
            'cpt':FIXTURE['runs'][0]['result']['suggestions'][2]['terminology']['reason']})
    return case


class GuidelineProjection(MemoryProjection):
    """Mirror the exact scalar metadata expression; SQL is tested separately."""
    def read(self, expression, params=()):
        if "'format', tabular->'format'" in expression:
            assert "provenance #>> '{manifest,files,guidelines,sha256}'" in expression
            value={k:v for k,v in self.full['tabular'].items() if k not in ('codes','nodes')}
            value['guidelines_sha256']=self.full.get('provenance',{}).get('manifest',{}).get('files',{}).get('guidelines',{}).get('sha256')
            return self.bounded(value)
        return super().read(expression,params)


def metadata(full):
    class BoundMetadata(N):
        @property
        def provenance(self):
            raise AssertionError('Deferred provenance must not be fetched.')
    return BoundMetadata(pk=vars(full).get('id','retained-reference'),release_id=full.release_id,release=full.release,
        digest=full.digest,full=vars(full))


class NECProofTests(SimpleTestCase):
    def setUp(self):
        self.t = retained_case()

    def route(self, text, quote=None):
        return self.t.route('Patient: Synthetic Uma Bell\nHistory of present illness\n'+text,quote or text,'R13.19')

    def test_raw_authority_is_complete_and_contains_no_code_mapping(self):
        raw, relations = nec.load()
        self.assertEqual(len(raw['records']),71)
        self.assertEqual(len({r['descriptor_id'] for r in relations}),5)
        self.assertEqual(len(relations),13)
        terms=[(r['parent']['terms'],r['child']['terms']) for r in relations]
        self.assertTrue(any('Dysphagia' in p and 'Esophageal Dysphagia' in c for p,c in terms))
        self.assertTrue(any('Cerebrovascular Disorders' in p and 'Cerebrovascular Insufficiency' in c for p,c in terms))
        self.assertTrue(any('Stroke' in p and 'Stroke, Acute' in c for p,c in terms))
        self.assertNotIn('R13.19',nec.RESOURCE.read_text())
        self.assertEqual(nec.parse_resource(json.loads(nec.RESOURCE.read_bytes())),relations)
        family=next(iter(nec.condition_families(raw).values()))
        self.assertEqual((len(family['descriptors']),len(family['concepts']),family['term_count'],family['rows']),
                         (81,240,626,1258))

    def test_condition_family_pages_counts_types_and_connectivity_are_not_optional(self):
        original,_=nec.load()
        def repack(item,change):
            value=json.loads(item['raw']);change(value)
            item['raw']=json.dumps(value);item['sha256']=hashlib.sha256(item['raw'].encode()).hexdigest()
        for kind in ('missing_page','count','version','duplicate','missing_inventory','query','cycle'):
            raw=deepcopy(original);family=raw['conditional_families'][0]
            if kind=='missing_page':family['pages'].pop()
            elif kind=='count':repack(family['count'],lambda value:value['results']['bindings'][0]['count'].update(value='1257'))
            elif kind=='version':repack(family['pages'][0],lambda value:value['results']['bindings'][0]['term'].update(value=nec.BASE.replace('2026','2025')+'T1'))
            elif kind=='duplicate':repack(family['pages'][0],lambda value:value['results']['bindings'].__setitem__(1,deepcopy(value['results']['bindings'][0])))
            elif kind=='missing_inventory':repack(family['inventory'],lambda value:value['results']['bindings'].pop())
            elif kind=='query':family['pages'][0]['query']=family['pages'][0]['query'].replace('broaderDescriptor','relatedDescriptor')
            elif kind=='cycle':
                def change(value):
                    for row in value['results']['bindings']:
                        if row['descriptor']['value']==family['root']:row['parent']['value']=family['root']
                for page in family['pages']:repack(page,change)
            with self.subTest(kind=kind),self.assertRaises(ValidationError):nec.condition_families(raw)

    def test_missing_corrupt_cyclic_or_retyped_relation_cannot_license_specificity(self):
        raw,_=nec.load()
        mutations=[]
        missing=deepcopy(raw);missing['records'].pop();mutations.append(missing)
        corrupt=deepcopy(raw);corrupt['records'][0]['raw']+=' ';mutations.append(corrupt)
        for mode in ('cycle','predicate'):
            changed=deepcopy(raw)
            item=next(z for z in changed['records'] if '/M0005756.json' in z['url'])
            row=json.loads(item['raw'])
            if mode=='cycle':row['narrowerConcept']=[row['@id']]
            else:row['@context']['narrowerConcept']['@id']=nec.VOCAB+'relatedConcept'
            item['raw']=json.dumps(row);item['sha256']=hashlib.sha256(item['raw'].encode()).hexdigest();mutations.append(changed)
        for value in mutations:
            with self.subTest(mode=value['records'][0]['sha256']),self.assertRaises(ValidationError):nec.parse_resource(value)

    def test_retained_r13_route_and_approval_recompute_both_proofs(self):
        run=self.t.result();row=run.result['suggestions'][0]
        self.assertTrue(row['eligible']);candidate=run.result['candidates']['selected:0'][0]
        self.assertEqual(candidate['path'],['Dysphagia','specified NEC'])
        self.assertEqual(candidate['clinical_specificity']['source_sha256'],hashlib.sha256(NOTES.encode()).hexdigest())
        self.assertEqual(len(candidate['clinical_specificity']['index_family_ids']),22)
        resolution=next(i['resolution'] for i in row['instructions'] if i.get('resolution'))
        self.assertEqual(resolution['source_sha256'],hashlib.sha256(NOTES.encode()).hexdigest())
        selection={'selected_ids':['selected:0','selected:1'],'overrides':{}}
        def catalog(**kw):return N(first=lambda:N(description=self.t.reference.tabular['codes'][kw['code']]))
        with patch.object(corti_coding,'terminology',return_value=(self.t.terms,run.result['cpt'])),\
             patch.object(engine,'reference_for',return_value=self.t.reference),\
             patch.object(engine.Code.objects,'filter',side_effect=catalog):
            self.assertEqual(corti_coding.validate_selection(run,selection),selection)
            candidate['clinical_specificity']['child_concept_id']='forged'
            with self.assertRaises(ValidationError):corti_coding.validate_selection(run,selection)

    def test_real_projection_paths_preserve_results_and_selection_proof_without_full_provenance(self):
        original=self.t.reference;run=self.t.result()
        selection={'selected_ids':['selected:0','selected:1'],'overrides':{}}
        with patch.object(store,'_Projection',GuidelineProjection),\
             patch.object(engine,'_loaded_reference',side_effect=AssertionError('No full reference fallback')):
            prediction=store.prediction_reference(metadata(original),['R13.19','R12'],source_contract=engine.CURRENT_SOURCE_CONTRACT)
            approval=store.selection_reference(metadata(original),run,selection)
        for reference in (prediction,approval):
            self.assertEqual(reference.guidelines_sha256,nec.GUIDELINES_SHA256)
            self.assertNotIn('provenance',vars(reference))
            self.assertNotIn('guidelines_sha256',reference.tabular)
            self.assertLess(reference.projection_bytes,100000)
        for contract in (engine.ASSERTION_SOURCE_CONTRACT,engine.CURRENT_SOURCE_CONTRACT):
            expected=self.t.result(contract=contract).result
            with patch.object(self.t,'reference',prediction):
                self.assertEqual(self.t.result(contract=contract).result,expected)
        def catalog(**kw):return N(first=lambda:N(description=original.tabular['codes'][kw['code']]))
        with patch.object(corti_coding,'terminology',return_value=(self.t.terms,run.result['cpt'])),\
             patch.object(engine,'reference_for',return_value=approval),\
             patch.object(engine.Code.objects,'filter',side_effect=catalog):
            self.assertEqual(corti_coding.validate_selection(run,selection),selection)

    def test_missing_or_wrong_projected_guideline_never_uses_deferred_fallback(self):
        original=self.t.reference
        expected=self.t.result(contract=engine.ASSERTION_SOURCE_CONTRACT).result
        for digest in (None,'0'*64,[],{'sha256':nec.GUIDELINES_SHA256}):
            full=deepcopy(original)
            full.provenance['manifest']['files']['guidelines']['sha256']=digest
            with patch.object(store,'_Projection',GuidelineProjection):
                reference=store.prediction_reference(metadata(full),['R13.19','R12'],source_contract=engine.CURRENT_SOURCE_CONTRACT)
            with self.subTest(digest=digest),patch.object(self.t,'reference',reference):
                self.assertFalse(nec._guideline_bound(reference))
                self.assertIsNone(self.route('The patient reports esophageal dysphagia today.'))
                self.assertEqual(self.t.result(contract=engine.ASSERTION_SOURCE_CONTRACT).result,expected)
        class Deferred(N):
            @property
            def provenance(self):raise AssertionError('Deferred access')
        self.assertFalse(nec._guideline_bound(Deferred(release=N(version='FY2027'))))
        self.assertFalse(nec._guideline_bound(Deferred(release=N(version='FY2027'),guidelines_sha256=None)))

    def test_unfamiliar_complete_assertions_have_the_same_general_route(self):
        for text in ('The patient reports esophageal dysphagia for nine days.',
                     'She experiences intermittent esophageal dysphagia after meals.',
                     'The patient endorses esophageal dysphagia today and nausea for two days.'):
            with self.subTest(text=text):self.assertIsNotNone(self.route(text))

    def test_general_family_proof_uses_an_independent_authoritative_relation(self):
        # A deliberately synthetic classification tree isolates the generic
        # algorithm. This is not a claim that these are real ICD assignments.
        reference=deepcopy(self.t.reference)
        head={'id':'synthetic-parent','term':'Cerebrovascular Disorders','title':'Cerebrovascular Disorders',
              'path':['Cerebrovascular Disorders'],'parent_id':None,'children':['synthetic-nec','synthetic-specific'],
              'code':None,'requires_review':False,'nonessential_modifiers':[]}
        entry={'id':'synthetic-nec','term':'specified NEC','parent_id':head['id'],'children':[],
               'path':[head['term'],'specified NEC'],'code':'SYNTHETIC-OTHER','requires_review':False}
        sibling={'id':'synthetic-specific','term':'occlusion','parent_id':head['id'],'children':[],
                 'path':[head['term'],'occlusion'],'code':'SYNTHETIC-SPECIFIC','requires_review':False}
        reference.index=[head,entry,sibling];reference.__dict__.pop('_index_lookup',None)
        text='The patient reports cerebrovascular insufficiency today.'
        concept=dict(id='offline',term=head['term'],index_terms=[head['term']],evidence=text,
            kind='diagnosis',certainty='confirmed',temporality='current',subject='patient',relevant=True,
            missing_detail='',integral_to='')
        notes='Patient: Synthetic Uma Bell\n'+text
        proof=nec.prove(reference,entry,concept,notes,source_contract=engine.CURRENT_SOURCE_CONTRACT)
        self.assertIsNotNone(proof)
        self.assertTrue(proof[1]['child_concept_id'].endswith('M0334622'))
        self.assertIsNone(nec.prove(reference,entry,concept,notes+'\nHer cerebrovascular disorders include occlusion.',
            source_contract=engine.CURRENT_SOURCE_CONTRACT))

    def test_specific_siblings_compounds_and_unrecognized_qualifiers_stay_held(self):
        for value in ('oropharyngeal','pharyngeal','pharyngoesophageal','oral phase',
                      'pharyngeal and esophageal','oral and esophageal','neurogenic esophageal',
                      'possible esophageal','historical esophageal','left esophageal','renal',
                      'severe','persistent','frequent','stable','corrected esophageal'):
            text='The patient reports '+value+' dysphagia today.'
            with self.subTest(value=value):self.assertIsNone(self.route(text))
        for suffix in (' She also reports pharyngeal dysphagia.',
                       ' Her dysphagia may involve the oral phase.',
                       ' The esophageal dysphagia statement was recorded in error.',
                       ' The patient denies dysphagia today.',
                       ' Esophageal dysphagia belongs to another patient.'):
            with self.subTest(suffix=suffix):self.assertIsNone(self.route('The patient reports esophageal dysphagia today.'+suffix))

    def test_optional_causal_instruction_retains_positive_uncertain_historical_and_alias_holds(self):
        base='The patient reports esophageal dysphagia today.'
        for suffix in (' She had a stroke last year.',
                       ' She has cerebrovascular disease.',
                       ' A prior cerebrovascular accident is possible.',
                       ' Her history includes CVA.',
                       ' Her history includes apoplexy.',
                       ' Her history includes transient ischemic attack.',
                       ' She has a history of strokes.',
                       ' She had three TIAs.',
                       ' Her history includes intracranial aneurysm.',
                       ' Her history includes moyamoya disease.',
                       ' Her history includes vertebrobasilar insufficiency.',
                       ' Her dysphagia follows an earlier neurological event.',
                       ' Her dysphagia began after a neurological event.',
                       ' Her swallowing symptoms started after an earlier neurological event.',
                       ' Her deglutition complaints emerged after an earlier neurological event.',
                       ' Her esophageal condition is attributable to an earlier neurological event.',
                       ' Her unexplained symptoms arose as a consequence of an earlier illness.',
                       ' Her dysphagia arose as a consequence of a neurological event.',
                       ' Her dysphagia is attributable to a prior neurological event.',
                       ' Her dysphagia developed in the context of an earlier illness.',
                       ' The condition may be linked to a prior event.',
                       ' Her dysphagia is due to another condition.',
                       ' She has TIA.'):
            with self.subTest(suffix=suffix):self.assertIsNone(self.route(base+suffix,base))
        for suffix in (' She denies stroke.', ' No history of cerebrovascular disease.',
                       ' No history of strokes.',
                       ' Her mother had a stroke last year.',
                       ' Her mother had a transient ischemic attack last year.',
                       ' Her mother had dysphagia after a neurological event.',
                       ' She has an unrelated wrist condition following a fall.',
                       ' Her unrelated wrist symptoms began after a fall.',
                       ' Her headache began after a minor injury.'):
            with self.subTest(suffix=suffix):self.assertIsNotNone(self.route(base+suffix,base))

    def test_absence_must_be_owned_and_causal_links_must_refer_to_the_target(self):
        base='The patient reports esophageal dysphagia today.'
        for suffix in ('\n"She denies stroke."','\nHypothetical example:\nShe denies stroke.',
                       '\nThe following clinical history may belong to another patient.\nShe denies stroke.'):
            with self.subTest(suffix=suffix):self.assertIsNone(self.route(base+suffix,base))
        for suffix in (' She has an unrelated wrist condition following a fall.',
                       ' The etiology of her wrist condition is attributable to a fall.',
                       ' Her mother has a condition following a fall.'):
            with self.subTest(suffix=suffix):self.assertIsNotNone(self.route(base+suffix,base))
        selection={'selected_ids':['selected:0'],'overrides':{}}
        def catalog(**kw):return N(first=lambda:N(description=self.t.reference.tabular['codes'][kw['code']]))
        for suffix,allowed in [('\n"She denies stroke."',False),
            ('\nHypothetical example:\nShe denies stroke.',False),
            ('\nThe following clinical history may belong to another patient.\nShe denies stroke.',False),
            ('\nShe has an unrelated wrist condition following a fall.',True)]:
            run=self.t.run_value(notes=NOTES+suffix);old=run.result
            with self.subTest(suffix=suffix),\
                 patch.object(corti_coding,'terminology',return_value=(self.t.terms,old['cpt'])),\
                 patch.object(engine,'reference_for',return_value=self.t.reference),\
                 patch.object(engine.Code.objects,'filter',side_effect=catalog):
                run.result=corti_coding.retained_result(run,corti_prediction.payload(run),
                    old['adapter']['diagnostics']['provider_response'],FIXTURE['runs'][0]['requests'][0]['response_sha256'])
                self.assertEqual(run.result['suggestions'][0]['eligible'],allowed)
                if allowed:self.assertEqual(corti_coding.validate_selection(run,selection),selection)
                else:
                    with self.assertRaises(ValidationError):corti_coding.validate_selection(run,selection)

    def test_causal_accounts_require_complete_positive_separation(self):
        base='The patient reports esophageal dysphagia today.'
        holds=(
            'Her swallowing difficulty began after an earlier neurological event.',
            'She has a swallowing difficulty that began after an earlier neurological event.',
            'A swallowing difficulty began after an earlier neurological event.',
            'These problems began after an earlier neurological event.',
            'It began after an earlier neurological event.',
            'This followed an earlier neurological event.',
            'Those difficulties appeared after an earlier neurological event.',
            'Her unexplained problem arose after an earlier neurological event.',
            'She has symptoms following an earlier neurological event.',
            'Her possibly unrelated symptoms started after an earlier neurological event.',
            'Her not unrelated symptoms started after an earlier neurological event.',
            'Her reportedly separate symptoms started after an earlier neurological event.',
            'Her possibly unrelated wrist symptoms started after an earlier neurological event.',
            'She has a possibly unrelated wrist condition following an earlier neurological event.',
            'Reportedly, her unrelated wrist symptoms started after an earlier neurological event.',
        )
        allows=(
            'Her unrelated wrist symptoms began after a fall.',
            'Her separate wrist problem began after a fall.',
            'She has a different wrist condition following a fall.',
            'The etiology of her wrist condition is attributable to a fall.',
            'Her mother had symptoms following an earlier neurological event.',
        )
        for suffix in holds:
            with self.subTest(suffix=suffix):self.assertIsNone(self.route(base+' '+suffix,base))
        for suffix in allows:
            with self.subTest(suffix=suffix):self.assertIsNotNone(self.route(base+' '+suffix,base))
        selection={'selected_ids':['selected:0'],'overrides':{}}
        def catalog(**kw):return N(first=lambda:N(description=self.t.reference.tabular['codes'][kw['code']]))
        for suffix,allowed in [(text,False) for text in holds]+[(text,True) for text in allows[:3]]:
            run=self.t.run_value(notes=NOTES+'\n'+suffix);old=run.result
            with self.subTest(boundary=suffix),\
                 patch.object(corti_coding,'terminology',return_value=(self.t.terms,old['cpt'])),\
                 patch.object(engine,'reference_for',return_value=self.t.reference),\
                 patch.object(engine.Code.objects,'filter',side_effect=catalog):
                run.result=corti_coding.retained_result(run,corti_prediction.payload(run),
                    old['adapter']['diagnostics']['provider_response'],FIXTURE['runs'][0]['requests'][0]['response_sha256'])
                self.assertEqual(run.result['suggestions'][0]['eligible'],allowed)
                if allowed:self.assertEqual(corti_coding.validate_selection(run,selection),selection)
                else:
                    with self.assertRaises(ValidationError):corti_coding.validate_selection(run,selection)

    def test_selected_causal_category_or_unbound_guideline_cannot_clear_the_instruction(self):
        run=self.t.result();row=run.result['suggestions'][0]
        instruction=next(i for i in row['instructions'] if i.get('resolution'))
        concept=row['concept']
        for selected in (['R13.19','I69.391'],['I69.991']):
            with self.subTest(selected=selected):
                self.assertIsNone(nec.conditional_following_resolution(
                    instruction,NOTES,concept,self.t.reference,selected))
        for version,digest in (('FY2026',nec.GUIDELINES_SHA256),('FY2027','0'*64),('FY2027',None)):
            reference=deepcopy(self.t.reference);reference.release.version=version
            reference.provenance['manifest']['files']['guidelines']['sha256']=digest
            with self.subTest(version=version,digest=digest):
                self.assertIsNone(nec.conditional_following_resolution(
                    instruction,NOTES,concept,reference,['R13.19']))

    def test_active_and_passive_causal_accounts_share_source_scope(self):
        base='The patient reports esophageal dysphagia today.'
        holds=(
            'She attributes her swallowing difficulty to an earlier neurological event.',
            'The patient relates this swallowing problem to an earlier neurological event.',
            'Her swallowing difficulty is attributed to an earlier neurological event.',
            'She associates these problems with an earlier neurological event.',
            'The patient links it to an earlier neurological event.',
            'She ascribes this complaint to an earlier neurological event.',
            'An earlier neurological event caused her swallowing difficulty.',
            'An earlier neurological event resulted in these problems.',
            'An earlier neurological event led to this difficulty.',
            'She attributes her possibly unrelated wrist symptoms to an earlier event.',
        )
        allows=(
            'She attributes her unrelated wrist symptoms to a fall.',
            'The patient relates her separate wrist problem to a fall.',
            'Her unrelated wrist condition is attributed to a fall.',
            'A fall caused her unrelated wrist symptoms.',
            'Her mother attributes her swallowing difficulty to an earlier neurological event.',
            'She denies stroke.',
        )
        for suffix in holds:
            with self.subTest(suffix=suffix):self.assertIsNone(self.route(base+' '+suffix,base))
        for suffix in allows:
            with self.subTest(suffix=suffix):self.assertIsNotNone(self.route(base+' '+suffix,base))
        selection={'selected_ids':['selected:0'],'overrides':{}}
        def catalog(**kw):return N(first=lambda:N(description=self.t.reference.tabular['codes'][kw['code']]))
        for suffix,allowed in [(text,False) for text in holds]+[(text,True) for text in allows[:4]]:
            run=self.t.run_value(notes=NOTES+'\n'+suffix);old=run.result
            with self.subTest(boundary=suffix),\
                 patch.object(corti_coding,'terminology',return_value=(self.t.terms,old['cpt'])),\
                 patch.object(engine,'reference_for',return_value=self.t.reference),\
                 patch.object(engine.Code.objects,'filter',side_effect=catalog):
                run.result=corti_coding.retained_result(run,corti_prediction.payload(run),
                    old['adapter']['diagnostics']['provider_response'],FIXTURE['runs'][0]['requests'][0]['response_sha256'])
                self.assertEqual(run.result['suggestions'][0]['eligible'],allowed)
                if allowed:self.assertEqual(corti_coding.validate_selection(run,selection),selection)
                else:
                    with self.assertRaises(ValidationError):corti_coding.validate_selection(run,selection)

    def test_source_or_reference_tampering_cannot_bypass_saved_eligibility(self):
        run=self.t.result();selection={'selected_ids':['selected:0'],'overrides':{}}
        def catalog(**kw):return N(first=lambda:N(description=self.t.reference.tabular['codes'][kw['code']]))
        with patch.object(corti_coding,'terminology',return_value=(self.t.terms,run.result['cpt'])),\
             patch.object(engine,'reference_for',return_value=self.t.reference),\
             patch.object(engine.Code.objects,'filter',side_effect=catalog):
            for suffix in (' She had a stroke.', ' The patient denies dysphagia.',
                           ' Her dysphagia began after a neurological event.',
                           ' Her swallowing symptoms started after an earlier neurological event.',
                           ' Her dysphagia arose as a consequence of a neurological event.',
                           ' Her dysphagia is attributable to a prior neurological event.',
                           ' All the above statements are false.'):
                run.inputs['notes']=NOTES+suffix
                with self.subTest(suffix=suffix),self.assertRaises(ValidationError):corti_coding.validate_selection(run,selection)
        reference=deepcopy(self.t.reference)
        reference.index=[r for r in reference.index if r['term']!='pharyngeal phase']
        reference.__dict__.pop('_index_lookup',None)
        with patch.object(self.t,'reference',reference),self.assertRaises(ValidationError):self.route('The patient reports esophageal dysphagia today.')

    def test_prior_service_relationship_is_owner_time_and_specialty_bound(self):
        for suffix,allowed in [('She saw Dr Voss last year.',False),('She saw Doctor Voss last year.',False),
            ('She saw dr. Voss last year.',False),('She saw the treating clinician last year.',False),
            ('She saw Dr. Voss five years ago.',True),('She saw Dr. Voss in 2019.',True),
            ('Her mother saw Dr. Voss last year.',True),
            ('She received professional services from a dermatologist of a different specialty and subspecialty in this same group practice last month.',True)]:
            with self.subTest(suffix=suffix):
                if allowed:self.assertEqual(self.t.boundary(NOTES+'\n'+suffix)['selection']['code'],'99204')
                else:
                    with self.assertRaises(ValidationError):self.t.boundary(NOTES+'\n'+suffix)

    def test_coordinated_predicates_and_whole_account_invalidations_are_not_findings(self):
        for verb in ('retracts','withdraws','corrects','questions'):
            text='The patient reports heartburn and '+verb+' that statement.'
            with self.subTest(verb=verb):self.assertIsNone(self.t.route('Patient: Synthetic Uma Bell\n'+text,text))
        for text in ('All the above statements are false.','The above clinical account is unverified.'):
            with self.subTest(text=text),self.assertRaises(ValidationError):self.t.boundary(NOTES+'\n'+text)


@skipUnless(connection.vendor=='postgresql','Actual PostgreSQL scalar projection required.')
class NECProjectionPostgresTests(TestCase):
    def setUp(self):
        self.full=deepcopy(FIXTURE['reference'])

    def create_reference(self,provenance):
        release=CodeSet.objects.create(system='ICD-10-CM',version='FY2027',
            effective_from=date(2026,10,1),effective_until=date(2027,9,30),
            source_url=self.full['release']['source_url'],sha256=self.full['release']['sha256'])
        row=CodingRelease.objects.create(release=release,index=self.full['index'],tabular=self.full['tabular'],
            provenance=provenance,digest=reference_digest(self.full))
        return CodingRelease.objects.only('release_id','digest').select_related('release').get(pk=row.pk)

    def test_actual_sql_projects_only_the_scalar_for_prediction_and_selection(self):
        provenance=deepcopy(self.full['provenance']);provenance['unrelated_padding']='x'*(1024*1024)
        metadata=self.create_reference(provenance)
        run=retained_case().result();selection={'selected_ids':['selected:0','selected:1'],'overrides':{}}
        with CaptureQueriesContext(connection) as captured:
            prediction=store.prediction_reference(metadata,['R13.19','R12'],source_contract=engine.CURRENT_SOURCE_CONTRACT)
            approval=store.selection_reference(metadata,run,selection)
        for reference in (prediction,approval):
            self.assertEqual(reference.guidelines_sha256,nec.GUIDELINES_SHA256)
            self.assertTrue(nec._guideline_bound(reference))
            self.assertNotIn('provenance',vars(reference))
            self.assertLess(reference.projection_bytes,100000)
            candidate=run.result['candidates']['selected:0'][0]
            proof=nec.prove(reference,engine.index_lookup(reference)[candidate['entry_id']],
                run.result['suggestions'][0]['concept'],NOTES,source_contract=engine.CURRENT_SOURCE_CONTRACT)
            self.assertEqual(proof[1],candidate['clinical_specificity'])
        self.assertTrue({'index','tabular','provenance'} <= metadata.get_deferred_fields())
        self.assertTrue(all('octet_length(payload::text)' in row['sql'] for row in captured))
        self.assertEqual(sum("provenance #>> '{manifest,files,guidelines,sha256}'" in row['sql'] for row in captured),2)

    def check_unbound_scalar(self,digest):
        provenance={'manifest':{'files':{'guidelines':{'sha256':digest}}}}
        metadata=self.create_reference(provenance)
        reference=store.prediction_reference(metadata,['R13.19','R12'],source_contract=engine.CURRENT_SOURCE_CONTRACT)
        self.assertEqual(reference.guidelines_sha256,digest)
        self.assertFalse(nec._guideline_bound(reference))

    def test_actual_sql_missing_scalar_is_unbound(self):self.check_unbound_scalar(None)

    def test_actual_sql_wrong_scalar_is_unbound(self):self.check_unbound_scalar('0'*64)
