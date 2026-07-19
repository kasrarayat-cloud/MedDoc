"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  COMPLETED_CANDIDATE_REVIEW_RECEIPT,
  CompletedCandidateReviewProjectionSchema,
  type CompletedCandidateReviewDto,
  type CompletedCandidateReviewProjection,
} from "@/lib/template-twin/completed-candidate-contract";

import styles from "./completed-candidate.module.css";

const CREATE_ENDPOINT = "/api/note-templates/template-twin/completed-candidate";
const MAX_EXAMPLE_BYTES = 10 * 1024 * 1024;

type Decision = "APPROVED" | "REJECTED";

interface ApiPayload {
  ok?: boolean;
  error?: string;
  reviewUrl?: string;
  status?: "APPROVED" | "REJECTED";
  projection?: unknown;
  reviewReceipt?: string;
  expiresAtIso?: string;
}

async function readPayload(response: Response): Promise<ApiPayload> {
  try {
    return (await response.json()) as ApiPayload;
  } catch {
    return {};
  }
}

function abbreviatedHash(value: string): string {
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function decisionLabel(value: Decision | undefined): string {
  if (value === "APPROVED") return "approved";
  if (value === "REJECTED") return "rejected";
  return "needs decision";
}

type ProjectionTable = Extract<
  CompletedCandidateReviewProjection["blocks"][number],
  { kind: "table" }
>;

function projectionCellText(
  role: ProjectionTable["rows"][number]["cells"][number]["role"],
  side: "source" | "candidate",
): string {
  if (role.kind === "stable_label") return role.label;
  if (role.kind === "candidate_region") {
    return side === "source" ? "Example value withheld" : "Blank text control";
  }
  return side === "source"
    ? "Static content withheld"
    : "Static content preserved";
}

function projectionMatchesInventory(
  projection: CompletedCandidateReviewProjection,
  regions: CompletedCandidateReviewDto["regions"],
): boolean {
  const candidateTags = new Map<string, string>();
  const labels = new Map<string, string>();
  for (const block of projection.blocks) {
    if (block.kind !== "table") continue;
    for (const row of block.rows) {
      for (const cell of row.cells) {
        if (cell.role.kind === "candidate_region") {
          candidateTags.set(cell.role.regionId, cell.role.candidateTag);
        } else if (cell.role.kind === "stable_label") {
          labels.set(cell.role.forRegionId, cell.role.label);
        }
      }
    }
  }
  return (
    candidateTags.size === regions.length &&
    labels.size === regions.length &&
    regions.every(
      (region) =>
        candidateTags.get(region.regionId) === region.candidateTag &&
        labels.get(region.regionId) === region.label,
    )
  );
}

function StructuralTable({
  block,
  side,
}: {
  block: ProjectionTable;
  side: "source" | "candidate";
}) {
  return (
    <table className={styles.structuralTable}>
      <caption className={styles.visuallyHidden}>
        Table {block.tableIndex + 1},{" "}
        {side === "source" ? "isolated source" : "blank candidate"} structure
      </caption>
      <colgroup>
        {block.gridColumnBasisPoints.map((width, index) => (
          <col
            key={`${block.blockKey}:column:${index}`}
            style={{ width: `${width / 100}%` }}
          />
        ))}
      </colgroup>
      <tbody>
        {block.rows.map((row) => (
          <tr key={`${block.blockKey}:row:${row.rowIndex}`}>
            {row.cells.map((cell) => {
              const dynamic = cell.role.kind === "candidate_region";
              return (
                <td
                  key={cell.cellKey}
                  colSpan={cell.columnSpan}
                  className={dynamic ? styles.structuralDynamicCell : undefined}
                  data-structural-role={cell.role.kind}
                >
                  <span>{projectionCellText(cell.role, side)}</span>
                  {dynamic && (
                    <small>
                      {side === "source" ? "redacted" : "stable binding"}
                    </small>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CompletedCandidateUploadWorkspace() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [scope, setScope] = useState("");
  const [description, setDescription] = useState("");
  const [attested, setAttested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function chooseFiles(event: React.ChangeEvent<HTMLInputElement>) {
    setError("");
    setMessage("");
    const selected = Array.from(event.target.files ?? []);
    if (selected.length < 2 || selected.length > 3) {
      event.target.value = "";
      setFiles([]);
      setError("Choose exactly two or three synthetic DOCX examples.");
      return;
    }
    const invalid = selected.find(
      (file) =>
        !file.name.toLowerCase().endsWith(".docx") ||
        file.name.toLowerCase().endsWith(".docm") ||
        file.size < 1 ||
        file.size > MAX_EXAMPLE_BYTES,
    );
    if (invalid) {
      event.target.value = "";
      setFiles([]);
      setError(
        "Every example must be a non-empty, macro-free DOCX no larger than 10 MB.",
      );
      return;
    }
    setFiles(selected);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (files.length < 2 || files.length > 3 || !attested) return;
    setBusy(true);
    setError("");
    setMessage(
      "Quarantining and scanning the examples. No provider receives these bytes.",
    );
    try {
      const body = new FormData();
      files.forEach((file) => body.append("examples", file));
      body.set("candidateName", name);
      body.set("encounterScope", scope);
      body.set("versionDescription", description);
      body.set("syntheticAttestation", String(attested));
      const response = await fetch(CREATE_ENDPOINT, {
        method: "POST",
        credentials: "same-origin",
        body,
      });
      const payload = await readPayload(response);
      if (!response.ok || payload.ok !== true || !payload.reviewUrl) {
        throw new Error(
          payload.error ||
            "The examples were not converted. No template was activated.",
        );
      }
      setMessage("Candidate created. Opening the required field review…");
      router.push(payload.reviewUrl);
    } catch (caught) {
      setMessage("");
      setError(
        caught instanceof Error
          ? caught.message
          : "The examples were not converted. No template was activated.",
      );
    } finally {
      setBusy(false);
    }
  }

  const ready =
    files.length >= 2 &&
    files.length <= 3 &&
    name.trim().length >= 3 &&
    scope.trim().length >= 3 &&
    description.trim().length >= 3 &&
    attested &&
    !busy;

  return (
    <div className={styles.stack}>
      <section className={styles.boundary} aria-labelledby="candidate-boundary">
        <div>
          <div className={styles.eyebrow}>
            Separate workflow · synthetic only
          </div>
          <h2 className={styles.sectionTitle} id="candidate-boundary">
            This does not turn a completed report into an active template
          </h2>
          <p className={styles.copy}>
            QuillMD compares two or three structurally identical synthetic
            examples, detects only deterministic changed cells beside stable
            labels, and generates a new blank candidate. You must approve every
            region, download the candidate, and submit it through the ordinary
            blank-template certification workflow.
          </p>
        </div>
        <div className={styles.boundaryStatus}>No activation path</div>
      </section>

      <form className={styles.uploadPanel} onSubmit={submit}>
        <div className={styles.panelHeading}>
          <div>
            <div className={styles.step}>01 / Examples</div>
            <h2 className={styles.sectionTitle}>
              Add matching synthetic DOCX files
            </h2>
          </div>
          <span className={styles.count}>{files.length} / 2–3</span>
        </div>
        <p className={styles.copy}>
          Each file must contain the required QuillMD synthetic sentinel and the
          same layout. Real patient or physician documents are prohibited in
          this review mode.
        </p>
        <label className={styles.dropzone} htmlFor="candidate-examples">
          <span className={styles.dropzoneTitle}>
            Choose two or three DOCX examples
          </span>
          <span className={styles.helper}>
            Macro-free · 10 MB maximum per file
          </span>
          <input
            ref={fileInputRef}
            className={styles.fileInput}
            id="candidate-examples"
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            multiple
            onChange={chooseFiles}
            disabled={busy}
          />
        </label>
        {files.length > 0 && (
          <ol className={styles.fileList} aria-label="Selected examples">
            {files.map((file, index) => (
              <li key={`${file.name}:${file.size}:${index}`}>
                <span>{index + 1}</span>
                <strong>{file.name}</strong>
                <small>{(file.size / 1024).toFixed(1)} KB</small>
              </li>
            ))}
          </ol>
        )}

        <div className={styles.divider} />
        <div className={styles.step}>02 / Candidate identity</div>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>Candidate name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              required
              disabled={busy}
              placeholder="Synthetic follow-up candidate"
            />
          </label>
          <label className={styles.field}>
            <span>Encounter scope</span>
            <input
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              maxLength={120}
              required
              disabled={busy}
              placeholder="Synthetic follow-up encounter"
            />
          </label>
          <label className={`${styles.field} ${styles.fieldWide}`}>
            <span>Version description</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={500}
              required
              disabled={busy}
              placeholder="Why these examples belong to one stable document structure"
            />
          </label>
        </div>

        <label className={styles.attestation}>
          <input
            type="checkbox"
            checked={attested}
            onChange={(event) => setAttested(event.target.checked)}
            disabled={busy}
          />
          <span>
            I confirm that every selected file is purpose-built synthetic test
            data, contains no real patient or physician identity, and may be
            rejected if its structure is ambiguous.
          </span>
        </label>

        <div className={styles.actions}>
          <button
            className={styles.primaryButton}
            type="submit"
            disabled={!ready}
          >
            {busy ? "Scanning examples…" : "Generate blank candidate"}
          </button>
          <span className={styles.actionNote}>
            Raw files enter private quarantine before parsing.
          </span>
        </div>
        <div className={styles.live} aria-live="polite" aria-atomic="true">
          {error && <p className={styles.error}>{error}</p>}
          {message && <p className={styles.message}>{message}</p>}
        </div>
      </form>

      <section
        className={styles.compatibility}
        aria-labelledby="candidate-matrix"
      >
        <div className={styles.step}>Compatibility boundary</div>
        <h2 className={styles.sectionTitle} id="candidate-matrix">
          Narrow by design
        </h2>
        <div className={styles.matrix}>
          <div>
            <strong>Accepted for detection</strong>
            <p>
              Stable labels with changing plain-text scalar cells in identical
              main-document tables.
            </p>
          </div>
          <div>
            <strong>Rejected or routed elsewhere</strong>
            <p>
              Narrative inference, changed layouts, headers/footers, media,
              identifiers, one-off examples, and documents already containing
              controls or placeholders.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

export function CompletedCandidateReviewWorkspace({
  initial,
}: {
  initial: CompletedCandidateReviewDto;
}) {
  const router = useRouter();
  const [status, setStatus] = useState(initial.status);
  const [selectedId, setSelectedId] = useState(
    initial.regions[0]?.regionId ?? "",
  );
  const [decisions, setDecisions] = useState<Record<string, Decision>>(() =>
    Object.fromEntries(
      initial.regions.flatMap((region) =>
        region.decision === "PENDING"
          ? []
          : [[region.regionId, region.decision as Decision]],
      ),
    ),
  );
  const [attested, setAttested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [preview, setPreview] = useState<{
    projection: CompletedCandidateReviewProjection;
    expiresAtIso: string;
  } | null>(null);
  const reviewReceiptRef = useRef<string | null>(null);
  const [bulkUndo, setBulkUndo] = useState<Record<string, Decision> | null>(
    null,
  );
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const terminal = status !== "PENDING_REVIEW";

  useEffect(() => {
    if (!dirty || status !== "PENDING_REVIEW") return;
    const guard = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty, status]);

  useEffect(() => {
    if (!preview) return;
    const expiresAt = Date.parse(preview.expiresAtIso);
    const delay = Math.max(0, expiresAt - Date.now());
    const timer = window.setTimeout(
      () => {
        reviewReceiptRef.current = null;
        setPreview(null);
        setDecisions({});
        setBulkUndo(null);
        setAttested(false);
        setDirty(false);
        setMessage("");
        setError(
          "The protected comparison expired. Open it again before making the final decision.",
        );
      },
      Math.min(delay, 2_147_483_647),
    );
    return () => window.clearTimeout(timer);
  }, [preview]);

  useEffect(
    () => () => {
      reviewReceiptRef.current = null;
    },
    [],
  );

  const selected =
    initial.regions.find((region) => region.regionId === selectedId) ??
    initial.regions[0];
  const decidedCount = Object.keys(decisions).length;
  const rejectedCount = Object.values(decisions).filter(
    (decision) => decision === "REJECTED",
  ).length;
  const allDecided = decidedCount === initial.regions.length;
  const expectedResult = rejectedCount > 0 ? "REJECTED" : "APPROVED";
  const regionIds = useMemo(
    () => initial.regions.map((region) => region.regionId),
    [initial.regions],
  );

  function clearPreviewForRetry(message: string) {
    reviewReceiptRef.current = null;
    setPreview(null);
    setDecisions({});
    setBulkUndo(null);
    setAttested(false);
    setDirty(false);
    setMessage("");
    setError(message);
  }

  async function openProtectedComparison() {
    if (terminal || previewBusy || busy) return;
    setPreviewBusy(true);
    setError("");
    setMessage(
      "Loading the hash-bound redacted source and candidate topology…",
    );
    reviewReceiptRef.current = null;
    try {
      const response = await fetch(
        `${CREATE_ENDPOINT}/${encodeURIComponent(initial.id)}/review-preview`,
        {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
        },
      );
      const payload = await readPayload(response);
      const expiresAt =
        typeof payload.expiresAtIso === "string"
          ? Date.parse(payload.expiresAtIso)
          : Number.NaN;
      const parsed = CompletedCandidateReviewProjectionSchema.safeParse(
        payload.projection,
      );
      if (
        !response.ok ||
        payload.ok !== true ||
        !parsed.success ||
        typeof payload.reviewReceipt !== "string" ||
        !COMPLETED_CANDIDATE_REVIEW_RECEIPT.test(payload.reviewReceipt) ||
        typeof payload.expiresAtIso !== "string" ||
        !Number.isFinite(expiresAt) ||
        expiresAt <= Date.now() ||
        expiresAt > Date.now() + 15 * 60 * 1000 + 5_000 ||
        parsed.data.candidateSha256 !== initial.candidateSha256 ||
        parsed.data.inventorySha256 !== initial.inventorySha256 ||
        parsed.data.regionCount !== initial.regions.length ||
        !projectionMatchesInventory(parsed.data, initial.regions)
      ) {
        throw new Error(
          payload.error ||
            "The protected comparison was incomplete. Open it again.",
        );
      }
      reviewReceiptRef.current = payload.reviewReceipt;
      setPreview({
        projection: parsed.data,
        expiresAtIso: payload.expiresAtIso,
      });
      setDecisions({});
      setBulkUndo(null);
      setAttested(false);
      setDirty(false);
      setError("");
      setMessage(
        "Exact redacted topology loaded. Decisions remain reversible until you save the terminal review.",
      );
    } catch (caught) {
      clearPreviewForRetry(
        caught instanceof Error
          ? caught.message
          : "The protected comparison could not be opened.",
      );
    } finally {
      setPreviewBusy(false);
    }
  }

  function decide(regionId: string, decision: Decision) {
    if (status !== "PENDING_REVIEW" || !preview || previewBusy) return;
    setDecisions((current) => ({ ...current, [regionId]: decision }));
    setBulkUndo(null);
    setDirty(true);
    setError("");
  }

  function approveAllVisible() {
    if (status !== "PENDING_REVIEW" || !preview || previewBusy) return;
    setBulkUndo(decisions);
    setDecisions(
      Object.fromEntries(regionIds.map((regionId) => [regionId, "APPROVED"])),
    );
    setDirty(true);
    setError("");
  }

  function undoBulkApproval() {
    if (!bulkUndo || status !== "PENDING_REVIEW" || !preview || previewBusy)
      return;
    setDecisions(bulkUndo);
    setBulkUndo(null);
    setDirty(true);
    setError("");
  }

  async function saveReview() {
    const reviewReceipt = reviewReceiptRef.current;
    if (
      !preview ||
      !reviewReceipt ||
      !allDecided ||
      !attested ||
      previewBusy ||
      status !== "PENDING_REVIEW"
    )
      return;
    setBusy(true);
    setError("");
    setMessage("Saving the terminal physician decision…");
    try {
      const response = await fetch(
        `${CREATE_ENDPOINT}/${encodeURIComponent(initial.id)}/review`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            decisions: initial.regions.map((region) => ({
              regionId: region.regionId,
              decision: decisions[region.regionId],
            })),
            physicianAttestation: true,
            reviewReceipt,
          }),
        },
      );
      const payload = await readPayload(response);
      if (response.status === 409) {
        clearPreviewForRetry(
          payload.error ||
            "The protected comparison is stale. Open it again before saving.",
        );
        return;
      }
      if (
        !response.ok ||
        payload.ok !== true ||
        (payload.status !== "APPROVED" && payload.status !== "REJECTED")
      ) {
        throw new Error(payload.error || "The physician review was not saved.");
      }
      setStatus(payload.status);
      reviewReceiptRef.current = null;
      setPreview(null);
      setBulkUndo(null);
      setDirty(false);
      setMessage(
        payload.status === "APPROVED"
          ? "Every region was approved. The blank candidate is available for download, but it is not active."
          : "The candidate was rejected and cannot be downloaded or activated.",
      );
      router.refresh();
    } catch (caught) {
      setMessage("");
      setError(
        caught instanceof Error
          ? caught.message
          : "The physician review was not saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.reviewShell}>
      <section className={styles.reviewSummary}>
        <div>
          <div className={styles.eyebrow}>Completed example → candidate</div>
          <h1>{initial.name}</h1>
          <p>
            {initial.encounterScope} · {initial.versionDescription}
          </p>
        </div>
        <span className={styles[`status${status}`]}>
          {status.replaceAll("_", " ")}
        </span>
      </section>

      <section
        className={styles.compare}
        aria-labelledby="structural-comparison"
      >
        <div className={styles.compareHeading}>
          <div>
            <div className={styles.step}>Structural comparison</div>
            <h2 className={styles.sectionTitle} id="structural-comparison">
              Source evidence and new blank candidate
            </h2>
          </div>
          <span className={styles.count}>
            {initial.comparison.exampleCount} examples
          </span>
        </div>
        <div className={styles.compareGrid}>
          <div>
            <span className={styles.compareLabel}>Isolated sources</span>
            <strong>{initial.comparison.sourceSummary}</strong>
            <p>
              Values are deliberately withheld. Only deterministic structure and
              cryptographic evidence are exposed here.
            </p>
          </div>
          <div>
            <span className={styles.compareLabel}>Generated candidate</span>
            <strong>{initial.comparison.candidateSummary}</strong>
            <p>
              {initial.comparison.candidateFieldCount} blank controls ·{" "}
              {initial.comparison.preservedStaticBlockCount} static blocks
              preserved
            </p>
          </div>
        </div>
        {!terminal && !preview && (
          <div className={styles.previewGate}>
            <div>
              <strong>Open the exact redacted structure before deciding</strong>
              <p>
                QuillMD will disclose one synchronized, value-free projection of
                every source and candidate block. The proof is bound to this
                candidate and expires after 15 minutes.
              </p>
            </div>
            <button
              className={styles.secondaryButton}
              type="button"
              onClick={openProtectedComparison}
              disabled={previewBusy || busy}
            >
              {previewBusy ? "Opening comparison…" : "Open redacted comparison"}
            </button>
          </div>
        )}
        {preview && (
          <div className={styles.structuralPreview}>
            <div className={styles.previewSession} role="status">
              <span>
                Exact projection verified · values withheld · no provider egress
              </span>
              <span>
                Review proof expires at{" "}
                {new Intl.DateTimeFormat(undefined, {
                  hour: "numeric",
                  minute: "2-digit",
                  second: "2-digit",
                }).format(new Date(preview.expiresAtIso))}
              </span>
              <button
                type="button"
                onClick={openProtectedComparison}
                disabled={previewBusy || busy}
              >
                Refresh 15-minute proof
              </button>
            </div>
            <div className={styles.structuralColumnLabels} aria-hidden="true">
              <span>Isolated source structure</span>
              <span>Generated blank candidate</span>
            </div>
            <div className={styles.structuralBlocks}>
              {preview.projection.blocks.map((block) => (
                <section
                  className={styles.structuralPair}
                  key={block.blockKey}
                  data-topology-key={block.blockKey}
                >
                  <div className={styles.structuralPane}>
                    <span className={styles.compareLabel}>
                      Source block {block.displayOrder + 1}
                    </span>
                    {block.kind === "table" ? (
                      <StructuralTable block={block} side="source" />
                    ) : (
                      <div className={styles.redactedParagraph}>
                        Static paragraph withheld
                      </div>
                    )}
                  </div>
                  <div className={styles.structuralPane}>
                    <span className={styles.compareLabel}>
                      Candidate block {block.displayOrder + 1}
                    </span>
                    {block.kind === "table" ? (
                      <StructuralTable block={block} side="candidate" />
                    ) : (
                      <div className={styles.redactedParagraph}>
                        Static paragraph preserved
                      </div>
                    )}
                  </div>
                </section>
              ))}
            </div>
            <p className={styles.previewFootnote}>
              This is a complete structural projection, not a rendered Word
              page. Pagination is intentionally not represented; desktop Word
              inspection remains a separate gate after download.
            </p>
          </div>
        )}
        <dl className={styles.hashes}>
          <div>
            <dt>Candidate SHA-256</dt>
            <dd title={initial.candidateSha256}>
              {abbreviatedHash(initial.candidateSha256)}
            </dd>
          </div>
          <div>
            <dt>Inventory SHA-256</dt>
            <dd title={initial.inventorySha256}>
              {abbreviatedHash(initial.inventorySha256)}
            </dd>
          </div>
          <div>
            <dt>Provider egress</dt>
            <dd>{initial.privacy.providerEgress ? "Blocked" : "None"}</dd>
          </div>
        </dl>
      </section>

      <section
        className={styles.inventory}
        aria-labelledby="candidate-inventory"
      >
        <div className={styles.inventoryHeader}>
          <div>
            <div className={styles.step}>Required physician review</div>
            <h2 className={styles.sectionTitle} id="candidate-inventory">
              Candidate-field inventory
            </h2>
            <p className={styles.copy}>
              Every detected region appears below. Approving confirms only that
              the region should become a blank text control; it does not certify
              clinical mapping or activate a template.
            </p>
          </div>
          <div
            className={styles.progress}
            aria-label={`${decidedCount} of ${initial.regions.length} regions decided`}
          >
            <strong>{decidedCount}</strong> / {initial.regions.length}
          </div>
        </div>

        {!terminal && (
          <div className={styles.bulkBar}>
            <span>
              {preview
                ? `All ${initial.regions.length} suggestions are visible in both the protected comparison and this inventory.`
                : "Open the protected comparison to enable physician decisions."}
            </span>
            <div className={styles.bulkActions}>
              {bulkUndo && (
                <button
                  type="button"
                  onClick={undoBulkApproval}
                  disabled={busy || previewBusy || !preview}
                >
                  Undo bulk approval
                </button>
              )}
              <button
                type="button"
                onClick={approveAllVisible}
                disabled={busy || previewBusy || !preview}
              >
                Approve all {initial.regions.length} visible regions
              </button>
            </div>
          </div>
        )}

        <div className={styles.reviewGrid}>
          <ol className={styles.regionRail} aria-label="Candidate regions">
            {initial.regions.map((region) => {
              const decision = decisions[region.regionId];
              return (
                <li key={region.regionId}>
                  <button
                    type="button"
                    className={
                      region.regionId === selected?.regionId
                        ? styles.regionSelected
                        : ""
                    }
                    onClick={() => setSelectedId(region.regionId)}
                    aria-current={
                      region.regionId === selected?.regionId
                        ? "true"
                        : undefined
                    }
                  >
                    <span className={styles.regionOrder}>
                      {String(region.displayOrder + 1).padStart(2, "0")}
                    </span>
                    <span className={styles.regionIdentity}>
                      <strong>{region.label}</strong>
                      <small>{region.location} · blank text control</small>
                    </span>
                    <span
                      className={styles[`decision${decision ?? "PENDING"}`]}
                    >
                      {decisionLabel(decision)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          {selected && (
            <aside
              className={styles.inspector}
              aria-label={`Review ${selected.label}`}
            >
              <div className={styles.step}>
                Region {selected.displayOrder + 1}
              </div>
              <h3>{selected.label}</h3>
              <dl>
                <div>
                  <dt>Deterministic evidence</dt>
                  <dd>{selected.sourceDescription}</dd>
                </div>
                <div>
                  <dt>Candidate result</dt>
                  <dd>{selected.candidateDescription}</dd>
                </div>
                <div>
                  <dt>Location</dt>
                  <dd>{selected.location}</dd>
                </div>
                <div>
                  <dt>Stable binding</dt>
                  <dd className={styles.mono}>{selected.candidateTag}</dd>
                </div>
                <div>
                  <dt>Source evidence SHA-256</dt>
                  <dd className={styles.mono}>
                    {abbreviatedHash(selected.sourceEvidenceSha256)}
                  </dd>
                </div>
              </dl>
              <fieldset
                className={styles.decisionSet}
                disabled={terminal || busy || previewBusy || !preview}
              >
                <legend>Physician decision</legend>
                <label>
                  <input
                    type="radio"
                    name={`decision-${selected.regionId}`}
                    checked={decisions[selected.regionId] === "APPROVED"}
                    onChange={() => decide(selected.regionId, "APPROVED")}
                  />
                  <span>
                    <strong>Approve region</strong>
                    Keep this as a blank text control.
                  </span>
                </label>
                <label>
                  <input
                    type="radio"
                    name={`decision-${selected.regionId}`}
                    checked={decisions[selected.regionId] === "REJECTED"}
                    onChange={() => decide(selected.regionId, "REJECTED")}
                  />
                  <span>
                    <strong>Reject candidate</strong>
                    This region is not safely inferred.
                  </span>
                </label>
              </fieldset>
            </aside>
          )}
        </div>
      </section>

      {status === "PENDING_REVIEW" ? (
        <section className={styles.finalize}>
          <div>
            <div className={styles.step}>Terminal decision</div>
            <h2 className={styles.sectionTitle}>
              {!preview
                ? "Open the protected structural comparison first"
                : allDecided
                  ? `Saving will mark this candidate ${expectedResult.toLowerCase()}`
                  : `Decide ${initial.regions.length - decidedCount} remaining region${initial.regions.length - decidedCount === 1 ? "" : "s"}`}
            </h2>
          </div>
          <label className={styles.attestation}>
            <input
              type="checkbox"
              checked={attested}
              onChange={(event) => {
                setAttested(event.target.checked);
                setDirty(true);
              }}
              disabled={!preview || !allDecided || busy || previewBusy}
            />
            <span>
              I compared the exact redacted source and candidate structure,
              reviewed every visible region, and understand that this decision
              is final. Approval permits candidate download only.
            </span>
          </label>
          <div className={styles.actions}>
            <button
              className={styles.primaryButton}
              type="button"
              onClick={saveReview}
              disabled={
                !preview || !allDecided || !attested || busy || previewBusy
              }
            >
              {busy ? "Saving review…" : "Save final physician decision"}
            </button>
            <span className={styles.actionNote}>
              No candidate can self-activate.
            </span>
          </div>
        </section>
      ) : (
        <section
          className={status === "APPROVED" ? styles.approved : styles.rejected}
        >
          <div>
            <div className={styles.step}>Review complete</div>
            <h2 className={styles.sectionTitle}>
              {status === "APPROVED"
                ? "Blank candidate approved for download"
                : "Candidate rejected"}
            </h2>
            <p className={styles.copy}>
              {status === "APPROVED"
                ? "The candidate remains separate from active templates. Download it, inspect it in Word, then upload it through the blank/fillable DOCX certification workflow."
                : "A rejected candidate is terminal. It cannot be downloaded, certified, or activated."}
            </p>
          </div>
          {status === "APPROVED" && (
            <a
              className={styles.primaryButton}
              href={`${CREATE_ENDPOINT}/${encodeURIComponent(initial.id)}/download`}
            >
              Download blank candidate DOCX
            </a>
          )}
        </section>
      )}

      <div className={styles.live} aria-live="polite" aria-atomic="true">
        {error && <p className={styles.error}>{error}</p>}
        {message && <p className={styles.message}>{message}</p>}
      </div>
    </div>
  );
}
