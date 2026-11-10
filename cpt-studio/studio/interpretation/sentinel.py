"""The production legacy-call sentinel (design/FINAL.md 10, 16.7 and 16.13, as design/ADJUDICATION.md R-1, R-3, R-4 and R-5
amend it; DECISIONS D17 and D22). On the new path Gemini is the only interpreter, and this module is how a process KNOWS
that no code of the legacy reader executed during new-path work: by counting executions, never by trusting a call graph.

THE DENY SET (FINAL 10.1, R-1, R-4, R-5) is computed at install from code objects - every live function of a denied file
and every code object nested in one (walked through co_consts; lru_cache wrappers through __wrapped__) - never from names:
1. the whole of studio/gi/*.py but profiles.py and catalogue.py, studio/validation/{engine,reconcile,review_view,
   rationale}.py and studio/candidates.py (DENY_MODULES);
2. studio/validation/checks.py by function, as an ALLOWLIST (R-5): every function but the FINAL 7.1 names
   (CHECKS_ALLOWLIST; incomplete_check is not one, R-4) and the helpers they reach through checks.py's own call graph
   (CHECKS_ALLOWED_HELPERS). FINAL 10.1(3)'s list - the 22 functions with function-local studio.gi imports
   (CHECKS_GI_IMPORTERS), every function reaching them, and the named routing and cue readers (CHECKS_NAMED_READERS) -
   must lie inside the denied part, or the install fails;
3. the archived legacy stages of studio/jobs.py (ARCHIVED_JOBS), to catch a mis-dispatch.
Not in it: dataclass-generated methods (co_filename '<string>'), so building a review_view.View is allowed; module and
class bodies, which run once at import (importing is not calling, D17); the re-homed stored-fact predicates, whose code
lives in studio/context_facts.py; gi.profiles, gi.catalogue, questions.py and jobs.release_routing_caches.

R-1. install() IMPORTS the pinned module list explicitly before it walks anything (AppConfig.ready sees no legacy module of
its own accord: studio/apps.py and models.py import only Django), and refuses unless that list equals glob(studio/gi/*.py)
minus profiles and catalogue, plus the named validation files and candidates.py - a legacy module added later cannot sit
outside the deny set unnoticed. The set's size is pinned per file (PINNED_SIZES) and the checks split by name
(CHECKS_DENIED, CHECKS_ALLOWED_HELPERS, CHECKS_GI_IMPORTERS); any difference fails the install, so a refactor cannot
silently shrink it. A deliberate change to a denied file (ADJUDICATION R-2's re-homing, say) updates these pins in the
same commit.

THE MECHANISM (FINAL 10.2). sys.monitoring tool 4 ('cpt-studio-sentinel'; 0, 1, 2 and 5 are the conventional debugger,
coverage, profiler and optimizer ids), with PY_START set LOCALLY on each denied code object only, so nothing else pays a
cost. The callback reads the ContextVar frame (its scope and label), counts the code object under that label and returns
None - never DISABLE, so every execution is counted. Monitoring survives fork: a forked child's counts come back with its
result (counted, merge, run_counted), even when the child's work raised. In production the denied lru caches are cleared
whenever a new_path scope opens or a reader relabels a row new_path, so a cache hit cannot answer for a legacy function
without executing it.

TEST MODE (call_checks, strict; FINAL 10.2 and R-3): CALL events on every code object, counting - when the calling code is
the app's own - a re.Pattern method given a denied pattern as its first argument, a bound method of a denied pattern, one
of the re module's functions given a denied pattern, the lru_cache wrapper of a denied function, and a denied pattern's
bound method passed as a first argument: the C-level reads PY_START cannot see. The denied patterns (denied_patterns) are
every compiled pattern a denied module's globals hold, and checks.py's split as its functions are (R-5): a pattern global
the allowed closure names (CHECKS_ALLOWED_PATTERNS) is allowed, every other one (CHECKS_DENIED_PATTERNS, the denied
readers' keyword vocabularies) is denied. Only a pinned pattern is exempt (EXEMPT_PATTERNS): one that is not the legacy
reader's, though a denied module holds it - the re-homed predicates' pattern, and a regex new code compiles from the same
source, which re's cache can return as the one object. Holding a legacy pattern exempts nothing, so a module that imports
one leaves it denied, and a new exemption is a deliberate edit of the pin (the test fails on any production regex equal to
a denied one whose original is not pinned: twins).

SCOPES AND LABELS (FINAL 10.3): ``scope`` opens a new_path, legacy_record or other scope; ``relabel`` changes the label
for one row of a reader; outside any scope an execution counts as unscoped. WRITE GATES (``gate``) refuse - CPT Studio's
sentence, and an AuditEvent 'sentinel.tripped' naming the entry points and the counts - when this process's sentinel is not
installed and proven, when no scope armed by it is open, when a callback failed in the scope, or when the scope (with its
enclosing scopes) counted a new_path execution. Reads (``observe``) never refuse and record what a write would refuse:
once per scope for the scope's own reason, and once per PROCESS when this process's sentinel is not installed and proven
(FINAL 10.2: "The web records it. The D22 report shows it."). The D22 record of a new-path assessment is ``record``.

FAIL-CLOSED. Whatever keeps the deny set from being computed exactly as pinned, the tool from being acquired, or the
positive control from firing leaves the sentinel failed, with the reason (status). The failure stands for the process -
the deny set is not walked again on every scope - and a failed process refuses every new-path write. Only an install
attempted before Django's app registry is ready is not a failure: it changes nothing, and a later call installs.
"""
from __future__ import annotations

import contextlib
import contextvars
import dis
import functools
import gc
import importlib
import logging
import os
import re
import sys
import threading
import traceback
import types
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

TOOL = 'sys.monitoring'  # the D22 record's ``tool``
TOOL_ID = 4
TOOL_NAME = 'cpt-studio-sentinel'

NEW_PATH, LEGACY_RECORD, OTHER, UNSCOPED = 'new_path', 'legacy_record', 'other', 'unscoped'
PROBE = 'probe'  # the positive control's own label: never in a total
SCOPE_LABELS = (NEW_PATH, LEGACY_RECORD, OTHER)
LABELS = (NEW_PATH, LEGACY_RECORD, OTHER, UNSCOPED)
CODE, REGEX, CACHE = 'code', 'regex', 'cache'  # what a counted execution was: a denied code object, a denied pattern, a
# denied cache wrapper (the last two only in test mode)
TRIPPED = 'sentinel.tripped'  # AuditEvent.event of a refused write or a recorded read
MAX_ENTRIES = 10  # entry points kept per scope (a trip's evidence; the counts are complete)

# --- the pinned lists (R-1, R-4, R-5) ------------------------------------------------------------------------------------

GI_KEPT = ('profiles', 'catalogue')  # studio/gi's reference tables, never denied
VALIDATION_DENIED = ('engine', 'reconcile', 'review_view', 'rationale')
DENY_MODULES = (
    'studio.gi', 'studio.gi.clauses', 'studio.gi.context', 'studio.gi.cues', 'studio.gi.detect', 'studio.gi.purpose',
    'studio.gi.sections', 'studio.gi.services', 'studio.gi.structure',
    'studio.validation.engine', 'studio.validation.reconcile', 'studio.validation.review_view',
    'studio.validation.rationale',
    'studio.candidates',
)
CHECKS_MODULE = 'studio.validation.checks'
JOBS_MODULE = 'studio.jobs'
ARCHIVED_JOBS = ('_analyze_child', '_route_child', '_assess_child', 'make_context', '_merged_facts')

