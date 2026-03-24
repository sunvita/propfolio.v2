"""
Propfolio AU — FastAPI application entry point.

Run with:  uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from backend.config import UPLOADS_DIR, PARSED_DIR, OUTPUT_DIR, DATA_DIR
from backend.routes import properties, upload, transactions, reports

# Ensure directories exist
for d in [UPLOADS_DIR, PARSED_DIR, OUTPUT_DIR, DATA_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Propfolio AU",
    description="Australian property portfolio P&L management",
    version="0.1.0",
)

# CORS for Next.js frontend (dev: localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(properties.router)
app.include_router(upload.router)
app.include_router(transactions.router)
app.include_router(reports.router)


@app.get("/api/health")
async def health_check():
    import os
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    key_prefix = os.getenv("ANTHROPIC_API_KEY", "")[:7] if has_key else None
    return {
        "status": "ok",
        "app": "Propfolio AU",
        "version": "0.1.0",
        "anthropic_key_set": has_key,
        "key_prefix": key_prefix,
        "env_vercel": bool(os.getenv("VERCEL")),
    }


@app.get("/api/portfolio")
async def get_portfolio():
    """Return the full portfolio with all properties."""
    from backend.services.ledger import load_portfolio
    portfolio = load_portfolio()
    return portfolio.model_dump(mode="json")


@app.get("/api/portfolio/summary")
async def get_portfolio_summary():
    """Return aggregated portfolio KPIs and per-property P&L for current FY."""
    from datetime import datetime
    from backend.services.ledger import load_portfolio, aggregate_by_category_month
    from backend.services.fy_utils import get_fy, get_fy_year_range, get_fy_months
    from backend.config import (
        INCOME_ROWS, OPEX_ROWS, UTILITY_ROWS, FINANCING_ROWS, CAPITAL_ROWS,
    )

    portfolio = load_portfolio()
    current_fy = get_fy(datetime.now())
    start_yr, _ = get_fy_year_range(current_fy)
    months = get_fy_months(start_yr)

    total_asset_value = 0.0
    total_debt = 0.0
    property_summaries = []

    for prop in portfolio.properties:
        total_asset_value += prop.current_value or prop.purchase_price or 0
        total_debt += prop.mortgage_balance or 0

        agg = aggregate_by_category_month(prop.id)

        def _section_total(rows_dict):
            total = 0.0
            for cat_key in rows_dict:
                for _, m_num, yr in months:
                    mk = f"{yr}-{m_num:02d}"
                    val = agg.get((cat_key, mk), 0)
                    total += abs(val)
            return round(total, 2)

        income = _section_total(INCOME_ROWS)
        opex = _section_total(OPEX_ROWS)
        utilities = _section_total(UTILITY_ROWS)
        financing = _section_total(FINANCING_ROWS)
        depreciation = _section_total(CAPITAL_ROWS)
        noi = round(income - opex, 2)
        net_profit = round(noi - utilities - financing - depreciation, 2)

        property_summaries.append({
            "id": prop.id,
            "short_name": prop.short_name,
            "display_name": prop.display_name,
            "current_value": prop.current_value or prop.purchase_price or 0,
            "mortgage_balance": prop.mortgage_balance or 0,
            "income": income,
            "opex": opex,
            "noi": noi,
            "utilities": utilities,
            "financing": financing,
            "depreciation": depreciation,
            "net_profit": net_profit,
        })

    total_equity = total_asset_value - total_debt
    total_income = sum(p["income"] for p in property_summaries)
    total_expenses = sum(p["opex"] + p["utilities"] + p["financing"] + p["depreciation"] for p in property_summaries)
    total_net_profit = sum(p["net_profit"] for p in property_summaries)

    return {
        "fy": current_fy,
        "total_asset_value": round(total_asset_value, 2),
        "total_debt": round(total_debt, 2),
        "total_equity": round(total_equity, 2),
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "total_net_profit": round(total_net_profit, 2),
        "property_count": len(portfolio.properties),
        "properties": property_summaries,
    }


# Serve the test UI if available
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        index_path = _static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Propfolio AU API — visit /docs for Swagger UI"}
else:
    @app.get("/")
    async def root():
        return {"message": "Propfolio AU API — visit /docs for Swagger UI"}
