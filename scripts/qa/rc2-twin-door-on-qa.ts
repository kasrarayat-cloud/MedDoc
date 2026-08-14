// ============================================================================
// RC-2 — THE TWIN DOOR, WALKED ON THE LIVE QA STACK.
// Ruling #106(b), SPEC §4.3a. The long-owed generated-document proof.
// ----------------------------------------------------------------------------
// The unit suite proves `saveNoteTemplateAction` INVOKES the compiler, against
// a mock. That is the reachability half. This is the other half: the compiler
// pointed at the REAL QA database and the REAL artifact store, doing what it
// claims — and, critically, ATTACHING to the doctor's own template rather than
// minting a shadow beside it.
//
//     upload (bytes stored) → compile (attached) → the twin tables
//
// ⚠️ WHY THIS WALK EXISTS AT ALL. Production holds zero compiled versions. The
// cause was never the compiler and never the gate: `NativeTemplateManager`
// renders **null** under `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true`, so the only
// caller of the compile path had no door in front of it. Everything written
// about the feature read as though it did. So the arms below assert the DOOR
// and the BINDING, which are the two things nobody had ever observed together.
//
// ⚠️ IT RUNS THE WORKING TREE, NOT THE QA IMAGE, AND SAYS SO. AGENTS.md's
// standing warning is that a green `--qa` migrations check says nothing about
// the QA IMAGES. This walk sidesteps that class by executing the source under
// test. What it therefore does NOT prove is that a shipped image contains this
// code; that is the deploy's own structural check.
//
// ⚠️ FAIL-CLOSED ON THE DATABASE NAME. It WRITES — a practice, a user, a note
// template, twin rows. Pointing it at production would be manufacturing rows in
// a live clinical database to prove a change works. It refuses any database
// whose name does not carry a qa/test marker.
//
// ⚠️ THE FIXTURE IS THE SANCTIONED BLANK FORM. `tests/e2e/fixtures/sample-form.docx`
// is the committed copy of the customer's BLANK template — headings, dropdown
// content controls and letterhead, no patient data (AGENTS.md, "Tracked
// fixtures"). A filled document is never a fixture and none is produced here.
//
// Usage: run inside a node container on the QA network, repo bind-mounted.
// Exit:  0 = every arm passed · 1 = FINDING · 2 = cannot tell
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

import prisma from '@meddoc/db';

import { createTemplateTwinDraft } from '../../apps/transcribe-md/src/lib/template-twin/create-draft';
import { createTemplateTwinArtifactStore } from '../../apps/transcribe-md/src/lib/template-twin/storage';

const FIXTURE = path.resolve(
  __dirname,
  '../../apps/transcribe-md/tests/e2e/fixtures/sample-form.docx',
);

let findings = 0;
const ok = (m: string) => console.log(`  🟢 ${m}`);
const bad = (m: string) => {
  findings += 1;
  console.log(`  🔴 FINDING — ${m}`);
};

function cannotTell(m: string): never {
  console.log(`🟡 CANNOT TELL — ${m}`);
  process.exit(2);
}

