Payment workflow: PayNow (Zimbabwe)
=====================================

Assumptions
-----------
- We will use the PayNow provider available in Zimbabwe (confirm exact vendor: paynow.co.zw or local provider). Before implementation, obtain the provider's API docs and test credentials.

High-level flow
----------------
1. FastAPI `POST /checkout` creates a Payment record (PENDING) with a unique `payment_id` and `idempotency_key`.
2. Server calls PayNow's API to create a transaction and receives a `payment_url` and `paynow_id`.
3. Frontend redirects user to `payment_url` to complete payment.
4. PayNow sends a webhook to `/webhooks/paynow` with `paynow_id`, `status`, and `signature`.
5. Webhook validates signature and paynow_id; if payment successful mark Payment as PAID, attach `provider_reference`, and enqueue delivery.
6. FastAPI sends confirmation email and admin notification.

Implementation notes
--------------------
- Idempotency: store `provider_reference` and skip processing if already seen.
- Signature verification: use provider secret to verify webhook authenticity.
- Retries: respond HTTP 200 quickly to webhook; if processing fails use background job to reconcile.
- Webhook security: restrict by IP/rate-limit and use HMAC signature validation.

Testing
-------
- Use provider sandbox/test mode.
- Simulate slow webhook delivery and duplicated webhooks.

Receipts and invoicing
----------------------
- Store payment receipts (provider payload) and generate simple invoice PDF (optional).
- Email receipt to customer on successful payment.

Fallbacks
---------
- If webhook fails or provider has polling API, use a scheduled reconciler job to query transaction status for PENDING items.