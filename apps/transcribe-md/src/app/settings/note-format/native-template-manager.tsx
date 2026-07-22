'use client';

// ============================================================================
// Template Twin — certify-once workspace (Stage 4). Flag-gated; rendered only
// when NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX is ON.
// ----------------------------------------------------------------------------
// Upload your Word .docx ONCE → it compiles → you review the field mapping →
// certify. From then on every visit on that template fills + exports in your own
// document automatically. You never review per-note. Uncertified templates keep
// the standard styled export.
// ============================================================================

import { useRef, useState, useTransition } from 'react';

import {
  uploadNativeTemplateAction,
  certifyNativeTemplateAction,
} from '@/actions/template-twin-certify';
import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';

export interface NativeTemplateListItem {
  noteTemplateId: string;
  name: string;
  certificationStatus: string; // 'certified' | 'recognized' | 'needs_confirmation' | 'unsupported' | 'quarantined'
  fieldCount: number;
  version: number;
}

const mono = 'var(--font-mono)';
const sans = 'var(--font-sans)';

function StatusPill({ status }: { status: string }) {
  const certified = status === 'certified';
  const blocked = status === 'unsupported' || status === 'quarantined';
  const cls = certified
    ? 'qm-lin-pill qm-lin-pill--ready'
    : blocked
      ? 'qm-lin-pill qm-lin-pill--review'
      : 'qm-lin-pill';
  const label = certified
    ? 'Certified'
    : status === 'needs_confirmation'
      ? 'Needs review'
      : blocked
        ? 'Unsupported'
        : 'Draft';
  return <span className={cls}>{label}</span>;
}

