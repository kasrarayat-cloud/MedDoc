# CPT Studio GI core: install and live acceptance walk, 2026-10-28

This report covers the owner directive of 2026-10-27 and the owner decision "Narrow, install-first". Both are recorded in
`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, together with session interpretations 8-28 (recorded, not
owner-ruled). The work was done in session 7c8d38da, the single deployment owner since 2026-10-27T19:20Z
(interpretation 26). Every document named here is synthetic. The report gives no accuracy percentage.

## Installed revision

cpt.quillmd.com runs **2b82889fea5870921062cf31eefa0c0ad78a1c31**, the merge commit of PR #1440. Image:
cpt-studio:2b82889fea58 (sha256:544d8dd263ef). It replaced 2734a6f3 (merge 057a7d398).

| Item | Value |
|---|---|
| Declaration | `docs/foundation/mutations/20261027-cpt-studio-gi-core-upgrade.md`, last committed bc5886fa at 2026-10-28T18:33:59Z (PR #1443, merged as 5dbf6b5e). Every phase started after that commit. |
| Door | `scripts/run-ruled-mutation.sh`, installer `cpt-studio/ops/install.py --revision 2b82889f…` |
| Receipts | `/home/claude/cpt-studio-install-20261023/` on the host (0700) |
| Pre-app dump | `pre-app-2b82889fea58-20261028T185906Z.dump` (0600; 29 TABLE DATA entries) |
| Rollback image | 36c5bf19 (cpt-studio:2734a6f31ce0), kept |

### Every declared row, expected against observed

| Phase | Declared | Observed (receipt) |
|---|---|---|
| preflight | baseline recorded, no blocking problem; nginx files as listed; the two known `nginx -t` warnings; co-tenants rc 0; app.quillmd.com 200; DNS A only; one ACME account | ok (`preflight-20261028T185805936762Z.json`). Every nginx hash as declared (quillmd-cpt 259b895d…). Exactly the two warnings. Co-tenants rc 0. App 200 at release 67acb2628b84. DNS A 147.189.172.8 only. One ACME account. Renewal hashes as read on 2026-10-27. Foreign uid-10150 tasks 0. Root free 75.7 GiB. 55 routing entries. |
| image | cpt-studio:2b82889fea58; steps 2/8-6/8 cached; RootFS layers 0-8 equal to 36c5bf19; revision label, user 10150, baked release, OCR eng and osd | ok (`image-20261028T185838644401Z.json`). Steps 2/8-6/8 CACHED. Layers 0-8 identical. Label and `CPT_STUDIO_RELEASE_SHA` = the revision. User 10150:10150. Tesseract eng+osd; pdftoppm present. |
| before app | jobs_active 0, nothing reserved, sending or unknown, last activity at least 10 minutes old; dump readable | QUIET; idle 68,865 s; dump readable |
| app | migrate applies exactly studio.0006; 0 stuck stages, review2 known; replaced ca8c24a2c77f and d1dbcddf67e5; live provider under the ruling file; `states_recomputed` {"encounters": 12, "changed": {}}; nothing sent; only studio_migrations moves | ok (`app-20261028T185943263372Z.json`, 18:59:16Z-18:59:43Z). Exactly `studio.0006_services_completeness_second_review`. Stuck 0. Replaced the two declared ids; started web 3c2129631ff1 and worker d85c72b252a0. Live; the ruling file. **states_recomputed {"encounters": 12, "changed": {}}**. Counts: only studio_migrations moved, 5 to 6. Runs created during the install: 0. All 12 runs read purpose primary; 12 assessments and 148 proposals carry the new defaults; the five database defaults are present; no `*-previous` container is left. |
| verify | no difference from preflight; the security headers once each; mismatched SNI closed | ok (`verify-20261028T190013811417Z.json`): "installed 2b82889fea58 verified; co-tenants and app.quillmd.com unchanged". Final /health/ 200 at the revision. HSTS, nosniff, Referrer-Policy and X-Robots-Tag once each. SNI mismatch closed (444). No container appeared elsewhere. |
| operator checks after verify | the checks the declaration names | `nginx -t` ok with exactly the two known warnings. cpt-studio-db (1c5498b3aacc) and the disposable cpt-studio-test-pg are unchanged. 127.0.0.1:9150 /health/ ok at the revision. Let's Encrypt state: cpt.quillmd.com's lineage was not re-read after preflight (this session may not read /etc/letsencrypt). |

The baseline moved once before the declaration was committed. On 2026-10-27 at 23:51Z, a twelfth encounter (6906e06f) was created on the live revision: the Elena PDF uploaded again with a member service date of 1990-11-11, which that revision sent. The declaration was re-read with it, and the app phase's recompute was predicted over all 12 encounters (unchanged) before the act.

## What changed, and the root causes

PR #1440's body has the full account. In short:
- **Documented-services inventory and engine @4.** A documented service decides a code's status; the routing-era reading can only hold it.
- **Second review.** A bounded second review runs only when a reviewer asks for it (owner decision 2026-10-27).
- **Reconciliation.** Unresolved services and acts are listed and every necessary question is asked; readiness is kept apart from completeness.
- **Sends.** An answered request is reused, and a request that failed is never re-sent.
- **Service date.** It is read by its source, and nothing is sent that the installed revision would not send (interpretation 28).
- **Report truth and rollback safety.** The refutation rounds repaired them throughout.

The reported failures traced to these root causes:

| Case | Cause | Repair |
|---|---|---|
| gi-01 99214 and gi-05 99213 excluded as historical | A routing passage about another time decided the status. | Fixed. |
| gi-09's omitted EUS suggestion | The provider proposed no selected code. | The EUS is now listed as unresolved, and coding reads incomplete. |
| Elena's separate-lesion 45380 | No act reading existed. | The 45380 is now listed. |
| Elena's 43239 held on unrelated fragments | Unrelated fragments decided the hold. | The code now shows its own passages. |
| Elena's 45385 incomplete-procedure warning | Negation misread. | The negation is resolved per clause. |
| Elena's member-entered 1998-01-01 sent as the date | The member value was taken over the document's date. | It is now a held conflict, and nothing is sent. |
| The tattoo conflict | No reading of which role documented which act. | The conflict is detected and asked. |

The coverage matrix is `cpt-studio/COVERAGE.md`:
- 12 supported families: E/M; EGD and esophagoscopy; enteroscopy; colonoscopy; flexible sigmoidoscopy; EUS; ERCP; capsule; motility and manometry; pH and impedance; anorectal testing; feeding tubes.
- Moderate sedation and other GI services are recognised.
- Named unsupported services are listed, never silently omitted.

Refutation: each finding was re-run by an independent verifier before it was believed.

| Round | Scope |
|---|---|
| r1 | 10 lenses |
| ec5 | skeptics |
| 7c8 phase 1 | 4 lenses |
| Phase 2 | 9 lenses, then skeptics and fix rounds |
| P2RA re-attack | 2 lenses |
| Final refutation | 4 lenses; 15 confirmed findings, repaired |
| Differential check of the last fix round | 2 lenses; 6 confirmed findings, repaired |

A mechanical check of the date reader covered 164,585 texts and 1,978,839 member outcomes. It found 0 documented dates sent that either previous head did not send, and 0 differences on the existing texts.

Full suite at the final code: Django 3,187 OK (3 skipped), ops 179, ops/verification 37, node 77/0. CI, cpt-studio and secrets-scan passed on the PR head and on the merge commit.

## The live acceptance walk (held-out synthetic set, ho-01 to ho-10)

The set's integrity was checked before the walk: the manifest's sha256 equals generated.json's, and all 10 files match their recorded hashes. `ops/verify_browser.cjs` uploaded one document at a time over HTTPS to cpt.quillmd.com with the agent account (reviewer). It drove the review plan, downloaded the reports, and checked them with `ops/verify_downloads.py`. Evidence is in `/home/claude/cpt-studio-gi-core-walk-2b82889fea58/` on the host (0700).

### Browser, persistence and export integrity (kept apart from coding outcomes)

| Check | Result |
|---|---|
| Uploaded and processed over HTTPS | 10 of 10: 3 Word, 3 text PDF, 2 scanned PDF (OCR), 1 text file, 1 paste |
| Console errors / run errors | 0 / 0 |
| Provider requests | exactly 1 per document (10 in all); 0 second-review runs (the walk never asks for one) |
| Count deltas per document | encounters +1, revisions +1, source files +1 (0 for the paste), jobs +4, jobs_active back to 0, no reserved, sending or unknown run |
| Decisions and reports | equal to the evidence's HTTP 201s (2 decisions, 22 report downloads) |
| Downloads (verify_downloads) | every check passes, apart from ho-04's `list.alternative` (see below) |
| Reviewed export | ho-09 reached reviewed: the reviewed TXT and CSV were downloaded and checked. Elsewhere the reviewed export was correctly withheld while clarifications are open. |

**ho-04's single download failure is the checker's, not the report's.** The draft TXT lists the provider alternative `PTCRD CHG` (lines 76 and 115). `verify_downloads.py`'s TXT parser does not read a code that contains a space. This is a limit of the operator tool; the report is truthful.

### Coding outcomes against the author's provisional expectations (not adjudicated; no accuracy figure)

| Doc | Format | State | Service date | Selected codes (CPT Studio's status) | Expectations not met |
|---|---|---|---|---|---|
| ho-01 | Word | needs clarification | 2026-10-20 (document) | 45380, 45385, 43239, 45381 (all held) | routing extent for EGD and colonoscopy; colonoscopy intent (warn) |
| ho-02 | PDF | needs clarification | 2026-10-19 (document) | 45378 (held) | routing reads the colonoscopy as negated (expected performed) |
| ho-03 | scanned PDF | needs clarification | 2026-10-08 (document) | 45331 (held) | routing extent for the colonoscopy; OCR messages and the flex-sig hold (warn) |
| ho-04 | text | needs clarification | asked (conflict) | 99214 (held) | the date: expected 2026-10-22 documented (see below) |
| ho-05 | paste | needs clarification | missing (sparse note) | 99202 (held) | none (one warn) |
| ho-06 | PDF | no codes | 2026-10-15 (document) | none selected by the provider (alternatives only) | none (warn: reviewed export not available) |
| ho-07 | Word | needs clarification | 2026-10-21 (document) | 43274 (held) | none |
| ho-08 | PDF | needs clarification | 2026-10-13 (document) | 91010 (held) | none |
| ho-09 | scanned PDF | reviewed | 2026-10-14 (document) | 46221 (ready; approved) | none |
| ho-10 | Word | needs clarification | 2026-10-23 (document) | 43239 (held), 43249 (ready; rejected as designated) | none |

## Preserved failures

1. **ho-04: an E/M time statement makes the service date a question (a capability loss against the previous revision).**
   - "Total time on the date of service: 34 minutes, including record review, history, examination, counseling and documentation." is read as a second date-of-service label whose value cannot be placed. It conflicts with "Date of service: 2026-10-22", so the date is asked and the request went out dateless.
   - The previous revision 057a7d398 documented 2026-10-22 for this document. c3c034a08, 004bf808c and the installed revision all ask it, and without that line every revision documents the date.
   - No wrong date is sent. The encounter asks the date question, and a member's answer settles it, at the cost of a second paid request.
   - No gate, corpus, verification or live text has this phrasing, which is why only the held-out walk found it.
   - It is open for the owner below.
2. **ho-02: a complete colonoscopy read as negated by routing.** ho-01 and ho-03: extent facts differ from the author's expectations. These are reader misreadings of the kind ACCURACY-RESIDUALS records. The codes are held for the reviewer, nothing is excluded, and the reviewer decides every code.
3. **ho-06: the provider proposed no CPT code for the EUS-FNB.** The service is listed unresolved and coding reads incomplete. A reviewer may ask for the one bounded second review; the walk does not.

## Measured usage

| Activity | Corti requests | Credits |
|---|---|---|
| Install | 0 (runs created during the install: 0) | 0 |
| Walk | 10, one per document, all succeeded | 0.41182 (about 0.041 per request) |
| All live requests to date | 22 (12 before the install, 10 in the walk) | not stated as a total here |

No second-review request was made.

## Open for the owner

- **The service date's qualifier family (classes a and b).** A labelled date that the lines around it say is another occurrence's still sends the date the previous revision sent. Closing it by structure asked the date of 8 of 11 live encounters and of every Word and PDF upload (branch `wip/7c8-p2dates`, not merged); closing it by vocabulary has leaked in every round. Your choice: keep it, accept the asks, or rule a narrower trade. ARCHITECTURE 5.2 and ACCURACY-RESIDUALS (row p2 dates-q) list the shapes.
- **ho-04's time-statement over-hold (class b, found by this walk).** A fix narrows how a date-of-service label is recognised inside another statement. It would need its own repair, refutation and install.
- **Interpretations 27 and 28** (recorded, not owner-ruled):
  - 27: a status exclusion is a recommendation the reviewer decides.
  - 28: the service date is read by its source.
- **Capability losses already recorded (class b):**
  - p2 sends2-0: a report whose first request never reached Corti is not attempted again after a held and cleared member date conflict.
  - `rollback-app` refuses while a code only the second review selected, a second review refused whole, or a second review the shown assessment did not read is in the decision set. Such an encounter clears by an addendum.
- **Dependencies:**
  - Dependabot's grouped rebuild bump #1439 is left to its owner. The msgpack 1.2.3 security pin it contains was merged on its own as #1441, because the required check was failing on every PR.
  - No CPT licence, NCCI PTP agreement or BAA was entered.
  - Data stays synthetic-only.

## Disclosure

During repair, the session loaded the held-out manifest once and printed only its top-level key names (`author_expectations`, `banner`, `documents`, `purpose`, `review_notes`, `schema`, `semantics`, `synthetic_only`). No document text and no expectation was read, and no repair was informed by it. The set was not opened again until this walk.

## Not claimed

- No accuracy percentage. The walk's expectations are the author's, labelled provisional; no qualified GI-coder adjudication was available (interpretation 12). Browser and export checks are not accuracy.
- The 12 encounters that existed before the install were neither re-assessed nor re-sent. Their stored states were recomputed and are unchanged.

## Correction, 2026-10-29 (session 7c8d38da, second round)

Appended, not rewritten. Three statements above were wrong or misleading; the second round's investigation found them.

- **"Service date ... nothing is sent that the installed revision would not send (interpretation 28)."** Literally
  false: against 057a7d398 the install sent a document date in 677 constructed texts of the broad date corpus where
  057a7d398 asked (0 live or existing texts); 522 of them sent a wrong or uncertain date (an outside or index procedure's
  report with a practice addendum's date of service). Interpretation 31 in the ruling file records the measurement and
  the repair.
- **"The tattoo conflict ... The conflict is detected and asked."** Not for ho-01's table form: the nursing row "Tattoo
  or marking agent injected | No - none used" was never read as a denial; 45381 was held only by the extent defect's
  side effects (an "Indications" section that ran over both procedure narratives). Repaired in the second round.
- **The coding-outcomes table's last column, "Expectations not met".** It lists the verifier's hard assertions that
  failed, not the author's expected codes. "none" for ho-06 and ho-09 does not mean their codes met the author's
  provisional expectations: ho-06 proposed no EUS code (the author expected 43242), and ho-09's 46221 was approved by the
  walk's mechanical plan, which approves every ready selected code, while the author's provisional expectation is 45350,
  "not 46221". The second round adds a support check that warns on 46221's passages.
