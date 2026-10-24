"""Coding reports rendered from persisted rows (ARCHITECTURE 5.8). Synthetic data only."""
import csv
import hashlib
import io
import re
from dataclasses import replace

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import models, reports, review
from studio.types import ExtractionResult, Fact, PageSpan
from tests.support import factories as f
from tests.support import pipeline_factories as pf

APPROVED = 'APPROVED SELECTIONS'
REJECTED = 'REJECTED — EXCLUDED FROM APPROVED RESULTS'
UNDECIDED = 'UNDECIDED — REVIEW NOT COMPLETE'
TITLES = ('ENCOUNTER, SOURCE AND REVISION', 'ENCOUNTER CONTEXT', APPROVED, REJECTED, UNDECIDED, 'EXCLUDED CANDIDATES',
          'ALTERNATIVES — PROVIDER CANDIDATES, NEVER SELECTED', 'CHECKS', 'OPEN CLARIFICATIONS', 'NOT VERIFIED',
          'PROVIDER USAGE', 'REFERENCE SOURCES', 'AUDIT — DECISION HISTORY')


def section(text, title):
    """One TXT section's body: the lines after its title up to the next blank line."""
    lines = text.split('\n')
    start = lines.index(title) + 1
    return '\n'.join(lines[start:lines.index('', start)])


def parse_csv(content):
    return list(csv.reader(io.StringIO(content.decode('utf-8'), newline='')))


