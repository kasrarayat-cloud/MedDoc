# Prospective declaration: QuillMD rebuild code-only release at app.quillmd.com (67acb2628 to 797199c7c625beac27b6788b4cec9af683137ac4)

Authority: the owner's directive of 2026-10-31 (round 4), recorded verbatim in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, item 1: "Address the reported live rebuild PDF-security finding first,
as a separate scoped change. ... Reproduce the inspection bypass using harmless fixtures; repair the actual upload and
original-download path. Do not assume strict=True, warning suppression or a dependency upgrade establishes safety." The
standing authority of 2026-08-22 (AGENTS.md: supervised sessions deploy and judge clinical-surface changes). Session
interpretations 62 (round-4 order), 64 (session 1bf3b49c is the single integration and deployment owner) and 67 with its
addendum (D1 code only, D2 no venv downgrade, D3 foreign units unchanged and idle, D4 this declaration merged to `main`
before the act; the tracked installer; no signal to the act). No purchase, key, payment change, real-patient processing or
provider request is part of this act.

Freeze: `main` is frozen from the preflight of record (step 3, 2026-11-01T18:37:22.002072+00:00) until this act's records land (step 9).
No other session was running on this host when the freeze began (ListAgents: none reachable), and no open pull request
has auto-merge enabled.

## Revision and how it is executed

- `BASE` = 67acb2628b84c2be25f379a15168aa802350c060, the served release (shared tree `main`, health, `QUILLMD_RELEASE_SHA`).
- `CODE` = 797199c7c625beac27b6788b4cec9af683137ac4: `origin/main` after PR #1454 (P1) and PR #1455 (this installer) merged, before this declaration.
- `CANDIDATE` = the merge commit of the pull request that adds exactly this file, and nothing else, on top of `CODE`.
- Interpreter `PY=/opt/meddoc-pro/rebuild/.venv/bin/python`, always `-I -B`. Reports in the private (0700) directory
  `R=/home/claude/cpt-studio-gi4-20261031/install/r-20261101`; the backup report is `$R/backup-report-01.json` (attempt
  `/opt/meddoc-pro/backups/rebuild-release-20261101/attempt-01`, finished 2026-11-01T11:17:53Z, so the act must start
  before 2026-11-01T23:17:53Z or take a new attempt); the preflight of record is `$R/preflight-01.json`.

The act is docs/runbooks/rebuild-release-install-20261031.md step 7, verbatim:

```
mkdir -m 0700 $R/evidence
cd $X && RULED_ACT_MAX_SECS=86400 setsid --fork bash $X/scripts/run-ruled-mutation.sh --declaration $X/$DECL -- \
  $PY -I -B $X/rebuild/ops/install_rebuild_release.py --execute \
  --base $BASE --candidate $CANDIDATE --declaration $X/$DECL --backup-report $R/backup-report-01.json \
  --result $R/act-01.json --evidence-directory $R/evidence/act-01 --manifest-sha256 $MANIFEST \
  </dev/null >$R/act-01.transcript 2>&1
```

`X` is a plain detached worktree at `CANDIDATE`; `MANIFEST` is `measured.manifest_sha256` from the final preflight (step 6),
taken no more than 30 minutes before the act. Nobody signals the act, its process group or its `timeout` until the runner
prints its FINISHED line, and no other operator process (no session, agent, loop, scheduled job of ours, test or plain
`git` in `/opt/meddoc-pro`) runs until then.

## The full delta, by class (`BASE`..`CODE`)

401 paths in total (`git diff --name-only 67acb2628 797199c7c625beac27b6788b4cec9af683137ac4`). Five classes, and nothing else:

