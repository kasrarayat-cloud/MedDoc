// ============================================================================
// Note-format customization — Phase 2b: doctor-scoped template reads + mappers
// ----------------------------------------------------------------------------
// Plain module (NOT 'use server') so the settings server component can read
// directly and the pure mappers stay unit-testable. Every read here is called
// with a doctorId the caller already resolved from the session — callers MUST
// pass the session doctor's own id (a doctor never sees another's templates).
// ============================================================================

import prisma from "@meddoc/db";
import { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION } from "@meddoc/ai";
import type {
  NoteTemplateSection,
  ParsedStyleProfile,
} from "@/lib/note-template-parse/note-template-schema";
// Types live in ./types (no prisma) so client code never imports this
// prisma-backed module. Consumers import the types from there directly.
import type {
  TemplateStatus,
  TemplateReviewModel,
  TemplateListItem,
  TemplateKind,
  TemplateTwinCertificationStatus,
} from "./types";

function certificationStatus(
  value: string | null | undefined,
): TemplateTwinCertificationStatus | null {
  if (!value) return null;
  return value.toLowerCase() as TemplateTwinCertificationStatus;
}

function asSections(json: unknown): NoteTemplateSection[] {
  return Array.isArray(json) ? (json as NoteTemplateSection[]) : [];
}

function asStyleProfile(json: unknown): ParsedStyleProfile {
  const o = (json ?? {}) as Record<string, unknown>;
  return {
    tense: typeof o.tense === "string" ? o.tense : null,
    tone: typeof o.tone === "string" ? o.tone : "",
    abbreviations: typeof o.abbreviations === "string" ? o.abbreviations : null,
  };
}

/** Map a Prisma NoteTemplate row → the review-editor model (format only). */
export function rowToReviewModel(row: {
  id: string;
  name: string;
  encounterType: string | null;
  sections: unknown;
  styleProfile: unknown;
}): TemplateReviewModel {
  return {
    id: row.id,
    name: row.name,
    encounterType: row.encounterType,
    sections: asSections(row.sections),
    styleProfile: asStyleProfile(row.styleProfile),
  };
}

/** Map a row → list item (counts derived from the sections JSON). */
export function rowToListItem(row: {
  id: string;
  name: string;
  encounterType: string | null;
  status: string;
  version: number;
  sections: unknown;
  templateKind?: string;
  templateTwinCompiledVersion?: {
    certificationStatus: string;
    blockingUnsupportedCount: number;
    _count: { fields: number };
  } | null;
  updatedAt: Date;
}): TemplateListItem {
  const sections = asSections(row.sections);
  return {
    id: row.id,
    name: row.name,
    encounterType: row.encounterType,
    status: (row.status as TemplateStatus) ?? "draft",
    version: row.version,
    sectionCount: sections.length,
    defaultCount: sections.filter((s) => !!s.defaultText).length,
    templateKind:
      (row.templateKind as TemplateKind | undefined) ?? "structured",
    twinCertificationStatus: certificationStatus(
      row.templateTwinCompiledVersion?.certificationStatus,
    ),
    twinFieldCount: row.templateTwinCompiledVersion?._count.fields ?? 0,
    twinBlockingUnsupportedCount:
      row.templateTwinCompiledVersion?.blockingUnsupportedCount ?? 0,
    updatedAt: row.updatedAt,
  };
}

/** The doctor's own templates for the settings list — draft + active +
 *  superseded(inactive) history, newest first, active surfaced first. */
export async function listDoctorTemplates(
  doctorId: string,
): Promise<TemplateListItem[]> {
  const rows = await prisma.noteTemplate.findMany({
    where: { doctorId },
    select: {
      id: true,
      name: true,
      encounterType: true,
      status: true,
      version: true,
      sections: true,
      templateKind: true,
      templateTwinCompiledVersion: {
        select: {
          certificationStatus: true,
          blockingUnsupportedCount: true,
          _count: { select: { fields: true } },
        },
      },
      updatedAt: true,
    },
    orderBy: [{ updatedAt: "desc" }],
  });
  const items: TemplateListItem[] = rows.map(
    (r: {
      id: string;
      name: string;
      encounterType: string | null;
      status: string;
      version: number;
      sections: unknown;
      templateKind: string;
      templateTwinCompiledVersion: {
        certificationStatus: string;
        blockingUnsupportedCount: number;
        _count: { fields: number };
      } | null;
      updatedAt: Date;
    }) => rowToListItem(r),
  );
  // Active first, then drafts, then inactive — stable within each by recency.
  const rank: Record<TemplateStatus, number> = {
    active: 0,
    draft: 1,
    inactive: 2,
    retired: 3,
  };
  return items.sort(
    (a: TemplateListItem, b: TemplateListItem) =>
      rank[a.status] - rank[b.status],
  );
}

/**
 * Synthetic QA never receives the doctor's ordinary template collection.
 * This query is tenant- and actor-scoped to a current, durable root admission
 * whose immutable rollout generations match the database token pinned by the
 * settings server component. Generic templates therefore remain available
 * only through the ordinary note-format experience.
 */
export async function listDoctorStagingQaTemplates(input: {
  doctorId: string;
  practiceId: string;
  globalGeneration: bigint;
  practiceGeneration: bigint;
  now?: Date;
}): Promise<TemplateListItem[]> {
  const rows = await prisma.noteTemplate.findMany({
    where: {
      doctorId: input.doctorId,
      templateKind: "template_twin_docx",
      templateTwinSyntheticQaAdmissions: {
        some: {
          practiceId: input.practiceId,
          actorId: input.doctorId,
          purpose: "UPLOAD",
          providerMode: "SYNTHETIC_LIFECYCLE",
          fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
          phase: { in: ["TEMPLATE_LINKED", "CERTIFIED"] },
          pinnedGlobalRolloutGeneration: input.globalGeneration,
          pinnedPracticeRolloutGeneration: input.practiceGeneration,
          failedAt: null,
          revokedAt: null,
          expiresAt: { gt: input.now ?? new Date() },
        },
      },
    },
    select: {
      id: true,
      name: true,
      encounterType: true,
      status: true,
      version: true,
      sections: true,
      templateKind: true,
      templateTwinCompiledVersion: {
        select: {
          certificationStatus: true,
          blockingUnsupportedCount: true,
          _count: { select: { fields: true } },
        },
      },
      updatedAt: true,
    },
    orderBy: [{ updatedAt: "desc" }],
  });
  const items: TemplateListItem[] = rows.map(
    (row: Parameters<typeof rowToListItem>[0]) => rowToListItem(row),
  );
  const rank: Record<TemplateStatus, number> = {
    active: 0,
    draft: 1,
    inactive: 2,
    retired: 3,
  };
  return items.sort(
    (a: TemplateListItem, b: TemplateListItem) =>
      rank[a.status] - rank[b.status],
  );
}
