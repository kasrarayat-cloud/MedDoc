// ============================================================================
// The bridge cites REAL evidence, or it writes nothing.
// ----------------------------------------------------------------------------
// The defect this pins: bridgeTemplateFill marked bridged values
// `status: 'supported'` while citing a placeholder fact id
// (ttfact_000000000000000000000000) and a placeholder anchor. Neither existed
// in the fact set, so validateTemplateTwin rejected every bridged value
// (SOURCE_FACT_MISSING / EVIDENCE_ANCHOR_UNTRACEABLE / ASSERTION_NOT_SUPPORTED).
// prepareTemplateTwinFill is shared with the VISIT path, so those values were
// rejected there too — the bridge never actually filled a rendered document.
//
// The invariant now: every citation a bridged value carries must resolve to a
// fact that is really in the set. Anything else is blank, with a named reason.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { citationOf, matchMeasurementFact, matchPickFact } from '../bridge-evidence';
import type { EncounterFact } from '../ir';

function fact(over: Partial<EncounterFact> & { factId: string }): EncounterFact {
  return {
    sourceType: 'encounter_evidence',
    concept: 'gsv sfj reflux',
    value: 2.4,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'right',
    number: 2.4,
    unit: 'sec',
    speaker: 'Doctor',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['anchor-1'],
    evidenceQuote: 'reflux two point four on the right',
    quality: { asr: 'unknown', evidence: 'direct' },
    ...over,
  } as EncounterFact;
}

const REAL_ID = 'ttfact_aaaaaaaaaaaaaaaaaaaaaaaa';
const PLACEHOLDER = `ttfact_${'0'.repeat(24)}`;

describe('measurement matching', () => {
  it('cites the matched fact, with ITS id and anchor', () => {
    const f = fact({ factId: REAL_ID, evidenceAnchorIds: ['anchor-sfj'] });
    const r = matchMeasurementFact({ value: '2.4', segmentLabel: 'GSV at the SFJ', facts: [f] });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    const cite = citationOf(r.match);
    expect(cite.sourceFactIds).toEqual([REAL_ID]);
    expect(cite.evidenceAnchorIds).toEqual(['anchor-sfj']);
    // The regression, stated directly.
    expect(cite.sourceFactIds).not.toContain(PLACEHOLDER);
  });

  it('takes laterality FROM the fact, not from row position', () => {
    const f = fact({ factId: REAL_ID, laterality: 'left' });
    const r = matchMeasurementFact({ value: '2.4', segmentLabel: 'GSV at the SFJ', facts: [f] });
    expect(r.ok && r.match.laterality).toBe('left');
  });

  it('CANARY: a value with no supporting fact does not get cited', () => {
    // 9.9 was never dictated. Under the old bridge this became a "supported"
    // measurement with a minted citation — an unevidenced number in a document.
    const r = matchMeasurementFact({
      value: '9.9',
      segmentLabel: 'GSV at the SFJ',
      facts: [fact({ factId: REAL_ID })],
    });
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('no_supporting_fact');
  });

  it('refuses when two sides claim the same number and segment', () => {
    // Guessing here would put a right-leg measurement in a left-leg row.
    const r = matchMeasurementFact({
      value: '2.4',
      segmentLabel: 'GSV at the SFJ',
      facts: [
        fact({ factId: REAL_ID, laterality: 'right' }),
        fact({ factId: 'ttfact_bbbbbbbbbbbbbbbbbbbbbbbb', laterality: 'left' }),
      ],
    });
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('ambiguous_laterality');
  });

  it('requires segment congruence, not just a matching number', () => {
    const r = matchMeasurementFact({
      value: '2.4',
      segmentLabel: 'SSV at the popliteal fossa',
      facts: [fact({ factId: REAL_ID, concept: 'gsv sfj reflux' })],
    });
    expect(r.ok).toBe(false);
  });

  it('ignores denied facts — a negated finding is not support', () => {
    const r = matchMeasurementFact({
      value: '2.4',
      segmentLabel: 'GSV at the SFJ',
      facts: [fact({ factId: REAL_ID, polarity: 'denied' })],
    });
    expect(r.ok).toBe(false);
  });
});

describe('pick matching', () => {
  const dx = 'Chronic venous hypertension with other complications of bilateral lower extremities';

  it('cites the entailing fact', () => {
    const f = fact({
      factId: REAL_ID,
      concept: 'assessment',
      value: dx,
      number: null,
      laterality: 'bilateral',
    });
    const r = matchPickFact({ optionText: dx, facts: [f] });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(citationOf(r.match).sourceFactIds).toEqual([REAL_ID]);
  });

  it('CANARY: a pick nothing supports stays uncited', () => {
    const r = matchPickFact({
      optionText: dx,
      facts: [fact({ factId: REAL_ID, concept: 'assessment', value: 'something else entirely' })],
    });
    expect(r.ok).toBe(false);
  });

  it('a partial overlap is not entailment', () => {
    // "lower extremities" alone must not satisfy the bilateral chronic-venous
    // option — that would silently upgrade a vaguer finding into a diagnosis.
    const r = matchPickFact({
      optionText: dx,
      facts: [fact({ factId: REAL_ID, concept: 'assessment', value: 'lower extremities' })],
    });
    expect(r.ok).toBe(false);
  });
});

describe('MUTATION GUARD — a stamper must not pass', () => {
  it('no bridge module mints a placeholder citation', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    for (const file of ['bridge-fill.ts', 'picks-bridge.ts', 'bridge-evidence.ts']) {
      const src = readFileSync(join(__dirname, '..', file), 'utf-8');
      expect(
        src,
        `${file} mints a placeholder fact id — bridged values must cite a fact ` +
          'that exists in the fact set, or be left blank'
      ).not.toMatch(/ttfact_\$\{'0'\.repeat\(24\)\}/);
      expect(src).not.toMatch(/evidenceAnchorIds:\s*\['(choice-slot-pick|table-cell-measurement)'\]/);
    }
  });

  it('the MEASUREMENT bridge routes its citation through citationOf', () => {
    // A stamper mutant that reintroduces a literal citation would bypass this.
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    const src = readFileSync(join(__dirname, '..', 'bridge-fill.ts'), 'utf-8');
    expect(src, 'bridge-fill.ts no longer cites via citationOf').toContain('citationOf(');
  });

  it('the PICKS bridge mints provenance only through the named class', () => {
    // Picks legitimately do not cite an extracted fact — the options are
    // protocol language no extractor emits, so requiring entailment left every
    // dropdown blank on every real visit. They cite the SELECTION instead,
    // through one auditable constructor whose identity includes the note
    // version. What must never come back is a hand-rolled citation object.
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    const src = readFileSync(join(__dirname, '..', 'picks-bridge.ts'), 'utf-8');
    expect(src).toContain('buildVerifiedNoteSelectionFact(');
    // The citation is taken FROM the built fact, never composed beside it.
    expect(src).toContain('sourceFactIds: [fact.factId]');
    expect(src).toContain('evidenceAnchorIds: [...fact.evidenceAnchorIds]');
    // And the facts leave the bridge — a citation to a fact that never reaches
    // the manifest is untraceable, which is where this whole class started.
    expect(src).toContain('facts.push(built.fact)');
  });
});
