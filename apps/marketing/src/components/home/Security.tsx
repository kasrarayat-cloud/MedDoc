/**
 * Security — Phase 7 v6 (Apple Product).
 *
 * Stage with intro + secondary CTA, then a 3-col grid of 6 cells (each
 * with a sage-tinted icon square + heading + body + optional vendor pills).
 */
type Item = {
  title: string;
  body: string;
  pills?: string[];
  icon: React.ReactNode;
};

const ITEMS: Item[] = [
  {
    title: 'HIPAA-aligned',
    body:
      'Technical, administrative, and physical safeguards per 45 CFR § 164. On request BAA with your practice.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    title: 'End-to-end encryption',
    body:
      'TLS 1.3 in transit. AES-256 at rest. Per-tenant key isolation. Keys rotate every 90 days.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <rect x="3" y="11" width="18" height="11" rx="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    ),
  },
  {
    title: 'No training on your data',
    body:
      'Model vendors run under standard no-retention terms for API data. Nothing you send is used to train foundation models.',
    pills: ['Anthropic', 'OpenAI', 'Deepgram'],
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0z" />
        <path d="M3 12h18" />
        <path d="M12 3a14 14 0 0 1 0 18" />
        <path d="M12 3a14 14 0 0 0 0 18" />
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
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
        <circle cx="12" cy="10" r="3" />
      </svg>
    ),
  },
  {
    title: 'Full audit log',
    body:
      'Every read, write, and export logged with user, timestamp, and IP. Exportable to your compliance team.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M9 13h6" />
        <path d="M9 17h4" />
      </svg>
    ),
  },
  {
    title: 'Data portability',
    body:
      'Export all your notes as PDF, DOCX, or FHIR JSON in one click. No lock-in. Your patients, your data.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
    ),
  },
];

export function Security() {
  return (
    <section className="stage" id="security">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">05 / Trust</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          We handle PHI <span className="quiet">the way you would.</span>
        </h2>
        <p className="stage-sub reveal delay-2">
          Every byte is encrypted in transit and at rest. Nothing you send is used to train
          foundation models. A signed BAA is available on request. You own the audit log and you
          can delete any visit, any time.
        </p>

        <div className="reveal delay-3" style={{ marginTop: 24 }}>
          <a href="/security" className="btn btn-secondary">
            Read security whitepaper →
          </a>
        </div>

        <div className="sec-list reveal delay-4">
          {ITEMS.map((item) => (
            <div key={item.title} className="sec-cell">
              <div className="sec-icon">{item.icon}</div>
              <h3 className="sec-h">{item.title}</h3>
              <p className="sec-body">{item.body}</p>
              {item.pills && (
                <div className="sec-pills">
                  {item.pills.map((p) => (
                    <span key={p} className="sec-pill">
                      {p}
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
