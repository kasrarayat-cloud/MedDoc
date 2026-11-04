"""The customer contract (CORE-UX-DESIGN.md 7): every payload a workspace member is served, built by ALLOWLIST.

Nothing here passes a stored dict or stored free text through (R4-api-leak-surface 6.1(1)). The engine's sentences, the
adapters' errors, the participants' readings and the job errors name vendors, models, rule ids and request ids, and they
sit on immutable rows - so every customer sentence is re-derived here from structured fields (statuses, check ids and
their states, act kinds, exact spans of the document) in CPT Studio's own fixed wording, and every key is written out.
A label CPT Studio composed from the document's own words (an act's anatomy, a lesion) is used only when it passes the
server-side guard (``plain``); otherwise the fixed sentence stands in for it. The complete record - providers, models,
usage, runs, hashes, rule ids, the trace - stays available to platform operators at /ops/ (studio.operator), served by
studio.serializers, which is the operator serializer and is never called for a customer.

What other layers decide is read from them, never decided again here: every status, check, open question, approve
gate, readiness blocker, modifier review and summary from the review overlay (review.effective_view: the assessment as
its current decisions and the member's standing answers leave it); the approved export's items from
review.approved_items; readiness from review.readiness over that overlay; the date of service, the details rows, the
progress panel and the three checks from P5's answers.service_date_block, answers.details_needed, progress.
encounter_progress and progress.checks_summary. This module only words them for a member, by allowlist.
"""
from __future__ import annotations

import re

from django.conf import settings

from . import answers, models, progress, review
from .gi.profiles import PROFILES
from .models import Decision, Proposal, ProviderRun, ReportArtifact, SourceRevision

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
# the member's answer that left a code's needed detail unavailable (review_view.View.answer)
UNAVAILABLE_SUB_LABELS = {'not_documented': UNAVAILABLE_SUB_LABEL,
                          'cannot_confirm': 'A needed detail could not be confirmed'}
# What waits on a member (the review queue, and the session's count of it): a date to choose, details to answer, codes to
# review - exactly the states the customer page lists in its queue (app.js QUEUE_STATES)
QUEUE_STATES = ('action_needed', 'awaiting_detail', 'ready')
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
# built from the document's own words that matches falls back to CPT Studio's fixed sentence. The readers' own words
# (routing, reader, cue, own passage: the engine's support details carry them) are machinery too.
FORBIDDEN = re.compile(
    r'(?i)\b(?:corti|astra|fable|openai|anthropic|claude)\b|\bgpt-\d|\bclaude-[a-z]|@cptstudio-|\bcpt-studio:[a-z]'
    r'|(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])|\b(?:participants?|peer[ -]reviews?|vendors?|tokens?|credits?|traces?'
    r'|sha256|tool calls?|request ids?|replay|providers?|routing|readers?|cues?|own passages?)\b'
    r'|\b[a-z]+[.-][a-z_]+@\d+\b')


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
    # the details flow's own refusals (answers.py), already in the member's words
    answers.BUSY: None,
    answers.STALE: None,
    answers.ALREADY_WITHDRAWN: None,
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
    # the review overlay's blockers of an approval it no longer supports (review_view.review_view, _held_blocker)
    (re.compile(CODE + r' was approved, but a detail it needs was answered as (not documented|cannot be confirmed|'
                       r'unavailable): revoke the approval'),
     lambda m: f'{m.group(1)} was approved, but a detail it needs was answered as {m.group(2)}; undo the decision.'),
    (re.compile(CODE + r' was approved, but its examination is the endoscopic portion of the endoscopic ultrasound '
                       r'documented with it and is normally included in it; revoke the approval'),
     lambda m: f'{m.group(1)} was approved, but its examination is part of the endoscopic ultrasound documented with '
               'it and is normally included in it; undo the decision.'),
    (re.compile(CODE + r' was approved, but ([0-9A-Z, and]{4,200}) (was reinstated|were reinstated|is selected|are '
                       r'selected): its diagnostic examination is normally included in (that intervention|those '
                       r'interventions); revoke one of the decisions'),
     lambda m: f'{m.group(1)} was approved, but {m.group(2)} {m.group(3)}: its diagnostic examination is normally '
               f'included in {m.group(4)}; undo one of the decisions.'),
    (re.compile(CODE + r' was approved, but the documented ([a-z ]{1,60}) includes ([^\n;]{1,200}), which this '
                       r'diagnostic code does not account for; revoke the approval'),
     lambda m: plain(f'{m.group(1)} was approved, but the documented {m.group(2)} includes {m.group(3)}, which this '
                     'diagnostic code does not account for; undo the decision.')),
    (re.compile(CODE + r' was approved, but it now needs clarification; revoke the approval'),
     lambda m: f'{m.group(1)} was approved, but it now needs a detail; undo the decision.'),
    (re.compile(CODE + r' was approved with modifier (59|XS), but the separate-lesion modifier review no longer '
                       r'applies to it; revoke the approval and decide it again'),
     lambda m: f'{m.group(1)} was approved with modifier {m.group(2)}, but the separate-lesion modifier review no '
               'longer applies to it; undo the decision and decide it again.'),
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
            return words(match) or 'The review is not complete yet.'
    return 'The review is not complete yet.'


