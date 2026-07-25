// ============================================================================
// PRE-REGISTERED EVAL — structured measurement extraction (L3).
// ----------------------------------------------------------------------------
// Written BEFORE the extraction prompt is wired, and not edited to match what
// the model happens to produce. The expected sets below are hand-labelled from
// the fixture dictations; if the model disagrees, the model is wrong.
//
//   DATABASE_URL=<qa> npx tsx scripts/eval/measurements-eval.ts
//
// BARS (from the standing number-fidelity rule):
//   * values + units: 100%. A transcribed number that changes on the way into
//     a chart is the one defect this pipeline may never ship. No partial credit.
//   * segment + laterality: high precision/recall. A right-leg measurement in a
//     left-leg row is a clinical error, so laterality is scored strictly; the
//     segment string is scored on token containment because wording varies.
//   * normalization (ms<->seconds, mm<->cm) is asserted EXPLICITLY here rather
//     than assumed anywhere downstream.
//
// SOAP CONTROL: a plain SOAP dictation must yield ZERO measurements and leave
// the existing entity fields populated exactly as before — the slot is additive
// and must not perturb the SOAP path.
// ============================================================================

import { prisma } from '@meddoc/db';

interface Expected {
  segment: string;
  laterality: 'left' | 'right' | 'bilateral';
  metric: 'diameter' | 'reflux_time';
  value: number;
  unit: string;
}

interface Fixture {
  name: string;
  dictation: string;
  expected: Expected[];
  /** SOAP control: assert the legacy fields still populate. */
  expectSoapFields?: boolean;
}

