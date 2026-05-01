/**
 * Features grid — Linear V1 (Faithful).
 *
 * Six-cell hairline-divided grid on `--color-linear-surface-1`. Sage icons,
 * Inter 600 title, body copy, no chip. Mirrors landing-v1.html lines
 * 919-971; .feat-grid styling is in landing.css.
 */
type Feature = {
  title: string;
  body: string;
  icon: React.ReactNode;
};

const FEATURES: Feature[] = [
  {
    title: 'Real-time SOAP draft',
    body: 'Subjective, Objective, Assessment, Plan light up section-by-section as the visit unfolds. Edit inline; sign when ready.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 12h3l3-9 4 18 3-9h5" />
      </svg>
    ),
  },
  {
    title: 'ICD-10 + CPT auto-coded',
    body: 'Diagnosis and procedure recommendations with confidence scores; the doctor approves or edits in one click.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M7 8h10M7 12h6M7 16h8" />
      </svg>
    ),
  },
  {
    title: 'HIPAA, BAA on file',
    body: 'Audit-logged at every layer. End-to-end encryption. PHI never leaves our US-hosted environment.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2L4 6v6c0 5 3.5 9 8 10 4.5-1 8-5 8-10V6l-8-4z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    title: 'Specialty-aware',
    body: 'Family Medicine, Cardiology, Pediatrics, Psychiatry, Endo. The model adapts to your domain, not the reverse.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2" />
      </svg>
    ),
  },
  {
    title: 'Cmd-K everywhere',
    body: 'Jump to any patient, any visit, any specialty pack. Never more than two keystrokes from the next note.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <path d="M6 9h2v2H6zM10 9h2v2h-2zM14 9h2v2h-2zM6 13h12v2H6z" />
      </svg>
    ),
  },
  {
    title: 'Audit-logged + US-hosted',
    body: 'Every action emits an immutable event. Servers in us-east-1. Your data never crosses a border.',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 12c0 5-4 9-9 9s-9-4-9-9 4-9 9-9c2.5 0 4.7 1 6.4 2.6" />
        <path d="M21 4v5h-5" />
      </svg>
    ),
  },
];

export function Features() {
  return (
    <section className="features" id="features">
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">02 / Built for the visit</div>
          <h2 className="section-title">
            Everything a working clinic needs. Nothing it doesn&apos;t.
          </h2>
          <p className="section-sub">
            Six features that move the cursor from end-of-visit to next-patient.
          </p>
        </div>

        <div className="feat-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feat reveal">
              <div className="feat-icon">{f.icon}</div>
              <h4 className="feat-title">{f.title}</h4>
              <p className="feat-copy">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
