// ============================================================================
// RULING #274 · THE CORPUS — BOTH REAL DOCUMENTS, FIVE TRANSFORMATIONS EACH.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE SAME MISTAKE WAS MADE THREE TIMES: a property
// measured on ONE document and stated as universal.
//
//   ROUND 1 · the key was positional (`path` + `ordinal`). Inserting one control
//     into `WM IOV Template.docx` mis-paired 3 of 3 certified dispositions.
//   ROUND 2 · the replacement claimed "a collision never mis-transfers". False:
//     two controls sharing a key both claimed one certified row, and a LEFT leg
//     finding was certified to print the RIGHT leg's concept.
//   ROUND 3 · `sdtId` was called STABLE on the strength of `28/80, 28 distinct`
//     — measured on WM IOV, whose ids are Word-generated randoms. The OWNER'S
//     form assigns them with `nextId += 1` per control IN DOCUMENT ORDER, so a
//     single dropped clause renumbered everything and walked the exam narrative
//     one organ system sideways, 15 rows, all `certified`.
//
//     A CLAIM MEASURED ON ONE DOCUMENT IS NOT A CLAIM.
//
// So the corpus is BOTH real documents, and every transformation asserts ZERO
// mis-pairs — not a transfer count, which is the number that stayed right while
// the pairing was wrong in all three rounds.
//
// ── ON THE SECOND DOCUMENT'S PROVENANCE, STATED PLAINLY ─────────────────────
// The owner's blank 53-control source is NOT in this repository; only production
// holds those bytes, and `regenerate-consult-form.ts` refuses any others by sha.
// So its arm is built from the generator's OWN exported vocabulary — `sdt()`,
// `ROS_CLAUSES`, `EXAM_CLAUSES`, `FIRST_ADDED_SDT_ID` — imported, never retyped.
// That is what makes it evidence: the id progression under test is the shipped
// one, and a fixture free to get `nextId += 1` wrong could never have caught the
// defect that motivated this file.
// ============================================================================
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { deflateRawSync, inflateRawSync } from 'node:zlib';

import { describe, expect, it } from 'vitest';

import {
  EXAM_CLAUSES,
  FIRST_ADDED_SDT_ID,
  ROS_CLAUSES,
  sdt,
} from '../../../../scripts/regenerate-consult-form';
import { compileTemplateDocx } from '@/lib/note-template-docx';
import { planTransfer } from '../ingest-plan';
import type { SemanticMapping, TemplateDocIR } from '../ir';

const WM_IOV = resolve(__dirname, '../../../../../../WM IOV Template.docx');

// ── a minimal, dependency-free zip reader/writer for the .docx package ───────
function readZip(bytes: Buffer): Map<string, Buffer> {
  const files = new Map<string, Buffer>();
  let end = bytes.length - 22;
  while (end >= 0 && bytes.readUInt32LE(end) !== 0x06054b50) end -= 1;
  const count = bytes.readUInt16LE(end + 10);
  let p = bytes.readUInt32LE(end + 16);
  for (let i = 0; i < count; i += 1) {
    const nameLen = bytes.readUInt16LE(p + 28);
    const extraLen = bytes.readUInt16LE(p + 30);
    const commentLen = bytes.readUInt16LE(p + 32);
    const local = bytes.readUInt32LE(p + 42);
    const name = bytes.subarray(p + 46, p + 46 + nameLen).toString('utf8');
    const method = bytes.readUInt16LE(local + 8);
    const csize = bytes.readUInt32LE(p + 20);
    const lNameLen = bytes.readUInt16LE(local + 26);
    const lExtraLen = bytes.readUInt16LE(local + 28);
    const dataAt = local + 30 + lNameLen + lExtraLen;
    const raw = bytes.subarray(dataAt, dataAt + csize);
    files.set(name, method === 8 ? inflateRawSync(raw) : Buffer.from(raw));
    p += 46 + nameLen + extraLen + commentLen;
  }
  return files;
}

