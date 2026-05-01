// Phase 5 — Linear V1 Faithful auth shell.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (chrome
// tokens), landing-v1.html (sage-glow accent on a darker right pane).
//
// Split-screen on dark canvas:
//   - Left pane (linear-bg): brand wordmark + form card
//   - Right pane (linear-surface-1, hidden < 980px): subtle sage glow
//     accent with HIPAA / BAA / US-hosted trust strip in mono.
//
// All Phase 4 cinematic photo-band machinery is gone. The `cinematic`
// prop and `AuthShellTheme` / `AuthShellCinematic` types are kept for
// back-compat with login/page.tsx etc. that still pass them — the
// runtime ignores both. Stage 5 will drop the props in one sweep.

import type { ReactNode } from 'react';
import { Ic } from './icon';

export type AuthShellTheme = 'legacy' | 'clinician';

/** @deprecated kept for back-compat; cinematic photo band is removed. */
export interface AuthShellCinematic {
  eyebrow?: ReactNode;
  headlinePre: string;
  headlineEm: string;
  headlinePost: string;
}

export function AuthShell({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  /** Small mono all-caps line above the title. */
  eyebrow?: ReactNode;
  /** Page heading. JSX accepted; emphasised <em> nodes pick up
   *  sage-bright color via the .qm-auth-em selector below. */
  title: ReactNode;
  subtitle?: ReactNode;
  /** Form + inline nav links. Rendered inside the form card. */
  children: ReactNode;
  /** @deprecated kept for back-compat with unmigrated callers. */
  theme?: AuthShellTheme;
  /** @deprecated kept for back-compat; cinematic band is removed. */
  cinematic?: AuthShellCinematic;
}) {
  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        background: 'var(--color-linear-bg)',
        color: 'var(--color-linear-text)',
        display: 'grid',
        gridTemplateColumns: '1fr',
      }}
    >
      <style>{`
        @media (min-width: 980px) {
          .qm-auth-grid {
            grid-template-columns: 1fr 1fr !important;
          }
          .qm-auth-right {
            display: flex !important;
          }
        }
        /* Promote <em> inside the auth title to sage-bright + non-italic
           regardless of any legacy inline color the page may pass.
           Hard rule: Linear V1 has no Source Serif italics. */
        .qm-auth-em-host em {
          color: var(--color-linear-sage-bright) !important;
          font-style: normal !important;
        }
      `}</style>

      <div
        className="qm-auth-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr',
          minHeight: '100vh',
        }}
      >
        {/* LEFT — form pane */}
        <section
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '48px 24px',
            background: 'var(--color-linear-bg)',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 400,
            }}
          >
            {/* Brand */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 32,
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 6,
                  background:
                    'linear-gradient(135deg, var(--color-linear-sage) 0%, var(--color-linear-sage-deep) 100%)',
                  display: 'grid',
                  placeItems: 'center',
                  color: '#0c1410',
                  fontSize: 12,
                  fontWeight: 700,
                  boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.06)',
                }}
              >
                Q
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 16,
                  fontWeight: 600,
                  letterSpacing: '-0.01em',
                  color: 'var(--color-linear-text)',
                }}
              >
                QuillMD
              </span>
            </div>

            {eyebrow && (
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10.5,
                  fontWeight: 500,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--color-linear-text-3)',
                  marginBottom: 12,
                }}
              >
                {eyebrow}
              </div>
            )}
            <h1
              style={{
                margin: 0,
                fontFamily: 'var(--font-sans)',
                fontSize: 26,
                fontWeight: 500,
                letterSpacing: '-0.015em',
                lineHeight: 1.2,
                color: 'var(--color-linear-text)',
              }}
            >
              <AuthTitle>{title}</AuthTitle>
            </h1>
            {subtitle && (
              <p
                style={{
                  fontFamily: 'var(--font-sans)',
                  marginTop: 8,
                  marginBottom: 28,
                  fontSize: 13.5,
                  lineHeight: 1.5,
                  color: 'var(--color-linear-text-2)',
                  letterSpacing: '-0.005em',
                }}
              >
                {subtitle}
              </p>
            )}
            {!subtitle && <div style={{ height: 24 }} />}

            <div>{children}</div>

            {/* Trust footer */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 14,
                marginTop: 28,
                color: 'var(--color-linear-text-3)',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.04em',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <Ic.shield width={12} height={12} />
                HIPAA ready
              </span>
              <span style={{ color: 'var(--color-linear-text-3)' }}>·</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <Ic.lock width={12} height={12} />
                BAA included
              </span>
              <span style={{ color: 'var(--color-linear-text-3)' }}>·</span>
              <span>US-hosted</span>
            </div>
          </div>
        </section>

        {/* RIGHT — accent pane (hidden under 980px) */}
        <section
          className="qm-auth-right"
          aria-hidden
          style={{
            display: 'none',
            position: 'relative',
            background: 'var(--color-linear-surface-1)',
            borderLeft: '1px solid var(--color-linear-border)',
            overflow: 'hidden',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '48px',
          }}
        >
          {/* Sage glow accent */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage:
                'radial-gradient(circle at 70% 35%, var(--color-linear-sage-glow), transparent 55%)',
              opacity: 0.7,
              pointerEvents: 'none',
            }}
          />
          {/* Hairline grid */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage:
                'linear-gradient(var(--color-linear-hairline) 1px, transparent 1px), linear-gradient(90deg, var(--color-linear-hairline) 1px, transparent 1px)',
              backgroundSize: '64px 64px',
              maskImage:
                'radial-gradient(circle at 60% 40%, #000 0%, transparent 70%)',
              WebkitMaskImage:
                'radial-gradient(circle at 60% 40%, #000 0%, transparent 70%)',
              opacity: 0.6,
              pointerEvents: 'none',
            }}
          />
          <div
            style={{
              position: 'relative',
              maxWidth: 360,
              textAlign: 'left',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10.5,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--color-linear-sage-bright)',
                marginBottom: 16,
              }}
            >
              QuillMD · Clinical workspace
            </div>
            <h2
              style={{
                margin: 0,
                fontFamily: 'var(--font-sans)',
                fontSize: 22,
                fontWeight: 500,
                lineHeight: 1.3,
                letterSpacing: '-0.012em',
                color: 'var(--color-linear-text)',
              }}
            >
              Notes drafted in seconds. Signed by the{' '}
              <span style={{ color: 'var(--color-linear-sage-bright)' }}>
                clinician
              </span>
              .
            </h2>
            <p
              style={{
                marginTop: 14,
                fontFamily: 'var(--font-sans)',
                fontSize: 13,
                lineHeight: 1.55,
                color: 'var(--color-linear-text-2)',
                letterSpacing: '-0.005em',
              }}
            >
              SOAP, ICD-10, and CPT pulled from the encounter audio.
              Reviewable, exportable, HIPAA-eligible.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

