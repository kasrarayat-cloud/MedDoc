'use client';

// SCREEN 1 (final 3) — PATIENT DETAIL, in the C3 calm-one-action pattern. A calm patient header
// (identity + the few facts a doctor wants at a glance: problems, meds, allergies) + a quiet visit
// timeline that REUSES the dashboard inbox row + status pill. ONE primary ("+ New visit for this
// patient"); "Open last note" easy to reach. No 4 stat tiles, no dense 6-col table, no dead
// "Coming soon" tabs, no duplicate CTAs. Static mockup, synthetic no-PHI data.
import Link from 'next/link';
import { AppShell, StatusPill } from './AppShell';
import { SAMPLE_BANNER } from './data';
import type { Visit } from './data';

const PATIENT = {
  name: 'Sample patient',
  meta: '54 · M · MRN SYN-0000',
  problems: ['Hypertension', 'Type 2 diabetes'],
  meds: ['Lisinopril 20 mg', 'Amlodipine 5 mg', 'Metformin 1000 mg'],
  allergy: 'Penicillin (rash)',
};

// the patient's visits — reverse chronological; the top one is still Ready to sign, the rest Signed
const VISITS: Visit[] = [
  { id: 'pv1', patient: 'Sample patient', meta: 'Hypertension follow-up', when: 'Today · 11:24', mins: 12, status: 'ready' },
  { id: 'pv2', patient: 'Sample patient', meta: 'Type 2 diabetes check', when: 'Mar 2 · 09:30', mins: 14, status: 'signed' },
  { id: 'pv3', patient: 'Sample patient', meta: 'Annual physical', when: 'Jan 18 · 10:05', mins: 22, status: 'signed' },
  { id: 'pv4', patient: 'Sample patient', meta: 'Acute visit — sore throat', when: 'Dec 4 · 14:40', mins: 8, status: 'signed' },
];

function VisitRow({ v }: { v: Visit }) {
  return (
    <Link href="/concepts/soap/c3-final" className="ax-row ax-row-link">
      <span className="ax-row-main">
        <span className="ax-row-patient">{v.meta}</span>
        <span className="ax-row-meta">{v.when}</span>
      </span>
      <span className="ax-row-right">
        <span className="ax-row-when">{v.mins} min</span>
        <StatusPill status={v.status} />
        <span className="ax-row-go" aria-hidden>→</span>
      </span>
    </Link>
  );
}

export function PatientScreen() {
  return (
    <AppShell active="patients">
      <div className="ax-pt">
        <header className="ax-pt-head">
          <div className="ax-pt-id">
            <span className="ax-pt-avatar" aria-hidden>SP</span>
            <div>
              <h1 className="ax-pt-name">{PATIENT.name}</h1>
              <p className="ax-pt-metaline">{PATIENT.meta}</p>
            </div>
          </div>
          <div className="ax-pt-actions">
            <Link href="/concepts/soap/c3-final" className="ax-pt-2nd">Open last note</Link>
            <Link href="/concepts/record" className="ax-cta">+ New visit</Link>
          </div>
        </header>

        <span className="ax-sample">● {SAMPLE_BANNER}</span>

        <dl className="ax-pt-facts">
          <div className="ax-pt-fact">
            <dt className="ax-pt-fact-k">Problems</dt>
            <dd className="ax-pt-fact-v">{PATIENT.problems.join(' · ')}</dd>
          </div>
          <div className="ax-pt-fact">
            <dt className="ax-pt-fact-k">Medications</dt>
            <dd className="ax-pt-fact-v">{PATIENT.meds.join(' · ')}</dd>
          </div>
          <div className="ax-pt-fact ax-pt-fact-warn">
            <dt className="ax-pt-fact-k">Allergies</dt>
            <dd className="ax-pt-fact-v">{PATIENT.allergy}</dd>
          </div>
        </dl>

        <section className="ax-section" aria-labelledby="ax-pt-visits">
          <div className="ax-section-head">
            <h2 id="ax-pt-visits" className="ax-section-title">Visits</h2>
            <span className="ax-section-count">{VISITS.length}</span>
          </div>
          <div className="ax-list">
            {VISITS.map((v) => (
              <VisitRow key={v.id} v={v} />
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
