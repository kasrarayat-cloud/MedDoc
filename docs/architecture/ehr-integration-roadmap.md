# EHR Integration Roadmap

**Status:** Scoping document. No code changes ship in the same PR
as this file — concrete implementation is sequenced per the Phase
breakdown below and driven by separate engineering tracks.

**Audience:** Kasra + future Claude Code sessions evaluating which
integration shape to pursue. The doc names the
buy-vs-build decision points and the architectural seams that
either path requires.

**Last updated:** 2026-05-10.

---

## 1 · Today's posture

QuillMD currently integrates with EHRs through **doctor-mediated
copy-paste**. There is no direct API connection to any EHR.

### What exists

| Surface | Where | Shape |
|---|---|---|
| Per-EHR clipboard formatters | `apps/transcribe-md/src/lib/ehr-formatters.ts` (344 lines) | Five output flavours: `epic`, `athena`, `cerner`, `eclinicalworks`, `generic`. Each renders the SOAP + assessment + plan + prescriptions for paste into the EHR's note field. |
| Visit export (server) | `apps/transcribe-md/src/lib/visit-export-server.ts` (107 lines) | Prisma-touching loader; converts the `TranscribeVisit` row into `VisitExportData`. |
| Visit export (pure) | `apps/transcribe-md/src/lib/visit-export.ts` (141 lines) | Wire types + pure helpers for the visit data shape. Client-safe. |
| DocX generation | `apps/transcribe-md/src/lib/docx-generator.ts` (584 lines) | Server-side DocX rendering when the doctor requests a download. |
| Delivery audit log | `apps/transcribe-md/src/lib/deliveries.ts` + `VisitDelivery` Prisma model | One row per export action with channel + destination + size. |
| Channel enum | `DeliveryChannel` in `deliveries.ts` | `clipboard_epic`, `clipboard_athena`, `clipboard_cerner`, `clipboard_eclinicalworks`, `clipboard_generic`, `pdf`, `docx`, `email`. |
| DrChrono cache field | `Patient.drChronoId` in `packages/db/prisma/schema.prisma` | **Note: this is on the meddoc-pro-side `Patient` model, not the transcribe-md-side `TranscribeMdPatient`.** Indicates a prior CRM-side DrChrono integration (out of scope for this doc — meddoc-pro is decommissioned per memory + POST_MERGE_TODO §21). |

### What does NOT exist

- No FHIR client. No HL7 v2 parser/emitter. No SMART on FHIR
  app-launch handshake. No bearer-token OAuth flow against any
  EHR's developer portal.
- No structured patient lookup against an external EHR. The
  `TranscribeMdPatient` model holds patient identity local-only.
- No write-back of the finalized note as a structured document
  (FHIR `DocumentReference`, HL7 v2 MDM^T02, etc.). All exports
  today are unstructured text or DocX/PDF binary.
- No structured ICD-10 / CPT code submission to an EHR billing
  module. Codes ride along in the copy-pasted note text.
- No appointment-context awareness. The doctor selects a patient
  manually inside QuillMD; the EHR's calendar is not consulted.

### What this means strategically

QuillMD's value prop today is **AI-quality SOAP draft** + **doctor
copy-paste back into their EHR**. That model:

- Works across every EHR (because copy-paste is universal).
- Requires zero per-EHR engineering investment.
- Is friction-rich: doctor must switch context, paste, re-verify
  patient match, then sign in their EHR. The "minutes saved per
  visit" is bounded by this round-trip.
- Carries audit-log liability: the *EHR's* audit log shows the
  doctor pasting + signing; QuillMD's audit log shows the export.
  Reconciling them at audit time is non-trivial.

The roadmap below describes how to evolve from this posture into
direct EHR integration without invalidating the doctor-mediated
copy-paste path (which remains valuable as a fallback for EHRs we
never integrate with).

---

## 2 · Coupling blockers (read this before any phase below)

### B1 · Practice-tenant model is local-only

`TranscribeMdPatient` has no `externalEhrId`-shaped column. Every
patient created in QuillMD is identity-local. Direct EHR
integration requires:

