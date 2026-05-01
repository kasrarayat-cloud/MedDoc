// Phase 5 — Linear V1 Faithful app shell.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html
//
// Pure dark-canvas chrome. The shell is a single grid: 240px sidebar |
// content. The TopNav (48px sticky) lives at the top of the content
// column so its blurred bottom hairline rests directly above the page.
// IconRail (the sidebar) is sticky inside its grid cell.
//
// Server component — reads auth() once so every page can just render
// <AppFrame>...</AppFrame> without wiring user-name props. Client
// interactions (route detection, avatar dropdown) live in TopNav /
// IconRail, each marked 'use client' as needed.
//
// HISTORICAL §8.2 — the scroll container must be a *direct child* of
// the flex row so position: sticky inside `children` (right rails,
// jumplinks) resolves against it rather than silently failing against
// an overflow:hidden ancestor.
//
// `theme` and `shader` props remain in the type signature for backward
// compatibility with surface code that hasn't been migrated yet, but
// are intentionally ignored — Stage 5 cleanup will drop them in one
// sweep across all call sites. ShaderBG has been removed entirely
// (Linear V1 has no shader).

import type { ReactNode } from 'react';
import { auth } from '@/lib/nextauth';
import { TopNav } from './top-nav';
import { IconRail } from './icon-rail';

type AppFrameTheme = 'legacy' | 'clinician';

interface AppFrameProps {
  children: ReactNode;
  /** @deprecated kept for back-compat; Linear V1 has no shader. */
  shader?: boolean;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: AppFrameTheme;
}

export async function AppFrame({ children }: AppFrameProps) {
  const session = await auth();
  const userName = session?.user?.name || session?.user?.email || 'Doctor';
  const userEmail = session?.user?.email ?? undefined;

  return (
    <div className="qm-lin-app">
      <IconRail />
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          minWidth: 0,
        }}
      >
        <TopNav userName={userName} userEmail={userEmail} />
        {/* §8.2: this <main> is the direct overflow parent so any
            position: sticky inside `children` resolves here. */}
        <main
          style={{
            flex: 1,
            minWidth: 0,
            position: 'relative',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
