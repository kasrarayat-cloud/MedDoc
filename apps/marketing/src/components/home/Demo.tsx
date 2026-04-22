import { QuillMark } from './QuillMark';

const WAVE_HEIGHTS = [14, 22, 18, 26, 12, 24, 16, 22, 14, 20, 18, 24, 16, 22];
const WAVE_DELAYS = ['-.1s', '-.3s', '-.2s', '-.6s', '-.1s', '-.4s', '-.7s', '-.2s', '-.9s', '-.3s', '-.5s', '-.1s', '-.8s', '-.2s'];

export function Demo() {
  return (
    <section className="block compact" id="demo">
      <div className="container">
        <div className="sec-label">
          <span className="num">§ 04 / SEE IT</span>
          <span>Live demo</span>
        </div>
        <div className="section-head reveal">
          <h2>
            Real visit. Real note. <em>Ninety seconds.</em>
          </h2>
          <p className="lede">
            A three‑month HTN follow‑up, transcribed and documented live. Patient data is synthetic.
          </p>
        </div>

        <div className="demo-showcase reveal">
          <div className="macbook">
            <div className="macbook-screen">
              <div className="macbook-bezel">
                <span className="macbook-cam" />
                <div className="demo-screen">
                  <aside className="demo-sidebar">
                    <div className="logo-row">
                      <span className="brand-quill" style={{ width: 22, height: 22 }}>
                        <QuillMark gradientId="demoQuill" />
                      </span>
                      QuillMD
                    </div>
                    <div className="nav-item active">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="4" y="4" width="16" height="16" rx="2" />
                        <path d="M8 9h8M8 13h6" />
                      </svg>
                      Visits
                    </div>
                    <div className="nav-item">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="8" />
                        <path d="M12 8v8M8 12h8" />
                      </svg>
                      Templates
                    </div>
                    <div className="nav-item">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M4 7h16M4 12h16M4 17h10" />
                      </svg>
                      Codes
                    </div>
                    <div className="nav-item">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 8v4l3 2" />
                        <circle cx="12" cy="12" r="9" />
                      </svg>
                      History
                    </div>
                    <div className="sec-label2">Today</div>
                    <div className="visit-row live">
                      <span>Okafor, R · 54F</span>
                      <span>live</span>
                    </div>
                    <div className="visit-row">
                      <span>Morales, J · 68M</span>
                      <span>10:15</span>
                    </div>
                    <div className="visit-row">
                      <span>Chen, M · 41F</span>
                      <span>09:30</span>
                    </div>
                    <div className="visit-row">
                      <span>Abboud, T · 29M</span>
                      <span>09:00</span>
                    </div>
                  </aside>
                  <main className="demo-main">
                    <div className="demo-pane">
                      <h5>
                        Transcript{' '}
                        <span className="tag">
                          <span className="d" />
                          Live · Deepgram
                        </span>
                      </h5>
                      <div className="demo-wave">
                        {WAVE_HEIGHTS.map((h, i) => (
                          <i
                            key={i}
                            style={
                              { '--h': `${h}px`, animationDelay: WAVE_DELAYS[i] } as React.CSSProperties
                            }
                          />
                        ))}
                      </div>
                      <div className="demo-transcript">
                        <p className="doc">
                          <span className="sp">Dr. Marchetti</span>So your home BP log is averaging{' '}
                          <span className="hl">128/82</span>. Any new side effects from the
                          lisinopril?
                        </p>
                        <p>
                          <span className="sp">Patient</span>Actually — I&apos;ve had this{' '}
                          <span className="hl">dry cough for two weeks</span> now.
                        </p>
                        <p className="doc">
                          <span className="sp">Dr. Marchetti</span>Let&apos;s switch you to
                          losartan, same dose.
                        </p>
                      </div>
                    </div>
                    <div className="demo-pane">
                      <h5>
                        SOAP · Okafor, R.{' '}
                        <span className="tag" style={{ color: 'var(--accent-bright)' }}>
                          MRN 00291
                        </span>
                      </h5>
                      <div style={{ height: 28 }} />
                      <div className="demo-soap">
                        <div className="demo-soap-row">
                          <span className="l">Subj</span>
                          <span>
                            3‑mo HTN f/u. <strong>Lisinopril</strong> adherence good. Home BP
                            128/82. <strong>Dry cough × 2 wk</strong>, worse nocturnally.
                          </span>
                        </div>
                        <div className="demo-soap-row">
                          <span className="l">Obj</span>
                          <span>BP 132/84 L arm · HR 72 reg · BMI 27.4 · RRR · Lungs clear.</span>
                        </div>
                        <div className="demo-soap-row">
                          <span className="l">Assess</span>
                          <span>
                            HTN, controlled <span className="demo-code">I10</span> · ACE‑I cough{' '}
                            <span className="demo-code">R05.9</span>
                          </span>
                        </div>
                        <div className="demo-soap-row">
                          <span className="l">Plan</span>
                          <span>
                            D/C lisinopril · <strong>Losartan 50mg PO qd</strong>{' '}
                            <span className="demo-rx">Rx draft</span> · BMP + lipid 4 wk · F/U 8 wk.
                          </span>
                        </div>
                        <div className="demo-soap-row">
                          <span className="l">CPT</span>
                          <span>
                            <span className="demo-code">99213</span> Est. patient, low MDM
                          </span>
                        </div>
                      </div>
                    </div>
                  </main>
                </div>
              </div>
            </div>
            <div className="macbook-base" />
          </div>
        </div>
      </div>
    </section>
  );
}
