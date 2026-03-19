# Fibtool Frontend DApp - Deployment Guide

## 🚀 Complete Deployment Instructions

### Prerequisites
- Node.js 18+ installed
- Arbitrum RPC URL (Alchemy or Infura)
- Deployed smart contract addresses
- MetaMask or compatible wallet

---

## 📦 Installation

```bash
cd web3/frontend
npm install
```

---

## ⚙️ Configuration

### 1. Environment Variables

Create `.env.local` file:

```bash
# App Configuration
NEXT_PUBLIC_APP_NAME=Fibtool
NEXT_PUBLIC_ENABLE_TESTNET=false

# Blockchain RPC
NEXT_PUBLIC_ARBITRUM_RPC_URL=https://arb1.arbitrum.io/rpc
NEXT_PUBLIC_ARBITRUM_TESTNET_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc

# Chain IDs
NEXT_PUBLIC_CHAIN_ID=42161
NEXT_PUBLIC_TESTNET_CHAIN_ID=421614

# Smart Contract Addresses (UPDATE THESE AFTER DEPLOYMENT)
NEXT_PUBLIC_FIBT_TOKEN_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_NFT_ADDRESS=0x...
NEXT_PUBLIC_STAKING_MANAGER_ADDRESS=0x...
NEXT_PUBLIC_SIGNAL_ESCROW_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_REGISTRY_ADDRESS=0x...
NEXT_PUBLIC_REVENUE_DISTRIBUTOR_ADDRESS=0x...
NEXT_PUBLIC_GOVERNANCE_DAO_ADDRESS=0x...
NEXT_PUBLIC_PRICE_ORACLE_ADDRESS=0x...
NEXT_PUBLIC_MT5_ORACLE_ADDRESS=0x...
NEXT_PUBLIC_PERFORMANCE_VERIFIER_ADDRESS=0x...
NEXT_PUBLIC_VIP_TIER_MANAGER_ADDRESS=0x...

# WalletConnect Project ID (Get from https://cloud.walletconnect.com)
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_project_id_here

# Optional: Analytics
NEXT_PUBLIC_GA_TRACKING_ID=G-XXXXXXXXXX
```

### 2. Update Contract Addresses

After deploying smart contracts, update addresses in `src/contracts/abis.ts`:

```typescript
export const FIBT_TOKEN_ADDRESS = process.env.NEXT_PUBLIC_FIBT_TOKEN_ADDRESS as `0x${string}`;
export const STRATEGY_NFT_ADDRESS = process.env.NEXT_PUBLIC_STRATEGY_NFT_ADDRESS as `0x${string}`;
// ... etc
```

---

## 🧪 Development

```bash
# Run development server
npm run dev

# Open http://localhost:3000
```

### Development Features
- Hot reload
- TypeScript type checking
- Real-time error reporting
- Mock notification simulator

---

## 🏗️ Build

```bash
# Type check
npm run type-check

# Build production bundle
npm run build

# Test production build locally
npm start
```

---

## 🌐 Deployment Options

### Option 1: Vercel (Recommended)

1. **Install Vercel CLI**
```bash
npm install -g vercel
```

2. **Login to Vercel**
```bash
vercel login
```

3. **Deploy**
```bash
vercel
```

4. **Set Environment Variables**
```bash
vercel env add NEXT_PUBLIC_FIBT_TOKEN_ADDRESS
vercel env add NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID
# ... add all env variables
```

5. **Production Deployment**
```bash
vercel --prod
```

### Option 2: Netlify

1. **Install Netlify CLI**
```bash
npm install -g netlify-cli
```

2. **Build**
```bash
npm run build
```

3. **Deploy**
```bash
netlify deploy --prod
```

### Option 3: IPFS/Fleek (Decentralized)

1. **Build**
```bash
npm run build
npm run export
```

2. **Upload to IPFS**
```bash
fleek site:deploy
```

### Option 4: Self-Hosted (VPS)

```bash
# On your server
git clone <repo>
cd web3/frontend
npm install
npm run build

# Install PM2
npm install -g pm2

# Start with PM2
pm2 start npm --name "fibtool-frontend" -- start
pm2 save
pm2 startup

# Setup Nginx reverse proxy
# /etc/nginx/sites-available/fibtool
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## 📱 PWA Setup

### Generate Icons

Install icon generator:
```bash
npm install -g pwa-asset-generator
```

Generate icons from your logo:
```bash
pwa-asset-generator logo.png public/icons --type png
```

### Test PWA

1. Build production version
2. Serve locally: `npm start`
3. Open Chrome DevTools > Application > Manifest
4. Check "Service Workers" tab
5. Test "Add to Home Screen"

### PWA Checklist
- ✅ manifest.json configured
- ✅ Service worker (sw.js) registered
- ✅ Icons (72x72 to 512x512)
- ✅ HTTPS enabled (required for PWA)
- ✅ Offline fallback page
- ✅ Push notification support

---

## 🔔 Notification System

### Browser Permissions

Request notification permission on first visit:
```typescript
if ('Notification' in window) {
  Notification.requestPermission();
}
```

### Test Notifications

```typescript
import { useNotifications } from '@/providers/NotificationProvider';

