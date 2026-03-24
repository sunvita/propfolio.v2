"""
PDF upload and classification routes.

Pipeline: Upload PDF → Parse → Classify → Review → Confirm
"""

import shutil
import traceback
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.config import UPLOADS_DIR, PARSED_DIR
from backend.models.schemas import Transaction
from backend.services.pdf_parser import parse_pdf
from backend.services.llm_classifier import classify_pdf_content
from backend.services.ledger import (
    get_property, save_pending, load_pending, delete_pending,
    append_transactions,
)
from backend.services.fy_utils import get_fy

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _process_single_pdf(prop, file: UploadFile) -> dict:
    """Process one PDF file through the parse → classify → pending pipeline."""
    prop_id = prop.id

    # 1. Save uploaded file
    upload_dir = Path(UPLOADS_DIR) / prop_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / file.filename
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2. Parse PDF
    parse_output_dir = str(Path(PARSED_DIR) / prop_id)
    content = parse_pdf(str(saved_path), parse_output_dir)

    # 3. Classify with LLM
    classified_items = classify_pdf_content(
        property_display_name=prop.display_name,
        property_address=prop.address,
        filename=file.filename,
        content=content,
    )

    # 4. Convert to Transaction objects
    transactions = []
    for item in classified_items:
        date_str = item.get("date")
        month_str = item.get("month")

        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                dt = datetime.now()
        elif month_str:
            try:
                dt = datetime.strptime(month_str + "-01", "%Y-%m-%d")
            except (ValueError, TypeError):
                dt = datetime.now()
        else:
            dt = datetime.now()

        amount = item.get("amount", 0)
        if isinstance(amount, str):
            try:
                amount = float(amount.replace(",", "").replace("$", ""))
            except ValueError:
                amount = 0

        confidence_map = {"high": 0.95, "medium": 0.7, "low": 0.4}
        conf = confidence_map.get(str(item.get("confidence", "medium")), 0.7)

        tx = Transaction(
            id=str(uuid4()),
            date=dt,
            month=dt.strftime("%Y-%m"),
            fy=get_fy(dt),
            category=item.get("category", "miscellaneous"),
            description=item.get("description", ""),
            amount=abs(float(amount)),
            type=item.get("type", "expense"),
            source_pdf=file.filename,
            confidence=conf,
        )
        transactions.append(tx)

    # 5. Save as pending
    pending_id = save_pending(prop_id, file.filename, transactions)

    return {
        "pending_id": pending_id,
        "filename": file.filename,
        "items_count": len(transactions),
        "items": [t.model_dump(mode="json") for t in transactions],
    }


@router.post("/{prop_id}")
async def upload_pdfs(prop_id: str, files: List[UploadFile] = File(...)):
    """
    Upload one or more PDFs for a property.

    Accepts multiple files. Each is parsed, classified, and stored as
    a separate pending batch for review.

    Returns a list of results, one per file.
    """
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    results = []
    errors = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename, "error": "Not a PDF file"})
            continue

        try:
            result = _process_single_pdf(prop, file)
            results.append(result)
        except Exception as e:
            print(f"Error processing {file.filename}: {traceback.format_exc()}")
            errors.append({"filename": file.filename, "error": str(e)})

    if not results and errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "All files failed to process",
                "errors": errors,
            }
        )

    return {
        "results": results,
        "errors": errors,
        "total_files": len(results) + len(errors),
        "successful": len(results),
        "failed": len(errors),
        # Backwards compat: if single file, also expose top-level fields
        **(results[0] if len(results) == 1 else {}),
    }


@router.get("/pending/{pending_id}")
async def get_pending(pending_id: str):
    """Retrieve a pending upload for review."""
    data = load_pending(pending_id)
    if not data:
        raise HTTPException(status_code=404, detail="Pending upload not found")
    return data


@router.post("/confirm/{pending_id}")
async def confirm_pending(pending_id: str):
    """Confirm a pending upload — move items to the property ledger."""
    data = load_pending(pending_id)
    if not data:
        raise HTTPException(status_code=404, detail="Pending upload not found")

    prop_id = data["prop_id"]
    items = [Transaction.model_validate(item) for item in data["items"]]

    result = append_transactions(prop_id, items)
    delete_pending(pending_id)

    return {
        "status": "confirmed",
        "property_id": prop_id,
        "added": result["added"],
        "skipped": result["skipped"],
    }


@router.post("/confirm-batch")
async def confirm_batch(pending_ids: List[str]):
    """Confirm multiple pending uploads at once."""
    total_added = 0
    total_skipped = 0
    confirmed = []

    for pid in pending_ids:
        data = load_pending(pid)
        if not data:
            continue
        items = [Transaction.model_validate(item) for item in data["items"]]
        result = append_transactions(data["prop_id"], items)
        delete_pending(pid)
        total_added += result["added"]
        total_skipped += result["skipped"]
        confirmed.append(pid)

    return {
        "status": "confirmed",
        "confirmed_count": len(confirmed),
        "added": total_added,
        "skipped": total_skipped,
    }


@router.delete("/pending/{pending_id}")
async def discard_pending(pending_id: str):
    """Discard a pending upload."""
    data = load_pending(pending_id)
    if not data:
        raise HTTPException(status_code=404, detail="Pending upload not found")

    delete_pending(pending_id)
    return {"status": "discarded", "pending_id": pending_id}
