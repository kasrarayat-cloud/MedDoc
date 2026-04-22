import { APP_SIGNUP_URL } from '@/lib/constants';
import { HeroOrb } from './HeroOrb';

/**
 * Split `text` into word spans with staggered `animation-delay` values so the
 * H1 fades up word-by-word on first paint. Server-rendered — no DOM mutation
 * and no hydration risk. The initial state (opacity 0, translateY) comes from
 * the `.word-anim` rule in landing.css; the `charIn` keyframe drives them to
 * final state with `forwards` fill-mode.
 */
function Staggered({
  text,
  startMs,
  stepMs = 70,
}: {
  text: string;
  startMs: number;
  stepMs?: number;
}) {
  const parts = text.split(/(\s+)/);
  let delay = startMs;
  return (
    <>
      {parts.map((part, i) => {
        if (!part) return null;
        if (/^\s+$/.test(part)) return <span key={i}>{part}</span>;
        delay += stepMs;
        return (
          <span
            key={i}
            className="word-anim"
            style={{ animationDelay: `${delay}ms` }}
          >
            {part}
          </span>
        );
      })}
    </>
  );
}

export function Hero() {
  return (
    <section className="hero">
      <div className="container hero-inner">
        <div className="hero-left">
          <div className="hero-pill reveal">
            <span className="badge">New</span>
            <span>Real‑time transcription via Deepgram Nova‑3 Medical</span>
            <span className="sep">·</span>
            <span>ICD‑10 · CPT · Rx</span>
          </div>

          <h1 className="hero-title" id="heroTitle">
            <span>
              <Staggered text="Stop writing notes." startMs={100} />
            </span>
            <br />
            <em>
              <Staggered text="Start practicing medicine." startMs={310} />
            </em>
          </h1>

          <p className="hero-sub reveal">
            QuillMD listens to the visit and hands you back a signed SOAP note, ICD‑10 / CPT codes,
            Rx drafts, referrals, and a patient summary — before your next patient knocks. Built for
            US physicians. <strong style={{ color: 'var(--fg)' }}>$49 a month. Flat.</strong>
          </p>

          <div className="hero-actions reveal">
            <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg">
              Start 14‑day free trial <span className="arrow">→</span>
            </a>
            <a href="#demo" className="btn btn-outline btn-lg">
              ▸ Watch 90s demo
            </a>
          </div>

          <div className="hero-meta reveal">
            <span>
              <span className="check">✓</span> No credit card
            </span>
            <span>
              <span className="check">✓</span> BAA available on request
            </span>
            <span>
              <span className="check">✓</span> Works with your EHR
            </span>
            <span>
              <span className="check">✓</span> Cancel any time
            </span>
          </div>
        </div>

        <HeroOrb />
      </div>

      <div className="scroll-ind" aria-hidden>
        <span>Scroll</span>
        <span className="line" />
      </div>
    </section>
  );
}
