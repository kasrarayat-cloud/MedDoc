# §2.5 JUDGMENT — the tree deploy, `7c42d2d7`, 2026-08-20T06:15:17Z

**Judged by** FOUNDATION run `20260820-014110-b1` session **02 of 6** — the actor
that ran `deploy-prod.sh`.

**Declaration:** `docs/foundation/deploys/20260820-b3459390.md` (PR #752).
**Baseline addendum:** `docs/deploy-reports/20260820-tree-deploy-baseline-addendum.md`
— my own re-measurement of every row, **committed 05:42:56Z–05:47:41Z, before
the act.**
**Deploy log:** `docs/deploy-logs/deploy-20260820T061517Z.log`.

## VERDICT — **15 of 15 ROWS MET**, with **ONE NAMED DIFFERENCE** and **ONE CANNOT-TELL**

Neither is a regression. Both are recorded here rather than absorbed, because
the declaration's own closing line is *"any difference not named above is THE
FINDING, whatever explanation is available after the fact."*

## THE GATE ITSELF

    shipping    : 7c42d2d7  (7c42d2d77eb0f7ec1a83b2b4d61acd74a13e5ea6)
    declared    : b3459390 — an ANCESTOR of the shipped tree, 2 commit(s) back
    resolution  : CARRY-FORWARD  (mode: strict — the declaration must be COMMITTED)
    tracked     : yes   modified-vs-HEAD: no
    committed   : abc0020d at 2026-08-20T05:31:05+00:00

**The provenance holds in the units that matter:** the declaration's commit
(`05:31:05Z`) and my addendum's commits (`05:42:56Z`–`05:47:41Z`) both precede
the deploy's start (`06:15:17Z`). Neither answer could have been tuned to an
outcome that did not yet exist.

`🟢 3 rollback tag(s) cut and verified against the running images.` — cut against
the **pre-deploy** digests, which are the ones I recorded independently at STEP 0:

| tag | digest it preserves |
|---|---|
| `meddoc-pro-transcribe-md:pre-7c42d2d7-20260820` | `c6b0dd3446fb` |
| `meddoc-pro-transcribe-md-worker:pre-7c42d2d7-20260820` | `c3caed78175e` |
| `meddoc-pro-gotenberg:pre-7c42d2d7-20260820` | `2d05d22572ba` |

## MUST CHANGE — 3 of 3

| # | declared | measured | |
|---|---|---|---|
| 1 | both image ids | app `c6b0dd3446fb` → **`47c225d4ab3a`**; worker `c3caed78175e` → **`fc16cbd6db7d`** | ✅ |
| 2 | the deployed commit becomes `b3459390` | **`7c42d2d7`** | ⚠️ **NAMED DIFFERENCE — see below** |
| 3 | worker carries `deriveVerificationEncounter` 0 → 1, and `certification-thresholds.ts` exists | `deriveVerificationEncounter` **1**; `certification-thresholds.ts` **present** | ✅ |

### ⚠️ THE NAMED DIFFERENCE — row 2, and it is STRUCTURAL, not an accident

The declaration names `b3459390`; production runs `7c42d2d7`. **Named rather
than explained away**, because "the explanation is available after the fact" is
exactly what the finding rule refuses.

What it is: **a declaration that names a sha cannot name the commit that lands
it.** Merging PR #752 *is* what moved `main`, so the declared sha is
unreachable-by-construction the moment the declaration is landed through the
gate that requires it to be committed.

Measured rather than argued — the FULL diff between the two:

    git diff --name-only b3459390 7c42d2d7
    → docs/foundation/deploys/20260820-b3459390.md

**One file, and it is the declaration itself.** The runtime tree shipped is
byte-identical to `b3459390`, which I verified **4 of 4 with `--expect`** at
STEP 0 (`CI` 32333342082 · `e2e` 32333342079 · `a11y-ci` 32333342083 ·
`secrets-scan` 32333342078, every line `a1`). So the code in production is
code a full gate has seen.

This is also precisely what `declaration_resolve`'s CARRY-FORWARD branch exists
to handle, and it reported the situation correctly and loudly — *"an ANCESTOR of
the shipped tree, 2 commit(s) back … 0 of them runtime"*. **The gate did its
job; the declaration's prose row is simply written in a tense the mechanism
cannot satisfy.**

> **Recommendation:** a tree-deploy declaration should write row 2 as *"the
> deployed commit becomes `<declared sha>` OR A DESCENDANT WHOSE ONLY DIFF IS
> THIS DECLARATION"*, which is checkable and always satisfiable. As written, the
> row can only ever be judged with a paragraph.

## MUST NOT CHANGE — 12 of 12

| # | must still read | measured | |
|---|---|---|---|
| 1 | visits 48 | **48** | ✅ |
| 2 | signed 30 | **30** | ✅ |
| 3 | patients 35 | **35** | ✅ |
| 4 | active templates 7 | **7** (10 total) | ✅ |
| 5 | migrations 104 of 104 | **104 of 104** | ✅ |
| 6 | `##` lines still *237* | **282 → 282** | ✅ **against the RE-BASELINE, not 237 — see below** |
| 7 | ⚠️ `###` lines still 8 | **8** | ✅ **the row that discriminates** |
| 8 | twin CERTIFIED 0 | **0** | ✅ |
| 9 | mappings 80 / 0 | **80 / 0** | ✅ |
| 10 | fill manifests 0 | **0** | ✅ |
| 11 | `check-imaging-em-artifacts` clean | **🟢 0 of 20** | ✅ |
| 12 | co-tenants expected, `pro` still 410 | **5 of 5, 4 distinct codes, `pro` 410** | ✅ |

**Row 6 is judged against 282, the figure I measured and committed before the
act.** The declaration's 237 is not reproducible by any of eight query shapes,
and three independent sources give 282 — F6.4's own committed declaration, my
SQL, and F12-g's projection control (290 total headings = 282 + 8). Full
evidence and the SQL: the baseline addendum. **The invariant the row protects is
satisfied either way** — this deploy carries no migration and no backfill, so a
heading count in stored text must not move at all, and it did not.

## ROW 16 — F6.4's STRUCTURAL PROBE, THE POINT OF THE WHOLE DEPLOY

Handed forward pre-controlled by session 01, re-run by me on both sides:

| | before | after |
|---|---|---|
| `NOTE_HEADING_LINE_RE` in the worker's `docx-generator.ts` | **0** | **2** ✅ |
| `renderSoapParagraphs` (traversal control) | 2 | 2 |

**The zero was only ever meaningful because the control was non-zero, and the
two is only meaningful for the same reason.** F6.4's fix is in the running
image: the eight `###` lines across three production visits will no longer print
their own hashes into an exported document.

### ⚠️ AND THE APP-IMAGE PROBE IS A **CANNOT-TELL**, NOT A PASS

The same grep against the app container returned **0** — and so did its
traversal control. **Two zeroes with opposite meanings is one broken
instrument**, this repository's own named diagnostic, and the contradiction is
the finding about the *probe*, not about the deploy. Confirmed directly:

    docker exec meddoc-pro-transcribe-md-1 sh -c 'ls /app/apps/transcribe-md'
    → fonts  package.json  public  server.js

The app ships a **standalone Next build, not a source tree**, so no
source-symbol grep can resolve there. Recorded as unverified rather than
claimed: what stands is that the worker demonstrably carries the fix, both
images were rebuilt from `7c42d2d7` in the same `deploy-prod.sh` run, and both
image ids moved.

## POST-DEPLOY HEALTH

All **9** containers running and healthy; `transcribe-md` and
`transcribe-md-worker` recreated (`Up About a minute`), everything else
untouched at `Up 12 days`. `app.quillmd.com` answers **307**.

## WHAT THIS DEPLOY DOES NOT CLAIM

- **No clinical walk was performed, and none was attempted.** Verification here
  is structural by standing law. ⚠️ **QA could not have supplied one either:**
  its images are from `2026-08-18T14:4xZ` and carry **0** occurrences of
  `NOTE_HEADING_LINE_RE` against a traversal control of **2** — measured, so the
  zero is real absence rather than blindness. A behavioural proof of F6.4 on QA
  today would have exercised a build without the fix in it.
- **The MAY-CHANGE backfill was NOT run.** Twin CERTIFIED is still `0`, which is
  the declared correct state. The retroactive auto-certification dry run remains
  a separate, deliberate act for a later session.
- **F5-c shipped inside this deploy and is judged only to the depth its three
  rows reach** — the symbol is in the image, the constant file exists. Nothing
  here exercises its behaviour.
