# Independent retention refutation — frozen 4dc254

**REFUTED: one preservation lifecycle defect with a restore false-green consequence.** Source: `4dc254bb4d3ecc25585949e47b393e43284f57d7`, parent `4caa34431a60e6ce3409ecadbbb6989b50659d7b`. Author tree was clean and unchanged when the evidence was sealed. No source edit, provider, corpus, live target, or full suite was used.

## 1. Release can erase bytes represented by protected history

Locations: `rebuild/core/retention.py:93`, `:143`, `:154`; `rebuild/core/migrations/0025_preservation_guards.py:65`; actual deletion caller `rebuild/core/jobs.py:757`.

The file registry is populated only when cleanup encounters an active hold. Release removes that hold from `active_holds`; subsequent cleanup consults current durable references and the file registry, but not the immutable archived prior rows.

Concrete frozen-source probes:

- **Case03:** create an expired over-limit upload with its correct encounter audit reference; create a matching patient hold; second administrator releases it before any cleanup attempt; invoke the real abandoned-upload reaper. **Output:** `removed=1`, file absent, preserved-file count zero. The hold had matched that encounter. File survival depends on whether cleanup happened to run during the hold.
- **Case04:** a transcription job references that upload; while held, change its `input_path` to a replacement. The database correctly archives the exact old job row. Release the hold and invoke the same real reaper. **Output:** `removed=1`, old bytes absent, registry count zero, while the immutable preserved row still contains the old path. The archive cannot recover the bytes it represents.

The second case proves loss of already captured evidence. The first additionally refutes the broad claim that files covered by a hold survive release. Neither example invents a disposition authorization. All inputs and contents are synthetic.

**Base comparison:** parent4caa had no preservation models or promises, and its reaper unconditionally removed eligible transient uploads. This is an incomplete new preservation boundary, rather than a regression in a previously implemented hold mechanism.

## 2. Restore validation accepts that incomplete archive

Location: `rebuild/ops/production_restore_check.py:85`.

**Case11:** retain the archived old job path from the same correction/release sequence, remove its bytes, and provide valid current template/replacement files. Run the real local `check` function against the isolated database and private state root.

**Output:** overall `passed=true`; 39/39 exact triggers passed; four invariants passed; file report `referenced=2, missing=0, hash_mismatched=0`. The prior-row file is absent. Adding `core_preservedfile` to the reader does not cover evidence whose registration never happened. This is a local verifier false green; no target admission or actual restore was attempted.

## Bounded controls and evidence

Thirteen independent controls: **10 PASS / 3 RED / 0 instrument errors**. Positive controls cover exact prior-row preservation, registered-file survival after release, unrelated and unknown scope cleanup, finalized raw DELETE refusal, distinct release custodian, stale suspended actor refusal, evidence update/delete/TRUNCATE refusal, fresh39 catalog with same-count body replacement refusal, and cleanup waiting for a committed hold. No additional finding is claimed for the remaining statically traced surfaces; this is not exhaustive authorization/concurrency certification.

Private runtime: `/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/retention-refutation-4dc254`.

- `probes.py`, `02-probe-results.json`: first ten cases.
- `extended_probes.py`, `03-extended-results.json`: restore, catalog, and concurrency cases.
- Fresh isolated database namespace: `custodian_retention_4dc254_20260927`, assigned loopback port55705; no existing database/schema changed. The launcher reads existing container credentials privately and never prints them. AI mode is asserted fixture; Python network entry points are denied. No attempted provider/network call was recorded.
- Source identity manifest SHA256: `b6a9ade7e4e6334b647470dc3bbb23836be1393a337237714e52aa6567759b83`.
- Evidence seal SHA256: `6f73adad90ed51c97c10b3d393aad73bc794676a55816462709ecdf963843d89`.

Key frozen hashes: retention.py `4f4c3dd7e67cc9f0fae296813742514beaeb351cafdd67ea64ec92d23070ad23`; migration0025 `33a8d1e3b6d20ff73cc0c1fecb91344ec67a738425c9607352d8549db95da268`; production restore checker `9fedd60678563e72e9938bce7c0c461e36430cbbde43f7d2258448d742da5f8c`.

Parent received exact reproductions before repair. Earlier failures, original corpus manifests/first passes and sealed unseen maps remain preserved.
