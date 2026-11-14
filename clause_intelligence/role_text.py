"""Matching view with a reversible source-position map; never rewritten evidence."""
from dataclasses import dataclass
import re
import unicodedata
from .classification import fold
from .evidence import subspan


@dataclass(frozen=True)
class TextView:
    original: str
    text: str
    positions: tuple[int, ...]

    @classmethod
    def of(cls, text):
        characters, positions = [], []
        for index, character in enumerate(text):
            normalized = fold(character)
            characters.extend(normalized)
            positions.extend([index]*len(normalized))
        return cls(text, ''.join(characters), tuple(positions))

    def bounds(self, start, end):
        if not 0 <= start < end <= len(self.positions):
            raise ValueError('Invalid matching-view bounds')
        left, right = self.positions[start], self.positions[end-1]+1
        while right < len(self.original) and unicodedata.combining(self.original[right]):
            right += 1
        return left, right

    def span(self, clause, start, end):
        return subspan(clause, *self.bounds(start, end))


def clean_party(value):
    value = fold(value).strip()
    value = re.sub(r'^the\s+', '', value)
    if value.startswith('لل'):
        value = 'ال'+value[2:]
    return value


def sentences(text):
    heading = re.match(r'^\s*(?:(?:clause|article|المادة|البند)\s+)?\d+(?:[./]\d+)*(?:\([a-z]\))?[.:)]?\s*', text, re.I)
    initial = heading.end() if heading else 0
    start = initial
    for match in re.finditer(r'[;؛\n]|[.!?](?=\s|$)', text[initial:]):
        end = initial+match.end()
        if text[start:end].strip():
            yield start, end
        start = end
    if text[start:].strip():
        yield start, len(text)
