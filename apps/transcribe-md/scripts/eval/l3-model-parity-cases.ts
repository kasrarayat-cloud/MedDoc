// ============================================================================
// THE L3 PARITY CORPUS — SIDE-EFFECT-FREE, SO SOMETHING CAN CHECK IT.
// ----------------------------------------------------------------------------
// ⚠️ EXTRACTED BECAUSE THE EVAL CANNOT BE IMPORTED. `l3-model-parity.ts` runs a
// top-level IIFE, so merely importing it EXECUTES the eval and attempts twelve
// live model calls — verified with an empty ANTHROPIC_API_KEY, which printed
// the full report and twelve "ERROR ANTHROPIC_API_KEY is not set." lines. No CI
// arm could reach the ground truth while it lived there.
//
// ⚠️ AND THE GROUND TRUTH WAS PARTLY UNSATISFIABLE, WHICH IS WHY THE ARM
// MATTERS. Matching was `String(finding).toLowerCase().includes(findingLike)`,
// against a `finding` that #179 made a CLOSED-LEXICON TOKEN. Measured, 3 of 8
// ROS rows could never score on any model:
//
//   findingLike 'chest pain'  vs token `chest_pain`   — the SPACE never matches
//   findingLike 'breath'      vs token `dyspnea`      — no character in common
//   findingLike 'blood'       vs token `hematochezia` — likewise
//
// A fourth, 'weight', matched TWO tokens (`weight_loss`, `weight_gain`), so it
// could score on the wrong one.
//
// ⚠️ THE DIRECTION OF THE ERROR IS THE PART TO KEEP: the eval was reporting a
// score WORSE than reality, on both models equally. It could not have flagged a
// regression, and it could have condemned a model that was extracting
// perfectly. `findingLike` is therefore now `finding`, an EXACT lexicon token,
// and `gate-179-ros-eval-corpus-reachable` asserts every row is one.
// ============================================================================

export interface Expected {
  ros: ReadonlyArray<{ system: string; finding: string; polarity: 'affirmed' | 'denied' }>;
  exam: ReadonlyArray<{ system: string; findingLike: string }>;
  minEntities: number;
}

export interface Case {
  readonly name: string;
  readonly text: string;
  readonly expected: Expected;
}

/**
 * ⚠️ GROUND TRUTH IS WRITTEN, NOT INFERRED. Each case states what a correct
 * extraction contains, so "coverage" is measured against an answer fixed before
 * either model ran — the same discipline as a §2.5 declaration.
 *
 * ⚠️ AND THE POLARITY CASES ARE DELIBERATELY MIXED. A denial-only corpus lets a
 * model that always answers "denied" score perfectly. Three cases affirm, three
 * deny, and one does both in a single sentence — the shape §02.9's comment
 * names as where a regex "over-fires when one quote carries two findings".
 */
export const CASES: readonly Case[] = [
  {
    name: 'GI denial, plain',
    text: [
      'Doctor: This is a gastroenterology consultation.',
      'Doctor: The patient denies heartburn, difficulty swallowing, and painful swallowing.',
      'Doctor: He denies nausea or vomiting.',
    ].join('\n'),
    expected: {
      ros: [
        { system: 'gastrointestinal', finding: 'heartburn', polarity: 'denied' },
        { system: 'gastrointestinal', finding: 'nausea', polarity: 'denied' },
      ],
      exam: [],
      minEntities: 2,
    },
  },
  {
    name: 'GI affirmation — must NOT be read as a denial',
    text: [
      'Doctor: Gastroenterology consultation.',
      'Doctor: The patient reports heartburn three times a week for two months.',
      'Doctor: He also reports early satiety.',
    ].join('\n'),
    expected: {
      ros: [
        { system: 'gastrointestinal', finding: 'heartburn', polarity: 'affirmed' },
        { system: 'gastrointestinal', finding: 'early_satiety', polarity: 'affirmed' },
      ],
      exam: [],
      minEntities: 2,
    },
  },
  {
    name: 'MIXED polarity in one sentence — the regex trap §02.9 names',
    text: [
      'Doctor: Consultation note.',
      'Doctor: She denies chest pain but does get short of breath climbing stairs.',
    ].join('\n'),
    expected: {
      ros: [
        { system: 'cardiovascular', finding: 'chest_pain', polarity: 'denied' },
        { system: 'respiratory', finding: 'dyspnea', polarity: 'affirmed' },
      ],
      exam: [],
      minEntities: 2,
    },
  },
  {
    name: 'Colloquial denial — no charting token present',
    text: [
      'Doctor: Follow-up visit.',
      'Doctor: I asked about blood in the stool and he said none at all.',
    ].join('\n'),
    expected: {
      ros: [{ system: 'gastrointestinal', finding: 'hematochezia', polarity: 'denied' }],
      exam: [],
      minEntities: 1,
    },
  },
  {
    name: 'Exam findings, abnormal and normal',
    text: [
      'Doctor: On examination the abdomen is tender in the right upper quadrant.',
      'Doctor: Lungs are clear to auscultation bilaterally.',
      'Doctor: The patient is alert and oriented, in no acute distress.',
    ].join('\n'),
    expected: {
      ros: [],
      exam: [
        { system: 'abdomen', findingLike: 'tender' },
        { system: 'lungs', findingLike: 'clear' },
      ],
      minEntities: 2,
    },
  },
  {
    name: 'Full consult — the 19-concept vocabulary in one pass',
    text: [
      'Doctor: Gastroenterology consultation for a fifty-two year old.',
      'Doctor: Chief complaint is abdominal bloating for three months.',
      'Doctor: Past medical history includes hypertension and type two diabetes.',
      'Doctor: He takes lisinopril ten milligrams daily.',
      'Doctor: He is allergic to penicillin, which causes a rash.',
      'Doctor: Father had colon cancer.',
      'Doctor: He is a former smoker, drinks socially, works as an accountant.',
      'Doctor: The patient denies weight loss.',
      'Doctor: Abdomen is soft and non-tender on exam.',
      'Doctor: Impression is functional bloating.',
      'Doctor: Plan is a trial of dietary modification and follow up in six weeks.',
    ].join('\n'),
    expected: {
      ros: [{ system: 'constitutional', finding: 'weight_loss', polarity: 'denied' }],
      exam: [{ system: 'abdomen', findingLike: 'non-tender' }],
      minEntities: 10,
    },
  },
];
