"""
LLM classification service for Propfolio AU.

Uses Anthropic Claude API to classify property-related transactions
and expenses from PDF documents into standardized categories.
"""

import json
import os
import re
from typing import Optional

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


def classify_pdf_content(
    property_display_name: str,
    property_address: str,
    filename: str,
    content: str
) -> list[dict]:
    """
    Classify transaction/expense data from PDF content using Claude API.

    Args:
        property_display_name: Display name of the property
        property_address: Full address of the property
        filename: Original filename of the PDF
        content: Text or markdown content extracted from PDF

    Returns:
        List of classification dictionaries with keys:
        - date: Transaction date (YYYY-MM-DD format if available)
        - month: Month in YYYY-MM format if date not available
        - category: Category key (e.g., "rental_income", "mortgage_interest")
        - description: Brief description of the transaction
        - amount: Transaction amount (numeric or string)
        - type: "income", "expense", or "cash_flow"
        - confidence: Confidence level ("high", "medium", "low")

    Raises:
        ValueError: If ANTHROPIC_API_KEY environment variable not set
    """
    if not HAS_ANTHROPIC:
        return _handle_missing_anthropic()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it to use the LLM classifier."
        )

    # Build the classification prompt
    prompt = build_classification_prompt(
        property_display_name,
        property_address,
        filename,
        content
    )

    # Call Claude API
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # Extract response text
    response_text = message.content[0].text

    # Parse JSON from response
    classifications = _parse_json_response(response_text)

    return classifications


