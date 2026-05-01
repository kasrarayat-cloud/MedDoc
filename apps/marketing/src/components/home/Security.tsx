/**
 * Security section — Linear V1 (Faithful).
 *
 * Two-column on wide screens (intro left, 6-cell grid right). Uses the
 * .features/.feat-grid surface vocabulary so the security card is visually
 * consistent with the main features grid. Drop Source Serif italic, drop
 * the cinematic-era inline styles.
 */
type SecItem = {
  title: string;
  body: string;
  icon: React.ReactNode;
  logos?: string[];
};

const ITEMS: SecItem[] = [
  {
    title: 'HIPAA-aligned',
    body: 'Technical, administrative, and physical safeguards per 45 CFR § 164. On request BAA with your practice.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2 L 4 6 v 6 c 0 5 3.5 8 8 10 c 4.5 -2 8 -5 8 -10 V 6 z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    title: 'End-to-end encryption',
    body: 'TLS 1.3 in transit. AES-256 at rest. Per-tenant key isolation. Keys rotate every 90 days.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="4" y="11" width="16" height="10" rx="2" />
        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
      </svg>
    ),
  },
  {
    title: 'No training on your data',
    body: 'Model vendors run under standard no-retention terms for API data. Nothing you send is used to train foundation models.',
    logos: ['Anthropic', 'OpenAI', 'Deepgram'],
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 7h16v12H4z" />
        <path d="M8 3v4M16 3v4M4 11h16" />
      </svg>
    ),
  },
  {
    title: 'US-only hosting',
    body: 'AWS us-east-1. Data never leaves US borders. No offshore contractors.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
      </svg>
    ),
  },
  {
    title: 'Full audit log',
    body: 'Every read, write, and export logged with user, timestamp, and IP. Exportable to your compliance team.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 7h18v12H3zM3 7l9-4 9 4" />
        <path d="M8 11h8M8 15h5" />
      </svg>
    ),
  },
  {
    title: 'Data portability',
    body: 'Export all your notes as PDF, DOCX, or FHIR JSON in one click. No lock-in. Your patients, your data.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 6h16M4 12h10M4 18h16" />
        <path d="M18 9l3 3-3 3" />
      </svg>
    ),
  },
];

export function Security() {
  return (
    <section className="features" id="security" style={{ padding: '32px 0 96px' }}>
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">05 / Trust</div>
          <h2 className="section-title">We handle PHI the way you would.</h2>
          <p className="section-sub">
            Every byte is encrypted in transit and at rest. Nothing you send is used to train
            foundation models. A signed BAA is available on request. You own the audit log and
            you can delete any visit, any time.
          </p>
          <div style={{ marginTop: 24 }}>
            <a href="/security" className="btn btn-secondary">
              Read security whitepaper
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M5 12h14M13 5l7 7-7 7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </a>
          </div>
        </div>

        <div className="feat-grid reveal">
          {ITEMS.map((item) => (
            <div key={item.title} className="feat">
              <div className="feat-icon">{item.icon}</div>
              <h4 className="feat-title">{item.title}</h4>
              <p className="feat-copy">{item.body}</p>
              {item.logos && (
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    marginTop: 12,
                  }}
                >
                  {item.logos.map((l) => (
                    <span
                      key={l}
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10.5,
                        color: 'var(--color-linear-text-3)',
                        padding: '2px 7px',
                        border: '1px solid var(--color-linear-hairline)',
                        borderRadius: 4,
                        letterSpacing: '0.04em',
                      }}
                    >
                      {l}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
