#!/usr/bin/env python3
"""Analyze cross-input-mode audit results.

Reads /tmp/cross-input-mode-results.json (produced by runner.ts --run).
For each scenario, compares the (text_notes, voice_dictation,
audio_upload) outputs on:
  - ICD-10 codes emitted (Jaccard overlap pairwise + 3-way intersection)
  - CPT codes (E&M + procedures)
  - Rx drug-name overlap
  - Per-scenario expected safety-rule fires (regex-based)

Output:
  - /tmp/cross-input-mode-parity.json : structured parity matrix
  - stdout : human-readable summary

Hard pass criterion (per the brief): ICD overlap >=80% AND identical
safety-rule fires. Scenarios that fail one or both bubble to the
TOP of the report.
"""
import json
import re
import sys
from pathlib import Path

RESULTS = Path('/tmp/cross-input-mode-results.json')
PARITY_OUT = Path('/tmp/cross-input-mode-parity.json')
SCENARIOS_TS = Path('/opt/meddoc-pro/apps/transcribe-md/scripts/cross-input-mode/scenarios.ts')
# Ground-truth manifest of every scenario's safety-rule labels, written
# by `runner.ts --emit-rule-labels`. The analyzer's regex parser of
# scenarios.ts is best-effort and could silently drop or mis-extract a
# rule if a future regex literal contains characters like `]`, `}`, or
# unescaped `/`. The round-trip parity check below catches that drift.
RULE_LABELS_MANIFEST = Path('/tmp/cross-input-mode-rule-labels.json')

MODES = ['text_notes', 'voice_dictation', 'audio_upload']


def extract_icd(visit):
    icd = visit.get('icdCodes') or {}
    if not isinstance(icd, dict):
        return []
    codes = icd.get('codes') or []
    return [c.get('code') for c in codes if isinstance(c, dict) and c.get('code')]


def extract_cpt_em(visit):
    cpt = visit.get('cptCodes') or {}
    if not isinstance(cpt, dict):
        return None
    em = cpt.get('em') or {}
    if isinstance(em, dict):
        return em.get('code')
    return None


def extract_cpt_procs(visit):
    cpt = visit.get('cptCodes') or {}
    if not isinstance(cpt, dict):
        return []
    procs = cpt.get('procedures') or []
    return [p.get('code') for p in procs if isinstance(p, dict) and p.get('code')]


def extract_rx_drugs(visit):
    rx = visit.get('rxDrafts') or {}
    if not isinstance(rx, dict):
        return []
    rxs = rx.get('prescriptions') or []
    return [(r.get('drug') or '').strip().lower() for r in rxs if isinstance(r, dict) and r.get('drug')]


def extract_rx_warning_text(visit):
    rx = visit.get('rxDrafts') or {}
    if not isinstance(rx, dict):
        return ''
    warns = rx.get('warnings') or []
    return '\n'.join((w.get('message') or '') for w in warns if isinstance(w, dict))


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def parse_scenarios_ts():
    """Pull the expected-safety-rule regexes out of the TS file.

    Cheap heuristic regex extraction — we only need `tag` +
    `rxSafetyRules: [{ pattern: /.../ , required: true|false, label: '...' }]`.
    The TS file is module-local so importing it from Python is impossible;
    parsing is the path of least resistance for a one-shot harness.
    """
    text = SCENARIOS_TS.read_text()
    # Split on `tag: '...'` blocks at the top of each scenario.
    scenarios = {}
    # Simple state machine — find each `tag: 'XX',` and the matching
    # `rxSafetyRules: [...]` if present in the same scenario block.
    blocks = re.split(r"\s*\{\s*tag:\s*'([A-Z0-9]+)',", text)
    # blocks[0] is the preamble; then alternates [tag, body, tag, body, ...]
    for i in range(1, len(blocks), 2):
        tag = blocks[i]
        body = blocks[i + 1] if i + 1 < len(blocks) else ''
        rules = []
        m = re.search(r'rxSafetyRules:\s*\[(.*?)\],?\s*\}', body, re.S)
        if m:
            inside = m.group(1)
            for rule_match in re.finditer(
                r"label:\s*'([^']+)'[^}]*?pattern:\s*/(.*?)/([gimsuy]*)(?:[^}]*?required:\s*(true|false))?",
                inside, re.S,
            ):
                label = rule_match.group(1)
                raw = rule_match.group(2)
                flags = rule_match.group(3)
                required = rule_match.group(4) == 'true'
                py_flags = 0
                if 'i' in flags: py_flags |= re.I
                if 's' in flags: py_flags |= re.S
                rules.append({'label': label, 'pattern': raw, 'py_flags': py_flags, 'required': required})
        scenarios[tag] = rules
    return scenarios


