#!/usr/bin/env python3
"""Standing synthetic API testing under the owner's standing authority quillmd-v1-private-api-testing-standing-20260930.

The authority (docs/rebuild/v1/QuillMD-V1-Standing-API-Testing-Authority-20260930.json, owner words verbatim) is
`standing_unlimited_monetary`: there is NO owner monetary ceiling and no per-batch monetary confirmation. This runner
therefore enforces no money limit — it does not invent one, and every place a limit would stand holds None (JSON null),
never a large number. Every NON-monetary control stays, each stated so a reader can see how it would fail:

  declared_standing()   The declaration is TRACKED, COMMITTED and UNMODIFIED in docs/foundation/mutations/ (the historical
                        campaign's own rule, provider_campaign.committed_file), names this authority by id, carries exactly
                        one standing authorization line, `mode: standing_unlimited_monetary`, `monetary_ceiling: none`, the
                        owner words byte-equal to the committed authority record (whose sha256 it states), and NO money limit
                        line of any kind; a template placeholder (`<FILL`) refuses. It names a NEW campaign, root and QA
                        database — never the historical ones — and `declaration_use: live` (the committed TEST declaration
                        under ops/tests/fixtures says `test` and is refused by every command that sends).
  require_door()        Every send and the preflight run only through the ruled-mutation door
                        (scripts/run-ruled-mutation.sh): RULED_MUTATION_DECLARATION must name this declaration and
                        RULED_MUTATION_DECL_COMMIT its commit.
  Stop file             <root>/STOP (any kind of file) refuses every send, the preflight and every admission while it
                        exists; the ledger's campaign-stop.json (written by a leak or an unscannable tree) likewise.
  credential            only the declared credential file, by the historical campaign's rules (provider_campaign.
                        load_credential: absolute, no environment-file name, no link at any component, one name, a regular
                        0600 file owned by this account, one line); the request process inherits nothing (scrubbed).
  check_configuration() before anything is written: the synthetic QA database named by the declaration on the QA server
                        127.0.0.1:55731 (never the installed database on 55438), STATE_DIR under the campaign root (never
                        the installed /var/lib/quillmd), a runner checkout that is not the installed tree
                        /opt/meddoc-pro/rebuild, no layout socket, synthetic mode, live AI at the declared model, rates,
                        thinking, effort and geography, EXACTLY the stage's contract flags, the declared pricing version, and
                        a request profile inside the declared per-request bounds.
  inputs                synthetic and authorised only: each send's input is a frozen synthetic form (the diagnostics freeze,
                        verified) or the fixed model-check case; a run records the allowed input hashes, and every attempt's
                        form must be one of them and none of the development originals the rights ledger marks
                        "no provider upload" (paid_or_model_stage1_authorized false), whose sha256s are read from the
                        declared rights ledger after its own sha256 is verified.
  bounded batches       `concurrency: 1` (one runner per campaign: the ledger lock; one request at a time; a running job in
                        the QA database refuses); `max_sends_per_run`; each stage's total `sends`; `max_output_tokens_per_
                        request` (checked on the profile and again by the request capture on the outgoing body); the
                        per-send `request_deadline_seconds`; `automatic_retries: none` (the SDK runs with max_retries=0 and a
                        sent request is never sent again).
  duplicates            a send (stage + send id) is attempted at most once in this campaign: the plan skips what has an
                        attempt, and the ledger refuses an attempt whose send already has one.
  reconciliation        before any new send every attempt has an outcome (an interrupted one is recorded
                        interrupted_unknown, its stage failed) and an open run left by a dead process is closed as
                        interrupted.
  safety                the per-send verdicts are the historical campaign's own (provider_campaign.classify_case, the stage
                        runner's graders): unsafe output or a contract failure fails the stage — that path stops until a
                        committed diagnosis and repair reopen it (provider_campaign.Campaign.reopen, with no money check).
  preflight             `preflight` makes ONE free request, GET https://api.anthropic.com/v1/models/<declared model>, and
                        records the returned id and display information. It is MODEL ACCESS evidence, not generation proof;
                        `run` requires one whose returned id is the declared model.
  transcription         a declared `transcription` stage (ops/standing_qa_transcription.py): Deepgram nova-3-medical with
                        mip_opt_out=true at the declared per-minute rate, on synthetic speech only — the runner's own
                        allowlist (TRANSCRIPTION_AUDIO: sha256-pinned recordings, each 'synthesized speech, not a human
                        microphone recording') narrowed to the declared inputs. Each recording is two sends: its transcription
                        (one QA-worker job; the reviewed transcript then saved as the notes through the real view) and the
                        generation on that encounter (review, finalization, authenticated export). The Deepgram key is read
                        from `transcription_credential_file` by the same file rules as the Anthropic key, only for a
                        transcription run, and must be a key of its own BY VALUE (sharing no run of 16 characters with
                        the Anthropic key in any letter case, never Anthropic-shaped: require_own_transcription_key,
                        refutation L1:R1-F2 — a copy at a path of its own was sent to Deepgram); it reaches only that
                        run's request process, whose environment holds it only around the transcription send's one
                        request; a transport guard admits only that request (POST https://api.deepgram.com/v1/listen
                        with exactly the declared parameters and key, the Anthropic key nowhere in it), captured first.

The historical campaign quillmd-v1-sonnet5-staged-40 (its declaration, ledger, limits, attempts 1-24, failures and
verdicts) is untouched: its runner (ops/sonnet5_qa.py) still reads it (plan, status), refuses every write to its root
(sonnet5_qa.require_not_historical) and sends nothing again at any root (sonnet5_qa.SENDS_CLOSED: `run` and `_inner`
refuse before reading anything); this runner refuses its campaign id, root and database.

Commands (from the candidate checkout; `run` and `preflight` only through the ruled-mutation door; every command but
`pricing` takes `--declaration docs/foundation/mutations/<YYYYMMDD>-quillmd-v1-standing-api-testing[-<n>].md` for a
later campaign, whose id fixes its root and QA database — default: the first campaign's declaration):
  pricing --model M --input R --output R --cached R --thinking T --effort E [--inference-geo G]
          [--deepgram-rate-per-minute D]
                     the pricing version the APPLICATION computes for each pricing key under those settings, and each
                     request profile (no credential, network or database) — what the lead writes into the declaration;
                     with D, also the `transcription` version (D is hashed into it) and each allowlisted recording's
                     transcription maximum
  plan [--stage S] [--price]
                     the plan definitions (send ids, inputs and their sha256), what each stage has already attempted and
                     what is left; --price: each send's maximum from the application (needs the declaration)
  status             the ledger, runs, stage states and preflights; no ceiling (null); read-only
  preflight          the model-access preflight (door)
  run --stage S [--max-sends N]
                     one bounded run of a stage (door)
  recover            records any attempt left without an outcome and closes a dangling run
  reopen --stage S --diagnosis P
                     reopens a failed stage after an offline, committed diagnosis and repair; nothing is sent
Exit status: 0 PASS (or a clean plan/status/pricing/recover/reopen, or a preflight that matched; a run that made its
sends with no stop, whether or not its stage is now decided — the result's `decision` says), 3 FAIL, 2 REFUSED, 4 HALTED
(the Stop file appeared during a run: the remaining sends were not made, the stage stays open — including when it
appeared after the loop's own check, inside a send before its attempt was written: that refusal is a halt, never a
failure, and the send's queued job is cancelled through the product).
"""
import argparse
import dataclasses
import hashlib
import json
import os
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import unicodedata
from decimal import Decimal
from pathlib import Path

try:
    from . import provider_campaign as pc
    from . import sonnet5_qa as sq
except ImportError:                                  # (run as a script: ops/ is on sys.path)
    import provider_campaign as pc
    import sonnet5_qa as sq

RUNNER = Path(__file__).resolve()
REBUILD = RUNNER.parents[1]
REPOSITORY = REBUILD.parent

require = pc.require
Refused = pc.Refused

# ── the authority, the campaign and where it runs ────────────────────────────────────────────────────────────────

AUTHORITY_ID = 'quillmd-v1-private-api-testing-standing-20260930'
AUTHORITY_DATE = '2026-09-30'
#: The committed authority record (repository-relative): the owner words, verbatim, and the mode.
AUTHORITY_RECORD = 'docs/rebuild/v1/QuillMD-V1-Standing-API-Testing-Authority-20260930.json'
MODE = 'standing_unlimited_monetary'
CAMPAIGN = 'quillmd-v1-standing-api-testing-20261001'
#: The model the live declaration must name (the owner: "switch to sonnet 5.5 to the brand new one").
DECLARED_MODEL = 'claude-sonnet-5-5'
MUTATIONS = REPOSITORY / 'docs' / 'foundation' / 'mutations'
#: The live declaration of the first campaign, written by the lead from TEMPLATE once the 5.5 profile is integrated.
DECLARATION = MUTATIONS / '20261001-quillmd-v1-standing-api-testing.md'
TEMPLATE = MUTATIONS / '20261001-quillmd-v1-standing-api-testing.TEMPLATE.md'
#: Where every standing campaign's root lives. A live campaign's id fixes its root, its QA database and its declaration's
#: file name (live_places) — a declaration can never point a campaign at another place. A later campaign under the same
#: authority (to measure a send again after a repair: a send is made at most once per campaign) is a new declaration
#: file, `<date>-quillmd-v1-standing-api-testing-<n>.md`, naming `quillmd-v1-standing-api-testing-<date>-<n>`.
RUNTIME = Path('/opt/meddoc-pro/rebuild/.runtime')
LIVE_CAMPAIGN = re.compile(r'quillmd-v1-standing-api-testing-(20[0-9]{6})(?:-([2-9]|[1-9][0-9]))?')


def live_places(campaign):
    """{'root', 'database', 'declaration_name'} a live campaign id fixes; refuses any other id."""
    match = LIVE_CAMPAIGN.fullmatch(campaign or '')
    require(match, f'A live standing campaign is named quillmd-v1-standing-api-testing-<YYYYMMDD>[-<n>], not {campaign!r}.')
    suffix = match.group(1) + (f'-{match.group(2)}' if match.group(2) else '')
    return {'root': RUNTIME / f'v1-standing-api-testing-{suffix}',
            'database': 'quillmd_qa_standing_' + suffix.replace('-', '_'),
            'declaration_name': f'{match.group(1)}-quillmd-v1-standing-api-testing'
                                + (f'-{match.group(2)}' if match.group(2) else '') + '.md'}


#: The first campaign's own root and synthetic QA database (live_places of CAMPAIGN; never the historical ones).
LIVE_ROOT = RUNTIME / 'v1-standing-api-testing-20261001'
DATABASE_NAME = 'quillmd_qa_standing_20261001'
QA_SERVER = {'host': '127.0.0.1', 'port': '55731', 'user': 'quillmd_qa'}
#: The preserved campaign: never written, never admitted under this authority.
HISTORICAL = {'campaign': 'quillmd-v1-sonnet5-staged-40',
              'authority_id': 'quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk',
              'root': sq.HISTORICAL_ROOT, 'database': sq.DATABASE['name']}
#: The installed release's places: its tree (the units' WorkingDirectory), database port and state directory.
INSTALLED = {'tree': Path('/opt/meddoc-pro/rebuild'), 'database_port': '55438', 'state_dirs': (Path('/var/lib/quillmd'),)}
#: The operator's Stop file, at the campaign root: while it exists nothing is sent.
STOP_NAME = 'STOP'
CONTEXT_VARIABLE = 'STANDING_QA_CONTEXT'
PROVIDER_ROOT = 'https://api.anthropic.com'
MODELS_URL = PROVIDER_ROOT + '/v1/models/'
PREFLIGHT_TIMEOUT_SECONDS = 30
#: 4 HALTED: the operator's Stop file appeared during a run; the remaining sends were not made and the stage stays open.
EXIT = {**sq.EXIT, 'HALTED': 4}
#: The most a non-streaming request may ask for (core.generation.NONSTREAMING_MAX_OUTPUT_TOKENS) and the longest
#: per-send deadline this runner accepts.
NONSTREAMING_MAX_OUTPUT_TOKENS = 21333
MAX_DEADLINE_SECONDS = 600

# ── the stages (plan definitions) ────────────────────────────────────────────────────────────────────────────────

#: Which stage runner a stage uses ('model_check': sonnet5_qa.run_model_check; transcription:
#: standing_qa_transcription.TranscriptionRun; the others: sonnet5_stages.Run).
STAGE_KIND = {'model_check': 'model_check', 'mapping': 'mapping', 'notes_comparison': 'ordinary_notes',
              'd30_d31_structure': 'ordinary_notes', 'transcription': 'transcription'}
#: The pricing keys each stage's sends are priced under (every one must be declared for a declared stage).
STAGE_PRICING = {'model_check': ('model_check',), 'mapping': ('mapping',),
                 'notes_comparison': ('ordinary_notes', 'ordinary_notes_field_relations'),
                 'd30_d31_structure': ('ordinary_notes', 'ordinary_notes_field_relations'),
                 'transcription': ('transcription',)}
_ALL_OFF = {'QUILLMD_WM_NARRATIVE': '0', 'QUILLMD_V3_HISTORY_CONTEXT': '0', 'QUILLMD_V3_GENERATION_BATCHES': '0',
            'QUILLMD_V3_FIELD_RELATIONS': '0', 'QUILLMD_MAPPING_ASSISTANCE': '0', 'QUILLMD_MAPPING_ASSISTANCE_LIVE': '0',
            'QUILLMD_LAYOUT_SOCKET': '', 'QUILLMD_LAYOUT_SERVICE_UID': ''}
#: The request process's contract flags per stage — EXACTLY these (check_configuration). Field relations is switched on
#: only around the field-relations sends (the frozen app-path steps' PATH_FLAGS), never for the process. The
#: transcription stage runs the notes stage's v3 engine with every contract flag off, Deepgram's Model Improvement
#: opt-out ON and smart formatting off by default; stage_flags adds its declared per-minute rate and smart formatting.
STAGE_FLAGS = {'model_check': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'legacy'},
               'mapping': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3', 'QUILLMD_MAPPING_ASSISTANCE': '1',
                           'QUILLMD_MAPPING_ASSISTANCE_LIVE': '1'},
               'notes_comparison': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3'},
               'd30_d31_structure': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3'},
               'transcription': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3', 'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'true',
                                 'QUILLMD_DEEPGRAM_SMART_FORMAT': 'false'}}
#: The flags the pricing versions are computed under, per pricing key (`transcription` also under the declared
#: per-minute rate: the application hashes the voice rate into every pricing version).
PRICING_FLAGS = {'model_check': STAGE_FLAGS['model_check'], 'mapping': STAGE_FLAGS['mapping'],
                 'ordinary_notes': STAGE_FLAGS['notes_comparison'],
                 'ordinary_notes_field_relations': {**STAGE_FLAGS['notes_comparison'], 'QUILLMD_V3_FIELD_RELATIONS': '1'},
                 'transcription': STAGE_FLAGS['transcription']}
#: How each flag is read back from Django settings (name, type).
FLAG_SETTINGS = {'QUILLMD_WM_NARRATIVE': ('WM_NARRATIVE', bool), 'QUILLMD_V3_HISTORY_CONTEXT': ('V3_HISTORY_CONTEXT', bool),
                 'QUILLMD_V3_GENERATION_BATCHES': ('V3_GENERATION_BATCHES', bool),
                 'QUILLMD_V3_FIELD_RELATIONS': ('V3_FIELD_RELATIONS', bool),
                 'QUILLMD_MAPPING_ASSISTANCE': ('QUILLMD_MAPPING_ASSISTANCE', bool),
                 'QUILLMD_MAPPING_ASSISTANCE_LIVE': ('QUILLMD_MAPPING_ASSISTANCE_LIVE', bool),
                 'QUILLMD_WORD_ENGINE': ('QUILLMD_WORD_ENGINE', str), 'QUILLMD_LAYOUT_SOCKET': ('QUILLMD_LAYOUT_SOCKET', str),
                 'QUILLMD_DEEPGRAM_MIP_OPT_OUT': ('QUILLMD_DEEPGRAM_MIP_OPT_OUT', str),
                 'QUILLMD_DEEPGRAM_SMART_FORMAT': ('QUILLMD_DEEPGRAM_SMART_FORMAT', str)}
MODEL_CHECK_SEND = 'model_check:fixed-case'
#: The 14 frozen notes cases with a default send (cases.json), each sent on BOTH requests.
NOTES_COMPARISON_CASES = 14
#: Why the D30/D31-structure stage has no plan yet (it refuses rather than guess one).
D30_D31_NOT_ESTABLISHED = (
    'not established: no frozen, provider-safe synthetic D30/D31-structure input set exists. The D30/D31 whole-app '
    'replays (diagnostics/offline-replays) ran on the development ORIGINALS, which are "no provider upload", and must '
    'never build a provider request. A provider-bound set needs synthetic forms with the D30/D31 STRUCTURE (content '
    'controls and question boxes; the 12-fact ordinary case; the long answer) and none of their wording — a frozen set '
    'with its sha256s and a wording check against the development ground truth (diagnostics/CHECK.md W1: no shared '
    'normalized window of 25+ characters) — then a declaration naming this stage and its send count.')
