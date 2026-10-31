# Rebuild release install, code only (2026-10-31)

This runbook installs the next rebuild release from the served revision (`BASE`) to `origin/main` (`CANDIDATE`)
with tracked tools only. It is bound by interpretation 67
(`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`):

- **D1, code only.** The live venv `/opt/meddoc-pro/rebuild/.venv` stays exactly as found: pypdf 6.21.1,
  filelock 4.0.0, msgpack 1.2.2 and the 63 unrecorded bytecode files. A full footprint is taken before and after
  the act. `rebuild/requirements.txt` will name newer versions than the venv. That mismatch is declared, not
  refused. The dependency move is a later, separate act (D1b).
- **D2.** No rollback ever downgrades the venv.
- **D3.** The Corti candidate units and every other foreign service stay running and unchanged. The act checks
  that they are idle and unchanged before it starts and again after the resume.
- **D4.** The declaration is merged to `main` through a PR before the act, so the candidate contains it.

| tool | what it does |
|---|---|
| `rebuild/ops/rebuild_release_backup.py` | One locked encrypted backup plus an isolated restore check, written up as a private report. |
| `rebuild/ops/install_rebuild_release.py` | Without `--execute`: a real, read-only preflight that prints the plan and the declaration contract. With `--execute`: the act, and only under `scripts/run-ruled-mutation.sh`. |
| `rebuild/ops/venv_footprint.py` | The exact, read-only venv footprint and census used by both. |
| `rebuild/ops/rebuild_dependency_stage.py` | D1b only, later. It is not used by this act. |

The installer binds the sha-pinned tracked engine (`activate_core_workflow_repair.py`, 436acf8f…) and its seven
primitives, and runs their checks and actions in the engine's own order:

- locks;
- baselines of the database, clinical files, configuration and foreign services;
- stopping the three owned units through the root docker helper;
- `git merge --ff-only` in `/opt/meddoc-pro`;
- a rewrite of `QUILLMD_RELEASE_SHA` only, through the engine's renderer;
- starting the worker, then the doctor and the admin;
- HTTPS health on the candidate;
- automatic recovery only when the act fails before publication.

It does not call the engine's `execute()`. That function's declaration check (line 193) needs the candidate's own
sha inside the declaration, which D4 makes impossible. The module docstring explains this, and a unit test pins
the stage order to the engine's.

## Roles and standing rules

- One integration owner (interpretation 64) runs every step and reads each output before starting the next. Nothing
  is retried automatically.
- `main` is frozen from the preflight of record (step 3) until step 9. Write the freeze in the log before step 3 and
  tell the parallel sessions.
- The shared tree `/opt/meddoc-pro` is never checked out or written by hand. Every git write happens in a worktree.
  A `fetch` from any worktree updates the shared remote-tracking refs.
- Prose goes by file only: `git commit -F`, `gh pr create --body-file`.
- Before any push or merge, take both views (`gh run list --commit <full sha>` and `gh run list --branch <branch>`).
  Merge only with `bash scripts/merge-pr.sh <n>`.
- Do not run tests, pip or Python without `-B` in a worktree whose `rebuild/.venv` links to the live venv, at any
  time between step 3 and step 8. `scripts/setup-worktree.sh` creates such links. A stray process on the live venv
  refuses the preflight, and new bytecode changes the footprint.
- Run no synthetic workflow, upload or provider call during step 7. The engine's database baseline is taken while
  the units still serve, and any row written before the stop, other than a health tick, refuses the act. That
  refusal comes before publication, so the original release is restarted automatically.

## Values

```
BASE=<shared tree HEAD = served release, 40 hex>      # 67acb2628b84c2be25f379a15168aa802350c060 on 2026-10-31
CODE=<origin/main once P1 and this installer are merged, before the declaration, 40 hex>
CANDIDATE=<origin/main after the declaration PR, 40 hex>
DATE=<YYYYMMDD of the act>
PY=/opt/meddoc-pro/rebuild/.venv/bin/python           # always with -I -B
R=<a new private directory for reports, mode 0700>
DECL=docs/foundation/mutations/$DATE-quillmd-rebuild-release-${CODE:0:12}.md
```

The declaration's file name carries `CODE`, never `CANDIDATE`: the candidate is the commit that contains it.

## 1. Code worktree at `CODE`

