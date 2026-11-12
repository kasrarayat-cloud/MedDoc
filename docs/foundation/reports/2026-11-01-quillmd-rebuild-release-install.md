# QuillMD rebuild code-only release: install report (2026-11-01, 67acb2628 to c8b54991)

Declaration: `docs/foundation/mutations/20261101-quillmd-rebuild-release-797199c7c625.md` (commit `4fc8bc7e3`, committed
2026-11-01T18:38:44Z, merged by PR #1456 as `c8b54991`). Runbook: `docs/runbooks/rebuild-release-install-20261031.md`.
Owner: session 1bf3b49c, the single integration and deployment owner (interpretation 64). Interpretation 70 records the
release's scope.

## Result

**Installed.** The act ran from 2026-11-01T19:36:12Z to 19:38:53Z (runner exit 0); the owned units were stopped at
19:37:45Z and resumed at 19:38:26Z. `https://app.quillmd.com/health/` reports
`{"status": "ok", "data_mode": "synthetic-only", "surface": "doctor", "release": "c8b54991c1149789c000cb4a47f269bf1d18670f"}`.

## Sequence

| step | when (UTC) | outcome |
|---|---|---|
| 2 backup + isolated restore check | 10:50:54 to 11:17:53 | complete; backup `20261101T105056Z-c8423457` (48 tables, 233,049 rows, 1,272 files, 97,619,512 bytes); restore `bd7ff3cb2254fdc3` matched every table and file, network none, container not retained |
| 3 preflight of record at `CODE` 797199c7 | 18:36:23 to 18:37:22 | exit 1 with exactly the three expected declaration rows failing; the contract as the runbook expects |
| 4 declaration PR #1456 | 18:38 to 19:02 | one file; CI 2 of 2; merged as `c8b54991`; `diff CODE CANDIDATE` is exactly `A` of the declaration |
| main CI on `c8b54991` | to 19:34:49 | `check-citation.sh`: 2 of 2 |
| 6 final preflight | 19:35:10 to 19:36:00 | exit 0, 35 of 35 rows PASS; `MANIFEST` `18cd1a1e0d10dd2c8a18242d5a4516e2ada8855b670ba86169ee2154868bd56e` |
| 7 the act | 19:36:12 to 19:38:53 | exit 0; detached (`setsid --fork`), ceiling 86400 s; no signal; no other operator process ran |
| 8 verification | 19:39 to 19:50 | every structural row matches (below) |

`main` was frozen from 18:37:22Z (step 3) until this report's merge. No other session ran on the host and no pull request
had auto-merge enabled (checked 18:16:41Z, recorded in the operator's freeze log).

## Receipts (sha256)

```
f124c44c21cd6f7d0afa0ad43fc6535536ffc29f3e5b7e0575e38ae569f92b78 backup-report-01.json
4f6eff24e7cad4dfaaac3def3a47d5630c12fe77572099b248233f9b2c11fb27 preflight-01.json
c1ab7310560388ed360b39d8f246a331e7e11e0fcc4ddecb260f5ea53cc623eb preflight-02.json
a50a132915c5d18e7687a20e9e71188c654a3f68b9d59a6ead26c925f12d7903 act-01.json
9097b9b6041276df73760e5ff164978354a871c5d1bcb6064111700d9c01ff67 act-01.transcript
71c744dfe1a33f2c8dbe9f6eb992ab95ab5cc8272d729dc746087e8bc8e0e573 evidence/act-01/baseline.json
26bbfed45217392a795454b2f1cf1ae80969d00be0a5eacc38b1edb6dd767ed6 evidence/act-01/database-after-stop.json
26bbfed45217392a795454b2f1cf1ae80969d00be0a5eacc38b1edb6dd767ed6 evidence/act-01/database-before-resume.json
ecad98d7ab86026e97856fe00f6ec8e9f57d3d45b47ad7a090f1d659009691fc evidence/act-01/installation-complete.json
afca7989d619db8b68021aef7240d0f0257f43ba9a57212adeaed9c7e8774e60 evidence/act-01/plan.json
e0eda19acc6886e224aa6a0f352a8514b05caaef70faf042ac434d28a7f6e628 evidence/act-01/preflight.json
9f5b2c08b8535e3484479a7b05e7e1f4b68ab496d92a55c47cbe0c65024f8197 evidence/act-01/pre-resume-preservation.json
7d7b48561f9cfe18919ce1971987bb37fb964d06f120c0f91f5ad1cc1452e44a evidence/act-01/rollback-readback.json
9e4c6befd48e63f78384e4328ca3020d8346491779b289fdafbc2adad00adeef evidence/act-01/venv-before.json
884ef8e1297ffa532ff4ee4a8ccb286ac0731eb5e7f21ef326e94a1da63cdba1 evidence/act-01/environment-after.fernet
4d6a83ad180642b019371d96e51f54857dc3d76837c3073066dbcb99608e93a6 evidence/act-01/environment-before.fernet
```

The receipts stay in the operator's private (0700) report directory on the host; they are not committed here. The two
`.fernet` files are the encrypted environment snapshots; nothing of `rebuild/.env` was read in clear by this session.

## Judged against the declaration, every row

| declared | measured | |
|---|---|---|
| shared tree fast-forwards to `CANDIDATE`, tracked-clean | `main` at `c8b54991`, 0 tracked changes (`git --no-optional-locks`) | match |
| `QUILLMD_RELEASE_SHA` becomes `CANDIDATE`; health reports it | receipt `environment_delta` `["QUILLMD_RELEASE_SHA"]`; health release `c8b54991` | match |
| the three owned units restarted and active | admin, doctor and worker running under new main PIDs started 19:38:25 to 19:38:26Z (before: 10317, 10318, 10319) | match |
| venv footprint unchanged | `976009db259506a4…`, 64 distributions, 63 unrecorded bytecode, before and after; receipt `venv_change: null` | match |
| no dependency install, no migration, no provider request | receipt `dependency_installs: 0`, `migrations_executed: 0`, `provider_calls: 0`, `clinician_decisions_created` recorded | match |
| every row count unchanged except health ticks | `database-after-stop.json` and `database-before-resume.json` are byte-identical (`26bbfed4…`); postcondition `after_stop_database_exact_before_resume` | match |
| configuration, clinical files, static inventory unchanged | postconditions `configuration_preserved_after_resume`, `configuration_and_files_exact_before_publication`, `static_sources: []` | match |
| foreign services and the Corti candidate units unrestarted and idle | postconditions `foreign_services_preserved_after_resume`, `venv_sharing_units_idle_after_resume`; the Corti units still run as PIDs 10102 and 10103, started 2026-10-30 22:01:14 | match |
| worker limits unchanged | `memory.max` 1073741824, `memory.swap.max` 0, `pids.max` 64, `Max core file size` 0 | match |
| requirements mismatch exactly filelock, msgpack, pypdf | filelock 4.0.0 vs 4.2.1, msgpack 1.2.2 vs 1.2.3, pypdf 6.21.1 vs 6.21.4; nothing else | match |
| no signal | `signals_received: []`, `signal_records: []`, `interrupted: null` | match |

No difference outside the declaration was found.

## Judged checks, recorded separately

- **P1 on the installed bytes (offline, not HTTPS).** The 38 fixtures of the independent builder were run through the
  shared tree's installed `documents.check_original` (the live tree's files, a throwaway interpreter on the live pypdf
  6.21.1, `-B`, nothing written into the tree). Every fixture carrying a hidden script was refused: the 18 bypass shapes,
  the 2 fail-closed shapes (script inside an undecodable object stream), the control (well-formed, script reachable) and
  the negative (the root-object-recovery shape the base accepted as `supported`). Of the 9 benign files, 7 were accepted
  and 2 (a corrupt cross-reference entry, an inert dropped previous stream) refused as `unreadable_pdf`, the documented
  fail-closed class already left to the owner; the 7 fixtures expected to be refused were refused.
- **Not exercised: P1 through HTTPS on the synthetic account, and the first fresh synthetic extraction under PR #1434's
  instructions.** This session has no sanctioned credential path to an authenticated synthetic session on the rebuild,
  and it does not read credentials it was not given. Both stay unverified until someone with that access runs them; the
  structural rows above do not stand in for them.

## Not claimed, and what remains

- No pypdf, filelock or msgpack move: the venv keeps 6.21.1, 4.0.0 and 1.2.2, and the dependency audit of the live venv
  stays red until D1b, whose act code is not built.
- The rebuild's pypdf 6.21.4 compatibility repair (`fix/rebuild-pypdf-6214-compat-20261101`, pushed, unmerged) is not
  in this release and its refutation did not run (interpretation 70).
- P1's recorded limits stand: PG-1, GR1-UPLOAD-FILL, F1, F2, and the six ordinary pypdf-incremental files refused
  (`docs/rebuild/security-readiness.md`).
- Scheduled rebuild backups still fail (since 2026-10-12, `backup_timeout`); this act took its own manual backup. The
  schedule's repair goes to the owner (interpretation 67's addendum).
- The reverse act is not implemented; a failure from here is answered by a newly declared corrective act.
