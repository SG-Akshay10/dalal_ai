from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from app.auth import get_current_user
from app.database import DatabaseManager
from app.services.ingestion import ingest_for_symbols
from app.services.alerts import evaluate_and_dispatch_alerts

router = APIRouter(prefix="/api/feed", tags=["feed"])

def get_user_id(user: dict) -> str:
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id

@router.get("")
def get_feed(
    symbol: Optional[str] = Query(None, description="Filter by stock symbol"),
    category: Optional[str] = Query(None, description="Filter by announcement category"),
    materiality: Optional[str] = Query(None, description="Filter by materiality level (high, medium, low)"),
    sentiment: Optional[str] = Query(None, description="Filter by directional sentiment (positive, negative, neutral, unclear)"),
    q: Optional[str] = Query(None, description="Search query string"),
    days: int = Query(3, ge=1, le=30, description="Filter news within last N days"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    """
    Returns portfolio-wide news and filing feed sorted by materiality ranking (High -> Medium -> Low)
    and recency.
    """
    user_id = get_user_id(user)
    holdings = DatabaseManager.get_holdings(user_id)
    user_symbols = [h["symbol"] for h in holdings] if holdings else []

    symbols_filter = [symbol.upper()] if symbol else user_symbols

    feed_items = DatabaseManager.get_news_feed(
        symbols=symbols_filter,
        category=category,
        materiality=materiality,
        sentiment=sentiment,
        search_query=q,
        max_days=days,
        limit=limit,
        offset=offset
    )

    if not feed_items and user_symbols:
        ingested = ingest_for_symbols(user_symbols)
        evaluate_and_dispatch_alerts(user_id, ingested)
        feed_items = DatabaseManager.get_news_feed(
            symbols=symbols_filter,
            category=category,
            materiality=materiality,
            sentiment=sentiment,
            search_query=q,
            max_days=days,
            limit=limit,
            offset=offset
        )

    return {
        "count": len(feed_items),
        "user_holdings": user_symbols,
        "items": feed_items
    }

@router.get("/stock/{symbol}")
def get_stock_timeline(symbol: str, user: dict = Depends(get_current_user)):
    """
    Returns historical timeline of news, filings, and AI explanations for a specific stock holding.
    """
    user_id = get_user_id(user)
    sym_clean = symbol.strip().upper()
    timeline = DatabaseManager.get_news_by_symbol(sym_clean, max_days=3)

    if not timeline:
        ingested = ingest_for_symbols([sym_clean])
        evaluate_and_dispatch_alerts(user_id, ingested)
        timeline = DatabaseManager.get_news_by_symbol(sym_clean, max_days=3)

    return {
        "symbol": sym_clean,
        "count": len(timeline),
        "items": timeline
    }

@router.post("/trigger-ingest")
def trigger_manual_ingest(user: dict = Depends(get_current_user)):
    """
    Manually triggers live news & filing ingestion + Sarvam AI classification for user holdings.
    """
    user_id = get_user_id(user)
    holdings = DatabaseManager.get_holdings(user_id)
    if not holdings:
        raise HTTPException(status_code=400, detail="No holdings found in user portfolio.")

    user_symbols = [h["symbol"] for h in holdings]
    newly_ingested = ingest_for_symbols(user_symbols)
    dispatched_alerts = evaluate_and_dispatch_alerts(user_id, newly_ingested)

    return {
        "message": f"Successfully ingested latest filings and news for {len(user_symbols)} holdings.",
        "ingested_count": len(newly_ingested),
        "alerts_triggered": len(dispatched_alerts),
        "symbols": user_symbols
    }
