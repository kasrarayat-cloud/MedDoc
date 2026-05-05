---
id: A10-P3-005
severity: P3
domain: a11y — async status announcements
title: Limited aria-live coverage on async UI; processing pipeline status changes not announced to screen readers
---

## Issue

The visit detail's `<ProcessingState>` component renders a 7-step pipeline (Transcribe → Understand → SOAP draft → Review → Polish → Codes + Rx → Ready) and updates the active step every 2 s via polling. Visually this is a sage halo + animated step ladder. **Screen-reader users get exactly one announcement** when they land on the page (the centre `role="status"` block) and **no further announcements** when steps advance.

This means a blind doctor who navigated to a freshly-uploaded visit hears "Drafting" once, then complete silence for 60-180 seconds while the pipeline runs, with no way to know progress without re-loading the page.

Other places where `aria-live` should be set but isn't:

- `apps/transcribe-md/src/app/visits/[id]/processing-state.tsx:490` has `role="status"` on the headline crossfade — but the value updates inside it without an explicit `aria-live="polite"` (role status implies polite, but the [transition behaviour requires `aria-atomic="true"` to re-announce the whole region](https://www.w3.org/TR/wai-aria-1.1/#aria-atomic), which is missing).
- `apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx:882` — same `role="status"` pattern without atomic.
- The autosave / unsaved-edit indicator in `soap-editor.tsx` updates `Saving…` → `Saved 2s ago` silently; no live region.
- The toast container has Sonner's default live-region (good — already announces) but with the 4 s timeout (see A10-P2-001) the announcement is short.

## Evidence

`apps/transcribe-md/src/app/visits/[id]/processing-state.tsx:485-510` (approximate):

```tsx
<div role="status" className="...">
  <span className="qm-lin-process-headline">{HEADLINE_FOR[status]}</span>
  <span className="qm-lin-process-hint">{progressHint}</span>
</div>
```

`role="status"` implies `aria-live="polite"` and `aria-atomic="false"` per WAI-ARIA. Without `aria-atomic="true"`, when the headline crossfades from "Listening" to "Drafting", VoiceOver may announce only the diff (or nothing, depending on the DOM update strategy). React's reconciliation often replaces the text node entirely on innerHTML change, which screen readers don't always pick up.

`apps/transcribe-md/src/components/visits/CodingRail.tsx:287` does this right — `aria-live="polite"` explicit:
```tsx
<span className="qm-lin-coding-code" aria-live="polite">
```

## Risk

- WCAG 4.1.3 (Status Messages) Level AA — borderline. The presence of `role="status"` may or may not be sufficient depending on the browser/AT combo. Adding `aria-atomic="true"` makes the conformance unambiguous.
- Blind / low-vision doctors lose all sense of pipeline progress, which is a 60-180 s wait per visit. They may assume the system is broken.

## Recommended fix

1. In `apps/transcribe-md/src/app/visits/[id]/processing-state.tsx:490`, change to:
   ```tsx
   <div role="status" aria-live="polite" aria-atomic="true" className="...">
   ```

2. Same update in `visit-ready-view.tsx:882` and `recording-client.tsx:421`.

3. For the autosave indicator in `soap-editor.tsx`, add an off-screen `<span aria-live="polite" className="sr-only">{saveState === 'saved' ? 'Draft saved' : ''}</span>` that updates after a successful save. Don't announce on every keystroke (would be noisy) — only on the save-debounce flush.

4. For the dashboard's "N awaiting review" subtitle, it currently re-renders on data refresh — wrap in `<span aria-live="polite" aria-atomic="true">` so an SR user gets a re-announcement when the count changes.

Effort: ~5 attribute additions across 3 files. Low risk, real improvement.
