#!/usr/bin/env python3
"""Generic machinery for an owner-declared, money-bounded provider campaign (no Django in this module).

Ported from the reviewed WM narrative campaign runner (feat/wm-narrative, ops/wm_narrative_campaign.py): `write_new`,
the O_EXCL ledger, `exposure`, admission, `hold_lock`, `declared`, `recover_interrupted`, `leaked`, the request capture
and the scrubbed environment. ONE PART IS DELIBERATELY NOT PORTED: that runner read the provider key out of the
application's protected configuration file. A campaign here takes the key ONLY from the declaration's own
`credential_file`, and refuses any path that is, or sits under, a `.env` file or directory BEFORE anything is opened.

What each piece guarantees, stated so a reader can see how it would fail:

  declared()          The declaration is TRACKED, COMMITTED and UNMODIFIED (the index, the working tree and the committed
                      blob all agree, so `--assume-unchanged` cannot hide an edit), has exactly one authorization line
                      and an `owner_words:` line, and carries no revocation. Every number the runner enforces is parsed
                      from it; nothing is a second copy in code. Its commit time is printed, so the transcript shows the
                      authority existed before the act.
  Ledger              Write-once JSON records (temporary file + link: a kill leaves no record or a whole one), gapless
                      attempt numbers, ONE runner at a time (flock), the attempt written and synced BEFORE any send and
                      its outcome after. An attempt with no outcome is never forgotten: `recover_interrupted` records it
                      as `interrupted_unknown` in a NEW outcome record and it counts at its maximum. Stage decisions are
                      numbered — failed-1, reopened-1, failed-2 … — and a sequence out of order is refused; a pass is
                      the one unnumbered stage-<id>-passed.json (the form the live model_check record already has).
  exposure()          Known provider usage is priced at the rates the ledger PINNED (Campaign.pinned_terms); anything not
                      known — a completed outcome that does not report input or output tokens included — is counted at
                      the attempt's maximum x 1.1, never as zero.
  Campaign.pinned_terms()
                      The rates, model, thinking, effort, inference geography and pricing versions in force when the
                      ledger's FIRST attempt was written (the terms it records; a legacy first attempt: those of the
                      declaration blob it names). Admission and reopening refuse while the current declaration states
                      any other; an edited declaration never changes what is admitted or how anything is costed.
  Campaign.limits()   The limits IN FORCE: the tightest of the current declaration's and those each ledger attempt
                      recorded (or, for an attempt from before attempts recorded them, those of the declaration it names
                      by sha256). Raising a limit by editing the declaration never admits more.
  Campaign.admit()    Refuses before the request is built: a prerequisite stage not passed, a stage already passed or
                      failed (and not reopened), an attempt without an outcome, the stage or total limit in force, the
                      stage's request count; a reopened stage admits only a runner that contains the repair.
  Campaign.reopen()   The ONLY way a failed stage is admitted again: a committed, unmodified diagnosis naming the failed
                      attempts and the repair commit, a runner that is not a failed one and contains the repair, a
                      runner or engine file that differs from every failed attempt's recorded hashes, a repair commit
                      that touches one, and money and a request left under the stage's OWN limits. Writes
                      stage-<id>-reopened-<n>.json.
  load_credential()   The declared file only: absolute, no environment-file name (`.env`, `*.env`, `.env.*`,
                      `*.env.*`) anywhere in its path or its resolved path, no symbolic link at ANY component, one name
                      only (no hard link), a regular 0600 file owned by this account, exactly one non-empty line —
                      all checked on the opened descriptor BEFORE any read. The key is returned, never printed.
  scrubbed_environment()
                      The process that makes requests inherits NOTHING: every name the SDK or httpx could take a
                      credential, endpoint, header, profile, federation or proxy from is absent by construction, and
                      `ANTHROPIC_CONFIG_DIR` points at a fresh empty directory.
  install_request_capture()
                      The exact outbound request (method, URL, JSON body, headers without x-api-key/authorization) is
                      written to the current attempt's evidence BEFORE it is sent; a request outside an attempt, a second
                      request inside one, a non-Anthropic URL, a retrying client or a credential-provider client is
                      refused and never sent. The response is retained AS RECEIVED (status, headers without cookies or
                      credentials, the exact body bytes) the moment the SDK has it — before the SDK parses it and before
                      the product settles, refuses or stores anything — so a billed response the product cannot settle is
                      never lost (refutation RAW-RESPONSE-LOST-200). `received_response` reads it back.
  leaked()            Every retained file (zip and gzip members included, nested to depth 4 within a byte bound) is
                      searched for the key and the sk-ant- shape. It FAILS CLOSED: a directory it cannot list or enter, a
                      file it cannot read or decode, an archive past its bounds, a link or special file, an
                      environment-named entry (never opened), a root under an environment-named directory and any
                      unexpected exception raise `Unscannable` — a stop, never 'no leak'.
  classify_case()     The per-case verdict for the mapping and ordinary_notes stages: unsafe findings and contract/money
                      failures stop the stage; held / missing / refused answers are usefulness, recorded per field.
"""
import dataclasses
import errno
import fcntl
import gzip
import hashlib
import hmac
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

RUNNER = Path(__file__).resolve()
REBUILD = RUNNER.parents[1]
#: The one live place for this campaign's ledger and evidence (the declaration's own credential file lives under it).
LIVE_ROOT = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign')
#: US-only inference is billed 1.1x on Claude 4.6+; the workspace default geography cannot be read without an Admin
#: credential, so every unknown is counted with it (the declaration's "Admission, per request").
GEO_MARGIN = Decimal('1.1')
KEY_SHAPE = re.compile(rb'sk-ant-[A-Za-z0-9_\-]{8,}')
SCAN_CHUNK = 8 * 1024 * 1024


class Refused(Exception):
    """The campaign will not start, or will not make the next attempt. Nothing further is sent."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    """A Decimal amount from a Decimal or a string only: a float is binary arithmetic and never money here."""
    require(isinstance(value, (Decimal, str)) and not isinstance(value, bool), f'Money must be a Decimal or a string, not {type(value).__name__}.')
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise Refused('Money is not a number.') from None
    require(amount.is_finite(), 'Money must be finite.')
    return amount


# ── private files ────────────────────────────────────────────────────────────────────────────────────────────────

def write_new(path, document, raw=False):
    """Written once and never rewritten, and published whole: the bytes go to a private temporary file (O_EXCL, synced),
    which is then hard-linked to its name — a link fails if the name exists, and a kill leaves either no record or a
    complete one. `raw`: `document` is written as it is (str or bytes), otherwise as sorted JSON."""
    path = Path(path)
    if raw:
        data = document.encode('utf-8') if isinstance(document, str) else bytes(document)
    else:
        data = (json.dumps(document, indent=2, sort_keys=True, default=str) + '\n').encode('utf-8')
    temporary = path.with_name(f'.partial-{os.getpid()}-{path.name}')
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def private_directory(path):
    """A real directory, owned by this account, mode 0700 (created so if missing)."""
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode), f'{path} is not a real directory.')
    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, f'{path} must be 0700 and owned by this account.')
    return path


def read_private(path, limit=65536):
    """A regular, singly-linked, owner-only file of bounded size, opened without following a link. (Never a `.env`.)"""
    refuse_env_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) & 0o077 == 0 and info.st_size <= limit,
                f'{path} is not a private file of at most {limit} bytes.')
        return os.read(fd, limit + 1)
    finally:
        os.close(fd)


def hold_lock(path):
    """An exclusive lock for this process's whole life (released by the kernel on any exit)."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise Refused('Another runner holds this campaign.') from None
    return fd


# ── the declaration ──────────────────────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Stage:
    id: str
    limit: Decimal
    max_requests: object            # int, or None when the declaration names no request count for the stage
    requires: object                # the id of the stage whose PASS is required, or None


@dataclasses.dataclass(frozen=True)
class Rates:
    """USD per million tokens, kept as the declaration spells them: the application hashes the literal strings into its
    pricing version, so '0.20' and '0.2' are different prices to it."""
    input: str
    output: str
    cached: str

    def decimals(self):
        return {'input': Decimal(self.input), 'output': Decimal(self.output), 'cached': Decimal(self.cached)}

    def as_dict(self):
        return {'input': self.input, 'output': self.output, 'cached': self.cached}


STAGE_ID = re.compile(r'[a-z][a-z0-9_]*')
FULL_COMMIT = re.compile(r'[0-9a-f]{40}')


@dataclasses.dataclass(frozen=True)
class StageLimit:
    id: str
    limit: Decimal
    max_requests: object            # int, or None when no request count applies
    requires: tuple                 # the stage ids whose PASS is required (sorted; empty when none)


@dataclasses.dataclass(frozen=True)
class Limits:
    """The money and request limits admission enforces. A new attempt records the limits in force when it was written
    (`record()`); admission then uses the TIGHTEST of the current declaration's and every recorded set, so a limit
    raised by editing the declaration never admits more than was in force when the ledger's attempts were written."""
    total: Decimal
    stages: tuple                   # StageLimit, in declaration order

    def stage(self, stage_id):
        found = [s for s in self.stages if s.id == stage_id]
        require(len(found) == 1, f'Stage {stage_id} has no limit in force (the limits the ledger pinned do not name it).')
        return found[0]

    def record(self):
        return {'total_limit_provider_usd': format(self.total, 'f'),
                'stages': {s.id: {'limit_provider_usd': format(s.limit, 'f'), 'max_requests': s.max_requests,
                                  'requires': list(s.requires)} for s in self.stages}}

    @staticmethod
    def from_record(record, what):
        """Recorded limits, read strictly: anything malformed is refused, never read as 'no limit'."""
        def valid(condition):
            require(condition, f'{what} records limits that cannot be read; the limits in force cannot be established.')
        valid(isinstance(record, dict) and set(record) == {'total_limit_provider_usd', 'stages'}
              and isinstance(record['total_limit_provider_usd'], str) and isinstance(record['stages'], dict))
        total = money(record['total_limit_provider_usd'])
        stages = []
        for stage_id, entry in record['stages'].items():
            valid(isinstance(stage_id, str) and STAGE_ID.fullmatch(stage_id) and isinstance(entry, dict)
                  and set(entry) == {'limit_provider_usd', 'max_requests', 'requires'}
                  and isinstance(entry['limit_provider_usd'], str)
                  and (entry['max_requests'] is None or type(entry['max_requests']) is int)
                  and isinstance(entry['requires'], list)
                  and all(isinstance(p, str) and STAGE_ID.fullmatch(p) for p in entry['requires']))
            stages.append(StageLimit(stage_id, money(entry['limit_provider_usd']), entry['max_requests'],
                                     tuple(sorted(set(entry['requires'])))))
        valid(total >= 0 and all(s.limit >= 0 and (s.max_requests is None or s.max_requests >= 0) for s in stages))
        return Limits(total, tuple(stages))

    def tightest(self, other):
        """Per value, the lower of the two; a stage only one of them names has no limit in force; prerequisites add up."""
        theirs = {s.id: s for s in other.stages}
        stages = []
        for mine in self.stages:
            if mine.id not in theirs:
                continue
            other_stage = theirs[mine.id]
            counts = [n for n in (mine.max_requests, other_stage.max_requests) if n is not None]
            stages.append(StageLimit(mine.id, min(mine.limit, other_stage.limit), min(counts) if counts else None,
                                     tuple(sorted(set(mine.requires) | set(other_stage.requires)))))
        return Limits(min(self.total, other.total), tuple(stages))