function writeZip(files: Map<string, Buffer>): Buffer {
  const locals: Buffer[] = [];
  const centrals: Buffer[] = [];
  let offset = 0;
  const crcTable = (() => {
    const t = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c;
    }
    return t;
  })();
  const crc32 = (buf: Buffer): number => {
    let c = -1;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff]! ^ (c >>> 8);
    return (c ^ -1) >>> 0;
  };
  for (const [name, content] of files) {
    const nameBuf = Buffer.from(name, 'utf8');
    const deflated = deflateRawSync(content);
    const crc = crc32(content);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(8, 8);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(deflated.length, 18);
    local.writeUInt32LE(content.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    locals.push(local, nameBuf, deflated);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(8, 10);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(deflated.length, 20);
    central.writeUInt32LE(content.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt32LE(offset, 42);
    centrals.push(central, nameBuf);
    offset += 30 + nameBuf.length + deflated.length;
  }
  const centralSize = centrals.reduce((n, b) => n + b.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.size, 8);
  end.writeUInt16LE(files.size, 10);
  end.writeUInt32LE(centralSize, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, ...centrals, end]);
}

function editDocumentXml(bytes: Buffer, edit: (xml: string) => string): Buffer {
  const files = readZip(bytes);
  const xml = files.get('word/document.xml')!.toString('utf8');
  const next = edit(xml);
  expect(next, 'the transformation was a NO-OP — the arm would prove nothing').not.toBe(xml);
  files.set('word/document.xml', Buffer.from(next, 'utf8'));
  return writeZip(files);
}

/**
 * ⚠️ THE MEASURE IS INDEPENDENT OF THE THING IT MEASURES, AND THE FIRST TWO
 * VERSIONS WERE NOT.
 *
 * v1 keyed the expected concept on `originalLabel`. That called every legitimate
 * RENAME a mis-pair, because a renamed control correctly keeps its certification
 * via its tag.
 *
 * v2 keyed it on `tag ?? originalLabel` — the SAME two attributes `identityKeys`
 * matches on. ⚠️ THAT IS CIRCULAR, AND ROUND FOUR PROVED IT COSTS A DEFECT: on
 * the real document, where 14 ADJACENT pairs share a label, two controls sharing
 * a label also share a concept STRING, so handing clause #1's certified
 * disposition to clause #2 read as CORRECT. On the decisive run the identity
 * measure scored **14 of 14 wrong** and this corpus scored **ZERO**.
 *
 *     A MEASURE BUILT FROM THE ATTRIBUTES UNDER TEST CANNOT SEE A DEFECT IN
 *     THOSE ATTRIBUTES. It agrees with the code by construction.
 *
 * So a control is certified to its DOCUMENT POSITION in the source — an index,
 * which no identity key reads and which is unique by definition — and the
 * expected position is supplied by the transformation itself, which knows what
 * it moved. The measure and the mechanism now share nothing.
 */
type PositionPlan = {
  /** For target index j, the source index whose disposition it must receive, or null. */
  readonly expect: ReadonlyArray<number | null>;
};

function certifyByPosition(ir: TemplateDocIR): Map<string, SemanticMapping> {
  return new Map(
    ir.fields.map((f, i) => [
      f.fieldId,
      {
        fieldId: f.fieldId,
        clinicalConcept: `SRC#${i}`,
        status: 'certified',
      } as unknown as SemanticMapping,
    ]),
  );
}

/**
 * Every transfer that landed on a control other than the one the transformation
 * says it belongs to. `expect[j] === null` means "this target must NOT inherit".
 */
