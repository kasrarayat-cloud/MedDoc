'use client';

// C1 — GRAMMARLY MODEL. The note is the primary document (left, wide). ONE calm right rail
// holds the secondary work as cards: Rx warnings (critical carries override-to-sign), AI
// suggestions (adopt/dismiss), and a collapsed Coding panel. ONE Sign button (top-right +
// sticky on mobile); sign-blockers surface inline beside it.
import { PatientMeta, SampleChip, NoteDoc, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { LANE, RX } from './data';

export function C1Grammarly() {
  const r = useReview();
  const reviewCount = r.blockingRx.length + r.pendingLane.length;
  return (
    <div className="c1 sc-app">
      <header className="c1-top sc-top">
        <div className="sc-top-l">
          <PatientMeta />
          <SampleChip />
        </div>
        <div className="sc-top-r">
          <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} />
        </div>
      </header>

      <div className="c1-body">
        <main className="c1-note sc-pane">
          <div className="sc-pane-head">
            <span className="sc-pane-title">Note · SOAP</span>
            <button className="sc-btn sc-btn-quiet" type="button">Copy</button>
          </div>
          <NoteDoc />
        </main>

        <aside className="c1-rail">
          <div className="sc-rail-head">
            <span className="sc-rail-title">To review</span>
            {reviewCount > 0 && <span className="sc-rail-count">{reviewCount}</span>}
          </div>
          {RX.map((w) => (
            <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
          ))}
          {LANE.map((l) => (
            <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
          ))}
          <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
        </aside>
      </div>

      <div className="sc-mobilebar">
        <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
      </div>
    </div>
  );
}