PRICING_VERSION = re.compile(r'configured-v1:[0-9a-f]{64}')


@dataclasses.dataclass(frozen=True)
class Terms:
    """What a request is admitted at and every outcome is costed at: the declared rates (as the declaration spells them),
    model, thinking, effort, inference geography ('' when unset) and every pricing version. A new attempt records the
    terms in force (`record()`); the ledger's FIRST attempt pins them for the whole campaign (Campaign.pinned_terms)."""
    rates: Rates
    model: str
    thinking: str
    effort: str
    inference_geo: str
    pricing_versions: tuple         # ((name, 'configured-v1:…'), …), sorted by name

    def record(self):
        return {'rates': self.rates.as_dict(), 'model': self.model, 'thinking': self.thinking, 'effort': self.effort,
                'inference_geo': self.inference_geo, 'pricing_versions': dict(self.pricing_versions)}

    @staticmethod
    def from_record(record, what):
        """Recorded terms, read strictly: anything malformed is refused, never read as matching."""
        def valid(condition):
            require(condition, f'{what} records terms that cannot be read; the terms in force cannot be established.')
        names = ('rates', 'model', 'thinking', 'effort', 'inference_geo', 'pricing_versions')
        valid(isinstance(record, dict) and set(record) == set(names))
        rates, versions = record['rates'], record['pricing_versions']
        valid(isinstance(rates, dict) and set(rates) == {'input', 'output', 'cached'}
              and all(type(value) is str for value in rates.values())
              and all(type(record[name]) is str for name in ('model', 'thinking', 'effort', 'inference_geo'))
              and isinstance(versions, dict) and all(isinstance(name, str) and STAGE_ID.fullmatch(name)
                                                     and isinstance(value, str) and PRICING_VERSION.fullmatch(value)
                                                     for name, value in versions.items()))
        return Terms(Rates(rates['input'], rates['output'], rates['cached']), record['model'], record['thinking'],
                     record['effort'], record['inference_geo'], tuple(sorted(versions.items())))

    def differences(self, other):
        """The names of the terms in which `other` differs from these."""
        return [name for name in ('rates', 'model', 'thinking', 'effort', 'inference_geo', 'pricing_versions')
                if getattr(self, name) != getattr(other, name)]


@dataclasses.dataclass(frozen=True)
class Declaration:
    path: str
    sha256: str
    commit: str
    commit_time: str
    campaign: str
    authority_id: str
    authorization: str
    owner_words: str
    total_limit: Decimal
    stages: tuple
    transfers: bool
    provider: str
    model: str
    rates: Rates
    thinking: str
    effort: str
    inference_geo: str              # '' when the declaration says `unset`
    pricing_versions: tuple         # ((stage or variant, 'configured-v1:…'), …)
    credential_file: str
    repository: str = ''            # the checkout the declaration was verified in ('' when unknown)

    def stage(self, stage_id):
        found = [s for s in self.stages if s.id == stage_id]
        require(len(found) == 1, f'The declaration names no stage {stage_id!r}.')
        return found[0]

    def pricing_version(self, key):
        found = [value for name, value in self.pricing_versions if name == key]
        require(len(found) == 1, f'The declaration names no pricing version for {key!r}.')
        return found[0]

    def limits(self):
        return Limits(self.total_limit, tuple(StageLimit(s.id, s.limit, s.max_requests, (s.requires,) if s.requires else ())
                                              for s in self.stages))

    def terms(self):
        return Terms(self.rates, self.model, self.thinking, self.effort, self.inference_geo,
                     tuple(sorted(self.pricing_versions)))


#: Every line that READS as an authorization — any word starting authoriz/authoris (authorization, authorised,
#: Authorizations …), in any case or markdown decoration (a heading, a quote, a list item, a table row): exactly one may
#: exist, and it must be exactly the one form below.
AUTHORIZATION_LINE = re.compile(r'^[ \t>*_#+|0-9.)-]*authori[sz].*$', re.M | re.I)
AUTHORIZATION = re.compile(r'authorization: owner (\d{4}-\d{2}-\d{2}) approved \S(?:.*\S)? at the stated limits')
REVOCATION = re.compile(r'revok|rescind|withdr[ae]w|cancel|suspend|retract|annul', re.I)
#: The ONLY revocation-like wording the committed declaration carries, and why it is not one: it is the owner's
#: recommended hygiene for a dedicated API key (revoke the KEY when the campaign ends), not a revocation of the
#: authority. Matched as the whole sentence, whitespace-normalized across line wrapping, at most once; any other
#: revocation word anywhere — a heading, a `revoked:` line, a second copy of this sentence — refuses.
KNOWN_NON_REVOCATIONS = (
    'Recommended to the owner (not required by this declaration): a dedicated API key in a workspace whose '
    'provider-side spend limit is at most the remaining campaign total, revoked when the campaign ends.',
)
NUMBER = r'\d+(?:\.\d+)?'
STAGE_LINE = re.compile(rf'^stage: ([a-z][a-z0-9_]*) limit_provider_usd ({NUMBER})(?: max_requests (\d+))? requires (\S+)[ \t]*$', re.M)
PRICING_LINE = re.compile(r'^pricing_version ([a-z][a-z0-9_]*): (configured-v1:[0-9a-f]{64})[ \t]*$', re.M)


def _one(text, pattern, what, document='declaration'):
    found = re.findall(pattern, text, re.M)
    require(len(found) == 1, f'The {document} must state exactly one `{what}` line (found {len(found)}).')
    return found[0]


def _git(root, *args, check=True):
    result = subprocess.run(['git', '--literal-pathspecs', '-C', str(root), *args], capture_output=True)
    if check:
        require(result.returncode == 0, f'git {args[0]} failed on the declaration\'s checkout.')
    return result


def commit_exists(root, commit):
    return bool(FULL_COMMIT.fullmatch(str(commit))) and _git(root, 'cat-file', '-e', f'{commit}^{{commit}}',
                                                              check=False).returncode == 0


def is_ancestor(root, ancestor, descendant):
    """Whether `ancestor` is `descendant` or one of its ancestors. Refuses when git cannot tell (an unknown commit)."""
    require(FULL_COMMIT.fullmatch(str(ancestor)) and FULL_COMMIT.fullmatch(str(descendant)),
            'A commit is named by its full 40-character id.')
    result = _git(root, 'merge-base', '--is-ancestor', ancestor, descendant, check=False)
    require(result.returncode in (0, 1), f'git cannot tell whether {ancestor} is contained in {descendant}.')
    return result.returncode == 0


def blob_sha256(root, commit, relative):
    """The sha256 of `relative` as committed at `commit`, or None when the commit does not hold it."""
    blob = _git(root, 'cat-file', 'blob', f'{commit}:{relative}', check=False)
    return hashlib.sha256(blob.stdout).hexdigest() if blob.returncode == 0 else None


def files_changed_by(root, commit):
    """The repository-relative paths `commit` changes against its first parent. Refuses a commit without a parent."""
    require(FULL_COMMIT.fullmatch(str(commit)) and commit_exists(root, f'{commit}'), f'{commit} is not a commit here.')
    require(_git(root, 'rev-parse', '--verify', '--quiet', f'{commit}^', check=False).returncode == 0,
            f'The commit {commit} has no parent; what it changes cannot be shown.')
    return _git(root, 'diff', '--name-only', '-z', f'{commit}^', commit).stdout.decode().split('\0')[:-1]


def committed_file(path, root, document):
    """(bytes, commit, commit time, path relative to `root`) of a file that is TRACKED, COMMITTED and UNMODIFIED in the
    checkout `root`: the index, the working tree and the committed blob all agree, so `--assume-unchanged` cannot hide
    an edit. `path` is already resolved and inside `root`."""
    relative = str(path.relative_to(root))
    tracked = _git(root, 'ls-files', '--error-unmatch', '--', relative, check=False).returncode == 0
    unmodified = _git(root, 'diff', '--quiet', 'HEAD', '--', relative, check=False).returncode == 0
    unstaged = _git(root, 'diff', '--quiet', '--', relative, check=False).returncode == 0
    nothing_staged = _git(root, 'diff', '--cached', '--quiet', '--', relative, check=False).returncode == 0
    require(tracked and unmodified and unstaged and nothing_staged,
            f'The {document} must be tracked, committed and unmodified.')
    data = path.read_bytes()
    # (the committed blob itself, byte for byte: `git update-index --assume-unchanged` makes every diff above report
    # clean over an edited file)
    committed = _git(root, 'cat-file', 'blob', f'HEAD:{relative}', check=False)
    require(committed.returncode == 0 and committed.stdout == data, f'The {document} differs from its committed blob.')
    log = _git(root, 'log', '-1', '--format=%H%x00%cI', 'HEAD', '--', relative).stdout.decode().strip()
    require('\x00' in log, f'The {document} has no commit.')
    commit, commit_time = log.split('\x00', 1)
    return data, commit, commit_time, relative


