// HANDOFF §4 — specialty chip with icon + tint + label. The kind enum is
// closed by design: new specialties must be added here AND in Settings'
// specialty picker AND wherever the dashboard filters by specialty.

import { Ic } from './icon';

type SpecialtyKind =
  | 'cardiology'
  | 'pain'
  | 'ortho'
  | 'primary'
  | 'pulmonology'
  | 'ophthalmology';

export const SPECIALTY: Record<
  SpecialtyKind,
  { icon: (typeof Ic)[keyof typeof Ic]; tint: string; label: string }
> = {
  cardiology: { icon: Ic.heart, tint: '#FB7185', label: 'Cardiology' },
  pain: { icon: Ic.nerve, tint: '#A87CFF', label: 'Pain mgmt' },
  ortho: { icon: Ic.bone, tint: '#60A5FA', label: 'Orthopedics' },
  primary: { icon: Ic.stethoscope, tint: '#6EE7B7', label: 'Primary care' },
  pulmonology: { icon: Ic.lung, tint: '#FBBF24', label: 'Pulmonology' },
  ophthalmology: { icon: Ic.eye, tint: '#D946EF', label: 'Ophthalmology' },
};

export type { SpecialtyKind };

export function SpecChip({
  kind = 'primary',
  size = 'md',
}: {
  kind?: SpecialtyKind;
  size?: 'sm' | 'md';
}) {
  const s = SPECIALTY[kind] ?? SPECIALTY.primary;
  const h = size === 'sm' ? 22 : 26;
  const ic = size === 'sm' ? 11 : 13;
  return (
    <span
      className="qm-chip"
      style={{
        height: h,
        padding: size === 'sm' ? '0 8px' : '0 10px',
        color: s.tint,
        borderColor: `${s.tint}55`,
        background: `${s.tint}11`,
        fontFamily: 'var(--sans)',
        fontSize: size === 'sm' ? 10.5 : 11.5,
        letterSpacing: '0.02em',
        textTransform: 'none',
      }}
    >
      <s.icon width={ic} height={ic} />
      {s.label}
    </span>
  );
}
