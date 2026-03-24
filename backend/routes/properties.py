"""
Property CRUD routes.
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import PropertyCreate, Property
from backend.services.ledger import (
    add_property, get_property, list_properties, load_ledger,
)
from backend.services.fy_utils import get_fy
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


@router.get("/{prop_id}", response_model=Property)
async def get_property_detail(prop_id: str):
    """Get a single property by ID."""
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.get("/{prop_id}/summary")
async def get_property_summary(prop_id: str):
    """Return current-FY P&L summary and gearing status for a property."""
    from datetime import datetime
    from backend.services.ledger import aggregate_by_category_month
    from backend.config import (
        INCOME_ROWS, OPEX_ROWS, UTILITY_ROWS, FINANCING_ROWS, CAPITAL_ROWS,
    )

    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    agg = aggregate_by_category_month(prop_id)
    current_fy = get_fy(datetime.now())

    # Sum by section for current FY
    def _section_total(rows_dict: dict, agg: dict, fy: str) -> float:
        from backend.services.fy_utils import get_fy_year_range, get_fy_months
        start_yr, _ = get_fy_year_range(fy)
        months = get_fy_months(start_yr)
        total = 0.0
        for cat_key in rows_dict:
            for _, m_num, yr in months:
                mk = f"{yr}-{m_num:02d}"
                val = agg.get((cat_key, mk), 0)
                total += abs(val)
        return total

    income = _section_total(INCOME_ROWS, agg, current_fy)
    opex = _section_total(OPEX_ROWS, agg, current_fy)
    utilities = _section_total(UTILITY_ROWS, agg, current_fy)
    financing = _section_total(FINANCING_ROWS, agg, current_fy)
    depreciation = _section_total(CAPITAL_ROWS, agg, current_fy)

    noi = income - opex
    net_profit = noi - utilities - financing - depreciation

    if net_profit > 0:
        gearing = "Positively Geared"
        gearing_detail = f"In the Money by ${net_profit:,.2f}"
    elif net_profit < 0:
        gearing = "Negatively Geared"
        gearing_detail = f"Out of Pocket by ${abs(net_profit):,.2f}"
    else:
        gearing = "Neutral"
        gearing_detail = "Break Even"

    return {
        "property": prop,
        "fy": current_fy,
        "income": income,
        "opex": opex,
        "noi": noi,
        "utilities": utilities,
        "financing": financing,
        "depreciation": depreciation,
        "net_profit": net_profit,
        "gearing": gearing,
        "gearing_detail": gearing_detail,
    }
