'use client';

import { useState } from 'react';

type Node = {
  key: string;
  label: string;
  glyph: string;
  blurb: string;
};

// ONE note's lifecycle — not a patient pipeline.
const NODES: Node[] = [
  {
    key: 'record',
    label: 'Record',
    glyph: '◉',
    blurb:
      'Capture the visit — ambient audio or dictation. Medical-grade transcription turns the conversation into a labeled transcript.',
  },
  {
    key: 'draft',
    label: 'Draft',
    glyph: '◑',
    blurb:
      'The note is drafted from the transcript. Every sentence carries an anchor to the words that support it — nothing is written from thin air.',
  },
  {
    key: 'verify',
    label: 'Verify',
    glyph: '◈',
    blurb:
      'A fail-closed checker confirms each claim against its anchor. Anything it can’t ground is held back in a review lane instead of silently asserted.',
  },
  {
    key: 'sign',
    label: 'Sign',
    glyph: '✦',
    blurb:
      'You review the draft, adopt or dismiss anything in the review lane, and sign. The signed note is yours — your attestation, on the record.',
  },
];

export function Journey() {
  const [active, setActive] = useState<string>('record');

  return (
    <section id="journey" className="section journey" aria-label="The note’s journey">
      <header className="section-head reveal">
        <p className="eyebrow">The note’s journey</p>
        <h2 className="font-display section-title">One note,<br />four moves</h2>
        <p className="section-lede">
          From spoken visit to signed record. Hover a step to open it.
        </p>
      </header>

      <div
        className="journey-grid reveal"
        onMouseLeave={() => setActive('record')}
      >
        {/* the glowing spine */}
        <div className="journey-spine" aria-hidden>
          <span className="journey-spine-pulse" />
        </div>

        <ol className="journey-nodes">
          {NODES.map((n, i) => {
            const open = active === n.key;
            return (
              <li
                key={n.key}
                className={`journey-node ${open ? 'is-open' : ''}`}
                onMouseEnter={() => setActive(n.key)}
                onFocus={() => setActive(n.key)}
              >
                <button
                  className="node-dot"
                  type="button"
                  aria-expanded={open}
                  aria-controls={`step-${n.key}`}
                  onClick={() => setActive(n.key)}
                >
                  <span className="node-glyph" aria-hidden>{n.glyph}</span>
                  <span className="node-index font-mono" aria-hidden>0{i + 1}</span>
                </button>

                <div className="node-rail">
                  <span className="node-label font-display">{n.label}</span>
                  <div
                    id={`step-${n.key}`}
                    className={`glass glass-edge node-card ${open ? 'is-open' : ''}`}
                    role="region"
                    aria-label={`${n.label} — step ${i + 1}`}
                  >
                    <span className="node-card-glitch" aria-hidden>{n.label}</span>
                    <p className="node-card-text">{n.blurb}</p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
