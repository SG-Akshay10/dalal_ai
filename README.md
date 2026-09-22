# dalal.ai

> **Next.js 16 · NextAuth v5 · FastAPI · Supabase Postgres · Docker**

A modern full-stack stock portfolio management app with AI-powered risk analysis. Built with a Next.js frontend, Python FastAPI backend, Supabase Postgres database, and LangGraph multi-agent analysis.

---

## 🏛️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
│                                                             │
│  Next.js (port 3000)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  NextAuth v5 (Credentials Provider)                 │   │
│  │  • Issues signed JWT (HS256, AUTH_SECRET)           │   │
│  │  • Calls FastAPI with Authorization: Bearer <jwt>   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │                              │
          │ (service_role key)           │ (Bearer JWT)
          ▼                              ▼
┌──────────────────┐          ┌──────────────────────┐
│  Supabase Postgres│         │  FastAPI (port 8000)  │
│  • User accounts  │         │  • JWT verification  │
│  • Holdings & Risk│◄────────│  • LangGraph agents  │
└──────────────────┘          └──────────────────────┘
```

---

## 📁 Directory Structure

```
dalal.ai/
├── frontend/             # Next.js 16 App Router
├── backend/              # FastAPI Python service & LangGraph agents
├── supabase/             # SQL schema definitions
├── Dockerfile            # Unified Docker container spec (supervisord)
├── docker-compose.yml    # Docker Compose setup
├── supervisord.conf      # Process management for Docker
└── .env.example          # Environment variables template
```

---

## 📋 Prerequisites

Before running the application, ensure you have installed:

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- A **Supabase** project (free tier — [create one here](https://supabase.com))

---

## ⚙️ Setup & Installation (Docker)

### 1. Database Setup

1. Go to your Supabase Project → **SQL Editor**.
2. Run the SQL script found in [`supabase/schema.sql`](./supabase/schema.sql).
3. This provisions the necessary tables: `app_users`, `items`, `holdings`, `news_items`, `user_alert_settings`, and `user_alerts_sent`.

### 2. Environment Configuration

Copy the root environment example file to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and fill in your configuration:

| Variable | Description |
|---|---|
| `AUTH_SECRET` | Secret key for JWT signing (generate using `npx auth secret`) |
| `NEXTAUTH_URL` | Frontend URL (`http://localhost:3000`) |
| `NEXT_PUBLIC_API_URL` | Backend URL (`http://localhost:8000`) |
| `FRONTEND_URL` | Backend CORS allowed origin (`http://localhost:3000`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_URL` | Supabase Project URL (backend) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Anonymous Key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role Key ⚠️ Keep secret |
| `SARVAM_API_KEY` | *(Optional)* Sarvam AI API Key for Portfolio Risk Analysis |

---

## 🐳 Running the Application

### Option 1: Using Docker Compose (Recommended)

Build and launch the application in a single command:

```bash
docker compose up --build
```

Access the application:
- **Frontend App**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

To stop the containers:

```bash
docker compose down
```

### Option 2: Using Docker CLI Directly

```bash
# Build the container image
docker build -t dalal-ai .

# Run the container using your .env file
docker run -p 3000:3000 -p 8000:8000 --env-file .env dalal-ai
```

---

## 🔌 API Endpoints Summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Backend health check |
| `GET` | `/api/items/` | 🔒 JWT | List items for authenticated user |
| `POST` | `/api/items/` | 🔒 JWT | Create new item |
| `DELETE` | `/api/items/{id}` | 🔒 JWT | Delete item by ID |
| `POST` | `/api/analysis/risk-profile` | 🔒 JWT | Run multi-agent AI risk analysis |

---

## 🔒 Security Notes

- Keep `SUPABASE_SERVICE_ROLE_KEY` and `AUTH_SECRET` secure and never expose them publicly.
- Ensure `AUTH_SECRET` matches across frontend and backend environments.
- Use HTTPS in production environments.


---

## Vercel Deployment Guide

### Option 1: Frontend on Vercel + Backend on Docker Cloud (Recommended)

Vercel natively excels at hosting Next.js applications, while Docker containers with dual background processes (Next.js + FastAPI) are best run on container platforms like **Render**, **Fly.io**, or **AWS ECS/App Runner**.

1. **Deploy Backend to Container Service (Render / Fly.io / Railway)**:
   - Deploy this Docker container or backend folder.
   - Set environment variables (`AUTH_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FRONTEND_URL`).
   - Copy your public backend service URL (e.g. `https://dalal-backend.onrender.com`).

2. **Deploy Frontend to Vercel**:
   - Push your project to GitHub.
   - Import project into Vercel and select root directory `frontend`.
   - Set Vercel Environment Variables:
     - `NEXT_PUBLIC_API_URL`: Your deployed backend URL.
     - `AUTH_SECRET`: Same secret as backend.
     - `NEXTAUTH_URL`: Your Vercel domain (e.g. `https://your-app.vercel.app`).
     - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

### Option 2: Deploying Docker Container directly on Vercel

If you wish to deploy a containerized deployment setup:
- Vercel focus is on Serverless and Frontend deployments. For hosting custom Docker containers, use **Vercel Web Analytics / Serverless Functions** or pair Vercel with Docker on **Fly.io** / **Render**.
- If deploying Next.js standalone container to Vercel using Docker, use the **Vercel CLI** or connect your GitHub repository and point your build target accordingly.

---

## API Endpoints

### FastAPI (port 8000)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Health check |
| `GET` | `/api/items/` | 🔒 JWT | List items for logged-in user |
| `POST` | `/api/items/` | 🔒 JWT | Create new item |
| `DELETE` | `/api/items/{id}` | 🔒 JWT | Delete item (owner only) |
| `POST` | `/api/analysis/risk-profile` | 🔒 JWT | Structured stock, sector, and diversification risk analysis |

Interactive docs: **http://localhost:8000/docs**

### Portfolio risk-analysis input

`POST /api/analysis/risk-profile` accepts raw holdings as JSON. Each item needs
`ticker` (or `symbol`) and `quantity`; provide `sector` and `current_price` (or
`buy_price`) for allocation analysis. The optional fields
`annualized_volatility_pct` (or `historical_prices`), `beta`, `market_cap`,
`analyst_target_price`, `recent_momentum_pct`, and `growth_outlook` enrich risk
and return-potential profiles. Missing market/sector fields are returned in the
per-stock and portfolio `data_quality.errors` fields rather than failing the
whole report.

```json
{
  "holdings": [
    {
      "ticker": "INFY",
      "quantity": 20,
      "sector": "Information Technology",
      "current_price": 1500,
      "annualized_volatility_pct": 28.4,
      "market_cap": 650000000000,
      "beta": 1.1,
      "analyst_target_price": 1650,
      "recent_momentum_pct": 8.5,
      "growth_outlook": "positive"
    }
  ],
  "include_llm_insight": true,
  "concentration_threshold_pct": 35,
  "minimum_allocation_pct": 5
}
```

The endpoint now runs a LangGraph multi-agent analysis: ingestion feeds sector,
asset-technical, and risk agents in parallel; a critic validates their
structured outputs before Sarvam synthesizes the executive report. Responses
include the full `executive_report`, enriched holdings, sector and risk outputs,
and compatibility summary fields for the dashboard. A portfolio of ten or fewer
holdings receives an asset narrative of at least 100 words per holding; larger
portfolios receive detailed sector-level analysis only. If Sarvam is unavailable
or cannot produce a validated report, the endpoint returns HTTP 503 and the UI
does not display a stale or partial AI report.

AI reports are held in backend memory for 24 hours per user and portfolio
composition. Dashboard refreshes reuse the cached report, while live quotes and
charts can refresh independently. Changing holdings, quantity, buy price,
sector, or exchange starts a new report cycle. The process-local cache resets
when the backend restarts.

To run the graph against holdings already created through the dashboard:

```bash
cd backend
python test_pipeline.py --user-id <user-id>
```

---

## Development Tips

- **Hot-reload**: Both `npm run dev` and `uvicorn --reload` support hot-reload.
- **Inspect JWT**: Paste the token from `/api/auth/token` into [jwt.io](https://jwt.io) to inspect the payload.
- **Supabase Studio**: View your `app_users` and `items` rows live at `https://supabase.com/dashboard/project/<ref>/editor`.

---

## Security Notes (for production hardening)

- Move password hashing from the Register client component to a **Server Action** or API route — never trust client-side hashing alone in production.
- Enable **RLS** (Row-Level Security) on Supabase tables and configure appropriate policies.
- Rotate `AUTH_SECRET` periodically and use a strong random value.
- Store `SUPABASE_SERVICE_ROLE_KEY` securely (never commit it; use a secrets manager).
- Add HTTPS termination in front of both services.
