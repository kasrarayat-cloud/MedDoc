> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **106 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## The substring trap — fourth sighting, same family

`'practice-scope' in source` — an import-insertion guard — matched the word
**"practice-scoped"** in a comment written moments earlier, so two imports were
silently skipped and `tsc` named the missing symbol instead of the real cause.

The family, so the shape is recognisable rather than re-derived each time:

| Sighting | The trap |
|---|---|
| `'dashboard'` contains `'board'` | a flag-ON assertion passed on the flag-OFF label — asserted nothing |
| `backgroundColor` ends in `color` | a matcher-shape census miscounted its own negative control |
| `'practice-scope' in source` matches `"practice-scoped"` | an idempotence check satisfied by PROSE, so a required import was skipped |

**The rule stands and is now cheap to state: prefer `toBe` over `toContain`
whenever the expected value is knowable; when a substring genuinely is the right
shape, check the two candidates are not substrings of each other; and for
"is this already present" checks, match the EXACT token that would be present —
`from '@/lib/practice-scope'`, never the bare word.** Prose is not a proxy for
code, and a file's comments are the one place where the words you are grepping
for are guaranteed to appear.

