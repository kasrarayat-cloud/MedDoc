"""Prospective synthetic admission does not relabel historical coding work."""
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from core import coding_dispatch as dispatch, coding_service as service, coding_engine, corti_coding
from core.models import CodingContext, CodingRun
from core.tests.test_corti_workflow import CortiWorkflowTests, FIXTURE, STORAGES


@override_settings(CODING_PROVIDER='existing', CORTI_CODING_MODE='replay',
    CORTI_REPLAY_FIXTURE=FIXTURE, CODING_ALLOW_TEST_FIXTURES=True, SYNTHETIC_ONLY=True,
    ADMIN_SITE=False, STORAGES=STORAGES, CPT_ENTITLEMENT_MANIFEST='/missing-test-entitlement.json')
class ProspectiveCortiAdmissionTests(TestCase):
    setUp = CortiWorkflowTests.setUp

    def admission(self, **overrides):
        return override_settings(CORTI_NEW_ENCOUNTERS_SINCE=(timezone.now()-timedelta(days=1)).isoformat(),
            CORTI_NEW_ENCOUNTER_ACTORS=(str(self.actor.pk),), **overrides)

    def test_existing_run_retains_engine_and_digest_after_admission(self):
        before = service.input_snapshot(self.encounter)
        run = CodingRun.objects.create(encounter=self.encounter, user=self.actor,
            input_digest=before[3], inputs=before[0], context=before[1], releases=before[2],
            config={'provider':'anthropic'}, state='needs_detail')
        with self.admission():
            self.assertEqual(dispatch.provider(self.encounter), 'existing')
            self.assertEqual(dispatch.contract(self.encounter), coding_engine.CONTRACT)
            self.assertEqual(service.input_snapshot(self.encounter), before)
            self.assertEqual(service.ensure_run(self.encounter,self.actor).pk,run.pk)
        self.send.assert_not_called()

    def test_new_eligible_encounter_pins_corti_once_and_does_not_attest_time(self):
        CodingContext.objects.filter(encounter=self.encounter).delete()
        with self.admission():
            self.assertEqual(dispatch.provider(self.encounter), 'corti')
            context=service.context_data(self.encounter)
            self.assertEqual(context['setting'],'outpatient_office')
            self.assertEqual(context['patient_status'],'established')
            self.assertFalse(context['time_qualified_clinician'])
            self.assertFalse(context['time_same_day'])
            self.assertFalse(context['time_excludes_separately_reported'])
            run=service.ensure_run(self.encounter,self.actor)
            self.assertEqual(run.inputs['engine_contract'],corti_coding.CONTRACT)
            self.assertEqual(run.config['provider'],'corti')
            self.assertEqual(service.ensure_run(self.encounter,self.actor).pk,run.pk)
        # Removing admission does not alter the historical result's input binding.
        self.assertEqual(dispatch.provider(self.encounter),'corti')
        self.assertEqual(service.input_snapshot(self.encounter)[3],run.input_digest)
        self.assertEqual(CodingRun.objects.filter(encounter=self.encounter).count(),1)
        self.send.assert_not_called()

    def test_other_actors_older_encounters_and_real_patient_mode_are_not_admitted(self):
        with override_settings(CORTI_NEW_ENCOUNTERS_SINCE=(timezone.now()-timedelta(days=1)).isoformat(),
                CORTI_NEW_ENCOUNTER_ACTORS=('another-actor',)):
            self.assertEqual(dispatch.provider(self.encounter),'existing')
        with override_settings(CORTI_NEW_ENCOUNTERS_SINCE=(timezone.now()+timedelta(days=1)).isoformat(),
                CORTI_NEW_ENCOUNTER_ACTORS=(str(self.actor.pk),)):
            self.assertEqual(dispatch.provider(self.encounter),'existing')
        with self.admission(SYNTHETIC_ONLY=False):
            self.assertEqual(dispatch.provider(self.encounter),'existing')

    def test_undocumented_time_does_not_supply_context_or_confirmation(self):
        CodingContext.objects.filter(encounter=self.encounter).delete()
        self.encounter.notes='Patient name: Synthetic Taylor Reed. Symptoms lasted 25 minutes.'
        with self.admission():
            self.assertEqual(service.context_data(self.encounter),service.CONTEXT_DEFAULTS)

    def test_historical_corti_without_context_retains_its_defaults_and_digest(self):
        CodingContext.objects.filter(encounter=self.encounter).delete()
        with override_settings(CODING_PROVIDER='corti'):
            before=service.input_snapshot(self.encounter)
        self.assertEqual(before[1],service.CONTEXT_DEFAULTS)
        CodingRun.objects.create(encounter=self.encounter,user=self.actor,input_digest=before[3],
            inputs=before[0],context=before[1],releases=before[2],config={'provider':'corti','mode':'live'},state='needs_detail')
        with self.admission():
            self.assertEqual(dispatch.provider(self.encounter),'corti')
            self.assertFalse(dispatch.source_context_enabled(self.encounter))
            self.assertEqual(service.input_snapshot(self.encounter),before)

    def test_direct_payload_preserves_original_source_and_does_not_repeat_generated_answers(self):
        from types import SimpleNamespace
        from core.corti_prediction import payload
        run=SimpleNamespace(config={'mode':'live'},inputs={'notes':self.encounter.notes,
            'service_date':'2026-10-16','answers':{'derived':{'text':'Generated wording is not source'}}})
        request=payload(run)
        self.assertEqual(request,{'system':['icd10cm-outpatient','cpt'],
            'context':[{'type':'text','text':self.encounter.notes},{'type':'text','text':'Date of service: 2026-10-16'}]})