# FINAL 7.1: the pure, text-free checks the new path may call (R-4: incomplete_check is not one; NOT_CONNECTED_CHECKS is a
# constant, not a function, so it has no code object to allow).
CHECKS_ALLOWLIST = (
    'code_scope', 'scope_check', 'exact_evidence', 'evidence_checks',
    'pfs_check', 'mue_check', 'endoscopic_check', 'pctc_consideration', 'duplicate_check', 'reference_source_entries',
    'service_date_state', 'service_date_check', 'service_date_clarification',
    'required_facts_check', 'fact_clarifications',
    'separate_em_clarification', 'em_procedure_check', 'same_day_if_reinstated_check', 'same_day_em_check',
    'reinstatement_check',
    'provider_checks', 'extraction_check', 'distinct_lesion_review_text',
)
CHECKS_ALLOWLIST_CONSTANTS = ('NOT_CONNECTED_CHECKS',)
# What the allowlist reaches through checks.py's own call graph (computed at install, and pinned here: a helper an allowed
# function newly calls must be allowed by a deliberate edit, never by the walk alone).
CHECKS_ALLOWED_HELPERS = (
    '_date_problem', '_dropped_summary', '_evidence_problem', '_iso_date', '_join', '_reference_source_label',
    '_same_day_subject', 'applied_source', 'conflict_values', 'excerpt', 'fact_label', 'is_member_entered',
    'page_for', 'plural', 'response_problems', 'same_day_reason', 'unavailable_reason',
)
# FINAL 10.1(3), measured: the functions with function-local studio.gi imports ...
CHECKS_GI_IMPORTERS = (
    '_V2_doubt_index', '_V2_explained', '_V2_judged_away', '_V2_judged_by', '_V2_patterns', '_V2_phrase',
    '_V2_says_today', '_V2_today_of_the_act', '_V2_tokens', '_V2_wording', '_VAL_another_time', '_VAL_doubted',
    '_VAL_in_class', '_VAL_lead_name', '_VAL_names_other_service', '_VAL_owned_leads', '_VAL_stated',
    '_VAL_states_no_procedure_of_its_own', '_VAL_text_index', '_VAL_told_act', 'names_intervention', 'span_status',
)
# ... and the named routing and cue readers. Both, with every function reaching an importer, must be denied.
CHECKS_NAMED_READERS = (
    'evidence_readings', 'routing_readings', 'resolve_status', 'required_fact_states', 'separate_em_statement',
    'routing_check', 'status_check', 'exclusion_reason', 'uncertain_reason', 'performed_clarification',
    'unproposed_check', 'unsupported_check', 'restated', 'cite', 'silent',
)
# The denied checks functions, by name (R-5: every checks function the allowlist does not reach).
CHECKS_DENIED = (
    '_V2_accounted', '_V2_doubt', '_V2_doubt_index', '_V2_doubts_it', '_V2_explained', '_V2_explicable',
    '_V2_inside', '_V2_judged_away', '_V2_judged_by', '_V2_np_after', '_V2_np_before', '_V2_of_the_procedure',
    '_V2_owns_phrase', '_V2_patterns', '_V2_phrase', '_V2_reference_nouns', '_V2_says_today',
    '_V2_today_of_the_act', '_V2_token', '_V2_tokens', '_V2_unaccounted', '_V2_wording', '_VAL_another_time',
    '_VAL_doubted', '_VAL_in_class', '_VAL_introduced', '_VAL_lead_matches', '_VAL_lead_name', '_VAL_name',
    '_VAL_names_other_service', '_VAL_one_procedure_words', '_VAL_opening_sentences', '_VAL_opens_with',
    '_VAL_own_procedure', '_VAL_owned_leads', '_VAL_owns', '_VAL_routing_holds', '_VAL_same_procedure',
    '_VAL_sentence_leads', '_VAL_stated', '_VAL_states_no_procedure_of_its_own', '_VAL_text_index', '_VAL_told_act',
    '_first', '_problem', '_quoted_by', '_section_cue', '_silent', 'by_section_alone', 'cite',
    'confirmations_applied_check', 'confirmations_ignored_check', 'confirmed_exclusion',
    'confirmed_incomplete_check', 'confirmed_incomplete_note', 'confirmed_status_check', 'confirmed_status_detail',
    'evidence_readings', 'exclusion_reason', 'global_days_note', 'incomplete_check', 'incomplete_consideration',
    'is_documented', 'names_intervention', 'names_procedure', 'normalise_span_status',
    'participants_disagree_check', 'participants_services_check', 'participants_summary_check',
    'performed_clarification', 'provider_status_beside_participants', 'quoted_passages', 'required_fact_states',
    'resolve_status', 'restated', 'routing_check', 'routing_readings', 'says_today_in_plan', 'section_default',
    'separate_em_statement', 'service_name', 'silent', 'span_status', 'states_no_procedure', 'status_check',
    'uncertain_reason', 'uncited_label', 'unlisted_codes', 'unlisted_codes_check', 'unproposed_check',
    'unsupported_check',
)
# checks.py's compiled patterns, split as its functions are (R-5), by the global that holds them: ALLOWED when a function
# of the allowed closure or an allowlisted constant names it (LOAD_GLOBAL), DENIED otherwise - the keyword vocabularies of
# the denied _V2_ and _VAL_ readers (and one no function names), as legacy as a gi pattern. Test mode denies their reads.
CHECKS_ALLOWED_PATTERNS = ('SCOPE_FORMATS',)
CHECKS_DENIED_PATTERNS = (
    '_ACT_STATED', '_V2_ACT_END', '_V2_AUX', '_V2_BLEEDING', '_V2_CLASS_NEEDS', '_V2_CLASS_WORD', '_V2_CUT',
    '_V2_DENIAL_WORDS', '_V2_DENIED_PARTICIPLE', '_V2_DOUBT_WORDS', '_V2_HEDGE', '_V2_IN_LEAD', '_V2_IT',
    '_V2_LEAD_CLAUSE', '_V2_LEAD_WORD', '_V2_LIST_MARK', '_V2_MEDICATION', '_V2_MODAL', '_V2_N3', '_V2_NOT_ATTR',
    '_V2_NOUN_REFERENCE', '_V2_NO_REPEAT', '_V2_OTHER_EXAM', '_V2_PROCEDURE_STEP', '_V2_PRONOUN', '_V2_SCOPES',
    '_V2_SIBLING', '_V2_SOFT', '_V2_SUBJECT', '_V2_TIME_WORD', '_V2_WORD', '_VAL_ACT_VERB', '_VAL_ANY_OWN',
    '_VAL_INTRO', '_VAL_INTRO_ELSEWHEN', '_VAL_LIST_MARKER', '_VAL_NAME_LEAD', '_VAL_OBJECT', '_VAL_ONE_PROCEDURE',
    '_VAL_OWN_PROCEDURES', '_VAL_REFERENCE', '_VAL_RELATIVE_BEFORE', '_VAL_SERVICE_NOUNS', '_VAL_SIBLING',
    '_VAL_TEMPORAL_LEAD',
)
# The only denied-module patterns test mode does not deny, each with why it is not the legacy reader's (by any location a
# denied module holds it under). Holding a pattern exempts nothing: a new exemption is an edit here, and the test fails on
# any production regex whose source and flags are a denied one's (twins) unless its original is pinned here.
EXEMPT_PATTERNS = {
    'studio.gi.context._CHARGE_NOTE_OWN': 'the re-homed stored-fact predicates\' own pattern: studio.context_facts '
                                          'compiles it and gi.context imports it back (S04)',
    'studio.candidates._ISO_DATE': 'a bare ISO date shape that new code compiles from the same source; re\'s cache can '
                                   'return the one object to both',
    'studio.gi.context.MONTH_YEAR': 'a month-and-year date literal that studio.interpretation.literals compiles from the '
                                    'same source (EB1 reads date literals); re\'s cache can return the one object to both',
}
# Denied code objects per file (a nested function, lambda or generator expression is its own code object), measured on
# Python 3.12 (the image's and CI's): a different interpreter compiles a different number of code objects, and the
# install then refuses rather than guess. ADJUDICATION R-2 (slice S11) re-homed nine code objects into
# studio/code_shapes.py, imported back with identity preserved: engine.py 457 -> 452 (_listable, participant_listable,
# participant_unlisted_count and its generator expression, participant_unlisted_codes), reconcile.py 109 -> 107
# (act_label, kind_label), review_view.py 47 -> 45 (_field, service_answers).
PINNED_SIZES = {
    'studio/gi/__init__.py': 0,
    'studio/gi/clauses.py': 31,
    'studio/gi/context.py': 219,
    'studio/gi/cues.py': 14,
    'studio/gi/detect.py': 766,
    'studio/gi/purpose.py': 5,
    'studio/gi/sections.py': 71,
    'studio/gi/services.py': 456,
    'studio/gi/structure.py': 152,
    'studio/validation/engine.py': 452,
    'studio/validation/reconcile.py': 107,
    'studio/validation/review_view.py': 45,
    'studio/validation/rationale.py': 7,
    'studio/candidates.py': 45,
    'studio/validation/checks.py': 164,
    'studio/jobs.py': 5,
}
DENY_SIZE = sum(PINNED_SIZES.values())