def _limits_from_text(text):
    """(total, (Stage, …)) as the declaration states them — the one parser of the limits, for the current declaration
    and for the one an earlier attempt was admitted under."""
    total = money(_one(text, rf'^total_limit_provider_usd:[ \t]*({NUMBER})[ \t]*$', 'total_limit_provider_usd:'))
    stages = []
    for stage_id, limit, max_requests, requires in STAGE_LINE.findall(text):
        stages.append((stage_id, money(limit), int(max_requests) if max_requests else None, requires))
    require(stages, 'The declaration names no stage.')
    ids = [s[0] for s in stages]
    require(len(set(ids)) == len(ids), 'The declaration names a stage twice.')
    require(len(re.findall(r'^stage:', text, re.M)) == len(stages), 'A `stage:` line does not have the required form.')
    parsed_stages = []
    for stage_id, limit, max_requests, requires in stages:
        if requires == 'none':
            prerequisite = None
        else:
            match = re.fullmatch(r'([a-z][a-z0-9_]*)_passed', requires)
            require(match and match.group(1) in ids and match.group(1) != stage_id,
                    f'Stage {stage_id} requires an unknown stage ({requires}).')
            prerequisite = match.group(1)
        require(limit > 0 and (max_requests is None or max_requests > 0), f'Stage {stage_id} has no usable limit.')
        parsed_stages.append(Stage(stage_id, limit, max_requests, prerequisite))
    return total, tuple(parsed_stages)


def _terms_from_text(text):
    """(provider, Terms) as the declaration states them — the one parser of the pricing terms, for the current declaration
    and for the one a legacy first attempt was admitted under."""
    provider = _one(text, r'^provider:[ \t]*(\S+)[ \t]*$', 'provider:')
    model = _one(text, r'^model:[ \t]*(\S+)[ \t]*$', 'model:')
    rates = Rates(*_one(text, r'^rates: input (\S+) output (\S+) cached (\S+) \(USD per million tokens\)[ \t]*$', 'rates:'))
    for value in (rates.input, rates.output, rates.cached):
        require(money(value) >= 0, 'A declared rate is negative.')
    thinking = _one(text, r'^thinking:[ \t]*(\S+)[ \t]*$', 'thinking:')
    effort = _one(text, r'^effort:[ \t]*(\S+)[ \t]*$', 'effort:')
    geo = _one(text, r'^inference_geo:[ \t]*(\S+)[ \t]*$', 'inference_geo:')
    versions = PRICING_LINE.findall(text)
    require(len(re.findall(r'^pricing_version\b', text, re.M)) == len(versions), 'A `pricing_version` line does not have the required form.')
    names = [name for name, _ in versions]
    require(len(set(names)) == len(names), 'The declaration names a pricing version twice.')
    return provider, Terms(rates, model, thinking, effort, '' if geo == 'unset' else geo, tuple(sorted(versions)))


def _declaration_blob(declaration, commit, sha256, what):
    """The text of the declaration an earlier attempt names (`declaration_commit`, `declaration_sha256`), read from the
    committed blob at that commit and accepted only if its bytes hash to the recorded sha256 and it is this campaign's."""
    unknown = f'An attempt was admitted under a declaration whose {what} cannot be read back; the {what} in force cannot be established.'
    require(declaration.repository and FULL_COMMIT.fullmatch(str(commit)) and re.fullmatch(r'[0-9a-f]{64}', str(sha256)),
            unknown)
    root = Path(declaration.repository)
    relative = str(Path(declaration.path).relative_to(root))
    blob = _git(root, 'cat-file', 'blob', f'{commit}:{relative}', check=False)
    require(blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == sha256, unknown)
    text = blob.stdout.decode('utf-8')
    require(_one(text, r'^campaign:[ \t]*(\S+)[ \t]*$', 'campaign:') == declaration.campaign
            and _one(text, r'^authority_id:[ \t]*(\S+)[ \t]*$', 'authority_id:') == declaration.authority_id,
            'An attempt was admitted under a declaration of another campaign or authority.')
    return text


def declared_terms_at(declaration, commit, sha256):
    """The pricing terms of the declaration a legacy first attempt names, read back from git (see _declaration_blob)."""
    return _terms_from_text(_declaration_blob(declaration, commit, sha256, 'terms'))[1]


def declared_limits_at(declaration, commit, sha256):
    """The limits of the declaration an earlier attempt names (`declaration_commit`, `declaration_sha256`), read from
    the committed blob at that commit and accepted only if its bytes hash to the recorded sha256."""
    total, stages = _limits_from_text(_declaration_blob(declaration, commit, sha256, 'limits'))
    return Limits(total, tuple(StageLimit(s.id, s.limit, s.max_requests, (s.requires,) if s.requires else ())
                               for s in stages))


