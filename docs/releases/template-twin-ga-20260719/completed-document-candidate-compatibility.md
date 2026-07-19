# Completed Document → Template Candidate v1

Status: **TECHNICAL SLICE — SYNTHETIC REVIEW ONLY**

Converter: `completed-document-candidate/1.1.0`

Runtime selector: exact value `TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE=synthetic-review-v1`

This is a separate workflow from native blank/fillable DOCX intake. A populated
report is treated as an example, never as an active template. The uploaded
examples are not overwritten, admitted as template sources, rendered, or sent
to an AI/provider. The output is a new blank candidate DOCX that must be
downloaded and re-enter the ordinary native DOCX certification gates.

## Admission and isolation contract

The service performs these operations in order for each example:

1. Write the exact raw bytes to the private, versioned quarantine namespace and
   record the immutable object ledger intent/identity.
2. Obtain a real local ClamAV attestation over a Unix-domain socket.
3. Minimize identifying DOCX core/app/custom metadata locally.
4. Run the package safety boundary and deterministic structural comparison.
5. Generate a distinct immutable `candidate` object only after every example
   passes.
6. Atomically bind two or three `ISOLATED` quarantine rows, the new candidate,
   the complete region inventory, and the audit outbox event in one tenant.

The local privacy evidence is hash-bound and records `providerEgress: false`.
Source values are not returned by the review API or rendered in the physician
workspace. Each region exposes only a stable label, structural location,
candidate binding, evidence class, and SHA-256 evidence digest.

## Supported compatibility matrix

| Input property       | v1 behavior                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Number of examples   | Exactly 2 or 3                                                                                                                                               |
| Data class           | Purpose-built synthetic documents only; exact QuillMD synthetic sentinel required                                                                            |
| File format          | Macro-free `.docx`, maximum 10 MB each                                                                                                                       |
| Package relationship | All examples must have identical safe OOXML part and relationship structure                                                                                  |
| Document layout      | Identical `word/document.xml` block and table shape across examples                                                                                          |
| Candidate region     | A changed, non-empty plain-text scalar value cell immediately to the right of one unchanged, unique, safe label                                              |
| Static content       | Preserved from the first minimized example only after all examples prove identical structure                                                                 |
| Candidate binding    | New deterministic Word text content control with stable `qmd:candidate:*` tag and ID                                                                         |
| Review projection    | Value-redacted table topology only; source and candidate panes are rendered from the same immutable projection, and pagination is explicitly not represented |
| Review               | Every region visible and decided exactly once after opening the protected comparison; bulk approval is reversible until save                                 |
| Approval result      | Download of the new blank candidate only; no activation or source admission                                                                                  |
| Rejection result     | Terminal; no candidate download, certification, or activation                                                                                                |

## Unsupported and fail-closed matrix

| Input or requested inference                                                                                                                                | Result                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| One example, more than three examples, or a non-synthetic example                                                                                           | Reject                                                                                                        |
| Real patient, physician, practice, or other identifying document                                                                                            | Prohibited in this mode; reject on deterministic identifier evidence, with human policy gate still required   |
| Existing content controls or supported placeholders                                                                                                         | Reject and route to native blank/fillable DOCX intake                                                         |
| Narrative paragraph changes                                                                                                                                 | Reject; ordinary narrative is never assumed fillable                                                          |
| Changed row/cell count, repeating-row inference, or layout differences                                                                                      | Reject                                                                                                        |
| Duplicate or ambiguous labels                                                                                                                               | Reject                                                                                                        |
| Headers, footers, comments, footnotes, endnotes, media, embedded fonts, charts, drawings, or other auxiliary parts                                          | Reject in v1                                                                                                  |
| Dropdown, checkbox, date, measurement, polarity, laterality, medication, allergy, or option-set inference from completed values                             | Reject; v1 generates text controls only                                                                       |
| Macros, OLE, ActiveX, scripts, external relationships, unsafe fields, traversal, malformed XML, hidden content, decompression attacks, or unsupported parts | Reject through the existing package boundary                                                                  |
| Different Word versions that normalize the same visible layout to different OOXML                                                                           | Reject unless the OOXML structure is identical                                                                |
| Preview receipt in a different browser tab, after refresh, after 15 minutes, or after one use                                                               | Reject; reopen and review the exact comparison again                                                          |
| Source values, source DOCX bytes, hidden preview fields, or pagination inferred from the projection                                                         | Never returned by the preview API                                                                             |
| Candidate activation                                                                                                                                        | Impossible by schema and service design; candidate is neither `NoteTemplate` nor `TemplateTwinSourceArtifact` |

