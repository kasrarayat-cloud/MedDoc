// ============================================================================
// RULING #313 · WHAT IS A BULLET GROUP — G1..G7, THE REFUSALS, THE OWNER SHAPE.
// ----------------------------------------------------------------------------
// WHAT WOULD MAKE THIS FAIL: drop any one rule from `bulletGroups` and the arm
// for its counterexample groups what must be refused (and its distribution
// output stops being byte-identical to the pass not existing). Every refusal
// is a ONE-CHANGE variant of the same positive base, so the base is its twin.
//
// ⚠️ THE OWNER SHAPE (A16) IS BUILT FROM THE GENERATOR'S OWN VOCABULARY
// (`sdt`, `ROS_CLAUSES`, `EXAM_CLAUSES`), as gate-274 does. The owner's bytes are
// NOT in this repository and no `.docx` is committed.
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  EXAM_CLAUSES,
  ROS_CLAUSES,
  sdt,
} from '../../../../scripts/regenerate-consult-form';
import {
  analyzeBulletGroups,
  bulletGroups,
  BULLET_GROUP_COMPARED_MAPPING_KEYS,
  BULLET_GROUP_IDENTITY_KEYS,
} from '../bullet-groups';
import { canonicalSha256 } from '../canonical';
import { SemanticMappingSchema, type SemanticMapping } from '../ir';
import { distributeListItems } from '../list-distribution';
import {
  bullets,
  compiledForm,
  ctl,
  fact,
  heading,
  headerXml,
  mappingsFor,
  membersByAlias,
  para,
  PMH,
  PMH_BODY,
  PMH_CONCEPTS,
  resolveAll,
  text,
  withoutSoleParagraphControl,
} from './helpers-313';

const TWO_ITEMS = [
  fact('g-a', 'past_medical_history', 'Hypertension'),
  fact('g-b', 'past_medical_history', 'Type 2 diabetes mellitus'),
];

/** Refused output must be BYTE-IDENTICAL to the pass not existing. */
function distributionIsANoOp(
  ir: Parameters<typeof resolveAll>[0],
  mappings: SemanticMapping[],
): boolean {
  const resolved = resolveAll(ir, mappings, TWO_ITEMS);
  const out = distributeListItems({ ir, mappings, facts: TWO_ITEMS, resolutions: resolved });
  return canonicalSha256(out) === canonicalSha256(resolved);
}

