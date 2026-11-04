"""The customer contract (CORE-UX-DESIGN.md 7): every payload a workspace member is served, built by ALLOWLIST.

Nothing here passes a stored dict or stored free text through (R4-api-leak-surface 6.1(1)). The engine's sentences, the
adapters' errors, the participants' readings and the job errors name vendors, models, rule ids and request ids, and they
sit on immutable rows - so every customer sentence is re-derived here from structured fields (statuses, check ids and
their states, act kinds, exact spans of the document) in CPT Studio's own fixed wording, and every key is written out.
A label CPT Studio composed from the document's own words (an act's anatomy, a lesion) is used only when it passes the
server-side guard (``plain``); otherwise the fixed sentence stands in for it. The complete record - providers, models,
usage, runs, hashes, rule ids, the trace - stays available to platform operators at /ops/ (studio.operator), served by
studio.serializers, which is the operator serializer and is never called for a customer.

The blocks other packages build are made here by stand-ins with exactly the contract's shape, each marked
``# INTEGRATION: replaced by <module.function>``: P3's effective review view and approved items (review.effective_view,
review.approved_items), P5's progress, details and document-date blocks (progress.encounter_progress,
answers.details_needed, EncounterContext.document_date).
"""
from __future__ import annotations

import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import models, review
from .gi.context import charge_date_problem
from .gi.profiles import PROFILES
from .models import Decision, Job, Proposal, ProviderRun, ReportArtifact, SourceRevision

# --- the customer vocabulary --------------------------------------------------------------------------------------

STATE_LABELS = {
    'processing': 'Processing', 'action_needed': 'Action needed', 'awaiting_detail': 'A few details needed',
    'ready': 'Ready for review', 'reviewed': 'Reviewed', 'no_codes': 'No codes suggested', 'stopped': 'Stopped',
    'failed': 'Could not finish', 'being_confirmed': 'Being confirmed',
}
# The stored (derived) encounter state -> the customer's. A state this table does not know reads as processing.
STORED_STATES = {
    'processing': 'processing', 'stopped': 'stopped', 'extraction_failed': 'failed', 'processing_failed': 'failed',
    'provider_not_run': 'failed', 'provider_failed': 'failed', 'provider_unknown': 'being_confirmed',
    'needs_clarification': 'awaiting_detail', 'ready_for_review': 'ready', 'reviewed': 'reviewed', 'no_codes': 'no_codes',
}
STATUS_LABELS = {'ready': 'Ready for review', 'needs_detail': 'Needs a detail', 'approved': 'Approved',
                 'excluded': 'Excluded'}
AGENT_SUB_LABEL = 'Agent-executed synthetic review — not clinical approval'
REJECTED_SUB_LABEL = 'Rejected in review'
CONFIRMED_SUB_LABEL = 'Exclusion confirmed in review'
REINSTATED_SUB_LABEL = 'Reinstated in review'
CHECK_EXCLUDED_SUB_LABEL = 'Excluded by a documentation check'
UNAVAILABLE_SUB_LABEL = 'A needed detail is not documented'
GENERIC_ERROR = 'This action is not available right now.'
STALE_EXPORT = 'This export no longer matches the saved decisions; create a new one.'
DISTINCT_LESION = "Separate lesions are documented: this code's act is on "  # the engine's own sentence (engine.py)
SETTING_CHOICES = (('office', 'Office'), ('hospital_outpatient', 'Hospital outpatient'),
                   ('asc', 'Ambulatory surgical center'), ('inpatient', 'Inpatient'),
                   ('emergency', 'Emergency department'), ('telehealth', 'Telehealth'))
CHOICES = {'setting': SETTING_CHOICES,
           'patient_status': (('new', 'New patient'), ('established', 'Established patient')),
           'billing_context': (('professional', 'Professional'), ('facility', 'Facility'))}
FACT_WORDS = {'service_date': 'the date of service', 'setting': 'the place of service',
              'patient_status': 'whether the patient is new or established',
              'billing_context': 'professional or facility billing', 'extent': 'how far the examination reached',
              'completion': 'whether the examination was completed', 'em_basis': 'the basis for the visit level',
              'target': 'the structure examined', 'cannulation': 'whether cannulation was achieved',
              'performed_status': 'whether the service was performed', 'base_included': 'how the codes are reported',
              'separate_em': 'a separate office visit'}
LIMITATIONS = (
    'CPT descriptions are not shown: no licensed CPT descriptor is connected.',
    'CPT code-set membership for the date of service is not verified.',
    'NCCI procedure-to-procedure edits and payer modifier policies are not checked.',
    'The documentation checks read stated wording and can miss wording they do not recognise; decide from the whole '
    'document.',
)
NO_REFERENCE_FILE = 'No CMS fee-schedule file applies to the date of service, so those reference checks were not run.'
REFERENCE_FAILED = 'The CMS reference check could not run for this document.'
RECORDED_RESPONSE = 'These results come from a recorded test response, not a live check.'
PARTIAL_READING = 'Part of the document could not be read; check the text against the original.'

# A server-composed customer string is refused when it carries any of these (the regex net of R4 6.6(3)): a label
# built from the document's own words that matches falls back to CPT Studio's fixed sentence.
FORBIDDEN = re.compile(
    r'(?i)\b(?:corti|astra|fable|openai|anthropic|claude)\b|\bgpt-\d|\bclaude-[a-z]|@cptstudio-|\bcpt-studio:[a-z]'
    r'|(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])|\b(?:participants?|peer[ -]reviews?|vendors?|tokens?|credits?|traces?'
    r'|sha256|tool calls?|request ids?|replay|providers?)\b|\b[a-z]+[.-][a-z_]+@\d+\b')


def plain(text) -> str:
    """``text`` when it is a non-empty string the guard passes, else ''."""
    if not isinstance(text, str):
        return ''
    text = ' '.join(text.split())
    return text if text and not FORBIDDEN.search(text) else ''


def _iso(value):
    return value.isoformat() if value else None


def _sentence(text):
    text = text.strip()
    return text if not text or text.endswith(('.', '!', '?')) else f'{text}.'


def _capital(text):
    return text[:1].upper() + text[1:]


def _family_label(slug):
    return PROFILES[slug].label if slug in PROFILES else 'Procedure'


def _act_label(kind):
    from .validation.reconcile import act_label  # local import: the reconciliation's own constant labels
    return act_label(kind) if isinstance(kind, str) and kind else 'act'


def _code(value) -> str:
    """A code as the customer is shown it: only in a code's shape (letters and digits, at most 10), else ''."""
    return value if isinstance(value, str) and re.fullmatch(r'[0-9A-Z]{4,10}', value) else ''


# --- errors -------------------------------------------------------------------------------------------------------

