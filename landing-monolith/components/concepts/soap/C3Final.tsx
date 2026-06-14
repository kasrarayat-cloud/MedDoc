'use client';

// C3 "Drawer" — the COMPLETE, polished version (static mockup, synthetic no-PHI data).
//
// Locked direction: the SOAP note is full-width and primary; ONE "Sign note" button; everything
// secondary lives behind a single "N to review" count pill that opens a calm, dismissible right
// drawer. This builds out every state — with-flags / clean / before-sign / signed /
// critical-override / E/M-confirm — driven by a small mockup control so Kasra can preview them all.
//
// NOT wired to the real pipeline/server actions/auth. Reuses the pure presentational toolkit from
// parts.tsx (NoteDoc, LaneCard, RxCard, EmPanel, SignButton, SampleChip, PatientMeta) but runs its
// own scenario-parametrized review state so the "clean" dataset can differ from "with flags"
// without touching the shared useReview() hook the 10 switcher concepts depend on.
import { useEffect, useId, useRef, useState } from 'react';
import { PatientMeta, SampleChip, NoteDoc, LaneCard, RxCard, EmPanel, SignButton } from './parts';
import { SOAP, LANE, RX } from './data';
import type { LaneItem, RxWarn } from './data';

type Scenario = 'flags' | 'clean';

// ── A calm, post-sign export affordance — ONE button → a small 2-option menu (not the old
// 8-option modal). Esc + click-outside close; focus moves into the menu on open. ──────────────
function ExportMenu() {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    firstItemRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  const pick = (label: string) => {
    setDone(label);
    setOpen(false);
  };

  return (
    <div className="c3f-export" ref={wrapRef}>
      <button className="sc-btn sc-btn-quiet c3f-export-btn" type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Export ▾
      </button>
      {open && (
        <div className="c3f-export-menu" role="menu" id={menuId} aria-label="Export note">
          <button ref={firstItemRef} className="c3f-export-item" type="button" role="menuitem" onClick={() => pick('PDF downloaded')}>
            <span className="c3f-export-ico" aria-hidden>⤓</span> Download PDF
          </button>
          <button className="c3f-export-item" type="button" role="menuitem" onClick={() => pick('Copied for the EHR')}>
            <span className="c3f-export-ico" aria-hidden>⧉</span> Copy for the EHR
          </button>
        </div>
      )}
      {done && (
        <span className="c3f-export-done" role="status">
          ✓ {done}
        </span>
      )}
    </div>
  );
}

// The signed state of the sign region: a calm confirmation + the one Export affordance.
function SignedBanner() {
  return (
    <div className="c3f-signed">
      <div className="c3f-signed-l">
        <span className="c3f-signed-check" aria-hidden>✓</span>
        <div className="c3f-signed-text">
          <span className="c3f-signed-head">Note signed</span>
          <span className="c3f-signed-sub">Dr. Sample · today 11:26</span>
        </div>
      </div>
      <ExportMenu />
    </div>
  );
}

// Read-only render of the note for the signed state (no edit affordances).
function ReadonlyNote() {
  return (
    <div className="sc-note c3f-note-ro">
      {SOAP.map((s) => (
        <div className="sc-sec" key={s.tag}>
          <div className="sc-sec-head">
            <span className={`sc-tag sc-tag-${s.tag}`}>{s.tag}</span>
            <span className="sc-sec-label">{s.label}</span>
          </div>
          <p className="sc-sec-text">{s.text}</p>
        </div>
      ))}
    </div>
  );
}

