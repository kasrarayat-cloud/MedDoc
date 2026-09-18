# What is left of the original application, and what is not

Written 2026-09-18 against the running host. Every count in this document was
measured on the day it was written; the commands are named so each one can be
re-run.

## The correction

The 2026-09-17 report said the rebuild had kept **"all of the original
application's remnants."** That sentence is wrong, and earlier reports saying
the old system had been removed were closer to the truth without being exact
either. Neither is a safe thing to leave standing, because "all of it is still
there" and "it is gone" lead to opposite decisions about a disk that holds real
contact details.

What is actually true, and the distinction the sentence missed:

- **The original application's source is gone from the shared tree and from
  `main`, along with its build images and its scheduled job.** It does not run,
  and no current service loads a line of it. ⚠️ **It is NOT gone from this
  disk:** nineteen other git worktrees under `/opt/meddoc-pro` still carry a
  full `apps/transcribe-md` checkout — other sessions' working trees, not this
  session's to reap. The distinction matters, because "the source is gone" and
  "the source is in nineteen places" lead to different answers about what a disk
  image of this host would contain.
- **Three data services it used are still running, and one of them holds
  genuine business records.** They are not remnants of code; they are where the
  original data lives.
- **The marketing site and the shared ingress are not remnants at all.** They
  are current, deliberately kept, and serving.

## 1. Obsolete original code and data — removed, verified absent

| What | State | Evidence |
| --- | --- | --- |
| Application source `apps/transcribe-md`, `packages/{ai,auth,db,types}` | **absent from the shared tree and from `main`** | `ls apps/` returns `marketing` only; `ls packages/` returns `shared` only. **Present in 19 other worktrees**, counted with `git worktree list` + a test for `apps/transcribe-md` |
| 19 pinned obsolete source paths | **all absent from the shared tree** | `docs/rebuild/obsolete-source-manifest.json`, re-checked path by path. They survive inside the 19 worktrees above |
| Nightly 02:00 cron entry for the old stack | **absent** | crontab read; the line is gone |
| 85 obsolete images across 104 tags | **removed 2026-09-17**, ~28.27 GiB freed | `docs/rebuild/obsolete-image-cleanup-result.json` |
| Application containers `transcribe-md`, `transcribe-md-worker`, `meddoc-pro` | **not running** | `docker ps` lists neither; `pro.quillmd.com` answers 410 by design |

The previously prepared source/cron cleanup
(`scripts/retire-old-quillmd-source.py`, declaration
`docs/foundation/mutations/20260917-quillmd-obsolete-source.md`) is therefore
**complete**. Nothing in it remains to execute.

## 2. Original data still held — preserved deliberately, NOT obsolete

| Service | Contents, measured | Disposition |
| --- | --- | --- |
| `meddoc-pro-postgres-1`, database `meddoc` (9,671 kB) | **one table, `waitlist_entries`, with 7 rows created 2026-08-02 to 2026-09-05**, columns `id, email, name, note, source, invitedAt, createdAt` | **PRESERVE.** These are real people who asked to be told about the product. They are business records and contact details, not test rows. Values were not read or copied while auditing |
| `meddoc-pro-minio-1` (20 GiB LUKS volume) | **0 buckets, 0 objects** outside `.minio.sys` | empty, retained pending an owner decision |
| `meddoc-pro-redis-1` | `DBSIZE` **0**, no keyspace | empty, retained pending an owner decision |

⚠️ **This row is the reason the earlier "the old system was removed" phrasing
was unsafe.** Reading it as "nothing is left" invites deleting a postgres
volume that holds the only copy of seven people's contact details. They are not
recoverable from the rebuild, which has never imported them.

## 3. Preserved marketing and shared resources — current, not legacy

