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
7. **Input bounds that meet the stage limits (2026-10-26, after refutation
   round 7).** The owner's decision below makes stage time or memory limits a
   must-fix class. Where a reader's cost is inherent in the input rather than a
   defect in the code, the limit is met by a documented bound. Nothing is ever
   truncated: the input is refused or held.
   - A document naming procedures more than 1,000 times is not read. The
     analyze stage fails with a plain message naming the count, and nothing is
     sent.
   - A provider response citing more than 1,024 evidence passages is not used.
     It is refused whole and by count, as the 64 and 256 code caps are.
   - A check-box row with a mark past the document's first 1,000 marks is held,
     never paired.
   - A service line with more than eight negation words is not read for its own
     denial. The line above decides, and it can only hold.
   - The assess stage has 120 s and 768 MiB: twice the analyze stage's time, and
     its memory plus 256 MiB.

   No real report reaches the first four. Each is a constant
   (`settings.MAX_SERVICE_MENTIONS`, `corti.MAX_EVIDENCE`,
   `detect.B3_DOCUMENT_MARKS`, `detect._S2_OWN_LINE_TOKENS`,
   `settings.JOB_DEADLINE_SECONDS` and `ASSESS_MEMORY_BYTES`), and any can be
   raised or removed if the owner overrules it.

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

## Owner directive, 2026-10-27 — repair and expand the shared GI coding core

Received directly from the owner in session meddoc-pro-94 (909be030) on 27 October 2026, as pasted instruction
text, after the install of revision 2734a6f3 and the owner's own synthetic test of encounter
cb96adb2-2044-4160-9c69-12dbcbbc8028 ("GI_Complex_Case_Elena_Hartwell"). Recorded by the receiving session before
the work that depends on it is committed for review. Verbatim:

> Repair and expand CPT Studio’s shared GI coding core at https://cpt.quillmd.com. Carry the work through implementation, installation and meaningful verification. Preserve the approved design and one GI workspace.
>
> This is a general engine repair. Do not solve it with patient-name exceptions, document fingerprints, expected-code injection or patches that recognize individual test sentences.
>
> 1. Establish the actual installed state
>
> Inspect the current revision, active deployment owner, application code, retained documents, raw Corti responses, processing traces and existing tests. Coordinate deployment through one owner.
>
> Do not assume the previously reported revision is still current. Preserve the original failures, provider responses, decisions, audit history and downloaded reports. Keep app.quillmd.com, VoiceAssistMain and unrelated server resources unchanged.
>
> 2. Diagnose the shared failures before assigning their cause
>
> Trace the original ten GI tests and the Elena encounter:
>
> cb96adb2-2044-4160-9c69-12dbcbbc8028
>
> Its uploaded PDF has SHA256:
> 861a9940d0509fdf7c8de4745a1d798db5724679e1efd03e840f73538a51aeb5
>
> Observed Elena findings:
> - 43239 was proposed but held; its exported evidence omitted the actual biopsy actions.
> - 45385 was proposed with an incorrect incomplete-procedure warning despite documentation that the examination was complete and not discontinued.
> - 45380 was absent despite a separate descending-colon lesion sampled with forceps.
> - Physician and nursing entries conflict about tattoo injection. Determine whether the application detected this; the CSV alone does not establish that.
> - The export contains two undecided proposals, twelve informational alternatives and no approvals.
>
> Earlier tests also reported current E/M services classified as historical, an omitted EUS suggestion and incomplete clarification questions.
>
> For each failure, establish whether it originated in document extraction, Corti, adaptation, evidence selection, local validation or export. Do not blame the provider or application without tracing the actual data.
>
> 3. Implement a shared representation of documented services
>
> For each service, retain its source document and revision, service date, clinician, setting, anatomy, lesion identity, technique, extent, completion, supporting passages and uncertainty.
>
> Distinguish:
> - Performed, historical, planned, negated and uncertain services.
> - Complete examinations from incomplete examinations.
> - Lesions sampled, removed, untreated or scheduled for later treatment.
> - Separate lesions from multiple actions on the same lesion.
> - Routine procedure-related work from separately documented E/M.
> - Endoscopist services from anesthesia, pathology and facility services.
>
> Interpret negation and time within the relevant clause and service. An unrelated historical reference must not invalidate a current service. An unresected lesion must not make a completed colonoscopy incomplete.
>
> Use validated structured data and bounded extraction. Diagnose schema or validation failures rather than silently discarding unsupported parts of a response.
>
> 4. Add evidence and completeness verification
>
> Exact quotation matching is necessary but insufficient. Verify that each passage supports the proposed action, anatomy, technique and date.
>
> Build a source-based inventory of documented services independently of the proposed code list. Reconcile that inventory with Corti’s suggestions so missing services become visible.
>
> If a documented service has no supported proposal, expose it as unresolved and use a bounded second review when justified. Do not invent a code, automatically promote an alternative or repeatedly resend the same request.
>
> Ask all materially necessary clarification questions for the affected service. Preserve both sides of genuine conflicts. Keep supported services available for review while clearly showing that the encounter remains incomplete.
>
> Separate “this proposal is ready for review” from “the entire encounter has complete, verified coding.”
>
> 5. Expand GI coverage through internal service profiles
>
> Keep one user-facing GI workspace. Maintain an explicit coverage catalogue for:
> - Office/outpatient E/M.
> - EGD, esophagoscopy, colonoscopy and flexible sigmoidoscopy.
> - EUS and ERCP.
> - Enteroscopy and capsule studies.
> - Motility/manometry, pH/impedance and anorectal testing.
> - Feeding-tube procedures and advanced endoscopic treatments.
>
> Define the required documentation, supported interventions, exclusions, clarification requirements and verification evidence for each family.
>
> Complete the shared repair across currently supported families. Add broader families through the same architecture, with actual implementation and validation. Clearly identify any remaining unsupported service; do not silently omit it or advertise comprehensive GI coverage before it is established.
>
> 6. Connect authoritative rules without inventing verification
>
> Inventory the authorized CPT content, guidance and applicable dated CMS/payer references actually available to this product.
>
> Apply appropriate code-version, bundling, units, modifier, provider and setting checks. Keep practitioner and facility rules distinct.
>
> Do not hardcode unofficial descriptors or claim that code membership, modifiers or rules were verified when the necessary source is unavailable. Keep licensing and source gaps explicit while continuing independent engineering work.
>
> Do not sign agreements, buy subscriptions or credits, change payment settings or process real patients.
>
> 7. Verify the core across documents and services
>
> Use retained responses first to diagnose and test shared logic economically.
>
> Add meaningful regressions covering paraphrases, mixed dates, negation, separate lesions, combined procedures, incomplete documentation, conflicting checkboxes, pending pathology and completed versus discontinued examinations. Include Word, digital PDF and scanned/OCR input.
>
> Keep expected answers outside the coding input and implementation logic.
>
> After installation, perform purposeful fresh synthetic tests through the ordinary HTTPS interface: upload, processing, review, saved decisions, reload and actual report download. Identify automated synthetic approvals accurately.
>
> Arrange independent GI-coder adjudication for the accuracy benchmark. If qualified adjudication is unavailable, label expectations provisional and report that limitation rather than claiming clinical validation.
>
> Report separately:
> - Supported procedure families.
> - Correct complete code-and-modifier sets.
> - Missed services.
> - Unsupported additions.
> - Clarification and conflict handling.
> - Human-review requirements.
> - Browser, persistence and export integrity.
>
> Do not treat browser passes, exact quotations or file-integrity checks as coding-accuracy percentages. Do not promise 100% accuracy.
>
> 8. Execution and delivery
>
> Use the existing standing authority for necessary private synthetic testing. Do not reinstate superseded $8.15 or nine/ten-call funding gates. Preserve historical usage, reservations and unknown costs.
>
> Use small purposeful batches, finite deadlines, duplicate prevention and a working Stop path. Reconcile unknown execution outcomes before another submission. Actual provider authentication, quota or payment failures remain operational constraints.
>
> Deliver the installed revision, demonstrated root causes, general repairs, coverage matrix, fresh acceptance results, preserved failures, measured usage and exact remaining dependencies. Continue through repair and verification; do not stop after producing a plan or passing isolated unit tests.

### Session interpretation, 2026-10-27 — recorded, not owner-ruled

8. **The documented-service inventory is deterministic** (`studio/gi/services.py`, a clause-level reader run in the
   bounded assess child, its output validated by `services.validate`). No new runtime model, provider, key or
   account is added: choosing a coding engine stays the owner's separate decision (first brief), and a new key is a
   class (d) item. The inventory is advisory, like routing.
9. **Hold-only combination.** The documented service decides a code's status, but the routing-era reading is a
   second opinion that can only hold: a hedge, denial or cancellation in the code's own passage about that service
   holds it, a disagreement is never a new exclusion, and routing's own doubt about a family holds its codes. What it
   no longer does is let a fragment about something else, or a passage about another time, decide (the Elena 43239
   hold, the gi-01 and gi-05 E/M exclusions).
10. **The second review is automatic and bounded**: once per revision and service date, only after a successful
    primary request, only for a documented service of a supported family left without a supported proposal, with the
    text that documents that service, under the full send discipline. Its codes fill only unresolved items. It is an
    additional provider request funded by the standing authority; its usage is recorded like any other.
11. **A member-entered context value that differs from the document's is a conflict** with both sides kept, not an
    override (the Elena encounter's member-entered 1998-01-01 against a documented 20 October 2026). It is resolved by
    correcting or clearing the metadata or by an addendum.
12. **No qualified GI-coder adjudication is available to this session.** Every expectation in the regression corpus
    and the held-out acceptance set is an author expectation, labelled provisional; no accuracy percentage is claimed.
13. **Routing's family doubt is narrowed to today's report** (refines 9). Routing reads a family from its NAME, so
    its one-line family summary is often about another occurrence: a planned repeat in the plan ("Repeat colonoscopy
    in three years"), an earlier examination in the indication ("found at an outside colonoscopy on 2026-09-03", "no
    prior colonoscopy"). Read against the documented acts, that summary made clearly performed procedures uncertain
    (7 of 43 corpus documents). It now holds a performed service only through a contrary statement in today's own
    report: negated or cancelled outside history, indication and plan, or planned or historical inside procedure,
    findings, technique or impression. Routing's own doubt about today's service (a hedge, an ambiguous box row)
    still holds, as 9 says.
14. **An unresolved negation the inventory resolves does not hold a code.** When the routing-era reader's only doubt
    is a negation it could not resolve ("The examination was complete and was not discontinued") in a passage the
    inventory reads, clause by clause, as this service's own positive statement (its performance, a performed act,
    a completion read as complete), the code is not held for it; the detail names both readings. A hedge, a denial
    or a cancellation still holds. This is the Elena 45385 hold the earlier repair left in place.
15. **How three services are modelled** (provisional, for adjudication): a PEG placed during an upper endoscopy is
    that EGD's act, not a feeding-tube service; an EGD performed with an EUS is kept and marked included in the EUS
    (no code of its own is asked, its acts are still reconciled), where the corpus author modelled one EUS service;
    a procedure documented as "PROCEDURE PERFORMED: transoral esophagoscopy … the intended EGD could not be
    completed" is a performed esophagoscopy (no endpoint), where the corpus author expected an incomplete EGD. The
    three differences are recorded with their reasons in cpt-studio/tests/corpus/services/known_differences.json.
16. **The 43-document corpus is a development corpus.** The reader was repaired against it, so it is committed as a
    regression guard (tests/test_services_corpus.py), never reported as an accuracy measure. The live acceptance set
    (10 documents) is held out: it was written separately, and its documents and expectations were neither read
    nor run through the reader while repairing. The repairing sessions saw only its file names, sizes, one-line
    titles and source hashes (909be030 at 02:46Z, after the WIP 2 reader repairs; bc7df129 while taking over).
17. **No CPT fact is asserted without a connected source.** The coverage catalogue no longer says ESD "has no
    specific CPT code; reported as an unlisted procedure"; it says no code profile exists here and a coder decides.
18. **One deployment owner.** At 02:51Z on 27 October 2026 the owner chose "Take over now" in session
    meddoc-pro-01 (bc7df129) and stopped 909be030 (meddoc-pro-94), whose last commit was WIP 2 (9eb82f0d) and
    whose refutation workflow (wf_ce4e77bb-c22) died with it before any lens finished. From then on bc7df129 is the
    single owner of this branch, its install and its live verification.
19. **Nothing is sent while the service date is a member-vs-document conflict** (refines 11; bc7df129). A conflicted
    context has no date a request could carry, and a dateless request would be paid for and discarded once the date is
    settled. The predict stage records a not-sent run that says so (`ProviderRun.scope` `held: member_date_conflict`);
    the encounter is needs_clarification on the date question, not "provider failed"; correcting or clearing the
    metadata starts the request for the agreed date, and an identical retained result is reused. Setting, patient
    status and billing never enter a request, so their member conflicts only hold, as 11 says. The installed revision
    sent the member's date itself (the Elena 1998-01-01 request); WIP 3 sent a dateless request instead.
20. **The reader reads a soft line wrap as a space** (bc7df129, from a format harness that read every corpus document
    as text, as Word, as a digital PDF wrapped at 90 characters, and as a scan read with real OCR in the image). On
    WIP 3 the digital PDF read differently from the text in 13 of 43 documents and the scan in 38 of 43: a wrapped
    sentence line looked like a heading, and the attribution, lesion and act readers stop at line breaks. The reader
    now reads a same-length view of the text (`services.reflow`) in which a line break inside a sentence is a space:
    only after a long line of prose (25+ characters, 4+ words) that ends no sentence, label or answer of its own
    (`_answered_line`, the rule sentences are cut at), before a line that continues it in lower case or after a word
    that cannot end a line; never around a check-box, option, table, list or field row, nor inside an extraction
    block. Every offset and passage stays the text's own (each passage is re-read from the text at its offsets, and
    routing's box reader is given the text itself). The digital-PDF reading of every corpus document is a regression
    test with each remaining difference recorded with its reason (`tests/test_services_formats_corpus.py`,
    `format_known_differences.json`); a scanned report and a scanned sample of the corpus are read with real OCR
    wherever tesseract is installed (CI and the image). Proper-noun wraps and OCR misreads remain known limits.
21. **How this change's refutation pass finishes** (bc7df129). One full round runs on the finished diff, with nine
    lenses (false release, missed service, negation and time, provider sends, report and UI truth, cost and bounds,
    migration and upgrade, document formats, member-entered context), every finding re-run by a skeptic and graded as
    interpretation 6 grades it. Each repair of a blocking finding is then attacked once more by its own skeptic before
    merge, because in rounds 1-7 about a quarter of each round's findings were the previous round's repairs. Confirmed
    misreadings that do not block are recorded in `cpt-studio/ACCURACY-RESIDUALS.md` and the PR body. This takes the
    shape of the owner's 2026-10-25 decision for this change; the owner can overrule it.
22. **Refinements of 10 and 11 found by the triage skeptics** (bc7df129). A member value settles a conflict INSIDE the
    document only by choosing one of its values; any other value is a third side kept with them (a member-entered
    1998-01-01 against two documented dates had been accepted). A member conflict that no question asks about is asked
    once at the encounter, both sides named. The bounded second review (10) is never made after a primary response
    refused whole, nor while the service date is unknown, and without a known service date a dated act statement is
    held, never read as today's (a dated history line had produced a phantom performed service and a paid second
    review). The note's own dated title is only the FIRST dated title line near the top; a qualified one gives no date.
23. **A neutral list label's items are not read as done** (bc7df129, triage round 1 routing_level). Under a label that
    neither states nor denies performance ("Additional procedures:" over "EGD with balloon dilation.") the listed
    service is held for the reviewer, never ready and never excluded. Graded UNCLEAR: a coder may read the list as done,
    so this over-holds by design and is recorded as known limit sec:1 rather than repaired by a word list.
24. **The owner's strict-box decision (2026-10-25) applied to the documented-service reader** (bc7df129, triage round 2
    skeptics). A checked box or a checked "Yes" form field documents its act only inside a list of what was done, read
    structurally (the label directly over its run, or a printed item its field names), and only in a service a title, a
    statement or an instrument already documents; anywhere else it holds. What a consent or an authorization is for is
    held the same way. Removing the box promotions entirely was tried and rejected: it held 95 records the installed
    revision makes ready on unambiguous rows (an accepted-capability loss this session may not take), while the
    fail-closed form sends no second review for any of the fourteen consent, equipment, education, office and form-field
    documents in test_services_second_review (the skeptics' and this session's), and still sends one for a checked box
    under "Interventions:" (its positive control).

## Owner decision, 2026-10-27 (session ec5e7910) — narrow, install-first

Asked in session ec5e7910 at about 16:00Z on 27 October 2026, after the session found that refutation round r1 had left
63 blocking findings on this branch (seven repaired, integrated as `wip/r1-integ` b7715733) and that the account's
weekly usage stood at 92% with no extra usage enabled. Verbatim:

> With ~8% weekly usage left, how should I get the GI-core repair to installation?
> — Narrow, install-first (Recommended): Make the second Corti review reviewer-requested, never automatic. That removes most wrongful paid sends. Fix only the must-fix classes: wrong date sent to Corti, re-sending an identical request, reports or the UI misstating saved state, rollback safety, time/memory. Record the remaining misreadings as known limits; the reviewer still decides every code. Then tests, PR, CI, merge, install, and a fresh HTTPS Word/PDF walk with real downloads. This overrules interpretation 21 for this change. It may still run out before the install; if so I stop at a pushed checkpoint.

The owner's answer: **"Narrow, install-first (Recommended)"**.

What it changes, so a later session does not re-derive it:
- The bounded second review (interpretation 10) is made only when a workspace owner or reviewer asks for it, for the
  current assessment, under every bound 10, 19 and 22 set (once per revision and service date, a usable primary
  response, a known and unconflicted date, the identical-request rule). An assessment never queues one.
- Interpretation 21's grading is overruled for this change only. The merge is blocked by the must-fix classes of the
  owner's 2026-10-25 decision (read in full: a request sent to Corti that should not be sent, including a wrong or
  conflicting date and an identical re-send; stage time or memory limits; a report, export or screen that misstates
  persisted state; a code approved or removed from the decision set without a reviewer's decision; data loss; rollback
  safety; security). Every other confirmed r1 misreading is a known limit in `cpt-studio/ACCURACY-RESIDUALS.md` and the
  PR body; the reviewer decides every code.

### Session interpretation, 2026-10-27 (ec5e7910) — recorded, not owner-ruled

25. **One deployment owner, again.** Session 06f227b1 (which took this branch over from bc7df129 at 13:01Z) stopped at
    its account's usage limit at 15:03Z, and its repair workflows ended with it; no session was running at 15:50Z. The
    owner started session ec5e7910 to continue, so from 15:50Z ec5e7910 is the single owner of this branch, its install
    and its live verification. 06f227b1's unfinished cluster edits stay where it left them (worktrees
    `.worktrees/cpt-r1fix-*`, backups `fix/partial/*.patch` in the save directory); the commits of this session name
    what they adopt from them.
26. **One deployment owner, again (7c8d38da).** Session ec5e7910 stopped at its account's weekly limit at 17:50Z on 27
    October 2026 (every later message was answered with the limit notice), and its workflow wf_d9952ac0-e1f lost seven
    agents mid-run. The owner opened session 7c8d38da and told it to continue, so from 19:20Z 7c8d38da is the single
    owner of this branch, its install and its live verification. Edits ec5e7910's agents had proven but not committed
    are committed by 7c8d38da, each commit naming its origin; ec5e7910's integration branch `wip/ec5-integ` carries on,
    and the unfinished cluster work continues in worktrees `.worktrees/cpt-7c8-*` branched from its head.

### Session interpretation, 2026-10-28 (7c8d38da) — recorded, not owner-ruled

