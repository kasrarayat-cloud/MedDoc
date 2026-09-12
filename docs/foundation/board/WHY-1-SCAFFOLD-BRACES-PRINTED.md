# WHY-1 — why the `{patient}`/`{age}` scaffold printed on the owner's first real visit

**Filed separately at the owner's instruction, as the prerequisite to TOKEN-1.**
Forensic run 2026-09-11 by a four-lens read of the fill/render path at `main`
`1bc62c08`, cross-checked against the source by the lead.

## Verdict — the panel INSERTED it (hypothesis A). It was not an unfilled render (hypothesis B).

The literal braces reached the document because the **"Your blanks" panel's
*Insert my default* action wrote the control's scaffold text — braces and all —
as a `scaffold_default` override, and the renderer emitted that stored value
verbatim.** An *unfilled* scaffolded control does **not** print its scaffold;
the renderer clears it.

## The path that printed the braces (A), traced

1. The panel offers the four HPI-intro controls (displayOrder 6–9 of `d2120cdd`,
   each labelled `{patient} is a pleasant {age}-year-old presenting for
   gastro...`). The offer list is built in
   `src/actions/preview-visit-document.ts:433-448` (`insertableDefaults`), gated
   by `scaffoldDefaultOfferable` (`clinician-override.ts:232-321`). All four are
   blank, concept-bearing `narrative_text` scaffolds, so all four are offered,
   each showing the raw `{patient}...` string.
2. A click (or *Insert all*) calls `insertScaffoldDefaultAction`
   (`set-template-control.ts:801`). It reads the value **server-side from the
   compiled IR** — `text = (field.scaffoldText ?? '').trim()` (`:821`) — and
   upserts an override row `overrideKind:'scaffold_default', insertedText: text`
   (`:945`). The client never supplies the text; it is the brace string verbatim.
3. On the next fill, `applyClinicianOverrides` takes the `scaffold_default` arm
   (`clinician-override.ts:547-608`): it mints a `clinician_correction` fact
   (`buildScaffoldDefaultFact`, `:399-441`) whose value is that string, and sets
   the resolution `status:'supported', value: insertedText,
   reasonCode:'clinician_scaffold_default'` (`:590-605`).
4. The renderer sees a **non-null** value and writes it verbatim:
   `displayValue`'s `narrative_text` case returns `safeDisplayText(value)` with
   **no token/brace handling** (`renderer.ts:1522-1527`). `{patient}`/`{age}`
   print exactly as stored.

## Why it is NOT the unfilled render (B), stated because the intuition is wrong

An unfilled scaffolded content control resolves `not_mentioned` / `value:null`
(ruling #194 deleted the machine `keep`/`default_kept` branch). The renderer
then CLEARS it: `contentControlPatches` → `sdtBoundedClearPatches`
(`renderer.ts:1146-1200`) walks `w:sdtContent` and emits the scaffold's `w:t`
runs as **deletion** patches, so the braces are removed. The only null-narrative
outcome that keeps source bytes is a **zero-patch `blank`**, reached only when
the clear produces no patches — a scaffold with visible brace text does not
qualify. So an un-inserted scaffold prints **nothing**, never its braces.

## The decisive tell in the owner's real-visit manifest

For the four controls: `manifest.fields[fieldId].reasonCode ===
'clinician_scaffold_default'` with `status:'supported'`, and a round-trip proof
`kind:'clinician_default'` (NOT `blank`); plus `TemplateTwinFieldOverride` rows
`overrideKind='scaffold_default'` with `insertedText` set, and
`DEFAULT_INSERTED_BY_DOCTOR` audit rows on `surface:'review_defaults_panel'`. If
instead those fields carried `reasonCode:'fact_not_mentioned'`, `value:null`,
proof `blank`, and no override rows, that would be B — but in that state the
renderer clears the control and the braces could not have printed. (The one B
variant not excluded is HPI text that is NOT an `ir.field` at all — static body
prose — but gate-216 compiles this exact line as a scaffolded `narrative_text`
content control, and the panel offers it, so it is a field.)

## Consequence for the fix

The braces enter through the **inserted value**, so:
- **TOKEN-1** substitutes the registered tokens at fill time, on the
  `insertedText` as it becomes the resolution value (never in the renderer, so
  the manifest records the substituted value and the round-trip verifier still
  matches). An unresolvable token declines the insert (the field renders blank)
  with a named reason.
- **PANEL-1** stops offering a control whose scaffold is furniture, and drops
  controls whose scaffold is a token TOKEN-1 fills — so the raw-brace insert can
  no longer be chosen in the first place.

The two rulings meet here: TOKEN-1 makes the inserted value safe; PANEL-1 stops
the unsafe offer.
