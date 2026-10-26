"""The Gastroenterology category and its internal service-family profiles.

Profiles are INTERNAL routing and validation units. The doctor never picks
one: documents are routed automatically and every family's results appear in
one combined review.

Numeric code ranges are used ONLY to route a provider-selected code to a
family. They are not a CPT reference: they establish neither that a code
exists for a service date nor what it describes. Code-set membership and
descriptors stay "not verified" / "withheld" until a licensed CPT edition is
connected.

Required facts are this service's own documentation-completeness checks for
routing review. They are not official coding rules.
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORY_SLUG = 'gastroenterology'
CATEGORY_NAME = 'Gastroenterology'
PROFILES_VERSION = 'gi-profiles@2'


@dataclass(frozen=True)
class ServiceProfile:
    slug: str
    version: str
    label: str
    eyebrow: str
    supported: bool
    # Inclusive numeric code ranges (5-digit strings) used only for routing.
    code_ranges: tuple[tuple[str, str], ...]
    # Individual codes carved out of the ranges above and routed elsewhere.
    excluded_codes: tuple[str, ...] = ()
    required_facts: tuple[str, ...] = ()
    procedure: bool = False  # an endoscopic/procedural family (vs. E/M)
    note: str = ''


def _p(slug, label, eyebrow, supported, ranges, *, excluded=(), required=(), procedure=False, note=''):
    return ServiceProfile(slug=slug, version=f'{slug}@1', label=label, eyebrow=eyebrow, supported=supported,
                          code_ranges=tuple(ranges), excluded_codes=tuple(excluded), required_facts=tuple(required),
                          procedure=procedure, note=note)


EUS_CODES = ('43231', '43232', '43237', '43238', '43242', '43253', '43259', '44406', '44407', '45341', '45342', '45391',
             '45392', '76975')
# Inside the colonoscopy number range but not colonoscopy: they route on to 'outside the GI profiles'.
NOT_COLONOSCOPY = ('45395', '45397', '45399')

PROFILES: dict[str, ServiceProfile] = {p.slug: p for p in (
    _p('gi.office_em', 'Office / outpatient evaluation and management', 'EVALUATION & MANAGEMENT', True,
       [('99202', '99205'), ('99211', '99215'), ('99242', '99245'), ('99417', '99417')],
       required=('setting', 'patient_status', 'em_basis')),
    _p('gi.egd', 'Upper GI endoscopy (EGD, esophagoscopy, enteroscopy)', 'UPPER GI ENDOSCOPY', True,
       [('43180', '43233'), ('43235', '43270'), ('44360', '44379'), ('43210', '43210')],
       excluded=EUS_CODES + tuple(str(c) for c in range(43260, 43271) if c not in (43266, 43270)),
       required=('extent',), procedure=True),
    _p('gi.colonoscopy', 'Colonoscopy', 'COLONOSCOPY', True,
       [('45378', '45399'), ('44388', '44408')], excluded=EUS_CODES + NOT_COLONOSCOPY,
       required=('extent',), procedure=True),
    _p('gi.flex_sig', 'Flexible sigmoidoscopy', 'FLEXIBLE SIGMOIDOSCOPY', True,
       [('45330', '45350')], excluded=EUS_CODES,
       required=('extent',), procedure=True),
    _p('gi.eus', 'Endoscopic ultrasound', 'ENDOSCOPIC ULTRASOUND', True,
       [(code, code) for code in EUS_CODES],
       required=('target',), procedure=True),
    _p('gi.ercp', 'ERCP', 'ERCP', True,
       [('43260', '43265'), ('43273', '43278'), ('74328', '74330')],
       required=('cannulation',), procedure=True),
    _p('gi.sedation', 'Moderate sedation by the performing physician', 'MODERATE SEDATION', False,
       [('99151', '99157')],
       note='Sedation checks are not implemented in this release; review required.'),
    _p('gi.em_other', 'E/M in another setting (hospital, emergency, consult)', 'EVALUATION & MANAGEMENT · OTHER SETTING', False,
       [('99221', '99239'), ('99281', '99288'), ('99291', '99292'), ('99252', '99255')],
       note='Only office/outpatient E/M is profiled in this release; review required.'),
    _p('gi.other', 'Other GI service', 'OTHER GI SERVICE', False,
       [('43450', '43453'), ('43752', '43761'), ('45300', '45327'), ('46600', '46615'), ('46221', '46250'),
        ('91010', '91299'), ('47000', '47001'), ('49082', '49084')],
       note='Recognised as a GI service without a profile in this release; review required.'),
    _p('gi.unsupported', 'Service outside the GI profiles', 'OUTSIDE GI PROFILES', False, [],
       note='Not covered by any GI profile in this release; review required.'),
)}

FAMILY_ORDER = ('gi.office_em', 'gi.egd', 'gi.eus', 'gi.ercp', 'gi.colonoscopy', 'gi.flex_sig',
                'gi.sedation', 'gi.em_other', 'gi.other', 'gi.unsupported')

# Families that routing (gi/detect.py) recognises in document text.
DETECTED_FAMILIES = ('gi.office_em', 'gi.egd', 'gi.colonoscopy', 'gi.flex_sig', 'gi.eus', 'gi.ercp')


def family_for_code(code: str) -> str:
    """Route a provider code to a family by number only. Never raises."""
    if not (isinstance(code, str) and len(code) == 5 and code.isdigit()):
        return 'gi.unsupported'
    for slug in FAMILY_ORDER:
        profile = PROFILES[slug]
        if code in profile.excluded_codes:
            continue
        for low, high in profile.code_ranges:
            if low <= code <= high:
                return slug
    return 'gi.unsupported'


def profile(slug: str) -> ServiceProfile:
    return PROFILES[slug]
