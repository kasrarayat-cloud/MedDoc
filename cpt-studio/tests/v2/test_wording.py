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
- the copies of v1's words (assess, classes, coverage, ercp, events, checks, mapping, derive) equal their originals.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from studio import customer_api
from studio.interpretation import wording
from studio.interpretation.contract.types import (Approach, Device, Extent, Kind, Landmark, Owner, SessionKind, Span,
                                                  Station, Tract)
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

    def test_slots_that_contradict_the_message_are_refused(self):
        for message, changes in ((M.ANOTHER_TRACT, {'tract': Tract.UPPER}),
                                 (M.ANOTHER_TRACT, {'required_tract': Tract.PANCREATOBILIARY}),
                                 (M.ANOTHER_TECHNIQUE, {'stated': TechniqueClass.BALLOON}),
                                 (M.ANOTHER_ENTRY, {'owner': Owner.DOCUMENTING_CLINICIAN}),
                                 (M.ANOTHER_SITE, {'place': Landmark.OTHER}),
                                 (M.STATION_CLASS, {'denied': (), 'stations': (Station.STOMACH,)}),
                                 (M.PART, {'bundling': wording.Bundling.CLIP}),
                                 (M.CONFLICT_FACT, {'statements': (DENIAL,)}),
                                 (M.SEPARATE_EM, {'listed': (), 'possible': ()}),
                                 (M.BASE_EXPLAINED, {'codes': (), 'listed': ()})):
            with self.subTest(message=message, changes=changes), self.assertRaises(ValueError):
                built(message, **changes)


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
        item = built(M.BASE_WITHIN)
        self.assertEqual((item.question, item.reason), (spec.question, spec.reason))
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
        with self.assertRaises(ValueError):
            phrase()

    def test_group_and_service_phrases(self):
        def group(*kinds, family=None):
            return wording.group_phrase(wording.Slots(group=kinds, family=family))
        self.assertEqual(group(Kind.EXAMINATION, family=SessionKind.EUS), 'endosonographic examination')
        self.assertEqual(group(Kind.EXAMINATION, family=SessionKind.EGD), 'upper endoscopy')
        self.assertEqual(group(Kind.EXAMINATION), 'examination')
        self.assertEqual(group(Kind.SNARE, Kind.EMR, Kind.SNARE), 'snare removal or endoscopic mucosal resection')
        with self.assertRaises(ValueError):
            group()
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
