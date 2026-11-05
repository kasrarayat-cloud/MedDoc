"""Write the synthetic samples the verification tooling's offline tests read, to the contract they verify.

    python3 -B ops/verification/samples/make_samples.py [--check]

One fictional two-lesion colonoscopy, as the platform-operator API serves it (today's full encounter view and trace,
operator-encounter.json / operator-trace.json), as the customer API serves it (cpt-studio/CORE-UX-DESIGN.md section 7,
customer-encounter.json and customer-session.json), as the customer page draws it (the DOM contract of section 8,
customer-page.html and, with a few details needed, customer-page-details.html), and its customer reports
(cpt-studio-customer-report@1, section 5: customer-report-{approved,draft}.{txt,csv}). Nothing here is a fixture of
the product: the product's own fixtures are its serializers' (tests/fixtures/customer/). These samples exist so the walk
(ops/verify_browser.cjs), the download verifier (ops/verify_downloads.py) and the customer scanner
(ops/scan_customer.py) are each tested against one agreed rendering of the contract.

The operator view is what the walk's operator account reads: ops-agent holds a grant and NO membership (CORE-UX-DESIGN.md
9, decision (h)), so the view allows no review action of its own (studio.operator.ReadOnlyAccess) - the tools judge the
customer's actions by what the server accepts from the customer, never by the operator's (refutation round 2, L3-5). Each
code the customer page lists carries the view's statement of that page ('customer': serializers.customer_codes - its
number, status, labels and the actions a member who may review is allowed), which the tools judge the page and the
exports against (refutation round 3, B-02 and B-03).

The customer reports are never written in a grammar of this script's own (refutation round 2, L3-1: they once were, and
every genuine export failed the checks the samples passed). This script writes the report SNAPSHOTS
(customer-report-snapshots.json: what studio.reports.customer_snapshot builds for this encounter, and the generation
stamp), and the four report files are studio/reports.py's own render_customer_txt / render_customer_csv bytes of them:

    CPT_STUDIO_WRITE_SAMPLES=1 python manage.py test tests.test_cux_r2_reports.SampleReportTests   # writes them
    python manage.py test tests.test_cux_r2_reports                                               # pins them

--check: write nothing; exit 1 when a committed sample this script writes differs from what it writes (the tests run
it). Stdlib only. Every value is synthetic.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
SYNTHETIC_LINE = 'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS'
FORMAT = 'cpt-studio-customer-report@1'
AGENT = 'CPT Studio review agent (automated agent)'
AGENT_SUB = 'Agent-executed synthetic review — not clinical approval'
NOTE = 'Agent-executed synthetic verification review'
ACKNOWLEDGEMENT = ('I am an automated agent. This agent-executed synthetic review is not clinical approval or billing '
                   'advice.')

DATE_LINE = 'Date of service: 2026-11-03'
CECUM = 'The colonoscope was advanced to the cecum.'
COL1 = 'COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.'
COL2 = 'COL-2: a 9 mm sigmoid colon polyp was removed with a cold snare.'
PLAN = 'Plan: upper endoscopy is scheduled next month.'
NO_EM = 'No separate office evaluation and management encounter is documented on this date.'
TEXT = '\n'.join([BANNER, 'Colonoscopy report (fictional)', 'Patient: Synthetic Patient Nine (fictional)', DATE_LINE,
                  'Procedure: Colonoscopy with polyp removal.', CECUM, COL1, COL2, PLAN, NO_EM]) + '\n'

ENC = '7d0c4a52-2f6e-4c39-9a51-3b1e6f0d2a11'
REV = '0e5d1c6b-8a47-4f2e-b3d9-5c6a7b8d9e10'
ASM = '4b2a1c0d-9e8f-4a7b-8c6d-5e4f3a2b1c0d'
P80, P85, P78, P39 = ('a1f0b2c3-0001-4d5e-8f60-718293a4b5c6', 'a1f0b2c3-0002-4d5e-8f60-718293a4b5c6',
                      'a1f0b2c3-0003-4d5e-8f60-718293a4b5c6', 'a1f0b2c3-0004-4d5e-8f60-718293a4b5c6')
D80, D85 = 'd0e1f2a3-0001-4b5c-9d6e-7f8091a2b3c4', 'd0e1f2a3-0002-4b5c-9d6e-7f8091a2b3c4'
RUNS = {name: f'c0ffee00-{n:04d}-4a5b-8c6d-7e8f9a0b1c2d' for n, name in enumerate(
    ('corti', 'astra', 'fable', 'astra_peer', 'fable_peer'), start=1)}
REPORTS = {('draft', 'txt'): 'b0b0b0b0-0001-4c4c-8d8d-9e9e9e9e9e01', ('draft', 'csv'): 'b0b0b0b0-0002-4c4c-8d8d-9e9e9e9e9e02',
           ('approved', 'txt'): 'b0b0b0b0-0003-4c4c-8d8d-9e9e9e9e9e03',
           ('approved', 'csv'): 'b0b0b0b0-0004-4c4c-8d8d-9e9e9e9e9e04'}
LEGACY_REPORT = 'b0b0b0b0-0009-4c4c-8d8d-9e9e9e9e9e09'
CREATED = '2026-11-03T22:00:00+00:00'
DECIDED = {P80: '2026-11-03T22:05:00+00:00', P85: '2026-11-03T22:05:30+00:00'}
GENERATED = '2026-11-03T22:10:00+00:00'
TITLE = 'Synthetic colonoscopy (two lesions)'
MODIFIER_TEXT = ('The two removals are documented on separate lesions (COL-1 ascending colon, COL-2 sigmoid colon). The CMS '
                 'claims manual example allows a distinct-lesion modifier for them; procedure-to-procedure edits and '
                 'payer modifier policies are not checked. Choose a modifier only if it applies.')
MODIFIER_SOURCE = 'CMS claims manual Pub. 100-04 ch. 12 (Rev. 13753, 2026-05-07)'
LIMITATIONS = ['CPT descriptions are withheld: no licensed CPT description is connected.',
               'Procedure-to-procedure edits and payer modifier policies are not checked.',
               'Whether each service was performed is read from the document; review the whole document.']
SUMMARIES = {P80: 'The colonoscopy documents removal of the 4 mm ascending colon polyp (COL-1) with cold biopsy forceps.',
             P85: 'The colonoscopy documents removal of the 9 mm sigmoid colon polyp (COL-2) with a cold snare.'}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def span(passage: str, **extra) -> dict:
    start = TEXT.index(passage)
    return {'context_index': 0, 'start': start, 'end': start + len(passage), 'text': passage, 'exact': True, 'page': 1,
            **extra}


def quote(passage: str) -> dict:
    start = TEXT.index(passage)
    return {'text': passage, 'start': start, 'end': start + len(passage), 'page': 1, 'exact': True}


# --- the platform-operator view (today's serializers.encounter_detail; /ops/api/encounters/<id>) -------------------

# The operator account reads with no membership (studio.operator.ReadOnlyAccess): the view allows it no action of its own.
OPERATOR_PERMISSIONS = {'can_review': False, 'is_owner': False, 'can_confirm': False}


def op_decision(pid: str, code: str, modifiers: list) -> dict:
    return {'id': D80 if pid == P80 else D85, 'proposal_id': pid, 'code': code, 'action': 'approve', 'note': NOTE,
            'reviewer': AGENT, 'reviewer_kind': 'agent', 'created_at': DECIDED[pid], 'decided_at': DECIDED[pid],
            'carried_at': None, 'acknowledgement': ACKNOWLEDGEMENT, 'carried_from': None, 'invalidated': None,
            'revision_number': 1, 'modifiers': modifiers}


def op_customer(number: int) -> dict:
    """What the customer page shows for an agent's approval, as the operator view states it (serializers.customer_codes:
    customer_api.code_rows' row - Approved, labelled agent review, revoke only for a member who may review)."""
    return {'number': number, 'status': 'approved', 'status_label': 'Approved', 'sub_label': AGENT_SUB,
            'reviewer_actions': ['revoke']}


