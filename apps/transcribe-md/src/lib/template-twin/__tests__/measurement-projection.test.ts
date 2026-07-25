// ============================================================================
// STAGE 2 — measurements project to numeric EncounterFacts.
// ----------------------------------------------------------------------------
// matchMeasurementFact requires a fact with a real `number` and a real
// `laterality`. L3's SOAP-shaped schema could never produce one, which is why
// every measurement cell was refused `no_supporting_fact` for four sessions.
// The matcher is untouched — its requirements are simply satisfiable now.
//
// Unit normalization lives HERE, not in the extractor: asking a language model
// to convert is asking it to be a calculator. L3 records what was said; this
// converts deterministically and keeps the spoken form in the evidence quote.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { normalizeMeasurement, projectEncounterFacts } from '../encounter-facts';

const project = (measurements: unknown[], contextText: string) =>
  projectEncounterFacts({
    mode: 'text',
    contextText,
    entities: { measurements } as never,
    asrQuality: 'unknown',
  });

const M = (over: Record<string, unknown> = {}) => ({
  segment: 'great saphenous vein at the saphenofemoral junction',
  laterality: 'right',
  metric: 'diameter',
  value: 7,
  unit: 'millimeters',
  sourceSpan: 'Right great saphenous vein at the saphenofemoral junction: diameter 7 millimeters',
  ...over,
});

describe('unit normalization (deterministic, not the model)', () => {
  it.each([
    [7, 'millimeters', 7, 'mm'],
    [0.62, 'centimeters', 6.2, 'mm'],
    [5, 'mm', 5, 'mm'],
    [2.4, 'seconds', 2.4, 'seconds'],
    [1800, 'milliseconds', 1.8, 'seconds'],
    [900, 'ms', 0.9, 'seconds'],
  ])('%s %s -> %s %s', (v, u, wantV, wantU) => {
    expect(normalizeMeasurement(v as number, u as string)).toEqual({ value: wantV, unit: wantU });
  });

  it('kills float noise (0.62 cm must be 6.2, not 6.199999999999999)', () => {
    expect(normalizeMeasurement(0.62, 'cm').value).toBe(6.2);
  });

  it('passes an unrecognised unit through rather than guessing', () => {
    // Degrades to "no match" downstream, never to a wrong number.
    expect(normalizeMeasurement(3, 'furlongs')).toEqual({ value: 3, unit: 'furlongs' });
  });
});

describe('projection', () => {
  const CTX = 'Right great saphenous vein at the saphenofemoral junction: diameter 7 millimeters';

  it('emits a fact carrying a real number and laterality', () => {
    const [fact] = project([M()], CTX);
    expect(fact).toBeDefined();
    expect(fact!.number).toBe(7);
    expect(fact!.unit).toBe('mm');
    expect(fact!.laterality).toBe('right');
    expect(fact!.polarity).toBe('affirmed');
  });

  it('anchors on the REAL source span', () => {
    const [fact] = project([M()], CTX);
    expect(fact!.evidenceQuote).toBe(M().sourceSpan);
    expect(fact!.evidenceAnchorIds[0]).toMatch(/^ttev_[a-f0-9]{24}$/);
    expect(fact!.factId).toMatch(/^ttfact_[a-f0-9]{24}$/);
  });

  it('converts at projection time, keeping the spoken form as evidence', () => {
    const span = 'Right SSV at the SPJ measures 0.62 centimeters';
    const [fact] = project(
      [M({ value: 0.62, unit: 'centimeters', sourceSpan: span })],
      span,
    );
    expect(fact!.number).toBe(6.2);
    expect(fact!.unit).toBe('mm');
    // The conversion stays auditable against what was actually said.
    expect(fact!.evidenceQuote).toContain('0.62 centimeters');
  });

  it('keeps the two legs DISTINCT even at the same value and segment', () => {
    // The exact clinical hazard: a right-leg number landing in a left-leg row.
    const span = 'bilateral GSV at the SFJ diameter 7 millimeters';
    const facts = project(
      [M({ laterality: 'right', sourceSpan: span }), M({ laterality: 'left', sourceSpan: span })],
      span,
    );
    expect(facts).toHaveLength(2);
    expect(new Set(facts.map((f) => f.factId)).size).toBe(2);
    expect(new Set(facts.map((f) => f.laterality))).toEqual(new Set(['left', 'right']));
  });

  it('gives each metric its own fact for one segment', () => {
    const span = 'GSV at the SFJ: diameter 7 millimeters, reflux 2.4 seconds';
    const facts = project(
      [M({ sourceSpan: span }), M({ metric: 'reflux_time', value: 2.4, unit: 'seconds', sourceSpan: span })],
      span,
    );
    expect(facts).toHaveLength(2);
    expect(facts.map((f) => f.concept).sort()).toEqual([
      'measurement.diameter',
      'measurement.reflux_time',
    ]);
    expect(facts.find((f) => f.concept === 'measurement.reflux_time')!.number).toBe(2.4);
  });

  it('skips a malformed measurement rather than emitting a bad number', () => {
    expect(project([M({ value: Number.NaN })], CTX)).toEqual([]);
    expect(project([M({ value: 'seven' })], CTX)).toEqual([]);
  });

  it('a SOAP encounter (no measurements) projects nothing extra', () => {
    expect(project([], 'Follow-up for hypertension.')).toEqual([]);
  });
});
