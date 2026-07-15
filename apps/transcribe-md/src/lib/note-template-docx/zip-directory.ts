import { inflateRawSync } from "node:zlib";

import { crc32 } from "./crc32";
import { failTemplateDocx, TemplateDocxError } from "./errors";
import { resolveTemplateDocxLimits, type TemplateDocxLimits } from "./limits";

const LOCAL_FILE_HEADER = 0x04034b50;
const CENTRAL_DIRECTORY_HEADER = 0x02014b50;
const END_OF_CENTRAL_DIRECTORY = 0x06054b50;
const ZIP64_END_OF_CENTRAL_DIRECTORY = 0x06064b50;
const ZIP64_END_OF_CENTRAL_DIRECTORY_LOCATOR = 0x07064b50;
const MAX_EOCD_SEARCH_BYTES = 65_557;

export interface VerifiedZipEntry {
  readonly name: string;
  readonly bytes: Buffer;
  readonly compressedSize: number;
  readonly uncompressedSize: number;
  readonly compressionMethod: 0 | 8;
  readonly crc32: number;
}

export interface VerifiedZipPackage {
  readonly source: Buffer;
  readonly entries: ReadonlyMap<string, VerifiedZipEntry>;
  readonly totalUncompressedBytes: number;
}

interface CentralDirectoryEntry {
  name: string;
  rawName: Buffer;
  flags: number;
  compressionMethod: 0 | 8;
  expectedCrc32: number;
  compressedSize: number;
  uncompressedSize: number;
  localHeaderOffset: number;
  isDirectory: boolean;
}

