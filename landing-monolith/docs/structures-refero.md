# QuillMD — 5 structurally-distinct landing concepts (`/structures`)

Staging-only design exploration. The variable here is **page ARCHITECTURE**, not style.
The previous concepts failed because they were one hero re-skinned (headline top-left, two
buttons, trust row). These five differ in their **bones** — where content sits, what the
user sees first, how the page is navigated. Each is **locked to a real Refero screen whose
STRUCTURE (not colour) it borrows**, pulled via `refero_search_screens` / verified via
`refero_get_screen_image`. Queries were generic UX/structure descriptors (PHI hygiene).

Same real QuillMD content rides each concept (selectable headline somewhere; SOAP sample
from `components/motion/shared.tsx`; a fully synthetic, no-PHI transcript for S1/S4).

---

## S1 — PRODUCT-FIRST
- **Structural lock:** ElevenLabs Studio editor — `refero.design/pages/3c08634c-8f25-4056-be64-5be134fb70aa`. Borrowed structure: **the app IS the page** — top app bar (file + export), a left vertical rail, a working canvas, and a **bottom transcript/waveform/playback bar**. No marketing hero.
- **Architecture:** full-viewport app frame. Top bar (wordmark + ● REC timer + Sign), left rail (Record/Transcript/Note/Codes/Sign), main canvas where the SOAP note writes itself line-by-line, bottom live-waveform + scrolling transcript line. Marketing copy + CTAs live BELOW the app frame.
- **Distinct because:** there is no headline hero at all — the user lands inside running software (rails, bars, a caret writing the note). None of the others is an app chrome.

## S2 — SPLIT-SCREEN
- **Structural lock:** Squarespace 50/50 split — `refero.design/pages/66d5906f-6dd5-4252-9877-34367bd635c3` (two equal vertical halves, solid colour one side / content the other). Secondary: Klarna `95cb7c0b`.
- **Architecture:** the viewport is divided by a hard vertical seam into two equal halves — LEFT (dark) "before": the hour of after-hours notes; RIGHT (light) "after": the note already written + signed. A before/after diptych, not a column.
- **Distinct because:** the composition is two halves meeting at a centre seam — there is no single content column; the eye is split left/right, not stacked.

## S3 — HORIZONTAL SCROLL
- **Structural lock:** NYT TimesMachine — `refero.design/pages/a201f6e9-c51f-4d24-8467-f9b72d418dd6` (a horizontal filmstrip of panels side-by-side across the screen, ◀▶ "page N of M").
- **Architecture:** a horizontal track of full-height chapter panels — Intro → Listen → Draft → Verify → Sign — the user scrolls SIDEWAYS (scroll-snap-x) through them; a "1 / 5" indicator + ◀▶. Mobile fallback: the track becomes a normal vertical stack.
- **Distinct because:** the navigation AXIS is horizontal. No other concept moves sideways; this one literally can't be turned into the others by recolouring — its layout engine is different.

## S4 — CONVERSATION-LED
- **Structural lock:** Grammarly doc editor — `refero.design/pages/caceccf5-d1b4-4bed-aae6-4f1ef3e15fb5` (primary text with highlighted spans + margin annotation/suggestion cards tied to the text).
- **Architecture:** the hero is a real doctor↔patient **transcript** (main column) with highlighted utterances; the SOAP note **assembles in the right margin**, each S/O/A/P line tagged to the exact quote it came from. The conversation is the hero; the note is the annotation.
- **Distinct because:** the first thing the user reads is a dialogue, not a pitch; the "hero" is a document-with-margin-notes layout. No headline-led concept reads like this.

## S5 — SINGLE STATEMENT
- **Structural lock:** mymind — `refero.design/pages/927bcaf7-b66e-4af3-8855-beb60f3b8358` (one large centred serif statement in near-empty space).
- **Architecture:** one full screen, a few words **dead-centre**, and **nothing else above the fold** — no buttons, no badges, no card. The subhead, proof (SOAP), CTAs and trust all live BELOW the fold (scroll to reveal).
- **Distinct because:** above the fold it is JUST the statement. This is the explicit anti-pattern of the old concepts (which crammed headline+sub+2 buttons+trust above the fold). Emptiness is the structure.

---

## Shared floor (all five)
Real selectable headline text somewhere in each; readable without JS (S1 is the SSR'd
default); `prefers-reduced-motion` → static, fully-visible frame; visible keyboard focus;
mobile graceful (S3 horizontal → vertical stack on mobile); 60fps (transform/opacity only).
A fixed 1–5 switcher. Route-scoped: loads only on `/structures`; the root landing, `/motion`
and `/heroes` stay byte-identical.
