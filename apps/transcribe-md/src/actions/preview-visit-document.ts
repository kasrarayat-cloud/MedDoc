'use server';

// ============================================================================
// previewVisitDocumentAction — the visit, as the doctor's own page.
// ----------------------------------------------------------------------------
// The review screen shows the note. This shows the DOCUMENT: their form, filled
// with what has been captured so far, blanks where nothing has. It is the same
// fill the export produces, computed through the same code
// (readAndPrepareTemplateTwinFill), so what they read before signing is what
// comes out afterwards.
//
// IT WRITES NOTHING. Not a fill manifest, not an artifact, not a template
// claim. That is not tidiness — the sign gate validates a STORED manifest
// against the certified IR, so a manifest written mid-review would let a doctor
// sign a fill that predates their own adoptions. The preview reads and computes
// and then forgets.
//
// AND IT GATES NOTHING. Every failure returns a named reason; the caller falls
// back to the styled note and the doctor signs exactly as before.
// ============================================================================

import prisma from '@meddoc/db';

import { requireSession } from '@/lib/auth';
import { visitByIdScope, type PracticeId } from '@/lib/practice-scope';
import { convertDocxToPdf } from '@/lib/docx-preview/convert';
import {
  readCachedFill,
  writeCachedFill,
  type CachedFill,
} from '@/lib/docx-preview/fill-cache';
import { generateVisitDocx } from '@/lib/docx-generator';
import { readAndPrepareTemplateTwinFill } from '@/lib/template-twin/fill-engine';
import { TemplateDocIRSchema } from '@/lib/template-twin/ir';
import { scaffoldDefaultOfferable } from '@/lib/template-twin/clinician-override';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { loadNativeTemplateDocxForVisit } from '@/lib/template-twin/native-export';
import type { NativePreviewResult } from './preview-native-document';

/** Why there is no document to show. Every one is surfaced, and none is fatal. */
export type VisitPreviewMiss =
  /** Neither a certified twin NOR a styled document could be produced. */
  | 'not_template_visit'
  /** Template uploaded and compiled, but never certified. */
  | 'not_certified'
  /** The fill ran and produced no document (nothing renderable yet). */
  | 'no_render'
  /** The fill itself failed. Named, so it is never a blank screen. */
  | 'fill_failed';

export interface VisitPreviewResult extends Omit<NativePreviewResult, 'reason'> {
  reason: NativePreviewResult['reason'] | VisitPreviewMiss | null;
  /** How much of their form is actually filled — shown honestly above the page
   *  so blanks read as "not dictated yet" rather than "the export is broken". */
  counts: {
    filled: number;
    needsReview: number;
    notMentioned: number;
  } | null;
  /** Changes whenever the underlying fill changes. The client uses it to tell
   *  a genuine update from a re-fetch that produced the same document. */
  fillSha: string | null;
  /**
   * REVIEW-DEFAULTS item 1 — the blank scaffolded controls the doctor has a
   * default for, so the review surface can offer to insert them.
   *
   * ⚠️ THIS EXISTS BECAUSE THE DOCUMENT IS A CANVAS BITMAP. `DocumentPages`
   * renders each page into a `<canvas role="img">`; there is no element for a
   * field, no fieldId in the DOM and no hit-testing, so an in-place control has
   * nowhere to attach. The list travels beside the page instead.
   *
   * ⚠️ PHI-FREE BY CONSTRUCTION, AND IT IS WORTH SAYING WHY IT IS SAFE. Both
   * strings come from the doctor's OWN UPLOADED FORM — `originalLabel` is the
   * control's caption and `scaffoldText` is the wording their template shipped
   * with. Neither is derived from the transcript, the note or the patient. The
   * resolved VALUE of a field is never included here.
   */
  insertableDefaults: {
    fieldId: string;
    /** The control's caption on the doctor's own form. */
    label: string;
    /** The wording their template ships with, compiled. */
    scaffoldText: string;
    /** True when this default is already inserted, so the surface offers UNDO
     *  rather than a second insert. */
    inserted: boolean;
  }[] | null;
}

/**
 * The styled note, as a document.
 *
 * Same pipeline as the native path — DOCX to the converter, PDF back, drawn
 * page by page — so the two surfaces are the same surface. The bytes are the
 * ones the doctor would download, which is the whole point: what they read is
 * what they sign.
 */
