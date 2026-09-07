import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routers import items, holdings, feed, alerts, analysis

load_dotenv()

app = FastAPI(
    title="dalal.ai API",
    description="FastAPI backend for tracking price-material stock news and Sarvam AI summaries.",
    version="1.0.0",
)

# ---- CORS ----
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
app.include_router(holdings.router)
app.include_router(feed.router)
app.include_router(alerts.router)
app.include_router(items.router)
app.include_router(analysis.router)

# ---- Public routes ----
@app.get("/health", tags=["health"])
def health_check():
    """Public health-check endpoint."""
    return {"status": "ok", "service": "dalal.ai API"}
