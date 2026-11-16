"""Step 3c of design v2 (docs/gemini-migration/FINAL-V2.md 4.8, 5.6; DECISIONS D181, D182): interpretation/wording.py's
additive part - the five new question facts (NEW_FACTS, MISSING), quote_span (the design's wording.quote(span)), and the
message ids with their question and explanation builders. Text-only and synthetic: no database, no network.

What is proved here:
- v1's wording is unchanged: every v1 function, class and constant of the module has the source it had at the base
  commit (V1_PINS, sha256 of each top-level definition's source), and NEW_FACTS and MISSING keep v1's seven entries;
- D181: the five new facts join NEW_FACTS and MISSING with their sentences verbatim, and so customer_api.FACT_WORDS;
- quote_span slices the revision by spans only, in document order, merging overlaps, refusing a span past the text;
- every message id has a sentence: each builds a question and a reason from its fixture, and every item
  engine/requirements.RULES can raise (rank, fact key, question or explanation) has a message id of that rank, key and
  kind;
- build refuses (never a fallback sentence) a missing slot, a quote with no words, a span past the text, an untyped slot
  and slots that contradict the message;
- no sentence names a provider or model (customer_api.FORBIDDEN and the customer denylist's hard patterns), carries a
  held fact's cause, or quotes anything but the document's own words;
- the copies of v1's words (assess, classes, coverage, ercp, events, checks, mapping, derive) equal their originals;
- D225 (repair r3c; refute-4a-r2 P5, P6, P7, P10, P11): each new id's exact text in every form its slots allow, its
  refusals of slots that contradict it, and its tables (ATTRIBUTE_PHRASES over every Attribute, ROUTE_WORDS over every
  Approach, the exchange reasons copied from ercp.exchange_question) - D225Items;
- repair r3c's second round (refute-r3c-r1 P1, P2, P3, P6, P7): a session's attribute is worded about the session (its
  service), never the act the item names, which only keys the fact; the sides are quoted beside the act's own sentence;
  every attribute's sentence and every route in its exact text; the act's label never states the contested value; the
  module's docstring names the engine import it makes - D225Round2;
- D246 (repair r3c; the lead's L1, refute-5c-r2 R2-03, r4a Q4 and R4): BASE_INCLUDED's codes form (no act in doubt) and
  SEPARATE_EM's (no same-day act to list), each naming the codes as proposed only; DOUBT, SAME_DUCT and STATEMENT_SCOPE
  naming an act or a statement with no units without a quote (D160 (3)); the new id SYNTHETIC_ACT (rank 2,
  performed_status, a question) naming a synthetic act's own kind and quoting its own unit - each in its exact text, the
  earlier forms unchanged beside them, the refusals that stay, the customer scan over every new sentence - D246Forms;
  and the engine's own unit-less items worded (D246EngineItems);
- D254 (repair r3c of round w8r): rule 1 - each message's needs name only slots every item carries by construction
  (CARRIED), and for every Message, every combination of present and absent slots its builder reads (recorded, and
  proved the only slots that change its words), with values from the slots' own types, builds a non-empty question and
  reason fit for the customer; every value of every slot read is worded; only a missing carried slot or a binding
  failure is refused (D254Total); the six refusing shapes of the lead's VERIFY.md, assessed by the engine, word from the
  slots the renderer gives them today (D254SixShapes); rule 2 - an act no kind names is 'another act', its article
  included, wherever a kind is turned into words (D254AnotherAct); rule 3 - ENTEROSCOPY_APPROACH without an approach names
  no route, and BASE_INCLUDED, BASE_EXPLAINED and SEPARATE_EM have a true form with nothing to name; every route is named
  (D254Rule3); each builder worded through the act's article is still v1's sentence for every named kind
  (ThroughTheActEqualsV1);
- D257: BASE_WITHIN names the whole by its own family, never an EUS it is not, and a whole only possibly done as
  possibly performed (D257BaseWithin); D258: UNLISTED_SCOPE's entry and words, never "in doubt" or a denial
  (D258UnlistedScope); D253 QX (ii): ENTEROSCOPY_THROUGH asks only the anatomy passed through (D253EnteroscopyThrough);
  D255: no codes-form test rests on an add-on pair (D255AddOnPairs);
- D266 (repair r3c of round w9r; refute-r3c-r1 F3): DOUBT words an unlisted DENIAL - carded or not, of kind snare or
  none, and every other kind - as a statement that the act was not done, quoting the denial, never "leaves ... in doubt";
  through the renderer's own call over the engine's items for F3's probe shapes (D266DenialForm); UNLISTED_SCOPE and
  DOUBT have a true form with no quote of the examination for a Fill that gives none (D266NoQuote);
- D267: BUNDLED with a group that names no act (() or (OTHER,)) words the code itself (D267Bundled); a route the Fill
  marks as only possible (the new optional Slots field possible_approaches) is worded as possible, never "the documented
  pouch" or "the documented stoma" (D267PossibleRoute); customer_api.held_fact_words' half is in
  tests/v2/test_update_customer.py (D267HeldFactWords).
"""
import ast
import functools
import hashlib
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from studio import customer_api
from studio.interpretation import wording
from studio.interpretation.contract.types import (Approach, Attribute, Device, Extent, Kind, Landmark, Owner,
                                                  SessionKind, Span, Station, Tract, UnlistedWhat)
from studio.interpretation.engine import requirements
from studio.interpretation.engine.catalogue import EnteroscopyClass, EusClass, SiteClass, TechniqueClass
from studio.interpretation.engine.types import ItemKind

ROOT = Path(__file__).resolve().parents[2]
WORDING = ROOT / 'studio' / 'interpretation' / 'wording.py'
DENYLIST = json.loads((ROOT / 'ops' / 'verification' / 'customer-denylist.json').read_text(encoding='utf-8'))
HARD = [re.compile(item['source'], re.ASCII | re.IGNORECASE) for item in DENYLIST['patterns']
        if item['severity'] == 'hard' and 'json' in item['surfaces']]
M = wording.Message

V1_PINS = {
    'ACT_LABELS': '528fd6ff6d133ba97605c62971068da40ab7abaee14af2fdd589bb42c966330c',
    'BUNDLING_QUESTIONS': '9df6ca2ac7a84bf61820a94dcbe40a35fb1fd003527f259d529016b2eadd22c6',
    'CONTEXT_SOURCE': '7a296c36d7adafb3ce7dfa4fee3e57f9d58c6bc42d30c216502535ce93a70a64',
    'COVERAGE_SOURCE': '47796f098e1eec469cbb19a8009698d378784667c27754a2672ba9085c7ab02d',
    'EM_FAMILIES': '6deee2875fa842c2fa847dad338ec3e5333b141fe80bfedc4d325c9201cd815b',
    'EM_SOURCE': '537dea3f1c34aaf738877d851395d759bab2fc62fbb85a330d770851b05cfbb3',
    'EVENTS_SOURCE': 'd85459772903c98831eb73b502083cd918fe8f3370ba10ef03d4b6be7b6ff12c',
    'EVENT_LABELS': 'ae7ead0580305e54160e3206060fcf319e9a5cf513de4b899bc7c2f9266ebad1',
    'EXAMINATION_CLASS_CHECK': '5f679892c0112e35dfbea044f563b62dc08ba17a5f30813aac53827bf80e5599',
    'EXAMINATION_CLASS_WORDS': '6e58f9b82aa356936d35ce1e50e6c5b0af6fc57d2c1395640bf772631ca1e3ad',
    'EXCERPT_CHARS': 'b67ce29481f4f9db7932ab538fceca87b0f34d30c5c06fd21d28525a3279ce6e',
    'MAX_LISTED_CODE': 'd2869e9482e39e11bb1fee0af6af5bd5bc8d6b4b2f83dd1daca9e6923e591420',
    'MEMBER_ANSWER_CHECK': 'ca5b35820f74e7b9deff07e580f47be9711d953257e9a9a3e6e86b82e4fefc90',
    'MEMBER_ANSWER_LABELS': 'b14e1c49e5ceeceef5c1f2d9d4e0cef94aaee975473897aff245aece3037a2e4',
    'MEMBER_ANSWER_SOURCE': '774c5de4a9d3f09393aad4c7d5134373b5d3f021beaa4b3c1f3b1e4313f6a034',
    'MEMBER_ENTERED': 'ec8254bc90d19a6cff47516b26f8648b79e205a2a6a78fb8dd1d385e7175b83a',
    'NOT_APPLIED': '468030ba2fc7d3de6bbba1559cbaf925cfc74f6c1eadf10853e47dc3e21aa833',
    'NO_EVIDENCE': '46aca430f182bbd5e97a617d076b6f587a77825c58ecae77dbad904a94611861',
    'OVERLAY_READ': '9dea83210ab358b9f087c4bca801ef79fc8df9f6d54694ea59a71db1d0ed7a1b',
    'PROPOSAL_DATE_CHECK': '7bb277edfad46dd12e69301e8d243e43821bf54733fda453e886f7830ec3f780',
    'PROVIDER_SOURCE': '1d5b39f085521dc05c1291263759ac9556ac4fa57793967bbe9faa0030a7752a',
    'SEPARATE_EM_CONSIDERATION': '88c8b3672d6a9b5b70780d10e21a633898558d7c73795b1f3a4a99c5377a77d1',
    'SERVICE_LABELS': 'bfa357d4f32bc6f3c9d7d6c3a43236ee3c504f76f0067ce7e12d4a48f803f0b4',
    'SITE_WORDS': 'c9fcd121a46f33ef52c391d42dfa90af1fe74fb70538e83c540d1be3da65527c',
    'SOURCE': 'b4749feec336f8d841f2357a9fe7d915f6dba6e58874e261c1444bddb4061dcb',
    'STATE_PHRASES': '57c373b7ac44ce30ccef778acb1ac451ee0db66b272b721ac38b06890e3065a2',
    'STATUS_SOURCE': '92c0178c7f03e421567a6726ca15d15a037e03aa142d30faf2502d5065c9d797',
    'TECHNIQUE_WORDS': 'e9ab1c37026d3b295caf152b3cb75d1ed696fa0c7062c7f07720e2d5c7bf1a7d',
    'UNKNOWN_DATE_NOTE': '4bfb03a156c32b197c90acfc43640e87b63124eebb46faafacf13b93f721fa54',
    '_listing': '63f6d2f03e1a246206f6012ebc2fa45c60009ec385d706a7a3c749cda3dafbef',
    'act_included': '7accfa270ad64649acb06a8412a7c8de99a4e3fbec83d3dddf238f3ae3b3ad2b',
    'act_label': '664f1018f1063c1ad9ce2ecd7995df2e81961b9de43c883c7cdac928dccb1b89',
    'alternative_note': 'c4a1a7e1215e0c244dbc3cf25ee0e542ec5edd1983491bfcc1092a8866c50ab2',
    'alternative_rationale': '87db8918571a9d9bbfe8d820d86cb17ae55d3752fb70acef97beec1fcdcbc63a',
    'another_site': '02c96b94352ab7be60372fe9fa9ede09cc3e8717451cc3a087c22b7b2222dad6',
    'another_technique': '75ac29507d06ea102990a659242302ea5a9597d49877d73e167025262006fed9',
    'answered_fingerprint': '5bcdc4196d865e120f4641da886de72c61dede5bb101e4b15b5d3a06ee216c83',
    'attempted_question': 'f9690a8e3837c6e4f98c053dbce594edea48bf6ef417f7056deb102559b30de0',
    'attempted_reason': '975f1bbc4a24b466dcaa435af56922bb5efad39c98e788d2f9a5e2d146e650d6',
    'bundling_question': '986c501666c20dd4450532c8f05ffc756c9ef02b0d32cb49b2486ba6fd3dd67d',
    'bundling_reason': '1659e69c63517a3e234b9dad5e1afe999462f174c0bf067cac942dcac9dc501b',
    'conflict_question': '8b2a853c76a5edb0274aa43e0966d57bf7a5e879a4d1e9e92a8bb8d38e8f5610',
    'conflict_reason': '47a64cd04d2e6e7d700f425d2a57c7cff6efb348c348c1ce1205cd9f172f399d',
    'defining_target_hold': 'b136153f06b1848fe9e6617619020dfda58bb529490f63a29846a6949b41e339',
    'doubt_question': '0e550bc937972039816656a5f9d881cc4c49fa8d0c174f3dab48507fd61386fc',
    'doubt_reason': '29096fff6fc52fccd9a233cb4f29d93d54ccf9f05547e1405f7089f0c3cb0fdc',
    'event_kind_label': 'b20b57c30207e322a7078d1ee776919a96e8ac7b9d49f7b67e9045e550963d89',
    'examination_class_hold': '14b9aadceceb4a497e36d63c66df3b816a6d264fbaecb3711ab3e1566353a3d5',
    'excerpt': 'e7e1bb282972641cb4f3beb2f0f37e129d115b4f59e755dec4b08fff4d6f81e6',
    'exclusion_reason': '1b59ada7303f0b90df781292aabe411ff6203a0de88015dd413e687c34b2256a',
    'family_label': '14c1d29cb1f2864a77028f25ad2edcfe634cb656046f10df528073b4bae3e896',
    'global_days_note': '41a947ca75d6fa98a403e38835532ee7400ed36af44c9eacc728b43f40b0f57b',
    'incomplete_check': '22ad067c43706dd6e0b1ee56d8eefe091185709b8fb7f1c4cf3c1b941be0c960',
    'incomplete_consideration': 'c9297fa2a6d1baf4af7d1cb2e4f90d777396782cfb98daa033bc71837bb5647c',
    'join': '235d99863f15c2b2fdc24bf3af016c19deaefda96091bbe7ecb229d7c758fa2a',
    'kind_label': 'a4c823ce0f60248347f3f1a7aae4748e0a4004832a2ce5f4054e26c03cbaedc0',
    'landmark_label': 'a8cbc690a4a34347fe40a37a4777e869d600a03277f967d27a5b0c63ddf5f467',
    'member_answer_reason': 'e11d6952c2808a3060e28930415a57d31cf83bf0ac8923d1c082782fdd1ea689',
    'method_question': '3c33bdcf651a89b232786e5226b4f98e72ea7efea296c192a21d1a3243aca4f0',
    'method_reason': 'df10e2ab94615a6cae5dd9da6913c01627961c72f2ae29fe8f13386b63d0f679',
    'not_documented_reason': 'dcc7a1b63990c88d581295373de180d3ee8cbc620e371cbf713362a1a3ee73e1',
    'not_linked_reason': '1de70ba26541b71839fd43eb12e36518197f95c906f257c5f12b787dd468fc86',
    'performed_question': 'df05d9cb79072f88980057385447a22d7d8aba373c0795ff825a3bc38b6a2862',
    'performer_question': 'f23c0a2a25513eb9be373ec6270d467b7d6bbe34f4c6c7443e1f68543ceb31f6',
    'performer_reason': '78b86642b5aaeee02b91d73d99f0a2d1a33898ed3a0646a4565fb62ec47dfb71',
    'plural': 'bc79bf8fddaf1ce8330a914f6decb2769fb11a8f3b8e545a8f8fe31cb28d265e',
    'procedure_question': '91baacddf93c53eadcac9ca6a61c8b57e275fcc63cc1007f482c3d883d8a093b',
    'procedure_reason': '83b2c23669bb37f00cb5c9368a4633a049f647805a719f2c9b7a8557e0f02fc9',
    'quote': 'c5dfd701271832b9a73ba60ffec3eacda54c221da4738162e0ef49607a3a77b6',
    'response_problems': 'f7c969658ef60610524246860434a910956edb79519f318ba1e31745e74d9a01',
    'scope_question': '1ead75ab6723087f8e2c4cee932a71b1610492fa57ea4018833c7d945c45add3',
    'scope_reason': '64a1d707d2eae9d8b05a60105a0a522072246977768630f634cc6c0331b059c6',
    'selected_rationale': 'ce8ca2c4d48ca3787745ded2aa2c3dee2e3e477e8cb7877dc8a3620f0ebd3be7',
    'service_name': 'c3c1efaa0a765a124b023dfafb6abb185187ed0ae2eae932a46a0040ad74be08',
    'session_question': '2f6161bd833d29abf3c37817743400aca7af79674f492adbcd4a18c1311214b5',
    'site_reason': 'f452b3053fba8f1df041e02fb92d89be7aaff24ed1827d847a657d09774cc237',
    'status_question': 'df24e89634acbf3f432792fad1bfc5de49358d9ccc19ed5b12e54728759b6a75',
    'status_reason': 'aeea91252a5eea220f3616f43adadc3925d61676e010fac2a9f82705aa8faf06',
    'target_question': 'e0470f4612d1246b551ca5fe240c852714c9a39dd3c3d68d7938480a8ddb5f89',
    'target_reason': '783c1b548a1478a5b8b3792c99b175af85a45428365134ed331e1a8cd08dff93',
    'technique_question': 'd7f1fe51338cb23c382b5bb6fe1367d5bbeaa80b73930e83cbd0b70b74275733',
    'technique_reason': '06b75cd0a5aef20fcf87bc75b86de1f01ee8b7b1857e2d27a2db596254e47bb0',
    'technique_unresolved_reason': '55481091d564ac7d1ce99b0e65d75ac799d5f8ff6456264b6264629d492c6540',
    'time_question': 'd0c6390c85f50fea69be4607961dc112f9ac2e1a46c1c230e1b3bb28f4638e02',
    'time_reason': '91b911b9c3a0844af7b38ddb4a39e8d8f6dabae44c3c15e2fad60d07246dffae',
    'unavailable_reason': '8e79734080e275b9f3198ec222ef1ae5ba835aacc4d0c4a63ac250c88d4231ad',
    'unlisted_codes': 'b8ed63329be1a580d564e69e52e00e204b86dc07155931a3c81ce2b9cb99aab6',
    'unlisted_codes_check': '96e67554cd840ccfc9c2a7fdbde1d31d624adb48c0a4278cac5a055d89f05929',
}
# v1's seven new facts and their sentences, as the base commit holds them (DECISIONS D181 appends five after them)
V1_NEW_FACTS = ('event_time', 'event_performer', 'act_target', 'technique', 'statement_scope', 'act_method', 'procedure')
V1_MISSING = {
    'event_time': 'whether the act was done at this encounter',
    'event_performer': 'who performed the act',
    'act_target': 'which lesion or site the act was done on',
    'technique': 'which technique was used',
    'statement_scope': 'whether a statement in the document applies to this act',
    'act_method': 'by which method the lesion was removed',
    'procedure': 'in which procedure the act was done',
}
# DECISIONS D181 (and FINAL-V2 4.8), verbatim
D181 = {
    'event_entry': 'whose entry the act is told in',
    'exam_stations': 'which parts of the upper tract were examined',
    'act_yield': 'what the extraction retrieved',
    'act_cause': 'what caused the bleeding the act treated',
    'act_part': 'whether the act was part of another act',
}

TEXT = ('A cold snare polypectomy of the 6 mm sigmoid polyp was performed. No polyp was removed from the rectum. '
        'Biopsies were taken from the polyp base. Nursing note: clip placed at the polypectomy site. '
        'The scope was advanced to the cecum. EUS imaging was performed from the stomach. '
        'The old stent was removed and a new stent was placed. Balloon sweeps retrieved no stones.')


def sp(phrase):
    start = TEXT.index(phrase)
    return (Span(start, start + len(phrase)),)


ACT = sp('A cold snare polypectomy of the 6 mm sigmoid polyp was performed.')
DENIAL = sp('No polyp was removed from the rectum.')
BIOPSY = sp('Biopsies were taken from the polyp base.')
CLIP = sp('clip placed at the polypectomy site.')
REACH = sp('The scope was advanced to the cecum.')
EUS = sp('EUS imaging was performed from the stomach.')
REMOVAL = sp('The old stent was removed')
PLACED = sp('a new stent was placed.')
SWEEP = sp('Balloon sweeps retrieved no stones.')
BASE = dict(code='45385', act=Kind.SNARE, device=Device.COLD_SNARE, words=ACT, family=SessionKind.COLONOSCOPY,
            group=(Kind.SNARE,))
EUS_BASE = dict(code='43242', act=Kind.EXAMINATION, words=EUS, family=SessionKind.EUS)
ENT_BASE = dict(code='44376', act=Kind.EXAMINATION, family=SessionKind.ENTEROSCOPY, words=REACH, reached=Extent.ILEUM)

# One synthetic fixture per message id: the slots the engine would fill for it.
FIXTURES = {
    M.CONFLICT: {**BASE, 'statements': (DENIAL,)},
    M.CONFLICT_FACT: {**BASE, 'statements': (ACT, DENIAL)},
    M.DOUBT: {**BASE},
    M.STATEMENT_SCOPE: {**BASE, 'statements': (DENIAL,)},
    M.STATUS: {**BASE},
    M.NOT_DOCUMENTED: {**BASE},
    M.ATTEMPTED: {**BASE},
    M.UNPROFILED: {'code': '0001U'},
    M.NOT_LINKED: {'code': '43999'},
    M.RECOGNISED_ONLY: {'code': '99152', 'family': SessionKind.SEDATION},
    M.UNRECONCILED: {'code': '46221'},
    M.ENTRY: {**BASE},
    M.ANOTHER_ENTRY: {**BASE, 'act': Kind.CLIP, 'words': CLIP, 'group': (Kind.CLIP,), 'owner': Owner.NURSING},
    M.TIME: {**BASE},
    M.TIME_BESIDE_VISIT: {**BASE},
    M.PERFORMER: {**BASE},
    M.PROCEDURE: {**BASE},
    M.ANOTHER_TRACT: {**EUS_BASE, 'tract': Tract.LOWER, 'required_tract': Tract.UPPER, 'place': Landmark.RECTUM},
    M.ENTEROSCOPY_ROUTE: {**ENT_BASE, 'code': '44380', 'enteroscopy_class': EnteroscopyClass.STOMA,
                          'approaches': (Approach.THROUGH_STOMA,)},
    M.ENTEROSCOPY_APPROACH: {**ENT_BASE, 'enteroscopy_class': EnteroscopyClass.ILEAL,
                             'approach': Approach.THROUGH_STOMA, 'approach_words': REACH},
    M.METHOD: {**BASE, 'act': Kind.REMOVAL, 'lesion': sp('6 mm sigmoid polyp')},
    M.TECHNIQUE: {**BASE, 'code': '45386', 'act': Kind.DILATION, 'device': None, 'technique': TechniqueClass.BALLOON},
    M.STATED_TECHNIQUE: {**BASE, 'act': Kind.DILATION, 'device': None},
    M.ANOTHER_TECHNIQUE: {**BASE, 'code': '43249', 'act': Kind.DILATION, 'family': SessionKind.EGD,
                          'technique': TechniqueClass.BALLOON, 'stated': TechniqueClass.WIRE_BOUGIE},
    M.ROUTE: {**EUS_BASE, 'code': '43253', 'act': Kind.INJECTION},
    M.WALL_INJECTION: {**EUS_BASE, 'code': '43253', 'act': Kind.INJECTION},
    M.ACT_TARGET: {**BASE},
    M.SITE: {**BASE, 'code': '43249', 'act': Kind.DILATION, 'site': SiteClass.ESOPHAGEAL},
    M.ANOTHER_SITE: {**BASE, 'code': '43249', 'act': Kind.DILATION, 'family': SessionKind.EGD,
                     'site': SiteClass.ESOPHAGEAL, 'place': Landmark.DUODENUM},
    M.DUCT: {**BASE, 'code': '43276', 'act': Kind.STENT_REMOVAL, 'device': None, 'words': REMOVAL,
             'whole': Kind.STENT, 'whole_words': PLACED},
    M.TARGET: {'family': SessionKind.EUS},
    M.STRUCTURE: {**EUS_BASE, 'code': '43240', 'act': Kind.DRAINAGE},
    M.ANOTHER_STRUCTURE: {**EUS_BASE, 'code': '43240', 'act': Kind.DRAINAGE, 'place': Landmark.GALLBLADDER},
    M.STATIONS: {**EUS_BASE, 'stations': (Station.STOMACH,)},
    M.STATION_CLASS: {**EUS_BASE, 'denied': (Station.DUODENUM,)},
    M.EXTENT: {'family': SessionKind.COLONOSCOPY},
    M.EXAMINATION_CLASS: {**EUS_BASE, 'code': '43237', 'exam_class': EusClass.LIMITED, 'reached': Extent.DUODENUM},
    M.ENTEROSCOPY_CLASS: {**ENT_BASE, 'enteroscopy_class': EnteroscopyClass.JEJUNAL},
    M.YIELD: {**BASE, 'code': '43264', 'act': Kind.STONE_EXTRACTION, 'device': None, 'words': SWEEP},
    M.NOTHING_RETRIEVED: {**BASE, 'code': '43264', 'act': Kind.STONE_EXTRACTION, 'device': None, 'words': SWEEP},
    M.CANNULATION: {'family': SessionKind.ERCP},
    M.PART: {**BASE, 'code': '45380', 'act': Kind.BIOPSY, 'device': None, 'words': BIOPSY, 'whole': Kind.SNARE,
             'whole_words': ACT, 'bundling': wording.Bundling.BIOPSY_OF_REMOVED_LESION},
    M.BUNDLING_TARGET: {**BASE, 'code': '45380', 'act': Kind.BIOPSY, 'device': None, 'words': BIOPSY,
                        'whole_words': ACT, 'bundling': wording.Bundling.BIOPSY_OF_REMOVED_LESION},
    M.CAUSE: {**BASE, 'code': '45382', 'act': Kind.CLIP, 'device': None, 'words': CLIP, 'whole': Kind.SNARE,
              'whole_words': ACT},
    M.BUNDLED: {**BASE, 'code': '45380', 'act': Kind.BIOPSY, 'device': None, 'words': BIOPSY, 'group': (Kind.BIOPSY,),
                'bundling': wording.Bundling.BIOPSY_OF_REMOVED_LESION},
    M.EM_BASIS: {'family': SessionKind.OFFICE_EM},
    M.SEPARATE_EM: {**BASE, 'code': '99213', 'listed': (Kind.SNARE,), 'possible': (Kind.BIOPSY,)},
    M.SEPARATE_EM_DENIED: {**BASE, 'code': '99213', 'words': DENIAL},
    M.BASE_INCLUDED: {**BASE, 'code': '45378', 'listed': (Kind.SNARE,)},
    M.BASE_EXPLAINED: {**BASE, 'code': '45378', 'codes': ('45385',)},
    M.BASE_WITHIN: {**BASE, 'code': '43235', 'family': SessionKind.EGD, 'codes': ('43237',)},
    M.COMPETING: {**BASE, 'codes': ('45384',)},
    M.SETTING: {'family': SessionKind.OFFICE_EM},
    M.PATIENT_STATUS: {'family': SessionKind.OFFICE_EM},
    M.SERVICE_DATE: {},
    # D225 (repair r3c)
    M.CONFLICT_ATTRIBUTE: {**BASE, 'attribute': Attribute.DATE_RELATION, 'statements': (ACT, DENIAL)},
    M.UNLISTED_EVIDENCE: {'code': '45385', 'unlisted_what': UnlistedWhat.DOUBT, 'unlisted_kind': Kind.BIOPSY,
                          'statements': (DENIAL,)},
    M.EXAMINATION_ROUTE: {**EUS_BASE, 'code': '44406', 'exam_class': EusClass.STOMA, 'words': REACH,
                          'reached': Extent.CECUM},
    M.EXAMINATION_APPROACH: {**EUS_BASE, 'code': '44406', 'exam_class': EusClass.STOMA, 'words': REACH,
                             'approach': Approach.TRANSANAL},
    M.SAME_DUCT: {**BASE, 'code': '43274', 'act': Kind.STENT_REMOVAL, 'device': None, 'words': REMOVAL,
                  'whole': Kind.STENT, 'whole_words': PLACED},
    M.STRUCTURE_PLACE: {**EUS_BASE, 'code': '43240', 'act': Kind.DRAINAGE, 'place': Landmark.GALLBLADDER},
    # D246 (repair r3c)
    M.SYNTHETIC_ACT: {'code': '43274', 'act': Kind.STENT_REMOVAL, 'words': REMOVAL},
    # D258, D253 QX (ii) (repair r3c of round w8r)
    M.UNLISTED_SCOPE: {'code': '45378', 'act': Kind.EXAMINATION, 'family': SessionKind.COLONOSCOPY, 'words': REACH,
                       'statements': (DENIAL,)},
    M.ENTEROSCOPY_THROUGH: {**ENT_BASE, 'code': '44380', 'enteroscopy_class': EnteroscopyClass.STOMA,
                            'approach': Approach.THROUGH_STOMA},
    # D280.3 and D284 (step f3w of AMENDMENT-2's build round)
    M.DIGITAL_SCOPE: {'code': '45385', 'act': Kind.EXAMINATION, 'family': SessionKind.COLONOSCOPY, 'words': REACH,
                      'statements': (DENIAL,), 'attribute': Attribute.STATUS, 'held': requirements.Rank.STATUS},
    M.ADDON: {'code': '99417', 'family': SessionKind.OFFICE_EM, 'codes': ('99205', '99215', '99245')},
}


def built(message, **changes):
    return wording.build(message, wording.Slots(**{**FIXTURES[message], **changes}), TEXT)


def every_sentence():
    for message in M:
        item = built(message)
        yield message, item.question
        yield message, item.reason


