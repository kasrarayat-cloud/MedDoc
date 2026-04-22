type QA = { q: string; a: React.ReactNode };

const ITEMS: QA[] = [
  {
    q: 'Is QuillMD HIPAA compliant?',
    a: "Yes. We operate under HIPAA's technical, administrative, and physical safeguards. A signed BAA is available on request — email me and I'll send one over. We're working with model vendors (Anthropic, OpenAI, Deepgram) under their standard no-retention / no-training terms for API data, and will formalize BAAs with them as the business scales.",
  },
  {
    q: 'How does it integrate with my EHR?',
    a: "Copy/paste works with every EHR today. One‑click push to popular EHRs is on the roadmap — tell me which EHR you use and I'll prioritize it.",
  },
  {
    q: 'Can I cancel anytime?',
    a: "Yes. One click, in your settings. No retention team will call you. You'll keep access through the end of the current month, then you're done. All your notes stay exportable forever.",
  },
  {
    q: 'Is my patient data secure?',
    a: 'TLS 1.3 in transit, AES‑256 at rest, per‑tenant key isolation, keys rotate every 90 days. US‑hosted on AWS us‑east‑1. Zero data residency outside the US. Full audit log exportable on demand.',
  },
  {
    q: 'Do I need to train it?',
    a: "No. It's usable from the first visit. The template adapts to your shorthand and plan style over the first 5–10 visits. You can also paste a sample note and have it calibrate immediately.",
  },
  {
    q: 'What specialties work best today?',
    a: "Primary care, cardiology, pain management, urgent care, pediatrics, dermatology, psychiatry, and orthopedics — all with curated templates. Others work on the generic template. If yours isn't listed, email me — I'll usually have a template ready within a week.",
  },
  {
    q: 'Who is behind QuillMD?',
    a: "Solo founder, son of an internist who dictated until midnight for 30 years. Built this so the next generation doesn't have to.",
  },
];

export function FAQ() {
  return (
    <section className="block compact faq" id="faq">
      <div className="container">
        <div className="sec-label">
          <span className="num">§ 07 / QUESTIONS</span>
          <span>FAQ</span>
        </div>
        <div className="faq-wrap">
          <div className="reveal">
            <span className="eyebrow">The usual, directly answered</span>
            <h2>
              Short answers <br />
              to <em>fair questions.</em>
            </h2>
            <p className="lede">
              Can&apos;t find yours? Email <a href="mailto:kasra@quillmd.com">kasra@quillmd.com</a>.
              I read every one.
            </p>
          </div>
          <div className="faq-list reveal">
            {ITEMS.map((item, i) => (
              <details key={item.q} className="faq-item" open={i === 0}>
                <summary>
                  {item.q}
                  <span className="faq-plus">+</span>
                </summary>
                <div className="faq-a">{item.a}</div>
              </details>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
