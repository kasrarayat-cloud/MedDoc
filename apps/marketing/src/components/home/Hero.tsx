import { APP_SIGNUP_URL } from '@/lib/constants';
import { HeroAnimator } from './HeroAnimator';

/**
 * Hero — Phase 4 Apple Cinematic treatment.
 *
 * Full-bleed hero (`min-height: 100vh`) with the gpt-image-1 cinematic
 * dusk-clinician photo as a background, cream gradient overlay for text
 * contrast, and a sage radial wash for warmth. Headline blurs in
 * word-by-word with a 600 ms hold between line 1 ("Stop writing notes.")
 * and line 2 ("Start practicing medicine.") — the italic word
 * "practicing" picks up a sage-bright glow via `.av1-word.glow`.
 *
 * Animation timeline + visual treatment is lifted from
 * `docs/design-directions-v6/studio-variations/landing-11-anim-1.html`.
 * The `<HeroAnimator>` client component runs the timeline + scroll
 * parallax handler so this file stays a server component (and the photo
 * backdrop renders on the SSR pass with no FOUC).
 */
export function Hero() {
  return (
    <section className="qm-cin-hero">
      <HeroAnimator />
      <div className="qm-cin-bg" id="qm-cin-bg" aria-hidden />
      <div className="qm-cin-inner">
        <div>
          <span className="qm-cin-eyebrow av1-fade" id="av1-eyebrow">
            <span className="dot" /> Made for clinicians who chart at 9 PM
          </span>
          <h1
            className="qm-cin-headline"
            aria-label="Stop writing notes. Start practicing medicine."
          >
            <span className="qm-cin-line">
              <span className="av1-word" data-d="0">
                Stop&nbsp;
              </span>
              <span className="av1-word" data-d="120">
                writing&nbsp;
              </span>
              <span className="av1-word" data-d="240">
                notes.
              </span>
            </span>
            <span className="qm-cin-line">
              <span className="av1-word" data-d="900">
                Start&nbsp;
              </span>
              <span className="av1-word em glow" data-d="1020">
                practicing&nbsp;
              </span>
              <span className="av1-word" data-d="1140">
                medicine.
              </span>
            </span>
          </h1>
          <p className="qm-cin-standfirst av1-fade">
            QuillMD listens, drafts your SOAP, suggests the codes, flags the medication
            interactions, and waits patiently while you sign.
          </p>
          <div className="qm-cin-actions">
            <a href={APP_SIGNUP_URL} className="btn btn-primary btn-lg av1-cta">
              Begin a visit
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14M13 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
            <a href="#how" className="btn btn-ghost btn-lg av1-cta">
              See how it works
            </a>
          </div>
          <div className="qm-cin-meta av1-fade">
            <span className="qm-cin-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline
                  points="20 6 9 17 4 12"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              HIPAA-compliant
            </span>
            <span className="qm-cin-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline
                  points="20 6 9 17 4 12"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              BAA on file
            </span>
            <span className="qm-cin-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline
                  points="20 6 9 17 4 12"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              US-hosted · audit-logged
            </span>
          </div>
        </div>

        <aside className="qm-cin-soap-card av1-card" id="av1-soap-card" aria-hidden="true">
          <div className="qm-cin-soap-head">
            <span>SOAP · Family Medicine</span>
            <span className="badge">Drafted 0:38</span>
          </div>
          <div className="qm-cin-soap-line">
            <span className="qm-cin-soap-letter">S</span>
            <span className="qm-cin-soap-text">
              42F · acute bronchitis · J20.9. Productive cough × 8 days, low-grade fever.
            </span>
          </div>
          <div className="qm-cin-soap-line">
            <span className="qm-cin-soap-letter">O</span>
            <span className="qm-cin-soap-text">
              Lungs clear bilaterally, no wheeze. Heart RRR. Sat 97% RA.
            </span>
          </div>
          <div className="qm-cin-soap-line">
            <span className="qm-cin-soap-letter">A</span>
            <span className="qm-cin-soap-text">
              Acute bronchitis, likely viral. No clinical features of pneumonia.
            </span>
          </div>
          <div className="qm-cin-soap-line">
            <span className="qm-cin-soap-letter">P</span>
            <span className="qm-cin-soap-text">
              Symptomatic care; albuterol PRN. Follow-up 7 days if persistent.
            </span>
          </div>
        </aside>
      </div>
    </section>
  );
}
