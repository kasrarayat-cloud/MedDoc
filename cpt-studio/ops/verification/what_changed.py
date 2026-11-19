#!/usr/bin/env python3
"""The differential check of "what changed" (docs/gemini-migration/AMENDMENT-1.md 11.3; step 6b of its section 10).

    python3 ops/verification/what_changed.py --operator OP.json --customer CUST.json [--app-root cpt-studio]

An independent implementation of the amendment's 6.2, written from that text WITHOUT reading customer_api.what_changed,
over the stored rows the operator API serves for one encounter (``what_changed_rows``, schema ROWS_SCHEMA: OP.json is
GET /ops/api/encounters/<id> read by an operator). U11 and W7 compare the page's ``what_changed`` (CUST.json, GET
/api/encounters/<id> read by a member) with ``compute``'s, field by field (``compare``); a difference fails the check and
is the finding. Exit 0 when they agree, 1 when they differ or a part could not be judged, 2 when an input is not usable.

WHAT IS READ. Stored rows only, as 6.2 says - Assessment, Proposal, Clarification, EncounterContext, Decision,
DecisionInvalidation, SourceRevision, and for step 5 MemberAnswer and its revocation - never the review overlay, a
reader, the clock or the configuration. Two values are the product's own and are served beside the rows, never derived
here: ``fresh`` (review.fresh, a precondition of 6.2: "null unless the encounter is fresh") and a proposal's
``other_reason`` (6.2 step 3: the other-codes list's reason, customer_api._exclusion_reason's "Not suggested: ...", read
from the stored checks by an expression 6.2 names and does not state). Everything else is computed here: which rows
are listed, their statuses and details, the pairing by code and stored position, the decisions the update acted on and
how each ends (the four outcomes, 5.4's words), and the answers line. The words come from 6.2 and 5.4 where they give
them, from answers.CHOICE_LABELS and answers.PROMPTS (read from the source with ast: no Django), and where 6.2 gives
contents but no sentence, from step 3c's recorded reading (its Q9: "{label}: {before} → {after}" and "{code} is no
longer suggested. {reason}"), named in NOTES as a question. Where 6.2 gives no words at all (a conflict of a choice, a
selected row of another status, a row needing a detail with no clarification, a fact with no prompt), the part is NOT
JUDGED: ``compute`` lists it under ``unjudged`` and ``compare`` fails on it - an invented sentence would be a false
finding, a skipped one a false pass.

Stdlib only; nothing is sent; nothing is written but stdout.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

ROWS_SCHEMA = 'cpt-studio-what-changed-rows@1'
SCHEMA = 'cpt-studio-what-changed-check@1'
APP_ROOT = Path(__file__).resolve().parents[2]

# studio.types.CONTEXT_FACTS, in its order, and 5.1's labels (the details lines of the update block and of 6.2 step 2)
CONTEXT_FIELDS = ('service_date', 'setting', 'billing_context', 'patient_status')
FIELD_LABELS = {'service_date': 'Date of service', 'setting': 'Place of service', 'patient_status': 'Patient',
                'billing_context': 'Claim'}
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November',
          'December')
NOT_DOCUMENTED = 'not documented'  # 6.2 step 2: "not documented" for none
TWO_DATES = 'two dates to choose from'  # 6.2 step 2: for a conflict (of the date: the one conflict 6.2 words)
DOCUMENTATION_ADDED = 'Documentation added (revision {n})'
READ_AGAIN = 'The document was read again with the current reading.'
# 6.2 step 3: a row's status, read from the row
READY_FOR_REVIEW, NEEDS_A_DETAIL = 'Ready for review', 'Needs a detail'
EXCLUDED_BY_CHECK = 'Excluded by a documentation check'
ANSWERED_AWAY = 'Excluded: a needed detail is not documented'
ALTERNATIVE_REASON = 'Listed as an alternative only; not suggested for approval.'
NOT_SUGGESTED = 'Not suggested: '
ADDED = '{code} is now suggested ({status})'
REMOVED = '{code} is no longer suggested'
REMOVED_WITH_REASON = '{code} is no longer suggested. {reason}'  # step 3c's Q9 (6.2 gives the contents)
STATUS_CHANGED = '{code}: {before} → {after}'
UNITS_CHANGED = '{code}: {before} → {after} units'
DETAIL_CHANGED = '{code}: the detail needed changed: "{before}" → "{after}"'
DETAIL_LINE = '{label}: {before} → {after}'  # step 3c's Q9 (6.2 gives the contents)
# 6.2 step 4: the fixed nouns, and the four outcomes
ACTION_NOUNS = {'approve': 'Approval', 'reject': 'Rejection', 'reinstate': 'Reinstatement',
                'confirm': 'Confirmed exclusion'}
KEPT = '{action} of {code} kept: the code is unchanged.'
KEPT_THEN_CLEARED = ('{action} of {code} was kept by the update, then cleared when the codes were checked again with the '
                     'same details.')
KEPT_THEN_CHANGED = '{action} of {code} was kept by the update, then changed by a reviewer.'
# 5.4's words for a cleared decision, first match wins
CLEARED_BY_REVISION = 'Cleared when documentation was added (revision {n}).'
CLEARED_ACROSS_ENGINES = ('Made on the earlier reading of the document; the current codes come from a new reading, so it '
                          'does not carry. Decide the current codes.')
CLEARED_SAME_DETAILS = 'Cleared when the codes were checked again with the same details: the code it was made on changed.'
CLEARED_DETAILS = 'Cleared when the details changed: the code it was made on changed.'
# 6.2 step 5
ANSWERS_LINE = ('Some answers you gave before this change are not applied to the updated codes; they are listed under '
                'Earlier answers, not applied.')
SELECTED, ALTERNATIVE, EXCLUDED = 'selected', 'alternative', 'excluded'
READY, NEEDS_CLARIFICATION = 'ready', 'needs_clarification'
REVOKE = 'revoke'
EVENTS_FAMILY = 'cpt-studio-events@'  # interpretation.is_new_assessment's family
GEMINI_CONTEXT_FAMILY = 'gemini-context@'  # interpretation.is_new_context's family


class Unusable(ValueError):
    """An input is not what this check reads (exit 2)."""


# --- the words of the product's tables, read from the source (no Django) ------------------------------------------------

def _assignments(path: Path) -> dict[str, ast.expr]:
    """{name: value node} of the module-level assignments of ``path`` (a tuple assignment is split element by element)."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
            if isinstance(target, ast.Name):
                found[target.id] = value
            elif isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple) and len(target.elts) == len(value.elts):
                for name, item in zip(target.elts, value.elts):
                    if isinstance(name, ast.Name):
                        found[name.id] = item
    return found


