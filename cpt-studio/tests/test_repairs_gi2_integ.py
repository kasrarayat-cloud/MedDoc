"""Integrator repairs of the GI round 2 (session 7c8d38da): defects the repair agents found outside their own scope.
Synthetic data only; the provider is an in-process fake."""
from django.test import TestCase, override_settings

from studio import models
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE, ApiHarness


@override_settings(**LIVE)
class RepeatedResumeTests(ApiHarness, TestCase):
    """sends known limit 'third Resume': every Resume appended 44 characters to the previous key, so the third or fourth
    Stop/Resume in a row overflowed Job.idempotency_key (200 characters) with an HTTP 500 and nothing recorded."""

    def test_six_stop_resume_rounds_each_resume_and_the_document_finishes(self):
        encounter_id = self.create()
        for round_number in range(6):
            stop = self.client.post(f'/api/encounters/{encounter_id}/stop')
            self.assertEqual(stop.status_code, 200, (round_number, stop.content))
            drain()
            resume = self.client.post(f'/api/encounters/{encounter_id}/resume')
            self.assertEqual(resume.status_code, 201, (round_number, resume.content))
        drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')
        keys = list(models.Job.objects.filter(encounter_id=encounter_id).values_list('idempotency_key', flat=True))
        resumed = [key for key in keys if ':resume:' in key]
        self.assertGreaterEqual(len(resumed), 6)
        self.assertTrue(all(key.count(':resume:') == 1 for key in resumed), resumed)
        self.assertLessEqual(max(len(key) for key in keys), 200)
        self.assertEqual(len(self.provider.sent), 1)


class OneSubActReadPerSentenceTests(TestCase):
    """gi2 integration, cost (negation repair's must-fix concern): every status reference in one sentence re-read the
    whole sentence for its sub-act question, so one pasted line repeating "The procedure was not aborted," passed the
    analyze stage's 60 s at 8,000 repetitions (60.3 s at 2b82889f). The answer is read once per family and sentence."""

    def test_a_line_of_repeated_status_references_reads_its_sentence_once(self):
        from datetime import date
        from unittest import mock

        from studio.gi import detect
        head = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nColonoscopy Report\nDate of procedure: 2026-10-19\n'
                'Procedure: Colonoscopy.\n\nDescription\nThe colonoscope was advanced to the cecum.\n\nFindings\n')
        text = head + 'The procedure was not aborted, ' * 300 + 'and the terminal ileum was not intubated.\n'
        real = detect._only_a_sub_act_read
        calls = []

        def counted(an, attributed, family, s, e):
            calls.append((family, s, e))
            return real(an, attributed, family, s, e)

        with mock.patch.object(detect, '_only_a_sub_act_read', side_effect=counted):
            routed = detect.route(text, date(2026, 10, 19))
        self.assertTrue(calls)
        self.assertEqual(len(calls), len(set(calls)), 'a sentence was read again for the same family')
        self.assertEqual(routed, detect.route(text, date(2026, 10, 19)))
