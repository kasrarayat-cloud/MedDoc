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

        <div className="security-vault reveal" aria-hidden>
          <div className="vault-glow" />
          {/* SECURITY_VAULT image — self-hosted; swapped to the real Higgsfield
              render when its URL is provided. The streaming data + lock CSS
              layer reads as encryption even before/behind the art. */}
          <img
            src="/assets/security-vault.svg"
            alt=""
            className="vault-img"
            width={720}
            height={720}
            decoding="async"
          />
          <div className="vault-stream font-mono" aria-hidden>
            {Array.from({ length: 7 }).map((_, i) => (
              <span key={i} className="stream-line" style={{ animationDelay: `${i * 0.5}s` }}>
                {hex(i)}
              </span>
            ))}
          </div>
          <div className="vault-lock" aria-hidden>
            <svg viewBox="0 0 48 48" width="48" height="48" fill="none">
              <rect x="9" y="21" width="30" height="22" rx="3" stroke="currentColor" strokeWidth="2" />
              <path d="M15 21v-5a9 9 0 0 1 18 0v5" stroke="currentColor" strokeWidth="2" />
              <circle cx="24" cy="31" r="3" fill="currentColor" />
            </svg>
          </div>
        </div>
      </div>
    </section>
  );
}

function hex(seed: number): string {
  const chars = '0123456789ABCDEF';
  let s = '';
  for (let i = 0; i < 26; i++) s += chars[(seed * 7 + i * 13) % 16];
  return s.replace(/(.{4})/g, '$1 ').trim();
}
