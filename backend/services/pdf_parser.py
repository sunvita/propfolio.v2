"""
PDF parsing service for Propfolio AU.

Fallback chain:
1. opendataloader-pdf (best quality, needs install)
2. PyPDF2 (lightweight, works on Vercel serverless)
3. pdftotext CLI (system utility)
4. Placeholder message
"""

import os
import subprocess
from pathlib import Path

try:
    import opendataloader_pdf
    HAS_OPENDATALOADER = True
except ImportError:
    HAS_OPENDATALOADER = False

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

    # 1. Try opendataloader_pdf
    if HAS_OPENDATALOADER:
        try:
            return _parse_with_opendataloader(file_path, output_dir)
        except Exception as e:
            print(f"Warning: opendataloader_pdf failed ({e})")

    # 2. Try PyPDF2 (lightweight, works on serverless)
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
        "No PDF parser available. Please install PyPDF2 or opendataloader-pdf."
    )


def _parse_with_opendataloader(file_path: str, output_dir: str) -> str:
    opendataloader_pdf.convert(
        input_path=[file_path],
        output_dir=output_dir,
        format="markdown"
    )
    pdf_name = Path(file_path).stem
    md_file = os.path.join(output_dir, f"{pdf_name}.md")
    if not os.path.isfile(md_file):
        raise FileNotFoundError(f"Markdown output not generated: {md_file}")
    with open(md_file, "r", encoding="utf-8") as f:
        return f.read()


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
