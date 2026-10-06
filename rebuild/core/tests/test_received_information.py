"""Ordinary receipt information retains its historical source and role guards."""
from django.test import SimpleTestCase, override_settings
from core import generation as g, v3_field_relations as r
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw
from .test_v3_field_relations import relation_wire
from .test_transcript_context import proof


@override_settings(**SONNET_55_DEFAULT)
class ReceivedInformation(SimpleTestCase):
    def answer(self,notes,label,pick,extra_labels=()):
        fields=form(label,*extra_labels)
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

    def test_retained_elliptical_receipt_date_keeps_whole_source_and_other_answer(self):
        notes='Signed consent received on: 2026-09-30\nUnrelated note: Synthetic review'
        fields=form('Signed consent received on','Unrelated note')
        units=g.source_units(notes,fields)[0]
        body=relation_wire(notes,fields,{f['key']:[u['quote']] for f,u in zip(fields,units)})
        result=raw(notes,fields,body,g.SONNET_5_5);result['patient_default_context']=proof(notes)
        answers=r.validated(result);governance=g.governance_for(notes,fields)
        for field,unit,value in zip(fields,units,['2026-09-30','Synthetic review']):
            page=g.as_currently_governed(governance,notes,{**field,**answers[field['key']]})
            self.assertEqual((page['status'],page['text']),('supported',value))
            self.assertEqual(page['evidence'],[{k:unit[k] for k in ('quote','start','end')}])
        self.assertEqual(g.governed_decisions(notes,fields,answers),[])

    def test_receipt_date_accepts_calendar_formats_and_source_relative_past_day(self):
        for label in ['Signed consent received on','Signed consent was received on']:
            for value in ['2026-09-30','3 October 2026','September 30, 2026','09/30/2026',
                          '30/09/2026','today','yesterday']:
                with self.subTest(label=label,value=value):
                    source=label+': '+value
                    fields,answers,page=self.answer(source+'\nUnrelated note: Synthetic review',label,source,('Unrelated note',))
                    self.assertEqual((page['status'],page['text']),('supported',value))
                    self.assertEqual(g.governed_decisions(source+'\nUnrelated note: Synthetic review',fields,answers),[])

    def test_completed_receipt_date_never_adopts_future_uncertain_or_non_date_value(self):
        for label in ['Signed consent received on','Signed consent was received on']:
            for value in ['tomorrow','next week','possibly 2026-09-30','not received','unknown',
                          '2026-09-31','2026-09-30 for mother','2026-09-30 (witness only)']:
                with self.subTest(label=label,value=value):
                    source=label+': '+value
                    fields,answers,page=self.answer(source,label,source)
                    self.assertEqual((page['status'],page['text']),('conflict',''))
                    # A stored formerly supported draft is governed the same
                    # way at page display and finalization; no new record
                    # silently adopts its stale completion value.
                    stale={**answers['f1'],'status':'supported','text':value}
                    self.assertEqual(g.governed_decisions(source,fields,{'f1':stale}),[label])
                    row=g.as_currently_governed(g.governance_for(source,fields),source,{**fields[0],**stale})
                    self.assertEqual((row['status'],row['text']),('conflict',''))

    def test_future_receipt_schedule_is_a_separate_useful_destination(self):
        label='Signed consent due on';source=label+': tomorrow'
        fields,answers,page=self.answer(source,label,source)
        self.assertEqual((page['status'],page['text']),('supported','tomorrow'))
        self.assertEqual(g.governed_decisions(source,fields,answers),[])

    def test_elliptical_receipt_never_grants_permission_or_a_signing_actor(self):
        for label in ['Consent obtained','Signed by (patient)','Signed by (witness)','Signed by (manager)',
                      'Patient signature','Witness signature','Manager signature','Clinician signature',
                      'Patient received on','Manager received on','Witness received on','Nurse received on',
                      'Expected signed consent received on','Possible signed consent received on',
                      'Signed consent not received on','Signed consent will be received on',
                      'Signed consent currently received on']:
            with self.subTest(label=label):
                source=label+': 2026-09-30'
                _,_,page=self.answer(source+'\nUnrelated note: Synthetic review',label,source,('Unrelated note',))
                self.assertNotEqual(page['status'],'supported')
                self.assertEqual(page['text'],'')

    def test_elliptical_receipt_retains_actual_correction_and_uncertain_source(self):
        source='Signed consent received on: 2026-09-30'
        for ending in ['Correction: signed consent was not received.',
                       'Correction: received on 2026-10-01 instead.',
                       'It is unclear whether signed consent was received.',
                       'The patient has not consented.']:
            with self.subTest(ending=ending):
                fields,answers,page=self.answer(source+'\n'+ending,'Signed consent received on',source)
                self.assertEqual((page['status'],page['text']),('conflict',''))
                self.assertEqual(g.governed_decisions(source+'\n'+ending,fields,answers),[])

    def test_consent_act_does_not_inherit_receipt_exemption(self):
        notes='Consent obtained: yes\n\nPlan: Rest.'
        fields=form('Consent obtained','Plan');units=g.source_units(notes,fields)[0]
        body=relation_wire(notes,fields,{f['key']:[u['quote']] for f,u in zip(fields,units)})
        result=raw(notes,fields,body,g.SONNET_5_5);result['patient_default_context']=proof(notes)
        answer=r.validated(result)['f1']
        self.assertEqual((answer['status'],answer['text']),('conflict',''))
