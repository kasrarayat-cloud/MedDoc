'use client';

// Every line here is a real, true property of the product. No certifications
// we don't hold, no invented "protocols". The LOOK sells security; the WORDS
// are accurate for a HIPAA medical product.
const CLAIMS: { k: string; v: string }[] = [
  { k: 'HIPAA-ready', v: 'Built to the Security Rule — administrative, physical, and technical safeguards.' },
  { k: 'BAA included', v: 'A Business Associate Agreement is part of every account, at no extra cost.' },
  { k: 'Encrypted at rest', v: 'Stored data is encrypted on US-based infrastructure.' },
  { k: 'US-hosted', v: 'PHI is stored and processed inside the United States.' },
  { k: 'Fully audit-logged', v: 'Every action emits an immutable, append-only audit event.' },
  { k: 'You sign every note', v: 'Nothing is final until a clinician reviews and signs it.' },
];

// THIS note, protected — the page's own SOAP language, encrypted. Each line is
// an elegant redaction bar (deterministic widths) under an encryption shimmer.
const ENC_LINES: { tag: string; w: number }[] = [
  { tag: 'S', w: 86 },
  { tag: 'O', w: 64 },
  { tag: 'A', w: 44 },
  { tag: 'P', w: 72 },
];

// Quiet, append-only audit trail at the base — readable events, not hex noise.
const AUDIT: string[] = [
  '09:24:01  note.created',
  '09:31:18  note.signed      ✓',
  '09:31:18  record.sealed    🔒',
];

export function Security() {
  return (
    <section id="security" className="section security" aria-label="Security">
      <div className="security-inner">
        <div className="security-copy reveal">
          <p className="eyebrow">Security</p>
          <h2 className="font-display security-title">
            Secured.<br />Encrypted.<br /><span className="text-gold">Audited.</span>
          </h2>
          <p className="section-lede">
            A clinical record is the most sensitive document you write. QuillMD
            treats it that way — encryption, a signed BAA, US-only hosting, and a
            complete audit trail behind every note.
          </p>

          <ul className="claim-list">
            {CLAIMS.map((c) => (
              <li key={c.k} className="claim">
                <span className="claim-key font-mono text-turq">{c.k}</span>
                <span className="claim-val">{c.v}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* In-code "encrypted clinical record" visual — pure DOM/SVG/CSS, no
            raster asset. Decorative: the real information is the claims list. */}
        <div className="security-visual reveal" aria-hidden>
          <div className="encnote glass glass-edge">
            <div className="enc-shimmer" />
            <header className="encnote-head font-mono">
              <span className="encnote-kind">SOAP · clinical note</span>
              <span className="encnote-state">
                <LockMark />
                ENCRYPTED
              </span>
            </header>

            <div className="encnote-body">
              {ENC_LINES.map((l, i) => (
                <div className="encline" key={l.tag} style={{ ['--w' as string]: `${l.w}%`, ['--i' as string]: i }}>
                  <span className={`encline-tag enc-${l.tag}`}>{l.tag}</span>
                  <span className="encline-bar" />
                </div>
              ))}
            </div>

            <footer className="encnote-audit font-mono">
              {AUDIT.map((a, i) => (
                <span className="audit-line" key={a} style={{ ['--i' as string]: i }}>
                  <span className="audit-tick" />
                  {a}
                </span>
              ))}
            </footer>
          </div>
        </div>
      </div>
    </section>
  );
}

function LockMark() {
  return (
    <svg className="enc-lockmark" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden>
      <defs>
        <linearGradient id="lockg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#e8b85c" />
          <stop offset="1" stopColor="#3fd8c8" />
        </linearGradient>
      </defs>
      <rect x="5.5" y="10.5" width="13" height="9.5" rx="2" stroke="url(#lockg)" strokeWidth="1.6" />
      <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" stroke="url(#lockg)" strokeWidth="1.6" />
      <circle cx="12" cy="15" r="1.4" fill="url(#lockg)" />
    </svg>
  );
}