# The positive control's real call: a pure denied function, executed once under the probe label at install, so the code
# object armed is shown to be the code object that runs.
PROBE_CALL = ('studio.gi.cues', 'page_number_line', ('3',))

MESSAGES = {
    'executed': 'Nothing was saved: during this step the server ran code it keeps only for earlier records, so its result '
                'is not used.',
    'unavailable': 'Nothing was saved: this server cannot confirm which reading code ran during this step.',
}
REASONS = ('executed', 'unavailable', 'unscoped', 'instrument')


class Tripped(Exception):
    """A new-path write refused by a gate (FINAL 10.3). ``reason``: 'executed' (the scope counted a new_path execution),
    'unavailable' (this process's sentinel is not installed and proven, or the scope opened before it was), 'unscoped'
    (no scope is open) or 'instrument' (a callback failed while the scope was open). ``data``: the audit record. The
    message is CPT Studio's sentence; it names no module, provider or model."""

    def __init__(self, reason: str, data: dict):
        super().__init__(MESSAGES['executed' if reason == 'executed' else 'unavailable'])
        self.reason = reason
        self.data = data


class _Refused(Exception):
    """The install cannot be completed as pinned; the message is the operator's reason."""


class _NotReady(Exception):
    """The install was attempted before Django's app registry was ready: nothing changed, and a later call installs."""


# --- state ---------------------------------------------------------------------------------------------------------------

class _State:
    def __init__(self):
        self.installed = False
        self.failed = ''  # why the install failed ('' when it did not, or none was tried); a failure stands
        self.positive_control = 'not run'
        self.deny = {}  # id(code) -> code
        self.sizes = {}  # file key -> count
        self.wrappers = {}  # id(wrapper) -> the lru_cache wrapper of a denied function
        self.checks = {}  # the checks split, by name
        self.errors = 0  # callback failures in this process
        # a read in a process that cannot count says so once (FINAL 10.2): logged, and recorded on the first read that
        # names an encounter (an AuditEvent needs its workspace)
        self.unavailable_logged = False
        self.unavailable_recorded = False


_STATE = _State()
_LOCK = threading.RLock()
_FRAME = contextvars.ContextVar('cpt_studio_sentinel_frame', default=None)
_TOTALS = {label: {} for label in LABELS}  # the process's counts: closed outermost scopes, and unscoped executions
_UNSCOPED = _TOTALS[UNSCOPED]
_NAMES = {}  # id -> a readable name ('studio/gi/detect.py:120 route', 'studio.gi.cues.PAGE_NUMBER_LINE')
_KINDS = {}  # id -> CODE, REGEX or CACHE
_CALLS = {'depth': 0, 'exempt': {}}
_PATTERNS = frozenset()  # test mode: ids of the denied patterns
_WRAPPERS = frozenset()  # test mode: ids of the denied cache wrappers
_RE_FUNCTIONS = frozenset({re.search, re.match, re.fullmatch, re.finditer, re.findall, re.sub, re.subn, re.split})
_METHOD_DESCRIPTOR = type(re.Pattern.search)
# A builtin function or bound builtin method: 3.12 binds a pattern's methods as 'builtin_method' (PyCMethod), a subtype
# of 'builtin_function_or_method', so both types are named and matched exactly.
_BOUND = frozenset({type(len), type(re.compile('').search)})
_LRU_WRAPPER = functools._lru_cache_wrapper
STUDIO_DIR = Path(__file__).resolve().parent.parent  # the studio package
_APP_PREFIX = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + os.sep
HOLDERS = frozenset({'studio', 'cptstudio'})  # the production packages twins() reads (never a test's)


def _after_fork_in_child():
    global _LOCK
    _LOCK = threading.RLock()  # a lock another thread held at the fork would never be released in the child


os.register_at_fork(after_in_child=_after_fork_in_child)


class _Frame:
    """The ContextVar's value: the open scope and the label its executions count under."""
    __slots__ = ('label', 'scope', 'hits', 'new_path')

    def __init__(self, label, scope):
        self.label = label
        self.scope = scope
        self.hits = scope.hits.setdefault(label, {})
        self.new_path = label == NEW_PATH


class Scope:
    """One labelled stretch of work (FINAL 10.3): a worker stage, a web request naming an encounter, a forked child.
    ``hits`` counts the denied executions made while it was the innermost scope, by label and by what ran (an id; see
    names()); a nested scope's counts join it when that scope closes, and an outermost scope's join the process's
    totals. ``armed``: whether the sentinel was installed and proven when it opened. ``entries``: the first new_path
    entry points, each 'caller -> denied code'."""
    __slots__ = ('label', 'entry', 'parent', 'hits', 'entries', 'errors', 'armed', 'private', 'reported')

    def __init__(self, label, entry, parent=None, *, armed=False, private=False):
        self.label = label
        self.entry = entry
        self.parent = parent
        self.hits = {}
        self.entries = []
        self.errors = 0
        self.armed = armed
        self.private = private
        self.reported = False

    def count(self, label: str = NEW_PATH) -> int:
        """The executions counted under ``label`` in this scope alone."""
        return sum(self.hits.get(label, {}).values())

    def chain(self):
        """This scope and the scopes enclosing it, innermost first."""
        scope_ = self
        while scope_ is not None:
            yield scope_
            scope_ = scope_.parent

    def total(self, label: str = NEW_PATH) -> int:
        """The executions counted under ``label`` in this scope and every scope enclosing it: what a gate reads."""
        return sum(item.count(label) for item in self.chain())

    def counts(self) -> dict:
        """{label: executions} of this scope alone, for every label it counted."""
        return {label: total for label in self.hits if (total := self.count(label))}

    def by_kind(self, label: str = NEW_PATH) -> dict:
        """{CODE, REGEX, CACHE: executions} under ``label`` in this scope alone (FINAL 10.4(3): a positive control must
        record hits in every class)."""
        out = {CODE: 0, REGEX: 0, CACHE: 0}
        for key, n in self.hits.get(label, {}).items():
            out[_KINDS.get(key, CODE)] += n
        return out

    def describe(self, label: str = NEW_PATH) -> list:
        """'<name> x<count>' for each denied thing counted under ``label``, most first, then the entry points: what a
        failing test prints (FINAL 10.4(1): the file, the qualname and the first new-path frame)."""
        hits = sorted(self.hits.get(label, {}).items(), key=lambda item: (-item[1], _NAMES.get(item[0], '')))
        return [f'{_NAMES.get(key, f"id {key}")} x{n}' for key, n in hits] + [f'entered: {e}' for e in self.entries]

    def _entry(self, what: str, frame):
        if len(self.entries) >= MAX_ENTRIES:
            return
        caller = frame
        while caller is not None and id(caller.f_code) in _STATE.deny:
            caller = caller.f_back
        where = _where(caller) if caller is not None else 'no calling frame'
        self.entries.append(f'{where} -> {what}')

    def _close(self):
        if self.private:
            return
        with _LOCK:
            target = self.parent.hits if self.parent is not None else None
            for label, hits in self.hits.items():
                into = (target.setdefault(label, {}) if target is not None
                        else _TOTALS.setdefault(label, {}) if label in LABELS else None)
                if into is None:
                    continue
                for key, n in hits.items():
                    into[key] = into.get(key, 0) + n
            if self.parent is not None:
                room = MAX_ENTRIES - len(self.parent.entries)
                self.parent.entries.extend(self.entries[:max(room, 0)])
                self.parent.errors += self.errors


def _where(frame) -> str:
    code = frame.f_code
    return f'{_relative(code.co_filename)}:{frame.f_lineno} {code.co_qualname}'


def _relative(filename: str) -> str:
    return filename[len(_APP_PREFIX):] if filename.startswith(_APP_PREFIX) else filename


def _code_name(code) -> str:
    return f'{_relative(code.co_filename)}:{code.co_firstlineno} {code.co_qualname}'


# --- the callbacks (kept small: every denied execution in the process runs one) ----------------------------------------