def customer_blockers(blockers) -> list:
    return list(dict.fromkeys(customer_blocker(item) for item in blockers or []))


# --- the effective review view and the approved items (P3: review.effective_view, review.approved_items) ----------

def views_of(assessment, current=None):
    """{proposal key: review_view.View}: ``assessment`` as its current decisions and the member's standing answers leave
    it (review.effective_view) - every status, check, open question, approve gate, readiness blocker, modifier review and
    summary this module words is read from it. {} without an assessment."""
    return review.effective_view(assessment, current) if assessment is not None else {}


MODIFIER_FALLBACK = ('Separate lesions are documented for these codes. Whether an NCCI procedure-to-procedure edit pairs '
                     'them, and which modifier your payer accepts (59 or XS), is not checked here. No modifier is added '
                     'unless the reviewer chooses one.')


def _source_words(source):
    """A modifier review's dated CMS source as the customer is shown it (its title, release, effective date and page),
    or '' when it does not pass the guard: never its key, url or hash."""
    if not isinstance(source, dict):
        return ''
    title, release = str(source.get('title') or ''), str(source.get('release') or '')
    effective, page = str(source.get('effective_start') or ''), str(source.get('page') or '')
    dated = '; '.join(item for item in (release, f'in effect from {effective}' if effective else '') if item)
    return plain(f'{title}' + (f' ({dated})' if dated else '') + (f', page {page}' if page else ''))


def modifier_review_of(view):
    """The contract's ``modifier_review`` ({options, text, sources}) from the overlay's structured separate-lesion
    review of the code over the effective set (None when none applies - and so dropped when the other code leaves it):
    the options it offers, its plain text (a fixed sentence when the text names anything the guard refuses) and its
    dated sources. The options stay whatever the text says, because the reviewer chooses from them (record_decision)."""
    found = getattr(view, 'modifier_review', None) if view is not None else None
    if not isinstance(found, dict):
        return None
    options = [option for option in found.get('options') or [] if option in ('59', 'XS')]
    if not options:
        return None
    sources = [words for words in (_source_words(source) for source in found.get('sources') or []) if words]
    return {'options': options, 'text': plain(found.get('text')) or MODIFIER_FALLBACK, 'sources': sources}


def approved_export_items(assessment, current, views):
    """The approved export's items (review.approved_items: approved decisions only, never an unresolved or unapproved
    item, nor an approval the overlay no longer supports), in stored order, as the customer report prints them: code,
    units, the reviewer's chosen modifier, approver, approver kind, whether agent review is involved, decision time and
    id, the one-sentence summary and the exact passages the approval rests on (with page and character offsets)."""
    proposals = {str(proposal.pk): proposal for proposal in assessment.proposals.all()}
    items = []
    for item in review.approved_items(assessment):
        proposal = proposals[item['proposal_id']]
        decision = current[proposal.pk]
        reinstated = review.reinstatement_for(decision) if proposal.bucket == Proposal.EXCLUDED else None
        items.append({
            'proposal_id': item['proposal_id'], 'decision_id': str(decision.pk), 'code': _code(item['code']),
            'units': item['units'], 'modifiers': list(item['modifiers']), 'approver': item['approved_by'],
            'approver_kind': item['approver_kind'],
            'agent': item['approver_kind'] == models.User.AGENT or (
                reinstated is not None and reinstated.reviewer_kind == models.User.AGENT),
            'decided_at': item['decided_at'], 'note': item['note'],
            'evidence': [{'text': span['text'], 'start': span['start'], 'end': span['end'], 'page': span.get('page')}
                         for span in item['evidence']],
            'summary': code_summary(proposal, views.get(proposal.key))})
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
    """One sentence from the code's support record alone - the documented service's family and the acts the code
    accounts for, as CPT Studio's reading labels them - for a code the overlay's summary does not describe (its matched
    service is not in the recorded reading, or the guard refuses its words)."""
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


