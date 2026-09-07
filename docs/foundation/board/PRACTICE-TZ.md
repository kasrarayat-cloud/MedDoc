# PRACTICE-TZ — `Practice.timezone`, and the clinical error that is refused until it exists

**Filed 2026-09-07 by the custom-file session, to Design/Admin, under ruling
#264.** The ruling itself is discharged in code: the age injector now **refuses,
blank and with a named reason**, whenever the answer depends on a timezone
nobody has recorded. This note is the other half — the durable request for the
column that retires that refusal.

## THE ASK, IN ONE LINE

> **`Practice.timezone` — IANA (`America/Los_Angeles`, `Pacific/Auckland`),
> captured at signup, editable in settings, and used by EVERY visit-local-date
> derivation.**

Not only by age. Age is simply the first derivation that could not be computed
honestly without it, so it is the one that surfaced the gap.

## WHAT IS THERE TODAY — measured, not assumed

`practices` has **ten columns and none of them is a timezone**:

```
address  audioRetentionDays  createdAt  id  isActive
name     phone               slug       transcriptRetentionDays  updatedAt
```

⚠️ **AND A CARELESS GREP SAYS OTHERWISE.** `grep -icE 'timezone|timeZone|tz'`
over the `Practice` model in `schema.prisma` returns **2** — both of them
`@db.Timestamptz(6)` on `createdAt` and `updatedAt`. The pattern `tz` matches a
Postgres type name. The live `information_schema` is the authority and it was
read before this note was written.

**There IS a timezone in the schema, and it is the wrong one for this job:**
`User.timeZone String? @default("America/Los_Angeles")` (`schema.prisma:813`).

⚠️ **A USER'S ZONE IS NOT THE PRACTICE'S, AND SUBSTITUTING IT WOULD BE WORSE
THAN THE GAP.** The question a consult letter asks is *"what was the local
calendar date where the encounter happened"* — a property of the **practice**,
not of whoever happens to be signed in. A locum covering from another state, an
admin in a different city, or the default nobody ever changed would each move a
patient's printed age by a year, and it would do so **silently and
inconsistently between two readers of the same visit**. The default is
`America/Los_Angeles` for the majority user base, which means the wrong answer
would also be the common one.

## WHY IT MATTERS — the error runs BOTH ways

The visit instant is a `timestamptz`; the DOB is a `@db.Date` at UTC midnight.
Age computed on **UTC** calendar parts is therefore right only for a practice at
UTC.

| visit, in the doctor's own zone | as UTC | UTC says | the doctor sees |
|---|---|---|---|
| 2026-06-13 **19:00** America/Los_Angeles | `2026-06-14T02:00Z` | birthday passed → **68** | it is the 13th → **67** |
| 2026-06-14 **09:00** Pacific/Auckland | `2026-06-13T21:00Z` | not yet → **67** | it is the 14th → **68** |

⚠️ **THE SOURCE COMMENT NAMED ONLY THE FIRST ROW** — *"prints an age one year
high"* — and a fix aimed at one direction would have shipped. The error is
symmetric about UTC, and the second row is the one a fix written from the
comment alone would have missed.

**A one-year-high age on a consult letter is a clinical error, not a formatting
blemish**, and the previous position — *"recorded rather than hidden"* — put the
record in a source comment the doctor does not read.

## WHAT #264 DOES IN THE MEANTIME

`ageAtDateResolved` computes the age at the visit instant shifted to **UTC-12**
and to **UTC+14**. If the two differ, the age is not determined by anything this
system knows, and it **refuses** with `age_timezone_ambiguous`. The reason
travels to the resolver and lands in the manifest's `reasonCode`, so the blank
says *why* instead of `fact_not_mentioned` — *"nobody said it"* — which would
send the doctor looking for a dictation that was never the point.

**It is a total predicate that needs no timezone**, which is exactly why the
ruling chose it over a guess.

### WHAT IT COSTS, so nobody has to estimate it

The window is 26 hours wide, so the refusal fires only when a patient's birthday
boundary falls inside it — of the order of **26/24 days a year, ~0.3% of
visits**, and those are precisely the visits where the old answer was a coin
flip. Measured in the gate over a full year of instants against one DOB:
**≥360 of 365 days answer, ≤2 refuse.** Every other visit is unaffected.

## WHAT LANDING THE COLUMN CHANGES

1. `ageAtDateResolved` takes the practice zone and computes the **local**
   calendar date. The ±26h check becomes unreachable rather than deleted — it
   stays as the fail-closed arm for a practice whose zone is null.
2. Every other visit-local-date derivation stops silently meaning "UTC".
   ⚠️ **That set has not been enumerated here**, and enumerating it is part of
   the work rather than a precondition for it — but `withProcedureDateFact` (the
   printed date of procedure) is the obvious second member and should be
   audited in the same change.
3. The refusal's reason token can be retired from the manifest vocabulary, or
   kept for the null-zone case. Keeping it is cheaper and fails closed.

## ACCEPTANCE

- a practice with no zone still **refuses** rather than assuming UTC — the
  fail-closed arm is not deleted by the fix
- a practice in `America/Los_Angeles` reading the 19:00 visit above prints
  **67**, and one in `Pacific/Auckland` reading the 09:00 visit prints **68** —
  **both directions**, because one direction was already documented and still
  wrong
- the ~0.3% refusal rate goes to zero for practices that have set a zone
