'use client';

// C5 — SPLIT BEFORE/AFTER. Two panes side by side: the raw visit transcript (left) and the note
// assembling from it (right). Provenance IS the layout — hovering or focusing a note section lights
// the transcript lines it came from, and hovering a tagged transcript line lights its note section.
// Flagged items + the one Sign sit beneath the note. (≠ everything else: the source/output pairing
// is the structure.)
import { useState } from 'react';
import { PatientMeta, SampleChip, NoteSection, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { SOAP, TRANSCRIPT, LANE, RX } from './data';

const TAG_LABEL: Record<string, string> = { S: 'Subjective', O: 'Objective', A: 'Assessment', P: 'Plan' };

export function C5Split() {
  const r = useReview();
  const [lit, setLit] = useState<string | null>(null);

  return (
    <div className="c5 sc-app">
      <header className="c5-top sc-top">
        <div className="sc-top-l"><PatientMeta /><SampleChip /></div>
      </header>

      <div className="c5-body">
        <section className="c5-src" aria-label="Source transcript">
          <div className="c5-col-head"><span className="c5-col-title">Visit transcript</span><span className="c5-col-sub">what was said</span></div>
          <ol className="c5-lines">
            {TRANSCRIPT.map((u, i) => (
              <li
                key={i}
                className={`c5-line c5-${u.who} ${u.tag ? 'has-tag' : ''} ${lit && u.tag === lit ? 'is-lit' : ''}`}
                onMouseEnter={() => u.tag && setLit(u.tag)}
                onMouseLeave={() => setLit(null)}
              >
                <span className="c5-who">{u.who === 'dr' ? 'Dr' : 'Pt'}</span>
                <span className="c5-said">{u.text}</span>
                {u.tag && <span className="c5-prov" aria-hidden>→ {u.tag}</span>}
              </li>
            ))}
          </ol>
        </section>

        <section className="c5-out" aria-label="Generated note">
          <div className="c5-col-head"><span className="c5-col-title">Note · SOAP</span><span className="c5-col-sub">assembled from the visit</span></div>
          <div className="c5-note">
            {SOAP.map((s) => (
              <div
                key={s.tag}
                className={`c5-sec ${lit === s.tag ? 'is-lit' : ''}`}
                onMouseEnter={() => setLit(s.tag)}
                onMouseLeave={() => setLit(null)}
                onFocus={() => setLit(s.tag)}
                onBlur={() => setLit(null)}
              >
                <NoteSection s={s} />
                <span className="c5-from" aria-hidden>{lit === s.tag ? `↤ from ${TAG_LABEL[s.tag]} lines` : 'hover to trace ↤'}</span>
              </div>
            ))}
          </div>

          <div className="c5-flags">
            <span className="sc-rail-title">Before you sign</span>
            {RX.map((w) => (
              <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
            ))}
            {LANE.map((l) => (
              <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
            ))}
            <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
          </div>

          <div className="c5-sign">
            <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
          </div>
        </section>
      </div>

      <div className="sc-mobilebar">
        <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
      </div>
    </div>
  );
}
