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
from dataclasses import dataclass

from django.conf import settings

from . import answers, jobs, models, progress, review
from .gi.profiles import PROFILES
from .interpretation import readers, sentinel
from .interpretation.wording import MISSING as EVENT_FACTS_MISSING
from .models import Decision, Proposal, ProviderRun, ReportArtifact, SourceRevision
from .validation import questions

# --- the customer vocabulary --------------------------------------------------------------------------------------

STATE_LABELS = {
    'processing': 'Processing', 'action_needed': 'Action needed', 'awaiting_detail': 'A few details needed',
    'ready': 'Ready for review', 'reviewed': 'Reviewed', 'no_codes': 'No codes suggested', 'stopped': 'Stopped',
    'failed': 'Could not finish', 'being_confirmed': 'Being confirmed',
    # FINAL-V2 amendment 1, 5.1 (step 3c): the customer state while the codes are updated after a save
    'updating': 'Updating codes',
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
# The customer states that wait on the member (a date to choose, details to answer, codes to review): the review queue
# lists these and what the review queue's own rule holds waiting (in_queue).
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
              'separate_em': 'a separate office visit',
              'competing_codes': 'which of the codes proposed for the same act the documentation supports',
              # the Gemini migration's facts (design/FINAL.md 7.4, 8.3), in their own words
              **EVENT_FACTS_MISSING}
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
# The Gemini migration (design/FINAL.md 8.3): what a new-path assessment's reading can miss, naming no provider or model
# (D22). It takes the place of LIMITATIONS' last sentence, which describes the earlier reading's wording checks.
EVENTS_READING = ('The procedures documented were read by an automated interpreter, whose reading of each act is checked '
                  "against the document's own words; it can still misread an act, so decide from the whole document.")

