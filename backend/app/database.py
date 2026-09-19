import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("database")
logging.basicConfig(level=logging.INFO)

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

supabase_client: Optional[Any] = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase client: {e}")

supabase = supabase_client

# ---- Local SQLite fallback setup ----
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DB_DIR, exist_ok=True)
SQLITE_DB_PATH = os.path.join(DB_DIR, "portfolio.db")

def get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite_db():
    """Ensure all required domain tables exist in local SQLite storage."""
    conn = get_sqlite_conn()
    cursor = conn.cursor()

    # app_users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # holdings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS holdings (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        company_name TEXT NOT NULL,
        exchange TEXT NOT NULL DEFAULT 'NSE',
        quantity REAL,
        buy_price REAL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, symbol)
    );
    """)

    # news_items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS news_items (
        id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        title TEXT NOT NULL,
        source TEXT NOT NULL,
        url TEXT NOT NULL,
        content TEXT,
        published_at TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'General News',
        materiality TEXT NOT NULL DEFAULT 'medium',
        sentiment TEXT NOT NULL DEFAULT 'neutral',
        summary TEXT NOT NULL,
        processed_at TEXT NOT NULL,
        dedup_hash TEXT UNIQUE NOT NULL
    );
    """)

    # user_alert_settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_alert_settings (
        user_id TEXT PRIMARY KEY,
        channel TEXT NOT NULL DEFAULT 'browser',
        materiality_threshold TEXT NOT NULL DEFAULT 'high',
        telegram_chat_id TEXT,
        email_destination TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
    );
    """)

    # user_alerts_sent table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_alerts_sent (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        news_item_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'delivered',
        sent_at TEXT NOT NULL
    );
    """)

    # user_analysis_logs table for rate limiting
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_analysis_logs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        generated_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

# Run initialization immediately
init_sqlite_db()


