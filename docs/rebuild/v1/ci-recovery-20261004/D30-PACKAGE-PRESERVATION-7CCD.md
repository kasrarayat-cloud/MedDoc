# D30 original-to-final preservation adjudication — 2026-10-04

The archived D30 final export preserves the original document content and structure. Independent read-only comparison found only the two intended new selection-marker runs; all 32 untargeted ZIP-part payloads are byte-identical. ZIP storage representation is not identical: recompression changes compressed payloads and two entry metadata fields. This result qualifies the declared manual export's package content, not automatic mapping, useful generation, native Word inspection or the whole 60/20 gate.

The actual route packet remains bound to `7ccdcb6e75241685e90519774b909ecbd5b1e827`. Its original D30 is the unchanged ledger member, SHA256 `fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`. Its archived final, reviewed export and actual authenticated download are identical, SHA256 `fdf4dbe9327f7d2cab8dafc4981d76d9701a69ab423e8ae9d774fe6a76bd498c`. The initial-import bytes equal the retained original exactly. The rights ledger still permits this internal offline replay and denies provider upload; no rights inference or source substitution was made.

## Independent package result

The comparison reads the original, mapping, archived final and actual-download evidence directly. It imports no application/export/scorer code. It verifies the 558 recorded Python source files against the exact clean retained 7ccd worktree and the unchanged before/after source receipt.

| Property | Actual finding |
| --- | --- |
| Package members | All 33 member names and order retained; archive comment retained; both ZIPs pass CRC checks. |
| Untargeted raw parts | All 32 uncompressed part payloads are byte-identical, including headers, footers, numbering, styles, relationships, media and properties. |
| Original XML tree | All original nodes, attributes, text and tails retained after removing only the two separately identified new marker runs. Forty tables and 281 direct-body paragraphs remain. |
| Paragraphs | Of 465 original paragraph subtrees, 463 are wholly unchanged. The two changed subtrees retain every original node and add exactly one `☒ ` run each. |
| Manual A20 | Eight original printed options remain in `b/p[73]` through `b/p[80]`, with their original paragraph/run properties and numbering. Only `b/p[77]` “own flat/house” and `b/p[79]` “with partner” receive a marker. No option is removed or renamed. |
| Neighbor A21 | Mapping `v3_20` and the complete original `b/tbl[4]/tr[0]/tc[0]` subtree are unchanged. Its saved decision is explicitly left blank and reviewed; it is not substituted for A20. |
| ZIP storage limit | All 33 entries change `external_attr` from 0 to 25165824; 31 change `flag_bits` from 6 to 0, and 31 compressed payloads change. The changed document entry also changes `create_system` from 0 to 3 and `create_version` from 45 to 20. Content bytes remain exact outside `word/document.xml`. No compressed-byte/whole-container identity claim is made. |

The storage difference is visible at the existing `documents/word_v3.py:276–290` package writer: it rebuilds the ZIP through `writestr`, preserving payloads and original compression type but allowing Python's recompression/default attribute behavior. Its docstring's “same metadata” wording is broader than this observed result. There is no demonstrated loss of Word content or physical structure in this D30 artifact. No package or source was edited by this adjudication.

## Outcomes remain separate

The unchanged automatic ground-truth result is **61/62**, with one missed A20 and no extra/duplicate destination. Manual A20 mapping yields **62/62 recovery**. Neither is a whole-document automatic pass.

The stored first fixture answers are **57 conflict plus 5 missing**, with zero useful supported answers. The actual review POST has 59 answer/review requests and 58 explicit blank requests. The saved final answers are **58 left blank, 3 missing and 1 edited selection**. Three signing destinations remain missing/unreviewed and unposted: `v3_36` Signature, `v3_40` Signature and `v3_55` Clinical Supervisor’s Signature. These counts correct earlier “62 conflicts/61 blanks” shorthand; they do not change its zero-useful-generation conclusion. The simulated usage is zero. No clinician identity or invented answer was inserted into the three other-person signing places.

The original actual-route child completed one method with exit 0 in 30.345 seconds. The lead reported outer exit 0 in 47.685 seconds; the retained packet's own elapsed field is 47.518 seconds. Its recorded normal/test database catalog absence and renderer/socket teardown remain separate evidence. This adjudication performed no database query, renderer launch, provider call, service action or additional route test.

## Retained independent evidence

Own protected evidence: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/d30-package-adjudication-7ccd-20261004/replay-03`.

- Result SHA256: `cbe3484d5f9eadb0ef1e8ad2612fcfbe7d4cd37614c8e727f9d90ae3cdce9814`.
- Pure script SHA256: `532a57ed4140f7635e6a51ae8e3e8d575ad614bbf4e7909f0e3d7e1e5b299ee7`.
- Actual read-only exit: 0, 0.225 seconds. Immutable original/final copies, per-part hashes, eight exact option texts, A21 signature and route/source receipt hashes are retained there.

Two earlier pure instrumentation assertions incorrectly inherited the shorthand counts. They failed with actual exit 1 at 0.412 and 0.508 seconds; their scripts, original traceback records and input copies remain in the prior output directories. Only the instrumentation counts were corrected. The original, final export, source, ground truth, scorer, thresholds and denominator were unchanged. Native Microsoft Word and a new visual/render inspection remain unverified by this work.