# A server-composed customer string is refused when it carries any of these (the regex net of R4 6.6(3)): a label
# built from the document's own words that matches falls back to CPT Studio's fixed sentence. The readers' own words
# (routing, reader, cue, own passage: the engine's support details carry them) are machinery too.
# FINAL-V2 4.12 [R:MO-2]: a provider name is bounded by letters and digits, never by \b - '_' is a word character, so
# \bgemini\b let gemini_unknown and reading_gemini_x through - and so it is never matched inside a clinical word that
# begins with a name (corticosteroid, cortical). PROVIDER_JOINED (step 3c's fail-closed reading of "joined forms",
# recorded as a question): a capitalized name joined to a word by its case alone (GeminiTimeout, readingGemini), which
# the letter-and-digit boundary cannot see; matched case-sensitively, so it never matches Corticosteroid or CORTICAL.
PROVIDER_NAMES = 'corti|astra|fable|openai|anthropic|claude|gemini|google'
PROVIDER_JOINED = 'Corti|Astra|Fable|Openai|OpenAI|Anthropic|Claude|Gemini|Google'
FORBIDDEN = re.compile(
    rf'(?i)(?<![a-z0-9])(?:{PROVIDER_NAMES})(?![a-z0-9])'
    rf'|(?-i:(?:{PROVIDER_JOINED})(?=[A-Z])|(?<=[a-z])(?:{PROVIDER_JOINED}))'
    r'|\bgpt-\d|\bclaude-[a-z]|\bgemini-\d'
    r'|@cptstudio-|\bcpt-studio:[a-z]'
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
    from .code_shapes import act_label  # the reconciliation's own constant labels, re-homed (ADJUDICATION R-2)
    return act_label(kind) if isinstance(kind, str) and kind else 'act'


def _code(value) -> str:
    """A code as the customer is shown it: only in a code's shape (letters and digits, at most 10), else ''."""
    return value if isinstance(value, str) and re.fullmatch(r'[0-9A-Z]{4,10}', value) else ''


# --- design v2: the appraise stage, the held facts, and amendment 1's customer texts (step 3c) ----------------------
#
# FINAL-V2 4.12: progress names functions, never vendors - pass 2's step detail and its slow message, for
# progress.DETAILS['appraise'] and SLOW_MESSAGES (step 5b; progress.py must read this module inside a function, or
# hold equal literals pinned by a test: this module imports progress at its top). FINAL-V2 4.8 and 4.12 [R:MO-2]: a reviewer sees each held fact only as CPT
# Studio's fixed sentence for its fact key (held_fact_words), never its cause.
#
# FINAL-V2 amendment 1 (DECISIONS D208; its sections 1.4, 3.9, 5.1-5.4, 6.2, 7.1-7.3): every customer text of the
# automatic update, as constants - the TEXTS and their keys only. The functions that read an update's state for the page
# (encounter_json's update keys, what_changed, decision_history, readiness by update state) are step 5d's, which uses
# these and never re-words them. Where the amendment gives a text verbatim it is here verbatim (tests/v2/
# test_update_customer.py finds each in AMENDMENT-1.md). The derived forms follow 7.1's three rules, each written out
# and checked by the test against the rule applied to the base text: CASE C (update.kind 'documentation': no restore
# clause; "from before your change" reads "from before the documentation was added"; the too-long and the
# could-not-be-prepared texts end "Upload the document again, shorter or split, to have it read."), NO RESTORE
# (update.restorable false within one revision: every restore clause dropped; the too-long text ends "Shorten the
# document and upload it again."), and CHECK (update.kind 'check', A21: no "Your change is saved"; "from before your
# change" and "from before your latest change" read "from before this update"; "after your change" dropped; no restore
# clause). Every one names no provider or model and carries no held-fact cause.

APPRAISE_DETAIL = 'Checking the reading against the document'  # FINAL-V2 4.12, verbatim
APPRAISE_SLOW = 'Checking the reading against the document is taking longer than usual for this document.'

# FINAL-V2 4.4: the causes a held fact can carry (operator data). No customer string carries one (tests: the scan).
HELD_FACT_CAUSES = ('reading_unknown', 'reading_contradicted', 'unestablished:', 'appraisal:', 'relation:', 'unlisted',
                    'coding_rule:', 'context_missing', 'date_unknown')


def held_fact_words(fact) -> str:
    """CPT Studio's fixed sentence for a held fact's key (FINAL-V2 4.8: support.held_facts is shown to the reviewer
    "only as CPT Studio's fixed sentence per fact key, never a cause" [R:MO-2]): BLOCKER_TEMPLATES' open-clarification
    sentence over FACT_WORDS (which carries wording.MISSING, the five new facts of D181 among them), and for a conflict
    (conflict:<kind>) the statement about that act - the act's label only when <kind> is one of the contract's act kinds.
    It takes the key alone, so no cause can reach it; a key it does not know reads the encounter's generic detail."""
    from .interpretation.contract.types import Kind  # local import: the contract's kinds, for a conflict's act label
    text = fact if isinstance(fact, str) else ''
    if text.startswith('conflict:'):
        kind = text.split(':', 1)[1]
        known = kind in {member.value for member in Kind}
        return f'A detail is needed: {questions.missing("conflict:", _act_label(kind) if known else "act")}.'
    return f'A detail is needed: {FACT_WORDS.get(text, "a detail of the encounter")}.'


# 5.1: the progress panel's title while an update is pending, and for kind 'check' (A21, nothing saved): the state label
UPDATE_TITLE = 'Changes saved—updating codes'
UPDATE_TITLE_CHECK = 'Updating codes'
# 5.1: what was saved, from the update block (the saved values in the member's words: answers.CHOICE_LABELS)
CHANGE_SERVICE_DATE = 'Date of service: {date}'
CHANGE_SERVICE_DATE_REMOVED = 'Date of service removed'
CHANGE_SETTING = 'Place of service: {value}'
CHANGE_PATIENT_STATUS = 'Patient: {value}'
CHANGE_BILLING_CONTEXT = 'Claim: {value}'
CHANGE_DOCUMENTATION = 'Documentation added (revision {n})'
CHANGE_SAVED_BY = 'Saved by {member}, {time}'
# 5.1 [R3:binding-R3B-6]: the one fixed line shown in place of an empty saved-changes list, by why the codes are updated
SAVED_CHANGES_UNFINISHED = ('The codes from before your change were not finished; they are being finished for these '
                            'details.')
SAVED_CHANGES_SAME_DETAILS = ('These are the details of the codes from before your change; the codes are made again '
                              'because your answers, or an earlier check, changed since those codes were made.')
SAVED_CHANGES_CHECK = 'An earlier check was settled, so the document is being read again with the current reading.'
SAVED_CHANGES_EMPTY = {'unfinished': SAVED_CHANGES_UNFINISHED, 'same_details': SAVED_CHANGES_SAME_DETAILS,
                       'check': SAVED_CHANGES_CHECK}
# 5.1: the earlier codes' section, true in every update state [R:truth-T4]
EARLIER_CODES_HEADING = 'Codes from before your change'
EARLIER_CODES_HEADING_CHECK = 'Codes from before this update'
EARLIER_CODES_MADE = ('Made {time}, with date of service {date}. They cannot be approved or exported: they are from '
                      'before your latest change.')
EARLIER_CODES_MADE_CHECK = ('Made {time}, with date of service {date}. They cannot be approved or exported: they are '
                            'from before this update.')
# 5.1: a detail row that takes "Not documented" or "Cannot confirm" while an update is pending (no control is drawn)
ANSWER_AFTER_UPDATE = 'You can answer this once the codes are updated.'
# 5.1: UPDATE_EXPORT_NOTE, by the update's state [R:truth-T4]: 'updating', and every other ('failed', 'stopped',
# 'paused', 'being_confirmed')
UPDATE_EXPORT_NOTE = {
    'updating': ('Your change is saved and the codes are being updated. Exports are available again once the update '
                 'finishes.'),
    'other': ('Your change is saved, but the codes have not been updated yet; the panel above says why. The codes from '
              'before your change cannot be exported as current.'),
}
UPDATE_EXPORT_NOTE_CHECK = {
    'updating': 'The codes are being updated. Exports are available again once the update finishes.',
    'other': ('The codes have not been updated yet; the panel above says why. The codes from before this update cannot '
              'be exported as current.'),
}
# 5.1 [R:truth-T5][R2:truth-RT8]: the results section and the review bar's tally while an update is pending
RESULTS_UPDATING = ('The updated codes appear here when the update finishes. The codes from before your change are shown '
                    'below.')
RESULTS_NOT_UPDATED = ('The codes have not been updated after your change yet; the panel above says why. The codes from '
                       'before your change are shown below.')
RESULTS_EARLIER_SHOWN = 'The codes from before your change are shown below.'
RESULTS_NO_EARLIER_CODE = 'No code was suggested before your change.'  # in place of RESULTS_EARLIER_SHOWN
TALLY_BEFORE = 'Before your change: '
TALLY_NO_EARLIER_CODE = 'Before your change: no code suggested'
RESULTS_UPDATING_CHECK = ('The updated codes appear here when the update finishes. The codes from before this update '
                          'are shown below.')
RESULTS_NOT_UPDATED_CHECK = ('The codes have not been updated yet; the panel above says why. The codes from before this '
                             'update are shown below.')
RESULTS_EARLIER_SHOWN_CHECK = 'The codes from before this update are shown below.'
# The three below have no check form in 7.1's rules (none says "from before your change"); worded by the rule that no
# check text names a change of the member's (recorded as a question)
RESULTS_NO_EARLIER_CODE_CHECK = 'No code was suggested before this update.'
TALLY_BEFORE_CHECK = 'Before this update: '
TALLY_NO_EARLIER_CODE_CHECK = 'Before this update: no code suggested'
# 2.5 [R:truth-T13]: the toast of a save that restored the earlier codes
RESTORED_TOAST = 'Saved. The codes from before your change are current again.'

# 5.3: the server-side refusals while an update is pending (internal = customer), and the readiness blocker
UPDATE_DECISION = ('These codes are from before your latest change and cannot be decided on. Decide on the codes once '
                   'they are updated.')
UPDATE_DECISION_CHECK = ('These codes are from before this update and cannot be decided on. Decide on the codes once '
                         'they are updated.')
UPDATE_EXPORT = ('These codes are from before your latest change and cannot be exported as current. Exports are '
                 'available again once the codes are updated; earlier downloads stay available, marked as earlier.')
UPDATE_EXPORT_CHECK = ('These codes are from before this update and cannot be exported as current. Exports are '
                       'available again once the codes are updated; earlier downloads stay available, marked as '
                       'earlier.')
UPDATE_ANSWER_WITHDRAW = 'You can change your answers once the codes are updated.'
UPDATE_BLOCKER = 'The codes are from before the latest change; the update has not finished'  # review.readiness's (5b)
# The blocker's customer words by the update's state and kind (customer_api.readiness, step 5d, chooses): while
# 'updating', and in every other state. BLOCKER_EXACT holds the check kind's 'other' form, the one true in every state
# and every kind: it never says "being updated" while nothing runs, nor names a change of the member's (A21).
UPDATE_BLOCKER_WORDS = {
    ('updating', 'details'): 'The codes are being updated after your change.',
    ('other', 'details'): 'The codes have not been updated after your change yet.',
    ('updating', 'check'): 'The codes are being updated.',
    ('other', 'check'): 'The codes have not been updated yet.',
}

# 1.4 (A12, A19): the save and addendum refusals; 3.9 (A13): the duplicate addendum (a KNOWN_TEMPLATES entry)
SAVE_TOO_LONG = ('This document is too long to be read in one piece, so its details cannot be changed here. The codes '
                 'shown stay as they are.')
SAVE_UNPREPARED = ('This document could not be prepared for reading, so its details cannot be changed here. The codes '
                   'shown stay as they are. Upload it again to change them.')
ADDENDUM_TOO_LONG = ('With this documentation the document would be too long to be read in one piece, so it was not '
                     'added.')
ADDENDUM_UNPREPARED = 'This documentation could not be prepared for reading, so it was not added.'
ADDENDUM_DOCUMENT_TOO_LONG = ('This document is too long to be read in one piece, so documentation cannot be added to it '
                              'here. Upload it again, shorter or split, with the documentation included.')
ADDENDUM_DOCUMENT_UNPREPARED = ('This document cannot be prepared for reading as it stands, so documentation cannot be '
                                'added to it here. Upload it again with the documentation included, without bracketed '
                                'markers such as [S2].')
ADDENDUM_DUPLICATE = 'This documentation was already added as revision {n}.'
RESTORE_REFUSED = ('The codes from before your change cannot be used again as they were, so their details cannot be '
                   'restored until the update has finished.')

# 7.2: retry_update's refusals (jobs.RETRY_BUSY and jobs.RETRY_UNKNOWN unchanged), and 7.1's action labels
RETRY_UPDATE_NOTHING = 'There is no failed update to try again.'
RETRY_UPDATE_HELD = ('Updating the codes is paused on this installation; resume once the coding service is available '
                     'again.')
RETRY_UPDATE_READING = 'This update failed while reading the document; use Try reading again.'
RETRY_UPDATE_REFUSED_BEFORE = 'The coding service refused this same request before, so it is not sent again.'
UPDATE_ACTION_LABELS = {'retry_reading': 'Try reading again', 'retry_update': 'Try updating again'}

# 7.1 [R2:truth-RT6][R3:truth-R3T-7]: a FIRST processing paused under the coding service's hold (progress.
# provider_paused, step 5b), while the hold stands; once released the stage reads STOPPED_BY_SYSTEM
PROVIDER_PAUSED = ('The coding service is paused on this installation, so this document\'s codes are not checked yet. '
                   'Nothing more is sent to it until it is available again; resume once it is.')


_WORKER_PAUSED = ('Processing is paused: the processing service is not responding right now. Your document is saved, '
                  'and this page shows the next step once the service is back.')  # progress.MESSAGES['paused']


@dataclass(frozen=True)
class UpdateText:
    """One row of amendment 7.1's table in its four forms (each a complete customer sentence): ``details`` for kind
    'details' with update.restorable; ``no_restore`` for kind 'details' without it; ``documentation`` for kind
    'documentation' (case C); ``check`` for kind 'check' (A21). ``phase`` and ``action`` are the row's; a 'resume'
    is offered only where review.can_resume holds (7.1: "resume when can_resume")."""
    details: str
    no_restore: str
    documentation: str
    check: str
    phase: str
    action: str


def _update_row(details, no_restore, documentation, check, phase, action) -> UpdateText:
    return UpdateText(details, no_restore, documentation, check, phase, action)


# 7.1's rows, by situation (progress.UPDATE_ERRORS' keys, step 5b, read these texts): the forms are written out, never
# computed, so each can be read and grepped; the test re-derives each form from ``details`` by 7.1's rules.
UPDATE_TEXTS = {
    'reading_failed': _update_row(
        'Your change is saved, but the codes could not be updated: reading the documented procedures could not be '
        'completed. The codes shown are from before your change and cannot be approved or exported until the update '
        'finishes.',
        'Your change is saved, but the codes could not be updated: reading the documented procedures could not be '
        'completed. The codes shown are from before your change and cannot be approved or exported until the update '
        'finishes.',
        'Your change is saved, but the codes could not be updated: reading the documented procedures could not be '
        'completed. The codes shown are from before the documentation was added and cannot be approved or exported '
        'until the update finishes.',
        'The codes could not be updated: reading the documented procedures could not be completed. The codes shown are '
        'from before this update and cannot be approved or exported until the update finishes.',
        'failed', 'retry_reading'),
    'appraisal_failed': _update_row(
        'Your change is saved, but the codes could not be updated: checking the reading against the document could not '
        'be completed. The codes shown are from before your change and cannot be approved or exported until the update '
        'finishes.',
        'Your change is saved, but the codes could not be updated: checking the reading against the document could not '
        'be completed. The codes shown are from before your change and cannot be approved or exported until the update '
        'finishes.',
        'Your change is saved, but the codes could not be updated: checking the reading against the document could not '
        'be completed. The codes shown are from before the documentation was added and cannot be approved or exported '
        'until the update finishes.',
        'The codes could not be updated: checking the reading against the document could not be completed. The codes '
        'shown are from before this update and cannot be approved or exported until the update finishes.',
        'failed', 'retry_reading'),
    'too_long': _update_row(
        'Your change is saved, but the codes could not be updated: this document is too long to be read in one piece. '
        'The codes shown are from before your change and cannot be approved or exported. Restore the earlier details '
        'to use them again, or shorten the document and upload it again.',
        'Your change is saved, but the codes could not be updated: this document is too long to be read in one piece. '
        'The codes shown are from before your change and cannot be approved or exported. Shorten the document and '
        'upload it again.',
        'Your change is saved, but the codes could not be updated: this document is too long to be read in one piece. '
        'The codes shown are from before the documentation was added and cannot be approved or exported. Upload the '
        'document again, shorter or split, to have it read.',
        'The codes could not be updated: this document is too long to be read in one piece. The codes shown are from '
        'before this update and cannot be approved or exported. Shorten the document and upload it again.',
        'failed', 'none'),
    'review_failed': _update_row(
        'Your change is saved, but the codes could not be updated: the coding service could not complete its review. '
        'The codes shown are from before your change and cannot be approved or exported until the update finishes.',
        'Your change is saved, but the codes could not be updated: the coding service could not complete its review. '
        'The codes shown are from before your change and cannot be approved or exported until the update finishes.',
        'Your change is saved, but the codes could not be updated: the coding service could not complete its review. '
        'The codes shown are from before the documentation was added and cannot be approved or exported until the '
        'update finishes.',
        'The codes could not be updated: the coding service could not complete its review. The codes shown are from '
        'before this update and cannot be approved or exported until the update finishes.',
        'failed', 'retry_update'),
    'review_not_sent': _update_row(
        'Your change is saved, but the codes could not be updated: the coding service could not be used just now, and '
        'the document was not sent to it. The codes shown are from before your change and cannot be approved or '
        'exported until the update finishes.',
        'Your change is saved, but the codes could not be updated: the coding service could not be used just now, and '
        'the document was not sent to it. The codes shown are from before your change and cannot be approved or '
        'exported until the update finishes.',
        'Your change is saved, but the codes could not be updated: the coding service could not be used just now, and '
        'the document was not sent to it. The codes shown are from before the documentation was added and cannot be '
        'approved or exported until the update finishes.',
        'The codes could not be updated: the coding service could not be used just now, and the document was not sent '
        'to it. The codes shown are from before this update and cannot be approved or exported until the update '
        'finishes.',
        'failed', 'retry_update'),
    'review_held': _update_row(
        'Your change is saved. Updating the codes is paused on this installation: the coding service refused its '
        'requests, and nothing more is sent to it until it is available again. The codes shown are from before your '
        'change and cannot be approved or exported until the update finishes. You can restore the earlier details to '
        'use them again.',
        'Your change is saved. Updating the codes is paused on this installation: the coding service refused its '
        'requests, and nothing more is sent to it until it is available again. The codes shown are from before your '
        'change and cannot be approved or exported until the update finishes.',
        'Your change is saved. Updating the codes is paused on this installation: the coding service refused its '
        'requests, and nothing more is sent to it until it is available again. The codes shown are from before the '
        'documentation was added and cannot be approved or exported until the update finishes.',
        'Updating the codes is paused on this installation: the coding service refused its requests, and nothing more '
        'is sent to it until it is available again. The codes shown are from before this update and cannot be approved '
        'or exported until the update finishes.',
        'paused', 'resume'),
    'review_refused_before': _update_row(
        'Your change is saved, but the codes could not be updated: the coding service refused this same request '
        'before, and it is not sent again. The codes shown are from before your change and cannot be approved or '
        'exported. Restore the earlier details to use them again.',
        'Your change is saved, but the codes could not be updated: the coding service refused this same request '
        'before, and it is not sent again. The codes shown are from before your change and cannot be approved or '
        'exported.',
        'Your change is saved, but the codes could not be updated: the coding service refused this same request '
        'before, and it is not sent again. The codes shown are from before the documentation was added and cannot be '
        'approved or exported.',
        'The codes could not be updated: the coding service refused this same request before, and it is not sent '
        'again. The codes shown are from before this update and cannot be approved or exported.',
        'failed', 'none'),
    'review_unbuilt': _update_row(
        'Your change is saved, but the codes could not be updated: the document could not be prepared for the coding '
        'service, and nothing was sent. The codes shown are from before your change. Restore the earlier details to '
        'use them again.',
        'Your change is saved, but the codes could not be updated: the document could not be prepared for the coding '
        'service, and nothing was sent. The codes shown are from before your change.',
        'Your change is saved, but the codes could not be updated: the document could not be prepared for the coding '
        'service, and nothing was sent. The codes shown are from before the documentation was added. Upload the '
        'document again, shorter or split, to have it read.',
        'The codes could not be updated: the document could not be prepared for the coding service, and nothing was '
        'sent. The codes shown are from before this update.',
        'failed', 'none'),
    'processing_failed': _update_row(
        'Your change is saved, but the codes could not be updated: processing could not be completed, and nothing was '
        'sent. The codes shown are from before your change and cannot be approved or exported until the update '
        'finishes.',
        'Your change is saved, but the codes could not be updated: processing could not be completed, and nothing was '
        'sent. The codes shown are from before your change and cannot be approved or exported until the update '
        'finishes.',
        'Your change is saved, but the codes could not be updated: processing could not be completed, and nothing was '
        'sent. The codes shown are from before the documentation was added and cannot be approved or exported until '
        'the update finishes.',
        'The codes could not be updated: processing could not be completed, and nothing was sent. The codes shown are '
        'from before this update and cannot be approved or exported until the update finishes.',
        'failed', 'retry_update'),
    'interpreter_paused': _update_row(
        'Your change is saved. Updating the codes is paused on this installation, and nothing was sent. The codes shown '
        'are from before your change and cannot be approved or exported until the update finishes. You can restore the '
        'earlier details to use them again.',
        'Your change is saved. Updating the codes is paused on this installation, and nothing was sent. The codes shown '
        'are from before your change and cannot be approved or exported until the update finishes.',
        'Your change is saved. Updating the codes is paused on this installation, and nothing was sent. The codes shown '
        'are from before the documentation was added and cannot be approved or exported until the update finishes.',
        'Updating the codes is paused on this installation, and nothing was sent. The codes shown are from before this '
        'update and cannot be approved or exported until the update finishes.',
        'paused', 'resume'),
    'review_disabled': _update_row(
        'Your change is saved. The coding service is not available on this installation right now, so the codes are '
        'not updated yet, and nothing was sent. The codes shown are from before your change. Resume once it is '
        'available, or restore the earlier details.',
        'Your change is saved. The coding service is not available on this installation right now, so the codes are '
        'not updated yet, and nothing was sent. The codes shown are from before your change. Resume once it is '
        'available.',
        'Your change is saved. The coding service is not available on this installation right now, so the codes are '
        'not updated yet, and nothing was sent. The codes shown are from before the documentation was added. Resume '
        'once it is available.',
        'The coding service is not available on this installation right now, so the codes are not updated yet, and '
        'nothing was sent. The codes shown are from before this update. Resume once it is available.',
        'paused', 'resume'),
    'being_confirmed': _update_row(
        'Your change is saved. We are confirming whether an earlier check completed; the codes are updated once that '
        'is settled, and nothing is sent again until then.',
        'Your change is saved. We are confirming whether an earlier check completed; the codes are updated once that '
        'is settled, and nothing is sent again until then.',
        'Your change is saved. We are confirming whether an earlier check completed; the codes are updated once that '
        'is settled, and nothing is sent again until then.',
        'We are confirming whether an earlier check completed; the codes are updated once that is settled, and nothing '
        'is sent again until then.',
        'being_confirmed', 'none'),
    'stopped_by_member': _update_row(
        'Updating the codes was stopped. The codes shown are from before your change and cannot be approved or '
        'exported until the update finishes. Resume to finish it, or restore the earlier details.',
        'Updating the codes was stopped. The codes shown are from before your change and cannot be approved or '
        'exported until the update finishes. Resume to finish it.',
        'Updating the codes was stopped. The codes shown are from before the documentation was added and cannot be '
        'approved or exported until the update finishes. Resume to finish it.',
        'Updating the codes was stopped. The codes shown are from before this update and cannot be approved or exported '
        'until the update finishes. Resume to finish it.',
        'stopped', 'resume'),
    'stopped_by_system': _update_row(
        'Updating the codes paused before it finished. The codes shown are from before your change. Resume to finish '
        'it.',
        'Updating the codes paused before it finished. The codes shown are from before your change. Resume to finish '
        'it.',
        'Updating the codes paused before it finished. The codes shown are from before the documentation was added. '
        'Resume to finish it.',
        'Updating the codes paused before it finished. The codes shown are from before this update. Resume to finish '
        'it.',
        'stopped', 'resume'),
    # 7.1's last row: the worker not responding reads progress.MESSAGES['paused'], unchanged, in every form - copied as
    # a literal (pinned equal by test), so this table reads no attribute of progress while modules are imported
    'worker_paused': _update_row(*(_WORKER_PAUSED,) * 4, 'paused', 'none'),
}
UPDATE_KINDS = ('details', 'documentation', 'check')


def update_text(situation, kind, restorable) -> str:
    """7.1's text of ``situation`` for an update of ``kind`` (update.kind) with ``restorable`` (update.restorable): the
    case-C form for 'documentation', the check form for 'check', else the restore form only when ``restorable`` is
    True. KeyError for a situation or kind 7.1 does not name: never a text of another row."""
    row = UPDATE_TEXTS[situation]
    if kind not in UPDATE_KINDS:
        raise KeyError(kind)
    if kind == 'documentation':
        return row.documentation
    if kind == 'check':
        return row.check
    return row.details if restorable is True else row.no_restore


# 6.2: "What changed", from stored rows (customer_api.what_changed, step 5d), in these words
WHAT_CHANGED_COMPARED = 'Compared with the codes as suggested on {time}, before any answer or decision'
WHAT_CHANGED_SINCE = 'since the codes as suggested on {time}'  # 6.2: after an answer's recompute (see the question)
WHAT_CHANGED_DETAIL_LABELS = {'service_date': 'Date of service', 'setting': 'Place of service',
                              'patient_status': 'Patient', 'billing_context': 'Claim'}  # 5.1's labels
WHAT_CHANGED_DETAIL = '{label}: {before} → {after}'  # step 2: the field's label with both values
WHAT_CHANGED_NOT_DOCUMENTED = 'not documented'
WHAT_CHANGED_TWO_DATES = 'two dates to choose from'
WHAT_CHANGED_DOCUMENTATION = 'Documentation added (revision {n})'
WHAT_CHANGED_READ_AGAIN = 'The document was read again with the current reading.'
WHAT_CHANGED_STATUS = {'ready': 'Ready for review', 'needs_detail': 'Needs a detail',
                       'excluded': 'Excluded by a documentation check',
                       'answered_away': 'Excluded: a needed detail is not documented'}
WHAT_CHANGED_ADDED = '{code} is now suggested ({status})'
WHAT_CHANGED_REMOVED = '{code} is no longer suggested'
WHAT_CHANGED_REMOVED_REASON = '{code} is no longer suggested. {reason}'  # with the other-codes list's reason
WHAT_CHANGED_ALTERNATIVE = 'Listed as an alternative only; not suggested for approval.'  # code_rows' own words
WHAT_CHANGED_NOT_SUGGESTED = 'Not suggested: {reason}'  # code_rows' own form, _exclusion_reason lower-cased
WHAT_CHANGED_STATUS_CHANGED = '{code}: {before} → {after}'
WHAT_CHANGED_UNITS = '{code}: {before} → {after} units'
WHAT_CHANGED_ITEM = '{code}: the detail needed changed: "{before}" → "{after}"'
WHAT_CHANGED_UNCHANGED = '{n} codes unchanged'
WHAT_CHANGED_UNCHANGED_ONE = '1 code unchanged'
WHAT_CHANGED_DECISION_NOUNS = {Decision.APPROVE: 'Approval', Decision.REJECT: 'Rejection',
                               Decision.REINSTATE: 'Reinstatement', Decision.CONFIRM: 'Confirmed exclusion'}
WHAT_CHANGED_KEPT = '{action} of {code} kept: the code is unchanged.'
WHAT_CHANGED_KEPT_THEN_CLEARED = ('{action} of {code} was kept by the update, then cleared when the codes were checked '
                                  'again with the same details.')
WHAT_CHANGED_KEPT_THEN_CHANGED = '{action} of {code} was kept by the update, then changed by a reviewer.'
WHAT_CHANGED_ANSWERS = ('Some answers you gave before this change are not applied to the updated codes; they are listed '
                        'under Earlier answers, not applied.')
# 5.4: why an earlier decision no longer applies (first match wins), and 6.2 step 4's 'cleared' outcome
CLEARED_BY_REVISION = 'Cleared when documentation was added (revision {n}).'
CLEARED_NEW_READING = ('Made on the earlier reading of the document; the current codes come from a new reading, so it '
                       'does not carry. Decide the current codes.')
CLEARED_SAME_DETAILS = 'Cleared when the codes were checked again with the same details: the code it was made on changed.'
CLEARED_DETAILS_CHANGED = 'Cleared when the details changed: the code it was made on changed.'
# 5.4: an earlier download, listed and linked (it downloads with the banner, step 5d)
EARLIER_DOWNLOAD = 'Earlier — made on revision {n}; it may not show the current codes'


# --- errors -------------------------------------------------------------------------------------------------------

# The customer's words for jobs.SECOND_REVIEW_NOT_FINAL (KNOWN_ERRORS): the peer chain is 'the independent checks', as
# in the confirmation's refusal below.
SECOND_REVIEW_NOT_FINAL_WORDS = ('The independent checks for this document have not finished: resume processing to '
                                 'finish them, then ask for a second review.')

# Refusals from deeper layers (jobs.Refused, ValidationError, PermissionDenied, AttestationRefused) that are already in
# CPT Studio's plain customer wording pass through; the rest are re-worded; anything this table does not know answers
# GENERIC_ERROR, so no stored or exception text ever reaches a customer.
KNOWN_ERRORS = {
    'Context can be set once the document text has been extracted.': None,
    'Wait for processing to finish (or stop it) before changing context.': None,
    'This document could not be read to the end, so its context cannot be changed and nothing is sent for it. '
    'Upload it again, shorter or split.': None,
    'Wait for processing to finish (or stop it) before resuming.': None,
    # the recorded retry of a reading (jobs.retry_reading; FINAL 11.3), already in the member's words
    jobs.RETRY_BUSY: None,
    jobs.RETRY_NOTHING: None,
    jobs.RETRY_READ: None,
    jobs.RETRY_UNKNOWN: None,
    jobs.RETRY_PAUSED: None,
    jobs.RETRY_TOO_LONG: None,
    jobs.RETRY_UNBUILT: None,
    # a write the legacy-call sentinel refused (FINAL 10.3): CPT Studio's sentence, naming no module or provider
    sentinel.MESSAGES['executed']: None,
    sentinel.MESSAGES['unavailable']: None,
    # a gated write refused because a reading finished between its request's read of the encounter and its row lock
    # (readers.moved; the Gemini migration's review, finding 3): retried by the member
    readers.MOVED: None,
    # a context save on a new-path revision whose reading ended without a result, or that was never read (S10's
    # hand-off; jobs.change_context): already in the member's words, naming no module or provider
    jobs.CONTEXT_UNREAD_MESSAGE: None,
    jobs.CONTEXT_NONE_MESSAGE: None,
    # a second review asked before its chain's final assessment (jobs._second_review_bounds): re-worded, as the
    # confirmation's refusal below is, because 'peer reviews' names the machinery
    jobs.SECOND_REVIEW_NOT_FINAL: SECOND_REVIEW_NOT_FINAL_WORDS,
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
    # FINAL-V2 amendment 1 (step 3c): the refusals while an update is pending (5.3; the check forms of A21), the save
    # and addendum refusals (1.4) and retry_update's own (7.2) - each already the member's words, naming no provider
    UPDATE_DECISION: None,
    UPDATE_DECISION_CHECK: None,
    UPDATE_EXPORT: None,
    UPDATE_EXPORT_CHECK: None,
    UPDATE_ANSWER_WITHDRAW: None,
    SAVE_TOO_LONG: None,
    SAVE_UNPREPARED: None,
    ADDENDUM_TOO_LONG: None,
    ADDENDUM_UNPREPARED: None,
    ADDENDUM_DOCUMENT_TOO_LONG: None,
    ADDENDUM_DOCUMENT_UNPREPARED: None,
    RESTORE_REFUSED: None,
    RETRY_UPDATE_NOTHING: None,
    RETRY_UPDATE_HELD: None,
    RETRY_UPDATE_READING: None,
    RETRY_UPDATE_REFUSED_BEFORE: None,
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
    # FINAL-V2 amendment 1, 3.9 (A13): ADDENDUM_DUPLICATE, its revision number filled in
    re.compile(r'This documentation was already added as revision [1-9][0-9]{0,5}\.'),
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
    review.DATE_CONFIRMATION_BLOCKER: 'Confirm the date of service under "A few details needed".',
    review.STALE_ANSWER_BLOCKER: 'A detail you withdrew or changed is still being applied: resume processing if it was stopped.',
    'The encounter context changed; re-assessment has not finished': 'The details changed; the results are being updated.',
    'The provider was not run': 'The coding service did not run for this document.',
    'The provider outcome is unknown': 'We are confirming whether an earlier check completed.',
    'Nothing was sent: the service date entered as encounter metadata conflicts with the document':
        'The service date you entered differs from the document; choose which date to use.',
    'The provider request failed': 'The coding service could not finish for this document.',
    'The provider response was not used': "The coding service's answer could not be used.",
    review.UNREADABLE_EVENTS_BLOCKER: 'This document must be checked again before its codes can be approved or exported.',
    # FINAL-V2 amendment 1, 5.3: UPDATE_BLOCKER in the form true in every update state and kind; customer_api.readiness
    # (step 5d) says it by the update's state and kind from UPDATE_BLOCKER_WORDS
    UPDATE_BLOCKER: UPDATE_BLOCKER_WORDS[('other', 'check')],
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
    or '' when it does not pass the guard: never its key, url or hash. A source with no title - one this release does
    not bundle, which the overlay names by no title (review_view._modifier_review) - or a title that is only its key is
    not shown at all (refutation round 2, L4-4: the key had reached the customer's modifier review)."""
    if not isinstance(source, dict):
        return ''
    title, release = str(source.get('title') or '').strip(), str(source.get('release') or '')
    if not title or title == str(source.get('key') or '').strip():
        return ''
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


def agent_approval(decision) -> bool:
    """Whether an approval is labelled "Agent-executed synthetic review - not clinical approval": exactly when its
    approver is an automated agent (CORE-UX-DESIGN.md 5 and 7, the directive's test approvals). ONE rule for every
    customer surface - the code's sub_label beside decision.by_kind, and the approved export's approver kind and agent
    line - so one approval carries one kind and one label everywhere (refutation round 2, L3-6: a person's approval of
    a code an agent had reinstated was labelled the agent's beside by_kind 'human'). Who reinstated a code stays in the
    record (Decision rows, the activity, the operator report), never in the label of somebody else's approval."""
    return decision is not None and decision.reviewer_kind == models.User.AGENT


def approved_export_items(assessment, current, views):
    """The approved export's items (review.approved_items: approved decisions only, never an unresolved or unapproved
    item, nor an approval the overlay no longer supports), in stored order, as the customer report prints them: code,
    units, the reviewer's chosen modifier, approver, approver kind, whether it is an agent's approval (agent_approval),
    decision time and id, the one-sentence summary and the exact passages the approval rests on (review.evidence_spans,
    with page and character offsets: the passages "Why this code?" shows)."""
    proposals = {str(proposal.pk): proposal for proposal in assessment.proposals.all()}
    items = []
    for item in review.approved_items(assessment):
        proposal = proposals[item['proposal_id']]
        decision = current[proposal.pk]
        items.append({
            'proposal_id': item['proposal_id'], 'decision_id': str(decision.pk), 'code': _code(item['code']),
            'units': item['units'], 'modifiers': list(item['modifiers']), 'approver': item['approved_by'],
            'approver_kind': item['approver_kind'], 'agent': agent_approval(decision),
            'decided_at': item['decided_at'], 'note': item['note'],
            'evidence': [{'text': span['text'], 'start': span['start'], 'end': span['end'], 'page': span.get('page')}
                         for span in item['evidence']],
            'summary': code_summary(proposal, views.get(proposal.key))})
    return items


# --- the codes -----------------------------------------------------------------------------------------------------

def _act_index(assessment):
    return review.act_index(assessment.services)


def _quotes(proposal, text, pages, acts, status):
    """ "Why this code?": the passages review.evidence_spans gives - the ONE rule the approved export's evidence is read
    by, so the page and the export never quote different passages (refutation round 2, L3-7 and L3-10): CPT Studio's
    own located passages for the matched act first, then the provider's exact passages the support records as showing
    it, and nothing where the support reading records no act as shown (an act denied or in doubt, no support reading)
    - never a passage that does not support - and none for an excluded code. Each re-checked against the text."""
    if status == 'excluded':
        return []
    return [{'text': span['text'], 'start': span['start'], 'end': span['end'], 'page': span['page'], 'exact': True}
            for span in review.evidence_spans(proposal, text, pages, acts)]


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
    # refutation round 1 of harness repair 3 (L4-6): a competition hold says what settles it
    'competing_codes': 'Another code is proposed for the same documented act: reject the one the documentation does '
                       'not support, and this one is then ready for review.',
    # completion repair (2026-11-06, U9/U10): what CPT Studio could not confirm - a reading's limit, never a statement
    # that the document leaves it out, which only a passage makes (its question shows the passages it concerns)
    'performed_status': 'CPT Studio could not confirm from the document that this was done on the date of service.',
    'extent': 'CPT Studio could not confirm how far the examination reached.',
    'completion': 'CPT Studio could not confirm whether the examination was completed.',
    'separate_em': 'CPT Studio could not confirm a separately identifiable office visit beside the procedure.',
    'em_basis': 'CPT Studio could not confirm the basis for the visit level.',
    'setting': 'CPT Studio could not confirm the place of service.',
    'patient_status': 'CPT Studio could not confirm whether the patient is new or established.',
    'target': 'CPT Studio could not confirm the structure examined.',
    'cannulation': 'CPT Studio could not confirm whether cannulation was achieved.',
}
# why approve is withheld from a code (review_view.View.withheld_by, same_day_held); a reinstated code its gate withholds
# reads "Needs a detail" with the row that asks it (the overlay asks its waits: refutation round 2, L3-8)
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
        same_day = view is not None and view.same_day_held
        for question in questions:
            fact = question.get('fact') if isinstance(question, dict) else ''
            if fact == 'base_included':
                out.append(f'{code} may be included in another code reported for this examination; a detail is '
                           'needed before it can be approved.' if code else
                           'This code may be included in another code reported for this examination.')
            elif fact == 'separate_em' and same_day:
                # the visit a reinstated same-day procedure holds (refutation round 3, B-05): the gate's own sentence
                out.append(WITHHELD_WORDS[review.SAME_DAY_EM_GATE])
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
        return 'approved', AGENT_SUB_LABEL if agent_approval(decision) else ''
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
        # a code the engine excluded by a member's answer stays where the selected code it was is listed (completion
        # repair 2026-11-06, U11): excluded, "A needed detail is not documented", withdrawable by the answer's row
        if (proposal.bucket == Proposal.SELECTED or questions.answered_away(proposal)
                or (proposal.bucket == Proposal.EXCLUDED and decision is not None
                    and decision.action != Decision.CONFIRM)):
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
    # Harness repair 2026-11-05: a code the numbered list already suggests is never listed again as "not suggested" (the
    # bounded second review's own selection of a code a primary proposal carries, an admitted participant's copy of a
    # code CPT Studio excluded for its evidence): the operator console keeps every row
    other_codes, listed = [], {row['code'] for row in rows if row['code']}
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
    """What the reconciliation leaves unresolved, in fixed sentences. An unresolved item is a documented service (or
    act) performed today that no supported code accounts for (reconcile.Unresolved: no_proposal, not_covered,
    unsupported, coverage_unknown) - an office visit included, which is then documented, never "not documented"; only a
    visit the reading leaves uncertain is one that is mentioned but not established."""
    out = []
    for item in completeness.get('unresolved_items') or []:
        if not isinstance(item, dict):
            continue
        family = item.get('family')
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
    events = assessment is not None and readers.for_assessment(assessment).kind == readers.EVENTS
    if events:
        out[-1] = EVENTS_READING  # the new path's reading, in place of the wording checks' (FINAL 8.3)
    if assessment is not None:
        if any(retrieval_failed(entry) for entry in assessment.retrieval or []):
            out.append(REFERENCE_FAILED)
        elif not source_applied(assessment.reference_sources):
            out.append(NO_REFERENCE_FILE)
        interpreted = (assessment.event_inventory.provider_run if events and assessment.event_inventory_id
                       else None)
        if any(run is not None and review.run_mode(run) == 'replay'
               for run in (assessment.provider_run, interpreted)):
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
    """The encounter's customer exports, newest first, each ``current`` while it still matches the saved decisions
    (reports.customer_marker_digest: the same comparison the download answers 409 by)."""
    from .reports import customer_marker_digest  # local import: reports reads this module
    artifacts = list(encounter.reports.filter(audience=ReportArtifact.CUSTOMER).select_related('generated_by')
                     .order_by('-generated_at', '-pk'))
    marker = customer_marker_digest(encounter) if artifacts else None
    return [report_json(artifact, marker is not None and artifact.snapshot_sha256 == marker) for artifact in artifacts]


RECHECK_NOT_COMPLETED = ('check_not_completed', 'The check of what is still open could not be completed')
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


# A re-check's outcome known not to have completed when its request ended: it failed, or it was not sent. An outcome
# still unknown is never one (refutation round 3, C-R3-2): it is being confirmed and may have been answered
# (progress.JOB_STEP_STATES, MESSAGES['being_confirmed']), and is said once a reconciliation settles it.
RECHECK_ENDED = (ProviderRun.FAILED, ProviderRun.NOT_SENT)
_RUN_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def _reconciled_rechecks(encounter, events):
    """The ids of this document's re-check runs (purpose second_review) whose unknown outcome a reconciliation settled,
    among the runs ``events``' provider.reconciled rows name: the re-check then did not complete, whichever path left its
    outcome unknown - a read that timed out after sending, a worker that died mid-send (jobs.mark_stale) or an outcome
    that could not be recorded (jobs._settle_unrecorded), the last two with no provider.finished row (refutation round 3,
    C-R3-3)."""
    named = set()
    for event in events:
        run = event.data.get('run') if isinstance(event.data, dict) else None
        if event.event == 'provider.reconciled' and isinstance(run, str) and _RUN_ID.fullmatch(run):
            named.add(run)
    if not named:
        return set()
    return {str(pk) for pk in encounter.provider_runs.filter(
        pk__in=named, purpose=ProviderRun.SECOND_REVIEW, state=ProviderRun.UNKNOWN,
        reconciled_at__isnull=False).values_list('pk', flat=True)}


def activity(encounter):
    out = []
    events = list(encounter.audit_events.select_related('actor').order_by('created_at', 'pk'))
    reconciled = _reconciled_rechecks(encounter, events)
    for event in events:
        data = event.data if isinstance(event.data, dict) else {}
        entry = ACTIVITY.get(event.event)
        actor = event.actor
        kind = event.actor_kind if event.actor_kind in ('human', 'agent') else 'system'
        if (event.event == 'provider.finished' and data.get('purpose') == ProviderRun.SECOND_REVIEW
                and data.get('state') in RECHECK_ENDED):
            entry = RECHECK_NOT_COMPLETED  # the re-check's own outcome, said once it is known (refutation round 2, L5-5)
        elif event.event == 'provider.reconciled' and data.get('run') in reconciled:
            # an unknown outcome settled (refutation round 3, C-R3-3), said as CPT Studio's: a reconciliation is the
            # platform operator's work, and who did it is the operator's record, never the practice's activity
            entry, actor, kind = RECHECK_NOT_COMPLETED, None, 'system'
        if entry is None:
            continue
        if event.event == 'report.generated' and data.get('audience', ReportArtifact.CUSTOMER) != ReportArtifact.CUSTOMER:
            continue  # an operator's report is the operator's record, never the practice's activity
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


def in_queue(encounter, state=None):
    """Whether the customer's review queue lists ``encounter`` - and the session counts it: one predicate for both
    (session decision (o), 2026-11-04), so the badge never counts a document the queue does not list. A customer state
    that waits on the member (QUEUE_STATES: a date to choose, details to answer, codes to review), or what the review
    queue's own rule holds waiting (serializers.queue_reasons, refutations gi2 RC6 and ec5: an open question or a code
    to decide, an unknown outcome being confirmed, coding left incomplete, a re-check that can be asked for, a state that
    always waited). ``state``: the customer state already read for this encounter."""
    from .serializers import QUEUE_STATES as WAITING_STATES, queue_reasons  # the review queue's own rule
    # the same three-way OR, cheapest first: the customer state is read last, and only when no state was given (the
    # session's count read it first for every encounter, and took 2.4 times the installed count's time on the live data)
    if (state is not None and state in QUEUE_STATES) or encounter.state in WAITING_STATES or queue_reasons(encounter):
        return True
    return state is None and customer_state(encounter) in QUEUE_STATES


def session_json(user, membership):
    """GET /api/session. ``counts.queue`` counts the documents the review queue lists (in_queue, the predicate each list
    row carries as ``in_queue``)."""
    from .serializers import _initials
    workspace = membership.workspace
    encounters = list(workspace.encounters.select_related('current_revision', 'current_context',
                                                          'current_assessment'))
    # R-6: each encounter's row read under its own label (readers.labelled), as the list's rows are
    queued = sum(1 for encounter in encounters if readers.labelled(in_queue, encounter))
    return {'user': {'id': str(user.pk), 'label': user.label(), 'initials': _initials(user),
                     'actor_kind': user.actor_kind},
            'workspace': {'id': str(workspace.pk), 'name': workspace.name},
            'role': membership.role, 'can_review': membership.can_review,
            'acknowledgement': review.ACKNOWLEDGEMENTS.get(user.actor_kind, ''),
            'counts': {'documents': len(encounters), 'queue': queued},
            'synthetic_only': settings.SYNTHETIC_ONLY}


def list_row(encounter):
    """One row of GET /api/encounters: its state, the date of service in use and whether a member's date conflicts with
    the document's (answers.service_date_block), the details still unanswered (the rows the document page shows
    without a saved answer), and whether the review queue lists it (in_queue, which the session's count counts)."""
    assessment = review.live_assessment(encounter)
    state = customer_state(encounter, assessment)
    date = answers.service_date_block(encounter)
    revision = encounter.current_revision
    rows = answers.details_needed(encounter, assessment, views_of(assessment) if assessment is not None else None)
    return {'id': str(encounter.pk), 'title': encounter.title, 'state': state, 'state_label': STATE_LABELS[state],
            'service_date': date['value'], 'date_conflict': date['conflict'],
            'open_details': sum(1 for row in rows if row['saved'] is None), 'created_at': _iso(encounter.created_at),
            'kind': revision.kind if revision is not None and revision.kind in ('upload', 'paste', 'addendum')
            else 'upload', 'in_queue': in_queue(encounter, state)}


def recheck_block(encounter, membership):
    """The bounded re-check of what is still open - the one second review of the current assessment (ARCHITECTURE 5.11)
    that the installed page offered as an ask - kept on the customer page by function (session decision (n),
    2026-11-04): ``available`` when one can be asked for now (jobs.second_review_status: a documented service left
    without a supported code and no bound standing - the predicate POST second-review accepts an ask by), ``can_request``
    when this member may also ask (owners and reviewers). Never queued by an assessment (owner decision 2026-10-27)."""
    from . import jobs  # local import: the job layer is not this module's reader
    available = bool(jobs.second_review_status(encounter)['available'])
    return {'available': available, 'can_request': available and bool(membership.can_review)}


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
        # the documented services the reader of the assessment's engine gives (FINAL 8.3): the stored services record,
        # or the sessions of the new path's event coding
        services = readers.for_assessment(assessment).services_list(assessment)
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
        'earlier_answers': answers.earlier_answers(encounter, assessment),
        'unresolved': _unresolved(completeness, services),
        'recheck': recheck_block(encounter, membership),
        'limitations': limitations(assessment, revision),
        'readiness': readiness(encounter, assessment, current),
        'reports': _reports(encounter),
        'activity': activity(encounter),
    }
