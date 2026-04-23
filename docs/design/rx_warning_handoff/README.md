# Rx Warning Card — Handoff Bundle

**Component:** `RxWarningCard`
**System:** QuillMD · dark theme · purple accent
**Delivered:** April 23, 2026

---

## What's in this bundle

```
rx_warning_handoff/
├── README.md                      ← you are here
├── DESIGN_SPEC.md                 ← full implementation spec
├── spec-page.html                 ← the interactive design doc (open in browser)
├── tokens.css                     ← root design tokens (reference)
├── screenshots/                   ← 6 hi-res section captures
│   ├── 01-section-1-before-after.png
│   ├── 02-section-2-anatomy.png
│   ├── 03-section-3-severity-scale.png
│   ├── 04-section-4-collapsed-expanded.png
│   ├── 05-section-5-in-context.png
│   └── 06-section-6-tokens.png
└── variants/                      ← individual card frames, isolated
    ├── 01-critical-expanded.png
    ├── 02-warning.png
    ├── 03-info.png
    ├── 04-collapsed.png
    ├── 05-expanded.png
    └── 06-in-context.png
```

---

## Where to start

1. **Skim the design** — open `spec-page.html` in a browser. Six chapters, each explaining one dimension of the card.
2. **Read the spec** — `DESIGN_SPEC.md`. Everything an engineer needs: tokens, anatomy, severity variants, states, a11y.
3. **Reference tokens** — `tokens.css`. The severity colors (`--coral`, `--amber`, `--accent-c`) drive all three variants via 4 CSS custom props remapped per modifier class.

---

## What the card does

Surfaces AI-confidence and clinical-rules warnings on Rx lines of an AI-drafted SOAP note. Three severities:

| Severity  | Use                                        | Blocks signing? |
|-----------|--------------------------------------------|-----------------|
| critical  | Cannot verify — physician must resolve     | **Yes**         |
| warning   | Concerning but not blocking — acknowledge  | No              |
| info      | FYI — compact, dismissible                 | No              |

The design's core move is **eye-path ordering**: badge → headline → **one red action sentence** → transcribed evidence → patient-specific risks → next step → collapsed rationale. A physician resolves ~95% of warnings without ever expanding the details.

---

## Key design decisions (quick reference)

- **One red sentence** — the action tile is the only place saturated severity color touches prose. Keeping the rest of the card neutral is what makes red mean something.
- **Two beats per risk** — `current med` (what the patient is on) → `outcome` (what goes wrong). Never write a paragraph when two pills will do.
- **Details collapsed by default** — the original paragraph is preserved inside "Show clinical reasoning" with transcript timestamp + rule version. Nothing is lost; everything is staged.
- **Info auto-compacts** — when `sev === 'info'`, regions 4–8 hide. Same skeleton, different density.
- **Critical has no dismiss** — overriding is a deliberate action (⇧O) that opens a confirmation modal and is audit-logged.

---

## Implementation notes

- Tokens live in `app/tokens.css` (included in bundle). The component adds no new root tokens — it reuses `--coral`, `--amber`, `--accent-c` and remaps them to 4 scoped props per severity modifier.
- All interactive states (hover, focus, active, disabled) defer to the app-wide `:focus-visible` rule for accessibility.
- Respect `prefers-reduced-motion: reduce` — disable the chevron rotation; swap glyph instead.
- Uses `role="alert"` + `aria-live="assertive"` for critical; `role="status"` + polite for warning; `role="note"` for info.

---

## Questions?

Things I'd be glad to spec further if helpful:

- **Confirmation modal** for override — flow + copy
- **Inline editing affordance** — how the "Edit medication" action opens and closes against the surrounding Rx slip
- **Dismiss state history** — if warnings should re-surface after N days
- **Mobile / tablet** — the card is laid out for desktop-first; tablet stacking rules not yet defined

Any of those, or tweaks to anything here — just let me know.
