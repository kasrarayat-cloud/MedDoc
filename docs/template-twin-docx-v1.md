# Template Twin — Structure-Preserving DOCX v1

## Status and safety invariant

**Repository status:** safe-alpha hardening is in progress on
`fix/template-twin-audit-gates-v1`, based on the preserved seven-commit
`feat/template-twin-docx-v1` prototype. It is not deployed. This document is
an architecture and release-gate handoff, not deployment approval or evidence
that the feature is ready for real PHI.

Template Twin is **default off at two independent server-side gates**:

- `TEMPLATE_TWIN_KILL_SWITCH` must be set to the exact value `false`; an
  absent, malformed, or truthy value keeps the feature off globally.
- `Practice.templateTwinEnabled` must be `true`; the database default is
  `false`.

Upload, compilation/certification, management, active-template selection,
generation, review, signing, and original-template export all enforce this
rollout decision on the server. Hiding the UI is not an authorization control.

Template Twin adds an exact-source Word delivery alongside the existing SOAP, coding, PDF, generic DOCX, email, and clipboard flows. It does not replace those flows.

The clinical invariant is:

> A clinical value may be rendered into the physician's DOCX only when the
> current versioned extractor can produce its certified concept, it resolves
> from retained encounter evidence or an explicitly approved practice default,
> passes independent validation, and survives output-derived exact-binding
> readback. An unresolved clinically meaningful field blocks signing. A value
> must never be manufactured from a blank, an unknown checkbox, or the nearest
> dropdown option.

No production migration, bucket provisioning, service restart, or deployment
was performed as part of this branch. Local non-production app, worker, and
migration images were built and exercised only in the disposable `meddoc-qa`
Compose project; that stack and its volumes were removed after validation.

## Architecture and data flow

```mermaid
flowchart TD
    A[Physician uploads named, scoped blank DOCX] --> R0[Global and practice rollout gates]
    R0 --> B[Bounded multipart and deterministic package/security compiler]
    B -->|rejected| Q[Metadata-only quarantine record]
    B -->|accepted| C[TemplateDocIR + exact renderer bindings + unsupported register]
    C --> D[Fail-closed template PHI gate]
    D -->|rejected| Q
    D -->|accepted| F[ModelClient semantic mapping proposal or unconfirmed fallback]
    F --> F2[Versioned supported-concept registry]
    F2 -->|unsupported concept| Q2[Certification blocker]
    F2 --> E[Immutable tenant-scoped source object and draft transaction]
    E --> G[Physician mapping review]
    G --> H[Field-level synthetic evidence test or allowed waiver]
    H --> I[Exact DOCX render and round-trip verification]
    I --> J[Explicit certification and activation]

    K[Voice conversation] --> L[Existing Layer 3 evidence entities]
    M[Voice dictation] --> L
    N[Typed encounter text] --> L
    L --> O[Canonical encounter facts]
    J --> P[Certified immutable template version]
    O --> R[Deterministic field resolver]
    P --> R
    R --> S[Independent clinical/document validator]
    S -->|blocking issue| T[Needs-review manifest; no output]
    S -->|valid| U[Clone source and patch approved bindings only]
    U --> V[Reopen, reparse, verify fields and static regions]
    V --> V2[Independent output readback from completed DOCX]
    V2 --> W[Immutable output object + SOAP-bound fill manifest]
    W --> X[Visit review with evidence]
    X --> Y[Atomic server-side sign gate + stored-byte stream hash]
    Y --> Z[Original Template DOCX delivery]
```

The implementation is divided into these boundaries:

| Boundary                       | Primary code                                                                                       | Responsibility                                                                                                                                  |
| ------------------------------ | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Untrusted DOCX                 | `apps/transcribe-md/src/lib/note-template-docx/`                                                   | ZIP/OPC/XML validation, deterministic compilation, exact rendering, independent output readback, and static-region proof                        |
| Shared contracts               | `apps/transcribe-md/src/lib/template-twin/ir.ts`                                                   | Provider-neutral IR, facts, mappings, resolutions, validation, and manifest schemas                                                             |
| Safe-alpha extraction boundary | `supported-concepts.ts`, `encounter-facts/`                                                        | Versioned exact concept allowlist and the extension interface for a later Template-Aware Extraction Agent                                       |
| Artifact custody               | `apps/transcribe-md/src/lib/template-twin/storage/`                                                | Tenant-scoped keys, immutable-style writes, readiness evidence, bounded stream reads, byte/hash verification, and durable object-write ledger   |
| Draft and certification        | `create-draft.ts`, `certification-lifecycle.ts`, `synthetic-test.ts`                               | Persist draft, propose/approve mappings, synthetic proof, certify, and activate                                                                 |
| Encounter filling              | `encounter-facts/`, `resolver/`, `validation/`, `fill-engine.ts`                                   | One voice/text fact path, exact field resolution, validation, rendering, and manifest persistence                                               |
| Review and signing             | `components/visit/template-twin-review*`, `review-service.ts`, `signing-gate.ts`, visit sign route | Minimal review DTO, labeled physician corrections, explicit mapping-version forks, server-side signing enforcement, and immutable sign decision |
| Delivery                       | `export/original-template-docx/route.ts`                                                           | Authenticated read of the already-rendered, hash-verified output; never regenerates at download time                                            |
| Durable safety evidence        | `audit-outbox.ts`, `worker/cleanup/template-twin-maintenance.ts`                                   | Transactional audit intent, retrying audit delivery, object-ledger reconciliation, and fail-closed maintenance configuration                    |

Version constants in v1 are:

- IR schema: `2`
- compiler: `template-docx-compiler/1.2.0`
- resolver: `template-field-resolver/1.0.0`
- renderer: `template-docx-renderer/1.2.0`
- validator: `template-field-validator/1.0.0`
- strict binding/readback: `template-docx-certified-binding/2.0.0` and
  `template-docx-readback/2.0.0`
- QA-only Office round-trip: `template-twin-office-roundtrip-qa/2.1.0`

The 1.2 renderer accepts a persisted compiler-1.1 IR only when a fresh
independent compile produces identical structure/static hashes and identical
parts, fields, and tables. A source that newly qualifies for a 1.2 structural
profile therefore fails closed and requires a new immutable certified version.

## Immutable artifacts and tenant boundary

The source DOCX is stored before database activation under an opaque key shaped like:

```text
practices/<practice-id>/template-twin/sources/<lineage-id>/v<version>/<opaque-id>/<sha256>.docx
```

Rendered outputs use:

```text
practices/<practice-id>/template-twin/outputs/<visit-id>/<manifest-sha256>/<opaque-id>/<output-sha256>.docx
```

The application:

