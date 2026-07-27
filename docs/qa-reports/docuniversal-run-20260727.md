# Every visit gets a document — the run, after an unclean host reset

**Date:** 2026-07-27 · **Branch:** `fix/twin-visit-export-harness`
**Recovered from:** hard reset at 2026-07-27T00:55:33Z, box back at 01:11:51Z

---

## 1. The crash, and what it cost

The host went down **uncleanly** at **00:55:33 UTC** and came back **16 minutes
later** at 01:11:51.

What says so:

| Evidence | Reading |
|---|---|
| Previous boot's journal ends mid-stream at 00:55:33 | No shutdown sequence was ever written |
| No `shutdown` record in `last -x`; prior sessions end in `crash` | Not a graceful reboot |
| No `oom-kill` / `killed process` / panic in that boot's journal | Not an in-guest OOM |
| 16-minute gap before boot; every co-tenant (leathererp, drhooman, voiceassist) died together | A host/hypervisor-level reset, not anything QuillMD did |
| RAM at reset: no pressure recorded. Disk 87%, not full | Neither resource was the cause |

**It was not our workload.** No OOM, no disk-full, no runaway process. The
guest was reset from underneath. That is not something the run could have
avoided, and nothing about it argues against continuing.

**What was lost:** only verification work, no code. The last source edit landed
at 00:16:55 and the flag-OFF image finished building at 00:49 — the crash
caught the run *between building the rollback image and driving it*.

**What survived:** the entire code change, uncommitted in the working tree, plus
three screenshots. Committed as WIP `6947640` before continuing.

**The trap in what survived:** the three screenshots are timestamped **23:37**,
and every fix in the tree landed **23:46–00:16**. They are the *before* pictures.
`du-word-toggle.png` shows both bugs the later edits fixed. Anyone reading that
directory as evidence of a working feature would have been reading the bug.

### Two unrelated things the reset exposed
- **A stale `@reboot` cron.** `scripts/h8-post-reboot.sh` was installed for
  Phase 5.2 as "one-shot, self-removes". It did not. It fired again and appended
  a fourth snapshot to `docs/reboot-test-reports/h8-reboot-20260503T040001Z.md`.
  Reverted; it will dirty the tree on every future boot. Not fixed — out of scope.
- **`openclaw-gateway.service`** (another tenant) is in a permanent crash loop,
  `MODULE_NOT_FOUND`, **restart counter 79269**. Named only because it fills the
  journal.

---

## 2. Prod, first

Checked before any feature work.

| | |
|---|---|
| Containers | **10/10 healthy** — all auto-restarted after boot |
| `/api/health` | `{"status":"healthy"}` · postgres 10 ms · redis 3 ms · minio 5 ms |
| Through Caddy | `GET /` **200** |
| Co-tenants | app 307 · pro 200 · admin 404 · quillmd.com 200 · leathererp 200 |
| Data | 20 visits / 193 users intact |

**The QA stack did not survive** — 5 of 6 containers `Exited (255)`; only the
Gotenberg sidecar had a policy that restarted it. Brought back up, 6/6, healthy.

---

## 3. Phase 0 — the answer, in plain words

The question was why kasra's visits fell to a wall of cards instead of a
document. The answer is bigger than kasra.

`previewVisitDocumentAction` would only produce a document for a visit that had
**a bound note template** *and* **a compiled Template-Twin row** *and* that row
**CERTIFIED**. Production, queried read-only:

```
template_twin_compiled_versions:  0 rows
transcribe_visits:               20 rows, 20 with a note
  bound to a template:            4
  with a CERTIFIED twin:          0        ← the gate
```

**Every single production visit missed.** All 20, for both doctors, returned
`not_template_visit`. The document surface shipped, was flagged ON, and was
reachable by nobody. `not_certified` was not even reachable — you need a compiled
row to be told it isn't certified, and there are none.

Kasra specifically has **one** template — *"Venous Duplex Ultrasound Note"*,
v1, active — with **no compiled row at all**. That is not a failure; it is the
note-format flow working as designed. It learns a **format** from a *note*.
There is no uploaded **form** behind it, so there is nothing to compile a twin
from and nothing to certify. 17 of his 20 visits carry no template binding at all.

So the honest framing: this was never "kasra's template is broken". It is that
**the document view was built for a case that essentially does not exist yet**,
while the case that describes every real doctor — taught us a format, never
uploaded a form — was routed to the old surface by design.

---

## 4. What the change does

A note and a practice are now enough. No certified twin required.

