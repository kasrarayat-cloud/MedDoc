'use client';

// SCREEN 2 — CREATE / RECORD, redesigned as "just start": one obvious path (a sensible walk-in
// default, no three co-equal tiles), a clean recording screen with an HONEST state (a live audio
// level — NOT a fake transcript pretending to work), clear Start/Stop with Pause, and a real
// confirm before the irreversible process step. Then honest processing → the C3 review. Static
// mockup — the timer/level are local; nothing is sent anywhere.
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { AppShell } from './AppShell';
import { SAMPLE_BANNER, VISIT_DEFAULT } from './data';

type Phase = 'start' | 'recording' | 'paused' | 'confirm' | 'processing';

function fmt(s: number) {
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const ss = (s % 60).toString().padStart(2, '0');
  return `${m}:${ss}`;
}

const BARS = Array.from({ length: 36 }, (_, i) => i);
const PROC_STEPS = ['Uploaded securely', 'Transcribing the visit', 'Drafting the SOAP note', 'Checked for safety & coding'];

export function RecordScreen() {
  const [phase, setPhase] = useState<Phase>('start');
  const [secs, setSecs] = useState(0);
  const [proc, setProc] = useState(0);

  // the timer advances only while actively recording
  useEffect(() => {
    if (phase !== 'recording') return;
    const id = window.setInterval(() => setSecs((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  // processing walks honest steps, then reveals the review link
  useEffect(() => {
    if (phase !== 'processing') return;
    setProc(0);
    const id = window.setInterval(() => setProc((p) => (p < PROC_STEPS.length ? p + 1 : p)), 1100);
    return () => window.clearInterval(id);
  }, [phase]);

  const start = () => { setSecs(0); setPhase('recording'); };
  const live = phase === 'recording';

  return (
    <AppShell active="home">
      <div className="ax-rec">
        <span className="ax-sample">● {SAMPLE_BANNER}</span>

        {phase === 'start' && (
          <div className="ax-rec-card ax-rec-start">
            <span className="ax-rec-kicker">New visit</span>
            <h1 className="ax-rec-h">Start a visit</h1>
            <p className="ax-rec-p">We’ll record the conversation and write the note after you stop. Nothing is processed until you choose to.</p>
            <div className="ax-rec-context">
              <div className="ax-rec-ctx">
                <span className="ax-rec-ctx-type">{VISIT_DEFAULT.type}</span>
                <span className="ax-rec-ctx-who">{VISIT_DEFAULT.who}</span>
              </div>
              <button className="ax-link" type="button">Change</button>
            </div>
            <button className="ax-rec-go" type="button" onClick={start}>
              <span className="ax-rec-go-dot" aria-hidden /> Start recording
            </button>
            <p className="ax-rec-hint">Walk-in is selected by default — just press start.</p>
          </div>
        )}

        {(phase === 'recording' || phase === 'paused') && (
          <div className="ax-rec-card ax-rec-live">
            <div className="ax-rec-statusline">
              <span className={`ax-rec-dot ${live ? 'live' : 'paused'}`} aria-hidden />
              <span aria-live="polite">{live ? 'Recording' : 'Paused'}</span>
            </div>
            <div className="ax-rec-timer">{fmt(secs)}</div>
            <div className={`ax-wave ${live ? '' : 'is-paused'}`} aria-hidden>
              {BARS.map((i) => (
                <span key={i} style={{ animationDelay: `${(i % 12) * 0.07}s` }} />
              ))}
            </div>
            <p className="ax-rec-honest">Listening to the visit. The note is written after you stop — there’s no live transcript to watch.</p>
            <div className="ax-rec-controls">
              {live ? (
                <button className="ax-rec-2nd" type="button" onClick={() => setPhase('paused')}>❚❚ Pause</button>
              ) : (
                <button className="ax-rec-2nd" type="button" onClick={() => setPhase('recording')}>▶ Resume</button>
              )}
              <button className="ax-rec-stop" type="button" onClick={() => setPhase('confirm')}>■ Stop</button>
            </div>
          </div>
        )}

        {phase === 'confirm' && (
          <div className="ax-rec-card ax-rec-confirm">
            <span className="ax-rec-kicker">Recording stopped</span>
            <h1 className="ax-rec-h">Write the note?</h1>
            <p className="ax-rec-p">
              <strong>{fmt(secs)}</strong> captured. Processing transcribes the visit and drafts the SOAP note. Review the draft before you sign.
            </p>
            <div className="ax-rec-actions">
              <button className="ax-rec-go" type="button" onClick={() => setPhase('processing')}>Process &amp; write note</button>
              <button className="ax-link" type="button" onClick={() => setPhase('recording')}>Resume recording</button>
              <button className="ax-link ax-link-quiet" type="button" onClick={() => { setSecs(0); setPhase('start'); }}>Discard</button>
            </div>
          </div>
        )}

        {phase === 'processing' && (
          <div className="ax-rec-card ax-rec-proc">
            <div className={`ax-proc-spin ${proc >= PROC_STEPS.length ? 'done' : ''}`} aria-hidden />
            <h1 className="ax-rec-h" aria-live="polite">{proc >= PROC_STEPS.length ? 'Note ready' : 'Writing the note…'}</h1>
            <ol className="ax-proc-steps">
              {PROC_STEPS.map((s, i) => (
                <li key={s} className={proc > i ? 'done' : proc === i ? 'now' : ''}>
                  <span className="ax-proc-mark" aria-hidden>{proc > i ? '✓' : '○'}</span> {s}
                </li>
              ))}
            </ol>
            {proc >= PROC_STEPS.length ? (
              <Link href="/concepts/soap/c3-final" className="ax-rec-go">Review the draft →</Link>
            ) : (
              <p className="ax-rec-hint" aria-live="polite">You can leave — it’ll be ready on your dashboard.</p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
