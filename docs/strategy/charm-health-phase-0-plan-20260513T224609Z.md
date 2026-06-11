# Charm Health — Phase 0 Implementation Plan

**Date:** 2026-05-13 22:46 UTC
**Author:** Claude (Opus 4.7 1M)
**Companion:** `charm-health-deepdive-20260513T224609Z.md` (load that first if you haven't)

**Scope:** `apps/transcribe-md` only. DrChrono is out of scope (was tied to deprecated meddoc-pro). All Charm reasoning below assumes single-VPS deploy + existing audit-log + queue infrastructure from prior PRs.

**No implementation yet.** This is the architectural commitment + milestone shape; engineering begins next session once Kasra has a Charm Health dev account.

---

## 0. Headline Findings From the Deep-Dive

Three findings shape every architecture choice below:

1. **Charm has BOTH SMART-on-FHIR (read) AND a proprietary REST API (write).** They are SEPARATE endpoints with SEPARATE OAuth scopes at SEPARATE hosts. **FHIR is read-only.** SOAP write-back goes through the proprietary REST API.

2. **CPT code write is undocumented.** ICD-10 push works (`POST /patients/{id}/diagnoses`). SOAP push works. Rx push works as a chart entry. **But there is no public CPT-write endpoint** — procedures are GET-only and billing/coding flows live behind Charm's RCM module. **This is the single most important question to resolve with Charm BD before committing the $1,000 sandbox spend.**

3. **API-driven sign + lock works** (`POST /patients/{id}/encounters/{eid}/sign`). This is rare — most EHRs require the doctor's UI session to finalize. QuillMD inheriting this capability is a measurable UX win over competitors.

---

## A. Connection Model

### A.1 — Per-practice OAuth grant

Charm's authorization model is **practice-level** by default:
- Practice admin enables QuillMD in Charm at Settings → Account → API Keys
- Charm issues a `client_id` + `client_secret` scoped to that practice's tenant
- QuillMD's server holds the refresh token; access tokens are 1-hour
- All API calls (read OR write) happen against the same practice context

**Per-doctor scoping is NOT first-class.** Multiple doctors in the same practice share the same OAuth grant; the audit trail must distinguish them via QuillMD's own user identity (which IS already tied to the visit in our schema via `transcribe_visits.userId`).

### A.2 — Two OAuth client registrations

The hybrid architecture needs TWO OAuth registrations per practice:

| Registration | Purpose | Scopes | Token lifetime |
|---|---|---|---|
| **SMART on FHIR client** | EHR-launch context pickup; pre-visit chart read | `user/Patient.rs`, `user/Encounter.rs`, `user/Condition.rs`, `user/MedicationStatement.rs`, `user/AllergyIntolerance.rs`, `user/Observation.rs`, `launch`, `openid`, `fhirUser`, `offline_access` | Per-launch (1h access) |
| **REST API client** | All writes (SOAP, ICD-10, sign action), some reads | Charm proprietary scopes (e.g., `charmhealth.patient.demographics.READ`, `charmhealth.encounters.UPDATE`) | 1h access; refresh stored server-side |

**Practical wiring:** Both clients are registered through the same Charm API Program form, with separate `client_id`s. Practice admin grants both in one consent flow per QuillMD's own onboarding UX.

### A.3 — Token storage

Reuse the existing `auth_tokens` table convention but add a new model for vendor tokens:

```
EhrIntegrationToken {
  id           cuid()
  practiceId   String   (FK → Practice)
  vendor       String   ("charm")
  scope        String   ("smart-fhir" | "rest-api")
  accessToken  String   (encrypted at app layer; LUKS handles disk)
  refreshToken String   (encrypted)
  expiresAt    DateTime
  scopes       String[] (granted scopes for auditing)
  createdAt    DateTime
  updatedAt    DateTime
  UNIQUE(practiceId, vendor, scope)
}
```

Tokens encrypted at the application layer (libsodium / `crypto.subtle`) since LUKS protects the disk but not the running process. Encryption key from `EHR_TOKEN_ENCRYPTION_KEY` env var.

### A.4 — Self-serve activation vs admin-call-Charm

Activation flow per practice:
1. Doctor (or practice admin) signs into QuillMD
2. QuillMD shows "Connect to Charm Health" CTA
3. CTA routes to Charm's OAuth authorize endpoint for both SMART and REST clients (sequential consent, OR consolidated if Charm supports it — verify)
4. Practice admin must additionally enable the integration in their Charm Settings → API Keys (Charm-side gate)
5. QuillMD persists tokens, confirms the loop with a `GET /patients?limit=1` test call, surfaces connection-OK status

The Charm-side gate is the friction point. Build a clear in-app checklist that walks the practice admin through both QuillMD's OAuth flow AND Charm's in-EHR enablement.

---

## B. Data Flow

### B.1 — Visit lifecycle

The QuillMD → Charm push is **one-way for the Phase-0 milestone** (QuillMD writes; Charm doesn't push events back yet — webhooks are Phase 1.1).

```
[Doctor opens Charm UI]
  ↓
[Doctor launches QuillMD via SMART app launch button in Charm]
  ↓ SMART hands us {patient_id, encounter_id, user_id, access_token}
[QuillMD opens with patient context pre-loaded]
  ↓
[QuillMD reads chart context via FHIR R4: problem list + meds + allergies + vitals]
  ↓
[Doctor records visit; QuillMD pipeline runs: L1 transcribe → L4 SOAP → L7 codes/Rx]
  ↓
[Doctor reviews + signs SOAP in QuillMD]
  ↓ (PUSH BEGINS)
[QuillMD → Charm REST: POST /soap/encounters/{eid} with chief_complaints + entries[]]
[QuillMD → Charm REST: POST /patients/{id}/diagnoses for each ICD-10 (with encounter_id)]
[QuillMD → Charm REST: POST /patients/{id}/medications for each Rx (as draft)]
[QuillMD → Charm REST: POST /patients/{id}/encounters/{eid}/sign]
  ↓
[Doctor's Charm UI now shows the signed SOAP + diagnoses + Rx drafts]
[Doctor completes Rx Sign & Send in Charm's UI for SureScripts transmission]
```

### B.2 — Patient sync model

**One-way pull on demand, NOT shadow sync.**

- When doctor launches QuillMD from a Charm encounter, QuillMD reads patient + encounter context FRESH from Charm via FHIR R4.
- QuillMD's `TranscribeMdPatient` row stores `charm_patient_id` as a foreign reference but **doesn't try to mirror demographics**.
- Each visit's `TranscribeVisit` row stores `charm_encounter_id`.

**Why not shadow:**
- Multi-tenant complexity (one Charm patient could exist in multiple Charm tenants if the same patient sees multiple providers; QuillMD shouldn't try to deduplicate across)
- Demographics-drift conflicts (Charm is source of truth; mirroring invites stale-data bugs)
- Single-VPS scale doesn't justify the storage + sync overhead

**Schema additions:**

```
TranscribeMdPatient {
  ... existing fields ...
  charmPatientId String?  @unique([practiceId, charmPatientId])
  charmLastSyncedAt DateTime?
}

TranscribeVisit {
  ... existing fields ...
  charmEncounterId String?  @unique
  charmPushStatus  String?  ("pending" | "succeeded" | "failed" | null)
  charmPushAttempts Int      @default(0)
  charmLastPushAt  DateTime?
  charmLastPushError String?
}
```

### B.3 — Coding push timing

Per the QuillMD pipeline today (L7a ICD-10, L7b CPT, L7c Rx):

- **ICD-10**: pushed at `Encounter.Sign` time as `POST /patients/{id}/diagnoses` with `encounter_id` attached. Each ICD-10 becomes a Charm diagnosis row tied to the encounter.
- **CPT**: ⚠ **deferred until Charm BD confirms write endpoint exists.** If yes → push at sign time. If no → Phase 0 ships without CPT push; QuillMD continues to display CPT in its own UI but doesn't push to Charm. The doctor enters CPTs manually in Charm's billing module.
- **Rx**: pushed at sign time as `POST /patients/{id}/medications` (chart entry only — no SureScripts transmission). Marked "draft from QuillMD" via metadata so the doctor knows to review + send via Charm UI.

### B.4 — Rx workflow caveat

Charm's e-Rx Sign-and-Send + EPCS workflow requires the clinician's UI session (and 2FA for EPCS). The MCP server does NOT expose a "send Rx" action.

**Phase 0 Rx UX:**
- QuillMD displays the Rx draft as it does today (warning modal, severity gates from PR-D safety pack)
- On encounter sign, push Rx to Charm chart medications as "QuillMD-drafted, not transmitted"
- Doctor sees the Rx in Charm's medication module after the visit and completes SureScripts transmission via Charm's native Sign & Send button

**This is the degrade-from-frictionless point.** Sales positioning should be: "QuillMD drafts the Rx + ICD-10 + signed note — you finalize the e-prescription in Charm with your existing workflow."

### B.5 — Direction

**One-way from QuillMD → Charm for Phase 0.** No webhook subscription, no Charm → QuillMD reverse-sync. This keeps Phase 0 scope minimal.

Phase 1.1 (post-MVP) adds the `Encounter.Sign` + `Encounter.Unlock` webhook subscription so QuillMD knows if a doctor modifies the SOAP in Charm after we pushed it (audit-log correlation).

---

## C. Failure Modes

### C.1 — Charm is down mid-visit

| Failure | QuillMD behavior |
|---|---|
| **SMART launch fails** (Charm unreachable when doctor clicks app) | Fall back to standalone QuillMD launch; doctor picks patient via QuillMD's own picker (existing flow). No data lost. |
| **FHIR read for pre-visit context fails** | Show degraded "couldn't load chart context — recording will proceed without it" banner. Doctor's visit recording continues. The post-visit push still happens. |
| **REST write for SOAP/diagnoses fails after sign** | Mark `charmPushStatus = 'failed'`, queue for retry. Existing T-M16.4 retry infrastructure handles this. Show admin notification at /admin/charm-integration. **Critically: the doctor's sign in QuillMD is still valid** — the visit is signed in QuillMD's system of record regardless of Charm push status. |
| **Charm hits 429 rate limit** | Exponential backoff (1s → 2s → 4s → 8s → 16s, max 5 retries). Honor any `Retry-After` header if Charm sends one. |

### C.2 — Push fails after SOAP is signed in QuillMD

**This is the load-bearing failure mode.** QuillMD must not silently drop a push.

**Strategy:**
1. After QuillMD-side sign, enqueue a BullMQ `process_charm_push` job
2. Worker attempts each write in order: SOAP → diagnoses → medications → sign
3. On any failure, marks `charmPushStatus = 'failed'` with last-error redacted via existing `redactPhi` helper
4. Job retries with exponential backoff up to 5 attempts over ~30 min
5. If all retries exhausted, emit `VISIT_CHARM_PUSH_FAILED` audit row + alert via existing /admin/queues UI
6. Doctor sees a "Charm push pending" banner in QuillMD's visit view; clicking shows the error + manual retry button

**Reconciliation:**
- If a push partially succeeded (SOAP saved but sign failed), the next retry must check Charm state via `GET /soap/encounters/{eid}` before re-pushing — content-hash dedupe.
- If Charm shows the encounter already signed but QuillMD shows `failed`, the worker reconciles: marks status `succeeded`, no double-push.

### C.3 — Retry strategy + reconciliation

**Idempotency is the open problem** — Charm doesn't document an `Idempotency-Key` header. Our defense:

1. **Pre-write check:** before each retry, `GET` the target resource to see if our previous attempt succeeded server-side
2. **Content hashing:** store SHA-256 of payload in QuillMD; if Charm shows a resource with matching hash already attached to the encounter, skip
3. **Deterministic correlation:** every write carries QuillMD's `visitId` + `userId` + `attemptIdx` in a metadata field so audit traces are unambiguous

This is more complex than ideal but unavoidable until Charm confirms idempotency support.

### C.4 — Audit log split

Three audit surfaces involved:
- **QuillMD's `audit_logs` table** (DB-level REVOKE-locked per security audit) — primary record of QuillMD-side actions
- **Charm's internal audit trail** — Drummond-certified; visible to practice admins in Charm UI; no public API to query
- **External BAA-compliance records** — not in code; lives in QuillMD's BAA paperwork with Charm

QuillMD writes a new audit action per Charm interaction:

| Action | When emitted |
|---|---|
| `EHR_PUSH_INITIATED` | Worker starts a push attempt |
| `EHR_PUSH_SUCCEEDED` | All resources pushed + sign action succeeded |
| `EHR_PUSH_FAILED` | All retries exhausted |
| `EHR_PUSH_PARTIAL` | Some resources pushed, some failed; left in inconsistent state |
| `EHR_CONNECTION_GRANTED` | Practice admin completes OAuth grant |
| `EHR_CONNECTION_REVOKED` | Token refresh fails repeatedly OR practice admin revokes in Charm |

PHI scrub posture from PRs #240 + #242 applies — only resource counts + status codes in metadata; no SOAP text, no diagnoses content.

---

## D. Pricing Surface

### D.1 — Per-API-call cost

Charm charges via the API Program: **$1,000 one-time sandbox init + $250/yr/module** (community-reported; verify in writing). No documented per-call charge.

**For QuillMD's economic model:**
- Today: $0.31-$0.43/visit AI/audio cost
- Charm integration adds: zero per-call cost, but ~$250-$2,500/yr platform cost depending on modules
- At 100 visits/practice/mo (≈1,200/yr): per-visit Charm cost ≈ $0.21 (if $250/yr) or ≈$2.10 (if $2,500/yr / 10 modules)

**Module estimate for QuillMD's flow:**

| Module | Required for | Estimated cost |
|---|---|---|
| Patients | Demographics read + ICD-10 push + Rx push | $250/yr |
| Encounters | SOAP push + sign action | $250/yr |
| Scheduling | Appointment context | $250/yr |
| Labs (optional) | Lab catalog/result read | $250/yr |

Conservative: **~$1,000/yr per practice** ($250 × 4 modules). Acceptable at typical $99-$249 PMPM doctor pricing.

### D.2 — Interaction with QuillMD's per-visit cost

Per-visit costs don't change (no Charm per-call charge). Per-practice fixed cost goes up by ~$1,000/yr. At 100 visits/practice/mo, the fixed cost amortizes to ~$0.83/visit — a 2.7x increase on the audio-AI marginal cost, but a sublinear hit on the price the doctor pays.

**Pricing recommendation for QuillMD's Charm-integrated tier:** absorb the $250/module floor as part of QuillMD's pricing; do NOT pass-through bill the doctor.

---

## E. Phase-0 Milestone Breakdown

### M0.1 — Auth + connection (XS scope)

**Deliverable:** practice admin connects QuillMD to their Charm tenant; QuillMD's `GET /patients?limit=1` test call succeeds.

**Smallest unit of work:**
- OAuth client registration (both SMART + REST) via Charm API Program form (Kasra-blocking)
- Sandbox provisioning + initial smoke test from QuillMD against `sandbox3.charmtracker.com`
- New `EhrIntegrationToken` schema + Prisma migration
- New `/api/ehr/charm/connect` route — initiates OAuth flow
- New `/api/ehr/charm/callback` route — exchanges code for tokens, persists
- Token refresh background job (cron every 50 min)
- Connection-test endpoint: `GET /api/ehr/charm/health`

**Dependencies:**
- Charm dev account + API agreement signed (Kasra blocker)
- BAA signed (Kasra blocker)
- $1,000 sandbox init paid (Kasra blocker — see Section F)

**Can parallelize:** schema + UI flow can be drafted ahead of Charm account; final wire-up gated on Charm credentials.

### M0.2 — Patient sync / one-way pull (S scope)

**Deliverable:** when QuillMD app is launched from a Charm encounter (or via standalone patient picker), QuillMD pulls Charm patient demographics + creates-or-updates the `TranscribeMdPatient` row.

**Smallest unit of work:**
- FHIR R4 `Patient` reader in `apps/transcribe-md/src/lib/charm/patient.ts`
- `charmPatientId` + `charmLastSyncedAt` schema fields
- Match-or-create logic: if `charmPatientId` already exists in QuillMD → update demographics; if not → create new TranscribeMdPatient row tied to it
- Practice picker → patient picker flow respects `charmPatientId`
- Visit-creation flow accepts `charmEncounterId` as an optional parameter (SMART launch sets it; standalone may not)

**Dependencies:** M0.1 (need tokens)

**Can parallelize:** UI work parallel to FHIR client; final integration test gated on M0.1.

### M0.3 — Visit creation hook (S scope)

**Deliverable:** when QuillMD creates a visit, if it was launched from a Charm context (encounter_id present), QuillMD stores `charm_encounter_id` on the `TranscribeVisit` row.

**Smallest unit of work:**
- Schema: `charmEncounterId` field on `TranscribeVisit`
- Visit-creation server action accepts `charmEncounterId` from SMART launch params
- Visit-view UI shows "Linked to Charm encounter #X" badge

**Dependencies:** M0.2

**Can parallelize:** schema parallel to UI badge.

### M0.4 — SOAP note push (M scope) — load-bearing

**Deliverable:** after doctor signs SOAP in QuillMD, push to Charm encounter with discrete S/O/A/P sections + audit row + idempotent retry.

**Smallest unit of work:**
- Charm REST client at `apps/transcribe-md/src/lib/charm/encounter.ts`
- SOAP template provisioning: must call `getPracticeInfo(info_type='template_details')` once per practice to discover Charm's SOAP template `entry_id`s. Cache per practice in `EhrIntegrationToken.metadata`.
- Note transformation: map QuillMD's S/O/A/P sections to Charm's `entries[]` format
- Push job: `process_charm_soap_push` BullMQ job, kicked off on visit sign
- Retry-with-backoff (existing pattern from worker.ts)
- Audit emit on success/failure (`EHR_PUSH_*` actions)
- Idempotency: content-hash + pre-write GET check before retry
- Sign action: `POST /patients/{id}/encounters/{eid}/sign` after content writes succeed

**Dependencies:** M0.1, M0.3

**Can parallelize:** can pre-build the transformation + client without live Charm; tests run against MCP server reference impl.

### M0.5 — Codes push (M scope, conditional)

**Deliverable:** ICD-10 codes pushed alongside SOAP; CPT codes pushed IF Charm BD confirms write endpoint exists.

**Smallest unit of work:**
- ICD-10: `POST /patients/{id}/diagnoses` for each, with `encounter_id` attached
- ICD-10 reconciliation on retry (content-hash dedupe)
- **CPT: HOLD until Charm BD confirms.** Phase 0 ships without CPT push if endpoint unavailable; ship with CPT if confirmed.
- Coding-coach warning-modal override workflow: QuillMD already lets the doctor accept/override a warning. The pushed ICD-10 reflects the final-accepted state, not the pre-override state.

**Dependencies:** M0.4

**Can parallelize:** ICD-10 path can ship without CPT decision. CPT path can ship in M0.5.1 after Charm confirms.

### M0.6 — Rx push (S scope) — degraded from frictionless

**Deliverable:** Rx drafts pushed to Charm chart medication list with QuillMD-source metadata. **No SureScripts transmission via API** — doctor finalizes in Charm UI.

**Smallest unit of work:**
- `POST /patients/{id}/medications` per Rx draft, with metadata `{source: "quillmd", visitId, draftedAt}`
- Status pinned to "draft" so doctor sees the Rx in Charm's draft list, not active medication list
- Existing PR-D Rx safety warnings still gate the push: only push Rx the doctor accepted in QuillMD's flow
- Supplements (functional med use case): use `POST /patients/{id}/supplements` endpoint instead

**Dependencies:** M0.4

**Can parallelize:** Rx + ICD-10 push both depend on M0.4 but are independent of each other.

### M0.7 — Audit + observability (S scope)

**Deliverable:** `/admin/charm-integration` dashboard surfaces per-practice health: connection status, last-push timestamp, last-error, push success rate.

**Smallest unit of work:**
- New page `apps/transcribe-md/src/app/admin/charm/page.tsx`
- Query `audit_logs` for `EHR_PUSH_*` actions in the last N days
- Per-practice rollup: success / failure / partial counts
- Per-visit drill-down showing the audit chain for a single push
- Manual retry button (Kasra/admin-only) for failed pushes

**Dependencies:** M0.4 (need real push events to display)

**Can parallelize:** schema + query parallel to UI; final wire-up gated on real push data.

### Milestone summary table

| Milestone | Scope | Depends on | Can parallelize | Blocker |
|---|---|---|---|---|
| M0.1 — Auth + connection | XS | — | Schema + UI parallel | Kasra: API agreement, sandbox payment, BAA |
| M0.2 — Patient sync | S | M0.1 | UI + FHIR client parallel | M0.1 |
| M0.3 — Visit creation hook | S | M0.2 | Schema + UI parallel | M0.2 |
| **M0.4 — SOAP push** | M (load-bearing) | M0.1, M0.3 | Transformation + client parallel | M0.1 |
| M0.5 — ICD-10 push | S (M with CPT) | M0.4 | Independent of M0.6 | **CPT-write confirmation from Charm BD** |
| M0.6 — Rx push | S | M0.4 | Independent of M0.5 | None |
| M0.7 — Admin dashboard | S | M0.4 | Schema + UI parallel | None |

**MVP gating definition:** M0.1 + M0.2 + M0.3 + M0.4 + M0.5 (ICD-10 only) + M0.7 = "QuillMD pushes signed SOAP + ICD-10 codes to a Charm encounter with admin visibility." Rx (M0.6) and CPT can ship as fast-follows.

---

## F. Open Questions for Kasra (ranked by blocking-status)

### BLOCKING — Phase 0 cannot start until resolved

1. **API agreement + BAA + sandbox payment.** Must be filled, signed, and paid before any engineering happens. **First action: submit the API Access Request form at [charmhealth.com/resources/ehr-api-program.html](https://www.charmhealth.com/resources/ehr-api-program.html).** Expect ~2 business days post-payment for sandbox credentials.

2. **CPT-write endpoint confirmation.** Ask Charm BD directly: "Does the Certified API program expose a CPT/procedure-code write endpoint, or is that gated to the RCM module?" If gated, **does QuillMD need a separate license to enable it?** This determines whether M0.5 ships full or partial.

3. **Free Plan API gating.** Confirm in writing: can Charm's Free Plan practices use the API, or is API access gated to Encounter Plan or higher? Affects the segment QuillMD can address.

### NEAR-BLOCKING — Phase 0 starts but specific milestones can't ship

4. **BAA scope + liability cap.** The Certified API ToS has broad indemnification with no published liability cap. Negotiate a reasonable cap before signing.

5. **AI-scribe BAA addendum.** Does Charm have an AI/LLM-specific BAA rider supplementing the standard BAA? If yes, request a copy. Aligns with QuillMD's existing Anthropic-BAA + PHI-scrub posture.

6. **Sandbox parity.** Are there documented feature-flag deltas between sandbox and production? Affects which milestones can be tested in sandbox vs require live customer.

7. **Practice-sponsor for first GA customer.** Charm requires per-practice admin enablement. Phase 0 needs ONE pilot practice (ideally one of the bariatric / functional-med customers from QuillMD's current pipeline) willing to be the live integration target. **Who is that practice?**

### NICE-TO-KNOW — Affect implementation details but not gate

8. **Encryption at rest.** Charm's security policy doesn't address this. Important for QuillMD's own security posture / pilot doctor IT review.

9. **Multi-tenant isolation architecture.** Logical vs physical separation, schema-per-tenant? Affects QuillMD's positioning in enterprise sales conversations.

10. **Webhook signing scheme.** `x-charm-action` header is documented; HMAC/mTLS verification is not. Required before subscribing in Phase 1.1.

11. **Cyber-liability insurance minimum.** May appear in the API License Agreement; cyber-liability minimums are standard.

12. **Charm's stance on QuillMD's competing AI scribe ($125/provider/mo or $2/encounter).** Will Charm treat QuillMD as a partner or a competitor? This is the question that defines whether QuillMD gets fast partnership treatment or slow-walked.

### Strategic / positioning

13. **Pilot customer profile.** Bariatrics + Spanish-language is QuillMD's wedge per the brief, but Charm's published case studies are bariatric (English) + functional-med (English). Does QuillMD have a multilingual / Spanish-speaking Charm-customer prospect, or do we need to find one?

14. **Pricing model for Charm-integrated tier.** Absorb $250/yr/module as part of QuillMD's PMPM, or surface it as a per-integration add-on? Affects unit economics + sales conversations.

15. **Whether to also pursue Charm Marketplace listing.** Listing in Charm's marketplace ([charmhealthhub.com](https://www.charmhealthhub.com/)) is a sales channel but adds onboarding-pricing complexity. Worth a separate sales-channel decision.

---

## G. Specific Actions for Kasra to Take

In priority order — these unblock Phase 0 engineering:

### Today (or this week)

**1. Submit the Charm API Access Request form.** [charmhealth.com/resources/ehr-api-program.html](https://www.charmhealth.com/resources/ehr-api-program.html). The form is the first contact — Charm responds with pricing + agreement.

**2. Join the Tuesday Zoom office hours.** "Integrate with CharmHealth," 10AM-12PM PST. Lower-friction way to ask BD questions than a cold email. Useful for asking the CPT-write question + AI-scribe-rider question without committing.

**3. Email `support@charmhealth.com` with the specific Phase-0 questions:**
   - CPT-write endpoint availability for Certified API developers
   - Whether Free Plan can use the API
   - AI-scribe BAA addendum availability
   - Webhook HMAC verification mechanism
   - BAA liability cap negotiability

### After Charm BD responds (week 2)

**4. Sign the API License Agreement + BAA.** Read carefully for indemnification scope + insurance minimums.

**5. Pay the $1,000 sandbox init fee.** Sandbox provisioning takes ~2 business days post-invoice.

**6. Identify the pilot practice.** Ideally one of QuillMD's existing prospects or pilots; must be on Charm; must be willing to grant API access via Settings → API Keys.

### Once sandbox is live (week 3+)

**7. Hand off Charm credentials to QuillMD engineering.** Engineering begins M0.1 once credentials land.

**8. Schedule a 2-3 week status check** to evaluate whether the CPT-write conversation has resolved before M0.5 engineering starts.

---

## H. Risks + Decision Points

| Risk | Mitigation | Decision point |
|---|---|---|
| Charm's competing AI scribe creates partnership friction | Position QuillMD as complementary (interpreter-mode + bariatric depth + Spanish-language capture) rather than head-on alternative. Lean into the differentiators competitors don't have. | If Charm slow-walks the API agreement → re-evaluate at week 4. |
| CPT-write turns out unavailable | Ship M0.5 ICD-10-only; CPT becomes a "Phase 1" item. Sales positioning shifts to "diagnoses + SOAP push" rather than "full coding push." | After Charm BD response. |
| Practice-sponsor doesn't materialize | Phase 0 can still SHIP the integration code path with sandbox testing, but no GA customer to validate end-to-end. Acceptable if Phase 0 is positioned as "ready when first customer is ready." | After 4 weeks of sales pipeline conversations. |
| 100-call/min rate limit hits in production | Add explicit batching of writes (single SOAP + multiple diagnoses in one synchronous batch); add exponential-backoff retry on 429. | Discover in M0.4 testing. |
| Idempotency missing causes double-push in production | Content-hash + pre-write GET defense (already in plan). Verify against Charm sandbox before GA. | M0.4 implementation. |
| BAA indemnification cap not negotiable | Final go/no-go after reviewing the actual document. Could decline if liability scope is unbounded vs QuillMD's stage. | At BAA signing. |

---

## I. What Phase 0 Does NOT Include

Explicit scope-fences to keep Phase 0 small:

- ❌ Charm webhook subscription (`Encounter.Sign`, `Encounter.Unlock`) — Phase 1.1
- ❌ Bi-directional sync (Charm → QuillMD on note edits)
- ❌ Multi-EHR abstraction layer — Phase 0 is Charm-only; multi-EHR comes when 2nd integration commits
- ❌ Charm Marketplace listing — separate sales-channel decision
- ❌ Charm RCM module integration (CPT-write may force this; see open question #2)
- ❌ SureScripts e-Rx transmission via API (degraded UX accepted in M0.6)
- ❌ Patient consent UX changes (existing QuillMD consent suffices; revisit if Charm BAA requires)
- ❌ Test data import from Charm sandbox into QuillMD dev for repeatable regression