def _on_start(code, instruction_offset):
    try:
        frame = _FRAME.get()
        key = id(code)
        if frame is None:
            hits = _UNSCOPED
        else:
            hits = frame.hits
            if frame.new_path and key not in hits:
                frame.scope._entry(_NAMES.get(key) or _code_name(code), sys._getframe(1).f_back)
        hits[key] = hits.get(key, 0) + 1
    except Exception:  # noqa: BLE001 - counted; a scope open while its instrument failed refuses its writes
        _failed_callback()
    return None


def _on_call(code, instruction_offset, func, arg0):
    try:
        if not code.co_filename.startswith(_APP_PREFIX):
            return sys.monitoring.DISABLE  # never checked: a call site outside the app (the re module's own, say)
        key = _denied_call(func, arg0)
        if key is None:
            return None
        frame = _FRAME.get()
        if frame is None:
            hits = _UNSCOPED
        else:
            hits = frame.hits
            if frame.new_path and key not in hits:
                frame.scope._entry(_NAMES.get(key, f'id {key}'), sys._getframe(1))
        hits[key] = hits.get(key, 0) + 1
    except Exception:  # noqa: BLE001 - as _on_start
        _failed_callback()
    return None


def _denied_call(func, arg0) -> Optional[int]:
    """The id of the denied pattern or cache wrapper a CALL event reads (R-3's three forms, the wrapper, and a pattern's
    bound method passed on), or None."""
    kind = type(func)
    if kind is _METHOD_DESCRIPTOR:
        if func.__objclass__ is re.Pattern and id(arg0) in _PATTERNS:
            return id(arg0)
    elif kind in _BOUND:
        if id(func.__self__) in _PATTERNS:
            return id(func.__self__)
    elif kind is types.FunctionType:
        if func in _RE_FUNCTIONS and id(arg0) in _PATTERNS:
            return id(arg0)
    elif id(func) in _WRAPPERS:
        return id(func)
    if type(arg0) in _BOUND and id(arg0.__self__) in _PATTERNS:
        return id(arg0.__self__)
    return None


def _failed_callback():
    _STATE.errors += 1
    frame = _FRAME.get()
    if frame is not None:
        frame.scope.errors += 1


def _probe_target():
    """The positive control's synthetic target: armed as a denied code object is, only while the control runs."""
    return None


# --- install -------------------------------------------------------------------------------------------------------------

def install() -> dict:
    """Install the sentinel in this process, once (FINAL 10.2; R-1): import the pinned deny modules, check the list
    against the files, compute the deny set from code objects and check it against its pins, acquire tool 4, arm every
    denied code object, and run the positive control. Every process installs it (AppConfig.ready, and a new_path scope
    as a backstop); a later call returns the standing status, a failure included. On any failure the process is left
    with no armed code and the reason, and refuses every new-path write. Returns status()."""
    with _LOCK:
        if _STATE.installed or _STATE.failed:
            return status()
        acquired = False
        try:
            if not hasattr(sys, 'monitoring'):
                raise _Refused('this Python has no sys.monitoring')
            _require_ready()
            _import_deny_modules()
            check_module_list()
            deny, sizes, checks, names = _compute()
            _check_pins(sizes, checks)
            monitoring = sys.monitoring
            holder = monitoring.get_tool(TOOL_ID)
            if holder is not None and holder != TOOL_NAME:
                raise _Refused(f'sys.monitoring tool {TOOL_ID} is held by {holder!r}')
            if holder is None:
                monitoring.use_tool_id(TOOL_ID, TOOL_NAME)
            acquired = True
            monitoring.register_callback(TOOL_ID, monitoring.events.PY_START, _on_start)
            for code in deny.values():
                monitoring.set_local_events(TOOL_ID, code, monitoring.events.PY_START)
            _STATE.deny, _STATE.sizes, _STATE.checks = deny, sizes, checks
            _STATE.wrappers = _denied_wrappers(deny)
            _NAMES.update(names)
            _KINDS.update({key: CODE for key in deny})
            for key, wrapper in _STATE.wrappers.items():
                _NAMES[key] = f'{getattr(wrapper, "__module__", "?")}.{getattr(wrapper, "__qualname__", "?")} (cache)'
                _KINDS[key] = CACHE
            _positive_control(deny)
        except _NotReady:
            return status()  # nothing was changed: a later call (AppConfig.ready, a new_path scope) installs
        except Exception as exc:  # noqa: BLE001 - any failure leaves the process refusing new-path writes, with why
            reason = str(exc) if isinstance(exc, _Refused) else f'{type(exc).__name__}: {exc}'
            if acquired:
                _disarm()
            _STATE.installed, _STATE.failed, _STATE.positive_control = False, reason, 'failed'
            _STATE.deny, _STATE.wrappers = {}, {}
            log.error('the legacy-call sentinel is not installed: %s; this process refuses new-path writes', reason)
            return status()
        _STATE.installed, _STATE.failed, _STATE.positive_control = True, '', 'ok'
        return status()


def _require_ready():
    """_NotReady while Django is loaded but its models are not (the deny modules import them); an install made then would
    fail for a reason that a moment later no longer holds. AppConfig.ready() runs once the models are ready, before the
    registry calls itself ready, which is why models_ready is read, not ready."""
    django_apps = sys.modules.get('django.apps')
    if django_apps is not None and not django_apps.apps.models_ready:
        raise _NotReady()


def _import_deny_modules():
    """R-1: the pinned modules, imported here and now, before anything is walked."""
    for name in DENY_MODULES + (CHECKS_MODULE, JOBS_MODULE):
        importlib.import_module(name)


def expected_modules(root: Path = STUDIO_DIR) -> set:
    """R-1's list, read from the files under ``root`` (the studio package): every studio/gi/*.py but profiles and
    catalogue, the named validation files and candidates.py. Raises _Refused when a named file is missing or studio/gi
    holds a subpackage (a module there would not be a studio/gi/*.py file)."""
    gi = root / 'gi'
    found = {'studio.gi' if path.stem == '__init__' else f'studio.gi.{path.stem}'
             for path in gi.glob('*.py') if path.stem not in GI_KEPT}
    for name in VALIDATION_DENIED:
        if not (root / 'validation' / f'{name}.py').is_file():
            raise _Refused(f'studio/validation/{name}.py, a denied file, does not exist')
    if not (root / 'candidates.py').is_file():
        raise _Refused('studio/candidates.py, a denied file, does not exist')
    nested = sorted(str(path.relative_to(root)) for path in gi.glob('*/*.py') if '__pycache__' not in path.parts)
    if nested:
        raise _Refused(f'studio/gi holds a subpackage outside the deny list: {nested}')
    return found | {f'studio.validation.{name}' for name in VALIDATION_DENIED} | {'studio.candidates'}


def check_module_list(root: Path = STUDIO_DIR, modules: tuple = DENY_MODULES):
    """R-1: ``modules`` (DENY_MODULES) names each module once and equals expected_modules(root); _Refused otherwise."""
    expected = expected_modules(root)
    if len(set(modules)) != len(modules) or set(modules) != expected:
        missing, extra = sorted(expected - set(modules)), sorted(set(modules) - expected)
        raise _Refused(f'the pinned deny modules differ from the files: missing {missing}, not a file {extra}')


def _module_key(module) -> str:
    """'studio/gi/detect.py', 'studio/gi/__init__.py': a file's name in the pins, from its module, not the disk."""
    name = module.__name__.replace('.', '/')
    return f'{name}/__init__.py' if hasattr(module, '__path__') else f'{name}.py'


def _tree(code, out: dict) -> dict:
    """``code`` and every code object nested in it, by id."""
    if id(code) not in out:
        out[id(code)] = code
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                _tree(const, out)
    return out


def _unwrap(value):
    for _ in range(16):
        inner = getattr(value, '__wrapped__', None)
        if inner is None:
            break
        value = inner
    return value