class DatabaseManager:
    """
    Hybrid database manager that queries Supabase first and gracefully
    falls back to SQLite if a Supabase table is not yet provisioned.
    """

    @staticmethod
    def get_holdings(user_id: str) -> List[Dict[str, Any]]:
        if supabase_client:
            try:
                res = supabase_client.table("holdings").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
                return res.data
            except Exception as e:
                logger.info(f"Supabase holdings table query failed ({e}), using local store.")
        
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM holdings WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def add_holding(user_id: str, holding_data: Dict[str, Any]) -> Dict[str, Any]:
        import uuid
        holding_id = holding_data.get("id") or str(uuid.uuid4())
        now_str = datetime.utcnow().isoformat() + "Z"

        record = {
            "id": holding_id,
            "user_id": user_id,
            "symbol": holding_data["symbol"].strip().upper(),
            "company_name": holding_data.get("company_name", holding_data["symbol"]),
            "exchange": holding_data.get("exchange", "NSE").upper(),
            "quantity": holding_data.get("quantity"),
            "buy_price": holding_data.get("buy_price"),
            "created_at": now_str
        }

        # Try Supabase insert
        if supabase_client:
            try:
                res = supabase_client.table("holdings").insert(record).execute()
                if res.data and len(res.data) > 0:
                    record = res.data[0]
            except Exception as e:
                logger.info(f"Supabase insert holdings failed ({e}), writing to local store.")

        # Always maintain SQLite state
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO holdings (id, user_id, symbol, company_name, exchange, quantity, buy_price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (record["id"], record["user_id"], record["symbol"], record["company_name"],
              record["exchange"], record["quantity"], record["buy_price"], record["created_at"]))
        conn.commit()
        conn.close()

        return record

    @staticmethod
    def delete_holding(user_id: str, holding_id: str) -> bool:
        if supabase_client:
            try:
                supabase_client.table("holdings").delete().eq("id", holding_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.info(f"Supabase delete holding failed ({e}).")

        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM holdings WHERE id = ? AND user_id = ?", (holding_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    @staticmethod
    def save_news_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        saved = []
        conn = get_sqlite_conn()
        cursor = conn.cursor()

        for item in items:
            import uuid
            item_id = item.get("id") or str(uuid.uuid4())
            symbol = item["symbol"].upper()
            title = item["title"]
            source = item.get("source", "Market Feed")
            url = item.get("url", "#")
            content = item.get("content", "")
            published_at = item.get("published_at") or datetime.now(timezone.utc).isoformat()
            category = item.get("category", "General News")
            materiality = item.get("materiality", "medium").lower()
            sentiment = item.get("sentiment", "neutral").lower()
            summary = item.get("summary", "")
            processed_at = datetime.now(timezone.utc).isoformat()
            dedup_hash = item.get("dedup_hash") or f"{symbol}_{hash(title)}"

            record = {
                "id": item_id,
                "symbol": symbol,
                "title": title,
                "source": source,
                "url": url,
                "content": content,
                "published_at": published_at,
                "category": category,
                "materiality": materiality,
                "sentiment": sentiment,
                "summary": summary,
                "processed_at": processed_at,
                "dedup_hash": dedup_hash
            }

            # Try Supabase insert
            if supabase_client:
                try:
                    supabase_client.table("news_items").upsert(record, on_conflict="dedup_hash").execute()
                except Exception as e:
                    pass

            # SQLite insert
            cursor.execute("""
                INSERT OR REPLACE INTO news_items 
                (id, symbol, title, source, url, content, published_at, category, materiality, sentiment, summary, processed_at, dedup_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, symbol, title, source, url, content, published_at, category, materiality, sentiment, summary, processed_at, dedup_hash))

            saved.append(record)

        conn.commit()
        conn.close()
        return saved

    @staticmethod
    def get_news_feed(
        symbols: Optional[List[str]] = None,
        category: Optional[str] = None,
        materiality: Optional[str] = None,
        sentiment: Optional[str] = None,
        search_query: Optional[str] = None,
        max_days: Optional[int] = 3,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        # Query local database (which mirrors or stores news items)
        conn = get_sqlite_conn()
        cursor = conn.cursor()

        sql = "SELECT * FROM news_items WHERE 1=1"
        params = []

        if max_days is not None:
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()
            sql += " AND published_at >= ?"
            params.append(cutoff_iso)

        if symbols:
            upper_symbols = [s.upper() for s in symbols]
            placeholders = ",".join(["?"] * len(upper_symbols))
            sql += f" AND symbol IN ({placeholders})"
            params.extend(upper_symbols)

        if category and category.lower() != "all":
            sql += " AND LOWER(category) = ?"
            params.append(category.lower())

        if materiality and materiality.lower() != "all":
            sql += " AND LOWER(materiality) = ?"
            params.append(materiality.lower())

        if sentiment and sentiment.lower() != "all":
            sql += " AND LOWER(sentiment) = ?"
            params.append(sentiment.lower())

        if search_query:
            sql += " AND (title LIKE ? OR summary LIKE ? OR symbol LIKE ?)"
            q_param = f"%{search_query}%"
            params.extend([q_param, q_param, q_param])

        # Materiality ranking: high -> medium -> low, then recency
        sql += """
            ORDER BY 
                CASE LOWER(materiality)
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END ASC,
                published_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_news_by_symbol(symbol: str, max_days: Optional[int] = 3) -> List[Dict[str, Any]]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        if max_days is not None:
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()
            cursor.execute("""
                SELECT * FROM news_items 
                WHERE symbol = ? AND published_at >= ?
                ORDER BY published_at DESC
            """, (symbol.upper(), cutoff_iso))
        else:
            cursor.execute("""
                SELECT * FROM news_items 
                WHERE symbol = ? 
                ORDER BY published_at DESC
            """, (symbol.upper(),))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_alert_settings(user_id: str) -> Dict[str, Any]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_alert_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            res = dict(row)
            res["enabled"] = bool(res["enabled"])
            return res

        default_settings = {
            "user_id": user_id,
            "channel": "browser",
            "materiality_threshold": "high",
            "telegram_chat_id": "",
            "email_destination": "",
            "enabled": True,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        return default_settings

    @staticmethod
    def save_alert_settings(user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        channel = settings.get("channel", "browser")
        materiality_threshold = settings.get("materiality_threshold", "high")
        telegram_chat_id = settings.get("telegram_chat_id", "")
        email_destination = settings.get("email_destination", "")
        enabled = 1 if settings.get("enabled", True) else 0
        updated_at = datetime.utcnow().isoformat() + "Z"

        record = {
            "user_id": user_id,
            "channel": channel,
            "materiality_threshold": materiality_threshold,
            "telegram_chat_id": telegram_chat_id,
            "email_destination": email_destination,
            "enabled": bool(enabled),
            "updated_at": updated_at
        }

        if supabase_client:
            try:
                supabase_client.table("user_alert_settings").upsert(record).execute()
            except Exception as e:
                pass

        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_alert_settings
            (user_id, channel, materiality_threshold, telegram_chat_id, email_destination, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, channel, materiality_threshold, telegram_chat_id, email_destination, enabled, updated_at))
        conn.commit()
        conn.close()

        return record

    @staticmethod
    def log_sent_alert(user_id: str, news_item_id: str, channel: str, status: str = "delivered") -> Dict[str, Any]:
        import uuid
        alert_id = str(uuid.uuid4())
        sent_at = datetime.utcnow().isoformat() + "Z"

        record = {
            "id": alert_id,
            "user_id": user_id,
            "news_item_id": news_item_id,
            "channel": channel,
            "status": status,
            "sent_at": sent_at
        }

        if supabase_client:
            try:
                supabase_client.table("user_alerts_sent").insert(record).execute()
            except Exception:
                pass

        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_alerts_sent (id, user_id, news_item_id, channel, status, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (alert_id, user_id, news_item_id, channel, status, sent_at))
        conn.commit()
        conn.close()

        return record

    @staticmethod
    def get_sent_alerts(user_id: str) -> List[Dict[str, Any]]:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, n.title, n.symbol, n.materiality, n.summary 
            FROM user_alerts_sent a
            JOIN news_items n ON a.news_item_id = n.id
            WHERE a.user_id = ?
            ORDER BY a.sent_at DESC
            LIMIT 50
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_last_analysis_timestamp(user_id: str) -> Optional[datetime]:
        """Return the most recent analysis generation datetime (UTC) for a user, or None."""
        if supabase_client:
            try:
                res = supabase_client.table("user_analysis_logs").select("generated_at").eq("user_id", user_id).order("generated_at", desc=True).limit(1).execute()
                if res.data and len(res.data) > 0:
                    raw_dt = res.data[0]["generated_at"]
                    return datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
            except Exception as e:
                logger.info(f"Supabase user_analysis_logs query failed ({e}), falling back to local store.")

        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT generated_at FROM user_analysis_logs WHERE user_id = ? ORDER BY generated_at DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row["generated_at"]:
            return datetime.fromisoformat(row["generated_at"].replace("Z", "+00:00"))
        return None

    @staticmethod
    def log_analysis_generation(user_id: str) -> Dict[str, Any]:
        """Log a new AI analysis generation timestamp for a user."""
        import uuid
        log_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()

        record = {
            "id": log_id,
            "user_id": user_id,
            "generated_at": generated_at
        }

        if supabase_client:
            try:
                supabase_client.table("user_analysis_logs").insert(record).execute()
            except Exception as e:
                logger.info(f"Supabase log_analysis_generation failed ({e}).")

        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user_analysis_logs (id, user_id, generated_at) VALUES (?, ?, ?)", (log_id, user_id, generated_at))
        conn.commit()
        conn.close()

        return record

# Backward compatibility alias
database = DatabaseManager