def literals(function):
    """The string literals of ``function``'s source, joined in order: where a copied sentence's fixed words come from."""
    import inspect
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    found = [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    return ''.join(node.value for node in sorted(found, key=lambda node: (node.lineno, node.col_offset)))


class V1Unchanged(SimpleTestCase):
    """Done when: v1's wording functions are unchanged."""

    def test_every_v1_definition_keeps_its_source(self):
        source = WORDING.read_text(encoding='utf-8')
        tree = ast.parse(source)
        found = {}
        for node in tree.body:
            names = ([node.name] if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                     else [target.id for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                           if isinstance(target, ast.Name)] if isinstance(node, (ast.Assign, ast.AnnAssign)) else [])
            for name in names:
                found[name] = hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
        changed = sorted(name for name, digest in V1_PINS.items() if found.get(name) != digest)
        self.assertEqual(changed, [])
        self.assertEqual(len(V1_PINS), 88)

    def test_new_facts_and_missing_keep_v1s_seven_first(self):
        self.assertEqual(wording.NEW_FACTS[:7], V1_NEW_FACTS)
        self.assertEqual({key: wording.MISSING[key] for key in V1_NEW_FACTS}, V1_MISSING)
        self.assertEqual(list(wording.MISSING)[:7], list(V1_MISSING))


class NewFacts(SimpleTestCase):
    """D181: the five new facts join NEW_FACTS and MISSING with their sentences."""

    def test_the_five_join_in_d181s_order_with_their_sentences_verbatim(self):
        self.assertEqual(wording.NEW_FACTS, V1_NEW_FACTS + tuple(D181))
        self.assertEqual({key: wording.MISSING[key] for key in D181}, D181)
        self.assertEqual(set(wording.MISSING), set(wording.NEW_FACTS))
        decisions = ' '.join((ROOT / 'docs' / 'gemini-migration' / 'DECISIONS.md').read_text(encoding='utf-8').split())
        final = ' '.join((ROOT / 'docs' / 'gemini-migration' / 'FINAL-V2.md').read_text(encoding='utf-8').split())
        for fact, sentence in D181.items():
            self.assertIn(f'`{fact}`: "{sentence}"', decisions)
            self.assertIn(f'"{sentence}"', final)

    def test_every_new_fact_is_a_rank_fact_key_and_reaches_the_customer_words(self):
        keys = {fact.value for fact in requirements.FactKey}
        for fact in D181:
            self.assertIn(fact, keys)
            self.assertEqual(customer_api.FACT_WORDS[fact], D181[fact])
            self.assertIsNone(customer_api.FORBIDDEN.search(D181[fact]))


class QuoteSpan(SimpleTestCase):
    """The design's wording.quote(span): the revision sliced by integer spans only, after the decision."""

    def test_a_span_is_its_slice_in_curly_quotes(self):
        self.assertEqual(wording.span_text(TEXT, DENIAL), 'No polyp was removed from the rectum.')
        self.assertEqual(wording.quote_span(TEXT, DENIAL), '“No polyp was removed from the rectum.”')
        self.assertEqual(wording.quote_span(TEXT, DENIAL[0]), '“No polyp was removed from the rectum.”')
        self.assertEqual(wording.quote_span(TEXT, ACT, 20), wording.quote(wording.span_text(TEXT, ACT), 20))

    def test_spans_are_read_in_document_order_each_run_once(self):
        start = DENIAL[0].start
        spans = (Span(start + 9, start + 16), Span(start, start + 9), Span(start + 3, start + 12))
        self.assertEqual(wording.span_text(TEXT, spans), TEXT[start:start + 16])
        self.assertEqual(wording.span_text(TEXT, ACT + DENIAL), f'{wording.span_text(TEXT, ACT)} '
                                                                f'{wording.span_text(TEXT, DENIAL)}')
        self.assertEqual(wording.span_text(TEXT, (Span(3, 3),)), '')
        self.assertEqual(wording.span_text(TEXT, ()), '')

    def test_a_span_past_the_text_or_not_a_span_is_refused(self):
        with self.assertRaises(ValueError):
            wording.span_text(TEXT, (Span(0, len(TEXT) + 1),))
        with self.assertRaises(ValueError):
            wording.span_text(TEXT, ((0, 4),))
        with self.assertRaises(ValueError):
            wording.quote_span(None, DENIAL)


class Messages(SimpleTestCase):
    """Done when: every message id has a sentence; and every item the engine can raise has a message id."""

    def test_every_message_id_has_an_entry_a_rank_row_and_needs_only_slots(self):
        self.assertEqual(set(wording.MESSAGES), set(M))
        slot_names = set(wording.Slots.__dataclass_fields__)
        for message, spec in wording.MESSAGES.items():
            with self.subTest(message=message):
                self.assertLessEqual(set(spec.needs), slot_names)
                if spec.rank is None:
                    self.assertIn(requirements.FactKey(spec.fact), requirements.UNRANKED)
                else:
                    requirements.Item(requirements.Rank(spec.rank), requirements.FactKey(spec.fact))  # a RANK row
                self.assertIsInstance(spec.kind, ItemKind)

    def test_every_item_requirements_rules_raise_has_a_message_of_its_rank_key_and_kind(self):
        served = {(spec.rank, spec.fact, spec.kind) for spec in wording.MESSAGES.values()}
        missing = set()
        for name, rule in requirements.RULES.items():
            for items, kind in ((rule.asks, ItemKind.QUESTION), (rule.explains, ItemKind.EXPLANATION)):
                for item in items:
                    key = (item.rank.value if item.rank is not None else None, item.fact.value, kind)
                    if key not in served:
                        missing.add((str(name), *map(str, key)))
        self.assertEqual(missing, set())

    def test_every_message_id_builds_a_question_and_a_reason(self):
        self.assertEqual(set(FIXTURES), set(M))
        for message in M:
            with self.subTest(message=message):
                item = built(message)
                spec = wording.MESSAGES[message]
                self.assertEqual((item.message, item.kind), (message, spec.kind))
                self.assertEqual(item.fact, f'conflict:{FIXTURES[message]["act"].value}' if spec.fact == 'conflict'
                                 else spec.fact)
                for sentence in (item.question, item.reason):
                    self.assertTrue(sentence and sentence == sentence.strip(), sentence)
                    self.assertTrue(sentence.endswith(('.', '?')), sentence)
                    self.assertFalse(re.search(r'[{}]|\bNone\b|“”|\s{2}', sentence), sentence)
                self.assertTrue(item.question.endswith('?') or item.question.endswith('.'))
                self.assertEqual(wording.question(message, wording.Slots(**FIXTURES[message]), TEXT), item.question)
                self.assertEqual(wording.explanation(message, wording.Slots(**FIXTURES[message]), TEXT), item.reason)
                self.assertEqual(built(message), item)  # pure: the same inputs give the same words

    def test_every_quote_is_the_documents_own_words(self):
        for message, sentence in every_sentence():
            for quoted in re.findall(r'“([^”]*)”', sentence):
                with self.subTest(message=message, quoted=quoted):
                    self.assertIn(quoted.rstrip('…'), TEXT)

    def test_no_sentence_names_a_provider_or_model_or_carries_a_cause(self):
        for message, sentence in every_sentence():
            with self.subTest(message=message, sentence=sentence):
                self.assertIsNone(customer_api.FORBIDDEN.search(sentence))
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(sentence)], [])
                self.assertFalse([cause for cause in customer_api.HELD_FACT_CAUSES if cause in sentence])

    def test_the_conflict_fact_key_names_the_acts_kind(self):
        self.assertEqual(built(M.CONFLICT).fact, 'conflict:snare')
        self.assertEqual(built(M.CONFLICT_FACT, act=Kind.STONE_EXTRACTION).fact, 'conflict:stone_extraction')
        self.assertEqual(wording.fact_key(M.YIELD, wording.Slots()), 'act_yield')


