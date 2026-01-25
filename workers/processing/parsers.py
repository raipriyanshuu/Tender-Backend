from __future__ import annotations

import csv
import os
from typing import Iterable

import PyPDF2
from docx import Document
from openpyxl import load_workbook

from workers.core.errors import ParseError, PermanentError
from workers.utils.filesystem import get_file_type

# OCR imports (optional - only if ENABLE_OCR=true)
_OCR_AVAILABLE = False
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    _OCR_AVAILABLE = True
except ImportError:
    pass

# GAEB imports (optional - only if GAEB_ENABLED=true)
# DISABLED FOR PRODUCTION - Python 3.13 compatibility issues
_GAEB_AVAILABLE = False
# try:
#     from lxml import etree
#     _GAEB_AVAILABLE = True
# except ImportError:
#     pass


def _ocr_pdf_page(image) -> str:
    """Extract text from a single PDF page image using OCR."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        return pytesseract.image_to_string(image, lang="deu+eng")
    except Exception:  # noqa: BLE001
        return ""


def parse_pdf(file_path: str, enable_ocr: bool = False, ocr_max_pages: int = 50) -> str:
    """Parse PDF with optional OCR fallback for scanned documents."""
    try:
        with open(file_path, "rb") as handle:
            reader = PyPDF2.PdfReader(handle)
            text_content = "\n".join(page.extract_text() or "" for page in reader.pages)
            
            # Check if PDF is scanned (no/minimal text)
            if enable_ocr and _OCR_AVAILABLE and len(text_content.strip()) < 100:
                print(f"[Parser] PDF appears scanned ({len(text_content)} chars), running OCR...")
                
                # Limit pages for OCR to prevent runaway jobs
                num_pages = len(reader.pages)
                pages_to_ocr = min(num_pages, ocr_max_pages)
                
                try:
                    # Convert PDF to images and OCR
                    images = convert_from_path(file_path, dpi=300, first_page=1, last_page=pages_to_ocr)
                    ocr_chunks = [_ocr_pdf_page(img) for img in images]
                    ocr_text = "\n\n=== PAGE BREAK ===\n\n".join(ocr_chunks)
                    
                    if len(ocr_text.strip()) > 100:
                        print(f"[Parser] OCR successful: {len(ocr_text)} chars from {pages_to_ocr} pages")
                        return ocr_text
                    else:
                        print(f"[Parser] OCR failed to extract meaningful text")
                        return text_content  # Return original (even if empty)
                except Exception as ocr_exc:  # noqa: BLE001
                    print(f"[Parser] OCR failed: {ocr_exc}")
                    return text_content  # Fallback to original text
            
            return text_content
    except Exception as exc:  # noqa: BLE001 - return consistent error types
        raise ParseError(f"Failed to parse PDF: {file_path}") from exc


def parse_word(file_path: str) -> str:
    try:
        doc = Document(file_path)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    except Exception as exc:  # noqa: BLE001 - return consistent error types
        raise ParseError(f"Failed to parse Word document: {file_path}") from exc


def parse_excel(file_path: str) -> str:
    try:
        wb = load_workbook(filename=file_path, data_only=True)
        chunks: list[str] = []
        for sheet in wb.worksheets:
            chunks.append(f"## {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join("" if value is None else str(value) for value in row)
                if row_text.strip():
                    chunks.append(row_text)
        return "\n".join(chunks)
    except Exception as exc:  # noqa: BLE001 - return consistent error types
        raise ParseError(f"Failed to parse Excel file: {file_path}") from exc


def parse_csv(file_path: str) -> str:
    try:
        chunks: list[str] = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            reader = csv.reader(handle)
            for row in reader:
                row_text = " | ".join(str(cell) for cell in row)
                if row_text.strip():
                    chunks.append(row_text)
        return "\n".join(chunks)
    except Exception as exc:  # noqa: BLE001 - return consistent error types
        raise ParseError(f"Failed to parse CSV file: {file_path}") from exc


def parse_text(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except Exception as exc:  # noqa: BLE001 - return consistent error types
        raise ParseError(f"Failed to parse text file: {file_path}") from exc


# GAEB PARSING DISABLED FOR PRODUCTION - Python 3.13 compatibility issues
# def parse_gaeb(file_path: str) -> str:
#     """Parse GAEB XML files (German tender exchange format) into normalized text."""
#     raise ParseError("GAEB parsing is disabled in production due to Python 3.13 compatibility issues")


def parse_file(
    file_path: str,
    enable_ocr: bool = False,
    ocr_max_pages: int = 50,
    temp_file_path: str | None = None,
) -> str:
    """
    Parse file based on type, with optional OCR for scanned PDFs.
    
    Args:
        file_path: Original file path (for type detection)
        enable_ocr: Enable OCR for scanned PDFs
        ocr_max_pages: Maximum pages to OCR
        temp_file_path: Temporary file path (if downloaded from R2)
        
    Returns:
        Extracted text content
    """
    # Use temp file path if provided, otherwise use original path
    actual_path = temp_file_path if temp_file_path else file_path
    
    file_type = get_file_type(file_path)
    
    if file_type == "pdf":
        return parse_pdf(actual_path, enable_ocr=enable_ocr, ocr_max_pages=ocr_max_pages)
    if file_type == "word":
        return parse_word(actual_path)
    if file_type == "excel":
        return parse_excel(actual_path)
    if file_type == "csv":
        return parse_csv(actual_path)
    if file_type == "text":
        return parse_text(actual_path)
    # GAEB PARSING DISABLED FOR PRODUCTION
    # if file_type == "gaeb":
    #     return parse_gaeb(actual_path)
    
    raise PermanentError(f"Unsupported file type: {file_path}")
