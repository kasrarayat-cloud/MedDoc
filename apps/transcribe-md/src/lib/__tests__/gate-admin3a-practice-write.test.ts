// ============================================================================
// ADMIN-3a — THE ONLY WRITE PATH TO A `Practice` ROW.
// ----------------------------------------------------------------------------
// ⚠️ THERE WAS NONE. `practice.update|practices.update` over apps/ and packages/
// returned ZERO call sites, against a positive control of 15+ `user.update`.
// FOUR FILED ROWS AND A STANDING RULING all waited on that single absence —
// ADMIN-3 (set a specialty), ADMIN-6 (archive), ADMIN-2a (change a slug), and
// ruling #226, blocked since 2026-09-07 and naming this exact cause in its own
// words: "NO ADMIN PATH WRITES A PRACTICE ROW."
//
// ⚠️ ADMIN-6 (2026-09-10) — THE VERB NOW RUNS IN ONE READ COMMITTED TRANSACTION
// and writes its audit row INSIDE it (`tx.auditLog.create`), so this harness
// drives a `tx`, not `logAudit`. The archive's own refusals and design-A's
// "only the practice row is written" are proven in
// `gate-admin6-practice-archive.test.ts`.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => {
  // ⚠️ EVERY MOCK DECLARES ITS PARAMETERS, AND THAT IS NOT COSMETIC. `vi.fn(async
  // () => …)` types `calls` as `[][]`, so every `calls[0]![0]` below is a
  // compile error that VITEST CANNOT SEE — it strips types. The pre-push hook
  // caught exactly this, which is what it exists for.
  const tx = {
    $queryRaw: vi.fn(async (_s: TemplateStringsArray, ..._v: unknown[]): Promise<unknown[]> => []),
    practice: {
      findUnique: vi.fn(async (_a: unknown): Promise<unknown> => null),
      update: vi.fn(async (_a: { where: { id: string }; data: Record<string, unknown> }) => ({})),
    },
    user: {
      findUnique: vi.fn(async (_a: unknown): Promise<unknown> => ({ practiceId: 'prac_admin', email: 'a@x.invalid' })),
      findMany: vi.fn(async (_a: unknown): Promise<unknown[]> => []),
    },
    transcribeVisit: { findMany: vi.fn(async (_a: unknown): Promise<unknown[]> => []) },
    auditLog: {
      create: vi.fn(async (_a: {
        data: {
          action: string;
          targetType?: string;
          targetId?: string;
          metadata: { changed: Record<string, { from: unknown; to: unknown }>; reason: string | null };
        };
      }) => ({})),
    },
  };
  const transaction = vi.fn(async (fn: (t: typeof tx) => unknown, _opts?: unknown) => fn(tx));
  return { tx, prisma: { $transaction: transaction } };
});
vi.mock('@meddoc/db', () => ({ default: h.prisma, prisma: h.prisma }));

import {
  PRACTICE_WRITABLE_FIELDS,
  slugRefusal,
  updatePractice,
} from '../practice-write';

const { tx } = h;
const EXISTING = { id: 'prac_1', name: 'Northside', slug: 'northside', isActive: true };

beforeEach(() => {
  vi.clearAllMocks();
  tx.$queryRaw.mockResolvedValue([EXISTING]);
  tx.practice.findUnique.mockResolvedValue(null);
});

