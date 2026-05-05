---
id: A10-P1-004
severity: P1
domain: a11y / WCAG 2.1.1 (Keyboard)
title: Transcript-tab audio Play / Skip-back / Skip-forward buttons have tabIndex={-1} — unreachable by keyboard
---

## Issue

The transcript-tab right-rail "Transport" panel contains three audio-control buttons (Skip-back 10 s, Play, Skip-forward 10 s) used to scrub through the visit recording while reading the transcript. **All three** have explicit `tabIndex={-1}`, which removes them from the keyboard tab sequence entirely. There is no associated keyboard shortcut documented.

A keyboard-only doctor (or anyone using NVDA / JAWS / VoiceOver) cannot operate the audio playback during transcript review. They can read the transcript and click on turns (those are properly keyboard-accessible — `role="button"` + `tabIndex={0}` + Enter/Space handler) but cannot start, pause, or skip audio without a mouse.

This is a Level A WCAG 2.1.1 violation.

## Evidence

`apps/transcribe-md/src/app/visits/[id]/transcript-tab.tsx:325-348`:

```tsx
<button
  type="button"
  className="grid h-7 w-7 place-items-center rounded-md border border-transparent text-linear-text-3 transition-colors hover:border-linear-border hover:text-linear-text"
  aria-label="Skip back 10 seconds"
  tabIndex={-1}                    {/* ← Cannot tab here */}
>
  <RotateCcw className="h-3 w-3" />
</button>
<button
  type="button"
  className="grid h-8 w-8 place-items-center rounded-full bg-linear-sage text-[#0d1611]"
  aria-label="Play"
  tabIndex={-1}                    {/* ← Cannot tab here */}
>
  <Play className="h-3 w-3 fill-current" />
</button>
<button
  type="button"
  ...
  aria-label="Skip forward 10 seconds"
  tabIndex={-1}                    {/* ← Cannot tab here */}
>
  <RotateCw className="h-3 w-3" />
</button>
```

The aria-labels are correct (good — A10-positive) but the keyboard pathway is intentionally severed. The adjacent comment on line 322 — `<span className="qm-lin-rail-meta">use ▶ above</span>` — implies these are decorative duplicates of a primary set of audio controls. But the only "primary" audio controls in this view are these three buttons. The `▶ above` reference is to an HTML5 `<audio controls>` element that I could not find in the rendered tree.

It's possible these buttons are stubs awaiting wiring (no `onClick` handler is set in the snippet above). Either way:

- If they're intended to function: remove `tabIndex={-1}` and wire `onClick`. WCAG fix.
- If they're decorative-only: replace `<button>` with `<div aria-hidden>` + remove the `aria-label` so AT doesn't announce them. Otherwise screen readers announce three "buttons" the user cannot reach.

## Risk

- WCAG 2.1.1 Level A — keyboard accessibility failure on a clinician-facing surface.
- Procurement audit fail.
- A blind doctor reviewing a transcript with screen-reader audio playback cannot scrub. This is a meaningful exclusion.

## Recommended fix

Inspect intent. If functional:

```tsx
<button
  type="button"
  ...
  aria-label="Skip back 10 seconds"
  onClick={skipBack10}
>
```

If decorative (audio is controlled via a different element):

```tsx
<div aria-hidden className="...">
  <RotateCcw className="h-3 w-3" />
</div>
```

Plus expose proper keyboard shortcuts ("J" / "K" / "L" YouTube-style or Space-to-play) — the existing `useShortcut` infrastructure in `apps/transcribe-md/src/lib/shortcuts.ts` makes this trivial.
