"""The harness in the reports (HARNESS.md 6-7, I4): the TXT's REVIEW PARTICIPANTS and REFERENCE RETRIEVAL sections and
each code's "Proposed by" and reference check; the CSV's trailing proposed_by and reference_check columns. Proposed,
reference-checked and approved stay three statuses in both formats.

Synthetic data only; no network. The downloads are also read by ops/verify_downloads.py, which must still pass them.
"""
import csv
import importlib.util
import io
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from studio import jobs, models, reports, review, serializers
from tests.support import pipeline_factories as pf
from tests.test_harness_api import fake_pricing, record
from tests.test_harness_pipeline import BOTH, TIME_QUOTE, HarnessCase, fake_passages
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE

_spec = importlib.util.spec_from_file_location('cpt_verify_downloads_harness',
                                               Path(settings.BASE_DIR) / 'ops' / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_verify_downloads_harness'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)


def section(text, title):
    """The body lines of the TXT section headed ``title`` (up to the next blank line before a heading)."""
    lines = text.splitlines()
    start = lines.index(title) + 1
    end = next((i for i in range(start, len(lines)) if not lines[i] and i + 1 < len(lines)
                and lines[i + 1] and not lines[i + 1].startswith(' ')), len(lines))
    return lines[start:end]


def rows(content):
    return list(csv.reader(io.StringIO(content.decode('utf-8'))))


class HandBuiltReportTests(TestCase):
    """Reports of a hand-built assessment that records participant entries and a retrieval trace."""

    def setUp(self):
        self.s = pf.scenario()
        self.items = (
            replace(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]), support={'origin': 'primary',
                                                                               'proposed_by': ['astra', 'fable']}),
            replace(pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE], checks=pf.standard_checks(pfs_presence='warn')),
                    support={'origin': 'participant', 'proposed_by': ['astra']}),
            pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                        exclusion_reason='The colonoscopy is planned, not performed on this date.'),
            replace(pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative', checks=(),
                                exclusion_reason='no exact evidence located for it'),
                    support={'origin': 'participant', 'proposed_by': ['fable']}),
        )
        enc = self.s.encounter
        corti = pf.provider_run(enc, self.s.revision)
        self.astra = self.participant_run('astra', usage={'input_tokens': 2000, 'output_tokens': 400})
        self.fable = self.participant_run('fable', usage={'input_tokens': 1000, 'output_tokens': 100},
                                          returned='claude-other-model')
        participants = [record('astra', 'read', run=self.astra, codes=[('43239', pf.EGD_PASSAGE), ('45385', '')],
                               unverified=1, model='gpt-6-astra'),
                        dict(record('fable', 'refused', run=self.fable,
                                    reason='Answered by claude-other-model, not claude-fable-5-1.',
                                    model='claude-fable-5-1'), returned_model='claude-other-model')]
        retrieval = [{'code': '43239', 'service_date': '2026-10-21',
                      'facts': [{'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D',
                                 'effective': ['2026-10-01', '2026-12-31'], 'sha256': '0' * 64, 'field': 'status',
                                 'value': 'A'}],
                      'passages': [{'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
                                    'passage_key': 'vi-c-1', 'section': 'Chapter VI §C', 'page': '12',
                                    'topic': 'pfs.endo_base', 'topic_value': '43235', 'sha256': '1' * 64,
                                    'text': 'Surgical endoscopy includes diagnostic endoscopy (synthetic test text).'}],
                      'lookups': ['43239: cms-pfs-rvu26d RVU26D'], 'notes': ['43239: synthetic note.']}]
        self.assessment = review.persist_assessment(
            encounter=enc, revision=self.s.revision, context=self.s.context, routing_run=pf.routing(self.s.revision),
            provider_run=corti, result=pf.result(*self.items), participants=participants, retrieval=retrieval)

    def participant_run(self, name, *, usage, returned=None):
        model = {'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}[name]
        run = pf.provider_run(self.s.encounter, self.s.revision, provider=name, usage=usage)
        models.ProviderRun.objects.filter(pk=run.pk).update(
            purpose='independent', service_date=None, scope={'mode': 'live'}, usage_basis='vendor_reported_tokens',
            endpoint={'astra': 'https://api.openai.com/v1/responses',
                      'fable': 'https://api.anthropic.com/v1/messages'}[name],
            requested_model=model, returned_model=returned or model, provider_request_id=f'req_{name}_1',
            response_id={'astra': 'resp_synthetic_1', 'fable': 'msg_synthetic_1'}[name])
        run.refresh_from_db()
        return run

    def txt(self, kind='draft'):
        with mock.patch.dict(sys.modules, {'studio.participants.pricing': fake_pricing()}):
            return reports.render_txt(reports.snapshot(self.s.encounter, kind)).decode('utf-8')

    def test_review_participants_section(self):
        lines = section(self.txt(), 'REVIEW PARTICIPANTS')
        self.assertEqual(lines[0], '  - Corti · Corti · answered; its codes were checked')
        astra = lines.index('  - Astra · OpenAI · answered; the reading was used')
        self.assertEqual(lines[astra + 1:astra + 8], [
            f'    Run: {self.astra.pk}',
            '    Endpoint: https://api.openai.com/v1/responses',
            '    Models: requested gpt-6-astra · returned gpt-6-astra',
            '    Request id: req_astra_1 · response id: resp_synthetic_1',
            '    Usage: {"input_tokens": 2000, "output_tokens": 400} (vendor_reported_tokens)',
            '    Estimated cost: USD 0.0400 (estimated from published rates, not reconciled to an invoice)',
            '    Unverified quotes: 1 (not found in the document; never used as evidence)'])
        fable = lines.index('  - Fable · Anthropic · answered; the reading was not used')
        self.assertIn('    Models: requested claude-fable-5-1 · returned claude-other-model', lines[fable:])
        self.assertIn('    Refusal reason: Answered by claude-other-model, not claude-fable-5-1.', lines[fable:])
        self.assertIn('    Estimated cost: not estimated (Corti reports usage in credits, not USD)', lines[:astra])

    def test_a_run_with_usage_and_no_estimate_says_not_estimated_never_no_usage(self):
        text = reports.render_txt(reports.snapshot(self.s.encounter, 'draft')).decode('utf-8')  # no pricing module
        lines = section(text, 'REVIEW PARTICIPANTS')
        astra = lines.index('  - Astra · OpenAI · answered; the reading was used')
        self.assertIn('    Estimated cost: not estimated (no published rate could be applied to the usage reported)',
                      lines[astra:astra + 9])

    def test_reference_retrieval_section(self):
        lines = section(self.txt(), 'REFERENCE RETRIEVAL')
        self.assertEqual(lines, [
            '  - 43239 · service date 2026-10-21',
            '    Fact: status = A · cms-pfs-rvu26d, release RVU26D, effective 2026-10-01 to 2026-12-31',
            '    Passage: cms-ncci-manual-test, release Revision 1/1/2026 · section Chapter VI §C · page 12 · '
            'pfs.endo_base 43235:',
            '        "Surgical endoscopy includes diagnostic endoscopy (synthetic test text)."',
            '    Lookup: 43239: cms-pfs-rvu26d RVU26D',
            '    Note: 43239: synthetic note.',
            '  Not connected: NCCI procedure-to-procedure edits (AMA licence agreement not accepted); AMA CPT '
            'descriptors and guidelines (no licence); Payer policies.'])

    def test_every_code_says_who_proposed_it_apart_from_its_check_and_its_decision(self):
        text = self.txt()
        undecided = section(text, 'UNDECIDED — REVIEW NOT COMPLETE')
        first = undecided.index('  1. 43239 · Upper GI endoscopy (EGD, esophagoscopy, POEM) · units 1')
        block = undecided[first:undecided.index('  2. 45385 · Colonoscopy · units 1')]
        self.assertIn('     Current decision: none', block)
        self.assertIn('     Proposed by: Corti, Astra, Fable', block)
        self.assertIn('     Reference check: passed — Present in the CMS fee schedule file: passed. NCCI '
                      'procedure-to-procedure edits are not connected, so bundling with other codes is not verified.',
                      block)
        second = undecided[undecided.index('  2. 45385 · Colonoscopy · units 1'):]
        self.assertIn('     Proposed by: Astra', second)
        self.assertTrue(any(line.startswith('     Reference check: attention — ') for line in second))
        excluded = section(text, 'EXCLUDED CANDIDATES')
        self.assertIn('     Proposed by: Corti', excluded)
        alternatives = section(text, reports.ALTERNATIVES_TITLE)
        self.assertEqual(alternatives, [
            '  - 45380 · Colonoscopy — proposed by Fable, not added as a proposal, never selectable: no exact evidence '
            'located for it', '     Proposed by: Fable'])
        # I4: a passing check and three proposers decide nothing - the reviewed report needs a member's decisions
        self.assertFalse(review.readiness(self.s.encounter)['reviewed'])

    def test_csv_trailing_columns(self):
        data = rows(reports.render_csv(reports.snapshot(self.s.encounter, 'draft')))
        self.assertEqual(data[0][-2:], ['proposed_by', 'reference_check'])
        self.assertEqual(data[0][:-2], list(reports.CSV_COLUMNS[:-2]))
        by_code = {row[8]: dict(zip(data[0], row)) for row in data[1:] if row[8]}
        self.assertEqual((by_code['43239']['proposed_by'], by_code['43239']['reference_check']),
                         ('corti;astra;fable', 'passed'))
        self.assertEqual((by_code['45385']['proposed_by'], by_code['45385']['reference_check']), ('astra', 'attention'))
        self.assertEqual((by_code['45380']['proposed_by'], by_code['45380']['reference_check']),
                         ('fable', 'not_verified'))
        self.assertEqual(by_code['43239']['decision'], '')  # proposed and checked, never approved by that
        coding = next(dict(zip(data[0], row)) for row in data if row[7] == 'coding_completeness')
        self.assertEqual((coding['proposed_by'], coding['reference_check']), ('', ''))

    def test_the_reviewed_report_keeps_the_three_statuses_apart(self):
        for key, action in (('sel:0', 'approve'), ('sel:1', 'reject'), ('exc:0', 'confirm')):
            self.s.decide(key, action)
        text = self.txt('reviewed')
        approved = section(text, 'APPROVED SELECTIONS')
        self.assertTrue(approved[0].startswith('  1. 43239 '))
        self.assertTrue(any(line.startswith('     Decision: approved by ') for line in approved))
        self.assertIn('     Proposed by: Corti, Astra, Fable', approved)
        rejected = section(text, 'REJECTED — EXCLUDED FROM APPROVED RESULTS')
        self.assertEqual(len(rejected), 1, rejected)  # one line per rejection, the proposers closing it
        self.assertTrue(rejected[0].startswith('  - 45385 · Colonoscopy — rejected by '), rejected)
        self.assertTrue(rejected[0].endswith(' · proposed by Astra'), rejected)
        data = rows(reports.render_csv(reports.snapshot(self.s.encounter, 'reviewed')))
        approved_row = next(dict(zip(data[0], row)) for row in data[1:] if row[8] == '43239')
        self.assertEqual((approved_row['item_list'], approved_row['decision'], approved_row['proposed_by'],
                          approved_row['reference_check']), ('approved', 'approve', 'corti;astra;fable', 'passed'))
        # the download verifier reads both formats of this report - a rejection's proposers, a participant's
        # alternative and the new sections included - as it reads every other
        self.s.encounter.refresh_from_db()
        api = json.loads(json.dumps(serializers.encounter_detail(self.s.encounter, self.s.membership(self.s.reviewer)),
                                    default=str))
        with mock.patch.dict(sys.modules, {'studio.participants.pricing': fake_pricing()}):
            snap = reports.snapshot(self.s.encounter, 'reviewed')
        failed = [f'{r.check}: {r.detail}' for r in
                  vd.check_txt('harness', 'reviewed.txt', reports.render_txt(snap).decode('utf-8'), 'reviewed', api)
                  + vd.check_csv('harness', 'reviewed.csv', reports.render_csv(snap).decode('utf-8'), 'reviewed', api)
                  if r.status == 'fail']
        self.assertEqual(failed, [])

    def test_provider_usage_lists_the_participant_runs_as_independent_reviews(self):
        lines = section(self.txt(), 'PROVIDER USAGE')
        astra = next(line for line in lines if line.startswith('  - astra · live · succeeded'))
        self.assertIn(' · independent review · ', astra)
        self.assertTrue(astra.endswith(' · used by this assessment'), astra)
        fable = next(line for line in lines if line.startswith('  - fable · live · succeeded'))
        self.assertTrue(fable.endswith(' · read by this assessment; its response was not used'), fable)


class CortiOnlyReportTests(TestCase):
    def test_participants_not_configured_and_nothing_retrieved(self):
        s = pf.scenario()
        enc = s.encounter
        review.persist_assessment(encounter=enc, revision=s.revision, context=s.context,
                                  routing_run=pf.routing(s.revision), provider_run=pf.provider_run(enc, s.revision),
                                  result=pf.standard_result(), retrieval=[],
                                  participants=[jobs.not_configured_record('astra'),
                                                jobs.not_configured_record('fable')])
        text = reports.render_txt(reports.snapshot(enc, 'draft')).decode('utf-8')
        lines = section(text, 'REVIEW PARTICIPANTS')
        self.assertIn('  - Astra · OpenAI · not configured on this installation', lines)
        self.assertIn('  - Fable · Anthropic · not configured on this installation', lines)
        self.assertEqual(section(text, 'REFERENCE RETRIEVAL')[0], '  - none retrieved')

    def test_a_participant_not_run_gives_its_reason_only_when_it_says_more_than_the_state(self):
        s = pf.scenario()
        enc = s.encounter
        held = jobs.PARTICIPANT_HELD_MESSAGE.format(label='Astra')
        review.persist_assessment(encounter=enc, revision=s.revision, context=s.context,
                                  routing_run=pf.routing(s.revision), provider_run=pf.provider_run(enc, s.revision),
                                  result=pf.standard_result(), retrieval=[],
                                  participants=[record('astra', 'not_run', reason=held),
                                                record('fable', 'not_run', reason=jobs.PARTICIPANT_NOT_RUN)])
        lines = section(reports.render_txt(reports.snapshot(enc, 'draft')).decode('utf-8'), 'REVIEW PARTICIPANTS')
        astra = lines.index('  - Astra · OpenAI · no request was made for this revision')
        self.assertEqual(lines[astra + 1], f'    Reason: {held}')
        fable = lines.index('  - Fable · Anthropic · no request was made for this revision')
        self.assertFalse(lines[fable + 1:] and lines[fable + 1].startswith('    Reason:'), lines[fable:])

    def test_an_assessment_recorded_before_the_harness_says_so(self):
        s = pf.scenario()
        pf.assess(s.encounter, pf.standard_result())
        text = reports.render_txt(reports.snapshot(s.encounter, 'draft')).decode('utf-8')
        lines = section(text, 'REVIEW PARTICIPANTS')
        self.assertIn('  - Astra · OpenAI · not recorded: this assessment predates the review participants', lines)
        self.assertEqual(lines[-1], '  This assessment was recorded before the review participants existed: only '
                                    'Corti was run.')
        self.assertEqual(section(text, 'REFERENCE RETRIEVAL')[0],
                         '  - none retrieved: this assessment was recorded before reference retrieval existed')


@override_settings(**LIVE, **BOTH)
class RealDownloadsTests(HarnessCase):
    """The server's own TXT and CSV of a harness encounter, read by ops/verify_downloads.py as a download is."""

    def test_the_download_verifier_still_passes_both_formats(self):
        recorded = []
        self.adapters['fable'].returned_model = 'claude-other-model'  # one participant refused
        with mock.patch('studio.jobs.reference_passages', fake_passages(recorded)):
            encounter_id = self.create()
            drain()
        encounter = self.encounter(encounter_id)
        reviewer = models.Membership.objects.get(user=self.reviewer, workspace=self.ws)
        for kind in ('draft', 'reviewed'):
            if kind == 'reviewed':  # a member approves each code: the reviewed report needs the member's decisions
                for proposal in self.client.get(f'/api/encounters/{encounter_id}').json()['assessment']['proposals']:
                    if 'approve' in proposal['allowed_actions']:
                        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                                             {'proposal_id': proposal['id'], 'action': 'approve',
                                              'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
                        self.assertEqual(response.status_code, 201, response.content)
                self.assertTrue(review.readiness(encounter)['reviewed'], review.readiness(encounter))
            encounter.refresh_from_db()
            api = json.loads(json.dumps(serializers.encounter_detail(encounter, reviewer), default=str))
            snap = reports.snapshot(encounter, kind)
            text, data = reports.render_txt(snap).decode('utf-8'), reports.render_csv(snap).decode('utf-8')
            failed = [f'{r.check}: {r.detail}' for r in vd.check_txt('harness', f'{kind}.txt', text, kind, api)
                      + vd.check_csv('harness', f'{kind}.csv', data, kind, api) if r.status == 'fail']
            self.assertEqual(failed, [], kind)
            self.assertIn('REVIEW PARTICIPANTS', text.splitlines())
            self.assertIn(f'    Fact: status =  · cms-pfs-test, release RVU26D, effective 2026-10-01 to 2026-12-31',
                          text.splitlines())
        self.assertIn('     Proposed by: Corti', section(text, 'APPROVED SELECTIONS'))
        # the participant's run in PROVIDER USAGE carries its mode: replayed answers never read as live output
        usage = section(text, 'PROVIDER USAGE')
        self.assertTrue(any(line.startswith('  - astra · REPLAY (recorded response, not live output) · succeeded')
                            for line in usage), usage)
        self.assertTrue(TIME_QUOTE in text)
        # harness@2 (HARNESS.md 12.6): Astra's peer review is listed as one, also replayed, and the report has its
        # PEER REVIEW and PARTICIPANT REFERENCES sections; Fable's refused first reading took no part in peer review
        self.assertTrue(any(line.startswith('  - astra · REPLAY (recorded response, not live output) · succeeded')
                            and ' · peer review · ' in line for line in usage), usage)
        self.assertFalse(any(line.startswith('  - fable ') and ' · peer review · ' in line for line in usage), usage)
        self.assertIn('PEER REVIEW', text.splitlines())
        self.assertIn('PARTICIPANT REFERENCES', text.splitlines())
