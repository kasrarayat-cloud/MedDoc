'use client';

// ============================================================================
// ADMIN-1 — THE MEMBERS PANEL.
// ----------------------------------------------------------------------------
// ⚠️ NO FIGMA FRAMES EXIST FOR THIS SURFACE, and none were invented. Everything
// here is composed from shipped, already-approved settings idioms — the C3
// section shell, `qm-lin-btn`, `SpecularButton`, `LocalTime`, the `--color-
// linear-*` tokens and the same inline-style shape `settings/page.tsx` already
// uses for its read-only rows. The states that genuinely need a designer's call
// are on the batched Figma request list rather than guessed at here.
//
// ⚠️ THE TOKEN NAMES ARE THE BRIDGED SPELLINGS — `--color-linear-text`,
// `-text-2`, `-text-3` — NOT `-text-primary/-secondary/-tertiary`. The first
// draft used the latter and `gate-rounds-bridge` caught it: names a C1 surface
// reads but the host bridge does not redeclare keep their OLD-SKIN value, so
// this panel would have rendered wrong on an otherwise-correct screen. Read the
// bridged set off `rounds-tokens.css`; do not guess it from the name.
//
// ⚠️ THE CONTROLS ARE HIDDEN FOR NON-OWNERS AND THE SERVER REFUSES ANYWAY.
// `canAdminister` only decides what is DRAWN. Every action re-reads the actor's
// role from the database, because a prop is a claim the client makes about
// itself and a JWT can be five minutes stale.
// ============================================================================

import { useActionState, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { LocalTime } from '@/components/ui/local-time';
import { SpecularButton } from '@/components/specular-button';
import { ASSIGNABLE_ROLES, LEAVE_PRACTICE, STEP_DOWN_OPTIONS } from '@/lib/practice-roles';
import {
  changeMemberRoleAction,
  mintSeatInviteAction,
  removeMemberAction,
  revokeSeatInviteAction,
  transferOwnershipAction,
  type RoleState,
  type SeatState,
} from '@/actions/practice-members';

const ROLE_LABEL: Record<string, string> = {
  OWNER: 'Owner',
  CLINICIAN: 'Clinician',
  TECH: 'Tech',
};

/** What each role may do, in the doctor's words rather than the enum's.
 *  ⚠️ SIGNING IS THE ONLY DIFFERENCE, and saying so plainly is the point: a
 *  page that implies a tech is restricted everywhere teaches the practice to
 *  work around a boundary that is not there. */
const ROLE_HINT: Record<string, string> = {
  OWNER: 'Signs notes, and manages members.',
  CLINICIAN: 'Signs notes.',
  TECH: 'Prepares and delivers notes. Cannot sign.',
};

/**
 * ⚠️ THE OPTIONS ARE DERIVED FROM THE SERVER'S OWN LIST, NEVER RETYPED.
 *
 * Both selects used to hardcode `CLINICIAN`/`TECH`. That is a silent-drift
 * shape, and the OWNER-not-exclusive ruling is exactly the change that would
 * have exposed it: widening `ASSIGNABLE_ROLES` on the server would have passed
 * every server test while the page kept offering the old two, so the feature
 * would have shipped invisible with a green suite. Derived here, the constant
 * and the control cannot disagree.
 */
const ROLE_OPTIONS = ASSIGNABLE_ROLES.map((value) => ({
  value,
  label: ROLE_LABEL[value] ?? value,
  hint: ROLE_HINT[value] ?? '',
}));

export interface MemberRow {
  id: string;
  name: string | null;
  email: string;
  practiceRole: string | null;
  isSelf: boolean;
}

export interface InviteRow {
  id: string;
  label: string | null;
  practiceRole: string | null;
  expiresAt: string | null;
  createdAt: string;
}

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '12px 0',
  borderBottom: '1px solid var(--color-linear-hairline)',
};