describe('#313 G7 — the compared mapping keys are DERIVED from the schema, and pinned', () => {
  it('identity keys are exactly [fieldId]; everything else is compared', () => {
    expect(BULLET_GROUP_IDENTITY_KEYS).toEqual(['fieldId']);
    expect([...BULLET_GROUP_COMPARED_MAPPING_KEYS].sort()).toEqual(
      Object.keys(SemanticMappingSchema.shape).filter((key) => key !== 'fieldId').sort(),
    );
    // ⚠️ THE PIN. A key added to `SemanticMappingSchema` is compared by default
    // (fail-closed) — and this list makes the addition SEEN: it goes red, and
    // whoever adds the key decides here whether members must agree on it.
    expect([...BULLET_GROUP_COMPARED_MAPPING_KEYS].sort()).toEqual(
      [
        'approvedSynonyms',
        'blankPolicy',
        'clinicalConcept',
        'conceptScope',
        'expectedDataType',
        'laterality',
        'polarityBehavior',
        'practiceDefault',
        'required',
        'sourceType',
        'status',
        'temporality',
        'unitPolicy',
        'unknownPolicy',
        'unmentionedPolicy',
      ].sort(),
    );
  });

  // One different, VALID value per compared key. A key with no row here fails
  // the arm below — the table must grow with the schema.
  const ALTERNATIVE: Record<string, unknown> = {
    sourceType: 'manual',
    clinicalConcept: 'past_surgical_history',
    expectedDataType: 'single_select',
    polarityBehavior: 'explicit_denial_allowed',
    temporality: 'historical',
    laterality: 'optional',
    unitPolicy: 'forbidden',
    approvedSynonyms: ['PMH'],
    conceptScope: ['past_medical_history'],
    required: true,
    blankPolicy: 'requires_input',
    unknownPolicy: 'requires_input',
    unmentionedPolicy: 'omit',
    practiceDefault: 'Hypertension',
    status: 'recognized',
  };

  it.each([...BULLET_GROUP_COMPARED_MAPPING_KEYS])(
    'bullet 3 differing ONLY on `%s` refuses the WHOLE group, naming that key',
    async (key) => {
      expect(ALTERNATIVE, `no alternative value for new mapping key "${key}"`).toHaveProperty(key);
      const { ir } = await compiledForm(PMH_BODY);
      const mappings = mappingsFor(ir, PMH_CONCEPTS, (_field, index) =>
        index === 2 ? ({ [key]: ALTERNATIVE[key] } as Partial<SemanticMapping>) : {},
      );
      const analysis = analyzeBulletGroups(ir.fields, mappings);
      expect(analysis.groups).toEqual([]);
      expect(analysis.refused).toHaveLength(1);
      expect(analysis.refused[0]!.memberFieldIds).toHaveLength(3); // never SPLIT
      expect(['member_mappings_differ', 'member_mapping_not_list_valued']).toContain(
        analysis.refused[0]!.reason,
      );
      if (analysis.refused[0]!.reason === 'member_mappings_differ') {
        expect(analysis.refused[0]!.key).toBe(key);
      }
    },
  );

  it('POSITIVE: equivalent spellings the MATCHER treats alike do not refuse', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const mappings = mappingsFor(ir, PMH_CONCEPTS, (_field, index) =>
      index === 0
        ? { approvedSynonyms: ['PMH', 'Medical History'], clinicalConcept: 'Past_Medical_History' }
        : index === 1
          ? { approvedSynonyms: ['medical history', 'pmh'], unmentionedPolicy: null }
          : { approvedSynonyms: ['Medical History', 'PMH'], conceptScope: [] },
    );
    expect(bulletGroups(ir.fields, mappings)).toHaveLength(1);
  });

  it('⚠️ registry SYNONYMS are NOT equal here (narrower than canonical) — refused', async () => {
    // `impression` canonicalises to `assessment`, but the MATCHER compares
    // normalised spellings, so the two members would admit different fact sets.
    const { ir } = await compiledForm([heading('Impression'), ...bullets('Impression', 'imp', 2, 1)]);
    const mappings = mappingsFor(ir, { Impression: 'assessment' }, (_field, index) =>
      index === 1 ? { clinicalConcept: 'impression' } : {},
    );
    const analysis = analyzeBulletGroups(ir.fields, mappings);
    expect(analysis.groups).toEqual([]);
    expect(analysis.refused[0]).toMatchObject({ reason: 'member_mappings_differ', key: 'clinicalConcept' });
  });
});

