'use client';

// C3 — NOTE-ONLY + ON-DEMAND DRAWER. Maximal note-primacy: the note is full-width and alone,
// with just the Sign button and a single "N to review" count pill. All secondary work
// (Rx, suggestions, coding) lives in a dismissible right drawer opened from that pill — closed
// by default, so the note is the only thing on screen until the doctor chooses to review.
import { useState, useEffect, useRef } from 'react';
import { PatientMeta, SampleChip, NoteDoc, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { LANE, RX } from './data';

export function C3Drawer() {
  const r = useReview();
  const [open, setOpen] = useState(false);
  const count = r.blockingRx.length + r.pendingLane.length;
  const pillLabel = count > 0 ? `${count} to review` : 'Reviewed ✓';
  const closeRef = useRef<HTMLButtonElement>(null);

  // when the drawer opens, move focus into it and let Escape close it
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <div className="c3 sc-app">
      <header className="c3-top sc-top">
        <div className="sc-top-l">
          <PatientMeta />
          <SampleChip />
        </div>
        <div className="sc-top-r">
          <button className={`c3-pill ${count > 0 ? 'has' : ''}`} type="button" onClick={() => setOpen(true)} aria-expanded={open}>
            {pillLabel}
          </button>
          <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} />
        </div>
      </header>

      <main className="c3-note sc-pane">
        <div className="sc-pane-head">
          <span className="sc-pane-title">Note · SOAP</span>
          <button className="sc-btn sc-btn-quiet" type="button">Copy</button>
        </div>
        <NoteDoc />
      </main>

      {open && <div className="c3-scrim" onClick={() => setOpen(false)} aria-hidden />}
      <aside className={`c3-drawer ${open ? 'open' : ''}`} aria-label="Flagged items to review" aria-hidden={!open}>
        <div className="c3-drawer-head">
          <span className="sc-rail-title">To review</span>
          <button ref={closeRef} className="sc-btn sc-btn-quiet" type="button" onClick={() => setOpen(false)} aria-label="Close panel">
            Close ✕
          </button>
        </div>
        <div className="c3-drawer-body">
          {RX.map((w) => (
            <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
          ))}
          {LANE.map((l) => (
            <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
          ))}
          <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
        </div>
      </aside>

      <div className="sc-mobilebar c3-mobilebar">
        <button className={`c3-pill ${count > 0 ? 'has' : ''}`} type="button" onClick={() => setOpen(true)}>
          {pillLabel}
        </button>
        <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
      </div>
    </div>
  );
}