class Refusals(SimpleTestCase):
    """build never falls back to another sentence: it refuses."""

    def test_each_needed_slot_left_empty_is_refused(self):
        for message, spec in wording.MESSAGES.items():
            for name in spec.needs:
                empty = '' if name == 'code' else () if isinstance(FIXTURES[message].get(name), tuple) else None
                with self.subTest(message=message, slot=name), self.assertRaises(ValueError):
                    built(message, **{name: empty})

    def test_a_quote_with_no_words_and_a_span_past_the_text_are_refused(self):
        blank = (Span(TEXT.index('. N') + 1, TEXT.index('. N') + 2),)  # a single space
        with self.assertRaises(ValueError):
            built(M.STATUS, words=blank)
        with self.assertRaises(ValueError):
            built(M.STATEMENT_SCOPE, statements=(blank,))
        with self.assertRaises(ValueError):
            built(M.TIME, words=(Span(0, len(TEXT) + 5),))
        with self.assertRaises(ValueError):
            wording.build(M.TIME, wording.Slots(**FIXTURES[M.TIME]), TEXT[:10])

    def test_untyped_slots_are_refused(self):
        for changes in ({'words': (('S1',),)}, {'words': 'A cold snare'}, {'act': 'snare'}, {'code': 45385},
                        {'statements': (Span(0, 3),)}, {'codes': (45384,)}, {'incomplete': 1}, {'owner': 'nursing'},
                        {'technique': 'balloon'}, {'group': ('snare',)}, {'code': '45 385'}, {'code': '12345678901'},
                        {'code': '4538\u0665'}, {'codes': ('',)}, {'codes': ('45384;',)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                wording.Slots(**{**FIXTURES[M.STATUS], **changes})
        with self.assertRaises(ValueError):
            wording.build('status', wording.Slots(**FIXTURES[M.STATUS]), TEXT)
        with self.assertRaises(ValueError):
            wording.build(M.STATUS, FIXTURES[M.STATUS], TEXT)

    def test_slots_that_contradict_the_message_are_worded_as_their_absence(self):
        """D254 rule 1 (repair r3c of round w8r; these were refusals until it): a slot whose value the message cannot name
        truly is worded as its absence - the sentence states the message's own fact and never that value."""
        expected = {
            (M.ANOTHER_TRACT, 'tract'): (
                'The documented endoscopic ultrasound is placed in another tract than the upper tract (the rectum: “EUS '
                'imaging was performed from the stomach.”). Was an endoscopic ultrasound through an upper endoscopy (the '
                'esophagus, the stomach or the duodenum) performed on the date of service?',
                '43242 accounts for an endoscopic ultrasound through an upper endoscopy (the esophagus, the stomach or '
                'the duodenum); the document places this endoscopic ultrasound in another tract than the upper tract (the '
                'rectum: “EUS imaging was performed from the stomach.”). Held for the reviewer, not excluded.'),
            (M.ANOTHER_TECHNIQUE, 'stated'): (
                'The documented dilation (“A cold snare polypectomy of the 6 mm sigmoid polyp was performed.”) states a '
                'dilation of another technique. Was a balloon dilation performed on the date of service?',
                'The upper endoscopy is documented as performed with a dilation of another technique (“A cold snare '
                'polypectomy of the 6 mm sigmoid polyp was performed.”); this code accounts for a balloon dilation, which '
                'CPT Studio could not find in the document.'),
            (M.ANOTHER_ENTRY, 'owner'): (
                "The clip placement is documented only in an entry other than the physician's note (“clip placed at the "
                'polypectomy site.”). Was it performed in this colonoscopy on the date of service?',
                "The clip placement this code accounts for is documented only in an entry other than the physician's "
                'note (“clip placed at the polypectomy site.”), not by the physician performing the colonoscopy. Held '
                'for the reviewer, not excluded.'),
            (M.ANOTHER_SITE, 'place'): (
                'The documented dilation (“A cold snare polypectomy of the 6 mm sigmoid polyp was performed.”) is at '
                'another site. Was a dilation of the esophagus performed on the date of service?',
                'The upper endoscopy is documented as performed with a dilation at another site (“A cold snare '
                'polypectomy of the 6 mm sigmoid polyp was performed.”); this code accounts for a dilation of the '
                'esophagus, which CPT Studio could not find in the document.'),
            (M.STATION_CLASS, 'stations'): (
                'CPT Studio could not find the endoscopic ultrasound examination this code describes in the documented '
                'endoscopic ultrasound examination (“EUS imaging was performed from the stomach.”). Was it performed on '
                'the date of service?',
                '43242 accounts for the endoscopic ultrasound examination this code describes, which CPT Studio could '
                'not find in the document. Held for the reviewer, not excluded.'),
            (M.PART, 'bundling'): (
                'Was the forceps biopsy (“Biopsies were taken from the polyp base.”) part of another act documented with '
                'it (“A cold snare polypectomy of the 6 mm sigmoid polyp was performed.”)?',
                'CPT Studio could not confirm from the document whether the forceps biopsy is part of another act '
                'documented with it.'),
            (M.CONFLICT_FACT, 'statements'): (
                'The document is not consistent about the snare removal (cold snare) (“No polyp was removed from the '
                'rectum.”). Which is correct for this encounter?',
                'The document is not consistent about the snare removal (cold snare) (“No polyp was removed from the '
                'rectum.”). Each value it states is kept; none is chosen.'),
            (M.SEPARATE_EM, 'listed'): (wording.SEPARATE_EM_QUESTION, wording.SEPARATE_EM_UNNAMED),
            (M.BASE_INCLUDED, 'listed'): (
                'Is 45378 reported separately from another act (stated in doubt) for this examination?',
                'The documented colonoscopy includes another act (stated in doubt), which this diagnostic code does not '
                'account for (internal profile rule). Held for the reviewer, not excluded.'),
            (M.BASE_EXPLAINED, 'codes'): (
                'Is 45378 reported separately from another act for this examination?',
                'The documented colonoscopy includes another act, which this diagnostic code does not account for '
                '(internal profile rule). Held for the reviewer, not excluded.'),
        }
        changes = {(M.ANOTHER_TRACT, 'tract'): {'tract': Tract.UPPER},
                   (M.ANOTHER_TECHNIQUE, 'stated'): {'stated': TechniqueClass.BALLOON},
                   (M.ANOTHER_ENTRY, 'owner'): {'owner': Owner.DOCUMENTING_CLINICIAN},
                   (M.ANOTHER_SITE, 'place'): {'place': Landmark.OTHER},
                   (M.STATION_CLASS, 'stations'): {'denied': (), 'stations': (Station.STOMACH,)},
                   (M.PART, 'bundling'): {'bundling': wording.Bundling.CLIP},
                   (M.CONFLICT_FACT, 'statements'): {'statements': (DENIAL,)},
                   (M.SEPARATE_EM, 'listed'): {'listed': (), 'possible': (), 'codes': ()},
                   (M.BASE_INCLUDED, 'listed'): {'listed': (), 'codes': ()},
                   (M.BASE_EXPLAINED, 'codes'): {'codes': (), 'listed': ()}}
        for key, words in expected.items():
            with self.subTest(message=key[0], changes=changes[key]):
                item = built(key[0], **changes[key])
                self.assertEqual((item.question, item.reason), words)
        self.assertEqual(built(M.SEPARATE_EM, listed=(), possible=()).reason, wording.SEPARATE_EM_UNNAMED)
        item = built(M.ANOTHER_TRACT, required_tract=Tract.PANCREATOBILIARY)  # no luminal EUS tract: named as a place
        self.assertIn('accounts for an endoscopic ultrasound placed in the pancreatobiliary tract;', item.reason)
        self.assertIn('and this code needs it placed in the pancreatobiliary tract.', item.reason)


class CopiesEqualV1(SimpleTestCase):
    """The words copied from v1's modules equal their originals (test-only imports of the retired modules)."""

    def test_constants(self):
        from studio.interpretation import assess, classes, coverage, mapping
        from studio.interpretation.engine import derive
        from studio.validation import checks
        self.assertEqual(wording.HELD, assess.HELD)
        self.assertEqual((wording.EGD_LIMITED_WORDS, wording.FULL_STATIONS_WORDS, wording.UPPER_TRACT_WORDS),
                         (assess.EGD_LIMITED_WORDS, assess.FULL_STATIONS_WORDS, assess.UPPER_TRACT_WORDS))
        self.assertEqual(wording.EXTENT_NOT_FOUND, checks.EXTENT_NOT_FOUND)
        self.assertEqual(dict(wording.R6_QUESTIONS), checks.FACT_QUESTIONS)
        self.assertEqual(wording.SEPARATE_EM_QUESTION, checks.SEPARATE_EM_QUESTION)
        self.assertEqual((wording.BASE_QUESTION, wording.IN_DOUBT), (classes.BASE_QUESTION, classes.IN_DOUBT))
        self.assertEqual({key.value: value for key, value in wording.ENTEROSCOPY_CLASS_WORDS.items()},
                         dict(classes.CLASS_WORDS))
        self.assertEqual({classes.ROUTE_PHRASES[{Approach.ORAL: classes.ORAL, Approach.THROUGH_STOMA:
                                                 classes.THROUGH_STOMA, Approach.THROUGH_POUCH: classes.THROUGH_POUCH}
                                                [way]] for way in wording.APPROACH_WORDS},
                         set(wording.APPROACH_WORDS.values()))
        self.assertEqual({wording.family_slug(family): service for family, service in wording.SESSION_SERVICES.items()},
                         dict(mapping.SERVICE_KIND))
        for family in SessionKind:
            self.assertEqual(wording.family_slug(family), derive.family_slug(family))
        self.assertEqual(wording.BUNDLING_WHY[wording.Bundling.PROCEDURAL_ADJUNCT], coverage.PROCEDURAL_ADJUNCT)
        self.assertEqual(wording.BUNDLING_WHY[wording.Bundling.STENT_INCLUDED], coverage.STENT_INCLUDED)
        for rule in ('biopsy_of_removed_lesion', 'resection_technique', 'lift_injection', 'clip', 'cannulation'):
            self.assertEqual(wording.BUNDLING_WHY[wording.Bundling(rule)], coverage.COMMON[rule])
        for labels, possible in ((['a'], []), ([], ['b', 'c']), (['a', 'b'], ['c'])):
            self.assertEqual(wording._same_day_subject(labels, possible), checks._same_day_subject(labels, possible))

    def test_sentences_built_by_v1_equal(self):
        from studio.interpretation import combination, events, mapping
        _, spec = combination.competing_hold('45385', 'gi.colonoscopy', 'k', ['45384'], 'colonoscopy')
        item = built(M.COMPETING)
        self.assertEqual((item.question, item.reason), (spec.question, spec.reason))
        _, spec = combination.base_hold('45378', 'gi.colonoscopy', 'k', ['45385'], 'colonoscopy')
        item = built(M.BASE_EXPLAINED)
        self.assertEqual((item.question, item.reason), (spec.question, spec.reason))
        _, spec = combination.base_hold('45378', 'gi.colonoscopy', 'k', ['snare removal'], 'colonoscopy')
        item = built(M.BASE_EXPLAINED, codes=(), listed=(Kind.SNARE,))
        self.assertEqual((item.question, item.reason), (spec.question, spec.reason))
        _, spec = combination.base_within_hold('43235', 'gi.egd', 'k', ['43237'], 'upper endoscopy')
        item = built(M.BASE_WITHIN, whole_family=SessionKind.EUS)  # D257: v1's whole was always an EUS
        self.assertEqual((item.question, item.reason), (spec.question, spec.reason))
        unnamed = built(M.BASE_WITHIN)  # D257: with no whole's family, never an EUS it may not be
        self.assertNotIn('endoscopic ultrasound', unnamed.question + unnamed.reason)
        evaluation = events.recognised_only_hold('99152', mapping.code_link('99152'), ())
        item = built(M.RECOGNISED_ONLY)
        self.assertEqual((item.question, item.reason), (evaluation.question.question, evaluation.detail))
        for exam_class, reached in ((EusClass.FULL, Extent.STOMACH), (EusClass.LIMITED, Extent.DUODENUM)):
            for incomplete in (False, True):
                reason, question = wording.examination_class_hold('43242', exam_class.value, reached.value,
                                                                  'EUS imaging was performed.', incomplete=incomplete)
                item = wording.build(M.EXAMINATION_CLASS, wording.Slots(
                    code='43242', exam_class=exam_class, reached=reached, incomplete=incomplete,
                    words=(Span(0, 26),)), 'EUS imaging was performed. The rest.')
                self.assertEqual((item.question, item.reason), (question, reason))

    def test_the_copied_sentences_fixed_words_are_v1s(self):
        from studio.interpretation import assess, classes, ercp, events
        pins = (
            (ercp._nothing_retrieved_hold, ('Was any stone, calculus, debris or sludge removed with the ',
                                            'The document states that nothing was retrieved with the ',
                                            'CPT Studio does not read a sweep or an extraction that retrieved nothing '
                                            'as a removal of stones or debris. Held for the reviewer, not excluded.')),
            (events.another_role_hold, (' is documented only in the ', '. Was it performed in this ',
                                        ' on the date of service?', ', not by the physician performing the ')),
            (assess._eus_code_hold, ('; the document places this endoscopic ultrasound in the lower tract (',
                                     '), which no upper endoscopic ultrasound code describes. ',
                                     'The documented endoscopic ultrasound is placed in the lower tract (',
                                     ' was not examined (', 'names one station only, the ',
                                     ' describes an EUS-guided transmural injection (of a diagnostic or therapeutic '
                                     'substance, or of fiducial markers); the document ',
                                     'describes this ', ' as an injection of the wall (',
                                     ', a submucosal injection rather than a transmural one. ',
                                     ' an EUS-guided transmural injection or fiducial placement, or a submucosal '
                                     'injection of the wall?')),
            (classes.class_hold, ('The enteroscopy is documented as reaching the ', ' and as incomplete',
                                  ', and CPT Studio could not confirm from the document whether it was passed through '
                                  'the mouth or ', ' is stated to be incomplete. Was ',
                                  ' performed on the date of service?')),
        )
        for function, fragments in pins:
            text = literals(function)
            for fragment in fragments:
                with self.subTest(function=function.__name__, fragment=fragment):
                    self.assertIn(fragment, text)


class Labels(SimpleTestCase):
    """events.event_label, group_label and service_label over text-free facts."""

    def test_act_phrase(self):
        def phrase(**slots):
            return wording.act_phrase(TEXT, wording.Slots(**slots))
        self.assertEqual(phrase(act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY), 'colonoscopy')
        self.assertEqual(phrase(act=Kind.EXAMINATION), 'examination')
        self.assertEqual(phrase(act=Kind.EXAMINATION, family=SessionKind.SEDATION), 'examination')
        self.assertEqual(phrase(act=Kind.SNARE, device=Device.COLD_SNARE), 'snare removal (cold snare)')
        self.assertEqual(phrase(act=Kind.SNARE, device=Device.SNARE), 'snare removal')
        self.assertEqual(phrase(act=Kind.SNARE, device=Device.ENDOSCOPE), 'snare removal')
        self.assertEqual(phrase(act=Kind.SNARE, device=Device.OTHER), 'snare removal')
        self.assertEqual(phrase(act=Kind.SNARE, device=Device.COLD_SNARE, lesion=sp('6 mm sigmoid polyp'),
                                place=Landmark.SIGMOID_COLON), 'snare removal (cold snare) of the 6 mm sigmoid polyp')
        self.assertEqual(phrase(act=Kind.SNARE, place=Landmark.SIGMOID_COLON), 'snare removal at the sigmoid colon')
        self.assertEqual(phrase(act=Kind.SNARE, place=Landmark.OTHER), 'snare removal')
        self.assertEqual(phrase(act=Kind.REMOVAL), 'removal')
        self.assertEqual(phrase(), 'another act')  # D254 rule 2: a kind not established
        self.assertEqual(phrase(act=Kind.OTHER, device=Device.NEEDLE, place=Landmark.PANCREAS),
                         'another act (needle) at the pancreas')

    def test_group_and_service_phrases(self):
        def group(*kinds, family=None):
            return wording.group_phrase(wording.Slots(group=kinds, family=family))
        self.assertEqual(group(Kind.EXAMINATION, family=SessionKind.EUS), 'endosonographic examination')
        self.assertEqual(group(Kind.EXAMINATION, family=SessionKind.EGD), 'upper endoscopy')
        self.assertEqual(group(Kind.EXAMINATION), 'examination')
        self.assertEqual(group(Kind.SNARE, Kind.EMR, Kind.SNARE), 'snare removal or endoscopic mucosal resection')
        self.assertEqual(group(), '')  # D254: a group that names no act ('' - each builder words the code instead)
        self.assertEqual(group(Kind.OTHER), '')
        self.assertEqual(group(Kind.CLIP, Kind.OTHER), 'clip placement')
        self.assertEqual(wording.service_phrase(SessionKind.ERCP), 'ERCP')
        self.assertEqual(wording.service_phrase(SessionKind.SEDATION), 'Moderate sedation by the performing physician')
        self.assertEqual(wording.service_phrase(None), 'procedure')
        self.assertEqual(wording.profile_label(SessionKind.OTHER_GI), 'Other GI service')


class TrueSentences(SimpleTestCase):
    """Sentences that would be false in some state are worded for every state the slots allow."""

    def test_a_pancreatobiliary_session_is_said_by_the_rule_it_fails(self):
        item = built(M.ANOTHER_TRACT, tract=Tract.PANCREATOBILIARY, place=None)
        self.assertIn('places this endoscopic ultrasound in the pancreatobiliary tract (', item.reason)
        self.assertIn('and this code needs it placed in the upper tract. Held for the reviewer', item.reason)
        self.assertNotIn('describes', item.reason)  # an upper EUS images the pancreas and the bile ducts
        lower = built(M.ANOTHER_TRACT)
        self.assertIn('which no upper endoscopic ultrasound code describes', lower.reason)
        upper = built(M.ANOTHER_TRACT, code='45391', tract=Tract.UPPER, required_tract=Tract.LOWER, place=None)
        self.assertIn('which no lower endoscopic ultrasound code describes', upper.reason)

    def test_route_b_is_never_ready(self):
        self.assertEqual(built(M.UNRECONCILED).reason,
                         '46221 is matched to the documented acts by their place alone: no service profile in this '
                         'release reconciles it with them, so it is never ready for approval (DECISIONS D197). Held for '
                         'the reviewer, not excluded.')

    def test_the_cause_question_names_each_cause_of_the_contract(self):
        self.assertEqual(built(M.CAUSE).question,
                         'Did the snare removal (“A cold snare polypectomy of the 6 mm sigmoid polyp was performed.”) at '
                         'this procedure cause the bleeding the clip placement (“clip placed at the polypectomy site.”) '
                         'treated, or was the bleeding from a lesion present before it, from an earlier procedure, or '
                         'spontaneous?')
        self.assertEqual(built(M.CAUSE, whole=None, whole_words=()).question,
                         'Did an act of this procedure cause the bleeding the clip placement (“clip placed at the '
                         'polypectomy site.”) treated, or was the bleeding from a lesion present before it, from an '
                         'earlier procedure, or spontaneous?')


# --- D225 (repair r3c): the items step r4a words (refute-4a-r2 P5, P6, P7, P10, P11) ---------------------------------

D225_TEXT = ('The snare polypectomy was done today or at the last visit. The snare polypectomy was done today. '
             'The snare polypectomy was done at the 2019 colonoscopy. No polyps were removed. '
             'EUS was advanced through the colostomy to the sigmoid colon. '
             'The echoendoscope entered through the stoma. '
             'EUS was advanced to the sigmoid colon. The approach was transanal. '
             'The old biliary stent was removed. A new plastic stent was placed. '
             'EUS-guided drainage was performed at the common bile duct.')


def d225(phrase):
    start = D225_TEXT.index(phrase)
    return (Span(start, start + len(phrase)),)


ONE = d225('The snare polypectomy was done today or at the last visit.')
TODAY = d225('The snare polypectomy was done today.')
EARLIER = d225('The snare polypectomy was done at the 2019 colonoscopy.')
NONE_REMOVED = d225('No polyps were removed.')
STOMA_EUS = d225('EUS was advanced through the colostomy to the sigmoid colon.')
STOMA_ENTRY = d225('The echoendoscope entered through the stoma.')
EXAM = d225('EUS was advanced to the sigmoid colon.')
TRANSANAL = d225('The approach was transanal.')
OLD = d225('The old biliary stent was removed.')
NEW = d225('A new plastic stent was placed.')
DRAIN = d225('EUS-guided drainage was performed at the common bile duct.')
STOMA_CLASS = 'an endoscopic ultrasound examination through a colonoscopy by way of a stoma'
HELD_WORDS = 'Held for the reviewer, not excluded.'


def worded(message, **slots):
    return wording.build(message, wording.Slots(**slots), D225_TEXT)


class D225Items(SimpleTestCase):
    """D225: each new id's exact text in every form its slots allow, and its refusals."""

    def test_the_new_ids_entries(self):
        expected = {
            M.CONFLICT_ATTRIBUTE: ('conflict', ItemKind.QUESTION, 1, ('act', 'attribute')),
            # D254 rule 1 (repair r3c of round w8r): only the slots every item carries by construction (CARRIED)
            M.UNLISTED_EVIDENCE: ('performed_status', ItemKind.QUESTION, 2, ('code', 'unlisted_what')),
            M.EXAMINATION_ROUTE: ('procedure', ItemKind.QUESTION, 8, ('code', 'exam_class')),
            M.EXAMINATION_APPROACH: ('procedure', ItemKind.EXPLANATION, 8, ('code', 'exam_class')),
            M.SAME_DUCT: ('act_target', ItemKind.QUESTION, 11, ()),
            M.STRUCTURE_PLACE: ('target', ItemKind.EXPLANATION, 12, ('code',)),
        }
        for message, entry in expected.items():
            spec = wording.MESSAGES[message]
            self.assertEqual((spec.fact, spec.kind, spec.rank, spec.needs), entry, message)
        # the six D225 ids, then D246's synthetic_act and round w8r's two ids appended after them, then step f3w's two
        # (D280.3's digital_scope, D284's addon)
        self.assertEqual([member.value for member in M][-11:-5], ['conflict_attribute', 'unlisted_evidence',
                                                                  'examination_route', 'examination_approach',
                                                                  'same_duct', 'structure_place'])
        self.assertEqual([member.value for member in M][-5:], ['synthetic_act', 'unlisted_scope', 'enteroscopy_through',
                                                               'digital_scope', 'addon'])
        names = [field.name for field in wording.Slots.__dataclass_fields__.values()]  # after both, whatever follows them
        self.assertEqual(names[names.index('both') + 1:names.index('both') + 4], ['attribute', 'unlisted_what',
                                                                                  'unlisted_kind'])

    # P7: a contradicted attribute, named, each side's own sentence quoted once
    def test_conflict_attribute_two_sentences(self):
        item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=Attribute.DATE_RELATION,
                      statements=(TODAY, EARLIER))
        self.assertEqual((item.fact, item.kind), ('conflict:snare', ItemKind.QUESTION))
        self.assertEqual(item.question, 'Statements in the document disagree about when the snare removal was done: “The '
                                        'snare polypectomy was done today.” and “The snare polypectomy was done at the '
                                        '2019 colonoscopy.”. Which is correct for this encounter?')
        self.assertEqual(item.reason, 'Statements in the document disagree about when the snare removal was done (“The '
                                      'snare polypectomy was done today.”; “The snare polypectomy was done at the 2019 '
                                      'colonoscopy.”). Both are kept; neither is chosen.')

    def test_conflict_attribute_in_one_sentence_quotes_it_once(self):
        """P7's input: both sides' sources in one unit (HO-8's E3 date relation contra(ON, EARLIER)) - the sentence is
        quoted once, the attribute named, never "performed and not performed"; the act's own sentence stands in when
        the sides carry no span of their own."""
        expected = ('The document is not consistent about when the snare removal was done (“The snare polypectomy was '
                    'done today or at the last visit.”). Which is correct for this encounter?',
                    'The document is not consistent about when the snare removal was done (“The snare polypectomy was '
                    'done today or at the last visit.”). Each value it states is kept; none is chosen.')
        for slots in ({'statements': (ONE, ONE)}, {'statements': (ONE,)}, {'words': ONE}):
            with self.subTest(slots=slots):
                item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=Attribute.DATE_RELATION, **slots)
                self.assertEqual((item.question, item.reason), expected)
                self.assertNotIn('not performed', item.question + item.reason)

    def test_conflict_attribute_three_sentences_and_the_device(self):
        """Three sides; and the contested device is not stated as the act's (refute-r3c-r1 P6: the first round's
        "the dilation (balloon)" named one side's value as fact)."""
        item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.DILATION, device=Device.BALLOON, attribute=Attribute.TECHNIQUE_DEVICE,
                      statements=(ONE, TODAY, EARLIER))
        self.assertEqual(item.question, 'Statements in the document disagree about which device was used for the '
                                        'dilation: “The snare polypectomy was done today or at the last visit.”, “The '
                                        'snare polypectomy was done today.” and “The snare polypectomy was done at the '
                                        '2019 colonoscopy.”. Which is correct for this encounter?')
        self.assertEqual(item.reason, 'Statements in the document disagree about which device was used for the dilation '
                                      '(“The snare polypectomy was done today or at the last visit.”; “The snare '
                                      'polypectomy was done today.”; “The snare polypectomy was done at the 2019 '
                                      'colonoscopy.”). Each is kept; none is chosen.')
        self.assertEqual(item.fact, 'conflict:dilation')

    def test_conflict_attribute_refusals(self):
        blank = (Span(D225_TEXT.index('. N') + 1, D225_TEXT.index('. N') + 2),)
        for slots in ({'attribute': Attribute.DATE_RELATION, 'statements': (blank,)},  # a binding failure
                      {'attribute': Attribute.DATE_RELATION, 'statements': (TODAY, blank)},
                      {'statements': (TODAY, EARLIER)}):  # the attribute is carried by construction (CARRIED)
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, **slots)
        # D254 rule 1: an act's attribute with no sentence at all is named, nothing quoted
        item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=Attribute.DATE_RELATION)
        self.assertEqual((item.question, item.reason),
                         ('The document is not consistent about when the snare removal was done. Which is correct for '
                          'this encounter?',
                          'The document is not consistent about when the snare removal was done. Each value it states is '
                          'kept; none is chosen.'))
        self.assertEqual(item, worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=Attribute.DATE_RELATION,
                                      statements=((),)))

    def test_every_attribute_has_a_phrase_read_after_about(self):
        self.assertEqual(set(wording.ATTRIBUTE_PHRASES), set(Attribute))
        for attribute, phrase in wording.ATTRIBUTE_PHRASES.items():
            with self.subTest(attribute=attribute):
                said = phrase.format(act='snare removal', session='colonoscopy')
                self.assertTrue(said and '{' not in said and '}' not in said, said)
                self.assertFalse(said.startswith(('with ', 'in ', 'at ', 'by ', 'through ', 'on ')), said)
                item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, family=SessionKind.COLONOSCOPY, attribute=attribute,
                              statements=(TODAY, EARLIER))
                self.assertTrue(item.question.startswith(f'Statements in the document disagree about {said}: '))
        self.assertEqual(wording.ATTRIBUTE_PHRASES[Attribute.DATE_RELATION], 'when the {act} was done')
        self.assertEqual(wording.ATTRIBUTE_PHRASES[Attribute.TECHNIQUE_DEVICE], 'which device was used for the {act}')
        self.assertEqual(wording.ATTRIBUTE_PHRASES[Attribute.STATUS], 'whether the {act} was done')

    # P11: 3.2.6 rule 2's item, the unlisted entry's nature and kind, its own unit quoted
    def test_unlisted_evidence_by_nature(self):
        item = worded(M.UNLISTED_EVIDENCE, code='45385', act=Kind.SNARE, unlisted_what=UnlistedWhat.DOUBT,
                      unlisted_kind=Kind.BIOPSY, statements=(NONE_REMOVED,))
        self.assertEqual((item.fact, item.kind), ('performed_status', ItemKind.QUESTION))
        self.assertEqual(item.question, 'The evidence passage of 45385 (“No polyps were removed.”) leaves a forceps '
                                        'biopsy in doubt. Confirm whether 45385 is supported by what was done on the '
                                        'date of service.')
        self.assertEqual(item.reason, "The evidence passage of 45385 (“No polyps were removed.”) leaves a forceps biopsy "
                                      "in doubt, which CPT Studio's reading of the document does not account for. Held "
                                      "for the reviewer, not excluded.")
        self.assertNotIn('snare', item.question + item.reason)  # never the code's act said to be in doubt (P11)
        item = worded(M.UNLISTED_EVIDENCE, code='43274', unlisted_what=UnlistedWhat.ACT,
                      unlisted_kind=Kind.STENT_REMOVAL, statements=(OLD,))
        self.assertEqual(item.question, 'The evidence passage of 43274 (“The old biliary stent was removed.”) documents '
                                        'a stent removal. Confirm whether 43274 is supported by what was done on the '
                                        'date of service.')
        self.assertEqual(item.reason, "The evidence passage of 43274 (“The old biliary stent was removed.”) documents a "
                                      "stent removal, which CPT Studio's reading of the document does not account for. "
                                      "Held for the reviewer, not excluded.")
        item = worded(M.UNLISTED_EVIDENCE, code='45385', unlisted_what=UnlistedWhat.DENIAL, statements=(NONE_REMOVED,))
        # D254 rule 2: an entry of no kind is 'another act'
        self.assertEqual(item.question, 'The evidence passage of 45385 (“No polyps were removed.”) states that another act '
                                        'was not done. Confirm whether 45385 is supported by what was done on the date of '
                                        'service.')
        self.assertEqual(item.reason, "The evidence passage of 45385 (“No polyps were removed.”) states that another act "
                                      "was not done, which CPT Studio's reading of the document does not account for. "
                                      "Held for the reviewer, not excluded.")
        item = worded(M.UNLISTED_EVIDENCE, code='45385', unlisted_what=UnlistedWhat.DENIAL, unlisted_kind=Kind.EMR,
                      statements=(NONE_REMOVED,))
        self.assertIn('states that an endoscopic mucosal resection was not done', item.question)
        self.assertEqual(dict(wording.UNLISTED_STATED), {UnlistedWhat.ACT: 'documents {kind}',
                                                         UnlistedWhat.DENIAL: 'states that {kind} was not done',
                                                         UnlistedWhat.DOUBT: 'leaves {kind} in doubt'})

    def test_unlisted_evidence_refusals(self):
        for slots in ({'unlisted_what': None}, {'code': ''}):  # carried by construction (CARRIED)
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                worded(M.UNLISTED_EVIDENCE, **{'code': '45385', 'unlisted_what': UnlistedWhat.DOUBT,
                                               'statements': (NONE_REMOVED,), **slots})
        # D254 rule 1: an entry with no units is named without a quote; several statements' units are its one passage
        item = worded(M.UNLISTED_EVIDENCE, code='45385', unlisted_what=UnlistedWhat.DOUBT, statements=())
        self.assertEqual((item.question, item.reason),
                         ('The evidence passage of 45385 leaves another act in doubt. Confirm whether 45385 is supported '
                          'by what was done on the date of service.',
                          "The evidence passage of 45385 leaves another act in doubt, which CPT Studio's reading of the "
                          'document does not account for. Held for the reviewer, not excluded.'))
        self.assertEqual(item, worded(M.UNLISTED_EVIDENCE, code='45385', unlisted_what=UnlistedWhat.DOUBT,
                                      statements=((),)))
        item = worded(M.UNLISTED_EVIDENCE, code='45385', unlisted_what=UnlistedWhat.DOUBT, statements=(NONE_REMOVED, OLD))
        self.assertTrue(item.question.startswith('The evidence passage of 45385 (“No polyps were removed. The old biliary '
                                                 'stent was removed.”) leaves another act in doubt.'), item.question)

    def test_with_article(self):
        for kind in Kind:
            label = wording.event_kind_label(kind.value)
            with self.subTest(kind=kind):
                self.assertEqual(wording.with_article(label), ('an ' if label[0] in 'aeiou' else 'a ') + label)
        self.assertEqual(wording.with_article('endoscopic mucosal resection'), 'an endoscopic mucosal resection')
        self.assertEqual(wording.with_article('forceps biopsy'), 'a forceps biopsy')
        self.assertEqual(wording.with_article(wording.event_kind_label('other')), 'an act')

    # P5: LOWER's stoma class asks its approach, never R6's extent sentence
    def test_examination_route_with_the_approach_not_established(self):
        base = dict(code='44406', exam_class=EusClass.STOMA, words=STOMA_EUS)
        item = worded(M.EXAMINATION_ROUTE, reached=Extent.SIGMOID_COLON, **base)
        self.assertEqual((item.fact, item.kind), ('procedure', ItemKind.QUESTION))
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced through the '
                                        'colostomy to the sigmoid colon.”) reached the sigmoid colon; CPT Studio could '
                                        'not confirm from the document whether it was passed through a stoma. Was an '
                                        'endoscopic ultrasound examination through a colonoscopy by way of a stoma '
                                        'performed on the date of service?')
        self.assertEqual(item.reason, f'44406 accounts for {STOMA_CLASS}; CPT Studio could not confirm from the document '
                                      'whether the endoscopic ultrasound examination was passed through a stoma. '
                                      f'{HELD_WORDS}')
        for sentence in (item.question, item.reason):
            self.assertNotIn('furthest extent', sentence)
            self.assertNotIn(wording.EXTENT_NOT_FOUND, sentence)
        item = worded(M.EXAMINATION_ROUTE, **base)
        self.assertEqual(item.question, 'CPT Studio could not confirm from the document whether the documented endoscopic '
                                        'ultrasound examination (“EUS was advanced through the colostomy to the sigmoid '
                                        f'colon.”) was passed through a stoma. Was {STOMA_CLASS} performed on the date of '
                                        'service?')
        item = worded(M.EXAMINATION_ROUTE, reached=Extent.SIGMOID_COLON, approaches=(Approach.THROUGH_STOMA,), **base)
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced through the '
                                        'colostomy to the sigmoid colon.”) reached the sigmoid colon; CPT Studio could '
                                        'not confirm from the document whether it was passed through the documented '
                                        f'stoma. Was {STOMA_CLASS} performed on the date of service?')
        self.assertEqual(item.reason, f'44406 accounts for {STOMA_CLASS}; CPT Studio could not confirm from the document '
                                      'whether the endoscopic ultrasound examination was passed through the documented '
                                      f'stoma. {HELD_WORDS}')

    def test_examination_route_with_the_stoma_not_established(self):
        base = dict(code='44406', exam_class=EusClass.STOMA, words=STOMA_EUS, approach=Approach.THROUGH_STOMA)
        item = worded(M.EXAMINATION_ROUTE, approach_words=STOMA_ENTRY, **base)
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced through the '
                                        'colostomy to the sigmoid colon.”) is stated to be passed through a stoma (“The '
                                        'echoendoscope entered through the stoma.”); CPT Studio could not confirm from '
                                        f'the document that the patient has a stoma. Was {STOMA_CLASS} performed on the '
                                        'date of service?')
        self.assertEqual(item.reason, f'44406 accounts for {STOMA_CLASS}; the document states that the endoscopic '
                                      'ultrasound examination was passed through a stoma (“The echoendoscope entered '
                                      'through the stoma.”), and CPT Studio could not confirm from the document that the '
                                      f'patient has a stoma. {HELD_WORDS}')
        item = worded(M.EXAMINATION_ROUTE, approach_words=STOMA_EUS, **base)  # its own sentence: quoted once
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced through the '
                                        'colostomy to the sigmoid colon.”) is stated to be passed through a stoma; CPT '
                                        'Studio could not confirm from the document that the patient has a stoma. Was '
                                        f'{STOMA_CLASS} performed on the date of service?')
        self.assertEqual(item.reason, f'44406 accounts for {STOMA_CLASS}; the document states that the endoscopic '
                                      'ultrasound examination was passed through a stoma, and CPT Studio could not '
                                      f'confirm from the document that the patient has a stoma. {HELD_WORDS}')

    def test_examination_route_refusals(self):
        base = dict(code='44406', exam_class=EusClass.STOMA, words=STOMA_EUS)
        for changes in ({'exam_class': None}, {'code': ''}):  # carried by construction (CARRIED)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                worded(M.EXAMINATION_ROUTE, **{**base, **changes})
        # D254 rule 1: every other value is worded. The route and the stoma both given (the item still asks the route):
        # the stoma it was passed through not confirmed
        item = worded(M.EXAMINATION_ROUTE, approach=Approach.THROUGH_STOMA, approaches=(Approach.THROUGH_STOMA,), **base)
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced through the '
                                        'colostomy to the sigmoid colon.”) is stated to be passed through a stoma; CPT '
                                        'Studio could not confirm from the document that it was passed through the '
                                        f'documented stoma. Was {STOMA_CLASS} performed on the date of service?')
        # an approach established otherwise is worded as the route not established (what the question asks)
        self.assertEqual(worded(M.EXAMINATION_ROUTE, approach=Approach.TRANSANAL, **base), worded(M.EXAMINATION_ROUTE,
                                                                                                 **base))
        # a class that needs no route of its own: the route not confirmed, or the approach given
        item = worded(M.EXAMINATION_ROUTE, **{**base, 'exam_class': EusClass.FULL})
        self.assertEqual((item.question, item.reason),
                         ('CPT Studio could not confirm from the document the route of the documented endoscopic '
                          'ultrasound examination (“EUS was advanced through the colostomy to the sigmoid colon.”). Was a '
                          'full endoscopic ultrasound examination (to the duodenum or beyond) performed on the date of '
                          'service?',
                          '44406 accounts for a full endoscopic ultrasound examination (to the duodenum or beyond); CPT '
                          'Studio could not confirm from the document the route of the endoscopic ultrasound examination. '
                          'Held for the reviewer, not excluded.'))
        item = worded(M.EXAMINATION_ROUTE, **{**base, 'exam_class': EusClass.FULL, 'approach': Approach.ORAL})
        self.assertIn('was passed through the mouth. Was a full endoscopic ultrasound examination', item.question)

    def test_examination_approach(self):
        item = worded(M.EXAMINATION_APPROACH, code='44406', exam_class=EusClass.STOMA, words=EXAM,
                      approach=Approach.TRANSANAL, approach_words=TRANSANAL)
        self.assertEqual((item.fact, item.kind), ('procedure', ItemKind.EXPLANATION))
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced to the '
                                        'sigmoid colon.”) was passed through the anus (“The approach was transanal.”). '
                                        f'Was {STOMA_CLASS} performed on the date of service?')
        self.assertEqual(item.reason, 'The endoscopic ultrasound examination is documented as passed through the anus '
                                      f'(“The approach was transanal.”); 44406 accounts for {STOMA_CLASS}, which CPT '
                                      'Studio could not find in the document.')
        item = worded(M.EXAMINATION_APPROACH, code='44407', exam_class=EusClass.STOMA, words=EXAM,
                      approach=Approach.ORAL)
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination (“EUS was advanced to the '
                                        f'sigmoid colon.”) was passed through the mouth. Was {STOMA_CLASS} performed on '
                                        'the date of service?')
        self.assertEqual(item.reason, 'The endoscopic ultrasound examination is documented as passed through the mouth; '
                                      f'44407 accounts for {STOMA_CLASS}, which CPT Studio could not find in the '
                                      'document.')
        # D254 rule 3's reading for this class: no other approach given (none, or the class's own) - no route named
        unnamed = ('CPT Studio could not confirm from the document that the documented endoscopic ultrasound '
                   'examination (“EUS was advanced to the sigmoid colon.”) was passed by the route this code describes. '
                   f'Was {STOMA_CLASS} performed on the date of service?',
                   'The endoscopic ultrasound examination is documented (“EUS was advanced to the sigmoid colon.”); 44406 '
                   f'accounts for {STOMA_CLASS}, which CPT Studio could not find in the document.')
        for changes in ({'approach': Approach.THROUGH_STOMA}, {'approach': None}):
            with self.subTest(changes=changes):
                item = worded(M.EXAMINATION_APPROACH, **{'code': '44406', 'exam_class': EusClass.STOMA, 'words': EXAM,
                                                         'approach': Approach.TRANSANAL, **changes})
                self.assertEqual((item.question, item.reason), unnamed)
        item = worded(M.EXAMINATION_APPROACH, code='44406', exam_class=EusClass.LIMITED, words=EXAM,
                      approach=Approach.TRANSANAL)  # a class with no route of its own: the approach named
        self.assertIn('was passed through the anus. Was a limited endoscopic ultrasound examination', item.question)
        with self.assertRaises(ValueError):
            worded(M.EXAMINATION_APPROACH, code='44406', words=EXAM, approach=Approach.TRANSANAL)  # carried: the class

    def test_route_tables(self):
        self.assertEqual(set(wording.ROUTE_WORDS), set(Approach))
        self.assertEqual({way: wording.ROUTE_WORDS[way] for way in wording.APPROACH_WORDS},
                         dict(wording.APPROACH_WORDS))
        self.assertEqual(dict(wording.EUS_CLASS_ROUTES), {EusClass.STOMA: Approach.THROUGH_STOMA})
        self.assertEqual(wording.ROUTE_WORDS[Approach.TRANSANAL], 'through the anus')

    # P6: XCHG's two-act duct question names the act whose duct is not established
    def test_same_duct(self):
        item = worded(M.SAME_DUCT, code='43274', act=Kind.STENT_REMOVAL, words=OLD, whole=Kind.STENT, whole_words=NEW)
        self.assertEqual((item.fact, item.kind), ('act_target', ItemKind.QUESTION))
        self.assertEqual(item.question, 'Were the stent removal (“The old biliary stent was removed.”) and the stent '
                                        'placement (“A new plastic stent was placed.”) done in the same duct?')
        self.assertEqual(item.reason, 'CPT Studio could not confirm from the document in which duct the stent removal '
                                      'was done. A stent removed and replaced in the same duct at one session is one '
                                      'stent exchange (43276), not a removal (43275) and a placement (43274). Held for '
                                      'the reviewer, not excluded.')
        duct = worded(M.DUCT, code='43274', act=Kind.STENT_REMOVAL, words=OLD, whole=Kind.STENT, whole_words=NEW)
        self.assertEqual(item.question, duct.question)  # DUCT's two-act form, reached from a fill naming both acts
        item = worded(M.SAME_DUCT, code='43276', act=Kind.STENT, words=NEW, whole=Kind.STENT_EXCHANGE, whole_words=OLD)
        self.assertEqual(item.reason, 'CPT Studio could not confirm from the document in which duct the stent placement '
                                      'was done. A removal or a placement that is part of a stent exchange is reported '
                                      'with the exchange (43276), not separately (43275, 43274). Held for the reviewer, '
                                      'not excluded.')
        base = dict(code='43274', act=Kind.STENT_REMOVAL, words=OLD, whole=Kind.STENT, whole_words=NEW)
        # D246: an act with no units ({'words': ()}, {'whole_words': ()}) is named without a quote (D246Forms). D254:
        # either act may name no kind ('another act'), and the exchange's reason is given only for its own pair
        held = 'Held for the reviewer, not excluded.'
        for changes, question, reason in (
                ({'whole': None}, 'Were the stent removal (“The old biliary stent was removed.”) and another act (“A new '
                                  'plastic stent was placed.”) done in the same duct?',
                 f'CPT Studio could not confirm from the document in which duct the stent removal was done. {held}'),
                ({'act': None}, 'Were another act (“The old biliary stent was removed.”) and the stent placement (“A new '
                                'plastic stent was placed.”) done in the same duct?',
                 f'CPT Studio could not confirm from the document in which duct another act was done. {held}'),
                ({'act': Kind.BIOPSY}, 'Were the forceps biopsy (“The old biliary stent was removed.”) and the stent '
                                       'placement (“A new plastic stent was placed.”) done in the same duct?',
                 f'CPT Studio could not confirm from the document in which duct the forceps biopsy was done. {held}'),
                ({'whole': Kind.STENT_REMOVAL}, 'Were the stent removal (“The old biliary stent was removed.”) and the '
                                                'stent removal (“A new plastic stent was placed.”) done in the same duct?',
                 f'CPT Studio could not confirm from the document in which duct the stent removal was done. {held}'),
                ({'whole': Kind.CLIP}, 'Were the stent removal (“The old biliary stent was removed.”) and the clip '
                                       'placement (“A new plastic stent was placed.”) done in the same duct?',
                 f'CPT Studio could not confirm from the document in which duct the stent removal was done. {held}')):
            with self.subTest(changes=changes):
                item = worded(M.SAME_DUCT, **{**base, **changes})
                self.assertEqual((item.question, item.reason), (question, reason))

    def test_the_exchange_reasons_are_v1s(self):
        from studio.interpretation import ercp
        text = literals(ercp.exchange_question)
        self.assertIn(wording.EXCHANGE_PAIR_RULE[:-1] + ';', text)
        self.assertIn(wording.EXCHANGE_PART_RULE[:-1] + ';', text)
        self.assertEqual(wording.STENT_KINDS, frozenset({Kind.STENT, Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE}))

    # P10: STRUCT:pfc's explanation names the place it sets apart
    def test_structure_place(self):
        item = worded(M.STRUCTURE_PLACE, code='43240', act=Kind.DRAINAGE, words=DRAIN, place=Landmark.COMMON_BILE_DUCT)
        self.assertEqual((item.fact, item.kind), ('target', ItemKind.EXPLANATION))
        self.assertEqual(item.question, 'Which structure was the drainage (“EUS-guided drainage was performed at the '
                                        'common bile duct.”) done on: a pancreatic fluid collection (a pseudocyst or '
                                        'walled-off necrosis), or another structure?')
        self.assertEqual(item.reason, '43240 describes the transmural drainage of a pancreatic fluid collection (a '
                                      'pseudocyst or walled-off necrosis); the document places this drainage at the '
                                      'common bile duct (“EUS-guided drainage was performed at the common bile duct.”). '
                                      'CPT Studio does not read an act placed in the biliary tree or the liver as the '
                                      'drainage of a pancreatic fluid collection. Held for the reviewer, not excluded.')
        item = worded(M.STRUCTURE_PLACE, code='43240', act=Kind.DRAINAGE, words=DRAIN, place=Landmark.LIVER)
        self.assertIn('the document places this drainage at the liver (', item.reason)
        # D254 rule 1 (P10's refusal replaced): a place STRUCT:pfc does not set apart is named without the rule - never
        # "does not read an act placed in the biliary tree or the liver" of the pancreas - and no place as another
        # structure
        prefix = ('43240 describes the transmural drainage of a pancreatic fluid collection (a pseudocyst or walled-off '
                  'necrosis); the document places this drainage at ')
        for place, at in ((Landmark.PANCREAS, 'the pancreas'), (Landmark.STOMACH, 'the stomach'),
                          (Landmark.DUODENAL_BULB, 'the duodenal bulb'), (Landmark.OTHER, 'another structure'),
                          (None, 'another structure')):
            with self.subTest(place=place):
                item = worded(M.STRUCTURE_PLACE, code='43240', act=Kind.DRAINAGE, words=DRAIN, place=place)
                self.assertEqual(item.reason, f'{prefix}{at} (“EUS-guided drainage was performed at the common bile '
                                              'duct.”). Held for the reviewer, not excluded.')
                self.assertNotIn(wording.APART_PLACE_RULE, item.reason)

    def test_the_new_slots_are_typed(self):
        for changes in ({'attribute': 'date_relation'}, {'attribute': Kind.SNARE}, {'unlisted_what': 'doubt'},
                        {'unlisted_what': Attribute.STATUS}, {'unlisted_kind': 'biopsy'},
                        {'unlisted_kind': UnlistedWhat.ACT}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                wording.Slots(**changes)
        wording.Slots(attribute=Attribute.STATUS, unlisted_what=UnlistedWhat.ACT, unlisted_kind=None)

    def test_no_new_sentence_names_a_provider_or_model_or_carries_a_cause(self):
        sentences = []
        for attribute in Attribute:
            for statements in ((TODAY, EARLIER), (ONE,)):
                item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=attribute, statements=statements)
                sentences += [item.question, item.reason]
        for what in UnlistedWhat:
            for kind in (None, *Kind):
                item = worded(M.UNLISTED_EVIDENCE, code='45385', unlisted_what=what, unlisted_kind=kind,
                              statements=(NONE_REMOVED,))
                sentences += [item.question, item.reason]
        for approach in Approach:
            if approach is not Approach.THROUGH_STOMA:
                item = worded(M.EXAMINATION_APPROACH, code='44406', exam_class=EusClass.STOMA, approach=approach)
                sentences += [item.question, item.reason]
        for message, slots in ((M.EXAMINATION_ROUTE, dict(code='44406', exam_class=EusClass.STOMA, words=STOMA_EUS,
                                                          reached=Extent.SIGMOID_COLON)),
                               (M.EXAMINATION_ROUTE, dict(code='44406', exam_class=EusClass.STOMA, words=STOMA_EUS,
                                                          approach=Approach.THROUGH_STOMA, approach_words=STOMA_ENTRY)),
                               (M.SAME_DUCT, dict(act=Kind.STENT_REMOVAL, words=OLD, whole=Kind.STENT_EXCHANGE,
                                                  whole_words=NEW)),
                               (M.STRUCTURE_PLACE, dict(code='43240', act=Kind.DRAINAGE, words=DRAIN,
                                                        place=Landmark.AMPULLA))):
            item = worded(message, **slots)
            sentences += [item.question, item.reason]
        self.assertGreater(len(sentences), 300)
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                self.assertIsNone(customer_api.FORBIDDEN.search(sentence))
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(sentence)], [])
                self.assertFalse([cause for cause in customer_api.HELD_FACT_CAUSES if cause in sentence])
                self.assertFalse(re.search(r'[{}]|\bNone\b|“”|\s{2}', sentence), sentence)
                for quoted in re.findall(r'“([^”]*)”', sentence):
                    self.assertIn(quoted.rstrip('…'), D225_TEXT)


# --- repair r3c, round 2 (refute-r3c-r1 P1, P2, P3, P6, P7) -----------------------------------------------------------

R2_TEXT = ('Linear EUS was performed from the stomach. FNA of the pancreatic head mass was done. '
           'The upper tract was examined. The lower tract was examined. '
           'Balloon dilation of the esophagus was performed. Bougie dilation of the esophagus was performed. '
           'A 6 mm polyp was removed with a cold snare. The polyp was in the sigmoid colon. '
           'The polyp was in the descending colon.')


def r2(phrase):
    start = R2_TEXT.index(phrase)
    return (Span(start, start + len(phrase)),)


