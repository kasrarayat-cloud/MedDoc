// ============================================================================
// RULING #225's SECOND HALF, STEP 2 — confirm, CERTIFY and ACTIVATE.
// ----------------------------------------------------------------------------
// A RULED MUTATION. Same declaration as step 1:
//   docs/foundation/mutations/20260907-form53-transfer-certify.md
//
// ⚠️ THE CORRECTIONS BELOW ARE A CLINICAL SAFETY ACT, NOT BOOKKEEPING.
// The proposer mapped `Past Surgical History` -> `past_medical_history` and
// `Marital status` -> `social_history.occupation`. Certifying those AS PROPOSED
// would print the patient's medical history into a SURGICAL history field and
// their occupation into MARITAL STATUS. Both are wrong facts in a signed note.
//
// The correct concepts do not exist: measured through `isRegisteredConcept`,
// `past_surgical_history`, `social_history.marital_status`, `visit_metadata`
// (even bare) and any total-time concept are ALL REFUSED by the closed
// registry. Until they exist, these fields are `manual` — a per-visit human
// value that renders blank and is attested — which is the honest outcome and
// the one the 35-control template already uses for its administrative fields.
// ============================================================================
import prisma from '@meddoc/db';

import { readTemplateTwinWorkspace } from '../src/lib/template-twin/workspace-read';
import {
  updateTemplateTwinMappings,
  certifyAndActivateTemplateTwin,
} from '../src/lib/template-twin/certification-lifecycle';
import type { SemanticMapping } from '../src/lib/template-twin/ir';

const NOTE_TEMPLATE_ID = '939aa9ea-2f03-41d5-881f-026445e959c1';
const OWNER = {
  userId: 'cmo5ye2nm000c01s3ofudqzi6',
  userEmail: 'kasra.rayat@gmail.com',
  practiceId: 'cmo5ye2nf000b01s3q0xlkaxb',
};
const COMMIT = process.argv.includes('--commit');

/** displayOrder -> why it becomes `manual`. The registry cannot express these yet. */
const TO_MANUAL: Record<number, string> = {
  1: 'Referring MD — acceptance row 7; visit_metadata is REFUSED by the registry',
  2: 'Patient — acceptance row 7; same',
  3: 'Age — acceptance row 7; same',
  22: 'Past Surgical History — acceptance row 2; past_surgical_history REFUSED. Proposed past_medical_history would print the WRONG history',
  23: 'Past Surgical History — same',
  24: 'Past Surgical History — same',
  36: 'Marital status — acceptance row 9; social_history.marital_status REFUSED. Proposed social_history.occupation would print the WRONG fact',
  56: 'Telehealth consent — acceptance row 6; omitted when unsupported',
  70: 'Total minutes spent with patient — acceptance row 8; no time concept is registered',
  71: 'Total time minutes — acceptance row 8; the second render of the same datum',
};
/** Acceptance row 6 — the one policy #194 left standing. */
const OMIT_ON = new Set([56]);

async function main() {
  console.log(`mode: ${COMMIT ? '⚠️  COMMIT (confirms, certifies, ACTIVATES)' : 'REPORT ONLY'}`);
  const ws = await readTemplateTwinWorkspace({
    noteTemplateId: NOTE_TEMPLATE_ID,
    doctorId: OWNER.userId,
    practiceId: OWNER.practiceId,
  });
  if (!ws) throw new Error('workspace not found');
  console.log(`fields=${ws.fields.length}  mappingsSha=${ws.mappingsSha256}`);

  // ⚠️ THE WORKSPACE FIELD IS { definitionId, field, mapping } — displayOrder,
  // fieldId and originalLabel live under `.field`, NOT on the row itself. The
  // first version of this script read them off the row, every lookup was
  // `undefined`, and NOT ONE correction applied. It printed `manual: 0`, which
  // is the only reason it was caught: a --commit run would have certified
  // `Past Surgical History -> past_medical_history` and
  // `Marital status -> social_history.occupation` exactly as proposed.
  type Row = { field: { fieldId: string; displayOrder: number; originalLabel: string }; mapping: SemanticMapping };
  const rows = ws.fields as unknown as Row[];

  const next: SemanticMapping[] = rows.map((r) => {
    const m = { ...r.mapping };
    const d = r.field.displayOrder;
    if (TO_MANUAL[d]) {
      m.sourceType = 'manual';
      m.clinicalConcept = null;
      m.approvedSynonyms = [];
    }
    if (OMIT_ON.has(d)) m.unmentionedPolicy = 'omit';
    m.status = 'certified';
    return m;
  });

  console.log('\n--- what this sets ---');
  for (const r of rows) {
    const d = r.field.displayOrder;
    if (!TO_MANUAL[d] && !OMIT_ON.has(d)) continue;
    const m = next.find((x) => x.fieldId === r.field.fieldId)!;
    console.log(`  ${String(d).padStart(2)} ${r.field.originalLabel.slice(0, 42).padEnd(42)} src=${m.sourceType} concept=${m.clinicalConcept ?? '(none)'} policy=${m.unmentionedPolicy ?? '(null)'}`);
    console.log(`     was: ${r.mapping.clinicalConcept ?? '(none)'}   why: ${TO_MANUAL[d] ?? 'omit policy only'}`);
  }
  // ⚠️ ASSERT THE EDIT APPLIED. A correction that silently matches nothing is
  // the failure this script already had once.
  const expected = Object.keys(TO_MANUAL).length;
  const applied = next.filter((m) => m.sourceType === 'manual').length;
  console.log(`\ncorrections expected ${expected} / applied ${applied}`);
  if (applied !== expected) throw new Error(`REFUSING — ${applied} of ${expected} corrections applied`);
  const omits = next.filter((m) => m.unmentionedPolicy === 'omit').length;
  if (omits !== OMIT_ON.size) throw new Error(`REFUSING — ${omits} of ${OMIT_ON.size} omit policies applied`);
  const manual = next.filter((m) => m.sourceType === 'manual').length;
  console.log(`\nmanual: ${manual}   extraction: ${next.length - manual}   omit-policy: ${next.filter((m) => m.unmentionedPolicy === 'omit').length}`);

  if (!COMMIT) {
    console.log('\nREPORT ONLY — nothing written.');
    return;
  }

  const afterUpdate = await updateTemplateTwinMappings({
    noteTemplateId: NOTE_TEMPLATE_ID,
    actor: OWNER,
    expectedMappingsSha256: ws.mappingsSha256,
    mappings: next,
  });
  console.log(`\n✅ mappings confirmed. new mappingsSha=${afterUpdate.mappingsSha256}`);

  const certified = await certifyAndActivateTemplateTwin({
    noteTemplateId: NOTE_TEMPLATE_ID,
    actor: OWNER,
    expectedMappingsSha256: afterUpdate.mappingsSha256,
  });
  console.log(`✅ CERTIFIED and ACTIVATED. status=${certified.certificationStatus}`);
}

main()
  .then(async () => { await prisma.$disconnect(); process.exit(0); })
  .catch(async (e) => {
    console.error('🔴', e instanceof Error ? `${e.name}: ${e.message}` : e);
    await prisma.$disconnect().catch(() => {});
    process.exit(1);
  });