def code_summary(proposal, view):
    """The code's one sentence of CPT Studio's own reading (CORE-UX-DESIGN.md 7): the overlay's (review_view.summary:
    the documented service, its state and the acts the code accounts for, from the recorded reading's structured fields
    and act labels - never a support detail, a provider's wording or any stored free text), else _summary's."""
    return plain(getattr(view, 'summary', '') if view is not None else '') or _summary(proposal)


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
# why approve is withheld from a code the list shows as ready (review_view.View.withheld_by, same_day_held)
WITHHELD_WORDS = {
    'review.reinstatement': 'This reinstated code needs a detail before it can be approved.',
    'em.same_day_if_reinstated': 'A separately identifiable office visit is not documented beside the procedure '
                                 'reinstated for the same day.',
}
STALE_WORDS = ('After the review decisions, a check that depends on the other codes could not be recomputed for this '
               'code.')


def _reference_attention(proposal, view):
    """Whether a CMS fee-schedule check of the code warns or fails, as the overlay leaves its checks (an endoscopic-
    family check is recomputed over the effective set) - review.reference_check's 'attention'."""
    checks = view.checks if view is not None else proposal.checks or []
    return any(isinstance(check, dict) and check.get('id') in review.CMS_CHECKS and check.get('status') in ('warn', 'fail')
               for check in checks)


def _qualifications(proposal, status, view, code):
    """What qualifies the code, in fixed sentences: why it needs a detail (a conflict, each open question the overlay
    leaves it), why approve is withheld, why it is excluded, a decision the overlay no longer supports (its readiness
    blocker), a check that could not be recomputed, its modifier review and a CMS fee-schedule check that needs
    attention."""
    support = proposal.support or {}
    questions = list(view.questions) if view is not None else []
    out = []
    if status == 'needs_detail' and support.get('reason') == 'conflict':
        kinds = [act.get('kind') for act in support.get('acts') or [] if isinstance(act, dict)]
        out.append(f'The document has conflicting statements about the {_act_label(kinds[0] if kinds else "")}; '
                   'a detail is needed before this code can be approved.')
    if status in ('needs_detail', 'ready'):
        for question in questions:
            fact = question.get('fact') if isinstance(question, dict) else ''
            if fact == 'base_included':
                out.append(f'{code} may be included in another code reported for this examination; a detail is '
                           'needed before it can be approved.' if code else
                           'This code may be included in another code reported for this examination.')
            elif fact in QUESTION_WORDS:
                out.append(QUESTION_WORDS[fact])
        if status == 'needs_detail' and not out:
            out.append('A detail is needed before this code can be approved.')
        withheld = view.withheld_by if view is not None else ''
        if withheld in WITHHELD_WORDS:
            out.append(WITHHELD_WORDS[withheld])
        if view is not None and view.same_day_held:
            out.append(WITHHELD_WORDS['em.same_day_if_reinstated'])
    if status == 'excluded' and proposal.bucket == Proposal.EXCLUDED and not (view is not None
                                                                           and view.reason == review.DETAIL_UNAVAILABLE):
        out.append(_exclusion_reason(proposal))
    if view is not None and view.reason == review.DETAIL_UNAVAILABLE:
        out.append('A detail this code needs was answered as not documented or not confirmable, so it is excluded '
                   'until that answer is withdrawn.')
    if view is not None and view.blocker:
        out.append(customer_blocker(view.blocker))
    if view is not None and view.stale:
        out.append(STALE_WORDS)
    modifier = modifier_review_of(view)
    if modifier:
        out.append(modifier['text'])
    if _reference_attention(proposal, view):
        out.append('A CMS fee-schedule check for this code needs attention.')
    return list(dict.fromkeys(out))


def _status(proposal, decision, view):
    """(status, sub_label) by CORE-UX-DESIGN.md 7 over the review overlay: an approval is approved; a rejection, a
    confirmed exclusion, an exclusion that stands and a code whose needed detail a member answered as unavailable
    (review.DETAIL_UNAVAILABLE) are excluded; a code the overlay leaves needing clarification needs a detail; any other
    is ready for review."""
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
    if view is not None and view.reason == review.DETAIL_UNAVAILABLE:
        return 'excluded', UNAVAILABLE_SUB_LABELS.get(view.answer, UNAVAILABLE_SUB_LABEL)
    if proposal.bucket == Proposal.EXCLUDED and action != Decision.REINSTATE:
        return 'excluded', CHECK_EXCLUDED_SUB_LABEL
    status = view.status if view is not None else proposal.status
    if status == Proposal.NEEDS_CLARIFICATION:
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


