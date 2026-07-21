// ============================================================================
// PostgreSQL connection-string startup options
// ----------------------------------------------------------------------------
// node-postgres reduces repeated query-string keys to one value. Therefore a
// second `options` key can silently replace an earlier security setting. Keep
// the reviewed search path and statement timeout in one canonical value, and
// reject every ambiguous or unreviewed alternative before it reaches the
// driver.
// ============================================================================

export const DATABASE_SEARCH_PATH = "pg_catalog,public";
export const DEFAULT_STATEMENT_TIMEOUT_MS = 30_000;

export interface DatabaseConnectionStartupContract {
  /** Optional operator-only lock bound. Ordinary application clients omit it. */
  lockTimeoutMs?: number;
  /** Fixed, non-secret observability label sent as a PostgreSQL startup GUC. */
  applicationName?: string;
  /** Used by read-only operator modes so the server, not convention, enforces it. */
  defaultTransactionReadOnly?: boolean;
}

const MAX_POSTGRES_INTEGER_GUC_MS = 2_147_483_647;
const SEARCH_PATH_OPTION = `-c search_path=${DATABASE_SEARCH_PATH}`;
const DIRECT_CONNECTION_IDENTITY_KEYS = new Set([
  "database",
  "dbname",
  "host",
  "password",
  "port",
  "service",
  "servicefile",
  "user",
]);
const DIRECT_STARTUP_GUC_KEYS = new Set([
  "application_name",
  "client_encoding",
  "default_transaction_read_only",
  "fallback_application_name",
  "idle_in_transaction_session_timeout",
  "lock_timeout",
  "query_timeout",
  "replication",
  "search_path",
  "statement_timeout",
]);

function invalid(reason: string): never {
  throw new Error(`DATABASE_CONNECTION_OPTIONS_INVALID:${reason}`);
}

function decodeQueryComponent(value: string): string {
  try {
    return decodeURIComponent(value.replace(/\+/g, " "));
  } catch {
    return invalid("MALFORMED_QUERY_ENCODING");
  }
}

export function parseStatementTimeoutMs(
  value: string | number | undefined,
): number {
  const candidate = value ?? DEFAULT_STATEMENT_TIMEOUT_MS;

  if (
    (typeof candidate === "string" && !/^[1-9][0-9]*$/.test(candidate)) ||
    (typeof candidate !== "string" && typeof candidate !== "number")
  ) {
    return invalid("STATEMENT_TIMEOUT_NOT_POSITIVE_INTEGER");
  }

  const milliseconds = Number(candidate);
  if (
    !Number.isSafeInteger(milliseconds) ||
    milliseconds < 1 ||
    milliseconds > MAX_POSTGRES_INTEGER_GUC_MS
  ) {
    return invalid("STATEMENT_TIMEOUT_OUT_OF_RANGE");
  }

  return milliseconds;
}

function existingOptionsValues(url: URL): string[] {
  const values: string[] = [];
  const seenKeys = new Set<string>();
  const query = url.search.slice(1);
  if (!query) return values;

  for (const entry of query.split("&")) {
    if (!entry) return invalid("EMPTY_QUERY_ENTRY");
    const separator = entry.indexOf("=");
    const rawKey = separator === -1 ? entry : entry.slice(0, separator);
    const rawValue = separator === -1 ? "" : entry.slice(separator + 1);
    const key = decodeQueryComponent(rawKey);
    if (!key) return invalid("EMPTY_QUERY_KEY");
    const lowerKey = key.toLowerCase();

    // pg-connection-string collapses repeated query keys with last-value-wins
    // semantics. Reject repetitions before WHATWG URLSearchParams or the
    // driver can normalize an ambiguous target into an apparently safe one.
    if (seenKeys.has(key)) {
      return invalid(
        lowerKey === "options" ? "DUPLICATE_OPTIONS" : "DUPLICATE_QUERY_KEY",
      );
    }
    seenKeys.add(key);

    // The driver recognizes the exact lower-case keys below. Case variants
    // are rejected, while percent-encoded spellings are decoded and counted
    // so they cannot disguise a duplicate configuration channel.
    if (lowerKey === "options") {
      if (key !== "options") return invalid("AMBIGUOUS_OPTIONS_KEY");
      values.push(decodeQueryComponent(rawValue));
      continue;
    }

    if (DIRECT_CONNECTION_IDENTITY_KEYS.has(lowerKey)) {
      return invalid(
        key === lowerKey
          ? "IDENTITY_OUTSIDE_URL_AUTHORITY"
          : "AMBIGUOUS_IDENTITY_KEY",
      );
    }

    if (DIRECT_STARTUP_GUC_KEYS.has(lowerKey)) {
      return invalid("SETTING_OUTSIDE_CANONICAL_OPTIONS");
    }

    // Reject malformed encoding throughout the query. Otherwise the WHATWG
    // URL parser and the driver's compatibility normalization can disagree
    // about where a parameter ends.
    decodeQueryComponent(rawValue);
  }

  return values;
}

export function buildDatabaseConnectionString(
  raw: string,
  statementTimeout: string | number | undefined = undefined,
  startup: DatabaseConnectionStartupContract = {},
): string {
  if (!raw || raw !== raw.trim()) return invalid("DATABASE_URL_NOT_CANONICAL");

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return invalid("DATABASE_URL_UNPARSEABLE");
  }

  if (url.protocol !== "postgresql:" && url.protocol !== "postgres:") {
    return invalid("DATABASE_URL_PROTOCOL");
  }
  if (url.hash) return invalid("DATABASE_URL_FRAGMENT");

  const timeoutMs = parseStatementTimeoutMs(statementTimeout);
  const canonicalParts = [
    SEARCH_PATH_OPTION,
    `-c statement_timeout=${timeoutMs}`,
  ];
  if (startup.lockTimeoutMs !== undefined) {
    canonicalParts.push(
      `-c lock_timeout=${parseStatementTimeoutMs(startup.lockTimeoutMs)}`,
    );
  }
  if (startup.applicationName !== undefined) {
    if (!/^[a-z][a-z0-9_]{0,62}$/u.test(startup.applicationName)) {
      return invalid("APPLICATION_NAME_NOT_CANONICAL");
    }
    canonicalParts.push(`-c application_name=${startup.applicationName}`);
  }
  if (startup.defaultTransactionReadOnly !== undefined) {
    canonicalParts.push(
      `-c default_transaction_read_only=${startup.defaultTransactionReadOnly ? "on" : "off"}`,
    );
  }
  const canonicalOptions = canonicalParts.join(" ");
  const existingOptions = existingOptionsValues(url);

  if (existingOptions.length > 1) return invalid("DUPLICATE_OPTIONS");
  if (
    existingOptions.length === 1 &&
    existingOptions[0] !== SEARCH_PATH_OPTION &&
    existingOptions[0] !== canonicalOptions
  ) {
    return invalid("UNREVIEWED_OPTIONS");
  }

  // `set` produces exactly one effective key. Duplicate keys have already
  // failed closed, so this never normalizes an ambiguous input into a pass.
  url.searchParams.set("options", canonicalOptions);
  return url.toString();
}
