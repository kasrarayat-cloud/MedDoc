// HANDOFF §2.2 (SignInScreen visual) — shared shell for every auth route
// (login, signup, forgot-password, reset-password, check-email).
//
// Two visual variants live behind a single `theme` prop:
//   - `'legacy'`  (default): the original dark App-redesign-v1 surface —
//                  ShaderBG + mesh-grid + .qm-glass card. Kept intact in
//                  case any non-Clinician auth caller appears later.
//   - `'clinician'`: warm cream canvas, Source Serif 4 wordmark with the
//                    sage line-art ink-feather mark, .qm-cl-card form
//                    panel, sage CTA-tinted trust footer. Per Phase 2
//                    Batch F (clinician remodel).
//
// Every page passes its own form + inline links as `children`. Server-
// action wiring stays in the page-level form components, untouched.
//
// Subcomponents `AuthFieldLabel` + `AuthFieldError` keep their existing
// API and pick up the right typography per theme.

import type { ReactNode } from 'react';
import { Ic } from './icon';
import { QuillLogo } from './quill-logo';
import { ShaderBG } from './shader-bg';
import { WordMark } from './word-mark';

export type AuthShellTheme = 'legacy' | 'clinician';

export function AuthShell({
  eyebrow,
  title,
  subtitle,
  children,
  theme = 'legacy',
}: {
  /** Small mono all-caps line above the title. */
  eyebrow?: ReactNode;
  /** Serif title — pass JSX so the <em> italic-accent pattern works:
   *  `<>Sign <em>in</em></>` → "Sign *in*" with the accent color. */
  title: ReactNode;
  subtitle?: ReactNode;
  /** Form + inline nav links. Rendered inside the card. */
  children: ReactNode;
  /** Visual variant. Defaults to `'legacy'` to keep any unmigrated
   *  caller working; Clinician auth routes pass `'clinician'`. */
  theme?: AuthShellTheme;
}) {
  if (theme === 'clinician') {
    return <ClinicianAuthShell {...{ eyebrow, title, subtitle, children }} />;
  }
  return <LegacyAuthShell {...{ eyebrow, title, subtitle, children }} />;
}

// ─────────────────────────────────────────────────────────────────────
// Clinician variant — warm cream + sage line-art, per landing-and-
// recording.html mockup. Centered card, soft warm shadow, italic-serif
// accent in the headline.
// ─────────────────────────────────────────────────────────────────────

function ClinicianAuthShell({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      className="qm-cl-app"
      data-grain
      style={{
        minHeight: '100vh',
        width: '100%',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 20px',
      }}
    >
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          width: '100%',
          maxWidth: 440,
        }}
      >
        {/* Wordmark — Source Serif 4 "Quill" with the sage ink-feather
            mark from the landing mockup (header brand). */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            marginBottom: 28,
          }}
        >
          <InkFeatherMark size={28} />
          <span className="qm-cl-wordmark" style={{ fontSize: 22 }}>
            Quill
          </span>
        </div>

        {/* Form card — warm cream-card surface, 16px radius, soft shadow */}
        <div
          className="qm-cl-card"
          style={{
            padding: '32px 32px 30px',
            textAlign: 'left',
          }}
        >
          {eyebrow && (
            <div className="qm-cl-eyebrow" style={{ marginBottom: 10 }}>
              {eyebrow}
            </div>
          )}
          <h1
            className="qm-cl-serif"
            style={{
              margin: 0,
              fontSize: 34,
              fontWeight: 400,
              letterSpacing: '-0.015em',
              lineHeight: 1.1,
              color: 'var(--ink)',
            }}
          >
            {title}
          </h1>
          {subtitle && (
            <p
              className="qm-cl-serif"
              style={{
                color: 'var(--ink-2)',
                marginTop: 10,
                marginBottom: 22,
                fontSize: 15,
                lineHeight: 1.55,
                fontStyle: 'italic',
              }}
            >
              {subtitle}
            </p>
          )}

          {children}
        </div>

        {/* Trust footer — quiet meta in DM Sans 11.5px */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 14,
            marginTop: 22,
            color: 'var(--ink-3)',
            fontSize: 11.5,
            fontFamily: 'var(--sans)',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Ic.shield width={13} height={13} />
            HIPAA ready
          </span>
          <span style={{ color: 'var(--ink-4)' }}>·</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Ic.lock width={13} height={13} />
            BAA included
          </span>
          <span style={{ color: 'var(--ink-4)' }}>·</span>
          <span>US-hosted</span>
        </div>
      </div>
    </div>
  );
}

