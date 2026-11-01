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

