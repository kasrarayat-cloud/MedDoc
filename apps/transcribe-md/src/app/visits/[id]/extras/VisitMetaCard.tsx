'use client';

// ============================================================================
// VisitMetaCard — encounter-level facts (specialty, type, duration,
// location, billing provider, encounter ID, recording metadata).
// ----------------------------------------------------------------------------
// Pulls from data already on the visit / user objects in the page
// fetch — no new queries needed.
// ============================================================================

import { ExtrasCard, Kv } from './ExtrasCard';

export interface VisitMetaData {
  specialty: string;
  visitType?: string | null;
  /** Encounter wall-time, in seconds. */
  durationSec: number | null;
  /** Audio capture duration, in seconds. */
  audioDurationSec: number | null;
  inputMode: string;
  /** Display name of the billing / signing provider. */
  billingProvider?: string | null;
  /** Provider NPI (10-digit identifier). */
  providerNpi?: string | null;
  /** Encounter ID (defaults to visit id if no separate identifier
   *  exists). */
  encounterId: string;
  /** Display name of the recording clinician (= billing provider in
   *  the single-clinician model, but kept distinct for future
   *  delegated-recording flows). */
  recordedBy?: string | null;
  /** Optional clinic location string. */
  location?: string | null;
}

interface Props {
  data: VisitMetaData;
}

function fmtDuration(sec: number | null): string | null {
  if (sec == null) return null;
  if (sec < 60) return `${sec} s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s === 0 ? `${m} min` : `${m} min ${s.toString().padStart(2, '0')} s`;
}

function inputModeLabel(mode: string): string {
  switch (mode) {
    case 'audio_upload':
      return 'Audio upload';
    case 'voice_dictation':
      return 'Voice dictation';
    case 'text_notes':
      return 'Text notes';
    default:
      return mode;
  }
}

export function VisitMetaCard({ data }: Props) {
  const wallDuration = fmtDuration(data.durationSec);
  const audioDuration = fmtDuration(data.audioDurationSec);

  return (
    <ExtrasCard
      icon="ⓘ"
      title="Visit metadata"
      sub={`Encounter · ${data.encounterId}`}
      count="7 fields"
      countTone="default"
      hideEdit
    >
      <div className="qm-lin-extras-kv-grid">
        <Kv label="Specialty" value={data.specialty} />
        <Kv
          label="Visit type"
          value={data.visitType ?? null}
          secondary={inputModeLabel(data.inputMode).toLowerCase()}
        />
        <Kv
          label="Duration"
          value={wallDuration}
          secondary={audioDuration ? `${audioDuration} audio` : undefined}
          mono={Boolean(wallDuration)}
        />
        <Kv label="Location" value={data.location ?? null} />
        <Kv
          label="Billing provider"
          value={data.billingProvider ?? null}
          secondary={data.providerNpi ? `NPI ${data.providerNpi}` : undefined}
        />
        <Kv label="Recorded by" value={data.recordedBy ?? null} />
        <Kv label="Encounter ID" value={data.encounterId} mono />
      </div>
    </ExtrasCard>
  );
}
