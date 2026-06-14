'use client';

// C8 — TWO-PANE READING VIEW + MARGIN PINS. The note reads like a clean editorial document; every
// flagged item is a numbered footnote pin in the right margin, anchored to where it applies (the
// Plan carries inline reference markers). Click a pin — or its inline marker — to resolve it in
// place. One Sign sits quietly top-right; the document leads. (≠ C1's always-open stacked rail:
// here the flags are collapsed footnotes tied to document positions.)
import { useState } from 'react';
import { PatientMeta, SampleChip, NoteSection, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { SOAP, LANE, RX } from './data';
import type { LaneItem, RxWarn } from './data';

type Pin = { key: string; n: number; label: string; kind: 'rx' | 'lane' | 'coding'; warn?: RxWarn; item?: LaneItem; done: boolean };

export function C8Margin() {
  const r = useReview();
  const [open, setOpen] = useState<string | null>(null);

  const pins: Pin[] = [
    ...RX.map((w) => ({
      key: w.id,
      kind: 'rx' as const,
      label: w.severity === 'critical' ? 'Interaction' : 'Interaction (info)',
      warn: w,
      done: w.severity === 'critical' ? r.overrides.has(w.id) : true,
    })),
    ...LANE.map((l) => ({
      key: l.id,
      kind: 'lane' as const,
      label: l.kind === 'held' ? 'Held suggestion' : 'Suggestion',
      item: l,
      done: r.laneState(l.id) !== undefined,
    })),
    { key: 'coding', kind: 'coding' as const, label: 'Coding', done: r.bumpApplied ? r.emConfirmed : true },
  ].map((p, i) => ({ ...p, n: i + 1 }));

  const toggle = (k: string) => setOpen((o) => (o === k ? null : k));

  return (
    <div className="c8 sc-app">
      <header className="c8-top sc-top">
        <div className="sc-top-l"><PatientMeta /><SampleChip /></div>
        <div className="sc-top-r">
          <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} />
        </div>
      </header>

      <div className="c8-body">
        <article className="c8-doc">
          {SOAP.map((s) => (
            <div key={s.tag} className="c8-sec">
              <NoteSection s={s} />
              {s.tag === 'P' && (
                <p className="c8-refs">
                  <span className="c8-refs-label" aria-hidden>flagged ·</span>
                  {pins.map((p) => (
                    <button
                      key={p.key}
                      className={`c8-ref ${open === p.key ? 'on' : ''} ${p.done ? 'done' : ''}`}
                      type="button"
                      onClick={() => toggle(p.key)}
                      aria-label={`${p.label} — footnote ${p.n}`}
                    >
                      {p.n}
                    </button>
                  ))}
                </p>
              )}
            </div>
          ))}
        </article>

        <aside className="c8-margin" aria-label="Flagged items">
          {pins.map((p) => (
            <div key={p.key} className={`c8-pin ${open === p.key ? 'open' : ''} ${p.done ? 'done' : ''}`}>
              <button className="c8-pin-head" type="button" onClick={() => toggle(p.key)} aria-expanded={open === p.key}>
                <span className={`c8-pin-n ${p.kind === 'rx' && p.warn?.severity === 'critical' && !p.done ? 'crit' : ''}`}>{p.done ? '✓' : p.n}</span>
                <span className="c8-pin-label">{p.label}</span>
              </button>
              {open === p.key && (
                <div className="c8-pin-body">
                  {p.kind === 'rx' && p.warn && <RxCard warn={p.warn} overridden={r.overrides.has(p.warn.id)} onOverride={r.override} />}
                  {p.kind === 'lane' && p.item && <LaneCard item={p.item} state={r.laneState(p.item.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />}
                  {p.kind === 'coding' && <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />}
                </div>
              )}
            </div>
          ))}
        </aside>
      </div>

      <div className="sc-mobilebar">
        <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
      </div>
    </div>
  );
}
