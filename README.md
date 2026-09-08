# dalal.ai

> **Next.js 16 · NextAuth v5 · FastAPI · Supabase Postgres**

A minimal but complete full-stack demo app demonstrating how to wire together a Next.js frontend with credential-based authentication (NextAuth), a Python FastAPI backend, and a shared Supabase Postgres database.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
│                                                             │
│  Next.js (port 3000)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  NextAuth v5 (Credentials Provider)                 │   │
│  │  • authorize() → Supabase app_users lookup          │   │
│  │  • Issues signed JWT (HS256, AUTH_SECRET)           │   │
│  │  • Stored as HttpOnly cookie                        │   │
│  │                                                     │   │
│  │  Dashboard page                                     │   │
│  │  • Calls /api/auth/token → gets raw JWT             │   │
│  │  • fetch FastAPI with Authorization: Bearer <jwt>   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │                              │
          │ (service_role key)           │ (Bearer JWT)
          ▼                              ▼
┌──────────────────┐          ┌──────────────────────┐
│  Supabase Postgres│         │  FastAPI (port 8000)  │
│  • app_users      │         │  • auth.py: decode JWT│
│  • items          │         │    with AUTH_SECRET   │
│                   │◄────────│  • database.py:       │
│                   │         │    supabase-py queries│
└──────────────────┘          └──────────────────────┘
```

**Token flow:**
1. User logs in → NextAuth issues JWT signed with `AUTH_SECRET`
2. Dashboard page fetches raw JWT from `/api/auth/token` (server route)
3. JWT is sent as `Authorization: Bearer <token>` to FastAPI
4. FastAPI decodes & verifies the JWT using the same `AUTH_SECRET`
5. `user.sub` (user ID) is extracted to scope DB queries to that user

---

## Folder Structure

```
dalal.ai/
├── frontend/                   # Next.js 14 App Router
│   ├── app/
│   │   ├── api/auth/
│   │   │   ├── [...nextauth]/route.ts   # NextAuth handler
│   │   │   └── token/route.ts           # Exposes raw JWT
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── dashboard/page.tsx           # Protected — calls FastAPI
│   │   ├── layout.tsx
│   │   └── page.tsx                     # Landing
│   ├── components/
│   │   ├── Navbar.tsx
│   │   └── SessionProvider.tsx
│   ├── lib/
│   │   ├── auth.ts              # NextAuth config
│   │   └── supabaseClient.ts   # Supabase JS clients
│   ├── types/next-auth.d.ts    # Session type augmentation
│   ├── middleware.ts            # Route protection
│   └── .env.local.example
│
├── backend/                    # FastAPI Python service
│   ├── app/
│   │   ├── main.py             # App entry point + CORS
│   │   ├── auth.py             # JWT verification dependency
│   │   ├── database.py         # supabase-py client
│   │   └── routers/
│   │       └── items.py        # CRUD routes
│   ├── requirements.txt
│   └── .env.example
│
├── supabase/
│   └── schema.sql              # DB bootstrap script
│
└── README.md
```

---

## Prerequisites

- **Node.js** 18+
- **Python** 3.11+
- A **Supabase** project (free tier works — [create one here](https://supabase.com))

---

## Setup Instructions

### 1. Supabase Database

1. Open your Supabase project → **SQL Editor**
2. Paste and run the contents of [`supabase/schema.sql`](./supabase/schema.sql)
3. This creates the `app_users`, `items`, `holdings`, `news_items`, `user_alert_settings`, and `user_alerts_sent` tables
### 2. Frontend

```bash
cd frontend
cp .env.local.example .env.local
# Edit .env.local and fill in all values (see below)

npm install
npm run dev   # Runs on http://localhost:3000
```

**`frontend/.env.local`** — required variables:

| Variable | Where to find |
|---|---|
| `AUTH_SECRET` | Run `npx auth secret` and copy the output |
| `NEXTAUTH_URL` | `http://localhost:3000` for local dev |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Dashboard → Settings → API → anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → service_role key ⚠️ Keep secret |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` for local dev |

### 3. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from the example
cp .env.example .env
# Edit .env with your values (AUTH_SECRET must match frontend exactly!)

# Run the server
uvicorn app.main:app --reload    # Runs on http://localhost:8000
```

**`backend/.env`** — required variables:

| Variable | Value |
|---|---|
| `AUTH_SECRET` | **Exact same value** as `AUTH_SECRET` in `frontend/.env.local` |
| `SUPABASE_URL` | Same as `NEXT_PUBLIC_SUPABASE_URL` |
| `SUPABASE_SERVICE_ROLE_KEY` | Same service_role key |
| `FRONTEND_URL` | `http://localhost:3000` |

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
