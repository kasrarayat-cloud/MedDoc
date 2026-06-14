'use client';

// SCREEN 1 — DASHBOARD, redesigned as a calm "here's your work" home. The single focus is the
// notes-to-sign inbox (the doctor's real "do this next"); the one clear primary is "+ New visit";
// the old 4 vanity stat cards are demoted to one quiet line; there are no duplicate patients/visits
// tabs. One glance answers "what do I do next." Each inbox row opens the C3 review (the flow).
import Link from 'next/link';
import { AppShell, StatusPill } from './AppShell';
import { DOCTOR, INBOX, INPROGRESS, DAY_SUMMARY, SAMPLE_BANNER } from './data';
import type { Visit } from './data';

function InboxRow({ v }: { v: Visit }) {
  return (
    <Link href="/concepts/soap/c3-final" className="ax-row ax-row-link">
      <span className="ax-row-main">
        <span className="ax-row-patient">{v.patient}</span>
        <span className="ax-row-meta">{v.meta}</span>
      </span>
      <span className="ax-row-right">
        <span className="ax-row-when">{v.when} · {v.mins} min</span>
        <StatusPill status={v.status} />
        <span className="ax-row-go" aria-hidden>→</span>
      </span>
    </Link>
  );
}

export function DashboardScreen() {
  return (
    <AppShell active="home">
      <div className="ax-dash">
        <header className="ax-dash-head">
          <div className="ax-dash-greet">
            <h1 className="ax-dash-title">{DOCTOR.greeting}, {DOCTOR.name}</h1>
            <p className="ax-dash-sub">{DOCTOR.day} · {DAY_SUMMARY.total} visits today · {DAY_SUMMARY.signed} signed</p>
          </div>
          <Link href="/concepts/record" className="ax-cta">+ New visit</Link>
        </header>

        <span className="ax-sample">● {SAMPLE_BANNER}</span>

        <section className="ax-section" aria-labelledby="ax-tosign">
          <div className="ax-section-head">
            <h2 id="ax-tosign" className="ax-section-title">Ready to sign</h2>
            <span className="ax-section-count">{INBOX.length}</span>
          </div>
          {INBOX.length === 0 ? (
            <div className="ax-empty">
              <span className="ax-empty-mark" aria-hidden>✓</span> You’re all caught up.
            </div>
          ) : (
            <div className="ax-list">
              {INBOX.map((v) => (
                <InboxRow key={v.id} v={v} />
              ))}
            </div>
          )}
        </section>

        <section className="ax-section ax-section-quiet" aria-labelledby="ax-inflight">
          <div className="ax-section-head">
            <h2 id="ax-inflight" className="ax-section-title">In progress</h2>
            <span className="ax-section-count">{INPROGRESS.length}</span>
          </div>
          <div className="ax-list">
            {INPROGRESS.map((v) => (
              <div key={v.id} className="ax-row">
                <span className="ax-row-main">
                  <span className="ax-row-patient">{v.patient}</span>
                  <span className="ax-row-meta">{v.meta}</span>
                </span>
                <span className="ax-row-right">
                  <span className="ax-row-when">{v.when}</span>
                  <StatusPill status={v.status} />
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
