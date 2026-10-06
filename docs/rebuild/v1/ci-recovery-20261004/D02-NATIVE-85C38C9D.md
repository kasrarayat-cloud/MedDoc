# D02 affected native route replay — 2026-10-04

The exact `85c38c9de426224543cb27616b90707de3661f59` route method passed, but the whole-document packet remains failed. The original D02, expected answers, profiles, scorers and acceptance thresholds were preserved. This is an affected regression of a previously exposed case; it is not the frozen 60/20 acceptance gate.

The detached source is `/opt/meddoc-pro/.worktrees/v1-ops-d02-85c38c9d-20261004`. Evidence is under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/d02-native-85c38c9d-20261004`, with application output `dev-native-application-85c38c9de426-1791095520595553943`.

## Actual outcomes

| Evidence | Result |
| --- | --- |
| Actual upload, native mapping review and typed-note/review route method | 1 method passed in 9.823 seconds; child exit 0 |
| Bounded outer packet | Exit 1 in 52.456675 seconds; no timeout |
| Fixed first-pass mapping | 19/24 correct; 5 wrong kinds; no missed, extra or duplicate destinations; strict and tolerant false |
| Empty export | Byte-identical to original; finalized/downloaded |
| Fixed ordinary and long profiles | Saved review state; finalization refused by actual clinician signing identity guard |
| Separate native ordinary recovery | One explicitly reviewed signature-value correction; no mapping correction; finalized/downloaded; mechanical and render checks passed |
| Separate native long recovery | One explicitly reviewed signature-value correction; no mapping correction; finalized/downloaded; mechanical and fixed render checks passed; two supplemental contiguous full-answer probes failed |

The five mapping failures are `PATIENT DOB`, `DATE OF PROCEDURE`, `Electronically signed by`, `DD (dictated)` and `DT (transcribed)`. The unchanged fixed signing value is refused with: “The reviewed signature must match your signed-in clinician name.” Each separately reported recovery explicitly replaces that value with the authenticated synthetic clinician’s name. This is recovery evidence and earns no automatic gate credit.

Original SHA-256: `8ae1e2b0ebeec317c038b8bfeed6a0824055f44d689c039ab450404593f2815a`.

Native ordinary export: `d69dbd77606e95e9d02424aaf48dda258f3fa4bb170ea54d20ca358e934f93bf`.

Native long export: `0be53184e334bbf838ef61a4c919fbe69c72eca5628a2787495bd3c1ff18142f`. Both exports and hash-bound reviewed answers were archived before assertions.

## Render evidence and its limits

The unchanged fixed renderer finds no missing fixed probes or overlap in the long export, which spans four pages. The supplemental checker retains misses for `tab_v1_8ae1e2b0ebeec317_0_18_0` (DESCRIPTION OF PROCEDURE) and `tab_v1_8ae1e2b0ebeec317_0_30_1` (DD dictated).

The separate pypdf 6.19.0 trace binds the actual export to `instrumented.docx`/`instrumented.pdf`, and the original to `document.docx`/`document.pdf`. All non-document parts remain byte-identical. Every PDF page begins in extraction order with text from the unchanged original `word/footer1.xml`: `GASTROENTEROLOGY 1 / 1`. This footer interrupts two continued answer strings. Removing only those independently verified original footer prefixes from the supplementary body trace recovers all 24 complete answers; the assigned XML readbacks also match all values. The original fixed and supplemental results are preserved. This trace does not prove visual clipping or native Microsoft Word acceptance.

`supplementary-full-answer-trace.json` SHA-256: `ae78efff072f8bd6efe8adaae8793ee73eaef8325608048a60f56527a6eb31ec`.

## Source and process preservation

The original harness and checker were copied byte-identically. The runner changes only the owned database and socket prefixes; moving its literal copy also confines output to Ops scratch. The existing pinned PDFium files were reused read-only and hash-bound before launch. Prospective manifest SHA-256: `3af3bcec29991ae1e27ef7e057df5796555b7a4b6f88391b5c58372cd7c9ab94`.

Tracked source manifests and harness hashes are equal before/after. Database `quillmd_qa_sol_ops_d02_1320598` and its `test_` counterpart were directly queried and absent before/after. The test database was destroyed, the renderer ended with SIGINT status -2, the owned socket was removed, and renderer/outer PIDs were absent. The exclusive QA/render slot was explicitly released. No files were deleted.

`packet-report.json` SHA-256: `3abd8ea52c7132496ffd90e47fa400b68c852db13c52f43afeda59d89365a96b`.

There were zero provider calls, jobs, reservations or usage records. These fixed writer profiles exercise persisted typed notes and clinician review; they do not qualify clinical model generation. Installed/public services, the old demonstration and original 60/20 denominators were untouched.
