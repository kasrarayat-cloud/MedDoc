# Template Twin staging UI v1

## Scope and release posture

This slice integrates Template Twin into the authenticated QuillMD product as
a default-off, synthetic-only staging workflow. It does not authorize patient
care, real PHI, production enablement, or Microsoft Word compatibility. The
existing compiler, certification, worker, storage, verifier, review, signing,
and export contracts remain authoritative.

The staging workflow is admitted only when all of these server-side conditions
hold:

1. `TEMPLATE_TWIN_STAGING_QA_ENABLED` is exactly `true`.
2. no explicit deployment profile identifies production;
3. the database is recognizably disposable QA/test/synthetic infrastructure;
4. the exact `isolated-disposable-qa-v1` resource attestation is present;
5. Redis uses a positively identified QA/local host and dedicated non-zero
   logical database;
6. both MinIO buckets are QA/test/synthetic-named, distinct, and reached only
   through a local endpoint or an explicitly TLS-protected QA endpoint;
7. the existing Template Twin environment kill switch permits use;
8. the practice rollout flag and persisted rollout generations permit use;
9. the caller is a current tenant member with the required physician role; and
10. the source bytes match the versioned allowlisted synthetic fixture.

Normal visits never inherit synthetic provider behavior. A durable,
tenant-scoped staging-run row is the only admission marker, and the worker
enters a request-local synthetic provider context only after validating it.
The literal resource attestation value is a required operator assertion, not
standalone proof: the server independently checks the environment profile,
database name, Redis host and non-zero logical database, distinct bucket
names, storage profile, endpoint locality/TLS, provider-fixture enablement,
and the exact allowlisted source bytes before admitting a run.

### Synthetic-only process fence

Explicitly requesting the staging-QA profile changes the process admission
boundary, not merely the visible UI. While that profile is requested, the
generic Template Twin DOCX upload, generic template lifecycle mutations,
generic worker admission, and generic static-asset review or approval workflow
are unavailable. The process accepts only the exact byte-and-size allowlisted
synthetic DOCX and only worker work backed by its tenant-scoped durable staging
run. A missing, stale, cross-tenant, or non-matching run fails closed; it cannot
fall through to the generic worker or provider path.

This fence is staging-specific. When the staging-QA flag is absent, existing
production generic Template Twin behavior is preserved and remains governed by
its ordinary rollout, authorization, clinical-safety, privacy, and storage
gates.

## Product reference lock

The implementation follows QuillMD's existing Calm Clinical surfaces:

- the settings section shell and its preserved navigation state;
- the Note Format manager's lineage and lifecycle controls;
- the existing Template Twin field queue, intent editor, unsupported register,
  evidence test, waiver, and certification gates;
- the visit review tabs and Template Twin evidence review;
- the static-asset review pattern of inspection, evidence, attestation, and
  explicit decision; and
- the established typography, status colors, focus rings, buttons, 44-pixel
  touch targets, and reduced-motion behavior in `globals.css`.

No new visual language, marketing surface, or parallel template product is
introduced.

## Guided physician journey

1. **Inspect structure** — show package, privacy, media, and structural
   inspection outcomes plus the complete field and blocker inventory.
2. **Confirm intent** — show one field at a time with a stable identity, visible
   context, mapping, type, requiredness, and gate. No ambiguous intent is
   preselected.
3. **Exercise synthetic cases** — require field-level synthetic evidence or an
   audited optional waiver using the existing certification contract.
4. **Run staging QA** — create an idempotent typed or mocked-voice staging run
   through PostgreSQL, BullMQ, the worker, object storage, the exact renderer,
   and verification-contract-v2.
5. **Review evidence** — display resolved, unresolved, conflicting,
   intentionally static, and blocked fields with source-fact anchors.
6. **Sign and download** — preserve every existing server-side signing gate,
   then make the verified Original Template DOCX the primary download.

A permanent `SYNTHETIC TEST ONLY — NOT FOR PATIENT CARE` warning appears on
every staging-specific surface. Microsoft Word is always reported as
`PENDING`; LibreOffice or package checks never upgrade that status.

## Interaction decisions

- Field selection is navigation, not an ARIA listbox. Native buttons provide
  keyboard activation, and the selected detail heading receives focus.
- Important blockers are visible text linked to the relevant field; they do not
  exist only in a tooltip or color.
- Physician language is shown by default. OOXML paths, hashes, versions, and
  audit delivery state live in a collapsed technical-details section.
- On narrow screens the field queue and detail panel stack. Forms retain
  16-pixel inputs and actions retain 44-pixel targets.
- Status updates use polite live regions; errors use an assertive alert and
  preserve the physician's entered work.
- Retry uses the durable staging-run identity. Double submission cannot create
  a second visit, queue job, or claimed object.

## Protected contracts

- Strict pre-delivery verification-contract-v2 remains the signing proof.
- Stored bytes are reread and hashed at signing and download.
- SOAP version/hash and rollout generation must match the immutable manifest.
- Office-resaved files never become signing inputs.
- Unsupported concepts and structures remain certification-blocking.
- The real WM IOV placeholder decisions and media remain unresolved.
- Critical audit events use the existing transactional outbox.
- Rejected objects remain in the object-ledger reconciliation path.

State-changing staging transactions use one lock order whenever the named row
exists for that operation: global rollout control, owning practice, durable
staging run, current actor, visit, then fill manifest or output claim. In
compact form this is
`global -> practice -> run -> actor -> visit -> fill/output`. An admission,
retry, worker claim, correction, READY claim, signing claim, and download
authorization may omit rows that do not apply, but may not reverse the
relative order of the rows it does lock. The actor row is re-read under lock
so a removed, disabled, cross-practice, or no-longer-DOCTOR account cannot
finish work admitted under an earlier authorization snapshot. Rollout disable
uses the same global then practice prefix; transaction commit is the
linearization point.

## Rollback

The staging gate defaults off. Disabling the environment gate or either rollout
gate removes admission immediately; persisted rollout-generation checks stop
stale final claims. The additive staging-run table can remain dormant during a
rollback. Existing non-Template-Twin visits and generic export behavior do not
depend on it.

The previously observed Windows CMD/Word COM launcher hang is a separate
human-QA tooling defect. It is not diagnosed or fixed by this staging browser
slice, the browser does not invoke that launcher, and no launcher result is
counted as an Office or Microsoft Word pass here.

Staging deployment remains blocked until a fresh independent audit accepts the
exact remediation head. Any later environment must also prove network-level
outbound-provider denial, private authenticated access with public registration
disabled, and separately provisioned synthetic ADMIN and DOCTOR identities.
