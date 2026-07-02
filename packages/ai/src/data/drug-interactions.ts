// ============================================================================
// Deterministic drug–drug interaction floor (F-8, 2026-07-02).
// ----------------------------------------------------------------------------
// The QA matrix proved the product had NO drug-pair checking anywhere: the
// dose-range validator is single-drug-only, and the L7c LLM tiers
// interactions at `major` when it surfaces them at all (0/3 phrasings caught
// amlodipine + simvastatin 40 mg in the 2026-07-02 repro). This module is the
// deterministic, phrasing-independent floor: a SMALL curated table of
// well-established, high-severity pairs checked against the union of the
// visit's drafted prescriptions and the current-medication list.
//
// Curation rules (mirror dose-ranges.ts):
//   - Only pairs with an FDA-label or boxed-warning basis — cite it in
//     `basis`. This is a safety FLOOR, not a comprehensive DDI database
//     (that remains the Phase-7 RxNav/RxNorm follow-up noted in
//     dose-ranges.ts).
//   - Conservative severities: `critical` ONLY where the label states a
//     hard cap or the combination is a classic severe-harm pair; class
//     co-prescriptions that are sometimes intentional stay `major`.
//   - Caution-first: a dose-cap rule with an UNKNOWN dose emits `major`
//     ("verify the dose") rather than staying silent.
//
// Wired into worker layer 07c AFTER the per-drug validateRxDose loop; its
// warnings are ADDITIVE (this module never suppresses anything) and the
// critical-Rx sign gate consumes them through the existing severity field —
// the gate itself is untouched.
// ============================================================================

export type InteractionSeverity = 'critical' | 'major';

export interface InteractionMed {
  /** Drug name as extracted/drafted (any casing; brand or generic). */
  name: string;
  /** Parsed mg/day when known; null = unparseable/PRN/unknown. */
  doseMgPerDay: number | null;
  /** Where this med came from — drafted this visit vs current list. */
  source: 'draft' | 'current';
  /** Transcript evidence for the med, when available. */
  evidenceQuote?: string | null;
}

export interface InteractionWarning {
  code: 'RX_DRUG_PAIR_INTERACTION' | 'RX_DRUG_PAIR_DOSE_CAP';
  severity: InteractionSeverity;
  /** The drug the warning is "about" (shown on its Rx card when drafted). */
  primaryDrug: string;
  otherDrug: string;
  message: string;
  /** Rule id for tests/telemetry (stable). */
  ruleId: string;
}

interface PairRule {
  /** Stable id (tests + dedup). */
  id: string;
  /** Canonical lowercase names matching side A (generic + brands). */
  a: ReadonlyArray<string>;
  /** Canonical lowercase names matching side B. */
  b: ReadonlyArray<string>;
  /** Plain pair warning, or a dose cap applying to side A's mg/day. */
  kind: 'pair' | 'dose-cap-a';
  /** For dose-cap-a: side A must stay at or under this mg/day. */
  capMgPerDay?: number;
  severity: InteractionSeverity;
  /** Severity when a dose-cap rule cannot verify the dose (caution-first). */
  severityUnverifiable?: InteractionSeverity;
  message: (aName: string, bName: string, doseMgPerDay: number | null) => string;
  /** Reference basis — reviewer-facing, keep specific. */
  basis: string;
}