const { addNotification } = useNotifications();

addNotification({
  type: 'signal',
  title: 'New Signal',
  message: 'EURUSD Buy signal available',
  actionUrl: '/marketplace/1',
});
```

---

## 📊 Analytics Integration

### Google Analytics

```typescript
// src/lib/analytics.ts
export const GA_TRACKING_ID = process.env.NEXT_PUBLIC_GA_TRACKING_ID;

export const pageview = (url: string) => {
  window.gtag('config', GA_TRACKING_ID, {
    page_path: url,
  });
};
```

Add to layout.tsx:
```typescript
import Script from 'next/script';

<Script
  src={`https://www.googletagmanager.com/gtag/js?id=${GA_TRACKING_ID}`}
  strategy="afterInteractive"
/>
```

---

## 🧪 Testing

### Unit Tests
```bash
npm test
```

### E2E Tests (Playwright)
```bash
npm run test:e2e
```

### Test Coverage
```bash
npm run test:coverage
```

---

## 🔐 Security Checklist

- [ ] All environment variables set
- [ ] Contract addresses verified
- [ ] HTTPS enabled
- [ ] Content Security Policy configured
- [ ] Rate limiting on API routes
- [ ] Input validation on all forms
- [ ] XSS protection enabled
- [ ] CORS properly configured
- [ ] Dependencies audited: `npm audit`

---

## 🚦 Performance Optimization

### Lighthouse Score Goals
- Performance: 90+
- Accessibility: 95+
- Best Practices: 95+
- SEO: 100

### Optimization Tips

1. **Image Optimization**
```typescript
import Image from 'next/image';

<Image
  src="/logo.png"
  width={200}
  height={50}
  alt="Fibtool"
  priority
/>
```

2. **Code Splitting**
```typescript
import dynamic from 'next/dynamic';

const Chart = dynamic(() => import('./Chart'), { ssr: false });
```

3. **Caching**
```typescript
// next.config.js
headers: [
  {
    source: '/:all*(svg|jpg|png)',
    headers: [
      {
        key: 'Cache-Control',
        value: 'public, max-age=31536000, immutable',
      },
    ],
  },
],
```

---

## 📈 Monitoring

### Vercel Analytics
```bash
npm install @vercel/analytics
```

```typescript
import { Analytics } from '@vercel/analytics/react';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

### Error Tracking (Sentry)
```bash
npm install @sentry/nextjs
```

```typescript
// sentry.client.config.ts
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 1.0,
});
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions

`.github/workflows/deploy.yml`:
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm ci
      - run: npm run build
      - run: npm run test
      - uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.ORG_ID }}
          vercel-project-id: ${{ secrets.PROJECT_ID }}
```

---

## 🐛 Troubleshooting

### Common Issues

**1. RainbowKit Connection Error**
- Check WalletConnect Project ID
- Verify chain ID matches network
- Clear browser cache

**2. Contract Read Errors**
- Verify contract addresses
- Check RPC URL is working
- Ensure contracts are deployed

**3. Build Errors**
- Run `npm run type-check`
- Check TypeScript errors
- Verify all imports

**4. PWA Not Installing**
- Must use HTTPS (localhost exempt)
- Check manifest.json syntax
- Verify service worker registered

---

## 📚 Additional Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [wagmi Documentation](https://wagmi.sh)
- [RainbowKit Docs](https://www.rainbowkit.com)
- [Arbitrum Docs](https://docs.arbitrum.io)
- [Chart.js Docs](https://www.chartjs.org)

---

## 🎯 Post-Deployment Checklist

- [ ] All pages load correctly
- [ ] Wallet connection works
- [ ] Contract interactions functional
- [ ] Notifications working
- [ ] PWA installable
- [ ] Mobile responsive
- [ ] Analytics tracking
- [ ] Error monitoring active
- [ ] SSL certificate valid
- [ ] Domain configured
- [ ] SEO meta tags present
- [ ] Social media cards working

---

## 📞 Support

For issues or questions:
- GitHub Issues
- Discord: [Join Server]
- Email: support@fibtool.io

---

**Built with ❤️ by the Fibtool Team**
