import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { lstatSync, readFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import { ScureBase32Plugin } from "otplib";

export const MFA_SECRET_ACTIVE_KEY_ID_ENV = "MFA_SECRET_ACTIVE_KEY_ID" as const;
export const MFA_SECRET_KEYRING_FILE_ENV = "MFA_SECRET_KEYRING_FILE" as const;
export const MFA_SECRET_LEGACY_READ_MODE_ENV =
  "MFA_SECRET_LEGACY_READ_MODE" as const;
export const MFA_SECRET_LEGACY_READ_UNTIL_ENV =
  "MFA_SECRET_LEGACY_READ_UNTIL" as const;
export const MFA_SECRET_LEGACY_READ_ATTESTATION_ENV =
  "MFA_SECRET_LEGACY_READ_ATTESTATION" as const;

const ENVELOPE_PREFIX = "qmfa";
const ENVELOPE_VERSION = "v1";
const KEYRING_VERSION = 1;
const KEY_BYTES = 32;
const NONCE_BYTES = 12;
const AUTH_TAG_BYTES = 16;
const MAX_KEYRING_BYTES = 16 * 1024;
const MAX_KEYRING_KEYS = 16;
const MAX_ENVELOPE_BYTES = 2 * 1024;
const MIN_TOTP_SECRET_BYTES = 16;
const MAX_TOTP_SECRET_BYTES = 64;
const TRANSCRIBE_MD_RUNTIME_GID = 1001;
const KEY_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/u;
const BASE32_SECRET_PATTERN = /^[A-Z2-7]{1,128}$/u;
const BASE32_CODEC = new ScureBase32Plugin();
const STRICT_LEGACY_READ_MODE = "strict";
const BACKFILL_LEGACY_READ_MODE = "backfill-v1";
const BACKFILL_LEGACY_READ_ATTESTATION =
  "accepted-bounded-mfa-secret-backfill-v1";
const MAX_LEGACY_READ_WINDOW_MS = 24 * 60 * 60 * 1000;
const MFA_CONSUMER_ROLES = new Set([
  "physician-app",
  "template-twin-admin-app",
]);

const CONFIGURATION_ERROR_MESSAGE =
  "MFA secret encryption configuration is unavailable.";
const ENVELOPE_ERROR_MESSAGE =
  "MFA secret ciphertext could not be authenticated.";

export class MfaSecretConfigurationError extends Error {
  readonly code = "MFA_SECRET_CONFIGURATION_INVALID" as const;

  constructor() {
    super(CONFIGURATION_ERROR_MESSAGE);
    this.name = "MfaSecretConfigurationError";
  }
}

export class MfaSecretEnvelopeError extends Error {
  readonly code = "MFA_SECRET_ENVELOPE_INVALID" as const;

  constructor() {
    super(ENVELOPE_ERROR_MESSAGE);
    this.name = "MfaSecretEnvelopeError";
  }
}

export interface MfaSecretKey {
  id: string;
  key: Uint8Array;
}

export interface MfaSecretEnvelopeCodec {
  encrypt(input: { userId: string; plaintextSecret: string }): string;
  decrypt(input: { userId: string; encryptedSecret: string }): string;
}

interface KeyringFileAccess {
  lstat(path: string): {
    isFile(): boolean;
    isSymbolicLink(): boolean;
    uid: number;
    gid: number;
    mode: number;
    size: number;
  };
  read(path: string): string;
}

const NODE_FILE_ACCESS: KeyringFileAccess = {
  lstat: (path) => lstatSync(path),
  read: (path) => readFileSync(path, "utf8"),
};

function configurationFailure(): never {
  throw new MfaSecretConfigurationError();
}

function envelopeFailure(): never {
  throw new MfaSecretEnvelopeError();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return (
    actual.length === wanted.length &&
    actual.every((key, index) => key === wanted[index])
  );
}

function decodeCanonicalBase64Url(
  value: string,
  expectedBytes: number,
): Buffer {
  if (!/^[A-Za-z0-9_-]+$/u.test(value)) envelopeFailure();
  const decoded = Buffer.from(value, "base64url");
  if (
    decoded.length !== expectedBytes ||
    decoded.toString("base64url") !== value
  ) {
    envelopeFailure();
  }
  return decoded;
}

function parseKeyMaterial(value: unknown): Buffer {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/u.test(value)) {
    configurationFailure();
  }
  const decoded = Buffer.from(value, "base64url");
  if (decoded.length !== KEY_BYTES || decoded.toString("base64url") !== value) {
    configurationFailure();
  }
  return decoded;
}

