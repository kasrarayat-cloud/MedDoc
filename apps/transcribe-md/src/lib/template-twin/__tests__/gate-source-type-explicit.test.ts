// ============================================================================
// EVERY SITE THAT *CONSTRUCTS* A SemanticMapping CLASSIFIES IT EXPLICITLY.
//
// ⚠️ WHY THIS EXISTS. `SemanticMappingSchema.sourceType` carries
// `.default('extraction')`. A default is a fine safety net and a terrible
// classification: `fallbackSemanticMappings` omitted the field entirely, so the
// provider-failure path silently labelled EVERY field `extraction` — including
// the enumerated dropdowns whose values come from the note's constrained pick,
// and the manual fields that have no clinical concept BY CONSTRUCTION.
//
// That is not cosmetic. `MAPPINGS_NOT_READY` demands a concept for every
// NON-manual field, so a manual field mislabelled `extraction` is permanently
// unsatisfiable — and `concept-registry.ts` already records what the enumerated
// half costs: classifying those as `extraction` "left fourteen of them
// permanently blank on every real visit and blocked the native export".
//
// ⚠️ AND REMOVING THE DEFAULT WAS EVALUATED AND DECLINED, ON EVIDENCE — see the
// comment at the default in `ir.ts`. Six re-parse sites feed the FILL path, so
// removal turns a silent mislabel into a throw while filling a doctor's
// document. This test is what makes a forgetful future path fail LOUDLY at
// author time instead, which is the same goal at a much better moment.
// ============================================================================
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const DIR = path.resolve(__dirname, '..');

/**
 * A CONSTRUCTING site is `SemanticMappingSchema.parse({` — an object literal.
 * A re-parse (`parse(mapping)`, `parse(raw)`) forwards a value that already
 * carries its classification and is deliberately NOT in scope: those are the
 * fill-path sites the default protects.
 */
function constructingSites(src: string): { index: number; body: string }[] {
  const out: { index: number; body: string }[] = [];
  const re = /SemanticMappingSchema\.parse\(\{/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    // Walk to the matching brace so the body is the literal, not a fixed window
    // — a fixed window is how a field 40 lines down gets missed.
    let depth = 0;
    let i = m.index + m[0].length - 1;
    for (; i < src.length; i += 1) {
      if (src[i] === '{') depth += 1;
      else if (src[i] === '}') {
        depth -= 1;
        if (depth === 0) break;
      }
    }
    out.push({ index: m.index, body: src.slice(m.index, i + 1) });
  }
  return out;
}

const FILES = ['semantic-mapping/index.ts'];

describe('sourceType is classified, never defaulted, at every constructing site', () => {
  it('the matcher finds constructing sites and can tell them from re-parses', () => {
    // POSITIVE CONTROLS. A guard whose only job is to go red is worthless if
    // its matcher matches nothing — and this one must also NOT flag the
    // re-parse sites the default deliberately protects.
    const sample = 'SemanticMappingSchema.parse({ a: 1, b: { c: 2 } });';
    expect(constructingSites(sample)).toHaveLength(1);
    expect(constructingSites(sample)[0]!.body.endsWith('}')).toBe(true);
    expect(constructingSites('SemanticMappingSchema.parse(mapping)')).toHaveLength(0);
    expect(constructingSites('SemanticMappingSchema.safeParse(raw)')).toHaveLength(0);
  });

  it('the scan is not vacuous — the proposer file really does construct', () => {
    const src = readFileSync(path.join(DIR, 'semantic-mapping/index.ts'), 'utf8');
    expect(
      constructingSites(src).length,
      'no constructing site found — the matcher is broken, not the code',
    ).toBeGreaterThanOrEqual(2);
  });

  it('EVERY constructing site sets sourceType explicitly', () => {
    const offenders: string[] = [];
    for (const rel of FILES) {
      const src = readFileSync(path.join(DIR, rel), 'utf8');
      constructingSites(src).forEach((site, n) => {
        // Strip comments so PROSE mentioning sourceType cannot satisfy this —
        // the substring trap, which this repository has paid for repeatedly and
        // which would be especially easy here, since the explanation above the
        // field names it.
        const code = site.body
          .replace(/\/\*[\s\S]*?\*\//g, ' ')
          .replace(/^\s*\/\/.*$/gm, ' ');
        // ⚠️ `[:,]` ADMITS THE ES6 SHORTHAND, AND THAT IS NOT A LOOSENING.
        // The claim is that the constructing site NAMES `sourceType` rather
        // than letting the schema default supply it. `{ sourceType }` names it
        // exactly as `{ sourceType: x }` does, and #247's proposer uses the
        // shorthand because the value is read once above and consumed twice —
        // reading it a second time would be two callers of one classifier.
        // Comments are already stripped, so prose still cannot satisfy this.
        if (!/\bsourceType\s*[:,]/.test(code)) {
          offenders.push(`${rel} :: constructing site #${n + 1}`);
        }
      });
    }
    expect(
      offenders,
      'a site constructs a SemanticMapping without classifying it. The schema ' +
        'default would silently label it `extraction`, which is a WRONG answer ' +
        'for enumerated and manual fields — call classifyFieldSource(label, field).',
    ).toEqual([]);
  });
});
