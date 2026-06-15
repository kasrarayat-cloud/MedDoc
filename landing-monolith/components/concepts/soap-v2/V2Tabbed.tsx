'use client';

// V2 — "TABBED SIGN-GATE WORKSPACE". The note is full-width on its own tab; secondary content
// lives on its OWN full-width tab (Review / Rx / Coding) — never beside the note, so there is no
// side-by-side collision to begin with. The risk of tabs ("a blocker hides one tap away") is
// answered three ways that stay on screen no matter which tab is open: (1) a count/warning BADGE
// on each tab label, (2) a persistent "sign readiness" meter in the header, and (3) a persistent
// bottom Sign bar that always names the top remaining blocker and jumps to it. Static mockup.
import { useRef, useState } from 'react';
import { SampleChip, PatientMeta, NoteDoc, LaneCard, RxCard, SignButton } from '../soap/parts';
import { EmCardV2 } from './parts-v2';
import { useReviewV2 } from './engine';
import { VISIT, LANE, RX } from '../soap/data';

type Tab = 'note' | 'review' | 'rx' | 'coding';

export function V2Tabbed() {
  const r = useReviewV2();
  const [tab, setTab] = useState<Tab>('note');
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  // Sign readiness — the two HARD gates (Rx + coding). Visible regardless of active tab.
  const cleared = 2 - r.blockers.length;
  const primaryTab: Tab | null = r.blockingRx.length ? 'rx' : r.emNeeded ? 'coding' : null;

  const tabs: { id: Tab; label: string; badge?: { text: string; tone: 'crit' | 'warn' | 'info' | 'ok' } }[] = [
    { id: 'note', label: 'Note' },
    {
      id: 'review',
      label: 'Review',
      badge: r.pendingLane.length ? { text: String(r.pendingLane.length), tone: 'info' } : { text: '✓', tone: 'ok' },
    },
    {
      id: 'rx',
      label: 'Rx',
      badge: r.blockingRx.length ? { text: '!', tone: 'crit' } : { text: '✓', tone: 'ok' },
    },
    {
      id: 'coding',
      label: 'Coding',
      badge: r.emNeeded ? { text: '!', tone: 'warn' } : { text: '✓', tone: 'ok' },
    },
  ];

  return (
    <div className="sc-app v2v2">
      <header className="sc-top">
        <div className="sc-top-l">
          <PatientMeta />
        </div>
        <div className="sc-top-r">
          <SampleChip />
        </div>
      </header>

      {/* Persistent header: sign-readiness meter + badged tab strip. */}
      <div className="v2-bar">
        <div className="v2-ready" aria-label={`Sign readiness: ${cleared} of 2 safety checks cleared`}>
          <span className={`v2-dot ${r.canSign ? 'ok' : 'warn'}`} aria-hidden />
          <span className="v2-ready-text">
            {r.canSign ? 'Ready to sign' : `${cleared} of 2 checks cleared`}
          </span>
          <span className="v2-pips" aria-hidden>
            <span className={`v2-pip ${r.blockingRx.length ? '' : 'on'}`} title="Prescription safety" />
            <span className={`v2-pip ${r.emNeeded ? '' : 'on'}`} title="Coding confirmed" />
          </span>
        </div>

        <div
          className="v2-tabs"
          role="tablist"
          aria-label="Review sections"
          onKeyDown={(e) => {
            const order = tabs.map((t) => t.id);
            const i = order.indexOf(tab);
            let next = i;
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i + 1) % order.length;
            else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i - 1 + order.length) % order.length;
            else if (e.key === 'Home') next = 0;
            else if (e.key === 'End') next = order.length - 1;
            else return;
            e.preventDefault();
            const id = order[next];
            setTab(id);
            tabRefs.current[id]?.focus();
          }}
        >
          {tabs.map((t) => (
            <button
              key={t.id}
              id={`v2-tab-${t.id}`}
              ref={(el) => {
                tabRefs.current[t.id] = el;
              }}
              role="tab"
              type="button"
              aria-selected={tab === t.id}
              aria-controls="v2-tabpanel"
              tabIndex={tab === t.id ? 0 : -1}
              className={`v2-tab ${tab === t.id ? 'on' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <span className="v2-tab-label">{t.label}</span>
              {t.badge && <span className={`v2-tab-badge ${t.badge.tone}`}>{t.badge.text}</span>}
            </button>
          ))}
        </div>
      </div>

      {/* Full-width tab panel — exactly one section, always full width. */}
      <div className="v2-panel" id="v2-tabpanel" role="tabpanel" aria-labelledby={`v2-tab-${tab}`} tabIndex={0} key={tab}>
        {tab === 'note' && (
          <article className="v2-note">
            <div className="v2-masthead">
              <h1 className="v2-pt-name">{VISIT.patient}</h1>
              <p className="v2-pt-meta">
                {VISIT.meta} · MRN {VISIT.mrn} · {VISIT.when}
              </p>
            </div>
            <NoteDoc />
          </article>
        )}

        {tab === 'review' && (
          <section className="v2-section" aria-label="AI suggestions to review">
            <div className="v2-sec-head">
              <h2 className="v2-sec-title">AI suggestions</h2>
              <span className="v2-sec-sub">
                {r.pendingLane.length ? `${r.pendingLane.length} to review` : 'all reviewed'}
              </span>
            </div>
            <p className="v2-sec-lead">
              Kept out of the note until you adopt them. Adopting adds the line as your own attestation.
            </p>
            <div className="v2-stack">
              {LANE.map((l) => (
                <LaneCard key={l.id} item={l} state={r.laneState(l.id)} onAdopt={r.adopt} onDismiss={r.dismiss} />
              ))}
            </div>
          </section>
        )}

        {tab === 'rx' && (
          <section className="v2-section" aria-label="Prescription safety">
            <div className="v2-sec-head">
              <h2 className="v2-sec-title">Prescription interactions</h2>
              <span className={`v2-sec-sub ${r.blockingRx.length ? 'crit' : ''}`}>
                {r.blockingRx.length ? '1 critical · override to sign' : 'cleared'}
              </span>
            </div>
            <div className="v2-stack">
              {RX.map((w) => (
                <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
              ))}
            </div>
          </section>
        )}

        {tab === 'coding' && (
          <section className="v2-section" aria-label="Evaluation and management coding">
            <div className="v2-sec-head">
              <h2 className="v2-sec-title">E/M level</h2>
              <span className={`v2-sec-sub ${r.emNeeded ? 'warn' : ''}`}>
                {r.emNeeded ? 'confirm to sign' : 'confirmed'}
              </span>
            </div>
            <EmCardV2 confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
          </section>
        )}
      </div>

      {/* Persistent Sign bar — always visible across every tab; names + jumps to the top blocker. */}
      <div className="v2-signbar">
        <div className="v2-signbar-in">
          {r.canSign ? (
            <div className="v2-sign-status">
              <span className="v2-dot ok" aria-hidden />
              <span className="v2-sign-msg">All checks cleared</span>
            </div>
          ) : (
            <button
              type="button"
              className="v2-sign-status v2-sign-jump"
              onClick={() => primaryTab && setTab(primaryTab)}
              aria-label={`${r.blockers[0]} — go to it`}
            >
              <span className="v2-dot warn" aria-hidden />
              <span className="v2-sign-msg">
                {r.blockers.length} to resolve · <span className="v2-sign-top">{r.blockers[0]}</span>
              </span>
              <span className="v2-sign-go" aria-hidden>
                →
              </span>
            </button>
          )}
          <SignButton canSign={r.canSign} blockers={r.blockers} signed={r.signed} onSign={() => r.setSigned(true)} />
        </div>
      </div>
    </div>
  );
}