function misPairsByPosition(
  source: TemplateDocIR,
  target: TemplateDocIR,
  plan: PositionPlan,
): string[] {
  const certified = certifyByPosition(source);
  const result = planTransfer({ target, sourceIr: source, certifiedByFieldId: certified });
  const indexOf = new Map(target.fields.map((f, i) => [f.fieldId, i]));
  const wrong: string[] = [];
  for (const t of result.transferred) {
    const j = indexOf.get(t.fieldId)!;
    const want = plan.expect[j];
    const got = String(t.mapping.clinicalConcept);
    if (want === null || want === undefined) {
      wrong.push(`target#${j} (${target.fields[j]!.originalLabel}) inherited ${got} and must not have`);
    } else if (got !== `SRC#${want}`) {
      wrong.push(`target#${j} (${target.fields[j]!.originalLabel}) expected SRC#${want}, got ${got}`);
    }
  }
  return wrong;
}

/** IDENTICAL documents: target j must receive source j. */
function identityPlan(n: number): PositionPlan {
  return { expect: Array.from({ length: n }, (_, i) => i) };
}

/**
 * A document with one control REMOVED at `removedAt`: target j maps to source j
 * below the cut and j+1 above it. This is the shape that has now defeated three
 * different keys, so the corpus states it explicitly rather than inferring it.
 */
function afterRemovalPlan(n: number, removedAt: number, tagged: (j: number) => boolean): PositionPlan {
  return {
    expect: Array.from({ length: n }, (_, j) => {
      const src = j < removedAt ? j : j + 1;
      // Only a TAGGED control may inherit across a renumber; everything else
      // must re-propose. `null` asserts exactly that.
      return tagged(j) ? src : null;
    }),
  };
}

function transferCount(source: TemplateDocIR, target: TemplateDocIR): number {
  return planTransfer({ target, sourceIr: source, certifiedByFieldId: certifyByPosition(source) })
    .transferred.length;
}

const ARM_BUDGET_MS = 60_000;

// ══════════════════════════════════════════════════════════════════════════════
// DOCUMENT 1 · `WM IOV Template.docx` — REAL BYTES, 80 controls, random sdtIds
// ══════════════════════════════════════════════════════════════════════════════
describe('#274 CORPUS · WM IOV Template.docx (real bytes)', () => {
  const base = readFileSync(WM_IOV);
  const baseIr = compileTemplateDocx(base);
  const tagOf = (ir: TemplateDocIR, j: number) => (ir.fields[j]!.rendererBinding.tag ?? '').trim();

  it('POSITIVE CONTROL — the document is the one every claim was measured on', () => {
    // ⚠️ THESE NUMBERS ARE THE ARGUMENT FOR THE CURRENT DESIGN, so the corpus
    // asserts them rather than trusting a comment. 79 of 80 controls carry no
    // tag, labels repeat, and FOURTEEN ADJACENT PAIRS share one — which is what
    // defeated the sdtId+label pairing in round four.
    expect(baseIr.fields.length).toBe(80);
    const labels = baseIr.fields.map((f) => f.originalLabel);
    expect(new Set(labels).size, 'distinct labels').toBe(26);
    let adjacent = 0;
    for (let i = 1; i < labels.length; i += 1) if (labels[i] === labels[i - 1]) adjacent += 1;
    expect(adjacent, 'adjacent pairs sharing a label').toBe(14);
    expect(baseIr.fields.filter((f) => (f.rendererBinding.tag ?? '').trim() !== '').length).toBe(1);
  }, ARM_BUDGET_MS);

  it('1 · IDENTICAL bytes — everything transfers, nothing mis-paired', () => {
    const target = compileTemplateDocx(base);
    expect(misPairsByPosition(baseIr, target, identityPlan(target.fields.length))).toEqual([]);
    expect(transferCount(baseIr, target)).toBe(baseIr.fields.length);
  }, ARM_BUDGET_MS);

  it('⚠️ 3 · one control DROPPED — the renumber that mis-paired 14 of 14', () => {
    // The decisive case. Every untagged control MUST re-propose; only the single
    // tagged one may inherit, and only if it survived the cut.
    const mutated = editDocumentXml(base, (xml) => xml.replace(/<w:sdt>[\s\S]*?<\/w:sdt>/, ''));
    const target = compileTemplateDocx(mutated);
    const removedAt = 0;
    const plan = afterRemovalPlan(target.fields.length, removedAt, (j) => tagOf(target, j) !== '');
    expect(
      misPairsByPosition(baseIr, target, plan),
      'a renumber walked a certified concept onto a same-label neighbour',
    ).toEqual([]);
  }, ARM_BUDGET_MS);

  it('2 · one control INSERTED at the top', () => {
    const mutated = editDocumentXml(base, (xml) =>
      xml.replace(/(<w:body[^>]*>)/, `$1<w:p>${sdt('INSERTED PROBE', 'inserted_probe', 990001, 'x')}</w:p>`),
    );
    const target = compileTemplateDocx(mutated);
    // target j>0 corresponds to source j-1; only tagged controls may inherit.
    const plan: PositionPlan = {
      expect: target.fields.map((_, j) => (j > 0 && tagOf(target, j) !== '' ? j - 1 : null)),
    };
    expect(misPairsByPosition(baseIr, target, plan), 'an insert mis-paired').toEqual([]);
  }, ARM_BUDGET_MS);

  it('4 · a COPY-PASTED control — same id, same label, twice', () => {
    const mutated = editDocumentXml(base, (xml) => {
      const m = /<w:sdt>[\s\S]*?<\/w:sdt>/.exec(xml)!;
      return xml.replace(m[0], `${m[0]}${m[0]}`);
    });
    const target = compileTemplateDocx(mutated);
    const plan: PositionPlan = { expect: target.fields.map(() => null) };
    expect(misPairsByPosition(baseIr, target, plan), 'a copy-paste claimed a disposition').toEqual([]);
  }, ARM_BUDGET_MS);

  it('5 · a LABEL RENAME — an untagged control must NOT inherit', () => {
    const mutated = editDocumentXml(base, (xml) =>
      xml.replace(/<w:alias w:val="([^"]+)"\/>/, '<w:alias w:val="$1 (reworded)"/>'),
    );
    const target = compileTemplateDocx(mutated);
    const plan: PositionPlan = {
      expect: target.fields.map((_, j) => (tagOf(target, j) !== '' ? j : null)),
    };
    expect(misPairsByPosition(baseIr, target, plan), 'a rename mis-paired').toEqual([]);
  }, ARM_BUDGET_MS);
});

