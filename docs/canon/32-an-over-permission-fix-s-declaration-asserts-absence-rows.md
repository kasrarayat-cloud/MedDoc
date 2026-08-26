> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **66 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## AN OVER-PERMISSION FIX'S DECLARATION ASSERTS **ABSENCE** ROWS

**Standing 2026-08-14. Contributed by the GI session; verified here against
`main` before it was written down.**

Most §2.5 declarations assert what must APPEAR after a deploy. That is the right
shape for a change that ADDS a capability. It is the wrong shape — and a
dangerous one — for a fix to something that was **too permissive**.

> **A presence-only declaration cannot detect over-admission. "Is the new code
> shipped?" passes just as happily on the broken version.**

⚠️ **REFERENCE CASE — two non-billable ICD-10 headers on the accepted side of a
billing floor.** A GI cohort's first draft added `'K21.0'` and `'K22.7'`. Both
are subcategory HEADERS, not submittable codes: FY2023 expanded `K21.0` into
`K21.00`/`K21.01`, FY2017 expanded `K22.7` into `K22.70`/`K22.71x`. Measured
against the real module at the time:

    isValidIcd10('K21.0')   true    ← a non-submittable code ADMITTED
    isValidIcd10('K21.00')  false   ← the code a chart maps to, still DROPPED

So the fix for *"GI codes get dropped"* **failed at its own purpose and created
False Claims Act exposure at the same time**, in the file whose header names that
exact risk. Verified on `main` after the fix: `K21.0` and `K22.7` absent,
`K21.00`, `K21.01`, `K22.70` present.

⚠️ **AND THE TELL WAS INSIDE THE AUTHOR'S OWN DIFF — "THE EVIDENCE WAS IN THE
ARTIFACT I AUTHORED".** The comment written beside `'K22.7'` was the official
title of **`K22.70`**. The correct code had been written down, in prose, on the
same line as the wrong one.

The declaration therefore carried a row asserting `'K21.0'` must still read
**0** in the shipped validator — and the guard
(`icd10-allowlist-gastroenterology.test.ts`) refuses both headers **paired with
an arm asserting the billable children ARE allowed**, because refusing both
would be a stricter floor and a worse product. Mutation-proved: re-admitting
`K21.0` reddens naming it.

