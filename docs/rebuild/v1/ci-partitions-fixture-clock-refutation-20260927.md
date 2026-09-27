# Independent CI partition and fixture-clock refutation — 2026-09-27

**NOTHING FOUND within the bounded omission, false-green and test-weakening review.** This is local evidence, not a remote CI success or proof that setup plus every lane finishes within 20 minutes.

Reviewed commits: `52f48d72b266894adbf8ddf2ab3d694751c0dd5e` and `fc7361cb79c36a3e0c46ddc319c25d42df2fb49b`; parent `a4e5b692029e69b7dde47263b628a783c1608eec`.

## Evidence

38/38 independent controls passed. Source snapshots, complete results, synthetic shell call logs and the runner are private under `/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/ci-partitions-fc7361cb-20260927`.

- The actual parent and candidate shell scripts were driven by logging executables. Candidate core plus support exactly equals the parent's five Python commands, including the full explicit document list and ops discovery. Legacy `python`, default/all and marketing retain the same commands. Twelve failure injections across core/support/all return the original failure code and stop before later commands; missing credentials/core suite and unknown mode refuse before any command.
- Parsed workflow comparison preserves triggers, permissions, concurrency, PostgreSQL service/environment, all preparation and qualification commands, and both unrelated jobs. The two fixed lanes retain 20-minute limits and `fail-fast: false`. SSH qualification, actual Word adapter/kernel qualification and Python dependency audit each run on support; setup stays available in both lanes.
- The original required name `Fresh application tests` is preserved by an `always()` aggregate needing the matrix job. Its actual shell predicate accepts only exact `success`; failure, cancellation, skipped, empty, mixed-case, multiline and injected-looking values refuse. No continue-on-error was added. GitHub service scheduling/cancellation semantics and branch-protection configuration were not exercised locally.
- AST comparison confirms every pre-existing assertion call in both changed offsite test files remains identical. Production `automatic_offsite.py` is byte-identical to the parent and matches the imported source. The fixture changes construct the real Budget before patching its factory, pass the intended limits, and supply an explicit historical clock; preflight and expiration logic remain active.
- Only the four corrected fixture cases and new expiry negative were executed: five pass. Independent real-Budget probes reject a clock before policy observation, at the exact expiry instant, and after expiry; observation time and one microsecond before expiry pass.
- An in-memory mutation omitting Budget.preflight is detected by the new expiry negative. It ends in an error after the mock transport is wrongly reached (Mock cannot be serialized), rather than a direct assertion failure; this narrower mutation evidence is retained verbatim.

## Limits and instrument notes

No full suite was repeated. No database, provider transport, count_tokens, Word rendering, corpus or qualification maps were used. One urllib3 import-time IPv6 socket-construction attempt was blocked before construction by the audit hook; a separate import trace locates it at `urllib3.util.connection._has_ipv6`. No connection or provider request occurred. Local Python lacked PyYAML in the release venv, so the runner used the already installed system PyYAML 6.0.1 solely for workflow parsing; nothing was installed.

The root's original full ops failures and subsequent focused/full reruns remain separate evidence. These controls do not turn that earlier failed run into a pass or waive final exact-candidate CI.

Seal: `064-ci-partitions-fixture-clock-seal.json`, SHA256 `4e134bcaadbe135c10c27dc2ae6ac16e3d2363fc26598fde10078a2fc268d8f1`.
