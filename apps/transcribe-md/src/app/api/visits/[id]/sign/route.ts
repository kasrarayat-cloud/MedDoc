// ============================================================================
// POST /api/visits/[id]/sign (T-M7)
// ----------------------------------------------------------------------------
// The unified sign + deliver path (T-M7) — the SOLE path that transitions a
// visit READY→SIGNED. Accepts a multi-destination body so the doctor can, in
// one click, freeze the note AND paste-to-Epic AND email themselves AND
// download the PDF.
//
// Body: {
//   destinations: Array<
//     | 'clipboard_epic' | 'clipboard_athena' | 'clipboard_cerner'
//     | 'clipboard_eclinicalworks' | 'clipboard_generic'
//     | 'pdf' | 'docx' | 'email'
//   >,
//   emailTo?: string,
//   // E/M visible-confirm (prod smoke #311): REQUIRED (echoing the
//   // recorded {from, to} exactly) when an unacknowledged suggestion-
//   // caused E/M level change exists on the visit — otherwise the
//   // READY→SIGNED transition is refused with 400
//   // { ok:false, error, code:'EM_CHANGE_UNACKNOWLEDGED' }.
//   acknowledgedEmChange?: { from: string, to: string }
// }
//
// Response: {
//   signedAt: ISO,
//   clipboardTexts?: Record<clipboard_format, string>,
//   pdfDownloadUrl?: string,   // "/api/visits/:id/export/pdf"
//   formatNotice?: { reason, message },  // present ONLY on a styled downgrade
//   docxDownloadUrl?: string,
//   emailQueued?: boolean
// }
// ============================================================================

