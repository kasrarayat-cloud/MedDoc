# Deploy report — F1, the numbered-list fidelity fix — 2026-08-15

**Commit `efe1b4430219793a23015a11ceca5dfcda350ac0`** (PR #665, ruling #112,
RELAY F1).
**Declaration:** `docs/foundation/deploys/20260815-efe1b443.md` — written before
the merge commit existed, judged here without amendment.

> ⚠️ **The declaration file is NOT edited by this report.** Appending a
> judgement to the document being judged is how a comparison stops being
> falsifiable; the two live in separate files on purpose.

**Verdict: 25 of 25 declared quantities matched. No movement the declaration
does not name.**

---

## THE ROW THAT COULD HAVE GONE THE OTHER WAY

The declaration's whole point was a probe that could FAIL. A doctor's visit is
never a smoke target, so "did the fix ship" is answered structurally — by the
ABSENCE of the numbering-reference attachment from the built artifact.

⚠️ **The app image ships a BUILT Next bundle; the worker ships SOURCE.** They are
probed differently on purpose — a probe pointed at the wrong one returns 0 for
everything and reads exactly like a pass. (The GI session's two-zeroes lesson:
when a sweep answers 0 to a question whose true answer is 1, check the
instrument.)

| probe | declared BEFORE | measured AFTER | |
|---|---|---|---|
| app `_0slatfn._.js` — `plan-numbering` | 2 → **1** | **1** | ✅ |
| app `_0slatfn._.js` — `numbering:{reference:"plan-numbering",level:0}` | 1 → **0** | **0** | ✅ |
| app ssr chunk — `plan-numbering` | 2 → **1** | **1** | ✅ |
| app ssr chunk — the defect shape | 1 → **0** | **0** | ✅ |
| worker `src/lib/docx-generator.ts` — `plan-numbering` | 3 → **2** | **2** | ✅ |
| worker source — the defect line (was line 645) | 1 → **0** | **0** | ✅ |

**Traversal control held:** `grep -rl` found **2** chunks naming
`plan-numbering` both before and after. Chunk filenames are content-hashed, so
the probe re-derives them rather than reusing the pre-deploy names — a probe
keyed on a stale filename returns 0 because the file is gone, which is
indistinguishable from the fix having landed. A zero files-found would have been
a broken probe, not a clean result.

**Worker source grew 804 → 830 lines** — the corrected comments, consistent with
the diff and with `plan-numbering` dropping by exactly one occurrence rather
than to zero (the numbering config is KEPT, declared and inert).

### The cache-key bump, verified the same way

| | declared | measured |
|---|---|---|
| `visitdoc:v3` in the shipped bundle | present | **5** |
| `visitdoc:v2` in the shipped bundle | **0** | **0** |

Both occurrences moved together — the writer and `invalidateVisitFills`'s SCAN
pattern. Had only the writer moved, the scan would hunt `v2` keys while `v3`
keys accumulated, quietly breaking the one-entry-per-visit bound that exists
because **the cached value is PHI**.

---

## MUST CHANGE — all matched

| | before | after |
|---|---|---|
| `transcribe-md` image | `sha256:56b20e432234…` | **`sha256:bc4e06c609be…`** |
| `transcribe-md-worker` image | `sha256:69f5995ced43…` | **`sha256:b8f373321a21…`** |

## MUST NOT CHANGE — all matched

| quantity | declared | measured after |
|---|---|---|
| visits | 44 | **44** |
| signed | 26 | **26** |
| patients | 31 | **31** |
| templates | 9 | **9** |
| `audit_logs` | monotonic from 11445 | **11445** |
| migrations | 104 | **104** |
| `template_twin_source_artifacts` | 0 | **0** |
| `template_twin_compiled_versions` | 0 | **0** |
| `template_twin_fill_manifests` | 0 | **0** |
| `app /api/health` | 200 | **200** |
| co-tenant `app` | 307 | **307** |
| co-tenant `admin` | 404 | **404** |
| co-tenant `quillmd` | 200 | **200** |
| co-tenant `www` | 200 | **200** |
| co-tenant `pro` | 410 | **410** |

`transcribe-md`, `transcribe-md-worker` and `gotenberg` all `healthy` after the
settle. Standing checks re-run after the deploy: `assert-migrations-applied` 🟢
(104/104), `check-imaging-em-artifacts` 🟢 (0 of 17), `check-ingress-tls` 🟢
(every SNI, fresh handshake, negative control discriminating).

---

## ⚠️ WHAT THIS DEPLOY DID **NOT** DO, STATED SO IT IS NOT READ WIDER

- **It rewrote no stored bytes.** `soapFinal` is untouched on every row. What
  changed is what the RENDERER emits next time a visit is exported or previewed.
  The signed record's content was always the stored text — the export was the
  thing misreporting it.
- **The 7 signed multi-section visits were not migrated, edited or re-rendered.**
  Their next export will read correctly; nothing has been done to them in place,
  and nothing should be.
- **The PDF export leg (`…/export/pdf`) is byte-unchanged.** It runs
  `generateVisitPdf` (pdfkit), a separate builder this diff does not touch.
  Ruling #113 / RELAY F3 owns its convergence.
- **No behavioural export walk was performed on production.** The document-bytes
  proof for a real note belongs on QA against a byte-identical build, and it was
  not run tonight. **That step is UNVERIFIED and is named as such** rather than
  implied by a green structural probe — the probe proves the shipped code, not a
  rendered document.

## AFFECTED POPULATION — measured before the deploy, unchanged by it

| | |
|---|---|
| visits containing at least one numbered line | **18** |
| of those, SIGNED | **10** |
| visits with TWO OR MORE numbered sections | **12** |
| **of those 12, SIGNED** | **7** |
| distinct clinicians across the 12 | **2** |

The matcher was controlled in both directions before these were believed: the
same regex form finds `## ` headings in all 42 non-null `soapFinal` rows (the
traversal reaches the column), and an impossible token returns 0 (it
discriminates).

## ROLLBACK

    meddoc-pro-transcribe-md:pre-numbering-20260815          (sha256:56b20e432234…)
    meddoc-pro-transcribe-md-worker:pre-numbering-20260815   (sha256:69f5995ced43…)

Both cut against the RUNNING ids and verified equal to them before the deploy
began. Reverting the commit is equally sufficient — no migration, no data change.
⚠️ A rollback **re-introduces the defect** (#112's recorded reversal path).
