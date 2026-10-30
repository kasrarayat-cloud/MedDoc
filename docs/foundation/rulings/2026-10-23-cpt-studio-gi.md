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
