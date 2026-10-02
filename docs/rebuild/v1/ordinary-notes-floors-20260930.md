# Ordinary notes — usefulness attempt, safety floors, and what remains (2026-09-30)

Offline only: retained provider responses, reference answers built from the independent freeze
(`freeze-76`: 46 SHOULD_FILL of which 38 expressible, 16 MISSING, 10 HUMAN, 4 CONTRADICTION), synthetic batteries. No
paid request was made; attempts 17 and 20 and the failed stage verdict are unchanged.

## What was tried and why it was not integrated

`fix/v1-notes-relations` (pushed, head `0bb9fc46`) made the field-relations v2 contract the Sonnet 5 notes contract
and fixed the traced first faulty decisions by RELEASING holds: a pronoun, thing or implicit subject counted as the
patient; the form title is not a qualifier; option polarity from a pronoun; the 'A 45-year-old man presents…' opener;
N02's time clause; attempt 18's attendance line. With correct model relations it filled **32 of 38** (23 before).
Three refutation rounds each confirmed HIGH unsafe adoptions against 43fcf214 — the wrong person (a companion named
without an article, a telegraphic 'cares for disabled veteran', an initialism role), another encounter or time ('On
admission she is on warfarin', 'From 03/2015 to 03/2019…'), the other side, and a 17× page cost. Each repair added
readers and the next round broke them: the same structural-reading trap recorded for mapping. The releases were
dropped.

## What was integrated (`fix/v1-notes-floors` 0e842b0c, merged in `df908301`)

- **Hold-only floors on the field-relations path** that a model calling a line 'independent' cannot remove: another
  person/actor, bounded clause, dated past (and the now-question), plan/intention, a line that points back or a bare
  cessation, an opposed statement on the same topic (including a denial of a labelled value), another person's same
  topic, a class denial. Proven hold-only against 43fcf214 on an 8,118-entry differential battery built from every
  earlier refuter's inputs (0 releases, 0 default-path differences).
- **Question context in the default request** (prompt v7): each v3 field's printed parent question/section is sent,
  so three 'Other' fields are no longer indistinguishable (N02). A context matching the injection screen is not sent.
- **Contract selection unchanged**: the field-relations path is on only when `QUILLMD_V3_FIELD_RELATIONS=1`, and then
  only for claude-sonnet-5 (4.6 keeps the default request). Records written by either tree read the same on both.

## Measured (freeze / cases.json; nothing rescored)

| path | correct | incorrect | unjustifiably held | appropriately held | missing |
|---|---|---|---|---|---|
| default request, 14 retained responses (43fcf214 and integrated identical) | 7 / 7 | 0 / 0 | 31 / 29 | 15 / 17 | 23 / 23 |
| field-relations, reference relations from the freeze (both identical) | 23 / 23 | 0 / 0 | 15 / 13 | 17 / 19 | 21 / 21 |

| relations-path exposure, model calls every other line 'independent' | 43fcf214 | integrated |
|---|---|---|
| adverse rows adopted (57 originals) | 18 | **2** |
| adverse rows + line-break variants (369) | 204 | **26** |
| frozen replay leaks | 8 | **0** (caught 31 → 39) |
| frozen 'not supported' entries leaking | 8 | **0** |
| default path, all 369 | 0 | 0 |

Cost against 43fcf214: 0.97–1.16× on the refuters' long-note probes; one long shape where asserting and denying
predicates share heads is 2.2–2.4× (recorded LOW). N13's retained attempt 020 finalizes, exports and reads back;
the D30/D31 replays are identical in all 22 modes.

## Where usefulness stands, honestly

The default path still fills **7 of 38** answerable fields. The path that is useful — field relations, **23 of 38**
with a correct model and now with 2 model-only adverse rows instead of 18 — stays off. Three things stand between it
and use, none of them a wording rule:

1. **Live qualification**: the campaign's notes stage has no declared send left (failed-3). The smallest batch that
   answers the question is the **14 retained default cases re-sent once on the field-relations contract** (measured
   relations sends cost $0.0048–$0.0056 each, so about $0.08 actual; the plan prints the worst-case bound). It needs
   a new allowance from the owner; it is prepared, not sent.
2. **A production switch**: the production environment renderer refuses the `QUILLMD_V3_FIELD_RELATIONS` name today,
   so production cannot enable it; that is an operations change to make with the qualification, not before.
3. **Large forms**: the relations contract's 20,000-byte response bound sends a D30-sized note of 13+ units to the
   batch path, which is off; those forms are refused rather than degraded.

Consent baseline unchanged: a model cannot attest, sign or change identity; a factual 'Consent obtained' answers only
from an explicit statement and still needs review.

Evidence: `rebuild/.runtime/v1-product-20260930/b/notes/` (the released attempt, three rounds) and `b2/notes/` (the
integrated floors, refutation, repair, final verification).
