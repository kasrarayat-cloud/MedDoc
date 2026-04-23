// HANDOFF §2.1 — initials + deterministic tinted gradient. Ported from
// shell.jsx `Avatar`. The tint is picked from a fixed 7-hue palette based
// on the first character of the name, so the same doctor always gets the
// same colour across the app.

const TINTS = [
  '#8B5CFF',
  '#D946EF',
  '#60A5FA',
  '#6EE7B7',
  '#FBBF24',
  '#FB7185',
  '#A87CFF',
] as const;

function pickTint(name: string): string {
  const code = name.charCodeAt(0) || 0;
  return TINTS[code % TINTS.length]!;
}

function initialsFrom(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0] ?? '')
    .join('')
    .toUpperCase();
}

export function Avatar({
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
