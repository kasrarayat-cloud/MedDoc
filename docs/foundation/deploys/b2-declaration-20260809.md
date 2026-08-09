# B2 — §2.5 DEPLOY DECLARATION

**Written 2026-08-09T20:36Z, BEFORE the deploy runs and before any post-deploy
evidence exists.** That ordering is the whole point: a post-deploy check written
afterwards is unfalsifiable, because every number has a story available to it
after the fact. This document fixes the one correct answer while it is still a
prediction.

Item: **B2 — the failure paths reach the durable meter.** PR #568.

---

## 1. WHAT KIND OF DEPLOY THIS IS

**CODE-ONLY. B2 carries NO migration.** So the baseline's migration count must
be *identical* afterwards, not merely "applied" — a change there would mean
something entered this deploy that nobody declared.

⚠️ **But the one-line code-only declaration — *"nothing but the image ids"* —
IS NOT SUFFICIENT HERE, and saying why matters.** B2 adds new *writers*. On the
seven wired branches a vendor failure now emits an `api_usage_events` row that
would not have existed before. So this deploy CAN legitimately move a row count,
and the declaration has to say in advance exactly which one and in which
direction, or the check degenerates into "the number moved, and there is a
reason available".

---

## 2. THE BASELINE — measured 2026-08-09T20:36Z, production

| quantity | value |
|---|---|
| `transcribe_visits` | **25** |
| …of which signed | **16** |
| `transcribe_md_patients` | **15** |
| `api_usage_events` | **1325** |
| …`unitsSource='vendor'` | **1325** (`$26.3556`) |
| …`unitsSource='mock'` | **0** |
| `ai_calls` | **1125** |
| `ai_calls` failed-but-billed (`success=false AND inputTokens>0`) | **42** |
| applied migrations | **95** |

---

## 3. WHAT MUST **NOT** CHANGE

- **Clinical counts — visits 25, signed 16, patients 15.** A deploy that moves
  any of these has done something nobody asked for. This row is never omitted.
- **Applied migrations: 95.** B2 carries none.
- **`unitsSource='mock'` stays 0** in production. Production is not mocked; a
  mock row appearing would mean the mock seam leaked into prod, which is the
  exact regression B0-a exists to prevent and which B2's new writers could
  reintroduce if the helper had hardcoded provenance.
- **Existing `api_usage_events` rows are not rewritten.** `totalCostUsd` over
  the 1325 pre-existing rows stays `$26.3556`. B2 adds rows; it edits none.
- **Co-tenants** — `app` 307 · `admin` 404 · `quillmd` 200 · `www` 200 ·
  `pro` 410.

## 4. WHAT MAY CHANGE, AND ONLY THIS

- **The image ids** for `transcribe-md` and `transcribe-md-worker`.
- **`api_usage_events` may GAIN rows, and only in one shape**: rows whose
  `metadata->>'outcome' = 'failed'`. Any new row without that marker is an
  ordinary success-path row and is unrelated to B2.
- **`ai_calls` may gain rows** from ordinary traffic, including — new with B2 —
  a row from `llm-mdm.ts`'s judge catch, which previously wrote none.

## 5. THE HONEST EXPECTATION

**The most likely correct outcome is that NOTHING moves except the image ids.**

The wired branches only fire when a real vendor call fails, and production is
quiet. The 42 historical failed-billed calls accumulated over months, so the
base rate is roughly **one every few days** — a post-deploy window of minutes
should see **zero** new failure rows.

⚠️ **THEREFORE: A LARGE JUMP IN `outcome='failed'` ROWS IMMEDIATELY AFTER
DEPLOY IS A FINDING, NOT A SUCCESS.** It would not mean "B2 works" — it would
mean the wiring fires on a path that is not a vendor failure. Zero new rows is
the *expected* reading, and it is not evidence that B2 is broken; the behaviour
is proven by the gate, not by production traffic.

**Judgement rule:** every row in §3 unchanged, and any `api_usage_events`
growth accounted for row-by-row against §4. A difference that is not in this
declaration is THE FINDING, whatever its explanation sounds like afterwards.

---

## 6. ⚠️ A BASELINE THAT ALREADY CONTRADICTS THE DISCOVERY DOCUMENT

DISCOVERY §C.3 measured **44** failed-but-billed `ai_calls` rows on 2026-08-04.
Today it is **42**.

`ai_calls` rows are created by vendor calls and removed by exactly four
production deleters. Nothing else lowers the count — so the net −2 over five
days means **at least two calls' worth of billing evidence has been destroyed
by the normal operation of the product**, in the five days this programme spent
deciding what to do about it.

That is not a side note. It is §C.4's argument arriving as data:

- It **confirms the ruling** — `ai_calls` cannot be the billing source, because
  it demonstrably does not retain its rows.
- It **prices the backfill.** The 42 are the only record of those charges, they
  live exclusively in the perishable table, and the population is shrinking. A
  backfill is a production write needing its own ruling (ruling 59), but the
  window for it is **closing on its own**, and that should be stated when the
  ruling is sought rather than discovered later.

⚠️ **The exact figure to migrate is therefore whatever the count is AT
EXECUTION TIME, re-derived then — never 44, and never 42 copied from here.**
That is ruling 59's standing shape and this is precisely the case it is for.
