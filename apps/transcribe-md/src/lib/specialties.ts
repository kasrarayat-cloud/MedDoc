export type SpecialtySlug =
  | 'cardiology'
  | 'dermatology'
  | 'internal-medicine'
  | 'ob-gyn'
  | 'orthopedics'
  | 'pediatrics'
  | 'primary-care'
  | 'psychiatry';

export const SPECIALTIES: Array<{ slug: SpecialtySlug; displayName: string }> = [
  { slug: 'cardiology', displayName: 'Cardiology' },
  { slug: 'dermatology', displayName: 'Dermatology' },
  { slug: 'internal-medicine', displayName: 'Internal Medicine' },
  { slug: 'ob-gyn', displayName: 'Obstetrics & Gynecology' },
  { slug: 'orthopedics', displayName: 'Orthopedics' },
  { slug: 'pediatrics', displayName: 'Pediatrics' },
  { slug: 'primary-care', displayName: 'Primary Care / Family Medicine' },
  { slug: 'psychiatry', displayName: 'Psychiatry' },
];