describe("#274 CORPUS · the owner's consult form (generator's own vocabulary)", () => {
  /**
   * The 18 controls the rule ADDS, at the ids and tags it assigns them.
   *
   * ⚠️ `sdt`, `ROS_CLAUSES`, `EXAM_CLAUSES` and `FIRST_ADDED_SDT_ID` are
   * IMPORTED. Retyping them would test the copy, and `nextId += 1` per control
   * IN DOCUMENT ORDER is the exact detail that made `sdtId` positional.
   */
  function buildAdded(dropRosIndex: number | null, renameTag: string | null): string {
    let id = FIRST_ADDED_SDT_ID;
    const parts: string[] = [];
    ROS_CLAUSES.forEach(([tag, sentence], i) => {
      if (i === dropRosIndex) return;
      const alias = renameTag === tag ? `${sentence} (reworded)` : sentence;
      parts.push(`<w:p>${sdt(alias.replace(/\.$/, ''), tag, id, sentence)}</w:p>`);
      id += 1;
    });
    EXAM_CLAUSES.forEach(([tag, label, value]) => {
      const alias = renameTag === tag ? `${label} (reworded)` : label;
      parts.push(`<w:p>${sdt(alias.replace(/:\s*$/, ''), tag, id, value)}</w:p>`);
      id += 1;
    });
    parts.push(`<w:p>${sdt('Telehealth consent', 'telehealth_consent', id, 'consent')}</w:p>`);
    id += 1;
    parts.push(`<w:p>${sdt('Total time minutes', 'total_time_minutes', id, '______')}</w:p>`);
    return parts.join('');
  }

  const base = readFileSync(WM_IOV);
  const pack = (added: string): TemplateDocIR =>
    compileTemplateDocx(editDocumentXml(base, (xml) => xml.replace(/(<w:body[^>]*>)/, `$1${added}`)));

  const sourceIr = pack(buildAdded(null, null));
  const tagAt = (ir: TemplateDocIR, j: number) => (ir.fields[j]!.rendererBinding.tag ?? '').trim();

  /**
   * ⚠️ THE EXPECTATION IS BUILT FROM THE TAG CORRESPONDENCE, WHICH THE
   * TRANSFORMATION KNOWS AND THE MEASURE DOES NOT INFER. For each target index,
   * the source index carrying the SAME tag — or null when the control has no tag
   * and therefore must re-propose.
   */
  function tagPlan(target: TemplateDocIR): PositionPlan {
    const srcByTag = new Map<string, number>();
    sourceIr.fields.forEach((f, i) => {
      const t = (f.rendererBinding.tag ?? '').trim();
      if (t !== '' && !srcByTag.has(t)) srcByTag.set(t, i);
    });
    return {
      expect: target.fields.map((_, j) => {
        const t = tagAt(target, j);
        if (t === '') return null;
        return srcByTag.has(t) ? srcByTag.get(t)! : null;
      }),
    };
  }

  it('POSITIVE CONTROL — the ids ARE dense sequential and every added control is tagged', () => {
    const addedTags = new Set<string>([
      ...ROS_CLAUSES.map(([t]) => t),
      ...EXAM_CLAUSES.map(([t]) => t),
      'telehealth_consent',
      'total_time_minutes',
    ]);
    const added = sourceIr.fields.filter(
      (f) => f.rendererBinding.tag !== null && addedTags.has(f.rendererBinding.tag),
    );
    expect(added.length).toBeGreaterThanOrEqual(18);
    const ids = added.map((f) => Number(f.rendererBinding.sdtId)).sort((a, b) => a - b);
    expect(ids[ids.length - 1]! - ids[0]!, 'the ids are not dense — not the shipped shape').toBe(
      ids.length - 1,
    );
  }, ARM_BUDGET_MS);

  it('1 · IDENTICAL bytes', () => {
    const target = pack(buildAdded(null, null));
    expect(misPairsByPosition(sourceIr, target, identityPlan(target.fields.length))).toEqual([]);
  }, ARM_BUDGET_MS);

  it('⚠️ 3 · one ROS clause DROPPED — EVERY downstream sdtId shifts by one', () => {
    // THE ROUND-THREE DEFECT. Before the tag path this transferred 52 of 52 with
    // FIFTEEN concepts on the wrong controls, every one `certified`, and all
    // three bijection guards satisfied.
    const target = pack(buildAdded(2, null));
    expect(
      misPairsByPosition(sourceIr, target, tagPlan(target)),
      'a renumber walked the exam narrative sideways',
    ).toEqual([]);
  }, ARM_BUDGET_MS);

  it('⚠️ 5 · a LABEL RENAME — the TAG must still carry it', () => {
    const target = pack(buildAdded(null, 'exam_lungs'));
    expect(misPairsByPosition(sourceIr, target, tagPlan(target)), 'a rename mis-paired').toEqual([]);
    // and it must actually TRANSFER — a measure satisfied by transferring
    // nothing would pass the line above and prove nothing.
    const renamed = target.fields.find((f) => f.rendererBinding.tag === 'exam_lungs')!;
    const plan = planTransfer({ target, sourceIr, certifiedByFieldId: certifyByPosition(sourceIr) });
    expect(
      plan.transferred.find((t) => t.fieldId === renamed.fieldId),
      'the renamed control lost its certification — the tag path is dead',
    ).toBeDefined();
  }, ARM_BUDGET_MS);

  it('⚠️ 3+5 · a DROP **and** a RENAME together — ids shift AND the label moves', () => {
    const target = pack(buildAdded(2, 'exam_lungs'));
    expect(
      misPairsByPosition(sourceIr, target, tagPlan(target)),
      'drop + rename mis-paired',
    ).toEqual([]);
  }, ARM_BUDGET_MS);
});
