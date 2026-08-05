// ============================================================================
// Every vendor-calling path honours MOCK_AI_CALLS.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE `em-coding/llm-mdm.ts` DID NOT, AND MADE REAL ANTHROPIC
// CALLS FROM CI. They surfaced as `401 invalid x-api-key` in the e2e job's app
// logs — failing only because CI's key is a dummy, which is the second condition
// working exactly as AGENTS.md describes it. With a real key in the environment
// the same code would have spent money and reached a vendor from a stack whose
// header promises it can reach nothing.
//
// ⚠️ AND `check-qa-mock-posture.sh` COULD NOT HAVE CAUGHT IT. That check reads
// the RUNNING CONTAINERS' env, and the env was correct — `docker-compose.qa.yml`
// hardcodes `MOCK_AI_CALLS: "true"` for app and worker, not a `${VAR:-}`
// default. Config was right; a code path simply never consulted it. Reading
// configuration proves nothing about a path that does not read it, so the guard
// has to be in the source.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

/** Files that construct a vendor client or issue a vendor call directly. */
const VENDOR_PATHS = ['src/lib/em-coding/llm-mdm.ts'] as const;

const strip = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');

describe('MOCK_AI_CALLS is honoured by the paths that can reach a vendor', () => {
  it('NON-VACUITY — the sources parsed to something real', () => {
    // Without this, a stripper that ate the file would make every `toMatch`
    // below trivially false and the gate would report green about nothing.
    for (const f of VENDOR_PATHS) {
      const code = strip(readFileSync(join(process.cwd(), f), 'utf8'));
      expect(code.length, `${f} stripped to almost nothing`).toBeGreaterThan(2000);
    }
  });

  it('llm-mdm short-circuits BEFORE it builds a request', () => {
    const src = readFileSync(join(process.cwd(), 'src/lib/em-coding/llm-mdm.ts'), 'utf8');
    const code = strip(src);

    // ⚠️ ASSERTED ON EXECUTABLE SOURCE, NOT THE RAW FILE. The comment above the
    // guard explains the flag at length; matching prose instead of code is the
    // A2 defect-2 shape that has caught several guards in this repo.
    expect(code, 'llm-mdm does not consult MOCK_AI_CALLS at all').toMatch(
      /process\.env\.MOCK_AI_CALLS\s*===\s*'true'/,
    );

    // ⚠️ AND IT MUST COME FIRST. A flag read that sits AFTER the request is
    // built, or after the client is constructed, is not a short-circuit — it
    // would still have reached the vendor. Position is the property, so
    // position is what gets asserted.
    const guardAt = code.indexOf('MOCK_AI_CALLS');
    const bodyAt = code.indexOf('args.soap.trim()');
    expect(guardAt, 'no MOCK_AI_CALLS guard found in callClaudeMdm').toBeGreaterThan(-1);
    expect(bodyAt, 'the prompt-building line moved — re-anchor this test').toBeGreaterThan(-1);
    expect(
      guardAt,
      'the MOCK_AI_CALLS guard sits AFTER the request is built — it would ' +
        'still reach the vendor',
    ).toBeLessThan(bodyAt);
  });

  it('POSITIVE CONTROL — the matcher fires on the pre-fix source', () => {
    // The file as it stood: straight into building the prompt, no flag read.
    const preFix = `
      async function callClaudeMdm(args) {
        const userPrompt = args.soap.trim();
        const response = await anthropic.messages.create({ ... });
        return validateMdmJudgement(response);
      }
    `;
    expect(preFix).not.toMatch(/process\.env\.MOCK_AI_CALLS\s*===\s*'true'/);
  });

  it('the strict-equality form is used — truthiness would be a different bug', () => {
    const code = strip(
      readFileSync(join(process.cwd(), 'src/lib/em-coding/llm-mdm.ts'), 'utf8'),
    );
    // `if (process.env.MOCK_AI_CALLS)` is true for the string 'false', which is
    // how a mock guard turns into an always-on guard. Every sibling in this repo
    // compares against the literal 'true'; so does this one.
    expect(code).not.toMatch(/if\s*\(\s*process\.env\.MOCK_AI_CALLS\s*\)/);
  });
});