def _live_codes(files, modules=()) -> dict:
    """{file: {id: code}}: every code object of a live function whose co_filename is one of ``files``, and every code
    object nested in one. Found through the collector, so a function held only by a container, a closure or a cache is
    found too, and through ``modules``' globals as well, so a collector that was frozen (gc.freeze hides what it froze
    from gc.get_objects) cannot shrink the set unseen. A module or class body is not found: it ran once, at import."""
    found = {path: {} for path in files}

    def take(fn):
        bucket = found.get(fn.__code__.co_filename)
        if bucket is not None:
            _tree(fn.__code__, bucket)

    for obj in gc.get_objects():
        if type(obj) is types.FunctionType:
            take(obj)
    for module in modules:
        for fn in _module_functions(module):
            take(fn)
    return found


def _module_functions(module) -> list:
    """The functions a module's globals hold: directly, behind a decorator's __wrapped__, in a container, or as a method,
    static or class method or property of a class defined in the module."""
    out, seen, owner = [], set(), module.__name__

    def visit(value, depth):
        if depth > 6 or id(value) in seen:
            return
        seen.add(id(value))
        inner = _unwrap(value)
        if isinstance(inner, types.FunctionType):
            out.append(inner)
        elif isinstance(value, (staticmethod, classmethod)):
            visit(value.__func__, depth + 1)
        elif isinstance(value, property):
            for part in (value.fget, value.fset, value.fdel):
                if part is not None:
                    visit(part, depth + 1)
        elif isinstance(value, (tuple, list, set, frozenset)):
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, dict):
            for item in list(value.values()):
                visit(item, depth + 1)
        elif isinstance(value, type) and value.__module__ == owner:
            for item in list(vars(value).values()):
                visit(item, depth + 1)

    for value in list(vars(module).values()):
        if not isinstance(value, types.ModuleType):
            visit(value, 0)
    return out


def _top_functions(module) -> dict:
    """{name: function} for the module's globals bound to a function defined in its own file (unwrapped)."""
    out = {}
    for name, value in vars(module).items():
        fn = _unwrap(value)
        if isinstance(fn, types.FunctionType) and fn.__code__.co_filename == module.__file__:
            out[name] = fn
    return out


def _instructions(tree: dict):
    for code in tree.values():
        yield from dis.get_instructions(code)


def _global_refs(tree: dict) -> set:
    return {ins.argval for ins in _instructions(tree) if ins.opname == 'LOAD_GLOBAL'}


def _imports(tree: dict, package: str) -> list:
    """[(module, fromlist)] of every import statement in ``tree``, resolved against ``package``."""
    out = []
    for code in tree.values():
        listed = list(dis.get_instructions(code))
        for at, ins in enumerate(listed):
            if ins.opname != 'IMPORT_NAME':
                continue
            level = listed[at - 2].argval if at >= 2 and listed[at - 2].opname == 'LOAD_CONST' else 0
            fromlist = listed[at - 1].argval if at >= 1 and listed[at - 1].opname == 'LOAD_CONST' else None
            name = ins.argval
            if level:
                parts = package.split('.')
                base = '.'.join(parts[:len(parts) - (level - 1)])
                name = f'{base}.{name}' if name else base
            out.append((name, tuple(fromlist or ())))
    return out


def _legacy_import(name: str, fromlist: tuple) -> bool:
    """Whether an import names a studio.gi module other than the reference tables."""
    if name == 'studio.gi':
        return not fromlist or any(item not in GI_KEPT for item in fromlist)
    return name.startswith('studio.gi.') and name.split('.')[2] not in GI_KEPT


def _closure(graph: dict, start) -> set:
    seen, stack = set(start), list(start)
    while stack:
        for callee in graph.get(stack.pop(), ()):
            if callee not in seen:
                seen.add(callee)
                stack.append(callee)
    return seen


def _reaching(graph: dict, targets) -> set:
    callers = {}
    for caller, callees in graph.items():
        for callee in callees:
            callers.setdefault(callee, set()).add(caller)
    return _closure(callers, targets)


def _checks_graph(module) -> tuple:
    """(top functions by name, their code trees by name, the call graph by name) of checks.py, from its own code."""
    top = _top_functions(module)
    trees = {name: _tree(fn.__code__, {}) for name, fn in top.items()}
    graph = {name: (_global_refs(tree) & top.keys()) - {name} for name, tree in trees.items()}
    return top, trees, graph


def checks_split(module=None, codes=None) -> dict:
    """The checks.py split (R-5; FINAL 10.1(3)), computed from the module's code: {'allowed', 'helpers', 'denied',
    'importers', 'reaching', 'named'} by function name; {'patterns_allowed', 'patterns_denied'}, its pattern globals
    split the same way (checks_patterns); and 'codes', the denied code objects by id. Raises _Refused when the allowlist
    names a function the module lacks or reaches a function 10.1(3) denies."""
    module = module or sys.modules[CHECKS_MODULE]
    if codes is None:
        codes = _live_codes({module.__file__}, [module])[module.__file__]
    top, trees, graph = _checks_graph(module)
    package = module.__name__.rpartition('.')[0]
    importers = {name for name, tree in trees.items()
                 if any(_legacy_import(found, fromlist) for found, fromlist in _imports(tree, package))}
    reaching = _reaching(graph, importers)
    absent = [name for name in CHECKS_ALLOWLIST + CHECKS_NAMED_READERS if name not in top]
    if absent:
        raise _Refused(f'checks.py has no function {absent}')
    for name in CHECKS_ALLOWLIST_CONSTANTS:
        if not hasattr(module, name):
            raise _Refused(f'checks.py has no {name}')
    allowed = _closure(graph, CHECKS_ALLOWLIST)
    clash = sorted(allowed & (reaching | set(CHECKS_NAMED_READERS)))
    if clash:
        raise _Refused(f'the checks allowlist reaches functions FINAL 10.1(3) denies: {clash}')
    allowed_ids = set()
    for name in allowed:
        allowed_ids |= trees[name].keys()
    return {'allowed': sorted(allowed), 'helpers': sorted(allowed - set(CHECKS_ALLOWLIST)),
            'denied': sorted(set(top) - allowed), 'importers': sorted(importers),
            'reaching': sorted(reaching - importers), 'named': sorted(CHECKS_NAMED_READERS),
            **_split_patterns(module, trees, allowed),
            'codes': {key: code for key, code in codes.items() if key not in allowed_ids}}


def checks_patterns(module=None) -> dict:
    """R-5 applied to checks.py's compiled patterns (FINAL 10.2's CALL checks): {'patterns_allowed', 'patterns_denied'},
    its pattern globals by name. A global is allowed when a function of the allowed closure, or an allowlisted constant,
    names it (LOAD_GLOBAL); every other one is denied - the keyword vocabularies of the denied _V2_ and _VAL_ readers."""
    module = module or sys.modules[CHECKS_MODULE]
    top, trees, graph = _checks_graph(module)
    return _split_patterns(module, trees, _closure(graph, [name for name in CHECKS_ALLOWLIST if name in top]))


def _split_patterns(module, trees: dict, allowed) -> dict:
    named = set(CHECKS_ALLOWLIST_CONSTANTS)
    for name in allowed:
        named |= _global_refs(trees[name])
    held = _pattern_globals(module)
    return {'patterns_allowed': sorted(name for name in held if name in named),
            'patterns_denied': sorted(name for name in held if name not in named)}


def _compute():
    """(deny {id: code}, sizes {file key: n}, checks split by name, names {id: readable name})."""
    modules = [sys.modules[name] for name in DENY_MODULES]
    checks_module, jobs = sys.modules[CHECKS_MODULE], sys.modules[JOBS_MODULE]
    live = _live_codes({module.__file__ for module in modules + [checks_module]}, modules + [checks_module])
    deny, sizes = {}, {}
    for module in modules:
        codes = live[module.__file__]
        deny.update(codes)
        sizes[_module_key(module)] = len(codes)
    split = checks_split(checks_module, live[checks_module.__file__])
    deny.update(split.pop('codes'))
    sizes[_module_key(checks_module)] = len(deny) - sum(sizes.values())
    archived = {}
    for name in ARCHIVED_JOBS:
        fn = _unwrap(getattr(jobs, name, None))
        if not isinstance(fn, types.FunctionType) or fn.__code__.co_filename != jobs.__file__:
            raise _Refused(f'studio/jobs.py has no archived function {name}')
        _tree(fn.__code__, archived)
    deny.update(archived)
    sizes[_module_key(jobs)] = len(archived)
    return deny, sizes, split, {key: _code_name(code) for key, code in deny.items()}


