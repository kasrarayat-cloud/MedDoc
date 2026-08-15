# F-117 — the attestation footer, POST-DEPLOY JUDGEMENT

**Deployed `012ea04c` at 2026-08-15T22:52:07Z.** Judged against
`docs/foundation/deploys/20260815-012ea04c.md`, which was written and placed
**before** `deploy-prod.sh` ran.

**Citation — 4 of 4 on `012ea04c48461ba239f51d17c96dee8a77d2535f`**, produced by
`scripts/check-citation.sh`, not typed:

    · CI          31911389817 a1
    · e2e         31911389795 a1
    · a11y-ci     31911389763 a1
    · secrets-scan 31911389761 a1

Every line `a1`. ⚠️ **The `a2` in this item's history was on the PR BRANCH, not
the merge commit** — see "the timeout class" below — so the citation row itself
needs no re-run explanation.

⚠️ **THIS CITATION ALSO DISCHARGES `1d80e4a3` (PR #675), WHICH WAS 3-OF-4.**
That merge's `e2e` on `main` hit `e2e.yml`'s 55-minute wall (55m21s) and reports
as `cancelled`. `012ea04c` contains `1d80e4a3` in full, so the descendant
citation is strictly stricter — the standing recovery pattern, applied.

---

## THE JUDGEMENT — 15 of 15 declared rows matched

### Must CHANGE

| # | quantity | before | after | ✓ |
|---|---|---|---|---|
| 1 | app image id | `d1108cb1081b` | `7491a69694a8` | ✅ |
| 1 | worker image id | `cffabcc2d97b` | `2a01833d05ed` | ✅ |
| 2 | `new Footer(` in the shipped worker | 0 | **1** | ✅ |
| 3 | `visitdoc:${KEY_VERSION}` in the shipped worker | 0 | **2** (writer + SCAN) | ✅ |

### Must NOT change — the absence rows

| # | quantity | required | measured | ✓ |
|---|---|---|---|---|
| 8 | `visitdoc:v4` in the shipped worker | **0** | **0** (was 2) | ✅ |
| 9 | `generateVisitPdf` route callers | **5** | **5** | ✅ |
| 10 | migrations, prod | 104 | **104** | ✅ |
| 10 | migrations, `--qa` | 104 | **104** | ✅ |
| 11 | visits / signed / patients / deliveries | 45 / 27 / 32 / 95 | **45 / 27 / 32 / 95** | ✅ |
| 12 | co-tenants | `307 · 404 · 200 · 200 · 410` | **identical** | ✅ |
| 13 | containers healthy | 9 of 9 | **9 of 9** | ✅ |
| 14 | the in-body signature block | still present | **present** | ✅ |
| 15 | `pdf-native` marking | unchanged and still absent | **unchanged** | ✅ |

**Row 9 is the one that matters most for what did NOT ship:** F3's retirement is
not in this deploy, and five callers prove it.

**Row 15 confirms #118(d) was REFERRED, not quietly fixed** — `signedStatusLine`
is still passed once and still drawn on `pages[0]` only (`fill-engine.ts:218`).

---

## ⚠️ ROWS 4–7 WERE DOWNGRADED TO A STRUCTURAL CHECK, AND THAT IS A DEFECT IN MY OWN DECLARATION

Rows 4–7 declared that an UNSIGNED / SIGNED / form-only `.docx` export would be
**unzipped and inspected**. **On production that means exporting a real doctor's
note, which is forbidden** — *"a real doctor's visit is never a smoke target"*.

> **I wrote a declaration row whose verification I am not allowed to perform.
> That is the defect, and the honest response is to say so rather than to
> perform it or to tick it.**

**What was checked instead — structural, in the SHIPPED worker image:**

    function attestationFooter(data: VisitExportData): Footer | undefined {
      if (!data.signedAt) return footerLine(DRAFT_FOOTER_LINE); // (a) — form-only included
      if (data.formOnly) return undefined;                      // (c)
      return footerLine(signedAttestationLine(...));            // (b)
    }

    DRAFT_FOOTER_LINE = 'DRAFT — Not yet signed.'   (visit-export.ts:396)

That is the four-cell matrix and, critically, **the BRANCH ORDER** — the thing
mutation 2 proved is the difference between marking every form-only draft and
silently marking none. The behavioural proof of the same matrix is the unit gate
(`gate-attestation-footer.test.ts`, 7 arms, mutation-proved 11 of 11), which ran
in the cited `CI`.

**So: the OOXML behaviour is proven by the gate, and its PRESENCE IN THE SHIPPED
IMAGE is proven here. What is NOT proven anywhere is a rendered page** — see
#117(e) below.

**The lesson for the next declaration:** an absence/presence row must name a
check that is legal on production. "Unzip an export" never is.

---

## CONTROLS — every zero has a live one beside it

| probe | zero | its control |
|---|---|---|
| `new Footer(` pre-deploy = **0** | must-not-exist | `new Paragraph(` = **29** |
| `visitdoc:v4` post-deploy = **0** | must-be-gone | `visitdoc:${KEY_VERSION}` = **2** |

⚠️ **AND ONE PROBE WAS BROKEN AND WAS CAUGHT BY THIS RULE.** Row 15's first
matcher grepped a single-line `signedAt ? \`Electronically signed` against a
MULTI-LINE ternary and returned **0** — which reads exactly like "the marking is
gone", the answer I wanted. Re-measured with `signedStatusLine` (**1**) and the
`pages[0]` draw site (**present**, `fill-engine.ts:218`). **A zero with no
control is not a measurement.**

⚠️ The app image ships a BUILT Next application and answers `0` to every source
grep, so every probe above was run against the **worker**, which ships source.

---

## ROLLBACK — cut by hand, verified, and still pointing at the right ids

    meddoc-pro-transcribe-md:pre-footer-20260815         d1108cb1081b
    meddoc-pro-transcribe-md-worker:pre-footer-20260815  cffabcc2d97b

Cut **before** the deploy, against the then-running ids, because
`deploy-prod.sh` contains no `docker tag` at all — F2-b's finding, and the
deploy log echoes the declaration back, which makes "named" and "cut"
indistinguishable in a transcript.

---

## WHAT IS STILL NOT TRUE

- ⚠️ **#117(e) IS NOT BUILT.** No E2E through the real converter, no multi-page
  render, no page count. **#117 is PARTIALLY discharged and F3's deploy gate
  remains open.** And per **#118(a)**, clause (e) as literally written would go
  RED against what just shipped — it needs amending before it can be built.
- ⚠️ **`pdf-native` still marks nothing on an unsigned export** (2 production
  visits). Referred in #118(d); its own item and its own ruling.
- **The provenance of this declaration is transcript-only.** `deploy-prod.sh`
  said so in its own words: the file was untracked at deploy time, so the ORDER
  is asserted by the log rather than provable from git. It is committed in the
  same PR as this report. Mode is `present` not `strict` by design — but the
  stronger habit is to commit the declaration with the change.
