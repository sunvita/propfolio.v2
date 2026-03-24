"""
Property CRUD routes.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.models.schemas import PropertyCreate, PropertyUpdate, Property
from backend.services.ledger import (
    add_property, get_property, list_properties, load_ledger, update_property,
)
from backend.services.fy_utils import get_fy, get_fy_list_from_transactions
from backend.services.excel_generator import generate_workbook

router = APIRouter(prefix="/api/properties", tags=["properties"])


@router.get("/", response_model=list[Property])
async def get_all_properties():
    """List all properties in the portfolio."""
    return list_properties()


@router.post("/", response_model=Property)
async def create_property(data: PropertyCreate):
    """Create a new property and initialise an empty ledger."""
    return add_property(data)


@router.put("/{prop_id}", response_model=Property)
async def update_property_detail(prop_id: str, data: PropertyUpdate):
    """Update an existing property's details."""
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = update_property(prop_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Property not found")
    return updated


@router.get("/{prop_id}", response_model=Property)
async def get_property_detail(prop_id: str):
    """Get a single property by ID."""
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.get("/{prop_id}/fy-list")
async def get_property_fy_list(prop_id: str):
    """Return list of FYs that have transaction data for this property."""
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    ledger = load_ledger(prop_id)
    txs = [{"date": tx.date} for tx in ledger.transactions]
    return get_fy_list_from_transactions(txs)


@router.get("/{prop_id}/summary")
async def get_property_summary(prop_id: str, fy: Optional[str] = Query(None, description="FY label e.g. 'FY 2024-25'. Defaults to current FY.")):
    """Return P&L summary and gearing status for a property, optionally filtered by FY."""
    from datetime import datetime
    from backend.services.ledger import aggregate_by_category_month
    from backend.config import (
        INCOME_ROWS, OPEX_ROWS, UTILITY_ROWS, FINANCING_ROWS, CAPITAL_ROWS,
        CASHFLOW_ROWS, PRINCIPAL_ROWS,
    )
    from backend.services.fy_utils import get_fy_year_range, get_fy_months

    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    agg = aggregate_by_category_month(prop_id)
    selected_fy = fy or get_fy(datetime.now())
    start_yr, _ = get_fy_year_range(selected_fy)
    months = get_fy_months(start_yr)

    # Sum per-category for current FY
    def _category_totals(rows_dict: dict) -> dict[str, float]:
        totals = {}
        for cat_key in rows_dict:
            cat_total = 0.0
            for _, m_num, yr in months:
                mk = f"{yr}-{m_num:02d}"
                val = agg.get((cat_key, mk), 0)
                cat_total += abs(val)
            if cat_total > 0:
                totals[cat_key] = round(cat_total, 2)
        return totals

    income_breakdown = _category_totals(INCOME_ROWS)
    opex_breakdown = _category_totals(OPEX_ROWS)
    utility_breakdown = _category_totals(UTILITY_ROWS)
    financing_breakdown = _category_totals(FINANCING_ROWS)
    capital_breakdown = _category_totals(CAPITAL_ROWS)
    cashflow_breakdown = _category_totals(CASHFLOW_ROWS)

    income = round(sum(income_breakdown.values()), 2)
    opex = round(sum(opex_breakdown.values()), 2)
    utilities = round(sum(utility_breakdown.values()), 2)
    financing = round(sum(financing_breakdown.values()), 2)
    depreciation = round(sum(capital_breakdown.values()), 2)

    noi = round(income - opex, 2)
    net_profit = round(noi - utilities - financing - depreciation, 2)

    if net_profit > 0:
        gearing = "Positively Geared"
        gearing_detail = f"In the Money by ${net_profit:,.2f}"
    elif net_profit < 0:
        gearing = "Negatively Geared"
        gearing_detail = f"Out of Pocket by ${abs(net_profit):,.2f}"
    else:
        gearing = "Neutral"
        gearing_detail = "Break Even"

    principal_breakdown = _category_totals(PRINCIPAL_ROWS)

    # Category display name lookup
    all_rows = {**INCOME_ROWS, **OPEX_ROWS, **UTILITY_ROWS, **FINANCING_ROWS,
                **CAPITAL_ROWS, **CASHFLOW_ROWS, **PRINCIPAL_ROWS}
    def _with_labels(breakdown: dict) -> list[dict]:
        return [
            {"key": k, "label": all_rows.get(k, (0, k))[1], "amount": v}
            for k, v in breakdown.items()
        ]

    # Combine cashflow + principal for the full cash flow display
    full_cashflow = {**cashflow_breakdown, **principal_breakdown}

    return {
        "property": prop,
        "fy": selected_fy,
        "income": income,
        "income_breakdown": _with_labels(income_breakdown),
        "opex": opex,
        "opex_breakdown": _with_labels(opex_breakdown),
        "noi": noi,
        "utilities": utilities,
        "utility_breakdown": _with_labels(utility_breakdown),
        "financing": financing,
        "financing_breakdown": _with_labels(financing_breakdown),
        "depreciation": depreciation,
        "capital_breakdown": _with_labels(capital_breakdown),
        "net_profit": net_profit,
        "gearing": gearing,
        "gearing_detail": gearing_detail,
        "cashflow_breakdown": _with_labels(full_cashflow),
        "principal_repaid": round(sum(principal_breakdown.values()), 2),
    }
