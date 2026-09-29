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
                      as `interrupted_unknown` in a NEW outcome record and it counts at its maximum.
  exposure()          Known provider usage is priced at the DECLARED rates (the attempt carries them); anything not known
                      is counted at the attempt's maximum x 1.1.
  Campaign.admit()    Refuses before the request is built: a prerequisite stage not passed, a stage already decided, an
                      attempt without an outcome, the stage or total limit, the stage's request count.
  load_credential()   The declared file only: absolute, no `.env` anywhere in its path or its resolved path, a regular
                      0600 file owned by this account, exactly one non-empty line. The key is returned, never printed.
  scrubbed_environment()
                      The process that makes requests inherits NOTHING: every name the SDK or httpx could take a
                      credential, endpoint, header, profile, federation or proxy from is absent by construction, and
                      `ANTHROPIC_CONFIG_DIR` points at a fresh empty directory.
  install_request_capture()
                      The exact outbound request (method, URL, JSON body, headers without x-api-key/authorization) is
                      written to the current attempt's evidence BEFORE it is sent; a request outside an attempt, a second
                      request inside one, a non-Anthropic URL, a retrying client or a credential-provider client is
                      refused and never sent.
  leaked()            Every retained file (zip members included) is searched for the key and the sk-ant- shape.
"""
import dataclasses
import fcntl
import hashlib
import hmac
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

    def stage(self, stage_id):
        found = [s for s in self.stages if s.id == stage_id]
        require(len(found) == 1, f'The declaration names no stage {stage_id!r}.')
        return found[0]

    def pricing_version(self, key):
        found = [value for name, value in self.pricing_versions if name == key]
        require(len(found) == 1, f'The declaration names no pricing version for {key!r}.')
        return found[0]


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


def _one(text, pattern, what):
    found = re.findall(pattern, text, re.M)
    require(len(found) == 1, f'The declaration must state exactly one `{what}` line (found {len(found)}).')
    return found[0]


def _git(root, *args, check=True):
    result = subprocess.run(['git', '--literal-pathspecs', '-C', str(root), *args], capture_output=True)
    if check:
        require(result.returncode == 0, f'git {args[0]} failed on the declaration\'s checkout.')
    return result


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
    relative = str(path.relative_to(root))
    tracked = _git(root, 'ls-files', '--error-unmatch', '--', relative, check=False).returncode == 0
    unmodified = _git(root, 'diff', '--quiet', 'HEAD', '--', relative, check=False).returncode == 0
    unstaged = _git(root, 'diff', '--quiet', '--', relative, check=False).returncode == 0
    nothing_staged = _git(root, 'diff', '--cached', '--quiet', '--', relative, check=False).returncode == 0
    require(tracked and unmodified and unstaged and nothing_staged, 'The declaration must be tracked, committed and unmodified.')
    data = path.read_bytes()
    # (the committed blob itself, byte for byte: `git update-index --assume-unchanged` makes every diff above report
    # clean over an edited file)
    committed = _git(root, 'cat-file', 'blob', f'HEAD:{relative}', check=False)
    require(committed.returncode == 0 and committed.stdout == data, 'The declaration differs from its committed blob.')
    log = _git(root, 'log', '-1', '--format=%H%x00%cI', 'HEAD', '--', relative).stdout.decode().strip()
    require('\x00' in log, 'The declaration has no commit.')
    commit, commit_time = log.split('\x00', 1)
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
    total = money(_one(text, rf'^total_limit_provider_usd:[ \t]*({NUMBER})[ \t]*$', 'total_limit_provider_usd:'))
    transfers = _one(text, r'^unused_stage_budget_transfers:[ \t]*(yes|no)[ \t]*$', 'unused_stage_budget_transfers:')
    require(transfers == 'no', 'This runner enforces per-stage limits with no transfer between stages.')
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
    for stage in parsed_stages:
        require(stage.id in names, f'Stage {stage.id} has no declared pricing version.')
    credential_file = _one(text, r'^credential_file:[ \t]*(/\S+)[ \t]*$', 'credential_file:')
    refuse_env_path(credential_file)
    declaration = Declaration(
        path=str(path), sha256=hashlib.sha256(data).hexdigest(), commit=commit, commit_time=commit_time,
        campaign=campaign, authority_id=authority_id, authorization=lines[0].split(':', 1)[1].strip(),
        owner_words=owner_words, total_limit=total, stages=tuple(parsed_stages), transfers=False, provider=provider,
        model=model, rates=rates, thinking=thinking, effort=effort, inference_geo='' if geo == 'unset' else geo,
        pricing_versions=tuple(versions), credential_file=credential_file)
    print(f'declaration {relative}: committed {commit_time} in {commit}; sha256 {declaration.sha256}', file=out)
    return declaration


# ── the ledger ───────────────────────────────────────────────────────────────────────────────────────────────────

ATTEMPT_FILE = re.compile(r'(\d{3})-attempt\.json')
OUTCOME_FILE = re.compile(r'(\d{3})-outcome\.json')
STAGE_FILE = re.compile(r'stage-([a-z][a-z0-9_]*)-(passed|failed)\.json')
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
                stages.setdefault(match.group(1), {})[match.group(2)] = self.dir / name
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

    def stage_records(self):
        _, _, stages, _ = self._listing()
        return {stage: {kind: read_json(path) for kind, path in kinds.items()} for stage, kinds in stages.items()}

    def stage_record(self, stage, kind):
        return self.stage_records().get(stage, {}).get(kind)

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
        """A stage decision is written once: `passed` or `failed`, never both, never twice."""
        self._require_lock()
        require(kind in ('passed', 'failed'), 'A stage record is passed or failed.')
        require(not self.stage_records().get(stage), f'Stage {stage} already has a decision.')
        return write_new(self.dir / f'stage-{stage}-{kind}.json', {**document, 'stage': stage, 'decision': kind,
                                                                     'recorded_at': now()})

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

def _count(usage, name):
    value = usage.get(name, 0)
    value = 0 if value is None else value
    if type(value) is not int or value < 0:
        raise ValueError(f'usage.{name} is not a token count')
    return value


def usage_cost(usage, rates, *, unknown_geography_margin=True):
    """What provider-reported usage costs at the declared rates (USD per million tokens): input; cache reads at the
    cached rate; cache writes at 1.25x input for 5 minutes and 2x for 1 hour (a write the provider did not split is
    priced at 2x, the higher); output. x1.1 when the response metered `inference_geo: us` — and, with
    `unknown_geography_margin`, when it reported no geography at all, since the workspace default cannot be read."""
    rate = {name: Decimal(str(value)) for name, value in (rates.decimals() if isinstance(rates, Rates) else rates).items()}
    inputs, outputs = _count(usage, 'input_tokens'), _count(usage, 'output_tokens')
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


def exposure(attempt, outcome):
    """What one attempt may have cost at the provider, worst case.

    completed         the provider-reported usage at the attempt's declared rates;
    not_sent          zero — only when the product proved no request existed and none was captured;
    anything else     (unknown, uncertain, interrupted_unknown, reconciliation, no outcome) the attempt's maximum x 1.1,
                      or the reported usage's cost if that is higher."""
    bound = attempt_bound(attempt['maximum_cost'])
    if outcome is None:
        return bound
    if outcome.get('class') == 'not_sent':
        return Decimal(0)
    usage = outcome.get('usage')
    known = None
    if isinstance(usage, dict) and isinstance(attempt.get('rates'), dict):
        try:
            known = usage_cost(usage, attempt['rates'])
        except (KeyError, ValueError, TypeError, InvalidOperation):
            known = None
    if outcome.get('class') == 'completed' and known is not None:
        return known
    return max(bound, known) if known is not None else bound


