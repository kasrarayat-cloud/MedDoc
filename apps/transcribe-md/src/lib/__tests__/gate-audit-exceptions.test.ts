// ============================================================================
// #163 B(ii) — THE AUDIT GATE'S EXCEPTIONS ARE SCOPED, DEBT-BEARING, AND
// CANNOT ROT.
// ----------------------------------------------------------------------------
// An exception mechanism is a hole in a security gate. What makes this one an
// EXCEPTION rather than an override is a set of properties the gate enforces
// on itself — so those properties are what this file tests, in the direction
// that matters: the gate must REFUSE.
//
// ⚠️ THE DECISION IS A PURE FUNCTION ON PURPOSE. `judgeAudit(report, file)`
// takes an npm-audit report and the exceptions file and returns a verdict, so
// every arm below runs without a network, a lockfile, or an install — and a
// future advisory publication cannot turn these arms red for a reason that has
// nothing to do with the code.
// ============================================================================
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const gate = await import(
  /* @vite-ignore */ resolve(process.cwd(), '../../scripts/audit-gate.mjs')
);
const exceptionsFile = JSON.parse(
  readFileSync(resolve(process.cwd(), '../../scripts/audit-exceptions.json'), 'utf8'),
);

const LIVE_ID = 'GHSA-3f6p-5ww8-9rcr';
const advisory = (id: string, severity = 'high', name = 'pkg') => ({
  severity,
  via: [{ name, url: `https://github.com/advisories/${id}`, title: `${id} title`, severity }],
});

describe('#163 B(ii) — the npm-audit gate refuses what it should', () => {
  it('PASSES when the only high/critical advisory is the excepted one', () => {
    const verdict = gate.judgeAudit(
      { vulnerabilities: { mysql2: advisory(LIVE_ID, 'high', 'mysql2') } },
      exceptionsFile,
    );
    expect(verdict.code).toBe(0);
  });

  it('⚠️ BLOCKS a DIFFERENT advisory on the SAME package — the exception is by id', () => {
    // This is the property that makes it an exception and not a hole. An
    // exception written against `mysql2` would silently absorb the next
    // advisory published against mysql2 — the one nobody has read.
    const verdict = gate.judgeAudit(
      {
        vulnerabilities: {
          mysql2: {
            severity: 'high',
            via: [
              { name: 'mysql2', url: `https://github.com/advisories/${LIVE_ID}`, title: 'excepted', severity: 'high' },
              { name: 'mysql2', url: 'https://github.com/advisories/GHSA-nnnn-nnnn-nnnn', title: 'brand new', severity: 'high' },
            ],
          },
        },
      },
      exceptionsFile,
    );
    expect(verdict.code).toBe(1);
    expect(verdict.lines.some((l: string) => l.includes('GHSA-nnnn-nnnn-nnnn'))).toBe(true);
  });

  it('BLOCKS an unrelated high, and the excepted one does not shield it', () => {
    const verdict = gate.judgeAudit(
      {
        vulnerabilities: {
          mysql2: advisory(LIVE_ID, 'high', 'mysql2'),
          lodash: advisory('GHSA-xxxx-xxxx-xxxx', 'critical', 'lodash'),
        },
      },
      exceptionsFile,
    );
    expect(verdict.code).toBe(1);
    expect(verdict.lines.some((l: string) => l.includes('GHSA-xxxx-xxxx-xxxx'))).toBe(true);
  });

  it('⚠️ BLOCKS a STALE exception — a justification nobody re-reads is worse than none', () => {
    // Prose decays silently; an entry matching no live advisory sits where the
    // next reader takes it for a current decision.
    const verdict = gate.judgeAudit({ vulnerabilities: {} }, exceptionsFile);
    expect(verdict.code).toBe(1);
    expect(verdict.lines.some((l: string) => l.includes('STALE EXCEPTION'))).toBe(true);
  });

  it('⚠️ BLOCKS an exception with no retirement condition — that is an override', () => {
    const verdict = gate.judgeAudit(
      { vulnerabilities: { mysql2: advisory(LIVE_ID) } },
      { exceptions: [{ id: LIVE_ID, package: 'mysql2', justification: 'because' }] },
    );
    expect(verdict.code).toBe(1);
    expect(verdict.lines.some((l: string) => l.includes('INVALID EXCEPTION'))).toBe(true);
  });

  it('⚠️ FAILS CLOSED (2) when it cannot tell — no report, and no attributable id', () => {
    expect(gate.judgeAudit({}, exceptionsFile).code).toBe(2);
    expect(gate.judgeAudit({ vulnerabilities: {} }, {}).code).toBe(2);
    // A high package whose chain yields no advisory id at all: refuse rather
    // than pass an advisory nobody can name.
    expect(
      gate.judgeAudit(
        { vulnerabilities: { ghost: { severity: 'high', via: ['ghost'] } } },
        exceptionsFile,
      ).code,
    ).toBe(2);
  });

  it('a MODERATE advisory reached through a high package does not block', () => {
    // The gate's threshold is high/critical. The first version of the chain
    // walk reported a moderate valibot issue as BLOCKING because it inherited
    // the package's severity instead of reading the advisory's own.
    const verdict = gate.judgeAudit(
      {
        vulnerabilities: {
          mysql2: {
            severity: 'high',
            via: [
              { name: 'mysql2', url: `https://github.com/advisories/${LIVE_ID}`, title: 'x', severity: 'high' },
              { name: 'valibot', url: 'https://github.com/advisories/GHSA-mod-mod-mod', title: 'moderate thing', severity: 'moderate' },
            ],
          },
        },
      },
      exceptionsFile,
    );
    expect(verdict.code).toBe(0);
  });

  it('the SHIPPED exceptions file is itself well-formed and debt-bearing', () => {
    expect(exceptionsFile.exceptions.length).toBeGreaterThan(0);
    for (const e of exceptionsFile.exceptions) {
      expect(e.id, 'every exception is keyed by advisory id').toMatch(/^GHSA-/);
      expect(e.justification.length).toBeGreaterThan(80);
      expect(e.retires_when.length).toBeGreaterThan(20);
      expect(e.debt_item, 'an exception without a debt item is an override').toBeTruthy();
      // ⚠️ AND THE DEBT ITEM MUST EXIST, NOT MERELY BE NAMED. A blocking row
      // names the artifact that would discharge it; a pointer to a file nobody
      // wrote is the same as no retirement condition at all.
      expect(
        existsSync(resolve(process.cwd(), '../..', e.debt_item)),
        `${e.id} names a debt item that does not exist: ${e.debt_item}`,
      ).toBe(true);
    }
  });
});
