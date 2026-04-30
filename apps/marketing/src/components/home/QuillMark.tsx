/**
 * Sage ink-feather mark — Clinician brand glyph (Phase 3). Lifted from the
 * landing-and-recording.html mockup wordmark. Uses the sage primary color
 * (#7AA68C) with a soft sage-tint fill so it reads warm against cream.
 *
 * `gradientId` is preserved for backward compatibility with sites that
 * still pass it; the glyph no longer uses an SVG gradient (Clinician's
 * marks are flat sage strokes), but the prop is accepted to avoid TS
 * breakage at call sites.
 */
export function QuillMark({ gradientId: _gradientId = 'quillG' }: { gradientId?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <path
        d="M4 19c4 -1 7 -3.5 9.5 -7c1.5 -2 3 -3.5 5 -4.5c1.2 -0.6 2 -0.4 1.6 0.8c-0.7 2 -2.4 4.4 -4.6 6.4c-2.6 2.4 -5.6 4 -8.5 4.7c-1 0.2 -2.4 0.3 -3 -0.4z"
        stroke="#7AA68C"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="rgba(122,166,140,0.14)"
      />
      <path
        d="M4 19l3.5 -3"
        stroke="#7AA68C"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
