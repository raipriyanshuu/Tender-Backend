"""
Tests for GAEB and OCR parsing functionality.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from workers.processing.parsers import parse_file, parse_gaeb, parse_pdf
from workers.core.errors import ParseError


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_gaeb_parser_with_sample():
    """Test GAEB parser with a minimal sample file."""
    sample_gaeb = FIXTURES_DIR / "sample.x83"
    
    if not sample_gaeb.exists():
        pytest.skip("GAEB sample file not found - create test fixture first")
    
    try:
        text = parse_gaeb(str(sample_gaeb))
        assert len(text) > 50, "GAEB extraction should return meaningful text"
        assert "LEISTUNGSVERZEICHNIS" in text or "LV" in text or "Projekt" in text
    except ParseError as exc:
        pytest.fail(f"GAEB parsing failed: {exc}")


def test_gaeb_empty_file():
    """Test GAEB parser handles empty/invalid files gracefully."""
    sample_empty = FIXTURES_DIR / "empty.x84"
    
    if not sample_empty.exists():
        pytest.skip("Empty GAEB fixture not found")
    
    with pytest.raises(ParseError, match="GAEB file appears empty"):
        parse_gaeb(str(sample_empty))


def test_ocr_detection_on_scanned_pdf():
    """Test OCR fallback for scanned PDFs."""
    sample_scanned = FIXTURES_DIR / "scanned.pdf"
    
    if not sample_scanned.exists():
        pytest.skip("Scanned PDF fixture not found")
    
    try:
        # With OCR enabled
        text = parse_pdf(str(sample_scanned), enable_ocr=True, ocr_max_pages=5)
        # Scanned PDFs should return text (either original or OCR)
        assert isinstance(text, str)
    except Exception as exc:
        # OCR might fail if tesseract not installed
        if "tesseract" in str(exc).lower():
            pytest.skip("Tesseract not installed")
        raise


def test_normal_pdf_ignores_ocr():
    """Test normal PDFs don't trigger OCR when text is present."""
    sample_normal = FIXTURES_DIR / "normal.pdf"
    
    if not sample_normal.exists():
        pytest.skip("Normal PDF fixture not found")
    
    # Parse without OCR
    text_no_ocr = parse_pdf(str(sample_normal), enable_ocr=False)
    
    # Parse with OCR (should still use text extraction)
    text_with_ocr = parse_pdf(str(sample_normal), enable_ocr=True)
    
    # Should be identical (OCR not triggered if text exists)
    assert text_no_ocr == text_with_ocr


def test_parse_file_routing_gaeb():
    """Test parse_file() routes GAEB files correctly."""
    sample_gaeb = FIXTURES_DIR / "sample.x85"
    
    if not sample_gaeb.exists():
        pytest.skip("GAEB sample not found")
    
    # Should auto-detect as gaeb type and route to parse_gaeb
    text = parse_file(str(sample_gaeb))
    assert len(text) > 0


def test_parse_file_routing_pdf_with_ocr():
    """Test parse_file() routes PDFs with OCR enabled."""
    sample_pdf = FIXTURES_DIR / "document.pdf"
    
    if not sample_pdf.exists():
        pytest.skip("PDF sample not found")
    
    # Should route to parse_pdf with OCR settings
    text = parse_file(str(sample_pdf), enable_ocr=True, ocr_max_pages=10)
    assert isinstance(text, str)


if __name__ == "__main__":
    # Manual test runner
    print("Running GAEB/OCR parser tests...")
    print("\nNote: Create test fixtures in workers/tests/fixtures/:")
    print("  - sample.x83, sample.x84, sample.x85 (GAEB files)")
    print("  - scanned.pdf (scanned PDF with no text)")
    print("  - normal.pdf (regular PDF with selectable text)")
    print("  - empty.x84 (empty GAEB file)")
    
    pytest.main([__file__, "-v"])
