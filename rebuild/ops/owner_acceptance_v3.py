"""Reviewed, bounded owner acceptance protocol for the private QuillMD app.

This operational tool changes no clinical generation, application security,
services or existing records. Installed entry points require the normal ruled
door, exact cited sources, genuine recovery evidence and fresh native admissions.
Default invocation describes the scope without accessing installed state.
"""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import argparse
import ast
import base64
import copy
import fcntl
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
import re
import signal
import stat
import subprocess
import sys
import time
import types

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
RUNTIME = APP / '.runtime'
BASE = RUNTIME / 'owner-demo-20261006'
FROZEN = BASE / 'recovery-20261007/acceptance-v3-preparation-v2-20261007'
SOURCE = Path(__file__).resolve().parents[2]
SELF = 'rebuild/ops/owner_acceptance_v3.py'
TEST = 'rebuild/ops/test_owner_acceptance_v3.py'
ENTRY = 'scripts/run-owner-acceptance-v3.py'
DECL = 'docs/foundation/mutations/20261007-quillmd-owner-acceptance-v3.md'
ALLOWED = frozenset((SELF, TEST, ENTRY, DECL))
M6 = '4194f58cb37b13e179810db486b54bf2fe7a42a8'
OPERATIONS_REVISION_POLICY = 'derive_clean_canonical_worktree_head_with_exact_or_reviewed_normal_descendant_main_and_ci_v2'
NORMAL_DECL = 'docs/foundation/mutations/20261007-quillmd-owner-normal443.md'
NORMAL_SELF = 'rebuild/ops/owner_normal_origin.py'
NORMAL_ALLOWED = frozenset((NORMAL_DECL, NORMAL_SELF, 'rebuild/ops/test_owner_normal_origin.py',
    'scripts/prepare-owner-normal-origin.py', 'rebuild/deploy/owner-normal-https.conf',
    'rebuild/quillmd/settings.py', 'rebuild/core/preview_access.py',
    'rebuild/core/tests/test_owner_normal_origin.py'))
NORMAL_RUNTIME_BINDING = 'private-acceptance-completion-cross-hashes-v1'
NATIVE_NAMES = ('managed_helper', 'private_storage', 'backup_restore', 'email_activation',
                'activation_exclusion', 'legacy_model_activation', 'repair_source_permissions',
                'publisher_verification', 'private_availability_recovery')
USED_SOURCE = ALLOWED | frozenset('rebuild/ops/' + name + '.py' for name in NATIVE_NAMES) | frozenset((
    'scripts/check-citation.sh', 'scripts/lib/runs-api.sh',
    'docs/foundation/mutations/20261007-quillmd-private-availability-recovery.md'))
ORIGIN = 'https://app.quillmd.com:9443'
MODEL = 'claude-sonnet-5-5'
PROFILE = {'max_tokens': 6000, 'timeout_seconds': 60, 'max_retries': 0,
           'thinking': 'provider_default', 'effort': 'provider_default', 'inference_geo': 'provider_default'}
PRICING = 'configured-v1:a2f0c372e0933e2ba28ea9219a8758571af82e675aec749f6f73e41d4ffa4686'
CASES = ('soap-typed', 'custom-word-typed', 'soap-voice', 'allergy-missing', 'allergy-legitimate')
UNITS = tuple('quillmd-fresh-' + name + '.service' for name in ('doctor', 'admin', 'worker'))
AVAILABILITY = RUNTIME / 'private-availability-recovery-20261007'
PREPARATION = BASE / 'installed-acceptance-v3-preparation-20261007'
ADMIN = BASE / 'installed-admin-acceptance-v3-20261007'
CAMPAIGN = BASE / 'installed-acceptance-v3-20261007'
ATTEMPT = BASE / 'installed-acceptance-v3-attempt-20261007.json'
ORIGINAL = RUNTIME / 'legacy-model-demo-20261007T012249Z'
CONSUMED = RUNTIME / 'legacy-model-continuation-20261007'
PYTHON = APP / '.venv/bin/python'
LOCKS = ('legacy-model-activation.lock', 'backup-monitor/capture.lock',
         'automatic-offsite/execution.lock', 'backup-alerts/monitor.lock')
FROZEN_B77 = 'b77a1c48f2a08c8a0a73df6fc945da850bdc5f558254d32a526913409f17683c'
DEPENDENCIES = {
    'prepare-installed-admin-auth-v3.mjs': 'c8fa9d63de993fca8aacb33a0ce5f295b3a1bfdc7c685bce598acf841453e90f',
    'installed-browser-acceptance-v3.mjs': 'd58204d839ecf150bb918f34899f0d7784f312a2e3f55008248df01916667aa0',
    'verify_installed_acceptance_v3.py': '34d4d3bf0b9641a2f642717b33833beb7a7f49a0c043bc095e592c41a78b0023',
    'acceptance-v3-contract.mjs': 'e0b41fe388c1b9c7f7ac9676e1a76294cf4a45aa2a63f6564b4a69d70ca4e38f',
    'acceptance_v3_contract.py': 'ca343c4a7e320c525657d13986e83496346fce2cb97692205dfd828c9c25f668',
    'historical-qualified-policy.json': 'cc4e5221eb8bd695abd48b50c90be71c9c9a0bce59d89450299816774ec47580',
    'preparation-contract.json': '32d1f00b7b031617797b049c4f70e8a1bb178451305b95b68572945f258757c2',
    'test-preparation.py': 'c835678e5bf541172fa66a9f5b8ef07f4f080889783dfaaddc924198881847da',
}
# These are source qualifications, never environment/declaration switches.
EXECUTION_QUALIFIED = True
NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED = True
FIXED_CHILD_PROTOCOL_QUALIFIED = True
ENTRY_OBSERVATIONS = {'installed_state_accessed': False, 'authentication_possible': False,
                      'provider_possible': False}
PARENT_PHASES = ('normal-auth', 'browser', 'verify')
PUBLICATION_LOCK = 'publication/.activation-publication.lock'
PUBLISHER = 'quillmd-fresh-operations-publisher.service'
PUBLISHER_TIMER = 'quillmd-fresh-operations-publisher.timer'

# A separate exact post-restoration boundary; the historical receipt stays immutable.
POST_RESTORE_PROPOSAL = BASE / 'recovery-20261007/post-restoration-current-preservation-proposal-ee71e3-v1.json'
POST_RESTORE_PROPOSAL_SHA = '5521e9a5fc47573b8c315ccc5a7c4c38c66deb48d453f532023aae2165bf220a'
POST_RESTORE_OWNER_REPLY = BASE / 'recovery-20261007/owner-post-restoration-preservation-message-ee71e3-v1.json'
POST_RESTORE_OWNER_REPLY_SHA = '54c79de6d9d9805ceda92881db58c91447f09495391b84e526e2975be96b836f'
POST_RESTORE_PINS = {'availability_receipt_sha256': '17200fa1c565af7040033d5c34e99955976a18bc7e79c44d7be2f75690ed83bd',
 'configuration_differences': [{'before': {'device': 2050,
                                           'gid': 0,
                                           'inode': 920081,
                                           'mode': 420,
                                           'sha256': '051f70eaec42aa7c7736cefb59668b9b082989ca076c31924a320635600f96eb',
                                           'uid': 0},
                                'current': {'device': 2050,
                                            'gid': 0,
                                            'inode': 918217,
                                            'mode': 420,
                                            'sha256': '051f70eaec42aa7c7736cefb59668b9b082989ca076c31924a320635600f96eb',
                                            'uid': 0},
                                'path': '/etc/nginx/sites-available/voice.kasitcorp.com'},
                               {'before': {'device': 2050,
                                           'gid': 0,
                                           'inode': 918217,
                                           'mode': 420,
                                           'sha256': 'e7d586f4c0a3c342234533d5cc8647a982e959eb3fc847b2f867bbea1907e3c3',
                                           'uid': 0},
                                'current': {'device': 2050,
                                            'gid': 0,
                                            'inode': 918246,
                                            'mode': 420,
                                            'sha256': 'e7d586f4c0a3c342234533d5cc8647a982e959eb3fc847b2f867bbea1907e3c3',
                                            'uid': 0},
                                'path': '/etc/nginx/snippets/founder-dashboard-callback.conf'},
                               {'before': {'device': 2050,
                                           'gid': 0,
                                           'inode': 918246,
                                           'mode': 420,
                                           'sha256': '7c00d8f2f8bf1d126466ff3b8e28d0934aef6664d83c1e9f7950e3cab83d9008',
                                           'uid': 0},
                                'current': {'device': 2050,
                                            'gid': 0,
                                            'inode': 918239,
                                            'mode': 420,
                                            'sha256': '7c00d8f2f8bf1d126466ff3b8e28d0934aef6664d83c1e9f7950e3cab83d9008',
                                            'uid': 0},
                                'path': '/etc/systemd/system/founder-dashboard-callback.service'},
                               {'before': {'device': 2050,
                                           'gid': 0,
                                           'inode': 920385,
                                           'mode': 420,
                                           'sha256': 'c80609f72457a8ce056cec3fd19b2bab9c9c1edde5a35098b7071a6989c57e72',
                                           'uid': 0},
                                'current': {'device': 2050,
                                            'gid': 0,
                                            'inode': 920504,
                                            'mode': 420,
                                            'sha256': 'aac5369f1a8398e98838b28de22942e890122fe063c4594f0b1c2b96ffa58dec',
                                            'uid': 0},
                                'path': '/etc/systemd/system/voiceassistmain-product.service'}],
 'current_public_records': [{'metadata': [2050,
                                          918217,
                                          0,
                                          0,
                                          420,
                                          1549,
                                          1791399914209634909,
                                          1791399914211634948],
                             'path': '/etc/nginx/sites-available/voice.kasitcorp.com',
                             'sha256': '051f70eaec42aa7c7736cefb59668b9b082989ca076c31924a320635600f96eb'},
                            {'metadata': [2050,
                                          918246,
                                          0,
                                          0,
                                          420,
                                          722,
                                          1791399912809607089,
                                          1791399912810607109],
                             'path': '/etc/nginx/snippets/founder-dashboard-callback.conf',
                             'sha256': 'e7d586f4c0a3c342234533d5cc8647a982e959eb3fc847b2f867bbea1907e3c3'},
                            {'metadata': [2050,
                                          918239,
                                          0,
                                          0,
                                          420,
                                          685,
                                          1791399912807607049,
                                          1791399912808607069],
                             'path': '/etc/systemd/system/founder-dashboard-callback.service',
                             'sha256': '7c00d8f2f8bf1d126466ff3b8e28d0934aef6664d83c1e9f7950e3cab83d9008'},
                            {'metadata': [2050,
                                          920504,
                                          0,
                                          0,
                                          420,
                                          611,
                                          1791401765002048371,
                                          1791401765003048392],
                             'path': '/etc/systemd/system/voiceassistmain-product.service',
                             'sha256': 'aac5369f1a8398e98838b28de22942e890122fe063c4594f0b1c2b96ffa58dec'},
                            {'metadata': [2050,
                                          920502,
                                          0,
                                          0,
                                          420,
                                          87955,
                                          1791401765000048327,
                                          1791401765001048349],
                             'path': '/etc/voiceassistmain-product.json',
                             'sha256': 'c72fa8d89faeb08a45ee5650c20592965555acc40d8bc3f786f2a68caa3e6e7e'},
                            {'metadata': [2050,
                                          395871,
                                          0,
                                          0,
                                          420,
                                          1292,
                                          1791401768854132218,
                                          1791401768855132239],
                             'path': '/var/lib/voiceassistmain-product-installation/8c13fe1a-5bda-4bdf-bc73-4b5cac49b1f4.json',
                             'sha256': '47b774566b9298cf93fb7e0fd97546dae6b6130e20991aff0807b2e9ece1a8ea'}],
 'product_loaded_state': {'ActiveState': 'active',
                          'DropInPaths': '',
                          'ExecMainStartTimestampMonotonic': '338077210152',
                          'FragmentPath': '/etc/systemd/system/voiceassistmain-product.service',
                          'Group': 'voiceassistmain',
                          'InvocationID': 'f3ab81f527df45a0baa38aa22a8a22d2',
                          'LoadState': 'loaded',
                          'MainPID': '2659478',
                          'NeedDaemonReload': 'no',
                          'SubState': 'running',
                          'UnitFileState': 'enabled',
                          'User': 'voiceassistmain',
                          'WorkingDirectory': '/opt/voiceassistmain-product/releases/ee71e3c32364ca06a3a25c60'}}
PUBLISHER_JUDGE_FIELDS = ('Result', 'ExecMainStartTimestamp', 'ExecMainExitTimestamp',
                          'ExecMainStatus', 'InvocationID')
DEFERRAL_STDOUT = ('Publication deferred: an activation holds exclusion. '
                   'Nothing written; the existing row keeps its own freshness.')
REPORT = CAMPAIGN / 'independent-verification.json'
FINAL_ADMIN_STATE = CAMPAIGN / 'admin-browser-session-after-readback.json'
FIXTURE_PINS = {
    'acceptance_admin_preparation_sha256': DEPENDENCIES['prepare-installed-admin-auth-v3.mjs'],
    'acceptance_browser_sha256': DEPENDENCIES['installed-browser-acceptance-v3.mjs'],
    'acceptance_options_sha256': '748ae77377f867255a75d6717a2119f176378bd8fe02714cfbff043464ff84bc',
    'acceptance_allergy_manifest_sha256': 'eaebefde696a8944b2788bd422f7316e431fd39e07e253fcc6fababfc00aac05',
    'acceptance_allergy_form_sha256': 'ebc2189d113cc95a2289e0a65d66f07a011e91c0ef01924553838889dbab0ab9',
}


class Refusal(RuntimeError):
    pass


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()


def full_revision(value):
    require(isinstance(value, str) and re.fullmatch('[a-f0-9]{40}', value), 'v3_full_revision_required')
    return value


def stamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, AttributeError, ValueError):
        raise Refusal('v3_aware_timestamp_required') from None
    require(result.tzinfo is not None, 'v3_aware_timestamp_required')
    return result.astimezone(timezone.utc)


def execution_gate():
    require(EXECUTION_QUALIFIED and NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED
            and FIXED_CHILD_PROTOCOL_QUALIFIED, 'v3_execution_source_protocol_unqualified')


def failure_summary(error):
    """Known early zeros differ from an entered phase with an unknown outcome."""
    def constants(code):
        for value in code.co_consts:
            if isinstance(value, types.CodeType): yield from constants(value)
            elif isinstance(value, str) and re.fullmatch('v3_[a-z0-9_]{1,96}', value): yield value
    labels = {value for function in globals().values() if isinstance(function, types.FunctionType)
              for value in constants(function.__code__)}
    labels.update(node.value for node in ast.walk(ast.parse(CONFIGURATION_ADMISSION_SOURCE))
                  if isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and re.fullmatch('v3_[a-z0-9_]{1,96}', node.value))
    labels.update('v3_preserved_' + name for name in ('mail', 'static', 'configuration', 'old_files'))
    labels.update('v3_fixed_adapter_' + name for name in ('native_child_gate', 'contract_import',
        'declaration_buffer', 'runtime_authority', 'closed_citation', 'initial_gate_report'))
    label = str(error) if isinstance(error, Refusal) and str(error) in labels else 'v3_fixed_protocol_failure'
    return {'format': 3, 'complete': False, 'reason': label,
        'installed_state_accessed': ENTRY_OBSERVATIONS['installed_state_accessed'],
        'provider_calls': None if ENTRY_OBSERVATIONS['provider_possible'] else 0,
        'authentication_submissions': None if ENTRY_OBSERVATIONS['authentication_possible'] else 0,
        'database_writes': None if (ENTRY_OBSERVATIONS['provider_possible'] or ENTRY_OBSERVATIONS['authentication_possible']) else 0,
        'phase_outcomes_require_protected_receipts': ENTRY_OBSERVATIONS['provider_possible'] or ENTRY_OBSERVATIONS['authentication_possible'],
        'automatic_retries': False, 'arbitrary_exception_text_exported': False}


