# §2.5 DECLARATION — THE ANNOTATION ACT (ruled mutation)

**Rulings #155(b) and R1's recovery clause.** Append-only. This act writes audit
rows and **touches nothing else** — no visit row, no fill manifest, no document
byte.

⚠️ **THIS IS NOT A DEPLOY.** It is an irreversible append to `audit_logs`, run
through `scripts/run-ruled-mutation.sh`, which requires this declaration to be
**TRACKED, UNMODIFIED and COMMITTED** before the act — so the commit timestamp
provably precedes the rows, in the units the rows themselves carry.

## WHAT IS WRITTEN

| population | label | rows |
|---|---|---|
| SIGNED visits whose artifact printed no E/M | `EM_OMITTED_IN_SIGNED_ARTIFACT` | **10** |
| servable visits whose template binding was destroyed | `TEMPLATE_PROVENANCE_LOST` | **29** |

## MUST CHANGE

| quantity | before | after |
|---|---|---|
| `audit_logs` | **11,962** | **12,001** (+39) |
| rows bearing `EM_OMITTED_IN_SIGNED_ARTIFACT` | **0** | **10** |
| rows bearing `TEMPLATE_PROVENANCE_LOST` | **0** | **29** |

⚠️ **+39 ROWS ACROSS 38 DISTINCT VISITS, AND BOTH NUMBERS ARE CORRECT.** The two
populations **overlap by exactly one visit**. That visit receives TWO rows because
it carries two distinct facts — an E/M omitted from its signed artifact, and a
destroyed template binding — not one fact recorded twice. Stating only "39" or
only "38" would answer a question nobody asked.

⚠️ **THIS CLOSES THE PAIRED SEAL.** The migration deploy of `36ad23ce` declared
this same counter in the opposite direction — *"this deploy writes ZERO rows
bearing any of the five new labels"* — and was judged at 0. *A quantity shared
across consecutive acts is declared in BOTH, in opposite directions; the pair is
what makes an out-of-band write checkable from either side.*

## MUST NOT CHANGE — the whole point of #155(a)

| quantity | must stay |
|---|---|
| visits | **51** |
| signed visits | **34** |
| patients | **40** |
| note_templates | **11** |
| CERTIFIED twins | **1** |
| `em=null` + scored + SIGNED | **10** |
| NULL `noteTemplateId`, servable | **29** |

**#155(a) ruled that the ten already-signed records STAY AS SIGNED.** The freeze
is this product's deepest promise: retroactively inserting an E/M the artifact
never carried would make the SERVED document differ from what was ATTESTED. This
act makes the gap VISIBLE without moving a byte, and the rows above are how that
promise becomes checkable rather than merely intended.

## WHAT THE ROWS SAY, AND WHAT THEY REFUSE TO SAY

The 29 carry `retrospective: true`, the measurement time, the destruction window
(`2026-07-07..2026-08-27`, the `updatedAt` range of the affected set), and:

    "originalTemplate": "not identifiable — no deletion audit row was ever written"

⚠️ **NEVER AN INFERRED ID.** Measured: `audit_logs` holds 9 template-targeted rows
and every one is `TEMPLATE_TWIN_*` — none a deletion. The old `ON DELETE SET NULL`
destroyed the binding and nothing recorded what it had been, so the original id is
genuinely unrecoverable. The metadata says that, rather than a plausible guess.

## SAFETY PROPERTIES, EACH VERIFIED BEFORE THE ACT

- **Idempotent**: every INSERT is guarded by `NOT EXISTS (action, targetId)`. An
  append-only table has no undo; running it twice must not double the record.
- **Pre-write population guard**: it REFUSES unless 10 / 29 / 1 still hold. A
  population that moved since this file was committed means the declaration
  describes a different world.
- **Dry-run first, and it was**: 11,962 / 10 / 29 / 1 → 39 across 38, nothing
  written.
- **UUID ids, deliberately**: the app writes cuids. Measured before choosing —
  `audit_logs` has ZERO inbound foreign keys and ZERO check constraints, so
  nothing breaks, and a backfilled row being distinguishable at a glance is worth
  having. `retrospective: true` is the authoritative marker; the id shape is a
  weaker second one.
