# Prod — suggestion lane deleted, verifier audit-only, preview framed (2026-07-27)

Two deploys. Rollbacks `:pre-auditonly-20260727` and `:pre-lanedelete-20260727`.

| | commit | app | worker |
|---|---|---|---|
| checkpoint (backend) | `41ec3a44` | `8b72fe36cbcb` | `b76a991e84a1` |
| lane delete + preview | `0e5257ce` → `4719eef70099` | `4719eef70099` | `09ea62317b44` |

Migration `20260727190000_anchor_flags_recorded` applied; enum value live.

## Root cause

The six-FP-class provenance work shipped at 17:42 and a fresh ultrasound visit
at 18:22 still carried **ten** flags. Both true: `buildSectionPolicy` reads the
ACTIVE TEMPLATE's declared sections, and `provenance` is an OPTIONAL field only
the BUILT-IN templates set.

The production form that failed has eight sections, `provenance` on **none**,
`defaultText` on **all**, and it DECLARES `PROCEDURES / E&M` and
`PATIENT SUMMARY`. So:

- `s.provenance ?? 'dictation'` marked TECHNIQUE and IMPRESSION verifiable →
  2 flags.
- `if (!byLabel.has(label))` let that declaration beat `PIPELINE_SECTION_POLICY`
  → the cross-step sections were judged too → 8 flags, 7 of them
  patient-summary paraphrase.

The smoke that "proved" the fix used a doctor with no custom template, fell back
to the built-in ultrasound template — the one carrying the declarations — and
measured the single path that was never broken.

## Fixes

1. `PIPELINE_SECTION_POLICY` wins **unconditionally**. No template can claim
   authorship of content a later step writes.
2. `inferProvenance` covers protocol-by-nature sections (technique, comparison)
   for templates that never declared any.
3. Template boilerplate is exempt **per line**, not per section — the fixed
   prose a form supplies becomes mandated lines. Section-level was tried first
   and would have exempted FINDINGS, where the measurements live; caught by
   reading the real template before deploying, and pinned by a test.
4. Verifier is **audit-only**: `suggestedClaims` actively cleared, the draft
   comes from a new `fullBody` (all lines, anchors stripped, nothing demoted
   away), findings recorded as `ANCHOR_FLAGS_RECORDED`.

## E/M relocation

The `⋯ details` collapsible housed `em-stale-badge` and the lazy re-score — the
only control that clears the E/M gate. Deleting it wholesale would have left the
sign route refusing for a reason folded behind a disclosure.

**New home:** an inline gate card in the stack next to the signature —
`review-doc-em-stale-gate`, carrying `em-stale-badge` and
`review-doc-em-rescore`. The sign bar names it too. Then the collapsible was
deleted; its billing / codes / dictation panels render inline, with
`data-chat-target="codes"` preserved so "show billing" still resolves.

## Prod evidence

**Custom-template ultrasound** (`isSystemDefault=f` — the regressed path):

| | before (18:22) | after |
|---|---|---|
| suggested claims | 10 | **0** (cleared) |
| sections evacuated | TECHNIQUE, PROCEDURES/E&M | **0** |
| DOM suggestion nodes | card stack | **0** across 5 selectors |
| `⋯ details` toggle | present | **0** |
| letter | flooded | all 6 sections incl. PATIENT SUMMARY |

Audit sample — counts only, no note text:
```json
{"visitId":"cms3msa3l…","flagCount":2,
 "categories":{"no_anchor":1,"not_entailed":1},"anchored":12,"demoted":2}
```

**Preview framing** — page capped at `--qm-page-w: 820px`, one number both
formats obey:

| viewport | PDF paper | Word paper | gutter | side-scroll |
|---|---|---|---|---|
| 1024 | 584 (column-limited) | — | 41px | none |
| 1440 | **820** | **820** | 131px | none |
| 1920 | **820** | **820** | 371px | none |

0px parity, where PDF previously stretched to 1082 / 1562. Canvas
`rgb(8,9,10)` = #08090a, `padding-top: 0` (dead band gone), one toolbar row.

**Three gates:**

- **E/M — verified end-to-end on a primary-care visit.** Edit → `emStale=true`
  with baseline 99214 → inline gate + badge + "Re-check the documentation level
  above" → re-check (`EM_RESCORED` audit row) → flag cleared → **SIGNED**.
  Not verifiable on imaging: `emNotApplicable` is true for ultrasound by design.
- **VIEWED_VISIT** — 13 rows across the walk.
- **critical-Rx typed override — NOT exercised live.** Neither smoke visit drew
  a critical warning, so the override path was not walked on prod. It is covered
  by unit tests and by the structural fact that the sign route references
  `suggestedClaims` zero times, but this report does not claim a live pass.

## QA walker — DID NOT RUN

`sweep-visit-page.mjs` fails at its own login stage against prod
(`page.waitForURL` timeout, no `LOGIN_SUCCESS`/`LOGIN_FAILED` audit row — the
submit never reached the server). Not a product fault: the smoke account has
`mfaEnabled=false`, a verified email and the TRANSCRIBE_MD product, and the same
credentials log in through a browser seconds earlier. The walker is a QA-stack
tool whose default user and fixtures live there.

Recorded as unverified rather than skipped quietly. The same surface was
asserted directly (DOM counts across five suggestion selectors, the collapsible,
the gate testids, the panels, the section list) — narrower than a walker sweep,
and named as such.

