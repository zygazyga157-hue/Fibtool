Database schema (initial)
===========================

Use PostgreSQL in production; SQLite for local dev.

Tables
------

users
- id (uuid, pk)
- email (unique)
- password_hash
- name
- is_active
- is_admin
- created_at

plans
- id (uuid)
- name
- type (one-off|subscription)
- price (in smallest currency unit, e.g., cents)
- currency (ZWL or USD)
- interval (monthly/yearly/null)
- description

payments
- id (uuid)
- user_id (fk users)
- plan_id (fk plans)
- amount
- currency
- status (PENDING | PAID | FAILED | CANCELLED)
- provider ("paynow")
- provider_reference (string)
- idempotency_key
- payload (json) -- raw provider response
- created_at
- paid_at

subscriptions
- id (uuid)
- user_id
- plan_id
- status (ACTIVE | CANCELLED | PAST_DUE)
- started_at
- cancelled_at

deliveries
- id (uuid)
- payment_id (fk payments)
- user_id
- symbol
- timeframe
- file_path (storage path)
- email_sent_at
- status (PENDING | SENT | FAILED)
- created_at

audit_logs
- id
- event_type
- payload (json)
- created_at

Indexes
- payments.provider_reference (unique)
- payments.idempotency_key

Notes
-----
- Use UUIDs for public-facing ids where possible.
- Keep raw provider payloads for audit and dispute handling.