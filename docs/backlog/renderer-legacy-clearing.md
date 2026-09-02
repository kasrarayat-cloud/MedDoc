# RENDERER SLICE — legacy form-field clearing has two measured defects

**Filed 2026-09-02 by ruling #164 item 1.** Both defects were REPRODUCED against
real documents during the #163 adversarial pass. #164 keeps `main`'s clearing
behaviour — it is the proven production path — and records these rather than
deleting the evidence for them.

⚠️ **This item is load-bearing for certification.** `blank-proof-count.ts` will
not count a `legacy_form_field` `emptied` proof toward the blank requirement
*because of these two defects*. When this slice lands, the single change there
is adding `legacy_form_field` to `PROVEN_EMPTIABLE_BINDINGS` — and the gate arm
*"a LEGACY `emptied` DOES NOT COUNT"* is what will notice if it is added without
the work.

## Defect 1 — a paragraph-spanning FORMTEXT result is not cleared

`legacyResultTextNodes` scopes its walk to the `begin` fldChar's own `w:p`. Word
produces a result spanning two paragraphs the moment a paragraph mark is entered
inside a field result, and then `separate` and `end` are out of view: the walk
returns empty, nothing is cleared, and the template's stale `w:default` survives.

**Reproduced**, two-paragraph FORMTEXT, null resolution:

    [ONE-PARA]  SOURCE true -> OUTPUT false   (cleared, correct)
    [SPANNING]  SOURCE true -> OUTPUT true    (SURVIVES)

both `verified: true`.

⚠️ **The obvious repair is the one that must not be taken.** Widening the walk to
the part root was tried under #163 and, on an unbalanced `w:fldChar`, ran past
the field and **ERASED unrelated clinical text** — a patient's allergy line —
with every guard green, where `main` correctly REFUSED that render. Any fix here
needs a principled field-extent model, not a wider scope.

## Defect 2 — non-`w:t` content in a cleared region survives

Clearing collects `w:t` nodes only. `w:sym`, `w:pict`, `w:object`, `w:drawing`
and `w:delText` all put marks on the page and carry no `w:t`.

**Reproduced**: a null-resolved control whose region holds
`<w:sym w:font="Wingdings" w:char="F0FE"/>` renders the tick, and a region
holding a `w:pict` keeps the image. ⚠️ **Not legacy-specific** — the same glyph
survives in a plain `w:text` content control.

## Definition of done

1. A field-extent model that is correct for a spanning result **and** cannot
   over-reach on a malformed document — the two must be solved together, since
   the naive fix for one causes the other.
2. Non-`w:t` visible content handled, or its survival documented as accepted
   with the reason.
3. The two `it.todo` arms in `gate-164-blank-union.test.ts` become real arms.
4. `legacy_form_field` joins `PROVEN_EMPTIABLE_BINDINGS`.

## Population note

Production carries **zero** `legacy_form_field` bindings today (measured
2026-09-01: 3 compiled versions, 150 field rows, 98 `content_control` +
52 `table_cell`). That is a fact about the corpus, not the code: the path re-arms
the first time a doctor uploads a `.doc`-era form, with no code change.
