# A BYTE-IDENTITY ROW NEEDS A BEFORE-HASH

**Ratified 2026-08-27.** The declared-vs-measured discipline, turned on the
declaration itself.

> **A CONTENT claim needs a CONTENT baseline. If you did not capture one, the row
> downgrades — honestly, in writing — to structural incapability, SO LABELED.**

§2.5 exists because *"a post-deploy check written afterwards is unfalsifiable"*.
Every quantity in a declaration is therefore measured before the act, so the
comparison has one correct answer fixed before the evidence existed.

⚠️ **A ROW CAN SATISFY THAT RULE IN FORM AND FAIL IT IN SUBSTANCE.** The
declaration for `eec8685b` carried:

| quantity | required |
|---|---|
| **any stored note's text** | **byte-identical** |

Every other row had a number captured at `18:30:20Z`. **This one had a row
count.** `soapFinal=49` says how many notes exist; it says nothing whatsoever
about what any of them contains. A hash taken after the deploy proves nothing
without its predecessor, and there was no predecessor to compare it to.

**The row was written in good faith and was unverifiable the moment it was
written** — which is the same defect §2.5 prevents, arriving inside the
instrument that prevents it.

## THE TWO HONEST EXITS, AND BOTH ARE BETTER THAN A CONFIDENT TICK

**1 · CAPTURE THE BASELINE.** For a content claim that is one query:

    SELECT md5(string_agg("soapFinal", '' ORDER BY id)) FROM transcribe_visits
      WHERE "soapFinal" IS NOT NULL;

One value, before the act, and the row becomes as falsifiable as every other.

**2 · DOWNGRADE IT EXPLICITLY.** Where the baseline was missed, argue
**structural incapability** instead — and say that is what you are doing. Here:
the two migrations hold **five statements**, all `ALTER TABLE … ADD COLUMN IF NOT
EXISTS` (nullable) and `ALTER TYPE … ADD VALUE`; a scoped grep for
`UPDATE`/`DELETE`/`DROP COLUMN`/`TRUNCATE`/the column name returns **0**,
positive-controlled by an `ALTER` grep returning **7**. They *cannot* move note
text.

That argument is sound and it is **weaker than a measurement**: it reasons from
what the change is *able* to do, not from what the data *did*. It cannot see a
write performed by anything other than the migration — an application path, a
cron, a hand. **Which is exactly why the label matters more than the verdict.**

> **THE RULE IS NOT "NEVER SHIP A ROW YOU CANNOT MEASURE." It is "never let a
> structural argument wear a measurement's clothes."** A judgement that says
> *"18 of 18 matched"* with one row silently resting on inference is a true
> sentence doing misleading work — the same shape as *"I deployed `main`" is not
> "I judged what I deployed."*

**AND THE ASYMMETRY IS THE POINT:** the cost of capturing a before-hash is one
query. The cost of not having it is a permanent hole in the record of an
irreversible act. There is no version of that trade that favours skipping it.