def declared(path, *, repository=None, out=None):
    """The committed, unmodified declaration at `path`, parsed. `repository`: the checkout it must belong to (the
    runner's own checkout by default). Prints the declaration's commit and commit time to `out` (stderr)."""
    out = sys.stderr if out is None else out
    path = Path(path).resolve()
    if repository is None:
        top = subprocess.run(['git', '-C', str(REBUILD), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
        repository = top.stdout.strip() or '/nonexistent'
    root = Path(repository).resolve()
    require(path.parent == root / 'docs' / 'foundation' / 'mutations',
            'The declaration must be in this checkout\'s docs/foundation/mutations/.')
    data, commit, commit_time, relative = committed_file(path, root, 'declaration')
    text = data.decode('utf-8')

    lines = AUTHORIZATION_LINE.findall(text)
    authorization = AUTHORIZATION.fullmatch(lines[0].rstrip()) if len(lines) == 1 else None
    require(authorization, 'The declaration names no owner authorization (exactly one line, exactly `authorization: owner '
                           '<YYYY-MM-DD> approved <what> at the stated limits`, nothing after it).')
    owner_words = _one(text, r'^owner_words:[ \t]*(\S.*?)[ \t]*$', 'owner_words:')
    flat = ' '.join(text.split())
    for sentence in KNOWN_NON_REVOCATIONS:
        require(flat.count(sentence) <= 1, 'The declaration repeats a sentence that names a revocation.')
        flat = flat.replace(sentence, ' ')
    require(not REVOCATION.search(flat), 'The declaration carries a revocation.')

    campaign = _one(text, r'^campaign:[ \t]*(\S+)[ \t]*$', 'campaign:')
    authority_id = _one(text, r'^authority_id:[ \t]*(\S+)[ \t]*$', 'authority_id:')
    transfers = _one(text, r'^unused_stage_budget_transfers:[ \t]*(yes|no)[ \t]*$', 'unused_stage_budget_transfers:')
    require(transfers == 'no', 'This runner enforces per-stage limits with no transfer between stages.')
    total, parsed_stages = _limits_from_text(text)
    provider, terms = _terms_from_text(text)
    versions = [(name, version) for name, version in PRICING_LINE.findall(text)]
    names = [name for name, _ in versions]
    for stage in parsed_stages:
        require(stage.id in names, f'Stage {stage.id} has no declared pricing version.')
    credential_file = _one(text, r'^credential_file:[ \t]*(/\S+)[ \t]*$', 'credential_file:')
    refuse_env_path(credential_file)
    declaration = Declaration(
        path=str(path), sha256=hashlib.sha256(data).hexdigest(), commit=commit, commit_time=commit_time,
        campaign=campaign, authority_id=authority_id, authorization=lines[0].split(':', 1)[1].strip(),
        owner_words=owner_words, total_limit=total, stages=tuple(parsed_stages), transfers=False, provider=provider,
        model=terms.model, rates=terms.rates, thinking=terms.thinking, effort=terms.effort,
        inference_geo=terms.inference_geo, pricing_versions=tuple(versions), credential_file=credential_file,
        repository=str(root))
    print(f'declaration {relative}: committed {commit_time} in {commit}; sha256 {declaration.sha256}', file=out)
    return declaration


# ── the ledger ───────────────────────────────────────────────────────────────────────────────────────────────────

ATTEMPT_FILE = re.compile(r'(\d{3})-attempt\.json')
OUTCOME_FILE = re.compile(r'(\d{3})-outcome\.json')
#: A stage decision. `passed` is unnumbered (a stage passes once: the existing stage-model_check-passed.json is this
#: form); failures and reopenings are numbered failed-1, reopened-1, failed-2 … An unnumbered `failed` (the form before
#: numbering) is failure 1.
STAGE_FILE = re.compile(r'stage-([a-z][a-z0-9_]*)-(passed|failed|reopened)(?:-([1-9][0-9]{0,5}))?\.json')
STOP_FILE = 'campaign-stop.json'
LOCK_FILE = 'runner.lock'


class Ledger:
    """The append-only record of every attempt, its outcome, and every stage decision."""

    def __init__(self, directory):
        self.dir = Path(directory)
        self._lock = None

    # (one runner at a time: two could otherwise both pass the same limit check)
    def acquire(self):
        private_directory(self.dir)
        if self._lock is None:
            self._lock = hold_lock(self.dir / LOCK_FILE)
        return self

    def release(self):
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None

    def _require_lock(self):
        require(self._lock is not None, 'The ledger is written only by the runner holding its lock.')

    def _listing(self):
        if not self.dir.exists():
            return {}, {}, {}, None
        attempts, outcomes, stages, stop = {}, {}, {}, None
        for name in sorted(os.listdir(self.dir)):
            if name.startswith('.partial-') or name == LOCK_FILE:
                continue            # (a kill before a record's link leaves its temporary file; it is never a record)
            if match := ATTEMPT_FILE.fullmatch(name):
                attempts[int(match.group(1))] = self.dir / name
            elif match := OUTCOME_FILE.fullmatch(name):
                outcomes[int(match.group(1))] = self.dir / name
            elif match := STAGE_FILE.fullmatch(name):
                number = int(match.group(3)) if match.group(3) else None
                stages.setdefault(match.group(1), []).append((match.group(2), number, self.dir / name))
            elif name == STOP_FILE:
                stop = self.dir / name
            else:
                raise Refused(f'The ledger holds a file that is not a ledger record: {name}.')
        return attempts, outcomes, stages, stop

    def rows(self):
        """[(attempt, outcome or None)] in attempt order; refuses a gap, an orphan outcome or a mislabelled record."""
        attempts, outcomes, _, _ = self._listing()
        numbers = sorted(attempts)
        require(numbers == list(range(1, len(numbers) + 1)), f'The ledger is not a gapless sequence: {numbers}.')
        require(set(outcomes) <= set(attempts), 'The ledger holds an outcome with no attempt.')
        rows = []
        for number in numbers:
            attempt = read_json(attempts[number])
            outcome = read_json(outcomes[number]) if number in outcomes else None
            require(attempt.get('number') == number and (outcome is None or outcome.get('number') == number),
                    f'Ledger record {number:03d} is labelled with another number.')
            rows.append((attempt, outcome))
        return rows

    def _stage(self, stage, entries):
        """One stage's decisions, validated as a sequence: failures 1..F, reopenings 1..R with R == F or R == F - 1, at
        most one pass and only when no failure is left open; each record names its own stage, decision and number."""
        failed, reopened, passed = {}, {}, []
        for kind, number, path in entries:
            record = read_json(path)
            require(isinstance(record, dict) and record.get('stage') == stage and record.get('decision') == kind,
                    f'The ledger record {path.name} is labelled with another stage or decision.')
            if kind == 'passed':
                require(number is None, f'A pass is recorded once, unnumbered ({path.name}).')
                passed.append(record)
                continue
            if kind == 'failed' and number is None:
                require('number' not in record, f'The ledger record {path.name} is labelled with another number.')
                number = 1
            else:
                require(record.get('number') == number, f'The ledger record {path.name} is labelled with another number.')
            found = failed if kind == 'failed' else reopened
            require(number not in found, f'Stage {stage} records failure {number} twice.')
            found[number] = record
        failures, reopenings = len(failed), len(reopened)
        require(sorted(failed) == list(range(1, failures + 1)) and sorted(reopened) == list(range(1, reopenings + 1))
                and reopenings in (failures, failures - 1) and len(passed) <= 1
                and (not passed or reopenings == failures),
                f'The decisions recorded for stage {stage} are out of sequence.')
        open_since = 0
        if reopenings:
            open_since = reopened[reopenings].get('ledger_attempts')
            require(type(open_since) is int and open_since >= 0,
                    f'The reopening of stage {stage} does not record the ledger it was written against.')
        state = 'passed' if passed else ('failed' if failures > reopenings else 'open')
        return {'state': state, 'failures': failures, 'reopenings': reopenings, 'open_since': open_since,
                'passed': passed[0] if passed else None, 'failed': [failed[n] for n in sorted(failed)],
                'reopened': [reopened[n] for n in sorted(reopened)]}

    def stage_state(self, stage):
        """{'state': 'open' | 'failed' | 'passed', 'failures', 'reopenings', 'open_since' (the number of ledger attempts
        when the stage was last reopened; 0 if never), and the records}. A stage with no decision is open."""
        _, _, stages, _ = self._listing()
        return self._stage(stage, stages.get(stage, []))

    def stage_records(self):
        """{stage: {kind: the LATEST record of that kind}} for every stage with a decision (for reports)."""
        _, _, stages, _ = self._listing()
        records = {}
        for stage, entries in stages.items():
            state = self._stage(stage, entries)
            latest = {'passed': state['passed'], 'failed': (state['failed'] or [None])[-1],
                      'reopened': (state['reopened'] or [None])[-1]}
            records[stage] = {kind: record for kind, record in latest.items() if record is not None}
        return records

    def stage_record(self, stage, kind):
        return self.stage_records().get(stage, {}).get(kind)

    def undecided(self, rows=None):
        """{stage: [attempt numbers]} of the attempts no stage decision covers yet: every attempt of an open stage made
        after its last reopening (all of them, if it was never reopened)."""
        rows = self.rows() if rows is None else rows
        found = {}
        for stage in sorted({attempt['stage'] for attempt, _ in rows}):
            state = self.stage_state(stage)
            if state['state'] != 'open':
                continue
            numbers = [attempt['number'] for attempt, _ in rows
                       if attempt['stage'] == stage and attempt['number'] > state['open_since']]
            if numbers:
                found[stage] = numbers
        return found

    def campaign_stop(self):
        _, _, _, stop = self._listing()
        return read_json(stop) if stop else None

    def write_attempt(self, attempt):
        """BEFORE any send: the attempt is durable first, so a lost response is never forgotten."""
        self._require_lock()
        rows = self.rows()
        require(all(outcome is not None for _, outcome in rows), 'An earlier attempt has no outcome; reconcile first.')
        require(attempt.get('number') == len(rows) + 1, 'Attempt numbers are gapless.')
        return write_new(self.dir / f'{attempt["number"]:03d}-attempt.json', attempt)

    def write_outcome(self, number, outcome):
        self._require_lock()
        attempts, outcomes, _, _ = self._listing()
        require(number in attempts and number not in outcomes, f'Attempt {number} has no open attempt record.')
        return write_new(self.dir / f'{number:03d}-outcome.json', {**outcome, 'number': number})

    def write_stage(self, stage, kind, document):
        """A stage decision, written once, only while the stage is open (never decided, or reopened since its last
        failure): `passed` (unnumbered) or `failed-<n>`, the stage's n-th failure."""
        self._require_lock()
        require(kind in ('passed', 'failed'), 'A stage record is passed or failed.')
        require(STAGE_ID.fullmatch(stage), 'A stage is named by its declared id.')
        state = self.stage_state(stage)
        require(state['state'] == 'open', f'Stage {stage} already has a decision.')
        if kind == 'passed':
            return write_new(self.dir / f'stage-{stage}-passed.json', {**document, 'stage': stage, 'decision': kind,
                                                                         'recorded_at': now()})
        number = state['failures'] + 1
        return write_new(self.dir / f'stage-{stage}-failed-{number}.json',
                         {**document, 'stage': stage, 'decision': kind, 'number': number, 'recorded_at': now()})

    def write_reopen(self, stage, number, document):
        """`stage-<id>-reopened-<n>.json`, write-once: only for a stage whose n-th failure is its latest decision.
        Returns the record as written."""
        self._require_lock()
        require(STAGE_ID.fullmatch(stage), 'A stage is named by its declared id.')
        state = self.stage_state(stage)
        require(state['state'] == 'failed' and state['failures'] == number,
                f'Stage {stage} has no open failure {number} to reopen.')
        record = {**document, 'stage': stage, 'decision': 'reopened', 'number': number, 'recorded_at': now()}
        require(type(record.get('ledger_attempts')) is int, 'A reopening records the ledger it was written against.')
        write_new(self.dir / f'stage-{stage}-reopened-{number}.json', record)
        return record

    def write_stop(self, document):
        self._require_lock()
        if self.campaign_stop() is None:
            write_new(self.dir / STOP_FILE, {**document, 'recorded_at': now()})


def recover_interrupted(ledger):
    """Every attempt with no outcome gets one: `interrupted_unknown`, a NEW outcome record (the attempt is never
    edited), counted at its maximum from now on. Returns the numbers recovered."""
    recovered = []
    for attempt, outcome in ledger.rows():
        if outcome is not None:
            continue
        ledger.write_outcome(attempt['number'], {
            'class': 'interrupted_unknown', 'recovered': True, 'recorded_at': now(),
            'note': 'The runner ended with this attempt in flight. Whether the provider processed it is unknown; it is '
                    'counted at its maximum and never sent again.'})
        recovered.append(attempt['number'])
    return recovered


# ── money ────────────────────────────────────────────────────────────────────────────────────────────────────────

def _count(usage, name, *, reported=False):
    """A token count from provider usage. `reported`: the count must be present and not None — input and output tokens
    are never assumed to be zero (a completed outcome without them is an unknown, counted at its maximum)."""
    value = usage.get(name)
    if value is None:
        if reported:
            raise ValueError(f'usage.{name} is not reported')
        value = 0
    if type(value) is not int or value < 0:
        raise ValueError(f'usage.{name} is not a token count')
    return value


def usage_cost(usage, rates, *, unknown_geography_margin=True):
    """What provider-reported usage costs at the declared rates (USD per million tokens): input; cache reads at the
    cached rate; cache writes at 1.25x input for 5 minutes and 2x for 1 hour (a write the provider did not split is
    priced at 2x, the higher); output. x1.1 when the response metered `inference_geo: us` — and, with
    `unknown_geography_margin`, when it reported no geography at all, since the workspace default cannot be read.
    Raises ValueError when input_tokens or output_tokens is not reported: that usage is not known."""
    rate = {name: Decimal(str(value)) for name, value in (rates.decimals() if isinstance(rates, Rates) else rates).items()}
    inputs, outputs = _count(usage, 'input_tokens', reported=True), _count(usage, 'output_tokens', reported=True)
    read, written = _count(usage, 'cache_read_input_tokens'), _count(usage, 'cache_creation_input_tokens')
    split = usage.get('cache_creation')
    if isinstance(split, dict):
        short, long = _count(split, 'ephemeral_5m_input_tokens'), _count(split, 'ephemeral_1h_input_tokens')
        if short + long != written:
            raise ValueError('the cache-write split does not reconcile')
    else:
        short, long = 0, written
    cost = (inputs * rate['input'] + read * rate['cached'] + short * rate['input'] * Decimal('1.25')
            + long * rate['input'] * 2 + outputs * rate['output']) / Decimal(1000000)
    geography = usage.get('inference_geo')
    if geography == 'us' or (geography in (None, '') and unknown_geography_margin):
        cost *= GEO_MARGIN
    return cost


def attempt_bound(maximum_cost):
    """The most one attempt may cost at the provider: the application's own maximum x 1.1."""
    return money(maximum_cost) * GEO_MARGIN


def known_cost(attempt, outcome, rates=None):
    """The provider-reported usage of an outcome at `rates` (a campaign passes the rates its ledger PINNED; without them,
    the attempt's own recorded rates), or None when it is not known (no usage, an unreported input or output count, an
    invalid count, no rates)."""
    usage = (outcome or {}).get('usage')
    rates = attempt.get('rates') if rates is None else rates
    if not (isinstance(usage, dict) and isinstance(rates, (dict, Rates))):
        return None
    try:
        return usage_cost(usage, rates)
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return None


def exposure(attempt, outcome, rates=None):
    """What one attempt may have cost at the provider, worst case. `rates`: the rates it is costed at — a campaign always
    passes the rates its ledger PINNED (Campaign.pinned_terms), never a later edit's.

    completed         the provider-reported usage at those rates — when input and output tokens are both reported; a
                      completed outcome without them is unknown;
    not_sent          zero — only when the product proved no request existed and none was captured;
    anything else     (unknown, uncertain, interrupted_unknown, reconciliation, no outcome) the attempt's maximum x 1.1,
                      or the reported usage's cost if that is higher."""
    bound = attempt_bound(attempt['maximum_cost'])
    if outcome is None:
        return bound
    if outcome.get('class') == 'not_sent':
        return Decimal(0)
    known = known_cost(attempt, outcome, rates)
    if outcome.get('class') == 'completed' and known is not None:
        return known
    return max(bound, known) if known is not None else bound


class Campaign:
    """A declaration and the ledger that spends under it."""

    def __init__(self, declaration, root, *, watched_files=()):
        self.declaration = declaration
        self.root = Path(root)
        self.ledger = Ledger(self.root / 'ledger')
        #: The runner and engine files (repository-relative) a reopening must show were repaired (A2).
        self.watched_files = tuple(watched_files)

    def rows(self):
        rows = self.ledger.rows()
        for attempt, _ in rows:
            require(attempt.get('campaign') == self.declaration.campaign
                    and attempt.get('authority_id') == self.declaration.authority_id,
                    'This ledger belongs to another campaign or authority.')
            self.declaration.stage(attempt.get('stage'))
        return rows

    def totals(self, stage=None):
        every = self.rows()
        rates = self.pinned_terms(every).rates
        rows = [(a, o) for a, o in every if stage is None or a['stage'] == stage]
        return {'attempts': len(rows), 'exposure': sum((exposure(a, o, rates) for a, o in rows), Decimal(0)),
                'open': sum(1 for _, o in rows if o is None),
                'unknown': sum(1 for a, o in rows if o is None or o.get('class') != 'completed'
                               or known_cost(a, o, rates) is None)}

    def pinned_terms(self, rows=None):
        """The pricing terms IN FORCE (A1, RR-MONEY-1): those the ledger's FIRST attempt records — or, for a legacy first
        attempt that records none (the live ledger's attempt 1), those of the declaration it names by sha256, read back
        from git at its declaration_commit when it is not the current declaration. With no attempt yet, the current
        declaration's (the first attempt will record them). Every later attempt that records terms must record the same;
        anything that cannot be established is refused."""
        rows = self.rows() if rows is None else rows
        if not rows:
            return self.declaration.terms()
        first = rows[0][0]
        if 'terms' in first:
            pinned = Terms.from_record(first['terms'], f'Attempt {first.get("number")}')
        else:
            sha256 = first.get('declaration_sha256')
            require(isinstance(sha256, str) and re.fullmatch(r'[0-9a-f]{64}', sha256),
                    'The first attempt records neither its terms nor its declaration; the terms in force cannot be established.')
            pinned = (self.declaration.terms() if sha256 == self.declaration.sha256
                      else declared_terms_at(self.declaration, first.get('declaration_commit'), sha256))
        for attempt, _ in rows[1:]:
            if 'terms' in attempt:
                require(Terms.from_record(attempt['terms'], f'Attempt {attempt.get("number")}') == pinned,
                        f'Attempt {attempt.get("number")} records other terms than the first attempt pinned; the ledger '
                        'is not consistent.')
        return pinned

    def require_pinned_terms(self, rows):
        """The pinned terms, refusing while the current declaration states any other rate, model, thinking, effort,
        inference geography or pricing version: an edited declaration never changes what is admitted or how it is
        costed."""
        pinned = self.pinned_terms(rows)
        changed = pinned.differences(self.declaration.terms())
        require(not changed, 'The declaration\'s ' + ', '.join(changed) + ' differ from those the ledger\'s first attempt '
                'pinned; an edited declaration never changes what is admitted or how it is costed.')
        return pinned

    def pinned_limits(self, attempt):
        """The limits in force when `attempt` was written: the ones it records, or — for an attempt written before
        attempts recorded them (the live ledger's attempt 1) — those of the declaration it names by sha256, read back
        from git at its declaration_commit when it is not the current declaration. Unknown limits are refused."""
        number = attempt.get('number')
        if 'limits' in attempt:
            return Limits.from_record(attempt['limits'], f'Attempt {number}')
        sha256 = attempt.get('declaration_sha256')
        require(isinstance(sha256, str) and re.fullmatch(r'[0-9a-f]{64}', sha256),
                f'Attempt {number} records neither its limits nor its declaration; the limits in force cannot be established.')
        if sha256 == self.declaration.sha256:
            return self.declaration.limits()
        return declared_limits_at(self.declaration, attempt.get('declaration_commit'), sha256)

    def limits(self, rows=None):
        """The limits admission enforces: the TIGHTEST of the current declaration's and those in force when each ledger
        attempt was written. Editing the declaration can lower a limit at once; it can never raise one."""
        rows = self.rows() if rows is None else rows
        limits, seen = self.declaration.limits(), set()
        for attempt, _ in rows:
            pinned = self.pinned_limits(attempt)
            key = json.dumps(pinned.record(), sort_keys=True)
            if key not in seen:
                seen.add(key)
                limits = limits.tightest(pinned)
        return limits

    def admit(self, stage_id, maximum_cost, *, runner_commit=None):
        """Refuses (with the reason) anything that could take a stage or the campaign past a limit in force, BEFORE the
        request is built. Returns the attempt's bound (maximum x 1.1). A stage reopened after a failure admits only a
        runner (`runner_commit`) that is not a failed one and contains the repair its reopening named."""
        declaration = self.declaration
        stage = declaration.stage(stage_id)
        maximum = money(maximum_cost)
        require(maximum > 0, 'An attempt has a positive maximum cost.')
        bound = maximum * GEO_MARGIN
        require(self.ledger.campaign_stop() is None, 'The campaign is stopped.')
        state = self.ledger.stage_state(stage.id)
        require(state['state'] != 'failed', f'Stage {stage.id} failed; it is stopped for offline diagnosis and is admitted '
                                            'again only after `reopen` with a committed diagnosis and repair.')
        require(state['state'] != 'passed', f'Stage {stage.id} already passed; it is never re-run in place.')
        rows = self.rows()
        require(all(outcome is not None for _, outcome in rows), 'An attempt has no outcome; reconcile before admitting.')
        limits = self.limits(rows)
        rates = self.require_pinned_terms(rows).rates
        in_force = limits.stage(stage.id)
        for prerequisite in in_force.requires:
            require(self.ledger.stage_state(prerequisite)['state'] == 'passed',
                    f'Stage {stage.id} requires {prerequisite} to have passed with recorded evidence.')
        here = [(a, o) for a, o in rows if a['stage'] == stage.id]
        if state['reopenings']:
            self._require_repaired_runner(stage.id, state['reopened'][-1], runner_commit)
        if in_force.max_requests is not None:
            require(len(here) + 1 <= in_force.max_requests,
                    f'Stage {stage.id} has used all {in_force.max_requests} requests.')
        spent = sum((exposure(a, o, rates) for a, o in here), Decimal(0))
        total = sum((exposure(a, o, rates) for a, o in rows), Decimal(0))
        require(spent + bound <= in_force.limit,
                f'Stage {stage.id} limit: {spent} exposed + {bound} would exceed ${in_force.limit}.')
        require(total + bound <= limits.total,
                f'Campaign limit: {total} exposed + {bound} would exceed ${limits.total}.')
        return bound

    def _require_repaired_runner(self, stage_id, reopening, runner_commit):
        """A reopened stage runs only on a runner that contains the repair its reopening named — which no failed runner
        of the stage contained (`reopen` proved it), so a failed runner is refused here too."""
        require(self.declaration.repository and isinstance(runner_commit, str)
                and is_ancestor(self.declaration.repository, reopening['repair_commit'], runner_commit),
                f'Stage {stage_id} was reopened for repair {reopening["repair_commit"]}; the runner does not contain it.')

    def reopen(self, stage_id, diagnosis, *, runner_commit):
        """Reopens a FAILED stage after offline repair — the only way one is admitted again. Requires, before anything is
        written: the campaign not stopped and the ledger reconciled; a diagnosis file TRACKED, COMMITTED and UNMODIFIED
        in the declaration's checkout (the declaration's own rules) that names this stage (`reopen_stage:`), exactly the
        attempts of this failure (`failed_attempts:`) and the repair commit (`repair_commit:`); a runner commit that is
        none of the stage's failed runners and contains the repair, which none of them contained; and money and a
        request left under the stage's OWN limits in force (never another stage's). Writes, write-once,
        stage-<id>-reopened-<n>.json and returns it."""
        declaration, ledger = self.declaration, self.ledger
        ledger._require_lock()
        stage = declaration.stage(stage_id)
        require(ledger.campaign_stop() is None, 'The campaign is stopped; no stage is reopened under a stop.')
        rows = self.rows()
        require(all(outcome is not None for _, outcome in rows), 'An attempt has no outcome; reconcile before reopening.')
        rates = self.require_pinned_terms(rows).rates
        state = ledger.stage_state(stage.id)
        require(state['state'] == 'failed', f'Stage {stage.id} has not failed; only a failed stage is reopened.')
        here = [(a, o) for a, o in rows if a['stage'] == stage.id]
        this_failure = [a['number'] for a, _ in here if a['number'] > state['open_since']]
        require(this_failure, f'Stage {stage.id} failed with no attempt of its own; there is nothing to diagnose.')

        # The diagnosis: committed before the act, in this checkout, naming what it diagnoses and the repair.
        require(declaration.repository, 'The declaration names no checkout; a diagnosis cannot be verified.')
        root = Path(declaration.repository).resolve()
        require(diagnosis is not None, 'A reopening needs --diagnosis <path>.')
        refuse_env_path(diagnosis)
        path = Path(diagnosis).resolve()
        require(path.is_relative_to(root) and path != root, 'The diagnosis must be a file in this checkout.')
        data, commit, commit_time, relative = committed_file(path, root, 'diagnosis')
        text = data.decode('utf-8')
        named_stage = _one(text, r'^reopen_stage:[ \t]*(\S+)[ \t]*$', 'reopen_stage:', 'diagnosis')
        require(named_stage == stage.id, f'The diagnosis names reopen_stage {named_stage}, not {stage.id}.')
        attempts = _one(text, r'^failed_attempts:[ \t]*([0-9]+(?:[ \t]*,?[ \t]*[0-9]+)*)[ \t]*$', 'failed_attempts:',
                        'diagnosis')
        named = [int(n) for n in re.findall(r'[0-9]+', attempts)]
        require(len(named) == len(set(named)) and sorted(named) == this_failure,
                f'The diagnosis names attempts {sorted(named)}; failure {state["failures"]} of stage {stage.id} is '
                f'attempts {this_failure}.')
        repair = _one(text, r'^repair_commit:[ \t]*([0-9a-f]{40})[ \t]*$', 'repair_commit:', 'diagnosis')
        # (a diagnosis cannot reopen twice: each failure's attempts are its own, and it must name exactly them)
        diagnosis_sha256 = hashlib.sha256(data).hexdigest()

        # The runner: not a failed one, and it carries the repair, which no failed runner carried.
        require(isinstance(runner_commit, str) and FULL_COMMIT.fullmatch(runner_commit),
                'The runner commit is not a full commit id.')
        failed_runners = sorted({str(a.get('runner_commit')) for a, _ in here})
        for failed_runner in failed_runners:
            require(FULL_COMMIT.fullmatch(failed_runner),
                    f'A failed attempt of stage {stage.id} records no runner commit; a repair cannot be shown to differ.')
        require(runner_commit not in failed_runners, 'The runner is the commit that failed; a repair is a new commit.')
        require(commit_exists(root, repair), f'The repair commit {repair} is not a commit in this checkout.')
        require(commit_exists(root, runner_commit), f'The runner commit {runner_commit} is not a commit in this checkout.')
        require(is_ancestor(root, repair, runner_commit), f'The runner {runner_commit} does not contain the repair {repair}.')
        for failed_runner in failed_runners:
            require(not is_ancestor(root, repair, failed_runner),
                    f'The repair {repair} was already in the failed runner {failed_runner}; it does not repair this failure.')

        # The repair changed what ran (A2): at least one runner or engine file differs between EVERY failed attempt's
        # recorded hashes and this runner's checkout, and the repair commit itself touches at least one of them — a
        # repair to a document alone, or one undone again, reopens nothing.
        watched = self.watched_files
        require(watched, 'This campaign watches no runner or engine file; a repair cannot be shown to change one.')
        current = {name: blob_sha256(root, runner_commit, name) for name in watched}
        changed = set()
        for attempt, _ in here:
            if attempt['number'] not in this_failure:
                continue
            recorded = attempt.get('engine_files')
            require(isinstance(recorded, dict) and all(name in recorded for name in watched),
                    f'Failed attempt {attempt["number"]} records no hash of every runner and engine file; a repair cannot '
                    'be shown to differ.')
            differs = [name for name in watched if recorded[name] != current[name]]
            require(differs, f'No runner or engine file differs between failed attempt {attempt["number"]} and the runner '
                             f'{runner_commit}; nothing that ran was repaired.')
            changed.update(differs)
        touched = sorted(set(files_changed_by(root, repair)) & set(watched))
        require(touched, f'The repair {repair} touches no runner or engine file; it does not repair what ran.')

        # The stage's own limits in force: money and a request left.
        limits = self.limits(rows)
        in_force = limits.stage(stage.id)
        spent = sum((exposure(a, o, rates) for a, o in here), Decimal(0))
        require(spent < in_force.limit, f'Stage {stage.id} has no money left under its own ${in_force.limit} limit '
                                        f'({spent} exposed); another stage\'s budget is never used.')
        if in_force.max_requests is not None:
            require(len(here) < in_force.max_requests,
                    f'Stage {stage.id} has used all {in_force.max_requests} requests of its own.')
        document = {
            'campaign': declaration.campaign, 'authority_id': declaration.authority_id,
            'declaration_sha256': declaration.sha256, 'declaration_commit': declaration.commit,
            'diagnosis': {'path': relative, 'sha256': diagnosis_sha256, 'commit': commit, 'commit_time': commit_time},
            'failed_attempts': this_failure, 'failed_runner_commits': failed_runners, 'repair_commit': repair,
            'runner_commit': runner_commit, 'ledger_attempts': len(rows), 'engine_files': current,
            'changed_files': sorted(changed), 'repair_touches': touched,
            'stage_exposure': format(spent, 'f'), 'stage_limit': format(in_force.limit, 'f'),
            'stage_remaining': format(in_force.limit - spent, 'f'), 'stage_requests': len(here),
            'max_requests': in_force.max_requests, 'limits': limits.record()}
        return ledger.write_reopen(stage.id, state['failures'], document)


# ── the credential ───────────────────────────────────────────────────────────────────────────────────────────────

def env_name(name):
    """An environment file's name: `.env`, `*.env`, `.env.*` and `*.env.*`, in any case."""
    lowered = str(name).lower()
    return lowered.endswith('.env') or '.env.' in lowered


def refuse_env_path(path):
    """Refuses a path that is, or sits under, an environment file or directory (see env_name) — as written AND as
    resolved — before anything is opened. (Resolving reads links, never a file's contents.)"""
    given = Path(path)
    for candidate in (given, Path(os.path.realpath(given))):
        for part in (candidate, *candidate.parents):
            require(not env_name(part.name), 'An environment file is never read.')


def _open_without_links(path, flags):
    """Opens an absolute `path` with NO symbolic link at ANY component: each directory is opened from its parent's
    descriptor with O_NOFOLLOW, then the file itself — so a link cannot be swapped in between a check and the open."""
    parts = Path(path).parts
    require(len(parts) >= 2 and parts[0] == '/', 'The credential file is named by an absolute path.')
    require('..' not in parts, 'The credential path must not name a parent directory (..).')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts[1:-1]:
            try:
                inner = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            except OSError as error:
                if error.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise Refused('A component of the credential path is a symbolic link (or not a directory); '
                                  'no link is ever followed to the credential.') from None
                raise
            os.close(directory)
            directory = inner
        try:
            return os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=directory)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise Refused('The credential file is a symbolic link; no link is ever followed to the credential.') from None
            raise
    finally:
        os.close(directory)


def load_credential(path, declaration=None):
    """The provider key from the declared credential file ONLY. Returned, never printed or logged. Refused before any
    read: an environment-file path, a symbolic link at any component, a file with more than one name (a hard link: the
    key would be reachable through a path nobody declared), the wrong type, mode or owner."""
    if declaration is not None:
        require(str(path) == declaration.credential_file, 'Only the declared credential_file is read.')
    require(os.path.isabs(str(path)), 'The credential file is named by an absolute path.')
    refuse_env_path(path)
    try:
        fd = _open_without_links(str(path), os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        raise Refused('The declared credential file does not exist; the campaign cannot start.') from None
    except OSError as error:
        raise Refused(f'The declared credential file cannot be opened ({type(error).__name__}).') from None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode), 'The credential file is not a regular file.')
        require(info.st_nlink == 1, 'The credential file has another name (a hard link); it is not read.')
        require(stat.S_IMODE(info.st_mode) == 0o600, 'The credential file must be mode 0600.')
        require(info.st_uid == os.getuid(), 'The credential file must be owned by the account that runs the runner.')
        require(0 < info.st_size <= 4096, 'The credential file must hold one line, the API key only.')
        data = os.read(fd, 4097)
    finally:
        os.close(fd)
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError:
        raise Refused('The credential file must hold one line, the API key only.') from None
    body = text[:-1] if text.endswith('\n') else text
    require(body and '\n' not in body and '\r' not in body and body.strip() == body and ' ' not in body
            and body.isprintable(), 'The credential file must hold exactly one non-empty line, the API key only.')
    return body


