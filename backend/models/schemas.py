from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PropertyCreate(BaseModel):
    short_name: str
    address: str
    type: Literal["residential", "commercial", "industrial"] = "residential"
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    current_value: Optional[float] = None
    current_value_date: Optional[str] = None
    notes: str = ""


class PropertyUpdate(BaseModel):
    short_name: Optional[str] = None
    address: Optional[str] = None
    type: Optional[Literal["residential", "commercial", "industrial"]] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    current_value: Optional[float] = None
    current_value_date: Optional[str] = None
    mortgage_balance: Optional[float] = None
    notes: Optional[str] = None


class Property(BaseModel):
    id: str = Field(..., description="e.g. IP1")
    short_name: str
    display_name: str
    address: str
    type: Literal["residential", "commercial", "industrial"] = "residential"
    units: int = 1
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    current_value: Optional[float] = None
    current_value_date: Optional[str] = None
    mortgage_balance: Optional[float] = None
    thumbnail: Optional[str] = None
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionCreate(BaseModel):
    date: datetime
    category: str
    description: str
    amount: float
    type: Literal["income", "expense", "cash_flow"]


class Transaction(BaseModel):
    id: Optional[str] = None
    date: datetime
    month: str = ""
    fy: str = ""
    category: str = ""
    description: str = ""
    amount: float = 0.0
    type: Literal["income", "expense", "cash_flow"] = "expense"
    source_pdf: Optional[str] = None
    source_page: Optional[int] = None
    confidence: float = 1.0
    manually_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Ledger(BaseModel):
    property_id: str = ""
    transactions: list[Transaction] = Field(default_factory=list)


class Portfolio(BaseModel):
    properties: list[Property] = Field(default_factory=list)
    settings: dict = Field(
        default_factory=lambda: {
            "fy_start_month": 7,
            "currency_symbol": "$",
            "country": "AU"
        }
    )


class PendingUpload(BaseModel):
    pending_id: str
    property_id: str
    filename: str
    items: list[Transaction]
    created_at: datetime = Field(default_factory=datetime.utcnow)
