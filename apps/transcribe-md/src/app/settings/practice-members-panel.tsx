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
          {/* ⚠️ THE HALF THAT IS NOT BUILT IS SAID OUT LOUD, NOT HIDDEN. An owner
              can now be created — that is the ruling. Taking it away is filed as
              its own item because it needs a last-owner guard that is correct
              under concurrency. A page that silently omits the control teaches
              the doctor the capability is missing by accident; saying so tells
              them it is deliberate and that support can act today. */}
          <p
            data-testid="members-owner-note"
            style={{ marginTop: 12, fontSize: 13, color: 'var(--color-linear-text-3)' }}
          >
            You can make another member an owner. Owners cannot be demoted or removed here
            yet — ask support if a partner is leaving the practice.
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

  // An OWNER, and yourself, are shown as text — the server refuses both, and a
  // control that is drawn and then refused teaches the doctor the page lies.
  const editable = canAdminister && !member.isSelf && member.practiceRole !== 'OWNER';

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
      // ⚠️ PROMOTION TO OWNER IS IRREVERSIBLE UNTIL ADMIN-5 SHIPS, AND IT SITS
      // ONE ARROW-KEY FROM THE CURRENT SELECTION. The options derive from
      // ASSIGNABLE_ROLES, where OWNER is first, so a CLINICIAN row opens with
      // OWNER directly above the selected item. There is no undo: the server
      // refuses every subsequent change to an owner, by design. An adversarial
      // pass reached it by one keystroke with nothing in the way.
      //
      // ⚠️ THE CONFIRM IS ON THE IRREVERSIBLE VALUE ONLY. Confirming every role
      // change would train the doctor to dismiss it, which is how a confirm
      // stops being a control.
      onSubmit={(e) => {
        const chosen = new FormData(e.currentTarget).get('role');
        if (chosen !== 'OWNER') return;
        const who = member.name?.trim() || member.email;
        const ok = window.confirm(
          `Make ${who} an owner of this practice?\n\n` +
            'Owners can manage members and invite people. This cannot be undone here — ' +
            'owners cannot be demoted or removed yet.',
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
