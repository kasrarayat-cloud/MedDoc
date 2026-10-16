"""Retained synthetic response through durable coding, no provider calls."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import coding_service as service, corti_prediction as provider, corti_coding
from core.coding_terminology import parse_reference, reference_digest
from core.models import Code, CodeSet, CodingRelease, CodingContext, CodingDecision, CodingRun, Department, Encounter, Membership, Organization, Patient, Template, TemplateVersion, User

FIXTURES = Path(__file__).parent / 'fixtures/corti'
REQUEST = json.loads((FIXTURES / 'request.json').read_text())
RAW = (FIXTURES / 'response.raw.json').read_text()
FIXTURE = {'request': REQUEST, 'response_raw': RAW, 'response_sha256': hashlib.sha256(RAW.encode()).hexdigest(),
           'original_verdict': 'FAIL_RESPONSE_QUALITY_WITH_SELECTED_CODES_PASS'}
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


class CortiClinicalBoundaryTests(SimpleTestCase):
    def test_integral_symptom_uses_existing_cross_concept_veto(self):
        notes='Assessment: reflux causes heartburn.'
        rows=[{'id':key,'eligible':True,'concept':{'id':key,'kind':kind,'term':term,'index_terms':[term],
            'evidence':notes}} for key,kind,term in [('symptom','symptom','heartburn'),('disease','diagnosis','reflux')]]
        self.assertEqual(corti_coding.integral_holds(rows,notes),{'symptom':'disease'})
        self.assertEqual(corti_coding.integral_holds(rows,'Assessment: heartburn; reflux is not established.'),{})
        self.assertEqual(corti_coding.integral_holds(rows[:1],notes),{'symptom':'source-causal-wording'})
        rows[1]['eligible']=False
        self.assertEqual(corti_coding.integral_holds(rows,notes),{'symptom':'source-causal-wording'})
        self.assertEqual(corti_coding.integral_holds(rows[:1],'Assessment: heartburn due to reflux.'),{'symptom':'source-causal-wording'})

    @override_settings(SYNTHETIC_ONLY=True)
    def test_generic_source_identity_does_not_fill_from_registry(self):
        from types import SimpleNamespace
        run=SimpleNamespace(inputs={'notes':REQUEST['context'][0]['text'], 'patient_identity':{'display_name':'Synthetic Different Patient'},
            'patient_name_answers':[]},context={})
        self.assertTrue(corti_coding.identity_blockers(run))
        run.inputs['patient_identity']['display_name']='Synthetic Taylor Reed'
        self.assertEqual(corti_coding.identity_blockers(run),[])
        run.inputs['notes'] += ' Patient name: Synthetic Morgan Lane.'
        self.assertTrue(corti_coding.identity_blockers(run))
        run.inputs['notes']='Patient name: Synthetic Taylor Reed. Assessment: heartburn.'
        self.assertEqual(corti_coding.identity_blockers(run),[])
        run.inputs['notes']='Patient reports heartburn.'
        self.assertTrue(corti_coding.identity_blockers(run))
        run.inputs['notes']="Synthetic Taylor Reed, age 44, attends her patient's office visit. The patient reports heartburn."
        self.assertTrue(corti_coding.identity_blockers(run))


@override_settings(CODING_PROVIDER='corti', CORTI_CODING_MODE='replay', CODING_ALLOW_TEST_FIXTURES=True,
                   CORTI_REPLAY_FIXTURE=FIXTURE, SYNTHETIC_ONLY=True, ADMIN_SITE=False, STORAGES=STORAGES,
                   CPT_ENTITLEMENT_MANIFEST='/missing-corti-test-entitlement.json')
class CortiWorkflowTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(id='2247e403-a830-4807-9a34-6903b95a0f50',
            username='corti-clinician', email='corti@synthetic.invalid', verified_at=timezone.now())
        org = Organization.objects.create(name='Synthetic Corti tests')
        self.department = Department.objects.create(id='46a5abdd-36f1-41f0-968f-8c09c39d9daa', organization=org, name='Synthetic GI')
        Membership.objects.create(user=self.actor, department=self.department, role='clinician')
        patient = Patient.objects.create(department=self.department, display_name='Synthetic Taylor Reed', created_by=self.actor)
        template = Template.objects.create(department=self.department, name='Synthetic note', format='docx',
            original_name='synthetic.docx', original_path='fixture.docx', sha256='a'*64, created_by=self.actor)
        version = TemplateVersion.objects.create(template=template, number=1, fields=[{'key':'note','label':'Clinical note'}], created_by=self.actor)
        self.encounter = Encounter.objects.create(department=self.department, patient=patient, template_version=version,
            created_by=self.actor, notes=REQUEST['context'][0]['text'], answers={'note': {'text': REQUEST['context'][0]['text']}},
            status='review', revision=2, service_date=date(2026, 10, 16))
        CodingContext.objects.create(encounter=self.encounter, updated_by=self.actor,
            data={**service.CONTEXT_DEFAULTS, 'setting':'outpatient_office'})
        # Deliberately tiny unit reference, not evidence of an installed official
        # release. The candidate acceptance separately imports the complete FY27 files.
        self.release = CodeSet.objects.create(system='ICD-10-CM', version='SYNTHETIC-UNIT-FY2027',
            effective_from=date(2026,10,1), effective_until=date(2027,9,30), sha256='b'*64,
            source_url='https://www.cms.gov/synthetic-unit-reference')
        rows = {'R12':'Heartburn', 'K59.00':'Constipation, unspecified'}
        for code, description in rows.items(): Code.objects.create(release=self.release, code=code, description=description)
        parsed = parse_reference('''<ICD10CM.index><version>2027</version><letter>
            <mainTerm><title>Heartburn</title><code>R12</code></mainTerm>
            <mainTerm><title>Constipation</title><code>K59.00</code></mainTerm>
            </letter></ICD10CM.index>''', '''<ICD10CM.tabular><version>2027</version><chapter><name>unit</name>
            <section id="unit"><diag><name>R12</name><desc>Heartburn</desc></diag>
            <diag><name>K59.00</name><desc>Constipation, unspecified</desc></diag></section></chapter></ICD10CM.tabular>''', rows)
        CodingRelease.objects.create(release=self.release, index=parsed['index'], tabular=parsed['tabular'], digest=reference_digest(parsed))
        self.client.force_login(self.actor)
        self.network = patch('core.corti_prediction._session', side_effect=AssertionError('Network prohibited'))
        self.send = self.network.start(); self.addCleanup(self.network.stop)

    def complete(self):
        run = service.ensure_run(self.encounter, self.actor)
        self.assertTrue(service.run_one()); run.refresh_from_db()
        self.assertIn(run.state, ('succeeded', 'needs_detail'), run.error)
        return run

    def test_retained_selection_seven_spans_and_raw_failure_preserved(self):
        run = self.complete()
        self.assertEqual([r['code'] for r in run.result['suggestions']], ['R12','K59.00','99213'])
        self.assertEqual(sum(len(r['evidence_spans']) for r in run.result['suggestions']), 7)
        self.assertEqual([r['eligible'] for r in run.result['suggestions']], [True,True,False])
        self.assertEqual(run.requests[0]['raw_response']['body'], RAW)
        self.assertFalse(run.requests[0]['sent']); self.assertTrue(run.requests[0]['simulated'])
        self.assertEqual(run.requests[0]['response_sha256'], FIXTURE['response_sha256'])
        self.assertEqual(run.result['original_verdict'], FIXTURE['original_verdict'])
        self.assertEqual(run.result['diagnostics_summary']['candidate_count'],11)
        self.assertEqual(run.result['diagnostics_summary']['alternative_count'],5)
        self.assertEqual(run.result['suggestions'][2]['provider_display'], '+PR OFFICE OUTPATIENT VISIT 15 MINUTES')
        self.assertEqual(run.result['suggestions'][2]['description'],'')
        html = self.client.get(f'/encounters/{self.encounter.pk}/coding/status/', HTTP_ACCEPT='application/json').json()['html']
        self.assertEqual(html.count('data-corti-evidence'),7)
        self.assertIn('Synthetic replay.', html); self.assertIn('Held — cannot accept or export', html)
        self.send.assert_not_called()

    def test_only_selected_eligible_codes_can_be_accepted(self):
        run = self.complete()
        for ids, overrides in [(['selected:2'],{}), (['candidate:0'],{}),
                (['selected:0'],{'selected:0':{'code':'K21.9','reason':'Candidate is not authority'}}),
                (['selected:0','selected:0'],{})]:
            with self.assertRaises(ValidationError):
                service.update_selection(run,self.actor,{'selected_ids':ids,'overrides':overrides},run.selection_revision)
        run = service.update_selection(run,self.actor,{'selected_ids':['selected:0'],'overrides':{}},run.selection_revision)
        decision = service.approve(run,self.actor,run.input_digest,service.selection_digest(run))
        self.assertEqual(decision.selections['selected_ids'],['selected:0'])
        self.assertEqual(service.snapshot(self.encounter,self.actor)['summary']['approved'],1)
        self.assertFalse(run.result['suggestions'][2]['eligible'])

    def test_duplicate_request_and_worker_cannot_resubmit(self):
        run = self.complete()
        for _ in range(3):
            self.assertEqual(service.ensure_run(self.encounter,self.actor).pk,run.pk)
            self.assertFalse(service.run_one())
        self.assertEqual(len(run.requests),1)
        with self.assertRaises(ValidationError): provider.execute(run,REQUEST)
        self.send.assert_not_called()

    def test_revision_changes_refuse_stale_approval(self):
        run = self.complete(); token = service.snapshot(self.encounter,self.actor)['display_token']
        self.encounter.revision += 1; self.encounter.save(update_fields=['revision'])
        with self.assertRaises(ValidationError):
            service.approve(run,self.actor,run.input_digest,service.selection_digest(run))
        with self.assertRaises(ValidationError): service.verify_display(self.encounter,self.actor,token,run)
        self.assertEqual(CodingDecision.objects.count(),0)

    def test_patient_separation_and_tenant_denial(self):
        first = self.complete()
        other = Patient.objects.create(department=self.department,display_name='Synthetic Different Patient',reference='different',created_by=self.actor)
        second = Encounter.objects.create(department=self.department,patient=other,template_version=self.encounter.template_version,
            created_by=self.actor,notes=self.encounter.notes,answers=self.encounter.answers,status='review',revision=2,service_date=self.encounter.service_date)
        self.assertNotEqual(service.input_snapshot(second)[3], first.input_digest)
        self.assertIsNone(service.snapshot(second,self.actor)['decision'])
        CodingContext.objects.create(encounter=second,updated_by=self.actor,data={**service.CONTEXT_DEFAULTS,'setting':'outpatient_office'})
        wrong=service.ensure_run(second,self.actor);service.run_one();wrong.refresh_from_db()
        self.assertTrue(wrong.result['global_blockers'])
        with self.assertRaises(ValidationError): service.approve(wrong,self.actor,wrong.input_digest,service.selection_digest(wrong))
        outsider = User.objects.create_user(username='outside',email='outside@synthetic.invalid',verified_at=timezone.now())
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f'/encounters/{self.encounter.pk}/coding/status/').status_code,404)

    def test_missing_evidence_unknown_code_and_unavailable_release_stay_held(self):
        mutations = [lambda r:r['codes'][0].update(evidences=[]),
                     lambda r:r['codes'][0].update(code='R99'),
                     lambda r:r['codes'][0].update(evidences=[{'contextIndex':0,'start':0,'end':5,'text':'wrong'}])]
        for change in mutations:
            raw=json.loads(RAW);change(raw);text=json.dumps(raw)
            fixture={**FIXTURE,'response_raw':text,'response_sha256':hashlib.sha256(text.encode()).hexdigest()}
            self.encounter.revision+=1;self.encounter.save(update_fields=['revision'])
            with override_settings(CORTI_REPLAY_FIXTURE=fixture):
                run=self.complete()
                self.assertFalse(run.result['suggestions'][0]['eligible'])
                with self.assertRaises(ValidationError): corti_coding.validate_selection(run,{'selected_ids':['selected:0'],'overrides':{}})
        self.encounter.service_date=date(2028,1,1);self.encounter.save(update_fields=['service_date'])
        run=service.ensure_run(self.encounter,self.actor)
        self.assertEqual(run.error_code,'terminology_unavailable');self.assertEqual(run.requests,[])

    def test_dotless_icd_and_unselected_diagnostic_injection(self):
        raw=json.loads(RAW);raw['codes'][1]['code']='K5900'
        raw['candidates'].append({'system':'icd10cm-outpatient','code':'Z99.9','display':'Do not promote'})
        raw['codes'][0]['alternatives'].append({'code':'Z99.8','display':'Do not promote'})
        text=json.dumps(raw)
        with override_settings(CORTI_REPLAY_FIXTURE={**FIXTURE,'response_raw':text,'response_sha256':hashlib.sha256(text.encode()).hexdigest()}):
            run=self.complete()
        self.assertEqual([r['code'] for r in run.result['suggestions']],['R12','K59.00','99213'])

    def test_replay_refuses_changed_note_and_production_database_gate(self):
        self.encounter.notes+=' Changed source.';self.encounter.save(update_fields=['notes'])
        run=service.ensure_run(self.encounter,self.actor);service.run_one();run.refresh_from_db()
        self.assertEqual(run.state,'failed');self.assertEqual(run.requests,[])
        with override_settings(CODING_ALLOW_TEST_FIXTURES=False), self.assertRaises(ValidationError):
            provider.configuration(self.actor,self.encounter)

    def test_mocked_live_transport_sends_exactly_one_prediction_no_agent_or_retry(self):
        session=MagicMock();session.__enter__.return_value=session
        auth=MagicMock(status_code=200);auth.json.return_value={'access_token':'synthetic-token'}
        response=MagicMock(status_code=200);response.__enter__.return_value=response
        response.iter_content.return_value=[b'{"codes":[],"usageInfo":{"creditsConsumed":0.01}}']
        session.post.side_effect=[auth,response]
        with override_settings(CORTI_CODING_MODE='live'), \
             patch.object(provider,'_session',return_value=session), \
             patch.object(provider,'_credentials',return_value=('us','base','synthetic-client','synthetic-secret')), \
             patch('core.testing_authority.enabled',return_value=True):
            run=service.ensure_run(self.encounter,self.actor)
            service.run_one();run.refresh_from_db()
            self.assertEqual(len(run.requests),1)
            self.assertEqual(run.requests[0]['state'],'succeeded')
            self.assertIsNone(run.actual_cost)  # Credits are not a dollar invoice.
            self.assertEqual(session.post.call_count,2)
            auth_call, coding_call=session.post.call_args_list
            self.assertEqual(auth_call.args[0],'https://auth.us.corti.app/realms/base/protocol/openid-connect/token')
            self.assertEqual(coding_call.args[0],'https://api.us.corti.app/v2/tools/coding/')
            self.assertFalse(coding_call.kwargs['allow_redirects'])
            self.assertEqual(json.loads(coding_call.kwargs['data'])['system'],['icd10cm-outpatient','cpt'])
            self.assertEqual(run.config['coding_purpose'],provider.PURPOSE)
            self.assertEqual(service.ensure_run(self.encounter,self.actor).pk,run.pk)
            self.assertFalse(service.run_one());self.assertEqual(session.post.call_count,2)
            self.assertNotIn('synthetic-secret',json.dumps(run.requests))
            self.assertNotIn('synthetic-token',json.dumps(run.requests))

    def test_mocked_timeout_keeps_unknown_attempt_and_never_resends(self):
        import requests
        session=MagicMock();session.__enter__.return_value=session
        auth=MagicMock(status_code=200);auth.json.return_value={'access_token':'synthetic-token'}
        session.post.side_effect=[auth,requests.Timeout('untrusted transport secret')]
        with override_settings(CORTI_CODING_MODE='live'), \
             patch.object(provider,'_session',return_value=session), \
             patch.object(provider,'_credentials',return_value=('us','base','synthetic-client','synthetic-secret')), \
             patch('core.testing_authority.enabled',return_value=True):
            run=service.ensure_run(self.encounter,self.actor);service.run_one();run.refresh_from_db()
            self.assertEqual(run.state,'uncertain');self.assertIsNone(run.actual_cost)
            self.assertEqual(run.requests[0]['state'],'unknown')
            self.assertEqual(service.ensure_run(self.encounter,self.actor).pk,run.pk)
            self.assertFalse(service.run_one());self.assertEqual(session.post.call_count,2)
            self.assertNotIn('untrusted transport secret',run.error)

    def test_transport_disables_automatic_retries_and_environment_proxy(self):
        # Construct only; this does not send a network request.
        self.network.stop()
        with provider._session() as session:
            self.assertEqual(session.get_adapter('https://api.us.corti.app').max_retries.total,0)
            self.assertFalse(session.trust_env)
