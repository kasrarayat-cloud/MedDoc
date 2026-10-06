# D11 temporal destination refutation — 2026-10-04

Independent pure inspection/export tested frozen Word source `eae56b63fda5c524d35e03f7e7e409876db6885f`, `documents/word_v3.py` SHA-256 `6ce37febf579571f68ce120060b76a56626a78a852ab0d75873bb622c67f1033`. Small project-authored synthetic originals were created in operations scratch. No database, renderer, provider, source edit or application workflow was run.

## Demonstrated raw export failure

At `rebuild/documents/word_v3.py:9798`, the new temporal source guard verifies each date writer independently. Two otherwise exact mappings for the same complete date paragraph, with distinct keys, both pass. Line 9999 then schedules both span writes against the same original range.

Concrete input: a table's unique aligned `Collection date and time:` caption owns complete `DD/MM/YYYY` and `(HH:MM)` paragraphs followed by the original AM/PM/24-hour selection. The inspector's current date field is copied under a second key. Answers are `04/10/2026` and `05/10/2026 EXTRA` for that one physical date paragraph. `fill()` succeeds; the export contains only `05/10/2026 EXTRA`. The first complete answer has disappeared.

Exact retained evidence under `operations/d11-independent-refutation-eae56b63-20261004T150928Z`:

| Artifact | SHA-256 |
| --- | --- |
| `metadata-negative-duplicate-exact-original.docx` | `f4890b52b9e837ecfe63c640ed7412e0a10dc96b4546b97db1fd529fff6dbe21` |
| `metadata-negative-duplicate-exact-fields.json` | `212819609f77fe7d8d70a6458925563dcf2269e84647e18759cfda2aae2e1850` |
| `metadata-negative-duplicate-exact-answers.json` | `8c85c12144b208601324473eac1b2429f538808c46c4c477ba4e7da8970d3e32` |
| `metadata-negative-duplicate-exact-WRONG-export.docx` | `619e927936c5cc58549df476df82f511503d5831215cecee61f6a9bf1c114bb8` |
| `sealed-adjudication.json` | `9f4da4ac585e83f057f32184cc5ddc88658e9f6b8afdfb197d2ba29c7c2ac056` |

The operations scratch root is `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations`. This is a demonstrated raw `fill()` interface result. Current persisted duplicate-confirmation protections may refuse that forged or stale mapping before export; application admission and reachability are **unverified here**. No clinical or installed failure is inferred.

## Positive and denial controls

Seventeen original denial controls passed, including hidden date/time/caption/clock source, linked date/caption source, a competing or merged caption, a neighboring caption, an existing date entry, removed relationships, whole-cell/copy-to-neighbor/clock-anchor forgery and human signing captions. No other concrete wrong output was demonstrated.

Three original positive assertions compared complete old/new clock metadata and failed on the generated ordinal key alone (`v3_4` → `v3_6` after adding two fields). A separate diagnostic proved all other clock metadata identical, the saved old clock mapping still accepted, and PM selection preserved the original date/time hints. The key-only assertion is an instrument issue; it is not evidence of broken historical export.

A new, separately retained packet, `operations/d11-preservation-controls-eae56b63-20261004T151448Z`, ran only those three blocked positive controls with the ordinal excluded from the physical-metadata comparison. **3/3 passed, actual exit 0**: date/time together, date/time plus an explicitly changed clock selection, and the saved old clock mapping. Exact full answers, existing witness/manager entries, the neighboring hyperlink, headers/footers, every untargeted paragraph and every non-document package part were preserved; no-answer export retained original bytes. Its result SHA-256 is `f96e6afc83c219e24c3940d6271d50e640f775defcba6f97e4f4712b5a139479`.

The original probe's actual exit was 1 and its source remained unchanged. Its 17 passes, three key-only assertion failures and one duplicated-write failure are retained unchanged. The first scratch invocation failed before imports because `documents` was absent from `PYTHONPATH`; the actual tool traceback is described in `first-instrument-error.json`, without a claim that a redirected raw log existed. The corrected invocation used the frozen rebuild directory on `PYTHONPATH`. No Word source was modified and no product acceptance denominator was changed.
