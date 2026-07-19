"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  FileJson2,
  Gauge,
  GitCommit,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import type { TemplateTwinReleaseControlView } from "@/lib/template-twin/release-control";
import {
  TEMPLATE_TWIN_RELEASE_DISCIPLINES,
  type TemplateTwinApprovalDecision,
  type TemplateTwinReleaseDiscipline,
  type TemplateTwinReleaseStage,
} from "@/lib/template-twin/release-control-contracts";

import AdminNav from "../../_components/AdminNav.client";

interface Props {
  readonly initial: TemplateTwinReleaseControlView;
}

type ReleaseView = NonNullable<TemplateTwinReleaseControlView["release"]>;
type Checkpoint = ReleaseView["checkpoints"][number];

const STAGE_LABELS: Record<string, string> = {
  CANARY: "Canary",
  PERCENT_10: "10%",
  PERCENT_25: "25%",
  PERCENT_50: "50%",
  PERCENT_100: "100%",
};

const DISCIPLINE_LABELS: Record<TemplateTwinReleaseDiscipline, string> = {
  DESKTOP_WORD: "Desktop Microsoft Word",
  CLINICAL_SAFETY: "Clinical Safety",
  PRIVACY_LEGAL: "Privacy / Legal",
  OPERATIONS: "Operations",
};

