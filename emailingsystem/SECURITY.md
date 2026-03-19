Security, privacy and compliance notes
======================================

Secrets and env
- Store secrets in environment variables and never commit them.
- Required secrets: DB URL, JWT secret, PayNow API key/secret, SMTP credentials, admin Telegram webhook token.

Authentication
- Hash passwords using Argon2 or bcrypt.
- Use JWTs with short expiry for access tokens and refresh tokens if needed.
- Store tokens in HttpOnly, Secure cookies for the dashboard.

Payment data
- Do NOT store card data or payment credentials. For PayNow we only store provider references and receipts.
- Follow provider's PCI guidance (we are not a card processor; PayNow handles payments).

Webhooks
- Validate webhook signatures using HMAC and provider secret.
- Use idempotency to avoid double-processing webhooks.

Emails
- Avoid leaking user lists; use BCC carefully or use a transactional provider.

Operational security
- Rate limit public endpoints (checkout, auth)
- Monitor logs and webhook failures
- Maintain an audit trail for payments and deliveries

Privacy
- Store minimal PII (email, name); allow users to request deletion (implement GDPR-like process even if not required).

Admin access
- Protect admin endpoints with role checks; consider IP allowlist for management actions.

Deployment
- Use HTTPS for all traffic.
- Use secrets manager if available (AWS Secrets Manager, Azure KeyVault) for production.