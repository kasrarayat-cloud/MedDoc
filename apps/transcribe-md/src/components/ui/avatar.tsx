// HANDOFF §2.1 — initials + deterministic tinted gradient. Ported from
// shell.jsx `Avatar`. The tint is picked from a fixed 7-hue palette based
// on the first character of the name, so the same doctor always gets the
// same colour across the app.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the 7-hue circular gradient
// chip byte-for-byte. `theme="clinician"` swaps to a rounded-square
// `.qm-cl-avatar` chip with serif initials, picking from the 5
// specialty tints (sage/teal/amber/coral/sky) deterministically by
// name. Same `name`/`size` API; the `tint` override only applies to
// the legacy branch.

const TINTS = [
  '#8B5CFF',
  '#D946EF',
  '#60A5FA',
  '#6EE7B7',
  '#FBBF24',
  '#FB7185',
  '#A87CFF',
] as const;

const CL_TINTS = [
  'sage',
  'teal',
  'amber',
  'coral',
  'sky',
] as const;

type AvatarTheme = 'legacy' | 'clinician';
type ClinicianTint = (typeof CL_TINTS)[number];

function pickTint(name: string): string {
  const code = name.charCodeAt(0) || 0;
  return TINTS[code % TINTS.length]!;
}

function pickClinicianTint(name: string): ClinicianTint {
  const code = name.charCodeAt(0) || 0;
  return CL_TINTS[code % CL_TINTS.length]!;
}

function initialsFrom(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0] ?? '')
    .join('')
    .toUpperCase();
}

interface AvatarProps {
  name?: string;
  size?: number;
  tint?: string;
  theme?: AvatarTheme;
}

export function Avatar({
  name = 'JD',
  size = 32,
  tint,
  theme = 'legacy',
}: AvatarProps) {
  if (theme === 'clinician') {
    return <ClinicianAvatar name={name} size={size} />;
  }
  return <LegacyAvatar name={name} size={size} tint={tint} />;
}

function LegacyAvatar({
  name = 'JD',
  size = 32,
  tint,
}: {
  name?: string;
  size?: number;
  tint?: string;
}) {
  const t = tint ?? pickTint(name);
  const initials = initialsFrom(name);
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        flex: `0 0 ${size}px`,
        borderRadius: '50%',
        background: `linear-gradient(135deg, ${t}33, ${t}0a)`,
        border: `1px solid ${t}55`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--sans)',
        fontSize: size * 0.38,
        fontWeight: 600,
        color: t,
        letterSpacing: 0,
        textTransform: 'uppercase',
      }}
    >
      {initials}
    </div>
  );
}

// ── Clinician branch ────────────────────────────────────────────
// Mockup ref: docs/design-directions-v3/clinician/dashboard.html
// (sidebar profile chip) + visit-detail.html (patient header chip).
// Rounded-square (12px radius) chip with serif initials, picking
// from `.qm-cl-avatar-{sage,teal,amber,coral,sky}` deterministically
// by the first character of the name. Width/height respect `size`
// while keeping the proportional 16px serif weight from the mockup.
function ClinicianAvatar({
  name = 'JD',
  size = 44,
}: {
  name?: string;
  size?: number;
}) {
  const tint = pickClinicianTint(name);
  const initials = initialsFrom(name);
  return (
    <div
      aria-hidden
      className={`qm-cl-avatar qm-cl-avatar-${tint}`}
      style={{
        width: size,
        height: size,
        flex: `0 0 ${size}px`,
        // Inline overrides on top of the class so `size` scales the
        // chip while keeping the warm-tint background from the class.
        fontSize: Math.max(11, size * 0.36),
      }}
    >
      {initials}
    </div>
  );
}
