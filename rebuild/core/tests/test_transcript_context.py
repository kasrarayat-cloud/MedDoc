"""Explicit reviewed-transcript actor context, original evidence and clinical counterexamples.

Every model choice is simulated; no provider requests or patient data.
"""
import json
import io
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g, transcript_context as tc, v3_field_relations as r
from core.jobs import enqueue, run_one
from core.models import AuditEvent, Encounter, Job, LedgerEntry, Membership, TranscriptReview, Usage
from core.security import private_path
from .test_billing_boundary import BoundaryFixture, deepgram
from .test_billing_policy import STORAGES
from .audio_fixtures import wav_bytes
from .test_v3_field_relations import relation_wire
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw
from .test_word_v3_workflow import V3, V3Fixture, part_text
from docx import Document


def proof(notes, start=0, end=None):
    end = len(notes) if end is None else end
    return tc.token_for(SimpleNamespace(pk=uuid4(), job_id=uuid4(), reviewed_by_id=uuid4(), source_revision=1,
        source_sha256=tc.digest(notes), raw_sha256=tc.digest(notes), result_sha256='0'*64,
        reviewed_sha256=tc.digest(notes[start:end]), span_start=start, span_end=end))


@override_settings(**SONNET_55_DEFAULT)
class PatientDefault(SimpleTestCase):
    def answers(self, notes, picks, context=True, start=0):
        fields = form(*picks)
        keyed = {f['key']: picks[f['label']] for f in fields}
        result = raw(notes, fields, relation_wire(notes, fields, keyed), g.SONNET_5_5)
        if context: result['patient_default_context'] = proof(notes, start=start)
        return fields, r.validated(result)

    def check(self, notes, label, selected, expected='supported', context=True, start=0):
        fields, answers = self.answers(notes, {label: selected}, context=context, start=start)
        answer = answers['f1']
        self.assertEqual(answer['status'], expected, (notes, answer))
        if expected == 'supported':
            self.assertEqual(answer['text'], '\n'.join(selected))
            self.assertEqual([e['quote'] for e in answer['evidence']], selected)
            self.assertEqual(g.governed_decisions(notes, fields, answers), [])
            row = g.as_currently_governed(g.governance_for(notes, fields), notes, {**fields[0], **answer})
            self.assertEqual((row['status'], row['text']), ('supported', answer['text']))
        else:self.assertEqual(answer['text'], '')
        return answer

    def test_subjectless_patient_values_are_useful_with_original_evidence(self):
        for label, source in [('Medications', 'Takes warfarin 5 mg daily.'),
                              ('Symptoms', 'Reports cough.')]:
            with self.subTest(source=source):
                self.check(source, label, [source], 'conflict', context=False)
                self.check(source, label, [source])

    def test_context_is_exact_and_span_bound_not_a_global_patient_assumption(self):
        source = 'Takes warfarin 5 mg daily.'
        prefix = 'Reports cough.\n\n'
        notes = prefix + source
        self.check(notes, 'Symptoms', ['Reports cough.'], 'conflict', start=len(prefix))
        self.check(notes, 'Medications', [source], start=len(prefix))
        token = proof(notes, start=len(prefix))
        self.assertTrue(tc.verified(notes, token))
        self.assertIsNone(tc.verified(notes+' ', token))
        self.assertIsNone(tc.verified(notes, token[:-1]+'x'))
        self.assertIsNone(tc.verified(notes, proof(notes, end=0)))
        self.assertIsNone(tc.verified(notes, True))

    def test_explicit_other_and_inherited_other_never_gain_patient_subject(self):
        for notes, pick in [('Her father takes warfarin 5 mg daily.', 'Her father takes warfarin 5 mg daily.'),
                            ('Her father reports cough. Takes warfarin 5 mg daily.', 'Takes warfarin 5 mg daily.'),
                            ('The nurse takes warfarin 5 mg daily.', 'The nurse takes warfarin 5 mg daily.'),
                            ('He takes warfarin 5 mg daily.', 'He takes warfarin 5 mg daily.'),
                            ('"Takes warfarin 5 mg daily."', '"Takes warfarin 5 mg daily."')]:
            with self.subTest(notes=notes):self.check(notes, 'Medications', [pick], 'conflict')

    def test_time_uncertainty_denial_and_cessation_keep_their_meaning(self):
        for notes, pick in [('Previously took warfarin 5 mg daily.', 'Previously took warfarin 5 mg daily.'),
                            ('May take warfarin 5 mg daily.', 'May take warfarin 5 mg daily.'),
                            ('Takes warfarin 5 mg daily. Warfarin was stopped.', 'Takes warfarin 5 mg daily.'),
                            ('Takes warfarin 5 mg daily. Warfarin was withheld today.', 'Takes warfarin 5 mg daily.'),
                            ('Takes warfarin 5 mg daily. Warfarin is on hold.', 'Takes warfarin 5 mg daily.'),
                            ('Takes warfarin 5 mg daily. Warfarin was replaced by apixaban.', 'Takes warfarin 5 mg daily.')]:
            with self.subTest(notes=notes):self.check(notes, 'Medications', [pick], 'conflict')
        # A denial stays a denial in the full retained sentence; subject context
        # cannot authorize a model's positive fragment or invented dose.
        notes = 'Denies cough.'
        _, answers = self.answers(notes, {'Symptoms': [notes]})
        self.assertNotEqual(answers['f1'].get('text'), 'cough')
        self.assertTrue(all(e['quote'] == notes for e in answers['f1']['evidence']))

    def test_two_original_voice_safety_controls_remain_blocked(self):
        retained=json.loads((Path(__file__).parent/'voice_first_pass_controls.json').read_text())
        notes=retained['notes']; fields=retained['fields']
        original=raw(notes,fields,retained['first_model_body'],g.SONNET_5_5)
        for context in [False,True]:
            if context:original['patient_default_context']=proof(notes)
            answers=r.validated(original)
            for key in retained['held_controls']:
                with self.subTest(context=context,key=key):
                    self.assertEqual((answers[key]['status'],answers[key]['text']),('conflict',''))
        # The model's exact original correction selection and planning line
        # remain adversarial controls, rather than newly simplified examples.

    def test_confirmation_does_not_tune_around_an_unresolved_parser_failure(self):
        # Pinned syntax still reads left as a past verb in this sentence. Retain
        # the first failed result; a clinician can edit and explicitly re-review.
        self.check('Reports left ankle pain.', 'Chief complaint', ['Reports left ankle pain.'], 'conflict')
        self.check('Mild swelling over the left ankle.', 'Examination', ['Mild swelling over the left ankle.'], 'conflict')

    def test_independent_refutation_ellipses_cannot_retract_a_patient_claim_silently(self):
        source='Takes warfarin 5 mg daily.'
        for tail,label in [('Only her father does.','Medications'),('Not today.','Medications taken today'),
                           ('Except today.','Medications taken today'),('Her father does not.','Medications'),
                           ('Not this week.','Medications taken this week'),
                           ('Only her father actually takes.','Medications'),
                           ('Only her father takes it.','Medications')]:
            with self.subTest(tail=tail):self.check(source+' '+tail,label,[source],'conflict')
        # A modifier before the first claim still cannot be declared independent.
        self.check('Not today. '+source,'Medications taken today',[source],'conflict')

    def test_elliptical_dependency_is_local_and_complete_other_person_claims_are_distinct(self):
        source='Takes warfarin 5 mg daily.'
        for tail in ['Her father takes apixaban.','Her father has diabetes.','Her father reports cough.']:
            with self.subTest(tail=tail):self.check(source+' '+tail,'Medications',[source])
        # The elliptical substitution points to the intervening cough statement;
        # it does not undo every earlier independent statement in the document.
        self.check(source+' Reports cough. Only her father does.','Medications',[source])
        self.check(source+' Reports cough. Only her father does.','Symptoms',['Reports cough.'],'conflict')

    @override_settings(V3_GENERATION_BATCHES=True)
    def test_whole_form_plan_keeps_context_in_request_digest_and_field_records(self):
        from core import generation_batch as b
        from .test_generation_batch import sample, manifest
        notes='Takes warfarin 5 mg daily. Reports cough.'
        e=sample(2,notes)
        e.template_version.fields[0]['label']='Medications'
        e.template_version.fields[1]['label']='Symptoms'
        e.template_version.generation_constraints=manifest(e.template_version.fields)
        config=g.configuration(e.template_version.fields)
        plan=b.plan_for(e,config,patient_context=proof(notes))
        payload=json.loads(b.request(plan,1)['messages'][0]['content'])
        self.assertEqual(payload['patient_default_context']['default_subject'],'encounter_patient')
        self.assertEqual(b.digest(b.request(plan,1)),plan['parts'][0]['request_sha256'])
        selected={e.template_version.fields[0]['key']:['Takes warfarin 5 mg daily.'],
                  e.template_version.fields[1]['key']:['Reports cough.']}
        output={'model':g.SONNET_5_5,'stop_reason':'end_turn','content':[{'type':'text',
                'text':json.dumps(relation_wire(notes,e.template_version.fields,selected))}]}
        answers,_=b.assemble(plan,[output])
        self.assertTrue(all(a['status']=='supported' for a in answers.values()))
        no_context=b.plan_for(e,config)
        self.assertNotEqual(b.digest(plan),b.digest(no_context))
        answers,_=b.assemble(no_context,[output])
        self.assertTrue(all(a['status']=='conflict' for a in answers.values()))
        plan['patient_default_context']='tampered'
        with self.assertRaises(ValidationError):b.request(plan,1)


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, STORAGES=STORAGES)
class ReviewVersion(BoundaryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = f'/encounters/{self.encounter.pk}/'

    def transcript(self, text='Takes warfarin 5 mg daily.'):
        with patch.dict(os.environ, self.VOICE_ENV):
            quote = self.client.get(self.url).context['usage_quote']
            response = self.client.post(self.url+'voice/', {'audio':SimpleUploadedFile('context.wav',wav_bytes(tag='context')),
                'consent':'on','usage_quote':quote})
            self.assertEqual(response.status_code,302)
            job = Job.objects.get(encounter=self.encounter)
            with patch('core.jobs.httpx.post', return_value=deepgram(text, 'synthetic-context-transcript', duration=1)):
                self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        return job

    def apply(self, job, text='Takes warfarin 5 mg daily.', **changes):
        self.encounter.refresh_from_db()
        return self.client.post(self.url+'notes/', {'revision': self.encounter.revision,
            'transcript_job': str(job.pk), 'corrected_transcript': text,
            'transcript_mode': 'append', 'transcript_reviewed': 'on',
            'transcript_patient_context': 'on', **changes})

    def test_raw_provider_and_clinician_edit_and_context_are_separate_evidence(self):
        job = self.transcript()
        original = self.encounter.notes
        result = private_path(job.result_path).read_bytes()
        corrected = 'Takes warfarin 4 mg daily.'
        self.assertEqual(self.apply(job, corrected).status_code, 302)
        self.encounter.refresh_from_db()
        review = TranscriptReview.objects.get(job=job)
        self.assertEqual(review.reviewed_text, corrected)
        self.assertEqual(review.raw_sha256, tc.digest('Takes warfarin 5 mg daily.'))
        self.assertEqual(review.reviewed_sha256, tc.digest(corrected))
        self.assertEqual(self.encounter.notes, original+'\n\n'+corrected)
        self.assertEqual(private_path(job.result_path).read_bytes(), result)
        self.assertTrue(tc.current(self.encounter))
        self.assertEqual(tc.payload(self.encounter.notes, tc.current(self.encounter))['start'], len(original)+2)
        event = AuditEvent.objects.get(action='transcription.applied', target=str(job.pk))
        self.assertNotIn(corrected, json.dumps(event.details))
        self.assertNotIn(review.context_token, json.dumps(event.details))
        self.assertEqual(Usage.objects.filter(job=job).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(job=job, kind='usage').count(), 1)
        self.assertEqual(self.apply(job).status_code, 409)

    def test_edit_revert_requires_new_explicit_review_without_retranscription(self):
        job = self.transcript()
        self.assertEqual(self.apply(job, transcript_mode='replace').status_code, 302)
        self.encounter.refresh_from_db(); notes = self.encounter.notes; token = tc.current(self.encounter)
        self.assertEqual(self.client.post(self.url+'notes/', {'revision': self.encounter.revision, 'notes': notes}).status_code, 302)
        self.encounter.refresh_from_db();self.assertEqual(tc.current(self.encounter), token)
        for edited in [notes+'\nReports cough.', notes]:
            self.assertEqual(self.client.post(self.url+'notes/', {'revision': self.encounter.revision, 'notes': edited}).status_code, 302)
            self.encounter.refresh_from_db();self.assertFalse(tc.current(self.encounter))
        usage = list(Usage.objects.values_list('id','actual_cost','charged_cost'))
        with patch('core.jobs.httpx.post') as provider:
            self.assertEqual(self.apply(job, notes, transcript_mode='replace', transcript_reconfirm='on').status_code, 302)
        provider.assert_not_called()
        self.encounter.refresh_from_db();self.assertTrue(tc.current(self.encounter))
        self.assertNotEqual(tc.current(self.encounter), token)
        self.assertEqual(TranscriptReview.objects.filter(job=job).count(), 2)
        self.assertEqual(list(Usage.objects.values_list('id','actual_cost','charged_cost')), usage)

    def test_employee_cannot_supply_clinician_context_and_failure_rolls_back(self):
        job = self.transcript()
        Membership.objects.filter(user=self.user, department=self.encounter.department).update(role='employee')
        previous = self.encounter.notes
        self.assertEqual(self.apply(job).status_code, 403)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.notes, previous)
        self.assertFalse(TranscriptReview.objects.exists())
        self.assertEqual(self.apply(job, transcript_patient_context='').status_code, 302)
        self.encounter.refresh_from_db();self.assertFalse(tc.current(self.encounter))
        self.assertFalse(TranscriptReview.objects.get().patient_context)

    def test_database_append_only_guard_cannot_be_bypassed_by_queryset(self):
        job = self.transcript();self.assertEqual(self.apply(job).status_code, 302)
        review = TranscriptReview.objects.get(job=job)
        with self.assertRaises(ValidationError):review.save()
        for operation in [lambda:TranscriptReview.objects.filter(pk=review.pk).update(reviewed_text='Lost evidence'),
                          lambda:TranscriptReview.objects.filter(pk=review.pk).delete()]:
            with self.assertRaises(DatabaseError), transaction.atomic():operation()
        review.refresh_from_db();self.assertEqual(review.reviewed_text, 'Takes warfarin 5 mg daily.')

    def test_database_refuses_review_of_a_different_source_span_before_retaining_it(self):
        job=self.transcript()
        source=self.encounter.notes
        for changes in [dict(reviewed_text='Another synthetic value'),dict(span_end=len(source)+1),
                        dict(source_revision=self.encounter.revision+1)]:
            values={'encounter':self.encounter,'job':job,'reviewed_by':self.user,
                'source_revision':self.encounter.revision,'source_sha256':tc.digest(source),
                'raw_sha256':tc.digest('Takes warfarin 5 mg daily.'),'result_sha256':job.result_sha256,
                'reviewed_sha256':tc.digest(source),'reviewed_text':source,'span_start':0,'span_end':len(source)}
            values.update(changes)
            with self.subTest(changes=changes),self.assertRaises(DatabaseError),transaction.atomic():
                TranscriptReview.objects.create(**values)
        self.assertFalse(TranscriptReview.objects.exists())
        self.assertEqual(self.apply(job).status_code,302)

    @override_settings(**SONNET_55_DEFAULT)
    def test_job_admission_only_uses_current_server_review_on_default_sonnet_route(self):
        job = self.transcript();self.assertEqual(self.apply(job).status_code, 302)
        self.encounter.refresh_from_db()
        config = g.configuration(form('Medications'))
        self.assertEqual(config['ordinary_field_contract'], r.CONTRACT)
        admitted = tc.admitted({**config,'patient_default_context':'forged'}, self.encounter)
        self.assertEqual(admitted['patient_default_context'], tc.current(self.encounter))
        self.assertNotIn('patient_default_context', tc.admitted({'patient_default_context':'forged'}, self.encounter))
        fields = form('Medications'); request = r.compile_request(self.encounter.notes, fields, admitted)
        payload=json.loads(request['wire']['messages'][0]['content'])
        self.assertEqual(payload['patient_default_context']['default_subject'], 'encounter_patient')
        self.assertNotIn(tc.current(self.encounter), json.dumps(payload))


