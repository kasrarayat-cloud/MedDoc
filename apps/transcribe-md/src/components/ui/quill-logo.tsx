// HANDOFF §2.1 — feather-quill wordmark glyph (the violet gradient shape
// on TopNav + SignIn). Ported from shell.jsx `QuillLogo`.

export function QuillLogo({ size = 28 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 32 32"
      width={size}
      height={size}
      fill="none"
      style={{ display: 'block' }}
      aria-hidden
    >
      <defs>
        <linearGradient id="qm-logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#D1B5FF" />
          <stop offset="0.5" stopColor="#A87CFF" />
          <stop offset="1" stopColor="#6B3FD9" />
        </linearGradient>
      </defs>
      <path
        d="M26 4 C 18 6, 10 12, 6 22 L 4 28 L 10 26 C 20 22, 26 14, 28 6 Z"
        fill="url(#qm-logo-g)"
        stroke="url(#qm-logo-g)"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      <path d="M8 24 L 20 12" stroke="rgba(255,255,255,0.4)" strokeWidth="0.75" />
    </svg>
  );
}
