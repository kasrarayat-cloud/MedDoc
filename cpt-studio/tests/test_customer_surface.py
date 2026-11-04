"""The customer surface (CORE-UX-DESIGN.md 5, 7; R4-api-leak-surface 6.6).

Every customer payload, header, error body, report download, the shell's HTML and the collected static bundle are
scanned for the internals the directive keeps from customers: a value-based denylist read from the database after each
scenario (every run id, request id, response id, sha256, endpoint, model, adapter, rule id and source, stored engine and
error text) and a regex net for what the database cannot list (names, model and adapter shapes, rule-id shapes, hex
digests, vendor id shapes, machinery words). The scenarios are driven through the real endpoints and the real pipeline
(tests.test_harness_pipeline's fakes: no network); their documents, titles and notes carry none of the forbidden
tokens (asserted), so any hit is server-generated. Every customer payload is held to the committed contract's key sets
(section 7), the operator URLs to the authorization matrix (404 - an unknown URL's answer - to every non-operator),
legacy artifacts to 404 for customers and byte-identical bytes for operators, and an approved export to 409 once the
decisions it was made from change.
"""
import gzip
import hashlib
import json
import re
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import Client, override_settings

from studio import customer_api, models, progress, reports, review
from studio.gi.catalogue import COMMON_BUNDLED
from tests.support import factories as f
from tests.support import operator as ops
from tests.support import pipeline_factories as pf
from tests.test_frontend import PLAIN_STATIC
from tests.test_harness_pipeline import BOTH, FakeParticipant, HarnessCase
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE

# --- the regex net (R4 6.6(3)) and design rule 0.6 ---------------------------------------------------------------

NET = {
    'provider name': re.compile(r'(?i)\b(?:corti|astra|fable|openai|anthropic|claude)\b'),
    'model id': re.compile(r'(?i)\bgpt-\d|\bclaude-[a-z]'),
    'adapter id': re.compile(r'@cptstudio-'),
    'rule source': re.compile(r'\bcpt-studio:[a-z]'),
    'versioned id': re.compile(r'\b[a-z]+[.-][a-z_]+@\d+\b'),
    'hex digest': re.compile(r'(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])'),
    'vendor id': re.compile(r'\b(?:req|resp|msg|call|chatcmpl)[_-][A-Za-z0-9]{3,}'),
    'check id': re.compile(r'\b(?:provider|participants|services|evidence|pfs|mue|cpt|ncci|scope|routing|facts|context|'
                           r'extraction)\.[a-z_]+\b'),
    'machinery': re.compile(r'(?i)\b(?:participants?|peer[ -]reviews?|vendors?|tokens?|credits?|traces?|sha256|'
                            r'tool calls?|request ids?|replay|providers?)\b'),
    # the readers' own words: an own-passage or disagreeing reading's stored detail names the routing-era reader, the
    # documented-service reader and the cue that decided (engine._reconcile_reading)
    'reader words': re.compile(r'(?i)\b(?:routing|readers?|cues?|own passages?)\b'),
}


def net_hits(text):
    """{net name: [matches]} for ``text``."""
    found = {}
    for name, pattern in NET.items():
        hits = sorted({match.group(0) for match in pattern.finditer(text)})
        if hits:
            found[name] = hits[:8]
    return found


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


HEX = re.compile(r'[0-9a-f]{32,}')


def denied_values():
    """Every value the database holds that a customer must never be served (R4 6.6(2)): run and request identities,
    hashes, endpoints, models, adapters, rule ids and sources, versions, stored engine sentences, error text, keys."""
    values = set()
    for run in models.ProviderRun.objects.all():
        values |= {str(run.pk), str(run.run_identity), run.provider_request_id, run.response_id, run.request_sha256,
                   run.response_sha256, run.endpoint, run.requested_model, run.returned_model, run.adapter_version,
                   run.authorization_ref, run.error}
    for exchange in models.ProviderExchange.objects.all():
        values |= {exchange.provider_request_id, exchange.response_id, exchange.request_sha256,
                   exchange.response_sha256, exchange.error}
    for call in models.ToolCall.objects.all():
        values |= {call.call_id, call.result_sha256}
    values |= set(models.SourceFile.objects.values_list('sha256', flat=True))
    values |= set(models.SourceRevision.objects.values_list('text_sha256', flat=True))
    values |= set(models.EncounterContext.objects.values_list('sha256', flat=True))
    values |= set(models.RoutingRun.objects.values_list('sha256', flat=True))
    values |= set(models.RoutingRun.objects.values_list('version', flat=True))
    for assessment in models.Assessment.objects.all():
        values |= {assessment.sha256, assessment.engine_version, assessment.profiles_version}
        for check in assessment.encounter_checks or []:
            values |= {check.get('id') if '.' in str(check.get('id')) else None, check.get('source'), check.get('detail')}
        # a retrieved CMS passage's release is the dated source a customer is shown: the modifier review cites it by
        # design (CORE-UX-DESIGN.md 4, 7: "cites the dated CMS source"); every other retrieval string stays denied
        cited = {str(passage.get('release')) for entry in assessment.retrieval or [] if isinstance(entry, dict)
                 for passage in entry.get('passages') or [] if isinstance(passage, dict)}
        for item in _strings([assessment.participants, assessment.retrieval]):
            if (HEX.fullmatch(item) or len(item) >= 24) and item not in cited:
                values.add(item)
        for source in assessment.reference_sources or []:
            values |= {source.get('sha256'), source.get('url'), source.get('key')}
    for proposal in models.Proposal.objects.all():
        support = proposal.support or {}
        values |= {proposal.fingerprint, proposal.profile_version, proposal.rationale, proposal.exclusion_reason,
                   proposal.provider_display, support.get('identity'), support.get('detail'),
                   support.get('detail_support')}
        for check in proposal.checks or []:
            values |= {check.get('id') if '.' in str(check.get('id')) else None, check.get('source'), check.get('detail')}
        values |= {str(item) for item in proposal.modifier_considerations or []}
    for question in models.Clarification.objects.all():
        values |= {question.question, question.reason}
    for report in models.ReportArtifact.objects.all():
        values |= {report.sha256, report.snapshot_sha256}
    for source in list(models.ReferenceSource.objects.all()) + list(models.PassageSource.objects.all()):
        values |= {source.sha256, source.url, source.key}
    for job in models.Job.objects.all():
        values |= {job.idempotency_key, job.error}
    values |= {'astra_peer', 'fable_peer'}
    return {value for value in values if isinstance(value, str) and len(value.strip()) >= 6}


