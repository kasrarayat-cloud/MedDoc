# Served profile browser assertion recovery — 2026-10-04

The new profile assertion at `browser-tests.mjs:216` rejected the correctly configured fixture page. `admin_console.language_model_rows()` emits the fixture provider-request disclosure with severity `warning`; `admin_services.html:46` renders that badge before its value. The captured cell therefore starts `warning NONE — QUILLMD_AI_MODE is fixture, ...`, while the original anchored assertion accepted only `NONE ...`. A finite render of the actual table fragment and execution of the original Node assertion demonstrated the rejection on source `e0cd3b14d64f2404abea141a0caf45aeab0af5ac`.

The one-line repair accepts that exact optional `warning` badge plus whitespace. It preserves the raw captured cell and the explicit fixture/no-provider message. Three focused actual-template/Node controls passed, exit 0 in 0.388 seconds: the badge and plain fixture positives pass, and missing/live/wrong-label/foreign-mode/error-badge negatives refuse. Node's syntax check and diff check passed. No application/browser, database, renderer, provider or installation ran.

The actual template confirms the other inactive model, profile, contract and pricing rows have no severity prefix. The database worker row does prepend its success badge; the existing unanchored `held by database session` assertion accepts that formatting and rejects the unknown or not-held rows. The two separately launched CI hosts and worker inherit the same full `github.sha`; the browser asserts their returned release identities match that job value. For pull-request CI this is the checked-out merge revision, which must remain distinct from the API's head revision in exact CI/source evidence. Private demo verification uses its own actual archive release and OS PID/source bindings.

Protected raw failure, original source bytes, corrected source and proof are retained under:

`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/browser-warning-original-probe-20261004`

| Artifact | SHA-256 |
| --- | --- |
| Original wrong-result `result.json` | `7edf52c196d5762066da6086f60423d9c2e0abb32edc9d9d85506ef144bb0027` |
| Corrected `corrected-result.json` | `32e33153e19d4aeb974610f08ff8bd6d559167aba7d64189cecc09e8fcfe35ba` |
| Actual corrected-control log | `bb43c6e1862d5a68c3ebf9a82fb9527486a9e09ae374ad5fa9e4fe57bb019263` |
| Retained originals and outputs seal | `a98fe070fadb77296a37aa39ba3e31d171648390bd122efd16a895f609676ade` |

The final-revision CI browser and actual private demo served checks remain pending. The future 119 financial packet remains prepared with the final source, source seal and root grant unset; no old passing test or fixture profile is relabeled as current execution.