def op_proposal(pid, code, bucket, status, evidence, *, decision=None, support=None, reinstatable=False,
                customer=None) -> dict:
    return {'id': pid, 'key': f'{code}:{pid[-4:]}', 'bucket': bucket, 'code': code, 'code_kind': 'cpt1',
            'family': 'gi.egd' if code.startswith('43') else 'gi.colonoscopy',
            'family_label': 'Upper GI endoscopy' if code.startswith('43') else 'Colonoscopy',
            'eyebrow': 'UPPER GI ENDOSCOPY' if code.startswith('43') else 'COLONOSCOPY', 'supported': True,
            'profile_version': 'gi.colonoscopy@3', 'status': status, 'status_label': status.replace('_', ' '),
            'exclusion_reason': 'Documented as planned, not as performed on the date of service.' if bucket == 'excluded'
            else '', 'reinstatable': reinstatable,
            'descriptor': {'status': 'withheld', 'label': 'Description withheld.'}, 'evidence': evidence,
            'rationale': 'Selected by corti. 1 exact evidence passage.', 'units': 1,
            'checks': [{'id': 'evidence.exact', 'status': 'pass', 'label': 'Exact evidence', 'detail': '',
                        'source': 'cpt-studio:provider@1'},
                       {'id': 'pfs.endoscopic_family', 'status': 'pass', 'label': 'Endoscopic family', 'detail': '',
                        'source': 'cms-pfs-rvu-2026@1'}],
            'modifier_considerations': ['Two lesions in different parts of the colon: a distinct-lesion modifier (59 or '
                                        'XS) may apply. NCCI edits are not connected; no modifier is assigned.']
            if code in ('45380', '45385') else [],
            'support': support or {}, 'clarification_ids': [], 'decision': decision,
            'decision_state': 'approved' if decision else 'undecided', 'reinstated_by': None,
            'allowed_actions': [], 'approve_withheld_by': None, 'overlay_reason': '', 'customer': customer,
            'proposed_by': ['corti', 'astra', 'fable'], 'listed_by': [], 'corti_relation': '',
            'participant_positions': [], 'reference_check': {'state': 'checked', 'detail': ''}, 'retrieval': [],
            'phases': {'astra': 'independent'}, 'confirmed': []}


