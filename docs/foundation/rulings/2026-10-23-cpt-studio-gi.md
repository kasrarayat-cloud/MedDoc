# CPT Studio — standalone GI-first CPT service at cpt.quillmd.com — 2026-10-23

Received directly from the owner in this session on 23 October 2026, as pasted
instruction text plus the owner's own messages, before any CPT Studio code,
provider request or host change. Recorded by the receiving session in its first
commit, per AGENTS.md.

## Owner messages, verbatim

Design approval (recorded in the design package's `DESIGN-APPROVAL.json`,
2026-10-23T20:37:53Z):

> Design is fine what is nexty?

Priority note accompanying the second brief:

> just addedd another proirity job to buidl category becasue we want to liek
> sperat each medical category in roder to optimzie and high accuracy

Design package link supplied by the owner (downloaded to session scratch,
verified, not committed): SwissTransfer transfer
`CPT-Studio-Design-Preview-20261023.zip`, 283,850 bytes, sha256
`6a7701358ab814ee098d265f6a33f7616794a084a5fab3ea69fefb07bf973850`. Its
`OPUS-START-PROMPT.txt` is byte-for-byte the first brief below.

## First brief (implementation), verbatim

> Implement CPT Studio from this approved design. The owner approved the
> appearance with: "Design is fine what is nexty?" Preserve the layout,
> typography, colors and interaction design. Use cpt.quillmd.com for this
> standalone CPT-only service; keep it independent of QuillMD's form completion
> and clinical generation pipeline.
>
> Read AGENTS.md, README.md, OPUS-IMPLEMENTATION-HANDOFF.md, DOMAIN-HANDOFF.md
> and DESIGN-VERIFICATION.json. This package contains a design prototype, not a
> working clinical coding backend. Opus 5.5 is the requested implementation
> assistant; that does not select Opus as the runtime medical coding engine.
>
> First milestone: one real end-to-end, authenticated, synthetic-only
> demonstration. Start with a documented US outpatient office-visit case in
> gastroenterology as a test fixture, without restricting the product to that
> specialty or claiming validation across other specialties.
>
> 1. Inspect the actual repository and server state using the server session's
>    existing authorized access. Reuse applicable deployment conventions and
>    coordinate with any active deployment owner. Preserve app.quillmd.com and
>    unrelated services. DNS already points cpt.quillmd.com to 147.189.172.8;
>    do not create a duplicate. Dedicated CPT hosting and a valid HTTPS
>    certificate are not installed by this package.
> 2. Replace the simulated upload with real PDF/DOCX/plain-text ingestion.
>    Preserve immutable originals and hashes; expose extraction/OCR errors.
>    Isolate records and files by authenticated user/workspace. Support service
>    date, setting and specialty as encounter context.
> 3. Integrate the existing authorized Corti account as an initial CPT proposal
>    adapter. Preserve raw responses and exact source evidence. Keep provider
>    interfaces interchangeable for later Astra/Fable comparisons. Do not turn
>    lower-confidence candidates into selected codes or treat model agreement as
>    verification.
> 4. Implement reference/rule validation as a separate layer, tied to
>    authorized sources and service-date applicability. If access or source
>    coverage is unavailable, report precisely what remains unverified; do not
>    invent a descriptor, percentage, official rule or pass result. Resolve
>    documentation gaps through targeted clarification, not invented clinical
>    facts.
> 5. Persist the source revision, proposals, supporting passages, decisions and
>    actual reviewer identity/time. Label synthetic agent reviews accurately.
>    Reload must retain the correct revision and decisions. Changed source must
>    invalidate affected approvals.
> 6. Produce an actual downloadable report containing the persisted reviewed
>    selections, supporting evidence and unresolved limitations. Draft and
>    reviewed reports must remain distinct. Exclude rejected/unsupported
>    proposals from approved selections. Verify the downloaded file itself, not
>    just the export button.
> 7. Install a protected synthetic demonstration at cpt.quillmd.com with normal
>    HTTPS verification. Recheck the existing app's health. Exercise the
>    ordinary browser flow from new upload through review, reload and report
>    download; preserve failures and diagnose before another attempt.
>
> Use existing project-authorized accounts and standing private synthetic
> testing authority where applicable. Use fresh run/authorization identities and
> bounded, duplicate-safe jobs with finite deadlines and Stop. Retain historical
> usage, reservations and unknown costs; do not reset counters or invent
> credits. Do not make new purchases, agreements, credit top-ups, real-patient
> uploads, claims submissions or a public clinical launch.
>
> After the first functional demonstration, compare Corti, Astra/Fable
> reference-assisted approaches and combinations on the same independently
> adjudicated specialty cases before selecting the production engine. Measure
> complete-case accuracy, missed/extra codes, modifiers, review frequency and
> actual cost. Do not promise 100% accuracy or payer payment.
>
> Carry routine authorized failures through repair and meaningful
> verification. Do not use hardcoded sample codes as live output or weaken
> validators to manufacture success. If an external dependency cannot be
> resolved with existing access, finish independent preparation and report the
> exact remaining dependency once.
>
> Final report: installed revision, protected URL, new synthetic encounter,
> actual provider usage, browser/reload results, downloadable report
> comparison, preservation checks and remaining material limits. Distinguish
> installed software, live provider success, coding correctness and export
> verification.