async function main(): Promise<void> {
  // ── 0. THE UNIVERSE ──────────────────────────────────────────────────────
  // Asserted, never stated. The RC-1 walk earned this arm.
  const [{ current_database: db }] = await prisma.$queryRawUnsafe<
    { current_database: string }[]
  >('select current_database()');
  console.log(`database: ${db}`);
  if (!/qa|test/i.test(db)) {
    cannotTell(
      `refusing to write to '${db}' — no qa/test marker in the database name. ` +
        'This walk creates rows; a production database is not a place to prove ' +
        'a change works.',
    );
  }
  ok(`database '${db}' carries a qa/test marker`);

  const cols = await prisma.$queryRawUnsafe<{ column_name: string }[]>(
    `select column_name from information_schema.columns
      where table_name = 'note_templates' and column_name like 'source%'`,
  );
  if (cols.length !== 2) {
    cannotTell(
      `note_templates carries ${cols.length} source* columns, expected 2 — the ` +
        'RC-2 migration has not been applied to this database. A walk against a ' +
        'schema that predates the feature proves nothing about the feature.',
    );
  }
  ok('the RC-2 source columns exist (sourceObjectKey, sourceSha256)');

  // ── 1. A SYNTHETIC DOCTOR ────────────────────────────────────────────────
  const stamp = randomUUID().slice(0, 8);
  const practiceId = `prac_rc2_${stamp}`;
  const userId = `user_rc2_${stamp}`;
  const email = `rc2-walk-${stamp}@qa.invalid`;

  // ⚠️ REQUIRED COLUMNS ENUMERATED FROM information_schema BEFORE WRITING, not
  // discovered one constraint violation per run. `slug` is NOT NULL here and
  // `passwordHash` is NOT NULL on users — the T3/T6 lesson, which is that the
  // set of required columns is a question for the DATABASE, not for memory.
  await prisma.$executeRawUnsafe(
    `insert into practices (id, name, slug, "createdAt", "updatedAt")
       values ($1, $2, $3, now(), now())`,
    practiceId,
    `RC-2 walk — ${stamp}`,
    `rc2-walk-${stamp}`,
  );
  // ⚠️ TWO DIFFERENT ROLE ENUMS, AND THE CHECK WATCHES THE SECOND ONE.
  // `role` is UserRole (DOCTOR/ADMIN/STAFF/SUPER_ADMIN); `practiceRole` is
  // PracticeRole (OWNER/CLINICIAN/TECH). T6's constraint
  // `users_active_member_has_practice_role` reads:
  //   isActive = false OR practiceId IS NULL OR practiceRole IS NOT NULL
  // — so an active user with a practice MUST carry a practiceRole. Read from
  // `pg_constraint`, not from memory: the two enums have no overlapping values
  // and picking the wrong one fails at the database, not the compiler.
  await prisma.$executeRawUnsafe(
    `insert into users (id, email, name, "practiceId", role, "practiceRole",
                        "isActive", "passwordHash", "createdAt", "updatedAt")
       values ($1, $2, $3, $4, 'DOCTOR', 'OWNER', true, 'x', now(), now())`,
    userId,
    email,
    'RC-2 Walk Doctor',
    practiceId,
  );
  ok(`seeded a synthetic practice and doctor (${practiceId})`);

  const templatesBefore = await prisma.noteTemplate.count({ where: { practiceId } });

  // ── 2. THE UPLOAD — bytes stored BEFORE anything is parsed ───────────────
  const bytes = new Uint8Array(readFileSync(FIXTURE));
  console.log(`fixture: ${path.basename(FIXTURE)} (${bytes.byteLength} bytes)`);

  const store = createTemplateTwinArtifactStore();
  let uploadKey: string;
  let uploadSha: string;
  try {
    const stored = await store.storeUploadArtifact({
      practiceId,
      uploadId: randomUUID(),
      bytes: Buffer.from(bytes),
    });
    uploadKey = stored.objectKey;
    uploadSha = stored.sha256;
  } catch (error) {
    cannotTell(
      `the artifact store refused the upload: ${
        error instanceof Error ? error.message : String(error)
      } — MinIO may be unreachable from this container.`,
    );
  }
  ok(`the .docx is stored BEFORE extraction (sha ${uploadSha.slice(0, 12)}…)`);

  // ── 3. THE DOCTOR'S OWN TEMPLATE — what the upload path writes ───────────
  const templateId = `tmpl_rc2_${stamp}`;
  await prisma.$executeRawUnsafe(
    `insert into note_templates
       (id, "doctorId", "practiceId", name, "encounterType", sections,
        "styleProfile", version, status, "isSystemDefault",
        "sourceObjectKey", "sourceSha256", "createdAt", "updatedAt")
     values ($1, $2, $3, $4, null, '[]'::jsonb, '{}'::jsonb, 1, 'draft', false,
             $5, $6, now(), now())`,
    templateId,
    userId,
    practiceId,
    `RC-2 walk — uploaded form ${stamp}`,
    uploadKey,
    uploadSha,
  );
  ok('the template row carries the source ref (origin provenance, not a mirror)');

  // ── 4. THE DOOR — read the bytes back, verified, and COMPILE ─────────────
  // Exactly what `saveNoteTemplateAction` now does, with the same digest check.
  const readBack = await store.readUploadArtifact({
    objectKey: uploadKey,
    practiceId,
    expectedSha256: uploadSha,
  });
  ok('the bytes read back and VERIFY against the stored digest');

  const compiled = await createTemplateTwinDraft({
    source: new Uint8Array(readBack),
    actor: { userId, userEmail: email, practiceId },
    attachToNoteTemplateId: templateId,
  });
  console.log(
    `compiled: fields=${compiled.fieldCount} blocking=${compiled.blockingUnsupportedCount} ` +
      `fallbackMappings=${compiled.usedFallbackMappings}`,
  );

  if (compiled.fieldCount > 0) ok(`the compiler extracted ${compiled.fieldCount} fillable fields`);
  else bad('the compiler extracted ZERO fields from the sanctioned blank form');

  // ── 5. THE BINDING — attached, not shadowed ──────────────────────────────
  if (compiled.noteTemplateId === templateId) {
    ok('the compiled version is bound to the DOCTOR’S OWN template');
  } else {
    bad(
      `the compiled version is bound to ${compiled.noteTemplateId}, not the ` +
        `doctor's template ${templateId} — this is the shadow-template defect`,
    );
  }

  const templatesAfter = await prisma.noteTemplate.count({ where: { practiceId } });
  if (templatesAfter === templatesBefore + 1) {
    ok(`exactly ONE template exists for this practice (${templatesAfter}) — no shadow`);
  } else {
    bad(
      `the practice holds ${templatesAfter} templates, expected ${templatesBefore + 1}. ` +
        'Compiling minted a second template beside the doctor’s own.',
    );
  }

  // ── 6. THE TWIN TABLES actually carry rows ───────────────────────────────
  const versions = await prisma.templateTwinCompiledVersion.findMany({
    where: { noteTemplateId: templateId },
    select: {
      id: true,
      practiceId: true,
      certificationStatus: true,
      blockingUnsupportedCount: true,
      _count: { select: { fields: true } },
    },
  });
  if (versions.length === 1) ok('exactly one compiled version row exists for the template');
  else bad(`${versions.length} compiled version rows exist, expected 1`);

  const v = versions[0];
  if (v) {
    if (v.practiceId === practiceId) ok('the compiled version carries the correct practice');
    else bad(`the compiled version carries practice ${v.practiceId}, expected ${practiceId}`);

    if (v._count.fields > 0) ok(`${v._count.fields} field rows persisted`);
    else bad('the compiled version persisted ZERO field rows');

    // ⚠️ NOT-CERTIFIED IS THE CORRECT OUTCOME, NOT A FAILURE. Certification
    // refuses until every field has a physician-confirmed mapping; on a real
    // customer form that is 79 of 80. AGENTS.md: never weaken the gate to
    // shrink the wall. A freshly compiled version MUST be uncertified.
    if (v.certificationStatus !== 'CERTIFIED') {
      ok(`certification status is '${v.certificationStatus}' — uncertified, as it must be`);
    } else {
      bad(
        'a freshly compiled version is CERTIFIED — nobody confirmed a mapping, ' +
          'and a certified twin nobody confirmed is worse than no twin',
      );
    }
  }

  // ── 7. THE AUDIT ROWS — a side effect nothing reads back is a comment ────
  const audits = await prisma.$queryRawUnsafe<{ action: string; n: bigint }[]>(
    `select action::text as action, count(*) as n from audit_logs
       where "practiceId" = $1 group by 1 order by 1`,
    practiceId,
  );
  const seen = new Set(audits.map((a) => a.action));
  for (const want of ['TEMPLATE_TWIN_SOURCE_UPLOADED', 'TEMPLATE_TWIN_COMPILED']) {
    if (seen.has(want)) ok(`audit row ${want} was written`);
    else bad(`audit row ${want} is MISSING — the fire-and-forget writer failed silently`);
  }

  console.log(
    findings === 0
      ? '\n🟢 RC-2 QA WALK — every arm passed'
      : `\n🔴 RC-2 QA WALK — ${findings} finding(s)`,
  );
  process.exit(findings === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  cannotTell(`the walk threw: ${error instanceof Error ? error.message : String(error)}`);
});
