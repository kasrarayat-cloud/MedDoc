# Retained human-consent refusal and independent signing/export browser control

Source base: `15f87bb2e7a487225711fa52c8092e279767ad01`. This repair changes the browser fixture preparer, browser qualification and focused tests only. It changes no application generation, destination-role, import-binding, Word engine or billing guard.

## Original failure and demonstrated cause

CI run `37158506012`, browser job `111306810056`, failed after five legacy Word checks at “Generate with the synthetic fixture at zero charge.” The downloaded `private-browser-evidence` artifact contains four result JSON files. It does **not** contain the referenced screenshots/trace, original DOCX, source notes or job configuration. The original CI result is retained unchanged beside this report. No original CI document hash or provider response is inferred from those missing files.

The unchanged eight-row preparer and unchanged browser script from the exact CI source were replayed in isolated synthetic QA. The same five checks passed and the same generation check failed, with browser exit 1. Unlike the original CI artifact, this replay preserved the actual original, inspector mapping, import manifest and persisted encounter before database teardown.

The original includes “Consent form signed” at `word/document.xml#b/tbl[0]/tr[5]/tc[1]`. The physical-coverage inspector identifies that destination as `human_signing_action`, leaves it unresolved in the legacy mapping and sets `block_generation: true`. Admission correctly refuses:

> This import has unmapped answer areas. No generation or charge is allowed until a clinician reviews the exact exclusions or a new original/mapping repairs them. Excluded areas remain unchanged and do not count as supported coverage.

The old browser script waited for a job that admission never created. Persisted reproduction: draft encounter, empty answers, **zero jobs, zero reservations, zero usage rows and no export**. The original remains unsupported coverage. Its three export assertions remain unevaluated. It is not relabelled a successful export or removed from any historical denominator.

## Resulting qualification

The preparer preserves the original eight rows and notes, and creates a **separately named seven-row signing/export positive control**. That control omits only the human-consent row. It retains Patient signature, Initials, both note-derived signing attacks, ordinary Initial assessment, all other original values and surrounding text. Input relationships and both original hashes are checked by the browser. The preparer refuses to replace any existing original or manifest, checking the entire output set before writing.

The browser first uploads the retained eight-row original, checks every mapping row and the immutable original download, creates a persisted draft, attempts generation and checks the precise refusal, draft/empty answers through the authorized API, no visible jobs and no export. Its result explicitly records `original_refusal`, `supported_coverage: false` and unevaluated original export assertions.

It then uploads the independent seven-row control and completes the normal fixture worker, clinician review, finalization and download. Its original DOCX assertions remain unchanged: ordinary values occur in their own destinations; both signing attack values are absent throughout all Word XML parts; both signing answer cells remain identical; label cells and original heading/instruction XML and order are preserved. These are automated DOCX structural checks, **not native Microsoft Word inspection**.

## Verification

- Focused persisted HTTP tests: **3/3 passed, 7.112 seconds, actual exit 0**, no skips, test database destroyed. Tests preserve preparer immutability/original eight-row denominator; repeated eight-row generation refusal with zero jobs/reservations/usage; and independent seven-row upload → worker → evidence-linked review → finalize → faithful export. The positive control has five supported ordinary answers, two blank unchanged signing cells, one successful fixture job and one simulated zero-cost/zero-charge usage row. Authorized positive downloads succeeded; a clinician from another department receives 404 for original download, encounter API and export.
- Actual Chromium replay: the unchanged old script reproduced the original failure (exit 1). The repaired dual-case browser passed **15/15 checks and all three export fidelity assertions**. A bounded `StaticLiveServerTestCase` harness checked the browser exits and persisted negative/positive records: **1/1 passed, 126.397 seconds, actual outer process exit 0**, database destroyed, worker stopped, no worker errors.
- JavaScript syntax and `git diff --check` passed. Subsequent browser source change was indentation only.

The browser helper had three preserved setup failures before the actual replay: external runner Django import path, absent task-owned seed parent and Playwright cache lookup under isolated HOME. The corrected harness uses its own synthetic seed directory and the existing Chromium installation. No dependencies, provider services or installed application were mutated.

Raw evidence is archived under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/browser-authority/frozen-evidence`. `HASHES.json` binds the retained sources, originals, persisted mappings/configuration/results, screenshots, trace, export and exit logs. Archive copies were hash-verified. Protected synthetic credentials are outside that manifest/archive and were not displayed. The retained unchanged reproduction source also remains in the task worktree as an untracked recovery copy.

## Limits and integration

No providers were called; API attempts and estimated provider exposure are unchanged. This fixture run makes no live Sonnet, real-provider voice, human microphone or real-patient claim. The two cases are supplemental safety evidence; the established **54/60 overall, 18/20 holdout and family/safety Word acceptance gates are unchanged**. Manual signing-blank control mode remains explicitly named as clinician recovery and cannot become automatic-correctness evidence. Root retains sole integration ownership and must run required CI on the exact resulting release commit.