function validateUserId(userId: string): void {
  if (
    typeof userId !== "string" ||
    userId.length === 0 ||
    userId.length > 256 ||
    userId.trim() !== userId ||
    /[\u0000-\u001f\u007f]/u.test(userId)
  ) {
    envelopeFailure();
  }
}

function isCanonicalPlaintextSecret(value: unknown): value is string {
  if (typeof value !== "string" || !BASE32_SECRET_PATTERN.test(value)) {
    return false;
  }
  let decoded: Uint8Array | undefined;
  try {
    decoded = BASE32_CODEC.decode(value);
    return (
      decoded.length >= MIN_TOTP_SECRET_BYTES &&
      decoded.length <= MAX_TOTP_SECRET_BYTES &&
      BASE32_CODEC.encode(decoded, { padding: false }) === value
    );
  } catch {
    return false;
  } finally {
    decoded?.fill(0);
  }
}

function validatePlaintextSecret(secret: string): void {
  if (!isCanonicalPlaintextSecret(secret)) envelopeFailure();
}

export function isLegacyPlaintextMfaSecret(value: unknown): value is string {
  return isCanonicalPlaintextSecret(value);
}

export function isMfaSecretEnvelope(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.startsWith(`${ENVELOPE_PREFIX}:${ENVELOPE_VERSION}:`)
  );
}

function assertLegacyReadMode(
  environment: Readonly<Record<string, string | undefined>>,
  now: Date,
): "strict" | "backfill-v1" {
  const rawMode = environment[MFA_SECRET_LEGACY_READ_MODE_ENV] ?? "";
  const mode = rawMode || STRICT_LEGACY_READ_MODE;
  const until = environment[MFA_SECRET_LEGACY_READ_UNTIL_ENV] ?? "";
  const attestation = environment[MFA_SECRET_LEGACY_READ_ATTESTATION_ENV] ?? "";
  if (mode === STRICT_LEGACY_READ_MODE) {
    if (until || attestation) configurationFailure();
    return "strict";
  }
  if (
    mode !== BACKFILL_LEGACY_READ_MODE ||
    rawMode.trim() !== rawMode ||
    attestation !== BACKFILL_LEGACY_READ_ATTESTATION
  ) {
    configurationFailure();
  }
  const nowMs = now.getTime();
  const untilMs = Date.parse(until);
  if (
    !Number.isFinite(nowMs) ||
    !Number.isFinite(untilMs) ||
    new Date(untilMs).toISOString() !== until ||
    untilMs <= nowMs ||
    untilMs - nowMs > MAX_LEGACY_READ_WINDOW_MS
  ) {
    configurationFailure();
  }
  return "backfill-v1";
}

export function legacyPlaintextMfaReadAllowed(
  environment: Readonly<Record<string, string | undefined>> = process.env,
  now = new Date(),
): boolean {
  try {
    return assertLegacyReadMode(environment, now) === "backfill-v1";
  } catch {
    return false;
  }
}

function aad(userId: string, keyId: string, purpose: "dek" | "secret") {
  return Buffer.from(
    `${ENVELOPE_PREFIX}:${ENVELOPE_VERSION}:${keyId}:user:${userId}:${purpose}`,
    "utf8",
  );
}

function encryptAesGcm(
  plaintext: Buffer,
  key: Buffer,
  nonce: Buffer,
  associatedData: Buffer,
): { ciphertext: Buffer; tag: Buffer } {
  const cipher = createCipheriv("aes-256-gcm", key, nonce, {
    authTagLength: AUTH_TAG_BYTES,
  });
  cipher.setAAD(associatedData, { plaintextLength: plaintext.length });
  return {
    ciphertext: Buffer.concat([cipher.update(plaintext), cipher.final()]),
    tag: cipher.getAuthTag(),
  };
}