# ── transcription: the provider, the synthetic speech it may hear, and the form the transcript is generated on ──────

#: The product's transcription request (core/jobs.py submit_transcription: DEEPGRAM_MODEL, the listen endpoint).
TRANSCRIPTION_PROVIDER = 'deepgram'
DEEPGRAM_MODEL = 'nova-3-medical'
DEEPGRAM_URL = 'https://api.deepgram.com/v1/listen'
#: What every allowlisted recording is, said wherever it is used (plan, run record, attempt, evidence).
AUDIO_LABEL = 'synthesized speech, not a human microphone recording'
#: The longest allowlisted recording the runner reads (the product's own upload bound is 15 MB).
AUDIO_READ_LIMIT = 16 * 1024 * 1024
#: The frozen synthetic notes form (diagnostics/notes cases.json, built by its frozen generator and checked against its
#: sha256) every transcript is generated on: a general clinical intake (chief complaint, history, examination,
#: assessment, plan …) that fits any of the allowlisted scripts.
TRANSCRIPTION_FORM = 'r1-11'
#: A declared rate: USD per audio minute, positive, at most ten decimals.
TRANSCRIPTION_RATE = re.compile(r'(?:0|[1-9][0-9]{0,2})\.[0-9]{1,10}|[1-9][0-9]{0,2}')


@dataclasses.dataclass(frozen=True)
class SyntheticAudio:
    """One allowlisted recording: synthesized speech of a synthetic script, pinned by sha256 and size."""
    id: str
    path: str
    sha256: str
    bytes: int
    source: str
    label: str = AUDIO_LABEL

    def record(self):
        return {'id': self.id, 'sha256': self.sha256, 'bytes': self.bytes, 'label': self.label, 'source': self.source,
                'path': self.path}


#: THE runner's synthetic-audio allowlist — the only recordings a transcription send may carry. Each is machine speech
#: of a synthetic script written for this project, never a human microphone recording; each is read only after its
#: bytes hash to the sha256 here (read_audio), and a declaration may only narrow this list (its `transcription_input`
#: lines name entries by id AND sha256).
TRANSCRIPTION_AUDIO = (
    SyntheticAudio('soap-ankle-speech', '/opt/meddoc-pro/rebuild/.runtime/soap-verification-20260920/speech-unpadded.wav',
                   '3121862714193bb2f36c09a688dc7b3f293504163014680cae3c610dc21ea2d7', 1918674,
                   'machine speech of the synthetic SOAP scenario script (soap-verification-20260920/speech-script.txt; '
                   'scenario.json: "Machine speech of the exact synthetic scenario; not a human clinician recording")'),
    SyntheticAudio('colonoscopy-speech', '/opt/meddoc-pro/rebuild/.runtime/typed-voice-20260921/synthetic-colonoscopy.wav',
                   'dfd22dfd4facec937dabd3fbaddd4670807fa5b018d86a4df9f425eb9f83e97c', 2639158,
                   'local espeak-ng synthesis of a synthetic colonoscopy script (typed-voice-20260921/'
                   'audio-provenance.json: "local espeak-ng synthesis; not natural human dictation")'))
AUDIO_BY_ID = {audio.id: audio for audio in TRANSCRIPTION_AUDIO}
#: The two sends of one recording: its transcription, and the generation on the encounter its transcript became.
TRANSCRIPTION_PATHS = ('transcription', 'transcription_generation')


def audio_entry(audio_id):
    require(audio_id in AUDIO_BY_ID, f'{audio_id!r} is not a recording on the runner\'s synthetic-audio allowlist.')
    return AUDIO_BY_ID[audio_id]


def read_audio(entry):
    """The allowlisted recording's bytes, read whole (a regular file, never a link, never an environment file) and
    refused unless they are exactly the pinned size and sha256 — whatever now sits at the path."""
    require(isinstance(entry, SyntheticAudio) and AUDIO_BY_ID.get(entry.id) == entry,
            'Only an entry of the runner\'s synthetic-audio allowlist is read.')
    data = _read_bounded(entry.path, limit=AUDIO_READ_LIMIT)
    require(len(data) == entry.bytes and hashlib.sha256(data).hexdigest() == entry.sha256,
            f'The recording at {entry.path} is not the allowlisted synthetic speech {entry.id} (its sha256 differs); '
            'nothing is sent.')
    return data


def transcription_maximum(seconds, rate):
    """The most a recording measured at `seconds` can cost at the provider at `rate` USD/minute: the product's own
    quote formula (core.jobs.transcription_quote: seconds x 1.02 + 2 s, no discount), before the 1.5x charge."""
    billed = Decimal(str(seconds)) * Decimal('1.02') + Decimal('2')
    return (billed * Decimal(str(rate)) / 60).quantize(Decimal('0.0000000001'))


def transcription_module():
    """ops/standing_qa_transcription.py (the Django-bound transcription worker and the Deepgram guard)."""
    try:
        from . import standing_qa_transcription
    except ImportError:
        import standing_qa_transcription
    return standing_qa_transcription


#: The files a reopening must show were repaired (A2): the historical set and the mapping, relations and Word modules
#: it lacked (a mapping-only repair could not pass A2 honestly there), the product's recording reader and submission
#: preparation, and this runner.
WATCHED_FILES = tuple(dict.fromkeys(sq.WATCHED_FILES + (
    'rebuild/ops/standing_qa.py', 'rebuild/ops/standing_qa_transcription.py', 'rebuild/core/mapping_assistance.py',
    'rebuild/core/mapping_wire.py', 'rebuild/core/mapping_jobs.py', 'rebuild/core/destination_roles.py',
    'rebuild/core/v3_mapping.py', 'rebuild/core/v3_field_relations.py', 'rebuild/core/v3_literal_facts.py',
    'rebuild/core/v3_destination.py', 'rebuild/core/generation_batch.py', 'rebuild/core/tab_review.py',
    'rebuild/documents/word_v3.py', 'rebuild/core/audio.py', 'rebuild/core/media.py')))


def watched_hashes(repository=None):
    """{repository-relative path: sha256, or None when absent} of every WATCHED_FILES entry in this checkout."""
    repository = REPOSITORY if repository is None else Path(repository)
    return {name: (pc.file_sha256(repository / name) if (repository / name).is_file() else None)
            for name in WATCHED_FILES}


def sha256_text(value):
    return hashlib.sha256(value if isinstance(value, bytes) else str(value).encode()).hexdigest()


# ── the declaration ──────────────────────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class StandingStage:
    id: str
    sends: int                      # the most attempts this stage may ever make in this campaign (its plan's size)
    requires: object                # the stage whose PASS is required, or None
    limit: object = None            # ALWAYS None: no money limit (provider_campaign code reads `.limit`)

    @property
    def max_requests(self):
        return self.sends


@dataclasses.dataclass(frozen=True)
class StandingLimits:
    """What admission enforces in a standing campaign: send counts and request bounds, NO money. `total` and every
    stage's `limit` are None — never a number standing for 'no limit'. A new attempt records these (`record()`);
    admission uses the TIGHTEST of the current declaration's and every recorded set, so an edited declaration never
    admits more than was in force when the ledger's attempts were written."""
    stages: tuple                   # provider_campaign.StageLimit(id, None, sends, requires)
    max_sends_per_run: int
    max_output_tokens_per_request: int
    request_deadline_seconds: int

    @property
    def total(self):
        return None

    def stage(self, stage_id):
        found = [s for s in self.stages if s.id == stage_id]
        require(len(found) == 1, f'Stage {stage_id} has no limit in force (the limits the ledger pinned do not name it).')
        return found[0]

    def record(self):
        return {'mode': MODE, 'monetary_ceiling': None, 'max_sends_per_run': self.max_sends_per_run,
                'max_output_tokens_per_request': self.max_output_tokens_per_request,
                'request_deadline_seconds': self.request_deadline_seconds,
                'stages': {s.id: {'limit_provider_usd': None, 'max_requests': s.max_requests, 'requires': list(s.requires)}
                           for s in self.stages}}

    @staticmethod
    def from_record(record, what):
        """Recorded standing limits, read strictly: a money figure anywhere refuses (this is not a standing ledger)."""
        def valid(condition):
            require(condition, f'{what} records limits that cannot be read as a standing campaign\'s; the limits in force '
                               'cannot be established.')
        names = {'mode', 'monetary_ceiling', 'max_sends_per_run', 'max_output_tokens_per_request',
                 'request_deadline_seconds', 'stages'}
        valid(isinstance(record, dict) and set(record) == names and record['mode'] == MODE
              and record['monetary_ceiling'] is None and isinstance(record['stages'], dict))
        counts = [record[n] for n in ('max_sends_per_run', 'max_output_tokens_per_request', 'request_deadline_seconds')]
        valid(all(type(n) is int and n > 0 for n in counts))
        stages = []
        for stage_id, entry in record['stages'].items():
            valid(isinstance(stage_id, str) and pc.STAGE_ID.fullmatch(stage_id) and isinstance(entry, dict)
                  and set(entry) == {'limit_provider_usd', 'max_requests', 'requires'}
                  and entry['limit_provider_usd'] is None and type(entry['max_requests']) is int
                  and entry['max_requests'] > 0 and isinstance(entry['requires'], list)
                  and all(isinstance(p, str) and pc.STAGE_ID.fullmatch(p) for p in entry['requires']))
            stages.append(pc.StageLimit(stage_id, None, entry['max_requests'], tuple(sorted(set(entry['requires'])))))
        return StandingLimits(tuple(stages), *counts)

    def tightest(self, other):
        theirs = {s.id: s for s in other.stages}
        stages = tuple(pc.StageLimit(s.id, None, min(s.max_requests, theirs[s.id].max_requests),
                                     tuple(sorted(set(s.requires) | set(theirs[s.id].requires))))
                       for s in self.stages if s.id in theirs)
        return StandingLimits(stages, min(self.max_sends_per_run, other.max_sends_per_run),
                              min(self.max_output_tokens_per_request, other.max_output_tokens_per_request),
                              min(self.request_deadline_seconds, other.request_deadline_seconds))


@dataclasses.dataclass(frozen=True)
class StandingDeclaration:
    path: str
    sha256: str
    commit: str
    commit_time: str
    repository: str
    campaign: str
    authority_id: str
    authority_record: str
    authority_record_sha256: str
    authorization: str
    owner_words: str
    use: str                        # 'live' | 'test'
    mode: str
    monetary_ceiling: object        # ALWAYS None
    per_batch_monetary_confirmation: bool
    provider: str
    model: str
    rates: pc.Rates
    thinking: str
    effort: str
    inference_geo: str              # '' when unset
    pricing_versions: tuple
    concurrency: int
    automatic_retries: str
    max_sends_per_run: int
    max_output_tokens_per_request: int
    request_deadline_seconds: int
    stages: tuple                   # StandingStage
    root: str
    qa_database: str
    credential_file: str
    qa_database_password_file: str
    restricted_inputs_ledger: str
    restricted_inputs_ledger_sha256: str
    transcription: object = None    # TranscriptionTerms when a transcription stage is declared, else None

    # (read by provider_campaign code written for the historical declaration)
    total_limit = None
    transfers = False

    def stage(self, stage_id):
        found = [s for s in self.stages if s.id == stage_id]
        require(len(found) == 1, f'The declaration names no stage {stage_id!r}.')
        return found[0]

    def pricing_version(self, key):
        found = [value for name, value in self.pricing_versions if name == key]
        require(len(found) == 1, f'The declaration names no pricing version for {key!r}.')
        return found[0]

    def terms(self):
        return pc.Terms(self.rates, self.model, self.thinking, self.effort, self.inference_geo,
                        tuple(sorted(self.pricing_versions)))

    def limits(self):
        return StandingLimits(tuple(pc.StageLimit(s.id, None, s.sends, (s.requires,) if s.requires else ())
                                    for s in self.stages),
                              self.max_sends_per_run, self.max_output_tokens_per_request, self.request_deadline_seconds)

    def expect(self, limits=None):
        """What the reused door (sonnet5_qa / sonnet5_stages preconditions) expects: this model, a valid profile bound by
        its pricing version, inside the per-request bounds in force."""
        limits = self.limits() if limits is None else limits
        return {'model': self.model, 'generation_profile': None,
                'max_output_tokens': limits.max_output_tokens_per_request,
                'timeout_seconds': limits.request_deadline_seconds}


@dataclasses.dataclass(frozen=True)
class TranscriptionTerms:
    """The declared transcription request: provider, model, the rate the lead read from the provider's pricing page, the
    Model Improvement opt-out (always 'true'), smart formatting ('false', the product's default, or 'true' — the
    per-deployment setting QUILLMD_DEEPGRAM_SMART_FORMAT, which Deepgram lists as included and the application leaves
    out of every quote), the Deepgram credential file, and the allowlisted recordings it sends (ids, in allowlist
    order)."""
    provider: str
    model: str
    rate_per_minute: str
    mip_opt_out: str
    smart_format: str
    credential_file: str
    inputs: tuple

    def parameters(self):
        """The query parameters the one request carries, exactly (core.jobs.deepgram_parameters' shape)."""
        return {'model': self.model, 'smart_format': self.smart_format, 'mip_opt_out': self.mip_opt_out}

    def record(self):
        return {'provider': self.provider, 'model': self.model, 'rate_per_minute': self.rate_per_minute,
                'parameters': self.parameters(), 'inputs': [AUDIO_BY_ID[i].record() for i in self.inputs]}


#: The transcription section's one-value lines, each stated exactly once when a transcription stage is declared.
TRANSCRIPTION_LINES = ('transcription_provider', 'transcription_model', 'transcription_rate_per_minute',
                       'transcription_mip_opt_out', 'transcription_smart_format', 'transcription_credential_file')
TRANSCRIPTION_INPUT = re.compile(r'^transcription_input: ([a-z0-9][a-z0-9-]{0,63}) ([0-9a-f]{64})[ \t]*$', re.M)


def transcription_terms(text, seen, stages, credential_file):
    """The declaration's transcription section, verified (pure): None when no transcription stage is declared — and
    then no transcription line may stand at all — otherwise every TRANSCRIPTION_LINES name exactly once (decorated
    copies counted), provider deepgram, model nova-3-medical, a positive per-minute rate, mip_opt_out true, smart
    formatting `true` or `false`, a Deepgram credential file of its own, and one or more `transcription_input: <id> <sha256>`
    lines, each an allowlisted recording with exactly its pinned sha256, none twice; and the stage's send count is two
    per recording (its transcription and its generation)."""
    declared = [stage for stage in stages if stage.id == 'transcription']
    named = re.findall(r'(?<![A-Za-z0-9_])(transcription_[A-Za-z0-9_]*)[^\w\n]*:', seen, re.I)
    if not declared:
        require(not named, 'The declaration states transcription terms (' + ', '.join(sorted(set(named))[:4]) + ') but '
                           'declares no transcription stage.')
        return None
    for name in TRANSCRIPTION_LINES:
        require(len(re.findall(rf'(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])[^\w\n]*:', seen, re.I)) == 1,
                f'A transcription stage states `{name}:` exactly once.')
    unknown = sorted({name.lower() for name in named} - set(TRANSCRIPTION_LINES) - {'transcription_input'})
    require(not unknown, 'The declaration states transcription terms this runner does not know: ' + ', '.join(unknown))

    def one(name, pattern=r'(\S+)'):
        return pc._one(text, rf'^{name}:[ \t]*{pattern}[ \t]*$', f'{name}:')
    provider, model = one('transcription_provider'), one('transcription_model')
    require(provider == TRANSCRIPTION_PROVIDER, f'The transcription provider is {TRANSCRIPTION_PROVIDER}.')
    require(model == DEEPGRAM_MODEL, f'The transcription model is the product\'s {DEEPGRAM_MODEL}.')
    rate = one('transcription_rate_per_minute')
    require(TRANSCRIPTION_RATE.fullmatch(rate) and Decimal(rate) > 0,
            'transcription_rate_per_minute is the provider\'s positive USD rate per audio minute (at most ten decimals), '
            'read from its pricing page when the declaration is written.')
    require(one('transcription_mip_opt_out') == 'true',
            'transcription_mip_opt_out is `true`: no synthetic recording is offered to the provider\'s model improvement.')
    smart_format = one('transcription_smart_format')
    require(smart_format in ('true', 'false'),
            'transcription_smart_format is `true` or `false`, a value the product\'s setting takes.')
    credential = one('transcription_credential_file', r'(/\S+)')
    pc.refuse_env_path(credential)
    require(os.path.abspath(credential) != os.path.abspath(credential_file),
            'The Deepgram credential is a file of its own, never the Anthropic credential file.')
    found = TRANSCRIPTION_INPUT.findall(text)
    require(found and len(re.findall(r'(?<![A-Za-z0-9_])transcription_input(?![A-Za-z0-9_])[^\w\n]*:', seen, re.I))
            == len(found),
            'Every recording is named on its own line `transcription_input: <allowlisted id> <its sha256>`.')
    ids = [audio_id for audio_id, _ in found]
    require(len(set(ids)) == len(ids), 'The declaration names a recording twice.')
    for audio_id, digest in found:
        require(audio_id in AUDIO_BY_ID and AUDIO_BY_ID[audio_id].sha256 == digest,
                f'{audio_id} {digest[:12]}… is not on the runner\'s synthetic-audio allowlist with that sha256; only '
                'allowlisted synthetic speech is ever sent for transcription.')
    require(declared[0].sends == 2 * len(found),
            f'The transcription stage makes two sends per recording (its transcription and its generation): '
            f'{2 * len(found)}, not {declared[0].sends}.')
    return TranscriptionTerms(provider, model, rate, 'true', smart_format, credential,
                              tuple(audio.id for audio in TRANSCRIPTION_AUDIO if audio.id in set(ids)))