def code_rows(assessment, current, views, membership=None, details=()):
    """(codes, other_codes). The numbered codes: selected and reinstated codes by stored position, then the excluded
    codes a reviewer can still decide (reinstatable); alternatives and exclusions nobody can decide go to other_codes.
    ``views``: views_of(assessment, current), the overlay every status, question, gate and modifier review is read
    from. ``membership``: whose allowed actions are listed (none without one). ``details``: the details rows; a code's
    ``detail_ids`` are the rows whose ``affects`` name it. Each row carries ``_decision`` (its current decision's id),
    which the payload drops."""
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
        view = views.get(proposal.key)
        status, sub_label = _status(proposal, decision, view)
        code = _code(proposal.code)
        rows.append({
            'id': str(proposal.pk), 'number': number, 'code': code, 'units': proposal.units,
            'modifiers': list(getattr(decision, 'modifiers', None) or []) if decision is not None else [],
            'modifier_review': modifier_review_of(view),
            'status': status, 'status_label': STATUS_LABELS[status], 'sub_label': sub_label,
            'summary': code_summary(proposal, view),
            'why': {'quotes': _quotes(proposal, revision.text, revision.pages, acts, status),
                    'qualifications': _qualifications(proposal, status, view, code)},
            'detail_ids': [row['id'] for row in details if code and code in row['affects']],
            'allowed_actions': (list(review.allowed_actions(proposal, assessment, membership, views))
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


# --- the details needed (P5: answers.details_needed over the review overlay) ----------------------------------------

def details_rows(encounter, assessment, views, membership):
    """The contract's ``details_needed``: answers.details_needed's rows - one per open material question the overlay
    leaves the live assessment (and the date of service at once while a member's date conflicts with the document),
    each with its control, the codes it affects and its saved answer - with the physician's addendum path offered only
    to a member whose role may add documentation."""
    rows = answers.details_needed(encounter, assessment, views if assessment is not None else None)
    can = bool(membership is not None and membership.can_review)
    return [{**row, 'addendum_allowed': bool(row['addendum_allowed'] and can)} for row in rows]


# --- progress and the three checks (P5: progress.encounter_progress, progress.checks_summary) ----------------------

def progress_block(encounter, membership):
    """The contract's ``progress`` (progress.encounter_progress: the four plain steps, one phase, the server's clock;
    never a percentage or an estimate), with Stop, Resume and the error's action offered only to a member whose role may
    take them."""
    block = progress.encounter_progress(encounter)
    can = bool(membership is not None and membership.can_review)
    block['can_stop'] = bool(block['can_stop'] and can)
    block['can_resume'] = bool(block['can_resume'] and can)
    if isinstance(block.get('error'), dict) and not can:
        block['error'] = {**block['error'], 'action': 'none'}
    return block


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

NONE_APPROVED = 'No code has been approved.'
NOT_COMPLETE = 'The review is not complete yet.'


def readiness(encounter, assessment=None, current=None):
    """{'draft', 'approved', 'blockers'}: a draft once an assessment exists; the approved export only when the review
    is complete (review.readiness over the review overlay: every suggested code resolved - approved, rejected, its
    exclusion confirmed, or its needed detail answered as unavailable - nothing processing, a settled result, no
    decision the overlay no longer supports) and it has an approved code to list (session decision (f) of 2026-11-03:
    the approved export lists the approved codes only, and a partial one is never built). The blockers in the
    customer's words."""
    ready = review.readiness(encounter)
    blockers = customer_blockers(ready['blockers'])
    approved = bool(ready['reviewed'])
    if approved:
        assessment = review.live_assessment(encounter) if assessment is None else assessment
        current = review.current_decisions(assessment) if current is None else current
        listed = {item['proposal_id'] for item in review.approved_items(assessment)}
        decided = {str(pk) for pk, decision in current.items() if decision.action == Decision.APPROVE}
        if not listed:
            approved = False
            blockers.append(NONE_APPROVED)
        elif listed != decided:  # never an export that leaves out an approval the decisions hold
            approved = False
            blockers.append(NOT_COMPLETE)
    return {'draft': bool(ready['draft']), 'approved': approved, 'blockers': list(dict.fromkeys(blockers))}


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
    # the details flow's own rows, in its own words (answers.ACTIVITY_SUMMARIES)
    'detail.answered': ('detail_answered', answers.ACTIVITY_SUMMARIES['detail.answered']),
    'detail.revoked': ('detail_withdrawn', answers.ACTIVITY_SUMMARIES['detail.revoked']),
    'assessment.refreshed': ('results_refreshed', answers.ACTIVITY_SUMMARIES['assessment.refreshed']),
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
    """The encounter's state as a member reads it. "Action needed" as soon as the current context holds a member's
    date that conflicts with the document (progress.date_held, the progress phase's own reading: known right after the
    document is read, before anything is sent), as the list and the document page both say it."""
    if progress.date_held(encounter):
        return 'action_needed'
    state = STORED_STATES.get(encounter.state, 'processing')
    if state in ('awaiting_detail', 'ready', 'no_codes', 'reviewed'):
        assessment = review.live_assessment(encounter) if assessment is None else assessment
        if _date_hold(encounter, assessment):
            return 'action_needed'
    return state


def session_json(user, membership):
    from .serializers import _initials  # local import: the operator serializer's own initials rule
    workspace = membership.workspace
    encounters = list(workspace.encounters.select_related('current_revision', 'current_context',
                                                          'current_assessment'))
    queued = sum(1 for encounter in encounters if customer_state(encounter) in QUEUE_STATES)
    return {'user': {'id': str(user.pk), 'label': user.label(), 'initials': _initials(user),
                     'actor_kind': user.actor_kind},
            'workspace': {'id': str(workspace.pk), 'name': workspace.name},
            'role': membership.role, 'can_review': membership.can_review,
            'acknowledgement': review.ACKNOWLEDGEMENTS.get(user.actor_kind, ''),
            'counts': {'documents': len(encounters), 'queue': queued},
            'synthetic_only': settings.SYNTHETIC_ONLY}


def list_row(encounter):
    """One row of GET /api/encounters: its state, the date of service in use and whether a member's date conflicts with
    the document's (answers.service_date_block), and the details still unanswered (the rows the document page shows
    without a saved answer)."""
    assessment = review.live_assessment(encounter)
    state = customer_state(encounter, assessment)
    date = answers.service_date_block(encounter)
    revision = encounter.current_revision
    rows = answers.details_needed(encounter, assessment, views_of(assessment) if assessment is not None else None)
    return {'id': str(encounter.pk), 'title': encounter.title, 'state': state, 'state_label': STATE_LABELS[state],
            'service_date': date['value'], 'date_conflict': date['conflict'],
            'open_details': sum(1 for row in rows if row['saved'] is None), 'created_at': _iso(encounter.created_at),
            'kind': revision.kind if revision is not None and revision.kind in ('upload', 'paste', 'addendum')
            else 'upload'}


def encounter_json(encounter, membership):
    """GET /api/encounters/<id> (CORE-UX-DESIGN.md 7): every key listed, nothing else."""
    revision = encounter.current_revision
    assessment = review.live_assessment(encounter)
    state = customer_state(encounter, assessment)
    current = review.current_decisions(assessment) if assessment is not None else {}
    views = views_of(assessment, current)
    details = details_rows(encounter, assessment, views, membership)
    if assessment is not None:
        codes, other_codes = code_rows(assessment, current, views, membership, details)
        codes = [{key: value for key, value in row.items() if not key.startswith('_')} for row in codes]
        completeness = review.reviewed_completeness(assessment, current) or {}
        services = [service for service in (assessment.services or {}).get('services') or [] if isinstance(service, dict)]
    else:
        codes, other_codes, completeness, services = [], [], {}, []
    return {
        'id': str(encounter.pk), 'title': encounter.title, 'created_at': _iso(encounter.created_at),
        'updated_at': _iso(encounter.updated_at), 'state': state, 'state_label': STATE_LABELS[state],
        'permissions': {'can_review': bool(membership.can_review)},
        'document': _document(encounter, revision),
        'service_date': answers.service_date_block(encounter),
        'progress': progress_block(encounter, membership),
        'checks': progress.checks_summary(encounter),
        'codes': codes, 'other_codes': other_codes,
        'not_separately_coded': _not_separately_coded(completeness, services),
        'details_needed': details,
        'unresolved': _unresolved(completeness, services),
        'limitations': limitations(assessment, revision),
        'readiness': readiness(encounter, assessment, current),
        'reports': _reports(encounter),
        'activity': activity(encounter),
    }
