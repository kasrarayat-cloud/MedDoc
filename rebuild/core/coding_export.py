"""A separate, local-only Word variant of an already finalized document.

Clinical generation is deliberately absent. The original file and every ZIP
member except document.xml remain unchanged; eligibility is rechecked on every
download, including downloads of a previously materialized variant.
"""
import copy
import hashlib
import re
from io import BytesIO
from xml.parsers import expat
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from lxml import etree

from . import coding_service as service
from .coding_dispatch import validate_selection
from .coding_licensing import cpt_status
from .models import Code, CodingDecision, CodingRun, Encounter
from .security import audit, membership, private_path, scoped

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
TAG = 'quillmd-coding-appendix-v1'
DRAFT_TAG = 'quillmd-synthetic-coding-draft-v1'
CONTRACT = 'finalized-word-with-codes-v1'


def eligible_codes(encounter):
    """Read the persisted approval; never infer acceptance from suggestions."""
    if encounter.status != 'finalized' or encounter.template_version.template.format.lower() != 'docx':
        raise ValidationError('Export with codes requires a finalized Word document. The original download remains available.')
    key = service.input_snapshot(encounter)[3]
    run = CodingRun.objects.filter(encounter=encounter, input_digest=key).first()
    if run is None:
        raise ValidationError('Review and approve coding for the current saved encounter revision before exporting with codes.')
    service.assert_current(run, encounter)
    decisions = list(CodingDecision.objects.filter(run=run)[:2])
    if len(decisions) != 1:
        raise ValidationError('A single saved coding approval is required before exporting with codes.')
    decision = decisions[0]
    if (decision.input_digest != key or decision.selection_digest != service.selection_digest(run)
            or decision.selections != run.selection):
        raise ValidationError('The saved coding approval no longer matches this reviewed result.')
    service.approval_ready(run)
    clean = validate_selection(run, copy.deepcopy(decision.selections))
    if clean != decision.selections or not clean.get('selected_ids'):
        raise ValidationError('No accepted, eligible codes are available for this export.')
    suggestions = run.result.get('suggestions', [])
    rows = {item['id']: item for item in suggestions}
    if len(rows) != len(suggestions):
        raise ValidationError('The coding result contains repeated recommendation identifiers.')
    exports = []
    seen = set()
    for identifier in clean['selected_ids']:
        row = rows.get(identifier)
        if not row or row.get('eligible') is not True or row.get('system') not in ('ICD-10-CM', 'CPT'):
            raise ValidationError('An accepted code is held or unsupported and cannot be exported.')
        replacement = clean['overrides'].get(identifier)
        selected = row
        if replacement:
            candidates = [candidate for candidate in run.result.get('candidates', {}).get(identifier, [])
                          if candidate.get('code') == replacement['code'] and candidate.get('system') == row['system']]
            if len(candidates) != 1:
                raise ValidationError('The approved replacement does not have one verified description.')
            selected = candidates[0]
        release_id = selected.get('release_id', row.get('release_id'))
        releases = [release for release in run.releases if release.get('id') == release_id
                    and release.get('system') == row['system']]
        if len(releases) != 1:
            raise ValidationError('The approved code has no unambiguous dated terminology release.')
        catalog = Code.objects.select_related('release').filter(release_id=release_id, code=selected['code']).first()
        if (catalog is None or catalog.release.system != row['system']
                or not catalog.release.effective_from <= encounter.service_date <= catalog.release.effective_until
                or catalog.description != selected.get('description')
                or not catalog.description.strip() or not catalog.release.source_url):
            raise ValidationError('The accepted code description or its dated source cannot be verified.')
        if row['system'] == 'CPT':
            status = cpt_status(encounter.service_date)
            if not status['available'] or str(catalog.release_id) != status.get('release_id'):
                raise ValidationError('CPT export remains held until the applicable licensed description and criteria are verified.')
        identity = (row['system'], catalog.code)
        if identity in seen:
            raise ValidationError('The accepted selections contain a repeated code.')
        seen.add(identity)
        exports.append({'system': row['system'], 'code': catalog.code, 'description': catalog.description,
                        'release_version': catalog.release.version, 'source_url': catalog.release.source_url,
                        'effective_from': catalog.release.effective_from.isoformat(),
                        'effective_until': catalog.release.effective_until.isoformat()})
    # The original approval and catalogue path above remain independent. A
    # bounded API-output decision does not alter that approval or turn an
    # unverified provider description into licensed terminology.
    from .coding_output import accepted_output_rows
    supplements = accepted_output_rows(encounter, run, decision)
    if supplements:
        for output in supplements:
            if (not isinstance(output, dict) or output.get('system') != 'CPT'
                    or not re.fullmatch(r'[0-9]{5}', str(output.get('code', '')))
                    or output.get('description_status') != 'withheld_defective_provider_text'):
                raise ValidationError('The accepted API output has an unsupported export shape.')
            matches = [row for row in suggestions
                       if row.get('system') == output['system'] and row.get('code') == output['code']]
            if len(matches) != 1:
                raise ValidationError('Only a retained selected code can enter the API-output appendix.')
            identity = (output['system'], output['code'])
            if identity in seen:
                raise ValidationError('The accepted selections contain a repeated code.')
            evidence = _note_evidence(output.get('evidence_spans'), run.inputs['notes'])
            if not evidence:
                raise ValidationError('The accepted API output has no original-note evidence.')
            seen.add(identity)
            exports.append({**copy.deepcopy(output), 'description': '',
                            'export_route': 'bounded_api_output', 'evidence_spans': evidence})
        # Preserve the byte-identical historical ICD-only variant until an
        # additional output decision is actually accepted. The combined review
        # also carries the original-note evidence for its accepted ICD rows.
        for exported in exports:
            if exported.get('export_route') == 'bounded_api_output':
                continue
            matched = [row for row in suggestions
                       if row.get('system') == exported['system'] and row.get('code') == exported['code']]
            if len(matched) == 1 and matched[0].get('evidence_spans'):
                exported['evidence_spans'] = _note_evidence(matched[0]['evidence_spans'], run.inputs['notes'])
    return run, decision, sorted(exports, key=lambda row: (row['system'] != 'ICD-10-CM', row['code']))


