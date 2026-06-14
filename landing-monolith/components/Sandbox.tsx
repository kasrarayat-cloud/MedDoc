'use client';

import { useEffect, useRef, useState } from 'react';

type Line = { tag: 'S' | 'O' | 'A' | 'P'; text: string; chip?: 'verified' | 'review' };

// A short, realistic, ANCHORED note — nothing here is a claim about a real
// patient; it's an illustrative demo of the output shape.
const NOTE: Line[] = [
  { tag: 'S', text: 'Patient reports a sore throat for three days, worse on swallowing. No fever at home.', chip: 'verified' },
  { tag: 'S', text: 'Denies cough, shortness of breath, or rash.', chip: 'verified' },
  { tag: 'O', text: 'Oropharynx erythematous, no exudate. Tender anterior cervical nodes.', chip: 'verified' },
  { tag: 'A', text: 'Likely viral pharyngitis.', chip: 'review' },
  { tag: 'P', text: 'Supportive care; saltwater gargles, fluids, rest.', chip: 'verified' },
  { tag: 'P', text: 'Return if fever, difficulty swallowing, or symptoms beyond a week.', chip: 'verified' },
];

const TAG_LABEL: Record<Line['tag'], string> = {
  S: 'Subjective',
  O: 'Objective',
  A: 'Assessment',
  P: 'Plan',
};

const WAVE_BARS = 36;

export function Sandbox() {
  const [shown, setShown] = useState<number>(0); // fully-typed line count
  const [typed, setTyped] = useState<string>(''); // current line in progress
  const [done, setDone] = useState(false);
  const reduceRef = useRef(false);

  useEffect(() => {
    reduceRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceRef.current) {
      setShown(NOTE.length);
      setDone(true);
      return;
    }
    let line = 0;
    let char = 0;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      if (line >= NOTE.length) {
        setDone(true);
        timer = setTimeout(() => {
          // loop the demo
          line = 0; char = 0;
          setShown(0); setTyped(''); setDone(false);
          tick();
        }, 3200);
        return;
      }
      const full = NOTE[line].text;
      if (char <= full.length) {
        setTyped(full.slice(0, char));
        char += 1;
        timer = setTimeout(tick, 18 + Math.random() * 26);
      } else {
        setShown(line + 1);
        setTyped('');
        line += 1;
        char = 0;
        timer = setTimeout(tick, 360);
      }
    };
    timer = setTimeout(tick, 600);
    return () => clearTimeout(timer);
  }, []);

  return (
    <section id="sandbox" className="section sandbox" aria-label="The live sandbox">
      <header className="section-head reveal">
        <p className="eyebrow">The live sandbox</p>
        <h2 className="font-display section-title">Watch the note<br />get written</h2>
        <p className="section-lede">
          Speech in on the left. A structured, transcript-anchored SOAP note out
          on the right — drafted as the visit unfolds, each line flagged
          <span className="text-turq"> verified</span> or sent to a
          <span className="text-gold"> review lane</span>.
        </p>
      </header>

      <div className="glass glass-edge sandbox-card reveal">
        <div className="sandbox-bar font-mono" aria-hidden>
          <span className="dotrow"><i /><i /><i /></span>
          <span className="sandbox-bar-label">quillmd · session live</span>
          <span className="rec"><span className="rec-dot" /> REC</span>
        </div>

        <div className="sandbox-grid">
          {/* LEFT — audio waveform */}
          <div className="wave-pane" role="img" aria-label="Live audio waveform — two speakers, illustrative">
            <div className="wave-meta font-mono" aria-hidden>
              <span>AUDIO IN</span>
              <span className="text-turq">2 speakers</span>
            </div>
            <div className="wave" aria-hidden>
              {Array.from({ length: WAVE_BARS }).map((_, i) => (
                <span
                  key={i}
                  className="wave-bar"
                  style={{
                    animationDelay: `${(i % 12) * 0.07}s`,
                    animationDuration: `${0.7 + (i % 5) * 0.14}s`,
                  }}
                />
              ))}
            </div>
            <div className="wave-foot font-mono">
              <span>nova-3-medical</span>
              <span className="text-turq">transcribing…</span>
            </div>
          </div>

          {/* RIGHT — the note typing itself */}
          <div className="note-pane" aria-label="SOAP note being written">
            <div className="note-meta font-mono">
              <span>SOAP DRAFT</span>
              <span className="text-gold">{done ? 'ready · 1 to review' : 'writing…'}</span>
            </div>
            <ol className="note-body font-mono">
              {NOTE.map((l, i) => {
                const visible = i < shown;
                const active = i === shown;
                if (!visible && !active) return null;
                return (
                  <li key={i} className="note-line" style={{ animationDelay: '0s' }}>
                    <span className={`soap-tag soap-${l.tag}`} title={TAG_LABEL[l.tag]}>{l.tag}</span>
                    <span className="note-text">
                      {visible ? l.text : typed}
                      {active && <span className="caret" aria-hidden />}
                    </span>
                    {visible && l.chip && (
                      <span className={`chip chip-${l.chip}`}>
                        {l.chip === 'verified' ? '✓ verified' : '⚑ review'}
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
