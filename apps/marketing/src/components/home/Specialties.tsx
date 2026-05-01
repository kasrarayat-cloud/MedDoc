/**
 * Specialty packs row — Linear V1 (Faithful).
 *
 * Centered eyebrow + Inter 600 heading + body copy + mono pill cluster.
 * Pills use the .qm-lin-pill primitive directly (defined in globals.css).
 */
const PILLS = [
  'Primary care',
  'Cardiology',
  'Pain management',
  'Urgent care',
  'Pediatrics',
  'Dermatology',
  'Psychiatry',
  'Orthopedics',
];

export function Specialties() {
  return (
    <section style={{ padding: '32px 0 96px' }}>
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">Tuned per specialty</div>
          <h2 className="section-title">Eight specialty templates. More every month.</h2>
          <p className="section-sub">
            Each template adapts to your charting shorthand and preferred note structure within
            the first five visits.
          </p>
        </div>
        <div
          className="reveal"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: 8,
            maxWidth: 720,
            margin: '0 auto',
          }}
        >
          {PILLS.map((p) => (
            <span key={p} className="qm-lin-pill">
              {p}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
