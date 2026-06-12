/**
 * Demo — Phase 7 v6 (Apple Product).
 *
 * Full-bleed product mockup centred in a stage. Window chrome, two panes
 * (Transcript / SOAP draft), 6 dialogue turns, 4 SOAP sections with status
 * badges + ICD/CPT code chips. The 2deg X tilt on the shell + sage glow
 * shadow make it feel like a floating product still.
 */
const TURNS: { role: 'pt' | 'dr'; text: React.ReactNode }[] = [
  { role: 'pt', text: 'It started about three days ago. Dull, behind the sternum, worse when I lie down.' },
  { role: 'dr', text: 'Any radiation to the jaw or arm, shortness of breath?' },
  { role: 'pt', text: 'No jaw. A little tight when I climb stairs, but I have asthma.' },
  { role: 'dr', text: 'BP one-twenty-eight over eighty-two, heart rate seventy-six, regular rhythm. Lungs clear bilaterally.' },
  { role: 'pt', text: 'My albuterol — I think I was using it more last week.' },
  {
    role: 'dr',
    text: (
      <>
        Let&apos;s get an ECG today and a follow-up next Tuesday. I&apos;ll also re-check your peak
        flow
        <span className="typing-cursor" />
      </>
    ),
  },
];

export function Demo() {
  return (
    <section className="stage" id="demo">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">04 / See it</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          Real visit. Real note. <span className="quiet">Ninety seconds.</span>
        </h2>
        <p className="stage-sub reveal delay-2">
          A three-month HTN follow-up, transcribed and documented live. Patient data is synthetic.
        </p>

        <div className="product-shell reveal delay-3">
          <div className="product-chrome">
            <span className="chrome-dot" />
            <span className="chrome-dot" />
            <span className="chrome-dot" />
            <div className="chrome-tabs">
              <span className="chrome-tab">visit-7K2A</span>
              <span className="chrome-tab active">live</span>
              <span className="chrome-tab">soap.md</span>
            </div>
            <div className="chrome-meta">
              <span className="live-dot" />
              recording · 01:42
            </div>
          </div>
          <div className="product-body">
            <div className="pane transcript">
              <div className="pane-label">
                Transcript <span className="src">/ Deepgram · diarized</span>
              </div>
              {TURNS.map((turn, i) => (
                <div key={i} className={`turn ${turn.role}`}>
                  <span className="who">{turn.role === 'dr' ? 'Dr' : 'Pt'}</span>
                  <div className="said">{turn.text}</div>
                </div>
              ))}
            </div>
            <div className="pane">
              <div className="pane-label">
                SOAP draft <span className="src">/ claude-opus-4.8 · verified</span>
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
                  Atypical chest pain, likely esophageal vs. musculoskeletal. Asthma — uncontrolled
                  per albuterol overuse.
                </div>
                <div className="soap-codes">
                  <span className="code-chip">R07.89</span>
                  <span className="code-chip">J45.40</span>
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
                <div className="soap-codes">
                  <span className="code-chip">99214</span>
                  <span className="code-chip">93000</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
