#!/usr/bin/env python3
"""Mutation proofs for the repair round. For each mutant: every anchor must occur exactly once, the mutated file is
read back and must differ from the original by sha256, the suite runs under a deadline, and the original bytes are
restored in `finally` and asserted by sha256. The UNMUTATED suites run first and must pass (a failing baseline makes
every kill vacuous)."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REB = Path('/opt/meddoc-pro/.worktrees/v1-sonnet5-campaign/rebuild')
PY = REB / '.venv/bin/python'
DJ = '/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/r2fix/run-django-tests.sh'
FILES = {'pc': REB / 'ops/provider_campaign.py', 'sq': REB / 'ops/sonnet5_qa.py'}
PLAIN = ['ops.tests.test_provider_campaign']
DJANGO = ['ops.tests.test_sonnet5_qa']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(kind, timeout):
    if kind == 'plain':
        cmd, env = [str(PY), '-B', '-m', 'unittest', *PLAIN], {**os.environ, 'TMPDIR': '/tmp'}
    else:
        cmd, env = ['bash', DJ, *DJANGO], {**os.environ, 'TEST_DB_NAME': 'quillmd_qa_repair_mut'}
    started = time.time()
    try:
        done = subprocess.run(cmd, cwd=REB, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', [], time.time() - started
    lines = (done.stdout + done.stderr).splitlines()
    tail = [line for line in lines if line.startswith(('Ran ', 'OK', 'FAILED'))]
    failing = sorted({line.split(' (')[0] for line in lines if line.startswith(('FAIL: ', 'ERROR: '))})
    return done.returncode, tail + failing[:4], time.time() - started


M = []


def mutant(ident, file, kind, why, *edits):
    M.append({'id': ident, 'file': file, 'kind': kind, 'why': why, 'edits': edits})


# ── item 1: the leak scan fails closed ──────────────────────────────────────────────────────────────────────────────
mutant('P01', 'pc', 'plain', 'os.walk skips an unlistable directory (no onerror)',
       ('os.walk(root, onerror=cannot_list, followlinks=False)', 'os.walk(root, followlinks=False)'))
mutant('P02', 'pc', 'plain', 'an unreadable file is read as clean',
       ("""        raise Unscannable(f'The leak scan cannot read {relative} ({type(error).__name__}); an unscannable file is a '
                          'stop, never "no leak".') from None""", '        return False'))
mutant('P03', 'pc', 'plain', 'a link or special file entry is not refused at lstat',
       ('            if not stat.S_ISREG(mode):', '            if False:'))
mutant('P04', 'pc', 'plain', 'a linked directory is not refused',
       ('            if not stat.S_ISDIR(entry(Path(directory) / name)):', '            if entry(Path(directory) / name) is None:'))
mutant('P05', 'pc', 'plain', 'an environment-named entry is opened like any file',
       ('        if env_name(path.name):', '        if False:'))
mutant('P06', 'pc', 'plain', 'a linked root is followed',
       ('    if not stat.S_ISDIR(root_mode) or env_name(root.name):', '    if False:'))
mutant('P07', 'pc', 'plain', 'the opened file is not re-checked as regular (TOCTOU layer behind P03)',
       ('        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):', '        if False:'))
# ── item 2: the credential's links ──────────────────────────────────────────────────────────────────────────────────
mutant('P08', 'pc', 'plain', 'a hard-linked credential is read',
       ("        require(info.st_nlink == 1, 'The credential file has another name (a hard link); it is not read.')",
        "        require(True, 'The credential file has another name (a hard link); it is not read.')"))
mutant('P09', 'pc', 'plain', 'a symbolic link in a directory component is followed',
       ('inner = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)',
        'inner = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=directory)'))
mutant('P10', 'pc', 'plain', 'a parent-directory component is accepted',
       ("    require('..' not in parts, 'The credential path must not name a parent directory (..).')",
        "    require(True, 'The credential path must not name a parent directory (..).')"))
# ── item 3: environment names ───────────────────────────────────────────────────────────────────────────────────────
mutant('P11', 'pc', 'plain', '.env.* and *.env.* are not environment files',
       ("    return lowered.endswith('.env') or '.env.' in lowered", "    return lowered.endswith('.env')"))
mutant('P12', 'pc', 'plain', 'environment names are matched case-sensitively',
       ('    lowered = str(name).lower()', '    lowered = str(name)'))
# ── item 7: unreported token counts ─────────────────────────────────────────────────────────────────────────────────
mutant('P13', 'pc', 'plain', 'a completed outcome without token counts is priced as zero tokens',
       ("inputs, outputs = _count(usage, 'input_tokens', reported=True), _count(usage, 'output_tokens', reported=True)",
        "inputs, outputs = _count(usage, 'input_tokens'), _count(usage, 'output_tokens')"))
mutant('P14', 'pc', 'plain', 'totals do not count an unpriceable completed outcome as unknown',
       ('                               or known_cost(a, o) is None)}', '                               )}'))
# ── item 8: pinned limits ───────────────────────────────────────────────────────────────────────────────────────────
mutant('P15', 'pc', 'plain', 'the recorded limits are ignored (current declaration only)',
       ('                limits = limits.tightest(pinned)', '                limits = limits'))
mutant('P16', 'pc', 'plain', "the current declaration's stage limit wins",
       ('min(mine.limit, other_stage.limit)', 'mine.limit'))
mutant('P17', 'pc', 'plain', "the current declaration's total wins",
       ('return Limits(min(self.total, other.total), tuple(stages))', 'return Limits(self.total, tuple(stages))'))
mutant('P18', 'pc', 'plain', "the current declaration's request count wins",
       ('min(counts) if counts else None', 'mine.max_requests'))
mutant('P19', 'pc', 'plain', 'a prerequisite dropped by an edit is dropped',
       ('tuple(sorted(set(mine.requires) | set(other_stage.requires)))', 'tuple(sorted(set(mine.requires)))'))
mutant('P20', 'pc', 'plain', 'a stage added by an edit gets a limit',
       ("""            if mine.id not in theirs:
                continue""", """            if mine.id not in theirs:
                stages.append(mine)
                continue"""))
mutant('P21', 'pc', 'plain', 'an attempt naming neither limits nor declaration falls back to the current declaration',
       ("""        require(isinstance(sha256, str) and re.fullmatch(r'[0-9a-f]{64}', sha256),
                f'Attempt {number} records neither its limits nor its declaration; the limits in force cannot be established.')""",
        """        if not (isinstance(sha256, str) and re.fullmatch(r'[0-9a-f]{64}', sha256)):
            return self.declaration.limits()"""))
mutant('P22', 'pc', 'plain', "a historic declaration is read without checking its recorded sha256",
       ('    require(blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == sha256, unknown)',
        '    require(blob.returncode == 0, unknown)'))
mutant('P23', 'pc', 'plain', 'recorded limits are not validated',
       ("            require(condition, f'{what} records limits that cannot be read; the limits in force cannot be established.')",
        "            require(True, f'{what} records limits that cannot be read; the limits in force cannot be established.')"))
mutant('P24', 'pc', 'plain', 'a negative recorded limit is accepted',
       ('        valid(total >= 0 and all(s.limit >= 0 and (s.max_requests is None or s.max_requests >= 0) for s in stages))',
        '        valid(True)'))
# ── item 9: the case verdict ────────────────────────────────────────────────────────────────────────────────────────
mutant('P25', 'pc', 'plain', 'a contract failure is not a verdict of its own',
       ("    verdict = 'unsafe' if unsafe else ('contract' if contract else 'usefulness')",
        "    verdict = 'unsafe' if unsafe else 'usefulness'"))
mutant('P26', 'pc', 'plain', 'an unknown finding is ignored',
       ('        require(isinstance(code, str) and code in UNSAFE_FINDINGS | CONTRACT_FINDINGS,', '        require(True,'))
mutant('P27', 'pc', 'plain', 'an unknown field outcome is accepted',
       ('        require(isinstance(outcome, str) and outcome in FIELD_OUTCOMES,', '        require(True,'))
mutant('P28', 'pc', 'plain', 'only unsafe findings stop the stage',
       ("'stops_stage': verdict != 'usefulness'", "'stops_stage': verdict == 'unsafe'"))
# ── item 10: numbered decisions and reopening ───────────────────────────────────────────────────────────────────────
mutant('P29', 'pc', 'plain', 'a second failure without a reopening is accepted',
       ('                and reopenings in (failures, failures - 1) and len(passed) <= 1', '                and len(passed) <= 1'))
mutant('P30', 'pc', 'plain', 'a pass after an open failure is accepted',
       ('                and (not passed or reopenings == failures),', '                and True,'))
mutant('P31', 'pc', 'plain', "a decision record's stage and decision are not checked",
       ("            require(isinstance(record, dict) and record.get('stage') == stage and record.get('decision') == kind,",
        '            require(isinstance(record, dict),'))
mutant('P32', 'pc', 'plain', "a reopening's ledger count is not validated",
       ('            require(type(open_since) is int and open_since >= 0,', '            require(True,'))
mutant('P33', 'pc', 'plain', 'a stage decision is written over an open failure',
       ("        require(state['state'] == 'open', f'Stage {stage} already has a decision.')",
        "        require(state['state'] != 'passed', f'Stage {stage} already has a decision.')"))
mutant('P34', 'pc', 'plain', "a reopening is written under another failure's number",
       ("        require(state['state'] == 'failed' and state['failures'] == number,", "        require(state['state'] == 'failed',"))
mutant('P35', 'pc', 'plain', 'a failed stage is admitted',
       ("        require(state['state'] != 'failed', f'Stage {stage.id} failed;", "        require(True, f'Stage {stage.id} failed;"))
mutant('P36', 'pc', 'plain', 'a reopened stage admits any runner',
       ("""        require(self.declaration.repository and isinstance(runner_commit, str)
                and is_ancestor(self.declaration.repository, reopening['repair_commit'], runner_commit),""",
        """        require(True,"""))
mutant('P37', 'pc', 'plain', 'a stopped campaign can reopen a stage',
       ("        require(ledger.campaign_stop() is None, 'The campaign is stopped; no stage is reopened under a stop.')",
        "        require(True, 'The campaign is stopped; no stage is reopened under a stop.')"))
mutant('P38', 'pc', 'plain', 'a stage that has not failed can be reopened',
       ("        require(state['state'] == 'failed', f'Stage {stage.id} has not failed; only a failed stage is reopened.')",
        "        require(state['state'] != 'passed', f'Stage {stage.id} has not failed; only a failed stage is reopened.')"))
mutant('P39', 'pc', 'plain', 'a failure with no attempt of its own can be reopened',
       ("        require(this_failure, f'Stage {stage.id} failed with no attempt of its own; there is nothing to diagnose.')",
        "        require(True, f'Stage {stage.id} failed with no attempt of its own; there is nothing to diagnose.')"))
mutant('P40', 'pc', 'plain', 'a declaration with no checkout can verify a diagnosis',
       ("        require(declaration.repository, 'The declaration names no checkout; a diagnosis cannot be verified.')",
        "        require(True, 'The declaration names no checkout; a diagnosis cannot be verified.')"))
mutant('P41', 'pc', 'plain', 'a missing diagnosis is not refused cleanly',
       ("        require(diagnosis is not None, 'A reopening needs --diagnosis <path>.')",
        "        require(True, 'A reopening needs --diagnosis <path>.')"))
mutant('P42', 'pc', 'plain', 'a diagnosis outside the checkout is accepted',
       ("        require(path.is_relative_to(root) and path != root, 'The diagnosis must be a file in this checkout.')",
        "        require(True, 'The diagnosis must be a file in this checkout.')"))
mutant('P43', 'pc', 'plain', 'an untracked or edited diagnosis is accepted',
       ("        data, commit, commit_time, relative = committed_file(path, root, 'diagnosis')",
        "        data, commit, commit_time, relative = path.read_bytes(), '0' * 40, 'unknown', str(path.relative_to(root))"))
mutant('P44', 'pc', 'plain', "a diagnosis of another stage is accepted",
       ("        require(named_stage == stage.id, f'The diagnosis names reopen_stage {named_stage}, not {stage.id}.')",
        "        require(True, f'The diagnosis names reopen_stage {named_stage}, not {stage.id}.')"))
mutant('P45', 'pc', 'plain', 'a diagnosis naming other attempts is accepted',
       ('        require(len(named) == len(set(named)) and sorted(named) == this_failure,', '        require(True,'))
mutant('P46', 'pc', 'plain', 'a runner commit that is not a full id is accepted',
       ("""        require(isinstance(runner_commit, str) and FULL_COMMIT.fullmatch(runner_commit),
                'The runner commit is not a full commit id.')""", """        require(True,
                'The runner commit is not a full commit id.')"""))
mutant('P47', 'pc', 'plain', 'a failed attempt without a runner commit is accepted',
       ('            require(FULL_COMMIT.fullmatch(failed_runner),', '            require(True,'))
mutant('P48', 'pc', 'plain', 'the failed runner itself is accepted as the repaired runner',
       ("        require(runner_commit not in failed_runners, 'The runner is the commit that failed; a repair is a new commit.')",
        "        require(True, 'The runner is the commit that failed; a repair is a new commit.')"))
mutant('P49', 'pc', 'plain', 'an unknown repair commit is not named as such',
       ("        require(commit_exists(root, repair), f'The repair commit {repair} is not a commit in this checkout.')",
        "        require(True, f'The repair commit {repair} is not a commit in this checkout.')"))
mutant('P50', 'pc', 'plain', 'an unknown runner commit is not named as such',
       ("        require(commit_exists(root, runner_commit), f'The runner commit {runner_commit} is not a commit in this checkout.')",
        "        require(True, f'The runner commit {runner_commit} is not a commit in this checkout.')"))
mutant('P51', 'pc', 'plain', 'a runner without the repair is accepted',
       ("        require(is_ancestor(root, repair, runner_commit), f'The runner {runner_commit} does not contain the repair {repair}.')",
        "        require(True, f'The runner {runner_commit} does not contain the repair {repair}.')"))
mutant('P52', 'pc', 'plain', 'a repair already in the failed runner is accepted',
       ('            require(not is_ancestor(root, repair, failed_runner),', '            require(True,'))
mutant('P53', 'pc', 'plain', "a stage with no money left under its own limit is reopened",
       ("        require(spent < in_force.limit, f'Stage", "        require(True, f'Stage"))
mutant('P54', 'pc', 'plain', 'a stage with no request left is reopened',
       ('            require(len(here) < in_force.max_requests,', '            require(True,'))
mutant('P55', 'pc', 'plain', "attempts decided before a reopening are read as undecided",
       ("                       if attempt['stage'] == stage and attempt['number'] > state['open_since']]",
        "                       if attempt['stage'] == stage]"))
mutant('P56', 'pc', 'plain', "a reopening's failure is read as every attempt of the stage",
       ("        this_failure = [a['number'] for a, _ in here if a['number'] > state['open_since']]",
        "        this_failure = [a['number'] for a, _ in here]"))
# ── sonnet5_qa: items 4, 5, 6, 1 (decision), 8 (record), 10 (settle) ───────────────────────────────────────────────
mutant('S01', 'sq', 'plain', 'inner() starts without QUILLMD_ENV_MANAGED=1',
       ("    require(os.environ.get('QUILLMD_ENV_MANAGED') == '1',", '    require(True,'))
mutant('S02', 'sq', 'plain', 'inner() starts beside rebuild/.env',
       ("    require(not env_file_present(), 'The candidate checkout has a rebuild/.env; the request process never starts beside one.')",
        "    require(True, 'The candidate checkout has a rebuild/.env; the request process never starts beside one.')"))
mutant('S03', 'sq', 'plain', "evidence outside its own question's line is accepted",
       ("            if line is not None and not (line[0] <= item['start'] and item['end'] <= line[1]):", '            if False:'))
mutant('S04', 'sq', 'plain', 'evidence that does not contain the adopted answer is accepted',
       ("            if not (isinstance(text, str) and text and text in item['quote']):", '            if False:'))
mutant('S05', 'sq', 'plain', 'the review reader reads every form on the page',
       ("            self.inside = attrs.get('action') == self.action", '            self.inside = True'))
mutant('S06', 'sq', 'plain', 'an <input> of an answer name is not read',
       ("        elif self.inside and tag == 'input' and attrs.get('name'):", '        elif False:'))
mutant('S07', 'sq', 'plain', 'a second input carrying the draft is accepted',
       ("        if found != [expected[field['label']]]:", "        if expected[field['label']] not in found:"))
mutant('S08', 'sq', 'plain', "an answer cell's text is its direct paragraphs only (the old reading)",
       (r"""    parts, paragraphs = [], 0
    for node in cell.iter():
        if node.tag == f'{{{W}}}p':
            if paragraphs:
                parts.append('\n')
            paragraphs += 1
        elif node.tag == f'{{{W}}}t':
            parts.append(node.text or '')
    return ''.join(parts)""", r"""    return '\n'.join(''.join(node.text or '' for node in paragraph.iter(f'{{{W}}}t'))
                     for paragraph in cell.findall(f'{{{W}}}p'))"""))
mutant('S09', 'sq', 'plain', 'hidden text in an answer cell is accepted',
       ('        if any(True for _ in answer_after.iter(*HIDDEN)):', '        if False:'))
mutant('S10', 'sq', 'plain', 'a nested table in an answer cell is accepted',
       ("        if answer_after.find(f'.//{{{W}}}tbl') is not None:", '        if False:'))
mutant('S11', 'sq', 'plain', 'settle ignores an attempt left open after a reopening',
       ('    for stage, numbers in sorted(ledger.undecided(rows).items()):',
        "    for stage, numbers in sorted({s: n for s, n in ledger.undecided(rows).items() if not ledger.stage_state(s)['reopenings']}.items()):"))
mutant('S12', 'sq', 'plain', 'status refuses when a stage has no limit in force',
       ('        in_force = {s.id: s for s in limits.stages}.get(stage.id)       # (None: no limit in force — never admitted)',
        '        in_force = limits.stage(stage.id)'))
mutant('S13', 'sq', 'django', 'the review check looks for the values anywhere on the page (the old, vacuous check)',
       ("""    if page.status_code != 200:
        reasons.append(f'the review page did not show the draft ({page.status_code})')
    else:
        reasons += review_form_problems(page.content.decode(), encounter.pk, fields, EXPECTED)""",
        """    if page.status_code != 200 or not all(EXPECTED[label].encode() in page.content for label in FORM_LABELS):
        reasons.append(f'the review page did not show the draft ({page.status_code})')"""))
mutant('S14', 'sq', 'django', 'an unreadable evidence file escapes the decision as a runner failure (no stop)',
       ("""    except OSError as error:
        unscannable = f'the evidence could not be read for its manifest ({type(error).__name__})'""",
        """    except ZeroDivisionError as error:
        unscannable = f'the evidence could not be read for its manifest ({type(error).__name__})'"""))
mutant('S15', 'sq', 'django', 'an unscannable tree is not a campaign stop',
       ("        ledger.write_stop({'reason': 'the retained evidence could not be scanned for the credential', 'detail': unscannable})",
        '        pass'))
mutant('S16', 'sq', 'django', 'an unscannable tree after the decision is not caught as a stop',
       ("""    try:
        late, late_unscannable = pc.leaked(root, secret, exclude=(declaration.credential_file,)), None
    except pc.Refused as refused:
        late, late_unscannable = [], str(refused)""",
        """    late, late_unscannable = pc.leaked(root, secret, exclude=(declaration.credential_file,)), None"""))
mutant('S17', 'sq', 'django', 'the attempt does not record the limits in force',
       ("               'limits': limits, 'runner_commit': runner_commit,", "               'runner_commit': runner_commit,"))
mutant('S18', 'sq', 'django', 'an interrupted run no longer fails an open stage',
       ("        if state == 'open':", "        if state == 'never':"))


def main(only=None):
    original = {key: path.read_bytes() for key, path in FILES.items()}
    digest = {key: sha(data) for key, data in original.items()}
    kinds = sorted({m['kind'] for m in M if only is None or m['kind'] == only})
    report = {'digests': digest, 'baseline': {}, 'mutants': []}
    for kind in kinds:
        code, tail, seconds = run(kind, 600)
        report['baseline'][kind] = {'code': code, 'tail': tail, 'seconds': round(seconds, 1)}
        print(f'BASELINE {kind}: exit {code} {tail}', flush=True)
        if code != 0:
            print('BASELINE FAILED: no mutant is run', flush=True)
            return report
    for m in M:
        if only is not None and m['kind'] != only:
            continue
        path = FILES[m['file']]
        text = original[m['file']].decode()
        row = {'id': m['id'], 'kind': m['kind'], 'why': m['why']}
        try:
            counts = [text.count(anchor) for anchor, _ in m['edits']]
            if counts != [1] * len(m['edits']):
                row.update(result='ANCHOR-MISS', counts=counts)
                continue
            for anchor, replacement in m['edits']:
                text = text.replace(anchor, replacement)
            path.write_bytes(text.encode())
            written = path.read_bytes()
            applied = written == text.encode() and sha(written) != digest[m['file']]
            row['applied'] = applied
            if not applied:
                row['result'] = 'NOT-APPLIED'
                continue
            code, tail, seconds = run(m['kind'], 600)
            row.update(code=code, tail=tail, seconds=round(seconds, 1),
                       result='TIMEOUT' if code == 'TIMEOUT' else ('KILLED' if code != 0 else 'SURVIVED'))
        finally:
            path.write_bytes(original[m['file']])
            row['restored'] = sha(path.read_bytes()) == digest[m['file']]
            assert row['restored'], f'{m["id"]}: {path} was NOT restored'
            report['mutants'].append(row)
            print(f"{row['id']} {row.get('result')} applied={row.get('applied')} restored={row['restored']} "
                  f"{row.get('seconds', '')}s :: {row['why']} :: {row.get('tail', row.get('counts'))}", flush=True)
    for key, path in FILES.items():
        assert sha(path.read_bytes()) == digest[key], f'{path} differs from its pre-run bytes'
    report['final_digests_match'] = True
    return report


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ids = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
    if ids:
        M[:] = [m for m in M if m['id'] in ids]
        assert {m['id'] for m in M} == ids, 'an id named on the command line is not a mutant'
    result = main(only)
    out = Path(__file__).with_name(f'mutation-{only or "all"}{"-" + "-".join(sorted(ids)) if ids else ""}.json')
    out.write_text(json.dumps(result, indent=1, default=str))
    print('written', out)
