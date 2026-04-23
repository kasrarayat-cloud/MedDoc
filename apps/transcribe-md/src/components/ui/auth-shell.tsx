// HANDOFF §2.2 (SignInScreen visual) — shared shell for every auth route
// (login, signup, forgot-password, reset-password, check-email). Each
// page passes its own form + inline links as `children`; the shell owns
// the .qm-app wrapper, louder ShaderBG (intensity=0.9 per §2.1), mesh-
// grid underlay, QuillLogo + WordMark, the serif-italic title pattern
// (§1.2), and the HIPAA / BAA / US-hosted trust chips footer.

import type { ReactNode } from 'react';
import { Ic } from './icon';
import { QuillLogo } from './quill-logo';
import { ShaderBG } from './shader-bg';
import { WordMark } from './word-mark';

export function AuthShell({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  /** Small mono all-caps line above the title. */
  eyebrow?: ReactNode;
  /** Serif title — pass JSX so the <em> italic-accent pattern works:
   *  `<>Sign <em>in</em></>` → "Sign *in*" with the accent color. */
  title: ReactNode;
  subtitle?: ReactNode;
  /** Form + inline nav links. Rendered inside the glass card. */
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

/** Shared mono-uppercase label used by auth form fields. */
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
          color: 'var(--fg-3)',
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