# ── the environment of the process that makes requests ───────────────────────────────────────────────────────────

#: Named by the task and the declaration; every other ANTHROPIC_* but the two below is refused as well.
REMOVED = ('ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_PROFILE', 'ANTHROPIC_CUSTOM_HEADERS')
KEPT_ANTHROPIC = ('ANTHROPIC_API_KEY', 'ANTHROPIC_CONFIG_DIR')
REFUSED_NAMES = frozenset(('SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'PYTHONPATH',
                           'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONUSERBASE', 'PYTHONINSPECT', 'NETRC'))


def forbidden_name(name):
    """A variable the request process may never carry: another credential source, an endpoint, a header, a profile,
    federation, any proxy, a TLS trust override, or anything that injects code into Python."""
    upper = name.upper()
    return ((upper.startswith('ANTHROPIC_') and upper not in KEPT_ANTHROPIC) or upper.startswith('OPENAI_')
            or upper.endswith('_PROXY') or upper in REFUSED_NAMES)


def declared_settings(declaration):
    """The application settings the declaration fixes, as the application reads them."""
    return {'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': declaration.provider, 'QUILLMD_AI_MODEL': declaration.model,
            'QUILLMD_AI_INPUT_RATE': declaration.rates.input, 'QUILLMD_AI_OUTPUT_RATE': declaration.rates.output,
            'QUILLMD_AI_CACHED_RATE': declaration.rates.cached, 'QUILLMD_AI_THINKING': declaration.thinking,
            'QUILLMD_AI_EFFORT': declaration.effort, 'QUILLMD_AI_INFERENCE_GEO': declaration.inference_geo,
            'QUILLMD_DATA_MODE': 'synthetic'}