def _imports(path: Path, package: Path) -> dict[str, Path]:
    """{name: the file it is imported from} for the relative ``from .x.y import name`` statements of ``path``."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out: dict[str, Path] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            source = package.joinpath(*node.module.split('.')).with_suffix('.py')
            for alias in node.names:
                out[alias.asname or alias.name] = source
    return out


def _string(node: ast.expr, local: Mapping[str, ast.expr], imported: Mapping[str, Path]) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in local:
            return _string(local[node.id], {}, {})
        if node.id in imported and imported[node.id].is_file():
            value = _assignments(imported[node.id]).get(node.id)
            return _string(value, {}, {}) if value is not None else None
    return None


def product_words(app_root: Path = APP_ROOT) -> dict[str, Any]:
    """answers.PROMPTS, DEFAULT_PROMPT and CHOICE_LABELS as studio/answers.py states them, read with ast: {'prompts',
    'default_prompt', 'choice_labels', 'unresolved'} - a PROMPTS key that is not a string this reader can resolve is
    listed in 'unresolved' (its fact is then not judged, never worded with the default)."""
    path = app_root / 'studio' / 'answers.py'
    local = _assignments(path)
    imported = _imports(path, app_root / 'studio')
    prompts: dict[str, str] = {}
    unresolved: list[str] = []
    table = local.get('PROMPTS')
    if not isinstance(table, ast.Dict):
        raise Unusable(f'{path} has no PROMPTS table')
    for key, value in zip(table.keys, table.values):
        name = _string(key, local, imported) if key is not None else None
        text = _string(value, local, imported)
        if name is None or text is None:
            unresolved.append(ast.unparse(key) if key is not None else '**')
            continue
        prompts[name] = text
    default = _string(local['DEFAULT_PROMPT'], local, imported) if 'DEFAULT_PROMPT' in local else None
    labels = ast.literal_eval(local['CHOICE_LABELS']) if 'CHOICE_LABELS' in local else None
    if default is None or not isinstance(labels, dict):
        raise Unusable(f'{path} has no DEFAULT_PROMPT or CHOICE_LABELS this reader can read')
    return {'prompts': prompts, 'default_prompt': default, 'choice_labels': labels, 'unresolved': unresolved}


# --- the rows (what_changed_rows, as the operator API serves them) -------------------------------------------------------

def rows_from_operator_view(detail: Any) -> dict[str, Any]:
    """The ``what_changed_rows`` of an operator view (GET /ops/api/encounters/<id>), checked for the shape ROWS_SCHEMA
    names; Unusable when it serves none (the operator API's addition is requested of the integration owner) or another
    shape."""
    rows = detail.get('what_changed_rows') if isinstance(detail, dict) else None
    if rows is None:
        raise Unusable('the operator view serves no what_changed_rows (the rows of AMENDMENT-1 6.2, which the operator '
                       'API must serve for this check: requested of the integration owner)')
    problem = rows_problem(rows)
    if problem:
        raise Unusable(f'the operator view\'s what_changed_rows are not {ROWS_SCHEMA}: {problem}')
    checked: dict[str, Any] = rows
    return checked


def rows_problem(rows: Any) -> str:
    """'' when ``rows`` has ROWS_SCHEMA's shape (every key this check reads, of its type); else what is wrong."""
    def text(value: Any) -> bool:
        return isinstance(value, str)

    def opt(value: Any) -> bool:
        return value is None or isinstance(value, str)
    if not isinstance(rows, dict) or rows.get('schema') != ROWS_SCHEMA:
        return 'no schema of this version'
    if type(rows.get('fresh')) is not bool or not opt(rows.get('current_assessment')) \
            or not opt(rows.get('current_context')):
        return 'fresh, current_assessment or current_context'
    for name in ('assessments', 'contexts', 'revisions'):
        if not isinstance(rows.get(name), dict):
            return f'{name} is not an object'
    for pk, item in rows['assessments'].items():
        if not (isinstance(item, dict) and text(item.get('created_at')) and text(item.get('revision'))
                and opt(item.get('context')) and text(item.get('engine_version'))
                and isinstance(item.get('proposals'), list) and isinstance(item.get('clarifications'), list)):
            return f'assessment {pk}'
        for proposal in item['proposals']:
            if not (isinstance(proposal, dict) and text(proposal.get('id')) and text(proposal.get('code'))
                    and text(proposal.get('bucket')) and text(proposal.get('status')) and text(proposal.get('family'))
                    and type(proposal.get('reinstatable')) is bool and type(proposal.get('units')) is int
                    and type(proposal.get('position')) is int and type(proposal.get('answered_away')) is bool
                    and isinstance(proposal.get('answers'), list) and opt(proposal.get('other_reason'))):
                return f'a proposal of assessment {pk}'
        for item_ in item['clarifications']:
            if not (isinstance(item_, dict) and text(item_.get('id')) and text(item_.get('created_at'))
                    and opt(item_.get('proposal')) and text(item_.get('scope')) and text(item_.get('family'))
                    and text(item_.get('fact')) and opt(item_.get('answer'))):
                return f'a clarification of assessment {pk}'
    for pk, item in rows['contexts'].items():
        if not (isinstance(item, dict) and text(item.get('created_at')) and text(item.get('revision'))
                and text(item.get('version')) and isinstance(item.get('facts'), dict)
                and opt(item.get('earlier_assessment'))):
            return f'context {pk}'
    for pk, item in rows['revisions'].items():
        if not (isinstance(item, dict) and type(item.get('number')) is int):
            return f'revision {pk}'
    for name, keys in (('decisions', ('id', 'assessment', 'proposal', 'code', 'action')),
                       ('invalidations', ('decision',)), ('member_answers', ('id', 'revision', 'answered_at'))):
        items = rows.get(name)
        if not isinstance(items, list) or not all(isinstance(item, dict) and all(text(item.get(key)) for key in keys)
                                                  for item in items):
            return name
    if not all(type(item.get('sequence')) is int and opt(item.get('carried_from')) for item in rows['decisions']):
        return 'decisions (sequence, carried_from)'
    if not all(opt(item.get('by_context')) and opt(item.get('by_revision')) for item in rows['invalidations']):
        return 'invalidations (by_context, by_revision)'
    if not all(type(item.get('standing')) is bool for item in rows['member_answers']):
        return 'member_answers (standing)'
    return ''


def _instant(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


# --- 6.2 ----------------------------------------------------------------------------------------------------------------

def _family(version: str) -> str:
    return version.partition('@')[0] + '@'


def _date_words(value: str) -> Optional[str]:
    try:
        day = dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return f'{day.day} {MONTHS[day.month - 1]} {day.year}'


def value_words(name: str, fact: Any, labels: Mapping[str, Mapping[str, str]]) -> Optional[str]:
    """A context fact in the member's words (6.2 step 2), or None where 6.2 gives none: dates as "10 November 2026",
    choices by answers.CHOICE_LABELS, "not documented" for none, "two dates to choose from" for a conflict of the date."""
    fact = fact if isinstance(fact, dict) else {}
    value, origin = fact.get('value'), fact.get('origin')
    if origin == 'conflict':
        return TWO_DATES if name == 'service_date' else None
    if value is None or value == '':
        return NOT_DOCUMENTED
    if name == 'service_date':
        return _date_words(value) if isinstance(value, str) else None
    return (labels.get(name) or {}).get(value) if isinstance(value, str) else None


class _Rows:
    """The rows, indexed."""

    def __init__(self, rows: Mapping[str, Any]):
        self.rows = rows
        self.assessments: Mapping[str, Any] = rows['assessments']
        self.contexts: Mapping[str, Any] = rows['contexts']
        self.revisions: Mapping[str, Any] = rows['revisions']
        self.decisions = sorted(rows['decisions'], key=lambda item: item['sequence'])
        self.decision = {item['id']: item for item in self.decisions}
        self.invalidation = {item['decision']: item for item in rows['invalidations']}
        self.carries: dict[str, list[Any]] = {}
        for item in self.decisions:
            if item.get('carried_from'):
                self.carries.setdefault(item['carried_from'], []).append(item)

    def number(self, revision: Optional[str]) -> Optional[int]:
        found = self.revisions.get(revision) if revision else None
        return found['number'] if isinstance(found, dict) else None

    def context_of(self, assessment: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        found = assessment.get('context')
        return self.contexts.get(found) if isinstance(found, str) else None

    def current_decisions(self, assessment_id: str) -> set[str]:
        """review.current_decisions as a set of decision ids: per proposal its latest decision on the assessment, unless
        that is a revoke or is invalidated."""
        latest: dict[str, Any] = {}
        for item in self.decisions:
            if item['assessment'] == assessment_id:
                latest[item['proposal']] = item
        return {item['id'] for item in latest.values()
                if item['action'] != REVOKE and item['id'] not in self.invalidation}


def _listed(assessment: Mapping[str, Any]) -> list[Any]:
    return sorted((proposal for proposal in assessment['proposals']
                   if proposal['bucket'] == SELECTED or proposal['answered_away']
                   or (proposal['bucket'] == EXCLUDED and proposal['reinstatable'])),
                  key=lambda proposal: (proposal['position'], proposal['id']))


def _status(proposal: Mapping[str, Any]) -> Optional[str]:
    if proposal['answered_away']:
        return ANSWERED_AWAY
    if proposal['bucket'] == EXCLUDED:
        return EXCLUDED_BY_CHECK
    if proposal['bucket'] == SELECTED and proposal['status'] == READY:
        return READY_FOR_REVIEW
    if proposal['bucket'] == SELECTED and proposal['status'] == NEEDS_CLARIFICATION:
        return NEEDS_A_DETAIL
    return None


def _detail_fact(assessment: Mapping[str, Any], proposal: Mapping[str, Any], families: Mapping[str, str]) -> Optional[str]:
    """6.2 step 3: the fact of the first clarification of the assessment naming the proposal (creation order), else of
    its first service-scoped clarification whose family is the proposal's."""
    ordered = sorted(assessment['clarifications'], key=lambda item: (_instant(item['created_at']), item['id']))
    for item in ordered:
        if item.get('proposal') == proposal['id']:
            return str(item['fact'])
    family = families.get(proposal['id'])
    for item in ordered:
        if item['scope'] == 'service' and family is not None and item['family'] == family:
            return str(item['fact'])
    return None


def compute(rows: Mapping[str, Any], words: Mapping[str, Any]) -> dict[str, Any]:
    """6.2 over ``rows`` (what_changed_rows) with ``words`` (product_words): {'what_changed': the six keys or None,
    'unjudged': [why]}. None unless the encounter is fresh and the current context records an earlier assessment E."""
    index = _Rows(rows)
    unjudged: list[str] = []
    n_id, context_id = rows.get('current_assessment'), rows.get('current_context')
    context = index.contexts.get(context_id) if isinstance(context_id, str) else None
    if (not rows['fresh'] or context is None or not context.get('earlier_assessment') or not isinstance(n_id, str)
            or n_id not in index.assessments):
        return {'what_changed': None, 'unjudged': []}
    e_id = context['earlier_assessment']
    if e_id not in index.assessments:
        return {'what_changed': None, 'unjudged': [f'the earlier assessment {e_id} is not among the rows served']}
    n, e = index.assessments[n_id], index.assessments[e_id]
    e_context, n_context = index.context_of(e), index.context_of(n)
    # 1. compared with
    compared = {'made_at': e['created_at'], 'revision': index.number(e['revision'])}
    # 2. details
    details: list[str] = []
    labels = words['choice_labels']
    for name in CONTEXT_FIELDS:
        before = ((e_context or {}).get('facts') or {}).get(name)
        after = ((n_context or {}).get('facts') or {}).get(name)
        old, new = value_words(name, before, labels), value_words(name, after, labels)
        if old is None or new is None:
            if (before or {}) != (after or {}):
                unjudged.append(f'details: {name} {before!r} -> {after!r} has no words in 6.2')
            continue
        if old != new:
            details.append(DETAIL_LINE.format(label=FIELD_LABELS[name], before=old, after=new))
    if e['revision'] != n['revision']:
        details.append(DOCUMENTATION_ADDED.format(n=index.number(n['revision'])))
    if _family(e['engine_version']) != _family(n['engine_version']):
        details.append(READ_AGAIN)
    # 3. codes
    families = {proposal['id']: proposal.get('family') for item in (e, n) for proposal in item['proposals']}
    codes: list[dict[str, Any]] = []
    unchanged = 0
    by_code: dict[str, tuple[list[Any], list[Any]]] = {}
    for side, item in ((0, e), (1, n)):
        for proposal in _listed(item):
            by_code.setdefault(proposal['code'], ([], []))[side].append(proposal)
    prompts, default = words['prompts'], words['default_prompt']

    def prompt(fact: Optional[str]) -> Optional[str]:
        if fact is None:
            return None
        if fact in prompts:
            return str(prompts[fact])
        return None if words.get('unresolved') else str(default)
    for code in sorted(by_code):
        olds, news = by_code[code]
        for position in range(max(len(olds), len(news))):
            old = olds[position] if position < len(olds) else None
            new = news[position] if position < len(news) else None
            if old is None:
                assert new is not None  # one side of a position always holds a row
                status = _status(new)
                if status is None:
                    unjudged.append(f'codes: {code} (added) has a status 6.2 does not word ({new["bucket"]}/{new["status"]})')
                    continue
                codes.append({'code': code, 'change': 'added', 'text': ADDED.format(code=code, status=status)})
                continue
            if new is None:
                others = sorted((proposal for proposal in n['proposals'] if proposal['code'] == code
                                 and proposal not in news), key=lambda proposal: (proposal['position'], proposal['id']))
                reason = None
                if others:
                    other = others[0]
                    if other['bucket'] == ALTERNATIVE:
                        reason = ALTERNATIVE_REASON
                    elif isinstance(other.get('other_reason'), str) and other['other_reason'].startswith(NOT_SUGGESTED):
                        reason = other['other_reason']
                    else:
                        unjudged.append(f'codes: {code} (removed) has a stored proposal on N whose reason is not '
                                        f'served ({other.get("other_reason")!r})')
                        continue
                codes.append({'code': code, 'change': 'removed',
                              'text': (REMOVED_WITH_REASON.format(code=code, reason=reason) if reason
                                       else REMOVED.format(code=code))})
                continue
            before, after = _status(old), _status(new)
            if before is None or after is None:
                unjudged.append(f'codes: {code} has a status 6.2 does not word')
                continue
            # refutation 6b-r1 P6: 6.2 step 3 lists the paired cases without saying whether a pair that changed in two
            # ways (its status and its units, or its units and its detail) is listed once or once for each change, so
            # such a pair is not judged - the check fails on it, never passes a page that drops one change nor fails a
            # page that lists both (6b-3 question Q11)
            changed = ([*(['status'] if before != after else []), *(['units'] if old['units'] != new['units'] else []),
                        *(['detail'] if before == after == NEEDS_A_DETAIL
                          and _detail_fact(e, old, families) != _detail_fact(n, new, families) else [])])
            if len(changed) > 1:
                unjudged.append(f'codes: {code} changed in more than one way ({", ".join(changed)}): 6.2 step 3 does '
                                'not say whether such a pair is listed once or once for each change')
            elif changed == ['status']:
                codes.append({'code': code, 'change': 'status',
                              'text': STATUS_CHANGED.format(code=code, before=before, after=after)})
            elif changed == ['units']:
                codes.append({'code': code, 'change': 'units',
                              'text': UNITS_CHANGED.format(code=code, before=old['units'], after=new['units'])})
            elif changed == ['detail']:
                was, now = prompt(_detail_fact(e, old, families)), prompt(_detail_fact(n, new, families))
                if was is None or now is None:
                    unjudged.append(f'codes: {code}\'s detail needed changed, and one side has no prompt')
                    continue
                codes.append({'code': code, 'change': 'detail',
                              'text': DETAIL_CHANGED.format(code=code, before=was, after=now)})
            else:
                unchanged += 1
    # 4. decisions
    decisions = []
    created = _instant(context['created_at'])
    numbers = (index.number(e['revision']), index.number(n['revision']))
    case_c = e['revision'] != n['revision']
    of_context = {pk for pk, item in index.assessments.items() if item.get('context') == context_id}
    current = index.current_decisions(n_id)
    for item in index.decisions:
        holder = index.assessments.get(item['assessment'])
        if holder is None or _instant(holder['created_at']) >= created:
            continue
        cleared = index.invalidation.get(item['id'])
        carried = any(carry['assessment'] in of_context for carry in index.carries.get(item['id'], ()))
        by_context = cleared is not None and cleared.get('by_context') == context_id
        by_revision = (case_c and cleared is not None and cleared.get('by_revision') is not None
                       and numbers[0] is not None and numbers[1] is not None
                       and numbers[0] < (index.number(cleared['by_revision']) or -1) <= numbers[1])
        if not (carried or by_context or by_revision):
            continue
        noun = ACTION_NOUNS.get(item['action'])
        if noun is None:
            unjudged.append(f'decisions: {item["code"]} ({item["action"]}) has no noun in 6.2')
            continue
        if cleared is not None:
            decisions.append(_cleared(index, item, cleared, noun))
            continue
        last, steps = item, 0
        while index.carries.get(last['id']) and steps <= len(index.decisions):  # bounded: the rows are never a cycle
            last = max(index.carries[last['id']], key=lambda carry: carry['sequence'])
            steps += 1
        if last['id'] in current:
            outcome, text = 'kept', KEPT
        elif last['id'] in index.invalidation:
            outcome, text = 'kept_then_cleared', KEPT_THEN_CLEARED
        else:
            outcome, text = 'kept_then_changed', KEPT_THEN_CHANGED
        decisions.append({'code': item['code'], 'action': item['action'], 'outcome': outcome,
                          'text': text.format(action=noun, code=item['code']), 'sequence': item['sequence']})
    decisions.sort(key=lambda entry: (entry['code'], entry['sequence']))
    for entry in decisions:
        entry.pop('sequence')
    # 5. answers
    answers = None
    if e['revision'] == n['revision']:
        read = {item['answer'] for item in n['clarifications'] if item.get('answer')}
        read |= {answer for proposal in n['proposals'] for answer in proposal['answers']}
        for answer in rows['member_answers']:
            if (answer['standing'] and answer['revision'] == n['revision']
                    and _instant(answer['answered_at']) < created and answer['id'] not in read):
                answers = ANSWERS_LINE
                break
    return {'what_changed': {'compared_with': compared, 'details': details, 'codes': codes, 'unchanged': unchanged,
                             'decisions': decisions, 'answers': answers},
            'unjudged': unjudged}


def _cleared(index: _Rows, item: Mapping[str, Any], cleared: Mapping[str, Any], noun: str) -> dict[str, Any]:
    """5.4's words for a cleared decision, first match wins."""
    holder = index.assessments[item['assessment']]
    found = cleared.get('by_context')
    by_context = index.contexts.get(found) if isinstance(found, str) else None
    if cleared.get('by_revision'):
        text = CLEARED_BY_REVISION.format(n=index.number(cleared['by_revision']))
    elif (not holder['engine_version'].startswith(EVENTS_FAMILY) and by_context is not None
          and by_context['version'].startswith(GEMINI_CONTEXT_FAMILY)):
        text = CLEARED_ACROSS_ENGINES
    elif cleared.get('by_context') and cleared.get('by_context') == holder.get('context'):
        text = CLEARED_SAME_DETAILS
    else:
        text = CLEARED_DETAILS
    return {'code': item['code'], 'action': item['action'], 'outcome': 'cleared', 'text': text,
            'sequence': item['sequence']}


# --- the comparison -----------------------------------------------------------------------------------------------------

def _action(value: Any) -> Any:
    """A decision's action as the page may serve it (the raw action or 6.2's noun), read as the raw action."""
    nouns = {noun: action for action, noun in ACTION_NOUNS.items()}
    return nouns.get(value, value)


def _differences(name: str, left: Sequence[tuple[Any, ...]], right: Sequence[tuple[Any, ...]]) -> list[str]:
    """Each position where the page's list ``left`` and the independent list ``right`` differ, named."""
    found = []
    for position in range(max(len(left), len(right))):
        ours = right[position] if position < len(right) else None
        theirs = left[position] if position < len(left) else None
        if theirs != ours:
            found.append(f'{name}[{position}]: the page {theirs}, the independent check {ours}')
    if len(left) == len(right) and not found:
        found.append(f'{name}: the page serves an entry that is not an object')
    return found


def compare(page: Any, mine: Mapping[str, Any]) -> list[str]:
    """Every difference between the page's ``what_changed`` and ``compute``'s result ``mine``, field by field ([] when
    they agree and nothing was left unjudged). The details may be listed in another order (6.2 orders only the parts),
    so they are compared as a multiset; the codes and decisions are "by code", compared in order."""
    found = [f'not judged: {why}' for why in mine.get('unjudged') or ()]
    ours = mine.get('what_changed')
    if page is None or ours is None:
        if (page is None) != (ours is None):
            found.append(f'what_changed: the page serves {"none" if page is None else "one"}, the independent check '
                         f'{"none" if ours is None else "one"}')
        return found
    if not isinstance(page, dict):
        return found + [f'what_changed: the page serves {type(page).__name__}, not an object']
    extra = sorted(set(page) - set(ours))
    if extra:
        found.append(f'what_changed: the page serves keys 6.2 does not have: {extra}')
    theirs: dict[str, Any] = page['compared_with'] if isinstance(page.get('compared_with'), dict) else {}
    try:
        same_time = _instant(str(theirs.get('made_at'))) == _instant(ours['compared_with']['made_at'])
    except (TypeError, ValueError):
        same_time = False
    if not same_time or theirs.get('revision') != ours['compared_with']['revision']:
        found.append(f'compared_with: the page {theirs}, the independent check {ours["compared_with"]}')
    details = page.get('details') if isinstance(page.get('details'), list) else None
    if details is None or sorted(map(str, details)) != sorted(ours['details']):
        found.append(f'details: the page {details}, the independent check {ours["details"]}')
    page_codes = [(item.get('code'), item.get('change'), item.get('text')) for item in page.get('codes') or ()
                  if isinstance(item, dict)]
    our_codes = [(item['code'], item['change'], item['text']) for item in ours['codes']]
    if page_codes != our_codes or len(page_codes) != len(page.get('codes') or ()):
        found += _differences('codes', page_codes, our_codes)
    if page.get('unchanged') != ours['unchanged']:
        found.append(f'unchanged: the page {page.get("unchanged")!r}, the independent check {ours["unchanged"]}')
    page_decisions = [(item.get('code'), _action(item.get('action')), item.get('outcome'), item.get('text'))
                      for item in page.get('decisions') or () if isinstance(item, dict)]
    our_decisions = [(item['code'], item['action'], item['outcome'], item['text']) for item in ours['decisions']]
    if page_decisions != our_decisions or len(page_decisions) != len(page.get('decisions') or ()):
        found += _differences('decisions', page_decisions, our_decisions)
    if page.get('answers') != ours['answers']:
        found.append(f'answers: the page {page.get("answers")!r}, the independent check {ours["answers"]!r}')
    return found


# --- the command --------------------------------------------------------------------------------------------------------

def check(operator_view: Any, customer_view: Any, words: Mapping[str, Any]) -> dict[str, Any]:
    """The check of one encounter: {'schema', 'encounter', 'result', 'differences', 'independent'}."""
    rows = rows_from_operator_view(operator_view)
    if not isinstance(customer_view, dict) or 'what_changed' not in customer_view:
        raise Unusable('the customer view serves no what_changed')
    mine = compute(rows, words)
    differences = compare(customer_view['what_changed'], mine)
    return {'schema': SCHEMA, 'encounter': operator_view.get('id'), 'result': 'pass' if not differences else 'fail',
            'differences': differences, 'independent': mine}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--operator', required=True, help='GET /ops/api/encounters/<id> as an operator read it (JSON)')
    parser.add_argument('--customer', required=True, help='GET /api/encounters/<id> as a member read it (JSON)')
    parser.add_argument('--app-root', default=str(APP_ROOT), help='the cpt-studio/ directory whose answers.py words it')
    args = parser.parse_args(argv)
    try:
        operator_view = json.loads(Path(args.operator).read_text(encoding='utf-8'))
        customer_view = json.loads(Path(args.customer).read_text(encoding='utf-8'))
        result = check(operator_view, customer_view, product_words(Path(args.app_root)))
    except (OSError, ValueError) as error:  # Unusable is a ValueError, as a JSON error is
        print(json.dumps({'schema': SCHEMA, 'result': 'unusable', 'error': str(error)}))
        return 2
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