export function NativeTemplateManager({
  existing,
}: {
  existing: NativeTemplateListItem[];
}) {
  const [workspace, setWorkspace] = useState<TemplateTwinWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [certifiedName, setCertifiedName] = useState<string | null>(null);
  const [uploading, startUpload] = useTransition();
  const [certifying, startCertify] = useTransition();
  const fileRef = useRef<HTMLInputElement>(null);

  function onFile(file: File) {
    setError(null);
    setCertifiedName(null);
    const fd = new FormData();
    fd.append('file', file);
    startUpload(async () => {
      const res = await uploadNativeTemplateAction(fd);
      if (res.ok) {
        setWorkspace(res.data);
      } else {
        setError(res.error);
        setWorkspace(null);
      }
      if (fileRef.current) fileRef.current.value = '';
    });
  }

  function onCertify() {
    if (!workspace) return;
    setError(null);
    startCertify(async () => {
      const res = await certifyNativeTemplateAction(
        workspace.template.id,
        workspace.mappingsSha256,
      );
      if (res.ok) {
        setCertifiedName(res.data.template.name);
        setWorkspace(null);
      } else {
        setError(res.error);
      }
    });
  }

  const busy = uploading || certifying;

  return (
    <div
      style={{
        marginTop: 22,
        paddingTop: 18,
        borderTop: '1px solid var(--color-linear-hairline)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <span
          style={{ fontFamily: sans, fontSize: 13, fontWeight: 500, color: 'var(--color-linear-text)' }}
        >
          Native template (beta)
        </span>
        <span className="qm-lin-pill">Opt-in</span>
      </div>
      <p
        style={{
          margin: '0 0 14px',
          fontFamily: sans,
          fontSize: 12.5,
          color: 'var(--color-linear-text-2)',
          lineHeight: 1.55,
          maxWidth: 620,
        }}
      >
        Upload your own Word template with dropdowns and tables. You review the
        field mapping <strong>once</strong> and certify it; after that, every
        visit on this template comes back as your exact document, filled in — no
        per-note review. Until you certify, exports use the standard format.
      </p>

      {/* Existing native templates */}
      {existing.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
          {existing.map((t) => (
            <div
              key={t.noteTemplateId}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                padding: '9px 12px',
                borderRadius: 8,
                border: '1px solid var(--color-linear-border)',
                background: 'var(--color-linear-surface-1)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                <span
                  style={{
                    fontFamily: sans,
                    fontSize: 13,
                    color: 'var(--color-linear-text)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {t.name}
                </span>
                <span style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)' }}>
                  {t.fieldCount} fields
                </span>
              </div>
              <StatusPill status={t.certificationStatus} />
            </div>
          ))}
        </div>
      )}

      {/* Just-certified confirmation */}
      {certifiedName && (
        <div
          role="status"
          style={{
            padding: '11px 14px',
            borderRadius: 8,
            border: '1px solid rgba(122, 166, 140, 0.4)',
            background: 'var(--color-linear-row-hover)',
            marginBottom: 14,
            fontFamily: sans,
            fontSize: 13,
            color: 'var(--color-linear-text)',
          }}
        >
          <strong>{certifiedName}</strong> is certified. New visits on this
          template will fill and export natively.
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          role="alert"
          style={{
            padding: '11px 14px',
            borderRadius: 8,
            border: '1px solid rgba(212, 87, 74, 0.35)',
            background: 'rgba(212, 87, 74, 0.06)',
            marginBottom: 14,
            fontFamily: sans,
            fontSize: 12.5,
            color: 'var(--color-linear-text)',
            lineHeight: 1.5,
          }}
        >
          {error}
        </div>
      )}

      {/* Review workspace (post-upload, pre-certify) */}
      {workspace ? (
        <ReviewWorkspace
          workspace={workspace}
          certifying={certifying}
          onCertify={onCertify}
          onCancel={() => {
            setWorkspace(null);
            setError(null);
          }}
        />
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <input
            ref={fileRef}
            type="file"
            accept=".docx"
            aria-label="Upload a Word .docx template to certify"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
            }}
            style={{ display: 'none' }}
            id="native-template-file"
          />
          <label
            htmlFor="native-template-file"
            className="qm-lin-btn qm-tap-44"
            aria-disabled={busy}
            style={{
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.55 : 1,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            {uploading ? 'Compiling…' : 'Upload .docx to certify'}
          </label>
          <span
            aria-live="polite"
            style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)' }}
          >
            {uploading ? 'Securing + compiling your template…' : '.docx, max 5 MB'}
          </span>
        </div>
      )}
    </div>
  );
}

function ReviewWorkspace({
  workspace,
  certifying,
  onCertify,
  onCancel,
}: {
  workspace: TemplateTwinWorkspace;
  certifying: boolean;
  onCertify: () => void;
  onCancel: () => void;
}) {
  const fields = workspace.fields;
  const byStatus = fields.reduce<Record<string, number>>((acc, f) => {
    const s = f.field.detectionStatus;
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});
  const blockingUnsupported = workspace.unsupported.filter((u) => u.blocksCertification);
  const canCertify = workspace.template.certificationStatus !== 'unsupported' &&
    blockingUnsupported.length === 0;

  return (
    <div
      style={{
        border: '1px solid var(--color-linear-border)',
        borderRadius: 10,
        overflow: 'hidden',
        background: 'var(--color-linear-surface-1)',
      }}
    >
      <div
        style={{
          padding: '13px 16px',
          borderBottom: '1px solid var(--color-linear-hairline)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div style={{ fontFamily: sans, fontSize: 14, fontWeight: 500, color: 'var(--color-linear-text)' }}>
            {workspace.template.name}
          </div>
          <div style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)', marginTop: 3 }}>
            {fields.length} fields · {workspace.stats.dropdowns} dropdowns · {workspace.stats.tables} table
            {workspace.stats.tables === 1 ? '' : 's'}
          </div>
        </div>
        <StatusPill status={workspace.template.certificationStatus} />
      </div>

      {/* Detection summary */}
      <div
        style={{
          padding: '12px 16px',
          display: 'flex',
          gap: 18,
          flexWrap: 'wrap',
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        {(['recognized', 'needs_confirmation', 'certified', 'unsupported'] as const).map((s) =>
          byStatus[s] ? (
            <div key={s} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontFamily: mono, fontSize: 18, color: 'var(--color-linear-text)' }}>
                {byStatus[s]}
              </span>
              <span style={{ fontFamily: mono, fontSize: 10.5, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--color-linear-text-3)' }}>
                {s.replace('_', ' ')}
              </span>
            </div>
          ) : null,
        )}
      </div>

      {/* Field mapping list (scrollable) */}
      <div style={{ maxHeight: 320, overflowY: 'auto' }} role="list" aria-label="Field mapping proposal">
        {fields.map((f) => (
          <div
            key={f.definitionId}
            role="listitem"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              padding: '8px 16px',
              borderBottom: '1px solid var(--color-linear-hairline)',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontFamily: sans,
                  fontSize: 12.5,
                  color: 'var(--color-linear-text)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {f.field.originalLabel}
              </div>
              <div style={{ fontFamily: mono, fontSize: 10.5, color: 'var(--color-linear-text-3)', marginTop: 2 }}>
                {f.field.kind.replace('_', ' ')}
                {f.mapping.clinicalConcept ? ` → ${f.mapping.clinicalConcept}` : ''}
              </div>
            </div>
            <span
              className={
                f.field.detectionStatus === 'unsupported'
                  ? 'qm-lin-pill qm-lin-pill--review'
                  : 'qm-lin-pill'
              }
              style={{ flexShrink: 0 }}
            >
              {f.field.detectionStatus.replace('_', ' ')}
            </span>
          </div>
        ))}
      </div>

      {blockingUnsupported.length > 0 && (
        <div
          style={{
            padding: '11px 16px',
            fontFamily: sans,
            fontSize: 12,
            color: 'var(--color-linear-coral)',
            borderTop: '1px solid var(--color-linear-hairline)',
          }}
        >
          {blockingUnsupported.length} element{blockingUnsupported.length === 1 ? '' : 's'} can&apos;t be
          safely reproduced and block certification. Simplify the template in Word and re-upload.
        </div>
      )}

      {/* Certify actions */}
      <div
        style={{
          padding: '13px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 10,
          borderTop: '1px solid var(--color-linear-hairline)',
        }}
      >
        <button type="button" className="qm-lin-btn qm-tap-44" onClick={onCancel} disabled={certifying}>
          Cancel
        </button>
        <button
          type="button"
          className="qm-lin-btn qm-tap-44"
          onClick={onCertify}
          disabled={certifying || !canCertify}
          title={canCertify ? 'Certify this mapping — fills every future visit' : 'Resolve blocking elements first'}
          style={{
            opacity: canCertify ? 1 : 0.5,
            background: 'var(--color-linear-sage)',
            borderColor: 'var(--color-linear-sage)',
            color: '#08090a',
            fontWeight: 500,
          }}
        >
          {certifying ? 'Verifying & certifying…' : 'Certify & activate'}
        </button>
      </div>
    </div>
  );
}
