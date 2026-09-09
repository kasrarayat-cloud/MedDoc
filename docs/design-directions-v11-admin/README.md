# v11 — the ADMIN shell, and the money view inside it

**Three directions, produced 2026-09-09 under ruling #310, from
`docs/foundation/board/ADMIN-DESIGN-BRIEF.md`.**

The owner picks **ONE**. The shell is then built into that direction and the
money view (ADMIN-4) goes inside it. **No ADMIN-4 screen is built on the old
dashboard** — that is the brief's one ordering constraint.

| direction | the idea | file | preview |
|---|---|---|---|
| **Control Room** | the console is read *continuously*, not visited — a telemetry ribbon, a status rail where every destination reports its own condition before you go there, and a seamed panel matrix | `control-room.html` | https://claude.ai/code/artifact/58efb45f-2ed7-4e25-a2f3-b4f6183bff5d |
| **Ledger** | money is a RECORD before it is a dashboard — `platform_rates` is insert-never-update, so the interface *is* the book and setting a rate is writing the next entry | `ledger.html` | https://claude.ai/code/artifact/10238003-fec6-44bc-97e9-1a041a4e3bdc |
| **Instrument Panel** | few readouts, read precisely — the margin is a calibrated control with visible hard stops whose positions are integer pairs | `instrument-panel.html` | https://claude.ai/code/artifact/1a33d185-8bfc-4973-a827-e6c62d3d20ef |

Each was produced in a **separate sub-session** that never saw the other two,
with a **BAN list** that forbids the other directions' signature moves plus a
universal ban on the generic-admin-dashboard skeleton (four KPI cards, gradient
hero, shadcn sidebar+card grid, emoji, donuts, decorative sparklines, lorem).
Three variations of one idea would have been a failure of the exercise.

Every file is self-contained: inline `<style>`, inline SVG, **no network
fetches**, and it paints its own background. Verified mechanically, not on the
author's word — 0 wrapper tags, 0 external hosts, 0 emoji, 0 lorem across all
three; `radial-gradient` and `border-radius:50%` are 0 in Control Room and
Ledger (both banned them) and non-zero only in Instrument Panel, which is the
one direction they belong to.

## ⚠️ THE PREVIEW PATH — A DECISION TAKEN ON THE OWNER'S BEHALF

Ruling #310 says *"published to the `_preview` path"*. **That path is closed,
and it was closed as a security remediation.** The 2026-07-24 full-app audit
recorded `app.quillmd.com/_preview/` as *"a live, unauthenticated public
directory listing on the production clinical host — 138 screenshots of every
authenticated screen including all six SUPER_ADMIN dashboards"* (item LEAD-7),
and `LAUNCH_READINESS.md` item 11 records it re-checked and closed.

Measured again 2026-09-09: `https://app.quillmd.com/_preview/` → **308 → 404**,
no Caddy handler, no compose mount — only a stale comment in
`docker-compose.yml` describing a bind that is no longer there.

**Re-opening it would republish exactly what an audit closed, and these are
admin and money screens — precisely the reconnaissance surface the finding
named.** Under #310(b) — *capability trades: fail closed, never strand, never
withhold* — the directions are published as **private Claude artifacts**
instead. The owner gets all three on a URL, from any device, immediately; the
production clinical host gains no new public surface.

**If the owner wants them on `_preview` specifically, that is his call to
re-open a closed finding, and it should be taken knowingly rather than
inherited from a ruling written before anyone re-measured the path.**

## What each direction had to solve, and what to judge it on

- **The exact ratio.** Margin is `numerator / denominator`, never a decimal
  input — `1.5` is representable in binary64 but `cost * 1.5` loses precision
  above 2^53 µ$. Display `1.50×`; store `3 / 2`. Each direction solves the
  *input* problem differently; that difference is worth judging.
- **NO RATE CONFIGURED.** Not an error, not an empty list — **a refusal with a
  cause**, and the state the platform is in right now. It is the first screen a
  real operator sees, so it is a first-class designed state in all three.
- **The wallet is two buckets.** Promo separate from paid, never one number
  with a footnote.
- **"The rate that applied" is a stamped row id, not a recomputation.** A money
  view that re-multiplies is a second implementation of the rate and will
  disagree with the ledger the day somebody changes it.

## Tokens

Production Rounds tokens were given to each session exactly
(`apps/transcribe-md/src/app/rounds-tokens.css`, 46 values), **breakable for
exploration**. Every break is declared in that file's own designer's note — read
those before deciding, because a break carried into the product is a decision,
not a detail. All three are deliberately single-theme: they render the product's
dark stage, which is what they are mockups *of*.
