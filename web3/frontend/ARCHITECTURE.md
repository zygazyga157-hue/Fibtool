# Fibtool Frontend Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FIBTOOL FRONTEND DAPP                         │
│                         Next.js 14 + TypeScript                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
        ┌───────────▼──────────┐        ┌──────────▼───────────┐
        │   CLIENT BROWSER     │        │   BLOCKCHAIN LAYER   │
        │                      │        │                      │
        │  ┌────────────────┐  │        │  ┌────────────────┐ │
        │  │  React 18.2.0  │  │        │  │ Arbitrum One   │ │
        │  │  (Components)  │  │        │  │   (Chain)      │ │
        │  └────────────────┘  │        │  └────────────────┘ │
        │          │            │        │          │          │
        │  ┌────────────────┐  │        │  ┌────────────────┐ │
        │  │ Web3 Provider  │◄─┼────────┼──┤  RPC Endpoint  │ │
        │  │   (wagmi v2)   │  │        │  │  (Alchemy)     │ │
        │  └────────────────┘  │        │  └────────────────┘ │
        │          │            │        │          │          │
        │  ┌────────────────┐  │        │  ┌────────────────┐ │
        │  │  RainbowKit    │  │        │  │ Smart Contracts│ │
        │  │ (Wallet UI)    │  │        │  │   (11 total)   │ │
        │  └────────────────┘  │        │  └────────────────┘ │
        └──────────────────────┘        └──────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                            PAGE STRUCTURE                               │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │   Home   │     │Marketplace│    │ Strategy │     │ Staking  │
    │  Page    │────▶│  Browse  │────▶│  Detail  │     │Dashboard │
    │   (/)    │     │          │     │  +Charts │     │          │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘
         │                                                     │
         ▼                                                     ▼
    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │Governance│     │ Profile  │     │   NFTs   │     │Analytics │
    │  Voting  │     │Portfolio │     │ Gallery  │     │Dashboard │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPONENT HIERARCHY                             │
└─────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────┐
                        │  RootLayout     │
                        │  (layout.tsx)   │
                        └────────┬────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
        ┌───────▼──────┐              ┌──────────▼─────────┐
        │ Web3Provider │              │NotificationProvider│
        │  (wagmi)     │              │   (Context)        │
        └───────┬──────┘              └──────────┬─────────┘
                │                                 │
                └──────────────┬──────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │         Navbar              │
                │  (with NotificationBell)    │
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │       Page Content          │
                │   (Dynamic Routes)          │
                └─────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW DIAGRAM                               │
└─────────────────────────────────────────────────────────────────────────┘

User Action                Contract Interaction              UI Update
    │                             │                              │
    │  1. Click "Stake"          │                              │
    ├───────────────────────────▶│                              │
    │                             │  2. Call contract.stake()   │
    │                             ├─────────────────────────────▶│
    │                             │                              │
    │                             │  3. Send transaction         │
    │                             │     (via MetaMask)           │
    │                             │◀─────────────────────────────┤
    │                             │                              │
    │                             │  4. Transaction pending...   │
    │                             ├─────────────────────────────▶│
    │                             │     (show loading)           │
    │                             │                              │
    │  5. Transaction confirmed  │                              │
    │◀────────────────────────────┤                              │
    │                             │  6. Query new balance        │
    │                             ├─────────────────────────────▶│
    │                             │     (useReadContract)        │
    │                             │                              │
    │                             │  7. Update UI                │
    │                             │     (show success toast)     │
    │◀────────────────────────────┴──────────────────────────────┤
    │                                                            │

┌─────────────────────────────────────────────────────────────────────────┐
│                    SMART CONTRACT INTEGRATION                           │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   FIBTToken      │      │  StrategyNFT     │      │StakingManager    │
│   (ERC20)        │      │   (ERC721)       │      │  (Staking)       │
└────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                         │                         │
         │  balanceOf()           │  mint()                 │  stake()
         │  approve()             │  ownerOf()              │  unstake()
         │  transfer()            │  tokenURI()             │  claimRewards()
         │                         │                         │
         └─────────────────────────┴─────────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │   wagmi Hooks     │
                         │  (React Bridge)   │
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
          ┌─────────▼────────┐    │    ┌────────▼─────────┐
          │ useReadContract  │    │    │ useWriteContract │
          │  (Read Data)     │    │    │  (Transactions)  │
          └──────────────────┘    │    └──────────────────┘
                                  │
                        ┌─────────▼────────┐
                        │  useAccount      │
                        │ (Wallet State)   │
                        └──────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      NOTIFICATION SYSTEM FLOW                           │
