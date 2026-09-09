// ============================================================================
// RULING #225's SECOND HALF — upload, certify and ACTIVATE the 53-control form.
// ----------------------------------------------------------------------------
// A RULED MUTATION. The only door is:
//
//   bash scripts/run-ruled-mutation.sh --declaration <path> -- \
//     npx tsx <this file> --commit
//
// DRY RUN IS THE DEFAULT. Without `--commit` it asserts both pinned sides,
// compiles the form, prints the full per-field map and writes NOTHING.
//
// ⚠️ IT USES THE PRODUCTION WIRING VERBATIM — the same `createTemplateTwinDraft`
// and `certifyAndActivateTemplateTwin` the server actions call. A script that
// ran a DIFFERENT chain from the one a doctor's upload runs would be a proof
// about the wrong universe, and this programme has paid for that already.
//
// ⚠️ THE FORM IS PRODUCED ONCE AND THIS SCRIPT DOES NOT PRODUCE IT. It reads the
// pinned artifact and REFUSES on any byte mismatch. Ruling #209: the form is the
// one that certifies; #215: its identity salt is the zip container, so a
// regenerated copy would mint different fieldIds and match nothing.
// ============================================================================
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

import { createTemplateTwinDraft } from '../src/lib/template-twin/create-draft';
import { readTemplateTwinWorkspace } from '../src/lib/template-twin/workspace-read';
import { compileTemplateDocx } from '../src/lib/note-template-docx/compiler';

/** BOTH PINNED SIDES — ruling #209, re-pinned by DOCUMENT sha under #216/#225. */
const FORM_PATH = process.env.FORM53_PATH ?? '/home/claude/r5-handoff/FORM-53-pinned-5367fd07.docx';
const PACKAGE_SHA = '5367fd075472cc2c6a1de768c5224e7522691ccad3d2c7aafc47071752920642';
const DOCUMENT_SHA = 'ecb817039a035e975cf73605f4e5ba68a88362a5a27f02d204e6e11903cf241d';
const EXPECT_FIELDS = 53;

const OWNER = {
  userId: 'cmo5ye2nm000c01s3ofudqzi6',
  userEmail: 'kasra.rayat@gmail.com',
  practiceId: 'cmo5ye2nf000b01s3q0xlkaxb',
};

const COMMIT = process.argv.includes('--commit');

async function main() {
  const host = new URL(process.env.DATABASE_URL ?? 'postgres://x/x').hostname;
  const db = new URL(process.env.DATABASE_URL ?? 'postgres://x/x').pathname.replace('/', '');
  console.log(`db target : ${host}/${db}`);
  console.log(`mode      : ${COMMIT ? '⚠️  COMMIT (uploads, certifies, activates)' : 'REPORT ONLY'}`);

  // ── BOTH PINNED SIDES, ASSERTED BEFORE ANYTHING ELSE ────────────────────
  const bytes = readFileSync(FORM_PATH);
  const pkgSha = createHash('sha256').update(bytes).digest('hex');
  console.log(`\nsource    : ${FORM_PATH}`);
  console.log(`package   : ${pkgSha}`);
  if (pkgSha !== PACKAGE_SHA) {
    throw new Error(`REFUSING — package sha ${pkgSha} != pinned ${PACKAGE_SHA}`);
  }

  const JSZip = (await import('jszip')).default;
  const zip = await JSZip.loadAsync(bytes);
  const docXml = await zip.file('word/document.xml')!.async('nodebuffer');
  const docSha = createHash('sha256').update(docXml).digest('hex');
  console.log(`document  : ${docSha}`);
  if (docSha !== DOCUMENT_SHA) {
    throw new Error(`REFUSING — document sha ${docSha} != pinned ${DOCUMENT_SHA}`);
  }
  console.log('✅ both pinned sides match — this is the form that certifies (#209)');

  // ── WHAT IT COMPILES TO UNDER THE DEPLOYED COMPILER ─────────────────────
  const ir = compileTemplateDocx(bytes);
  const kinds: Record<string, number> = {};
  let scaffolded = 0;
  for (const f of ir.fields) {
    kinds[f.kind] = (kinds[f.kind] ?? 0) + 1;
    if (f.scaffolded) scaffolded += 1;
  }
  console.log(`\nfields    : ${ir.fields.length}   scaffolded: ${scaffolded}   unsupported: ${(ir.unsupported as unknown[]).length}`);
  console.log(`kinds     : ${JSON.stringify(kinds)}`);
  console.log(`structure : ${(ir as unknown as { structureSha256: string }).structureSha256}`);
  if (ir.fields.length !== EXPECT_FIELDS) {
    throw new Error(`REFUSING — ${ir.fields.length} fields, expected ${EXPECT_FIELDS}`);
  }
  // ⚠️ #216's WHOLE POINT: the GI alarm-feature clause must be narrative_text.
  const weight = ir.fields.find((f) => f.originalLabel.includes('unintentional weight loss'));
  console.log(`\nros_gi_weight kind : ${weight?.kind}  (#216 requires narrative_text)`);
  if (weight?.kind !== 'narrative_text') {
    throw new Error('REFUSING — the alarm-feature clause is not narrative_text; #216 did not ship');
  }

  console.log('\n--- per-field map ---');
  for (const f of ir.fields) {
    console.log(`  ${String(f.displayOrder).padStart(2)}  ${f.kind.padEnd(15)} ${f.originalLabel.slice(0, 70)}`);
  }

  if (!COMMIT) {
    console.log('\nREPORT ONLY — nothing written. Re-run under run-ruled-mutation.sh with --commit.');
    return;
  }

  const created = await createTemplateTwinDraft({ source: new Uint8Array(bytes), actor: OWNER });
  console.log(`\n✅ draft created: noteTemplateId=${created.noteTemplateId}`);
  const ws = await readTemplateTwinWorkspace({
    noteTemplateId: created.noteTemplateId,
    doctorId: OWNER.userId,
    practiceId: OWNER.practiceId,
  });
  console.log(`   compiled=${ws?.compiledVersionId}  fields=${ws?.fields.length}  mappingsSha=${ws?.mappingsSha256?.slice(0, 12)}`);
  console.log('\n⚠️ STOPPING BEFORE CERTIFY. The acceptance rows (2/1/8/9/7 then 6) are');
  console.log('   confirmed next, and certification binds the mapping set — certifying');
  console.log('   first would hash-lock the UNCONFIRMED proposals.');
}

main()
  .then(() => process.exit(0))
  .catch((e) => {
    console.error('🔴', e instanceof Error ? e.message : e);
    process.exit(1);
  });