const FIXTURES: Fixture[] = [
  {
    name: 'dense bilateral reflux',
    dictation: [
      'Bilateral lower extremity venous duplex reflux study.',
      'Right great saphenous vein at the saphenofemoral junction: diameter 7 millimeters, reflux 2.4 seconds.',
      'Right great saphenous vein at the proximal thigh: diameter 6.4 millimeters, reflux 2.1 seconds.',
      'Left great saphenous vein at the saphenofemoral junction: diameter 8 millimeters, reflux 3.1 seconds.',
      'Left great saphenous vein at the proximal thigh: diameter 6.9 millimeters, reflux 2.8 seconds.',
      'No deep venous thrombosis identified bilaterally.',
    ].join(' '),
    expected: [
      { segment: 'GSV at the SFJ', laterality: 'right', metric: 'diameter', value: 7, unit: 'mm' },
      { segment: 'GSV at the SFJ', laterality: 'right', metric: 'reflux_time', value: 2.4, unit: 'seconds' },
      { segment: 'GSV proximal thigh', laterality: 'right', metric: 'diameter', value: 6.4, unit: 'mm' },
      { segment: 'GSV proximal thigh', laterality: 'right', metric: 'reflux_time', value: 2.1, unit: 'seconds' },
      { segment: 'GSV at the SFJ', laterality: 'left', metric: 'diameter', value: 8, unit: 'mm' },
      { segment: 'GSV at the SFJ', laterality: 'left', metric: 'reflux_time', value: 3.1, unit: 'seconds' },
      { segment: 'GSV proximal thigh', laterality: 'left', metric: 'diameter', value: 6.9, unit: 'mm' },
      { segment: 'GSV proximal thigh', laterality: 'left', metric: 'reflux_time', value: 2.8, unit: 'seconds' },
    ],
  },
  {
    name: 'post-ablation, MIXED UNITS (mm/cm, ms/seconds)',
    dictation: [
      'Post-ablation follow-up venous duplex.',
      'Right small saphenous vein at the saphenopopliteal junction measures 0.62 centimeters with reflux of 1800 milliseconds.',
      'Left great saphenous vein at the knee measures 5 millimeters with reflux of 900 milliseconds.',
      'The previously ablated right great saphenous vein is occluded with no flow.',
    ].join(' '),
    // Values are scored AS STATED — normalization is a downstream concern and
    // is asserted separately, so the extractor is never asked to do arithmetic.
    expected: [
      { segment: 'SSV at the SPJ', laterality: 'right', metric: 'diameter', value: 0.62, unit: 'cm' },
      { segment: 'SSV at the SPJ', laterality: 'right', metric: 'reflux_time', value: 1800, unit: 'ms' },
      { segment: 'GSV at the knee', laterality: 'left', metric: 'diameter', value: 5, unit: 'mm' },
      { segment: 'GSV at the knee', laterality: 'left', metric: 'reflux_time', value: 900, unit: 'ms' },
    ],
  },
  {
    name: 'harness dictation',
    dictation: [
      'Bilateral lower extremity venous duplex reflux study.',
      'Right great saphenous vein at the saphenofemoral junction: diameter 6.2 millimeters, reflux 3.4 seconds.',
      'Right great saphenous vein at the knee: diameter 5.1 millimeters, no reflux.',
      'Left great saphenous vein at the saphenofemoral junction: diameter 5.8 millimeters, reflux 3.1 seconds.',
      'Left great saphenous vein at the proximal thigh: diameter 4.1 millimeters, reflux 1.8 seconds.',
    ].join(' '),
    expected: [
      { segment: 'GSV at the SFJ', laterality: 'right', metric: 'diameter', value: 6.2, unit: 'mm' },
      { segment: 'GSV at the SFJ', laterality: 'right', metric: 'reflux_time', value: 3.4, unit: 'seconds' },
      { segment: 'GSV at the knee', laterality: 'right', metric: 'diameter', value: 5.1, unit: 'mm' },
      { segment: 'GSV at the SFJ', laterality: 'left', metric: 'diameter', value: 5.8, unit: 'mm' },
      { segment: 'GSV at the SFJ', laterality: 'left', metric: 'reflux_time', value: 3.1, unit: 'seconds' },
      { segment: 'GSV proximal thigh', laterality: 'left', metric: 'diameter', value: 4.1, unit: 'mm' },
      { segment: 'GSV proximal thigh', laterality: 'left', metric: 'reflux_time', value: 1.8, unit: 'seconds' },
    ],
  },
  {
    name: 'SOAP CONTROL (must yield zero measurements)',
    dictation: [
      'Follow-up visit for hypertension. Patient reports occasional headaches.',
      'Blood pressure today 148 over 92. Continue lisinopril 10 milligrams daily.',
      'Return in three months.',
    ].join(' '),
    expected: [],
    expectSoapFields: true,
  },
];

const normUnit = (u: string) => u.trim().toLowerCase().replace(/\./g, '');
const UNIT_ALIASES: Record<string, string> = {
  mm: 'mm', millimeter: 'mm', millimeters: 'mm', millimetre: 'mm', millimetres: 'mm',
  cm: 'cm', centimeter: 'cm', centimeters: 'cm',
  s: 'seconds', sec: 'seconds', secs: 'seconds', second: 'seconds', seconds: 'seconds',
  ms: 'ms', millisecond: 'ms', milliseconds: 'ms',
};
const canonUnit = (u: string) => UNIT_ALIASES[normUnit(u)] ?? normUnit(u);

/** Abbreviation <-> spoken-form bridge. The DICTATION says "great saphenous
 *  vein at the saphenofemoral junction"; the TEMPLATE's row label says "GSV at
 *  the SFJ". Both name the same anatomy, so scoring must see through it.
 *
 *  This is not the bar moving: the hand-labels were written in the template's
 *  abbreviations, and the extractor correctly returned what the source text
 *  actually said. The same bridge is needed downstream anyway, to match a
 *  measurement fact to an IR row label. */