#: Exactly one authorization line (provider_campaign.AUTHORIZATION_LINE finds every line that reads as one), this form.
STANDING_AUTHORIZATION = re.compile(r'authorization: owner (\d{4}-\d{2}-\d{2}) standing authority (\S+) with no owner '
                                    r'monetary ceiling')
#: A money LIMIT, matched by structure wherever it stands (decoration, quotes, list marks, any case): any `name:` whose
#: name speaks of money or a ceiling (MONEY_WORDS), and the historical declaration's stage-limit tokens wherever they
#: appear. A standing declaration states none; `monetary_ceiling: none` is the one money line it carries (checked apart:
#: exactly once, value `none`).
NAMED = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)[^\w\n]*:')
MONEY_WORDS = ('limit', 'ceiling', 'budget', 'spend', 'usd', 'dollar', 'cost', 'allowance', 'price', 'fund', 'cap')
MONEY_TOKENS = re.compile(r'(?<![A-Za-z0-9_])(?:limit_provider_usd|max_requests)(?![A-Za-z0-9_])', re.I)
ALLOWED_MONEY_NAMES = ('monetary_ceiling',)


def money_limits(seen):
    """Every money-limit name (or historical limit token) the text states, other than `monetary_ceiling`."""
    found = [name for name in NAMED.findall(seen) if name.lower() not in ALLOWED_MONEY_NAMES
             and any(word in part for part in name.lower().split('_') for word in MONEY_WORDS if part.startswith(word)
                     or part.endswith(word))]
    return found + MONEY_TOKENS.findall(seen)
STANDING_STAGE_LINE = re.compile(r'^stage: ([a-z][a-z0-9_]*) sends ([1-9][0-9]{0,3}) requires (\S+)[ \t]*$', re.M)
CAMPAIGN_ID = re.compile(r'[a-z0-9][a-z0-9.-]{2,79}')
DATABASE = re.compile(r'quillmd_qa_[a-z0-9_]{1,29}')
PLACEHOLDER = '<FILL'


def _seen(text):
    """What a reader sees: compatibility forms folded, invisible format characters removed (refutation F3's class)."""
    return ''.join(ch for ch in unicodedata.normalize('NFKC', text) if unicodedata.category(ch) != 'Cf')


def _inside(path, other):
    """Whether `path` is `other`, inside it, or contains it (absolute, normalized, links resolved where they exist)."""
    first, second = Path(os.path.realpath(str(path))), Path(os.path.realpath(str(other)))
    return first == second or second in first.parents or first in second.parents


def verified_authority_record(root, relative, expected_sha256):
    """The committed authority record: tracked, committed and unmodified in the declaration's checkout, at its fixed
    place, its bytes hashing to the sha256 the declaration states, and saying what this runner implements."""
    require(relative == AUTHORITY_RECORD, f'The authority record is {AUTHORITY_RECORD}, not {relative}.')
    path = (Path(root) / relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), 'The authority record must be a file in this checkout.')
    data, commit, commit_time, _ = pc.committed_file(path, Path(root).resolve(), 'authority record')
    require(hashlib.sha256(data).hexdigest() == expected_sha256,
            'The authority record is not the one the declaration names (its sha256 differs).')
    try:
        record = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise Refused('The authority record cannot be read.') from None
    require(isinstance(record, dict) and record.get('authority_id') == AUTHORITY_ID and record.get('mode') == MODE
            and 'owner_imposed_monetary_ceiling' in record and record['owner_imposed_monetary_ceiling'] is None
            and record.get('per_batch_monetary_confirmation_required') is False
            and isinstance(record.get('owner_words'), str) and record['owner_words'],
            'The authority record is not the standing authority this runner implements (id, mode, no owner ceiling, '
            'no per-batch confirmation, owner words).')
    historical = record.get('historical') if isinstance(record.get('historical'), dict) else {}
    require(historical.get('preserved_authority') == HISTORICAL['authority_id'],
            'The authority record does not preserve the historical authority it replaces for future testing only.')
    return {'record': record, 'commit': commit, 'commit_time': commit_time}


def declared_standing(path, *, repository=None, uses=('live',), out=None):
    """The committed, unmodified STANDING declaration at `path`, parsed and verified against the committed authority
    record. `uses`: the `declaration_use` values accepted ('live' for anything that sends). Prints its commit to `out`."""
    out = sys.stderr if out is None else out
    path = Path(path).resolve()
    if repository is None:
        top = subprocess.run(['git', '-C', str(REBUILD), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
        repository = top.stdout.strip() or '/nonexistent'
    root = Path(repository).resolve()
    require(path.parent == root / 'docs' / 'foundation' / 'mutations',
            'The declaration must be in this checkout\'s docs/foundation/mutations/.')
    data, commit, commit_time, relative = pc.committed_file(path, root, 'declaration')
    text = data.decode('utf-8')
    require(PLACEHOLDER not in text, 'The declaration still carries template placeholders (<FILL …>); a template is never '
                                     'a declaration.')
    seen = _seen(text)

    lines = pc.AUTHORIZATION_LINE.findall(seen)
    authorization = STANDING_AUTHORIZATION.fullmatch(lines[0].rstrip()) if len(lines) == 1 else None
    require(authorization and authorization.group(1) == AUTHORITY_DATE and authorization.group(2) == AUTHORITY_ID,
            'The declaration names no standing authorization (exactly one line, exactly `authorization: owner '
            f'{AUTHORITY_DATE} standing authority {AUTHORITY_ID} with no owner monetary ceiling`).')
    require(not pc.REVOCATION.search(' '.join(seen.split())), 'The declaration carries a revocation.')
    stated = money_limits(seen)
    require(not stated, 'A standing declaration states no money limit, cap or budget (found: ' + ', '.join(stated[:5])
            + '): the authority has no owner monetary ceiling, and none is invented.')
    for name in ('mode', 'monetary_ceiling', 'per_batch_monetary_confirmation', 'authority_id', 'campaign'):
        require(len(re.findall(rf'(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])[^\w\n]*:', seen, re.I)) == 1,
                f'The declaration must state `{name}:` exactly once.')

    def one(name, pattern=r'(\S+)'):
        return pc._one(text, rf'^{name}:[ \t]*{pattern}[ \t]*$', f'{name}:')
    require(one('mode') == MODE, f'The declaration\'s mode is not {MODE}.')
    require(one('monetary_ceiling') == 'none', 'A standing declaration states `monetary_ceiling: none` — the owner '
                                               'imposed no ceiling, and no number may stand for one.')
    require(one('per_batch_monetary_confirmation') == 'not_required',
            'A standing declaration states `per_batch_monetary_confirmation: not_required`.')
    authority_id = one('authority_id')
    require(authority_id == AUTHORITY_ID, f'The declaration names the authority {authority_id}, not {AUTHORITY_ID}.')
    campaign = one('campaign')
    require(CAMPAIGN_ID.fullmatch(campaign) and campaign != HISTORICAL['campaign'],
            'The declaration must name a new campaign of its own, never the historical one.')
    use = one('declaration_use', r'(live|test)')
    require(use in uses, f'This command needs a declaration for {"/".join(uses)} use; this one is for {use} use.')
    owner_words = pc._one(text, r'^owner_words:[ \t]*(\S.*?)[ \t]*$', 'owner_words:')
    verified = verified_authority_record(root, one('authority_record'),
                                         one('authority_record_sha256', r'([0-9a-f]{64})'))
    require(verified['record']['owner_words'] == owner_words,
            'The declaration\'s owner words are not the authority record\'s, verbatim.')

    provider, terms = pc._terms_from_text(text)
    require(provider == 'anthropic', 'The provider must be anthropic.')
    require(use != 'live' or terms.model == DECLARED_MODEL, f'A live declaration names the model {DECLARED_MODEL}.')
    concurrency = int(one('concurrency', r'([0-9]{1,3})'))
    require(concurrency == 1, 'Requests run one at a time: `concurrency: 1`.')
    retries = one('automatic_retries')
    require(retries == 'none', 'A sent request is never re-sent automatically: `automatic_retries: none`.')
    max_sends = int(one('max_sends_per_run', r'([1-9][0-9]{0,3})'))
    max_tokens = int(one('max_output_tokens_per_request', r'([1-9][0-9]{0,5})'))
    require(max_tokens <= NONSTREAMING_MAX_OUTPUT_TOKENS,
            f'max_output_tokens_per_request must be at most {NONSTREAMING_MAX_OUTPUT_TOKENS} (non-streaming).')
    deadline = int(one('request_deadline_seconds', r'([1-9][0-9]{0,3})'))
    require(deadline <= MAX_DEADLINE_SECONDS, f'request_deadline_seconds must be at most {MAX_DEADLINE_SECONDS}.')

    stages = []
    found = STANDING_STAGE_LINE.findall(text)
    require(found and len(re.findall(r'^stage:', text, re.M)) == len(found),
            'Every `stage:` line has the form `stage: <id> sends <n> requires <none|id_passed>`.')
    ids = [stage_id for stage_id, _, _ in found]
    require(len(set(ids)) == len(ids), 'The declaration names a stage twice.')
    for stage_id, sends, requires in found:
        require(stage_id in STAGE_KIND, f'No standing plan is defined for the stage {stage_id!r}.')
        if requires == 'none':
            prerequisite = None
        else:
            match = re.fullmatch(r'([a-z][a-z0-9_]*)_passed', requires)
            require(match and match.group(1) in ids and match.group(1) != stage_id,
                    f'Stage {stage_id} requires an unknown stage ({requires}).')
            prerequisite = match.group(1)
        stages.append(StandingStage(stage_id, int(sends), prerequisite))
    names = [name for name, _ in terms.pricing_versions]
    for stage in stages:
        for key in STAGE_PRICING[stage.id]:
            require(key in names, f'Stage {stage.id} has no declared pricing version for {key}.')

    campaign_root = one('root', r'(/\S+)')
    require(not _inside(campaign_root, HISTORICAL['root']) and not any(_inside(campaign_root, p)
                                                                       for p in INSTALLED['state_dirs']),
            'The campaign root must be its own: never the historical campaign\'s root and never the installed state.')
    database = one('qa_database')
    require(DATABASE.fullmatch(database) and database != HISTORICAL['database'],
            'The QA database must be a quillmd_qa_* synthetic database of its own (at most 40 characters), never the '
            'historical campaign\'s.')
    credential_file = one('credential_file', r'(/\S+)')
    password_file = one('qa_database_password_file', r'(/\S+)')
    restricted = one('restricted_inputs_ledger', r'(/\S+)')
    for named in (credential_file, password_file, restricted):
        pc.refuse_env_path(named)
    transcription = transcription_terms(text, seen, stages, credential_file)
    declaration = StandingDeclaration(
        path=str(path), sha256=hashlib.sha256(data).hexdigest(), commit=commit, commit_time=commit_time,
        repository=str(root), campaign=campaign, authority_id=authority_id, authority_record=AUTHORITY_RECORD,
        authority_record_sha256=one('authority_record_sha256'),
        authorization=lines[0].split(':', 1)[1].strip(), owner_words=owner_words, use=use, mode=MODE,
        monetary_ceiling=None, per_batch_monetary_confirmation=False, provider=provider, model=terms.model,
        rates=terms.rates, thinking=terms.thinking, effort=terms.effort, inference_geo=terms.inference_geo,
        pricing_versions=tuple(pc.PRICING_LINE.findall(text)), concurrency=concurrency, automatic_retries=retries,
        max_sends_per_run=max_sends, max_output_tokens_per_request=max_tokens, request_deadline_seconds=deadline,
        stages=tuple(stages), root=campaign_root, qa_database=database, credential_file=credential_file,
        qa_database_password_file=password_file, restricted_inputs_ledger=restricted,
        restricted_inputs_ledger_sha256=one('restricted_inputs_ledger_sha256', r'([0-9a-f]{64})'),
        transcription=transcription)
    print(f'declaration {relative}: committed {commit_time} in {commit}; sha256 {declaration.sha256}; authority '
          f'{authority_id}; mode {MODE}; monetary ceiling none', file=out)
    return declaration


def require_live(declaration):
    """A live declaration: for live use, of a live campaign id, in the file that id names, at the root and QA database
    that id fixes (live_places), naming claude-sonnet-5-5. Returns the places."""
    require(declaration.use == 'live', 'Only a live declaration sends.')
    places = live_places(declaration.campaign)
    require((declaration.root, declaration.qa_database) == (str(places['root']), places['database']),
            f'The live campaign {declaration.campaign} runs at {places["root"]} on {places["database"]}; the declaration '
            f'names {declaration.root} on {declaration.qa_database}.')
    require(Path(declaration.path).name == places['declaration_name'],
            f'The declaration of {declaration.campaign} is {places["declaration_name"]}, not {Path(declaration.path).name}.')
    require(declaration.model == DECLARED_MODEL, f'The live declaration names {DECLARED_MODEL}.')
    return places


def declaration_path(given=None):
    """The declaration a command reads: DECLARATION, or `--declaration`, which must be a live declaration's file in this
    checkout's docs/foundation/mutations/ (never the template)."""
    if given is None:
        return DECLARATION
    path = Path(given) if os.path.isabs(given) else REPOSITORY / given
    path = Path(os.path.abspath(str(path)))
    require(path.parent == MUTATIONS and re.fullmatch(r'20[0-9]{6}-quillmd-v1-standing-api-testing(?:-([2-9]|[1-9][0-9]))?'
                                                      r'\.md', path.name),
            'A standing declaration is docs/foundation/mutations/<YYYYMMDD>-quillmd-v1-standing-api-testing[-<n>].md.')
    return path


def require_door(declaration, environ=None):
    """The ruled-mutation door (scripts/run-ruled-mutation.sh) was opened for THIS declaration at THIS commit."""
    environ = os.environ if environ is None else environ
    given, commit = environ.get('RULED_MUTATION_DECLARATION', ''), environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(given and commit, 'Provider requests run only through the ruled-mutation door: bash '
                              'scripts/run-ruled-mutation.sh --declaration <this declaration> -- <this command>.')
    named = Path(given) if os.path.isabs(given) else Path(declaration.repository) / given
    require(named.resolve() == Path(declaration.path).resolve(),
            'The ruled-mutation door was opened for another declaration.')
    require(commit == declaration.commit, 'The ruled-mutation door names another commit of the declaration than the '
                                          'one in force.')
    return {'declaration': given, 'commit': commit}


#: The one name the Deepgram key ever has in a process environment: the product reads it there (core.jobs.transcribe).
TRANSCRIPTION_KEY_VARIABLE = 'DEEPGRAM_API_KEY'


#: Two credentials sharing this many consecutive characters (letter case ignored) are one credential copied: a real
#: Deepgram key (40 hexadecimal characters) and a real Anthropic key share no such run but by a copy.
SHARED_RUN = 16


def shares_a_run(first, second, run=SHARED_RUN):
    """True when `first` and `second`, letter case ignored, have `run` consecutive characters in common — or, when the
    shorter of the two is shorter than `run`, when it occurs whole in the other. Equality, one holding the other, a
    part of one, and a long piece of one among other characters are each such a run."""
    shorter, longer = sorted((first.lower(), second.lower()), key=len)
    run = min(run, len(shorter))
    return any(shorter[i:i + run] in longer for i in range(len(shorter) - run + 1))


def require_own_transcription_key(transcription_key, anthropic_key):
    """The Deepgram key is a credential of its own BY VALUE, not only by path (refutation L1:R1-F2: a declared Deepgram
    file at a path of its own holding a copy of the Anthropic key was handed on and sent to api.deepgram.com as `Token
    <the Anthropic key>`). Refused unless the Anthropic key is given to compare against, and unless the Deepgram key
    carries no Anthropic key's shape (provider_campaign.KEY_SHAPE, letter case ignored) and shares no run of SHARED_RUN
    characters with the Anthropic key (shares_a_run: a copy, the key inside a longer line, a part of it, a long piece of
    it among other characters, in any letter case). The one rule for every holder of both keys: the loader (outer,
    inner, the transcription preconditions), run_stage, and the transcription guard at the last door. Neither value is
    ever named in the refusal."""
    require(isinstance(anthropic_key, str) and anthropic_key,
            'The Deepgram credential is checked against the Anthropic key, which is not given; nothing is sent.')
    require(isinstance(transcription_key, str) and transcription_key
            and not pc.KEY_SHAPE.search(transcription_key.lower().encode())
            and not shares_a_run(transcription_key, anthropic_key),
            'The Deepgram credential is not a key of its own: it is, holds, is part of or shares a run of characters '
            'with the Anthropic key, or carries an Anthropic key\'s shape. It would be sent to another provider; '
            'nothing is sent.')
    return transcription_key


def load_transcription_credential(declaration, path=None, *, anthropic_key):
    """The Deepgram key from the declared `transcription_credential_file` ONLY, under the Anthropic key's own file rules
    (provider_campaign.load_credential), every one checked before a byte is read: an absolute path with no
    environment-file name and no symbolic link at ANY component, a regular file with one name (no hard link), mode 0600,
    owned by the account running the runner, one non-empty printable line. A missing file refuses. Then the key must be
    one of its own BY VALUE against `anthropic_key` (require_own_transcription_key: the path check alone let a copy of
    the Anthropic key through, L1:R1-F2) — a required argument, so no caller can read the Deepgram key without that
    comparison; the Anthropic key is given by the caller, never read here. Returned, never printed, logged, written or
    put in argv."""
    terms = declaration.transcription
    require(terms is not None, 'The declaration declares no transcription stage; no Deepgram credential is read.')
    path = terms.credential_file if path is None else path
    require(str(path) == terms.credential_file, 'Only the declared transcription_credential_file is read.')
    try:
        key = pc.load_credential(str(path))
    except Refused as refused:
        raise Refused(f'The Deepgram credential: {refused}') from None
    return require_own_transcription_key(key, anthropic_key)


# ── restricted and allowed inputs ────────────────────────────────────────────────────────────────────────────────

def restricted_hashes(declaration):
    """The sha256 of every development original the rights ledger does NOT authorise for provider or model use
    (`paid_or_model_stage1_authorized` anything but true): read only after the ledger's own sha256 is the declared one.
    A ledger that cannot be read whole refuses (an unknown restriction is never read as none)."""
    data = _read_bounded(declaration.restricted_inputs_ledger)
    require(hashlib.sha256(data).hexdigest() == declaration.restricted_inputs_ledger_sha256,
            'The rights ledger is not the one the declaration names (its sha256 differs).')
    try:
        records = json.loads(data.decode('utf-8'))['records']
        found = set()
        for record in records:
            digest = record['sha256']
            require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest), 'malformed')
            if record.get('paid_or_model_stage1_authorized') is not True:
                found.add(digest)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, Refused):
        raise Refused('The rights ledger cannot be read whole; the restricted inputs cannot be established.') from None
    require(records and found, 'The rights ledger names no restricted original; the restriction cannot be established.')
    return frozenset(found)


