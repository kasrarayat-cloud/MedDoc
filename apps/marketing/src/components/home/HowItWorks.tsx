/**
 * How it works — Phase 7 v6 (Apple Product).
 *
 * Intro stage + 3 sequential full-stage rows (text + visual). Steps 01 / 03
 * align text to the left, step 02 flips. Each visual is a custom panel:
 *  - 01: orb + microphone icon overlay + recording badge + animated waveform
 *  - 02: doc-line ladder (animated draws)
 *  - 03: dimmed orb + sage check ring
 *
 * Animations: orb breathing, wave pulse, doc-line draw, ring pulse — all CSS.
 */
export function HowItWorks() {
  return (
    <section id="how">
      <div className="stage" style={{ minHeight: '60vh', padding: '60px 0 30px' }}>
        <div className="container stage-inner">
          <div className="reveal">
            <span className="eyebrow-tiny">01 / Method</span>
          </div>
          <h2 className="stage-h2 reveal delay-1">
            Three steps. <span className="quiet">No workflow lift.</span>
          </h2>
          <p className="stage-sub reveal delay-2">
            The flow you already know — just with charting done by the time the patient stands up.
          </p>
        </div>
      </div>

      <div className="how-stage">
        <div className="how-row">
          <div className="how-text reveal">
            <div className="how-num">01 · Record</div>
            <h3 className="how-h">Record the visit.</h3>
            <p className="how-body">
              One tap on your phone, laptop, or browser. Real-time transcription via Deepgram
              Nova-3 Medical. Consent prompt optional.
            </p>
            <div className="how-cap">~1 tap · Live transcription</div>
          </div>
          <div className="how-visual reveal delay-1">
            <div className="how-visual-frame">
              <div className="how-visual-orb" />
              <div className="how-rec">
                <span className="live-dot" /> recording · 00:38
              </div>
              <div className="how-icon-overlay">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <rect x="9" y="2" width="6" height="12" rx="3" />
                  <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
                  <path d="M12 19v3" />
                </svg>
              </div>
              <div className="wave">
                {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3].map(
                  (delay, i) => (
                    <span
                      key={i}
                      className="wave-bar"
                      style={{ animationDelay: `${delay}s` }}
                    />
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="how-stage">
        <div className="how-row flip">
          <div className="how-text reveal">
            <div className="how-num">02 · Draft</div>
            <h3 className="how-h">AI writes the chart.</h3>
            <p className="how-body">
              SOAP, ICD-10 / CPT, Rx drafts, referral letters, patient summary — in your voice,
              your templates, your specialty.
            </p>
            <div className="how-cap">~30 seconds · 8 specialty templates</div>
          </div>
          <div className="how-visual reveal delay-1">
            <div className="how-visual-frame">
              <div className="doc-lines">
                <div className="doc-line tiny" />
                <div className="doc-line" />
                <div className="doc-line short" />
                <div className="doc-line" />
                <div className="doc-line tiny" />
                <div className="doc-line" />
                <div className="doc-line short" />
                <div className="doc-line" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="how-stage">
        <div className="how-row">
          <div className="how-text reveal">
            <div className="how-num">03 · Sign</div>
            <h3 className="how-h">Review &amp; sign.</h3>
            <p className="how-body">
              Edit inline, sign, push to your EHR or export PDF / DOCX. Patient summary can
              auto-send to the portal.
            </p>
            <div className="how-cap">1 click · PDF · DOCX · EHR export</div>
          </div>
          <div className="how-visual reveal delay-1">
            <div className="how-visual-frame">
              <div className="how-visual-orb" style={{ opacity: 0.2 }} />
              <div className="sign-check">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
