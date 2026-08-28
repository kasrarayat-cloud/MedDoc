# THE NOTE-CONTENT BASELINE — captured so the next byte-identity row is falsifiable

**Canon 69 applied to its own landing.** That entry says a content claim needs a
content baseline, and that the `eec8685b` judgement had to downgrade its
byte-identity row to structural incapability for want of one. This file is the
missing measurement, taken while it is still true.

## THE BASELINE — production, 2026-08-27T20:2xZ, after the `eec8685b` deploy

| quantity | value |
|---|---|
| `md5(string_agg("soapFinal", '' ORDER BY id))` | **`a1d1aaea47d1dc22badcbcae165a0223`** |
| over | **49** notes |

**The query, so the next author runs the identical one:**

```sql
SELECT md5(string_agg("soapFinal", '' ORDER BY id))
FROM transcribe_visits WHERE "soapFinal" IS NOT NULL;
```

⚠️ **POSITIVE CONTROL, RUN AT CAPTURE TIME, so the hash is known to be capable of
moving.** The same aggregate over `"soapFinal" || 'x'` gives
`5860d66998aa8bbcdb07bad964ce104e` — a different value. **The hash is sensitive
to CONTENT, not merely to row count**, which is the whole property a byte-identity
row depends on and the one a bare `count(*)` does not have.

## HOW TO USE IT, AND ITS HONEST LIMITS

**Use:** any future declaration carrying *"any stored note's text —
byte-identical"* names this hash as its BEFORE value and re-runs the query after
the act. Equal is the pass. Different is **the finding**, whatever the
explanation sounds like afterwards.

⚠️ **THE ROW COUNT IS PART OF THE CLAIM.** `string_agg` over a different
population produces a different hash for a reason that is not content — so a
comparison quotes **both** numbers, and a hash mismatch is diagnosed by checking
the count first.

⚠️ **AND IT GOES STALE THE MOMENT A DOCTOR EDITS A NOTE — BY DESIGN.** This is a
baseline for a DEPLOY WINDOW, not a standing invariant: capture it immediately
before the act, not from this file. What this file provides is the QUERY, the
CONTROL, and the proof that the measurement is cheap — the reasons the row was
skipped last time.
