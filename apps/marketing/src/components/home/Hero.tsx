'use client';

import { useRef } from 'react';
import { APP_SIGNUP_URL } from '@/lib/constants';
import { useWordStagger } from '@/hooks/useWordStagger';
import { HeroOrb } from './HeroOrb';

export function Hero() {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useWordStagger(titleRef);

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

          <h1 ref={titleRef} className="hero-title" id="heroTitle">
            <span>Stop writing notes.</span>
            <br />
            <em>Start practicing medicine.</em>
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
