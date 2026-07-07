// TEMP eval — parse-determinism (fix/template-parse-determinism). Parse the
// WM_IOV template N times (real Opus) and confirm ALL 28 dropdowns survive EVERY
// run (deterministic). Reports per-run counts.
// Run: tsx scripts/eval/iov-parse-determinism.ts <docx> [runs]
import { readFileSync } from 'node:fs';
import { docxToText } from '../../src/lib/note-template-parse/docx-to-text';
import { parseNoteToTemplate } from '../../src/lib/note-template-parse/parse-note-to-template';

const DOCX = process.argv[2] ?? `${process.env.HOME}/WM_IOV_Template.docx`;
const RUNS = Number(process.argv[3] ?? 5);

const MARKER_G = /\{\{one of:\s*([^}]*)\}\}/g;
/** A line's identity = the ORDERED sequence of its dropdown option-lists — the
 *  same key the reconciler uses. Robust to the LLM rewording surrounding prose
 *  or section labels (which the naive label-substring probe was not). */
function lineSeq(line: string): string {
  return [...line.matchAll(MARKER_G)]
    .map((m) => m[1].split('|').map((o) => o.trim().toLowerCase()).filter(Boolean).join('|'))
    .join(' >> ');
}
function seqSet(text: string): Set<string> {
  const s = new Set<string>();
  for (const l of text.split('\n')) {
    const q = lineSeq(l);
    if (q) s.add(q);
  }
  return s;
}

async function main() {
  const text = await docxToText(new Uint8Array(readFileSync(DOCX)));
  const srcMarkers = (text.match(/\{\{one of:/g) ?? []).length;
  const srcSeqs = seqSet(text); // every distinct source dropdown line-signature
  console.log(`[source] extracted markers=${srcMarkers}, distinct dropdown line-sigs=${srcSeqs.size} (deterministic)`);
  const results: { markers: number; seqCov: number; tables: number; ok: boolean }[] = [];
  for (let r = 1; r <= RUNS; r++) {
    const res = await parseNoteToTemplate(text, { practiceId: 'iov-det', userId: null });
    if (res.rejected) { console.log(`[run ${r}] REJECTED: ${res.reason}`); results.push({ markers: 0, seqCov: 0, tables: 0, ok: false }); continue; }
    const t = res.template!;
    const allDT = t.sections.map((s) => s.defaultText ?? '').join('\n');
    const markers = (allDT.match(/\{\{one of:/g) ?? []).length;
    const present = seqSet(allDT);
    // How many of the SOURCE dropdown signatures survived — this is the real
    // determinism guarantee (every extracted dropdown present, incl. the
    // header/context ones), immune to label/prose rewording.
    const seqCov = [...srcSeqs].filter((q) => present.has(q)).length;
    const tableSecs = t.sections.filter((s) => s.structure?.kind === 'table');
    const tables = tableSecs.length;
    const cols = tableSecs.reduce((n, s) => n + ((s.structure as { columns?: string[] }).columns?.length ?? 0), 0);
    // Determinism target: every source dropdown signature present (seqCov full)
    // AND the raw marker count matches. tables is reported for visibility only —
    // its 1-vs-2 grouping is a benign LLM structural choice (the measurement
    // value-dropdowns are within the guaranteed marker set).
    const ok = markers === srcMarkers && seqCov === srcSeqs.size;
    results.push({ markers, seqCov, tables, ok });
    console.log(`[run ${r}] markers=${markers}/${srcMarkers} dropdownSigs=${seqCov}/${srcSeqs.size} tables=${tables} tableCols=${cols} sections=${t.sections.length}  ${ok ? 'OK' : '*** MISS ***'}`);
  }
  const allOk = results.every((r) => r.ok);
  const tableCounts = [...new Set(results.map((r) => r.tables))].sort();
  console.log(`\n[DETERMINISM] ${results.filter((r) => r.ok).length}/${RUNS} runs preserved ALL ${srcMarkers} markers (every source dropdown signature) → ${allOk ? 'DETERMINISTIC ✓' : 'NON-DETERMINISTIC ✗'}`);
  console.log(`[tables] section-count across runs = {${tableCounts.join(', ')}} (grouping only; see tableCols for data preservation)`);
}
main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