27. **A status exclusion is a recommendation; a misread one is a known limit.** The must-fix class "a code approved or
    removed from the decision set without a reviewer's decision" (owner decisions of 2026-10-25 and 2026-10-27) is read
    with interpretation 5, which the code enforces at the integrated head 2fc8cde3d: every exclusion a documentation
    (status) check makes is reinstatable (`studio/validation/engine.py`, `reinstatable=s.excluded`; only an exclusion
    for scope or for no exact evidence is not, as at the installed revision) and stays in the decision set, and no
    reviewed report exists until the reviewer confirms it or reinstates the code (`studio/review.py`,
    `_assessment_blockers`: "<code> was excluded by a documentation check: confirm the exclusion or reinstate it").
    The decision set is the selected and the excluded proposals (as the installer's own rollback rules read it). A
    misreading that recommends excluding an act the document states done today - both readers reading it planned,
    historical, cancelled or negated - is therefore a wrong recommendation the reviewer decides, recorded as a known
    limit in `cpt-studio/ACCURACY-RESIDUALS.md`, like a misreading that makes a code ready or held. Class 4 stays for: an
    approval without a reviewer; a code that leaves the decision set (neither selected nor excluded) without one, as
    refutation phase 1's reports-0 did; an exclusion for a status reason that is not reinstatable or confirmable; and a
    reviewed report or export produced while an exclusion is undecided. Session ec5e7910's cluster brief had graded
    every exclusion of a done-today act as class 4; the repairs made under it stand (they remove wrong
    recommendations), and from refutation phase 2 (2026-10-28) such findings are graded by this interpretation. The
    owner's own list in the "Narrow, install-first" decision ("wrong date sent to Corti, re-sending an identical
    request, reports or the UI misstating saved state, rollback safety, time/memory") names no exclusion and says "the
    reviewer still decides every code". The owner may overrule this; the PR body and the install report say so.
28. **The service date is read by its source, and nothing is sent that the installed revision would not send.**
    Refutation phase 2 found the date sent to Corti taken from sources that are not this encounter's date of service:
    a fax's clocked "Date/Time:", a letter's "Date:", another discipline's dated title, a date of birth, a label's
    value with a bracket after it. Four rounds of qualifier words had each been refuted by the next paraphrase. The
    first repair (branch `wip/7c8-p2dates`) required a clean header block around the label: it closed every finding
    and asked the date of 8 of the 11 live encounters ("Date of procedure: 2026-10-14 ... not read as one"), of every
    PDF or Word upload and of 8,416 of the reading gate's 8,446 texts - a capability loss this session may not take
    (class b), so it was not merged. The rule this change carries instead (P2DN, then its skeptics' and the final
    refutation's fix rounds; ARCHITECTURE 5.2):
    - a document date is sent only from a date-of-service label's own value standing alone in its field (N1, N5);
      a dated title, a bare "Date:" or "Date/Time:" line, a letter's line, a dated service line or prose is evidence
      that can make the date a question, never the date - the installed revision's behaviour for those shapes. This
      supersedes interpretation 22's last sentence: no dated title gives the date;
    - a date of birth is never a candidate (N2); a member date is taken only when it equals a date some candidate
      states as its own value, never one the reader reads as another occurrence's (N3, N4);
    - only a labelled date written in a form the installed revision 057a7d398 reads is ever sent (N7): a day-first
      date, a table row's date or a label naming a time is asked.
    The family no structural rule closed without that capability loss - a labelled date the lines around it qualify
    as another occurrence's (a heading, a title, a field above or beside it) - stays as the installed revision has
    it, pinned as known limits, and is open for the owner: keep it, accept the structural rule's asks, or rule a
    narrower trade. The owner may overrule any of this; the PR body says so.

## Owner directive, 2026-10-28 — reliable GI interpretation and a usable synthetic demonstration

Received directly from the owner in session 7c8d38da on 28 October 2026, as pasted instruction text, after the install
of revision 2b82889f (PR #1440) and its report (PR #1444). Recorded by the receiving session in its first commit, before
the work that depends on it. Verbatim:

> Continue CPT Studio from installed revision 2b82889f and reports #1440/#1444. The next objective is reliable GI interpretation and a usable synthetic demonstration, beyond the completed narrow installation milestone.
>
> Inspect the original sources and retained responses for ho-01 through ho-04. Repair the shared extent, negation and date-field interpretation defects. Establish expected behavior from the source before editing; provisional author expectations are not automatically correct.
>
> For ho-04, distinguish elapsed physician time from a calendar service-date field. Preserve the explicit applicable date without ignoring genuine date conflicts. Do not introduce patient-specific patches or automatically merge the overly restrictive date branch.
>
> Inspect the documented wrong-occurrence date cases and recommend a source-based policy that preserves genuine uncertainty. Explain interpretations 27 and 28 through concrete product examples before changing their policy.
>
> Verify controlled recovery for conclusively not-sent requests after clarification. Preserve protections against duplicate submissions, unknown outcomes and automatic retries.
>
> Exercise the reviewer-requested EUS second-review path using an explicitly labelled synthetic review. Preserve raw results, decisions and usage; do not promote unsupported alternatives.
>
> Use parallel agents for independent investigation and verification, with one integration/deployment owner. Reuse retained evidence first, then run targeted fresh synthetic checks and actual reviewed downloads.
>
> Keep rollback protections intact. Finish with verified fixes, installed revision, remaining limitations and whether a complete doctor-facing synthetic demo is ready. Do not equate installation checks or test volume with clinical coding accuracy.

### Session interpretation, 2026-10-28 (7c8d38da, second round) — recorded, not owner-ruled

29. **The ten held-out documents are development documents from this round.** The owner directs this round to read
    ho-01..ho-04 and their retained responses, and ho-06 is the second-review case, so none of the ten can be
    acceptance evidence for this round's repairs. A fresh synthetic set, written by an author who reads neither the
    application code nor the repairs, is the acceptance set of the walk that follows; ho-01..ho-04 are re-run there as
    regressions only.
30. **One integration and deployment owner.** Session 7c8d38da is the single owner of this round's branch
    (`fix/cpt-studio-gi-interpretation-20261028`), its install and every live action (uploads, the second review,
    decisions, downloads). Its agents investigate and repair in their own worktrees and never act on the live service.

## Owner decisions, 2026-10-28 (session 7c8d38da, second round) — the wrong-occurrence date family and a demo account

Asked in session 7c8d38da at about 22:15Z on 28 October 2026, after the session explained interpretations 27 and 28
with product examples (a wrong status exclusion reinstated before a reviewed report exists; a right one confirmed; a
letter's "Date:" asked; an "Outside colonoscopy:" block whose "Procedure date: 09/03/2026" the installed revision sends
as today's date). Verbatim questions and the owner's answers:

> Which policy should this round adopt for service dates that the document itself marks as another occurrence's (e.g. an "Outside colonoscopy:" block whose "Procedure date: 09/03/2026" the installed revision sends as today's date)?
> — Narrow source rule (Recommended): Ask the date (never send it) when a heading, title or row field naming another occurrence (outside/prior/previous/cancelled/scheduled...) governs the label; neutral headings like 'Patient information:' unchanged. Prototype: 0 changes on all live, held-out, corpus and gate texts; ~9.6k constructed wrong-date sends become questions. A member cannot answer with the other occurrence's date (addendum only).

The owner's answer: **"Narrow source rule (Recommended)"**.

> For the doctor-facing demo, which account should a doctor use? Only two accounts exist today: your owner account and the verification agent account.
> — Separate demo reviewer (Recommended): I provision one new reviewer account in the GI workspace via manage.py provision, with a generated password stored 0600 on the server for you; decisions are attributed to it, not to you. A new credential (class d), so only with your yes.

The owner's answer: **"Separate demo reviewer (Recommended)"**.

What it changes, so a later session does not re-derive it:
- Interpretation 28's open family is ruled: a labelled date governed by a heading, a title or a field on its row that
  names another occurrence is asked, never sent, and a member's answer equal to that other occurrence's date is not
  taken (an addendum settles it). A neutral heading the reader cannot place changes nothing. The status field beside
  the label ("Status: Scheduled"), "Recall" and another discipline's undated title stay known limits.
- One new reviewer account is provisioned for doctor demonstrations, in the one GI workspace, as a declared step of this
  round's install; its password is generated on the server and kept there at mode 0600 for the owner.

### Session interpretation, 2026-10-29 (7c8d38da, second round) — recorded, not owner-ruled

31. **Interpretation 28's last claim, corrected by measurement.** "Nothing is sent that the installed revision would not
    send" was literally false for the install of 2b82889f: against 057a7d398 it sent a document date in 677 constructed
    texts of the 164,585-text broad date corpus where 057a7d398 asked (0 existing, live, corpus, verification or gate
    texts). A triage by shape found 522 wrong or uncertain (rule U: the header's only labelled date is another
    occurrence's, and the own date stands only in an addendum written after the body), 5 uncertain (an own date inside a
    block a heading names as another occurrence's - the owner's narrow source rule asks them) and 150 correct (an own date
    beside a qualified other-occurrence date, a numbered procedure part's own date, an addendum filling an empty field).
    This round asks the 527. Measured at the final head with dd.py and compare.py: against 2b82889f one document date is
    newly sent (the E/M time-statement shape of ho-04, the date 057a7d398 sends) and member answers are newly taken only
    where they equal the note's own dated service line (43, all taken by 057a7d398 too); against 057a7d398 document dates
    are sent only within the triage's correct shapes (130 of the 150, the others now asked by the round's BIRTH, PART and
    ORDER rules) and no member answer differs. The claim now reads: no document date is sent that differs from one the
    installed revision sends, and against 057a7d398 only in the triaged correct shapes.
32. **Negation scoped to the status word it governs.** "Examination complete, not aborted." no longer reads as the
    colonoscopy's denial. A bare such sentence releases the service only with corroboration in the family's own text and
    no unread procedure-level doubt; the release criterion is counterfactual - every newly performed reading is one the
    installed revision reads as performed once the misread sentence is removed. The unread-doubt guard is a word list and
    leaks on unseen phrasings; those leaks are known limits under interpretation 27 (the reviewer decides every code).
33. **Controlled recovery of conclusively not-sent requests.** A context save that settles a member date conflict makes
    the request when the run in use is a primary attempt that conclusively never reached the provider (recorded not
    sent, sent false, carrying its request, through the send door, never a sent and failed attempt of it), once per such
    save; every other save only re-checks. A second review recorded not sent, or cancelled before sending, no longer
    uses up the once-per-revision-and-date bound: a reviewer may ask again, explicitly. The protections stand: an unknown
    outcome blocks every send until a member reconciles it; an identical answered request is reused; a failed request is
    never sent again; nothing is retried automatically; concurrent saves and asks send once. Left for the owner: a
    not-sent primary attempt with no date question still recovers only by an addendum or a new upload, and a
    coding-endpoint refusal (401, 403, 429) is recorded failed and never re-sent identically.
34. **What labels a reviewer-requested second review.** The ask takes no body and an encounter cannot be renamed, so the
    synthetic label is the reviewer's account, its decision and reconciliation notes and the operator's evidence; the
    excerpt sent to Corti begins after the document's SYNTHETIC banner line. A request-level note, or a banner in every
    provider request, would be a product decision; both are listed for the owner.
35. **A document whose only labelled date is another occurrence's** asks the date and holds ANY member answer (an
    addendum settles it), because that date keeps speaking - stricter than the ruling's words, which name only a member
    answer equal to the other occurrence's date. Recorded so the owner can overrule it.
36. **Pre-existing stage-time defects found by this round's lenses were repaired**, not recorded: a pasted line of
    repeated status references (60.3 s at 2b82889f, now 8.3 s) and one of repeated E/M time statements (60.1 s, now 1.8 s)
    passed the analyze stage's 60 s; a third Resume in a row overflowed the job key (HTTP 500). One gate text (a
    50,087-character repeated "EUS" text) routes in about 57.5 s on both revisions, near the 60 s limit, and stays a known
    limit.
37. **Interpretation 31's member figure was wrong, and its "correct" class holds two texts the source contradicts.** A
    differential round (2026-10-29: three lenses and a verifier per finding, asking only whether the head is worse than
    the installed revision in a must-fix class) showed that the 37 member answers interpretation 31 counted, beside 6
    others, as "equal to the note's own dated service line" were not all that: in some the dated line was another,
    earlier service's ("EGD on 05/01/2019" in an office visit dated 10/13/2026), and that date reached the request. The
    integrator had accepted the class by its description without reading its members. The second fix round (5b125e737 and
    bae4e81ac, integrated as e5ea6c627 and 6546d778e) makes the date-of-birth, order and part doubt rules ask only: where
    they leave the note no own date, a member's answer counts only if the reading without them would take it, and a date
    of birth never answers. Measured at 6546d778e over the same 164,585 texts: against 2b82889f one document date is
    newly sent (ho-04's shape) and 6 member answers are newly taken (the head asks an outside colonoscopy's date that
    2b82889f sends, and the member's date equals the note's own dated title); against 057a7d398, 133 document dates are
    sent where it asks, and no member answer differs. Read member by member, the 133 hold two texts the source
    contradicts: lens:3705643aa10a ("Visit date: 05/01/2019" in an EGD note that opens "EGD: 11/04/2026") and
    lens:0d0e48706876 ("Date of service: 10/13/2026" beside "Colonoscopy - Referral date: 10/13/2026 - performed on
    11/04/2026"). The triage that called them correct read labels only, and a dated line naming the documented procedure
    is no label. 2b82889f sends both; so does this round, also with an E/M time statement added, where 2b82889f asked
    only because it misread "34 minutes" as a date. Closing them needs rule N1 to let a dated service line question the
    own label - interpretation 28's open family, which the owner ruled only for headings, titles and row fields - so they
    are listed for the owner (ACCURACY-RESIDUALS, gi2 dates-F1-n1). In the other 131, every other date is stated as
    another occurrence's on its own line or under its heading.

## Owner directive, 2026-10-29 — reliable shared GI interpretation (third round)

Received directly from the owner in session 7c8d38da on 29 October 2026 (about 18:05Z), as pasted instruction text,
after the install of revision 90377ec6f413 (PR #1445) and its report (PR #1447). Recorded by the receiving session in
its first commit, before the work that depends on it. Verbatim:

> Continue from installed CPT Studio revision 90377ec6f413 and reports #1445/#1447.
>
> The objective remains reliable shared GI interpretation. Successful installation and unchanged behavior versus an older revision are insufficient acceptance criteria.
>
> Prioritize h2-08: trace the original document, section boundaries, both service-date fields and the outbound request. A conflicting applicable service date must not be silently discarded because an unfamiliar heading inherits the Plan section. Repair the shared date/section binding, preserving genuine historical and planned dates.
>
> Then repair the shared extent/table interpretation and current-visit versus future-follow-up scope. Inspect the existing service inventory and repair its fact binding; do not assume a wholesale rewrite or add document-specific exceptions.
>
> Use source-reviewed expected facts and varied layouts/paraphrases. Known cases become regression tests. Keep a small independently written unseen set for acceptance. Require an independent adversarial review of correctness before freezing, rather than only comparison with the previous version.
>
> Keep Corti’s EUS omission separate. Do not invent codes, promote unsupported candidates or repeat unchanged requests indefinitely.
>
> Preserve original evidence, decisions, review safeguards and duplicate protection. Use parallel independent agents with one integration/deployment owner.
>
> After offline verification, perform minimal justified live synthetic checks, including the demo-reviewer login, clarification/recovery, persisted decisions, reload and actual reviewed downloads. Label synthetic approvals accurately.
>
> Report what is correct, what remains uncertain, provider omissions and demo readiness separately. Do not declare reliable coding while a known contradicted service date is still sent.

### Session interpretation, 2026-10-29 (7c8d38da, third round) — recorded, not owner-ruled

38. **The acceptance bar moves from "no worse than installed" to "right by the source".** The second round converged on a
    differential (never worse than the installed revision); the owner rules that insufficient. This round's repairs are
    judged against source-reviewed expected facts written per document, its adversarial review is told to find inputs
    the head reads WRONG by the source (not only differently from 2b82889f or 90377ec6f413), and the differential checks
    remain a safety net only.
39. **Known cases and the unseen set.** The fresh set h2-01..h2-10 and ho-01..ho-04 are known cases from this round on:
    they become regression tests with source-reviewed expected facts. A new, small, independently written set (h3) is the
    acceptance set: its author reads neither the application code nor the repairs, and this session reads it only after
    the code is frozen.
40. **Synthetic approvals and the demo account.** Every live approval is made by the agent account and labelled as agent
    review. The demo-reviewer account is a human account: the live check logs it in and reads its session, and makes no
    decision with it, so no synthetic approval is ever attributed to a human account.
41. **A contradicted service date is a blocker for any claim of reliable coding.** While any known source sends a date
    the document contradicts (h2-08 at 90377ec6f413), the report says so first and declares no reliable coding.

### Session interpretation, 2026-10-29 (7c8d38da, third round, after the investigations) — recorded, not owner-ruled

Made by the integration owner on reading four independent investigations (date/section binding, extent/tables, visit
scope, inventory fact binding), each with source-reviewed expected facts over varied layouts and paraphrases. Recorded
before the repairs that depend on them.

42. **The date binding.** A plan or history section governs a date label only while its reach lasts. A colon-less heading
    the section reader cannot place (a "neutral" heading: "Charge information", "Billing", "Visit details") ends that
    reach unless its words name a plan, a history, another occurrence, a service, an act or another document. A label
    no section governs speaks: it is read as a candidate that can only be ASKED, never sent by itself (so a heading
    vocabulary that misses a plan word over-asks rather than sends a planned date). Where such a label is the document's
    only date-of-service label, it is asked and a member's answer equal to it is taken (an accepted over-ask). Inside a
    plan with no block heading, the encounter's own date-of-service field speaks, and a visit or procedure date field
    is asked unless the plan item right before it names a later occurrence and its date is later than the visit's.
    A plan or history section opened by the document's own title governs no label. The setting and patient-status
    readers share this binding. The section boundaries themselves are not moved for dates (routing, extent and the
    inventory read them). Version labels stay as installed (the second round's precedent): encounters already read keep
    their recorded contexts; new uploads and member changes read under the new rules.
43. **E/M time basis.** A clinician's time on the date of service that its sentence frames as visit time, or that stands
    beside the document's own visit marker ("Face-to-face time: 24 minutes", "Physician time on the service date: 44
    minutes"), documents the time basis. It is a lower bound of the total time on the date, so it never over-levels; the
    level stays the reviewer's decision. A procedure's, sedation or interpretation time never counts.
44. **Today's visit and future follow-up.** Today's visit is established only by the document's own markers (a title in
    its head naming no other occurrence, a visit statement outside plan and history, a chief complaint, reason or MDM
    heading, MDM, or the visit's own time). A future occurrence (a return visit, labs, imaging, a repeat procedure) never
    establishes today's visit and is never presented as doubt about it. Planned-only documents and notes with no marker
    stay held: known limits, never ready.
45. **Tables.** There is one table model. A cell that holds only an answer answers its own column; a value bound to an
    extent column ends at its cell. A procedure-summary label over a summary table opens a procedure section; a table
    alone is never evidence that a service was done today.
46. **Inventory binding.** A past-tense denial in an act's own segment binds that act; a table answer binds to its own
    row's service. A table "Yes" states the act done only for a service already documented as performed (interpretation
    24); otherwise it holds. A stent placement or removal that is part of a documented exchange is held for the reviewer
    with the exchange named, never ready and never excluded. The ruled annotation behaviour (a white-out annotation
    names the page partial) is unchanged.
47. **Acceptance-set exposure.** A workflow journal preview showed the integration owner part of the sealed h3 author's
    summary (document shapes and some headings) before the code was frozen; the repair agents never saw it. A second
    sealed set, h4, was commissioned from a separate author whose only return is counts and hashes. h4 is the primary
    unseen acceptance set; h3 is reported as exposed to the integration owner, never as unseen.

### Session interpretation, 2026-10-29 (7c8d38da, third round, at integration) — recorded, not owner-ruled

Made by the integration owner on merging the four repairs and measuring the merged tree, before the independent
adversarial review. Each refines 42, 45 or 46 where an owner reported a residual for this decision, or where the merged
tree's own live replay showed one.

48. **Integration refinements.**
    (a) *A billing date of service under a kind-of-service heading (refines 42).* In a plan section, the encounter's own
        date-of-service label (date of service, DOS, service date, encounter date) under a block heading that names its
        block only as a kind of service - a service's name, or a visit, encounter, procedure, examination, consultation,
        session or review noun, with no plan, history, other-occurrence, status, other-document, return or recall word
        ("Office visit", "Clinic visit", "Coding review", "Colonoscopy") - speaks against the note's own labelled date
        (a conflict, asked). A heading naming another occurrence ("Next appointment", "Prior visit", "Return visit",
        "Recall", "Results", "Labs", "Referral") still governs, and so does a table's column label. Visit and procedure
        date fields keep 42's item rule.
    (b) *No planned date as the only answer (refines 42).* Where the note labels no date of its own, a plan's visit or
        procedure date field that no later-occurrence item governs stays dropped as the installed reading dropped it,
        so a member may answer any date; where the note labels its own date, the field still speaks (a conflict).
        Neither (a) nor (b) ever sends a date: each only asks, or reads as installed.
    (c) *An office note's summary table (refines 45).* A procedure-summary label opens nothing in a document whose own
        head titles it an office or clinic encounter's note (the visit-title marker of 44): such a table is a pasted
        report's unless something says otherwise, so its services are asked, as installed.
    (d) *One table model in one place (45).* The inventory reads the shared table model; its private copy, built to the
        same rule so the repairs could land in parallel, is removed after measured agreement on every corpus.
    (e) *An act's instrument (46).* An act never takes the technique of the instrument its own kind rules out: a forceps
        biopsy or hot forceps removal is never "(cold snare)", a snare removal never "(forceps)" - the instrument is what
        tells 45380 and 45384 from 45385, and the rationale must not misstate it.
    (f) *Added 2026-10-30, after the independent refutation - see 50(a). The code cites it as 48(f).*

### Session interpretation, 2026-10-30 (7c8d38da, third round, after the independent refutation) — recorded, not owner-ruled

49. **Correction to 42's version clause (recorded, not rewritten).** Interpretation 42 kept the version labels as
    installed so that "encounters already read keep their recorded contexts". The independent refutation of the
    integrated round (state lens, STATE-1 and STATE-2) showed that this keeps a context the new rules contradict CURRENT:
    h2-08's live context (gi-context@2) says 2026-10-05 as documented, and a predict queued or stopped at the install, a
    reconciliation or a reviewer-asked second review would send that date again, while an assess resumed after the
    install read 99215 ready on it. On today's 36 live encounters this was latent (h2-08's last stage is a succeeded
    assess), but nothing prevented it. So CONTEXT_VERSION becomes gi-context@3 and gi-context@2 an earlier version: the
    machinery the gi-context@1 upgrade built remakes an earlier context under the current rules before any stage sends or
    assesses on it, and refuses a second review on one. What 42 meant still holds for display: a reload runs no stage,
    so a pre-install encounter keeps showing its recorded reading until a member's action or a stage reads it again.
50. **Integration refinements after fix round 1, and two decisions before the freeze.**
    (a) *A charge line's date (refines 48(a); cited in the code as 48(f)).* In a plan section, the encounter's own
        date-of-service label in a block that carries a CPT code between its heading and the label ("CPT: 99214",
        "CPT code 45380", "CPT 43239-59") is this encounter's charge. Its date speaks against the note's own labelled
        date (a conflict, asked) whatever words the block's heading uses ("Evaluation and management", "Colonoscopy
        with biopsy"), unless the heading explicitly names another occurrence ("Prior visit", "Next appointment").
        Like 48(a) and (b) it never sends a date: it only asks, or reads as installed.
    (b) *A visit title stacked under the document's own follow-up title (refines 44).* A visit title in the head, directly
        under the document's own follow-up title ("Gastroenterology follow-up" / "Clinic note - return visit"), is this
        visit's title and never a block heading naming another occurrence. A title led by an other-occurrence word
        ("Prior clinic note", "Previous clinic note", "Scheduled office visit") still governs and documents nothing of
        today's visit.
    (c) *No visit time from a title alone where the note documents nothing of the visit (refines 43 and 44; the scope
        residual S-R1, decided must-fix).* After fix round 1, a "Hepatology clinic note" whose only clinical content is
        "Transient elastography today: ..." and "Physician time: 20 minutes." read 99213 ready; the installed revision
        held it. A ready E/M on a note that documents only another service's result is an unsupported promotion
        (must-fix class 4), and that time is most plausibly the elastography's interpretation, which 43 never counts.
        Rule: a visit title makes an unframed clinician time the visit's only where the note records part of the visit
        itself - a history, an examination or an assessment of its own. Otherwise the E/M is held, never ready and
        never excluded. Whether routing codes the procedure's family makes no difference.
    (d) *Version labels for the other readers (extends 49).* Routing, the documented-service inventory and the validation
        engine all read differently in this round, so their labels change at the freeze: gi-routing@5, gi-services@2
        (with the inventory's check source) and cpt-studio-validation@5. Otherwise a download made before the install
        and one made after it would name the same rules for different readings. The change affects provenance only:
        proposal fingerprints do not include the labels (engine._fingerprint), so no decision is invalidated by a label
        alone. The engine label's only other reader is the re-assessment's stated reasons (review._what_changed and
        _what_differs), which then name the engine change truthfully.

### Session interpretation, 2026-10-30 (7c8d38da, third round, after the second refutation) — recorded, not owner-ruled

The second refutation (six lenses over b6997c39d) reported 46 findings: nine requests that should not be sent (each
reproduced by the integration owner; two newly sent by this round's own code), a regression of the installed reading in
most of the code-status findings, two quadratic shapes in the integration owner's own 48(f) and 50(b) code, and one
data-loss path behind 49's version bump. Fix round 1's repairs were where most of them were, as in every round before.

51. **What blocks, and the fail-closed rules the second fix round follows (refines 41-46 and 48-50).**
    (a) *Class 4 (a correction, recorded not rewritten).* This round's refutation briefs graded "a code made ready or
        excluded wrongly" as must-fix class 4, while its repair and fix briefs kept the earlier rounds' wording, "a code
        approved or removed without a reviewer". The directive forbids promoting unsupported candidates, and a ready code
        is a promoted one, so the refutation's wording governs this round: a code made ready that the source does not
        support, or excluded where the source supports it, is must-fix.
    (b) *What blocks the freeze.* Every must-fix finding that regresses the installed revision 90377ec6f413's reading
        or comes from this round's own code; and every request that should not be sent - a contradicted, planned or
        historical date sent, or a conflicting applicable date dropped so that another is sent - whether or not the
        installed revision sends it too (41, and the directive's first priority). A must-fix finding the installed
        revision shares outside those is repaired where a general, measured rule exists; otherwise it is a known limit
        with its input and output, named among the report's uncertain readings.
    (c) *Dates: an uncertain binding asks.* (1) The encounter's own-date labels (date of service, DOS, service date,
        encounter date) are never dropped by their surroundings. In a plan or history section, under any block heading
        or in a table, such a label speaks against the note's own date (a conflict, asked), unless the label itself, or
        a heading of a closed class that explicitly names another occurrence ("Next appointment", "Prior visit"), names
        the occurrence it dates. (2) A label is the note's own only where the document allows it: a procedure date is
        never an office or clinic note's own date, and in the title's section a field after its first clinical sentence,
        or under a stacked heading that does not positively name this visit, follows the plan and history rules, not the
        header's. (3) The head is read as the head whatever a title above it says, and a label's separator is any short
        run of punctuation and spaces, so the visit's own header date is never lost. None of these sends a date the
        installed revision does not send, except the head's own date read under the document's own follow-up title.
    (d) *Scope: today's visit needs positive evidence both ways.* An office E/M is excluded only where the document
        positively shows that no visit took place today. A planned or earlier visit's mention, or a word of another
        occasion inside today's time statement, is never evidence against today's visit. It is ready only where the
        document's own markers establish both today's visit and its basis; another modality (telephone, portal,
        infusion, a letter) in the head, or a time whose occasion is uncertain, holds it.
    (e) *Inventory and extent: an act needs its own affirmation.* An act or a status read from a table cell, a relative
        clause or a summary is performed only where that cell or clause affirms it with no denial, plan or
        other-occasion word of its own. Otherwise it reads as the installed revision reads it. A procedure section opens
        only on positive evidence (a procedure report's own title or heading), never by default under an office or
        follow-up note.
    (f) *Word lists.* A closed list may add positive evidence. A list that exempts something from asking or holding
        fails open by construction, so none is added.

### Session interpretation, 2026-10-30 (7c8d38da, third round, at the second integration) — recorded, not owner-ruled

52. **Two corrections at the second integration (recorded, not rewritten).**
    (a) *50(c)'s assessment.* 50(c) named "a history, an examination or an assessment of its own" as the note's record of
        the visit. The scope owner's fix showed the assessment half wrong by the source: a study's interpretation is
        written under "Assessment and plan" too ("Transient elastography today: ..." / "Assessment and plan: No advanced
        fibrosis. Repeat in one year." / "Physician time: 20 minutes."), so the time may be the study's. A history,
        interval history, review of systems, examination or SOAP "Subjective" with content of its own records the visit;
        an assessment heading alone does not, and such a note is held, never ready (the installed revision held it).
    (b) *50(d)'s timing.* The version labels change before the third refutation rather than at the freeze, so that the
        tree the refutation reads is the tree that ships.

## Owner decision, 2026-10-30 (session 7c8d38da) — how round 3 finishes: a narrow release

Asked by the integration owner after the third, differential refutation, verbatim:

> Round 3 is not converging. The third, differential review of the candidate (dca76ed15) found 46 findings, 41 blocking.
> I reproduced the key ones: it newly sends a later visit's date (2027-04-05) where installed sent none; on an EGD
> report and a signature-dated note it refuses every member answer (the correct one included) where installed sent the
> right date; a pathology block's date becomes an acceptable answer that then gets sent; a context-stage scan takes 23 s
> at 30k characters (installed 0.05 s); a re-read loses a reviewer's approval on Resume. Each fix round fixed the last
> findings and introduced new ones (about 45 per round, three rounds, about 6M agent tokens per fix+review cycle).
> Nothing is pushed or installed; live is still 90377ec6f413. How should round 3 finish?

The options offered, verbatim:
- "Narrow release (Recommended)": "Ship only the h2-08 fix, built on the installed revision. Where installed silently
  drops a plan-section date of service, a charge or billing block's date now becomes a question instead; nothing new is
  ever sent. Add the context re-read and disabled-provider safeguards, run one focused refutation of that small diff,
  then PR, install and the live walk. The extent, scope, inventory and wider date work moves to a next round with a
  'never worse than installed' guard. Other contradicted-date shapes stay known limits, so still no reliable-coding
  claim."
- "One more fix round": "Fix only the must-not-ship findings in all four areas (wrong date sends, quadratic cost, data
  loss) and accept the remaining code-status and wording regressions against installed as known capability losses. Then
  a final differential review. About 6M tokens and 8 hours. On every round so far, fixing introduced new findings."
- "Continue full rounds": "Keep running fix and refutation cycles at the current bar until a differential review finds
  nothing blocking. Cost and duration are open-ended; three cycles have not converged."

**The owner's answer: "Narrow release (Recommended)".**

What it means for this change (recorded by the receiving session, before building on it):
- The release is built on the installed revision 90377ec6f413 (origin/main's cpt-studio is byte-identical to it), not on
  the round-3 integration branch. That branch (`fix/cpt-studio-gi-binding-20261029`, head dca76ed15 with the second
  integration's work) is kept for the next round, with its three refutations' findings, as that round's starting record.
- What ships: the h2-08 fix (a charge or billing block's date of service, which the installed reading drops inside a
  plan section, becomes a question where it differs from the note's own date; nothing new is ever sent); the context
  re-read (interpretation 49: gi-context@3, @2 earlier); and the disabled-provider safeguards (STATE2-1 as refined by
  the full suite and the ec5 ruling). Routing, inventory and engine readers stay as installed, so their labels do not
  change; interpretations 42-48 and 50-52 describe the integration branch's rules and do not ship with this release.
- One focused refutation of the small diff, then the PR, the install and the live walk.
- Interpretation 41 stands: other contradicted-date shapes remain known limits, and no reliable-coding claim is made.

### Session interpretation, 2026-10-30 (7c8d38da, the narrow release, after its refutations) — recorded, not owner-ruled

53. **The narrow release, as its two refutations refined it.**
    (a) *Which charge block asks.* The decision's wording is "a charge or billing block's date now becomes a question".
        The first narrow refutation showed that such a block can belong to another occurrence (dates-n3, dates-n4). Its
        examples were a copied note's or report's block, a booking, a prior visit's late charge, a pathology charge, and
        a date of birth auto-filled into the block. So only the note's own closing charge block asks, read on positive
        evidence (ACCURACY-RESIDUALS.md, "GI round 3 ... the narrow release"), and a block its guards recognise as
        another occurrence's reads exactly as installed.
    (b) *Its date is never an answer.* The second refutation found seven more shapes that passed those guards: a copied
        note announced in a sentence, a booking announced in a sentence, an appended telephone encounter, late and
        pathology charges in other words, another patient's block, and a date of birth in a form the reader does not
        read. Their dates were then taken as a member's answer and sent, which installed never did. No guard on the
        block's words or layout can decide whose block it is. So the block's date is read 'beside' (df-d:4): it makes
        the date a question and is quoted, but it is never a value a member's answer may choose. Only the document's
        own date is taken, and that is the date the installed revision sends. This applies the owner's decision of
        2026-10-28 for wrong-occurrence dates: a member cannot answer with a date that may be another occurrence's;
        an addendum settles it. A block the guards miss therefore costs an extra question, never a date taken or sent.
        The cost is that a member who believes h2-08's 2026-10-06 is held and must amend the document, as installed
        requires today. The question names the block, so it says nothing the source contradicts.
    (c) *What sending-disabled keeps.* STATE2-1 stopped the upgrade's predict only beside a succeeded run. The first
        refutation showed an unknown or failed outcome replaced by "provider not run" (STATE-N1). Now any recorded
        request (succeeded, failed or unknown) stops it, and an unknown outcome blocks it as it blocks every send. The
        stop message claims nothing about an assessment (STATE-N2).
    (d) *An upgrade's own predict stays one.* The second refutation found that 90377ec6f413's own upgrade predict,
        still queued at the swap, was remade here into a member's ordinary predict and sent (STATE2N-1). No live row
        can reach it at this install, but the next version bump could. Remade again, an upgrade's predict now queues
        the upgrade's predict for the fresh context, which never sends.
    (e) *Refutations of the finished diff.* The decision named one focused refutation. Its findings changed the diff,
        and so did the second's. The standing rule (AGENTS.md: the adversarial pass runs over the finished diff before
        merge) applies to each repair. So the same lenses refute the final diff again before the PR. This is not a new
        round of the parked work.

### Session interpretation, 2026-10-30 (7c8d38da, the narrow release, after its third refutation) — recorded, not owner-ruled

54. **The release changes only a date the installed reading sends (a correction of 53(b)'s mechanism, not of its
    principle).** 53(b) read the block's date 'beside' and kept it in the fact's evidence as a span no member's answer
    agrees with. The third refutation found no send and no answer wrongly taken. It found that the texts misstated the
    source in three ways (dates-n3-1 to n3-3, STATE3N-W1):
    - beside a question the document's own dates already raised (an own date in a form the reader does not read, a
      title or a second label stating another day), the question and check quoted the block's date as one more
      "documented" date of service, and the note claimed the block's date was never taken where the title stated it;
    - a member's unrelated date was held with "the document gives" followed by the block's line.
    So the release now acts on one fact only: one the installed reading sends (origin 'document'). There, where the
    note's own closing charge block states another date of service, the date is asked. The question keeps that fact's
    evidence and nothing else, so only the document's own date is a member's answer, and any other answer is held with
    the installed note. The block's date appears only in the fact's note, named as the block's
    (`context._charge_block_asks`, `CHARGE_DATE_NOTE`, read by `charge_date_problem`). Every other fact is returned
    exactly as the installed reading made it, its texts and the answers it takes included. The principle of 53(b)
    stands: the block's date is never this encounter's date of service.

### Session interpretation, 2026-10-30 (7c8d38da, the narrow release, after its fourth refutation) — recorded, not owner-ruled

55. **The question answers as the installed fact would, and names only the block's own lines (54, refined).** The
    fourth refutation found no send. It found two texts or holds that misstated the source, and one limit:
    - an own date hyphen-joined to its label ("DOS-10/05/2026"), which the installed reading reads and sends, could not
      answer the question, because the answer was checked by re-reading the evidence, which misses that form
      (dates-n4-1);
    - the closing block's region took in an entry written after the signature, such as a no-charge telephone call or
      an appointment, and named that entry's date as the block's (dates-n4-2).
    So the note keeps the date the installed fact sends, and a member's answer to the question is taken or held exactly
    as that fact takes or holds it, with the installed note. The block ends at its first signature line, and a block
    that also states the document's own date does not ask. The limit, an underscore-bold heading and a dash with no
    blanks (dates-n4-3), is now read.

### Session interpretation, 2026-10-30 (1bf3b49c, the narrow release, after its fifth refutation) — recorded, not owner-ruled

56. **Its text is true by construction, and routing stays the installed reading (55, refined).** The fifth refutation
    found no send and no answer wrongly taken. It found one misstatement, one regression against installed and two
    limits:
    - dates-n5-1: ending the block at its first signature line was one more word list. Seven signature forms it does
      not read left an entry written after the signature in the block, and the question said the charge or billing block
      states that entry's date;
    - dates-n5-3: a field that opens with a signature word ("Signed ABN on file: no") cut the block before its own date;
    - dates-n5-2: a dash bullet before a dash-joined heading hid the heading;
    - dates-n5-4: routing's only way to the document's date, `context.service_date_of`, returned None on the question.
      Read with no date, unanswered or with a member's answer held, a dated service went from performed to "service date
      not established", against the owner's "Routing, inventory and engine readers stay as installed".

    (a) *The block has no signature end.* No word list tells a signature line from a field, so the list is removed
        rather than extended. The block runs to the document's end, and the question names what "the lines from the
        document's last charge or billing heading to its end" state, as theirs. That sentence is true of any line it can
        name. The cost is an extra question on a dated entry after the signature, a known limit with its own row.
    (b) *Routing reads the date the installed reading sends*, which the question's note keeps. Session 7c8d38da's last
        thought was to record n5-4 as a limit. Session 1bf3b49c repaired it instead: it is two lines, it can reach no
        request (`jobs._service_date_of` reads the stored facts), and it turns the owner's sentence from nearly true into a
        property a mechanical differential can check. A version label kept over changed readings is the trap the context
        re-read (49) exists to close.
    (c) *What "stay as installed" means for the inventory and the engine.* They are handed the stored date, which is None
        while the question stands, so they cannot read the document as installed reads it with a sent date. What holds is
        narrower and exact: an open question reads as installed reads a held member's answer, so it is no new state, and
        the engine holds every proposal on it. The ruling's sentence is about readers, and those are unchanged.

    **Takeover.** The host rebooted at 2026-10-30 22:00:21Z, after session 7c8d38da stopped at 21:14Z mid-repair. `/tmp`
    was wiped, and with it the session's scratch, including both sealed acceptance sets. Session 1bf3b49c continues as
    the single integration and deployment owner (the owner said "Continue"), and rebuilt the harness from the session
    transcripts. h4, the primary set, was rebuilt from its author's own tool calls without being read: its manifest
    matches its pin (f8985709...) and all six of its renders are byte-identical to the hashes its author's run printed.
    h3, already exposed, could not be rebuilt or checked against its pin, so no claim rests on it.

### Session interpretation, 2026-10-31 (1bf3b49c, the narrow release, after its sixth refutation) — recorded, not owner-ruled

57. **The question holds the date, never the reading (56(c) overruled; the owner's sentence applied to its letter).** The
    sixth refutation (dates, parity and pipeline lenses) found no wrong date sent and no member answer changed. It found
    what 56 had wrong:
    (a) *56(c) was the wrong target.* It settled for "an open question reads as installed reads a held answer". Parity-6-1
        and 6-2 showed what that costs: read with no date, a 2025 colonoscopy read as done on this encounter, with a
        same-day E/M warning, and a code documented as done today went from ready to excluded. The owner's sentence is
        "Routing, inventory and engine readers stay as installed", and a reader handed None is not reading as installed.
        So every reader now reads the date the installed reading sends (`charge_question_day`), and only the gates keep
        none: each proposal holds on the question, and no dated reference applies. An open question reads as installed
        reads the same document with its date, except the date and what hangs on it. The engine's label does not change:
        for every document the installed revision read, its readers read what they read. A held member's answer stays as
        installed.
    (b) *"True by construction" was claimed before it was so.* The sentence still asserted what it could not know: "the
        last heading", "a date of service", "the document's own" (dates-n6-1, n6-3 to n6-6). It now quotes the line it read
        from, quotes each stated line whole, and says the date "is read from" its line. The test helper checks the claim
        on every asked text: the first quote is a line of the document, and each stated quote a whole line at or after it.
    (c) *Other readers kept the word.* All three lenses found the report, screen, list and change reason calling the fact
        conflicting, independently. They now ask the same predicate as the check, and say "asked".
    (d) *A limit accepted on measured reach.* Pipe6-1: a member's save that does not settle the date on a pre-install
        encounter the release asks sends one dateless request, where installed only re-assessed, and can invalidate a
        decision. Of the 36 live encounters exactly one can reach it, e084b793, with no decisions, and the walk does not
        touch it. It is recorded, not repaired: the repair would change the save path, which is where the parked work kept
        regressing, for one synthetic row. Pipe6-3 and pipe6-6 are rollback limits, recorded in the declaration.

### Session interpretation, 2026-10-31 (1bf3b49c, the narrow release, after its seventh refutation) — recorded, not owner-ruled

58. **The reader and gate split, finished (57 refined).** The seventh refutation was a differential pass: only what is
    worse than installed, or a text the release adds that misstates the source, could block. It found no wrong date sent,
    and the sentence held literally on 37,910 asked texts. Five things changed what 57 said:
    (a) *A reference row can be a reader.* 57(a) called every reference use a gate. This was the first run with
        fee-schedule rows loaded, and it showed `_procedural` reads a row's global days: with none a code counts as
        procedural (installed's fail-closed rule for an unknown date), so a breath test raised a same-day E/M question.
        Whether a code is a procedure is a reading, so `_procedural` reads the row the installed reading has. Everything
        else stays a gate: `pfs_check` reads a row's `applicable_sources`, so handing the checks a row would open them.
    (b) *A held answer on such a document reads as the open question does.* 57(a) left it reading with no date, as
        installed. But installed's held state has no provider answer, and here the dateless answer is kept, so the
        misreadings 57 had stopped came back, on the date the question quotes, the most natural wrong answer: a code went
        to excluded on a false reason. "As installed" was the wrong target for a state installed never reaches.
    (c) *57(d)'s limit was stated too narrowly.* It said only pre-install encounters reach it, and rested on that. A
        member clearing a date reaches it on any encounter (text-1, pipe7-3): one dateless request, and a decision on a
        ready code invalidated. The decision stands on a different ground: a dateless request is what an open question
        asks; avoiding it would pair a dated answer with an undated context, which the stages' date pairing refuses; and
        that path is where the parked work kept regressing. The row now says all of this. The live reach of a save of
        something else is still one encounter with no decisions.
    (d) *Its text can be true and still not settle.* An addendum stating the date the question names now settles it,
        wherever the line stands. The chip no longer promises a question that may not be on the page yet.
    (e) *What was not repaired, and why.* The considerations a fee-schedule row adds and an excluded code's reinstatement
        do wait on the date: they are gates, and the limit row names them. A stale tab during the install window reads an
        old page beside a new API: a limit of any install.

### Session interpretation, 2026-10-31 (1bf3b49c, the narrow release, after its eighth refutation) — recorded, not owner-ruled

59. **Back toward installed, in two places (58 refined).** The eighth refutation, one differential lens over the delta,
    found nothing that blocks. It raised two limits, and each showed a step 58 had taken too far.
    (a) *A running footer settles nothing.* 58(d) read the document's own date anywhere in the closing lines, so that an
        addendum could settle the question. It also let a running PDF footer settle it: h2-08 with "Date of service:
        10/05/2026 | Page 2 of 2" stopped asking and sent the contradicted date. That is installed's own reading, so it broke
        no class of the pass, and it was still the shape the release exists for. Agreement now reads a plan's reach, as
        before 58, or the application's own addendum section. What a member writes in an addendum still settles it, even in
        words that retract it: that route is the one the question offers, and the limit is named.
    (b) *A held answer with nothing kept stays installed.* 58(b) justified reading the date for a held answer by the
        dateless answer it keeps. A date held at upload keeps none, and installed reaches that state with nothing to
        misread. It reads as installed again. 58(b)'s sentence "a state installed never reaches" holds only for the answer it
        keeps, and is narrowed to that.

60. **The code is frozen (session 1bf3b49c, 2026-10-31).** The ninth refutation, one lens over the two conditions 59 added,
    found nothing that blocks, so the refutations stop here: nine over the narrow diff, the last two with no blocking finding.
    Their remaining limits are named in ACCURACY-RESIDUALS.md and go to the owner in the report. The owner's decision named
    one focused refutation; 53(e) explains why the rule required more, and each repair's cost is in that file's measured
    block. No reliable-coding claim is made.

### Session interpretation, 2026-10-31 (1bf3b49c, the narrow release, the pypdf advisories) — recorded, not owner-ruled

61. **The release ships on pypdf 6.21.2, and only the rebuild's pin moves.** Seven advisories against pypdf 6.21.2
    (CVE-2026-119203 to CVE-2026-119209) failed the required dependency audit on every pull request, this release's
    included. That audit reads `rebuild/requirements.txt`, and PR #1449 moved that pin to 6.21.4 on its own. CPT
    Studio's pin stays at 6.21.2, as installed, for three reasons.
    (a) *6.21.4 reads uploads differently.* Four refutation lenses attacked the move. An independent agent reproduced
        each finding, with both versions recorded. They found 34 differences in CPT Studio's reader, four of them
        blocking:
        - A valid ReportLab PDF using a predefined CJK character map had no usable text layer and went to OCR. It now
          reads as status ok, with a page of mojibake that the next stage would send.
        - A check mark named by a private-use glyph became "[]". Routing reads that as an unchecked box, so a
          performed service reads as negated.
        - A cut string in an annotation's appearance lost its notice, or went from partial to ok.
        The author reproduced all four. Each breaks "nothing new is ever sent" or "never worse than installed", and
        repairing them means reading as 6.21.2 failed, which is new reader work.
    (b) *The advisories are contained.* All seven are denial of service from a crafted PDF. CPT Studio reads each
        upload in a child process that has an address-space limit and a CPU limit, and whose process group is
        killed at the deadline. Only signed-in synthetic accounts upload. Staying on 6.21.2 keeps the installed
        exposure and adds none.
    (c) *The cost is a red that tells the truth.* CPT Studio's own workflow ends with its dependency audit, so its
        check stays red after every test has passed. It stays red until a later round moves CPT Studio to 6.21.4 with
        its reader repaired. That workflow is not a required check, and no gate is overridden.
    The findings are listed in ACCURACY-RESIDUALS.md under "pypdf 6.21.4 is not taken". The same refutation found
    that the rebuild's upload check can already be passed with a crafted cross-reference section, on the version
    `main` pins today. That is recorded in `docs/rebuild/security-readiness.md`, is not this release's to repair,
    and goes to the owner.

## Owner directive, 2026-10-31 — a complete reviewed synthetic GI demonstration (fourth round)

Received directly from the owner in session 1bf3b49c on 31 October 2026 (about 17:35Z), as pasted instruction text,
after the install of revision 80df1831d168 (PRs #1448 and #1451) and its report (PR #1452). Recorded by the receiving
session in its first commit, before the work that depends on it. Verbatim:

> Continue from CPT Studio round three, installed revision 80df1831d168. The objective is a complete, reviewed synthetic GI demonstration with an actual downloaded report, alongside repair of the documented shared interpretation defects.
>
> Start in a fresh worktree using scripts/setup-worktree.sh. Coordinate one integration/deployment owner. Preserve existing encounters, decisions, raw responses, failures, receipts and rollback artifacts.
>
> 1. Address the reported live rebuild PDF-security finding first, as a separate scoped change. Read docs/rebuild/security-readiness.md and docs/rebuild/pypdf-6.21.4.md. Reproduce the inspection bypass using harmless fixtures; repair the actual upload and original-download path. Do not assume strict=True, warning suppression or a dependency upgrade establishes safety. Verify malformed/unreadable content cannot silently pass the active-content policy, while ordinary supported PDFs remain usable.
>
> 2. Repair and verify the documented PDF compatibility regressions before deploying the dependency update to each application. Check rendered checkboxes, extracted text, OCR routing, annotations and filled answers. Verify installed runtime versions and resource limits. Do not conceal the dependency audit failure.
>
> 3. Repair CPT Studio’s shared service interpretation: bind dates, performed/planned/historical/negated status, anatomy, procedure extent and evidence to the correct service. Use h4 and h2-08 as regression cases, plus independently authored unseen variants. No patient-specific exceptions, forced approvals or weakened validators. “Unchanged from installed” is insufficient when installed behavior is known to be wrong.
>
> 4. Investigate Corti omissions separately using retained requests and responses first. Trace missing EUS/EGD and the ERCP discrepancy through source text, submitted payload, raw response and local filtering. Do not invent missing codes or promote alternatives. Keep provisional author expectations separate from qualified GI-coder adjudication.
>
> 5. After those repairs, execute a small fresh HTTPS acceptance test through the ordinary reviewer account: upload, necessary clarification, coding review, clearly labelled synthetic approval, reload and actual reviewed download. Verify completeness, evidence and persisted selections independently. Report legitimate documentation questions separately from software false holds.
>
> Use existing standing synthetic-testing authority, bounded purposeful provider calls and duplicate protection. Do not request repeated funding approval already superseded. Finish with installed revision, actual downloads, measured usage and precise remaining limitations. Do not claim reliable GI coding from installation or download checks alone.

### Session interpretation, 2026-10-31 (1bf3b49c, fourth round, on receipt) — recorded, not owner-ruled

62. **Order and scope.** The rebuild's upload check (P1) is repaired first, on its own branch and pull request, and
    installed in the rebuild on its own declaration. The pypdf move then happens per application, and only after that
    application's documented regressions are repaired and measured. The rebuild already pins 6.21.4 on `main` (PR #1449),
    so its next install carries that pin; that install is judged as a pypdf move too. The CPT Studio interpretation
    repair follows. The Corti investigation reads retained rows and sends nothing. The acceptance test comes last.
    Installing the rebuild is in scope for items 1 and 2. Round 3 had kept app.quillmd.com unchanged.
63. **The acceptance test uses the ordinary reviewer account.** For item 5 this overrides interpretation 40, which kept
    every synthetic approval on the agent account. This session makes the approval through the demo-reviewer account,
    and the decision's own record says it is a synthetic acceptance-test approval made by the session, not a human
    review. The report says the same. No other decision is made through that account.
64. **One integration and deployment owner.** This session alone commits to integration branches, pushes, merges and
    installs. Parallel agents investigate, write in their own worktrees and refute from read-only sandboxes.
65. **Nothing retained is deleted or rewritten.** That covers existing encounters, decisions, raw responses, failures,
    install receipts and rollback artifacts, including the pre-app dump of round 3. A repair that would need to rewrite
    a stored row is a finding for the owner, not something to carry out.
66. **Right by the source, for readers too.** Interpretation 38's bar applies to the pypdf move as well. A reading that
    differs from 6.21.2 is judged against the document, not against equality with 6.21.2. Equality with the installed
    reader is a safety net, never acceptance, wherever the installed reading is known to be wrong.

### Session interpretation, 2026-10-31 (1bf3b49c, fourth round, the rebuild installer) — recorded, not owner-ruled

Decided by the integration owner (interpretation 64) and recorded by the installer's author in its first commit,
before the code that depends on it.

67. **The rebuild's next install is code only, through a tracked installer.**
    - **D1.** The next act installs code only. The candidate is `origin/main` at the act: it carries P1, the
      never-installed PR #1434 instruction text and every other path since `67acb2628`. The live venv
      `/opt/meddoc-pro/rebuild/.venv` stays exactly as found (pypdf 6.21.1, filelock 4.0.0, msgpack 1.2.2 and the 63
      unrecorded bytecode files), asserted by a full footprint before and after. `rebuild/requirements.txt` will name
      newer versions than the venv; that mismatch is declared, not refused. The dependency move is a later, separate
      act (D1b).
    - **D2.** No rollback ever downgrades the venv.
    - **D3.** The Corti candidate units and every other foreign service stay running and unchanged. The act verifies
      them idle and unchanged before and after, as the October engine did.
    - **D4.** The declaration reaches `main` through a pull request before the act, so the candidate contains it. The
      October rule "the declaration is a direct child commit of the candidate adding only that file" is replaced by:
      the declaration is tracked, unmodified and committed in the candidate, and the strict gate of
      `scripts/run-ruled-mutation.sh` passes.

    This refines interpretation 62, which is kept as written: the next install carries main's pins in the tree but not
    in the venv, so it is judged as a code install with a declared requirements/runtime mismatch. The pypdf move is
    judged later, in D1b, after item 2's regressions are repaired and measured. In the install analyst's plan, D1
    matches option (ii) of its question O1 and D2 matches the precedent answer of its question O2.

    Added by the integration owner on 2026-11-01, after four refutation rounds of the installer:
    - **Why the installer is tracked.** The October installs ran through a private, untracked operator that patched the
      tracked engine at runtime, and their declarations survive only as unpushed commits in execution worktrees. This act's
      installer lives in the repository with tests, its default mode is a read-only preflight, and it went through four
      refutation rounds (22, 14, 6 and 4 findings, the last two signal and lock edge cases).
    - **Signals.** The act blocks every terminating signal and takes them only at checkpoints. It must still not be
      signalled: under the runner, a group signal ends in SIGKILL after 15 s, and the Go docker client can abort a unit
      action. It is run detached, with no other operator process, and only a separately declared reverse act recovers a
      killed act.
    - **Backups.** Every scheduled rebuild backup has failed since 2026-10-12. Each referenced file is copied through its
      own helper container, and the file count outgrew the fixed 540-second timeout. The act therefore takes a manual
      encrypted backup and an isolated restore check first. Repairing the schedule is outside this round and goes to the
      owner.

### Session interpretation, 2026-11-01 (1bf3b49c, fourth round, after the round-4 refutations) — recorded, not owner-ruled

68. **CPT Studio's pypdf move is deferred from this round, and the trade-off goes to the owner.** Four repair rounds of
    the CPT Studio reader on pypdf 6.21.4 (branch `fix/cpt-studio-pypdf-6.21.4-20261031`, head `6134dc7cf`) did not
    converge. Round 4's three-lens refutation filed 13 findings, 6 major:
    - **Meaning, R4M-1 to R4M-5 (4 major), all in round 4's new checklist-row rules.** A bulleted procedure list next
      to one boxed row becomes a checklist and every procedure is held, where installed reads them right (R4M-1). An
      unchecked check box in another column holds a procedure on the same baseline (R4M-2). In a two-column procedure
      checklist drawn row by row, procedures whose boxes are empty read performed, as installed reads them, where round
      3 held them (R4M-3; reproduced by the integration owner on `b6/t6_proc_twocol_typed_euc.pdf`: "Biopsy of the
      cecum" and "Tattoo injection" performed on round 4 and on installed). R4M-4 and R4M-5 likewise turn round 3's
      holds back into installed's readings.
    - **Cost, 2 major and 1 minor.** A 164 KB, 12-page file and a 62 KB page of 10,000 check boxes pass the 240 s
      deadline (R4-COST-CODESPACE-1, which also refutes the 4 MiB CMap cap's repair, and R4-COST-LEFTLABEL-1).
    - **Capability, 5 minor.** Each needs an unusual font structure; 200 new ordinary files read identically or better.

    Item 2 says to repair and verify the regressions *before* deploying the dependency update. They are not verified
    repaired, so CPT Studio installs this round on pypdf 6.21.2, exactly as round 3 did (interpretation 61), and its
    dependency audit stays red and is declared, not concealed. The branch is kept unmerged with its rounds' records.
    **For the owner (class b):** stay on 6.21.2 with seven known advisories, or accept round 4's false holds on some
    glyph-index and EUC-H checklist layouts to clear the audit, or fund further rounds. Nothing here changes what the
    installed reader does.

69. **A stated own date of service is held, not taken, when the entered date differs (h4-03).** PD's cycle 1 returned
    h4-03 to installed's behaviour: an entered date matching neither date the report states for its own case
    ("Exam date: 10/06/2026", ledger "Service date logged for this case: 10/08/2026", signed 10/09) was taken and sent,
    and 4 of 17 HARD states failed. "Unchanged from installed" is insufficient when installed is known to be wrong, so
    the integration owner directed a strong-head hold, declared in `pd.json` (`amendment_20261101_integration`) before
    its code: when the head is a procedure report's own head (PI+PE's predicate, imported) with exactly one own date, a
    member date that differs is held for a question quoting the stated date lines; it is never narrowed, taken or sent.
    The integration added two declared conditions (no hold on a note written around a procedure, or one mentioning a
    call or message) and a rewritten note. h4-03 goes to 17/17; NEW-SEND and NEW-TAKE stay 0. Recorded for the owner:
    with the relabelled ledger no answer is taken any more, and a consultation whose head carries proceduralist and
    sedation fields and the planned day would have its own date held (no such text is in the corpus).

70. **The rebuild release carries P1 and nothing of item 2.**
    - **P1's fifth round** repaired GR1-EXPORT-OPEN in `documents.check_original` only, not in `_run`: preparation
      records an unlisted code as `provider_unknown`, which would be false. PG-1 (a stop landing as a PDF-form
      transcription starts can leave it for reconciliation; unreachable with no PDF templates) and the pre-existing
      GR1-UPLOAD-FILL are recorded limits. P1 merged as `797199c7` after CI on its round-5 head.
    - **The rebuild's pypdf 6.21.4 compatibility repair** (`fix/rebuild-pypdf-6214-compat-20261101`) is not in this
      release: its refutation died with the previous account's weekly usage limit and was not re-run. D1b's act code is
      not built. The live venv keeps pypdf 6.21.1, filelock 4.0.0 and msgpack 1.2.2, declared.
    - **The usage limit.** At about 11:20Z the previous account's weekly limit stopped every running agent: P1 round
      4's last gate, both rebuild-compatibility lenses and two of three CPT Studio reader lenses. The owner switched
      accounts at about 16:45Z. Only commits survived; every lost run was re-run or is named above as not re-run.

## Owner directive, 2026-11-01 — the CPT Studio GI coding harness (Corti, Astra, Fable, references, reconciliation)

Received directly from the owner in session 1bf3b49c on 1 November 2026 (about 21:00Z), as pasted instruction text,
while round 4 was in progress (the rebuild release `c8b54991` installed; CPT Studio still serving `80df1831d168`). It
followed the owner's question whether Astra and Fable were reviewing the files, to which the session answered that the
review lenses were engineering subagents on the session's own model, and that Astra and Fable are, in the 2026-10-23
directive, alternative CPT-proposal engines. Recorded by the receiving session in its first commit, together with the
acceptance checklist it requires (`CPT-HARNESS-CHECKLIST.md`), before the work that depends on it. Verbatim:

> Implement and install the actual CPT Studio GI coding harness on cpt.quillmd.com: Corti plus independent Astra and Fable document reviews, supported by authoritative reference retrieval and evidence-based reconciliation.
>
> This is a product implementation task. Engineering subagents reviewing software do not satisfy the requirement for models reviewing each uploaded clinical document.
>
> Keep the existing single GI category and approved website design. Carry the work through implementation, installation and meaningful verification on the actual website.
>
> CHECKLIST AND REPORTING CONTRACT
>
> Create CPT-HARNESS-CHECKLIST.md in the repository before making changes. Use the checklist below as the acceptance contract.
>
> Every item must have:
> - Status: NOT RUN, IN PROGRESS, PASS, FAIL or BLOCKED.
> - Implementation revision.
> - Verification evidence location.
> - Remaining action, if any.
>
> Use [x] only for PASS backed by evidence. Writing code, passing a mocked test or repeating another report does not establish live completion.
>
> Complete prerequisite items before advancing to dependent stages. Independent preparation may continue in parallel. Investigate and repair failures; do not remove requirements or weaken checks to tick a box.
>
> Update the checklist after every completed stage and provide a concise progress report stating completed items, the current item and the next action. Preserve previous failures and measurements.
>
> STAGE 1 — ESTABLISH THE ACTUAL STARTING POINT
>
> - [ ] Inspect the current installed revision, active work and existing provider integrations. Coordinate with the current deployment owner and use a fresh worktree; do not edit the shared deployment checkout.
> - [ ] Produce a clear map of the current document-to-code workflow. Distinguish production clinical reviewers from engineering agents.
> - [ ] Verify backend access to Corti, Astra and Fable: exact provider, API model/endpoint identifier and a minimal synthetic capability check. Desktop model names are insufficient. Do not silently substitute a different model.
> - [ ] Identify the authorized CPT/reference sources and retrieval tools actually available, including releases, effective dates and permitted uses. Record unavailable dependencies accurately.
>
> An unavailable model or reference source blocks its dependent live stage, not all independent engineering work. Consolidate any unavoidable external dependency into one precise request.
>
> STAGE 2 — READ THE DOCUMENT CORRECTLY
>
> - [ ] Preserve the original document, its hash and revision. Support the existing Word, native PDF, scanned PDF and pasted-text paths with traceable extraction/OCR.
> - [ ] Verify relevant PDF upload-security repairs and parser safeguards on the actual applicable paths. Address documented encoding, checkbox and extraction failures; an unreadable symbol must not silently become a negative clinical fact.
> - [ ] Represent each service separately: date, performed/planned/historical/negated/uncertain status, anatomy, extent, technique, lesion identity, provider role and exact supporting evidence.
> - [ ] Repair shared interpretation defects without patient-specific exceptions. Do not feed all reviewers the same incorrect interpretation as unquestionable truth. Preserve access to source text and page evidence where supported.
>
> STAGE 3 — IMPLEMENT THREE GENUINE PARTICIPANTS
>
> - [ ] Corti independently receives the supported source input and returns proposals. Preserve its selected codes, alternatives, evidence, raw response and metering without rewriting its original answer.
> - [ ] Astra independently examines the source and produces supported service facts, proposed CPT codes, missing-service findings and clarification needs.
> - [ ] Fable independently examines the source and produces the same structured assessment before seeing Astra’s or Corti’s conclusions.
> - [ ] Record each participant’s actual model/endpoint, input revision, request identity, output and usage. Three summaries of one provider response do not count as three reviews.
>
> Respect each endpoint’s capabilities. Corti need not perform web searches itself; the harness can validate its proposals through a separate retrieval stage.
>
> STAGE 4 — RETRIEVE, VALIDATE AND RECONCILE
>
> - [ ] Implement actual reference retrieval. Retain source identity, retrieved passages, release/effective dates and tool traces. Model memory or an unsupported assertion that a code was “verified online” does not pass.
> - [ ] Check proposals against documented services, authorized CPT guidance and applicable payer/bundling/modifier rules. Public web search supplements authoritative sources; it does not replace missing licensed content.
> - [ ] Reconcile the complete service inventory against all three outputs, including services Corti omitted. Check completeness as well as whether returned codes appear plausible.
> - [ ] Resolve disagreements through source evidence and applicable rules. Majority agreement is not proof. Preserve unresolved contradictions and ask focused questions only when documentation actually requires them.
> - [ ] Distinguish a proposed code, a reference-supported code and a reviewer-approved code. No automatic approval merely because models agree.
>
> STAGE 5 — VERIFY GENERALIZATION BEFORE DEPLOYMENT
>
> - [ ] Reproduce the retained date, status, extent, EUS, EGD/biopsy and ERCP discrepancies. Distinguish application errors, provider omissions and unresolved coding judgments.
> - [ ] Predeclare a small independently authored unseen synthetic set before execution. Include varied document formats, multiple procedures, conflicting dates, planned/negated services and incomplete procedures. Record expectations and their source independently of system output.
> - [ ] Run the declared set and report every result: correct findings, missed services, unsupported proposals, unnecessary questions, legitimate abstentions and failures. Do not select only successful documents afterward and present them as full acceptance.
> - [ ] Verify tenant isolation, duplicate prevention, unknown-outcome recovery, evidence preservation and unchanged historical approvals/exports.
>
> Qualified GI-coder adjudication is required for a credible clinical accuracy claim. It is not a prerequisite for implementing and privately testing this harness.
>
> STAGE 6 — INSTALL AND VERIFY THE WEBSITE
>
> - [ ] Install the verified release on the existing login-protected cpt.quillmd.com website, with rollback evidence and preservation checks. Verify the served revision.
> - [ ] Show understandable per-document progress: Corti review, Astra review, Fable review, reference validation, clarification needs and final review status. Keep detailed traces in the appropriate administrative view.
> - [ ] Through an ordinary authorized account, upload fresh synthetic documents and prove that all three production participants and reference retrieval actually execute. Replay alone cannot satisfy this item.
> - [ ] Complete necessary clarification, review and synthetic decisions; verify persistence after reload and download the actual reviewed reports. Check their codes, evidence and decisions against saved state.
> - [ ] Label automated synthetic decisions accurately. Using a reviewer account does not turn an agent-executed approval into human clinical review.
> - [ ] Verify the doctor-facing demonstration on desktop and mobile, including genuine failure and unavailable-provider states.
>
> EXECUTION AUTHORITY
>
> Use the existing standing synthetic-testing authority and authorized provider accounts. Do not revive superseded campaign funding limits or request repeated approvals for already-authorized tests.
>
> Use purposeful bounded batches, finite deadlines, serialized clinical provider calls and one integration/deployment owner. Reconcile unknown outcomes before resubmitting. Preserve costs, raw responses, failures and historical reservations.
>
> Do not purchase subscriptions, accept new vendor agreements, process real patients, submit claims or publicly launch the service under this instruction.
>
> FINAL DELIVERY
>
> Return:
> 1. The complete checklist with evidence-backed statuses.
> 2. Installed revision and website link.
> 3. Demonstration encounter links and actual downloaded reports.
> 4. Proof of which providers/models ran and which references were retrieved.
> 5. Measured usage and unresolved issues.
> 6. Two separate verdicts: functional synthetic-demo readiness and independently established clinical accuracy.
>
> Do not declare the full harness complete while required participants or reference validation are missing. Do not stop at a plan, local preview or installation report. Deliver and verify the actual website workflow within the authorized scope.

## Owner directive, 2026-11-02 — the participants' credentials are placed: check them, wire them, access-check, then install and verify live

Received by session cd048041 at about 05:45Z (it took over integration and deployment from session 1bf3b49c at
00:40Z, at the owner's choice). Verbatim:

> Continue the CPT Studio harness work. Check these credential files first:
>
> - /etc/cpt-studio-provider-sources/anthropic.env
> - /etc/cpt-studio-provider-sources/openai.env
>
> Verify they exist, contain the expected variables, and have secure ownership and permissions. Never print the keys or
> include them in logs, reports or Git.
>
> Wire them through the existing installer/secret mechanism and run minimal authorized synthetic access checks for:
> - Anthropic: claude-fable-5-1
> - OpenAI: gpt-6-astra
>
> Record the actual returned model identifiers. Do not silently substitute models.
>
> If access passes, update the checklist and continue implementation, installation on cpt.quillmd.com, and the
> complete live acceptance workflow under the existing authorization. Keep QuillMD and unrelated services unchanged.
>
> Completion requires real Corti/Astra/Fable responses, traced references, saved synthetic review, persistence after
> reload and an actual reviewed report download. Keys working alone does not establish completion.
>
> Keep D3/D4 accurately recorded; do not accept new agreements or infer licensing permission. If access fails, diagnose
> the precise error without exposing credentials, and continue independent work.

### Session interpretation, 2026-11-02 (cd048041, on receipt) — recorded, not owner-ruled

(a) **The files were checked before anything else, and no value was printed.** A stdlib-only checker that applies
`studio/participants/credentials.py`'s rules ran as root in a throwaway container with no network and the directory
bound read-only, printing metadata and booleans only (proved first on fake files: no value in its output). Result
05:52Z: the directory is root:root 0700 with exactly the two files; each is a regular root:root 0600 file within
32,000 bytes that parses, with its required key present and a valid header value, and no optional key.

(b) **The installer's access check runs only inside the app phase of an install, and this release is not installable
yet** (round 1's repairs are running, and a refutation pass over the finished diff is mandatory before merge). So access
is checked now in two steps, and again formally by the install: (1) the installer's own `secrets` phase, alone, from
the harness revision under `docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md`, copies the two
sources into `/etc/cpt-studio/` (10150:10150 0400): the existing secret mechanism, with no code installed and no
service restarted; (2) `manage participant_access_check --participant astra` and `--participant fable` run once each from
a separately tagged candidate image (`cpt-studio-precheck:e3c05bc007c6`, built as the image phase builds), in a
one-shot with the installer's access-check layout (the copied file read-only at the worker's path, uid 10150, the
installer's hardening), on a throwaway network and database (the command needs a database only for its advisory lock;
the live database is never connected), and its output is kept only after a root helper finds no credential value in
it. The install's `app --access-check` repeats the check on the installed revision.

(c) **"Do not silently substitute models":** the requested and returned model ids are recorded exactly as the vendors
return them; the adapters refuse any reading answered by another model (I6).

(d) **D3 and D4 stay open as recorded.** The owner's remark earlier on 2026-11-02 that CPT descriptors are not needed
is noted, not recorded as a D3 decision: it was asked about and not confirmed. No agreement is accepted and no
licensing permission is inferred. Working keys establish checklist item 1.3 only; completion stays as the directive
states.

### Session interpretation, 2026-11-02 (cd048041, after the harness's second refutation) — recorded, not owner-ruled

(a) **The second refutation of the finished harness head (`cdc41dfa2`, PR #1459, a draft throughout) filed 32 findings;
31 were reproduced by independent verifiers, and one was blocking.** EV2-1: a performed-status candidate was verified on
a passage about the examination for a question about an act, so after one reviewer confirmation 45385 (snare removal)
became ready to approve on a document that says "No polyps were seen". Sixteen findings were major and fourteen minor;
EV2-4 was not reproduced (documented design). Records: `$S4/refute-harness-r2/findings.json` (the lenses) and
`$S4/verify-harness-r2/results.json` (the verdicts, reach, proposed repairs and evidence), where `$S4` is
`/home/claude/cpt-studio-gi4-20261031`.

(b) **Six design decisions were taken by the session, and none is an owner question.** They are D1-D6 of the repair plan
(`$S4/verify-harness-r2/REPAIR-PLAN.md`), recorded in HARNESS.md where each replaced rule is stated and indexed in
HARNESS.md 12.9. Each makes CPT Studio claim less or show a model less: a status is verified only where CPT Studio's own
readers read the question's act (or service) with exactly that status in the passage's whole sentence (D1); every fact's
passage gets the history, plan and indication rule, and a qualified passage never verifies (D2); candidates and
confirmations only on the current revision and context (D3); a peer request carries no person, no member-entered value
and none of the other model's free text (D4); each exchange is recorded as what happened (D5); I1 states its one
exception and the re-persist rule compares what round 4 compared (D6). Under the four classes that reach the owner: none
is a product decision without precedent (each brings the code back to a rule HARNESS.md already stated, or narrows that
rule); none is an accepted-capability loss, because harness@2 has never been installed - confirmations, candidates and
peer review do not exist on the live site, so nothing a member can do there today changes; none needs the owner's
eyeball beyond the live walk already required; none concerns money, keys or deleting data.

(c) **One tightening beyond D1, by the repair agent, accepted by the session:** a code that accounts for an act (its
coverage profile names the act kinds it covers) is checked on that act even when its hold was raised at the service
level, because checking it on the service would let a snare code become ready on the bare examination sentence through a
service-level hold. Recorded in HARNESS.md 12.5. A consequence, also recorded there and in 12.9: a 'performed' status
never verifies on a hold raised because the readers read no act of the code's kinds as done; such a hold is resolved by
an addendum or by rejecting the code, never by one confirmation.

(d) **Recorded and not repaired in this round, none an owner question:** the hand-written harness@1 fixtures (FG2-5 part
2, a test-fidelity gap whose user-visible half is repaired); Corti's send classification (D5's rule is not applied to
Corti, whose path I1 pins); routing's `_landmark_negations_near`, where `cues.NOT_REACHED_AFTER` is read with
`match(text, pos)` and its `^` anchor never matches there (verified by the session on "The cecum was not reached."), so
"the cecum was not reached" never explains its negation word in that reader. Its effect on routing output was not
measured, and repairing it changes Corti-only results, which I1 forbids without a declared change; it is left for a
round that declares one. The residuals of each repair are listed in HARNESS.md 12.9.

(e) **Integration.** The five repairs were merged into the harness branch in the order PARITY, EV, PEER, TRUTH, WORDING.
The test file's appended blocks and API.md's example were resolved as unions (0 lines removed from either side apart
from each side's declared edits), and the harness@2 fixtures were regenerated from the serializer. Each repair's patches
for files it did not own were applied. The session changed one runtime rule itself: the engine's first sentence of a
participant's own proposal now names a code Corti's bounded second review listed, as the page does, instead of saying
"Corti did not propose this code."; it is mutation-proved. Next: the full CI-like run and the Corti-only parity replay
on the merged head, a push, and a focused third refutation of the round-2 repair diff before the PR is made ready (each
round attacks the last round's repair).

### Session interpretation, 2026-11-02 (cd048041, after the harness's third refutation) — recorded, not owner-ruled

(a) **The third refutation, focused on round 2's repairs (`cdc41dfa2..624754eb1`), filed 35 findings through seven
lenses, and independent verifiers reproduced every one they checked.** Three were blocking, all in the status check
round 2 had built (D1): a readings-disagree hold was "verified" by the reader on one side of the disagreement ("The
sigmoid polyp was reportedly removed with a hot snare."), a denial in another clause of the sentence was not read ("A
hot snare was placed around the sigmoid polyp, but the polyp was not removed."), and a report title verified a
colonoscopy the document says was not performed; each time one reviewer confirmation made the code ready. Eleven more
majors were the same check's siblings for extent, cannulation, the E/M basis and the date (a hedge, a denial, a plan,
another occasion, a date of birth or a signature date written in a sentence, the last two sending Corti a request with
that date), a reviewer's confirmed conclusion shown to a peer as CPT Studio's own reading, and four gaps in the tests of
the confirmation path. The parity lens found nothing: I1 and D6 hold across the whole round-2 diff. Records:
`$S4/refute-harness-r3/findings.json`, `$S4/verify-harness-r3/results.json`, `$S4/verify-harness-r3/REPAIR-PLAN.md`.

(b) **Decision D7, taken by the session: this release offers no reviewer confirmation.** The confirmation endpoint
refuses and records nothing; the participants' located passages for an open question are still shown, with no claim
about what they state; the confirmation code stays, dormant, behind a code-level setting that defaults off and that no
installer, environment variable or member action can change (HARNESS.md 12.10). The reason is structural, not a matter
of one more repair: a fact is asked because CPT Studio's own readers did not establish it, and the three retained false
holds checklist 4.6 names (h4-01 99204, h4-03 43244, h4-06 45385) are all holds where the readers read nothing at all. A
check that verifies a passage only where the readers read its value can never verify those; a check that verifies more
is a second, weaker reader, and three rounds each found its next misreading in the previous round's repair.

(c) **Why the session may take D7, and what it leaves to the owner.** It is the fail-closed choice (hold, never offer);
harness@2 has never been installed, so no member loses anything they can do on the live site; the owner's completion
criteria (genuine Corti, Astra and Fable responses, traced references, a saved synthetic review, persistence after
reload, a reviewed download) do not need a confirmation; and it narrows a release after non-converging refutation, as
the owner's own decision of 2026-10-30 did. What checklist 4.6 becomes is the owner's question (class a), put to him
with two options and not decided here: (i) a human-override confirmation that claims nothing CPT Studio cannot check -
the reviewer's reading of the passage decides, the page says so, and approval stays a separate act; or (ii) no override,
with the false holds repaired at the readers themselves (the planned Wave 2: framed time, instrument reach), which also
improves Corti-only coding and is an I1-declared change.

(d) **Repaired in round 3 besides D7:** what a peer request shows of another model's codes, modifiers and ids (strict
shapes only); the retrieval-failure note, the positions and phase wording, Corti's unlisted codes, a reuse's counts,
Corti's alternatives and the one procedure-to-procedure statement per card; and the exchange records (a loop that lost
its database session sends nothing more, the installer's undo settles a run as the sweep does, a replayed exchange marks
nothing sent). At integration the session also made the owner's trace and a participant's problems show a model-written
code, modifier or id only in those strict shapes (I9). Each repair carries its tests and its mutation proofs; the
measurements on the integrated head are in its commit and in PR #1459.

### Session interpretation, 2026-11-02 (cd048041, after the harness's fourth refutation) — recorded, not owner-ruled

(a) **The fourth refutation, focused on round 3's repairs (`624754eb1..3daafa91b`), filed 24 findings, all reproduced,
none blocking (5 major).** The parity lens found nothing for the second round running. Three of the majors were in D7's
own display: the participants' "located passages" it still served under each open question were labelled "Their answer",
but their values were CPT Studio's own inferences from a reading ("Their answer: time" beside "Total time of 45 minutes
is not used to select the level"). Two were displays of a participant's own code-like text: a code the engine listed
because it was at most ten characters long, and a reference the participant cited but never retrieved.

(b) **Two further session decisions, each narrowing what CPT Studio claims or shows, neither an owner question for the
reasons D7's interpretation gives (fail closed; never installed; not in the completion criteria).** D8: with
confirmations off no candidate is served at all, and no sentence names a way a question is settled. D9: one strict-shape
rule for every value a participant wrote that CPT Studio lists or shows; Corti's own listing is unchanged, as I1
requires. HARNESS.md 12.12 indexes them and the round's other repairs.

(c) **What this means for the release.** A reviewer sees each open question, what it holds (the reviewed report, or one
code, which can still be rejected), and the participants' own readings and peer answers where they already were; CPT
Studio no longer puts a participant's passage forward as an answer. Checklist 4.6 stays the owner's open question as
interpretation (c) after the third refutation sets out.

### Session interpretation, 2026-11-02 (cd048041, after the harness's fifth refutation) — recorded, not owner-ruled

(a) **The fifth refutation, focused on round 4's repairs (`3daafa91b..0ca5e6623`), filed 20 findings, all reproduced,
none blocking (1 major).** The major was in the reports. A participant's peer answer was printed with CPT Studio's own
reading of its free text shown as the participant's answer, and that reader inverted "Cannulation of the bile duct was
not successful." into "successful", printed beside the participant's quote "Biliary cannulation was unsuccessful."
The others were sentences that claimed more than the code checks:
- the Clarification row's holds, false beside a rejected code, a stopped run and a Corti-only page;
- "proposed" said of entries with no located quote;
- two different counts of the same unlisted codes;
- a participant's HCPCS code called "a code CPT Studio does not read";
- the installer's advice to fix the credentials, beside a receipt showing that the vendor had answered.

The parity lens's one finding was the Clarification row on a Corti-only page.

(b) **Four further session decisions, each narrowing what CPT Studio says. None is an owner question, for the reasons
D7's interpretation gives.**
- **D10:** the reports print no value for a peer answer, only whether it is read as settling the question, with the
  passages it located.
- **D11:** the Clarification row only counts the open questions by what each is about; what holds the reviewed report
  is readiness's to say. This supersedes interpretation (c) after the fourth refutation in its words "what it holds
  (the reviewed report, or one code, which can still be rejected)".
- **D12:** "proposed" is said only of an entry with a located quote, on every surface; a participant that gave a code
  with no located quote is named as having listed it.
- **D13:** one count of a participant's codes that cannot be listed: the engine's.

HARNESS.md 12.13 indexes them and the round's other repairs.

(c) **What this means for the release, and what stays open.** A reviewer sees:
- how many questions are open, and what each is about;
- the readiness blockers, once;
- each participant's codes, as proposed or only listed;
- its peer answers, as claims with the passages they quote.

No value CPT Studio inferred from a participant's answer is printed or served. The inverting reader stays dormant (it
is not served while confirmations are off) and is recorded for option (ii) of checklist 4.6, which remains the owner's
open question.

The install's declaration draft is corrected before it is committed: Astra's and Fable's access check is one tool-loop
run each, at most four exchanges, so the act sends three to nine requests, not "exactly three".

## Owner directive, 2026-11-03 — finish round 6, check D10/D12's meaning, pursue the shared-reader repair, then install and walk

Received by session cd048041 at about 01:40Z, verbatim:

> Finish the currently declared round-6 review and repair any demonstrated defects. Keep the scope stable; initiate
> further review only when a concrete finding justifies it.
>
> For D10/D12, verify that the displayed conclusion preserves the quotation's meaning, negation, procedure ownership and
> time context. A quotation existing verbatim must not itself establish clinical support.
>
> Keep unresolved reviewer-confirmation functionality disabled until verified. Pursue the shared-reader repair for the
> known false holds; do not claim those holds are resolved by changing report wording.
>
> Once the applicable release gates pass, continue the declared installation and focused authenticated live walk.
> Demonstrate a clear synthetic case through actual Corti/Astra/Fable responses, reference retrieval, saved review,
> reload and a downloaded reviewed report. Report legitimate holds separately from software failures.
>
> Keep the pypdf audit result explicit. Do not silently waive it.
>
> In the next report, consolidate the exact wording, recommended choice and affected stages for checklist 4.6, D3–D5 and
> interpretation 68. Do not treat unresolved owner decisions as approved.
>
> Report actual requests, latency and usage. Completion requires the installed workflow—not test volume or another
> written contract.

### Session interpretation, 2026-11-03 (cd048041, on receipt) — recorded, not owner-ruled

(a) **Round 6 runs as declared and is not widened.** Five lenses attack round 5's repairs
(`0ca5e6623..ee570e4bc`), sandbox `.lens-harness-r6`, workflow `wf_0aecfe24-e67`, launched 01:19Z. Only reproduced
findings are repaired. A further round runs only if a concrete finding justifies it, and its scope is that finding.

(b) **The D10/D12 meaning check is a bounded verification the owner asked for, not a new review round.** It renders
every surface that states a conclusion about a participant's quotation (the cards and their evidence, positions,
alternatives, peer rows, the reports, the trace). It feeds them synthetic quotations that are verbatim in the document
but negated, about another procedure in the same document, or about another time (history, a prior visit, a plan).
For each surface it checks:
- that the displayed conclusion keeps the quotation's meaning;
- that nothing reads verbatim presence as clinical support.

HARNESS.md I2 already makes readiness the local readers' alone. This check is about what the displays say. Defects it
demonstrates are repaired under the same rule.

(c) **Reviewer confirmation stays disabled** (D7, `STUDIO_OFFER_CONFIRMATIONS = False`). Nothing here changes that.

(d) **The shared-reader repair for the three retained false holds is pursued as its own change.** The holds are h4-01
99204, h4-03 43244 and h4-06 45385. The change goes on a branch from `main` after the harness merges, with its own
refutation and an I1 declaration, since the readers are shared with the Corti-only path. No report wording is offered
as resolving them. Checklist 4.6 stays NOT DONE and an open owner decision. This directive's instruction to pursue the
reader repair is acted on as work. It is not recorded as the owner choosing option (ii) over option (i).

(e) **The release gates, before the declared install:**
- round 6 repaired;
- the CI-like suite green;
- I1's replay EQUAL and battery 0 on the final head;
- the PR's CI, with the cpt-studio job's pypdf audit stated as red with its seven advisories (interpretation 68),
  never waived;
- the merge through `scripts/merge-pr.sh`;
- the install declaration committed on `main` through its own PR before the act.

Then the install phases through `scripts/run-ruled-mutation.sh`, and the focused authenticated walk on a clear
synthetic case. The walk reports legitimate holds apart from software failures.

(f) **The next report gives:**
- the exact wording, a recommended choice and the affected stages of checklist 4.6, D3, D4, D5 and interpretation 68,
  each as still open;
- the access check's and the walk's actual requests, latency and usage, from the receipts and the recorded runs.

### Session interpretation, 2026-11-03 (cd048041, after the sixth refutation and the meaning check) — recorded, not owner-ruled

(a) **Round 6 is repaired.** Its 12 findings, all reproduced and all minor, are repaired by R6-TRACE, R6-ROW and
R6-SENDS. The answers lens found nothing. HARNESS.md 12.14 records each repair.

(b) **The D10/D12 meaning check did not hold.** Its 15 findings were all reproduced: 10 blocking, 1 major and 4 minor.
In each blocking finding a code became READY and approvable on a verbatim quotation that does not support it: a failed
act, a denial, another procedure's sentence, a pathology addendum, or an indication or history line. There are two
paths, and they are recorded apart:
- **Through the harness.** A participant-only code reached READY on the participant's quotation alone. That path was
  never installed, and D14 (c) closes it.
- **On the installed Corti-only path** (80df1831d168). Corti's own selection quoting such a passage is READY the same
  way. It was reproduced with participants disabled for 10 of the findings. I1 pins it, so this release neither
  introduced nor changed it. Two of its classes were already accepted as accuracy residuals, r1 release-0 and r1
  release-1 in ACCURACY-RESIDUALS.md, "because no code is approved without a reviewer". The check adds members those rows
  do not name. HARNESS.md 12.14 lists each reader with its input and its verifier's sketch.

(c) **D14 (session decision, fail closed, the D7 pattern the owner endorsed: "keep ... disabled until verified"): in
this release a participant's code is never a proposal.** A code no decidable proposal carries is listed as an
alternative with CPT Studio's own reason. Participants never make a code ready, never count as covering a documented
act, never make another code included and never clear an unresolved item. Corti's proposals are assessed exactly as with
no participant configured. Checklist 4.3 still holds: the three outputs are reconciled, services Corti omitted included.
**Owner question (class a), recorded and not answered here:** should a participant's own code ever become a selectable
proposal again, and on what reader guarantee? The recommendation is: only after the shared-reader repair passes its own
refutation, and re-enabled by the owner.

(d) **The Corti-only false READY is the first target of the shared-reader repair**, ahead of the three false holds
(h4-01, h4-03, h4-06) that interpretation (d) of 2026-11-03 named. A false READY is the harm the readers exist to
prevent. The repair is an I1-declared change on its own branch from `main`, with its declarations before code and its
own refutation cycles. This install does not change the defects' exposure. Whether to pause the live demonstration until
the repair lands is the owner's decision. The report puts it first, and the session does not decide it.

(e) **A narrow seventh refutation runs before the PR is made ready, and it is required, not optional.** D14 changes
which codes can be selected, so it is a change on the clinical decision path, and the standing gate (AGENTS.md, "THE
ADVERSARIAL PASS IS MANDATORY ON THE CLINICAL GENERATION PATH") requires a refutation of the finished diff. Its scope is
the concrete findings that justified this round's repairs, and nothing wider:
- D14's completeness;
- the displayed wording of the repaired surfaces;
- I1 parity;
- false-green gaps in the new pins.

The diff is `de6418fc6..` the integrated head. Only findings it reproduces are repaired, under the directive's rule.

(g) **The shared-reader repair's design is done (read-only).** It recommends that no rule release the three false
holds now:
- the visit rule (R-EM, for h4-01) is not to be coded, because no revision survived its critic's counterexamples;
- the extent rule (X2, for h4-03) is to be coded only under a parity standard the owner has not ruled: a release may
  have exactly the exposure installed routing already has on the named twin of the same document, never wider;
- h4-06 stays a recorded limit.

It also confirmed two more installed false READYs, each a hold-only item for the same repair (HARNESS.md 12.14). **Owner
question (class a), recorded:** which release standard governs a reader repair? Under the round-4 standard every
must-stay-held input stays held and a contained release counts as blocking. Under the parity standard a release may be
exactly as wide as the named twin, and never wider. The session applies the round-4 standard until the owner rules;
under it, checklist 4.6's holds stay recorded limits.

(f) **The release gates of interpretation (e) of 2026-11-03 stand**, with round 7's reproduced findings repaired and
the gates re-run on the final head. The pypdf audit stays red with its seven advisories (interpretation 68) and is
stated, never waived.

## Owner directive, 2026-11-03 (second message) — the shared-reader core repair and the customer interface

Received by session a12d8fb3 at about 22:30Z, verbatim:

> Implement the CPT Studio core repair and customer-interface improvements below on https://cpt.quillmd.com. Complete the work through installation and verification.
>
> **Keep the existing website and demo accessible while you work. Do not pause the demo, introduce a maintenance page, or disable customer access as the default approach.** Develop in isolation, keep the current release serving, and install a compatible update with health checks and rollback. Preserve active jobs and saved work. If an installation method would cause interruption, find an alternative before proceeding.
>
> Maintain a checklist with PASS, FAIL, BLOCKED and NOT RUN states. Tick an item only after verifying it. Continue authorized routine work without asking me for approval at every step.
>
> ## 1. Fix the shared document-reading logic
>
> Repair the general interpretation rules, not individual documents or expected-code fixtures.
>
> The live Mara encounter is:
> https://cpt.quillmd.com/#doc/effe4d0b-b449-4efd-b208-635ca1d09984
>
> Observed facts:
> - Its incorrect manual service date was 1998-01-01. That override has been cleared; the effective date is now 2026-11-03.
> - Corti, Astra, Fable, both peer reviews and the reference stage completed.
> - Suggestions are 43239, 45380 and 45385.
> - 45380 is ready for review; 43239 and 45385 remain held.
> - Five questions remain: two code questions and three office E/M questions.
> - No codes have been approved.
>
> Confirmed interpretation defects:
> - The app uses “No biopsy forceps were used on COL-2” to contradict affirmative esophageal/gastric biopsies. COL-2 is a sigmoid-colon lesion, not the upper-endoscopy procedure.
> - It treats “The forceps removal was not a biopsy of, or a completion step for, the snare-treated sigmoid lesion” as negating the documented snare removal. That sentence distinguishes two separate lesions.
> - It assigns the prophylactic sigmoid resection-site clip to the upper endoscopy.
> - It asks office setting, new/established status and E/M level questions despite the explicit statement: “No separate office evaluation and management encounter or office-visit time is documented on this date.”
>
> Bind each statement to its procedure, lesion, anatomy, action, time and responsible provider. Keep negation within its actual scope.
>
> When the document already supplies the answer, repair the reader and reassess from the source. Do not require doctors to rewrite an adequate report to overcome a parsing bug. Preserve genuine uncertainty and conflicting documentation.
>
> Also reproduce and repair the previously reported shared safety defects if they remain present:
> - Failed, negated, historical or wrong-procedure evidence allowing a code to become ready.
> - Restoring a therapeutic code such as 45385 without recomputing its conflict with a diagnostic base code such as 45378.
>
> Recompute relevant checks after every selection, restoration, context change, reload and export. Do not approve codes through model agreement or hardcoded expected results.
>
> ## 2. Remove provider identities from the customer experience
>
> Doctors and customers must not see Corti, Astra, Fable, OpenAI, Anthropic, Claude, model IDs or internal orchestration details in ordinary product screens or reports.
>
> Use functional labels such as:
> - Document review
> - Independent checks
> - Coding validation
>
> Prefer one compact progress panel over a long list of individual agents. These labels describe software functions; do not invent human reviewers or certifications.
>
> Remove customer-facing:
> - Participant/model lists and peer-review machinery.
> - Tool-call counts, token usage, internal credits and request IDs.
> - Raw reference retrieval logs, source hashes and technical rule IDs.
> - Trace links, raw provider responses and developer diagnostics.
> - Provider names in downloads, notifications, accessibility labels and error messages.
>
> **Enforce this on the server. CSS hiding or collapsed panels are insufficient.** Customer API responses and customer bundles must not expose these internal details.
>
> Keep complete provenance, exact provider/model identities, usage, failures and audit history available through authenticated platform-operator diagnostics. A customer practice administrator or tenant owner must not automatically gain platform-operator access. Verify direct diagnostic URLs and API authorization.
>
> Keep legally required privacy/subprocessor disclosures accurate. This request concerns routine product presentation, not falsifying required disclosures.
>
> ## 3. Make the result simple and codes-first
>
> The main result should be a short numbered list:
>
> 1. CPT number
> 2. CPT number
> 3. CPT number
>
> Each row should show:
> - Code.
> - Units and modifier when applicable.
> - Clear status: Ready for review, Needs a detail, Approved or Excluded.
> - One short, document-based explanation.
>
> Put the supporting quotation and any material qualification behind an optional “Why this code?” control. Keep engineering logs out of this view.
>
> Provide clear review and download actions. Distinguish suggested codes from approved codes. Approved exports must exclude unresolved or unapproved items and match persisted decisions.
>
> Retain concise, meaningful limitations. Do not imply complete validation when reference coverage is incomplete, and do not show unlicensed descriptions as official CPT content.
>
> ## 4. Replace cumbersome clarification cards with a short confirmation flow
>
> Doctors should not have to write an addendum for every routine context question.
>
> - Suppress irrelevant questions, including E/M questions when no separate E/M service is documented.
> - Resolve facts already stated unambiguously through the repaired reader.
> - Group genuinely missing details into one compact “A few details needed” panel.
> - Use relevant choices, date selectors and brief confirmations instead of repeated free-text forms.
> - Allow “Not documented” or “Cannot confirm” where appropriate.
> - Ask each material question once and preserve the saved answer.
> - Allow supported, independent services to remain reviewable while a different service awaits clarification.
>
> For a date conflict, show the document date and entered date together, with a clear “Use document date” action. Do not silently choose between genuinely conflicting dates or prefill an unsupported date.
>
> Store member-provided context separately from the original document, with attribution and audit history. Do not manufacture physician-authored addenda, clinical facts or approvals.
>
> For separately treated forceps/snare colon lesions, provide appropriate modifier review using available dated sources. Do not automatically append both 59 and XS or claim complete payer validation without the necessary coverage.
>
> ## 5. Show unmistakable upload and processing progress
>
> Immediately acknowledge a successful upload and show visible progress while the document is processed.
>
> Use plain stages tied to actual backend state, for example:
> - Reading your document
> - Identifying procedures
> - Checking suggested codes
> - Preparing your results
>
> Show the active stage, completed stages, elapsed time and a truthful status update. Make it clear when the user can leave the page and return.
>
> Requirements:
> - Distinguish uploading, queued, processing, awaiting a detail, completed, partially completed and failed.
> - Do not invent percentages or display an exact ETA without reliable measurements.
> - If processing takes longer than expected, explain what is actually happening.
> - Do not keep an animation running after the job has failed.
> - Display actionable errors in plain language without provider names or technical payloads.
> - If a date conflict prevents submission, show “Action needed” immediately rather than implying processing has begun.
> - Preserve progress and job identity after reload or reconnect.
> - Provide a working Stop path and safe recovery.
> - Reconcile unknown outcomes before retrying. Refreshing, reconnecting or opening results must not create duplicate paid requests.
>
> ## 6. Verify and install the complete repair
>
> Use existing authorized accounts and standing private synthetic-testing authority. Keep purposeful, bounded execution and provider-call concurrency one. Preserve originals, raw responses, historical failures, decisions, usage and rollback evidence.
>
> Acceptance checklist:
> - [ ] Shared procedure/lesion/negation binding repaired.
> - [ ] Absent separate E/M no longer creates unnecessary questions.
> - [ ] Unsupported evidence and diagnostic/therapeutic conflicts remain correctly blocked.
> - [ ] Customer screens, API responses and downloads omit provider identities and technical traces.
> - [ ] Operator diagnostics remain intact and protected from customer accounts.
> - [ ] Compact code results and clarification controls work on desktop and mobile.
> - [ ] Upload acknowledgement, real progress, failure, Stop and recovery states work.
> - [ ] Reload/reconnect preserves the existing job without duplicate submissions.
> - [ ] Mara is reassessed using retained responses where possible, with no fabricated answers or approvals.
> - [ ] One fresh synthetic GI case passes the installed workflow with actual provider responses.
> - [ ] Review decisions persist after reload.
> - [ ] An actual approved report is downloaded and independently compared with saved selections, units, modifiers and source evidence.
> - [ ] Existing records and exports remain preserved.
> - [ ] The live site remains accessible during development and after installation.
>
> Label any test approvals as agent-executed synthetic reviews. Do not present them as a doctor’s clinical approval.
>
> Use focused regression tests and a bounded independent review of the changed paths. Avoid endless broad audit rounds without new evidence.
>
> Finish by reporting the installed revision, checklist results, customer-facing screenshots, actual download evidence, measured usage and remaining limitations. Report functional completion, clinical accuracy validation and content-use permissions separately. Do not describe a passing synthetic case as guaranteed accuracy.

### Session interpretation, 2026-11-03 (a12d8fb3, on receipt) — recorded, not owner-ruled

(a) **The live demonstration is not paused** while this work runs, and no install method that interrupts it is used.
This answers the open item of interpretation (d) of 2026-11-03 (after the sixth refutation): the owner's instruction is
to keep the site and the demonstration available. Development happens in isolated worktrees and throwaway databases; the
installed release keeps serving until a successor has passed its health checks.

(b) **The shared-reader repair is one I1-declared change.** Its expected movements are written down before the code
(the gi4 harness's declaration files), and measured after it (replay, battery, mutants). The four Mara defects are
repaired as classes: statement-to-procedure and statement-to-lesion binding, negation scope, act-to-procedure
assignment, and an explicitly absent separate E/M service. No document, patient name or expected code is special-cased.
The round-4 release standard keeps governing (a must-stay-held input stays held); the parity-standard question of
2026-11-03 stays open and is not answered by this directive.

(c) **The bounded independent review is the standing refutation pass, bounded.** One round of distinct lenses over the
finished diff, each finding verified before it is believed, the reproduced findings repaired, then one narrow check of
those repairs only. A further round runs only on new evidence (the directive's "avoid endless broad audit rounds").

(d) **Platform-operator access is a grant on the user, never a consequence of a workspace role.** The workspace owner
role stops opening the administrative trace. Customer API responses, customer downloads and the customer bundle are
built without provider identities, model ids, usage, request ids, hashes, rule ids or traces, on the server; operator
diagnostics are served separately and keep the full record.

(e) **Existing records stay as they are.** Assessments, provider runs and their raw bytes, decisions and the 122
stored report artifacts are neither rewritten nor deleted. Older artifacts name participants, so they are served
through operator diagnostics; a customer download is a newly generated customer report of the persisted state.

(f) **Member answers are context, never clinical documentation.** Routine encounter context (the date of service, the
setting, new or established status) is answered with choices or a date selector and stored as member-provided context,
attributed and audited, apart from the document. A clinical fact (an act, its status, an E/M level or time) is never
supplied by a member answer: the choices are "Not documented" or "Cannot confirm", or the physician's own addendum.
Genuinely conflicting documentation stays held. Checklist 4.6 (a reviewer override) stays an open owner decision; this
directive is not read as choosing it.

(g) **Mara is reassessed from its retained responses** (no new provider request), as a declared act after the install.
The session answers none of its questions and approves none of its codes.

(h) **Test approvals are agent-executed synthetic reviews**, labelled so wherever they appear, on a fresh synthetic
document only.

(i) **Disclosures.** CPT Studio serves no privacy or subprocessor disclosure today (no such text in its templates,
static files or views). This change removes none and writes none; whether one is legally required is not decided here.

(j) **Requests and money.** Provider-call concurrency stays one. Mara's reassessment sends nothing. One fresh synthetic
document costs one Corti request and the participants' bounded exchanges (about US$0.3 to US$0.5 at the 2026-11-01
rates), plus the install's access checks; the US$10 stop of 2026-11-01 stands.

The working checklist is `CPT-CORE-UX-CHECKLIST.md` at the repository root.

### Session interpretation, 2026-11-03 (a12d8fb3, after mapping main and its completeness critique) — recorded, not owner-ruled

Nine read-only maps of `main` and a completeness critique (session scratch, `understand/R1..R9`, `critic.md`) reproduced
Mara's four defects byte for byte and every previously reported false READY of HARNESS.md 12.14 (register D1-D15, all
still present on the Corti-only path). These decisions bind the build:

(a) **Status follows CPT Studio's own reading of the documented service, never the provider's quotation** (the existing
design: ARCHITECTURE 5.10; the engine's `support` check never decides a status). So a code whose act CPT Studio reads as
performed today, in its own procedure and at its own lesion, may be ready even when the provider quoted a weaker passage.
The customer's "Why this code?" shows CPT Studio's own located passage first. The new narrow evidence hold only ADDS
holds: a code is held when every provider passage lies in another documented service or reads as another time or a
denial. A broad rule (hold whenever no provider passage shows the act) is not adopted, and is not offered as an owner
question.

(b) **The E/M questions are removed at the reader only.** The explicit "no separate E/M ... documented" statement is read
as a denial by both the routing and the documented-service readers, through one shared pattern. A validation-side
suppression of E/M questions is not adopted: it would also hide the questions for a visit that is stated ("An office
visit was also completed today.") but has no time or decision-making documented.

(c) **The A1 class stays closed.** Rule 5 of the binding map (a per-procedure heading kept in force over later structure)
and rule 6 (tract binding) are not part of this change. A1 was dropped after its second refutation (`pi.json`,
`amendment_20261101_cycle2`), and Mara needs only rules 1, 2, 3, 4 and 8: lesion labels, attributive compounds, copular
negation scope, combined titles, and the E/M denial. Reopening A1 would need its own decision.

(d) **The hold-only register repairs land with or before any rule that removes an act**, and every rule is measured at
proposal level (an act removed from the inventory must not be released back to ready by the own-passage path).

(e) **Member answers never release a code.** "Not documented" or "Cannot confirm" moves a code from "Needs a detail" to
"Excluded". It is never approvable and needs no further decision, until the answer is revoked. A member never supplies
a clinical fact. Only routine context (date of service, setting, new or established status, billing context) takes a
value. The dormant reviewer-confirmation path stays off (checklist 4.6 stays an open owner decision).

(f) **The approved export.** It is available only when every suggested code is resolved: approved, rejected or excluded,
or its detail answered as unavailable. It lists the approved codes only. A partial approved export is not built. The
directive's "exclude unresolved or unapproved items" is met by construction, and no export can be mistaken for a
complete review.

(g) **Older stored reports become operator-only.** They name the participants and carry hashes, and the directive
requires customer downloads without them. Customers can generate a new customer report of the persisted state at any
time. The stored bytes are kept unchanged. This loss follows from the directive itself, so it is not asked as an
accepted-capability question.

(h) **Operator access uses two new accounts** with recorded grants and no workspace membership:
- `platform-operator`, a human account for the owner, with its password in a root-only file;
- `ops-agent`, the automated verification account, with its password file 0600 under the session's home.

No workspace role confers access. The live refusal of operator URLs is proven with the reviewer and agent accounts. The
tenant-owner refusal is proven by the test suite, because the session does not sign in as the owner.

(i) **Test approvals in this directive's walk go through `review-agent`.** That account's approvals are labelled
"agent-executed synthetic review" everywhere, as the directive asks. Interpretation 63's labelled human-account path is
not used for this walk.

(j) **A dead worker never animates.** A worker heartbeat lets the progress panel say that processing is paused when no
worker has been seen recently.

(k) **A Corti run left `sending` after its job failed blocks further sends like an unknown outcome**, closing a recorded
duplicate-send edge.

(l) **A browser tab opened on the previous release gets a "reload" message, not a broken page.** Customer API calls
carry a client contract header, and a call without the current one is answered 409 `client_outdated`.

(m) **Disclosures.** CPT Studio has no privacy or subprocessor page, and after this change no customer screen names a
subprocessor. Whether a disclosure is legally required elsewhere is an owner or legal question, recorded here and not
answered.

**Session decisions (n) and (o), 2026-11-04 (lead integration, session a12d8fb3).** Both close seams the wiring report
found. Each keeps a capability or a ruled rule rather than removing one, so neither is a product decision without
precedent, and neither is an accepted-capability loss.

(n) **The customer page keeps the bounded second review.** The installed page (41e03656df61) offers it to owners and
reviewers as "Ask the provider once more". The new customer contract left it out without a decision: CORE-UX-DESIGN.md
section 7 never names it, and R4's open question 1 ("keep as a customer action with functional wording, or make it
operator-only?") was left undecided. Making it operator-only would take away something customers have, which is the
owner's trade to accept. Keeping it is the installed state. So it stays, worded by what it does and naming no provider:
"Check what is still open again", under "Still open".
- The server sends `recheck: {available, can_request}`. `available` reads `jobs.second_review_status`, the same predicate
  POST second-review accepts an ask by. `can_request` is true only for owners and reviewers.
- An assessment never queues one (owner decision 2026-10-27), and the offer itself sends nothing.

(o) **The customer queue lists what its badge counts.** The badge kept the review queue's rule, which refutations gi2
RC6 and ec5 pinned (`serializers.queue_reasons`, joined with the three customer states that wait on the member). The page
listed only those three states, so the badge could count documents the queue never showed: in the fixtures it counted 9
and listed 7. The rule is unchanged. Each list row now carries `in_queue`, the predicate the session counts
(`customer_api.in_queue`), and the queue lists exactly those rows. The queue's wording names "something still open"
beside a date, a detail and codes to review.


## Owner directive, 2026-11-05 — the GI core and multi-agent harness repair (D14's controlled replacement)

Received by session a12d8fb3 at about 09:03Z, verbatim:

> Complete the CPT Studio GI core and multi-agent harness repair, install it on https://cpt.quillmd.com, and verify the actual customer workflow. Fix the shared system, not just one document.
>
> Keep the existing site accessible while working. Use the normal installation and rollback process. Do not pause the demo by default, weaken clinical safeguards, or call incomplete work finished.
>
> CHECKLIST AND REPORTING
>
> Read and update the existing CPT-HARNESS-CHECKLIST.md and cpt-studio/HARNESS.md before implementation. Preserve previous history and add a dated section for this repair.
>
> Use these marks:
> - [ ] Not completed
> - [x] Completed and verified, with evidence
> - BLOCKED — exact dependency and work that can continue independently
>
> Every tick must identify the relevant revision, test or live observation, and evidence path. Previous tests, replay and access checks cannot substitute for fresh installed acceptance.
>
> Report the checklist after each major stage. Do not advance dependent stages past a failed gate, but continue useful independent work. Do not repeatedly ask permission for already-authorized engineering and private synthetic testing.
>
> CURRENT FINDINGS TO VERIFY
>
> The inspected encounter is:
> https://cpt.quillmd.com/#doc/88d9db32-65b5-4a55-98ee-b82ce0da8941
>
> Last observed live release:
> b0dc3446c64c840cd01e9f37b8de3bad7aa954d4
>
> The customer page showed:
> - 43239 and 45380 ready for review.
> - 45381 held by a false tattoo performed/not-performed conflict.
> - 43249, 45390 and 45385 listed only as alternatives.
> - Dilation, EMR, snare removal and gastric decompression unresolved.
> - A rectal biopsy explanation incorrectly included the sigmoid.
>
> The source contract’s D14 restriction prevents participant-only codes from becoming reviewable proposals. Therefore, additional Astra/Fable suggestions cannot currently recover omissions directly.
>
> These observations do not prove which provider omitted or selected each code. Inspect the protected original responses and reconciliation decisions before attributing responsibility.
>
> The owner already requested this encounter’s bounded second review at 2026-11-05 07:43 UTC. Preserve that consumed attempt. Do not reset it or resubmit it blindly.
>
> LOCAL REPAIR PACKAGE
>
> A local reader repair against that release passed 183 focused tests and 28 independent targeted checks. It was NOT installed and did NOT enable participant-only proposals.
>
> If available, inspect its manifest and accepted repair.patch. It changes:
> - studio/gi/services.py
> - studio/gi/detect.py
> - tests/test_advanced_gi_binding.py
>
> Do not install anything from rejected-experiment-DO-NOT-APPLY. Its decompression shortcut hid therapeutic or failed procedures and was rejected.
>
> If the ZIP is unavailable on the VPS, continue from the server repository and the findings above. Do not wait indefinitely for a Windows-only path. Verify current main and the served release before applying or adapting any patch.
>
> REQUIRED CHECKLIST
>
> [ ] 1. Establish the current baseline.
> Read project instructions, run required preflight, use an isolated worktree, and avoid concurrent deployment writers. Record the served revision, current configuration and preservation baseline. Preserve originals, responses, failed attempts, approvals, audit history and existing downloads.
>
> [ ] 2. Trace the actual harness.
> Inspect Corti, Astra and Fable first assessments, peer reviews, references and final reconciliation for the affected encounter. Identify exactly where each missing service or code was lost, held or made informational. Record facts rather than assuming model failure.
>
> [ ] 3. Repair shared interpretation.
> Correct tattoo versus resection negation, future localization versus future performance, comparison anatomy, and lesion ownership. Keep genuine contradictions, failed procedures, historical services, planned procedures and other-provider services protected. Do not hardcode this encounter or its expected code numbers.
>
> [ ] 4. Replace the blanket participant-proposal restriction safely.
> I authorize implementing a controlled replacement for D14’s blanket prohibition: an explicit proposal from Astra or Fable may enter the human-review workflow after the full source-validation path passes.
>
> Apply equivalent eligibility standards regardless of originating provider:
> - Correct procedure and performing provider.
> - Actual performance on the relevant service date.
> - Correct anatomy, lesion, technique and extent.
> - Exact evidence interpreted in its complete context.
> - Applicable relationship, reference and uncertainty checks.
>
> A quotation existing, model confidence, or agreement between models is insufficient. Raw alternative lists must not be automatically promoted. No model may approve a code.
>
> Record this changed requirement in the harness contract and checklist. Preserve true origin in protected diagnostics.
>
> [ ] 5. Preserve the complete harness.
> Keep Corti, Astra and Fable participating. Freeze and hash independent first assessments before peer conclusions are shared. Store peer-review results separately. Preserve reference-tool traces and dated source provenance.
>
> A skipped, refused, malformed or failed participant means partial completion—not a successful three-participant harness. Do not silently substitute models.
>
> [ ] 6. Reconcile the complete service set safely.
> Check distinct procedures and lesions, included components, units and potential modifier requirements. Do not separately charge EMR components or prophylactic clipping.
>
> Investigate gastric decompression without restoring the rejected automatic-bundling shortcut. Do not hide therapeutic or failed decompression to clear completeness.
>
> Recompute relevant relationships after clarification and review decisions, on reload, and before export. Do not make the six provisional candidate numbers an acceptance oracle; adjudicate them from documentation and applicable sources.
>
> [ ] 7. Keep the doctor-facing experience simple.
> Show CPT numbers, units/modifiers where supported, short source-based reasons, review status and only necessary questions.
>
> Keep provider/model identities, internal prompts and technical traces out of customer APIs, HTML, accessibility text, browser logs and downloads. Preserve them in protected operator diagnostics.
>
> Show truthful processing stages, elapsed time and failure states. Never display “Done” merely because a stage stopped.
>
> [ ] 8. Verify the finished implementation.
> Run meaningful Linux tests and required CI. Independently refute the finished diff with concrete counterexamples, especially false approvals, negation, time, procedure ownership, multiple lesions and misleading completeness.
>
> Reproduce findings before repairing them. Preserve failures. Do not weaken assertions or safety checks to pass. Use bounded, purposeful verification rather than endless broad campaigns.
>
> [ ] 9. Install and reassess retained evidence.
> Merge through the required project gates and install using a declared, reversible deployment that keeps the site available.
>
> Reassess the affected encounter from retained responses with provider sends disabled. Preserve the prior assessment and decisions. Verify the actual served behavior and explain any remaining omissions.
>
> [ ] 10. Complete fresh live acceptance.
> Use the existing standing authority for necessary private synthetic testing and existing authorized provider accounts. Do not reintroduce superseded funding ceilings. Keep usage records, finite deadlines, concurrency controls, duplicate prevention and Stop.
>
> Run a small fresh synthetic acceptance set with new document/run identities, including Word and PDF inputs. Establish expected services and provisional coding independently before inspecting outputs.
>
> Prove actual Corti, Astra and Fable participation, review decisions, reload persistence and an actual downloaded report matching those decisions. Label agent-executed synthetic approvals honestly. Never fabricate human clinical review.
>
> COMPLETION REPORT
>
> Return the full checklist with evidence-backed ticks and clearly identify:
> 1. What was repaired.
> 2. What is installed and its exact revision.
> 3. What passed live, including downloadable results.
> 4. Whether missing independent proposals now have a working, validated human-review path.
> 5. Remaining clinical, reference, modifier or licensing limitations.
> 6. Actual usage and estimated versus confirmed costs.
>
> Keep functional completion, clinical accuracy and content-use permissions as separate verdicts. Do not claim guaranteed accuracy or invent missing reference coverage.
>
> Carry this through implementation, installation and verification using existing authorized access. Escalate only a genuine unavailable credential, necessary external agreement or other dependency you cannot resolve—not routine engineering failures.

The owner's follow-up in the same turn, verbatim: "The repair package is at
/home/claude/CPT-Advanced-GI-Repair-20261105.zip. Inspect it and continue using the harness repair prompt and
checklist. Do not apply the rejected decompression experiment."

### Session interpretation, 2026-11-05 (a12d8fb3, on receipt) — recorded, not owner-ruled

(a) **D14's owner question is answered by this directive** (HARNESS.md 12.14, class a): a participant's own code may
again become a proposal, by the controlled path the directive authorizes and on no other. The two other open owner
questions are not answered by it and stay open: 4.6 (reviewer confirmation) and the release-standard question (the
round-4 standard or the parity standard). D3 to D5, interpretation 68 and decision (m) stay open too.

(b) **Which participant codes can enter.** Only an explicit proposal: an entry of the `codes` list of a participant's
frozen first reading, quoting the document verbatim. A code a participant adds in peer review (`additional_codes`) was
proposed after it had seen its peers' conclusions, so it is not an independent proposal and stays informational, as does
everything a raw list holds: a first reading's `not_coded`, Corti's candidates and alternatives, and any alternative row.

(c) **The path is the proposal provider's own, with the second review's admission rule.** Such a code is read by the
same per-code path as Corti's selections (scope, exact evidence, the routed family, the documented service and act, the
P2 READ-HOLD holds, the passages' support, required facts, PFS, MUE, the endoscopic base), from its proposers' exact
spans only. It becomes a proposal only where, like a code the bounded second review selected, it accounts for a
documented service or act that the decidable proposals left unresolved and that the documented-service reading documents
as done; otherwise it stays an alternative that says why. Where two different participant codes would account for the
same unresolved item, neither is added: CPT Studio does not choose between participants, and the item stays open with
both listed. A quote existing, a model's confidence and agreement between models add nothing (I3).

(d) **No model approves a code.** A participant's proposal is ready or held by CPT Studio's readers alone, and only a
workspace member's decision approves it. Approvals made by the session's automated review agent in acceptance testing
are recorded under that agent account and labelled as agent-executed synthetic reviews.

(e) **Origin is kept, and kept protected.** A participant's proposal records `origin: participant`, its proposers and
their phases in the assessment (the operator console and API serve it). Customer surfaces word it without any
participant's or model's identity.

(f) **The repair package is reviewed input, verified before use.** Its accepted `repair.patch` applies cleanly to
`main` (`8645fd54`), whose `studio/gi/services.py` and `studio/gi/detect.py` are byte-identical to the base release's; the
patched files equal the package's sources except for Windows line endings; on Linux its focused modules pass (125
tests), and on unpatched `main` its new binding module gives 8 failures and 1 error, as the package reported. The
rejected decompression experiment is neither applied nor copied into the repository.

(g) **Gastric decompression is investigated without the rejected shortcut.** The coverage catalogue has no
upper-endoscopy code that accounts for a decompression act, so an upper endoscopy that states "the stomach was
decompressed" is reported incomplete with nothing that can resolve it. The direction taken is recorded here when it is
decided (stage 6); a therapeutic or failed decompression is never made to disappear.

(h) **The consumed second review stays consumed.** The encounter is re-assessed from its retained responses with every
send disabled (the installer's reassess phase); no attempt is reset, re-sent or given a new identity.

(i) **The demonstration stays available.** Development in isolated worktrees and throwaway databases; the install is
blue/green through the ruled-act door, under a committed declaration, with the rollback image kept.

(j) **The refutation pass is bounded.** One round of distinct lenses over the finished diff; each finding reproduced
before it is repaired; then one narrow check of those repairs only; a further round only on new evidence.

(k) **Funding ceilings are not reintroduced.** Usage is recorded per run, one provider call at a time, with finite
deadlines, duplicate prevention and Stop, as installed.

## Owner directive, 2026-11-05 (second message) — genuinely independent admission, Fable's contract, recoverable Stop, the remaining interpretation repairs

Received by session a12d8fb3 at about 20:24Z, after the install of `e6d451f03d86` and its record (#1476), verbatim:

> Continue the existing CPT Studio GI repair. Do not restart the project or discard the existing checklist and evidence.
>
> Astra and Fable are primary code-finding participants. Corti remains another contributor, not a whitelist or veto over their proposals. I want the complete harness working before calling the GI release complete.
>
> Keep cpt.quillmd.com accessible while repairing, testing and installing updates.
>
> REQUIRED BEHAVIOR
>
> An explicit, source-supported proposal from Astra or Fable must be eligible for human review even when Corti:
> - omitted the code;
> - returned another code;
> - listed that code only as an alternative.
>
> Use a provider-neutral validation path. Reusing shared validation code is fine; requiring Corti to select or endorse the proposal is not.
>
> Do not automatically promote every number mentioned by a model. Distinguish an explicit proposal from a raw alternative, rejected suggestion or quoted example. Require correct procedure, actual performance, date, provider, anatomy, lesion, technique and supporting evidence. Model agreement alone never establishes correctness, and no model approves a code.
>
> “Passes the same path as Corti” is insufficient proof while that path has known negation and timing defects.
>
> FIRST: FIND MY CURRENT OMITTED CODE
>
> Inspect my latest identifiable synthetic GI test and determine exactly why its code was “not considered.” Do not assume it is the earlier PDF or assume Corti caused it.
>
> Trace:
> document → each independent assessment → normalized proposals → source validation → reconciliation → customer display.
>
> Report the encounter, code, originating proposal, exact exclusion reason and responsible component. If the exclusion is clinically justified, explain it; otherwise repair the shared cause. Do not force a code into the results merely to satisfy this request.
>
> If the exact recent encounter cannot be identified, ask only for its link or code while continuing the independently actionable repairs below.
>
> CHECKLIST — UPDATE THE EXISTING CPT-HARNESS-CHECKLIST.md
>
> Keep items 3, 5 and 10 PARTIAL until their missing requirements actually pass. Tick [x] only with current evidence. Report this checklist after each major stage; do not silently drop requested repairs and declare completion.
>
> [ ] 1. Diagnose the current omission.
> Identify whether it comes from response parsing, proposal admission, source interpretation, catalogue coverage, bundling, missing documentation or display. Preserve the original result and raw responses.
>
> [ ] 2. Fix Fable’s response contract.
> Inspect the three rejected responses and the unexpected fields in not_coded[0]. Repair the request/schema/normalization mismatch without disabling validation or silently discarding clinically meaningful content.
>
> Preserve raw output and validate the normalized result. Prove that a fresh real Fable response is accepted and actually contributes to the assessment—not merely that a request succeeded.
>
> [ ] 3. Verify genuinely independent proposal admission.
> Test these cases:
> - Only Astra proposes a supported service.
> - Only Fable proposes a supported service.
> - Corti disagrees, but the document supports the independent proposal.
> - Models agree on an unsupported, denied or historical service.
> - A number appears only in an alternative list.
>
> Supported explicit proposals must reach review regardless of provider. Unsupported suggestions must remain held or excluded with an accurate reason. Mere alternatives must not be promoted.
>
> [ ] 4. Repair the remaining interpretation defects.
> Address tattoo versus resection negation, completed marking versus future localization, historical references inside current reports, and the demonstrated Word routing errors.
>
> Protect “not snared,” “never removed,” prior procedures, other-provider procedures and genuine contradictions. Bind every action to its own procedure, lesion and time. Fix shared logic rather than hardcoding a document or code list.
>
> Do not restore the rejected automatic decompression-bundling experiment.
>
> [ ] 5. Repair recoverable Stop/Resume.
> Keep duplicate prevention. Reconcile the original request’s outcome before deciding whether a new attempt is permitted. Do not blindly resend an unknown request, reset consumed identities or permanently lose a participant merely because processing was stopped.
>
> Preserve attempt lineage and prove recovery without duplicate submissions.
>
> [ ] 6. Prove the complete harness.
> For a fresh case, obtain usable real Corti, Astra and Fable first assessments, frozen before peer access, with peer reviews stored separately.
>
> A refused, malformed, interrupted or skipped response means PARTIAL participation. Do not tick “full harness” because credentials exist, calls were recorded or two participants completed.
>
> [ ] 7. Verify review, reconciliation and downloads.
> Recompute code relationships after clarification and review decisions, after reload and before export. Preserve valid bundling, distinct-lesion relationships and unresolved modifier/reference limitations.
>
> Verify saved decisions and an actual downloaded report. Keep provider identities and technical traces confined to protected operator diagnostics. Doctors should see simple code rows, evidence, meaningful questions and truthful progress.
>
> [ ] 8. Test and install.
> Run required Linux tests/CI and an independent refutation of the finished diff. Repair demonstrated regressions without weakening safeguards.
>
> Install through the normal declared deployment and rollback process. Reassess retained cases without provider sends first, then run a small fresh Word/PDF acceptance set using the existing standing synthetic-testing authority. Preserve all previous records, failures and approvals.
>
> [ ] 9. Report release readiness honestly.
> Return:
> - The corrected checklist and evidence paths.
> - Exact installed revision.
> - Why my specific code was excluded and its verified final outcome.
> - Proof that Astra and Fable both contributed usable live results.
> - Fresh acceptance and actual-download results.
> - Remaining clinical, security, reference and licensing limitations.
>
> Resolve or explicitly account for the reported PDF-security advisories before claiming readiness for wider uploads.
>
> Continue through repair, installation and verification using existing authorized access. No repeated funding questions for already-authorized private testing, no new subscriptions or agreements, and no real-patient processing.
>
> I want a working GI product, but do not claim clinical accuracy, billing readiness or complete three-engine operation while known failures remain.

### Session interpretation, 2026-11-05 (a12d8fb3, on receipt of the second message) — recorded, not owner-ruled

(a) **This message supersedes the morning's interpretation (c) where they differ.** Two rules of (c) are withdrawn,
because together they made Corti's selection a veto over the participants' proposals:
- the gap-filling admission rule: a participant's code entered only where it accounted for an item Corti's decidable
  proposals left unresolved;
- its "neither is added" rule for two participant codes on one item.

Interpretations (b) and (d) stand:
- (b): only an explicit first-reading proposal can enter. A peer review's additional codes, a `not_coded` entry, a
  candidate and an alternative never do.
- (d): no model approves a code.

(b) **The provider-neutral path.** Each explicit proposal is validated on its own merits, by the same per-code
validation whoever proposed it. Validation never depends on another proposer selecting, omitting or listing the code.
It checks:
- scope and exact evidence in context;
- that the documented service was performed on the date, by this report's physician;
- that the act the code requires is documented as performed, with its anatomy, lesion and technique;
- the passages' support, the required facts, and the reference and relationship checks.

A code no decidable proposal carries, and that passes, becomes a proposal of origin `participant`. Sometimes codes of
different proposers, Corti included, account for one documented act as alternatives for it. Then each reaches review
and is held by one question naming the others. CPT Studio does not choose, and no code is preferred because of who
proposed it.

(c) **The path's own defects come first.** "Passes the same path as Corti" proves nothing while that path misreads
negation and time. So:
- the shared readers are repaired before the new admission is relied on;
- the acceptance cases of item 3 are written against each document's meaning, not against what the path did before.

(d) **What counts as source support is CPT Studio's reading of the document, never a participant's.** None of these add
anything (I3):
- a quote existing verbatim;
- a model's confidence or its stated modifiers;
- agreement between models.

A participant's code whose act CPT Studio's readers cannot establish is held or listed, with the reason it could not be
established. It is never made ready on the quote.

(e) **39f0ac49 is the reference case** (stage 1:
`docs/cpt-harness/repair3-20261105/stage1-trace-39f0ac49.md`). Its two assessments, six member answers and five runs are
kept. It is re-assessed from its retained responses, with sends disabled, after the install.

(f) **Stop and Resume:**
- A Stop is honoured at a boundary the harness controls.
- An exchange already sent is reconciled before any new attempt: from its recorded outcome, or from the provider's own
  record of it where the provider offers one.
- A new attempt carries a new identity, linked to the attempt it follows.
- An unknown outcome that cannot be reconciled stays blocked and reported. It is never resent blindly.

(g) **Fable's contract:**
- The rejected readings are kept exactly as received.
- The repair is to the request and the normalization, and the normalized reading is still validated strictly.
- A field a participant adds beyond the contract is kept in the protected record. It is never silently dropped and never
  read as clinical content.

(h) **Items 3, 5 and 10 of the morning's checklist section stay partial** until their missing requirements pass. Item
5's earlier tick is corrected to partial: Fable's walk readings were refused 3 of 3, and h2b lost Astra's peer review to
the Stop, so the complete harness was never proven.

(i) **The refutation pass keeps the two-cycle rule:**
- a releasing rule refuted twice is dropped, and its inputs are pinned as recorded residuals;
- findings are reproduced before repair;
- failures are preserved.

(j) **pypdf 6.21.2's advisories (interpretation 68)** are resolved, or explicitly accounted for, before any claim of
readiness for wider uploads.

(k) **Funding.** The standing authority for private synthetic testing applies and no ceiling is reintroduced. Usage is
recorded per run, with finite deadlines, duplicate prevention and Stop.

## Owner directive, 2026-11-06 — complete the remaining core repair: the verified installed workflow

Received by session a12d8fb3 at about 06:40Z, after the record of `fd8040d71e44` (#1479, merged as `eb7c9a77`), verbatim:

> Continue the existing CPT Studio GI project through completion of the remaining core repair. Use the current installed release as the verified starting point; the latest reported release is fd8040d71e44. Coordinate with the existing deployment owner.
>
> My required outcome is a working website where an uploaded GI PDF or Word document is assessed by Corti, Astra and Fable, supported proposals reach review, decisions persist, and the downloaded report matches those decisions. Repair the shared application logic, not individual documents or expected-code lists.
>
> Keep cpt.quillmd.com accessible during development and installation. Preserve the working harness, customer interface, provider privacy, existing documents, raw responses, failures, decisions and rollback evidence.
>
> **Put this completion contract into the harness before implementation.**
>
> Update HARNESS.md, CPT-HARNESS-CHECKLIST.md and the existing execution/checkpoint mechanism. Use one coordinated owner and the existing state format.
>
> Record:
> - Objective and acceptance criteria.
> - Installed and candidate revisions.
> - Current stage and next action.
> - Every unresolved defect and its evidence.
> - Test results, provider runs, usage and deployment receipts.
>
> Use NOT RUN, IN PROGRESS, PASS, FAIL and BLOCKED accurately. Tick an item only when its acceptance evidence passes. Reopen a passed item if later evidence disproves it. Distinguish implementation, offline verification and live verification.
>
> Advance automatically when a stage passes. Progress reports are checkpoints, not requests for permission to continue already-authorized work.
>
> **Continue until the engineering outcome is achieved.**
>
> For each failure: preserve it, diagnose its actual cause, repair it, run affected regressions and independent adversarial review, install when needed, and verify the affected website workflow.
>
> Do not end the task merely because a PR merged, installation succeeded, a large test suite passed, or an unsafe attempted fix was withdrawn.
>
> If a two-cycle rule requires abandoning an unsafe patch, abandon that patch and change the approach. Do not abandon the underlying requirement or repeatedly ship the known failure as completion. Do not repeat identical failing paid attempts.
>
> Use parallel agents for independent diagnosis, bounded implementation areas and adversarial review where useful. Keep integration and deployment serialized under one owner.
>
> Complete the following checklist:
>
> - [ ] **1. Establish the exact remaining failures.**
>   Reproduce 39f0ac49, the fresh PDF and the Word routing failure using retained source documents and provider responses. Trace source text → section boundaries → service/act interpretation → proposal admission → questions/status → review/export. Recover the counterexamples that defeated F-ACTS, F-SECTIONS and other relevant withdrawn fixes. Preserve them as regression cases.
>
> - [ ] **2. Repair the shared document interpretation.**
>   Resolve contextual references such as “the bolus” against their documented antecedents. Recognize completed procedure narratives after inline labels without incorrectly extending Indications over them. Bind evidence to the correct procedure, action, anatomy, lesion, extent, date, performer and outcome.
>
>   A failed therapeutic attempt must not automatically make the entire examination incomplete. Historical, planned, deferred, unsuccessful, negated and other-provider acts must remain distinct from completed current services. A completed marking performed for future localization must not become a future procedure solely because its purpose is future-facing.
>
>   Make routing, service interpretation and admission consistent about these facts. Do not apply patient-, filename-, document-ID- or CPT-specific exceptions.
>
> - [ ] **3. Preserve equal proposal eligibility.**
>   Astra and Fable are primary code-finding participants alongside Corti. An explicit supported proposal must receive the same evaluation regardless of which participant supplied it. Corti’s omission, selected-code list or interpretation must not veto another participant’s proposal.
>
>   Preserve actual provenance internally. Keep explicit proposals distinct from alternatives or incidental code mentions. Model agreement alone must never establish performance, resolve bundling or approve a code. Conflicting proposals must receive evidence-based reconciliation.
>
> - [ ] **4. Fix false positives as well as false holds.**
>   Test the previously rejected patches’ counterexamples and retained false READY cases, including a polyp explicitly left in place. Test minimal positive/negative pairs and equivalent wording across different layouts and GI procedure families.
>
>   Do not improve recall by treating every procedure mention as performed, ignoring negation, bypassing evidence checks or weakening rejection criteria.
>
> - [ ] **5. Make questions and statuses truthful.**
>   “Not performed” requires supporting documentation; a parser’s failure to recognize an act is not proof that it was not performed.
>
>   Resolve facts already present in the source before asking the doctor. For genuine ambiguity, show the specific missing fact and the relevant passage with a concise answer control. Do not manufacture an answer, force an addendum to repeat existing documentation, or introduce a blanket approval override.
>
>   Verify that resolving a question recomputes the affected assessment correctly. Preserve earlier answers and approvals without silently reusing them for a changed assessment.
>
> - [ ] **6. Prove the repair against retained evidence first.**
>   Reassess retained cases without new provider calls where possible. Verify the previously omitted proposal’s actual eligibility and remaining reference requirements. Preserve 88d9db32’s supported results.
>
>   Independently check the corrected routing, completed-act recognition, exclusions, necessary questions and provider-neutral admission. Original failures remain preserved beside the new results.
>
> - [ ] **7. Complete meaningful independent acceptance.**
>   Before new paid testing, pass the focused suite, relevant regressions and independent adversarial review of the final diff.
>
>   Prepare a small fresh synthetic PDF/Word set with expectations recorded before viewing model output. Include the repaired language/layout patterns and negative controls. Support expectations with applicable references; do not treat an author’s provisional list as unquestionable clinical truth.
>
>   Run the ordinary website workflow. Confirm actual accepted and usable responses from Corti, Astra and Fable, frozen independent first readings, separately stored peer reviews and final reconciliation. Configuration checks, rejected responses and replay alone do not count.
>
>   Verify Stop/Resume, duplicate prevention, visible progress, necessary clarification, explicitly labelled synthetic review decisions, reload persistence and actual downloads. Check both omitted supported services and unsupported additions—not only whether exported rows match the database.
>
> - [ ] **8. Install and verify the served result.**
>   Use the established deployment process, preserve rollback and coordinate the switch. Keep the website available.
>
>   Verify the actual served revision, worker behavior, retained records, customer-provider privacy and the repaired end-to-end workflow after installation. If a fresh acceptance failure exposes an authorized engineering defect, return to its cause and complete the repair loop.
>
>   Account for the already-recorded PDF security and reference limitations before claiming broader release readiness. Do not hide them by narrowing the final report.
>
> - [ ] **9. Close with evidence of the result.**
>   Provide the installed revision and website links, each original defect’s before/after outcome, fresh PDF/Word results, proof of all three participants’ usable contributions, persisted decisions and downloaded reports. Include measured usage, estimates and any unresolved charges accurately.
>
>   Mark functional completion only when these acceptance criteria pass. Report clinical-validation and content-use permission status separately. A successful synthetic workflow does not establish guaranteed accuracy or unrestricted billing/public-launch readiness.
>
> Use my existing standing authorization for necessary private synthetic testing, engineering repairs, project-scoped installation and verification with existing accounts. Do not reopen superseded funding limits or request permission for each eligible step.
>
> Keep purposeful batches, concurrency one for provider execution, finite deadlines, Stop, duplicate prevention and reconciliation of unknown outcomes before resubmission. Do not purchase subscriptions or credits, accept new agreements, process real patients or submit claims.
>
> Only stop for a genuine dependency that available access and existing authorization cannot resolve. Complete independent work first, preserve an actionable checkpoint, and identify the smallest necessary external action. If the session ends, resume from that checkpoint when continued; do not claim background work is running unless it actually is.
>
> The completion target is the verified installed workflow—not another partial report with the same core defects left unresolved.

### Session interpretation, 2026-11-06 (a12d8fb3, on receipt) — recorded, not owner-ruled

(a) **The completion target replaces "drop and record" as an outcome.** The second message's interpretation (i)
pinned a twice-refuted rule's inputs as residuals and stopped. This message keeps the two-cycle rule for a PATCH and
withdraws it as an END:
- a releasing patch refuted twice is abandoned;
- its requirement stays open, and the approach changes: a different mechanism, measured on every earlier refuter input
  and retained case before it is relied on;
- the item stays IN PROGRESS or FAIL until its own acceptance evidence passes;
- a release that still carries a known core defect is never reported as completion.

(b) **The core defects are the ones the fd8040d71e44 record names.** The checkpoint's unresolved list in
CPT-HARNESS-CHECKLIST.md ("Completion repair, 2026-11-06") carries each one with its evidence. Among them:
- the participants' 43247 for "the bolus was removed", listed as not done (d44a77b3, 39f0ac49);
- procedure narratives after inline labels read as part of the Indications (d44a77b3, 39f0ac49);
- a failed polypectomy attempt making the whole colonoscopy incomplete (e888f9ce);
- completed marking read as future localization;
- the base's own false READYs, among them "The polyp was left in place.";
- questions whose only offered answers exclude the code (39f0ac49).

(c) **Structural repair, not word lists.** Reader changes are rules over the document's structure:
- sections and inline labels;
- sentence and clause boundaries;
- an act's own verb, object, polarity, time and performer;
- a definite noun phrase's documented antecedent.

No rule names a patient, filename, document id or CPT code as an exception. Each rule is measured against the corpus
of every earlier refuter input and retained case before it is relied on. The measured record is that word-list repairs
did not converge (12 of 12 refuted) and a structural rule did.

(d) **One reading of each fact.** Routing (gi-routing), the documented-service reader (gi-services) and the admission
must agree about a section boundary or an act's status. Each such fact is computed once and read by all three. A
remaining disagreement is a recorded defect, never two answers.

(e) **"Not performed" needs documentation (item 5).** A reader that finds no act has not found that the act was not
done. So a status or a listing reason says "not done", "historical", "planned", "deferred", "unsuccessful", "negated"
or "by another provider" only with the passage that says so. Otherwise it says CPT Studio could not confirm the act.

An explicit, exactly quoted first-reading proposal that CPT Studio can neither confirm nor exclude from the document is
a genuine ambiguity. It reaches review held by a question that:
- shows the passage;
- names the one missing fact;
- offers an answer that can confirm as well as exclude.

It is never READY on the quote (the second message's (d) stands). It is never listed as not done merely because a
parser rule was missing.

(f) **Equal eligibility (item 3).** The second message's (b) and (d) stand:
- one per-code validation, whoever proposed the code;
- CPT Studio's reading is the only source support, and a quote, a confidence or agreement adds nothing;
- an alternative, a `not_coded` entry, a peer's additional code or an incidental mention never enters;
- codes of different proposers for one act each reach review, held by one question that shows the passages;
- no proposer is preferred and no model approves.

(g) **False READYs are first-class (item 4).** Every candidate rule runs over:
- the previous refuters' inputs (repair 2 rounds 1 to 7, repair 3 rounds and cycles r1 to c4);
- the base's false READYs;
- minimal positive and negative pairs;
- equivalent wording across layouts (paragraph, labelled line, table cell, Word title) and GI families.

A rule that opens a READY on any negative is not shipped.

(h) **Questions (item 5).**
- A fact the source already states is resolved before the doctor is asked.
- An answer recomputes the assessment.
- Earlier answers and approvals are kept. They are bound to the assessment and fact they answered, and never silently
  reused for a changed assessment.

(i) **Evidence order (items 6 to 8).**
1. The retained cases offline first: 88d9db32 keeps its six READY codes; then 39f0ac49, d44a77b3, e888f9ce and the
   earlier walk documents.
2. The full suite and CI.
3. The refutation pass over the final diff.
4. A fresh sealed set, its expectations written before any output is read, each with its reference.
5. The install.
6. The ordinary-use walk, including a clarification answered and recomputed, Stop and Resume, the downloads, and both
   omitted supported services and unsupported additions.

(j) **Paid attempts.**
- Provider execution runs at concurrency one, with finite deadlines, Stop and duplicate prevention.
- An unknown outcome is reconciled before any resubmission.
- No identical failing paid attempt is repeated: a walk runs again only after a repair changes the path it failed on.

(k) **One owner.** Session a12d8fb3 stays the integration and deployment owner, as for repairs 2 and 3.
- Agents diagnose read-only, implement bounded areas in isolated worktrees, and refute in sealed sandboxes. No agent
  is given write access to a file the owner is editing.
- Integration, merges, installs and walks are serialized under the owner.

(l) **Limitations reported, not hidden.** These stay in every report, beside clinical validation and content-use
permissions, which are reported separately:
- pypdf 6.21.2's advisories, resolved or explicitly accounted for before any claim of broader release readiness;
- NCCI PTP unconnected;
- D3 to D5 open.

(m) **Funding.** The standing authority for private synthetic testing applies and no ceiling is reintroduced. No
subscription, credit, agreement, real patient or claim.

## Owner decision, 2026-11-07 — the date reader may read more unambiguous forms of a stated date of service

Asked by session 30a58364 (the integration owner since a12d8fb3 ended on 2026-11-07 ~11:59Z), with the evidence: on a
held-out corpus of 24 fresh synthetic reports by six blind authors, 10 documents had a date of service the reader does not
read, and they held 17 of the corpus's 25 held codes. The question, verbatim:

> May CPT Studio's date reader read more ways of writing the date of service? Today a document that writes "16-Nov-2026",
> "9 November 2026", or the label "Date of Operation:" is treated as undated: every code is held and the doctor is asked
> for the date. On 24 fresh test reports, 10 were affected, and they hold 17 of the 25 held codes. Reading these dates
> means the providers' request would carry that stated date (today they get no date), which is why it needs your approval.

The owner's answer, verbatim: **"Yes, unambiguous forms (Recommended)"** - the option worded: *"Read '16-Nov-2026',
'9 November 2026', a weekday before the date, and the labels 'Date of Operation:' and 'Exam date:'. Two-digit years
('11/02/26') and '11-09-2026' stay unread and keep asking the doctor."* (The other options offered and not chosen: "Yes,
plus two-digit years"; "No, keep it as is".)

### Session interpretation, 2026-11-07 (30a58364, on receipt) — recorded, not owner-ruled

(a) **What changes.** The context reader reads, inside the date-of-service labels it already reads and the two new labels
"Date of Operation:" and "Exam date:" (any case), these additional value forms: a day, a month name (full or abbreviated)
and a four-digit year written day first ("16-Nov-2026", "9-Nov-2026", "16 Nov 2026", "9 November 2026"); and any form the
reader already reads, or one of these, after a weekday name ("Monday, November 9, 2026", "Mon 16-Nov-2026"). Nothing else:
a two-digit year, an all-numeric date with hyphens ("11-09-2026"), and every other form stay unread.

(b) **The request side moves, and only as decided.** The H2 freeze's date channel was "NEW-SEND = NEW-TAKE = 0, always".
This decision permits NEW-SEND exactly where a document's newly read date of service comes from one of the forms in (a)
under a date-of-service label; the gate is changed to accept such a movement only when a declaration names this decision
and every NEW-SEND text's new date fact quotes one of those forms - checked mechanically, never by count alone. NEW-TAKE
(a member answer the base did not take), NEW-HELD and SEND->ASK stay 0.

(c) **Everything else the date reader decides is unchanged**: which of two dates is the encounter's, a conflict between a
label and a field, another occurrence's date (ruling 2026-10-28), and the member-answer rules. A newly read date that
conflicts with another read date is a conflict, as today.

(d) **The same proof burden.** A design, two refutation cycles under the two-cycle rule, the full suite, CI, a declared
install and a walk.

### Session interpretation, 2026-11-07 (30a58364, after the first refutation of the date design) — appended, not rewritten

(b'), refining (b): the first design read the owner's labels everywhere and its lenses showed why that cannot stand - a
prior surgery's "Date of operation" in an indication, an imaging study's "Exam date", a recall "Exam date" in 2029, each
sent as the date of service. The repair reads "Exam date" and "Date of Operation" only in the document's head, where the
installed reader already reads its wide labels, and sends them there (never under a consent, booking or instructions
title); a blank or unreadable value reads as before. (b) said NEW-TAKE and NEW-HELD stay 0; that cannot hold while the
document now states a date: a member answer that CONTRADICTS the newly read document date is held, and one that EQUALS it
is taken - exactly as for every date the installed reader already reads. The gate accepts NEW-HELD and NEW-TAKE only in
those two shapes, text by text; SEND->ASK stays refused. The day-first and weekday forms under the installed labels read
exactly as the installed month-day-year twin, its 2026-10-28 known limits included (recorded as parity).

## Owner requirement, 2026-11-09 — the shared evidence model (GI Note #8), added to the completion contract

Received by session 30a58364 (the integration and deployment owner) on 2026-11-09 at about 00:00Z, as pasted. Recorded
verbatim below; it adds to the 2026-11-06 directive and replaces none of its unfinished requirements.

> Add this requirement to the current CPT Studio repair harness and continue the existing work. Do not restart the project or create a competing deployment task.
>
> MOST IMPORTANT: Fix the shared documentation-validation logic, not just the five CPT codes or GI Note #8. The repair must address the underlying association of evidence with procedures, targets, techniques and encounters so the same defect does not recur elsewhere.
>
> Integrate this into HARNESS.md, CPT-HARNESS-CHECKLIST.md and the current checkpoint. Cross-reference U12 and U30 and any related existing defects. Preserve completed work and reopen only items invalidated by new evidence.
>
> The new report concerns Advanced GI / IBD Colonoscopy Procedure Note #8. It reports five detected candidates—45385, 45390, 45386, 45380 and 45381—but six clarification questions and no codes ready for review. Treat this as evidence to reproduce, not proof that all five codes must be approved or separately billable.
>
> Complete these additional acceptance items:
>
> - [ ] Reproduce and trace the actual failure.
>   Locate the original retained document, extracted text, provider responses and current assessment. Trace all five candidates and all six questions. Identify the earliest stage where evidence becomes associated with the wrong target, technique, time or procedure. Compare the installed release with the active repair branch to avoid duplicating work already completed.
>
> - [ ] Repair the shared evidence model.
>   Before evaluating contradictions, associate each assertion with its procedure, anatomical target or lesion, intervention, technique, encounter/time, performer, outcome and exact source spans. Use the existing architecture where possible; the report’s suggested JSON is conceptual, not a requirement for a new database schema.
>
>   Different lesions can share the same anatomical segment. One lesion can also have several descriptions. Resolve references such as “this polyp,” “this lesion” and “the stricture” from their context rather than location or nearest-word matching alone. Preserve uncertain identity instead of guessing.
>
> - [ ] Evaluate genuine contradictions correctly.
>   Similar vocabulary must not establish a conflict. Compare assertions about compatible events and determine whether their meanings are actually incompatible.
>
>   Test both different-target and same-target cases. “No EMR electrosurgical snare was used” may coexist with cold-snare removal on the SAME polyp; do not assume it describes another lesion. Conversely, a broad denial of resection may contradict a specific completed resection on the same target.
>
>   Preserve sequence: an unsuccessful initial attempt followed by documented successful completion is not automatically contradictory. Genuine unresolved contradictions must still trigger review.
>
> - [ ] Repair temporal, injection and extent interpretation.
>   Historical non-performance in 2024 must not invalidate a separately documented current intervention. Inherit a supported service date within the correct procedure context; do not substitute upload, signature or document-creation dates.
>
>   Distinguish completed tattoo placement for future localization from planned tattooing. Keep tattoo material, target and purpose separate from an EMR saline lift. Documentation of two actions does not itself establish separate billability.
>
>   For altered surgical anatomy, extract the documented anatomy, anastomosis, landmarks, furthest point reached and traversal before/after dilation. Do not invent a cecum or automatically equate neo-terminal ileum intubation with every standard completion criterion.
>
> - [ ] Keep documentation and billing decisions separate.
>   Clearly distinguish performed, not performed, historical, planned/deferred and uncertain documentation from bundling, modifier, payer and reference restrictions.
>
>   Apply the same evidence standards to explicit Corti, Astra and Fable proposals. Preserve independent readings and provenance. Agreement alone must not approve a code.
>
>   Before asking a question, check whether the complete report already resolves it. A recognition failure must not be presented as proof that a procedure was not performed.
>
> - [ ] Prove generalization.
>   Add focused unit and integration tests for different lesions at the same site, different techniques on the same lesion, historical versus current events, failed-then-completed attempts, completed tattoos with future purposes, altered anatomy and genuine same-event contradictions.
>
>   Vary wording, paragraph order and PDF/Word layouts. Include negative controls for deferred procedures, untreated lesions and included procedural components. Trace other consumers of the shared validator and test reusable behavior without claiming untested specialties are clinically validated.
>
> - [ ] Verify every question and persisted outcome.
>   Produce a before/after table for each of the six questions: original reason, implicated evidence, confirmed cause, corrected result and any legitimate remaining uncertainty.
>
>   Remove a question only when existing documentation resolves it. Do not target “zero questions” or “five READY” regardless of evidence. Preserve original responses, assessments, answers and decisions.
>
>   Reassess retained data first, then complete a small fresh synthetic acceptance check. Verify review decisions, clarification recomputation, reload and actual downloads.
>
> - [ ] Install and close with evidence.
>   Continue through the authorized repair, relevant regression tests, independent adversarial review, installation and served verification while keeping the website accessible.
>
>   Tick these items only when their acceptance evidence passes. If a proposed fix fails, preserve the counterexample and change approach; do not drop the shared-core requirement and call the job complete.
>
>   Report the installed revision, confirmed root cause, shared functions repaired, generalization tests, six-question comparison, actual website/export results and precise remaining limitations.
>
> Continue under the existing standing synthetic-testing authority and technical safeguards. This is an addition to the current completion contract, not a replacement for its unfinished requirements.

### Session interpretation, 2026-11-09 (30a58364, on receipt) — recorded, not owner-ruled

(a) **The case, located and reproduced.** "GI_Advanced_IBD_Colonoscopy_Procedure_Note_08" is encounter
9dbe9fc4-0cef-48a5-85a7-34d873f92963, uploaded by the owner account on 2026-11-08 at 23:48Z as a PDF (19,398 extracted
characters, text sha256 prefix 25ef61e4bf743b70) and assessed by the installed release c2e53f8e (gi-routing@12,
cpt-studio-validation@10). Corti, Astra and Fable all answered. After the peer reviews all five candidates (45385, 45381,
45390, 45386, 45380) were held with ten stored questions, which the page shows as six: four "performed and not performed"
conflicts (snare 45385, endoscopic mucosal resection 45390, dilation 45386, biopsy 45380), 45381's performed status, and
one extent question (five per-code rows). The owner then answered "cannot confirm" to all ten and revoked three, so every
code reads excluded and the encounter reads reviewed. Re-assessed offline from its retained responses on a restored copy
(the R-judge path, nothing sent), the installed code reproduces both states exactly: with the owner's answers, five
excluded; without them, the same ten questions. Every original response, assessment, answer and revocation stays as it is.

(b) **What the requirement repairs.** The shared association of evidence: an assertion (an act done, an act denied, a plan,
a history) is tied to its procedure, its target or lesion, its technique, its time and its outcome before any two
assertions are compared. Note #8 is the evidence, not the target: no code is to be made READY, and no question removed,
except where the document resolves it. Its expected documentation reading is fixed by a careful reading recorded with
the trace, never by the five codes the report lists.

(c) **Cross-references.** U12 (one fact, three readers - the parent defect), U13 (a failed attempt's device; a lesion's
disposition), U30 (a cited passage that hedges holds the code; a denied lift injection read against a tattoo), U19 and
U14 (extent), U21 (the date forms), U10 and U11 (answers). Each keeps its own row; the new class is recorded as U32.

(d) **Documentation and billing stay apart.** Whether an act is documented as performed, not performed, historical,
planned or uncertain is the readers' decision. Bundling (45381 beside 45390, 45385 beside 45390 on another lesion),
modifiers, payer and reference rules stay considerations (limitation L2, NCCI PTP unconnected) and never hold or release
a documented act.

(e) **The same proof burden.** A design, two refutation cycles under the two-cycle rule, the full suite, CI, a declared
install, the retained re-assessment first, then a fresh synthetic acceptance check written blind to the repair. The date
item touches the request side (studio/gi/context.py, the H2 freeze); what it moves is decided after its trace, and any
request-side movement beyond the 2026-11-07 decision is put to the owner before it ships.

## Owner amendment, 2026-11-09 — parity is diagnostic; regressions are regressions; the paired denial-timing cases

Received by session 30a58364 at about 05:25Z, as pasted, after the session recorded its parity decision (HARNESS.md "The design,
stage A"). Recorded verbatim below; it amends the acceptance rule of the 2026-11-09 requirement and supersedes that decision.

> Continue the repair chain. Do not stop the project or pause the live website. Keep progressing through time, targets, matching and anatomy, but amend the harness’s acceptance rule as follows.
>
> **Ordinary-heading parity is diagnostic evidence, not proof of correctness.**
>
> For every recorded counterexample, record separately:
> 1. The installed release’s result on the exact original input.
> 2. The candidate’s result on that same input.
> 3. The ordinary-heading comparison, if useful.
> 4. The expected semantic outcome supported by the complete document.
>
> If the candidate incorrectly changes the original input from HELD to READY, record a regression. Do not dismiss it because the installed release also fails on a rewritten input. If both versions fail the same input, record an existing defect—not a passing correctness check.
>
> Do not describe “bounded by the ordinary-heading comparison” as “no false positives.”
>
> **Keep the completion requirement practical and specific.**
>
> I am not asking for proof that no imaginable document can ever fail. I am requiring resolution of the demonstrated material false READY and false-hold cases within this repair’s scope. Keep unrelated existing limitations separately recorded.
>
> Statements assigning a procedure to an earlier time or another performer must be interpreted in their full context. Do not automatically treat them as current, dismiss them as contrived, or turn uncertainty into evidence of performance.
>
> **Test the alternative denial-timing approach before accepting it.**
>
> Section context may contribute to time interpretation, but must not erase explicit dates, local temporal overrides or cross-sentence references.
>
> Required paired cases include:
> - A historical denial followed by a clearly documented current intervention.
> - A historical denial explicitly extended to the current encounter.
> - Historical and current services mixed within one section.
> - A previous performer and the current performer described in the same narrative.
> - A failed attempt followed by successful completion of the same intervention.
> - An unrelated target’s denial beside a completed current intervention.
>
> If time, ownership or reference resolution remains uncertain, preserve a targeted unresolved state. Do not invent current performance or apply a whole-document hold unnecessarily.
>
> **Keep repairing the shared logic.**
>
> Retiring an unsafe implementation after two attempts does not retire the requirement. Preserve its counterexamples and change the approach. Keep unsafe variants out of deployment while independent work continues.
>
> Before marking the integrated repair PASS:
> - Resolve the original Note #8 false holds and the retained material false READY counterexamples.
> - Verify correct target, technique, time, performer and extent—not just the code’s READY label.
> - Run independent review of the integrated result.
> - Install through the existing coordinated process and verify the served workflow, saved decisions and actual downloads.
>
> Continue under the existing completion contract. Do not close this work with a parity-only justification for unresolved failures in the changed behavior.

### Session interpretation, 2026-11-09 (30a58364, on receipt) — recorded, not owner-ruled

(a) **The session's parity decision is withdrawn.** "Parity-bounded" was used to set aside findings in which the candidate turned the
exact original input from held to READY while the installed release held it (c5c with "She had this done at the age of 50.", "Both done
by her previous gastroenterologist.", "She had both in her fifties."). Under this amendment each of those is a REGRESSION of the
candidate, to be resolved; the installed release's READY on the ordinary-heading rewrite is an EXISTING DEFECT, recorded beside it.

(b) **The counterexample registry.** Every recorded counterexample (wave 1's lens findings, the stage-A judges' batteries, the trace's
cases and every later lens finding) is kept with four separate results: the installed release on the exact input; the candidate on the
same input; the ordinary-heading comparison where it helps diagnosis; and the expected outcome the complete document supports. A
candidate's held-to-READY change against that outcome is a regression; a failure both share is an existing defect.

(c) **Scope and materiality.** Within scope: the association of a statement with its procedure, target, technique, time, performer,
outcome and extent, and the contradictions judged on it. "Material": a plausible report could contain it, and it changes a code's
documentation reading. Within-scope material false READYs and false holds are resolved before PASS; out-of-scope limitations stay
recorded separately (ACCURACY-RESIDUALS.md).

(d) **Time and performer by interpretation.** A statement that assigns a procedure to another time or another performer is read in its
full context - its referents ("this", "both", "all of this"), the patient's stated age, the document's own endoscopist, explicit dates,
local overrides ("today", "this time") and cross-sentence references - and is never assumed current, dismissed as contrived, or turned
into performance. Where the resolution stays uncertain, the affected codes keep a targeted unresolved state (a question about those
codes), never a whole-document hold where the rest is resolved.

(e) **The denial-timing approach is tested before it is accepted**, on the six paired cases the amendment names, built as unit and
integration tests with wording, order and PDF/Word variation. Section context contributes; it never erases an explicit date, a local
temporal override or a cross-sentence reference.

(f) **Unsafe variants stay out of deployment.** The installed release (c2e53f8e) stays live and unchanged until an integrated repair
passes; no candidate is installed that turns a correctly held original input READY.


## Owner request, 2026-11-09 — the first Gemini interpretation trial (recorded late, from the session transcript)

Received by session 30a58364 at 2026-11-09T05:45:13Z. **Recorded late:** the trial's records (HARNESS.md "The Gemini interpretation
trial", the trial REPORT) acted on this request, but the request itself lived only in the session transcript, which is the gap the
ruling rule in AGENTS.md exists to close. Extracted verbatim from the transcript on 2026-11-09 at ~07:20Z. The credential line is as
the owner pasted it: a file path and a variable name, no secret.

> Run the first Gemini interpretation trial now, within the existing CPT Studio harness.
>
> Credential:
> `/etc/cpt-studio-provider-sources/gemini.env`
> Variable: `GEMINI_API_KEY`
> Requested model: `gemini-4-argon`
>
> Read the credential securely without printing it. Verify access and record the returned model/version. Do not silently substitute another model. Use an isolated test process; keep the live website, current provider routing and saved approvals unchanged.
>
> Complete this bounded experiment:
>
> - [ ] Verify authentication and model access. Distinguish access errors, malformed responses and interpretation failures.
> - [ ] Locate the complete retained synthetic GI Note #8, encounter `9dbe9fc4-0cef-48a5-85a7-34d873f92963`. Preserve its source and revision hashes. If testing extracted text rather than the original PDF, explicitly label PDF/OCR understanding as untested.
> - [ ] Establish expected event facts independently before calling Gemini. Do not send Gemini the expected codes, previous model answers, bug report conclusions or desired result.
> - [ ] Ask Gemini to interpret the complete source into a compact structured event list: procedure, target/lesion, anatomy, technique, performer, time, performed/planned/denied/uncertain status, sequence, extent and exact supporting or contradicting passages. Unknown facts must remain unknown.
> - [ ] Test a small fixed set covering different lesions at the same site; different techniques on the same lesion; historical denial versus current performance; “This time as well”; different performers; and altered anatomy, including guidewire passage versus scope passage.
> - [ ] Freeze Gemini’s initial outputs before comparing them with retained Astra/Fable findings. Do not rerun those providers unnecessarily.
> - [ ] Independently evaluate meaning—not merely valid JSON or matching quotations. Check missed supported acts, unsupported completed acts, incorrect target/time/performer links, omitted contradictory evidence and unnecessary questions.
>
> Use concurrency one, finite deadlines, Stop and duplicate prevention. Preserve raw results and failures securely. Reconcile unknown execution outcomes before any resend.
>
> Report the actual results:
> 1. Did Gemini answer successfully using the requested model?
> 2. Which Note #8 interpretation errors did it resolve?
> 3. Did it introduce any incorrect completed procedures or miss genuine contradictions?
> 4. How did it compare with the current reader and retained participant findings?
> 5. What were latency and provider-reported usage?
> 6. Is it suitable for a controlled integration trial, or what specific failure needs repair?
>
> Do not claim Gemini is integrated or the website is repaired merely because this experiment passes. If suitable, the next integration must use its evidence-linked event interpretation without sending it through the same faulty keyword interpretation as an unconditional veto.
>
> Carry this trial through execution and an evidence-backed result report. Use the existing synthetic-testing authority; do not stop at a design proposal.

## Owner message, 2026-11-09 — billing enabled; continue the trial through evaluation (recorded late, from the session transcript)

Received 2026-11-09T06:15:03Z, and recorded late for the same reason. Outcome: HARNESS.md "The Gemini interpretation trial"
(freeze 0dfb1b2a, result d1137dbd).

> Google billing is now activated and I have added credit. Continue the existing Gemini interpretation trial through its evaluation and final report.
>
> Read the retained trial report and current HARNESS.md first:
> - /home/claude/cpt-studio-completion-20261106/gemini-trial/REPORT.md
> - cpt-studio/HARNESS.md
>
> Use the existing protected credential at /etc/cpt-studio-provider-sources/gemini.env. Never print its contents.
>
> **Purpose**
>
> Evaluate Gemini as an evidence-based interpreter of procedure events: what was performed, on which target, using which technique, by whom, and when—including negatives, historical statements and contradictions. Determine whether it can address the shared interpretation defects behind Note #8’s false holds. Model agreement alone must not approve codes or override conflicting documentation.
>
> **Continue this checklist, ticking items only when supported by saved evidence:**
>
> - [ ] Recover the original seven cases, sealed expectations, prompt, schema and input hashes. Keep them unchanged for this retry. Preserve all seven earlier HTTP 429 refusals.
> - [ ] Run the first case once with the existing key and requested model, gemini-4-argon. Record the returned model/version information where available. A model-information lookup alone does not establish generation access.
> - [ ] If the first generation succeeds, retain it as case one and complete the other six cases. Do not rerun case one unnecessarily.
> - [ ] If authentication, billing or quota fails, stop further generation immediately and inspect the exact error and project configuration. Do not substitute another model. Reconcile an unknown execution outcome before resubmitting.
> - [ ] Freeze and hash every response before evaluation. Keep expectations, previous model answers and desired conclusions out of Gemini’s input.
> - [ ] Independently evaluate all seven cases against the sealed expectations. Report corrected false holds, missed events, incorrect completed-procedure interpretations, missed contradictions and unresolved ambiguity.
> - [ ] Compare with the current reader and available retained Astra/Fable findings on matching inputs. Clearly identify missing or non-comparable evidence. Use retained results wherever possible.
> - [ ] Update HARNESS.md and the trial report with evidence links, actual usage, latency, estimated costs where calculable, and the remaining limitations.
>
> Use sequential requests, finite deadlines and bounded execution. Continue all already-authorized trial work without asking me to approve each request.
>
> Keep the live website available and its current provider routing, documents and saved approvals unchanged during this trial.
>
> Finish with a clear answer:
> 1. Did Gemini actually answer using the requested model?
> 2. Which interpretation errors did it fix or introduce?
> 3. Is there enough evidence for a controlled integration trial?
> 4. What shared architectural change would be required so a correct AI interpretation is not rejected again by the same defective reader?
>
> Distinguish successful API access, interpretation performance and readiness for integration. Seven synthetic cases cannot establish overall GI coding accuracy.

## Owner directive, 2026-11-09 — replace the legacy semantic interpretation engine with Gemini

Received by session 30a58364, the integration and deployment owner, at 2026-11-09T07:10Z. Recorded verbatim in this, the session's
first commit after receipt.

> Change of direction: replace CPT Studio's legacy semantic interpretation engine with Gemini. Stop extending the old keyword reader as the long-term solution.
>
> This authorizes implementation, necessary synthetic testing, installation on the existing authenticated synthetic site, and verification. A shadow-only implementation is not the requested final result.
>
> Keep the website available throughout the work. Preserve existing records, approvals, raw responses, failures and exports.
>
> ## Target architecture
>
> - Gemini, using the successfully tested gemini-4-argon model, becomes the primary interpreter of documented clinical events.
> - Corti, Astra and Fable remain code-proposal/review participants. Preserve their independent first assessments and source attribution.
> - Shared evidence checks, applicable coding/reference rules and reviewer approval remain.
> - The legacy semantic reader must no longer independently reinterpret Gemini's accepted events or veto them through keyword matching.
> - Gemini interpretation and model agreement do not constitute clinical approval.
>
> Read the current HARNESS.md, trial report and installed code before editing. Coordinate existing agents under one integration/deployment owner. Preserve unfinished work before stopping obsolete reader-repair branches.
>
> ## Evidence-backed completion checklist
>
> Create this migration checklist in HARNESS.md. Tick items only after their stated outcome is verified.
>
> - [ ] Record the installed baseline, rollback image, active work and all locations where semantic interpretation influences routing, matching, contradictions, completeness, clarification, review, saving and export.
>
> - [ ] Implement the production Gemini adapter using the existing protected credential. Include finite deadlines, Stop/resume, duplicate prevention, usage recording and reconciliation of unknown outcomes. Authentication/quota failures must stop requests. No silent model substitution or fallback to the old reader.
>
> - [ ] Introduce one versioned, persisted event inventory containing event identity, procedure, target/lesion, technique, time, performer, status, anatomy/extent and attribute-level source evidence. Bind it to the exact document revision and interpretation version. Preserve distinctions that the old Act structure or merge rules could erase.
>
> - [ ] Make all downstream consumers use that same inventory. Remove legacy semantic rereads from the new execution path—including those triggered by save, reload, review and export. Keeping archived legacy code for rollback is acceptable; retaining its hidden veto is not.
>
> - [ ] Preserve schema checks, source integrity, evidence binding, tenant isolation, applicable reference rules and approval controls. A quotation appearing in the document does not by itself establish that it supports an attribute.
>
> - [ ] Handle contradictions by their documented scope. Distinguish targets, techniques, times and performers, while also respecting broad statements such as "No polyp was removed today." Missing identifiers must not manufacture either a match or a non-match. Ask a focused question when necessary. An unresolved required attribute must still block the dependent code; unrelated supported codes can proceed.
>
> - [ ] Cover the original seven cases and the four reported Gemini slips, particularly unsupported historical extent and biopsy-site conflation. Include the scar example, historical/current acts, different lesions at one site, technique-specific denials, different performers, future purpose and guidewire-versus-scope extent. Preserve genuine contradictions.
>
> - [ ] Test independently authored PDF and Word inputs through actual ingestion, with repeated runs and source-grounded expectations. Label replay, text-only tests and fresh provider calls separately. Do not hardcode Note #8, its five codes, or expected answers.
>
> - [ ] Complete the actual website workflow with Gemini driving interpretation: upload, truthful progress, code review, explicitly labelled synthetic approval, save, reload and downloaded reports. Verify that saved decisions and downloaded content match. Keep provider/model names and traces out of customer screens and downloads.
>
> - [ ] Install the replacement through the established deployment process. Verify the served release and operator-side execution evidence showing Gemini is the active interpreter and legacy semantic vetoes are unused. Verify availability, preservation and rollback compatibility.
>
> ## Completion and reporting
>
> Continue through implementation, installation and meaningful verification. If a check fails, investigate and repair the new architecture without weakening acceptance criteria or returning to endless legacy-reader patches.
>
> Necessary testing remains authorized under the existing standing authority. Use purposeful bounded batches; preserve and report usage and costs.
>
> Report:
> 1. The installed revision and website link.
> 2. Exactly which legacy interpretation paths were replaced.
> 3. Which independent cases passed or failed.
> 4. Remaining false holds, false-ready results and unresolved questions.
> 5. Actual save/reload/download verification.
> 6. Usage, latency, costs and material limitations.
>
> Do not declare completion because the adapter works or the seven-case trial passed. Completion means the installed application actually uses the replacement successfully. Keep clinical accuracy claims separate from functional completion.
>
> If an unavoidable external dependency prevents completion, name the exact dependency and preserve a resumable checkpoint. Do not claim installation or success that has not occurred.

### Session interpretation, 2026-11-09 (30a58364, on receipt) — recorded, not owner-ruled

(a) **What "primary interpreter" covers.** Every new assessment of a GI document gets its event inventory from Gemini
(`gemini-4-argon`, pinned; no other model is accepted). On the new path, routing (which families), the matching of proposed codes to
events, contradictions, completeness facts (extent and the like), clarification questions, review, save, reload and export read that
persisted inventory. None of them calls the legacy semantic reader: `studio.gi.detect`, `studio.gi.services`, `studio.gi.context`,
`studio.gi.structure` / `sections`, `studio.gi.cues` / `purpose`, or the validation checks that consume them. A test and operator-side
evidence enforce this.

(b) **What is not semantic interpretation, and stays.** Ingestion and text extraction; source integrity (revision text, hashes,
offsets); evidence binding (every quotation and attribute anchor located in the revision); the reference store and the coding
rules (code definitions, inclusions and bundling, required facts); tenant isolation; human approval. These now take their inputs
from the inventory. Locating a quotation is necessary, not sufficient: each attribute needs its own support.

(c) **Participants.** Corti, Astra and Fable keep their roles and their independent first assessments. Their proposed codes are
matched to inventory events. The 2026-11-05 rulings stand: an explicit, supported proposal reaches review whoever proposed it, and
agreement is never approval.

(d) **Unresolved attributes.** A required attribute that is unknown or unverified holds only the code that depends on it, with a
focused question. Unrelated supported codes proceed.

(e) **Existing records.** Assessments made by the legacy reader stay exactly as they are and are not re-assessed silently. Reload
and export read the persisted assessment. A re-assessment is an explicit act that creates a new assessment.

(f) **Rollback.** The installed image (`cpt-studio:c2e53f8e7d33`) stays tagged. Migrations are additive, so that image can run
against the migrated database; this is tested before the install.

(g) **The 2026-11-09 requirement and amendment.** Their outcome conditions carry over where this directive's checklist restates them:
target, technique, time, performer and extent association; genuine contradictions; targeted unresolved states; a regression is a
regression. Their MEANS, repairing the keyword reader stage by stage, is superseded. The U32 c4 workflow was stopped at 07:12Z after
its files were hashed, and its four-result counterexample registry (1,374 entries) is kept as a regression corpus for the replacement.

(h) **Spending.** Gemini calls run in purposeful, bounded batches with concurrency one; every request's usage is recorded and
reported. The legacy reader's code stays in the tree for rollback only and is not deleted in this change.

## Owner message, 2026-11-11 — the Gemini spending cap raised to about $300

Received 2026-11-11T06:27Z in session 30a58364, after the session reported that the project's monthly spending cap (reached
2026-11-10 13:56Z at about $26) blocked the migration's live checks. Verbatim:

> i SET HIGH SPENING LIMIT AROUND 300 CAP FOR NOW DONT WORRY ABOUYT IT

**Session interpretation.** This is the money decision (standing authority class d). The cap is now about $300 for the month.
The migration's planned live checks may send within it: g1 x3 on the test instance (about $4.60 in all), the test-instance
walk, and the c6/c7 blind walks after the install. Interpretation (h) of the 2026-11-09 directive still governs every send:
purposeful, bounded batches with concurrency one, each with its own cost cap, and every request's usage recorded and reported.
A 429 with no QuotaFailure detail is still a hold, never retried in a loop (DECISIONS D39).

## Owner directive, 2026-11-12 — Gemini owns the open-ended clinical interpretation; the phrase-by-phrase repair campaign stops

Received in session 68197eb1 (continuing 30a58364) after the session reported that the migration's narrowing-only repair rounds
were not converging. Since round 5f (05a881a75), 14 repair builders had produced 7 integrable repairs, and every review found new
critical wordings, mostly paraphrases of the classes just repaired. The session asked how to proceed. The owner chose "Gemini
judges, fail closed (Recommended)", then wrote, verbatim:

> Proceed with option 1. This confirms my existing decision: Gemini must own the open-ended clinical interpretation. Stop the phrase-by-phrase semantic repair campaign.
>
> Update HARNESS.md and the migration checklist before continuing. Preserve the current work and evidence.
>
> Required implementation:
>
> - [ ] Move judgments about timing, causality, entry ownership, targets, techniques, examined stations and extent into Gemini’s structured, source-linked event inventory. Represent supported facts, explicit negatives, contradictions and unknowns distinctly.
> - [ ] Remove remaining keyword-based reinterpretations and semantic vetoes from the new path. Do not reproduce the old reader under a new “verification” name. Keep deterministic schema, source-integrity, revision-binding and applicable coding-rule checks.
> - [ ] Define verification honestly. A quote existing in the document does not prove that it supports the claimed meaning. Check attachment to the correct event and surrounding qualifications. Gemini must not certify its own answer simply by setting “verified=true”.
> - [ ] Hold only decisions dependent on unresolved required facts. Give one focused explanation or question. Let unrelated supported codes proceed. Preserve broad denials and genuine contradictions; never treat an unknown target as proof that statements cannot conflict.
> - [ ] Keep Corti, Astra and Fable as coding participants. Model agreement alone must not approve a code. Preserve reviewer approval and customer-facing provider confidentiality.
>
> Before changing the prompt, freeze the acceptance cases and expected outcomes. Include independent documents, previous failures, equivalent paraphrases, meaning-changing variants and repeated runs. Measure both wrong READY results and unnecessary holds. An all-held result cannot pass.
>
> Use necessary fresh Gemini recordings in small, bounded batches under my existing testing authority. Preserve prior recordings and distinguish fresh calls from replay.
>
> After the new interpretation path passes meaningful checks, complete installation and the actual website workflow: upload, processing, review, save, reload and downloaded reports. Verify the deployed runtime uses Gemini and does not invoke the retired semantic vetoes.
>
> Keep the current site available until the replacement is ready to switch. Preserve existing records and rollback capability.
>
> Continue through the authorized implementation and verification. Report the installed revision, remaining defects, incorrect approvals, unnecessary holds, usage and actual download results. Do not call the migration complete at the design, recording or offline-test stage.

**Session interpretation.**

(a) **What stops, and what is preserved.**
- STOPPED: the phrase-by-phrase repair campaign, refutation rounds 5-6 with repair rounds 5-5h, each adding deterministic word
  readers for the next counterexample.
- PRESERVED as evidence and as the baseline: the branch `feat/cpt-studio-gemini-interpreter-20261109` at 4726a8ce6, pushed and
  confirmed on origin; DECISIONS D1-D177 with every integration entry; the session's `gemini-migration/` directory (rounds,
  reviews, refutation results with their case files, the audited differential gate `gate5/` and its run on 05a881a75, the FRESH
  recordings and scores); the U32 c4 registry (1,374 entries).
- Nothing is deleted.

(b) **What Gemini owns.** The structured, source-linked event inventory carries the judgments of timing (including relative to the
date of service), causality (what an act was part of or caused by), entry ownership (whose entry an act is told in), targets,
techniques, examined stations and extent.
- Each is an attribute with its source link and a state that keeps four things apart: supported, explicitly negated, contradicted,
  and unknown.

(c) **What the deterministic layer keeps, and what leaves the new path.**
- Keeps: schema validation, source integrity, revision binding, the attachment checks of (d), and the applicable coding-rule checks
  (reference rows, CPT and NCCI relations, base and modifier rules) over the inventory's facts.
- Leaves the new path: every reader that re-reads the document's words to reinterpret an attribute Gemini owns, or to veto a code.
  Examples are the same-day frames, label and signature grammars, yield and denial clause readers, site and route phrase readers,
  and station word readers.
- It is not reproduced under another name. The legacy reader stays archived for rollback only.

(d) **Verification, honestly.** A cited quote existing in the revision proves only that the quote exists.
- The design must check each claimed fact's ATTACHMENT to the right event (the span lies within that event's own cited
  statement), and the SURROUNDING QUALIFICATIONS of that statement (negation, uncertainty, plan, another occasion or another
  performer), by means the design states and refutes.
- The interpreter's own flag never establishes support. No field Gemini sets ("verified", a confidence) certifies its own answer.

(e) **Holds.**
- Only a decision that depends on an unresolved required fact is held, with one focused explanation or question.
- Unrelated supported codes proceed.
- Broad denials and genuine contradictions are preserved.
- An unknown target never proves that two statements cannot conflict.

(f) **Participants and approval.** Corti, Astra and Fable stay coding participants. Model agreement alone never approves a code.
Reviewer approval stays required. Provider and model names stay out of customer screens and downloads.

(g) **Acceptance, frozen BEFORE the prompt changes.**
- The cases and their expected outcomes are committed by hash before any prompt change. They include:
  - independent documents (g1, sealed; c6 and c7 stay sealed for the post-install walk);
  - previous failures (the registry, the refutation rounds' confirmed findings, FRESH's recorded failures);
  - equivalent paraphrases;
  - meaning-changing variants;
  - repeated runs.
- Measured: wrong READY results (wrong code, wrong act or wrong facts), wrong exclusions and dropped genuine questions, AND
  unnecessary holds.
- The pass thresholds are fixed before measuring. An all-held result cannot pass.

(h) **Recordings.** Fresh Gemini calls run under the existing testing authority (the cap of about $300, 2026-11-11), in small,
bounded batches with concurrency one; every request's usage is recorded.
- Fresh calls are labelled apart from replays.
- Prior recordings (fresh-frozen, fresh2-frozen, the trial's) are kept unchanged.

(i) **Installation.**
- Only after the new interpretation path passes the frozen checks, through the established path (PR, CI, `scripts/merge-pr.sh`,
  a committed declaration, `scripts/run-ruled-mutation.sh`).
- Then the actual website workflow on the installed site: upload, processing, review, save, reload and downloaded reports.
- Then verification that the deployed runtime uses Gemini and invokes none of the retired semantic vetoes.
- The current site (c2e53f8e) stays available until the switch; existing records and the rollback image are kept.

(j) **Report.** The installed revision, the remaining defects, the incorrect approvals, the unnecessary holds, the usage and the
actual download results. The migration is NOT complete at the design, recording or offline-test stage.