export default function TemplateTwinReleaseWorkbench({ initial }: Props) {
  const [control, setControl] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    try {
      const response = await fetch("/api/admin/template-twin/releases", {
        cache: "no-store",
      });
      const payload = (await response.json()) as {
        ok?: boolean;
        control?: TemplateTwinReleaseControlView;
        error?: string;
      };
      if (!response.ok || !payload.control) {
        throw new Error(
          payload.error ?? "Release state could not be refreshed.",
        );
      }
      setControl(payload.control);
      setMessage("Release state refreshed from the database.");
    } catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : "Release refresh failed closed.";
      setMessage(detail);
      toast.error(detail);
    } finally {
      setBusy(false);
    }
  }

  async function mutate(body: Record<string, unknown>) {
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/admin/template-twin/releases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as {
        ok?: boolean;
        error?: string;
      };
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error ?? "Release mutation failed closed.");
      }
      toast.success("Release evidence committed.");
      await refresh();
    } catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : "Release mutation failed closed.";
      setMessage(detail);
      toast.error(detail);
    } finally {
      setBusy(false);
    }
  }

  const release = control.release;
  const gateSummary = useMemo(
    () => (release ? summarizeGates(release) : null),
    [release],
  );

  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <ShieldCheck
              className="h-5 w-5 text-linear-sage-bright"
              aria-hidden="true"
            />
            <div>
              <div className="mb-1 font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3">
                Admin · Production release
              </div>
              <h1 className="text-[20px] font-semibold leading-tight tracking-tight text-linear-text">
                Template Twin control plane
              </h1>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-linear-text-3">
                <StatusDot
                  tone={control.global.enabled ? "success" : "pending"}
                  label={
                    control.global.enabled
                      ? "Global gate enabled"
                      : "Global gate disabled"
                  }
                />
                <span aria-hidden="true">·</span>
                <span className="font-mono tabular-nums">
                  generation {control.global.generation}
                </span>
                <span aria-hidden="true">·</span>
                <span>rollback fence {control.global.rollbackFenceState}</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={busy}
            className="qm-lin-btn min-h-11 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            Refresh exact state
          </button>
        </div>
      </header>

      <AdminNav />

      <main className="mx-auto flex max-w-[1440px] flex-col gap-5 px-4 py-6 sm:px-6">
        <p className="sr-only" aria-live="polite">
          {message}
        </p>
        {message && (
          <div className="rounded-md border border-linear-border-strong bg-linear-surface-2 px-4 py-3 text-[12px] text-linear-text-2">
            {message}
          </div>
        )}

        {!release ? (
          <CreateReleaseControl busy={busy} mutate={mutate} />
        ) : (
          <>
            <section
              aria-labelledby="release-identity-heading"
              className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1"
            >
              <SectionHeading
                id="release-identity-heading"
                icon={GitCommit}
                eyebrow="1 · Exact release identity"
                title="Frozen inputs and deployment attestation"
                detail="Any SHA or image mismatch makes every downstream action ineligible."
                status={<StateBadge value={release.status} />}
              />
              <IdentityGrid release={release} />
              {release.status === "DRAFT" && (
                <FreezeControl release={release} busy={busy} mutate={mutate} />
              )}
            </section>

            <section
              aria-labelledby="release-gates-heading"
              className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1"
            >
              <SectionHeading
                id="release-gates-heading"
                icon={LockKeyhole}
                eyebrow="2 · Human gate ledger"
                title="Authority-bound decisions"
                detail="Decisions are append-only and bind evidence to this exact release identity."
                status={
                  gateSummary?.allPass ? (
                    <StateBadge value="PASS" />
                  ) : gateSummary?.hasFail ? (
                    <StateBadge value="FAIL" />
                  ) : (
                    <StateBadge value="HUMAN PENDING" />
                  )
                }
              />
              <GateLedger release={release} />
              {!["DRAFT", "REJECTED", "REVOKED"].includes(release.status) && (
                <ApprovalControl
                  release={release}
                  busy={busy}
                  mutate={mutate}
                />
              )}
            </section>

            <section
              aria-labelledby="release-checkpoints-heading"
              className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1"
            >
              <SectionHeading
                id="release-checkpoints-heading"
                icon={Gauge}
                eyebrow="3 · Controlled exposure"
                title="Fixed checkpoint rail"
                detail="Practices are indivisible. Target and actual physician counts remain visible at every checkpoint."
                status={
                  <StateBadge
                    value={control.global.enabled ? "ACTIVE" : "DISABLED"}
                  />
                }
              />
              <CheckpointRail checkpoints={release.checkpoints} />
              <CheckpointActions
                release={release}
                globalGeneration={control.global.generation}
                busy={busy}
                mutate={mutate}
              />
            </section>

            <section
              aria-labelledby="release-cohort-heading"
              className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1"
            >
              <SectionHeading
                id="release-cohort-heading"
                icon={Users}
                eyebrow="Authorized population"
                title="Practice-scoped stable cohort"
                detail="Counts are aggregate and PHI-free; practice assignment never changes after release creation."
                status={
                  <span className="font-mono text-[11px] text-linear-text-2">
                    {release.practices.length} practices
                  </span>
                }
              />
              <PracticeTable practices={release.practices} />
            </section>

            {["FROZEN", "APPROVED", "ROLLING_OUT", "STABLE_100"].includes(
              release.status,
            ) && (
              <RevokeControl
                release={release}
                globalGeneration={control.global.generation}
                busy={busy}
                mutate={mutate}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function CreateReleaseControl({
  busy,
  mutate,
}: {
  busy: boolean;
  mutate: (body: Record<string, unknown>) => Promise<void>;
}) {
  const expected = "CREATE EXACT RELEASE";
  const [manifest, setManifest] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const parsed = useMemo(() => {
    try {
      const value = JSON.parse(manifest) as unknown;
      if (!value || typeof value !== "object" || Array.isArray(value))
        return null;
      const record = value as Record<string, unknown>;
      if (
        !record.evidence ||
        !record.guardrailPolicy ||
        !Array.isArray(record.authorizedPracticeIds) ||
        !Array.isArray(record.canaryPracticeIds)
      ) {
        return null;
      }
      return record;
    } catch {
      return null;
    }
  }, [manifest]);

  return (
    <section
      aria-labelledby="create-release-heading"
      className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1"
    >
      <SectionHeading
        id="create-release-heading"
        icon={FileJson2}
        eyebrow="Exact evidence intake"
        title="Create a disabled release candidate"
        detail="Creation records immutable evidence and a stable practice cohort. It cannot enable global or practice rollout gates."
        status={<StateBadge value="DISABLED" />}
      />
      <div className="grid gap-4 px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <label className="grid gap-1 text-[11px] text-linear-text-3">
          Signed release manifest JSON
          <textarea
            value={manifest}
            onChange={(event) => setManifest(event.target.value)}
            rows={18}
            spellCheck={false}
            autoComplete="off"
            placeholder='{"evidence": {…}, "guardrailPolicy": {…}, "authorizedPracticeIds": […], "canaryPracticeIds": […]}'
            className="min-h-[320px] resize-y rounded-md border border-linear-border-strong bg-linear-surface-2 px-3 py-3 font-mono text-[11px] leading-5 text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
          />
        </label>
        <div className="flex flex-col gap-4">
          <div className="rounded-md border border-amber-400/25 bg-amber-400/[0.06] px-3 py-3 text-[11px] leading-5 text-amber-200/80">
            The manifest may contain only exact commit/image/evidence hashes,
            the versioned aggregate guardrail policy, and authorized practice
            identifiers. Do not paste credentials, documents, patient data, or
            free-text clinical content.
          </div>
          <dl className="space-y-2 text-[11px] text-linear-text-3">
            <div className="flex items-center justify-between gap-3">
              <dt>Manifest shape</dt>
              <dd>
                <StateBadge
                  value={parsed ? "READY TO VALIDATE" : "HUMAN PENDING"}
                  compact
                />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt>Authorized practices</dt>
              <dd className="font-mono text-linear-text-2">
                {parsed && Array.isArray(parsed.authorizedPracticeIds)
                  ? parsed.authorizedPracticeIds.length
                  : "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt>Explicit canaries</dt>
              <dd className="font-mono text-linear-text-2">
                {parsed && Array.isArray(parsed.canaryPracticeIds)
                  ? parsed.canaryPracticeIds.length
                  : "—"}
              </dd>
            </div>
          </dl>
          <div className="mt-auto grid gap-3">
            <TypedConfirmation
              expected={expected}
              value={confirmation}
              setValue={setConfirmation}
            />
            <button
              type="button"
              disabled={busy || !parsed || confirmation !== expected}
              onClick={() =>
                void mutate({
                  action: "create",
                  confirmation,
                  evidence: parsed!.evidence,
                  guardrailPolicy: parsed!.guardrailPolicy,
                  authorizedPracticeIds: parsed!.authorizedPracticeIds,
                  canaryPracticeIds: parsed!.canaryPracticeIds,
                })
              }
              className="qm-lin-btn-primary min-h-11 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <LockKeyhole className="h-3.5 w-3.5" aria-hidden="true" />
              Create disabled candidate
            </button>
          </div>
        </div>
      </div>
      <div className="border-t border-linear-border bg-linear-surface-2 px-4 py-3 text-[11px] text-linear-text-3 sm:px-5">
        Human authority assignments remain out of band and cannot be granted
        from this workbench.
      </div>
    </section>
  );
}

function SectionHeading({
  id,
  icon: Icon,
  eyebrow,
  title,
  detail,
  status,
}: {
  id: string;
  icon: typeof ShieldCheck;
  eyebrow: string;
  title: string;
  detail: string;
  status: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-linear-border px-4 py-4 sm:px-5">
      <div className="flex min-w-0 items-start gap-3">
        <Icon
          className="mt-0.5 h-4 w-4 shrink-0 text-linear-text-3"
          aria-hidden="true"
        />
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
            {eyebrow}
          </div>
          <h2
            id={id}
            className="mt-1 text-[15px] font-semibold text-linear-text"
          >
            {title}
          </h2>
          <p className="mt-1 text-[12px] leading-5 text-linear-text-3">
            {detail}
          </p>
        </div>
      </div>
      {status}
    </div>
  );
}

function IdentityGrid({ release }: { release: ReleaseView }) {
  const rows = [
    ["Release identity", release.releaseIdentitySha256],
    ["Source commit", release.sourceCommitSha],
    ["Base commit", release.baseCommitSha],
    ["Application image", release.appImageDigest],
    ["Worker image", release.workerImageDigest],
    ["Migrator image", release.migratorImageDigest],
    ["Test census", release.evidence.testCensusEvidenceSha256],
    ["Independent review", release.evidence.independentReviewEvidenceSha256],
    ["Security / secret scan", release.evidence.securityEvidenceSha256],
    ["Migration / restore", release.evidence.migrationRestoreEvidenceSha256],
    ["Desktop Word", release.evidence.officeWordEvidenceSha256],
    ["Guardrail policy", release.evidence.guardrailPolicySha256],
    ["Practice manifest", release.evidence.authorizedPracticeManifestSha256],
  ];
  return (
    <dl className="grid grid-cols-1 divide-y divide-linear-border sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-3">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="min-w-0 border-linear-border px-4 py-3 sm:border-b sm:border-r lg:px-5"
        >
          <dt className="text-[11px] text-linear-text-3">{label}</dt>
          <dd
            className="mt-1 truncate font-mono text-[11px] text-linear-text-2"
            title={value}
          >
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function FreezeControl({ release, busy, mutate }: ActionProps) {
  const expected = `FREEZE ${release.releaseIdentitySha256.slice(0, 12)}`;
  const [confirmation, setConfirmation] = useState("");
  return (
    <ActionPanel
      title="Freeze this exact candidate"
      detail="Freezing locks the creator out of every human approval discipline."
    >
      <TypedConfirmation
        expected={expected}
        value={confirmation}
        setValue={setConfirmation}
      />
      <button
        type="button"
        disabled={busy || confirmation !== expected}
        onClick={() =>
          void mutate({
            action: "freeze",
            releaseId: release.id,
            expectedReleaseGeneration: release.generation,
            confirmation,
          })
        }
        className="qm-lin-btn-primary min-h-11 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <LockKeyhole className="h-3.5 w-3.5" aria-hidden="true" />
        Freeze exact release
      </button>
    </ActionPanel>
  );
}

function GateLedger({ release }: { release: ReleaseView }) {
  return (
    <ul className="divide-y divide-linear-border">
      {TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => {
        const decision = release.approvals.find(
          (approval) => approval.discipline === discipline,
        );
        const status =
          !decision || !decision.authorityActive
            ? "HUMAN PENDING"
            : decision.decision === "APPROVE"
              ? "PASS"
              : "FAIL";
        return (
          <li
            key={discipline}
            className="grid gap-2 px-4 py-3 sm:grid-cols-[minmax(180px,1fr)_auto_minmax(220px,1.2fr)] sm:items-center sm:px-5"
          >
            <div>
              <div className="text-[13px] font-medium text-linear-text">
                {DISCIPLINE_LABELS[discipline]}
              </div>
              <div className="mt-0.5 text-[11px] text-linear-text-3">
                Independent human authority required
              </div>
            </div>
            <StateBadge value={status} />
            <div className="min-w-0 text-left text-[11px] text-linear-text-3 sm:text-right">
              {decision ? (
                <>
                  <div className="truncate font-mono text-linear-text-2">
                    {decision.actorEmailSnapshot ?? decision.actorId}
                  </div>
                  <div className="mt-0.5 truncate font-mono">
                    evidence {decision.evidenceSha256}
                  </div>
                  <div className="mt-0.5">
                    {formatTimestamp(decision.decidedAt)}
                    {!decision.authorityActive ? " · authority revoked" : ""}
                  </div>
                </>
              ) : (
                "No decision recorded"
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function ApprovalControl({ release, busy, mutate }: ActionProps) {
  const available = TEMPLATE_TWIN_RELEASE_DISCIPLINES.filter((discipline) =>
    release.operatorAuthorities.includes(discipline),
  );
  const [discipline, setDiscipline] = useState<TemplateTwinReleaseDiscipline>(
    available[0] ?? "DESKTOP_WORD",
  );
  const [decision, setDecision] =
    useState<TemplateTwinApprovalDecision>("APPROVE");
  const [evidenceSha256, setEvidenceSha256] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const rolloutStarted = ["ROLLING_OUT", "STABLE_100"].includes(release.status);
  const effectiveDecision =
    rolloutStarted && decision === "APPROVE" ? "REVOKE" : decision;
  const expected = `${effectiveDecision} ${discipline} ${release.releaseIdentitySha256.slice(0, 12)}`;
  if (available.length === 0) {
    return (
      <div className="border-t border-linear-border bg-linear-surface-2 px-4 py-4 text-[12px] text-linear-text-3 sm:px-5">
        This operator has no active out-of-band human authority assignment. The
        workbench cannot create one.
      </div>
    );
  }
  return (
    <ActionPanel
      title="Record a human decision"
      detail="The release creator/finalizer cannot use this action. Decisions cannot be edited or deleted."
    >
      <label className="grid gap-1 text-[11px] text-linear-text-3">
        Discipline
        <select
          value={discipline}
          onChange={(event) => {
            setDiscipline(event.target.value as TemplateTwinReleaseDiscipline);
            setConfirmation("");
          }}
          className="min-h-11 rounded-md border border-linear-border-strong bg-linear-surface-1 px-3 text-[12px] text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
        >
          {available.map((value) => (
            <option key={value} value={value}>
              {DISCIPLINE_LABELS[value]}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1 text-[11px] text-linear-text-3">
        Decision
        <select
          value={effectiveDecision}
          onChange={(event) => {
            setDecision(event.target.value as TemplateTwinApprovalDecision);
            setConfirmation("");
          }}
          className="min-h-11 rounded-md border border-linear-border-strong bg-linear-surface-1 px-3 text-[12px] text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
        >
          {!rolloutStarted && <option value="APPROVE">Approve</option>}
          <option value="REJECT">Reject</option>
          <option value="REVOKE">Revoke prior approval</option>
        </select>
      </label>
      <label className="grid min-w-[260px] flex-1 gap-1 text-[11px] text-linear-text-3">
        Evidence SHA-256
        <input
          value={evidenceSha256}
          onChange={(event) =>
            setEvidenceSha256(event.target.value.trim().toLowerCase())
          }
          spellCheck={false}
          autoComplete="off"
          className="min-h-11 rounded-md border border-linear-border-strong bg-linear-surface-1 px-3 font-mono text-[11px] text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
        />
      </label>
      <TypedConfirmation
        expected={expected}
        value={confirmation}
        setValue={setConfirmation}
      />
      <button
        type="button"
        disabled={
          busy ||
          confirmation !== expected ||
          !/^[0-9a-f]{64}$/u.test(evidenceSha256)
        }
        onClick={() =>
          void mutate({
            action: "record_approval",
            releaseId: release.id,
            expectedReleaseGeneration: release.generation,
            discipline,
            decision: effectiveDecision,
            evidenceSha256,
            confirmation,
          })
        }
        className={
          effectiveDecision === "APPROVE"
            ? "qm-lin-btn-primary min-h-11 disabled:cursor-not-allowed disabled:opacity-40"
            : "min-h-11 rounded-md border border-red-500/40 bg-red-500/10 px-3 text-[12px] font-medium text-red-300 disabled:cursor-not-allowed disabled:opacity-40"
        }
      >
        {effectiveDecision === "APPROVE" ? (
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
        ) : (
          <Ban className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
        )}
        Record {effectiveDecision.toLowerCase()}
      </button>
    </ActionPanel>
  );
}

function CheckpointRail({
  checkpoints,
}: {
  checkpoints: ReleaseView["checkpoints"];
}) {
  return (
    <ol className="grid grid-cols-1 border-b border-linear-border sm:grid-cols-5">
      {checkpoints.map((checkpoint, index) => (
        <li
          key={checkpoint.id}
          className="relative border-linear-border px-4 py-4 sm:border-r sm:last:border-r-0"
        >
          {index < checkpoints.length - 1 && (
            <span
              className="absolute right-0 top-[29px] hidden h-px w-4 translate-x-2 bg-linear-border-strong sm:block"
              aria-hidden="true"
            />
          )}
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
              {checkpoint.ordinal.toString().padStart(2, "0")}
            </span>
            <StateBadge value={checkpoint.status} compact />
          </div>
          <div className="mt-3 text-[15px] font-semibold text-linear-text">
            {STAGE_LABELS[checkpoint.stage] ?? checkpoint.stage}
          </div>
          <dl className="mt-3 space-y-1 text-[11px] text-linear-text-3">
            <div className="flex justify-between gap-2">
              <dt>Target</dt>
              <dd className="font-mono text-linear-text-2">
                {checkpoint.targetPhysicianCount}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Assigned</dt>
              <dd className="font-mono text-linear-text-2">
                {checkpoint.assignedPhysicianCount}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Observed</dt>
              <dd className="font-mono text-linear-text-2">
                {checkpoint.passedPhysicianCount ??
                  checkpoint.activatedPhysicianCount ??
                  "—"}
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ol>
  );
}

function CheckpointActions({
  release,
  globalGeneration,
  busy,
  mutate,
}: ActionProps & { globalGeneration: string }) {
  const active = release.checkpoints.find(
    (checkpoint) => checkpoint.status === "ACTIVE",
  );
  const next = release.checkpoints.find(
    (checkpoint) =>
      checkpoint.status === "PENDING" &&
      release.checkpoints
        .filter((row) => row.ordinal < checkpoint.ordinal)
        .every((row) => row.status === "PASSED"),
  );
  return (
    <div className="divide-y divide-linear-border">
      {active && (
        <ActiveCheckpointControl
          release={release}
          checkpoint={active}
          globalGeneration={globalGeneration}
          busy={busy}
          mutate={mutate}
        />
      )}
      {!active &&
        next &&
        ["APPROVED", "ROLLING_OUT"].includes(release.status) && (
          <ActivateControl
            release={release}
            checkpoint={next}
            globalGeneration={globalGeneration}
            busy={busy}
            mutate={mutate}
          />
        )}
      {!active && !next && (
        <div className="px-4 py-4 text-[12px] text-linear-text-3 sm:px-5">
          No checkpoint action is eligible in the current state.
        </div>
      )}
    </div>
  );
}

function ActivateControl({
  release,
  checkpoint,
  globalGeneration,
  busy,
  mutate,
}: ActionProps & { checkpoint: Checkpoint; globalGeneration: string }) {
  const stage = checkpoint.stage as TemplateTwinReleaseStage;
  const expected = `ACTIVATE ${stage} ${release.releaseIdentitySha256.slice(0, 12)}`;
  const [confirmation, setConfirmation] = useState("");
  return (
    <ActionPanel
      title={`Activate ${STAGE_LABELS[stage]}`}
      detail={`This enables ${checkpoint.assignedPhysicianCount} snapshot physicians across whole practices. The server re-censuses actual physicians before commit.`}
    >
      <TypedConfirmation
        expected={expected}
        value={confirmation}
        setValue={setConfirmation}
      />
      <button
        type="button"
        disabled={busy || confirmation !== expected}
        onClick={() =>
          void mutate({
            action: "activate_checkpoint",
            releaseId: release.id,
            stage,
            expectedReleaseGeneration: release.generation,
            expectedGlobalGeneration: globalGeneration,
            confirmation,
          })
        }
        className="qm-lin-btn-primary min-h-11 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Activate {STAGE_LABELS[stage]}
      </button>
    </ActionPanel>
  );
}

function ActiveCheckpointControl({
  release,
  checkpoint,
  globalGeneration,
  busy,
  mutate,
}: ActionProps & { checkpoint: Checkpoint; globalGeneration: string }) {
  const stage = checkpoint.stage as TemplateTwinReleaseStage;
  const expected = `PASS ${stage} ${release.releaseIdentitySha256.slice(0, 12)}`;
  const [confirmation, setConfirmation] = useState("");
  return (
    <div>
      <div className="grid gap-4 px-4 py-4 sm:grid-cols-3 sm:px-5">
        <EvidenceStat
          label="Activated"
          value={
            checkpoint.activatedAt
              ? formatTimestamp(checkpoint.activatedAt)
              : "—"
          }
        />
        <EvidenceStat
          label="Earliest pass"
          value={
            checkpoint.earliestPassAt
              ? formatTimestamp(checkpoint.earliestPassAt)
              : "—"
          }
        />
        <EvidenceStat
          label="Latest metric"
          value={
            checkpoint.latestMetric
              ? `${checkpoint.latestMetric.evaluation} · ${checkpoint.latestMetric.canonicalSha256.slice(0, 12)}`
              : "HUMAN PENDING / missing"
          }
        />
      </div>
      {checkpoint.latestMetric && (
        <div className="border-t border-linear-border px-4 py-3 text-[11px] text-linear-text-3 sm:px-5">
          <span className="font-mono text-linear-text-2">
            sample {checkpoint.latestMetric.sampleCount}
          </span>
          <span className="mx-2">·</span>
          {checkpoint.latestMetric.blockingReasons.length
            ? checkpoint.latestMetric.blockingReasons.join(", ")
            : "No blocking reason recorded"}
        </div>
      )}
      <ActionPanel
        title={`Pass ${STAGE_LABELS[stage]}`}
        detail="Pass is a separate human operation. A fresh, complete, baked metric snapshot is required server-side."
      >
        <TypedConfirmation
          expected={expected}
          value={confirmation}
          setValue={setConfirmation}
        />
        <button
          type="button"
          disabled={
            busy ||
            confirmation !== expected ||
            checkpoint.latestMetric?.evaluation !== "PASS"
          }
          onClick={() =>
            void mutate({
              action: "pass_checkpoint",
              releaseId: release.id,
              stage,
              expectedReleaseGeneration: release.generation,
              expectedGlobalGeneration: globalGeneration,
              confirmation,
            })
          }
          className="qm-lin-btn-primary min-h-11 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Pass {STAGE_LABELS[stage]}
        </button>
      </ActionPanel>
    </div>
  );
}

function PracticeTable({ practices }: { practices: ReleaseView["practices"] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-[12px]">
        <thead className="border-b border-linear-border bg-linear-surface-2 text-[10px] uppercase tracking-[0.07em] text-linear-text-3">
          <tr>
            <th className="px-4 py-3 font-medium sm:px-5">Rank / practice</th>
            <th className="px-4 py-3 font-medium">Stage</th>
            <th className="px-4 py-3 text-right font-medium">
              Snapshot physicians
            </th>
            <th className="px-4 py-3 text-right font-medium">Gate</th>
            <th className="px-4 py-3 text-right font-medium sm:px-5">
              Generation
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-linear-border">
          {practices.map((practice) => (
            <tr key={practice.practiceId} className="hover:bg-linear-row-hover">
              <td className="px-4 py-3 sm:px-5">
                <div className="font-medium text-linear-text">
                  {practice.cohortRank.toString().padStart(2, "0")} ·{" "}
                  {practice.practiceSlugSnapshot}
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-linear-text-3">
                  {practice.practiceId}
                </div>
              </td>
              <td className="px-4 py-3 text-linear-text-2">
                {STAGE_LABELS[practice.activationStage] ??
                  practice.activationStage}
                {practice.isCanary ? " · explicit canary" : ""}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-linear-text-2">
                {practice.physicianCountSnapshot}
              </td>
              <td className="px-4 py-3 text-right">
                <StateBadge
                  value={practice.templateTwinEnabled ? "ACTIVE" : "DISABLED"}
                  compact
                />
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-linear-text-3 sm:px-5">
                {practice.rolloutGeneration}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RevokeControl({
  release,
  globalGeneration,
  busy,
  mutate,
}: ActionProps & { globalGeneration: string }) {
  const expected = `REVOKE ${release.releaseIdentitySha256.slice(0, 12)}`;
  const [reasonCode, setReasonCode] = useState("");
  const [confirmation, setConfirmation] = useState("");
  return (
    <section
      aria-labelledby="release-revoke-heading"
      className="rounded-lg border border-red-500/30 bg-red-500/[0.06]"
    >
      <div className="flex items-start gap-3 px-4 py-4 sm:px-5">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0 text-red-300"
          aria-hidden="true"
        />
        <div>
          <h2
            id="release-revoke-heading"
            className="text-[14px] font-semibold text-red-200"
          >
            Global release revoke
          </h2>
          <p className="mt-1 text-[12px] leading-5 text-red-200/70">
            The server disables the global database gate before disabling any
            practice and makes this release terminal.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3 border-t border-red-500/20 px-4 py-4 sm:px-5">
        <label className="grid gap-1 text-[11px] text-red-200/70">
          Reason code
          <input
            value={reasonCode}
            onChange={(event) =>
              setReasonCode(event.target.value.toUpperCase())
            }
            placeholder="GUARDRAIL_OR_INCIDENT"
            className="min-h-11 rounded-md border border-red-500/30 bg-linear-surface-1 px-3 font-mono text-[11px] text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
          />
        </label>
        <TypedConfirmation
          expected={expected}
          value={confirmation}
          setValue={setConfirmation}
          tone="danger"
        />
        <button
          type="button"
          disabled={
            busy ||
            confirmation !== expected ||
            !/^[A-Z][A-Z0-9_]{2,79}$/u.test(reasonCode)
          }
          onClick={() =>
            void mutate({
              action: "revoke_release",
              releaseId: release.id,
              expectedReleaseGeneration: release.generation,
              expectedGlobalGeneration: globalGeneration,
              reasonCode,
              confirmation,
            })
          }
          className="min-h-11 rounded-md border border-red-500/40 bg-red-500/15 px-3 text-[12px] font-semibold text-red-200 transition-colors hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Ban className="mr-1.5 inline h-3.5 w-3.5" aria-hidden="true" />
          Revoke globally
        </button>
      </div>
    </section>
  );
}

interface ActionProps {
  release: ReleaseView;
  busy: boolean;
  mutate: (body: Record<string, unknown>) => Promise<void>;
}

function ActionPanel({
  title,
  detail,
  children,
}: {
  title: string;
  detail: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 border-t border-linear-border bg-linear-surface-2 px-4 py-4 sm:px-5">
      <div className="mr-auto max-w-md self-center">
        <div className="text-[12px] font-medium text-linear-text">{title}</div>
        <div className="mt-0.5 text-[11px] leading-5 text-linear-text-3">
          {detail}
        </div>
      </div>
      {children}
    </div>
  );
}

function TypedConfirmation({
  expected,
  value,
  setValue,
  tone = "default",
}: {
  expected: string;
  value: string;
  setValue: (value: string) => void;
  tone?: "default" | "danger";
}) {
  return (
    <label
      className={`grid min-w-[280px] flex-1 gap-1 text-[11px] ${tone === "danger" ? "text-red-200/70" : "text-linear-text-3"}`}
    >
      Type <span className="font-mono text-linear-text-2">{expected}</span>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        autoComplete="off"
        spellCheck={false}
        className={`min-h-11 rounded-md bg-linear-surface-1 px-3 font-mono text-[11px] text-linear-text focus-visible:outline-none focus-visible:ring-2 ${tone === "danger" ? "border border-red-500/30 focus-visible:ring-red-400" : "border border-linear-border-strong focus-visible:ring-linear-sage"}`}
      />
    </label>
  );
}

function EvidenceStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.07em] text-linear-text-3">
        {label}
      </div>
      <div
        className="mt-1 truncate font-mono text-[11px] text-linear-text-2"
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

function StateBadge({
  value,
  compact = false,
}: {
  value: string;
  compact?: boolean;
}) {
  const tone = ["PASS", "PASSED", "APPROVED", "STABLE_100", "ACTIVE"].includes(
    value,
  )
    ? "success"
    : ["FAIL", "FAILED", "REJECTED", "REVOKED"].includes(value)
      ? "danger"
      : "pending";
  const Icon =
    tone === "success" ? CheckCircle2 : tone === "danger" ? Ban : CircleDashed;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border font-mono font-medium uppercase tracking-[0.05em] ${compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-1 text-[10px]"} ${tone === "success" ? "border-linear-sage/30 bg-linear-sage-tint text-linear-sage-bright" : tone === "danger" ? "border-red-500/30 bg-red-500/10 text-red-300" : "border-amber-400/30 bg-amber-400/10 text-amber-300"}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {value.replaceAll("_", " ")}
    </span>
  );
}

function StatusDot({
  tone,
  label,
}: {
  tone: "success" | "pending";
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`h-1.5 w-1.5 rounded-full ${tone === "success" ? "bg-linear-sage" : "bg-amber-400"}`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}

function summarizeGates(release: ReleaseView) {
  const statuses = TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => {
    const decision = release.approvals.find(
      (approval) => approval.discipline === discipline,
    );
    if (!decision || !decision.authorityActive) return "PENDING";
    return decision.decision === "APPROVE" ? "PASS" : "FAIL";
  });
  return {
    allPass: statuses.every((status) => status === "PASS"),
    hasFail: statuses.some((status) => status === "FAIL"),
  };
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? date.toLocaleString()
    : "Invalid timestamp";
}
