// ============================================================================
// POST /api/visits/[id]/icd-codes/decision   (F8-S1)
// ----------------------------------------------------------------------------
// Body:     { code: string, decision: 'accepted' | 'rejected' | 'cleared' }
// Response: { ok: true, changed: boolean, projection, summary }
//
// F8 constraints (c) and (d): the physician's accept/reject is the authority,
// and every accept/reject writes an audit row. (a) evidence-mandatory and
// (b) allowlist-validated are already satisfied at GENERATION time by
// `07a-icd-coding.ts`, and this route never admits a code that layer did not
// produce — so neither guarantee is weakened by a decision surface existing.
//
// ⚠️ WHAT THIS ROUTE DELIBERATELY DOES NOT DO — F8-S1 IS THE SUBSTRATE.
//   · It does not change what any export or note emits. An accepted code
//     flows nowhere yet; that is a later slice and it is a document-visible
//     change that will need its own adversarial pass.
//   · It has NO UI CALLER on `main`. Said plainly because AGENTS.md records
//     the opposite failure twice — a capability with no caller passes every
//     test it has. The RELAY row names the consuming slice rather than
//     claiming F8 is done.
//
// Modelled on `POST /api/visits/[id]/em-score/override`, the nearest precedent
// here: a physician's coding decision, persisted to a Json column, audited,
// refused on a signed visit, 404 on ownership mismatch.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';

import { getSession } from '@/lib/auth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope, scopedUpdate, type PracticeId } from '@/lib/practice-scope';
import { logAudit, type AuditAction } from '@/lib/audit';
import {
  ICD_DECISION_INTENTS,
  ICD_REJECTION_REASONS,
  applyIcdDecision,
  icdDecisionSummary,
  projectIcdDecisions,
  type IcdDecisionIntent,
  type IcdDecisionRefusal,
} from '@/lib/icd-decisions';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

// ICD-10-CM is at most 7 characters plus the decimal point. The cap exists so
// a fat-fingered payload cannot bloat audit metadata; the REAL gate is
// membership of this visit's suggested set, which no length check substitutes
// for.
const MAX_CODE_LENGTH = 10;

const BodySchema = z.object({
  code: z.string().trim().min(2).max(MAX_CODE_LENGTH),
  decision: z.enum(ICD_DECISION_INTENTS),
  // ⚠️ A CLOSED ENUM AT THE EDGE, NEVER A STRING — RULING #154 (PROVISIONAL).
  // `z.enum` REFUSES anything outside the vocabulary at the boundary, so a
  // free-text rejection reason cannot reach the column even if a client sends
  // one. `z.string()` here with validation deeper in would have left one
  // forgotten call site between a doctor's prose and a JSONB blob the browser
  // reads. The pure layer re-checks it anyway; this is the outer of two.
  reason: z.enum(ICD_REJECTION_REASONS).optional(),
});

/** One label per intent. `cleared` is its own event — see the migration. */
const AUDIT_ACTION: Record<IcdDecisionIntent, AuditAction> = {
  accepted: 'ICD_CODE_ACCEPTED',
  rejected: 'ICD_CODE_REJECTED',
  cleared: 'ICD_CODE_DECISION_CLEARED',
};

/**
 * ⚠️ #148(e)'s OBLIGATION, FALLING DUE EXACTLY WHERE IT SAID IT WOULD.
 *
 * S1 deliberately did not audit refusals, and wrote its own re-arming
 * condition down: *"the moment a UI can invoke this route, a refused decision
 * becomes an event somebody will ask about — S2 revisits this."* **This slice
 * is that UI.** So refusals are audited now, under a fourth label.
 *
 * ⚠️ WHAT MAKES A REFUSAL WORTH A ROW, AND WHY IT IS NOT ALL OF THEM. A row is
 * written when an AUTHENTICATED, PRACTICE-SCOPED caller was refused a decision
 * on a visit they can see. Those are the ones a coding dispute asks about:
 * *"the doctor says they rejected that code — what happened?"*
 *
 * **401 is NOT audited**: there is no actor to attribute it to, and
 * `logAudit` needs one. **404 is NOT audited**: it is the ownership gate, it
 * fires on a foreign or non-existent id, and writing a row would let an
 * unauthorised prober append to the audit log of a practice they cannot read —
 * turning an information-leak refusal into an information-leak WRITE.
 */
const REFUSAL_AUDIT_LABEL: AuditAction = 'ICD_CODE_DECISION_REFUSED';

/** The refusal tokens that reach the audit row. Every one of them is emitted
 *  by code in this file or by `applyIcdDecision`, never composed from prose. */
type RefusalToken =
  | IcdDecisionRefusal
  | 'visit_not_active'
  | 'visit_locked'
  | 'visit_not_ready';

