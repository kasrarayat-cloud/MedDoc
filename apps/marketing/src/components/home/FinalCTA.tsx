import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * Final CTA — Linear V1 (Faithful).
 *
 * Centered eyebrow + Inter 600 heading + body copy + sage primary CTA
 * (Begin a visit) + sage outline CTA (Book demo). No more big-Q SVG
 * background; Linear V1 keeps decoration to the body::before radial
 * spotlight in landing.css.
 */
export function FinalCTA() {
  return (
    <section className="final-cta">
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">One more thing</div>
          <h2 className="section-title">Your next patient shouldn&apos;t wait.</h2>
          <p className="section-sub">
            Set it up in minutes. Sign your first AI-drafted note the same day. No sales call,
            no demo gauntlet, no procurement. Cancel with one click if it doesn&apos;t earn its
            keep.
          </p>
        </div>
        <div
          className="reveal"
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg">
            Start 14-day free trial
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
          <a href="/demo" className="btn btn-secondary btn-lg">
            Book a 15-min demo
          </a>
        </div>
      </div>
    </section>
  );
}
