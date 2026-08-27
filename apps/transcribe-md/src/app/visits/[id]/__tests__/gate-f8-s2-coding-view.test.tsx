// ============================================================================
// F8-S2 — THE CODING SURFACE ON THE VISIT PAGE. THE GATE.
// ----------------------------------------------------------------------------
// Ruling #153 put the coding surface on the visit page via the smallest
// navigation primitive that works, and #154 (PROVISIONAL) made the rejection
// reason a closed vocabulary. This file pins both, plus the one property that
// is invisible in a diff and expensive in a clinic:
//
//   ⚠️ SWITCHING TO CODING AND BACK MUST NOT UNMOUNT THE NOTE.
//
// `visit-ready-view.tsx` states the constraint itself: `ReviewDocumentView`
// holds the in-session E/M confirm in LOCAL STATE, and anything that changes
// its React identity "would silently re-block Sign and read as a flaky gate."
// A ternary two-view switch destroys that state on every glance at the coding
// list. Nothing in a source review makes that visible, and no existing gate
// watches it — so it is asserted behaviourally, through a real render, by
// counting mounts and by reading state back after a round trip.
//
// ⚠️ WHY A MOUNT COUNTER AND NOT A SNAPSHOT. "The node is still in the DOM" is
// satisfied by a remount, which is precisely the failure. The only honest
// question is *did this component instance survive*, and the only way to ask
// it is to have the instance report its own mounts and hold state across the
// switch. Both are asserted, because either alone has a cheap false pass.
// ============================================================================

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useEffect, useState } from 'react';

import { VisitViewSwitch } from '../visit-view-switch';
import { IcdCodingView } from '../icd-coding-view';
import {
  ICD_REJECTION_REASONS,
  projectIcdDecisions,
  readIcdDecisions,
} from '@/lib/icd-decisions';

const USER = 'user-1';
const AT = '2026-08-27T10:00:00.000Z';

/** Two suggested codes plus one the allowlist gate dropped. */
const BLOB = {
  codes: [
    {
      code: 'K21.00',
      description: 'GERD without esophagitis',
      evidence_quote: 'reports reflux after meals',
      confidence: 0.92,
    },
    {
      code: 'E11.9',
      description: 'Type 2 diabetes mellitus without complications',
      evidence_quote: 'known T2DM',
      confidence: 0.81,
    },
  ],
  dropped: [{ code: 'Z48.815', reason: 'not_in_verified_allowlist' }],
};

// ---------------------------------------------------------------------------
// 1 · THE SWITCH DOES NOT UNMOUNT — the clinical claim
// ---------------------------------------------------------------------------

describe('⚠️ F8-S2 — the two-view switch HIDES and never UNMOUNTS', () => {
  function Probe({ mounts }: { mounts: { n: number } }) {
    const [typed, setTyped] = useState('');
    useEffect(() => {
      mounts.n += 1;
    }, [mounts]);
    return (
      <input
        aria-label="note-state"
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
      />
    );
  }

  it('the note panel mounts EXACTLY ONCE across a full round trip', () => {
    const mounts = { n: 0 };
    render(<VisitViewSwitch note={<Probe mounts={mounts} />} coding={<p>coding</p>} />);
    expect(mounts.n).toBe(1);

    fireEvent.click(screen.getByTestId('visit-view-tab-coding'));
    fireEvent.click(screen.getByTestId('visit-view-tab-note'));
    fireEvent.click(screen.getByTestId('visit-view-tab-coding'));
    fireEvent.click(screen.getByTestId('visit-view-tab-note'));

    // A ternary switch reports 3 here. This is the whole gate.
    expect(mounts.n, 'the note panel was REMOUNTED — local state is destroyed').toBe(1);
  });

  it('local state entered in the note SURVIVES a trip through Coding', () => {
    // The behavioural half. `ReviewDocumentView`'s in-session E/M confirm is
    // exactly this shape of state; losing it silently re-blocks Sign.
    const mounts = { n: 0 };
    render(<VisitViewSwitch note={<Probe mounts={mounts} />} coding={<p>coding</p>} />);

    const input = screen.getByLabelText('note-state') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'confirmed' } });
    expect(input.value).toBe('confirmed');

    fireEvent.click(screen.getByTestId('visit-view-tab-coding'));
    fireEvent.click(screen.getByTestId('visit-view-tab-note'));

    expect(
      (screen.getByLabelText('note-state') as HTMLInputElement).value,
      'the doctor’s in-session state was lost by the view switch',
    ).toBe('confirmed');
  });

  it('the inactive panel is hidden BOTH ways — semantically and mechanically', () => {
    render(<VisitViewSwitch note={<p>note</p>} coding={<p>coding</p>} />);
    const coding = screen.getByTestId('visit-view-panel-coding');

    // `hidden` alone can be defeated by any author `display` rule with higher
    // specificity than the UA stylesheet, leaving the panel VISIBLE while
    // telling assistive tech it is absent — the worse of the two wrong answers.
    expect(coding.hasAttribute('hidden')).toBe(true);
    expect(coding.style.display).toBe('none');

    fireEvent.click(screen.getByTestId('visit-view-tab-coding'));
    expect(coding.hasAttribute('hidden')).toBe(false);
    expect(coding.style.display).toBe('');
  });

  it('the tablist is a coherent ARIA widget — roving tabindex and arrow keys', () => {
    render(<VisitViewSwitch note={<p>note</p>} coding={<p>coding</p>} />);
    const note = screen.getByTestId('visit-view-tab-note');
    const coding = screen.getByTestId('visit-view-tab-coding');

    expect(note.getAttribute('aria-selected')).toBe('true');
    expect(note.getAttribute('tabindex')).toBe('0');
    expect(coding.getAttribute('tabindex')).toBe('-1');

    // A `role="tab"` without arrow keys is a half-implemented pattern that
    // still passes axe — axe checks the roles cohere, not that the widget works.
    fireEvent.keyDown(note, { key: 'ArrowRight' });
    expect(coding.getAttribute('aria-selected')).toBe('true');
    expect(coding.getAttribute('tabindex')).toBe('0');

    fireEvent.keyDown(coding, { key: 'ArrowLeft' });
    expect(note.getAttribute('aria-selected')).toBe('true');
  });

  it('each tabpanel is labelled by its own tab, and the ids actually resolve', () => {
    // An `aria-controls` pointing at nothing is a silent a11y no-op.
    render(<VisitViewSwitch note={<p>note</p>} coding={<p>coding</p>} />);
    for (const v of ['note', 'coding']) {
      const tab = screen.getByTestId(`visit-view-tab-${v}`);
      const panel = screen.getByTestId(`visit-view-panel-${v}`);
      expect(tab.getAttribute('aria-controls')).toBe(panel.id);
      expect(panel.getAttribute('aria-labelledby')).toBe(tab.id);
      expect(panel.id.length).toBeGreaterThan(0);
    }
  });
});

