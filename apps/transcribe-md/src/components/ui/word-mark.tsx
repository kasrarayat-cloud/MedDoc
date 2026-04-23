// HANDOFF §2.1 — "QuillMD" wordmark typeset in serif with italic accent on
// the "MD" suffix (the signature move from §1.2).

export function WordMark({ size = 15 }: { size?: number }) {
  return (
    <span
      style={{
        fontFamily: 'var(--serif)',
        fontSize: size,
        fontWeight: 500,
        letterSpacing: '-0.02em',
        color: 'var(--fg)',
      }}
    >
      Quill
      <em style={{ fontStyle: 'italic', color: 'var(--accent-bright)' }}>MD</em>
    </span>
  );
}