# Refusals from deeper layers (jobs.Refused, ValidationError, PermissionDenied, AttestationRefused) that are already in
# CPT Studio's plain customer wording pass through; the rest are re-worded; anything this table does not know answers
# GENERIC_ERROR, so no stored or exception text ever reaches a customer.
KNOWN_ERRORS = {
    'Context can be set once the document text has been extracted.': None,
    'Wait for processing to finish (or stop it) before changing context.': None,
    'This document could not be read to the end, so its context cannot be changed and nothing is sent for it. '
    'Upload it again, shorter or split.': None,
    'Wait for processing to finish (or stop it) before resuming.': None,
    'Wait for processing to finish (or stop it) before asking for a second review.': None,
    'There is no current assessment to review again.': None,
    'No documented service is left without a supported proposal.': None,
    'A second review needs a known, agreed date of service: answer the date question first.': None,
    'A second review was already made for this document and date.': None,
    'A second review was already requested for this document and date.': None,
    'A second review was already requested for this assessment.': None,
    'This document was read under earlier context rules: save a change to the encounter context (or add an addendum) '
    'so it is read under the current ones, then ask.': None,
    'Only a successful provider response can be reviewed again.': 'Only a completed check can be checked again.',
    'A previous request has an unknown outcome; reconcile it before asking again.':
        'We are confirming whether an earlier check completed. Nothing will be sent again until that is settled.',
    'The provider is not configured on this installation.': 'The coding service is not available on this installation.',
    'The provider refused the request whole, so a second review has nothing to fill.':
        "The coding service's earlier answer could not be used, so there is nothing to check again.",
    'The text that documents the unresolved services is a request the provider already answered, so a second review '
    'would ask nothing new.': 'The unresolved services were already checked with this exact text, so another check '
                              'would ask nothing new.',
    'The text that documents the unresolved services is a request already sent for this document that failed, and an '
    'identical request is never sent again.': 'This exact check already failed for this document, and an identical '
                                              'one is never sent again.',
    'Your role in this workspace cannot record review decisions.': None,
    'Your role in this workspace cannot change documents or decisions.': None,
    'Your role in this workspace cannot confirm findings.': None,
    'That proposal is not part of the current review.': None,
    'Unknown review action.': None,
    review.NOT_FINAL_DECISION: 'The independent checks for this document have not finished; decisions are recorded '
                               'once they have.',
    'Approving requires an acknowledgement.': None,
    'The acknowledgement is not the current review attestation. Reload the page and approve again.': None,
    review.CONFIRMATIONS_NOT_OFFERED: None,
    'That question belongs to an earlier assessment; reload the page and answer the current one.': None,
    review.CONTEXT_CHANGED: None,
    'The peer reviews of this document have not finished: a finding can be confirmed once its final assessment is '
    'recorded.': 'The independent checks for this document have not finished; a finding can be confirmed once they '
                 'have.',
    'That question is not open.': None,
    'That question was confirmed already; a question takes one confirmation.': None,
    'Wait for processing to finish (or stop it) before confirming a finding.': None,
    "That candidate is not one of this question's candidates; reload the page.": None,
    "That question's proposal records no identity for a confirmation to be bound to, so it cannot be confirmed; nothing "
    'was recorded.': None,
    'Provide either a file or pasted text.': None,
    'Upload a PDF, DOCX or TXT file.': None,
    'The file is named .pdf but is not a PDF document.': None,
    'The file is named .docx but is not a Word (DOCX) document.': None,
    'The file is named .txt but contains binary data.': None,
    'The file is empty.': None,
    'There is no assessment of the current revision to report yet.': 'There is nothing to export yet.',
    'Only an active member of this workspace can create its exports.': None,
    'Choose a TXT or CSV export.': None,
    'Choose a draft or an approved export.': None,
    'The approved export is not available yet.': None,
}
KNOWN_TEMPLATES = (
    re.compile(r'(?:Approve|Reject|Reinstate for review|Revoke decision|Confirm exclusion) is not available for '
               r'[0-9A-Z]{4,10} right now\.'),
    re.compile(r'The file is larger than \d+ MB\.'),
    re.compile(r'Pasted text is longer than \d+ characters\.'),
    re.compile(r'The text that documents the unresolved services is longer than a second review sends '
               r'\([0-9,]+ characters\)\.'),
    re.compile(r'Reading this document took longer than \d+ seconds and was stopped\. The document may be too long or '
               r'unusual to read within the limit; shorten it or split it, then upload it again\.'),
    re.compile(r'Reading this document needed more memory than the limit allows and was stopped\. Shorten it or split '
               r'it, then upload it again\.'),
    re.compile(r'This document names a procedure [0-9,]+ times, more than the [0-9,]+ this service reads in one '
               r'document, so it was not read and nothing was sent\. Shorten it or split it, then upload it again\.'),
    re.compile(r'The attestation must read exactly: I read this passage in the source document; it documents [^\n]{1,80} '
               r'for this encounter\.'),
)


# A known refusal whose tail is composed from stored text: only its fixed head is said
KNOWN_HEADS = {
    'That candidate is not verified, so it cannot be confirmed: ':
        'That candidate is not verified, so it cannot be confirmed.',
}


def customer_error(message) -> str:
    """The customer sentence for a refusal raised below the API: as written when it is a known customer sentence,
    re-worded when it is a known sentence that names the machinery, only its fixed head when its tail is composed from
    stored text, else GENERIC_ERROR."""
    text = message if isinstance(message, str) else ''
    if text in KNOWN_ERRORS:
        return KNOWN_ERRORS[text] or text
    if any(template.fullmatch(text) for template in KNOWN_TEMPLATES):
        return text
    for head, words in KNOWN_HEADS.items():
        if text.startswith(head):
            return words
    return GENERIC_ERROR


# --- readiness ----------------------------------------------------------------------------------------------------

CODE = r'([0-9A-Z]{4,10})'
BLOCKER_EXACT = {
    'No document has been recorded yet': 'No document has been added yet.',
    'Processing has not finished': 'Processing has not finished.',
    'No text was extracted': 'The text of the document could not be read.',
    review.NOT_FINAL_BLOCKER: 'The independent checks have not finished.',
    'The encounter context changed; re-assessment has not finished': 'The details changed; the results are being updated.',
    'The provider was not run': 'The coding service did not run for this document.',
    'The provider outcome is unknown': 'We are confirming whether an earlier check completed.',
    'Nothing was sent: the service date entered as encounter metadata conflicts with the document':
        'The service date you entered differs from the document; choose which date to use.',
    'The provider request failed': 'The coding service could not finish for this document.',
    'The provider response was not used': "The coding service's answer could not be used.",
}
BLOCKER_TEMPLATES = (
    (re.compile(r'Revision \d+ has not been assessed yet'), lambda m: 'The latest version of the document has not been '
                                                                       'checked yet.'),
    (re.compile(r'Open clarification: ([a-z_: ]{1,60})'),
     lambda m: f'A detail is needed: {FACT_WORDS.get(m.group(1).replace(" ", "_"), "a detail of the encounter")}.'),
    (re.compile(CODE + r' needs a separately identifiable E/M: ([0-9A-Z, and]{4,200}) (?:was reinstated as a same-day '
                       r'procedure|were reinstated as same-day procedures)'),
     lambda m: f'{m.group(1)} needs a separately identifiable office visit: {m.group(2)} was reinstated for the same '
               'day.'),
    (re.compile(CODE + r' was reinstated and has no decision'), lambda m: f'{m.group(1)} was reinstated and has no '
                                                                         'decision yet.'),
    (re.compile(CODE + r' was excluded by a documentation check: confirm the exclusion or reinstate it'),
     lambda m: f'{m.group(1)} was excluded by a documentation check: confirm the exclusion or reinstate it.'),
    (re.compile(CODE + r' has an open clarification'), lambda m: f'{m.group(1)} needs a detail.'),
    (re.compile(CODE + r' needs clarification'), lambda m: f'{m.group(1)} needs a detail.'),
    (re.compile(CODE + r' has no decision'), lambda m: f'{m.group(1)} has no decision yet.'),
    (re.compile(r'No code is selected for approval[^\n]*'), lambda m: 'No code is selected for approval.'),
    (re.compile(r'No CPT code was proposed[^\n]*'), lambda m: 'No CPT code was suggested for this document.'),
)