def _check_pins(sizes: dict, checks: dict):
    if sizes != PINNED_SIZES:
        differ = {key: (sizes.get(key), PINNED_SIZES.get(key)) for key in sorted(set(sizes) | set(PINNED_SIZES))
                  if sizes.get(key) != PINNED_SIZES.get(key)}
        raise _Refused(f'the deny set differs from its pins (computed, pinned): {differ}')
    for field, pinned in (('denied', CHECKS_DENIED), ('helpers', CHECKS_ALLOWED_HELPERS),
                          ('importers', CHECKS_GI_IMPORTERS), ('patterns_denied', CHECKS_DENIED_PATTERNS),
                          ('patterns_allowed', CHECKS_ALLOWED_PATTERNS)):
        if tuple(checks[field]) != tuple(sorted(pinned)):
            raise _Refused(f'the checks split differs from its pin: {field}')


def _denied_wrappers(deny: dict) -> dict:
    """{id: wrapper} of every live lru_cache wrapper whose innermost function is denied."""
    out = {}
    for obj in gc.get_objects():
        if type(obj) is _LRU_WRAPPER:
            code = getattr(_unwrap(obj), '__code__', None)
            if code is not None and id(code) in deny:
                out[id(obj)] = obj
    return out


def _positive_control(deny: dict):
    """FINAL 10.2-10.4: an instrument that never fires proves nothing. Every denied code object armed; the PY_START
    callback the sentinel's; a sentinel-owned code object, armed as a denied one is, counted exactly once under the probe
    label; and one real denied function counted when it runs."""
    monitoring = sys.monitoring
    unarmed = sum(1 for code in deny.values()
                  if not monitoring.get_local_events(TOOL_ID, code) & monitoring.events.PY_START)
    if unarmed:
        raise _Refused(f'{unarmed} denied code objects are not armed')
    if monitoring.register_callback(TOOL_ID, monitoring.events.PY_START, _on_start) is not _on_start:
        raise _Refused('the PY_START callback of tool 4 is not the sentinel\'s')
    probe = _probe_target.__code__
    monitoring.set_local_events(TOOL_ID, probe, monitoring.events.PY_START)
    try:
        with _private() as scope_:
            _probe_target()
    finally:
        monitoring.set_local_events(TOOL_ID, probe, 0)
    if scope_.hits.get(PROBE, {}).get(id(probe)) != 1:
        raise _Refused('the positive control was not counted')
    fn = _probe_function()
    if id(fn.__code__) not in deny:
        raise _Refused(f'the positive control {PROBE_CALL[0]}.{PROBE_CALL[1]} is not denied')
    with _private() as scope_:
        fn(*PROBE_CALL[2])
    if not scope_.hits.get(PROBE, {}).get(id(fn.__code__)):
        raise _Refused(f'the positive control {PROBE_CALL[0]}.{PROBE_CALL[1]} ran and was not counted')


def _probe_function():
    module, name, _ = PROBE_CALL
    return getattr(sys.modules[module], name)


@contextlib.contextmanager
def _private(label: str = PROBE):
    """A scope of its own that joins nothing: the positive control's, and the trip test's."""
    scope_ = Scope(label, 'positive control', armed=True, private=True)
    token = _FRAME.set(_Frame(label, scope_))
    try:
        yield scope_
    finally:
        _FRAME.reset(token)


def trip_test() -> dict:
    """The positive control TRIPS (FINAL 10.4(3); the D22 self-test): in a private new_path scope of this process, the
    probe call - a real denied function - is counted and the write gate's rule refuses it ('executed'); in a clean
    private new_path scope the rule refuses nothing. Neither scope joins any total, and nothing is recorded. {'tripped',
    'clean', 'counted', 'ok'}; ok only when installed, tripped and clean."""
    if not _STATE.installed:
        return {'tripped': False, 'clean': False, 'counted': 0, 'ok': False}
    fn = _probe_function()
    with _private(NEW_PATH) as dirty:
        fn(*PROBE_CALL[2])
    with _private(NEW_PATH) as clean:
        pass
    tripped, unrefused = refusal(dirty) == 'executed', refusal(clean) is None
    return {'tripped': tripped, 'clean': unrefused, 'counted': dirty.count(NEW_PATH), 'ok': tripped and unrefused}


def _disarm():
    monitoring = sys.monitoring
    if monitoring.get_tool(TOOL_ID) != TOOL_NAME:
        return  # freed, or held by another tool: nothing of tool 4 can be changed (a freed id refuses every call)
    for code in _STATE.deny.values():
        monitoring.set_local_events(TOOL_ID, code, 0)
    monitoring.set_events(TOOL_ID, 0)
    monitoring.register_callback(TOOL_ID, monitoring.events.PY_START, None)
    monitoring.register_callback(TOOL_ID, monitoring.events.CALL, None)
    monitoring.free_tool_id(TOOL_ID)


def uninstall():
    """TESTS ONLY: disarm, free tool 4 and forget the install (or its failure), so a test can install from nothing or
    fail one. Never called by the application: a process never stops counting once it has started."""
    global _PATTERNS, _WRAPPERS
    with _LOCK:
        if hasattr(sys, 'monitoring'):
            _disarm()
        _CALLS['depth'] = 0
        _PATTERNS = _WRAPPERS = frozenset()
        state = _State()
        state.errors = _STATE.errors
        _STATE.__dict__.update(state.__dict__)


def status() -> dict:
    """This process's sentinel, as the D22 report and the operator read it."""
    state = 'ok' if _STATE.installed else 'failed' if _STATE.failed else 'not installed'
    return {'state': state, 'reason': _STATE.failed, 'tool': TOOL, 'tool_id': TOOL_ID, 'tool_name': TOOL_NAME,
            'deny_size': len(_STATE.deny), 'pinned_deny_size': DENY_SIZE, 'sizes': dict(_STATE.sizes),
            'checks_denied': len(_STATE.checks.get('denied', ())), 'caches': len(_STATE.wrappers),
            'positive_control': _STATE.positive_control, 'callback_errors': _STATE.errors,
            'python': '.'.join(str(part) for part in sys.version_info[:3])}


def installed() -> bool:
    return _STATE.installed


def deny_set() -> dict:
    """{id: code} of the armed deny set (empty unless installed)."""
    return dict(_STATE.deny)


def names() -> dict:
    """{id: readable name} of everything the sentinel counts: denied code, and in test mode patterns and caches."""
    return dict(_NAMES)


# --- scopes and labels ---------------------------------------------------------------------------------------------------

@contextlib.contextmanager
def scope(label: str, *, entry: str):
    """A labelled scope (FINAL 10.3). A new_path scope installs the sentinel first if this process has not (a backstop:
    AppConfig.ready installs it in every process) and clears the denied caches, so a cache hit cannot answer for a legacy
    function without executing it (FINAL 10.2). Yields the Scope."""
    if label not in SCOPE_LABELS:
        raise ValueError(f'A scope is labelled one of {", ".join(SCOPE_LABELS)}.')
    if label == NEW_PATH:
        install()
        clear_caches()
    frame = _FRAME.get()
    opened = Scope(label, entry, frame.scope if frame is not None else None, armed=_STATE.installed)
    token = _FRAME.set(_Frame(label, opened))
    try:
        yield opened
    finally:
        _FRAME.reset(token)
        opened._close()


@contextlib.contextmanager
def relabel(label: str):
    """Count under ``label`` within the open scope - a reader's label for one row (LegacyReader: legacy_record;
    EventReader: new_path). A row relabelled new_path clears the denied caches first, as a new_path scope does: a list
    view's legacy rows must not leave a cached legacy answer for its new rows. With no scope open, a scope of that label
    is opened. Yields the scope."""
    if label not in SCOPE_LABELS:
        raise ValueError(f'A label is one of {", ".join(SCOPE_LABELS)}.')
    frame = _FRAME.get()
    if frame is None:
        with scope(label, entry='relabel') as opened:
            yield opened
        return
    if label == NEW_PATH and not frame.new_path:
        clear_caches()
    token = _FRAME.set(_Frame(label, frame.scope))
    try:
        yield frame.scope
    finally:
        _FRAME.reset(token)


def current() -> Optional[Scope]:
    frame = _FRAME.get()
    return frame.scope if frame is not None else None