- A way to *find* a patient in the EHR before writing a note (by
  MRN, name+DOB, or appointment ID).
- A persistent cross-reference once found (mirror the meddoc-pro-
  side `Patient.drChronoId` pattern — `externalSystemId`,
  `externalSystem`, `externalIdLastSyncAt`).

**Effort to unblock:** small — a Prisma migration adding three
columns + a corresponding sync helper. Per the migration
workflow memory note, use `migrate diff` + hand-write folder +
`db-migrate` profile (since `migrate dev` is blocked by the
`t_m24_smart_inject` checksum drift).

### B2 · No OAuth / credential storage

QuillMD currently authenticates only end-users (Auth.js / NextAuth).
EHR integration adds **per-practice credentials** to external
systems — long-lived OAuth refresh tokens, system-account API keys
for the integration broker (if buying via Redox/Particle), or PKI
client certificates (Epic enterprise).

**Effort to unblock:** medium — needs a secure-credential store +
rotation policy + role gating (only practice admins can connect).
The existing `secrets/` host-only encryption pattern is per-VPS;
practice-tenant secrets need to be per-row in Postgres with
field-level encryption (libsodium / KMS-backed).

### B3 · Audit-log model assumes single-system visibility

`AuditLog` currently records actions inside QuillMD only. EHR
integration spawns a class of actions where QuillMD initiates an
external write (note posted, code submitted, prescription queued).
The schema needs:

- `externalSystem` discriminator on `AuditLog`.
- `externalActionId` to track the external system's transaction
  ID (so we can correlate the doctor's "I signed in Epic" with our
  own "we wrote to Epic at T-2 minutes").

**Effort to unblock:** small once B1 is in (same migration shape).

### B4 · Visit-mode field doesn't tag the EHR-bound flow

`TranscribeVisit.inputMode` is `audio_conversation` or
`voice_dictation`. There's no field that says "this visit will be
written back to an EHR vs exported standalone." The integration
flow needs to know **before** the worker runs whether to attach
EHR-context (appointment ID, patient MRN, EHR-specific codeset
preferences) to the SOAP draft.

**Effort to unblock:** small — additive Prisma column +
worker-side branching.

---

## 3 · Priority systems (the four EHRs that move the needle)

| EHR | Market share (US ambulatory) | Integration shape | Direct API maturity | SMART on FHIR | Broker support |
|---|---|---|---|---|---|
| **Epic** | ~36% | Direct via App Orchard / connection.epic.com OR via brokers | Mature (FHIR R4) | Full | Redox / Particle / Health Gorilla |
| **Cerner / Oracle Health** | ~24% | Direct via code.cerner.com OR brokers | Mature (FHIR R4 + DSTU2 legacy) | Full | Redox / Particle / Health Gorilla |
| **Athena Health** | ~10% (cloud-native; popular with small practices — overrepresented in QuillMD's pilot demographic) | Direct via developer.athenahealth.com OR brokers | Mature (REST + FHIR) | Partial | Redox / Particle |
| **eClinicalWorks** | ~8% (heavy in the SMB/independent-practice market) | Mostly via brokers; direct API is gated | Limited direct (FHIR R4 read-only on free tier) | Partial | Redox / Particle / Health Gorilla |

The pilot's specialty mix (urgent care, family medicine, internal
medicine) skews toward Athena + eClinicalWorks. Targeting one of
those first is more pilot-relevant than starting with Epic, even
though Epic has the largest market share overall.

**Recommendation:** start with **Athena** (smallest dev portal
friction + most pilot-relevant) OR with a **broker (Redox)** that
covers all four targets at once. The buy-vs-build decision below
collapses to this choice.

---

## 4 · Three integration approaches (the buy-vs-build decision)

### Path A · Direct API per EHR

**What it is.** QuillMD's worker writes directly to each EHR's
public API. One client per EHR (`packages/ai/src/ehr/epic.ts`,
`packages/ai/src/ehr/athena.ts`, …); each implements the EHR's
specific OAuth + endpoint + retry semantics.

**Pros:**

