'use client';

// ============================================================================
// MfaManagementPanel — shown when the user has MFA already enabled
// ----------------------------------------------------------------------------
//   - "MFA is on" status pill + verifiedAt date
//   - Disable button → opens dialog requiring password + TOTP/recovery
//   - SUPER_ADMIN gets a "MFA cannot be disabled (admin role)" message
//     instead of the disable button
// ============================================================================

import { useState } from 'react';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

import { Ic } from '@/components/ui/icon';

interface Props {
  /** Computed on the SERVER by `isMfaDisableLocked` (lib/super-admin.ts):
   *  the same predicate /api/mfa/disable refuses on. This panel used to
   *  compare `role === 'SUPER_ADMIN'`, so a platform SUPER_ADMIN, who is
   *  role DOCTOR in production, was shown a Disable button. */
  disableLocked: boolean;
  verifiedAt: string | null;
}

export function MfaManagementPanel({ disableLocked, verifiedAt }: Props) {
  const router = useRouter();
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const isSuperAdmin = disableLocked;

  async function disableMfa() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/mfa/disable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password,
          token: useRecovery ? undefined : token,
          recoveryCode: useRecovery ? recoveryCode : undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setError(json.error ?? 'Could not disable MFA');
        return;
      }
      toast.success('MFA disabled');
      setDialogOpen(false);
      router.refresh();
    } catch {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      style={{
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
        borderRadius: 10,
        padding: 22,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
        }}
      >
        {/* ⚠️ THE "ON" PILL IS ON THE READY FAMILY, AND THE BRIDGE IS WHY IT
            HAD TO BE. The obvious chrome here is raw SAGE literals —
            `rgba(122,166,140,·)` is `--color-linear-sage` at 13% / 32% — with
            the label on `--color-linear-sage-bright`, which the host bridge
            maps to `--rounds-accent-text` (#a5a5f0). Left on those tokens,
            this pill renders an INDIGO label inside a GREEN wash with a GREEN
            border, on an indigo stage.
            `--color-linear-sage` is not the escape either: it bridges to
            `--rounds-accent`, so recolouring the chrome through it makes the
            pill BRAND-coloured — hue-identical to every CTA on the page — and
            the one thing it exists to say ("you are protected") stops being
            legible at a glance. Green is right here; it is the wrong green.
            Rounds separates brand from success and carries a positive family
            for exactly this, and the shape below is `.qm-rounds-signed-lock`'s,
            which the spec requires green for the same reason.
            So the pill reads `--rounds-ready` directly: #6ee7a8 on the 12%
            wash over surface-1, 10.2:1. The `Ic.check` is `currentColor` and
            follows the label. */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            background:
              'color-mix(in srgb, var(--rounds-ready) 12%, transparent)',
            border: '1px solid var(--rounds-ready)',
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--rounds-ready-text)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          <Ic.check width={11} height={11} aria-hidden /> MFA enabled
        </span>
        {verifiedAt && (
          <span
            style={{
              fontSize: 12,
              color: 'var(--color-linear-text-3)',
              fontFamily: 'var(--font-sans)',
            }}
          >
            since {new Date(verifiedAt).toLocaleDateString()}
          </span>
        )}
      </div>

      <p
        style={{
          margin: 0,
          fontSize: 13,
          color: 'var(--color-linear-text-2)',
          fontFamily: 'var(--font-sans)',
          lineHeight: 1.55,
        }}
      >
        You&apos;ll be prompted for a 6-digit code on every sign-in. If you
        lose your authenticator app, use one of your saved recovery codes.
      </p>

      {isSuperAdmin ? (
        <div
          style={{
            marginTop: 14,
            padding: '10px 12px',
            background: 'var(--color-linear-surface-2)',
            border: '1px solid var(--color-linear-border)',
            borderRadius: 8,
            fontSize: 12.5,
            color: 'var(--color-linear-text-2)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          MFA cannot be disabled on SUPER_ADMIN accounts. To remove the
          factor, remove SUPER_ADMIN from the account first.
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="qm-lin-btn"
          style={{ marginTop: 16 }}
        >
          Disable MFA
        </button>
      )}

      {isDialogOpen && (
        <div
          role="dialog"
          aria-label="Disable MFA"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setDialogOpen(false);
          }}
        >
          <div
            style={{
              background: 'var(--color-linear-surface-1)',
              border: '1px solid var(--color-linear-border)',
              borderRadius: 12,
              padding: 22,
              width: 'min(420px, 100%)',
              boxShadow: '0 24px 60px rgba(0, 0, 0, 0.45)',
            }}
          >
            <h3
              style={{
                margin: '0 0 4px',
                fontSize: 16,
                fontWeight: 600,
                color: 'var(--color-linear-text)',
                fontFamily: 'var(--font-sans)',
              }}
            >
              Disable two-factor authentication
            </h3>
            <p
              style={{
                margin: 0,
                fontSize: 12.5,
                color: 'var(--color-linear-text-2)',
                fontFamily: 'var(--font-sans)',
                lineHeight: 1.5,
              }}
            >
              Confirm your password + a current code to disable MFA. You can
              re-enable it any time from this page.
            </p>

            <label htmlFor="disable-pw" style={fieldLabel}>
              Password
            </label>
            <input
              id="disable-pw"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
            />

            {!useRecovery ? (
              <>
                <label htmlFor="disable-token" style={fieldLabel}>
                  6-digit code
                </label>
                <input
                  id="disable-token"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={7}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
                />
              </>
            ) : (
              <>
                <label htmlFor="disable-recovery" style={fieldLabel}>
                  Recovery code
                </label>
                <input
                  id="disable-recovery"
                  type="text"
                  maxLength={20}
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value)}
                  style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }}
                  placeholder="ABCD-1234"
                />
              </>
            )}

            <button
              type="button"
              onClick={() => setUseRecovery((v) => !v)}
              style={{
                marginTop: 8,
                background: 'none',
                border: 'none',
                padding: 0,
                fontSize: 12,
                color: 'var(--color-linear-sage-bright)',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
                fontWeight: 500,
              }}
            >
              {useRecovery ? 'Use 6-digit code instead' : 'Use a recovery code'}
            </button>

            {error && (
              <div
                role="alert"
                style={{
                  marginTop: 10,
                  fontSize: 12,
                  color: 'var(--color-linear-amber)',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                {error}
              </div>
            )}

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 10,
                marginTop: 18,
              }}
            >
              <button
                type="button"
                onClick={() => setDialogOpen(false)}
                className="qm-lin-btn"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={disableMfa}
                className="qm-lin-btn-primary"
              >
                {loading ? 'Disabling…' : 'Disable MFA'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

const fieldLabel: React.CSSProperties = {
  display: 'block',
  marginTop: 12,
  marginBottom: 6,
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--color-linear-text-2)',
  fontFamily: 'var(--font-sans)',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 36,
  padding: '0 12px',
  background: 'var(--color-linear-surface-2)',
  border: '1px solid var(--color-linear-border)',
  borderRadius: 6,
  color: 'var(--color-linear-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: 13.5,
  outline: 'none',
};
