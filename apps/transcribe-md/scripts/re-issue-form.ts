// ============================================================================
// THE RULED RE-ISSUE ACT — ruling #263, executed through
// `run-ruled-mutation.sh --in transcribe-md-worker` under a COMMITTED
// declaration.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE IS DELIBERATELY THIN, AND THAT IS THE POINT. Every decision that
// can put a clinical meaning on the wrong control lives in `planTransfer`,
// which took FIVE refutation rounds and five blocking defects to settle. This
// wrapper reads bytes, states guards, calls it, and prints. It must never grow
// a rule of its own — a second place deciding what transfers is the "one rule,
// many readers" failure this repository has paid for repeatedly.
//
// ── WHY IT EXISTS AT ALL ────────────────────────────────────────────────────
// #274 shipped `ingestTemplateTwin` as a library function with ZERO callers.
// The seam was built and the door was not, so the ruled act had nothing to
// invoke. Found by checking the worker before the act rather than during it.
//
// ── EVERY ARGUMENT IS REQUIRED ──────────────────────────────────────────────
// No defaults, on purpose. A default is a value nobody declared, and this act
// is irreversible. The declaration names each of these numbers; passing them
// explicitly is what lets the transcript be compared against it.
// ============================================================================
import { createHash } from 'node:crypto';

import prisma from '@meddoc/db';

import {
  ingestTemplateTwin,
  TemplateTwinIngestRefused,
} from '../src/lib/template-twin/ingest';
import { readVerifiedZipPackage } from '../src/lib/note-template-docx/zip-directory';
import { createTemplateTwinArtifactStore } from '../src/lib/template-twin/storage/artifact-store';

function die(message: string): never {
  console.error(`🔴 re-issue: ${message}`);
  console.error('   Nothing was written.');
  process.exit(1);
}

function arg(name: string): string {
  const i = process.argv.indexOf(`--${name}`);
  if (i < 0 || i + 1 >= process.argv.length) die(`missing required argument --${name}`);
  const v = process.argv[i + 1]!;
  if (v.startsWith('--') || v.trim() === '') die(`--${name} needs a value`);
  return v;
}

function intArg(name: string): number {
  const raw = arg(name);
  // ⚠️ STRICT. `parseInt('53x')` is 53, and a count that silently accepts
  // garbage is a guard that reports a number nobody meant.
  if (!/^\d+$/.test(raw)) die(`--${name} must be a plain integer, got '${raw}'`);
  return Number(raw);
}

/**
 * ⚠️ A RECORDED MEASUREMENT, NOT A GATE — owner-ruled.
 *
 * Counts `w:tag` attributes across the package's XML parts. It settles whether
 * the owner's form is 18/53 tagged (what the repository can prove: the controls
 * `regenerate-consult-form.ts` adds) or 53/53 (what the ruling states). The
 * number decides how wide TAG-ON-INGEST has to be; it must NEVER abort the act.
 *
 * ⚠️ IT COUNTS THE ARTIFACT'S OWN XML, not the compiled IR, because the question
 * is about the DOCUMENT the doctor's form is, not about what this compiler
 * currently makes of it. `parts` is reported so a zero cannot be read as "no
 * tags" when it might be "nothing was inflated".
 */
function countTagAttributes(bytes: Buffer): { tags: number; sdts: number; parts: number } {
  // ⚠️ THE PACKAGE MUST BE INFLATED FIRST, AND MY FIRST DRAFT DID NOT.
  // A `.docx` is a ZIP: `<w:tag` lives in DEFLATED bytes, so a regex over the
  // raw buffer finds approximately zero and would have "settled" the 18-vs-53
  // question with a fabricated 0 — an instrument reporting confidently about a
  // universe it never opened. `readVerifiedZipPackage` is the repository's own
  // reader and it verifies each entry's CRC, so a corrupt part is an error
  // rather than a silently short count.
  const pkg = readVerifiedZipPackage(bytes, {
    maxEntries: 4096,
    maxTotalUncompressedBytes: 256 * 1024 * 1024,
  });
  let tags = 0;
  let sdts = 0;
  let parts = 0;
  for (const [name, entry] of pkg.entries) {
    if (!name.endsWith('.xml')) continue;
    parts += 1;
    const xml = entry.bytes.toString('utf8');
    tags += (xml.match(/<w:tag\b/g) ?? []).length;
    sdts += (xml.match(/<w:sdt>/g) ?? []).length;
  }
  return { tags, sdts, parts };
}

