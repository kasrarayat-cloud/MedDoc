# CPT Studio GI round 3: the narrow release, install and live acceptance walk, 2026-10-31

This report covers the owner's directive of 2026-10-29 and his decision of 2026-10-30, "Narrow release (Recommended)". Both
are recorded verbatim in `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, with session interpretations 53 to 61
(recorded, not owner-ruled). Session 1bf3b49c was the single integration and deployment owner. Every document named here is
synthetic, and the report gives no accuracy percentage. **No reliable-coding claim is made:** other contradicted-date
shapes remain known limits, and the extent, scope and inventory repairs did not ship.

## Installed revision

cpt.quillmd.com runs **80df1831d168c4ee83d83c37bac9860690986cf3**, the merge commit of PR #1448, on image
cpt-studio:80df1831d168 (sha256:88544c7cd33f). It replaced 90377ec6f413 (PR #1445).

| Item | Value |
|---|---|
| Declaration | `docs/foundation/mutations/20261031-cpt-studio-gi3-upgrade.md`, last committed af4a42117 at 2026-10-31T11:52:46Z (PR #1451, merged as a42c56f5). Every act started after that commit, the first at 12:25:56Z. |
| Door | `scripts/run-ruled-mutation.sh` from a clean detached checkout of a42c56f5 |
| Installer | `cpt-studio/ops/install.py --revision 80df1831…`, byte-identical to the one that installed 90377ec6f413 |
| Receipts | `/home/claude/cpt-studio-install-20261023/` on the host (0700) |
| Pre-app dump | `pre-app-80df1831d168-20261031T125510Z.dump` (0600; 29 TABLE DATA entries) |
| Rollback image | 0b95b5113214 (cpt-studio:90377ec6f413), kept with its image receipt |
| Citation of 80df1831 | the required checks pass: CI run 41190384588 and TruffleHog 41190384614. The cpt-studio run 41190384598 passes its checks, migration check and every suite (3,585 Django tests; ops 211 and 37; node 61 of 61), then fails at its last step, the pypdf 6.21.2 audit (see "The pypdf advisories") |

### Every declared row, expected against observed

| Phase | Declared | Observed (receipt) |
|---|---|---|
| before preflight | `scripts/check-cotenants.sh` in the checkout equals 80df1831's | identical (blob 35a01b2e) |
| preflight | nginx files and routing as on 2026-10-29; the two known `nginx -t` warnings; co-tenants rc 0; app.quillmd.com 200; DNS A only; one ACME account; at least 10 GiB free | ok (`preflight-20261031T122601663428Z.json`). nginx files and all 55 routing entries identical to the 2026-10-29 receipt; quillmd-cpt vhost 259b895d…; exactly the two warnings; co-tenants rc 0; app.quillmd.com 200 (release 67acb2628b84); A 147.189.172.8 only; one ACME account; 0 foreign uid-10150 tasks; 103.3 GiB free |
| image | steps 2 to 6 cached; layers other than the last two equal to 0b95b5113214's; pypdf 6.21.2; the package list identical to installed's | ok (`image-20261031T122632353202Z.json`), 11 s. The build log shows steps 2 to 6 CACHED. 11 layers each, the first 9 equal. pypdf 6.21.2. The package list read from 0b95b5113214 reproduces the recorded 166-line list (sha256 6f1b61f6…), and the new image's is identical. Tesseract 5.3.0 (eng, osd); pdftoppm 22.12.0 |
| before app | nothing queued, reserved, sending or unknown; no audit event in 10 minutes; dump at the declared path | quiet; idle 192,430 s; dump at the declared path, 29 TABLE DATA entries |
| app | migrate applies nothing; 0 stuck stages; replaces 5916ab772b79 and 6158f6e95bd4; `states_recomputed` {"encounters": 36, "changed": {}}; every count unchanged; nothing sent | ok (`app-20261031T125543968815Z.json`, 12:55:17Z-12:55:43Z). "No migrations to apply." Stuck 0. Replaced the two declared ids; new web 1f603dddd9aa and worker 083b9af8657a. **states_recomputed {"encounters": 36, "changed": {}}, as predicted.** Every count equals the pre-app reading. Provider runs, jobs and audit events created since the phase started: 0. No `*-previous` container |
| verify | no difference from preflight; the security headers once each; mismatched SNI closed | ok (`verify-20261031T125610994252Z.json`): "installed 80df1831d168 verified; co-tenants and app.quillmd.com unchanged". HTTPS /health/ serves the revision under normal certificate verification; HSTS, nosniff, Referrer-Policy and X-Robots-Tag once each; no container appeared elsewhere |
| after verify | `nginx -t` with only the two known warnings | ok, exactly the two warnings |

The state prediction was made beforehand over a read-only dump of the live rows, with this revision's code in a scratch
database on the test server: {"encounters": 36, "changed": {}}, and installed's code gave the same. A planted unknown
outcome changed one encounter, so the instrument can see a change. The installer's rollback hazard read over the same dump
named nothing, and its planted control was named.

## What changed

PR #1448 carries the release. Its body and `cpt-studio/ACCURACY-RESIDUALS.md` ("GI round 3 ... the narrow release") list
each change with its measurement and its limits.
- **h2-08's charge block.** Installed silently dropped a plan-section "Date of service" and sent the header's date, which
  the document contradicts. When the note's own closing charge or billing block states another date, the date now becomes
  a question. The question names the lines and the date each one states. Nothing new is sent: the document's own date
  answers it with one dated request, and any other answer is held as installed holds it.
- **The context re-read (gi-context@3).** An encounter recorded before the install has its context remade before any stage
  sends or assesses on it. So a queued or resumed stage cannot resend the old reading.
- **Disabled-provider safeguards.** With sending disabled, a remade context no longer drops a recorded provider answer or
  shows an unknown outcome as "provider not run".

Offline, on b5ddc4d32 (the frozen code), against installed:
- the reading gate changed nothing in 8,446 texts;
- of 227,700 constructed date texts, 2,160 turned from a sent date into the question, and every other text was identical;
- 0 dates newly sent;
- 61 of 61 mutants were killed.

Nine refutations ran over the narrow diff, each told to refute; the last two found nothing blocking.

## The pypdf advisories (interpretation 61)

Seven advisories against pypdf 6.21.2 (CVE-2026-119203 to CVE-2026-119209) failed the required dependency audit on every pull
request. All seven are denial of service from a crafted PDF.
- **The rebuild's pin moved** (PR #1449): `rebuild/requirements.txt` pins 6.21.4, so the required audit passes on its own
  merits. Nothing live changed. app.quillmd.com reports release 67acb2628b84, whose requirements pin pypdf 6.21.1. It keeps
  that until its own next install, which ships the new pin.
- **CPT Studio was not moved.** Four refutation lenses tested the move, and an independent agent reproduced each finding with
  both versions recorded. Under 6.21.4 they found 34 differences in how CPT Studio's reader reads uploads, four of them
  blocking:
  - a valid ReportLab PDF using a predefined CJK character map reads as a page of mojibake, which would be sent to the
    provider, instead of going to OCR;
  - a check mark named by a private-use glyph reads as an unchecked box, so a performed service reads as negated;
  - a cut string in an annotation's appearance loses its notice, or goes from partial to ok.

  This session reproduced all four.

  The advisories are contained by the ingest child: an address-space limit, a CPU limit, and a process-group kill at the
  deadline. So the service stays on 6.21.2, as installed. Its own workflow's audit stays red, after every test has passed,
  until a later round moves it with its reader repaired. The findings are listed in `ACCURACY-RESIDUALS.md` ("pypdf 6.21.4 is
  not taken"). The candidate is kept unmerged on `prep/cpt-studio-pypdf-6.21.4-20261031`.
- **A security finding on the live rebuild, P1, found on the way and not repaired here.** `pdf_inspect` refuses scripts and
  actions by walking what pypdf reads. pypdf drops a cross-reference section it cannot read, even with `strict=True`. So a
  crafted template can hide a script that the check never sees, on 6.21.1, 6.21.2 and 6.21.4 alike. The original is then
  returned byte for byte to the department's members. Recorded in `docs/rebuild/security-readiness.md` and
  `docs/rebuild/pypdf-6.21.4.md`.

## The live acceptance walk

Run 12:56:38Z-13:03:13Z through https://cpt.quillmd.com, one document per invocation, each started only when jobs_active
was 0 (`ops/verify_browser.cjs --no-auto-approve --deadline-seconds 900`, then `ops/verify_downloads.py`).

**The demo reviewer's login (no decision):** pass, 13 of 13 checks.
- Five requests: the sign-in form, the sign-in, the session (a human reviewer with an active membership in Gastroenterology),
  the sign-out, and the replayed session, refused with 401.
- Every count was unchanged, audit events included.
- The password file was passed by path and never read or printed.

**h2-08 (the release's own document, as a PDF):**

| Step | Observed |
|---|---|
| upload | the date asked: the charge block states 2026-10-06 against the header's 2026-10-05; the primary request carried no date line and was sent |
| answer 2026-10-05 | one dated primary run. Its request is byte-identical to the one sent for e084b793 on 2026-10-29, so it was **reused, nothing sent** (duplicate protection), as the declaration predicted |
| identical second save | refused by the form ("No context change to save."); the API save made no run |
| result | 99215 selected, needs_clarification and undecided, with both of its questions open (performed on the date; the level's basis), as installed reads it. No decision; the reviewed export withheld. No request carried 2026-10-06 |

h2-08 counts: provider runs +2, sent +1, jobs +7.

**The sealed set h4-01 to h4-06.** Its author read none of the service's code or the repairs, and this session read it only
after the code froze. Two of its documents are scans:

| Document | Date | Requests | Decisions | Reviewed export |
|---|---|---|---|---|
| h4-01 (paste, new-patient visit) | asked; answered 2026-10-26 | 2 sent (dateless, then dated) | none: 99204 needs a clarification | withheld |
| h4-02 (Word, EGD and flexible sigmoidoscopy) | asked; answered 2026-10-21 | 2 sent | none: no EGD code proposed; 45330 needs a clarification, so the designated rejection had no ready code | withheld |
| h4-03 (Word, EGD with two stated dates) | asked (read as missing, where the author expects a conflict); answered 2026-10-06 | 2 sent | none: 43244 needs a clarification | withheld |
| h4-04 (PDF, EGD and colonoscopy) | asked; answered 2026-10-19 | 2 sent | **43251 approved**, labelled as agent review | withheld: 45378 excluded by a documentation check (the colonoscopy read as negated) |
| h4-05 (text, EUS) | read from the document, 2026-10-15 | 1 sent | none: no code selected | withheld |
| h4-06 (scanned PDF, colonoscopy) | asked (OCR, page 1); answered 2026-10-27 | 2 sent | none: 45385 needs an extent | withheld |

**Bounds, all held:**
- provider runs +13 (bound 13), sent +12 (bound 12): 12 sent, plus h2-08's reuse;
- second reviews +0; no unknown, failed, reserved or sending run;
- jobs +46 (7 for each answered document, 4 for h4-05); decisions +1; reports +14; encounters +7;
- users, reference data and migrations +0;
- credits +0.707292.

Every document's draft TXT and CSV were downloaded and re-checked file by file, with 0 failures. The browser logged no
console error and the site returned no 5xx. **e084b793 was not touched:** still needs_clarification, last updated
2026-10-29, 1 run, 0 decisions. No stop condition fired.

## What is correct

- **The release does what it was for, live.** On h2-08 the contradicted date is no longer sent: it is asked, the question
  is true to the document, and the answer sends nothing new (here, a reuse).
- **Nothing was sent that the declaration did not allow.** Every request carries either no date, the document's own date
  (h4-05), or the declared answer. Duplicate protection reused an identical request live.
- **The install changed nothing it did not declare.** Every stored state was recomputed unchanged, every count held, and
  nothing was sent during the install. Co-tenants and app.quillmd.com were unchanged. The image's OS packages and OCR
  toolchain are byte-identical to installed's, and h4-06 was read by OCR on them.
- **The workflow end to end:**
  - upload of paste, Word, PDF, scanned PDF and text;
  - the date question and its answer (recovery);
  - reload;
  - a persisted, labelled agent decision (h4-04);
  - withheld reviewed exports with their blockers;
  - draft exports verified file by file;
  - the demo reviewer's own sign-in.

## What remains uncertain

- **The h4 author's expectations mostly fail, exactly as the offline reading predicted.** Both trees read 1 of the 6
  service dates (h4-05), with the same routing. On the others:
  - the date is asked rather than read;
  - the procedure status reads uncertain (h4-02 EGD and flexible sigmoidoscopy, h4-04 EGD), negated (h4-04 colonoscopy) or
    historical (h4-05 EUS, h4-06 colonoscopy) where the author says performed;
  - extents are not read, or read wrongly (h4-04 EGD "incomplete: stomach", where the author expects the duodenum).

  These are the extent, scope and status readers the narrow release did not touch. They hold codes for questions and do not
  send dates, but they are why no document reached a reviewed export.
- **h4-03's two dates** (header 10/06, ledger 10/08) are asked as missing, not named as a conflict. The date is still asked
  and nothing contradicted is sent; this is the known limit "gi3 other contradicted dates".
- **No reviewed download was reached in this walk.** Every document kept an open question or an undecided code, so each
  withheld the reviewed export, as declared. Releasing one needs a decision outside this declaration's walk (a stop), so it
  was not made. The reviewed TXT and CSV were last exercised live in round 2, on 90377ec6f413. This release changes report
  wording for its question, so the reviewed export at 80df1831 is unverified live.
- **The known limits of the narrow release** stand as listed in `ACCURACY-RESIDUALS.md`. Among them: other contradicted-date
  shapes are read as installed, and a member's save that leaves the question open sends one dateless request.
- **h3**, the second sealed set, could not be rebuilt after the host reboot of 2026-10-30, so no claim rests on it.

## Provider omissions (Corti), kept separate

- **h4-05 (EUS): no EUS code proposed**, where the author expects 43259. Every code proposed was an alternative from another
  family. This is the EUS omission seen on round 2's h2-09, and it is separate from our reader, which marked h4-05's EUS
  historical.
- **h4-02: no EGD code proposed**, where the author expects 43239 (EGD with biopsy) beside 45331 (flexible sigmoidoscopy with
  biopsy). Corti selected 45330 instead, which the author lists as not expected, because biopsies were taken. It still needs a
  clarification, and nobody decided it.
- From round 2: h2-10's ERCP stent exchange drew 43274 where the plan expects 43276.
- No candidate was promoted and no code was invented. Unsupported or alternative codes stayed as they came, undecided.

## Is a complete doctor-facing synthetic demo ready?

**Ready as a supervised workflow demonstration. Not ready as a demonstration of reliable GI coding.**
- **Shown live:**
  - the system asks rather than sends a contradicted date;
  - the reviewer's account works;
  - decisions are labelled and persist;
  - draft exports are exact;
  - nothing is sent twice.
- **A doctor would also see:**
  - most procedure reports end on a question;
  - this walk reached no reviewed export;
  - Corti omitted the EUS code again.
- **Still needed for a reliable-coding demo:**
  - the status, extent and scope readers, repaired under a "never worse than installed" guard;
  - a live reviewed export at this revision;
  - your own acceptance of the documents a doctor would see (class c).

## Open for the owner

- **P1, the rebuild's upload check (security; live today):** a crafted PDF can carry a hidden script past `pdf_inspect` and
  be served back as uploaded. It is not repaired, and it is outside this act. A guard could read the pypdf warnings that mark
  each dropped section.
- **The rebuild's next install ships pypdf 6.21.4** (PR #1449). Its declaration should judge the four crafted-file
  differences recorded in `docs/rebuild/pypdf-6.21.4.md`. One of them adds triggers to P1.
- **CPT Studio's pypdf move** is deferred to the next round with its reader repairs. Until then its non-required audit stays
  red and the service keeps the seven denial-of-service advisories, which its ingest limits contain.
- **A reviewed export at this revision** needs a separately declared live check: an approval or a confirmation that settles
  one walk encounter's codes.
- **The narrow release's recorded interpretations 53 to 61** (session-made) remain yours to overrule.
- **The demo's acceptance needs your eyeball (class c).** The draft TXT and CSV of the seven walk documents are the
  documents a doctor would see.

## Disclosure

- The declaration was refuted before the act by two read-only lenses, and an independent agent reproduced each finding. The
  first pass found 19 defects, two of them blocking:
  - h2-08's dated request would be a reuse;
  - an answered document makes 7 jobs, not 6.

  A delta pass found 15 more. One was in this session's own operator script: an env file it sources had redirected the
  pre-app dump to round 2's evidence directory. All were applied before the declaration was committed. The delta pass's own
  corrections were not refuted again.
- The narrow release's code froze on b5ddc4d32 after nine refutations. The decision named one; interpretation 53(e) records
  why the standing rule required more.

## Not claimed

- No accuracy percentage. Every expectation is an author's, provisional and not adjudicated.
- Install checks, test volume and browser checks are not coding accuracy.
- No reliable-coding claim, while known contradicted-date shapes and the reading limits above remain.
- No CPT licence, NCCI PTP agreement or BAA was entered. CPT edition, descriptors and NCCI PTP stay unverified
  (interpretations 1-3).
