// ============================================================================
// AUTO-CERTIFICATION — THE END-TO-END WALK, ON QA
// ----------------------------------------------------------------------------
// The unit suite proves the PLAN and the REFUSALS against mocks. This is the
// other half: the real compiler, the real workspace, the real lifecycle
// transition and the real round-trip proof, against a real database.
//
//     upload (bytes stored) → compile → auto-certify → CERTIFIED
//     …and the RED half: a template whose round-trip proof FAILS must land in
//     needs-review with NOTHING certified.
//
// ⚠️ IT RUNS THE WORKING TREE, NOT THE QA IMAGE, AND SAYS SO. The image leg —
// that the WORKER actually consumes the queued job — is proved separately,
// against rebuilt QA images. This script proves the logic and its database
// effects; it does not prove the dispatch wiring.
//
// ⚠️ THE FIXTURE IS THE SANCTIONED BLANK FORM. `tests/e2e/fixtures/sample-form.docx`
// is a BLANK customer form (AGENTS.md, "Tracked fixtures"). A filled document is
// never a fixture and none is produced here.
//
// Exit: 0 all arms green · 1 FINDINGS · 2 cannot tell (wrong universe)
// ============================================================================
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

import prisma from '@meddoc/db';

import { createTemplateTwinDraft } from '@/lib/template-twin/create-draft';
import { createTemplateTwinArtifactStore } from '@/lib/template-twin/storage';
import { runAutoCertifyTwin } from '@/worker/auto-certify-twin-job';

// The sanctioned BLANK form. Overridable so the walk can run inside the QA
// container, whose image does not ship the test fixtures.
const FIXTURE =
  process.env.TWIN_WALK_FIXTURE ??
  path.resolve(__dirname, '../../tests/e2e/fixtures/sample-form.docx');

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

async function seedDoctor(tag: string) {
  const stamp = randomUUID().slice(0, 8);
  const practiceId = `prac_${tag}_${stamp}`;
  const userId = `user_${tag}_${stamp}`;
  const email = `${tag}-${stamp}@qa.invalid`;
  await prisma.$executeRawUnsafe(
    `insert into practices (id, name, slug, "createdAt", "updatedAt")
       values ($1, $2, $3, now(), now())`,
    practiceId,
    `${tag} walk — ${stamp}`,
    `${tag}-walk-${stamp}`,
  );
  await prisma.$executeRawUnsafe(
    `insert into users (id, email, name, "practiceId", role, "practiceRole",
                        "isActive", "passwordHash", "createdAt", "updatedAt")
       values ($1, $2, $3, $4, 'DOCTOR', 'OWNER', true, 'x', now(), now())`,
    userId,
    email,
    `${tag} Walk Doctor`,
    practiceId,
  );
  return { practiceId, userId, email };
}

async function uploadAndCompile(who: { practiceId: string; userId: string; email: string }) {
  const { practiceId, userId, email } = who;
  const bytes = new Uint8Array(readFileSync(FIXTURE));
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

  const templateId = `tmpl_ac_${randomUUID().slice(0, 8)}`;
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
    `auto-certify walk — uploaded form`,
    uploadKey,
    uploadSha,
  );

  const readBack = await store.readUploadArtifact({
    objectKey: uploadKey,
    practiceId,
    expectedSha256: uploadSha,
  });

  const compiled = await createTemplateTwinDraft({
    source: new Uint8Array(readBack),
    actor: { userId, userEmail: email, practiceId },
    attachToNoteTemplateId: templateId,
  });
  return { compiled, templateId, uploadKey };
}

