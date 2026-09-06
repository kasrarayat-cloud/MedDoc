/**
 * RULING #198 — A MIGRATION-CARRYING DEPLOY REQUIRES THE `strict` DECLARATION.
 *
 * ⚠️ #96(b) IS APPLIED ONE LEVEL FINER, NOT OVERTURNED. Strictness is
 * proportional to reversibility. A code-only deploy is answerable by an image
 * rollback, so `present` stays — requiring a prior commit there would refuse
 * every deploy whose author lands the declaration in the same PR, which is a
 * real habit. A MIGRATION is not answerable by a rollback, so it takes the
 * standard `run-ruled-mutation.sh` already uses.
 *
 * THE SPECIMEN: `079b9205`'s migration finished at 00:01:00 and its declaration
 * was committed at 00:05:42; `50b02832`'s finished at 09:06:35 and its
 * declaration at 09:12:21. In both the irreversible act had ALREADY COMPLETED,
 * so the record cannot tell an honest declaration from one composed once the
 * outcome was known. The gate accepted both, correctly, by its own rules.
 *
 * ⚠️ THE DECISION IS DRIVEN, NOT REIMPLEMENTED. It is a pure shell function
 * taking two counts, split out of `deploy-prod.sh` for exactly this reason: the
 * GATHERING is a `find` plus a psql query, the DECISION is arithmetic, and only
 * the arithmetic can be wrong in a way nobody notices.
 */
import { describe, it, expect } from 'vitest';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const LIB = resolve(__dirname, '../../../../../scripts/lib/declaration.sh');

/** Drive the real function; returns `strict|reason` or `present|reason`. */
function decide(repo: string, applied: string): { mode: string; why: string } {
  const out = execFileSync(
    'bash',
    ['-c', `. "${LIB}"; declaration_strictness_for_migrations "${repo}" "${applied}"`],
    { encoding: 'utf8' },
  ).trim();
  const i = out.indexOf('|');
  return { mode: out.slice(0, i), why: out.slice(i + 1) };
}

describe('#198 — migration-carrying deploys are strict, code-only stays present', () => {
  it('POSITIVE CONTROL: the library loads and the function answers', () => {
    // Without this, every `strict` below could be an empty string from a
    // failed source, and "" !== "present" would pass the refusal arms.
    const r = decide('111', '111');
    expect(['strict', 'present']).toContain(r.mode);
    expect(r.why.length).toBeGreaterThan(10);
  });

  it('code-only stays `present` — the #96(b) case, and it must NOT tighten', () => {
    // This is the arm that stops #198 from becoming "strict for everything".
    // Today's production shape: 111 in the repo, 111 applied.
    expect(decide('111', '111').mode).toBe('present');
    expect(decide('5', '5').mode).toBe('present');
  });

  it('⚠️ a deploy that APPLIES a migration is raised to `strict`', () => {
    const r = decide('113', '111');
    expect(r.mode).toBe('strict');
    expect(r.why).toContain('APPLIES 2');
  });

  it('one migration is already migration-carrying — the boundary is >0, not >1', () => {
    expect(decide('112', '111').mode).toBe('strict');
  });

  it('⚠️ FAIL-CLOSED: an unreadable applied-count is `strict`, never `present`', () => {
    // A database that will not answer must not resolve to the weaker gate.
    for (const bad of ['', 'ERROR', 'null', ' ']) {
      expect(decide('111', bad).mode, `applied=${JSON.stringify(bad)}`).toBe('strict');
    }
  });

  it('⚠️ FAIL-CLOSED: an unreadable repo count is `strict` too', () => {
    for (const bad of ['', 'abc']) {
      expect(decide(bad, '111').mode, `repo=${JSON.stringify(bad)}`).toBe('strict');
    }
  });

  it('⚠️ a ZERO repo count is cannot-tell, not "no migrations"', () => {
    // This tree cannot be in that state, so a zero there is a broken `find`.
    // Read as "no migrations" it would hand the WEAKER gate to exactly the
    // situation where the instrument is broken.
    const r = decide('0', '111');
    expect(r.mode).toBe('strict');
    expect(r.why).toContain('not a state this tree can be in');
  });

  it('the reason always names the numbers, so a transcript can be audited', () => {
    expect(decide('113', '111').why).toContain('113');
    expect(decide('113', '111').why).toContain('111');
    expect(decide('111', '111').why).toContain('111');
  });
});
