"""Constructed answer controls, never edits to retained provider responses."""
from copy import deepcopy
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.tests.test_semantic_generation import fact, assignments
from documents.semantic_preparation_roles import default_definitions


class SoapCompositeAnswerTests(SimpleTestCase):
    header = 'Patient: Synthetic Ada Tern\nService date: 21 October 2027\nTreating clinician: Dr. Mira Cole\n'

    def assign(self,label,body,quotes,*,mode='narrative',measurements=False):
        notes=self.header+body
        fields=[{'key':'answer','label':label,'kind':'text','locator':{'cell':0}}]
        definitions=default_definitions(fields)
        definitions['answer'].update(version=2,answer_mode=mode)
        units,_=generation.source_units(notes,fields)
        raw=[fact(notes,fields,str(i),quote,kind='measurement' if measurements else 'finding',
            name_quote='Synthetic Ada Tern') for i,quote in enumerate(quotes)]
        for value in raw:
            named=value['subject']['name_span']
            value['source_unit_ids'].append(next(u['id'] for u in units if u['start']<=named['start']<named['end']<=u['end']))
            value['source_unit_ids']=sorted(set(value['source_unit_ids']))
        original=deepcopy(raw)
        validated=semantic.validate_facts(notes,units,{'facts':raw},scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        answers=semantic._assign(notes,fields,definitions,validated,assignments(fields,{'answer':[f['id'] for f in raw]}),
            scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        self.assertEqual(raw,original)
        return answers['answer']

    def test_narrative_vitals_keep_labels_and_units(self):
        quotes=['Blood pressure 112/70 mmHg','pulse 74 beats per minute',
                'temperature 36.8 degrees Celsius','weight 71.2 kg']
        result=self.assign('Blood pressure, pulse, temperature and weight with units',
            'O\n'+', '.join(quotes)+'.',quotes)
        self.assertEqual(result['status'],'supported',result['review_reasons'])
        self.assertEqual(result['text'],'Blood pressure 112/70 mmHg; Pulse 74 beats per minute; '
            'Temperature 36.8 degrees Celsius; Weight 71.2 kg')
        for mode in ('atomic','narrative'):
            invalid=self.assign('Blood pressure, pulse, temperature and weight with units',
                'O\n'+', '.join(quotes)+'.',['112/70','74','36.8','71.2'],mode=mode,measurements=True)
            self.assertEqual(invalid['text'],'')
            self.assertIn(invalid['status'],('ambiguous','conflict'))

    def test_atomic_guard_remains_and_reviewed_narrative_can_combine_identity(self):
        quotes=['Synthetic Ada Tern','REF-728']
        body='Record number: REF-728\nS\nShe reports discomfort.'
        for mode in ('atomic','narrative'):
            result=self.assign('Patient full name and record number',body,quotes,mode=mode)
            if mode=='atomic':
                self.assertEqual(result['text'],'')
                self.assertIn(result['status'],('conflict','ambiguous'))
            else:
                self.assertEqual(result['status'],'supported',result['review_reasons'])
                self.assertEqual(result['text'],'Synthetic Ada Tern; REF-728')

    def test_each_semicolon_qualification_remains_a_completeness_obligation(self):
        negative='The cause of tingling is not established'
        uncertain='nerve compression is a possibility but is not diagnosed'
        notes=self.header+'A\n'+negative+'; '+uncertain+'.'
        fields=[{'key':'answer','label':'Complete assessment and all diagnostic qualifications','kind':'text','locator':{'cell':0}}]
        definitions=default_definitions(fields)
        definitions['answer'].update(version=2,answer_mode='narrative')
        rows=semantic._clinical_context_inventory(notes,definitions,scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        self.assertEqual([(r['source']['quote'],r['polarities']) for r in rows],
            [(negative,['negated']),(uncertain,['uncertain'])])
        units,_=generation.source_units(notes,fields)
        values=[fact(notes,fields,'limit',negative,kind='assessment',polarity='negated'),
            fact(notes,fields,'possible',uncertain,kind='assessment',polarity='uncertain')]
        validated=semantic.validate_facts(notes,units,{'facts':values},scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        for picked in (['limit'],['possible'],['limit','possible']):
            result=semantic._assign(notes,fields,definitions,validated,assignments(fields,{'answer':picked}),
                scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)['answer']
            if len(picked)==2:self.assertEqual(result['status'],'supported',result['review_reasons'])
            else:self.assertIn(result['status'],('conflict','ambiguous'))