export function PracticeMembersPanel({
  members,
  invites,
  canAdminister,
}: {
  members: MemberRow[];
  invites: InviteRow[];
  canAdminister: boolean;
}) {
  return (
    <div data-testid="members-panel">
      <MemberList members={members} canAdminister={canAdminister} />
      {canAdminister ? (
        <>
          {/* ⚠️ `members-owner-note` WAS DELETED HERE, IN THE COMMIT THAT MADE IT
              FALSE (the ADMIN-5 row requires exactly that). It told the doctor
              owners "cannot be demoted or removed here yet — ask support".
              ADMIN-5 ships both, so leaving the sentence would send a practice
              owner to support for something the page in front of them now does;
              a disclosure that outlives its refusal is worse than none, because
              the doctor cannot tell it is stale. What IS still refused is said
              instead: the last owner cannot leave without handing over. */}
          <p
            data-testid="members-owner-help"
            style={{ marginTop: 12, fontSize: 13, color: 'var(--color-linear-text-3)' }}
          >
            You can make another member an owner, change any other member&rsquo;s role, or
            remove them from the practice. A practice must always keep at least one owner
            &mdash; to step down yourself, transfer ownership below.
          </p>
          <TransferOwnership members={members} />
          <InviteList invites={invites} />
          <MintSeat />
        </>
      ) : (
        <p
          data-testid="members-readonly-note"
          style={{ marginTop: 16, fontSize: 13, color: 'var(--color-linear-text-3)' }}
        >
          Only a practice owner can invite members or change roles.
        </p>
      )}
    </div>
  );
}

function MemberList({
  members,
  canAdminister,
}: {
  members: MemberRow[];
  canAdminister: boolean;
}) {
  return (
    <div data-testid="member-list">
      {members.map((m) => (
        <div key={m.id} style={rowStyle} data-testid={`member-row-${m.id}`}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 14, color: 'var(--color-linear-text)' }}>
              {m.name?.trim() || m.email}
              {m.isSelf ? (
                <span
                  style={{ marginLeft: 8, fontSize: 12, color: 'var(--color-linear-text-3)' }}
                >
                  you
                </span>
              ) : null}
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--color-linear-text-3)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {m.email}
            </div>
          </div>
          <RoleCell member={m} canAdminister={canAdminister} />
          <RemoveCell member={m} canAdminister={canAdminister} />
        </div>
      ))}
    </div>
  );
}

