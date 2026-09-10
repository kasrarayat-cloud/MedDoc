// ============================================================================
// GATE — ADMIN-1's MEMBERS PANEL: what is DRAWN, and for whom.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE PROVES NOTHING ABOUT SECURITY, and says so rather than implying
// otherwise. `canAdminister` decides what is RENDERED; the server actions
// re-read the actor's role from the database on every call, and
// `gate-admin1-practice-admin` is where that is measured. What is proved here
// is the other half: that a doctor is not shown a control the server will
// refuse, because a page that offers a button and then declines it teaches the
// practice that the page lies.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · a non-owner is shown role controls        -> the visibility block
//   · the member LIST is hidden from non-owners -> the visibility block
//   · another OWNER's row stops being editable  -> the owner block (ADMIN-5)
//   · your own row becomes editable             -> the owner block
//   · a select stops deriving from ASSIGNABLE_ROLES -> the owner block
//   · the stale "cannot be demoted" note returns -> the owner block (ADMIN-5)
//   · Remove appears on your own row, or unconfirmed -> the ADMIN-5 block
//   · Transfer offers yourself, or a non-derived step-down -> the ADMIN-5 block
//   · the panel implies a tech is broadly gated -> the vocabulary block
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
vi.mock('@/actions/practice-members', () => ({
  mintSeatInviteAction: vi.fn(),
  changeMemberRoleAction: vi.fn(),
  revokeSeatInviteAction: vi.fn(),
  removeMemberAction: vi.fn(async () => ({ ok: true, changedAt: 1 })),
  transferOwnershipAction: vi.fn(async () => ({ ok: true, changedAt: 1 })),
}));

import { PracticeMembersPanel } from '../practice-members-panel';
import { removeMemberAction, transferOwnershipAction } from '@/actions/practice-members';
import { ASSIGNABLE_ROLES, STEP_DOWN_OPTIONS } from '@/lib/practice-roles';

const MEMBERS = [
  { id: 'u-owner', name: 'Dr Owner', email: 'o@x.test', practiceRole: 'OWNER', isSelf: true },
  { id: 'u-clin', name: 'Dr Clin', email: 'c@x.test', practiceRole: 'CLINICIAN', isSelf: false },
  { id: 'u-tech', name: 'Tay Tech', email: 't@x.test', practiceRole: 'TECH', isSelf: false },
];

describe('⚠️ the list is practice-uniform; the CONTROLS are not', () => {
  it('a non-owner still sees every member — the boundary is on ACTIONS, not visibility', () => {
    // SPEC §4.1b, and the enum's own sentence. A clinician who cannot see who
    // else is in their practice cannot tell who to ask to sign.
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    for (const m of MEMBERS) expect(screen.getByTestId(`member-row-${m.id}`)).toBeTruthy();
  });

  it('and is shown NO role controls, no invite list and no mint form', () => {
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    expect(screen.queryByTestId('member-role-select-u-tech')).toBeNull();
    expect(screen.queryByTestId('invite-list')).toBeNull();
    expect(screen.queryByTestId('mint-seat')).toBeNull();
    expect(screen.getByTestId('members-readonly-note')).toBeTruthy();
  });

  it('an owner IS shown them — the arms above are not passing on an empty panel', () => {
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    expect(screen.getByTestId('member-role-select-u-tech')).toBeTruthy();
    expect(screen.getByTestId('mint-seat')).toBeTruthy();
    expect(screen.queryByTestId('members-readonly-note')).toBeNull();
  });
});