def _note_evidence(spans, notes):
    """Project exact note quotations only, never generated diagnostic prose."""
    if not isinstance(spans, list):
        raise ValidationError('The accepted output evidence cannot be verified.')
    evidence = []
    for span in spans:
        if not isinstance(span, dict):
            raise ValidationError('The accepted output evidence cannot be verified.')
        quote = span.get('quote', span.get('text'))
        if (not isinstance(quote, str) or not quote.strip() or quote not in notes
                or span.get('status', 'valid') != 'valid'):
            raise ValidationError('The accepted output evidence does not match the original note.')
        evidence.append({'quote': quote})
    return evidence


def export_status(encounter):
    try:
        _, _, rows = eligible_codes(encounter)
        return {'available': True, 'count': len(rows), 'reason': ''}
    except ValidationError as exc:
        return {'available': False, 'count': 0, 'reason': '; '.join(exc.messages)}


def _body_boundary(xml):
    """Locate insertion bytes without reserializing the clinical XML."""
    parser = expat.ParserCreate(namespace_separator='}')
    stack, sections = [], []
    boundary = {'end': None}

    def reject_doctype(*_):
        raise ValidationError('The finalized Word XML contains an unsupported document type.')

    def start(name, attrs):
        if name == W + '}tag' and attrs.get(W + '}val') in (TAG, DRAFT_TAG):
            raise ValidationError('This document already contains a coding appendix; download from the original finalized document.')
        if stack == [W + '}document', W + '}body']:
            boundary['last_child'] = name
            if name == W + '}sectPr':
                sections.append([parser.CurrentByteIndex, None])
        stack.append(name)

    def end(name):
        offset = parser.CurrentByteIndex
        if stack == [W + '}document', W + '}body', W + '}sectPr']:
            sections[-1][1] = xml.index(b'>', offset) + 1 if xml[offset:offset + 2] == b'</' else offset
        if stack == [W + '}document', W + '}body']:
            boundary['end'] = offset
        stack.pop()

    parser.StartDoctypeDeclHandler = reject_doctype
    parser.StartElementHandler, parser.EndElementHandler = start, end
    try:
        parser.Parse(xml, True)
    except (expat.ExpatError, ValueError) as exc:
        raise ValidationError('The finalized Word document XML is invalid.') from exc
    if boundary['end'] is None or len(sections) != 1 or boundary.get('last_child') != W + '}sectPr':
        raise ValidationError('The finalized Word section boundary is unsupported; its original download is unchanged.')
    # The raw-byte splice below intentionally supports the UTF-8 OOXML written by
    # QuillMD. A different encoding is refused, never silently rewritten.
    if b'\x00' in xml:
        raise ValidationError('The finalized Word XML encoding is unsupported for a preserving appendix.')
    return sections[0]


