// Phase 5 — Linear V1 Faithful auth shell.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (chrome
// tokens), landing-v1.html (sage-glow accent on a darker right pane).
//
// Split-screen on dark canvas:
//   - Left pane (linear-bg): brand wordmark + form card
//   - Right pane (linear-surface-1, hidden < 980px): subtle sage glow
//     accent with HIPAA / encryption / US-hosted trust strip in mono.
//
// 2026-07-29: "BAA included" was removed from this strip. Read the way a
// customer reads it, it promises QuillMD will sign a Business Associate
// Agreement with them — which QuillMD may well offer, but §164.308(b) first
// requires BAAs with its OWN subcontractors handling PHI, and Deepgram (raw
// patient audio) and the VPS host (every row of PHI) are unsigned. Restore it
// the day those two are countersigned; see docs/BAA_CHECKLIST.md.
//
// It was replaced with "Audit-logged", NOT the obvious "Encrypted at rest".
// Checked before writing it: Postgres does sit on a LUKS volume
// (/mnt/pgdata-encrypted), but MinIO — which holds the PATIENT AUDIO — is on an
// ordinary docker volume on the root filesystem. A blanket encryption claim
// would have replaced one overclaim with another. Every mutation writing an
// audit row is verified, live, and unambiguous.
//
// All Phase 4 cinematic photo-band machinery is gone. The `cinematic` prop and
// the `AuthShellTheme` / `AuthShellCinematic` types survive it, and the runtime
// ignores both.
//
// ⚠️ CORRECTED BY C1-d: this note used to say they were "kept for back-compat
// with login/page.tsx etc. that still pass them". Nothing passes them. All six
// auth pages were checked (`theme=` / `cinematic=` → no hits, against a control
// of `eyebrow=` hitting all six), and `AuthShellTheme` / `AuthShellCinematic`
// have no consumer anywhere outside this file. They are dead, not compatible —
// and a comment asserting a caller that does not exist is the reason the next
// reader stops looking. Item F retires the old skin and takes them with it.

import type { ReactNode } from 'react';
import { isSkinBeta } from '@/config/skin-beta';
import { isSkinRounds } from '@/config/skin-rounds';
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
  // ── C3 calm-skin auth (Stage 4, flag-gated) ───────────────────────────────
  // SKIN-ONLY: a re-skin of the auth chrome only. The split-screen shell
  // collapses to one quiet centered card on the dark canvas (matching
  // /concepts/signin). The form `children` — the real LoginForm / SignupForm /
  // reset forms carrying the next-auth signIn + server-action flows — are
  // rendered verbatim and UNTOUCHED. No auth logic is gated or changed. Flag
  // OFF → the split-screen shell below renders, byte-identical.
  if (isSkinBeta()) {
    return (
      // ── THE ROUNDS BRIDGE, on the C3 branch only ──────────────────────────
      // A BRIDGE rather than a fork, and that is the honest treatment here:
      // this branch carries no inline styles at all — its whole appearance is
      // `globals.css:5233-5330`, which reads `--color-linear-*`. Redeclaring
      // those custom properties on this node retints the card AND every inline
      // object in the form beneath it, because custom properties resolve at
      // computed-value time and inherit. `rounds-tokens.css` § C1-d carries the
      // shape and the three contrast forks the bridge cannot reach.
      //
      // Flag-OFF: `isSkinRounds()` is build-time, so this collapses to the bare
      // `qm-c3-auth` string and nothing moves.
      <div className={isSkinRounds() ? 'qm-c3-auth qm-rounds-host qm-rounds-auth' : 'qm-c3-auth'}>
        <main className="qm-c3-auth-card">
          <div className="qm-c3-auth-brand">
            <span aria-hidden className="qm-c3-auth-mark">
              Q
            </span>
            <span className="qm-c3-auth-word">QuillMD</span>
          </div>
          {eyebrow && <div className="qm-c3-auth-eyebrow">{eyebrow}</div>}
          <h1 className="qm-c3-auth-h qm-auth-em-host">
            <AuthTitle>{title}</AuthTitle>
          </h1>
          {subtitle && <p className="qm-c3-auth-sub">{subtitle}</p>}
          {/* ⚠️ THE SECOND CLASS IS THE GATE, NOT DECORATION. Gate C decides
              ownership by climbing to the nearest ancestor-or-self carrying ANY
              class and testing it for `qm-rounds-`. The five auth forms are
              inline-styled with almost no classes, so every violation inside
              them resolves UP — and it stops HERE. Without `qm-rounds-authform`
              the nearest classed ancestor is `qm-c3-auth-form`, which does not
              match, so every input, label and error in the form would be
              classified "inherited" and merely reported. `violations: []` while
              measuring nothing — trap 3, on the surface it matters most. */}
          <div
            className={
              isSkinRounds()
                ? 'qm-c3-auth-form qm-rounds-authform'
                : 'qm-c3-auth-form'
            }
          >
            {children}
          </div>
          <div className="qm-c3-auth-trust">
            <span>
              <Ic.shield width={12} height={12} aria-hidden />
              HIPAA ready
            </span>
            <span aria-hidden>·</span>
            <span>
              <Ic.lock width={12} height={12} aria-hidden />
              Audit-logged
            </span>
            <span aria-hidden>·</span>
            <span>US-hosted</span>
          </div>
        </main>
      </div>
    );
  }

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
                Audit-logged
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
        className={isSkinRounds() ? 'qm-rounds-label' : undefined}
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
      {/* ⚠️ `hint` IS A SIBLING OF THE LABEL AND MUST STAY ONE. Folding it
          inside — the obvious move when restyling a two-item flex row — is the
          single edit in this file that breaks the whole suite. Playwright's
          `getByLabel('Password', { exact: true })` matches the label's
          whitespace-normalised text against the WHOLE string; /login passes
          "Forgot?" through this prop, so folding it makes that text
          "Password Forgot?" and reds every login in the suite — seven spec
          files, via `helpers/auth.ts` and `helpers/signup.ts`. Pinned by
          `gate-c1d-auth`.
          Casing is safe to change: the engine reads DOM text, not the
          accessible name, so `textTransform: uppercase` above is invisible to
          it. Adding an `aria-label` to a field is NOT safe — it would override
          the visible label with no HTML a reviewer would flag. */}
      {hint}
    </div>
  );
}

/** Inline field-level error message (role="alert"). */
export function AuthFieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    // The colour needs no fork: `--color-linear-coral` already bridges to
    // `--rounds-critical-on-dark`, the text-safe variant (7.70:1 on surface-1).
    // The class is here for OWNERSHIP — this is the only `role="alert"`
    // reachable on /signup, so it is the node the pack scopes its refusal
    // assertion to, and it must be gate-visible when it renders.
    <p
      role="alert"
      className={isSkinRounds() ? 'qm-rounds-error' : undefined}
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