- No per-message broker fee (significant at scale).
- Direct visibility into the EHR's response codes / errors.
- Tightest control over latency + retry.
- Possible to ship first integration in 4-6 weeks (Athena dev
  portal is fast).

**Cons:**

- N integrations = N maintenance tracks. Each EHR has its own
  versioning cadence, deprecation surprises, and undocumented
  quirks.
- Onboarding into Epic / Cerner App Orchard requires security
  review + customer-validated reference deployments. The
  certification path can take 6-12 months wall-clock for Epic.
- Per-practice OAuth rotation logic must be built per EHR.
- BAA negotiation per EHR (Epic + Cerner have standard terms;
  Athena + eCW require legal review).

### Path B · SMART on FHIR (app launch)

**What it is.** QuillMD is launched **from inside** the EHR as a
SMART-on-FHIR-compliant embedded app. The doctor clicks a button
in their Epic / Cerner / Athena chart; QuillMD opens with the
patient + appointment context already attached via SMART's
launch-token handshake. QuillMD writes the finalized note back via
the FHIR `DocumentReference` resource.

**Pros:**

- Single integration shape across every SMART-compliant EHR (Epic,
  Cerner, Athena, plus dozens of smaller systems).
- The launch-token mechanism eliminates patient-match friction
  (the EHR pre-resolves who the visit is for).
- Already a well-understood pattern; FHIR is mature; many open-
  source SMART client libraries (`@asymmetrik/node-fhir-server-core`,
  `fhirclient/client-js`).
- Audit story is cleaner: the EHR's launch event is a real audit
  row in their system; our write-back is a real FHIR resource.

**Cons:**

- The doctor must launch QuillMD *from inside the EHR*. This
  changes the product's UX model — today QuillMD is a standalone
  app the doctor opens directly. SMART works best as an *embedded*
  experience.
- App-launch certification still required per EHR for production
  rollout (Epic App Orchard, Cerner code.cerner.com app
  publishing). The SMART standard reduces but does not eliminate
  per-EHR certification.
- FHIR `DocumentReference` is for *attaching* a note. Structured
  ICD-10 / CPT submission still requires per-EHR work
  (`Composition`, `Claim`, custom extensions).
- eClinicalWorks SMART support is partial — some pilot users may
  not be reachable via SMART for another year.

### Path C · Broker (Redox / Particle Health / Health Gorilla)