// ---------------------------------------------------------------------------
// 2 · THE PURE #154 ARMS LIVE IN `gate-f8-s2-decision-reason.test.ts`
// ---------------------------------------------------------------------------
// Moved there, not deleted, because a component test cannot run in a git
// worktree at all (`vitest.config.ts:21` hard-codes a root `node_modules`
// sibling). Keeping the pure arms here would have made the substrate half of
// ruling #154 unprovable locally for the loop, which works in worktrees by
// standing rule. That file is render-free and runs anywhere.

// ---------------------------------------------------------------------------
// 3 · THE VIEW — what a doctor can and cannot do
// ---------------------------------------------------------------------------

describe('F8-S2 — the coding view', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const view = (over: Partial<Parameters<typeof IcdCodingView>[0]> = {}) =>
    render(
      <IcdCodingView
        visitId="visit-1"
        icdCodes={BLOB}
        icdDecisions={null}
        readonly={false}
        {...over}
      />,
    );

  it('renders every suggested code, its evidence, and the summary chip', () => {
    view();
    expect(screen.getByTestId('icd-card-K21.00')).toBeTruthy();
    expect(screen.getByTestId('icd-card-E11.9')).toBeTruthy();
    expect(screen.getByTestId('icd-evidence-K21.00').textContent).toContain(
      'reports reflux after meals',
    );
    expect(screen.getByTestId('icd-summary-chip').textContent).toContain('2 suggested');
  });

  it('⚠️ the AMBER drop is SHOWN, and it is NOT called unbillable', () => {
    // #149(e): `isValidIcd10` is a 604-code STARTER set, and 51 of the 65
    // production-rejected codes are REAL, SUBMITTABLE codes absent from it.
    // Telling a physician those are "not billable" is false, and the direction
    // of harm is UNDER-CODING.
    view();
    const drop = screen.getByTestId('icd-drop-Z48.815');
    expect(drop.textContent).toContain('Not in this build’s verified set');
    expect(drop.textContent?.toLowerCase()).not.toContain('not billable');
    expect(drop.textContent?.toLowerCase()).not.toContain('unbillable');
  });

  it('⚠️ the AMBER drop offers NO action — a dropped code can never be accepted', () => {
    // #149(g) makes that a property of the DATA. A button here would be the
    // one thing capable of making it false again, and #149(a)'s provenance
    // separation forbids this surface writing into `icdCodes` at all.
    view();
    const drop = screen.getByTestId('icd-drop-Z48.815');
    expect(drop.querySelectorAll('button').length).toBe(0);
  });

  it('⚠️ SIGNED renders the codes and NO controls at all — #153(e)', () => {
    view({
      readonly: true,
      icdDecisions: {
        'K21.00': { state: 'accepted', at: AT, byUserId: USER },
      },
    });
    expect(screen.getByTestId('icd-frozen-notice')).toBeTruthy();
    // The record is still READABLE — a signed note is what a coding dispute is
    // about, so hiding the surface would remove it exactly when it is needed.
    expect(screen.getByTestId('icd-card-K21.00')).toBeTruthy();
    expect(screen.queryByTestId('icd-accept-E11.9')).toBeNull();
    expect(screen.queryByTestId('icd-reject-E11.9')).toBeNull();
    expect(screen.queryByTestId('icd-undo-K21.00')).toBeNull();
  });

  it('Reject opens the reason picker and offers EXACTLY the vocabulary', () => {
    view();
    fireEvent.click(screen.getByTestId('icd-reject-K21.00'));
    for (const r of ICD_REJECTION_REASONS) {
      expect(screen.getByTestId(`icd-reason-K21.00-${r}`)).toBeTruthy();
    }
    // No free-text entry anywhere in the picker — ruling #154 at the surface.
    const picker = screen.getByTestId('icd-reason-picker-K21.00');
    expect(picker.querySelectorAll('input, textarea').length).toBe(0);
  });

  it('⚠️ a code cannot be rejected WITHOUT passing through the reason picker', () => {
    // The surface must not be able to send a reasonless rejection at all —
    // the route would refuse it, but a UI that can compose a request the
    // server always rejects is a dead button.
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, changed: true, projection: projectIcdDecisions(BLOB, null) }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    view();
    fireEvent.click(screen.getByTestId('icd-reject-K21.00'));
    expect(fetchSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId('icd-reason-K21.00-wrong_specificity'));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const body = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(body).toEqual({
      code: 'K21.00',
      decision: 'rejected',
      reason: 'wrong_specificity',
    });
  });

  it('⚠️ while ANY decision is in flight, EVERY control is disabled', () => {
    // Found by the adversarial pass. A per-code disable lets two decisions be
    // in flight at once; the SERVER serialises them correctly under a row lock,
    // but each response carries a full projection and whichever lands LAST wins
    // the render — so an earlier response can overwrite a later one and the
    // doctor watches a decision they just made disappear.
    //
    // The mutation that reddens this: change any `disabled={pending !== null}`
    // back to `disabled={pending === code}`.
    let release: (v: Response) => void = () => {};
    vi.spyOn(globalThis, 'fetch').mockReturnValue(
      new Promise<Response>((res) => {
        release = res;
      }),
    );
    view();
    fireEvent.click(screen.getByTestId('icd-accept-K21.00'));

    // The OTHER code's controls must be disabled too — that is the whole claim.
    expect(
      (screen.getByTestId('icd-accept-E11.9') as HTMLButtonElement).disabled,
      'a second decision could be started while the first was in flight',
    ).toBe(true);
    expect((screen.getByTestId('icd-reject-E11.9') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('icd-accept-K21.00') as HTMLButtonElement).disabled).toBe(true);

    release(
      new Response(JSON.stringify({ ok: true, changed: true, projection: projectIcdDecisions(BLOB, null) }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  it('Accept sends no reason key at all', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, changed: true, projection: projectIcdDecisions(BLOB, null) }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    view();
    fireEvent.click(screen.getByTestId('icd-accept-K21.00'));
    const body = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect('reason' in body).toBe(false);
  });

  it('⚠️ a REFUSED decision is SURFACED — silence is illegal', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: 'Visit is signed and locked.' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    view();
    fireEvent.click(screen.getByTestId('icd-accept-K21.00'));
    const alert = await screen.findByTestId('icd-decision-error');
    expect(alert.textContent).toContain('Visit is signed and locked.');
    // The refusal is audited server-side now; a UI that swallowed it would
    // leave the log and the screen disagreeing about the same event.
    expect(alert.getAttribute('role')).toBe('alert');
  });

  it('a rejected code renders its stored reason as PROSE from the label map', () => {
    view({
      icdDecisions: {
        'K21.00': { state: 'rejected', at: AT, byUserId: USER, reason: 'wrong_specificity' },
      },
    });
    expect(screen.getByTestId('icd-rejected-reason-K21.00').textContent).toBe(
      'Wrong specificity',
    );
    // The COLUMN holds the token; the prose lives in the component.
    expect(readIcdDecisions({
      'K21.00': { state: 'rejected', at: AT, byUserId: USER, reason: 'wrong_specificity' },
    })['K21.00']?.reason).toBe('wrong_specificity');
  });

  it('an ORPHANED decision is surfaced and is nobody’s default', () => {
    view({
      icdDecisions: { 'Z00.00': { state: 'accepted', at: AT, byUserId: USER } },
    });
    const section = screen.getByTestId('icd-section-no-longer-suggested');
    expect(section.textContent).toContain('Z00.00');
    // Not counted as accepted — it is a decision about a code this note no
    // longer carries and must not flow into the record.
    expect(screen.getByTestId('icd-summary-chip').textContent).toContain('0 accepted');
  });
});
