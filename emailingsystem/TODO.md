Implementation TODO (prioritized)
=================================

Phase 0 — Planning (this set of docs) — DONE

Phase 1 — MVP (2-5 days)
- [ ] Scaffold backend folder `emailingsystem/backend` (FastAPI) with dependencies and Dockerfile
- [ ] Implement user auth (register/login) with JWT
- [ ] Implement `plans` and `checkout` endpoints; store Payment records (PENDING)
- [ ] Implement PayNow integration (create transaction + webhook endpoint stub)
- [ ] Implement minimal worker to generate a "dummy" plot (use existing outputs) and email it
- [ ] Scaffold frontend `emailingsystem/frontend` (Next.js) with marketing and checkout pages
- [ ] Basic E2E: create payment -> webhook -> mark PAID -> send email with attachment

Phase 2 — Harden & polish (1-2 weeks)
- [ ] Use Postgres, migrate DB schema
- [ ] Implement subscription lifecycle (create, renew, cancel)
- [ ] Add idempotency and reconciliation jobs for payments
- [ ] Add admin UI & exportable reports
- [ ] Add tests and CI

Phase 3 — Production & scaling
- [ ] Deploy to production hosting
- [ ] Configure monitoring, backups, and failover
- [ ] Add per-symbol pricing or tiering

Notes
-----
- I recommend starting the backend as the first implementation so you can iterate quickly on webhook/payment behavior.
- I'll scaffold the FastAPI app and the Next.js starter if you approve the plan and priorities.