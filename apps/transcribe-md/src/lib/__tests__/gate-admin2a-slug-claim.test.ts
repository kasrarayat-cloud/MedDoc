// ============================================================================
// GATE — ADMIN-2a: A HUMAN-CHOSEN PRACTICE SLUG.
// ----------------------------------------------------------------------------
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · a live zone / mail label stops being reserved     -> the label block
//   · the `solo-` namespace becomes claimable            -> the label block
//   · `xn--` or any `--` in positions 3–4 is accepted    -> the label block
//   · an UNCHANGED machine slug in a patch is refused    -> the write block
//   · a unique violation becomes a raw throw (500)       -> the write block
//   · a P2002 is relabelled when the slug did not change -> the write block
//   · the claim's compare-and-set leaves the WHERE       -> the write block
//   · a count-0 CAS reports success or audits            -> the write block
//   · a non-OWNER, or nobody, can claim                  -> the claim block
//   · a second claim succeeds                            -> the claim block
//   · the practice is read from the FORM                 -> the claim block
//   · an archived practice can claim                     -> the claim block
//
// ⚠️ THE REAL `practice-write` AND `practice-admin` RUN HERE. Only the database,
// the audit sink and the session are doubles, so the claim is exercised through
// the same verb and the same guard the product uses — not through a mock of
// either, which would prove the action calls a function and nothing else.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

type Row = { id: string; name: string; slug: string; isActive: boolean };

const { prisma, logAudit, getSession, state } = vi.hoisted(() => {
  const state: {
    row: { id: string; name: string; slug: string; isActive: boolean } | null;
    takenBy: string | null;
    actor: { practiceRole: string | null; practiceId: string } | null;
  } = { row: null, takenBy: null, actor: null };
  const practice = {
    // ⚠️ ONE DOUBLE ANSWERING BY THE SHAPE OF ITS `where`, because three
    // different reads hit it: the action's read (`id`), the verb's `before`
    // read (`id`) and the verb's taken check (`slug`).
    findUnique: vi.fn(async (q: { where: { id?: string; slug?: string } }) => {
      if (q.where.slug !== undefined) return state.takenBy ? { id: state.takenBy } : null;
      return state.row && q.where.id === state.row.id ? { ...state.row } : null;
    }),
    update: vi.fn(async (_q: { where: { id: string }; data: Partial<Row> }) => ({})),
    // Stateful: a matching CAS moves the row, so a SECOND claim sees the result.
    updateMany: vi.fn(async (q: { where: { id: string; slug: string }; data: Partial<Row> }) => {
      if (state.row && state.row.id === q.where.id && state.row.slug === q.where.slug) {
        state.row = { ...state.row, ...q.data };
        return { count: 1 };
      }
      return { count: 0 };
    }),
  };
  const user = {
    findUnique: vi.fn(async () => state.actor),
  };
  return {
    prisma: { practice, user },
    logAudit: vi.fn(async (_row: { action: string; metadata?: unknown }) => undefined),
    getSession: vi.fn(),
    state,
  };
});

