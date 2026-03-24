"""
Propfolio AU — Core configuration.
Categories, row map, color palette, column layout constants.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
PARSED_DIR = BASE_DIR / "parsed"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"

FY_START_MONTH = 7  # July

# ── P&L Row Map (fixed rows in every IP# sheet) ─────────────────────
# Maps category_key → (row_number, display_name, section, is_total)

INCOME_ROWS = {
    "rental_income":       (6,  "Rental Income"),
    "other_income":        (7,  "Other Income"),
    "excess_bill_shares":  (8,  "Excess Bill Shares"),
}
INCOME_TOTAL_ROW = 9  # "Total Income"

OPEX_ROWS = {
    "management_fees":     (12, "Management Fees"),
    "letting_fees":        (13, "Letting Fees"),
    "council_rates":       (14, "Council Rates"),
    "land_tax":            (15, "Land Tax"),
    "strata":              (16, "Strata / Body Corporate"),
    "building_insurance":  (17, "Building Insurance"),
    "maintenance_repairs": (18, "Maintenance & Repairs"),
    "cleaning":            (19, "Cleaning"),
    "advertising":         (20, "Advertising"),
    "miscellaneous":       (21, "Miscellaneous"),
    "furnishing_costs":    (22, "Furnishing Costs"),
}
OPEX_TOTAL_ROW = 23  # "Total Operating Expenses"

NOI_ROW = 25           # "NOI (Net Operating Income)"
NOI_MARGIN_ROW = 26    # "NOI Margin %"

UTILITY_ROWS = {
    "electricity": (29, "Electricity"),
    "water":       (30, "Water"),
    "gas":         (31, "Gas"),
    "internet":    (32, "Internet"),
}
UTILITY_TOTAL_ROW = 33  # "Total Utilities"

FINANCING_ROWS = {
    "mortgage_interest":  (36, "Mortgage Interest"),
    "bank_package_fee":   (37, "Bank Package Fee"),
    "bank_service_fee":   (38, "Bank Service Fee"),
}
FINANCING_TOTAL_ROW = 39  # "Total Financing Cost"

CAPITAL_ROWS = {
    "depreciation":   (42, "Depreciation (Div 40 — Plant & Equipment)"),
    "capital_works":  (43, "Capital Works (Div 43 — Building)"),
}
CAPITAL_TOTAL_ROW = 44  # "Total Capital Allowances"

# Shift rows 45+ down by 1 to accommodate capital_works row
NET_PROFIT_ROW = 46     # "NET PROFIT / (LOSS)"

CASHFLOW_ROWS = {
    "cash_received":      (49, "Cash Received (EFT)"),
    "utilities_paid":     (50, "Less: Utilities Paid"),
    "mortgage_repayment": (51, "Less: Mortgage Repayment"),
    "capex":              (52, "Less: Capital Expenditure"),
}
NET_CASHFLOW_ROW = 53   # "Net Cash Flow"
PRINCIPAL_ROW = 54      # "Principal Repaid"

KPI_HEADER_ROW = 57
KPI_START_ROW = 58

# Section header rows
SECTION_HEADERS = {
    5:  "INCOME",
    11: "OPERATING EXPENSES",
    28: "UTILITIES",
    35: "FINANCING",
    41: "CAPITAL ALLOWANCES",
    48: "CASH FLOW",
}

# ── Category → Row lookup (flat) ────────────────────────────────────
CATEGORY_ROW_MAP = {}
for d in [INCOME_ROWS, OPEX_ROWS, UTILITY_ROWS, FINANCING_ROWS, CAPITAL_ROWS, CASHFLOW_ROWS]:
    for key, (row, _) in d.items():
        CATEGORY_ROW_MAP[key] = row

# All valid category keys
ALL_CATEGORIES = list(CATEGORY_ROW_MAP.keys())

# ── Color Palette (RGB hex without #) ───────────────────────────────
COLORS = {
    "title_bg":          "1F3864",
    "title_font":        "FFFFFF",
    "legend_bg":         "F8F8F8",
    "legend_font":       "595959",
    "header_bg":         "1F3864",
    "header_font":       "FFFFFF",
    "fy_total_bg":       "D0D0D0",
    "active_fy_bg":      "FFFDE7",
    "inactive_bg":       "E0E0E0",
    "inactive_font":     "757575",
    "no_data_bg":        "F5F5F5",
    "section_bg":        "2F5496",
    "section_font":      "FFFFFF",
    "income_bg":         "EBF5EB",
    "income_font":       "1B5E20",
    "income_total_bg":   "C8E6C9",
    "expense_bg":        "FFF5F5",
    "expense_font":      "B71C1C",
    "expense_total_bg":  "FFCDD2",
    "noi_bg":            "EBF3FB",
    "noi_font":          "1A237E",
    "cashflow_bg":       "F3E5F5",
    "cashflow_font":     "4A148C",
    "cashflow_total_bg": "E1BEE7",
    "kpi_bg":            "F5F7FA",
    "kpi_alt_bg":        "FFFFFF",
}

# ── Number Formats ──────────────────────────────────────────────────
NUM_FMT_CURRENCY = '$#,##0.00;($#,##0.00);"-"'
NUM_FMT_PERCENT = '0.0%;(0.0%);"-"'
NUM_FMT_RATIO = '0.00;(0.00);"-"'

# ── Column Layout Constants ─────────────────────────────────────────
FY_BLOCK_WIDTH = 13  # 1 total col + 12 month cols per FY
MONTHS_IN_FY = [
    "Jun", "May", "Apr", "Mar", "Feb", "Jan",
    "Dec", "Nov", "Oct", "Sep", "Aug", "Jul"
]  # Reverse chronological within each FY block
