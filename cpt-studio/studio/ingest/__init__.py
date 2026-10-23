"""Document ingestion (ARCHITECTURE 5.1): canonical text from PDF, DOCX, TXT or paste.

Importable without Django: the sandboxed extraction child imports this package.
"""
from .extract import DETECT, Limits, engine_versions, extract_document, extract_paste
from .ocr import OcrTools, find_ocr_tools, ocr_available, ocr_tools
from .text import canonicalize

__all__ = ['DETECT', 'Limits', 'OcrTools', 'canonicalize', 'engine_versions', 'extract_document', 'extract_paste',
           'find_ocr_tools', 'ocr_available', 'ocr_tools']
