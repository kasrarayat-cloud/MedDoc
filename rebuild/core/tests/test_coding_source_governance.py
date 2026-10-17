"""Prospective source grammar over retained synthetic output; no provider calls.

The three historical runs retain their exact results. Changed-source controls
are explicit offline inputs, never substituted clinical answers or new receipts.
Other-specified routes require separate authoritative clinical subtype proof.
"""
import base64
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
import zlib

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_engine as engine, corti_coding, corti_semantics as semantics
from core import coding_output, coding_output_reference, corti_prediction
from core.corti_response import CatalogRelease, DatedTerminology
from core.tests.test_coding_output_live import bind_request


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/tessa_coding_retained.json').read_text())
ANSWER_BYTES = zlib.decompress(base64.b64decode(FIXTURE['retained_answers']['json']))
assert hashlib.sha256(ANSWER_BYTES).hexdigest() == FIXTURE['retained_answers']['sha256']
INPUTS = {**FIXTURE['shared_inputs'], 'answers': json.loads(ANSWER_BYTES)}
NOTES = FIXTURE['notes']
CONTRACT = 'source-bound-clinical-coding-v4'


class SourceGovernanceCodingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raw = deepcopy(FIXTURE['reference']); raw['release'] = N(**raw['release'])
        cls.reference = N(**raw)
        release = cls.reference.release
        unavailable = FIXTURE['runs'][0]['result']['suggestions'][2]['terminology']['reason']
        cls.terms = DatedTerminology([CatalogRelease('icd10cm-outpatient', release.version,
            date(2026,10,1), date(2027,9,30), release.source_url, release.sha256,
            cls.reference.tabular['codes'], release.source_url)], unavailable_reasons={'cpt': unavailable})

    def run_value(self, index=2, *, contract=CONTRACT, notes=NOTES):
        run = N(**deepcopy(FIXTURE['runs'][index]))
        run.inputs = deepcopy(INPUTS); run.inputs['notes'] = notes
        run.config['clinical_source_contract'] = contract
        run.pk = run.id
        return run

    def result(self, index=2, *, contract=CONTRACT):
        run = self.run_value(index, contract=contract)
        saved = FIXTURE['runs'][index]['result']
        with patch.object(corti_coding, 'terminology', return_value=(self.terms, saved['cpt'])), \
             patch.object(engine, 'reference_for', return_value=self.reference):
            run.result = corti_coding.retained_result(run, saved['provider_request'],
                saved['adapter']['diagnostics']['provider_response'],
                FIXTURE['runs'][0]['requests'][0]['response_sha256'])
        return run

    def route(self, notes, quote, code='R12'):
        start = notes.index(quote)
        proposal = {'id':'selected:0', 'code':code,
            'terminology':{'description':self.reference.tabular['codes'][code]},
            'evidence':[{'text':quote,'start':start,'end':start+len(quote),'status':'valid','context_index':0}]}
        return corti_coding._icd_source(self.run_value(notes=notes), self.reference, proposal, [code])[1]

    def boundary(self, notes=NOTES, *, context=None):
        """Explicit offline receipt rebinding tests the actual live boundary.

        Original selected response is retained; no altered-source control is
        represented as a real provider call, saved decision or live approval.
        """
        run = self.run_value(0, notes=notes)
        run.context = deepcopy(context or FIXTURE['context'])
        run.result['global_blockers'] = []
        run.input_digest = corti_prediction.receipts.digest({'inputs':run.inputs,
            'context':run.context, 'releases':run.releases})
        bind_request(run)
        encounter = N(pk=run.encounter_id, patient_id=INPUTS['patient_id'], notes=notes,
            status='finalized', service_date=date(2026,10,17))
        bundle = json.loads((Path(__file__).parents[2] / 'ops/fixtures/corti_office_time_output_reference.json').read_text())
        with patch.object(coding_output_reference, 'load', return_value=(bundle,[str(run.user_id)])):
            return coding_output.live_assessment(encounter, run)

    def test_retained_v3_full_results_and_raw_output_stay_exact(self):
        self.assertEqual(hashlib.sha256(NOTES.encode()).hexdigest(), FIXTURE['provenance']['notes_sha256'])
        for index, old in enumerate(FIXTURE['runs']):
            with self.subTest(run=old['id']):
                result = self.result(index, contract=engine.ASSERTION_SOURCE_CONTRACT).result
                self.assertEqual(result, {k:v for k,v in old['result'].items() if k!='retained_prediction'})
                self.assertEqual(result['adapter']['diagnostics']['provider_response'],
                                 old['result']['adapter']['diagnostics']['provider_response'])

    def test_retained_v4_current_symptoms_have_independent_authoritative_routes(self):
        run = self.result()
        self.assertEqual([(z['code'],z['eligible']) for z in run.result['suggestions']],
                         [('R13.19',True),('R12',True),('99204',False)])
        self.assertEqual(set(run.result['candidates']), {'selected:0','selected:1'})
        self.assertIn('clinical_specificity',run.result['candidates']['selected:0'][0])
        self.assertEqual(run.result['suggestions'][1]['index_path'], ['Heartburn'])
        self.assertEqual(run.result['suggestions'][2]['description'], '')
        self.assertEqual(run.result['adapter']['diagnostics']['provider_response'],
                         FIXTURE['runs'][2]['result']['adapter']['diagnostics']['provider_response'])

    def test_unfamiliar_coordinated_reports_keep_independent_duration(self):
        for quote in ('The patient reports nausea for six weeks and heartburn for four months.',
                      'She experiences heartburn today and nausea after meals.',
                      'The patient describes intermittent heartburn for five days and nausea today.'):
            notes='Patient: Synthetic Tessa Calder\nHistory of present illness\n'+quote
            with self.subTest(quote=quote):self.assertIsNotNone(self.route(notes,quote))

    def test_nonassertions_qualifications_and_foreign_ownership_remain_held(self):
        for quote in ('The patient asks whether she has nausea and heartburn.',
                      'The patient reports possible heartburn for four months and nausea today.',
                      'The patient reports heartburn according to an unverified report and nausea today.',
                      'The patient reports heartburn for four months and it is now denied.',
                      'The patient reports heartburn for four months, which was recorded in error.',
                      'The patient denies heartburn and nausea.',
                      'The patient reports a risk of heartburn and nausea.',
                      'The patient reports heartburn for four months in a hypothetical example.'):
            notes='Patient: Synthetic Tessa Calder\nHistory of present illness\n'+quote
            with self.subTest(quote=quote):self.assertIsNone(self.route(notes,quote))
        quote='The patient reports heartburn for four months and nausea today.'
        for heading in ('Mother:', 'Previous encounter:', 'Example:'):
            notes='Patient: Synthetic Tessa Calder\n'+heading+'\n'+quote
            with self.subTest(heading=heading):self.assertIsNone(self.route(notes,quote))

    def test_nec_is_not_licensed_by_an_adjective_or_unrelated_anatomy(self):
        for qualifier in ('renal','nasal','severe','mild','persistent','stable','left',
                          'possible esophageal','corrected esophageal','pharyngeal and esophageal'):
            quote='The patient reports '+qualifier+' dysphagia today.'
            notes='Patient: Synthetic Tessa Calder\nHistory of present illness\n'+quote
            with self.subTest(qualifier=qualifier):self.assertIsNone(self.route(notes,quote,'R13.19'))

    def test_unknown_existence_owner_or_time_modifiers_cannot_affirm_a_condition(self):
        for modifier in ('potential','conjectured','unconfirmed','questionable','historical','unlikely',
                         'unsubstantiated','familial','invented','unvalidated','future','prior','ruled-out'):
            quote='The patient reports '+modifier+' heartburn for four months and nausea today.'
            notes='Patient: Synthetic Tessa Calder\nHistory of present illness\n'+quote
            with self.subTest(modifier=modifier):self.assertIsNone(self.route(notes,quote))

    def test_approval_and_export_reapply_current_source_with_no_override(self):
        run=self.result(); selection={'selected_ids':['selected:1'],'overrides':{}}
        def catalog(**kw):return N(first=lambda:N(description=self.reference.tabular['codes'][kw['code']]))
        with patch.object(corti_coding,'terminology',return_value=(self.terms,run.result['cpt'])), \
             patch.object(engine,'reference_for',return_value=self.reference), \
             patch.object(engine.Code.objects,'filter',side_effect=catalog):
            self.assertEqual(corti_coding.validate_selection(run,selection),selection)
            for key in ('selected:2','candidate:0'):
                with self.subTest(key=key),self.assertRaises(ValidationError):
                    corti_coding.validate_selection(run,{'selected_ids':[key],'overrides':{}})
            for suffix in ('The patient denies heartburn today.',
                           'Heartburn was recorded in error after checking the chart.',
                           'The reported heartburn concerns another patient.'):
                run.inputs['notes']=NOTES+'\r\n'+suffix
                with self.subTest(suffix=suffix),self.assertRaises(ValidationError):
                    corti_coding.validate_selection(run,selection)

    def test_47_total_and_all_exclusions_support_existing_new_patient_99204_boundary(self):
        support=semantics.office_time_facts(NOTES,contract=CONTRACT)
        self.assertEqual(support['status'],'documented'); self.assertEqual(len(support['facts']),8)
        self.assertEqual({z['key']:z['value'] for z in support['facts']},
            {'setting':'outpatient_office','patient_status':'new','time_minutes':47,'time_same_day':True,
             'time_qualified_clinician':True,'time_excludes_staff':True,
             'time_excludes_separately_reported':True,'em_basis':'time'})
        self.assertTrue(all(NOTES[z['start']:z['end']]==z['quote'] for z in support['facts']))
        self.assertEqual(semantics.office_service_eligibility(NOTES,date(2026,10,17),contract=CONTRACT),[])
        assessment=self.boundary()
        self.assertEqual(assessment['selection']['code'],'99204')
        self.assertEqual(assessment['selection']['minimum_minutes'],45)
        self.assertEqual(assessment['selection']['maximum_minutes'],59)
        self.assertEqual(assessment['description_status'],'withheld_unverified_provider_text')
        self.assertEqual(assessment['permission']['scope'],'internal_fictional_review')
        self.assertEqual(assessment['provider_citation_adequacy']['status'],'insufficient_for_time_review')

    def test_calendar_date_and_same_day_arithmetic_do_not_accept_other_service_or_actor(self):
        for old,new in [('47 minutes on 17 October 2026','47 minutes on 16 October 2026'),
                        ('seven minutes reviewing','eight minutes reviewing'),
                        ('Dr. Voss personally spent','Dr. Hale personally spent'),
                        ('seven minutes reviewing the available outside records','seven minutes performing upper endoscopy'),
                        ('These are all physician activities on the encounter date.','These are all nursing activities on the encounter date.'),
                        ('The 47 minutes exclude eight minutes of staff intake work','The 47 minutes include eight minutes of staff intake work')]:
            notes=NOTES.replace(old,new);self.assertNotEqual(notes,NOTES)
            with self.subTest(new=new),self.assertRaises(ValidationError):self.boundary(notes)

    def test_actual_output_boundary_refuses_service_contradictions_and_missing_exclusions(self):
        for suffix in ('The stated 47 minutes were for the appointment yesterday, not today.',
                       'Only nursing staff saw the patient today; the physician did not participate.',
                       'The visit was cancelled.',
                       'The time total is wrong.',
                       'The 47 minutes include time for separately reported services.'):
            with self.subTest(suffix=suffix),self.assertRaises(ValidationError):self.boundary(NOTES+'\r\n'+suffix)
        removed=NOTES.replace('The total also excludes any time for separately reported services.','')
        with self.assertRaises(ValidationError):self.boundary(removed)
        context=deepcopy(FIXTURE['context']);context['time_qualified_clinician']=False
        with self.assertRaises(ValidationError):self.boundary(context=context)

    def test_current_new_label_cannot_override_qualifying_prior_service_history(self):
        for replacement in ('she has received professional services',
                            'she has received some professional services',
                            'she has not received no professional services'):
            notes=NOTES.replace('she has received no professional services',replacement)
            with self.subTest(replacement=replacement),self.assertRaises(ValidationError):self.boundary(notes)
        for suffix in ('New-patient history: She was an established patient of Dr. Voss last year.',
                       'She saw Dr. Voss last year.',
                       'She received professional services from the same specialty in this same group last month.',
                       'She has received professional services from Dr. Voss during the preceding three years.'):
            with self.subTest(suffix=suffix),self.assertRaises(ValidationError):self.boundary(NOTES+'\r\n'+suffix)
        # The actual outside-practice history, its prior treatment and stopped
        # medication remain literal source content, without becoming current
        # same-practice care or negating her separately documented heartburn.
        self.assertEqual(self.boundary()['selection']['code'],'99204')

    def test_unfamiliar_complete_status_setting_and_calendar_spelling(self):
        for old,new in [('During the preceding three years, she has received no',
                         'Over the past 3 years, the patient has received no'),
                        ('Encounter: New-patient, in-person visit in a U.S. gastrointestinal office.',
                         'Encounter: New patient, in-person consultation in a US digestive office.'),
                        ('47 minutes on 17 October 2026','47 minutes on 2026-10-17'),
                        ('47 minutes on 17 October 2026','47 minutes on October 17, 2026')]:
            notes=NOTES.replace(old,new);context=deepcopy(FIXTURE['context'])
            context['time_evidence']=notes[notes.index('Office E/M selection'):]
            with self.subTest(new=new):
                self.assertEqual(semantics.office_time_facts(notes,contract=CONTRACT)['status'],'documented')
                self.assertEqual(semantics.office_service_eligibility(notes,date(2026,10,17),contract=CONTRACT),[])
                # Header rewrites invalidate original provider quotation bytes;
                # no replacement provider evidence is fabricated for them.
                if old.startswith('47 minutes'):
                    self.assertEqual(self.boundary(notes,context=context)['selection']['code'],'99204')

    def test_existing_dated_range_not_an_unbounded_47_minute_permission(self):
        for minutes,review_minutes,want in [(44,'four',False),(45,'five',True),(59,'nineteen',True),(60,'20',False)]:
            notes=NOTES.replace('47 minutes',str(minutes)+' minutes').replace('seven minutes reviewing',review_minutes+' minutes reviewing')
            context=deepcopy(FIXTURE['context']);context['time_minutes']=str(minutes)
            context['time_evidence']=notes[notes.index('Office E/M selection'):]
            with self.subTest(minutes=minutes):
                if want:self.assertEqual(self.boundary(notes,context=context)['selection']['code'],'99204')
                else:
                    with self.assertRaises(ValidationError):self.boundary(notes,context=context)

    def test_legacy_time_reader_is_unchanged(self):
        saved=FIXTURE['runs'][2]['result']['suggestions'][2]['semantic_support']['documented_time_facts']
        self.assertEqual(semantics.office_time_facts(NOTES,contract=engine.ASSERTION_SOURCE_CONTRACT),saved)