def _element(parent, name, text=None, **attributes):
    element = etree.SubElement(parent, '{' + W + '}' + name)
    for key, value in attributes.items():
        element.set('{' + W + '}' + key, str(value))
    if text is not None:
        element.text = text
    return element


def _paragraph(parent, text, heading=False):
    paragraph = _element(parent, 'p')
    properties = _element(paragraph, 'pPr')
    _element(properties, 'spacing', before='180' if heading else '0', after='100')
    _element(properties, 'keepLines')
    if heading:
        _element(properties, 'keepNext')
    run = _element(paragraph, 'r')
    style = _element(run, 'rPr')
    _element(style, 'rFonts', ascii='Arial', hAnsi='Arial')
    _element(style, 'sz', val='26' if heading else '22')
    if heading:
        _element(style, 'b')
    _element(run, 't', text)


def append_codes(original, rows):
    """Return a fresh variant, preserving all clinical body bytes and assets."""
    paragraphs = [('Diagnosis and procedure codes', True)]
    bounded = any(row.get('export_route') == 'bounded_api_output' for row in rows)
    if bounded:
        paragraphs.append(('Synthetic retained-response review. AI-assisted code selections were reviewed and accepted '
            'by the clinician. CPT is exported as a code number with original-note evidence; its defective provider '
            'description is withheld and is not verified. This document is not for billing or real-patient use.', False))
    for system, label in (('ICD-10-CM', 'ICD-10-CM'), ('CPT', 'CPT')):
        group = [row for row in rows if row['system'] == system]
        if group:
            paragraphs.append((label, True))
            for row in group:
                if row.get('export_route') == 'bounded_api_output':
                    paragraphs.extend([(row['code'] + ' — clinician-accepted code number', False),
                                       ('Description withheld; upstream description and terminology version remain unresolved.', False)])
                else:
                    paragraphs.append((row['code'] + ' — ' + row['description'], False))
                if bounded:
                    for span in row.get('evidence_spans', []):
                        paragraphs.append(('Original-note evidence: ' + span['quote'], False))
    return append_review(original, paragraphs, tag=TAG)


