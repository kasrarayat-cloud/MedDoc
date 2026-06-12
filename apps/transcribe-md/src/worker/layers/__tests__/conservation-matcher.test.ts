// ============================================================================
// Conservation / lane-capture matcher — pinned on the run-3 forensic
// evidence (day2_consultation05, the TIA-suspect Gate-2 max-12 case): the
// completeness judge listed facts as omissions that were literally in the
// lane it was shown. These fixtures are the REAL judge "omissions" and the
// REAL lane items from primock57-fullchain-fabrication-20260612T014805Z.json.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  conservationCheck,
  laneCaptured,
  bodyCaptured,
} from '../../../../scripts/eval/conservation-matcher';

// The run-3 lane for day2_consultation05 (texts abridged to the matched
// prefixes the JSON shows; section labels as captured).
const RUN3_LANE = [
  {
    text: '**HPI:** Per patient, a 32-year-old male reports symptoms beginning approximately a month ago',
    section: 'Subjective',
  },
  {
    text: '- Aspirin 75 mg once a day (patient-initiated based on something read on the Internet, not previously reviewed by a GP).',
    section: 'Medications',
  },
  { text: '- Penicillin (reaction not stated).', section: 'Drug Allergies' },
  { text: '- Smoking: Non-smoker.', section: 'Social History' },
  { text: '- Lives with his wife.', section: 'Social History' },
  {
    text: '- Neurological: Per patient, pins and needles in right hand, right arm weakness, leg weakness',
    section: 'Review of Systems',
  },
  {
    text: '- Ophthalmological: Per patient, no clear visual problems; wears glasses.',
    section: 'Review of Systems',
  },
  {
    text: '5. PALS and hospital contact number to be added to the consultation notes so the patient can chase the appointment.',
    section: 'Plan',
  },
];

describe('laneCaptured — the run-3 judge-blindness patterns', () => {
  it('"Allergy to penicillin" IS captured by lane item "- Penicillin (reaction not stated)." under section Drug Allergies', () => {
    expect(laneCaptured('Allergy to penicillin', RUN3_LANE)).toBe(true);
  });

  it('"Aspirin 75 mg once daily, self-initiated after reading on the internet" IS captured by the lane aspirin item', () => {
    expect(
      laneCaptured(
        'Aspirin 75 mg once daily, self-initiated after reading on the internet, no GP has counselled him',
        RUN3_LANE
      )
    ).toBe(true);
  });

  it('"Patient lives with his wife" IS captured (the verbatim-blindness case)', () => {
    expect(laneCaptured('Patient lives with his wife', RUN3_LANE)).toBe(true);
  });

  it('"Patient is a non-smoker" IS captured', () => {
    expect(laneCaptured('Patient is a non-smoker', RUN3_LANE)).toBe(true);
  });

  it('"Patient is a 32-year-old male" IS captured by the HPI lane item', () => {
    expect(laneCaptured('Patient is a 32-year-old male', RUN3_LANE)).toBe(true);
  });

  it('"Patient works as a doctor in plastic surgery" is NOT captured — a true omission stays an omission', () => {
    expect(
      laneCaptured('Patient works as a doctor in plastic surgery', RUN3_LANE)
    ).toBe(false);
  });

  it('"Clinician noted the urgency and that TIA needs to be excluded" is NOT captured', () => {
    expect(
      laneCaptured(
        'Clinician noted the urgency and that despite the patient young age TIA needs to be excluded',
        RUN3_LANE
      )
    ).toBe(false);
  });

  it('digits must match exactly — "Aspirin 300 mg" is NOT captured by the 75 mg item', () => {
    expect(
      laneCaptured('Aspirin 300 mg once a day patient initiated', [
        RUN3_LANE[1],
      ])
    ).toBe(false);
  });

  it('empty lane captures nothing', () => {
    expect(laneCaptured('Allergy to penicillin', [])).toBe(false);
  });
});

describe('bodyCaptured', () => {
  const BODY = [
    '## Subjective',
    'Per patient, episodes of right-sided weakness lasting minutes.',
    'Symptoms resolve completely between episodes; asymptomatic today.',
    '## Plan',
    'Urgent TIA clinic referral submitted.',
  ].join('\n');

  it('finds a fact stated on one body line', () => {
    expect(
      bodyCaptured('Urgent referral to the TIA clinic submitted', BODY)
    ).toBe(true);
  });

  it('finds a fact wrapped across two consecutive lines', () => {
    expect(
      bodyCaptured(
        'episodes of right-sided weakness which resolve completely',
        BODY
      )
    ).toBe(true);
  });

  it('does NOT false-conserve via token scatter across NON-adjacent lines', () => {
    // 2 tokens from the Subjective line + 2 from the Plan line + 1 nowhere:
    // no single line or adjacent pair reaches the 0.5 coverage threshold.
    expect(
      bodyCaptured('episodes of weakness urgent chest referral', BODY)
    ).toBe(false);
  });
});

describe('conservationCheck — silent loss only', () => {
  const BASELINE = [
    '## Medications',
    '- Aspirin 75 mg once daily (self-initiated).',
    '## Allergies',
    '- Penicillin allergy.',
    '## Social History',
    '- Works as a doctor in plastic surgery.',
    '- [not documented]',
  ].join('\n');

  it('lane-captured + body-captured lines are conserved; truly lost lines are violations', () => {
    const r = conservationCheck(
      BASELINE,
      '## Medications\nNothing relevant retained.',
      RUN3_LANE
    );
    expect(r.total).toBe(3); // [not documented] + headers skipped
    expect(r.conserved).toBe(2); // aspirin + penicillin via lane
    expect(r.violations).toEqual([
      '- Works as a doctor in plastic surgery.',
    ]);
  });

  it('zero violations when everything is in the body', () => {
    const r = conservationCheck(
      BASELINE,
      [
        'Aspirin 75 mg once daily self-initiated.',
        'Penicillin allergy recorded.',
        'Works as a doctor in plastic surgery.',
      ].join('\n'),
      []
    );
    expect(r.violations).toEqual([]);
    expect(r.conserved).toBe(3);
  });
});
