# `docs/canon/` — the full canon bodies

**Created 2026-08-26 by an owner-directed SPLIT of `AGENTS.md`. Nothing here was
written for this directory: every file is a body MOVED verbatim out of
`AGENTS.md`, with a provenance header added above it and not one character of
the entry itself changed.**

## Why the split happened

`AGENTS.md` had reached **243,023 characters** against a **150,000-character
tool read limit**. A session could therefore load a **truncated rulebook and
never be told** — and a rule you cannot read is not a weaker rule, it is an
absent one. That is a stale-authority hazard, not a formatting problem: the
failure is silent, and it lands on the file that governs a clinical system.

It was split, **never trimmed**. The union of the new `AGENTS.md` and this
directory contains **every heading and every non-blank line** of the pre-split
file — proved, both directions, in the PR that landed it.

## What governs

| | |
|---|---|
| **these files** | the **AUTHORITY**. Full body, verbatim, dated |
| **`AGENTS.md`** | the live instruction set — what a session executes |
| **the CANON INDEX in `AGENTS.md`** | one row per entry: title, its own tell, and a pointer here. **A POINTER, NEVER THE RULE** |

If an index row and a body here ever disagree, **the body is right and the row
is a defect** — fix the row.

## The rule for this directory

> **NEVER REWRITTEN.** Corrections are **appended and dated**, and the superseded
> wording is **kept**, because in this programme the correction is the point.
> Several entries here exist specifically to record that their own earlier
> wording was wrong; deleting that would destroy the evidence the entry is made
> of.

**Adding canon:** the full body goes here as a new file, and its one-line row
goes in `AGENTS.md`'s CANON INDEX, **in the same commit**. Do not grow
`AGENTS.md` back — `scripts/check-agents-md-size.sh` fails at 120,000
characters, and CI enforces the same budget via `gate-agents-md-size.test.ts`.

**Citing an entry:** cite it by its **title**, as everything in this repository
already does. The title is unique, it survives in the index, and a grep for it
lands in `AGENTS.md` and tells you which file the body is in.

## Layout

`NN-<slug>.md`, where `NN` is the entry's original order in the pre-split
`AGENTS.md` — so a directory listing reads in the order the canon was written.
A file carries its entry plus that entry's own subsections.