```
git -C <any worktree> fetch origin main
git -C <any worktree> worktree add --detach /opt/meddoc-pro/.worktrees/rebuild-release-code-${CODE:0:12} $CODE
C=/opt/meddoc-pro/.worktrees/rebuild-release-code-${CODE:0:12}
```

Use a plain `git worktree add`. Never use `setup-worktree.sh` here: the worktree must not link the live venv.

## 2. Backup and isolated restore check (about 25-40 minutes)

Run it outside 04:20-04:50Z and 04:55-05:10Z. The step holds the four operation locks for its whole run, so
backup-alert checks skip meanwhile.

```
mkdir -m 0700 /opt/meddoc-pro/backups/rebuild-release-$DATE
cd $C
$PY -I -B $C/rebuild/ops/rebuild_release_backup.py \
  --output /opt/meddoc-pro/backups/rebuild-release-$DATE/attempt-01 --report $R/backup-report-01.json
# read the printed checks and the two exact commands, then:
$PY -I -B $C/rebuild/ops/rebuild_release_backup.py --execute \
  --output /opt/meddoc-pro/backups/rebuild-release-$DATE/attempt-01 --report $R/backup-report-01.json
```

What the step does:

- It runs the installed `/opt/meddoc-pro/rebuild/ops/backup_restore.py backup` with the scheduled capture's
  arguments, but without the 540 s cap. A 4-hour ceiling remains.
- It then runs `restore-check` and makes a read-only daemon query proving the drill container is gone.
- The key file and the role file are passed as paths. Only the tool opens them.

**STOP** if:

- the exit code is not 0;
- the report says `"complete": false`;
- an `INCOMPLETE` marker exists;
- `drill_container_absent` is not true. Inspect first, then remove only that labelled, network-less drill
  container.

Never reuse an attempt directory: a second attempt is `attempt-02` with a new report.

## 3. Preflight of record at `CODE` (read-only)

```
cd $C
$PY -I -B $C/rebuild/ops/install_rebuild_release.py --base $BASE --candidate $CODE \
  --declaration $C/$DECL --backup-report $R/backup-report-01.json --result $R/preflight-01.json
```

**Expected result: exit 1, and exactly three FAIL rows:** `declaration_provenance`, `strict_declaration_gate` and
`declaration_contract` (`declaration_not_in_candidate`). Every other check must PASS:

- the candidate worktree;
- the shared tree clean on `main` at `BASE`;
- `origin/main` equal to the candidate, locally and on the remote;
- no merge-time hooks;
- the manifest and the requirements rule;
- the venv footprint and the requirement pins;
- the owned units active;
- the foreign services, the venv-sharing units and their idle window;
- no undeclared live-venv process;
- health serving `BASE`;
- the locks free and the scheduled windows clear;
- the backup report;
- the release-stamp render;
- the read-only database baseline and no pending provider work;
- the engine's own source plan (every base file proven);
- the citation (2 of 2);
- the operator hashes.

**STOP** if any other check fails.

The command prints the contract block to embed. Read it against these expectations, and STOP on any surprise:

- `requirements_mismatch` names exactly filelock, msgpack and pypdf;
- `venv` shows 64 distributions and 63 unrecorded bytecode files;
- `foreign_venv_units` lists exactly the two Corti candidate units;
- `static` is `[]` (otherwise every name in it is a declared static publication);
- `runtime_paths` lists P1's files, `rebuild/core/source_assertion_generation.py` (PR #1434),
  `rebuild/requirements.txt` and the new operator modules.

## 4. Declaration PR

Write `$DECL` from a new branch at `CODE`. It contains the contract block from step 3 verbatim under its marker,
plus the sections of `docs/foundation/mutations/20261031-cpt-studio-gi3-upgrade.md`:

