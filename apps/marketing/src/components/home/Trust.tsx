const BADGES = [
  { label: 'HIPAA', sub: 'Aligned' },
  { label: 'BAA', sub: 'On request' },
  { label: 'Encrypted', sub: 'By default' },
  { label: 'AES‑256', sub: 'Transit + at rest' },
  { label: 'US‑hosted', sub: 'AWS us‑east‑1' },
];

export function Trust() {
  return (
    <section className="trust">
      <div className="container trust-inner">
        <div className="trust-title">
          Compliant by default.
          <br />
          Private by design.
        </div>
        <div className="trust-badges">
          {BADGES.map((b) => (
            <div key={b.label} className="trust-badge">
              <span className="label">{b.label}</span>
              <span className="sub">{b.sub}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
