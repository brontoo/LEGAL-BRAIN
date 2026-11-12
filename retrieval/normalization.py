"""Conservative search-only normalization. Never normalize stored evidence."""
import re
import unicodedata
from .schemas import RetrievalError

TRANSLATION = str.maketrans('أإآٱ٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', 'اااا01234567890123456789')


def normalize(text: str) -> str:
    if not isinstance(text,str) or len(text)>20000 or '\x00' in text:
        raise RetrievalError('Invalid search text')
    text=unicodedata.normalize('NFKC',text).lower().translate(TRANSLATION)
    text=re.sub('[\u064b-\u065f\u0670\u0640]', '', text)
    return ' '.join(text.split())