// ---------------------------------------------------------------------------
// Class member lists (lowercase; generics + common US brands). Deliberately
// short — only members with unambiguous class membership.
// ---------------------------------------------------------------------------
const SIMVASTATIN = ['simvastatin', 'zocor'];
const AMLODIPINE = ['amlodipine', 'norvasc'];
const NONDHP_CCB = ['verapamil', 'calan', 'verelan', 'diltiazem', 'cardizem', 'cartia', 'tiazac'];
const WARFARIN = ['warfarin', 'coumadin', 'jantoven'];
const NSAIDS = [
  'ibuprofen', 'advil', 'motrin',
  'naproxen', 'aleve', 'naprosyn',
  'diclofenac', 'voltaren',
  'meloxicam', 'mobic',
  'ketorolac', 'toradol',
  'indomethacin', 'indocin',
  'celecoxib', 'celebrex',
];
const ACE_INHIBITORS = [
  'lisinopril', 'zestril', 'prinivil',
  'enalapril', 'vasotec',
  'ramipril', 'altace',
  'benazepril', 'lotensin',
  'captopril', 'quinapril', 'accupril',
];
const POTASSIUM_RAISERS = [
  'spironolactone', 'aldactone',
  'eplerenone', 'inspra',
  'amiloride', 'triamterene', 'dyrenium',
  'potassium chloride', 'potassium citrate', 'klor-con', 'k-dur', 'k-tab', 'micro-k',
];
const METHOTREXATE = ['methotrexate', 'trexall', 'otrexup', 'rasuvo'];
const TRIMETHOPRIM = ['trimethoprim', 'trimethoprim-sulfamethoxazole', 'sulfamethoxazole-trimethoprim', 'bactrim', 'septra', 'co-trimoxazole', 'tmp-smx'];
const OPIOIDS = [
  'oxycodone', 'oxycontin', 'percocet', 'roxicodone',
  'hydrocodone', 'norco', 'vicodin',
  'morphine', 'ms contin',
  'hydromorphone', 'dilaudid',
  'fentanyl', 'duragesic',
  'codeine', 'tramadol', 'ultram',
  'methadone', 'oxymorphone',
];
const BENZODIAZEPINES = [
  'alprazolam', 'xanax',
  'diazepam', 'valium',
  'lorazepam', 'ativan',
  'clonazepam', 'klonopin',
  'temazepam', 'restoril',
  'chlordiazepoxide', 'librium',
];

const RULES: ReadonlyArray<PairRule> = [
  {
    id: 'simvastatin-amlodipine-cap20',
    a: SIMVASTATIN,
    b: AMLODIPINE,
    kind: 'dose-cap-a',
    capMgPerDay: 20,
    severity: 'critical',
    severityUnverifiable: 'major',
    message: (a, b, dose) =>
      dose !== null
        ? `${cap(a)} ${dose} mg/day exceeds the 20 mg/day maximum with ${b} — increased risk of myopathy/rhabdomyolysis. Reduce the ${a} dose or switch statins.`
        : `${cap(a)} is co-prescribed with ${b} — verify the ${a} dose does not exceed 20 mg/day (myopathy/rhabdomyolysis risk).`,
    basis: 'FDA simvastatin label (2011 dose-limitation update): max 20 mg/day with amlodipine.',
  },
  {
    id: 'simvastatin-nondhp-ccb-cap10',
    a: SIMVASTATIN,
    b: NONDHP_CCB,
    kind: 'dose-cap-a',
    capMgPerDay: 10,
    severity: 'critical',
    severityUnverifiable: 'major',
    message: (a, b, dose) =>
      dose !== null
        ? `${cap(a)} ${dose} mg/day exceeds the 10 mg/day maximum with ${b} — increased risk of myopathy/rhabdomyolysis. Reduce the ${a} dose or switch statins.`
        : `${cap(a)} is co-prescribed with ${b} — verify the ${a} dose does not exceed 10 mg/day (myopathy/rhabdomyolysis risk).`,
    basis: 'FDA simvastatin label (2011): max 10 mg/day with verapamil or diltiazem.',
  },
  {
    id: 'warfarin-nsaid',
    a: WARFARIN,
    b: NSAIDS,
    kind: 'pair',
    severity: 'critical',
    message: (a, b) =>
      `${cap(b)} with ${a} significantly increases major bleeding risk. Confirm the indication, consider alternatives, and document INR monitoring before signing.`,
    basis: 'FDA warfarin label: concurrent NSAIDs increase bleeding risk; classic severe DDI.',
  },
  {
    id: 'acei-potassium',
    a: ACE_INHIBITORS,
    b: POTASSIUM_RAISERS,
    kind: 'pair',
    severity: 'major',
    message: (a, b) =>
      `${cap(a)} with ${b} raises hyperkalemia risk — confirm the combination is intended and document potassium monitoring.`,
    basis: 'ACE-inhibitor labels: hyperkalemia risk with potassium-sparing diuretics/supplements.',
  },
  {
    id: 'methotrexate-trimethoprim',
    a: METHOTREXATE,
    b: TRIMETHOPRIM,
    kind: 'pair',
    severity: 'critical',
    message: (a, b) =>
      `${cap(b)} with ${a} can cause severe bone-marrow suppression (pancytopenia). Avoid the combination or verify hematologic monitoring is planned.`,
    basis: 'Methotrexate label contraindication-level interaction with trimethoprim (antifolate additive toxicity).',
  },
  {
    id: 'opioid-benzodiazepine',
    a: OPIOIDS,
    b: BENZODIAZEPINES,
    kind: 'pair',
    severity: 'major',
    message: (a, b) =>
      `${cap(a)} with ${b} — FDA boxed warning: concurrent opioid and benzodiazepine use risks profound sedation and respiratory depression. Confirm intent and document the rationale.`,
    basis: 'FDA 2016 boxed warning on concurrent opioid/benzodiazepine prescribing.',
  },
];

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Normalize a raw med name for matching: lowercase, strip trailing
 *  parentheticals and dose/formulation tails ("simvastatin 40 mg tablet"). */