export function readVerifiedZipPackage(
  source: Uint8Array,
  limitOverrides?: Partial<TemplateDocxLimits>,
): VerifiedZipPackage {
  const limits = resolveTemplateDocxLimits(limitOverrides);
  // Take an owning copy so verification cannot be invalidated by a caller
  // mutating the upload buffer while compilation is in progress.
  const bytes = Buffer.from(source);

  if (bytes.length === 0) failTemplateDocx("DOCX_EMPTY");
  if (bytes.length > limits.maxSourceBytes) failTemplateDocx("DOCX_TOO_LARGE");
  if (bytes.length < 4 || bytes.readUInt32LE(0) !== LOCAL_FILE_HEADER) {
    failTemplateDocx("ZIP_MAGIC_INVALID");
  }

  const eocdOffset = findEndOfCentralDirectory(bytes);
  if (eocdOffset < 0) failTemplateDocx("ZIP_EOCD_MISSING");
  if (
    hasSignatureImmediatelyBefore(
      bytes,
      eocdOffset,
      ZIP64_END_OF_CENTRAL_DIRECTORY_LOCATOR,
    ) ||
    findSignature(
      bytes,
      ZIP64_END_OF_CENTRAL_DIRECTORY,
      Math.max(0, eocdOffset - 96),
      eocdOffset,
    ) >= 0
  ) {
    failTemplateDocx("ZIP64_UNSUPPORTED");
  }

  ensureReadable(bytes, eocdOffset, 22, "ZIP_DIRECTORY_INVALID");
  const diskNumber = bytes.readUInt16LE(eocdOffset + 4);
  const directoryDisk = bytes.readUInt16LE(eocdOffset + 6);
  const entriesOnDisk = bytes.readUInt16LE(eocdOffset + 8);
  const totalEntries = bytes.readUInt16LE(eocdOffset + 10);
  const directorySize = bytes.readUInt32LE(eocdOffset + 12);
  const directoryOffset = bytes.readUInt32LE(eocdOffset + 16);
  const commentLength = bytes.readUInt16LE(eocdOffset + 20);

  if (
    diskNumber !== 0 ||
    directoryDisk !== 0 ||
    entriesOnDisk !== totalEntries
  ) {
    failTemplateDocx("ZIP_MULTI_DISK_UNSUPPORTED");
  }
  if (
    totalEntries === 0xffff ||
    directorySize === 0xffffffff ||
    directoryOffset === 0xffffffff
  ) {
    failTemplateDocx("ZIP64_UNSUPPORTED");
  }
  if (totalEntries === 0 || totalEntries > limits.maxEntries) {
    failTemplateDocx("ZIP_TOO_MANY_ENTRIES");
  }
  if (eocdOffset + 22 + commentLength !== bytes.length) {
    failTemplateDocx("ZIP_DIRECTORY_INVALID");
  }
  if (
    directoryOffset > eocdOffset ||
    directorySize > eocdOffset ||
    directoryOffset + directorySize !== eocdOffset
  ) {
    failTemplateDocx("ZIP_DIRECTORY_INVALID");
  }

  const centralEntries = readCentralDirectory(
    bytes,
    directoryOffset,
    directorySize,
    totalEntries,
    limits,
  );
  const entries = new Map<string, VerifiedZipEntry>();
  const occupiedLocalRanges: Array<{ start: number; end: number }> = [];
  let totalUncompressedBytes = 0;

  for (const central of centralEntries) {
    if (
      central.isDirectory &&
      (central.compressedSize !== 0 ||
        central.uncompressedSize !== 0 ||
        central.expectedCrc32 !== 0)
    ) {
      failTemplateDocx("ZIP_DIRECTORY_INVALID");
    }
    if (central.uncompressedSize > limits.maxEntryUncompressedBytes) {
      failTemplateDocx("ZIP_ENTRY_TOO_LARGE");
    }
    if (
      central.compressedSize === 0
        ? central.uncompressedSize > 0
        : central.uncompressedSize / central.compressedSize >
          limits.maxCompressionRatio
    ) {
      failTemplateDocx("ZIP_COMPRESSION_RATIO_EXCEEDED");
    }
    if (
      totalUncompressedBytes + central.uncompressedSize >
      limits.maxTotalUncompressedBytes
    ) {
      failTemplateDocx("ZIP_TOTAL_TOO_LARGE");
    }

    const local = readCompressedEntry(bytes, central, directoryOffset);
    if (
      occupiedLocalRanges.some(
        (range) => local.rangeStart < range.end && local.rangeEnd > range.start,
      )
    ) {
      failTemplateDocx("ZIP_LOCAL_HEADER_INVALID");
    }
    occupiedLocalRanges.push({ start: local.rangeStart, end: local.rangeEnd });

    if (central.isDirectory) continue;
    const remaining = limits.maxTotalUncompressedBytes - totalUncompressedBytes;
    const maxOutputLength = Math.min(
      limits.maxEntryUncompressedBytes,
      remaining,
    );
    let uncompressed: Buffer;
    try {
      uncompressed =
        central.compressionMethod === 0
          ? Buffer.from(local.compressed)
          : inflateRawSync(local.compressed, { maxOutputLength });
    } catch (cause) {
      const errorCode =
        cause instanceof Error &&
        (cause.message.includes("maxOutputLength") ||
          (cause as NodeJS.ErrnoException).code === "ERR_BUFFER_TOO_LARGE")
          ? "ZIP_ENTRY_TOO_LARGE"
          : "ZIP_SIZE_MISMATCH";
      throw new TemplateDocxError(errorCode, { cause });
    }

    if (uncompressed.length !== central.uncompressedSize) {
      failTemplateDocx("ZIP_SIZE_MISMATCH");
    }
    if (crc32(uncompressed) !== central.expectedCrc32) {
      failTemplateDocx("ZIP_CRC_MISMATCH");
    }

    totalUncompressedBytes += uncompressed.length;
    if (totalUncompressedBytes > limits.maxTotalUncompressedBytes) {
      failTemplateDocx("ZIP_TOTAL_TOO_LARGE");
    }
    entries.set(central.name, {
      name: central.name,
      bytes: uncompressed,
      compressedSize: central.compressedSize,
      uncompressedSize: uncompressed.length,
      compressionMethod: central.compressionMethod,
      crc32: central.expectedCrc32,
    });
  }

  return { source: bytes, entries, totalUncompressedBytes };
}

