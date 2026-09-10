// ============================================================================
// ADMIN-3a — THE ONLY WRITE PATH TO A `Practice` ROW.
// ----------------------------------------------------------------------------
// ⚠️ THERE WAS NONE. `practice.update|practices.update` over apps/ and packages/
// returned ZERO call sites, against a positive control of 15+ `user.update`.
// FOUR FILED ROWS AND A STANDING RULING all waited on that single absence —
// ADMIN-3 (set a specialty), ADMIN-6 (archive), ADMIN-2a (change a slug), and
// ruling #226, blocked since 2026-09-07 and naming this exact cause in its own
// words: "NO ADMIN PATH WRITES A PRACTICE ROW."
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { prisma, logAudit } = vi.hoisted(() => {
  const practice = { findUnique: vi.fn(), update: vi.fn() };
  // ⚠️ THE MOCK DECLARES ITS PARAMETER, AND THAT IS NOT COSMETIC. `vi.fn(async
  // () => …)` types `calls` as `[][]`, so every `calls[0]![0]` below is a
  // compile error that VITEST CANNOT SEE — it strips types. The pre-push hook
  // caught exactly this, which is what it exists for.
  return {
    prisma: { practice },
    logAudit: vi.fn(async (_row: { action: string; metadata: unknown }) => undefined),
  };
});
vi.mock('@meddoc/db', () => ({ default: prisma, prisma }));
vi.mock('../audit', () => ({ logAudit }));

import {
  PRACTICE_WRITABLE_FIELDS,
  practiceLabelRefusal as slugRefusal,
  updatePractice,
} from '../practice-write';

const EXISTING = { id: 'prac_1', name: 'Northside', slug: 'northside', isActive: true };

beforeEach(() => {
  prisma.practice.findUnique.mockReset();
  prisma.practice.update.mockReset();
  logAudit.mockClear();
  prisma.practice.findUnique.mockResolvedValue(EXISTING);
  prisma.practice.update.mockResolvedValue(EXISTING);
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
    expect(prisma.practice.update, 'it wrote before refusing').not.toHaveBeenCalled();
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
    expect(prisma.practice.update).toHaveBeenCalledTimes(1);
  });

  it('refuses before reading when the patch is empty', async () => {
    const r = await updatePractice({ practiceId: 'prac_1', patch: {}, actorUserId: 'u1' });
    expect(r.ok).toBe(false);
    expect(prisma.practice.findUnique).not.toHaveBeenCalled();
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
    // ⚠️ ADMIN-2a REVERSED THIS LINE ON PURPOSE. It used to assert the machine
    // shape was valid; the `solo-` namespace is now RESERVED, so a human cannot
    // claim a name that looks machine-made. Pinned in gate-admin2a-slug-claim.
    expect(slugRefusal('solo-a1b2c3d4-m1n2o3')).toBe('reserved_slug');
  });

  it('a taken slug is refused by NAME, not by a constraint violation', async () => {
    prisma.practice.findUnique
      .mockResolvedValueOnce(EXISTING)
      .mockResolvedValueOnce({ id: 'prac_other' });
    const r = await updatePractice({
      practiceId: 'prac_1',
      patch: { slug: 'southside' },
      actorUserId: 'u1',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('slug_taken');
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
    const row = logAudit.mock.calls[0]![0] as unknown as {
      action: string;
      metadata: { changed: Record<string, { from: unknown; to: unknown }>; reason: string | null };
    };
    expect(row.action).toBe('PRACTICE_UPDATED');
    expect(row.metadata.changed).toEqual({ name: { from: 'Northside', to: 'Southside' } });
    expect(row.metadata.reason).toBe('rebrand');
  });

  it('⚠️ AN ARCHIVE GETS ITS OWN ACTION — #226 named `PRACTICE_ARCHIVED` as missing', async () => {
    await updatePractice({
      practiceId: 'prac_1',
      patch: { isActive: false },
      actorUserId: 'u1',
    });
    expect((logAudit.mock.calls[0]![0] as unknown as { action: string }).action).toBe('PRACTICE_ARCHIVED');
  });

  it('⚠️ and a restore is distinguishable from an archive', async () => {
    prisma.practice.findUnique.mockResolvedValue({ ...EXISTING, isActive: false });
    await updatePractice({
      practiceId: 'prac_1',
      patch: { isActive: true },
      actorUserId: 'u1',
    });
    expect((logAudit.mock.calls[0]![0] as unknown as { action: string }).action).toBe('PRACTICE_RESTORED');
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
    expect(prisma.practice.update).not.toHaveBeenCalled();
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('a missing practice is `not_found`, and nothing is written', async () => {
    prisma.practice.findUnique.mockResolvedValue(null);
    const r = await updatePractice({
      practiceId: 'nope',
      patch: { name: 'X' },
      actorUserId: 'u1',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('not_found');
    expect(prisma.practice.update).not.toHaveBeenCalled();
  });
});

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
    const { execFileSync } = await import('node:child_process');
    const { join } = await import('node:path');
    const APP = join(__dirname, '..', '..', '..');
    const out = execFileSync('grep', ['-rn', '-F', '.practice.', '--include=*.ts', '--include=*.tsx', 'src'], {
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

    // POSITIVE CONTROL: the matcher fires at all.
    expect(hits.length, 'the grep found nothing — this arm measures nothing').toBeGreaterThan(0);

    const files = [...new Set(hits.map((l) => l.split(':')[0]!))].sort();
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
});
