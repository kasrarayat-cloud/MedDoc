"""Offline Corti response boundary; never selects candidates or approves a code.

No network, Django, database, credential, or clinical-record dependency. Terminology
is trusted caller-supplied data, never metadata accepted from the provider response.
Catalogue verification establishes dated membership/description, not clinical fit.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import hashlib
import re
from types import MappingProxyType
from typing import Mapping

SYSTEMS = {'icd10cm-outpatient', 'cpt'}


def normalize_code(system, value):
    if type(value) is not str:
        raise ValueError('A code must be a string.')
    code = value.strip().upper()
    if system == 'icd10cm-outpatient':
        if not re.fullmatch(r'[A-Z][A-Z0-9]{2}(?:\.[A-Z0-9]{1,4}|[A-Z0-9]{0,4})', code):
            raise ValueError('Invalid ICD-10-CM syntax.')
        code = code.replace('.', '')
        if not any(c.isdigit() for c in code):
            raise ValueError('Invalid ICD-10-CM syntax.')
        return code[:3] + ('.' + code[3:] if len(code) > 3 else '')
    if system == 'cpt' and re.fullmatch(r'(?:[0-9]{5}|[0-9]{4}[A-Z])', code):
        return code
    raise ValueError('Unsupported system or code syntax.')


@dataclass(frozen=True)
class CatalogRelease:
    """Trusted, verified local release. Not an entitlement importer or grant."""
    system: str
    version: str
    effective_from: date
    effective_until: date
    source: str
    sha256: str
    descriptions: Mapping[str, str]
    authorization_reference: str

    def __post_init__(self):
        if (self.system not in SYSTEMS or not self.version or not self.source
                or type(self.effective_from) is not date or type(self.effective_until) is not date
                or self.effective_from > self.effective_until
                or not re.fullmatch('[a-f0-9]{64}', self.sha256)):
            raise ValueError('Incomplete dated catalogue provenance.')
        rows = {}
        for code, description in self.descriptions.items():
            code = normalize_code(self.system, code)
            if code in rows or type(description) is not str or not description.strip():
                raise ValueError('Invalid or duplicate catalogue row.')
            rows[code] = description
        if not rows:
            raise ValueError('An empty catalogue cannot verify a code.')
        object.__setattr__(self, 'descriptions', MappingProxyType(rows))


class DatedTerminology:
    def __init__(self, releases=(), unavailable_reasons=None, required_versions=None):
        self.releases = tuple(releases)
        self.unavailable_reasons = dict(unavailable_reasons or {})
        self.required_versions = dict(required_versions or {})

    def lookup(self, system, code, service_date, provider_display):
        result = dict(status='unavailable', description=None, version=None, source=None,
                      sha256=None, effective_from=None, effective_until=None,
                      description_matches=None, reason='No authorized local catalogue is available.')
        available = [r for r in self.releases if r.system == system]
        if not available:
            result['reason'] = self.unavailable_reasons.get(system, result['reason'])
            return result
        authorized = [r for r in available if r.authorization_reference.strip()]
        if not authorized:
            result.update(status='unauthorized', reason='Catalogue use has no verified authorization reference.')
            return result
        matches = [r for r in authorized if r.effective_from <= service_date <= r.effective_until
                   and (system not in self.required_versions or r.version == self.required_versions[system])]
        if not matches:
            result.update(status='version_unavailable', reason='No authorized requested release covers the service date; no nearest-year fallback.')
            return result
        if len(matches) != 1:
            result.update(status='ambiguous_release', reason='More than one authorized release covers this date; verification refused.')
            return result
        release = matches[0]
        result.update(version=release.version, source=release.source, sha256=release.sha256,
                      effective_from=release.effective_from.isoformat(), effective_until=release.effective_until.isoformat())
        if code not in release.descriptions:
            result.update(status='unknown_code', reason='Code is absent from the authorized release for this service date.')
            return result
        description = release.descriptions[code]
        result.update(status='verified', description=description,
                      description_matches=provider_display == description,
                      reason='Dated code membership and reference description verified; clinical applicability still requires clinician review.')
        return result


def _evidence(raw, contexts):
    if type(raw) is not list or not raw:
        return [], 'missing' if raw in (None, []) else 'invalid'
    checked = []
    for item in raw:
        item = item if type(item) is dict else {}
        ci, start, end, text = (item.get(k) for k in ('contextIndex', 'start', 'end', 'text'))
        valid = (type(ci) is int and 0 <= ci < len(contexts)
                 and type(start) is int and type(end) is int and type(text) is str
                 and 0 <= start < end <= len(contexts[ci]) and contexts[ci][start:end] == text)
        checked.append(dict(context_index=ci, start=start, end=end, text=text,
                            status='valid' if valid else 'invalid',
                            reason='Exact source span; clinical meaning not automatically validated.' if valid
                            else 'Missing, out-of-range or mismatched source span.'))
    return checked, 'valid' if all(e['status'] == 'valid' for e in checked) else 'invalid'


def adapt_response(response, request, *, service_date, terminology=None,
                   original_verdict='NOT_EVALUATED', source_response_sha256=None):
    """Parse selected codes only. Every proposal remains unapproved/non-actionable.

    Missing/unknown terminology and evidence do not silently erase selected output:
    the provider selection survives with its precise verification failure. Malformed
    selected objects are quarantined in diagnostics, never salvaged from alternatives.
    """
    if type(service_date) is not date:
        raise ValueError('An explicit date of service is required.')
    if type(response) is not dict or type(response.get('codes')) is not list:
        raise ValueError('Response must contain a selected codes array.')
    if type(request) is not dict or request.get('system') != ['icd10cm-outpatient', 'cpt']:
        raise ValueError('This adapter requires the two authorized coding systems.')
    context = request.get('context')
    if type(context) is not list or not context or any(type(c) is not dict or c.get('type') != 'text'
            or type(c.get('text')) is not str for c in context):
        raise ValueError('Replay requires original text contexts for evidence verification.')
    texts = [c['text'] for c in context]
    terminology = terminology or DatedTerminology()
    proposals, rejected, alternatives, seen = [], [], [], set()
    for index, row in enumerate(response['codes']):
        selection_id = f'selected:{index}'
        if type(row) is not dict:
            rejected.append(dict(id=selection_id, reason='Malformed selected object.', raw=deepcopy(row)))
            continue
        alternatives.append(dict(selected_id=selection_id, system=row.get('system'),
                                 provider_code=row.get('code'), alternatives=deepcopy(row.get('alternatives', []))))
        try:
            system, provider_code = row.get('system'), row.get('code')
            code = normalize_code(system, provider_code)
        except (ValueError, TypeError):
            rejected.append(dict(id=selection_id, reason='Unsupported system or invalid selected code.', raw=deepcopy(row)))
            continue
        if (system, code) in seen:
            rejected.append(dict(id=selection_id, reason='Duplicate normalized selected code; original retained.', raw=deepcopy(row)))
            continue
        seen.add((system, code))
        evidence, evidence_status = _evidence(row.get('evidences'), texts)
        display = row.get('display') if type(row.get('display')) is str else None
        term = terminology.lookup(system, code, service_date, display)
        issues = []
        if evidence_status != 'valid':
            issues.append('Source evidence is ' + evidence_status + '; proposal cannot be accepted.')
        if term['status'] != 'verified':
            issues.append(term['reason'])
        elif not term['description_matches']:
            issues.append('Provider description differs from dated terminology. Both descriptions retained; no silent replacement.')
        if display is None:
            issues.append('Provider description is missing or malformed.')
        proposals.append(dict(id=selection_id, system=system, code=code, provider_code=provider_code,
                              provider_display=display, terminology=term, evidence=evidence,
                              evidence_status=evidence_status, clinical_applicability='requires_clinician_review',
                              approved=False, selectable=False, issues=issues))
    blockers = ['Offline replay only; no dashboard activation or clinical acceptance path is connected.',
                'Exact evidence spans do not establish clinical appropriateness; clinician review is still required.',
                'The original experiment verdict is retained: ' + original_verdict + '.']
    if any(p['terminology']['status'] != 'verified' for p in proposals):
        blockers.append('One or more proposals lack verified service-date terminology; affected results remain unverified.')
    if any(p['evidence_status'] != 'valid' for p in proposals):
        blockers.append('One or more proposals lack intact source evidence.')
    if rejected:
        blockers.append('Malformed, unsupported or duplicate selected entries require diagnostic review.')
    return dict(schema_version='quillmd-corti-replay-v1', mode='offline_replay', service_date=service_date.isoformat(),
                original_verdict=original_verdict, source_response_sha256=source_response_sha256,
                proposed_selections=proposals,
                diagnostics=dict(candidates=deepcopy(response.get('candidates', [])), alternatives=alternatives,
                                 rejected_selected=rejected, provider_response=deepcopy(response)),
                blockers=blockers, dashboard_activation_allowed=False)


def load_icd_catalog(path, metadata):
    """Read an existing official catalogue after verifying its pinned local provenance.

    Metadata must come from the application's audited release record, not Corti.
    This performs no download/import and cannot load/authorize CPT content.
    """
    from pathlib import Path
    from urllib.parse import urlsplit
    raw = Path(path).read_bytes()
    url = urlsplit(metadata['source'])
    if (metadata.get('system') != 'icd10cm-outpatient' or url.scheme != 'https'
            or url.hostname not in {'ftp.cdc.gov', 'www.cdc.gov', 'www.cms.gov'}
            or url.username or url.password or url.query or url.fragment
            or hashlib.sha256(raw).hexdigest() != metadata['sha256']):
        raise ValueError('Official ICD catalogue provenance/hash verification failed.')
    rows = {}
    for line in raw.decode('utf-8').splitlines():
        match = re.fullmatch(r'([A-Z][A-Z0-9]{2,6})\s+(.+)', line)
        if not match:
            raise ValueError('Malformed complete ICD catalogue row.')
        code = normalize_code('icd10cm-outpatient', match[1])
        if code in rows:
            raise ValueError('Duplicate ICD catalogue row.')
        rows[code] = match[2].strip()
    if len(rows) != metadata['code_count'] or len(rows) < 70000:
        raise ValueError('Incomplete ICD catalogue.')
    return CatalogRelease('icd10cm-outpatient', metadata['version'], date.fromisoformat(metadata['effective_from']),
                          date.fromisoformat(metadata['effective_until']), metadata['source'], metadata['sha256'], rows,
                          metadata['authorization_reference'])