No claim is made that every DOCX, every completed report, or every clinically
meaningful region is supported.

## Physician review contract

- The initial candidate response contains the bounded field inventory and
  evidence summaries, but not the structural projection or a review proof.
- Opening the protected comparison rechecks global and practice rollout under
  locks, validates the persisted projection as untrusted input, writes an audit
  event, and returns a 15-minute single-use receipt. Only its SHA-256 digest is
  stored. The opaque receipt stays in a React ref and is never placed in the
  DOM, browser storage, URL, audit metadata, or logs.
- The workspace shows synchronized source/candidate tables from one immutable
  projection. Source values are always `VALUE_WITHHELD`; generated regions are
  always `BLANK_CONTROL`. Static cells expose structure, never text.
- The full region inventory is visible in one rail. The inspector exposes the
  deterministic evidence class and exact candidate binding.
- A physician must approve or reject every region and make an explicit terminal
  attestation.
- Refresh, expiry, rollout-generation change, receipt replay, candidate/hash
  mismatch, or projection tamper clears all local decisions and attestation and
  requires the physician to reopen the exact comparison.
- Any rejection rejects the whole candidate. An approval requires all regions
  approved.
- Approved output copy explicitly instructs the physician to inspect the file
  in Word and submit it through blank/fillable certification. It does not imply
  clinical mapping, Office compatibility, or production activation approval.

## UI reference lock

The implementation follows the accepted Template Twin certification workspace
and Linear V1 settings surfaces: dark canvas, compact sans-serif hierarchy,
monospace evidence, flat divided regions, split inventory/inspector, sage only
for confirmed safe actions, and amber/red for pending or rejecting states. The
source-side reference is structural evidence; the generated candidate is always
presented as a new document, never as the uploaded source. Live status regions,
44-pixel actions, focus-visible outlines, terminal-state copy, and a responsive
single-column layout are included.

## Human and production gates

The following remain **HUMAN PENDING** and this exact synthetic selector must
remain off in production until they are satisfied:

- Privacy/Legal authorization for any real completed document or PHI.
- Clinical Safety approval of the supported inference boundary and physician
  language.
- Returned desktop Microsoft Word evidence for the generated corpus.
- Operations approval for retention, legal hold, deletion, monitoring,
  backup/restore, and incident ownership of isolated examples and candidates.

The synthetic slice does not waive native certification, verification-contract
v2, signing, provider, audit, tenant, storage, rollout, or kill-switch gates.

## Immutable projection and receipt boundary

The review projection is canonically hash-bound to the converter version, exact
source-example hashes in ordinal order, shared source structure hash, candidate
DOCX byte hash, compiled candidate structure hash, inventory hash, contiguous
block/table/row/cell identities, unique candidate tags, and the exact relational
region/label/location set. Candidate creation recompiles the generated DOCX and
requires one safe content control per region before storage. Application schema
validation, service validation, database constraints, deferred projection
triggers, immutable receipt triggers, and terminal review triggers are
independent fail-closed layers.

Rows created by converter `completed-document-candidate/1.0.0` remain only as
immutable historical evidence after the additive migration. They cannot open a
protected preview, receive a new decision, or return candidate bytes, even if a
pre-migration row already says `APPROVED`. Download requires converter 1.1, a
canonical projection that matches the relational inventory and the downloaded
DOCX bytes, and the exact consumed terminal receipt. There is no in-place
upgrade: an owner must create a new candidate from permitted synthetic examples.

Terminal review uses serializable transactions and the lock order global
rollout → practice rollout → candidate → receipt. The receipt is tied to the
same physician, practice, candidate hashes, projection hash, converter version,
and both rollout generations. Consumption, every region decision, the candidate
terminal state, review timestamp, receipt identifier, and audit-outbox event
commit atomically. An expired, consumed, mismatched, or unconsumed receipt
cannot support a terminal database state.

## Safe rollback

Remove the exact runtime selector (or set it to any value other than
`synthetic-review-v1`) and redeploy the previously accepted immutable image.
The settings entry, pages, and APIs then return no workflow surface. Do not drop
the additive tables or delete quarantine/candidate objects during incident
rollback; retain them under the approved storage schedule so audit and lineage
remain reproducible. Object reconciliation continues to handle unclaimed
candidate writes through the existing retention contract.