def support_for(passage: str, detail: str) -> dict:
    # reconcile.support: a 'pass' reading's source is empty - the provider's own passage (evidence[0]) shows the act
    return {'origin': 'primary', 'service': 'colon-a', 'family': 'gi.colonoscopy', 'state': 'performed', 'reason': '',
            'detail': detail, 'acts': [{'id': 'act-1', 'kind': 'removal', 'label': detail}], 'status': 'pass',
            'supporting': [0], 'unrelated': [], 'detail_support': '', 'source': []}


def run(name: str, provider: str, purpose: str, model: str, returned: str, usage: dict, n: int) -> dict:
    return {'id': RUNS[name], 'provider': provider, 'mode': 'live', 'state': 'succeeded', 'http_status': 200,
            'latency_ms': 1200 + n, 'usage': usage, 'usage_basis': 'reported',
            'request_sha256': sha(f'request {name}'), 'response_sha256': sha(f'response {name}'), 'reused_from': None,
            'error': '', 'reconciled': False, 'created_at': f'2026-11-03T22:00:{10 + n:02d}+00:00', 'purpose': purpose,
            'scope_items': [], 'requested_model': model, 'returned_model': returned}


def operator_encounter() -> dict:
    proposals = [
        op_proposal(P80, '45380', 'selected', 'ready', [span(COL1)], decision=op_decision(P80, '45380', []),
                    support=support_for(COL1, SUMMARIES[P80]), customer=op_customer(1)),
        op_proposal(P85, '45385', 'selected', 'ready', [span(COL2)], decision=op_decision(P85, '45385', ['XS']),
                    support=support_for(COL2, SUMMARIES[P85]), customer=op_customer(2)),
        op_proposal(P78, '45378', 'alternative', 'informational', [span(CECUM)]),
        op_proposal(P39, '43239', 'excluded', 'excluded', [span(PLAN)]),
    ]
    stages = [{'kind': kind, 'state': 'succeeded', 'error': '', 'finished_at': f'2026-11-03T22:00:{n:02d}+00:00'}
              for n, kind in enumerate(('extract', 'analyze', 'predict', 'astra', 'fable', 'assess', 'astra_peer',
                                        'fable_peer', 'assess'), start=1)]
    participants = [
        # Corti's coding API names no model (review.HARNESS_PARTICIPANTS: model ''), and none answers by name: the
        # live operator view of 2026-11-05 serves exactly this, so the walk is tested against it
        {'name': 'corti', 'label': 'Corti', 'vendor': 'Corti', 'model': '', 'state': 'done',
         'detail': 'Corti returned 3 codes.', 'run_id': RUNS['corti'], 'returned_model': '',
         'usage': {'creditsConsumed': 3}, 'usage_basis': 'reported', 'estimated_cost_usd': None,
         'codes': ['45380', '45385', '45378'], 'unverified_quotes': 0, 'reused': False},
        {'name': 'astra', 'label': 'Astra', 'vendor': 'OpenAI', 'model': 'gpt-6-astra', 'state': 'done',
         'detail': 'Astra read the document.', 'run_id': RUNS['astra'], 'returned_model': 'gpt-6-astra-2026-10-01',
         'usage': {'input_tokens': 2100, 'output_tokens': 420}, 'usage_basis': 'reported', 'estimated_cost_usd': 0.0412,
         'codes': ['45380', '45385'], 'unverified_quotes': 0, 'reused': False,
         'peer': {'state': 'done', 'run_id': RUNS['astra_peer'], 'codes_added': [], 'unverified_quotes': 0},
         'references': {'retrieved': [], 'used': []}, 'peer_references': {'retrieved': [], 'used': []}},
        {'name': 'fable', 'label': 'Fable', 'vendor': 'Anthropic', 'model': 'claude-fable-5-1', 'state': 'done',
         'detail': 'Fable read the document.', 'run_id': RUNS['fable'], 'returned_model': 'claude-fable-5-1',
         'usage': {'input_tokens': 2300, 'output_tokens': 510}, 'usage_basis': 'reported', 'estimated_cost_usd': 0.0533,
         'codes': ['45380', '45385'], 'unverified_quotes': 0, 'reused': False,
         'peer': {'state': 'done', 'run_id': RUNS['fable_peer'], 'codes_added': [], 'unverified_quotes': 0},
         'references': {'retrieved': [], 'used': []}, 'peer_references': {'retrieved': [], 'used': []}},
    ]
    runs = [run('corti', 'corti', 'primary', '', '', {'creditsConsumed': 3}, 1),
            run('astra', 'astra', 'independent', 'gpt-6-astra', 'gpt-6-astra-2026-10-01',
                {'input_tokens': 2100, 'output_tokens': 420}, 2),
            run('fable', 'fable', 'independent', 'claude-fable-5-1', 'claude-fable-5-1',
                {'input_tokens': 2300, 'output_tokens': 510}, 3),
            run('astra_peer', 'astra', 'peer_review', 'gpt-6-astra', 'gpt-6-astra-2026-10-01',
                {'input_tokens': 2600, 'output_tokens': 300}, 4),
            run('fable_peer', 'fable', 'peer_review', 'claude-fable-5-1', 'claude-fable-5-1',
                {'input_tokens': 2700, 'output_tokens': 280}, 5)]
    history = [{**proposals[0]['decision']}, {**proposals[1]['decision']}]
    reports = [{'id': REPORTS[key], 'kind': key[0], 'fmt': key[1], 'filename': f'CPT-Studio-{key[0]}.{key[1]}',
                'sha256': sha(f'report {key}'), 'generated_at': GENERATED, 'generated_by': AGENT,
                'download_url': f'/api/reports/{REPORTS[key]}/download'} for key in REPORTS]
    return {
        'id': ENC, 'title': TITLE, 'state': 'reviewed', 'state_label': 'Reviewed', 'service_date': '2026-11-03',
        'service_date_conflict': False, 'service_date_asked': False, 'service_date_evidence': [span(DATE_LINE)],
        'families': ['Colonoscopy'], 'source_kind': 'paste', 'open_clarifications': 0, 'coding_state': 'complete',
        'queue_reasons': [], 'created_at': CREATED, 'created_by': AGENT,
        'permissions': dict(OPERATOR_PERMISSIONS),
        'harness': {'participants': participants, 'phase': 2,
                    'reference_validation': {'state': 'done', 'codes_checked': 2, 'passages': 4,
                                             'sources': [{'key': 'cms-pfs-rvu-2026'}]},
                    'clarification': {'open': 0}, 'final': {'state': 'reviewed', 'label': 'Reviewed'}},
        'revision': {'id': REV, 'number': 1, 'kind': 'paste', 'revisions_total': 1, 'created_at': CREATED,
                     'source_file': None, 'addendum_text': '', 'addendum_offset': None,
                     'extraction': {'status': 'ok', 'method': 'text', 'messages': [], 'ocr_pages': [], 'page_count': 1,
                                    'engine': 'text/plain@1'},
                     'text': TEXT, 'text_sha256': sha(TEXT), 'pages': [{'page': 1, 'start': 0, 'end': len(TEXT)}]},
        'context': {'facts': {'service_date': {'name': 'service_date', 'value': '2026-11-03', 'origin': 'document',
                                               'evidence': [span(DATE_LINE)], 'note': '', 'member_conflict': False,
                                               'date_asked': False}},
                    'user_values': {}},
        'routing': {'version': 'routing-2026-11@4', 'document_kind': 'procedure_report', 'families': [
            {'family': 'gi.colonoscopy', 'label': 'Colonoscopy', 'supported': True, 'status': 'performed',
             'mentions': [{'status': 'performed', 'section': 'procedure', 'cues': [], 'span': span(CECUM)}],
             'facts': [], 'missing': []},
            {'family': 'gi.egd', 'label': 'Upper GI endoscopy', 'supported': True, 'status': 'planned',
             'mentions': [{'status': 'planned', 'section': 'plan', 'cues': [], 'span': span(PLAN)}], 'facts': [],
             'missing': []}]},
        'pipeline': {'busy': False, 'can_stop': False, 'can_resume': False, 'stopped_by_member': False, 'stages': stages},
        'provider_runs': runs, 'state_run': None,
        'second_review': {'available': False, 'can_request': False, 'items': [], 'reason': ''},
        'assessment': {'id': ASM, 'profiles_version': 'gi-profiles@7', 'engine_version': 'engine-2026.11.03@1',
                       'created_at': CREATED, 'proposals': proposals,
                       'encounter_checks': [{'id': 'participants.summary', 'status': 'pass', 'label': 'Independent checks',
                                             'detail': 'Astra (OpenAI, gpt-6-astra) read the document.',
                                             'source': 'cpt-studio:participants@1'}],
                       'unsupported': [], 'reference_sources': [{'key': 'cms-pfs-rvu-2026', 'sha256': sha('pfs'),
                                                                 'url': 'https://www.cms.gov/pfs/2026'}],
                       'summary': {}, 'services': {}, 'completeness': {'state': 'complete', 'unresolved_items': []},
                       'second_run': None},
        'clarifications': [], 'confirmations': [], 'decisions': {'history': history},
        'readiness': {'draft': True, 'reviewed': True, 'blockers': []}, 'coding': {'state': 'complete'},
        'reports': reports, 'activity': [],
    }


