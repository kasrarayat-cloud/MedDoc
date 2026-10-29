# CPT Studio GI round 2: install and live acceptance walk, 2026-10-29

This report covers the owner directive of 2026-10-28 ("reliable GI interpretation and a usable synthetic
demonstration") and the owner's two decisions of the same day ("Narrow source rule", "Separate demo reviewer"). All
three are recorded in `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, with session interpretations 29-37
(recorded, not owner-ruled). Session 7c8d38da was the single integration and deployment owner (interpretation 30).
Every document named here is synthetic. The report gives no accuracy percentage.

## Installed revision

cpt.quillmd.com runs **90377ec6f413ac6cf1601836a286f45e2af53e37**, the merge commit of PR #1445. Image:
cpt-studio:90377ec6f413 (sha256:0b95b5113214). It replaced 2b82889f (PR #1440).

| Item | Value |
|---|---|
| Declaration | `docs/foundation/mutations/20261029-cpt-studio-gi2-upgrade.md`, committed 5c02ba559 at 2026-10-29T06:45:34Z (PR #1446, merged as ca2247e5). Every act started after that commit (first at 07:18:02Z). |
| Door | `scripts/run-ruled-mutation.sh` from a clean detached checkout of ca2247e5; installer `cpt-studio/ops/install.py --revision 90377ec6f413…` |
| Receipts | `/home/claude/cpt-studio-install-20261023/` on the host (0700) |
| Pre-app dump | `pre-app-90377ec6f413-20261029T071920Z.dump` (0600; 29 TABLE DATA entries) |
| Rollback image | 544d8dd263ef (cpt-studio:2b82889fea58), kept, with its image receipt |

### Every declared row, expected against observed

| Phase | Declared | Observed (receipt) |
|---|---|---|
| preflight | the nginx files as on 2026-10-28; the two known `nginx -t` warnings; co-tenants rc 0; app.quillmd.com 200; DNS A only; one ACME account; at least 10 GiB free | ok (`preflight-20261029T071808125951Z.json`). All 19 nginx file entries identical to the 2026-10-28 receipt (quillmd e9aa049d…, quillmd-cpt 259b895d…). Exactly the two warnings. Co-tenants rc 0. App 200 at release 67acb2628b84. A 147.189.172.8 only. One ACME account. 59.4 GiB free. Routing 55 of 55 unchanged. Foreign uid-10150 tasks 0. |
| image | cpt-studio:90377ec6f413; dependency steps cached; layers up to the COPY equal to 544d8dd263ef's; revision label, user 10150, baked release, OCR | ok (`image-20261029T071851864400Z.json`). Steps 2/8-6/8 CACHED; layers 0-8 identical, only COPY and collectstatic new. Label `org.opencontainers.image.revision` and `CPT_STUDIO_RELEASE_SHA` = the revision. User 10150:10150. Tesseract eng+osd; pdftoppm 22.12.0. |
| before app | jobs_active 0; nothing reserved, sending or unknown; no activity in 10 minutes; dump readable | quiet; idle 34,033 s; dump readable |
| app | migrate applies nothing; 0 stuck stages, review2 known; replaces 3c2129631ff1 and d85c72b252a0; live provider under the ruling file; `states_recomputed` {"encounters": 22, "changed": {}}; every count unchanged; nothing sent | ok (`app-20261029T071956710858Z.json`, 07:19:28Z-07:19:56Z). Migrate log: "No migrations to apply.". Stuck 0, review2 known. Replaced the two declared ids; new web 5916ab772b79 and worker 6158f6e95bd4 on 0b95b5113214. Live; the ruling file. **states_recomputed {"encounters": 22, "changed": {}}**, as predicted. Every count equals the pre-app reading. Provider runs, jobs and audit events created during the install: 0. No `*-previous` container. |
| verify | no difference from preflight; the security headers once each; mismatched SNI closed | ok (`verify-20261029T072028456671Z.json`): "installed 90377ec6f413 verified; co-tenants and app.quillmd.com unchanged". HTTPS /health/ 200 at the revision under normal certificate verification. HSTS, nosniff, Referrer-Policy and X-Robots-Tag once each. SNI mismatch closed (RemoteDisconnected). No container appeared elsewhere. |
| operator checks after verify | the checks the declaration names | `nginx -t` ok with exactly the two known warnings. cpt-studio-db (1c5498b3aacc) running, unchanged; the disposable cpt-studio-test-pg untouched. cpt.quillmd.com's Let's Encrypt lineage was not re-read after preflight (this session may not read /etc/letsencrypt). |
| step D, the demo reviewer | "created human account demo-reviewer (reviewer)" and the workspace line; no password in the output; users 2→3, memberships 2→3, audit_events +1, category profiles_version gi-profiles@2→@3; nothing else | 07:21:33Z, exit 0. Exactly the two lines. The password was not found in the captured output (byte search; the capture was then shredded). users 2→3, memberships 2→3 (role reviewer, active, workspace ac7def49…), audit_events 193→194 (`account.provisioned`, no actor, created true), category gi-profiles@2→@3. The owner's and the agent's accounts are unchanged; no other count moved. |

**The demo reviewer account:** username `demo-reviewer`, display name "Demo reviewer (synthetic demonstration)", role
reviewer in the Gastroenterology workspace. Its password is on the server only, at
`/home/claude/.cpt-studio/demo-reviewer-password` (mode 0600). It was never printed or committed. Decisions made with
it are attributed to it, not to the owner.

## What changed: the repairs, verified on the documents the directive named

PR #1445 carries the round's repairs. Its body and `cpt-studio/ACCURACY-RESIDUALS.md` ("GI round 2") list each with
its before and after. On the four documents the directive named, their retained Corti responses were replayed through
both revisions (no provider), and each was walked again live:

| Document | 2b82889f (installed before) | 90377ec6f413 (installed now) | Live walk today |
|---|---|---|---|
| ho-01 (EGD and colonoscopy, tattoo charted both ways) | 6 open questions; 43239, 45380, 45381 and 45385 each held for an extent or status question | extents read (duodenum; terminal ileum); 43239, 45380 and 45385 ready; 45381 held for the genuine conflict (physician: tattoo injected; nursing checklist: none used) | pass; 43239, 45380 and 45385 approved; 45381 left for the reviewer's answer |
| ho-02 ("Examination complete, not aborted.") | 45378 held: the "not" read as the colonoscopy's denial | 45378 ready, coding complete pending review | pass; 45378 approved; reviewed TXT and CSV |
| ho-03 (stricture at 28 cm) | no extent read | "incomplete: sigmoid colon"; Corti's 45331 checked against the biopsy | pass; 45331 left undecided (the reviewer's call: a colonoscopy stopped at a stricture) |
| ho-04 (E/M with "Total time on the date of service: 34 minutes") | date asked ("34" read as a date), 99214 held | date 2026-10-22, as documented; 99214 ready | pass; date 2026-10-22; the designated reject path exercised on 99214 |

## The live acceptance walk

Fourteen documents, 07:21:59Z-07:28:01Z, through https://cpt.quillmd.com as the agent account review-agent with
`ops/verify_browser.cjs --no-auto-approve --deadline-seconds 900`, one document per invocation, each started only when
jobs_active was 0:
- **acceptance:** the fresh synthetic set h2-01..h2-10. It was written by an author who read neither the application
  code nor the repairs (interpretation 29), and this session read it only after the code was frozen;
- **regressions:** ho-01..ho-04.

The manifests are amended copies of the authors' (h2 sha256 07092d12…, ho d7105586…). They add only
`review_plan.approve_codes`, chosen by this session after reading each source, and the two exercises below. The
regenerated h2 documents are byte-identical to the author's render.

### Browser, persistence and export integrity (kept apart from coding outcomes)

- 14 of 14 documents were processed to completion, with jobs_active back to 0 each time. The browser logged no console
  error and the site returned no 5xx. /health/ still serves the revision.
- `ops/verify_downloads.py` re-checked every downloaded report file by file: 0 failures (46 to 90 checks per document).
  - h2-03, h2-06, ho-02 and ho-04 produced reviewed TXT and CSV reports.
  - The other ten withheld the reviewed export, each with its blockers (an open question, an undecided code or no
    selected code), and the walk asserted that the export was not offered.
- **Bounds (declared, database counts):** jobs +58 (bound 60), provider runs +15 (16), sent +11 (15), second-review runs
  +0, encounters +14, users, reference data and migrations +0. Credits used: 0.425128.
- **Reuse:** ho-01, ho-02 and ho-03 made a run but sent nothing and used no credits. Their identical requests from
  2026-10-28 were reused, which is the duplicate protection observed live. ho-04 sent one request, because it now
  carries the date 2026-10-22.

### The two exercises

- **h2-10, controlled recovery of a held request: pass on every hard check.** The member entered 2026-10-24, the
  signature date, where the note documents 2026-10-23.
  - The upload recorded one not-sent hold; nothing was sent, built or reused.
  - One context save to 2026-10-23 made exactly one request, for that date (0.030420 credits), and left the hold run
    unchanged.
  - The same save made again recorded no run and sent nothing, and the screen's form refused it ("No context change to
    save.").
- **h2-09, the reviewer-requested second review: not reachable in this walk.**
  - The primary run left the EUS unresolved. The second review was not offered, because the date question was open: "A
    second review needs a known, agreed date of service: answer the date question first."
  - The date question was open because "Date of examination: 2026-10-22" is no date-of-service label to this reader.
  - The walk does not force an ask. Answering the date first would have made a dated primary request; with the review,
    that is three sends, above h2-09's declared bound of two.
  - The second-review path was exercised live on 2b82889f on 2026-10-28: ho-06, labelled synthetic, one request,
    0.041256 credits. Corti returned 12 candidates of other families and no EUS code, nothing was added, and the raw
    results were kept.
  - This revision's new second-review wording is therefore still unobserved live.

### Coding outcomes against the authors' provisional expectations (not adjudicated; no accuracy figure)

The fresh set's documents were replayed offline through **both** revisions with their stored Corti responses. All ten
read **identically** at 2b82889f and 90377ec6f413: none of the failures below is a regression. They are limits both
installed revisions share, which an independent set found for the first time.

| Document | Walk | What happened | The author's reading |
|---|---|---|---|
| h2-01 (EGD and colonoscopy, a procedure-summary table and a section for each) | fail | EGD and colonoscopy read "uncertain" with no extent; 43239 and 45378 held | both performed to their stated extents (third portion of the duodenum; terminal ileum) |
| h2-02 (scanned colonoscopy stopped by looping) | fail | "Deepest point reached: hepatic flexure" not read as the extent; 45385 held | 45385, incomplete (52) |
| h2-03 (flexible sigmoidoscopy, lesion left for EMR) | **pass** | 45330 approved; reviewed report | 45330 |
| h2-04 (scanned EGD stopped at the pylorus) | fail | "Furthest extent: pyloric channel." not read as the extent; 43239 held | 43239, incomplete (52) |
| h2-05 (colonoscopy cancelled before insertion) | fail on a label | read "cancelled", no code: the outcome the author expects, but the status label is outside the author's expected set | nothing billable |
| h2-06 (E/M, "Time spent on the date of the encounter: 33 minutes") | **pass** | date 2026-10-14 sent, not asked; 99214 approved; reviewed report | 99214 |
| h2-07 (E/M, results table with a "Date of service" column) | fail | the date was right (2026-10-21), but the visit was read "uncertain" from "Return in one year ..."; 99213 held | 99213 |
| h2-08 (E/M, two "Date of service" labels: 2026-10-05 and, in the charge block, 2026-10-06) | fail | **2026-10-05 was sent**, with no date question; the visit was read "uncertain"; 99215 held | the date must be asked; 99215 |
| h2-09 (EUS limited to the stomach) | fail | date asked ("Date of examination" not read); EUS read "incomplete"; Corti selected no code; no second review (above) | 43238 (never 43242) |
| h2-10 (ERCP stent exchange, member-date conflict) | **pass** | the recovery above; Corti proposed 43274, left undecided (the plan approves only 43276) | 43276 |

The regression documents ho-01..ho-04 all pass.

## Preserved failures, with their mechanism

- **h2-08 sends a date the document contradicts. This is a must-fix class 1 shape that 057a7d398, 2b82889f and
  90377ec6f413 all share.** The "Assessment and plan" section runs over "Charge information", a heading the section
  reader cannot place. The charge block's "Date of service: 2026-10-06" is therefore read as a planned occurrence's date,
  which never speaks against the header's 2026-10-05. Removing that one heading gives the right answer, a conflict and a
  question (measured offline). It was found in the frozen code by reading the acceptance set after the freeze, so it was
  recorded, not patched. Patching would have spent the acceptance set as evidence for this shape. Next round: let a
  heading that names charge or billing information end a plan section, or let a second own date-of-service label speak
  wherever it stands.
- **Extent labels and table rows:** "Deepest point reached:", "Furthest extent:" and a summary table's "Furthest point
  reached" column read no extent (h2-01, h2-02, h2-04), so those codes wait for an extent question. This is the safe
  direction.
- **An office visit read "uncertain" from its plan sentences** (h2-07, h2-08), so the E/M code waits for a question. This
  is the safe direction.
- **"Date of examination:" is no date-of-service label** (h2-09), so the date is asked. This is the safe direction, but
  it also blocks a reviewer's second review until a member answers the date.

These findings are recorded here, not yet in `cpt-studio/ACCURACY-RESIDUALS.md`. A change under `cpt-studio/` on main
would make main's `cpt-studio/` differ from the installed revision's, which the installer's tree check and a rollback
read. They go into that file with the next code change.

## Measured usage

- This walk: 11 requests sent, 0.425128 credits (0.016572 to 0.080844 each), against Corti's own reported usage.
- Since the start of the service, provider credits total 1.478504.

## Open for the owner

- **h2-08's date (class a, a product rule):** a second own date-of-service label after the body is silenced when an
  unplaced heading follows a plan section. Both installed revisions do this. Fixing it changes the date reader, and its
  refutation and acceptance would be the next round's.
- **The wrong-occurrence family beyond the narrow source rule (class a; interpretation 37, gi2 dates-F1-n1):** a dated
  line naming the documented procedure ("... performed on 11/04/2026") does not question the date-of-service label.
- **Recorded interpretations you may overrule:** 27 (a status exclusion is a reinstatable recommendation), 34 (the
  synthetic label of a second review is the reviewer's account and notes), 35 (a document whose only labelled date is
  another occurrence's holds any member answer).
- **Recovery left as it is (class b):** a not-sent primary attempt with no date question recovers only by an addendum
  or a new upload; a 401, 403 or 429 refusal is recorded failed and never re-sent identically.
- **An encounter whose coding cannot be completed** stays on the review queue ("Reviewed · coding incomplete"). What
  closes it is a product decision.
- **The second review needs an agreed date:** on a document whose date the reader cannot read, the reviewer must
  answer the date before asking. Whether a second review may run dateless is a product rule.
- **Your acceptance needs your eyeball (class c):** the reviewed TXT and CSV of h2-03, h2-06, ho-02 and ho-04, and the
  withheld ones with their blockers, are the documents a doctor would see.

## Is a complete doctor-facing synthetic demo ready?

**Not yet as a demonstration of reliable GI coding. Yes as a supervised demonstration of the workflow.**

- **What works end to end, live:**
  - upload of Word, PDF, scanned PDF, text and paste;
  - processing within the stage limits, and the review screen;
  - decisions labelled by account, and reviewed TXT and CSV reports re-checked file by file;
  - the held member-date conflict and its one-request recovery;
  - reuse of an identical answered request;
  - the reviewer's own account, `demo-reviewer`.
- **What a doctor would see go wrong on new documents:** 7 of the 10 fresh documents missed an author expectation.
  - Most failures hold a code for a question: extent labels, and visits read "uncertain".
  - One sends a contradicted date (h2-08).
  - The reviewer decides every code, and nothing was approved without one. But a demo that leads with "reliable
    interpretation" would show a question on most procedure reports and the h2-08 date.
- **Also still missing:** your eyeball acceptance (class c); licensed CPT descriptors (interpretations 1-3); and
  confirm and reinstate depend on the provider's response for each document.

A supervised demo is possible today if it is framed as "the system asks rather than guesses, and the reviewer decides".
A demo of reliable coding needs at least the h2-08 date rule and the extent and E/M-status readers above, refuted and
walked again.

## Disclosure

- The second fix round (5b125e737, bae4e81ac) was gated by a mechanical differential, not by another open refutation.
  On every case corpus the final head was compared with the installed revision and with the refuted head (aec8edf3f).
  It only removes sends, plus 18 recorded rows whose plain versions 2b82889f already sends. The convergence method is
  recorded in this round's ruling interpretations and PR #1445.
- This session found h2-08's mechanism by an offline preview of the frozen code, made before the walk.

## Not claimed

- No accuracy percentage. Every expectation is an author's, provisional and not adjudicated.
- Install checks, test volume and browser checks are not coding accuracy.
- The ten held-out documents ho-01..ho-10 were this round's development documents.
- No CPT licence, NCCI PTP agreement or BAA was entered.
- The demo reviewer's login was not exercised: its existence, role and membership were read by SELECT.