def round_trip_parity_check(parsed: dict) -> None:
    """Compare the regex-parsed rule labels against the ground-truth
    manifest emitted by `runner.ts --emit-rule-labels`. Drift here
    means the regex parser dropped or fabricated a rule; failing loud
    is preferable to silent mis-counting.

    No-op when the manifest is missing (back-compat for ad-hoc runs
    where the operator skipped the --emit-rule-labels step). Prints a
    warning so the operator sees the skipped check.
    """
    if not RULE_LABELS_MANIFEST.exists():
        print(
            f'[parity] WARN: {RULE_LABELS_MANIFEST} missing — skipping '
            'round-trip parity check. Run `runner.ts --emit-rule-labels` '
            'before analyze.py to enable the self-test.',
            file=sys.stderr,
        )
        return
    expected = json.loads(RULE_LABELS_MANIFEST.read_text())
    expected_set = {(e['tag'], e['label']) for e in expected}
    parsed_set = set()
    for tag, rules in parsed.items():
        for rule in rules:
            parsed_set.add((tag, rule['label']))
    missing_from_parse = expected_set - parsed_set
    extra_in_parse = parsed_set - expected_set
    if missing_from_parse or extra_in_parse:
        print('[parity] FATAL: scenarios.ts regex parser drift detected.', file=sys.stderr)
        if missing_from_parse:
            print(f'  Missing from parse ({len(missing_from_parse)}):', file=sys.stderr)
            for t, l in sorted(missing_from_parse):
                print(f'    - {t}: {l!r}', file=sys.stderr)
        if extra_in_parse:
            print(f'  Extra in parse ({len(extra_in_parse)}):', file=sys.stderr)
            for t, l in sorted(extra_in_parse):
                print(f'    - {t}: {l!r}', file=sys.stderr)
        print(
            '  → Inspect parse_scenarios_ts() in analyze.py. Likely cause: '
            'a rule pattern contains a regex meta-char the parser does not '
            'escape (`/`, `]`, `}`).',
            file=sys.stderr,
        )
        sys.exit(2)
    # Also confirm `required` flags round-trip — labels match but
    # required drift would mean the report misclassifies load-bearing.
    expected_required = {(e['tag'], e['label']): e['required'] for e in expected}
    for tag, rules in parsed.items():
        for rule in rules:
            key = (tag, rule['label'])
            if expected_required.get(key) != rule['required']:
                print(
                    f'[parity] FATAL: required-flag drift at {tag} :: {rule["label"]!r} '
                    f'(manifest={expected_required.get(key)}, parsed={rule["required"]})',
                    file=sys.stderr,
                )
                sys.exit(2)
    print(f'[parity] OK — round-trip check passed on {len(expected_set)} safety-rule label(s)')


