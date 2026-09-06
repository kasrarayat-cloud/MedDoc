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
//   · an OWNER row becomes editable             -> the owner block
//   · your own row becomes editable             -> the owner block
//   · a select stops deriving from ASSIGNABLE_ROLES -> the owner block
//   · the not-built half stops being stated     -> the owner block
//   · the panel implies a tech is broadly gated -> the vocabulary block
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
vi.mock('@/actions/practice-members', () => ({
  mintSeatInviteAction: vi.fn(),
  changeMemberRoleAction: vi.fn(),
  revokeSeatInviteAction: vi.fn(),
}));

import { PracticeMembersPanel } from '../practice-members-panel';
import { ASSIGNABLE_ROLES } from '@/lib/practice-roles';

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

describe('⚠️ the two rows an owner may NOT change are not drawn as changeable', () => {
  it('an OWNER row is text, never a control — even one that is NOT you', () => {
    // ⚠️ THE FIRST VERSION OF THIS ARM WAS VACUOUS, AND THE MUTATION SAID SO.
    // It asserted only against `u-owner`, whose fixture is ALSO `isSelf`, so
    // the `isSelf` term satisfied it and deleting the OWNER term from
    // `editable` redded NOTHING. A guard tested only where another guard
    // already answers is not tested.
    //
    // The second owner is not self, so this row can ONLY be text because of
    // the OWNER term.
    const withSecondOwner = [
      ...MEMBERS,
      { id: 'u-owner2', name: 'Dr Two', email: 'o2@x.test', practiceRole: 'OWNER', isSelf: false },
    ];
    render(<PracticeMembersPanel members={withSecondOwner} invites={[]} canAdminister />);
    expect(screen.queryByTestId('member-role-select-u-owner2')).toBeNull();
    expect(screen.getByTestId('member-role-u-owner2').textContent).toContain('Owner');
    // And your own owner row too, for the same reason by a different term.
    expect(screen.queryByTestId('member-role-select-u-owner')).toBeNull();
    // Non-vacuity: a row that SHOULD be editable in this same render is.
    expect(screen.getByTestId('member-role-select-u-tech')).toBeTruthy();
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

  it('⚠️ and the half that is NOT built is stated on the surface, with the right POLARITY', () => {
    // A missing control reads as an oversight. The note is what tells the
    // doctor the refusal is deliberate and that there is a route today.
    //
    // ⚠️ THIS ARM USED TO ASSERT VOCABULARY, NOT POLARITY, AND AN ADVERSARIAL
    // PASS SHOWED IT PASSING ON A NOTE THAT SAID THE EXACT OPPOSITE. `/owner/i`
    // plus `/demoted or removed/i` is satisfied by "Owners can be demoted or
    // removed at any time" — the inverse of what the server does. Matching a
    // NEGATION is what makes it a test of meaning rather than of keywords.
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    const note = (screen.getByTestId('members-owner-note').textContent ?? '').replace(/\s+/g, ' ');
    expect(note).toMatch(/cannot be demoted or removed/i);
    expect(note).not.toMatch(/can be demoted or removed/i);
    // and it must still say the thing that IS possible, or it reads as a wall
    expect(note).toMatch(/make another member an owner/i);

    // Non-vacuity: a non-administering view does not get it, so this is not a
    // string that is simply always on the page.
    cleanup();
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    expect(screen.queryByTestId('members-owner-note')).toBeNull();
  });

  it('⚠️ promoting to OWNER asks for confirmation, and a refusal does NOT submit', () => {
    // Promotion is irreversible until ADMIN-5 ships and OWNER is the option
    // directly above the current selection. An adversarial pass reached it in
    // one keystroke with nothing in the way.
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const submitSpy = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);

    const select = screen.getByTestId('member-role-select-u-clin') as HTMLSelectElement;
    const formEl = select.closest('form') as HTMLFormElement;
    formEl.addEventListener('submit', submitSpy as unknown as EventListener);

    fireEvent.change(select, { target: { value: 'OWNER' } });
    fireEvent.submit(formEl);
    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(confirmSpy.mock.calls[0][0]).toMatch(/cannot be undone/i);

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
