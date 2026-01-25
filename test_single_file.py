#!/usr/bin/env python
"""
Test harness for processing a single file through the worker pipeline.
Usage: python test_single_file.py path/to/file.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add workers to Python path
sys.path.insert(0, str(Path(__file__).parent / "workers"))

from workers.config import load_config
from workers.processing.parsers import parse_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_single_file.py path/to/file.ext")
        print("\nSupported file types:")
        print("  - PDF (.pdf) - with optional OCR for scanned documents")
        print("  - GAEB (.x83, .x84, .x85, .x86, .d83, .d84, .d85, .d86, .p83-p86, .gaeb)")
        print("  - Word (.doc, .docx)")
        print("  - Excel (.xls, .xlsx)")
        print("  - CSV (.csv)")
        print("  - Text (.txt)")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Testing file: {file_path}")
    print(f"{'='*60}\n")
    
    try:
        config = load_config()
        print(f"Config loaded:")
        print(f"  - ENABLE_OCR: {config.enable_ocr}")
        print(f"  - OCR_MAX_PAGES: {config.ocr_max_pages}")
        print(f"  - GAEB_ENABLED: {config.gaeb_enabled}")
        print()
        
        print("Parsing file...")
        text = parse_file(
            file_path,
            enable_ocr=config.enable_ocr,
            ocr_max_pages=config.ocr_max_pages
        )
        
        print(f"\n{'='*60}")
        print(f"SUCCESS")
        print(f"{'='*60}")
        print(f"Extracted {len(text)} characters")
        print(f"\nFirst 500 characters:")
        print("-" * 60)
        print(text[:500])
        print("-" * 60)
        
        if len(text) > 500:
            print(f"\n... ({len(text) - 500} more characters)")
        
        print(f"\nFile can be processed successfully!")
        
    except Exception as exc:
        print(f"\n{'='*60}")
        print(f"FAILED")
        print(f"{'='*60}")
        print(f"Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
