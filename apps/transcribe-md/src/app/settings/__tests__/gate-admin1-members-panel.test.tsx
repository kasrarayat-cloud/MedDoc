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
  removeMemberAction: vi.fn(),
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
  it('⚠️ ADMIN-5 — an OWNER row IS a control now, and only YOURSELF stays text', async () => {
    // ⚠️ THIS ARM ASSERTED THE EXACT OPPOSITE AND IS INVERTED DELIBERATELY. It
    // read "an OWNER row is text, never a control — even one that is NOT you",
    // and the rule behind it is unchanged and still right: a control that is
    // drawn and then refused teaches the doctor the page lies. What changed is
    // which rows the server refuses. It refuses YOU; it no longer refuses an
    // owner.
    // ⚠️ A LOCAL FIXTURE WITH A SECOND OWNER, NOT AN EDIT TO `MEMBERS`. The
    // shared list has exactly one owner, and that owner is `isSelf` — so
    // against it, "an owner row is editable" and "your own row is not" are the
    // SAME row, and the arm could pass while testing only one of them. #195
    // made two owners a real shape; this is where the panel has to meet it.
    const TWO_OWNERS = [
      ...MEMBERS,
      { id: 'u-owner2', name: 'Dr Partner', email: 'p@x.test', practiceRole: 'OWNER', isSelf: false },
    ];
    render(<PracticeMembersPanel members={TWO_OWNERS} invites={[]} canAdminister />);

    // another owner: editable, and removable
    expect(screen.queryByTestId('member-role-select-u-owner2')).not.toBeNull();
    expect(screen.queryByTestId('member-remove-u-owner2')).not.toBeNull();

    // ⚠️ YOURSELF: NEITHER CONTROL, AND THE REMOVE ONE MATTERS MORE. The server
    // refuses both, but self-removal is the click that would strand a practice
    // fastest, and a disabled-looking button is not the same as no button.
    expect(screen.queryByTestId('member-role-select-u-owner')).toBeNull();
    expect(screen.queryByTestId('member-remove-u-owner')).toBeNull();

    // ⚠️ NON-VACUITY: a viewer who may not administer sees NO controls at all,
    // so the assertions above are about the owner's view rather than about
    // whether the testids exist anywhere on the page.
    cleanup();
    render(<PracticeMembersPanel members={TWO_OWNERS} invites={[]} canAdminister={false} />);
    expect(screen.queryByTestId('member-role-select-u-owner2')).toBeNull();
    expect(screen.queryByTestId('member-remove-u-owner2')).toBeNull();
    expect(screen.queryByTestId('member-remove-u-clin')).toBeNull();
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
    // ⚠️ ADMIN-5 INVERTED WHAT THIS ARM GUARDS, AND THE POLARITY DISCIPLINE IS
    // WHAT SURVIVED. The old note said owners "cannot be demoted or removed …
    // ask support", and this arm matched that NEGATION on purpose, because an
    // earlier version passed on a note asserting the exact opposite. Both
    // halves are now false, so `members-owner-note` is GONE — asserting its
    // absence is what proves the stale sentence cannot come back.
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);
    expect(screen.queryByTestId('members-owner-note')).toBeNull();

    const help = (screen.getByTestId('members-owner-help').textContent ?? '').replace(/\s+/g, ' ');
    // The polarity is now the other way, and it is matched the same way.
    expect(help).toMatch(/remove them from the practice/i);
    expect(help).not.toMatch(/cannot be demoted or removed/i);
    expect(help).not.toMatch(/ask support/i);
    // It must still name the constraint that IS real, or a doctor meets it as
    // a surprise refusal instead of as a rule.
    expect(help).toMatch(/at least one owner/i);

    // Non-vacuity: a non-administering view does not get it, so this is not a
    // string that is simply always on the page.
    cleanup();
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister={false} />);
    expect(screen.queryByTestId('members-owner-help')).toBeNull();
  });

  it('⚠️ promoting to OWNER asks for confirmation, and a refusal does NOT submit', () => {
    // ⚠️ THE CONFIRM OUTLIVED ITS ORIGINAL REASON, AND THAT IS DELIBERATE.
    // It was justified by promotion being IRREVERSIBLE until ADMIN-5 shipped;
    // ADMIN-5 has shipped, so that justification is gone. What has not gone is
    // that OWNER is the option directly above the current selection — an
    // adversarial pass reached it in one keystroke — and that handing somebody
    // administrative control of a clinic deserves a second deliberate act.
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const submitSpy = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(<PracticeMembersPanel members={MEMBERS} invites={[]} canAdminister />);

    const select = screen.getByTestId('member-role-select-u-clin') as HTMLSelectElement;
    const formEl = select.closest('form') as HTMLFormElement;
    formEl.addEventListener('submit', submitSpy as unknown as EventListener);

    fireEvent.change(select, { target: { value: 'OWNER' } });
    fireEvent.submit(formEl);
    expect(confirmSpy).toHaveBeenCalledOnce();
    // ⚠️ THE COPY MUST NOT PROMISE IRREVERSIBILITY THAT ADMIN-5 REMOVED. It used
    // to be pinned against /cannot be undone/i; that sentence is now false, and
    // a confirm that overstates a consequence is how a doctor learns to
    // disbelieve confirms. What it must still do is name the constraint.
    expect(confirmSpy.mock.calls[0][0]).not.toMatch(/cannot be undone/i);
    expect(confirmSpy.mock.calls[0][0]).toMatch(/keeps one owner/i);

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
