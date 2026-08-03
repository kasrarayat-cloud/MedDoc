// ============================================================================
// ROUNDS — the authenticated shell. One nav, no aside, every route.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS WHAT THE APP WAS MISSING AFTER THE FLIP, MEASURED ON PRODUCTION:
//
//   /board      qm-rounds                0 asides   Board · Templates · Settings
//   /patients   qm-c3 qm-lin             1 aside    Home · Patients · Settings
//   /dashboard  qm-c3 qm-lin             1 aside    (same legacy shell)
//   /settings   qm-c3 qm-lin qm-rounds   1 aside    (a Rounds host INSIDE it)
//
// The board grew its own chrome because it was the first Rounds screen.
// `AppFrame` — which wraps every OTHER authenticated route, including the
// Rounds visit stage — forked only on `isSkinBeta()`, so the skin's own stage
// rendered inside C3 chrome and the brand mark went somewhere different
// depending on which half of the app you were standing in.
//
// It lives in `components/rounds/` rather than in `components/ui/` beside
// `AppFrame` because `gate-controls-contract` draws its control/native
// boundary on the directory: Rounds' own screens live here, and everything
// applying a `qm-rounds-*` class OUTSIDE here has to be documented as a shared
// control primitive in SPEC.md's § Controls table. This is Rounds' own shell,
// so this is where it goes — `AppFrame` just picks the branch.
// ============================================================================

import type { ReactNode } from 'react';

import { RoundsTopBar } from './top-bar';

export function RoundsAppFrame({
  userName,
  children,
}: {
  userName: string;
  children: ReactNode;
}) {
  return (
    <div className="qm-rounds-app" data-testid="rounds-app-frame">
      <RoundsTopBar>
        <span className="qm-rounds-topbar-who">{userName}</span>
      </RoundsTopBar>
      {/* `id="main"` + `tabIndex={-1}` are carried over verbatim from the two
          branches below it in AppFrame: `id` is the skip-link target declared
          in layout.tsx, and a <main> does not take focus on a fragment hop
          unless it is programmatically focusable. Dropping either turns the
          skip link into a control that appears to work and moves nothing. */}
      <main id="main" tabIndex={-1} className="qm-rounds-app-main">
        {children}
      </main>
    </div>
  );
}
