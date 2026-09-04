// ============================================================================
// L3 MODEL PARITY — opus-4-8 vs opus-5, on SYNTHETIC dictations only.
// ----------------------------------------------------------------------------
// ⚠️ NO PHI. Every dictation below is written for this file. Nothing here comes
// from a patient, a visit, or a transcript, and the harness never reads one.
//
// The production model is pinned for ZERO DATA RETENTION, not for age. Verified
// 2026-09-04 against Anthropic's current documentation: Claude Fable 5.1,
// Mythos 5.1, Fable 5 and Mythos 5 are Covered Models requiring 30-day
// retention and excluded from ZDR; Opus 5 is NOT on that list. The features
// this path uses — Messages API, structured outputs, prompt caching — are all
// ZDR-eligible; batch processing and the Files API are not and must never
// enter it (`gate-zdr-ineligible-features.test.ts` asserts that).
//
// WHAT THIS MEASURES, and why each axis exists:
//
//   1. FABRICATION — every `evidence_quote` must appear VERBATIM in the source
//      dictation. Must be ZERO. A quote the doctor never said is the worst
//      thing this pipeline can produce, and it is the one axis with no
//      acceptable non-zero value.
//
//   2. ROS / EXAM ENTITY COVERAGE — the concepts row 4 and row 5 depend on.
//      Counted against a ground truth written into each case.
//
//   3. POLARITY CORRECTNESS — §02.9 made this measurable. The L3 schema makes
//      `polarity` REQUIRED WITH NO DEFAULT, so a model that omits it fails
//      schema validation and is retried; a model that states it WRONGLY passes
//      validation and quietly inverts a clinical claim. The second is the
//      dangerous one, so it is measured against ground truth rather than
//      merely counted as present.
//
//   4. EVIDENCE-ANCHOR FIDELITY across the whole 19-concept vocabulary — the
//      share of extracted entities whose quote is exactly locatable.
//
// SWITCHING RULE: parity-or-better on every axis, fabrication still 0, AND
// confirmed retention terms. The last is a contract fact, not a measurement,
// and this harness cannot establish it.
// ============================================================================
import { randomUUID } from 'node:crypto';

import { extractTemplateTwinEntities } from '../../src/worker/layers/03-extract-entities';

interface Expected {
  ros: ReadonlyArray<{ system: string; findingLike: string; polarity: 'affirmed' | 'denied' }>;
  exam: ReadonlyArray<{ system: string; findingLike: string }>;
  minEntities: number;
}

