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
    body: 'One tap on your phone, laptop, or browser. Real‑time transcription via Deepgram Nova‑3 Medical. Consent prompt optional.',
    detail: '~1 tap · Live transcription',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <rect x="9" y="3" width="6" height="12" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      </svg>
    ),
  },
  {
    idx: 2,
    title: 'AI writes the chart',
    body: 'SOAP, ICD‑10 / CPT, Rx drafts, referral letters, patient summary — in your voice, your templates, your specialty.',
    detail: '~30 seconds · 8 specialty templates',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 3 L 9 15 M7 21 l-3-3 4-1 M14 4 l6 6" />
      </svg>
    ),
  },
  {
    idx: 3,
    title: 'Review & sign',
    body: 'Edit inline, sign, push to your EHR or export PDF / DOCX. Patient summary can auto‑send to the portal.',
    detail: '1 click · PDF · DOCX · EHR export',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 6 9 17l-5-5" />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section className="block" id="how">
      <div className="container">
        <div className="sec-label">
          <span className="num">§ 01 / METHOD</span>
          <span>How it works</span>
        </div>
        <div className="section-head reveal">
          <h2>
            Three steps. <em>No workflow lift.</em>
          </h2>
          <p className="lede">
            The flow you already know — just with charting done by the time the patient stands up.
          </p>
        </div>

        <div className="how-steps">
          {STEPS.map((s) => (
            <div key={s.idx} className="how-step reveal">
              <div className="marker">
                <span className="idx">{s.idx}</span>
                {s.icon}
              </div>
              <h4>{s.title}</h4>
              <p>{s.body}</p>
              <span className="detail">{s.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