describe('⚠️ the row an owner may NOT change is not drawn as changeable — and ADMIN-5 opened the other', () => {
  it('⚠️ ADMIN-5 — ANOTHER owner\'s row IS a control now; your OWN owner row is still text', () => {
    // This arm used to assert the opposite ("an OWNER row is text, never a
    // control — even one that is NOT you"), mirroring `CANNOT_CHANGE_AN_OWNER`.
    // ADMIN-5 deleted that refusal, so the page must stop hiding the control:
    // a capability the server grants and the page withholds is a page that
    // lies in the other direction.
    //
    // The second owner is not self, so this row is a control ONLY because the
    // OWNER term is gone — re-adding it reds here.
    const withSecondOwner = [
      ...MEMBERS,
      { id: 'u-owner2', name: 'Dr Two', email: 'o2@x.test', practiceRole: 'OWNER', isSelf: false },
    ];
    render(<PracticeMembersPanel members={withSecondOwner} invites={[]} canAdminister />);
    const select = screen.getByTestId('member-role-select-u-owner2') as HTMLSelectElement;
    expect(select.value, 'the other owner\'s control does not start at OWNER').toBe('OWNER');
    // Your own owner row stays text — by the isSelf term, which still stands.
    expect(screen.queryByTestId('member-role-select-u-owner')).toBeNull();
    expect(screen.getByTestId('member-role-u-owner').textContent).toContain('Owner');
  });

  it('and neither is your own row', () => {
    const asClinician = MEMBERS.map((m) => ({ ...m, isSelf: m.id === 'u-clin' }));
    render(<PracticeMembersPanel members={asClinician} invites={[]} canAdminister />);
    expect(screen.queryByTestId('member-role-select-u-clin')).toBeNull();
    // The tech row, which is neither, still is.
    expect(screen.getByTestId('member-role-select-u-tech')).toBeTruthy();
  });

  it('the OWNER option IS offered now, and both selects are DERIVED from the server list', () => {
    // The OWNER-not-exclusive decision (branch
    // `feat/ruling-195-owner-not-exclusive`) opened promotion, so the control
    // that hands the role out must exist.
    //
    // ⚠️ ASSERTED AGAINST `ASSIGNABLE_ROLES` ITSELF, NOT AGAINST A RETYPED
    // LITERAL. Both selects previously hardcoded their options, which means
    // widening the server constant would have passed every server test while
    // this page kept offering the old two — the feature shipping invisible
    // under a green suite. Comparing to the imported constant is what makes
    // that drift impossible rather than merely unlikely.
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    const select = screen.getByTestId('member-role-select-u-tech');
    const values = within(select).getAllByRole('option').map((o) => (o as HTMLOptionElement).value);
    expect(values).toEqual([...ASSIGNABLE_ROLES]);
    expect(values).toContain('OWNER');

    const mint = screen.getByTestId('mint-role') as HTMLSelectElement;
    const mintValues = within(mint).getAllByRole('option').map((o) => (o as HTMLOptionElement).value);
    expect(mintValues).toEqual([...ASSIGNABLE_ROLES]);
  });

  it('⚠️ ADMIN-5 — the stale "cannot be demoted or removed" note is GONE, and the help says what is still refused', () => {
    // `members-owner-note` told the doctor owners "cannot be demoted or removed
    // here yet — ask support". ADMIN-5 ships both, and the row requires the note
    // removed in the SAME commit that makes it false: a disclosure that outlives
    // its refusal sends a doctor to support for something the page now does.
    //
    // ⚠️ POLARITY, NOT VOCABULARY — the lesson this arm's predecessor recorded.
    // "Owners cannot be demoted" and "owners can be demoted" share every
    // keyword; the NEGATION is what is tested.
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    expect(screen.queryByTestId('members-owner-note'), 'the stale note survived').toBeNull();
    const help = (screen.getByTestId('members-owner-help').textContent ?? '').replace(/\s+/g, ' ');
    expect(help).not.toMatch(/cannot be demoted|cannot be removed|ask support/i);
    expect(help).toMatch(/remove/i);
    // the one owner case still refused is stated, with the door that handles it
    expect(help).toMatch(/at least one owner/i);
    expect(help).toMatch(/transfer ownership/i);

    // Non-vacuity: a non-administering view does not get it.
    cleanup();
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    expect(screen.queryByTestId('members-owner-help')).toBeNull();
  });

  it('⚠️ promoting to OWNER asks for confirmation, and a refusal does NOT submit', () => {
    // OWNER hands over administration and is the option directly above the
    // current selection. An adversarial pass reached it in one keystroke with
    // nothing in the way. (Since ADMIN-5 the words say what an owner can do —
    // including to you — rather than "cannot be undone", which became false.)
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const submitSpy = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);

    const select = screen.getByTestId('member-role-select-u-clin') as HTMLSelectElement;
    const formEl = select.closest('form') as HTMLFormElement;
    formEl.addEventListener('submit', submitSpy as unknown as EventListener);

    fireEvent.change(select, { target: { value: 'OWNER' } });
    fireEvent.submit(formEl);
    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(confirmSpy.mock.calls[0][0]).toMatch(/remove other owners/i);
    expect(confirmSpy.mock.calls[0][0]).not.toMatch(/cannot be undone|cannot be demoted/i);

    // ⚠️ THE NON-VACUITY THAT MATTERS: a NON-owner role must not be confirmed at
    // all. An arm that only proves "confirm was called" would also pass on a
    // build that confirms every change — which trains the doctor to dismiss it.
    confirmSpy.mockClear();
    fireEvent.change(select, { target: { value: 'TECH' } });
    fireEvent.submit(formEl);
    expect(confirmSpy).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });
});