- **The styled export becomes the document.** Same pipeline as the native path —
  DOCX to the converter, PDF back, drawn page by page — so both surfaces are one
  surface. The bytes are the ones the doctor would download: what they read is
  what they sign.
- **It says whose page it is.** A styled document is captioned *"QuillMD's
  layout — upload your own blank form in Settings › My Note Format and this
  becomes your page."* It never calls our layout "your form".
- **PDF / Word toggle.** Same bytes, different engine, so a doctor can see the
  file as Word will open it.
- **The SIGNED branch moved above everything that could re-derive.** It sat
  below the template lookup, so a doctor deleting a note template — which nulls
  every visit's binding and cascades the compiled row away — sent their
  already-**signed** visits down the styled path and served them a freshly
  re-derived document, cached. The stored bytes were still there; nothing asked
  for them.
- **`status` added to the select.** Prisma is untyped here, so the guard reading
  it saw `undefined` and silently declined every visit. **Fourth** time this
  class has bitten; a source-grep test now pins it across four actions.
- **The fill cache keys on the rendering variant.** Without it, a styled entry
  written before certification was served to the twin path afterwards — the
  doctor certified their own form and kept seeing ours for the rest of the TTL.
- **Artifacts killed.** A verifier-demoted claim quoted from a measurements
  table read as `| GSV at the Knee | 3.4 | 1.8 |`. It now reads
  *"Right Leg — GSV at the Knee: diameter 3.4 mm, reflux time 1.8 seconds"* —
  the doctor's own column names, the laterality from the table's caption, and a
  refusal to guess when the row appears in more than one table. The
  `_[All AI-drafted…]_` placeholder is substituted, never silently dropped.

---

## 5. What this run found that the crashed one had not

### The screen-reader block still had raw markup
The document draws to a canvas, so the DOM copy of the note **is** the reading
order a screen reader uses. The suggestion cards were checked for pipes; that
block was not. It read:

```
DIAMETER AND REFLUX TIME — Right Leg | Segment | DIAMETER (mm) | REFLUX TIME (seconds) | Right Leg — GSV at the SFJ: diameter 6.2 mm…
```

Every **data** row had become a sentence. The **header** row had not — and it is
the one line `claimProse` structurally cannot rewrite, because it rewrites a row
by reading that table's header and a header has no header of its own. So a blind
doctor was the only person still being shown markup, on the accessible path
nobody looks at.

Fixed by dropping the header row along with its alignment rule. Nothing is lost:
every data row already carries its own column names. `spokenBody` was extracted
to `src/lib/spoken-body.ts` so it can be unit-tested as the pure function it is
(importing the view pulls in next-auth and the whole client tree). Pinned by 8
unit tests **and** an E2E assertion on the real rendered block.

### A config file promising the opposite of what ships
`config/visit-doc-page.ts` still read *"NON-TEMPLATE VISITS ARE UNTOUCHED …
the styled note-as-page is the correct surface and stays exactly as it is."*
In this repo those headers are the contract. Rewritten to say what is now true,
including why the old sentence was wrong about its own consequences.

---

## 6. Verification

| Check | Result |
|---|---|
| `tsc --noEmit` | **clean** |
| Vitest | **2496 passed**, 4 skipped, 207 files |
| `spoken-body` unit | **8/8** |
| ESLint, changed files only | **clean** |
| ESLint, repo-wide | 50 errors — **all pre-existing**, none in any file this change touches (eval scripts, older components, template-twin tests) |
| E2E `visit-document` + `review-document` | **21/21 passed** |
| Gates inlined in the shipped bundle | `NEXT_PUBLIC_VISIT_DOC_PAGE` / `REVIEW_DOC_VIEW` / `DOC_PREVIEW` / `CHAT_EDITOR` → **0 surviving runtime reads** |

### The two fixes that had no evidence, now driven in a real browser

| | Before (23:37 shot) | After (verified) |
|---|---|---|
| Word branch: toggle | absent — a **one-way trapdoor** | present, `aria-pressed` correct, returns to PDF |
| Word branch: caption | *"Your form, filled so far"* on **QuillMD's own layout** | *"QuillMD's layout. Upload your own blank form…"* |

Negative control: a **certified-template** visit still reads
`this visit, on your form — page 1 of 3` on every page and shows **no** styled
banner. The styled visit reads `this visit — page 1 of 2`. The honesty fix
discriminates correctly in both directions.

---

<!-- SECTIONS 7 (audit) AND 8 (promotion) APPENDED BELOW AFTER THEY COMPLETE -->
