"""Integrator repairs of the GI round 2 (session 7c8d38da): defects the repair agents found outside their own scope.
Synthetic data only; the provider is an in-process fake."""
from django.test import TestCase, override_settings

from studio import models
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_ec5_reportfacts import browser
from tests.test_repairs_gi2_present import LETTER, NO_PLACE, UNDATED, VISIT_TIME
from tests.test_repairs_gi2_present import Harness as PresentHarness
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


@override_settings(**LIVE)
class ListedDateQuotesTheKeptEvidenceTests(PresentHarness):
    """gi2 integration (present's open must-fix concern, occurrence RC5): the documents/queue list's SERVICE DATE cell
    and the overview card said "Not documented" for a date the reader kept as evidence and asks, while the review page
    and the checks quote it."""

    def run_documents(self, text):
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(text)
        drain()
        row = self.row(encounter_id)
        shown = browser('{row: app.documentRow(data.row), invite: app.inviteMarkup([data.row])}', {'row': row})
        return row, shown

    def test_a_kept_date_is_quoted_in_the_list_and_on_the_overview(self):
        row, shown = self.run_documents(LETTER)
        self.assertEqual(row['service_date_evidence'], 'Date: 10/27/2026')
        self.assertIn('Not read: “Date: 10/27/2026”', shown['row'])
        self.assertIn('service date not read: “Date: 10/27/2026”', shown['invite'])
        self.assertNotIn('ot documented', shown['row'] + shown['invite'])

    def test_control_nothing_stated_stays_not_documented_and_a_documented_date_is_the_date(self):
        row, shown = self.run_documents(UNDATED)
        self.assertEqual(row['service_date_evidence'], '')
        self.assertIn('Not documented', shown['row'])
        self.assertIn('service date not documented', shown['invite'])
        row, shown = self.run_documents(NO_PLACE)
        self.assertEqual((row['service_date'], row['service_date_evidence']), ('2026-10-20', ''))
        self.assertNotIn('Not read', shown['row'])


class EmTimeReadOncePerSentenceTests(TestCase):
    """gi2 integration, cost (the dates fix agent's pre-existing report): every E/M time statement re-read its whole
    sentence for "this time is not E/M time", so one pasted line of 7,500 "Total time on the date of service: 34
    minutes;" statements - one sentence - took 60.1 s to route at 2b82889f (the analyze stage's limit is 60 s)."""

    def test_a_sentence_is_searched_once_for_not_em_time(self):
        from datetime import date
        from unittest import mock

        from studio.gi import cues, detect
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nGastroenterology Office Visit\nDate of service: 2026-10-22\n'
                'Assessment\nChronic constipation.\n' + 'Total time on the date of service: 34 minutes; ' * 200 + '\n')
        real = cues.NOT_EM_TIME
        searched = []

        class Counting:
            def search(self, string, *span):
                searched.append(span)
                return real.search(string, *span)

        with mock.patch.object(cues, 'NOT_EM_TIME', Counting()):
            routed = detect.route(text, date(2026, 10, 22))
        self.assertTrue(searched)
        self.assertEqual(len(searched), len(set(searched)), 'a sentence was searched again')
        self.assertEqual(routed, detect.route(text, date(2026, 10, 22)))


class ExtentValueDepthIsLinearTests(TestCase):
    """gi2 integration, cost (refutation gi2 ops; ACCURACY-RESIDUALS gi2 cost-extent-blanks): the depth an extent label's
    value may open with began with two plain blank runs around an optional comma or bracket, so a run of blanks before no
    depth was tried at every split - quadratic per label (1,289 blank-padded labels routed 56.8-57.6 s against the
    installed 44 s). The runs are possessive; every match keeps its span."""

    def test_a_long_blank_run_is_read_at_once_and_spans_are_unchanged(self):
        import re
        import time

        from studio.gi import cues
        start = time.perf_counter()
        self.assertIsNone(cues.EXTENT_VALUE_DEPTH.match(' ' * 20000 + 'x'))
        self.assertLess(time.perf_counter() - start, 2.0)  # the plain runs took about 20 s here
        plain = re.compile(cues.EXTENT_VALUE_DEPTH.pattern.replace('*+', '*'), cues.EXTENT_VALUE_DEPTH.flags)
        for value in (' at 28 cm', ' (35 cm)', ', 28 cm from the anal verge', ' - 85 cm', '   ,   to approximately 40 cm',
                      '\tat ~30cm', ' x', '', '  ', ' at 7 minutes', ' — 85 cm', ' about 30 cm from the incisors'):
            with self.subTest(value=value):
                ours, theirs = cues.EXTENT_VALUE_DEPTH.match(value), plain.match(value)
                self.assertEqual(ours and ours.span(), theirs and theirs.span())