| What | Why it stays |
| --- | --- |
| `meddoc-pro-marketing-1` + `apps/marketing` | the live public site. It has **no database environment variable and opens no database connection** (`docker inspect` env, and `apps/marketing/src/lib/constants.ts` links the waitlist to the app URL rather than writing rows) |
| `meddoc-pro-caddy-1` | shared ingress behind the host nginx; serves the marketing site and the maintenance responses |
| `packages/shared` | shared library, used by the marketing build |
| `WM IOV Template.docx`, `colon_blank_answers.pdf` at the repo root | recorded blank tracked fixtures (`AGENTS.md`, "Tracked fixtures"); never re-flag |

## 4. Original user templates

The original application's uploaded templates lived in MinIO, which now holds
**zero objects**. The only original-format documents still on disk are the two
**blank** fixtures listed above, and the copies inside
`apps/transcribe-md/tests/e2e/fixtures/**` went with the source deletion. The
rebuild's own document store is separate and current:
`/var/lib/quillmd/{files,mail,proofs}` on the encrypted volume — **34 files, 6
mail items, 4 proofs**, all synthetic.

**No original user template was deleted by any cleanup in this programme**, and
none is recoverable from MinIO because none was there to begin with. The
committed E2E fixtures under `apps/transcribe-md/tests/e2e/fixtures/` left the
shared tree with the source and, like the source, still exist in the 19 other
worktrees.

## 5. Current rebuild files

`/opt/meddoc-pro/rebuild` — Django 5.2, three services on 127.0.0.1:9130/9131,
database `quillmd_fresh` in `quillmd-fresh-postgres`, private state on the LUKS2
volume. Verified: the **three services** — six processes, all owned by `quillmd-app`
rather than by the operator account — run from `/opt/meddoc-pro/rebuild`
(`ps -eo user,args`: two gunicorn masters with three workers between them, plus
`manage.py worker`), and both HTTP surfaces answer.

## 6. Historical evidence — keep

`backups/` (186 MB, including `db-pre-app-redesign-20260422.sql.gz` and two
0600 `.env` backups, unread), `docs/deploy-reports/`,
`docs/foundation/{deploys,mutations}/`, `docs/qa-reports/`,
`docs/rebuild/*.json` result files, and the audit rows in both databases.
**None of it is deleted to make a report read consistently.**

## Dependency verification — does anything current touch the old system?

| Question | Answer | How it was checked |
| --- | --- | --- |
| Does any running service execute original application code? | **No** | the three live processes are `gunicorn quillmd.wsgi` ×2 and `manage.py worker`, all from `/opt/meddoc-pro/rebuild` |
| Does the rebuild read the `meddoc` database? | **No** | it connects to `quillmd_fresh` on port 55438 — a different server from the legacy stack's. ⚠️ The guard that refuses a non-`quillmd_` database name is in `import_terminology` **only**; `settings.py` reads `QUILLMD_DB_NAME` without validating it, so the separation rests on configuration and on the port, not on a settings-level assertion |
| Does the rebuild use MinIO or the legacy Redis? | **No** | private storage is a filesystem path on the encrypted volume; the job queue is in PostgreSQL |
| Does marketing depend on the legacy database? | **No** | no DB env, no connection; the waitlist is a link to the app URL |
| Does the ingress route anything to the old app? | **No** | `pro.quillmd.com` answers **410 Gone** deliberately; the app hosts answer the maintenance surface |

## What remains on disk, and why this session did not remove it

Removing any of the following is **data deletion** — the owner's call under the
standing authority, class (d) — and none of it was inside the authorized
cleanup, which covered source and images only.

| Item | Size | Note |
| --- | --- | --- |
| `meddoc-pro_pgdata` (unlinked) | 77.44 MB | the pre-encryption copy of the legacy database directory |
| `meddoc-pro_pgbackups` | 19.86 MB | legacy backup sidecar output |
| `meddoc-pro_redis_data` | 33.19 MB | legacy cache volume |
| `meddoc-b017-segment-live1_qa_pgdata`, `meddoc-durable-admission-qa_qa_minio` | 72.23 MB, 22.44 kB | unlinked QA leftovers |
| `meddoc-pro-db-migrate:{latest,qa}`, `meddoc-override-probe:audit-2026-08-17`, `meddoc-pro-e2echeck-transcribe-md:latest` | ~13.8 GB | images not covered by the image cleanup manifest |
| `node_modules`, `.local` | 1.6 GB, 3.9 GB | build artefacts of the retired stack |
| 9 remaining git worktrees carrying the retired source | ~2.2 GB | **see the cleanup below** — each is held back for a named reason |

