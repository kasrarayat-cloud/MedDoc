"""FINAL-V2 amendment 1 (docs/gemini-migration/AMENDMENT-1.md, adopted as DECISIONS D208), section 8: the exports - step
5d's half (studio/reports.py, studio/api.py create_report and download_report). TEXT-ONLY and SYNTHETIC: the v2 and
legacy fixtures of tests/v2/test_update_pipeline.py (design v2's own InterpreterV2 with its one exchange answered there,
the in-process Corti, the installed release's own chain for the legacy encounter), downloads through the customer API.
Nothing is sent anywhere.

11.1's U13 (exports): a current download is served as stored; an earlier draft and an earlier approved download (@1 and
@2, TXT and CSV) carry the EARLIER banner, name their revision and download as '-earlier' while the stored artifact is
unchanged; a @2 export states the revision, the details and the time its codes were made, read from the assessment's
own context; and an approved @1 export of a legacy encounter is earlier for exactly as long as a case-B update is
pending - before its analyze, after a pass-1 failure, under a hold, after a Stop - and current again after a restore.
"""
from __future__ import annotations

import csv
import hashlib
import io

from django.test import Client

from studio import customer_api, models, reports, review
from studio.models import ReportArtifact
from tests.v2.test_jobs import BARE_429, EXTRACTION, HTTP_500, answered
from tests.v2.test_update_pipeline import OFFICE, UpdateCase

Job = models.Job
# what the installed release (format @1) stored for a customer export: its header, the codes, its banner - and no
# revision, details or time of the codes (8.2's @2 lines)
V1_TXT = ('SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\nCPT STUDIO — APPROVED CODES\nReport format: cpt-studio-customer-report@1\n'
          'Encounter: Synthetic note\nDate of service: 2031-03-14\nGenerated: 2031-03-14T12:00:00Z by Synthetic Reviewer\n\n'
          'Approved codes\n1. 45378 — units 1 — modifiers: none\n\nSYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\n')
V1_COLUMNS = ('report_format', 'encounter_title', 'date_of_service', 'number', 'code', 'units', 'modifiers', 'status',
              'approved_by', 'approver_kind', 'approved_at', 'summary', 'evidence_text', 'evidence_page', 'evidence_start',
              'evidence_end', 'review_label')


def v1_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(V1_COLUMNS)
    writer.writerow(['SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS'] + [''] * (len(V1_COLUMNS) - 1))
    writer.writerow(['cpt-studio-customer-report@1', 'Synthetic note', '2031-03-14', 1, '45378', 1, '', 'approved',
                     'Synthetic Reviewer', 'human', '2031-03-14T12:00:00Z', 'Colonoscopy.', '', '', '', '', ''])
    return buffer.getvalue().encode('utf-8')


