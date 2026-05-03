import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * Pricing — Phase 7 v6 (Apple Product).
 *
 * Single bold card on a stage. Floating "Solo physician" badge above, sage
 * gradient $49 amount, 10 features in a 2-col bullet list, glow CTA + mono
 * caption. Padding shrinks at ≤640px (handled in landing.css).
 */
const FEATURES = [
  'Unlimited visits, no per-note caps',
  'Real-time SOAP drafting',
  'ICD-10 and CPT recommendations',
  'Specialty packs (all 12)',
  'HIPAA BAA, on file',
  'US-hosted infrastructure',
  'Cmd-K command palette',
  'EHR-formatted exports (Epic, Athena, Cerner, eCW)',
  'DOCX and PDF generation',
  'Email and Slack support',
];

export function Pricing() {
  return (
    <section className="stage" id="pricing">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">06 / Pricing</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          One tier. Unlimited visits. <span className="quiet">No surprises.</span>
        </h2>

        <div className="pricing-card reveal delay-2">
          <span className="pricing-badge">Solo physician</span>
          <div className="price">
            <span className="price-amount">$49</span>
            <span className="price-unit">/ month per physician</span>
          </div>
          <p className="price-sub">Everything below, billed monthly. Cancel anytime.</p>
          <ul className="price-list">
            {FEATURES.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <div className="price-cta">
            <a href={APP_SIGNUP_URL} className="btn btn-lg btn-glow">
              Start your trial →
            </a>
            <span className="price-caption">14 days free · no card</span>
          </div>
        </div>
      </div>
    </section>
  );
}