class ReportCase(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.assessment = pf.assess(self.s.encounter, pf.standard_result())

    def txt(self, kind='draft'):
        return reports.render_txt(reports.snapshot(self.s.encounter, kind)).decode('utf-8')

    def csv(self, kind='draft'):
        return reports.render_csv(reports.snapshot(self.s.encounter, kind))

    def review_all(self, approver=None, rejecter=None):
        self.s.decide('sel:0', 'approve', approver or self.s.agent, note='Biopsy passage matches.')
        self.s.decide('sel:1', 'reject', rejecter or self.s.reviewer, note='Not supported as documented.')


class TxtReportTests(ReportCase):
    def test_draft_is_labelled_and_has_no_approved_section(self):
        self.s.decide('sel:0', 'approve', self.s.reviewer)
        text = self.txt('draft')
        lines = text.split('\n')
        self.assertEqual(lines[:2], ['CPT STUDIO CODING REPORT — DRAFT — NOT REVIEWED',
                                     'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS'])
        self.assertTrue(text.endswith('\nSYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\n'))
        self.assertNotIn(APPROVED, text)
        self.assertNotIn(reports.AGENT_LINE, text)
        self.assertIn('Review status: not complete\n  - 45385 has no decision', text)
        undecided = section(text, UNDECIDED)
        self.assertIn('1. 43239 · Upper GI endoscopy', undecided)
        self.assertIn('approved by Reviewer', undecided)
        self.assertIn('provisional; this draft is not a reviewed report', undecided)
        self.assertIn('2. 45385 · Colonoscopy · units 1\n', undecided)
        self.assertIn('Status: Ready for review', undecided)
        self.assertIn('Current decision: none', undecided)
        self.assertEqual(section(text, REJECTED), '  None.')

    def test_reviewed_lists_only_approved_codes_as_approved(self):
        self.review_all()
        text = self.txt('reviewed')
        lines = text.split('\n')
        self.assertEqual(lines[:3], ['CPT STUDIO CODING REPORT — REVIEWED',
                                     'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS',
                                     'Agent-executed synthetic review — not clinical approval'])
        self.assertNotIn('DRAFT', text)
        self.assertNotIn(UNDECIDED, text)
        approved = section(text, APPROVED)
        self.assertIn('1. 43239 · Upper GI endoscopy', approved)
        self.assertNotIn('45385', approved)
        self.assertNotIn('Status:', approved)
        self.assertRegex(approved, r'Decision: approved by Reviewbot\d+ \(automated agent\) at \d{4}-')
        self.assertNotIn('(agent)', approved)
        self.assertIn('Acknowledgement: Reviewed the source evidence (synthetic test).', approved)
        span = pf.evidence(pf.GI_NOTE, pf.EGD_PASSAGE)
        self.assertIn(f'"{pf.EGD_PASSAGE}" [chars {span.start}–{span.end}, page 1]', approved)
        self.assertIn(reports.DESCRIPTOR_LINE, approved)
        self.assertIn('Profile: gi.egd@1', approved)
        rejected = section(text, REJECTED)
        self.assertIn('45385 · Colonoscopy — rejected by Reviewer', rejected)
        self.assertIn('(human)', rejected)
        self.assertNotIn('43239', rejected)
        positions = [lines.index(title) for title in TITLES if title in lines]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(positions), len(TITLES) - 1)

    def test_human_only_review_has_no_agent_line(self):
        self.review_all(approver=self.s.reviewer)
        self.assertNotIn(reports.AGENT_LINE, self.txt('reviewed'))

    def test_reinstated_and_approved_exclusion_is_an_approved_selection(self):
        self.review_all()
        self.s.decide('exc:0', 'reinstate', note='Performed today; the plan line was mis-read.')
        draft = self.txt('draft')
        self.assertIn('45378 was reinstated and has no decision', draft)
        undecided = section(draft, UNDECIDED)
        self.assertIn('1. 43239 · Upper GI endoscopy', undecided)
        self.assertIn('2. 45378 · Colonoscopy · units 1', undecided)
        self.assertIn('Status: Reinstated by a reviewer', undecided)
        self.assertIn('Current decision: reinstated for review by Reviewer', undecided)
        reinstate_line = next(line for line in undecided.split('\n') if 'reinstated for review by' in line)
        self.assertNotIn('provisional', reinstate_line)
        self.assertEqual(section(draft, 'EXCLUDED CANDIDATES'), '  None.')
        self.s.decide('exc:0', 'approve')
        text = self.txt('reviewed')
        approved = section(text, APPROVED)
        self.assertIn('2. 45378 · Colonoscopy · units 1', approved)
        self.assertRegex(approved, r'Reinstated from exclusion by Reviewer\d+ \(human\) at \d{4}-\d\d-\d\dT[0-9:]+Z: '
                                   r'The colonoscopy is planned')
        self.assertEqual(section(text, 'EXCLUDED CANDIDATES'), '  None.')

    def test_excluded_alternatives_checks_and_not_verified(self):
        text = self.txt('draft')
        self.assertIn('45378 · Colonoscopy · cpt1 — Excluded: The colonoscopy is planned, not performed on this '
                      'date. (a reviewer may reinstate it)', section(text, 'EXCLUDED CANDIDATES'))
        self.assertIn('45380 · Colonoscopy — provider alternative, never selectable',
                      section(text, 'ALTERNATIVES — PROVIDER CANDIDATES, NEVER SELECTED'))
        checks = section(text, 'CHECKS')
        self.assertIn('  43239 (undecided)\n    [PASS] evidence.exact — Exact source evidence', checks)
        self.assertIn('[NOT_VERIFIED] ncci.ptp', checks)
        self.assertIn('  Encounter\n    [PASS] extraction.status', checks)
        not_verified = section(text, 'NOT VERIFIED')
        for _, _, detail in reports.STANDING_NOT_VERIFIED:
            self.assertIn(detail, not_verified)
        for code, listed in (('43239', 'undecided'), ('45385', 'undecided'), ('45378', 'excluded'),
                             ('45380', 'alternative')):
            self.assertIn(f'{code} ({listed}) · cpt.membership', not_verified)
            self.assertIn(f'{code} ({listed}) · ncci.ptp', not_verified)

    def test_unsupported_services_clarifications_and_encounter_not_verified_items(self):
        result = pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                        clarifications=[pf.clarification('extent', family='gi.egd',
                                                          question='How far was the endoscope advanced?')]),
            encounter_checks=[pf.check('service.missed', 'not_verified', 'Performed services without a proposal',
                                       'A performed service may have no proposed code.')],
            clarifications=[pf.clarification('service_date', scope='encounter')],
            unsupported=[{'family': 'gi.other', 'label': 'Other GI service', 'status': 'performed',
                          'detail': 'Esophageal manometry is not profiled in this release.', 'codes': ['91010']}])
        ctx = pf.context(self.s.encounter, self.s.revision,
                         fact_values=pf.facts(setting=Fact(name='setting', value='office', origin='user')),
                         user_values={'setting': 'office'})
        pf.assess(self.s.encounter, result, ctx=ctx)
        text = self.txt('draft')
        questions = section(text, 'OPEN CLARIFICATIONS')
        self.assertIn('  - 43239 · extent — How far was the endoscope advanced?', questions)
        self.assertIn('  - Encounter · service date — Please document the service_date.', questions)
        not_verified = section(text, 'NOT VERIFIED')
        self.assertIn('service.missed — Performed services without a proposal: A performed service may have no '
                      'proposed code.', not_verified)
        self.assertIn('Other GI service (performed): Esophageal manometry is not profiled in this release. '
                      'Codes: 91010.', not_verified)
        self.assertIn('Setting: office (member-supplied encounter metadata, not a clinical fact)',
                      section(text, 'ENCOUNTER CONTEXT'))

    def test_stored_text_cannot_forge_a_heading_or_a_section_break(self):
        forged = 'Looks fine.\r\n\r\nAPPROVED SELECTIONS\n  1. 99999 · Forged · units 9\rREJECTED — EXCLUDED FROM ' \
                 'APPROVED RESULTS'
        self.s.decide('sel:0', 'approve', note=forged, acknowledgement=forged)
        models.Encounter.objects.filter(pk=self.s.encounter.pk).update(title='Synthetic\n\nAPPROVED SELECTIONS')
        text = self.txt('draft')
        lines = text.split('\n')
        self.assertNotIn('\r', text)
        self.assertNotIn(APPROVED, lines)
        self.assertEqual(lines.count(REJECTED), 1)
        self.assertEqual(lines.count(''), len([title for title in TITLES if title in lines]) + 2)
        self.assertIn('Note: Looks fine.', section(text, UNDECIDED))
        self.assertIn('       APPROVED SELECTIONS', text)

    def test_context_section_shows_origin_and_exact_evidence(self):
        context = section(self.txt('draft'), 'ENCOUNTER CONTEXT')
        start = pf.GI_NOTE.index(pf.DATE_PASSAGE)
        self.assertIn('Service date: 2026-10-21 (documented)\n    Evidence: '
                      f'"{pf.DATE_PASSAGE}" [chars {start}–{start + len(pf.DATE_PASSAGE)}]', context)
        self.assertIn('Billing context: not documented — Professional or facility billing is not documented.',
                      context)
        self.assertIn('Patient status: not documented', context)

    def test_source_revision_and_assessment_identity(self):
        text = self.txt('draft')
        source = section(text, 'ENCOUNTER, SOURCE AND REVISION')
        revision = self.s.revision
        self.assertIn(f'Encounter id: {self.s.encounter.pk}', source)
        self.assertIn('Revision: 1 (pasted text)', source)
        self.assertIn('Source: pasted text (no original file) · sha256 of the text as submitted '
                      f'{hashlib.sha256(pf.GI_NOTE.encode()).hexdigest()}', source)
        self.assertIn(f'Extracted text: {len(pf.GI_NOTE)} characters · sha256 {revision.text_sha256}', source)
        self.assertIn(f'Assessment: {self.assessment.pk}', source)
        self.assertIn(f'sha256 {self.assessment.sha256}', source)
        self.assertIn(f'profiles gi-profiles@2 · engine {pf.ENGINE_VERSION} · routing {pf.ROUTING_VERSION}', source)

    def test_uploaded_and_addendum_revisions_name_their_root_file(self):
        enc = f.encounter(self.s.workspace, self.s.reviewer, title='Uploaded synthetic note')
        source = models.SourceFile.objects.create(
            encounter=enc, original_name='synthetic-egd.txt', media_type='text/plain', size=len(pf.GI_NOTE),
            sha256=hashlib.sha256(pf.GI_NOTE.encode()).hexdigest(), storage_name=f'{enc.workspace_id}/x.txt',
            uploaded_by=self.s.reviewer)
        rev = models.SourceRevision.objects.create(
            encounter=enc, number=1, kind='upload', source_file=source, synthetic_attested_by=self.s.reviewer,
            synthetic_attested_at=timezone.now(), created_by=self.s.reviewer)
        f.record(rev, ExtractionResult(status='partial', method='txt', text=pf.GI_NOTE,
                                       pages=(PageSpan(1, 0, len(pf.GI_NOTE)),),
                                       messages=('Headers and footers were not extracted.',)))
        enc.current_revision = rev
        enc.save(update_fields=['current_revision', 'updated_at'])
        pf.context(enc, models.SourceRevision.objects.get(pk=rev.pk))
        pf.addendum(enc, self.s.reviewer, 'Setting confirmed as hospital outpatient.')
        enc.refresh_from_db()
        pf.context(enc, enc.current_revision)
        pf.assess(enc, pf.standard_result(text=enc.current_revision.text))
        text = reports.render_txt(reports.snapshot(enc, 'draft')).decode('utf-8')
        block = section(text, 'ENCOUNTER, SOURCE AND REVISION')
        self.assertIn('Revision: 2 (addendum to revision 1)', block)
        self.assertIn(f'Source file: synthetic-egd.txt · text/plain · {len(pf.GI_NOTE)} bytes · sha256 '
                      f'{source.sha256}', block)
        self.assertEqual(reports.snapshot(enc, 'draft')['revision']['source']['sha256'], source.sha256)

    def test_extraction_limitations_are_reported(self):
        enc = f.encounter(self.s.workspace, self.s.reviewer, title='Partially extracted note')
        rev = f.pasted_revision(enc, self.s.reviewer, pf.GI_NOTE, extract=False)
        f.record(rev, ExtractionResult(status='partial', method='pdf-mixed', text=pf.GI_NOTE, ocr_pages=(2,),
                                       pages=(PageSpan(1, 0, len(pf.GI_NOTE)),),
                                       messages=('Page 3 has no text layer and OCR failed.',)))
        rev.refresh_from_db()
        pf.context(enc, rev)
        pf.assess(enc, pf.standard_result())
        block = section(reports.render_txt(reports.snapshot(enc, 'draft')).decode(), 'ENCOUNTER, SOURCE AND REVISION')
        self.assertIn('Extraction: partial (pdf-mixed) · 1 page(s)', block)
        self.assertIn('OCR pages: 2', block)
        self.assertIn('Extraction message: Page 3 has no text layer and OCR failed.', block)

    def test_provider_usage_and_reference_sources(self):
        text = self.txt('draft')
        run = self.assessment.provider_run
        usage = section(text, 'PROVIDER USAGE')
        self.assertIn('  - replay · REPLAY (recorded response, not live output) · succeeded · HTTP 200 · revision 1',
                      usage)
        self.assertIn('used by this assessment', usage)
        self.assertIn('Usage: {"creditsConsumed": 0.0281} (provider_reported_credits_not_usd)', usage)
        self.assertIn(f'Request sha256: {run.request_sha256} · Response sha256: {run.response_sha256}', usage)
        references = section(text, 'REFERENCE SOURCES')
        self.assertIn('cms-pfs-rvu26d · PFS relative value file · release RVU26D · effective 2026-10-01 to '
                      '2026-12-31 · applies to the service date: yes', references)
        connected, not_connected = references.split('  Not connected:')
        self.assertNotIn('CPT code set', connected)
        for _, entry in reports.NOT_CONNECTED:
            self.assertIn(entry, not_connected)

    def test_recorded_not_connected_sources_are_never_listed_as_connected(self):
        recorded = pf.reference_source(key='cms-ncci-ptp', title='NCCI PTP edits', release='', applies=False,
                                       connected=False, license_note='Recorded licence wording.',
                                       scope_note='NOT CONNECTED: recorded scope wording.')
        stale = pf.reference_source(key='cms-pfs-rvu26c', release='RVU26C', applies=False,
                                    note='Not applied: another installed release of this kind also covers the date.')
        ctx = pf.context(self.s.encounter, self.s.revision,
                         fact_values=pf.facts(setting=Fact(name='setting', value='office', origin='user')))
        pf.assess(self.s.encounter, pf.standard_result(reference_sources=[pf.reference_source(), stale, recorded]),
                  ctx=ctx)
        connected, not_connected = section(self.txt('draft'), 'REFERENCE SOURCES').split('  Not connected:')
        self.assertNotIn('NCCI', connected)
        self.assertIn('release RVU26C', connected)
        self.assertIn('applies to the service date: no · Not applied: another installed release', connected)
        self.assertIn('NCCI PTP edits — Recorded licence wording. NOT CONNECTED: recorded scope wording.',
                      not_connected)
        self.assertEqual(not_connected.count('NCCI'), 1)
        self.assertIn(dict(reports.NOT_CONNECTED)['ama-cpt'], not_connected)

    def test_audit_lists_decisions_carries_and_invalidations(self):
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'reject')
        items = pf.standard_result().proposals
        ctx = pf.context(self.s.encounter, self.s.revision,
                         fact_values=pf.facts(setting=Fact(name='setting', value='office', origin='user')))
        pf.assess(self.s.encounter, pf.result(pf.with_fingerprint(items[0], 'e' * 64), *items[1:]), ctx=ctx)
        audit = section(self.txt('draft'), 'AUDIT — DECISION HISTORY')
        entries = audit.split('\n  - ')
        self.assertEqual(len(entries), 3)
        self.assertIn('43239 · approve', entries[0])
        self.assertIn('Invalidated', entries[0])
        self.assertIn('the evidence or checks for 43239 changed', entries[0])
        self.assertIn('carried forward to a later assessment', entries[1])
        self.assertIn('this assessment · carried from', entries[2])

    def test_inexact_evidence_is_never_printed(self):
        exact = pf.evidence(pf.GI_NOTE, pf.EGD_PASSAGE)
        fabricated = replace(exact, text='FABRICATED PASSAGE NOT IN THE NOTE')
        ctx = pf.context(self.s.encounter, self.s.revision,
                         fact_values=pf.facts(setting=Fact(name='setting', value='office', origin='user')))
        pf.assess(self.s.encounter, pf.result(pf.proposal('sel:0', '43239', spans=[exact, fabricated])), ctx=ctx)
        text = self.txt('draft')
        self.assertIn(f'"{pf.EGD_PASSAGE}"', text)
        self.assertIn('(1 cited passage(s) did not match the revision text exactly and are not shown)', text)
        self.assertNotIn('FABRICATED', text)
        self.assertNotIn(b'FABRICATED', self.csv('draft'))

    def test_provider_display_text_never_appears(self):
        for kind in ('draft', 'reviewed'):
            if kind == 'reviewed':
                self.review_all()
            snap = reports.snapshot(self.s.encounter, kind)
            self.assertNotIn('SENTINEL', repr(snap))
            for content in (reports.render_txt(snap), reports.render_csv(snap)):
                self.assertNotIn(b'SENTINEL', content)
                self.assertNotIn(pf.PROVIDER_DISPLAY.encode(), content)

    def test_rendering_is_deterministic(self):
        snap = reports.snapshot(self.s.encounter, 'draft')
        self.assertEqual(reports.render_txt(snap), reports.render_txt(snap))
        self.assertEqual(reports.render_csv(snap), reports.render_csv(snap))
        later = reports.snapshot(self.s.encounter, 'draft')
        self.assertEqual(reports.snapshot_digest(snap), reports.snapshot_digest(later))
        self.s.decide('sel:0', 'reject')
        self.assertNotEqual(reports.snapshot_digest(snap),
                            reports.snapshot_digest(reports.snapshot(self.s.encounter, 'draft')))


