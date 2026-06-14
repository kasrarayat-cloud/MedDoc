'use client';

// C10 — DASHBOARD / SUMMARY-FIRST. Opens on a one-glance readiness view: status tiles (note,
// interactions, suggestions, coding) plus a plain "what's left" line and the single Sign. The
// blocker is resolved right here from the summary; the full note is a drill-in, not the default.
// The decision leads, the document follows. (≠ everyone else, where the note is primary on load.)
import { useState } from 'react';
import { PatientMeta, SampleChip, NoteDoc, LaneCard, RxCard, EmPanel, SignButton, useReview } from './parts';
import { LANE, RX, SOAP, EM } from './data';

export function C10Summary() {
  const r = useReview();
  const [view, setView] = useState<'summary' | 'note'>('summary');
  const [showRx, setShowRx] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const critical = RX.find((w) => w.severity === 'critical')!;
  const info = RX.filter((w) => w.severity !== 'critical');
  const critOk = r.overrides.has(critical.id);

  const tiles = [
    { k: 'note', label: 'Note', value: `${SOAP.length} sections`, state: 'ok' as const },
    { k: 'rx', label: 'Interactions', value: critOk ? 'resolved' : '1 critical', state: critOk ? ('ok' as const) : ('warn' as const) },
    { k: 'sug', label: 'Suggestions', value: r.pendingLane.length ? `${r.pendingLane.length} pending` : 'reviewed', state: r.pendingLane.length ? ('info' as const) : ('ok' as const) },
    { k: 'coding', label: 'Coding', value: r.bumpApplied ? EM.suggested : EM.current, state: r.bumpApplied && !r.emConfirmed ? ('warn' as const) : ('ok' as const) },
  ];

  return (
    <div className="c10 sc-app">
      <header className="c10-top sc-top">
        <div className="sc-top-l"><PatientMeta /><SampleChip /></div>
        <div className="c10-viewtabs" role="tablist" aria-label="View">
          <button role="tab" aria-selected={view === 'summary'} className={`c10-vtab ${view === 'summary' ? 'on' : ''}`} type="button" onClick={() => setView('summary')}>Summary</button>
          <button role="tab" aria-selected={view === 'note'} className={`c10-vtab ${view === 'note' ? 'on' : ''}`} type="button" onClick={() => setView('note')}>Full note</button>
        </div>
      </header>

      {view === 'summary' ? (
        <div className="c10-dash">
          <div className="c10-tiles">
            {tiles.map((t) => (
              <div className={`c10-tile c10-${t.state}`} key={t.k}>
                <span className="c10-tile-dot" aria-hidden />
                <span className="c10-tile-label">{t.label}</span>
                <span className="c10-tile-value">{t.value}</span>
              </div>
            ))}
          </div>

          <div className="c10-ready">
            <div className="c10-ready-l">
              <span className="c10-ready-head">{r.canSign ? 'Ready to sign.' : `${r.blockers.length} item${r.blockers.length === 1 ? '' : 's'} to resolve`}</span>
              <span className="c10-ready-sub">{r.canSign ? 'All flags handled — review the full note any time.' : r.blockers[0]}</span>
            </div>
            <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
          </div>

          {!critOk && (
            <div className="c10-resolve">
              <button className="c10-row-head" type="button" aria-expanded={showRx} onClick={() => setShowRx((s) => !s)}>
                <span className="sc-sev sc-sev-critical">Critical</span>
                <span className="c10-row-text">Resolve the amlodipine × simvastatin interaction</span>
                <span className="c10-chev" aria-hidden>{showRx ? '▾' : '▸'}</span>
              </button>
              {showRx && <RxCard warn={critical} overridden={critOk} onOverride={r.override} />}
            </div>
          )}

          <div className="c10-resolve">
            <button className="c10-row-head" type="button" aria-expanded={showMore} onClick={() => setShowMore((s) => !s)}>
              <span className="c10-mini">Suggestions, other flags &amp; coding</span>
              <span className="c10-chev" aria-hidden>{showMore ? '▾' : '▸'}</span>
            </button>
            {showMore && (
              <div className="c10-resolve-body">
                {LANE.map((l) => (
                  <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
                ))}
                {info.map((w) => (
                  <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
                ))}
                <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
              </div>
            )}
          </div>
        </div>
      ) : (
        <main className="c10-note sc-pane">
          <div className="sc-pane-head">
            <span className="sc-pane-title">Note · SOAP</span>
            <button className="sc-btn sc-btn-quiet" type="button" onClick={() => setView('summary')}>← Back to summary</button>
          </div>
          <NoteDoc />
        </main>
      )}

      <div className="sc-mobilebar">
        <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
      </div>
    </div>
  );
}
