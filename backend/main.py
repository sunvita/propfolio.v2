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