- never uses a user filename as an object key;
- validates the key grammar and practice prefix before every read;
- verifies provider metadata, byte length, and SHA-256 before accepting a source or output;
- reads with a hard size ceiling and hashes the stream as it is consumed;
- has no request-path Template Twin delete or overwrite method; only the
  separately gated maintenance worker can purge an unclaimed ledger object;
- stores source and output object keys only in server-side database rows;
- never sends object keys, hashes, or storage credentials to the browser review DTO;
- does not log document bytes, extracted document text, transcript text, field values, or evidence quotes in operational/audit metadata.

Every source/output write first creates a durable object-ledger intent. The
ledger records the tenant, key, digest, byte count, kind, write/claim state,
retry state, and retention boundary. The owning database transaction claims
the object only after the related source artifact or fill manifest is ready.
If the process crashes or loses a database race between object PUT and claim,
the maintenance worker reconciles the ledger idempotently. An expired
unclaimed object becomes `RETAINED` unless Operations separately enables the
exact `TEMPLATE_TWIN_ORPHAN_PURGE_APPROVED=true` boundary; maintenance alone
does not authorize deletion.

Database triggers make source-artifact rows and certification rows append-only. Certified compiler/field/mapping rows cannot be changed or deleted. Once `signedDecisionAt` is set, the fill-manifest row cannot be changed or deleted. Additional constraint triggers reject a compiled source joined to a `NoteTemplate` owner from another practice, later owner-practice reassignment, cross-practice fill lineage, output keys outside the owning visit/tenant prefix, review decisions linked to fields from another compiled version, and inconsistent waiver lineage. Compiled, template-owner, and owner-practice mutations share a transaction-scoped database lock so concurrent writes cannot each validate stale cross-table state. Those three lineage mutations are accepted only at PostgreSQL `READ COMMITTED`; snapshot-retaining `REPEATABLE READ` and `SERIALIZABLE` callers fail closed with a stable retry reason rather than validate a pre-lock snapshot. The audit-gate migration holds write-blocking table locks in one explicit transaction while it validates existing compiled rows and installs the triggers, so no concurrent mismatch can enter an installation gap.

Critical Template Twin actions enqueue PHI-safe audit intent in the same
transaction as the state change. The outbox uses stable event keys, bounded
metadata, retry/backoff, and stale-processing lease recovery before writing the
ordinary audit log. Certification, activation, deactivation, retirement,
rollback, corrections, render verification, signing, export, and safety-gate
decisions must fail rather than silently lose their required audit intent.