def scrubbed_environment(credential, declaration, extra=None, *, config_parent=None):
    """A NEW environ for the process that makes requests. Nothing is inherited from this process's environment, so
    ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_PROFILE, ANTHROPIC_CUSTOM_HEADERS, ANTHROPIC_FEDERATION_*, every
    other ANTHROPIC_* and every proxy variable are absent by construction; `extra` may not add one back (refused, not
    dropped). ANTHROPIC_API_KEY is the declared credential and ANTHROPIC_CONFIG_DIR a fresh, empty, private directory,
    so the SDK's profile and federation lookups find nothing."""
    require(isinstance(credential, str) and credential, 'The request process needs the declared credential.')
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
    env.update(declared_settings(declaration))
    for name, value in (extra or {}).items():
        require(not forbidden_name(name), f'{name} is never passed to the request process.')
        require(isinstance(value, str), f'{name} must be a string.')
        env[name] = value
    config_dir = Path(tempfile.mkdtemp(prefix='anthropic-config-', dir=config_parent))
    os.chmod(config_dir, 0o700)
    require(not any(config_dir.iterdir()), 'The provider configuration directory is not empty.')
    env['ANTHROPIC_CONFIG_DIR'] = str(config_dir)
    env['ANTHROPIC_API_KEY'] = credential
    for name in env:
        require(not forbidden_name(name), f'{name} reached the request process environment.')
    return env


