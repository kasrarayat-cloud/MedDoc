"""Source-boundary counterexamples; no provider, live DB or clinical generation."""
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from core import coding_engine as engine
from core.coding_terminology import parse_reference


def concept(term, evidence, **changes):
    return {'id':'c1','term':term,'index_terms':[term],'evidence':evidence,
            'kind':'symptom','certainty':'confirmed','temporality':'current','subject':'patient',
            'relevant':True,'missing_detail':'','integral_to':'',**changes}


def run(notes, **inputs):
    return SimpleNamespace(inputs={'notes':notes,'answers':{},'service_date':'2026-10-14',
        'patient_identity':{'display_name':'Synthetic Test Patient'},**inputs},
        context={'setting':'outpatient_office','patient_status':'unknown','em_basis':'unknown'},releases=[])


@override_settings(SYNTHETIC_ONLY=True)
class CodingEngineSourceTests(SimpleTestCase):
    def test_clipped_uncertainty_cannot_become_confirmed_disease(self):
        c=concept('GERD','GERD',kind='diagnosis')
        for source in ['Possible GERD is being evaluated.','GERD is suspected.']:
            with self.subTest(source=source):
                self.assertNotEqual(engine.source_disposition(c,source)[0],'eligible')

    def test_clipped_negation_cannot_become_current_disease(self):
        c=concept('GERD','GERD',kind='diagnosis')
        for source in ['The patient denies GERD.','GERD is absent.']:
            with self.subTest(source=source):
                self.assertNotEqual(engine.source_disposition(c,source)[0],'eligible')

    def test_unrelated_negation_does_not_erase_supported_diagnosis(self):
        note='The patient has GERD without dysphagia.'
        self.assertEqual(engine.source_disposition(concept('GERD',note,kind='diagnosis'),note)[0],'eligible')
        note='No nausea, but current heartburn.'
        self.assertEqual(engine.source_disposition(concept('heartburn','current heartburn'),note)[0],'eligible')

    def test_family_subject_cannot_be_removed_by_clipping(self):
        c=concept('colon polyps','colon polyps',kind='diagnosis')
        self.assertNotEqual(engine.source_disposition(c,"The patient's mother had colon polyps.")[0],'eligible')
        c=concept('colon polyps','colon polyps',kind='family_history',subject='family')
        self.assertNotEqual(engine.source_disposition(c,'The patient has colon polyps.')[0],'eligible')

    def test_positive_family_history_remains_eligible(self):
        note="The patient's mother had colon polyps at age 63."
        c=concept('colon polyps',note,kind='family_history',subject='family',temporality='historical')
        self.assertEqual(engine.source_disposition(c,note)[0],'eligible')
        self.assertTrue(engine.specificity_errors(c,'Z83.710','Family history of adenomatous and serrated polyps'))

    def test_documented_histology_cannot_be_guessed_or_downgraded(self):
        c=concept('colon polyps','Mother had adenomatous colon polyps.',kind='family_history',subject='family')
        self.assertTrue(engine.specificity_errors(c,'Z83.719','Family history of colon polyps, unspecified'))
        c['evidence']='Mother had non-adenomatous colon polyps.'
        self.assertTrue(engine.specificity_errors(c,'Z83.710','Family history of adenomatous and serrated polyps'))

    def test_contradictory_mentions_are_held(self):
        note='The patient reports heartburn. The patient denies heartburn.'
        self.assertEqual(engine.source_disposition(concept('heartburn','The patient reports heartburn.'),note)[0],'question')

    def test_plans_and_history_never_become_performed_procedures(self):
        for note,timing in [('Colonoscopy is planned for next month.','planned'),('Appendectomy was performed in 2008.','historical')]:
            c=concept(note.split()[0],note,kind='procedure',temporality=timing)
            self.assertEqual(engine.source_disposition(c,note)[0],'excluded')
        c=concept('colonoscopy','colonoscopy',kind='procedure')
        self.assertNotEqual(engine.source_disposition(c,'We plan colonoscopy next month.')[0],'eligible')

    def test_laterality_cannot_be_guessed_or_discarded(self):
        c=concept('wrist pain','The patient has left wrist pain.')
        self.assertTrue(engine.specificity_errors(c,'M25.531','Pain in right wrist'))
        self.assertTrue(engine.specificity_errors(c,'M25.539','Pain in unspecified wrist'))
        self.assertFalse(engine.specificity_errors(c,'M25.532','Pain in left wrist'))

    def test_identity_answers_do_not_depend_on_extractor(self):
        item=run('Synthetic Other Patient feels well.',patient_name_answers=[{'key':'name','label':'Patient name','text':'Synthetic Other Patient'}])
        result={'documented_patient_name':'','patient_name_evidence':''}
        self.assertTrue(engine.identity_blockers(item,result))
        item.context['identity_review_reason']='Owner confirms intentional reuse of this synthetic source.'
        self.assertEqual(engine.identity_blockers(item,result),[])
        with override_settings(SYNTHETIC_ONLY=False): self.assertTrue(engine.identity_blockers(item,result))

    def test_source_quote_is_exact_and_offsets_are_retained(self):
        self.assertEqual(engine.evidence_span('A. A.','A.')['occurrences'],[0,3])
        with self.assertRaises(ValidationError): engine.evidence_span('Heartburn.','heartburn')

    def test_unknown_setting_sends_nothing(self):
        item=run('Heartburn.');item.context['setting']='unknown'
        ref=SimpleNamespace(release=SimpleNamespace(version='FY2027'))
        with patch.object(engine,'reference_for',return_value=ref),patch.object(engine.coding_provider,'execute') as send:
            result=engine.generate(item)
        send.assert_not_called();self.assertTrue(result['global_blockers'])

    def test_mandatory_redirect_and_arbitrary_sibling_not_selectable(self):
        ref=SimpleNamespace(tabular={'codes':{'Z83.719':'Family history of colon polyps, unspecified','Z83.710':'Family history of adenomatous and serrated polyps'}})
        self.assertEqual(engine.code_variants(ref,{'code':'Z83.719','requires_review':True}),[])
        self.assertEqual(engine.code_variants(ref,{'code':'Z83.719'}),['Z83.719'])


