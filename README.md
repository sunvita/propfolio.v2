# Propfolio AU

Australian property portfolio P&L management app. Upload financial PDFs (PM statements, utility bills, mortgage statements, QS depreciation schedules), classify transactions via Claude LLM, and generate professionally formatted Excel P&L workbooks matching Australian FY (Jul-Jun) conventions.

## Quick Start

```bash
# 1. Clone and install
cd propfolio-au
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Anthropic API key

# 3. Run the backend
uvicorn backend.main:app --reload --port 8000

# 4. Open in browser
# Test console: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
```

## Architecture

```
Frontend (Next.js)  ←→  Backend (FastAPI)
                          ├── PDF Parser (opendataloader-pdf)
                          ├── LLM Classifier (Claude API)
                          ├── Excel Generator (openpyxl)
                          └── JSON Data Store
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/portfolio` | Full portfolio |
| GET | `/api/properties/` | List properties |
| POST | `/api/properties/` | Create property |
| GET | `/api/properties/{id}` | Property detail |
| GET | `/api/properties/{id}/summary` | P&L summary + gearing |
| POST | `/api/upload/{id}` | Upload PDF → parse → classify |
| GET | `/api/upload/pending/{id}` | Review pending items |
| POST | `/api/upload/confirm/{id}` | Confirm pending → ledger |
| DELETE | `/api/upload/pending/{id}` | Discard pending |
| GET/POST | `/api/reports/generate` | Generate Excel workbook |
| GET | `/api/transactions/{id}` | List transactions |
| POST | `/api/transactions/{id}` | Add manual transaction |
| DELETE | `/api/transactions/{id}/{tx_id}` | Delete transaction |

## P&L Structure

Income → Operating Expenses → NOI → Utilities → Financing → Capital Allowances → Net Profit → Cash Flow

- **Positively Geared** (Net Profit > 0): "In the Money by $X,XXX.XX"
- **Negatively Geared** (Net Profit < 0): "Out of Pocket by $X,XXX.XX"

## Excel Output

Each property gets an `IP#` sheet with 13-column FY blocks (FY Total + 12 months in reverse-chrono), plus CY aggregation columns and a KPI section. A Summary sheet links to all property sheets with cross-sheet formulas.

## Project Structure

```
propfolio-au/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py             # Row maps, colors, constants
│   ├── models/
│   │   └── schemas.py        # Pydantic models
│   ├── routes/
│   │   ├── properties.py     # Property CRUD
│   │   ├── upload.py          # PDF upload pipeline
│   │   ├── transactions.py    # Transaction CRUD
│   │   └── reports.py         # Excel generation
│   └── services/
│       ├── fy_utils.py        # Australian FY helpers
│       ├── ledger.py          # JSON ledger ops
│       ├── pdf_parser.py      # PDF → markdown
│       ├── llm_classifier.py  # Claude classification
│       └── excel_generator.py # openpyxl workbook builder
├── static/
│   └── index.html            # Test console
├── data/                     # JSON ledger files
├── uploads/                  # Uploaded PDFs
├── parsed/                   # Parsed PDF output
├── output/                   # Generated Excel files
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Tech Stack

- **Backend**: FastAPI + Python 3.11+
- **PDF Parsing**: opendataloader-pdf (hybrid mode)
- **Classification**: Claude API (Anthropic)
- **Excel**: openpyxl
- **Data Store**: JSON files
- **Frontend** (planned): Next.js + Tailwind CSS
