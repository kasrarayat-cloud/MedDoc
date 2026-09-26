# Result — nine superseded WM narrative Word engine builds removed, September 26, 2026

Declaration: `docs/foundation/mutations/20260926-quillmd-wm-narrative-obsolete-engine-builds.md`, committed `c6f632da`
at 2026-09-26T22:54:50Z. Authority: `docs/foundation/rulings/2026-09-26-owner-cleanup-authority.md`.

## The act

Executed by the owner through `scripts/run-ruled-mutation.sh`, reported as completing at **2026-09-26T23:19:01Z with
exit 0**. The door's transcript went to the owner's terminal, not into this record; its watchdog log file
(`/tmp/tmp.e8hVvkQfJk`, created 23:19:21Z) is empty, as it is for a command that prints nothing. The act followed the
declaration's commit by 24 minutes.

⚠️ A first request to run it (22:5xZ) was never executed: at 23:16Z the nine directories were unchanged, no bash-mode
entry was in the session and no watchdog log existed, and the session reported that rather than assuming success.

## Judged against the declaration (2026-09-26 ~23:20Z)

MUST change:

| declared | measured |
| --- | --- |
| the nine directories gone | **gone** — `rebuild/.runtime/` now holds `nuget-cache`, `proofs`, `publication`, `word-narrative-build-10` |
| used space falls by about 1,731 MB | 261,736 MB used at 23:16Z → **260,038 MB** at 23:20Z: **−1,698 MB** (90.36% → 89.77%, 29.6 GB available). The 33 MB short of 1,731 is co-tenant writing in the four minutes between, which the declaration named as the reason to judge on the paths' size and the used-space change together. Against the 22:53Z baseline (261,546 MB) the fall is 1,508 MB, the rest of the gap being co-tenant growth over 27 minutes |

MUST NOT change:

| declared | measured |
| --- | --- |
| build-10 `runtime-manifest.json` `2a1e4477…d756` | `2a1e4477144207bed04d3f3d38cb3b276cdaf7e450ef7d622f1ee63cd4e0d756` — unchanged |
| build-10 `build-proof.json` `9ded38e9…dbca` | `9ded38e9e3f0c6271ce2551ef8adaaa8fbb83ecde7b7bfb0d836365b55c0dbca` — unchanged |
| preserved proofs listing `971d9c74…1431` | `971d9c74d7b198150fcd8a4465dc6ad5e01866e205c4956179ac51439bcb1431`, 18 files — unchanged |
| `nuget-cache`, `publication/`, `proofs/` | 331 MB, 1 MB, 1 MB — unchanged |
| production | shared tree `dedac162`, private services 9130/9131 `200`, public maintenance `503`, every co-tenant at its expected status — unchanged |

Nothing outside the declaration changed. Preflight afterwards: `docs/preflight-reports/preflight-20260926T232027Z.md`
(🟡, disk below the line with a thin margin; swap full).
