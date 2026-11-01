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

What the installer adds to that shape (the 2026-11-01 refutations, 22 findings and then 14 more, every one repaired
with a test):

- **Path guards.** A dot-named path component is admitted only where the base already tracks that path, or where
  it is a new file that the declaration's contract names exactly in `new_dot_paths` (step 3). No manifest path may
  have an existing prefix in `/opt/meddoc-pro` that is not a real directory (an ignored `rebuild/.env` or `.env`
  included), and no added path may already exist in any form (a dangling link included): `git merge` silently
  replaces an ignored file that stands in its way. No merge-time or maintenance hook (`pre-auto-gc` included), no
  gate instrument (`scripts/check-citation.sh`, `scripts/lib/runs-api.sh`, `scripts/lib/declaration.sh`,
  `scripts/run-ruled-mutation.sh`, `scripts/lib/run-watched.sh`, `scripts/lib/container-revision.sh`) and no
  `.gitattributes` in the delta.
- **Trusted gates.** The citation and the strict declaration gate run from the base's tracked copies in the shared
  tree, each proven byte-equal to its blob at `BASE` and pinned by sha256 in the plan. `origin/main` is read as
  `refs/remotes/origin/main` (nothing may shadow it) and as exactly `refs/heads/main` on the remote.
- **Git's own state** refuses, in the shared tree and in the candidate worktree the installer runs from: a lock
  that changes `git merge --ff-only` in that worktree (its own `index.lock`, `HEAD.lock` or `ORIG_HEAD.lock`, or the
  lock of the branch it has checked out, `refs/heads/main.lock` in the shared tree), an unfinished merge,
  cherry-pick, revert, rebase or bisect there, assume-unchanged or skip-worktree entries, and any `refs/replace`
  entry. Measured on git 2.43: with `index.lock` or `ORIG_HEAD.lock` held the merge refuses before changing
  anything; with `HEAD.lock` or `refs/heads/main.lock` held it moves the index and the working tree and then refuses.
  The locks that other worktrees' ordinary git writes take in the shared common directory (`config.lock`,
  `packed-refs.lock`, another branch's or a remote's ref lock) change neither the checkout nor the merge (measured:
  it fast-forwards as usual with each held). They are recorded as `observed_locks` and never refused. A rebase is
  unfinished only while `rebase-merge/` or `rebase-apply/` exists, which is how git decides. A lone
  `.git/REBASE_HEAD` is what a finished rebase leaves behind (`--continue`, `--skip` and `--quit` all leave it). The
  live repository has had one since 2026-08-10. It is recorded as `observed` in the row's detail. It is never
  refused and never removed.
- **No replace objects.** Every git process, the installer's own and every child's, reads the objects behind the
  certified shas (`GIT_NO_REPLACE_OBJECTS=1`, `--no-replace-objects`, `core.useReplaceRefs=false`).
- **The candidate worktree is proven before anything is imported from it.** Its git state must be clean, as above.
  Nothing untracked may sit in `rebuild/ops`, ignored files included: an extension module or a package directory
  there would be imported instead of the tracked source. No bytecode is read from the source tree.
- **Re-comparison after the stop.** The venv, foreign services, configuration, clinical files, git's state,
  `rebuild/.env` and the static inventory are measured again after the stop and before the merge. Publication begins
  only when git has moved `HEAD` or the working tree. A refusal before that restores the original release, a merge
  git refused included. First every child process of the act is reaped, so no merge can still be running. Then the
  original is measured intact: the engine's `verify_original_before_resume`, plus the same shared-tree measurement
  as before the merge, git's own state included. It is never assumed. While the only failure is a held lock that
  changes the merge, it is measured again every second for about 30 s before the units are left drained.
- **Exception-proof recovery.** Every unit gets its drain or restore attempt whatever happens to an evidence write
  or to releasing the locks. A restore counts only when every unit is active and health reports `BASE`. Every git
  process of the act runs with hooks, automatic maintenance and replace objects switched off.