async function styledDocument(
  visitId: string,
  // T5 §4.1b — a READ. Scoped by practice, renamed so the call sites had to
  // be revisited rather than compiling unchanged on an identical `string`.
  practiceId: PracticeId,
  soapVersion: number,
  /** Carried through so the page can say WHY it is not their own form. */
  note: VisitPreviewMiss | null,
  format: PreviewFormat = 'pdf',
  /** A signed record's rendering is not a preview — never cache it. */
  cacheable = true,
): Promise<VisitPreviewResult> {
  // READ its own variant too. This path only ever wrote, so the majority of
  // visits re-ran the whole export + conversion on every mount while filling a
  // keyspace only the twin path could read.
  if (format === 'pdf' && cacheable) {
    const hit = await readCachedFill(visitId, soapVersion, 'styled');
    if (hit) {
      return {
        ok: true,
        kind: hit.kind,
        data: hit.data,
        reason: hit.reason as VisitPreviewResult['reason'],
        counts: hit.counts,
        // A cache entry written before this field existed carries no list, and
        // null is the honest answer: 'we did not compute it', not 'there are
        // none'. The surface renders nothing rather than an empty panel.
        insertableDefaults: hit.insertableDefaults ?? null,
        fillSha: hit.fillSha,
      };
    }
  }
  let docx: Buffer;
  try {
    const data = await loadVisitExportData(visitId, practiceId);
    if (!data) return miss('not_template_visit');
    docx = await generateVisitDocx(data);
  } catch (err) {
    const cls = err instanceof Error ? err.constructor.name : 'Unknown';
    console.warn(`[visit-preview] visit=${visitId} styled build failed (${cls})`);
    return miss('no_render');
  }

  const converted = format === 'word' ? { pdf: null, reason: null } : await convertDocxToPdf(docx, 'visit.docx');
  const result: CachedFill = converted.pdf
    ? {
        kind: 'pdf',
        data: Buffer.from(converted.pdf).toString('base64'),
        reason: note,
        counts: null,
        insertableDefaults: null,
        fillSha: `styled:${soapVersion}`,
      }
    : {
        kind: 'docx_fallback',
        data: docx.toString('base64'),
        reason: converted.reason,
        counts: null,
        insertableDefaults: null,
        fillSha: `styled:${soapVersion}`,
      };
  if (format === 'pdf' && cacheable) await writeCachedFill(visitId, soapVersion, result, 'styled');
  return {
    ok: true,
    ...result,
    insertableDefaults: result.insertableDefaults ?? null,
    reason: result.reason as VisitPreviewResult['reason'],
  };
}

function miss(reason: VisitPreviewResult['reason']): VisitPreviewResult {
  return {
    ok: false,
    kind: null,
    data: null,
    reason,
    counts: null,
    insertableDefaults: null,
    fillSha: null,
  };
}

/** Which rendering the doctor asked for. 'word' hands over the true DOCX for
 *  the browser to draw — the same bytes, a different engine — so they can see
 *  the file as Word will open it. */
export type PreviewFormat = 'pdf' | 'word';