FNA = r2('FNA of the pancreatic head mass was done.')
UPPER = r2('The upper tract was examined.')
LOWER = r2('The lower tract was examined.')
BALLOON = r2('Balloon dilation of the esophagus was performed.')
BOUGIE = r2('Bougie dilation of the esophagus was performed.')
POLYP = r2('6 mm polyp')
SIGMOID = r2('The polyp was in the sigmoid colon.')
DESCENDING = r2('The polyp was in the descending colon.')
SIDES = '“The snare polypectomy was done today.” and “The snare polypectomy was done at the 2019 colonoscopy.”'
KEPT = '(“The snare polypectomy was done today.”; “The snare polypectomy was done at the 2019 colonoscopy.”)'


def r2_worded(message, **slots):
    return wording.build(message, wording.Slots(**slots), R2_TEXT)


class D225Round2(SimpleTestCase):
    """Repair r3c, round 2: refute-r3c-r1's P1 (a session's attribute worded about the act the item names), P2 (the
    sides beside the act's own sentence unpinned), P3 (53 of the 56 attribute sentences unpinned), P6 (the contested
    device named as the act's) and P7 (the docstring's import claim)."""

    # every attribute's sentence (P3), the act a snare removal and the session a colonoscopy: what it is about
    PHRASES = {
        Attribute.DATE_OF_SERVICE: 'the date of service',
        Attribute.OTHER_DATES_ROLE: 'what a date the document gives refers to',
        Attribute.DOCUMENTING_CLINICIAN: 'who documented this encounter',
        Attribute.ROLE: 'the role of a person or of a part of the document',
        Attribute.OWNER: 'whose entry a part of the document is',
        Attribute.OCCASION: 'when the acts a part of the document tells were done',
        Attribute.PERFORMER: 'who performed the snare removal',
        Attribute.PERFORMER_PERSON: 'who performed the snare removal',
        Attribute.EXAMINATION: 'which documented act was the colonoscopy itself',
        Attribute.KIND: 'what was done',
        Attribute.ENCOUNTER: 'whether the colonoscopy was part of this encounter',
        Attribute.TRACT: 'which part of the digestive tract the colonoscopy examined',
        Attribute.APPROACH: 'the route of the colonoscopy',
        Attribute.THROUGH: 'the altered anatomy the colonoscopy was passed through',
        Attribute.REACHED: 'how far the colonoscopy reached',
        Attribute.DEVICE_REACHED: 'how far a device reached in the colonoscopy',
        Attribute.REACHED_ANATOMY: 'which altered anatomy the colonoscopy reached',
        Attribute.COMPLETION: 'whether the colonoscopy was completed',
        Attribute.STATIONS: 'which parts the colonoscopy examined',
        Attribute.PART_OF_SESSION: 'whether the colonoscopy was part of another procedure',
        Attribute.TYPE: 'what altered anatomy the document records',
        Attribute.ORGAN: 'which organ an altered anatomy the document records is in',
        Attribute.SUBTYPE: 'what kind of anastomosis the document records',
        Attribute.JOINS: 'what an anastomosis the document records joins',
        Attribute.MULTIPLICITY: 'whether the lesion of the snare removal is one lesion or a group',
        Attribute.PLACES: 'where the lesion of the snare removal lies',
        Attribute.DISTINCT_FROM: 'whether the lesion of the snare removal is distinct from another lesion',
        Attribute.SAME_AS: 'whether the lesion of the snare removal is the same as another lesion',
        Attribute.RESTATEMENTS_ROLE: 'whether another passage restates the snare removal',
        Attribute.OTHER_CLASS: 'what kind of service the snare removal was',
        Attribute.STATUS: 'whether the snare removal was done',
        Attribute.SESSION: 'which procedure the snare removal was done in',
        Attribute.DATE_RELATION: 'when the snare removal was done',
        Attribute.DATE: 'the date of the snare removal',
        Attribute.TARGET_LESION: 'which lesion the snare removal was done on',
        Attribute.TARGET_STRUCTURE: 'which structure the snare removal was done on',
        Attribute.TARGET_PLACES: 'where the snare removal was done',
        Attribute.TARGET_ANATOMY: 'which altered anatomy the snare removal was done at',
        Attribute.TARGET_DUCT: 'which duct the snare removal was done in',
        Attribute.TECHNIQUE_DEVICE: 'which device was used for the snare removal',
        Attribute.TECHNIQUE_ROUTE: 'how the snare removal reached the tissue',
        Attribute.PURPOSE: 'why the snare removal was done',
        Attribute.CAUSE: 'what caused the bleeding the snare removal treated',
        Attribute.CAUSE_EVENT: 'which act caused the bleeding the snare removal treated',
        Attribute.PART_OF: 'whether the snare removal was part of another act',
        Attribute.PART_RELATION: 'how the snare removal was part of another act',
        Attribute.YIELD: 'what the snare removal retrieved',
        Attribute.ACCESS_OUTCOME: 'whether the snare removal achieved access',
        Attribute.SCOPE_BREADTH: 'how much a statement in the document covers',
        Attribute.SCOPE_TARGETS: 'what a statement in the document is about',
        Attribute.SCOPE_SEGMENT: 'which segment a statement in the document covers',
        Attribute.SCOPE_COVERS: 'which acts a statement in the document covers',
        Attribute.SCOPE_EXCEPTS: 'which acts a statement in the document leaves out',
        Attribute.VISIT_BASIS: 'the basis for the level of the snare removal',
        Attribute.VISIT_SEPARATELY_IDENTIFIABLE: 'whether the snare removal was a significant, separately identifiable '
                                                 'service',
        Attribute.ENTRY: 'whose entry the snare removal is told in',
    }
    # session_label by the session's kind (P1): its service, else its noun, else 'procedure' (act not the examination)
    SESSIONS = {
        SessionKind.OFFICE_EM: 'office / outpatient visit', SessionKind.EGD: 'upper endoscopy',
        SessionKind.ENTEROSCOPY: 'enteroscopy', SessionKind.COLONOSCOPY: 'colonoscopy',
        SessionKind.FLEX_SIG: 'flexible sigmoidoscopy', SessionKind.EUS: 'endoscopic ultrasound',
        SessionKind.ERCP: 'ERCP',
        SessionKind.CAPSULE: 'capsule endoscopy', SessionKind.MOTILITY: 'manometry',
        SessionKind.REFLUX: 'pH / impedance study', SessionKind.ANORECTAL: 'anorectal testing',
        SessionKind.FEEDING_TUBE: 'feeding-tube procedure', SessionKind.SEDATION: 'procedure',
        SessionKind.EM_OTHER: 'visit', SessionKind.OTHER_GI: 'procedure', SessionKind.NOT_GI: 'procedure',
    }

    # P3: each of the 56 sentences in its exact text
    def test_every_attribute_in_its_exact_text(self):
        self.assertEqual(set(self.PHRASES), set(Attribute))
        for attribute, what in self.PHRASES.items():
            with self.subTest(attribute=attribute):
                item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, family=SessionKind.COLONOSCOPY, attribute=attribute,
                              statements=(TODAY, EARLIER))
                self.assertEqual(item.question, f'Statements in the document disagree about {what}: {SIDES}. Which is '
                                                'correct for this encounter?')
                self.assertEqual(item.reason, f'Statements in the document disagree about {what} {KEPT}. Both are '
                                              'kept; neither is chosen.')
                self.assertEqual(item.fact, 'conflict:snare')

    def test_every_route_in_its_exact_text(self):
        self.assertEqual(dict(wording.ROUTE_WORDS), {
            Approach.ORAL: 'through the mouth', Approach.TRANSNASAL: 'through the nose',
            Approach.TRANSANAL: 'through the anus', Approach.THROUGH_STOMA: 'through a stoma',
            Approach.THROUGH_POUCH: 'through a pouch', Approach.THROUGH_GASTROSTOMY: 'through a gastrostomy',
            Approach.PERCUTANEOUS: 'through the skin'})
        for approach, route in wording.ROUTE_WORDS.items():
            if approach is not Approach.THROUGH_STOMA:
                with self.subTest(approach=approach):
                    item = r2_worded(M.EXAMINATION_APPROACH, code='44406', exam_class=EusClass.STOMA, approach=approach)
                    self.assertEqual(item.question, f'The documented endoscopic ultrasound examination was passed '
                                                    f'{route}. Was {STOMA_CLASS} performed on the date of service?')

    # P1: a session's attribute is the session's, named by its service; the act only keys the fact
    def test_a_session_attribute_names_the_session_never_the_act(self):
        """refute-r3c-r1 P1's input: 43242, the FNA bound, the EUS session's tract contradicted - the held fact is
        conflict:fna (evaluate keys it by the candidate act), the fact itself the session's."""
        item = r2_worded(M.CONFLICT_ATTRIBUTE, code='43242', act=Kind.FNA, family=SessionKind.EUS, words=FNA,
                         attribute=Attribute.TRACT, statements=(UPPER, LOWER))
        self.assertEqual((item.fact, item.kind), ('conflict:fna', ItemKind.QUESTION))  # the held fact's own key
        self.assertEqual(item.question, 'Statements in the document disagree about which part of the digestive tract '
                                        'the endoscopic ultrasound examined: “The upper tract was examined.” and “The '
                                        'lower tract was examined.”. Which is correct for this encounter?')
        self.assertEqual(item.reason, 'Statements in the document disagree about which part of the digestive tract the '
                                      'endoscopic ultrasound examined (“The upper tract was examined.”; “The lower '
                                      'tract was examined.”). Both are kept; neither is chosen.')
        # the examination itself, the session's family given (another fill's reading), says the same of the session
        same = r2_worded(M.CONFLICT_ATTRIBUTE, code='43242', act=Kind.EXAMINATION, family=SessionKind.EUS,
                         attribute=Attribute.TRACT, statements=(UPPER, LOWER))
        self.assertEqual((same.question, same.reason, same.fact), (item.question, item.reason, 'conflict:examination'))
        item = r2_worded(M.CONFLICT_ATTRIBUTE, code='45342', act=Kind.FNA, family=SessionKind.EUS, words=FNA,
                         attribute=Attribute.REACHED, statements=(UPPER, LOWER))
        self.assertTrue(item.question.startswith('Statements in the document disagree about how far the endoscopic '
                                                 'ultrasound reached: '), item.question)
        for attribute in wording.SESSION_ATTRIBUTES:
            for act in (Kind.FNA, Kind.SNARE, Kind.STENT, Kind.DILATION, Kind.BIOPSY, Kind.DRAINAGE):
                with self.subTest(attribute=attribute, act=act):
                    item = r2_worded(M.CONFLICT_ATTRIBUTE, act=act, family=SessionKind.EUS, words=FNA,
                                     device=Device.BALLOON, place=Landmark.STOMACH, attribute=attribute,
                                     statements=(UPPER, LOWER))
                    self.assertEqual(item.fact, f'conflict:{act.value}')
                    label = wording.event_kind_label(act.value)
                    self.assertNotIn(label, item.question + item.reason)
                    self.assertIn('the endoscopic ultrasound', item.question)
                    self.assertNotIn('balloon', item.question + item.reason)
                    self.assertNotIn('stomach', item.question + item.reason)

    def test_session_label_by_the_sessions_kind(self):
        self.assertEqual(set(self.SESSIONS), set(SessionKind))
        for family, label in self.SESSIONS.items():
            with self.subTest(family=family):
                self.assertEqual(wording.session_label(wording.Slots(act=Kind.FNA, family=family)), label)
                item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, family=family, attribute=Attribute.ENCOUNTER,
                                 statements=(UPPER, LOWER))
                self.assertTrue(item.question.startswith(f'Statements in the document disagree about whether the '
                                                         f'{label} was part of this encounter: '), item.question)
        self.assertEqual(wording.session_label(wording.Slots(act=Kind.FNA)), 'procedure')
        self.assertEqual(wording.session_label(wording.Slots(act=Kind.EXAMINATION)), 'examination')
        self.assertEqual(wording.session_label(wording.Slots(act=Kind.EXAMINATION, family=SessionKind.OTHER_GI)),
                         'examination')
        self.assertEqual(wording.session_label(wording.Slots(act=Kind.EXAMINATION, family=SessionKind.EM_OTHER)),
                         'visit')
        self.assertEqual(dict(wording.SESSION_NOUNS), {SessionKind.EM_OTHER: 'visit'})
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.EXAMINATION, attribute=Attribute.REACHED,
                         statements=(UPPER, LOWER))
        self.assertTrue(item.question.startswith('Statements in the document disagree about how far the examination '
                                                 'reached: '), item.question)
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, attribute=Attribute.REACHED, statements=(UPPER, LOWER))
        self.assertTrue(item.question.startswith('Statements in the document disagree about how far the procedure '
                                                 'reached: '), item.question)

    def test_a_session_attribute_never_quotes_the_acts_own_sentence(self):
        """The act's own sentence is no side of its session's conflict: with no side's sentence nothing is quoted; an
        act's own attribute still quotes the act's sentence, and refuses nothing to quote."""
        for slots in ({'words': FNA}, {}):
            with self.subTest(slots=slots):
                item = r2_worded(M.CONFLICT_ATTRIBUTE, code='43242', act=Kind.FNA, family=SessionKind.EUS,
                                 attribute=Attribute.REACHED, **slots)
                self.assertEqual((item.fact, item.kind), ('conflict:fna', ItemKind.QUESTION))
                self.assertEqual(item.question, 'The document is not consistent about how far the endoscopic '
                                                'ultrasound reached. Which is correct for this encounter?')
                self.assertEqual(item.reason, 'The document is not consistent about how far the endoscopic ultrasound '
                                              'reached. Each value it states is kept; none is chosen.')
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, family=SessionKind.EUS, words=FNA,
                         attribute=Attribute.TRACT, statements=(UPPER, UPPER))
        self.assertEqual(item.question, 'The document is not consistent about which part of the digestive tract the '
                                        'endoscopic ultrasound examined (“The upper tract was examined.”). Which is '
                                        'correct for this encounter?')
        self.assertEqual(item.reason, 'The document is not consistent about which part of the digestive tract the '
                                      'endoscopic ultrasound examined (“The upper tract was examined.”). Each value it '
                                      'states is kept; none is chosen.')
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, family=SessionKind.EUS, words=FNA,
                         attribute=Attribute.DATE_RELATION)
        self.assertEqual(item.question, 'The document is not consistent about when the fine-needle aspiration or '
                                        'biopsy was done (“FNA of the pancreatic head mass was done.”). Which is '
                                        'correct for this encounter?')
        blank = (Span(R2_TEXT.index('. F') + 1, R2_TEXT.index('. F') + 2),)
        for slots in ({'attribute': Attribute.REACHED, 'statements': (blank,)},  # binding failures
                      {'attribute': Attribute.REACHED, 'statements': (UPPER, blank)}):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, family=SessionKind.EUS, **slots)
        # D254 rule 1: an act's attribute with no sentence at all is named, nothing quoted
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, family=SessionKind.EUS, attribute=Attribute.DATE_RELATION)
        self.assertEqual(item.question, 'The document is not consistent about when the fine-needle aspiration or biopsy '
                                        'was done. Which is correct for this encounter?')

    # P2: the slot shape questions.fill produces - the act's anchor as words AND the contested sides as statements
    def test_the_sides_are_quoted_beside_the_acts_own_sentence(self):
        item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=Attribute.DATE_RELATION, words=ONE,
                      statements=(TODAY, EARLIER))
        self.assertEqual(item.question, f'Statements in the document disagree about when the snare removal was done: '
                                        f'{SIDES}. Which is correct for this encounter?')
        self.assertEqual(item.reason, f'Statements in the document disagree about when the snare removal was done '
                                      f'{KEPT}. Both are kept; neither is chosen.')
        self.assertNotIn('today or at the last visit', item.question + item.reason)  # the act's own sentence: no side
        item = worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, attribute=Attribute.DATE_RELATION, words=ONE,
                      statements=(TODAY,))
        self.assertEqual(item.question, 'The document is not consistent about when the snare removal was done (“The '
                                        'snare polypectomy was done today.”). Which is correct for this encounter?')

    # P6: the act's label never states the value the conflict contests
    def test_the_acts_label_never_states_the_contested_value(self):
        self.assertEqual(dict(wording.CONTESTED_LABEL_PARTS), {
            Attribute.TECHNIQUE_DEVICE: ('device',), Attribute.TARGET_PLACES: ('place', 'lesion'),
            Attribute.TARGET_LESION: ('place', 'lesion'), Attribute.PLACES: ('place', 'lesion'),
            Attribute.MULTIPLICITY: ('lesion',), Attribute.DISTINCT_FROM: ('lesion',), Attribute.SAME_AS: ('lesion',)})
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.DILATION, device=Device.BALLOON,
                         place=Landmark.DISTAL_ESOPHAGUS, attribute=Attribute.TECHNIQUE_DEVICE,
                         statements=(BALLOON, BOUGIE))
        self.assertEqual(item.question, 'Statements in the document disagree about which device was used for the '
                                        'dilation at the distal esophagus: “Balloon dilation of the esophagus was '
                                        'performed.” and “Bougie dilation of the esophagus was performed.”. Which is '
                                        'correct for this encounter?')
        item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.DILATION, device=Device.BALLOON,
                         place=Landmark.DISTAL_ESOPHAGUS, attribute=Attribute.DATE_RELATION,
                         statements=(BALLOON, BOUGIE))
        self.assertTrue(item.question.startswith('Statements in the document disagree about when the dilation '
                                                 '(balloon) at the distal esophagus was done: '),
                        item.question)  # the device and the place are not contested here: named
        expected = {
            Attribute.TECHNIQUE_DEVICE: 'which device was used for the snare removal of the 6 mm polyp',
            Attribute.TARGET_PLACES: 'where the snare removal (cold snare) was done',
            Attribute.TARGET_LESION: 'which lesion the snare removal (cold snare) was done on',
            Attribute.PLACES: 'where the lesion of the snare removal (cold snare) lies',
            Attribute.MULTIPLICITY: 'whether the lesion of the snare removal (cold snare) at the sigmoid colon is one '
                                    'lesion or a group',
            Attribute.DISTINCT_FROM: 'whether the lesion of the snare removal (cold snare) at the sigmoid colon is '
                                     'distinct from another lesion',
            Attribute.SAME_AS: 'whether the lesion of the snare removal (cold snare) at the sigmoid colon is the same '
                               'as another lesion',
            Attribute.DATE_RELATION: 'when the snare removal (cold snare) of the 6 mm polyp was done',
            Attribute.STATUS: 'whether the snare removal (cold snare) of the 6 mm polyp was done',
        }
        for attribute, what in expected.items():
            with self.subTest(attribute=attribute):
                item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.SNARE, device=Device.COLD_SNARE, lesion=POLYP,
                                 place=Landmark.SIGMOID_COLON, attribute=attribute, statements=(SIGMOID, DESCENDING))
                self.assertEqual(item.question, f'Statements in the document disagree about {what}: “The polyp was '
                                                'in the sigmoid colon.” and “The polyp was in the descending colon.”. '
                                                'Which is correct for this encounter?')

    def test_the_session_tables(self):
        self.assertEqual(wording.SESSION_ATTRIBUTES, frozenset({
            Attribute.EXAMINATION, Attribute.ENCOUNTER, Attribute.TRACT, Attribute.APPROACH, Attribute.THROUGH,
            Attribute.REACHED, Attribute.DEVICE_REACHED, Attribute.REACHED_ANATOMY, Attribute.COMPLETION,
            Attribute.STATIONS, Attribute.PART_OF_SESSION}))
        for attribute, phrase in wording.ATTRIBUTE_PHRASES.items():
            with self.subTest(attribute=attribute):
                self.assertEqual('{session}' in phrase, attribute in wording.SESSION_ATTRIBUTES)
                if attribute in wording.SESSION_ATTRIBUTES:
                    self.assertNotIn('{act}', phrase)

    # P7: the module's docstring names the engine import it makes, and what it is for
    def test_the_docstring_names_the_engine_anatomy_import(self):
        doc = ast.get_docstring(ast.parse(WORDING.read_text(encoding='utf-8')))
        self.assertIn('engine import anatomy as engine_anatomy', WORDING.read_text(encoding='utf-8'))
        self.assertNotIn('catalogue and types, for its slot types only', ' '.join(doc.split()))
        self.assertIn("the engine's text-free anatomy for one refusal - STRUCTURE_PLACE refuses a place that "
                      "STRUCT:pfc does not set apart", ' '.join(doc.split()))

    def test_round_two_sentences_name_no_provider_or_model_or_cause(self):
        sentences = []
        for family in (None, *SessionKind):
            for attribute in Attribute:
                for slots in ({'statements': (UPPER, LOWER)}, {'statements': (UPPER,)}, {'words': FNA}):
                    item = r2_worded(M.CONFLICT_ATTRIBUTE, act=Kind.FNA, family=family, attribute=attribute,
                                     device=Device.BALLOON, lesion=POLYP, place=Landmark.SIGMOID_COLON, **slots)
                    sentences += [item.question, item.reason]
        self.assertGreater(len(sentences), 3000)
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                self.assertIsNone(customer_api.FORBIDDEN.search(sentence))
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(sentence)], [])
                self.assertFalse([cause for cause in customer_api.HELD_FACT_CAUSES if cause in sentence])
                self.assertFalse(re.search(r'[{}]|\bNone\b|“”|\s{2}|\(\)', sentence), sentence)
                for quoted in re.findall(r'“([^”]*)”', sentence):
                    self.assertIn(quoted.rstrip('…'), R2_TEXT)


# --- D246 (repair r3c): wording's half of "every item the engine makes is worded" (the lead's L1; refute-5c-r2 R2-03;
# r4a Q4 option (a) and R4 (a); D160 (3)) ------------------------------------------------------------------------------

D246_TEXT = ('The old biliary stent was removed. A new plastic stent was placed. Retroflexion was performed in the '
             'rectum. No polyps were removed. A cold snare polypectomy of the 6 mm sigmoid polyp was performed. The '
             'patient tolerated the procedure well and the scope was withdrawn slowly while the mucosa of the rectum, '
             'the sigmoid colon, the descending colon and the transverse colon was inspected again.')


def d246(phrase):
    start = D246_TEXT.index(phrase)
    return (Span(start, start + len(phrase)),)


OLD_STENT = d246('The old biliary stent was removed.')
NEW_STENT = d246('A new plastic stent was placed.')
RETRO = d246('Retroflexion was performed in the rectum.')
NO_POLYPS = d246('No polyps were removed.')
SNARED = d246('A cold snare polypectomy of the 6 mm sigmoid polyp was performed.')
INSPECTED = d246('The patient tolerated the procedure well and the scope was withdrawn slowly while the mucosa of the '
                 'rectum, the sigmoid colon, the descending colon and the transverse colon was inspected again.')
SPACE = (Span(D246_TEXT.index('. N') + 1, D246_TEXT.index('. N') + 2),)  # a single space: units that hold no words
UNACCOUNTED = "which CPT Studio's reading of the document does not account for"
CLEAN = r'[{}]|\bNone\b|“”|\s{2}|\(\)'
# the earlier ids (pristine, 22dcf0c9 + the waves 5-6 diff): their values in order, and each entry's (fact, kind, rank)
EARLIER_IDS = 'ca7e3f4026b60e9e2b4dbc5ebb278587944948725c0ff7750007af161687e7dd'
EARLIER_ENTRIES = '1535daca5ebe1392fc35d3d44b7c0bc3abbef6d4fcae4d0a8c0599151ec09e25'


def d246_worded(message, **slots):
    return wording.build(message, wording.Slots(**slots), D246_TEXT)


def digest(rows):
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def d246_sentences():
    """Every sentence a D246 form or id makes over its slots' range (each kind, family, count of codes; with units, a
    long unit and none), each with its label: the customer scans' input (here and tests/v2/test_update_customer.py)."""
    out = []

    def add(label, message, **slots):
        item = d246_worded(message, **slots)
        out.extend(((f'{label}.question', item.question), (f'{label}.reason', item.reason)))
    for kind in (None, *Kind):
        for name, words in (('none', ()), ('unit', RETRO), ('long', INSPECTED)):
            add(f'synthetic_act[{kind}, {name}]', M.SYNTHETIC_ACT, act=kind, words=words)
    for kind in Kind:
        add(f'doubt[{kind}]', M.DOUBT, act=kind)
        add(f'doubt[{kind}, statement]', M.DOUBT, act=kind, statements=(NO_POLYPS,))
        add(f'statement_scope[{kind}]', M.STATEMENT_SCOPE, act=kind)
        add(f'statement_scope[{kind}, words]', M.STATEMENT_SCOPE, act=kind, words=SNARED)
    for family in (None, *SessionKind):
        for codes in (('45386',), ('45385', '45386'), ('45380', '45385', '45386')):
            add(f'base_included[{family}, {codes}]', M.BASE_INCLUDED, code='45378', family=family, codes=codes)
            add(f'separate_em[{family}, {codes}]', M.SEPARATE_EM, code='99213', family=family, codes=codes)
    for act in wording.STENT_KINDS:
        for whole in wording.STENT_KINDS - {act}:
            for words, whole_words in (((), ()), (OLD_STENT, ()), ((), NEW_STENT)):
                add(f'same_duct[{act}, {whole}, {bool(words)}, {bool(whole_words)}]', M.SAME_DUCT, act=act, whole=whole,
                    words=words, whole_words=whole_words)
    return out


