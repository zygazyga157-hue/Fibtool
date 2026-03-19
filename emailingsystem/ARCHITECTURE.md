Architecture overview
======================

High level components
---------------------
- Frontend (Next.js)
  - Public marketing pages, pricing, signup, payment redirect
  - Customer dashboard (subscriptions, invoices, profile)
- Backend (FastAPI)
  - REST API for user auth, subscription management, payment creation
  - Webhook endpoints for payment notifications
  - Background worker endpoints to trigger plot generation and email delivery
- Payment Provider
  - PayNow (Zimbabwe) — accept payments, send webhooks on payment status
- Email Service
  - SMTP or transactional provider (SendGrid/Mailgun) for reliable delivery
- Database
  - PostgreSQL (production) / SQLite for MVP
- Storage
  - S3-compatible (AWS S3 or MinIO) for storing generated plot images and attachments
- Admin notifications
  - Telegram or email for every executed subscription/sale (reuses existing admin notification patterns)

Dataflow (user buys a plot/subscription)
---------------------------------------
1. User picks plan and checkout on Next.js frontend.
2. Frontend calls FastAPI to create a payment request.
3. FastAPI creates PayNow transaction and returns payment_url to frontend.
4. User pays using PayNow (mobile/USSD/bank) and PayNow calls our webhook.
5. Webhook validates signature/idempotency and marks payment as PAID; creates subscription record if applicable.
6. Background worker generates the plot (calls existing plotting tools or uses pre-generated outputs) and stores it to storage.
7. Email is sent to the user with the plot attached or link to the dashboard.
8. Admin receives notification of executed sale (Telegram/email), and the transaction is recorded in DB.

Why FastAPI + Next.js
---------------------
- FastAPI: fast to prototype, async webhooks, great typing and docs (OpenAPI)
- Next.js: SEO-friendly marketing pages + React-based dashboard with server-side rendering where needed

Notes on isolation
------------------
All code lives under `emailingsystem/` and communicates with the plotting tools via outputs CSV files and/or a small internal task queue. This keeps the production plotting scripts untouched.