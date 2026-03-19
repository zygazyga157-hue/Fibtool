# Fibtool Frontend DApp

Modern Next.js 14 DApp for the Fibtool decentralized trading signal marketplace, built on Arbitrum.

## 🚀 Features

- **Web3 Integration**: RainbowKit + wagmi for seamless wallet connection
- **Trading Signal Marketplace**: Browse, purchase, and track strategy performance
- **Staking Dashboard**: Stake FIBT tokens for rewards and VIP benefits
- **Governance**: On-chain voting for protocol decisions
- **NFT Minting**: Create strategy NFTs with tiered benefits
- **Real-time Analytics**: Performance charts and portfolio tracking

## 📦 Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Web3**: wagmi v2, viem, RainbowKit
- **State**: Zustand, TanStack Query
- **Charts**: Recharts, Chart.js
- **UI**: Headless UI, React Icons
- **Forms**: React Hook Form + Zod

## 🛠️ Installation

```bash
# Clone the repository
cd web3/frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Update .env.local with your contract addresses
```

## 🔧 Environment Variables

Create `.env.local` with the following:

```env
# Blockchain
NEXT_PUBLIC_CHAIN_ID=42161
NEXT_PUBLIC_RPC_URL=https://arb1.arbitrum.io/rpc

# Contract Addresses (update after deployment)
NEXT_PUBLIC_FIBT_TOKEN_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_NFT_ADDRESS=0x...
NEXT_PUBLIC_STAKING_MANAGER_ADDRESS=0x...
NEXT_PUBLIC_SIGNAL_ESCROW_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_REGISTRY_ADDRESS=0x...
NEXT_PUBLIC_GOVERNANCE_DAO_ADDRESS=0x...

# WalletConnect
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_project_id

# Optional
NEXT_PUBLIC_ALCHEMY_KEY=your_alchemy_key
```

## 🏃‍♂️ Development

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Type check
npm run type-check

# Lint
npm run lint
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js 14 app directory
│   │   ├── page.tsx           # Landing page
│   │   ├── marketplace/       # Strategy marketplace
│   │   ├── staking/           # Staking dashboard
│   │   ├── governance/        # Governance voting
│   │   └── profile/           # User portfolio
│   ├── components/            # React components
│   │   ├── TokenBalance.tsx
│   │   ├── StrategyCard.tsx
│   │   ├── StakingWidget.tsx
│   │   └── ...
│   ├── hooks/                 # Custom hooks
│   │   ├── useToken.ts
│   │   ├── useStaking.ts
│   │   ├── useNFT.ts
│   │   └── ...
│   ├── contracts/             # ABIs and addresses
│   │   └── abis.ts
│   ├── providers/             # Context providers
│   │   └── Web3Provider.tsx
│   └── utils/                 # Utility functions
│       └── helpers.ts
├── public/                    # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## 🎨 Pages

### Home (`/`)
- Hero section with call-to-action
- Platform statistics
- Feature highlights
- Wallet connection

### Marketplace (`/marketplace`)
- Browse all trading strategies
- Filter by category and performance
- View detailed strategy metrics
- Purchase signals with FIBT

### Staking (`/staking`)
- 4-tier staking system (Bronze → Platinum)
- APY: 5% → 15%
- Auto-compound option
- Claim rewards dashboard

### Governance (`/governance`)
- View active proposals
- Cast votes (weighted by FIBT holdings)
- Proposal creation (requires threshold)
- Execution tracking

### Profile (`/profile`)
- Portfolio overview
- Active signals
- Staking position
- Transaction history
- VIP tier status

## 🔐 Smart Contract Integration

### Token Operations
```typescript
import { useToken } from '@/hooks/useToken';

const { balance, approve, isApproving } = useToken();

// Approve spending
await approve(CONTRACTS.STAKING_MANAGER, '1000');
```

### Staking
```typescript
import { useStaking } from '@/hooks/useStaking';

const { stake, unstake, claimRewards, pendingRewards } = useStaking();

// Stake tokens
await stake('1000', 1, true); // amount, tier, autoCompound
```

### NFT Minting
```typescript
import { useNFT } from '@/hooks/useNFT';

const { mintNFT } = useNFT();

// Mint strategy NFT
await mintNFT(1, 'ipfs://metadata');
```

## 📊 Data Flow

1. **Wallet Connection**: RainbowKit handles wallet connection
2. **Contract Calls**: wagmi hooks interact with smart contracts
3. **State Management**: TanStack Query caches blockchain data
4. **UI Updates**: React re-renders on state changes

## 🎨 Styling

- **Tailwind CSS**: Utility-first styling
- **Custom Theme**: Primary (blue), Accent (yellow), Success (green)
- **Dark Mode**: Default dark theme optimized for crypto UIs
- **Glass Morphism**: Modern glassmorphism effects
- **Animations**: Smooth transitions and hover effects

## 🚢 Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

### Manual Build

```bash
npm run build
npm start
```

## 🔒 Security Considerations

- All contract addresses are environment variables
- No private keys in frontend code
- User approvals required for all transactions
- Transaction simulation before execution
- Clear error messages for failed transactions

## 📱 Responsive Design

- Mobile-first approach
- Breakpoints: sm (640px), md (768px), lg (1024px), xl (1280px)
- Touch-optimized interactions
- Progressive Web App ready

## 🌐 Browser Support

- Chrome/Edge (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Mobile browsers (iOS Safari, Chrome Android)

## 🧪 Testing

```bash
# Unit tests (to be implemented)
npm test

# E2E tests (to be implemented)
npm run test:e2e
```

## 📈 Performance

- Lighthouse score target: 90+
- Core Web Vitals optimized
- Image optimization with Next.js Image
- Code splitting for faster loads
- Service worker for offline functionality

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

See LICENSE file in project root.

## 🆘 Support

- Documentation: https://docs.fibtool.io
- Discord: https://discord.gg/fibtool
- Twitter: @FibtoolHQ
- Email: support@fibtool.io

## 🗺️ Roadmap

- [ ] Mobile app (React Native)
- [ ] Advanced charting (TradingView integration)
- [ ] Social features (follow traders, leaderboards)
- [ ] API for third-party integrations
- [ ] Multi-chain support (Ethereum, Polygon)
- [ ] Fiat on-ramp integration

---

Built with ❤️ by the Fibtool team
