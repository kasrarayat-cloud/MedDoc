import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * Pricing card — Linear V1 (Faithful).
 *
 * Single sage-bordered card on dark canvas, $49 amount + 2-col feature
 * checklist, sage primary CTA + mono "14 days free" caption. Mirrors
 * landing-v1.html lines 998-1028; the .price-card / .price-list structure
 * is already styled in Linear V1 via landing-v1.html's design language —
 * we re-author with inline styles here since landing.css doesn't yet
 * carry .price-card / .price-list rules (no need to add new CSS classes).
 */
const FEATURES = [
  'Unlimited visits, no per-note caps',
  'Real-time SOAP drafting',
  'ICD-10 and CPT recommendations',
  'Specialty packs (all 12)',
  'HIPAA BAA, on file',
  'US-hosted infrastructure',
  'Cmd-K command palette',
  'EHR-formatted exports (Epic, Athena, Cerner, eCW)',
  'DOCX and PDF generation',
  'Email and Slack support',
];

function CheckDot() {
  return (
    <span
      style={{
        flexShrink: 0,
        width: 14,
        height: 14,
        marginTop: 4,
        borderRadius: '50%',
        background: 'var(--color-linear-sage-tint)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg
        width="9"
        height="9"
        viewBox="0 0 14 14"
        fill="none"
        stroke="var(--color-linear-sage)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="3 7.5 6 10 11 4.5" />
      </svg>
    </span>
  );
}

export function Pricing() {
  return (
    <section style={{ padding: '32px 0 96px' }} id="pricing">
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">06 / Pricing</div>
          <h2 className="section-title">One tier. Unlimited visits. No surprises.</h2>
        </div>

        <div
          className="reveal"
          style={{
            maxWidth: 540,
            margin: '0 auto',
            padding: 32,
            background: 'var(--color-linear-surface-1)',
            border: '1px solid var(--color-linear-border)',
            borderRadius: 14,
            position: 'relative',
            boxShadow:
              'inset 0 1px 0 rgba(122, 166, 140, 0.10), 0 30px 60px -30px rgba(0, 0, 0, 0.6)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 4,
              marginBottom: 6,
            }}
          >
            <span
              style={{
                fontSize: 36,
                fontWeight: 600,
                letterSpacing: '-0.022em',
                color: 'var(--color-linear-text)',
                fontFamily: 'var(--font-sans)',
              }}
            >
              $49
            </span>
            <span style={{ fontSize: 14, color: 'var(--color-linear-text-3)' }}>
              / month per physician
            </span>
          </div>
          <p
            style={{
              fontSize: 14,
              color: 'var(--color-linear-text-2)',
              marginBottom: 22,
            }}
          >
            Everything below, billed monthly. Cancel anytime.
          </p>
          <ul
            style={{
              listStyle: 'none',
              margin: '0 0 24px',
              padding: 0,
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '9px 18px',
            }}
          >
            {FEATURES.map((f) => (
              <li
                key={f}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                  lineHeight: 1.5,
                }}
              >
                <CheckDot />
                <span>{f}</span>
              </li>
            ))}
          </ul>
          <div
            style={{
              display: 'flex',
              gap: 12,
              alignItems: 'center',
              flexWrap: 'wrap',
            }}
          >
            <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg">
              Start your trial
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M5 12h14M13 5l7 7-7 7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </a>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10.5,
                color: 'var(--color-linear-text-3)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              14 days free · no card
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
