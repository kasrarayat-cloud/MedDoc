import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";

const QUARANTINE_STALE_CODE =
  "TEMPLATE_TWIN_QUARANTINE_PROCESSING_TIMEOUT" as const;
const MALWARE_CLEAN_STALE_CODE =
  "TEMPLATE_TWIN_POST_SCAN_ADMISSION_TIMEOUT" as const;

interface StaleQuarantineRow {
  id: string;
  practiceId: string;
  sha256: string;
  intakeMode: string;
  status: "QUARANTINED" | "MALWARE_CLEAN";
  createdAt: Date;
}

interface QuarantineReconciliationTransaction {
  templateTwinQuarantineArtifact: {
    updateMany(args: Record<string, unknown>): Promise<{ count: number }>;
  };
  templateTwinAuditOutbox: {
    create(args: { data: Record<string, unknown> }): Promise<unknown>;
  };
}

export interface TemplateTwinQuarantineReconciliationClient {
  templateTwinQuarantineArtifact: {
    findMany(args: Record<string, unknown>): Promise<StaleQuarantineRow[]>;
  };
  $transaction<T>(
    callback: (tx: QuarantineReconciliationTransaction) => Promise<T>,
  ): Promise<T>;
}

export interface TemplateTwinQuarantineReconciliationResult {
  quarantinedRejected: number;
  malwareCleanRejected: number;
  contended: number;
}

function staleCode(status: StaleQuarantineRow["status"]): string {
  return status === "MALWARE_CLEAN"
    ? MALWARE_CLEAN_STALE_CODE
    : QUARANTINE_STALE_CODE;
}

/**
 * Terminally rejects intake attempts that stopped before admission. The raw
 * object and its claimed object-ledger row are deliberately retained; this
 * recovery path changes only the fail-closed relational state and enqueues a
 * PHI-free audit event. Object retention/deletion remains governed by the
 * separately approved ledger policy.
 */
export async function reconcileStaleTemplateTwinQuarantines(input: {
  prisma: TemplateTwinQuarantineReconciliationClient;
  now?: Date;
  staleAfterMs: number;
  limit?: number;
}): Promise<TemplateTwinQuarantineReconciliationResult> {
  const now = input.now ?? new Date();
  const limit = Math.max(1, Math.min(input.limit ?? 100, 500));
  if (!Number.isSafeInteger(input.staleAfterMs) || input.staleAfterMs < 1) {
    throw new Error("Template Twin quarantine stale interval is invalid.");
  }
  const cutoff = new Date(now.getTime() - input.staleAfterMs);
  const rows = await input.prisma.templateTwinQuarantineArtifact.findMany({
    where: {
      status: { in: ["QUARANTINED", "MALWARE_CLEAN"] },
      admittedAt: null,
      createdAt: { lte: cutoff },
    },
    select: {
      id: true,
      practiceId: true,
      sha256: true,
      intakeMode: true,
      status: true,
      createdAt: true,
    },
    orderBy: [{ createdAt: "asc" }, { id: "asc" }],
    take: limit,
  });

  const result: TemplateTwinQuarantineReconciliationResult = {
    quarantinedRejected: 0,
    malwareCleanRejected: 0,
    contended: 0,
  };
  for (const row of rows) {
    const rejectionCode = staleCode(row.status);
    const changed = await input.prisma.$transaction(async (tx) => {
      const updated = await tx.templateTwinQuarantineArtifact.updateMany({
        where: {
          id: row.id,
          practiceId: row.practiceId,
          sha256: row.sha256,
          status: row.status,
          admittedAt: null,
          createdAt: { lte: cutoff },
        },
        data: {
          status: "REJECTED",
          rejectionCodes: [rejectionCode],
        },
      });
      if (updated.count !== 1) return false;

      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:stale-quarantine-rejected:${row.id}:${rejectionCode}`,
        practiceId: row.practiceId,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TemplateTwinQuarantineArtifact",
        targetId: row.id,
        metadata: {
          sourceSha256: row.sha256,
          intakeMode: row.intakeMode,
          staleState: row.status,
          reasonCode: rejectionCode,
          cutoffAt: cutoff.toISOString(),
          gateOutcome: "terminally_rejected",
          rawObjectDisposition: "retained_by_object_ledger_policy",
        },
      });
      return true;
    });

    if (!changed) {
      result.contended += 1;
    } else if (row.status === "MALWARE_CLEAN") {
      result.malwareCleanRejected += 1;
    } else {
      result.quarantinedRejected += 1;
    }
  }
  return result;
}