export const POST = withApiHandler<{ id: string }>(
  'api:visits:icd-codes:decision',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const practiceId = (session?.user as any)?.practiceId as string | undefined;
    if (!userId || !practiceId) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      return apiError('invalid decision payload', 400, { code: 'INVALID_REQUEST' });
    }

    // ── EVERY GATE AND THE WRITE RUN UNDER ONE ROW LOCK ────────────────────
    //
    // ⚠️ `icdDecisions` IS A WHOLE-COLUMN OVERWRITE BUILT FROM A VALUE THIS
    // REQUEST READ. Without the lock, a doctor accepting two codes in quick
    // succession has two requests each read the map, each add their own entry,
    // and the second write silently DROPS the first — a recorded clinical
    // decision lost, with no error anywhere and nothing to reconstruct it
    // from. That is F5-h's class exactly ("read fresh, written stale"), which
    // this repository has already paid for once on the E/M blob.
    //
    // ⚠️ AND THE GATES ARE INSIDE THE LOCK, NOT ONLY THE WRITE. A visit signed
    // between a gate read and the write would otherwise take a decision AFTER
    // its signature — the freeze bypassed by a race rather than by a caller.
    //
    // The lock is taken on the PRACTICE-SCOPED row, so a foreign id locks
    // nothing and falls straight through to the 404 below. `$queryRaw`'s
    // tagged-template form parameterises both values.
    const { response, audit } = await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      await tx.$queryRaw`
        SELECT id FROM "transcribe_visits"
        WHERE id = ${visitId} AND "practiceId" = ${practiceId}
        FOR UPDATE`;
      return decide(tx, {
        visitId,
        // The BRANDED id, which is what `visitByIdScope` requires. The plain
        // string above is only ever a query parameter.
        practiceId: session.user.practiceId,
        userId,
        code: parsed.data.code,
        decision: parsed.data.decision,
        reason: parsed.data.reason,
      });
    });

    // ⚠️ THE AUDIT ROW IS EMITTED OUTSIDE THE TRANSACTION, ON PURPOSE.
    // `logAudit` is fire-and-forget so an audit failure can never refuse a
    // clinical action; running it inside would attach that fire-and-forget
    // promise to a transaction that has already resolved. It fires only when
    // the write actually committed, because `decide` returns it only then.
    if (audit) void logAudit(audit);

    return response;
  },
);

interface DecideInput {
  visitId: string;
  practiceId: PracticeId;
  userId: string;
  code: string;
  decision: IcdDecisionIntent;
  reason?: string;
}

/**
 * The refusal audit row. Metadata carries the SAME fields the success rows do
 * plus the refusal token — the code only, never the description, exactly as
 * `#148(d)` requires and for the identical reason.
 *
 * ⚠️ `attempted` IS THE INTENT, NOT A STATE TRANSITION. A refused request made
 * no transition, so there is no `fromState`/`toState` to report and inventing a
 * pair would make a refusal look like a decision in the one log a coding
 * dispute reads. Different event, different metadata shape.
 */
function refusalAudit(
  input: DecideInput,
  refusal: RefusalToken,
): Parameters<typeof logAudit>[0] {
  return {
    action: REFUSAL_AUDIT_LABEL,
    targetType: 'transcribe_visit',
    targetId: input.visitId,
    metadata: {
      code: input.code.trim().toUpperCase(),
      attempted: input.decision,
      refusal,
    },
  };
}

/**
 * The gated body. Split out only so that every refusal AND the write live
 * together inside the locked transaction — there is no window between deciding
 * and writing for anything to change underneath.
 *
 * Returns the response plus the audit row to emit, if any. A NO-OP returns no
 * audit row: re-asserting the stored state is not an event, the same reasoning
 * `PROMO_GRANT_CREDITED` uses for its own already-granted case.
 */