1. **P1, the reported PDF-security finding (PR #1454, merge `797199c7`).** Runtime:
   `rebuild/documents/pdf_raw.py` (new: the parser-independent raw scan), `engine.py`, `service.py`, `__init__.py`;
   `rebuild/core/views.py` (original and export downloads, encounter creation, the generate request), `jobs.py`,
   `coding_service.py`, `semantic_revalidation.py` (the worker guard before every provider call),
   `template_source.py`, `management/commands/check_pdf_originals.py` (new, read-only report), and
   `rebuild/templates/template_upload.html`. Tests: `documents/test_pdf_active_content.py`,
   `core/tests/test_template_original_safety.py`, `test_template_original_safety_r5.py` (new), and
   `test_security.py`, `test_clinical_validation_diagnostics.py`, `test_refutation.py`,
   `test_semantic_generation.py`. Docs: `docs/rebuild/security-readiness.md` (rounds 1-5),
   `docs/rebuild/pypdf-6.21.4.md`, `rebuild/documents/README.md`; CI: `scripts/ci/verify-fresh.sh`. Five refutation
   rounds; the last (three lenses on round 4) found no provider call or usage row past the guard; its findings are
   repaired or recorded in round 5. Round 3's retry page and route were removed again in round 4, so
   `rebuild/quillmd/urls.py`, the voice flows and their templates are unchanged from `BASE`.
2. **PR #1434's instruction text, on the clinical generation path (merge `cb154f8a4`).**
   `rebuild/core/source_assertion_generation.py`, blob `ddd0777f` to `7675fdb5`, 22 lines added and 1 removed: model
   instructions that negated, uncertain, conditional or hypothetical assertions carry an exact governing qualifier,
   coverage rows list their assertions exactly, and time roles carry literal references. It deletes no text by
   itself; its effect reaches a note only through the existing validators. Its October refutation is recorded only
   in the PR body ("The runtime diff passed independent refutation"); no transcript is tracked. Never installed
   until this act; judged after it by the first fresh synthetic extraction (Validation). `.github/workflows/test.yml`
   came with it.
3. **`rebuild/requirements.txt` (PRs #1436, #1441, #1449):** filelock 4.0.0 to 4.2.1, msgpack 1.2.2 to 1.2.3, pypdf
   6.21.1 to 6.21.4. Not installed (D1): the venv keeps the old versions, so the file and the venv differ in exactly
   these three pins after the act.
4. **The operator (PR #1455, merge `30fdc826`):** `rebuild/ops/install_rebuild_release.py`, `venv_footprint.py`,
   `rebuild_release_backup.py`, `rebuild_dependency_stage.py` and their four test modules, and
   `docs/runbooks/rebuild-release-install-20261031.md`. Nothing the running units import.
5. **Passengers, never executed by the rebuild units:** `cpt-studio/**` (CPT Studio's rounds 1-3, PRs #1435 to #1453;
   CPT Studio runs from its own image, `cpt-studio:80df1831d168`), including the two new dot paths
   `cpt-studio/.gitignore` and `cpt-studio/deploy/.dockerignore`, `.github/workflows/cpt-studio.yml`,
   `scripts/ci/verify-cpt-studio.sh`, and `docs/foundation/**` (rulings, interpretations and earlier declarations).

No rebuild migration (no `rebuild/**/migrations/**` path; the seven `cpt-studio/studio/migrations/` paths are
passengers, applied to CPT Studio's own database by its own installs), no static file, no unit file
(`rebuild/deploy/**` unchanged), no gate instrument and no `.gitattributes` is in the delta.

## Baseline (read-only, from the preflight of record 2026-11-01T18:37:22.002072+00:00; the act's own baseline is binding)

Measured by the preflight of record at 2026-11-01T18:37:22.002072+00:00 (`--base 67acb2628b84c2be25f379a15168aa802350c060`, `--candidate 797199c7c625beac27b6788b4cec9af683137ac4`). Its rows: 31 passed, 3 failed (declaration_provenance, strict_declaration_gate, declaration_contract).

**Database (read-only, `quillmd_fresh`):** 48 tables, 233,049 rows; pending provider work: `{"core_aistagereceipt": 0, "core_codingrun": 0, "core_job": 0, "core_templatedefinitionpreparation": 0, "core_templatepreparation": 0}`; applied migrations: 54. Every count below must be unchanged by the act (health ticks excluded by the engine).

| table | rows |
|---|---:|
| `auth_group` | 0 |
| `auth_group_permissions` | 0 |
| `auth_permission` | 136 |
| `core_aistagereceipt` | 383 |
| `core_auditevent` | 6,068 |
| `core_code` | 224,317 |
| `core_codeset` | 3 |
| `core_codesuggestion` | 0 |
| `core_codingcontext` | 19 |
| `core_codingdecision` | 14 |
| `core_codingoutputdecision` | 8 |
| `core_codingrelease` | 3 |
| `core_codingrun` | 50 |
| `core_codingsourcedecision` | 5 |
| `core_costreconciliation` | 0 |
| `core_department` | 3 |
| `core_encounter` | 162 |
| `core_invitation` | 9 |
| `core_job` | 163 |
| `core_ledgerentry` | 55 |
| `core_loginattempt` | 43 |
| `core_membership` | 11 |
| `core_organization` | 2 |
| `core_patient` | 46 |
| `core_payment` | 3 |
| `core_platformcost` | 19 |
| `core_preparationreceipt` | 125 |
| `core_providerreceipt` | 154 |
| `core_refund` | 2 |
| `core_reservation` | 34 |
| `core_servicehealth` | 1 |
| `core_sourceinterpretation` | 0 |
| `core_template` | 91 |
| `core_templatedefinitionpreparation` | 11 |
| `core_templatepreparation` | 73 |
| `core_templateversion` | 84 |
| `core_testingreservation` | 127 |
| `core_usage` | 157 |
| `core_user` | 12 |
| `core_user_groups` | 0 |
| `core_user_user_permissions` | 0 |
| `core_verification` | 0 |
| `core_wallet` | 24 |
| `core_webhookevent` | 7 |
| `django_content_type` | 34 |
| `django_migrations` | 54 |
| `django_session` | 536 |
| `otp_totp_totpdevice` | 1 |

**Live venv `/opt/meddoc-pro/rebuild/.venv`:** `{"bytecode_files": 7068, "distributions": 64, "file_bytes": 207285719, "footprint_sha256": "976009db259506a4a442234108f8ac4b63b46fc427428ab43ec68326fcbfa592", "objects": 21611, "pip_residue": 0, "unrecorded_bytecode": 63, "venv": "/opt/meddoc-pro/rebuild/.venv"}`

**Requirements mismatch (declared, D1):** `{"filelock": {"installed": "4.0.0", "required": "4.2.1"}, "msgpack": {"installed": "1.2.2", "required": "1.2.3"}, "pypdf": {"installed": "6.21.1", "required": "6.21.4"}}`

**Foreign units sharing the venv:** `["quillmd-corti-candidate-worker.service", "quillmd-corti-candidate.service"]`; idle: `{"idle": true, "max_cpu_fraction": 0.02, "units": {"quillmd-corti-candidate-worker.service": {"cpu_usec": 44999, "idle": true, "window_usec": 15000176}, "quillmd-corti-candidate.service": {"cpu_usec": 4073, "idle": true, "window_usec": 15000176}}}`

**Backup (step 2):** report sha256 `f124c44c21cd6f7d0afa0ad43fc6535536ffc29f3e5b7e0575e38ae569f92b78`, run `20261101T105056Z-c8423457`, restore check `bd7ff3cb2254fdc3`, finished 2026-11-01T11:17:53.431419+00:00, of `67acb2628b84c2be25f379a15168aa802350c060`: 48 tables, 233,049 rows, 1,272 files, 97,619,512 bytes; ciphertext files unchanged since the restore check: 1275.

**Citation of `CODE`:** **Citation — 2 of 2 on `797199c7c625beac27b6788b4cec9af683137ac4`:**

**Manifest sha256 at step 3:** `10cc6849c1e407ef8352c39c5303a0c0ed31e99c1f948abfa29ee80b6aab1348` (the act binds the step-6 value).

## What must change

- `/opt/meddoc-pro` fast-forwards from `BASE` to `CANDIDATE` on `main` and stays tracked-clean.
- `QUILLMD_RELEASE_SHA` in the release stamp becomes `CANDIDATE`; `https://app.quillmd.com/health/` reports it.
- The three owned units are restarted (new main PIDs) and active.
- Nothing else.

## What must not change

- The live venv `/opt/meddoc-pro/rebuild/.venv`: the full footprint before equals after (footprint sha256 `976009db259506a4a442234108f8ac4b63b46fc427428ab43ec68326fcbfa592`; 64 distributions,
  pypdf 6.21.1, filelock 4.0.0, msgpack 1.2.2, 63 unrecorded bytecode files). No pip, no dependency install (D1, D2).
- Every database table's row count, except the health tick rows the engine excludes; no migration is applied (none is in
  the delta); clinical counts (encounters, documents, approvals, provider calls, usage) are in the baseline above and move
  by zero during the act.
- The clinical-file inventory, the configuration hashes (`rebuild/.env` included, never read here), `/etc/systemd`,
  `/etc/nginx`, `/etc/ssh` and the Caddyfile, the static inventory (`static` is `[]`), every foreign service (MainPID and
  InvocationID), and the two Corti candidate units that share the venv: idle, unrestarted.
- `requirements.txt` keeps differing from the venv in exactly the three declared pins (filelock, msgpack, pypdf). That is
  reported, not concealed: the rebuild and CPT Studio dependency audits keep flagging the old versions until D1b.

## What the install sends to a provider: nothing

The act stops, merges, stamps and starts. It makes no provider call and writes no usage row. Any row written before the stop
other than a health tick refuses the act before publication, which restores the original release automatically.

## Validation

Step 8 of the runbook, read-only: `installation-complete.json` (`installed_revision == CANDIDATE`, `dependency_installs: 0`,
`migrations_executed: 0`, `all_postconditions_passed`); health reports the candidate and the three owned units are active;
the shared tree is clean `main` at `CANDIDATE` (`git --no-optional-locks`); the venv footprint equals the declared one; the
Corti candidate units keep their MainPID and InvocationID; the worker's cgroup limits are unchanged (memory 1 GiB, swap 0,
64 tasks, core 0); the requirements mismatch is exactly the declared one. Judged checks, recorded separately: P1's harmless
fixtures through HTTPS on the synthetic account (refused active content, an ordinary PDF and a DOCX still usable), and the
first fresh synthetic extraction under PR #1434's instructions.

## Rollback and its limits

`install_rebuild_release.py` refuses deletions and cannot reverse itself. Any refusal before `git merge` restores the
original release automatically and measured (`original-release-resumed.json`). After publication a failure leaves the units
drained, and only a newly declared corrective act may follow. The reverse act's shape is in the runbook ("The rollback
act"): its own declaration merged first, `git restore --source=BASE` over the manifest paths plus a compare-and-swap of
`refs/heads/main`, the release stamp back to `BASE`, the same locks and checks, and never pip (D2). It is not implemented;
it needs its own code, refutation and review before use.

## What is not claimed

- No pypdf, filelock or msgpack move: the venv keeps 6.21.1, 4.0.0 and 1.2.2 and the dependency audits stay red (D1b is a
  later act, not built).
- No clinical acceptance of PR #1434's instruction text: its effect is judged only by the first fresh synthetic extraction.
- P1's accepted cost: six ordinary pypdf-incremental files in the reader corpus are now refused as `unreadable_pdf`
  (strict pypdf cannot read their previous trailer); kept as an owner item, overrulable. The live rebuild holds 0 PDF
  templates, so no live template changes verdict (91 Word and 0 PDF templates by the round's read-only count; `check_pdf_originals` ships in this candidate and is not run against the live database by this act).
- Nothing about CPT Studio: its files in this delta are passengers; CPT Studio runs from its own image.

## Stop conditions

The runbook's table, verbatim (docs/runbooks/rebuild-release-install-20261031.md):

| when | stop if |
|---|---|
| any time | Another merge to `main` happens after step 3, the shared tree leaves clean `main` at `BASE`, or anyone runs pip or tests on the live venv. |
| step 2 | Any non-zero exit, an incomplete report, an `INCOMPLETE` marker, a restore that is not complete, a retained drill container, or a run inside a scheduled window. |
| step 3 | Any FAIL other than the three declaration rows; a requirements mismatch other than filelock, msgpack and pypdf; `new_dot_paths` other than the two cpt-studio files; a static name or a migration; venv-sharing units other than the Corti pair, or not idle; undeclared live-venv processes; locks held; pending provider work; a citation that is not 2 of 2; a contract that surprises the reader. |
| step 4 | CI is red on the PR or on the merge commit; the merge adds anything but the declaration; `diff CODE CANDIDATE` is not exactly `A $DECL`. |
| step 6 | Any FAIL, a backup report older than 12 hours, or a contract mismatch (the venv, foreign units, backup or code changed since step 3: redo steps 2-6 as needed). |
| step 7 | Anyone signals the act, its process group or its `timeout`, or any other operator process runs, before the runner's FINISHED line; exit 1 (read `failure.json`; never re-run); exit 2 (judge; units are serving the candidate); exit 137, 124 or any other 128 + n (the act was cut wherever it was, or runs on unwatched: find out whether it still runs, signal nothing, inspect the units at once; never re-run). |
| step 8 | Health is not the candidate, a unit is inactive, the venv footprint changed, a Corti unit restarted, the shared tree is not clean `main` at `CANDIDATE`, or the mismatch is not exactly the declared one. |

<!-- rebuild-release-contract -->
```json
{
  "backup": {
    "report_sha256": "f124c44c21cd6f7d0afa0ad43fc6535536ffc29f3e5b7e0575e38ae569f92b78",
    "restore_run_id": "bd7ff3cb2254fdc3",
    "run_id": "20261101T105056Z-c8423457"
  },
  "base": "67acb2628b84c2be25f379a15168aa802350c060",
  "code_candidate": "797199c7c625beac27b6788b4cec9af683137ac4",
  "code_manifest_sha256": "10cc6849c1e407ef8352c39c5303a0c0ed31e99c1f948abfa29ee80b6aab1348",
  "dependency_installs": 0,
  "dot_paths": [
    ".github/workflows/cpt-studio.yml",
    ".github/workflows/test.yml",
    "cpt-studio/.gitignore",
    "cpt-studio/deploy/.dockerignore"
  ],
  "environment_delta": [
    "QUILLMD_RELEASE_SHA"
  ],
  "foreign_venv_units": [
    "quillmd-corti-candidate-worker.service",
    "quillmd-corti-candidate.service"
  ],
  "format": "quillmd-rebuild-release-contract-v1",
  "migrations": 0,
  "new_dot_paths": [
    "cpt-studio/.gitignore",
    "cpt-studio/deploy/.dockerignore"
  ],
  "operator": {
    "rebuild/ops/install_rebuild_release.py": "7168948ded86d3aefa6e8c104e62131ae7f257a3642684d11ca1a6319b8f3ac9",
    "rebuild/ops/rebuild_release_backup.py": "9c129cb8bd14237ddf7bbb5c9cbc47821cd94b6ffee6c4b4cda864681a38d2ea",
    "rebuild/ops/venv_footprint.py": "cb4cf21283840bde37958b7fc7a22ae9990ba70d922b61c93dc075dac0771e4a"
  },
  "paths": {
    "added": 381,
    "classes": {
      "passenger": 372,
      "requirements": 1,
      "runtime": 17,
      "support": 11
    },
    "modified": 20,
    "total": 401
  },
  "requirements_mismatch": {
    "filelock": {
      "installed": "4.0.0",
      "required": "4.2.1"
    },
    "msgpack": {
      "installed": "1.2.2",
      "required": "1.2.3"
    },
    "pypdf": {
      "installed": "6.21.1",
      "required": "6.21.4"
    }
  },
  "runtime_paths": [
    "rebuild/core/coding_service.py",
    "rebuild/core/jobs.py",
    "rebuild/core/management/commands/check_pdf_originals.py",
    "rebuild/core/semantic_revalidation.py",
    "rebuild/core/source_assertion_generation.py",
    "rebuild/core/template_source.py",
    "rebuild/core/views.py",
    "rebuild/documents/README.md",
    "rebuild/documents/__init__.py",
    "rebuild/documents/engine.py",
    "rebuild/documents/pdf_raw.py",
    "rebuild/documents/service.py",
    "rebuild/ops/install_rebuild_release.py",
    "rebuild/ops/rebuild_dependency_stage.py",
    "rebuild/ops/rebuild_release_backup.py",
    "rebuild/ops/venv_footprint.py",
    "rebuild/requirements.txt",
    "rebuild/templates/template_upload.html"
  ],
  "static": [],
  "venv": {
    "distributions": 64,
    "footprint_sha256": "976009db259506a4a442234108f8ac4b63b46fc427428ab43ec68326fcbfa592",
    "path": "/opt/meddoc-pro/rebuild/.venv",
    "policy": "exact-before-and-after",
    "unrecorded_bytecode": 63
  }
}
```
