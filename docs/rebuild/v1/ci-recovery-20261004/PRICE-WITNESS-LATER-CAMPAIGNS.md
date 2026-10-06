# Offline financial witness campaign identities — 2026-10-04

Source repair `a29c2774b4bd33b8ecfca0dc26b49ee61fdcff5c` changes only the literal evidence identity grammar and its pure tests. The witness now accepts first and subsequent standing campaign roots with the same `20[0-9]{6}` date and optional suffix 2–99 admitted by `standing_qa.LIVE_CAMPAIGN`. Suffixes 0, 1, padded values and values above 99 remain refused, as do foreign roots and incorrect evidence paths/names.

The original byte-bound admission predicate refuses `/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-2/evidence`, although the normal standing runner admits the corresponding campaign. This original refusal is retained as a pure compiled-predicate reproduction. No helper execution or campaign read was needed to reproduce it.

Nine focused tests passed in 0.124 seconds; bounded process exit 0 in 0.332456 seconds. The four new methods compile the actual literal admission predicate, exercise every authorized later suffix 2–99, retain invalid/path/name negatives and compare its identity grammar to the normal runner’s actual pattern. Five existing prepared/refusal controls remain. Source hashes and the tracked diff were unchanged during verification.

Original refusal: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/current-price-evidence-identity-20261004/original-refusal.json`, SHA-256 `d8ee7a94fadd2bbdd77a9b04c55ab4b3779210bf4af520b3fcfe7b789d34b3e5`.

Test log SHA-256: `d73328c199e1347afa8bfe5cc9232ff1ea0ad23b3ecb24bf18765dee5b45454d`.

The exact source, manifest, standing authority, synthetic mode, attempt, output ownership, provider-response, pricing, settlement and financial audit guards remain unchanged. There were no actual financial witness executions, database/provider calls, source fingerprint renewals or new qualification claims. Finished clinical source and genuine exact-source qualification still govern any later price-proof renewal.