@contextmanager
def nofollow_parent(path):
    """Hold each parent directory while opening a bounded, fixed absolute path."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'v3_canonical_private_input')
    with ExitStack() as stack:
        parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, parent)
        for name in path.parts[1:-1]:
            parent = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, parent)
        yield parent


@contextmanager
def nofollow_file(path):
    with nofollow_parent(path) as parent:
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            yield fd
        finally:
            os.close(fd)


def bounded_bytes(path, *, private, maximum=16 * 1024 * 1024):
    with nofollow_file(path) as fd:
        before = os.fstat(fd)
        modes = (0o600,) if private else (0o644, 0o755)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 1000
                and stat.S_IMODE(before.st_mode) in modes and before.st_nlink == 1
                and before.st_size <= maximum and not os.listxattr(fd), 'v3_private_input_identity' if private
                else 'v3_public_source_identity')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(maximum + 1)
        after = os.fstat(fd)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mode,
                                item.st_uid, item.st_gid, item.st_nlink, item.st_mtime_ns, item.st_ctime_ns)
        with nofollow_file(path) as attached:
            require(identity(before) == identity(after) == identity(os.fstat(attached))
                    and len(raw) == before.st_size and not os.listxattr(fd), 'v3_private_input_race')
        return raw


def protected(path, maximum=16 * 1024 * 1024):
    return bounded_bytes(path, private=True, maximum=maximum)


def write_new(path, value):
    raw = value if isinstance(value, bytes) else encode(value) + b'\n'
    with nofollow_parent(path) as parent:
        fd = os.open(Path(path).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())


def module_from_bytes(raw, path, expected):
    require(sha(raw) == expected, 'v3_frozen_dependency_hash')
    module = types.ModuleType('_quillmd_v3_' + sha(raw)[:12])
    module.__file__ = str(path)
    module.__authenticated_source = raw
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


CONFIGURATION_ADMISSION_SOURCE = r'''
import ast as _configuration_ast
import copy as _configuration_copy

def configuration_same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (all(type(key) is str for key in left) and all(type(key) is str for key in right)
                and set(left) == set(right) and all(configuration_same(left[key], right[key]) for key in left))
    if isinstance(left, list):
        return len(left) == len(right) and all(configuration_same(a, b) for a, b in zip(left, right))
    return left == right

def current_configuration_proof(expected, current, proof):
    need(isinstance(expected, dict) and isinstance(current, dict) and isinstance(proof, dict),
         'v3_current_configuration_proof_inputs')
    need(all(type(path) is str for path in expected) and all(type(path) is str for path in current),
         'v3_current_configuration_string_paths')
    differences = POST_RESTORE_PINS['configuration_differences']
    paths = {item['path'] for item in differences}
    need(len(paths) == len(differences) == 4
         and {path for path in set(expected) | set(current)
              if path not in expected or path not in current
              or not configuration_same(expected[path], current[path])} == paths,
         'v3_current_configuration_exact_four_paths')
    need(all(configuration_same(expected.get(item['path']), item['before'])
             and configuration_same(current.get(item['path']), item['current'])
             for item in differences), 'v3_current_configuration_exact_metadata')
    need(isinstance(POST_RESTORE_OWNER_REPLY_SHA, str) and len(POST_RESTORE_OWNER_REPLY_SHA) == 64,
         'v3_current_configuration_owner_reply_required')
    required = {'format': 1, 'protocol': 'post-restoration-exact-owner-preservation-v1',
                'proposal_sha256': POST_RESTORE_PROPOSAL_SHA,
                'owner_reply_sha256': POST_RESTORE_OWNER_REPLY_SHA,
                'availability_receipt_sha256': POST_RESTORE_PINS['availability_receipt_sha256'],
                'configuration_differences': differences,
                'product_loaded_state': POST_RESTORE_PINS['product_loaded_state'],
                'historical_deployment_authorization_verified': False,
                'current_owner_preservation_authorized': True,
                'original_baseline_replaced': False, 'voiceassistmain_changes_authorized': False}
    need(configuration_same(proof, required),
         'v3_current_configuration_proof_binding')
    return True

def adapt_configuration_admission(scope, raw):
    tree = _configuration_ast.parse(raw)
    functions = [node for node in tree.body if isinstance(node, _configuration_ast.FunctionDef)
                 and node.name == 'admission']
    need(len(functions) == 1, 'v3_current_configuration_exact_frozen_admission')
    function = _configuration_copy.deepcopy(functions[0])
    expected = _configuration_ast.parse("snapshot.get(name)==receipt['before'].get(name)", mode='eval').body
    comparisons = [node for node in _configuration_ast.walk(function)
                   if isinstance(node, _configuration_ast.Compare)
                   and _configuration_ast.dump(node, include_attributes=False)
                   == _configuration_ast.dump(expected, include_attributes=False)]
    need(len(comparisons) == 1, 'v3_current_configuration_exact_frozen_predicate')
    replacement = _configuration_ast.parse(
        "(snapshot.get(name)==receipt['before'].get(name) if name!='configuration' else "
        "(configuration_same(snapshot.get(name),receipt['before'].get(name)) or "
        "current_configuration_proof(receipt['before'].get(name), snapshot.get(name), "
        "report.get('co_tenant_preservation_admission'))))", mode='eval').body
    class Replace(_configuration_ast.NodeTransformer):
        def visit_Compare(self, node):
            return _configuration_copy.deepcopy(replacement) if node is comparisons[0] else self.generic_visit(node)
    function = Replace().visit(function)
    namespace = dict(scope, current_configuration_proof=current_configuration_proof)
    exec(compile(_configuration_ast.fix_missing_locations(_configuration_ast.Module(body=[function], type_ignores=[])),
                 '<reviewed-exact-configuration-admission>', 'exec'), namespace)
    scope['admission'] = namespace['admission']
'''


def configuration_helpers(scope):
    scope.update(POST_RESTORE_PINS=copy.deepcopy(POST_RESTORE_PINS),
                 POST_RESTORE_PROPOSAL_SHA=POST_RESTORE_PROPOSAL_SHA,
                 POST_RESTORE_OWNER_REPLY_SHA=POST_RESTORE_OWNER_REPLY_SHA)
    exec(compile(CONFIGURATION_ADMISSION_SOURCE, '<reviewed-configuration-proof>', 'exec'), scope)
    return scope


def frozen_modules(reader=protected):
    """Authenticate all transitive inputs before compiling pure helpers."""
    blobs = {name: reader(FROZEN / name) for name in DEPENDENCIES}
    require(all(sha(blobs[name]) == digest for name, digest in DEPENDENCIES.items()), 'v3_transitive_dependency_drift')
    common = module_from_bytes(blobs['acceptance_v3_contract.py'], FROZEN / 'acceptance_v3_contract.py',
                               DEPENDENCIES['acceptance_v3_contract.py'])
    configuration_helpers(common.__dict__)['adapt_configuration_admission'](
        common.__dict__, blobs['acceptance_v3_contract.py'])
    original = reader(BASE / 'verify_installed_acceptance_v2.py')
    verifier = module_from_bytes(original, BASE / 'verify_installed_acceptance_v2.py', FROZEN_B77)
    adapt_publisher_adjudicator(verifier)
    return common, verifier, json.loads(blobs['historical-qualified-policy.json'])


def canonical_publisher_comparison(row):
    """Canonicalize exactly three aware timestamps; retain every other value."""
    require(isinstance(row, dict) and isinstance(row.get('id'), str),
            'v3_publisher_comparison_row')
    result = dict(row)
    for name in ('created_at', 'computed_at', 'published_at'):
        value = row.get(name)
        require(isinstance(value, (str, datetime)), 'v3_publisher_comparison_timestamp')
        try:
            stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        except ValueError:
            raise Refusal('v3_publisher_comparison_timestamp') from None
        require(stamp.tzinfo is not None, 'v3_publisher_comparison_timestamp')
        result[name] = stamp.astimezone(timezone.utc).isoformat()
    return result


def adapt_publisher_adjudicator(module):
    """Adapt only b77's final reread comparison, preserving its complete proof."""
    raw = module.__authenticated_source
    require(sha(raw) == FROZEN_B77, 'v3_frozen_dependency_hash')
    tree = ast.parse(raw)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == 'adjudicate_publisher']
    require(len(nodes) == 1, 'v3_publisher_adjudicator_population')
    function = copy.deepcopy(nodes[0])
    comparisons = [node for node in ast.walk(function) if isinstance(node, ast.Compare)
                  and ast.dump(node, include_attributes=False) == ast.dump(ast.parse(
                      "normalize(after.get('row'))==current_row", mode='eval').body,
                      include_attributes=False)]
    require(len(comparisons) == 1, 'v3_publisher_exact_final_comparison')
    call = comparisons[0].left
    call.args[0] = ast.Call(func=ast.Name(id='canonical_publisher_comparison', ctx=ast.Load()),
                            args=[call.args[0]], keywords=[])
    module.__dict__['canonical_publisher_comparison'] = canonical_publisher_comparison
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 module.__file__, 'exec'), module.__dict__)
    return module


def publisher_final_adapter(module, final_check):
    """Keep the entire authenticated proof; adapt only its last observer guard."""
    raw = module.__authenticated_source
    require(sha(raw) == FROZEN_B77 and callable(final_check), 'v3_frozen_dependency_hash')
    function = copy.deepcopy(next(node for node in ast.parse(raw).body
        if isinstance(node, ast.FunctionDef) and node.name == 'adjudicate_publisher'))
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'require'
             and len(node.args) == 2 and isinstance(node.args[1], ast.Constant)
             and node.args[1].value == 'publisher_record_changed_during_adjudication']
    expected = ast.parse("normalize(after.get('row'))==current_row and after.get('unit')==unit "
                         "and normalize(after.get('journal'))==normalize(journal)", mode='eval').body
    require(len(calls) == 1 and ast.dump(calls[0].args[0], include_attributes=False)
            == ast.dump(expected, include_attributes=False), 'v3_publisher_exact_final_comparison')
    calls[0].args[0] = ast.Call(func=ast.Name(id='publisher_final_check', ctx=ast.Load()),
        args=[ast.Name(id=name, ctx=ast.Load()) for name in ('after', 'current_row', 'unit', 'journal')], keywords=[])
    namespace = {**module.__dict__, 'publisher_final_check': final_check}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 module.__file__, 'exec'), namespace)
    return namespace['adjudicate_publisher']


def held_publication_admission(alignment, current, now):
    """The prior genuine publication and latest actual invocation are distinct facts."""
    selected = alignment['selected']; hold = alignment['hold']
    require(current.get('coherent_unit') is True and current['timer'] == selected['timer']
            and current['timer']['SubState'] == 'waiting', 'v3_held_publisher_timer_boundary')
    require(canonical_publisher_comparison(current['row']) == canonical_publisher_comparison(selected['row'])
            and current['unit_sources'] == alignment['unit_sources']
            and encode(current['selected_journal']) == encode(selected['journal']), 'v3_held_publication_preserved')
    unit, previous = current['unit'], selected['unit']
    boundary = ('LoadState', 'FragmentPath', 'DropInPaths', 'NeedDaemonReload')
    require(all(unit[name] == previous[name] for name in boundary)
            and unit['LoadState'] == 'loaded' and unit['FragmentPath'] == '/etc/systemd/system/' + PUBLISHER
            and unit['DropInPaths'] == '' and unit['NeedDaemonReload'] == 'no'
            and unit['MainPID'] == '0' and unit['ActiveState'] in ('inactive', 'failed'),
            'v3_held_publisher_loaded_boundary')
    if unit['InvocationID'] == previous['InvocationID']:
        require(unit == previous and encode(current['journal']) == encode(selected['journal']),
                'v3_held_genuine_invocation_drift')
        return {'latest_kind': 'selected_genuine_publication', 'latest_observation': current,
                'intermediate_invocation_exit_history': 'not_assessed'}
    require(re.fullmatch('[a-f0-9]{32}', unit['InvocationID'])
            and unit['ActiveState'] == 'inactive' and unit['SubState'] == 'dead'
            and unit['Result'] == 'success' and unit['ExecMainStatus'] == '0',
            'v3_held_deferred_invocation_result')
    monotonic = current['unit_monotonic']
    require(set(monotonic) == {'ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic'}
            and all(isinstance(value, str) and value.isdigit() for value in monotonic.values()),
            'v3_held_deferred_monotonic_population')
    begin, end = [int(monotonic[name]) / 1000000 for name in
                  ('ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic')]
    require(type(hold['acquired_monotonic']) in (int, float) and math.isfinite(hold['acquired_monotonic'])
            and 0 < hold['acquired_monotonic'] <= begin <= end <= now < hold['deadline_monotonic'],
            'v3_held_deferred_inside_parent_hold')
    messages = [message for invocation, message in current['journal'] if invocation == unit['InvocationID']]
    require(messages == [DEFERRAL_STDOUT], 'v3_held_deferred_exact_stdout')
    return {'latest_kind': 'completed_deferred_tick', 'latest_observation': current,
            'no_new_publication': True, 'backup_health_claimed_by_deferral': False,
            'intermediate_invocation_exit_history': 'not_assessed'}


def captured_publisher_factory(verifier, conn, original, policy):
    """Capture actual native inputs/callback, with no substitute current observation."""
    captured = []
    def capture(*args, **kwargs):
        captured.append((args, kwargs))
    function = verifier.publisher_source_admission
    namespace = {**function.__globals__, 'adjudicate_publisher': capture}
    private = types.FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
    private(conn, original, policy)
    require(len(captured) == 1 and len(captured[0][0]) == 4
            and set(captured[0][1]) == {'alerts', 'backup', 'offsite', 'judge', 'publisher_path',
                                     'expected_source_pins', 'recheck'}, 'v3_publisher_native_factory_population')
    return captured[0]


def declaration_contract(raw):
    match = re.findall(rb'<!-- owner-acceptance-v3-contract -->\s*```json\s*(.*?)```', raw, re.S)
    require(len(match) == 1, 'v3_single_contract_required')
    result = json.loads(match[0])
    require(result.get('format') == 3 and result.get('origin') == ORIGIN
            and result.get('approved_source_paths') == sorted(ALLOWED)
            and result.get('source_base') == M6 and result.get('dependency_sha256') == DEPENDENCIES,
            'v3_exact_declaration_scope')
    require(result.get('maximum_generations') == 5 and result.get('maximum_transcriptions') == 1
            and result.get('maximum_provider_exposure') == '0.70'
            and result.get('concurrency') == 1 and result.get('provider_retries') == 0
            and result.get('authentication_seconds') == 180 and result.get('browser_verifier_seconds') == 1200,
            'v3_exact_declared_bounds')
    require('operations_revision' in result and result['operations_revision'] is None
            and result.get('operations_revision_policy') == OPERATIONS_REVISION_POLICY,
            'v3_exact_operations_revision_derivation_policy')
    return result