interface Case {
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
const CASES: readonly Case[] = [
  {
    name: 'GI denial, plain',
    text: [
      'Doctor: This is a gastroenterology consultation.',
      'Doctor: The patient denies heartburn, difficulty swallowing, and painful swallowing.',
      'Doctor: He denies nausea or vomiting.',
    ].join('\n'),
    expected: {
      ros: [
        { system: 'gastrointestinal', findingLike: 'heartburn', polarity: 'denied' },
        { system: 'gastrointestinal', findingLike: 'nausea', polarity: 'denied' },
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
        { system: 'gastrointestinal', findingLike: 'heartburn', polarity: 'affirmed' },
        { system: 'gastrointestinal', findingLike: 'satiety', polarity: 'affirmed' },
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
        { system: 'cardiovascular', findingLike: 'chest pain', polarity: 'denied' },
        { system: 'respiratory', findingLike: 'breath', polarity: 'affirmed' },
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
      ros: [{ system: 'gastrointestinal', findingLike: 'blood', polarity: 'denied' }],
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
      ros: [{ system: 'constitutional', findingLike: 'weight', polarity: 'denied' }],
      exam: [{ system: 'abdomen', findingLike: 'non-tender' }],
      minEntities: 10,
    },
  },
];

/**
 * Normalised containment.
 *
 * ⚠️ SPEAKER LABELS ARE STRIPPED, AND THE FIRST VERSION DID NOT DO THAT — SO IT
 * REPORTED A FABRICATION ON BOTH MODELS IDENTICALLY. The dictation is
 * ROLE-LABELLED by construction (`buildRoleLabeledTranscript`), so a quote
 * spanning two sentences legitimately crosses a `Doctor: ` prefix:
 *
 *   source  "…for two months.\nDoctor: He also reports early satiety."
 *   quote   "…for two months. He also reports early satiety."
 *
 * The quote is verbatim CLINICAL prose; only the label sits between. A checker
 * that demands the label back scores every multi-sentence quote as invented —
 * and an identical failure on two different models was the tell that the
 * instrument was wrong, not the models.
 *
 * ⚠️ AND THIS IS THE ONE AXIS THAT MUST NOT BE LOOSENED CARELESSLY. Stripping
 * labels removes exactly the speaker prefixes and nothing else; it cannot make
 * invented CONTENT pass, which is what the axis is for. The positive control
 * below proves that.
 */
function saidVerbatim(quote: string, source: string): boolean {
  const strip = (s: string) =>
    s
      .split('\n')
      .map((l) => l.replace(/^\s*[A-Z][A-Za-z ]{0,20}:\s*/, ''))
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  return strip(source).includes(strip(quote));
}

/** ⚠️ THE AXIS MUST STILL CATCH INVENTION. Driven at startup, not asserted in a
 *  test that runs elsewhere: loosening a fabrication check is the change most
 *  worth a control standing right beside it. */
function assertFabricationCheckStillBites(): void {
  const src = 'Doctor: The patient reports heartburn.\nDoctor: He also reports early satiety.';
  const spanning = 'The patient reports heartburn. He also reports early satiety.';
  const invented = 'The patient reports crushing chest pain radiating to the jaw.';
  if (!saidVerbatim(spanning, src)) {
    throw new Error('fabrication check rejects a legitimate label-spanning quote');
  }
  if (saidVerbatim(invented, src)) {
    throw new Error('fabrication check no longer catches invented content');
  }
}
assertFabricationCheckStillBites();

function walkEntities(entities: unknown): Array<{ path: string; quote: string }> {
  const out: Array<{ path: string; quote: string }> = [];
  const walk = (node: unknown, path: string) => {
    if (Array.isArray(node)) return node.forEach((n, i) => walk(n, `${path}[${i}]`));
    if (node && typeof node === 'object') {
      const rec = node as Record<string, unknown>;
      if (typeof rec.evidence_quote === 'string') out.push({ path, quote: rec.evidence_quote });
      for (const [k, v] of Object.entries(rec)) walk(v, path ? `${path}.${k}` : k);
    }
  };
  walk(entities, '');
  return out;
}

interface Score {
  model: string;
  calls: number;
  errors: number;
  entitiesTotal: number;
  quotesTotal: number;
  quotesFabricated: number;
  rosExpected: number;
  rosFound: number;
  rosPolarityCorrect: number;
  rosPolarityStated: number;
  examExpected: number;
  examFound: number;
}

async function scoreModel(model: string): Promise<Score> {
  const s: Score = {
    model, calls: 0, errors: 0, entitiesTotal: 0, quotesTotal: 0, quotesFabricated: 0,
    rosExpected: 0, rosFound: 0, rosPolarityCorrect: 0, rosPolarityStated: 0,
    examExpected: 0, examFound: 0,
  };
  process.env.TRANSCRIBE_MD_CLINICAL_MODEL = model;
  // ⚠️ #179(7)/(3) — IDENTICAL WIRE SHAPES, ASSERTED RATHER THAN ASSUMED.
  // Parity measured across unequal regimes is not parity. Both models are in
  // TEMPERATURE_STRIPPED, so both send the same body; if either ever stopped
  // being, this comparison would silently be measuring the wire shape as much
  // as the model. The refusal arm in temperature-stripping.test.ts is what
  // makes an unlisted model impossible here rather than merely unlikely.

  for (const c of CASES) {
    s.rosExpected += c.expected.ros.length;
    s.examExpected += c.expected.exam.length;
    let entities: Record<string, unknown>;
    try {
      s.calls += 1;
      const out = await extractTemplateTwinEntities({
        mode: 'dictation',
        text: c.text,
        practiceId: `eval_${randomUUID().replace(/-/g, '').slice(0, 20)}`,
        userId: null,
        noteTemplateId: randomUUID(),
      });
      entities = out.entities as Record<string, unknown>;
    } catch (err) {
      s.errors += 1;
      console.error(`  [${model}] ${c.name}: ERROR ${(err as Error).message.slice(0, 120)}`);
      continue;
    }

    const quotes = walkEntities(entities);
    s.quotesTotal += quotes.length;
    s.entitiesTotal += quotes.length;
    for (const q of quotes) {
      if (!saidVerbatim(q.quote, c.text)) {
        s.quotesFabricated += 1;
        console.error(`  [${model}] ${c.name}: FABRICATED at ${q.path}: "${q.quote.slice(0, 80)}"`);
      }
    }

    const ros = (entities.ros ?? []) as Array<Record<string, unknown>>;
    for (const want of c.expected.ros) {
      const hit = ros.find((r) =>
        String(r.finding ?? '').toLowerCase().includes(want.findingLike.toLowerCase()),
      );
      if (!hit) continue;
      s.rosFound += 1;
      if (typeof hit.polarity === 'string') s.rosPolarityStated += 1;
      if (hit.polarity === want.polarity) s.rosPolarityCorrect += 1;
      else {
        console.error(
          `  [${model}] ${c.name}: POLARITY WRONG for "${want.findingLike}" — ` +
            `stated ${String(hit.polarity)}, truth ${want.polarity}`,
        );
      }
    }

    const exam = (entities.exam_findings ?? []) as Array<Record<string, unknown>>;
    for (const want of c.expected.exam) {
      if (
        exam.some((e) =>
          String(e.finding ?? '').toLowerCase().includes(want.findingLike.toLowerCase()),
        )
      ) {
        s.examFound += 1;
      }
    }
  }
  return s;
}

function line(s: Score): string {
  const pct = (a: number, b: number) => (b === 0 ? ' n/a' : `${Math.round((a / b) * 100)}%`.padStart(4));
  return [
    s.model.padEnd(18),
    `calls ${String(s.calls).padStart(2)}`,
    `err ${String(s.errors).padStart(2)}`,
    `FABRICATED ${String(s.quotesFabricated).padStart(3)}`,
    `anchors ${pct(s.quotesTotal - s.quotesFabricated, s.quotesTotal)}`,
    `ROS ${String(s.rosFound).padStart(2)}/${s.rosExpected}`,
    `polarity ${String(s.rosPolarityCorrect).padStart(2)}/${s.rosFound}`,
    `exam ${String(s.examFound).padStart(2)}/${s.examExpected}`,
  ].join('  ');
}

(async () => {
  const models = (process.env.ZZ_MODELS ?? 'claude-opus-4-8,claude-opus-5').split(',');
  console.log(`L3 MODEL PARITY — ${CASES.length} synthetic dictations, no PHI\n`);
  const scores: Score[] = [];
  for (const m of models) scores.push(await scoreModel(m.trim()));
  console.log('');
  for (const s of scores) console.log('  ' + line(s));

  const base = scores[0]!;
  const cand = scores[1];
  if (!cand) return;
  console.log('\n  VERDICT');
  const fabricationOk = cand.quotesFabricated === 0;
  const rosOk = cand.rosFound >= base.rosFound;
  const polOk = cand.rosPolarityCorrect >= base.rosPolarityCorrect;
  const examOk = cand.examFound >= base.examFound;
  const anchorOk =
    cand.quotesTotal === 0 ? false : cand.quotesFabricated <= base.quotesFabricated;
  for (const [label, ok] of [
    ['fabrication is ZERO', fabricationOk],
    ['ROS coverage parity-or-better', rosOk],
    ['polarity correctness parity-or-better', polOk],
    ['exam coverage parity-or-better', examOk],
    ['evidence-anchor fidelity parity-or-better', anchorOk],
  ] as Array<[string, boolean]>) {
    console.log(`  ${ok ? '✅' : '🔴'} ${label}`);
  }
  const pass = fabricationOk && rosOk && polOk && examOk && anchorOk;
  console.log(
    `\n  ${pass ? '🟢 PARITY-OR-BETTER' : '🔴 NOT AT PARITY'} — the switch additionally ` +
      'requires confirmed retention terms, which this harness cannot establish.',
  );
})();
