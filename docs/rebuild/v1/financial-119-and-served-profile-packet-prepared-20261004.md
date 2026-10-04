# Financial recovery and served profile packet — prepared 2026-10-04

The existing 119-selector universe is unchanged: 24 pure scanner/witness checks, 67 historical profile/wire/metering checks and 28 persisted quote/hold/settlement/payer checks. An AST-only read of finished financial source `d320d11e381bf7f9d9906de6765bd168925bdb2b` found all 119 exact selectors once, with all 119 original test-method ASTs unchanged. This is discovery evidence, not a test pass.

The concrete command packet uses normal `unittest` or `manage.py test` plus the existing protected QA wrapper and task-owned catalogue reader. It adds no runner framework. The source worktree, full commit, source seal and integration-owner execution grant remain **null**. Bind and seal those before execution, use distinct outputs and the allocated `quillmd_qa_sol_ops_fin{1,2,3}_20261004` databases, and serialize each packet. Bounds are 180 seconds for pure checks and 600 seconds for each Django packet, followed by bounded reaping and independent 30-second normal/test database absence checks. Preserve original child failures, both actual exits and source bytes; catalogue success cannot turn a failed child green. Provider transports are mocked and no provider request belongs to these checks.

Protected preparation root:

`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/financial-119-final-packet-prepared-20261004`

| Artifact | SHA-256 |
| --- | --- |
| `packet.PREPARED.json` | `c5687b1f548ba3391c92bbb5c694194be94ffc35a79ddc8517f2ccf56dbfbfa2` |
| `commands.PREPARED.txt` | `9e286fea84e9e238817a748beb7a929dc2d5138142a5aaf83d469c6d3047c6c5` |
| Original source-only health mismatch | `5e95cb5f4d52ed914518318e1603656a114590de3667b819896f6280edc1dd69` |
| Focused helper/syntax receipt | `184dbe54d8cc308071bba2aa35ef2d5fccf31ea4f01053c83e32912f719a5053` |

The original helper expected health `data_mode=synthetic`, while the actual `health_data_mode()` returns `synthetic-only`. The retained source-only equality counterexample is preserved; no served failure is inferred. The helper now checks the actual exact health contract on both hosts and rejects the old label, real/live data mode, stale release, opposite surface and extra identity. It also requires the normal demo's `auto` Word engine and records the actual application settings and both served health responses. Ten focused helper tests passed, actual exit 0 in 2.545 seconds; Node's browser-script syntax check passed. No QA database, renderer, provider, installation or browser run occurred in these checks.

The future CI private-browser job now explicitly presets fixture Anthropic/Sonnet 5.5, between-tools/medium, the declared 2/10/0.20 rates, `WORD_ENGINE=auto`, `V3_FIELD_RELATIONS=1`, and the actual job's full release SHA. Doctor and administrator remain separate processes on 9130 and 9131. Browser execution will retain the actual `/health/` responses, served administrator language-model/gate rows and database single-worker-lock status in `browser-artifacts/report.json` as `served_profile`, with live-model qualification false. It rejects a wrong host/release, live mode, base/8k profile or absent worker lock before a green result. The new demo uses its separately prepared normal launcher on 9160/9161, and its persisted reader additionally binds the actual doctor/admin/worker PIDs, immutable archived source, database, finalized records and downloaded bytes.

These two new browser assertions supplement the historical 15-check browser result at `7907ae5a`; that earlier legacy/gpt-4.1-mini fixture run is not relabeled ordinary-v4. Actual final-revision CI and private demo served/persisted verification remain pending. Required CI remains the normal `CI` and `secrets-scan` workflows, and fixture settings do not prove a live Sonnet 5.5 response.

The retained B2 policy SHA `742f57d226a44fcb2d0b764e9e9febec00458e3dbee92bd9eafa9bb3d96df7b2` expired `2026-09-23T22:05:53.615210Z`; the scheduled October 3 refusal and previous September 23 remote readback/restore scopes remain unchanged. The existing [owner handoff](private-fixture-factory-20261004/OWNER-EXTERNAL.md) and [served verification checklist](private-fixture-factory-20261004/SERVED-VERIFICATION.md) apply. Added disk and this preparation renew neither offsite coverage nor alert delivery; no new drill or email is required here. Dashboard status must be read on the future actually served revision before being called verified.
