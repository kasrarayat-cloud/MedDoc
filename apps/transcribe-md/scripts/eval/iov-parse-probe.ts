// TEMP eval — parse the WM_IOV content-control template in-process (real Opus).
// Proves the docx-content-control extraction + marker preservation end-to-end.
// Run: tsx scripts/eval/iov-parse-probe.ts <path-to-docx>
import { readFileSync } from 'node:fs';
import { docxToText } from '../../src/lib/note-template-parse/docx-to-text';
import { parseNoteToTemplate } from '../../src/lib/note-template-parse/parse-note-to-template';

async function main() {
  const path = process.argv[2];
  const bytes = new Uint8Array(readFileSync(path));
  const text = await docxToText(bytes);
  const markerCount = (text.match(/\{\{one of:/g) ?? []).length;
  console.log(`[extract] chars=${text.length} markers=${markerCount}`);

  const res = await parseNoteToTemplate(text, { practiceId: 'iov-eval', userId: null });
  if (res.rejected) {
    console.log('[parse] REJECTED:', res.reason);
    return;
  }
  const t = res.template!;
  console.log(`[parse] name=${JSON.stringify(t.name)} encounterType=${JSON.stringify(t.encounterType)} sections=${t.sections.length}`);
  console.log(`[parse] flags=${JSON.stringify((res as any).flags ?? [])}`);
  let totalMarkersInSections = 0;
  for (const s of t.sections) {
    const dt = s.defaultText ?? '';
    const m = (dt.match(/\{\{one of:/g) ?? []).length;
    totalMarkersInSections += m;
    const struct = s.structure ? `${s.structure.kind}(${s.structure.kind === 'options' ? s.structure.options.length + ' opts' : s.structure.columns.length + ' cols'})` : '-';
    console.log(`\n  §${s.order} ${JSON.stringify(s.label)}  markers=${m} structure=${struct} fmt=${s.formatHint}`);
    if (dt) console.log('    defaultText:', JSON.stringify(dt.length > 400 ? dt.slice(0, 400) + '…' : dt));
    if (s.styleInstructions) console.log('    style:', JSON.stringify(s.styleInstructions.slice(0, 160)));
  }
  console.log(`\n[summary] markers preserved into sections: ${totalMarkersInSections} / ${markerCount} extracted`);
  const outPath = process.argv[3];
  if (outPath) {
    const { writeFileSync } = await import('node:fs');
    writeFileSync(outPath, JSON.stringify(t, null, 2));
    console.log('[wrote]', outPath);
  }
}
main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