def operator_trace() -> dict:
    def trace_run(name, provider, model, returned, n):
        return {'id': RUNS[name], 'state': 'succeeded', 'sent': True, 'mode': 'live', 'purpose': 'independent',
                'run_identity': f'9f8e7d6c-{n:04d}-4b3a-8c7d-6e5f4a3b2c1d', 'authorization_ref': 'owner-ruling-2026-10-23',
                'requested_by': AGENT, 'adapter_version': f'{provider}-reader@cptstudio-3',
                'endpoint': f'https://api.example.invalid/{provider}/v1', 'requested_model': model,
                'returned_model': returned, 'request_id': f'req_{name}0123456789',
                'response_id': f'resp_{name}0123456789', 'http_status': 200, 'latency_ms': 1201, 'usage': {},
                'usage_basis': 'reported', 'estimated_cost_usd': 0.04, 'request_sha256': sha(f'request {name}'),
                'response_sha256': sha(f'response {name}'), 'response_bytes': 2048, 'created_at': CREATED,
                'finished_at': CREATED, 'error': '', 'reused_from': None, 'reconciled': False, 'reading': None,
                'review': None, 'exchanges': [{'turn': 1, 'state': 'succeeded', 'http_status': 200, 'latency_ms': 900,
                                               'usage': {}, 'request_sha256': sha(f'exchange {name}'),
                                               'response_sha256': sha(f'exchange answer {name}'),
                                               'provider_request_id': f'msg_{name}9876543210',
                                               'response_id': f'chatcmpl-{name}9876543210', 'error': '',
                                               'tool_calls': [{'call_id': f'call_{name}55555555', 'tool': 'search',
                                                               'arguments': {}, 'refs': [],
                                                               'result_sha256': sha(f'tool {name}'),
                                                               'executed_at': CREATED}]}]}
    def corti_trace_run():
        # the live trace of 2026-11-05 (run d24ae7b3, key by key): Corti's run names no model and no response id, and has
        # no exchanges; it is identified by its endpoint, adapter version and run identity
        return {**trace_run('corti', 'corti', '', '', 0), 'purpose': 'primary', 'adapter_version': 'corti-coding-v2@cptstudio-1',
                'endpoint': 'https://api.example.invalid/corti/v2/tools/coding/', 'response_id': '',
                'usage': {'creditsConsumed': 3}, 'usage_basis': 'provider_reported_credits_not_usd',
                'estimated_cost_usd': None, 'exchanges': []}
    return {'encounter': {'id': ENC, 'title': TITLE},
            'revision': {'id': REV, 'number': 1, 'text_sha256': sha(TEXT)},
            'participants': [{'name': 'corti', 'label': 'Corti', 'vendor': 'Corti', 'model': '', 'runs': [corti_trace_run()]},
                             {'name': 'astra', 'label': 'Astra', 'vendor': 'OpenAI', 'model': 'gpt-6-astra',
                              'runs': [trace_run('astra', 'astra', 'gpt-6-astra', 'gpt-6-astra-2026-10-01', 1)]},
                             {'name': 'fable', 'label': 'Fable', 'vendor': 'Anthropic', 'model': 'claude-fable-5-1',
                              'runs': [trace_run('fable', 'fable', 'claude-fable-5-1', 'claude-fable-5-1', 2)]}],
            'assessments': [{'id': ASM, 'created_at': CREATED, 'current': True, 'phase': 2, 'final': True,
                             'frozen': [['astra reading', sha('frozen astra')], ['fable reading', sha('frozen fable')]]}],
            'retrieval': [], 'reconciliation': []}