def customer_blocker(blocker) -> str:
    """One readiness blocker (review.readiness) in the customer's words; one this table does not know is 'The review is
    not complete yet.'"""
    text = blocker if isinstance(blocker, str) else ''
    if text in BLOCKER_EXACT:
        return BLOCKER_EXACT[text]
    for pattern, words in BLOCKER_TEMPLATES:
        match = pattern.fullmatch(text)
        if match:
            return words(match)
    return 'The review is not complete yet.'


def customer_blockers(blockers) -> list:
    return list(dict.fromkeys(customer_blocker(item) for item in blockers or []))


# --- the effective review view and the approved items (P3) ------------------------------------------------------

# INTEGRATION: replaced by review.effective_view (P3; CORE-UX-DESIGN.md 4)
def effective_view(assessment, current):
    """{proposal key: view} over the stored proposals and the current decisions: its status, the reason a view excluded
    it ('' here), and its distinct-lesion modifier review over the effective set."""
    proposals = list(assessment.proposals.order_by('position'))
    effective = [p for p in proposals if _in_effective_set(p, current.get(p.pk))]
    out = {}
    for proposal in proposals:
        out[proposal.key] = {'status': proposal.status, 'reason': '',
                             'modifier_review': _modifier_review(proposal, effective)}
    return out


def _in_effective_set(proposal, decision):
    """Whether a code counts toward the coding as the review leaves it: selected and not rejected, or reinstated."""
    action = decision.action if decision is not None else None
    if proposal.bucket == Proposal.SELECTED:
        return action != Decision.REJECT
    return proposal.bucket == Proposal.EXCLUDED and action in (Decision.REINSTATE, Decision.APPROVE)


def _distinct_lesion(proposal):
    return any(isinstance(item, str) and item.startswith(DISTINCT_LESION)
               for item in proposal.modifier_considerations or [])


def _claims_manual():
    """The dated CMS claims-manual source CPT Studio holds, as the customer names it ('' when none is installed)."""
    source = models.PassageSource.objects.filter(kind='cms-claims-manual').order_by('-effective_start').first()
    if source is None:
        return []
    named = plain(f'{source.title} ({source.release})')
    return [named] if named else []


# INTEGRATION: replaced by review.effective_view's modifier_review (P3; CORE-UX-DESIGN.md 4)
def _modifier_review(proposal, effective):
    """The distinct-lesion modifier review of ``proposal`` (directive 4): offered only while another code of the same
    documented service that the engine records separate lesions for is in the effective set, never assigned."""
    if proposal not in effective or not _distinct_lesion(proposal):
        return None
    service = (proposal.support or {}).get('service')
    others = [p for p in effective if p.pk != proposal.pk and p.code != proposal.code and _distinct_lesion(p)
              and (p.support or {}).get('service') == service and _code(p.code)]
    if not service or not others or not _code(proposal.code):
        return None
    codes = [proposal.code] + sorted({p.code for p in others})
    joined = ', '.join(codes[:-1]) + f' and {codes[-1]}'
    return {'kind': 'distinct_lesion', 'codes': codes, 'options': ['59', 'XS'],
            'text': (f'Separate lesions are documented for {joined}. If a payer edit pairs these codes, one '
                     'distinct-lesion modifier (59 or XS) may apply; none is assigned. NCCI procedure-to-procedure '
                     'edits and payer modifier policy are not checked.'),
            'sources': _claims_manual()}


# INTEGRATION: replaced by review.approved_items (P3; CORE-UX-DESIGN.md 4)
def approved_items(assessment, current=None):
    """The approved items of ``assessment``, in stored order: approved decisions only - never an unresolved or unapproved
    item - each with its code, units, modifiers, approver, approver kind, decision time, note, exact evidence and one
    sentence of CPT Studio's own reading."""
    current = review.current_decisions(assessment) if current is None else current
    revision = assessment.revision
    acts = _act_index(assessment)
    items = []
    for proposal in assessment.proposals.order_by('position'):
        decision = current.get(proposal.pk)
        if decision is None or decision.action != Decision.APPROVE:
            continue
        reinstated = review.reinstatement_for(decision) if proposal.bucket == Proposal.EXCLUDED else None
        items.append({'proposal_id': str(proposal.pk), 'decision_id': str(decision.pk), 'code': proposal.code,
                      'units': proposal.units, 'modifiers': list(getattr(decision, 'modifiers', None) or []),
                      'approver': decision.reviewer.label(), 'approver_kind': decision.reviewer_kind,
                      'agent': decision.reviewer_kind == models.User.AGENT or (
                          reinstated is not None and reinstated.reviewer_kind == models.User.AGENT),
                      'decided_at': _iso(review.decision_root(decision).created_at), 'note': decision.note,
                      'evidence': _quotes(proposal, revision.text, revision.pages, acts, 'approved'),
                      'summary': _summary(proposal)})
    return items


# --- the codes -----------------------------------------------------------------------------------------------------

def _act_index(assessment):
    out = {}
    for service in (assessment.services or {}).get('services') or []:
        if not isinstance(service, dict):
            continue
        for act in service.get('acts') or []:
            if isinstance(act, dict) and isinstance(act.get('id'), str):
                out[act['id']] = act
    return out


def _page(pages, offset):
    for page in pages or []:
        if (isinstance(page, dict) and type(page.get('start')) is int and type(page.get('end')) is int
                and page['start'] <= offset < page['end'] and type(page.get('page')) is int):
            return page['page']
    return None


def _quotes(proposal, text, pages, acts, status):
    """CPT Studio's own located passages for the matched act first (the support record's source passages, then the
    documented act's evidence), then the provider's exact passages only where the support record says they show the
    act - never a passage that does not support, and none for an excluded code. Each re-checked against the text."""
    if status == 'excluded':
        return []
    support = proposal.support or {}
    out, seen = [], []

    def add(span):
        if not isinstance(span, dict):
            return
        start, end, quote = span.get('start'), span.get('end'), span.get('text')
        if not (type(start) is int and type(end) is int and isinstance(quote, str) and 0 <= start < end <= len(text)
                and text[start:end] == quote):
            return
        if any(a <= start and end <= b for a, b in seen) or len(out) >= 4:
            return
        seen.append((start, end))
        out.append({'text': quote, 'start': start, 'end': end, 'page': _page(pages, start), 'exact': True})

    for span in support.get('source') or []:
        add(span)
    for act in support.get('acts') or []:
        stored = acts.get(act.get('id')) if isinstance(act, dict) else None
        if stored is not None and stored.get('status') in ('performed', 'incomplete'):
            for span in stored.get('evidence') or []:
                add(span)
    evidence = proposal.evidence or []
    for index in support.get('supporting') or []:
        if type(index) is int and 0 <= index < len(evidence) and evidence[index].get('context_index') == 0 \
                and evidence[index].get('exact') is True:
            add(evidence[index])
    return out