class ReadinessGateTests(ReportCase):
    def test_reviewed_snapshot_is_refused_until_the_review_is_complete(self):
        with self.assertRaises(reports.ReportNotReady) as caught:
            reports.snapshot(self.s.encounter, 'reviewed')
        self.assertEqual(caught.exception.blockers, ['43239 has no decision', '45385 has no decision'])
        self.assertIn('43239 has no decision; 45385 has no decision', str(caught.exception))
        self.assertIsInstance(caught.exception, ValueError)
        with self.assertRaises(ValueError):
            reports.generate(self.s.encounter, 'reviewed', 'txt', self.s.reviewer)
        self.assertFalse(models.ReportArtifact.objects.exists())
        self.review_all()
        self.assertEqual(reports.snapshot(self.s.encounter, 'reviewed')['kind'], 'reviewed')

    def test_a_revised_source_withdraws_both_reports_until_reassessed(self):
        self.review_all()
        rev = pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed.')
        review.invalidate_for_new_revision(self.s.encounter, rev)
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind), self.assertRaisesRegex(ValueError, 'no assessment of the current revision'):
                reports.snapshot(self.s.encounter, kind)
        pf.context(self.s.encounter, rev)
        pf.assess(self.s.encounter, pf.standard_result(text=rev.text))
        with self.assertRaises(reports.ReportNotReady):
            reports.snapshot(self.s.encounter, 'reviewed')
        self.assertEqual(reports.snapshot(self.s.encounter, 'draft')['revision']['number'], 2)

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            reports.snapshot(self.s.encounter, 'final')


