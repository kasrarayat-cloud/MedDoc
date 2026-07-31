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

---

## Second addendum, 2026-07-30 — the sweep's own boundary, closed to the device

The addendum above swept **four named roots**. That is the shape of the defect it
was written about: a claim whose boundary was chosen by hand. The relay session
that followed re-ran the sweep with the boundary set to **the whole device**, and
this section records where it looked so the answer can be checked rather than
trusted.

**Verification of the ruling, first — the two shredded roots are gone.**
`~/staging` does not exist anywhere on the device (`find / -maxdepth 4 -type d
-name staging` → nothing), and neither `~/release-witness` nor any
`~/reviewer-witness-*` remains. The purge targets themselves are gone too:
`find / -xdev` for `export.docx`, `export.pdf` and the path fragment
`phase-C/export*` returns **zero**, unbounded, across the whole filesystem.

### Boundary

| | |
|---|---|
| **Roots** | `/` — whole device |
| **Depth** | unbounded |
| **Filesystem** | `-xdev`, `/dev/sda2`, ext4, mounted `/` |
| **Documents censused** | 193 `.docx`/`.pdf` outside `node_modules` |
| **Trees examined in detail** | `~/reviews`, `~/release-programs`, `~/release-reviews`, `~/release-evidence` — **1609 files, 782 MiB** |

### Four directory trees the first ruling never scoped

They are the same liability class `AGENTS.md` now names, and none of them was in
the ruling's two globs. Scanned rather than assumed:

| Class | Result |
|---|---|
| **Purged exports** | zero copies, device-wide |
| **Credentials** | 11 credential-class variables from the live `.env` tested **by value**; `MINIO_ROOT_USER` skipped as under 12 characters and non-discriminating, 4 not set. **Zero hits.** |
| **Clinical free text** | 16 files match `chief complaint` / `date of birth` / `Assessment and Plan`. All 16 classified: 4 are a Playwright **test title** in a results JSON, 12 are the system default template's `styleInstructions` scaffold inside `note_templates` migrations — and those 12 are **byte-identical (`cmp`) to the repo's own tracked migrations**. No patient data. |
| **Audio** | none |

### The control that makes the zeros mean something

Every credential value **self-tested** against `/opt/meddoc-pro/.env` — proof the
matcher works on that value. **That is not sufficient**, and the first addendum's
own lesson says why: it does not prove the matcher ever reached the haystack. A
traversal that silently covers nothing returns zero for everything.

So the same `grep -rlF -- <needle> <roots>` form was run against needles known to
be present: `meddoc` → **204** files, `transcribe` → **304**, `QuillMD` → **8**.
The traversal genuinely enters those trees, so the credential zeros are **real
absences** rather than an untested path.

> A self-test proves the needle. A positive control proves the haystack. A sweep
> needs both, or its zero is a claim about nothing.

### Classified and cleared, so no future sweep re-litigates them

- **170 `.docx` under `~/reviews/native-docx-*/artifacts/`** — synthetic OOXML
  grammar fixtures (`bdo--customXml.docx`, `table-missing-properties.docx`,
  `run-rt--sdt.docx`). Generated parser inputs for the native-DOCX review. Not
  clinical, not filled.
- **`docs/qa-reports/comprehensive-audit-20260514T030426Z.pdf`** — tracked,
  predates the pre-commit guard (which blocks only *added* files), and carries
  **zero** clinical-label hits. A system audit report, not a rendered note.
- **8 third-party template `.docx`/`.pdf`** under `~/.codex/` and
  `~/.claude/skills/` — vendored tooling assets.

### Not destroyed, and why that is the call

These four trees are **verified clean**, so there is no exposure to remediate.
`AGENTS.md` now says repo snapshots are in scope forever and should be reaped by
the session that made them — and these outlived theirs. But the first addendum
deliberately scoped `~/release-evidence` **out**, and destroying 782 MiB of a
prior session's review evidence that provably carries no PHI and no credentials
buys no safety while it does discard the record other reports may cite.

Recorded rather than acted on, with the census above so the next sweep starts
from an inventory instead of repeating it. One removal was made: the empty
leftover directory `~/native-docx-exact-review.MB7eB0` (0 files).

---

## Third addendum, 2026-07-30 — the four clean trees, extracted then destroyed

**Summary line:** the four unowned evidence trees the second addendum censused
and cleared — `~/reviews`, `~/release-programs`, `~/release-reviews`,
`~/release-evidence`, **1609 files / 782 MiB** — had their **36 report/findings
files extracted** to `docs/qa-reports/witness-archive-20260730/` (244 KiB,
committed and pushed BEFORE anything was destroyed) and the **remaining 1573
files plus 5 symlinks shredded** with `shred -u -n 3 -z`, **0 failures**, after
which the four directories were removed and their absence verified.

**Why destroy something already proven clean.** Because being clean is not the
same as being free. A tree that is provably clean today must be **re-proven**
clean by every future sweep for as long as it exists, by people who did not
create it — and the purge these addenda are attached to missed six copies of two
filled exports that sat in precisely this class of tree. The ruling is therefore
extract-then-shred regardless of contents; `AGENTS.md` now carries it as a
standing close-out rule.

### What was extracted, and what was not

| Kept (36) | Discarded (1573) |
|---|---|
| `.md` review receipts, security audits, incident records, verification reports, and the small `*-summary.txt` scan conclusions | source snapshots, build output, container ids, port files, temp paths, file manifests and censuses, 170 synthetic OOXML grammar fixtures, 30 synthesised audit `.wav` |

Archived filenames preserve the original path (`/` → `~`), so each file still
says where it came from.

### The extraction was not a formality

One rescued document records a **service credential observed in a process
command line** on 2026-07-19. It states the value was deliberately omitted, and
its *Required disposition* makes rotation through the approved path a **release
blocker for production authorization**. Nothing in this repository records that
rotation having happened. Six other rescued files carry unresolved-blocker
language; all seven are named in the archive's README.

**Shredding first would have destroyed the only remaining pointer to an open
security item.** That is the argument for step 3 of the new rule: read what you
are about to destroy.

### Controls

- **Admission**, before anything entered the repo: sha1 against every tracked
  file (**0 of 36 already committed** — no duplicates); credentials by value
  (10 vars, **0 hits**); credential *shapes* — `PGPASSWORD=`,
  `postgres://user:pass@`, generic `password|secret|token|api_key` assignments,
  `sk-`, `Bearer`, PEM headers, `AKIA` — **0 hits, negative-controlled against a
  canary** carrying two of those shapes (the canary was then shredded); positive
  control on the traversal (`meddoc` → 18 of 36, `review` → 29).
- **Destruction**: `chmod u+w` applied FIRST — 7 files were read-only, and **6 of
  those were root-owned** and were shredded through the documented
  root-via-docker path rather than unlinked as the owner of the parent
  directory, which is what produced the two-file residual recorded above. 5
  symlinks were **unlinked, never shredded through** — `shred` follows a symlink
  to its target, which is how a sweep destroys something outside its boundary.
  Directory removal was **conditional on zero failures**, not unconditional.
- **Verification**: all four roots absent; a device-wide `find / -xdev` for
  witness-class directory names returns only OS paths
  (`/etc/update-manager/release-upgrades.d`, kernel `drivers/staging`);
  positive-controlled by the same find form returning `/opt/meddoc-pro`.

**Disk:** 73% before, 73% after — 782 MiB against a 296 G filesystem, `avail`
79 G → 80 G. Space was never the reason.