def _read_bounded(path, limit=8 * 1024 * 1024):
    """A regular file (never a link, never an environment file) of at most `limit` bytes, read whole."""
    pc.refuse_env_path(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise Refused(f'{path} cannot be opened ({type(error).__name__}).') from None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, f'{path} is not a regular file of at most {limit} '
                                                                      'bytes.')
        data = b''
        while chunk := os.read(fd, limit + 1 - len(data)):
            data += chunk
            require(len(data) <= limit, f'{path} is larger than {limit} bytes.')
        return data
    finally:
        os.close(fd)


def send_inputs(send, inputs):
    """{'form_sha256', 'notes_sha256'? | 'audio_sha256'?} of what `send` would put in a provider request: the fixed
    model-check case, a frozen mapping form, a frozen notes case, or an allowlisted synthetic recording and the frozen
    form its transcript is generated on — never anything else. (A transcript's notes are provider output: their sha256
    is known only once the transcription send has made them, and its generation attempt records it.)"""
    if send.path == 'model_check':
        return {'form_sha256': sq.FORM_SHA256, 'notes_sha256': sq.NOTES_SHA256}
    if send.path in TRANSCRIPTION_PATHS:
        return {'form_sha256': inputs['cases']['forms'][TRANSCRIPTION_FORM]['sha256'],
                'audio_sha256': audio_entry(send.case).sha256}
    if send.kind == 'mapping' or send.path == 'mapping_encounter':
        return {'form_sha256': inputs['forms_sha256'][f'mapping/{send.form}.docx']}
    case = next(c for c in inputs['cases']['cases'] if c['id'] == send.case)
    return {'form_sha256': inputs['cases']['forms'][case['form']]['sha256'], 'notes_sha256': sha256_text(case['notes'])}


# ── plan definitions ─────────────────────────────────────────────────────────────────────────────────────────────

def standing_plan(stage, inputs=None):
    """The sends of `stage`, in their fixed order (pure; `inputs` = sonnet5_stages.frozen_inputs() for every stage but
    model_check — for transcription with `transcription_audio`, the declared recordings (stage_inputs); without it, the
    whole allowlist, the plan's definition). Refuses a stage with no established plan (d30_d31_structure) rather than
    guess one."""
    stages = sq.stages_module()
    Send = stages.Send
    if stage == 'model_check':
        return [Send(1, MODEL_CHECK_SEND, 'generation', 'sonnet5-model-check', 'model_check', 'model_check', None,
                     'model_check')]
    if stage == 'transcription':
        chosen = (inputs or {}).get('transcription_audio')
        chosen = [audio.id for audio in TRANSCRIPTION_AUDIO] if chosen is None else list(chosen)
        require(chosen and all(audio_id in AUDIO_BY_ID for audio_id in chosen) and len(set(chosen)) == len(chosen),
                'The transcription plan sends allowlisted recordings only, each once.')
        sends = []
        for audio in TRANSCRIPTION_AUDIO:                       # (allowlist order, whatever order they were named in)
            if audio.id in chosen:
                sends.append(Send(len(sends) + 1, f'transcription:{audio.id}', 'transcription', TRANSCRIPTION_FORM,
                                  'transcription', 'transcription', audio.id, 'transcription'))
                sends.append(Send(len(sends) + 1, f'generation:{audio.id}', 'generation', TRANSCRIPTION_FORM,
                                  'transcription_generation', 'transcription', audio.id, 'transcription'))
        return sends
    if stage == 'mapping':
        return stages.plan_sends('mapping', inputs)
    if stage == 'notes_comparison':
        cases = sorted(inputs['cases']['cases'], key=lambda case: case['id'])
        compared = [case for case in cases if 'default' in case['send_paths']]
        require(len(compared) == NOTES_COMPARISON_CASES,
                f'The frozen notes set has {len(compared)} cases with a default send, not {NOTES_COMPARISON_CASES}.')
        sends = []
        for group, classes in stages.NOTES_GROUPS:
            for case in compared:
                if case['primary_class'] in classes:
                    sends.append(Send(len(sends) + 1, f'notes:{case["id"]}:default', 'generation', case['form'],
                                      'default', group, case['id'], 'ordinary_notes'))
        require(sorted(s.case for s in sends) == sorted(c['id'] for c in compared),
                'The comparison does not send every compared case once on the default request.')
        for case in compared:
            sends.append(Send(len(sends) + 1, f'notes:{case["id"]}:field_relations', 'generation', case['form'],
                              'field_relations', 'relations_last', case['id'], 'ordinary_notes_field_relations'))
        return sends
    if stage == 'd30_d31_structure':
        raise Refused(f'Stage d30_d31_structure: {D30_D31_NOT_ESTABLISHED}')
    raise Refused(f'No standing plan is defined for the stage {stage!r}.')


def plan_definitions(inputs):
    """Every stage's plan, as data (no declaration, credential, network or database)."""
    report = {}
    for stage in STAGE_KIND:
        try:
            sends = standing_plan(stage, inputs)
        except Refused as refused:
            report[stage] = {'established': False, 'statement': str(refused)}
            continue
        report[stage] = {'established': True, 'kind': STAGE_KIND[stage], 'pricing_keys': list(STAGE_PRICING[stage]),
                         'flags': STAGE_FLAGS[stage], 'sends': [{**s.record(), 'inputs': send_inputs(s, inputs)}
                                                                for s in sends], 'count': len(sends)}
        if stage == 'transcription':
            report[stage].update(
                provider=TRANSCRIPTION_PROVIDER, model=DEEPGRAM_MODEL, endpoint='POST ' + DEEPGRAM_URL,
                parameters={'model': DEEPGRAM_MODEL, 'smart_format': 'false', 'mip_opt_out': 'true'},
                audio=[audio.record() for audio in TRANSCRIPTION_AUDIO], form=TRANSCRIPTION_FORM,
                note='Every allowlisted recording is two sends: its transcription (the reviewed transcript then saved as '
                     'the notes) and the generation on that encounter. A declaration may narrow the recordings, never '
                     'add one; its per-minute rate is hashed into the transcription pricing version.')
    return report


def stage_inputs(stage, declaration):
    """What standing_plan reads for `stage` under `declaration`: nothing for model_check; the verified frozen
    diagnostics otherwise, and for transcription also the declared recordings."""
    if stage == 'model_check':
        return None
    inputs = sq.stages_module().frozen_inputs()
    if stage == 'transcription':
        require(declaration.transcription is not None, 'The declaration declares no transcription stage.')
        inputs = {**inputs, 'transcription_audio': declaration.transcription.inputs}
    return inputs


def needs(send):
    """The id of the send that must be made in the SAME run before `send` can be — a mapping encounter needs its form's
    proposal (sonnet5_stages.Run.templates), a transcript's generation needs the encounter its transcription send made
    (standing_qa_transcription.TranscriptionRun.transcribed), both held only in the request process — or None."""
    if send.path == 'mapping_encounter':
        return f'mapping:{send.form}'
    if send.path == 'transcription_generation':
        return f'transcription:{send.case}'
    return None


#: Why a stranded send is not sent, by its path (the mapping wording is the historical rule's, unchanged).
STRANDED_WHY = {'mapping_encounter': "needs its form's mapping send in the same run, and that send was already made; it "
                                     'is not sent',
                'transcription_generation': "needs its recording's transcription send in the same run, and that send "
                                            'was already made; it is not sent'}


def stranded(remaining):
    """The sends in `remaining` whose prerequisite send (needs) is not in it — it was made in an earlier run. Each needs
    what that send made in the same process, so it can never be sent in this campaign, and a stage with one left can
    never pass here."""
    ids = {send.id for send in remaining}
    return [send for send in remaining if needs(send) is not None and needs(send) not in ids]


def require_none_stranded(stage, remaining):
    """The historical rule (sonnet5_stages.pending_sends, f5fe720f): a remainder holding an encounter whose form's mapping
    send was already made — or a transcript generation whose recording's transcription send was — is refused WHOLE,
    before anything is written: it is not sent, and nothing else is. Refutation R1-F2/R2-F1: setting such a send aside
    as `not_exercised` let the stage PASS with it never sent."""
    found = stranded(remaining)
    require(not found, '; '.join(f'{send.id} {STRANDED_WHY[send.path]}' for send in found)
            + ('.' if stage is None else
               f'. Stage {stage} cannot pass in this campaign: its remainder is not sent (a later campaign, a new '
               'declaration <YYYYMMDD>-quillmd-v1-standing-api-testing-<n>.md, measures the stage again).'))
    return remaining


def select_batch(remaining, cap):
    """The next sends of a run: in plan order, at most `cap`; a send and the send that needs it in the same process (a
    mapping form and its encounter, a recording's transcription and its generation) are selected together or not at
    all. A remainder with a stranded send is refused (require_none_stranded) — it is never set aside."""
    require_none_stranded(None, remaining)
    chosen = set()
    for send in remaining:
        if needs(send) is not None:
            continue                                    # (selected with the send it needs)
        group = [send.id] + [other.id for other in remaining if needs(other) == send.id]
        if len(chosen) + len(group) > cap:
            break                                       # (the next run starts with this send, or this pair)
        chosen.update(group)
    require(chosen, f'No send fits in a run of {cap}.')
    return [send for send in remaining if send.id in chosen]


# ── the ledger, the runs and admission ───────────────────────────────────────────────────────────────────────────

RUN_FILE = re.compile(r'(\d{4})-(run|closed)\.json')


class StopFileHalt(Refused):
    """The operator's Stop file refused something (StandingCampaign.require_not_stopped, and nothing else raises it). Met
    by a send BEFORE its attempt was written — anywhere: the loop's own check, a preview admission, the admission or
    the attempt record — it halts the run (L1:R1-F4 / L2:R2-F2: a Stop file appearing after the loop's check used to
    fail the stage)."""


def stopped_by_halt(error):
    """Whether `error` is the Stop file's refusal, or the job refusal raised while handling it: sonnet5_stages.Run.
    refuse_job cancels the queued job and raises StageStop INSIDE the `except Refused` that caught the admission's
    refusal, so the halt is exactly that StageStop's implicit context. Decided by exception TYPE, one link deep, never
    by message text: a stop with any other cause — even while a Stop file exists — stays a stop."""
    if isinstance(error, StopFileHalt):
        return True
    return isinstance(error, sq.stages_module().StageStop) and isinstance(error.__context__, StopFileHalt)


class Runs:
    """Write-once run records: NNNN-run.json when a run opens (its stage, the sends it selected, its cap, the inputs it
    allows and the restricted ones), NNNN-closed.json when it closes. Gapless; at most one open, the last."""

    def __init__(self, directory):
        self.dir = Path(directory)

    def listing(self):
        if not self.dir.exists():
            return []
        found = {}
        for name in sorted(os.listdir(self.dir)):
            if name.startswith('.partial-'):
                continue
            match = RUN_FILE.fullmatch(name)
            require(match, f'The run records hold a file that is not a run record: {name}.')
            found.setdefault(int(match.group(1)), {})[match.group(2)] = self.dir / name
        numbers = sorted(found)
        require(numbers == list(range(1, len(numbers) + 1)), f'The run records are not a gapless sequence: {numbers}.')
        rows = []
        for number in numbers:
            require('run' in found[number], f'Run {number} has a closing record and no opening one.')
            opened = pc.read_json(found[number]['run'])
            closed = pc.read_json(found[number]['closed']) if 'closed' in found[number] else None
            require(isinstance(opened, dict) and opened.get('run') == number
                    and (closed is None or (isinstance(closed, dict) and closed.get('run') == number)),
                    f'Run record {number:04d} is labelled with another number.')
            rows.append((opened, closed))
        open_runs = [opened['run'] for opened, closed in rows if closed is None]
        require(open_runs in ([], [len(rows)]), f'More than one run is open, or an earlier one is: {open_runs}.')
        return rows

    def current(self):
        rows = self.listing()
        return rows[-1][0] if rows and rows[-1][1] is None else None

    def closed_numbers(self):
        return {opened['run'] for opened, closed in self.listing() if closed is not None}

    def begin(self, ledger, document):
        ledger._require_lock()
        pc.private_directory(self.dir)
        require(self.current() is None, 'A run is already open; it is closed (or settled) first.')
        number = len(self.listing()) + 1
        record = {**document, 'run': number, 'run_id': f'run-{number:04d}', 'opened_at': pc.now(), 'pid': os.getpid()}
        pc.write_new(self.dir / f'{number:04d}-run.json', record)
        return record

    def close(self, ledger, number, document):
        ledger._require_lock()
        current = self.current()
        require(current is not None and current['run'] == number, f'Run {number} is not the open run.')
        record = {**document, 'run': number, 'run_id': current['run_id'], 'closed_at': pc.now()}
        pc.write_new(self.dir / f'{number:04d}-closed.json', record)
        return record