└─────────────────────────────────────────────────────────────────────────┘

    Event Source                Notification Provider           User UI
        │                              │                          │
        │  1. New Signal Posted       │                          │
        ├─────────────────────────────▶│                          │
        │                              │  2. Add to queue         │
        │                              │     (localStorage)       │
        │                              ├─────────────────────────▶│
        │                              │  3. Show toast           │
        │                              │     (react-hot-toast)    │
        │                              │                          │
        │                              │  4. Browser notification │
        │                              │     (if permitted)       │
        │                              ├─────────────────────────▶│
        │                              │                          │
        │  5. User clicks notification│                          │
        │◀─────────────────────────────┴──────────────────────────┤
        │  6. Navigate to actionUrl                              │
        │                                                         │

┌─────────────────────────────────────────────────────────────────────────┐
│                         PWA ARCHITECTURE                                │
└─────────────────────────────────────────────────────────────────────────┘

    Browser                   Service Worker              Cache Storage
       │                            │                          │
       │  1. Request page          │                          │
       ├───────────────────────────▶│                          │
       │                            │  2. Check cache          │
       │                            ├─────────────────────────▶│
       │                            │  3. Return if cached     │
       │                            │◀─────────────────────────┤
       │  4. Serve cached page     │                          │
       │◀───────────────────────────┤                          │
       │                            │                          │
       │  5. If not cached...      │                          │
       │                            │  6. Fetch from network   │
       │                            │                          │
       │                            │  7. Store in cache       │
       │                            ├─────────────────────────▶│
       │  8. Serve fresh page      │                          │
       │◀───────────────────────────┤                          │
       │                            │                          │

┌─────────────────────────────────────────────────────────────────────────┐
│                    STATE MANAGEMENT LAYERS                              │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        Global State (Zustand)                        │
│  - User preferences                                                  │
│  - Theme settings                                                    │
│  - UI state (modals, dropdowns)                                      │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌──────────────────────────────▼────────────────────────────────────────┐
│                   Server State (TanStack Query)                       │
│  - Blockchain data (cached)                                          │
│  - Contract reads (auto-refetch)                                     │
│  - Real-time updates                                                 │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌──────────────────────────────▼────────────────────────────────────────┐
│                    Local State (useState/useReducer)                  │
│  - Form inputs                                                       │
│  - Component-specific state                                          │
│  - Temporary UI state                                                │
└──────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT PIPELINE                             │
└─────────────────────────────────────────────────────────────────────────┘

Local Dev          Git Push            CI/CD             Production
    │                  │                  │                   │
    │  npm run dev    │                  │                   │
    ├─────────────────▶│                  │                   │
    │                  │  Push to GitHub │                   │
    │                  ├─────────────────▶│                   │
    │                  │                  │  Run tests        │
    │                  │                  │  Build project    │
    │                  │                  │  Type check       │
    │                  │                  │                   │
    │                  │                  │  Deploy to Vercel │
    │                  │                  ├──────────────────▶│
    │                  │                  │                   │
    │                  │                  │  Live! 🚀         │
    │                  │                  │                   │

┌─────────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────┘

    User Input             Validation Layer         Contract Call
        │                        │                        │
        │  1. Form submit       │                        │
        ├───────────────────────▶│                        │
        │                        │  2. Zod validation    │
        │                        │     (schema check)    │
        │                        │                        │
        │                        │  3. Sanitize input    │
        │                        │     (XSS protection)  │
        │                        │                        │
        │                        │  4. Check allowance   │
        │                        │     (for tokens)      │
        │                        ├───────────────────────▶│
        │                        │  5. Send transaction  │
        │                        │     (via MetaMask)    │
        │                        │                        │
        │  6. Await confirmation│                        │
        │◀───────────────────────┴────────────────────────┤
        │                                                 │

┌─────────────────────────────────────────────────────────────────────────┐
│                     PERFORMANCE OPTIMIZATION                            │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  Code Splitting  │  → Dynamic imports for heavy components
└──────────────────┘
┌──────────────────┐
│  Lazy Loading    │  → Load images/charts only when visible
└──────────────────┘
┌──────────────────┐
│  Memoization     │  → useMemo/React.memo for expensive renders
└──────────────────┘
┌──────────────────┐
│  Query Caching   │  → TanStack Query caches blockchain reads
└──────────────────┘
┌──────────────────┐
│  Image Optimize  │  → Next.js Image with WebP
└──────────────────┘
┌──────────────────┐
│  Tree Shaking    │  → Remove unused code in build
└──────────────────┘

Target: 90+ Lighthouse Score ⚡
```

**Architecture Summary:**

- **Frontend**: Next.js 14 + React 18 + TypeScript
- **Web3**: wagmi v2 + RainbowKit + viem
- **State**: TanStack Query (server) + Zustand (global)
- **UI**: Tailwind CSS + Headless UI
- **Charts**: Chart.js + react-chartjs-2
- **PWA**: Service Worker + Manifest
- **Notifications**: Browser API + localStorage
- **Blockchain**: Arbitrum One (11 contracts)

**Data Flow**: User → UI → wagmi → RPC → Smart Contracts → Events → UI Update

**Built for**: Speed, Security, Scalability