async function decide(
  // The interactive-transaction client. Annotated because the `@meddoc/db`
  // barrel is deliberately `any` at the boundary, so `tx` would otherwise be
  // implicitly `any` and the reads below would typecheck against nothing.
  tx: Prisma.TransactionClient,
  input: DecideInput,
): Promise<{ response: ReturnType<typeof NextResponse.json>; audit: Parameters<typeof logAudit>[0] | null }> {
  const scope = visitByIdScope(input.visitId, input.practiceId);

  // Ownership gate. 404 on mismatch — never leak existence.
  const visit = await tx.transcribeVisit.findFirst({
    where: scope,
    select: {
      id: true,
      status: true,
      deletedAt: true,
      archivedAt: true,
      signedAt: true,
      icdCodes: true,
      icdDecisions: true,
    },
  });
  if (!visit) return { response: apiError('not found', 404), audit: null };

  if (visit.deletedAt !== null || visit.archivedAt !== null) {
    return {
      response: apiError('Visit is no longer active.', 400, { code: 'VISIT_NOT_ACTIVE' }),
      audit: refusalAudit(input, 'visit_not_active'),
    };
  }

  // ⚠️ THE FREEZE, AND IT LIVES HERE RATHER THAN IN THE UI.
  // The contract's state table says a signed visit is "read-only; decisions
  // frozen". A signed note is an attested record: changing which codes it
  // carries after the signature would alter what a physician attested to, and
  // "the UI wouldn't offer that" is exactly how an office E/M code once
  // reached an ultrasound report. Server-side and flag-independent, the same
  // posture `POST /sign` takes.
  if (visit.signedAt !== null || visit.status === TranscribeVisitStatus.SIGNED) {
    return {
      response: apiError(
        'Visit is signed and locked — coding decisions can no longer be changed.',
        409,
        { code: 'VISIT_LOCKED' },
      ),
      // ⚠️ THE MOST IMPORTANT ROW OF THE FOUR. An attempt to change coding on
      // a SIGNED record is precisely the event a coding dispute asks about, and
      // until this slice it left no trace anywhere.
      audit: refusalAudit(input, 'visit_locked'),
    };
  }

  // Earlier statuses mean L7a has not settled, so `icdCodes` is still moving
  // under any decision made against it. Same reasoning the override route uses
  // for its own READY gate.
  if (visit.status !== TranscribeVisitStatus.READY) {
    return {
      response: apiError(
        `Visit is in status ${visit.status}; a coding decision requires a READY visit.`,
        409,
        { code: 'VISIT_NOT_READY' },
      ),
      audit: refusalAudit(input, 'visit_not_ready'),
    };
  }

  const at = new Date().toISOString();
  const result = applyIcdDecision(
    { rawIcdCodes: visit.icdCodes, rawIcdDecisions: visit.icdDecisions },
    {
      code: input.code,
      decision: input.decision,
      userId: input.userId,
      at,
      reason: input.reason,
    },
  );

  if (!result.ok) {
    // ⚠️ ONE ARM PER REFUSAL, AND THE STATUS CODES DIFFER ON PURPOSE.
    // `code_not_suggested` is a CONFLICT with this visit's state — the code is
    // well formed and simply not on this note (409). The two reason refusals
    // are malformed REQUESTS: the caller sent a payload that is invalid for the
    // intent it declared, which no amount of retrying against a different visit
    // would fix (400). Collapsing them into one status would tell a client to
    // retry a request that can never succeed.
    if (result.reason === 'reason_required') {
      return {
        response: apiError('A rejection requires a reason.', 400, {
          code: 'ICD_REASON_REQUIRED',
        }),
        audit: refusalAudit(input, 'reason_required'),
      };
    }
    if (result.reason === 'reason_not_allowed') {
      return {
        response: apiError('A reason may only accompany a rejection.', 400, {
          code: 'ICD_REASON_NOT_ALLOWED',
        }),
        audit: refusalAudit(input, 'reason_not_allowed'),
      };
    }
    // ⚠️ THE ONLY WAY A CODE ENTERS THE RECORD IS BY HAVING BEEN SUGGESTED.
    // The suggester's output carries a mandatory `evidence_quote` and has
    // already passed `isValidIcd10`. A code arriving from anywhere else has
    // neither, so admitting it would be a door into a billable record that
    // bypasses both of F8's satisfied constraints at once. The contract's
    // search-add typeahead is a later slice and needs its own allowlist check
    // on the way in — it does not come free with this refusal.
    return {
      response: apiError('That code is not among this visit’s suggested codes.', 409, {
        code: 'ICD_CODE_NOT_SUGGESTED',
      }),
      audit: refusalAudit(input, 'code_not_suggested'),
    };
  }

  if (result.changed) {
    await scopedUpdate(tx.transcribeVisit, 'transcribeVisit', input.visitId, scope, {
      icdDecisions: result.decisions as unknown as Prisma.InputJsonValue,
    });
  }

  // Projected from what was just computed rather than re-read, so the answer
  // the caller renders is the state this request produced.
  const projection = projectIcdDecisions(visit.icdCodes, result.decisions);

  return {
    response: NextResponse.json(
      {
        ok: true,
        changed: result.changed,
        projection,
        summary: icdDecisionSummary(projection),
      },
      { status: 200 },
    ),
    audit: result.changed
      ? {
          action: AUDIT_ACTION[input.decision],
          targetType: 'transcribe_visit',
          targetId: input.visitId,
          metadata: {
            // THE CODE ONLY. `07a-icd-coding.ts:471-473` records that the
            // AI-emitted description can include patient context and excludes
            // it from its own audit row; the same exclusion applies here.
            code: input.code.trim().toUpperCase(),
            fromState: result.from,
            toState: result.to,
            // ⚠️ A TOKEN FROM A CLOSED SET, WHICH IS THE ONLY REASON IT MAY BE
            // HERE. `#148(d)` excludes the AI-emitted DESCRIPTION from this row
            // because free-form prose can carry patient context; ruling #154
            // makes the rejection reason an enum precisely so it cannot. Spread
            // conditionally so an accept's metadata is byte-identical to what
            // S1 wrote — an absent key, not `reason: null`.
            ...(result.to === 'rejected' ? { reason: input.reason } : {}),
          },
        }
      : null,
  };
}