function findEndOfCentralDirectory(bytes: Buffer): number {
  const start = Math.max(0, bytes.length - MAX_EOCD_SEARCH_BYTES);
  for (let offset = bytes.length - 22; offset >= start; offset -= 1) {
    if (bytes.readUInt32LE(offset) === END_OF_CENTRAL_DIRECTORY) return offset;
  }
  return -1;
}

function readCentralDirectory(
  bytes: Buffer,
  directoryOffset: number,
  directorySize: number,
  totalEntries: number,
  limits: TemplateDocxLimits,
): CentralDirectoryEntry[] {
  const entries: CentralDirectoryEntry[] = [];
  const names = new Set<string>();
  const foldedNames = new Set<string>();
  const directoryEnd = directoryOffset + directorySize;
  let offset = directoryOffset;

  for (let index = 0; index < totalEntries; index += 1) {
    ensureReadable(bytes, offset, 46, "ZIP_DIRECTORY_INVALID");
    if (bytes.readUInt32LE(offset) !== CENTRAL_DIRECTORY_HEADER) {
      failTemplateDocx("ZIP_DIRECTORY_INVALID");
    }

    const versionMadeBy = bytes.readUInt16LE(offset + 4);
    const flags = bytes.readUInt16LE(offset + 8);
    const method = bytes.readUInt16LE(offset + 10);
    const expectedCrc32 = bytes.readUInt32LE(offset + 16);
    const compressedSize = bytes.readUInt32LE(offset + 20);
    const uncompressedSize = bytes.readUInt32LE(offset + 24);
    const nameLength = bytes.readUInt16LE(offset + 28);
    const extraLength = bytes.readUInt16LE(offset + 30);
    const commentLength = bytes.readUInt16LE(offset + 32);
    const diskStart = bytes.readUInt16LE(offset + 34);
    const externalAttributes = bytes.readUInt32LE(offset + 38);
    const localHeaderOffset = bytes.readUInt32LE(offset + 42);
    const variableLength = nameLength + extraLength + commentLength;

    ensureReadable(bytes, offset + 46, variableLength, "ZIP_DIRECTORY_INVALID");
    if (offset + 46 + variableLength > directoryEnd) {
      failTemplateDocx("ZIP_DIRECTORY_INVALID");
    }
    if (diskStart !== 0) failTemplateDocx("ZIP_MULTI_DISK_UNSUPPORTED");
    if (
      compressedSize === 0xffffffff ||
      uncompressedSize === 0xffffffff ||
      localHeaderOffset === 0xffffffff ||
      containsZip64Extra(
        bytes.subarray(
          offset + 46 + nameLength,
          offset + 46 + nameLength + extraLength,
        ),
      )
    ) {
      failTemplateDocx("ZIP64_UNSUPPORTED");
    }
    if ((flags & 0x2041) !== 0) failTemplateDocx("ZIP_ENCRYPTED_ENTRY");
    if (method !== 0 && method !== 8)
      failTemplateDocx("ZIP_METHOD_UNSUPPORTED");
    if (nameLength === 0 || nameLength > limits.maxEntryNameBytes) {
      failTemplateDocx("ZIP_PATH_UNSAFE");
    }

    const rawName = bytes.subarray(offset + 46, offset + 46 + nameLength);
    const name = decodeEntryName(rawName, (flags & 0x0800) !== 0);
    validateEntryPath(name);
    const folded = name.toLowerCase();
    if (names.has(name) || foldedNames.has(folded)) {
      failTemplateDocx("ZIP_DUPLICATE_ENTRY");
    }
    names.add(name);
    foldedNames.add(folded);

    const hostSystem = versionMadeBy >>> 8;
    const unixFileType = (externalAttributes >>> 16) & 0xf000;
    if (hostSystem === 3 && unixFileType === 0xa000) {
      failTemplateDocx("ZIP_SYMLINK_ENTRY");
    }

    entries.push({
      name,
      rawName: Buffer.from(rawName),
      flags,
      compressionMethod: method,
      expectedCrc32,
      compressedSize,
      uncompressedSize,
      localHeaderOffset,
      isDirectory: name.endsWith("/"),
    });
    offset += 46 + variableLength;
  }

  if (offset !== directoryEnd) failTemplateDocx("ZIP_DIRECTORY_INVALID");
  return entries;
}