class D246Forms(SimpleTestCase):
    """D246 (repair r3c): each new form's and the new id's exact text, the earlier forms beside them unchanged, the
    refusals that stay, and the customer scan over every new sentence."""

    def test_synthetic_act_is_appended_and_every_earlier_entry_kept(self):
        values = [member.value for member in M]
        self.assertEqual(values[61], 'synthetic_act')  # round w8r's two ids follow it (D254Total)
        self.assertEqual(digest(values[:61]), EARLIER_IDS)  # every earlier id in its place
        spec = wording.MESSAGES[M.SYNTHETIC_ACT]
        self.assertEqual((spec.fact, spec.kind, spec.rank, spec.needs), ('performed_status', ItemKind.QUESTION, 2, ()))
        earlier = [message for message in wording.MESSAGES if message.value in values[:61]]
        self.assertEqual(digest([[message.value, wording.MESSAGES[message].fact, wording.MESSAGES[message].kind.value,
                                  wording.MESSAGES[message].rank] for message in earlier]), EARLIER_ENTRIES)
        # the needs: D254 rule 1 (round w8r) narrows every entry to the slots its items carry by construction - pinned
        # in D254Total.test_needs_name_only_carried_slots
        requirements.Item(requirements.Rank(2), requirements.FactKey('performed_status'))  # RANK row 2 holds it

    # BASE_INCLUDED's codes form (5c's R8; the lead's L1: render_sweep2's base_included refusals)
    def test_base_included_names_the_codes_when_no_act_is_in_doubt(self):
        item = d246_worded(M.BASE_INCLUDED, code='45378', family=SessionKind.COLONOSCOPY, codes=('45386',))
        self.assertEqual((item.message, item.fact, item.kind), (M.BASE_INCLUDED, 'base_included', ItemKind.QUESTION))
        self.assertEqual(item.question, 'Is 45378 reported separately from 45386 for this examination?')
        self.assertEqual(item.reason, '45386 is also proposed for the documented colonoscopy; 45378 is normally not '
                                      'reported separately from it (internal profile rule; NCCI procedure-to-procedure '
                                      'edits are not connected). Held for the reviewer, not excluded.')
        item = d246_worded(M.BASE_INCLUDED, code='43235', family=SessionKind.EGD, codes=('43239', '43249'))
        self.assertEqual(item.question, 'Is 43235 reported separately from 43239, 43249 for this examination?')
        self.assertEqual(item.reason, '43239 and 43249 are also proposed for the documented upper endoscopy; 43235 is '
                                      'normally not reported separately from them (internal profile rule; NCCI '
                                      'procedure-to-procedure edits are not connected). Held for the reviewer, not '
                                      'excluded.')
        item = d246_worded(M.BASE_INCLUDED, code='45378', codes=('45380', '45385', '45386'))
        self.assertEqual(item.question, 'Is 45378 reported separately from 45380, 45385, 45386 for this examination?')
        self.assertEqual(item.reason, '45380, 45385 and 45386 are also proposed for the documented procedure; 45378 is '
                                      'normally not reported separately from them (internal profile rule; NCCI '
                                      'procedure-to-procedure edits are not connected). Held for the reviewer, not '
                                      'excluded.')
        # a code named twice is one code
        self.assertEqual(d246_worded(M.BASE_INCLUDED, code='45378', family=SessionKind.COLONOSCOPY,
                                     codes=('45386', '45386')),
                         d246_worded(M.BASE_INCLUDED, code='45378', family=SessionKind.COLONOSCOPY, codes=('45386',)))
        # the question is BASE_EXPLAINED's over the same codes; the reason never states that an act they account for
        # was done (rule (a) alone is no fact: a proposal with no act documented is one)
        for codes in (('45386',), ('45385', '45386')):
            explained = d246_worded(M.BASE_EXPLAINED, code='45378', family=SessionKind.COLONOSCOPY, codes=codes)
            item = d246_worded(M.BASE_INCLUDED, code='45378', family=SessionKind.COLONOSCOPY, codes=codes)
            self.assertEqual(item.question, explained.question)
            for phrase in ('has interventions', 'includes', 'documented as', 'performed', ' done', IN_DOUBT_WORDS):
                self.assertNotIn(phrase, item.reason)

    def test_base_included_keeps_its_act_form_and_refuses_neither(self):
        expected = ('Is 45378 reported separately from snare removal (stated in doubt), forceps biopsy (stated in doubt) '
                    'for this examination?',
                    'The documented colonoscopy includes snare removal (stated in doubt), forceps biopsy (stated in '
                    'doubt), which this diagnostic code does not account for (internal profile rule). Held for the '
                    'reviewer, not excluded.')
        for codes in ((), ('45385',)):  # the acts in doubt decide the form, whatever codes are named beside them
            with self.subTest(codes=codes):
                item = d246_worded(M.BASE_INCLUDED, code='45378', family=SessionKind.COLONOSCOPY,
                                   listed=(Kind.SNARE, Kind.BIOPSY), codes=codes)
                self.assertEqual((item.question, item.reason), expected)
        # D254 rule 3 (round w8r): with nothing to name, the act form over 'another act' (the act the hold rests on, no
        # kind naming it) - refused until then
        unnamed = ('Is 45378 reported separately from another act (stated in doubt) for this examination?',
                   'The documented colonoscopy includes another act (stated in doubt), which this diagnostic code does '
                   'not account for (internal profile rule). Held for the reviewer, not excluded.')
        for slots in ({}, {'listed': (), 'codes': ()}, {'possible': (Kind.SNARE,)}, {'listed': (Kind.OTHER,)}):
            with self.subTest(slots=slots):
                item = d246_worded(M.BASE_INCLUDED, code='45378', family=SessionKind.COLONOSCOPY, **slots)
                self.assertEqual((item.question, item.reason), unnamed)
        with self.assertRaises(ValueError):
            d246_worded(M.BASE_INCLUDED, codes=('45386',))  # the base code itself is still needed (CARRIED)

    # SEPARATE_EM's codes form (refute-5c-r2 R2-03: a procedure day with no act to list)
    def test_separate_em_names_the_same_day_codes_when_the_day_has_no_act_to_list(self):
        item = d246_worded(M.SEPARATE_EM, code='99213', family=SessionKind.OFFICE_EM, codes=('45386',))
        self.assertEqual((item.message, item.fact, item.kind), (M.SEPARATE_EM, 'separate_em', ItemKind.QUESTION))
        self.assertEqual(item.question, 'Was a significant, separately identifiable evaluation and management service '
                                        'performed on the date of service, beyond the usual pre-procedure assessment? If '
                                        'so, add that documentation.')
        self.assertEqual(item.question, wording.SEPARATE_EM_QUESTION)
        self.assertEqual(item.reason, '45386 is proposed for the same date; a significant, separately identifiable E/M '
                                      'service is not established by this document.')
        item = d246_worded(M.SEPARATE_EM, code='99213', codes=('45378', '45386'))
        self.assertEqual(item.reason, '45378 and 45386 are proposed for the same date; a significant, separately '
                                      'identifiable E/M service is not established by this document.')
        item = d246_worded(M.SEPARATE_EM, code='99214', codes=('45378', '45380', '45386', '45378'))
        self.assertEqual(item.reason, '45378, 45380 and 45386 are proposed for the same date; a significant, separately '
                                      'identifiable E/M service is not established by this document.')
        for sentence in (item.question, item.reason):
            self.assertNotIn('documented as performed', sentence)  # proposed, never stated as done

    def test_separate_em_keeps_its_act_form_and_refuses_neither(self):
        item = d246_worded(M.SEPARATE_EM, code='99213', listed=(Kind.SNARE,), possible=(Kind.BIOPSY,), codes=('45385',))
        self.assertEqual(item.reason, 'Snare removal is documented as performed on the same date; forceps biopsy is '
                                      'possibly performed on the same date (its performance is not established); a '
                                      'significant, separately identifiable E/M service is not established by this '
                                      'document.')
        self.assertEqual(item, d246_worded(M.SEPARATE_EM, code='99213', listed=(Kind.SNARE,), possible=(Kind.BIOPSY,)))
        item = d246_worded(M.SEPARATE_EM, code='99213', possible=(Kind.BIOPSY,), codes=('45380',))
        self.assertEqual(item.reason, 'Forceps biopsy is possibly performed on the same date (its performance is not '
                                      'established); a significant, separately identifiable E/M service is not '
                                      'established by this document.')
        # D254 rule 3 (round w8r): with nothing to name, SEPARATE_EM_UNNAMED - refused until then
        for slots in ({}, {'codes': ()}, {'group': (Kind.SNARE,)}):
            with self.subTest(slots=slots):
                item = d246_worded(M.SEPARATE_EM, code='99213', **slots)
                self.assertEqual((item.question, item.reason), (wording.SEPARATE_EM_QUESTION,
                                                                wording.SEPARATE_EM_UNNAMED))

    # DOUBT, SAME_DUCT and STATEMENT_SCOPE: an act or a statement with no units, named without a quote (r4a Q4 (a))
    def test_doubt_names_an_act_with_no_units_without_a_quote(self):
        item = d246_worded(M.DOUBT, act=Kind.OTHER)  # r4a Q4's input p23: an unlisted act of no kind, units ()
        self.assertEqual((item.message, item.fact, item.kind), (M.DOUBT, 'performed_status', ItemKind.QUESTION))
        # D254 rule 2 (round w8r): an act no kind names is 'another act', its article included
        self.assertEqual(item.question, 'Confirm whether another act was done on the date of service.')
        self.assertEqual(item.reason, 'The document leaves another act in doubt.')
        self.assertEqual(item, d246_worded(M.DOUBT))  # a kind not established: the same label
        item = d246_worded(M.DOUBT, act=Kind.STENT_REMOVAL)
        self.assertEqual((item.question, item.reason), ('Confirm whether the stent removal was done on the date of '
                                                        'service.', 'The document leaves the stent removal in doubt.'))
        item = d246_worded(M.DOUBT, act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY)  # UnitlessEntries' shape
        # restated for D281 (step f3w; build list B6, G3-27): the held session's examination is asked by row 7's done
        self.assertEqual((item.question, item.reason), ('Confirm whether the colonoscopy is documented as performed, in '
                                                        'full or in part, on the date of service.',
                                                        'The document leaves the colonoscopy in doubt.'))
        # the doubt's passage, when it has units, is still the reason's quote
        item = d246_worded(M.DOUBT, act=Kind.STENT_REMOVAL, statements=(OLD_STENT,))
        self.assertEqual((item.question, item.reason), ('Confirm whether the stent removal was done on the date of '
                                                        'service.', 'The document leaves the stent removal in doubt: “The '
                                                        'old biliary stent was removed.”.'))

    def test_doubt_with_units_is_unchanged_and_units_with_no_words_are_refused(self):
        expected = ('Confirm whether the stent removal (“The old biliary stent was removed.”) was done on the date of '
                    'service.', 'The document leaves the stent removal in doubt: “The old biliary stent was removed.”.')
        self.assertEqual(expected, (wording.doubt_question('stent removal', 'The old biliary stent was removed.'),
                                    wording.doubt_reason('stent removal', 'The old biliary stent was removed.')))
        for slots in ({}, {'statements': ((),)}):  # a passage with no units: the act's own words stand in
            with self.subTest(slots=slots):
                item = d246_worded(M.DOUBT, act=Kind.STENT_REMOVAL, words=OLD_STENT, **slots)
                self.assertEqual((item.question, item.reason), expected)
        item = d246_worded(M.DOUBT, act=Kind.STENT_REMOVAL, words=OLD_STENT, statements=(NEW_STENT,))
        self.assertEqual(item.reason, 'The document leaves the stent removal in doubt: “A new plastic stent was '
                                      'placed.”.')
        for slots in ({'words': SPACE}, {'words': OLD_STENT, 'statements': (SPACE,)}, {'statements': (SPACE,)}):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                d246_worded(M.DOUBT, act=Kind.STENT_REMOVAL, **slots)
        item = d246_worded(M.DOUBT, words=OLD_STENT)  # D254 rule 2: a kind not established is 'another act'
        self.assertEqual(item.question, 'Confirm whether another act (“The old biliary stent was removed.”) was done on '
                                        'the date of service.')

    def test_same_duct_names_an_act_with_no_units_without_a_quote(self):
        base = dict(code='43274', act=Kind.STENT_REMOVAL, whole=Kind.STENT)
        rule = ('CPT Studio could not confirm from the document in which duct the stent removal was done. A stent '
                'removed and replaced in the same duct at one session is one stent exchange (43276), not a removal '
                '(43275) and a placement (43274). Held for the reviewer, not excluded.')
        expected = {
            ((), NEW_STENT): 'Were the stent removal and the stent placement (“A new plastic stent was placed.”) done in '
                             'the same duct?',  # p23's 43274: the kept unlisted removal, no units
            (OLD_STENT, ()): 'Were the stent removal (“The old biliary stent was removed.”) and the stent placement done '
                             'in the same duct?',
            ((), ()): 'Were the stent removal and the stent placement done in the same duct?',
            (OLD_STENT, NEW_STENT): 'Were the stent removal (“The old biliary stent was removed.”) and the stent '
                                    'placement (“A new plastic stent was placed.”) done in the same duct?',  # unchanged
        }
        for (words, whole_words), question in expected.items():
            with self.subTest(words=words, whole_words=whole_words):
                item = d246_worded(M.SAME_DUCT, words=words, whole_words=whole_words, **base)
                self.assertEqual((item.fact, item.kind), ('act_target', ItemKind.QUESTION))
                self.assertEqual((item.question, item.reason), (question, rule))
        item = d246_worded(M.SAME_DUCT, code='43276', act=Kind.STENT, whole=Kind.STENT_EXCHANGE)
        self.assertEqual(item.question, 'Were the stent placement and the stent exchange done in the same duct?')
        for changes in ({'words': SPACE}, {'whole_words': SPACE}):  # units that hold no words: a binding failure
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                d246_worded(M.SAME_DUCT, **{**base, 'words': OLD_STENT, 'whole_words': NEW_STENT, **changes})
        item = d246_worded(M.SAME_DUCT, code='43274')  # D254: neither act's kind given - 'another act' twice
        self.assertEqual(item.question, 'Were another act and another act done in the same duct?')

    def test_statement_scope_names_a_statement_with_no_units_without_a_quote(self):
        reason = 'CPT Studio could not confirm whether a statement in the document applies to the snare removal.'
        for statements in ((), ((),), ((), ())):  # rule 4's unit-less doubt: the statement has no units
            with self.subTest(statements=statements):
                item = d246_worded(M.STATEMENT_SCOPE, code='45385', act=Kind.SNARE, words=SNARED, statements=statements)
                self.assertEqual((item.fact, item.kind), ('statement_scope', ItemKind.QUESTION))
                self.assertEqual(item.question, 'Does a statement in the document apply to the snare removal (“A cold '
                                                'snare polypectomy of the 6 mm sigmoid polyp was performed.”)?')
                self.assertEqual(item.reason, reason)
        item = d246_worded(M.STATEMENT_SCOPE, act=Kind.SNARE)  # nor the act: v1's "this code accounts for" form
        self.assertEqual((item.question, item.reason),
                         ('Does a statement in the document apply to the snare removal this code accounts for?', reason))

    def test_statement_scope_quotes_every_statement_with_units_as_before(self):
        item = d246_worded(M.STATEMENT_SCOPE, act=Kind.SNARE, words=SNARED, statements=((), NO_POLYPS))
        self.assertEqual(item.question, 'Does “No polyps were removed.” apply to the snare removal (“A cold snare '
                                        'polypectomy of the 6 mm sigmoid polyp was performed.”)?')
        self.assertEqual(item.reason, 'The document states “No polyps were removed.”; CPT Studio could not confirm from '
                                      'the document whether that statement applies to the snare removal.')
        self.assertEqual(item, d246_worded(M.STATEMENT_SCOPE, act=Kind.SNARE, words=SNARED, statements=(NO_POLYPS,)))
        item = d246_worded(M.STATEMENT_SCOPE, act=Kind.SNARE, statements=(NO_POLYPS, OLD_STENT))
        self.assertEqual((item.question, item.reason), (
            wording.scope_question('No polyps were removed.', 'snare removal', '', whole=True,
                                   also=['The old biliary stent was removed.']),
            wording.scope_reason('No polyps were removed.', 'snare removal', whole=True,
                                 also=['The old biliary stent was removed.'])))
        self.assertEqual(item.question, 'Does “No polyps were removed.” or “The old biliary stent was removed.” apply to '
                                        'the snare removal this code accounts for?')
        for slots in ({'statements': (SPACE,)}, {'statements': (NO_POLYPS, SPACE)}, {'words': SPACE}):
            with self.subTest(slots=slots), self.assertRaises(ValueError):  # binding failures
                d246_worded(M.STATEMENT_SCOPE, **{'act': Kind.SNARE, **slots})
        item = d246_worded(M.STATEMENT_SCOPE, statements=(NO_POLYPS,))  # D254 rule 2: 'another act'
        self.assertEqual(item.question, 'Does “No polyps were removed.” apply to another act this code accounts for?')

    # SYNTHETIC_ACT (r4a R4 (a)): 3.2.6 rule 3's synthetic act, its own kind and its own unit
    def test_synthetic_act_names_its_kind_and_quotes_its_own_unit(self):
        item = d246_worded(M.SYNTHETIC_ACT, code='43274', act=Kind.STENT_REMOVAL, words=OLD_STENT)
        self.assertEqual((item.message, item.fact, item.kind), (M.SYNTHETIC_ACT, 'performed_status', ItemKind.QUESTION))
        self.assertEqual(item.question, 'The document documents a stent removal (“The old biliary stent was removed.”), '
                                        "which CPT Studio's reading of the document does not account for. Confirm "
                                        'whether it was done on the date of service.')
        self.assertEqual(item.reason, 'The document documents a stent removal (“The old biliary stent was removed.”), '
                                      "which CPT Studio's reading of the document does not account for. Held for the "
                                      'reviewer, not excluded.')
        self.assertNotIn('doubt', item.question + item.reason)  # never DOUBT's "leaves ... in doubt"
        slots = wording.Slots(code='43274', act=Kind.STENT_REMOVAL, words=OLD_STENT)
        self.assertEqual(wording.question(M.SYNTHETIC_ACT, slots, D246_TEXT), item.question)
        self.assertEqual(wording.explanation(M.SYNTHETIC_ACT, slots, D246_TEXT), item.reason)
        # D254 rule 2 (round w8r): none reads 'another act' (questions.fill names an entry of no kind Kind.OTHER)
        for kind in (None, Kind.OTHER):
            with self.subTest(kind=kind):
                item = d246_worded(M.SYNTHETIC_ACT, act=kind, words=RETRO)
                self.assertEqual(item.question, 'The document documents another act (“Retroflexion was performed in the '
                                                f'rectum.”), {UNACCOUNTED}. Confirm whether it was done on the date of '
                                                'service.')
                self.assertEqual(item.reason, 'The document documents another act (“Retroflexion was performed in the '
                                              f'rectum.”), {UNACCOUNTED}. Held for the reviewer, not excluded.')
        item = d246_worded(M.SYNTHETIC_ACT, act=Kind.EMR, words=RETRO)
        self.assertTrue(item.question.startswith('The document documents an endoscopic mucosal resection (“'))
        for kind in Kind:
            if kind is Kind.OTHER:
                continue
            with self.subTest(kind=kind):
                item = d246_worded(M.SYNTHETIC_ACT, act=kind, words=RETRO)
                label = wording.with_article(wording.event_kind_label(kind.value))
                self.assertEqual(item.question, f'The document documents {label} (“Retroflexion was performed in the '
                                                f'rectum.”), {UNACCOUNTED}. Confirm whether it was done on the date of '
                                                'service.')

    def test_synthetic_act_names_only_its_kind(self):
        """An unlisted examination is an examination, never the session's service; no device, place or lesion is named
        - none is a fact of an entry CPT Studio's reading does not hold."""
        plain = d246_worded(M.SYNTHETIC_ACT, act=Kind.EXAMINATION, words=RETRO)
        self.assertEqual(plain.question, 'The document documents an examination (“Retroflexion was performed in the '
                                         f'rectum.”), {UNACCOUNTED}. Confirm whether it was done on the date of service.')
        for family in SessionKind:
            with self.subTest(family=family):
                item = d246_worded(M.SYNTHETIC_ACT, act=Kind.EXAMINATION, family=family, words=RETRO,
                                   device=Device.COLD_SNARE, place=Landmark.RECTUM, lesion=d246('6 mm sigmoid polyp'),
                                   code='45378', group=(Kind.SNARE,))
                self.assertEqual(item, plain)

    def test_synthetic_act_with_no_units_and_a_long_unit(self):
        item = d246_worded(M.SYNTHETIC_ACT, act=Kind.STENT_REMOVAL)  # no units: named, nothing quoted (D160 (3))
        self.assertEqual(item.question, f'The document documents a stent removal, {UNACCOUNTED}. Confirm whether it was '
                                        'done on the date of service.')
        self.assertEqual(item.reason, f'The document documents a stent removal, {UNACCOUNTED}. Held for the reviewer, '
                                      'not excluded.')
        item = d246_worded(M.SYNTHETIC_ACT)  # D254 rule 2 (round w8r): 'another act'
        self.assertEqual(item.question, f'The document documents another act, {UNACCOUNTED}. Confirm whether it was done '
                                        'on the date of service.')
        long = wording.span_text(D246_TEXT, INSPECTED)
        self.assertGreater(len(long), 140)
        item = d246_worded(M.SYNTHETIC_ACT, act=Kind.EXAMINATION, words=INSPECTED)  # cut as every item's quotes are
        self.assertEqual(item.question, f'The document documents an examination ({wording.quote(long, 120)}), '
                                        f'{UNACCOUNTED}. Confirm whether it was done on the date of service.')
        self.assertEqual(item.reason, f'The document documents an examination ({wording.quote(long, 140)}), '
                                      f'{UNACCOUNTED}. Held for the reviewer, not excluded.')
        self.assertTrue(wording.quote(long, 120).endswith('…”'))
        for words in (SPACE, (Span(0, len(D246_TEXT) + 1),)):  # units with no words, or past the text: refused
            with self.subTest(words=words), self.assertRaises(ValueError):
                d246_worded(M.SYNTHETIC_ACT, act=Kind.STENT_REMOVAL, words=words)

    def test_every_d246_sentence_is_clean_and_names_no_provider_model_or_cause(self):
        sentences = d246_sentences()
        self.assertGreater(len(sentences), 700)
        for label, sentence in sentences:
            with self.subTest(label=label):
                self.assertIsNone(customer_api.FORBIDDEN.search(sentence), sentence)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(sentence)], [], sentence)
                self.assertFalse([cause for cause in customer_api.HELD_FACT_CAUSES if cause in sentence], sentence)
                self.assertFalse(re.search(CLEAN, sentence), sentence)
                self.assertTrue(sentence.endswith(('.', '?')) and sentence == sentence.strip(), sentence)
                for quoted in re.findall(r'“([^”]*)”', sentence):
                    self.assertIn(quoted.rstrip('…'), D246_TEXT)

    def test_the_codes_forms_read_no_text(self):
        """BASE_INCLUDED and SEPARATE_EM are TEXT_FREE (overlay.TEXT_FREE: read time words them with no text): their codes
        forms build the same words over any text, the empty one included."""
        for message, slots in ((M.BASE_INCLUDED, dict(code='45378', family=SessionKind.COLONOSCOPY, codes=('45386',))),
                               (M.BASE_INCLUDED, dict(code='99213', family=SessionKind.OFFICE_EM, codes=('99214',))),
                               (M.SEPARATE_EM, dict(code='99213', family=SessionKind.OFFICE_EM,
                                                    codes=('45378', '45386')))):
            with self.subTest(message=message, slots=slots):
                worded = [wording.build(message, wording.Slots(**slots), text) for text in ('', D246_TEXT, TEXT)]
                self.assertEqual(worded[0], worded[1])
                self.assertEqual(worded[0], worded[2])
        item = wording.build(M.BASE_INCLUDED, wording.Slots(code='99213', family=SessionKind.OFFICE_EM,
                                                            codes=('99214',)), '')
        self.assertEqual(item.reason, '99214 is also proposed for the documented office / outpatient visit; 99213 is '
                                      'normally not reported separately from it (internal profile rule; NCCI '
                                      'procedure-to-procedure edits are not connected). Held for the reviewer, not '
                                      'excluded.')

    def test_the_docstring_names_d246(self):
        doc = ' '.join(ast.get_docstring(ast.parse(WORDING.read_text(encoding='utf-8'))).split())
        self.assertIn('**D246**', doc)
        self.assertIn('SYNTHETIC_ACT (rank 2, performed_status, a question)', doc)
        self.assertIn("D160 (3)'s rule", doc)


IN_DOUBT_WORDS = wording.IN_DOUBT.strip()


class D246EngineItems(SimpleTestCase):
    """The engine's own unit-less items (refute-r4a-r1 F5; r4a Q4's input p23; step r4a's UnitlessEntries shapes): a kept
    unlisted act or doubt whose units pass 2 named none the reader knows holds its code with one item, which wording now
    words - naming the act, quoting nothing of the entry. Whatever id step r4a maps the item to (DOUBT today, SYNTHETIC_ACT
    once r4a maps the synthetic act's witness to it), the renderer's call never refuses."""

    FILLER = ('Synthetic filler words for the item sentences. ' * 60)[:2400]

    @staticmethod
    def slots(fill):
        """jobs._slots_of: the Slots of an item's Fill, field for field (the Bundling by value)."""
        import dataclasses
        values = {field.name: getattr(fill, field.name) for field in dataclasses.fields(fill)}
        if values.get('bundling') is not None:
            values['bundling'] = wording.Bundling(values['bundling'].value)
        return wording.Slots(**values)

    def items(self):
        from studio.interpretation.contract import types as ct
        from studio.interpretation.engine import evaluate as EV
        from studio.interpretation.engine.types import UnlistedStatement
        from tests.v2.evaluate_fixtures import Doc, X, sup, unit

        def colonoscopy(kind, what):
            doc = Doc()
            doc.session(1, SessionKind.COLONOSCOPY, reached=[sup(Extent.CECUM)])
            doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], device=sup(Device.COLD_SNARE))
            doc.unlisted.append(UnlistedStatement(units=(), what=what, kind=kind, session=X(1)))
            return doc.build()

        def ercp(kind, what):
            doc = Doc()
            doc.session(1, SessionKind.ERCP)
            doc.exam(1)
            doc.act(2, Kind.STENT, duct=sup(ct.Duct.BILIARY))
            doc.unlisted.append(UnlistedStatement(units=(), what=what, kind=kind, session=X(1)))
            return doc.build()

        cases = (('45385', colonoscopy(Kind.EXAMINATION, ct.UnlistedWhat.ACT), ()),
                 ('45385', colonoscopy(None, ct.UnlistedWhat.ACT), ()),  # p23: no kind
                 ('45385', colonoscopy(None, ct.UnlistedWhat.DOUBT), ()),
                 ('43274', ercp(Kind.STENT_REMOVAL, ct.UnlistedWhat.DOUBT), (unit(2),)),
                 ('43274', ercp(None, ct.UnlistedWhat.ACT), (unit(2),)),  # p23's 43274
                 ('43274', ercp(Kind.STENT_REMOVAL, ct.UnlistedWhat.ACT), (unit(2),)))
        for code, R, kept in cases:
            found = EV.item(code, kept, R, EV.decide(code, kept, R))
            yield code, R, found

    def test_unit_less_entries_are_worded_without_a_quote(self):
        unit_less = []
        for code, R, found in self.items():
            with self.subTest(code=code, unlisted=R.unlisted):
                self.assertIsNotNone(found)
                worded = wording.build(wording.Message(found.message.value), self.slots(found.fill), self.FILLER)
                for sentence in (worded.question, worded.reason):
                    self.assertFalse(re.search(CLEAN, sentence), sentence)
                    for quoted in re.findall(r'“([^”]*)”', sentence):
                        self.assertIn(quoted.rstrip('…'), self.FILLER)  # only a filed act's own unit, if any
                if found.fill.words:
                    continue  # the act the item names has units (a filed act): quoted as before
                unit_less.append((code, found.message.value))
                if found.message.value in ('doubt', 'synthetic_act'):
                    self.assertNotIn('“', worded.question + worded.reason)  # nothing of the entry is quoted
                elif found.message.value == 'same_duct':
                    # only the filed placement's own unit; a kindless unlisted counterpart is 'another act' (D254 rule
                    # 2: repair r4a's request R2, applied by the integration)
                    named = 'another act' if found.fill.act is Kind.OTHER else 'the stent removal'
                    self.assertTrue(worded.question.startswith(f'Were {named} and the stent placement (“'),
                                    worded.question)
        # On this tree five of the six cases are the unit-less shape wording refused before D246 - three DOUBT items
        # (SYNTHETIC_ACT once step r4a maps the synthetic act's witness to it) and two SAME_DUCT items; the kind-less
        # doubt beside the filed snare is an item about the snare, which has units. The engine's choice of item is step
        # r4a's and may move this round, so the test asserts only that each kind of unit-less item is exercised (never
        # vacuous) - every one of them is worded above, whatever id names it.
        self.assertTrue(any(message == 'same_duct' for _, message in unit_less), unit_less)
        self.assertTrue(any(message in ('doubt', 'synthetic_act') for _, message in unit_less), unit_less)


# --- D254, D257, D258, D253 QX (ii) and D255 (repair r3c of round w8r) -------------------------------------------------

# the statements' units come first and in a row, so a passage made of several of them (UNLISTED_EVIDENCE's) is the
# document's own words, its runs joined by the one space between them
D254_TEXT = ('No polyps were removed. It is not known whether she had a colonoscopy before. The old biliary stent was '
             'removed. A new plastic stent was placed. The 6 mm sigmoid polyp was seen. The scope was advanced to the '
             'ileum. The enteroscope entered through the stoma. The patient tolerated the procedure well and the scope '
             'was withdrawn slowly while the mucosa of the rectum, the sigmoid colon, the descending colon and the '
             'transverse colon was inspected again.')


def u(phrase):
    start = D254_TEXT.index(phrase)
    return (Span(start, start + len(phrase)),)


U_OLD = u('The old biliary stent was removed.')
U_NEW = u('A new plastic stent was placed.')
U_POLYP = u('6 mm sigmoid polyp')
U_SEEN = u('The 6 mm sigmoid polyp was seen.')
U_NONE = u('No polyps were removed.')
U_REACH = u('The scope was advanced to the ileum.')
U_STOMA = u('The enteroscope entered through the stoma.')
U_PRIOR = u('It is not known whether she had a colonoscopy before.')
U_LONG = u('The patient tolerated the procedure well and the scope was withdrawn slowly while the mucosa of the rectum, '
           'the sigmoid colon, the descending colon and the transverse colon was inspected again.')
FIELD_NAMES = tuple(field for field in wording.Slots.__dataclass_fields__)
# Each slot's values, drawn from its own type (every member of an enumeration; spans that are units of D254_TEXT -
# one, several, a long one cut by the quotes; a statement with no units among the statements; duplicates).
POOLS = {
    'code': ('45378', '43237', '44380', '0001U'),
    'act': tuple(Kind), 'whole': tuple(Kind), 'unlisted_kind': tuple(Kind), 'device': tuple(Device),
    'place': tuple(Landmark), 'family': tuple(SessionKind), 'whole_family': tuple(SessionKind),
    'technique': tuple(TechniqueClass), 'stated': tuple(TechniqueClass), 'site': tuple(SiteClass),
    'exam_class': tuple(EusClass), 'enteroscopy_class': tuple(EnteroscopyClass), 'reached': tuple(Extent),
    'owner': tuple(Owner), 'tract': tuple(Tract), 'required_tract': tuple(Tract), 'approach': tuple(Approach),
    'bundling': tuple(wording.Bundling), 'attribute': tuple(Attribute), 'unlisted_what': tuple(UnlistedWhat),
    'incomplete': (True,), 'both': (True,), 'whole_possible': (True,),
    'lesion': (U_POLYP, U_SEEN), 'words': (U_OLD, U_OLD + U_NEW, U_LONG),
    'whole_words': (U_NEW, U_LONG), 'approach_words': (U_STOMA, U_REACH),
    'statements': ((U_NONE,), (U_NONE, U_PRIOR), (U_NONE, U_PRIOR, U_OLD), ((),), ((), U_PRIOR), (U_NONE, U_NONE),
                   (U_LONG,)),
    'group': (*((kind,) for kind in Kind), (Kind.SNARE, Kind.EMR), (Kind.OTHER, Kind.CLIP)),
    'listed': (*((kind,) for kind in Kind), (Kind.SNARE, Kind.OTHER), (Kind.OTHER, Kind.OTHER)),
    'possible': (*((kind,) for kind in Kind), (Kind.BIOPSY, Kind.OTHER)),
    'stations': (*((station,) for station in Station), (Station.ESOPHAGUS, Station.STOMACH),
                 (Station.ESOPHAGUS, Station.STOMACH, Station.DUODENUM)),
    'denied': tuple((station,) for station in Station),
    'approaches': (*((approach,) for approach in Approach), (Approach.THROUGH_STOMA, Approach.THROUGH_POUCH)),
    'possible_approaches': (*((approach,) for approach in Approach), (Approach.THROUGH_STOMA, Approach.THROUGH_POUCH)),
    'codes': (('45385',), ('45385', '45386'), ('45385', '45385')),
    'held': tuple(requirements.Rank), 'techniques': (True,),  # D280.3 (step f3w): every RANK row; the flag
}
DEFAULTS = {field: getattr(wording.Slots(), field) for field in FIELD_NAMES}
_SEEN = set()
_QUIET = [0]


