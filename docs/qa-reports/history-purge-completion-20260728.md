# History purge — completion pass (2026-07-28)

Completes the purge of `docs/qa-reports/twin-real-visit-20260726.docx`
(blob `0c56522fa4c97678746fd8d4ba3dd6f6ab40b70d`, a FILLED clinical export,
49 402 bytes) begun in commit `d6ed2b3c` on 2026-07-27. That session was cut off
before it verified its own result. This pass reconstructed the state from
evidence and closed what was left.

**The headline: the previous pass reported the blob "destroyed … from origin".
That was not true when it was written.** Origin still served the blob to anyone
who ran `git clone --mirror`. It is now reduced to three refs we cannot delete —
see Residual.

---

## What was already done, and verified here

| Step | State found | Evidence |
|---|---|---|
| `filter-repo` rewrite ran | DONE | `9d65cbfa` (the introducing commit) does not resolve; every commit after 2026-07-26 re-hashed; pre-2026-07-24 SHAs (`95d5898`, `26e4f4c`, `4088f10`, `3a369af`, `1f221ef`) unchanged |
| Blob gone from working clone | DONE | `git cat-file -e 0c56522f…` fails; `git rev-list --objects --all \| grep twin-real-visit` empty |
| Reflogs expired + gc | DONE | HEAD reflog 6 entries (all post-rewrite); only `main` and `origin/main` carry non-empty reflog files out of 196; `git fsck --unreachable` returns 4 objects, none the blob |
| Origin re-added after rewrite | DONE | `filter-repo` strips remotes by design; `origin` present and functional |
| Force-push landed on **branches and tags** | DONE | Mirror clone of origin: **0** of 92 branches and **0** of 67 tags reach the blob |
| Branch protection restored | DONE | `allow_force_pushes.enabled = false`; all 6 required status checks intact; repo `private: true` |
| Other clones on the box | DONE | 40 `.git` directories enumerated box-wide; **0** carry the blob |
| Safety bundles | DONE | 6 `.bundle` files found under `~/release-evidence/`; each fetched into a throwaway store and checked — all clean. The one thin bundle that failed a bare fetch was resolved by seeding its prerequisites from the base bundle first, then verified clean |
| Docker images | DONE | `.dockerignore:16` excludes `docs`. All 7 retained images (`:latest` + 5 rollback tags + worker variants) checked **from inside** via `docker run --entrypoint sh … find` — clean |
| Prevention guard | DONE | `scripts/hooks/pre-commit` present; `core.hooksPath=scripts/hooks`; root `package.json` `prepare` re-installs it on every `npm install` |
| AGENTS.md lesson | DONE | "A tracked clinical file means a HISTORY REWRITE, not `git rm`" |
| CI on rewritten `main` | GREEN | `079278cc`: CI ✅, secrets-scan ✅, e2e ✅ |

## What was NOT done, and was completed in this pass

### 1. Origin still served the blob — 11 refs (NOW: 3)

A mirror clone of origin returned the blob. Not from a branch and not from a
tag — from GitHub's read-only `refs/pull/*` namespace:

- `refs/pull/{142,143,144,153,155,156,160,161}/merge` — **8 open dependabot PRs**
- `refs/pull/{415,417,418}/head` — 3 closed/merged PRs

**Why the previous pass missed this.** Its own commit message records the check
it ran: *"PR #171 is MERGED, not open, and no currently-open PR touched the
file."* That is the wrong question. Those 8 dependabot PRs never touched the
file. GitHub *computed a test-merge of each open PR into `main`* at
2026-07-27 17:32 UTC — while `main` still carried the blob — and published each
result as `refs/pull/N/merge`. The poison came from the base side, not the PR
side. **A PR does not have to touch a file to hold it.**

**Fix applied.** GitHub drops the `/merge` ref when a PR closes — verified as a
negative control first: `#415`/`#417`/`#418` are closed and have a `/head` ref
but *no* `/merge` ref, while open `#142`/`#153` had both. Closed all 8 PRs, each
with a comment explaining why. Re-mirrored origin: **0 `/merge` refs remain on
any of the 8.** Dependabot regenerates these against the rewritten `main`; the
dependency bumps themselves are unaffected.

### 2. SHA fallout in QA-report READMEs — 3 dead references

The rewrite re-hashed every commit after 2026-07-26, leaving dangling SHAs:

| Doc | Was | Now | How it was re-derived |
|---|---|---|---|
| `prod-lanedelete-20260727/README.md` | `41ec3a44` | `2e7310ab` | Exact title match against GitHub's retained Actions run record (`test(prod-smoke): a CUSTOM imaging template fixture`, 19:42Z) |
| `prod-lanedelete-20260727/README.md` | `0e5257ce` | `5fc32e9b` | Unique tip of `main` at 20:36:01Z, when app image `4719eef70099` was built |
| `prod-verifierfix-20260727/README.md` | `889f3748` | `943a1b6f` | The merge of PR #415 — a unique commit |

Re-derived from evidence, not memory: `filter-repo`'s `commit-map` was gone with
`.git/filter-repo/`. GitHub's workflow-run history survives a rewrite and still
carries pre-rewrite head SHAs alongside commit titles — it is the mapping table
you thought you'd lost.

Also un-stuck the stale "Open" status on the purge item in the lanedelete README.

### 3. Stray scratch the previous close-out missed

- `/opt/meddoc-pro/.playwright-mcp/page-*.yml` — 2 accessibility snapshots
  (these carry rendered note text), written 22:03 and 22:05
- `/tmp/qa-signed-preview.pdf` — a 4-page signed-preview PDF, written 23:24

Both post-date the 22:03 hygiene commit, which is exactly how they survived a
sweep that ran before them. Destroyed with `shred -u -n 3 -z`, exit code checked
per file rather than inferred from the file's absence. Trash: 0 files.

The two `--mirror` clones this investigation made were themselves
blob-carrying copies; both were shredded in-session.

---

## Residual — NOT closable by us, needs a human action

Three refs on origin still reach the blob:

    refs/pull/415/head    (PR #415, MERGED)
    refs/pull/417/head    (PR #417, CLOSED)
    refs/pull/418/head    (PR #418, CLOSED)

`refs/pull/*` is owned by GitHub and is **read-only** — it cannot be pushed,
force-pushed or deleted with git. For a closed or merged PR the `/head` ref is
permanent. Closing the PR does not help; these are already closed.

**This is a harder residual than the one the previous pass wrote down.** That
note said GitHub "retains unreachable objects until its own GC, so the blob may
stay fetchable by SHA for a period" — a decaying risk. It is not decaying. The
blob is *reachable* from live refs, so GitHub's GC will never collect it. It
persists until someone acts.

**The only remedy is a GitHub Support request** asking them to purge the
`refs/pull/*` entries and cached views for that blob — this is the documented
path for sensitive data in PR refs. That is an outward-facing request naming a
clinical-data incident, so it is left for the repository owner rather than filed
autonomously. Suggested wording:

> Private repo `kasrarayat-cloud/MedDoc`. We removed a file containing regulated
> health information from all branches and tags via `git filter-repo` + force
> push. Blob `0c56522fa4c97678746fd8d4ba3dd6f6ab40b70d` remains reachable via
> `refs/pull/415/head`, `refs/pull/417/head` and `refs/pull/418/head`. Please
> purge those pull-request refs and any cached views of that object.

**Exposure in the meantime.** The repository is private with a sole
collaborator. A plain `git clone` does *not* fetch `refs/pull/*` — verified: a
fresh default clone does not contain the blob. It takes `--mirror`, or an
explicit `refs/pull/*` refspec, plus repo access.

---

## Prod

Untouched throughout. 10/10 containers healthy, `RestartCount` 0 on every one.
`app.quillmd.com` 307, `pro.quillmd.com` 200, `admin.quillmd.com` 404,
`quillmd.com` 200; co-tenants `leathererp.com` 200, `www.leathererp.com` 301,
`staging.quillmd.com` 200. No image rebuilt, no container restarted, no
migration run. Disk 73% before and after.

## Separately flagged — not acted on

`docs/smoke-test-2026-05-04/phase-C/export.docx` and `export.pdf` are tracked in
git and are *filled* documents. The content is demonstrably synthetic —
"Dr. Smoke Tester MD", patient "Smoke TestPatient One", 2026-05-04 — so this is
not a PHI incident. But AGENTS.md close-out hygiene says a filled clinical export
is treated as PHI "regardless of whether the patient is real or synthetic", and
that filled exports never belong under `docs/`. By that rule these two files
qualify, and clearing them would mean a second `filter-repo` rewrite and another
force-push over a protected branch.

That is well outside this brief and is a judgement call about a rule's reach, not
a defect. **Owner's decision** — flagged here, deliberately not acted on.