- **Signals sent to the act's process are blocked, never handled.** Every signal that could end it (every
  catchable terminating signal and every real-time one; SIGPIPE stays ignored) is blocked for the whole act. They are
  taken only at checkpoints between stages and once more immediately before `git merge`. Before the merge, a signal
  takes the automatic recovery; from the merge on it is recorded and the act runs to completion (exit 2). **That is
  not a licence to signal it.** Under the runner a signal to the act's process group or to its parent `timeout`
  gets the act SIGKILLed 15 s later wherever it is, or ends `timeout` and leaves the act running unwatched; a group
  signal can also abort a unit action, because the docker helper client unblocks it; and Ctrl-C or a hangup in a
  terminal reaches only the runner. Nobody may signal the act. Step 7 has the details.
- **Nothing drains a healthy install.** After health on the candidate, these are reported for judgement (exit 2):
  a foreign restart, a failed configuration read, a signal, locks that could not be released, or a result file that
  could not be written.

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
  refuses the preflight, and new bytecode changes the footprint. The check reads each process's executable
  (`/proc/<pid>/exe`) and, for a bare `python3` started from an activated shell, its own `PATH`; an operator
  Python whose use of the venv cannot be determined refuses too. Other users' processes expose only their command
  line: they are decided by an absolute interpreter path and otherwise counted as `uninspectable_other_users`.
- Between step 3 and step 8, start every Python of your own uid with an absolute interpreter path. A relative one
  (`.venv/bin/python ...`, or a relative `PATH` entry) was resolved against the directory the process started in,
  and `/proc` keeps only the directory it is in now: a test that changes directory looks like it left the venv. Such
  a process is undetermined and refuses the preflight (`undeterminable_operator_interpreter_process`), whichever
  venv it really runs on.
- During step 7 no other operator process runs on the host: no other session or agent, loop, scheduled job of
  ours, cleanup or test, until the act has exited. Any of them could signal the act (step 7: nobody may) or take a
  git lock it measures.
- Run no plain `git` command in `/opt/meddoc-pro` during step 7 (use `git --no-optional-locks`): a plain
  `git status` takes the index lock, and a merge that meets it refuses. The act is then spent. It restores the
  original release only if git's state is clean again when the restore measures it: while only such a lock fails the
  measurement it measures again every second for about 30 s. A lock still there after that leaves the units drained
  (`original_recovery_refused` or `recovery: none`) until someone inspects them. A git write in another worktree takes
  its locks in the shared common directory (`config.lock`, `packed-refs.lock`, its own branch's or a remote's ref
  lock); those change neither the shared tree's checkout nor the merge, are recorded (`observed_locks`) and never
  refuse.
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
  --declaration $C/$DECL --backup-report $R/backup-report-01.json --result $R/preflight-01.json \
  --new-dot-path cpt-studio/.gitignore --new-dot-path cpt-studio/deploy/.dockerignore