def _summary(proposal):
    """One sentence of CPT Studio's own reading: the documented service and the acts the code accounts for."""
    support = proposal.support or {}
    family = _family_label(support.get('family') or proposal.family)
    acts = [plain(act.get('label')) for act in support.get('acts') or [] if isinstance(act, dict)]
    acts = [act for act in acts if act]
    state = support.get('state')
    if state == 'not_performed':
        return f'{family}: not documented as performed on the date of service.'
    if acts:
        return f'{family}: {"; ".join(acts)}.'
    if state in ('performed', 'incomplete'):
        return f'{family}: documented as {state} on the date of service.'
    return f'{family}: suggested from this document.'


EXCLUSION_REASONS = (
    ('scope.cpt', 'This code is outside the CPT codes this service reviews.'),
    ('evidence.exact', 'No passage of the document matches the text cited for this code exactly.'),
    ('service.status', 'The document does not show this service as performed on the date of service.'),
    ('service.documented', 'The document does not show this service as performed on the date of service.'),
    ('routing.family', 'The document does not show this kind of service on the date of service.'),
    ('service.act_elsewhere', 'The act this code needs is documented in another procedure.'),
    ('services.base_included', 'This code is included in another code reported for the same examination.'),
)


def _exclusion_reason(proposal):
    failing = {check.get('id') for check in proposal.checks or [] if isinstance(check, dict)
               and check.get('status') in ('fail', 'warn')}
    for check_id, words in EXCLUSION_REASONS:
        if check_id in failing:
            return words
    return 'A documentation check excluded this code.'


QUESTION_WORDS = {
    'performed_status': 'The document does not establish that this was done on the date of service.',
    'extent': 'How far the examination reached is not documented.',
    'completion': 'Whether the examination was completed is not documented.',
    'separate_em': 'A separately identifiable office visit is not documented beside the procedure.',
    'em_basis': 'The basis for the visit level is not documented.',
    'setting': 'The place of service is not documented.',
    'patient_status': 'Whether the patient is new or established is not documented.',
    'target': 'The structure examined is not documented.',
    'cannulation': 'Whether cannulation was achieved is not documented.',
}


def _qualifications(proposal, status, view, questions, code):
    support = proposal.support or {}
    out = []
    if status == 'needs_detail':
        if support.get('reason') == 'conflict':
            kinds = [act.get('kind') for act in support.get('acts') or [] if isinstance(act, dict)]
            out.append(f'The document has conflicting statements about the {_act_label(kinds[0] if kinds else "")}; '
                       'a detail is needed before this code can be approved.')
        for question in questions:
            fact = question.fact
            if fact == 'base_included':
                out.append(f'{code} may be included in another code reported for this examination; a detail is '
                           'needed before it can be approved.' if code else
                           'This code may be included in another code reported for this examination.')
            elif fact in QUESTION_WORDS:
                out.append(QUESTION_WORDS[fact])
        if not out:
            out.append('A detail is needed before this code can be approved.')
    if status == 'excluded' and proposal.bucket == Proposal.EXCLUDED:
        out.append(_exclusion_reason(proposal))
    modifier = (view or {}).get('modifier_review')
    if modifier:
        out.append(modifier['text'])
    if review.reference_check(proposal)['state'] == 'attention':
        out.append('A CMS fee-schedule check for this code needs attention.')
    return list(dict.fromkeys(out))


def _status(proposal, decision, view):
    """(status, sub_label) by CORE-UX-DESIGN.md 7: an approval is approved; a rejection, a confirmed exclusion and an
    exclusion that stands are excluded; a code that needs a detail needs one; any other is ready for review."""
    action = decision.action if decision is not None else None
    if action == Decision.APPROVE:
        reinstated = review.reinstatement_for(decision) if proposal.bucket == Proposal.EXCLUDED else None
        agent = decision.reviewer_kind == models.User.AGENT or (
            reinstated is not None and reinstated.reviewer_kind == models.User.AGENT)
        return 'approved', AGENT_SUB_LABEL if agent else ''
    if action == Decision.REJECT:
        return 'excluded', REJECTED_SUB_LABEL
    if action == Decision.CONFIRM:
        return 'excluded', CONFIRMED_SUB_LABEL
    view_status = (view or {}).get('status', proposal.status)
    if (view or {}).get('reason') == 'detail_unavailable':
        return 'excluded', UNAVAILABLE_SUB_LABEL
    if proposal.bucket == Proposal.EXCLUDED and action != Decision.REINSTATE:
        return 'excluded', CHECK_EXCLUDED_SUB_LABEL
    if view_status == Proposal.NEEDS_CLARIFICATION:
        return 'needs_detail', REINSTATED_SUB_LABEL if action == Decision.REINSTATE else ''
    return 'ready', REINSTATED_SUB_LABEL if action == Decision.REINSTATE else ''


def _decision_json(decision):
    if decision is None:
        return None
    return {'action': decision.action, 'by': decision.reviewer.label(), 'by_kind': decision.reviewer_kind,
            'at': _iso(review.decision_root(decision).created_at), 'note': decision.note,
            'modifiers': list(getattr(decision, 'modifiers', None) or [])}


def confirmation_effect(confirmation):
    """What the current assessment made of a reviewer's confirmation (review.confirmation_effect), in its fixed
    sentence: a sentence whose tail is the engine's own words is said without the tail (the dormant confirmation path,
    HARNESS.md 12.10)."""
    encounter = confirmation.encounter
    assessment = encounter.current_assessment if encounter.current_assessment_id else None
    if assessment is not None and assessment.revision_id != confirmation.revision_id:
        assessment = None
    effect = review.confirmation_effect(confirmation, assessment)
    detail = effect.get('detail') if isinstance(effect.get('detail'), str) else ''
    if detail.startswith('not read by this assessment: ') or not plain(detail):
        detail = 'not read by this assessment' if effect.get('state') != review.CONFIRMATION_READ else \
            'read by this assessment'
    return {'state': effect.get('state'), 'detail': detail}


def decision_response(decision):
    """POST decisions: the decision as the customer reads it on the code (``decision`` of the contract), and its code."""
    return {'id': str(decision.pk), 'proposal_id': str(decision.proposal_id), 'code': _code(decision.proposal.code),
            'decision': _decision_json(decision)}