# --- the committed customer contract (CORE-UX-DESIGN.md 7): every key listed, nothing else ------------------------

TOP_KEYS = {'id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document', 'service_date',
            'progress', 'checks', 'codes', 'other_codes', 'not_separately_coded', 'details_needed', 'unresolved',
            'limitations', 'readiness', 'reports', 'activity'}
DOCUMENT_KEYS = {'kind', 'name', 'media_type', 'size', 'page_count', 'revision', 'text', 'pages', 'reading',
                 'original_url'}
PAGE_KEYS = {'page', 'start', 'end'}
READING_KEYS = {'status', 'label', 'messages'}
SERVICE_DATE_KEYS = {'value', 'source', 'document_value', 'document_quote', 'entered_value', 'conflict',
                     'can_use_document_date'}
SPAN_KEYS = {'text', 'start', 'end'}
PROGRESS_KEYS = {'phase', 'busy', 'steps', 'active_detail', 'started_at', 'finished_at', 'server_time', 'slow',
                 'message', 'can_stop', 'can_resume', 'can_leave', 'error'}
STEP_KEYS = {'key', 'label', 'state', 'started_at', 'finished_at'}
ERROR_KEYS = {'text', 'action'}
CHECK_KEYS = {'key', 'label', 'state'}
CODE_KEYS = {'id', 'number', 'code', 'units', 'modifiers', 'modifier_review', 'status', 'status_label', 'sub_label',
             'summary', 'why', 'detail_ids', 'allowed_actions', 'decision'}
MODIFIER_REVIEW_KEYS = {'options', 'text', 'sources'}
WHY_KEYS = {'quotes', 'qualifications'}
QUOTE_KEYS = {'text', 'start', 'end', 'page', 'exact'}
DECISION_KEYS = {'action', 'by', 'by_kind', 'at', 'note', 'modifiers'}
OTHER_CODE_KEYS = {'code', 'reason'}
NOT_CODED_KEYS = {'label', 'reason'}
DETAIL_KEYS = {'id', 'fact', 'family_label', 'prompt', 'control', 'choices', 'allow', 'document_value',
               'entered_value', 'quote', 'affects', 'saved', 'addendum_allowed'}
CHOICE_KEYS = {'value', 'label'}
SAVED_KEYS = {'value', 'label', 'by', 'at', 'answer_id'}
READINESS_KEYS = {'draft', 'approved', 'blockers'}
REPORT_KEYS = {'id', 'kind', 'fmt', 'filename', 'generated_at', 'generated_by', 'download_url', 'current'}
ACTIVITY_KEYS = {'event', 'summary', 'actor', 'actor_kind', 'at'}
SESSION_KEYS = {'user', 'workspace', 'role', 'can_review', 'acknowledgement', 'counts', 'synthetic_only'}
SESSION_USER_KEYS = {'id', 'label', 'initials', 'actor_kind'}
SESSION_WORKSPACE_KEYS = {'id', 'name'}
COUNT_KEYS = {'documents', 'queue'}
LIST_ROW_KEYS = {'id', 'title', 'state', 'state_label', 'service_date', 'date_conflict', 'open_details', 'created_at',
                 'kind'}
STATES = set(customer_api.STATE_LABELS)
STATUSES = set(customer_api.STATUS_LABELS)
PHASES = {'queued', 'processing', 'action_needed', 'awaiting_detail', 'completed', 'partial', 'failed', 'stopped',
          'being_confirmed'}
STEP_STATES = {'done', 'active', 'waiting', 'not_started', 'failed', 'stopped', 'skipped'}
CHECK_STATES = {'done', 'running', 'waiting', 'unavailable', 'not_run'}
# The operator serializer's keys a customer payload must never carry (R4 6.3's "drop" column)
OPERATOR_ONLY = {'harness', 'provider_runs', 'state_run', 'second_review', 'routing', 'assessment', 'pipeline',
                 'clarifications', 'confirmations', 'decisions', 'coding', 'context', 'revision', 'created_by',
                 'queue_reasons', 'coding_state', 'service_date_conflict', 'families', 'source_kind',
                 'open_clarifications', 'provider_mode', 'release'}