```

Every run of the installer, a preflight or the act, needs a `--result` path that does not exist yet, in a private
(0700) directory: an existing one refuses before anything runs (`new_result_file`). A repeated preflight writes
`preflight-01b.json`, never over an earlier report.

**Expected result: exit 1, and exactly three FAIL rows:** `declaration_provenance`, `strict_declaration_gate` and
`declaration_contract` (`declaration_not_in_candidate`). Every other check must PASS:

- no git environment variable that redirects or reconfigures git (`git_environment_clean`);
- the candidate worktree: at the candidate, tracked-clean, git's own state clean (no hidden index entry), and nothing
  untracked in `rebuild/ops`. This row runs before any module is imported from the worktree; if it fails, the module
  and engine rows fail as `prerequisite_failed`;
- the shared tree clean on `main` at `BASE`, with none of the locks that change the merge (`index.lock`,
  `HEAD.lock`, `ORIG_HEAD.lock`, `refs/heads/main.lock`), no unfinished merge, cherry-pick, revert, rebase
  (`rebase-merge/` or `rebase-apply/`) or bisect, no assume-unchanged or skip-worktree entry and no `refs/replace`
  entry. The live repository's lone `REBASE_HEAD` appears as `"observed": ["REBASE_HEAD"]` in the row's
  `git_state`. That is expected: it does not fail the row. Do not remove it. A lock another worktree's git write
  holds in the common directory at that moment appears under `observed_locks`; it does not fail the row either;
- `origin/main` equal to the candidate, locally (`refs/remotes/origin/main`, unshadowed) and on the remote
  (`refs/heads/main` exactly);
- the trusted gate scripts: the shared tree's `check-citation.sh`, `lib/runs-api.sh` and `lib/declaration.sh` are
  the base's blobs;
- no merge-time hooks (`pre-auto-gc` included);
- the declared new dot paths (`declared_new_dot_paths`, from `--new-dot-path` at this step) and the manifest (no
  undeclared untracked dot path, no gate instrument, no `.gitattributes`), every manifest path unobstructed in the
  shared tree, and the requirements rule;
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
- the citation (2 of 2), produced by the base's pinned `check-citation.sh`;
- the operator hashes.

**STOP** if any other check fails.

**The two new dot files.** The planned delta (`67acb2628..`) adds two dot-named files the base does not track,
`cpt-studio/.gitignore` and `cpt-studio/deploy/.dockerignore`. They are admitted only as declared new dot paths:

- at this step they come from `--new-dot-path` (exact repository paths, no globs) and go into the contract to
  embed as `new_dot_paths`; the `whole_repository_manifest` row prints them as `new_dot_paths_admitted`;
- once the declaration is committed in the candidate (steps 6 and 7) it is the only source:
  `declared_new_dot_paths` reports `"source": "declaration"`, a different `--new-dot-path` refuses
  (`new_dot_paths_differ_from_the_declaration`), and the act refuses `--new-dot-path` outright;
- every other path guard still applies to them: absent from `/opt/meddoc-pro` (lstat), under real directories,
  with a regular blob mode;
- a declared path the delta does not add is a stale declaration and refuses (`declared_dot_path_not_in_delta`), as
  does a path the base already covers (`declared_dot_path_not_new`); a dot-named directory the base does not track
  and any undeclared dot path refuse (`untracked_dot_path`), and so does a `.git` or `.env*` name even when declared
  (`declared_dot_path_git_or_env`).

The command prints the contract block to embed. Read it against these expectations, and STOP on any surprise:

- `requirements_mismatch` names exactly filelock, msgpack and pypdf;
- `venv` shows 64 distributions and 63 unrecorded bytecode files;
- `foreign_venv_units` lists exactly the two Corti candidate units;
- `static` is `[]` (otherwise every name in it is a declared static publication);
- `new_dot_paths` is exactly `cpt-studio/.gitignore` and `cpt-studio/deploy/.dockerignore`;
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
- `strict_declaration_gate`: the runner's gate passes, run from the base's pinned copy;
- `declared_new_dot_paths`: `"source": "declaration"` with exactly the two cpt-studio files, which the manifest
  admits as `new_dot_paths_admitted` (no `--new-dot-path` is needed from here on);
- `backup_report`: complete, restore passed, no older than 12 hours, and intact on disk in exactly this sense
  (no key is used): the run directory holds `summary.json`, `manifest.json.fernet`, `database.dump.fernet` and
  `objects/` and nothing else, `objects/` holds exactly `file_count` objects, and every one of those files is
  private and has the bytes measured right after the restore check decrypted and verified them (report format
  `quillmd-rebuild-release-backup-v2`). The plaintext was proven once, by that restore check.

Record `measured.manifest_sha256`; it becomes `MANIFEST`.

## 7. The act (about 5 minutes; the units are down about 1-3 minutes)

Run it non-interactively: detached from any terminal (`setsid --fork`, so no Ctrl-C, Ctrl-\ or hangup can reach the
runner or the act), from a session that will outlive it, with the ceiling raised far above its worst duration, and
with no other operator process running on the host until it has exited (Roles and standing rules).

```
mkdir -m 0700 $R/evidence
cd $X && RULED_ACT_MAX_SECS=86400 setsid --fork bash $X/scripts/run-ruled-mutation.sh --declaration $X/$DECL -- \
  $PY -I -B $X/rebuild/ops/install_rebuild_release.py --execute \
  --base $BASE --candidate $CANDIDATE --declaration $X/$DECL --backup-report $R/backup-report-01.json \
  --result $R/act-01.json --evidence-directory $R/evidence/act-01 --manifest-sha256 $MANIFEST \
  </dev/null >$R/act-01.transcript 2>&1
