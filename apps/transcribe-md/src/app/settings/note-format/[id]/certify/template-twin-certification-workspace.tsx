'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import type { SemanticMapping } from '@/lib/template-twin/ir';
import type {
  TemplateTwinWorkspace,
  TemplateTwinWorkspaceField,
} from '@/lib/template-twin/client-types';

import styles from './template-twin-certification.module.css';

type FieldFilter = 'all' | 'attention';

const EXPECTED_TYPES: SemanticMapping['expectedDataType'][] = [
  'text',
  'single_select',
  'multi_select',
  'boolean',
  'date',
  'number',
  'measurement',
  'table',
];

const SYNTHETIC_STARTER = [
  'Synthetic test encounter. No real patient information.',
  'The patient reports a mild current symptom on the left side for three days.',
  'They explicitly deny medication allergies.',
  'A synthetic measurement is 12 mm. No medication was prescribed.',
].join(' ');

function titleCase(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function fieldStatus(item: TemplateTwinWorkspaceField): {
  label: string;
  tone: 'safe' | 'review' | 'block';
} {
  if (item.mapping.status === 'certified') {
    return { label: 'Certified', tone: 'safe' };
  }
  if (item.field.detectionStatus === 'unsupported') {
    return { label: 'Unsupported', tone: 'block' };
  }
  if (
    item.field.detectionStatus === 'needs_confirmation' ||
    item.mapping.status === 'needs_confirmation'
  ) {
    return { label: 'Needs confirmation', tone: 'review' };
  }
  return { label: 'Recognized', tone: 'safe' };
}

function StatusPill({ item }: { item: TemplateTwinWorkspaceField }) {
  const status = fieldStatus(item);
  return (
    <span className={styles.status} data-tone={status.tone}>
      {status.label}
    </span>
  );
}

export function TemplateTwinCertificationWorkspace({
  initial,
}: {
  initial: TemplateTwinWorkspace;
}) {
  const router = useRouter();
  const [workspace, setWorkspace] = useState(initial);
  const [fields, setFields] = useState(initial.fields);
  const [selectedId, setSelectedId] = useState(
    initial.fields.find((item) => item.mapping.status !== 'certified')?.field.fieldId ??
      initial.fields[0]?.field.fieldId ??
      '',
  );
  const [filter, setFilter] = useState<FieldFilter>('all');
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<'save' | 'test' | 'certify' | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [syntheticText, setSyntheticText] = useState(SYNTHETIC_STARTER);
  const [ackStructure, setAckStructure] = useState(false);
  const [ackTest, setAckTest] = useState(false);

  const selected =
    fields.find((item) => item.field.fieldId === selectedId) ?? fields[0] ?? null;
  const visibleFields = useMemo(
    () =>
      filter === 'all'
        ? fields
        : fields.filter((item) => fieldStatus(item).tone !== 'safe'),
    [fields, filter],
  );
  const confirmedCount = fields.filter(
    (item) => item.mapping.status === 'certified',
  ).length;
  const allConfirmed = fields.length > 0 && confirmedCount === fields.length;
  const testMatches = Boolean(
    workspace.latestSyntheticTest?.roundTripVerified &&
      workspace.latestSyntheticTest.mappingsSha256 === workspace.mappingsSha256,
  );
  const hasBlockingUnsupported = workspace.stats.blockingUnsupported > 0;
  const canCertify =
    workspace.canEdit &&
    !dirty &&
    allConfirmed &&
    testMatches &&
    !hasBlockingUnsupported &&
    ackStructure &&
    ackTest &&
    !busy;

  function updateMapping(
    fieldId: string,
    patch: Partial<SemanticMapping>,
  ) {
    setFields((current) =>
      current.map((item) =>
        item.field.fieldId === fieldId
          ? { ...item, mapping: { ...item.mapping, ...patch } }
          : item,
      ),
    );
    setDirty(true);
    setAnnouncement('Mapping changed. Save the draft before running a test.');
  }

  async function saveMappings(): Promise<boolean> {
    if (!workspace.canEdit) return true;
    setBusy('save');
    setAnnouncement('Saving semantic mappings.');
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/mappings`,
        {
          method: 'PATCH',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            expectedMappingsSha256: workspace.mappingsSha256,
            mappings: fields.map((item) => item.mapping),
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error('Mappings were not saved', {
          description:
            payload && !payload.ok ? payload.error : 'Reload the workspace and try again.',
        });
        return false;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setDirty(false);
      setAnnouncement('Mappings saved.');
      toast.success('Mapping draft saved');
      return true;
    } catch {
      toast.error('Mappings were not saved', {
        description: 'Check your connection and try again.',
      });
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function runSyntheticTest() {
    if (dirty) {
      toast.error('Save mapping changes first');
      return;
    }
    setBusy('test');
    setAnnouncement('Resolving synthetic evidence and verifying a cloned DOCX.');
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/synthetic-test`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            expectedMappingsSha256: workspace.mappingsSha256,
            encounterText: syntheticText,
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error('Synthetic DOCX did not verify', {
          description:
            payload && !payload.ok
              ? payload.error
              : 'No template was activated. Review the mappings and try again.',
        });
        return;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setAnnouncement('Synthetic DOCX passed package, field, and static-region verification.');
      toast.success('Synthetic DOCX verified');
    } catch {
      toast.error('Synthetic test did not finish', {
        description: 'No template was activated. Check your connection and try again.',
      });
    } finally {
      setBusy(null);
    }
  }

  async function certify() {
    if (!canCertify) return;
    setBusy('certify');
    setAnnouncement('Certifying and activating this immutable template version.');
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/certify`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            expectedMappingsSha256: workspace.mappingsSha256,
            acknowledgeStructure: true,
            acknowledgeSyntheticOutput: true,
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error('Template was not certified', {
          description:
            payload && !payload.ok
              ? payload.error
              : 'Nothing was activated. Reload and try again.',
        });
        return;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setAnnouncement('Template version certified and activated.');
      toast.success('Original Word template activated');
      router.refresh();
    } catch {
      toast.error('Template was not certified', {
        description: 'Nothing was activated. Check your connection and try again.',
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={styles.shell}>
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>

      <header className={styles.header}>
        <div className={styles.eyebrow}>Settings / Note format / Template Twin</div>
        <div className={styles.titleRow}>
          <div>
            <h1 className={styles.title}>{workspace.template.name}</h1>
            <p className={styles.subtitle}>
              Version {workspace.template.version} · Original Word structure ·{' '}
              {workspace.source.compilerVersion}. Every clinical fill must retain encounter evidence.
            </p>
          </div>
          <div className={styles.headerActions}>
            <span
              className={styles.status}
              data-tone={workspace.template.certificationStatus === 'certified' ? 'safe' : 'review'}
            >
              {titleCase(workspace.template.certificationStatus)}
            </span>
            <a href="/settings" className={styles.button} style={{ textDecoration: 'none' }}>
              Back to settings
            </a>
          </div>
        </div>
      </header>

      <section className={styles.summary} aria-label="Detected structure summary">
        <Metric label="Fields" value={workspace.stats.totalFields} />
        <Metric label="Dropdowns" value={workspace.stats.dropdowns + workspace.stats.comboBoxes} />
        <Metric label="Checkboxes" value={workspace.stats.checkboxes} />
        <Metric label="Tables" value={workspace.stats.tables} />
        <Metric label="Unsupported" value={workspace.stats.unsupported} />
        <Metric label="Confirmed" value={`${confirmedCount}/${fields.length}`} />
      </section>

      <div className={styles.workspace}>
        <aside className={styles.rail} aria-label="Template fields">
          <div className={styles.railHeader}>
            <div className={styles.filterRow}>
              <button
                type="button"
                className={styles.filterButton}
                data-active={filter === 'all'}
                onClick={() => setFilter('all')}
              >
                All fields
              </button>
              <button
                type="button"
                className={styles.filterButton}
                data-active={filter === 'attention'}
                onClick={() => setFilter('attention')}
              >
                Needs attention
              </button>
            </div>
          </div>
          <div className={styles.fieldList} role="listbox" aria-label="Detected fields">
            {visibleFields.map((item) => (
              <button
                key={item.field.fieldId}
                type="button"
                role="option"
                aria-selected={item.field.fieldId === selected?.field.fieldId}
                className={styles.fieldButton}
                data-selected={item.field.fieldId === selected?.field.fieldId}
                onClick={() => setSelectedId(item.field.fieldId)}
              >
                <span style={{ minWidth: 0 }}>
                  <span className={styles.fieldLabel}>{item.field.originalLabel}</span>
                  <span className={styles.fieldMeta}>
                    {titleCase(item.field.kind)} · Field {item.field.displayOrder + 1}
                  </span>
                </span>
                <StatusPill item={item} />
              </button>
            ))}
            {visibleFields.length === 0 && (
              <div className={styles.empty}>Every detected field is confirmed.</div>
            )}
          </div>
        </aside>

        <section className={styles.inspector} aria-label="Selected field inspector">
          <div className={styles.inspectorInner}>
            {selected ? (
              <FieldInspector
                item={selected}
                canEdit={workspace.canEdit}
                busy={busy !== null}
                onChange={(patch) => updateMapping(selected.field.fieldId, patch)}
              />
            ) : (
              <div className={styles.empty}>No fillable fields were detected.</div>
            )}

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Unsupported and ambiguous structure</h2>
              {workspace.unsupported.length === 0 ? (
                <div className={styles.callout}>
                  No unsupported OOXML elements were found in the compiled parts.
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 8 }}>
                  {workspace.unsupported.map((item, index) => (
                    <div
                      key={`${item.partName}:${item.path}:${index}`}
                      className={styles.callout}
                      data-tone={item.blocksCertification ? 'block' : undefined}
                    >
                      <strong style={{ color: 'var(--color-linear-text)', fontWeight: 600 }}>
                        {item.label || titleCase(item.code)}
                      </strong>
                      <div style={{ marginTop: 3 }}>{item.detail}</div>
                      <div className={styles.fieldMeta} style={{ marginTop: 6 }}>
                        {item.blocksCertification ? 'Blocks certification' : 'Review warning'} · {item.partName}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Synthetic evidence test</h2>
              <div className={styles.callout}>
                Use synthetic details only. This test runs the same fact resolver and exact renderer used by voice and typed visits, then reopens the DOCX and verifies fields and untouched regions.
              </div>
              <label className={`${styles.field} ${styles.fieldWide}`} style={{ marginTop: 12 }}>
                <span className={styles.monoLabel}>Synthetic encounter text</span>
                <textarea
                  className={styles.textarea}
                  value={syntheticText}
                  onChange={(event) => setSyntheticText(event.target.value)}
                  disabled={!workspace.canEdit || busy !== null}
                />
              </label>
              {workspace.latestSyntheticTest && (
                <div className={styles.testStatus}>
                  <span>
                    {testMatches ? 'Verified against current mappings' : 'Re-run required after mapping changes'}
                  </span>
                  <a
                    className={styles.button}
                    href={workspace.latestSyntheticTest.downloadUrl}
                    style={{ textDecoration: 'none' }}
                  >
                    Inspect filled DOCX
                  </a>
                </div>
              )}
            </div>

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Physician certification</h2>
              <div className={styles.checkList}>
                <label className={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={ackStructure}
                    onChange={(event) => setAckStructure(event.target.checked)}
                    disabled={!workspace.canEdit}
                  />
                  I reviewed every detected field and every unsupported item in this exact template version.
                </label>
                <label className={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={ackTest}
                    onChange={(event) => setAckTest(event.target.checked)}
                    disabled={!workspace.canEdit}
                  />
                  I inspected the synthetic filled copy and approve its mappings, blank policies, and structure.
                </label>
              </div>
            </div>
          </div>
        </section>
      </div>

      <footer className={styles.footer}>
        <div style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)', lineHeight: 1.4 }}>
          {workspace.canEdit
            ? dirty
              ? 'Unsaved mapping changes'
              : `${confirmedCount} of ${fields.length} fields confirmed`
            : 'This activated version is immutable. Create a new version to change a mapping.'}
        </div>
        <div className={styles.footerActions}>
          {workspace.canEdit && (
            <>
              <button
                type="button"
                className={styles.button}
                onClick={() => void saveMappings()}
                disabled={!dirty || busy !== null}
              >
                {busy === 'save' ? 'Saving…' : 'Save draft'}
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => void runSyntheticTest()}
                disabled={dirty || busy !== null || !allConfirmed || hasBlockingUnsupported}
              >
                {busy === 'test' ? 'Verifying…' : 'Run synthetic test'}
              </button>
              <button
                type="button"
                className={styles.primaryButton}
                onClick={() => void certify()}
                disabled={!canCertify}
                title={
                  canCertify
                    ? undefined
                    : 'Confirm every field, clear blocking items, verify the current mappings, and acknowledge both statements.'
                }
              >
                {busy === 'certify' ? 'Certifying…' : 'Certify & activate'}
              </button>
            </>
          )}
        </div>
      </footer>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.metric}>
      <span className={styles.monoLabel}>{label}</span>
      <span className={styles.metricValue}>{value}</span>
    </div>
  );
}

function FieldInspector({
  item,
  canEdit,
  busy,
  onChange,
}: {
  item: TemplateTwinWorkspaceField;
  canEdit: boolean;
  busy: boolean;
  onChange: (patch: Partial<SemanticMapping>) => void;
}) {
  const { field, mapping } = item;
  const disabled = !canEdit || busy;
  return (
    <>
      <div className={styles.section}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <div className={styles.eyebrow}>Selected field</div>
            <h2 style={{ margin: '5px 0 0', fontSize: 18, fontWeight: 500 }}>
              {field.originalLabel}
            </h2>
          </div>
          <StatusPill item={item} />
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Original Word definition</h3>
        <div className={styles.definitionGrid}>
          <Definition label="Field type" value={titleCase(field.kind)} />
          <Definition label="Detection" value={titleCase(field.detectionStatus)} />
          <Definition label="Label source" value={titleCase(field.labelSource)} />
          <Definition label="Clinical priority" value={titleCase(field.criticality)} />
          <Definition label="Location" value={field.rendererBinding.partName} />
        </div>
        {field.allowedOptions.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div className={styles.monoLabel} style={{ marginBottom: 6 }}>Allowed options · exact order</div>
            <ol className={styles.optionList}>
              {field.allowedOptions.map((option) => (
                <li key={`${option.ordinal}:${option.value}`} className={styles.optionRow}>
                  <span className={styles.optionOrdinal}>{option.ordinal + 1}</span>
                  <span>{option.displayText}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Approved semantic mapping</h3>
        <div className={styles.formGrid}>
          <label className={`${styles.field} ${styles.fieldWide}`}>
            <span className={styles.monoLabel}>Clinical concept</span>
            <input
              className={styles.input}
              value={mapping.clinicalConcept ?? ''}
              onChange={(event) => onChange({ clinicalConcept: event.target.value || null, status: 'needs_confirmation' })}
              disabled={disabled}
              maxLength={160}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Expected data type</span>
            <select
              className={styles.select}
              value={mapping.expectedDataType}
              onChange={(event) => onChange({ expectedDataType: event.target.value as SemanticMapping['expectedDataType'], status: 'needs_confirmation' })}
              disabled={disabled}
            >
              {EXPECTED_TYPES.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Polarity</span>
            <select
              className={styles.select}
              value={mapping.polarityBehavior}
              onChange={(event) => onChange({ polarityBehavior: event.target.value as SemanticMapping['polarityBehavior'], status: 'needs_confirmation' })}
              disabled={disabled}
            >
              {(['affirmative_only', 'explicit_denial_allowed', 'value_only', 'not_applicable'] as const).map((value) => (
                <option key={value} value={value}>{titleCase(value)}</option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Temporality</span>
            <select
              className={styles.select}
              value={mapping.temporality ?? ''}
              onChange={(event) => onChange({ temporality: (event.target.value || null) as SemanticMapping['temporality'], status: 'needs_confirmation' })}
              disabled={disabled}
            >
              <option value="">Not constrained</option>
              {(['current', 'historical', 'planned', 'any'] as const).map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Laterality</span>
            <select
              className={styles.select}
              value={mapping.laterality ?? ''}
              onChange={(event) => onChange({ laterality: (event.target.value || null) as SemanticMapping['laterality'], status: 'needs_confirmation' })}
              disabled={disabled}
            >
              <option value="">Not set</option>
              {(['required', 'optional', 'not_applicable'] as const).map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Unit policy</span>
            <select
              className={styles.select}
              value={mapping.unitPolicy ?? ''}
              onChange={(event) => onChange({ unitPolicy: (event.target.value || null) as SemanticMapping['unitPolicy'], status: 'needs_confirmation' })}
              disabled={disabled}
            >
              <option value="">Not set</option>
              {(['required', 'optional', 'forbidden', 'not_applicable'] as const).map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Unknown policy</span>
            <select
              className={styles.select}
              value={mapping.unknownPolicy}
              onChange={(event) => onChange({ unknownPolicy: event.target.value as SemanticMapping['unknownPolicy'], status: 'needs_confirmation' })}
              disabled={disabled}
            >
              {(['blank', 'not_documented', 'requires_input'] as const).map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
          </label>
          <label className={`${styles.field} ${styles.fieldWide}`}>
            <span className={styles.monoLabel}>Approved synonyms · comma separated</span>
            <input
              className={styles.input}
              value={mapping.approvedSynonyms.join(', ')}
              onChange={(event) => onChange({
                approvedSynonyms: event.target.value.split(',').map((value) => value.trim()).filter(Boolean).slice(0, 50),
                status: 'needs_confirmation',
              })}
              disabled={disabled}
            />
          </label>
          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={mapping.required}
              onChange={(event) => onChange({ required: event.target.checked, status: 'needs_confirmation' })}
              disabled={disabled}
            />
            Required before signing
          </label>
        </div>
        {canEdit && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 14 }}>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => onChange({ status: 'certified' })}
              disabled={busy || mapping.status === 'certified'}
            >
              {mapping.status === 'certified' ? 'Field confirmed' : 'Confirm this field'}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className={styles.monoLabel}>{label}</div>
      <div className={styles.definitionValue}>{value}</div>
    </div>
  );
}