This is application and database immutability. Storage administrators remain a privileged threat unless the bucket is also protected with object lock/versioning and restrictive IAM; see [Dedicated bucket readiness](#dedicated-bucket-readiness-and-qa-boundary).

## Untrusted-document defenses

Every uploaded file is treated as an untrusted ZIP/OOXML package. The upload route first enforces same-origin mutation, authenticated physician ownership, `.docx` extension, allowed MIME, non-empty bytes, and a 10 MiB source limit. It reads the request stream through a hard multipart byte ceiling before calling `formData()`, so missing, false, or chunked `Content-Length` cannot bypass the limit. The compiler then performs its own byte-level checks and does not trust the filename or browser MIME.

Default compiler limits include 512 entries, 16 MiB per expanded entry, 64 MiB total expanded content, a 100:1 maximum compression ratio, 12 MiB per parsed XML part, XML depth 128, 2,000 fields, 500 tables, and 10,000 structural nodes. Artifact reads/writes have a separate 25 MiB ceiling; source uploads remain subject to the stricter 10 MiB limit.

Rejected package classes include:

- wrong ZIP magic, missing/invalid central directory, CRC or size mismatch, overlapping local entries, or corrupt OPC declarations;
- ZIP64, multi-disk ZIP, encrypted entries, symbolic links, duplicate/case-colliding paths, unsupported compression methods, path traversal, and unsafe encoded paths;
- source, entry, total expansion, entry-count, compression-ratio, XML-depth, and structure-limit violations;
- macro-enabled DOCM content, VBA, ActiveX, custom UI, digital-signature active parts, OLE/package embeddings, `altChunk`, DDE/DDEAUTO, linked database/include fields, and attached templates;
- external or remote relationships, including `TargetMode="External"`;
- DTD/entity declarations, XML expansion/resource-limit violations, and malformed XML;
- missing or inconsistent `word/document.xml`, content types, relationships, headers, or footers.

Security-critical OOXML parsing matches namespace URI plus local name. OPC
relationship and content-type attributes are required to be unqualified; a
foreign-namespaced or duplicate-local-name `Target`, `TargetMode`, `Type`,
`Id`, or `ContentType` is rejected. Word fill structures in foreign
namespaces are rejected. `mc:AlternateContent` is inventoried as a
certification blocker rather than choosing a representation silently.

Field instructions are reconstructed from both `w:fldSimple/@w:instr` and
fragmented complex `w:instrText` runs. Safe alpha uses an allowlist of harmless
instructions (`DATE`, page/section counters, time, and Word form-field
instructions); DDE/DDEAUTO, INCLUDETEXT, INCLUDEPICTURE, DATABASE, LINK, and
every other unapproved instruction fail package inspection.

Rejected bytes are not stored. A metadata-only quarantine row may retain the digest, size, tenant/uploader, and a safe rejection code. Quarantine failures do not make an unsafe document acceptable.

Before source storage, the privacy inventory includes text nodes (including
tracked-deleted `w:delText`), every bounded non-namespace XML attribute,
document properties and metadata, relationship/content-type attributes,
header/footer/footnote/endnote parts, and image descriptions/alt text. XML
comments, CDATA, non-declaration processing instructions, custom XML, archive
or entry comments, arbitrary ZIP extra fields, and every unexpected OPC part
are rejected rather than declared scanned. The one container exception is an
exact Microsoft A220/A028 all-zero local-header growth pad; any other byte in
that payload is rejected.

Embedded media is rejected by default because its pixels cannot be reliably
scanned. A byte-exact, administratively reviewed static practice asset may be
approved only through the practice-scoped non-secret configuration:

```json
{
  "practice_synthetic_example": [
    "<lowercase-sha256-of-the-reviewed-static-asset>"
  ]
}
```

The JSON is supplied in
`TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON`. No global or
cross-practice hash is honored. Privacy/Legal and Operations own approval and
change control; Engineering must verify that each digest belongs to a blank,
static practice asset before configuration. The repository contains no real
asset or approval hash fixture.

The resulting inventory passes the deterministic PHI detector and a
fail-closed privacy scan through the shared `modelClient`. The scan sends the
privacy-relevant part text to the configured Anthropic clinical model;
therefore the appropriate vendor agreement, approved data handling, and
zero/limited-retention configuration are prerequisites. Provider failure,
uncertainty, over-limit text, suspected prompt injection, unscannable content,
or possible patient-specific content rejects the upload before immutable
storage. Rejected bytes are discarded; only digest, size, tenant/uploader,
safe rejection code, and durable audit intent may be retained.
An accepted immutable source also stores strict, PHI-safe scan provenance:
scanner profile, provider/model identifier, scan timestamp, scanned-part
count, and canonical hashes/counts for the exact practice approval set and
the approved assets actually used. The pre-certification synthetic proof binds
the canonical evidence hash, certification requires that exact proof-time
hash, and every later source read requires the certification binding. Missing,
malformed, legacy-null, or changed evidence blocks testing, certification,
generation, correction rendering, and signing with stable gate code
`TT_SOURCE_PROVENANCE_CURRENT_PROFILE_REQUIRED`.

## Deterministic compiler and `TemplateDocIR`

The compiler reads OOXML structure directly; it does not ask a language model to rediscover Word controls. It inventories the main document, headers, footers, relationships, styles, numbering, media, static nodes, bookmarks, and tables.

The safe-alpha compiler supports these structures when each exact binding can
be rendered and independently read back:

- single-paragraph plain-text content controls;
- native dropdowns with exact option order and stored value/display text;
- combo boxes, dates, and native Word checkboxes;
- safely detectable legacy text, dropdown, date, and checkbox form fields;
- simple fixed-table cells, including deterministic labels from adjacent or
  header cells; and
- table grids, horizontal `gridSpan`, vertical `vMerge`, nested-table
  inventory, fixed rows, headers, footers, bookmarks, tags, aliases, Word IDs,
  legacy names, static hashes, and exact structural paths.

Detection is broader than certification support. The IR records repeating
sections/rows, rich-text controls, multi-paragraph or list-bearing text
controls, compatibility blocks, data-bound controls, fixed/merged/nested
tables, drawings, and ordinary visible placeholders, but safe alpha blocks any
of them that cannot be proven through the renderer/readback pair.

Stable `fieldId`, `tableId`, and node IDs are derived from deterministic structure and hashes, not labels alone. Duplicate labels therefore remain distinct. Each fillable field records its exact part, structural path, binding kind, ordinal, original content hash, source-control hash, table location, and native identifiers.

Unsupported or ambiguous structures are appended to the IR with a stable code,
physician-readable reason, part/path available only in advanced detail,
clinical-materiality flag, and `blocksCertification` decision. Safe-alpha
blockers include:

- all Word repeating sections/items (`REPEATING_STRUCTURE_UNSUPPORTED_SAFE_ALPHA`),
  including non-table repeats; no cloned row is certified in this phase;
- rich-text controls and plain-text controls containing multiple paragraphs or
  list structure;
- unbound ordinary placeholders and visually blank complex table cells outside
  an explicitly versioned structural profile;
- `mc:AlternateContent`, data-bound/malformed/unrecognized controls, ambiguous
  or duplicate choice options, dynamic/active fields outside the harmless
  allowlist, and imported alternative-format content; and
- structures with a missing, duplicated, moved, or otherwise unstable binding.

An ordinary placeholder has no safe manual-binding path in this alpha. It must
be replaced with a supported Word control in a new template version. No
unsupported item is silently dropped or allowed to render blank under a claim
that the template is fully mapped.

The IR separately hashes:

- the immutable source package;
- the extracted structure (fields, tables, nodes, unsupported register);
- static content by part; and
- each binding's source control and original content.

### Existing `WM IOV Template.docx` compatibility evidence

The already-tracked repository fixture `WM IOV Template.docx` is read in place
by `wm-iov-existing-fixture.test.ts`; this branch does not add or copy another
real document. The current deterministic inventory reports:

| Structure                       | Aggregate finding                                                        |
| ------------------------------- | ------------------------------------------------------------------------ |
| Fillable controls               | 28 native dropdowns plus 52 `TAB_ONLY_BLANK_TABLE_CELL_V1` fields        |
| Other supported control kinds   | 0 combo boxes, 0 checkboxes, 0 date controls                             |
| Tables                          | 1 fixed table; 0 repeating tables                                        |
| Headers/footers                 | 2 header parts; 0 footer parts                                           |
| Compiler certification blockers | 7 `UNBOUND_ORDINARY_PLACEHOLDER`; no unrelated blocker is removed        |
| Pre-storage privacy blockers    | 6 auxiliary/glossary parts and 1 media part remain outside the allowlist |

The renderer/readback compatibility test can mechanically fill all 80 compiled
fields, removes all 28 `w:showingPlcHdr` markers, and verifies every field proof
plus static-region invariance. That does **not** certify the complete template:
the seven visible ordinary placeholders remain blocking and the package fails
the pre-storage auxiliary/media privacy profile. Desktop Word remains pending.

This fixture does **not** pass the complete upload gate. Aggregate inspection
finds one media entry and six auxiliary/custom package parts outside the
current safe-alpha privacy/package allowlist. Its image would additionally
need a byte-exact, practice-scoped administrative approval. Therefore the WM
IOV result is compiler/renderer compatibility evidence only, not evidence that
the document can be uploaded, stored, certified, or used with PHI. Every extra
part must first be safely classified or remain pre-storage blocked.

## Semantic mapping and certification lifecycle

After deterministic compilation, the shared `modelClient` may propose semantic metadata for the compiler-defined field set. The structured output can propose concept, data type, polarity, temporality, laterality, unit policy, synonyms, requiredness, and blank/unknown policy. It cannot create/delete fields, move controls, alter the layout, reorder/change native options, invent practice defaults, or activate a template.

Safe alpha additionally constrains `clinicalConcept` through the versioned
registry `template-twin-soap-concepts/1.0.0`. It contains only exact concepts
that the current Layer-3 SOAP entity projection can produce and the resolver
can validate: chief concern/HPI facets, medical history, medication and allergy
components, family/social history, named tests, assessment/plan items, and the
bounded ROS/exam system lists in `supported-concepts.ts`. Free-form specialty
concepts such as GAD-7, pregnancy status, monofilament findings, or custom
measurements are rejected with `TT_CONCEPT_UNSUPPORTED_V1`; they are not
silently left blank. `TemplateTwinConceptProvider` is the explicit extension
seam for a later versioned Template-Aware Extraction Agent, but safe alpha
registers no dynamic provider.

If the mapping provider is unavailable, deterministic fallback mappings are saved as visibly unconfirmed. They cannot be certified without physician review.

The certification flow is:

1. Upload a blank source DOCX.
2. Compile the package through all structural/security gates and build the IR/unsupported register.
3. Run the fail-closed template PHI gate, then store the accepted immutable source.
4. Review totals, controls, tables, every field, allowed options, semantic mapping, requiredness, and unknown policy.
5. Save physician mapping corrections. Saving invalidates any previous synthetic proof.
6. Exercise every required or clinically material field with explicitly marked
   synthetic evidence through the same Layer-3 fact/resolver/validator/renderer
   pipeline. Coverage records exact dropdown option/ordinal, checkbox polarity,
   date, number/unit, laterality, and table behavior as applicable. A single
   generic paragraph cannot certify unrelated fields. Before Layer 3 or
   persistence, synthetic input passes deterministic structured-PHI rejection
   and the conservative shared `modelClient` privacy gate. Synthetic audio uses
   the existing transcription orchestrator and is not stored by QuillMD.
7. Download and inspect the synthetic clone.
8. Explicitly acknowledge both certification statements.
9. Certify and activate only if every field mapping is supported/certified, the
   field set and mapping hash are current, required/material field coverage is
   complete, every optional untested field has a current physician waiver,
   there are no blocking unsupported items, and the synthetic output has
   verified package/static/field readback.

An optional-field waiver is field-specific and records physician identity,
reason, mapping hash, and timestamp with a durable audit event. Required or
clinically material fields cannot be waived. A mapping or synthetic-test change
invalidates prior certification acknowledgements; a stale mapping hash also
invalidates waivers and coverage evidence.

Certification and activation run in a serializable transaction. Activation inactivates another active template for the same physician/encounter scope. The append-only certification records the certifier, exact structure hash, approved mapping hash, synthetic manifest, output key/hash, and timestamp.

Changing a certified mapping must create a new `NoteTemplate` lineage version. It must never mutate the activated version or silently learn from a visit correction.

## Encounter facts, resolution, and validation

Conversation recording, dictation, and typed encounter input converge after the existing Layer 3 extraction step. `projectEncounterFacts` produces the same canonical fact shape for each input mode:

- value, polarity, temporality, experiencer, and laterality;
- explicit number and unit;
- speaker and source transcript offsets when available;
- audio timestamp when available;
- evidence-anchor IDs and the supporting quote; and
- ASR/evidence quality signals.

The Template Twin resolver is deterministic over certified mappings and canonical facts. It produces `supported`, `explicitly_denied`, `not_mentioned`, `ambiguous`, `conflict`, `needs_clinician_input`, or `approved_practice_default`.

Resolution rules include exact dropdown membership and ordinal matching,
tri-state checkbox handling, independent table-cell evidence, no inferred
units, no closest-option substitution, no implicit carry-forward,
patient-experiencer checks, required laterality, and blank/approved “not
documented” behavior for unsupported evidence. Every populated value,
including an approved practice default, is schema-invalid without retained
`sourceFactIds` and evidence anchors; generated default facts are explicitly
labeled as defaults rather than encounter evidence.

Checkbox `true` requires affirmative evidence. Checkbox `false` is renderable
only for an `explicitly_denied` resolution when the physician-certified
mapping explicitly defines unchecked as false. Null, unknown, conflict, and
not-mentioned states remain unresolved; they cannot collapse to false in
native or legacy checkbox bindings. A clinically meaningful unresolved
checkbox keeps the fill `NEEDS_REVIEW` and blocks signing.

For narrative, dropdown, multi-select, date, and repeating fields,
`explicitly_denied` is not renderable unless a future certified mapping schema
defines an exact negative output policy. Safe alpha has no such general policy,
so denial remains unresolved instead of being accepted by validation and then
failing in the renderer.

Independent validation reruns after resolution and before rendering. Blocking checks cover:

- malformed, duplicate, missing, unknown, uncertified, or type-incompatible fields/mappings/resolutions/facts;
- missing facts, missing/untraceable anchors, incomplete evidence coverage, unsupported assertions, or a populated unresolved field;
- dropdown/multi-select membership and ordinal integrity;
- checkbox polarity;
- ISO dates, finite numbers, explicit units, laterality, dates/durations, medication components, dose/route/frequency, and allergies;
- required fields, evidence conflicts, unclear evidence, and clinician-input requirements;
- table definition, row shape, aligned columns/evidence, and maximum-row overflow;
- clinically material unsupported structures.

Invalid manifests are persisted as `NEEDS_REVIEW` without an output DOCX. A valid manifest is rendered and stored as `VERIFIED`. A signed manifest is immutable.

## Exact renderer, round-trip proof, and signing

The renderer starts from bytes read and hash-verified from the immutable source. It recompiles the source and compares compiler version, source digest/size, structure, parts, fields, tables, and static hashes to the certified IR before applying any value.

It patches only approved XML spans:

- content-control display text and native dropdown/combo selection;
- checkbox state plus visible checked/unchecked glyph;
- date control value/display format;
- legacy form field state/result text;
- exact simple fixed-table-cell content; and
- populated control placeholder metadata (`w:showingPlcHdr` and
  placeholder-only `PlaceholderText` styling) without treating an unresolved
  control as populated.

Safe alpha does not patch multi-paragraph/list rich text or clone repeating
rows. Those structures block certification before runtime.

All other OOXML entries remain byte-identical after decompression. Modified XML parts must equal the exact source text plus the approved patches. The ZIP container itself is rebuilt deterministically enough for a valid DOCX, so the whole ZIP byte stream is not expected to match the source.

After rendering, `output-readback.ts` independently reopens the completed DOCX.
It receives source bytes, output bytes, the certified IR, and approved
resolutions—but no renderer patch objects. It reparses the package, locates
each stable binding, derives the actual content-control/legacy/table-cell
value, exact dropdown option, checkbox state/glyph, date, placeholder state,
and occurrence count from output XML, then computes output-derived value
hashes. Missing, duplicated, moved, unexpected, or value-mismatched bindings
fail closed. Package security, untouched-entry comparison, static-region
invariance, and output SHA-256 are checked separately.

Every IR field receives one proof, including blank/no-op fields. Its
disposition is `rendered`, `unresolved_blank`, `preserved_unresolved`, or
`preserved_unsupported`; omission is a verification failure. This prevents
certification and signing from disagreeing about fields the renderer skipped.

The visit review surface shows filled/review/not-mentioned/conflict counts, prioritizes critical field classes, supports an attention-only filter, surfaces deterministic long-value/repeating-row layout warnings, and reveals the resolved value, exact allowed options, reason, supporting quote, speaker, evidence anchors, and audio timestamp when present. Storage keys and provider payloads never cross the server-component DTO boundary.

A physician may explicitly correct an unsigned field. The server canonicalizes the field type, creates labeled physician-review evidence, reruns independent validation, and stores a replacement output only after exact rendering and output-derived readback. Each decision is append-only and uses optimistic manifest concurrency. “Create mapping rule” additionally forks an uncertified `NoteTemplate` version over the same immutable source/IR, resets the target mapping to `NEEDS_CONFIRMATION`, and requires a new synthetic proof and certification; it never changes the active version automatically.

Each fill manifest pins the exact physician-visible SOAP revision and canonical
SHA-256 used to resolve it. Every SOAP edit increments the SOAP version and, in
the same transaction, invalidates any unsigned Twin to `NEEDS_REVIEW`; the
prior manifest/output remain audit evidence but cannot authorize signing.
Regeneration must bind the new SOAP version/hash. The signing gate recomputes
the hash from the current SOAP and rejects a stale allergy, medication,
assessment, plan, or any other edit.

The worker and physician-correction service also lock and reread the visit in
their final serializable database transaction after rendering and immutable
object storage. They compare the exact SOAP text, version, canonical hash,
physician, and template version. If the SOAP changed during that window, a new
fill or correction is not created; an existing unsigned fill is left
`NEEDS_REVIEW`; and the newly written bytes remain an unclaimed `RETAINED`
ledger object with a durable `SOAP_BINDING_STALE` safety event. A version-only
or initial-read-only check cannot authorize the output.

The signing route independently reloads and parses the certified IR/mappings,
recomputes source/compiler/structure/static/mapping integrity, reruns the field
validator and status counts, and binds every output-derived proof to the
canonical manifest value/part/path/occurrence count. For **every** Template
Twin `READY` → `SIGNED` transition—even when the physician selected no DOCX
download destination—it reads the stored output stream, counts bytes, hashes
the bytes, and compares them with the manifest/signing claim. Missing,
truncated, modified, or replaced storage objects block signing. Only then does
the serializable transaction compare SOAP provenance and optimistically change
the exact fill claim from `VERIFIED` to `SIGNED` with the visit transition.
A concurrent correction, regeneration, artifact replacement, or stale worker
write loses closed. PHI-safe audit metadata contains codes, counts, IDs, and
versions, not clinical values.

“Original Template DOCX” is the clearly labeled primary document choice when a
Twin is active and verified, and remains an additive delivery destination
(`docx_original_template`). It is never silently signed or exported while
unresolved. The download route only serves an owned, non-deleted, signed visit
with a signed verified manifest. It reads the already-rendered object through
tenant/key/size/metadata/SHA verification and never regenerates at download
time. Existing generic DOCX/PDF/email/clipboard behavior remains available.

## HTTP surface

All responses are private/no-store. Template Twin mutation/export routes require a freshly read database user with the `DOCTOR` role, tenant/record ownership, both rollout gates, structured request validation, and same-origin checks; a stale session role cannot authorize the operation. Upload additionally requires a physician-readable name, encounter/specialty scope, and version description—there is no silent catch-all “Original Word template.”

| Method and route                                                  | Purpose                                                                                                                        |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `POST /api/note-templates/template-twin/upload`                   | Upload, validate, PHI-scan, compile, persist draft, and return certification URL                                               |
| `PATCH /api/note-templates/template-twin/:id/mappings`            | Save the complete physician-reviewed mapping set with optimistic mapping hash                                                  |
| `POST /api/note-templates/template-twin/:id/synthetic-test`       | Resolve synthetic text, validate, render, round-trip verify, and save the current proof                                        |
| `POST /api/note-templates/template-twin/:id/synthetic-test-voice` | Transcribe ephemeral synthetic audio through the existing provider architecture, then run the same synthetic fill proof        |
| `GET /api/note-templates/template-twin/:id/test-output`           | Download an owned, currently verified synthetic output                                                                         |
| `POST /api/note-templates/template-twin/:id/certify`              | Verify current hashes/acknowledgements, append certification, and activate                                                     |
| `PATCH /api/visits/:id/template-twin/corrections`                 | Apply one physician-labeled field delta, independently revalidate/rerender, and optionally fork an uncertified mapping version |
| `POST /api/visits/:id/sign`                                       | Enforce all existing clinical gates plus the Template Twin server gate and atomic sign claim                                   |
| `GET /api/visits/:id/export/original-template-docx`               | Stream the signed, immutable, storage-verified Template Twin output                                                            |

The certification workspace is `/settings/note-format/:id/certify`. It leads
with clinical labels, field meaning, exact options, checkbox meaning,
blank/unknown behavior, defaults, unsupported items, test coverage, and output
download. OOXML part names, structural paths, hashes, and renderer bindings are
inside collapsed advanced details.

The Note Format manager provides immutable-lineage actions to create a new
version, activate, deactivate, retire, inspect history, and roll back by
activating a previously certified version without changing history. Generic
note-template lifecycle actions reject mutation of Template Twin rows through
legacy edit/delete/duplicate paths.

## Database schema and migrations

The feature uses these forward migrations:

1. `packages/db/prisma/migrations/20260715162000_template_twin_docx_v1/migration.sql`
2. `packages/db/prisma/migrations/20260715180000_template_twin_version_forks/migration.sql`
3. `packages/db/prisma/migrations/20260715203000_template_twin_audit_gates_v1/migration.sql`
4. `packages/db/prisma/migrations/20260716113000_template_twin_rollout_generations/migration.sql`

The first migration is an atomic, timeout-bounded **expand only** migration. It
does not backfill `note_templates`, set `lineageId` non-null, or build a plain
index over the populated table. It adds:

- Template Twin audit actions and certification/detection/resolution/fill enums;
- nullable `NoteTemplate.lineageId`, `parentVersionId`, and `templateKind`, plus
  a mixed-version insert trigger;
- PHI-free durable lineage-backfill cursor/progress state;
- source artifacts, compiled versions, field definitions, semantic mappings, certifications, visit fill manifests, and review decisions;
- hash/count/state constraints, ownership/provenance foreign keys, lookup indexes, and one-fill-per-visit uniqueness;
- database triggers enforcing source, certification, certified-definition/mapping, and signed-manifest immutability.

The second migration replaces the original source/compiler unique index with a normal index. This permits a new immutable `NoteTemplate` version to reuse the same immutable source and IR when a physician explicitly creates a new mapping-rule version.

The third migration is additive and fail-closed. It adds:

- `Practice.templateTwinEnabled` with database default `false` and
  `NoteTemplate.versionDescription`;
- SOAP version/hash provenance on visit fill manifests (legacy nullable rows
  cannot sign until regenerated);
- field-level certification waivers keyed to the exact mapping hash;
- durable object-write/orphan ledger and transactional audit outbox tables;
- audit actions for waiver, deactivation, retirement, rollback, safety-gate,
  and reconciliation events; and
- compiled-source/physician-owner tenant validation, owner-reassignment,
  tenant/lineage, output-key, review-field, waiver, and immutability constraint
  triggers plus supporting indexes.

The fourth migration adds the database-backed monotonic global/practice rollout
generations and pinned/signed fill generations used for linearizable revocation.

`prisma migrate deploy` intentionally stops at the lineage expand shape. The
versioned operator in `packages/db/scripts/template-twin-lineage-online.ts`
must then build a transition guard index concurrently, backfill bounded
primary-key batches, build final indexes concurrently, validate a non-null
proof, and take the short final contract lock. Template Twin enablement fails
closed until the durable phase is `CONTRACTED`. Full deployment, pause/resume,
lock, failure, checksum, and future Prisma-drift handling are in
`docs/runbooks/template-twin-lineage-online-migration.md`.

The third migration intentionally takes `SHARE ROW EXCLUSIVE` locks on the
compiled-version, source-artifact, note-template, and user tables for the
duration of one explicit transaction. Production rollout therefore requires a
reviewed maintenance window and lock-wait monitoring; the migration must not be
split into statementwise execution.

There is no down migration. No migration has been applied to production by
this branch. Production rollback, if a later deployment is approved, is an
app/worker code-image rollback with the additive schema left in place and both
rollout gates off. Dropping Template Twin tables, enum values, triggers,
outbox/ledger evidence, or source/output objects is destructive and is not an
approved rollback.

## Dedicated bucket readiness and QA boundary

The application deliberately **never creates or configures the Template Twin
bucket from a request path**. `createTemplateTwinArtifactStore()` checks the
bucket and the selected readiness profile and fails closed when required
evidence is missing.

The bucket name is selected by the non-secret `TRANSCRIBE_MD_TEMPLATE_BUCKET`; when unset it defaults to:

```text
transcribe-md-template-artifacts
```

Production profile readiness requires provider verification or an explicit
operator attestation for every control: private access, encryption at rest,
TLS expectation, least-privilege runtime credentials, versioning/object lock,
lifecycle/retention, and backup/restore. A bucket that merely exists is not
ready. Attestation closes only an evidence/API gap; it does not configure the
provider.

The isolated QA compose file has a one-shot `minio-template-init` service that
creates `transcribe-md-template-artifacts-qa` separately from audio storage,
removes anonymous access, enables versioning, and creates it with MinIO object
lock capability. QA readiness does not accept a blanket “synthetic” exemption.
It requires the MinIO API to verify both:

- no anonymous/public bucket policy; and
- enabled versioning plus object-lock capability.

QA isolation also requires `TEMPLATE_TWIN_STORAGE_PROFILE=qa`, mocked providers,
a QA/test-named database, and a bucket name containing the QA marker. Controls
that this local stack cannot honestly prove require their own exact, named
exception value, `accepted-isolated-synthetic-qa-gap`:

- `TEMPLATE_TWIN_QA_STORAGE_ENCRYPTION_AT_REST_ATTESTATION`;
- `TEMPLATE_TWIN_QA_STORAGE_TLS_EXPECTATION_ATTESTATION`;
- `TEMPLATE_TWIN_QA_STORAGE_LEAST_PRIVILEGE_ATTESTATION`;
- `TEMPLATE_TWIN_QA_STORAGE_LIFECYCLE_RETENTION_ATTESTATION`; and
- `TEMPLATE_TWIN_QA_STORAGE_BACKUP_RESTORE_ATTESTATION`.

Each accepted value is reported as `qa_exception`, never `verified` or a
production attestation. A missing/malformed named exception, a public policy,
disabled versioning, or missing object-lock capability fails QA readiness.
Successful synthetic-QA readiness still returns `productionReady: false`.
Local MinIO does not prove production TLS, encryption, IAM, lifecycle, backup,
restore, or legal retention controls.

Before any approved production runtime test, Operations must:

1. Provision the bucket outside an application request path.
2. Keep it private with no anonymous policy or public URL.
3. Grant the request-serving application only the bucket-existence/stat, put,
   and get operations required by the code. If orphan purge is later approved,
   review a separately scoped worker identity for delete access to this
   dedicated bucket; do not give request paths delete authority.
4. Enable object lock at bucket creation when supported, or document the approved versioning/IAM alternative. Application UUID+digest keys and no-delete code reduce accidental overwrite risk but do not constrain a storage administrator.
5. Enable encryption at rest consistent with the QuillMD storage standard.
6. Include the bucket in encrypted backup/off-site-copy procedures and perform a documented synthetic restore test.
7. Define source/output retention with Privacy/Legal and Clinical Records. Do not attach a generic lifecycle deletion rule until signed-record retention is approved.
8. Add capacity, read-integrity, and failed-write alerts with an Operations owner.
9. Verify that logs/metrics record only safe error codes, counts, size, and hashes—not keys, filenames, document text, or field values.

The worker has an opt-in maintenance job for outbox delivery and object-ledger
reconciliation. `TEMPLATE_TWIN_MAINTENANCE_ENABLED=true` requires a bounded
`TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS` (1–365). It can recover an object whose
PUT succeeded before ledger state was advanced, retry transient stat/delivery
failures, and retain an expired orphan. Deletion remains independently off
unless `TEMPLATE_TWIN_ORPHAN_PURGE_APPROVED=true` is present at the destructive
boundary. Enabling purge requires an approved retention/legal-hold decision;
the branch does not invent one.

## Deployment order and operational acceptance

No deploy is authorized by this document. When separately approved, use an isolated QA environment and synthetic templates first.

Required order:

1. Record app/worker image digests, database migration status, and backup/restore evidence.
2. Provision and verify the private bucket and least-privilege runtime policy.
3. Confirm Anthropic/vendor agreement and privacy controls for source PHI scanning and mapping proposals.
4. Apply all three Prisma migrations through the existing migration deployment path.
5. Deploy compatible TranscribeMD app and worker images together; the app owns upload/review/sign/export, while the worker owns encounter filling.
6. Verify application and worker health without real PHI.
7. Run one synthetic upload → mapping review → synthetic output → certification → typed visit → review → sign → original DOCX flow.
8. Run a synthetic voice visit through the same certified template.
9. Verify durable outbox delivery, object-ledger reconciliation, and
   object/database hashes without printing payloads.
10. Keep `Practice.templateTwinEnabled=false` for every practice until its
    named clinical/operations approval; use the global kill switch for an
    immediate all-practice stop.
11. Obtain Engineering, Clinical Safety, Privacy/Legal, and Operations
    approval before any real-PHI pilot.

## Versioning and rollback

- Source artifacts and certified versions are immutable. A mapping/layout change creates a new lineage version; it never alters past visits.
- Each fill manifest pins template, compiler, resolver/model, renderer,
  fact-set hash, manifest hash, output hash, validation result, and exact SOAP
  version/hash.
- Worker retries atomically pin the active template ID/version before provider or object-storage I/O, then reuse that exact pin even after a newer lineage version becomes active; missing or inconsistent pins fail closed.
- A retry with the same manifest is idempotent. A changed unsigned result increments the database optimistic `manifestVersion` and creates a new output key. Reviewed or signed manifests reject worker replacement, and an unrelated visit review reason is never cleared by Template Twin.
- Existing generic note formats and exports are not removed.
- Product rollback for new visits is to activate a previously certified Twin
  version or deactivate the Twin and return to the approved structured
  template; historical Twin fills/outputs remain retained and readable.
- Immediate rollout rollback is `TEMPLATE_TWIN_KILL_SWITCH` absent/truthy or
  `Practice.templateTwinEnabled=false`; deployment rollback restores the prior
  app and worker images together and leaves additive database changes in place.
  The practice flag is rechecked in the final acknowledgement/signing database
  claim so a concurrent disable wins closed. The process environment kill
  switch stops newly evaluated requests; changing it by app rollout does not
  purport to drain work already executing on an older process, so Operations
  should also disable the practice flag before or with a global stop.
- If migrations themselves cause an unrecoverable database incident, use the established point-in-time/verified-backup recovery procedure. Do not improvise table drops on production.
- Before rollout, record exact previous app/worker image digests and confirm that the prior code tolerates the additive columns/tables (it should ignore them).

## Active TranscribeMD verification commands

Run from the repository root unless a command says otherwise. Bare root `npm run lint`, `npm run build`, and `npm run test:unit` target the legacy `meddoc-pro` workspace, not TranscribeMD, and are not the acceptance commands for this feature.

| Check                  | Active command                                                    | Notes                                                                           |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Prisma format          | `npx prisma format --schema packages/db/prisma/schema.prisma`     | Formatting only; review the resulting diff                                      |
| Prisma validation      | `npx prisma validate --schema packages/db/prisma/schema.prisma`   | Read-only schema validation                                                     |
| Generate client        | `npm run db:generate`                                             | Alias for `npm run generate -w @meddoc/db`                                      |
| Migration status       | `npm run db:migrate:status`                                       | Read-only status; do not use production credentials during local validation     |
| Targeted unit tests    | `npm run test:unit -w transcribe-md -- <app-relative-test-paths>` | Vitest runs from `apps/transcribe-md`; use `src/...` paths                      |
| Full active unit suite | `npm run test:unit -w transcribe-md`                              | Includes TranscribeMD and `packages/*/src` tests via the app Vitest config      |
| Typecheck              | `npx tsc -p apps/transcribe-md/tsconfig.json --noEmit`            | No package script exists; this is the active app config                         |
| Lint                   | `npm run lint -w transcribe-md`                                   | Covers app and worker source under the workspace                                |
| Production build       | `npm run build -w transcribe-md`                                  | Next.js 16 build; do not run against the live checkout during a read-only audit |
| TranscribeMD E2E       | `npm run test:e2e -w transcribe-md`                               | Playwright; isolated QA/test services and synthetic data only                   |
| Root E2E alias         | `npm run test:e2e:transcribe-md`                                  | Equivalent workspace alias                                                      |

CI evidence lives in:

- `.github/workflows/test.yml` — `npm run test:unit -w transcribe-md`;
- `.github/workflows/e2e.yml` — isolated TranscribeMD app/worker/QA stack and Playwright;
- `.github/workflows/a11y.yml` — TranscribeMD production build and accessibility run.

Migration deployment is `npm run db:migrate:deploy`, but it is an operational write and must run only in an explicitly approved deployment window. It is not a developer verification command.

### Synthetic test plan and result record

Only synthetic, deterministic fixtures are permitted. No provider, email, billing, storage-deletion, or production-service call belongs in the unit suite.

Required fixture coverage:

- native dropdowns, combo boxes, text/date controls, native and legacy checkboxes;
- legacy fields, fixed tables, repeating/nested/merged structure blockers,
  headers/footers, duplicate labels, long values, ordinary placeholders, rich
  text, and unsupported controls;
- corrupt ZIP/OPC/XML, wrong magic, path traversal, duplicate paths,
  symlink/encryption/ZIP64, namespace-shadowed relationships/content types,
  fragmented field instructions, malicious relationships, DTD/entity input,
  active content, OLE, and decompression/XML/resource limits;
- tracked-deleted PHI, document metadata, custom XML, image descriptions, and
  non-allowlisted media rejection before storage;
- semantic mapping with mocked `modelClient` output and fallback behavior;
- exact-option, tri-state checkbox, denial policy, unit, laterality,
  medication/allergy, table, evidence, supported-concept, and
  unsupported-element validation;
- renderer/readback independence, placeholder cleanup, static-region
  invariance, output-derived field-value hashes/occurrences, and fail-closed
  post-render mutation paths;
- fresh-role physician/practice authorization, lifecycle immutability, mapping-hash conflicts, certified-field overlays, certification prerequisites, signing claim races, pre-sign artifact verification, and export integrity;
- synthetic-marker/privacy-gate rejection before Layer 3 or persistence;
- stale SOAP and corrupted/missing stored-object sign blocks, account deletion
  with retained Twin data, feature-off routes, and direct-database cross-tenant
  insertion rejection;
- stateful upload-to-certification integration, route-level
  voice-to-filled-original E2E, typed/voice equivalence, correction and SOAP
  invalidation/regeneration, orphan reconciliation, retry-pin/reviewed-manifest
  races, and regression of current note-format and generic exports.

Complete this table at merge handoff; do not replace missing evidence with assumptions:

| Gate                                        | Command/evidence                                                             | Result                                                                                                             | UTC        | Commit/run link                    |
| ------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ---------- | ---------------------------------- |
| Prisma format/validate/generate             | Commands above                                                               | `PASS`                                                                                                             | 2026-07-16 | Local compatibility-branch run     |
| Full Template Twin suite                    | Consolidated feature-path invocation, including the tracked WM fixture       | `PASS — 63 files / 664 tests`                                                                                      | 2026-07-16 | Synthetic/local only               |
| Full TranscribeMD unit suite                | `npm run test:unit -w transcribe-md`                                         | `PASS — 205 files / 2,510 tests`                                                                                   | 2026-07-16 | Synthetic/local only               |
| Type generation/typecheck                   | `next typegen` then active `tsc --noEmit` command                            | `PASS`                                                                                                             | 2026-07-16 | Local compatibility-branch run     |
| Focused/full lint                           | Changed-path files / full active command                                     | `FOCUSED PASS; FULL ACTIVE MATCHES PRE-EXISTING DEBT — 29 errors / 39 warnings (main baseline: 30 / 41)`           | 2026-07-16 | Marketing: 0/1; legacy: 0/3        |
| Production build                            | Clean Docker app/worker/migrator image builds                                | `PASS`; app bundle assertions passed                                                                               | 2026-07-16 | Disposable local images            |
| Migration tests                             | Fresh QA PostgreSQL plus interrupted/resumed one-million-row upgrade harness | `PASS — all 71 migrations; 1,000,000 requested rows; retry/idempotency/lock-contention proof passed`               | 2026-07-16 | Disposable QA only                 |
| Isolated infrastructure-backed QA E2E       | `playwright test --project=template-twin`                                    | `PASS — 1 scenario / 28.9 s`                                                                                       | 2026-07-16 | QA stack and volumes removed       |
| Browser safety/accessibility                | Chromium, PHI reject, Rx safety, and axe projects                            | `PASS — 54 + 1 + 7 + 26 tests`                                                                                     | 2026-07-16 | Synthetic/local only               |
| Open XML and LibreOffice gate               | SDK 3.5.1 plus pinned LibreOffice 25.8.7.3                                   | `PRE-DELIVERY PASS; QA-ONLY ROUND-TRIP PASS; 7 classified LibreOffice-only schema diagnostics remain Word-pending` | 2026-07-16 | Exact tab-only corpus              |
| Desktop Microsoft Word                      | Returned no-network Windows QA bundle                                        | `PENDING`                                                                                                          | —          | Mandatory release gate             |
| Dependency/secret gates                     | npm high/critical audit and TruffleHog filesystem scan                       | `PASS — 0 high/critical; 0 detected secrets`                                                                       | 2026-07-16 | Moderate/low audit findings remain |
| Backup/restore and production bucket policy | Operations evidence                                                          | `PENDING`                                                                                                          | —          | Production-readiness prerequisite  |
| Clinical/privacy approval                   | Named approval records                                                       | `PENDING`                                                                                                          | —          | Real-PHI prerequisite              |

## Current limitations and v1 non-goals

### Exact WM IOV compatibility slice

`TAB_ONLY_BLANK_TABLE_CELL_V1` is the only additional unbound table-cell
profile admitted by this compatibility branch. It is not generic complex-table
support. The compiler requires one unmerged, non-nested target cell with one
blank paragraph. That paragraph contains only an approved set of ordinary
paragraph/run properties and exactly one left tab-stop definition under
`w:pPr/w:tabs/w:tab`; it contains no mutable run or visible text. A physician
must still confirm the inferred label, clinical mapping, blank policy, and
synthetic coverage before certification.

The renderer preserves the complete table, cell, paragraph properties, and tab
stop and appends one plain `w:r/w:t` value at the certified cell path. Strict
readback derives the value from that completed run, fingerprints the profile,
and inventories every profiled cell across the package. A moved, swapped,
duplicated, missing, merged, or property-altered cell fails
`template-docx-readback/2.0.0`; the profile proof is required again by
certification and signing. Newlines and content tabs are rejected, and the
existing 32,767-character limit continues to produce an overflow review gate.
The completed-byte fingerprint binds the exact cell/paragraph attributes and
the immutable `tcPr`/`pPr` descriptors. The renderer-owned run must have no
attributes or formatting children, and its one text node may carry only the
conditionally required `xml:space="preserve"`. Tracked-deletion attributes,
raw property text, added run attributes, and unnecessary text-preservation
metadata all fail strict readback.

The unchanged WM IOV fixture now deterministically compiles 52 cells under this
profile. Its seven ordinary placeholders remain
`UNBOUND_ORDINARY_PLACEHOLDER` certification blockers. Six auxiliary/glossary
parts and one media part remain rejected by the pre-storage privacy profile, so
the complete document still cannot upload or certify. Media, auxiliary parts,
ordinary placeholders, rich text, repeating sections, and every other complex
cell signature remain outside this slice.

Current implementation limitations that must remain visible:

- Word has no server-side layout engine here. The renderer enforces character
  limits plus XML/package integrity and can flag long replacements, but it
  cannot prove page-level overflow, pagination, font substitution, printer
  behavior, or whether desktop Word shows an open-repair dialog. The pinned
  LibreOffice synthetic round-trip passed for this profile; human desktop Word
  visual/open-repair QA remains a release gate.
- The ZIP container is rebuilt, so ZIP-level timestamps/compression/order may differ. The guarantee is approved XML patches plus byte-identical decompressed untouched entries and static-content invariance, not a byte-identical whole file.
- All repeating sections, multi-paragraph/list rich text, data-bound controls,
  ordinary unbound placeholders, unprofiled complex table cells,
  `mc:AlternateContent`, active/unapproved fields, and ambiguous structures are
  certification-blocked in safe alpha.
- The fixed SOAP taxonomy cannot extract arbitrary specialty concepts. The
  later Template-Aware Extraction Agent must extend the versioned registry and
  all projection/resolution/validation paths before such a concept can certify.
- Object-ledger reconciliation and audit delivery exist but are opt-in and do
  not replace an operations dashboard, alert owner, approved retention policy,
  or documented restore test. Orphan purge remains separately off.
- Accounts without Twin records keep the existing tested deletion path.
  Accounts with retained Twin source/certification/waiver/template/fill,
  object-ledger, outbox, or delivered-audit records receive deterministic HTTP
  409 with no partial database or bucket deletion.
  Privacy/Legal must decide anonymization, retention, and legal-hold policy
  before that path can change.
- Template Twin corrections intentionally do not clear a generic visit-level `needsReview` reason because other safety lanes may own it; clearing requires an explicit source-aware review-state model in a later change.
- The PHI gate cannot establish legal compliance by itself. Vendor agreements, policy, retention, access controls, backups/restores, incident response, and clinical approval remain separate requirements.
- Evidence anchors prove traceability to retained encounter evidence; they do not prove that ASR/model extraction is clinically correct. The physician still reviews and signs.

Explicit v1 non-goals:

- flattened/scanned PDF or PDF AcroForm filling;
- XLSX templates;
- marketing redesign, billing, provider migration, or production deployment;
- automatic learning from corrections without explicit physician approval;
- direct EHR integration; and
- replacing the existing generic DOCX/PDF/export or model-provider architecture.

## Production acceptance checklist

Production remains blocked until all of the following have evidence:

- all three migrations reviewed and applied in isolated QA;
- private bucket, IAM, encryption, immutability control, retention, backup, restore, and alert ownership approved;
- all test-result placeholders above completed with passing or explicitly dispositioned results;
- correction/rerender/new-version workflow tested in isolated QA with synthetic values;
- the infrastructure-backed upload → certification → typed/voice → SOAP edit
  invalidation → regeneration → correction → signing → stored-byte verification
  → download test passes against actual QA Postgres, Redis/worker, and MinIO;
- synthetic typed and voice end-to-end outputs visually compared with their original DOCX;
- no critical unresolved field can sign through direct API calls or races;
- existing custom-template and generic export regressions pass;
- Anthropic and storage vendor agreements/data handling approved by Privacy/Legal;
- a clinical owner approves review wording, critical-field policy, and synthetic cases;
- the global switch and every practice remain default off until a documented
  rollout/kill-switch exercise succeeds;
- prior image digests and rollback procedure recorded; and
- explicit founder/operations authorization for the production deployment window.