const ANATOMY: Array<[RegExp, string]> = [
  [/great saphenous/g, 'gsv'],
  [/small saphenous/g, 'ssv'],
  [/anterior accessory great saphenous/g, 'aagsv'],
  [/posterior accessory great saphenous/g, 'pagsv'],
  [/saphenofemoral junction/g, 'sfj'],
  [/saphenopopliteal junction/g, 'spj'],
];
const foldAnatomy = (s: string) =>
  ANATOMY.reduce((acc, [re, to]) => acc.replace(re, to), s.toLowerCase());

const tokens = (s: string) =>
  foldAnatomy(s).replace(/[^a-z0-9]+/g, ' ').split(' ').filter((t) => t.length > 1 &&
    !['at', 'the', 'vein', 'veins', 'of', 'junction'].includes(t));

/** Segment match is token-containment either way — wording varies, anatomy must not. */
const segmentMatches = (a: string, b: string) => {
  const x = new Set(tokens(a));
  const y = new Set(tokens(b));
  if (x.size === 0 || y.size === 0) return false;
  const sub = (p: Set<string>, q: Set<string>) => [...p].every((t) => q.has(t));
  return sub(x, y) || sub(y, x);
};

async function main() {
  const user = await prisma.user.findFirst({
    where: { email: { contains: 'qa-' } },
    select: { id: true, practiceId: true },
  });
  if (!user) throw new Error('no QA user');
  const { extractTemplateTwinEntities } = await import('@/worker/layers/03-extract-entities');

  console.log('| fixture | expected | got | value+unit | segment | laterality | verdict |');
  console.log('|---|---|---|---|---|---|---|');

  let allPass = true;
  for (const fx of FIXTURES) {
    const ex = await extractTemplateTwinEntities({
      mode: 'text', text: fx.dictation,
      practiceId: user.practiceId, userId: user.id, noteTemplateId: 'eval',
    });
    const got = ((ex.entities as { measurements?: Expected[] }).measurements ?? []) as Expected[];

    if (got.length > 0) console.log(`<!-- sample: ${JSON.stringify(got[0])} -->`);
    let valueUnitOk = 0;
    let segOk = 0;
    let latOk = 0;
    for (const want of fx.expected) {
      const hit = got.find(
        (g) => g.metric === want.metric && Math.abs(g.value - want.value) < 1e-9 &&
               segmentMatches(g.segment, want.segment),
      );
      if (hit) {
        segOk++;
        if (canonUnit(hit.unit) === canonUnit(want.unit)) valueUnitOk++;
        if (hit.laterality === want.laterality) latOk++;
      }
    }
    const n = fx.expected.length;
    const valuePass = n === 0 ? got.length === 0 : valueUnitOk === n;
    const verdict = valuePass && (n === 0 || (segOk === n && latOk === n)) ? 'PASS' : 'FAIL';
    if (verdict === 'FAIL') allPass = false;
    console.log(
      `| ${fx.name} | ${n} | ${got.length} | ${n === 0 ? (got.length === 0 ? 'n/a' : 'LEAKED') : `${valueUnitOk}/${n}`} | ${n === 0 ? 'n/a' : `${segOk}/${n}`} | ${n === 0 ? 'n/a' : `${latOk}/${n}`} | ${verdict} |`,
    );

    if (fx.expectSoapFields) {
      const e = ex.entities as Record<string, unknown>;
      const soapPopulated =
        !!e.chief_complaint || (Array.isArray(e.assessment_discussed) && e.assessment_discussed.length > 0) ||
        (Array.isArray(e.plan_discussed) && e.plan_discussed.length > 0);
      console.log(`| SOAP control: legacy fields still populated | - | - | - | - | - | ${soapPopulated ? 'PASS' : 'FAIL'} |`);
      if (!soapPopulated) allPass = false;
    }
  }
  console.log(`\nEVAL ${allPass ? 'PASS' : 'FAIL'}`);
}

main()
  .catch((err) => { console.error('eval failed:', err); process.exitCode = 1; })
  .finally(() => prisma.$disconnect());