def code_rows(assessment, current, view, membership=None, questions_by_proposal=None, details=()):
    """(codes, other_codes). The numbered codes: selected and reinstated codes by stored position, then the excluded
    codes a reviewer can still decide (reinstatable); alternatives and exclusions nobody can decide go to other_codes.
    ``membership``: whose allowed actions are listed (none without one). Each row carries ``_decision`` (its current
    decision's id, for the report snapshot), which the payload drops."""
    questions_by_proposal = questions_by_proposal or {}
    revision = assessment.revision
    acts = _act_index(assessment)
    proposals = list(assessment.proposals.order_by('position'))
    first, then, others = [], [], []
    for proposal in proposals:
        decision = current.get(proposal.pk)
        if proposal.bucket == Proposal.SELECTED or (proposal.bucket == Proposal.EXCLUDED and decision is not None
                                                    and decision.action != Decision.CONFIRM):
            first.append(proposal)
        elif proposal.bucket == Proposal.EXCLUDED and (proposal.reinstatable or decision is not None):
            then.append(proposal)
        else:
            others.append(proposal)
    rows = []
    for number, proposal in enumerate(first + then, start=1):
        decision = current.get(proposal.pk)
        entry = view.get(proposal.key) or {}
        status, sub_label = _status(proposal, decision, entry)
        code = _code(proposal.code)
        modifier = entry.get('modifier_review')
        rows.append({
            'id': str(proposal.pk), 'number': number, 'code': code, 'units': proposal.units,
            'modifiers': list(getattr(decision, 'modifiers', None) or []) if decision is not None else [],
            'modifier_review': ({'options': list(modifier['options']), 'text': modifier['text'],
                                 'sources': list(modifier['sources'])} if modifier else None),
            'status': status, 'status_label': STATUS_LABELS[status], 'sub_label': sub_label,
            'summary': _summary(proposal),
            'why': {'quotes': _quotes(proposal, revision.text, revision.pages, acts, status),
                    'qualifications': _qualifications(proposal, status, entry,
                                                      questions_by_proposal.get(proposal.pk, ()), code)},
            'detail_ids': [row['id'] for row in details if proposal.pk in row['_proposals']],
            'allowed_actions': (list(review.allowed_actions(proposal, assessment, membership))
                                if membership is not None else []),
            'decision': _decision_json(decision),
            '_decision': str(decision.pk) if decision is not None else None,
        })
    other_codes, listed = [], set()
    for proposal in others:
        code = _code(proposal.code)
        if not code or code in listed:
            continue
        listed.add(code)
        reason = ('Listed as an alternative only; not suggested for approval.' if proposal.bucket == Proposal.ALTERNATIVE
                  else f'Not suggested: {_exclusion_reason(proposal)[:1].lower()}{_exclusion_reason(proposal)[1:]}')
        other_codes.append({'code': code, 'reason': reason})
    return rows, other_codes


# --- the document, its date, its questions ------------------------------------------------------------------------

def _root(revision):
    root = revision
    while root.parent_id:
        root = root.parent
    return root


READING_LABELS = {SourceRevision.PENDING: 'Reading your document', SourceRevision.OK: 'Text read',
                  SourceRevision.PARTIAL: 'Text read in part', SourceRevision.FAILED: 'The text could not be read'}


def _reading(revision):
    status = revision.extraction_status if revision.extraction_status in READING_LABELS else SourceRevision.FAILED
    messages = []
    if status == SourceRevision.PARTIAL:
        messages.append(PARTIAL_READING)
    if status == SourceRevision.FAILED:
        messages.append('Upload the document again as a text-based PDF, a Word document or pasted text.')
    ocr = len([page for page in revision.ocr_pages or [] if type(page) is int])
    if ocr and status != SourceRevision.FAILED:
        messages.append(f'{ocr} page{"s were" if ocr != 1 else " was"} read from an image of the page; compare the '
                        'text with the original.')
    return {'status': status, 'label': READING_LABELS[status], 'messages': messages}


def _document(encounter, revision):
    if revision is None:
        return None
    root = _root(revision)
    source = root.source_file
    pages = [{'page': page['page'], 'start': page['start'], 'end': page['end']} for page in revision.pages or []
             if isinstance(page, dict) and all(type(page.get(key)) is int for key in ('page', 'start', 'end'))]
    return {'kind': revision.kind if revision.kind in ('upload', 'paste', 'addendum') else 'upload',
            'name': source.original_name if source else '', 'media_type': source.media_type if source else 'text/plain',
            'size': source.size if source else len((root.pasted_text or '').encode('utf-8')),
            'page_count': len(pages), 'revision': revision.number, 'text': revision.text, 'pages': pages,
            'reading': _reading(revision),
            'original_url': f'/api/encounters/{encounter.pk}/original' if source else None}


def _exact_span(span, text):
    if not isinstance(span, dict):
        return None
    start, end, quote = span.get('start'), span.get('end'), span.get('text')
    if type(start) is int and type(end) is int and isinstance(quote, str) and 0 <= start < end <= len(text) \
            and text[start:end] == quote:
        return {'text': quote, 'start': start, 'end': end}
    return None


# INTEGRATION: replaced by P5's service-date block (EncounterContext.document_date and
# context.document_service_date_fact; CORE-UX-DESIGN.md 6) - the document's own date of a member conflict is known
# here only where that field exists
def service_date_block(encounter, context=None, revision=None):
    """The date of service as the customer is shown it: the value in use, where it comes from, the document's own date
    and quote beside the date a member entered, whether they conflict and whether "Use document date" can settle it."""
    context = encounter.current_context if context is None else context
    revision = encounter.current_revision if revision is None else revision
    text = revision.text if revision is not None else ''
    facts = (context.facts or {}) if context is not None else {}
    fact = facts.get('service_date') if isinstance(facts.get('service_date'), dict) else {}
    origin = fact.get('origin')
    asked = charge_date_problem(fact) is not None if fact else False
    entered = (context.user_values or {}).get('service_date') if context is not None else None
    document_fact = getattr(context, 'document_date', None) if context is not None else None
    if not isinstance(document_fact, dict):
        document_fact = fact if origin == 'document' else None
    document_value = document_fact.get('value') if document_fact and document_fact.get('origin') == 'document' else None
    quote = None
    for span in ((document_fact or {}).get('evidence') or (fact.get('evidence') if origin == 'conflict' else None)
                 or []):
        quote = _exact_span(span, text)
        if quote:
            break
    value = fact.get('value') if origin in ('document', 'user') and isinstance(fact.get('value'), str) else None
    conflict = origin == 'conflict' and not asked
    source = 'missing' if asked else {'document': 'document', 'user': 'member', 'conflict': 'conflict'}.get(origin,
                                                                                                       'missing')
    return {'value': value, 'source': source, 'document_value': document_value if isinstance(document_value, str) else None,
            'document_quote': quote, 'entered_value': entered if isinstance(entered, str) and entered else None,
            'conflict': conflict,
            'can_use_document_date': bool(conflict and entered and isinstance(document_value, str)
                                          and entered != document_value)}


def _open_questions(assessment):
    """The open questions of the assessment, one per (fact, family, code), oldest first."""
    if assessment is None:
        return []
    out, seen = [], set()
    for question in assessment.clarifications.filter(state=models.Clarification.OPEN).select_related('proposal') \
            .order_by('created_at', 'pk'):
        key = (question.fact, question.family, question.proposal.code if question.proposal_id else '')
        if key in seen:
            continue
        seen.add(key)
        out.append(question)
    return out


def _prompt(question, code, family):
    fact = question.fact
    if fact.startswith('conflict:'):
        return (f'The document has conflicting statements about the {_act_label(fact.split(":", 1)[1])}. Was it done on '
                'the date of service?')
    prompts = {
        'service_date': 'Which date of service is right for this encounter?',
        'setting': 'Where was the patient seen (the place of service)?',
        'patient_status': 'Is the patient new or established?',
        'billing_context': 'Is this professional or facility billing?',
        'extent': f'How far was the {family.lower()} advanced?',
        'completion': f'Was the {family.lower()} completed as intended?',
        'performed_status': f'Was {code or "this service"} performed on the date of service?',
        'base_included': f'Is {code or "this code"} reported separately from the other codes for this examination?',
        'separate_em': 'Was a separate office visit documented on this date?',
        'em_basis': 'Does the visit level rest on total time or on medical decision making?',
        'target': 'Which structure was examined?',
        'cannulation': 'Was cannulation achieved?',
    }
    return prompts.get(fact, f'A detail about {code or family.lower()} needs confirming.')