class Campaign:
    """A declaration and the ledger that spends under it."""

    def __init__(self, declaration, root):
        self.declaration = declaration
        self.root = Path(root)
        self.ledger = Ledger(self.root / 'ledger')

    def rows(self):
        rows = self.ledger.rows()
        for attempt, _ in rows:
            require(attempt.get('campaign') == self.declaration.campaign
                    and attempt.get('authority_id') == self.declaration.authority_id,
                    'This ledger belongs to another campaign or authority.')
            self.declaration.stage(attempt.get('stage'))
        return rows

    def totals(self, stage=None):
        rows = [(a, o) for a, o in self.rows() if stage is None or a['stage'] == stage]
        return {'attempts': len(rows), 'exposure': sum((exposure(a, o) for a, o in rows), Decimal(0)),
                'open': sum(1 for _, o in rows if o is None),
                'unknown': sum(1 for _, o in rows if o is None or o.get('class') != 'completed')}

    def admit(self, stage_id, maximum_cost):
        """Refuses (with the reason) anything that could take a stage or the campaign past a declared limit, BEFORE the
        request is built. Returns the attempt's bound (maximum x 1.1)."""
        declaration = self.declaration
        stage = declaration.stage(stage_id)
        maximum = money(maximum_cost)
        require(maximum > 0, 'An attempt has a positive maximum cost.')
        bound = maximum * GEO_MARGIN
        require(self.ledger.campaign_stop() is None, 'The campaign is stopped.')
        records = self.ledger.stage_records()
        mine = records.get(stage.id, {})
        require('failed' not in mine, f'Stage {stage.id} failed; it is stopped for offline diagnosis and never repeated.')
        require('passed' not in mine, f'Stage {stage.id} already passed; it is never re-run in place.')
        if stage.requires:
            require('passed' in records.get(stage.requires, {}),
                    f'Stage {stage.id} requires {stage.requires} to have passed with recorded evidence.')
        rows = self.rows()
        require(all(outcome is not None for _, outcome in rows), 'An attempt has no outcome; reconcile before admitting.')
        here = [(a, o) for a, o in rows if a['stage'] == stage.id]
        if stage.max_requests is not None:
            require(len(here) + 1 <= stage.max_requests, f'Stage {stage.id} has used all {stage.max_requests} requests.')
        spent = sum((exposure(a, o) for a, o in here), Decimal(0))
        total = sum((exposure(a, o) for a, o in rows), Decimal(0))
        require(spent + bound <= stage.limit,
                f'Stage {stage.id} limit: {spent} exposed + {bound} would exceed ${stage.limit}.')
        require(total + bound <= declaration.total_limit,
                f'Campaign limit: {total} exposed + {bound} would exceed ${declaration.total_limit}.')
        return bound