def label() -> str:
    frame = _FRAME.get()
    return frame.label if frame is not None else UNSCOPED


def totals() -> dict:
    """{label: executions} this process counted in closed outermost scopes and outside any scope."""
    with _LOCK:
        return {name: sum(_TOTALS.get(name, {}).values()) for name in LABELS}


def top(label_: str, limit: int = MAX_ENTRIES) -> list:
    """'<name> x<count>' of what this process counted under ``label_`` in closed outermost scopes (unscoped: outside any
    scope), most first: the residual legacy execution an operator reads beside the totals."""
    with _LOCK:
        hits = sorted(_TOTALS.get(label_, {}).items(), key=lambda item: (-item[1], _NAMES.get(item[0], '')))
    return [f'{_NAMES.get(key, f"id {key}")} x{n}' for key, n in hits[:limit]]


def clear_caches() -> int:
    """Clear every denied lru cache; the number cleared."""
    for wrapper in _STATE.wrappers.values():
        wrapper.cache_clear()
    return len(_STATE.wrappers)


# --- forked children (FINAL 10.2: monitoring survives fork; the child returns its counters with its result) -------------

def counted(fn, *args):
    """``fn(*args)`` in a forked child, as (result, counts): what the child counted, under the label it inherited, for
    the parent's merge(). Pass it to bounded.run_bounded as the function (run_counted does both). When ``fn`` raises, the
    counts still come back, with the error (its traceback), and run_counted raises after merging them: a child whose
    work failed after it ran legacy code is still counted against its scope."""
    frame = _FRAME.get()
    inherited = frame.label if frame is not None else UNSCOPED
    child = Scope(inherited, 'forked child', armed=_STATE.installed, private=True)
    token = _FRAME.set(_Frame(inherited, child))
    result, error = None, ''
    try:
        result = fn(*args)
    except MemoryError:
        raise  # bounded reports it as the memory limit
    except Exception:  # noqa: BLE001 - returned with the counts; run_counted raises it in the parent
        error = traceback.format_exc()
    finally:
        _FRAME.reset(token)
    return result, {'hits': {name: dict(hits) for name, hits in child.hits.items()}, 'entries': list(child.entries),
                    'errors': child.errors, 'armed': child.armed, 'error': error}


def merge(counts: dict):
    """Add a forked child's counts (counted's second value) to the open scope, or to the process's totals."""
    frame = _FRAME.get()
    target = frame.scope if frame is not None else None
    with _LOCK:
        for name, hits in counts.get('hits', {}).items():
            into = (target.hits.setdefault(name, {}) if target is not None
                    else _TOTALS.setdefault(name, {}) if name in LABELS else None)
            if into is None:
                continue
            for key, n in hits.items():
                into[key] = into.get(key, 0) + n
    if target is not None:
        room = MAX_ENTRIES - len(target.entries)
        target.entries.extend(list(counts.get('entries', ()))[:max(room, 0)])
        target.errors += int(counts.get('errors', 0)) + (0 if counts.get('armed', True) else 1)


def run_counted(fn, *args, seconds, memory_bytes):
    """bounded.run_bounded(fn, *args) with the child's counts merged into the open scope; returns fn's result. A child
    whose ``fn`` raised raises here as bounded.run_bounded's own child failure does (RuntimeError, the error logged),
    after its counts were merged."""
    from studio import bounded

    result, counts = bounded.run_bounded(counted, fn, *args, seconds=seconds, memory_bytes=memory_bytes)
    merge(counts)
    if counts.get('error'):
        log.error('bounded child failed:\n%s', counts['error'])
        raise RuntimeError('The bounded child failed; the error was logged.')
    return result


# --- gates and the D22 record --------------------------------------------------------------------------------------------

def _intact() -> bool:
    """Whether tool 4 is still the sentinel's, with the sentinel's PY_START callback. Anything that freed the tool or
    replaced the callback after the install stopped every count from then on, so the process can vouch for nothing:
    it is failed for good (the callback is put back only so that later counting resumes - the failure stands)."""
    monitoring = sys.monitoring
    held = monitoring.get_tool(TOOL_ID) == TOOL_NAME
    ours = held and monitoring.register_callback(TOOL_ID, monitoring.events.PY_START, _on_start) is _on_start
    if ours:
        return True
    with _LOCK:
        if _STATE.installed:
            _STATE.installed, _STATE.positive_control = False, 'failed'
            _STATE.failed = (f'sys.monitoring tool {TOOL_ID} was freed after the install' if not held else
                             f'the PY_START callback of tool {TOOL_ID} was replaced after the install')
            log.error('the legacy-call sentinel is no longer counting: %s; this process refuses new-path writes',
                      _STATE.failed)
    return False


def refusal(scope_: Optional[Scope] = None) -> Optional[str]:
    """Why a new-path write in ``scope_`` (default: the open one) would be refused, or None."""
    scope_ = scope_ if scope_ is not None else current()
    if not _STATE.installed or not _intact():
        return 'unavailable'
    if scope_ is None:
        return 'unscoped'
    if not all(item.armed for item in scope_.chain()):
        return 'unavailable'
    if any(item.errors for item in scope_.chain()):
        return 'instrument'
    if scope_.total(NEW_PATH):
        return 'executed'
    return None


def gate(entry: str, *, encounter=None, actor=None, scope_: Optional[Scope] = None):
    """A new-path WRITE gate (FINAL 10.3): an EventInventory insert, a gemini context or routing insert,
    persist_assessment of a new-path assessment, record_decision on one, report generation from one, a member answer on a
    new-path revision. Returns None when the write may proceed; otherwise records AuditEvent 'sentinel.tripped' on
    ``encounter``'s workspace (logged only, without one) and raises Tripped, which the caller turns into a failed stage
    or a 409. Call it before opening the write's transaction: a row written inside one the refusal rolls back is lost
    (the log line stays)."""
    scope_ = scope_ if scope_ is not None else current()
    reason = refusal(scope_)
    if reason is None:
        return None
    data = _trip(entry, reason, scope_, refused=True)
    _audit(encounter, actor, data)
    raise Tripped(reason, data)


def observe(entry: str, *, encounter=None, actor=None, scope_: Optional[Scope] = None) -> dict:
    """A new-path READ (FINAL 10.3): never refuses, for availability, and records AuditEvent 'sentinel.tripped' (refused
    false) for what a write in its place would be refused for:
    - this process's sentinel is not installed and proven ('unavailable', with the install's reason): once per PROCESS,
      whatever the scope, so a process that cannot count is on record - in the D22 report, where 'no sentinel trip'
      then fails - before any write of its trips a gate (FINAL 10.2: "The web records it. The D22 report shows it.");
    - otherwise the scope's own reason ('executed', 'instrument', or 'unavailable' for a scope opened before the
      install): once per scope. A read outside any scope records nothing more.
    Returns the scope's counts."""
    scope_ = scope_ if scope_ is not None else current()
    if not _STATE.installed or not _intact():
        _unavailable_read(entry, encounter, actor, scope_)
    elif scope_ is not None and not scope_.reported:
        reason = refusal(scope_)
        if reason is not None:
            scope_.reported = True
            _audit(encounter, actor, _trip(entry, reason, scope_, refused=False))
    return scope_.counts() if scope_ is not None else {}


def _unavailable_read(entry: str, encounter, actor, scope_: Optional[Scope]):
    """A read in a process whose sentinel cannot count: logged once, and recorded once, on the first read that names an
    encounter."""
    with _LOCK:
        if _STATE.unavailable_recorded or (encounter is None and _STATE.unavailable_logged):
            return
        _STATE.unavailable_logged = True
        _STATE.unavailable_recorded = encounter is not None
    try:
        _audit(encounter, actor, _trip(entry, 'unavailable', scope_, refused=False))
    except Exception:
        _STATE.unavailable_recorded = False  # not recorded: the next read that names an encounter records it
        raise


