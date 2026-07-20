"use client";

// ============================================================================
// MfaEnrollmentPanel — three-step client component
// ----------------------------------------------------------------------------
//   Step 1: scan QR (or copy the otpauth URI manually)
//   Step 2: verify with a 6-digit code
//   Step 3: download recovery codes (shown once)
// ============================================================================

import { useState } from "react";
import { toast } from "sonner";
import Image from "next/image";
import { useRouter } from "next/navigation";

import { Ic } from "@/components/ui/icon";

interface EnrollmentArtifact {
  otpauthUri: string;
  qrPngDataUrl: string;
}

type Step = "scan" | "verify" | "recovery";

export function MfaEnrollmentPanel({
  userEmail,
  completionHref = "/settings",
}: {
  userEmail: string;
  completionHref?: "/admin/template-twin-release" | "/settings";
}) {
  const router = useRouter();
  const [step, setStep] = useState<Step>("scan");
  const [artifact, setArtifact] = useState<EnrollmentArtifact | null>(null);
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [enrollmentError, setEnrollmentError] = useState<string | null>(null);

  async function startEnrollment() {
    if (!password) {
      setEnrollmentError("Enter your current password.");
      return;
    }
    setLoading(true);
    setEnrollmentError(null);
    try {
      const res = await fetch("/api/mfa/enroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        toast.error("Could not start enrollment", { description: json.error });
        return;
      }
      setArtifact({
        otpauthUri: json.otpauthUri,
        qrPngDataUrl: json.qrPngDataUrl,
      });
      setPassword("");
      setStep("verify");
    } catch {
      toast.error("Network error");
    } finally {
      setLoading(false);
    }
  }

  async function verifyToken() {
    if (token.replace(/\s+/g, "").length !== 6) {
      setTokenError("Enter the 6-digit code from your app.");
      return;
    }
    setLoading(true);
    setTokenError(null);
    try {
      const res = await fetch("/api/mfa/verify-enrollment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setTokenError(json.error ?? "Verification failed");
        return;
      }
      setRecoveryCodes(json.recoveryCodes);
      setStep("recovery");
    } catch {
      setTokenError("Network error");
    } finally {
      setLoading(false);
    }
  }

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Could not copy — select + copy manually");
    }
  }

  function downloadRecoveryCodes() {
    const text =
      `QuillMD recovery codes — ${userEmail}\n\n` +
      recoveryCodes.join("\n") +
      `\n\nGenerated: ${new Date().toISOString()}\n` +
      `Each code is single-use. Store securely.\n`;
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quillmd-mfa-recovery-codes-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
      <Stepper step={step} />

      {step === "scan" && (
        <>
          <h2 style={panelHeading}>Step 1 — Scan the QR code</h2>
          <p style={panelBody}>
            Open your authenticator app (1Password, Authy, Google Authenticator,
            etc.) and add a new account. The button below generates a fresh
            secret tied to your email. Re-enter your password before the secret
            is created.
          </p>
          <label htmlFor="mfa-enrollment-password" style={fieldLabel}>
            Current password
          </label>
          <input
            id="mfa-enrollment-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            style={{
              ...inputStyle,
              width: "100%",
              maxWidth: 360,
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              letterSpacing: "normal",
            }}
            aria-describedby={
              enrollmentError ? "mfa-enrollment-password-error" : undefined
            }
          />
          {enrollmentError && (
            <p
              id="mfa-enrollment-password-error"
              role="alert"
              style={errorStyle}
            >
              {enrollmentError}
            </p>
          )}
          <button
            type="button"
            disabled={loading || !password}
            onClick={startEnrollment}
            className="qm-lin-btn-primary"
            style={{ marginTop: 16 }}
          >
            {loading ? "Generating…" : "Generate QR code"}
          </button>
        </>
      )}

      {step === "verify" && artifact && (
        <>
          <h2 style={panelHeading}>Step 2 — Scan + verify</h2>
          <p style={panelBody}>
            Scan this QR code with your authenticator app, then enter the
            6-digit code it produces.
          </p>
          <div
            style={{
              marginTop: 14,
              padding: 16,
              background: "var(--color-linear-surface-2)",
              border: "1px solid var(--color-linear-border)",
              borderRadius: 8,
              display: "flex",
              gap: 16,
              alignItems: "flex-start",
            }}
          >
            <Image
              src={artifact.qrPngDataUrl}
              alt="MFA enrollment QR code"
              width={200}
              height={200}
              unoptimized
              style={{ background: "white", borderRadius: 4 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--color-linear-text-2)",
                  fontFamily: "var(--font-sans)",
                  marginBottom: 6,
                }}
              >
                Or paste this URI:
              </div>
              <code
                style={{
                  display: "block",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-linear-text-2)",
                  wordBreak: "break-all",
                  background: "var(--color-linear-surface-3)",
                  padding: 8,
                  borderRadius: 4,
                  maxHeight: 80,
                  overflow: "auto",
                }}
              >
                {artifact.otpauthUri}
              </code>
              <button
                type="button"
                onClick={() => copyToClipboard(artifact.otpauthUri)}
                style={{
                  marginTop: 8,
                  background: "none",
                  border: "none",
                  padding: 0,
                  fontSize: 11.5,
                  color: "var(--color-linear-sage-bright)",
                  cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                  fontWeight: 500,
                }}
              >
                Copy URI
              </button>
            </div>
          </div>

          <label htmlFor="mfa-token" style={fieldLabel}>
            6-digit code
          </label>
          <input
            id="mfa-token"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={7}
            placeholder="123456"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            style={inputStyle}
          />
          {tokenError && (
            <div
              role="alert"
              style={{
                marginTop: 6,
                fontSize: 12,
                color: "var(--color-linear-amber)",
                fontFamily: "var(--font-sans)",
              }}
            >
              {tokenError}
            </div>
          )}

          <button
            type="button"
            disabled={loading}
            onClick={verifyToken}
            className="qm-lin-btn-primary"
            style={{ marginTop: 14 }}
          >
            {loading ? "Verifying…" : "Verify + enable"}
          </button>
        </>
      )}

      {step === "recovery" && (
        <>
          <h2 style={panelHeading}>Step 3 — Save your recovery codes</h2>
          <p style={panelBody}>
            <strong style={{ color: "var(--color-linear-amber)" }}>
              These codes will not be shown again.
            </strong>{" "}
            Each is single-use. Store them where you can reach them if you lose
            access to your authenticator app.
          </p>
          <pre
            style={{
              marginTop: 14,
              padding: 14,
              background: "var(--color-linear-surface-2)",
              border: "1px solid var(--color-linear-border)",
              borderRadius: 8,
              fontSize: 13,
              fontFamily: "var(--font-mono)",
              color: "var(--color-linear-text)",
              letterSpacing: "0.5px",
              lineHeight: 1.6,
            }}
          >
            {recoveryCodes.join("\n")}
          </pre>

          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button
              type="button"
              onClick={() => copyToClipboard(recoveryCodes.join("\n"))}
              className="qm-lin-btn"
            >
              Copy all
            </button>
            <button
              type="button"
              onClick={downloadRecoveryCodes}
              className="qm-lin-btn"
            >
              Download .txt
            </button>
            <button
              type="button"
              onClick={() => router.push(completionHref)}
              className="qm-lin-btn-primary"
              style={{ marginLeft: "auto" }}
            >
              I&apos;ve saved them — done
              <Ic.arrowRight width={14} height={14} />
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function Stepper({ step }: { step: Step }) {
  const steps: Array<[Step, string]> = [
    ["scan", "Generate"],
    ["verify", "Verify"],
    ["recovery", "Recovery"],
  ];
  const currentIndex = steps.findIndex((s) => s[0] === step);
  return (
    <ol
      aria-label="Enrollment steps"
      style={{
        display: "flex",
        gap: 8,
        listStyle: "none",
        padding: 0,
        margin: "0 0 18px",
      }}
    >
      {steps.map(([key, label], i) => {
        const isActive = i === currentIndex;
        const isDone = i < currentIndex;
        return (
          <li
            key={key}
            aria-current={isActive ? "step" : undefined}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: isActive
                ? "var(--color-linear-text)"
                : isDone
                  ? "var(--color-linear-sage-bright)"
                  : "var(--color-linear-text-3)",
              fontFamily: "var(--font-sans)",
              fontWeight: isActive ? 600 : 500,
            }}
          >
            <span
              aria-hidden
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 18,
                height: 18,
                borderRadius: "50%",
                fontSize: 10.5,
                background: isActive
                  ? "var(--color-linear-sage)"
                  : isDone
                    ? "var(--color-linear-sage)"
                    : "var(--color-linear-surface-2)",
                color:
                  isActive || isDone ? "#0d1611" : "var(--color-linear-text-3)",
                border:
                  isActive || isDone
                    ? "none"
                    : "1px solid var(--color-linear-border)",
              }}
            >
              {i + 1}
            </span>
            {label}
          </li>
        );
      })}
    </ol>
  );
}