export async function previewVisitDocumentAction(
  visitId: string,
  format: PreviewFormat = 'pdf',
): Promise<VisitPreviewResult> {
  const session = await requireSession();

  // Ownership is a WHERE clause, never a check after the fact.
  const visit = await prisma.transcribeVisit.findFirst({
    // Mirrors the fill path's own filters (fill-engine's template claim), not
    // just the client's. A server action is a POST endpoint — "the page does
    // not render it for a signed visit" is not an access control.
    where: {
      // READ — §4.1b: practice-uniform. A colleague may preview the
      // practice's document; the author conjunct is deliberately gone.
      ...visitByIdScope(visitId, session.user.practiceId),
      deletedAt: null,
      archivedAt: null,
    },
    select: {
      userId: true,
      // `status` MUST be selected — the guard below reads it, and Prisma is
      // untyped here, so an absent column reads as `undefined` and silently
      // rejects every visit. Fourth time this class has bitten in this repo.
      status: true,
      signedAt: true,
      inputMode: true,
      transcriptText: true,
      entities: true,
      soapFinal: true,
      soapVersion: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      createdAt: true,
      user: { select: { practiceId: true } },
    },
  });
  // NO VISIT, NO DOCUMENT — and this guard must come FIRST.
  //
  // `findFirst` returns null for a visit that does not exist, belongs to
  // another doctor, or is deleted/archived — all four are ordinary, and the
  // WHERE clause above is what makes them null rather than a leak. Moving the
  // signed branch up moved it ABOVE the only null check, so `visit.signedAt`
  // dereferenced null and the action threw instead of returning a named miss.
  // tsc cannot see it: prisma is `any` here, the same untyped-result class this
  // file's own select comment is about.
  if (!visit) return miss('not_template_visit');

  // SIGNED FIRST, above ANY path that could re-derive.
  //
  // This sat below the template lookup, so a doctor deleting a note template —
  // which nulls every visit's binding and cascades the compiled row away —
  // sent their already-SIGNED visits down the styled path and served them a
  // freshly re-derived document, cached. The stored bytes were still there;
  // nothing was asking for them.
  //
  // SIGNED: serve the STORED, roundtrip-verified bytes — the actual file that
  // was delivered. Never re-derive a signed document; a fresh fill could differ
  // from what the doctor put their name to, and the twin fill path refuses a
  // signed visit anyway.
  if (visit.signedAt) {
    const stored = await loadNativeTemplateDocxForVisit(visitId, session.user.practiceId);
    if (!stored) {
      // No stored native file (never had one, or the template was deleted).
      // The signed note as a styled document is the honest answer — and it is
      // NOT cached: a signed record's rendering is not a preview.
      return styledDocument(visitId, session.user.practiceId, visit.soapVersion, null, format, false);
    }
    const conv = await convertDocxToPdf(stored.bytes, 'visit.docx');
    return conv.pdf
      ? {
          ok: true,
          kind: 'pdf',
          data: Buffer.from(conv.pdf).toString('base64'),
          reason: null,
          counts: null,
          insertableDefaults: null,
          fillSha: stored.outputSha256,
        }
      : {
          ok: true,
          kind: 'docx_fallback',
          data: stored.bytes.toString('base64'),
          reason: conv.reason,
          counts: null,
          insertableDefaults: null,
          fillSha: stored.outputSha256,
        };
  }

  // Cached on the NOTE'S VERSION — and only ever consulted BELOW the signed
  // branch. Read above it, a pre-sign entry would be served for a signed visit
  // and quietly defeat the one rule that branch exists to enforce.

  // A NOTE is all that is required. The template fields gate the TWIN path
  // below, not this function — demanding them here is what sent every styled
  // visit back to the card wall before the styled document existed.
  if (!visit?.soapFinal || !visit.user?.practiceId) {
    return miss('not_template_visit');
  }
  // A server action is a POST endpoint. A visit still processing (or failed)
  // may carry a stale note from a previous run; it does not get a document.
  if (visit.status !== 'READY' && !visit.signedAt) {
    return miss('not_template_visit');
  }

  const compiled = visit.noteTemplateId && visit.noteTemplateVersion != null
    ? await prisma.templateTwinCompiledVersion.findUnique({
        where: { noteTemplateId: visit.noteTemplateId },
        select: { id: true, certificationStatus: true, compiledDocumentIr: true },
      })
    : null;

  // NO CERTIFIED TWIN — but every visit still gets a document.
  //
  // A doctor with no uploaded FORM (most of them: the note-format flow teaches
  // us a format from a note, which has no page behind it) used to fall through
  // to a wall of cards. They get the same paginated document as everyone else
  // now, built from the styled export — the very file they would download.
  // One review surface, one interaction model, whatever the template state.
  if (!compiled || compiled.certificationStatus !== 'CERTIFIED') {
    return styledDocument(visitId, session.user.practiceId, visit.soapVersion, compiled ? 'not_certified' : null, format);
  }

  let docx: Buffer;
  let counts: VisitPreviewResult['counts'] = null;
  let insertableDefaults: VisitPreviewResult['insertableDefaults'] = null;
  let fillSha: string;

  // The cache holds ONE rendering per note version; a Word request must not be
  // answered with the PDF entry, nor overwrite it.
  const cached = format === 'pdf' ? await readCachedFill(visitId, visit.soapVersion, 'twin') : null;
  if (cached) {
    return {
      ok: true,
      kind: cached.kind,
      data: cached.data,
      reason: cached.reason as VisitPreviewResult['reason'],
      counts: cached.counts,
      insertableDefaults: cached.insertableDefaults ?? null,
      fillSha: cached.fillSha,
    };
  }

  // EXPLICIT, not inferred. Prisma's result is untyped here (`as any` in the
  // db barrel), so tsc cannot tell that reaching this line implies a bound
  // template — it would happily pass null straight into the fill. This is the
  // same class that put a non-existent column in a select twice this week.
  const templateId = visit.noteTemplateId;
  const templateVersion = visit.noteTemplateVersion;
  if (typeof templateId !== 'string' || typeof templateVersion !== 'number') {
    return styledDocument(visitId, session.user.practiceId, visit.soapVersion, null, format);
  }

  try {
    const { prepared } = await readAndPrepareTemplateTwinFill({
      // ⚠️ F24-S5 — REQUIRED, AND THE PREVIEW IS WHY. The clinician's own
      // form-control corrections are keyed by visit; a preview that omitted this
      // would show the doctor a document that disagrees with the one the export
      // and the signature will produce. The parameter is required on the shared
      // function so forgetting it is a compile error rather than a divergence.
      visitId,
      practiceId: visit.user.practiceId,
      // ⚠️ THE VISIT'S OWN DOCTOR, NOT THE REQUESTER. This read is
      // practice-scoped, so a colleague previewing the record would otherwise
      // stamp their id on the author's fill. Same actor fix as native-export's.
      doctorId: visit.userId,
      noteTemplateId: templateId,
      noteTemplateVersion: templateVersion,
      inputMode:
        visit.inputMode === 'voice_dictation'
          ? 'dictation'
          : visit.inputMode === 'text_notes'
            ? 'text'
            : 'conversation',
      contextText: visit.transcriptText ?? '',
      entities: visit.entities,
      generatedNote: visit.soapFinal,
      validationNow: new Date(),
      visitDate: visit.createdAt,
      resolverModelVersion: null,
    });
    if (!prepared.render?.document) return miss('no_render');
    docx = prepared.render.document;
    counts = {
      filled: prepared.manifest.counts.filled,
      needsReview: prepared.manifest.counts.needsReview,
      notMentioned: prepared.manifest.counts.notMentioned,
    };
    fillSha = prepared.manifestSha256;

    // ⚠️ DERIVED FROM THE COMPILED IR AND THE MANIFEST, NEVER FROM THE CLIENT.
    // A field qualifies when the COMPILER marked it scaffolded and it carries
    // text — `scaffolded` is a fact about the document's bytes, and ruling #192
    // falsified three attempts to infer it from content, one of which printed
    // "Enter assessment" onto a rendered note.
    //
    // The list keeps a field while it is still BLANK (there is something to
    // insert) or while this doctor's default is ALREADY INSERTED (there is
    // something to undo). A field filled from dictation drops off it entirely,
    // which is the same blank-only rule the overlay enforces server-side —
    // stated in two places because the surface must not offer an act the writer
    // would decline.
    const irForDefaults = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
    const byFieldId = new Map(prepared.manifest.fields.map((f) => [f.fieldId, f]));
    // ⚠️ ONE PREDICATE, SHARED WITH THE DOOR AND THE OVERLAY. An adversarial
    // pass found three different tests here and offered acts the writer would
    // refuse — including on fields the encounter had DENIED, under the caption
    // "Nothing was dictated for these".
    // The concepts come from the field DEFINITIONS, which is where the door
    // reads them too — the manifest does not carry mappings.
    const defs = await prisma.templateTwinFieldDefinition.findMany({
      where: { compiledVersionId: compiled.id },
      // ⚠️ `unmentionedPolicy` IS SELECTED BECAUSE THE PREDICATE READS IT. An
      // unselected column arrives `undefined`, which is not `'omit'`, so the
      // guard in `scaffoldDefaultOfferable` would be dead code that looks live.
      select: {
        fieldId: true,
        mapping: { select: { clinicalConcept: true, unmentionedPolicy: true } },
      },
    });
    const mappingByFieldId = new Map(
      defs.map((d) => [d.fieldId, d.mapping ?? null] as const),
    );
    insertableDefaults = irForDefaults.fields.flatMap((f) => {
      const text = (f.scaffoldText ?? '').trim();
      const r = byFieldId.get(f.fieldId);
      const inserted = r?.reasonCode === 'clinician_scaffold_default';
      // An already-inserted default stays listed so the doctor can UNDO it;
      // everything else must pass the same test the writer applies.
      const offerable =
        inserted ||
        scaffoldDefaultOfferable({
          field: f,
          mapping: mappingByFieldId.get(f.fieldId) ?? null,
          current: r ?? null,
        });
      if (!offerable || !text) return [];
      return [{ fieldId: f.fieldId, label: f.originalLabel, scaffoldText: text, inserted }];
    });
  } catch (err) {
    const cls = err instanceof Error ? err.constructor.name : 'Unknown';
    console.warn(
      `[visit-preview] visit=${visitId} fill failed (${cls}); the styled note still renders`,
    );
    return miss('fill_failed');
  }

  const converted = format === 'word' ? { pdf: null, reason: null } : await convertDocxToPdf(docx, 'visit.docx');
  const result: CachedFill = converted.pdf
    ? {
        kind: 'pdf',
        data: Buffer.from(converted.pdf).toString('base64'),
        reason: null,
        counts,
        insertableDefaults,
        fillSha,
      }
    : {
        // Converter unavailable — hand the true bytes over and let the browser
        // draw them. Cached too: a sidecar that is down stays down, and
        // re-running the whole fill to rediscover that helps nobody.
        kind: 'docx_fallback',
        data: Buffer.from(docx).toString('base64'),
        reason: converted.reason,
        counts,
        insertableDefaults,
        fillSha,
      };
  if (format === 'pdf') await writeCachedFill(visitId, visit.soapVersion, result, 'twin');
  return {
    ok: true,
    ...result,
    insertableDefaults: result.insertableDefaults ?? null,
    reason: result.reason as VisitPreviewResult['reason'],
  };
}
