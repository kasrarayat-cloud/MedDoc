export interface TemplateDocxLimits {
  maxSourceBytes: number;
  maxEntries: number;
  maxEntryNameBytes: number;
  maxEntryUncompressedBytes: number;
  maxTotalUncompressedBytes: number;
  maxCompressionRatio: number;
  maxXmlBytes: number;
  maxXmlDepth: number;
  maxXmlElements: number;
  maxXmlAttributes: number;
  maxXmlAttributeCharacters: number;
  maxXmlTextCharacters: number;
  maxStructuralPathLength: number;
  maxFields: number;
  maxTables: number;
  maxNodes: number;
}

/** Conservative defaults for physician-authored clinical templates. */
export const DEFAULT_TEMPLATE_DOCX_LIMITS: Readonly<TemplateDocxLimits> = {
  maxSourceBytes: 10 * 1024 * 1024,
  maxEntries: 512,
  maxEntryNameBytes: 240,
  maxEntryUncompressedBytes: 16 * 1024 * 1024,
  maxTotalUncompressedBytes: 64 * 1024 * 1024,
  maxCompressionRatio: 100,
  maxXmlBytes: 12 * 1024 * 1024,
  maxXmlDepth: 128,
  maxXmlElements: 250_000,
  maxXmlAttributes: 500_000,
  maxXmlAttributeCharacters: 4 * 1024 * 1024,
  maxXmlTextCharacters: 16 * 1024 * 1024,
  maxStructuralPathLength: 512,
  maxFields: 2_000,
  maxTables: 500,
  maxNodes: 10_000,
};

export function resolveTemplateDocxLimits(
  overrides?: Partial<TemplateDocxLimits>,
): TemplateDocxLimits {
  const limits = { ...DEFAULT_TEMPLATE_DOCX_LIMITS, ...overrides };
  for (const value of Object.values(limits)) {
    if (!Number.isFinite(value) || value <= 0) {
      throw new TypeError(
        "Template DOCX limits must be positive finite numbers",
      );
    }
  }
  return limits;
}
