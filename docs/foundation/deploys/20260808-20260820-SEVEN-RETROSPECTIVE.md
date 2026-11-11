# RETROSPECTIVE — seven deploys, 2026-08-08 → 2026-08-20, that reached production unjudged

**Filed 2026-09-05 on owner direction. Evidence recoverable; the gate is not.**

> **A RETROSPECTIVE RECOVERS THE EVIDENCE, NEVER THE GATE.** That sentence is
> already standing law here, and this file is bound by it: nothing below turns
> an unjudged deploy into a judged one.

## The seven

| declaration | shipped? | migrations | judgement in file |
|---|---|---|---|
| `20260808-079b9205` | ancestor of `main` ✓ | **1** | none |
| `20260811-50b02832` | ✓ | **1** | none |
| `20260814-83d22d01` | ✓ | 0 | none |
| `20260814-f975b0cf` | ✓ | 0 | none |
| `20260815-85e82be5` | ✓ | 0 | none |
| `20260820-64c49a45` | ✓ | 0 | none |
| `20260820-cba367fc` | ✓ | 0 | none |

All seven declarations exist, are tracked, and every sha is an ancestor of
today's `main` — so the code shipped and is still shipping.

## ⚠️ WHAT THE RECOVERY ACTUALLY FOUND IS WORSE THAN "UNJUDGED"

The brief was *seven deploys with no judgement*. That is true. It is not the
finding.

**Five of the seven have declarations committed AFTER their own act had begun,
and two of those after an IRREVERSIBLE act had completed.**

Deploy start times recovered from `docs/deploy-logs/` (gitignored, 67 survive on
disk); migration completion times read from `_prisma_migrations` in production.

### The two that carried migrations — the serious class

| | migration finished | declaration committed | gap |
|---|---|---|---|
| `079b9205` | **2026-08-09 00:01:00** | 2026-08-09 00:05:42 | **+4m42s** |
| `50b02832` | **2026-08-11 09:06:35** | 2026-08-11 09:12:21 | **+5m46s** |

Both migrations are applied, `finished_at` set, `rolled_back_at` null:
`20260808230000_b0_units_source_not_null` and `20260811070000_b5_ledger_entries`.

⚠️ **In both cases the irreversible act had ALREADY COMPLETED when the
declaration was committed.** The outcome was knowable. That is precisely the
distinction §2.5 exists to buy — *the record cannot distinguish an honest
declaration from one composed once the outcome was known* — and it is the same
defect as B7 step 3c's backfill, which was 1m57s late. These are 4m42s and
5m46s late.

### The three datable non-migration deploys — a weaker case, stated as weaker

| | deploy started | declaration committed | gap |
|---|---|---|---|
| `83d22d01` | 04:15:00 | 04:20:53 | +5m53s |
| `f975b0cf` | 06:30:19 | 06:36:12 | +5m53s |
| `85e82be5` | 12:50:45 | 12:57:05 | +6m20s |

These are **after the deploy started** but a deploy on this box runs ~20 minutes
and rebuilds containers near the end, so at +6 minutes the post-deploy numbers
did not yet exist. **The declaration was late; the outcome was probably not yet
knowable.** That is a process failure and not an integrity one, and it is
recorded as the lesser thing it is.

### Two cannot be dated

`64c49a45` and `cba367fc` have no surviving deploy log. Their declarations are
committed and their code shipped; when they were written relative to their act
**cannot be established**, and no inference is offered.

## What is recoverable, and is hereby recovered

- **The code shipped and still ships** — all seven are ancestors of `main`.
- **Both migrations completed and neither was rolled back**, with timestamps.
- **Production today is internally consistent**: 111 applied / 0 unapplied, and
  the deploy of `dcc8cabf` judged 34 of 34 against a declaration written before
  the act, which exercises the same invariants these seven declared.

## What is NOT recoverable, and is not claimed

- **Nobody compared production against these seven declarations at the time.**
  The comparisons cannot be run now: the counts they named have been moved by
  roughly twenty later deploys, so any number I produce today would be a fact
  about September, dressed as a judgement of August.
- **The rollback tags are gone**, but not by this session's prune: the tags of
  that era were named for FEATURES (`pre-t5w-20260807`), not shas, so
  `pre-079b9205` never existed. Checked rather than assumed, because "my
  cleanup destroyed the evidence" was the obvious suspicion and it is false.

## The question this raises, which is the owner's

The deploy path's declaration gate is deliberately set to `present`, not
`strict` — strictness proportional to reversibility, per ruling #96(b). The
mutation path is `strict` and requires the declaration COMMITTED before the act.

**This retrospective is evidence that `present` is not enough for a
migration-carrying deploy.** Two of two migration deploys in this window had
their declaration committed after the migration had already finished, and the
gate accepted both — correctly, by its own rules.

⚠️ **I am not changing that gate.** It is a rule about what evidence a deploy
must produce, and #96(b) reasoned it deliberately. Surfaced with the
measurement attached, as a question: *should a deploy whose range contains a
migration require the `strict` (committed-first) declaration that the mutation
path already requires?*
