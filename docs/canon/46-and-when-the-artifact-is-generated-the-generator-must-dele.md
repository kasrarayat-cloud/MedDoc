> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **101 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ A scripted edit PROVES ITS OWN APPLICATION**.
> Why the split: `docs/canon/README.md`.

### ⚠️ AND WHEN THE ARTIFACT IS GENERATED: THE GENERATOR MUST DELETE WHAT IT REPLACES

**Standing 2026-08-14.** A regeneration that PREPENDS its output and never
removes the previous copy leaves a file that still contains every value you
assert — and is syntactically dead.

⚠️ **REFERENCE CASE — this programme's own migration, found by CI.** `130cbc22`
regenerated `…_resync_system_default_template_never_editorialize/migration.sql`
and emitted a second `UPDATE "note_templates" SET` above the first. One
statement, two headers. Postgres refused it at deploy —
`syntax error at or near "note_templates"` — taking `a11y-ci`, `CI` and `e2e`
down together on a branch whose unit suite was green.

**Its parity test stayed GREEN, and that is the finding.** The test extracts
`@seed:sections` and `@seed:styleProfile` by regex and deep-equals both against
the TS constant. Both markers were present, correct and byte-identical. **The
values were right and the statement carrying them was not** — the watched-set
failure aimed at a generated artifact: the test asserted the PAYLOAD and
nothing about the SHAPE. Mutation-proved afterwards in the direction that
matters: with the doubled header restored, the new shape arm goes red and the
parity arm **stays green** — `1 failed | 10 passed` — which is the blindness
stated as a measurement rather than as a worry.

So: **a test over a generated file asserts its STRUCTURE as well as its
CONTENT.** Here: exactly one `UPDATE`, one `SET`, one `WHERE`, terminated at
the end.

⚠️ **AND BIND THE STRUCTURAL ASSERTIONS TO CODE.** The first draft of that arm
counted `;` and read **4** on a correct file, because semicolons live inside
the JSONB payload. A structural check that counts string content is the
wrong-QUANTITY failure arriving inside the fix for the wrong-SHAPE one — and it
was caught only because the arm was run against the KNOWN-GOOD file before
being trusted against a bad one. Comment lines are stripped for the same
reason: prose in a migration says `UPDATE` too.

**A DATA MIGRATION IS PROVED BY APPLYING IT, ON A THROWAWAY DATABASE.**
`pg_isready` is not that proof — it returns green during the image's bootstrap
phase, before the target database exists. Poll for the database, apply the full
set, then confirm the row actually moved (`_prisma_migrations` finished, and
the seeded value present in the column). 103 migrations were then swept for the
same doubled-header shape, pattern positive-controlled first: none.