## Second brief (GI priority), verbatim

> Build the working CPT Studio website at **cpt.quillmd.com**, using the
> approved design. Gastroenterology (GI) is my first priority.
>
> Inspect the existing implementation before changing anything. Preserve
> completed work, the approved appearance and the existing QuillMD application.
> Continue implementation through installation and meaningful verification
> using available authorized access.
>
> **1. One GI workspace**
>
> The user-facing product must have ONE Gastroenterology workspace, ONE
> document-upload flow and ONE combined CPT results screen.
>
> Do not create separate navigation tabs, dashboards or required category
> dropdowns for EGD, colonoscopy, EUS, ERCP or office visits.
>
> The doctor uploads a GI document. The system identifies the documented
> services automatically and applies the appropriate coding checks internally.
> Documents containing multiple services must produce one combined review.
>
> Broad GI coverage is the product goal. Internal service families should
> include:
>
> - Office/outpatient evaluation and management.
> - Upper GI endoscopy, including EGD.
> - Colonoscopy.
> - Flexible sigmoidoscopy.
> - Endoscopic ultrasound.
> - ERCP.
> - Other GI services, with extensible internal profiles.
>
> These are internal routing and validation profiles, not separate sections
> the doctor must navigate. Do not assume this list exhausts GI practice.
> Clearly identify unsupported services within the affected result.
>
> **2. Preserve the approved design**
>
> Retain the approved layout, typography, colors, responsive behavior and
> evidence-beside-results experience.
>
> Replace simulated behavior with working functionality. Do not redesign the
> application or present hardcoded example codes as live AI output.
>
> Opus 5.5 is the implementation assistant. Runtime medical-coding engines are
> a separate architectural decision.
>
> **3. Read the original document directly**
>
> Support PDF, DOCX and pasted clinical text. Provide OCR for scanned documents
> where supported, with explicit extraction failures or limitations.
>
> Coding must operate directly on the original clinical documentation. It must
> not depend on QuillMD generating or filling a Word template first.
>
> Preserve the original file, its hash, extracted text and source locations.
> Maintain authenticated user/workspace isolation. Keep provider credentials
> server-side.
>
> Extract service date, care setting and professional-versus-facility billing
> context where documented. Ask a focused clarification only when an essential
> fact cannot be established.
>
> **4. Implement real CPT generation and verification**
>
> Use the existing authorized Corti account as the initial CPT-proposal
> adapter. Keep provider interfaces interchangeable so Astra, Fable or combined
> approaches can be evaluated later.
>
> Preserve raw provider responses, usage and supporting passages. Keep selected
> codes, alternatives and excluded candidates distinct.
>
> Return CPT-only results. Diagnoses may remain internal clinical context; do
> not add an ICD results section.
>
> Separate code generation from reference/rule verification. Use appropriately
> authorized CPT references and applicable service-date rules for code
> validity, modifiers, units and combinations. Apply relevant CMS NCCI checks
> while recognizing that they do not cover every CPT or payer requirement.
>
> When references are unavailable, identify what remains unverified. Never
> fabricate official descriptions, source versions, verification results or
> confidence percentages. Agreement between models is not proof of
> correctness.
>
> **5. Handle GI documentation accurately**
>
> Distinguish services performed today from scheduled, historical, canceled or
> uncertain services. Handle incomplete procedures using applicable rules and
> review rather than automatically treating them as completed or excluding
> them.
>
> Preserve documented technique, anatomical location, interventions and
> procedure extent. Preserve screening, surveillance or diagnostic intent when
> documented.
>
> Support multiple procedures in one encounter without duplicating or
> improperly unbundling services. Do not automatically add a separate
> office-visit code because a procedure report contains history or examination
> text.
>
> Link every proposal to exact source evidence. Scope missing information or
> verification problems to the affected service when logically independent; do
> not unnecessarily block unrelated supported suggestions.
>
> **6. Make review and exports real**
>
> Show proposed CPT codes, supporting passages, concise rationale, missing
> information, validation status and reference applicability when available.
>
> Allow acceptance, rejection and clarification. Save decisions against the
> correct source revision and internal validation-profile version. Record
> reviewer identity and time.
>
> Changes to source or encounter context must invalidate affected approvals
> and trigger appropriate revalidation. Reuse retained results when valid;
> avoid unnecessary duplicate paid predictions.
>
> Provide an actual downloadable coding report and structured CSV. Exports must
> match persisted decisions, exclude rejected selections from approved results,
> and distinguish drafts from reviewed reports. Retain original evidence and
> audit history.
>
> **7. Verify the complete GI workflow**
>
> Use fresh synthetic documents covering office visits, EGD, colonoscopy, mixed
> procedures, planned-but-not-performed services, incomplete procedures and
> missing critical information. Extend testing to other GI families before
> claiming their coverage.
>
> Verify automatic routing, exact evidence, applicable rules, clarification,
> review decisions, reload persistence and actual downloaded files.
>
> For accuracy evaluation, use independently adjudicated reference cases
> withheld from development. Report complete-case correctness, missed codes,
> extra codes, modifiers and human-review frequency separately for each
> internal service family. Keep the user interface unified.
>
> Do not claim full GI coverage or 100% accuracy from a few successful
> examples.
>
> **8. Install and report honestly**
>
> Verify current DNS, server configuration and HTTPS before deployment. The
> intended address is cpt.quillmd.com. Preserve app.quillmd.com and unrelated
> services. Use a valid trusted certificate and a protected synthetic
> demonstration.
>
> Follow AGENTS.md and existing project authority. Use existing authorized
> accounts, bounded requests, finite deadlines, duplicate prevention and a
> working Stop path. Reconcile unknown execution outcomes before resubmitting.
> Preserve historical usage, reservations, failures and unknown costs.
>
> No new subscriptions, purchases, agreements, real-patient processing, claims
> submission or public clinical launch are implied.
>
> Carry routine authorized failures through diagnosis, repair and
> verification. Never weaken correctness checks to manufacture a pass.
>
> Finish with the installed revision, protected URL, supported GI service
> families, actual provider usage, fresh browser results, reload verification,
> actual report-download comparison and precise remaining limitations.
> Distinguish software installation, provider success, coding correctness and
> export verification.

