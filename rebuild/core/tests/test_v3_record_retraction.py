"""Combined source subjects and nominal Plan must retain record corrections for review."""
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, override_settings
from core import generation as g
from .test_v3_literal_subjects import ALLERGY, EXAMS, FIELDS
from .test_v3_ordinary_notes import run, LIVE
from .test_v3_ordinary_input import ordinary_input_form
from .test_word_v3_workflow import V3EncounterFixture


class RecordRetraction(SimpleTestCase):
    def test_record_retractions_govern_generation_and_old_supported_values(self):
        for label,quote,tail in [
            ('Allergies',ALLERGY,'removal of erroneous NKA entry.'),
            ('Allergies',ALLERGY,'delete that entry from the chart.'),
            ('Allergies',ALLERGY,'omit this statement from final chart.'),
            ('Allergies',ALLERGY,'withdrawal of the erroneous declaration.'),
            ('Allergies',ALLERGY,'omission of erroneous NKA entry.'),
            ('Allergies',ALLERGY,'clinician deletes erroneous NKA entry.'),
            ('Allergies',ALLERGY,'clinician removes erroneous NKA entry.'),
            ('Examination',EXAMS[0],'deletion of erroneous normal neurological entry.'),
            ('Examination',EXAMS[1],'deletion of erroneous normal cardiopulmonary entry.'),
            ('Allergies',ALLERGY,'penicillin avoidance for documented anaphylaxis.'),
            ('Allergies',ALLERGY,'ａｃｔｕａｌｌｙ there is a penicillin reaction.'),
            ('Examination',EXAMS[0],'ａｃｔｕａｌｌｙ focal weakness is present.')]:
            with self.subTest(label=label,tail=tail):
                notes=quote+'\nPlan: '+tail
                answer=run(notes,{label:[quote]},fields=FIELDS)[label]
                self.assertEqual((answer['status'],answer['text']),('conflict',''))
                key=next(f['key'] for f in FIELDS if f['label']==label)
                old={'status':'supported','text':quote,'reviewed':True,
                     'evidence':[{'quote':quote,'start':0,'end':len(quote)}]}
                self.assertEqual(g.governed_decisions(notes,FIELDS,{key:old}),[label])

    def test_fullwidth_beneficiary_does_not_acquire_patient_ownership(self):
        quote='Neurological examination is normal for her ｍｏｔｈｅｒ.'
        notes=quote+'\n'+ALLERGY
        answers=run(notes,{'Examination':[quote],'Allergies':[ALLERGY]},fields=FIELDS)
        for label in ('Examination','Allergies'):
            self.assertEqual((answers[label]['status'],answers[label]['text']),('conflict',''))

    def test_physical_removal_is_not_a_record_retraction(self):
        for tail in ('removal of stitches.','removal of the temporary device.',
                     'removal of stitches documented.','removal of the temporary device documented.',
                     'record removal of stitches.','remove the catheter and note response.',
                     'document removal of stitches.'):
            notes=ALLERGY+'\nPlan: '+tail
            answer=run(notes,{'Allergies':[ALLERGY]},fields=FIELDS)['Allergies']
            self.assertEqual((answer['status'],answer['text']),('supported',ALLERGY))


@override_settings(**LIVE)
class RetractionWorkflow(V3EncounterFixture,TestCase):
    def setUp(self):
        with patch('core.tests.test_word_v3_workflow.build_intake_form',
                   side_effect=lambda path:ordinary_input_form(path,['Allergies','Plan'])):
            super().setUp()
        denied=patch('socket.socket.connect',side_effect=AssertionError('Network denied'))
        denied.start();self.addCleanup(denied.stop)

    def test_stale_supported_record_cannot_be_reapproved_or_exported(self):
        self.encounter.notes=ALLERGY+'\nPlan: removal of erroneous NKA entry.'
        self.encounter.answers={f['key']:{'status':'left_blank','text':'','reviewed':True,'evidence':[]}
                                for f in self.version.fields}
        self.encounter.answers[self.key('Allergies')]={'status':'supported','text':ALLERGY,'reviewed':True,
            'evidence':[{'quote':ALLERGY,'start':0,'end':len(ALLERGY)}]}
        self.encounter.save(update_fields=['notes','answers'])
        rows=self.client.get(f'/encounters/{self.encounter.pk}/').context['answer_rows']
        row=next(r for r in rows if r['label']=='Allergies')
        self.assertEqual((row['status'],row['text']),('conflict',''))
        self.finalize();self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status,'finalized');self.assertFalse(self.encounter.export_path)
        self.assertEqual(self.save({'Allergies':ALLERGY}).status_code,302)
        self.finalize();self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status,'finalized');self.assertFalse(self.encounter.export_path)