def append_review(original, paragraphs, *, tag):
    """Share preserving assembly without changing approved export semantics."""
    if tag not in (TAG, DRAFT_TAG):
        raise ValidationError('Unsupported coding appendix variant.')
    try:
        with ZipFile(BytesIO(original)) as source:
            if len(source.namelist()) != len(set(source.namelist())):
                raise ValidationError('The finalized Word archive has repeated members.')
            xml = source.read('word/document.xml')
            begin, end = _body_boundary(xml)
            original_section = xml[begin:end]
            safe = etree.XMLParser(resolve_entities=False, no_network=True)
            document = etree.fromstring(xml, safe)
            section = document.find('{' + W + '}body/{' + W + '}sectPr')
            appendix_section = etree.Element('{' + W + '}sectPr', nsmap={'q': W})
            # Header/footer, paper and margins carry forward, while multi-column
            # clinical layouts do not force the code list into narrow columns.
            for child in section:
                if etree.QName(child).localname in ('headerReference', 'footerReference', 'pgSz', 'pgMar', 'titlePg'):
                    appendix_section.append(copy.deepcopy(child))
            position = sum(etree.QName(child).localname in ('headerReference', 'footerReference') for child in appendix_section)
            kind = etree.Element('{' + W + '}type')
            kind.set('{' + W + '}val', 'nextPage')
            appendix_section.insert(position, kind)
            appendix = etree.Element('{' + W + '}sdt', nsmap={'q': W})
            _element(_element(appendix, 'sdtPr'), 'tag', val=tag)
            content = _element(appendix, 'sdtContent')
            for text, heading in paragraphs:
                _paragraph(content, text, heading=heading)
            boundary = ('<q:p xmlns:q="' + W + '"><q:pPr>'
                        '<q:spacing q:before="0" q:after="0" q:line="1" q:lineRule="exact"/>'
                        '<q:rPr><q:sz q:val="2"/></q:rPr>').encode() + original_section + b'</q:pPr></q:p>'
            amended = xml[:begin] + boundary + etree.tostring(appendix) + etree.tostring(appendix_section) + xml[end:]
            etree.fromstring(amended, safe)  # Fail before saving an invalid variant.
            output = BytesIO()
            with ZipFile(output, 'w') as target:
                target.comment = source.comment
                for member in source.infolist():
                    target.writestr(member, amended if member.filename == 'word/document.xml' else source.read(member.filename))
            return output.getvalue()
    except (BadZipFile, KeyError, etree.XMLSyntaxError, TypeError, ValueError) as exc:
        raise ValidationError('The finalized Word document cannot receive a preserving code appendix.') from exc


def _materialize(encounter, decision, rows, original):
    binding = service.digest({'contract': CONTRACT, 'original_sha256': encounter.export_sha256,
                              'decision': str(decision.pk), 'selection_digest': decision.selection_digest, 'codes': rows})
    path = private_path(f'exports/coding/{encounter.pk}/{binding}.docx')
    for directory in (path.parent.parent, path.parent):
        directory.mkdir(exist_ok=True, mode=0o700)
    output = append_codes(original, rows)
    expected = hashlib.sha256(output).hexdigest()
    try:
        with path.open('xb') as handle:
            path.chmod(0o600)
            handle.write(output)
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValidationError('The existing code export failed its integrity check.')
    return path, expected


@never_cache
@require_GET
@transaction.atomic
def export_with_codes(request, pk):
    encounter = get_object_or_404(scoped(Encounter, request.user).select_for_update(of=('self',))
                                 .select_related('patient', 'department', 'template_version__template'),
                                 pk=pk, status='finalized')
    membership(request.user, encounter.department)
    try:
        run, decision, rows = eligible_codes(encounter)
        original = private_path(encounter.export_path).read_bytes()
        if hashlib.sha256(original).hexdigest() != encounter.export_sha256:
            raise ValidationError('The original finalized export failed its integrity check.')
        path, sha256 = _materialize(encounter, decision, rows, original)
    except (ValidationError, OSError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'The finalized export could not be read or stored.'
        return HttpResponse(message, status=409, content_type='text/plain')
    audit(request.user, 'encounter.export_with_codes', encounter.pk, department=encounter.department,
          run_id=str(run.pk), decision_id=str(decision.pk), selection_digest=decision.selection_digest,
          original_sha256=encounter.export_sha256, export_sha256=sha256, code_count=len(rows))
    return FileResponse(path.open('rb'), as_attachment=True,
                        filename=f'quillmd-{str(encounter.pk)[:8]}-with-codes.docx')
