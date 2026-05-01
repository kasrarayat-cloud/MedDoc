'use client';

import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { SpecularButton } from '@/components/specular-button';
import { LocalTime } from '@/components/ui/local-time';
import { signOutAction, signOutAllDevicesAction } from '@/actions/session';

// Phase 5 — Linear V1 Faithful session panel. Server actions
// (signOutAction, signOutAllDevicesAction) are unchanged per
// PROTECTED_CONTRACTS.

interface SessionPanelProps {
  ipAddress: string | null;
  browser: string;
  os: string;
  locationLabel: string;
  loggedInAtIso: string;
  expiresAtIso: string;
  lastActiveAtIso: string;
}

export function SessionPanel(props: SessionPanelProps) {
  const router = useRouter();

  async function doSignOut() {
    await signOutAction();
    toast.success('Signed out');
    router.push('/login');
    router.refresh();
  }

  async function doSignOutAll() {
    await signOutAllDevicesAction();
    toast.success('Signed out from all devices', {
      description: 'Every active session has been revoked.',
    });
    router.push('/login');
    router.refresh();
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <dl
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
          margin: 0,
        }}
      >
        <Row label="IP address" value={props.ipAddress ?? 'Unknown'} />
        <Row label="Location" value={props.locationLabel} />
        <Row label="Browser" value={`${props.browser} · ${props.os}`} />
        <Row
          label="Logged in"
          value={<LocalTime iso={props.loggedInAtIso} variant="dateTime" />}
        />
        <Row
          label="Last active"
          value={<LocalTime iso={props.lastActiveAtIso} variant="relative" />}
        />
        <Row
          label="Expires"
          value={<LocalTime iso={props.expiresAtIso} variant="dateTime" />}
        />
      </dl>

      <div>
        <SpecularButton variant="secondary" size="md" onClick={doSignOut}>
          Sign out
        </SpecularButton>
      </div>

      <div
        style={{
          borderTop: '1px solid var(--color-linear-hairline)',
          paddingTop: 18,
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.07em',
            color: 'var(--color-linear-coral)',
            marginBottom: 6,
          }}
        >
          Danger zone
        </div>
        <p
          style={{
            margin: '0 0 12px',
            fontFamily: 'var(--font-sans)',
            fontSize: 13,
            color: 'var(--color-linear-text-2)',
            lineHeight: 1.5,
          }}
        >
          If you think your account was accessed without your permission, sign
          out of every device to revoke all active sessions.
        </p>
        <button
          type="button"
          onClick={doSignOutAll}
          className="qm-lin-btn"
          style={{
            borderColor: 'rgba(212, 87, 74, 0.40)',
            color: 'var(--color-linear-coral)',
          }}
        >
          Sign out all devices
        </button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div
      style={{
        padding: '10px 12px',
        background: 'var(--color-linear-surface-2)',
        border: '1px solid var(--color-linear-border)',
        borderRadius: 6,
      }}
    >
      <dt
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          fontWeight: 500,
          letterSpacing: '0.07em',
          textTransform: 'uppercase',
          color: 'var(--color-linear-text-3)',
        }}
      >
        {label}
      </dt>
      <dd
        style={{
          margin: '4px 0 0',
          fontFamily: 'var(--font-sans)',
          fontSize: 13,
          color: 'var(--color-linear-text)',
          wordBreak: 'break-all',
        }}
      >
        {value}
      </dd>
    </div>
  );
}
