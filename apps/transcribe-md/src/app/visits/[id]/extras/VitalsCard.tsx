'use client';

// ============================================================================
// VitalsCard — 4-column tile grid (BP / HR / RR / Temp / SpO₂ / Weight /
// Height / BMI). Each tile = mono uppercase label + big mono value +
// small unit + optional sage "Normal" affirmation.
// ----------------------------------------------------------------------------
// The visit-detail data path doesn't currently emit structured vitals.
// Until a follow-up PR wires that, the card renders the tile
// scaffolding with em-dash placeholders so the visual layout matches
// the V4 mock and a future data-only PR can populate values without
// re-touching this component.
// ============================================================================

import { ExtrasCard } from './ExtrasCard';

export interface Vital {
  /** Numeric or formatted reading (e.g. "118/74", "98.6"). */
  value: string | null;
  /** Display unit (e.g. "mmHg"). */
  unit?: string | null;
  /** Optional sage affirmation ("Normal", "Stable") shown under the value. */
  ok?: string | null;
}

export interface VitalsCardData {
  bp?: Vital | null;
  hr?: Vital | null;
  rr?: Vital | null;
  temp?: Vital | null;
  spo2?: Vital | null;
  weight?: Vital | null;
  height?: Vital | null;
  bmi?: Vital | null;
  /** ISO timestamp when the vitals were recorded. */
  recordedAt?: string | null;
}

interface Props {
  data: VitalsCardData;
  readonly: boolean;
}

interface Tile {
  label: string;
  vital?: Vital | null;
}

function Tile({ label, vital }: Tile) {
  const display = vital?.value ?? '—';
  const unit = vital?.unit ?? null;
  const ok = vital?.ok ?? null;
  return (
    <div className="qm-lin-extras-vt">
      <span className="qm-lin-extras-vt-lbl">{label}</span>
      <span className="qm-lin-extras-vt-val">
        {display}
        {unit && <span className="qm-lin-extras-vt-unit">{unit}</span>}
      </span>
      {ok && <span className="qm-lin-extras-vt-ok">✓ {ok}</span>}
    </div>
  );
}

export function VitalsCard({ data, readonly }: Props) {
  const tiles: Tile[] = [
    { label: 'BP', vital: data.bp },
    { label: 'HR', vital: data.hr },
    { label: 'RR', vital: data.rr },
    { label: 'Temp', vital: data.temp },
    { label: 'SpO₂', vital: data.spo2 },
    { label: 'Weight', vital: data.weight },
    { label: 'Height', vital: data.height },
    { label: 'BMI', vital: data.bmi },
  ];

  const populated = tiles.filter((t) => t.vital?.value != null).length;
  const inRange = tiles.filter((t) => t.vital?.ok != null).length;

  const sub = data.recordedAt
    ? `Recorded ${data.recordedAt}`
    : populated > 0
      ? `${populated} reading${populated === 1 ? '' : 's'}`
      : 'No vitals recorded for this visit';

  const count =
    populated > 0
      ? `${inRange} / ${populated} in range`
      : null;

  return (
    <ExtrasCard
      icon="❤"
      title="Vitals"
      sub={sub}
      count={count}
      countTone={inRange === populated && populated > 0 ? 'sage' : 'default'}
      hideEdit={readonly}
    >
      <div className="qm-lin-extras-vitals-tiles">
        {tiles.map((t) => (
          <Tile key={t.label} label={t.label} vital={t.vital} />
        ))}
      </div>
    </ExtrasCard>
  );
}
