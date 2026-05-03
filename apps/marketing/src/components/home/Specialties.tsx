/**
 * Specialties — Phase 7 v6 (Apple Product).
 *
 * Centred stage with 8 huge rounded pills. Hover lifts each pill with sage
 * tint background + glow.
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
    <section className="stage" id="specialties">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">Tuned per specialty</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          Eight specialty templates. <span className="quiet">More every month.</span>
        </h2>
        <p className="stage-sub reveal delay-2">
          Each template adapts to your charting shorthand and preferred note structure within the
          first five visits.
        </p>

        <div className="specs-pills reveal delay-3">
          {PILLS.map((p) => (
            <span key={p} className="qm-pill">
              {p}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