def source_literal(raw, name, expected):
    assignments = [node.value for node in ast.parse(raw).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    require(len(assignments) == 1 and isinstance(assignments[0], ast.Constant)
            and type(assignments[0].value) is type(expected) and assignments[0].value == expected,
            'v3_normal_descendant_exact_source_literal')


def merged_main_admission(host, contract, operations, served):
    """Allow only the cited prospective normal-origin release atop these exact operations."""
    target = full_revision(host.git(ROOT, 'rev-parse', 'origin/main').strip().decode())
    if target == operations:
        return {'revision': target, 'kind': 'exact_acceptance_operations'}
    host.git(ROOT, 'merge-base', '--is-ancestor', operations, target)
    changes = set(host.git(ROOT, 'diff', '--name-only', operations, target).decode().splitlines())
    require(changes == NORMAL_ALLOWED, 'v3_normal_descendant_exact_eight_path_scope')
    raw = host.git(ROOT, 'show', target + ':' + NORMAL_DECL)
    matches = re.findall(rb'<!-- owner-normal443-contract -->\s*```json\s*(.*?)```', raw, re.S)
    require(len(matches) == 1, 'v3_normal_descendant_single_contract')
    policy = json.loads(matches[0])
    availability_sha = contract.get('availability_receipt_sha256')
    require(re.fullmatch('[a-f0-9]{64}', availability_sha or '')
            and policy.get('format') == 1 and policy.get('source_base') == operations
            and policy.get('private_accepted_revision') == served
            and policy.get('approved_source_paths') == sorted(NORMAL_ALLOWED)
            and policy.get('availability') == {'path': str(AVAILABILITY / 'complete.json'), 'sha256': availability_sha}
            and policy.get('origin') == 'https://app.quillmd.com' and policy.get('private_origin') == ORIGIN
            and policy.get('ingress_path') == '/etc/nginx/sites-available/quillmd'
            and policy.get('original_ingress_sha256') == 'ff7320480fe823cbc1564e3c104ee41bac1dd5e1336f8772274af36a541a7a0a'
            and policy.get('private_ingress_sha256') == 'cbc81159b1505fd566625062517bb18dd8d4706cd30b0e334e7fdceec659f21a'
            and policy.get('caddy_sha256') == 'bf0c14729a4ae86ecf2e8ff34d9b5e68aeba55a0bb0c06879580bc73e3a23c87'
            and policy.get('runtime_receipt_binding_protocol') == NORMAL_RUNTIME_BINDING
            and policy.get('private_acceptance_completed') is False
            and all(policy.get(name) is True for name in ('active_protocol_qualified',
                'private_acceptance_protocol_qualified', 'ingress_publication_qualified'))
            and policy.get('authentication_submissions') == policy.get('provider_calls') == policy.get('database_writes') == 0
            and policy.get('automatic_retries') is False and policy.get('outer_ceiling_seconds') == 2400
            and policy.get('session_forward_reserve_seconds') == 600
            and policy.get('session_completion_reserve_seconds') == 60,
            'v3_normal_descendant_exact_prospective_contract')
    for name, path in (('private_acceptance', CAMPAIGN / 'complete.json'), ('private_report', REPORT),
                       ('private_authority', PREPARATION / 'parent-phase-verify.json')):
        require(policy.get(name) == {'path': str(path), 'binding': NORMAL_RUNTIME_BINDING},
                'v3_normal_descendant_fixed_runtime_inputs')
    source = host.git(ROOT, 'show', target + ':' + NORMAL_SELF)
    source_literal(source, 'BASE', operations)
    source_literal(source, 'RUNTIME_BINDING', NORMAL_RUNTIME_BINDING)
    for name in ('ACTIVE_PROTOCOL_QUALIFIED', 'PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED', 'INGRESS_PUBLICATION_QUALIFIED'):
        source_literal(source, name, True)
    preview = host.git(ROOT, 'show', target + ':rebuild/core/preview_access.py')
    source_literal(preview, 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED', True)
    setting = [node.value for node in ast.parse(host.git(ROOT, 'show', target + ':rebuild/quillmd/settings.py')).body
               if isinstance(node, ast.Assign) and any(isinstance(item, ast.Name)
                   and item.id == 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED' for item in node.targets)]
    expected = ast.parse("os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', '0') == '1'", mode='eval').body
    require(len(setting) == 1 and ast.dump(setting[0], include_attributes=False)
            == ast.dump(expected, include_attributes=False), 'v3_normal_descendant_default_disabled_application')
    commit = full_revision(host.git(ROOT, 'log', '-1', '--format=%H', target, '--', NORMAL_DECL).strip().decode())
    require(host.git(ROOT, 'show', commit + ':' + NORMAL_DECL) == raw,
            'v3_normal_descendant_committed_declaration')
    # The exact eight-path diff already excludes every used acceptance source;
    # compare them explicitly so this dependency boundary remains executable.
    for relative in USED_SOURCE:
        require(host.git(ROOT, 'show', target + ':' + relative)
                == host.git(host.source, 'show', operations + ':' + relative),
                'v3_normal_descendant_unchanged_used_acceptance_source')
    host.citation(target)
    return {'revision': target, 'kind': 'reviewed_normal_descendant', 'source_base': operations,
            'served_revision': served, 'availability_receipt_sha256': availability_sha,
            'changed_paths': sorted(changes), 'normal_declaration_commit': commit,
            'normal_declaration_sha256': sha(raw), 'runtime_receipt_binding_protocol': NORMAL_RUNTIME_BINDING,
            'private_acceptance_completed_claimed': False, 'citation_verified': True}


def source_gate(host, contract, operations, served, environment):
    """Two independently cited identities; operational code is not served code."""
    full_revision(operations); full_revision(served)
    source = host.source
    require(source.is_relative_to(ROOT / '.worktrees') and host.canonical(source) == source,
            'v3_canonical_operations_worktree')
    derived_operations = full_revision(host.git(source, 'rev-parse', 'HEAD').strip().decode())
    require(operations == derived_operations, 'v3_caller_operations_revision_matches_derived_head')
    operations = derived_operations
    require(not host.git(source, 'status', '--porcelain', '--untracked-files=no').strip(),
            'v3_clean_operations_revision')
    main_proof = merged_main_admission(host, contract, operations, served)
    host.git(source, 'merge-base', '--is-ancestor', M6, operations)
    changes = set(host.git(source, 'diff', '--name-only', M6, operations).decode().splitlines())
    require(changes == ALLOWED, 'v3_operations_four_path_scope')
    require(environment.get('RULED_MUTATION_DECLARATION') == DECL, 'v3_normal_ruled_door')
    commit = full_revision(environment.get('RULED_MUTATION_DECL_COMMIT'))
    declaration = host.read_source(source / DECL)
    require(host.git(source, 'log', '-1', '--format=%H', '--', DECL).strip().decode() == commit
            and host.git(source, 'show', commit + ':' + DECL) == declaration
            and declaration_contract(declaration) == contract, 'v3_committed_declaration_identity')
    require(contract.get('served_revision') == served, 'v3_separate_declared_served_revision')
    for revision in dict.fromkeys((M6, operations, served)):
        host.citation(revision)
    require(host.git(ROOT, 'branch', '--show-current').strip() == b'main'
            and host.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == served
            and not host.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'v3_clean_served_revision')
    tracked = host.git(ROOT, 'ls-files', 'rebuild').decode().splitlines()
    for relative in tracked:
        require(host.read_source(ROOT / relative) == host.git(ROOT, 'show', served + ':' + relative),
                'v3_served_tracked_byte_identity')
        host.readability(ROOT / relative)
    for relative in USED_SOURCE:
        require(host.read_source(source / relative) == host.git(source, 'show', operations + ':' + relative),
                'v3_operations_tracked_byte_identity')
        host.readability(source / relative)
    require(host.git(ROOT, 'rev-parse', 'origin/main').strip().decode() == main_proof['revision'],
            'v3_merged_main_unchanged_during_source_admission')
    return {'operations_revision': derived_operations, 'served_revision': served,
            'operations_revision_policy': OPERATIONS_REVISION_POLICY,
            'operations_source': str(source), 'changed_paths': sorted(changes), 'citation_verified': True,
            'merged_main': main_proof}


def exact_cgroup(raw, unit):
    require(raw == '0::/system.slice/' + unit + '\n', 'v3_exact_native_cgroup')


def live_identity(availability, current, served):
    """Source/configuration/startup proof, never a returned provider-model claim."""
    require(set(current['units']) == set(UNITS), 'v3_three_live_units')
    measured = availability.get('completion_unit_provenance')
    require(isinstance(measured, dict) and set(measured) == set(UNITS), 'v3_measured_availability_invocations_required')
    legacy_fields = {'ActiveState', 'SubState', 'MainPID', 'FragmentPath', 'DropInPaths',
                     'UnitFileState', 'ExecMainStartTimestampMonotonic'}
    for unit in UNITS:
        before = measured[unit]; after = current['units'][unit]
        require(set(before) == legacy_fields | {'InvocationID', 'NeedDaemonReload'}
                and {key: before[key] for key in legacy_fields} == availability['units_after'][unit]
                and re.fullmatch('[a-f0-9]{32}', before.get('InvocationID', ''))
                and before.get('NeedDaemonReload') == 'no', 'v3_exact_measured_availability_invocations')
        keys = ('MainPID', 'InvocationID', 'ExecMainStartTimestampMonotonic')
        require(all(after.get(key) == before.get(key) for key in keys)
                and after.get('ActiveState') == 'active' and after.get('SubState') == 'running'
                and after.get('NeedDaemonReload') == 'no' and after.get('DropInPaths') == ''
                and after.get('UnitFileState') == before['UnitFileState'] == 'enabled'
                and after.get('FragmentPath') == before['FragmentPath'] == '/etc/systemd/system/' + unit
                and after.get('release') == served, 'v3_same_live_service_source_start')
        exact_cgroup(current['cgroups'][unit], unit)
        require(int(after['MainPID']) > 0 and current['kernel_start_ticks'][unit] > 0,
                'v3_live_kernel_identity')
    original = availability['worker_configuration_provenance']
    proof = current['worker_configuration_provenance']
    require(proof == original and proof['values']['QUILLMD_RELEASE_SHA'] == served
            and proof['values']['QUILLMD_AI_MODEL'] == MODEL
            and proof.get('actual_provider_model_verified') is False, 'v3_unchanged_worker_configuration')
    require(current['pending_jobs'] == current['held'] == current['unresolved_reaper_paths'] == 0
            and current['old_job_receipt_usage_unchanged'] is True, 'v3_idle_worker_all_reaper_paths')
    require(current['private_origin'] == ORIGIN and current['public_status'] == 503
            and current['ingress_sha256'] == current['expected_ingress_sha256'], 'v3_private_ingress_public_maintenance')
    return {'worker_running_idle': True, 'actual_provider_model_verified': False,
            'same_pid_start_source_and_configuration': True}


def current_external_boundary(recovery, acknowledgement):
    """Observe the separately authorized exact current boundary; change no foreign state."""
    execution_gate()
    require(isinstance(POST_RESTORE_OWNER_REPLY_SHA, str)
            and re.fullmatch('[a-f0-9]{64}', POST_RESTORE_OWNER_REPLY_SHA),
            'v3_current_configuration_owner_reply_required')
    proposal_raw = protected(POST_RESTORE_PROPOSAL)
    require(sha(proposal_raw) == POST_RESTORE_PROPOSAL_SHA, 'v3_current_configuration_proposal_hash')
    proposal = json.loads(proposal_raw)
    same = configuration_helpers({'need': require})['configuration_same']
    require(all(same(proposal.get(key), value) for key, value in POST_RESTORE_PINS.items()),
            'v3_current_configuration_proposal_binding')
    reply_raw = protected(POST_RESTORE_OWNER_REPLY, 65536)
    require(sha(reply_raw) == POST_RESTORE_OWNER_REPLY_SHA, 'v3_current_configuration_owner_reply_hash')
    reply = json.loads(reply_raw)
    require(type(reply.get('format')) is int and reply['format'] == 1
            and reply.get('decision') == 'authorize_exact_post_restoration_preservation_boundary'
            and reply.get('proposal_sha256') == POST_RESTORE_PROPOSAL_SHA
            and isinstance(reply.get('owner_reply'), str) and reply['owner_reply'].strip()
            and reply.get('historical_deployment_authorization_verified') is False
            and reply.get('voiceassistmain_changes_authorized') is False,
            'v3_current_configuration_owner_reply_scope')
    # Authenticate the earlier seven-path decision as history, without asking its
    # native reader to pretend the earlier product invocation is still current.
    export, boundary = recovery.owner_boundary_inputs(acknowledgement)
    recovery.acknowledge_current_owner_configuration(boundary['before'], boundary['after'], acknowledgement)
    native = recovery.native_boundary_identity()
    require(native == export['native_host_proof'], 'v3_current_configuration_native_host')
    product = POST_RESTORE_PINS['product_loaded_state']
    product_name = recovery.EXTERNAL_UNIT.rsplit('/', 1)[1]
    require(recovery.owner_unit_state(product_name, tuple(product)) == product,
            'v3_current_configuration_product_state')
    sources = recovery.source_files
    receipt_path = '/var/lib/voiceassistmain-product-installation/8c13fe1a-5bda-4bdf-bc73-4b5cac49b1f4.json'
    public_records = POST_RESTORE_PINS['current_public_records']
    required_paths = {item['path'] for item in POST_RESTORE_PINS['configuration_differences']} | {
        '/etc/voiceassistmain-product.json', receipt_path}
    require(len(public_records) == 6 and {item['path'] for item in public_records} == required_paths,
            'v3_current_configuration_public_path_scope')
    parsed = {}
    with sources.open_root(Path('/')) as root_fd:
        for item in public_records:
            path = item['path']; fd = sources.open_relative(root_fd, path[1:])
            try:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
                        and stat.S_IMODE(before.st_mode) == 0o644 and before.st_nlink == 1
                        and not os.listxattr(fd) and recovery.full_native_metadata(before) == item['metadata'],
                        'v3_current_configuration_public_metadata')
                raw = sources.bytes_at(fd, 2 * 1024 * 1024)
                require(sha(raw) == item['sha256'], 'v3_current_configuration_public_bytes')
                reopened = sources.open_relative(root_fd, path[1:])
                try:
                    require(sources.stable(before) == sources.stable(os.fstat(fd))
                            == sources.stable(os.fstat(reopened)), 'v3_current_configuration_public_race')
                finally:
                    os.close(reopened)
                if path == recovery.EXTERNAL_UNIT:
                    require([line for line in raw.splitlines() if line.strip().startswith(b'WorkingDirectory=')]
                            == [b'WorkingDirectory=' + product['WorkingDirectory'].encode()],
                            'v3_current_configuration_working_directory')
                if path.endswith('.json'):
                    parsed[path] = json.loads(raw)
            finally:
                os.close(fd)
        additional = export['additional_configuration_evidence']
        for item in additional['exact_added_files']:
            recovery.owner_public_record(root_fd, item['path'], item['sha256'], item['metadata'])
        for item in additional['exact_added_enablement_links']:
            path = Path(item['path']); parent = sources.open_relative(root_fd, str(path.parent)[1:], directory=True)
            try:
                before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                require(stat.S_ISLNK(before.st_mode) and before.st_uid == before.st_gid == 0 and before.st_nlink == 1
                        and recovery.full_native_metadata(before) == item['metadata']
                        and os.readlink(path.name, dir_fd=parent) == recovery.CURRENT_OWNER_PINS['added_links'][str(path)],
                        'v3_current_configuration_enablement_link')
                require(sources.stable(before) == sources.stable(os.stat(path.name, dir_fd=parent, follow_symlinks=False)),
                        'v3_current_configuration_enablement_race')
            finally:
                os.close(parent)
    manifest = parsed['/etc/voiceassistmain-product.json']
    receipt = parsed[receipt_path]
    manifest_sha = next(item['sha256'] for item in public_records if item['path'] == '/etc/voiceassistmain-product.json')
    require(manifest['installation_id'] == receipt['installation_id'] == '8c13fe1a-5bda-4bdf-bc73-4b5cac49b1f4'
            and manifest['source_sha256'] == receipt['source_sha256']
                == 'ee71e3c32364ca06a3a25c60f7ac45861dc1942db36565b6875be8a7e008aa26'
            and manifest['release_root'] == receipt['release_root'] == product['WorkingDirectory']
            and receipt['manifest_sha256'] == manifest_sha
            and type(receipt['main_pid']) is int and receipt['main_pid'] == int(product['MainPID'])
            and receipt['installed'] is True and type(receipt['calls_started']) is int and receipt['calls_started'] == 0
            and type(receipt['provider_writes']) is int and receipt['provider_writes'] == 0
            and receipt['nginx_changed'] is False, 'v3_current_configuration_installation_binding')
    stable_units = {}
    for expected in additional['loaded_states']:
        name = expected['Id']; stable = {key: value for key, value in expected.items() if key not in ('ActiveState', 'SubState')}
        for _ in range(2):
            actual = recovery.owner_unit_state(name, tuple(expected))
            require({key: actual[key] for key in stable} == stable
                    and actual['ActiveState'] in ('active', 'inactive', 'activating', 'deactivating', 'failed',
                                                  'reloading', 'maintenance')
                    and actual['SubState'] in ('dead', 'running', 'waiting', 'elapsed', 'exited', 'failed', 'start',
                        'start-pre', 'start-post', 'stop', 'stop-sigterm', 'stop-sigkill', 'stop-post',
                        'final-sigterm', 'final-sigkill', 'auto-restart', 'cleaning', 'reload'),
                    'v3_current_configuration_other_unit_configuration')
        stable_units[name] = stable
    require(recovery.owner_unit_state(product_name, tuple(product)) == product
            and recovery.native_boundary_identity() == native, 'v3_current_configuration_native_final_race')
    proof = {'format': 1, 'protocol': 'post-restoration-exact-owner-preservation-v1',
             'proposal_sha256': POST_RESTORE_PROPOSAL_SHA, 'owner_reply_sha256': POST_RESTORE_OWNER_REPLY_SHA,
             'availability_receipt_sha256': POST_RESTORE_PINS['availability_receipt_sha256'],
             'configuration_differences': copy.deepcopy(POST_RESTORE_PINS['configuration_differences']),
             'product_loaded_state': copy.deepcopy(product), 'historical_deployment_authorization_verified': False,
             'current_owner_preservation_authorized': True, 'original_baseline_replaced': False,
             'voiceassistmain_changes_authorized': False}
    return {'configuration_admission': proof, 'native_host_proof': native,
            'additional_unit_configuration': stable_units}


def preserved_snapshot(expected, current, database, configuration_proof=None):
    require(current['database'] == database, 'v3_database_snapshot_race')
    for label in ('mail', 'static'):
        require(expected[label] == current[label], 'v3_preserved_' + label)
    helpers = configuration_helpers({'need': require})
    if not helpers['configuration_same'](expected['configuration'], current['configuration']):
        helpers['current_configuration_proof'](
            expected['configuration'], current['configuration'], configuration_proof)
    require(all(current['files'].get(name) == value for name, value in expected['files'].items()),
            'v3_preserved_old_files')
    return True


def authenticated_rows_admission(verifier, old, current, keys, policy, secret, fingerprint, auth, publisher, edge_ip=None):
    """Use the qualified COPY algorithm, with explicit route input instead of I/O.

    The one replaced AST statement is its TCP route observation. The caller
    supplies a route address observed by the qualified native collector under
    the same hold. This helper itself has no socket or installed-state access.
    """
    require(isinstance(getattr(verifier, '__authenticated_source', None), bytes), 'v3_authenticated_copy_source_required')
    definitions = [node for node in ast.parse(verifier.__authenticated_source).body
                   if isinstance(node, ast.FunctionDef) and node.name == 'continuation_rows_admission']
    require(len(definitions) == 1, 'v3_exact_pure_copy_function')
    function = definitions[0]
    raw = ast.Module(body=[function], type_ignores=[])
    replacements = 0
    for node in ast.walk(function):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == 'auth':
            for index, statement in enumerate(node.body):
                if isinstance(statement, ast.With) and any(isinstance(child, ast.Attribute)
                        and child.attr == 'create_connection' for child in ast.walk(statement)):
                    node.body[index] = ast.parse('edge_ip = supplied_edge_ip').body[0]
                    replacements += 1
    require(replacements == 1, 'v3_exact_pure_auth_route_adapter')
    if auth is not None:
        try:
            require(str(ipaddress.ip_address(edge_ip)) == edge_ip, 'v3_canonical_native_edge_address')
        except (ValueError, TypeError):
            raise Refusal('v3_canonical_native_edge_address') from None
    namespace = dict(verifier.__dict__, supplied_edge_ip=edge_ip)
    exec(compile(ast.fix_missing_locations(raw), '<qualified-v3-pure-copy-adapter>', 'exec'), namespace)
    return namespace['continuation_rows_admission'](old, current, keys, policy, secret, fingerprint, auth, publisher)


def authenticated_admin(verifier, packet, original, operations, served, availability_sha):
    """No password/MFA seed/session recovery; authenticate supplied normal evidence."""
    raw = packet['normal_raw']; admin = json.loads(raw); session_raw = packet['session_raw']
    require(admin.get('format') == 1 and admin.get('complete') is True and admin.get('availability_first') is True
            and admin.get('operations_revision') == operations and admin.get('served_revision') == served
            and admin.get('release') == served and admin.get('origin') == ORIGIN
            and admin.get('normal_mfa_login') is True and admin.get('auth_reset') is False
            and admin.get('csrf403_no_OTP_noauththrottle') is True
            and admin.get('availability_receipt_sha256') == availability_sha
            and admin.get('session_cookie_name') == 'quillmd_doctor_session'
            and admin.get('session_file') == str(ADMIN / 'browser-session.json')
            and admin.get('session_sha256') == sha(session_raw), 'v3_normal_admin_evidence')
    cookies = json.loads(session_raw)['cookies']
    expected = {'__Host-quillmd_preview': 'Lax', 'quillmd_doctor_session': 'Strict', 'quillmd_doctor_csrf': 'Strict'}
    require(len(cookies) == 3 and {row['name'] for row in cookies} == set(expected), 'v3_exact_auth_cookie_population')
    for row in cookies:
        require(row['secure'] is True and row['httpOnly'] is True and row['sameSite'] == expected[row['name']]
                and row['domain'] == 'app.quillmd.com' and row['path'] == '/' and row['value'], 'v3_auth_served_chain_cookie')
    cookie_proof = admin.get('cookie_contract', {})
    require(cookie_proof.get('installed_ingress_identity_verified') is True
            and cookie_proof.get('HTTPS_ingress_CSRF_httpOnly') is True
            and cookie_proof.get('source_sha256', {}).get('rebuild/deploy/email-private-https.conf')
                == 'cbc81159b1505fd566625062517bb18dd8d4706cd30b0e334e7fdceec659f21a', 'v3_actual_cookie_ingress_source')
    before_raw, invalid_raw, after_raw = (packet[name] for name in ('before_raw', 'invalid_raw', 'after_raw'))
    require([sha(value) for value in (before_raw, invalid_raw, after_raw)] == [admin['authentication_metadata'][name]
            for name in ('before_sha256', 'invalid_csrf_sha256', 'normal_mfa_sha256')], 'v3_auth_metadata_hashes')
    before, invalid, after = map(json.loads, (before_raw, invalid_raw, after_raw))
    require(before == invalid, 'v3_invalid_csrf_changed_authentication')
    verifier.same_auth_metadata(original, before)
    permitted = {'last_t', 'last_used_at', 'throttling_failure_count', 'throttling_failure_timestamp'}
    stable_actor = lambda value: {key: item for key, item in value.items() if key != 'last_login'}
    require(stable_actor(before['actor']) == stable_actor(after['actor'])
            and {key: value for key, value in before['device'].items() if key not in permitted}
                == {key: value for key, value in after['device'].items() if key not in permitted}
            and after['device']['last_t'] > before['device']['last_t']
            and after['device']['throttling_failure_count'] == 0
            and after['device']['throttling_failure_timestamp'] is None, 'v3_one_existing_device_mfa')
    fresh = [row for row in after['auth_audits'] if row not in before['auth_audits']]
    require(fresh == [admin['normal_login_audit']] and fresh[0]['action'] == 'auth.login'
            and fresh[0]['actor_id'] == admin['actor_id'], 'v3_one_normal_login_audit')
    begin, end = stamp(admin['started']), stamp(admin['finished_at'])
    login = stamp(fresh[0]['created_at'])
    require(begin <= stamp(admin['authenticated_at']) <= end and 0 <= (end - begin).total_seconds() <= 180
            and begin <= login <= end and begin <= stamp(after['actor']['last_login']) <= end
            and abs((stamp(after['actor']['last_login']) - login).total_seconds()) < 2
            and begin <= stamp(after['device']['last_used_at']) <= end, 'v3_measured_normal_mfa_interval')
    return {'admin': admin, 'before': before, 'after': after,
            'cookies': {row['value']: row['name'] for row in cookies if row['name'] != 'quillmd_doctor_csrf'},
            'cookie': next(row['value'] for row in cookies if row['name'] == 'quillmd_doctor_session'),
            'interval': (begin, end), 'evidence_sha256': sha(raw), 'session_sha256': sha(session_raw)}


def generation_admission(verifier, packet, expected):
    job, metadata, receipt, usage = (packet[name] for name in ('job', 'metadata', 'receipt', 'usage'))
    config = job['config']
    require(job['kind'] == 'generation' and job['state'] == 'succeeded' and packet['attempt_count'] == 1
            and job['id'] == expected['job_id'] and job['encounter_id'] == expected['encounter']
            and job['user_id'] == expected['actor'] and config.get('provider') == 'anthropic'
            and config.get('model') == MODEL and config.get('pricing_version') == PRICING,
            'v3_actual_immutable_generation_job')
    require(str(metadata['id']) == str(receipt['job_id']) == str(usage['job_id']) == job['id']
            and str(metadata['encounter_id']) == job['encounter_id']
            and str(metadata['user_id']) == job['user_id'] and metadata['config'] == config
            and metadata['result_sha256'] == job['result_sha256'], 'v3_generation_packet_database_row_binding')
    require(config == packet['signed_quote_configuration'] and config.get('mode') == 'live'
            and all(config.get(key) == value for key, value in
                    {'input_rate': '2', 'output_rate': '10', 'cached_rate': '0.20',
                     'voice_rate_minute': '0.0043', 'discount_rate': '0'}.items()), 'v3_immutable_signed_quote_profile')
    content = packet['content']
    require(sha(content['notes'].encode()) == expected['notes_sha256']
            and metadata['form_sha256'] == expected['sha256']
            and str(metadata['template_version_id']) == expected['mapping_id']
            and metadata['mapping_version'] == 1 and str(metadata['department_id']) == expected['department_id']
            and str(metadata['patient_id']) == expected['patient_id']
            and str(metadata['template_id']) == expected['template_id'], 'v3_immutable_source_scope_binding')
    require(metadata['fields'] == expected['fields'] and content['status'] == 'finalized'
            and str(content['finalized_by_id']) == expected['actor'], 'v3_actual_finalized_document_actor_fields')
    require(packet['served_client_profile'] == PROFILE and packet['served_source_revision'] == expected['served_revision'],
            'v3_exact_served_client_profile')
    require(sha(packet['provider_raw']) == job['result_sha256'], 'v3_raw_provider_result_hash')
    message = json.loads(packet['provider_raw'])['provider_output']
    cost = verifier.check_generation_financial(message, metadata, receipt, usage, packet['ledger'], packet['holds'])
    selected = json.loads(''.join(block['text'] for block in message['content'] if block['type'] == 'text'))['fields']
    require(selected == packet['selections'], 'v3_actual_raw_selections')
    first = verifier.validate_first_quotes(expected, selected)
    values = {field['label']: first[field['key']]['text'] for field in expected['fields']}
    actual_values = {field['label']: content['answers'][field['key']]['text'] for field in expected['fields']}
    require(values == expected['expected'] and packet['accepted_values'] == actual_values == expected['expected']
            and all(content['answers'][field['key']]['reviewed'] is True
                    and content['answers'][field['key']]['reviewed_by'] == expected['actor']
                    and content['answers'][field['key']]['status'] == ('left_blank' if expected['expected'][field['label']] == '' else 'supported')
                    for field in expected['fields']),
            'v3_first_complete_answers_and_accepted_values')
    if expected['name'] == 'allergy-missing':
        missing = content['answers']['cell_3']; decision = missing.get('blank_decision', {})
        require(expected['expected']['Allergies'] == '' and decision.get('by') == expected['actor']
                and decision.get('from_status') == 'missing' and missing.get('blank_history')
                and missing['blank_history'][0]['decision'] == 'left_blank'
                and any('cell_3' in row['details'].get('left_blank', []) for row in packet['answer_save_audits']),
                'v3_explicit_missing_allergy_blank_decision_audit')
    require(sha(packet['original_docx']) == expected['sha256']
            and sha(packet['exported_docx']) == metadata['export_sha256'], 'v3_original_and_export_hashes')
    export = verifier.verify_export(packet['original_docx'], packet['exported_docx'], expected['expected'])
    require(packet['normal_review_decisions_recorded'] is True and packet['empty_finalize_refused'] is True
            and packet['premature_export_refused'] is True, 'v3_normal_review_before_finalize_export')
    return {'case': expected['name'], 'job_id': job['id'], 'encounter': job['encounter_id'],
            'requested_model_from_immutable_job': MODEL, 'returned_model': message['model'],
            'provider_request_id': metadata['provider_request_id'], 'message_id': message['id'],
            'actual_cost': str(cost), 'charged_cost': str(usage['charged_cost']),
            'raw_provider_result_sha256': sha(packet['provider_raw']), 'structural_export': export,
            'raw_provider_selections_distinct_from_accepted_export': True, 'on_wire_capture_available': False}


def speech_admission(verifier, packet, expected):
    job = packet['job']; config = job['config']
    require(job['kind'] == 'transcription' and job['state'] == 'succeeded' and packet['attempt_count'] == 1
            and job['id'] == expected['job_id'] and job['encounter_id'] == expected['encounter']
            and job['user_id'] == expected['actor'] and config.get('transcript_review_required') is True
            and config.get('provider') == 'deepgram' and config.get('model') == 'nova-3-medical'
            and packet['timeout_seconds'] == 90 and packet['max_retries'] == 0, 'v3_actual_speech_job_profile')
    require(str(packet['receipt']['job_id']) == str(packet['usage']['job_id']) == job['id'], 'v3_speech_packet_database_row_binding')
    require(sha(packet['audio']) == '8bb6b53f2832ae830fc422e6fac366a383226fcb911e59a814466cb90809b8d7'
            and sha(packet['provider_raw']) == job['result_sha256'], 'v3_frozen_synthetic_audio_result')
    cost = verifier.check_speech_financial(job, packet['receipt'], packet['usage'], packet['ledger'], packet['holds'])
    result = json.loads(packet['provider_raw']); audit = packet['applied_audit']
    require(audit['actor_id'] == expected['actor'] and audit['department_id'] == expected['department_id']
            and audit['target'] == job['id'] and audit['action'] == 'transcription.applied'
            and audit['details']['raw_sha256'] == sha(result['raw_transcript'].encode())
            and audit['details']['corrected_sha256'] == expected['notes_sha256']
            and sha(packet['reviewed_notes'].encode()) == expected['notes_sha256'], 'v3_explicit_transcript_review_audit')
    return {'job_id': job['id'], 'actual_cost': str(cost), 'explicit_review_verified': True,
            'hardware_microphone_verified': False, 'on_wire_capture_available': False}


def old_and_added_rows_admission(verifier, original, current, keys, manifest, after_auth, context):
    """Preserve the original authenticated population, then narrow browser deltas.

    The prior normal-MFA transitions are authenticated against ORIGINAL bytes;
    they never substitute a fresh dump for the preserved capture. Every table,
    primary key and column is compared. Current health stays byte-exact after
    the previously source-adjudicated publication while the same hold remains.
    """
    require(set(original) == set(current) == set(keys), 'v3_complete_table_population')
    transitions = {(row['table'], row['primary_key_sha256']): row
                   for row in after_auth['allowed_deltas']['original_row_transitions']}
    admitted_added = {(row['table'], row['primary_key_sha256']): row
                      for row in after_auth['allowed_deltas']['added_rows']}
    require(len(transitions) == len(after_auth['allowed_deltas']['original_row_transitions'])
            and len(admitted_added) == len(after_auth['allowed_deltas']['added_rows']), 'v3_unique_admitted_lifecycle_rows')
    auth = context['authentication']; auth['publisher'] = after_auth['allowed_deltas']['publisher']
    auth['allowed_login_keys'] = context['allowed_login_keys']
    seen_added = set(); counts = {}; exceptions = []
    for table, data in original.items():
        columns = data['columns']
        require(current[table]['columns'] == columns, 'v3_exact_original_column_order')
        before = verifier.row_mapping(table, data['rows'], columns, keys[table])
        after = verifier.row_mapping(table, current[table]['rows'], columns, keys[table])
        key_sort = lambda raw: tuple(int(cell) if cell.isdigit() else cell for cell in raw)
        ordered = b''.join(b'\t'.join(before[key][name] for name in columns) + b'\n' for key in sorted(before, key=key_sort))
        require(sha(ordered) == manifest['tables'][table]['sha256']
                and len(before) == manifest['tables'][table]['rows'] and before.keys() <= after.keys(),
                'v3_authenticated_original_rows_undeleted')
        for primary, row in before.items():
            digest = sha(encode([cell.decode() for cell in primary]))
            transition = transitions.get((table, digest))
            if transition is not None:
                row = verifier.admitted_original_row(row, columns, transition, table, auth['admin']['actor_id'], auth)
            following = after[primary]
            if row == following:
                continue
            if table == 'django_session':
                require(following['session_key'].decode() in context['admin_cookies'], 'v3_only_named_admin_session_renewal')
            result = verifier.check_old_row(table, row, following, actor=context['actor'], login_at=context['login_at'],
                start=context['start'], deltas=context['wallet_deltas'], allowed_login_keys=context['allowed_login_keys'],
                secret=context['secret'], activation=context['activation'], admin_read_interval=context['admin_read_interval'],
                old_preview_key=context['admin_preview_cookie'], preview_fingerprint=context['preview_fingerprint'])
            exceptions.append({'table': table, 'primary_key_sha256': digest, 'columns': result['columns']})
        added = [row for primary, row in after.items() if primary not in before]
        counts[table] = len(added)
        for row in added:
            digest = sha(encode([row[name].decode() for name in keys[table]])); identity = (table, digest)
            if identity in admitted_added:
                verifier.validate_admitted_added_row(row, columns, admitted_added[identity], auth['admin']['actor_id'],
                    context['secret'], context['preview_fingerprint'], context['admin_read_interval'], context['actor'],
                    context['login_at'], context['start'], context['allowed_login_keys'], context['activation'],
                    context['health_policy'])
                seen_added.add(identity)
                continue
            admitted_new_row(verifier, table, row, context)
    require(seen_added == set(admitted_added), 'v3_all_admitted_lifecycle_rows_retained')
    require(counts.get('core_encounter') == 5 and counts.get('core_job') == 6
            and counts.get('core_usage') == counts.get('core_providerreceipt') == 6
            and counts.get('core_template') == counts.get('core_templateversion') == 1
            and counts.get('django_session') == 5 and counts.get('otp_totp_totpdevice') == 0,
            'v3_exact_new_case_auth_population')
    return {'all_original_tables_rows_columns_compared': True, 'original_capture_replaced': False,
            'OTP_unchanged_after_one_declared_MFA': True, 'all_health_fields_strict_after_publication_admission': True,
            'normal_authentication_lifecycle': after_auth['allowed_deltas'],
            'permitted_subsequent_old_row_deltas': exceptions, 'new_row_counts': counts}


def admitted_new_row(verifier, table, row, context):
    ids, jobs = context['encounters'], context['jobs']; form = context['allergy_form']
    if table == 'core_encounter':
        require(row['id'].decode() in ids and row['created_by_id'].decode() == context['actor']
                and row['department_id'].decode() == context['department_id'], 'v3_named_synthetic_encounter')
    elif table == 'core_job':
        require(row['id'].decode() in jobs and row['encounter_id'].decode() in ids
                and row['user_id'].decode() == context['actor'], 'v3_named_synthetic_job')
    elif table in ('core_usage', 'core_providerreceipt', 'core_reservation', 'core_ledgerentry'):
        require(row['job_id'].decode() in jobs, 'v3_named_job_accounting_history')
    elif table == 'core_template':
        require(row['id'].decode() == form['template_id'] and row['sha256'].decode() == form['sha256'], 'v3_one_blank_original_template')
    elif table == 'core_templateversion':
        require(row['id'].decode() == form['mapping_id'] and row['template_id'].decode() == form['template_id']
                and row['number'] == b'1', 'v3_one_version_one_mapping')
    elif table == 'core_auditevent':
        actions = {'auth.login', 'template.upload', 'template.download', 'encounter.create', 'encounter.view',
            'encounter.answers_saved', 'encounter.finalize', 'encounter.export', 'encounter.notes_saved',
            'coding.invalidated_by_source_edit', 'transcription.applied', 'job.result_download', 'provider.receipt',
            'usage.reserve', 'usage.settle', 'billing.job_read', 'job.queued', 'job.succeeded',
            'voice.submission_prepared', 'transcription.review_ready'}
        ordinary = row['actor_id'].decode() == context['actor'] and row['action'].decode() in actions
        preview = row['actor_id'] == b'\\N' and row['action'] == b'preview.login' and row['target'] == b''
        staff = row['actor_id'].decode() == context['authentication']['admin']['actor_id'] and row['action'] in (b'admin.dashboard', b'admin.audit_read')
        require((ordinary or preview or staff) and context['start'] <= verifier.parsed_timestamp(row['created_at']) <= context['finish']
                and (row['target'] == b'' or row['target'].decode() in ids | jobs | {form['template_id'], form['mapping_id']}),
                'v3_named_actor_action_target_audit')
    elif table == 'core_loginattempt':
        require(row['key'].decode() in context['allowed_login_keys'] and row['count'] == b'1', 'v3_named_login_throttle')
    elif table == 'django_session':
        key = row['session_key'].decode()
        require(key in context['doctor_cookies'], 'v3_named_normal_doctor_session')
        value = verifier.normal_session(row['session_data'], context['secret'])
        verifier.validate_new_session(row, value, context['doctor_cookies'][key], context['actor'],
                                      (context['start'], context['finish']), context['preview_fingerprint'])
    else:
        raise Refusal('v3_undeclared_added_table_row')


def file_catalog_admission(original_baseline, current_snapshot, catalog, referenced_files, invariant_counts):
    require(catalog == original_baseline['database']['catalog']
            and invariant_counts == original_baseline['database']['invariants'], 'v3_original_catalog_invariants')
    for label in ('configuration', 'static', 'mail'):
        require(current_snapshot[label] == original_baseline[label], 'v3_final_preserved_' + label)
    before = original_baseline['files']; after = current_snapshot['files']
    require(all(after.get(name) == value for name, value in before.items()), 'v3_final_all_original_file_metadata_bytes')
    require(set(after) == set(before) | set(referenced_files)
            and all(after[name]['sha256'] == digest for name, digest in referenced_files.items()),
            'v3_exact_new_referenced_file_population')
    return {'original_catalog_and_sequences_unchanged': True, 'all_old_file_metadata_bytes_preserved': True,
            'only_authenticated_new_references': True, 'mail_static_configuration_unchanged': True}


def original_policy_admission(common, policy, contract, original_declaration):
    """Existing qualified policy is history, not replacement current expectations."""
    matches = re.findall(rb'<!-- legacy-model-contract -->\s*```json\s*(.*?)```', original_declaration, re.S)
    require(len(matches) == 1, 'v3_original_policy_contract_population')
    historical = json.loads(matches[0])['continuation_contract']
    require(policy == historical == contract.get('original_policy'), 'v3_exact_historical_policy')
    require(len(policy['publisher_admission_policy']['source_sha256']) == 23,
            'v3_full_historical_publisher_source_population')
    return policy


def readonly_connection_flags(conn):
    """No ORM/settings import; fixed backup role and read-only transaction."""
    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    conn.execute("SET LOCAL timezone='UTC'")
    conn.execute("SET LOCAL datestyle='ISO, MDY'")
    conn.execute("SET LOCAL statement_timeout='90s'")
    flags = conn.execute("SELECT current_user,current_database(),current_setting('transaction_read_only') AS read_only").fetchone()
    require(flags['current_user'] == 'quillmd_backup' and flags['current_database'] == 'quillmd_fresh'
            and flags['read_only'] == 'on', 'v3_readonly_target_connection')
    privileges = conn.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=current_user').fetchone()
    require(privileges and not any(privileges.values()), 'v3_nonprivileged_backup_role')


def readonly_copy_admission(conn, verifier, backup, original, baseline, manifest, policy, secret, fingerprint,
                            auth=None, edge_ip=None, publisher_admission=None):
    """Source-faithful admission on an explicitly supplied read-only connection.

    The caller owns all five exclusions. No auth/migrations/writes occur here;
    current health is adjudicated by the unchanged 23-source publisher closure.
    The database connection itself is supplied, not discovered by this helper.
    """
    readonly_connection_flags(conn)
    current, keys, tables = verifier.current_copy_tables(conn, original, backup)
    rows = verifier.row_mapping('core_servicehealth', original['core_servicehealth']['rows'],
                                 original['core_servicehealth']['columns'], keys['core_servicehealth'])
    health = [row for row in rows.values() if row['key'] == b'backup']
    require(len(health) == 1, 'v3_one_original_publisher_row')
    require(callable(publisher_admission), 'v3_checked_publisher_admission_required')
    publisher = publisher_admission(conn, health[0], policy)
    semantics = authenticated_rows_admission(verifier, original, current, keys,
        dict(policy, original_tables=manifest['tables']), secret, fingerprint, auth, publisher, edge_ip)
    database = verifier.continuation_database_fingerprint(conn, tables, baseline, backup)
    conn.rollback()
    return {'complete': True, 'current_database_fingerprint': database, 'allowed_deltas': semantics,
            'original_records_adjudicated': True, 'read_only_role': 'quillmd_backup',
            'provider_calls': 0, 'database_writes': 0}


def installed_database_admission(contract, *, auth_packet=None, operations=None, served=None,
                                 availability_sha=None, verifier_override=None, native_modules=None,
                                 publisher_admission=None):
    """Future fixed collection path; gate precedes key/role/socket/DB access."""
    execution_gate()
    import psycopg
    from psycopg.rows import dict_row
    from django.utils.crypto import salted_hmac
    from dotenv import dotenv_values
    from io import StringIO
    if native_modules is None:
        from ops import legacy_model_activation as legacy
        _, backup, _, _, _ = legacy.modules()
    else:
        legacy, backup = native_modules
    common, verifier, policy = frozen_modules()
    if verifier_override is not None:
        verifier = verifier_override
    original_declaration = subprocess.run(['git', '-C', str(SOURCE), 'show',
        'fa331c8e33ccf4ed82c7b0a6c36283f463092f62:docs/foundation/mutations/20261006-quillmd-legacy-model-demo.md'],
        check=True, capture_output=True, timeout=30).stdout
    original_policy_admission(common, policy, contract, original_declaration)
    capture, baseline, manifest, original = verifier.original_continuation_capture(policy, datetime.now(timezone.utc))
    require(manifest['tables']['django_session']['rows'] == 212
            and capture['backup']['manifest_cipher_sha256'] == common.BACKUP_SHA, 'v3_original_212_capture_identity')
    values = dotenv_values(stream=StringIO(backup.key_at(legacy.KEY).decrypt(
        protected(ORIGINAL / 'environment-before.fernet', 128 * 1024)).decode()), interpolate=False)
    secret = values['QUILLMD_SECRET_KEY']
    fingerprint = salted_hmac('quillmd-preview-v1', values['QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME'] + '\0'
                             + values['QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD'], secret=secret).hexdigest()
    del values  # no provider-key extraction or output
    auth = None; edge_ip = None
    if auth_packet is not None:
        original_maps = {table: [dict(zip(data['columns'], line[:-1].split(b'\t'))) for line in data['rows']]
                         for table, data in original.items()}
        auth = authenticated_admin(verifier, auth_packet, original_maps, operations, served, availability_sha)
        # TCP route observation creates no HTTPS preview session and has no
        # credentials/provider request; it remains behind the real source gate.
        import socket
        with socket.create_connection(('app.quillmd.com', 9443), timeout=5) as route:
            edge_ip = route.getsockname()[0]
    options = backup.source_options(APP, legacy.ROLES)
    with psycopg.connect(**options, row_factory=dict_row) as conn:
        return readonly_copy_admission(conn, verifier, backup, original, baseline, manifest,
                                       policy, secret, fingerprint, auth, edge_ip, publisher_admission)


def installed_auth_packet():
    execution_gate()
    names = {'normal_raw': 'normal-authentication.json', 'session_raw': 'browser-session.json',
             'before_raw': 'metadata-before.json', 'invalid_raw': 'metadata-after-invalid-csrf.json',
             'after_raw': 'metadata-after-normal-mfa.json'}
    return {key: protected(ADMIN / name) for key, name in names.items()}


def validate_admin_final_storage(progress, reader=None):
    """Authenticate the actually captured final GET context; retain original MFA evidence."""
    reader = protected if reader is None else reader
    readback = progress['admin_readback']
    require(readback.get('final_storage_state_path') == str(FINAL_ADMIN_STATE)
            and re.fullmatch('[a-f0-9]{64}', readback.get('final_storage_state_sha256') or ''),
            'v3_exact_final_admin_storage_binding')
    started, finished = stamp(progress['started']), stamp(progress['finished'])
    workflows = stamp(progress['clinical_workflows_completed_at'])
    begin, captured, end = [stamp(readback[name]) for name in
                           ('started_at', 'final_storage_state_captured_at', 'finished_at')]
    require(started <= workflows <= begin <= captured <= end <= finished
            and 0 <= (end - begin).total_seconds() <= 1200
            and {row['name'] for row in progress['cases']} == set(CASES) and len(progress['cases']) == 5
            and all(row.get('browser_complete') is True for row in progress['cases']),
            'v3_final_admin_capture_actual_readback_interval')
    original_raw = reader(ADMIN / 'browser-session.json')
    authentication_raw = reader(ADMIN / 'normal-authentication.json')
    authentication = json.loads(authentication_raw)
    final_raw = reader(FINAL_ADMIN_STATE)
    require(sha(final_raw) == readback['final_storage_state_sha256']
            and sha(original_raw) == authentication.get('session_sha256') == readback.get('protected_session_sha256')
            and sha(authentication_raw) == readback.get('preparation_evidence_sha256')
            and authentication.get('session_file') == str(ADMIN / 'browser-session.json')
            and authentication.get('actor_id') == readback.get('actor_id'),
            'v3_final_admin_storage_evidence_hashes')
    expected = {'__Host-quillmd_preview': 'Lax', 'quillmd_doctor_session': 'Strict', 'quillmd_doctor_csrf': 'Strict'}
    populations = []
    for raw in (original_raw, final_raw):
        state = json.loads(raw); cookies = state.get('cookies')
        require(isinstance(cookies, list) and len(cookies) == 3
                and {row.get('name') for row in cookies} == set(expected), 'v3_final_admin_exact_cookie_population')
        for cookie in cookies:
            require(cookie.get('secure') is True and cookie.get('httpOnly') is True
                    and cookie.get('sameSite') == expected[cookie['name']]
                    and cookie.get('domain') == 'app.quillmd.com' and cookie.get('path') == '/'
                    and isinstance(cookie.get('value'), str) and cookie['value'],
                    'v3_final_admin_served_cookie_scope')
        populations.append({row['name']: row['value'] for row in cookies})
    names = ('quillmd_doctor_session', '__Host-quillmd_preview')
    require(all(populations[0][name] == populations[1][name] for name in names),
            'v3_final_admin_same_authenticated_cookie_identity')
    return {'complete': True, 'path': str(FINAL_ADMIN_STATE), 'sha256': sha(final_raw),
            'captured_at': readback['final_storage_state_captured_at'],
            'readback_interval': [readback['started_at'], readback['finished_at']],
            'same_authenticated_cookie_fingerprint': {name: sha(populations[1][name].encode()) for name in names},
            'original_MFA_storage_sha256': sha(original_raw), 'authentication_submissions': 0,
            'additional_GET_requests_by_verifier': 0, 'expiry_modified_by_adapter': False}


def validate_doctor_final_storage(progress, reader=None):
    """Bind the existing final doctor state to the genuine progress capture."""
    reader = protected if reader is None else reader
    item = progress.get('doctor_final_storage_state', {})
    path = CAMPAIGN / 'browser-session.json'
    require(item.get('path') == str(path) and re.fullmatch('[a-f0-9]{64}', item.get('sha256') or '')
            and stamp(progress['started']) <= stamp(item['captured_at']) <= stamp(progress['finished']),
            'v3_exact_final_doctor_storage_binding')
    raw = reader(path)
    require(sha(raw) == item['sha256'], 'v3_final_doctor_storage_actual_hash')
    return {'complete': True, **item, 'additional_requests': 0, 'expiry_modified_by_adapter': False}


def final_admission(verifier, packets, expected, preservation, operations, served):
    """Join independently collected clinical, financial and population evidence.

    Inputs are explicit in-memory packets. This pure join is not an installed
    collection or assertion that any browser/provider request has occurred.
    """
    full_revision(operations); full_revision(served)
    require(set(packets['generation']) == set(expected) == set(CASES), 'v3_exact_five_named_cases')
    require({case['actor'] for case in expected.values()} == {preservation['context']['actor']}
            and all(case['served_revision'] == served for case in expected.values()), 'v3_one_actual_actor_served_revision')
    proofs = [generation_admission(verifier, packets['generation'][name], expected[name]) for name in CASES]
    voice = speech_admission(verifier, packets['speech'], packets['speech_expected'])
    require(voice['job_id'] in preservation['context']['jobs']
            and packets['speech_expected']['encounter'] == expected['soap-voice']['encounter'],
            'v3_voice_same_soap_encounter')
    exposure = exposure_admission(packets['attempts'], complete=True)
    attempts = {row['job_id']: row for row in packets['attempts']}
    require(set(attempts) == {row['job_id'] for row in proofs} | {voice['job_id']}
            and all(Decimal(str(attempts[row['job_id']]['actual_cost'])) == Decimal(row['actual_cost']) for row in proofs + [voice]),
            'v3_attempt_actual_durable_cost_binding')
    population = old_and_added_rows_admission(verifier, preservation['original'], preservation['current'],
        preservation['keys'], preservation['manifest'], preservation['after_auth'], preservation['context'])
    files = file_catalog_admission(preservation['baseline'], preservation['snapshot'], preservation['catalog'],
                                   preservation['referenced_files'], preservation['invariants'])
    service = live_identity(preservation['availability'], preservation['live_identity'], served)
    admin = packets['admin_readback']
    require(admin['actor_id'] == preservation['context']['authentication']['admin']['actor_id']
            and admin['normal_session_reused'] is True and admin['authentication_submissions'] == 0
            and admin['department_patient_api_empty'] is True and admin['all_nine_get_checks_passed'] is True
            and admin['viewports'] == [1440, 768, 390], 'v3_staff_readonly_mfa_and_department_scope')
    return {'format': 3, 'complete': True, 'application_url': ORIGIN + '/',
            'operations_revision': operations, 'served_revision': served, 'model': MODEL,
            'provider_calls_by_verifier': 0, 'database_writes_by_verifier': 0,
            'configured_model_distinct_from_actual_message_model': True,
            'cases': proofs, 'voice': voice, 'exposure': exposure, 'population': population,
            'files': files, 'service_identity': service, 'admin_readback': admin,
            'limitations': ['No installed on-wire provider capture.',
                'Hardware microphone and native Microsoft Word rendering remain unverified.',
                'Free-prose rewriting and arbitrary/scanned forms are unsupported in this demo scope.',
                'Normal 443 requires separate restricted-ingress qualification without more provider calls.']}


def exposure_admission(attempts, *, complete=False):
    """Sequential known outcomes; a failed/unknown attempt permanently stops sends."""
    require(len(attempts) <= 6, 'v3_six_attempt_maximum')
    jobs = set(); generations = 0; speech = 0; total = Decimal(0)
    for position, row in enumerate(attempts):
        require(row['job_id'] not in jobs and row.get('send_sequence') == position + 1
                and row.get('retries') == 0 and row.get('passed') is True and row.get('actual_cost') is not None,
                'v3_known_passed_sequential_outcome_required')
        jobs.add(row['job_id']); cost = Decimal(str(row['actual_cost']))
        require(cost.is_finite() and cost >= 0, 'v3_finite_known_provider_cost')
        if row['kind'] == 'generation':
            generations += 1; cap = Decimal('.10')
        else:
            require(row['kind'] == 'transcription', 'v3_declared_attempt_kind')
            speech += 1; cap = Decimal('.20')
        quote = Decimal(str(row['quote_maximum']))
        require(quote.is_finite() and 0 < quote <= cap and cost <= quote, 'v3_provider_per_request_cap')
        total += cost
    require(generations <= 5 and speech <= 1 and total <= Decimal('.70'), 'v3_campaign_provider_cap')
    if complete:
        require(generations == 5 and speech == 1, 'v3_exact_completed_attempt_population')
    return {'generations': generations, 'transcriptions': speech, 'actual_provider_cost': str(total),
            'maximum_provider_exposure': '0.70', 'retries': 0}


def deadline_remaining(deadline, clock=time.monotonic):
    value = deadline - clock()
    require(value > 0, 'v3_phase_deadline')
    return value


def fixed_child_argv(source, phase, operations, served):
    full_revision(operations); full_revision(served)
    require(phase in ('before-auth', 'normal-auth', 'after-auth', 'browser', 'verify'), 'v3_fixed_child_phase')
    mode = '--dispatch-' + phase if phase in ('normal-auth', 'browser') else (
        '--verify' if phase == 'verify' else '--admit-' + phase)
    return [str(PYTHON), '-B', str(source / ENTRY), mode,
            '--operations-revision', operations, '--served-revision', served]


def native_group_identity(pid):
    execution_gate()
    return os.getpgid(pid), os.getsid(pid)


def native_group_alive(pid):
    execution_gate()
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def child_process(argv, source, destination, label, deadline, *, ruled, environment=None,
                  clock=time.monotonic, popen=None, killpg=None, group_identity=None,
                  group_alive=None, sleep=time.sleep, writer=write_new, input_bytes=None, pass_fds=()):
    """Kill/reap an owned process group on unknown outcome; never repeat it."""
    if popen is None or popen is subprocess.Popen:
        execution_gate()
        popen = subprocess.Popen
        killpg, group_identity, group_alive = os.killpg, native_group_identity, native_group_alive
    else:
        # An invented transport must not accidentally fall through to native
        # signals or /proc observations while the real source gate is false.
        require(killpg is not None and group_identity is not None and group_alive is not None,
                'v3_injected_transport_requires_injected_group_observers')
    remaining = deadline_remaining(deadline, clock)
    env = dict(os.environ if environment is None else environment)
    if ruled:
        env['RULED_ACT_MAX_SECS'] = str(max(1, int(remaining)))
    options = {'stdin': subprocess.PIPE} if input_bytes is not None else {}
    if pass_fds:
        options['pass_fds'] = pass_fds
    process = popen(argv, cwd=source, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True, **options)
    unknown = False; owned = False; cleanup_deadline = None
    require(type(process.pid) is int and process.pid > 0, 'v3_spawned_positive_process_identity')
    group = process.pid
    try:
        # The group identifier comes only from this newly spawned session,
        # never an external CLI/JSON group. Refuse PGID/SID disagreement.
        require(group_identity(group) == (group, group), 'v3_spawned_session_group_identity')
        owned = True
        try:
            stdout, stderr = process.communicate(input=input_bytes, timeout=remaining) if input_bytes is not None else process.communicate(timeout=remaining)
        except BaseException:
            unknown = True
        # Even an ordinary leader exit can leave descendants in this newly
        # allocated group. That outcome is incomplete, never successful.
        if unknown or group_alive(group):
            unknown = True
            try:
                killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except BaseException:
                pass
            cleanup_deadline = clock() + 10
            # A reaped leader and closed pipes do not prove its owned group is
            # empty. Kill/drain residual descendants before diagnostics.
            if group_alive(group):
                try: killpg(group, signal.SIGKILL)
                except ProcessLookupError: pass
            stdout, stderr = process.communicate(timeout=deadline_remaining(cleanup_deadline, clock))
            while group_alive(group):
                remaining = cleanup_deadline - clock()
                require(remaining > 0, 'v3_owned_group_drain_unknown_outcome')
                sleep(min(.05, remaining))
    finally:
        # Cleanup is finished before diagnostics can fail (e.g. ENOSPC).
        if process.poll() is None:
            if owned:
                try: killpg(group, signal.SIGKILL)
                except ProcessLookupError: pass
            else:
                # No unverified group signal. Popen's child handle is ours.
                process.kill()
            process.communicate(timeout=10 if cleanup_deadline is None else deadline_remaining(cleanup_deadline, clock))
    writer(destination / (label + '-stdout.log'), stdout)
    writer(destination / (label + '-stderr.log'), stderr)
    require(not unknown, 'v3_child_unknown_outcome_no_retry')
    require(process.returncode == 0 and len(stdout) <= 2 * 1024 * 1024 and len(stderr) <= 2 * 1024 * 1024,
            'v3_child_failed_no_retry')
    deadline_remaining(deadline, clock)
    return {'exit_code': 0, 'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr), 'retries': 0}


@contextmanager
def existing_operation_locks(runtime=RUNTIME):
    """No lock creation, adopted FD, alternative runtime, or detached holder."""
    if runtime == RUNTIME:
        execution_gate()
    with ExitStack() as stack:
        for relative in LOCKS:
            path = runtime / relative
            require(path.parent.resolve(strict=True) == path.parent, 'v3_canonical_lock_parent')
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            stack.callback(os.close, fd)
            item = os.fstat(fd)
            require(stat.S_ISREG(item.st_mode) and item.st_uid == os.getuid()
                    and stat.S_IMODE(item.st_mode) == 0o600 and item.st_nlink == 1, 'v3_owned_existing_lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def protocol_pipeline(host, contract, operations, served):
    """Fixed phase sequencing; fake Host tests do not constitute lock/live proof."""
    require(contract.get('protocol_qualified') is True, 'v3_contract_not_qualified')
    source_gate(host, contract, operations, served, host.environment)
    host.authenticate_dependencies()
    receipt = host.authenticate_availability(contract, operations, served)
    require(host.fresh_paths_absent(), 'v3_exclusive_new_paths_required')
    started = host.clock()
    outer_deadline = started + 1680  # acquisition/admissions + 180 + shared1200 + boundedcleanup
    with host.exclusions(operations, outer_deadline):
        host.recheck_source_and_idle(receipt, operations, served)
        before = host.admit('before-auth', contract, receipt, operations, served)
        require(before['complete'] is True, 'v3_before_auth_admission_incomplete')
        deadline_remaining(outer_deadline, host.clock)
        host.create_exclusive_preparation(operations, served, before)
        auth_deadline = min(host.clock() + 180, outer_deadline)
        try:
            host.child('normal-auth', operations, served, auth_deadline)
            auth = host.normal_auth_evidence()
            after = host.admit('after-auth', contract, receipt, operations, served, auth)
            require(after['complete'] is True, 'v3_after_auth_admission_incomplete')
            deadline_remaining(outer_deadline, host.clock)
            host.recheck_source_and_idle(receipt, operations, served)
        except BaseException:
            host.write_stop('v3_authentication_failed_or_unknown_no_replay')
            raise
        deadline_remaining(outer_deadline, host.clock)
        # Same parent exclusions remain held through all actual clinical effects.
        phase_deadline = min(host.clock() + 1200, outer_deadline)
        deadline_remaining(phase_deadline, host.clock)
        host.write_attempt(operations, served, before, after)
        try:
            host.child('browser', operations, served, phase_deadline)
            host.child('verify', operations, served, phase_deadline)
            report = host.independent_report()
            require(report['complete'] is True and report['operations_revision'] == operations
                    and report['served_revision'] == served, 'v3_independent_report_revision_binding')
            deadline_remaining(phase_deadline, host.clock)
            host.write_complete(report)
            return report
        except BaseException:
            host.write_stop('v3_campaign_failed_or_unknown_preserve_availability_and_records')
            raise


@contextmanager
def sealed_buffer(raw):
    """A child executes these exact bytes, never a second pathname read."""
    fd = os.memfd_create('quillmd-v3-checked-source', os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
    try:
        require(os.write(fd, raw) == len(raw), 'v3_checked_buffer_write')
        os.lseek(fd, 0, os.SEEK_SET)
        seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
        require(fcntl.fcntl(fd, fcntl.F_GET_SEALS) == seals, 'v3_checked_buffer_seals')
        yield fd
    finally:
        os.close(fd)


CHECKED_BOOTSTRAP = """import fcntl,hashlib,os,sys
fd=int(sys.argv[1]);expected=sys.argv[2];filename=sys.argv[3]
seals=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
assert fcntl.fcntl(fd,fcntl.F_GET_SEALS)==seals
raw=os.pread(fd,2*1024*1024,0);assert hashlib.sha256(raw).hexdigest()==expected
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.dirname(filename)))+'/rebuild')
sys.argv=[filename]+sys.argv[4:]
scope={'__file__':filename,'__name__':'_quillmd_v3_checked_child','CHECKED_SOURCE_FD':fd}
exec(compile(raw,filename,'exec'),scope)
raise SystemExit(scope['main']())
"""


def checked_python_argv(source, fd, raw, arguments):
    return [str(PYTHON), '-B', '-c', CHECKED_BOOTSTRAP, str(fd), sha(raw), str(source / SELF), *arguments]


def child_environment(environment):
    allowed = {'HOME', 'GH_TOKEN', 'GITHUB_TOKEN', 'GH_HOST', 'GH_CONFIG_DIR',
               'RULED_MUTATION_DECLARATION', 'RULED_MUTATION_DECL_COMMIT', 'RULED_ACT_MAX_SECS'}
    value = {name: item for name, item in environment.items() if name in allowed}
    value.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LC_ALL='C', GIT_OPTIONAL_LOCKS='0')
    return value


def process_start(raw):
    """Linux stat starttime survives spaces and parentheses in the comm field."""
    try:
        value = int(raw.rsplit(') ', 1)[1].split()[19])
    except (IndexError, ValueError):
        raise Refusal('v3_native_process_start') from None
    require(value > 0, 'v3_native_process_start')
    return value


def lock_population(raw, pid):
    found = set()
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) == 8 and fields[1:4] == ['FLOCK', 'ADVISORY', 'WRITE'] and fields[4] == str(pid):
            device, inode = fields[5].rsplit(':', 1)
            major, minor = device.split(':')
            found.add((int(major, 16), int(minor, 16), int(inode)))
    return found


def parent_phase_admission(context, phase, operations, served, *, monotonic=time.monotonic,
                           stat_fd=os.stat, read_text=lambda path: Path(path).read_text(),
                           read_bytes=lambda path: Path(path).read_bytes(), source=SOURCE,
                           self_mode=None):
    """Observe the native holder; child calls retain the exact execute contract."""
    require(phase in PARENT_PHASES and context.get('format') == 3
            and context.get('phase') == phase and context.get('operations_revision') == operations
            and context.get('served_revision') == served, 'v3_parent_phase_binding')
    pid = context.get('parent_pid')
    require(type(pid) is int and pid > 1 and context.get('parent_uid') == 1000
            and type(context.get('deadline_monotonic')) in (int, float)
            and math.isfinite(context['deadline_monotonic']) and context['deadline_monotonic'] > monotonic(),
            'v3_parent_phase_live_deadline')
    proc = Path('/proc') / str(pid)
    mode = '--execute'
    if self_mode is not None:
        require(pid == os.getpid() and self_mode in ('--execute', '--preflight', '--admit-before-auth'),
                'v3_exact_own_holder_mode')
        mode = self_mode
    expected_argv = [str(PYTHON), '-B', str(source / ENTRY), mode,
                     '--operations-revision', operations, '--served-revision', served]
    require(read_bytes(proc / 'cmdline') == b'\0'.join(value.encode() for value in expected_argv) + b'\0',
            'v3_parent_fixed_command')
    require(process_start(read_text(proc / 'stat')) == context.get('parent_start_ticks'), 'v3_parent_process_reused')
    locks = context.get('locks')
    require(isinstance(locks, list) and {row.get('path') for row in locks}
            == {str(RUNTIME / value) for value in (*LOCKS, PUBLICATION_LOCK)} and len(locks) == 5,
            'v3_same_five_parent_locks')
    held = lock_population(read_text('/proc/locks'), pid)
    for row in locks:
        require(type(row.get('fd')) is int and row['fd'] >= 3, 'v3_parent_lock_descriptor')
        info = stat_fd(proc / 'fd' / str(row['fd']))
        require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                and info.st_dev == row['device'] and info.st_ino == row['inode']
                and (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino) in held,
                'v3_parent_lock_not_held')
        with nofollow_file(row['path']) as attached:
            info_at_path = os.fstat(attached)
            require((info_at_path.st_dev, info_at_path.st_ino) == (info.st_dev, info.st_ino),
                    'v3_parent_lock_path_replaced')
    require(process_start(read_text(proc / 'stat')) == context['parent_start_ticks'], 'v3_parent_process_race')
    return context


def derive_authority(contract, common, operations, served, admission_raws):
    """Actual observed hashes are derived evidence, never prospective self-pins."""
    require(contract.get('protocol_qualified') is True and contract.get('served_revision') == served
            and contract.get('operations_revision') is None
            and contract.get('operations_revision_policy') == OPERATIONS_REVISION_POLICY,
            'v3_derived_authority_source_policy')
    require(set(admission_raws) <= {'before-auth', 'after-auth'}, 'v3_runtime_admission_population')
    result = copy.deepcopy(contract)
    result.update(operations_revision=full_revision(operations), served_revision=full_revision(served),
                  original_activation=str(ORIGINAL), original_receipts=common.ORIGINAL_RECEIPTS,
                  failed_continuation_receipts=common.FAILED_CONTINUATION,
                  admissions={phase: {'path': str(PREPARATION / ('admission-' + phase + '.json')),
                                     'sha256': sha(raw)} for phase, raw in admission_raws.items()})
    return result


def replace_once(raw, before, after, label):
    require(raw.count(before) == 1, 'v3_fixed_adapter_' + label)
    return raw.replace(before, after)


JS_OWNED_IO = rb"""
const ownedOutputs=new Map();
function openedParent(filename){
 must(typeof filename==='string'&&path.isAbsolute(filename)&&path.normalize(filename)===filename,'Fixed absolute input required');
 const descriptors=[];let fd;
 try{
  fd=fs.openSync('/',fs.constants.O_RDONLY|fs.constants.O_DIRECTORY|fs.constants.O_NOFOLLOW);descriptors.push(fd);
  let current='';for(const name of path.dirname(filename).split('/').filter(Boolean)){
   current+='/'+name;fd=fs.openSync('/proc/self/fd/'+fd+'/'+name,fs.constants.O_RDONLY|fs.constants.O_DIRECTORY|fs.constants.O_NOFOLLOW);descriptors.push(fd);
   must(fs.readlinkSync('/proc/self/fd/'+fd)===current,'Input parent changed');
  }
  return {fd,descriptors,filename,check(){must(fs.readlinkSync('/proc/self/fd/'+fd)===path.dirname(filename),'Input parent changed');},close(){for(const item of descriptors.reverse())fs.closeSync(item);}};
 }catch(error){for(const item of descriptors.reverse())fs.closeSync(item);throw error;}
}
function fdIdentity(info){return [info.dev,info.ino,info.uid,info.gid,info.mode,info.nlink,info.size,info.mtimeMs,info.ctimeMs].join(':');}
function checkedRead(filename,privateMode,maximum){
 const parent=openedParent(filename);let fd,attached;
 try{
  fd=fs.openSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  const before=fs.fstatSync(fd),mode=before.mode&0o7777;
  const archive=filename.startsWith('/opt/meddoc-pro/rebuild/.runtime/owner-demo-20261006/legacy-qa/source/');
  const rootPublic=filename==='/etc/nginx/sites-available/quillmd-email-preview';
  const owner=before.uid===1000&&before.gid===1000||!privateMode&&rootPublic&&before.uid===0&&before.gid===0;
  must(before.isFile()&&owner&&before.nlink===1&&before.size<=maximum&&(privateMode?mode===0o600:!(mode&0o7000)&&((mode&0o004)!==0||archive&&mode===0o600)),'Input identity refused');
  const raw=fs.readFileSync(fd);parent.check();
  attached=fs.openSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  must(raw.length===before.size&&fdIdentity(before)===fdIdentity(fs.fstatSync(fd))&&fdIdentity(before)===fdIdentity(fs.fstatSync(attached)),'Input changed');
  return raw;
 }finally{if(attached!==undefined)fs.closeSync(attached);if(fd!==undefined)fs.closeSync(fd);parent.close();}
}
function privateRead(filename,maximum=8*1024*1024){return checkedRead(filename,true,maximum);}
function reviewedRead(filename,encoding){
 if(typeof filename==='number')return fs.readFileSync(filename,encoding);
 const raw=checkedRead(filename,false,16*1024*1024);return encoding?raw.toString(encoding):raw;
}
function durable(filename,value,exclusive=false){
 must(filename.startsWith(ADMIN+'/')||filename.startsWith(CAMPAIGN+'/'),'Only new fixed evidence outputs permitted');
 const raw=Buffer.from(JSON.stringify(value,null,2)+'\n');must(raw.length<=8*1024*1024,'Evidence size bound');
 const parent=openedParent(filename);let attached;
 try{
  let fd=ownedOutputs.get(filename);
  if(fd===undefined){fd=fs.openSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);ownedOutputs.set(filename,fd);}
  else must(!exclusive&&filename===CAMPAIGN+'/progress.json','Only own progress output may repeat');
  const before=fs.fstatSync(fd);must(before.isFile()&&before.uid===1000&&before.gid===1000&&(before.mode&0o7777)===0o600&&before.nlink===1,'Own output identity changed');
  attached=fs.openSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  must(fdIdentity(before)===fdIdentity(fs.fstatSync(attached)),'Own output path replaced');parent.check();
  fs.ftruncateSync(fd,0);let offset=0;while(offset<raw.length)offset+=fs.writeSync(fd,raw,offset,raw.length-offset,offset);fs.fsyncSync(fd);
  must(fdIdentity(fs.fstatSync(fd))===fdIdentity(fs.fstatSync(attached)),'Own output changed');parent.check();
 }finally{if(attached!==undefined)fs.closeSync(attached);parent.close();}
}
function checkedNewRaw(filename,value,options){
 must(typeof filename==='string'&&(filename.startsWith(ADMIN+'/')||filename.startsWith(CAMPAIGN+'/'))&&options.mode===0o600&&options.flag==='wx','Fixed new evidence output required');
 const raw=Buffer.isBuffer(value)?value:Buffer.from(value);must(raw.length<=16*1024*1024,'Evidence size bound');
 const parent=openedParent(filename);let fd,attached;
 try{
  fd=fs.openSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  const info=fs.fstatSync(fd);must(info.isFile()&&info.uid===1000&&info.gid===1000&&(info.mode&0o7777)===0o600&&info.nlink===1,'New evidence identity refused');
  fs.writeFileSync(fd,raw);fs.fsyncSync(fd);parent.check();
  attached=fs.openSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  must(fdIdentity(fs.fstatSync(fd))===fdIdentity(fs.fstatSync(attached)),'New evidence path changed');
 }finally{if(attached!==undefined)fs.closeSync(attached);if(fd!==undefined)fs.closeSync(fd);parent.close();}
}
function checkedNewDir(filename,options){
 const permitted=[ADMIN,CAMPAIGN,...['soap-typed','custom-word-typed','soap-voice','allergy-missing','allergy-legitimate'].map(name=>CAMPAIGN+'/'+name)];
 must(permitted.includes(filename)&&options.mode===0o700,'Fixed new directory required');
 const parent=openedParent(filename);
 try{fs.mkdirSync('/proc/self/fd/'+parent.fd+'/'+path.basename(filename),options);parent.check();}finally{parent.close();}
}
"""


def javascript_adapter(blobs, phase, declaration, authority, child_check):
    """Exact frozen algorithm plus source-owned authority and checked-byte imports.

    No preparation file is edited. The only newly enabled gate is the qualified
    current Python child's fresh source, parent-lock and live-service admission.
    """
    require(phase in ('normal-auth', 'browser'), 'v3_fixed_javascript_phase')
    require(set(blobs) == set(DEPENDENCIES) and all(sha(blobs[name]) == expected
            for name, expected in DEPENDENCIES.items()), 'v3_transitive_dependency_drift')
    filename = 'prepare-installed-admin-auth-v3.mjs' if phase == 'normal-auth' else 'installed-browser-acceptance-v3.mjs'
    original = blobs[filename]
    if phase == 'browser':
        # Move the same authenticated block; its GET, layout, accessibility and
        # privacy predicates remain byte-identical. No frozen input is edited.
        start = b"  const adminContext=await browser.newContext({storageState:JSON.parse(adminSessionBytes)});let readback;\n"
        end = b"  }finally{await adminContext.close();if(readback){readback.finished_at=new Date().toISOString();save();}}\n"
        require(original.count(start) == original.count(end) == 1, 'v3_fixed_admin_readback_block')
        first, last = original.index(start), original.index(end) + len(end)
        require(first < last, 'v3_fixed_admin_readback_block')
        block = original[first:last]
        capture = (b"const finalAdminState=await adminContext.storageState();"
            b"readback.final_storage_state_captured_at=new Date().toISOString();"
            b"readback.final_storage_state_path=OUTPUT+'/admin-browser-session-after-readback.json';"
            b"durable(readback.final_storage_state_path,finalAdminState,true);"
            b"readback.final_storage_state_sha256=digest(privateRead(readback.final_storage_state_path));"
            b"readback.complete=true;save();")
        block = replace_once(block, b'readback.complete=true;save();', capture, 'final_admin_storage_capture')
        clinical_end = b"  result.browser_workflows_complete=true;result.independent_billing_history_pending=true;"
        result = original[:first] + original[last:]
        result = replace_once(result, clinical_end,
            b"  result.clinical_workflows_completed_at=new Date().toISOString();save();\n" + block + clinical_end,
            'final_admin_readback_position')
        result = replace_once(result,
            b"await ctx.storageState({path:OUTPUT+'/browser-session.json'});fs.chmodSync(OUTPUT+'/browser-session.json',0o600);",
            b"const finalDoctorState=await ctx.storageState();const doctorCapturedAt=new Date().toISOString();"
            b"durable(OUTPUT+'/browser-session.json',finalDoctorState,true);"
            b"result.doctor_final_storage_state={path:OUTPUT+'/browser-session.json',"
            b"sha256:digest(privateRead(OUTPUT+'/browser-session.json')),captured_at:doctorCapturedAt};",
            'final_doctor_storage_capture')
    else:
        result = original
    common = blobs['acceptance-v3-contract.mjs']
    # The original pure validators execute authenticated Python bytes via stdin,
    # preserving their predicates without re-importing a mutable filename.
    py = ("import base64,json,sys;scope={};exec(compile(base64.b64decode("
          + repr(base64.b64encode(blobs['acceptance_v3_contract.py']).decode())
          + "),'<authenticated-v3-contract>','exec'),scope);"
          + "scope.update(POST_RESTORE_PINS=json.loads(" + repr(encode(POST_RESTORE_PINS).decode())
          + "),POST_RESTORE_PROPOSAL_SHA=" + repr(POST_RESTORE_PROPOSAL_SHA)
          + ",POST_RESTORE_OWNER_REPLY_SHA=" + repr(POST_RESTORE_OWNER_REPLY_SHA) + ");"
          + "exec(compile(" + repr(CONFIGURATION_ADMISSION_SOURCE)
          + ",'<reviewed-configuration-proof>','exec'),scope);"
          + "scope['adapt_configuration_admission'](scope,base64.b64decode("
          + repr(base64.b64encode(blobs['acceptance_v3_contract.py']).decode()) + "));"
          + "value=json.load(sys.stdin);"
          "raw=bytes.fromhex(value['raw_hex']);args=value['args'];kind=value['kind'];"
          "result=scope['availability'](raw,bytes.fromhex(value['original_hex']),**args)"
          "if kind=='availability'else scope['auth_sequence'](raw,**args)if kind=='auth'"
          "else scope['admission'](raw,**args);print(json.dumps(result,separators=(',',':')))")
    gate = ("export function executionGate(){execFileSync(" + json.dumps(str(PYTHON)) + ","
            + json.dumps(child_check['argv']) + ",{encoding:'utf8',timeout:90000,maxBuffer:1048576,"
            "stdio:['pipe','pipe','pipe'," + str(child_check['source_fd']) + "]});}")
    old_gate = b"export function executionGate(){if(!EXECUTION_QUALIFIED||!NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED||!FIXED_RUNNER_QUALIFIED)throw new Error('acceptance_v3_execution_unqualified');}"
    common = replace_once(common, old_gate, gate.encode(), 'native_child_gate')
    start = common.index(b'export function validateV3(kind,args){')
    common = common[:start] + ("export function validateV3(kind,args){return JSON.parse(execFileSync("
        + json.dumps(str(PYTHON)) + ",['-B','-c'," + json.dumps(py)
        + "],{input:JSON.stringify({kind,...args}),encoding:'utf8',maxBuffer:4194304,timeout:15000}));}\n").encode()
    url = 'data:text/javascript;base64,' + base64.b64encode(common).decode()
    result = replace_once(result, b"from './acceptance-v3-contract.mjs'", ('from ' + json.dumps(url)).encode(), 'contract_import')
    result = result.replace(b'privateRead(new URL(import.meta.url).pathname)',
                            ('Buffer.from(' + json.dumps(base64.b64encode(original).decode()) + ",'base64')").encode())
    expected_reads = 2 if phase == 'normal-auth' else 1
    require(original.count(b'privateRead(new URL(import.meta.url).pathname)') == expected_reads,
            'v3_fixed_adapter_self_source')
    result = replace_once(result, b'fs.readFileSync(path.join(process.cwd(),DECLARATION))',
                          ('Buffer.from(' + json.dumps(base64.b64encode(declaration).decode()) + ",'base64')").encode(), 'declaration_buffer')
    if phase == 'normal-auth':
        result = replace_once(result, b'const contract=JSON.parse(contractJSON[1]);',
                              ('const contract=' + encode(authority).decode() + ';').encode(), 'runtime_authority')
        old_citation = b"execFileSync('bash',[path.join(process.cwd(),'scripts/check-citation.sh'),revision],{cwd:process.cwd(),encoding:'utf8',maxBuffer:1024*1024,timeout:360000})"
        new_citation = b"'exact checked parent and child citation passed'"
        result = replace_once(result, old_citation, new_citation, 'closed_citation')
    else:
        result = replace_once(result, b"const contract=JSON.parse(/<!-- owner-acceptance-v3-contract -->\\s*```json\\s*([\\s\\S]*?)```/.exec(declaration.toString())[1]);",
                              ('const contract=' + encode(authority).decode() + ';').encode(), 'runtime_authority')
    # The qualified helper may have observed installed metadata before refusing.
    # Node has sent nothing at this point; it must not deny those observations.
    result = replace_once(result, b'installed_state_accessed:false,reason:',
                          b'installed_state_accessed:true,reason:', 'initial_gate_report')
    # The frozen I/O helpers use pathname checks followed by opens. Keep the
    # clinical/auth algorithms, but close those parents and retain only newly
    # created output descriptors; a replacement cannot redirect a save.
    require(result.count(b'function privateRead(') == result.count(b'function durable(') == 1,
            'v3_fixed_adapter_owned_io')
    begin = result.index(b'function privateRead(filename,maximum=8*1024*1024){')
    end = result.index(b'\n}', begin) + 2
    result = result[:begin] + result[end:]
    begin = result.index(b'function durable(filename,value')
    end = result.index(b'\n', begin)
    result = result[:begin] + result[end:]
    result = result.replace(b'fs.readFileSync(', b'reviewedRead(')
    result = result.replace(b'fs.writeFileSync(', b'checkedNewRaw(')
    result = result.replace(b'fs.mkdirSync(', b'checkedNewDir(')
    begin = result.index(b'\n', result.index(b'function must(value,message)')) + 1
    result = result[:begin] + JS_OWNED_IO + result[begin:]
    return result


def verifier_adapter(raw, common, authority, availability_verifier, completion_check=None,
                     publisher_admission=None):
    """Use the full frozen independent DB/files/SDK/Word verifier, not browser flags."""
    require(sha(raw) == DEPENDENCIES['verify_installed_acceptance_v3.py'], 'v3_frozen_dependency_hash')
    tree = ast.parse(raw)
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == 'acceptance_v3_contract']
    require(len(imports) == 2, 'v3_fixed_verifier_contract_imports')
    tree.body = [node for node in tree.body if node not in imports]
    constants = [node for node in ast.walk(tree) if isinstance(node, ast.Constant)
                 and node.value == 'installed-acceptance-v2-20261006']
    # Four frozen v2 campaign literals: downloaded generation/speech results,
    # downloaded DOCX, and the exclusive report destination. No check weakens.
    require(len(constants) == 4 and {node.lineno for node in constants} == {942, 973, 998, 1044},
            'v3_fixed_verifier_destination')
    for node in constants:
        node.value = CAMPAIGN.name
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'verify']
    require(len(functions) == 1, 'v3_exact_final_admin_verifier_function')
    assignments = [node for node in functions[0].body if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == 'admin_end']
    expected = ast.parse("admin_end=datetime.fromisoformat(readback['finished_at'].replace('Z','+00:00'))").body[0]
    require(len(assignments) == 1 and ast.dump(assignments[0], include_attributes=False)
            == ast.dump(expected, include_attributes=False), 'v3_exact_final_admin_verifier_interval')
    position = functions[0].body.index(assignments[0]) + 1
    functions[0].body.insert(position, ast.parse(
        "readback['final_storage_state_verification']=validate_admin_final_storage(progress)").body[0])
    functions[0].body.insert(position + 1, ast.parse(
        "progress['doctor_final_storage_state']['verification']=validate_doctor_final_storage(progress)").body[0])
    reports = [node for node in functions[0].body if isinstance(node, ast.Assign)
               and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
               and node.targets[0].id == 'report' and isinstance(node.value, ast.Dict)]
    require(len(reports) == 1 and not any(isinstance(key, ast.Constant) and key.value == 'doctor_final_storage_state'
            for key in reports[0].value.keys), 'v3_exact_final_doctor_verifier_report')
    reports[0].value.keys.append(ast.Constant('doctor_final_storage_state'))
    reports[0].value.values.append(ast.parse("progress['doctor_final_storage_state']", mode='eval').body)
    module = types.ModuleType('_quillmd_v3_independent_verifier')
    module.__file__ = str(FROZEN / 'verify_installed_acceptance_v3.py')
    module.__dict__.update(v3_execution_gate=execution_gate, validate_v3_availability=common.availability,
        validate_v3_admission=common.admission, validate_v3_auth_sequence=common.auth_sequence,
        validate_admin_final_storage=validate_admin_final_storage,
        validate_doctor_final_storage=validate_doctor_final_storage,
        AVAILABILITY=str(AVAILABILITY), PREPARATION=str(PREPARATION), ADMIN=str(ADMIN), CAMPAIGN=str(CAMPAIGN))
    exec(compile(ast.fix_missing_locations(tree), module.__file__, 'exec'), module.__dict__)
    module.load_v3_authority = lambda operations, served: copy.deepcopy(authority) if (
        operations == authority['operations_revision'] and served == authority['served_revision']) else require(False, 'v3_verifier_authority_revision')
    # The operational descendant's reviewed publisher closure handles native
    # clock representations. It retains the frozen semantics and old captures.
    require(callable(publisher_admission), 'v3_checked_publisher_admission_required')
    module.publisher_source_admission = publisher_admission
    module.protected = protected
    original_service_verification = module.verify_service_identity
    def checked_services(release, activation, storage):
        require(callable(completion_check), 'v3_independent_completion_provenance_required')
        result = original_service_verification(release, activation, storage)
        result['completion_unit_provenance'] = completion_check(activation)
        return result
    module.verify_service_identity = checked_services
    return module


def checked_native_modules(host):
    """Private package namespace resolves transitive relative imports to checked bytes."""
    names = NATIVE_NAMES
    blobs = {}
    for name in names:
        relative = 'rebuild/ops/' + name + '.py'
        blobs[name] = host.read_source(host.source / relative)
        require(blobs[name] == host.git(host.source, 'show', host.operations + ':' + relative),
                'v3_native_adapter_git_identity')
    package_name = '_quillmd_v3_native_' + host.operations
    package = types.ModuleType(package_name)
    package.__path__ = []  # no pathname fallback for an unknown dependency
    sys.modules[package_name] = package
    for name in names:
        module = types.ModuleType(package_name + '.' + name)
        module.__file__ = str(host.source / ('rebuild/ops/' + name + '.py'))
        module.__package__ = package_name
        sys.modules[module.__name__] = module
        setattr(package, name, module)
        exec(compile(blobs[name], module.__file__, 'exec'), module.__dict__)
    return package


class InstalledHost:
    """Fixed native adapter. Its first gate precedes every installed observation."""
    source = SOURCE

    def __init__(self):
        execution_gate()
        require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000,
                'v3_native_owner_identity')
        self.environment = dict(os.environ)
        self.clock = time.monotonic
        self.inside = False
        self.lock_rows = []
        self.admission_raws = {}
        self.contract = None
        self.publication_alignment = None
        self.parent_lock_context = None
        self.own_hold_mode = None

    def canonical(self, path):
        return Path(path).resolve(strict=True)

    def command(self, argv, *, timeout=90):
        env = {name: value for name, value in self.environment.items()
               if name in ('HOME', 'GH_TOKEN', 'GITHUB_TOKEN', 'GH_HOST', 'GH_CONFIG_DIR')}
        env.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LC_ALL='C', GIT_OPTIONAL_LOCKS='0')
        result = subprocess.run(argv, cwd=self.source, env=env, capture_output=True, timeout=timeout)
        require(result.returncode == 0 and len(result.stdout) <= 16 * 1024 * 1024,
                'v3_fixed_readonly_command')
        return result.stdout

    def git(self, tree, *args):
        return self.command(['/usr/bin/git', '-C', str(tree), *args])

    def read_source(self, path):
        return bounded_bytes(path, private=False)

    def readability(self, path):
        tree = self.source if Path(path).is_relative_to(self.source) else ROOT
        relative = str(Path(path).relative_to(tree))
        index = self.git(tree, 'ls-files', '-s', '--', relative).split()
        require(len(index) >= 4 and index[0] in (b'100644', b'100755'), 'v3_canonical_source_index_mode')
        with nofollow_file(path) as fd:
            info = os.fstat(fd)
            require(stat.S_IMODE(info.st_mode) == int(index[0][-3:], 8), 'v3_canonical_source_mode')
        for parent in Path(path).parents:
            if parent == Path('/'):
                break
            require(stat.S_IMODE(parent.stat().st_mode) & 0o001, 'v3_source_public_traversal')

    def citation(self, revision):
        # Reuse the reviewed descriptor-closed citation predicates, with a
        # private module namespace so no other operator's globals are changed.
        raw = self.read_source(self.source / 'rebuild/ops/repair_source_permissions.py')
        require(raw == self.git(self.source, 'show', self.operations + ':rebuild/ops/repair_source_permissions.py'),
                'v3_citation_adapter_source')
        module = module_from_bytes(raw, self.source / 'rebuild/ops/repair_source_permissions.py', sha(raw))
        module.SOURCE = self.source
        top = self.read_source(self.source / 'scripts/check-citation.sh')
        library = self.read_source(self.source / 'scripts/lib/runs-api.sh')
        for name, value in (('scripts/check-citation.sh', top), ('scripts/lib/runs-api.sh', library)):
            require(value == self.git(self.source, 'show', self.operations + ':' + name), 'v3_citation_checked_bytes')
        module.sealed_citation(top, library, revision)

    def bind(self, contract, operations, served):
        self.contract, self.operations, self.served = contract, full_revision(operations), full_revision(served)
        return source_gate(self, contract, operations, served, self.environment)

    def authenticate_dependencies(self):
        self.blobs = {name: protected(FROZEN / name) for name in DEPENDENCIES}
        require(all(sha(self.blobs[name]) == expected for name, expected in DEPENDENCIES.items()),
                'v3_transitive_dependency_drift')
        self.common, _, self.policy = frozen_modules()
        # Import only the reviewed operational source after bind has authenticated
        # its Git tree and exact citation. No service helper is ever invoked here.
        package = checked_native_modules(self)
        old, recovery = package.legacy_model_activation, package.private_availability_recovery
        self.old, self.recovery = old, recovery
        _, self.backup, _, managed, self.storage = old.modules()
        self.native = old.Host(managed)
        self.availability_verifier = recovery.frozen_verifier()
        original_verifier = protected(BASE / 'verify_installed_acceptance_v2.py', 2 * 1024 * 1024)
        require(sha(original_verifier) == FROZEN_B77, 'v3_frozen_dependency_hash')
        setattr(self.availability_verifier, '__authenticated_source', original_verifier)
        adapt_publisher_adjudicator(self.availability_verifier)

    def authority(self):
        return derive_authority(self.contract, self.common, self.operations, self.served, self.admission_raws)

    def authenticate_availability(self, contract, operations, served):
        raw = protected(AVAILABILITY / 'complete.json')
        require(re.fullmatch('[a-f0-9]{64}', contract.get('availability_receipt_sha256') or '')
                and sha(raw) == contract['availability_receipt_sha256'], 'v3_actual_availability_receipt_pin')
        receipt = self.common.availability(raw, protected(ORIGINAL / 'failed.json'), self.authority(), operations, served)
        for directory, pins in ((ORIGINAL, self.common.ORIGINAL_RECEIPTS), (CONSUMED, self.common.FAILED_CONTINUATION)):
            require(all(sha(protected(directory / name)) == expected for name, expected in pins.items()),
                    'v3_original_failed_evidence_preserved')
        self.availability_raw, self.receipt = raw, receipt
        return receipt

    def fresh_paths_absent(self):
        return not any(os.path.lexists(path) for path in (PREPARATION, ADMIN, CAMPAIGN, ATTEMPT))

    @contextmanager
    def exclusions(self, operations, deadline):
        require(not self.inside and operations == self.operations, 'v3_parent_exclusion_scope')
        with ExitStack() as stack:
            def acquire(relative, limit):
                path = RUNTIME / relative
                fd = stack.enter_context(nofollow_file(path))
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000
                        and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
                        'v3_owned_existing_lock')
                while True:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        deadline_remaining(limit, self.clock)
                        time.sleep(.05)
                self.lock_rows.append({'path': str(path), 'fd': fd, 'device': info.st_dev, 'inode': info.st_ino})
            try:
                for relative in LOCKS:
                    acquire(relative, deadline)
                # Freeze publisher inputs first, while leaving natural publication
                # free. Otherwise an older row can describe an earlier monitor.
                deadline_remaining(deadline, self.clock)
                contract = self.recovery.contract_from_bytes(self.read_source(self.source / self.recovery.DECL))
                sources = self.recovery.publisher_unit_sources()
                observe = self.recovery.publisher_observer(self.backup)
                selected = self.recovery.await_natural_publication(contract, observe)
                deadline_remaining(deadline, self.clock)
                acquire(PUBLICATION_LOCK, min(deadline, self.clock() + 120))
                acquired_monotonic = self.clock()
                current = observe()
                require(current['coherent_unit'] and all(current[name] == selected[name]
                        for name in ('row', 'unit', 'timer', 'journal')),
                        'v3_selected_publication_drift')
                require(self.recovery.publisher_unit_sources() == sources,
                        'v3_publisher_unit_file_drift')
                deadline_remaining(deadline, self.clock)
                self.publication_alignment = {'format': 3, 'selected': selected,
                    'unit_sources': sources, 'maximum_natural_wait_seconds': 360,
                    'manual_publications': 0, 'timer_or_service_actions': 0, 'provider_calls': 0,
                    'hold': {'acquired_monotonic': acquired_monotonic, 'deadline_monotonic': deadline,
                             'parent_pid': os.getpid(), 'parent_start_ticks': process_start(Path('/proc/self/stat').read_text()),
                             'locks': copy.deepcopy(self.lock_rows), 'own_mode': self.own_hold_mode}}
                self.parent_lock_context = {'format': 3, 'phase': 'verify', 'operations_revision': self.operations,
                    'served_revision': self.served, 'parent_pid': os.getpid(), 'parent_uid': os.getuid(),
                    'parent_start_ticks': self.publication_alignment['hold']['parent_start_ticks'],
                    'deadline_monotonic': deadline, 'locks': copy.deepcopy(self.lock_rows)}
                self.inside = True
                yield
            finally:
                self.inside = False
                self.lock_rows = []
                self.publication_alignment = None
                self.parent_lock_context = None

    def check_publication_hold(self):
        require(self.inside and isinstance(self.publication_alignment, dict)
                and isinstance(self.parent_lock_context, dict), 'v3_existing_parent_publication_hold_required')
        hold, context = self.publication_alignment['hold'], self.parent_lock_context
        require(all(hold[name] == context[name] for name in ('parent_pid', 'parent_start_ticks', 'locks'))
                and 0 < hold['acquired_monotonic'] <= self.clock() < hold['deadline_monotonic']
                and context['deadline_monotonic'] <= hold['deadline_monotonic'], 'v3_hash_bound_parent_hold_identity')
        parent_phase_admission(context, context['phase'], self.operations, self.served,
                               monotonic=self.clock, source=self.source,
                               self_mode=hold['own_mode'] if context['parent_pid'] == os.getpid() else None)

    def observe_held_publication(self):
        self.check_publication_hold()
        monotonic_fields = ('InvocationID', 'ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic')
        before = self.recovery.own_unit_properties(PUBLISHER, monotonic_fields)
        current = self.recovery.publisher_observer(self.backup)()
        after = self.recovery.own_unit_properties(PUBLISHER, monotonic_fields)
        require(before == after and after['InvocationID'] == current['unit']['InvocationID'],
                'v3_latest_publisher_monotonic_race')
        unit = self.publication_alignment['selected']['unit']
        end = (datetime.strptime(unit['ExecMainExitTimestamp'], '%a %Y-%m-%d %H:%M:%S UTC')
               + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S UTC')
        journal = self.command(['/usr/bin/journalctl', '-u', PUBLISHER, '--since', unit['ExecMainStartTimestamp'],
                                '--until', end, '-o', 'json', '--no-pager'])
        current.update(unit_monotonic={key: after[key] for key in monotonic_fields if key != 'InvocationID'},
            selected_journal=[(row.get('_SYSTEMD_INVOCATION_ID'), row.get('MESSAGE'))
                              for row in map(json.loads, journal.splitlines())],
            unit_sources=self.recovery.publisher_unit_sources())
        self.check_publication_hold()
        return current

    def publisher_admission(self, conn, original, policy):
        """Reproduce the genuine prior row; separately authenticate latest deferral."""
        self.check_publication_hold()
        args, kwargs = captured_publisher_factory(self.availability_verifier,
            self.recovery.publisher_observation_connection(conn), original, policy)
        current = self.observe_held_publication()
        witness = held_publication_admission(self.publication_alignment, current, self.clock())
        selected = self.publication_alignment['selected']
        require(canonical_publisher_comparison(args[1]) == canonical_publisher_comparison(current['row'])
                and args[2] == {key: current['unit'][key] for key in PUBLISHER_JUDGE_FIELDS}
                and args[3] == current['journal'], 'v3_actual_factory_observation_race')
        selected_unit = {key: selected['unit'][key] for key in PUBLISHER_JUDGE_FIELDS}
        def final_check(actual, reproduced, genuine_unit, genuine_journal):
            # actual is the factory's real fresh callback result, never replaced.
            latest = self.observe_held_publication()
            require(latest == current, 'v3_latest_publisher_changed_during_reproduction')
            held_publication_admission(self.publication_alignment, latest, self.clock())
            require(canonical_publisher_comparison(actual.get('row')) == canonical_publisher_comparison(latest['row'])
                    == reproduced and actual.get('unit') == {key: latest['unit'][key] for key in PUBLISHER_JUDGE_FIELDS}
                    and actual.get('journal') == latest['journal']
                    and genuine_unit == selected_unit and genuine_journal == selected['journal'],
                    'v3_actual_final_observer_binding')
            return True
        adjudicator = publisher_final_adapter(self.availability_verifier, final_check)
        proof = adjudicator(args[0], current['row'], selected_unit, selected['journal'], **kwargs)
        proof['selected_previous_genuine_publication'] = selected
        proof['latest_invocation_assessment'] = witness
        proof['parent_hold'] = copy.deepcopy(self.publication_alignment['hold'])
        return proof

    def snapshot(self):
        acknowledgement = self.recovery.contract_from_bytes(
            self.read_source(self.source / self.recovery.DECL))['external_configuration_ack']
        before = current_external_boundary(self.recovery, acknowledgement)
        snapshot = self.old.snapshot(self.native, self.backup, self.storage)
        configuration_helpers({'need': require})['current_configuration_proof'](
            self.receipt['before']['configuration'], snapshot['configuration'], before['configuration_admission'])
        require(current_external_boundary(self.recovery, acknowledgement) == before,
                'v3_current_configuration_snapshot_race')
        self.current_co_tenant_boundary = before
        return snapshot

    def recheck_source_and_idle(self, receipt, operations, served):
        require(self.inside, 'v3_parent_hold_required')
        self.bind(self.contract, operations, served)
        units = self.old.service_boundary(self.native, self.storage, served, worker_required=True)
        boundary = copy.deepcopy(units)
        # Native state is augmented with measured invocation/reload properties;
        # these must have been retained by the qualified availability protocol.
        cgroups, ticks = {}, {}
        for unit, value in units.items():
            extra = self.command(['/usr/bin/systemctl', 'show', unit,
                '--property=InvocationID,NeedDaemonReload']).decode()
            value.update(dict(line.split('=', 1) for line in extra.splitlines() if '=' in line))
            pid = int(value['MainPID']); proc = Path('/proc') / str(pid)
            cgroups[unit] = (proc / 'cgroup').read_text()
            ticks[unit] = process_start((proc / 'stat').read_text())
            # release is an observed launcher proof, already authenticated by
            # service_boundary, rather than an invented systemd property.
            value['release'] = served
        env = protected(APP / '.env', 65536)
        proof = self.native.worker_configuration(env, served, boundary)
        packet = installed_auth_packet() if 'after-auth' in self.admission_raws else None
        admitted = installed_database_admission(self.contract, auth_packet=packet, operations=operations, served=served,
            availability_sha=sha(self.availability_raw), verifier_override=self.availability_verifier,
            native_modules=(self.old, self.backup), publisher_admission=self.publisher_admission)
        snapshot = self.snapshot()
        require(snapshot['database'] == admitted['current_database_fingerprint'], 'v3_idle_database_race')
        self.old.reaper_admission(lambda sql: self._readonly_query(sql), snapshot['files'])
        import httpx
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            public = client.get('https://app.quillmd.com/', headers={'Cookie': ''}).status_code
        self.recovery.direct_health(served)
        ingress = Path('/etc/nginx/sites-available/quillmd-email-preview')
        # The existing recovery capture carries the canonical ingress hash.
        expected = receipt['before']['configuration'][str(ingress)]['sha256']
        current = {'units': units, 'cgroups': cgroups, 'kernel_start_ticks': ticks,
            'worker_configuration_provenance': proof, 'pending_jobs': snapshot['database']['pending_jobs'],
            'held': snapshot['database']['held'], 'unresolved_reaper_paths': 0,
            'old_job_receipt_usage_unchanged': admitted['original_records_adjudicated'] is True,
            'private_origin': ORIGIN, 'public_status': public,
            'ingress_sha256': snapshot['configuration'][str(ingress)]['sha256'], 'expected_ingress_sha256': expected}
        # The source-derived database admission proves old job/receipt/usage rows;
        # its second collection immediately before a send is required below.
        live_identity(receipt, current, served)
        for unit, before in boundary.items():
            require(self.native.state(unit) == before, 'v3_native_unit_collection_race')
            extra = self.command(['/usr/bin/systemctl', 'show', unit,
                '--property=InvocationID,NeedDaemonReload']).decode()
            require(dict(line.split('=', 1) for line in extra.splitlines() if '=' in line)
                    == {key: units[unit][key] for key in ('InvocationID', 'NeedDaemonReload')},
                    'v3_native_invocation_collection_race')
        self.live = current
        return snapshot

    def _readonly_query(self, statement):
        import psycopg
        with psycopg.connect(**self.backup.source_options(APP, self.old.ROLES)) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            result = conn.execute(statement).fetchall()
            conn.rollback()
            return result

    def measured_completion(self, receipt):
        expected = receipt.get('completion_unit_provenance')
        require(isinstance(expected, dict) and set(expected) == set(UNITS), 'v3_measured_availability_invocations_required')
        properties = ('ActiveState,SubState,MainPID,FragmentPath,DropInPaths,UnitFileState,'
                      'ExecMainStartTimestampMonotonic,InvocationID,NeedDaemonReload')
        current = {}
        for unit in UNITS:
            raw = self.command(['/usr/bin/systemctl', 'show', unit, '--property=' + properties]).decode()
            value = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
            require(value == expected[unit], 'v3_independent_completion_invocation_drift')
            legacy = {key: value[key] for key in receipt['units_after'][unit]}
            require(legacy == receipt['units_after'][unit] == self.native.state(unit), 'v3_independent_completion_legacy_projection')
            proc = Path('/proc') / value['MainPID']
            exact_cgroup((proc / 'cgroup').read_text(), unit)
            ticks = process_start((proc / 'stat').read_text())
            require(abs(ticks * 1000000 / os.sysconf('SC_CLK_TCK') - int(value['ExecMainStartTimestampMonotonic'])) < 1000000,
                    'v3_independent_completion_kernel_start')
            current[unit] = value
        require(sha(protected(APP / '.env', 65536)) == receipt['environment_after_sha256'],
                'v3_independent_completion_environment_drift')
        self.bind(self.contract, self.operations, self.served)
        return current

    def admit(self, phase, contract, receipt, operations, served, auth=None):
        require(self.inside and phase in ('before-auth', 'after-auth'), 'v3_parent_admission_hold')
        started = datetime.now(timezone.utc).isoformat()
        packet = installed_auth_packet() if phase == 'after-auth' else None
        admission = installed_database_admission(contract, auth_packet=packet, operations=operations, served=served,
            availability_sha=sha(self.availability_raw), verifier_override=self.availability_verifier,
            native_modules=(self.old, self.backup), publisher_admission=self.publisher_admission)
        require(isinstance(self.publication_alignment, dict)
                and admission['allowed_deltas']['publisher']['current_full_row']
                    == self.publication_alignment['selected']['row'], 'v3_admitted_selected_publication')
        snapshot = self.snapshot()
        preserved_snapshot(receipt['before'], snapshot, admission['current_database_fingerprint'],
                           self.current_co_tenant_boundary['configuration_admission'])
        worker = receipt['units_after'][UNITS[2]]
        report = {'format': 3, 'complete': True, 'phase': phase, 'operations_revision': operations,
            'served_revision': served, 'availability_receipt_sha256': sha(self.availability_raw),
            'original_activation': str(ORIGINAL), 'original_failed_sha256': self.common.ORIGINAL_SHA,
            'original_backup_manifest_cipher_sha256': self.common.BACKUP_SHA, 'original_records_adjudicated': True,
            'provider_calls': 0, 'database_writes_by_verifier': 0, 'current_snapshot': snapshot,
            'current_database_fingerprint': admission['current_database_fingerprint'],
            'allowed_deltas': admission['allowed_deltas'], 'service_identities': receipt['units_after'],
            'co_tenant_preservation_admission': self.current_co_tenant_boundary['configuration_admission'],
            'worker_running_idle': {'unit': UNITS[2], 'pid': int(worker['MainPID']),
                'start_monotonic_usec': worker['ExecMainStartTimestampMonotonic'],
                'pending_jobs': 0, 'held_reservations': 0, 'unresolved_reaper_paths': 0,
                'existing_job_receipt_usage_rows_unchanged': True}, 'started_at': started,
            'finished_at': datetime.now(timezone.utc).isoformat()}
        raw = encode(report) + b'\n'
        self.admission_raws[phase] = raw
        self.common.admission(raw, phase, self.authority(), receipt, operations, served, sha(self.availability_raw))
        if phase == 'after-auth':
            write_new(PREPARATION / 'admission-after-auth.json', raw)
            self.common.auth_sequence(packet['normal_raw'], json.loads(self.admission_raws['before-auth']), report,
                                      operations, served, sha(self.availability_raw))
        return report

    def create_exclusive_preparation(self, operations, served, before):
        require(self.inside and not os.path.lexists(PREPARATION), 'v3_exclusive_preparation')
        PREPARATION.mkdir(mode=0o700)
        write_new(PREPARATION / 'publisher-alignment.json', self.publication_alignment)
        write_new(PREPARATION / 'admission-before-auth.json', self.admission_raws['before-auth'])
        write_new(PREPARATION / 'parent.json', {'format': 3, 'operations_revision': operations,
            'served_revision': served, 'original_capture_adopted': False, 'provider_calls': 0,
            'authentication_submissions': 0})

    def phase_context(self, phase, deadline):
        require(self.inside and phase in PARENT_PHASES, 'v3_parent_phase_scope')
        value = {'format': 3, 'phase': phase, 'operations_revision': self.operations, 'served_revision': self.served,
            'parent_pid': os.getpid(), 'parent_uid': os.getuid(),
            'parent_start_ticks': process_start(Path('/proc/self/stat').read_text()),
            'deadline_monotonic': deadline, 'locks': copy.deepcopy(self.lock_rows),
            'publisher_alignment_sha256': sha(encode(self.publication_alignment) + b'\n'),
            'authority': self.authority(), 'admission_sha256': {k: sha(v) for k, v in self.admission_raws.items()}}
        raw = encode(value) + b'\n'
        write_new(PREPARATION / ('parent-phase-' + phase + '.json'), raw)
        return sha(raw)

    def child(self, phase, operations, served, deadline):
        if phase == 'normal-auth': ENTRY_OBSERVATIONS['authentication_possible'] = True
        if phase == 'browser': ENTRY_OBSERVATIONS['provider_possible'] = True
        context_sha = self.phase_context(phase, deadline)
        raw = self.read_source(self.source / SELF)
        require(raw == self.git(self.source, 'show', operations + ':' + SELF), 'v3_child_checked_source')
        mode = '--verify' if phase == 'verify' else '--dispatch-' + phase
        with sealed_buffer(raw) as fd:
            return child_process(checked_python_argv(self.source, fd, raw, [mode, '--operations-revision', operations,
                '--served-revision', served, '--parent-context-sha256', context_sha]), self.source,
                PREPARATION, phase, deadline, ruled=False, pass_fds=(fd,),
                environment=child_environment(self.environment))

    def normal_auth_evidence(self):
        return installed_auth_packet()

    def write_attempt(self, operations, served, before, after):
        require(self.inside, 'v3_parent_hold_required')
        write_new(ATTEMPT, {'format': 3, 'attempt': 1, 'operations_revision': operations, 'served_revision': served,
            'before_auth_sha256': sha(self.admission_raws['before-auth']),
            'after_auth_sha256': sha(self.admission_raws['after-auth']), 'provider_retries': 0})

    def independent_report(self):
        return json.loads(protected(REPORT))

    def write_complete(self, report):
        write_new(CAMPAIGN / 'complete.json', {'format': 3, 'complete': True,
            'operations_revision': self.operations, 'served_revision': self.served,
            'independent_report_sha256': sha(protected(REPORT)), 'independent_report': str(REPORT),
            'availability_preserved': True, 'provider_retries': 0})

    def write_stop(self, reason):
        target = CAMPAIGN if os.path.lexists(CAMPAIGN) else PREPARATION
        write_new(target / 'STOP.json', {'format': 3, 'complete': False, 'reason': reason,
            'operations_revision': self.operations, 'served_revision': self.served,
            'unknown_outcome_blocks_replay': True, 'records_and_availability_left_in_place': True,
            'automatic_retries': False, 'no_rollback_attempted': True})


def installed_contract(host):
    raw = host.read_source(host.source / DECL)
    contract = declaration_contract(raw)
    require(contract.get('protocol_qualified') is True and all(contract.get(name) is True for name in (
        'execution_qualified', 'native_authorization_protocol_qualified', 'fixed_child_protocol_qualified')),
        'v3_declaration_source_qualification_required')
    require(contract.get('post_restoration_preservation') == {
                'protocol': 'post-restoration-exact-owner-preservation-v1',
                'proposal': {'path': str(POST_RESTORE_PROPOSAL), 'sha256': POST_RESTORE_PROPOSAL_SHA},
                'owner_reply': {'path': str(POST_RESTORE_OWNER_REPLY), 'sha256': POST_RESTORE_OWNER_REPLY_SHA}}
            and isinstance(POST_RESTORE_OWNER_REPLY_SHA, str)
            and re.fullmatch('[a-f0-9]{64}', POST_RESTORE_OWNER_REPLY_SHA),
            'v3_current_configuration_declared_owner_binding')
    expected_paths = {'admin_directory': ADMIN, 'availability_directory': AVAILABILITY,
                      'preparation_directory': PREPARATION, 'campaign_directory': CAMPAIGN, 'attempt_marker': ATTEMPT}
    require(all(contract.get(name) == str(path) for name, path in expected_paths.items())
            and contract.get('outer_ceiling_seconds') == 1680, 'v3_fixed_native_paths_and_ceiling')
    for name, expected in FIXTURE_PINS.items():
        require(re.findall(('^' + name + ': ([a-f0-9]{64})$').encode(), raw, re.M) == [expected.encode()],
                'v3_committed_frozen_input_pin')
    return raw, contract


def admit_parent_child(host, phase, context_sha):
    require(phase in PARENT_PHASES and re.fullmatch('[a-f0-9]{64}', context_sha or ''),
            'v3_parent_context_hash_required')
    raw = protected(PREPARATION / ('parent-phase-' + phase + '.json'))
    require(sha(raw) == context_sha, 'v3_parent_context_changed')
    context = json.loads(raw)
    parent_phase_admission(context, phase, host.operations, host.served, source=host.source)
    alignment_raw = protected(PREPARATION / 'publisher-alignment.json')
    require(sha(alignment_raw) == context.get('publisher_alignment_sha256'),
            'v3_parent_publication_alignment_hash')
    host.publication_alignment = json.loads(alignment_raw)
    host.parent_lock_context = context
    require(0 < context['deadline_monotonic'] - host.clock() <= (180 if phase == 'normal-auth' else 1200),
            'v3_exact_phase_ceiling')
    phases = ('before-auth',) if phase == 'normal-auth' else ('before-auth', 'after-auth')
    host.admission_raws = {value: protected(PREPARATION / ('admission-' + value + '.json')) for value in phases}
    require(context.get('admission_sha256') == {key: sha(value) for key, value in host.admission_raws.items()},
            'v3_parent_admission_hashes')
    require(context.get('authority') == host.authority(), 'v3_derived_parent_authority_changed')
    receipt = host.authenticate_availability(host.contract, host.operations, host.served)
    for value, report_raw in host.admission_raws.items():
        host.common.admission(report_raw, value, host.authority(), receipt, host.operations, host.served,
                              sha(host.availability_raw))
    if phase != 'normal-auth':
        attempt = json.loads(protected(ATTEMPT))
        require(attempt.get('format') == 3 and attempt.get('attempt') == 1
                and attempt.get('operations_revision') == host.operations and attempt.get('served_revision') == host.served
                and attempt.get('before_auth_sha256') == sha(host.admission_raws['before-auth'])
                and attempt.get('after_auth_sha256') == sha(host.admission_raws['after-auth'])
                and attempt.get('provider_retries') == 0, 'v3_single_clinical_attempt_binding')
    else:
        require(not any(os.path.lexists(path) for path in (ADMIN, CAMPAIGN, ATTEMPT)), 'v3_no_authentication_reuse')
    if phase == 'browser':
        require(not os.path.lexists(CAMPAIGN), 'v3_no_campaign_reuse')
    # The existing parent owns exclusions. This flag does not acquire or claim
    # local locks: the independent kernel observations above establish its hold.
    host.inside = True
    if phase != 'verify':
        host.recheck_source_and_idle(receipt, host.operations, host.served)
    parent_phase_admission(context, phase, host.operations, host.served, source=host.source)
    return context


def dispatch_javascript(host, phase, context_sha, declaration):
    execution_gate()
    context = admit_parent_child(host, phase, context_sha)
    fd = globals().get('CHECKED_SOURCE_FD')
    require(type(fd) is int and fd >= 3, 'v3_dispatch_checked_source_descriptor')
    raw = os.pread(fd, 2 * 1024 * 1024, 0)
    require(raw == host.git(host.source, 'show', host.operations + ':' + SELF), 'v3_dispatch_checked_git_source')
    args = ['--child-check-' + phase, '--operations-revision', host.operations,
            '--served-revision', host.served, '--parent-context-sha256', context_sha]
    check = {'argv': checked_python_argv(host.source, 3, raw, args)[1:], 'source_fd': fd}
    javascript = javascript_adapter(host.blobs, phase, declaration, host.authority(), check)
    # Replace this one process in the parent's owned session. A new independent
    # child group would escape its timeout/unknown-outcome drain.
    with sealed_buffer(javascript) as script:
        os.dup2(script, 0)
        os.set_inheritable(fd, True)
        env = child_environment(host.environment)
        os.execve('/usr/bin/node', ['/usr/bin/node', '--input-type=module', '-', '--execute-v3',
            host.operations, host.served, str(AVAILABILITY)], env)


def dispatch_verification(host, context_sha):
    execution_gate()
    context = admit_parent_child(host, 'verify', context_sha)
    verifier = verifier_adapter(host.blobs['verify_installed_acceptance_v3.py'], host.common,
                                host.authority(), host.availability_verifier, host.measured_completion,
                                host.publisher_admission)
    verifier.verify(types.SimpleNamespace(progress=str(CAMPAIGN / 'progress.json'), output=str(REPORT)))
    report = json.loads(protected(REPORT))
    require(report.get('complete') is True and report.get('operations_revision') == host.operations
            and report.get('served_revision') == host.served
            and report.get('provider_calls') == report.get('database_writes') == 0,
            'v3_independent_native_verification')
    parent_phase_admission(context, 'verify', host.operations, host.served, source=host.source)
    deadline_remaining(context['deadline_monotonic'], host.clock)
    return report


def plan():
    return {'format': 3, 'complete': False, 'preparation_only': True, 'installed_state_accessed': False,
            'provider_calls': 0, 'authentication_submissions': 0, 'database_writes': 0,
            'execution_qualified': EXECUTION_QUALIFIED,
            'native_authorization_protocol_qualified': NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED,
            'fixed_child_protocol_qualified': FIXED_CHILD_PROTOCOL_QUALIFIED,
            'origin': ORIGIN, 'source_base': M6, 'declaration': DECL, 'source_paths': sorted(ALLOWED),
            'dependency_sha256': DEPENDENCIES, 'operations_revision': None, 'served_revision': None,
            'prospective_served_revision': M6,
            'operations_revision_policy': OPERATIONS_REVISION_POLICY,
            'maximum_generations': 5, 'maximum_transcriptions': 1, 'maximum_provider_exposure': '0.70',
            'maximum_authentication_seconds': 180, 'shared_browser_verifier_seconds': 1200,
            'provider_retries': 0, 'unknown_outcome_stops': True, 'real_runner_adapter_available': True,
            'post_restoration_current_boundary': {'proposal_path': str(POST_RESTORE_PROPOSAL),
                'proposal_sha256': POST_RESTORE_PROPOSAL_SHA,
                'owner_reply_source_binding_present': isinstance(POST_RESTORE_OWNER_REPLY_SHA, str),
                'historical_deployment_authorization_verified': False},
            'remaining_dependencies': ['exact separately bound owner reply for the four post-restoration differences',
                'exact merged operations and normal-descendant citations',
                'fresh bounded native source, recovery and preservation admissions',
                'one authorized normal-MFA and synthetic workflow campaign'],
            'normal_443_is_separate_qualification': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    for name in ('execute', 'preflight', 'admit-before-auth', 'admit-after-auth', 'verify',
                 'dispatch-normal-auth', 'dispatch-browser', 'child-check-normal-auth', 'child-check-browser'):
        mode.add_argument('--' + name, action='store_true')
    parser.add_argument('--operations-revision')
    parser.add_argument('--served-revision')
    parser.add_argument('--parent-context-sha256')
    args = parser.parse_args(argv)
    modes = ('execute', 'preflight', 'admit_before_auth', 'admit_after_auth', 'verify',
             'dispatch_normal_auth', 'dispatch_browser', 'child_check_normal_auth', 'child_check_browser')
    if any(getattr(args, name) for name in modes):
        execution_gate()
        ENTRY_OBSERVATIONS['installed_state_accessed'] = True
        operations, served = full_revision(args.operations_revision), full_revision(args.served_revision)
        host = InstalledHost()
        host.own_hold_mode = ('--execute' if args.execute else '--preflight' if args.preflight
                             else '--admit-before-auth' if args.admit_before_auth else None)
        declaration, contract = installed_contract(host)
        host.bind(contract, operations, served)
        host.authenticate_dependencies()
        if args.execute:
            report = protocol_pipeline(host, contract, operations, served)
        elif args.dispatch_normal_auth or args.dispatch_browser:
            return dispatch_javascript(host, 'normal-auth' if args.dispatch_normal_auth else 'browser',
                                       args.parent_context_sha256, declaration)
        elif args.verify:
            report = dispatch_verification(host, args.parent_context_sha256)
        elif args.child_check_normal_auth or args.child_check_browser:
            phase = 'normal-auth' if args.child_check_normal_auth else 'browser'
            admit_parent_child(host, phase, args.parent_context_sha256)
            report = {'complete': True, 'phase': phase, 'parent_hold_verified': True}
        else:
            # Before-auth preflight produces no directory, marker, session or
            # admission file. After-auth is exclusively a live parent child.
            require(not args.admit_after_auth, 'v3_after_auth_only_inside_fixed_parent_pipeline')
            receipt = host.authenticate_availability(contract, operations, served)
            require(host.fresh_paths_absent(), 'v3_exclusive_new_paths_required')
            with host.exclusions(operations, host.clock() + 600):
                host.recheck_source_and_idle(receipt, operations, served)
                report = host.admit('before-auth', contract, receipt, operations, served)
            report = {'complete': True, 'read_only_preflight': True,
                      'admission_sha256': sha(encode(report) + b'\n'), 'provider_calls': 0,
                      'authentication_submissions': 0, 'database_writes': 0}
        print(json.dumps(report, sort_keys=True, default=str))
        return 0
    print(json.dumps(plan(), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps(failure_summary(error)), flush=True)
        raise SystemExit(2)
