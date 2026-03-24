"""
Report generation routes.
"""

from typing import Optional
from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.services.excel_generator import generate_workbook
from backend.services.ledger import list_properties

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
async def generate_report(
    property_ids: Optional[list[str]] = None,
    filename: Optional[str] = None,
):
    """
    Generate an Excel P&L workbook.

    Body:
      - property_ids: List of property IDs to include. Omit for all.
      - filename: Custom filename (optional).

    Returns the generated .xlsx file as a download.
    """
    path = generate_workbook(
        property_ids=property_ids,
        output_filename=filename,
    )
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.split("/")[-1],
    )


@router.get("/generate")
async def generate_report_get():
    """
    Quick-generate: GET endpoint that generates for all properties.
    Useful for testing via browser.
    """
    path = generate_workbook()
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.split("/")[-1],
    )
