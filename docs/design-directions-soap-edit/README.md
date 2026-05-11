# SOAP edit — ten interaction directions (v1)

Branch: `design/soap-edit-patterns-v1`

Static HTML mockups exploring how the SOAP edit affordance could
change. View `index.html` in a browser — it renders as a dark Linear-
flavored design page with the diagnostic at the top and ten patterns
below, three frames per pattern.

## Diagnostic — why the current click-to-edit feels "very hard"

The current flow (`apps/transcribe-md/src/app/visits/[id]/soap/SoapInlineEdit.tsx`):

- Each SOAP section body is a `<button>` wrapping the rendered
  markdown. Hover lights a subtle background and reveals a "Click to
  edit" pencil hint. Click swaps the body for a single `<textarea>`
  with a sage outline. `Esc` or blur saves via `saveSoapDraftAction`
  against the visit's `soapVersion` optimistic lock.

Three things the implementation makes hard:

1. **Section ≠ scope.** The textarea contains the entire SOAP
   markdown blob, not just the section the user clicked
   (`SoapInlineEdit.tsx:13-17`). Clicking "Plan" puts ~300 lines of
   S/O/A/P in front of someone who wanted to fix one sentence.
2. **Blur silently saves.** Clicking anywhere outside the textarea —
   coding rail, Rx warnings, whitespace — fires
   `onBlur → persist(draft)`. No explicit Save / Cancel chrome;
   accidental commits are one stray click away.
3. **Esc saves, not cancels.** `onKeyDown` for `Escape` calls the
   same `persist(draft)` as blur. The control that every other app
   uses for "throw away" here means "commit and exit." There is no
   revert path.

## The ten patterns

| # | Pattern | One-line | Win | Cost |
| - | ------- | -------- | --- | ---- |
| 1 | Per-section inline | Click edits only that section; siblings stay rendered | Scope matches what user clicked | Per-section serializer needed |
| 2 | Hover mini-toolbar | Edit · Regenerate · Copy as floating chip on hover | Regenerate in reach | Tablet touch ergonomics wobbly |
| 3 | Edit pill toggle | Always-visible "Edit" pill in section header | Always discoverable | Header chrome on every section |
| 4 | Always-editable | `contenteditable` body, autosave dot, no edit state | Zero ceremony | Accidental edits more likely |
| 5 | Modal editor | Centered modal + Bold/Italic/H3 + explicit Save | Big edit area, formatting | Hides coding rail context |
| 6 | Side-panel editor | Panel slides in from right; original section dimmed | Keep read context | Hides coding rail |
| 7 | Click select · dbl-click edit | Word/Docs gesture; single-click highlights for copy | No accidental edits | Discoverability of double-click |
| 8 | SOAP-wide View/Edit | One toggle flips all 4 sections editable | Whole-note refactor flow | Loses focused-edit model |
| 9 | Sticky action bar | Same click-to-edit, but Save/Cancel/Discard bar at bottom | Explicit controls always visible | Viewport chrome cost |
| 10 | Voice-first | Per-section mic; dictation becomes tentative; type as fallback | Medical-native modality | Mic permission · ambient noise |

## Notes on the seed list

- **Seed #1** (click-to-edit with hover pencil) was a near-refinement
  of the status quo — keeping the worst friction point (whole-blob
  scope) untouched. Swapped for **per-section inline edit**, which
  directly addresses friction #1 above.
- All other seeds kept; #4 was strengthened with an explicit autosave
  indicator and an undo window so the loss of save/cancel ceremony
  has a safety net.

## Production tokens — what the mockups assume

The HTML inlines a mirror of `apps/transcribe-md/src/app/globals.css`
tokens. Notably:

- Canvas `#08090a`, surface-1 `#0d0e10`, surface-2 `#131416`.
- Sage `#7AA68C` (base) · `#9BC4A8` (bright) · `rgba(122,166,140,0.13)` tint.
- Inter (sans), JetBrains Mono (mono · for eyebrows, labels, kbd).
- SOAP section structure mirrors `.qm-lin-soap-section` /
  `.qm-lin-soap-eyebrow` / `.qm-lin-soap-letter` / `.qm-lin-soap-body`
  (the four-block left-pane layout from the v6 mockups).
- Inline edit textarea mirrors `.qm-lin-soap-inline-edit-ta`
  (sage border `rgba(122, 166, 140, 0.42)`, focus glow 3px sage 0.20).

If the design picks a winner, the only token addition needed is for
the optional toolbar / action-bar / panel surfaces — and those reuse
existing `surface-2` / `border-strong` / `sage-edge` values.

## Next step

Designer picks 1-2 to prototype against live `SoapInlineEdit.tsx`.
Patterns 1, 3, and 9 are likely the highest-leverage pairings — each
fixes a different one of the three friction points and they don't
conflict with each other.
