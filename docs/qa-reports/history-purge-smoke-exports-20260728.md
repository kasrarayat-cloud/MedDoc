# History purge — the tracked smoke exports (2026-07-28)

Purged `docs/smoke-test-2026-05-04/phase-C/export.docx` (blob
`5e9cd8a9f47edc8fb0f02794134f556a4478bab9`) and `export.pdf` (blob
`164026c1da969e49e7aa31bcae3e79b1e8a16f8a`) from every reachable location.

**The ruling, applied without adjudication.** Both files are *filled* clinical
exports. Their content is plainly synthetic — "Dr. Smoke Tester MD", patient
"Smoke TestPatient One", 2026-05-04 — and the decision was that this makes no
difference: the close-out rule treats a filled clinical export as PHI regardless
of whether the patient is real, so there is no adjudication class and no
argument to have at the moment one is found. The posture cannot depend on
knowing which, because by the time you are asking, the file already exists
somewhere it should not.

The rest of `docs/smoke-test-2026-05-04/` — the run logs, metadata, screenshots,
`cleanup.sql`, the executive summary — is untouched and stays.

---

## What it cost, and why that number matters

The twin-real-visit purge four days earlier removed a file that was **four days
old**: one branch, ten tags, one commit pruned. These two had been sitting in
`main` since **2026-05-04** (PR #108). Same two files' worth of content;
~200× the blast radius, purely from age:

| | twin export (4 days old) | these (85 days old) |
|---|---|---|
| Branches + tags carrying it | 1 branch, 10 tags | **75 of 141** |
| Local branches to clear | — | **104** |
| Stale clones on the box | 22 | **31** |
| `refs/pull/*` refs, permanent | 3 | **293, across 300 PRs** |

That last row is the one that never comes back down. `refs/pull/*` is
GitHub-owned and unpushable, and a new one is minted per PR. **The residual grew
by roughly one permanent ref for every PR opened while the files sat there.**
The cost of a tracked clinical file is not fixed — it compounds, and it
compounds in the one place a rewrite cannot reach.

---

## Procedure and checkpoints

| # | Step | Result |
|---|---|---|
| 0 | Sequencing guard | no live git/filter-repo process, no locks, no `refs/original`, `main == origin/main`, tree clean, one worktree |
| 1 | Close open dependabot PRs | 10 closed (#145–#159) so no new `/merge` ref could capture the pre-rewrite `main` |
| 2 | Rewrite | `git filter-repo --invert-paths` on both paths, run against a **fresh `--mirror` clone** so every origin ref was in scope — not the working clone, which had only 104 of them |
| 3 | **Tree-identity proof, before any push** | rewritten `main` tree vs original: differs by exactly the two exports (2775 → 2773 files); every surviving blob hash byte-identical. History changed, content did not |
| 4 | Commit-count proof | `main` **933 → 933**. Nothing lost. The `--all` count fell 2559 → 2342 entirely inside `refs/pull/*`, which cannot be pushed anyway |
| 5 | Branch protection | read and saved verbatim; `allow_force_pushes` relaxed alone; restored immediately; **verified field-by-field against the saved copy — 9/9 identical** |
| 6 | Force-push | all 74 heads + all 67 tags. Not `--all` from the working clone: that would have pushed 104 stale local branches over origin, several backing open PRs |
| 7 | Local clone | reset `main` onto the rewrite, deleted 103 stale local branches, `reflog expire --expire=now --all`, `gc --prune=now` → both blobs **GONE**, path in 0 refs |
| 8 | Box-wide clones | 31 stale clones under `~/` carried them (worktrees, release-witness, reviews, release-programs). Object stores shredded, trees removed. **Re-scan: 0** |
| 9 | Origin verification | fresh `--mirror`: **0 heads, 0 tags**. Fresh default clone: both blobs absent |
| 10 | `/merge` refs | 7 open PRs (#192, #204, #209, #210, #211, #362, #371) still held a test-merge against the old `main`. Closed **and immediately reopened** — GitHub drops `/merge` on close and recomputes on reopen. All 7 verified ABSENT; all 7 PRs are OPEN again and unchanged |
| 11 | Docker | `.dockerignore:16` excludes `docs`, so no image ever carried them — verified from inside the three keeper images rather than assumed |
| 12 | SHA repair | 226 dangling references across 58 docs, remapped from filter-repo's own `commit-map` |

## SHA repair — and the one place it over-reached

This rewrite's boundary is 2026-05-04, so **every commit since** re-hashed —
including the ones this session had just written, and the ones the *previous*
purge report had already repaired once.

`filter-repo` writes `.git/filter-repo/commit-map`, an authoritative old→new
table. 149 dead hex tokens in `docs/` were real commits; 226 references across
58 files were rewritten from that map, with a uniqueness guard so a token that
prefix-matched more than one commit was skipped rather than guessed.

**It over-reached exactly once, and the reason is worth keeping.** The mirror
included `refs/pull/*`, which still hold *pre-twin-purge* history — so the map
contained `9d65cbfa`, the commit that introduced the twin export and was
destroyed on 2026-07-27. Three docs (including AGENTS.md) cite it deliberately,
as a historical fact about a commit that no longer exists. The script remapped
it to a `refs/pull`-only object that resolves nowhere. Restored by hand.

The lesson: **a commit-map built from a mirror describes more history than the
repository has.** It is authoritative about what changed; it is not a statement
that every entry is a live commit.

One token was left alone on purpose: `b9f699a` in
`docs/design-directions/direction-C.html` is decorative chrome in a mockup
status bar ("apiv7 · b9f699a"), not a citation.

---

## Residual — permanent, and it needs one human action

**293 `refs/pull/*/head` refs, across 300 PRs (#108 … #419).** Every PR opened
since the files were committed. `refs/pull/*` is owned by GitHub and read-only:
it cannot be pushed, force-pushed or deleted with git, and for a closed or
merged PR the `/head` ref is permanent. Because these are *live refs*, the
objects are reachable, so GitHub's own GC will never collect them.

**Only a GitHub Support request removes them.** That is an outward-facing
message naming a clinical-data incident, so it is drafted here for the owner to
send rather than filed autonomously.

### One ticket, covering both purges

> Private repository `kasrarayat-cloud/MedDoc`.
>
> We removed three files containing regulated-health-information-classed content
> from all branches and tags using `git filter-repo` followed by a force push.
> The blobs remain reachable through pull-request refs, which we cannot delete.
>
> Please purge these objects and any cached views of them:
>
> * `0c56522fa4c97678746fd8d4ba3dd6f6ab40b70d`
>   (`docs/qa-reports/twin-real-visit-20260726.docx`) — reachable via
>   `refs/pull/415/head`, `refs/pull/417/head`, `refs/pull/418/head`
> * `5e9cd8a9f47edc8fb0f02794134f556a4478bab9`
>   (`docs/smoke-test-2026-05-04/phase-C/export.docx`)
> * `164026c1da969e49e7aa31bcae3e79b1e8a16f8a`
>   (`docs/smoke-test-2026-05-04/phase-C/export.pdf`)
>
> The last two are reachable via `refs/pull/N/head` for N in 108, 110–201,
> 203–205, 207–362, 371–419 (293 refs, full list attached).
>
> All branches and tags are already clean — a default `git clone` does not
> contain any of the three. Only `--mirror` or an explicit `refs/pull/*` refspec
> reaches them.

The full ref list is at `docs/qa-reports/history-purge-pull-refs-20260728.txt`.

**Exposure until then.** The repository is private with a sole collaborator, and
a plain `git clone` does not fetch `refs/pull/*` — verified against a fresh
default clone. It takes `--mirror`, or an explicit refspec, plus repo access.

---

## Prevention

The pre-commit guard already blocked this class before either purge; these files
predate it. AGENTS.md now carries the canonical fixture allowlist as a table
that must agree with `scripts/hooks/pre-commit` (hook wins on disagreement), and
records this purge so the files are not re-added.

## Prod

Untouched by Part C. No image built, no container restarted, no migration run.

---

## Addendum, 2026-07-30 — the purge cleared history; it did not clear the disk

**Summary line:** six copies of these same two exports were still on the host two
days after this purge reported success, in three plain directory SNAPSHOTS under
`~/release-witness/` and `~/reviewer-witness-authz-*/` dated 2026-07-21 — all six
`shred -u -n 3 -z`'d, and the four snapshot trees (8485 files, 366 MiB) swept for
further clinical and credential content, then destroyed.

**Why the original scan could not have found them.** The completion report's
method for stale copies was `find / -name .git` plus `git cat-file -e <blob>` per
repo. **These snapshots are not git repositories.** They are flat directory
copies of the working tree, so there was no `.git` to enumerate and no object
database to query. The blob-oriented scan was correct for clones and blind to
snapshots.

> **Scan for the CONTENT PATH, not only for git objects.** A history purge is a
> claim about refs. It says nothing about a filesystem, and on this host the
> filesystem had six copies of what the refs no longer had.

**And the first sweep under-reported.** A pass bounded at `-maxdepth 6` returned
**4 of the 6** and read as a complete inventory; the other two sat at depth 7.
That is the same defect this project has now hit three times in a week — *an
answer about a set whose boundary was never established*, the shape that also
produced the post-reboot proof's three false greens. A depth-limited sweep is a
sample, never an inventory.

### Boundary of the 2026-07-30 sweep — stated so a reader can judge it

| | |
|---|---|
| **Roots** | `~/release-witness`, `~/reviewer-witness-authz-25047df1-n3tTP4`, `~/reviewer-witness-authz-3a915158-95arZC`, `~/reviewer-witness-authz-50286004-ZTM1jQ` |
| **Depth** | unbounded |
| **Filesystem** | `-xdev`, single device, mounted at `/` |
| **Census** | 8485 files, 366 MiB |
| **Verification of the export removal** | `find / -xdev` (unbounded, whole device) for both basenames and the `phase-C/export.*` path — **zero remaining** |

### What the sweep found before the trees were destroyed

- **Document artifacts:** 21, all committed test fixtures (`blank.pdf`,
  `dra-multipage.pdf`, `sample-note.docx|pdf`, `scanned-no-text.pdf`), the blank
  `WM IOV Template.docx`, and a committed audit PDF. No filled export survived
  the shred above.
- **Audio:** 30 `.wav`, all under `docs/deep-audit-*/artifacts/synthetic-audio/generated/`
  — synthesised audit inputs, not patient recordings.
- **Credentials:** every credential-class variable in the live `/opt/meddoc-pro/.env`
  was tested against the snapshots by value — `AUTH_SECRET`, `DATABASE_URL`,
  `DB_PASSWORD`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`,
  `RESEND_API_KEY`, `SCRIBE_SERVICE_TOKEN`, `MINIO_ROOT_PASSWORD`,
  `MINIO_KMS_SECRET_KEY` — **none present**. Six variables did match and all six
  are non-secret public configuration (`NEXTAUTH_URL`, `PUBLIC_URL`,
  `MARKETING_URL`, `TRANSCRIBE_MD_AUTH_URL`, and the two `NEXT_PUBLIC_*` URLs).
  The matcher was negative-controlled both ways: it finds a value that *is* live,
  and it finds a string that *is* in the snapshots.
- **Clinical free text:** 385 non-source files carry markers like "chief
  complaint" / "date of birth". Inspected by class: these are field LABELS in
  design docs, the compliance register, schema dumps and golden prompt fixtures —
  the vocabulary of a medical application's documentation, not patient data.

### Residual, accepted and named

**Two files were deleted rather than shredded.** `shred` returned non-zero on
`release-witness/authz-b016-pg-trust.conf` and
`reviewer-witness-authz-3a915158-95arZC/AUTHZ-INDEPENDENT-REVIEW-3a915158.md`
(the known mode-`0400` failure), and the directory removal that followed ran
**unconditionally**, so the retry-via-root path was no longer available. Their
blocks are unlinked but not overwritten.

Neither file appeared in the credential-bearing or clinical-content sets above —
a Postgres `trust` fixture and a review markdown — so the exposure is judged
negligible and no free-space overwrite was performed on a shared production host
for it.

> **Process fix this cost:** shred → **check exit codes** → escalate the failures
> via the documented root-via-docker path → **only then** remove the directory.
> Unlinking before the failures are resolved converts a recoverable
> "Permission denied" into a permanent one.

**Disk:** 70% before, 70% after — 366 MiB against a 296 G filesystem is below the
reporting resolution. `~/release-evidence` (570 MiB) was **not** in scope and is
untouched. `/opt/meddoc-pro/backups/`, the blank fixtures and the committed E2E
fixtures all verified intact afterwards.
