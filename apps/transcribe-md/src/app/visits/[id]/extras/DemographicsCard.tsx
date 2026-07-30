'use client';

// ============================================================================
// DemographicsCard — patient profile (name / DOB / MRN / address / …).
// ----------------------------------------------------------------------------
// Reads what the visit page already fetches on the patient relation
// (name, dateOfBirth, externalId). Anything beyond that — address,
// insurance, language, emergency contact — is not yet wired into the
// extras-tab data shape; those rows render with an em-dash placeholder
// and "Awaiting data" sub-eyebrow so the field surface remains intact
// for a follow-up data PR.
// ============================================================================

import { ExtrasCard, Kv } from './ExtrasCard';
import { formatLocalDate } from '@/lib/format-time';
import { ageYearsOf } from '@/lib/patient-display';

export interface DemographicsCardData {
  name: string;
  dateOfBirth: string | null;
  externalId: string | null;
  /** Optional fields the existing data shape doesn't surface yet. Pass
   *  in if/when the patient model grows; they default to null and
   *  render as em-dash. */
  address?: string | null;
  insurance?: string | null;
  insuranceVerified?: string | null;
  preferredLanguage?: string | null;
  emergencyContact?: string | null;
  emergencyRelation?: string | null;
}

interface Props {
  data: DemographicsCardData;
  readonly: boolean;
}

export function DemographicsCard({ data, readonly }: Props) {
  const age = ageYearsOf(data.dateOfBirth);
  // Field count: name + dob always present; mrn / address / insurance /
  // language / emergency-contact each contribute when populated.
  const populatedFields = [
    Boolean(data.name),
    Boolean(data.dateOfBirth),
    Boolean(data.externalId),
    Boolean(data.address),
    Boolean(data.insurance),
    Boolean(data.preferredLanguage),
    Boolean(data.emergencyContact),
  ].filter(Boolean).length;

  return (
    <ExtrasCard
      icon="👤"
      title="Demographics"
      sub={`Patient profile · ${populatedFields} field${
        populatedFields === 1 ? '' : 's'
      }`}
      count={null}
      hideEdit={readonly}
    >
      <div className="qm-lin-extras-kv-grid">
        <Kv label="Full name" value={data.name} />
        <Kv
          label="Date of birth"
          value={
            data.dateOfBirth ? formatLocalDate(data.dateOfBirth) : null
          }
          secondary={age != null ? `${age} yo` : undefined}
          mono={Boolean(data.dateOfBirth)}
        />
        <Kv label="MRN" value={data.externalId} mono />
        <Kv label="Address" value={data.address ?? null} />
        <Kv
          label="Insurance"
          value={data.insurance ?? null}
          secondary={
            data.insuranceVerified
              ? `verified ${data.insuranceVerified}`
              : undefined
          }
        />
        <Kv label="Preferred language" value={data.preferredLanguage ?? null} />
        <Kv
          label="Emergency contact"
          value={data.emergencyContact ?? null}
          secondary={data.emergencyRelation ?? undefined}
        />
      </div>
    </ExtrasCard>
  );
}
