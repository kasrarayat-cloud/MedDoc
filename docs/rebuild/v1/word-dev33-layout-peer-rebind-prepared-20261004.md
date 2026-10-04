# Reauthenticated peer metadata preparation — 2026-10-04

Root's exact original socket-replacement replay passes on integrated `5bf30245`: the real recorded peer is accepted, a replacement PID with the same UID is refused while the recorded process stays alive, and both owned test children are reaped. The original failure remains in `B/root-layout-peer-replacement-9173`; the distinct successful replay is `B/root-layout-peer-replacement-fixed-5bf30245`, where B is `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z`. Neither replay sends a document or accesses QA/provider state.

The derivative is now `dev33-supported-layout-peer-v3`, with helper SHA256 `00a5c8eb0a9bf944fe22d06ae552a9ed4a42ff73bf527287cef5f813d4b66d49` and prepared-plan SHA256 `b5e20bc3eee78e53e541ba380e18aa3e77e1da8130994dc8d6f89a64653cb1f1`. Its original prepared-plan reference remains `e1ca082b8c7ddff09a054cf9f581ef6bbbbb4c35b693380b1bc698ef90822d39`. Only the added version/helper/driver-source declarations change; every original preparation value remains equal. Final source, worktree and execution authority remain unset. The provider freeze at 5bf is not the final Word source freeze.

Five fresh owned driver copies are in `B/operations/dev33-supported-layout-prepared-20261004-v3`; earlier v2 copies, original derivative bytes and all five partial S2 packets remain untouched. Four drivers change only the old helper-hash literals to the repaired hash. The checker is byte-identical. Tracked `.source` copies under `docs/rebuild/v1/word-eval/dev33-supported-layout-preparation-v3-20261004` have exactly the same bytes, so CI validates portable source evidence instead of trying to read task-local O paths. Actual execution still authenticates the protected paths through the prospective seal; tracked copies are not launched by tests.

| Driver | SHA256 |
| --- | --- |
| `run_dev_application_gate_v2.py` | `a7059768fc9b4208ab639a5acb6fff7ed7a8f780597506b18c122636afa1fcb7` |
| `dev_application_gate_v2.py` | `fbf37994963d6a39ba546eb35e5bec7a3967e545a707ab253c746be9f45ab918` |
| `run_dev_application_gate_native_v1.py` | `fe47f9d20b2a2820b21621486d02744dd4ca55d38825ab224a84408fd9b74da5` |
| `dev_application_gate_native_v1.py` | `3de3c34f5451b57fbf3a65b92294ea7cb242b38431f19242ca881d3635d500c5` |
| `fixed_render_checker.py` | `a1cd77577e266b25f8c42d01a5aba7fd4f05ea042eee50822ac944e09e09aa0e` |

The mixed metadata adapter SHA256 is `66e7791f2b8b964563278e548981c5c5ae0273ad48f2b97d10ff1a08bca5eccf`; only VERSION/PREPARED_SHA/PEER_SHA/DRIVERS declarations change. The outer supervisor SHA256 is `c2c5a3dfa26957646a6c3317b3dd39cb3cf24138439d63cf3cf7c6504092024f`; only its two pinned driver hashes change. All helper function ASTs, scoring/profile functions, exact 17 memberships/33 originals/seven holds, ground truth, family criteria and 54/60 plus 18/20 thresholds remain unchanged. New negative controls refuse the old helper hash and version.

The three affected pure modules pass 97 methods, actual exit 0 in 0.641 seconds, outer 0.695 seconds. All 12 recorded source/literal files remain unchanged before/after. Evidence is `B/operations/dev33-supported-layout-prepared-20261004-v3/pure-finished-proof`; result SHA256 `7e96313cf70c44eb0b6b99d525cbb607c2fbcf50dde45b70acfd27cb09b3a50b`, raw log SHA256 `93ab7cc0169e2aba8d2e10e58642a794c49684cefbcacab2c4dac308f3e09327`. An initial preparation-script SyntaxError occurred before any write or child launch and is retained separately as `initial-instrument-syntax-error.json`. No original outcome is overwritten.

No actual DEV packet, application renderer, database, provider request, credential, financial pin, installation or cleanup follows from this preparation. Root's finished metadata refutation, coherent Word source freeze, exact new source/seal hashes and explicit serialized resource handoff remain required before the prepared 17 invocation commands can run. The fixed whole-document gates remain unmet; seven held originals retain their denominator and holdout 20 is unexecuted by this preparation.
