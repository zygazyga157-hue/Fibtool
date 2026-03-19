FastAPI API specification
==========================

Authentication
--------------
- We will support email/password (hashed) and JWT tokens for the API.
- Admin endpoints protected by role-based access.

Key endpoints
-------------

Public
- POST /api/v1/auth/register
  - Body: { email, password, name }
  - Returns: 201 Created + { user_id }
- POST /api/v1/auth/login
  - Body: { email, password }
  - Returns: { access_token, token_type }
- GET /api/v1/plans
  - List available purchase plans (single report, monthly, yearly)
- POST /api/v1/checkout
  - Create a payment request
  - Body: { plan_id, return_url (frontend), customer_email }
  - Server: create PayNow transaction, create Payment record (PENDING), return { payment_url, payment_id }

Webhooks
- POST /api/v1/webhooks/paynow
  - PayNow will POST status updates here
  - Validate signature, idempotency
  - On success: mark Payment as PAID, create Subscription/Order as required, enqueue delivery task
  - Auth: shared secret (validate payload signature)

Authenticated (user)
- GET /api/v1/dashboard
  - Returns subscription and purchase history
- POST /api/v1/requests/send_report
  - Request an ad-hoc plot delivery (one-off)
  - Body: { symbol, timeframe, email (optional) }
  - Triggers background task to attach generated plot

Admin
- GET /api/v1/admin/payments
  - List payments, filter by status
- POST /api/v1/admin/trigger_delivery
  - Manually trigger delivery for a payment or subscription

Background worker endpoints (internal)
- POST /api/v1/internal/generate_plot
  - Accepts job details, returns job id
- GET /api/v1/internal/job_status/{job_id}

Errors and idempotency
----------------------
- Use idempotency keys for checkout creation (header: Idempotency-Key)
- Webhook must be idempotent: check payment provider transaction id before double-processing

Observability
-------------
- Expose /metrics (Prometheus) and request logging
- Webhook logs kept for audit

OpenAPI docs
------------
FastAPI will auto-generate OpenAPI schema at /docs for dev/testing.