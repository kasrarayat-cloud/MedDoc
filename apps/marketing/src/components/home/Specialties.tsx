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
    <section className="specialties">
      <div className="container">
        <div className="sp-head reveal">
          <span className="eyebrow">Tuned per specialty</span>
          <h3>
            Eight <em>specialty templates.</em> More every month.
          </h3>
          <p>
            Each template adapts to your charting shorthand and preferred note structure within the
            first five visits.
          </p>
        </div>
        <div className="sp-grid reveal">
          {PILLS.map((p) => (
            <span key={p} className="sp-pill">
              {p}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
