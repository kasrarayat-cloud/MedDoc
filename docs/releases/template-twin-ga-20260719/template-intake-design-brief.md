# Template Twin production intake design brief

Status: reference lock for implementation; not a release approval.

## Brief

Designing a DOCX intake and candidate-review workflow for authorized QuillMD physicians on the physician web application.

- Goal: let a physician identify a blank/fillable template or a completed example, understand exactly what QuillMD can and cannot convert, and approve every clinically meaningful field before activation.
- Tone: precise clinical instrument; calm because consequences are high, not decorative or aspirational.
- Main risk: suggesting that ordinary narrative or patient-like text is a fillable field, hiding unsupported structure, or making approval feel automatic.
- Must remember: an uploaded completed report is evidence for a new candidate, never the template itself.
- Constraints: preserve the current Linear V1 application tokens and information density, fail closed, work with keyboard and screen readers, retain immutable lineage, never expose raw source or provider payloads through client DTOs, and do not use real PHI in design or tests.
- Research needed: existing QuillMD upload, certification, static-asset review, and visit-review surfaces; bundled form/accessibility, operational-copy, and anti-generic design guidance.
- Path: direct build inside the established application design system; no new visual language or generated imagery.

## Research summary

Live Refero tools were unavailable, so the locked production references are the repository's existing screens plus the bundled Refero craft guidance.

Reviewed product sources:

1. `note-format-manager.tsx`: existing DOCX entry point, immutable-version language, modal semantics, and sage primary action.
2. `template-twin-certification-workspace.tsx` and its CSS module: two-column field rail/inspector, flat divider hierarchy, compact status badges, monospace evidence labels, explicit attention filters, and synthetic-test proof surface.
3. `static-asset-review-workspace.tsx`: authenticated exact-byte decisions and privacy-sensitive review language.
4. `template-twin-review.tsx`: clinical attention ordering, evidence visibility, completion acknowledgement, and blocking states.
5. Refero `craft-details.md`, `copywriting.md`, and `anti-ai-slop.md`: semantic controls, visible focus, inline actionable errors, async announcements, operational copy, and avoiding decorative cards or generic redesign motifs.

## Reference lock

- Primary direction: the current Template Twin certification workspace.
- Preserve: dark Linear V1 canvas; compact sans typography; monospace labels only for technical evidence; sage only for safe primary actions/confirmed states; amber/red only for review/block meaning; rail-and-inspector information architecture; flat sections separated by hairlines.
- Borrow only: the existing static-asset workspace's exact-byte attestation pattern and the visit-review surface's attention-first ordering.
- Role rules: sage never means model confidence; amber never decorates; red only blocks; a bordered container is used only when it is interactive or communicates a bounded state.
- Media strategy: no invented page image. Side-by-side comparison uses deterministic, de-identified structural regions and an exact generated-candidate representation, with stable dimensions and downloadable synthetic test artifacts.
- Reject: generic card grids, celebratory onboarding tone, indigo/violet additions, raw narrative previews containing patient-like values, hidden bulk approval, or a single action labeled merely “Continue.”
- Token commitment: reuse `--color-linear-*`, `--font-sans`, `--font-mono`, 6–8px control radii, existing hairline/border recipes, and existing focus-visible sage outline.

## Journey

1. Choose a clearly named intake mode: **Blank or Fillable Template** or **Completed Document Example**. The choice remains visible and reversible before upload.
2. Upload into quarantine. Show receipt, scanner, structure, privacy, and admission states separately; do not show a compiling success state before every required gate passes.
3. Blank mode enters the existing field-certification workspace only after clean admission.
4. Completed-example mode never enters standard certification directly. It shows a de-identified source structure beside a newly generated blank candidate structure.
5. Every candidate region appears in one inventory with evidence type, confidence class, uncertainty, support status, and an explicit physician decision. Bulk confirmation is available only for the currently visible eligible set, with a preview of every affected region and an undo action before save.
6. Approved candidate regions produce a new immutable blank DOCX version with stable bindings. The original completed document is never overwritten or activated.
7. The generated candidate then enters the normal certification and synthetic-test gates.

## Decision ledger

| Decision | Source | Rule / role | Why |
|---|---|---|---|
| Mode choice precedes upload | User boundary; operational-copy guidance | Name the object and consequence | Prevents treating a populated report as a blank template. |
| Quarantine gate shown as a stepwise receipt | Security requirements; existing admission summary | Status, not marketing | A physician can see which gate failed and the safe next action. |
| Rail lists candidate regions; inspector compares one region | Existing certification workspace | Preserve established split layout | Scales beyond a few fields without a card grid or hidden modal sequence. |
| Source pane is structurally de-identified | Privacy boundary | Never render patient-like values into the ordinary client DTO | Supports comparison without normalizing completed-report content as reusable template text. |
| Bulk action requires a visible eligible set and undo | User requirement; form craft | No hidden selection, specific action label | Makes every suggestion visible and reversible. |
| Activation remains outside conversion | Existing lifecycle; user boundary | Conversion creates a draft candidate only | Preserves physician certification, signing, rollout, and evidence gates. |
| Errors state what failed and how to fix it | Refero copy/form guidance | Context + cause + next action | Avoids vague “Something went wrong” handling in a high-stakes flow. |

## Accessibility and QA lock

- Use native buttons, links, labels, radios/checkboxes, headings, lists, and tables where their semantics fit.
- Keep dialog focus trapping and return focus; use `:focus-visible`; never remove outlines without replacement.
- Announce async admission and candidate-generation changes through a polite live region; blocking errors use `role="alert"` and focus the first failed item.
- Provide text equivalents for structure comparisons; color is never the only status signal.
- At narrow breakpoints, stack source above candidate while retaining the selected-region rail and approval controls.
- Test keyboard-only mode selection, upload, filters, every-region approval, bulk preview/undo, unsaved-change warning, error recovery, and screen-reader status names.
