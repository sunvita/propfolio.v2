import json
import hashlib
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import Optional

from backend.config import DATA_DIR
from backend.models.schemas import Property, PropertyCreate, Transaction, Ledger, Portfolio
from backend.services.fy_utils import get_fy


def _ensure_data_dir():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def _sanitize_prop_id(prop_id: str) -> str:
    return prop_id.replace("#", "")


def load_portfolio() -> Portfolio:
    _ensure_data_dir()
    portfolio_path = Path(DATA_DIR) / "portfolio.json"

    if portfolio_path.exists():
        with open(portfolio_path, "r") as f:
            data = json.load(f)
            return Portfolio.model_validate(data)

    return Portfolio(properties=[])


def save_portfolio(portfolio: Portfolio):
    _ensure_data_dir()
    portfolio_path = Path(DATA_DIR) / "portfolio.json"
    with open(portfolio_path, "w") as f:
        json.dump(portfolio.model_dump(mode="json"), f, indent=2)


def add_property(data: PropertyCreate) -> Property:
    portfolio = load_portfolio()

    next_num = 1
    if portfolio.properties:
        max_num = max(
            int(p.id.replace("IP", ""))
            for p in portfolio.properties
            if p.id.startswith("IP")
        )
        next_num = max_num + 1

    prop_id = f"IP{next_num}"
    display_name = f"IP#{next_num} — {data.short_name}"

    property_obj = Property(
        id=prop_id,
        short_name=data.short_name,
        display_name=display_name,
        address=data.address,
        purchase_date=data.purchase_date,
        purchase_price=data.purchase_price,
        current_value=data.current_value,
        current_value_date=data.current_value_date,
        notes=data.notes or ""
    )

    portfolio.properties.append(property_obj)
    save_portfolio(portfolio)

    empty_ledger = Ledger(transactions=[])
    save_ledger(prop_id, empty_ledger)

    return property_obj


def update_property(prop_id: str, updates: dict) -> Optional[Property]:
    """Update an existing property's fields. Returns updated property or None if not found."""
    portfolio = load_portfolio()
    for i, prop in enumerate(portfolio.properties):
        if prop.id == prop_id:
            prop_dict = prop.model_dump()
            for key, value in updates.items():
                if value is not None and key in prop_dict:
                    prop_dict[key] = value
            # Rebuild display_name if short_name changed
            if "short_name" in updates and updates["short_name"] is not None:
                num = prop_id.replace("IP", "")
                prop_dict["display_name"] = f"IP#{num} — {updates['short_name']}"
            updated_prop = Property.model_validate(prop_dict)
            portfolio.properties[i] = updated_prop
            save_portfolio(portfolio)
            return updated_prop
    return None


def get_property(prop_id: str) -> Optional[Property]:
    portfolio = load_portfolio()
    for prop in portfolio.properties:
        if prop.id == prop_id:
            return prop
    return None


def list_properties() -> list[Property]:
    portfolio = load_portfolio()
    return portfolio.properties


def load_ledger(prop_id: str) -> Ledger:
    _ensure_data_dir()
    sanitized_id = _sanitize_prop_id(prop_id)
    ledger_path = Path(DATA_DIR) / f"{sanitized_id}_ledger.json"

    if ledger_path.exists():
        with open(ledger_path, "r") as f:
            data = json.load(f)
            return Ledger.model_validate(data)

    return Ledger(transactions=[])


def save_ledger(prop_id: str, ledger: Ledger):
    _ensure_data_dir()
    sanitized_id = _sanitize_prop_id(prop_id)
    ledger_path = Path(DATA_DIR) / f"{sanitized_id}_ledger.json"
    with open(ledger_path, "w") as f:
        json.dump(ledger.model_dump(mode="json"), f, indent=2)


def append_transactions(prop_id: str, transactions: list[Transaction]) -> dict:
    ledger = load_ledger(prop_id)

    existing_hashes = set()
    for tx in ledger.transactions:
        key = f"{tx.date}|{tx.category}|{tx.amount}|{tx.description[:50]}"
        existing_hashes.add(hashlib.sha256(key.encode()).hexdigest())

    added = 0
    skipped = 0

    for tx in transactions:
        key = f"{tx.date}|{tx.category}|{tx.amount}|{tx.description[:50]}"
        tx_hash = hashlib.sha256(key.encode()).hexdigest()

        if tx_hash not in existing_hashes:
            if not tx.id:
                tx.id = str(uuid4())
            ledger.transactions.append(tx)
            existing_hashes.add(tx_hash)
            added += 1
        else:
            skipped += 1

    save_ledger(prop_id, ledger)
    return {"added": added, "skipped": skipped}


def get_transactions(
    prop_id: str,
    fy: Optional[str] = None,
    month: Optional[str] = None
) -> list[Transaction]:
    ledger = load_ledger(prop_id)
    result = ledger.transactions

    if fy:
        result = [
            tx for tx in result
            if get_fy(tx.date) == fy
        ]

    if month:
        result = [
            tx for tx in result
            if tx.date.startswith(month)
        ]

    return result


def delete_transaction(prop_id: str, tx_id: str) -> bool:
    ledger = load_ledger(prop_id)

    original_count = len(ledger.transactions)
    ledger.transactions = [tx for tx in ledger.transactions if tx.id != tx_id]

    if len(ledger.transactions) < original_count:
        save_ledger(prop_id, ledger)
        return True

    return False


def aggregate_by_category_month(prop_id: str) -> dict[tuple[str, str], float]:
    ledger = load_ledger(prop_id)
    result = {}

    for tx in ledger.transactions:
        if isinstance(tx.date, str):
            month = tx.date[:7]
        else:
            month = tx.date.strftime("%Y-%m")
        key = (tx.category, month)

        amount = tx.amount
        if tx.type in ["expense", "cash_flow"]:
            amount = -amount

        result[key] = result.get(key, 0) + amount

    return result


def save_pending(prop_id: str, filename: str, items: list[Transaction]) -> str:
    _ensure_data_dir()
    pending_id = str(uuid4())
    pending_path = Path(DATA_DIR) / f"pending_{pending_id}.json"

    pending_data = {
        "prop_id": prop_id,
        "filename": filename,
        "created_at": datetime.utcnow().isoformat(),
        "items": [item.model_dump(mode="json") for item in items]
    }

    with open(pending_path, "w") as f:
        json.dump(pending_data, f, indent=2)

    return pending_id


def load_pending(pending_id: str) -> Optional[dict]:
    _ensure_data_dir()
    pending_path = Path(DATA_DIR) / f"pending_{pending_id}.json"

    if pending_path.exists():
        with open(pending_path, "r") as f:
            return json.load(f)

    return None


def delete_pending(pending_id: str):
    _ensure_data_dir()
    pending_path = Path(DATA_DIR) / f"pending_{pending_id}.json"
    if pending_path.exists():
        pending_path.unlink()