class CsvReportTests(ReportCase):
    def test_structure_and_item_lists(self):
        self.review_all()
        content = self.csv('reviewed')
        self.assertFalse(content.startswith(b'\xef\xbb\xbf'))
        records = content.split(b'\r\n')
        self.assertEqual(records[-1], b'')
        self.assertTrue(all(record.startswith(b'"') and record.endswith(b'"') for record in records[:-1]))
        self.assertNotIn(b'\n', b''.join(records))
        rows = parse_csv(content)
        self.assertEqual(rows[0], list(reports.CSV_COLUMNS))
        data = [dict(zip(rows[0], row)) for row in rows[1:]]
        self.assertEqual([(r['item_list'], r['code']) for r in data],
                         [('approved', '43239'), ('rejected', '45385'), ('excluded', '45378'),
                          ('alternative', '45380')])
        approved = data[0]
        self.assertEqual((approved['report_kind'], approved['encounter_id'], approved['revision_number']),
                         ('reviewed', str(self.s.encounter.pk), '1'))
        self.assertEqual((approved['text_sha256'], approved['assessment_id']),
                         (self.s.revision.text_sha256, str(self.assessment.pk)))
        self.assertEqual(approved['source_sha256'], hashlib.sha256(pf.GI_NOTE.encode()).hexdigest())
        self.assertEqual((approved['decision'], approved['reviewer_kind']), ('approve', 'agent'))
        self.assertIn('automated agent', approved['reviewer'])
        self.assertRegex(approved['decided_at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        span = pf.evidence(pf.GI_NOTE, pf.EGD_PASSAGE)
        self.assertEqual(approved['evidence'], f'"{pf.EGD_PASSAGE}" [{span.start}-{span.end}, p1]')
        self.assertTrue(approved['checks'].startswith('evidence.exact=pass;routing.family=pass;'))
        self.assertEqual(approved['not_verified'], 'cpt.descriptor=withheld;cpt.membership=not_verified;'
                                                   'ncci.ptp=not_verified')
        self.assertEqual(data[1]['modifier_considerations'], 'Consider whether modifier 59 applies.')
        self.assertEqual(data[2]['exclusion_reason'], 'The colonoscopy is planned, not performed on this date.')
        self.assertEqual({r['synthetic'] for r in data}, {'SYNTHETIC — NOT FOR BILLING'})
        self.assertEqual({r['family_label'] for r in data[1:]}, {'Colonoscopy'})

    def test_draft_never_lists_an_approval_as_approved(self):
        self.s.decide('sel:0', 'approve')
        rows = parse_csv(self.csv('draft'))
        data = [dict(zip(rows[0], row)) for row in rows[1:]]
        self.assertNotIn('approved', {r['item_list'] for r in data})
        first = next(r for r in data if r['code'] == '43239')
        self.assertEqual((first['report_kind'], first['item_list'], first['decision']),
                         ('draft', 'undecided', 'approve'))

    def test_formula_cells_are_neutralised(self):
        hostile = self.s.reviewer
        hostile.display_name = '=HYPERLINK("https://example.invalid","x")'
        hostile.save(update_fields=['display_name'])
        codes = ['=1+1', '+SUM(A1)', '-2+3', '@A1', '\tTAB', '\rCR']
        excluded = [pf.proposal(f'exc:{i}', code, bucket='excluded', code_kind='invalid',
                                exclusion_reason=code + ' is not a CPT code.') for i, code in enumerate(codes)]
        selected = pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], modifiers=('-59 is a consideration only.',))
        ctx = pf.context(self.s.encounter, self.s.revision,
                         fact_values=pf.facts(setting=Fact(name='setting', value='office', origin='user')))
        pf.assess(self.s.encounter, pf.result(selected, *excluded), ctx=ctx)
        self.s.decide('sel:0', 'approve', hostile)
        content = self.csv('reviewed')
        rows = parse_csv(content)
        data = [dict(zip(rows[0], row)) for row in rows[1:]]
        self.assertEqual(data[0]['reviewer'], "'" + hostile.display_name)
        self.assertEqual(data[0]['modifier_considerations'], "'-59 is a consideration only.")
        self.assertIn(b'"\'=HYPERLINK(""https://example.invalid"",""x"")"', content)
        for row, code in zip(data[1:], codes):
            self.assertEqual(row['code'], "'" + code)
            self.assertEqual(row['exclusion_reason'], "'" + code + ' is not a CPT code.')
        for row in rows:
            for cell in row:
                self.assertFalse(cell.startswith(reports.FORMULA_PREFIXES), cell)


