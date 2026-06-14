'use client';

// C7 — COMMAND-BAR DRIVEN. The note is the page; the only action surface is a ⌘K command bar. Press
// ⌘K (or click the hint) to open a spotlight palette of the things that need doing — resolve the
// critical interaction, adopt a suggestion, review held items, view coding, sign. Keyboard-first:
// type to filter, ↑↓ to move, Enter to run. No competing buttons, no rail, no drawer.
//
// a11y: a combobox (the input) drives a listbox (the command rows). Options carry NO focusable
// children — selection is roved via aria-activedescendant — and the expanded action panel renders
// as a sibling region BELOW the listbox so its textarea/buttons stay properly focusable.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { PatientMeta, SampleChip, NoteDoc, EmPanel, useReview } from './parts';
import { LANE, RX, EM } from './data';

type Cmd = { id: string; label: string; hint: string; done?: boolean; danger?: boolean; disabled?: boolean };

export function C7Command() {
  const r = useReview();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [why, setWhy] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const critical = RX.find((w) => w.severity === 'critical')!;
  const grounded = LANE.find((l) => l.kind === 'grounded')!;
  const heldItem = LANE.find((l) => l.kind === 'held')!;

  const cmds: Cmd[] = useMemo(
    () => [
      { id: 'rx', label: 'Resolve critical interaction', hint: critical.pair, done: r.overrides.has(critical.id), danger: true },
      { id: 'adopt', label: 'Adopt suggestion — order BMP at follow-up', hint: 'grounded in the visit', done: r.laneState(grounded.id) === 'adopted' },
      { id: 'held', label: 'Review held suggestion — DASH counseling', hint: 'not stated in this visit', done: r.laneState(heldItem.id) !== undefined },
      { id: 'coding', label: `Coding · ${r.bumpApplied ? EM.suggested : EM.current}`, hint: r.bumpApplied && !r.emConfirmed ? 'confirm the level change' : 'review level', done: r.bumpApplied && r.emConfirmed },
      { id: 'sign', label: 'Sign note', hint: r.canSign ? 'ready' : `${r.blockers.length} to resolve first`, disabled: !r.canSign },
    ],
    [r, critical, grounded, heldItem],
  );

  const filtered = cmds.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));
  const active = filtered[sel];
  const expandedCmd = expanded ? cmds.find((c) => c.id === expanded) : undefined;

  const close = () => {
    setOpen(false);
    triggerRef.current?.focus(); // restore focus to the opener
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === 'Escape') {
        setExpanded(null);
        if (open) close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (open) {
      setSel(0);
      inputRef.current?.focus();
    } else {
      setExpanded(null);
      setQ('');
    }
  }, [open]);

  const run = (c?: Cmd) => {
    if (!c || c.disabled) return;
    if (c.id === 'sign') {
      r.setSigned(true);
      close();
      return;
    }
    if (c.id === 'adopt') {
      r.adopt(grounded.id);
      return;
    }
    setExpanded((x) => (x === c.id ? null : c.id));
  };

  const onListKey = (e: ReactKeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((s) => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((s) => Math.max(s - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      run(active);
    }
  };

  return (
    <div className="c7 sc-app">
      <div className="c7-hintbar">
        <div className="sc-top-l"><PatientMeta /><SampleChip /></div>
        <button ref={triggerRef} className="c7-trigger" type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open}>
          <kbd className="c7-kbd">⌘K</kbd>
          <span>{r.signed ? 'Signed ✓' : r.canSign ? 'Ready to sign' : `${r.blockers.length} to resolve`}</span>
        </button>
      </div>

      <main className="c7-note sc-pane">
        <div className="sc-pane-head"><span className="sc-pane-title">Note · SOAP</span><span className="c7-note-hint">Press ⌘K to act</span></div>
        <NoteDoc />
      </main>

      {open && <div className="c7-scrim" onClick={close} aria-hidden />}
      {open && (
        <div className="c7-palette" role="dialog" aria-label="Command bar" aria-modal="true" onKeyDown={onListKey}>
          <input
            ref={inputRef}
            className="c7-input"
            role="combobox"
            aria-expanded="true"
            aria-controls="c7-list"
            aria-activedescendant={active ? `c7-cmd-${active.id}` : undefined}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSel(0);
            }}
            placeholder="Type a command…  (resolve, adopt, coding, sign)"
            aria-label="Command"
          />
          <ul id="c7-list" className="c7-list" role="listbox" aria-label="Commands">
            {filtered.map((c, i) => (
              <li
                key={c.id}
                id={`c7-cmd-${c.id}`}
                className={`c7-cmd ${i === sel ? 'sel' : ''} ${c.done ? 'done' : ''} ${c.disabled ? 'off' : ''}`}
                role="option"
                aria-selected={i === sel}
                aria-disabled={c.disabled || undefined}
                onMouseEnter={() => setSel(i)}
                onClick={() => run(c)}
              >
                <span className={`c7-cmd-dot ${c.danger ? 'danger' : ''} ${c.done ? 'done' : ''}`} aria-hidden>{c.done ? '✓' : c.danger ? '!' : '›'}</span>
                <span className="c7-cmd-label">{c.label}</span>
                <span className="c7-cmd-hint">{c.hint}</span>
              </li>
            ))}
            {filtered.length === 0 && <li className="c7-empty" role="presentation">No commands match “{q}”.</li>}
          </ul>

          {expandedCmd && (
            <div className="c7-expand" role="group" aria-label={expandedCmd.label}>
              {expandedCmd.id === 'rx' && !r.overrides.has(critical.id) && (
                <>
                  <p className="sc-card-text">{critical.text}</p>
                  <label className="sc-override-label" htmlFor="c7-why">Why sign past this? (required)</label>
                  <textarea id="c7-why" className="sc-override-area" value={why} onChange={(e) => setWhy(e.target.value)} placeholder="e.g. simvastatin already reduced to 20 mg" />
                  <button className="sc-btn sc-btn-danger" type="button" disabled={why.trim().length < 10} onClick={() => { r.override(critical.id); setExpanded(null); }}>
                    Override &amp; continue
                  </button>
                </>
              )}
              {expandedCmd.id === 'held' && r.laneState(heldItem.id) === undefined && (
                <>
                  <p className="sc-card-text">{heldItem.text}</p>
                  <p className="sc-lane-note is-held">{heldItem.note}</p>
                  <div className="sc-actions">
                    <button className="sc-btn sc-btn-pry-ghost" type="button" onClick={() => { r.adopt(heldItem.id); setExpanded(null); }}>Add to note</button>
                    <button className="sc-btn sc-btn-quiet" type="button" onClick={() => { r.dismiss(heldItem.id); setExpanded(null); }}>Leave out</button>
                  </div>
                </>
              )}
              {expandedCmd.id === 'coding' && (
                <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
              )}
            </div>
          )}

          {r.signed && <div className="c7-signed-row">✓ Note signed</div>}
        </div>
      )}

      <div className="sc-mobilebar c7-mobilebar">
        <button className="c7-trigger big" type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open}>
          <kbd className="c7-kbd">⌘K</kbd> <span>{r.canSign ? 'Sign note' : `${r.blockers.length} to resolve`}</span>
        </button>
      </div>
    </div>
  );
}