# ── the credential ───────────────────────────────────────────────────────────────────────────────────────────────

def env_name(name):
    return name == '.env' or name.endswith('.env')


def refuse_env_path(path):
    """Refuses a path that is, or sits under, a `.env` file or directory — as written AND as resolved — before anything
    is opened. (Resolving reads links, never a file's contents.)"""
    given = Path(path)
    for candidate in (given, Path(os.path.realpath(given))):
        for part in (candidate, *candidate.parents):
            require(not env_name(part.name), 'An environment file is never read.')


def load_credential(path, declaration=None):
    """The provider key from the declared credential file ONLY. Returned, never printed or logged."""
    if declaration is not None:
        require(str(path) == declaration.credential_file, 'Only the declared credential_file is read.')
    require(os.path.isabs(str(path)), 'The credential file is named by an absolute path.')
    refuse_env_path(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        raise Refused('The declared credential file does not exist; the campaign cannot start.') from None
    except OSError as error:
        raise Refused(f'The declared credential file cannot be opened ({type(error).__name__}).') from None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode), 'The credential file is not a regular file.')
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


# ── the leak scan ────────────────────────────────────────────────────────────────────────────────────────────────

def _scan_bytes(data, key):
    return (bool(key) and key.encode() in data) or bool(KEY_SHAPE.search(data))


def _scan_file(path, key):
    overlap = max(len(key.encode()) if key else 0, 64)
    tail = b''
    with open(path, 'rb') as handle:
        while block := handle.read(SCAN_CHUNK):
            if _scan_bytes(tail + block, key):
                return True
            tail = block[-overlap:]
    if zipfile.is_zipfile(path):
        # (a Word export is compressed: a key inside its XML is invisible in the file's own bytes)
        try:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.file_size > 256 * 1024 * 1024:
                        return True     # (unscannable: counted as a finding, never skipped)
                    if _scan_bytes(archive.read(member), key):
                        return True
        except (zipfile.BadZipFile, RuntimeError, OSError):
            return True
    return False


def leaked(root, key, exclude=()):
    """Every retained file under `root` searched for the key (by value, never printed) and the sk-ant- shape. `exclude`:
    exact files that are the credential itself. Returns the relative paths of the files that carry one."""
    root = Path(root)
    excluded = {os.path.realpath(path) for path in exclude}
    found = []
    for directory, subdirectories, files in os.walk(root, followlinks=False):
        subdirectories.sort()
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file() or os.path.realpath(path) in excluded:
                continue
            if _scan_file(path, key):
                found.append(str(path.relative_to(root)))
    return found


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