async function main(): Promise<void> {
  const artifactId = arg('artifact-id');
  const transferFrom = arg('transfer-from');
  const practiceId = arg('practice-id');
  const userId = arg('user-id');
  const userEmail = arg('user-email');
  const expectSha = arg('expect-sha256');
  const expectFields = intArg('expect-fields');
  const expectTransfer = intArg('expect-transfer');

  console.log('=== RE-ISSUE — ruling #263 ===');
  console.log(`   artifact      ${artifactId}`);
  console.log(`   transfer from ${transferFrom}`);
  console.log(`   expect        ${expectFields} fields, ${expectTransfer} transferred`);
  console.log(`   expect sha    ${expectSha}`);

  // ── read the stored bytes. The store verifies the digest itself. ──────────
  const artifact = await prisma.templateTwinSourceArtifact.findUnique({
    where: { id: artifactId },
    select: { objectKey: true, sha256: true, sizeBytes: true, practiceId: true },
  });
  if (!artifact) die(`artifact ${artifactId} not found`);
  if (artifact.practiceId !== practiceId) die('artifact belongs to a different practice');
  if (artifact.sha256 !== expectSha) {
    die(`PRE-GUARD 1 FAILED — stored sha ${artifact.sha256} != declared ${expectSha}`);
  }

  // ⚠️ `objectKey` IS NULLABLE, AND A NULL HERE IS A REFUSAL, NOT A CAST.
  // An artifact row whose object key is absent describes bytes nothing can
  // fetch; `!` would turn that into a runtime failure halfway through an
  // irreversible act instead of a refusal before it starts.
  if (!artifact.objectKey) die(`artifact ${artifactId} has no objectKey — its bytes are unreachable`);

  const store = createTemplateTwinArtifactStore();
  const bytes = await store.readSourceArtifact({
    practiceId,
    objectKey: artifact.objectKey,
    expectedSha256: artifact.sha256,
    expectedSizeBytes: artifact.sizeBytes,
  });

  const actual = createHash('sha256').update(bytes).digest('hex');
  if (actual !== expectSha) die(`bytes read back as ${actual}, declared ${expectSha}`);
  console.log(`   ✓ PRE-GUARD 1 — artifact bytes sha256 matches the declaration`);

  // ── the certified source's field ids, for the set-equality guard ──────────
  const source = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: transferFrom },
    select: { practiceId: true, fields: { select: { fieldId: true } } },
  });
  if (!source) die(`transfer source ${transferFrom} not found`);
  if (source.practiceId !== practiceId) die('transfer source belongs to a different practice');
  const expectFieldIds = source.fields.map((f) => f.fieldId);
  if (expectFieldIds.length !== expectFields) {
    die(`PRE-GUARD 2 FAILED — source has ${expectFieldIds.length} fields, declared ${expectFields}`);
  }
  console.log(`   ✓ source carries ${expectFieldIds.length} field ids`);

  // ⚠️ THE MEASUREMENT, TAKEN BEFORE THE ACT so it is recorded even if the act
  // refuses. It gates nothing.
  const census = countTagAttributes(bytes);
  console.log('=== RECORDED MEASUREMENT — not a gate ===');
  console.log(`   w:tag attributes on the artifact : ${census.tags}`);
  console.log(`   w:sdt controls on the artifact   : ${census.sdts}`);
  console.log(`   xml parts inflated and scanned   : ${census.parts}`);
  console.log(`   declared expectation was: tagged >= 18`);
  console.log(`   ⚠️ this settles the 18-vs-53 premise for TAG-ON-INGEST and`);
  console.log(`      MUST NOT abort the act whatever it says.`);

  // ── the act ───────────────────────────────────────────────────────────────
  try {
    const result = await ingestTemplateTwin({
      source: bytes,
      actor: { userId, userEmail, practiceId },
      transferFrom,
      guards: {
        expectSourceSha256: expectSha,
        expectFieldIds,
        expectTransferCount: expectTransfer,
      },
    });
    console.log('=== RESULT ===');
    console.log(`   new note template  ${result.noteTemplateId}`);
    console.log(`   source sha256      ${result.sourceSha256}`);
    console.log(`   fields             ${result.fieldCount}`);
    console.log(`   transferred        ${result.transferred}`);
    console.log(`   re-proposed        ${result.reproposed}`);
    console.log('');
    console.log('   ⚠️ NOTHING WAS CERTIFIED AND NOTHING WAS ACTIVATED.');
    console.log('      The new template is a DRAFT. The owner confirms the rows,');
    console.log('      then certification and activation run as their own acts.');
  } catch (error) {
    if (error instanceof TemplateTwinIngestRefused) {
      die(`REFUSED before acting — ${JSON.stringify(error.failure)}`);
    }
    throw error;
  }
}

// ⚠️ ONLY WHEN INVOKED DIRECTLY — importing this module must never run the act.
// A bare `void main()` at module scope executed a production script on import
// once already this session; canon 143 records what it cost to notice.
const invokedDirectly = (() => {
  const entry = process.argv[1];
  return Boolean(entry && /re-issue-form\.(ts|js)$/.test(entry));
})();

if (invokedDirectly) {
  void main().catch((error) => {
    console.error('🔴 re-issue: UNEXPECTED failure');
    console.error(error);
    process.exit(1);
  });
}
