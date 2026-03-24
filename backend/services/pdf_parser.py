"""
PDF parsing service for Propfolio AU.

Fallback chain:
1. pdfplumber (best for utility bills, complex layouts, tables)
2. PyPDF2 (lightweight fallback)
3. pdftotext CLI (system utility)
4. Placeholder message
"""

import os
import subprocess
from pathlib import Path

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


def parse_pdf(file_path: str, output_dir: str) -> str:
    """
    Parse a PDF file and return its content as text/markdown.

    Falls through multiple backends until one succeeds.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    os.makedirs(output_dir, exist_ok=True)

    # 1. Try pdfplumber (best for complex layouts like utility bills)
    if HAS_PDFPLUMBER:
        try:
            return _parse_with_pdfplumber(file_path)
        except Exception as e:
            print(f"Warning: pdfplumber failed ({e})")

    # 2. Try PyPDF2 (lightweight fallback)
    if HAS_PYPDF2:
        try:
            return _parse_with_pypdf2(file_path)
        except Exception as e:
            print(f"Warning: PyPDF2 failed ({e})")

    # 3. Try pdftotext CLI
    try:
        return _parse_with_pdftotext(file_path)
    except Exception as e:
        print(f"Warning: pdftotext failed ({e})")

    # 4. Final fallback
    return (
        f"[Could not extract text from PDF: {os.path.basename(file_path)}]\n"
        "No PDF parser available. Please install pdfplumber or PyPDF2."
    )


def _parse_with_pdfplumber(file_path: str) -> str:
    """Extract text from PDF using pdfplumber — handles complex layouts, tables, utility bills."""
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(f"--- Page {i + 1} ---\n{text.strip()}")

            # Also extract tables if present
            tables = page.extract_tables()
            for ti, table in enumerate(tables):
                if table:
                    table_text = _format_table(table)
                    if table_text.strip():
                        pages.append(f"--- Page {i + 1} Table {ti + 1} ---\n{table_text}")

    if not pages:
        raise ValueError("pdfplumber extracted no text (possibly a scanned/image PDF)")
    return "\n\n".join(pages)


def _format_table(table: list) -> str:
    """Format a pdfplumber table as readable text."""
    rows = []
    for row in table:
        if row:
            cells = [str(cell).strip() if cell else "" for cell in row]
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _parse_with_pypdf2(file_path: str) -> str:
    """Extract text from PDF using PyPDF2 — lightweight, no system deps."""
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append(f"--- Page {i + 1} ---\n{text.strip()}")
    if not pages:
        raise ValueError("PyPDF2 extracted no text (possibly a scanned PDF)")
    return "\n\n".join(pages)


def _parse_with_pdftotext(file_path: str) -> str:
    result = subprocess.run(
        ["pdftotext", file_path, "-"],
        capture_output=True, text=True, check=True
    )
    return result.stdout
