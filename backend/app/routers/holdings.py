from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from app.auth import get_current_user
from app.database import DatabaseManager

router = APIRouter(prefix="/api/holdings", tags=["holdings"])

DEFAULT_POPULAR_STOCKS = [
    {"symbol": "RELIANCE", "company_name": "Reliance Industries Ltd", "exchange": "NSE"},
    {"symbol": "TCS", "company_name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
    {"symbol": "INFY", "company_name": "Infosys Limited", "exchange": "NSE"},
    {"symbol": "HDFCBANK", "company_name": "HDFC Bank Ltd", "exchange": "NSE"},
    {"symbol": "TATASTEEL", "company_name": "Tata Steel Limited", "exchange": "NSE"}
]

class HoldingCreate(BaseModel):
    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = "NSE"
    quantity: Optional[float] = None
    buy_price: Optional[float] = None

def get_user_id(user: dict) -> str:
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id

@router.get("")
def get_holdings(user: dict = Depends(get_current_user)):
    """Fetch user's tracked portfolio holdings."""
    user_id = get_user_id(user)
    holdings = DatabaseManager.get_holdings(user_id)

    return holdings

@router.post("", status_code=status.HTTP_201_CREATED)
def add_holding(payload: HoldingCreate, user: dict = Depends(get_current_user)):
    """Add a stock holding to tracked portfolio."""
    user_id = get_user_id(user)
    symbol_clean = payload.symbol.strip().upper()
    if not symbol_clean:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty.")

    holding_data = {
        "symbol": symbol_clean,
        "company_name": payload.company_name or f"{symbol_clean} Ltd",
        "exchange": (payload.exchange or "NSE").upper(),
        "quantity": payload.quantity,
        "buy_price": payload.buy_price
    }

    record = DatabaseManager.add_holding(user_id, holding_data)
    return record

@router.delete("/{holding_id}")
def delete_holding(holding_id: str, user: dict = Depends(get_current_user)):
    """Remove stock holding from portfolio."""
    user_id = get_user_id(user)
    success = DatabaseManager.delete_holding(user_id, holding_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holding not found.")
    return {"message": "Holding deleted successfully."}
