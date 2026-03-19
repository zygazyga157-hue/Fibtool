Frontend (Next.js) flow
========================

Pages and routes
----------------
- /               — marketing home
- /pricing        — list plans (one-off vs subscription)
- /checkout       — checkout page which requests `payment_url` from backend and redirects
- /dashboard      — authenticated user area: subscriptions, past purchases, download links
- /account       — profile, payment methods (if supported)
- /webhook-return — landing page after payment (reads status from backend)

Checkout UX
-----------
1. User selects plan and enters email (or signs in).
2. Frontend calls `POST /api/v1/checkout` with plan info and receives `payment_url`.
3. Redirect to `payment_url` (PayNow gateway) — user completes payment outside site.
4. Provider redirects back to `return_url` (optional). Final status via webhook; frontend shows "Payment pending" then polls backend for final status.

Dashboard
---------
- List of purchased reports with download links
- Subscription status and cancellation button
- Billing history

Auth
----
- Use JWT stored in an HttpOnly cookie (or secure local storage) for authenticated pages.
- Social login could be added later but keep MVP simple (email/password and magic link optional).

Client-side considerations
-------------------------
- Minimal client-side state; use server-side rendering for SEO pages.
- Polling/push: after returning from payment, poll `GET /api/v1/payment_status/{payment_id}` until final state.

Notifications
-------------
- Show in-app notifications for delivered reports
- Optional email confirmations handled by backend

Payment security
----------------
- Do not store raw payment details client-side
- Ensure return_url is validated/tied to a specific payment session (server-side)