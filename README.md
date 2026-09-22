# dalal.ai

> **Next.js 16 · NextAuth v5 · FastAPI · Supabase Postgres · Render · Vercel**

A modern full-stack stock portfolio management app with AI-powered risk analysis. Built with a Next.js frontend, Python FastAPI backend, Supabase Postgres database, and LangGraph multi-agent analysis.

---

## 🏛️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
│                                                             │
│  Next.js on Vercel                                         │
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
│  Supabase Postgres│         │  FastAPI on Render    │
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
├── backend/Dockerfile    # Backend-only image for Render
├── render.yaml           # Render backend service blueprint
└── .env.example          # Environment variables template
```

---

## 📋 Prerequisites

Before running the application, ensure you have installed:

- A **Supabase** project (free tier — [create one here](https://supabase.com))
- Node.js 20+ and Python 3.11+

---

## ⚙️ Setup & Installation

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
| `NEXTAUTH_URL` | Frontend URL (`http://localhost:3000` locally, Vercel URL in production) |
| `NEXT_PUBLIC_API_URL` | Backend URL (`http://localhost:8000` locally, Render URL in production) |
| `FRONTEND_URL` | Backend CORS allowed origin (`http://localhost:3000` locally, Vercel URL in production) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_URL` | Supabase Project URL (backend) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Anonymous Key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role Key ⚠️ Keep secret |
| `SARVAM_API_KEY` | *(Optional)* Sarvam AI API Key for Portfolio Risk Analysis |

---

## 🛠️ Running Locally

Start the backend:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend is available at [http://localhost:3000](http://localhost:3000), and the API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

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

## 🚀 Deployment

### Backend on Render

The repository includes [`render.yaml`](./render.yaml), which configures Render to build only [`backend/Dockerfile`](./backend/Dockerfile) and serve FastAPI on Render's `$PORT`.

1. Create a Render Blueprint from this repository, or create a Docker Web Service with root directory `backend` and Dockerfile path `Dockerfile`.
2. Set `AUTH_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `FRONTEND_URL` in Render. Add `SARVAM_API_KEY` if AI analysis is enabled.
3. Copy the resulting service URL, such as `https://dalal-backend.onrender.com`.

### Frontend on Vercel

1. Import this repository into Vercel and set the project root directory to `frontend`.
2. Set `AUTH_SECRET`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`.
3. Set `NEXT_PUBLIC_API_URL` to the Render backend URL and set `NEXTAUTH_URL` to the Vercel production URL.
4. Set Render's `FRONTEND_URL` to the same Vercel URL so browser requests pass CORS checks.

The frontend and backend must use the same `AUTH_SECRET`.

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