function readCompressedEntry(
  bytes: Buffer,
  entry: CentralDirectoryEntry,
  directoryOffset: number,
): { compressed: Buffer; rangeStart: number; rangeEnd: number } {
  const offset = entry.localHeaderOffset;
  ensureReadable(bytes, offset, 30, "ZIP_LOCAL_HEADER_INVALID");
  if (bytes.readUInt32LE(offset) !== LOCAL_FILE_HEADER) {
    failTemplateDocx("ZIP_LOCAL_HEADER_INVALID");
  }

  const flags = bytes.readUInt16LE(offset + 6);
  const method = bytes.readUInt16LE(offset + 8);
  const localCrc32 = bytes.readUInt32LE(offset + 14);
  const localCompressedSize = bytes.readUInt32LE(offset + 18);
  const localUncompressedSize = bytes.readUInt32LE(offset + 22);
  const nameLength = bytes.readUInt16LE(offset + 26);
  const extraLength = bytes.readUInt16LE(offset + 28);
  const dataOffset = offset + 30 + nameLength + extraLength;
  ensureReadable(
    bytes,
    offset + 30,
    nameLength + extraLength,
    "ZIP_LOCAL_HEADER_INVALID",
  );
  ensureReadable(
    bytes,
    dataOffset,
    entry.compressedSize,
    "ZIP_LOCAL_HEADER_INVALID",
  );

  const rawLocalName = bytes.subarray(offset + 30, offset + 30 + nameLength);
  const localName = decodeEntryName(rawLocalName, (flags & 0x0800) !== 0);
  const localExtra = bytes.subarray(
    offset + 30 + nameLength,
    offset + 30 + nameLength + extraLength,
  );
  if (
    localName !== entry.name ||
    rawLocalName.compare(entry.rawName) !== 0 ||
    flags !== entry.flags ||
    method !== entry.compressionMethod
  ) {
    failTemplateDocx("ZIP_LOCAL_HEADER_INVALID");
  }
  if (containsZip64Extra(localExtra)) failTemplateDocx("ZIP64_UNSUPPORTED");

  let rangeEnd = dataOffset + entry.compressedSize;
  if ((flags & 0x0008) === 0) {
    if (localCrc32 !== entry.expectedCrc32)
      failTemplateDocx("ZIP_CRC_MISMATCH");
    if (
      localCompressedSize !== entry.compressedSize ||
      localUncompressedSize !== entry.uncompressedSize
    ) {
      failTemplateDocx("ZIP_SIZE_MISMATCH");
    }
  } else {
    rangeEnd = verifyDataDescriptor(bytes, rangeEnd, entry, directoryOffset);
  }
  if (rangeEnd > directoryOffset) failTemplateDocx("ZIP_LOCAL_HEADER_INVALID");

  return {
    compressed: bytes.subarray(dataOffset, dataOffset + entry.compressedSize),
    rangeStart: offset,
    rangeEnd,
  };
}