- authority (interpretations 62, 64 and 67);
- revision and how it is executed (this runbook's step 7, verbatim);
- the FULL delta by class: P1, PR #1434's instruction text on the clinical generation path with its October
  refutations cited by blob, `requirements.txt`, the operator modules, and the cpt-studio, docs and CI passengers;
- the baseline: every table's row count from `preflight-01.json`, clinical counts included, plus the venv summary,
  the foreign units and the backup facts;
- what must change: the shared tree fast-forwards to the candidate, and `QUILLMD_RELEASE_SHA` becomes the
  candidate;
- what must not change: the venv footprint, every row, clinical file, configuration hash, foreign service, static
  asset and migration;
- that nothing is sent to a provider;
- the validation;
- the rollback and its limits;
- what is not claimed: no pypdf move, no clinical acceptance;
- every STOP condition below.

The PR must add **exactly one file**. A merge that brings anything else makes the act refuse
(`declaration_is_the_only_delta`), and so does any other merge to `main` in between: start again from step 3.

Merge the PR with `scripts/merge-pr.sh`, wait for the merge commit's CI, then:

```
git -C $C fetch origin main
CANDIDATE=$(git -C $C rev-parse origin/main)
git -C $C diff --name-status $CODE $CANDIDATE         # exactly: A<TAB>$DECL
bash $C/scripts/check-citation.sh $CANDIDATE          # CI and secrets-scan, 2 of 2
```

## 5. Candidate worktree

```
git -C $C worktree add --detach /opt/meddoc-pro/.worktrees/rebuild-release-${CANDIDATE:0:12} $CANDIDATE
X=/opt/meddoc-pro/.worktrees/rebuild-release-${CANDIDATE:0:12}
```

This is a plain worktree, as in step 1. The act runs from here: the runner checks the declaration in this tree, and
the installer binds the engine from here.

## 6. Final preflight (read-only), no more than 30 minutes before the act

```
cd $X
$PY -I -B $X/rebuild/ops/install_rebuild_release.py --base $BASE --candidate $CANDIDATE \
  --declaration $X/$DECL --backup-report $R/backup-report-01.json --result $R/preflight-02.json
```

**It must exit 0, with every row PASS.** This includes:

- `declaration_contract_matches_measurement`: the embedded contract equals today's measurement, the code manifest
  equals the declared one, and the declaration is the only delta from `CODE`;
- `strict_declaration_gate`: the runner's own gate passes;
- `backup_report`: complete, intact on disk, restore passed, and no older than 12 hours.

Record `measured.manifest_sha256`; it becomes `MANIFEST`.

## 7. The act (about 5 minutes; the units are down about 1-3 minutes)

```
mkdir -m 0700 $R/evidence
cd $X && bash $X/scripts/run-ruled-mutation.sh --declaration $X/$DECL -- \
  $PY -I -B $X/rebuild/ops/install_rebuild_release.py --execute \
  --base $BASE --candidate $CANDIDATE --declaration $X/$DECL --backup-report $R/backup-report-01.json \
  --result $R/act-01.json --evidence-directory $R/evidence/act-01 --manifest-sha256 $MANIFEST
```

The installer refuses before anything if:

- it is not under the runner (`RULED_MUTATION_*` must name this declaration);
- its current directory is not `$X`;
- the evidence directory already exists;
- any preflight row fails;
- the manifest differs from `MANIFEST`.

Then it acts in the engine's order. It checks the venv footprint at the baseline, after the stop (before
publication) and after the resume. It checks the venv-sharing units for idleness at the baseline and after the
resume. It compares the foreign services at the baseline, after the stop, before the resume and after the resume.

| exit | meaning | next |
|---|---|---|
| 0 | `installation-complete.json`, every post-condition passed | step 8 |
| 2 | installed and serving the candidate; a post-condition the act cannot cause failed: foreign units not idle after the resume, or the venv footprint changed during the act | judge it from `installation-complete.json` (`postconditions`, `venv_change`). Do not re-run. |
| 1 | refused or failed | read `failure.json` first. If `publication_attempted` is false and `original-release-resumed.json` exists, the original release is back. If it is true, the units are drained and only a newly declared corrective act may follow. **Never re-run** an act whose evidence directory exists. |

Evidence (private, mode 0700): `plan.json`, `preflight.json`, `environment-before.fernet`,
`environment-after.fernet`, `rollback-readback.json`, `baseline.json`, `venv-before.json`,
`database-after-stop.json`, `database-before-resume.json`, `pre-resume-preservation.json`, then
`installation-complete.json`, or `failure.json` plus `failed-resume-drain.json`, `original-recovery-refused.json` or
`original-release-resumed.json`.

## 8. Verification (read-only)

- `installation-complete.json`: `installed_revision == CANDIDATE`, the health record, `dependency_installs: 0`,
  `migrations_executed: 0` and `all_postconditions_passed`.
- `https://app.quillmd.com/health/` reports the candidate, and the three owned units are active.
- `/opt/meddoc-pro` is on `main` at `CANDIDATE` and tracked-clean (`git --no-optional-locks`).
- The venv footprint equals the declared one:
  `python3 -I -B -c "import sys; sys.path.insert(0, '$X/rebuild'); from ops import venv_footprint as f; print(f.summary(f.snapshot(f.Path('/opt/meddoc-pro/rebuild/.venv'))))"`.
  It must report the declared `footprint_sha256`, 64 distributions and 63 unrecorded bytecode files.