## Cleaned to baseline

visits 0 / patients 0 / templates 0; user, practice and **158 audit rows**
preserved. Downloaded signed PDF removed from the box.

## Observations

- A prior session's real patient export (`visit-eleanor-whitfield-*.pdf/.docx`)
  is sitting in `.playwright-mcp/` on the box. Gitignored (line 117) and not
  tracked, so no PHI reached the repo — but it is a filled clinical document on
  disk and worth a deliberate clean-up decision.
- The gap between the visit title row and the chat card is unchanged. The dead
  band this work removed is the one **above the page**, inside the document
  frame; the header spacing is a different surface.

---

# Close-out pass (2026-07-27, later)

## 1 · Stray exports — destroyed

Posture applied: a filled clinical export outside a sanctioned path is PHI,
real or synthetic. `shred -u -n 3 -z` throughout. Paths only.

- `.playwright-mcp/` — the whole scratch dir, **142 files**. Two named visit
  exports AND the `page-*.yml` accessibility snapshots, which carry the rendered
  note text of every page walked.
- Repo root (root-owned, needed the root-via-docker path): `twin-native-output.docx`,
  `twin-prod-visit.docx`, `twin-real-visit.docx`, `diag-l4-note.txt`, `diag-facts.json`
- `/tmp`: `qa-signed-preview.pdf`, `scratch-docx-mjCQ2a/v.docx`, `scratch-docx-lnzu0G/v.docx`
- Staging evidence + a worktree `template-twin-staging-output.docx`
- `~/.local/share/Trash` — purged, **3 009 files**

**Two findings.** A filled twin export was in Trash *after* its original had
been cleaned — deleting is not destroying, and a sweep that skips Trash reports
clean while the document is still on disk. And `shred` fails on root-owned files
with a "Permission denied" line among the successes; three artifacts survived
the first pass that way.

**Tracked, therefore still in history:**
`docs/qa-reports/twin-real-visit-20260726.docx` — a filled document committed in
`9d65cbfa`, which reached `main`. Removed from the tree; **the blob remains
reachable in git history.** Clearing it needs a deliberate rewrite decision, not
a close-out `git rm`. Open.

Checklist added to AGENTS.md, naming what must SURVIVE a sweep (the WM IOV blank
form, `colon_blank_answers.pdf`, the e2e fixtures) as carefully as what must not.

## 2 · Critical-Rx typed override — PASSED live

Floor: warfarin (current) + NSAID (new) → CRITICAL, deterministic.

```
22:04:47  RX_DRUG_PAIR_INTERACTION     ← floor fired, 2 critical warnings
          sign disabled · "Resolve the prescription warning above"
22:06:00  RX_OVERRIDE_RECORDED         ← typed reason, warning 1
22:06:06  RX_OVERRIDE_RECORDED         ← typed reason, warning 2
22:06:33  VISIT_SIGNED
```

One audit row per warning, never a bulk row. "Confirm override" stays disabled
until a reason is typed. All three gates are now verified live post-rewrite.

## 3 · QA walker — PASSED (on QA, deliberately not prod)

Two causes, and the first made the earlier report wrong:

1. `APP_BASE` reads **`QA_AUDITOR_APP_URL`** (default `localhost:9020`), not the
   `QA_AUDITOR_BASE_URL` that was being set. The browser was pointed at the QA
   stack the whole time — it had **never talked to prod**.
2. The login is `<form action={formAction}>`, a React 19 server action, so it
   soft-navigates and no `load` event fires. `waitForURL` (default
   `waitUntil:'load'`) sat for its full timeout while the login had SUCCEEDED.
   Replaced with a pathname poll; failures now name the URL and the env vars.

**Not run against prod, deliberately.** The walker asserts DB deltas per click
and carries an explicit prod-refusal guard. That guard is right, and
`QA_AUDITOR_ALLOW_PROD` is not something to reach for to close a checklist item.
Ran on the QA stack, which was already serving the identical `:latest` image —
verified by grepping the rewrite's markers out of its running bundle first.

Result: `ok=true`, 34 elements, 16 clicks. Walked the format toggle, three
section editors, the Rx cards and Sign & Download — and enumerated **zero**
suggestion cards.

## 4 · Disk — 85% → 79%

| | before | after |
|---|---|---|
| used | 85% | **79%** |
| avail | 46 G | **62 G** |
| build cache | 11.97 GB | 0 B |
| rollback tags | 52 | 5 |

Untagged 48 superseded rollback tags (keepers and co-tenants verified absent
from the list first), pruned builder cache and the stale `visit-doc` /
`doc-preview` / `review-doc` e2e build tags. Kept `:pre-auditonly-20260727`,
`:pre-lanedelete-20260727` and everything newer. `backups/` untouched.

**≤75% not reached, and not reachable without breaking the rules.** What remains
is co-tenant: 50 `voiceassistmain-agent:git-*` images plus `openclaw:local`,
which are explicitly off-limits. QuillMD's own footprint is now close to its
floor — the remaining "reclaimable" figure Docker reports is mostly those
co-tenant images plus the four rollback tags being kept on purpose.

Prod untouched throughout: no container restarted this pass, 0 restarts,
0 error/fatal lines, co-tenants 307/200/200/404 and their containers healthy.
