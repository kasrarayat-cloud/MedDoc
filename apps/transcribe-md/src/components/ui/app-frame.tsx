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

import type { ReactNode } from 'react';
import { auth } from '@/lib/nextauth';
import { TopNav } from './top-nav';
import { IconRail } from './icon-rail';
import { ShaderBG } from './shader-bg';

export async function AppFrame({
  children,
  shader = true,
}: {
  children: ReactNode;
  shader?: boolean;
}) {
  const session = await auth();
  const userName = session?.user?.name || session?.user?.email || 'Doctor';
  const userEmail = session?.user?.email ?? undefined;

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
