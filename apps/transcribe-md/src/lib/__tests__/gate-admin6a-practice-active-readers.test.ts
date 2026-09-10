// ============================================================================
// ADMIN-6a — THE READERS OF THE PRACTICE FLAG ARE PINNED, BOTH WAYS.
// ----------------------------------------------------------------------------
// `practices.isActive` had ZERO readers until this change (measured at
// 6fcd21d0, raw SQL included), which is why an archive turned nothing off.
// ADMIN-6a gives it exactly three:
//
//   D1  apps/transcribe-md/src/lib/nextauth.ts   login          (authorize)
//   D2  packages/auth/src/user-session.ts         every request  (validateSession)
//   D3  apps/transcribe-md/src/actions/auth.ts    invite redemption (pre-check + in-tx)
//
// ⚠️ BOTH DIRECTIONS, BECAUSE EACH FAILURE IS SILENT IN THE OTHER:
//
//   · a FOURTH reader appears  → a second statement of the rule, which drifts
//                                from the first the day either is edited (the
//                                "one rule, many readers" class). Unclassified
//                                files RED, by name.
//   · a door DISAPPEARS        → the archive stops disabling that surface and
//                                nothing else notices: every other test still
//                                passes, because the doors are the only thing
//                                that reads the flag. Stale entries RED.
//
// ⚠️ THE UNIVERSE IS READ FROM THE FILESYSTEM (`git ls-files`), NEVER LISTED —
// ruling #289. And the scanner matches the CAST FORM — ruling #231: six admin
// doors were once written `(prisma.user as any).update` and were invisible to
// the obvious grep, and a cast is exactly how a read is written when the
// property is not on the declared type, which is precisely when a NEW reader
// arrives.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '..', '..', '..', '..', '..');

