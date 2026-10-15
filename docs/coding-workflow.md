# Outpatient coding workflow

This release prepares coding for saved US outpatient/office encounters, including
GI. It retains the application's synthetic-only restriction. It does not submit
claims or change the finalized clinical document or original Word export.

## Confirmed original failure

The finalized synthetic Kasra_5 encounter on 14 October 2026 had no coding job,
coding audit, or suggestions. The old action was hidden after finalization and
the old implementation only recognized literal code tokens. The FY2027 code
dictionary was present, but no Index-to-Tabular concept-resolution workflow
existed. An absent CPT agreement was a separate limitation, not the cause of the
missing ICD request. The original note and Word bytes were retained before work.

## Clinician workflow

An eligible saved revision queues coding once. Existing finalized notes expose
an explicit action. Saving changed coding context also queues its new review.
The Coding tab polls read-only status and updates without a page refresh; it
preserves unsaved edits when a newer result arrives.

Rows show the authoritative description, exact supporting documentation and
applicable instructions. A clinician can exclude a row or select a supported
replacement with a reason. Saving choices does not approve them. One explicit
approval records all displayed selections, including exclusions. Existing
clinical approval never approves newly prepared codes.

The review summary separately counts approved selections, suggestions awaiting
review and unresolved questions for the exact saved revision. An approved
decision supplies both its included and excluded rows; exclusions are reviewed,
not pending. Approval does not resolve questions or mark the entire coding task
complete. Earlier approvals are labeled as history and never count toward a
changed revision.

Every run binds the note, saved answers, revision, patient identity, service date,
setting, other coding context, and exact terminology release/digest. A changed
input makes the previous review stale. Decisions and finished execution evidence
are append-only; earlier records remain visible as history. An explicit synthetic
identity-reuse reason affects only the coding context, not the clinical record.

## Terminology and execution

The provider extracts source concepts, then selects only candidates retrieved
from the official service-date Index and verified against the Tabular List and
complete reportable-code dictionary. Source checks preserve negation, uncertainty,
subject, temporality, laterality and documented specificity. Unresolved conditions
hold the affected recommendation with a question. Historical releases remain
available. See [the reference guide](coding-reference-guide.md).

CPT is independently gated by applicable rights and dated licensed content and
criteria. Its absence does not block ICD review or ordinary export. Office E/M
requires the setting, patient status and a qualifying documented basis; minutes
alone are insufficient. See [CPT integration](coding-cpt-integration.md) and the
[prepared licensing handoff](coding-cpt-licensing-handoff.md).

The new coding purpose reuses the configured provider and shared send lock.
Each run permits at most one concept call and one resolution call, with SDK
retries disabled. Requests, raw responses, provider identities, token usage,
configured rates and known costs are retained. A possibly charged unknown
outcome remains unknown and is not automatically resent. No wallet charge is
created by this synthetic coding purpose.

Concept requests carry the exact saved, displayed answer text and its clinical
status and units, rather than repeated internal generation proofs for every
field. The complete original answers remain in the immutable input snapshot.
The request byte limit still applies without truncating clinical text. This
projection has a new engine version, so an earlier failed review is retained
and an existing finalized encounter can explicitly request the current version.

One actual concept response contained blank identifiers and source evidence.
The complete saved note reached the provider; local validation rejected the
response and retained its receipt and known cost. The provider SDK moves some
string constraints into schema descriptions, so transport validation alone
does not establish a usable clinical response. Concept fields now carry explicit
source and nonblank requirements, with local whitespace rejection that preserves
accepted strings exactly. Empty concept lists remain valid when no concepts are
supported; placeholder objects are invalid.

This correction has a distinct engine contract. A finalized encounter requires
an explicit request for that contract, and repeated requests reuse its one run.
Previous terminal failures, provider receipts and costs are preserved. There is
no automatic resend of a failed request. These checks do not guarantee that a
future provider response will pass clinical validation; served acceptance must
verify the actual response separately.

The UI distinguishes unrequested work, unavailable terminology, pending work,
insufficient detail, a supported empty result, execution failure and an uncertain
provider outcome. GET requests do not enqueue jobs or record approvals.

## Installation and verification

`rebuild/ops/activate_outpatient_coding.py` is inert by default. Its declared
operation requires an exact candidate citation, a fresh backup and isolated
restore, measured additive schema, three pinned official references, a static
asset union, current foreign-service observations and original-history proofs.
Installation changes four coding tables, one function and three triggers, adds
one migration record and three reference-import audits, and preserves existing
clinical rows and public assets. A prepared operator is not an installation
receipt; normal HTTPS clinician acceptance and actual usage readback are separate
evidence after installation.