class StandingLedger(pc.Ledger):
    """The historical append-only ledger, with this campaign's identities and its last door before any send."""

    def __init__(self, directory, campaign):
        super().__init__(directory)
        self.campaign = campaign

    def write_attempt(self, attempt):
        """BEFORE any send. Adds the run and attempt identities and the send key, and refuses: the operator Stop file or
        a campaign stop; an attempt outside an open run, of another stage, campaign or authority, or for a send its run
        did not select; a send that already has an attempt in this campaign (duplicates); an attempt past its run's
        cap; an input that is not one its run allows, or that is a restricted development original."""
        self._require_lock()
        campaign = self.campaign
        declaration = campaign.declaration
        campaign.require_not_stopped()
        run = campaign.runs.current()
        require(run is not None, 'An attempt is written only inside an open run.')
        require(attempt.get('campaign') == declaration.campaign and attempt.get('authority_id') == declaration.authority_id
                and attempt.get('stage') == run['stage'],
                'The attempt names another campaign, authority or stage than its run.')
        send = attempt.get('send') if isinstance(attempt.get('send'), dict) else None
        if send is None and attempt.get('stage') == 'model_check':
            send = attempt['send'] = {'id': MODEL_CHECK_SEND}
        send_id = (send or {}).get('id')
        require(isinstance(send_id, str) and send_id in run['sends'], f'The attempt is for a send its run did not select '
                                                                      f'({send_id!r}).')
        send_key = f'{attempt["stage"]}:{send_id}'
        rows = self.rows()
        require(all(outcome is not None for _, outcome in rows), 'An earlier attempt has no outcome; reconcile first.')
        require(not any(a.get('send_key') == send_key for a, _ in rows),
                f'{send_key} already has an attempt in this campaign; a send is never made twice.')
        in_run = sum(1 for a, _ in rows if a.get('run') == run['run'])
        require(in_run < run['max_sends'], f'Run {run["run_id"]} has made all {run["max_sends"]} sends it may make.')
        form = attempt.get('form_sha256')
        require(isinstance(form, str) and form in run['allowed_inputs'],
                'The attempt\'s form is not one of the synthetic inputs its run allows.')
        require(form not in set(run['restricted_inputs']),
                'The attempt\'s form is a development original marked "no provider upload"; it is never sent.')
        if attempt['stage'] == 'transcription' or 'audio_sha256' in attempt:
            # (a recording is the runner's allowlisted synthetic speech for THIS send, one its run allows, and never a
            # restricted original — whatever the worker or a run record says)
            audio = attempt.get('audio_sha256')
            entry = AUDIO_BY_ID.get((send or {}).get('case'))
            require((send or {}).get('path') in TRANSCRIPTION_PATHS and entry is not None and audio == entry.sha256,
                    'The attempt\'s recording is not the allowlisted synthetic speech its send names; only allowlisted '
                    'synthetic speech is ever sent for transcription.')
            require(audio in run['allowed_inputs'], 'The attempt\'s recording is not one its run allows.')
            require(audio not in set(run['restricted_inputs']),
                    'The attempt\'s recording is marked "no provider upload"; it is never sent.')
        attempt.update(mode=MODE, monetary_ceiling=None, run=run['run'], run_id=run['run_id'],
                       attempt_id=f'{declaration.campaign}/{run["run_id"]}/attempt-{attempt["number"]:03d}',
                       send_key=send_key, engine_files=watched_hashes())
        return super().write_attempt(attempt)

    def undecided(self, rows=None):
        """The historical rule, except that an attempt its CLOSED run recorded is decided for now: a stage runs over
        several bounded runs before its decision."""
        rows = self.rows() if rows is None else rows
        found = super().undecided(rows)
        closed = self.campaign.runs.closed_numbers()
        run_of = {attempt['number']: attempt.get('run') for attempt, _ in rows}
        kept = {}
        for stage, numbers in found.items():
            left = [number for number in numbers if run_of.get(number) not in closed]
            if left:
                kept[stage] = left
        return kept


class StandingCampaign(pc.Campaign):
    """A standing declaration and the ledger that sends under it. Admission enforces no money limit (there is none) and
    every non-monetary control; the per-send machinery is the historical campaign's own."""

    def __init__(self, declaration, root=None, *, watched_files=WATCHED_FILES):
        require(isinstance(declaration, StandingDeclaration), 'A standing campaign needs a standing declaration.')
        super().__init__(declaration, declaration.root if root is None else root, watched_files=watched_files)
        require(not _inside(self.root, HISTORICAL['root']), 'The historical campaign\'s root is never a standing root.')
        self.ledger = StandingLedger(self.root / 'ledger', self)
        self.runs = Runs(self.root / 'runs')

    def stop_file(self):
        return self.root / STOP_NAME

    def require_not_stopped(self):
        """The operator's Stop file refuses with StopFileHalt — a HALT wherever it is met during a run, never a failure
        (stopped_by_halt); a campaign stop refuses with a plain Refused."""
        if os.path.lexists(self.stop_file()):
            raise StopFileHalt(f'The Stop file {self.stop_file()} exists; nothing is sent.')
        require(self.ledger.campaign_stop() is None, 'The campaign is stopped (campaign-stop.json).')

    def rows(self):
        rows = super().rows()
        for attempt, _ in rows:
            require(attempt.get('mode') == MODE and attempt.get('monetary_ceiling', 'missing') is None
                    and type(attempt.get('run')) is int and isinstance(attempt.get('attempt_id'), str)
                    and isinstance(attempt.get('send_key'), str),
                    f'Attempt {attempt.get("number")} is not a standing campaign attempt (mode, run, identity).')
        return rows

    def totals(self, stage=None):
        """The historical totals, with a transcription send costed by its own measure (attempt_exposure). Accounting
        only: there is no money limit to compare it with."""
        every = self.rows()
        rates = self.pinned_terms(every).rates
        rows = [(a, o) for a, o in every if stage is None or a['stage'] == stage]
        return {'attempts': len(rows), 'exposure': sum((attempt_exposure(a, o, rates) for a, o in rows), Decimal(0)),
                'open': sum(1 for _, o in rows if o is None),
                'unknown': sum(1 for a, o in rows if o is None or o.get('class') != 'completed'
                               or known_attempt_cost(a, o, rates) is None)}

    def pinned_limits(self, attempt):
        require('limits' in attempt, f'Attempt {attempt.get("number")} records no limits; the limits in force cannot be '
                                     'established.')
        return StandingLimits.from_record(attempt['limits'], f'Attempt {attempt.get("number")}')

    def stage_open(self, stage_id, rows=None):
        """Everything admission requires that needs no request yet: not stopped, reconciled, the pinned terms, the stage
        neither failed nor passed, and its prerequisites passed. Returns the stage's limit in force."""
        stage = self.declaration.stage(stage_id)
        self.require_not_stopped()
        state = self.ledger.stage_state(stage.id)
        require(state['state'] != 'failed', f'Stage {stage.id} failed; that path is stopped until a committed diagnosis '
                                            'and repair reopen it.')
        require(state['state'] != 'passed', f'Stage {stage.id} already passed; it is never re-run in place.')
        rows = self.rows() if rows is None else rows
        require(all(outcome is not None for _, outcome in rows), 'An attempt has no outcome; reconcile before admitting.')
        self.require_pinned_terms(rows)
        in_force = self.limits(rows).stage(stage.id)
        for prerequisite in in_force.requires:
            require(self.ledger.stage_state(prerequisite)['state'] == 'passed',
                    f'Stage {stage.id} requires {prerequisite} to have passed with recorded evidence.')
        return state, in_force

    def admit(self, stage_id, maximum_cost, *, runner_commit=None):
        """Refuses (with the reason) before the request is built: the Stop file or a campaign stop; an attempt without an
        outcome; terms other than the pinned ones; a failed (unreopened) or passed stage; a prerequisite not passed; a
        reopened stage on a runner without the repair; no open run of this stage; the run's cap; the stage's declared
        send count. Returns the attempt's recorded exposure bound (maximum x 1.1) — accounting only: there is no money
        limit to compare it with."""
        maximum = pc.money(maximum_cost)
        require(maximum > 0, 'An attempt has a positive maximum cost.')
        rows = self.rows()
        state, in_force = self.stage_open(stage_id, rows)
        if state['reopenings']:
            self._require_repaired_runner(stage_id, state['reopened'][-1], runner_commit)
        here = [a for a, _ in rows if a['stage'] == stage_id]
        require(len(here) + 1 <= in_force.max_requests, f'Stage {stage_id} has made all {in_force.max_requests} sends '
                                                         'it declares.')
        run = self.runs.current()
        require(run is not None and run['stage'] == stage_id, f'No run of stage {stage_id} is open.')
        in_run = sum(1 for a, _ in rows if a.get('run') == run['run'])
        require(in_run + 1 <= run['max_sends'], f'Run {run["run_id"]} has made all {run["max_sends"]} sends it may make.')
        return maximum * pc.GEO_MARGIN


def known_attempt_cost(attempt, outcome, rates):
    """provider_campaign.known_cost, except for a transcription send, which has no tokens: its outcome's
    `provider_cost` (the response's duration at the declared per-minute rate), or None when it is not known."""
    if (attempt.get('send') or {}).get('path') != 'transcription':
        return pc.known_cost(attempt, outcome, rates)
    value = (outcome or {}).get('provider_cost')
    try:
        cost = pc.money(value)
    except Refused:
        return None
    return cost if cost >= 0 else None


def attempt_exposure(attempt, outcome, rates):
    """provider_campaign.exposure, with a transcription send's known cost read by known_attempt_cost (the same rules:
    completed and known — that cost; not_sent — zero; otherwise the maximum x 1.1, or the known cost if higher)."""
    if (attempt.get('send') or {}).get('path') != 'transcription':
        return pc.exposure(attempt, outcome, rates)
    bound = pc.attempt_bound(attempt['maximum_cost'])
    if outcome is None:
        return bound
    if outcome.get('class') == 'not_sent':
        return Decimal(0)
    known = known_attempt_cost(attempt, outcome, rates)
    if outcome.get('class') == 'completed' and known is not None:
        return known
    return max(bound, known) if known is not None else bound


def settle(campaign):
    """Reconciliation before anything new: an attempt without an outcome is recorded interrupted_unknown and its stage
    failed (the historical rule, sonnet5_qa.settle_open_stages); then a run left open by a dead process is closed as
    interrupted. Needs the lock."""
    ledger = campaign.ledger
    ledger._require_lock()
    settled = sq.settle_open_stages(campaign)
    dangling = campaign.runs.current()
    if dangling is not None:
        numbers = [a['number'] for a, _ in ledger.rows() if a.get('run') == dangling['run']]
        campaign.runs.close(ledger, dangling['run'], {
            'closed_as': 'interrupted', 'attempts': numbers,
            'reason': 'The runner ended before this run was closed; its attempts are reconciled and its stage, if it was '
                      'open, is failed. Nothing is re-sent.'})
    return {**settled, 'run_closed_as_interrupted': dangling['run'] if dangling else None}


def recorded_rows(campaign, stage):
    """{attempt number: [per-send rows]} recorded for `stage` by the closed runs and the stage's decisions."""
    rows = {}

    def add(row):
        if isinstance(row, dict) and type(row.get('attempt')) is int:
            text = json.dumps(row, sort_keys=True, default=str)
            entries = rows.setdefault(row['attempt'], {})
            entries[text] = row
    for opened, closed in campaign.runs.listing():
        if closed is not None and opened.get('stage') == stage:
            for row in closed.get('sends') or []:
                add(row)
    state = campaign.ledger.stage_state(stage)
    for record in state['failed'] + ([state['passed']] if state['passed'] else []):
        summary = record.get('summary') if isinstance(record.get('summary'), dict) else {}
        for row in summary.get('sends') or []:
            add(row)
    return {number: list(entries.values()) for number, entries in rows.items()}


def earlier_stops(campaign, stage, current=()):
    """The attempts of `stage` outside `current` that did not end clean: exactly one recorded row, for the send the
    attempt records, saying it did not stop the stage — anything else (a stop, an interruption, no row) is returned. A
    send is never made twice, so while any is left the stage can NEVER pass (the historical rule)."""
    rows, found, current = recorded_rows(campaign, stage), [], set(current)
    for attempt, _ in campaign.ledger.rows():
        number = attempt.get('number')
        if attempt.get('stage') != stage or number in current:
            continue
        named = rows.get(number, [])
        send = (attempt.get('send') or {}).get('id')
        if len(named) != 1:
            why = 'no record of the stage says how it ended' if not named else 'its records disagree'
        elif (named[0].get('send') or {}).get('id') != send:
            why = 'its record names another send'
        elif named[0].get('stops_stage') is not False:
            why = f'it stopped the stage ({named[0].get("recorded_as") or "no reason recorded"})'
        else:
            continue
        found.append({'send': send, 'attempt': number, 'why': why})
    return found


def remaining_sends(campaign, stage, plan):
    """The plan's sends with no attempt in this campaign and not recorded as not exercisable (duplicates are never
    planned), in plan order. A row is `not_exercised` only when the worker found an encounter it could not confirm
    without removing a field (sonnet5_stages.Run.encounter_send), never because its form was mapped in another run."""
    attempted = {(a.get('send') or {}).get('id') for a, _ in campaign.ledger.rows() if a.get('stage') == stage}
    unexercised = set()
    for opened, closed in campaign.runs.listing():
        if closed is not None and opened.get('stage') == stage:
            unexercised |= {row['send']['id'] for row in closed.get('sends') or []
                            if isinstance(row, dict) and 'not_exercised' in row and isinstance(row.get('send'), dict)}
    return [send for send in plan if send.id not in attempted and send.id not in unexercised]


# ── the configuration of the request process ─────────────────────────────────────────────────────────────────────

def settings_snapshot(stage):
    """What check_configuration judges, read from Django in the request process."""
    from django.conf import settings
    from django.db import connection
    from core import generation
    database = connection.settings_dict
    config = generation.configuration()
    return {'database': {'NAME': str(database['NAME']), 'HOST': str(database['HOST']), 'PORT': str(database['PORT'])},
            'state_dir': str(settings.STATE_DIR), 'media_root': str(settings.MEDIA_ROOT),
            'synthetic_only': settings.SYNTHETIC_ONLY, 'data_mode': settings.QUILLMD_DATA_MODE,
            'ai_mode': settings.AI_MODE, 'provider': settings.AI_PROVIDER, 'model': settings.AI_MODEL,
            'rates': {'input': settings.AI_INPUT_RATE, 'output': settings.AI_OUTPUT_RATE, 'cached': settings.AI_CACHED_RATE},
            'thinking': settings.AI_THINKING, 'effort': settings.AI_EFFORT, 'inference_geo': settings.AI_INFERENCE_GEO,
            'settings': {name: getattr(settings, name) for name, _ in FLAG_SETTINGS.values()},
            'voice_rates': {'minute': os.environ.get('QUILLMD_DEEPGRAM_RATE_PER_MINUTE', ''),
                            'second': os.environ.get('QUILLMD_DEEPGRAM_RATE_PER_SECOND', '')},
            'request_profile': config['request_profile'], 'pricing_version': config['pricing_version']}


def stage_flags(stage, declaration):
    """The request process's settings for `stage`: STAGE_FLAGS, and for transcription the declared per-minute rate (and
    no per-second rate) — which overrides the historical PRICE_SETTINGS rate in request_environment."""
    flags = dict(STAGE_FLAGS[stage])
    if stage == 'transcription':
        require(declaration.transcription is not None, 'The declaration declares no transcription stage.')
        flags.update(QUILLMD_DEEPGRAM_RATE_PER_MINUTE=declaration.transcription.rate_per_minute,
                     QUILLMD_DEEPGRAM_RATE_PER_SECOND='',
                     QUILLMD_DEEPGRAM_SMART_FORMAT=declaration.transcription.smart_format)
    return flags


def expected_settings(stage, declaration=None):
    """The Django settings values the stage's flags mean (with a declaration, its declared transcription terms)."""
    values = {}
    flags = (stage_flags(stage, declaration) if declaration is not None and stage == 'transcription'
             and declaration.transcription is not None else STAGE_FLAGS[stage])
    for flag, value in flags.items():
        if flag in FLAG_SETTINGS:
            name, kind = FLAG_SETTINGS[flag]
            values[name] = (value == '1') if kind is bool else value
    return values