def assert_contract(case, doc):
    """``doc`` (GET /api/encounters/<id>) has exactly the contract's keys, at every level, and its enumerations."""
    case.assertEqual(set(doc), TOP_KEYS)
    case.assertIn(doc['state'], STATES)
    case.assertEqual(doc['state_label'], customer_api.STATE_LABELS[doc['state']])
    case.assertEqual(set(doc['permissions']), {'can_review'})
    document = doc['document']
    case.assertEqual(set(document), DOCUMENT_KEYS)
    for page in document['pages']:
        case.assertEqual(set(page), PAGE_KEYS)
    case.assertEqual(set(document['reading']), READING_KEYS)
    case.assertEqual(set(doc['service_date']), SERVICE_DATE_KEYS)
    if doc['service_date']['document_quote'] is not None:
        case.assertEqual(set(doc['service_date']['document_quote']), SPAN_KEYS)
    progress = doc['progress']
    case.assertEqual(set(progress), PROGRESS_KEYS)
    case.assertIn(progress['phase'], PHASES)
    case.assertEqual([step['key'] for step in progress['steps']], ['reading', 'identifying', 'checking', 'preparing'])
    for step in progress['steps']:
        case.assertEqual(set(step), STEP_KEYS)
        case.assertIn(step['state'], STEP_STATES)
    if progress['error'] is not None:
        case.assertEqual(set(progress['error']), ERROR_KEYS)
        case.assertIn(progress['error']['action'], {'resume', 'new_document', 'none'})
    case.assertEqual([check['key'] for check in doc['checks']], ['document_review', 'independent_checks',
                                                                 'coding_validation'])
    for check in doc['checks']:
        case.assertEqual(set(check), CHECK_KEYS)
        case.assertIn(check['state'], CHECK_STATES)
    for number, code in enumerate(doc['codes'], start=1):
        case.assertEqual(set(code), CODE_KEYS)
        case.assertEqual(code['number'], number)
        case.assertIn(code['status'], STATUSES)
        case.assertEqual(code['status_label'], customer_api.STATUS_LABELS[code['status']])
        if code['modifier_review'] is not None:
            case.assertEqual(set(code['modifier_review']), MODIFIER_REVIEW_KEYS)
            case.assertEqual(code['modifier_review']['options'], ['59', 'XS'])
        case.assertEqual(set(code['why']), WHY_KEYS)
        for quote in code['why']['quotes']:
            case.assertEqual(set(quote), QUOTE_KEYS)
            case.assertEqual(document['text'][quote['start']:quote['end']], quote['text'])  # exact, never assumed
            case.assertIs(quote['exact'], True)
        if code['decision'] is not None:
            case.assertEqual(set(code['decision']), DECISION_KEYS)
    for item in doc['other_codes']:
        case.assertEqual(set(item), OTHER_CODE_KEYS)
    for item in doc['not_separately_coded']:
        case.assertEqual(set(item), NOT_CODED_KEYS)
    for item in doc['details_needed']:
        case.assertEqual(set(item), DETAIL_KEYS)
        case.assertIn(item['control'], {'date', 'choice', 'confirm'})
        for choice in item['choices']:
            case.assertEqual(set(choice), CHOICE_KEYS)
        if item['saved'] is not None:
            case.assertEqual(set(item['saved']), SAVED_KEYS)
    case.assertTrue(all(isinstance(item, str) for item in doc['unresolved'] + doc['limitations']))
    case.assertEqual(set(doc['readiness']), READINESS_KEYS)
    for report in doc['reports']:
        case.assertEqual(set(report), REPORT_KEYS)
        case.assertIn(report['kind'], {'draft', 'approved'})
    for event in doc['activity']:
        case.assertEqual(set(event), ACTIVITY_KEYS)
        case.assertIn(event['actor_kind'], {'human', 'agent', 'system'})
    case.assertFalse(OPERATOR_ONLY & set(doc))


def assert_session(case, session):
    case.assertEqual(set(session), SESSION_KEYS)
    case.assertEqual(set(session['user']), SESSION_USER_KEYS)
    case.assertEqual(set(session['workspace']), SESSION_WORKSPACE_KEYS)
    case.assertEqual(set(session['counts']), COUNT_KEYS)


def assert_rows(case, rows):
    for row in rows:
        case.assertEqual(set(row), LIST_ROW_KEYS)
        case.assertIn(row['state'], STATES)


# --- the scenarios ------------------------------------------------------------------------------------------------

GI_TWO_LESIONS = (
    'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
    'Procedure report\n'
    'Date of service: 2026-10-21\n'
    'Place of service: hospital outpatient endoscopy unit\n'
    'Procedures: EGD with biopsy; colonoscopy with biopsy and snare polypectomy.\n'
    'EGD: The endoscope was advanced to the second portion of the duodenum. '
    'Cold forceps biopsies were taken from the gastric antrum.\n'
    'Colonoscopy: The colonoscope was advanced to the cecum; the appendiceal orifice was identified.\n'
    'Lesion A - ascending colon: a 3 mm sessile polyp was removed with cold biopsy forceps.\n'
    'Lesion B - sigmoid colon: a 9 mm sessile polyp was removed with a cold snare. A clip was placed to prevent '
    'bleeding.\n'
    'Plan: Repeat colonoscopy in 3 years.\n')
EGD = 'Cold forceps biopsies were taken from the gastric antrum.'
LESION_A = 'Lesion A - ascending colon: a 3 mm sessile polyp was removed with cold biopsy forceps.'
LESION_B = 'Lesion B - sigmoid colon: a 9 mm sessile polyp was removed with a cold snare.'
CLIP = 'A clip was placed to prevent bleeding.'
PLAN = 'Repeat colonoscopy in 3 years.'
DISTINCT = ("Separate lesions are documented: this code's act is on {here}, and another act is on {there}. If an NCCI "
            "procedure-to-procedure edit pairs the two codes, a distinct-lesion modifier (59 or XS) may apply. NCCI edits "
            "are not connected; no modifier is assigned.")


# what the engine stores beside a code (rationale.py, engine.py): it names the vendor, the participants, a model and
# a rule source, so a customer payload that passed it through would fail the regex net as well as the denylist
STORED_RATIONALE = ('Selected by corti. 1 exact evidence passage. Astra (OpenAI, gpt-6-astra) proposed it too '
                    '(cpt-studio:harness@1).')
STORED_EXCLUSION = 'Listed by Astra with no quote found verbatim; the service is planned (cpt-studio:status@1).'


def span(text, passage):
    start = text.index(passage)
    return {'start': start, 'end': start + len(passage), 'text': passage}



