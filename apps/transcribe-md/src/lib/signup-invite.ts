// ============================================================================
// Invite-only signup — the gate, and only the gate.
// ----------------------------------------------------------------------------
// Registration was open, rate-limited at 5/hour/IP and nothing else. The data
// said what that buys: 195 accounts, 172 of which had never logged in and only
// 43 with a verified email, accruing at a steady 1–3/day — a cadence that sits
// comfortably under the limit. A rate limit does not stop a patient bot.
//
// TWO SOURCES OF TRUTH, deliberately:
//
//   env  — SIGNUP_INVITE_CODES, comma-separated. Bootstrap and break-glass.
//          Survives an empty database and needs no admin UI to exist.
//   db   — invite_codes rows, hashed, with use limits and expiry. The real
//          mechanism once the pilot has more than a handful of doctors.
//
// A code matching EITHER is accepted. The env list is checked first because it
// is free (no query) and because a database outage must not lock the operator
// out of onboarding.
//
// WHERE THIS RUNS IN THE SIGNUP FLOW MATTERS. The gate is checked BEFORE the
// email lookup, not after. Signup deliberately returns identical responses for
// an existing and a new email (Round 3 PR-F, anti-enumeration); putting the
// invite check first means an attacker without a code never reaches the lookup
// at all, and so learns nothing about which emails exist. The gate makes
// enumeration strictly harder, not easier.
// ============================================================================

import { createHash, timingSafeEqual } from 'node:crypto';

import prisma from '@meddoc/db';

/** SHA-256 hex. Codes are stored hashed so a database read cannot mint signups
 *  — the same discipline AuthToken uses for reset and verification tokens. */
export function hashInviteCode(raw: string): string {
  return createHash('sha256').update(normalizeInviteCode(raw)).digest('hex');
}

/** Codes are handed over verbally and pasted from emails, so casing and
 *  surrounding whitespace are noise. Interior characters are left alone. */
export function normalizeInviteCode(raw: string): string {
  return raw.trim().toUpperCase();
}

/** Constant-time compare over the hashes, so a wrong code cannot be narrowed
 *  down by timing. Cheap, and the alternative is a subtle oracle. */
function hashesMatch(a: string, b: string): boolean {
  const ab = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

/** The env allowlist, normalized. Empty when unset — which means env alone
 *  admits nobody, and the DB is the only door. */
export function envInviteCodeHashes(): string[] {
  return (process.env.SIGNUP_INVITE_CODES ?? '')
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean)
    .map((c) => hashInviteCode(c));
}

/**
 * The membership an invite admits into. **NULL means the LEGACY contract**: mint
 * a fresh solo practice and make the redeemer its OWNER, exactly as every signup
 * did before T8.
 *
 * ⚠️ The two fields travel TOGETHER because the database refuses them apart
 * (`invite_codes_practice_and_role_together`). A practice without a role would
 * let the redeemer fall to the application's default for a new signup — OWNER —
 * handing an owner's rights over somebody else's clinic to anyone holding the
 * code.
 */
export type InviteMembership = {
  practiceId: string;
  practiceRole: 'OWNER' | 'CLINICIAN' | 'TECH';
};

export type InviteCheck =
  | { ok: true; source: 'env'; membership?: undefined }
  | { ok: true; source: 'db'; inviteCodeId: string; membership: InviteMembership | null }
  | { ok: false; reason: 'missing' | 'invalid' | 'expired' | 'revoked' | 'exhausted' };

/**
 * Is this code good for one signup right now?
 *
 * READ-ONLY — it does not consume the use. Consumption happens inside the
 * signup transaction (see `consumeDbInviteCode`) so two concurrent signups
 * cannot both spend the last use of a code.
 */
export async function checkInviteCode(rawCode: string): Promise<InviteCheck> {
  const code = normalizeInviteCode(rawCode ?? '');
  if (!code) return { ok: false, reason: 'missing' };

  const hash = hashInviteCode(code);

  for (const envHash of envInviteCodeHashes()) {
    if (hashesMatch(hash, envHash)) return { ok: true, source: 'env' };
  }

  const row = await prisma.inviteCode.findUnique({
    where: { codeHash: hash },
    select: {
      id: true,
      maxUses: true,
      usedCount: true,
      expiresAt: true,
      revokedAt: true,
      // T8 — the membership this code admits into. Both or neither, enforced by
      // `invite_codes_practice_and_role_together`.
      practiceId: true,
      practiceRole: true,
    },
  });
  if (!row) return { ok: false, reason: 'invalid' };
  if (row.revokedAt) return { ok: false, reason: 'revoked' };
  if (row.expiresAt && row.expiresAt.getTime() <= Date.now()) {
    return { ok: false, reason: 'expired' };
  }
  if (row.usedCount >= row.maxUses) return { ok: false, reason: 'exhausted' };

  return {
    ok: true,
    source: 'db',
    inviteCodeId: row.id,
    // ⚠️ NULL HERE IS THE LEGACY CONTRACT, NOT AN ABSENCE TO PATCH.
    // A code with no practice mints a fresh solo practice, exactly as every
    // signup did before T8. The migration header states it; this is where the
    // caller reads it.
    membership:
      row.practiceId && row.practiceRole
        ? { practiceId: row.practiceId, practiceRole: row.practiceRole }
        : null,
  };
}

/**
 * Spend one use, atomically. Call INSIDE the signup transaction.
 *
 * The `usedCount < maxUses` predicate lives in the WHERE clause rather than in
 * a read-then-write, so the database decides the race. `updateMany` returning
 * `count: 0` means somebody else took the last use between the check above and
 * this write — the caller must treat that as a refusal, not as success.
 */
export async function consumeDbInviteCode(
  tx: { inviteCode: { updateMany: (args: never) => Promise<{ count: number }> } },
  inviteCodeId: string,
): Promise<boolean> {
  const res = await tx.inviteCode.updateMany({
    where: {
      id: inviteCodeId,
      revokedAt: null,
      // Column-to-column comparison via Prisma's field-reference API. The
      // reference is taken from the CLIENT, not from `tx` — a transaction
      // client does not expose `.fields`.
      usedCount: { lt: prisma.inviteCode.fields.maxUses },
    },
    data: { usedCount: { increment: 1 } },
  } as never);
  return res.count === 1;
}

/** The message a would-be signup sees. Deliberately identical for every failure
 *  reason: "expired" vs "exhausted" vs "invalid" tells a prober which codes are
 *  real, and the honest answer to all of them is the same anyway. */
export const INVITE_REJECTED_MESSAGE =
  'QuillMD is invite-only during the pilot. Check the code, or join the waitlist.';
