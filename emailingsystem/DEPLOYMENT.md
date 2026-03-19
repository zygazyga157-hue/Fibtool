Deployment & Ops
==================

Containers
----------
- Backend: FastAPI container (uvicorn + gunicorn or uvicorn workers)
- Frontend: Next.js container
- DB: Postgres (managed or container)
- Storage: S3 or MinIO
- Worker: Celery/RQ or a lightweight background runner for plot generation and email sending

Docker
------
- Provide Dockerfiles for backend and frontend
- Provide docker-compose for local dev (Postgres, MinIO, backend, frontend)

CI/CD
-----
- Use GitHub Actions to run tests, lint, build images, and deploy to staging
- Secrets stored in repo secrets

Hosting
-------
- Frontend: Vercel or Netlify (for Next.js) or container on VPS
- Backend: Cloud VM, DigitalOcean App Platform, or managed container service
- DB: Managed Postgres (Heroku, Supabase) recommended for reliability

Monitoring
----------
- Logs to central sink (Papertrail/CloudWatch)
- Metrics via Prometheus/Grafana, or a hosted provider

Backups
-------
- Regular DB backups
- Retention policy for stored plot files

Scaling notes
-------------
- Email delivery and plot generation are the main CPU/IO tasks — run them in a worker pool and autoscale if necessary.
- Payment webhook traffic is low; keep webhook endpoint robust and idempotent.