import { NextResponse } from 'next/server';
import { rescoreEmAction } from '@/actions/rescore-em';
import {
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from '@meddoc/shared/specialties';
import { emAppliesToVisit } from '@/lib/note-shape';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';
import { getSession } from '@/lib/auth';
import { formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { computeDisplayedEmCode } from '@/lib/em-coding/displayed-level';
import { formatForEhr, type EhrFormat } from '@/lib/ehr-formatters';
import { sendVisitPdfEmail } from '@/lib/email';
import {
  logDelivery,
  type DeliveryChannel,
} from '@/lib/deliveries';
import { captureEditPattern } from '@/lib/edit-tracking';

import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';
import { unacknowledgedEmChange, type EmChangeCause } from '@/lib/em-pending-change';

export const runtime = 'nodejs';

/** How the refusal message names WHY the level moved. Exhaustive over
 *  `EmChangeCause` on purpose: a new cause must not be able to inherit some
 *  other cause's wording, which is how a doctor's own override came to be
 *  described to them as "an AI-suggestion action". Adding a cause without
 *  adding a phrase here is a type error. */
const EM_CAUSE_PHRASE: Record<EmChangeCause, string> = {
  suggestion_adopted: 'by an AI-suggestion action',
  suggestion_dismissed: 'by an AI-suggestion action',
  note_edited: 'by an edit to the note',
  doctor_override: 'because you set it',
};
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const Destination = z.enum([
  'clipboard_epic',
  'clipboard_athena',
  'clipboard_cerner',
  'clipboard_eclinicalworks',
  'clipboard_generic',
  'pdf',
  'docx',
  'email',
]);

const BodySchema = z.object({
  destinations: z.array(Destination).max(10).default([]),
  emailTo: z.string().email().max(254).optional(),
  /** E/M visible-confirm (prod smoke #311): the doctor's explicit
   *  acknowledgement of a suggestion-caused E/M level change. Must echo
   *  the recorded {from, to} EXACTLY (content-identity check, same
   *  philosophy as the suggestions lane's expectedText) — a stale tab
   *  can never acknowledge a change the doctor didn't see. */
  acknowledgedEmChange: z
    .object({
      from: z.string().min(1).max(16),
      to: z.string().min(1).max(16),
    })
    .optional(),
  /** THE DOCTOR'S ATTESTATION — required, 2026-08-02.
   *
   *  Until this field existed the attestation was a UI-only gate
   *  (`sign-gates.ts` marked it `serverEnforced: false`). A second sign control
   *  shipped to production that did not count it, and because nothing here
   *  counted it either, the gate could be passed with no refusal and no audit
   *  row. Optional in the SCHEMA so a request without it produces the typed
   *  refusal below rather than a generic 400 the caller cannot act on. */
  attestation: z
    .object({
      acknowledged: z.literal(true),
    })
    .optional(),
});

const FORMAT_FOR_CHANNEL: Partial<
  Record<z.infer<typeof Destination>, EhrFormat>
> = {
  clipboard_epic: 'epic',
  clipboard_athena: 'athena',
  clipboard_cerner: 'cerner',
  clipboard_eclinicalworks: 'eclinicalworks',
  clipboard_generic: 'generic',
};

export const POST = withApiHandler<{ id: string }>(
  'api:visits:sign',
  async (req, { params }) => {
    const { id: visitId } = await params;

    // Declared at handler scope: set inside the sign branch, read by the
    // response below. A visit that was ALREADY signed never enters that branch
    // and correctly reports no notice.
    let nativeFreeze: { state: string; reason?: string; manifestId?: string } = {
      state: 'not_applicable',
    };
    /** Set when THIS request lost the race: another actor's signature stands. */
    let supersededBySigner: string | null = null;

    const session = await getSession();
    const userId = session?.user.id;
    const sessionEmail = session?.user?.email;
    if (!userId || !sessionEmail) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid destinations payload', 400);

    // ── PHI exfiltration guard ─────────────────────────────────────
    // If an 'email' destination is requested, `emailTo` MUST match
    // the caller's own account email (case-insensitive). Same guard
    // as /api/visits/[id]/export/email — prevents a session holder
    // from co-delivering every signed SOAP to any external inbox in
    // the same click that signs the visit.
    if (parsed.data.destinations.includes('email')) {
      const requestedTo = (parsed.data.emailTo ?? sessionEmail)
        .toLowerCase()
        .trim();
      if (requestedTo !== sessionEmail.toLowerCase().trim()) {
        log.warn('api:visits:sign', 'email destination blocked', {
          userId,
          visitId,
          requestedDomain: requestedTo.split('@')[1] ?? 'unknown',
          sessionDomain: sessionEmail.split('@')[1] ?? 'unknown',
        });
        void logAudit({
          action: 'EXPORT_EMAIL_BLOCKED_DESTINATION',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          success: false,
          errorCode: 'INVALID_DESTINATION',
          metadata: {
            via: 'sign',
            requestedDomain: requestedTo.split('@')[1] ?? 'unknown',
            sessionDomain: sessionEmail.split('@')[1] ?? 'unknown',
          },
        });
        return apiError(
          'Email destination must match your account email.',
          403,
          { code: 'INVALID_DESTINATION', retry: false }
        );
      }
    }

    // ── Sign ────────────────────────────────────────────────────────
    // Use an atomic updateMany with a status guard so two concurrent
    // submissions can't both "win" and double-sign.
    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        status: true,
        soapFinal: true,
        // ⚠️ THE CAPTURE'S IDENTITY — the compare-and-swap on the signature
        // write guards on it, so the text that is signed is the text that was
        // read.
        soapVersion: true,
        icdCodes: true,
        rxDrafts: true,
        cptCodes: true,
        signedAt: true,
        deletedAt: true,
        archivedAt: true,
        emPendingChange: true,
        emStale: true,
        specialty: true,
        // F12 / ruling #123 — the note-SHAPE axis of E/M applicability.
        noteTemplate: { select: { sections: true } },
      },
    });
    // ═══ THE SIGN GATE — TWO BRANCHES, AND THEY ARE NOT INTERCHANGEABLE ═══
    //
    // ⚠️ 1. CROSS-PRACTICE → 404, SILENT. The read above is practice-scoped
    // (T5), so a visit in another practice simply does not come back. 404 is
    // deliberate here: "not found" and "not yours" must be indistinguishable, or
    // the response becomes an id-enumeration oracle for other practices' charts.
    if (!visit) return apiError('not found', 404);
    //
    // ⚠️ 2. IN-PRACTICE, WRONG ROLE → REFUSED BY NAME. SPEC §4.1a: "you may not
    // sign" and "this does not exist" are different facts, and a clinician
    // deserves the true one. A TECH looking at a visit they legitimately SEE
    // (§4.1b — read is practice-uniform) gets a real explanation, not a lie
    // about the record existing. There is no enumeration risk: they can already
    // see it.
    //
    // Fail-closed on an ABSENT or UNRECOGNISED role, not just on TECH. A member
    // whose practiceRole is somehow null refuses too — the database CHECK makes
    // that unreachable for an active member, and this does not rely on it.
    const signer = await prisma.user.findUnique({
      where: { id: userId },
      select: { practiceRole: true },
    });
    if (signer?.practiceRole !== 'OWNER' && signer?.practiceRole !== 'CLINICIAN') {
      // The refusal is audited. R1's lesson: a gate nothing records is one path
      // away from not existing.
      void logAudit({
        action: 'SIGN_BLOCKED_ROLE_NOT_PERMITTED',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        // Structured only — the role and the fact of refusal. Never note text.
        metadata: { practiceRole: signer?.practiceRole ?? null },
      });
      return NextResponse.json(
        {
          error:
            signer?.practiceRole === 'TECH'
              ? 'Your role cannot sign clinical notes. Ask a clinician in your practice to sign this visit.'
              : 'Your account does not have a role that can sign clinical notes.',
          code: 'ROLE_MAY_NOT_SIGN',
        },
        { status: 403 }
      );
    }
    //
    // ⚠️ 3. AUTHORSHIP IS NO LONGER A GATE — §4.1c retired, per §4.1a.
    // This line used to read `|| visit.userId !== userId`. OWNER and CLINICIAN
    // may sign any UNSIGNED visit in their practice: the target workflow is
    // tech-creates, doctor-signs, and the locum principle carries through — the
    // chart owns the note, the signer owns the signature. `signedBy` is stamped
    // server-side below, so who signed is recorded rather than assumed.
    // T-M17.3: never silently sign a trashed / archived visit. Archived
    // SIGNED visits cannot be re-signed via this route — the operator
    // must unarchive first (dedicated flow, not in T-M17.3 scope).
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error: 'Visit is no longer active. Restore it first.',
          code: 'VISIT_NOT_ACTIVE',
        },
        { status: 400 }
      );
    }
    if (
      visit.status !== TranscribeVisitStatus.READY &&
      visit.status !== TranscribeVisitStatus.SIGNED
    ) {
      return apiError('visit is still processing', 409);
    }
    if (!visit.soapFinal?.trim()) {
      return apiError('visit has no SOAP to sign', 409);
    }

    // ⚠️ THE CRITICAL-Rx SIGN GATE WAS REMOVED HERE — OWNER RULING #109,
    // 2026-08-14. Do not reinstate it as a bug fix; it is a deliberate product
    // decision, and it is recorded at the point of removal precisely so the
    // next reader does not "restore" it.
    //
    // What stood here: on the READY -> SIGNED transition, every persisted
    // critical Rx warning had to carry an `RxWarningOverride` row keyed by its
    // real `rx-warning-<index>` id, or the route returned 422 OVERRIDE_REQUIRED
    // and wrote an `RX_SIGN_BLOCKED_NO_OVERRIDE` audit row.
    //
    // The ruling deletes the surface that DISPLAYED prescription safety. A
    // server-side refusal whose only remedy lived on a deleted surface is not a
    // safety net — it is an unclearable block: no door in, and every affected
    // doctor stuck at 422 with nothing to click. So the gate comes out WITH the
    // face, in the same commit, by design.
    //
    // ⚠️ THIS IS A REAL REDUCTION IN WHAT THE SERVER REFUSES, and it is declared
    // as such in the PR body and the §2.5 delta rather than described as a
    // cleanup. Extraction, persistence and the `RxWarningOverride` audit trail
    // are all untouched (`07c-rx-drafting.ts`, `rx-warnings.ts`,
    // `rx-warning-audit.ts`): the data keeps being produced and stored, and its
    // disposition is an OPEN question the ruling deliberately left open. The
    // `RX_SIGN_BLOCKED_NO_OVERRIDE` AuditAction value stays in the Postgres enum
    // — historical rows reference it, and an enum value is not removable by the
    // same edit that stops writing it.

    // ── E/M visible-confirm gate (prod smoke #311) ─────────────────────
    // Adopting/dismissing an AI suggestion that changed the computed E/M
    // level records {from, to, cause, at} on the visit (suggestion-
    // actions.ts). The READY→SIGNED transition is REFUSED until the
    // request explicitly echoes that exact {from, to} back — fail-closed
    // server-side, so a UI that forgot to render the confirm control (or
    // a direct/scripted caller) can never sign through a silent level
    // change. Already-SIGNED visits skip the gate (this route only
    // re-delivers them; the change was acknowledged when they signed).
    // ── E/M STALE gate ────────────────────────────────────────────────
    // The note changed since the level was last validated. Until something
    // re-scores it we do not know whether the level moved, and "we do not
    // know" is not a state a note may be signed in.
    //
    // This closes a gap that predates the chat editor: a doctor could edit
    // the note in the inline editor and sign, and nothing ever revisited the
    // E/M level — only ADOPTING a suggestion computed a delta. There is one
    // semantics now, whether a human or a model made the change.
    //
    // It only ADDS a condition; every existing check below is untouched.
    // Imaging reports have no office-visit E/M level at all — the pipeline
    // skips scoring them and the Billing surface says "not applicable". A
    // staleness gate over a level that does not exist would make an ultrasound
    // report permanently unsignable after any edit, and "resolving" it would
    // mean inventing a clinic code. The flag may be set; here it is inert.
    // F12 / ruling #123 — the same reasoning covers an OPERATIVE or PROCEDURE
    // note: a staleness gate over a level that does not exist would make a
    // colonoscopy report permanently unsignable after any edit.
    const emApplies = emAppliesToVisit({
      specialtyId: visit.specialty,
      templateSections: visit.noteTemplate?.sections ?? null,
      // `soapFinal`, not `signedSoap`: this runs BEFORE the sign, and
      // `signedSoap` is written FROM `soapFinal` further down (`:517`). So
      // this is the same bytes the signature is about to freeze.
      noteText: visit.soapFinal,
    });
    if (visit.status === TranscribeVisitStatus.READY && visit.emStale && emApplies) {
      // RE-SCORE HERE, don't just refuse.
      //
      // The first version returned 409 and told the doctor to open the codes
      // row. That made a server-side gate depend on a client control that only
      // exists behind NEXT_PUBLIC_REVIEW_DOC_VIEW — so with that flag off (its
      // own documented rollback), every edited visit became PERMANENTLY
      // unsignable, and in a second tab the named remedy did nothing.
      //
      // Doing the work here costs one scoring call on a path that is already
      // slow, only when the note actually changed, and it means the gate is
      // enforced by the route that owns the transition rather than by whichever
      // surface happens to be rendered. The lazy row-open re-score stays as an
      // optimisation, so most doctors meet the confirm card long before this.
      const rescored = await rescoreEmAction(visitId);
      if (!rescored.ok) {
        void logAudit({
          action: 'EM_SIGN_BLOCKED_STALE',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: { reason: 'rescore_failed' },
        });
        return apiError(
          "We couldn't re-check the billing level for this note. Try again in a moment.",
          409,
        );
      }
      // Take the re-score's answer WHOLESALE, not just when it armed
      // something. Patching only on `pending` left a cleared record in place:
      // the level came back to the reviewed one, the DB record was dropped,
      // and this still demanded acknowledgement of a change that no longer
      // existed — while the refreshed UI showed no control to give it.
      visit.emPendingChange = rescored.pending
        ? ({
            from: rescored.pending.from,
            to: rescored.pending.to,
            // CARRY THE CAUSE, don't assume it. Hardcoding 'note_edited' here
            // relabelled a doctor's own override as an edit — the record the
            // re-score preserves already knows which it was, and the refusal
            // message below is built from this field.
            cause: rescored.cause ?? 'note_edited',
            at: new Date().toISOString(),
          } as unknown as typeof visit.emPendingChange)
        : null;
    }

    // ⚠️ `&& emApplies` — F12-a / ruling #126, and this arm makes an operative
    // note PERMANENTLY UNSIGNABLE without it. Found by the independent
    // adversarial pass; `emApplies` has been in scope since `:335`.
    //
    // Ungated, a colonoscopy holding an `emPendingChange` gets a 400 reading
    // "Documentation level changed (99213 → 99214) … confirm the new level
    // before signing" — an office E/M level asserted about an operative note.
    // And the doctor cannot clear it: `page.tsx` nulls the client's
    // `pendingEmChange` when E/M does not apply, so the modal never collects an
    // acknowledgement, and `rescore-em.ts`'s not-applicable branch clears only
    // `emStale`, never `emPendingChange`. The loop has no exit.
    //
    // ⚠️ THIS IS THE FAILURE THE COMMENT 50 LINES ABOVE SAYS IT IS PREVENTING —
    // *"would make a colonoscopy report permanently unsignable after any
    // edit"* — fixed on the STALE arm and reintroduced on the PENDING one.
    // F12 is what makes it reachable: the predicate used to be a near-immutable
    // column, and it is now a function of the note body and the template
    // binding, both of which move on ordinary edits. TRUE-at-write /
    // FALSE-at-sign is routine now, where it used to be the "should never
    // happen" imaging artifact.
    const pendingEm =
      visit.status === TranscribeVisitStatus.READY && emApplies
        ? unacknowledgedEmChange(visit.emPendingChange)
        : null;
    if (pendingEm) {
      const ack = parsed.data.acknowledgedEmChange;
      if (!ack || ack.from !== pendingEm.from || ack.to !== pendingEm.to) {
        log.warn('api:visits:sign', 'em change unacknowledged', {
          userId,
          visitId,
          from: pendingEm.from,
          to: pendingEm.to,
          cause: pendingEm.cause,
          ackProvided: !!ack,
        });
        void logAudit({
          action: 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          success: false,
          errorCode: 'EM_CHANGE_UNACKNOWLEDGED',
          metadata: {
            from: pendingEm.from,
            to: pendingEm.to,
            cause: pendingEm.cause,
          },
        });
        return NextResponse.json(
          {
            ok: false,
            // Name the RIGHT cause. Every level change used to come from a
            // suggestion; an edit can move it now too, and telling a doctor
            // their own edit was "an AI-suggestion action" is a small lie in a
            // message whose whole job is to be believed.
            //
            // EXHAUSTIVE, not a ternary. The two-arm version put every cause it
            // did not name into "by an AI-suggestion action", so the moment a
            // doctor could set the level themselves it told them their own
            // choice was the model's. A Record over EmChangeCause means a new
            // cause fails to TYPECHECK instead of silently misattributing.
            error: `Documentation level changed (${pendingEm.from} → ${pendingEm.to}) ${
              EM_CAUSE_PHRASE[pendingEm.cause]
            } — confirm the new level before signing.`,
            code: 'EM_CHANGE_UNACKNOWLEDGED',
            pendingEmChange: { from: pendingEm.from, to: pendingEm.to },
          },
          { status: 400 }
        );
      }
    }

    // ── GATE 3 — THE ATTESTATION, NOW A SERVER TERM ─────────────────────
    // Same shape as the E/M refusal above: typed code, audit row, 400. It runs
    // for every visit that is actually being signed, on every path, because the
    // lesson that produced it is that a gate only the UI holds is one alternate
    // control away from not existing.
    //
    // ⚠️ LAST, AND THE ORDER IS THE POINT. This block sat FIRST and jumped the
    // queue: a visit with a moved E/M level answered ATTESTATION_REQUIRED
    // instead of naming the level that moved, and two tests that drive the
    // route directly to prove the E/M refusal got the wrong one. `sign-gates`
    // orders the gates rx → em → attestation, which is the order the doctor
    // walks them and the order Gate 3 sits last in. The route refuses in that
    // same order, so the FIRST thing a caller is told is the most clinically
    // specific thing that is wrong — not the formality they were going to do
    // last anyway.
    if (visit.status === TranscribeVisitStatus.READY && !parsed.data.attestation) {
      log.warn('api:visits:sign', 'attestation missing', { userId, visitId });
      void logAudit({
        action: 'SIGN_BLOCKED_NO_ATTESTATION',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        success: false,
        errorCode: 'ATTESTATION_REQUIRED',
        metadata: { status: visit.status },
      });
      return NextResponse.json(
        {
          ok: false,
          error:
            'This note has not been attested. Confirm the attestation before signing.',
          code: 'ATTESTATION_REQUIRED',
        },
        { status: 400 }
      );
    }

    let signedAt = visit.signedAt;
    if (visit.status === TranscribeVisitStatus.READY) {
      // E/M PARITY (2026-06-13, #315 obs#2): FREEZE the authoritative billing
      // code at sign time. The signed note's DISPLAYED level (override ??
      // engine, via computeDisplayedEmCode — the SAME projection the rail
      // shows and the confirm gate guards) becomes cptCodes.em.signedCode, so
      // every downstream artifact (PDF, DOCX, EHR exports) prints the level
      // the doctor reviewed and attested — NOT the raw L7b model suggestion in
      // em.code. Frozen here (not recomputed at export) so it can't drift.
      // Fail-SAFE: a scoring error must never block a sign — the export loader
      // falls back to override ?? code when signedCode is absent.
      let cptWrite: Prisma.InputJsonValue | undefined;
      const cptBlob =
        visit.cptCodes && typeof visit.cptCodes === 'object' && !Array.isArray(visit.cptCodes)
          ? (visit.cptCodes as Record<string, unknown>)
          : null;
      const emBlob =
        cptBlob && cptBlob.em && typeof cptBlob.em === 'object'
          ? (cptBlob.em as Record<string, unknown>)
          : null;
      // ⚠️ `emApplies` — F12-a / ruling #126, found by the independent
      // adversarial pass. This branch used to read `if (emBlob)` alone, and
      // `emApplies` has been sitting in scope since `:335` without being
      // consulted here. (F12-a added it as `emBlob && emApplies`; F12-e then
      // DROPPED the `emBlob` conjunct — see the F12-e block below. The reason
      // `emApplies` must be consulted at all is unchanged and is recorded
      // here; what changed is that it is now the ONLY term.)
      // On an operative note the pipeline still WRITES a
      // `cptCodes.em` blob (see the FOLLOW-UP note below), so this freeze
      // stamped a **frozen office E/M level onto the signed record** of a
      // colonoscopy — invisible, because display and export both suppress it.
      //
      // That is the artifact class this repository has already paid for once:
      // five production imaging visits acquired `emScoredCode` from a page
      // render and sat there for two days, written by no seeder and visible to
      // no test. `specialties.ts:139-143` states the invariant is enforced at
      // THREE layers — COMPUTE, STORE, EXPORT — and for the note-shape axis
      // this was the missing STORE half.
      //
      // ⚠️ FOLLOW-UP, DELIBERATELY NOT FIXED HERE: `worker.ts:963-967` gates
      // L7b on `!isImagingReportSpecialty(...)` only, so an operative note
      // still COMPUTES an `em` blob. The naive repair — adding the note-shape
      // axis to `flags.cpt` — would suppress the WHOLE of L7b and delete the
      // PROCEDURE CPT codes from a colonoscopy, which is the one code that
      // encounter genuinely bills. That is a bigger change than a one-line
      // conjunction and it is filed as its own item rather than guessed at.
      // ⚠️ F12-e — THE GATE IS `emApplies` ALONE. `emBlob &&` WAS THE DEFECT,
      // NOT THE GUARD, AND IT IS MEASURED RATHER THAN ARGUED.
      //
      // The freeze used to require that L7b had emitted an `em` blob. But the
      // level the doctor REVIEWED does not come from that blob — `page.tsx:649`
      // seeds `emScoredCode` from `initialEmScore.override ?? suggestedCode`,
      // i.e. the rubric engine scored against the note, and that seed sits
      // INSIDE `if (!emNotApplicable)`. So the rail can display a level on a
      // visit whose `cptCodes.em` is null, and then:
      //
      //   emBlob === null  ->  no signedCode frozen
      //   -> `projectEmForDisplay(null, …)` returns null at visit-export.ts:107
      //   -> the signed PDF, DOCX and EVERY EHR clipboard format print NO E/M,
      //      while the screen showed one and the doctor attested it.
      //
      // ⚠️ THIS IS LIVE IN PRODUCTION, NOT A HYPOTHETICAL, AND NOT MERELY
      // ARMED BY F12-c. Measured read-only on prod, 2026-08-27: **12** visits
      // carry `cptCodes.em = null` AND a non-null `emScoredCode` — **10 of
      // them SIGNED** — `bariatric-surgery` and `gastroenterology`, **zero**
      // imaging. `emScoredCode` is only ever written under `!emNotApplicable`,
      // so its presence is structural proof the predicate said E/M APPLIES,
      // established without reading one byte of note text.
      //
      // The filing expected `cptCodes.emSuppressed` to be the hook. It is not
      // needed: `emSuppressed` distinguishes *why* the blob is absent, and the
      // freeze does not care. E/M PARITY (#315 obs#2) says the artifact prints
      // the level the doctor reviewed and attested; the CURRENT verdict on the
      // note being signed is `emApplies`, and that is the whole gate. Keeping
      // `emBlob &&` would make a standing ruling contingent on whether a model
      // happened to return a field.
      //
      // Direction of harm, stated because this house ranks them: this moves an
      // ABSENT field to the level the doctor confirmed. It cannot introduce the
      // WRONG-field harm — `emApplies` is the same predicate the export seam
      // already trusts (`visit-export-server.ts:151-163`), so a suppressed note
      // shape is still suppressed, and #123 / #126 / #128 are untouched.
      if (emApplies) {
        try {
          const signedCode = await computeDisplayedEmCode(
            visit.soapFinal ?? '',
            { icdCodes: visit.icdCodes, rxDrafts: visit.rxDrafts, cptCodes: visit.cptCodes },
            { practiceId: session?.user?.practiceId, visitId, userId }
          );
          // `cptBlob`/`emBlob` may both be null now that the gate no longer
          // requires them. Spreading null yields `{}`, which is the intended
          // shape — but it is written explicitly so a reader does not have to
          // know that, and so a future edit cannot silently depend on it.
          cptWrite = {
            ...(cptBlob ?? {}),
            em: { ...(emBlob ?? {}), signedCode },
          } as Prisma.InputJsonValue;
        } catch (err) {
          log.warn('api:visits:sign', 'em signedCode freeze failed — export falls back to override ?? code', {
            visitId,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
      // ⚠️ FREEZE THE PAIR BEFORE THE SIGNATURE — F5-f ruling 1.
      //
      // `native-export` declines a manifest that no longer matches the note, so
      // a stale document is never SERVED. But a visit signed while stale is
      // frozen stale: afterwards the compute path refuses to recompute
      // (`visit_not_eligible`), so the doctor's own letterhead is unavailable
      // on their own signed record, permanently, with no stated reason.
      //
      // Re-fill happens HERE, before the row becomes SIGNED, so a fresh
      // manifest and the signed note correspond by construction.
      //
      // ⚠️ AND IT NEVER BLOCKS THE SIGNATURE. Every failure path below lets the
      // sign proceed styled — a formatting subsystem must not stand between a
      // doctor and their signature. What is forbidden is SILENCE, so the reason
      // reaches BOTH the audit row and the response the doctor sees. Same shape
      // as the E/M signedCode freeze above.
      // ⚠️ LAZY IMPORT, DELIBERATELY. A static import pulls the whole fill engine
      // into this route's module graph — a route a doctor waits on, and one
      // whose existing tests mock `@meddoc/ai` narrowly. Widening that graph
      // broke an unrelated sign test on first attempt.
      // ⚠️ THE IMPORT IS INSIDE THE TRY, AND THAT IS THE WHOLE POINT.
      //
      // The first draft put `await import(...)` OUTSIDE the `.catch`, which
      // covered only the CALL. A module-load rejection therefore escaped the
      // handler, `withApiHandler` returned 500, and the `updateMany` that writes
      // SIGNED never ran — the visit stayed READY and the doctor COULD NOT SIGN.
      //
      // That falsified this change's own central claim, stated twice in its own
      // comments, and my gate was GREEN with the defect present: its substring
      // window checked for `.catch(` and never asked what the catch covered.
      // Found by the refutation pass over POST /sign.
      //
      // ⚠️ AND IT IS FLAG-GATED. `freezeNativeManifestForSigning` was the only
      // entry point to the twin subsystem not behind `templateNativeDocxEnabled`,
      // so the documented flag rollback would still have run a full fill inside
      // the signature request and still shown the doctor a notice about a
      // feature that is switched off.
      try {
        if (templateNativeDocxEnabled()) {
          const { freezeNativeManifestForSigning } = await import(
            '@/lib/template-twin/sign-freeze'
          );
          nativeFreeze = await freezeNativeManifestForSigning({
            visitId,
            practiceId: session.user.practiceId,
          });
        }
      } catch (err) {
        nativeFreeze = {
          state: 'failed',
          reason: err instanceof Error ? err.message : 'freeze_threw',
        };
      }
      if (nativeFreeze.state === 'failed') {
        log.warn(
          'api:visits:sign',
          'native manifest could not be refreshed — signing styled',
          { visitId, reason: nativeFreeze.reason }
        );
      }

      // ⚠️ THE POINTER MUST NEVER COST A SIGNATURE.
      //
      // `frozenFillManifestId` is a FOREIGN KEY written inside the one statement
      // that must not fail. A concurrent note-template delete cascades the
      // visit's fill manifest away, and this UPDATE would then violate the FK
      // and throw — a doctor unable to sign because a FORMATTING artifact was
      // removed underneath them. Found by the aimed TOCTOU pass.
      //
      // Attempted with the pointer, retried WITHOUT it. Signing styled is the
      // correct degraded outcome and is already a first-class state (null =
      // this signature froze no native document), so the retry lands in a
      // meaning the rest of the system already understands.
      // ⚠️ THE E/M STATE IS RE-READ INSIDE THE GUARDED WRITE — F5-h ruling 1.
      //
      // `cptCodes` and `emPendingChange` were both built from the :198 capture
      // and written after every intervening await — a read-modify-write across
      // seconds, including the whole sign-freeze window.
      //
      // `POST /em-score/override` is the concurrent writer, and it DELIBERATELY
      // does not bump `soapVersion` ("an override is not a note edit" — which is
      // correct: a coding decision must never trip a colleague's note-CAS into a
      // 409). So the note-CAS passes and the signature's whole-blob overwrite
      // ERASED the doctor's override — code, typed reason and timestamp — then
      // froze `signedCode` at the model's level.
      //
      // The fix is not a wider CAS. It is to stop the stale read being an INPUT:
      // the blob is re-read inside the same statement's transaction, and the
      // override — whenever it landed — wins by construction.
      //
      // ⚠️ THE EXPENSIVE PART STAYS OUTSIDE. `computeDisplayedEmCode` awaits
      // `computeEmScore`, which can reach a model; holding a row lock across
      // that is how a formatting concern becomes a database incident. Only the
      // PRECEDENCE is applied inside — `override.code ?? engine.code`, the same
      // projection the rail and the gate use.
      class EmChangedWhileSigning extends Error {
        constructor(readonly emFrom: string, readonly emTo: string) {
          super('EM_CHANGED_WHILE_SIGNING');
          this.name = 'EmChangedWhileSigning';
        }
      }

      // ⚠️ SERIALIZABLE, THE SAME LEVEL THE FILL ENGINE'S CREATE PATH USES.
      // At Postgres's default READ COMMITTED the re-read and the CAS-guarded
      // `updateMany` take two snapshots, so an override committing between
      // them is invisible to BOTH — to the read (uncommitted) and to the CAS
      // (it touches neither `status` nor `soapVersion`). That is the original
      // erasure race with a smaller window, which is not the same as a closed
      // one. Serializable makes the pair atomic; the expensive work stays
      // outside, so the transaction holds for one round trip.
      const signWrite = (frozenId: string | null) =>
        prisma.$transaction(async (tx) => {
          const fresh = await tx.transcribeVisit.findFirst({
            where: visitByIdScope(visitId, session.user.practiceId),
            select: { cptCodes: true, emPendingChange: true },
          });
          const freshBlob = (fresh?.cptCodes ?? null) as {
            em?: { override?: { code?: string } };
          } | null;
          const freshOverride = freshBlob?.em?.override?.code;

          // ⚠️ THE GATE AND THE WRITE MUST JUDGE THE SAME SNAPSHOT.
          //
          // The aimed re-run caught this in W1 itself, and it is the canon
          // shape: *"an absent field is content the doctor did not see; a WRONG
          // field is content that says the opposite of the record being
          // signed — and restoring a surface can introduce the second while
          // fixing the first."*
          //
          // Before W1, a concurrent override was ERASED by the whole-blob
          // overwrite. Data loss, and the record stayed internally honest: it
          // froze the level the signer had actually reviewed.
          //
          // W1 fixed the erasure by reading `cptCodes` fresh — and in the same
          // expression started freezing a level NOTHING ON THE RECORD SAYS WAS
          // CONFIRMED. `POST /em-score/override` deliberately does not move
          // `soapVersion` (a coding decision must not trip a colleague's
          // note-CAS), so it is invisible to the CAS; and the confirm gate ran
          // hundreds of lines earlier against the ENTRY capture. The signed
          // record could therefore assert an acknowledged 99213→99214 while
          // freezing 99215. That is strictly worse than the bug it replaced.
          //
          // The fix is NOT to go back to the stale read. It is to make the
          // divergence IMPOSSIBLE rather than silent: the same transaction
          // re-reads the gate's own datum, and a change the gate never judged
          // REFUSES the signature. The doctor confirms it and signs again —
          // which is the product behaviour they already know, arriving one
          // moment later than usual.
          //
          // The override still wins by construction. It simply cannot be frozen
          // without an attestation naming it.
          const freshPending = emApplies
            ? unacknowledgedEmChange(fresh?.emPendingChange)
            : null;
          const gateJudged = pendingEm;
          const divergent =
            freshPending !== null &&
            (gateJudged === null ||
              freshPending.from !== gateJudged.from ||
              freshPending.to !== gateJudged.to ||
              freshPending.at !== gateJudged.at);
          if (divergent) {
            throw new EmChangedWhileSigning(freshPending.from, freshPending.to);
          }

          // Start from the FRESH blob so a concurrent override survives; layer
          // this signature's frozen level on top, deferring to the override.
          const mergedCpt =
            cptWrite === undefined
              ? undefined
              : ({
                  ...(freshBlob ?? {}),
                  em: {
                    ...(freshBlob?.em ?? {}),
                    ...((cptWrite as { em?: object }).em ?? {}),
                    // the override itself is never overwritten
                    ...(freshBlob?.em?.override
                      ? { override: freshBlob.em.override }
                      : {}),
                    signedCode:
                      freshOverride ??
                      ((cptWrite as { em?: { signedCode?: string } }).em?.signedCode ??
                        undefined),
                  },
                } as Prisma.InputJsonValue);

          return tx.transcribeVisit.updateMany({
        where: {
          ...visitByIdScope(visitId, session.user.practiceId),
          status: TranscribeVisitStatus.READY,
          // ⚠️ A SIGNED RECORD IS ONE FROZEN OBJECT — COMPARE-AND-SWAP ON THE
          // NOTE'S IDENTITY.
          //
          // `signedSoap` is written from the in-memory `visit.soapFinal`
          // captured at entry, and the freshness check and any re-fill target
          // that SAME capture. Without this guard a save landing between the
          // capture and this write produced a signed record whose frozen text
          // was one version and whose native document was bound to another —
          // the download could contain clinical text the signature does not.
          //
          // With it: a doctor signs what they saw, or signs nothing.
          soapVersion: visit.soapVersion,
        },
        data: {
          status: TranscribeVisitStatus.SIGNED,
          signedSoap: visit.soapFinal,
          // ⚠️ THE POINTER AND THE SIGNATURE ARE ONE WRITE — ruling 2(b).
          //
          // The SIGNED serve path resolves the document by THIS id and never by
          // lookup, so a manifest that lands afterwards (an orphaned fill whose
          // wait was abandoned) is UNREACHABLE rather than merely refused.
          // Layer (a) makes that write impossible; this makes a write that
          // slipped through inert.
          //
          // NULL is not an absence of information: it records that this
          // signature froze NO native document and the record is styled,
          // deliberately and forever.
          frozenFillManifestId: frozenId,
          signedAt: new Date(),
          // ⚠️ T4 — THE SIGNER, STAMPED SERVER-SIDE, IN THE SAME STATEMENT AS
          // THE SIGNATURE. `userId` is `session.user.id` (line ~137), resolved
          // from the session cookie — it is NEVER read from the request body,
          // because a client-supplied signer is a client-supplied claim about
          // who attested to a clinical record.
          //
          // Set HERE rather than in a follow-up update, deliberately: this
          // `updateMany` is one atomic statement, so a row cannot exist in the
          // window between "signed" and "attributed". The DB CHECK
          // (`signedAt IS NULL OR signedBy IS NOT NULL`) makes that window
          // unrepresentable anyway — this is the code side of the same rule, so
          // the constraint never has to fire in normal operation.
          signedBy: userId,
          ...(mergedCpt !== undefined ? { cptCodes: mergedCpt } : {}),
          // E/M visible-confirm: the gate above verified the explicit
          // acknowledgement — MARK (not clear) the record so the row
          // keeps the forensic trail alongside the audit rows.
          // ⚠️ THE FRESH RECORD, NOT THE CAPTURED ONE. The re-read above
          // refused every value that diverges from what the gate judged, so
          // by here `freshPending` IS the gate's change — or the doctor
          // reverted it mid-signature and there is nothing left to
          // acknowledge. Spreading the captured `pendingEm` instead would
          // stamp an acknowledgement onto a record the database no longer
          // holds, which is the same lie one field over.
          ...(freshPending
            ? {
                emPendingChange: {
                  ...freshPending,
                  acknowledgedAt: new Date().toISOString(),
                } as unknown as Prisma.InputJsonValue,
              }
            : {}),
        },
          });
        },
        { isolationLevel: Prisma.TransactionIsolationLevel.Serializable });

      let updated: { count: number };
      try {
       try {
        // ⚠️ THE POINTER IS DERIVED AT WRITE TIME, NOT TRUSTED FROM THE FREEZE.
        //
        // `nativeFreeze.manifestId` is an in-memory value computed BEFORE the
        // CAS. Two interleaves make it wrong, and the aimed pass demonstrated
        // both:
        //   · two concurrent signs — the loser's fill throws MANIFEST_CONFLICT,
        //     its outcome is `failed` (a variant that structurally carries no
        //     manifestId), and it stamps NULL even though the winner produced
        //     exactly the document this note needs;
        //   · a single sign whose 20s race expired — the orphaned fill lands
        //     the correct manifest moments later, and NULL is stamped anyway.
        //
        // Either way the record is styled FOREVER and its audit row asserts a
        // downgrade that did not happen.
        //
        // So the question asked here is not "what did MY freeze produce" but
        // "which manifest corresponds to the text I am about to sign" — which
        // is answerable from the database, by anyone, at the last moment.
        const { resolveFrozenPointer } = await import(
          '@/lib/template-twin/sign-freeze'
        );
        const pointer = await resolveFrozenPointer(
          visitId,
          session.user.practiceId,
          visit.soapFinal
        );
        if (!pointer && nativeFreeze.state !== 'failed') {
          nativeFreeze = { state: 'failed', reason: 'no_matching_manifest_at_signature' };
        } else if (pointer && nativeFreeze.state === 'failed') {
          // Another actor produced it. The downgrade notice would be a lie.
          nativeFreeze = { state: 'regenerated', manifestId: pointer };
        }
        updated = await signWrite(pointer);
      } catch (err) {
        // ⚠️ THE E/M REFUSAL IS NOT A MANIFEST FAILURE AND MUST NOT BE
        // RETRIED STYLED. Falling through here would re-run the identical
        // transaction, hit the identical divergence, and — because the second
        // throw lands outside this try — surface as a 500 on a route whose
        // whole job is to be precise about why a signature did not happen.
        // The doctor needs the coding card, not an error page.
        // ⚠️ RETHROWN, NOT ANSWERED HERE — AND NOT RETRIED STYLED.
        // The styled retry below lives INSIDE this catch, so an E/M refusal
        // raised by THAT attempt would escape the try entirely and reach the
        // client as a 500. Both attempts therefore hand the sentinel to the
        // outer handler, where the refusal is written exactly once.
        if (err instanceof EmChangedWhileSigning) throw err;
        log.warn(
          'api:visits:sign',
          'frozen manifest unavailable at signature — signing styled',
          { visitId, error: err instanceof Error ? err.message : String(err) }
        );
        nativeFreeze = { state: 'failed', reason: 'frozen_manifest_vanished' };
        updated = await signWrite(null);
       }
      } catch (err) {
        if (!(err instanceof EmChangedWhileSigning)) throw err;
        // ⚠️ THE SAME `code` THE ENTRY GATE USES, DELIBERATELY.
        //
        // The aimed pass's sibling finding was that `supersededBy` is a wire
        // field NOTHING READS — an honest server still handing the loser a
        // success-shaped 200. A fresh code here would repeat that mistake one
        // refusal over: the client would fall to its generic error toast and
        // the doctor would be told "something went wrong" about a coding
        // change they can resolve in one click.
        //
        // `EM_CHANGE_UNACKNOWLEDGED` already has a renderer — the confirm
        // card — and this IS that condition, discovered a few hundred
        // milliseconds later than usual. Reusing it ships the fix with a
        // working surface instead of a wire field and a promise.
        void logAudit({
          // ⚠️ THE EXISTING VALUE, NOT A FOURTH ONE. A new enum member is
          // THREE edits (TS union, Prisma enum, its own Postgres migration)
          // and this programme has shipped that half-done twice.
          // `EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE` already means exactly "a
          // sign request was rejected over an unacknowledged E/M change"; the
          // only difference is WHEN it was detected, carried as metadata.
          action: 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE',
          userId,
          practiceId: session.user.practiceId,
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: {
            reason: 'em_changed_between_gate_and_write',
            from: err.emFrom,
            to: err.emTo,
            gateJudged: pendingEm
              ? { from: pendingEm.from, to: pendingEm.to }
              : null,
          },
        });
        return NextResponse.json(
          {
            ok: false,
            error: `Documentation level changed (${err.emFrom} → ${err.emTo}) while you were signing — confirm the new level before signing.`,
            code: 'EM_CHANGE_UNACKNOWLEDGED',
            pendingEmChange: { from: err.emFrom, to: err.emTo },
          },
          { status: 409 }
        );
      }
      // The pre-sign preview cache is keyed on soapVersion, which SIGNING DOES
      // NOT BUMP — so without this a signed visit could be served the pre-sign
      // render for the rest of the TTL, defeating the rule that a signed
      // document is never re-derived. Preview-side only; nothing here is read
      // by this route's own gates.
      void invalidateVisitFills(visitId);

      if (updated.count === 0) {
        // Another concurrent request got there first. Re-read.
        const refreshed = await prisma.transcribeVisit.findFirst({
          where: visitByIdScope(visitId, session.user.practiceId),
          select: {
            signedAt: true,
            status: true,
            soapVersion: true,
            signedBy: true,
            signer: { select: { name: true, email: true } },
          },
        });
        if (refreshed?.status !== TranscribeVisitStatus.SIGNED) {
          // ⚠️ TWO DIFFERENT RACES, TWO DIFFERENT MESSAGES. A doctor whose note
          // moved under them must re-read it before signing again; one who
          // simply lost a double-click need not.
          const noteMoved = refreshed?.soapVersion !== visit.soapVersion;
          return apiError(
            noteMoved
              ? 'note changed while signing — reload and review before signing'
              : 'sign race lost — please refresh and retry',
            409
          );
        }
        // ⚠️ THE LOSER IS TOLD WHAT HAPPENED — F5-h ruling 2.
        //
        // This branch used to fall through to a 200 that looks exactly like a
        // successful signature. It is not one: THIS request signed nothing.
        // Another actor did, possibly against a different version of the note.
        //
        // ⚠️ AND THE ATTESTATION IS RECORDED RATHER THAN DISCARDED. The route
        // treats it as a mandatory server term (400 ATTESTATION_REQUIRED), so a
        // term that was offered and then silently dropped is exactly the silence
        // family this programme keeps closing. It becomes a RECORDED NON-EVENT.
        // ⚠️ ONLY NAME A COLLEAGUE WHEN IT WAS ONE. Nothing serialises two
        // sign requests from one session — no lock, no idempotency key — so a
        // double-submit loses the CAS to ITSELF. Telling that caller "Dr X
        // signed this first" when Dr X is the caller is a fabricated second
        // actor in a clinical audit trail, and `signedBy` may also be null on
        // a legacy row. Both collapse to the honest, unnamed sentence.
        const supersededBySelf =
          refreshed.signedBy !== null && refreshed.signedBy === userId;
        supersededBySigner = supersededBySelf
          ? 'this account (a second signature request)'
          : (refreshed.signer?.name ?? refreshed.signer?.email ?? 'another clinician');
        void logAudit({
          // ⚠️ NOT `VISIT_SIGNED` — THIS REQUEST SIGNED NOTHING.
          //
          // The first draft used it and my OWN gate caught it: two rows claiming
          // that action for one visit is the corrupted trail, and a reader doing
          // `.find(action === 'VISIT_SIGNED')` would pick the non-signature.
          // The `SIGN_BLOCKED_*` family already means "an attempt that did not
          // produce a signature", which is exactly this — and reusing it avoids
          // the three-edit enum trap for a value that would mean the same thing.
          action: 'SIGN_BLOCKED_NO_ATTESTATION',
          userId,
          practiceId: session.user.practiceId,
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: {
            // The attestation WAS supplied — the block is the lost race. Named
            // in the metadata so the row is not misread as a missing term.
            sign_attempt_superseded: true,
            supersededBy: refreshed.signedBy ?? null,
            attestedSoapVersion: visit.soapVersion,
            signedSoapVersion: refreshed.soapVersion,
            attestation: parsed.data.attestation ?? null,
          },
        });
        // ⚠️ AND ITS OWN freeze VERDICT IS SUPPRESSED. `nativeFreeze` describes
        // work this request did that never reached the record; reporting it
        // would describe a freeze that did not win.
        nativeFreeze = { state: 'not_applicable' };
        signedAt = refreshed.signedAt;
      } else {
        const refreshed = await prisma.transcribeVisit.findFirst({
          where: visitByIdScope(visitId, session.user.practiceId),
          select: { signedAt: true },
        });
        signedAt = refreshed?.signedAt ?? new Date();
        // T-M14.1: fire-and-forget edit-pattern capture. Only on the
        // winning transition — race losers already have a capture in
        // flight from the winner's handler, and the @unique visitId
        // constraint would reject a second insert anyway.
        void captureEditPattern({
          visitId,
          doctorId: userId,
          practiceId: session.user.practiceId,
        });
        // HIPAA audit — one row per successful READY→SIGNED transition.
        // Race losers (updated.count===0) don't re-write; the winner
        // already covered them.
        void logAudit({
          action: 'VISIT_SIGNED',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: {
            destinations: parsed.data.destinations,
            // E/M visible-confirm: record on the SIGN audit row that the
            // doctor explicitly acknowledged the suggestion-caused level
            // change ({from, to} codes only — never note text).
            ...(pendingEm
              ? {
                  emChangeAcknowledged: {
                    from: pendingEm.from,
                    to: pendingEm.to,
                  },
                }
              : {}),
            // ⚠️ THE DOWNGRADE RIDES THE SIGNATURE'S OWN ROW — one signature,
            // one audit row.
            //
            // An earlier draft emitted a SECOND `VISIT_SIGNED` row carrying
            // this reason. Two rows claiming the same action for one signature
            // is a corrupted trail, and the first of them was not a signature
            // at all. It was caught by an existing sign test whose
            // `.find(action === 'VISIT_SIGNED')` picked up my row instead of
            // the real one — the audit trail's own reader noticing the
            // duplicate before any human did.
            ...(nativeFreeze.state === 'failed'
              ? {
                  signNativeRefreshFailed: true,
                  signNativeRefreshReason: nativeFreeze.reason,
                }
              : {}),
          },
        });
      }
    }

    // ── Deliver ─────────────────────────────────────────────────────
    // loadVisitExportData reads the freshly-signed row so downstream
    // generators see signedSoap / signedAt set correctly.
    const data = await loadVisitExportData(visitId, session.user.practiceId);
    if (!data) return apiError('visit disappeared after signing', 500);

    const clipboardTexts: Record<string, string> = {};
    let pdfDownloadUrl: string | undefined;
    let docxDownloadUrl: string | undefined;
    let emailQueued = false;
    // Track which destinations actually succeeded vs which soft-failed so
    // the client can tell the user specifically what didn't go through.
    const deliveryErrors: Record<string, string> = {};

    for (const dest of parsed.data.destinations) {
      const channel: DeliveryChannel = dest;
      try {
        if (dest === 'pdf') {
          // The browser does the actual download; we return a URL so the
          // JSON response stays small. We still log here — the user
          // explicitly requested a PDF delivery, and the dedicated route
          // will log again when they fetch. Two rows is fine; it
          // reflects intent + completion.
          pdfDownloadUrl = `/api/visits/${visitId}/export/pdf`;
          logDelivery({ visitId, practiceId: session.user.practiceId, channel });
        } else if (dest === 'docx') {
          docxDownloadUrl = `/api/visits/${visitId}/export/docx`;
          logDelivery({ visitId, practiceId: session.user.practiceId, channel });
        } else if (dest === 'email') {
          if (!process.env.RESEND_API_KEY) {
            deliveryErrors[dest] =
              'email delivery is not configured on this environment';
            continue;
          }
          // Guard above already enforced emailTo === sessionEmail
          // when present. Resolve to sessionEmail explicitly to
          // close the loop for any future refactor of the guard.
          const to = sessionEmail;
          // ⚠️ Ruling #116(b) — a full PDF render of this patient's signed note
          // USED to happen here, purely to read `pdf.byteLength` into
          // `logDelivery({ sizeBytes })`. The email has carried a link rather
          // than an attachment since `sendVisitPdfEmail` changed, so the
          // document was rendered and dropped.
          //
          // `sizeBytes` is WRITE-ONLY — enumerated, not assumed: `visitDelivery`
          // has exactly one reference in the application (the `.create` in
          // `deliveries.ts`), with no read in any route, action, admin surface
          // or test. Under #113 that render would have become a Gotenberg
          // network round-trip INSIDE `POST /sign`, the most critical clinical
          // action in the product, for a number nobody queries. Deleted.
          await sendVisitPdfEmail({
            toEmail: to,
            visitId,
            doctorName: data.clinicianName,
            // Ruling #115 — SIGNING date, deliberately: the body says "a note
            // you signed on X". Not one of the eight visit-date sites.
            signedDate: formatVisitDate(data.signedAt ?? data.createdAt),
          });
          emailQueued = true;
          logDelivery({
            visitId,
            practiceId: session.user.practiceId,
            channel,
            destination: to,
          });
        } else {
          const format = FORMAT_FOR_CHANNEL[dest];
          if (!format) continue;
          const text = formatForEhr(format, data);
          clipboardTexts[dest] = text;
          logDelivery({
            visitId,
            practiceId: session.user.practiceId,
            channel,
            sizeBytes: Buffer.byteLength(text, 'utf8'),
          });
        }
      } catch (err) {
        // T-M16.3: Resend/MinIO/PDF errors occasionally echo recipient
        // email or filename — scrub before logging.
        console.error(
          `[api:visits:sign] destination ${dest} failed:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
        deliveryErrors[dest] =
          err instanceof Error ? err.message : 'delivery failed';
      }
    }

    return NextResponse.json(
      {
        signedAt: signedAt?.toISOString() ?? null,
        clipboardTexts,
        pdfDownloadUrl,
        docxDownloadUrl,
        emailQueued,
        // Present ONLY when this request did not produce the signature.
        supersededBy: supersededBySigner ?? undefined,
        // ⚠️ THE DOCTOR LEARNS AT SIGN TIME, NOT AT DOWNLOAD TIME.
        //
        // Present ONLY when the native document could not be refreshed against
        // the signed note, so the record's exports are the styled layout rather
        // than their own form. Signing succeeded; the downgrade did not silently
        // succeed with it. Absent on every healthy path, so a client need not
        // special-case the common case.
        formatNotice:
          nativeFreeze.state === 'failed'
            ? {
                reason: nativeFreeze.reason,
                message:
                  'Signed. This record exports in the standard layout — your own ' +
                  'form could not be regenerated for the signed note.',
              }
            : undefined,
        deliveryErrors: Object.keys(deliveryErrors).length
          ? deliveryErrors
          : undefined,
      },
      { status: 200 }
    );
  }
);