## Effective scope

- A standalone, CPT-only service at `cpt.quillmd.com`, independent of the
  QuillMD rebuild application, its database, users, form completion and
  clinical generation pipeline.
- Specialty categories are separate optimisation units. Gastroenterology is
  the first category: one GI workspace, one upload flow and one combined
  results screen; GI service families are internal, versioned routing and
  validation profiles.
- A login-protected, synthetic-only demonstration. Not a public clinical
  launch, not real-patient processing, not claims submission.
- The existing authorized Corti account is the initial proposal adapter.
  Provider calls follow the controls retained by the 2026-10-23 standing
  authority: bounded technical execution, single-flight sends, duplicate
  prevention, a working Stop, unknown outcomes reconciled before any
  resubmission, and preserved historical usage. No purchases, top-ups, new
  subscriptions or new agreements.
- Coding correctness, licensed CPT content and independent adjudication are
  separate questions that this directive does not settle.

## Session interpretation — recorded, not owner-ruled

These are the receiving session's implementation decisions under the
directive. They are listed so a later reader can tell them apart from what the
owner said, and so any of them can be overruled.

1. **No CPT edition is licensed** (`docs/coding-cpt-licensing-handoff.md`).
   Descriptors stay withheld; CPT code-set membership for the service date is
   reported as not verified. Corti's display text is never shown as a
   descriptor.
