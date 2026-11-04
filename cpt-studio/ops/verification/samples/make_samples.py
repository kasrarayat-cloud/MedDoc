"""Write the synthetic samples the verification tooling's offline tests read, to the contract they verify.

    python3 -B ops/verification/samples/make_samples.py [--check]

One fictional two-lesion colonoscopy, as the platform-operator API serves it (today's full encounter view and trace,
operator-encounter.json / operator-trace.json), as the customer API serves it (cpt-studio/CORE-UX-DESIGN.md section 7,
customer-encounter.json and customer-session.json), as the customer page draws it (the DOM contract of section 8,
customer-page.html and, with a few details needed, customer-page-details.html), and its customer reports
(cpt-studio-customer-report@1, section 5: customer-report-{approved,draft}.{txt,csv}). Nothing here is a fixture of
the product: the product's own fixtures are its serializers' (tests/fixtures/customer/). These samples exist so the walk
(ops/verify_browser.cjs), the download verifier (ops/verify_downloads.py) and the customer scanner
(ops/scan_customer.py) are each tested against one agreed rendering of the contract, and the TXT and CSV grammar the
download verifier reads is written down in one place (customer_txt / customer_csv below).

--check: write nothing; exit 1 when a committed sample differs from what this script writes (the tests run it).
Stdlib only. Every value is synthetic.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
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

def op_decision(pid: str, code: str, modifiers: list) -> dict:
    return {'id': D80 if pid == P80 else D85, 'proposal_id': pid, 'code': code, 'action': 'approve', 'note': NOTE,
            'reviewer': AGENT, 'reviewer_kind': 'agent', 'created_at': DECIDED[pid], 'decided_at': DECIDED[pid],
            'carried_at': None, 'acknowledgement': ACKNOWLEDGEMENT, 'carried_from': None, 'invalidated': None,
            'revision_number': 1, 'modifiers': modifiers}


def op_proposal(pid, code, bucket, status, evidence, *, decision=None, support=None, reinstatable=False,
                allowed=('approve', 'reject')) -> dict:
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
            'allowed_actions': ['revoke'] if decision else list(allowed), 'approve_withheld_by': None,
            'proposed_by': ['corti', 'astra', 'fable'], 'listed_by': [], 'corti_relation': '',
            'participant_positions': [], 'reference_check': {'state': 'checked', 'detail': ''}, 'retrieval': [],
            'phases': {'astra': 'independent'}, 'confirmed': []}


def support_for(passage: str, detail: str) -> dict:
    return {'origin': 'primary', 'service': 'colon-a', 'family': 'gi.colonoscopy', 'state': 'performed', 'reason': '',
            'detail': detail, 'acts': [{'id': 'act-1', 'kind': 'removal', 'label': detail}], 'status': 'pass',
            'supporting': [0], 'unrelated': [], 'detail_support': '',
            'source': [{'start': TEXT.index(passage), 'end': TEXT.index(passage) + len(passage), 'text': passage}]}


def run(name: str, provider: str, purpose: str, model: str, returned: str, usage: dict, n: int) -> dict:
    return {'id': RUNS[name], 'provider': provider, 'mode': 'live', 'state': 'succeeded', 'http_status': 200,
            'latency_ms': 1200 + n, 'usage': usage, 'usage_basis': 'reported',
            'request_sha256': sha(f'request {name}'), 'response_sha256': sha(f'response {name}'), 'reused_from': None,
            'error': '', 'reconciled': False, 'created_at': f'2026-11-03T22:00:{10 + n:02d}+00:00', 'purpose': purpose,
            'scope_items': [], 'requested_model': model, 'returned_model': returned}


def operator_encounter() -> dict:
    proposals = [
        op_proposal(P80, '45380', 'selected', 'ready', [span(COL1)], decision=op_decision(P80, '45380', []),
                    support=support_for(COL1, SUMMARIES[P80])),
        op_proposal(P85, '45385', 'selected', 'ready', [span(COL2)], decision=op_decision(P85, '45385', ['XS']),
                    support=support_for(COL2, SUMMARIES[P85])),
        op_proposal(P78, '45378', 'alternative', 'informational', [span(CECUM)], allowed=()),
        op_proposal(P39, '43239', 'excluded', 'excluded', [span(PLAN)], allowed=()),
    ]
    stages = [{'kind': kind, 'state': 'succeeded', 'error': '', 'finished_at': f'2026-11-03T22:00:{n:02d}+00:00'}
              for n, kind in enumerate(('extract', 'analyze', 'predict', 'astra', 'fable', 'assess', 'astra_peer',
                                        'fable_peer', 'assess'), start=1)]
    participants = [
        {'name': 'corti', 'label': 'Corti', 'vendor': 'Corti', 'model': 'corti-coding-v2', 'state': 'done',
         'detail': 'Corti returned 3 codes.', 'run_id': RUNS['corti'], 'returned_model': 'corti-coding-v2',
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
    runs = [run('corti', 'corti', 'primary', 'corti-coding-v2', 'corti-coding-v2', {'creditsConsumed': 3}, 1),
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
        'permissions': {'can_review': True, 'is_owner': False, 'can_confirm': False},
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
        'second_review': {'available': False, 'can_request': True, 'items': [], 'reason': ''},
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
    return {'encounter': {'id': ENC, 'title': TITLE},
            'revision': {'id': REV, 'number': 1, 'text_sha256': sha(TEXT)},
            'participants': [{'name': 'corti', 'label': 'Corti', 'vendor': 'Corti', 'model': 'corti-coding-v2', 'runs': []},
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
        'details_needed': [], 'unresolved': [], 'limitations': LIMITATIONS,
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
            if detail['document_value']:
                controls += '<button type="button" data-action="use-document-date">Use document date</button>'
        for choice in detail['choices']:
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
            f'<section class="progress-panel{busy}" data-phase="{progress["phase"]}" role="status">'
            f'<h2>Processing</h2><ol>{steps}</ol><p>Elapsed <span data-elapsed>1 min 04 s</span></p>'
            f'<p class="progress-message">{esc(progress["message"])}</p>'
            '<p class="leave-note">You can leave this page: processing continues, and the document stays in Documents.</p>'
            '</section>'
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
        {'id': 'detail-service-date', 'fact': 'service_date', 'family_label': 'Encounter', 'prompt': 'Which date of service applies?',
         'control': 'date', 'choices': [], 'allow': [], 'document_value': '2026-11-03', 'entered_value': '2026-11-02',
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
# The TXT grammar ops/verify_downloads.py reads: the SYNTHETIC line first and last; a headline; "Report format: <format>";
# the header fields "Encounter:", "Date of service:", "Generated at:", "Generated by:"; one section headed
# "SUGGESTED CODES — NOT APPROVED" (draft) or "APPROVED CODES" (approved), whose items are numbered lines
# "  N. CODE · units U[ · modifier M[, M]][ · <status label>]" (draft items carry the status label), each followed by
# detail lines indented five spaces: "Approved by <label> at <ISO>" and the agent line (approved), the one-sentence
# summary, and one "Quote: "<passage>" [page P, characters S–E]" per quoted passage (a draft may print "[page P]" only);
# then "LIMITATIONS" with "  - " lines. A passage's line breaks continue on lines indented seven spaces.

def customer_txt(enc: dict, kind: str) -> str:
    approved = kind == 'approved'
    lines = [SYNTHETIC_LINE, 'CPT STUDIO — APPROVED CODES' if approved else 'CPT STUDIO — SUGGESTED CODES — NOT APPROVED',
             f'Report format: {FORMAT}', f'Encounter: {enc["title"]}',
             f'Date of service: {enc["service_date"]["value"] or "not established"}',
             f'Generated at: {GENERATED.replace("+00:00", "Z")}', f'Generated by: {AGENT}', '',
             'APPROVED CODES' if approved else 'SUGGESTED CODES — NOT APPROVED']
    codes = [c for c in enc['codes'] if not approved or c['status'] == 'approved']
    for number, code in enumerate(codes, start=1):
        head = f'  {number}. {code["code"]} · units {code["units"]}'
        if code['modifiers']:
            head += f' · modifier {", ".join(code["modifiers"])}'
        if not approved:
            head += f' · {code["status_label"]}'
        lines.append(head)
        if approved:
            decision = code['decision']
            lines.append(f'     Approved by {decision["by"]} at {decision["at"].replace("+00:00", "Z")}')
            if decision['by_kind'] == 'agent':
                lines.append(f'     {AGENT_SUB}')
        lines.append(f'     {code["summary"]}')
        for q in code['why']['quotes']:
            where = f'[page {q["page"]}, characters {q["start"]}–{q["end"]}]' if approved else f'[page {q["page"]}]'
            text = q['text'].replace('\n', '\n       ')
            lines.append(f'     Quote: "{text}" {where}')
    lines += ['', 'LIMITATIONS'] + [f'  - {item}' for item in enc['limitations']] + ['', SYNTHETIC_LINE]
    return '\n'.join(lines) + '\n'


CSV_COLUMNS = ('report_format', 'encounter_title', 'date_of_service', 'number', 'code', 'units', 'modifiers', 'status',
               'approved_by', 'approver_kind', 'approved_at', 'summary', 'evidence_text', 'evidence_page',
               'evidence_start', 'evidence_end')


def customer_csv(enc: dict, kind: str) -> str:
    approved = kind == 'approved'
    out = io.StringIO()
    out.write(SYNTHETIC_LINE + '\r\n')
    writer = csv.writer(out, lineterminator='\r\n')
    writer.writerow(CSV_COLUMNS)
    codes = [c for c in enc['codes'] if not approved or c['status'] == 'approved']
    for number, code in enumerate(codes, start=1):
        decision = code['decision'] if approved else None
        for q in code['why']['quotes'] or [None]:
            writer.writerow([FORMAT, enc['title'], enc['service_date']['value'] or '', number, code['code'], code['units'],
                             ';'.join(code['modifiers']), code['status'], decision['by'] if decision else '',
                             decision['by_kind'] if decision else '', decision['at'] if decision else '', code['summary'],
                             q['text'] if q else '', q['page'] if q else '', q['start'] if q else '',
                             q['end'] if q else ''])
    out.write(SYNTHETIC_LINE + '\r\n')
    return out.getvalue()


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
        'customer-report-approved.txt': customer_txt(enc, 'approved'),
        'customer-report-draft.txt': customer_txt(enc, 'draft'),
        'customer-report-approved.csv': customer_csv(enc, 'approved'),
        'customer-report-draft.csv': customer_csv(enc, 'draft'),
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