def check_configuration(snapshot, declaration, stage, root, *, rebuild=REBUILD, limits=None):
    """Every problem with the request process's configuration for `stage` (empty: it may proceed). Pure: `snapshot` is
    settings_snapshot()'s shape. The installed route (its tree, database and state), any database but the declared
    synthetic QA one, a contract flag other than the stage's, and a profile outside the per-request bounds are each a
    problem."""
    limits = declaration.limits() if limits is None else limits
    problems = []
    if _inside(rebuild, INSTALLED['tree']):
        problems.append(f'the runner checkout is the installed tree {INSTALLED["tree"]} (the installed worker route)')
    database = snapshot.get('database') or {}
    if str(database.get('PORT')) == INSTALLED['database_port']:
        problems.append(f'the database is the installed release\'s (port {INSTALLED["database_port"]})')
    if (str(database.get('HOST')), str(database.get('PORT'))) != (QA_SERVER['host'], QA_SERVER['port']):
        problems.append(f'the database is not the QA server {QA_SERVER["host"]}:{QA_SERVER["port"]}')
    if database.get('NAME') != declaration.qa_database or database.get('NAME') == HISTORICAL['database']:
        problems.append(f'the database is not the declared synthetic QA database {declaration.qa_database}')
    root = Path(os.path.abspath(str(root)))
    state, media = Path(os.path.abspath(str(snapshot.get('state_dir', '')))), Path(os.path.abspath(
        str(snapshot.get('media_root', ''))))
    if not (root in state.parents and (media == state or state in media.parents)):
        problems.append('STATE_DIR (and its files) is not under the campaign root')
    if any(_inside(state, installed) for installed in INSTALLED['state_dirs']):
        problems.append('STATE_DIR is the installed release\'s state')
    if not (snapshot.get('synthetic_only') is True and snapshot.get('data_mode') == 'synthetic'):
        problems.append('the process is not in synthetic-only mode')
    if snapshot.get('ai_mode') != 'live':
        problems.append('the process is not in live AI mode')
    if (snapshot.get('provider'), snapshot.get('model')) != (declaration.provider, declaration.model):
        problems.append(f'the configured provider/model is not {declaration.provider}/{declaration.model}')
    if snapshot.get('rates') != declaration.rates.as_dict():
        problems.append('the configured rates are not the declared rates')
    if (snapshot.get('thinking'), snapshot.get('effort'), snapshot.get('inference_geo')) != (
            declaration.thinking, declaration.effort, declaration.inference_geo):
        problems.append('the configured thinking, effort or inference geography is not the declared one')
    flags = snapshot.get('settings') or {}
    for name, value in expected_settings(stage, declaration).items():
        if flags.get(name) != value:
            problems.append(f'the contract flag {name} is {flags.get(name)!r}, not {value!r} for stage {stage}')
    if not sq.stages_module().within_bounds(snapshot.get('request_profile'), declaration.expect(limits)):
        problems.append('the request profile is invalid or outside the per-request bounds '
                        f'({limits.max_output_tokens_per_request} output tokens, {limits.request_deadline_seconds} s)')
    key = STAGE_PRICING[stage][0]
    if snapshot.get('pricing_version') != declaration.pricing_version(key):
        problems.append(f'the application prices {snapshot.get("pricing_version")}, not the declared {key} version')
    if stage == 'transcription':
        terms = declaration.transcription
        if terms is None:
            problems.append('the declaration declares no transcription terms')
        elif snapshot.get('voice_rates') != {'minute': terms.rate_per_minute, 'second': ''}:
            problems.append(f'the transcription rate is not the declared {terms.rate_per_minute} USD per minute (and no '
                            'per-second rate)')
    return problems


# ── the model-access preflight ───────────────────────────────────────────────────────────────────────────────────

def _preflight_transport_class():
    import httpx

    class PreflightTransport(httpx.BaseTransport):
        """ONE request: GET <models URL of the declared model>. Recorded (no credential header) BEFORE it is sent; the
        response retained as received; anything else, or a second request, refused before it leaves."""

        def __init__(self, inner, url, evidence, secret):
            self.inner, self.url, self.evidence, self.secret, self.sent = inner, url, Path(evidence), secret, False

        def handle_request(self, request):
            require(not self.sent, 'A second preflight request was refused; the preflight makes one request.')
            require(request.method == 'GET' and str(request.url) == self.url,
                    f'A preflight request {request.method} {request.url.host}{request.url.path} was refused; only '
                    f'GET {self.url} is made.')
            # The credential on the wire is exactly the declared key, and nothing else authenticates the request (an SDK
            # credential provider or profile would add Authorization). Checked here, on the request itself, rather than
            # on the client object, so the cost scanner can still trace the client as a provider-call root.
            require(request.headers.get('x-api-key') == self.secret and 'authorization' not in request.headers,
                    'The preflight request does not carry exactly the declared credential; refused before it leaves.')
            record = pc.capture_record(request, self.secret)
            record.update(captured_at=pc.now())
            pc.write_new(self.evidence / 'request.json', record)
            self.sent = True
            response = self.inner.handle_request(request)
            response.read()
            received = pc.response_record(response, self.secret)
            received.update(received_at=pc.now())
            pc.write_new(self.evidence / pc.RESPONSE_BODY, response.content, raw=True)
            pc.write_new(self.evidence / pc.RESPONSE_FILE, received)
            return response

        def close(self):
            self.inner.close()
    return PreflightTransport


PREFLIGHT_DIR = re.compile(r'(\d{3})')
PREFLIGHT_STATEMENT = ('The models endpoint was asked about the declared model id. This is MODEL ACCESS evidence only: it '
                       'is free, sends no clinical or synthetic content, and proves nothing about generation, its request '
                       'profile, its price or its output.')


def preflights(root):
    """[(number, result or None)] of every preflight under `root`, in order."""
    base = Path(root) / 'preflight'
    if not base.exists():
        return []
    found = []
    for name in sorted(os.listdir(base)):
        if not PREFLIGHT_DIR.fullmatch(name):
            continue
        result = base / name / 'result.json'
        found.append((int(name), pc.read_json(result) if result.is_file() else None))
    return found


def require_preflight(campaign):
    """A recorded preflight whose returned id is the declared model, for this campaign."""
    matched = [result for _, result in preflights(campaign.root) if isinstance(result, dict)
               and result.get('matches_declared') is True and result.get('model_returned') == campaign.declaration.model
               and result.get('campaign') == campaign.declaration.campaign]
    require(matched, f'No preflight has shown the provider serving {campaign.declaration.model} to this credential; run '
                     '`preflight` first (free).')
    return matched[-1]


def run_preflight(campaign, *, secret, transport=None):
    """The ONE models request, its evidence and its result. `transport`: the transport the guard wraps (the network by
    default; a MockTransport in tests). Needs the lock; refuses under the Stop file."""
    import anthropic
    import httpx
    declaration = campaign.declaration
    campaign.ledger._require_lock()
    campaign.require_not_stopped()
    base = pc.private_directory(campaign.root / 'preflight')
    number = len(preflights(campaign.root)) + 1
    evidence = base / f'{number:03d}'
    evidence.mkdir(mode=0o700)
    url = MODELS_URL + declaration.model
    guard = _preflight_transport_class()(transport or httpx.HTTPTransport(), url, evidence, secret)
    client = anthropic.Anthropic(api_key=secret, base_url=PROVIDER_ROOT, max_retries=0,
                                 timeout=PREFLIGHT_TIMEOUT_SECONDS,
                                 http_client=httpx.Client(transport=guard, timeout=PREFLIGHT_TIMEOUT_SECONDS))
    error = None
    try:
        # No retry is possible: the guard refuses any second request; the credential is checked on the request.
        client.models.retrieve(declaration.model)
    except anthropic.APIStatusError as failure:
        error = {'class': type(failure).__name__, 'status_code': failure.status_code}
    except anthropic.APIError as failure:
        error = {'class': type(failure).__name__, 'status_code': None}
    finally:
        client.close()
    received = pc.received_response(evidence)
    body = (received or {}).get('body_json')
    body = body if isinstance(body, dict) else {}
    result = {'campaign': declaration.campaign, 'authority_id': declaration.authority_id, 'preflight': number,
              'declaration': {'path': declaration.path, 'sha256': declaration.sha256, 'commit': declaration.commit},
              'endpoint': 'GET ' + url, 'model_requested': declaration.model, 'model_returned': body.get('id'),
              'display_name': body.get('display_name'), 'created_at': body.get('created_at'), 'type': body.get('type'),
              'max_input_tokens': body.get('max_input_tokens'), 'max_tokens': body.get('max_tokens'),
              'status_code': (received or {}).get('status_code'), 'request_id': (received or {}).get('request_id'),
              'request_captured': (evidence / 'request.json').exists(), 'error': error,
              'generation_proof': False, 'statement': PREFLIGHT_STATEMENT, 'recorded_at': pc.now()}
    result['matches_declared'] = bool(received is not None and received.get('status_code') == 200 and error is None
                                      and body.get('id') == declaration.model)
    try:
        hits = pc.leaked(evidence, secret)
    except pc.Refused as refused:
        hits = [f'unscannable: {refused}']
    if hits:
        result.update(matches_declared=False, leak=hits)
        campaign.ledger.write_stop({'reason': 'the preflight evidence could not be scanned, or carries the credential',
                                    'detail': hits})
    pc.write_new(evidence / 'result.json', result)
    return result


# ── the stage runs ───────────────────────────────────────────────────────────────────────────────────────────────

def begin_run(campaign, stage, sends, inputs, cap, provenance):
    """Opens a run for `sends` (already selected): its allowed inputs, and the restricted originals, recorded first."""
    restricted = restricted_hashes(campaign.declaration)
    allowed = sorted({digest for send in sends for name, digest in send_inputs(send, inputs).items()
                      if name in ('form_sha256', 'audio_sha256')})
    clash = sorted(set(allowed) & restricted)
    require(not clash, 'A planned input is a development original marked "no provider upload": ' + ', '.join(clash))
    extra = {}
    if stage == 'transcription':
        terms = campaign.declaration.transcription
        require(terms is not None and all(send.case in terms.inputs for send in sends),
                'A transcription run sends only the recordings its declaration names.')
        extra['audio'] = [audio_entry(audio_id).record() for audio_id in dict.fromkeys(send.case for send in sends)]
    return campaign.runs.begin(campaign.ledger, {
        'campaign': campaign.declaration.campaign, 'authority_id': campaign.declaration.authority_id, 'stage': stage,
        'sends': [send.id for send in sends], 'max_sends': cap, 'allowed_inputs': allowed,
        'restricted_inputs': sorted(restricted), 'monetary_ceiling': None,
        'declaration': {'sha256': campaign.declaration.sha256, 'commit': campaign.declaration.commit},
        'runner_commit': provenance.get('runner_commit'), **extra})


def run_model_check(campaign, *, secret, provenance, environ=None, rebuild=REBUILD, database_prefix=sq.DATABASE_PREFIX):
    """One run of the model check: the historical campaign's own end-to-end model check (sonnet5_qa.run_model_check:
    the real views and worker, the fixed case, the review, finalization, the verified export, the billing audit, the
    leak scan and the stage decision) inside a standing run, with this campaign's expectations and deadline."""
    declaration, ledger = campaign.declaration, campaign.ledger
    ledger.acquire()
    settled = settle(campaign)
    require_preflight(campaign)
    plan = standing_plan('model_check')
    _, in_force = campaign.stage_open('model_check')
    require(len(plan) == in_force.max_requests, f'model_check declares {in_force.max_requests} sends; its plan has '
                                                f'{len(plan)}.')
    remaining = remaining_sends(campaign, 'model_check', plan)
    require(remaining, 'The model check already has its attempt in this campaign; a send is never made twice.')
    limits = campaign.limits()
    run = begin_run(campaign, 'model_check', remaining, None, 1, provenance)
    try:
        result = sq.run_model_check(campaign, secret=secret, provenance=provenance, environ=environ, rebuild=rebuild,
                                    database_prefix=database_prefix, expect=declaration.expect(limits),
                                    deadline=limits.request_deadline_seconds)
    except Refused as refused:
        if stopped_by_halt(refused):
            # (the Stop file met inside the model check before its attempt was written — its preview admission, its
            # admission or its attempt record: a halt, as in a stage run; a job it had queued is cancelled)
            halted = (f'the Stop file {campaign.stop_file()} appeared during {MODEL_CHECK_SEND}, before its attempt was '
                      'written; it was not made')
            jobs = cancel_queued(None)
            campaign.runs.close(ledger, run['run'], {'closed_as': 'halted', 'sends': [], 'not_sent': [MODEL_CHECK_SEND],
                                                     'reasons': [], 'halted': halted, 'halt_jobs': jobs})
            return {'stage': 'model_check', 'run': run['run_id'], 'verdict': 'HALTED', 'decision': 'halted',
                    'reasons': [], 'halted': halted, 'halt_jobs': jobs, 'settled_before_start': settled}
        campaign.runs.close(ledger, run['run'], {'closed_as': 'refused_before_attempt', 'reason': str(refused),
                                                 'sends': []})
        raise
    row = {'send': {'id': MODEL_CHECK_SEND}, 'attempt': result.get('attempt'), 'stops_stage': result['verdict'] != 'PASS',
           'recorded_as': None if result['verdict'] == 'PASS' else 'failed', 'reasons': result.get('reasons')}
    campaign.runs.close(ledger, run['run'], {'closed_as': 'decided', 'verdict': result['verdict'], 'sends': [row]})
    return {**result, 'run': run['run_id'], 'settled_before_start': settled}


