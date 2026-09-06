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
import { ASSIGNABLE_ROLES } from '@/lib/practice-roles';
import {
  changeMemberRoleAction,
  mintSeatInviteAction,
  removeMemberAction,
  revokeSeatInviteAction,
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
              FALSE. It told the doctor that owners "cannot be demoted or removed
              here yet — ask support". ADMIN-5 ships both, so leaving the
              sentence would send a practice owner to support for something the
              page in front of them now does. The ADMIN-5 row required its
              removal in the same commit for exactly that reason; a disclosure
              that outlives its refusal is worse than none, because the doctor
              has no way to tell it is stale. */}
          <p
            data-testid="members-owner-help"
            style={{ marginTop: 12, fontSize: 13, color: 'var(--color-linear-text-3)' }}
          >
            You can make another member an owner, change a member&rsquo;s role, or remove
            them from the practice. A practice must always keep at least one owner.
          </p>
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

  // ⚠️ ONLY YOURSELF IS TEXT NOW. An OWNER used to be shown as text too, because
  // the server refused every change to one — "a control that is drawn and then
  // refused teaches the doctor the page lies" is still the rule, and it is why
  // this predicate moved the moment the server stopped refusing.
  //
  // ⚠️ THE LAST OWNER IS DELIBERATELY *NOT* EXCLUDED HERE, AND THAT IS NOT AN
  // OVERSIGHT. Whether a member is the last owner is a fact about the practice
  // at the instant of the write, not a property of the row this component was
  // rendered from — a page rendered when there were two owners is stale the
  // moment the other one is removed in another tab. Disabling the control on a
  // stale count would refuse changes that are safe and permit ones that are
  // not. The database decides, and the refusal is spoken.
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
      // ⚠️ THE CONFIRM STAYS, AND ITS REASON CHANGED. Promotion to OWNER is no
      // longer irreversible — ADMIN-5 ships the demotion — so the old wording
      // ("this cannot be undone here") is retired with the refusal it described.
      // What has not changed is that OWNER sits ONE ARROW-KEY from the current
      // selection: the options derive from ASSIGNABLE_ROLES, where OWNER is
      // first, so a CLINICIAN row opens with OWNER directly above the selected
      // item, and an adversarial pass reached it by one keystroke.
      //
      // Handing somebody administrative control of a clinic is worth a
      // deliberate second act even when it can be undone.
      //
      // ⚠️ THE CONFIRM IS ON THAT ONE VALUE ONLY. Confirming every role change
      // would train the doctor to dismiss it, which is how a confirm stops
      // being a control.
      onSubmit={(e) => {
        const chosen = new FormData(e.currentTarget).get('role');
        if (chosen !== 'OWNER') return;
        const who = member.name?.trim() || member.email;
        const ok = window.confirm(
          `Make ${who} an owner of this practice?\n\n` +
            'Owners can manage members, invite people, and remove them. ' +
            'You can change this later, as long as the practice keeps one owner.',
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
    // ⚠️ THE REFUSAL IS SPOKEN, and the LAST_OWNER one is the whole reason this
    // matters: the doctor is told the practice would be left with no owner and
    // what to do about it, rather than watching a button do nothing.
    else if (state?.ok === false) toast.error(state.message);
  }, [state]);

  // ⚠️ NO CONTROL AT ALL FOR YOURSELF. The server refuses self-removal, and
  // drawing a button that is always refused teaches the doctor the page lies —
  // the same rule the role cell follows. Rendering nothing is also what keeps
  // "remove" from being the misclick that empties a practice.
  if (!canAdminister || member.isSelf) return null;

  const who = member.name?.trim() || member.email;

  return (
    <form
      action={action}
      style={{ display: 'flex', alignItems: 'center' }}
      // ⚠️ CONFIRMED, AND UNLIKE THE ROLE CONTROL IT IS CONFIRMED ALWAYS.
      // Removal ends somebody's access to a clinical system in one click and
      // there is no undo on this page at any role — so the "confirm only the
      // irreversible value" reasoning that keeps the role confirm rare argues
      // the opposite way here. Every removal is the irreversible value.
      onSubmit={(e) => {
        const ok = window.confirm(
          `Remove ${who} from this practice?\n\n` +
            'They will lose access immediately. Their visits, patients and audit ' +
            'history stay exactly as they are.',
        );
        if (!ok) e.preventDefault();
      }}
    >
      <input type="hidden" name="userId" value={member.id} />
      <button
        type="submit"
        disabled={pending}
        data-testid={`member-remove-${member.id}`}
        className="qm-lin-btn qm-tap-44"
        style={{ fontSize: 13, padding: '6px 10px', color: 'var(--color-linear-text-2)' }}
      >
        {pending ? 'Removing…' : 'Remove'}
      </button>
      {/* ⚠️ A PLAIN <button>, NOT `SpecularButton`. That component enumerates
          its props and never spreads, so `data-testid` is silently DROPPED —
          measured on this very file, where `member-role-save-*`, `mint-submit`
          and `mint-result` never reach the DOM. Widening a shared component is
          its own change; using a plain button here means this control is
          actually reachable by the gate that claims to drive it. */}
    </form>
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
