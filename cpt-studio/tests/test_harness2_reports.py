"""harness@2 in the reports (HARNESS.md 12.6, I4): the TXT's CONFIRMED FINDINGS, PEER REVIEW and PARTICIPANT REFERENCES
sections and the CSV's rows for them, the participants' references kept apart from REFERENCE RETRIEVAL, a phase-1
report, and a Corti-only report that carries none of it. The downloads are read by ops/verify_downloads.py, which must
pass them and must fail a tampered one.

Synthetic data only; no network. The rows are tests.test_harness2_api's (HARNESS.md 12.3 shapes).
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

from studio import candidates, jobs, models, reports, review, serializers
from tests.test_harness2_api import (BOTH, CECUM_QUOTE, DATE_QUOTE, FACT_REF, PASSAGE_REF, PREP_QUOTE, RECTUM_QUOTE,
                                     Harness2Case)
from tests.support import pipeline_factories as pf
from tests.test_participants_support import NOTE

_spec = importlib.util.spec_from_file_location('cpt_verify_downloads_harness2',
                                               Path(settings.BASE_DIR) / 'ops' / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_verify_downloads_harness2'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)

HARNESS1_TITLES = ('CODING COMPLETENESS', 'ENCOUNTER, SOURCE AND REVISION', 'ENCOUNTER CONTEXT', 'DOCUMENTED SERVICES',
                   'UNRESOLVED DOCUMENTED SERVICES — NO SUPPORTED PROPOSAL', 'CONFLICTS IN THE RECORD',
                   'REJECTED — EXCLUDED FROM APPROVED RESULTS', 'UNDECIDED — REVIEW NOT COMPLETE',
                   'EXCLUDED CANDIDATES',
                   'ALTERNATIVES — INFORMATIONAL, NEVER SELECTABLE', 'CHECKS', 'OPEN CLARIFICATIONS', 'NOT VERIFIED',
                   'REVIEW PARTICIPANTS', 'PROVIDER USAGE', 'REFERENCE SOURCES', 'REFERENCE RETRIEVAL',
                   'AUDIT — DECISION HISTORY')
HARNESS2_TITLES = (HARNESS1_TITLES[:12] + ('CONFIRMED FINDINGS',) + HARNESS1_TITLES[12:14]
                   + ('PEER REVIEW', 'PARTICIPANT REFERENCES') + HARNESS1_TITLES[14:])
WORDING = ('Participant wording.', 'Retrieved only by its first reading.', 'The NCCI endoscopy rule.',
           'The endoscopic base of the snare removal.', 'A rule this run never retrieved.',
           'appendiceal orifice seen')


def section(text, title):
    lines = text.split('\n')
    start = lines.index(title) + 1
    return lines[start:lines.index('', start)]


def titles(text):
    lines = text.split('\n')
    return [line for i, line in enumerate(lines) if i and not lines[i - 1] and line and not line.startswith(' ')
            and line == line.upper() and line not in (reports.SYNTHETIC_LINE,)]


def at(quote, page):
    start = NOTE.index(quote)
    return f'"{quote}" [chars {start}–{start + len(quote)}, page {page}]'


def rows_of(content):
    data = list(csv.reader(io.StringIO(content.decode('utf-8'), newline='')))
    return data[0], [dict(zip(data[0], row)) for row in data[1:]]


@override_settings(**BOTH)
class SectionTests(Harness2Case):
    def txt(self, kind='draft'):
        return reports.render_txt(reports.snapshot(self.encounter, kind)).decode('utf-8')

    def test_the_sections_and_their_order(self):
        self.assertEqual(titles(self.txt()), list(HARNESS2_TITLES))

    def test_peer_review(self):
        lines = section(self.txt(), 'PEER REVIEW')
        first = {c.fact: c for c in self.first.clarifications.all()}
        frozen = ' · '.join(f'{name} {value}' for name, value in self.reviews['astra'].frozen_inputs)
        self.assertEqual(lines[:12], [
            '  - Astra · answered in peer review; the review was used',
            f'    Run: {self.peer_runs["astra"].pk} · REPLAY (recorded response, not live output)',
            f'    Frozen inputs shown: {frozen}',
            f'    Answer to "{first["extent"].question}" (extent reached): cecum',
            f'      {at(CECUM_QUOTE, 1)}',
            f'    Answer to "{first["service_date"].question}" (service date): 2026-10-21',
            f'      {at(DATE_QUOTE, 1)}',
            f'    Answer to "{first["performed_status"].question}" (performed status): performed',
            f'      {at(RECTUM_QUOTE, 2)}',
            '    Position on 45380: supports',
            f'      {at(RECTUM_QUOTE, 2)}',
            '    Additional code 45381 · units 1 — proposed after peer review, never independent'])
        self.assertEqual(lines[12], f'      {at(PREP_QUOTE, 1)}')
        fable = lines.index('  - Fable · answered in peer review; the review was used')
        # its answer is stated in CPT Studio's words (the landmark its value names), never its own
        self.assertEqual(lines[fable + 3:fable + 5], [
            f'    Answer to "{first["extent"].question}" (extent reached): cecum', f'      {at(CECUM_QUOTE, 1)}'])
        text = self.txt()
        for words in WORDING:  # a participant's own wording never reaches a report
            self.assertNotIn(words, text)

    def test_participant_references_apart_from_reference_retrieval(self):
        text = self.txt()
        lines = section(text, 'PARTICIPANT REFERENCES')
        self.assertTrue(lines[0].startswith("  Each participant run's own tool results (retrieved)"))
        self.assertEqual(lines[1:], [
            f'  - Astra · independent reading · run {self.runs["astra"].pk}',
            f'    Retrieved: {FACT_REF} (fact · cms-pfs-rvu26d, release RVU26D, effective 2026-10-01 to 2026-12-31)',
            f'    Used: {FACT_REF} — retrieved by this run',
            f'    Used: {PASSAGE_REF} — cited, not retrieved by this run, so never shown as retrieved',
            f'  - Astra · peer review · run {self.peer_runs["astra"].pk}',
            f'    Retrieved: {PASSAGE_REF} (passage · cms-ncci-policy-manual-2026, release Revision 2026, effective '
            '2026-01-01 to 2026-12-31)',
            f'    Used: {PASSAGE_REF} — retrieved by this run',
            f'    Used: {FACT_REF} — cited, not retrieved by this run, so never shown as retrieved',
            f'  - Fable · independent reading · run {self.runs["fable"].pk}', '    Retrieved: none', '    Used: none',
            f'  - Fable · peer review · run {self.peer_runs["fable"].pk}', '    Retrieved: none', '    Used: none'])
        # the reconciliation's retrieval is its own section and names none of the participants' references
        retrieval = '\n'.join(section(text, 'REFERENCE RETRIEVAL'))
        self.assertNotIn(FACT_REF, retrieval)
        self.assertNotIn(PASSAGE_REF, retrieval)

    def test_review_participants_and_provider_usage_name_the_tool_loop_and_the_peer_runs(self):
        text = self.txt()
        participants_lines = section(text, 'REVIEW PARTICIPANTS')
        self.assertIn('    Exchanges: 2 · tool calls: 1', participants_lines)
        self.assertIn('    Exchanges: 1 · tool calls: 0', participants_lines)
        usage = [line for line in section(text, 'PROVIDER USAGE') if line.startswith('  - ')]
        peer = [line for line in usage if ' · peer review · ' in line]
        self.assertEqual(len(peer), 2, usage)
        self.assertTrue(all(line.endswith(' · used by this assessment') for line in peer), peer)
        self.assertTrue(all(' REPLAY (recorded response, not live output) ' in line for line in peer), peer)

    def test_confirmed_findings(self):
        self.assertEqual(section(self.txt(), 'CONFIRMED FINDINGS'),
                         ['  None: no reviewer has confirmed a finding for this revision.'])
        candidate = self.verified('extent')
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            self.assertEqual(self.confirm('extent', candidate).status_code, 201)
        confirmation = models.FindingConfirmation.objects.get()
        lines = section(self.txt(), 'CONFIRMED FINDINGS')
        self.assertRegex(lines[0], r'^  - Extent reached = cecum · 45385 \(sel:0\) · Colonoscopy — confirmed by '
                                   r'Reviewer2B \(human\) at \d{4}-\d\d-\d\dT[0-9:]+Z$')
        self.assertEqual(lines[1:], [
            f'    Confirmation: {confirmation.pk} · question {self.questions["extent"].pk}',
            f'    Passage: {at(CECUM_QUOTE, 1)}', '    Located by: Astra, Fable',
            f'    Attestation: {candidates.attestation("cecum")}',
            '    Effect: not read by this assessment, which was made before it'])
        # the re-assessment that reads it says so
        read = self.persist([self.entry(name, peer=True) for name in ('astra', 'fable')], replace(
            self.result(), completeness={'confirmations': {'applied': [{'ids': [str(confirmation.pk)]}],
                                                           'ignored': []}}))
        self.assertEqual(read.pk, self.encounter.current_assessment_id)
        self.assertIn('    Effect: read by this assessment', section(self.txt(), 'CONFIRMED FINDINGS'))
        # I4: a confirmation is a confirmed fact, never a decision on a code
        self.assertFalse(models.Decision.objects.exists())

    def test_a_confirmed_service_date_says_how_it_entered(self):
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            self.assertEqual(self.confirm('service_date').status_code, 201)
        snap = reports.snapshot(self.encounter, 'draft')
        (item,) = snap['confirmed_findings']
        self.assertEqual((item['fact'], item['value'], item['scope']), ('service_date', '2026-10-21', 'encounter'))
        self.assertTrue(item['effect'].startswith("entered as the member's service date through the encounter context"))
        lines = section(reports.render_txt(snap).decode('utf-8'), 'CONFIRMED FINDINGS')
        self.assertTrue(lines[0].startswith('  - Service date = 2026-10-21 · the encounter — confirmed by '), lines)

    def test_a_phase_1_report_says_the_peer_reviews_follow(self):
        self.persist([self.entry(name) for name in ('astra', 'fable')])
        text = self.txt()
        self.assertEqual(section(text, 'PEER REVIEW'),
                         ['  - none recorded for this assessment: its peer reviews follow it (phase 1)'])
        self.assertEqual(titles(text), list(HARNESS2_TITLES))
        # a participant whose first reading was not read takes no part in peer review
        entries = [self.entry('astra', peer=True), dict(self.entry('fable', peer=True), state='refused',
                                                        reason='The reading was not used: synthetic.')]
        self.persist(entries)
        lines = section(self.txt(), 'PEER REVIEW')
        fable = lines.index('  - Fable · no peer review')
        self.assertEqual(lines[fable + 2],
                         '    Reason: It takes no part in peer review: its first reading was not read.')


@override_settings(**BOTH)
class CsvTests(Harness2Case):
    def test_the_rows_beside_the_proposals_never_a_decision(self):
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            self.assertEqual(self.confirm('extent').status_code, 201)
        confirmation = models.FindingConfirmation.objects.get()
        header, rows = rows_of(reports.render_csv(reports.snapshot(self.encounter, 'draft')))
        self.assertEqual(header, list(reports.CSV_COLUMNS))
        by_list = {}
        for row in rows:
            by_list.setdefault(row['item_list'], []).append(row)
        (found,) = by_list['confirmed_finding']
        start = NOTE.index(CECUM_QUOTE)
        self.assertEqual({key: found[key] for key in ('code', 'family', 'status', 'exclusion_reason', 'evidence',
                                                      'proposed_by', 'reviewer', 'reviewer_kind', 'decision', 'checks',
                                                      'evidence_support')},
                         {'code': '45385', 'family': 'gi.colonoscopy', 'status': 'extent', 'exclusion_reason': 'cecum',
                          'evidence': f'"{CECUM_QUOTE}" [{start}-{start + len(CECUM_QUOTE)}, p1]',
                          'proposed_by': 'astra;fable', 'reviewer': self.reviewer.label(), 'reviewer_kind': 'human',
                          'decision': '', 'evidence_support': candidates.attestation('cecum'),
                          'checks': f'confirmation={confirmation.pk};clarification={self.questions["extent"].pk};'
                                    'scope=proposal'})
        answers = by_list['peer_answer']
        self.assertEqual(sorted((r['proposed_by'], r['status'], r['exclusion_reason']) for r in answers),
                         [('astra', 'settled', '2026-10-21'), ('astra', 'settled', 'cecum'),
                          ('astra', 'settled', 'performed'), ('fable', 'settled', 'cecum')])
        self.assertTrue(all(r['proposal_origin'] == 'peer_review' for r in answers))
        (position,) = by_list['peer_position']
        self.assertEqual((position['code'], position['status'], position['proposed_by']),
                         ('45380', 'supports', 'astra'))
        (added,) = by_list['peer_additional_code']
        self.assertEqual((added['code'], added['units'], added['status'], added['proposal_origin']),
                         ('45381', '1', 'proposed_after_peer_review', 'peer_review'))
        references = sorted((r['proposed_by'], r['proposal_origin'], r['status'], r['exclusion_reason'])
                            for r in by_list['participant_reference'])
        self.assertEqual(references, [('astra', 'independent', 'cited_not_retrieved', PASSAGE_REF),
                                      ('astra', 'independent', 'retrieved', FACT_REF),
                                      ('astra', 'independent', 'used', FACT_REF),
                                      ('astra', 'peer_review', 'cited_not_retrieved', FACT_REF),
                                      ('astra', 'peer_review', 'retrieved', PASSAGE_REF),
                                      ('astra', 'peer_review', 'used', PASSAGE_REF)])
        harness2 = [row for lists in reports.HARNESS2_LISTS for row in by_list.get(lists, [])]
        self.assertTrue(all(row['decision'] == '' for row in harness2))  # I4
        self.assertNotIn('Participant wording.', reports.render_csv(reports.snapshot(self.encounter, 'draft')).decode())


class CortiOnlyTests(TestCase):
    """An encounter with Astra and Fable disabled: its assessment records them 'not configured' (I1)."""

    def test_a_corti_only_report_carries_nothing_of_harness_2(self):
        s = pf.scenario()
        review.persist_assessment(
            encounter=s.encounter, revision=s.revision, context=s.context, routing_run=pf.routing(s.revision),
            provider_run=pf.provider_run(s.encounter, s.revision), result=pf.standard_result(), retrieval=[],
            participants=[jobs.not_configured_record('astra'), jobs.not_configured_record('fable')])
        snap = reports.snapshot(s.encounter, 'draft')
        text = reports.render_txt(snap).decode('utf-8')
        data = reports.render_csv(snap).decode('utf-8')
        self.assertFalse({'phase', 'peer_review', 'confirmed_findings', 'participant_references'} & set(snap))
        self.assertEqual(titles(text), list(HARNESS1_TITLES))
        self.assertFalse({row['item_list'] for row in rows_of(data.encode())[1]} & set(reports.HARNESS2_LISTS))
        for words in ('Exchanges:', 'peer review', 'CONFIRMED FINDINGS', 'PARTICIPANT REFERENCES'):
            self.assertNotIn(words, text)
        # the download verifier reads it as before: no harness@2 check, nothing failed
        s.encounter.refresh_from_db()
        api = json.loads(json.dumps(serializers.encounter_detail(s.encounter, s.membership(s.reviewer)), default=str))
        results = {r.check: r.status for r in vd.check_txt('h1', 'draft.txt', text, 'draft', api)
                   + vd.check_csv('h1', 'draft.csv', data, 'draft', api)}
        self.assertFalse({'txt.harness2_passages', 'txt.confirmed_findings', 'csv.harness2_passages',
                          'csv.confirmed_findings'} & set(results))
        self.assertEqual({check for check, status in results.items() if status == 'fail'}, set())


@override_settings(**BOTH)
class DownloadVerifierTests(Harness2Case):
    def checked(self, txt=None, csv_text=None):
        self.encounter.refresh_from_db()
        api = json.loads(json.dumps(serializers.encounter_detail(self.encounter, self.s_membership()), default=str))
        snap = reports.snapshot(self.encounter, 'draft')
        txt = txt(reports.render_txt(snap).decode('utf-8')) if callable(txt) else reports.render_txt(snap).decode()
        data = (csv_text(reports.render_csv(snap).decode('utf-8')) if callable(csv_text)
                else reports.render_csv(snap).decode('utf-8'))
        return {r.check: (r.status, r.detail) for r in vd.check_txt('h2', 'draft.txt', txt, 'draft', api)
                + vd.check_csv('h2', 'draft.csv', data, 'draft', api)}

    def s_membership(self):
        return models.Membership.objects.get(user=self.reviewer, workspace=self.ws)

    def confirmed(self):
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            self.assertEqual(self.confirm('extent').status_code, 201)

    def test_both_formats_pass_with_the_new_sections_and_rows(self):
        self.confirmed()
        results = self.checked()
        failed = {check: detail for check, (status, detail) in results.items() if status == 'fail'}
        self.assertEqual(failed, {})
        for check in ('txt.harness2_passages', 'txt.confirmed_findings', 'csv.harness2_passages',
                      'csv.confirmed_findings', 'csv.items'):
            self.assertEqual(results[check][0], 'pass', (check, results[check]))

    def test_a_tampered_passage_or_a_missing_confirmation_fails(self):
        self.confirmed()
        start = NOTE.index(CECUM_QUOTE)
        right = f'[chars {start}–{start + len(CECUM_QUOTE)}, page 1]'
        shifted = f'[chars {start + 1}–{start + len(CECUM_QUOTE) + 1}, page 1]'
        results = self.checked(txt=lambda text: text.replace(f'    Passage: "{CECUM_QUOTE}" {right}',
                                                             f'    Passage: "{CECUM_QUOTE}" {shifted}', 1))
        self.assertEqual(results['txt.harness2_passages'][0], 'fail')
        dropped = self.checked(txt=lambda text: '\n'.join(line for line in text.split('\n')
                                                          if not line.startswith('    Confirmation: ')))
        self.assertEqual(dropped['txt.confirmed_findings'][0], 'fail')
        rows = self.checked(csv_text=lambda text: text.replace(f'"confirmation=', '"confirmations=', 1))
        self.assertEqual(rows['csv.confirmed_findings'][0], 'fail')
        moved = self.checked(csv_text=lambda text: text.replace(f'[{start}-{start + len(CECUM_QUOTE)}, p1]',
                                                                f'[{start + 2}-{start + len(CECUM_QUOTE)}, p1]', 1))
        self.assertEqual(moved['csv.harness2_passages'][0], 'fail')

    def test_a_persisted_confirmation_the_report_leaves_out_fails(self):
        self.confirmed()
        results = self.checked(txt=lambda text: text.replace('\nCONFIRMED FINDINGS\n', '\nCONFIRMED FINDING\n', 1))
        self.assertEqual(results['txt.confirmed_findings'][0], 'fail')
        self.assertIn('section missing', results['txt.confirmed_findings'][1])
