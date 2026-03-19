# Fibtool Backend API

FastAPI backend for the Fibtool subscription and payment system.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update the values:

```bash
copy .env.example .env
```

Edit `.env` with your actual credentials.

### 3. Initialize Database

```bash
python init_db.py
```

This will:
- Create all database tables
- Seed initial plans (Single Report, Monthly, Yearly)
- Create admin user (admin@fibtool.com / admin123)

### 4. Run Development Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Key Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/me` - Get current user info

### Plans
- `GET /api/v1/plans` - List all available plans

### Payments
- `POST /api/v1/checkout` - Create payment and get payment URL
- `GET /api/v1/payment/{payment_id}` - Get payment status

### Webhooks
- `POST /api/v1/webhooks/paynow` - PayNow webhook endpoint

### Dashboard
- `GET /api/v1/dashboard` - Get user dashboard data

## Testing the Flow

### 1. Register a User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123",
    "name": "Test User"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123"
  }'
```

### 3. Get Plans
```bash
curl http://localhost:8000/api/v1/plans
```

### 4. Create Checkout
```bash
curl -X POST http://localhost:8000/api/v1/checkout \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "plan_id": "PLAN_ID",
    "return_url": "http://localhost:3000/payment-return"
  }'
```

## Project Structure

```
backend/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # Core configuration and security
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic services
│   └── main.py       # FastAPI app entry point
├── init_db.py        # Database initialization script
├── requirements.txt  # Python dependencies
├── Dockerfile        # Docker configuration
└── .env.example      # Environment variables template
```

## TODO for Production

- [ ] Implement actual PayNow API integration
- [ ] Add webhook signature verification
- [ ] Implement background task queue (Celery/RQ)
- [ ] Add rate limiting
- [ ] Implement proper logging
- [ ] Add monitoring and metrics
- [ ] Set up proper SMTP/email service
- [ ] Add comprehensive tests