// ============================================================================
// ADMIN-5 / ADMIN-5a — REMOVE AND TRANSFER, drawn only where the server allows.
// ============================================================================
describe('⚠️ ADMIN-5 — Remove is drawn for every OTHER member, and always confirmed', () => {
  it('a Remove control on every row but your own — including another OWNER', () => {
    const withSecondOwner = [
      ...MEMBERS,
      { id: 'u-owner2', name: 'Dr Two', email: 'o2@x.test', practiceRole: 'OWNER', isSelf: false },
    ];
    render(<PracticeMembersPanel members={withSecondOwner} invites={[]} canAdminister />);
    for (const id of ['u-clin', 'u-tech', 'u-owner2']) {
      expect(screen.getByTestId(`member-remove-${id}`), `no Remove on ${id}`).toBeTruthy();
    }
    expect(screen.queryByTestId('member-remove-u-owner'), 'Remove drawn on your own row').toBeNull();
  });

  it('and NONE for a non-owner viewer', () => {
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    for (const m of MEMBERS) expect(screen.queryByTestId(`member-remove-${m.id}`)).toBeNull();
  });

  it('⚠️ a DECLINED confirm dispatches nothing; an accepted one does (non-vacuity)', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    vi.mocked(removeMemberAction).mockClear();
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    const button = screen.getByTestId('member-remove-u-tech');
    fireEvent.submit(button.closest('form') as HTMLFormElement);
    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(confirmSpy.mock.calls[0][0]).toMatch(/Remove Tay Tech from this practice/);
    expect(confirmSpy.mock.calls[0][0]).toMatch(/stay with the practice/i);
    await new Promise((r) => setTimeout(r, 20));
    expect(removeMemberAction, 'a declined removal was dispatched anyway').not.toHaveBeenCalled();

    // POSITIVE CONTROL — without it, "not dispatched" also holds for a form
    // that can never dispatch in this environment.
    confirmSpy.mockReturnValue(true);
    fireEvent.submit(button.closest('form') as HTMLFormElement);
    await waitFor(() => expect(removeMemberAction).toHaveBeenCalledOnce());
    const fd = vi.mocked(removeMemberAction).mock.calls[0][1] as FormData;
    expect(fd.get('userId')).toBe('u-tech');
    confirmSpy.mockRestore();
  });
});

