'use client';

// C2 — FOCUS / STEPPED. A calm guided sequence (Review → Resolve → Sign) shown as a slim top
// progress bar with ONE focused panel at a time, so there's always exactly one thing to do
// next and never 6 tabs. The Rx/lane resolution IS the middle step, so a blocker can't hide on
// a different tab. Billing is one quiet line at the sign step.
import { useState } from 'react';
import { PatientMeta, SampleChip, NoteDoc, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { LANE, RX } from './data';

const STEPS = ['Review note', 'Resolve flagged', 'Sign'];

export function C2Stepped() {
  const r = useReview();
  const [step, setStep] = useState(0);
  const canLeaveResolve = r.blockingRx.length === 0; // critical Rx must be overridden to advance

  return (
    <div className="c2 sc-app">
      <header className="c2-top sc-top">
        <div className="sc-top-l">
          <PatientMeta />
          <SampleChip />
        </div>
      </header>

      <ol className="c2-stepper" aria-label="Review steps">
        {STEPS.map((s, i) => (
          <li className={`c2-step ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`} key={s} aria-current={i === step ? 'step' : undefined}>
            <span className="c2-step-n">{i < step ? '✓' : i + 1}</span>
            <span className="c2-step-l">{s}</span>
          </li>
        ))}
      </ol>

      <div className="c2-panel sc-pane">
        {step === 0 && (
          <>
            <div className="sc-pane-head">
              <span className="sc-pane-title">Read the note</span>
            </div>
            <NoteDoc />
            <div className="c2-foot">
              <span className="c2-foot-hint">Edit anything that needs it, then continue.</span>
              <button className="sc-btn sc-btn-sign" type="button" onClick={() => setStep(1)}>
                Looks right — continue
              </button>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <div className="sc-pane-head">
              <span className="sc-pane-title">Resolve flagged items</span>
              {!canLeaveResolve && <span className="c2-count">1 must be resolved</span>}
            </div>
            <div className="c2-resolve">
              {RX.map((w) => (
                <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
              ))}
              {LANE.map((l) => (
                <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
              ))}
            </div>
            <div className="c2-foot">
              <button className="sc-btn sc-btn-quiet" type="button" onClick={() => setStep(0)}>
                Back
              </button>
              <button className="sc-btn sc-btn-sign" type="button" disabled={!canLeaveResolve} onClick={() => setStep(2)}>
                {canLeaveResolve ? 'All clear — continue' : 'Override the critical interaction first'}
              </button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="sc-pane-head">
              <span className="sc-pane-title">Sign &amp; finish</span>
            </div>
            <div className="c2-summary">
              <div className="c2-sum-row">
                <span className="c2-sum-k">Note</span>
                <span className="c2-sum-v">SOAP · 4 sections</span>
              </div>
              <div className="c2-sum-row">
                <span className="c2-sum-k">Flags</span>
                <span className="c2-sum-v">{r.blockingRx.length === 0 ? 'All resolved' : 'unresolved'}</span>
              </div>
              <div className="c2-sum-row">
                <span className="c2-sum-k">Coding</span>
                <div className="c2-sum-v">
                  <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
                </div>
              </div>
              <div className="c2-sum-row">
                <span className="c2-sum-k">Send</span>
                <span className="c2-sum-v c2-exports">
                  PDF · Copy for Epic <button className="sc-btn sc-btn-quiet" type="button">Change</button>
                </span>
              </div>
            </div>
            <div className="c2-foot">
              <button className="sc-btn sc-btn-quiet" type="button" onClick={() => setStep(1)}>
                Back
              </button>
              <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