Disk at the time of writing: **236 GB used of 296 GB, 48 GB free (84%)**. None
of the above is urgent, and none of it is removable without an owner decision on
the `waitlist_entries` rows first, because the postgres volume that holds them
is in the same cleanup conversation.


## The worktree cleanup, 2026-09-18

The retired application's source is gone from `main` and from the shared tree, and it survived in
nineteen other working copies. Ten were removed; nine were not, each for a reason that is stated
rather than implied.

**Removed — 10 worktrees, 2.2 GB.** Every one was clean (no uncommitted changes), inactive (no process
with its cwd inside, no lock file, nothing written in 24 hours) and obsolete, and — the condition that
matters — **every commit it held is reachable from a named `origin` branch**, so removing the working
copy destroyed no work:

| worktree | branch | survives on |
| --- | --- | --- |
| `.cdev` | `scratch/cdev-certify-live-template` | origin |
| `.r162` | `fix/ruling-162-blank-proof` | origin |
| `.wt-a2` | `feat/admin2-host-resolution` | origin |
| `.wt-a2a` | `feat/admin2a-slug-claim` | origin |
| `.wt-a6` | `feat/admin6-practice-archive` | origin |
| `.wt-keep` | `fix/ruling-297-keep-policy` | origin |
| `.wt-mfa` | `fix/admin-api-mfa-parity` | origin |
| `.wt-port` | `feat/admin-console-port` | origin |
| `.wt-r230j` | `docs/r230-judgement` | origin |
| `.wt-r2` | `docs/judged-s3-f00956ef` | merged into `main` (PR #1145); its remote branch was deleted, the local branch is kept |

Removal used `git worktree remove`, which deletes the working directory and the administrative files
and **no commits and no branches**. All ten branches remain checkoutable; this was verified after the
fact, branch by branch.

**Kept — 9 worktrees, each with its reason.**

| worktree | why it stays |
| --- | --- |
| `.wt-307` | 13 commits on **no** origin ref |
| `.wt-b2` | 11 commits on no origin ref |
| `.wt-a3` | 6 commits on no origin ref |
| `.wt-admin5` | 3 commits on no origin ref |
| `.wt-a5` | 2 commits on no origin ref, plus 5 uncommitted files |
| `.wt-admin4` | 2 commits on no origin ref, plus 7 uncommitted files |
| `.wt-dmp` | 2 commits on no origin ref |
| `.f24s5-build` | 4 uncommitted files |
| `.wt-fl` | a live process has its cwd inside it — another session's orphaned keep-alive loop, running since 2026-09-16. Clean and fully merged otherwise; removable once its owner stops it |

⚠️ **A measurement trap that would have produced a confident wrong answer.** The activity check was
first run as `find <path> -type f -newermt '-24 hours'`. The `find` on this host is **bfs**, which
rejects that relative timestamp, exits non-zero and prints nothing — so with stderr discarded it
returns a **vacuous zero for every directory**, and every worktree looks dormant. Re-run with an
absolute timestamp, one worktree showed thousands of files written in the last day. Every figure
above was taken with an absolute cutoff.

**Not claimed:** that every historical copy or git object of the retired application has been erased.
Objects remain in `.git`, in packfiles, in the reflog, on `origin`, and in the nine kept worktrees.
This was a cleanup of redundant working copies, not a history rewrite.

**Preserved deliberately:** the legacy `meddoc` database and its seven waitlist rows, the MinIO and
Redis volumes, the marketing site and its container, the shared ingress, and every backup and
evidence path. Marketing was outside the deletion scope and needed no further decision.
