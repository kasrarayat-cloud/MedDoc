# Witness archive — extracted 2026-07-30, before the trees were destroyed

These 36 files are the **findings** rescued from four unowned evidence trees
under `~` before those trees were shredded. The raw trees are gone; this is what
survives of them, and it survives because a report is worth keeping and a
snapshot of the source tree never was.

| | |
|---|---|
| **Source trees** | `~/reviews`, `~/release-programs`, `~/release-reviews`, `~/release-evidence` |
| **Census before destruction** | 1609 files, 782 MiB |
| **Extracted** | 36 report/findings files, 244 KiB |
| **Destroyed** | everything else — source snapshots, build artifacts, container ids, port files, temp paths, file manifests, 170 synthetic OOXML fixtures, 30 synthesised audit `.wav` |

Filenames are the original paths with `/` replaced by `~`, so every file still
says where it came from.

## Why they were destroyed rather than kept

They were **verified clean** — no credentials, no clinical content, no copies of
the exports purged on 2026-07-28. That is exactly the point: a tree that is
provably clean today still has to be *re-proven* clean by every future sweep, for
as long as it exists. The 2026-07-28 purge missed six copies of two filled
exports precisely because they sat in trees of this class, and the scan that
looked for them enumerated git repositories — which a directory snapshot is not.

So the standing rule is now **extract, then shred**: findings into the
repository, raw trees destroyed, unowned snapshots never persist. See
`AGENTS.md`, close-out hygiene.

## What was checked before anything was copied in

A file entering the repository is a file entering every future clone, so the
admission check is stricter than the sweep that cleared the trees:

- **Byte-identity against the repo** — none of the 36 was already committed
  (sha1 against every tracked file), so nothing here is a duplicate.
- **Credentials by value** — ten credential-class variables from the live `.env`.
  Zero hits.
- **Credential SHAPES** — `PGPASSWORD=`, `postgres://user:pass@`, generic
  `password|secret|token|api_key` assignments, `sk-…`, `Bearer …`, PEM private
  key headers, `AKIA…`. Zero hits, **and the pattern set was negative-controlled
  against a canary file carrying two of those shapes** (which then got shredded).
  A scan that has not been watched to fire is not known to be a scan.
- **Positive control on the traversal** — the same matcher form found `meddoc` in
  18 of the 36 and `review` in 29, so the zeros above are real absences rather
  than a search that never entered the files.
- **Prose reading** of the two documents whose titles implied they might carry a
  secret that patterns cannot see. One of them
  (`…process-argument-credential-exposure-20260719.md`) records the incident and
  explicitly states the value is omitted — which is why it was safe to keep, and
  why it was worth keeping.

## ⚠️ Live open items rescued here — read these, do not just file them

Seven of the 36 carry unresolved-blocker language. This one matters most:

> **`…security~process-argument-credential-exposure-20260719.md`** — a service
> credential was observed in a process command line on 2026-07-19. The document
> records the value as deliberately omitted, and its *Required disposition* says
> rotation through the approved path is a **release blocker for production
> authorization** until done.
>
> **Nothing in this repository records that rotation having happened.** It is not
> re-asserted as still-open here — that would be a claim this archive cannot
> support — but it is flagged so the next person checks rather than assumes. The
> trees that held it are gone; this file is the only remaining pointer.

The other six: `ci-failure-fc08599-20260721.md`,
`mfa-backfill-restore-rehearsal.md`, `…authz-fc08599-independent…receipt.md`,
`…provider-auth-root-audit-20260719.md`,
`…source-admission-review-ecf3c23~review-report.md`,
`…source-admission-merged-ef9d980~verification-report.md`.

## What is NOT here, deliberately

No source snapshots, no `.docx`/`.pdf`, no audio, no build output, no container
ids or temp paths. Those are not findings — they are the machine's leftovers, and
keeping them is how a liability class reconstitutes itself.
