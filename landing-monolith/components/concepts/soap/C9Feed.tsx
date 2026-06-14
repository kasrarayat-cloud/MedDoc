'use client';

// C9 — CARD / FEED. One vertical column, no rail and no tabs. The visit reads top to bottom: a
// patient header, each SOAP section as a card, a divider, then the flagged items as inline cards in
// reading order (right where the plan that triggered them sits), then coding, then the ONE Sign
// card at the very bottom. One scroll resolves the whole visit. (≠ C1's two-column note+rail.)
import { PatientMeta, SampleChip, NoteSection, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { SOAP, LANE, RX } from './data';

export function C9Feed() {
  const r = useReview();
  return (
    <div className="c9 sc-app">
      <div className="c9-feed">
        <header className="c9-card c9-head">
          <PatientMeta />
          <SampleChip />
        </header>

        {SOAP.map((s) => (
          <section className="c9-card c9-sec" key={s.tag}>
            <NoteSection s={s} />
          </section>
        ))}

        <div className="c9-divider"><span>Before you sign</span></div>

        {RX.map((w) => (
          <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
        ))}
        {LANE.map((l) => (
          <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
        ))}
        <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />

        <section className="c9-card c9-signcard">
          <span className="c9-sign-title">{r.canSign ? 'Everything looks resolved.' : 'A few things to resolve first.'}</span>
          <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
        </section>
      </div>
    </div>
  );
}
