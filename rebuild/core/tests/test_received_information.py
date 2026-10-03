"""Ordinary receipt information retains its historical source and role guards."""
from django.test import SimpleTestCase, override_settings
from core import generation as g, v3_field_relations as r
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw
from .test_v3_field_relations import relation_wire
from .test_transcript_context import proof


@override_settings(**SONNET_55_DEFAULT)
class ReceivedInformation(SimpleTestCase):
    def answer(self,notes,label,pick):
        fields=form(label)
        result=raw(notes,fields,relation_wire(notes,fields,{'f1':[pick]}),g.SONNET_5_5)
        result['patient_default_context']=proof(notes)
        answers=r.validated(result);answer=answers['f1']
        page=g.as_currently_governed(g.governance_for(notes,fields),notes,{**fields[0],**answer})
        self.assertEqual(page['status'],answer['status'])
        return fields,answers,page

    def test_retained_received_date_and_document_are_useful(self):
        for label,notes,expected in [
            ('Signed consent was received on','Signed consent was received on: 3 October 2026','3 October 2026'),
            ('Signed referral received','Signed referral received: a signed referral letter from the GP was received yesterday.',
             'a signed referral letter from the GP was received yesterday.')]:
            with self.subTest(label=label):
                fields,answers,page=self.answer(notes,label,notes)
                self.assertEqual((page['status'],page['text']),('supported',expected))
                self.assertEqual(page['evidence'],[{'quote':notes,'start':0,'end':len(notes)}])
                self.assertEqual(g.governed_decisions(notes,fields,answers),[])

    def test_ordinary_receipt_does_not_erase_correction_or_current_time(self):
        source='Signed referral received: a signed referral letter from the GP was received yesterday.'
        for label,notes in [
            ('Signed referral received',source+'\n\nCorrection: the referral letter was not received.'),
            ('Signed referral currently received','Signed referral currently received: a signed referral letter from the GP was received yesterday.')]:
            with self.subTest(label=label):
                pick=source if label=='Signed referral received' else notes
                _,_,page=self.answer(notes,label,pick)
                self.assertEqual((page['status'],page['text']),('conflict',''))

    def test_entire_retained_receipt_source_preserves_other_answers_and_finalization(self):
        notes='Initial diagnosis: Sprain\n\nSigned consent was received on: 3 October 2026\n\nPlan: Rest.'
        fields=form('Initial diagnosis','Signed consent was received on','Plan')
        expected=['Sprain','3 October 2026','Rest.']
        units=g.source_units(notes,fields)[0]
        body=relation_wire(notes,fields,{f['key']:[u['quote']] for f,u in zip(fields,units)})
        result=raw(notes,fields,body,g.SONNET_5_5);result['patient_default_context']=proof(notes)
        answers=r.validated(result);governance=g.governance_for(notes,fields)
        for field,value in zip(fields,expected):
            row=g.as_currently_governed(governance,notes,{**field,**answers[field['key']]})
            self.assertEqual((row['status'],row['text']),('supported',value))
        self.assertEqual(g.governed_decisions(notes,fields,answers),[])

    def test_actual_signing_destinations_never_adopt_receipt_values(self):
        for label in ['Clinician signature','Signed by (patient)','Signed by (witness)','Signed (manager)']:
            notes=label+': Dr Synthetic'
            with self.subTest(label=label):
                _,_,page=self.answer(notes,label,notes)
                self.assertNotEqual(page['status'],'supported')
                self.assertEqual(page['text'],'')

    def test_consent_act_does_not_inherit_receipt_exemption(self):
        notes='Consent obtained: yes\n\nPlan: Rest.'
        fields=form('Consent obtained','Plan');units=g.source_units(notes,fields)[0]
        body=relation_wire(notes,fields,{f['key']:[u['quote']] for f,u in zip(fields,units)})
        result=raw(notes,fields,body,g.SONNET_5_5);result['patient_default_context']=proof(notes)
        answer=r.validated(result)['f1']
        self.assertEqual((answer['status'],answer['text']),('conflict',''))
