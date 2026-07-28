# Deploy — note-format live sample-note preview (`feat/note-format-live-preview`) → prod

**When:** 2026-06-10 ~06:48 UTC
**What:** The deferred 2b fast-follow — on the note-format review screen, after a doctor parses their
uploaded format, generate + show a SAMPLE SOAP note rendered IN THEIR FORMAT (from a fixed synthetic
demo visit) so they preview real output before activating.
**Result:** ✅ Deployed + verified in prod (real-model sample renders in-format, labelled synthetic, no
PHI, activate intact). No rollback. Worker + co-tenants untouched.

Commit: `b36cb55` on `feat/note-format-live-preview`. Image: `a244dc1bc918` (`:latest`).

---

## Approach (generation + caching)
- **Reuse, don't reimplement, don't persist.** A new `'use server'` action `previewNoteTemplateAction`
  reuses the L4 primitives — `buildSoapSystemPrompt` + `buildSoapUserPrompt` (immutable safety preamble +
  confirm-not-fabricate, sourced from the system default, un-weakenable by a custom template) +
  `modelClient.completeText` + `validateSoapStructure` — against a FIXED synthetic transcript, with
  `visitId: null`. It does NOT call the L3–L6 layer wrappers (they persist to a visit row). Same
  `normalizeReviewedTemplate` + `applyPhiGate` as the save path.
- **No visit, no PHI.** The only input is the hardcoded synthetic encounter (generic T2DM/HTN follow-up,
  `worker/note-templates/sample-preview-transcript.ts`) + a baked entities fixture (skips the visit-
  coupled L3). The only DB rows produced are FK-less AiCall/ApiUsageEvent billing telemetry with
  `visitId=NULL` — exactly like `tm_template_parse`.
- **Cached** in Redis by a content-hash of the draft + transcript version (`lib/sample-preview-cache.ts`,
  7d TTL, fail-soft) — generated ONCE per distinct template content; no migration; regenerable.
- **Model:** reuses L4's `tm_soap_draft` / `claude-opus-4-8` (Anthropic) — the SAME model the production
  SOAP pipeline uses, so the preview is faithful. ⚠️ See the OpenAI-only memory note in the PR/summary.

## Review-screen UI (`template-review-editor.tsx`)
The right column renders the live sample, CLEARLY LABELLED synthetic ("Demo visit · synthetic" + footer
"a synthetic demo visit — not a real patient"), minimal SOAP-markdown render, auto-generate after parse,
a Regenerate control, loading + error states. ADDITIVE: a generation failure degrades to the structural
outline + a quiet note and NEVER blocks parse/save/activate (the action bar is never gated on the preview).

## Pre-flight + qa validation
🟢 GO (`docs/preflight-reports/preflight-20260610T062535Z.md`). On the isolated meddoc-qa stack running the
exact `:latest` image: scenario 5 (incl. the new preview test) **2/2**, full chromium **54 passed / 0
failed**, unit `preview-note-template.test.ts` **8/8** (real prompt fed the template + immutable preamble;
visitId:null; NEVER persists a visit; content-hash caching; refuses invalid/PHI; model-failure → {ok:false}).
qa torn down `-v`. code-quality-auditor: **SHIP** (0 BLOCK; the four load-bearing properties verified).

## Safe app rebuild + deploy
- Rollback `:pre-note-preview` → `f7b622c7` tagged BEFORE the build. `docker compose build transcribe-md`
  (6G heap + bundle-assert baked) → `a244dc1b`, exit 0, no OOM, `[bundle-assert] OK`. Feature content-
  verified in the bundle ("Sample note in your format", `v1-t2dm-htn-2026-06`, `notefmt:preview:v1:`).
- App-only recreate: `docker compose up -d --no-deps transcribe-md`. Container diff: only the app changed;
  worker (`91c97b…`, StartedAt unchanged) + all co-tenants byte-identical. Post-build cache prune → 0B.

## Post-deploy verification (PROD, real auth, real model — qa-interaction-auditor)
Scoped to `qa-auditor@quillmd.test` (temp password set then **restored & verified == original**). Drove
the real note-format preview UI on app.quillmd.com. **PASS (A–E):**

| Check | Result |
|-------|--------|
| A — real sample renders in the parsed format (Subjective/Objective/Assessment/Plan) | ✅ |
| B — labelled synthetic ("DEMO VISIT · SYNTHETIC" + "not a real patient") | ✅ |
| C — content is the synthetic T2DM demo (12 markers), NOT the pasted note; no real PHI; no fabrication | ✅ |
| C — zero visit rows; all 3 model calls logged `visitId=NULL` (stateless, no PHI/FK) | ✅ |
| D — Save & activate works (status `active`); preview never blocks | ✅ |
| E — Regenerate served from the content-hash cache (one `tm_soap_draft` call) | ✅ |

Cleanup verified: test template deleted (0 left), password restored (`hash == original`), sessions cleared.

## Blast radius / safety
- Prod writes confined to `qa-auditor` (temp password restored; one test template deleted; sessions cleared)
  + FK-less billing-telemetry rows from the verification (harmless). No real patient/visit data touched.
- Worker + all co-tenants byte-identical. The no-preview path is unchanged — the preview is purely additive.

## Rollback (retained, unused)
`meddoc-pro-transcribe-md:pre-note-preview` → `f7b622c7` (the prior prod image — the Rx-gate deploy). To
roll back: re-tag `:latest` + `up -d --no-deps transcribe-md`. Not needed — verified healthy.
