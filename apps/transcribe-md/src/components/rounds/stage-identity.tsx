// ============================================================================
// ROUNDS — Screen 2's identity header.
// ----------------------------------------------------------------------------
// Name · MRN · age · DOB · reason line, then Ward Board's bordered meta cells
// for recorded-at and audio duration.
//
// EVERY CELL IS CONDITIONAL, and that is the point. A patient with no MRN gets
// no MRN cell — not "MRN —", not "MRN unknown". The shipped meta strip already
// works this way (`{visit.patient?.externalId && …}`) and it is the honest
// render: an empty labelled cell reads as a value the system failed to load,
// which sends the reader looking for a bug that is not there.
//
// The vitals-chip slot the spec reserves is DELIBERATELY ABSENT from this
// component. L3 has a `measurements` slot but no vitals shape, so there is
// nothing real to render; the spec says build it only when structured vitals
// exist — parked, never faked. The reservation lives in the stage layout, and
// `stage.test.tsx` asserts the slot is empty rather than that it is populated.
// ============================================================================

import type { StageIdentity } from '@/lib/rounds/stage-data';
import { formatLocalDateTime } from '@/lib/format-time';

function MetaCell({
  label,
  value,
  testId,
}: {
  label: string;
  value: string;
  testId: string;
}) {
  return (
    <div className="qm-rounds-ident-cell" data-testid={testId}>
      <span className="qm-rounds-ident-cell-label">{label}</span>
      <span className="qm-rounds-ident-cell-value">{value}</span>
    </div>
  );
}

export function RoundsStageIdentity({ identity }: { identity: StageIdentity }) {
  const { patientLabel, mrn, ageYears, dob, reason, recordedAtIso, durationLabel } =
    identity;

  // MRN · age · DOB read as one line of demographic facts, so they are joined
  // rather than boxed separately — the boxed cells below are for the ENCOUNTER
  // (when it happened, how long it ran), which is a different kind of fact.
  const demographics = [
    mrn ? `MRN ${mrn}` : null,
    ageYears !== null ? `${ageYears}y` : null,
    dob ? `DOB ${dob}` : null,
  ].filter(Boolean) as string[];

  return (
    <header className="qm-rounds-ident" data-testid="rounds-stage-identity">
      <h1 className="qm-rounds-ident-name" data-testid="rounds-stage-patient">
        {patientLabel}
      </h1>

      {demographics.length ? (
        <p className="qm-rounds-ident-demo" data-testid="rounds-stage-demographics">
          {demographics.join(' · ')}
        </p>
      ) : null}

      {reason ? (
        <p className="qm-rounds-ident-reason" data-testid="rounds-stage-reason">
          {reason}
        </p>
      ) : null}

      <div className="qm-rounds-ident-cells">
        <MetaCell
          label="Recorded"
          value={formatLocalDateTime(recordedAtIso)}
          testId="rounds-stage-recorded"
        />
        {durationLabel ? (
          <MetaCell
            label="Audio"
            value={durationLabel}
            testId="rounds-stage-duration"
          />
        ) : null}
      </div>
    </header>
  );
}
