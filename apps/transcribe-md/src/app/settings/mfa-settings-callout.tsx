import Link from "next/link";

import { Ic } from "@/components/ui/icon";

export function MfaSettingsCallout({ enabled }: { enabled: boolean }) {
  return (
    <div style={{ marginTop: 20 }}>
      <div
        style={{
          padding: "14px 16px",
          borderRadius: 8,
          border: "1px dashed var(--color-linear-border-strong)",
          background: "var(--color-linear-row-hover)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 6,
          }}
        >
          <Ic.shield
            width={14}
            height={14}
            aria-hidden
            style={{ color: "var(--color-linear-sage-bright)" }}
          />
          <span
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              fontWeight: 500,
              color: "var(--color-linear-text)",
            }}
          >
            Two-factor authentication
          </span>
          <span
            className={
              enabled
                ? "qm-lin-pill qm-lin-pill--ready"
                : "qm-lin-pill qm-lin-pill--review"
            }
          >
            {enabled ? "Enabled" : "Off"}
          </span>
        </div>
        <p
          style={{
            margin: 0,
            fontFamily: "var(--font-sans)",
            fontSize: 12.5,
            color: "var(--color-linear-text-2)",
            lineHeight: 1.55,
          }}
        >
          {enabled
            ? "Review your authenticator and recovery-code readiness."
            : "Add an authenticator app and generate one-time recovery codes."}
        </p>
        <Link
          href="/settings/security/mfa"
          className="qm-lin-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            height: 36,
            marginTop: 12,
          }}
        >
          {enabled ? "Manage MFA" : "Set up MFA"}
        </Link>
      </div>
    </div>
  );
}
