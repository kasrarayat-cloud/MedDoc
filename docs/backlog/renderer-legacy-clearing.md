# RENDERER SLICE — legacy form fields have no bounded container

**Filed 2026-09-02 (ruling #164 item 1). REWRITTEN the same day under ruling
#165, because #165 fixed one of the two defects and re-scoped the other.**

⚠️ **THE FIRST VERSION OF THIS FILE WAS MIS-SCOPED, AND AN ADVERSARIAL LENS
CAUGHT IT.** It filed both defects as *legacy* problems and set a Definition of
Done of *"`legacy_form_field` joins `PROVEN_EMPTIABLE_BINDINGS`"* — while its own
Defect 2 said, verbatim, *"Not legacy-specific — the same glyph survives in a
plain `w:text` content control."* Completing the item as written would not have
touched the `content_control` exposure, which was the one that was live.

## Defect 2 — non-`w:t` content survives a cleared region — **FIXED for SDTs**

`textContainerPatches` clears only `w:t` descendants, so `w:sym`, `w:pict`,
`w:drawing`, `w:object`, `w:delText` and `w:instrText` all survived a null
render. This was **never legacy-specific**; it applied to every binding that
cleared by walking for text nodes.

**#165 rule 1 fixes it for content controls** by replacing the whole
`w:sdtContent` subtree — the boundary is the document's own element, so there is
no carrier list to be incomplete. Proved in
`gate-165-bounded-clearing.test.ts`, one arm per carrier, each asserting the
carrier is present in the SOURCE and absent from the OUTPUT.

**Still open for `legacy_form_field`**, for the structural reason below.

## Defect 1 — a paragraph-spanning FORMTEXT result is not cleared — **OPEN**

`legacyResultTextNodes` scopes its walk to the `begin` fldChar's own `w:p`. Word
produces a result spanning two paragraphs the moment a paragraph mark is entered
inside a field result, and then `separate` and `end` are out of view: nothing is
cleared and the template's stale `w:default` survives.

**Reproduced**, two-paragraph FORMTEXT, null resolution:

    [ONE-PARA]  SOURCE true -> OUTPUT false   (cleared, correct)
    [SPANNING]  SOURCE true -> OUTPUT true    (SURVIVES)

both `verified: true`.

⚠️ **THE OBVIOUS REPAIR IS THE ONE THAT MUST NOT BE TAKEN.** Widening the walk to
the part root was tried under #163 and, on an unbalanced `w:fldChar`, ran past
the field and **ERASED unrelated clinical text** — a patient's allergy line —
with every guard green, where `main` correctly REFUSED that render.

## Why legacy cannot simply take #165's cure

**A legacy form field has no enclosing element.** Its result is a SPAN between a
`separate` fldChar and an `end` fldChar, both of which are siblings in a run
sequence. There is no `w:sdtContent` equivalent to replace — which is exactly
why every attempt to bound it by walking has been falsified, and why #165's
whole-subtree replacement has nothing to grip.

So the slice is not "port the SDT fix" (whichever of the four SDT mechanisms
this arc shipped is meant). It is: **give the legacy result a
principled extent model** that is correct for a spanning result AND cannot
over-reach on a malformed document. Those two must be solved together, since the
naive fix for one causes the other.

## Definition of done

1. A field-extent model meeting both constraints above.
2. The `it.todo` arms in `gate-165-bounded-clearing.test.ts` become real arms.
3. Only then does `legacy_form_field` join `PROVEN_EMPTIABLE_BINDINGS` — and the
   arm asserting a legacy proof is NOT `emptied` is what notices if it is added
   without the work.

## Population note

Production carries **zero** `legacy_form_field` bindings today (measured
2026-09-01: 150 field rows — 60 `content_control`/narrative, 52 `table_cell`,
28 `content_control`/`single_select`, 10 `content_control`/number). That is a
fact about the corpus, not the code: the path re-arms the first time a doctor
uploads a `.doc`-era form, with no code change.

## Sibling item

`table_cell` (52 rows) **does** have a bounded container — `w:tc` — and is the
next candidate for the same treatment. It is excluded today only because that
write does not exist yet, not because it cannot work.