@override_settings(**dict(V3,**SONNET_55_DEFAULT))
class VoiceToWord(V3Fixture, TestCase):
    """Actual HTTP/worker/Word export with mocked providers; live calls are a separate gate."""
    def test_reviewed_subjectless_transcript_reaches_default_doctor_generation_and_export(self):
        doc=Document();doc.add_paragraph('Medications: ____________');doc.add_paragraph('Symptoms: ____________')
        buffer=io.BytesIO();doc.save(buffer)
        template,version=self.uploaded(data=buffer.getvalue(),name='Synthetic subjectless voice')
        self.confirm(template,version)
        self.assertEqual(self.new_encounter(version,notes='').status_code,302)
        encounter=Encounter.objects.get(template_version=version)
        url=f'/encounters/{encounter.pk}/'
        with patch.dict(os.environ,BoundaryFixture.VOICE_ENV):
            quote=self.client.get(url).context['usage_quote']
            response=self.client.post(url+'voice/',{'audio':SimpleUploadedFile('synthetic.wav',wav_bytes(tag='scope')),
                'consent':'on','usage_quote':quote})
            self.assertEqual(response.status_code,302)
            with patch('core.jobs.httpx.post',return_value=deepgram('Takes warfarin 5 mg daily. Reports cough.',
                'synthetic-reviewed-voice',duration=1)):self.assertTrue(run_one())
        voice=Job.objects.get(kind='transcription',encounter=encounter)
        voice.refresh_from_db();self.assertEqual(voice.state,'succeeded',voice.error)
        raw_bytes=private_path(voice.result_path).read_bytes()
        self.assertContains(self.client.get(url),'Statements with no subject in this reviewed transcript are about this patient.')
        encounter.refresh_from_db()
        self.assertEqual(self.client.post(url+'notes/',{'revision':encounter.revision,'transcript_job':voice.pk,
            'corrected_transcript':'Takes warfarin 5 mg daily. Reports cough.','transcript_mode':'replace',
            'transcript_reviewed':'on','transcript_patient_context':'on'}).status_code,302)
        encounter.refresh_from_db()
        page=self.client.get(url);self.assertContains(page,'data-patient-context-current')
        self.assertEqual(self.client.post(url+'generate/',{'revision':encounter.revision,
            'usage_quote':page.context['usage_quote']}).status_code,302)
        generation=Job.objects.get(kind='generation',encounter=encounter)
        self.assertEqual(generation.config['patient_default_context'],tc.current(encounter))
        sent=[]
        def reply(**request):
            sent.append(request);payload=json.loads(request['messages'][0]['content'])
            self.assertEqual(payload['patient_default_context']['default_subject'],'encounter_patient')
            picks={f['key']:['Takes warfarin 5 mg daily.' if f['label']=='Medications' else 'Reports cough.']
                   for f in version.fields}
            body=json.dumps(relation_wire(encounter.notes,version.fields,picks))
            return SimpleNamespace(model=g.SONNET_5_5,stop_reason='end_turn',content=[SimpleNamespace(type='text',text=body)],
                id='msg_synthetic_reviewed_voice',_request_id='req_synthetic_reviewed_voice',
                usage=SimpleNamespace(input_tokens=100,output_tokens=20,cache_read_input_tokens=0,cache_creation_input_tokens=0),
                model_dump=lambda **kwargs:{'id':'msg_synthetic_reviewed_voice','text':body})
        with patch('anthropic.Anthropic',return_value=SimpleNamespace(messages=SimpleNamespace(create=reply))):
            self.assertTrue(run_one())
        generation.refresh_from_db();self.assertEqual(generation.state,'succeeded',generation.error)
        self.assertEqual(len(sent),1)
        encounter.refresh_from_db()
        self.assertEqual([encounter.answers[f['key']]['status'] for f in version.fields],['supported','supported'])
        self.assertEqual(Usage.objects.filter(job=voice).count(),1)
        self.assertEqual(Usage.objects.filter(job=generation).count(),1)
        payload={'revision':encounter.revision}
        for field in version.fields:
            payload['answer_'+field['key']]=encounter.answers[field['key']]['text']
            payload['reviewed_'+field['key']]='on'
        self.assertEqual(self.client.post(url+'save/',payload).status_code,302)
        encounter.refresh_from_db();self.assertTrue(tc.current(encounter))
        self.assertEqual(self.client.post(url+'finalize/',{'revision':encounter.revision,'reviewed':'on'}).status_code,302)
        encounter.refresh_from_db();self.assertEqual(encounter.status,'finalized')
        export=self.client.get(url+'export/');self.assertEqual(export.status_code,200)
        text=part_text(b''.join(export.streaming_content))
        self.assertIn('Takes warfarin 5 mg daily.',text);self.assertIn('Reports cough.',text)
        self.assertEqual(private_path(voice.result_path).read_bytes(),raw_bytes)
