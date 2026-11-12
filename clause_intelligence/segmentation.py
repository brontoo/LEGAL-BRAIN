"""Line-anchored structure candidates, without rewriting source or inventing labels."""
import re
from .schemas import Clause, ClauseError, EvidenceSpan
from . import config

ORDINALS = {'الأولى': '1', 'الاولى': '1', 'الأول': '1', 'الاول': '1', 'الثانية': '2', 'الثاني': '2',
            'الثالثة': '3', 'الثالث': '3', 'الرابعة': '4', 'الرابع': '4', 'الخامسة': '5', 'الخامس': '5',
            'السادسة': '6', 'السادس': '6', 'السابعة': '7', 'السابع': '7', 'الثامنة': '8', 'الثامن': '8',
            'التاسعة': '9', 'التاسع': '9', 'العاشرة': '10', 'العاشر': '10', 'أولاً': '1', 'أولا': '1',
            'اولاً': '1', 'اولًا': '1', 'ثانياً': '2', 'ثانيا': '2', 'ثالثاً': '3', 'ثالثا': '3'}
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
NUMBER = r'\d+(?:[./]\d+)*(?:\([a-zA-Zأ-ي]\))?'
HEADING = re.compile(r'^(?:(?P<prefix>Clause|Article|المادة|البند)\s+(?P<ref>' + NUMBER + r'|' +
                     '|'.join(ORDINALS) + r')(?=\s|[:.)—–-]|$)|(?P<bare>' + NUMBER +
                     r')(?=\s|[:.)—–-]|$)|(?P<ordinal>أولاً|أولا|اولاً|ثانياً|ثانيا|ثالثاً|ثالثا)(?=\s|:|$))', re.I)
STRUCTURE = re.compile(r'^(?P<kind>Schedule|Annex|Appendix|ملحق|مرفق)\s+(?P<label>[\w-]{1,30})(?=\s|:|$)', re.I)
SECTION = re.compile(r'^(Recitals|Definitions|Signatures?|Amendments?|التمهيد|التعريفات|التوقيعات|التعديلات)(?:\s*[:：]|\s*$)', re.I)


def canonical_label(value):
    value = value.strip().translate(DIGITS)
    return ORDINALS.get(value, value.lower())


def segment(document):
    boundaries = []
    position = 0
    previous_blank = True
    for line in document.text.splitlines(keepends=True):
        text = line.strip()
        if text:
            heading = HEADING.match(text)
            schedule = STRUCTURE.match(text)
            section = SECTION.match(text)
            label = None
            structure = 'provision'
            status = 'explicit'
            if heading:
                label = canonical_label(heading.group('ref') or heading.group('bare') or heading.group('ordinal'))
                if heading.group('bare') and '.' not in label and '/' not in label:
                    # A standalone four-digit line can be a date, amount or clause.
                    status = 'ambiguous_numbering' if len(label) == 4 else 'explicit'
            elif schedule:
                label = 'schedule:' + canonical_label(schedule.group('label'))
                structure = 'schedule'
            elif section:
                structure = {'recitals': 'recitals', 'التمهيد': 'recitals', 'definitions': 'definitions',
                             'التعريفات': 'definitions', 'التوقيعات': 'signature', 'التعديلات': 'amendment'}.get(
                                 section.group(1).lower(), 'signature' if text.lower().startswith('signature') else 'amendment')
            elif not boundaries or previous_blank:
                structure = 'title' if not boundaries and len(text) <= 120 else 'provision'
                status = 'unnumbered_boundary_candidate'
            else:
                position += len(line)
                previous_blank = False
                continue
            boundaries.append((position, label, text[:160] if heading or schedule or section or structure == 'title' else None, structure, status))
        previous_blank = not text
        position += len(line)
    if len(boundaries) > config.MAX_CLAUSES:
        raise ClauseError('Too many clauses')
    clauses = []
    labels = {}
    for index, (start, label, heading, structure, status) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(document.text)
        while start < end and document.text[start].isspace():
            start += 1
        while end > start and document.text[end - 1].isspace():
            end -= 1
        if end - start > config.MAX_CLAUSE_CHARS:
            raise ClauseError('Clause exceeds analysis limits; supply smaller sections')
        clause_id = f'C-{index + 1:04d}'  # Internal identity, never fabricated contractual numbering.
        parent = None
        if label and not label.startswith('schedule:'):
            parent_label = re.sub(r'\([^)]+\)$', '', label) if label.endswith(')') else re.sub(r'[./][^./]+$', '', label)
            candidates = labels.get(parent_label, []) if parent_label != label else []
            parent = candidates[0] if len(candidates) == 1 else None
        span = EvidenceSpan(document.document_id, document.version, document.digest, clause_id,
                            start, end, document.text[start:end])
        clauses.append(Clause(clause_id, index + 1, span, label, heading, parent, structure, status))
        if label:
            labels.setdefault(label, []).append(clause_id)
    return tuple(clauses)
