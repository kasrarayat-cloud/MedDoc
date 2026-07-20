"use client";

// ============================================================================
// MfaManagementPanel — shown when the user has MFA already enabled
// ----------------------------------------------------------------------------
//   - "MFA is on" status pill + verifiedAt date
//   - Recovery-code rotation requires password + current TOTP and shows the
//     new codes once; available to physicians and platform administrators
//   - Disable button → opens dialog requiring password + TOTP/recovery
//   - Product.SUPER_ADMIN gets a mandatory-MFA message
//     instead of the disable button
// ============================================================================

import { useState } from "react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { Ic } from "@/components/ui/icon";

interface Props {
  isPlatformAdmin: boolean;
  usableRecoveryCodeCount: number | null;
  verifiedAt: string | null;
}

export function MfaManagementPanel({
  isPlatformAdmin,
  usableRecoveryCodeCount,
  verifiedAt,
}: Props) {
  const router = useRouter();
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isRotationDialogOpen, setRotationDialogOpen] = useState(false);
  const [rotationPassword, setRotationPassword] = useState("");
  const [rotationToken, setRotationToken] = useState("");
  const [rotationError, setRotationError] = useState<string | null>(null);
  const [rotationLoading, setRotationLoading] = useState(false);
  const [rotatedRecoveryCodes, setRotatedRecoveryCodes] = useState<string[]>(
    [],
  );
  const effectiveRecoveryCodeCount =
    rotatedRecoveryCodes.length > 0
      ? rotatedRecoveryCodes.length
      : usableRecoveryCodeCount;
  const canUseRecoveryCode =
    effectiveRecoveryCodeCount !== null && effectiveRecoveryCodeCount > 0;

  async function disableMfa() {
    setLoading(true);
    setError(null);
    const usingRecoveryCode = useRecovery && canUseRecoveryCode;
    try {
      const res = await fetch("/api/mfa/disable", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          password,
          token: usingRecoveryCode ? undefined : token,
          recoveryCode: usingRecoveryCode ? recoveryCode : undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setError(json.error ?? "Could not disable MFA");
        return;
      }
      toast.success("MFA disabled");
      setDialogOpen(false);
      router.refresh();
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }

  function closeRotationDialog() {
    if (rotationLoading) return;
    setRotationDialogOpen(false);
    setRotationPassword("");
    setRotationToken("");
    setRotationError(null);
  }

  async function rotateRecoveryCodes() {
    setRotationLoading(true);
    setRotationError(null);
    try {
      const res = await fetch("/api/mfa/recovery-codes/rotate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          password: rotationPassword,
          token: rotationToken,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setRotationError(json.error ?? "Could not generate recovery codes");
        return;
      }
      if (
        !Array.isArray(json.recoveryCodes) ||
        json.recoveryCodes.length === 0 ||
        !json.recoveryCodes.every((code: unknown) => typeof code === "string")
      ) {
        setRotationError("Could not generate recovery codes");
        return;
      }
      setRotatedRecoveryCodes(json.recoveryCodes);
      setRotationPassword("");
      setRotationToken("");
      setRotationDialogOpen(false);
      toast.success("Recovery codes replaced");
    } catch {
      setRotationError("Network error");
    } finally {
      setRotationLoading(false);
    }
  }

  return (
    <section
      style={{
        background: "var(--color-linear-surface-1)",
        border: "1px solid var(--color-linear-border)",
        borderRadius: 10,
        padding: 22,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            background: "rgba(122, 166, 140, 0.13)",
            border: "1px solid rgba(122, 166, 140, 0.32)",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 500,
            color: "var(--color-linear-sage-bright)",
            fontFamily: "var(--font-sans)",
          }}
        >
          <Ic.check width={11} height={11} aria-hidden /> MFA enabled
        </span>
        {verifiedAt && (
          <span
            style={{
              fontSize: 12,
              color: "var(--color-linear-text-3)",
              fontFamily: "var(--font-sans)",
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
          color: "var(--color-linear-text-2)",
          fontFamily: "var(--font-sans)",
          lineHeight: 1.55,
        }}
      >
        You&apos;ll be prompted for a 6-digit code on every sign-in.
        {effectiveRecoveryCodeCount !== null && effectiveRecoveryCodeCount > 0
          ? ` You currently have ${effectiveRecoveryCodeCount} usable recovery ${effectiveRecoveryCodeCount === 1 ? "code" : "codes"}.`
          : " Your authenticator remains active, but no usable recovery code is confirmed."}
      </p>

      {(effectiveRecoveryCodeCount === null ||
        effectiveRecoveryCodeCount === 0) && (
        <div
          role="alert"
          aria-labelledby="mfa-no-usable-recovery-codes"
          style={{
            marginTop: 14,
            padding: "10px 12px",
            background: "rgba(212, 165, 116, 0.08)",
            border: "1px solid rgba(212, 165, 116, 0.36)",
            borderRadius: 8,
            fontSize: 12.5,
            lineHeight: 1.5,
            color: "var(--color-linear-text)",
            fontFamily: "var(--font-sans)",
          }}
        >
          <strong
            id="mfa-no-usable-recovery-codes"
            style={{ display: "block", marginBottom: 3 }}
          >
            No usable recovery codes—generate replacements now
          </strong>
          Legacy recovery codes are retired and cannot be used. Confirm your
          password and a current authenticator code below to create a new set.
        </div>
      )}

      <button
        type="button"
        onClick={() => setRotationDialogOpen(true)}
        className="qm-lin-btn"
        style={{ marginTop: 16 }}
      >
        Generate new recovery codes
      </button>

      {rotatedRecoveryCodes.length > 0 && (
        <div
          aria-live="polite"
          style={{
            marginTop: 16,
            padding: "14px 16px",
            background: "var(--color-linear-surface-2)",
            border: "1px solid var(--color-linear-border)",
            borderRadius: 8,
          }}
        >
          <h3
            style={{
              margin: "0 0 6px",
              fontSize: 14,
              color: "var(--color-linear-text)",
              fontFamily: "var(--font-sans)",
            }}
          >
            Save your new recovery codes
          </h3>
          <p
            style={{
              margin: "0 0 10px",
              fontSize: 12.5,
              lineHeight: 1.5,
              color: "var(--color-linear-text-2)",
              fontFamily: "var(--font-sans)",
            }}
          >
            Your previous codes no longer work. This is the only time QuillMD
            will return this replacement set. Store it somewhere secure before
            leaving this page.
          </p>
          <ul
            aria-label="New recovery codes"
            style={{
              margin: 0,
              paddingLeft: 22,
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
              columnGap: 18,
              color: "var(--color-linear-text)",
              fontFamily: "var(--font-mono)",
              fontSize: 12.5,
              lineHeight: 1.8,
              minWidth: 0,
              overflowX: "auto",
            }}
          >
            {rotatedRecoveryCodes.map((code) => (
              <li key={code} style={{ minWidth: 0, overflowWrap: "anywhere" }}>
                <code>{code}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isPlatformAdmin ? (
        <div
          style={{
            marginTop: 14,
            padding: "10px 12px",
            background: "var(--color-linear-surface-2)",
            border: "1px solid var(--color-linear-border)",
            borderRadius: 8,
            fontSize: 12.5,
            color: "var(--color-linear-text-2)",
            fontFamily: "var(--font-sans)",
          }}
        >
          MFA cannot be disabled while this account has the platform-admin
          product entitlement. Revoke that entitlement through the controlled
          admin workflow first.
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

      {isRotationDialogOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Generate new recovery codes"
          style={dialogBackdropStyle}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeRotationDialog();
          }}
        >
          <div style={dialogSurfaceStyle}>
            <h3
              style={{
                margin: "0 0 4px",
                fontSize: 16,
                fontWeight: 600,
                color: "var(--color-linear-text)",
                fontFamily: "var(--font-sans)",
              }}
            >
              Replace recovery codes
            </h3>
            <p
              style={{
                margin: 0,
                fontSize: 12.5,
                color: "var(--color-linear-text-2)",
                fontFamily: "var(--font-sans)",
                lineHeight: 1.5,
              }}
            >
              Confirm your password and a current authenticator code. All old
              recovery codes will stop working, and your other sessions will be
              signed out.
            </p>

            <label htmlFor="rotate-recovery-password" style={fieldLabel}>
              Password
            </label>
            <input
              id="rotate-recovery-password"
              type="password"
              autoComplete="current-password"
              maxLength={200}
              value={rotationPassword}
              onChange={(event) => setRotationPassword(event.target.value)}
              style={inputStyle}
            />

            <label htmlFor="rotate-recovery-token" style={fieldLabel}>
              Current 6-digit code
            </label>
            <input
              id="rotate-recovery-token"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={7}
              value={rotationToken}
              onChange={(event) => setRotationToken(event.target.value)}
              style={{ ...inputStyle, fontFamily: "var(--font-mono)" }}
            />

            {rotationError && (
              <div
                role="alert"
                style={{
                  marginTop: 10,
                  fontSize: 12,
                  color: "var(--color-linear-amber)",
                  fontFamily: "var(--font-sans)",
                }}
              >
                {rotationError}
              </div>
            )}

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 10,
                marginTop: 18,
              }}
            >
              <button
                type="button"
                onClick={closeRotationDialog}
                disabled={rotationLoading}
                className="qm-lin-btn"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={rotationLoading}
                onClick={rotateRecoveryCodes}
                className="qm-lin-btn-primary"
              >
                {rotationLoading ? "Replacing…" : "Replace codes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {isDialogOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Disable MFA"
          style={dialogBackdropStyle}
          onClick={(e) => {
            if (e.target === e.currentTarget) setDialogOpen(false);
          }}
        >
          <div style={dialogSurfaceStyle}>
            <h3
              style={{
                margin: "0 0 4px",
                fontSize: 16,
                fontWeight: 600,
                color: "var(--color-linear-text)",
                fontFamily: "var(--font-sans)",
              }}
            >
              Disable two-factor authentication
            </h3>
            <p
              style={{
                margin: 0,
                fontSize: 12.5,
                color: "var(--color-linear-text-2)",
                fontFamily: "var(--font-sans)",
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

            {!useRecovery || !canUseRecoveryCode ? (
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
                  style={{ ...inputStyle, fontFamily: "var(--font-mono)" }}
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
                  maxLength={40}
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value)}
                  style={{ ...inputStyle, fontFamily: "var(--font-mono)" }}
                  placeholder="ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345"
                />
              </>
            )}

            {canUseRecoveryCode && (
              <button
                type="button"
                onClick={() => setUseRecovery((v) => !v)}
                style={{
                  marginTop: 8,
                  background: "none",
                  border: "none",
                  padding: 0,
                  fontSize: 12,
                  color: "var(--color-linear-sage-bright)",
                  cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                  fontWeight: 500,
                }}
              >
                {useRecovery
                  ? "Use 6-digit code instead"
                  : "Use a recovery code"}
              </button>
            )}

            {error && (
              <div
                role="alert"
                style={{
                  marginTop: 10,
                  fontSize: 12,
                  color: "var(--color-linear-amber)",
                  fontFamily: "var(--font-sans)",
                }}
              >
                {error}
              </div>
            )}

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
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
                {loading ? "Disabling…" : "Disable MFA"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

const fieldLabel: React.CSSProperties = {
  display: "block",
  marginTop: 12,
  marginBottom: 6,
  fontSize: 12,
  fontWeight: 500,
  color: "var(--color-linear-text-2)",
  fontFamily: "var(--font-sans)",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  height: 36,
  boxSizing: "border-box",
  padding: "0 12px",
  background: "var(--color-linear-surface-2)",
  border: "1px solid var(--color-linear-border)",
  borderRadius: 6,
  color: "var(--color-linear-text)",
  fontFamily: "var(--font-sans)",
  fontSize: 13.5,
  outline: "none",
};

const dialogBackdropStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(0, 0, 0, 0.55)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
  boxSizing: "border-box",
  padding: 16,
};

const dialogSurfaceStyle: React.CSSProperties = {
  background: "var(--color-linear-surface-1)",
  border: "1px solid var(--color-linear-border)",
  borderRadius: 12,
  padding: 22,
  width: "min(420px, 100%)",
  maxHeight: "calc(100dvh - 32px)",
  overflowY: "auto",
  boxSizing: "border-box",
  boxShadow: "0 24px 60px rgba(0, 0, 0, 0.45)",
};
