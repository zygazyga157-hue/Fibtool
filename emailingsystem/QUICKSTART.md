# Phase 1 MVP - Quick Start Guide

## What Has Been Built

A complete full-stack application with:

### Backend (FastAPI)
- ✅ User authentication with JWT
- ✅ Database models (Users, Plans, Payments, Subscriptions, Deliveries)
- ✅ REST API endpoints
- ✅ PayNow webhook handler (stubbed)
- ✅ Email service (ready for SMTP config)
- ✅ Plot delivery service

### Frontend (Next.js 14)
- ✅ Marketing homepage
- ✅ Pricing page
- ✅ Login/Register pages
- ✅ User dashboard
- ✅ API integration layer

## Installation & Setup

### 1. Backend Setup

```powershell
cd backend
pip install -r requirements.txt
copy .env.example .env
python init_db.py
uvicorn app.main:app --reload
```

**Default Admin User Created:**
- Email: `admin@fibtool.com`
- Password: `admin123`

**3 Plans Created:**
1. Single Report - $5.00
2. Monthly Subscription - $20.00/month
3. Yearly Subscription - $200.00/year

**Backend Running At:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

### 2. Frontend Setup

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

**Frontend Running At:**
- App: http://localhost:3000

## Testing the Complete Flow

### Step 1: Register a New User
1. Visit http://localhost:3000/register
2. Fill in email, password, and name
3. Click "Register"
4. You'll be auto-logged in and redirected to dashboard

### Step 2: View Plans
1. Click on a plan in the dashboard
2. Click "Buy Now"
3. Note the payment ID shown in the alert

### Step 3: Simulate PayNow Webhook (Mark Payment as PAID)

Since PayNow integration is stubbed, manually trigger the webhook:

```powershell
curl -X POST http://localhost:8000/api/v1/webhooks/paynow -F "reference=YOUR_PAYMENT_ID" -F "paynowreference=PAYNOW-TEST-123" -F "status=paid"
```

Replace `YOUR_PAYMENT_ID` with the actual payment ID from Step 2.

### Step 4: Verify Payment Status
1. Refresh the dashboard
2. You should see the payment marked as "PAID"
3. A delivery record will be created
4. If SMTP is configured, you'll receive an email

## API Testing with Swagger

Visit http://localhost:8000/docs to test all API endpoints interactively:

1. **Register**: POST /api/v1/auth/register
2. **Login**: POST /api/v1/auth/login (copy the access_token)
3. **Authorize**: Click "Authorize" button, paste token
4. **Test Other Endpoints**: Now you can test authenticated endpoints

## Troubleshooting

### Backend Issues

**Import errors:** Make sure all dependencies are installed
```powershell
pip install -r requirements.txt
```

**Database errors:** Reinitialize the database
```powershell
python init_db.py
```

**Port already in use:** Change port in command
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend Issues

**Module not found:** Install dependencies
```powershell
npm install
```

**Can't connect to API:** Check backend is running at http://localhost:8000

**Port already in use:** Next.js will auto-select next available port

## File Structure

```
backend/
├── app/
│   ├── api/              # Endpoints
│   │   ├── auth.py       # Register/Login
│   │   ├── plans.py      # List plans
│   │   ├── payments.py   # Checkout
│   │   ├── webhooks.py   # PayNow webhook
│   │   └── dashboard.py  # User dashboard
│   ├── core/             # Core functionality
│   │   ├── config.py     # Settings
│   │   ├── database.py   # DB connection
│   │   └── security.py   # Auth/JWT
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── paynow.py     # Payment provider
│   │   ├── email.py      # Email sending
│   │   └── delivery.py   # Plot delivery
│   └── main.py           # FastAPI app
├── init_db.py            # DB initialization
└── requirements.txt

frontend/
├── app/
│   ├── dashboard/        # Dashboard page
│   ├── login/            # Login page
│   ├── pricing/          # Pricing page
│   ├── register/         # Register page
│   ├── layout.tsx        # Root layout
│   └── page.tsx          # Homepage
├── lib/
│   └── api.ts            # API client
└── package.json
```

## Environment Variables

### Backend (.env)
- `DATABASE_URL` - Database connection
- `SECRET_KEY` - JWT secret
- `PAYNOW_*` - PayNow credentials
- `SMTP_*` - Email configuration

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` - Backend API URL

## What's Not Implemented (Coming in Phase 2)

- ❌ Actual PayNow API integration (currently stubbed)
- ❌ Webhook signature verification
- ❌ Background task queue (Celery/RQ)
- ❌ Automated plot generation trigger
- ❌ Production email configuration
- ❌ Subscription renewal logic
- ❌ Comprehensive tests
- ❌ Production deployment config

## Next Steps

1. **Test locally** using this guide
2. **Configure SMTP** to enable email sending
3. **Integrate PayNow** API (replace stubs in `services/paynow.py`)
4. **Add tests** for critical flows
5. **Deploy** to production (see DEPLOYMENT.md)

## Support

For detailed information, see:
- `ARCHITECTURE.md` - System design
- `FASTAPI_API_SPEC.md` - Complete API reference
- `PAYMENT_WORKFLOW.md` - Payment flow details
- `SECURITY.md` - Security considerations
