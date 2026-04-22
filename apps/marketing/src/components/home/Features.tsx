type Feature = {
  title: string;
  body: string;
  chip: string;
  icon: React.ReactNode;
};

const FEATURES: Feature[] = [
  {
    title: 'SOAP notes',
    body: 'Structured subjective, objective, assessment, and plan in your format. Adopts your shorthand over the first few visits.',
    chip: '8 specialties',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path d="M8 9h8M8 13h8M8 17h5" />
      </svg>
    ),
  },
  {
    title: 'ICD‑10 & CPT',
    body: 'Suggested codes with confidence scores. Accept, edit, or swap in one click. Never auto‑submitted without review.',
    chip: 'Billable day‑one',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 7h16M4 12h16M4 17h10" />
      </svg>
    ),
  },
  {
    title: 'Rx drafts',
    body: 'Medication, dose, frequency, duration — pre‑filled from the conversation. Pipes to your e‑prescribing tool.',
    chip: 'e‑Rx ready',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3v18M7 8h10M7 16h10" />
      </svg>
    ),
  },
  {
    title: 'Referral letters',
    body: 'Polished letters addressed to the specialist of your choice. Editable, signed, exportable as PDF.',
    chip: 'PDF · DOCX',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a4 4 0 01-4 4H7l-4 4V7a4 4 0 014-4h10a4 4 0 014 4z" />
      </svg>
    ),
  },
  {
    title: 'Patient summaries',
    body: 'Plain‑language recap in the patient\u2019s reading level. Auto‑send via email or portal. Cuts callbacks.',
    chip: 'Multilingual',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    title: 'Polished exports',
    body: 'Pixel‑perfect PDF and editable DOCX. Your letterhead, your signature, your logo. Ready to file.',
    chip: 'Your brand',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </svg>
    ),
  },
];

export function Features() {
  return (
    <section className="block compact" id="features">
      <div className="container">
        <div className="sec-label">
          <span className="num">§ 02 / WHAT YOU GET</span>
          <span>Features</span>
        </div>
        <div className="section-head reveal">
          <h2>
            Everything you&apos;d <em>otherwise do at 9&nbsp;pm.</em>
          </h2>
          <p className="lede">
            Six things. All core. All included. No add‑ons, seat upgrades, or &ldquo;Contact
            Sales&rdquo; tiers.
          </p>
        </div>

        <div className="feat-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feat reveal">
              <div className="ico">{f.icon}</div>
              <h4>{f.title}</h4>
              <p>{f.body}</p>
              <div className="foot">
                <span>CORE</span>
                <span className="chip">{f.chip}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