2. **CMS public files with no click-through are used for Medicare indicators
   only** — the October 2026 PFS relative value file (RVU26D) and the
   2026-Q4 practitioner MUE table — keyed by code number, descriptors dropped
   at import, for internal synthetic evaluation. This follows the precedent of
   the 2026-10-16 Corti reassessment, which used RVU26D for code presence only.
3. **NCCI PTP edits are not connected.** CMS serves the PTP tables only
   through an AMA "End User Point and Click Agreement"
   (`/license/ama?file=...`) that limits use to CMS programs and prohibits
   commercial use. Accepting it is a new agreement, which the directive
   excludes. PTP checks are reported as not verified until the owner decides.
4. **A login-protected synthetic demonstration is not a public clinical
   launch**, by the owner's own wording ("protected synthetic
   demonstration").
5. **Routing's status reading is advisory; the reviewer decides every code
   (2026-10-24, after refutation round 4).** Rounds 1-4 confirmed 47, 49, 71
   and 99 defects: each round found new phrasings that the performed /
   planned / cancelled / incomplete reader misreads, in both directions. A
   reader of open clinical prose cannot be made complete, so nothing it decides
   is final: a status exclusion is a recommendation the reviewer must confirm
   (new decision action `confirm`) or reinstate before a reviewed report
   exists; approving a code means the reviewer read the whole document, not
   only the cited passages; the UI and every report say the service status is
   not verified. This adds a click per excluded code and is the directive's
   own instruction to handle status by "review rather than automatically
   treating them as completed or excluding them", applied to every status.
6. **How refutation is graded from round 5.** Misreadings of wording OUTSIDE
   every declared list are recorded as accuracy residuals
   (`cpt-studio/ACCURACY-RESIDUALS.md`), for the adjudicated evaluation the
   directive requires, and are not merge blockers. Critical and high stay
   reserved for: a code approved or removed without a reviewer decision,
   report or export errors, data loss, security, cost and memory limits,
   regressions, and misreadings of what the code declares it reads. This is a
   change of the session's own stopping rule, recorded so it can be
   overruled.

## Owner decision, 2026-10-25 — how the refutation rounds finish

Asked after refutation round 6 (63 findings, 59 confirmed, 40 critical/high and
not residual, against round 5's 48), verbatim:

> Round 6 found 40 blocking defects (48 last round). How should we finish?
> — Fix + one more check (Recommended): Repair all 40 now, making checkbox rows
> strict (unusual rows go to the reviewer as a question). Then run one more
> attack round. Fix anything it finds in the must-fix areas (data sent to Corti,
> time/memory limits, reports, approvals, security), record other misreadings as
> known limits, and ship. About 1.5 days.

The owner's answer: **"Fix + one more check (Recommended)"**.

What it changes, so a later session does not re-derive it:
- Repair round 4d repairs all 40 blocking round-6 findings. Check-box and status
  rows become strict: a box is trusted only on a row the reader can read
  unambiguously; any other row holds (a question for the reviewer), never ready
  and never newly excluded.
- Refutation round 7 attacks round 4d's head. After it, only the must-fix
  classes block the merge: a request sent to Corti that should not be sent; stage
  time or memory limits; a report or export that misstates persisted state; a
  code approved or removed from the decision set without a reviewer's decision;
  data loss; security. Every other confirmed misreading is recorded as a known
  limit (`cpt-studio/ACCURACY-RESIDUALS.md` and the PR body) and does not block.
- This supersedes interpretation 6's stopping rule for the end of this PR only;
  the hold-only rule and every gate stay as they are.