/** The scanned universe: shipped app source, app scripts, and every package. */
function universe(): string[] {
  // ⚠️ `--others --exclude-standard` TOO. The first run of this pin reported the
  // PREDICATE FILE ITSELF as stale — it was new and not yet committed, so plain
  // `ls-files` could not see it. The same blindness would let a brand-new
  // reader pass locally until the moment it is committed.
  return execFileSync(
    'git',
    [
      'ls-files', '--cached', '--others', '--exclude-standard',
      'apps/transcribe-md/src', 'apps/transcribe-md/scripts', 'packages',
    ],
    { cwd: REPO, encoding: 'utf8' },
  )
    .split('\n')
    .filter(
      (f) =>
        /\.(ts|tsx)$/.test(f) &&
        !f.includes('__tests__') &&
        !/\.(test|spec)\.tsx?$/.test(f) &&
        // packages/* other than their src/ (prisma proofs, generated) are not code
        (!f.startsWith('packages/') || /^packages\/[^/]+\/src\//.test(f)),
    );
}

const stripComments = (s: string) =>
  s
    .split('\n')
    .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
    .join('\n');

/**
 * Property reads of `isActive` on a receiver matching `receiver`, INCLUDING the
 * cast form. Parameterised so the SAME machinery is pointed at user-side
 * receivers as the positive control — a control that used a different regex
 * would prove that regex works, not this one.
 */
function flagReads(src: string, receiver: string): string[] {
  const direct = new RegExp(`\\b[\\w$]*${receiver}[\\w$]*\\s*\\??\\.\\s*isActive\\b`, 'gi');
  // `(x.practice as any).isActive`, `(practice as { isActive?: boolean })?.isActive`
  const cast = new RegExp(
    `\\(\\s*[\\w$.?]*${receiver}[\\w$]*\\s+as\\s+[^)]*\\)\\s*\\??\\.\\s*isActive\\b`,
    'gi',
  );
  return [...src.matchAll(direct), ...src.matchAll(cast)].map((m) => m[0]);
}

/**
 * The argument text of every call on the Practice MODEL, paren-matched —
 * including the cast form `(tx.practice as any).count(…)`.
 */
function practiceModelCallArgs(src: string): string[] {
  const out: string[] = [];
  const re =
    /\.\s*practice\s*(?:as\s+\w+\s*\)\s*)?\.\s*(?:findUnique|findUniqueOrThrow|findFirst|findFirstOrThrow|findMany|count|update|updateMany|upsert|create|createMany)\s*\(/g;
  for (const m of src.matchAll(re)) {
    const start = m.index! + m[0].length;
    let depth = 1;
    let i = start;
    for (; i < src.length && depth > 0; i += 1) {
      if (src[i] === '(') depth += 1;
      else if (src[i] === ')') depth -= 1;
    }
    out.push(src.slice(start, i - 1));
  }
  return out;
}

/**
 * Prisma argument keys that stay ON the practice. A key outside this set opens
 * a RELATION (`users: { some: … }`), and an `isActive` under it belongs to the
 * related model, not to the practice.
 */
const PRACTICE_SCOPE_KEYS = new Set(['where', 'select', 'data', 'include', 'create', 'update', 'AND', 'OR', 'NOT']);

/**
 * Does `isActive` appear in this model-call argument as a key reachable only
 * through practice-scope keys?
 *
 * ⚠️ WHY KEY PATHS AND NOT A CHARACTER WINDOW. The first version matched any
 * `isActive` within 400 characters of `.practice.<verb>(`, and flagged three
 * files that never touch the practice flag: `backfill-promo-grants.ts`
 * (`practice.findMany({ where: { users: { some: { isActive } } } })` — the
 * USERS' flag, through a relation filter) and two QA scripts whose next
 * statement created a user. A false positive costs a wrong classification that
 * then sits on the list looking load-bearing — the #231 stale-entry shape.
 */
function namesPracticeFlag(arg: string): boolean {
  const stack: (string | null)[] = [];
  const re = /([A-Za-z_$][\w$]*)\s*:\s*([{[])?|([{[])|([}\]])/g;
  for (const m of arg.matchAll(re)) {
    if (m[1] !== undefined) {
      if (m[1] === 'isActive' && stack.every((k) => k === null || PRACTICE_SCOPE_KEYS.has(k))) return true;
      if (m[2] !== undefined) stack.push(m[1]);
    } else if (m[3] !== undefined) {
      stack.push(null); // an array or an unkeyed object — transparent
    } else {
      stack.pop();
    }
  }
  return false;
}

/** Every way a file can mention the PRACTICE's flag in code. */
function practiceFlagMentions(raw: string): string[] {
  const src = stripComments(raw);
  const hits: string[] = [];
  hits.push(...flagReads(src, 'practice'));
  // A relation select/where/include on the practice: `practice: { … isActive`
  for (const m of src.matchAll(/\bpractices?\s*:\s*\{[^}]*\bisActive\b/g)) hits.push(m[0]);
  // A query on the Practice MODEL that names the flag ON THE PRACTICE.
  for (const arg of practiceModelCallArgs(src)) {
    if (namesPracticeFlag(arg)) hits.push('model:' + arg.slice(0, 60));
  }
  // The one predicate's own spellings — how a DOOR is written.
  for (const m of src.matchAll(/\b(?:practiceAdmits\s*\(|PRACTICE_ADMITS(?:_SELECT)?\b)/g)) {
    hits.push(m[0]);
  }
  // Raw SQL naming both the table and the column, in either order.
  for (const m of src.matchAll(/\$(?:query|execute)Raw(?:Unsafe)?\s*(?:<[^>]*>)?\s*(`[^`]*`|\(\s*`[^`]*`)/g)) {
    const body = m[1]!;
    if (/\bpractices\b/.test(body) && /"isActive"/.test(body)) hits.push('raw:' + body.slice(0, 60));
  }
  return hits;
}

/**
 * ⚠️ EVERY FILE THAT MENTIONS THE PRACTICE FLAG, WITH ITS ROLE. A file not here
 * REDS; an entry that no longer mentions the flag REDS. `door` entries carry the
 * exact number of `practiceAdmits(` calls, so a door losing a check reds too.
 */
const CLASSIFIED: Record<string, { role: 'door' | 'predicate' | 'writer' | 'other'; why: string; admitsCalls?: number }> = {
  'apps/transcribe-md/src/lib/nextauth.ts': {
    role: 'door',
    why: 'D1 — login refuses a member of an archived practice (LOGIN_FAILED / ACCOUNT_PRACTICE_ARCHIVED)',
    admitsCalls: 1,
  },
  'packages/auth/src/user-session.ts': {
    role: 'door',
    why: 'D2 — validateSession returns null, ending every session of an archived practice',
    admitsCalls: 1,
  },
  'apps/transcribe-md/src/actions/auth.ts': {
    role: 'door',
    why: 'D3 — invite redemption: a pre-check before the email lookup (no enumeration oracle) and the authoritative in-transaction read',
    admitsCalls: 2,
  },
  'packages/db/src/practice-admits.ts': {
    role: 'predicate',
    why: 'the ONE statement of the rule — PRACTICE_ADMITS / practiceAdmits',
  },
  'apps/transcribe-md/src/lib/practice-write.ts': {
    role: 'writer',
    why: 'the one audited verb; reads the flag under FOR UPDATE to compute from/to, never to admit anyone',
  },
  'apps/transcribe-md/scripts/prod-smoke/provision.ts': {
    role: 'other',
    why: 'smoke fixture REFUSES to run on an archived smoke practice rather than silently un-archiving it',
  },
  'apps/transcribe-md/scripts/seed-qa-user.ts': {
    role: 'other',
    why: 'QA seed (assertNonProdDatabase) — CREATE branch only sets isActive:true on a new practice; its update branch is {}',
  },
  'apps/transcribe-md/scripts/proofs/admin6-archive-restore-proof.ts': {
    role: 'other',
    why: 'the real-Postgres proof (assertNonProdDatabase) READS the flag to verify the act; it never admits anyone',
  },
};

describe('ADMIN-6a — the scanner itself (so a green below means something)', () => {
  it('POSITIVE CONTROL — the same machinery finds the USER-side isActive reads', () => {
    // Pointed at user receivers, the identical function must find the reads we
    // KNOW exist. If it finds nothing, every "no unclassified reader" below is
    // vacuous — the scanner, not the tree, would be what is empty.
    const nextauth = stripComments(readFileSync(join(REPO, 'apps/transcribe-md/src/lib/nextauth.ts'), 'utf8'));
    const session = stripComments(readFileSync(join(REPO, 'packages/auth/src/user-session.ts'), 'utf8'));
    expect(flagReads(nextauth, 'user').length, 'user.isActive in authorize()').toBeGreaterThan(0);
    expect(flagReads(session, 'user').length, 'user.isActive in validateSession()').toBeGreaterThan(0);
  });

  it.each([
    ['cast through any', 'const a = (row as any).practice.isActive;'],
    ['cast to a shape', 'const b = (practice as { isActive?: boolean }).isActive;'],
    ['cast then optional chain', 'const c = (user.practice as any)?.isActive;'],
    ['optional chain', 'if (user?.practice?.isActive) go();'],
    ['relation select', 'include: { practice: { select: { isActive: true } } }'],
    ['model query', 'await prisma.practice.findMany({ where: { isActive: false } })'],
    ['model query under OR', 'await prisma.practice.findMany({ where: { OR: [{ isActive: false }, { slug: s }] } })'],
    ['model create', 'await prisma.practice.create({ data: { name, slug, isActive: true } })'],
    ['a USER query filtering on the practice', 'await prisma.user.findMany({ where: { practice: { isActive: true } } })'],
    ['cast model query', 'await (tx.practice as any).count({ where: { isActive: true } })'],
    ['raw SQL', 'await tx.$queryRaw`SELECT 1 FROM practices WHERE "isActive" = true`'],
    ['the predicate', 'if (!practiceAdmits(p)) return null;'],
  ])('⚠️ detects the %s form — ruling #231', (_n, snippet) => {
    expect(practiceFlagMentions(snippet), snippet).not.toEqual([]);
  });

  it.each([
    ['a user read', 'if (!user.isActive) return null;'],
    ['a cast user read', 'if ((user as any).isActive === false) return null;'],
    ['a patient read', 'where: { patient: { isActive: true } }'],
    // ⚠️ the two false-positive shapes the first scanner flagged in the real tree
    ['the USERS\' flag through a relation filter', 'await prisma.practice.findMany({ where: { users: { some: { isActive: true } } } })'],
    ['a nested user create', 'await prisma.practice.create({ data: { name, users: { create: [{ isActive: true }] } } })'],
    ['a practice create followed by a user write', 'await prisma.practice.create({ data: { name } }); await prisma.user.create({ data: { isActive: true } });'],
  ])('and does NOT count %s as a practice read', (_n, snippet) => {
    expect(practiceFlagMentions(snippet), snippet).toEqual([]);
  });
});

describe('ADMIN-6a — the practice-flag population is PINNED', () => {
  const found = new Map<string, string[]>();
  for (const f of universe()) {
    const hits = practiceFlagMentions(readFileSync(join(REPO, f), 'utf8'));
    if (hits.length > 0) found.set(f, hits);
  }

  it('NON-VACUITY — the universe is real and the doors are in it', () => {
    expect(universe().length, 'git ls-files returned nothing — every arm below is vacuous').toBeGreaterThan(100);
    expect(found.size).toBeGreaterThan(0);
  });

  it('⚠️ NO UNCLASSIFIED FILE mentions the practice flag — a fourth reader reds by name', () => {
    const unclassified = [...found.keys()].filter((f) => !(f in CLASSIFIED));
    expect(
      unclassified.map((f) => `${f}: ${found.get(f)!.join(' | ')}`),
      'a new reader of practices.isActive — route it through @meddoc/db/practice-admits and classify it here, or remove it',
    ).toEqual([]);
  });

  it('⚠️ NO STALE ENTRY — every classified file still mentions the flag (a deleted door reds)', () => {
    const stale = Object.keys(CLASSIFIED).filter((f) => !found.has(f));
    expect(stale, 'a classified file no longer reads the flag — if it was a DOOR, that surface is no longer disabled by an archive').toEqual([]);
  });

  it('⚠️ THE DOORS ARE EXACTLY D1–D3, and each calls the ONE predicate the pinned number of times', () => {
    const doors = Object.entries(CLASSIFIED).filter(([, c]) => c.role === 'door');
    expect(doors.map(([f]) => f).sort()).toEqual([
      'apps/transcribe-md/src/actions/auth.ts',
      'apps/transcribe-md/src/lib/nextauth.ts',
      'packages/auth/src/user-session.ts',
    ]);
    for (const [f, c] of doors) {
      const src = stripComments(readFileSync(join(REPO, f), 'utf8'));
      const calls = [...src.matchAll(/\bpracticeAdmits\s*\(/g)].length;
      expect(calls, `${f} — ${c.why}`).toBe(c.admitsCalls);
      expect(src, `${f} must import the predicate from its one home`).toContain(
        "from '@meddoc/db/practice-admits'",
      );
    }
  });

  it('⚠️ NO DOOR RESTATES THE RULE BY HAND — the flag is never compared outside the predicate', () => {
    // A door writing `practice.isActive === true` next to the import is the
    // second reader this pin exists to prevent, wearing the first one's name.
    for (const [f, c] of Object.entries(CLASSIFIED)) {
      if (c.role !== 'door') continue;
      const src = stripComments(readFileSync(join(REPO, f), 'utf8'));
      expect(flagReads(src, 'practice'), `${f} compares the practice flag by hand`).toEqual([]);
    }
  });

  it('⚠️ THE WORKER IS NOT A DOOR — D4 is deliberately absent (clinical generation path)', () => {
    // Recorded as a pin rather than a comment: a worker door is a change to the
    // clinical generation path and needs its own adversarial pass. The archive
    // act refuses while a visit is in flight instead (practice-write.ts).
    const workerFiles = [...found.keys()].filter(
      (f) => f.includes('/worker') || f.startsWith('packages/ai/'),
    );
    expect(workerFiles).toEqual([]);
  });
});
