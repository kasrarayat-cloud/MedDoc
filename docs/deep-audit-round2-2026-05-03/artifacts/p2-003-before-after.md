# P2-003 mobile tap-target before/after — iPhone 13 viewport

Both passes used the same harness (`p2-003-audit.js`) on the iPhone 13
device profile (390×844 CSS, DPR 3) against the deployed
`app.quillmd.com` shell as the qa-bypass owner account. Counts come
from per-route `_summary.json` in `p2-003-audit/` (before) and
`p2-003-after/` (after). "small" = visible interactive element with
measured height under 44px AND no tappable ancestor ≥44 either.

| Route                    | Total interactive | Pre-fix small | Post-fix small | Δ        |
|--------------------------|------------------:|--------------:|---------------:|---------:|
| `/dashboard`             | 20                |            20 |              0 |   −20    |
| `/visits`                | 21                |            21 |              0 |   −21    |
| `/visits/new` step-2     | 15                |            13 |              0 |   −13    |
| `/visits/[id]`           | 33                |            22 |              0 |   −22    |
| `/patients`              | 17                |            10 |              0 |   −10    |
| `/settings`              | 30                |            30 |              0 |   −30    |
| `/settings/security`*    | 2                 |             2 |              1 |    −1    |
| **Total**                | **138**           |       **118** |          **1** | **−117** |

\* `/settings/security` doesn't exist as a real route — both audits hit
the `not-found.tsx` page. The remaining sub-44 element is the "Sign in"
link inside that 404 chrome (h=18). Fixed in the same commit
(`apps/transcribe-md/src/app/not-found.tsx` adds the `qm-tap-44`
utility) but the audit was captured before this rebuild was deployed
to production. Post-deploy verification expected to read 0/2.

## Where the fix lives

The 117 wins came from these 8 changes:

| Surface                  | Diff                                                     | Wins             |
|--------------------------|----------------------------------------------------------|------------------|
| `globals.css` `.qm-lin-row`         | `@media (max-width: 639px) { min-height: 44px }`         | 17 row-level    |
| `globals.css` `.qm-lin-btn`         | same media-query floor                                   | 11 secondary btn |
| `globals.css` `.qm-lin-btn-primary` | same media-query floor                                   | 12 primary CTAs  |
| `globals.css` `.qm-lin-cmdk`        | same media-query floor (overrides hardcoded `height: 26px`) | 6 Cmd-K trigger  |
| `globals.css` new `.qm-tap-44` utility | `min-height: 44px` on mobile for inline-styled chrome  | covers 30+      |
| `globals.css` new `.qm-tap-44-input` | same plus `font-size: 16px` (kills iOS focus-zoom)     | covers 14 inputs |
| `globals.css` `.qm-lin-em-nudge` / `.qm-lin-coding-override` / `.qm-lin-coding-confirm` | mobile floor on the 3 Coding Coach controls | 3 |
| Component `className="qm-tap-44"` adds | IconRail RailRow, TopNav brand link + avatar, dashboard TabBar Links, settings sub-nav anchors, visit-detail breadcrumb Links + tabs | covers 30+ |

Per the constraint: zero typography weight changes, zero color changes,
zero desktop layout changes. The desktop chrome (≥640px) is unchanged
because every floor is gated on `@media (max-width: 639px)`.

## What's left (not blocking)

- `/settings/security` 1 element — the not-found "Sign in" link, fixed
  in `not-found.tsx` and pending the post-merge rebuild.
- `<select>` Radix Select shims (1-2px tall) are filtered from both the
  audit script and the e2e gate — not real tap targets.
- The Coding Coach `+ add 1 element` nudge buttons on `/visits/[id]`
  inflate to 44px on mobile (was 21px). This adds visible weight to
  the Coding Coach rail on phone width — acceptable trade per spec
  (HIG > visual density).

## How to keep this from regressing

`apps/transcribe-md/tests/e2e/mobile-tap-targets.spec.ts` runs the
same gate on iPhone 13 against every authenticated route and fails
the e2e suite if any route grows a sub-44 element with no tappable
ancestor. The gate uses an `ancestorTapHeight` helper (5-deep) so
list rows that wrap an inner anchor still pass when the outer row
has the floor. Skip-list is empty today; tag the rare exemption with
`data-tap-target-skip` rather than relaxing the floor.
