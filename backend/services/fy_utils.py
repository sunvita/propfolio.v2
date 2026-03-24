from datetime import datetime
from typing import Optional


def get_fy(date: datetime | str) -> str:
    """Returns FY label (e.g. 'FY 2025-26') for any given date.

    Australian financial year runs Jul-Jun.
    """
    if isinstance(date, str):
        date = datetime.fromisoformat(date)

    year = date.year
    month = date.month

    if month >= 7:
        return f"FY {year}-{year + 1 - 2000:02d}"
    else:
        return f"FY {year - 1}-{year - 2000:02d}"


def get_fy_year_range(fy_label: str) -> tuple[int, int]:
    """Parse 'FY 2025-26' → (2025, 2026)"""
    parts = fy_label.replace("FY ", "").split("-")
    start_year = int(parts[0])
    end_year = int(parts[1])

    if end_year < 100:
        end_year += 2000

    return (start_year, end_year)


def get_fy_months(fy_start_year: int) -> list[tuple[str, int, int]]:
    """Returns list of (month_label, month_num, year) in reverse chronological order.

    For FY starting in 2025 (FY 2025-26):
    [("Jun-26", 6, 2026), ("May-26", 5, 2026), ..., ("Jul-25", 7, 2025)]
    """
    months = [
        ("Jul", 7), ("Aug", 8), ("Sep", 9), ("Oct", 10),
        ("Nov", 11), ("Dec", 12), ("Jan", 1), ("Feb", 2),
        ("Mar", 3), ("Apr", 4), ("May", 5), ("Jun", 6)
    ]

    result = []
    for month_name, month_num in months:
        year = fy_start_year if month_num >= 7 else fy_start_year + 1
        label = f"{month_name}-{str(year)[-2:]}"
        result.append((label, month_num, year))

    return list(reversed(result))


def get_fy_from_month(month_str: str) -> str:
    """Takes '2026-03' → 'FY 2025-26'"""
    parts = month_str.split("-")
    year = int(parts[0])
    month = int(parts[1])

    if month >= 7:
        return f"FY {year}-{year + 1 - 2000:02d}"
    else:
        return f"FY {year - 1}-{year - 2000:02d}"


def get_fy_list_from_transactions(transactions: list[dict]) -> list[str]:
    """Returns sorted list of unique FY labels from transactions (most recent first)"""
    fy_set = set()

    for tx in transactions:
        date = tx.get("date")
        if date:
            fy = get_fy(date)
            fy_set.add(fy)

    fy_list = sorted(fy_set, reverse=True)
    return fy_list


def get_cy_list_from_transactions(transactions: list[dict]) -> list[str]:
    """Returns sorted list of unique CY years (most recent first)"""
    cy_set = set()

    for tx in transactions:
        date = tx.get("date")
        if date:
            if isinstance(date, str):
                date = datetime.fromisoformat(date)
            cy_set.add(str(date.year))

    cy_list = sorted(cy_set, reverse=True)
    return cy_list
