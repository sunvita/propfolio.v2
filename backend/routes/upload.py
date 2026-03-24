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

from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Form

from backend.config import UPLOADS_DIR, PARSED_DIR
from backend.models.schemas import Transaction
from backend.services.pdf_parser import parse_pdf
from backend.services.llm_classifier import classify_pdf_content
from backend.services.ledger import (
    get_property, save_pending, load_pending, delete_pending,
    append_transactions, load_ledger,
)
from backend.services.fy_utils import get_fy

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _ensure_principal_repaid(items: list[dict]) -> list[dict]:
    """
    Auto-calculate principal_repaid if mortgage_repayment and mortgage_interest
    exist for a month but principal_repaid is missing.
    """
    # Group by month
    by_month: dict[str, dict] = {}
    for item in items:
        month = item.get("month") or (item.get("date", "")[:7] if item.get("date") else None)
        if not month:
            continue
        if month not in by_month:
            by_month[month] = {"repayment": None, "interest": None, "has_principal": False}
        cat = item.get("category", "")
        if cat == "mortgage_repayment":
            try:
                by_month[month]["repayment"] = abs(float(str(item.get("amount", 0)).replace(",", "").replace("$", "")))
            except (ValueError, TypeError):
                pass
        elif cat == "mortgage_interest":
            try:
                by_month[month]["interest"] = abs(float(str(item.get("amount", 0)).replace(",", "").replace("$", "")))
            except (ValueError, TypeError):
                pass
        elif cat == "principal_repaid":
            by_month[month]["has_principal"] = True

    # Generate missing principal_repaid entries
    new_items = list(items)
    for month, data in by_month.items():
        if data["repayment"] is not None and data["interest"] is not None and not data["has_principal"]:
            principal = round(data["repayment"] - data["interest"], 2)
            if principal > 0:
                new_items.append({
                    "date": f"{month}-01",
                    "month": month,
                    "category": "principal_repaid",
                    "description": f"Principal repaid (calculated: repayment − interest)",
                    "amount": principal,
                    "type": "cash_flow",
                    "confidence": "high",
                })

    return new_items


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

    # 3b. Post-process: auto-calculate principal_repaid if missing
    classified_items = _ensure_principal_repaid(classified_items)

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

    # 5. Check for duplicates against existing ledger (same hash logic as append_transactions)
    import hashlib
    existing_ledger = load_ledger(prop_id)
    existing_hashes = set()
    for etx in existing_ledger.transactions:
        key = f"{etx.date}|{etx.category}|{etx.amount}|{etx.description[:50]}"
        existing_hashes.add(hashlib.sha256(key.encode()).hexdigest())

    items_out = []
    for t in transactions:
        item_dict = t.model_dump(mode="json")
        key = f"{t.date}|{t.category}|{t.amount}|{t.description[:50]}"
        tx_hash = hashlib.sha256(key.encode()).hexdigest()
        item_dict["is_duplicate"] = tx_hash in existing_hashes
        items_out.append(item_dict)

    # 6. Save as pending
    pending_id = save_pending(prop_id, file.filename, transactions)

    return {
        "pending_id": pending_id,
        "filename": file.filename,
        "items_count": len(transactions),
        "items": items_out,
    }


@router.post("/{prop_id}")
async def upload_pdfs(
    prop_id: str,
    files: List[UploadFile] = File(...),
    property_json: str = Form(None),
):
    """
    Upload one or more PDFs for a property.

    Accepts multiple files. Each is parsed, classified, and stored as
    a separate pending batch for review.

    On Vercel, different Lambda instances have isolated /tmp. If the property
    doesn't exist in this instance's /tmp, the frontend can pass property_json
    (a JSON string of the property object) to bootstrap it locally.
    """
    import json as _json
    from backend.services.ledger import load_portfolio, save_portfolio, save_ledger
    from backend.models.schemas import Ledger as LedgerModel, Property as PropertyModel

    prop = get_property(prop_id)
    if not prop and property_json:
        # Bootstrap property from frontend-supplied data into this Lambda's /tmp
        try:
            prop_data = _json.loads(property_json)
            prop_obj = PropertyModel.model_validate(prop_data)
            portfolio = load_portfolio()
            # Only add if not already there
            if not any(p.id == prop_id for p in portfolio.properties):
                portfolio.properties.append(prop_obj)
                save_portfolio(portfolio)
                save_ledger(prop_id, LedgerModel(transactions=[]))
            prop = prop_obj
        except Exception:
            pass  # Fall through to the 404 below

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


