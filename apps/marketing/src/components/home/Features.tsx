/**
 * Features — Phase 7 v6 (Apple Product).
 *
 * Intro stage + 6 sequential full-row stages (alternating left/right). Each
 * has a custom feature visual:
 *  - 01: 4-cell SOAP grid with 3 lit
 *  - 02: ICD/CPT code chips with confidence pills
 *  - 03: shield icon + 3 pulsing rings (HIPAA)
 *  - 04: specialty stack list with one row active
 *  - 05: cmdk palette mock with input + cursor + 4 results
 *  - 06: audit log with mono timestamp/event/id rows
 */
export function Features() {
  return (
    <section id="features" className="features-stage">
      <div className="stage" style={{ minHeight: '60vh', padding: '60px 0 30px' }}>
        <div className="container stage-inner">
          <div className="reveal">
            <span className="eyebrow-tiny">02 / Built for the visit</span>
          </div>
          <h2 className="stage-h2 reveal delay-1">
            Everything a working clinic needs.{' '}
            <span className="quiet">Nothing it doesn&apos;t.</span>
          </h2>
          <p className="stage-sub reveal delay-2">
            Six features that move the cursor from end-of-visit to next-patient.
          </p>
        </div>
      </div>

      <div className="feature-row">
        <div className="feature-text reveal">
          <div className="feature-num">Feature 01</div>
          <h3 className="feature-h">Real-time SOAP draft.</h3>
          <p className="feature-body">
            Subjective, Objective, Assessment, Plan light up section-by-section as the visit
            unfolds. Edit inline; sign when ready.
          </p>
        </div>
        <div className="feature-visual reveal delay-1">
          <div className="fv-soap-grid">
            <div className="fv-soap-cell lit">
              <span className="fv-soap-letter">S</span>
              <span className="fv-soap-line" />
              <span className="fv-soap-line short" />
            </div>
            <div className="fv-soap-cell lit">
              <span className="fv-soap-letter">O</span>
              <span className="fv-soap-line" />
              <span className="fv-soap-line" />
            </div>
            <div className="fv-soap-cell lit">
              <span className="fv-soap-letter">A</span>
              <span className="fv-soap-line" />
              <span className="fv-soap-line short" />
            </div>
            <div className="fv-soap-cell">
              <span className="fv-soap-letter">P</span>
              <span className="fv-soap-line" />
              <span className="fv-soap-line short" />
            </div>
          </div>
        </div>
      </div>

      <div className="feature-row flip">
        <div className="feature-text reveal">
          <div className="feature-num">Feature 02</div>
          <h3 className="feature-h">ICD-10 + CPT auto-coded.</h3>
          <p className="feature-body">
            Diagnosis and procedure recommendations with confidence scores; the doctor approves or
            edits in one click.
          </p>
        </div>
        <div className="feature-visual reveal delay-1">
          <div className="fv-codes">
            <span className="fv-chip">R07.89</span>
            <span className="fv-chip confidence">98%</span>
            <span className="fv-chip">J45.40</span>
            <span className="fv-chip confidence">94%</span>
            <span className="fv-chip cpt">99214</span>
            <span className="fv-chip confidence">99%</span>
            <span className="fv-chip cpt">93000</span>
            <span className="fv-chip confidence">96%</span>
            <span className="fv-chip">I10</span>
            <span className="fv-chip confidence">88%</span>
          </div>
        </div>
      </div>

      <div className="feature-row">
        <div className="feature-text reveal">
          <div className="feature-num">Feature 03</div>
          <h3 className="feature-h">HIPAA, BAA on file.</h3>
          <p className="feature-body">
            Audit-logged at every layer. End-to-end encryption. PHI never leaves our US-hosted
            environment.
          </p>
        </div>
        <div className="feature-visual reveal delay-1">
          <div className="fv-shield">
            <div className="fv-shield-rings">
              <div className="fv-shield-ring" />
              <div className="fv-shield-ring" />
              <div className="fv-shield-ring" />
            </div>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>
        </div>
      </div>

      <div className="feature-row flip">
        <div className="feature-text reveal">
          <div className="feature-num">Feature 04</div>
          <h3 className="feature-h">Specialty-aware.</h3>
          <p className="feature-body">
            Family Medicine, Cardiology, Pediatrics, Psychiatry, Endo. The model adapts to your
            domain, not the reverse.
          </p>
        </div>
        <div className="feature-visual reveal delay-1">
          <div className="fv-stack">
            <div className="fv-stack-row">
              <span className="fv-stack-dot" /> Family Medicine
            </div>
            <div className="fv-stack-row active">
              <span className="fv-stack-dot" /> Cardiology · loaded
            </div>
            <div className="fv-stack-row">
              <span className="fv-stack-dot" /> Pediatrics
            </div>
            <div className="fv-stack-row">
              <span className="fv-stack-dot" /> Psychiatry
            </div>
            <div className="fv-stack-row">
              <span className="fv-stack-dot" /> Endocrinology
            </div>
          </div>
        </div>
      </div>

      <div className="feature-row">
        <div className="feature-text reveal">
          <div className="feature-num">Feature 05</div>
          <h3 className="feature-h">Cmd-K everywhere.</h3>
          <p className="feature-body">
            Jump to any patient, any visit, any specialty pack. Never more than two keystrokes
            from the next note.
          </p>
        </div>
        <div className="feature-visual reveal delay-1">
          <div className="fv-cmdk">
            <div className="fv-cmdk-input">
              {' '}
              Sarah Mitchell
              <span className="fv-cmdk-cursor" />
            </div>
            <div className="fv-cmdk-list">
              <div className="fv-cmdk-item sel">
                <span className="ico">P</span> Sarah Mitchell — last visit Apr 28
                <span className="kbd">↵</span>
              </div>
              <div className="fv-cmdk-item">
                <span className="ico">N</span> New visit — Cardiology<span className="kbd">⌘N</span>
              </div>
              <div className="fv-cmdk-item">
                <span className="ico">T</span> Switch template — Psychiatry
                <span className="kbd">⌘T</span>
              </div>
              <div className="fv-cmdk-item">
                <span className="ico">S</span> Search all visits<span className="kbd">⌘F</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="feature-row flip">
        <div className="feature-text reveal">
          <div className="feature-num">Feature 06</div>
          <h3 className="feature-h">Audit-logged + US-hosted.</h3>
          <p className="feature-body">
            Every action emits an immutable event. US-based servers. Your data never crosses a
            border.
          </p>
        </div>
        <div className="feature-visual reveal delay-1">
          <div className="fv-audit">
            <div className="fv-audit-row">
              <span className="fv-audit-time">14:32:08</span>
              <span className="fv-audit-event">
                <span className="verb">SIGNED</span> visit-7K2A
              </span>
              <span className="fv-audit-id">u-091</span>
            </div>
            <div className="fv-audit-row">
              <span className="fv-audit-time">14:31:54</span>
              <span className="fv-audit-event">
                <span className="verb">EDITED</span> soap.assessment
              </span>
              <span className="fv-audit-id">u-091</span>
            </div>
            <div className="fv-audit-row">
              <span className="fv-audit-time">14:31:12</span>
              <span className="fv-audit-event">
                <span className="verb">CODED</span> R07.89 · J45.40
              </span>
              <span className="fv-audit-id">sys</span>
            </div>
            <div className="fv-audit-row">
              <span className="fv-audit-time">14:30:48</span>
              <span className="fv-audit-event">
                <span className="verb">DRAFTED</span> SOAP note
              </span>
              <span className="fv-audit-id">sys</span>
            </div>
            <div className="fv-audit-row">
              <span className="fv-audit-time">14:28:14</span>
              <span className="fv-audit-event">
                <span className="verb">STARTED</span> visit recording
              </span>
              <span className="fv-audit-id">u-091</span>
            </div>
            <div className="fv-audit-row">
              <span className="fv-audit-time">14:27:02</span>
              <span className="fv-audit-event">
                <span className="verb">OPENED</span> patient · Mitchell
              </span>
              <span className="fv-audit-id">u-091</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
