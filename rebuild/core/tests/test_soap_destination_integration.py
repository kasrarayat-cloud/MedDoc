"""Prospective destination routing with unchanged source evidence and decisions."""
from copy import deepcopy
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.tests.test_semantic_generation import fact, assignments
from documents.semantic_preparation_roles import default_definitions


class SoapDestinationIntegrationTests(SimpleTestCase):
    header='Patient: Synthetic Ada Tern\nService date: 21 October 2027\nTreating clinician: Dr. Mira Cole\n'

    def run_assignment(self,body,values,meanings,picked,*,profile=None):
        notes=self.header+body
        fields=[{'key':key,'label':key,'kind':'text','locator':{'cell':index}}
            for index,key in enumerate(meanings)]
        definitions=default_definitions(fields)
        for key,(meaning,subject,timing,polarity) in meanings.items():
            definitions[key].update(version=2,answer_mode='narrative',meaning=meaning,
                scope={'subject':subject,'temporality':timing,'polarity':polarity})
        units,_=generation.source_units(notes,fields)
        raw=[fact(notes,fields,key,value[0],kind=value[1],polarity=value[2],timing=value[3],
            subject=value[4] if len(value)>4 else 'patient') for key,value in values.items()]
        before=deepcopy(raw)
        profile=profile or semantic.SOAP_ASSERTION_SCOPE_CONTRACT
        validated=semantic.validate_facts(notes,units,{'facts':raw},scope_contract=profile)
        result=semantic._assign(notes,fields,definitions,validated,assignments(fields,picked),scope_contract=profile)
        self.assertEqual(raw,before)
        return result,validated

    def test_whole_denial_and_exam_preserve_scope_and_omission_holds(self):
        denial='She denies fever, vomiting and severe abdominal pain'
        exam='The abdomen is soft and nondistended, with normal bowel sounds and no tenderness, guarding or rebound'
        values={'denial':(denial,'finding','negated','current'), 'exam':(exam,'finding','mixed','current')}
        meanings={
            'negative':('All documented symptom negatives (symptoms documented as absent), each with its exact documented scope.','patient','current','negative'),
            'objective':('The complete documented examination, including both positive and negative findings.','patient','current','any')}
        body='S\n'+denial+'.\nO\n'+exam+'.'
        for omitted in (None,'exam'):
            picked={'negative':['denial'],'objective':[] if omitted else ['exam']}
            result,_=self.run_assignment(body,values,meanings,picked)
            self.assertEqual(result['negative']['status'],'supported',result['negative']['review_reasons'])
            self.assertIn('severe abdominal pain',result['negative']['text'])
            if omitted:self.assertIn(result['objective']['status'],('conflict','ambiguous'))
            else:self.assertEqual(result['objective']['status'],'supported',result['objective']['review_reasons'])
        restricted=deepcopy(meanings)
        restricted['negative']=(meanings['negative'][0]+' Exclude abdominal pain.','patient','current','negative')
        result,_=self.run_assignment(body,values,restricted,{'negative':['denial'],'objective':['exam']})
        self.assertNotEqual(result['negative']['status'],'supported')
        for instruction in ('Physical exam findings. Omit normal bowel sounds.',
                'Physical exam findings, do not include normal bowel sounds.',
                'Physical exam findings, positive observations alone.',
                'Physical exam findings, negative findings are optional.'):
            restricted['objective']=(instruction,'patient','current','any')
            result,_=self.run_assignment(body,values,restricted,{'negative':['denial'],'objective':['exam']})
            self.assertNotEqual(result['objective']['status'],'supported',instruction)

    def test_past_trial_can_include_requested_current_nonuse_only_with_selected_trial(self):
        trial='She previously took cetirizine 10 mg by mouth each evening for itching from 2 October through 7 October 2027'
        response='It gave no meaningful relief'
        stopped='She stopped it on 8 October because it was not helping and is no longer taking cetirizine'
        current='is no longer taking cetirizine'
        values={'trial':(trial,'history','affirmed','past'),'response':(response,'history','negated','past'),
            'stop':(stopped.split(' and ')[0],'history','affirmed','past'),
            'current':(current,'history','negated','current')}
        meaning='A stopped historical medicine as documented: dose, route, frequency, indication, dates, response, stopping reason and explicit statement of non-use now. Restricted to medicine used before the target encounter; documented absence is allowed.'
        meanings={'prior':(meaning,'patient','past','any')}
        body='S\n'+trial+'. '+response+'. '+stopped+'.'
        for selected in (list(values),['trial','response','stop'],['response','stop','current'],
                ['trial','response','current'],['trial','stop','current'],['trial','current']):
            result,_=self.run_assignment(body,values,meanings,{'prior':selected})
            if len(selected)==4:self.assertEqual(result['prior']['status'],'supported',result['prior']['review_reasons'])
            else:self.assertIn(result['prior']['status'],('conflict','ambiguous'))
        meanings['prior']=(meaning+' Omit current non-use.','patient','past','any')
        result,_=self.run_assignment(body,values,meanings,{'prior':list(values)})
        self.assertNotEqual(result['prior']['status'],'supported')

    def test_investigation_and_procedure_statuses_route_separately_without_dropping_either(self):
        test='No blood sample was collected today, the test was not performed today and no result is available'
        procedure='No procedure was performed during this encounter'
        values={'test':(test,'finding','negated','current'),'procedure':(procedure,'finding','negated','current')}
        meanings={
            'investigation':('Investigation ordered, its evaluation purpose, intended collection timing, and the actual collection, performance and result status today. Retain documented not-yet-done or not-resulted status.','patient','current','any'),
            'procedure':('Procedure status today.','encounter','current','any')}
        body='P\n'+test+'. '+procedure+'.'
        for omitted in (None,'test','procedure'):
            picked={'investigation':[] if omitted=='test' else ['test'],'procedure':[] if omitted=='procedure' else ['procedure']}
            result,_=self.run_assignment(body,values,meanings,picked)
            for key,which in [('investigation','test'),('procedure','procedure')]:
                if omitted==which:self.assertIn(result[key]['status'],('conflict','ambiguous'))
                else:self.assertEqual(result[key]['status'],'supported',result[key]['review_reasons'])
        for restriction in ('Exclude results.','Do not include result status.',
                'Retain collection only.','Omit the actual performance status.'):
            restricted={'investigation':(meanings['investigation'][0]+' '+restriction,'patient','current','any')}
            result,_=self.run_assignment('P\n'+test+'.',{'test':values['test']},restricted,{'investigation':['test']})
            self.assertNotEqual(result['investigation']['status'],'supported',restriction)
            self.assertTrue(any('restricted by this approved destination' in reason for reason in result['investigation']['review_reasons']))

    def test_unclassified_coordinated_nonperformance_keeps_legacy_completeness_hold(self):
        source='No blood test or endoscopy was performed today'
        meanings={'procedure':('Procedure status today.','encounter','current','any')}
        result,_=self.run_assignment('P\n'+source+'.',{},meanings,{'procedure':[]})
        self.assertEqual(result['procedure']['status'],'conflict')
        self.assertTrue(any(source in reason for reason in result['procedure']['review_reasons']))

    def test_order_purpose_and_timing_cannot_disappear_behind_complete_status(self):
        meaning='Investigation ordered, its evaluation purpose, intended collection timing, and the actual collection, performance and result status today. Retain documented not-yet-done or not-resulted status.'
        status='No blood sample was collected today, the test was not performed today and no result is available'
        orders=('I ordered a urine culture to evaluate for urinary infection, with collection planned tomorrow',
            'A thyroid-stimulating hormone blood test is ordered for collection at a laboratory after this visit as part of the constipation evaluation')
        for order in orders:
            values={'order':(order,'plan','affirmed','current'),'status':(status,'finding','negated','current')}
            for selected in (['order','status'],['status']):
                result,_=self.run_assignment('P\n'+order+'. '+status+'.',values,
                    {'investigation':(meaning,'patient','current','any')},{'investigation':selected})
                if len(selected)==2:self.assertEqual(result['investigation']['status'],'supported',result['investigation']['review_reasons'])
                else:
                    self.assertEqual(result['investigation']['status'],'conflict')
                    self.assertTrue(any('investigation_order' in r for r in result['investigation']['review_reasons']))
        for beneficiary in ('her sister',"the patient's mother",'another patient',
                'her cousin','his aunt','their nephew','her friend','her paternal grandmother',
                'her family member','her parent'):
            order='I ordered a urine culture for '+beneficiary+' to evaluate urinary infection, with collection planned tomorrow'
            values={'order':(order,'plan','affirmed','current'),'status':(status,'finding','negated','current')}
            result,facts=self.run_assignment('P\n'+order+'. '+status+'.',values,
                {'investigation':(meaning,'patient','current','any')},{'investigation':['order','status']})
            self.assertNotEqual(result['investigation']['status'],'supported')
            self.assertTrue(any('beneficiary' in reason for reason in facts['order']['issues']))
            self.assertEqual(facts['status']['issues'],[])
        order='I ordered a blood test for family history of thyroid disease, with collection planned tomorrow'
        from core.clinical_assertions_v4 import foreign_order_beneficiary
        self.assertFalse(foreign_order_beneficiary(order))
        values={'order':(order,'plan','affirmed','current'),'status':(status,'finding','negated','current')}
        result,facts=self.run_assignment('P\n'+order+'. '+status+'.',values,
            {'investigation':(meaning,'patient','current','any')},{'investigation':['order','status']})
        # A complete current order retains the family relationship as its
        # indication, never as an order beneficiary or patient diagnosis.
        self.assertFalse(any('beneficiary' in reason for reason in facts['order']['issues']))
        self.assertEqual(facts['order']['issues'],[])
        self.assertEqual(facts['status']['issues'],[])
        self.assertEqual(result['investigation']['status'],'supported',result['investigation']['review_reasons'])

    def test_included_and_excluded_time_each_remain_required_in_their_own_field(self):
        basis="Office E/M selection is based on the treating physician's total time on the service date"
        total='Dr. Cole personally spent 34 minutes on 21 October 2027: 30 minutes examining the patient and four minutes documenting'
        exclusion='The 34 minutes exclude five minutes of staff intake work and eight minutes of physician record review performed on the preceding day'
        values={key:(quote,'other','affirmed','current','clinician') for key,quote in [('basis',basis),('total',total),('exclusion',exclusion)]}
        meanings={
            'included':('The documented E/M selection basis, total physician time, service date and each included activity with its minutes.','encounter','current','any'),
            'excluded':('Excluded staff time and prior-day physician time with minutes, any separately reported service exclusion, and procedure status today.','encounter','current','any')}
        body='P\n'+basis+'. '+total+'. '+exclusion+'.'
        for omitted in (None,'total','exclusion'):
            picked={'included':['basis']+([] if omitted=='total' else ['total']),
                'excluded':[] if omitted=='exclusion' else ['exclusion']}
            result,_=self.run_assignment(body,values,meanings,picked)
            for key,which in [('included','total'),('excluded','exclusion')]:
                if omitted==which:self.assertIn(result[key]['status'],('conflict','ambiguous'))
                else:self.assertEqual(result[key]['status'],'supported',result[key]['review_reasons'])
