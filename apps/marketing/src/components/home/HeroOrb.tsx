'use client';

/**
 * Glass orb with a refracted mini-app UI inside + 4 floating satellite
 * labels outside. The outer glow, rings, specular highlights, and drift
 * animation are all pure CSS (see landing.css). The orb's parallax-on-
 * cursor rotation is applied by CursorAura via #orbWrap getElementById.
 */
export function HeroOrb() {
  return (
    <div className="orb-stage" id="orbStage">
      <div className="orb-wrap" id="orbWrap">
        <div className="orb-glow" />
        <div className="orb-rings">
          <div className="ring r1" />
          <div className="ring r2" />
          <div className="ring r3" />
          <span className="tick" />
          <span className="tick" style={{ top: '50%', right: 0, left: 'auto' }} />
          <span className="tick" style={{ top: 0, left: '50%', transform: 'rotate(90deg)' }} />
        </div>
        <div className="orb">
          <div className="orb-refract">
            <div className="orb-refract-inner">
              <div className="mini-app">
                <div className="mini-topbar">
                  <span>app.quillmd.com / okafor</span>
                  <span className="rec">
                    <span className="d" /> LIVE 00:42
                  </span>
                </div>
                <div className="mini-body">
                  <div className="mini-col">
                    <span className="mini-lbl">Transcript</span>
                    <div className="mini-wave">
                      {[10, 14, 8, 12, 14, 9, 13, 11, 14, 8].map((h, i) => (
                        <i
                          key={i}
                          style={
                            {
                              '--h': `${h}px`,
                              animationDelay: `${-((i * 0.1) % 0.7).toFixed(1)}s`,
                            } as React.CSSProperties
                          }
                        />
                      ))}
                    </div>
                    <div className="mini-transcript">
                      <p>
                        <span className="sp">Dr</span>BP <span className="hl">128/82</span>, adherence
                        good.
                      </p>
                      <p>
                        <span className="sp">Pt</span>Dry cough 2 weeks.
                      </p>
                      <p>
                        <span className="sp">Dr</span>Switching to losartan.
                      </p>
                    </div>
                  </div>
                  <div className="mini-col">
                    <span className="mini-lbl">SOAP note</span>
                    <div className="mini-soap-row">
                      <span className="l">S</span>
                      <span>
                        HTN f/u. <strong>Dry cough</strong> × 2 wk.
                      </span>
                    </div>
                    <div className="mini-soap-row">
                      <span className="l">O</span>
                      <span>BP 132/84, HR 72.</span>
                    </div>
                    <div className="mini-soap-row">
                      <span className="l">A</span>
                      <span>
                        HTN <span className="mini-code">I10</span>, ACE cough{' '}
                        <span className="mini-code">R05.9</span>
                      </span>
                    </div>
                    <div className="mini-soap-row">
                      <span className="l">P</span>
                      <span>
                        D/C lisinopril. <strong>Losartan 50mg</strong>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="orb-sat a">
        <span className="ico">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M12 2v10M12 2l-3 3M12 2l3 3" />
            <path d="M6 14c0 3 3 6 6 6s6-3 6-6" />
          </svg>
        </span>
        <div>
          <span className="k">Transcribe</span> <span className="v">Deepgram Nova‑3</span>
        </div>
      </div>
      <div className="orb-sat b">
        <span className="ico">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M4 7h16M4 12h10M4 17h13" />
          </svg>
        </span>
        <div>
          <span className="k">SOAP</span> <span className="v">Auto‑drafted</span>
        </div>
      </div>
      <div className="orb-sat c">
        <span className="ico">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <path d="M9 9h1M9 13h6M9 17h4" />
          </svg>
        </span>
        <div>
          <span className="k">ICD‑10</span> <span className="v">I10 · R05.9</span>
        </div>
      </div>
      <div className="orb-sat d">
        <span className="ico">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <circle cx="12" cy="12" r="8" />
            <path d="M12 8v8M8 12h8" />
          </svg>
        </span>
        <div>
          <span className="k">Rx</span> <span className="v">Losartan 50mg</span>
        </div>
      </div>
    </div>
  );
}
