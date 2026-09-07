# A NEW L3 FIELD CARRIES A `.default()`, OR IT BREAKS THREE THINGS AT ONCE

**Ratified 2026-09-07, from the REGISTRY-1 surface map.**

`ExtractedEntities` is a single Zod object and every optional family in it
carries `.default([])` or `.default(null)`. That is not style. **A new field
declared without one becomes a REQUIRED key, and three unrelated things break in
the same instant:**

| what breaks | why |
|---|---|
| **every mocked run** | `packages/ai/src/mock.ts` returns only `{chief_complaint: null, hpi: null}` and relies on every other field defaulting. Without a default, every QA and E2E run `SCHEMA_FAIL`s. |
| **module load** | `sample-preview-transcript.ts` calls `ExtractedEntities.parse()` **at module load**, so the import itself throws — a failure that presents as an unrelated file being unimportable. |
| **every resumed job** | `worker.ts` resumes with `resumeState.entities as ExtractedEntities` — a **CAST, not a parse**. Old persisted blobs keep flowing and now carry a type lie the compiler cannot see. |

⚠️ **THE THIRD IS THE DANGEROUS ONE.** The first two fail loudly and
immediately. The cast fails **silently and later**, on jobs that were already
in flight when the field shipped, and the type system actively asserts the
absent key is present.

> **The rule: a new `ExtractedEntities` field is `.default([])`,
> `.default(null)`, or `.optional()` — never bare.**

**And the same reasoning reaches the hand-mirrored interface.**
`EncounterEntitySnapshot` restates the L3 shape by hand for the projector; a new
member added there must be `?:` optional for exactly the same reason — every
existing caller and every fixture constructs it without the new key.