function RoleCell({
  member,
  canAdminister,
}: {
  member: MemberRow;
  canAdminister: boolean;
}) {
  const [state, action, pending] = useActionState<RoleState, FormData>(
    changeMemberRoleAction,
    null,
  );
  const seen = useRef<RoleState>(null);

  useEffect(() => {
    if (state === seen.current) return;
    seen.current = state;
    if (state?.ok === true) toast.success('Role updated');
    // ⚠️ THE REFUSAL IS SPOKEN. The server's message is the doctor-facing one,
    // and silence here would make a refused change look like a change.
    else if (state?.ok === false) toast.error(state.message);
  }, [state]);

  const role = member.practiceRole ?? '—';
  const label = ROLE_LABEL[role] ?? role;

  // Your own row is shown as text — the server refuses a self role change, and a
  // control that is drawn and then refused teaches the doctor the page lies.
  // ⚠️ ADMIN-5 — ANOTHER OWNER'S ROW IS A CONTROL NOW. The `!== 'OWNER'` term
  // that stood here mirrored `CANNOT_CHANGE_AN_OWNER`, which is deleted; the
  // one owner case still refused (the last owner) is the database's, and a
  // re-checked active-owner actor is never the last owner of what they demote.
  const editable = canAdminister && !member.isSelf;

  if (!editable) {
    return (
      <span
        data-testid={`member-role-${member.id}`}
        title={ROLE_HINT[role] ?? undefined}
        style={{ fontSize: 13, color: 'var(--color-linear-text-2)' }}
      >
        {label}
      </span>
    );
  }

  return (
    <form
      action={action}
      style={{ display: 'flex', alignItems: 'center', gap: 8 }}
      // ⚠️ PROMOTION TO OWNER HANDS OVER ADMINISTRATION, AND IT SITS ONE
      // ARROW-KEY FROM THE CURRENT SELECTION. The options derive from
      // ASSIGNABLE_ROLES, where OWNER is first, so a CLINICIAN row opens with
      // OWNER directly above the selected item. An adversarial pass reached it
      // by one keystroke with nothing in the way. (Until ADMIN-5 this confirm
      // also said "this cannot be undone"; an owner can be demoted now, so the
      // sentence that is still true is WHAT an owner can do — including to you.)
      //
      // ⚠️ THE CONFIRM IS ON THE OWNER VALUE ONLY. Confirming every role change
      // would train the doctor to dismiss it, which is how a confirm stops
      // being a control.
      onSubmit={(e) => {
        const chosen = new FormData(e.currentTarget).get('role');
        if (chosen !== 'OWNER') return;
        const who = member.name?.trim() || member.email;
        const ok = window.confirm(
          `Make ${who} an owner of this practice?\n\n` +
            'Owners can manage members, invite people, and change or remove other owners — ' +
            'including you.',
        );
        if (!ok) e.preventDefault();
      }}
    >
      <input type="hidden" name="userId" value={member.id} />
      <label className="qm-sr-only" htmlFor={`role-${member.id}`}>
        Role for {member.name?.trim() || member.email}
      </label>
      <select
        id={`role-${member.id}`}
        name="role"
        defaultValue={member.practiceRole ?? 'TECH'}
        disabled={pending}
        data-testid={`member-role-select-${member.id}`}
        className="qm-lin-btn qm-tap-44"
        style={{ fontSize: 13, padding: '6px 10px' }}
      >
        {ROLE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <SpecularButton type="submit" disabled={pending} data-testid={`member-role-save-${member.id}`}>
        {pending ? 'Saving…' : 'Save'}
      </SpecularButton>
    </form>
  );
}

// ============================================================================
// ADMIN-5 — REMOVE. Salvaged from PR #1026's panel; the server door is new.
// ============================================================================
function RemoveCell({
  member,
  canAdminister,
}: {
  member: MemberRow;
  canAdminister: boolean;
}) {
  const [state, action, pending] = useActionState<RoleState, FormData>(
    removeMemberAction,
    null,
  );
  const seen = useRef<RoleState>(null);

  useEffect(() => {
    if (state === seen.current) return;
    seen.current = state;
    if (state?.ok === true) toast.success('Member removed');
    // ⚠️ THE REFUSAL IS SPOKEN — the server's message is the doctor-facing one.
    else if (state?.ok === false) toast.error(state.message);
  }, [state]);

  // ⚠️ NO CONTROL AT ALL FOR YOURSELF. The server refuses self-removal, and
  // drawing a button that is always refused teaches the doctor the page lies.
  // Leaving is the transfer control's job.
  if (!canAdminister || member.isSelf) return null;

  const who = member.name?.trim() || member.email;

  return (
    <form
      action={action}
      style={{ display: 'flex', alignItems: 'center' }}
      // ⚠️ CONFIRMED ALWAYS — unlike the role control. Removal ends somebody's
      // access to a clinical system in one click and cannot be undone from this
      // page, so every removal is "the irreversible value".
      onSubmit={(e) => {
        const ok = window.confirm(
          `Remove ${who} from this practice?\n\n` +
            'They will be signed out and lose access immediately. Their visits, patients and ' +
            'audit history stay with the practice. This cannot be undone from this page.',
        );
        if (!ok) e.preventDefault();
      }}
    >
      <input type="hidden" name="userId" value={member.id} />
      {/* ⚠️ A PLAIN <button>, NOT `SpecularButton`: that component enumerates
          its props and never spreads, so `data-testid` would be silently
          dropped and the gate that claims to drive this control could not. */}
      <button
        type="submit"
        disabled={pending}
        data-testid={`member-remove-${member.id}`}
        className="qm-lin-btn qm-tap-44"
        style={{ fontSize: 13, padding: '6px 10px', color: 'var(--color-linear-text-2)' }}
      >
        {pending ? 'Removing…' : 'Remove'}
      </button>
    </form>
  );
}

// ============================================================================
// ADMIN-5a — TRANSFER OWNERSHIP. The one door by which an owner steps down:
// the incoming owner is promoted FIRST, then you step down or leave, in ONE
// transaction on the server.
// ============================================================================
const stepDownLabel = (v: string) =>
  v === LEAVE_PRACTICE ? 'Leave the practice' : `Stay as ${(ROLE_LABEL[v] ?? v).toLowerCase()}`;

function TransferOwnership({ members }: { members: MemberRow[] }) {
  const [state, action, pending] = useActionState<RoleState, FormData>(
    transferOwnershipAction,
    null,
  );
  const seen = useRef<RoleState>(null);
  useEffect(() => {
    if (state === seen.current) return;
    seen.current = state;
    if (state?.ok === true) toast.success('Ownership transferred');
    else if (state?.ok === false) toast.error(state.message);
  }, [state]);

  const candidates = members.filter((m) => !m.isSelf);

  return (
    <section style={{ marginTop: 24 }} data-testid="transfer-ownership">
      <h3 style={{ fontSize: 13, color: 'var(--color-linear-text-2)', margin: '0 0 8px' }}>
        Transfer ownership
      </h3>
      <p style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--color-linear-text-3)' }}>
        Hand the practice to another member. They become an owner first, then you step down or
        leave &mdash; in one step, so the practice is never left without an owner.
      </p>
      {candidates.length === 0 ? (
        <p
          data-testid="transfer-no-candidates"
          style={{ fontSize: 13, color: 'var(--color-linear-text-3)', margin: 0 }}
        >
          There is nobody to hand the practice to yet. Invite a member first.
        </p>
      ) : (
        <form
          action={action}
          style={{ display: 'grid', gap: 10, maxWidth: 460 }}
          onSubmit={(e) => {
            const fd = new FormData(e.currentTarget);
            const to = candidates.find((m) => m.id === fd.get('userId'));
            const then = String(fd.get('then') ?? '');
            const who = to?.name?.trim() || to?.email || 'this member';
            const leaving = then === LEAVE_PRACTICE;
            const ok = window.confirm(
              `Make ${who} an owner, then ${leaving ? 'leave the practice' : stepDownLabel(then).toLowerCase()}?\n\n` +
                (leaving
                  ? 'You will be signed out and lose access to this practice. This cannot be undone from this page.'
                  : 'You will no longer be able to manage members or invite people.'),
            );
            if (!ok) e.preventDefault();
          }}
        >
          <label style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
            Hand the practice to
            <select
              name="userId"
              data-testid="transfer-target"
              className="qm-lin-btn qm-tap-44"
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px' }}
            >
              {candidates.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name?.trim() || m.email}
                </option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
            Then
            <select
              name="then"
              defaultValue={STEP_DOWN_OPTIONS[0]}
              data-testid="transfer-then"
              className="qm-lin-btn qm-tap-44"
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px' }}
            >
              {STEP_DOWN_OPTIONS.map((v) => (
                <option key={v} value={v}>
                  {stepDownLabel(v)}
                </option>
              ))}
            </select>
          </label>
          <div>
            <button
              type="submit"
              disabled={pending}
              data-testid="transfer-submit"
              className="qm-lin-btn qm-tap-44"
            >
              {pending ? 'Transferring…' : 'Transfer ownership'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function InviteList({ invites }: { invites: InviteRow[] }) {
  const [state, action, pending] = useActionState<RoleState, FormData>(
    revokeSeatInviteAction,
    null,
  );
  const seen = useRef<RoleState>(null);
  useEffect(() => {
    if (state === seen.current) return;
    seen.current = state;
    if (state?.ok === true) toast.success('Invite revoked');
    else if (state?.ok === false) toast.error(state.message);
  }, [state]);

  return (
    <section style={{ marginTop: 24 }} data-testid="invite-list">
      <h3 style={{ fontSize: 13, color: 'var(--color-linear-text-2)', margin: '0 0 8px' }}>
        Outstanding invites
      </h3>
      {invites.length === 0 ? (
        <p
          data-testid="invite-list-empty"
          style={{ fontSize: 13, color: 'var(--color-linear-text-3)', margin: 0 }}
        >
          No unused invites.
        </p>
      ) : (
        invites.map((i) => (
          <div key={i.id} style={rowStyle} data-testid={`invite-row-${i.id}`}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 14, color: 'var(--color-linear-text)' }}>
                {i.label ?? 'Untitled seat'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
                {ROLE_LABEL[i.practiceRole ?? ''] ?? i.practiceRole} ·{' '}
                {i.expiresAt ? (
                  <>
                    expires <LocalTime iso={i.expiresAt} variant="date" />
                  </>
                ) : (
                  'no expiry'
                )}
              </div>
            </div>
            <form action={action}>
              <input type="hidden" name="inviteId" value={i.id} />
              <button
                type="submit"
                disabled={pending}
                className="qm-lin-btn qm-tap-44"
                data-testid={`invite-revoke-${i.id}`}
              >
                Revoke
              </button>
            </form>
          </div>
        ))
      )}
    </section>
  );
}

function MintSeat() {
  const [state, action, pending] = useActionState<SeatState, FormData>(
    mintSeatInviteAction,
    null,
  );
  const [copied, setCopied] = useState(false);
  const seen = useRef<SeatState>(null);

  useEffect(() => {
    if (state === seen.current) return;
    seen.current = state;
    setCopied(false);
    if (state?.ok === false) toast.error(state.message);
  }, [state]);

  return (
    <section style={{ marginTop: 24 }} data-testid="mint-seat">
      <h3 style={{ fontSize: 13, color: 'var(--color-linear-text-2)', margin: '0 0 8px' }}>
        Invite a member
      </h3>

      <form action={action} style={{ display: 'grid', gap: 10, maxWidth: 460 }}>
        <label style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
          Who is this seat for?
          <input
            name="label"
            required
            maxLength={120}
            placeholder="Dr Okafor — new associate"
            data-testid="mint-label"
            className="qm-lin-btn"
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px' }}
          />
        </label>

        <label style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
          Role
          <select
            name="role"
            defaultValue="CLINICIAN"
            data-testid="mint-role"
            className="qm-lin-btn qm-tap-44"
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px' }}
          >
            {ROLE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.hint ? `${o.label} — ${o.hint.replace(/\.$/, '').toLowerCase()}` : o.label}
              </option>
            ))}
          </select>
        </label>

        <label style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
          Expires after (days, optional)
          <input
            name="expiresInDays"
            type="number"
            min={1}
            max={90}
            placeholder="never"
            data-testid="mint-expiry"
            className="qm-lin-btn"
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px' }}
          />
        </label>

        <div>
          <SpecularButton type="submit" disabled={pending} data-testid="mint-submit">
            {pending ? 'Creating…' : 'Create invite'}
          </SpecularButton>
        </div>
      </form>

      {state?.ok === true ? (
        <div
          data-testid="mint-result"
          style={{
            marginTop: 14,
            padding: '12px 14px',
            borderRadius: 8,
            border: '1px dashed var(--color-linear-border-strong)',
            background: 'var(--color-linear-row-hover)',
          }}
        >
          {/* ⚠️ SAID BEFORE THE CODE, NOT AFTER. This is the only time the value
              exists — the row stores a SHA-256 and nothing can recover it — and
              a warning underneath a code the doctor has already scrolled past
              is a warning nobody read. */}
          <p
            data-testid="mint-once-warning"
            style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--color-linear-text)' }}
          >
            This code is shown once. Copy it now — it cannot be shown again.
          </p>
          <code
            data-testid="mint-code"
            style={{
              display: 'block',
              fontFamily: 'var(--font-mono, ui-monospace), monospace',
              fontSize: 16,
              letterSpacing: '0.06em',
              color: 'var(--color-linear-text)',
              wordBreak: 'break-all',
            }}
          >
            {state.code}
          </code>
          <button
            type="button"
            className="qm-lin-btn qm-tap-44"
            style={{ marginTop: 10 }}
            data-testid="mint-copy"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(state.code);
                setCopied(true);
              } catch {
                // ⚠️ A BLOCKED CLIPBOARD IS SAID OUT LOUD, never swallowed into
                // a "Copied" that did not happen. The code is on screen, so the
                // doctor can still select it — which is why this is a warning
                // and not an error.
                toast.warning('Copy blocked — select the code above instead.');
              }
            }}
          >
            {copied ? 'Copied' : 'Copy code'}
          </button>
        </div>
      ) : null}
    </section>
  );
}