class Recorder(wording.Slots):
    """wording.Slots that records which of its fields a builder reads (Slots' own validation is not counted)."""
    __slots__ = ()

    def __post_init__(self):
        _QUIET[0] += 1
        try:
            wording.Slots.__post_init__(self)
        finally:
            _QUIET[0] -= 1

    def __getattribute__(self, name):
        if not _QUIET[0] and name in DEFAULTS:
            _SEEN.add(name)
        return object.__getattribute__(self, name)


def recorded(message, slots, text=D254_TEXT):
    """(the item, the slots its builder read) of ``message`` over ``slots``."""
    _SEEN.clear()
    item = wording.build(message, Recorder(**slots), text)
    return item, frozenset(_SEEN)


def value_of(field, index):
    pool = POOLS[field]
    return pool[index % len(pool)]


def combination(needs, optional, mask, shift=0):
    """The slots of one combination: the carried ones and the optional ones ``mask`` marks present, each value drawn
    from its own pool by the mask (so the combinations walk every pool)."""
    present = set(needs) | {field for bit, field in enumerate(optional) if mask >> bit & 1}
    return {field: value_of(field, mask + shift + 7 * offset) for offset, field in enumerate(FIELD_NAMES)
            if field in present}


@functools.lru_cache(maxsize=None)
def reads_of(message):
    """The slots ``message``'s builder reads (the slots D254Total varies, and proves no other slot changes its words):
    recorded over every value of every slot - all given, and only the carried ones - then over every combination of
    present and absent slots it has read, again until no combination reads a slot more (a fixpoint)."""
    needs = wording.MESSAGES[message].needs
    seen = set(needs)
    longest = max(len(pool) for pool in POOLS.values())
    for index in range(longest):
        for present in (FIELD_NAMES, needs):
            slots = {field: value_of(field, index + offset) for offset, field in enumerate(FIELD_NAMES)
                     if field in present}
            seen |= recorded(message, slots)[1]
    while True:
        optional = sorted(seen - set(needs))
        found = set(seen)
        for mask in range(2 ** len(optional)):
            found |= recorded(message, combination(needs, optional, mask, 11))[1]
        if found == seen:
            return frozenset(seen)
        seen = found


@functools.lru_cache(maxsize=None)
def d254_sentences():
    """Every sentence the combinations of D254Total make (each message, every combination of present and absent slots
    its builder reads), each with its label: the customer scans' input (here and tests/v2/test_update_customer.py)."""
    out = []
    for message in M:
        needs = wording.MESSAGES[message].needs
        optional = sorted(reads_of(message) - set(needs))
        for mask in range(2 ** len(optional)):
            item = wording.build(message, wording.Slots(**combination(needs, optional, mask)), D254_TEXT)
            out += [(f'{message.value}#{mask}.question', item.question), (f'{message.value}#{mask}.reason', item.reason)]
    return tuple(out)


NO_ARTICLE = re.compile(r'\b(?:[Tt]he|[Aa]n?|[Tt]his) another act\b')


def sentence_problems(sentence, text=D254_TEXT):
    """What makes a customer sentence unfit: empty, untrimmed, unterminated, a placeholder or a None, an empty quote or
    brackets, a doubled space, a provider or model or cause, a quote that is not the document's own words, 'another act'
    after an article, a bare 'act' label (R3C1-03's 'from act'), or an article or the label opening it uncapitalized."""
    found = []
    if not sentence or sentence != sentence.strip() or not sentence.endswith(('.', '?')):
        found.append('shape')
    if re.search(CLEAN, sentence):
        found.append('placeholder, None, empty quote or brackets, or a doubled space')
    if customer_api.FORBIDDEN.search(sentence) or [p for p in HARD if p.search(sentence)]:
        found.append('provider or model')
    if [cause for cause in customer_api.HELD_FACT_CAUSES if cause in sentence]:
        found.append('cause')
    if [q for q in re.findall(r'“([^”]*)”', sentence) if q.rstrip('…') not in ' '.join(text.split())]:
        found.append('a quote that is not the document')
    if NO_ARTICLE.search(sentence) or re.search(r'(?<!another )\bact \(stated in doubt\)|\bfrom act\b', sentence):
        found.append('the act label')
    if re.match(r'(?:another|the|an?|this)\b', sentence):
        found.append('an article or the act label opens it')
    return found


class D254Total(SimpleTestCase):
    """D254 rule 1 (and rule 4's wording half; repair r3c of round w8r): every builder words every value its slots can
    hold and refuses only a missing slot every item of its message carries by construction (MESSAGES' needs, each with
    its reason in CARRIED). The done-when: for every Message, every combination of present and absent optional slots -
    the slots its builder reads (recorded, and proved to be the only ones that change its words) - with values from the
    slots' own types, wording.build returns a non-empty question and reason, each fit for the customer."""

    NEEDS = {
        M.CONFLICT: ('act',), M.CONFLICT_FACT: ('act',), M.CONFLICT_ATTRIBUTE: ('act', 'attribute'),
        M.NOT_DOCUMENTED: ('code',), M.ATTEMPTED: ('code',), M.UNPROFILED: ('code',), M.NOT_LINKED: ('code',),
        M.RECOGNISED_ONLY: ('code', 'family'), M.UNRECONCILED: ('code',), M.ANOTHER_TRACT: ('code',),
        M.ENTEROSCOPY_ROUTE: ('code',), M.ENTEROSCOPY_APPROACH: ('code',), M.ENTEROSCOPY_CLASS: ('code',),
        M.ENTEROSCOPY_THROUGH: ('code',), M.ROUTE: ('code',), M.WALL_INJECTION: ('code',), M.TARGET: ('family',),
        M.STRUCTURE: ('code',), M.ANOTHER_STRUCTURE: ('code',), M.STRUCTURE_PLACE: ('code',), M.STATIONS: ('code',),
        M.STATION_CLASS: ('code',), M.EXTENT: ('family',), M.EXAMINATION_CLASS: ('code',), M.CANNULATION: ('family',),
        M.EM_BASIS: ('family',), M.BASE_INCLUDED: ('code',), M.BASE_EXPLAINED: ('code',), M.BASE_WITHIN: ('code',),
        M.COMPETING: ('code',), M.SETTING: ('family',), M.PATIENT_STATUS: ('family',),
        M.UNLISTED_EVIDENCE: ('code', 'unlisted_what'), M.EXAMINATION_ROUTE: ('code', 'exam_class'),
        M.EXAMINATION_APPROACH: ('code', 'exam_class'),
        M.DIGITAL_SCOPE: ('held', 'act'), M.ADDON: ('code',),  # D280.3 and D284 (step f3w)
    }

    def test_needs_name_only_carried_slots(self):
        """Each message's needs (D254 rule 1): only slots CARRIED gives a reason for - the held code, the R6 label's
        family, a conflict's act and attribute, an unlisted entry's nature, the stoma EUS class; none for the rest."""
        found = {message: spec.needs for message, spec in wording.MESSAGES.items() if spec.needs}
        self.assertEqual(found, self.NEEDS)
        used = {name for needs in found.values() for name in needs}
        self.assertEqual(used, set(wording.CARRIED))
        for name, why in wording.CARRIED.items():
            self.assertIn(name, FIELD_NAMES)
            self.assertTrue(why and why == ' '.join(why.split()), name)
        self.assertNotIn(M.SERVICE_DATE, found)  # its encounter-scope item_slots gives Slots(): no code
        self.assertNotIn(M.DOUBT, found)  # _own_entry clears the family; act_kind may give no kind

    def test_every_message_words_every_combination_of_present_and_absent_slots(self):
        built_count, combinations = 0, {}
        for message in M:
            needs = wording.MESSAGES[message].needs
            reads = reads_of(message)
            optional = sorted(reads - set(needs))
            combinations[message.value] = 2 ** len(optional)
            self.assertLessEqual(len(optional), 12, (message, optional))  # every combination stays enumerable
            for mask in range(2 ** len(optional)):
                slots = combination(needs, optional, mask)
                item, seen = recorded(message, slots)
                built_count += 1
                self.assertLessEqual(seen, reads, (message, slots))  # no slot read that this loop did not vary
                for sentence in (item.question, item.reason):
                    problems = sentence_problems(sentence)
                    if problems:
                        self.fail(f'{message.value} {slots}: {problems}: {sentence}')
                spec = wording.MESSAGES[message]
                self.assertEqual((item.message, item.kind), (message, spec.kind))
        self.assertGreater(built_count, 3500, combinations)  # never vacuous (3,987 combinations on this tree)

    def test_every_value_of_every_slot_a_builder_reads_is_worded(self):
        for message in M:
            reads = reads_of(message)
            for field in sorted(reads):
                for index, value in enumerate(POOLS[field]):
                    for others in (reads, wording.MESSAGES[message].needs):  # beside every other slot, and alone
                        slots = {name: value_of(name, index + 3) for name in others}
                        slots[field] = value
                        item = wording.build(message, wording.Slots(**slots), D254_TEXT)
                        for sentence in (item.question, item.reason):
                            problems = sentence_problems(sentence)
                            if problems:
                                self.fail(f'{message.value} {field}={value!r}: {problems}: {sentence}')

    def test_a_slot_no_builder_reads_changes_no_sentence(self):
        """The combinations above cover every sentence: a slot a builder does not read never changes its words."""
        import random
        rng = random.Random(254)
        for message in M:
            reads = reads_of(message)
            for _ in range(25):
                full = {field: rng.choice(POOLS[field]) for field in FIELD_NAMES}
                read_only = {field: value for field, value in full.items() if field in reads}
                self.assertEqual(wording.build(message, wording.Slots(**full), D254_TEXT),
                                 wording.build(message, wording.Slots(**read_only), D254_TEXT), message)

    def test_random_slots_are_worded(self):
        import hypothesis
        from hypothesis import strategies as st

        @hypothesis.settings(max_examples=400, deadline=None, derandomize=True, database=None)
        @hypothesis.given(st.sampled_from(list(M)), st.data())
        def check(message, data):
            slots = {field: data.draw(st.sampled_from(POOLS[field])) for field in FIELD_NAMES
                     if field in wording.MESSAGES[message].needs or data.draw(st.booleans())}
            item = wording.build(message, wording.Slots(**slots), D254_TEXT)
            for sentence in (item.question, item.reason):
                self.assertEqual(sentence_problems(sentence), [], (message.value, slots, sentence))
        check()

    def test_only_a_missing_carried_slot_or_a_binding_failure_is_refused(self):
        """What is left of the refusals: a carried slot left empty (a programming error, rule 5), and a span the
        revision holds no words at or does not reach (a binding failure)."""
        blank = (Span(D254_TEXT.index('. A') + 1, D254_TEXT.index('. A') + 2),)
        for message in M:
            needs = wording.MESSAGES[message].needs
            full = {field: value_of(field, 1) for field in FIELD_NAMES}
            for name in needs:
                with self.subTest(message=message, slot=name), self.assertRaisesRegex(ValueError, f'needs the slot {name}'):
                    wording.build(message, wording.Slots(**{**full, name: DEFAULTS[name]}), D254_TEXT)
            read = recorded(message, full)[1]
            for field in ('words', 'whole_words', 'approach_words', 'lesion', 'statements'):
                if field not in read:
                    continue
                # past the text; units holding no words (a lesion's words with none are read as no lesion, act_phrase's
                # rule since D225: its place names the act instead)
                for spans in ((Span(0, len(D254_TEXT) + 1),),) + (() if field == 'lesion' else (blank,)):
                    value = (spans,) if field == 'statements' else spans
                    with self.subTest(message=message, field=field, spans=spans):
                        with self.assertRaises(ValueError):
                            wording.build(message, wording.Slots(**{**full, field: value}), D254_TEXT)


class D254SixShapes(SimpleTestCase):
    """D254's six refusing shapes (the lead's VERIFY.md, each its refuter's own synthetic FactSet), assessed by the
    engine on this tree and worded from the slots the renderer words them with - overlay.item_slots for a TEXT_FREE
    item, else the Slots of the item's Fill (jobs.word_item's own choice) - and through jobs.word_item itself."""

    @staticmethod
    def shapes():
        from studio.interpretation.contract import types as ct
        from studio.interpretation.engine.types import UnlistedStatement
        from tests.v2 import evaluate_fixtures as EF
        sup, neg, unit, X, Y = EF.sup, EF.neg, EF.unit, EF.X, EF.Y

        def enteroscopy(reached, approach, through=None, entries=(), biopsy=False):
            doc = EF.Doc()
            doc.session(1, SessionKind.ENTEROSCOPY, approach=approach, reached=reached, through=through)
            for number, kind in entries:
                doc.entry(number, type=sup(kind, spans=(unit(8),)))
            doc.exam(1)
            if biopsy:
                doc.act(2, Kind.BIOPSY, places=[sup(Landmark.JEJUNUM)])
            return doc.build()

        def contra_colonoscopy():
            doc = EF.Doc()
            doc.session(1, SessionKind.COLONOSCOPY, reached=[sup(Extent.CECUM)])
            doc.exam(1)
            doc.act(2, EF.contra(Kind.SNARE, Kind.BIOPSY), places=[sup(Landmark.SIGMOID_COLON)])
            return doc.build()

        def office_and_contra_sigmoidoscopy():
            doc = EF.Doc()
            doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
            doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
            doc.session(2, SessionKind.FLEX_SIG, reached=[sup(Extent.SIGMOID_COLON)])
            doc.exam(2, session=X(2))
            doc.act(3, EF.contra(Kind.SNARE, Kind.BIOPSY), session=X(2), places=[sup(Landmark.SIGMOID_COLON)])
            return doc.build()

        def eus_other_act():
            doc = EF.Doc()
            doc.session(1, SessionKind.EUS, tract=sup(Tract.UPPER), encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                        stations=[sup(s) for s in (Station.ESOPHAGUS, Station.STOMACH, Station.DUODENUM)],
                        reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
            doc.exam(1, places=[sup(Landmark.PANCREAS)])
            doc.act(2, Kind.OTHER, places=[sup(Landmark.PANCREAS)])
            return doc.build()

        def kindless(session):
            return UnlistedStatement(units=(Span(3000, 3040),), what=UnlistedWhat.ACT, kind=None, session=session)

        def egd_tube():
            doc = EF.egd()
            doc.session(3, SessionKind.FEEDING_TUBE)
            doc.unlisted.append(kindless(X(3)))
            return doc.build()

        def colonoscopy_kindless_carded():
            doc = EF.colonoscopy(snare=False)
            doc.unlisted.append(kindless(X(1)))
            return doc.build()

        jejunum, ileum = sup(Extent.JEJUNUM, spans=(unit(5),)), sup(Extent.ILEUM, spans=(unit(6),))
        not_oral = neg(Approach.ORAL, spans=(unit(4),))
        return (
            ('A1 44360', enteroscopy([jejunum], not_oral), (('44360', 1),), '44360', 'enteroscopy_approach'),
            ('A1 44376', enteroscopy([ileum], not_oral), (('44376', 1),), '44376', 'enteroscopy_approach'),
            ('A1 44361', enteroscopy([jejunum], not_oral, biopsy=True), (('44361', 2),), '44361',
             'enteroscopy_approach'),
            ('A1 44380', enteroscopy([ileum], neg(Approach.THROUGH_STOMA, spans=(unit(4),)),
                                     through=sup(Y(1), spans=(unit(3),)), entries=((1, ct.AnatomyType.STOMA),)),
             (('44380', 1),), '44380', 'enteroscopy_approach'),
            ('R3C1-01 45378', contra_colonoscopy(), (('45378', 1),), '45378', 'base_included'),
            ('R3C1-01 45330 beside 99213', office_and_contra_sigmoidoscopy(), (('99213', 1), ('45330', 2)), '45330',
             'base_included'),
            ('5b F1 43259', eus_other_act(), (('43259', 1),), '43259', 'base_explained'),
            ('5b F1 43259 with 64530', eus_other_act(), (('43259', 1), ('64530', 2)), '43259', 'base_explained'),
            ('r4d S1 43235', egd_tube(), (('43235', 1),), '43235', 'base_included'),
            ('r4d S2c 45378', colonoscopy_kindless_carded(), (('45378', 1),), '45378', 'base_included'),
        )

    def test_the_six_shapes_are_worded_from_the_slots_the_renderer_gives_today(self):
        from studio import jobs
        from studio.interpretation import overlay
        from tests.v2 import test_assess as TA
        seen = {}
        for label, R, codes, code, message in self.shapes():
            with self.subTest(shape=label):
                assessment = TA.run(R, *codes)
                found = next(item for item in assessment.codes if item.code == code)
                self.assertEqual(found.item.message.value, message)  # the shape the lead reproduced, still made
                slots = overlay.item_slots(found.item, found.key, assessment.combination, R)
                slots = slots if slots is not None else jobs._slots_of(found.item.fill)
                worded = wording.build(wording.Message(message), slots, TA.TEXT)
                for sentence in (worded.question, worded.reason):
                    self.assertEqual(sentence_problems(sentence, TA.TEXT), [], sentence)
                spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT)  # the renderer's call
                self.assertEqual((spec.question, spec.reason), (worded.question, worded.reason))
                seen[label] = worded
        # what each says (D254 rule 3): the enteroscopy class without a route; the act no kind names as 'another act'
        a1 = seen['A1 44360']
        self.assertEqual(a1.question, 'The documented enteroscopy (' + wording.quote(TA.TEXT[500:560], 120) + ') reached '
                                      'the jejunum; CPT Studio could not confirm from the document the route this code '
                                      'describes. Was a small-bowel enteroscopy past the second portion of the duodenum '
                                      'that stops short of the ileum performed on the date of service?')
        self.assertEqual(a1.reason, 'The enteroscopy is documented as reaching the jejunum ('
                                    + wording.quote(TA.TEXT[500:560]) + '); 44360 accounts for a small-bowel enteroscopy '
                                    'past the second portion of the duodenum that stops short of the ileum, which CPT '
                                    'Studio could not find in the document.')
        for label in ('A1 44360', 'A1 44376', 'A1 44361', 'A1 44380'):  # no route named (the class's own words aside)
            said = seen[label].question + seen[label].reason
            for words in wording.ENTEROSCOPY_CLASS_WORDS.values():
                said = said.replace(words, '')
            self.assertIn('the route this code describes', said)
            for route in wording.ROUTE_WORDS.values():
                self.assertNotIn(route, said)
        self.assertEqual(seen['R3C1-01 45378'].question,
                         'Is 45378 reported separately from another act (stated in doubt) for this examination?')
        self.assertEqual(seen['5b F1 43259'].reason,
                         'The documented endoscopic ultrasound includes another act, which this diagnostic code does not '
                         'account for (internal profile rule). Held for the reviewer, not excluded.')
        self.assertEqual(seen['r4d S1 43235'].reason,
                         'The documented upper endoscopy includes another act (stated in doubt), which this diagnostic '
                         'code does not account for (internal profile rule). Held for the reviewer, not excluded.')


class D254AnotherAct(SimpleTestCase):
    """D254 rule 2: an act no kind names (Kind.OTHER, or a kind not established) has one label wherever wording turns a
    kind into words - 'another act', its article included, 'Another act ...' opening a sentence; R3C1-03's 'from act'
    is gone."""

    def test_the_label_and_its_article(self):
        self.assertEqual(wording.NO_KIND_LABEL, 'another act')
        for kind in (None, Kind.OTHER):
            self.assertEqual(wording.kind_words(kind), 'another act')
            self.assertFalse(wording.named_kind(kind))
        for kind in Kind:
            if kind is not Kind.OTHER:
                self.assertTrue(wording.named_kind(kind))
                self.assertEqual(wording.kind_words(kind), wording.event_kind_label(kind.value))
        self.assertEqual(wording.the_act(D254_TEXT, wording.Slots(act=Kind.OTHER)), 'another act')
        self.assertEqual(wording.the_act(D254_TEXT, wording.Slots(act=Kind.SNARE)), 'the snare removal')

    def test_every_kind_slot_with_no_kind_reads_another_act(self):
        """Over every message and every slot that holds a kind (act, whole, unlisted_kind, listed, possible): with
        Kind.OTHER or none, no article stands before 'another act', no bare 'act' label is left, and a sentence the label
        opens reads 'Another act'."""
        reads = {message: reads_of(message) for message in M}
        named = 0
        for message in M:
            for field in ('act', 'whole', 'unlisted_kind', 'listed', 'possible'):
                if field not in reads[message]:
                    continue
                carried = field in wording.MESSAGES[message].needs  # a carried kind is never left out (CARRIED)
                for value in (((Kind.OTHER,) if carried else (None, Kind.OTHER)) if field in ('act', 'whole', 'unlisted_kind')
                              else ((Kind.OTHER,), (Kind.OTHER, Kind.SNARE))):
                    for index in range(3):
                        slots = {name: value_of(name, index + 5) for name in reads[message]}
                        slots[field] = value
                        item = wording.build(message, wording.Slots(**slots), D254_TEXT)
                        text = item.question + ' ' + item.reason
                        self.assertFalse(NO_ARTICLE.search(text), (message, field, text))
                        self.assertFalse(re.search(r'(?<!another )\bact \(stated in doubt\)|\bfrom act\b', text), text)
                        named += 'another act' in text or 'Another act' in text
        self.assertGreater(named, 150)
        item = wording.build(M.SEPARATE_EM, wording.Slots(code='99213', possible=(Kind.OTHER,)), '')
        self.assertTrue(item.reason.startswith('Another act is possibly performed on the same date (its performance is '
                                               'not established);'), item.reason)  # I2's day act, D254's label
        item = wording.build(M.ATTEMPTED, wording.Slots(code='45385', act=Kind.OTHER), '')
        self.assertTrue(item.question.startswith('Another act was begun and not completed.'), item.question)
        item = wording.build(M.BASE_INCLUDED, wording.Slots(code='45378', family=SessionKind.COLONOSCOPY,
                                                            listed=(Kind.OTHER,)), '')
        self.assertNotIn('from act ', item.question)  # R3C1-03
        self.assertIn('from another act (stated in doubt)', item.question)


class D254Rule3(SimpleTestCase):
    """D254 rule 3: ENTEROSCOPY_APPROACH without ``approach`` (a denied or unstated route) words the class without
    naming a route; BASE_INCLUDED, BASE_EXPLAINED and SEPARATE_EM each have a true form with nothing to name; and
    (rule 1, refute-r4a-r2's note) every route an enteroscopy is passed by is named."""

    def test_enteroscopy_approach_without_an_approach_names_no_route(self):
        base = dict(code='44376', act=Kind.EXAMINATION, family=SessionKind.ENTEROSCOPY,
                    enteroscopy_class=EnteroscopyClass.ILEAL)
        ileal = 'a small-bowel enteroscopy past the second portion of the duodenum that reaches the ileum'
        item = wording.build(M.ENTEROSCOPY_APPROACH, wording.Slots(**base, words=U_REACH, reached=Extent.ILEUM),
                             D254_TEXT)
        self.assertEqual(item.question, 'The documented enteroscopy (“The scope was advanced to the ileum.”) reached the '
                                        'ileum; CPT Studio could not confirm from the document the route this code '
                                        f'describes. Was {ileal} performed on the date of service?')
        self.assertEqual(item.reason, 'The enteroscopy is documented as reaching the ileum (“The scope was advanced to '
                                      f'the ileum.”); 44376 accounts for {ileal}, which CPT Studio could not find in the '
                                      'document.')
        item = wording.build(M.ENTEROSCOPY_APPROACH, wording.Slots(**base), D254_TEXT)  # nor a reach, nor words
        self.assertEqual(item.question, 'CPT Studio could not confirm from the document the route this code describes '
                                        f'for the documented enteroscopy. Was {ileal} performed on the date of service?')
        self.assertEqual(item.reason, f'The enteroscopy is documented; 44376 accounts for {ileal}, which CPT Studio could '
                                      'not find in the document.')
        for slots in ({}, {'reached': Extent.ILEUM}, {'words': U_REACH}, {'enteroscopy_class': None}):
            item = wording.build(M.ENTEROSCOPY_APPROACH, wording.Slots(**{**base, **slots}), D254_TEXT)
            for route in wording.ROUTE_WORDS.values():
                self.assertNotIn(route, item.question + item.reason)

    def test_every_route_is_named(self):
        """refute-r4a-r2 (recorded for 3c): ENTEROSCOPY_APPROACH named only the three APPROACH_WORDS routes, so 44376
        passed through the anus to the ileum read as if nothing explained the hold."""
        for approach, route in wording.ROUTE_WORDS.items():
            item = wording.build(M.ENTEROSCOPY_APPROACH, wording.Slots(
                code='44376', enteroscopy_class=EnteroscopyClass.ILEAL, words=U_REACH, reached=Extent.ILEUM,
                approach=approach, approach_words=U_STOMA), D254_TEXT)
            self.assertIn(f'reached the ileum {route} (“The enteroscope entered through the stoma.”)', item.question)
            self.assertIn(f'reaching the ileum (“The scope was advanced to the ileum.”) {route} (“The enteroscope '
                          'entered through the stoma.”);', item.reason)
        item = wording.build(M.ENTEROSCOPY_APPROACH, wording.Slots(code='44376', enteroscopy_class=EnteroscopyClass.ILEAL,
                                                                   reached=Extent.ILEUM, approach=Approach.TRANSANAL),
                             D254_TEXT)
        self.assertEqual(item.question, 'The documented enteroscopy reached the ileum through the anus. Was a small-bowel '
                                        'enteroscopy past the second portion of the duodenum that reaches the ileum '
                                        'performed on the date of service?')

    def test_the_base_and_same_day_items_with_nothing_to_name(self):
        for message, question, reason in (
                (M.BASE_INCLUDED, 'Is 43235 reported separately from another act (stated in doubt) for this examination?',
                 'The documented upper endoscopy includes another act (stated in doubt), which this diagnostic code does '
                 'not account for (internal profile rule). Held for the reviewer, not excluded.'),
                (M.BASE_EXPLAINED, 'Is 43235 reported separately from another act for this examination?',
                 'The documented upper endoscopy includes another act, which this diagnostic code does not account for '
                 '(internal profile rule). Held for the reviewer, not excluded.'),
                (M.SEPARATE_EM, wording.SEPARATE_EM_QUESTION,
                 'A significant, separately identifiable E/M service beside a procedure on the same date is not '
                 'established by this document.')):
            with self.subTest(message=message):
                for text in ('', D254_TEXT):  # TEXT_FREE: read time words them with no text
                    item = wording.build(message, wording.Slots(code='43235', family=SessionKind.EGD), text)
                    self.assertEqual((item.question, item.reason), (question, reason))


