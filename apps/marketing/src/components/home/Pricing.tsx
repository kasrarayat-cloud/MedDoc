import { APP_SIGNUP_URL } from '@/lib/constants';

const FEATURES = [
  'Unlimited patient visits',
  'SOAP, ICD‑10/CPT, Rx, referrals, patient summaries',
  'Real‑time transcription with Deepgram Nova‑3 Medical',
  '8 specialty templates · learns your style',
  'Signed BAA · HIPAA‑aligned · US hosted',
  'PDF / DOCX exports with your letterhead',
  'Email support · live chat during business hours',
];

function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

export function Pricing() {
  return (
    <section className="pricing" id="pricing">
      <div className="container pricing-inner">
        <div className="sec-label" style={{ maxWidth: 900, margin: '0 auto 40px' }}>
          <span className="num">§ 06 / PRICING</span>
          <span>One plan · Flat · Cancel anytime</span>
        </div>
        <h2 className="reveal">
          A single plan, <em>for a single doctor.</em>
        </h2>
        <p className="lede reveal">
          No seat tiers. No per‑visit fees. No annual commitment. Your budget should be as
          predictable as your schedule.
        </p>

        <div className="price-hero reveal">
          <span className="digit-stack">
            <span className="currency">$</span>
            <span className="digits">49</span>
            <span className="per">/ month</span>
          </span>
        </div>
        <div className="price-tagline reveal">
          Flat rate. <em>Unlimited visits.</em> Cancel any time.
        </div>

        <div className="price-card reveal">
          <ul className="price-features">
            {FEATURES.map((f) => (
              <li key={f}>
                <Check />
                {f}
              </li>
            ))}
          </ul>
          <div className="price-cta-row">
            <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg">
              Start 14‑day free trial <span className="arrow">→</span>
            </a>
            <a href="#demo" className="btn btn-outline btn-lg">
              Watch demo
            </a>
          </div>
          <div className="price-guarantee">No credit card · No sales call · Cancel with one click</div>
        </div>
      </div>
    </section>
  );
}