def scrubbed_now(environ=None):
    """The checks the request process runs on its OWN environment before anything is sent."""
    environ = os.environ if environ is None else environ
    offending = sorted(name for name in environ if forbidden_name(name))
    require(not offending, 'The request process environment carries: ' + ', '.join(offending) + '.')
    config_dir = environ.get('ANTHROPIC_CONFIG_DIR', '')
    require(config_dir and Path(config_dir).is_dir() and not any(Path(config_dir).iterdir()),
            'ANTHROPIC_CONFIG_DIR must name an empty directory.')
    require(environ.get('ANTHROPIC_API_KEY'), 'The request process has no credential.')


# ── the request capture ──────────────────────────────────────────────────────────────────────────────────────────

#: The attempt a provider request belongs to: {'number': n, 'evidence_dir': Path, 'secret': str}. Set by the runner
#: around its ONE `run_one`; the capture refuses any request outside it.
CURRENT_ATTEMPT = {}
PROVIDER_URL = 'https://api.anthropic.com/v1/messages'
SECRET_HEADERS = frozenset(('x-api-key', 'authorization', 'proxy-authorization', 'cookie'))


def capture_record(request, secret):
    """The request as it will be sent, without its credential headers. Refused if the key survives anywhere in it."""
    headers = {}
    for name, value in request.headers.multi_items():
        if name.lower() in SECRET_HEADERS or (secret and secret in value):
            continue
        headers[name.lower()] = value
    content = request.content
    try:
        body = json.loads(content)
    except ValueError:
        body = None
    record = {'method': request.method, 'url': str(request.url), 'headers': headers, 'body_json': body,
              'body_sha256': hashlib.sha256(content).hexdigest(), 'body_bytes': len(content),
              'removed_headers': sorted(name.lower() for name in request.headers if name.lower() in SECRET_HEADERS)}
    text = json.dumps(record, sort_keys=True)
    require(not (secret and secret in text) and not KEY_SHAPE.search(text.encode()),
            'The captured request would carry the credential; nothing was sent.')
    return record


def install_request_capture():
    """Wrap the SDK's last step before `send` (`SyncAPIClient._prepare_request`, after the request is built) so the exact
    outbound request is written to the current attempt's evidence BEFORE it leaves. The write is O_EXCL, so a second
    request inside one attempt fails on it and is never sent; a request outside an attempt is refused. In this process
    only: the product is not changed."""
    from anthropic._base_client import SyncAPIClient
    original = SyncAPIClient._prepare_request
    if getattr(original, '_campaign_capture', False):
        return

    def _prepare_request(self, request):
        original(self, request)
        attempt = dict(CURRENT_ATTEMPT)
        require(attempt.get('number') and attempt.get('evidence_dir'), 'A provider request outside an attempt was refused.')
        require(getattr(self, 'max_retries', None) == 0, 'The provider client must not retry (max_retries=0).')
        require(getattr(self, 'custom_auth', None) is None, 'The provider client resolved a credential provider.')
        require(request.method == 'POST' and str(request.url) == PROVIDER_URL,
                f'A request to {request.url.host}{request.url.path} was refused.')
        record = capture_record(request, attempt.get('secret', ''))
        record.update(attempt=attempt['number'], captured_at=now(),
                      client={'base_url': str(getattr(self, 'base_url', '')), 'timeout': str(getattr(self, 'timeout', '')),
                              'max_retries': getattr(self, 'max_retries', None)})
        try:
            write_new(Path(attempt['evidence_dir']) / 'request.json', record)
        except FileExistsError:
            raise Refused('A second provider request inside one attempt was refused.') from None

    _prepare_request._campaign_capture = True
    _prepare_request._campaign_original = original
    SyncAPIClient._prepare_request = _prepare_request
    install_response_capture()


#: The response of an attempt, retained as received: its record (JSON) and its exact body bytes.
RESPONSE_FILE = 'provider-response.json'
RESPONSE_BODY = 'provider-response.body'
#: Response headers never retained (a cookie is not evidence and may be a session token).
DROPPED_RESPONSE_HEADERS = SECRET_HEADERS | frozenset(('set-cookie',))


def response_record(response, secret):
    """The response as it arrived: status, headers without cookies or credentials, the body's sha256 and size, and the
    body as JSON when it parses. Refused if the key (or anything key-shaped) is anywhere in it."""
    headers, removed = {}, set()
    for name, value in response.headers.multi_items():
        if name.lower() in DROPPED_RESPONSE_HEADERS or (secret and secret in value):
            removed.add(name.lower())
            continue
        headers[name.lower()] = value
    body = response.content
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = None
    record = {'status_code': response.status_code, 'reason': response.reason_phrase,
              'http_version': response.http_version, 'headers': headers, 'removed_headers': sorted(removed),
              'request_id': headers.get('request-id', ''), 'body_file': RESPONSE_BODY,
              'body_sha256': hashlib.sha256(body).hexdigest(), 'body_bytes': len(body), 'body_json': parsed}
    text = json.dumps(record, sort_keys=True).encode()
    require(not (secret and (secret.encode() in text or secret.encode() in body))
            and not KEY_SHAPE.search(text) and not KEY_SHAPE.search(body),
            'The provider response would carry the credential; it was not retained.')
    return record


def install_response_capture():
    """Wrap the SDK's one send site (`SyncAPIClient._attempt_request`: build, `_prepare_request`, `_client.send`) so the
    response of an attempt's one request is written to its evidence AS RECEIVED, whatever its status, before the SDK
    parses it and before the product settles, refuses or stores anything. O_EXCL: a second response inside one attempt
    is refused. Fails closed when this SDK has no such send site. In this process only: the product is not changed."""
    from anthropic._base_client import SyncAPIClient
    original = getattr(SyncAPIClient, '_attempt_request', None)
    require(callable(original), 'This provider SDK has no single send site the response capture can wrap.')
    if getattr(original, '_campaign_capture', False):
        return

    def _attempt_request(self, *args, **kwargs):
        response, prepared = original(self, *args, **kwargs)
        attempt = dict(CURRENT_ATTEMPT)
        require(attempt.get('number') and attempt.get('evidence_dir'),
                'A provider response outside an attempt was refused.')
        response.read()                                   # (no-op when httpx already read it: stream=False)
        record = response_record(response, attempt.get('secret', ''))
        record.update(attempt=attempt['number'], received_at=now())
        evidence = Path(attempt['evidence_dir'])
        try:
            write_new(evidence / RESPONSE_BODY, response.content, raw=True)
            write_new(evidence / RESPONSE_FILE, record)
        except FileExistsError:
            raise Refused('A second provider response inside one attempt was refused.') from None
        return response, prepared

    _attempt_request._campaign_capture = True
    _attempt_request._campaign_original = original
    SyncAPIClient._attempt_request = _attempt_request


def received_response(evidence):
    """The response retained for an attempt (its record, `body_json` the parsed body), or None when none arrived.
    Refused when the record and the body retained beside it disagree."""
    evidence = Path(evidence)
    if not (evidence / RESPONSE_FILE).exists():
        return None
    record = read_json(evidence / RESPONSE_FILE)
    body = (evidence / RESPONSE_BODY).read_bytes()
    require(isinstance(record, dict) and record.get('body_sha256') == hashlib.sha256(body).hexdigest(),
            'The retained provider response does not match the body retained beside it.')
    return record


#: Sends that reached the transport, per attempt number (this process only).
SENT = {}


def install_transport_guard():
    """The last door before a socket (`httpx.HTTPTransport.handle_request`): ONE send per attempt, only to the Messages
    URL, only while an attempt is current and only once its request was captured. Anything else — another host, a
    transcription or payment call, a second send, a send the capture never saw — is refused before a connection is
    opened. Defense in depth behind the SDK-level capture; in this process only."""
    import httpx
    original = httpx.HTTPTransport.handle_request
    if getattr(original, '_campaign_guard', False):
        return

    def handle_request(self, request):
        attempt = dict(CURRENT_ATTEMPT)
        require(attempt.get('number') and attempt.get('evidence_dir'),
                'An outbound request outside an attempt was refused at the transport.')
        require(request.method == 'POST' and str(request.url) == PROVIDER_URL,
                f'An outbound request to {request.url.host} was refused at the transport.')
        require((Path(attempt['evidence_dir']) / 'request.json').exists(),
                'An outbound request the capture did not record was refused at the transport.')
        require(not SENT.get(attempt['number']), 'A second send inside one attempt was refused at the transport.')
        SENT[attempt['number']] = 1
        return original(self, request)

    handle_request._campaign_guard = True
    handle_request._campaign_original = original
    httpx.HTTPTransport.handle_request = handle_request


def uninstall_transport_guard():
    import httpx
    current = httpx.HTTPTransport.handle_request
    if getattr(current, '_campaign_guard', False):
        httpx.HTTPTransport.handle_request = current._campaign_original


def uninstall_request_capture():
    from anthropic._base_client import SyncAPIClient
    current = SyncAPIClient._prepare_request
    if getattr(current, '_campaign_capture', False):
        SyncAPIClient._prepare_request = current._campaign_original
    current = getattr(SyncAPIClient, '_attempt_request', None)
    if getattr(current, '_campaign_capture', False):
        SyncAPIClient._attempt_request = current._campaign_original


# ── the leak scan ────────────────────────────────────────────────────────────────────────────────────────────────

class Unscannable(Refused):
    """The leak scan could not read the whole tree — a directory it cannot list or enter, a file it cannot read, a link
    or special file it will not follow, an environment file it will not open. That is a STOP, never 'no leak'."""


def _scan_bytes(data, key):
    return (bool(key) and key.encode() in data) or bool(KEY_SHAPE.search(data))


#: Archives inside retained files are opened and their members scanned, recursively, to this depth (a member of the
#: file's own archive is depth 1) and within this many expanded bytes per retained file. Past either bound the file is
#: UNSCANNABLE — a stop, never skipped and never "no leak".
SCAN_NESTING_LIMIT = 4
SCAN_EXPANDED_LIMIT = 256 * 1024 * 1024
GZIP_MAGIC = b'\x1f\x8b'


def _expand(stream, budget, relative):
    """All of a decompressing stream, counted against the file's expanded-byte budget."""
    parts = []
    with stream:
        while chunk := stream.read(1024 * 1024):
            budget[0] -= len(chunk)
            if budget[0] < 0:
                raise Unscannable(f'{relative} expands to more than {SCAN_EXPANDED_LIMIT} bytes; the leak scan does not '
                                  'read past its bound, so it is unscannable.')
            parts.append(chunk)
    return b''.join(parts)


