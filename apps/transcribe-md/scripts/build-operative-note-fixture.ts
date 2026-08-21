/**
 * Regenerate the BLANK operative-note E2E fixture from its tracked source.
 *
 *     cd apps/transcribe-md && npx tsx scripts/build-operative-note-fixture.ts
 *
 * ⚠️ THE .docx IS AN ARTIFACT; `operative-note-source.ts` IS THE SOURCE.
 * Never hand-edit the binary. `gate-f5i-second-shape-refuses-honestly.test.ts`
 * compiles BOTH the committed file and an in-memory build from the source and
 * asserts they yield the identical field set, so a hand-edit would redden CI
 * rather than sit there undetected.
 *
 * ⚠️ IT OVERWRITES RATHER THAN APPENDS. AGENTS.md records a regeneration that
 * PREPENDED its output and left the previous copy below it, producing a file
 * that still contained every value anyone asserted and did not parse.
 * `writeFileSync` replaces the whole file; there is no append path here, and
 * there must not be one.
 *
 * The fixture is BLANK — prompts, never values. A filled document is never a
 * fixture.
 */
import { writeFileSync } from 'node:fs';
import path from 'node:path';

import { buildOperativeNoteDocx } from '../src/lib/template-twin/__tests__/fixtures/operative-note-source';

const OUT = path.resolve(
  __dirname,
  '..',
  'tests',
  'e2e',
  'fixtures',
  'sample-operative-note.docx',
);

async function main(): Promise<void> {
  const bytes = await buildOperativeNoteDocx();
  writeFileSync(OUT, bytes);
  console.log(`wrote ${OUT} (${bytes.length} bytes)`);
}

void main();