# INTEGRATION: replaced by answers.details_needed (P5; CORE-UX-DESIGN.md 6) - no answer is saved in this tree
def details_needed(encounter, assessment, membership, proposals, date_block):
    """The open questions as one compact list: one row per material question with its control - a date beside the
    document's, a listed choice, or a confirmation where only "Not documented" or "Cannot confirm" may be answered (a
    member never supplies a clinical fact) - the codes it affects and its saved answer."""
    rows = []
    decidable = [p for p in proposals if review.decidable(p)]
    for question in _open_questions(assessment):
        fact = question.fact
        code = _code(question.proposal.code) if question.proposal_id else ''
        family = _family_label(question.family) if question.family else ''
        if question.proposal_id:
            affected = [question.proposal]
        elif question.scope == 'service' and question.family:
            affected = [p for p in decidable if p.family == question.family]
        else:
            affected = list(decidable)
        control = 'date' if fact == 'service_date' else 'choice' if fact in CHOICES else 'confirm'
        rows.append({
            'id': str(question.pk), 'fact': fact, 'family_label': family,
            'prompt': _prompt(question, code, family or 'procedure'), 'control': control,
            'choices': [{'value': value, 'label': label} for value, label in CHOICES.get(fact, ())],
            'allow': ['not_documented', 'cannot_confirm'] if control == 'confirm' else
            ['not_documented'] if control == 'choice' else [],
            'document_value': date_block['document_value'] if control == 'date' else None,
            'entered_value': date_block['entered_value'] if control == 'date' else None,
            'quote': date_block['document_quote'] if control == 'date' else None,
            'affects': sorted({_code(p.code) for p in affected if _code(p.code)}),
            'saved': None,
            'addendum_allowed': bool(control == 'confirm' and membership.can_review),
            '_proposals': {p.pk for p in affected},
        })
    return rows


# --- progress and the three checks (P5) ---------------------------------------------------------------------------

STEPS = (('reading', 'Reading your document'), ('identifying', 'Identifying procedures'),
         ('checking', 'Checking suggested codes'), ('preparing', 'Preparing your results'))
STEP_OF = {Job.EXTRACT: 'reading', Job.ANALYZE: 'identifying', Job.PREDICT: 'checking', Job.ASTRA: 'checking',
           Job.FABLE: 'checking', Job.ASTRA_PEER: 'checking', Job.FABLE_PEER: 'checking', Job.REVIEW2: 'checking',
           Job.ASSESS: 'preparing'}
DETAIL_OF = {Job.PREDICT: 'Document review', Job.REVIEW2: 'Document review', Job.ASTRA: 'Independent checks',
             Job.FABLE: 'Independent checks', Job.ASTRA_PEER: 'Independent checks',
             Job.FABLE_PEER: 'Independent checks', Job.ASSESS: 'Coding validation'}
PHASE_MESSAGES = {
    'queued': 'Your document is in line to be processed. You can leave this page and come back.',
    'processing': 'Your document is being processed. You can leave this page and come back; your results will be here.',
    'action_needed': 'The service date you entered differs from the document. Choose the date to use; nothing has been '
                     'sent for checking yet.',
    'awaiting_detail': 'A few details are needed before every code can be reviewed.',
    'completed': 'Your results are ready.',
    'partial': 'Your results are ready, but some checks could not be completed.',
    'failed': 'Processing could not finish.',
    'stopped': 'Processing was stopped. You can resume it.',
    'being_confirmed': 'We are confirming whether an earlier check completed. Nothing will be sent again until that is '
                       'settled.',
}
FAILED_MESSAGES = {'extraction_failed': ('The text of this document could not be read.', 'new_document'),
                   'processing_failed': ('Processing could not finish for this document.', 'none'),
                   'provider_failed': ('The coding service could not finish for this document.', 'none'),
                   'provider_not_run': ('The coding service did not run for this document.', 'none')}
PARTIAL_RECORDS = ('refused', 'failed', 'unknown', 'not_sent', 'blocked')


def _step_rows(jobs, busy, failed):
    groups = {key: [] for key, _ in STEPS}
    for index, job in enumerate(jobs):
        step = STEP_OF.get(job.kind)
        if step is None:
            continue
        if job.kind == Job.ASSESS and any(later.kind in Job.PEER_KINDS for later in jobs[index + 1:]):
            step = 'checking'  # a first assessment the peer stages follow
        groups[step].append(job)
    rows, active_seen = [], False
    for key, label in STEPS:
        group = groups[key]
        started = [job.started_at or job.created_at for job in group if job.started_at or job.created_at]
        finished = [job.finished_at for job in group if job.finished_at]
        live = [job for job in group if job.state in (Job.QUEUED, Job.RUNNING)]
        if live:
            state, active_seen = ('active' if not active_seen else 'waiting'), True
        elif not group:
            state = 'waiting' if busy and not active_seen else 'skipped' if failed else 'not_started'
            if busy and active_seen:
                state = 'waiting'
        elif group[-1].state == Job.CANCELLED:
            state = 'stopped'
        elif group[-1].state in (Job.FAILED, Job.UNKNOWN) and not any(
                groups[later] for later, _ in STEPS[STEPS.index((key, label)) + 1:]):
            state = 'failed'
        else:
            state = 'done'
        rows.append({'key': key, 'label': label, 'state': state, 'started_at': _iso(min(started)) if started else None,
                     'finished_at': _iso(max(finished)) if finished and state in ('done', 'failed', 'stopped') else None})
    return rows


# INTEGRATION: replaced by progress.encounter_progress (P5; CORE-UX-DESIGN.md 6)
def progress_block(encounter, membership, jobs, assessment, state, now=None):
    """The one compact progress panel, folded from the current revision's jobs: four plain steps with their real
    states and times, the phase, a fixed message for it, and the Stop and Resume paths. Never a percentage or an ETA."""
    from .jobs import busy as is_busy  # local import: jobs imports this module's peers

    now = now or timezone.now()
    busy = is_busy(encounter)
    stored = encounter.state
    running = [job for job in jobs if job.state == Job.RUNNING]
    queued = [job for job in jobs if job.state == Job.QUEUED]
    if busy:
        phase = 'processing' if running else 'queued'
    elif state == 'failed':
        phase = 'failed'
    elif state in ('stopped', 'being_confirmed', 'action_needed'):
        phase = state
    elif state == 'awaiting_detail':
        phase = 'awaiting_detail'
    elif state == 'processing':  # no stage runs, yet the results are not those of the current document and details
        phase = 'processing'
    elif assessment is not None and _partial(assessment, encounter):
        phase = 'partial'
    else:
        phase = 'completed'
    steps = _step_rows(jobs, busy, phase == 'failed')
    active = (running or queued)[:1]
    slow, message = False, PHASE_MESSAGES[phase]
    if running:
        job = running[0]
        bound = settings.JOB_DEADLINE_SECONDS.get(job.kind)
        began = job.started_at or job.created_at
        if bound and began and now - began > timedelta(seconds=0.6 * bound):
            slow = True
            label = dict(STEPS).get(STEP_OF.get(job.kind, ''), 'Processing')
            message = (f'{label} is taking longer than usual. It is still running and stops on its own if it cannot '
                       'finish; you can leave this page and come back.')
    error = None
    if phase == 'failed':
        text, action = FAILED_MESSAGES.get(stored, ('Processing could not finish for this document.', 'none'))
        error = {'text': text, 'action': action}
    elif phase == 'stopped':
        error = {'text': 'Processing was stopped before it finished.', 'action': 'resume'}
    times = [job.started_at or job.created_at for job in jobs if job.started_at or job.created_at]
    ends = [job.finished_at for job in jobs if job.finished_at]
    return {'phase': phase, 'busy': busy, 'steps': steps,
            'active_detail': DETAIL_OF.get(active[0].kind, '') if active else '',
            'started_at': _iso(min(times)) if times else None,
            'finished_at': _iso(max(ends)) if ends and not busy else None,
            'server_time': _iso(now), 'slow': slow, 'message': message,
            'can_stop': bool(busy and membership.can_review),
            'can_resume': bool(review.can_resume(encounter) and membership.can_review), 'can_leave': True,
            'error': error}