export function C3Final() {
  // ── scenario + review state ───────────────────────────────────────────────────────────────
  const [scenario, setScenario] = useState<Scenario>('flags');
  const [previewSigned, setPreviewSigned] = useState(false);
  const [adopted, setAdopted] = useState<Set<string>>(new Set());
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [overrides, setOverrides] = useState<Set<string>>(new Set());
  const [bumpApplied, setBumpApplied] = useState(false);
  const [emConfirmed, setEmConfirmed] = useState(false);
  const [signed, setSigned] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const drawerRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // the dataset for the active scenario (clean = nothing flagged → instant happy path)
  const lane: LaneItem[] = scenario === 'flags' ? LANE : [];
  const rx: RxWarn[] = scenario === 'flags' ? RX : [];
  const emEnabled = scenario === 'flags';

  const resetState = () => {
    setAdopted(new Set());
    setDismissed(new Set());
    setOverrides(new Set());
    setBumpApplied(false);
    setEmConfirmed(false);
    setSigned(false);
    setDrawerOpen(false);
  };
  const switchScenario = (s: Scenario) => {
    setScenario(s);
    setPreviewSigned(false);
    resetState();
  };

  // ── derived review state ──────────────────────────────────────────────────────────────────
  const adopt = (id: string) => {
    setAdopted((s) => new Set(s).add(id));
    setDismissed((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
  };
  const dismiss = (id: string) => {
    setDismissed((s) => new Set(s).add(id));
    setAdopted((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
  };
  const override = (id: string) => setOverrides((s) => new Set(s).add(id));
  const laneState = (id: string): 'adopted' | 'dismissed' | undefined =>
    adopted.has(id) ? 'adopted' : dismissed.has(id) ? 'dismissed' : undefined;

  const pendingLane = lane.filter((l) => !adopted.has(l.id) && !dismissed.has(l.id));
  const blockingRx = rx.filter((w) => w.blocking && !overrides.has(w.id));
  const emNeeded = emEnabled && bumpApplied && !emConfirmed;
  const blockers = [
    ...blockingRx.map((w) => `critical interaction ${w.id} — override to sign`),
    ...(emNeeded ? ['coding changed 99213 → 99214 — confirm'] : []),
  ];
  const canSign = blockers.length === 0;
  const reviewCount = pendingLane.length + blockingRx.length + (emNeeded ? 1 : 0);
  const isSignedView = signed || previewSigned;

  const pillLabel = reviewCount > 0 ? `${reviewCount} to review` : 'Nothing to review';

  // ── drawer a11y: focus trap + Esc + return focus to the opener ─────────────────────────────
  const closeDrawer = () => {
    setDrawerOpen(false);
    // return focus to whichever count pill is actually visible (top bar on desktop, sticky bar
    // on mobile). Defer to the next frame so React has re-rendered first — on mobile the sticky
    // bar is display:none while `is-drawer-open` is applied, so a synchronous query would find
    // no visible pill and drop focus to <body>.
    requestAnimationFrame(() => {
      const pill = Array.from(document.querySelectorAll<HTMLButtonElement>('.c3f-pill')).find(
        (p) => p.offsetParent !== null && !p.disabled,
      );
      pill?.focus();
    });
  };
  useEffect(() => {
    if (!drawerOpen) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeDrawer();
        return;
      }
      if (e.key !== 'Tab' || !drawerRef.current) return;
      const nodes = drawerRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])',
      );
      const list = Array.from(nodes).filter((el) => !(el as HTMLButtonElement).disabled && el.offsetParent !== null);
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // closeDrawer is stable enough for this mockup; deps intentionally minimal
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawerOpen]);

  // ── the one sign affordance (signed banner, or the Sign button with inline blockers) ───────
  const signRegion = (big?: boolean) =>
    isSignedView ? <SignedBanner /> : <SignButton canSign={canSign} blockers={blockers} signed={false} onSign={() => setSigned(true)} big={big} />;

  const reviewPill = (
    <button
      className={`c3f-pill ${reviewCount > 0 ? 'has' : 'clear'}`}
      type="button"
      onClick={() => setDrawerOpen(true)}
      aria-expanded={drawerOpen}
      aria-haspopup="dialog"
      disabled={isSignedView}
    >
      {isSignedView ? 'Reviewed ✓' : pillLabel}
    </button>
  );

  return (
    <div className={`c3f sc-root sc-app ${isSignedView ? 'is-signed' : ''} ${drawerOpen ? 'is-drawer-open' : ''}`}>
      <header className="c3f-top sc-top" inert={drawerOpen || undefined}>
        <div className="sc-top-l">
          <div className="c3f-id">
            <PatientMeta />
            <span className={`c3f-status ${isSignedView ? 'signed' : 'draft'}`}>{isSignedView ? '● Signed' : '○ Draft'}</span>
          </div>
          <SampleChip />
        </div>
        <div className="sc-top-r c3f-actions">
          {!isSignedView && reviewPill}
          {signRegion(false)}
        </div>
      </header>

      <main className="c3f-main sc-pane" inert={drawerOpen || undefined}>
        <div className="sc-pane-head">
          <span className="sc-pane-title">Note · SOAP{isSignedView ? ' · signed' : ''}</span>
          {!isSignedView && <span className="c3f-hint">Click a section to edit · everything else is one pill away</span>}
        </div>
        {isSignedView ? <ReadonlyNote /> : <NoteDoc />}
      </main>

      {/* the review drawer — the heart of the concept */}
      {drawerOpen && <div className="c3f-scrim" onClick={closeDrawer} aria-hidden />}
      <aside
        ref={drawerRef}
        className={`c3f-drawer ${drawerOpen ? 'open' : ''}`}
        role="dialog"
        aria-modal={drawerOpen || undefined}
        aria-label="Review before signing"
        inert={!drawerOpen}
      >
        <div className="c3f-drawer-head">
          <div className="c3f-drawer-title">
            <span className="sc-rail-title">Review</span>
            <span className={`c3f-resolve ${blockers.length > 0 ? 'blocked' : 'clear'}`}>
              {blockers.length > 0 ? `${blockers.length} to resolve before signing` : 'All clear — ready to sign'}
            </span>
          </div>
          <button ref={closeRef} className="sc-btn sc-btn-quiet" type="button" onClick={closeDrawer} aria-label="Close review panel">
            Close ✕
          </button>
        </div>

        <div className="c3f-drawer-body">
          {reviewCount === 0 ? (
            <div className="c3f-empty">
              <span className="c3f-empty-mark" aria-hidden>✓</span>
              <p className="c3f-empty-head">Nothing to review</p>
              <p className="c3f-empty-sub">No AI suggestions, no interaction warnings, no coding change. This visit is ready to sign.</p>
            </div>
          ) : (
            <>
              {lane.length > 0 && (
                <section className="c3f-group" aria-label="AI suggestions">
                  <h3 className="c3f-group-h">AI suggestions</h3>
                  {lane.map((l) => (
                    <LaneCard key={l.id} item={l} state={laneState(l.id)} onAdopt={adopt} onDismiss={dismiss} />
                  ))}
                </section>
              )}
              {rx.length > 0 && (
                <section className="c3f-group" aria-label="Prescription safety">
                  <h3 className="c3f-group-h">Prescription safety {blockingRx.length > 0 && <span className="c3f-group-flag">must resolve</span>}</h3>
                  {rx.map((w) => (
                    <RxCard key={w.id} warn={w} overridden={overrides.has(w.id)} onOverride={override} />
                  ))}
                </section>
              )}
              {emEnabled && (
                <section className="c3f-group" aria-label="Coding">
                  <h3 className="c3f-group-h">Coding {emNeeded && <span className="c3f-group-flag">confirm to sign</span>}</h3>
                  <EmPanel applied={bumpApplied} onApply={() => setBumpApplied(true)} confirmed={emConfirmed} onConfirm={setEmConfirmed} />
                </section>
              )}
            </>
          )}
        </div>

        <div className="c3f-drawer-foot">{signRegion(true)}</div>
      </aside>

      {/* mobile: pill + Sign as a sticky bottom bar (drawer becomes a full-screen sheet) */}
      <div className="sc-mobilebar c3f-mobilebar">
        {!isSignedView && reviewPill}
        {signRegion(true)}
      </div>

      {/* mockup control — preview every state (clearly a demo affordance, not product chrome).
          Hidden while the drawer is open so it never overlaps the sheet on a tablet/phone. */}
      <nav className={`c3f-mock ${drawerOpen ? 'is-hidden' : ''}`} aria-label="Mockup state controls">
        <span className="c3f-mock-tag" aria-hidden>◆ MOCKUP</span>
        <div className="c3f-mock-grp" role="group" aria-label="Scenario">
          <button type="button" className={scenario === 'flags' ? 'on' : ''} aria-pressed={scenario === 'flags'} onClick={() => switchScenario('flags')}>
            With flags
          </button>
          <button type="button" className={scenario === 'clean' ? 'on' : ''} aria-pressed={scenario === 'clean'} onClick={() => switchScenario('clean')}>
            Clean
          </button>
        </div>
        <div className="c3f-mock-grp" role="group" aria-label="State">
          <button type="button" className={!isSignedView ? 'on' : ''} aria-pressed={!isSignedView} onClick={() => { setPreviewSigned(false); setSigned(false); }}>
            Draft
          </button>
          <button type="button" className={isSignedView ? 'on' : ''} aria-pressed={isSignedView} onClick={() => { setPreviewSigned(true); setDrawerOpen(false); }}>
            Signed
          </button>
        </div>
        {!isSignedView && (
          <button type="button" className="c3f-mock-reset" onClick={resetState} aria-label="Reset interactions">
            ↺ Reset
          </button>
        )}
      </nav>
    </div>
  );
}
