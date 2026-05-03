/**
 * Compare — Phase 7 v6 (Apple Product).
 *
 * Bold 5-column compare table with sage glow + heavy dark shadow. Mobile
 * collapses to 2 columns (label + QuillMD only) via landing.css media query.
 */
type Cell = {
  value: string;
  isStrong?: boolean;
  mark?: 'yes' | 'no';
  className?: string;
};

type Row = {
  label: string;
  us: Cell;
  abridge: Cell;
  suki: Cell;
  nabla: Cell;
};

const ROWS: Row[] = [
  {
    label: 'Monthly price',
    us: { value: '$49 flat', isStrong: true },
    abridge: { value: '$250–500+' },
    suki: { value: '$400+' },
    nabla: { value: 'Custom' },
  },
  {
    label: 'Self-serve signup',
    us: { value: '2-min onboarding', mark: 'yes' },
    abridge: { value: 'Sales required', mark: 'no' },
    suki: { value: 'Sales required', mark: 'no' },
    nabla: { value: 'Sales required', mark: 'no' },
  },
  {
    label: 'Built for solo doctors',
    us: { value: 'From day one', mark: 'yes' },
    abridge: { value: 'Enterprise first', mark: 'no' },
    suki: { value: 'Enterprise first', mark: 'no' },
    nabla: { value: 'Enterprise first', mark: 'no' },
  },
  {
    label: 'Per-visit fees',
    us: { value: 'Unlimited', mark: 'yes' },
    abridge: { value: 'Sometimes' },
    suki: { value: 'Yes' },
    nabla: { value: 'Yes' },
  },
  {
    label: 'Contract term',
    us: { value: 'None. Cancel anytime.', isStrong: true },
    abridge: { value: '12 months' },
    suki: { value: '12 months' },
    nabla: { value: '12+ months' },
  },
];

function UsCell({ cell }: { cell: Cell }) {
  const className = cell.isStrong ? 'compare-cell us strong' : 'compare-cell us';
  return (
    <div className={className}>
      {cell.mark === 'yes' && <span className="check">✓</span>}
      {cell.value}
    </div>
  );
}

function OtherCell({ cell }: { cell: Cell }) {
  const className = cell.mark === 'no' ? 'compare-cell no' : 'compare-cell';
  return (
    <div className={className}>
      {cell.mark === 'no' && <span className="x">✗</span>}
      {cell.value}
    </div>
  );
}

export function Compare() {
  return (
    <section className="stage" id="compare">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">03 / Difference</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          Built for the doctor, <span className="quiet">not the health system.</span>
        </h2>
        <p className="stage-sub reveal delay-2">
          Other scribes are sold to hospitals with procurement officers. QuillMD is sold to you —
          at a price that makes sense for one clinician.
        </p>

        <div className="compare-table reveal delay-3">
          <div className="compare-row head">
            <div className="compare-cell" />
            <div className="compare-cell us">QuillMD</div>
            <div className="compare-cell">Abridge</div>
            <div className="compare-cell">Suki</div>
            <div className="compare-cell">Nabla</div>
          </div>
          {ROWS.map((row) => (
            <div key={row.label} className="compare-row">
              <div className="compare-cell label">{row.label}</div>
              <UsCell cell={row.us} />
              <OtherCell cell={row.abridge} />
              <OtherCell cell={row.suki} />
              <OtherCell cell={row.nabla} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
