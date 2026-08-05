// Rounds (R1) app shell.
//
// Server component — reads auth() once so every page can just render
// <AppFrame>...</AppFrame> without wiring user-name props. Client
// interactions (route detection, avatar dropdown) live inside
// RoundsAppFrame and its children, each marked 'use client' as needed.
//
// `theme` and `shader` props remain in the type signature for backward
// compatibility with surface code that hasn't been migrated yet, but
// are intentionally ignored.

import type { ReactNode } from 'react';
import { auth } from '@/lib/nextauth';
import { RoundsAppFrame } from '@/components/rounds/app-frame-rounds';

type AppFrameTheme = 'legacy' | 'clinician';

interface AppFrameProps {
  children: ReactNode;
  /** @deprecated kept for back-compat; Rounds has no shader. */
  shader?: boolean;
  /** @deprecated kept for back-compat; Rounds is single-theme. */
  theme?: AppFrameTheme;
}

export async function AppFrame({ children }: AppFrameProps) {
  const session = await auth();
  const userName = session?.user?.name || session?.user?.email || 'Doctor';

  // ── ROUNDS (R1) ─────────────────────────────────────────────────────────────
  // The app was split-brain before this became the only path: `AppFrame` wraps
  // every authed route outside the board, and it used to fork on its own skin
  // flag — so `/board` rendered the Rounds nav with 0 asides while `/patients`,
  // `/dashboard` and `/settings` each rendered a 240px C3 sidebar with a
  // DIFFERENT nav, and `/settings` rendered a Rounds host *inside* that legacy
  // aside. One doctor, one session, two products.
  //
  // No <aside>. The nav is horizontal and shared with the board, so there is
  // one nav in the app and it cannot drift. Full detail, and the measurement
  // that found the fork, in `components/rounds/app-frame-rounds.tsx`.
  return <RoundsAppFrame userName={userName}>{children}</RoundsAppFrame>;
}
