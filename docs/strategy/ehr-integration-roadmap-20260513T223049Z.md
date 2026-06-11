# EHR Integration Roadmap

**Date:** 2026-05-13
**Author:** Claude (Opus 4.7 1M)
**Status:** Research + strategy. No code shipped. Read before any Phase-0 implementation work begins.

---

## A. Executive Summary

EHR integration is the single most important missing capability for QuillMD vs competitors today, but the right way to ship it is **deliberately narrow first**: pick ONE EHR that matches QuillMD's actual customer pipeline, ship it end-to-end (signed SOAP + ICD-10 + CPT + Rx pushed into the patient's chart for the encounter QuillMD just recorded), and use that single working integration as proof-of-concept to drive enterprise sponsorship for the bigger names. The wrong move is announcing six integrations of which one is real — the competitive landscape already shows that pattern (Abridge's integrations URL 404s; Freed names no EHRs; Augmedix lists seven without case studies). Specificity beats breadth.

The recommended first integration is **DrChrono** (architectural validation; QuillMD already has working DrChrono plumbing on the sister CRM, marginal cost near zero, 2-6 week lift) followed in short order by **Elation Health** (commercial fit for QuillMD's solo-doctor / primary-care / DPC positioning; FHIR-first; activation in days post-BAA; cleanest cultural alignment). Phase 1 expansion is **athenahealth** (the realistic scale path into independent multi-specialty groups, with a 15-30% Marketplace rev-share that needs explicit economic modeling) and **Charm Health** (the only mainstream EHR with native weight-management / functional-medicine specialty fit — directly relevant to QuillMD's bariatrics differentiator). Phase 2 is the enterprise wedge: either **Epic Garden Plot** with a sponsoring customer in hand, or **Redox** as a broker for everything else. eClinicalWorks stays reactive — every serious competitor either outsources it to Vim or omits it.

QuillMD has three genuine differentiation opportunities the competitive landscape leaves open: (1) **solo-doctor pricing with real bi-directional integration** — Freed wins solo on $79-119 PMPM but has no API integration; Heidi has integration but gates it behind upgrades; (2) **interpreter mode** — none of nine competitors surveyed market multilingual ambient capture as a first-class feature, and QuillMD just validated GREEN demo readiness for Spanish/English/interpreter as of 2026-05-13; (3) **bariatrics + endocrine specialty depth** — competitors lead with oncology (DeepScribe via Flatiron/Ontada), dermatology/ortho (ModMed), or generalist horizontal-coverage. The integration roadmap should be designed so each phase preserves these differentiators rather than diluting them.

---

## B. Landscape Inventory

### B.1 — Market share + practice fit

| Vendor (product) | US ambulatory share | Typical practice size | Pricing tier | Source |
|---|---|---|---|---|
| Epic (EpicCare Ambulatory / Garden Plot) | ~19.5% installs; 37-44% by visit volume | Large IDNs + academic medical centers; Garden Plot targets smaller affiliates | High ($10M-$30M+ enterprise) | Definitive Healthcare Oct 2025; EHR Source Feb 2026 |
| Oracle Health (Cerner Ambulatory / CommunityWorks) | ~5.4% | Mid-to-large hospitals + employed ambulatory | High ($2M-$5M mid-hospital) | Definitive Healthcare Oct 2025 |
| athenahealth (athenaOne) | ~6.9%; 160k+ providers | 1-75 providers; independent group sweet spot | Mid (~$140/provider/mo + % collections) | Definitive Healthcare Oct 2025 |
| eClinicalWorks | ~11.9%; 850k+ users | Multi-specialty groups + FQHCs | Mid ($449-$599/provider/mo) | Definitive Healthcare Oct 2025 |
| NextGen Healthcare | ~4.2% | 10-200+ provider specialty groups | Mid ($150-$500/provider/mo) | Definitive Healthcare Oct 2025 |
| Veradigm (legacy Allscripts Pro/TouchWorks) | ~3.1% | Mid-size ambulatory | Mid | Definitive Healthcare Oct 2025 |
| Practice Fusion (Veradigm Connect) | ~3.1% | Solo + 1-5 provider; legacy free-tier base | Low ($149/provider/mo since 2018) | Definitive Healthcare Oct 2025 |
| DrChrono (EverHealth) | not in top-10; ~17k physicians self-reported | 1-5 providers, iPad/mobile-first | Mid ($299+/provider/mo) | Vendor 2024 |
| Tebra (Kareo + PatientPop) | ~107k providers historically; not in top-10 | 1-3 providers, startup solo | Low ($10-$100+/mo, modular) | Tebra 2024 |
| **Elation Health** | Not in top-10; **Best in KLAS Small-Practice Ambulatory 2025 + 2026** | Solo + small primary-care, DPC | Mid (~$275/provider/mo) | KLAS 2025/2026 |
| Charm Health | Unknown | Solo + micro-practice; integrative/functional med | Low ($0 free tier ≤50 enc/mo; $0.50/enc paid) | Vendor |
| OpenEMR | ~5k US installs / 70k+ global | Solo, FQHCs, international clinics | Free (self-host) | Open-EMR.org 2024 |

**Top three (Epic + eCW + athena) hold ~38-40% of ambulatory installations.** Solo / sub-5-physician segment is **36.5% of 2024 ambulatory EHR revenue** and the fastest-growing slice (Grand View Research 2024) — QuillMD's structural lane.

### B.2 — Specialty fit (only the rows that matter to QuillMD)

| Vendor | Specialty fit for QuillMD's segments |
|---|---|
| **Elation Health** | Primary care purebred — DPC, family medicine, internal medicine, pediatrics, geriatrics. KLAS Small-Practice leader. No native bariatric specialization but the DPC overlap with multilingual immigrant-serving clinics is strong. |
| **Charm Health** | **Strongest bariatric/weight-management fit** — integrative + functional medicine, weight-management, naturopathic, telehealth. Native specialty templates exist for this clinical model. |
| **NextGen** | Explicitly specialty-template-driven (26 templates incl. **endocrinology**, orthopedics, OB/GYN). The endocrine play. |
| **Veradigm** (Allscripts Pro/TouchWorks) | Mid-size cardiology, oncology, **endocrinology** — broad specialty coverage but losing share. |
| **DrChrono** | Mobile-first / iPad — dermatology, urgent care, chiropractic, mental health, concierge primary care. **QuillMD's meddoc-pro CRM already integrates here.** |
| **athenahealth** | Independent primary care + multi-specialty groups; growing OB/GYN + cardiology footprint; KLAS-favored for independent practices. |
| Epic, Oracle, eClinicalWorks | Generalist; specialty templating exists but the buyers are enterprise hospital systems, not QuillMD's first-customer profile. |

### B.3 — Reflection

QuillMD's strongest commercial lane is the solo / sub-5-provider tier — 36.5% of 2024 ambulatory EHR revenue and the fastest-growing slice — where Epic and Oracle are structurally absent and the field fragments into 5-6 viable targets. Priority integration order for QuillMD's bariatrics + endocrine + interpreter-mode differentiators: (1) **DrChrono** (free reuse from CRM), (2) **Elation** (primary-care KLAS leader, DPC channel for solo physician), (3) **Charm** (only EHR with native functional-medicine + weight-management specialty fit and a free tier mirroring QuillMD's solo-onboarding funnel), (4) **athenahealth** (scale path into independent multi-specialty groups), (5) **NextGen + Veradigm** (endocrine-specialty plays where templated workflows already exist). Epic, Oracle, and eCW are deferrable — their buyers won't choose QuillMD over an in-suite scribe at QuillMD's current stage.

---

## C. Integration Standards + Patterns

### C.1 — FHIR

**FHIR R4 is the regulatory baseline.** US Core IG STU 6.1.0 is anchored to R4. R5 (2023) sees opportunistic use but US Core is not migrating off R4 and ASTP is unlikely to adopt a newer version before 2028. **Target R4 first; R5 only when a specific customer requires it.**

**Cures Act timeline relevant to QuillMD's go-to-market window:**
- **January 1, 2026** (already passed) — certified EHRs must support **USCDI v3** (adds SDOH, sexual orientation, gender identity, mental/cognitive status)
- **July 4, 2026** — TEFCA-participating networks must expose USCDI v3 over US-Core-aligned FHIR APIs
- Information-blocking rules carry financial disincentives + loss of certification, so most EHR vendors are leaning forward on READ APIs. **Write is not mandated** — this is the load-bearing landmine.

**Resources QuillMD cares about — read vs write reality:**

| Resource | Read (universal R4) | Write (Create/Update) |
|---|---|---|
| Patient | Yes — all certified EHRs | Rarely pushed by scribes |
| Encounter | Yes | Vendor-gated; often read-only or via DocumentReference context |
| **DocumentReference** | Yes | **Yes on Epic + Cerner** — the canonical scribe push target. Per-section writes (HPI, A&P, etc.) supported on Epic via R4 |
| Condition | Yes (Problem List) | Epic: Yes; athena/eCW: partial, often proprietary endpoints |
| MedicationRequest | Yes | **Highly gated** — Epic gates Rx writes behind Connection Hub + EPCS; almost never available to a third-party scribe via FHIR alone |
| Procedure | Yes | Limited; usually flows through billing endpoints, not FHIR |

**The big read-only landmine.** "Has FHIR" almost always means **read APIs only** absent a vendor partnership. eClinicalWorks in particular advertises US Core conformance but has documented coverage gaps where data lives in narrative notes. Practical implication for QuillMD: **plan for read-FHIR + write-via-other-channel** on most EHRs other than Epic.

### C.2 — SMART on FHIR

**Launch model.** Two flavors: EHR-launch (clinician clicks the app inside the EHR; EHR provides patient/encounter context) and standalone-launch (app initiates auth, then asks for context). For QuillMD's ambient-scribe-then-push workflow, EHR-launch is the natural fit because encounter context is free; standalone is fallback for desktop/mobile capture.

**OAuth scopes.** SMART v2.2 uses `<actor>/<Resource>.<permissions>`. For QuillMD: `user/DocumentReference.c` (create note), plus read scopes for chart context. `system/` scopes for backend service flows.

**No central SMART certification.** Each EHR runs its own intake — Epic Vendor Services, Oracle Health Developer Program, athena Marketplace, etc.

**Existing SMART scribe apps (competitive intel):** Microsoft Dragon Copilot (Epic + Cerner + athena via Epic App Orchard + SMART v2), Abridge (Epic Connection Hub + Particle Health for cross-org context), Suki (Epic + Cerner + athena + MEDITECH), DeepScribe (Epic SmartData Elements + others), Nabla (multi-EHR SMART), Heidi Health (multi-EHR; eCW via Vim middleware). The implementation pattern that's now table-stakes: **per-section DocumentReference writes**, mapping each SOAP section to a discrete chart field rather than dumping the full note as a blob.

### C.3 — HL7 v2

**Still required when:** hospital ADT feeds, lab/radiology orders + results, billing/charge capture, immunization registries, the long tail of legacy ambulatory systems (older eClinicalWorks, NextGen, Greenway). v2 is NOT dying — it's the workhorse for transactional clinical data even at FHIR-forward shops.

**Wire protocol:** MLLP — pipe-delimited messages framed by `0x0B` / `0x1C 0x0D`, typically TCP, often inside a VPN/SFTP envelope.

**Interface engines + rough costs:**
- **Mirth Connect** (open source) — zero license cost. Default for SMB. Year-one engineering $25K-$100K.
- **Rhapsody / Corepoint / Cloverleaf** (commercial) — small clinic on Rhapsody ~$80K year-one; enterprise on Cloverleaf $4M+/yr.
- Per-interface engineering: 2-6 weeks each.

**Relevance for QuillMD's segment:** **Low priority short-term, but not zero.** Independent practices on cloud-native EHRs primarily expose FHIR/REST. Practices on legacy eClinicalWorks or older NextGen may still need v2 ORU/ADT. **Don't build v2 in v1**; if a target customer needs it, deploy a customer-side Mirth instance or partner with a broker.

### C.4 — Vendor-proprietary APIs

| Vendor | Apply friction | Cost | Capability depth |
|---|---|---|---|
| **Epic** (Vendor Services + Showroom) | Moderate — open.epic registration is free; production app requires a sponsoring Epic customer | App Orchard/Showroom listing fees $5K-$15K/yr; Workshop tier adds rev-share + possible equity terms | Deepest — R4 write to DocumentReference, Condition, AllergyIntolerance, Observation. Per-section SOAP mapping supported. **EpicAI Charting launched Feb 2026 is direct competition.** |
| **Cerner / Oracle Health Code** | Low — self-serve registration on code.cerner.com | "Contact sales" for production; sandbox free | FHIR R4 (Ignite APIs) recommended for new builds. Strong SMART support. |
| **athenahealth Marketplace** | Low — public developer portal, 800+ endpoints documented | **Revenue share 15-30%** of subscription revenue on Marketplace-sourced deals | Strong — REST + FHIR. 160K+ providers reachable. |
| **DrChrono** | Lowest — public OAuth REST, no gatekeeper sponsor required | No listing fee; standard Marketplace rev-share terms | REST mature; FHIR newer (ConnectEHR-mediated). Good fit for solo/small offices. |
| **eClinicalWorks** | High historically — public docs scarce; gated by direct sales | "Contact sales"; sponsor-required for production keys | US Core / FHIR present but coverage gaps documented; data often in narrative fields. **Route eCW via Redox or wait for sponsor demand.** |

### C.5 — Indirect / broker routes

| Broker | Pricing | EHR coverage | Direct/indirect complexity | BAA |
|---|---|---|---|---|
| **Redox** | $30K-$200K+/yr ACV; tiered by integrations + message volume | 12,200+ orgs, 100+ EHRs + HIEs | One Redox JSON API; Redox handles HL7v2, FHIR, vendor APIs underneath. Massive complexity reduction. | Standard BAA |
| **Particle Health** | Contact sales; per-query + seat-based | 160K+ orgs, 320M+ FHIR patient records via Carequality/TEFCA | Optimized for **read** (cross-org chart context — Abridge uses it). Less suited to writing notes back. | Yes |
| **1upHealth** | Contact sales | Largest declared FHIR network footprint; emphasis on aggregator + patient-mediated | Pure FHIR R4 surface, good for read aggregation; write capability depends on downstream EHR | Yes |
| **Health Gorilla** | Contact sales | 92% of US healthcare orgs reachable; designated TEFCA QHIN | Strong for clinical data network reads, ADT, lab results; less of a write broker | Yes |
| **Smile CDR / HAPI FHIR** | HAPI FHIR free (Apache 2.0); Smile CDR from ~$10K/yr | Self-hosted FHIR server — not a connectivity broker | Useful as QuillMD's own canonical FHIR persistence layer | Self-host |

**Broker recommendation for QuillMD's stage.** Given single-VPS footprint + SMB target: **Redox is the pragmatic broker** for breadth (Epic/Cerner/athena/eCW in one contract) but the $30K floor is steep for current stage. **DrChrono direct + Elation direct + athenahealth direct + Redox for everything else** is the more capital-efficient path. **1upHealth or HAPI FHIR** could be an internal canonical-FHIR persistence layer if QuillMD wants R4 storage decoupled from downstream EHR-specific quirks. Particle Health + Health Gorilla are oriented at **read** (cross-org chart context) — relevant if QuillMD ever needs longitudinal context pull-forward, less so for pushing notes today.

---

## D. Per-EHR Depth Assessment

Scoring legend: ✅ strong / ⚠ partial-conditional / ❌ weak / ❓ unknown.

| Dimension | **Epic** (Showroom + Garden Plot) | **athenahealth** (Marketplace) | **eClinicalWorks** | **DrChrono** (EverHealth) | **Elation Health** |
|---|---|---|---|---|---|
| **API maturity** | ✅ FHIR R4, SMART-on-FHIR, HL7v2, CDA, proprietary Interconnect | ✅ REST + FHIR R4, OAuth2; sandbox stable | ⚠ FHIR R4 (CMS minimum), separate proprietary "Open API" for deeper write | ⚠ Proprietary REST v4 + partial FHIR; clinical_note has structured sub-sections; versioning stable | ✅ REST API 2.0 + FHIR R4 + HL7; FHIR-first posture |
| **Write access** (SOAP / ICD-10 / CPT / Rx) | ⚠ `DocumentReference.Create` per-section; `Condition.Create`, `Observation.Create`, `MedicationRequest.Create` available **gated by Workshop scope + per-site approval** | ✅ FHIR `DocumentReference` POST/PUT supported; encounter + payment write POST-capable; CPT/Rx via proprietary endpoints | ⚠ Free FHIR largely read; "Progress Note direct write" exists but requires **contracted Open API access** — gated, sponsor-required | ✅ Read+write on `clinical_notes`, `appointments`, `patients`, `medications`, problems, billing line items | ✅ POST `/api/2.0/visit_notes` and `/non_visit_notes` (free-text + structured bullets incl. SOAP, problems, plan, billing); Rx via RxInform |
| **Auth complexity** | ⚠⚠ OAuth2 + SMART + per-customer client registration + Workshop/Toolbox review; manual approval at each Epic site | ⚠ OAuth2 (Auth-Code + Client-Credentials); single multi-tenant instance, one cert covers all practices | ⚠⚠ OAuth2 + eCW Developer Portal + customer sponsorship before production keys | ✅ Standard OAuth2, self-serve app creation | ✅ OAuth2 (Auth-Code or Client-Credentials); per-practice tokens; partner registration |
| **Cost to integrate** | ❌ Showroom: Connection Hub ~$500/yr; Toolbox curated; Workshop = co-dev with equity/rev-share + warranty; Vendor Services fees can run six figures | ⚠ No setup fees; **15-30% rev-share** of partner revenue on Marketplace-sourced deals; build $25k-$200k typical | ⚠ Certified FHIR free; contracted Open API undisclosed; community reports $500-$2k per integration + sponsor practice fees | ✅ **Free** dev account, free sandbox; Marketplace listing free; no rev-share gate | ⚠ Partner program disclosed but pricing undisclosed; HITRUST + BAA required; light/no upfront fee for small partners, rev-share possible |
| **Time to integrate** | ❌ 3-12 months end-to-end; per-customer go-live adds weeks each | ⚠ 6-12 weeks for Marketplace cert; 1.5-8 months full build | ❌ Slow — 6-10 weeks small-practice go-live **after** contracted access negotiation (months) | ✅ **2-6 weeks** (QuillMD has working DrChrono integration on CRM, marginal cost near zero) | ✅ **2-8 weeks**; some integration partners cite "3-5 business days" post-BAA |
| **BAA** | ✅ Standard via Showroom partner agreement (negotiated, lengthy) | ✅ Standard; HITRUST self-assessment within 90 days of GA | ✅ Standard in contracted-access bundle (heavy paperwork) | ✅ Standard, auto-attached to API terms | ✅ Required of marketplace partners + practices activating |
| **Practice friction** | ❌ Per-site approval at every Epic customer | ✅ Practice self-activates Marketplace apps from athenaOne admin UI | ⚠ Customer must sponsor contracted access | ✅ Doctor self-installs from Marketplace + OAuth consent | ✅ Practice admin connects via Partner Hub; activation 3-5 business days |
| **Audit-log support** (§164.312(b)) | ✅ Every FHIR write records caller client_id + user + timestamp + encounter | ✅ Writes carry partner identity + user OAuth scope + timestamp | ✅ Audit logging mandatory; eCW captures writes through Open API | ⚠ API writes stamped with API-app identity; per-action "who-did-what" lighter than enterprise EHRs | ✅ Visit-note writes record API client + linked Elation user |

**Per-EHR meaning for QuillMD:**

**Epic.** Highest-value market but worst fit for a solo-doctor SaaS today. Workshop-tier write to `DocumentReference` is technically clean and ambient-scribe-friendly (per-section SOAP write), but the 3-12 month integration + per-site sponsorship + equity/rev-share posture makes it Year-2+. **Garden Plot is the right wedge** but it's still Epic underneath, Workshop rules still apply. **Decision point: pursue once first design-partner Epic customer materializes; not before.**

**athenahealth.** Best risk-adjusted Phase 1 target. Single multi-tenant cloud means one certification unlocks every customer. `DocumentReference` write is standard FHIR. OAuth is sane. Practice activation is self-serve from the athenaOne admin UI. The **15-30% Marketplace rev-share** is the real economic cost — must be modeled before commitment. Realistic 3-4 month path to first paying customer.

**eClinicalWorks.** **Avoid in v1.** Free FHIR is read-biased; the write-capable Open API requires contracted relationship + customer sponsorship + enrollment that looks like Epic-lite in process without Epic's market share. Every serious competitor either outsources via Vim (Heidi) or omits eCW entirely (Ambience). **Revisit only if a specific bariatric/endocrine customer drags QuillMD in.**

**DrChrono.** Lowest-cost on-ramp and QuillMD already has plumbing on the sister CRM. Free dev account, write-capable `clinical_notes` endpoint with structured sub-sections, OAuth self-serve, no rev-share. The audit-trail granularity is the one §164.312(b) item to harden — capture user→note linkage on QuillMD's side and write that through. **Lowest-friction first integration.**

**Elation Health.** Strongest cultural and product fit for QuillMD's solo-doctor / weight-management / endocrine positioning — primary-care/DPC-native, FHIR-first, supports POST `non_visit_notes` and `visit_notes` with SOAP-style structured fields plus Rx via RxInform. Activation is days, not months. The remaining unknown is partner-tier pricing (not public), but Elation's posture toward small partners is materially friendlier than Epic/eCW. **Strongest commercial-fit first integration if QuillMD's pipeline supports it.**

---

## E. Competitive Landscape

| Competitor | EHRs claimed | Depth | Mechanism | Target market |
|---|---|---|---|---|
| **Abridge** | Epic, athena, eCW, Cerner, AllScripts, NextGen | Epic: notes + orders pilot. Athena: co-branded. Others: thin / marketing-soft. | Epic Workshop / Pals & Partners; athena marketplace | Health systems |
| **Microsoft Dragon Copilot** (formerly Nuance DAX) | Epic, athena, MEDITECH | Bi-directional notes + FHIR reads + order assist | Epic App Orchard + **SMART on FHIR R4** (publicly documented) | Health systems |
| **Suki** | Epic, Oracle, athena, MEDITECH | Bi-directional + **Rx order staging** (first ambient scribe to claim) | Epic App Orchard + native MEDITECH APIs | Mid-to-enterprise |
| **DeepScribe** | 9 named (Epic, athena, eCW, ModMed, AdvancedMD, DrChrono, Flatiron, Ontada, OMS) | Epic SmartData bi-dir; per-EHR depth otherwise unspecified | Direct API | Mid-market specialty (oncology lean) |
| **Ambience Healthcare** | Epic, Cerner, athena | Deepest dual Epic + Cerner write (DynDoc) | Epic Ambient Module + native APIs | Health systems |
| **Augmedix** | athena, Epic, Cerner, MEDITECH, iKnowMed, eCW, NextGen | Marketed broad, depth opaque | Not disclosed (likely HL7 + RPA legacy) | Hospital + mid |
| **Heidi Health** | Epic, athena, eCW (via Vim) | Push-to-chart on paid tier only; SmartSections | Marketplace + Vim middleware | Solo + small group |
| **Freed AI** | "Top browser-based" (unnamed) | Chrome-extension paste; **no structured write-back** | Browser automation | Solo |
| **Notable Health** | Epic, Oracle, Cerner, athena, MEDITECH | Bi-dir; RPA-augmented | API + RPA + HL7 | Health systems (workflow automation, not pure scribe) |

### E.1 — The bar QuillMD needs to clear

Table-stakes in 2026 is **named Epic + athena + (Cerner or eCW) coverage with at least note write-back**. Anyone serious in this space claims it. Differentiation tiers up from there:
1. Epic App Orchard + SMART on FHIR R4 with FHIR read for pull-forward (Dragon Copilot bar);
2. Bi-directional structured writes into SmartData Elements / SmartSections (DeepScribe, Heidi, Ambience);
3. Order staging + Rx (Suki first, Abridge in pilot).

The naked-eye floor for a credible health-system sales conversation is bi-directional Epic via SmartData + ONE second EHR done natively (not RPA). Notably, **only Dragon Copilot publicly documents SMART on FHIR R4** — QuillMD quoting that explicitly in a sales deck is a differentiator on its own.

### E.2 — Soft spots in competitor coverage

Three soft spots QuillMD can attack:

1. **eClinicalWorks is consistently outsourced or omitted.** Heidi uses Vim middleware. Ambience explicitly excludes it. Augmedix marketing is vague. A first-party eCW integration would be a genuine wedge — but only IF a specific paying customer requires it (otherwise the contracted-access friction is uneconomic).

2. **Solo-doc and small-group tiers are dominated by paste-tier products.** Freed's Chrome extension. Heidi's lower tier requires copy/paste. There is no scribe with REAL API write-back at a $79-$129 self-serve PMPM price point — Heidi's "Together" tier is the closest, and it is gated heavily.

3. **Most competitor marketing pages fail the "is this real?" smell test.** Abridge's integrations URL 404s. Suki's was 404 on the canonical slug. Freed names no EHRs at all. Augmedix lists seven without case studies. Investors will read these claims at face value; **QuillMD can win credibility just by being specific** (named EHR + named customer + named module).

### E.3 — QuillMD-specific differentiation opportunities

1. **Solo-doc + real bi-directional integration at $89-$129 PMPM** is an open niche. A QuillMD bundle at that price point with named DrChrono + Elation + athena Marketplace + first-party eCW (later) would not have a direct competitor.

2. **Interpreter mode** (validated GREEN as of 2026-05-13) is genuinely absent from every competitor surveyed. None markets multilingual ambient capture as a first-class feature. This is an outpatient-immigrant-clinic and FQHC sales wedge competitors literally cannot answer today.

3. **Bariatrics + endocrine specialty depth.** DeepScribe goes deep in oncology via Flatiron/Ontada/iKnowMed. ModMed handles derm/ortho. Nobody publicly leads on bariatrics or endocrine — these are template-heavy, longitudinal-care specialties where pre-built structured templates, GLP-1 / weight-trajectory pull-forward, and labs-aware note generation would beat a horizontal scribe.

**Combined, these three (solo-doc pricing + interpreter + endocrine/bariatrics templates) sell a product none of the nine competitors map to directly.** The integration roadmap should reinforce, not dilute, this triple.

---

## F. Recommended Roadmap

### Phase 0 — MVP integration (one EHR, ship end-to-end)

**Recommendation: DrChrono first, Elation second.**

The case for DrChrono as Phase 0:
- QuillMD already has working DrChrono integration on the sister meddoc-pro CRM. The lift to TranscribeMD is engineering work only — no vendor relationship cost, no sponsorship, no BAA negotiation (already in place).
- Free dev account; OAuth self-serve; no rev-share to ship.
- 2-6 week realistic engineering scope (S/M).
- Mid-tier pricing fits QuillMD's existing customer profile.
- Provides architectural validation for a single end-to-end push: capture audio → SOAP → ICD-10 + CPT → push to DrChrono `clinical_notes` with structured sections + auto-attach to patient encounter.

The case for Elation as a fast-follow:
- Strongest commercial fit for QuillMD's positioning (solo doctor + primary care + DPC + bariatrics-adjacent).
- 2-8 week integration; activation 3-5 business days post-BAA.
- FHIR-first; native SOAP-style structured note write.
- KLAS Best in Small-Practice Ambulatory 2025 + 2026 — a credibility halo.

**Pilot doctor unlock value (DrChrono as Phase 0):**
- Audio capture in QuillMD → signed SOAP automatically appears in the matching DrChrono patient encounter, with HPI / A&P / Plan as discrete fields, ICD-10 + CPT codes attached to the billing record, Rx drafts staged in the medications module.
- Net for the doctor: **eliminates manual copy-paste**. QuillMD claims its end-to-end pipeline value (audio → signed chart-ready note + codes + Rx) for the first time.

**BAA + compliance overhead:** DrChrono BAA is already executed via QuillMD's existing relationship (sister CRM). New scope: extend the existing BAA to cover TranscribeMD's data flows (notes + codes write-back). Light lift, 1-2 weeks legal.

**Effort estimate: Medium.** ~2-4 weeks engineering + 1-2 weeks BAA scoping. Tests + audit-log integration are the load-bearing items.

**Risks:**
- DrChrono's audit-trail granularity is lighter than enterprise EHRs. QuillMD must keep its own §164.312(b) audit linking user → note → push event so the chain is reconstructable.
- DrChrono's API stability has been generally good but versioned changes have caused breakage on the CRM in the past. Pin a version + monitor changelogs.

**Decision point at end of Phase 0:** Did at least one paying customer use the DrChrono integration in production? Did the integration generate measurable workflow-time savings? If yes → Phase 1. If no → diagnose product or positioning, NOT pile on more EHRs.

### Phase 1 — Second and third EHR (commercial scale)

**Recommendation: Elation Health, then athenahealth.**

**Elation:**
- 2-8 weeks engineering.
- FHIR R4 + REST 2.0 API surface.
- Partner Hub registration; BAA required.
- Partner-tier pricing not public — surface in commercial conversations.

**athenahealth:**
- 6-12 weeks Marketplace certification + integration build.
- **15-30% revenue share on Marketplace-sourced deals.** Must be modeled before commitment — at a $129 PMPM customer, that's $19-$39/month/customer paid to athena. Defensible because Marketplace is the de facto sales channel, but the cost has to be priced in.
- Decision point: do we go Marketplace-listed (rev-share) or partner-direct (no Marketplace but no rev-share, no sales surface)?

**Indirect (Redox) at this point — no, not yet.** Redox's $30K floor is steep when QuillMD has only 2 direct integrations live. Revisit after Phase 1 expansion when 3rd-5th EHR coverage is the constraint.

**Risks:**
- athena rev-share economics could disqualify low-margin segments. Validate against pilot economics before signing the partnership agreement.
- Elation pricing tier might land in a place that's incompatible with the partner-economics positioning (i.e., they want a higher commit than QuillMD's customer count justifies).

### Phase 2 — Broad coverage + enterprise wedge

**Two parallel decisions:**

**(a) Epic Garden Plot (or full Epic Workshop) — if and only if a sponsoring customer materializes.** Epic's per-customer approval gate means QuillMD literally cannot pursue Epic until a paying customer is willing to be the sponsor. Decision point: track the customer pipeline for any QuillMD prospect with Epic in production; pivot to Epic Workshop when one materializes. No earlier.

**(b) Redox as broker for everything else.** When QuillMD's customer pipeline includes Cerner, NextGen, Allscripts, or legacy eCW practices that aren't directly covered, switch on Redox to fan-out across that long tail. $30K floor is justified once 3-5 broker-only EHRs are in play.

**Coverage target end-of-Phase-2:** 60-70% of US ambulatory docs reachable. (DrChrono + Elation + athena ≈ 8-15% direct; Epic + Redox ≈ 50%+ via broker; remaining gap is the long tail.)

**Charm Health** is a wildcard. If bariatrics + weight-management becomes QuillMD's killer-vertical sales motion, **Charm Health belongs in Phase 1 ahead of athenahealth.** This is the single most important decision-fork in the roadmap and depends entirely on QuillMD's specialty positioning (see Section G).

### Risks across the roadmap

| Risk | Mitigation |
|---|---|
| **Epic's own EpicAI Charting launched Feb 2026** | Position QuillMD's integration explicitly: "QuillMD's note + codes flow back into your Epic chart, regardless of which AI captured them." Epic's competing scribe doesn't write to other EHRs. |
| **Specialty-template depth competitors don't have** | Bariatrics + endocrine + interpreter mode are the moat. Each EHR integration should ship with the corresponding specialty templates. |
| **athena rev-share economics could be too high** | Model post-share margin at intended PMPM. If <40%, push for direct partnership outside Marketplace. |
| **DrChrono's audit granularity is lighter than enterprise EHRs** | QuillMD's own audit_logs table is already §164.312(b)-compliant (REVOKE-locked, pinned via PR-C of the 2026-05-05 audit). User → note → push-event must be linkable end-to-end on QuillMD's side. |
| **Customer mix could shift to favor a different EHR mid-Phase-1** | Re-evaluate every 6 customers signed. The Phase 1 EHR order is recommendation, not commitment. |

---

## G. Open Questions for Kasra

These genuinely need input before Phase 0 implementation work begins:

1. **What's the actual customer pipeline?** The DrChrono-first recommendation depends on QuillMD having DrChrono prospects (or the willingness to put the integration in front of new prospects). If the live pipeline is heavily Elation-DPC or athena-mid-market, the order changes.

2. **Specialty mix going-forward — bariatrics-first or generalist?** If bariatrics + weight management is the killer wedge, **Charm Health moves to Phase 1 ahead of athenahealth** (it's the only EHR with native specialty fit). If positioning is generalist primary care, the recommended order holds.

3. **Geographic + market focus — US-only, or international?** Everything in this roadmap is US-centric. If QuillMD is targeting Australian / European primary care, the landscape shifts heavily (Best Practice, MedicalDirector, Bp Premier in AU; EMIS, SystmOne, TPP in UK).

4. **Capital constraints — Redox $30K/yr commit now vs deferred?** If QuillMD has runway + customer volume to absorb $30K/yr Redox today, it shortens Phase 2 dramatically. If not, the direct-integration approach (DrChrono → Elation → athena) gates Phase 2 on customer concentration.

5. **Marketplace rev-share posture for athena.** Will QuillMD accept a 15-30% rev-share on Marketplace-sourced deals, or insist on partner-direct? Affects pricing model + commercial conversations.

6. **Interpreter-mode positioning.** Should Phase 0 demo the multilingual capture → English-pushed-note flow (Spanish source, English chart write-back)? This is a unique-to-QuillMD demo moment that no competitor can show.

7. **Pricing-vs-feature decision — is EHR integration a free feature, a paid tier feature, or a paid add-on?** Affects every subsequent decision (revenue model, customer acquisition, rev-share economics).

8. **Audit-log harmonization — should QuillMD's audit row include the EHR push event by default, or only when an EHR integration is live?** Architectural decision; affects schema for the EHR_PUSH_SUCCESS / EHR_PUSH_FAILED audit actions.

9. **Sponsor relationship — has Kasra or QuillMD spoken to any Epic-using customer or prospect about being a sponsor?** Decision point for when to pivot toward Epic Workshop in Phase 2. The longer this is silent, the further out Phase 2(a) slides.

10. **Charm Health depth.** This roadmap recommends Charm in Phase 1 if bariatrics is killer-vertical, but the agent research found "unknown" market share for Charm. A short pilot conversation with Charm Health business development would surface their integration friction tier (partner program structure, BAA posture, build-vs-buy mindset). Worth a 30-min outreach in parallel with Phase 0 engineering.

---

## Sources

- Definitive Healthcare — Top Ambulatory EHR Vendors (Oct 2025)
- EHR Source — Top EHR Vendors (Feb 2026)
- Grand View Research — US Ambulatory EHR Market Size (2024)
- KLAS — Small Practice Ambulatory Best-in-KLAS (2025, 2026)
- ONC FHIR Ecosystem / US Core IG STU 6.1.0
- HL7 SMART App Launch v2.2
- Epic on FHIR + Epic Vendor Services
- athenahealth Developer Portal + Marketplace FAQ
- DrChrono Partners + API docs
- Elation Health API + Partner Hub
- 6B Health — eClinicalWorks coverage gaps writeup
- Mirth Support — HL7 Integration Engines (2026)
- Redox / Particle Health / 1upHealth / Health Gorilla / Smile CDR
- Competitor sites: Abridge, Microsoft Dragon Copilot, Suki, DeepScribe, Ambience, Augmedix, Heidi Health, Freed AI, Notable Health

Full URL list in the four research transcripts archived alongside this document.