tail -f $R/act-01.transcript        # Ctrl-C here stops only tail
```

`setsid --fork` returns at once; the runner then runs in its own session with no controlling terminal. The runner's
last lines in the transcript are `RULED MUTATION — FINISHED at <time>, exit <code>`: that code is the exit in the
table below. Until that line appears, signal nothing (below), and do not close or log out of the session it was
started from: stopping a session's scope signals every process in it.

The installer refuses before anything if:

- it is not under the runner (`RULED_MUTATION_*` must name this declaration);
- `--new-dot-path` is given (the act admits only the new dot paths the merged declaration names);
- its current directory is not `$X`;
- the evidence directory already exists, or its parent is not a private (0700) directory it can write;
- `--result` already exists, is not in a private (0700) directory it can write, or is inside the evidence directory.
  A refused preflight writes `--result` and creates no evidence directory, so a re-run needs a new `--result`
  (`act-02.json`) as well as a new evidence directory;
- any preflight row fails;
- the manifest differs from `MANIFEST`.

**The ceiling can only cut the act, never protect it: set it far above any duration the act can have.**
`run_watched` starts the act as `timeout -k 15 $RULED_ACT_MAX_SECS <act>`. When the ceiling fires, `timeout` sends
SIGTERM to the act's whole process group and SIGKILL 15 s later; the SIGKILL ends the act wherever it is, a restore
or the resume included, with no failure path and no outcome file. The act normally takes about 5 minutes, and every
child and helper call in it is bounded: unit actions 170 s each, configuration reads 30 s, one systemctl read of up
to 60 s per running service in each of four snapshots, one database statement of up to 90 s per table in each of
three snapshots, health 45 s, reaping a left-over child 120 s, the restore's lock wait about 30 s. Those bounds have
not been summed into a proven worst case (the number of services and tables is the host's), so the command above sets
`RULED_ACT_MAX_SECS=86400`. Never run it with the 3600 s default or lower.

**Nobody may signal the act, by any route, until the runner has printed its FINISHED line.** What a signal does
depends on where it lands. Measured on this host on 2026-11-01, on the installer's real act over the suite's fakes
under the real `run_watched` (nothing live was run, docker included):

- **Sent to the act's own process only** (`kill <installer pid>`): every signal that could end it is blocked from
  its first statement until it exits: every catchable signal whose default action ends a process (SIGTERM, SIGINT,
  SIGHUP, SIGQUIT, SIGUSR1, SIGUSR2, SIGALRM, SIGVTALRM, SIGPROF, SIGXCPU, SIGXFSZ, SIGIO, SIGPWR, SIGSTKFLT and the
  fault signals when sent by kill) and every real-time one. SIGPIPE is left to the interpreter's SIG_IGN, so it is
  neither fatal nor recorded. No handler runs: not the installer's (it has none), not the SIGTERM handler the
  managed docker helper installs for each call, not Ctrl-C's KeyboardInterrupt. Such a signal interrupts no stage,
  helper call, child's start, drain or restore. It is taken at the next checkpoint and recorded with its number,
  sender pid and uid (`signal_records`); two standard signals of the same kind between two checkpoints are one
  record. Taken **before the merge** it takes the automatic recovery, exactly as a refusal does: before the stop
  nothing is restored, after it the units are restored once the original is measured intact; the last such
  checkpoint is immediately before `publish_source` runs `git merge`, after its own re-checks and file proofs.
  Taken **from the merge on**, it is recorded and the act runs to completion (resume, health, every post-condition,
  the receipt) and exits 2 (`interrupted`, `signals_received`). After the receipt it is recorded in `--result`
  (`signals_after_the_act`), exit 2. A C child keeps the blocked mask (measured: a git child survives SIGTERM, SIGINT
  and SIGHUP and stops only on SIGKILL), so no signal stops a merge half-way.
- **Sent to the act's process group or to `timeout`** (`kill -TERM -<pgid>`, `kill <timeout pid>`, or `pkill -f` on
  the installer's path, which timeout's command line also carries): under the runner the act's parent is `timeout`,
  and timeout leads the act's process group. A SIGTERM, SIGINT, SIGHUP or SIGQUIT that reaches timeout is forwarded
  to the whole group; a SIGALRM fires timeout's ceiling, which sends the group SIGTERM. Either is followed 15 s later
  by SIGKILL. The act is gone 15 s after the signal wherever it is (measured for SIGTERM to the group and to timeout,
  and SIGQUIT and SIGALRM to timeout: in the restore after two of three starts; in the resume with the admin unit
  never started), with no outcome file, and the runner exits 137 unless the act happened to finish within those 15 s.
  Any other terminating signal that reaches timeout ends timeout itself, and so does a SIGKILL sent to timeout: the
  runner exits 128 + its number at once (measured: 138 for SIGUSR1, 137 for SIGKILL, 2.6 s after the signal) and the
  act runs on, unwatched, to its own end (measured: it installed, or recorded the group's SIGUSR1 and restored, about
  26 s later). Its later stage lines are lost from the transcript; its evidence and `--result` are not.
  A group signal also reaches the docker helper client of a unit action in flight. It is a Go binary, and the Go
  runtime unblocks the signals it handles (measured on a Go stand-in under the act's mask: SIGHUP, SIGINT, SIGQUIT,
  SIGTERM, SIGABRT, SIGPROF, SIGSTKFLT, the fault signals and SIGRTMIN unblocked on every thread; it died of SIGTERM).
  docker forwards the signals it receives into the helper container (its sig-proxy, which subscribes to every signal;
  read from the binary and docker's documentation, docker was not run). That start or stop fails: before publication
  the failure path then restores (unverified if a start failed); once the resume has started it drains the new
  release.
- **From a terminal** (Ctrl-C, Ctrl-\, a hangup): when the runner runs in a terminal they reach only the runner,
  because `timeout` moved the act out of the terminal's foreground process group. The runner dies at once, the act
  runs on detached and records nothing, and the runner's verdict is never printed (measured: the act went on to
  install). Started as above, with `setsid --fork` and no terminal, the runner has no controlling terminal and they
  reach neither it nor the act (measured).
- **SIGKILL** ends the act wherever it is. **SIGSTOP** (or SIGTSTP, SIGTTIN, SIGTTOU, which stop rather than end a
  process) freezes it, units and all, until SIGCONT.

If the act must be stopped anyway, the only way is SIGKILL, and the only recovery is a separately declared reverse
act (the rollback act, below): inspect the units at once and declare it.

Then it acts in the engine's order. It checks the venv footprint at the baseline, after the stop (before
publication) and after the resume. It checks the venv-sharing units for idleness at the baseline and after the
resume. It compares the foreign services at the baseline, after the stop, before the resume and after the resume.
After the stop and before the merge it also compares these with their baselines: the configuration hashes, the
clinical-file inventory, the shared tree (clean `main` at `BASE`, git's own state, every manifest path
unobstructed), and last, nearest the merge, `rebuild/.env` and the static inventory. Every git process of the act
runs with `core.hooksPath=/dev/null`, `maintenance.auto=false`, `gc.auto=0` and `core.useReplaceRefs=false`.

**Publication begins only when git has moved `HEAD` or the working tree.** Any refusal before the merge restores
the original release. So does a refusal inside the engine's `publish_source` before it runs `git merge`
(`merge_invoked: false`). So does a merge git refused before changing anything. The act measures that instead of
assuming it:

1. it reaps every child it started, so no `git merge` can still move `HEAD` behind the measurement. A child still
   running after 120 s counts as publication (`act_child_process_still_running`);
2. it runs the engine's `verify_original_before_resume`: `HEAD` at `BASE`, the tree clean, every base file proven,
   every new path absent;
3. it repeats the shared-tree measurement taken before the merge: clean `main` at `BASE`, git's own state, every
   manifest path unobstructed.

If the measurement fails, nothing is started. That happens if git moved the index or the working tree (as with a
held `HEAD.lock`), or if git's state is not clean: an unfinished operation, or a lock that changes the merge (the
shared tree's `index.lock`, `HEAD.lock`, `ORIG_HEAD.lock` or `refs/heads/main.lock`) that git left behind or that
another process still holds. While such a lock is the only failure, the measurement is taken again every second for
about 30 s, so a lock a `git status` holds for a moment does not strand the units; every measurement is recorded in
`original_verification.measurements`, with the lock it saw. The locks another worktree's git write takes in the
common directory (`config.lock`, `packed-refs.lock`, another branch's or a remote's ref lock) never fail it; a
passing measurement lists them under `observed_locks`. A changed `rebuild/.env` also fails it: the original is then
not intact. If the merge was invoked, publication counts as begun (`recovery: none`). Otherwise the original recovery
is refused (`recovery: refused`). In both cases the units stay drained.

**The failure path.** `failure.json` is written first: stage, fixed label, `recovery` (`restore`, `drain`,
`refused` or `none`), `publication_attempted`, `merge_invoked`, `original_verification`, `children` (reaped and
still running), `signals_received` and `signal_records`. Then, whatever happened to that write, every owned unit
gets its restore or drain attempt, the locks are released (a failure there is recorded as
`coordination_released: false` and never replaces the outcome), and one outcome file follows:

- `original-release-resumed.json`: every start returned, health reports `BASE`, and every unit is active with a
  main PID, all MEASURED;
- `original-release-restore-unverified.json`: a start failed, a unit did not come up, or health did not report
  `BASE`; inspect the units now;
- `original-recovery-refused.json`: the original could not be verified, so nothing was started;
- `failed-resume-drain.json`: the resume had started; every unit was stopped and checked.

If an evidence write fails, the same record is printed on stderr as one line
`[rebuild-release] {"rebuild_release_outcome": {...}}` (the runner's transcript), and `--result` carries it under
`recovery`. A signal taken before the merge takes this same path. A signal sent to the act's own process while units
are being restored or drained is recorded in the outcome (`signals_received`) and does not cut the recovery short.
A signal sent to its process group or to `timeout` can: the SIGKILL that follows 15 s later, or the failed start or
stop of a unit action whose docker client it reached. So read `failure.json` and the outcome file after any exit
other than 0 or 2.

| exit | meaning | next |
|---|---|---|
| 0 | `installation-complete.json`, every post-condition passed | step 8 |
| 2 | installed and serving the candidate, but something the act cannot undo needs judging: the configuration changed or could not be read after the resume; a foreign service restarted after the resume; foreign units not idle after the resume; the venv footprint changed during the act; a signal arrived after publication began (or after the receipt); the locks could not be released; the receipt or `--result` could not be written | judge it from `installation-complete.json` (`postconditions`, `observations`, `venv_change`, `interrupted`, `signal_records`, `coordination_released`) or, if the receipt is missing, from stderr. Nothing was drained. Do not re-run. |
| 1, `installation_failed_inspect_retained_evidence` | refused or failed | read `failure.json` first. `recovery: restore` with `original-release-resumed.json`: the original release is back, measured. `recovery: none` with `publication_attempted: true`: the units are drained and only a newly declared corrective act may follow. **Never re-run** an act whose evidence directory exists. |
| 1, `original_restore_unverified_inspect_retained_evidence` | the restore ran but was not proven | read `original-release-restore-unverified.json` (`starts`, `units_active`, `health`) and the units' state at once. |
| 1, `original_recovery_refused_inspect_retained_evidence` | the original could not be verified; nothing was started | read `original-recovery-refused.json`; the units are drained. |
| 1, `failed_resume_drain_incomplete` | the resume failed and a unit could not be proven stopped | read `failed-resume-drain.json`; inspect the units at once. |
| 1, `installation_failed_recovery_state_unknown` | the failure path itself failed | inspect the units and stderr at once. |
| 137 | SIGKILL. Either the act was cut wherever it was: 15 s after the ceiling, or 15 s after a SIGTERM, SIGINT, SIGHUP, SIGQUIT or SIGALRM reached `timeout` (a signal to the act's process group, to timeout, or a `pkill -f` on the installer's path), or by a direct SIGKILL. Or `timeout` itself was SIGKILLed and the act is still running. The runner prints its ceiling banner only for 124, never for 137. | first find out whether the act still runs: `pgrep -a -f 'install_rebuild_release.py --execute'` from an interactive shell (it lists the act, and its timeout while that lives; inside a `bash -c` it would also list its own command line). If anything is listed, signal nothing: wait until nothing is, then read `--result` and the evidence. If nothing is: inspect the units at once, then `failure.json`, the outcome file, `--result` and the transcript. A cut act is answered only by a separately declared act. **Never re-run.** |
| 124 | the ceiling fired: `timeout` sent the act SIGTERM (blocked, recorded if a checkpoint came) and the act then ended on its own within 15 s | as for 137; with the ceiling at 86400 s this means the act ran for a day. |
| any other 128 + n | signal n ended `timeout`, not the act, which blocks it (138 SIGUSR1, 140 SIGUSR2, 141 SIGPIPE, ...): the act may still be running, unwatched, its later stage lines lost. Only a fault the kernel delivers whatever the mask (132 SIGILL, 134 SIGABRT, 135 SIGBUS, 136 SIGFPE, 139 SIGSEGV) can mean that the act itself died. | as for 137. |

Evidence (private, mode 0700): `plan.json`, `preflight.json`, `environment-before.fernet`,
`environment-after.fernet`, `rollback-readback.json`, `baseline.json`, `venv-before.json`,
`database-after-stop.json`, `database-before-resume.json`, `pre-resume-preservation.json`, then
`installation-complete.json`, or `failure.json` plus one of `failed-resume-drain.json`,
`original-release-resumed.json`, `original-release-restore-unverified.json` or `original-recovery-refused.json`.

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
| step 3 | Any FAIL other than the three declaration rows; a requirements mismatch other than filelock, msgpack and pypdf; `new_dot_paths` other than the two cpt-studio files; a static name or a migration; venv-sharing units other than the Corti pair, or not idle; undeclared live-venv processes; locks held; pending provider work; a citation that is not 2 of 2; a contract that surprises the reader. |
| step 4 | CI is red on the PR or on the merge commit; the merge adds anything but the declaration; `diff CODE CANDIDATE` is not exactly `A $DECL`. |
| step 6 | Any FAIL, a backup report older than 12 hours, or a contract mismatch (the venv, foreign units, backup or code changed since step 3: redo steps 2-6 as needed). |
| step 7 | Anyone signals the act, its process group or its `timeout`, or any other operator process runs, before the runner's FINISHED line; exit 1 (read `failure.json`; never re-run); exit 2 (judge; units are serving the candidate); exit 137, 124 or any other 128 + n (the act was cut wherever it was, or runs on unwatched: find out whether it still runs, signal nothing, inspect the units at once; never re-run). |
| step 8 | Health is not the candidate, a unit is inactive, the venv footprint changed, a Corti unit restarted, the shared tree is not clean `main` at `CANDIDATE`, or the mismatch is not exactly the declared one. |

## What this act never does

- No pip; the venv is left exactly as found (D1, D2).
- No migration; a changed `rebuild/**/migrations/**` path refuses.
- No new dot-named path the base does not track unless the declaration names that exact file (never a dot-named
  directory, never a `.git` or `.env*` name), nothing written through or over an existing non-directory in the
  shared tree, no hook, no gate instrument and no `.gitattributes` from the delta.
- No static publication unless the contract names it: flat `rebuild/static/<name>` only, through the engine's own
  static path.
- No unit-file change: `rebuild/deploy/**` refuses, and `/etc/systemd`, `/etc/nginx`, `/etc/ssh` and the Caddyfile
  are hashed and must not change.
- No provider call, no clinician decision, no restart of a foreign service.
- No backup: that is step 2.
