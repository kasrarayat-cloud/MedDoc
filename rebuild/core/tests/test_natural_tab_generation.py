"""Synthetic natural-source contract checks; no model/provider requests."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from core import generation as g
from documents.engine import docx_inspect

ORIGINAL=Path(__file__).resolve().parents[2]/'documents/__fixtures__/Colonoscopy_Operative_Template.docx'
NOTES=('Fictional software test only. Patient name: Sample Colonoscopy. Date of birth: January 2, 1980. '
       'Patient ID: SYN-COLON-AI-20260921. Procedure date: September 21, 2026. Endoscopist: Dr Synthetic Example. '
       'Procedure: diagnostic colonoscopy. Anesthesia: monitored anesthesia care. Bowel preparation score: BBPS eight. '
       'The scope was advanced to the cecum. Indication: rectal bleeding. '
       'Findings: sigmoid diverticulosis and small internal hemorrhoids. No polyps were seen. '
       'No specimens were collected. Estimated blood loss was zero millilitres; correction, less than one millilitre. '
       'There were no immediate complications. Recommendation: follow up with the referring clinician in two weeks.')
EXPECTED={
    'PATIENT NAME':'Patient name: Sample Colonoscopy.',
    'PATIENT DOB':'Date of birth: January 2, 1980.',
    'PATIENT ID #':'Patient ID: SYN-COLON-AI-20260921.',
    'DATE OF PROCEDURE':'Procedure date: September 21, 2026.',
    'SURGEON / ENDOSCOPIST':'Endoscopist: Dr Synthetic Example.',
    'PROCEDURE':'Procedure: diagnostic colonoscopy.',
    'ANESTHESIA':'Anesthesia: monitored anesthesia care.',
    'BOWEL PREPARATION / BBPS':'Bowel preparation score: BBPS eight.',
    'EXTENT OF EXAMINATION':'The scope was advanced to the cecum.',
    'PREOPERATIVE DIAGNOSIS / INDICATION':'Indication: rectal bleeding.',
    'POSTOPERATIVE FINDINGS — 1':'Findings: sigmoid diverticulosis and small internal hemorrhoids.',
    'POSTOPERATIVE FINDINGS — 2':'No polyps were seen.',
    'DESCRIPTION OF PROCEDURE':'The scope was advanced to the cecum.',
    'SPECIMENS':'No specimens were collected.',
    'ESTIMATED BLOOD LOSS':'Estimated blood loss was zero millilitres; correction, less than one millilitre.',
    'COMPLICATIONS':'There were no immediate complications.',
    'RECOMMENDATIONS — 1':'Recommendation: follow up with the referring clinician in two weeks.',
}

class NaturalTabGenerationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields=docx_inspect(ORIGINAL)[3]

    def selected(self,notes,by_label,*,conflicts=()):
        selections=g.Selections(fields=[g.Selection(key=f['key'],quotes=by_label.get(f['label'],[]),
            conflict=f['label'] in conflicts) for f in self.fields])
        result=g.validate_selections(notes,self.fields,selections)
        return {f['label']:result[f['key']] for f in self.fields}

    def test_exact_owner_map_complete_fact_units_and_corrected_value(self):
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
                         '8ae1e2b0ebeec317c038b8bfeed6a0824055f44d689c039ab450404593f2815a')
        self.assertEqual(len(self.fields),24)
        self.assertEqual(sum(len(f['locator']['tab_form']['anchors']) for f in self.fields),28)
        answers=self.selected(NOTES,{label:[quote] for label,quote in EXPECTED.items()})
        self.assertEqual(sum(a['status']=='supported' for a in answers.values()),17)
        self.assertEqual(sum(a['status']=='missing' for a in answers.values()),7)
        self.assertEqual(answers['ESTIMATED BLOOD LOSS']['text'],'less than one millilitre.')
        self.assertEqual(answers['COMPLICATIONS']['text'],'There were no immediate complications.')
        self.assertEqual(answers['POSTOPERATIVE FINDINGS — 1']['text'],EXPECTED['POSTOPERATIVE FINDINGS — 1'])
        self.assertEqual(answers['POSTOPERATIVE FINDINGS — 2']['text'],'No polyps were seen.')
        self.assertEqual(answers['PATIENT NAME']['text'],'Sample Colonoscopy.')
        self.assertEqual(answers['PROCEDURE']['text'],'diagnostic colonoscopy.')
        for label,answer in answers.items():
            self.assertFalse(answer['reviewed'])
            for span in answer['evidence']:
                self.assertEqual(NOTES[span['start']:span['end']],span['quote'])
                self.assertEqual(span['quote'],EXPECTED[label])
        for label in ('CONSENT','Electronically signed by','DD (dictated)','DT (transcribed)',
                      'POSTOPERATIVE FINDINGS — 3','RECOMMENDATIONS — 2','RECOMMENDATIONS — 3'):
            self.assertEqual((answers[label]['status'],answers[label]['text']),('missing',''))

    def test_old_whole_paragraph_and_word_fragments_are_no_longer_offered(self):
        for quote in (NOTES,'polyps','one millilitre.','small internal hemorrhoids.'):
            with self.subTest(quote=quote),self.assertRaises(ValidationError):
                self.selected(NOTES,{'POSTOPERATIVE FINDINGS — 1':[quote]})

    def test_sentence_boundaries_keep_abbreviations_decimals_semicolons_and_unicode_offsets(self):
        notes='  Name: Dr. Synthetic Example. Measurement was 1.5 mm; no change.\r\n  No fever; cough cannot be excluded. '
        units,inherited=g.source_units(notes,self.fields)
        self.assertFalse(inherited)
        self.assertEqual([u['quote'] for u in units],['Name: Dr. Synthetic Example.',
            'Measurement was 1.5 mm; no change.','No fever; cough cannot be excluded.'])
        for unit in units:self.assertEqual(notes[unit['start']:unit['end']],unit['quote'])
        unicode='  🩺 Patient name: Sample Colonoscopy. No polyps were seen.'
        for unit in g.source_units(unicode,self.fields)[0]:
            self.assertEqual(unicode[unit['start']:unit['end']],unit['quote'])

    def test_complete_multiline_narrative_is_supported_but_inherited_heading_is_not(self):
        notes='The scope was advanced to the cecum.\nThere were no immediate complications.'
        answer=self.selected(notes,{'COMPLICATIONS':[notes.splitlines()[1]]})['COMPLICATIONS']
        self.assertEqual(answer['status'],'supported')
        for prefix in ('The following findings are denied:\n','Family history:\n','Findings not present. The following are absent.\n'):
            notes=prefix+'Diabetes.'
            answer=self.selected(notes,{'POSTOPERATIVE FINDINGS — 1':['Diabetes.']})['POSTOPERATIVE FINDINGS — 1']
            self.assertEqual(answer['status'],'conflict')
            self.assertEqual(answer['evidence'],[{'quote':notes,'start':0,'end':len(notes)}])

    def test_true_repeated_label_conflict_cannot_be_hidden_by_provider(self):
        notes='Estimated blood loss: zero millilitres. Estimated blood loss: five millilitres.'
        answer=self.selected(notes,{'ESTIMATED BLOOD LOSS':['Estimated blood loss: five millilitres.']})['ESTIMATED BLOOD LOSS']
        self.assertEqual((answer['status'],answer['text']),('conflict',''))
        self.assertEqual(len(answer['evidence']),2)

    def test_exact_labels_cannot_be_borrowed_by_another_field(self):
        with self.assertRaises(ValidationError):
            self.selected('Anesthesia: monitored anesthesia care.',{'PROCEDURE':['Anesthesia: monitored anesthesia care.']})

    def test_correction_is_not_a_license_to_use_a_lone_substring(self):
        quote=EXPECTED['ESTIMATED BLOOD LOSS']
        self.assertEqual(self.selected(quote,{'ESTIMATED BLOOD LOSS':[quote]})['ESTIMATED BLOOD LOSS']['text'],
                         'less than one millilitre.')
        with self.assertRaises(ValidationError):
            self.selected(quote,{'ESTIMATED BLOOD LOSS':['less than one millilitre.']})

    def test_source_date_or_name_cannot_supply_attestation_or_unmentioned_dates_and_consent(self):
        notes='Procedure date: September 21, 2026. Endoscopist: Dr Synthetic Example.'
        answer=self.selected(notes,{'DD (dictated)':['Procedure date: September 21, 2026.'],
             'DT (transcribed)':['Procedure date: September 21, 2026.'],
             'CONSENT':['Endoscopist: Dr Synthetic Example.'],
             'Electronically signed by':['Endoscopist: Dr Synthetic Example.']})
        for label in ('DD (dictated)','DT (transcribed)','CONSENT'):
            self.assertEqual((answer[label]['status'],answer[label]['text']),('conflict',''))
        self.assertEqual((answer['Electronically signed by']['status'],answer['Electronically signed by']['text']),('missing',''))

    def test_one_statement_cannot_fill_two_numbered_slots(self):
        with self.assertRaises(ValidationError):
            self.selected('No polyps were seen.',{'POSTOPERATIVE FINDINGS — 1':['No polyps were seen.'],
                'POSTOPERATIVE FINDINGS — 2':['No polyps were seen.']})

    def test_evidence_id_contract_refuses_unknown_and_duplicate_units(self):
        for ids in ([0],[9999],[1,1]):
            with self.subTest(ids=ids),self.assertRaises(ValidationError):
                g.unit_selections(NOTES,self.fields,g.UnitSelections(fields=[
                    g.UnitSelection(key=self.fields[0]['key'],unit_ids=ids,conflict=False)]))

    def test_fixture_uses_complete_exact_label_units_and_does_not_pretend_to_map_narrative(self):
        notes='PATIENT NAME: Synthetic Example\nANESTHESIA: Documented synthetic value'
        result=g.validate_selections(notes,self.fields,g.fixture(notes,self.fields))
        self.assertEqual(result[self.fields[0]['key']]['text'],'Synthetic Example')
        self.assertEqual(sum(a['status']=='supported' for a in result.values()),2)

    @override_settings(AI_MODE='live',AI_PROVIDER='anthropic',AI_MODEL='claude-sonnet-4-6',
        AI_INPUT_RATE='1',AI_OUTPUT_RATE='5',AI_CACHED_RATE='0.1')
    def test_provider_adapter_sends_bounded_units_and_retains_raw_id_selection_for_validation(self):
        units,_=g.source_units(NOTES,self.fields)
        by_quote={u['quote']:u['id'] for u in units}
        selected={'fields':[{'key':f['key'],'unit_ids':[by_quote[EXPECTED[f['label']]]] if f['label'] in EXPECTED else [],
                            'conflict':False} for f in self.fields]}
        response=SimpleNamespace(usage=SimpleNamespace(input_tokens=1,output_tokens=1),stop_reason='end_turn',
            content=[SimpleNamespace(type='text',text=json.dumps(selected))],_request_id='synthetic-mock-only')
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value=response
            raw,*_=g.generate(NOTES,self.fields)
            sent=client.return_value.messages.create.call_args.kwargs
        self.assertEqual(json.loads(sent['messages'][0]['content'])['source_units'],units)
        self.assertIn('UnitSelection',sent['output_config']['format']['schema']['$defs'])
        self.assertEqual(raw['evidence_contract'],g.TAB_CONTRACT)
        self.assertEqual(raw['anthropic_response'],response)
        result=g.validated(raw)
        self.assertEqual(sum(a['status']=='supported' for a in result.values()),17)
        self.assertEqual(result[next(f['key'] for f in self.fields if f['label']=='ESTIMATED BLOOD LOSS')]['text'],
                         'less than one millilitre.')

    def test_ambiguous_correction_cannot_remove_negation_or_change_quantity_units(self):
        for quote in ('Symptoms: patient denies pain; correction, fever.',
                      'Estimated blood loss was zero millilitres; correction, one kilogram.',
                      'Estimated blood loss was not zero millilitres; correction, one millilitre.'):
            answer=self.selected(quote,{'ESTIMATED BLOOD LOSS':[quote]})['ESTIMATED BLOOD LOSS']
            self.assertEqual((answer['status'],answer['text']),('conflict',''))
            self.assertEqual(answer['evidence'][0]['quote'],quote)

    def test_reviewed_consent_display_label_retains_documentation_guard(self):
        fields=[{**f,'label':'CONSENT DOCUMENTATION'} if f['label']=='CONSENT' else f for f in self.fields]
        quote='Procedure date: September 21, 2026.'
        selected=g.Selections(fields=[g.Selection(key=f['key'],quotes=[quote] if f['label']=='CONSENT DOCUMENTATION' else [],
            conflict=False) for f in fields])
        result=g.validate_selections(quote,fields,selected)
        key=next(f['key'] for f in fields if f['label']=='CONSENT DOCUMENTATION')
        self.assertEqual((result[key]['status'],result[key]['text']),('conflict',''))

    @override_settings(AI_MODE='live',AI_PROVIDER='anthropic',AI_MODEL='claude-sonnet-4-6',
        AI_INPUT_RATE='1',AI_OUTPUT_RATE='5',AI_CACHED_RATE='0.1')
    def test_queued_legacy_prompt_and_receipt_keep_original_quotation_contract(self):
        config=g.configuration(); config['prompt_version']='extractive-v3-reviewed-context-labels'
        notes='PATIENT NAME: Synthetic Example'
        selected={'fields':[{'key':f['key'],'quotes':['Synthetic Example'] if f['label']=='PATIENT NAME' else [],
                            'conflict':False} for f in self.fields]}
        response=SimpleNamespace(usage=SimpleNamespace(input_tokens=1,output_tokens=1),stop_reason='end_turn',
            content=[SimpleNamespace(type='text',text=json.dumps(selected))],_request_id='synthetic-legacy-mock-only')
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value=response
            raw,*_=g.generate(notes,self.fields,config)
            sent=client.return_value.messages.create.call_args.kwargs
        self.assertNotIn('source_units',json.loads(sent['messages'][0]['content']))
        self.assertIn('Selection',sent['output_config']['format']['schema']['$defs'])
        self.assertEqual(raw['evidence_contract'],'legacy')
        self.assertEqual(g.validated(raw)[self.fields[0]['key']]['text'],'Synthetic Example')
        del raw['evidence_contract']
        self.assertEqual(g.validated(raw)[self.fields[0]['key']]['text'],'Synthetic Example')
        config['mode']='fixture'
        fixture,*_=g.generate(notes,self.fields,config)
        self.assertEqual(fixture[self.fields[0]['key']]['text'],'Synthetic Example')

    def test_refutation_unlabelled_subject_conflict_keeps_both_claims(self):
        notes='Estimated blood loss was zero millilitres. Estimated blood loss was five millilitres.'
        answer=self.selected(notes,{'ESTIMATED BLOOD LOSS':['Estimated blood loss was five millilitres.']})['ESTIMATED BLOOD LOSS']
        self.assertEqual((answer['status'],answer['text']),('conflict',''))
        self.assertEqual([item['quote'] for item in answer['evidence']],
                         ['Estimated blood loss was zero millilitres.','Estimated blood loss was five millilitres.'])

    def test_refutation_scope_cannot_drop_denial_or_quoted_hypothesis(self):
        cases=[('The patient denied these symptoms: fever. Rectal bleeding.','Rectal bleeding.'),
               ('The patient asks: "What if I had cancer. Bleeding. Would that require surgery?"','Bleeding.'),
               ('Absent symptoms: fever. Rectal bleeding.','Rectal bleeding.'),
               ('Suppose bleeding were present. Bleeding was observed.','Bleeding was observed.'),
               ('Family history: polyps. Polyps were observed.','Polyps were observed.')]
        for notes,quote in cases:
            with self.subTest(notes=notes):
                answer=self.selected(notes,{'POSTOPERATIVE FINDINGS — 1':[quote]})['POSTOPERATIVE FINDINGS — 1']
                self.assertEqual((answer['status'],answer['text']),('conflict',''))
                self.assertEqual(answer['evidence'],[{'quote':notes,'start':0,'end':len(notes)}])

    def test_unlabelled_fragment_is_review_required_not_a_complete_finding(self):
        answer=self.selected('Rectal bleeding.',{'POSTOPERATIVE FINDINGS — 1':['Rectal bleeding.']})['POSTOPERATIVE FINDINGS — 1']
        self.assertEqual((answer['status'],answer['text']),('conflict',''))

    def test_selected_id_binds_the_selected_occurrence_even_when_quote_repeats(self):
        notes='No polyps were seen. No polyps were seen.'
        fields=[self.fields[10]]
        selections=g.unit_selections(notes,fields,g.UnitSelections(fields=[
            g.UnitSelection(key=fields[0]['key'],unit_ids=[1],conflict=False)]))
        answer=g.validate_selections(notes,fields,selections)[fields[0]['key']]
        self.assertEqual(answer['evidence'],[{'quote':'No polyps were seen.','start':0,'end':20}])