function verifyDataDescriptor(
  bytes: Buffer,
  offset: number,
  entry: CentralDirectoryEntry,
  directoryOffset: number,
): number {
  ensureReadable(bytes, offset, 12, "ZIP_LOCAL_HEADER_INVALID");
  const hasSignature = bytes.readUInt32LE(offset) === 0x08074b50;
  const valuesOffset = offset + (hasSignature ? 4 : 0);
  ensureReadable(bytes, valuesOffset, 12, "ZIP_LOCAL_HEADER_INVALID");
  if (valuesOffset + 12 > directoryOffset)
    failTemplateDocx("ZIP_LOCAL_HEADER_INVALID");
  if (bytes.readUInt32LE(valuesOffset) !== entry.expectedCrc32) {
    failTemplateDocx("ZIP_CRC_MISMATCH");
  }
  if (
    bytes.readUInt32LE(valuesOffset + 4) !== entry.compressedSize ||
    bytes.readUInt32LE(valuesOffset + 8) !== entry.uncompressedSize
  ) {
    failTemplateDocx("ZIP_SIZE_MISMATCH");
  }
  return valuesOffset + 12;
}

function validateEntryPath(name: string): void {
  if (
    name.includes("\0") ||
    name.includes("\\") ||
    name.startsWith("/") ||
    name.startsWith("//") ||
    /^[a-zA-Z]:/.test(name) ||
    /[?#:]/.test(name) ||
    !/^[\x21-\x7e]+$/.test(name) ||
    /%(?:2e|2f|5c)/i.test(name)
  ) {
    failTemplateDocx("ZIP_PATH_UNSAFE");
  }

  const path = name.endsWith("/") ? name.slice(0, -1) : name;
  if (path.length === 0) failTemplateDocx("ZIP_PATH_UNSAFE");
  const segments = path.split("/");
  if (
    segments.some(
      (segment) => segment === "" || segment === "." || segment === "..",
    )
  ) {
    failTemplateDocx("ZIP_PATH_UNSAFE");
  }
}

function decodeEntryName(rawName: Buffer, utf8: boolean): string {
  // OOXML part names are ASCII/UTF-8. Reject undecodable or legacy-code-page
  // ambiguity instead of allowing two byte sequences to address one part.
  const name = rawName.toString(utf8 ? "utf8" : "latin1");
  if (utf8 && Buffer.from(name, "utf8").compare(rawName) !== 0) {
    failTemplateDocx("ZIP_PATH_UNSAFE");
  }
  if (!utf8 && rawName.some((byte) => byte > 0x7f)) {
    failTemplateDocx("ZIP_PATH_UNSAFE");
  }
  return name;
}

function containsZip64Extra(extra: Buffer): boolean {
  let offset = 0;
  while (offset + 4 <= extra.length) {
    const headerId = extra.readUInt16LE(offset);
    const size = extra.readUInt16LE(offset + 2);
    if (offset + 4 + size > extra.length)
      failTemplateDocx("ZIP_DIRECTORY_INVALID");
    if (headerId === 0x0001) return true;
    offset += 4 + size;
  }
  if (offset !== extra.length) failTemplateDocx("ZIP_DIRECTORY_INVALID");
  return false;
}

function ensureReadable(
  bytes: Buffer,
  offset: number,
  length: number,
  code: "ZIP_DIRECTORY_INVALID" | "ZIP_LOCAL_HEADER_INVALID",
): void {
  if (
    !Number.isSafeInteger(offset) ||
    !Number.isSafeInteger(length) ||
    offset < 0 ||
    length < 0 ||
    offset > bytes.length ||
    length > bytes.length - offset
  ) {
    failTemplateDocx(code);
  }
}

function hasSignatureImmediatelyBefore(
  bytes: Buffer,
  offset: number,
  signature: number,
): boolean {
  return offset >= 20 && bytes.readUInt32LE(offset - 20) === signature;
}

function findSignature(
  bytes: Buffer,
  signature: number,
  start: number,
  end: number,
): number {
  for (let offset = start; offset + 4 <= end; offset += 1) {
    if (bytes.readUInt32LE(offset) === signature) return offset;
  }
  return -1;
}
