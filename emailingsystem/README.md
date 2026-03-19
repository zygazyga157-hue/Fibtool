Fibtool Emailing System - Phase 1 MVP
======================================

This folder contains the complete implementation of Phase 1 MVP for the Fibtool subscription and email delivery system.

Purpose
-------
A subscription-based web platform to sell Fibtool plot outputs to customers via email delivery. Backend is FastAPI, frontend is Next.js, payments via PayNow (Zimbabwe).

Project Structure
-----------------
```
emailingsystem/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/      # API endpoints
│   │   ├── core/     # Config and security
│   │   ├── models/   # Database models
│   │   ├── schemas/  # Pydantic schemas
│   │   └── services/ # Business logic
│   ├── init_db.py    # Database initialization
│   └── requirements.txt
├── frontend/          # Next.js frontend
│   ├── app/          # App router pages
│   ├── lib/          # API client
│   └── package.json
└── docker-compose.yml
```

Quick Start
-----------

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
python init_db.py
uvicorn app.main:app --reload
```

Backend at `http://localhost:8000` | Docs at `http://localhost:8000/docs`

### Frontend Setup
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Frontend at `http://localhost:3000`

Features Implemented
-------------------
✅ User authentication (register/login) with JWT
✅ Plans management
✅ Checkout flow
✅ Payment webhook endpoint
✅ Delivery service (stub)
✅ Email service (stub)
✅ Dashboard for users
✅ Frontend pages (home, pricing, login, register, dashboard)

Design Docs
-----------
- `ARCHITECTURE.md` — high level components and data flow
- `FASTAPI_API_SPEC.md` — API endpoints and contracts
- `DB_SCHEMA.md` — proposed database tables
- `PAYMENT_WORKFLOW.md` — payment flow, webhook handling and idempotency
- `FRONTEND_FLOW.md` — Next.js pages and UX flow
- `SECURITY.md` — auth, secrets, PCI considerations
- `DEPLOYMENT.md` — Docker, env, recommended hosting
- `TODO.md` — prioritized implementation plan

Next Steps (Phase 2)
--------------------
- Implement actual PayNow API integration
- Add webhook signature verification
- Implement background task queue
- Add comprehensive tests
- Deploy to production