# --- the customer view (CORE-UX-DESIGN.md section 7) ----------------------------------------------------------------

def customer_code(pid: str, number: int, code: str, passage: str, modifiers: list) -> dict:
    return {'id': pid, 'number': number, 'code': code, 'units': 1, 'modifiers': modifiers,
            'modifier_review': {'options': ['59', 'XS'], 'text': MODIFIER_TEXT, 'sources': [MODIFIER_SOURCE]},
            'status': 'approved', 'status_label': 'Approved', 'sub_label': AGENT_SUB, 'summary': SUMMARIES[pid],
            'why': {'quotes': [quote(passage)],
                    'qualifications': ['Removed from a separate lesion; see the modifier review.']},
            'detail_ids': [], 'allowed_actions': ['revoke'],
            'decision': {'action': 'approve', 'by': AGENT, 'by_kind': 'agent', 'at': DECIDED[pid], 'note': NOTE,
                         'modifiers': modifiers}}


def customer_encounter() -> dict:
    date_start = TEXT.index(DATE_LINE)
    steps = [{'key': key, 'label': label, 'state': 'done', 'started_at': f'2026-11-03T22:00:{n:02d}+00:00',
              'finished_at': f'2026-11-03T22:00:{n + 1:02d}+00:00'}
             for n, (key, label) in enumerate((('reading', 'Reading your document'),
                                               ('identifying', 'Identifying procedures'),
                                               ('checking', 'Checking suggested codes'),
                                               ('preparing', 'Preparing your results')), start=1)]
    return {
        'id': ENC, 'title': TITLE, 'created_at': CREATED, 'updated_at': GENERATED, 'state': 'reviewed',
        'state_label': 'Reviewed', 'permissions': {'can_review': True},
        'document': {'kind': 'paste', 'name': None, 'media_type': 'text/plain', 'size': None, 'page_count': 1,
                     'revision': 1, 'text': TEXT, 'pages': [{'page': 1, 'start': 0, 'end': len(TEXT)}],
                     'reading': {'status': 'ok', 'label': 'Text read', 'messages': []}, 'original_url': None},
        'service_date': {'value': '2026-11-03', 'source': 'document', 'document_value': '2026-11-03',
                         'document_quote': {'text': DATE_LINE, 'start': date_start, 'end': date_start + len(DATE_LINE)},
                         'entered_value': None, 'conflict': False, 'can_use_document_date': False},
        'progress': {'phase': 'completed', 'busy': False, 'steps': steps, 'active_detail': '',
                     'started_at': '2026-11-03T22:00:01+00:00', 'finished_at': '2026-11-03T22:00:05+00:00',
                     'server_time': GENERATED, 'slow': False, 'message': 'Your results are ready.', 'can_stop': False,
                     'can_resume': False, 'can_leave': True, 'error': None},
        'checks': [{'key': 'document_review', 'label': 'Document review', 'state': 'done'},
                   {'key': 'independent_checks', 'label': 'Independent checks', 'state': 'done'},
                   {'key': 'coding_validation', 'label': 'Coding validation', 'state': 'done'}],
        'codes': [customer_code(P80, 1, '45380', COL1, []), customer_code(P85, 2, '45385', COL2, ['XS'])],
        'other_codes': [{'code': '45378', 'reason': 'Considered, not suggested: a diagnostic colonoscopy is included '
                                                   'when a removal is coded.'}],
        'not_separately_coded': [],
        'details_needed': [], 'unresolved': [], 'recheck': {'available': False, 'can_request': False},
        'limitations': LIMITATIONS,
        'readiness': {'draft': True, 'approved': True, 'blockers': []},
        'reports': [{'id': REPORTS[key], 'kind': key[0], 'fmt': key[1], 'filename': f'CPT-Studio-{key[0]}.{key[1]}',
                     'generated_at': GENERATED, 'generated_by': AGENT,
                     'download_url': f'/api/reports/{REPORTS[key]}/download', 'current': True} for key in REPORTS],
        'activity': [{'event': 'decision.recorded', 'summary': 'A review decision was recorded', 'actor': AGENT,
                      'actor_kind': 'agent', 'at': DECIDED[P80]}],
    }