async function main(): Promise<void> {
  // ── 0. THE UNIVERSE ──────────────────────────────────────────────────────
  const [{ current_database: db }] = await prisma.$queryRawUnsafe<
    { current_database: string }[]
  >('select current_database()');
  console.log(`database: ${db}`);
  if (!/qa|test/i.test(db)) {
    cannotTell(
      `refusing to write to '${db}' — no qa/test marker. This walk creates rows ` +
        'and certifies templates; production is not a place to prove a change works.',
    );
  }
  ok(`database '${db}' carries a qa/test marker`);

  // ── GREEN HALF ───────────────────────────────────────────────────────────
  console.log('\n── GREEN: a clean template auto-certifies ──');
  const who = await seedDoctor('ac');
  const { compiled, templateId } = await uploadAndCompile(who);
  console.log(
    `compiled: fields=${compiled.fieldCount} blocking=${compiled.blockingUnsupportedCount}`,
  );
  if (compiled.fieldCount > 0) ok(`the compiler extracted ${compiled.fieldCount} fields`);
  else bad('the compiler extracted ZERO fields from the sanctioned blank form');

  const before = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId: templateId },
    select: { certificationStatus: true },
  });
  if (before?.certificationStatus !== 'CERTIFIED') {
    ok(`freshly compiled is ${before?.certificationStatus} — not certified by compiling`);
  } else {
    bad('a freshly compiled version is already CERTIFIED — nobody confirmed anything');
  }

  // ── LEG 1: THE REFUSAL, ON WHAT THE MOCK ACTUALLY PRODUCES ───────────────
  // ⚠️ THIS IS THE REAL MOCK-UNIVERSE RESULT AND IT IS NOT A DEFECT.
  // QA runs MOCK_AI_CALLS=true and is severed from every vendor by design, so
  // the verified-note-selection step proposes no clinical concepts. 22 of the
  // 80 fields therefore arrive with none. Production's own data shows the
  // contrast: all 80 mappings on the owner's template carry a concept.
  //
  // So the first leg proves the SAFETY behaviour on real input: a template with
  // unmapped fields must not certify, and must not certify PARTIALLY.
  const res1 = await runAutoCertifyTwin({
    noteTemplateId: templateId,
    userId: who.userId,
    userEmail: who.email,
    practiceId: who.practiceId,
  });
  console.log(`auto-certify (as compiled): status=${res1.status} confirmed=${res1.confirmed} declined=${res1.declined.length}`);

  if (res1.status === 'declined') ok(`it DECLINED — ${res1.declined.length} fields carry no concept`);
  else bad(`expected 'declined' on a template with concept-less fields, got '${res1.status}'`);

  const midway = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId: templateId },
    select: { certificationStatus: true },
  });
  if (midway?.certificationStatus !== 'CERTIFIED') {
    ok(`nothing certified on a decline — still ${midway?.certificationStatus}`);
  } else {
    bad('the template CERTIFIED despite fields being declined — PARTIAL CERTIFICATION');
  }

  // ── LEG 2: THE SUCCESS ───────────────────────────────────────────────────
  // ⚠️ EXPLICIT SUBSTITUTION, STATED SO NOBODY READS THIS AS THE MODEL'S WORK.
  // The concepts below stand in for what the note-selection step proposes when
  // a real model is reachable. QA cannot reach one — that is the point of QA —
  // so the only alternatives are to substitute the model's OUTPUT here or to
  // leave the success path unproven. It is substituted, and said out loud.
  // Everything after this line is the production code path, unmodified.
  const filled = await prisma.$executeRawUnsafe(
    `update template_twin_semantic_mappings m
        set "clinicalConcept" = 'exam.vascular'
       from template_twin_field_definitions d, template_twin_compiled_versions c
      where m."fieldDefinitionId" = d.id and d."compiledVersionId" = c.id
        and c."noteTemplateId" = $1
        and m."clinicalConcept" is null
        and m."sourceType" <> 'manual'`,
    templateId,
  );
  console.log(`substituted a concept on ${filled} concept-less non-manual mappings`);

  const res = await runAutoCertifyTwin({
    noteTemplateId: templateId,
    userId: who.userId,
    userEmail: who.email,
    practiceId: who.practiceId,
  });
  console.log(`auto-certify: status=${res.status} confirmed=${res.confirmed} declined=${res.declined.length}`);

  // ⚠️ THE CEILING IS NAMED, NOT PAINTED GREEN.
  // The lifecycle gate requires the synthetic encounter to actually FILL >= 10
  // fields, one of them a measurement CELL. Under MOCK_AI_CALLS=true the note
  // generator returns canned text that resolves nothing, so 0 fields fill. That
  // is a property of the MOCK, not of the feature — and it means the CERTIFIED
  // end-state is NOT REACHABLE on this stack.
  //
  // It is reported as UNVERIFIED rather than as a finding, and ONLY for this one
  // reason string. Any other non-certified outcome is still a finding: a ceiling
  // that swallows unrelated failures is worse than no ceiling.
  const FILL_CEILING = /verify a synthetic DOCX|fillCoverage/i;
  let ceilingHit = false;

  if (res.status === 'certified') {
    ok('the job reports CERTIFIED');
  } else if (res.status === 'proof_failed' && FILL_CEILING.test(res.reason ?? '')) {
    ceilingHit = true;
    console.log(
      '  🟡 UNVERIFIED — the CERTIFIED end-state cannot be reached under MOCK_AI:\n' +
        '     the lifecycle gate needs >= 10 filled fields incl. a measurement cell,\n' +
        '     and the mock note generator fills none. Everything up to that gate ran.',
    );
  } else {
    bad(`the job reports '${res.status}' on a fully mapped template (${res.reason ?? 'no reason'})`);
  }

  const after = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId: templateId },
    select: { certificationStatus: true },
  });
  if (after?.certificationStatus === 'CERTIFIED') {
    ok('the DATABASE says CERTIFIED — not just the return value');
  } else if (ceilingHit) {
    ok(`the database left it at ${after?.certificationStatus} — consistent with the refusal, nothing half-done`);
  } else {
    bad(`the database says ${after?.certificationStatus}, the job said ${res.status}`);
  }

  const pending = await prisma.templateTwinSemanticMapping.count({
    where: {
      fieldDefinition: { compiledVersion: { noteTemplateId: templateId } },
      mappingStatus: { not: 'CERTIFIED' },
    },
  });
  if (pending === 0) ok('every mapping is confirmed — 0 left at NEEDS_CONFIRMATION');
  else bad(`${pending} mappings remain unconfirmed on a template the job called ${res.status}`);

  // ── THE AUDIT ROW, READ BACK ─────────────────────────────────────────────
  // A fire-and-forget writer is proved only by a test that READS IT BACK.
  const rows = await prisma.$queryRawUnsafe<{ action: string; metadata: unknown }[]>(
    `select action::text, metadata from audit_logs
      where "practiceId" = $1 and action::text like 'TEMPLATE_TWIN%'
      order by "timestamp" desc limit 20`,
    who.practiceId,
  );
  if (rows.length > 0) ok(`${rows.length} twin audit rows written`);
  else bad('NO audit row was written for an auto-certification');

  const meta = JSON.stringify(rows.map((r) => r.metadata));
  if (/"auto":true/.test(meta.replace(/\s/g, ''))) ok('the audit row marks the action as automatic');
  else bad('no audit row carries auto:true — an AI certification is indistinguishable from a human one');

  if (/proposedByModel/.test(meta)) ok('the audit row names the PROPOSING MODEL (the ruled signal)');
  else bad('no audit row names the proposing model');

  // ⚠️ THE PROVENANCE LABEL MUST NOT CLAIM A HUMAN. Measured on production:
  // every `sourceType: 'manual'` row is model-proposed with no approver.
  if (/"manual":/.test(meta)) {
    bad("an audit row records provenance 'manual' — that reads as human attestation");
  } else {
    ok("no audit row attributes a mapping to a human ('manual' provenance absent)");
  }

  // ── RED HALF: the round-trip proof must be able to REFUSE ────────────────
  console.log('\n── RED: a template whose round-trip proof fails must NOT certify ──');
  const who2 = await seedDoctor('acred');
  const { templateId: templateId2 } = await uploadAndCompile(who2);

  // ⚠️ THE RED ARM MUST REACH THE PROOF, OR IT MEASURES THE WRONG REFUSAL.
  // The first run of this walk reported a green here on `fields_need_confirmation`
  // — the template declined for UNMAPPED FIELDS and never consulted the source
  // artifact at all. The corruption below was never exercised, and the arm was
  // vacuous while printing a tick. Map it first, exactly as leg 2 does, so the
  // ONLY thing left that can refuse is the round-trip proof itself.
  await prisma.$executeRawUnsafe(
    `update template_twin_semantic_mappings m
        set "clinicalConcept" = 'exam.vascular'
       from template_twin_field_definitions d, template_twin_compiled_versions c
      where m."fieldDefinitionId" = d.id and d."compiledVersionId" = c.id
        and c."noteTemplateId" = $1
        and m."clinicalConcept" is null
        and m."sourceType" <> 'manual'`,
    templateId2,
  );

  // ⚠️ A REAL FAILURE, NOT A MOCKED ONE. Deleting the stored source artifact
  // makes the round-trip proof genuinely unable to read the bytes it must
  // compare against. The refusal that follows is the production code path
  // refusing, not a stub returning a rejection.
  // ⚠️ THE MUTATION TARGETS WHAT THE PROOF ACTUALLY READS.
  // `runTemplateTwinSyntheticTest` reads `compiled.sourceArtifact` — NOT
  // `note_templates.sourceObjectKey`. An earlier draft of this walk corrupted the
  // latter, which the proof never consults: it would have certified, and this arm
  // would have reported a false FINDING while looking like it had tested
  // something. Corrupting the artifact's DIGEST makes the store's own integrity
  // check refuse, which is production code refusing for a production reason.
  const corrupted = await prisma.$executeRawUnsafe(
    `update template_twin_source_artifacts set sha256 = $1
      where id = (select "sourceArtifactId" from template_twin_compiled_versions
                   where "noteTemplateId" = $2 order by "compiledAt" desc limit 1)`,
    '0'.repeat(64),
    templateId2,
  );
  if (corrupted !== 1) {
    cannotTell(
      `the digest mutation touched ${corrupted} rows, expected 1 — this arm cannot ` +
        'distinguish a refusal from a no-op, so its result would mean nothing.',
    );
  }
  ok('the source artifact digest was corrupted (1 row) — the proof must now refuse');

  const res2 = await runAutoCertifyTwin({
    noteTemplateId: templateId2,
    userId: who2.userId,
    userEmail: who2.email,
    practiceId: who2.practiceId,
  });
  console.log(`auto-certify (broken): status=${res2.status} reason=${res2.reason ?? '-'}`);

  if (res2.status === 'proof_failed') {
    ok(`the ROUND-TRIP PROOF refused — status '${res2.status}'`);
  } else if (res2.status === 'declined') {
    bad(
      `it refused with 'declined' (${res2.reason ?? 'no reason'}) — that is the ` +
        'MAPPING gate, not the round-trip proof. This arm did not test what it claims.',
    );
  } else {
    bad('the job CERTIFIED a template whose source artifact fails its own digest');
  }

  const after2 = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId: templateId2 },
    select: { certificationStatus: true },
  });
  if (after2?.certificationStatus !== 'CERTIFIED') {
    ok(`the database left it at ${after2?.certificationStatus} — nothing half-certified`);
  } else {
    bad('the database says CERTIFIED after a failed proof — THE FEATURE IS UNSAFE');
  }

  console.log(
    `\n${findings === 0 ? '🟢 ALL ARMS GREEN' : `🔴 ${findings} FINDING(S)`}`,
  );
  process.exit(findings === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error('walk FAILED:', e instanceof Error ? e.stack : e);
  process.exit(2);
});
