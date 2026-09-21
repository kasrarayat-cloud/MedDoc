from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from core.generation import Selection, Selections, fixture, validate_selections
from core.tab_review import validate_identity


class TabIdentityPolicyTests(SimpleTestCase):
    def setUp(self):
        self.fields=[{'key':'signed','label':'Electronically signed by',
                     'answer_policy':'clinician_identity','locator':{'tab_form':{'version':1}}},
                    {'key':'consent','label':'CONSENT'},
                    {'key':'dictated','label':'DD (dictated)'},
                    {'key':'transcribed','label':'DT (transcribed)'},
                    {'key':'finding','label':'POSTOPERATIVE FINDINGS — 1'}]
        self.actor=SimpleNamespace(pk='finalizer',get_full_name=lambda:'Synthetic Clinician',email='doctor@synthetic.quillmd.invalid')

    def test_provider_selected_other_identity_is_never_generated(self):
        notes='Electronically signed by: Someone Else'
        selections=Selections(fields=[Selection(key=f['key'],quotes=['Someone Else'] if f['key']=='signed' else [],conflict=False) for f in self.fields])
        answer=validate_selections(notes,self.fields,selections)['signed']
        self.assertEqual((answer['text'],answer['status'],answer['reviewed']),('','missing',False))

    def test_missing_consent_dates_and_findings_have_no_defaults(self):
        result=validate_selections('',self.fields,fixture('',self.fields))
        self.assertTrue(all(x['text']=='' and x['status']=='missing' for x in result.values()))

    def test_documented_dates_are_not_replaced_with_finalization_time(self):
        notes='DD (dictated): 2026-09-18\nDT (transcribed): 2026-09-19'
        result=validate_selections(notes,self.fields,fixture(notes,self.fields))
        self.assertEqual(result['dictated']['text'],'2026-09-18')
        self.assertEqual(result['transcribed']['text'],'2026-09-19')
        self.assertEqual(result['signed']['text'],'')

    def test_finalizer_identity_or_explicit_blank_only(self):
        validate_identity(self.fields,{},self.actor)
        validate_identity(self.fields,{'signed':{'text':'Synthetic Clinician','reviewed':True,'reviewed_by':'finalizer'}},self.actor)
        with self.assertRaises(ValidationError):
            validate_identity(self.fields,{'signed':{'text':'Someone Else'}},self.actor)

    def test_editing_display_label_does_not_remove_identity_guard(self):
        fields=[{**self.fields[0],'label':'Other label'}]
        with self.assertRaises(ValidationError):
            validate_identity(fields,{'signed':{'text':'Someone Else'}},self.actor)

    def test_legacy_regular_fields_retain_their_existing_behavior(self):
        fields=[{'key':'old','label':'Signature','locator':{'paragraph':0}}]
        validate_identity(fields,{'old':{'text':'Legacy reviewed text'}},self.actor)

    def test_another_reviewers_checkbox_cannot_authorize_finalizers_signature(self):
        for answer in ({'text':'Synthetic Clinician','reviewed':True,'reviewed_by':'other'},
                       {'text':'Synthetic Clinician','reviewed':False,'reviewed_by':'finalizer'}):
            with self.assertRaises(ValidationError):
                validate_identity(self.fields,{'signed':answer},self.actor)
