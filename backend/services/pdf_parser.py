"""
PDF parsing service for Propfolio AU.

Wraps opendataloader-pdf for converting PDFs to markdown.
Falls back to pdftotext or placeholder message if dependencies unavailable.
"""

import os
import subprocess
from pathlib import Path

try:
    import opendataloader_pdf
    HAS_OPENDATALOADER = True
except ImportError:
    HAS_OPENDATALOADER = False


def parse_pdf(file_path: str, output_dir: str) -> str:
    """
    Parse a PDF file and return its content as markdown.

    Args:
        file_path: Path to the PDF file to parse
        output_dir: Directory where the markdown output will be saved

    Returns:
        Markdown content as a string. Returns placeholder message if no parser available.

    Raises:
        FileNotFoundError: If the input PDF file does not exist
        OSError: If output directory cannot be created or accessed
    """
    # Validate input file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Try opendataloader_pdf first
    if HAS_OPENDATALOADER:
        try:
            return _parse_with_opendataloader(file_path, output_dir)
        except Exception as e:
            print(f"Warning: opendataloader_pdf failed ({e}), trying pdftotext...")

    # Fall back to pdftotext
    try:
        return _parse_with_pdftotext(file_path)
    except Exception as e:
        print(f"Warning: pdftotext failed ({e})")

    # Final fallback: placeholder message
    return (
        "opendataloader-pdf not installed — paste PDF text manually\n\n"
        f"File: {os.path.basename(file_path)}\n"
        "Please extract the PDF content and paste it here for classification."
    )


def _parse_with_opendataloader(file_path: str, output_dir: str) -> str:
    """
    Parse PDF using opendataloader_pdf library.

    Args:
        file_path: Path to the PDF file
        output_dir: Directory for output files

    Returns:
        Markdown content as a string
    """
    # Convert PDF to markdown
    opendataloader_pdf.convert(
        input_path=[file_path],
        output_dir=output_dir,
        format="markdown"
    )

    # Generate expected markdown filename from input
    pdf_name = Path(file_path).stem
    md_file = os.path.join(output_dir, f"{pdf_name}.md")

    # Read the generated markdown file
    if not os.path.isfile(md_file):
        raise FileNotFoundError(f"Markdown output not generated: {md_file}")

    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    return content


def _parse_with_pdftotext(file_path: str) -> str:
    """
    Parse PDF using system pdftotext utility.

    Args:
        file_path: Path to the PDF file

    Returns:
        Text content extracted from PDF
    """
    result = subprocess.run(
        ["pdftotext", file_path, "-"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout
