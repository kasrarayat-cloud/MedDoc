# Corti coding and preserving Word export candidate — 16 October 2026

The normal Coding tab can now use Corti direct prediction independently of the
clinical-generation provider. A clinician reviews saved suggestions, saves
accept/reject choices, explicitly approves that revision, and downloads a new
Word variant with accepted eligible codes. Original-format exports and historical
documents remain unchanged. This candidate is synthetic-only; it is not a
production or real-patient activation.

## Implementation and boundaries

- `QUILLMD_CODING_PROVIDER` defaults to `existing`. Corti is an explicit separate
  configuration, not a change to `AI_PROVIDER`. Immutable runs select their own
  engine; old ICD runs retain their existing engine and restrictions.
- The direct path requests `icd10cm-outpatient` and `cpt` in one prediction.
  It never invokes an agent, connector discovery, verification inference or
  fallback prediction. A durable attempt is reserved before transport. Duplicate
  admission returns the existing revision-bound run; any attempted/unknown
  outcome cannot be sent again. Automatic retries and redirects are disabled.
- A future eligible live configuration uses protected dotenv data with
  `CORTI_CLIENT_ID`, `CORTI_CLIENT_SECRET`, `CORTI_ENVIRONMENT` and
  `CORTI_TENANT_NAME`. Exported assignments are parsed without shell execution or
  interpolation. Region and tenant are bound to the run; secrets/tokens are not.
  The retained account's region/tenant are `us`/`base`. This implementation did
  not read its credentials or make a provider request.
- The new prospective purpose is
  `corti-direct-coding-workflow-synthetic-20261016`, under the current standing
  QuillMD testing authority and enrolled clinician/department checks. It does not
  reuse the original prediction or agent-task allowance. Technical limits are
  one prediction per run, 512,000 request bytes, 4 MiB response bytes and a
  120-second response bound. Client timeouts do not cancel server work or impose
  a guaranteed billing cap. Provider credits remain credits; unreconciled dollar
  cost remains unknown.
- The unchanged adapter from `b998d9613` admits only provider-selected codes.
  Full provider candidates, nested alternatives, raw display text and evidence
  remain diagnostic. They cannot be promoted through selection or override
  payloads. The context-ID repair `4b41274c4` and its GET-only recovery tests
  remain unchanged; no task recovery or submission is needed here.
- ICD descriptions come from the bound, hashed, dated official release. The
  selected code also needs a source-to-Index-to-Tabular route, specificity and
  assertion checks. Source identity and explicit symptom causality are checked
  independently of provider omissions. Unrecognized source routes remain held.
- Decisions bind encounter, patient, department, saved revision, context,
  terminology and selection digest. Unsaved edits survive polling and block
  approval/export. The server rechecks currentness, permissions and eligibility.
  Acceptance cannot establish a missing terminology release or permission.
- The export reads the persisted approval. It copies the finalized original,
  preserves its clinical body bytes and every other ZIP member, and appends one
  tagged “Diagnosis and procedure codes” section. Nonempty groups are ICD-10-CM
  then CPT. Only accepted eligible descriptions from the dated catalog are used.
  A deterministic separate private variant is created exclusively, never
  overwritten. Repeated downloads reuse it after eligibility/integrity checks.
  Existing appendices are refused. No clinical generation runs during export.

## Installed private replay candidate

The isolated checkout is
`/home/claude/quillmd-corti-test/workflow-checkout-20261016`, based on both preserved
commits. Its candidate server is loopback-only at `127.0.0.1:9146`, with a separate
PostgreSQL container on `127.0.0.1:55449`, test database, private files, static
assets and file-only outbox. It does not load the served environment or provider
secrets. The candidate settings force the exact retained synthetic replay.

Clinician URL:
`http://127.0.0.1:9146/encounters/a724dfab-59fe-45ac-87de-88cbc9d92d17/?tab=coding`.
Use the usual authenticated SSH access to forward local port 9146 to server
`127.0.0.1:9146`. The new ordinary nonstaff clinician's login is held only in the
owner-readable `workflow-runtime-20261016/clinician-access.json`; do not paste it
into chat or logs. No existing account password was reset.

The blank Word form and saved clinical answer were explicitly seeded as fictional
fixtures. The browser then saved the clinical review, finalized the note and
reviewed coding through ordinary application actions. This is an authenticated
synthetic replay, not live Corti validation or an AI-generated clinical document.

The full existing FY2027 official ICD reference was imported into this isolated
database after verifying its retained manifest, code archive, Index and Tabular
hashes. The release covers 2026-10-01 through 2027-09-30; its 74,879-code catalog
SHA-256 is `3c0583a38ee0e848f7dc0ac8ce88e8f001bbba8c6385ed825d44d46f6e5297c9`.

## Verification and preserved evidence

Private evidence directory:
`/home/claude/quillmd-corti-test/workflow-verification-20261016/`.

- `focused-tests-final.log`: 92 tests passed, covering direct transport mocks,
  duplicate/no-resubmit behavior, patient/tenant isolation, stale decisions,
  missing evidence, unknown codes, unavailable releases, old ICD workflow,
  preserving export, original adapter and context-ID recovery.
- `browser-first/report.json`: authenticated desktop/mobile replay passed. All
  seven spans remained. R12 was accepted, K59.00 explicitly rejected and 99213
  held. Dirty selections survived polling; a stale approval returned 409.
  Original, repeated appendix and mobile Word downloads were actually obtained.
- `download-persisted-comparison.json`: downloaded appendix exactly matched the
  persisted R12 decision. Original XML prefix and all other ZIP members matched;
  one coding run, one simulated attempt, zero generation jobs and zero provider
  calls. Original and repeated downloads remained byte-identical.
- `download-layout-second/report.json`: actual downloaded Word rendered without
  clipping/overlap at wide/narrow widths, with the clinical section unchanged
  and only R12 in the appendix. **Native Microsoft Word pagination is unverified.**
  The bundled HTML renderer joins same-size sections despite the explicit
  `nextPage` in Word XML. The initial two-preview-pages assertion failure is
  retained in `download-layout-first`; no Word content was altered to hide it.
- Independent refutation found source identity and causal-symptom gaps. The
  fixes and concrete counterexamples are regression-tested; the final bounded
  refutation found no remaining issue in those confirmed cases.
- Initial test-fixture failures and subsequent corrections are retained. No
  database immutability guard was disabled to make the tests pass.

The original prediction raw hash remains
`560b4c979bf734a3b6ad6cf2aafaeadfc67226e3c5463da0959bd80181e5dc7f` and its verdict
remains `FAIL_RESPONSE_QUALITY_WITH_SELECTED_CODES_PASS`. The preservation
manifest covers 112 original evaluation/replay/discovery/agent/repair files.
Nothing in this candidate changes the original failure into a pass.

## CPT dependency and activation status

**CPT-DATED-SOURCE — unresolved.** Direct prediction selected 99213 and supplied
the defective `+PR OFFICE OUTPATIENT VISIT 15 MINUTES` display. The actual tested
Medical Coding connector supported-systems response omitted CPT. It therefore
has not supplied verified CPT lookup, applicable E/M criteria or dated-source
provenance for the 2026-10-16 encounter. A connector/software version is not a CPT
release. This does not establish that the selected code is wrong.

An authoritative CPT descriptor and E/M rule source, with release, effective
dates, attribution and verified applicability to the service date, is still
required. It may be supplied as a properly authorized local reference or an
account capability that actually returns that evidence; the optional agent
connector is not a workflow prerequisite. The raw description stays visible in
diagnostics. No replacement descriptor is hardcoded or generated as official.

Commercial CPT rights/entitlement are a separate prerequisite, enforced by the
existing licensing gate. Dashboard/native acceptance is also separate: this
candidate does not authorize real-patient use or certify all Word templates.
Native promotion still requires the normal reviewed exact-revision installation,
CI/static/installation declaration and applicable operator gates. The prior
consumed native installation packet cannot be reused for this new UI/config.
The served provider, clinical records, native services and historical Word files
remain unchanged. No purchase, billing change, vendor message or live call occurred.
