import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * Final CTA — Phase 7 v6 (Apple Product).
 *
 * 90vh stage with a sage radial spotlight behind the headline. Glow primary
 * "Start 14-day free trial" + secondary "Book a 15-min demo".
 */
export function FinalCTA() {
  return (
    <section className="final-cta">
      <div className="container final-cta-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">One more thing</span>
        </div>
        <h2 className="stage-h2 reveal delay-1" style={{ marginBottom: 32 }}>
          Your next patient <span className="quiet">shouldn&apos;t wait.</span>
        </h2>
        <p className="stage-sub reveal delay-2">
          Set it up in minutes. Sign your first AI-drafted note the same day. No sales call, no
          demo gauntlet, no procurement. Cancel with one click if it doesn&apos;t earn its keep.
        </p>

        <div className="hero-ctas reveal delay-3">
          <a href={APP_SIGNUP_URL} className="btn btn-lg btn-glow">
            Start 14-day free trial
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
          <a href="/demo" className="btn btn-lg btn-secondary">
            Book a 15-min demo
          </a>
        </div>
      </div>
    </section>
  );
}
