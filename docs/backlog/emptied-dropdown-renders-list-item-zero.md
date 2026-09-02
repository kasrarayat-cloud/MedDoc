# EXPORT DEFECT — an emptied dropdown renders its first list item

**Filed 2026-09-02, ruling #168(b). Measured by an adversarial lens on the real
customer template, and INDEPENDENT of certification.**

## The defect

A content control backed by `w:dropDownList` whose content is empty does not
render as empty. The PDF engine falls back to the control's **first list item**,
so the doctor's exported document prints a value nobody chose.

On `WM IOV Template.docx` the affected control is `<w:alias w:val="Address"/>` —
the clinic-address dropdown, **the first text item on page 1** of the rendered
report — and what prints is `"Choose an item."`

Proven by mutating only that control's `w:listItem[0]` and re-converting:

    base-null:    item[0]="Choose an item."   x=261
    v3-null:      item[0]="Choose an item."   x=261
    v3-null-li:   item[0]="ZQXLISTZQX"        x=269.65   <- the probe printed

The x-shift is that control's own `w:jc="center"` centring a different string —
independent confirmation that the printed glyphs come from the list definition
and not from anywhere else.

⚠️ **THE ALTERNATIVE MECHANISM WAS REFUTED, WHICH IS WHY THE ATTRIBUTION HOLDS.**
Injecting a probe string into the glossary `w:docPart` body did **not** print, in
any variant. The engine does not materialise the docPart; it materialises
`listItem[0]`.

## ⚠️ THIS IS NOT A REGRESSION, AND THAT IS THE REASON TO FILE IT SEPARATELY

**Base prints it too.** Every render of this template, before and after every
ruling in this arc, has put "Choose an item." on page 1. Nothing here made a
document worse.

What ruling #165 briefly did was let that field buy the certification blank
requirement — turning a true statement about the document into a **false
attestation** about it. #168(b) closes that half by excluding selection kinds
from the count. **The printing itself is untouched and is this item.**

Separating them matters: a fix that only silenced the certificate would leave the
doctor's exported report exactly as wrong as it is today, while removing the
signal that it is wrong.

## Definition of done

An emptied selection control must render as EMPTY in the product's own PDF path.
Candidate approaches, in the order they should be tried:

1. **Remove the list definition when the control resolves null** — correct
    output, but it edits the doctor's template semantics inside a fill, which
    this programme has repeatedly found to be the expensive kind of mistake.
2. **Replace the control with its cleared content at export time**, so no
    `sdtPr` list survives to fall back to.
3. **Establish the behaviour is engine-specific** — Word may not do this — and
    if so, scope the fix to the export path rather than the stored document.

**(3) is the cheapest and must come first**, because the whole item rests on one
engine's behaviour and Word is untested.

## Scope

Every `single_select` / `multi_select` content control that resolves null. The
production corpus carries **28** of them, all on `WM IOV Template.docx`. The
owner's form `87223c49` (30 `narrative_text` + 5 `number`) contains none, so its
certification path is unaffected either way.
