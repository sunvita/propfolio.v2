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
        - type: "income" or "expense"
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

INCOME CATEGORIES:
- rental_income: Rental income received
- other_income: Other property-related income (e.g., parking fees, laundry)
- excess_bill_shares: Recovery of excess utility costs from tenants

OPERATING EXPENSES:
- management_fees: Property management fees
- letting_fees: Letting agent fees
- council_rates: Council/local rates
- land_tax: Land tax / payroll tax
- strata: Strata/body corporate fees (for apartments/units)
- building_insurance: Building and contents insurance
- maintenance_repairs: Repairs and maintenance
- cleaning: Cleaning and housekeeping
- advertising: Advertising for tenants
- miscellaneous: Other operating expenses
- furnishing_costs: Furnishings and minor fixtures (if deductible)

UTILITIES:
- electricity: Electricity costs
- water: Water and sewerage
- gas: Gas costs
- internet: Internet and phone

FINANCING:
- mortgage_interest: Mortgage interest (only interest, not principal)
- bank_package_fee: Bank package fees
- bank_service_fee: Bank service fees

CAPITAL ALLOWANCES & DEPRECIATION:
- depreciation: Depreciation on building/chattels (plant & equipment)
- capital_works: Capital works deduction (eligible structural improvements)

CASH FLOW TRACKING:
- cash_received: Cash received from tenants/other sources
- utilities_paid: Cash paid for utilities
- mortgage_repayment: Total mortgage repayment (principal + interest)
- principal_repaid: Principal amount repaid on mortgage
- capex: Capital expenditure (major improvements, replacements)

DEPRECIATION RULES & GUIDELINES:
1. EXPENSE vs CAPITALISE:
   - Items under AUD $300 → typically expense
   - Items over AUD $300 → typically capitalise (add to capital works or depreciation)
   - Building structural improvements → capital works deduction (straight line, generally)
   - Plant & equipment depreciation → use diminishing value method

2. QUANTITY SURVEYOR (QS) SCHEDULES:
   - If document references a QS depreciation schedule, extract line items
   - Use QS schedule amounts if available (authoritative)
   - Don't double-count: if QS schedule shows total, don't add individual items again

3. DON'T DOUBLE-COUNT:
   - If a document shows both individual expenses AND a management fee summary, use the summary
   - If there's both cash paid AND accrued/invoiced amounts, use paid amounts for cash flow
   - Mortgage: split into mortgage_interest (operating) and principal_repaid (capital)

OUTPUT FORMAT:

Return a JSON array of classification objects. Each object must have:
{{
  "date": "YYYY-MM-DD" or null if unavailable,
  "month": "YYYY-MM" or null if unavailable,
  "category": "one of the category keys above",
  "description": "Brief description of the transaction",
  "amount": numeric value or string if unclear,
  "type": "income" or "expense",
  "confidence": "high", "medium", or "low"
}}

NOTES:
- If a document date exists, prefer YYYY-MM-DD format. Use month only if date unavailable.
- Amount should be positive numeric value (don't include negative signs).
- Type should be "income" for INCOME categories, "expense" for all others.
- Use "low" confidence for ambiguous items or if text is unclear.
- Return ONLY valid JSON (no markdown, no extra text).
- If the document contains no financial data, return an empty array: []

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
