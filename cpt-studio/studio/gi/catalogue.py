"""The GI coverage catalogue: what each internal service family supports, requires and checks (ARCHITECTURE 5.10).

One entry per family states its support level, the documentation it requires, the documented acts it can reconcile
with proposed codes, which acts are not separately reported (and why, as an internal profile rule), the questions it
asks when required documentation is missing, and what a proposal's evidence must show.

The code-to-act table (``CODES``) says which documented act a provider-selected code accounts for. It is an INTERNAL
engineering profile used only to reconcile proposals with the documented-service inventory: it is not a CPT reference,
it contains no descriptor, and it neither proposes nor validates a code. Code-set membership stays not verified until a
licensed CPT edition is connected; a code missing from this table is "coverage not established", never "wrong".

Support levels:
- ``supported``: the inventory reads the family's services and acts, the catalogue reconciles them with proposals, and
  the family has regression documents (tests/corpus/services).
- ``recognised``: services are recognised and listed for review, but acts are not reconciled with codes.
- ``unsupported``: named so that the result can say so; nothing is reconciled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CATALOGUE_VERSION = 'gi-catalogue@1'

SUPPORTED, RECOGNISED, UNSUPPORTED = 'supported', 'recognised', 'unsupported'


@dataclass(frozen=True)
class CodeProfile:
    family: str
    covers: tuple[str, ...] = ()  # documented act kinds the code accounts for
    base: bool = False  # the family's examination without an intervention
    exam: str = ''  # an examination class where the family distinguishes them (EUS: 'limited' | 'full')
    addon: bool = False


@dataclass(frozen=True)
class FamilyEntry:
    family: str
    label: str
    support: str
    kinds: tuple[str, ...]
    documentation: tuple[str, ...]  # what the family requires documented
    acts: tuple[str, ...]  # act kinds reconciled with codes
    bundled: tuple[tuple[str, str], ...] = ()  # (act kind, why it is not separately reported in this profile)
    unsupported_acts: tuple[tuple[str, str], ...] = ()  # (act kind, what is missing)
    questions: tuple[tuple[str, str], ...] = ()  # (fact, question asked when it is not documented)
    evidence: tuple[str, ...] = ()  # what a proposal's passages must show
    rules: tuple[str, ...] = ()  # rule checks applied, with the source that grounds each
    notes: tuple[str, ...] = ()


def _c(family, covers=(), *, base=False, exam='', addon=False):
    return CodeProfile(family=family, covers=tuple(covers), base=base, exam=exam, addon=addon)


C, EGD, ESO, ENT, SIG, EUS, ERCP = ('gi.colonoscopy', 'gi.egd', 'gi.egd', 'gi.enteroscopy', 'gi.flex_sig', 'gi.eus',
                                    'gi.ercp')

CODES: dict[str, CodeProfile] = {
    # Office / outpatient E/M
    **{code: _c('gi.office_em', ('em_visit',), base=True) for code in (
        '99202', '99203', '99204', '99205', '99211', '99212', '99213', '99214', '99215',
        '99242', '99243', '99244', '99245')},
    '99417': _c('gi.office_em', ('em_prolonged',), addon=True),
    # EGD
    '43235': _c(EGD, base=True), '43236': _c(EGD, ('injection',)), '43239': _c(EGD, ('biopsy',)),
    '43241': _c(EGD, ('tube_placement',)), '43243': _c(EGD, ('injection',)), '43244': _c(EGD, ('band_ligation',)),
    '43245': _c(EGD, ('dilation',)), '43246': _c(EGD, ('peg',)), '43247': _c(EGD, ('foreign_body',)),
    '43248': _c(EGD, ('dilation',)), '43249': _c(EGD, ('dilation',)), '43233': _c(EGD, ('dilation',)),
    '43250': _c(EGD, ('hot_biopsy',)), '43251': _c(EGD, ('snare',)), '43254': _c(EGD, ('emr',)),
    '43255': _c(EGD, ('bleeding_control',)), '43257': _c(EGD, ('ablation',)), '43266': _c(EGD, ('stent',)),
    '43270': _c(EGD, ('ablation',)), '43210': _c(EGD, ('fundoplication',)), '43497': _c(EGD, ('myotomy',)),
    # Esophagoscopy (flexible transoral and transnasal), in the upper GI family
    '43200': _c(ESO, base=True), '43201': _c(ESO, ('injection',)), '43202': _c(ESO, ('biopsy',)),
    '43204': _c(ESO, ('injection',)), '43205': _c(ESO, ('band_ligation',)), '43211': _c(ESO, ('emr',)),
    '43212': _c(ESO, ('stent',)), '43213': _c(ESO, ('dilation',)), '43214': _c(ESO, ('dilation',)),
    '43215': _c(ESO, ('foreign_body',)), '43216': _c(ESO, ('hot_biopsy',)), '43217': _c(ESO, ('snare',)),
    '43220': _c(ESO, ('dilation',)), '43226': _c(ESO, ('dilation',)), '43227': _c(ESO, ('bleeding_control',)),
    '43229': _c(ESO, ('ablation',)), '43197': _c(ESO, base=True), '43198': _c(ESO, ('biopsy',)),
    # Small-bowel enteroscopy, ileoscopy and pouchoscopy through a stoma
    '44360': _c(ENT, base=True), '44361': _c(ENT, ('biopsy',)), '44363': _c(ENT, ('foreign_body',)),
    '44364': _c(ENT, ('snare',)), '44365': _c(ENT, ('hot_biopsy', 'ablation')), '44366': _c(ENT, ('bleeding_control',)),
    '44369': _c(ENT, ('ablation',)), '44370': _c(ENT, ('stent',)), '44372': _c(ENT, ('tube_placement', 'peg')),
    '44373': _c(ENT, ('tube_replacement',)), '44376': _c(ENT, base=True), '44377': _c(ENT, ('biopsy',)),
    '44378': _c(ENT, ('bleeding_control',)), '44379': _c(ENT, ('stent',)), '44380': _c(ENT, base=True),
    '44381': _c(ENT, ('dilation',)), '44382': _c(ENT, ('biopsy',)), '44384': _c(ENT, ('stent',)),
    '44385': _c(ENT, base=True), '44386': _c(ENT, ('biopsy',)),
    # Colonoscopy (and through a stoma)
    '45378': _c(C, base=True), '45379': _c(C, ('foreign_body',)), '45380': _c(C, ('biopsy',)),
    '45381': _c(C, ('injection', 'tattoo')), '45382': _c(C, ('bleeding_control',)), '45384': _c(C, ('hot_biopsy',)),
    '45385': _c(C, ('snare',)), '45386': _c(C, ('dilation',)), '45388': _c(C, ('ablation',)),
    '45389': _c(C, ('stent',)), '45390': _c(C, ('emr',)), '45393': _c(C, ('decompression',)),
    '45398': _c(C, ('band_ligation',)),
    '44388': _c(C, base=True), '44389': _c(C, ('biopsy',)), '44390': _c(C, ('foreign_body',)),
    '44391': _c(C, ('bleeding_control',)), '44392': _c(C, ('hot_biopsy',)), '44394': _c(C, ('snare',)),
    '44401': _c(C, ('ablation',)), '44402': _c(C, ('stent',)), '44403': _c(C, ('emr',)),
    '44404': _c(C, ('injection', 'tattoo')), '44405': _c(C, ('dilation',)), '44408': _c(C, ('decompression',)),
    # Flexible sigmoidoscopy
    '45330': _c(SIG, base=True), '45331': _c(SIG, ('biopsy',)), '45332': _c(SIG, ('foreign_body',)),
    '45333': _c(SIG, ('hot_biopsy',)), '45334': _c(SIG, ('bleeding_control',)), '45335': _c(SIG, ('injection', 'tattoo')),
    '45337': _c(SIG, ('decompression',)), '45338': _c(SIG, ('snare',)), '45340': _c(SIG, ('dilation',)),
    '45346': _c(SIG, ('ablation',)), '45347': _c(SIG, ('stent',)), '45349': _c(SIG, ('emr',)),
    '45350': _c(SIG, ('band_ligation',)),
    # Endoscopic ultrasound
    '43231': _c(EUS, ('eus_exam',), exam='limited'), '43232': _c(EUS, ('eus_exam', 'fna'), exam='limited'),
    '43237': _c(EUS, ('eus_exam',), exam='limited'), '43238': _c(EUS, ('eus_exam', 'fna'), exam='limited'),
    '43242': _c(EUS, ('eus_exam', 'fna'), exam='full'), '43259': _c(EUS, ('eus_exam',), exam='full'),
    '43253': _c(EUS, ('eus_exam', 'injection')), '43240': _c(EUS, ('eus_exam', 'drainage')),
    '45341': _c(EUS, ('eus_exam',)), '45342': _c(EUS, ('eus_exam', 'fna')),
    '45391': _c(EUS, ('eus_exam',)), '45392': _c(EUS, ('eus_exam', 'fna')),
    '44406': _c(EUS, ('eus_exam',)), '44407': _c(EUS, ('eus_exam', 'fna')),
    # ERCP
    '43260': _c(ERCP, base=True), '43261': _c(ERCP, ('biopsy',)), '43262': _c(ERCP, ('sphincterotomy',)),
    '43263': _c(ERCP, ('pressure_measurement',)), '43264': _c(ERCP, ('stone_extraction',)),
    '43265': _c(ERCP, ('lithotripsy', 'stone_extraction')), '43273': _c(ERCP, ('cholangioscopy',), addon=True),
    '43274': _c(ERCP, ('stent',)), '43275': _c(ERCP, ('stent_removal', 'foreign_body')),
    '43276': _c(ERCP, ('stent_exchange',)), '43277': _c(ERCP, ('dilation',)), '43278': _c(ERCP, ('ablation',)),
    # Capsule endoscopy
    '91110': _c('gi.capsule', ('capsule_study',)), '91111': _c('gi.capsule', ('capsule_study',)),
    '91113': _c('gi.capsule', ('capsule_study',)),
    # Motility / manometry
    '91010': _c('gi.motility', ('manometry',)), '91013': _c('gi.motility', ('manometry',), addon=True),
    '91020': _c('gi.motility', ('manometry',)), '91022': _c('gi.motility', ('manometry',)),
    '91117': _c('gi.motility', ('manometry',)), '91040': _c('gi.motility', ('manometry',)),
    # pH / impedance
    '91034': _c('gi.reflux', ('ph_monitoring',)), '91035': _c('gi.reflux', ('ph_monitoring',)),
    '91037': _c('gi.reflux', ('ph_monitoring',)), '91038': _c('gi.reflux', ('ph_monitoring',)),
    '91030': _c('gi.reflux', ('ph_monitoring',)),
    # Anorectal testing
    '91120': _c('gi.anorectal', ('rectal_sensation',)), '91122': _c('gi.anorectal', ('manometry',)),
    # Feeding tubes outside an endoscopy
    '43762': _c('gi.feeding_tube', ('tube_replacement',)), '43763': _c('gi.feeding_tube', ('tube_replacement',)),
    '49440': _c('gi.feeding_tube', ('peg', 'tube_placement')), '49441': _c('gi.feeding_tube', ('tube_placement',)),
    '49446': _c('gi.feeding_tube', ('tube_placement',)), '49450': _c('gi.feeding_tube', ('tube_replacement',)),
    '49451': _c('gi.feeding_tube', ('tube_replacement',)), '49452': _c('gi.feeding_tube', ('tube_replacement',)),
    # Moderate sedation by the performing physician
    '99152': _c('gi.sedation', ('moderate_sedation',)), '99153': _c('gi.sedation', ('moderate_sedation',), addon=True),
}

ENDOSCOPIC_ACTS = ('biopsy', 'hot_biopsy', 'snare', 'emr', 'ablation', 'bleeding_control', 'injection', 'tattoo',
                   'band_ligation', 'dilation', 'stent', 'foreign_body', 'decompression')
COMMON_BUNDLED = (
    ('clip', 'A clip placed prophylactically, with no bleeding treated, is not reported as a separate service; a clip '
             'that treats bleeding is read as bleeding control (internal profile rule).'),
    ('cannulation', 'Instrument passage and cannulation are part of the examination itself.'),
    ('biopsy_of_removed_lesion', 'A biopsy of a lesion that is then removed at the same session (snare, hot forceps, '
                                 'EMR) is part of the removal (internal profile rule, NCCI policy principle; NCCI is '
                                 'not connected).'),
    ('lift_injection', 'A submucosal injection made to lift a lesion for its resection is part of the resection.'),
)
ENDOSCOPIC_QUESTIONS = (
    ('extent', 'How far was the instrument advanced (the landmark reached)?'),
    ('completion', 'Was the examination completed as intended? If not, how far did it reach and why was it stopped?'),
)
PROCEDURE_EVIDENCE = ('the examination documented on the date of service (not history or plan)',
                      'each coded act (biopsy, removal, dilation ...) stated as done, at the anatomy the code needs',
                      'the technique where the code depends on it (snare vs hot forceps vs forceps)')
PROCEDURE_RULES = ('CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family '
                   '(multiple-endoscopy payment rule), PC/TC indicator',
                   'CMS practitioner MUE: units per day',
                   'Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)',
                   'Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family '
                   '(59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening '
                   'that became therapeutic (PT/33, payer rule not connected)')

CATALOGUE: dict[str, FamilyEntry] = {e.family: e for e in (
    FamilyEntry(
        'gi.office_em', 'Office / outpatient evaluation and management', SUPPORTED, ('office_em',),
        documentation=('date of service', 'setting (office or outpatient)', 'new or established patient status',
                       'the basis for the level: total time on the date of service, or the level of medical decision '
                       'making', 'on a procedure day: a significant, separately identifiable E/M stated as such'),
        acts=('em_visit',),
        bundled=(('em_routine', 'The routine history, examination and consent before a procedure belong to the '
                                'procedure (its global period), not to a separate E/M.'),),
        questions=(('setting', 'Where did the visit take place (office, hospital outpatient, telehealth)?'),
                   ('patient_status', 'Was the patient new or established to this clinician and group?'),
                   ('em_basis', 'What supports the level: total time on the date of service, or the level of medical '
                                'decision making?'),
                   ('service_date', 'What is the date of service of the visit?')),
        evidence=('a visit documented on the date of service', 'the time statement or the MDM statement the level '
                  'rests on', 'on a procedure day: the statement of a separately identifiable E/M'),
        rules=('CMS PFS presence and status for the date', 'Same-day procedure: separately identifiable E/M '
               '(modifier 25 consideration, never assigned)'),
        notes=('Office consultation codes (99242-99245) are not paid by Medicare; payer rules are not connected.',)),
    FamilyEntry(
        'gi.egd', 'Upper GI endoscopy (EGD, esophagoscopy, POEM)', SUPPORTED, ('egd', 'esophagoscopy', 'poem'),
        documentation=('the examination and its extent (esophagus only, or to the duodenum)', 'each intervention, '
                       'its anatomy and technique', 'completion, and the reason when it was not completed'),
        acts=ENDOSCOPIC_ACTS + ('peg', 'tube_placement', 'myotomy', 'fundoplication'),
        bundled=COMMON_BUNDLED,
        unsupported_acts=(('esd', 'Endoscopic submucosal dissection has no code profile here; a coder decides how it is reported.'),),
        questions=ENDOSCOPIC_QUESTIONS, evidence=PROCEDURE_EVIDENCE, rules=PROCEDURE_RULES),
    FamilyEntry(
        'gi.enteroscopy', 'Small-bowel enteroscopy (push, balloon-assisted, through a stoma)', SUPPORTED,
        ('enteroscopy',),
        documentation=('the depth reached (beyond the second portion of the duodenum; whether the ileum was reached)',
                       'each intervention, its anatomy and technique'),
        acts=('biopsy', 'hot_biopsy', 'snare', 'ablation', 'bleeding_control', 'stent', 'foreign_body', 'dilation',
              'tube_placement', 'peg', 'tube_replacement'),
        bundled=COMMON_BUNDLED, questions=ENDOSCOPIC_QUESTIONS, evidence=PROCEDURE_EVIDENCE, rules=PROCEDURE_RULES),
    FamilyEntry(
        'gi.colonoscopy', 'Colonoscopy', SUPPORTED, ('colonoscopy',),
        documentation=('the extent reached (cecum or terminal ileum for a complete examination)', 'bowel preparation',
                       'each lesion (size, site) and what was done to it (sampled, removed, untreated)', 'intent '
                       '(screening, surveillance or diagnostic)', 'completion and the reason it was not completed'),
        acts=ENDOSCOPIC_ACTS, bundled=COMMON_BUNDLED,
        unsupported_acts=(('esd', 'Endoscopic submucosal dissection has no code profile here; a coder decides how it is reported.'),),
        questions=ENDOSCOPIC_QUESTIONS, evidence=PROCEDURE_EVIDENCE, rules=PROCEDURE_RULES),
    FamilyEntry(
        'gi.flex_sig', 'Flexible sigmoidoscopy', SUPPORTED, ('flex_sig',),
        documentation=('the extent reached', 'each lesion and what was done to it', 'intent'),
        acts=ENDOSCOPIC_ACTS, bundled=COMMON_BUNDLED, questions=ENDOSCOPIC_QUESTIONS, evidence=PROCEDURE_EVIDENCE,
        rules=PROCEDURE_RULES),
    FamilyEntry(
        'gi.eus', 'Endoscopic ultrasound', SUPPORTED, ('eus',),
        documentation=('the stations examined (limited to one organ and adjacent structures, or esophagus, stomach and '
                       'duodenum)', 'the target of any fine-needle aspiration or biopsy and the passes made',
                       'any drainage or injection'),
        acts=('eus_exam', 'fna', 'injection', 'drainage'),
        bundled=(('biopsy', 'A forceps biopsy at the same upper examination is read under the upper GI family.'),),
        unsupported_acts=(('drainage', 'EUS-guided drainage other than of a pseudocyst (biliary, gallbladder, '
                                       'gastroenterostomy) has no profiled code.'),),
        questions=(('target', 'What was examined, and what (if anything) was sampled with the needle?'),),
        evidence=('the endosonographic examination on the date of service', 'the needle sampling and its target',
                  'the stations examined (whether the examination was limited or full is the reviewer\'s to judge; '
                  'this catalogue does not check it)'),
        rules=PROCEDURE_RULES),
    FamilyEntry(
        'gi.ercp', 'ERCP', SUPPORTED, ('ercp',),
        documentation=('cannulation (which duct, success or failure)', 'each intervention (sphincterotomy, stone '
                       'removal, stent placement, dilation, cholangioscopy, lithotripsy)', 'stents placed (number, '
                       'duct)'),
        acts=('biopsy', 'sphincterotomy', 'stone_extraction', 'lithotripsy', 'cholangioscopy', 'stent',
              'stent_removal', 'stent_exchange', 'dilation', 'ablation', 'pressure_measurement'),
        bundled=(('cannulation', 'Cannulation and contrast injection are part of the ERCP itself.'),
                 ('injection', 'Contrast injection during ERCP is part of the examination.'),
                 ('clip', COMMON_BUNDLED[0][1])),
        questions=(('cannulation', 'Was the intended duct cannulated, and which interventions were done?'),),
        evidence=PROCEDURE_EVIDENCE,
        rules=PROCEDURE_RULES + ('Radiological supervision and interpretation is a separate service; where the '
                                 'document attributes it to a radiologist it is not the endoscopist\'s',)),
    FamilyEntry(
        'gi.capsule', 'Capsule endoscopy (small bowel, esophagus, colon)', SUPPORTED, ('capsule',),
        documentation=('the capsule study and its segment (small bowel, esophagus or colon)', 'the physician '
                       'interpretation and report', 'recording completeness (whether the capsule reached the '
                       'colon / was excreted)'),
        acts=('capsule_study',),
        questions=(('interpretation', 'Who interpreted the capsule recording, and on which date?'),),
        evidence=('the capsule study and its interpretation by the physician on the date of service',),
        rules=('CMS PFS PC/TC indicator: in a facility setting the professional component is reported with modifier '
               '26 (consideration from the connected PFS file; never assigned)', 'CMS practitioner MUE')),
    FamilyEntry(
        'gi.motility', 'Motility and manometry (esophageal, gastric, duodenal, colonic)', SUPPORTED, ('manometry',),
        documentation=('which study (esophageal manometry, antroduodenal, colonic)', 'the recording and the '
                       'physician interpretation', 'provocative stimulation or perfusion, when done'),
        acts=('manometry',),
        questions=(('interpretation', 'Who interpreted the study, and was it a complete recording?'),),
        evidence=('the study performed and interpreted on the date of service',),
        rules=('CMS PFS PC/TC indicator (modifier 26 consideration in a facility setting)', 'CMS practitioner MUE')),
    FamilyEntry(
        'gi.reflux', 'pH and impedance monitoring', SUPPORTED, ('ph_study',),
        documentation=('the method (catheter pH, wireless pH capsule, impedance)', 'the recording duration',
                       'the physician interpretation'),
        acts=('ph_monitoring',),
        bundled=(('capsule_study', 'A wireless pH capsule is part of the pH study, not a capsule endoscopy.'),),
        questions=(('method', 'Which method was used (catheter pH, wireless pH capsule, impedance) and for how long?'),),
        evidence=('the recording and its interpretation',),
        rules=('CMS PFS PC/TC indicator (modifier 26 consideration in a facility setting)', 'CMS practitioner MUE')),
    FamilyEntry(
        'gi.anorectal', 'Anorectal testing (manometry, sensation and compliance)', SUPPORTED, ('anorectal_testing',),
        documentation=('anorectal manometry', 'rectal sensation, tone and compliance testing', 'the physician '
                       'interpretation'),
        acts=('manometry', 'rectal_sensation'),
        unsupported_acts=(('balloon_expulsion', 'A balloon expulsion test has no profiled code of its own here; it '
                                                'is listed for the reviewer.'),),
        questions=(('interpretation', 'Which anorectal tests were performed and interpreted?'),),
        evidence=('each test performed and interpreted on the date of service',),
        rules=('CMS PFS PC/TC indicator (modifier 26 consideration in a facility setting)', 'CMS practitioner MUE')),
    FamilyEntry(
        'gi.feeding_tube', 'Feeding-tube procedures (gastrostomy and jejunostomy placement and replacement)',
        SUPPORTED, ('feeding_tube',),
        documentation=('placement or replacement', 'the route (endoscopic, percutaneous with imaging, bedside '
                       'replacement)', 'whether the tract needed revision'),
        acts=('peg', 'tube_placement', 'tube_replacement'),
        questions=(('route', 'Was the tube placed endoscopically, percutaneously with imaging, or replaced at the '
                             'bedside, and was the tract revised?'),),
        evidence=('the placement or replacement on the date of service, and its route',),
        rules=('CMS PFS presence and status for the date', 'CMS practitioner MUE'),
        notes=('A PEG placed during an EGD is reconciled under the upper GI family (its own EGD code).',)),
    FamilyEntry(
        'gi.sedation', 'Moderate sedation by the performing physician', RECOGNISED, ('sedation',),
        documentation=('who provided sedation (the endoscopist, or a separate anesthesia professional)',
                       'intraservice time when the endoscopist provided moderate sedation'),
        acts=('moderate_sedation',),
        notes=('Anesthesia by a separate professional is that professional\'s service and is never coded for the '
               'endoscopist; moderate sedation is recognised and listed, not reconciled.',)),
    FamilyEntry(
        'gi.other', 'Other GI services (anoscopy, hemorrhoid banding, rigid proctosigmoidoscopy, liver biopsy, '
                    'paracentesis, breath tests, elastography)', RECOGNISED, (),
        documentation=(), acts=(),
        notes=('Recognised and listed for review; no service profile reconciles them in this release.',)),
)}

UNSUPPORTED_SERVICES = (
    ('Endoscopic submucosal dissection (ESD)', 'no code profile in this catalogue; no code is proposed or checked for it, and a coder decides how it is reported (the CPT code set is not connected)'),
    ('Endoscopic suturing and endoscopic bariatric procedures (sleeve gastroplasty)', 'not profiled'),
    ('EUS-guided drainage other than of a pseudocyst (biliary, gallbladder, gastroenterostomy)', 'not profiled'),
    ('Gastric peroral endoscopic myotomy (G-POEM) and flexible Zenker diverticulotomy', 'not profiled'),
    ('Endoscopic necrosectomy', 'not profiled'),
    ('Anal and pelvic-floor EMG, biofeedback', 'outside the GI code ranges profiled here'),
    ('Unlisted GI procedures (43499, 43999, 44799, 45399, 91299)', 'unlisted codes are never reconciled'),
)

# Acts that never need a code of their own, whatever the family (handled by reconciliation rules).
NOT_REPORTED = frozenset(('clip', 'cannulation'))
# Acts no profile reconciles: an act of these kinds documented as done is listed as unsupported, never as covered.
UNSUPPORTED_ACTS = frozenset(('esd',))


def code_profile(code: str):
    return CODES.get(code)


def entry(family: str):
    return CATALOGUE.get(family)


def coverage_matrix() -> list[dict]:
    """The catalogue as rows (one per family) for the API, the reports and COVERAGE.md."""
    rows = []
    for family, e in CATALOGUE.items():
        codes = sorted(code for code, p in CODES.items() if p.family == family)
        rows.append({'family': family, 'label': e.label, 'support': e.support, 'documentation': list(e.documentation),
                     'acts': list(e.acts), 'bundled': [{'act': a, 'why': w} for a, w in e.bundled],
                     'unsupported_acts': [{'act': a, 'why': w} for a, w in e.unsupported_acts],
                     'questions': [{'fact': f, 'question': q} for f, q in e.questions],
                     'evidence': list(e.evidence), 'rules': list(e.rules), 'notes': list(e.notes),
                     'codes_reconciled': codes})
    rows.append({'family': 'unsupported', 'label': 'Named unsupported services', 'support': UNSUPPORTED,
                 'documentation': [], 'acts': [], 'bundled': [], 'unsupported_acts': [], 'questions': [],
                 'evidence': [], 'rules': [], 'notes': [f'{name}: {why}' for name, why in UNSUPPORTED_SERVICES],
                 'codes_reconciled': []})
    return rows


def render_markdown() -> str:
    """COVERAGE.md, generated from this catalogue (tests/test_services_reconcile.py keeps the file in step)."""
    lines = ['# CPT Studio — GI coverage catalogue', '',
             f'Generated from `studio/gi/catalogue.py` ({CATALOGUE_VERSION}); do not edit by hand. One GI workspace, '
             'one upload flow and one combined results screen: these families are internal profiles, never '
             'navigation.', '',
             'Support levels: **supported** — the documented-service reader reads the family\'s services and acts, '
             'and the catalogue reconciles them with provider-selected codes, with regression documents; '
             '**recognised** — listed for review, not reconciled; **unsupported** — named so a result can say so.', '',
             'The code lists are internal reconciliation profiles (which documented act a code accounts for). They are '
             'not a CPT reference and carry no descriptors; CPT code-set membership, NCCI procedure-to-procedure edits '
             'and payer policies are not connected, so they stay not verified. No coverage claim is an accuracy claim: '
             'accuracy needs independently adjudicated cases.', '']
    lines += ['| Family | Support | Acts reconciled | Codes reconciled |', '|---|---|---|---|']
    for row in coverage_matrix():
        acts = ', '.join(row['acts']) or '—'
        codes = ', '.join(row['codes_reconciled']) or '—'
        lines.append(f'| {row["label"]} (`{row["family"]}`) | {row["support"]} | {acts} | {codes} |')
    for row in coverage_matrix():
        lines += ['', f'## {row["label"]} — {row["support"]}', '']
        for title, key in (('Required documentation', 'documentation'), ('Verification evidence', 'evidence'),
                           ('Rule checks', 'rules'), ('Notes', 'notes')):
            if row[key]:
                lines.append(f'**{title}:**')
                lines += [f'- {item}' for item in row[key]]
        if row['questions']:
            lines.append('**Clarification questions (asked together, when not documented):**')
            lines += [f'- `{q["fact"]}`: {q["question"]}' for q in row['questions']]
        if row['bundled']:
            lines.append('**Not separately reported (internal profile rules):**')
            lines += [f'- `{b["act"]}`: {b["why"]}' for b in row['bundled']]
        if row['unsupported_acts']:
            lines.append('**Unsupported within the family:**')
            lines += [f'- `{u["act"]}`: {u["why"]}' for u in row['unsupported_acts']]
    return '\n'.join(lines) + '\n'
