/**
 * PR #993's DEPLOY ROW — a stale ICD-10 edition reports; stale PLUS shipping ICD
 * changes refuses.
 *
 * CMS publishes ICD-10-CM by fiscal year. Nothing breaks loudly when the
 * edition turns over: the ingestion gates assert FY2026's counts against
 * FY2026's data, so a stale set is indistinguishable from a correct one to
 * everything that runs. The cost lands on a BILLING surface — a doctor told to
 * bill a child code that no longer exists.
 *
 * ⚠️ REPORTING, NOT BLOCKING, IS PR #993's OWN RECOMMENDATION AND IT IS KEPT. A
 * hard gate reds every lane from today, because the watcher already says DUE at
 * 25 days.
 */
import { describe, it, expect } from 'vitest';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const LIB = resolve(__dirname, '../../../../../scripts/lib/icd-staleness-row.sh');
const verdict = (rc: string, p: string) =>
  execFileSync('bash', ['-c', `. "${LIB}"; icd_staleness_verdict "${rc}" "${p}"`], { encoding: 'utf8' }).trim();
const kind = (rc: string, p: string) => verdict(rc, p).split('|')[0];

describe('PR #993 — the staleness row and its passenger clause', () => {
  it('POSITIVE CONTROL: the library loads and answers', () => {
    expect(['pass', 'report', 'refuse']).toContain(kind('0', '0'));
    expect(verdict('0', '0').split('|')[1].length).toBeGreaterThan(10);
  });

  it('a CURRENT edition passes, even when shipping ICD changes', () => {
    expect(kind('0', '0')).toBe('pass');
    expect(kind('0', '9')).toBe('pass');
  });

  it('stale with NO ICD changes REPORTS — it must not block other lanes', () => {
    // The arm that keeps PR #993's recommendation honest. If this ever says
    // refuse, every deploy from every lane stops on a 25-day warning.
    expect(kind('1', '0')).toBe('report');
    expect(kind('2', '0')).toBe('report');
  });

  it('⚠️ stale AND shipping ICD changes REFUSES, naming both halves', () => {
    const v = verdict('1', '2');
    expect(v.split('|')[0]).toBe('refuse');
    expect(v).toContain('NOT current');
    expect(v).toContain('2 ICD file');
  });

  it('one ICD file is already a passenger — the boundary is >0', () => {
    expect(kind('1', '1')).toBe('refuse');
  });

  it('⚠️ an UNKNOWN passenger count REPORTS, not refuses — and that is deliberate', () => {
    // Against the usual fail-closed instinct, on purpose: the refusal needs
    // BOTH halves, and refusing on an unknown second half blocks deploys that
    // carry no ICD change at all — a watcher becoming an outage.
    expect(kind('1', '')).toBe('report');
    expect(verdict('1', '')).toContain('UNKNOWN');
  });

  it('an unreadable exit code REPORTS and says it is unevaluated', () => {
    expect(kind('x', '0')).toBe('report');
    expect(verdict('', '0')).toContain('UNEVALUATED');
  });
});
