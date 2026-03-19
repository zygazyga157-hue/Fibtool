# ⚡ Fibtool Frontend - Quick Start

Get your DApp running in 5 minutes!

---

## 🚀 Installation

```bash
cd web3/frontend
npm install
```

---

## ⚙️ Configuration

1. **Copy environment file**
```bash
cp .env.example .env.local
```

2. **Add your WalletConnect Project ID**

Get one free at: https://cloud.walletconnect.com

```bash
# .env.local
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_project_id_here
```

3. **Update contract addresses** (after deployment)
```bash
NEXT_PUBLIC_FIBT_TOKEN_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_NFT_ADDRESS=0x...
# ... etc
```

---

## 🏃 Run Development Server

```bash
npm run dev
```

Open **http://localhost:3000** 🎉

---

## 📱 Test PWA

1. Build production version:
```bash
npm run build
npm start
```

2. Open Chrome DevTools (F12)
3. Go to **Application** > **Manifest**
4. Click **"Add to Home Screen"**

---

## 🔔 Test Notifications

Notifications automatically simulate every 30 seconds in dev mode!

Look for the bell icon 🔔 in the navbar.

---

## 📊 Available Pages

- **/** - Landing page
- **/marketplace** - Browse strategies
- **/marketplace/1** - Strategy detail (Chart.js demo)
- **/staking** - Staking dashboard
- **/governance** - Voting & proposals
- **/profile** - User portfolio
- **/nfts** - NFT collection
- **/analytics** - Analytics dashboard

---

## 🧪 Test Features

### 1. Wallet Connection
- Click "Connect Wallet" in navbar
- Select MetaMask (or any wallet)
- Approve connection

### 2. View Token Balance
- Navigate to any page
- See FIBT balance in profile

### 3. Staking Widget
- Go to **/staking**
- Select tier (Bronze/Silver/Gold/Platinum)
- Enter amount
- Click "Stake FIBT"

### 4. Browse Strategies
- Go to **/marketplace**
- Use search bar
- Filter by category
- Click card to see details

### 5. Vote on Proposals
- Go to **/governance**
- Click "Vote For" or "Vote Against"
- Confirm transaction

### 6. Notifications
- Click bell icon in navbar
- See recent notifications
- Click notification to navigate

### 7. PWA Install
- Build production
- Visit site on mobile
- Tap "Add to Home Screen"

---

## 🐛 Troubleshooting

### "Cannot find module 'react'" error
Run: `npm install`

### Wallet won't connect
1. Check WalletConnect Project ID in `.env.local`
2. Make sure MetaMask is installed
3. Try refreshing page

### Contract read errors
1. Verify contract addresses in `.env.local`
2. Check you're on correct network (Arbitrum)
3. Ensure contracts are deployed

### PWA not installing
1. Must use HTTPS (or localhost)
2. Check manifest.json is accessible
3. Verify service worker registered

---

## 📚 Documentation

- **Full Deployment Guide**: See `DEPLOYMENT.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Main README**: See `README.md`

---

## 🎯 Next Steps

1. ✅ Install dependencies
2. ✅ Configure environment
3. ✅ Run dev server
4. ✅ Test all pages
5. ⏭️ Deploy contracts
6. ⏭️ Update contract addresses
7. ⏭️ Deploy frontend
8. ⏭️ Enable PWA
9. ⏭️ Go live! 🚀

---

## 💡 Pro Tips

- Use **Chrome DevTools** > **Application** to debug PWA
- Use **Network** tab to see contract calls
- Enable **React DevTools** for component debugging
- Check **Console** for error messages
- Use **Lighthouse** to test performance

---

**Need Help?**
- Check DEPLOYMENT.md for detailed instructions
- Review code comments in source files
- Test with mock data before connecting real contracts

**Happy Building! 🎉**