def analyze():
    if not RESULTS.exists():
        print(f'FATAL: {RESULTS} missing — run runner.ts --run first', file=sys.stderr)
        sys.exit(1)
    data = json.loads(RESULTS.read_text())
    safety_rules = parse_scenarios_ts()
    round_trip_parity_check(safety_rules)

    # Group by scenario.
    by_scenario = {}
    for v in data:
        tag = v['scenarioTag']
        by_scenario.setdefault(tag, {})[v['mode']] = v

    per_scenario = []
    for tag, by_mode in sorted(by_scenario.items()):
        text_v = by_mode.get('text_notes')
        dict_v = by_mode.get('voice_dictation')
        upld_v = by_mode.get('audio_upload')

        if not (text_v and dict_v and upld_v):
            per_scenario.append({
                'tag': tag,
                'incomplete': True,
                'modesPresent': sorted(by_mode.keys()),
            })
            continue

        text_icd = extract_icd(text_v)
        dict_icd = extract_icd(dict_v)
        upld_icd = extract_icd(upld_v)

        text_cpt_em = extract_cpt_em(text_v)
        dict_cpt_em = extract_cpt_em(dict_v)
        upld_cpt_em = extract_cpt_em(upld_v)

        text_procs = extract_cpt_procs(text_v)
        dict_procs = extract_cpt_procs(dict_v)
        upld_procs = extract_cpt_procs(upld_v)

        text_rx = extract_rx_drugs(text_v)
        dict_rx = extract_rx_drugs(dict_v)
        upld_rx = extract_rx_drugs(upld_v)

        # Pairwise Jaccard + 3-way Jaccard for ICD.
        icd_jaccards = {
            'text_vs_dict': jaccard(text_icd, dict_icd),
            'text_vs_upld': jaccard(text_icd, upld_icd),
            'dict_vs_upld': jaccard(dict_icd, upld_icd),
        }
        icd_min = min(icd_jaccards.values())

        # Rx drug-name Jaccard (lowercased).
        rx_jaccards = {
            'text_vs_dict': jaccard(text_rx, dict_rx),
            'text_vs_upld': jaccard(text_rx, upld_rx),
            'dict_vs_upld': jaccard(dict_rx, upld_rx),
        }
        rx_min = min(rx_jaccards.values())

        # CPT E&M tier comparison — count tiers consistent (e.g.
        # 99213 vs 99214 = different but both established-low).
        em_agree = (text_cpt_em == dict_cpt_em == upld_cpt_em)
        em_set = {text_cpt_em, dict_cpt_em, upld_cpt_em} - {None}
        # Procedure overlap.
        proc_jaccards = {
            'text_vs_dict': jaccard(text_procs, dict_procs),
            'text_vs_upld': jaccard(text_procs, upld_procs),
            'dict_vs_upld': jaccard(dict_procs, upld_procs),
        }

        # Safety-rule fires per mode.
        warnings_text = {
            'text_notes': extract_rx_warning_text(text_v),
            'voice_dictation': extract_rx_warning_text(dict_v),
            'audio_upload': extract_rx_warning_text(upld_v),
        }
        rules = safety_rules.get(tag, [])
        rule_fires_per_mode = []
        for rule in rules:
            pattern = re.compile(rule['pattern'], rule['py_flags'])
            fires = {
                m: bool(pattern.search(warnings_text[m])) for m in MODES
            }
            rule_fires_per_mode.append({
                'label': rule['label'],
                'required': rule['required'],
                'fires': fires,
                'agrees': len(set(fires.values())) == 1,
            })

        # Status agreement.
        statuses = {m: by_mode[m].get('status') for m in MODES}
        all_ready = all(s == 'READY' for s in statuses.values())

        # Cost per mode.
        costs = {m: (by_mode[m].get('processingCostCents') or 0) for m in MODES}

        per_scenario.append({
            'tag': tag,
            'specialty': text_v.get('specialty'),
            'specialtyLabel': text_v.get('specialtyLabel'),
            'title': text_v.get('scenarioTitle'),
            'statuses': statuses,
            'all_ready': all_ready,
            'incomplete': False,
            'icd_emitted': {
                'text_notes': text_icd,
                'voice_dictation': dict_icd,
                'audio_upload': upld_icd,
            },
            'icd_jaccards': icd_jaccards,
            'icd_min_jaccard': icd_min,
            'icd_passes_80': icd_min >= 0.80,
            'rx_emitted': {
                'text_notes': text_rx,
                'voice_dictation': dict_rx,
                'audio_upload': upld_rx,
            },
            'rx_jaccards': rx_jaccards,
            'rx_min_jaccard': rx_min,
            'cpt_em': {
                'text_notes': text_cpt_em,
                'voice_dictation': dict_cpt_em,
                'audio_upload': upld_cpt_em,
            },
            'cpt_em_agree_exact': em_agree,
            'cpt_em_distinct_set': sorted(em_set),
            'cpt_procs': {
                'text_notes': text_procs,
                'voice_dictation': dict_procs,
                'audio_upload': upld_procs,
            },
            'cpt_proc_jaccards': proc_jaccards,
            'safety_rule_fires': rule_fires_per_mode,
            'costs_cents': costs,
        })

    # ── Roll-up ──
    n = len(per_scenario)
    completed = [p for p in per_scenario if not p.get('incomplete') and p.get('all_ready')]
    n_all_ready = len(completed)
    icd_pass = sum(1 for p in completed if p['icd_passes_80'])
    icd_fail = [p for p in completed if not p['icd_passes_80']]

    # Required-safety-rule fires must agree across modes. We track BOTH
    # the total count of required rules (denominator) AND the count of
    # misses (numerator), so the summary line accurately reflects
    # "load-bearing rules passed" rather than "scenarios with no
    # required rules trivially counted as passing."
    required_rule_total = 0
    required_rule_passes = 0
    safety_misses = []
    for p in completed:
        for rule in p.get('safety_rule_fires') or []:
            if rule['required']:
                required_rule_total += 1
                fires = rule['fires']
                if all(fires.values()):
                    required_rule_passes += 1
                else:
                    safety_misses.append({
                        'tag': p['tag'],
                        'rule': rule['label'],
                        'fires': fires,
                    })

    mean_cost = (
        sum(sum(p['costs_cents'].values()) for p in completed) / max(1, n_all_ready * 3) / 100
    )

    summary = {
        'total_scenarios': n,
        'all_three_ready': n_all_ready,
        'icd_passes_80pct_overlap': icd_pass,
        'icd_failures': [
            {'tag': p['tag'], 'min_jaccard': p['icd_min_jaccard'], 'icd_by_mode': p['icd_emitted']}
            for p in icd_fail
        ],
        'required_safety_rule_total': required_rule_total,
        'required_safety_rule_passes': required_rule_passes,
        'required_safety_rule_misses': safety_misses,
        'mean_cost_per_visit_usd': round(mean_cost, 3),
        'per_scenario': per_scenario,
    }
    PARITY_OUT.write_text(json.dumps(summary, indent=2))
    print(f'wrote {PARITY_OUT}')
    print()
    print(f'=== Cross-input-mode audit summary ===')
    print(f'Scenarios: {n_all_ready}/{n} fully ready (3/3 modes READY)')
    print(f'ICD overlap >=80% across modes: {icd_pass}/{n_all_ready}')
    # Load-bearing safety rules are the demo-critical metric. The
    # denominator is the number of rules tagged `required: true` in
    # scenarios.ts (currently 2: BS1 calcium-carbonate + VS2
    # iohexol-contrast-AKI), NOT the count of all completed scenarios.
    print(f'Load-bearing safety rules consistent across modes: {required_rule_passes}/{required_rule_total}')
    print(f'Mean cost / visit: ${mean_cost:.2f}')
    print()
    if icd_fail:
        print('--- ICD-OVERLAP FAILURES (<80% min Jaccard) ---')
        for p in icd_fail:
            print(f'  {p["tag"]} ({p["title"]}): min Jaccard = {p["icd_min_jaccard"]:.2f}')
            for m in MODES:
                codes = p['icd_emitted'][m]
                print(f'    {m:16}: {", ".join(codes) if codes else "(empty)"}')
        print()
    if safety_misses:
        print('--- REQUIRED SAFETY-RULE MISSES ---')
        for ms in safety_misses:
            print(f'  {ms["tag"]} :: {ms["rule"]}')
            print(f'    fires per mode: {ms["fires"]}')
        print()


if __name__ == '__main__':
    analyze()