/** Wrap the title in a span that promotes any <em> child to sage-bright.
 *  Pages pass `<>Sign <em>in</em></>` and the em picks up the accent
 *  via the .qm-auth-em selector. We render children verbatim — the
 *  accent is applied through CSS so callers don't need to know it. */
function AuthTitle({ children }: { children: ReactNode }) {
  return <span className="qm-auth-em-host">{children}</span>;
}

// ─────────────────────────────────────────────────────────────────────
// Field subcomponents — shared by login / signup / forgot / reset /
// check-email forms. Now Linear V1 only: mono uppercase label,
// linear-text-3 color, linear-coral error message.
// ─────────────────────────────────────────────────────────────────────

/** Auth form-field label. Mono uppercase in linear-text-3. */
export function AuthFieldLabel({
  htmlFor,
  children,
  hint,
}: {
  htmlFor: string;
  children: ReactNode;
  /** Right-aligned secondary content (e.g., "Forgot?" link). */
  hint?: ReactNode;
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
      }}
    >
      <label
        htmlFor={htmlFor}
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          fontWeight: 500,
          color: 'var(--color-linear-text-3)',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
        }}
      >
        {children}
      </label>
      {hint}
    </div>
  );
}

/** Inline field-level error message (role="alert"). */
export function AuthFieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      style={{
        marginTop: 6,
        fontFamily: 'var(--font-sans)',
        fontSize: 12,
        color: 'var(--color-linear-coral)',
        letterSpacing: '-0.005em',
      }}
    >
      {message}
    </p>
  );
}
