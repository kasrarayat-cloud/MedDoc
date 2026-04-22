import { Fragment } from 'react';

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
    label: 'Self‑serve signup',
    us: { value: '2‑min onboarding', mark: 'yes' },
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
    label: 'Per‑visit fees',
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
  return <span className={kind}>{kind === 'yes' ? '✓ ' : '✗ '}</span>;
}

export function Compare() {
  return (
    <section className="block compact" id="compare">
      <div className="container">
        <div className="sec-label">
          <span className="num">§ 03 / DIFFERENCE</span>
          <span>Vs. the enterprise scribes</span>
        </div>
        <div className="section-head reveal">
          <h2>
            Built for the doctor, <em>not the health system.</em>
          </h2>
          <p className="lede">
            Other scribes are sold to hospitals with procurement officers. QuillMD is sold to you —
            at a price that makes sense for one clinician.
          </p>
        </div>

        <div className="compare reveal">
          <div className="compare-grid">
            <div className="col-head" />
            <div className="col-head us">QuillMD</div>
            <div className="col-head">Abridge</div>
            <div className="col-head them2-h">Suki</div>
            <div className="col-head them3-h">Nabla</div>

            {ROWS.map((r) => (
              <Fragment key={r.label}>
                <div className="row-label">{r.label}</div>
                <div className="cell us">
                  <Mark kind={r.us.mark} />
                  {r.us.isStrong ? <strong>{r.us.value}</strong> : r.us.value}
                </div>
                <div className="cell">
                  <Mark kind={r.abridge.mark} />
                  {r.abridge.value}
                </div>
                <div className="cell them2">
                  <Mark kind={r.suki.mark} />
                  {r.suki.value}
                </div>
                <div className="cell them3">
                  <Mark kind={r.nabla.mark} />
                  {r.nabla.value}
                </div>
              </Fragment>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