describe('ADMIN-3a — the allowlist FAILS CLOSED', () => {
  it('⚠️ an unknown field is REFUSED, never ignored', async () => {
    // Ignoring is how a caller silently fails to change what it asked to
    // change — and the caller that does this is a future one nobody watches.
    const r = await updatePractice({
      practiceId: 'prac_1',
      patch: { audioRetentionDays: 1 } as never,
      actorUserId: 'u1',
    });
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('unknown_field');
    expect(tx.practice.update, 'it wrote before refusing').not.toHaveBeenCalled();
  });

  it('⚠️ THE RETENTION COLUMNS ARE NOT WRITABLE — they destroy records on a schedule', async () => {
    for (const f of ['audioRetentionDays', 'transcriptRetentionDays']) {
      expect(PRACTICE_WRITABLE_FIELDS as readonly string[]).not.toContain(f);
    }
  });

  it('⚠️ NON-VACUITY — an allowlisted field DOES write', async () => {
    const r = await updatePractice({
      practiceId: 'prac_1',
      patch: { name: 'Southside' },
      actorUserId: 'u1',
    });
    expect(r.ok, 'the verb refuses everything — every arm above is vacuous').toBe(true);
    expect(tx.practice.update).toHaveBeenCalledTimes(1);
  });

  it('refuses before reading when the patch is empty', async () => {
    const r = await updatePractice({ practiceId: 'prac_1', patch: {}, actorUserId: 'u1' });
    expect(r.ok).toBe(false);
    expect(h.prisma.$transaction).not.toHaveBeenCalled();
  });
});

