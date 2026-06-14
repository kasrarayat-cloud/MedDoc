'use client';

// C4 — ZERO-CHROME / NOTE-ONLY. The note fills the screen: no top bar, no rail, no visible Sign.
// A single floating affordance (bottom-right) is the only UI — it summons ONE calm sheet holding
// everything (patient, flagged items, coding, the Sign button), then dismisses back to a pure
// document. Even Sign is summoned on demand, never persistent chrome. (≠ C3, which keeps a header
// + visible Sign + pill always on screen.)
import { useEffect, useRef, useState } from 'react';
import { PatientMeta, SampleChip, NoteDoc, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { LANE, RX, VISIT } from './data';

export function C4Zen() {
  const r = useReview();
  const [open, setOpen] = useState(false);
  const count = r.blockingRx.length + r.pendingLane.length; // parity with C1/C3's pill count
  const closeRef = useRef<HTMLButtonElement>(null);
  const fabRef = useRef<HTMLButtonElement>(null);

  const close = () => {
    setOpen(false);
    fabRef.current?.focus(); // restore focus to the opener
  };

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <div className="c4 sc-app">
      <span className="c4-corner"><SampleChip /></span>

      <main className="c4-note">
        <header className="c4-masthead">
          <h1 className="c4-pt">{VISIT.patient}</h1>
          <p className="c4-meta">{VISIT.meta} · MRN {VISIT.mrn} · {VISIT.when}</p>
        </header>
        <NoteDoc />
      </main>

      {r.signed ? (
        <div className="c4-fab signed" aria-live="polite">✓ Signed</div>
      ) : (
        <button
          ref={fabRef}
          className={`c4-fab ${count > 0 ? 'has' : 'clear'}`}
          type="button"
          onClick={() => setOpen(true)}
          aria-expanded={open}
          aria-haspopup="dialog"
        >
          {count > 0 ? `Review & sign · ${count}` : 'Sign note'}
        </button>
      )}

      {open && <div className="c4-scrim" onClick={close} aria-hidden />}
      {open && (
        <div className="c4-sheet" role="dialog" aria-label="Review and sign" aria-modal="true">
          <div className="c4-sheet-head">
            <PatientMeta />
            <button ref={closeRef} className="sc-btn sc-btn-quiet" type="button" onClick={close} aria-label="Close">
              Close ✕
            </button>
          </div>
          <div className="c4-sheet-body">
            {RX.map((w) => (
              <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
            ))}
            {LANE.map((l) => (
              <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
            ))}
            <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
          </div>
          <div className="c4-sheet-foot">
            <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => { r.setSigned(true); setOpen(false); }} big />
          </div>
        </div>
      )}
    </div>
  );
}