def _partial(assessment, encounter):
    from .serializers import retrieval_failed  # local import: the operator serializer's own predicate
    records = [record for record in assessment.participants or [] if isinstance(record, dict)]
    if any(record.get('state') in PARTIAL_RECORDS or record.get('peer_state') in PARTIAL_RECORDS for record in records):
        return True
    if any(retrieval_failed(entry) for entry in assessment.retrieval or []):
        return True
    return encounter.current_revision is not None and \
        encounter.current_revision.extraction_status == SourceRevision.PARTIAL


# INTEGRATION: replaced by P5's checks fold (progress.encounter_progress; CORE-UX-DESIGN.md 6)
def checks_block(encounter, jobs, assessment, busy):
    """Document review, independent checks and coding validation: what each functional stage did, in four words."""
    def state_of(kinds, done):
        own = [job for job in jobs if job.kind in kinds]
        if any(job.state == Job.RUNNING for job in own):
            return 'running'
        if any(job.state == Job.QUEUED for job in own) or (busy and not own):
            return 'waiting'
        if done is not None:
            return done
        if not own:
            return 'not_run'
        return 'unavailable' if own[-1].state in (Job.FAILED, Job.UNKNOWN, Job.CANCELLED) else 'done'

    run = assessment.provider_run if assessment is not None else None
    document = ('done' if run is not None and run.state == ProviderRun.SUCCEEDED and not review._refused_run(assessment)
                else 'unavailable' if run is not None else None)
    records = [record for record in (assessment.participants or [] if assessment is not None else [])
               if isinstance(record, dict)]
    if records:
        states = [record.get('state') for record in records] + [record.get('peer_state') for record in records
                                                                if 'peer_state' in record]
        independent = 'unavailable' if any(state in PARTIAL_RECORDS for state in states) else (
            'done' if any(state == 'read' for state in states) else 'not_run')
    else:
        independent = None
    validation = 'done' if assessment is not None and review.is_final(assessment) else None
    return [{'key': 'document_review', 'label': 'Document review',
             'state': state_of((Job.PREDICT, Job.REVIEW2), document)},
            {'key': 'independent_checks', 'label': 'Independent checks',
             'state': state_of(Job.PARTICIPANT_KINDS + Job.PEER_KINDS, independent)},
            {'key': 'coding_validation', 'label': 'Coding validation', 'state': state_of((Job.ASSESS,), validation)}]


# --- what is not coded, what is unresolved, what is limited -------------------------------------------------------

def _bundled_reason(item):
    from .gi.catalogue import COMMON_BUNDLED  # local import: the catalogue's own constants
    common = dict(COMMON_BUNDLED)
    why = item.get('why')
    if why == common.get('clip'):
        return 'A clip placed to prevent bleeding is not reported as a separate service.'
    if why == common.get('cannulation'):
        return 'Passing the instrument is part of the examination itself.'
    if why == common.get('biopsy_of_removed_lesion'):
        return 'A biopsy of a lesion removed in the same session is part of the removal.'
    if why == common.get('lift_injection'):
        return 'An injection that lifts a lesion for its removal is part of the removal.'
    return 'Part of the examination; not reported as a separate service.'


def _not_separately_coded(completeness, services):
    families = {service.get('id'): service.get('family') for service in services if isinstance(service, dict)}
    out = []
    for item in completeness.get('bundled') or []:
        if not isinstance(item, dict):
            continue
        label = plain(item.get('label')) or _act_label(item.get('act'))
        family = families.get(item.get('service'))
        shown = _capital(label) + (f' ({_family_label(family)})' if family else '')
        out.append({'label': shown, 'reason': _bundled_reason(item)})
    return out


def _unresolved(completeness, services):
    out = []
    for item in completeness.get('unresolved_items') or []:
        if not isinstance(item, dict):
            continue
        family = item.get('family')
        if family == 'gi.office_em':
            out.append('An office visit is mentioned but is not documented as a separate service.')
            continue
        act = item.get('act')
        what = _family_label(family) + (f': {_act_label(act)}' if isinstance(act, str) and act else '')
        reason = item.get('reason')
        if reason == 'unsupported':
            out.append(f'{what}: this service does not cover it, so no code is suggested.')
        else:
            out.append(f'{what}: no supported code was found for it.')
    if any(isinstance(service, dict) and service.get('family') == 'gi.office_em' and service.get('status') == 'uncertain'
           for service in services):
        out.append('An office visit is mentioned but is not documented as a separate service.')
    return list(dict.fromkeys(out))


def limitations(assessment, revision):
    """The concise, true limitations: what is never checked, plus what this assessment could not check."""
    from .serializers import retrieval_failed, source_applied  # local import: the operator serializer's predicates
    out = list(LIMITATIONS)
    if assessment is not None:
        if any(retrieval_failed(entry) for entry in assessment.retrieval or []):
            out.append(REFERENCE_FAILED)
        elif not source_applied(assessment.reference_sources):
            out.append(NO_REFERENCE_FILE)
        if assessment.provider_run is not None and review.run_mode(assessment.provider_run) == 'replay':
            out.append(RECORDED_RESPONSE)
    if revision is not None and revision.extraction_status == SourceRevision.PARTIAL:
        out.append(PARTIAL_READING)
    return out


# --- readiness, reports, activity ----------------------------------------------------------------------------------

# INTEGRATION: replaced by review.readiness over review.effective_view (P3; CORE-UX-DESIGN.md 4)
def readiness(encounter, assessment=None, current=None):
    """{'draft', 'approved', 'blockers'}: a draft once an assessment exists; the approved export when the review is
    complete and at least one code is approved; the blockers in the customer's words."""
    ready = review.readiness(encounter)
    assessment = review.live_assessment(encounter) if assessment is None else assessment
    blockers = customer_blockers(ready['blockers'])
    approved = bool(ready['reviewed'])
    if approved and (assessment is None or not approved_items(assessment, current)):
        approved = False
        blockers.append('No code has been approved.')
    return {'draft': bool(ready['draft']), 'approved': approved, 'blockers': blockers}


