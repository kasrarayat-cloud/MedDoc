# Charm Health Deep-Dive

**Date:** 2026-05-13 22:46 UTC
**Author:** Claude (Opus 4.7 1M)
**Purpose:** Phase-0 EHR integration target reconnaissance — pure research, no code. Companion doc: `charm-health-phase-0-plan-20260513T224609Z.md`.

---

## A. Product Taxonomy

### A.1 — Product lines

The parent brand rebranded from **ChARM Health** to **CharmHealth** (lowercase "h" in current marketing; legacy URLs and reviews still use "ChARM EHR" interchangeably).

| Official product name | What it is | URL |
|---|---|---|
| **CharmHealth EHR** (a.k.a. legacy ChARM EHR) | The clinical EHR — Phase-0 integration target | [charmhealth.com/ehr/](https://www.charmhealth.com/ehr/) |
| **Charm PHR** | Patient-facing personal health record portal | [charmhealth.com/ehr/phr-patient-health-record.html](https://www.charmhealth.com/ehr/phr-patient-health-record.html) |
| **Practice Management** | Scheduling, front-office | charmhealth.com homepage |
| **TeleHealth** | Video visits — $20/provider/mo add-on | [ehr-pricing-us.html](https://www.charmhealth.com/ehr/ehr-pricing-us.html) |
| **Medical Billing Platform** | Standalone billing product | charmhealth.com homepage |
| **Revenue Cycle Management** | Full-service RCM (coding, claims, denial management) | charmhealth.com homepage |
| **CharmCopilot + Charm AI Scribe + CharmAssist GPT** | AI documentation suite — $125/provider/mo OR $2/encounter | [ehr-pricing-us.html](https://www.charmhealth.com/ehr/ehr-pricing-us.html) |
| **Charm Connect** | Interoperability layer | charmhealth.com homepage |
| **Charm Inventory** | In-house dispensing (supplements, vaccines, OTC, lab kits) | [integrative-medicine-emr.html](https://www.charmhealth.com/ehr/integrative-medicine/integrative-medicine-emr.html) |

**Phase-0 integration target: CharmHealth EHR** via the **proprietary REST API** (write surface) and **FHIR R4 API** (read surface). Both APIs are exposed through the "CharmHealth API Program" requiring a paid developer license.

### A.2 — Pricing tiers (US)

Verbatim from [charmhealth.com/ehr/ehr-pricing-us.html](https://www.charmhealth.com/ehr/ehr-pricing-us.html):

| Tier | Cost | Encounters | Providers / Users / Patients | Storage |
|---|---|---|---|---|
| **Free Plan** | $0 | ≤50/mo | 1 / 5 / 1,000 | 200 emails/mo |
| **Encounter Plan** | $0.50/encounter, $25/mo minimum; $1,000 + $0.30/consult beyond 2,000 | Unlimited | Unlimited | 25 GB |
| **Provider Plan** | $200/provider/mo (or $350 upgrade tier) | Unlimited | Unlimited | 50 GB |

**Add-ons** (apply to paid tiers):
- eRx: $15/provider/mo · EPCS: $250/provider/year + $10/mo
- Telehealth: $20/provider/mo
- **AI Scribe: $125/provider/mo OR $2/encounter** (this IS Charm's competing scribe product — directly relevant to QuillMD positioning)
- Electronic Claims: $25/mo minimum

**Auto-upgrade trigger:** Charm auto-upgrades Free → Encounter Plan once a practice crosses 50 encounters/month. Net: free practices ARE prospects who'll hit a $25/mo floor as soon as they grow — pricing friction is low.

**API access tier — UNRESOLVED from public docs.** The API Program page describes a gated process (questionnaire → review → signed agreement → client_id/client_secret) with no published statement on whether the Free Plan can use the API. Community-reported fees: **$1,000 one-time sandbox init + $250/yr per API module enabled** ([Mindbowser integration guide](https://www.mindbowser.com/charmhealth-ehr-integration-for-developers/)). These are not on Charm's own site; confirm during the API Request call.

**Specialty modules pricing:** No separately-priced SKUs for bariatrics / functional medicine. Specialty depth is delivered as **templates + integrations** on the base EHR (Fullscript supplements catalog, Charm Inventory) at no separately documented surcharge.

### A.3 — Target market positioning

**Stated positioning:** "medical practices of all sizes" — independent clinic to large enterprise. Marketing leads with "Founded and designed by doctors" and "Unlike most platforms, CharmHealth lets you get started for free."

**Operational reality (per Capterra / G2 reviews):**
- Sweet spot = solo / micro-practice / small group ("the most inclusive program," "pivotal for small practice success")
- US-primary, with some international footprint (testimonials from Australia, Hawaii); separate `ehr-pricing-us.html` page implies geographic pricing differences
- **Multilingual / Spanish-speaking / immigrant-serving — NO evidence found.** No Spanish-language case study, no immigrant-clinic reference in any reviewed source. This is QuillMD's wedge to attack rather than a Charm capability to inherit.

### A.4 — Specialty depth for QuillMD's wedge

**Weight Loss / Bariatrics** ([charmhealth.com/ehr/bariatrics/bariatrics-emr.html](https://www.charmhealth.com/ehr/bariatrics/bariatrics-emr.html)):

Documented features:
- Patient-facing questionnaires + screening forms (weight log, exercise, diet)
- Ready-to-use templates for weight-loss clinics
- Per-session progress notes
- LabCorp / Quest integration
- Remote video consultations
- Weight-trend plotting feature in patient encounters

**Not documented:** GLP-1 / semaglutide-specific workflow, DEXA/BIA body-composition integration, anthropometric measurement schemas beyond standard vitals, automated meal planning, scale integration. **This is a template-and-flowsheet play, not a dedicated bariatric module — leaving room for QuillMD's specialty depth.**

**Integrative / Functional Medicine** ([charmhealth.com/ehr/integrative-medicine/integrative-medicine-emr.html](https://www.charmhealth.com/ehr/integrative-medicine/integrative-medicine-emr.html)):

Documented features:
- Diet / lifestyle / supplement-aware care plans
- Custom templates for nutritionists, dietitians, acupuncturists, therapists
- Drug-Herb interaction databases
- **Charm Inventory** for supplements, vaccines, OTC drugs, lab kits
- **Fullscript supplements integration** (catalog of "professional-grade supplements")

**Not documented:** Functional labs (DUTCH, GI-MAP, Genova) — Charm references "LabCorp and Quest" but not the specialty functional-medicine labs. **Verify directly.**

---

## B. API Surface Inventory

### B.1 — Developer portal

| Resource | URL |
|---|---|
| **Primary landing** | [charmhealth.com/resources/ehr-api-program.html](https://www.charmhealth.com/resources/ehr-api-program.html) |
| **FHIR API docs** | [charmhealth.com/resources/fhir/index.html](https://www.charmhealth.com/resources/fhir/index.html) |
| **REST API index** | [charmhealth.com/resources/api/index.html](https://www.charmhealth.com/resources/api/index.html) |
| **Marketplace** | [charmhealthhub.com](https://www.charmhealthhub.com/) |
| **Partner services** | [charmhealth.com/partner/integration/services.html](https://www.charmhealth.com/partner/integration/services.html) |
| **MCP server (reference impl)** | [github.com/CharmHealth/charm-mcp-server](https://github.com/CharmHealth/charm-mcp-server) |
| **Weekly office hours** | "Integrate with CharmHealth" Zoom webinar, Tues 10AM-12PM PST |
| **API support contact** | `vibhu@charmhealthtech.com` (MCP repo maintainer) · `support@charmhealth.com` · `info@charmhealth.com` · `sales@charmhealth.com` |

### B.2 — Registration

**Not self-serve.** The process:
1. Submit the "CharmHealth Certified API Access Request" form
2. Charm reviews + sends pricing + agreement
3. Pay $1,000 one-time sandbox initialization fee (community-reported)
4. Sign API License Agreement
5. Charm issues `client_id`, `client_secret`, and provisions sandbox (~2 business days post-invoice)
6. **Per-practice authorization required INSIDE the EHR UI** at Settings → Account → API Keys before the app can act on practice data

### B.3 — Auth model

- **Protocol:** OAuth 2.0 + SMART-on-FHIR
- **Discovery:** `/.well-known/smart-configuration` confirms `launch-ehr` and `launch-standalone` capabilities
- **Grant types supported:** `authorization_code` (with/without PKCE), `refresh_token`, `client_credentials`, `urn:ietf:params:oauth:grant-type:device_code`, `urn:ietf:params:oauth:grant-type:jwt-bearer`, `implicit` (legacy)
- **Endpoints:**
  - Authorize: `https://accounts.charmtracker.com/oauth/v2/auth`
  - Token: `https://accounts.charmtracker.com/oauth/v2/token`
  - Revoke: `https://accounts.charmtracker.com/oauth/v2/token/revoke`
  - Userinfo: `https://accounts.charmtracker.com/oauth/v2/userinfo`
- **Scope model:** Three actors × USCDI-aligned resources
  - `patient/<Resource>.read` — patient-facing apps
  - `user/<Resource>.read` — provider-facing apps with multi-patient access
  - `system/<Resource>.read` — backend services / bulk export
  - Context: `launch`, `launch/patient`, `openid`, `fhirUser`, `offline_access`
  - **SMART scopes only document `.read`** — writes use the proprietary REST API's separate scope system (`charmhealth.patient.demographics.READ` etc.) not SMART scopes
- **Token lifetime:** 3600s (1 hour) access tokens; refresh tokens issued with `offline_access`
- **Grant scope:** Practice-level (admin grants in EHR UI); patient-level via SMART launch; no first-class per-doctor concept

### B.4 — Sandbox

- Base URL: `https://sandbox3.charmtracker.com/api/ehr/v1`
- Provisioned post-payment of $1,000 init fee (~2 business days)
- Sample data preloaded but specifics not published
- **Parity caveat:** docs note some testing scenarios need "production endpoint with test credentials" — suggests partial parity
- Reset / wipe: not documented publicly; likely a support-ticket operation

### B.5 — Rate limits + quotas

- **100 calls/min per module** (community-reported via Mindbowser; Charm's own FHIR docs list 429 as a status but no number)
- No published per-tier quotas
- 429 returned on overage; `Retry-After` header behavior **not documented**

**Implication for QuillMD:** workable at single-practice scale. Multi-module orchestration during a busy visit (read demographics + write encounter + write Rx) could approach the cap on bursty workflows — design with retry-with-backoff.

### B.6 — Versioning + deprecation

- **FHIR API:** v1 at `ehr.charmtracker.com/api/ehr/v1/fhir`, v2 at `ehr2.charmtracker.com/api/ehr/v2/fhir` — **active v1→v2 migration in progress** (different host indicates host-level breaking changes Charm has shipped before)
- **REST API:** v1 at `apiehr.charmtracker.com/api/ehr/v1/` — no v2 yet
- **No public deprecation policy / sunset SLA.** Treat deprecation risk as opaque; pin versions + canary-test on releases.

### B.7 — Tooling

- **OpenAPI / Swagger:** Not published
- **Postman collection:** Not published
- **SDKs:** No official JS / Python SDKs
- **Reference implementation:** [github.com/CharmHealth/charm-mcp-server](https://github.com/CharmHealth/charm-mcp-server) — Python 3.13+ MCP server wrapping 15 tools (patient search, encounters/SOAP, vitals, labs, allergies, diagnoses, files, appointments). This is the closest thing to a reference SDK. MIT-licensed.
- **Community forum:** None — no Discord, no Stack Overflow tag, no Reddit r/healthIT corpus

---

## C. Capability Matrix

**Two parallel APIs.** Writes happen via the proprietary REST surface; FHIR is read-only.

| # | Capability | Supported? | Endpoint | Tier | Gotchas |
|---|---|---|---|---|---|
| 1 | Patient demographics (read) | ✅ Yes | `GET /patients/{id}` (REST); `GET /Patient/{id}` (FHIR) | Patients module | Patient module purchase required |
| 2 | Visit notes / encounters (read) | ✅ Yes | `GET /encounters?patient_id={id}`; `GET /soap/encounters/{id}` for full body; FHIR `GET /Encounter` | Encounters module | List returns thin record; need separate call for SOAP body |
| 3 | Problem list / ICD-10 (read) | ✅ Yes | `GET /patients/{id}/diagnoses`; FHIR `Condition` | Patients module | Returns `patient_diagnoses` array |
| 4 | Current medications (read) | ✅ Yes | `GET /patients/{id}/medications`; FHIR `MedicationStatement` | Patients/Rx module | RxNorm-coded; active+inactive default |
| 5 | Allergies (read) | ✅ Yes | `GET /patients/{id}/allergies`; FHIR `AllergyIntolerance` | Patients module | Standard filtering |
| 6 | Vitals + body composition (read) | ✅ Yes | `GET /patients/{id}/vitals`; FHIR `Observation` (vital-signs cat) | Patients module | Custom vital templates per practice — must call `getPracticeInfo(info_type='vitals_templates')` |
| 7 | Lab catalog + results (read) | ⚠ Partial | `GET /labs/results`; write via `POST /labs/results/upload` | Labs module | Integrated lab vendors only; outside labs via PDF upload |
| 8 | Appointments (read) | ✅ Yes | `GET /appointments`; FHIR `Appointment` | Scheduling module | Webhooks available |
| **9** | **Push SOAP note** | **⚠ Yes (REST only)** | Create: `POST /patients/{id}/encounter` or `POST /appointments/{id}/encounter` w/ `chart_type:SOAP`. Save narrative: `POST /patients/{id}/encounters/{eid}/save`. Update via template: `POST /soap/encounters/{eid}` w/ `entries`. Attach template: `POST /soap/encounters/{eid}/template` | Encounters module | **S/O/A/P are NOT discrete top-level fields.** Single `chief_complaints` narrative blob is primary. Discrete sections require pre-provisioning a SOAP template in Charm + pushing as `entries[]` keyed by `entry_id`. **`entry_id` values must come from `getPracticeInfo(info_type='template_details')` — fabricated IDs are silently dropped.** |
| **10** | **Push ICD-10** | **✅ Yes** | `POST /patients/{id}/diagnoses`; pass `encounter_id` in payload to attach | Patients module | Updates `PUT /patients/{id}/diagnoses/{record_id}`; uses Charm's ICD-10 catalog |
| **11** | **Push CPT codes** | **❌ Unknown / not documented** | **No POST endpoint surfaced in MCP server or public docs.** Procedures are GET-only: `GET /patients/{id}/procedures`. Billing/coding flows live behind Charm's RCM service — likely separate module not exposed via standard developer license | Billing/coding (likely separate module) | **MAJOR YELLOW FLAG.** Either no public CPT-write endpoint exists or it's gated behind billing module. Confirm with `support@charmhealth.com` before Phase-0 commit. |
| **12** | **Push Rx** | **⚠ Partial (chart-only, not transmitted)** | `POST /patients/{id}/medications` adds to chart medication list; supplements: `POST /patients/{id}/supplements` | Patients/Rx module | **MCP server does NOT expose a "Sign & Send Rx" action.** SureScripts/EPCS transmission requires clinician's UI session (2FA for EPCS). API push becomes an unsigned draft the doctor must dispatch manually. |
| **13** | **Sign + lock workflow** | **✅ Yes** | `POST /patients/{patient_id}/encounters/{encounter_id}/sign` to sign; `POST /encounters/{eid}/unlock` w/ `{reason}` to unlock | Encounters module | **Rare and valuable.** Once signed: "legally binding and cannot be modified" without explicit unlock + re-sign. API-driven sign IS supported — most EHRs require UI session. |
| 14 | Update existing visit | ✅ Yes (pre-sign) | `POST /soap/encounters/{eid}` for narrative/entries | Encounters module | Cannot update once signed — addendum/unlock workflow only |
| 15 | Idempotency-Key header | ❌ Not documented | — | — | **Retries will likely double-push.** Build client-side dedup (hash content + encounter_id before retry) |
| 16 | Audit log read API | ❌ Not documented | No `/audit` endpoint surfaced | — | Charm has internal audit logs (Drummond-certified) but no public read API |
| 17 | Webhooks on Charm-side edits | ✅ Yes | Per-practice subscription; events use `x-charm-action` header | Per-module | Events: `Patient.Add/Edit/Deactivate/Activate`, `Appointment.Add/Reschedule/StatusChange/Edit/Cancel`, `Encounter.Create/Sign/Unlock/Delete`, lab `eReceive`, `Invoice.*`. **`Encounter.Sign` is critical for QuillMD.** Signing/HMAC verification details not documented. |
| 18 | Error response shape | ✅ Structured JSON | `{"code":"0","message":"...",...}` envelope; success on `code == "0"` | — | **Non-standard:** uses string `"0"` for success rather than HTTP status alone. HTTP 200 + `code != "0"` is a logical failure. |

### C.1 — The green path

The transcribe-summarize-push loop **is achievable** in Phase-0:

1. Pull rich context (demographics, problem list, meds, allergies, vitals) via REST OR FHIR before recording
2. Create encounter for appointment via `POST /appointments/{id}/encounter` w/ `chart_type=SOAP`
3. Save SOAP narrative + template entries via `POST /soap/encounters/{eid}`
4. Push ICD-10 to encounter via `POST /patients/{id}/diagnoses` w/ `encounter_id`
5. Optionally pre-populate medications via `POST /patients/{id}/medications`
6. **Trigger sign via `POST /patients/{id}/encounters/{eid}/sign`** — this is the rare differentiator
7. Listen for `Encounter.Sign` webhook to confirm finality

The MCP server is effectively reference client code QuillMD can read.

### C.2 — The red flags

**Three in descending severity:**

1. **No public CPT/procedure write endpoint.** GET-only on `/procedures`. Charm's CPT entry happens in Billing module — likely separate license, may require RCM service. **For the QuillMD value prop ("push the codes that drive the bill"), this is the single biggest gap.** Must verify directly before Phase-0 commit.

2. **No API-level "Sign & Send Rx" — SureScripts transmission is UI-only.** `POST /patients/{id}/medications` adds inactive/active chart entry but no "send Rx" action. SureScripts and EPCS flows require the clinician's UI session + 2FA. QuillMD's Rx push becomes a draft the doctor completes in Charm — still useful but degrades the "frictionless" pitch.

3. **No documented idempotency.** Retries on flaky networks will double-push notes/diagnoses/Rxs. QuillMD must build client-side dedup until Charm confirms otherwise.

**Secondary unknowns:** No documented audit-log read API. No discrete S/O/A/P fields — Charm models the note as `chief_complaints` narrative + template `entries[]`, requiring per-practice template provisioning + entry-ID discovery.

### C.3 — Specialty quirks for QuillMD's wedge

- **`/patients/{id}/supplements`** is a distinct endpoint from `/medications`. Useful for functional-med practices documenting supplements heavily.
- **Practice-customizable vitals templates** — body composition fields (waist circumference, BIA body fat) are first-class once configured. Must call `getPracticeInfo` per tenant to discover field IDs; hardcoding will silently fail.
- **Custom flowsheets / questionnaires per practice** — weight-management visits map well, but every practice's template IDs are different.

---

## D. Integration Mechanism Options

| Mechanism | Status at Charm | Recommended for QuillMD Phase-0? |
|---|---|---|
| **Direct REST API** (proprietary) | ✅ Primary write surface — `https://apiehr.charmtracker.com/api/ehr/v1/` | **Yes — for the write-back path.** This is where SOAP notes, ICD-10, Rx, and sign actions land. |
| **FHIR R4** | ✅ Read-only — `https://ehr2.charmtracker.com/api/ehr/v2/fhir/` | **Yes — for the read-context path.** Pull demographics + problem list + meds + allergies before the visit. |
| **SMART on FHIR app launch** | ✅ `launch-ehr` + `launch-standalone` confirmed via `.well-known/smart-configuration` | **Yes — for the UX win.** Doctor opens QuillMD from inside Charm, gets `patient` + `encounter` + `user` context free. SMART scopes are read-only so the launched session doesn't write — backend OAuth handles writes separately. |
| **HL7 v2 (MLLP)** | ❌ No published partner surface | **No.** Skip. |
| **Webhooks** | ✅ Per-practice subscription via `x-charm-action` header on lifecycle events | **Defer to v1.1.** Useful for `Encounter.Sign` confirmation but not Phase-0 critical. Signing/HMAC scheme undocumented — confirm before relying. |

**Recommended hybrid for Phase 0:**

1. SMART on FHIR EHR-launch for clinician-initiated context handoff (visit starts in Charm → QuillMD opens with patient + encounter context)
2. FHIR R4 read API for pre-visit context priming (problem list, meds, allergies)
3. **Proprietary REST API for ALL writes** (SOAP, ICD-10, medications, sign action)
4. (Phase 1.1) Webhook subscription on `Encounter.Sign` for confirmation

### D.1 — Why SMART alone fails

FHIR is read-only at Charm. No `POST DocumentReference` for the signed note. SMART buys patient context + read tokens but does NOT buy a write path. Showstopper for a SMART-only architecture.

### D.2 — Why direct REST alone is worse UX

Loses the in-context EHR launch — doctor must manually paste `patient_id` into QuillMD for every visit. Onboarding tax compounds per-customer. SMART launch is the friction-killer.

---

## E. Compliance Posture

### E.1 — Phase-0 blocker check

**NO HARD BLOCKER FOUND.** Charm does not publicly require integrators to be SOC 2 Type II or HITRUST-certified before granting production API access. The gating artifacts are:

1. API Request Questionnaire (form-based)
2. Signed API License Agreement (paid)
3. Separate BAA (negotiated via `support@charmhealth.com`)
4. $1,000 sandbox init fee + $250/yr/module

**Soft caution:** Charm's public compliance footprint is unusually thin — no SOC 2, no HITRUST, no published pen-test summary. This is "no documented blocker" rather than "verified clean."

### E.2 — BAA

| Item | Status |
|---|---|
| Will Charm sign with third-party integrator? | ✅ Yes — terms explicitly contemplate it. MedicalMine (Charm's parent) self-identifies as a Business Associate. |
| Standardized vs negotiated? | Standardized template; negotiated case-by-case via `support@charmhealth.com`. May be limited to Enterprise plans (third-party report — verify). |
| BAA contact | No dedicated `legal@` / `compliance@` published. Route via `support@charmhealth.com`. Confirm during API questionnaire. |
| Turnaround | ~2 business days for API agreement+sandbox post-invoice (community report). BAA-specific timing not documented. |
| Gotchas | (a) Paid API license is prerequisite; (b) Surescripts adds audit-rights clause if e-Rx is enabled; (c) integrator indemnification clause is **broad with no published liability cap**. |

### E.3 — Certifications

| Cert | Status |
|---|---|
| HIPAA | ✅ Self-asserted; no OCR-audit history surfaced |
| HITRUST CSF | ❌ Not certified, not claimed |
| SOC 2 Type II | ❌ Not publicly claimed — Keragon's third-party review explicitly flags this |
| **ONC Health IT** | ✅ Yes — ChARM EHR v1.2 is 2015 Edition Cures Update certified. Cert ID `15.04.04.1948.ChAR.12.00.1.181115` (2018-11-15). FHIR R4 + US Core STU 3.1.1 + SMART App Launch + EHI Export all in scope. [Source: Newswire announcement] |
| PCI-DSS | Not addressed publicly (billing delegated to Optum) |
| GDPR / CCPA | No separate posture published |

### E.4 — Data residency + isolation

| Item | Status |
|---|---|
| Hosting location | US-only — "Tier 3 Plus data centers in the United States" (privacy policy) |
| US entity | ✅ MedicalMine Inc., Pleasanton, CA — simplifies BAA jurisdiction |
| Encryption in transit | TLS 1.2 / AES-CBC/AES-GCM 256/128 / SHA-2 MAC |
| **Encryption at rest** | ⚠ Not stated publicly — confirm in security review |
| Multi-tenant isolation | Not publicly described — must ask Charm directly |
| DR / backup | "Customer data mirrored in separate geographic location for DR"; no RPO/RTO published |
| Audit trail | "captures all actions performed in the application related to creation, alteration, or deletion of PHI" |

### E.5 — Integrator obligations

Per the Certified API ToS:

- "You are solely responsible for all aspects of HIPAA compliance in your application"
- "You will ensure that you will provide authentication, access control, authorization and a trusted connection to our API servers"
- **Full indemnification for HIPAA breach or gross negligence — no liability cap published**

**Not required of integrators:**
- SOC 2 / HITRUST
- Pen-test reports
- Cyber-liability insurance minimums (may appear in API License Agreement — confirm)
- Specific N-year audit retention (default to 6 years per HIPAA §164.316(b)(2) regardless)

### E.6 — AI-scribe-specific policy

**This is the most concrete + recent compliance text Charm has published** — in the MCP server README:

- "Only use HIPAA-compliant LLM services covered by a signed BAA and configured with no training and zero data retention"
- "Do not connect non-HIPAA consumer LLM endpoints or clients"
- "Do not use non-HIPAA consumer clients (e.g., Claude Desktop) with PHI" — **Claude Desktop is explicitly prohibited**; Anthropic API under BAA is the implicit acceptable path
- "Keep `COLLECT_METRICS=false` unless your telemetry backend is HIPAA-compliant and covered by a BAA"
- Integrator must enforce: "least-privilege access controls, audit logging, encryption in transit and at rest"; "breach notification"

QuillMD already uses the Anthropic API under BAA (per the 2026-05-13 security audit baseline). The Claude Desktop prohibition doesn't affect us. The PHI-redaction posture from PR #240 + #242 (Sentry scrubbing, DLQ redaction, client-errors PHI scrub) aligns with Charm's expectations.

---

## F. What We Don't Know Without a Dev Account

These genuinely require Charm BD conversation or paid sandbox access. None block Phase-0 architecture decisions, but each carries Phase-0 implementation risk:

1. **Whether a CPT/procedure-code write endpoint exists for licensed developers.** Most important unknown. The QuillMD value prop ("push the codes that drive the bill") depends on this.
2. **Whether the `/sign` endpoint enforces EPCS 2FA** when the encounter contains controlled-substance prescriptions. UI flow requires it; unclear if API attempts to bypass or hard-fails.
3. **Actual 429 rate-limit behavior** (back-off-and-retry guidance, `Retry-After` header).
4. **Webhook payload schema + signing/HMAC verification details.** `x-charm-action` header is documented; payload structure + authenticity verification aren't.
5. **Whether a `MedicationRequest` write or Sign-and-Send Rx REST endpoint exists in a non-public partner SDK.** SureScripts-certified vendors sometimes get private endpoints.
6. **Sandbox parity with production.** Feature-flag deltas are common; impossible to verify without the $1,000 + $250 license.
7. **Whether FHIR `POST /_search` operations count toward 100-call/min limit** the same as REST GETs.
8. **The actual `entries[]` payload schema for SOAP templates** — MCP code shows the wire format but the canonical field list lives behind paid docs.
9. **Whether BAA gating is Enterprise-tier-restricted** (Keragon hints this; verify).
10. **Whether Charm has an AI-scribe-specific BAA addendum** (newer scribe-specific compliance riders are emerging across the industry).
11. **Encryption at rest specifics** (algorithm, key management, customer-managed keys?).
12. **Multi-tenant isolation architecture** (logical vs physical separation, schema-per-tenant?).
13. **DR RPO/RTO + backup-test cadence.**
14. **Insurance minimums in the API License Agreement** (cyber liability, E&O floor).
15. **Sub-processor list** (who else touches PHI in Charm's stack?).
16. **Breach-notification SLA in Charm's direction** (Charm → QuillMD timing).

---

## G. Quick-Reference URL Index

| Resource | URL |
|---|---|
| API Program (entry point) | https://www.charmhealth.com/resources/ehr-api-program.html |
| FHIR API docs (v2) | https://www.charmhealth.com/resources/fhir/index.html |
| FHIR API docs (v1, legacy) | https://www.charmhealth.com/resources/fhirapi/ |
| REST API index | https://www.charmhealth.com/resources/api/index.html |
| MCP server (reference impl) | https://github.com/CharmHealth/charm-mcp-server |
| FHIR base URL (v2) | https://ehr2.charmtracker.com/api/ehr/v2/fhir/ |
| REST base URL (v1) | https://apiehr.charmtracker.com/api/ehr/v1/ |
| Sandbox REST | https://sandbox3.charmtracker.com/api/ehr/v1 |
| OAuth authorize | https://accounts.charmtracker.com/oauth/v2/auth |
| OAuth token | https://accounts.charmtracker.com/oauth/v2/token |
| OAuth revoke | https://accounts.charmtracker.com/oauth/v2/token/revoke |
| SMART config | https://ehr2.charmtracker.com/api/ehr/v2/fhir/.well-known/smart-configuration |
| API Terms of Service | https://www.charmhealth.com/resources/api-terms-of-service.html |
| Certified API ToS | https://www.charmhealth.com/resources/certified-api-terms-of-service.html |
| Privacy Policy | https://www.charmhealth.com/privacy-policy.html |
| Security Policy | https://www.charmhealth.com/security.html |
| Real World Test Plan 2025 | https://www.charmhealth.com/resources/meaningful-use/real-world-testing/real-world-test-plan-2025.pdf |
| Marketplace | https://www.charmhealthhub.com/ |
| ONC CHPL (verify cert) | https://chpl.healthit.gov |
| Mindbowser developer guide (community ref) | https://www.mindbowser.com/charmhealth-ehr-integration-for-developers/ |
| Keragon HIPAA review | https://www.keragon.com/hipaa/hipaa-compliant-checker/charm-health |

**Contacts:**

| Purpose | Contact |
|---|---|
| API access request | API Program form on charmhealth.com |
| API support / BAA inquiry | `support@charmhealth.com` |
| MCP repo / dev questions | `vibhu@charmhealthtech.com` |
| General / sales | `info@charmhealth.com` / `sales@charmhealth.com` |
| Office hours | Tuesdays 10AM-12PM PST, Zoom (registration via `charmhealth.com`) |