def _archive_kind(data):
    if data[:2] == GZIP_MAGIC:
        return 'gzip'
    return 'zip' if zipfile.is_zipfile(io.BytesIO(data)) else None


def _scan_archive(source, kind, key, relative, depth, budget):
    """Every member of a zip (or the content of a gzip) at `depth`, each scanned whole and, when it is itself an archive,
    opened in turn. Any decoding error propagates to the caller, which makes it `Unscannable`."""
    if depth > SCAN_NESTING_LIMIT:
        raise Unscannable(f'{relative} nests archives deeper than {SCAN_NESTING_LIMIT}; the leak scan does not read past '
                          'its bound, so it is unscannable.')
    if kind == 'zip':
        members = []
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                members.append(_expand(archive.open(member), budget, relative))
    else:
        members = [_expand(gzip.GzipFile(fileobj=source, mode='rb'), budget, relative)]
    for data in members:
        if _scan_bytes(data, key):
            return True
        inner = _archive_kind(data)
        if inner and _scan_archive(io.BytesIO(data), inner, key, relative, depth + 1, budget):
            return True
    return False


def _scan_file(path, key, relative):
    overlap = max(len(key.encode()) if key else 0, 64)
    tail = head = b''
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as error:
        raise Unscannable(f'The leak scan cannot read {relative} ({type(error).__name__}); an unscannable file is a '
                          'stop, never "no leak".') from None
    with os.fdopen(fd, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise Unscannable(f'{relative} is not a regular file; the leak scan does not read it.')
        try:
            while block := handle.read(SCAN_CHUNK):
                head = head or block[:4]
                if _scan_bytes(tail + block, key):
                    return True
                tail = block[-overlap:]
            handle.seek(0)
            kind = 'gzip' if head[:2] == GZIP_MAGIC else ('zip' if zipfile.is_zipfile(handle) else None)
            if kind:
                # (a Word export is compressed: a key inside its XML is invisible in the file's own bytes; so is one
                # inside a gzip, or an archive inside either)
                handle.seek(0)
                return _scan_archive(handle, kind, key, relative, 1, [SCAN_EXPANDED_LIMIT])
        except Unscannable:
            raise
        except Exception as error:
            # (a corrupt member, a truncated gzip, an unsupported compression, an encrypted member: never a finding that
            # says "leaked", never "no leak" — the file could not be read whole)
            raise Unscannable(f'The leak scan cannot decode {relative} ({type(error).__name__}); an undecodable file is a '
                              'stop, never "no leak".') from None
    return False


def leaked(root, key, exclude=()):
    """Every retained file under `root` searched for the key (by value, never printed) and the sk-ant- shape, archives
    (zip and gzip, nested to SCAN_NESTING_LIMIT within SCAN_EXPANDED_LIMIT bytes) included. `exclude`: exact files that
    are the credential itself. Returns the relative paths of the files that carry one.

    FAILS CLOSED: a root that is not a real directory, or that is or lies under an environment-named directory; a
    directory it cannot list or enter; a file it cannot read or decode; an archive past its bounds; any symbolic link,
    special file or environment-named entry; and ANY unexpected exception raise `Unscannable` (a `Refused`) — nothing
    unread is ever reported as clean, and an environment file is never opened."""
    try:
        return _leaked(root, key, exclude)
    except Unscannable:
        raise
    except Exception as error:
        raise Unscannable(f'The leak scan failed ({type(error).__name__}); a scan that did not finish is a stop, never '
                          '"no leak".') from None


def _leaked(root, key, exclude):
    root = Path(root)
    for candidate in (Path(os.path.abspath(root)), Path(os.path.realpath(root))):
        if any(env_name(part) for part in candidate.parts):
            raise Unscannable('The leak scan root is, or lies under, an environment-named directory; it is never read.')
    excluded = {os.path.realpath(path) for path in exclude}
    found = []

    def relative(path):
        try:
            return str(Path(path).relative_to(root))
        except ValueError:
            return str(path)

    def cannot_list(error):
        raise Unscannable(f'The leak scan cannot list {relative(error.filename or root)} ({type(error).__name__}); an '
                          'unscannable directory is a stop, never "no leak".')

    def entry(path):
        name = relative(path)
        if env_name(path.name):
            raise Unscannable(f'The leak scan met an environment file ({name}); it is never opened, and the campaign '
                              'root never holds one.')
        try:
            return os.lstat(path).st_mode
        except OSError as error:
            raise Unscannable(f'The leak scan cannot read {name} ({type(error).__name__}).') from None

    try:
        root_mode = os.lstat(root).st_mode
    except OSError as error:
        raise Unscannable(f'The leak scan cannot read its root ({type(error).__name__}).') from None
    if not stat.S_ISDIR(root_mode):
        raise Unscannable('The leak scan root is not a real directory (a link is not followed).')
    for directory, subdirectories, files in os.walk(root, onerror=cannot_list, followlinks=False):
        subdirectories.sort()
        for name in subdirectories:
            if not stat.S_ISDIR(entry(Path(directory) / name)):
                raise Unscannable(f'{relative(Path(directory) / name)} is a link, not a directory; the leak scan does '
                                  'not follow it.')
        for name in sorted(files):
            path = Path(directory) / name
            mode = entry(path)
            if not stat.S_ISREG(mode):
                raise Unscannable(f'{relative(path)} is a link or special file; the leak scan does not follow it.')
            if os.path.realpath(path) in excluded:
                continue
            if _scan_file(path, key, relative(path)):
                found.append(relative(path))
    return found


# ── the per-case verdict (mapping and ordinary_notes) ─────────────────────────────────────────────────────────────

#: Output that would put wrong clinical content in a document, or leak the key: each STOPS the stage.
UNSAFE_FINDINGS = frozenset(('adopted_without_source_support', 'wrong_destination', 'wrong_side', 'wrong_denial',
                             'contradiction_adopted', 'protected_area_answered', 'credential_leak',
                             'harmful_change_unreviewed'))
#: A broken request contract or money path: each STOPS the stage.
CONTRACT_FINDINGS = frozenset(('wrong_served_model', 'stop_reason_not_end_turn', 'reconciliation', 'uncertain_outcome',
                               'output_over_70_percent', 'metered_us_while_unset', 'settlement_mismatch', 'audit_failure',
                               'validator_failure', 'more_than_one_request', 'request_not_captured',
                               'export_verification_failed', 'response_not_captured'))
#: What happened to each field (or, for mapping, each expected area, control or false field) of a case: USEFULNESS,
#: recorded per item. Held, missing, over-held and refused answers are the product declining to guess — measured, never
#: a stop ('held_unadjudicated': a hold of an UNLISTED model selection on a field that may be supported — the frozen
#: README's scoring never auto-scores an unlisted response, so it is neither a correct hold nor an over-hold until it
#: is adjudicated by hand). The outcomes in IMPLIED_FINDINGS ARE unsafe output: each carries its unsafe finding, so a case cannot record
#: one without stopping. 'wrong' (a kept deterministic mapping defect) carries none: the runner adds a finding when it is
#: a wrong destination or a change the proposal made.
FIELD_OUTCOMES = frozenset((
    'adopted', 'held', 'missing', 'refused',
    'right', 'held_safe', 'wrong', 'missed', 'false_field', 'false_field_held',
    'supported_correct', 'held_correct', 'over_held', 'usefulness_loss', 'recorded_not_asserted', 'supported_incomplete',
    'clinician_correction', 'held_unadjudicated',
    'unsupported_accepted', 'wrong_side_adopted', 'wrong_denial_adopted', 'contradiction_adopted'))
IMPLIED_FINDINGS = {'unsupported_accepted': 'adopted_without_source_support', 'wrong_side_adopted': 'wrong_side',
                    'wrong_denial_adopted': 'wrong_denial', 'contradiction_adopted': 'contradiction_adopted',
                    'false_field': 'wrong_destination'}


def classify_case(fields, findings):
    """One case's verdict, pure: `fields` {field key: one of FIELD_OUTCOMES}, `findings` a list of codes from
    UNSAFE_FINDINGS or CONTRACT_FINDINGS. Returns {'verdict': 'unsafe' | 'contract' | 'usefulness', 'stops_stage',
    'unsafe', 'contract' (sorted codes; an unsafe field outcome adds its IMPLIED_FINDINGS code), 'fields' (a copy),
    'usefulness' (a count per outcome)}. Unsafe outranks a contract failure; both stop the stage and both are kept. Any
    value outside the vocabulary is REFUSED — an unknown finding is never read as no finding."""
    require(isinstance(fields, dict), 'A case\'s fields are a mapping of field key to outcome.')
    require(isinstance(findings, (list, tuple)), 'A case\'s findings are a list of codes.')
    for key, outcome in fields.items():
        require(isinstance(key, str) and key, 'A field is named by its key.')
        require(isinstance(outcome, str) and outcome in FIELD_OUTCOMES,
                f'Field {key!r} has an outcome outside {sorted(FIELD_OUTCOMES)}.')
    for code in findings:
        require(isinstance(code, str) and code in UNSAFE_FINDINGS | CONTRACT_FINDINGS,
                f'The finding {code!r} is not a known unsafe or contract finding.')
    unsafe = sorted({code for code in findings if code in UNSAFE_FINDINGS}
                    | {IMPLIED_FINDINGS[outcome] for outcome in fields.values() if outcome in IMPLIED_FINDINGS})
    contract = sorted({code for code in findings if code in CONTRACT_FINDINGS})
    verdict = 'unsafe' if unsafe else ('contract' if contract else 'usefulness')
    return {'verdict': verdict, 'stops_stage': verdict != 'usefulness', 'unsafe': unsafe, 'contract': contract,
            'fields': dict(fields),
            'usefulness': {outcome: sum(1 for value in fields.values() if value == outcome)
                           for outcome in sorted(set(fields.values()))}}


def git_identity(checkout=None):
    """The runner checkout's commit, and whether its tracked files are unmodified."""
    checkout = checkout or REBUILD
    head = subprocess.run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(checkout), 'status', '--porcelain', '--untracked-files=no'],
                           capture_output=True, text=True).stdout.strip()
    return {'commit': head, 'clean': len(head) == 40 and not dirty}


def constant_time_equal(first, second):
    return hmac.compare_digest(str(first).encode(), str(second).encode())


def dumps_decimal(value):
    return format(value, 'f') if isinstance(value, Decimal) else value
