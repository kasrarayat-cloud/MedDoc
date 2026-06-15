'use client';

// V1 — "READ DOWN TO SIGN". One column, full-width. The note reads like a clean document; a calm
// sticky SUMMARY BAR above it glances everything that needs attention; tapping a summary badge
// smooth-scrolls to that item rendered INLINE, full-width, BELOW the note (review → Rx → coding
// stack vertically — never beside the note). ONE Sign button is pinned at the bottom, always
// visible, with the active blocker named right next to it. Kills the side-by-side collision by
// never having a second column: secondary content lives in the vertical reading flow.
import { SampleChip, PatientMeta, NoteDoc, LaneCard, RxCard, SignButton } from '../soap/parts';
import { EmCardV2 } from './parts-v2';
import { useReviewV2 } from './engine';
import { VISIT, LANE, RX } from '../soap/data';

function scrollToId(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
}

export function V1ReadDown() {
  const r = useReviewV2();

  return (
    <div className="sc-app v2v1">
      <header className="sc-top">
        <div className="sc-top-l">
          <PatientMeta />
        </div>
        <div className="sc-top-r">
          <SampleChip />
        </div>
      </header>

      {/* Calm summary bar — one glanceable line + tappable badges. Always shows the gate state. */}
      <div className="v1-summary" role="region" aria-label="What needs attention before signing">
        <div className="v1-summary-in">
          {r.canSign ? (
            <span className="v1-sum-lead">
              <span className="v1-dot ok" aria-hidden />
              All checks cleared — ready to sign
            </span>
          ) : (
            <span className="v1-sum-lead">
              <span className="v1-dot warn" aria-hidden />
              {r.blockers.length} to resolve before signing
            </span>
          )}
          <div className="v1-badges">
            {r.attention.length === 0 ? (
              <span className="v1-badge done">Nothing pending</span>
            ) : (
              r.attention.map((a) => (
                <button
                  key={a.kind}
                  type="button"
                  className={`v1-badge ${a.level === 'block' ? (a.kind === 'rx' ? 'crit' : 'warn') : 'info'}`}
                  onClick={() => scrollToId(a.target)}
                  aria-label={`${a.full} — jump to it`}
                >
                  <span className="v1-badge-dot" aria-hidden />
                  {a.short}
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* The reading column — note first, then resolve sections stacked full-width below it. */}
      <div className="v1-doc">
        <article className="v1-note">
          <div className="v1-masthead">
            <h1 className="v1-pt-name">{VISIT.patient}</h1>
            <p className="v1-pt-meta">
              {VISIT.meta} · MRN {VISIT.mrn} · {VISIT.when}
            </p>
          </div>
          <NoteDoc />
        </article>

        {/* Review (AI suggestions) — recommended, not gating, but always visible. */}
        <section id="v2-review" className="v1-block" aria-label="AI suggestions to review">
          <div className="v1-block-head">
            <span className="v1-block-kicker">Review</span>
            <h2 className="v1-block-title">AI suggestions</h2>
            <span className="v1-block-count">
              {r.pendingLane.length ? `${r.pendingLane.length} to review` : 'all reviewed'}
            </span>
          </div>
          <p className="v1-block-sub">
            Kept out of the note until you adopt them. Adopting adds the line as your own attestation.
          </p>
          <div className="v1-stack">
            {LANE.map((l) => (
              <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
            ))}
          </div>
        </section>

        {/* Rx safety — the critical interaction is a HARD blocker. */}
        <section id="v2-rx" className="v1-block v1-block-rx" aria-label="Prescription safety">
          <div className="v1-block-head">
            <span className="v1-block-kicker crit">Safety</span>
            <h2 className="v1-block-title">Prescription interactions</h2>
            <span className={`v1-block-count ${r.blockingRx.length ? 'crit' : ''}`}>
              {r.blockingRx.length ? '1 critical · must resolve' : 'cleared'}
            </span>
          </div>
          <div className="v1-stack">
            {RX.map((w) => (
              <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
            ))}
          </div>
        </section>

        {/* Coding — confirm-before-sign gate (neutral, no dollar framing). */}
        <section id="v2-coding" className="v1-block" aria-label="Evaluation and management coding">
          <div className="v1-block-head">
            <span className={`v1-block-kicker ${r.emNeeded ? 'warn' : ''}`}>Coding</span>
            <h2 className="v1-block-title">E/M level</h2>
            <span className={`v1-block-count ${r.emNeeded ? 'warn' : ''}`}>
              {r.emNeeded ? 'confirm to sign' : 'confirmed'}
            </span>
          </div>
          <EmCardV2 confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
        </section>

        <div className="v1-doc-foot" aria-hidden />
      </div>

      {/* ONE Sign button, pinned, always visible — blocker named right beside it. */}
      <div className="v1-signbar">
        <div className="v1-signbar-in">
          <div className="v1-sign-status">
            <span className={`v1-dot ${r.canSign ? 'ok' : 'warn'}`} aria-hidden />
            <span className="v1-sign-msg">{r.canSign ? 'Ready to sign' : 'Review before signing'}</span>
          </div>
          <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} />
        </div>
      </div>
    </div>
  );
}
