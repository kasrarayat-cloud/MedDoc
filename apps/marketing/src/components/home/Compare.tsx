import { Fragment } from 'react';

/**
 * Compare table — Linear V1 (Faithful).
 *
 * 4-column compare-grid (label + 3 competitor cols + us). Hairline-bordered,
 * surface-1 background, sage-bright "yes" + muted "no". Mirrors landing.css
 * .compare-grid; the .col-head + .row-label + .cell.us classes are already
 * mapped to Linear V1 tokens.
 */
type Row = {
  label: string;
  us: { value: string; isStrong?: boolean; mark?: 'yes' | 'no' };
  abridge: { value: string; mark?: 'yes' | 'no' };
  suki: { value: string; mark?: 'yes' | 'no' };
  nabla: { value: string; mark?: 'yes' | 'no' };
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

function Mark({ kind }: { kind?: 'yes' | 'no' }) {
  if (!kind) return null;
  return <span>{kind === 'yes' ? '✓ ' : '✗ '}</span>;
}

export function Compare() {
  return (
    <section className="compare" id="compare">
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">03 / Difference</div>
          <h2 className="section-title">Built for the doctor, not the health system.</h2>
          <p className="section-sub">
            Other scribes are sold to hospitals with procurement officers. QuillMD is sold to
            you — at a price that makes sense for one clinician.
          </p>
        </div>

        <div className="compare-grid reveal">
          <div className="cell head" />
          <div className="cell head brand">QuillMD</div>
          <div className="cell head">Abridge</div>
          <div className="cell head">Suki</div>
          <div className="cell head">Nabla</div>

          {ROWS.map((r) => (
            <Fragment key={r.label}>
              <div className="cell row-label">{r.label}</div>
              <div className={r.us.mark === 'yes' ? 'cell yes' : 'cell'}>
                <Mark kind={r.us.mark} />
                {r.us.isStrong ? <strong>{r.us.value}</strong> : r.us.value}
              </div>
              <div className={r.abridge.mark === 'no' ? 'cell no' : 'cell'}>
                <Mark kind={r.abridge.mark} />
                {r.abridge.value}
              </div>
              <div className={r.suki.mark === 'no' ? 'cell no' : 'cell'}>
                <Mark kind={r.suki.mark} />
                {r.suki.value}
              </div>
              <div className={r.nabla.mark === 'no' ? 'cell no' : 'cell'}>
                <Mark kind={r.nabla.mark} />
                {r.nabla.value}
              </div>
            </Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}