describe('#313 A7 — every counterexample refuses, and the output is byte-identical', () => {
  it('POSITIVE BASE: Past Medical History ×3 is one group, and distribution CHANGES the output', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const mappings = mappingsFor(ir, PMH_CONCEPTS);
    const groups = bulletGroups(ir.fields, mappings);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.memberFieldIds).toEqual(membersByAlias(ir, PMH).map((field) => field.fieldId));
    expect(distributionIsANoOp(ir, mappings)).toBe(false);
  });

  const A = PMH;
  const CASES: ReadonlyArray<{
    name: string;
    body: string[];
    header?: string;
    concepts?: Record<string, string>;
    reason: string | null;
  }> = [
    {
      name: '"Right leg: [control]" / "Left leg: [control]" — text outside (G4)',
      body: [
        heading(A),
        para(text('Right leg: '), ctl(A, 'pmh', 100)),
        para(text('Left leg: '), ctl(A, 'pmh', 101)),
        para(text('Other: '), ctl(A, 'pmh', 102)),
      ],
      reason: 'member_not_sole_in_paragraph',
    },
    {
      name: 'three same-alias controls in ONE paragraph, the ROS shape (G4)',
      body: [heading(A), para(ctl(A, 'pmh', 100), text(' '), ctl(A, 'pmh', 101), text(' '), ctl(A, 'pmh', 102))],
      reason: 'member_not_sole_in_paragraph',
    },
    {
      name: 'a legacy form field sharing a bullet paragraph (G4)',
      body: [
        heading(A),
        para(ctl(A, 'pmh', 100)),
        para(ctl(A, 'pmh', 101)),
        para(
          ctl(A, 'pmh', 102),
          '<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="L"/><w:textInput/></w:ffData></w:fldChar></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>',
        ),
      ],
      reason: 'member_not_sole_in_paragraph',
    },
    {
      name: 'scaffold "Right: ___" / "Left: ___" inside the controls (G6)',
      body: [
        heading(A),
        para(ctl(A, 'pmh', 100, 'Right: ____')),
        para(ctl(A, 'pmh', 101, 'Left: ____')),
        para(ctl(A, 'pmh', 102, '- ____')),
      ],
      reason: 'member_scaffold_differs',
    },
    {
      name: 'a run broken by a "(continued)" line (G5) — never split into two item-1s',
      body: [heading(A), para(ctl(A, 'pmh', 100)), para(ctl(A, 'pmh', 101)), heading('(continued)'), para(ctl(A, 'pmh', 102))],
      reason: 'members_not_one_run',
    },
    {
      name: 'one bullet without the shared tag (G3)',
      body: [heading(A), para(ctl(A, 'pmh', 100)), para(ctl(A, 'pmh', 101)), para(ctl(A, null, 102))],
      reason: 'member_identity',
    },
    {
      name: 'the tag shared by a control elsewhere under another alias (G3, linked by tag)',
      body: [...PMH_BODY, heading('Notes'), para(text('Note: '), ctl('Other note', 'pmh', 300))],
      reason: 'member_identity',
    },
    {
      name: 'tag-only bullets — no DECLARED alias (G3)',
      body: [heading(A), para(ctl(null, 'pmh', 100)), para(ctl(null, 'pmh', 101)), para(ctl(null, 'pmh', 102))],
      reason: 'member_identity',
    },
    {
      name: 'the same alias and tag in the header and the body (G2)',
      body: [heading(A), para(ctl(A, 'pmh', 100)), para(ctl(A, 'pmh', 101))],
      header: headerXml(`<w:p>${ctl(A, 'pmh', 900)}</w:p>`),
      reason: 'member_part',
    },
    {
      name: 'a laterality-critical alias ("Right leg findings") (G1)',
      body: [heading('Findings'), ...bullets('Right leg findings', 'rlf', 3, 100)],
      concepts: { 'Right leg findings': 'past_medical_history' },
      reason: 'member_kind',
    },
    {
      name: 'bullets in fixed-grid table cells (G1)',
      body: [
        heading(A),
        `<w:tbl><w:tblGrid><w:gridCol w:w="4000"/></w:tblGrid>` +
          [100, 101, 102].map((id) => `<w:tr><w:tc><w:p>${ctl(A, 'pmh', id)}</w:p></w:tc></w:tr>`).join('') +
          `</w:tbl>`,
      ],
      reason: 'member_kind',
    },
    {
      name: 'a concept that does not accumulate (hpi.severity) (G7)',
      body: PMH_BODY as string[],
      concepts: { [A]: 'hpi.severity' },
      reason: 'member_mapping_not_list_valued',
    },
  ];

  it.each(CASES)('$name', async ({ body, header, concepts, reason }) => {
    const { ir } = await compiledForm(body, header ? { header } : {});
    const mappings = mappingsFor(ir, concepts ?? PMH_CONCEPTS);
    const analysis = analyzeBulletGroups(ir.fields, mappings);
    expect(analysis.groups).toEqual([]);
    expect(analysis.refused.map((refusal) => refusal.reason)).toEqual([reason]);
    expect(distributionIsANoOp(ir, mappings)).toBe(true);
  });

  it('unaliased, untagged "- [control]" bullets are never even a candidate', async () => {
    const { ir } = await compiledForm([heading(A), ...[100, 101, 102].map((id) => para(ctl(null, null, id)))]);
    const analysis = analyzeBulletGroups(ir.fields, mappingsFor(ir, {}));
    expect(analysis).toEqual({ groups: [], refused: [] });
  });

  it('the total-time pair (text outside, different alias AND tag) is never grouped', async () => {
    const { ir } = await compiledForm([
      para(text('Total minutes spent with patient: '), ctl('Total minutes spent with patient', 'total_minutes', 1, '____')),
      para(text('Total time minutes: '), ctl('Total time minutes', 'total_time', 2, '____')),
    ]);
    const mappings = mappingsFor(ir, {
      'Total minutes spent with patient': 'total_time_minutes',
      'Total time minutes': 'total_time_minutes',
    });
    expect(analyzeBulletGroups(ir.fields, mappings)).toEqual({ groups: [], refused: [] });
  });

  it('Impression ×4 directly followed by Plan ×5 is TWO groups, never one', async () => {
    const { ir } = await compiledForm([heading('Impression'), ...bullets('Impression', 'imp', 4, 1), ...bullets('Plan', 'plan', 5, 10)]);
    const groups = bulletGroups(ir.fields, mappingsFor(ir, { Impression: 'assessment', Plan: 'plan' }));
    expect(groups.map((group) => group.memberFieldIds.length)).toEqual([4, 5]);
    expect(groups.map((group) => group.alias)).toEqual(['Impression', 'Plan']);
  });

  it('a STORED IR compiled before #313 (property absent) forms NO group — today\'s output', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const stored = withoutSoleParagraphControl(ir);
    const mappings = mappingsFor(stored, PMH_CONCEPTS);
    const analysis = analyzeBulletGroups(stored.fields, mappings);
    expect(analysis.groups).toEqual([]);
    expect(analysis.refused.map((refusal) => refusal.reason)).toEqual(['member_not_sole_in_paragraph']);
    expect(distributionIsANoOp(stored, mappings)).toBe(true);
    // twin: the very same compile WITH the property groups.
    expect(bulletGroups(ir.fields, mappingsFor(ir, PMH_CONCEPTS))).toHaveLength(1);
  });

  // ⚠️ SHAPES THE COMPILER NEVER WRITES, CHECKED ANYWAY. The battery found
  // these two clauses masked by their siblings for every COMPILED input
  // (`tableId` and the binding's table indices come from one context; a
  // non-null alias always yields `labelSource: 'alias'`). A stored IR is data,
  // not a compile, so each clause is proved on its own.
  it('a member carrying a tableId (with no table indices) refuses the group — G1', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const bullet3 = membersByAlias(ir, PMH)[2]!.fieldId;
    const fields = ir.fields.map((field) =>
      field.fieldId === bullet3 ? { ...field, tableId: 'ttb_' + '0'.repeat(20) } : field,
    );
    const analysis = analyzeBulletGroups(fields, mappingsFor(ir, PMH_CONCEPTS));
    expect(analysis.groups).toEqual([]);
    expect(analysis.refused.map((refusal) => refusal.reason)).toEqual(['member_kind']);
  });

  it('a member whose label did NOT come from its alias refuses the group — G3', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const bullet3 = membersByAlias(ir, PMH)[2]!.fieldId;
    const fields = ir.fields.map((field) =>
      field.fieldId === bullet3 ? { ...field, labelSource: 'tag' as const } : field,
    );
    const analysis = analyzeBulletGroups(fields, mappingsFor(ir, PMH_CONCEPTS));
    expect(analysis.groups).toEqual([]);
    expect(analysis.refused.map((refusal) => refusal.reason)).toEqual(['member_identity']);
  });

  it('a NON-member field sharing a member\'s display order sits inside the run — G5', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const second = membersByAlias(ir, PMH)[1]!;
    const header = ir.fields.find((field) => field.rendererBinding.partName !== 'word/document.xml')!;
    const fields = ir.fields.map((field) =>
      field.fieldId === header.fieldId ? { ...field, displayOrder: second.displayOrder } : field,
    );
    const analysis = analyzeBulletGroups(fields, mappingsFor(ir, PMH_CONCEPTS));
    expect(analysis.groups).toEqual([]);
    expect(analysis.refused.map((refusal) => refusal.reason)).toEqual(['members_not_one_run']);
    // twin: the untouched orders group
    expect(bulletGroups(ir.fields, mappingsFor(ir, PMH_CONCEPTS))).toHaveLength(1);
  });

  it('a missing mapping on one member refuses the whole group', async () => {
    const { ir } = await compiledForm(PMH_BODY);
    const bullet3 = membersByAlias(ir, PMH)[2]!.fieldId;
    const mappings = mappingsFor(ir, PMH_CONCEPTS).filter((mapping) => mapping.fieldId !== bullet3);
    expect(analyzeBulletGroups(ir.fields, mappings).refused[0]!.reason).toBe('member_mapping_not_list_valued');
  });
});

