// ONE MEASUREMENT — does the visit's ACTUAL DOCX carry a continuing numbering
// instance across two numbered sections? READ-ONLY; renders in memory and
// prints STRUCTURE only. No clinical prose, no artifact written to disk.
import JSZip from 'jszip';
import { loadVisitExportData } from '../../apps/transcribe-md/src/lib/visit-export-server';
import { generateVisitDocx } from '../../apps/transcribe-md/src/lib/docx-generator';

const VISIT = process.env.REPRO_VISIT!;
const PRACTICE = process.env.REPRO_PRACTICE!;

(async () => {
  const data = await loadVisitExportData(VISIT, PRACTICE);
  if (!data) { console.log('NO EXPORT DATA'); process.exit(2); }

  // The stored markers, as the builder receives them.
  const stored = (data.soapText ?? '')
    .split('\n')
    .filter((l) => /^\s*(#{1,6}\s|\d+\.)/.test(l))
    .map((l) => (l.match(/^\s*(#{1,6})\s*(.+)$/) ? `H ${l.replace(/^\s*#+\s*/, '').slice(0, 32)}` : `  ${l.trim().split(/\s/)[0]}`));
  console.log('STORED-SKELETON =>', JSON.stringify(stored));

  const buf = await generateVisitDocx(data);
  const zip = await JSZip.loadAsync(buf);
  const xml = await zip.file('word/document.xml')!.async('string');
  const numIds = [...xml.matchAll(/<w:numId w:val="(\d+)"/g)].map((m) => m[1]);
  console.log('NUMID-SEQUENCE  =>', JSON.stringify(numIds));
  console.log('DISTINCT-NUMIDS =>', JSON.stringify([...new Set(numIds)]));
  console.log('LITERAL-MARKERS-SURVIVE =>', /<w:t[^>]*>\s*\d+\./.test(xml));

  const numbering = zip.file('word/numbering.xml');
  if (numbering) {
    const nx = await numbering.async('string');
    const nums = [...nx.matchAll(/<w:num w:numId="(\d+)"[^>]*>\s*<w:abstractNumId w:val="(\d+)"/g)]
      .map((m) => ({ numId: m[1], abstract: m[2] }));
    console.log('NUMBERING-DEFS  =>', JSON.stringify(nums));
    console.log('RESTART-OVERRIDES =>', (nx.match(/<w:lvlOverride/g) ?? []).length);
  } else {
    console.log('NUMBERING-DEFS  => (no numbering.xml)');
  }
  process.exit(0);
})();
