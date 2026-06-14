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
import { isSkinBeta } from '@/config/skin-beta';
import { TopNav } from './top-nav';
import { IconRail } from './icon-rail';
import { SidebarC3 } from './sidebar-c3';
import { TopNavC3 } from './top-nav-c3';
import { MobileNavC3 } from './mobile-nav-c3';

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

  // ── C3 calm-skin chrome (Stage 1b, flag-gated) ──────────────────────────────
  // Reuses the SAME .qm-lin-app grid + content-column + <main> overflow parent as
  // the original (so the §8.2 sticky contract holds), with the C3 sidebar/top-bar
  // content + a real mobile bottom nav. Flag OFF → the original below, unchanged.
  if (isSkinBeta()) {
    return (
      <div className="qm-lin-app qm-c3-app">
        <SidebarC3 userName={userName} userEmail={userEmail} />
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', minWidth: 0 }}>
          <TopNavC3 />
          <main id="main" tabIndex={-1} style={{ flex: 1, minWidth: 0, position: 'relative', outline: 'none' }}>
            {children}
          </main>
        </div>
        <MobileNavC3 />
      </div>
    );
  }

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
            position: sticky inside `children` resolves here.
            Round 3 PR-I — A09-P1 a11y. id="main" matches the skip-link
            target in layout.tsx; tabIndex={-1} makes the element
            programmatically focusable so the skip link's :target jump
            actually moves keyboard focus (browsers don't focus a
            <main> on a fragment hop unless tabIndex is set). */}
        <main
          id="main"
          tabIndex={-1}
          style={{
            flex: 1,
            minWidth: 0,
            position: 'relative',
            outline: 'none',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
