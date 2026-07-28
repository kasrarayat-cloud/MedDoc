// ============================================================================
// Issue an invite code for the pilot.
// ----------------------------------------------------------------------------
// Signup is invite-only (2026-07-28). This is how a code comes into existence.
//
// The RAW code is printed ONCE, here, and never stored — only its SHA-256 hash
// reaches the database, the same discipline AuthToken uses for reset and
// verification tokens. If the operator loses it, issue another; there is no
// recovery, deliberately, because a database read must not be able to mint
// signups.
//
// Prefer this over the SIGNUP_INVITE_CODES env variable. A code in .env is a
// code in plaintext in a file, with no use limit, no expiry and no revocation.
// Keep the variable for bootstrap and break-glass.
//
// Usage:
//   npx tsx scripts/issue-invite-code.ts --label "Dr Rahman, vascular"
//   npx tsx scripts/issue-invite-code.ts --label "pilot cohort 1" --uses 5 --days 30
//
// On the VPS, run it in the db-migrate container — NOT the app container. The
// runtime image is a slim runner without devDependencies, so `npx tsx` there
// fails with "missing packages and no YES option". db-migrate is the builder
// target and has the toolchain, and it is already the documented home for
// one-off scripts (see .github/workflows/e2e.yml's seed step):
//
//   docker compose run --rm --entrypoint sh db-migrate -c \
//     'cd /app/apps/transcribe-md && npx --no-install tsx \
//      scripts/issue-invite-code.ts --label "Dr Rahman, vascular"'
// ============================================================================

import { randomBytes } from 'node:crypto';

import prisma from '@meddoc/db';

import { hashInviteCode, normalizeInviteCode } from '../src/lib/signup-invite';

/** Crockford-ish: no I, L, O, U — they are the characters people mis-hear and
 *  mis-type when a code is read down a phone line, which is how these travel. */
const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

function generateCode(): string {
  const bytes = randomBytes(16);
  let out = '';
  for (let i = 0; i < 16; i += 1) {
    out += ALPHABET[bytes[i] % ALPHABET.length];
    if (i === 3 || i === 7 || i === 11) out += '-';
  }
  return out;
}

function arg(name: string): string | null {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : null;
}

async function main(): Promise<void> {
  const label = arg('label');
  const uses = Number(arg('uses') ?? '1');
  const days = arg('days') ? Number(arg('days')) : null;

  if (!label) {
    console.error(
      'A --label is required. It is how you will know later who this was for;\n' +
        'an unlabelled code is one nobody can safely revoke.\n\n' +
        '  npx tsx scripts/issue-invite-code.ts --label "Dr Rahman, vascular"',
    );
    process.exit(1);
  }
  if (!Number.isInteger(uses) || uses < 1) {
    console.error('--uses must be a positive integer.');
    process.exit(1);
  }
  // NEVER PHI. The label is an operational note, and it goes in a table that is
  // not covered by the clinical retention rules.
  if (/\b\d{3}-?\d{2}-?\d{4}\b/.test(label)) {
    console.error('That label looks like it contains an SSN. Refusing.');
    process.exit(1);
  }

  const raw = generateCode();
  const expiresAt = days ? new Date(Date.now() + days * 86_400_000) : null;

  const row = await prisma.inviteCode.create({
    data: {
      codeHash: hashInviteCode(raw),
      label,
      maxUses: uses,
      expiresAt,
    },
    select: { id: true },
  });

  console.log('');
  console.log('  Invite code issued — this is the ONLY time it is shown.');
  console.log('');
  console.log(`    ${normalizeInviteCode(raw)}`);
  console.log('');
  console.log(`  label    ${label}`);
  console.log(`  uses     ${uses}`);
  console.log(`  expires  ${expiresAt ? expiresAt.toISOString() : 'never'}`);
  console.log(`  id       ${row.id}`);
  console.log('');
  console.log('  Revoke it later with:');
  console.log(
    `    UPDATE invite_codes SET "revokedAt" = now() WHERE id = '${row.id}';`,
  );
  console.log('');
}

main()
  .catch((err) => {
    console.error('[issue-invite-code] failed:', err);
    process.exit(1);
  })
  .finally(() => {
    void prisma.$disconnect();
  });