def price_sends(stage, sends, inputs, state_dir, declaration, limits=None):
    """Each send's maximum, computed by the application under the stage's settings (Django configured; nothing is sent
    and no database is touched): the declared pricing version per send, and a request profile inside the per-request
    bounds. Unlike the historical plan, no frozen bound is compared: those describe claude-sonnet-5."""
    from types import SimpleNamespace
    from django.test.utils import override_settings
    from core import generation, mapping_assistance
    from documents import service
    stages = sq.stages_module()
    limits = declaration.limits() if limits is None else limits
    expect = declaration.expect(limits)
    forms = stages.build_forms(Path(state_dir) / 'forms', 'mapping' if stage == 'mapping' else 'ordinary_notes', inputs) \
        if stage != 'model_check' else {}
    originals = Path(state_dir) / 'files' / 'originals'
    originals.mkdir(parents=True, exist_ok=True)
    priced, fields_of = {}, {}
    for send in sends:
        flags = stages.steps.PATH_FLAGS.get(send.path, {})
        with override_settings(MEDIA_ROOT=Path(state_dir) / 'files', **flags):
            if send.path == 'model_check':
                fields = [{'key': f'cell_{i}', 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                          for i, label in enumerate(sq.FORM_LABELS)]
            elif send.kind == 'mapping' or send.path == 'mapping_encounter':
                path = originals / f'{send.form}.docx'
                path.write_bytes(forms[send.form])
                fields = fields_of.get(send.form) or service.inspect_template(str(path), engine='v3')['fields']
                fields_of[send.form] = fields
            else:
                fields = inputs['cases']['forms'][send.form]['fields']
            config = generation.configuration(fields if send.kind == 'generation' else None)
            require(config['pricing_version'] == declaration.pricing_version(send.pricing_key),
                    f'{send.id}: the application prices {config["pricing_version"]}, not the declared '
                    f'{send.pricing_key}.')
            profile = config['request_profile']
            if send.kind == 'mapping':
                version = SimpleNamespace(template=SimpleNamespace(format='docx', sha256=hashlib.sha256(
                    forms[send.form]).hexdigest(), original_path=f'originals/{send.form}.docx'), contract='v3',
                    document_backend={}, fields=fields)
                profile = mapping_assistance.request_profile(config)
                maximum = Decimal(mapping_assistance.compile_request(version, config)['maximum_cost'])
            elif send.path == 'model_check':
                maximum = generation.maximum_cost(sq.NOTES, fields, config, context_labels=[], requirements=[])
            elif send.path == 'mapping_encounter':
                notes = (inputs['long_answer'] if send.form == 'f6a-long-answer'
                         else inputs['maps'][send.form]['source_note']['text'])
                maximum = generation.maximum_cost(notes, fields, config, context_labels=[], requirements=[])
            else:
                case = next(c for c in inputs['cases']['cases'] if c['id'] == send.case)
                maximum = generation.maximum_cost(case['notes'], fields, config, context_labels=[], requirements=[])
            require(stages.within_bounds(profile, expect),
                    f'{send.id}: the request profile is invalid or outside the per-request bounds.')
        priced[send.id] = {'maximum_cost': maximum, 'bound': pc.attempt_bound(maximum),
                           'pricing_version': config['pricing_version'],
                           'max_output_tokens': profile['max_output_tokens'], 'timeout_seconds': profile['timeout_seconds']}
    return priced


def cancel_queued(world):
    """Every queued job, cancelled through the product (sonnet5_qa.cancel_stale_jobs: its hold released, it never ran,
    so nothing was sent). Used when a send halted before its attempt was written: a job it had already queued — the
    refusal at the attempt record sits outside the per-send code that cancels — is not left queued. (`world` is passed
    through; the cancellation is the product's own, by each job's requester.) Returns what it did, or why it could not
    (the next run's own cancellation then covers it)."""
    try:
        return {'cancelled': sq.cancel_stale_jobs(world)}
    except Exception as error:                                  # (recorded, never raised: the halt stands either way)
        return {'error': f'{type(error).__name__}: {error}'[:300]}


def run_stage(campaign, stage, *, secret, provenance, max_sends=None, environ=None, rebuild=REBUILD,
              database_prefix=sq.DATABASE_PREFIX, transcription_secret=None):
    """One bounded run of a mapping, notes or transcription stage, through the historical per-send machinery
    (sonnet5_stages.Run, or for transcription its subclass standing_qa_transcription.TranscriptionRun: the real views and
    worker, admission per send, the attempt before the one request, the outcome, the contract checks, the frozen graders,
    the export read-back, the billing audit, the leak scan). Only sends with no attempt in this campaign are planned; at
    most min(max_sends, max_sends_per_run). A remainder holding a send whose prerequisite send was made in an earlier run
    (a mapping encounter, a transcript's generation — after a halt between the two, or a stop before its attempt) is
    refused whole before anything is written (require_none_stranded: the historical rule) — the stage can never pass in
    this campaign. The stage is decided failed on any stop, passed when every planned send is made and none ever stopped
    it; otherwise the run closes and the stage stays open. The operator's Stop file met by a send before its attempt
    was written (stopped_by_halt) halts the run like the loop's own check does: no failure, its queued job cancelled.
    `transcription_secret`: the Deepgram key — given to a transcription run, and only to one."""
    stages = sq.stages_module()
    declaration, ledger, root = campaign.declaration, campaign.ledger, campaign.root
    require(stage in STAGE_KIND and stage != 'model_check', f'No stage run for {stage!r} here.')
    kind = STAGE_KIND[stage]
    transcribing = stage == 'transcription'
    require(transcribing == (transcription_secret is not None),
            'The Deepgram credential reaches a transcription run only, and a transcription run needs it.')
    if transcribing:
        require_own_transcription_key(transcription_secret, secret)      # (L1:R1-F2: before the ledger, a run, a worker)
    ledger.acquire()
    settled = settle(campaign)
    require_preflight(campaign)
    limits = campaign.limits()
    if transcribing:
        checked = transcription_module().preconditions(
            campaign, secret=secret, transcription_secret=transcription_secret, database_prefix=database_prefix,
            rebuild=rebuild, environ=environ, expect=declaration.expect(limits))
    else:
        checked = stages.stage_preconditions(declaration, kind, root, database_prefix=database_prefix, rebuild=rebuild,
                                             environ=environ, ledger=ledger, expect=declaration.expect(limits))
    inputs = stage_inputs(stage, declaration)
    plan = standing_plan(stage, inputs)
    _, in_force = campaign.stage_open(stage)
    require(len(plan) == in_force.max_requests, f'{stage} declares {in_force.max_requests} sends; its plan has '
                                                f'{len(plan)}.')
    remaining = remaining_sends(campaign, stage, plan)
    require(remaining, f'Every send of {stage} already has an attempt (or was recorded not exercisable); nothing is '
                       'sent twice.')
    require_none_stranded(stage, remaining)                 # (before anything is written: the historical rule)
    cap = limits.max_sends_per_run if max_sends is None else min(int(max_sends), limits.max_sends_per_run)
    require(cap > 0, 'A run makes at least one send.')
    selected = select_batch(remaining, cap)
    run = begin_run(campaign, stage, selected, inputs, cap, provenance)
    try:
        forms = stages.build_forms(root / 'forms' / stage, 'ordinary_notes' if transcribing else kind, inputs)
        restricted = set(run['restricted_inputs'])
        for name, data in forms.items():
            require(hashlib.sha256(data).hexdigest() not in restricted,
                    f'The form {name} is a development original marked "no provider upload".')
        world = stages.seed_account(root)
        stale = sq.cancel_stale_jobs(world)
        if transcribing:
            tr = transcription_module()
            worker = tr.TranscriptionRun(campaign, stage, secret=secret, transcription_secret=transcription_secret,
                                         provenance=provenance, inputs=inputs, forms=forms, world=world, checked=checked,
                                         deadline=limits.request_deadline_seconds)
            worker.planned = tr.planned_maxima(selected, declaration)
        else:
            worker = stages.Run(campaign, stage, secret=secret, provenance=provenance, inputs=inputs, forms=forms,
                                world=world, checked=checked, deadline=limits.request_deadline_seconds)
            scratch = pc.private_directory(root / 'tmp' / f'price-{stage}-{run["run_id"]}')
            worker.planned = {key: value['maximum_cost'] for key, value in price_sends(
                stage, selected, inputs, scratch, declaration, limits).items()}
    except Refused as refused:
        campaign.runs.close(ledger, run['run'], {'closed_as': 'refused_before_attempt', 'reason': str(refused),
                                                 'sends': []})
        raise
    reasons, not_sent, halted, halt_jobs = [], [], None, None
    for send in selected:
        if worker.stopped or halted:
            not_sent.append(send.id)
            continue
        if os.path.lexists(campaign.stop_file()):
            # (the operator's halt switch, not a safety failure: the run ends here and the stage stays open)
            halted = f'the Stop file {campaign.stop_file()} appeared during the run; the remaining sends were not made'
            not_sent.append(send.id)
            continue
        try:
            done = worker.run_send(send)
        except (stages.StageStop, Refused) as stop:
            if stopped_by_halt(stop):
                # (L1:R1-F4 / L2:R2-F2: the Stop file appeared AFTER the check above and was met inside this send — at its
                # preview admission, its admission or its attempt record — so nothing was sent for it. The same halt as
                # the check above, never a failure; a job it had queued is cancelled through the product.)
                halted = (f'the Stop file {campaign.stop_file()} appeared during {send.id}, before its attempt was '
                          'written; it and the remaining sends were not made')
                not_sent.append(send.id)
                halt_jobs = cancel_queued(world)
                continue
            worker.stopped = {'send': send.id, 'before_attempt': True, 'reason': str(stop)}
            reasons.append(f'{send.id}: stopped before its attempt was written (nothing sent): {stop}')
            not_sent.append(send.id)
            continue
        if done is None:
            continue
        record, stops = done
        if stops:
            worker.stopped = {'send': send.id, 'attempt': record.get('attempt'), 'findings': record.get('findings')}
            reasons.append(f'{send.id}: ' + '; '.join(f['why'] for f in record.get('findings') or []))
    base = {'settled_before_start': settled, 'stale_jobs_cancelled': stale}
    if halt_jobs is not None:
        base['halt_jobs'] = halt_jobs
    return decide_run(campaign, stage, run, plan, worker, reasons, not_sent, base, halted=halted)


def run_secrets(campaign, worker):
    """[(key, its credential file)] every leak scan of a run searches for: the Anthropic key, and in a transcription run
    the Deepgram key too (by value: it has no fixed shape)."""
    found = [(worker.secret, campaign.declaration.credential_file)]
    deepgram = getattr(worker, 'transcription_secret', None)
    if deepgram:
        found.append((deepgram, campaign.declaration.transcription.credential_file))
    return found


def decide_run(campaign, stage, run, plan, worker, reasons, not_sent, base, *, halted=None):
    """The run's close and, when it is due, the stage's decision: failed on any stop (that path stops until a committed
    diagnosis and repair reopen it); passed only when every planned send has been made (or, for an encounter whose form
    was mapped in the same run, recorded not exercisable by the worker), this run made at least one, and no attempt of
    any run ever stopped it; otherwise the run closes and the stage stays open for the next run — `halted` (the
    operator's Stop file during the run) included: a halt is not a failure (a halt that strands an encounter leaves a
    remainder the next run refuses: require_none_stranded)."""
    ledger = campaign.ledger
    attempts = [row.get('attempt') for row in worker.sends if row.get('attempt')]
    earlier = earlier_stops(campaign, stage, attempts)
    late = []
    for key, credential in run_secrets(campaign, worker):
        try:
            late += pc.leaked(campaign.root, key, exclude=(credential,))
        except pc.Refused as refused:
            late.append(str(refused))
    if late:
        ledger.write_stop({'reason': 'the evidence could not be scanned, or carries the credential, at the run\'s close',
                           'detail': late})
        reasons = list(reasons) + ['the final leak scan did not come back clean']
    left = [send.id for send in remaining_sends(campaign, stage, plan)
            if send.id not in {row['send']['id'] for row in worker.sends if isinstance(row.get('send'), dict)
                               and 'not_exercised' in row}]
    summary = {'run': run['run_id'], 'plan': [send.id for send in plan], 'selected': run['sends'],
               'sends': worker.sends, 'not_sent': not_sent, 'veto_evidence': worker.veto_evidence, 'attempts': attempts,
               'earlier_stops': earlier, 'remaining_after': left, 'monetary_ceiling': None, **base}
    if not attempts and not reasons and not halted:
        # (the historical rule, sonnet5_stages.decide_stage: a run that made no send is never a pass — whatever rows it
        # recorded as not exercisable; a not-exercisable encounter is only ever one whose form was mapped in this run)
        reasons = ['no send was made']
    summary['halted'] = halted
    decision = 'partial'
    if halted and not reasons:
        decision = 'halted'
    elif ledger.stage_state(stage)['state'] == 'open':
        if reasons:
            ledger.write_stage(stage, 'failed', {'reasons': reasons, 'summary': summary})
            decision = 'failed'
        elif not left:
            if earlier:
                reasons = ['the stage cannot pass: an earlier run did not end clean — ' + '; '.join(
                    f'{e["send"]} (attempt {e["attempt"]}): {e["why"]}' for e in earlier)]
                ledger.write_stage(stage, 'failed', {'reasons': reasons, 'summary': summary})
                decision = 'failed'
            else:
                ledger.write_stage(stage, 'passed', {'summary': summary})
                decision = 'passed'
    campaign.runs.close(ledger, run['run'], {'closed_as': decision, 'sends': worker.sends, 'not_sent': not_sent,
                                             'reasons': reasons, 'remaining_after': left, 'halted': halted})
    verdict = {'failed': 'FAIL', 'halted': 'HALTED'}.get(decision, 'PASS')
    return {'stage': stage, 'run': run['run_id'], 'verdict': verdict, 'decision': decision, 'reasons': reasons,
            'summary': summary}


# ── read-only reports ────────────────────────────────────────────────────────────────────────────────────────────

def status(root=None, declaration_path=None, *, repository=None, out=None):
    """The ledger, runs, stage states and preflights against the send counts in force; NO money limit (null). Read-only:
    no lock is taken and nothing is written."""
    out = sys.stdout if out is None else out
    declaration = declared_standing(DECLARATION if declaration_path is None else declaration_path,
                                    repository=repository, uses=('live', 'test'))
    campaign = StandingCampaign(declaration, root)
    rows = campaign.rows()
    limits = campaign.limits(rows)
    stages = {}
    for stage in declaration.stages:
        totals = campaign.totals(stage.id)
        state = campaign.ledger.stage_state(stage.id)
        in_force = {s.id: s for s in limits.stages}.get(stage.id)
        stages[stage.id] = {'attempts': totals['attempts'], 'sends_declared': in_force.max_requests if in_force else 0,
                            'calculated_exposure_usd': format(totals['exposure'], 'f'), 'limit': None,
                            'requires': list(in_force.requires) if in_force else None, 'state': state['state'],
                            'failures': state['failures'], 'reopenings': state['reopenings']}
    total = campaign.totals()
    report = {'campaign': declaration.campaign, 'authority_id': declaration.authority_id, 'mode': MODE,
              'monetary_ceiling': None, 'root': str(campaign.root), 'limits_in_force': limits.record(), 'stages': stages,
              'total': {'attempts': total['attempts'], 'calculated_exposure_usd': format(total['exposure'], 'f'),
                        'limit': None, 'open': total['open'], 'unknown': total['unknown']},
              'open_attempts': [a['number'] for a, o in rows if o is None],
              'runs': [{'run': opened['run_id'], 'stage': opened.get('stage'), 'sends': opened.get('sends'),
                        'closed_as': (closed or {}).get('closed_as')} for opened, closed in campaign.runs.listing()],
              'preflights': [{'preflight': n, 'model_returned': (r or {}).get('model_returned'),
                              'matches_declared': (r or {}).get('matches_declared')} for n, r in preflights(campaign.root)],
              'stop_file': os.path.lexists(campaign.stop_file()), 'campaign_stop': campaign.ledger.campaign_stop(),
              'credential_file_present': os.path.lexists(declaration.credential_file)}
    print(json.dumps(report, indent=1, default=str), file=out)
    return report


def plan_report(stage=None, *, root=None, declaration_path=None, repository=None):
    """The plan definitions (and, with a declaration, what each stage already attempted and what is left). No credential,
    network or database."""
    inputs = sq.stages_module().frozen_inputs()
    definitions = plan_definitions(inputs)
    if stage is not None:
        require(stage in definitions, f'No standing plan is defined for the stage {stage!r}.')
        definitions = {stage: definitions[stage]}
    report = {'authority_id': AUTHORITY_ID, 'mode': MODE, 'monetary_ceiling': None,
              'freeze_manifest_sha256': inputs['freeze']['manifest_sha256'], 'stages': definitions,
              'credential_read': False, 'network': 'none', 'database': 'none'}
    path = DECLARATION if declaration_path is None else Path(declaration_path)
    if path.exists():
        declaration = declared_standing(path, repository=repository, uses=('live', 'test'))
        campaign = StandingCampaign(declaration, root)
        for name, entry in definitions.items():
            if not entry.get('established'):
                continue
            if name == 'transcription':
                if declaration.transcription is None:
                    entry['declared'] = False                # (defined, not declared: nothing of it can be sent)
                    continue
                sends = standing_plan(name, {**inputs, 'transcription_audio': declaration.transcription.inputs})
                entry['declared_terms'] = declaration.transcription.record()
            else:
                sends = standing_plan(name, inputs)
            left = remaining_sends(campaign, name, sends)
            entry['remaining'] = [send.id for send in left]
            entry['stranded'] = [send.id for send in stranded(left)]         # (never sent here: the stage cannot pass)
            entry['stage_state'] = campaign.ledger.stage_state(name)['state']
            entry['earlier_stops'] = earlier_stops(campaign, name)
        report['declaration'] = {'path': str(path), 'sha256': declaration.sha256, 'commit': declaration.commit}
    else:
        report['declaration'] = {'path': str(path), 'present': False,
                                 'note': 'the lead writes it from the TEMPLATE once the 5.5 profile is integrated'}
    return report


# ── processes ────────────────────────────────────────────────────────────────────────────────────────────────────

def application_environment(declaration, state_dir, flags, *, database='unused', password='unused-by-this-process'):
    """The settings the application reads, for a process that configures Django without sending (pricing, plan)."""
    return {'QUILLMD_SECRET_KEY': 'standing-offline-' + secrets.token_hex(16), 'QUILLMD_DB_PASSWORD': password,
            'QUILLMD_DB_NAME': database, 'QUILLMD_DB_USER': QA_SERVER['user'],
            'QUILLMD_DB_HOST': '/nonexistent-offline-socket-dir', 'QUILLMD_DB_PORT': '1', 'QUILLMD_ENV_MANAGED': '1',
            'QUILLMD_STATE_DIR': str(state_dir), 'QUILLMD_ADMIN_SITE': '0', **pc.declared_settings(declaration),
            **sq.PRICE_SETTINGS, **flags}


def _offline_django(environ):
    """Django configured from `environ`, with every database connection refused (nothing here touches one)."""
    require(not sq.env_file_present(), 'This runs only in a checkout with no rebuild/.env.')
    os.environ.update(environ)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
    if str(REBUILD) not in sys.path:
        sys.path.insert(0, str(REBUILD))
    import django
    django.setup()
    from django.db.backends.base import base as dbbase

    def no_database(self, *args, **kwargs):
        raise AssertionError('this command never touches a database')
    dbbase.BaseDatabaseWrapper.ensure_connection = no_database


def pricing(model, rates, thinking, effort, inference_geo='', *, transcription_rate=None, out=None):
    """The pricing version the APPLICATION computes for every pricing key, and each request profile, under the named
    settings (PRICING_FLAGS per key; sonnet5_qa.PRICE_SETTINGS). Refuses a key whose profile the application does not
    have (an invalid profile is never priced). What the lead writes into the declaration's pricing_version lines.
    `transcription_rate` (USD per audio minute, the provider's price when the declaration is written): also the
    `transcription` version — computed with that rate as the application's QUILLMD_DEEPGRAM_RATE_PER_MINUTE, which every
    pricing version hashes — and, per allowlisted recording, its measured length and transcription maximum (each
    recording read only after its sha256 matches; one that cannot be read is reported, not priced)."""
    out = sys.stdout if out is None else out
    if transcription_rate is not None:
        require(TRANSCRIPTION_RATE.fullmatch(str(transcription_rate)) and Decimal(transcription_rate) > 0,
                '--deepgram-rate-per-minute is a positive USD rate per audio minute (at most ten decimals).')
    probe = SimpleDeclaration(model, pc.Rates(*rates), thinking, effort, inference_geo)
    with tempfile.TemporaryDirectory(prefix='standing-pricing-') as scratch:
        _offline_django(application_environment(probe, scratch, STAGE_FLAGS['model_check']))
        from django.test.utils import override_settings
        from core import audio as app_audio, generation, jobs as app_jobs, mapping_assistance
        versions, profiles, previews = {}, {}, {}
        for key, flags in PRICING_FLAGS.items():
            if key == 'transcription' and transcription_rate is None:
                continue
            saved = os.environ.get('QUILLMD_DEEPGRAM_RATE_PER_MINUTE')
            if key == 'transcription':
                os.environ['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'] = str(transcription_rate)
            try:
                with override_settings(**expected_settings_from_flags(flags)):
                    config = generation.configuration()
                    profile = config['request_profile']
                    require('invalid' not in profile, f'{key}: the application has no valid request profile for '
                                                      f'{model}: {profile.get("invalid")}')
                    if key == 'mapping':
                        try:
                            profiles['mapping_request'] = mapping_assistance.request_profile(config)
                        except Exception as error:
                            raise Refused(f'mapping: the application refuses a mapping request profile for {model} '
                                          f'({type(error).__name__}: {error})') from None
                    if key == 'transcription':
                        for entry in TRANSCRIPTION_AUDIO:
                            try:
                                seconds = app_audio.measure_bounds(read_audio(entry)).measured
                                quote = app_jobs.transcription_quote(seconds, config)
                                previews[entry.id] = {
                                    'sha256': entry.sha256, 'label': entry.label, 'measured_seconds': str(seconds),
                                    'maximum_cost': format(transcription_maximum(seconds, transcription_rate), 'f'),
                                    'charge_limit': quote['charge_limit'], 'standard_limit': quote['standard_limit'],
                                    'within_standard': quote['within_standard']}
                            except Exception as error:
                                previews[entry.id] = {'sha256': entry.sha256, 'unpriced': f'{type(error).__name__}: '
                                                                                          f'{error}'[:300]}
                    versions[key], profiles[key] = config['pricing_version'], profile
            finally:
                if saved is None:
                    os.environ.pop('QUILLMD_DEEPGRAM_RATE_PER_MINUTE', None)
                else:
                    os.environ['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'] = saved
    report = {'model': model, 'rates': probe.rates.as_dict(), 'thinking': thinking, 'effort': effort,
              'inference_geo': inference_geo or 'unset', 'price_settings': sq.PRICE_SETTINGS,
              'pricing_versions': versions, 'request_profiles': profiles,
              'declaration_lines': [f'pricing_version {key}: {value}' for key, value in sorted(versions.items())]}
    if transcription_rate is not None:
        report['transcription'] = {'provider': TRANSCRIPTION_PROVIDER, 'model': DEEPGRAM_MODEL,
                                   'rate_per_minute': str(transcription_rate), 'flags': STAGE_FLAGS['transcription'],
                                   'recordings': previews,
                                   'declaration_line': f'transcription_rate_per_minute: {transcription_rate}'}
    print(json.dumps(report, indent=1), file=out)
    return report


@dataclasses.dataclass(frozen=True)
class SimpleDeclaration:
    """The settings `pricing` needs before any declaration exists (provider_campaign.declared_settings reads these)."""
    model: str
    rates: pc.Rates
    thinking: str
    effort: str
    inference_geo: str
    provider: str = 'anthropic'


def expected_settings_from_flags(flags):
    values = {}
    for flag, value in flags.items():
        if flag in FLAG_SETTINGS:
            name, kind = FLAG_SETTINGS[flag]
            values[name] = (value == '1') if kind is bool else value
    return values


def ensure_database(password, name):
    """The campaign's own synthetic database on the QA server, created if absent."""
    import psycopg
    from psycopg import sql
    require(DATABASE.fullmatch(name) and name != HISTORICAL['database'], 'The campaign database name is not its own QA name.')
    with psycopg.connect(host=QA_SERVER['host'], port=QA_SERVER['port'], user=QA_SERVER['user'], password=password,
                         dbname='postgres', autocommit=True, connect_timeout=10) as connection:
        exists = connection.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,)).fetchone()
        if not exists:
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))


