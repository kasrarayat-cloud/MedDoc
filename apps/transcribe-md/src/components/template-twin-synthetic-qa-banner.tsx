import { FlaskConical } from "lucide-react";

export function TemplateTwinSyntheticQaBanner({
  compact = false,
}: {
  compact?: boolean;
}) {
  return (
    <aside
      aria-label="Template Twin synthetic test restriction"
      className={`flex gap-3 rounded-lg border border-linear-amber/35 bg-linear-amber/5 text-linear-text ${
        compact ? "px-3 py-2.5" : "px-4 py-3"
      }`}
    >
      <FlaskConical
        aria-hidden
        className="mt-0.5 h-4 w-4 flex-none text-linear-amber"
      />
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-linear-amber">
          Synthetic test only — not for patient care
        </p>
        {!compact && (
          <p className="mt-1 text-[12px] leading-5 text-linear-text-2">
            Use only the allowlisted synthetic template and synthetic encounter
            details. This staging workflow cannot authorize real patient use.
          </p>
        )}
      </div>
    </aside>
  );
}
