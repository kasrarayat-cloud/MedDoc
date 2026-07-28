import { APP_WAITLIST_URL } from '@/lib/constants';
import { HeroVisual } from './HeroVisual';

/**
 * Hero — Phase 7 v6 (Apple Product).
 *
 * Full-viewport hero: pill eyebrow, three-line H1 with sage gradient on the
 * middle line, sub copy, glow CTA + secondary CTA, mono trust strip, then
 * the floating 3D SOAP product card below.
 */
export function Hero() {
  return (
    <section className="hero">
      <div className="container">
        <div className="hero-stack">
          <div className="hero-eyebrow">
            <span className="pill-tag">New</span>
            <span>Specialty packs for Cardiology &amp; Psych are live</span>
            <span className="pill-arrow">›</span>
          </div>

          <h1 className="hero-h1">
            <span className="accent">The medical scribe</span>
            <br />
            <span className="accent-sage">that practitioners</span>
            <br />
            <span className="accent">actually use.</span>
          </h1>

          <p className="hero-sub">
            Real-time SOAP drafting, ICD-10 + CPT recommendations, and signed notes in under
            ninety seconds. Built for US clinicians, audited end-to-end.
          </p>

          <div className="hero-ctas">
            <a href={APP_WAITLIST_URL} className="btn btn-lg btn-glow">
              Begin a visit
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M3 7h8M8 3l4 4-4 4" />
              </svg>
            </a>
            <a href="#demo" className="btn btn-lg btn-secondary">
              Watch a 90-second demo
            </a>
          </div>

          <div className="hero-trust">
            Made for US clinicians<span className="dot">·</span>HIPAA<span className="dot">·</span>
            BAA on file
          </div>
        </div>

        <HeroVisual />
      </div>
    </section>
  );
}