def customer_session() -> dict:
    return {'user': {'id': '5e6f7a8b-1111-4c2d-9e3f-4a5b6c7d8e9f', 'label': AGENT, 'initials': 'CS',
                     'actor_kind': 'agent'},
            'workspace': {'id': '2b3c4d5e-2222-4f6a-8b7c-9d0e1f2a3b4c', 'name': 'Gastroenterology'},
            'role': 'reviewer', 'can_review': True, 'acknowledgement': ACKNOWLEDGEMENT,
            'counts': {'documents': 1, 'queue': 0}, 'synthetic_only': True}


# --- the customer page (CORE-UX-DESIGN.md section 8) ----------------------------------------------------------------

def esc(text) -> str:
    return html.escape(str(text), quote=True)


def row_html(code: dict) -> str:
    quotes = ''.join(f'<blockquote class="why-quote" data-start="{q["start"]}" data-end="{q["end"]}" '
                     f'data-page="{q["page"]}">“{esc(q["text"])}”</blockquote>' for q in code['why']['quotes'])
    qualifications = ''.join(f'<p class="why-qualification">{esc(q)}</p>' for q in code['why']['qualifications'])
    buttons = ''.join(f'<button type="button" class="button" data-decision="{a}" data-proposal="{code["id"]}">'
                      f'{"Undo decision" if a == "revoke" else a.title()}</button>' for a in code['allowed_actions'])
    modifiers = f'Modifier {", ".join(code["modifiers"])}' if code['modifiers'] else ''
    return (f'<li class="result-row" id="card-{code["id"]}" data-proposal="{code["id"]}" data-code="{code["code"]}" '
            f'data-status="{code["status"]}"><span class="result-number">{code["number"]}.</span> '
            f'<span class="result-code">{code["code"]}</span> <span class="result-units">{code["units"]} unit</span> '
            f'<span class="result-modifiers">{esc(modifiers)}</span> '
            f'<span class="status" data-status="{code["status"]}">{esc(code["status_label"])}</span> '
            f'<span class="result-sub">{esc(code["sub_label"])}</span>'
            f'<p class="result-summary">{esc(code["summary"])}</p>'
            f'<details class="why-code"><summary>Why this code?</summary>{quotes}{qualifications}</details>'
            f'<div class="result-actions">{buttons}</div></li>')


def details_html(details: list) -> str:
    if not details:
        return ''
    rows = []
    for detail in details:
        controls = ''
        if detail['control'] == 'date':
            controls += (f'<p class="detail-document-date">Document: {esc(detail["document_value"] or "not stated")}</p>'
                         f'<p class="detail-entered-date">You entered: {esc(detail["entered_value"] or "nothing")}</p>'
                         f'<input type="date" data-detail-input value="{esc(detail["entered_value"] or "")}">')
            # app.js dateControl: "Use document date" only where the row itself offers it (its choices), never because
            # a document date exists; and a date row's radios are its documented DATES only (documentedDates)
            if detail['document_value'] and any(choice['value'] == 'use_document' for choice in detail['choices']):
                controls += '<button type="button" data-action="use-document-date">Use document date</button>'
        radios = ([c for c in detail['choices'] if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(c['value']))]
                  if detail['control'] == 'date' else detail['choices'])
        for choice in radios:
            controls += (f'<label><input type="radio" name="detail-{detail["id"]}" value="{esc(choice["value"])}"> '
                         f'{esc(choice["label"])}</label>')
        for allowed in detail['allow']:
            words = {'not_documented': 'Not documented', 'cannot_confirm': 'Cannot confirm'}[allowed]
            controls += f'<button type="button" data-detail-choice="{allowed}">{words}</button>'
        saved = (f'<p class="detail-saved">Saved: {esc(detail["saved"]["label"])} by {esc(detail["saved"]["by"])}</p>'
                 if detail['saved'] else '')
        rows.append(f'<div class="detail-row" data-detail="{detail["id"]}" data-fact="{detail["fact"]}">'
                    f'<p class="detail-prompt">{esc(detail["prompt"])}</p>{controls}{saved}'
                    f'<p class="detail-affects">Affects {esc(", ".join(detail["affects"]))}</p></div>')
    return ('<section class="details-panel"><h2>A few details needed</h2>' + ''.join(rows)
            + '<button type="button" data-action="save-details">Save details</button></section>')


