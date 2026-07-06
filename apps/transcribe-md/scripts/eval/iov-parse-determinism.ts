// TEMP eval — parse-determinism (fix/template-parse-determinism). Parse the
// WM_IOV template N times (real Opus) and confirm ALL 28 dropdowns + both
// measurement tables survive EVERY run (deterministic). Reports per-run counts.
// Run: tsx scripts/eval/iov-parse-determinism.ts <docx> [runs]
import { readFileSync } from 'node:fs';
import { docxToText } from '../../src/lib/note-template-parse/docx-to-text';
import { parseNoteToTemplate } from '../../src/lib/note-template-parse/parse-note-to-template';

const DOCX = process.argv[2] ?? `${process.env.HOME}/WM_IOV_Template.docx`;
const RUNS = Number(process.argv[3] ?? 5);

// The 5 header/context-region dropdowns most prone to LLM drop.
const CONTEXT_PROBES = ['SIDE OF EXAM', 'REFERRING PHYSICIAN', 'ULTRASOUND TECHNOLOGIST', 'MACHINE', 'LOCATION', 'DIAGNOSIS'];

async function main() {
  const text = await docxToText(new Uint8Array(readFileSync(DOCX)));
  const srcMarkers = (text.match(/\{\{one of:/g) ?? []).length;
  console.log(`[source] extracted markers=${srcMarkers} (deterministic)`);
  const results: { markers: number; tables: number; ctx: number; ok: boolean }[] = [];
  for (let r = 1; r <= RUNS; r++) {
    const res = await parseNoteToTemplate(text, { practiceId: 'iov-det', userId: null });
    if (res.rejected) { console.log(`[run ${r}] REJECTED: ${res.reason}`); results.push({ markers: 0, tables: 0, ctx: 0, ok: false }); continue; }
    const t = res.template!;
    const allDT = t.sections.map((s) => s.defaultText ?? '').join('\n');
    const markers = (allDT.match(/\{\{one of:/g) ?? []).length;
    const tables = t.sections.filter((s) => s.structure?.kind === 'table').length;
    const ctx = CONTEXT_PROBES.filter((p) => allDT.includes(p + ':') || allDT.includes(p)).length;
    const ok = markers === srcMarkers && tables === 2 && ctx === CONTEXT_PROBES.length;
    results.push({ markers, tables, ctx, ok });
    console.log(`[run ${r}] markers=${markers}/${srcMarkers} tables=${tables}/2 contextFields=${ctx}/${CONTEXT_PROBES.length} sections=${t.sections.length}  ${ok ? 'OK' : '*** MISS ***'}`);
  }
  const allOk = results.every((r) => r.ok);
  console.log(`\n[DETERMINISM] ${results.filter((r) => r.ok).length}/${RUNS} runs preserved ALL ${srcMarkers} markers + 2 tables + all context fields → ${allOk ? 'DETERMINISTIC ✓' : 'NON-DETERMINISTIC ✗'}`);
}
main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