class ExportCase(UpdateCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def membership(self):
        return models.Membership.objects.get(workspace=self.ws, user=self.user)

    def approve_all(self, encounter):
        """Every code of ``encounter``'s current (legacy, decidable) assessment approved through the review layer."""
        row = self.fresh_row(encounter)
        for proposal in row.current_assessment.proposals.all():
            if review.APPROVE in review.allowed_actions(proposal, row.current_assessment, self.membership()):
                review.record_decision(encounter=self.fresh_row(encounter), proposal=proposal, action=review.APPROVE,
                                       user=self.user, membership=self.membership(),
                                       acknowledgement=review.ACKNOWLEDGEMENTS[self.user.actor_kind])

    def v1_artifact(self, encounter, kind='approved', fmt='txt'):
        """A customer export as the installed release (format @1) stored it, current: its marker digest the encounter's
        now (the marker is unchanged by this release, 8.2)."""
        row = self.fresh_row(encounter)
        content = V1_TXT.encode('utf-8') if fmt == 'txt' else v1_csv()
        return ReportArtifact.objects.create(
            encounter=row, assessment=row.current_assessment, kind=kind, fmt=fmt,
            filename=f'CPT-Studio-{kind}-r1-20310314T120000.{fmt}', content=content,
            sha256=hashlib.sha256(content).hexdigest(), snapshot_sha256=reports.customer_marker_digest(row),
            generated_by=self.user, audience=ReportArtifact.CUSTOMER)

    def export(self, encounter, kind='draft', fmt='txt'):
        response = self.client.post(f'/api/encounters/{encounter.pk}/reports', {'kind': kind, 'fmt': fmt},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return ReportArtifact.objects.get(pk=response.json()['id'])

    def download(self, report):
        response = self.client.get(f'/api/reports/{report.pk}/download')
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def listed(self, encounter, report):
        [found] = [item for item in customer_api._reports(self.fresh_row(encounter)) if item['id'] == str(report.pk)]
        return found

    def assertStoredUnchanged(self, report):  # noqa: N802 - unittest's naming
        stored = ReportArtifact.objects.get(pk=report.pk)
        self.assertEqual(bytes(stored.content), bytes(report.content))
        self.assertEqual(stored.sha256, hashlib.sha256(bytes(report.content)).hexdigest())

    def assertCurrentDownload(self, report):  # noqa: N802 - unittest's naming
        response = self.download(report)
        self.assertEqual(response.content, bytes(report.content))
        self.assertEqual(response['Content-Disposition'], f'attachment; filename="{report.filename}"')

    def assertEarlierDownload(self, report):  # noqa: N802 - unittest's naming
        """8.3: the banner, then the stored bytes; the '-earlier' name; the artifact's assessment's revision named."""
        response = self.download(report)
        number = report.assessment.revision.number
        made = reports.EARLIER_MADE.format(at=reports._ts(report.generated_at), n=number)
        stem, extension = report.filename.rsplit('.', 1)
        self.assertEqual(response['Content-Disposition'], f'attachment; filename="{stem}-earlier.{extension}"')
        stored = bytes(report.content)
        if report.fmt == 'txt':
            self.assertEqual(response.content, f'{reports.EARLIER_BANNER}\n{made}\n\n'.encode() + stored)
        else:
            rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'), newline='')))
            stored_rows = list(csv.reader(io.StringIO(stored.decode('utf-8'), newline='')))
            self.assertEqual(rows[0], stored_rows[0])  # the stored header first
            self.assertEqual(rows[1], [f'{reports.EARLIER_BANNER}\n{made}'] + [''] * (len(stored_rows[0]) - 1))
            self.assertEqual(rows[2:], stored_rows[1:])
            self.assertTrue(response.content.endswith(stored[len(stored.decode('utf-8').split('\r\n', 1)[0]) + 2:]))
        self.assertIn(f'on revision {number}.', response.content.decode('utf-8'))
        self.assertStoredUnchanged(report)


class DownloadTests(ExportCase):
    """8.3: current downloads as stored; earlier ones, of either kind and format, @1 included, with the banner."""

    def test_u13_a_current_download_is_byte_identical_to_its_stored_bytes(self):
        encounter = self.legacy_fixture()
        for fmt in ('txt', 'csv'):
            with self.subTest(fmt=fmt):
                report = self.export(encounter, 'draft', fmt)
                self.assertTrue(self.listed(encounter, report)['current'])
                self.assertCurrentDownload(report)
                self.assertTrue(reports.customer_artifact_current(report))

    def test_u13_earlier_drafts_and_approved_exports_at_1_and_2_download_with_the_banner(self):
        encounter = self.legacy_fixture()
        self.approve_all(encounter)
        made = [self.export(encounter, kind, fmt) for kind in ('draft', 'approved') for fmt in ('txt', 'csv')]
        made += [self.v1_artifact(encounter, 'approved', fmt) for fmt in ('txt', 'csv')]
        for report in made:
            self.assertTrue(reports.customer_artifact_current(report), report.filename)
        # a decision changes the marker: every export made before it is earlier - never refused (A9: 409 no more)
        proposal = self.fresh_row(encounter).current_assessment.proposals.first()
        review.record_decision(encounter=self.fresh_row(encounter), proposal=proposal, action=review.REVOKE,
                               user=self.user, membership=self.membership())
        for report in made:
            with self.subTest(report=report.filename):
                self.assertFalse(reports.customer_artifact_current(report))
                listed = self.listed(encounter, report)
                self.assertEqual((listed['current'], listed['revision']), (False, 1))
                self.assertEarlierDownload(report)

    def test_u13_a_2_export_states_revision_details_and_codes_made_from_the_assessments_context(self):
        encounter = self.v2_fixture()
        assessment = self.fresh_row(encounter).current_assessment
        txt = self.export(encounter, 'draft', 'txt')
        body = bytes(txt.content).decode('utf-8')
        self.assertIn(f'Report format: {reports.CUSTOMER_FORMAT}\n', body)
        self.assertEqual(reports.CUSTOMER_FORMAT, 'cpt-studio-customer-report@2')
        date, details = reports._context_details(assessment.context)
        self.assertEqual(date, '2031-03-14')  # NOTE's own date, from the assessment's context facts
        self.assertEqual(details, 'date of service 2031-03-14; place of service not documented; patient not documented; '
                                  'claim not documented')
        lines = body.split('\n')
        at = lines.index('Encounter: Synthetic note')
        self.assertEqual(lines[at + 1:at + 5], ['Document: revision 1', f'Details used: {details}',
                                                f'Codes made: {reports._ts(assessment.created_at)}',
                                                'Date of service: 2031-03-14'])
        csv_report = self.export(encounter, 'draft', 'csv')
        rows = list(csv.DictReader(io.StringIO(bytes(csv_report.content).decode('utf-8'), newline='')))
        self.assertEqual(list(rows[0])[-3:], ['revision_number', 'details_used', 'codes_made_at'])
        for row in rows:  # every row, the banner rows included
            self.assertEqual((row['revision_number'], row['details_used'], row['codes_made_at']),
                             ('1', details, reports._ts(assessment.created_at)))

    def test_u13_the_details_come_from_the_assessments_own_context_never_the_encounters(self):
        """8.2: a context whose facts carry a documented setting and a member's choice, read through its own facts -
        whatever the encounter's saved values are now."""
        encounter = self.v2_fixture()
        context = self.fresh_row(encounter).current_assessment.context
        facts = dict(context.facts)
        facts['setting'] = {'name': 'setting', 'value': 'hospital_outpatient', 'origin': 'document', 'evidence': []}
        facts['billing_context'] = {'name': 'billing_context', 'value': None, 'origin': 'conflict', 'evidence': []}
        stand_in = models.EncounterContext(facts=facts, user_values={'setting': 'office'})
        date, details = reports._context_details(stand_in)
        self.assertEqual(details, 'date of service 2031-03-14; place of service Hospital outpatient department; '
                                  'patient not documented; claim not established')
        self.assertEqual(reports._context_details(None), (None, 'date of service not documented; place of service not '
                                                                 'documented; patient not documented; claim not documented'))

    def test_u13_the_earlier_filename_and_a_header_only_csv(self):
        self.assertEqual(reports.earlier_filename('CPT-Studio-draft-r2-20310314T120000.csv'),
                         'CPT-Studio-draft-r2-20310314T120000-earlier.csv')
        self.assertEqual(reports.earlier_filename('export'), 'export-earlier')


class DuringAnUpdateTests(ExportCase):
    """8.1 and 8.3 [R:races-R1][R:truth-T1][R:legacy-L1]: while an update is pending no export is made, and every export
    made before it is earlier - a case-B update included, whose save keeps the context, the assessment, the decisions
    and the answers (so the marker alone stays byte-identical) - and current again after a restore."""

    def assertEarlierWhilePending(self, encounter, report, state):  # noqa: N802 - unittest's naming
        row = self.fresh_row(encounter)
        self.assertTrue(review.update_pending(row), state)
        self.assertEqual(reports.customer_marker_digest(row), report.snapshot_sha256, f'{state}: the marker is unchanged')
        self.assertFalse(reports.customer_artifact_current(report), state)
        self.assertFalse(self.listed(encounter, report)['current'], state)
        self.assertEarlierDownload(report)
        # no new export of the earlier codes, of either kind, in either format (8.1): 409 UPDATE_EXPORT, nothing written
        count = ReportArtifact.objects.count()
        for kind in ('draft', 'approved'):
            for fmt in ('txt', 'csv'):
                response = self.client.post(f'/api/encounters/{encounter.pk}/reports', {'kind': kind, 'fmt': fmt},
                                            content_type='application/json')
                self.assertEqual(response.status_code, 409, (state, kind, fmt))
                self.assertEqual(response.json()['error'], customer_api.UPDATE_EXPORT, (state, kind, fmt))
        self.assertEqual(ReportArtifact.objects.count(), count, state)

    def restore_and_check(self, encounter, report):
        saved = self.save(encounter, setting='')
        self.assertTrue(saved.restored)
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertTrue(reports.customer_artifact_current(report))
        self.assertTrue(self.listed(encounter, report)['current'])
        self.assertCurrentDownload(report)

    def test_u13_an_approved_1_export_is_earlier_before_the_updates_analyze_then_current_after_a_restore(self):
        encounter = self.legacy_fixture()
        self.approve_all(encounter)
        report = self.v1_artifact(encounter)
        self.assertTrue(reports.customer_artifact_current(report))
        self.save(encounter, setting=OFFICE)  # case B: the context is kept, the reading queued
        self.assertEarlierWhilePending(encounter, report, 'before analyze')
        self.restore_and_check(encounter, report)

    def test_u13_after_a_pass_1_failure(self):
        encounter = self.legacy_fixture()
        self.approve_all(encounter)
        report = self.v1_artifact(encounter, fmt='csv')
        self.interpreter.script = {EXTRACTION: [answered(HTTP_500, status=500)]}
        self.save(encounter, setting=OFFICE)
        self.drain()
        self.assertEqual(review._derive_state(self.fresh_row(encounter)), 'provider_failed')
        self.assertEarlierWhilePending(encounter, report, 'after a pass-1 failure')
        self.restore_and_check(encounter, report)

    def test_u13_under_a_hold(self):
        encounter = self.legacy_fixture()
        self.approve_all(encounter)
        report = self.v1_artifact(encounter)
        self.interpreter.script = {EXTRACTION: [answered(BARE_429, status=429)]}
        self.save(encounter, setting=OFFICE)
        self.drain()
        self.assertEqual(review._derive_state(self.fresh_row(encounter)), 'stopped')  # paused under the hold
        self.assertEarlierWhilePending(encounter, report, 'under a hold')
        self.restore_and_check(encounter, report)

    def test_u13_after_a_stop(self):
        from studio import jobs

        encounter = self.legacy_fixture()
        self.approve_all(encounter)
        report = self.v1_artifact(encounter)
        self.save(encounter, setting=OFFICE)
        jobs.stop_encounter(self.fresh_row(encounter), self.user)
        self.assertFalse(Job.objects.filter(encounter=encounter, state__in=(Job.QUEUED, Job.RUNNING)).exists())
        self.assertEarlierWhilePending(encounter, report, 'after a Stop')
        self.restore_and_check(encounter, report)

    def test_u13_the_snapshot_refuses_under_the_lock_when_a_save_lands_after_the_requests_read(self):
        """8.1: create_report reads the encounter before the snapshot's lock; a save in between is refused there too, and
        the API answers UPDATE_EXPORT, nothing written."""
        from unittest import mock

        encounter = self.legacy_fixture()
        real = reports.update_refusal
        calls = []

        def first_sees_nothing(found):
            calls.append(found.pk)
            if len(calls) == 1:  # the API's own read, before the save lands
                self.save(encounter, setting=OFFICE)
                return None
            return real(found)
        count = ReportArtifact.objects.count()
        with mock.patch.object(reports, 'update_refusal', side_effect=first_sees_nothing):
            response = self.client.post(f'/api/encounters/{encounter.pk}/reports', {'kind': 'draft', 'fmt': 'txt'},
                                        content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], customer_api.UPDATE_EXPORT)
        self.assertEqual(ReportArtifact.objects.count(), count)
        self.assertGreaterEqual(len(calls), 2)
