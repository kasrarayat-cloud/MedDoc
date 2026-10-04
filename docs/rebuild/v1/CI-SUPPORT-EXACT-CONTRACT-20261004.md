# Exact SUPPORT CI contract correction — 2026-10-04

The source-bound local correction passes all seven existing `CIGatePartitions` controls. It adds the eight already-running document modules to the exact expected support list and asserts the existing 60-minute `python-checks` bound within that job. The executable CI script, workflow, application source, lane membership, required aggregate, complete discovery and fail-closed outcomes are unchanged.

The initial failure remains evidence: CI run 37233714610, job 111528565534, on `2240a49ed4f843cf2248550a46bd35fdf3bbb8f9` ran 2007 support controls in 222.100s, with two failures and 17 skips, then exited 1. Its authenticated API log download exited 0 and retained 848437 bytes. `test_partitions_exactly_cover_legacy_python_gate` expected 27 modules while the executable script named 35; `test_required_aggregate_runs_always_and_accepts_only_success` still expected 30 minutes after the full core-1 workload established the bounded 60-minute requirement.

The isolated correction starts from `c99d8fb81bfcf537b5c295df01539756e0d009d3`; the two test assertions, CI script and workflow at that baseline are byte-identical to the failed CI commit. A finite network/DB-denied local packet reproduces both failures before editing: actual child exit 1, two tests, two failures, no errors/skips/connections, 1.925s. After editing, the full affected existing class runs seven tests with actual child exit 0, no failures/errors/skips/connections, 3.227s. Both bounded children were reaped without timeout and all tracked file bytes remained identical before/after each run. This is the affected local test packet; exact final-candidate CI remains a separate required citation.

The unchanged controls still prove exact legacy/core/support coverage, every document test module named once, settings propagation, both full core discovery labels, fail-stop at every stage, unknown-mode refusal and an always-running aggregate which accepts only success. `failure`, `cancelled`, `skipped` and empty outcomes still fail. No suite was run through the probe’s synthetic interpreter; it captures the real shell partition commands and returns deliberate bounded stage failures.

Protected raw evidence is in `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/release-completion-20261004T200104Z`. The retained SHA-256 bindings are:

| Artifact | SHA-256 |
|---|---|
| `CI-C2240-support-FAILURE.json` | `8a02bf6a759e285240d616c92c8d98cb8ef5298d1c7f24be4b2fdc1cf22047ba` |
| `CI-C2240-support-111528565534.log` | `15fad5fade974045796217814bcf9f0e1455d86da1143e073493d0afe5fe6ad1` |
| `support-ci-contract-probe.py` | `90a26fa77692d6d4f35cbf147d9a0415db383dfc7fa063d697c04b4bf2c021d4` |
| `support-ci-contract-original-result.json` | `388708a1e1448f6b859704a9d395ad57fc3d563577f63fc0bdd3eeabc6ba4d51` |
| `support-ci-contract-fixed-result.json` | `5becb568a4c60cc5c3784f7f4be51af28712452b537971109bbe96e0be621b0c` |
| `support-ci-contract-original/process.json` | `d3ede04885750d70b7f4598915fc8058cf93b17c8259166ce436f763e6173861` |
| `support-ci-contract-original/stderr.log` | `24ff9c03070a0e26fb437fcba448f0214a3b5d811a130b437d83879b565ee07a` |
| `support-ci-contract-fixed/process.json` | `15d84bcedf615db7951059c18a746fe459b3b030060882bf90e2eae15271cf6a` |
| `support-ci-contract-fixed/stderr.log` | `58954069e0fcec3bf8b38c23ec3655ece9719100377c7fd3c5b03ae34a38d017` |

No provider, renderer, browser, service or database operation was performed. No workflow bound was extended by this correction.
