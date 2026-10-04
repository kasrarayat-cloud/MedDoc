# Independent legacy archive-comment refutation — 2026-10-04

Finished source `2da3457b50477f99edc9184beaf1cd0da0a6915f`, parent `85c38c9de426224543cb27616b90707de3661f59`: **NOTHING FOUND** within the assigned ZIP-comment claim.

Five independently constructed copies of the accepted blank WM fixture use empty, text, NUL/high-byte, all-byte and maximum 65,535-byte ZIP comments. The repaired writer preserves each exact comment. Its repaired `word/document.xml` is byte-identical to the parent’s repaired content, every other part retains its bytes, and the second repair is a whole-file byte-identical no-op. A separate unrelated document with a binary comment also remains a whole-file no-op. Parent comment loss is reproduced in four nonempty cases.

The first independent harness exited 1 because it incorrectly expected the second-pass summary to report one newly changed table. The actual unchanged second-pass summary is zero changed tables and two recognized headings. That failed script/log and partial outputs remain; the second script corrects only that harness expectation. No production source or scorer was changed.

Actual second exit 0, elapsed 0.415790 seconds, under a 90-second deadline. There were no database, renderer, provider or network operations. Exact committed layout sources and the blank original were hash-bound and remained unchanged. Native Word layout acceptance is outside this metadata-only proof.

Evidence: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/layout-comment-refutation-2da3457b-20261004/replay-02/result.json`.

Result SHA-256: `329477f625b095e0f8877fdfba22828b5b5b066b337bfb2b5bacfb628db2dcc6`.
