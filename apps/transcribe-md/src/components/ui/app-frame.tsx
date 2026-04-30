// HANDOFF §2.1 + §8.2 — authed app shell. Composes TopNav + IconRail +
// scrollable main area under a .qm-app root. The scroll container is a
// *direct child* of the flex row so position: sticky inside `children`
// (right rails, jumplinks) resolves against it rather than silently
// failing against an overflow:hidden ancestor.
//
// This is a server component — it reads auth() once so every page can
// just render <AppFrame>...</AppFrame> without wiring user-name props.
// Client interactions (route detection, avatar dropdown, shader loop)
// live in the child components, each 'use client' as needed.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark `.qm-app`
// rendering identical to pre-remodel. Pages opt in to the Clinician
// chrome by passing `theme="clinician"`, which wraps in `.qm-cl-app`
// so all `.qm-cl-*` descendant classes resolve against the warm cream
// token scope. Both branches share the same auth() call and propagate
// the same user identity to TopNav/IconRail.

import type { ReactNode } from 'react';
import { auth } from '@/lib/nextauth';
import { TopNav } from './top-nav';
import { IconRail } from './icon-rail';
import { ShaderBG } from './shader-bg';

type AppFrameTheme = 'legacy' | 'clinician';

interface AppFrameProps {
  children: ReactNode;
  shader?: boolean;
  theme?: AppFrameTheme;
}

export async function AppFrame({
  children,
  shader = true,
  theme = 'legacy',
}: AppFrameProps) {
  const session = await auth();
  const userName = session?.user?.name || session?.user?.email || 'Doctor';
  const userEmail = session?.user?.email ?? undefined;

  if (theme === 'clinician') {
    return (
      <ClinicianAppFrame userName={userName} userEmail={userEmail}>
        {children}
      </ClinicianAppFrame>
    );
  }

  return (
    <LegacyAppFrame
      userName={userName}
      userEmail={userEmail}
      shader={shader}
    >
      {children}
    </LegacyAppFrame>
  );
}

interface InnerFrameProps {
  children: ReactNode;
  userName: string;
  userEmail: string | undefined;
}

function LegacyAppFrame({
  children,
  userName,
  userEmail,
  shader,
}: InnerFrameProps & { shader: boolean }) {
  return (
    <div
      className="qm-app"
      style={{
        width: '100%',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      {shader && <ShaderBG intensity={0.3} />}
      <div className="qm-noise" aria-hidden />

      <TopNav userName={userName} userEmail={userEmail} />

      <div
        style={{
          flex: 1,
          display: 'flex',
          minHeight: 0,
          position: 'relative',
          zIndex: 3,
        }}
      >
        <IconRail />
        {/* §8.2: scroll container is this direct child. Do NOT add
           overflow:hidden to anything between here and a sticky
           descendant or position:sticky will silently go static. */}
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            position: 'relative',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}

function ClinicianAppFrame({
  children,
  userName,
  userEmail,
}: InnerFrameProps) {
  // Per direction CL-5: no theatrical motion. ShaderBG is intentionally
  // omitted from the Clinician branch (it stays available for the
  // legacy branch). The cream canvas comes from `.qm-cl-app` itself.
  return (
    <div
      className="qm-cl-app"
      style={{
        width: '100%',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      <TopNav theme="clinician" userName={userName} userEmail={userEmail} />

      <div
        style={{
          flex: 1,
          display: 'flex',
          minHeight: 0,
          position: 'relative',
        }}
      >
        <IconRail theme="clinician" />
        {/* §8.2 still applies: keep this <main> as the direct overflow
           parent so position: sticky inside `children` resolves here. */}
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            position: 'relative',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
