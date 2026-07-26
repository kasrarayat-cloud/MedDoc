// ============================================================================
// The reading gate must rest on something the server owns.
// ----------------------------------------------------------------------------
// The version this replaces searched a CLIENT-SUPPLIED transcript for each
// claim's text. A crafted POST could hand over a fabricated assistant turn and
// satisfy it without a word having reached a doctor. These pin the replacement:
// the record is written by the server, keyed to content, and fails closed.
// ============================================================================

import { readFileSync } from 'node:fs';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { claimId, recordRendered, wereRendered } from '../attestation';

const CLAIM = { section: 'FINDINGS', text: 'Right GSV reflux 2.4 seconds.' };

/** A tiny in-memory stand-in for the set operations we use. */
function fakeRedis() {
  const sets = new Map<string, Set<string>>();
  return {
    sets,
    client: {
      /** `recordRendered` pipelines sadd+expire so a dropped connection cannot
       *  leave a key without a TTL — the stub mirrors that shape. */
      multi() {
        const ops: Array<() => void> = [];
        const chain = {
          sadd(k: string, ...v: string[]) {
            ops.push(() => {
              const set = sets.get(k) ?? new Set<string>();
              v.forEach((x) => set.add(x));
              sets.set(k, set);
            });
            return chain;
          },
          expire() {
            return chain;
          },
          async exec() {
            ops.forEach((op) => op());
            return [];
          },
        };
        return chain;
      },
      async sadd(k: string, ...v: string[]) {
        const s = sets.get(k) ?? new Set<string>();
        v.forEach((x) => s.add(x));
        sets.set(k, s);
        return v.length;
      },
      async expire() {
        return 1;
      },
      async smismember(k: string, ...v: string[]) {
        const s = sets.get(k) ?? new Set<string>();
        return v.map((x) => (s.has(x) ? 1 : 0));
      },
      async del(k: string) {
        sets.delete(k);
        return 1;
      },
    },
  };
}

async function withRedis(ready: boolean, fn: (r: ReturnType<typeof fakeRedis>) => Promise<void>) {
  const r = fakeRedis();
  vi.doMock('@/lib/redis', () => ({
    getRedis: () => r.client,
    isRedisReady: () => ready,
  }));
  await fn(r);
  vi.doUnmock('@/lib/redis');
}

afterEach(() => vi.resetModules());

describe('claim identity', () => {
  it('is derived from CONTENT, not position', () => {
    // Adopting shrinks the array, so index 3 after two adoptions is a
    // different claim than index 3 before them. An attestation keyed by index
    // would authorise a suggestion the doctor never read.
    expect(claimId(CLAIM)).toBe(claimId({ ...CLAIM }));
    expect(claimId(CLAIM)).not.toBe(claimId({ ...CLAIM, text: `${CLAIM.text} ` }));
    expect(claimId(CLAIM)).not.toBe(claimId({ ...CLAIM, section: 'IMPRESSION' }));
  });
});

describe('the attestation store', () => {
  it('records what the server rendered, and confirms it', async () => {
    await withRedis(true, async () => {
      const m = await import('../attestation');
      const id = m.claimId(CLAIM);
      expect(await m.wereRendered('v1', 'u1', [id])).toBe(false);
      await m.recordRendered('v1', 'u1', [id]);
      expect(await m.wereRendered('v1', 'u1', [id])).toBe(true);
    });
  });

  it('is scoped to the visit AND the doctor', async () => {
    await withRedis(true, async () => {
      const m = await import('../attestation');
      const id = m.claimId(CLAIM);
      await m.recordRendered('v1', 'u1', [id]);
      expect(await m.wereRendered('v2', 'u1', [id])).toBe(false);
      expect(await m.wereRendered('v1', 'u2', [id])).toBe(false);
    });
  });

  it('needs ALL of them — a partial reading is not a reading', async () => {
    await withRedis(true, async () => {
      const m = await import('../attestation');
      const a = m.claimId(CLAIM);
      const b = m.claimId({ section: 'IMPRESSION', text: 'Left GSV patent.' });
      await m.recordRendered('v1', 'u1', [a]);
      expect(await m.wereRendered('v1', 'u1', [a, b])).toBe(false);
    });
  });

  it('FAILS CLOSED when the store is unavailable', async () => {
    await withRedis(false, async () => {
      const m = await import('../attestation');
      const id = m.claimId(CLAIM);
      await m.recordRendered('v1', 'u1', [id]); // no-op
      expect(await m.wereRendered('v1', 'u1', [id])).toBe(false);
    });
  });

  it('an empty set is never "rendered"', async () => {
    await withRedis(true, async () => {
      const m = await import('../attestation');
      expect(await m.wereRendered('v1', 'u1', [])).toBe(false);
    });
  });
});

describe('the dispatcher no longer trusts the client', () => {
  const src = readFileSync('src/actions/chat-edit-visit.ts', 'utf8');

  it('the client-transcript check is GONE', () => {
    expect(src, 'wereListed searched a client-supplied transcript').not.toContain('wereListed');
    expect(src).not.toContain('.filter((t) => t.role === ');
  });

  it('records only what the REPLY actually contains', () => {
    // The model declares what it listed; the server checks its own outgoing
    // reply for each claim's FULL text before recording anything.
    expect(src).toContain('parsed.reply.includes(c.text)');
    expect(src).toContain('recordRendered(');
  });

  it('gates bulk adoption on the SERVER record', () => {
    expect(src).toContain('await wereRendered(');
  });

  it('caps what one turn may do', () => {
    expect(src).toContain('MAX_ACTIONS_PER_TURN');
    expect(src).toMatch(/budget <= 0/);
  });
});

describe('the per-turn cap', () => {
  const src = readFileSync('src/actions/chat-edit-visit.ts', 'utf8');

  it('is enforced on a shared budget, not per intent', () => {
    // The listing gate was once evaluated per-intent, which fifty singular
    // adopts walked straight past. The cap must not repeat that: one budget
    // for the turn, decremented by every action whatever its shape.
    const decl = src.indexOf('let budget = MAX_ACTIONS_PER_TURN;');
    const loop = src.indexOf('for (const intent of parsed.intents)');
    expect(decl, 'the budget must be declared before the loop').toBeGreaterThan(-1);
    expect(decl).toBeLessThan(loop);
    // Both the adopt loop and the section edit draw from it.
    expect(src.match(/budget <= 0/g)?.length ?? 0).toBeGreaterThanOrEqual(2);
  });

  it('SAYS when it capped — silent truncation would read as completion', () => {
    expect(src).toContain('capped > 0');
    expect(src).toContain('I stopped at');
  });
});

describe('the attestation cannot authorise the turn that created it', () => {
  const src = readFileSync('src/actions/chat-edit-visit.ts', 'utf8');

  it('checks the PRE-EXISTING record, then records this turn', () => {
    // Recording first and checking after let one reply both list and adopt —
    // the model satisfying, in the same breath, the gate that exists to put
    // the doctor's eyes between the two.
    const check = src.indexOf('await wereRendered(');
    const record = src.indexOf('await recordRendered(');
    expect(check).toBeGreaterThan(-1);
    expect(record).toBeGreaterThan(-1);
    expect(check, 'the check must precede the record').toBeLessThan(record);
  });
});
