# Independent retention repair refutation — 09487a39

**One remaining scope/lifecycle failure.** Frozen source `09487a390a0da41aa49f36fff424bde00f2aba58` was read from a clean isolated snapshot. Nineteen bounded controls: **18 PASS / 1 RED / 0 instrument errors**. No source changes, provider calls, corpus access, production target, or full suite.

## Closed demonstrations

The original ten inputs were replayed unchanged apart from isolated database/source/output namespaces: all ten pass. Both earlier deletion cases now retain the bytes and register the file after release. Earlier evidence remains sealed.

The restore reader independently passed a present archived-only input path with no file-registry row, failed after those archived bytes were deliberately removed, and passed after the exact bytes were restored. A separate archived original-file hash control passed, failed after byte tampering, and passed after restoration. These are local verifier controls, not a restore admission.

## Remaining concrete failure

Locations: `rebuild/core/retention.py:97`, `:179`; `rebuild/core/migrations/0025_preservation_guards.py:54`, `:56`; real reaper caller `rebuild/core/jobs.py:758`.

Case18 performs:

1. Create a patientA hold and upload synthetic bytes through the real `store_upload`; the pre-file ledger correctly records no exemption for this active hold.
2. Record the correct encounter ownership in an expired over-limit upload audit event.
3. Release through the second administrator.
4. Reassign the encounter to patientB in the same department. The ordinary database constraints allow this after release, and no prior encounter row is archived.
5. Invoke the actual abandoned-upload reaper.

**Observed:** reassignment succeeds, current-scope historical-hold count is zero, archived encounter-row count is zero, reaper removes one file, and the held bytes are absent. The new birth ledger does not preserve the historical scope identity. Looking up old holds through current encounter ownership loses the original patient hold after the permitted reassignment.

**Base comparison:** this is a remaining instance of the previously demonstrated hold/release lifecycle class. It is not claimed as a new regression caused by09487a39. The earlier same-scope failures are closed; that closure does not cover post-release scope changes.

Other bounded controls pass: real uploads after a committed release can be cleaned in that same scope; uploads during a hold survive release; an earlier release exemption cannot defeat a later hold; file keys cannot be reused; birth audit update/delete is refused; unknown old-file ownership remains conservative; creation waits for a concurrent release commit and records that release before bytes exist. No broader authorization or concurrency theorem is claimed.

## Retained evidence

Private runtime: `/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/retention-rerefutation-09487a39`.

- `probes.py` / `02-probe-results.json`: ten unchanged controls.
- `repair_probes.py` / `03-repair-results.json`: restore and birth/scope/release controls; exact failing case18.
- `launch.py`: fresh database `custodian_retention_09487a39_20260928`, assigned loopback55705, fixture AI, isolated state, private credential loading. Python network calls denied; no network attempt recorded.
- Source identity manifest SHA256 `f17942f2f334c73ad572cc574538fdd3a7ab54c44a928e2ded6a4d3cf39c2f7e`.
- Evidence seal SHA256 `ba7805174f0a305b7c9af855d0cd7d11db675c3e597814448ae097f786d8e2fc`.

Source hashes: retention.py `e74c9e6dc6c8b75f7e80e677c3d27052ef93bb11943e4d47d28dc56d367112f6`; restore checker `216621dacc9d96cdf297d125e6437125cbc0652f5afc5a53bf31a58d099ee2b2`. Root received case18 before any repair. Every prior failure remains preserved.
