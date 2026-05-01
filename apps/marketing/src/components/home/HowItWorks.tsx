/**
 * HowItWorks — Linear V1 (Faithful).
 *
 * Three-step grid on a hairline-bordered surface, sage step number + sage
 * icon + Inter 600 title + body copy + mono caption. Mirrors the .feature
 * grid pattern from landing-v1.html lines 919-971 but in 3 columns.
 */
type Step = {
  idx: number;
  title: string;
  body: string;
  detail: string;
  icon: React.ReactNode;
};

const STEPS: Step[] = [
  {
    idx: 1,
    title: 'Record the visit',
    body: 'One tap on your phone, laptop, or browser. Real-time transcription via Deepgram Nova-3 Medical. Consent prompt optional.',
    detail: '~1 tap · Live transcription',
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      >
        <rect x="9" y="3" width="6" height="12" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </svg>
    ),
  },
  {
    idx: 2,
    title: 'AI writes the chart',
    body: 'SOAP, ICD-10 / CPT, Rx drafts, referral letters, patient summary — in your voice, your templates, your specialty.',
    detail: '~30 seconds · 8 specialty templates',
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 3 L 9 15 M7 21 l-3-3 4-1 M14 4 l6 6" />
      </svg>
    ),
  },
  {
    idx: 3,
    title: 'Review & sign',
    body: 'Edit inline, sign, push to your EHR or export PDF / DOCX. Patient summary can auto-send to the portal.',
    detail: '1 click · PDF · DOCX · EHR export',
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M20 6 9 17l-5-5" />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section className="features" id="how" style={{ padding: '32px 0 96px' }}>
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">01 / Method</div>
          <h2 className="section-title">Three steps. No workflow lift.</h2>
          <p className="section-sub">
            The flow you already know — just with charting done by the time the patient stands up.
          </p>
        </div>

        <div className="feat-grid">
          {STEPS.map((s) => (
            <div key={s.idx} className="feat reveal">
              <div className="feat-icon">{s.icon}</div>
              <h4 className="feat-title">
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    color: 'var(--color-linear-sage)',
                    marginRight: 8,
                    letterSpacing: '0.04em',
                  }}
                >
                  0{s.idx}
                </span>
                {s.title}
              </h4>
              <p className="feat-copy">{s.body}</p>
              <span
                style={{
                  display: 'inline-block',
                  marginTop: 12,
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10.5,
                  color: 'var(--color-linear-text-3)',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                }}
              >
                {s.detail}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