describe('⚠️ ADMIN-5a — Transfer ownership offers only OTHER members and a DERIVED step-down', () => {
  it('is drawn for an owner, never for a non-owner', () => {
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    expect(screen.getByTestId('transfer-ownership')).toBeTruthy();
    cleanup();
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    expect(screen.queryByTestId('transfer-ownership')).toBeNull();
  });

  it('the target list is every member but you; the step-down list IS `STEP_DOWN_OPTIONS`', () => {
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    const targets = within(screen.getByTestId('transfer-target'))
      .getAllByRole('option')
      .map((o) => (o as HTMLOptionElement).value);
    expect(targets).toEqual(['u-clin', 'u-tech']);
    const thens = within(screen.getByTestId('transfer-then'))
      .getAllByRole('option')
      .map((o) => (o as HTMLOptionElement).value);
    expect(thens).toEqual([...STEP_DOWN_OPTIONS]);
    expect(thens).not.toContain('OWNER');
    expect(thens).toContain('LEAVE');
  });

  it('a practice with nobody else says so rather than offering an empty select', () => {
    render(<PracticeMembersPanel members={[MEMBERS[0]!]} invites={[]} canAdminister />);
    expect(screen.getByTestId('transfer-no-candidates')).toBeTruthy();
    expect(screen.queryByTestId('transfer-target')).toBeNull();
  });

  it('⚠️ LEAVE is confirmed in words that say you lose access; a declined confirm dispatches nothing', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    vi.mocked(transferOwnershipAction).mockClear();
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    fireEvent.change(screen.getByTestId('transfer-then'), { target: { value: 'LEAVE' } });
    const formEl = screen.getByTestId('transfer-submit').closest('form') as HTMLFormElement;
    fireEvent.submit(formEl);
    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(confirmSpy.mock.calls[0][0]).toMatch(/leave the practice/i);
    expect(confirmSpy.mock.calls[0][0]).toMatch(/lose access/i);
    await new Promise((r) => setTimeout(r, 20));
    expect(transferOwnershipAction).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.submit(formEl);
    await waitFor(() => expect(transferOwnershipAction).toHaveBeenCalledOnce());
    const fd = vi.mocked(transferOwnershipAction).mock.calls[0][1] as FormData;
    expect(fd.get('then')).toBe('LEAVE');
    expect(fd.get('userId')).toBe('u-clin');
    confirmSpy.mockRestore();
  });
});

describe('⚠️ the vocabulary — a tech is gated at ONE action, and the page says only that', () => {
  it('names signing as the difference, and does not imply a broader restriction', () => {
    // ⚠️ THE PRODUCT RISK IS OVERSTATEMENT, not understatement. Signing is the
    // sole role-gated action (RULINGS 2026-08-06, re-ratified 2026-09-05):
    // techs prepare, including deleting unsigned drafts, and deliver. A page
    // implying otherwise teaches a practice to work around a boundary that is
    // not there.
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    const mint = screen.getByTestId('mint-role').textContent ?? '';
    expect(mint).toMatch(/cannot sign/i);
    expect(mint).toMatch(/prepares and delivers/i);
    // Nothing claiming a wider gate.
    expect(mint).not.toMatch(/read-only|cannot edit|cannot delete|view only/i);
  });
});

describe('⚠️ the once-only code is labelled BEFORE it is shown', () => {
  it('the empty invite list says so rather than rendering nothing', () => {
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    expect(screen.getByTestId('invite-list-empty')).toBeTruthy();
  });

  it('an outstanding invite renders with a revoke control', () => {
    render(
      <PracticeMembersPanel
        members={MEMBERS}
        canAdminister
        invites={[
          {
            id: 'inv-1',
            label: 'Locum cover',
            practiceRole: 'CLINICIAN',
            expiresAt: null,
            createdAt: '2026-09-05T00:00:00.000Z',
          },
        ]}
      />,
    );
    expect(screen.getByTestId('invite-row-inv-1')).toBeTruthy();
    expect(screen.getByTestId('invite-revoke-inv-1')).toBeTruthy();
    expect(screen.queryByTestId('invite-list-empty')).toBeNull();
  });
});
