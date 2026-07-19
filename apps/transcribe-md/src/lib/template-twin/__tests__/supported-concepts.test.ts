import { describe, expect, it } from 'vitest';

import { projectEncounterFacts } from '../encounter-facts';
import {
  TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION,
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  isSupportedTemplateTwinConcept,
  resolveSupportedTemplateTwinConcept,
  supportedProjectedSystemConcept,
  type TemplateTwinConceptProvider,
} from '../supported-concepts';

describe('Template Twin safe-alpha supported clinical concepts', () => {
  it('is versioned and accepts only the bounded SOAP projection taxonomy', () => {
    expect(TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION).toBe(
      'template-twin-soap-concepts/1.0.0',
    );
    expect(TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE).toBe(
      'TT_CONCEPT_UNSUPPORTED_V1',
    );
    expect(isSupportedTemplateTwinConcept('chief_complaint')).toBe(true);
    expect(isSupportedTemplateTwinConcept('medication.dose')).toBe(true);
    expect(isSupportedTemplateTwinConcept('ros.respiratory')).toBe(true);
    expect(isSupportedTemplateTwinConcept('exam.neurological')).toBe(true);
  });

  it.each([
    'gad_7.total_score',
    'pregnancy.status',
    'exam.monofilament',
    'measurement.custom_ankle_width',
    'test.synthetic_panel.result',
  ])('rejects unsupported specialty/custom concept %s', (concept) => {
    expect(isSupportedTemplateTwinConcept(concept)).toBe(false);
    expect(resolveSupportedTemplateTwinConcept(concept)).toBeNull();
  });

  it('normalizes only approved system aliases and refuses arbitrary systems', () => {
    expect(supportedProjectedSystemConcept('ros', 'Pulmonary')).toBe(
      'ros.respiratory',
    );
    expect(supportedProjectedSystemConcept('exam', 'Neuro')).toBe(
      'exam.neurological',
    );
    expect(supportedProjectedSystemConcept('exam', 'Monofilament')).toBeNull();
    expect(supportedProjectedSystemConcept('ros', 'Pregnancy')).toBeNull();
  });

  it('keeps unsupported extracted specialty detail out of the Twin fact set', () => {
    const quote = 'Synthetic test only: respiratory clear; monofilament finding stated.';
    const facts = projectEncounterFacts({
      mode: 'text',
      contextText: quote,
      entities: {
        exam_findings: [
          { system: 'Respiratory', finding: 'Clear', evidence_quote: quote },
          {
            system: 'Monofilament',
            finding: 'Synthetic intact finding',
            evidence_quote: quote,
          },
        ],
        tests_mentioned: [
          {
            test: 'Synthetic specialty panel',
            result_if_given: 'Synthetic result',
            evidence_quote: quote,
          },
        ],
      },
    });

    expect(facts.map((fact) => fact.concept)).toEqual([
      'exam.respiratory',
      'test.name',
    ]);
  });

  it('preserves a deliberate versioned extension seam without enabling it by default', () => {
    const extension: TemplateTwinConceptProvider = {
      providerVersion: 'template-aware-agent/synthetic-v2',
      resolveExact(concept) {
        return concept === 'gad_7.total_score'
          ? {
              concept,
              sourceEntityPath: 'templateAgent.gad7.total',
              physicianLabel: 'GAD-7 total score',
            }
          : null;
      },
    };

    expect(resolveSupportedTemplateTwinConcept('gad_7.total_score')).toBeNull();
    expect(
      resolveSupportedTemplateTwinConcept('gad_7.total_score', [extension]),
    ).toMatchObject({ concept: 'gad_7.total_score' });
  });
});