def regression_reference():
    """Small public FY2027 paths/instructions in a synthetic XML wrapper.

    These cases were established against the full official release before the
    engine fixes. This excerpt makes the counterexamples repeatable without
    downloading a catalogue or invoking a database/provider in the test suite.
    """
    index = '''<ICD10CM.index><version>2027</version><letter>
      <mainTerm><title>Heartburn</title><code>R12</code>
        <term><title>psychogenic</title><code>F45.8</code></term></mainTerm>
      <mainTerm><title>GERD<nemod>(gastroesophageal reflux disease)</nemod></title><code>K21.9</code></mainTerm>
      <mainTerm><title>Disease</title><term><title>gastroesophageal reflux</title><code>K21.9</code></term></mainTerm>
      <mainTerm><title>Polyp</title><term><title>colon</title><code>K63.5</code></term></mainTerm>
      <mainTerm><title>History</title><term><title>family<nemod>(of)</nemod></title>
        <term><title>colonic polyps</title><code>Z83.719</code>
          <term><title>adenomatous and serrated</title><code>Z83.710</code></term></term></term>
        <term><title>personal</title><term><title>neoplasm</title><term><title>benign</title>
          <term><title>colon polyp</title><code>Z86.0100</code></term></term></term></term></mainTerm>
      <mainTerm><title>Screening<nemod>(for)</nemod></title><term><title>colonoscopy</title><code>Z12.11</code></term></mainTerm>
      </letter></ICD10CM.index>'''
    codes = {'R12':'Heartburn', 'F45.8':'Other somatoform disorders',
             'K21.9':'Gastro-esophageal reflux disease without esophagitis', 'K63.5':'Polyp of colon',
             'Z83.719':'Family history of colon polyps, unspecified',
             'Z83.710':'Family history of adenomatous and serrated polyps',
             'Z86.0100':'Personal history of colon polyps, unspecified',
             'Z12.11':'Encounter for screening for malignant neoplasm of colon'}
    nodes = ''.join(f'<diag><name>{code}</name><desc>{codes[code]}</desc></diag>'
                    for code in ('R12','F45.8','K21.9','K63.5'))
    tabular = f'''<ICD10CM.tabular><version>2027</version><chapter><name>1</name>
      <section id="synthetic-wrapper">{nodes}</section></chapter><chapter><name>21</name>
      <section id="Z00-Z13"><diag><name>Z12</name><desc>Encounter for screening for malignant neoplasms</desc>
        <useAdditionalCode><note>code to identify any family history of malignant neoplasm (Z80.-)</note></useAdditionalCode>
        <excludes1><note>encounter for diagnostic examination-code to sign or symptom</note></excludes1>
        <diag><name>Z12.11</name><desc>{codes['Z12.11']}</desc></diag></diag></section>
      <section id="Z77-Z99"><codeAlso><note>any follow-up examination (Z08-Z09)</note></codeAlso>
        <diag><name>Z83.719</name><desc>{codes['Z83.719']}</desc></diag>
        <diag><name>Z83.710</name><desc>{codes['Z83.710']}</desc></diag>
        <diag><name>Z86</name><desc>Personal history of certain other diseases</desc>
          <codeFirst><note>any follow-up examination after treatment (Z09)</note></codeFirst>
          <diag><name>Z86.0100</name><desc>{codes['Z86.0100']}</desc></diag></diag>
      </section></chapter></ICD10CM.tabular>'''
    return SimpleNamespace(**parse_reference(index, tabular, codes),
                           release_id='synthetic-reference', release=SimpleNamespace(version='FY2027'))


