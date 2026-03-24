"""
Transaction CRUD routes.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException

from backend.models.schemas import Transaction, TransactionCreate
from backend.services.ledger import (
    get_property, get_transactions, delete_transaction, load_ledger,
    save_ledger, append_transactions,
)
from backend.services.fy_utils import get_fy

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/{prop_id}")
async def list_transactions(
    prop_id: str,
    fy: Optional[str] = None,
    month: Optional[str] = None,
):
    """
    List transactions for a property, optionally filtered by FY or month.

    Query params:
      - fy: e.g. "FY 2025-26"
      - month: e.g. "2025-07"
    """
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    txs = get_transactions(prop_id, fy=fy, month=month)
    return [t.model_dump(mode="json") for t in txs]


@router.post("/{prop_id}")
async def add_manual_transaction(prop_id: str, data: TransactionCreate):
    """Add a single manually entered transaction to a property's ledger."""
    from uuid import uuid4
    from datetime import datetime

    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    tx = Transaction(
        id=str(uuid4()),
        date=data.date,
        month=data.date.strftime("%Y-%m"),
        fy=get_fy(data.date),
        category=data.category,
        description=data.description,
        amount=abs(data.amount),
        type=data.type,
        manually_verified=True,
    )

    result = append_transactions(prop_id, [tx])
    return {
        "status": "added",
        "transaction": tx.model_dump(mode="json"),
        "added": result["added"],
        "skipped": result["skipped"],
    }


@router.delete("/{prop_id}/{tx_id}")
async def remove_transaction(prop_id: str, tx_id: str):
    """Delete a transaction from a property's ledger."""
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    deleted = delete_transaction(prop_id, tx_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {"status": "deleted", "tx_id": tx_id}