const panelHeading: React.CSSProperties = {
  margin: 0,
  fontSize: 16,
  fontWeight: 600,
  color: "var(--color-linear-text)",
  fontFamily: "var(--font-sans)",
};

const panelBody: React.CSSProperties = {
  margin: "6px 0 0",
  fontSize: 13,
  color: "var(--color-linear-text-2)",
  fontFamily: "var(--font-sans)",
  lineHeight: 1.55,
};

const fieldLabel: React.CSSProperties = {
  display: "block",
  marginTop: 14,
  marginBottom: 6,
  fontSize: 12,
  fontWeight: 500,
  color: "var(--color-linear-text-2)",
  fontFamily: "var(--font-sans)",
};

const inputStyle: React.CSSProperties = {
  width: 200,
  height: 36,
  padding: "0 12px",
  background: "var(--color-linear-surface-2)",
  border: "1px solid var(--color-linear-border)",
  borderRadius: 6,
  color: "var(--color-linear-text)",
  fontFamily: "var(--font-mono)",
  fontSize: 16,
  letterSpacing: "2px",
  outline: "none",
};

const errorStyle: React.CSSProperties = {
  margin: "6px 0 0",
  color: "var(--color-linear-danger, #e78284)",
  fontFamily: "var(--font-sans)",
  fontSize: 12,
};