describe('#313 A16 — the owner\'s form, rebuilt from the generator\'s vocabulary', () => {
  const HPI = '{patient} is a pleasant {age}-year-old presenting for gastro';
  const MEDS = 'The patient medications were reviewed and reconciled on EHR.';
  let nextId = 900_001;
  const S = (alias: string, tag: string, inner: string) => sdt(alias, tag, nextId++, inner);
  const run = (alias: string, tag: string, count: number) =>
    Array.from({ length: count }, () => para(S(alias, tag, '- ____')));

  const OWNER_BODY = [
    para(text('Referring MD: '), S('Referring MD', 'ref_md', '____')),
    para(text('Patient: '), S('Patient', 'patient', '____')),
    para(text('Age: '), S('Age', 'age', '__')),
    heading('HPI'),
    ...run(HPI, 'hpi_intro', 4),
    heading('Review of systems'),
    para(...ROS_CLAUSES.map(([tag, sentence]) => S(sentence.replace(/\.$/, ''), tag, sentence))),
    heading('Past Medical History'),
    ...run('Past Medical History', 'pmh', 3),
    heading('Past Surgical History'),
    ...run('Past Surgical History', 'psh', 3),
    heading('Allergies'),
    ...run('Allergies', 'allergies', 2),
    heading('Medications'),
    ...run(MEDS, 'meds', 2),
    heading('Social History'),
    ...['Tobacco', 'Alcohol', 'Recreational drugs', 'Marital status', 'Occupation'].map((label) =>
      para(text(`${label}: `), S(label, `sh_${label.toLowerCase().replace(/\W+/g, '_')}`, '____')),
    ),
    heading('Family History'),
    ...run('Family History', 'fh', 3),
    heading('Physical Exam'),
    ...EXAM_CLAUSES.map(([tag, label, value]) =>
      para(`<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">${label}</w:t></w:r>`, S(label.replace(/:\s*$/, ''), tag, value)),
    ),
    para(S('Telehealth consent', 'telehealth', 'Patient verbalized informed consent.')),
    heading('Impression'),
    ...run('Impression', 'impression', 4),
    heading('Plan'),
    ...run('Plan', 'plan', 5),
    para(text('Total minutes spent with patient: '), S('Total minutes spent with patient', 'total_minutes', '____')),
    para(text('Total time minutes: '), S('Total time minutes', 'total_time', '____')),
  ];
  const RUN_CONCEPTS: Record<string, string> = {
    [HPI]: 'chief_complaint',
    'Past Medical History': 'past_medical_history',
    'Past Surgical History': 'past_surgical_history',
    Allergies: 'allergy',
    [MEDS]: 'medication',
    'Family History': 'family_history',
    Impression: 'assessment',
    Plan: 'plan',
    'Total minutes spent with patient': 'total_time_minutes',
    'Total time minutes': 'total_time_minutes',
  };

  it('53 controls; exactly 8 groups and 26 members; nothing else grouped', async () => {
    nextId = 900_001;
    const { ir } = await compiledForm(OWNER_BODY);
    const body = ir.fields.filter((field) => field.rendererBinding.partName === 'word/document.xml');
    expect(body).toHaveLength(53);
    const groups = bulletGroups(ir.fields, mappingsFor(ir, RUN_CONCEPTS));
    expect(groups).toHaveLength(8);
    expect(groups.reduce((total, group) => total + group.memberFieldIds.length, 0)).toBe(26);
    expect(groups.map((group) => group.memberFieldIds.length)).toEqual([4, 3, 3, 2, 2, 3, 4, 5]);
    const grouped = new Set(groups.flatMap((group) => group.memberFieldIds));
    const label = (field: (typeof body)[number]) => field.rendererBinding.alias ?? '';
    // total-time, ROS, exam, social history and the telehealth line are refused
    for (const field of body) {
      const alias = label(field);
      const expected = Object.keys(RUN_CONCEPTS).includes(alias) && !alias.startsWith('Total');
      expect(grouped.has(field.fieldId), `${alias} grouped?`).toBe(expected);
    }
    // 26 bullets + the telehealth line are alone in their paragraphs — measured
    // on the owner's pinned bytes as 27 as well.
    expect(body.filter((field) => field.soleParagraphControl === true)).toHaveLength(27);
  });

  it('TWIN: the draft\'s divergent Allergies mappings refuse THAT group only — 7 and 24', async () => {
    nextId = 900_001;
    const { ir } = await compiledForm(OWNER_BODY);
    // Measured on production draft d2120cdd: the two Allergies controls carry
    // `affirmative_only` and `explicit_denial_allowed` respectively.
    const mappings = mappingsFor(ir, RUN_CONCEPTS, (field, index) =>
      field.rendererBinding.alias === 'Allergies' && index === 1
        ? { polarityBehavior: 'explicit_denial_allowed' }
        : {},
    );
    const analysis = analyzeBulletGroups(ir.fields, mappings);
    expect(analysis.groups).toHaveLength(7);
    expect(analysis.groups.reduce((total, group) => total + group.memberFieldIds.length, 0)).toBe(24);
    expect(analysis.refused).toEqual([
      expect.objectContaining({ reason: 'member_mappings_differ', key: 'polarityBehavior' }),
    ]);
  });
});
