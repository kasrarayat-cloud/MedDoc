/**
 * Trust badges row — Linear V1 (Faithful).
 *
 * Below-fold compliance/encryption strip. Linear V1 doesn't have a discrete
 * trust section in the mockup, but we keep this surface as a low-key mono
 * row of compliance pills + caption — reads like the kind of small-text
 * trust footer Linear uses on its enterprise landing pages.
 */
const BADGES = [
  { label: 'HIPAA', sub: 'Aligned' },
  { label: 'BAA', sub: 'On request' },
  { label: 'Encrypted', sub: 'By default' },
  { label: 'AES-256', sub: 'Transit + at rest' },
  { label: 'US-hosted', sub: 'AWS us-east-1' },
];

export function Trust() {
  return (
    <section
      style={{
        padding: '32px 0 64px',
        borderTop: '1px solid var(--color-linear-hairline)',
        borderBottom: '1px solid var(--color-linear-hairline)',
      }}
    >
      <div className="container">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            alignItems: 'center',
            gap: 32,
          }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: 'var(--color-linear-text)',
              letterSpacing: '-0.005em',
              maxWidth: 240,
              lineHeight: 1.4,
            }}
          >
            Compliant by default. Private by design.
          </div>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 28,
              justifyContent: 'flex-end',
            }}
          >
            {BADGES.map((b) => (
              <div
                key={b.label}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--color-linear-text-2)',
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                  }}
                >
                  {b.label}
                </span>
                <span
                  style={{
                    fontSize: 10.5,
                    color: 'var(--color-linear-text-3)',
                    letterSpacing: '0.04em',
                  }}
                >
                  {b.sub}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
