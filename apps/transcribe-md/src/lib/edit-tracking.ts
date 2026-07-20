// ============================================================================
// Sign-time edit-pattern capture (T-M14.1)
// ----------------------------------------------------------------------------
// Called fire-and-forget from both sign entry points (action + HTTP
// route) right after the READY→SIGNED transition succeeds. Records one
// doctor_edit_patterns row carrying:
//   - originalSoap   = visit.soapL6Original (the AI's final output)
//   - editedSoap     = visit.signedSoap     (what the doctor signed)
//   - editDistance   = char-level Levenshtein of the two
//   - embedding      = OpenAI text-embedding-3-small of originalSoap
//
// Contract
//   - This function MUST NOT throw. Callers discard the promise with
//     `void captureEditPattern(...)` — so any exception would become an
//     unhandled rejection that crashes the sign response path. Every
//     code path inside is wrapped in try/catch.
//   - Legacy visits (soapL6Original == null) are skipped with an info
//     log, not an error. T-M13 resume logic may also produce visits
//     that reached READY without ever running T-M14.1's L6 write — same
//     treatment.
//   - The embedding is written via raw SQL after the row insert because
//     Prisma's Unsupported("vector(1536)") field type is read-only
//     through the generated client. An embed-call failure leaves the
//     row in place with NULL embedding; a batch backfill job can
//     populate it later.
// ============================================================================

import prisma from "@meddoc/db";
import { embedText, redactPhi } from "@meddoc/ai";
import type { Prisma } from "@prisma/client";

import { charLevenshtein } from "./edit-distance";
import { log } from "./log";
import { currentClinicalVisitActorWhere } from "./clinical-visit-authority";
import { lockAndAssertOrdinaryClinicalMutation } from "./template-twin/visit-mutation-authority";

const LOG = "[edit-tracking]";

export async function captureEditPattern(args: {
  visitId: string;
  doctorId: string;
}): Promise<void> {
  try {
    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: args.visitId,
        ...currentClinicalVisitActorWhere(args.doctorId),
      },
      select: {
        soapL6Original: true,
        signedSoap: true,
        userId: true,
        patientId: true,
        noteTemplateId: true,
        updatedAt: true,
        user: { select: { practiceId: true } },
      },
    });

    if (!visit) {
      console.warn(`${LOG} visit=${args.visitId} disappeared before capture`);
      return;
    }
    if (!visit.soapL6Original) {
      // Pre-T-M14.1 visits, or retried-without-L6 resumes, have no
      // original snapshot. Nothing meaningful to capture.
      console.info(
        `${LOG} visit=${args.visitId} skip: no soapL6Original (legacy visit)`,
      );
      return;
    }
    if (!visit.signedSoap) {
      // Sign path just wrote signedSoap in the same transaction. If
      // it's null here, something skipped the updateMany. Surface but
      // don't throw.
      console.warn(
        `${LOG} visit=${args.visitId} skip: no signedSoap (unexpected post-sign state)`,
      );
      return;
    }

    const original = visit.soapL6Original;
    const edited = visit.signedSoap;
    const editDistance = charLevenshtein(original, edited);
    const ordinaryFence = (tx: Prisma.TransactionClient) =>
      lockAndAssertOrdinaryClinicalMutation({
        tx,
        visitId: args.visitId,
        actorUserId: args.doctorId,
        admittedVisitUpdatedAt: visit.updatedAt,
        admittedPatientId: visit.patientId,
        admittedNoteTemplateId: visit.noteTemplateId,
      });

    // Step 1: insert the row WITHOUT the embedding. Prisma generates
    // the cuid id for us. The @unique constraint on visitId prevents
    // a double-capture if this function ever fires twice for the same
    // visit — the duplicate create() throws, our outer catch logs it.
    const row = await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        await ordinaryFence(tx);
        return tx.doctorEditPattern.create({
          data: {
            visitId: args.visitId,
            doctorId: args.doctorId,
            originalSoap: original,
            editedSoap: edited,
            editDistance,
          },
          select: { id: true },
        });
      },
    );

    // Step 2: best-effort embed + vector write. Row persists with NULL
    // embedding if this block fails.
    let embedded = false;
    try {
      // A visit can acquire durable Twin provenance after the signed ordinary
      // snapshot was read. Fence immediately before egress; a transition here
      // leaves the internal row unembedded and sends no note text externally.
      await prisma.$transaction(ordinaryFence);
      const { embedding } = await embedText({
        text: original,
        practiceId: visit.user.practiceId,
        userId: args.doctorId,
        visitId: args.visitId,
        purpose: "tm_embed",
      });
      // pgvector accepts text literals of form '[n1,n2,...]' with a
      // ::vector cast. Parameterized through $executeRaw so the
      // embedding float list is safely escaped.
      const literal = "[" + embedding.join(",") + "]";
      await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
        // Discard a returned embedding if provenance changed during the
        // provider call. The exact signed snapshot and vector write share the
        // same transaction, so no stale ordinary result can commit to a Twin.
        await ordinaryFence(tx);
        await tx.$executeRaw`
          UPDATE doctor_edit_patterns
          SET embedding = ${literal}::vector
          WHERE id = ${row.id}
        `;
      });
      embedded = true;
    } catch (embedErr) {
      console.error(
        `${LOG} visit=${args.visitId} embed+write failed (row kept, embedding NULL):`,
        embedErr,
      );
    }

    log.info("edit-tracking", "edit pattern captured", {
      visitId: args.visitId,
      doctorId: args.doctorId,
      editDistance,
      embedded,
    });
  } catch (err) {
    // Catchall: unique violation, DB outage, any other surprise. Must
    // never propagate — sign must always succeed from the user's POV.
    // T-M18.3 A17: wrap err through redactPhi since originalSoap is in
    // scope and a Prisma error could in theory echo a column value.
    console.error(
      `${LOG} visit=${args.visitId} capture failed:`,
      redactPhi(err instanceof Error ? err.message : err),
    );
  }
}
