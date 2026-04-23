'use client';

import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { SpecularButton } from '@/components/specular-button';
import { LocalTime } from '@/components/ui/local-time';
import { signOutAction, signOutAllDevicesAction } from '@/actions/session';

interface SessionPanelProps {
  ipAddress: string | null;
  browser: string;
  os: string;
  locationLabel: string;
  /** ISO 8601 UTC — session createdAt. Formatted client-side in the
   *  viewer's local timezone. */
  loggedInAtIso: string;
  /** ISO 8601 UTC — session expiresAt. */
  expiresAtIso: string;
  /** ISO 8601 UTC — session lastActiveAt. */
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
    <div className="space-y-6">
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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

      <div className="border-t border-border-subtle pt-6">
        <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-danger">
          Danger zone
        </div>
        <p className="mb-3 text-[13px] text-text-tertiary">
          If you think your account was accessed without your permission, sign out
          of every device to revoke all active sessions.
        </p>
        <SpecularButton
          variant="secondary"
          size="md"
          onClick={doSignOutAll}
          className="border-danger/40 text-danger hover:border-danger hover:text-danger"
        >
          Sign out all devices
        </SpecularButton>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-surface-1/60 px-3.5 py-3">
      <dt className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </dt>
      <dd className="mt-1 text-[13px] text-text-secondary break-all">{value}</dd>
    </div>
  );
}
