import { APP_SIGNUP_URL } from '@/lib/constants';

export function FinalCTA() {
  return (
    <section className="final-cta">
      <div className="inner-quill" aria-hidden>
        <svg viewBox="0 0 200 200" fill="none">
          <defs>
            <linearGradient id="bigQ" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="currentColor" stopOpacity="0.9" />
              <stop offset="1" stopColor="currentColor" stopOpacity="0.1" />
            </linearGradient>
          </defs>
          <path
            d="M160 30 C 110 40, 60 70, 40 140 L 35 165 L 60 155 C 130 135, 170 90, 175 40 Z"
            stroke="url(#bigQ)"
            strokeWidth="1.2"
            fill="none"
          />
          <path d="M55 150 L 130 80" stroke="currentColor" strokeOpacity="0.4" strokeWidth="0.8" />
        </svg>
      </div>
      <div className="container">
        <span className="eyebrow reveal">§ One more thing</span>
        <h2 className="reveal">
          Your next patient <em>shouldn&apos;t wait.</em>
        </h2>
        <p className="reveal">
          Set it up in minutes. Sign your first AI‑drafted note the same day. Keep the violet glow —
          or match it to your practice colors later.
        </p>
        <div className="final-actions reveal">
          <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg">
            Start 14‑day free trial <span className="arrow">→</span>
          </a>
          <a href="/demo" className="btn btn-outline btn-lg">
            Book a 15‑min demo
          </a>
        </div>
      </div>
    </section>
  );
}
