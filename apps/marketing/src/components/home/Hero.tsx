import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * Hero — Phase 5 Linear V1 (Faithful).
 *
 * Centered hero on dark canvas (no full-bleed cinematic photo, no word-stagger).
 * Sage-tinted "New" pill eyebrow, large Inter 600 headline, sage primary CTA
 * + sage outline secondary, mono uppercase trust strip below.
 *
 * Source of truth: docs/design-directions-v8-linear/landing-v1.html lines 796–812.
 *
 * Phase 4's cinematic dusk-clinician photo + `.av1-word` stagger + scroll DOF
 * blur are removed entirely. The HeroAnimator client component is gone with
 * them — Linear V1 is calm and immediate, no hold-and-reveal sequence.
 */
export function Hero() {
  return (
    <section className="hero">
      <div className="container">
        <div className="hero-eyebrow">
          <span className="pill-tag">New</span>
          <span>Specialty packs for Cardiology &amp; Psych are live</span>
          <span className="pill-arrow">›</span>
        </div>
        <h1 className="hero-title">The medical scribe that practitioners actually use.</h1>
        <p className="hero-sub">
          Real-time SOAP drafting, ICD-10 + CPT recommendations, and signed notes in under
          ninety seconds. Built for US clinicians, audited end-to-end.
        </p>
        <div className="hero-ctas">
          <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg">
            Begin a visit
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M5 12h14M13 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
          <a href="#demo" className="btn btn-secondary btn-lg">
            Watch a 90-second demo
          </a>
        </div>
        <div className="hero-trust">
          Made for US clinicians<span className="dot">·</span>HIPAA<span className="dot">·</span>BAA
          on file
        </div>
      </div>
    </section>
  );
}
