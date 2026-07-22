/**
 * Stable, non-sensitive failure codes for the untrusted DOCX boundary.
 *
 * Messages intentionally omit entry names and XML content. Callers may persist
 * the code for audit/quarantine decisions without risking template disclosure.
 */
export type TemplateDocxErrorCode =
  | "DOCX_EMPTY"
  | "DOCX_TOO_LARGE"
  | "ZIP_MAGIC_INVALID"
  | "ZIP_EOCD_MISSING"
  | "ZIP64_UNSUPPORTED"
  | "ZIP_MULTI_DISK_UNSUPPORTED"
  | "ZIP_DIRECTORY_INVALID"
  | "ZIP_TOO_MANY_ENTRIES"
  | "ZIP_PATH_UNSAFE"
  | "ZIP_DUPLICATE_ENTRY"
  | "ZIP_ENCRYPTED_ENTRY"
  | "ZIP_SYMLINK_ENTRY"
  | "ZIP_METHOD_UNSUPPORTED"
  | "ZIP_ENTRY_TOO_LARGE"
  | "ZIP_COMPRESSION_RATIO_EXCEEDED"
  | "ZIP_TOTAL_TOO_LARGE"
  | "ZIP_LOCAL_HEADER_INVALID"
  | "ZIP_SIZE_MISMATCH"
  | "ZIP_CRC_MISMATCH"
  | "OPC_REQUIRED_PART_MISSING"
  | "OPC_CONTENT_TYPE_INVALID"
  | "OPC_RELATIONSHIP_INVALID"
  | "DOCM_REJECTED"
  | "ACTIVE_CONTENT_REJECTED"
  | "EMBEDDED_OBJECT_REJECTED"
  | "EXTERNAL_RELATIONSHIP_REJECTED"
  | "XML_DTD_REJECTED"
  | "XML_INVALID"
  | "DOCUMENT_STRUCTURE_LIMIT_EXCEEDED"
  | "IR_VALIDATION_FAILED";

const SAFE_MESSAGES: Record<TemplateDocxErrorCode, string> = {
  DOCX_EMPTY: "The DOCX package is empty.",
  DOCX_TOO_LARGE: "The DOCX package exceeds the allowed upload size.",
  ZIP_MAGIC_INVALID: "The upload is not a valid DOCX ZIP package.",
  ZIP_EOCD_MISSING: "The DOCX ZIP directory could not be located.",
  ZIP64_UNSUPPORTED: "ZIP64 DOCX packages are not supported.",
  ZIP_MULTI_DISK_UNSUPPORTED: "Multi-disk ZIP packages are not supported.",
  ZIP_DIRECTORY_INVALID: "The DOCX ZIP directory is invalid.",
  ZIP_TOO_MANY_ENTRIES: "The DOCX package contains too many entries.",
  ZIP_PATH_UNSAFE: "The DOCX package contains an unsafe entry path.",
  ZIP_DUPLICATE_ENTRY: "The DOCX package contains duplicate entry paths.",
  ZIP_ENCRYPTED_ENTRY: "Encrypted DOCX package entries are not supported.",
  ZIP_SYMLINK_ENTRY: "Symbolic links are not permitted in DOCX packages.",
  ZIP_METHOD_UNSUPPORTED:
    "The DOCX package uses an unsupported compression method.",
  ZIP_ENTRY_TOO_LARGE: "A DOCX package entry exceeds the allowed size.",
  ZIP_COMPRESSION_RATIO_EXCEEDED:
    "The DOCX package exceeds the allowed decompression ratio.",
  ZIP_TOTAL_TOO_LARGE:
    "The DOCX package expands beyond the allowed total size.",
  ZIP_LOCAL_HEADER_INVALID: "A DOCX ZIP entry header is invalid.",
  ZIP_SIZE_MISMATCH: "A DOCX ZIP entry has inconsistent size metadata.",
  ZIP_CRC_MISMATCH: "A DOCX ZIP entry failed integrity verification.",
  OPC_REQUIRED_PART_MISSING:
    "The DOCX package is missing a required OOXML part.",
  OPC_CONTENT_TYPE_INVALID:
    "The DOCX package has an invalid content type declaration.",
  OPC_RELATIONSHIP_INVALID:
    "The DOCX package contains an invalid OOXML relationship.",
  DOCM_REJECTED: "Macro-enabled Word documents are not accepted.",
  ACTIVE_CONTENT_REJECTED:
    "The DOCX package contains unsupported active content.",
  EMBEDDED_OBJECT_REJECTED: "The DOCX package contains an embedded object.",
  EXTERNAL_RELATIONSHIP_REJECTED:
    "The DOCX package contains an external or remote relationship.",
  XML_DTD_REJECTED:
    "DTD and entity declarations are not permitted in DOCX XML.",
  XML_INVALID: "An OOXML part is malformed.",
  DOCUMENT_STRUCTURE_LIMIT_EXCEEDED:
    "The DOCX document structure exceeds the supported complexity limit.",
  IR_VALIDATION_FAILED: "The compiled template structure is invalid.",
};

export class TemplateDocxError extends Error {
  readonly code: TemplateDocxErrorCode;

  constructor(code: TemplateDocxErrorCode, options?: { cause?: unknown }) {
    super(SAFE_MESSAGES[code], options);
    this.name = "TemplateDocxError";
    this.code = code;
  }
}

export function failTemplateDocx(code: TemplateDocxErrorCode): never {
  throw new TemplateDocxError(code);
}
