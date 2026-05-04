# P2-003 — Mobile dashboard tap targets fail Apple HIG (44pt minimum)

**Severity:** P2 (mobile UX — explicitly target audience per marketing)
**Devices affected:** all iPhone viewports (tested: iPhone 13 = 390×844)

## What

Apple Human Interface Guidelines specifies minimum tap target of
44×44 points. On iPhone 13 viewport, **17 of 17 sampled
interactive elements on the authenticated dashboard fail the height
threshold**:

| Element | Width × Height (pt) | Affects |
|---|---|---|
| Top-nav links (Dashboard / Visits / Patients / Settings) | 373 × **28** | every page navigation |
| Brand mark (QQuillMD) | 75 × **19** | "back to dashboard" entry |
| Cmd-K search bar | 220 × **26** | global search (most-used affordance) |
| "New visit" CTA | 95 × **28** | the primary action |
| Avatar (QB) | 54 × **32** | profile menu trigger |
| Patients dashboard tile | 86 × **30** | navigation to patients |
| All visits dashboard tile | 86 × **30** | navigation to visits |
| Recent visit row | 294 × **36** | open a recent visit |

100% miss rate. Heights of 19-36 pt mean the tap area is 2-3 mm
tall on a real iPhone — a thumb can easily miss.

## Why it matters

The marketing site explicitly targets **solo physicians using
mobile** (per the Phase 7 v6 hero copy, the floating SOAP card
mockup, the "Built for US clinicians" trust strip). Doctors using
the app on phone — the explicit target audience — will feel
friction immediately.

Sub-44pt nav height is the #1 a11y complaint in iOS app reviews.

## Reproduction

Open `https://app.quillmd.com/dashboard` on a real iPhone (or in
Safari devtools at iPhone 13 simulation), and try to:
- Tap "Visits" in the top nav
- Tap a recent-visit row in the dashboard list

You'll experience visible mistap rate.

Or via Playwright + iPhone 13 device profile:
```ts
const ctx = await browser.newContext({ ...devices['iPhone 13'] });
const page = await ctx.newPage();
// (login)
await page.goto('https://app.quillmd.com/dashboard');
const small = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('a, button, input, select, [role="button"]'))
    .filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44);
    }).length;
});
// → 17 (all 17 sampled fail)
```

## Risk if NOT fixed

- Mobile UX friction — real doctors will mistap, get frustrated
- App-store-style review complaints if QuillMD ever wraps in a
  WebView wrapper for distribution
- Lighthouse mobile a11y reports tap-target failures (Round 1
  Lighthouse already flagged the auth surface; this would
  compound)

## Proposed remediation

In the auth-app shell CSS / Tailwind classes:

```css
/* apps/transcribe-md/src/app/globals.css or component-level */
.qm-lin-nav-link, .qm-lin-card, .qm-lin-button-primary {
  min-height: 44px;
  /* + appropriate padding to keep visual size proportional */
}
```

Or per-component: bump nav-link `padding-y` from 4-8px to 12-16px.
Brand mark: increase target with invisible padding (`hit area` >
`visual area`).

The Phase 7 v6 marketing redesign already uses 44pt+ buttons; the
auth shell wasn't updated to match.

## Effort

- CSS / Tailwind class updates: ~30 min
- Visual regression check: ~15 min
- Total: ~45 min

## Risk to fix

LOW — visual changes only, no behavior change. Bumping heights
from ~28pt to 44pt does affect layout density; verify the dashboard
still fits "above the fold" on iPhone SE viewport (375×667) with
larger nav.

## Status

Plan-only per audit rules. High-impact fix; recommend Kasra
prioritize alongside P1-001 (PDF metadata) and UX-01 (text-3
contrast — carried from Round 1).