/** The sage ink-feather mark from the landing mockup wordmark. Quill's
 *  lone bit of decoration on the auth surfaces. */
function InkFeatherMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M4 19c4 -1 7 -3.5 9.5 -7c1.5 -2 3 -3.5 5 -4.5c1.2 -0.6 2 -0.4 1.6 0.8c-0.7 2 -2.4 4.4 -4.6 6.4c-2.6 2.4 -5.6 4 -8.5 4.7c-1 0.2 -2.4 0.3 -3 -0.4z"
        stroke="#7AA68C"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="rgba(122,166,140,0.14)"
      />
      <path
        d="M4 19l3.5 -3"
        stroke="#7AA68C"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Legacy variant — preserved verbatim for any non-Clinician caller. Per
// Batch F decision, no caller exists today, but keeping the legacy path
// mirrors Batch A's `theme` prop pattern (defensive, removable later).
// ─────────────────────────────────────────────────────────────────────

function LegacyAuthShell({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      className="qm-app"
      style={{
        minHeight: '100vh',
        width: '100%',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 20px',
      }}
    >
      <ShaderBG intensity={0.9} />
      <div className="qm-noise" aria-hidden />

      {/* Faint mesh grid behind the glass card (HANDOFF source lines
         13–18) — 48px cells in violet, radial-masked to fade at the
         edges so it reads as "depth" not "graph paper". */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 1,
          opacity: 0.35,
          backgroundImage:
            'linear-gradient(rgba(139,92,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(139,92,255,0.06) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage:
            'radial-gradient(circle at 50% 45%, #000 0%, transparent 70%)',
          WebkitMaskImage:
            'radial-gradient(circle at 50% 45%, #000 0%, transparent 70%)',
        }}
      />

      <div
        style={{
          position: 'relative',
          zIndex: 3,
          width: '100%',
          maxWidth: 420,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            marginBottom: 28,
          }}
        >
          <QuillLogo size={30} />
          <WordMark size={20} />
        </div>

        <div
          className="qm-glass"
          style={{
            padding: '36px 34px',
            borderRadius: 20,
            textAlign: 'left',
            boxShadow: 'var(--shadow-2)',
          }}
        >
          {eyebrow && (
            <div className="qm-sectlabel" style={{ marginBottom: 8 }}>
              {eyebrow}
            </div>
          )}
          <h1
            className="qm-serif"
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 400,
              letterSpacing: '-0.02em',
              lineHeight: 1.1,
            }}
          >
            {title}
          </h1>
          {subtitle && (
            <p
              style={{
                color: 'var(--fg-3)',
                marginTop: 6,
                marginBottom: 24,
                fontSize: 13,
              }}
            >
              {subtitle}
            </p>
          )}

          {children}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 14,
            marginTop: 20,
            color: 'var(--fg-4)',
            fontSize: 11.5,
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Ic.shield width={13} height={13} />
            HIPAA ready
          </span>
          <span>·</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Ic.lock width={13} height={13} />
            BAA included
          </span>
          <span>·</span>
          <span>US-hosted</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Field subcomponents — shared between legacy + clinician auth pages.
// They opt into the right typography by reading from the surrounding
// scope: inside `.qm-cl-app` the bare-name CSS vars resolve to the
// Clinician palette; inside `.qm-app` they resolve to the legacy
// palette. So the components themselves stay theme-agnostic.
// ─────────────────────────────────────────────────────────────────────

/** Shared label used by auth form fields. In Clinician scope this picks
 *  up DM Sans + warm-charcoal ink. In legacy scope it stays JetBrains
 *  Mono uppercase. */
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
          fontSize: 11.5,
          color: 'var(--fg-3, var(--ink-3))',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          fontFamily: 'var(--mono)',
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
        fontSize: 12,
        color: 'var(--coral)',
      }}
    >
      {message}
    </p>
  );
}