class D257BaseWithin(SimpleTestCase):
    """D257 (refute-r4d-r2 P5): BASE_WITHIN names the whole by its own family - never "the endoscopic ultrasound" for a
    colonoscopy - and a whole only possibly done is stated as possibly performed on the date of service, its performance
    not established."""

    RULE = ('that examination is normally included in it, not reported separately (internal profile rule; NCCI '
            'procedure-to-procedure edits are not connected). Held for the reviewer, not excluded.')

    def worded(self, **slots):
        return wording.build(M.BASE_WITHIN, wording.Slots(**slots), '')

    def test_the_whole_is_named_by_its_own_family(self):
        item = self.worded(code='45330', family=SessionKind.FLEX_SIG, codes=('45378',),
                           whole_family=SessionKind.COLONOSCOPY)  # N3 (i)
        self.assertEqual(item.question, 'Is 45330 reported separately from 45378 for this examination?')
        self.assertEqual(item.reason, 'The documented flexible sigmoidoscopy is part of the colonoscopy documented with it, '
                                      f'which 45378 accounts for; {self.RULE}')
        item = self.worded(code='45330', family=SessionKind.FLEX_SIG, whole_family=SessionKind.COLONOSCOPY)
        self.assertEqual(item.question, 'Is 45330 reported separately from the colonoscopy for this examination?')
        item = self.worded(code='43235', family=SessionKind.EGD, codes=('43242',), whole_family=SessionKind.EUS)
        self.assertEqual(item.reason, 'The documented upper endoscopy is the endoscopic portion of the endoscopic '
                                      f'ultrasound documented with it, which 43242 accounts for; {self.RULE}')  # v1's
        for family in SessionKind:  # an EUS only when the whole is one
            item = self.worded(code='45330', family=SessionKind.FLEX_SIG, whole_family=family)
            self.assertEqual('endoscopic ultrasound' in item.question + item.reason, family is SessionKind.EUS, family)
        item = self.worded(code='45330', family=SessionKind.FLEX_SIG, codes=('45378',))  # no family given
        self.assertEqual(item.reason, 'The documented flexible sigmoidoscopy is part of another procedure documented with '
                                      f'it, which 45378 accounts for; {self.RULE}')
        self.assertEqual(self.worded(code='45330', family=SessionKind.FLEX_SIG).question,
                         'Is 45330 reported separately from the procedure it is part of for this examination?')

    def test_a_whole_only_possibly_done_is_stated_so(self):
        item = self.worded(code='43235', family=SessionKind.EGD, codes=('43242',), whole_family=SessionKind.EUS,
                           whole_possible=True)  # refute-r4d-r2 P2's planned or possible EUS
        self.assertEqual(item.question, 'Is 43235 reported separately from 43242 for this examination?')
        self.assertEqual(item.reason, 'The documented upper endoscopy may be the endoscopic portion of the endoscopic '
                                      'ultrasound documented with it, possibly performed on the date of service (its '
                                      f'performance is not established), which 43242 accounts for; {self.RULE}')
        item = self.worded(code='45330', family=SessionKind.FLEX_SIG, whole_possible=True)
        self.assertEqual(item.question, 'Is 45330 reported separately from the procedure it may be part of for this '
                                        'examination?')
        self.assertEqual(item.reason, 'The documented flexible sigmoidoscopy may be part of another procedure documented '
                                      'with it, possibly performed on the date of service (its performance is not '
                                      f'established); {self.RULE}')
        for family in (None, *SessionKind):
            item = self.worded(code='45330', family=SessionKind.FLEX_SIG, whole_family=family, whole_possible=True)
            self.assertIn('possibly performed on the date of service (its performance is not established)', item.reason)
            self.assertNotIn(' is part of', item.reason)

    def test_the_new_slots_are_optional_and_typed(self):
        self.assertEqual((wording.Slots().whole_family, wording.Slots().whole_possible), (None, False))
        names = [field for field in wording.Slots.__dataclass_fields__]  # appended after unlisted_kind (round w9r's
        start = names.index('unlisted_kind') + 1                           # possible_approaches follows them: D267)
        self.assertEqual(names[start:start + 2], ['whole_family', 'whole_possible'])
        for changes in ({'whole_family': 'eus'}, {'whole_family': Kind.SNARE}, {'whole_possible': 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                wording.Slots(**changes)


class D258UnlistedScope(SimpleTestCase):
    """D258 (r4a QP2, QD; r4c Q1): UNLISTED_SCOPE - a statement that names no procedure session, beside the held session's
    established examination: the question names that examination by its service and asks whether it is documented as
    performed, in full or in part, on the date of service (row 7's done: D281, build list B6 - restated from
    "documented as done"); the reason quotes the statement and says it names no procedure session; never that the
    document leaves that examination in doubt or denies it."""

    def test_the_entry(self):
        spec = wording.MESSAGES[M.UNLISTED_SCOPE]
        self.assertEqual((M.UNLISTED_SCOPE.value, spec.fact, spec.kind, spec.rank, spec.needs),
                         ('unlisted_scope', 'performed_status', ItemKind.QUESTION, 2, ()))
        self.assertEqual([member.value for member in M][-5:],  # D280.3's and D284's two appended after it (step f3w)
                         ['synthetic_act', 'unlisted_scope', 'enteroscopy_through', 'digital_scope', 'addon'])
        requirements.Item(requirements.Rank(2), requirements.FactKey('performed_status'))

    def test_the_question_and_the_reason(self):
        item = wording.build(M.UNLISTED_SCOPE, wording.Slots(code='45378', act=Kind.EXAMINATION,
                                                             family=SessionKind.COLONOSCOPY, words=U_REACH,
                                                             statements=(U_PRIOR,)), D254_TEXT)  # QP2's input
        self.assertEqual((item.fact, item.kind), ('performed_status', ItemKind.QUESTION))
        self.assertEqual(item.question, 'Is the colonoscopy (“The scope was advanced to the ileum.”) documented as '
                                        'performed, in full or in part, on the date of service?')
        self.assertEqual(item.reason, 'The document states “It is not known whether she had a colonoscopy before.”, which '
                                      'names no procedure session; CPT Studio could not confirm from the document whether '
                                      'it is about the colonoscopy. Held for the reviewer, not excluded.')
        item = wording.build(M.UNLISTED_SCOPE, wording.Slots(family=SessionKind.EGD, statements=(U_NONE,)), D254_TEXT)
        self.assertEqual(item.question, 'Is the upper endoscopy documented as performed, in full or in part, on the date '
                                        'of service?')  # QD
        self.assertIn('“No polyps were removed.”, which names no procedure session;', item.reason)
        item = wording.build(M.UNLISTED_SCOPE, wording.Slots(), D254_TEXT)  # nothing given
        self.assertEqual((item.question, item.reason),
                         ('Is the examination documented as performed, in full or in part, on the date of service?',
                          'A statement in the document names no procedure session; CPT Studio could not confirm from the '
                          'document whether it is about the examination. Held for the reviewer, not excluded.'))
        item = wording.build(M.UNLISTED_SCOPE, wording.Slots(family=SessionKind.ENTEROSCOPY,
                                                             statements=(U_PRIOR, U_NONE)), D254_TEXT)
        self.assertIn('which name no procedure session; CPT Studio could not confirm from the document whether they are '
                      'about the enteroscopy.', item.reason)

    def test_it_never_says_the_examination_is_in_doubt_or_denied(self):
        for family in (None, *SessionKind):
            for what in (None, *UnlistedWhat):
                for statements in ((), (U_PRIOR,), (U_NONE,), ((),)):
                    item = wording.build(M.UNLISTED_SCOPE, wording.Slots(family=family, unlisted_what=what,
                                                                         statements=statements, words=U_REACH),
                                         D254_TEXT)
                    said = (item.question + ' ' + item.reason).replace('“It is not known whether she had a colonoscopy '
                                                                       'before.”', '').replace('“No polyps were removed.”', '')
                    for phrase in ('in doubt', 'leaves', 'denies', 'not done', 'was not', 'deny'):
                        self.assertNotIn(phrase, said, (family, what, statements))
                    self.assertEqual(sentence_problems(item.question), [])
                    self.assertEqual(sentence_problems(item.reason), [])


class D253EnteroscopyThrough(SimpleTestCase):
    """D253 QX (ii): an enteroscopy route part whose only unknown is the anatomy it was passed through is asked by the
    route's own question - no existing form asked only that, so ENTEROSCOPY_THROUGH (procedure, a question, rank 8) is
    added for step r4a to map - never "In which procedure was the enteroscopy done?"."""

    STOMA = 'an examination of the ileum through a stoma'

    def test_the_entry_and_its_words(self):
        spec = wording.MESSAGES[M.ENTEROSCOPY_THROUGH]
        self.assertEqual((M.ENTEROSCOPY_THROUGH.value, spec.fact, spec.kind, spec.rank, spec.needs),
                         ('enteroscopy_through', 'procedure', ItemKind.QUESTION, 8, ('code',)))
        item = wording.build(M.ENTEROSCOPY_THROUGH, wording.Slots(
            code='44380', act=Kind.EXAMINATION, family=SessionKind.ENTEROSCOPY, enteroscopy_class=EnteroscopyClass.STOMA,
            reached=Extent.ILEUM, words=U_REACH, approach=Approach.THROUGH_STOMA, approach_words=U_STOMA), D254_TEXT)
        self.assertEqual(item.question, 'The documented enteroscopy (“The scope was advanced to the ileum.”) reached the '
                                        'ileum, passed through a stoma (“The enteroscope entered through the stoma.”); CPT '
                                        'Studio could not confirm from the document the altered anatomy it was passed '
                                        f'through. Was {self.STOMA} performed on the date of service?')
        self.assertEqual(item.reason, 'The enteroscopy is documented as reaching the ileum (“The scope was advanced to the '
                                      'ileum.”), passed through a stoma (“The enteroscope entered through the stoma.”), '
                                      'and CPT Studio could not confirm from the document the altered anatomy it was '
                                      f'passed through; 44380 accounts for {self.STOMA}, which CPT Studio could not find '
                                      'in the document.')
        item = wording.build(M.ENTEROSCOPY_THROUGH, wording.Slots(code='44380', enteroscopy_class=EnteroscopyClass.STOMA),
                             D254_TEXT)  # QX (ii)'s input: 44380, no through filed - nor a reach or a route here
        self.assertEqual(item.question, 'CPT Studio could not confirm from the document the altered anatomy the documented '
                                        f'enteroscopy was passed through. Was {self.STOMA} performed on the date of '
                                        'service?')
        for slots in ({}, {'reached': Extent.ILEUM}, {'approach': Approach.THROUGH_POUCH}, {'words': U_LONG}):
            item = wording.build(M.ENTEROSCOPY_THROUGH, wording.Slots(code='44385', **slots), D254_TEXT)
            self.assertNotIn('In which procedure', item.question)
            self.assertIn('could not confirm from the document the altered anatomy', item.question)
            self.assertNotIn('through the mouth or', item.question)  # the route itself is not what is unknown


class D255AddOnPairs(SimpleTestCase):
    """D255 (refute-r3c-r1 R3C1-02): an add-on code never includes another under rule (a), so no codes-form test here
    rests on an add-on pair (99215 with 99417, 43260 with 43273): none did, and this pins it (the add-on table read from
    engine/assess, where step r4d stops holding such pairs)."""

    def test_no_codes_form_pair_here_is_an_add_on_pair(self):
        from studio.interpretation.engine import assess as engine_assess
        addons = {str(addon): {str(primary) for primary in primaries}
                  for addon, primaries in engine_assess.ADDON_PRIMARIES.items()}
        tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
        pairs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ('d246_worded', 'worded', 'built'):
                if node.args and isinstance(node.args[0], ast.Attribute) and node.args[0].attr in (
                        'BASE_INCLUDED', 'BASE_EXPLAINED', 'BASE_WITHIN', 'SEPARATE_EM'):
                    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
                    code = keywords.get('code')
                    codes = keywords.get('codes')
                    if isinstance(code, ast.Constant) and isinstance(codes, ast.Tuple):
                        for other in codes.elts:
                            if isinstance(other, ast.Constant):
                                pairs.add((code.value, other.value))
        self.assertGreater(len(pairs), 5)
        for code, other in pairs:
            self.assertNotIn(code, addons.get(other, set()), (code, other))
            self.assertNotIn(other, addons.get(code, set()), (code, other))
            self.assertNotIn(code, addons, (code, other))


class ThroughTheActEqualsV1(SimpleTestCase):
    """The builders now word the act through its article (the_act: D254 rule 2); for every kind that names an act, with
    the act's own words given, each sentence is still v1's own (the copies' functions, called here)."""

    def test_every_named_kind_reads_as_v1(self):
        text = D254_TEXT
        words, statement = wording.span_text(text, U_OLD), wording.span_text(text, U_NONE)
        for kind in Kind:
            if kind is Kind.OTHER:
                continue
            slots = dict(code='45385', act=kind, words=U_OLD, statements=(U_NONE,), technique=TechniqueClass.BALLOON,
                         site=SiteClass.ESOPHAGEAL)
            act = wording.act_phrase(text, wording.Slots(**slots))
            pairs = {
                M.STATUS: (wording.status_question(act, words), wording.status_reason(act)),
                M.TIME: (wording.time_question(act, words), wording.time_reason(act)),
                M.PERFORMER: (wording.performer_question(act, words), wording.performer_reason(act)),
                M.PROCEDURE: (wording.procedure_question(act, words), wording.procedure_reason(act)),
                M.ACT_TARGET: (wording.target_question(act, words), wording.target_reason(act)),
                M.TECHNIQUE: (wording.technique_question(act, words), wording.technique_reason(act, 'balloon dilation')),
                M.STATED_TECHNIQUE: (wording.technique_question(act, words), wording.technique_unresolved_reason(act)),
                M.SITE: (wording.target_question(act, words), wording.site_reason(act, 'dilation of the esophagus')),
                M.DOUBT: (wording.doubt_question(act, words), wording.doubt_reason(act, statement)),
                M.CONFLICT: (wording.conflict_question(act), wording.conflict_reason(act, words, statement)),
                M.ATTEMPTED: (wording.attempted_question('45385', act), wording.attempted_reason(act, words)),
                M.STATEMENT_SCOPE: (wording.scope_question(statement, act, words, whole=True),
                                    wording.scope_reason(statement, act, whole=True)),
            }
            for message, expected in pairs.items():
                with self.subTest(kind=kind, message=message):
                    item = wording.build(message, wording.Slots(**slots), text)
                    self.assertEqual((item.question, item.reason), expected)
            for rule in ('biopsy_of_removed_lesion', 'resection_technique', 'lift_injection', 'procedural_adjunct'):
                item = wording.build(M.PART, wording.Slots(act=kind, words=U_OLD, whole_words=U_NEW,
                                                           bundling=wording.Bundling(rule)), text)
                self.assertEqual(item.question, wording.bundling_question(rule, wording.event_kind_label(kind.value),
                                                                          words, wording.span_text(text, U_NEW)))
                self.assertEqual(item.reason, wording.bundling_reason(wording.act_phrase(text, wording.Slots(act=kind))))
        for rule, template in wording.PART_QUESTIONS.items():
            item = wording.build(M.PART, wording.Slots(act=Kind.FNA, words=U_OLD, whole_words=U_NEW, bundling=rule), text)
            self.assertEqual(item.question, template.format(act='fine-needle aspiration or biopsy',
                                                            part=wording.quote(words, 120),
                                                            whole=wording.quote(wording.span_text(text, U_NEW), 120)))
        detail, question = wording.another_technique('upper endoscopy', 'dilation with dilators passed over a guide wire',
                                                     'balloon dilation', words)
        item = wording.build(M.ANOTHER_TECHNIQUE, wording.Slots(family=SessionKind.EGD, technique=TechniqueClass.BALLOON,
                                                                stated=TechniqueClass.WIRE_BOUGIE, words=U_OLD), text)
        self.assertEqual((item.question, item.reason), (question, detail))
        detail, question = wording.another_site('upper endoscopy', 'duodenum', 'dilation of the esophagus', words)
        item = wording.build(M.ANOTHER_SITE, wording.Slots(family=SessionKind.EGD, site=SiteClass.ESOPHAGEAL,
                                                           place=Landmark.DUODENUM, words=U_OLD), text)
        self.assertEqual((item.question, item.reason), (question, detail))
        for place in (Landmark.GALLBLADDER, None):
            reason, question = wording.defining_target_hold('43240', 'drainage', wording.landmark_label(place.value)
                                                            if place else '', words)
            item = wording.build(M.ANOTHER_STRUCTURE if place else M.STRUCTURE, wording.Slots(
                code='43240', act=Kind.DRAINAGE, words=U_OLD, place=place), text)
            self.assertEqual((item.question, item.reason), (question, reason))
        detail, question = wording.act_included('colonoscopy', 'performed', 'snare removal',
                                                wording.BUNDLING_WHY[wording.Bundling.CLIP], 'clip placement', words)
        item = wording.build(M.BUNDLED, wording.Slots(family=SessionKind.COLONOSCOPY, listed=(Kind.SNARE,),
                                                      group=(Kind.CLIP,), bundling=wording.Bundling.CLIP, words=U_OLD),
                             text)
        self.assertEqual((item.question, item.reason), (question, detail))


# --- D266 and D267 (repair r3c of round w9r) ---------------------------------------------------------------------------

W9_TEXT = ('A cold snare polypectomy of the 6 mm sigmoid polyp was performed. No polyp was removed from the rectum. '
           'No colonoscopy was performed today. It is not known whether she had a colonoscopy before. The scope was '
           'advanced to the jejunum. A clip was placed at the polypectomy site. The echoendoscope entered through the '
           'stoma.')


def w9(phrase):
    start = W9_TEXT.index(phrase)
    return (Span(start, start + len(phrase)),)


W9_SNARED = w9('A cold snare polypectomy of the 6 mm sigmoid polyp was performed.')
W9_DENIAL = w9('No polyp was removed from the rectum.')
W9_NONE_TODAY = w9('No colonoscopy was performed today.')
W9_PRIOR = w9('It is not known whether she had a colonoscopy before.')
W9_REACH = w9('The scope was advanced to the jejunum.')
W9_CLIP = w9('A clip was placed at the polypectomy site.')
W9_STOMA = w9('The echoendoscope entered through the stoma.')


def unquoted(sentence):
    """``sentence`` with each quote of the document's words emptied: what CPT Studio itself says in it."""
    return re.sub(r'“[^”]*”', '“”', sentence)


class D266DenialForm(SimpleTestCase):
    """D266 (refute-r3c-r1 F3; r4a-2 Q2; TRIAGE G2-16): DOUBT words an unlisted DENIAL (``unlisted_what``, which step r4a
    fills for a carded entry as for one with no card) - of any kind or none - as a statement that the act was not done,
    quoting the denial, never "leaves ... in doubt"; its question is v1's doubt_question, and the held fact, kind and rank
    are DOUBT's. A doubt, or no entry named, reads as before; an ACT (no Fill gives DOUBT one) as SYNTHETIC_ACT's
    sentence."""

    SNARE = dict(code='45385', act=Kind.SNARE, device=Device.COLD_SNARE, place=Landmark.SIGMOID_COLON, words=W9_SNARED,
                 family=SessionKind.COLONOSCOPY)
    LABEL = 'snare removal (cold snare) at the sigmoid colon'  # act_phrase's; v1's builders put 'the' before it
    ACT = f'the {LABEL}'
    SNARED = '“A cold snare polypectomy of the 6 mm sigmoid polyp was performed.”'

    @staticmethod
    def worded(**slots):
        return wording.build(M.DOUBT, wording.Slots(**slots), W9_TEXT)

    def test_a_denial_states_that_the_act_was_not_done(self):
        """Restated for D281 (step f3w; build list B5, G3-10 ruling D): a rule-4 denial's scope is unresolved by
        construction, so the reason states it as a statement that AN act was not done and that CPT Studio could not
        confirm whether it is about the act - never "states that <the act> was not done" (before: D266's DENIAL_STATED,
        now gone)."""
        item = self.worded(**self.SNARE, statements=(W9_DENIAL,), unlisted_what=UnlistedWhat.DENIAL)
        self.assertEqual((item.message, item.fact, item.kind), (M.DOUBT, 'performed_status', ItemKind.QUESTION))
        self.assertEqual(item.question, f'Confirm whether {self.ACT} ({self.SNARED}) was done on the date of service.')
        self.assertEqual(item.reason, '“No polyp was removed from the rectum.”'.join((
            'The document states ', ', a statement that an act was not done; CPT Studio could not confirm from the '
            f'document whether it is about {self.ACT}.')))
        self.assertEqual(item.question, wording.doubt_question(self.LABEL, wording.span_text(W9_TEXT, W9_SNARED)))
        self.assertEqual(wording.DENIAL_SCOPE, 'a statement that an act was not done')
        self.assertFalse(hasattr(wording, 'DENIAL_STATED'))  # B5's mutant restores it
        self.assertEqual(wording.UNLISTED_STATED[UnlistedWhat.DENIAL], 'states that {kind} was not done')  # its row
        # the session's examination (a carded kindless denial beside 45378 alone: G2-16 (ii)), named by its service and
        # asked by row 7's done (B6)
        item = self.worded(code='45378', act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY,
                           statements=(W9_NONE_TODAY,), unlisted_what=UnlistedWhat.DENIAL)
        self.assertEqual((item.question, item.reason),
                         ('Confirm whether the colonoscopy is documented as performed, in full or in part, on the date '
                          'of service.',
                          'The document states “No colonoscopy was performed today.”, a statement that an act was not '
                          'done; CPT Studio could not confirm from the document whether it is about the colonoscopy.'))
        # an act no kind names (D254 rule 2): 'another act', no article before it
        item = self.worded(code='45385', statements=(W9_DENIAL,), unlisted_what=UnlistedWhat.DENIAL)
        self.assertEqual((item.question, item.reason),
                         ('Confirm whether another act was done on the date of service.',
                          'The document states “No polyp was removed from the rectum.”, a statement that an act was not '
                          'done; CPT Studio could not confirm from the document whether it is about another act.'))

    def test_a_denial_with_no_units_is_named_without_a_quote_never_the_acts_own_sentence(self):
        """A Fill that gives no statement with units: the denial is stated, nothing quoted for it - never the act's own
        sentence, which states the act (DOUBT's doubt form falls back to it; a denial never does). Restated for D281 (B5):
        "The document states that an act was not done; CPT Studio could not confirm ... whether it is about <the act>"."""
        for statements in ((), ((),)):
            item = self.worded(**self.SNARE, statements=statements, unlisted_what=UnlistedWhat.DENIAL)
            self.assertEqual(item.reason, 'The document states that an act was not done; CPT Studio could not confirm '
                                          f'from the document whether it is about {self.ACT}.')
            self.assertEqual(item.question, f'Confirm whether {self.ACT} ({self.SNARED}) was done on the date of service.')
        item = self.worded(code='45378', act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY,
                           unlisted_what=UnlistedWhat.DENIAL)
        self.assertEqual((item.question, item.reason),
                         ('Confirm whether the colonoscopy is documented as performed, in full or in part, on the date of '
                          'service.',
                          'The document states that an act was not done; CPT Studio could not confirm from the document '
                          'whether it is about the colonoscopy.'))

    def test_a_denial_is_never_said_to_leave_the_act_in_doubt(self):
        """Over every kind (and none), with the act's own words and without, every statement shape and two families: no
        "doubt" and no "leaves" in what CPT Studio says, "was not done" in the reason, the denial quoted when it has
        units, the act's own sentence never quoted as the denial, each sentence fit for the customer."""
        built = 0
        for kind in (None, *Kind):
            for statements in ((), (W9_DENIAL,), ((),), ((), W9_DENIAL), (W9_DENIAL, W9_PRIOR)):
                for words in ((), W9_SNARED):
                    for family in (None, SessionKind.COLONOSCOPY):
                        item = self.worded(code='45385', act=kind, words=words, family=family, statements=statements,
                                           unlisted_what=UnlistedWhat.DENIAL)
                        built += 1
                        for sentence in (item.question, item.reason):
                            said = unquoted(sentence)
                            self.assertNotIn('doubt', said, sentence)
                            self.assertNotIn('leaves', said, sentence)
                            self.assertEqual(sentence_problems(sentence, W9_TEXT), [], sentence)
                        self.assertIn(' was not done', item.reason)
                        self.assertEqual('“No polyp was removed from the rectum.”' in item.reason,
                                         W9_DENIAL in statements, (statements, item.reason))
                        self.assertNotIn(self.SNARED, item.reason)
        self.assertEqual(built, (len(Kind) + 1) * 5 * 2 * 2)

    def test_a_doubt_or_no_entry_reads_as_before(self):
        before = (f'Confirm whether {self.ACT} ({self.SNARED}) was done on the date of service.',
                  f'The document leaves {self.ACT} in doubt: “It is not known whether she had a colonoscopy before.”.')
        for what in (None, UnlistedWhat.DOUBT):
            item = self.worded(**self.SNARE, statements=(W9_PRIOR,), unlisted_what=what)
            self.assertEqual((item.question, item.reason), before)
            self.assertEqual(item.reason, wording.doubt_reason(self.LABEL, wording.span_text(W9_TEXT, W9_PRIOR)))

    def test_an_unlisted_act_is_never_said_to_be_in_doubt(self):
        """No Fill gives DOUBT an unlisted ACT (step r4a words 3.2.6 rule 3's synthetic act by SYNTHETIC_ACT), but the
        builder words it truly (D254 rule 1): SYNTHETIC_ACT's sentence over the entry's own kind and statement (D246:
        "leaves ... in doubt" is untrue of an act the document states)."""
        item = self.worded(**self.SNARE, statements=(W9_CLIP,), unlisted_what=UnlistedWhat.ACT,
                           unlisted_kind=Kind.CLIP)
        self.assertEqual(item.reason, f'The document documents a clip placement (“A clip was placed at the polypectomy '
                                      f'site.”), {wording.SYNTHETIC_UNACCOUNTED}.')
        for kind in (None, Kind.OTHER):
            item = self.worded(**self.SNARE, unlisted_what=UnlistedWhat.ACT, unlisted_kind=kind)
            self.assertEqual(item.reason, f'The document documents another act, {wording.SYNTHETIC_UNACCOUNTED}.')
            self.assertNotIn('doubt', item.question + item.reason)

    def test_carded_and_no_card_denials_of_kind_snare_and_kindless_through_the_renderer(self):
        """refute-r3c-r1 F3's own probe (probes/v8r3c1_carded_denial.py): a colonoscopy X1 with 45385 on its snare E2 (or
        45378 alone) and a kept unlisted DENIAL carded X1 or with no card, of kind snare or none - the engine's own item,
        its Fill given ``unlisted_what`` as step r4a fills it (D266), worded by the renderer's own call
        (jobs.word_item): no "doubt" and no "leaves" in any of them, and each DOUBT states that its act was not done,
        quoting the denial."""
        import dataclasses

        from studio import jobs
        from studio.interpretation.engine.types import UnlistedStatement
        from tests.v2 import evaluate_fixtures as EF
        from tests.v2 import test_assess as TA
        units = (Span(3000, 3040),)
        quoted = wording.quote(TA.TEXT[3000:3040], 140)
        doubts = set()
        for card in (EF.X(1), None):
            for kind in (None, Kind.SNARE):
                for snare in (True, False):
                    with self.subTest(card=card, kind=kind, snare=snare):
                        doc = EF.colonoscopy(snare=snare)
                        doc.unlisted.append(UnlistedStatement(units=units, what=UnlistedWhat.DENIAL, kind=kind,
                                                              session=card))
                        R = doc.build()
                        assessment = TA.run(R, ('45385', 2) if snare else ('45378', 1))
                        found = assessment.codes[0]
                        if found.item is None:  # a denial the engine pairs with no act of this code (READY)
                            continue
                        item = dataclasses.replace(found.item, fill=dataclasses.replace(
                            found.item.fill, unlisted_what=UnlistedWhat.DENIAL))
                        spec = jobs.word_item(item, found.key, assessment.combination, R, TA.TEXT)
                        for sentence in (spec.question, spec.reason):
                            self.assertNotIn('doubt', unquoted(sentence), sentence)
                            self.assertNotIn('leaves', unquoted(sentence), sentence)
                        if found.item.message.value == 'doubt':  # D281 (B5): the denial's scope never asserted
                            doubts.add((card is not None, kind, found.code))
                            self.assertTrue(spec.reason.startswith(f'The document states {quoted}, a statement that an '
                                                                   'act was not done; CPT Studio could not confirm from '
                                                                   'the document whether it is about '), spec.reason)
                            self.assertNotIn(' was not done: ', spec.reason)
        # never vacuous: the carded and the no-card denial of kind snare and kindless beside the snare are each DOUBT
        for card in (True, False):
            for kind in (None, Kind.SNARE):
                self.assertIn((card, kind, '45385'), doubts)


class D266NoQuote(SimpleTestCase):
    """D266's first half (refute-r4a-r2 F2; TRIAGE G1-03): step r4a quotes the held session's examination only when it is
    possibly done on the date of service; UNLISTED_SCOPE and DOUBT have a true form with no quote for a Fill that gives
    none - the examination named by its service, nothing of it quoted (and with no statement of units, nothing at all)."""

    EXAM = dict(code='45378', act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY)

    def test_unlisted_scope_names_the_examination_by_its_service_with_no_quote(self):
        """Restated for D281 (B6): row 7's done, "documented as performed, in full or in part, on the date of service"."""
        item = wording.build(M.UNLISTED_SCOPE, wording.Slots(**self.EXAM, statements=(W9_PRIOR,)), W9_TEXT)
        self.assertEqual(item.question, 'Is the colonoscopy documented as performed, in full or in part, on the date of '
                                        'service?')
        self.assertEqual(item.reason, 'The document states “It is not known whether she had a colonoscopy before.”, which '
                                      'names no procedure session; CPT Studio could not confirm from the document whether '
                                      'it is about the colonoscopy. Held for the reviewer, not excluded.')
        item = wording.build(M.UNLISTED_SCOPE, wording.Slots(**self.EXAM), W9_TEXT)
        self.assertEqual((item.question, item.reason),
                         ('Is the colonoscopy documented as performed, in full or in part, on the date of service?',
                          'A statement in the document names no procedure session; CPT Studio could not confirm from the '
                          'document whether it is about the colonoscopy. Held for the reviewer, not excluded.'))

    def test_doubt_names_the_examination_by_its_service_with_no_quote(self):
        """Restated for D281: the session's DOUBT asks row 7's done (B6); a denial's reason never asserts its scope (B5)."""
        question = 'Confirm whether the colonoscopy is documented as performed, in full or in part, on the date of service.'
        for what, statements, reason in (
                (None, (W9_PRIOR,), 'The document leaves the colonoscopy in doubt: “It is not known whether she had a '
                                    'colonoscopy before.”.'),
                (UnlistedWhat.DOUBT, (), 'The document leaves the colonoscopy in doubt.'),
                (UnlistedWhat.DENIAL, (W9_NONE_TODAY,), 'The document states “No colonoscopy was performed today.”, a '
                                                        'statement that an act was not done; CPT Studio could not '
                                                        'confirm from the document whether it is about the colonoscopy.'),
                (UnlistedWhat.DENIAL, (), 'The document states that an act was not done; CPT Studio could not confirm '
                                          'from the document whether it is about the colonoscopy.')):
            with self.subTest(what=what, statements=statements):
                item = wording.build(M.DOUBT, wording.Slots(**self.EXAM, statements=statements, unlisted_what=what),
                                     W9_TEXT)
                self.assertEqual((item.question, item.reason), (question, reason))

    def test_with_no_words_the_question_quotes_nothing_for_every_service(self):
        for family in (None, *SessionKind):
            for what in (None, *UnlistedWhat):
                for message in (M.UNLISTED_SCOPE, M.DOUBT):
                    item = wording.build(message, wording.Slots(act=Kind.EXAMINATION, family=family, unlisted_what=what,
                                                                statements=(W9_PRIOR,)), W9_TEXT)
                    self.assertNotIn('“', item.question, (family, what, message))
                    self.assertEqual(sentence_problems(item.question, W9_TEXT), [])
                    self.assertEqual(sentence_problems(item.reason, W9_TEXT), [])


class D267Bundled(SimpleTestCase):
    """D267 (refute-r3c-r1 F6; TRIAGE G1-07): BUNDLED with a requirement group that names no act - () or (OTHER,) - words
    the code itself, as NOT_DOCUMENTED and METHOD do, never a bare 'act' standing for a kind ("The act documented ...",
    "No separate act is documented for this code."); a group that names an act keeps v1's sentence."""

    RULE = wording.BUNDLING_WHY[wording.Bundling.CLIP]

    def test_a_group_that_names_no_act_words_the_code(self):
        for group in ((), (Kind.OTHER,), (Kind.OTHER, Kind.OTHER)):
            with self.subTest(group=group):
                item = wording.build(M.BUNDLED, wording.Slots(code='45385', act=Kind.SNARE, group=group, words=W9_CLIP,
                                                              bundling=wording.Bundling.CLIP,
                                                              family=SessionKind.COLONOSCOPY), W9_TEXT)
                self.assertEqual((item.message, item.fact, item.kind), (M.BUNDLED, 'performed_status',
                                                                        ItemKind.EXPLANATION))
                self.assertEqual(item.question, 'The documented act (“A clip was placed at the polypectomy site.”) that '
                                                '45385 accounts for is part of another procedure documented with it. Was '
                                                'a separate act that 45385 accounts for performed on the date of '
                                                'service?')
                self.assertEqual(item.reason, 'The colonoscopy is documented as performed with snare removal, which is '
                                              f'part of another documented act: {self.RULE} No separate act that 45385 '
                                              'accounts for is documented.')

    def test_f6s_input_and_no_code(self):
        for group in ((), (Kind.OTHER,)):  # refute-r3c-r1 F6's exact input
            item = wording.build(M.BUNDLED, wording.Slots(code='45385', act=Kind.SNARE, group=group,
                                                          bundling=wording.Bundling.CLIP), '')
            self.assertEqual(item.question, 'The documented act that 45385 accounts for is part of another procedure '
                                            'documented with it. Was a separate act that 45385 accounts for performed on '
                                            'the date of service?')
            for sentence in (item.question, item.reason):
                self.assertNotIn('The act documented', sentence)
                self.assertNotRegex(sentence, r'separate act (?:performed|is documented)')  # no bare 'act' for a kind
                self.assertEqual(sentence_problems(sentence, ''), [], sentence)
        item = wording.build(M.BUNDLED, wording.Slots(), '')  # BUNDLED carries no code by construction: this code's
        self.assertEqual((item.question, item.reason),
                         ('The documented act that this code accounts for is part of another procedure documented with '
                          'it. Was a separate act that this code accounts for performed on the date of service?',
                          'The procedure is documented as performed with another act, which is part of another '
                          'documented act. No separate act that this code accounts for is documented.'))

    def test_a_group_that_names_an_act_keeps_v1s_sentence(self):
        for group in ((Kind.CLIP,), (Kind.CLIP, Kind.OTHER)):
            item = wording.build(M.BUNDLED, wording.Slots(code='45385', listed=(Kind.SNARE,), group=group, words=W9_CLIP,
                                                          bundling=wording.Bundling.CLIP,
                                                          family=SessionKind.COLONOSCOPY), W9_TEXT)
            detail, question = wording.act_included('colonoscopy', 'performed', 'snare removal', self.RULE,
                                                    'clip placement', wording.span_text(W9_TEXT, W9_CLIP))
            self.assertEqual((item.question, item.reason), (question, detail))
            self.assertNotIn('45385 accounts for', item.question + item.reason)


class D267PossibleRoute(SimpleTestCase):
    """D267 (refute-r4a-r2 F5; TRIAGE G1-05; D254 rule 1): a route the Fill marks as only possible - the optional Slots
    field possible_approaches, for step r4a (classes.doubted_routes: a doubted or unresolved through, or an anatomy entry
    whose type is not established) - is worded as possible, never "the documented pouch" or "the documented stoma";
    ``approaches`` keeps v1's "through the documented <anatomy>" for a route the anatomy establishes."""

    BASE = dict(code='44360', act=Kind.EXAMINATION, family=SessionKind.ENTEROSCOPY,
                enteroscopy_class=EnteroscopyClass.JEJUNAL, reached=Extent.JEJUNUM, words=W9_REACH)
    JEJUNAL = ('a small-bowel enteroscopy past the second portion of the duodenum that stops short of the ileum')
    TWO = (Approach.THROUGH_STOMA, Approach.THROUGH_POUCH)

    def route(self, **slots):
        return wording.build(M.ENTEROSCOPY_ROUTE, wording.Slots(**{**self.BASE, **slots}), W9_TEXT)

    def test_f5s_two_routes_of_an_entry_of_no_type_are_possible(self):
        """F5's input: 44360, approach supported oral, reached the jejunum, through doubted (or unresolved) naming Y1,
        Y1's type silent - both routes only possibly opened."""
        item = self.route(possible_approaches=self.TWO)
        ways = 'whether it was passed through the mouth or possibly through a pouch or a stoma'
        self.assertEqual(item.question, 'The documented enteroscopy (“The scope was advanced to the jejunum.”) reached '
                                        f'the jejunum; CPT Studio could not confirm from the document {ways}. Was '
                                        f'{self.JEJUNAL} performed on the date of service?')
        self.assertEqual(item.reason, 'The enteroscopy is documented as reaching the jejunum (“The scope was advanced to '
                                      f'the jejunum.”), and CPT Studio could not confirm from the document {ways}; 44360 '
                                      f'accounts for {self.JEJUNAL}, which CPT Studio could not find in the document.')
        for sentence in (item.question, item.reason):
            self.assertNotIn('documented pouch', sentence)
            self.assertNotIn('documented stoma', sentence)

    def test_f5s_state_from_the_engines_item_once_the_fill_marks_the_route(self):
        """refute-r4a-r2 F5's own state (probes/w2_oral_type_open.py): 44360 on an enteroscopy X1, approach supported
        oral, reached the jejunum, its through doubted naming Y1 whose type is silent. The engine's ENTEROSCOPY_ROUTE
        item, its slots marked as step r4a is asked to fill them (request R1: ``approaches`` the routes classes.routes
        establishes, ``possible_approaches`` those classes.doubted_routes leaves open), worded as the renderer words a
        Fill (jobs._slots_of, then wording.build): "possibly through a pouch or a stoma", never "the documented"."""
        import dataclasses

        from studio import jobs
        from studio.interpretation.engine import classes
        from tests.v2 import test_assess as TA
        from tests.v2.evaluate_fixtures import Doc, X, Y, doubted, sup, unit
        doc = Doc()
        doc.session(1, SessionKind.ENTEROSCOPY, approach=sup(Approach.ORAL, spans=(unit(4),)),
                    reached=[sup(Extent.JEJUNUM, spans=(unit(6),))], through=doubted(Y(1), spans=(unit(8),)))
        doc.exam(1)
        doc.entry(1, type=None)
        R = doc.build()
        found = TA.run(R, ('44360', 1)).codes[0]
        self.assertEqual(found.item.message.value, 'enteroscopy_route')  # r4a-2's _two_routes (D253 QX (ii))
        established, possible = classes.routes(X(1), R), classes.doubted_routes(X(1), R)
        self.assertEqual((established, possible), (frozenset(), frozenset(self.TWO)))
        slots = dataclasses.replace(jobs._slots_of(found.item.fill),
                                    approaches=tuple(way for way in Approach if way in established),
                                    possible_approaches=tuple(way for way in Approach if way in possible))
        item = wording.build(M.ENTEROSCOPY_ROUTE, slots, TA.TEXT)
        for sentence in (item.question, item.reason):
            self.assertIn('could not confirm from the document whether it was passed through the mouth or possibly '
                          'through a pouch or a stoma', sentence)
            self.assertNotIn('documented pouch', sentence)
            self.assertNotIn('documented stoma', sentence)
            self.assertEqual(sentence_problems(sentence, TA.TEXT), [], sentence)

    def test_an_established_route_keeps_v1s_words_and_the_marker_wins(self):
        mixed = self.route(approaches=(Approach.THROUGH_STOMA,), possible_approaches=(Approach.THROUGH_POUCH,))
        self.assertIn('through the mouth or through the documented stoma or possibly through a pouch.', mixed.question)
        established = self.route(approaches=self.TWO)  # v1's (classes.class_hold's route form)
        self.assertIn('through the mouth or through the documented pouch or through the documented stoma.',
                      established.question)
        both = self.route(approaches=self.TWO, possible_approaches=(Approach.THROUGH_POUCH,))  # in both: possible
        self.assertIn('through the mouth or through the documented stoma or possibly through a pouch.', both.question)
        self.assertIn('through a stoma or pouch.', self.route().question)  # neither given: as before

    def test_no_route_marked_possible_is_ever_documented(self):
        """Every subset of the approaches as established and as possible, for ENTEROSCOPY_ROUTE and EXAMINATION_ROUTE (the
        stoma EUS class, every approach of the examination's own): a possible route is never "the documented" one; a
        route only established always is."""
        import itertools
        subsets = [tuple(group) for size in range(len(Approach) + 1) for group in itertools.combinations(Approach, size)]
        anatomy = wording.APPROACH_ANATOMY
        checked = 0
        for established in subsets:
            for possible in subsets:
                if len(established) > 3 or len(possible) > 3:
                    continue
                item = self.route(approaches=established, possible_approaches=possible)
                said = item.question + ' ' + item.reason
                for way, name in anatomy.items():
                    if way in possible:
                        self.assertNotIn(f'documented {name}', said)
                        self.assertRegex(said, rf'possibly through (?:a \w+ or )*a {name}\b')
                    elif way in established:
                        self.assertIn(f'through the documented {name}', said)
                for approach in (None, *Approach):
                    exam = wording.build(M.EXAMINATION_ROUTE, wording.Slots(
                        code='43242', exam_class=EusClass.STOMA, approach=approach, approach_words=W9_STOMA,
                        approaches=established, possible_approaches=possible), W9_TEXT)
                    said = exam.question + ' ' + exam.reason
                    marked = Approach.THROUGH_STOMA in possible or Approach.THROUGH_STOMA not in established
                    self.assertEqual('documented stoma' in said, not marked, (established, possible, approach))
                    for sentence in (exam.question, exam.reason):
                        self.assertEqual(sentence_problems(sentence, W9_TEXT), [], sentence)
                checked += 1
        self.assertGreater(checked, 1000)

    def test_the_examination_route_with_a_possible_stoma(self):
        stoma_class = 'an endoscopic ultrasound examination through a colonoscopy by way of a stoma'
        item = wording.build(M.EXAMINATION_ROUTE, wording.Slots(
            code='43242', exam_class=EusClass.STOMA, approaches=(Approach.THROUGH_STOMA,),
            possible_approaches=(Approach.THROUGH_STOMA,)), W9_TEXT)
        self.assertEqual(item.question, 'CPT Studio could not confirm from the document whether the documented endoscopic '
                                        f'ultrasound examination was passed through a stoma. Was {stoma_class} performed '
                                        'on the date of service?')
        item = wording.build(M.EXAMINATION_ROUTE, wording.Slots(
            code='43242', exam_class=EusClass.STOMA, approach=Approach.THROUGH_STOMA, approach_words=W9_STOMA,
            approaches=(Approach.THROUGH_STOMA,), possible_approaches=(Approach.THROUGH_STOMA,)), W9_TEXT)
        self.assertEqual(item.question, 'The documented endoscopic ultrasound examination is stated to be passed through a '
                                        'stoma (“The echoendoscope entered through the stoma.”); CPT Studio could not '
                                        f'confirm from the document that the patient has a stoma. Was {stoma_class} '
                                        'performed on the date of service?')

    def test_the_marker_is_an_optional_typed_slot_appended_last(self):
        # restated for step f3w: D280.3's two optional fields (held, techniques) are appended after it
        self.assertEqual([field for field in wording.Slots.__dataclass_fields__][-3:],
                         ['possible_approaches', 'held', 'techniques'])
        self.assertEqual(wording.Slots().possible_approaches, ())
        self.assertEqual(wording._SLOT_TYPES['possible_approaches'], (Approach, True))
        for value in ('through_stoma', (Kind.SNARE,), Approach.THROUGH_STOMA, ('through_pouch',)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                wording.Slots(possible_approaches=value)
        self.assertIn('possible_approaches', reads_of(M.ENTEROSCOPY_ROUTE))
        self.assertIn('possible_approaches', reads_of(M.EXAMINATION_ROUTE))


# --- step f3w of AMENDMENT-2's build round (DECISIONS D280-D284; build list B1, B3, B5, B6, B7) -------------------------

# the claimed examination's own sentence (any unit of W9_TEXT stands for it here), the held session's examination's
W9_CLAIMED = W9_NONE_TODAY
DS = dict(code='45385', act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY, words=W9_REACH, statements=(W9_CLAIMED,))
DS_ASK = ('Is the colonoscopy (“The scope was advanced to the jejunum.”) documented as performed, in full or in part, on '
          'the date of service?')
DS_STATED = ('The document states “No colonoscopy was performed today.”, a statement whose technique CPT Studio could not '
             'confirm from the document')
R_ = requirements.Rank


class D280DigitalScope(SimpleTestCase):
    """DECISIONS D280.3 (build list B1): DIGITAL_SCOPE words every hold resting on an examination whose device claims
    manual without establishing it as D258 asks - the question names the held session's examination by its service and
    asks whether it is documented as performed, in full or in part, on the date of service, quoting only ``words`` (the
    session's examination that may be quoted, never the claimed one); the reason quotes the claimed examination's own
    words (``statements``' first) as a statement whose technique CPT Studio could not confirm, and states its open fact
    by the held fact's RANK row (``held``) and attribute - its sides for a conflict, the owner for an entry, more than one
    technique stated (``techniques``), and, with no attribute (a pair whose statement it is), whether it is about that
    examination. The clarification keeps the held fact's key (fact_key from ``held`` and, for a conflict, ``act``)."""

    @staticmethod
    def worded(**slots):
        return wording.build(M.DIGITAL_SCOPE, wording.Slots(**{**DS, **slots}), W9_TEXT)

    def test_the_entry(self):
        spec = wording.MESSAGES[M.DIGITAL_SCOPE]
        self.assertEqual((M.DIGITAL_SCOPE.value, spec.fact, spec.kind, spec.rank, spec.needs),
                         ('digital_scope', 'performed_status', ItemKind.QUESTION, 2, ('held', 'act')))
        self.assertIn('held', wording.CARRIED)
        self.assertIn('digital_scope', wording.CARRIED['act'])
        self.assertEqual(wording._SLOT_TYPES['held'], (requirements.Rank, False))
        self.assertEqual(wording._SLOT_TYPES['techniques'], (bool, False))
        self.assertEqual((wording.Slots().held, wording.Slots().techniques), (None, False))
        for value in (4, 'status', requirements.FactKey.PERFORMED_STATUS):
            with self.subTest(value=value), self.assertRaises(ValueError):
                wording.Slots(held=value)

    def test_each_open_fact_in_its_exact_text(self):
        """Every row a hold on a claimed examination can rest on - its own facts (row 7's status, doubt, date, performer,
        entry, a conflict, its session tie) and a pair whose statement it is (no attribute: statement_scope, procedure,
        technique, timing, performer rows) - in its exact sentence; the question is the same for every one."""
        about = 'CPT Studio could not confirm from the document whether it is about the colonoscopy'
        cases = (
            (dict(held=R_.STATUS, attribute=Attribute.STATUS), 'it is not established as done on the date of service'),
            (dict(held=R_.STATUS, attribute=Attribute.SESSION),
             'CPT Studio could not confirm from the document in which procedure it was done'),
            (dict(held=R_.STATUS, attribute=Attribute.KIND), 'CPT Studio could not confirm from the document what was done'),
            (dict(held=R_.DOUBT, attribute=Attribute.STATUS), 'the document leaves it in doubt'),
            (dict(held=R_.TIME, attribute=Attribute.DATE_RELATION),
             'CPT Studio could not confirm from the document when it was done'),
            (dict(held=R_.PERFORMER, attribute=Attribute.PERFORMER),
             'CPT Studio could not confirm from the document who performed it'),
            (dict(held=R_.ENTRY, attribute=Attribute.ENTRY, owner=Owner.NURSING), 'it is told only in the nursing entry'),
            (dict(held=R_.ENTRY, attribute=Attribute.ENTRY, owner=Owner.OTHER_CLINICIAN),
             "it is told only in another clinician's entry"),
            (dict(held=R_.ENTRY, attribute=Attribute.ENTRY),
             'CPT Studio could not confirm from the document whose entry it is told in'),
            (dict(held=R_.ENTRY, attribute=Attribute.ENTRY, owner=Owner.DOCUMENTING_CLINICIAN),
             'CPT Studio could not confirm from the document whose entry it is told in'),  # contradicts the row: absent
            (dict(held=R_.CONFLICT, attribute=Attribute.STATUS, statements=(W9_CLAIMED, W9_PRIOR, W9_CLAIMED)),
             'statements in the document disagree about whether it was done (“It is not known whether she had a '
             'colonoscopy before.”; “No colonoscopy was performed today.”)'),
            (dict(held=R_.CONFLICT, attribute=Attribute.DATE_RELATION, statements=(W9_CLAIMED, W9_PRIOR)),
             'the document is not consistent about when it was done (“It is not known whether she had a colonoscopy '
             'before.”)'),
            (dict(held=R_.CONFLICT, attribute=Attribute.STATUS, statements=(W9_CLAIMED, W9_CLAIMED)),
             'the document is not consistent about whether it was done'),  # its one side is the statement quoted
            (dict(held=R_.CONFLICT, attribute=Attribute.ENTRY), 'the document is not consistent about whose entry it is '
                                                                'told in'),
            *((dict(held=rank), about) for rank in (R_.STATEMENT_SCOPE, R_.PROCEDURE, R_.TECHNIQUE, R_.TIME,
                                                     R_.PERFORMER)),
        )
        for slots, open_fact in cases:
            with self.subTest(**{key: getattr(value, 'value', value) for key, value in slots.items()
                                 if key != 'statements'}):
                item = self.worded(**slots)
                self.assertEqual(item.question, DS_ASK)
                self.assertEqual(item.reason, f'{DS_STATED}; {open_fact}. {wording.HELD}')

    def test_more_than_one_technique_and_no_statement_or_words(self):
        item = self.worded(held=R_.STATUS, attribute=Attribute.STATUS, techniques=True)
        self.assertEqual(item.reason, f'{DS_STATED} (the document states more than one technique for it); it is not '
                                      f'established as done on the date of service. {wording.HELD}')
        item = wording.build(M.DIGITAL_SCOPE, wording.Slots(act=Kind.EXAMINATION, held=R_.TIME,
                                                             attribute=Attribute.DATE_RELATION), W9_TEXT)
        self.assertEqual((item.question, item.reason),
                         ('Is the examination documented as performed, in full or in part, on the date of service?',
                          'A statement in the document names an examination whose technique CPT Studio could not '
                          'confirm from the document; CPT Studio could not confirm from the document when it was done. '
                          f'{wording.HELD}'))
        item = self.worded(held=R_.PROCEDURE, family=SessionKind.EGD, words=(), statements=((),))
        self.assertEqual(item.question, 'Is the upper endoscopy documented as performed, in full or in part, on the date '
                                        'of service?')

    def test_the_clarification_keeps_the_held_facts_key(self):
        """D280.3: "The held facts, rank and status are unchanged. The clarification keeps the held fact's key, so an
        answer binds as today; a message may take its key from the item (wording.fact_key)": for every RANK row, the
        row's fact key (the first of a row of several), conflict:<act> for the conflict row - never MESSAGES' own fact."""
        for rank in requirements.Rank:
            key = requirements.RANK[rank][0]
            for act in (Kind.EXAMINATION, Kind.OTHER, Kind.SNARE):
                with self.subTest(rank=rank, act=act):
                    expected = f'conflict:{act.value}' if key is requirements.FactKey.CONFLICT else key.value
                    slots = wording.Slots(**{**DS, 'act': act, 'held': rank})
                    self.assertEqual(wording.fact_key(M.DIGITAL_SCOPE, slots), expected)
                    self.assertEqual(wording.build(M.DIGITAL_SCOPE, slots, W9_TEXT).fact, expected)
        with self.assertRaises(ValueError):
            wording.build(M.DIGITAL_SCOPE, wording.Slots(**DS), W9_TEXT)  # no held row: refused (CARRIED)

    def test_it_never_asks_about_the_claimed_examination(self):
        """Over every RANK row, every attribute and owner: the claimed examination's words are never in the question
        (a truthful "Not documented" about it would exclude the code: D258), always in the reason; no "in doubt" of the
        session's examination, no provider, cause or placeholder; the question is row 7's done."""
        claimed = '“No colonoscopy was performed today.”'
        built = 0
        for rank in requirements.Rank:
            for attribute in (None, *Attribute):
                for owner in (None, Owner.NURSING):
                    item = self.worded(held=rank, attribute=attribute, owner=owner, techniques=bool(built % 2))
                    built += 1
                    self.assertNotIn(claimed, item.question)
                    self.assertIn(claimed, item.reason)
                    self.assertTrue(item.question.endswith('documented as performed, in full or in part, on the date of '
                                                           'service?'))
                    self.assertNotIn('the colonoscopy in doubt', item.reason)
                    for sentence in (item.question, item.reason):
                        self.assertEqual(sentence_problems(sentence, W9_TEXT), [], sentence)
        self.assertEqual(built, len(requirements.Rank) * (len(Attribute) + 1) * 2)


class D281Forms(SimpleTestCase):
    """DECISIONS D281 (step f3w): B3 (G1-05 (ii)) - ANOTHER_ENTRY names the code's group ("this code accounts for") only
    for the code's own act; a session's examination the group does not name is named by the item's act (case B: "The
    colonoscopy is documented only in the nursing entry (...)"); B6 (G3-27) - the held session's examination is asked by
    row 7's done, "documented as performed, in full or in part, on the date of service", in UNLISTED_SCOPE, the
    session's DOUBT and DIGITAL_SCOPE, while every other act keeps v1's "was done"."""

    def test_case_b_the_colonoscopy_told_only_in_the_nursing_entry(self):
        item = wording.build(M.ANOTHER_ENTRY, wording.Slots(code='45385', act=Kind.EXAMINATION,
                                                            family=SessionKind.COLONOSCOPY, group=(Kind.SNARE,),
                                                            words=W9_REACH, owner=Owner.NURSING), W9_TEXT)
        self.assertEqual(item.question, 'The colonoscopy is documented only in the nursing entry (“The scope was advanced '
                                        'to the jejunum.”). Was it performed in this colonoscopy on the date of service?')
        self.assertEqual(item.reason, 'The colonoscopy is documented only in the nursing entry (“The scope was advanced to '
                                      'the jejunum.”), not by the physician performing the colonoscopy. Held for the '
                                      'reviewer, not excluded.')
        self.assertNotIn('this code accounts for', item.question + item.reason)
        self.assertNotIn('snare', item.question + item.reason)

    def test_the_codes_own_act_keeps_its_group(self):
        """Case C (the snare itself in the nursing entry), 45378's own examination, and the code's own act of a kind not
        established (D2xx's first prototype would have renamed it): "this code accounts for" as before."""
        for slots, what in ((dict(code='45385', act=Kind.SNARE, group=(Kind.SNARE,)), 'The snare removal'),
                            (dict(code='45378', act=Kind.EXAMINATION, group=(Kind.EXAMINATION,)), 'The colonoscopy'),
                            (dict(code='45385', act=Kind.OTHER, group=(Kind.SNARE,)), 'The snare removal'),
                            (dict(code='45385', group=(Kind.SNARE,)), 'The snare removal')):
            with self.subTest(**{key: str(value) for key, value in slots.items()}):
                item = wording.build(M.ANOTHER_ENTRY, wording.Slots(**slots, family=SessionKind.COLONOSCOPY,
                                                                    words=W9_SNARED, owner=Owner.NURSING), W9_TEXT)
                self.assertTrue(item.reason.startswith(f'{what} this code accounts for is documented only in the '
                                                       'nursing entry'), item.reason)

    def test_the_held_sessions_examination_is_asked_by_row_7s_done(self):
        done = 'documented as performed, in full or in part, on the date of service'
        for message, slots, question in (
                (M.UNLISTED_SCOPE, dict(act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY, words=W9_REACH),
                 f'Is the colonoscopy (“The scope was advanced to the jejunum.”) {done}?'),
                (M.DOUBT, dict(act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY, words=W9_REACH),
                 f'Confirm whether the colonoscopy (“The scope was advanced to the jejunum.”) is {done}.'),
                (M.DOUBT, dict(act=Kind.EXAMINATION, words=W9_REACH),  # the examination its own unit speaks of
                 'Confirm whether the examination (“The scope was advanced to the jejunum.”) was done on the date of '
                 'service.'),
                (M.DOUBT, dict(act=Kind.SNARE, family=SessionKind.COLONOSCOPY, words=W9_SNARED),  # another act: v1's
                 'Confirm whether the snare removal (“A cold snare polypectomy of the 6 mm sigmoid polyp was '
                 'performed.”) was done on the date of service.'),
                (M.DIGITAL_SCOPE, dict(DS, held=R_.STATUS, attribute=Attribute.STATUS), DS_ASK)):
            with self.subTest(message=message, act=slots.get('act'), family=slots.get('family')):
                item = wording.build(message, wording.Slots(**slots), W9_TEXT)
                self.assertEqual(item.question, question)


class D284Addon(SimpleTestCase):
    """DECISIONS D284 (G3-15; build list B7): ADDON words an add-on its ADDON row holds from ``code`` and ``codes`` alone -
    none of its primary codes is counted for this encounter - TEXT_FREE (it reads no document text and quotes nothing),
    asking no fact of the add-on's act, never "could not confirm ... done", with a true form for no codes (D254 rule 1);
    its fact key and rank are the ADDON row's (performed_status, rank 4, a question)."""

    def test_the_entry(self):
        spec = wording.MESSAGES[M.ADDON]
        self.assertEqual((M.ADDON.value, spec.fact, spec.kind, spec.rank, spec.needs),
                         ('addon', 'performed_status', ItemKind.QUESTION, 4, ('code',)))
        self.assertEqual([member.value for member in M][-1], 'addon')

    def test_every_present_and_absent_combination(self):
        cases = (
            (('99215',), '99417 is reported only together with one of its primary codes (99215), and none of them is '
                         'counted for this encounter. Is one of them documented as performed on the date of service?',
             '99417 is an add-on code: it is reported only together with one of its primary codes (99215), and none of '
             f'them is counted for this encounter. {wording.HELD}'),
            (('99205', '99215', '99245'), '99417 is reported only together with one of its primary codes (99205, 99215 '
                                          'or 99245), and none of them is counted for this encounter. Is one of them '
                                          'documented as performed on the date of service?',
             '99417 is an add-on code: it is reported only together with one of its primary codes (99205, 99215 or '
             f'99245), and none of them is counted for this encounter. {wording.HELD}'),
            ((), '99417 is reported only together with a primary code, and none is counted for this encounter. Is one '
                 'documented as performed on the date of service?',
             '99417 is an add-on code: it is reported only together with a primary code, and none is counted for this '
             f'encounter. {wording.HELD}'),
        )
        for codes, question, reason in cases:
            for family in (None, SessionKind.OFFICE_EM):
                with self.subTest(codes=codes, family=family):
                    item = wording.build(M.ADDON, wording.Slots(code='99417', codes=codes, family=family), '')
                    self.assertEqual((item.question, item.reason, item.fact), (question, reason, 'performed_status'))
                    for sentence in (item.question, item.reason):
                        self.assertNotIn('“', sentence)
                        self.assertNotRegex(sentence, r'could not confirm.*done')
                        self.assertEqual(sentence_problems(sentence, ''), [], sentence)
        self.assertEqual(wording.build(M.ADDON, wording.Slots(code='43273', codes=('43260', '43260')), '').question,
                         '43273 is reported only together with one of its primary codes (43260), and none of them is '
                         'counted for this encounter. Is one of them documented as performed on the date of service?')

    def test_it_reads_no_text_and_every_slot_it_reads(self):
        """TEXT_FREE: worded over an empty revision text exactly as over any; the slots it reads are code and codes."""
        slots = wording.Slots(**FIXTURES[M.ADDON])
        self.assertEqual(wording.build(M.ADDON, slots, ''), wording.build(M.ADDON, slots, TEXT))
        self.assertEqual(reads_of(M.ADDON), frozenset({'code', 'codes'}))