def build_classification_prompt(
    property_display_name: str,
    property_address: str,
    filename: str,
    content: str
) -> str:
    """
    Build the complete classification prompt for Claude.

    Args:
        property_display_name: Display name of the property
        property_address: Full address of the property
        filename: Original filename of the PDF
        content: Extracted PDF content

    Returns:
        Formatted prompt string with all context and instructions
    """
    prompt = f"""You are an expert Australian property investment accountant.
Your task is to classify transactions and expenses from a property document.

PROPERTY DETAILS:
- Name: {property_display_name}
- Address: {property_address}
- Document: {filename}

DOCUMENT CONTENT:
{content}

---

CLASSIFICATION TASK:

Extract all financial transactions and expenses from the document above.
Classify each item into ONE of the following categories:

This system has TWO separate sections in the P&L:
  (A) P&L SECTION — accrual-basis items (income earned, expenses incurred)
  (B) CASH FLOW SECTION — actual cash movements (money in/out of bank account)

A single PDF may generate items for BOTH sections. Read the rules carefully.

═══════════════════════════════════════════════
SECTION A — P&L CATEGORIES (type: "income" or "expense")
═══════════════════════════════════════════════

INCOME (type = "income"):
- rental_income: Gross rent charged/earned for the period. Use the RENT AMOUNT, not the net EFT deposit.
- other_income: Other property-related income (parking fees, laundry, etc.)
- excess_bill_shares: Recovery of excess utility costs from tenants

OPERATING EXPENSES (type = "expense"):
- management_fees: Property management fees (percentage of rent collected)
- letting_fees: Letting/leasing agent fees (one-off for finding a tenant)
- council_rates: Council/local government rates
- land_tax: Land tax / payroll tax
- strata: Strata/body corporate fees (apartments/units)
- building_insurance: Building and contents insurance
- maintenance_repairs: Repairs and maintenance
- cleaning: Cleaning and housekeeping
- advertising: Advertising for tenants
- miscellaneous: Other operating expenses
- furnishing_costs: Furnishings and minor fixtures (if deductible)

UTILITIES (type = "expense"):
- electricity: Electricity costs
- water: Water and sewerage
- gas: Gas costs
- internet: Internet and phone

FINANCING (type = "expense"):
- mortgage_interest: Mortgage interest portion ONLY (not principal)
- bank_package_fee: Bank package fees
- bank_service_fee: Bank service fees

CAPITAL ALLOWANCES (type = "expense"):
- depreciation: Depreciation (Div 40 — Plant & Equipment)
- capital_works: Capital Works deduction (Div 43 — Building)

═══════════════════════════════════════════════
SECTION B — CASH FLOW CATEGORIES (type: "cash_flow")
═══════════════════════════════════════════════

All cash flow items MUST use type = "cash_flow":
- cash_received: Net cash deposited into owner's bank account (EFT from PM)
- utilities_paid: Actual cash paid for utility bills
- mortgage_repayment: Total mortgage repayment (principal + interest combined)
- principal_repaid: Principal portion of mortgage repayment
- capex: Capital expenditure (major improvements, replacements)

═══════════════════════════════════════════════
DOCUMENT-SPECIFIC RULES
═══════════════════════════════════════════════

PROPERTY MANAGEMENT (PM) STATEMENTS:
A PM statement typically shows rent collected, fees deducted, and net EFT paid to owner.
Extract BOTH P&L and Cash Flow items:
  → rental_income (type:"income") = GROSS rent collected (before PM fees)
  → management_fees (type:"expense") = PM fee amount
  → letting_fees (type:"expense") = if a letting/leasing fee is shown
  → cash_received (type:"cash_flow") = NET EFT deposit to owner's account
  → maintenance, repairs, cleaning etc. = their respective EXPENSE categories
WATER/UTILITIES ON PM STATEMENTS — READ CAREFULLY:
Water and utility charges on PM statements can be EITHER an expense OR income depending
on context. You MUST determine the direction from the statement layout:

(a) DEDUCTED from owner (reduces net payment) → This means the PM paid a water/utility
    bill on behalf of the owner. It is an EXPENSE to the owner.
    → water (type:"expense") — or electricity/gas as appropriate
    Clues: appears in "Disbursements", "Expenses", "Payments Out", "Deductions" section;
    listed alongside management fees and other costs; labelled "Water Rates", "Water Usage",
    "Water Corp invoice", or similar; reduces the net EFT to the owner.

(b) ADDED to owner (increases net payment) → This means the tenant reimbursed the owner
    for excess water/utility usage. It is INCOME to the owner.
    → excess_bill_shares (type:"income")
    Clues: appears in "Income", "Receipts", "Credits" section; labelled "Tenant water
    reimbursement", "Excess water recovery", "Water recovery from tenant", "Water
    contribution"; increases the net EFT to the owner.

If unclear, look at whether the amount INCREASES or DECREASES the net payment to owner.
Standalone water authority bills (Water Corporation, Sydney Water, etc.) are always
water (type:"expense").
IMPORTANT: Use the STATEMENT PERIOD date for rental_income and expenses.
Use the PAYMENT/EFT date for cash_received.
Do NOT create cash_received from the rent amount — only from actual EFT/payment lines.

UTILITY BILLS (electricity, water, gas, internet):
Extract BOTH a P&L expense AND a cash flow payment:
  → electricity/water/gas/internet (type:"expense") = the bill total (incl GST)
  → utilities_paid (type:"cash_flow") = same amount (the cash outflow)
Use the bill date or due date for both entries.
The bill total should be the final "Total" or "Amount Due" including GST.

MORTGAGE / LOAN STATEMENTS:
  → mortgage_interest (type:"expense") = interest portion only
  → mortgage_repayment (type:"cash_flow") = total repayment (principal + interest)
  → principal_repaid (type:"cash_flow") = principal portion
If the document shows total repayment and interest but NOT the principal explicitly,
calculate it: principal_repaid = mortgage_repayment − mortgage_interest.
Always emit all three items for each period where mortgage data is available.

QS / DEPRECIATION SCHEDULES:
  → depreciation (type:"expense") = Div 40 plant & equipment total
  → capital_works (type:"expense") = Div 43 building deduction total

═══════════════════════════════════════════════
ANTI-DOUBLE-COUNTING RULES
═══════════════════════════════════════════════
- NEVER create rental_income from the EFT/deposit amount — use gross rent only
- NEVER create cash_received from the gross rent amount — use net EFT only
- If a PM statement shows both a line-by-line breakdown AND a summary total, use the summary
- If the same expense appears as both "incurred" and "paid by PM", extract only ONCE as the expense category
- Mortgage: split into mortgage_interest (P&L) + mortgage_repayment (cash flow), not both as expense

OUTPUT FORMAT:

Return a JSON array. Each object must have:
{{
  "date": "YYYY-MM-DD" or null if unavailable,
  "month": "YYYY-MM" or null if unavailable,
  "category": "one of the category keys above",
  "description": "Brief description",
  "amount": positive numeric value,
  "type": "income" or "expense" or "cash_flow",
  "confidence": "high" or "medium" or "low"
}}

RULES:
- Amounts MUST be positive numbers (no negative signs).
- type MUST be "income" for income categories, "expense" for P&L expense categories, "cash_flow" for cash flow categories.
- Prefer YYYY-MM-DD date format. Use "month" (YYYY-MM) only if exact date unavailable.
- Return ONLY valid JSON (no markdown fences, no extra text).
- If no financial data found, return: []

Begin classification:
"""
    return prompt


def _parse_json_response(response_text: str) -> list[dict]:
    """
    Extract and parse JSON array from Claude's response.

    Args:
        response_text: Raw response text from Claude API

    Returns:
        List of classification dictionaries

    Raises:
        ValueError: If no valid JSON array can be extracted
    """
    # Try to parse the entire response as JSON first
    try:
        result = json.loads(response_text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the response
    json_match = re.search(r'\[[\s\S]*\]', response_text)
    if json_match:
        try:
            result = json.loads(json_match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # If still no valid JSON, raise error with helpful message
    raise ValueError(
        f"Could not parse JSON from Claude response. "
        f"Response: {response_text[:500]}"
    )


def _handle_missing_anthropic() -> list[dict]:
    """
    Handle case where anthropic SDK is not installed.

    Returns:
        Empty list with explanatory message
    """
    print(
        "Warning: anthropic SDK not installed. "
        "Install with: pip install anthropic"
    )
    return []
