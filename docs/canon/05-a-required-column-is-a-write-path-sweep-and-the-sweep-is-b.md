> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **14 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A required column is a WRITE-PATH sweep, and the sweep is BY TABLE

**Standing rule for any migration that adds a NOT NULL column, or any constraint
that makes an existing shape illegal.** Enumerate every write path *before* the
column lands, not after CI finds them one at a time.

T3 added `practiceId` to `transcribe_visits` and cost **five CI cycles**. Four of
them were the same mistake at a different altitude:

| I enumerated | It lived in |
|---|---|
| `isSkinRounds` — the accessor | `next.config.ts`, reading the raw env var |
| flag consumers | a hardcoded **destination** in the command palette |
| three build-block keys | a fourth, `target: builder` |
| three models' required fields | a fourth model, `User.passwordHash` |
| `transcribeVisit.create` — the ORM method | `INSERT INTO transcribe_visits` — raw SQL |
| a named subset — *"every write that sets `signedAt`"* | **the other members of the subset I had just named** |

The first five are the same shape: **the inventory was taken at the layer I was
thinking in, and the thing lived one layer down.** The fifth was the worst of
those, because raw SQL has no type checker — a required column is invisible
until the database refuses the row at runtime.

⚠️ **THE SIXTH IS DIFFERENT AND IS THE ONE TO WATCH FOR. NAMING A CLASS IS NOT
ENUMERATING IT.** T4's commit message said, in as many words, *"the createdBy
sweep covered every CREATE; signedBy applies only to the SUBSET that sets
signedAt."* Having written that sentence I fixed exactly ONE member of the
subset — the one the database had already refused — and shipped. The other two
reddened CI on the next run.

The failure was not searching the wrong layer. It was **not searching at all**,
because the sentence felt like the work. So: **a named subset is swept by its
DEFINING PREDICATE, never by memory of which members were touched.** Here the
predicate is *"every write that sets `signedAt`"*, and the sweep classifies each
site by BEHAVIOUR — signs / never signs / clones — with an assertion that
`signs == names_signer` for every one. If you can state the rule, you can grep
for it; if you only state it, you have written a comment.

So the sweep has a fixed shape:

1. **BY TABLE, not by API.** Search the table name, then the ORM method. Both.
   `grep -rniE 'insert into ["\x27]?<table>'` **and** `<model>.(create|upsert|createMany)`.
2. **Clone and bulk paths are VERIFIED, not assumed.** `select * from <table>`
   carries new columns automatically — but confirm the source is the table
   itself. `INSERT … SELECT` from a narrowed projection does not.
3. **Type-check is decisive only for TYPED sites.** With the column required,
   `tsc` 0 errors proves every typed create satisfies it. Payloads typed `any`
   are invisible to it — read those.
4. **POSITIVE-CONTROL THE SWEEP'S OWN PATTERN before believing its zero.** Mine
   lied in both directions inside five minutes: first `0 sites` (shell escaping
   ate the pattern — a false all-clear that would have ended the search), then
   `3 MISSING` that were fine (a 40-line window could not see a value set on a
   spread object defined earlier). A sweep that reports nothing and a sweep that
   is broken produce the same output.
5. **MUTATE THE CODE, NEVER A LIVE DATABASE.** Proving a constraint-backed test
   can go red means changing the SOURCE (the assertion, the column name), or
   running against a throwaway database — never `ALTER TABLE … DROP CONSTRAINT`
   on a stack other tests share.

   ⚠️ This is written down because it cost real damage on 2026-08-05. A mutation
   dropped `transcribe_visits_signed_requires_signer`; the gate's own
   `UPDATE … SET "signedBy" = NULL` then SUCCEEDED, nulling 21 signers; and the
   re-`ADD CONSTRAINT` failed **because of the rows it had just created**. The
   database was left with unattributed signatures AND no constraint — the exact
   state that test exists to prove impossible.

   Two corollaries, both earned:
   - **Any write inside a gate that a constraint is supposed to refuse belongs
     in `BEGIN; … ROLLBACK;`.** Then the attempt is observable and never
     consequential, whatever state the constraint is in.
   - **NEVER pipe a repair or a re-add to `/dev/null`.** The silent failure is
     how "restored" became untrue for twenty minutes. Read the exit code, then
     re-verify the object exists.

6. **Prefer DERIVING the value in the query over threading a parameter.** T3's
   raw-SQL sites take
   `(select "practiceId" from transcribe_md_patients where id = …)`.
   A hand-passed value can only be correct or rejected; a derived one cannot
   drift.
7. **A RAW `CREATE INDEX` / `ADD CONSTRAINT` IS DECLARED IN THE SAME COMMIT, OR
   ITS INEXPRESSIBILITY IS DOCUMENTED IN PLACE.** A migration that adds an index
   in SQL and does not touch `schema.prisma` has created drift, and drift is
   invisible until something else trips over it.

   ⚠️ Written down because T3 and T4 both did it — the same programme that was
   *fixing* drift introduced two more instances (`transcribe_visits_practiceId_idx`,
   `transcribe_visits_signedBy_idx`), and they were only found by enumerating.

   Where Prisma genuinely cannot express the object — PARTIAL indexes,
   expression/GIN/GiST indexes, `NULLS NOT DISTINCT` — document it beside the
   model in the `schema.prisma:1700` style: name the index, give its real DDL,
   and say what a naive "fix" would break.

   ⚠️ **AND THE NAIVE FIX IS SOMETIMES WORSE THAN THE DRIFT.** `note_templates`
   carries a PARTIAL unique on `(doctorId, encounterType) WHERE status='active'`.
   Declaring `@@unique([doctorId, encounterType])` to "close the drift" would
   create a FULL unique — strictly stronger than the database enforces — and
   production already holds a row group that violates it. Check what the
   constraint actually says before declaring you are merely writing it down.

   **STANDING EXPECTATION: the drift enumeration reports UNDECLARED-PLAIN = 0.**
   Partial and expression indexes are the only permitted residue, and each is
   documented. Checkable at any time by comparing `pg_indexes` against the
   `@@index`/`@@unique`/`@unique` declarations in the schema.

8. **The migration ABORTS on any underivable row before `SET NOT NULL`.**
   `RAISE EXCEPTION` on a non-zero count. A partially-backfilled column that
   then takes NOT NULL is a migration that half-ran and reported success.

⚠️ **The one that mattered was production code.** `src/actions/visits.ts` is the
real visit-creation path; it would have failed for every doctor on the first
request after deploy, with `Argument \`user\` is missing` — an error that does
not even name the missing column. Finding it took enumerating rather than
patching what CI happened to surface.

