/**
 * Demo product preview — Linear V1 (Faithful).
 *
 * Replaces the MacBook frame with Linear V1's product chrome: 3-dot window
 * controls, mono visit-id tabs, sage live-dot indicator, two-pane body
 * (transcript + SOAP). Mirrors landing-v1.html lines 815-915 byte-for-byte
 * in markup, leveraging .product/.product-chrome/.pane/.soap-* styling
 * already in landing.css.
 */
export function Demo() {
  return (
    <section className="features" id="demo" style={{ padding: '32px 0 96px' }}>
      <div className="container">
        <div className="section-head reveal">
          <div className="section-eyebrow">04 / See it</div>
          <h2 className="section-title">Real visit. Real note. Ninety seconds.</h2>
          <p className="section-sub">
            A three-month HTN follow-up, transcribed and documented live. Patient data is
            synthetic.
          </p>
        </div>

        <div className="product reveal">
          <div className="product-chrome">
            <div className="chrome-dots">
              <span className="chrome-dot" />
              <span className="chrome-dot" />
              <span className="chrome-dot" />
            </div>
            <div className="chrome-tabs">
              <span className="chrome-tab">visit-7K2A</span>
              <span className="chrome-tab active">live</span>
              <span className="chrome-tab">soap.md</span>
            </div>
            <div className="chrome-meta">
              <span className="live-dot" />
              <span>recording · 01:42</span>
            </div>
          </div>

          <div className="product-body">
            <div className="pane transcript">
              <div className="pane-label">
                <span>Transcript</span>
                <span className="meta">Deepgram · diarized</span>
              </div>
              <div className="turn">
                <span className="turn-speaker">Pt</span>
                <span className="turn-text">
                  It started about three days ago. Dull, behind the sternum, worse when I lie down.
                </span>
              </div>
              <div className="turn">
                <span className="turn-speaker dr">Dr</span>
                <span className="turn-text">
                  Any radiation to the jaw or arm, shortness of breath?
                </span>
              </div>
              <div className="turn">
                <span className="turn-speaker">Pt</span>
                <span className="turn-text">
                  No jaw. A little tight when I climb stairs, but I have asthma.
                </span>
              </div>
              <div className="turn">
                <span className="turn-speaker dr">Dr</span>
                <span className="turn-text">
                  BP one-twenty-eight over eighty-two, heart rate seventy-six, regular rhythm.
                  Lungs clear bilaterally.
                </span>
              </div>
              <div className="turn">
                <span className="turn-speaker">Pt</span>
                <span className="turn-text">
                  My albuterol — I think I was using it more last week.
                </span>
              </div>
              <div className="turn">
                <span className="turn-speaker dr">Dr</span>
                <span className="turn-text">
                  Let&apos;s get an ECG today and a follow-up next Tuesday. I&apos;ll also re-check
                  your peak flow
                  <span className="typing-cursor" />
                </span>
              </div>
            </div>

            <div className="pane">
              <div className="pane-label">
                <span>SOAP draft</span>
                <span className="meta">claude-sonnet-4.6 · validated</span>
              </div>
              <div className="soap-section lit">
                <div className="soap-head">
                  <span className="soap-letter">S</span>
                  <span className="soap-name">Subjective</span>
                  <span className="soap-status">drafted</span>
                </div>
                <div className="soap-body">
                  3-day retrosternal chest discomfort, positional, non-radiating. Mild exertional
                  dyspnea on stairs. Increased albuterol use over past week.
                </div>
              </div>
              <div className="soap-section lit">
                <div className="soap-head">
                  <span className="soap-letter">O</span>
                  <span className="soap-name">Objective</span>
                  <span className="soap-status">drafted</span>
                </div>
                <div className="soap-body">
                  BP 128/82, HR 76 reg., RR 16, SpO₂ 98% RA. Lungs CTAB. No JVD, no peripheral
                  edema.
                </div>
              </div>
              <div className="soap-section lit">
                <div className="soap-head">
                  <span className="soap-letter">A</span>
                  <span className="soap-name">Assessment</span>
                  <span className="soap-status">coded</span>
                </div>
                <div className="soap-body">
                  Atypical chest pain, likely esophageal vs. musculoskeletal. Asthma —
                  uncontrolled per albuterol overuse.
                </div>
                <div className="soap-code-row">
                  <span className="soap-code">R07.89</span>
                  <span className="soap-code">J45.40</span>
                </div>
              </div>
              <div className="soap-section lit">
                <div className="soap-head">
                  <span className="soap-letter">P</span>
                  <span className="soap-name">Plan</span>
                  <span className="soap-status">complete</span>
                </div>
                <div className="soap-body">
                  ECG today. Trial PPI × 2 wks. Step-up ICS, peak-flow review. F/U Tue.
                </div>
                <div className="soap-code-row">
                  <span className="soap-code">99214</span>
                  <span className="soap-code">93000</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