# The phases the page draws as its whole progress panel (app.js PANEL_PHASES); every other phase is one compact line:
# its title, the time it took and - for a detail asked or a limitation - the server's message (app.js progressPanel;
# the 2026-11-05 acceptance walk found this sample drawing a finished document as the whole panel, which no page does).
PANEL_PHASES = {'uploading', 'queued', 'processing', 'action_needed', 'failed', 'stopped', 'being_confirmed', 'paused'}
COMPACT_TITLES = {'completed': 'Results ready', 'awaiting_detail': 'Results ready', 'partial': 'Results ready, with a limitation'}


def progress_html(progress: dict, steps: str, busy: str) -> str:
    if progress['phase'] not in PANEL_PHASES:
        message = (f'<p class="progress-message">{esc(progress["message"])}</p>'
                   if progress['phase'] in ('awaiting_detail', 'partial') and progress.get('message') else '')
        return (f'<section class="progress-panel progress-done" data-phase="{progress["phase"]}" aria-label="Processing"><div>'
                f'<p class="progress-summary"><strong>{esc(COMPACT_TITLES[progress["phase"]])}</strong> · finished in '
                f'<span data-elapsed>4 s</span></p>{message}</div></section>')
    return (f'<section class="progress-panel{busy}" data-phase="{progress["phase"]}" role="status">'
            f'<h2>Processing</h2><ol>{steps}</ol><p>Elapsed <span data-elapsed>1 min 04 s</span></p>'
            f'<p class="progress-message">{esc(progress["message"])}</p>'
            '<p class="leave-note">You can leave this page: processing continues, and the document stays in Documents.</p>'
            '</section>')


def page_html(enc: dict) -> str:
    progress = enc['progress']
    steps = ''.join(f'<li class="progress-step" data-step="{s["key"]}" data-state="{s["state"]}">{esc(s["label"])}</li>'
                    for s in progress['steps'])
    checks = ''.join(f'<li class="check-step" data-check="{c["key"]}" data-state="{c["state"]}">{esc(c["label"])}</li>'
                     for c in enc['checks'])
    busy = ' progress-card' if progress['busy'] else ''
    rows = ''.join(row_html(code) for code in enc['codes'])
    options = ''.join(f'<button type="button" class="export-option" data-export-kind="{kind}" data-export-fmt="{fmt}"'
                      f'{"" if enc["readiness"][kind] else " disabled"}>{"Approved codes" if kind == "approved" else "Suggested codes (draft)"} '
                      f'({fmt.upper()})</button>' for kind in ('draft', 'approved') for fmt in ('txt', 'csv'))
    blockers = ''.join(f'<li>{esc(b)}</li>' for b in enc['readiness']['blockers'])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>CPT Studio</title></head><body>'
            '<main id="main">'
            f'<h1>{esc(enc["title"])}</h1>'
            f'{details_html(enc["details_needed"])}'
            f'{progress_html(progress, steps, busy)}'
            f'<ul class="checks-panel">{checks}</ul>'
            f'<ol class="result-list" aria-label="Suggested CPT codes">{rows}</ol>'
            '<button type="button" class="button" data-action="export">Download</button>'
            f'<pre class="document-text">{esc(enc["document"]["text"])}</pre>'
            '</main>'
            '<dialog id="reviewDialog"><form method="dialog"><label><input type="checkbox" id="reviewAcknowledgement"> '
            f'{esc(ACKNOWLEDGEMENT)}</label>'
            '<select id="reviewModifier"><option value=""></option><option value="59">59</option>'
            '<option value="XS">XS</option></select>'
            '<textarea id="reviewNote" maxlength="600"></textarea><button type="button" id="saveReview">Save</button>'
            '</form></dialog>'
            f'<dialog id="exportDialog"><div id="exportOptions">{options}</div><ul class="export-blockers">{blockers}</ul>'
            '</dialog><div id="toast" role="status"></div></body></html>\n')


def details_encounter() -> dict:
    """The same document before any decision, with a date conflict and one confirmation question open: the details
    panel has a date row (document date and entered date side by side, Use document date) and a confirm row."""
    enc = customer_encounter()
    enc['state'], enc['state_label'] = 'awaiting_detail', 'A few details needed'
    enc['progress'] = {**enc['progress'], 'phase': 'awaiting_detail', 'message': 'A few details are needed.'}
    date_start = TEXT.index(DATE_LINE)
    enc['service_date'] = {'value': None, 'source': 'conflict', 'document_value': '2026-11-03',
                           'document_quote': {'text': DATE_LINE, 'start': date_start, 'end': date_start + len(DATE_LINE)},
                           'entered_value': '2026-11-02', 'conflict': True, 'can_use_document_date': True}
    enc['details_needed'] = [
        # the member's date beside the document's own, and "Use document date" offered: the serializer puts that offer in
        # the row's own choices (answers._date_row, from can_use_document_date), which is what the page draws it from
        # (app.js dateControl); a row without it is one the server never serves (the 2026-11-05 saved-row pin found it)
        {'id': 'detail-service-date', 'fact': 'service_date', 'family_label': 'Encounter', 'prompt': 'Which date of service applies?',
         'control': 'date', 'choices': [{'value': 'use_document', 'label': 'Use document date'}], 'allow': [],
         'document_value': '2026-11-03', 'entered_value': '2026-11-02',
         'quote': {'text': DATE_LINE, 'start': date_start, 'end': date_start + len(DATE_LINE)}, 'affects': ['45380', '45385'],
         'saved': None, 'addendum_allowed': False},
        {'id': 'detail-extent', 'fact': 'extent', 'family_label': 'Colonoscopy',
         'prompt': 'Is the extent of the examination documented?', 'control': 'confirm', 'choices': [],
         'allow': ['not_documented', 'cannot_confirm'], 'document_value': None, 'entered_value': None, 'quote': None,
         'affects': ['45385'], 'saved': None, 'addendum_allowed': True},
    ]
    for code in enc['codes']:
        code.update(status='ready', status_label='Ready for review', sub_label='', modifiers=[], decision=None,
                    allowed_actions=['approve', 'reject'])
    enc['codes'][1].update(status='needs_detail', status_label='Needs a detail', detail_ids=['detail-extent'],
                           allowed_actions=['reject'])
    enc['readiness'] = {'draft': True, 'approved': False, 'blockers': ['45380 has no decision.', '45385 needs a detail.']}
    enc['reports'] = []
    enc['activity'] = []
    return enc