function decryptAesGcm(
  ciphertext: Buffer,
  tag: Buffer,
  key: Buffer,
  nonce: Buffer,
  associatedData: Buffer,
): Buffer {
  const decipher = createDecipheriv("aes-256-gcm", key, nonce, {
    authTagLength: AUTH_TAG_BYTES,
  });
  decipher.setAAD(associatedData, { plaintextLength: ciphertext.length });
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

export function createMfaSecretEnvelopeCodec(input: {
  activeKeyId: string;
  keys: readonly MfaSecretKey[];
}): MfaSecretEnvelopeCodec {
  if (
    !KEY_ID_PATTERN.test(input.activeKeyId) ||
    input.keys.length === 0 ||
    input.keys.length > MAX_KEYRING_KEYS
  ) {
    configurationFailure();
  }
  const keys = new Map<string, Buffer>();
  for (const entry of input.keys) {
    if (
      !KEY_ID_PATTERN.test(entry.id) ||
      entry.key.byteLength !== KEY_BYTES ||
      keys.has(entry.id)
    ) {
      configurationFailure();
    }
    keys.set(entry.id, Buffer.from(entry.key));
  }
  if (!keys.has(input.activeKeyId)) configurationFailure();

  return {
    encrypt({ userId, plaintextSecret }) {
      validateUserId(userId);
      validatePlaintextSecret(plaintextSecret);
      const keyId = input.activeKeyId;
      const wrappingKey = keys.get(keyId);
      if (!wrappingKey) configurationFailure();

      const dataKey = randomBytes(KEY_BYTES);
      const wrapNonce = randomBytes(NONCE_BYTES);
      const secretNonce = randomBytes(NONCE_BYTES);
      const plaintext = Buffer.from(plaintextSecret, "utf8");
      try {
        const wrapped = encryptAesGcm(
          dataKey,
          wrappingKey,
          wrapNonce,
          aad(userId, keyId, "dek"),
        );
        const encrypted = encryptAesGcm(
          plaintext,
          dataKey,
          secretNonce,
          aad(userId, keyId, "secret"),
        );
        return [
          ENVELOPE_PREFIX,
          ENVELOPE_VERSION,
          keyId,
          wrapNonce.toString("base64url"),
          wrapped.ciphertext.toString("base64url"),
          wrapped.tag.toString("base64url"),
          secretNonce.toString("base64url"),
          encrypted.ciphertext.toString("base64url"),
          encrypted.tag.toString("base64url"),
        ].join(":");
      } catch {
        return envelopeFailure();
      } finally {
        dataKey.fill(0);
        plaintext.fill(0);
      }
    },

    decrypt({ userId, encryptedSecret }) {
      try {
        validateUserId(userId);
        if (
          typeof encryptedSecret !== "string" ||
          encryptedSecret.length === 0 ||
          Buffer.byteLength(encryptedSecret, "utf8") > MAX_ENVELOPE_BYTES
        ) {
          return envelopeFailure();
        }
        const parts = encryptedSecret.split(":");
        if (
          parts.length !== 9 ||
          parts[0] !== ENVELOPE_PREFIX ||
          parts[1] !== ENVELOPE_VERSION
        ) {
          return envelopeFailure();
        }
        const keyId = parts[2] ?? "";
        if (!KEY_ID_PATTERN.test(keyId)) return envelopeFailure();
        const wrappingKey = keys.get(keyId);
        if (!wrappingKey) return envelopeFailure();

        const wrapNonce = decodeCanonicalBase64Url(parts[3] ?? "", NONCE_BYTES);
        const wrappedDataKey = decodeCanonicalBase64Url(
          parts[4] ?? "",
          KEY_BYTES,
        );
        const wrapTag = decodeCanonicalBase64Url(
          parts[5] ?? "",
          AUTH_TAG_BYTES,
        );
        const secretNonce = decodeCanonicalBase64Url(
          parts[6] ?? "",
          NONCE_BYTES,
        );
        const encryptedSecretBytes = decodeCanonicalBase64Url(
          parts[7] ?? "",
          Buffer.from(parts[7] ?? "", "base64url").length,
        );
        const secretTag = decodeCanonicalBase64Url(
          parts[8] ?? "",
          AUTH_TAG_BYTES,
        );

        const dataKey = decryptAesGcm(
          wrappedDataKey,
          wrapTag,
          wrappingKey,
          wrapNonce,
          aad(userId, keyId, "dek"),
        );
        try {
          if (dataKey.length !== KEY_BYTES) return envelopeFailure();
          const plaintext = decryptAesGcm(
            encryptedSecretBytes,
            secretTag,
            dataKey,
            secretNonce,
            aad(userId, keyId, "secret"),
          );
          try {
            const secret = plaintext.toString("utf8");
            validatePlaintextSecret(secret);
            return secret;
          } finally {
            plaintext.fill(0);
          }
        } finally {
          dataKey.fill(0);
        }
      } catch {
        return envelopeFailure();
      }
    },
  };
}

function keyringFromFile(
  path: string,
  activeKeyId: string,
  productionPermissions: boolean,
  fileAccess: KeyringFileAccess,
): MfaSecretEnvelopeCodec {
  try {
    if (!isAbsolute(path) || path.trim() !== path) configurationFailure();
    const stat = fileAccess.lstat(path);
    if (
      !stat.isFile() ||
      stat.isSymbolicLink() ||
      stat.size <= 0 ||
      stat.size > MAX_KEYRING_BYTES
    ) {
      configurationFailure();
    }
    if (
      productionPermissions &&
      (stat.uid !== 0 ||
        stat.gid !== TRANSCRIBE_MD_RUNTIME_GID ||
        (stat.mode & 0o777) !== 0o440)
    ) {
      configurationFailure();
    }
    const parsed: unknown = JSON.parse(fileAccess.read(path));
    if (
      !isRecord(parsed) ||
      !hasExactKeys(parsed, ["version", "keys"]) ||
      parsed.version !== KEYRING_VERSION ||
      !Array.isArray(parsed.keys) ||
      parsed.keys.length === 0 ||
      parsed.keys.length > MAX_KEYRING_KEYS
    ) {
      configurationFailure();
    }
    const keys = parsed.keys.map((entry): MfaSecretKey => {
      if (
        !isRecord(entry) ||
        !hasExactKeys(entry, ["id", "keyBase64Url"]) ||
        typeof entry.id !== "string" ||
        !KEY_ID_PATTERN.test(entry.id)
      ) {
        return configurationFailure();
      }
      return { id: entry.id, key: parseKeyMaterial(entry.keyBase64Url) };
    });
    return createMfaSecretEnvelopeCodec({ activeKeyId, keys });
  } catch (error) {
    if (error instanceof MfaSecretConfigurationError) throw error;
    return configurationFailure();
  }
}

let cachedRuntimeCodec:
  | { signature: string; codec: MfaSecretEnvelopeCodec }
  | undefined;
let localEphemeralCodec: MfaSecretEnvelopeCodec | undefined;

function runtimeCodec(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): MfaSecretEnvelopeCodec {
  const activeKeyId = environment[MFA_SECRET_ACTIVE_KEY_ID_ENV] ?? "";
  const path = environment[MFA_SECRET_KEYRING_FILE_ENV] ?? "";
  if (activeKeyId || path) {
    if (
      !activeKeyId ||
      !path ||
      activeKeyId.trim() !== activeKeyId ||
      !KEY_ID_PATTERN.test(activeKeyId)
    ) {
      configurationFailure();
    }
    const signature = `${activeKeyId}\u0000${path}`;
    if (cachedRuntimeCodec?.signature === signature) {
      return cachedRuntimeCodec.codec;
    }
    const codec = keyringFromFile(
      path,
      activeKeyId,
      environment.NODE_ENV === "production",
      NODE_FILE_ACCESS,
    );
    cachedRuntimeCodec = { signature, codec };
    return codec;
  }
  if (environment.NODE_ENV === "production") configurationFailure();
  localEphemeralCodec ??= createMfaSecretEnvelopeCodec({
    activeKeyId: "local-ephemeral-v1",
    keys: [{ id: "local-ephemeral-v1", key: randomBytes(KEY_BYTES) }],
  });
  return localEphemeralCodec;
}

export function assertMfaSecretRuntimeConfiguration(
  environment: Readonly<Record<string, string | undefined>> = process.env,
  fileAccess: KeyringFileAccess = NODE_FILE_ACCESS,
  now = new Date(),
): void {
  if (environment.NODE_ENV !== "production") return;
  const role = environment.QUILLMD_SERVICE_ROLE?.trim() ?? "";
  const activeKeyId = environment[MFA_SECRET_ACTIVE_KEY_ID_ENV] ?? "";
  const path = environment[MFA_SECRET_KEYRING_FILE_ENV] ?? "";
  const legacyMode = environment[MFA_SECRET_LEGACY_READ_MODE_ENV] ?? "";
  const legacyUntil = environment[MFA_SECRET_LEGACY_READ_UNTIL_ENV] ?? "";
  const legacyAttestation =
    environment[MFA_SECRET_LEGACY_READ_ATTESTATION_ENV] ?? "";
  if (!MFA_CONSUMER_ROLES.has(role)) {
    if (activeKeyId || path || legacyMode || legacyUntil || legacyAttestation) {
      configurationFailure();
    }
    return;
  }
  if (
    !activeKeyId ||
    activeKeyId.trim() !== activeKeyId ||
    !KEY_ID_PATTERN.test(activeKeyId) ||
    !path
  ) {
    configurationFailure();
  }
  void keyringFromFile(path, activeKeyId, true, fileAccess);
  void assertLegacyReadMode(environment, now);
}

export function encryptMfaSecretForUser(input: {
  userId: string;
  plaintextSecret: string;
}): string {
  return runtimeCodec().encrypt(input);
}

export function decryptMfaSecretForUser(input: {
  userId: string;
  encryptedSecret: string;
}): string {
  return runtimeCodec().decrypt(input);
}