@override_settings(**LIVE, **BOTH)
class SurfaceCase(HarnessCase):
    """HarnessCase's workspace (its reviewer), with an owner and a viewer: every customer role reads every surface."""

    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        self.viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)
        self.inputs = [OFFICE_NOTE, 'Synthetic office follow-up']

    def signed_in(self, user):
        client = Client(enforce_csrf_checks=False)
        client.force_login(user)
        return client

    def surface(self, encounter_id):
        """[(label, text)] of every customer response for every role: the session, the list, the encounter (with each
        response's headers), its original, and every customer report it lists."""
        out = []
        for user in (self.owner, self.reviewer, self.viewer):
            client = self.signed_in(user)
            for path in ('/api/session', '/api/encounters', f'/api/encounters/{encounter_id}'):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, (path, response.content))
                out.append((f'{user.username} GET {path}', response.content.decode('utf-8')))
                out.append((f'{user.username} GET {path} headers', json.dumps(dict(response.headers))))
                if path == '/api/session':
                    assert_session(self, response.json())
                elif path == '/api/encounters':
                    assert_rows(self, response.json()['encounters'])
                else:
                    assert_contract(self, response.json())
            doc = client.get(f'/api/encounters/{encounter_id}').json()
            for report in doc['reports']:
                response = client.get(report['download_url'])
                out.append((f'{user.username} GET {report["download_url"]}', response.content.decode('utf-8')))
                out.append((f'{user.username} download headers', json.dumps(dict(response.headers))))
        return out

    def assertClean(self, texts):
        # the member's own words - the documents and titles - are theirs to be shown: a stored value that is a passage
        # of them (a quotation a participant's record keeps) is not a leak, and they carry no forbidden token
        own = [text for text in models.SourceRevision.objects.values_list('text', flat=True) if text]
        own += list(models.Encounter.objects.values_list('title', flat=True)) + self.inputs
        for value in own:  # precondition: no forbidden token is the member's own
            self.assertEqual(net_hits(value), {}, value)
        denied = {value for value in denied_values() if not any(value in text for text in own)}
        self.assertTrue(denied, 'the denylist is read from the scenario\'s own rows')
        leaks = []
        for label, text in texts:
            # the customer report's own format name is the one versioned identifier a customer is shown (DESIGN.md 5)
            hits = net_hits(text.replace(reports.CUSTOMER_FORMAT, ''))
            values = sorted(value for value in denied if value in text)
            if hits or values:
                leaks.append((label, hits, values[:5]))
        self.assertEqual(leaks, [])

    def gi_encounter(self):
        """A two-lesion colonoscopy and an EGD with biopsy, as the engine records them (documented services, acts with
        their evidence, lesions, the support of each code and the distinct-lesion consideration), one code approved by
        the review agent, a prophylactic clip bundled and a planned colonoscopy excluded."""
        encounter = f.encounter(self.ws, self.reviewer, title='Synthetic EGD and two-lesion colonoscopy')
        revision = f.pasted_revision(encounter, self.reviewer, GI_TWO_LESIONS)
        pf.context(encounter, revision, fact_values=pf.facts(GI_TWO_LESIONS))
        text = GI_TWO_LESIONS
        a_words, b_words = '3 mm sessile polyp in the ascending colon', '9 mm sessile polyp in the sigmoid colon'

        def support(service, family, act, kind, label, index=0, reason='service'):
            # an own-passage reading's stored detail names the readers and a cue, as the engine words it
            # (engine._reconcile_reading); none of it may reach a customer (the summary is built from enums and labels)
            detail = (f'The service is documented as performed with {label}; the routing-era reader reads the passage '
                      'the code cites as performed (cue "was removed"), and its own passage decides.'
                      if reason == 'own_passage' else f'The service is documented as performed with {label}.')
            return {'origin': 'primary', 'service': service, 'family': family, 'state': 'performed', 'reason': reason,
                    'detail': detail,
                    'acts': [{'id': act, 'kind': kind, 'label': label}], 'status': 'pass', 'supporting': [index],
                    'unrelated': [], 'detail_support': 'Every provider passage shows the act.', 'source': []}
        engine = dict(text=text, rationale=STORED_RATIONALE)
        egd = replace(pf.proposal('sel:0', '43239', [EGD], **engine),
                      support=support('S1', 'gi.egd', 'S1-A1', 'biopsy', 'forceps biopsy (cold forceps) at the gastric '
                                                                       'antrum'))
        biopsy = replace(pf.proposal('sel:1', '45380', [LESION_A], **engine,
                                     modifiers=(DISTINCT.format(here=a_words, there=b_words),)),
                         support=support('S2', 'gi.colonoscopy', 'S2-A1', 'biopsy',
                                         f'forceps biopsy (cold biopsy forceps) of the {a_words}'))
        snare = replace(pf.proposal('sel:2', '45385', [LESION_B], **engine,
                                    modifiers=(DISTINCT.format(here=b_words, there=a_words),)),
                        support=support('S2', 'gi.colonoscopy', 'S2-A2', 'snare', f'snare removal (cold snare) of the '
                                                                                    f'{b_words}', reason='own_passage'))
        planned = pf.proposal('exc:0', '45378', [PLAN], text=text, bucket='excluded', reinstatable=True,
                              checks=pf.standard_checks(service_status='fail'),
                              exclusion_reason=STORED_EXCLUSION, rationale=STORED_RATIONALE)
        alternative = pf.proposal('alt:0', '45381', [LESION_B], text=text, bucket='alternative')
        # the documented-service reading as the engine records it (gi.services.ServiceInventory, to_jsonable): each act
        # names its service and role, and the colonoscopy its two lesions - the review overlay reads it again
        # (review.effective_view: the summary, the separate-lesion modifier review), so it must be the whole record
        services = {'version': 'gi-services@test', 'services': [
            {'id': 'S1', 'family': 'gi.egd', 'kind': 'egd', 'status': 'performed', 'acts': [
                {'id': 'S1-A1', 'service': 'S1', 'kind': 'biopsy', 'status': 'performed', 'role': 'physician',
                 'anatomy': ['gastric antrum'], 'technique': 'cold forceps', 'evidence': [span(text, EGD)]}]},
            {'id': 'S2', 'family': 'gi.colonoscopy', 'kind': 'colonoscopy', 'status': 'performed', 'lesions': [
                {'id': 'S2-L1', 'service': 'S2', 'noun': 'polyp', 'size': '3 mm', 'morphology': 'sessile',
                 'anatomy': 'ascending colon', 'disposition': 'removed', 'evidence': [span(text, LESION_A)]},
                {'id': 'S2-L2', 'service': 'S2', 'noun': 'polyp', 'size': '9 mm', 'morphology': 'sessile',
                 'anatomy': 'sigmoid colon', 'disposition': 'removed', 'evidence': [span(text, LESION_B)]}], 'acts': [
                {'id': 'S2-A1', 'service': 'S2', 'kind': 'biopsy', 'status': 'performed', 'role': 'physician',
                 'technique': 'cold biopsy forceps', 'lesion': 'S2-L1', 'evidence': [span(text, LESION_A)]},
                {'id': 'S2-A2', 'service': 'S2', 'kind': 'snare', 'status': 'performed', 'role': 'physician',
                 'technique': 'cold snare', 'lesion': 'S2-L2', 'evidence': [span(text, LESION_B)]},
                {'id': 'S2-A3', 'service': 'S2', 'kind': 'clip', 'status': 'performed', 'role': 'physician',
                 'anatomy': ['sigmoid colon'], 'evidence': [span(text, CLIP)]}]}]}
        completeness = {'state': 'complete', 'reasons': [], 'covered': {'S1': ['43239'], 'S2': ['45380', '45385']},
                        'bundled': [{'service': 'S2', 'act': 'clip', 'label': 'clip placement at the sigmoid colon',
                                     'why': dict(COMMON_BUNDLED)['clip']}],
                        'unresolved_items': [], 'not_listed': [], 'catalogue_version': 'gi-catalogue@test'}
        result = replace(pf.result(egd, biopsy, snare, planned, alternative), services=services,
                         completeness=completeness)
        pf.assess(encounter, result)
        review.refresh_state(encounter)
        scenario = pf.Scenario(workspace=self.ws, reviewer=self.reviewer, agent=None, viewer=self.viewer,
                               encounter=encounter, revision=revision, context=encounter.current_context)
        agent = getattr(self, 'agent', None) or f.member(self.ws, f.user('reviewbot', actor_kind=models.User.AGENT))
        self.agent = agent
        scenario.decide('sel:0', 'approve', agent)
        return encounter.pk

    def detail(self, encounter_id, user=None):
        response = self.signed_in(user or self.reviewer).get(f'/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def decide_all(self, encounter_id, user=None):
        """Every decidable code decided as a reviewer would: approve what can be approved, else reject or confirm."""
        user = user or self.reviewer
        client = self.signed_in(user)
        for _ in range(12):
            doc = self.detail(encounter_id, user)
            pending = [code for code in doc['codes'] if code['decision'] is None and code['allowed_actions']]
            if not pending:
                return doc
            code = pending[0]
            action = next(a for a in ('approve', 'confirm', 'reject') if a in code['allowed_actions'])
            body = {'proposal_id': code['id'], 'action': action}
            if action == 'approve':
                body['acknowledgement'] = review.ACKNOWLEDGEMENTS[user.actor_kind]
            response = client.post(f'/api/encounters/{encounter_id}/decisions', data=json.dumps(body),
                                   content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(set(response.json()), {'id', 'proposal_id', 'code', 'decision'})
        raise AssertionError('the decisions did not settle')


class ScenarioTests(SurfaceCase):
    def test_harness2_both_participants_after_peer_review(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.encounter(encounter_id).current_assessment.participants[0]['name'], 'astra')
        doc = self.detail(encounter_id)
        self.assertEqual(doc['state'], 'ready')
        self.assertEqual([code['code'] for code in doc['codes']][:1], ['99213'])
        # coding validation states the reference validation (progress.checks_summary): no installed CMS fee-schedule
        # file applies to this scenario's date, so it is not verified - unavailable, and the results partial (DESIGN 6)
        self.assertEqual([check['state'] for check in doc['checks']], ['done', 'done', 'unavailable'])
        self.assertEqual(doc['progress']['phase'], 'partial')
        self.assertClean(self.surface(encounter_id))

    def test_harness2_phase_one_while_the_peer_reviews_are_owed(self):
        from studio import jobs
        encounter_id = self.create()
        for _ in range(20):  # run the chain only up to its first assessment: the peer stages stay queued
            job = jobs.claim_next()
            self.assertIsNotNone(job)
            jobs.run_job(job)
            if job.kind == models.Job.ASSESS:
                break
        encounter = self.encounter(encounter_id)
        self.assertEqual(review.assessment_phase(encounter.current_assessment), 1)
        self.assertTrue(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED,
                                                  kind__in=models.Job.PEER_KINDS).exists())
        doc = self.detail(encounter_id)
        self.assertEqual((doc['state'], doc['progress']['phase'], doc['checks'][1]['state']),
                         ('processing', 'queued', 'waiting'))
        self.assertClean(self.surface(encounter_id))

    def test_a_gi_encounter_with_documented_acts_lesions_and_the_engine_s_stored_words(self):
        """Codes whose support records documented acts and lesions - the summary, the quotations and the modifier
        review are built from them - beside the stored engine words a real assessment carries (they name the vendor,
        a participant, a model and a rule source), which never reach a customer."""
        encounter_id = self.gi_encounter()
        self.inputs.append(GI_TWO_LESIONS)
        doc = self.detail(encounter_id)
        codes = {code['code']: code for code in doc['codes']}
        # the review overlay's sentence of CPT Studio's own reading (review_view.summary): the documented service and the
        # act the code accounts for, never the stored detail or rationale
        self.assertEqual(codes['45380']['summary'], 'The colonoscopy documents forceps biopsy (cold biopsy forceps) of the '
                                                    '3 mm sessile polyp in the ascending colon.')
        self.assertEqual([quote['text'] for quote in codes['45385']['why']['quotes']], [LESION_B])
        self.assertEqual((codes['45380']['modifier_review']['options'], codes['45385']['modifier_review']['options']),
                         (['59', 'XS'], ['59', 'XS']))
        self.assertEqual((codes['43239']['status'], codes['43239']['sub_label']),
                         ('approved', customer_api.AGENT_SUB_LABEL))
        self.assertEqual(codes['45378']['why'], {'quotes': [], 'qualifications': [
            'The document does not show this service as performed on the date of service.']})
        self.assertIn(STORED_RATIONALE, denied_values())
        # the own-passage reading's stored detail names the readers and a cue: the scan must never find it served
        detail = models.Proposal.objects.get(assessment__encounter_id=encounter_id, code='45385').support['detail']
        self.assertEqual(sorted(net_hits(detail)['reader words']), ['cue', 'own passage', 'reader', 'routing'])
        self.assertIn(detail, denied_values())
        self.assertClean(self.surface(encounter_id))

    @override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
    def test_corti_only(self):
        encounter_id = self.create()
        drain()
        doc = self.detail(encounter_id)
        self.assertEqual(doc['checks'][1]['state'], 'not_run')
        self.assertClean(self.surface(encounter_id))

    def test_a_participant_refusal_and_a_model_mismatch(self):
        self.adapters['astra'].refused = True
        self.adapters['fable'] = FakeParticipant('fable', codes=self.fable_codes, model='claude-other-9')
        encounter_id = self.create()
        drain()
        reasons = [record.get('reason') for record in self.encounter(encounter_id).current_assessment.participants]
        self.assertTrue(any('claude-other-9' in str(reason) for reason in reasons), reasons)  # the operator record has it
        self.assertEqual(self.detail(encounter_id)['progress']['phase'], 'partial')
        self.assertClean(self.surface(encounter_id))

    def test_a_participant_http_failure_names_no_vendor(self):
        self.adapters['astra'].outcome = 'failed'
        encounter_id = self.create()
        drain()
        self.assertIn('529', str(self.runs_of(encounter_id, 'astra')[0].http_status))
        self.assertEqual(self.detail(encounter_id)['checks'][1]['state'], 'unavailable')
        self.assertClean(self.surface(encounter_id))

    def test_an_unknown_outcome_is_being_confirmed(self):
        self.corti.outcome = 'unknown'
        encounter_id = self.create()
        drain()
        doc = self.detail(encounter_id)
        self.assertEqual((doc['state'], doc['progress']['phase']), ('being_confirmed', 'being_confirmed'))
        self.assertEqual(doc['progress']['message'], 'We are confirming whether an earlier check completed. Nothing will '
                                                     'be sent again until that is settled.')
        # the refusal of a second review while it stands is worded for the member, never "reconcile"
        response = self.post(f'/api/encounters/{encounter_id}/second-review', {})
        self.assertEqual(response.status_code, 409)
        self.assertClean(self.surface(encounter_id) + [('second review refusal', response.content.decode())])

    def test_provider_failed(self):
        self.corti.outcomes = ['failed']
        encounter_id = self.create()
        drain()
        doc = self.detail(encounter_id)
        text, action = progress.ERRORS['provider_failed']  # P5's fixed sentence for the state, never the run's error
        self.assertEqual((doc['state'], doc['progress']['error']), ('failed', {'text': text, 'action': action}))
        self.assertClean(self.surface(encounter_id))

    def test_a_member_date_conflict_is_action_needed(self):
        encounter_id = self.create(service_date='2026-10-01')
        drain()
        doc = self.detail(encounter_id)
        self.assertEqual(doc['state'], 'action_needed')
        self.assertEqual(doc['service_date']['entered_value'], '2026-10-01')
        self.assertTrue(doc['service_date']['conflict'])
        self.assertIn('date', [row['control'] for row in doc['details_needed']])
        self.assertClean(self.surface(encounter_id))

    def test_stop_and_resume_name_no_stage(self):
        encounter_id = self.create()
        response = self.post(f'/api/encounters/{encounter_id}/stop', {})
        self.assertEqual(response.status_code, 200, response.content)
        doc = self.detail(encounter_id)
        self.assertEqual((doc['state'], doc['progress']['phase'], doc['progress']['error']['action']),
                         ('stopped', 'stopped', 'resume'))
        resumed = self.post(f'/api/encounters/{encounter_id}/resume', {})
        self.assertEqual((resumed.status_code, resumed.json()), (201, {'resumed': True}))
        again = self.post(f'/api/encounters/{encounter_id}/resume', {})
        drain()
        self.assertClean(self.surface(encounter_id) + [('resume', resumed.content.decode()),
                                                        ('resume refusal', again.content.decode())])

    def test_an_unexpected_stage_failure_names_no_stage(self):
        def boom(job):
            raise RuntimeError('synthetic astra stage defect')
        with mock.patch.dict('studio.jobs.STAGES', {models.Job.ASTRA: boom}), self.assertLogs('studio.jobs', 'ERROR'):
            encounter_id = self.create()
            drain()
        self.assertIn('astra', models.Job.objects.get(encounter_id=encounter_id, kind='astra').error)
        doc = self.detail(encounter_id)
        self.assertEqual(doc['state'], 'failed')
        self.assertClean(self.surface(encounter_id))

    def test_extraction_failed(self):
        encounter = f.encounter(self.ws, self.reviewer, title='Synthetic unreadable upload')
        revision = f.pasted_revision(encounter, self.reviewer, 'x', extract=False)
        models.SourceRevision.record_extraction(revision.pk, extraction_status='failed', extraction_method='pdf_text',
                                                text='', text_sha256='', pages=[], messages=['No text (synthetic).'],
                                                ocr_pages=[], engine={'ingest': 'synthetic@1'})
        review.refresh_state(encounter)
        doc = self.detail(encounter.pk)
        self.assertEqual((doc['state'], doc['document']['reading']['status']), ('failed', 'failed'))
        self.assertEqual(doc['progress']['error']['action'], 'new_document')
        self.inputs.append('Synthetic unreadable upload')
        self.assertClean(self.surface(encounter.pk))

    def test_refusals_from_every_layer_are_worded_for_the_member(self):
        encounter_id = self.create()
        texts = []
        for path, body in ((f'/api/encounters/{encounter_id}/context', {'setting': 'office'}),
                           (f'/api/encounters/{encounter_id}/second-review', {}),
                           (f'/api/encounters/{encounter_id}/resume', {}),
                           (f'/api/encounters/{encounter_id}/addenda', {'text': 'More.', 'synthetic_attestation': 'yes'}),
                           (f'/api/encounters/{encounter_id}/reports', {'kind': 'approved', 'fmt': 'txt'})):
            response = self.post(path, body)  # processing is queued, so each refuses
            self.assertGreaterEqual(response.status_code, 400, (path, response.content))
            texts.append((path, response.content.decode()))
        drain()
        proposal = self.detail(encounter_id)['codes'][0]
        for body in ({'proposal_id': proposal['id'], 'action': 'approve', 'acknowledgement': 'not the attestation'},
                     {'proposal_id': proposal['id'], 'action': 'reinstate'}):
            response = self.post(f'/api/encounters/{encounter_id}/decisions', body)
            self.assertIn(response.status_code, (400, 409), response.content)
            texts.append(('decisions', response.content.decode()))
        viewer = self.signed_in(self.viewer)
        texts.append(('viewer decision', viewer.post(f'/api/encounters/{encounter_id}/decisions', data=json.dumps(
            {'proposal_id': proposal['id'], 'action': 'reject'}), content_type='application/json').content.decode()))
        second = self.post(f'/api/encounters/{encounter_id}/second-review', {})
        texts.append(('second review', second.content.decode()))
        self.assertClean(texts + self.surface(encounter_id))
        for _, text in texts:
            error = json.loads(text).get('error', '')
            self.assertTrue(error, text)

    def test_no_stored_refusal_text_passes_through_the_vocabulary(self):
        self.assertEqual(customer_api.customer_error('The stored provider response no longer matches its recorded hash.'),
                         customer_api.GENERIC_ERROR)
        self.assertEqual(customer_api.customer_error(review.NOT_FINAL_DECISION),
                         'The independent checks for this document have not finished; decisions are recorded once they '
                         'have.')
        self.assertEqual(customer_api.customer_error('Approve is not available for 45385 right now.'),
                         'Approve is not available for 45385 right now.')
        self.assertEqual(customer_api.customer_error('Approve is not available for Astra right now.'),
                         customer_api.GENERIC_ERROR)
        for message in customer_api.KNOWN_ERRORS:
            self.assertEqual(net_hits(customer_api.customer_error(message)), {}, message)
        self.assertEqual(customer_api.customer_blocker('No code is selected for approval: each code listed was given by '
                                                       'Astra or Fable and is offered only as an alternative'),
                         'No code is selected for approval.')
        self.assertEqual(customer_api.customer_blocker('anything else'), 'The review is not complete yet.')


class ReportTests(SurfaceCase):
    """Customer reports (cpt-studio-customer-report@1), legacy artifacts and the stale approved export."""

    def setUp(self):
        super().setUp()
        self.encounter_id = self.create()
        drain()

    def export(self, kind, fmt, user=None):
        client = self.signed_in(user or self.reviewer)
        response = client.post(f'/api/encounters/{self.encounter_id}/reports', data=json.dumps({'kind': kind, 'fmt': fmt}),
                               content_type='application/json')
        return response

    def test_draft_and_approved_exports_in_txt_and_csv(self):
        texts = []
        for fmt in ('txt', 'csv'):
            response = self.export('draft', fmt)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(set(response.json()), REPORT_KEYS)
            download = self.signed_in(self.viewer).get(response.json()['download_url'])
            self.assertEqual(download.status_code, 200)
            self.assertNotIn('X-Content-SHA256', download.headers)
            body = download.content.decode('utf-8')
            self.assertIn(reports.CUSTOMER_FORMAT, body)
            self.assertEqual(body.count(reports.SYNTHETIC_LINE), 2, body)
            texts.append((f'draft {fmt}', body))
        refused = self.export('approved', 'txt')
        self.assertEqual(refused.status_code, 409)
        self.assertTrue(refused.json()['details']['blockers'])
        texts.append(('approved refusal', refused.content.decode()))
        decided = self.decide_all(self.encounter_id)
        approved_codes = [code['code'] for code in decided['codes'] if code['status'] == 'approved']
        self.assertTrue(approved_codes)
        self.assertTrue(decided['readiness']['approved'], decided['readiness'])
        for fmt in ('txt', 'csv'):
            response = self.export('approved', fmt)
            self.assertEqual(response.status_code, 201, response.content)
            body = self.signed_in(self.owner).get(response.json()['download_url']).content.decode('utf-8')
            texts.append((f'approved {fmt}', body))
            self.assertEqual(body.count(reports.SYNTHETIC_LINE), 2, body)
        # the approved export lists exactly the approved decisions: code, units, modifiers, approver
        encounter = self.encounter(self.encounter_id)
        approved = [d for d in review.current_decisions(encounter.current_assessment).values()
                    if d.action == models.Decision.APPROVE]
        csv_text = texts[-1][1]
        import csv as csv_module
        import io
        rows = list(csv_module.DictReader(io.StringIO(csv_text)))
        items = [row for row in rows if row['report_format'] == reports.CUSTOMER_FORMAT]
        self.assertEqual(sorted({(row['code'], row['units'], row['modifiers'], row['approved_by'], row['approver_kind'])
                                 for row in items}),
                         sorted({(d.proposal.code, str(d.proposal.units), '', d.reviewer.label(), d.reviewer_kind)
                                 for d in approved}))
        self.assertEqual([row['report_format'] for row in (rows[0], rows[-1])], [reports.SYNTHETIC_LINE] * 2)
        txt = texts[-2][1]
        for decision in approved:
            self.assertIn(f'{decision.proposal.code} — units {decision.proposal.units} — modifiers: none', txt)
        for code in decided['codes']:
            if code['status'] != 'approved':
                self.assertNotIn(f'. {code["code"]} — units', txt, 'an unapproved code is never in the approved export')
        self.assertClean(texts + self.surface(self.encounter_id))

    def test_a_stale_approved_export_answers_409_and_a_new_one_is_current(self):
        self.decide_all(self.encounter_id)
        report = self.export('approved', 'txt').json()
        client = self.signed_in(self.reviewer)
        self.assertEqual(client.get(report['download_url']).status_code, 200)
        listed = {item['id']: item for item in self.detail(self.encounter_id)['reports']}
        self.assertTrue(listed[report['id']]['current'])
        code = next(code for code in self.detail(self.encounter_id)['codes'] if code['status'] == 'approved')
        response = self.post(f'/api/encounters/{self.encounter_id}/decisions', {'proposal_id': code['id'],
                                                                                'action': 'revoke'})
        self.assertEqual(response.status_code, 201, response.content)
        stale = client.get(report['download_url'])
        self.assertEqual((stale.status_code, stale.json()), (409, {'error': customer_api.STALE_EXPORT, 'details': {}}))
        self.assertFalse({item['id']: item for item in self.detail(self.encounter_id)['reports']}[report['id']]['current'])
        stored = models.ReportArtifact.objects.get(pk=report['id'])
        self.assertEqual(hashlib.sha256(bytes(stored.content)).hexdigest(), stored.sha256)  # never modified
        self.decide_all(self.encounter_id)
        fresh = self.export('approved', 'txt').json()
        self.assertEqual(client.get(fresh['download_url']).status_code, 200)

    def test_legacy_artifacts_answer_404_to_customers_and_stay_byte_identical_for_operators(self):
        legacy = reports.generate(self.encounter(self.encounter_id), 'draft', 'txt', self.reviewer)
        self.assertEqual(legacy.audience, 'operator')
        # as a row the previous release inserts (it names no audience): the database default makes it an operator's
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT column_default FROM information_schema.columns WHERE table_name = %s AND '
                           'column_name = %s', ['studio_reportartifact', 'audience'])
            self.assertIn("'operator'", cursor.fetchone()[0])
        for user in (self.owner, self.reviewer, self.viewer):
            response = self.signed_in(user).get(f'/api/reports/{legacy.pk}/download')
            self.assertEqual(response.status_code, 404, user.username)
            self.assertNotIn(str(legacy.pk), json.dumps(self.detail(self.encounter_id, user)))
        operator_client = ops.client(f.user('platform-operator'))
        response = operator_client.get(f'/ops/api/reports/{legacy.pk}/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(hashlib.sha256(response.content).hexdigest(), legacy.sha256)
        self.assertEqual(response.content, bytes(legacy.content))
        self.assertEqual(response['X-Content-SHA256'], legacy.sha256)
        listed = operator_client.get(f'/ops/api/encounters/{self.encounter_id}/reports').json()['reports']
        self.assertEqual([(item['id'], item['audience'], item['sha256']) for item in listed],
                         [(str(legacy.pk), 'operator', legacy.sha256)])

    def test_the_shell_names_nothing_internal(self):
        with override_settings(STORAGES=PLAIN_STATIC):
            html = self.signed_in(self.reviewer).get('/')
        self.assertEqual(html.status_code, 200)
        self.assertClean([('GET /', html.content.decode('utf-8')), ('GET / headers', json.dumps(dict(html.headers)))])


class CollectedStaticTests(SurfaceCase):
    """The customer bundle (P6's codes-first studio/static/studio/app.js and styles.css, CORE-UX-DESIGN.md 2, 8) and
    the customer shell (templates/studio/index.html, login.html) name nothing internal; the operator console's bundle
    lives at studio/operator/, outside static, served only behind the operator grant (tests.test_operator)."""
    TEMPLATES = Path(settings.BASE_DIR) / 'studio' / 'templates' / 'studio'

    def collected(self):
        """[(path, text)] of every file a fresh collectstatic writes (compressed copies decompressed)."""
        with tempfile.TemporaryDirectory(dir=settings.STATE_DIR) as root, \
                override_settings(STATIC_ROOT=root, STORAGES=PLAIN_STATIC):
            call_command('collectstatic', interactive=False, verbosity=0)
            texts = []
            for path in sorted(Path(root).rglob('*')):
                if not path.is_file():
                    continue
                data = path.read_bytes()
                if path.suffix == '.gz':
                    data = gzip.decompress(data)
                texts.append((str(path.relative_to(root)), data.decode('utf-8', errors='replace')))
        return texts

    def leaking(self, texts):
        return sorted({name for name, text in texts if net_hits(text)})

    def test_the_collected_static_bundle_names_nothing_internal(self):
        texts = self.collected()
        names = {name for name, _ in texts}
        self.assertTrue({'studio/app.js', 'studio/styles.css'} <= names, sorted(names))
        self.assertEqual(self.leaking(texts), [])
        # the scan reads what it is given: a planted machinery word in the bundle is found
        self.assertEqual(self.leaking([('studio/app.js', dict(texts)['studio/app.js'] + '\n// via Corti')]),
                         ['studio/app.js'])

    def test_the_customer_templates_and_the_sign_in_page_name_nothing_internal(self):
        for name in ('index.html', 'login.html'):
            with self.subTest(name):
                self.assertEqual(net_hits((self.TEMPLATES / name).read_text(encoding='utf-8')), {})
        with override_settings(STORAGES=PLAIN_STATIC):
            page = Client().get('/login/')
        self.assertEqual(page.status_code, 200)
        self.assertClean([('GET /login/', page.content.decode('utf-8')),
                          ('GET /login/ headers', json.dumps(dict(page.headers)))])

    def test_the_operator_bundle_is_never_collected_as_static(self):
        with tempfile.TemporaryDirectory(dir=settings.STATE_DIR) as root, \
                override_settings(STATIC_ROOT=root, STORAGES=PLAIN_STATIC):
            call_command('collectstatic', interactive=False, verbosity=0)
            names = [path.name for path in Path(root).rglob('*') if path.is_file()]
        self.assertTrue(names)
        self.assertFalse({'ops.js', 'ops.css'} & set(names), names)
        self.assertEqual(Client().get('/static/studio/ops.js').status_code, 404)
