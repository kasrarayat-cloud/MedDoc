import { describe, expect, it } from 'vitest';

import {
  parseExplicitNumberAndUnit,
  projectEncounterFacts,
} from '..';

describe('projectEncounterFacts', () => {
  it('projects deterministic evidence-addressable facts for all input modes', () => {
    const contextText = [
      'Left knee pain began three days ago.',
      'Taking syntheticmed 10 mg by mouth daily.',
      'No known allergies.',
    ].join('\n');
    const input = {
      mode: 'conversation' as const,
      contextText,
      asrQuality: 'high' as const,
      entities: {
        hpi: {
          location: 'left knee',
          duration: 'three days',
          evidence_quote: 'Left knee pain began three days ago.',
          speaker: 'Patient',
          timestamp: 12,
        },
        medications: [
          {
            name: 'syntheticmed',
            dose: '10 mg',
            route: 'by mouth',
            frequency: 'daily',
            evidence_quote: 'Taking syntheticmed 10 mg by mouth daily.',
            speaker: 'Patient',
            timestamp: 18,
          },
        ],
        allergies: [
          {
            substance: 'No known allergies',
            evidence_quote: 'No known allergies.',
            speaker: 'Patient',
            timestamp: 25,
          },
        ],
      },
    };

    const first = projectEncounterFacts(input);
    const second = projectEncounterFacts(input);
    expect(first).toEqual(second);
    expect(first.every((fact) => fact.factId.startsWith('ttfact_'))).toBe(true);
    expect(first.every((fact) => fact.evidenceAnchorIds.length > 0)).toBe(true);

    const location = first.find((fact) => fact.concept === 'hpi.location');
    expect(location).toMatchObject({
      value: 'left knee',
      laterality: 'left',
      audioTimestampSeconds: 12,
      sourceTranscriptOffsets: {
        start: 0,
        end: 'Left knee pain began three days ago.'.length,
      },
      quality: { asr: 'high', evidence: 'direct' },
    });

    const medicationFacts = first.filter((fact) =>
      fact.concept.startsWith('medication.'),
    );
    expect(medicationFacts).toHaveLength(4);
    expect(new Set(medicationFacts.flatMap((fact) => fact.evidenceAnchorIds)).size).toBe(1);
    expect(
      medicationFacts.find((fact) => fact.concept === 'medication.dose'),
    ).toMatchObject({ number: 10, unit: 'mg' });

    const allergy = first.find((fact) => fact.concept === 'allergy.substance');
    expect(allergy?.polarity).toBe('denied');
  });

  it('does not fabricate an offset and marks unclear ASR for review', () => {
    const [fact] = projectEncounterFacts({
      mode: 'dictation',
      contextText: 'Different synthetic source text.',
      asrQuality: 'high',
      entities: {
        assessment_discussed: [
          {
            finding: 'unclear term',
            evidence_quote: '[unclear in recording]',
            speaker: 'Doctor',
            timestamp: 4,
          },
        ],
      },
    });
    expect(fact.sourceTranscriptOffsets).toBeNull();
    expect(fact.quality).toEqual({ asr: 'review', evidence: 'unclear' });
  });

  it('parses only explicit standalone numbers and units', () => {
    expect(parseExplicitNumberAndUnit('12.5 mg')).toEqual({
      number: 12.5,
      unit: 'mg',
    });
    expect(parseExplicitNumberAndUnit(7)).toEqual({ number: 7, unit: null });
    expect(parseExplicitNumberAndUnit('about 12 mg')).toEqual({
      number: null,
      unit: null,
    });
    expect(parseExplicitNumberAndUnit('twelve mg')).toEqual({
      number: null,
      unit: null,
    });
  });
});
