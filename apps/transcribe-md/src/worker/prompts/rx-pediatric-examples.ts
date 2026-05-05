// ============================================================================
// L7c Rx drafting — pediatric few-shot examples (Fix-Pack 1, Q0-2)
// ----------------------------------------------------------------------------
// Audit Finding 01.1 — pediatric framing for the Rx drafting layer.
//
// Two anchor examples appended to the L7c system prompt when the patient is
// pediatric (ageYears < 18). They demonstrate:
//   1. The mg/kg/day calculation surfaced in evidence_quote
//   2. A within-range outcome (no warning) AND an at-the-ceiling outcome
//      (minor warning with the calculation in the message)
//
// These exemplars anchor the formatting AND the safety behavior; they do NOT
// substitute for the deterministic dose validator (that's wired separately
// per Sub-Agent 1 — Finding 06.5).
// ============================================================================

export const RX_PEDIATRIC_FEWSHOT_EXAMPLES = [
  'PEDIATRIC FEW-SHOT EXAMPLES — anchor your output formatting and the',
  'mg/kg/day surfacing pattern on these.',
  '',
  'EXAMPLE A — 4-year-old, 16 kg, acute otitis media. Plan: "amoxicillin',
  '250 mg TID for 10 days".',
  '',
  '  Calculation: 250 mg × 3 doses/day = 750 mg/day ÷ 16 kg = 47 mg/kg/day.',
  '  Pediatric AOM range for amoxicillin is 80-90 mg/kg/day (high-dose)',
  '  or 40-50 mg/kg/day (standard). 47 mg/kg/day is within the standard',
  '  range — no warning needed.',
  '',
  '  Output:',
  '  {',
  '    "prescriptions": [{',
  '      "drug": "Amoxicillin",',
  '      "strength": "250 mg",',
  '      "form": "suspension",',
  '      "sig": "Take 250 mg by mouth three times daily for 10 days",',
  '      "quantity": "150 mL",',
  '      "refills": "0",',
  '      "action": "new",',
  '      "evidence_quote": "amoxicillin 250 mg TID for 10 days (47 mg/kg/day at 16 kg)"',
  '    }],',
  '    "warnings": []',
  '  }',
  '',
  'EXAMPLE B — 6-year-old, 22 kg, fever. Plan: "ibuprofen 200 mg q6h prn',
  'fever".',
  '',
  '  Calculation: 200 mg × 4 doses/day = 800 mg/day ÷ 22 kg = 36 mg/kg/day.',
  '  Pediatric ibuprofen range is 30-40 mg/kg/day max. 36 mg/kg/day is at',
  '  the upper bound — emit a minor warning with the calculation in the',
  '  message so the doctor verifies before signing.',
  '',
  '  Output:',
  '  {',
  '    "prescriptions": [{',
  '      "drug": "Ibuprofen",',
  '      "strength": "200 mg",',
  '      "form": "tablet",',
  '      "sig": "Take 200 mg by mouth every 6 hours as needed for fever",',
  '      "quantity": "20",',
  '      "refills": "0",',
  '      "action": "new",',
  '      "evidence_quote": "ibuprofen 200 mg q6h prn fever (36 mg/kg/day at 22 kg)"',
  '    }],',
  '    "warnings": [{',
  '      "severity": "minor",',
  '      "rx_drug": "Ibuprofen",',
  '      "message": "Dose 36 mg/kg/day is at peds upper bound for ibuprofen (max 30-40 mg/kg/day); verify before signing.",',
  '      "evidence_quote": "ibuprofen 200 mg q6h prn fever"',
  '    }]',
  '  }',
].join('\n');