function normName(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/\s*\([^)]*\)\s*$/, '')
    .replace(/\s+\d+(\.\d+)?\s*(mg|mcg|g|ml|units?)\b.*$/, '')
    .replace(/\s+(er|xr|sr|ir|xl|cr|odt|dr)\b.*$/, '')
    .trim();
}

function matches(names: ReadonlyArray<string>, med: InteractionMed): boolean {
  const n = normName(med.name);
  if (!n) return false;
  return names.some((cand) => n === cand || n.startsWith(`${cand} `));
}

/**
 * Check every rule against the visit's med set (drafted ∪ current). Emits at
 * most one warning per rule per (A-drug, B-drug) name pair. Pure + additive:
 * callers append these to whatever the LLM already produced.
 */
export function checkDrugInteractions(
  meds: ReadonlyArray<InteractionMed>
): InteractionWarning[] {
  const out: InteractionWarning[] = [];
  const seen = new Set<string>();
  for (const rule of RULES) {
    const sideA = meds.filter((m) => matches(rule.a, m));
    const sideB = meds.filter((m) => matches(rule.b, m));
    for (const aMed of sideA) {
      for (const bMed of sideB) {
        if (aMed === bMed) continue;
        const key = `${rule.id}|${normName(aMed.name)}|${normName(bMed.name)}`;
        if (seen.has(key)) continue;

        if (rule.kind === 'dose-cap-a') {
          // Prefer a verifiable dose from ANY matching side-A med (a drafted
          // row usually carries the parseable strength/sig).
          const dose = aMed.doseMgPerDay;
          if (dose !== null && dose <= (rule.capMgPerDay ?? Infinity)) {
            continue; // at/under the interaction-adjusted cap — compliant
          }
          seen.add(key);
          out.push({
            code: 'RX_DRUG_PAIR_DOSE_CAP',
            severity: dose !== null ? rule.severity : (rule.severityUnverifiable ?? rule.severity),
            primaryDrug: aMed.name,
            otherDrug: bMed.name,
            message: rule.message(normName(aMed.name), normName(bMed.name), dose),
            ruleId: rule.id,
          });
        } else {
          seen.add(key);
          out.push({
            code: 'RX_DRUG_PAIR_INTERACTION',
            severity: rule.severity,
            // For pair rules the drafted med (if any) is the actionable one.
            primaryDrug: (aMed.source === 'draft' ? aMed : bMed.source === 'draft' ? bMed : aMed).name,
            otherDrug: (aMed.source === 'draft' ? bMed : bMed.source === 'draft' ? aMed : bMed).name,
            message: rule.message(normName(aMed.name), normName(bMed.name), null),
            ruleId: rule.id,
          });
        }
      }
    }
  }
  return out;
}

/** Rule count surfaced in admin diagnostics (mirrors DOSE_RANGE_TABLE_SIZE). */
export const DRUG_INTERACTION_RULE_COUNT = RULES.length;
