// Synthetic, no-PHI data for the dashboard + create/record concept screens. NOT wired to the real
// pipeline — static props. Same synthetic "Sample patient" used across the family; clinical facts
// are generic age/sex/visit-type strings, never real identifiers.

export const SAMPLE_BANNER = 'Synthetic sample — not a real patient or visit';

export const DOCTOR = { name: 'Dr. Sample', greeting: 'Good afternoon', day: 'Thursday' };

// ── ONE unified status vocabulary ───────────────────────────────────────────────────────────
// The live app currently scatters ~7 lifecycle words (queued / transcribing / drafting / draft /
// needs review / completed / archived). The whole lifecycle collapses to these four plain states,
// used identically on the dashboard and in the record flow:
export type Status = 'recording' | 'processing' | 'ready' | 'signed';
export const STATUS_LABEL: Record<Status, string> = {
  recording: 'Recording',
  processing: 'Processing',
  ready: 'Ready to sign',
  signed: 'Signed',
};

export type Visit = { id: string; patient: string; meta: string; when: string; mins: number; status: Status };

// The dashboard's single focus: notes ready to sign (the doctor's actual "do this next").
export const INBOX: Visit[] = [
  { id: 'v1', patient: 'Sample patient', meta: '54 M · Hypertension follow-up', when: '11:24', mins: 12, status: 'ready' },
  { id: 'v2', patient: 'Sample patient', meta: '38 F · Annual physical', when: '10:05', mins: 18, status: 'ready' },
  { id: 'v3', patient: 'Sample patient', meta: '61 M · Type 2 diabetes check', when: '09:30', mins: 9, status: 'ready' },
];

// In-flight visits (still capturing / being drafted) — shown smaller, below the inbox.
export const INPROGRESS: Visit[] = [
  { id: 'p1', patient: 'Sample patient', meta: '47 F · Knee pain', when: '11:58', mins: 0, status: 'processing' },
  { id: 'p2', patient: 'Sample patient', meta: '29 M · Walk-in', when: '12:02', mins: 0, status: 'recording' },
];

// Quiet, demoted day summary (replaces the old 4 vanity stat cards).
export const DAY_SUMMARY = { total: 6, signed: 3 };

// The record screen's sensible default for a walk-in (no choice-overload).
export const VISIT_DEFAULT = { type: 'Office visit', who: 'Walk-in · new patient' };
