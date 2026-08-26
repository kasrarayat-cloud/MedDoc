> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **67 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## TEXT PRESENCE IS NOT MEMBERSHIP

**Standing 2026-08-14. Same night, same file, and the verification PASSED while
the module did not even parse.**

> **`grep` answers a question about a FILE. Membership is a question about a
> DATA STRUCTURE. They agree right up until they don't.**

⚠️ **REFERENCE CASE.** A 33-code block was inserted anchored on the
`export const ICD10_ALLOWLIST` declaration rather than on the array's closing
`];`, so the codes landed **outside the array literal** — dangling statements
after the close. The file did not parse. **And the author's verification
reported success anyway:**

    grep -o "'K63.5'" file | wc -l   ->  1     "0 of 33 missing"

The text was in the file. The value was not in the Set.

⚠️ **THE PARSER CAUGHT IT, NOT THE CHECK — which is the part that should worry
you.** Had the block landed somewhere syntactically legal but semantically
wrong, the grep would still have reported 33 of 33 and nothing else would have
objected.

**So allowlist and registry verification asserts THROUGH the structure** —
`ICD10_ALLOWLIST.has()`, `isValidIcd10()` — never through the file text. The
guard on `main` carries **14** membership assertions and **zero** file-text
assertions, plus a non-vacuity row (`expect(all.length).toBe(38)`) so a cohort
that collapsed to nothing cannot satisfy every filter while checking nothing.