def report_json(report, current=True):
    return {'id': str(report.pk), 'kind': report.kind, 'fmt': report.fmt, 'filename': report.filename,
            'generated_at': _iso(report.generated_at), 'generated_by': report.generated_by.label(),
            'download_url': f'/api/reports/{report.pk}/download', 'current': bool(current)}


def _reports(encounter):
    from .reports import customer_digest  # local import: reports reads this module
    artifacts = list(encounter.reports.filter(audience=ReportArtifact.CUSTOMER).select_related('generated_by')
                     .order_by('-generated_at', '-pk'))
    digests = {kind: customer_digest(encounter, kind) for kind in {artifact.kind for artifact in artifacts}}
    return [report_json(artifact, artifact.snapshot_sha256 == digests.get(artifact.kind)) for artifact in artifacts]


# event -> (the customer's event key, summary); an event not listed is never shown to a customer
ACTIVITY = {
    'encounter.created': ('document_added', 'Document added'),
    'revision.extracted': ('text_read', 'Text read'),
    'revision.addendum': ('documentation_added', 'Documentation added'),
    'context.changed': ('details_changed', 'Encounter details changed'),
    'assessment.created': ('checks_completed', 'Checks completed'),
    'decision.recorded': ('decision_recorded', 'Review decision recorded'),
    'decisions.invalidated': ('decisions_cleared', 'Earlier decisions were cleared because the document changed'),
    'report.generated': ('report_created', 'Export created'),
    'pipeline.stopped': ('processing_stopped', 'Processing stopped'),
    'pipeline.resumed': ('processing_resumed', 'Processing resumed'),
    'provider.second_review_requested': ('check_requested', 'Another check of an unresolved service was requested'),
    'detail.answered': ('detail_answered', 'A detail was answered'),
    'assessment.refreshed': ('results_refreshed', 'Results were refreshed with updated software'),
    'finding.confirmed': ('detail_confirmed', 'A detail was confirmed'),
}


def activity(encounter):
    out = []
    for event in encounter.audit_events.select_related('actor').order_by('created_at', 'pk'):
        entry = ACTIVITY.get(event.event)
        if entry is None:
            continue
        data = event.data if isinstance(event.data, dict) else {}
        if event.event == 'report.generated' and data.get('audience', ReportArtifact.CUSTOMER) != ReportArtifact.CUSTOMER:
            continue  # an operator's report is the operator's record, never the practice's activity
        actor = event.actor
        kind = event.actor_kind if event.actor_kind in ('human', 'agent') else 'system'
        out.append({'event': entry[0], 'summary': entry[1], 'actor': actor.label() if actor else 'CPT Studio',
                    'actor_kind': kind, 'at': _iso(event.created_at)})
    return out


# --- the payloads --------------------------------------------------------------------------------------------------

def _date_hold(encounter, assessment):
    """Whether nothing was sent because the member's service date conflicts with the document (the held request)."""
    if assessment is None or assessment.context_id != encounter.current_context_id:
        return False
    run = assessment.provider_run
    return (run is not None and run.state == ProviderRun.NOT_SENT
            and (run.scope or {}).get('held') == ProviderRun.HELD_MEMBER_DATE_CONFLICT)


def customer_state(encounter, assessment=None):
    state = STORED_STATES.get(encounter.state, 'processing')
    if state in ('awaiting_detail', 'ready', 'no_codes', 'reviewed'):
        assessment = review.live_assessment(encounter) if assessment is None else assessment
        if _date_hold(encounter, assessment):
            return 'action_needed'
    return state


def session_json(user, membership):
    from .serializers import QUEUE_STATES, _initials, queue_reasons  # local import: the review queue's own rule
    workspace = membership.workspace
    encounters = workspace.encounters.select_related('current_revision', 'current_context', 'current_assessment')
    queued = sum(1 for encounter in encounters if encounter.state in QUEUE_STATES or queue_reasons(encounter))
    return {'user': {'id': str(user.pk), 'label': user.label(), 'initials': _initials(user),
                     'actor_kind': user.actor_kind},
            'workspace': {'id': str(workspace.pk), 'name': workspace.name},
            'role': membership.role, 'can_review': membership.can_review,
            'acknowledgement': review.ACKNOWLEDGEMENTS.get(user.actor_kind, ''),
            'counts': {'documents': encounters.count(), 'queue': queued},
            'synthetic_only': settings.SYNTHETIC_ONLY}


def list_row(encounter):
    assessment = review.live_assessment(encounter)
    state = customer_state(encounter, assessment)
    date = service_date_block(encounter)
    revision = encounter.current_revision
    return {'id': str(encounter.pk), 'title': encounter.title, 'state': state, 'state_label': STATE_LABELS[state],
            'service_date': date['value'], 'date_conflict': date['conflict'],
            'open_details': len(_open_questions(assessment)), 'created_at': _iso(encounter.created_at),
            'kind': revision.kind if revision is not None and revision.kind in ('upload', 'paste', 'addendum')
            else 'upload'}


def encounter_json(encounter, membership):
    """GET /api/encounters/<id> (CORE-UX-DESIGN.md 7): every key listed, nothing else."""
    from .jobs import busy as is_busy  # local import: jobs imports this module's peers

    revision = encounter.current_revision
    assessment = review.live_assessment(encounter)
    jobs = list(encounter.jobs.filter(revision=revision).order_by('created_at', 'pk')) if revision else []
    state = customer_state(encounter, assessment)
    date = service_date_block(encounter)
    current = review.current_decisions(assessment) if assessment is not None else {}
    proposals = list(assessment.proposals.order_by('position')) if assessment is not None else []
    details = details_needed(encounter, assessment, membership, proposals, date) if assessment is not None else []
    questions = {}
    for question in _open_questions(assessment):
        if question.proposal_id:
            questions.setdefault(question.proposal_id, []).append(question)
    if assessment is not None:
        view = effective_view(assessment, current)
        codes, other_codes = code_rows(assessment, current, view, membership, questions, details)
        codes = [{key: value for key, value in row.items() if not key.startswith('_')} for row in codes]
        completeness = review.reviewed_completeness(assessment, current) or {}
        services = [service for service in (assessment.services or {}).get('services') or [] if isinstance(service, dict)]
    else:
        codes, other_codes, completeness, services = [], [], {}, []
    busy = is_busy(encounter)
    return {
        'id': str(encounter.pk), 'title': encounter.title, 'created_at': _iso(encounter.created_at),
        'updated_at': _iso(encounter.updated_at), 'state': state, 'state_label': STATE_LABELS[state],
        'permissions': {'can_review': bool(membership.can_review)},
        'document': _document(encounter, revision),
        'service_date': date,
        'progress': progress_block(encounter, membership, jobs, assessment, state),
        'checks': checks_block(encounter, jobs, assessment, busy),
        'codes': codes, 'other_codes': other_codes,
        'not_separately_coded': _not_separately_coded(completeness, services),
        'details_needed': [{key: value for key, value in row.items() if not key.startswith('_')} for row in details],
        'unresolved': _unresolved(completeness, services),
        'limitations': limitations(assessment, revision),
        'readiness': readiness(encounter, assessment, current),
        'reports': _reports(encounter),
        'activity': activity(encounter),
    }