@override_settings(SYNTHETIC_ONLY=True)
class CodingEngineDemonstratedRegressionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = regression_reference()

    def generate_rows(self, notes, concepts, wanted):
        item = run(notes)
        def response(_run, stage, payload, *_args):
            if stage == 'concepts':
                return {'documented_patient_name':'', 'patient_name_evidence':'', 'concepts':concepts}
            choices = []
            for current in payload['concepts']:
                candidate = next((c for c in payload['candidates'][current['id']]
                                  if c['code'] == wanted[current['id']]), None)
                choices.append({'concept_id':current['id'], 'entry_id':candidate['entry_id'] if candidate else '',
                    'code':candidate['code'] if candidate else '', 'explanation':'Choose only a supplied candidate.',
                    'missing_detail':'' if candidate else 'The requested code was not supplied.'})
            return {'choices':choices}
        def code_lookup(**kwargs):
            return SimpleNamespace(first=lambda:SimpleNamespace(description=self.reference.tabular['codes'][kwargs['code']]))
        with patch.object(engine, 'reference_for', return_value=self.reference), \
             patch.object(engine.coding_provider, 'execute', side_effect=response), \
             patch('core.coding_licensing.cpt_status', return_value={'available':False}), \
             patch.object(engine.Code.objects, 'filter', side_effect=code_lookup):
            item.result = engine.generate(item)
            selected = [row['id'] for row in item.result['suggestions']]
            engine.validate_selection(item, {'selected_ids':selected, 'overrides':{}})
        return item.result

    def assert_codes(self, notes, current, requested, expected):
        result = self.generate_rows(notes, [current], {current['id']:requested})
        self.assertEqual([r['code'] for r in result['suggestions']], expected)
        return result

    def test_bare_symptom_cannot_select_psychogenic_child_or_disease_route(self):
        for terms, code in [(['Heartburn'],'F45.8'), (['Disease gastroesophageal reflux'],'K21.9')]:
            with self.subTest(terms=terms):
                c=concept('heartburn','Heartburn.',index_terms=terms)
                self.assert_codes('Heartburn.',c,code,[])
        self.assert_codes('Heartburn.',concept('heartburn','Heartburn.'),'R12',['R12'])

    def test_family_taxonomy_does_not_establish_an_unmentioned_condition(self):
        note="The patient's mother has heartburn."
        c=concept('heartburn',note,index_terms=['History family colonic polyps'],kind='family_history',subject='family')
        self.assert_codes(note,c,'Z83.719',[])

    def test_patient_and_heading_owned_family_findings_cannot_swap_roles(self):
        for note, evidence in [("The patient's mother had colon polyps.",'colon polyps'),
                               ('Family history:\nMother:\nColon polyps.','Colon polyps.')]:
            with self.subTest(note=note):
                self.assert_codes(note,concept('colon polyps',evidence,index_terms=['Polyp colon'],kind='diagnosis'),'K63.5',[])
        note='The patient has colon polyps.'
        c=concept('colon polyps',note,index_terms=['History family colonic polyps'],kind='family_history',subject='family')
        self.assert_codes(note,c,'Z83.719',[])

    def test_postposed_uncertainty_negation_and_resolved_history_override_model_labels(self):
        for note in ['GERD is suspected.','GERD is absent.','GERD has not been confirmed.','GERD resolved in 2018.']:
            with self.subTest(note=note):
                self.assert_codes(note,concept('GERD',note,kind='diagnosis'),'K21.9',[])

    def test_negated_branch_cannot_supply_missing_specificity(self):
        note='Heartburn. A psychogenic cause is not diagnosed.'
        self.assert_codes(note,concept('heartburn',note),'F45.8',[])
        note="The patient's mother had non-adenomatous colon polyps."
        c=concept('colon polyps',note,index_terms=['History family colonic polyps adenomatous'],kind='family_history',subject='family')
        self.assert_codes(note,c,'Z83.710',[])

    def test_official_and_title_accepts_either_documented_alternative(self):
        for histology in ['adenomatous','serrated']:
            note=f"The patient's mother had {histology} colon polyps."
            c=concept('colon polyps',note,index_terms=['History family colonic polyps '+histology],kind='family_history',subject='family')
            with self.subTest(histology=histology): self.assert_codes(note,c,'Z83.710',['Z83.710'])

    def test_source_causality_excludes_integral_symptom_without_model_link(self):
        note='The patient has GERD causing heartburn.'
        concepts=[concept('GERD',note,kind='diagnosis'),concept('heartburn',note,id='c2')]
        result=self.generate_rows(note,concepts,{'c1':'K21.9','c2':'R12'})
        self.assertEqual([r['code'] for r in result['suggestions']],['K21.9'])
        self.assertEqual([r['concept_id'] for r in result['excluded']],['c2'])

    def test_patient_profession_and_physician_report_do_not_transfer_ownership(self):
        for note in ['The patient is a doctor with GERD.','The physician reports that the patient has GERD.']:
            with self.subTest(note=note):
                self.assert_codes(note,concept('GERD',note,kind='diagnosis'),'K21.9',['K21.9'])
        note='The referring doctor has GERD.'
        self.assert_codes(note,concept('GERD',note,kind='diagnosis'),'K21.9',[])

    def test_complete_quote_does_not_absorb_later_family_sentence(self):
        quote='The patient has GERD.'
        self.assert_codes(quote+" The patient's mother had colon polyps.",
                          concept('GERD',quote,kind='diagnosis'),'K21.9',['K21.9'])

    def screening(self, suffix=''):
        quote='Asymptomatic patient here specifically for colon cancer screening; screening colonoscopy is planned.'
        current=concept('screening',quote,index_terms=['Screening colonoscopy'],kind='reason')
        return quote+suffix,current

    def test_screening_without_family_malignancy_does_not_invent_additional_code(self):
        for suffix in ['', ' No family history of malignant neoplasm.']:
            notes,current=self.screening(suffix)
            with self.subTest(suffix=suffix): self.assert_codes(notes,current,'Z12.11',['Z12.11'])

    def test_screening_with_family_malignancy_retains_unresolved_instruction(self):
        for suffix in [' Mother had colon cancer.','\nFamily history:\nMother:\nColon cancer.']:
            notes,current=self.screening(suffix)
            with self.subTest(suffix=suffix):
                result=self.assert_codes(notes,current,'Z12.11',[])
                self.assertTrue(any('family history of malignant neoplasm' in q['question'] for q in result['questions']))

    def test_later_same_procedure_diagnostic_correction_cannot_be_clipped_away(self):
        notes,current=self.screening(" Correction: the same colonoscopy is diagnostic for the patient's current abdominal pain.")
        result=self.assert_codes(notes,current,'Z12.11',[])
        self.assertTrue(any('diagnostic examination' in q['question'] for q in result['questions']))

    def test_personal_history_follow_up_condition_is_evaluated_from_whole_source(self):
        quote='The patient previously had a colon polyp removed.'
        current=concept('colon polyp',quote,index_terms=['History personal neoplasm benign colon polyp'],kind='personal_history',temporality='historical')
        self.assert_codes(quote,current,'Z86.0100',['Z86.0100'])
        result=self.assert_codes(quote+' This is a follow-up examination after completed treatment.',current,'Z86.0100',[])
        self.assertTrue(any('follow-up examination after treatment' in q['question'] for q in result['questions']))
