/**
 * Trust strip — Phase 7 v6 (Apple Product).
 *
 * Compact strip below hero: one-line claim left, 5 mono badge stacks right.
 * Hairline top + bottom rules.
 */
const BADGES = [
  { top: 'HIPAA', bottom: 'Aligned' },
  { top: 'BAA', bottom: 'On request' },
  { top: 'Encrypted', bottom: 'By default' },
  { top: 'AES-256', bottom: 'Transit + at rest' },
  { top: 'US-hosted', bottom: 'AWS us-east-1' },
];

export function Trust() {
  return (
    <section className="trust-strip">
      <div className="container">
        <div className="trust-grid">
          <div className="trust-claim">Compliant by default. Private by design.</div>
          <div className="trust-badges">
            {BADGES.map((b) => (
              <div key={b.top} className="trust-badge">
                <div className="top">{b.top}</div>
                <div className="bottom">{b.bottom}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
