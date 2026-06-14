# QuillMD — app-pattern concept screens (`/concepts/dashboard`, `/concepts/record`)

Staging-only design exploration. Extends the approved **C3 "calm, one-clear-action"** pattern
(`/concepts/soap/c3-final`) across the two other screens a doctor lives in daily, so the full
**land → record → review → sign** flow reads as ONE app before the real build. **Static mockups**
with synthetic no-PHI data — NOT wired to the real visit pipeline, server actions, auth, or data.
The live app, pipeline, production and co-tenants are untouched.

## The shared pattern (carried from C3)
Content primary · **exactly one clear primary action** · secondary stuff calm and on-demand ·
dark tokens (`#08090a`, sage `#7AA68C`, Inter + JetBrains Mono) · simple, uncluttered. Same tokens
and fonts as the C3 SOAP screen, so the four screens visibly belong to one family.

## Shared chrome fixes (the inventory's global problems)
- **ONE left nav** (`AppShell`) — wordmark, the single **"+ New visit"** primary, minimal
  Home / Patients / Settings links, and a **quiet** "Search ⌘K" (no double nav, no loud command bar).
- **A real mobile nav** — a bottom tab bar (Home · Patients · center **+** · Search · Settings)
  with a top bar carrying the wordmark + search. Not a desktop nav crammed onto a phone.
- **ONE unified status vocabulary** — the live app's ~7 scattered lifecycle words collapse to four
  plain states used identically everywhere: **Recording → Processing → Ready to sign → Signed**
  (old: queued / transcribing / drafting / draft / needs-review / completed / archived).

## Screen 1 — DASHBOARD (`/concepts/dashboard`)
A calm **"here's your work"** home. The single focus is the **notes-to-sign inbox** (drafts
**Ready to sign** — the doctor's real "do this next"); each row opens the C3 review. The clearest
primary is **"+ New visit."** The old 4 vanity stat cards are demoted to one quiet line
("6 visits today · 3 signed"). There are **no duplicate patients/visits tabs**. A quieter
"In progress" list below shows in-flight visits (Recording / Processing). One glance answers
"what do I do next." (Refs: Rise/Fernand one-focus inbox, Linear quiet dark list.)

## Screen 2 — CREATE / RECORD (`/concepts/record`)
**"Just start."** One obvious path — a sensible **walk-in default** (no three co-equal capture
tiles, no choice-overload) and one **"Start recording"** primary. The recording screen is **honest**:
a live audio-level waveform + a big timer + the explicit line *"there's no live transcript to
watch"* — **no fake transcript pretending to work.** Clear **Start / Stop / Pause**. Stopping opens
a **confirm gate** before the irreversible process step ("Write the note?" → Process / Resume /
Discard). Processing shows honest steps (Uploaded → Transcribing → Drafting → Safety & coding) and
then **"Review the draft →"** into the C3 review. (Refs: [untitled].stream dark recording with
waveform + timer, Suno trim; Intercom confirm-before-go-live.)

## The flow (feelable)
`/concepts/dashboard` → **+ New visit** → `/concepts/record` → record → **Process** → processing →
**Review the draft →** `/concepts/soap/c3-final` (the C3 screen). Dashboard inbox rows also deep-link
straight to the C3 review.

## Build / isolation
Purely additive — `app/concepts/(app)/{layout,app.css,dashboard,record}` + `components/concepts/app/*`
(`AppShell`, `StatusPill`, `DashboardScreen`, `RecordScreen`, `data`). The `(app)` route group keeps
the URLs clean and does not affect the sibling `/concepts/soap` routes. No existing tracked file
modified; the real app (`apps/transcribe-md`) is git-clean.

## Floor
Real selectable text; visible focus (`.ax-root :focus-visible`); `prefers-reduced-motion` gates the
waveform / recording pulse / processing spinner (content stays as static text); mobile/tablet
graceful (real bottom nav, recording card fits between the bars); 60fps. Route-scoped: Inter/JetBrains
+ app.css load only on these routes.

## Proposed order for the remaining screens (same pattern)
1. **Patient detail** — the next most-used; a calm patient header + a quiet visit timeline reusing
   the inbox row + status pill; one primary ("+ New visit for this patient").
2. **Settings** — collapse to a single calm left-rail of sections (the C3 calm-list treatment);
   "My note format" already lives here — fold it in.
3. **Auth (sign-in)** — a quiet single-card sign-in matching the dark family; lowest churn, do last.
