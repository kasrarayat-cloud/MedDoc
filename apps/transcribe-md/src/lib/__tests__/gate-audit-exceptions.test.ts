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
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
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

// ============================================================================
// ⚠️ THE REGISTRY IS A DEPENDENCY OF A REQUIRED CHECK — RETRY, FAIL CLOSED.
// ----------------------------------------------------------------------------
// On 2026-09-04 this gate redded a deploy commit with CANNOT TELL: npm's
// advisory endpoint answered 500, so the report carried no `vulnerabilities`
// object. NO VULNERABILITY WAS FOUND — the gate could not tell, which is the
// correct refusal and the wrong outcome for a one-second blip. A re-run minutes
// later was green, and a deploy had already paid a cycle for it.
//
// ⚠️ AND THE FIX IS NOT WHAT THE FAILURE LOG APPEARS TO ASK FOR. The log
// carried npm's *"this endpoint is being retired — use the bulk advisory
// endpoint"* notice, which reads like the diagnosis. Measured on npm 11.10.0:
// the bulk path is ALREADY what npm uses, and `audits/quick` is npm's own
// FALLBACK once bulk has failed. The notice is a symptom of the outage. A
// reader who fixed what the log named would have changed nothing.
// ============================================================================
describe('the audit gate survives a registry blip without going blind', () => {
  it('⚠️ an ANSWER is never re-rolled — including one that BLOCKS', async () => {
    const { isUsableReport } = await import(
      /* @vite-ignore */ resolve(process.cwd(), '../../scripts/audit-gate.mjs')
    );
    // the dangerous retry would be one that re-rolls a report full of findings
    // until the registry hiccups and hands back a clean-looking blank
    expect(
      isUsableReport(JSON.stringify({ vulnerabilities: { lodash: { severity: 'critical' } } })),
      'a BLOCKING report was treated as unusable and would be retried away',
    ).toBe(true);
    expect(isUsableReport(JSON.stringify({ vulnerabilities: {}, metadata: {} }))).toBe(true);
  });

  it('⚠️ an OUTAGE is not mistaken for an all-clear', async () => {
    const { isUsableReport } = await import(
      /* @vite-ignore */ resolve(process.cwd(), '../../scripts/audit-gate.mjs')
    );
    // a registry failure still writes JSON to stdout — it simply has no
    // findings in it. "Did it print something" cannot tell an all-clear from an
    // outage, which is the exact confusion this gate exists to refuse.
    expect(isUsableReport(JSON.stringify({ error: { code: 'E500' } }))).toBe(false);
    expect(isUsableReport('')).toBe(false);
    expect(isUsableReport('not json')).toBe(false);
    expect(isUsableReport(null)).toBe(false);
  });

  // ⚠️ THIS ARM WAS A SOURCE-TEXT CHECK AND TWO MUTATIONS WALKED PAST IT.
  // `/ATTEMPTS/` still matches `ATTEMPTS_REMOVED` — the substring trap — and
  // `process.exit(2)` appears more than once, so replacing the cannot-tell one
  // left the pattern satisfied. Both are now driven BEHAVIOURALLY: a fake `npm`
  // on PATH, and the real script's real exit code.
  it('⚠️ RETRIES a transient outage, then SUCCEEDS — driven through a fake npm', () => {
    const dir = mkdtempSync(join(tmpdir(), 'auditgate-'));
    // fails once with a registry-shaped error, then answers properly
    writeFileSync(
      join(dir, 'npm'),
      [
        '#!/usr/bin/env bash',
        `n=$(cat "${dir}/count" 2>/dev/null || echo 0)`,
        `echo $((n+1)) > "${dir}/count"`,
        'if [ "$n" = "0" ]; then echo \'{"error":{"code":"E500"}}\'; exit 1; fi',
        'echo \'{"auditReportVersion":2,"vulnerabilities":{},"metadata":{}}\'',
      ].join('\n'),
      { mode: 0o755 },
    );
    const r = spawnSync('node', [resolve(process.cwd(), '../../scripts/audit-gate.mjs')], {
      env: { ...process.env, PATH: `${dir}:${process.env.PATH}` },
      encoding: 'utf8',
      timeout: 120_000,
    });
    // THE PROPERTY: a transient outage is RETRIED, and the second answer is
    // then JUDGED rather than discarded.
    expect(readFileSync(join(dir, 'count'), 'utf8').trim(), 'it did not retry').toBe('2');
    // ⚠️ NOT `toBe(0)`, AND THE FIRST DRAFT GOT THIS WRONG. My fake report is
    // empty, so the gate correctly called the shipped exception STALE and
    // exited 1 — a refusal caused by my own substitution, not by the retry.
    // Pinning exit 0 would also couple this arm to the live advisory corpus, so
    // it would red whenever an unrelated advisory came or went. What must hold
    // is that the outcome is an ANSWER: anything but CANNOT TELL.
    expect(
      r.status,
      `still CANNOT TELL after a successful retry; stderr=${r.stderr}`,
    ).not.toBe(2);
    expect(r.stdout + r.stderr, 'it never reached a verdict').toMatch(/audit-gate: (PASS|BLOCKED)/);
    rmSync(dir, { recursive: true, force: true });
  }, 120_000);

  it('⚠️ FAILS CLOSED (2) when every attempt is unusable — an outage still blocks', () => {
    const dir = mkdtempSync(join(tmpdir(), 'auditgate-'));
    writeFileSync(
      join(dir, 'npm'),
      ['#!/usr/bin/env bash', 'echo \'{"error":{"code":"E500"}}\'', 'exit 1'].join('\n'),
      { mode: 0o755 },
    );
    const r = spawnSync('node', [resolve(process.cwd(), '../../scripts/audit-gate.mjs')], {
      env: { ...process.env, PATH: `${dir}:${process.env.PATH}` },
      encoding: 'utf8',
      timeout: 180_000,
    });
    // ⚠️ 2, NOT 0 AND NOT 1. A registry outage is CANNOT TELL, never an
    // all-clear and never a finding.
    expect(r.status, `expected CANNOT TELL; stdout: ${r.stdout}`).toBe(2);
    expect(r.stderr + r.stdout).toMatch(/CANNOT TELL/);
    rmSync(dir, { recursive: true, force: true });
  }, 180_000);

  // ⚠️ THERE ARE TWO CANNOT-TELL EXITS AND THEY NEED SEPARATE ARMS. The arm
  // above drives `judgeAudit`'s code 2 (parseable JSON, no findings object).
  // This one drives the PARSE-FAILURE branch — npm emitting something that is
  // not JSON at all. A mutation flipping that branch to exit 0 walked past the
  // whole file until this existed.
  it('⚠️ UNPARSEABLE output also fails closed (2), not silently green', () => {
    const dir = mkdtempSync(join(tmpdir(), 'auditgate-'));
    writeFileSync(
      join(dir, 'npm'),
      ['#!/usr/bin/env bash', 'echo "<html>502 Bad Gateway</html>"', 'exit 1'].join('\n'),
      { mode: 0o755 },
    );
    const r = spawnSync('node', [resolve(process.cwd(), '../../scripts/audit-gate.mjs')], {
      env: { ...process.env, PATH: `${dir}:${process.env.PATH}` },
      encoding: 'utf8',
      timeout: 180_000,
    });
    expect(r.status, `expected CANNOT TELL; stdout: ${r.stdout}`).toBe(2);
    expect(r.stderr + r.stdout).toMatch(/CANNOT TELL/);
    rmSync(dir, { recursive: true, force: true });
  }, 180_000);
});
