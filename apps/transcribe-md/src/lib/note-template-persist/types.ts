// ============================================================================
// Note-format customization — Phase 2b: client-safe shared types
// ----------------------------------------------------------------------------
// Types only (no prisma / no 'use server') so client components can import
// them without dragging server code across the boundary. read.ts (server) and
// the client manager both depend on this module.
// ============================================================================

import type {
  NoteTemplateSection,
  ParsedStyleProfile,
} from '@/lib/note-template-parse/note-template-schema';

export type TemplateStatus = 'draft' | 'active' | 'inactive';

/** The shape the review editor loads (a parse result OR an existing row). */
export interface TemplateReviewModel {
  id?: string;
  name: string;
  encounterType: string | null;
  sections: NoteTemplateSection[];
  styleProfile: ParsedStyleProfile;
}

/** A row as read for the templates list (server-side; updatedAt is a Date). */
export interface TemplateListItem {
  id: string;
  name: string;
  encounterType: string | null;
  status: TemplateStatus;
  version: number;
  sectionCount: number;
  defaultCount: number;
  updatedAt: Date;
}

/** A list row serialized for the client (Date → ISO string + display labels). */
export interface ClientTemplateListItem {
  id: string;
  name: string;
  encounterType: string | null;
  encounterLabel: string;
  status: TemplateStatus;
  version: number;
  sectionCount: number;
  defaultCount: number;
  updatedAtIso: string;
}
