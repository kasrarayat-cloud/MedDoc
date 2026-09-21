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
        fields=[{'key':'old','label':'Findings','locator':{'paragraph':0}}]
        validate_identity(fields,{'old':{'text':'Legacy reviewed text'}},self.actor)

    def test_a_legacy_field_actually_labelled_signature_is_no_longer_regular(self):
        """⚠️ A DELIBERATE CHANGE OF BEHAVIOUR ON EXISTING DATA, recorded rather than slipped in.

        This case used the label 'Signature' to stand for "an ordinary legacy field", and the
        assertion was that it finalizes with any text and no review. But 'Signature' is the
        commonest signature label on a real Word form, and the refutation pass measured the
        consequence: a name lifted from the dictation reached the signature line of a finalized
        record with no check that the finalizer was the person named.

        So the protection now follows the LABEL, and the cost lands here: an existing encounter
        whose question is called 'Signature' can no longer be finalized until the clinician
        reviews it and enters their own name or leaves it blank. That is a real cost on stored
        work, it is the owner's to revisit, and it is written into the handoff as such.
        """
        fields=[{'key':'old','label':'Signature','locator':{'paragraph':0}}]
        with self.assertRaises(ValidationError):
            validate_identity(fields,{'old':{'text':'Legacy reviewed text'}},self.actor)

    def test_a_parenthetical_that_makes_it_a_date_question_is_not_a_signature(self):
        """⚠️ THE DECLARED BOUND WAS REACHABLE BY ANOTHER SPELLING.

        The qualifier arm `( ?\([^)]*\))?` is content-blind, so `Signature (date)` and
        `Signature (date and time)` matched and would have demanded the finalizing clinician's
        own name in a DATE question — exactly the false refusal the declaration says it bounded.
        """
        for label in ('Signature (date)', 'Signature (date and time)', 'Signature (Date)'):
            with self.subTest(label=label):
                fields=[{'key':'old','label':label,'locator':{'paragraph':0}}]
                validate_identity(fields,{'old':{'text':'12/09/2026'}},self.actor)

    def test_the_signature_lines_it_must_still_recognise_are_untouched(self):
        """The control on that narrowing: a date WORD alone must not disarm the guard."""
        for label in ('Signature/Date', 'Signature (print name)', 'Electronically signed by'):
            with self.subTest(label=label):
                fields=[{'key':'old','label':label,'locator':{'paragraph':0}}]
                with self.assertRaises(ValidationError):
                    validate_identity(fields,{'old':{'text':'Somebody Else'}},self.actor)

    def test_a_signature_that_is_explicitly_somebody_elses_is_not_the_finalizers(self):
        """The false-refusal control on the same widening."""
        for label in ('Patient signature','Signed by (witness)','Guardian signature',
                      'Signature date','Attestation'):
            with self.subTest(label=label):
                fields=[{'key':'old','label':label,'locator':{'paragraph':0}}]
                validate_identity(fields,{'old':{'text':'Legacy reviewed text'}},self.actor)

    def test_another_reviewers_checkbox_cannot_authorize_finalizers_signature(self):
        for answer in ({'text':'Synthetic Clinician','reviewed':True,'reviewed_by':'other'},
                       {'text':'Synthetic Clinician','reviewed':False,'reviewed_by':'finalizer'}):
            with self.assertRaises(ValidationError):
                validate_identity(self.fields,{'signed':answer},self.actor)