**What it is.** QuillMD integrates with one broker. The broker
fans out to every EHR via their pre-built connectors. QuillMD
sends a single canonical message ("write this note for patient
X at practice Y"); the broker translates to the destination EHR's
native API.

**Pros:**

- One integration replaces 4+ direct integrations. Massive
  reduction in initial engineering + ongoing maintenance.
- Brokers handle EHR-specific quirks (Athena's odd note-attach
  endpoint, Cerner's MDM message format, Epic's auth refresh).
- BAA scope shrinks: one BAA with the broker, not N BAAs with
  every EHR.
- Brokers ship sandbox + test credentials immediately — first
  successful round-trip can happen in days, not weeks.
- Most brokers also handle inbound (read appointments / patient
  lookup) on the same connection, solving the patient-match
  problem.

**Cons:**

- Per-message fee (typically $0.10-$0.50 per write or read). At
  pilot scale negligible; at 1000-doctor scale this stacks.
- The broker becomes a single point of failure + a third party
  in the data path. Redox went through a multi-day outage in 2025
  that affected hundreds of vendors; an outage means QuillMD's
  write-back queues backlog.
- Less control over edge cases. When a write fails, the broker's
  error message may abstract over the real EHR error in unhelpful
  ways.
- Onboarding into the broker still requires per-customer enabling
  (the broker handles auth but the *practice* still needs to
  authorize QuillMD via the broker's auth flow).

### Recommendation

**Start with Path C (Redox or Particle) for the pilot expansion.**
Reasons:

1. Pilot growth is bounded; per-message fees won't dominate cost.
2. The pilot user mix spans Athena + eCW + sometimes Epic. Path A
   would force three concurrent integration tracks; Path C
   collapses them.
3. Path C does not preclude Path A or Path B later. Once one EHR
   reaches >40% of the broker volume, replacing that one EHR with
   a direct integration is incremental — the canonical message
   shape inside QuillMD (B-side abstraction) stays unchanged.
4. The broker's BAA + their established compliance posture
   shortens QuillMD's compliance review for the integration.

**Defer Path B (SMART on FHIR) until pilot validates the embedded-
launch UX is what doctors actually want.** Today QuillMD is a
"open the app, click record" workflow; SMART rewires that to
"open the EHR, click QuillMD." Both are valid; SMART is
strategically more powerful but operationally more disruptive.
Validate user demand before committing to it.

**Defer Path A direct integrations until either the broker fee
becomes material (>$5K/mo) or until a single EHR concentrates
>40% of traffic.** Both are well-defined trigger points.

---

## 5 · Phased plan

### Phase 1 — Schema + identity hooks (1-2 PRs, 1-2 weeks)

**What:** unblock B1 + B3 + B4 from §2.

- Add `TranscribeMdPatient.externalSystem`,
  `TranscribeMdPatient.externalSystemId`,
  `TranscribeMdPatient.externalIdLastSyncAt` (nullable; mirrors
  the meddoc-pro `Patient.drChronoId` shape).
- Add `AuditLog.externalSystem`, `AuditLog.externalActionId`
  (nullable; populated only for EHR-action audit rows).
- Add `TranscribeVisit.deliveryTarget` enum (`'standalone' |
  'ehr_writeback'` — defaults `'standalone'`; doctor selects on
  upload page when an EHR is connected).
- Migration via `migrate diff` + hand-write folder + `db-migrate`
  profile.

**Out of scope for Phase 1:** the actual integration. Phase 1 is
purely schema-prep so that no future PR has to land schema +
integration + UI in the same blast radius.

### Phase 2 — Broker selection + sandbox round-trip (1-2 weeks)

**What:** pick Redox or Particle Health; get a successful "write
test note for test patient" round-trip in their sandbox.

- Sign sandbox BAA + get sandbox credentials.
- Build a `packages/ai/src/ehr/broker-client.ts` with the broker's
  canonical write-note shape.
- One end-to-end test: synthetic visit → broker sandbox →
  inspect mock EHR's note field.
- Document the connector's auth model (system account vs
  per-practice OAuth) in
  `docs/architecture/ehr-broker-credentials.md`.

**Decision gate at Phase 2 end:** ship in pilot, or move to Path A
direct? Decision criteria: latency p95 (broker sandbox vs realistic
target), sandbox API ergonomics, sandbox BAA terms vs production
BAA terms.

### Phase 3 — Production credentials + first practice (2-3 weeks)

**What:** wire one real practice's real EHR to QuillMD via the
broker. Pilot rollout.

- Production BAA signed with broker.
- Per-practice credential storage (Postgres + libsodium
  encryption).
- Practice-admin UI for "Connect your EHR" (broker handles the
  per-practice OAuth handshake).
- Worker-side: when `TranscribeVisit.deliveryTarget = 'ehr_writeback'`,
  fire broker write at end of pipeline. Audit-log the result with
  the broker's external-action ID.
- Rollback path: any broker write failure falls back to clipboard
  export (no doctor user-facing degradation).

**Decision gate at Phase 3 end:** does pilot adoption justify
expanding to second EHR via broker, or pivot to direct?

### Phase 4 — Code-level write-back (4-6 weeks)

**What:** structured ICD-10 / CPT submission alongside the note.

- The note text itself ships in Phase 3. Structured codes (FHIR
  `Composition` with coded sections, or HL7 v2 DFT for billing)
  ship here.
- Per-EHR codeset preference (some EHRs reject ICD-10-CM with
  certain billable-status flags; codes need EHR-specific
  filtering).
- Reconciliation: when the EHR rejects a code, the doctor sees
  the rejection in QuillMD's review pane.

**Decision gate at Phase 4 end:** SMART on FHIR for embedded
launch, or stay standalone?

### Phase 5 — SMART on FHIR (only if Phase 4 validates demand)

**What:** doctor launches QuillMD from inside their EHR's chart.

- Implement SMART app-launch handshake (PKCE OAuth + launch-token
  pickup).
- Receive patient + appointment context from EHR; pre-resolve
  patient match.
- Embed visit-recording UI in iframe-ready layout (no full-page
  redirects that would lose the launch-token).
- Submit to Epic App Orchard / Cerner / Athena / eCW for
  certification + production publishing.

This is months of work + per-EHR certification cycles. Defer
until §3's pilot data validates the UX direction.

---

## 6 · What to build in-house vs buy

| Component | Build vs buy | Why |
|---|---|---|
| Per-EHR clipboard formatters (existing) | **Keep building** | Fallback path remains valuable forever. Doctors with EHRs we don't integrate get value. |
| Broker client (Phase 2-3) | **Buy** (Redox / Particle / Health Gorilla) | Already covered above; not strategically differentiating. |
| Direct EHR clients (post-§4 Decision) | **Build only when broker fees concentrate** | Per the trigger points in Path A. |
| FHIR resource shapes (Phase 4-5) | **Use library** (`@asymmetrik/node-fhir-server-core` or `fhirclient/client-js`) | FHIR is mature; rolling our own resource validators is not strategically differentiating. |
| OAuth credential storage | **Build (Postgres + libsodium)** | Per-practice secret rotation is QuillMD-specific tenant logic; not buyable. |
| Audit-log reconciliation between QuillMD and EHR | **Build** | This is a HIPAA-compliance differentiation; the schema + verification flow is tenant-specific. |

---

## 7 · Open questions (Kasra to resolve)

1. **Pilot vs production**. Is the goal in 2026-Q3 to onboard
   non-pilot practices via this integration, or just to make the
   pilot itself stickier? The answer changes Phase 2's broker
   choice (Redox is the default for pilot; Health Gorilla is
   stronger for at-scale Epic).
2. **Does QuillMD want to be an Epic App Orchard listed app?**
   The certification cost is high but the channel is real
   (a publicly-listed Epic app is a credibility marker). Alternative:
   stay broker-mediated, never Epic-listed, accept the
   credibility ceiling.
3. **What happens to the existing `Patient.drChronoId` integration
   on the meddoc-pro side?** Per memory + POST_MERGE_TODO §21,
   meddoc-pro is decommissioned. The DrChrono code there is dead
   weight. This roadmap assumes we delete that and start fresh on
   the transcribe-md side; confirm before Phase 1 PR opens.
4. **BAA portfolio scope.** The current `BAA_CHECKLIST.md` covers
   AI-pipeline vendors (Anthropic, Deepgram, Resend, MinIO).
   Adding broker + EHR(s) materially expands the BAA surface.
   Is there a compliance-counsel review process budgeted for
   that?

These are not scoping questions for this doc — they are
strategic-direction questions whose answers shape the Phase 2
and Phase 3 plans.

---

## 8 · Reference

- Existing per-EHR clipboard formatters:
  `apps/transcribe-md/src/lib/ehr-formatters.ts`.
- Existing visit export (server + pure):
  `apps/transcribe-md/src/lib/visit-export-server.ts`,
  `apps/transcribe-md/src/lib/visit-export.ts`.
- Existing delivery audit log:
  `apps/transcribe-md/src/lib/deliveries.ts` +
  `VisitDelivery` Prisma model.
- Existing patient model with DrChrono cache (out of roadmap
  scope — meddoc-pro side):
  `packages/db/prisma/schema.prisma` `model Patient`.
- BAA checklist: `docs/BAA_CHECKLIST.md`.
- Broker docs:
  - Redox: https://www.redoxengine.com/developers/
  - Particle Health: https://www.particlehealth.com/developers
  - Health Gorilla: https://developer.healthgorilla.com/
- SMART on FHIR spec: https://docs.smarthealthit.org/
- Epic App Orchard: https://apporchard.epic.com/
- Cerner code: https://code.cerner.com/
- Athena Health developer portal:
  https://developer.athenahealth.com/