def request_environment(key, declaration, root, password, context, flags, door, transcription_key=None):
    """The complete environment of the request process (nothing inherited): the declared settings, the stage's flags, the
    campaign's own QA database and state, and the door's two variables (so the request process re-checks the door).
    `transcription_key`: the Deepgram key, for a transcription run's request process only (outer passes it for no other
    command or stage); the request process takes it out of its environment before anything else (inner)."""
    extra = {'DJANGO_SETTINGS_MODULE': 'quillmd.settings', 'QUILLMD_SECRET_KEY': secrets.token_urlsafe(48),
             'QUILLMD_DB_NAME': declaration.qa_database, 'QUILLMD_DB_USER': QA_SERVER['user'],
             'QUILLMD_DB_PASSWORD': password, 'QUILLMD_DB_HOST': QA_SERVER['host'], 'QUILLMD_DB_PORT': QA_SERVER['port'],
             'QUILLMD_STATE_DIR': str(root / 'qa-state'), 'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_ADMIN_SITE': '0',
             'QUILLMD_HTTPS': '0', 'QUILLMD_EMAIL_MODE': 'file', 'HOME': str(root / 'home'), 'TMPDIR': str(root / 'tmp'),
             **sq.PRICE_SETTINGS, **flags, CONTEXT_VARIABLE: json.dumps(context),
             'RULED_MUTATION_DECLARATION': door['declaration'], 'RULED_MUTATION_DECL_COMMIT': door['commit']}
    if transcription_key is not None:
        require(isinstance(transcription_key, str) and transcription_key, 'The Deepgram credential is empty.')
        extra[TRANSCRIPTION_KEY_VARIABLE] = transcription_key
    return pc.scrubbed_environment(key, declaration, extra, config_parent=str(root / 'tmp'))


def outer(command, stage=None, max_sends=None, path=None):
    """Everything that needs no database, then the request process (a fresh, scrubbed process) — the one door for the
    preflight and every stage run."""
    require(command in ('preflight', 'run'), f'No process command {command!r}.')
    require(not sq.env_file_present(REBUILD), 'The checkout has a rebuild/.env; the campaign never runs beside one.')
    require(not _inside(REBUILD, INSTALLED['tree']), 'The runner never runs from the installed tree.')
    identity = pc.git_identity(REBUILD)
    require(identity['clean'], 'The runner checkout must be a clean commit.')
    path = DECLARATION if path is None else path
    declaration = declared_standing(path)
    places = require_live(declaration)
    door = require_door(declaration)
    if command == 'run':
        require(stage in STAGE_KIND, f'run needs --stage {"|".join(STAGE_KIND)}.')
        declaration.stage(stage)
    root = pc.private_directory(places['root'])
    for name in ('ledger', 'runs', 'evidence', 'preflight', 'qa-state', 'access', 'home', 'tmp', 'forms'):
        pc.private_directory(root / name)
    require(not os.path.lexists(root / STOP_NAME), f'The Stop file {root / STOP_NAME} exists; nothing is sent.')
    key = pc.load_credential(declaration.credential_file, declaration)
    # (the Deepgram key: read for a transcription run ONLY, by the same file rules, before anything is sent — a missing,
    # linked, wrongly owned or wrongly permissioned file refuses here, before the database or the request process, and
    # so does one holding the Anthropic key's value at a path of its own: L1:R1-F2)
    transcribing = command == 'run' and stage == 'transcription'
    transcription_key = load_transcription_credential(declaration, anthropic_key=key) if transcribing else None
    password = ''
    if command == 'run':
        password = pc.read_private(declaration.qa_database_password_file).decode().strip()
        require(password and '\n' not in password, 'The QA database password file is not one line.')
    context = {'command': command, 'root': str(root), 'declaration': str(path), 'stage': stage,
               'max_sends': max_sends, 'runner_commit': identity['commit']}
    env = request_environment(key, declaration, root, password, context,
                              stage_flags(stage, declaration) if command == 'run' else STAGE_FLAGS['model_check'], door,
                              transcription_key=transcription_key)
    if command == 'run':
        ensure_database(password, declaration.qa_database)
    os.chdir(REBUILD)
    os.execve(sys.executable, [sys.executable, '-B', str(RUNNER), '_inner'], env)


def _interrupted(signum, frame):
    raise SystemExit(f'signal {signum}')


def inner():
    """The request process. Before anything else it takes the Deepgram key (if it was handed one) OUT of its own
    environment, into memory; then — before the declaration is read and long before django.setup() — it refuses unless
    QUILLMD_ENV_MANAGED is exactly '1' and rebuild/.env does not exist; then it re-verifies the declaration, the door,
    the Stop file, the scrubbed environment and each credential itself. The Deepgram key is accepted only by a
    transcription run (for anything else its presence refuses), must equal the declared file's, and is put back into the
    environment only around the transcription send's one request (standing_qa_transcription.TranscriptionRun)."""
    transcription_key = os.environ.pop(TRANSCRIPTION_KEY_VARIABLE, None)
    require(os.environ.get('QUILLMD_ENV_MANAGED') == '1',
            'The request process runs only with QUILLMD_ENV_MANAGED=1: settings must never load a .env file.')
    require(not sq.env_file_present(REBUILD), 'The checkout has a rebuild/.env; the request process never starts beside '
                                              'one.')
    os.umask(0o077)
    signal.signal(signal.SIGTERM, _interrupted)
    signal.signal(signal.SIGINT, _interrupted)
    context = json.loads(os.environ[CONTEXT_VARIABLE])
    transcribing = context.get('command') == 'run' and context.get('stage') == 'transcription'
    require(transcribing or transcription_key is None,
            'The Deepgram credential reached a request process that is not a transcription run; nothing is sent.')
    declaration = declared_standing(context['declaration'])
    require_live(declaration)
    require_door(declaration)
    require(Path(context['root']) == require_live(declaration)['root'],
            'The request process runs only at this campaign\'s root.')
    campaign = StandingCampaign(declaration)
    campaign.ledger.acquire()
    pc.scrubbed_now()
    campaign.require_not_stopped()
    key = os.environ['ANTHROPIC_API_KEY']
    require(pc.constant_time_equal(key, pc.load_credential(declaration.credential_file, declaration)),
            'The request process does not carry the declared credential.')
    if transcribing:
        require(transcription_key and pc.constant_time_equal(
                    transcription_key, load_transcription_credential(declaration, anthropic_key=key)),
                'The request process does not carry the declared Deepgram credential.')
    provenance = {'runner_commit': context['runner_commit']}
    try:
        if context['command'] == 'preflight':
            result = run_preflight(campaign, secret=key)
            code = 0 if result['matches_declared'] else EXIT['FAIL']
        else:
            stage = context['stage']
            require_preflight(campaign)
            sys.path.insert(0, str(REBUILD))
            import django
            django.setup()
            from django.test.utils import override_settings
            override_settings(STORAGES=sq.STATIC_STORAGES).enable()
            settle(campaign)
            problems = check_configuration(settings_snapshot(stage), declaration, stage, campaign.root,
                                           limits=campaign.limits())
            require(not problems, 'The request process is not configured for this stage: ' + '; '.join(problems))
            from django.core.management import call_command
            call_command('migrate', interactive=False, verbosity=0)
            pc.install_request_capture()
            pc.install_transport_guard()
            if transcribing:
                transcription_module().install_transcription_guard()
            # Item assignment, not a call with a max_tokens keyword: the cost scanner reads a call carrying an output-cap
            # keyword as a provider call. These are the capture guard's per-request bounds, not a request.
            pc.REQUEST_BOUNDS['model'] = declaration.model
            pc.REQUEST_BOUNDS['max_tokens'] = campaign.limits().max_output_tokens_per_request
            if stage == 'model_check':
                result = run_model_check(campaign, secret=key, provenance=provenance)
            else:
                result = run_stage(campaign, stage, secret=key, provenance=provenance, max_sends=context['max_sends'],
                                   transcription_secret=transcription_key if transcribing else None)
            code = EXIT[result['verdict']]
    finally:
        os.environ.pop('ANTHROPIC_API_KEY', None)
        os.environ.pop(TRANSCRIPTION_KEY_VARIABLE, None)
    text = json.dumps(result, indent=1, default=str)
    require(key not in text and not pc.KEY_SHAPE.search(text.encode())
            and not (transcription_key and transcription_key in text),
            'The result carried a key-shaped value; withheld.')
    print(text)
    return code


def recover(root=None, declaration_path=None, *, repository=None):
    declaration = declared_standing(DECLARATION if declaration_path is None else declaration_path, repository=repository)
    campaign = StandingCampaign(declaration, root)
    campaign.ledger.acquire()
    try:
        result = settle(campaign)
    finally:
        campaign.ledger.release()
    print(json.dumps(result, indent=1, default=str))
    return 0


def reopen(stage, diagnosis, root=None, declaration_path=None, *, repository=None, rebuild=None):
    """Reopens a FAILED stage after offline repair (provider_campaign.Campaign.reopen, which has no money check here):
    the diagnosis committed and unmodified, naming the failed attempts and the repair commit, which this clean runner
    contains and none of the failed runners did, a watched file changed; and something left to send. Nothing is sent."""
    declaration = declared_standing(DECLARATION if declaration_path is None else declaration_path, repository=repository)
    identity = pc.git_identity(REBUILD if rebuild is None else rebuild)
    require(identity['clean'], 'The runner checkout must be a clean commit.')
    campaign = StandingCampaign(declaration, root)

    def remainder():
        # (the historical reopening's rule, sonnet5_qa.reopen -> pending_sends: a remainder the stage runner would refuse
        # — nothing left, or a stranded encounter — is refused here, before the reopening is written)
        left = remaining_sends(campaign, stage, standing_plan(stage, stage_inputs(stage, declaration)))
        require(left, f'Stage {stage} has no send left that was never made; a reopening would send nothing.')
        return [send.id for send in require_none_stranded(stage, left)]
    campaign.ledger.acquire()
    try:
        record = campaign.reopen(stage, diagnosis, runner_commit=identity['commit'], remainder=remainder)
    finally:
        campaign.ledger.release()
    print(json.dumps(record, indent=1, default=str))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv[:1] == ['_inner']:
            return inner()
        parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
        parser.add_argument('command', choices=['pricing', 'plan', 'status', 'preflight', 'run', 'recover', 'reopen'])
        parser.add_argument('--stage')
        parser.add_argument('--max-sends', type=int)
        parser.add_argument('--diagnosis')
        parser.add_argument('--price', action='store_true')
        parser.add_argument('--model')
        parser.add_argument('--input')
        parser.add_argument('--output')
        parser.add_argument('--cached')
        parser.add_argument('--thinking')
        parser.add_argument('--effort')
        parser.add_argument('--inference-geo', default='')
        parser.add_argument('--deepgram-rate-per-minute')
        parser.add_argument('--declaration')
        args = parser.parse_args(argv)
        path = declaration_path(args.declaration)
        if args.command == 'pricing':
            require(all((args.model, args.input, args.output, args.cached, args.thinking, args.effort)),
                    'pricing needs --model --input --output --cached --thinking --effort.')
            pricing(args.model, (args.input, args.output, args.cached), args.thinking, args.effort, args.inference_geo,
                    transcription_rate=args.deepgram_rate_per_minute)
            return 0
        if args.command == 'plan':
            report = plan_report(args.stage, declaration_path=path)
            if args.price:
                report['priced'] = priced_plan(args.stage, path)
            print(json.dumps(report, indent=1, default=str))
            return 0
        if args.command == 'status':
            status(declaration_path=path)
            return 0
        if args.command == 'recover':
            return recover(declaration_path=path)
        if args.command == 'reopen':
            require(args.stage, 'reopen needs --stage.')
            return reopen(args.stage, args.diagnosis, declaration_path=path)
        if args.command == 'preflight':
            outer('preflight', path=path)
        else:
            require(args.stage, f'run needs --stage {"|".join(STAGE_KIND)}.')
            require(args.max_sends is None or args.max_sends > 0, '--max-sends is at least 1.')
            outer('run', args.stage, args.max_sends, path=path)
    except Refused as refused:
        print('REFUSED: ' + str(refused), file=sys.stderr)
        return EXIT['REFUSED']
    return EXIT['REFUSED']


def priced_plan(stage=None, path=None):
    """Each send's maximum, from the application under the live declaration's settings (offline Django)."""
    declaration = declared_standing(DECLARATION if path is None else path, uses=('live',))
    inputs = sq.stages_module().frozen_inputs()
    names = [stage] if stage else [s.id for s in declaration.stages]
    with tempfile.TemporaryDirectory(prefix='standing-plan-') as scratch:
        _offline_django(application_environment(declaration, scratch, STAGE_FLAGS['model_check'],
                                                database=declaration.qa_database))
        from django.test.utils import override_settings
        report = {}
        for name in names:
            if name == 'transcription':
                planned = transcription_module().planned_maxima(standing_plan(name, stage_inputs(name, declaration)),
                                                                declaration)
                report[name] = {send_id: ({'maximum_cost': format(value, 'f'), 'bound': format(pc.attempt_bound(value),
                                                                                                  'f')}
                                          if value is not None else
                                          {'maximum_cost': None, 'note': 'the generation on a transcript is priced by '
                                                                         'the application once the transcript exists'})
                                for send_id, value in planned.items()}
                continue
            with override_settings(**expected_settings(name)):
                priced = price_sends(name, standing_plan(name, inputs), inputs, Path(scratch) / name, declaration)
            report[name] = {send_id: {k: (format(v, 'f') if isinstance(v, Decimal) else v) for k, v in row.items()}
                            for send_id, row in priced.items()}
            report[name]['_calculated_worst_case_usd'] = format(sum((row['bound'] for row in priced.values()),
                                                                    Decimal(0)), 'f')
    return report


if __name__ == '__main__':
    sys.exit(main())