describe('ADMIN-3a — the slug is a HOSTNAME, and is validated as one', () => {
  it.each([
    ['uppercase', 'Northside'],
    ['underscore', 'north_side'],
    ['leading hyphen', '-north'],
    ['trailing hyphen', 'north-'],
    ['too short', 'ab'],
    ['a dot', 'north.side'],
    ['a space', 'north side'],
  ])('⚠️ refuses %s', (_n, slug) => {
    expect(slugRefusal(slug)).toBe('invalid_slug');
  });

  it.each([['admin'], ['api'], ['www'], ['app'], ['status']])(
    '⚠️ refuses the reserved name %s — ADMIN-2 keys hostnames on this column',
    (slug) => {
      expect(slugRefusal(slug)).toBe('reserved_slug');
    },
  );

  it('⚠️ NON-VACUITY — an ordinary slug passes', () => {
    expect(slugRefusal('northside')).toBeNull();
    expect(slugRefusal('north-side-clinic')).toBeNull();
    // and the machine-generated shape ADMIN-2a exists to retire is itself valid
    expect(slugRefusal('solo-a1b2c3d4-m1n2o3')).toBeNull();
  });

  it('a taken slug is refused by NAME, not by a constraint violation', async () => {
    tx.practice.findUnique.mockResolvedValueOnce({ id: 'prac_other' });
    const r = await updatePractice({
      practiceId: 'prac_1',
      patch: { slug: 'southside' },
      actorUserId: 'u1',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('slug_taken');
    expect(tx.practice.update).not.toHaveBeenCalled();
  });
});

describe('ADMIN-3a — the audit row is the point', () => {
  it('⚠️ carries `from` AND `to` — the previous value is what a recovery needs', async () => {
    await updatePractice({
      practiceId: 'prac_1',
      patch: { name: 'Southside' },
      actorUserId: 'u1',
      reason: 'rebrand',
    });
    const row = tx.auditLog.create.mock.calls[0]![0].data;
    expect(row.action).toBe('PRACTICE_UPDATED');
    expect(row.metadata.changed).toEqual({ name: { from: 'Northside', to: 'Southside' } });
    expect(row.metadata.reason).toBe('rebrand');
    // ⚠️ ADMIN-6 — the row now NAMES its target; it had neither column before.
    expect(row.targetType).toBe('Practice');
    expect(row.targetId).toBe('prac_1');
  });

  it('⚠️ AN ARCHIVE GETS ITS OWN ACTION — #226 named `PRACTICE_ARCHIVED` as missing', async () => {
    await updatePractice({
      practiceId: 'prac_1',
      patch: { isActive: false },
      actorUserId: 'u1',
    });
    expect(tx.auditLog.create.mock.calls[0]![0].data.action).toBe('PRACTICE_ARCHIVED');
  });

  it('⚠️ and a restore is distinguishable from an archive', async () => {
    tx.$queryRaw.mockResolvedValue([{ ...EXISTING, isActive: false }]);
    await updatePractice({
      practiceId: 'prac_1',
      patch: { isActive: true },
      actorUserId: 'u1',
    });
    expect(tx.auditLog.create.mock.calls[0]![0].data.action).toBe('PRACTICE_RESTORED');
  });

  it('⚠️ a no-op patch writes NOTHING and audits NOTHING', async () => {
    // An audit row saying "somebody changed the name to what it already was"
    // is noise in the one log an incident reads.
    const r = await updatePractice({
      practiceId: 'prac_1',
      patch: { name: 'Northside' },
      actorUserId: 'u1',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('no_change');
    expect(tx.practice.update).not.toHaveBeenCalled();
    expect(tx.auditLog.create).not.toHaveBeenCalled();
  });

  it('a missing practice is `not_found`, and nothing is written', async () => {
    tx.$queryRaw.mockResolvedValue([]);
    const r = await updatePractice({
      practiceId: 'nope',
      patch: { name: 'X' },
      actorUserId: 'u1',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('not_found');
    expect(tx.practice.update).not.toHaveBeenCalled();
  });
});

/** Files under `dir` (relative to the app) with a `.practice.<write>(` call. */
async function practiceWriters(dir: string): Promise<{ files: string[]; hits: string[] }> {
  const { execFileSync } = await import('node:child_process');
  const { join } = await import('node:path');
  const APP = join(__dirname, '..', '..', '..');
  const out = execFileSync('grep', ['-rn', '-F', '.practice.', '--include=*.ts', '--include=*.tsx', dir], {
    cwd: APP,
    encoding: 'utf8',
  });
  const WRITES = ['update(', 'updateMany(', 'upsert(', 'delete(', 'deleteMany(', 'create('];
  const hits = out
    .split('\n')
    .filter(Boolean)
    .filter((l) => !l.includes('__tests__') && !l.includes('.test.'))
    .filter((l) => {
      const i = l.indexOf('.practice.');
      const after = l.slice(i + '.practice.'.length);
      return WRITES.some((w) => after.startsWith(w));
    });
  return { files: [...new Set(hits.map((l) => l.split(':')[0]!))].sort(), hits };
}

describe('ADMIN-3a — the practice-write population is PINNED', () => {
  it('⚠️ exactly three files write a `Practice` row, and each is named', async () => {
    // The reason this file exists is that FOUR rows each needed an update verb
    // and would each have grown their own. A third *update* site is the defect.
    //
    // ⚠️ AND THE RECON'S "`practice.update` = 0" WAS TRUE AND INCOMPLETE, IN A
    // WAY THAT SHARPENS THE POINT RATHER THAN SOFTENING IT. Measured here:
    // there were already TWO practice writers — `auth.ts` CREATES one at
    // signup, and `delete-account/route.ts` HARD DELETES one when the last
    // account goes.
    //
    // So the product could MAKE a practice and DESTROY a practice, and could
    // not CHANGE one. It had the irreversible half of the lifecycle and not the
    // reversible half — which is the shape #306 ruled against one arc over, and
    // exactly why ADMIN-6's archive has to exist before anything relies on
    // deletion.
    const { files, hits } = await practiceWriters('src');

    // POSITIVE CONTROL: the matcher fires at all.
    expect(hits.length, 'the grep found nothing — this arm measures nothing').toBeGreaterThan(0);

    expect(files, `practice-writing files moved:\n${hits.join('\n')}`).toEqual([
      'src/actions/auth.ts', // pre-existing CREATE — signup mints a solo practice
      'src/app/api/settings/delete-account/route.ts', // pre-existing HARD DELETE
      'src/lib/practice-write.ts', // ADMIN-3a — the only UPDATE verb
    ]);
  });

  it('⚠️ and the pre-existing one is a DELETE, not an update — the verb is still alone', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(
      join(__dirname, '..', '..', 'app', 'api', 'settings', 'delete-account', 'route.ts'),
      'utf8',
    );
    expect(src).toContain('tx.practice.delete');
    expect(src, 'the delete path grew an update — that is a second verb').not.toMatch(
      /\.practice\.(update|upsert)/,
    );
  });

  // ⚠️ ADMIN-6 — WIDENED TO `scripts/`, BECAUSE THE FLAG BECAME A SWITCH.
  //
  // The arm above greps `src` only. `scripts/prod-smoke/provision.ts` upserted
  // `isActive: true` on every run — invisible to it, and harmless while nothing
  // read the flag. Once three doors read it, that line is a SILENT UN-ARCHIVE:
  // a restore with no audit row. So scripts are pinned too, and the invariant
  // pinned is the one that matters: NO SCRIPT CHANGES AN EXISTING PRACTICE'S
  // FLAG. Creating a fresh practice (QA seeds, on a non-prod database) is not a
  // flip of anybody's archive.
  const SCRIPT_WRITERS: Record<string, string> = {
    'scripts/prod-smoke/provision.ts': 'smoke fixture upsert — name only on update; refuses on an archived practice',
    'scripts/proofs/admin6-archive-restore-proof.ts': 'ADMIN-6 real-Postgres proof (assertNonProdDatabase) — creates its own fixtures only',
    'scripts/qa/b8-admission-on-qa.ts': 'QA create (assertNonProdDatabase)',
    'scripts/qa/b8-failure-cost-on-qa.ts': 'QA create (assertNonProdDatabase)',
    'scripts/qa/b8-permanent-discard-on-qa.ts': 'QA create (assertNonProdDatabase)',
    'scripts/seed-qa-user.ts': 'QA seed upsert (assertNonProdDatabase) — update branch is {}',
    'scripts/seed-t1-multiseat.ts': 'T1 fixture upsert (assertNonProdDatabase) — update branch is {}',
  };

  it('⚠️ every SCRIPT that writes a practice is classified — a new one reds by name', async () => {
    const { files, hits } = await practiceWriters('scripts');
    expect(hits.length, 'the scripts grep found nothing — the arm below is vacuous').toBeGreaterThan(0);
    expect(files, `script practice-writers moved:\n${hits.join('\n')}`).toEqual(
      Object.keys(SCRIPT_WRITERS).sort(),
    );
  });

  it('⚠️ NO SCRIPT CHANGES AN EXISTING PRACTICE\'S `isActive` — only the audited verb may', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const APP = join(__dirname, '..', '..', '..');
    const offenders: string[] = [];
    let upsertsSeen = 0;
    for (const f of Object.keys(SCRIPT_WRITERS)) {
      const src = readFileSync(join(APP, f), 'utf8');
      // A bare update verb in a script is a second update path, full stop.
      if (/\.practice\s*\.\s*(?:update|updateMany)\s*\(/.test(src)) offenders.push(`${f}: practice.update`);
      // An upsert's UPDATE branch is a write to an EXISTING row: it must not
      // name the flag. Brace-matched, so a nested object cannot hide it.
      for (let i = src.search(/\.practice\s*\.\s*upsert\s*\(/); i > -1; ) {
        upsertsSeen += 1;
        const u = src.indexOf('update:', i);
        const open = src.indexOf('{', u);
        let depth = 0;
        let end = open;
        for (; end < src.length; end += 1) {
          if (src[end] === '{') depth += 1;
          else if (src[end] === '}' && (depth -= 1) === 0) break;
        }
        if (/\bisActive\b/.test(src.slice(open, end + 1))) offenders.push(`${f}: upsert update-branch writes isActive`);
        const next = src.slice(end).search(/\.practice\s*\.\s*upsert\s*\(/);
        i = next < 0 ? -1 : end + next;
      }
    }
    expect(upsertsSeen, 'no upsert was parsed — the arm measures nothing').toBeGreaterThanOrEqual(3);
    expect(offenders).toEqual([]);
  });
});