# --- the customer reports (cpt-studio-customer-report@1; CORE-UX-DESIGN.md section 5) ---------------------------------
#
# The SNAPSHOTS studio.reports.customer_snapshot builds for this encounter (its draft from the customer rows, its
# approved export from the approved items), with the generation stamp generate_customer passes the renderers.
# tests/test_cux_r2_reports.py renders them with studio/reports.py and pins the four committed report files to those
# bytes, and holds this shape to what customer_snapshot builds from a real encounter. No report text is written here.

REPORT_FORMAT = FORMAT
GENERATED_STAMP = {'at': GENERATED.replace('+00:00', 'Z'), 'by': AGENT}  # reports._ts(now), user.label()


def report_quote(q: dict) -> dict:
    return {'text': q['text'], 'page': q['page'], 'start': q['start'], 'end': q['end']}  # reports._customer_quote


def report_snapshot(enc: dict, kind: str) -> dict:
    snap = {'format_version': REPORT_FORMAT, 'kind': kind, 'encounter': {'id': ENC, 'title': enc['title']},
            'revision': {'id': REV, 'number': 1}, 'assessment': ASM, 'date_of_service': enc['service_date']['value'],
            'limitations': list(enc['limitations'])}
    decision_ids = {P80: D80, P85: D85}
    if kind == 'approved':
        codes = [c for c in enc['codes'] if c['status'] == 'approved']
        snap['items'] = [{'number': number, 'code': c['code'], 'units': c['units'], 'modifiers': list(c['modifiers']),
                          'status': 'approved', 'approver': c['decision']['by'], 'approver_kind': c['decision']['by_kind'],
                          'agent': c['decision']['by_kind'] == 'agent', 'decided_at': c['decision']['at'],
                          'decision': decision_ids[c['id']], 'summary': c['summary'],
                          'quotes': [report_quote(q) for q in c['why']['quotes']]}
                         for number, c in enumerate(codes, start=1)]
    else:
        snap['items'] = [{'number': c['number'], 'code': c['code'], 'units': c['units'], 'modifiers': list(c['modifiers']),
                          'status': c['status'], 'status_label': c['status_label'], 'sub_label': c['sub_label'],
                          'agent': c['status'] == 'approved' and c['sub_label'] == AGENT_SUB,
                          'summary': c['summary'], 'decision': decision_ids.get(c['id']) if c['decision'] else None,
                          'quotes': [report_quote(q) for q in c['why']['quotes']]}
                         for c in enc['codes']]
    snap['agent_review'] = any(item['agent'] for item in snap['items'])
    return snap


def report_snapshots(enc: dict) -> dict:
    return {'generated': dict(GENERATED_STAMP), 'approved': report_snapshot(enc, 'approved'),
            'draft': report_snapshot(enc, 'draft')}


REPORT_FILES = ('customer-report-approved.txt', 'customer-report-draft.txt', 'customer-report-approved.csv',
                'customer-report-draft.csv')  # studio/reports.py's bytes of report_snapshots(): not written here


# --- driver --------------------------------------------------------------------------------------------------------

def outputs() -> dict[str, str]:
    enc = customer_encounter()
    dumps = lambda value: json.dumps(value, indent=2, ensure_ascii=False) + '\n'  # noqa: E731
    return {
        'document.txt': TEXT,
        'operator-encounter.json': dumps(operator_encounter()),
        'operator-trace.json': dumps(operator_trace()),
        'customer-encounter.json': dumps(enc),
        'customer-encounter-details.json': dumps(details_encounter()),
        'customer-session.json': dumps(customer_session()),
        'customer-page.html': page_html(enc),
        'customer-page-details.html': page_html(details_encounter()),
        'customer-report-snapshots.json': dumps(report_snapshots(enc)),
    }


def main(argv) -> int:
    check = '--check' in argv
    stale = []
    for name, content in outputs().items():
        path = HERE / name
        if check:
            if not path.is_file() or path.read_bytes() != content.encode('utf-8'):
                stale.append(name)
        else:
            path.write_bytes(content.encode('utf-8'))
    if stale:
        print('stale samples (run make_samples.py): ' + ', '.join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