def _trip(entry: str, reason: str, scope_: Optional[Scope], *, refused: bool) -> dict:
    chain = list(scope_.chain()) if scope_ is not None else []
    counts = {}
    for item in chain:
        for name, n in item.counts().items():
            counts[name] = counts.get(name, 0) + n
    entries = [e for item in chain for e in item.entries][:MAX_ENTRIES]
    executed = [line for item in chain for line in item.describe(NEW_PATH) if not line.startswith('entered: ')]
    return {'entry': entry, 'reason': reason, 'refused': refused, 'scope': scope_.entry if scope_ else '',
            'label': scope_.label if scope_ else UNSCOPED, 'counts': counts, 'entry_points': entries,
            'executed': executed[:MAX_ENTRIES], 'install': 'ok' if _STATE.installed else (_STATE.failed or 'not installed'),
            'deny_size': len(_STATE.deny)}


def _audit(encounter, actor, data: dict):
    log.error('legacy-call sentinel tripped: %s', data)
    if encounter is None:
        return
    from studio import audit

    audit.record(encounter.workspace, TRIPPED, encounter=encounter, actor=actor, **data)


def record(scope_: Optional[Scope] = None, *, name: Optional[str] = None) -> dict:
    """The D22 record of a new-path assessment (FINAL 10.3; Assessment.interpretation['sentinel']): {legacy_calls,
    scope, tool, deny_size, positive_control}. legacy_calls is the new_path executions of the scope and the scopes
    enclosing it."""
    scope_ = scope_ if scope_ is not None else current()
    if scope_ is None:
        raise ValueError('The sentinel record is made inside the scope whose work it records.')
    return {'legacy_calls': scope_.total(NEW_PATH), 'scope': name or scope_.entry, 'tool': TOOL,
            'deny_size': len(_STATE.deny), 'positive_control': _STATE.positive_control}


# --- test mode: CALL-level checks (FINAL 10.2; R-3) ----------------------------------------------------------------------

@contextlib.contextmanager
def call_checks():
    """TESTS ONLY. While open, CALL events are on for every code object in the process and a call from the app's own code
    that reads a denied pattern or a denied cache wrapper is counted under the current label (kinds REGEX and CACHE).
    Raises RuntimeError when the sentinel cannot be installed."""
    global _PATTERNS, _WRAPPERS
    if not install()['state'] == 'ok':
        raise RuntimeError(f'The sentinel is not installed: {_STATE.failed or "the app registry is not ready"}')
    monitoring = sys.monitoring
    with _LOCK:
        _CALLS['depth'] += 1
        if _CALLS['depth'] == 1:
            patterns, exempt = denied_patterns()
            for key, (pattern, where) in patterns.items():
                _NAMES[key] = where
                _KINDS[key] = REGEX
            _PATTERNS, _WRAPPERS = frozenset(patterns), frozenset(_STATE.wrappers)
            _CALLS['exempt'] = {key: where for key, (where, _) in exempt.items()}  # names only: no pattern is kept
            monitoring.register_callback(TOOL_ID, monitoring.events.CALL, _on_call)
            monitoring.set_events(TOOL_ID, monitoring.events.CALL)
    try:
        yield
    finally:
        with _LOCK:
            _CALLS['depth'] -= 1
            if _CALLS['depth'] == 0:
                monitoring.set_events(TOOL_ID, 0)
                monitoring.register_callback(TOOL_ID, monitoring.events.CALL, None)
                _PATTERNS = _WRAPPERS = frozenset()


@contextlib.contextmanager
def strict(entry: str = 'strict'):
    """TESTS ONLY (FINAL 15, S08: "the sentinel in strict mode shows zero denied executions"): a new_path scope with the
    CALL-level checks on. Yields the scope; on a clean exit raises AssertionError naming every denied execution it
    counted (the file, the qualname and the first new-path frame), if any."""
    with call_checks(), scope(NEW_PATH, entry=entry) as opened:
        yield opened
    if opened.count(NEW_PATH):
        raise AssertionError('denied executions in a new_path scope:\n  ' + '\n  '.join(opened.describe(NEW_PATH)))


def denied_patterns() -> tuple:
    """({id: (pattern, where)} of the denied patterns; {id: (where, why)} of the pinned exemptions). Denied: every
    compiled pattern a denied module's globals hold - directly, in a container, a class of the module or an instance of
    one - and every pattern of checks.py's denied globals (checks_patterns), but never one its allowed globals hold too
    (code_scope reads SCOPE_FORMATS on the new path). Exempt: a pattern any of whose denied locations EXEMPT_PATTERNS
    names, and nothing else - whichever module holds a pattern, it stays denied, so a module that imports a legacy
    pattern cannot exempt it, and a new exemption is a deliberate edit of the pin."""
    found = _denied_locations()
    exempt = {}
    for key, (pattern, wheres) in list(found.items()):
        pinned = [where for where in wheres if where in EXEMPT_PATTERNS]
        if pinned:
            exempt[key] = (pinned[0], EXEMPT_PATTERNS[pinned[0]])
            del found[key]
    return {key: (pattern, wheres[0]) for key, (pattern, wheres) in found.items()}, exempt


def _denied_locations() -> dict:
    """{id: (pattern, [every location a denied module or a denied checks global holds it under])}, before exemptions."""
    found = {}

    def add(pattern, where):
        found.setdefault(id(pattern), (pattern, []))[1].append(where)

    for name in DENY_MODULES:
        for located in _pattern_globals(sys.modules[name]).values():
            for where, pattern in located.items():
                add(pattern, where)
    checks = sys.modules[CHECKS_MODULE]
    # the split the install computed and checked against its pins, else computed now (by name: it never goes stale)
    split = _STATE.checks if 'patterns_denied' in _STATE.checks else checks_patterns(checks)
    held = _pattern_globals(checks)
    allowed = {id(pattern) for name in split['patterns_allowed'] for pattern in held[name].values()}
    for name in split['patterns_denied']:
        for where, pattern in held[name].items():
            add(pattern, where)
    for key in allowed:
        found.pop(key, None)
    return found


def twins() -> dict:
    """TESTS ONLY (the pin of EXEMPT_PATTERNS): {location: [denied locations]} for every compiled pattern a loaded
    PRODUCTION module holds - the application's own packages (HOLDERS) outside the denied modules, this module and
    checks.py's denied globals - whose source and flags are a denied pattern's: the same object or not, since re's cache
    returns one object for one source in some import orders and not in others. A twin is either new code's own regex,
    whose denied original EXEMPT_PATTERNS names, or a legacy pattern a module imported, which stays denied; the test
    fails on a twin of an unpinned pattern, so neither arrives unseen."""
    by_source = {}
    for pattern, wheres in _denied_locations().values():
        by_source.setdefault((pattern.pattern, pattern.flags), set()).update(wheres)
    allowed = set(checks_patterns()['patterns_allowed'])
    out = {}
    for name, module in sorted(sys.modules.items()):
        if (module is None or name.partition('.')[0] not in HOLDERS or name in DENY_MODULES
                or name == __name__):
            continue
        for held, located in _pattern_globals(module).items():
            if name == CHECKS_MODULE and held not in allowed:
                continue
            for where, pattern in located.items():
                original = by_source.get((pattern.pattern, pattern.flags))
                if original:
                    out[where] = sorted(original)
    return out


def _pattern_globals(module) -> dict:
    """{global name: {location: pattern}}: every compiled pattern the module's globals hold - directly, in a container,
    in a class defined in the module or in an instance of one - under the global that holds it (an object held twice is
    listed at each location)."""
    out, owner = {}, module.__name__

    def visit(value, where, depth, seen, into):
        if depth > 6:
            return
        if isinstance(value, re.Pattern):
            into.setdefault(where, value)
            return
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, (tuple, list, set, frozenset)):
            for at, item in enumerate(value):
                visit(item, f'{where}[{at}]', depth + 1, seen, into)
        elif isinstance(value, dict):
            for key, item in list(value.items()):
                visit(item, f'{where}[{key!r}]', depth + 1, seen, into)
        elif isinstance(value, type):
            if value.__module__ == owner:
                for key, item in list(vars(value).items()):
                    visit(item, f'{where}.{key}', depth + 1, seen, into)
        elif type(value).__module__ == owner and hasattr(value, '__dict__'):
            for key, item in list(vars(value).items()):
                visit(item, f'{where}.{key}', depth + 1, seen, into)

    for key, value in list(vars(module).items()):
        if not isinstance(value, types.ModuleType):
            located = {}
            visit(value, f'{owner}.{key}', 0, set(), located)
            if located:
                out[key] = located
    return out
