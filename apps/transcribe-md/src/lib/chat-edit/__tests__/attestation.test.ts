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
function fakeRedis(opts: { expireFails?: boolean } = {}) {
  const sets = new Map<string, Set<string>>();
  const ttls = new Map<string, number>();
  const calls: string[] = [];
  return {
    sets,
    ttls,
    calls,
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
          expire(k: string, ttl: number) {
            ops.push(() => {
              if (!opts.expireFails) ttls.set(k, ttl);
            });
            return chain;
          },
          async exec() {
            ops.forEach((op) => op());
            calls.push('exec');
            return opts.expireFails
              ? [[null, 1] as const, [new Error('expire failed'), null] as const]
              : [[null, 1] as const, [null, 1] as const];
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
      async expire(k: string, ttl: number) {
        calls.push('expire');
        if (opts.expireFails) return 0;
        ttls.set(k, ttl);
        return 1;
      },
      async smismember(k: string, ...v: string[]) {
        const s = sets.get(k) ?? new Set<string>();
        return v.map((x) => (s.has(x) ? 1 : 0));
      },
      /** Narrowed delete: the key is only dropped when it genuinely has no
       *  TTL, so an earlier turn's attested ids are not thrown away. */
      async pttl(k: string) {
        calls.push('pttl');
        return ttls.has(k) ? ttls.get(k)! * 1000 : -1;
      },
      async del(k: string) {
        calls.push('del');
        sets.delete(k);
        ttls.delete(k);
        return 1;
      },
    },
  };
}

async function withRedis(
  ready: boolean,
  fn: (r: ReturnType<typeof fakeRedis>) => Promise<void>,
  opts: { expireFails?: boolean } = {},
) {
  const r = fakeRedis(opts);
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

describe('no TTL-less keys', () => {
  it('sets a TTL on the happy path', async () => {
    await withRedis(true, async (r) => {
      const m = await import('../attestation');
      await m.recordRendered('v1', 'u1', [m.claimId(CLAIM)]);
      expect(r.ttls.size, 'the key must carry a TTL').toBe(1);
    });
  });

  it('when the pipelined expire fails, it RETRIES and then DROPS the key', async () => {
    // `exec()` reports per-command errors as [err, res] pairs and does not
    // throw for them, so an expire that failed while the sadd succeeded left a
    // key that never expires — holding state in the instance that also brokers
    // the clinical pipeline.
    await withRedis(
      true,
      async (r) => {
        const m = await import('../attestation');
        await m.recordRendered('v1', 'u1', [m.claimId(CLAIM)]);
        expect(r.calls, 'it must retry the TTL').toContain('expire');
        expect(r.calls, 'and drop the key when that fails too').toContain('del');
        expect(r.ttls.size).toBe(0);
        expect(r.sets.size, 'a key with no TTL must not survive').toBe(0);
      },
      { expireFails: true },
    );
  });
});

describe('a failed SADD is its own failure, not a TTL problem', () => {
  it('reports it and does not pretend a record exists', async () => {
    // `some(([err]) => ...)` over BOTH pairs swallowed a failed sadd — the
    // attestation was never recorded at all — and misreported it as a missing
    // TTL. The gate refuses either way, but the operator was told the wrong
    // thing.
    const src = readFileSync('src/lib/chat-edit/attestation.ts', 'utf8');
    expect(src).toContain('const [saddErr] = results[0];');
    expect(src).toContain('const [expireErr] = results[1];');
    expect(src, 'the two failures must not be conflated').not.toContain(
      'results.some(([err])',
    );
  });

  it('only drops the key when it genuinely has no TTL', async () => {
    // recordRendered accumulates ids across listing turns. Deleting on any
    // expire hiccup would throw away earlier turns' correctly-attested ids
    // under a live TTL, and make the doctor re-read a list they had read.
    const src = readFileSync('src/lib/chat-edit/attestation.ts', 'utf8');
    expect(src).toContain('redis.pttl(k)');
    expect(src).toContain('if (ttl < 0)');
  });
});
