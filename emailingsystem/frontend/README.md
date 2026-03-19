# Fibtool Frontend

Next.js 14 frontend for the Fibtool subscription platform.

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Copy `.env.example` to `.env.local`:

```bash
copy .env.example .env.local
```

Edit `.env.local` with your API URL (defaults to `http://localhost:8000`).

### 3. Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

## Pages

- `/` - Marketing home page
- `/pricing` - Plans and pricing
- `/login` - User login
- `/register` - User registration
- `/dashboard` - User dashboard (authenticated)

## Project Structure

```
frontend/
├── app/
│   ├── dashboard/     # Dashboard page
│   ├── login/         # Login page
│   ├── pricing/       # Pricing page
│   ├── register/      # Registration page
│   ├── layout.tsx     # Root layout
│   ├── page.tsx       # Home page
│   └── globals.css    # Global styles
├── components/        # Reusable components
├── lib/
│   └── api.ts        # API client
├── package.json
└── tsconfig.json
```

## API Integration

The frontend communicates with the FastAPI backend at `http://localhost:8000` by default.

All API calls are made through the `lib/api.ts` module which handles:
- JWT token management
- Request/response formatting
- Error handling

## Building for Production

```bash
npm run build
npm start
```

## TypeScript

The project uses TypeScript for type safety. Run type checking with:

```bash
npx tsc --noEmit
```
