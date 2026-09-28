# Two bounded core CI lanes — 2026-09-28

Prepared on isolated `v1-ci-core-shards`, base
`c3e32e7c4a997363543505463be612c6a529c3ab`. No application source or core test
assertions changed. No full suite, provider call or database operation ran.

## Retained failure

PR1289 CI36364004389 at527930e7 reported **2,097 core tests in1,092.350s,
OK**, then its20-minute job was cancelled during teardown. The job remains
failed; successful test output does not replace the cancelled CI result.
The retained log SHA256 is
`45eaf65d6ec235978cd3278a033ccf33ea27fa4a70bd6cd80eb43873a9ac0e90`.

## Execution and coverage contract

The workflow has `core-1`, `core-2` and unchanged `support` lanes, each still
limited to20minutes with `fail-fast: false`. Both core lanes still run Django
checks and migration-drift checks. The original `python-core` and combined
`python` commands remain available and invoke the same full `core.tests` suite.

`CoreShardRunner` subclasses Django's installed `DiscoverRunner`. Each CI lane
first builds that same complete real `core.tests` suite, rejects discovery-error
placeholders, duplicate test IDs and empty plans, then deterministically assigns
whole test classes. Classes are sorted by descending test count and qualified
name, assigned to the currently smaller lane, with lane number as tie break.
Each selected suite retains its original Django execution order. No elapsed-time
history, hand-picked module list or runtime test result controls assignment.
Filtering flags, alternate labels, parallel execution, missing source identity
and reused manifest paths refuse before test execution.

Each core job records its complete class/test-ID inventory, selected IDs and
source SHA. The existing required **Fresh application tests** aggregate still
runs with `always()` and first requires success from every Python matrix lane.
It then downloads the two current-run manifests and independently verifies the
same source and discovery universe, the deterministic assignments, and every
discovered ID occurring in exactly one nonempty lane. Missing, malformed,
duplicated, inconsistent or incomplete manifests fail the aggregate. The
aggregate retains its2-minute cap.

Only the exact per-lane JSON file is uploaded. Hidden-file inclusion is explicit
because the file is under `.runtime`; missing-file handling is an error.
The official v4 [upload inputs](https://github.com/actions/upload-artifact/blob/v4/action.yml)
and [current-run download inputs](https://github.com/actions/download-artifact/blob/v4/action.yml)
were read for these settings. No runtime directory, environment file or patient
artifact is uploaded by this step.

## Measured bounded evidence

- **2,097 discovered test IDs /391 whole classes →1,049 and1,048 tests**.
- Both manifests' union is byte-identity-equivalent as sorted IDs to the default
  DiscoverRunner universe and to all2,097 test IDs parsed from the retained52793
  CI log. There are no duplicated IDs or class splits.
- Universe SHA256:
  `5c184f35741b8458f94e11e84e9f8a977282f07968f15a5560d59b0edfbd14c9`.
- Discovery ran with network and DB connection methods blocked and fixture mode
  set. **Zero core tests executed**. This proves coverage, not execution timing.
- **12 focused pure test methods PASS**, including deterministic balance/order,
  discovery errors, empty and duplicated cases, filtering/identity refusals,
  thirteen malformed manifest variations, shell-stage early failures, original
  full-command preservation and fail-closed aggregate status. `bash -n` and
  `git diff --check` pass.

[Summary](ci-core-shards-20260928/summary.json),
[full baseline IDs](ci-core-shards-20260928/baseline-ids.json),
[lane1 manifest](ci-core-shards-20260928/core-shard-1.json),
[lane2 manifest](ci-core-shards-20260928/core-shard-2.json),
[focused results](ci-core-shards-20260928/focused-frozen.log),
[source/evidence seal](ci-core-shards-20260928/seal.json).

The first historical-log parser required trailing ellipses on the test-name
line and recognized1,662 IDs. Tests with docstrings put the ellipsis on their
next descriptive line. Its assertion failure and435 omitted IDs are retained;
the corrected parser reads the qualified test-name line and proves exact2,097
identity. The initial discovery and both shard manifests were already complete
and remain unchanged.

Actual lane duration and artifact transport still need exact-head CI after
independent finished-diff refutation. Count balance does not promise equal
execution time. No timeout was increased and no prior failed run is relabeled.
Runtime: `/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/ci-core-shards-20260928/`.
