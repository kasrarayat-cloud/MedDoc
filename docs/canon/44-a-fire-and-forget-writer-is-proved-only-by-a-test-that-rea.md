> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **92 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A FIRE-AND-FORGET WRITER IS PROVED ONLY BY A TEST THAT READS IT BACK

**Standing rule for audit rows and every other side effect written with `void`,
`.catch(() => {})`, or a detached promise.** If nothing awaits it and nothing
reads it, its failure is invisible by construction — and that is usually
deliberate, because an audit write must never break a clinical action.

> **A gate that claims "and the refusal is audited" has not been tested until
> something queries the row.** Otherwise the claim is a comment.

⚠️ **REFERENCE CASE — THE SAME DEFECT THREE TIMES.** `AuditAction` values live in
three places, and each layer looks sufficient from the one above it:

| Layer | Passes when the layer below is missing? |
|---|---|
| the TypeScript union in `audit.ts` | ✅ `tsc` is happy |
| the Prisma enum in `schema.prisma` | ✅ `prisma validate` is happy |
| **the Postgres enum** — needs its own `ALTER TYPE … ADD VALUE` migration | ❌ the write throws at runtime |

- **2026-08-03** — a sign refusal shipped whose audit row silently did not: the
  union was updated, the Prisma enum was not. Banked then as *"the TS union is
  not the database"*.
- **2026-08-06, attempt 1** — an edit landed in `audit.ts` only, because the
  `schema.prisma` anchor missed on indentation. Caught by an occurrence
  assertion (see the section below).
- **2026-08-06, attempt 2** — landed in **both** and still not in the database,
  because a Prisma enum VALUE requires its own migration. `prisma validate`
  passed, `tsc` passed, **3192 unit tests passed**, and the refusal fired
  correctly with a 403. The app logged
  `invalid input value for enum "AuditAction"` and swallowed it.

**Only an E2E that queried `audit_logs` for the row caught it.** So:

1. **Adding an enum value is THREE edits**, and the third is a migration. Check
   `pg_enum` after applying, not `prisma validate`.
2. **Every audited gate asserts the ROW**, by action and target — not the status
   code. The status code is written by the branch you can see; the row is
   written by the part that fails silently.
3. **Do not "fix" this by awaiting the audit write.** The fire-and-forget is
   correct: a failed audit must not refuse a doctor's sign. The cure is a test,
   not a stricter runtime.