- The Corti candidate units keep the MainPID and InvocationID recorded in `baseline.json`.
- The worker's cgroup limits are unchanged: memory 1 GiB, swap 0, 64 tasks, core 0.
- `requirements.txt` still differs from the venv in exactly the three declared pins. Report this; do not conceal
  it. The CPT Studio and rebuild dependency audits still flag the old versions until D1b.
- Judged checks, recorded separately from the structural ones: P1's fixtures through HTTPS on the synthetic
  account, and the first fresh synthetic extraction under PR #1434's instructions.

## 9. Records

Through PRs only:

- the install report under `docs/foundation/reports/`, quoting the receipts by sha;
- any interpretation rows;
- then lift the freeze.

Reap only this session's scratch. Never reap a worktree that holds a declaration, an attempt directory or an
evidence directory.

## The rollback act (a separate declared act; not implemented by this installer)

`install_rebuild_release.py` refuses deletions, so it cannot reverse itself. A reverse act has this shape:

- **Its own declaration** under `docs/foundation/mutations/`, merged before it (D4). It names the forward evidence
  by sha: `plan.json`, `installation-complete.json`, `baseline.json` and `pre-resume-preservation.json`.
- **The source moves from `CANDIDATE` back to `BASE`.** On clean `main` at `CANDIDATE`, with the index equal to the
  candidate tree and no reference-transaction or other merge-time hook:
  - run `git restore --source=BASE --staged --worktree -- <every manifest path>` (this restores the modified paths
    and removes the added ones);
  - then compare-and-swap with `git update-ref refs/heads/main BASE CANDIDATE`;
  - this is the October operator's `reverse_publish` shape around `legacy.restore_source`.
  `origin/main` stays where it is.
- **The release stamp goes back to `BASE`**, through the same renderer.
- **The same locks, baselines, foreign-service checks and venv-footprint checks** apply, the worker is resumed
  first, and health must report `BASE`.
- **No pip, ever (D2).** The venv stays exactly as found. After this code-only act the venv already matches `BASE`'s
  pins, so the reverse has no mismatch. After D1b, a reverse keeps the patched packages and declares the mismatch.

That reverse mode needs its own tracked code, a refutation pass and a review before it can be used. Until it
exists, a failure after publication is answered by a newly declared corrective act.

## STOP conditions

| when | stop if |
|---|---|
| any time | Another merge to `main` happens after step 3, the shared tree leaves clean `main` at `BASE`, or anyone runs pip or tests on the live venv. |
| step 2 | Any non-zero exit, an incomplete report, an `INCOMPLETE` marker, a restore that is not complete, a retained drill container, or a run inside a scheduled window. |
| step 3 | Any FAIL other than the three declaration rows; a requirements mismatch other than filelock, msgpack and pypdf; a static name or a migration; venv-sharing units other than the Corti pair, or not idle; undeclared live-venv processes; locks held; pending provider work; a citation that is not 2 of 2; a contract that surprises the reader. |
| step 4 | CI is red on the PR or on the merge commit; the merge adds anything but the declaration; `diff CODE CANDIDATE` is not exactly `A $DECL`. |
| step 6 | Any FAIL, a backup report older than 12 hours, or a contract mismatch (the venv, foreign units, backup or code changed since step 3: redo steps 2-6 as needed). |
| step 7 | Exit 1 (read `failure.json`; never re-run); exit 2 (judge; units are serving the candidate). |
| step 8 | Health is not the candidate, a unit is inactive, the venv footprint changed, a Corti unit restarted, the shared tree is not clean `main` at `CANDIDATE`, or the mismatch is not exactly the declared one. |

## What this act never does

- No pip; the venv is left exactly as found (D1, D2).
- No migration; a changed `rebuild/**/migrations/**` path refuses.
- No static publication unless the contract names it: flat `rebuild/static/<name>` only, through the engine's own
  static path.
- No unit-file change: `rebuild/deploy/**` refuses, and `/etc/systemd`, `/etc/nginx`, `/etc/ssh` and the Caddyfile
  are hashed and must not change.
- No provider call, no clinician decision, no restart of a foreign service.
- No backup: that is step 2.
