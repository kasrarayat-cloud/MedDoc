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
