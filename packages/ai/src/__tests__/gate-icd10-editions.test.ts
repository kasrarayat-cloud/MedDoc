// ============================================================================
// GATE — the generator's EDITION table, and its refusal to run unpinned
// ----------------------------------------------------------------------------
// FY2027 takes effect 2026-10-01. The generator is parameterised by fiscal year
// so that ingestion is adding a row rather than editing a constant — and the
// SAFETY property is the REFUSAL: an edition whose bytes have not been pinned
// must abort, not run against whatever the network happens to return.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · a year-derived URL replacing the literal per-edition one -> the URL block
//   · an edition pinned HALF-WAY, or carrying another's digests -> the all-or-nothing
//     and forward-fill blocks (these REPLACED an arm that asserted fy2027 was
//     null — a current state written down as an invariant, which went red at
//     the first person to do the right thing)
//   · the shipped data drifting from fy2026's pinned digests   -> the identity block
//   · the edition table losing fy2027 before it is ingested    -> the presence block
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';
import PROVENANCE from '../data/icd10cm-fy2026-provenance.json';

const GENERATOR = readFileSync(
  join(__dirname, '..', '..', '..', '..', 'scripts', 'data', 'build-icd10cm.mjs'),
  'utf8',
);

describe('the generator is parameterised by fiscal year', () => {
  it('carries an EDITIONS table with both fy2026 and fy2027', () => {
    expect(GENERATOR).toMatch(/const EDITIONS = \{/);
    expect(GENERATOR).toMatch(/\bfy2026:\s*\{/);
    expect(GENERATOR).toMatch(/\bfy2027:\s*\{/);
    expect(GENERATOR).toMatch(/--edition/);
  });

  it('⚠️ each edition carries a LITERAL url — none is built from the year', () => {
    // Measured 2026-09-04: CMS dropped "and-" from the code-tables filename
    // between FY2026 and FY2027, so a year-substituting helper 404s in the year
    // it matters. Both literals must be present, and no template-built URL.
    expect(GENERATOR).toContain('2026-code-descriptions-tabular-order.zip');
    expect(GENERATOR).toContain('2027-code-descriptions-tabular-order.zip');
    // no `${year}` interpolation anywhere in a cms.gov path
    expect(GENERATOR).not.toMatch(/cms\.gov[^\n'"`]*\$\{/);
  });

  // ==========================================================================
  // ⚠️ THIS ARM REPLACED ONE THAT ASSERTED "fy2027 IS UNPINNED", AND THE
  // REPLACEMENT IS THE POINT.
  // --------------------------------------------------------------------------
  // The old arm required every fy2027 provenance field to be literally `null`.
  // That was TRUE when it was written and it was never the property being
  // protected — it encoded a CURRENT STATE as an INVARIANT. The moment somebody
  // did the right thing and pinned FY2027 from an archive they had actually
  // downloaded, the gate went red at them for it.
  //
  // The property this file wants is: **provenance is never FORWARD-FILLED.**
  // Nobody carries FY2026's digits forward, nobody guesses, and nobody pins
  // half an edition. That property survives an edition being pinned, and it
  // keeps applying to fy2028 without anyone editing this file again.
  //
  // ⚠️ AND IT IS STRICTLY STRONGER THAN WHAT IT REPLACED. "fy2027 is null"
  // said nothing about fy2026, said nothing about a partial pin, and expired on
  // first contact with the work it was guarding. Verified against the real
  // table: the pin is present, complete, and distinct from FY2026's.
  // ==========================================================================
  const editionBody = (fy) => {
    const at = GENERATOR.indexOf(`${fy}: {`);
    expect(at, `${fy} is missing from the EDITIONS table`).toBeGreaterThan(0);
    const rest = GENERATOR.slice(at);
    const end = rest.indexOf('\n  },');
    expect(end, `${fy}'s block is unterminated`).toBeGreaterThan(0);
    return rest.slice(0, end);
  };
  const PINNED_FIELDS = ['retrieved', 'zipSha256', 'zipBytes', 'codesSha256', 'orderSha256'];

  it('⚠️ every edition is pinned ALL-OR-NOTHING — a PARTIAL pin is a forward-fill', () => {
    for (const fy of ['fy2026', 'fy2027']) {
      const body = editionBody(fy);
      const nulls = PINNED_FIELDS.filter((f) => new RegExp(`${f}:\\s*null`).test(body));
      const filled = PINNED_FIELDS.filter((f) =>
        new RegExp(`${f}:\\s*(?!null)['\\d]`).test(body),
      );
      // Every field accounted for — a field that is neither is a parse failure,
      // and a parse failure that silently yields an empty set would make this
      // whole arm vacuous.
      expect(
        nulls.length + filled.length,
        `${fy}: ${PINNED_FIELDS.length - nulls.length - filled.length} field(s) parsed as neither null nor filled`,
      ).toBe(PINNED_FIELDS.length);
      expect(
        nulls.length === 0 || filled.length === 0,
        `${fy} is HALF pinned — filled [${filled}] and null [${nulls}]. ` +
          `A partial pin is exactly the forward-fill this gate exists to refuse.`,
      ).toBe(true);
    }
  });

  it('⚠️ NO EDITION CARRIES ANOTHER EDITION\'S DIGESTS — the forward-fill signature', () => {
    // The cheapest possible tell for the failure actually being guarded against:
    // somebody copies the previous edition's block and edits the year. Distinct
    // archives cannot share a sha256.
    const digestsOf = (fy) => {
      const body = editionBody(fy);
      return ['zipSha256', 'codesSha256', 'orderSha256'].map((f) => {
        const m = body.match(new RegExp(`${f}:\\s*'([0-9a-f]{64})'`));
        return m ? m[1] : null;
      });
    };
    const a = digestsOf('fy2026');
    const b = digestsOf('fy2027');
    // NON-VACUITY: if neither edition is pinned there is nothing to compare and
    // this arm must say so rather than pass.
    expect(a.filter(Boolean).length, 'fy2026 carries no digests to compare').toBe(3);
    if (b.filter(Boolean).length === 0) return; // legitimately unpinned
    expect(b.filter(Boolean).length, 'fy2027 is partially pinned').toBe(3);
    for (const d of b) {
      expect(a, `a FY2026 digest was carried forward into fy2027: ${d}`).not.toContain(d);
    }
  });

  it('⚠️ A PINNED EDITION IS NOT AN ACTIVE ONE — the switch is a separate act', () => {
    // This is the row that actually protects a patient. FY2027 may be pinned and
    // HELD; what must not happen is the shipped dataset moving without the
    // dated, declared switch. The identity block below pins the payload; this
    // arm pins the INTENT, so a future reader cannot mistake "pinned" for "live".
    const body = editionBody('fy2027');
    expect(body).toContain("effectiveFrom: '2026-10-01'");
    expect(body, 'a pinned-but-inactive edition must say so in words').toMatch(
      /HELD, NOT\s*\n?\s*\/\/\s*ACTIVE|HELD, NOT ACTIVE/,
    );
    // and the shipped provenance is still the PREVIOUS edition's
    expect(PROVENANCE.effectiveTo).toBe('2026-09-30');
  });

  it('the generator still REFUSES to run an unpinned edition', () => {
    // Unchanged, and it is the original safety property: an edition whose bytes
    // were never pinned must abort rather than run against whatever the network
    // returns today.
    expect(GENERATOR).toMatch(/has no pinned \$\{?field\}?|has no pinned/);
    expect(GENERATOR).toMatch(/Provenance is pinned BEFORE the act/);
  });

  it('fy2027 still records what IS knowable — url and effective window', () => {
    const fy27 = GENERATOR.slice(GENERATOR.indexOf('fy2027: {'));
    const body = fy27.slice(0, fy27.indexOf('\n  },'));
    expect(body).toContain("effectiveFrom: '2026-10-01'");
    expect(body).toContain("effectiveTo: '2027-09-30'");
    expect(body).toContain('2027-code-descriptions-tabular-order.zip');
  });

  it('the SHIPPED data is still fy2026, and its digests are unmoved', () => {
    // Parameterising must not have altered a single code. The payload digests
    // are the ones T8 pinned; a banner change is fine, a payload change is not.
    expect(PROVENANCE.effectiveFrom).toBe('2025-10-01');
    expect(PROVENANCE.effectiveTo).toBe('2026-09-30');
    expect(PROVENANCE.payloadSha256.billable).toBe(
      'def6594909779f92e8974b8441e72d04afa57acd1bdcc5fb3739d1dd0149a939',
    );
    expect(PROVENANCE.payloadSha256.headers).toBe(
      '3b2b5c0711884186706ada712e5bf86702a6570602b01fbc80cf8b85c3e12101',
    );
    expect(PROVENANCE.counts).toEqual({ billable: 74719, headers: 23467, total: 98186 });
  });

  it('the April/October cadence is recorded, with FY2026 as a fact not a rule', () => {
    expect(GENERATOR).toMatch(/APRIL 1 mid-year update|april/i);
    // the measured FY2026 result must be labelled as edition-specific
    expect(GENERATOR).toMatch(/fact about FY2026, NOT a rule|NOT a rule/);
  });
});