vi.mock('@meddoc/db', () => ({ default: prisma, prisma }));
vi.mock('../audit', () => ({ logAudit }));
vi.mock('@/lib/auth', () => ({ getSession }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import { isMachineSlug, practiceLabelRefusal, updatePractice } from '../practice-write';
import { claimPracticeSlug } from '../../actions/practice-settings';

const MACHINE = 'solo-k3j9x2-mz81qa';
const SESSION = { user: { id: 'u-owner', practiceId: 'p-1' } };

function form(entries: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(entries)) fd.set(k, v);
  return fd;
}

function asRole(role: string | null, practiceId = 'p-1') {
  state.actor = { practiceRole: role, practiceId };
  getSession.mockResolvedValue(SESSION);
}

function practiceUpdatedRows() {
  return logAudit.mock.calls
    .map((c) => c[0])
    .filter((r) => r.action === 'PRACTICE_UPDATED');
}

beforeEach(() => {
  vi.clearAllMocks();
  state.row = { id: 'p-1', name: 'Solo — Dr A', slug: MACHINE, isActive: true };
  state.takenBy = null;
  state.actor = null;
});

// ============================================================================
describe('ADMIN-2a — the label guard: what may be a practice host label', () => {
  it.each([
    'send', // MEASURED: live MX + SPF in the zone
    'www2',
    'mta-sts',
    'autodiscover',
    'autoconfig',
    'quillmd',
    'imap',
    'pop',
    'pop3',
    'webmail',
  ])('⚠️ refuses the zone / mail label %s', (slug) => {
    expect(practiceLabelRefusal(slug)).toBe('reserved_slug');
  });

  it.each(['www', 'app', 'admin', 'staging', 'pro'])(
    'still refuses the pre-existing reserved name %s',
    (slug) => {
      expect(practiceLabelRefusal(slug)).toBe('reserved_slug');
    },
  );

  it.each(['solo-northside', MACHINE, 'solo-abc'])(
    '⚠️ refuses the machine namespace %s — a human cannot claim a machine-looking name',
    (slug) => {
      expect(practiceLabelRefusal(slug)).toBe('reserved_slug');
    },
  );

  it.each([
    ['punycode', 'xn--nrthside-q9a'],
    ['R-LDH, not xn', 'ab--cd'],
    ['R-LDH, digits', '12--34'],
  ])('⚠️ refuses %s (%s) — `--` in positions 3–4 is RFC 5891-reserved', (_n, slug) => {
    expect(practiceLabelRefusal(slug)).toBe('invalid_slug');
  });

  it('⚠️ NON-VACUITY — near misses of every rule above are ACCEPTED', () => {
    // Each of these sits one step from a refused shape. If any is refused, a
    // rule above has grown past its stated boundary.
    for (const slug of [
      'northside',
      'abc--d', // `--` at positions 4–5, not 3–4
      'north--side',
      'solo', // the word, not the `solo-` prefix
      'soloist',
      'solos-clinic',
      'sender', // not `send`
      'popular', // not `pop`
    ]) {
      expect(practiceLabelRefusal(slug), slug).toBeNull();
    }
  });

  it('isMachineSlug is the prefix and only the prefix', () => {
    expect(isMachineSlug(MACHINE)).toBe(true);
    expect(isMachineSlug('solo-')).toBe(true);
    expect(isMachineSlug('solo')).toBe(false);
    expect(isMachineSlug('northside')).toBe(false);
    expect(isMachineSlug('x-solo-a')).toBe(false);
  });
});

// ============================================================================
describe('ADMIN-2a — the write verb', () => {
  it('⚠️ an UNCHANGED machine slug in a patch is NOT refused — 195 rows hold one', async () => {
    // A form that sends every field carries the current slug back. Refusing it
    // would make a rename impossible for 195 practices, over a value nobody
    // asked to write.
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { name: 'Northside Clinic', slug: MACHINE },
      actorUserId: 'u-admin',
    });
    expect(r.ok, JSON.stringify(r)).toBe(true);
    if (r.ok) expect(Object.keys(r.changed)).toEqual(['name']);
  });

  it('but CHANGING to a machine slug is refused, before any taken-read or write', async () => {
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { slug: 'solo-mine' },
      actorUserId: 'u-admin',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('reserved_slug');
    expect(prisma.practice.update).not.toHaveBeenCalled();
    expect(
      prisma.practice.findUnique.mock.calls.some((c) => c[0].where.slug !== undefined),
      'the taken check ran for a refused label',
    ).toBe(false);
  });

  it('⚠️ a unique violation on the WRITE is `slug_taken`, not a raw 500 — and audits nothing', async () => {
    // The taken-read saw the name free; a concurrent writer took it first.
    prisma.practice.update.mockRejectedValueOnce(
      Object.assign(new Error('Unique constraint failed on the constraint: `practices_slug_key`'), {
        code: 'P2002',
      }),
    );
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { slug: 'northside' },
      actorUserId: 'u-admin',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('slug_taken');
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ a P2002 when the patch does NOT change the slug is rethrown, never relabelled', async () => {
    const err = Object.assign(new Error('some other unique'), { code: 'P2002' });
    prisma.practice.update.mockRejectedValueOnce(err);
    await expect(
      updatePractice({ practiceId: 'p-1', patch: { name: 'X' }, actorUserId: 'u-admin' }),
    ).rejects.toBe(err);
  });

  it('and a non-unique failure on a slug change is rethrown too', async () => {
    const err = Object.assign(new Error('connection reset'), { code: 'P1017' });
    prisma.practice.update.mockRejectedValueOnce(err);
    await expect(
      updatePractice({ practiceId: 'p-1', patch: { slug: 'northside' }, actorUserId: 'u-admin' }),
    ).rejects.toBe(err);
  });

  it('⚠️ `ifSlugIs` is a COMPARE-AND-SET in the WHERE — the plain update is not used', async () => {
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { slug: 'northside' },
      actorUserId: 'u-owner',
      ifSlugIs: MACHINE,
    });
    expect(r.ok).toBe(true);
    expect(prisma.practice.update).not.toHaveBeenCalled();
    expect(prisma.practice.updateMany).toHaveBeenCalledOnce();
    expect(prisma.practice.updateMany.mock.calls[0]![0].where).toEqual({
      id: 'p-1',
      slug: MACHINE, // ← the CAS predicate. Without it a second claim overwrites the first.
    });
  });

  it('⚠️ a CAS that matches nothing is `changed_under_you` and audits NOTHING', async () => {
    // The row moved between the verb's read and its write.
    prisma.practice.updateMany.mockResolvedValueOnce({ count: 0 });
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { slug: 'northside' },
      actorUserId: 'u-owner',
      ifSlugIs: MACHINE,
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('changed_under_you');
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('a precondition already false at the read refuses before any write', async () => {
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { slug: 'northside' },
      actorUserId: 'u-owner',
      ifSlugIs: 'solo-some-other',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('changed_under_you');
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
    expect(prisma.practice.update).not.toHaveBeenCalled();
  });

  it('and a P2002 through the CAS path is `slug_taken` as well', async () => {
    prisma.practice.updateMany.mockRejectedValueOnce(
      Object.assign(new Error('unique'), { code: 'P2002' }),
    );
    const r = await updatePractice({
      practiceId: 'p-1',
      patch: { slug: 'northside' },
      actorUserId: 'u-owner',
      ifSlugIs: MACHINE,
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('slug_taken');
  });
});

// ============================================================================
describe("ADMIN-2a — the owner's one-time claim", () => {
  it('an OWNER on a machine slug claims a name: CAS write, audited from -> to', async () => {
    asRole('OWNER');
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res, JSON.stringify(res)).toEqual({ ok: true, slug: 'northside' });
    expect(prisma.practice.updateMany.mock.calls[0]![0]).toMatchObject({
      where: { id: 'p-1', slug: MACHINE },
      data: { slug: 'northside' },
    });
    const rows = practiceUpdatedRows();
    expect(rows).toHaveLength(1);
    expect(rows[0]!.metadata).toMatchObject({
      changed: { slug: { from: MACHINE, to: 'northside' } },
      reason: expect.stringContaining('ADMIN-2a'),
    });
  });

  it('trims and lowercases what the doctor typed — and nothing else', async () => {
    asRole('OWNER');
    const res = await claimPracticeSlug(null, form({ slug: '  NorthSide  ' }));
    expect(res).toEqual({ ok: true, slug: 'northside' });
  });

  it.each(['CLINICIAN', 'TECH', null])(
    '⚠️ a %s cannot claim — no practice read, no write',
    async (role) => {
      asRole(role);
      const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
      expect(res?.ok).toBe(false);
      expect(res && !res.ok && res.reason).toBe('ROLE_MAY_NOT_ADMINISTER');
      expect(prisma.practice.findUnique).not.toHaveBeenCalled();
      expect(prisma.practice.updateMany).not.toHaveBeenCalled();
      expect(prisma.practice.update).not.toHaveBeenCalled();
    },
  );

  it('an OWNER of ANOTHER practice cannot claim this one', async () => {
    asRole('OWNER', 'p-2');
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_MAY_NOT_ADMINISTER');
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
  });

  it('nobody signed in cannot claim', async () => {
    getSession.mockResolvedValue(null);
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res && !res.ok && res.reason).toBe('UNAUTHENTICATED');
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ A SECOND CLAIM IS REFUSED — the first succeeds, the second names support', async () => {
    asRole('OWNER');
    const first = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(first?.ok, 'the first claim must succeed or the second proves nothing').toBe(true);

    const second = await claimPracticeSlug(null, form({ slug: 'southside' }));
    expect(second?.ok).toBe(false);
    if (second && !second.ok) {
      expect(second.reason).toBe('ALREADY_CLAIMED');
      // The refusal says where later changes are made, per the brief.
      expect(second.message).toMatch(/support/i);
    }
    expect(prisma.practice.updateMany).toHaveBeenCalledTimes(1);
    expect(practiceUpdatedRows()).toHaveLength(1);
    expect(state.row!.slug).toBe('northside');
  });

  it('a practice that already had a human slug is refused the same way', async () => {
    asRole('OWNER');
    state.row = { ...state.row!, slug: 'eastside' };
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res && !res.ok && res.reason).toBe('ALREADY_CLAIMED');
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ two owners claiming at once: the CAS lets exactly one through', async () => {
    // Both read the machine slug; the verb's own read is taken AFTER the first
    // write landed in this interleaving, so the second is stopped by the CAS
    // precondition. Modelled by moving the row between the action's read and
    // the verb's write.
    asRole('OWNER');
    prisma.practice.updateMany.mockImplementationOnce(async () => ({ count: 0 }));
    const res = await claimPracticeSlug(null, form({ slug: 'southside' }));
    expect(res && !res.ok && res.reason).toBe('changed_under_you');
    expect(practiceUpdatedRows()).toHaveLength(0);
  });

  it('an ARCHIVED practice cannot claim — fail closed', async () => {
    asRole('OWNER');
    state.row = { ...state.row!, isActive: false };
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res && !res.ok && res.reason).toBe('PRACTICE_ARCHIVED');
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ the practice comes from the GUARD — a posted practiceId is ignored', async () => {
    asRole('OWNER');
    state.row = { ...state.row!, id: 'p-1' };
    const res = await claimPracticeSlug(null, form({ slug: 'northside', practiceId: 'p-2' }));
    expect(res?.ok).toBe(true);
    expect(prisma.practice.updateMany.mock.calls[0]![0].where.id).toBe('p-1');
  });

  it.each([
    ['admin', 'reserved_slug'],
    ['send', 'reserved_slug'],
    ['solo-mine', 'reserved_slug'],
    ['xn--nrthside-q9a', 'invalid_slug'],
    ['ab--cd', 'invalid_slug'],
    ['ab', 'invalid_slug'],
    ['north side', 'invalid_slug'],
    ['   ', 'INVALID'],
  ])('refuses %s as %s — before reading the practice, and writes nothing', async (slug, reason) => {
    asRole('OWNER');
    const res = await claimPracticeSlug(null, form({ slug }));
    expect(res?.ok).toBe(false);
    if (res && !res.ok) {
      expect(res.reason).toBe(reason);
      expect(res.message.length).toBeGreaterThan(10);
    }
    expect(prisma.practice.findUnique).not.toHaveBeenCalled();
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
  });

  it('a missing slug field is INVALID', async () => {
    asRole('OWNER');
    const res = await claimPracticeSlug(null, form({}));
    expect(res && !res.ok && res.reason).toBe('INVALID');
  });

  it('a name another practice holds is `slug_taken`', async () => {
    asRole('OWNER');
    state.takenBy = 'p-9';
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res && !res.ok && res.reason).toBe('slug_taken');
    expect(prisma.practice.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ and the RACE past that check is `slug_taken` too, with words — not a 500', async () => {
    asRole('OWNER');
    prisma.practice.updateMany.mockRejectedValueOnce(
      Object.assign(new Error('Unique constraint failed'), { code: 'P2002' }),
    );
    const res = await claimPracticeSlug(null, form({ slug: 'northside' }));
    expect(res && !res.ok && res.reason).toBe('slug_taken');
    expect(res && !res.ok && res.message).toMatch(/another practice/i);
    expect(practiceUpdatedRows()).toHaveLength(0);
  });
});
