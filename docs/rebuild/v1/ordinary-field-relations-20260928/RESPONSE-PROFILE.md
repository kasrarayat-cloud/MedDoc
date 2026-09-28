# Prepared ordinary response profile

Engineering preparation only. The ordinary feature remains off by default. This
change is neither activation nor paid-call authorization; the existing proposed
$40 request remains unapproved. Any future authorized send must reconcile its
actual per-call exposure, model eligibility and remaining budget first.

New disabled-thinking native Sonnet 5 ordinary requests use the immutable
`claude-sonnet-5-ordinary-v1` profile, with 20,000 output tokens and the existing
120-second timeout. It stays below the pinned SDK's 21,333-token non-streaming
ceiling and the worker's 150-second stop allowance. No streaming or 32k request
was introduced. Historical 8k disabled and 16k adaptive profiles reconstruct
unchanged; specific non-v3 callers retain their previous profile. New quotes
include the distinct profile in their pricing fingerprint and recorded config.

The arbitrary 256 field-by-unit limit was removed. Complete serialized requests
remain bounded at 512,000 bytes, source at 50,000 characters, requested fields at
100 per response and deterministic batches at eight children. The conservative
closed-response JSON byte bound must fit the actual profile output-token cap.
Nothing shortens source/catalogue or discards relation cells to fit. Physical
groups remain indivisible and unknown form constraints still refuse batching.

Measured response envelope (bytes of the complete closed maximum response):

| Requested fields | Source units | Response bytes | Fits 20k |
|---:|---:|---:|:---:|
| 50 | 12 | 14,952 | yes |
| 50 | 20 | 22,552 | no |
| 75 | 10 | 19,577 | yes |
| 75 | 12 | 22,427 | no |
| 100 | 5 | 17,002 | yes |
| 100 | 12 | 29,902 | no |

The saved D30 61-field map has 57 requested fields and 12 complete units: its
response bound is 17,160 bytes, so this profile admits a single request without
fabricating a form-constraints manifest. This is an admission measurement, not
whole-form clinical acceptance. With that saved map, actual compiled SDK request
sizes are 39,678 bytes globally and 39,701 with explicit US geography. At the
recorded $2/$10 per-million input/output rates, provider bounds are $0.303356 and
$0.3337422 respectively; 1.5 retail bounds are $0.455034 and $0.5006133 before
ledger currency rounding. Later mapping metadata changes alter the exact quote.

The extra 12,000 output tokens add **$0.12 provider / $0.18 retail** globally,
or **$0.132 / $0.198** with the 1.1 US multiplier. One extra serialized
`max_tokens` digit adds a further $0.000002 provider input bound globally
($0.0000022 US). The compiler prices the actual full request bytes plus its
existing 12k input overhead, the exact output cap and geography multiplier;
quote, immutable config, child reservation and actual SDK kwargs use that same
compiler/profile. All child holds still precede sending; unknown outcomes,
cancellation and one-time complete adoption retain the existing ledger rules.

Verification: 22 focused no-DB methods passed, followed by 93 workflow, batch,
legacy profile, quote and settlement methods in 93.140 seconds against the
fresh isolated synthetic ordinary database. Exact 20,000/20,001 response and
512,000/512,001 request-byte boundaries were exercised. The flag-off legacy wire
probe is byte-identical to frozen 9f, including Sonnet 5/4.6 and stored batch
v1/v2 reconstruction: SHA256
`81e1209b719eee4c1dbb61a84a5d52db87cc4c00fdb37f6ae7b607433c3bd149`.
Provider calls were mocked; no external spend or payment actions occurred.