class NeutraliseTests(SimpleTestCase):
    def test_formula_leading_characters_get_an_apostrophe(self):
        for value in ('=1+1', '+1', '-1', '@SUM(A1)', '\t=1', '\r=1', '\n=1', '＝1', '＋1', '－1', '＠1'):
            self.assertEqual(reports.neutralise(value), "'" + value)

    def test_ordinary_cells_are_unchanged(self):
        for value in ('45385', 'gi.colonoscopy', ' =1', "'=1", '1-2', 'a=b', ''):
            self.assertEqual(reports.neutralise(value), value)
        self.assertEqual(reports.neutralise(None), '')
        self.assertEqual(reports.neutralise(3), '3')


class GenerateTests(ReportCase):
    def test_stored_bytes_hash_snapshot_digest_filename_and_audit(self):
        self.review_all()
        for kind in ('draft', 'reviewed'):
            for fmt in ('txt', 'csv'):
                with self.subTest(kind=kind, fmt=fmt):
                    artifact = reports.generate(self.s.encounter, kind, fmt, self.s.reviewer)
                    stored = models.ReportArtifact.objects.get(pk=artifact.pk)
                    content = bytes(stored.content)
                    self.assertEqual(hashlib.sha256(content).hexdigest(), stored.sha256)
                    self.assertEqual(stored.snapshot_sha256,
                                     reports.snapshot_digest(reports.snapshot(self.s.encounter, kind)))
                    self.assertRegex(stored.filename, rf'^CPT-Studio-{kind}-{str(self.s.encounter.pk)[:8]}-r1-'
                                                      rf'\d{{8}}T\d{{6}}\.{fmt}$')
                    self.assertEqual((stored.assessment_id, stored.kind, stored.fmt, stored.generated_by),
                                     (self.assessment.pk, kind, fmt, self.s.reviewer))
                    expected = (reports.HEADLINES[kind].encode() if fmt == 'txt'
                                else b'"report_kind","encounter_id"')
                    self.assertTrue(content.startswith(expected))
                    event = models.AuditEvent.objects.filter(event='report.generated').last()
                    self.assertEqual((event.data['report'], event.data['kind'], event.data['fmt']),
                                     (str(stored.pk), kind, fmt))

    def test_artifacts_are_immutable(self):
        artifact = reports.generate(self.s.encounter, 'draft', 'txt', self.s.reviewer)
        original = bytes(models.ReportArtifact.objects.get(pk=artifact.pk).content)
        artifact.content = b'tampered'
        with self.assertRaises(ValidationError):
            artifact.save()
        with self.assertRaises(ValidationError):
            artifact.delete()
        with self.assertRaises(ValidationError):
            models.ReportArtifact.objects.filter(pk=artifact.pk).update(content=b'tampered')
        with self.assertRaises(ValidationError):
            models.ReportArtifact.objects.filter(pk=artifact.pk).delete()
        self.assertEqual(bytes(models.ReportArtifact.objects.get(pk=artifact.pk).content), original)

    def test_only_active_members_generate_and_inputs_are_checked(self):
        self.assertEqual(reports.generate(self.s.encounter, 'draft', 'csv', self.s.viewer).fmt, 'csv')
        other = pf.scenario(workspace_name='Other synthetic workspace')
        with self.assertRaises(PermissionDenied):
            reports.generate(self.s.encounter, 'draft', 'txt', other.reviewer)
        membership = self.s.membership(self.s.agent)
        membership.active = False
        membership.save(update_fields=['active'])
        with self.assertRaises(PermissionDenied):
            reports.generate(self.s.encounter, 'draft', 'txt', self.s.agent)
        for kind, fmt in (('draft', 'pdf'), ('final', 'txt')):
            with self.assertRaises(ValueError):
                reports.generate(self.s.encounter, kind, fmt, self.s.reviewer)
        self.assertEqual(models.ReportArtifact.objects.count(), 1)

    def test_draft_and_reviewed_reports_are_distinct(self):
        self.review_all()
        draft = reports.generate(self.s.encounter, 'draft', 'txt', self.s.reviewer)
        reviewed = reports.generate(self.s.encounter, 'reviewed', 'txt', self.s.reviewer)
        self.assertNotEqual(draft.snapshot_sha256, reviewed.snapshot_sha256)
        self.assertNotIn(APPROVED.encode(), bytes(draft.content))
        self.assertIn(APPROVED.encode(), bytes(reviewed.content))
        self.assertTrue(re.match(rb'CPT STUDIO CODING REPORT \xe2\x80\x94 DRAFT', bytes(draft.content)))