@router.post("/confirm-items/{prop_id}")
async def confirm_items(prop_id: str, payload: dict = Body(...)):
    """
    Confirm selected transaction items directly (no pending file dependency).

    Accepts: { "items": [ {transaction objects} ], "property_json": "{...}" (optional) }
    This bypasses /tmp file storage, fixing Vercel serverless where
    Lambda instances don't share /tmp.
    """
    import json as _json
    from backend.services.ledger import load_portfolio, save_portfolio, save_ledger
    from backend.models.schemas import Ledger as LedgerModel, Property as PropertyModel

    prop = get_property(prop_id)
    if not prop and payload.get("property_json"):
        try:
            prop_data = _json.loads(payload["property_json"]) if isinstance(payload["property_json"], str) else payload["property_json"]
            prop_obj = PropertyModel.model_validate(prop_data)
            portfolio = load_portfolio()
            if not any(p.id == prop_id for p in portfolio.properties):
                portfolio.properties.append(prop_obj)
                save_portfolio(portfolio)
                save_ledger(prop_id, LedgerModel(transactions=[]))
            prop = prop_obj
        except Exception:
            pass

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    raw_items = payload.get("items", [])
    if not raw_items:
        raise HTTPException(status_code=400, detail="No items provided")

    transactions = [Transaction.model_validate(item) for item in raw_items]
    result = append_transactions(prop_id, transactions)

    # Return full portfolio snapshot from THIS Lambda (which has the freshly-written data)
    # This avoids Vercel /tmp isolation where the portfolio endpoint hits a different Lambda
    from backend.services.ledger import load_portfolio, aggregate_by_category_month
    from backend.services.fy_utils import get_fy, get_fy_year_range, get_fy_months
    from backend.config import INCOME_ROWS, OPEX_ROWS, UTILITY_ROWS, FINANCING_ROWS, CAPITAL_ROWS
    from datetime import datetime as _dt

    portfolio = load_portfolio()
    selected_fy = get_fy(_dt.now())
    start_yr, _ = get_fy_year_range(selected_fy)
    months = get_fy_months(start_yr)
    fy_set = set()
    property_summaries = []
    total_asset_value = 0.0
    total_debt = 0.0

    for p in portfolio.properties:
        total_asset_value += p.current_value or p.purchase_price or 0
        total_debt += p.mortgage_balance or 0
        ledger = load_ledger(p.id)
        for tx in ledger.transactions:
            fy_set.add(get_fy(tx.date))
        agg = aggregate_by_category_month(p.id)
        def _sec(rows):
            t = 0.0
            for ck in rows:
                for _, mn, yr in months:
                    t += abs(agg.get((ck, f"{yr}-{mn:02d}"), 0))
            return round(t, 2)
        inc = _sec(INCOME_ROWS); opx = _sec(OPEX_ROWS); utl = _sec(UTILITY_ROWS)
        fin = _sec(FINANCING_ROWS); dep = _sec(CAPITAL_ROWS)
        noi = round(inc - opx, 2); np_ = round(noi - utl - fin - dep, 2)
        property_summaries.append({"id": p.id, "short_name": p.short_name,
            "display_name": p.display_name, "net_profit": np_})

    return {
        "status": "confirmed",
        "property_id": prop_id,
        "added": result["added"],
        "skipped": result["skipped"],
        "portfolio_snapshot": {
            "properties": [p.model_dump(mode="json") for p in portfolio.properties],
            "fy": selected_fy,
            "fy_list": sorted(fy_set, reverse=True),
            "total_asset_value": round(total_asset_value, 2),
            "total_debt": round(total_debt, 2),
            "total_equity": round(total_asset_value - total_debt, 2),
            "total_net_profit": round(sum(ps["net_profit"] for ps in property_summaries), 2),
            "property_count": len(portfolio.properties),
            "property_summaries": property_summaries,
        },
    }


@router.delete("/pending/{pending_id}")
async def discard_pending(pending_id: str):
    """Discard a pending upload."""
    data = load_pending(pending_id)
    if not data:
        # On Vercel, pending files may not exist across Lambda instances
        return {"status": "discarded", "pending_id": pending_id}

    delete_pending(pending_id)
    return {"status": "discarded", "pending_id": pending_id}
