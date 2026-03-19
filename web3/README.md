# Fibtool Smart Contracts 🔐

Complete suite of 11 smart contracts for the Fibtool decentralized trading signal marketplace on Arbitrum.

---

## 📦 Contracts Overview

### Core Token & NFT
1. **FIBTToken** - ERC20 governance and utility token
2. **StrategyNFT** - ERC721 NFTs representing strategy ownership

### Staking & Rewards
3. **StakingManager** - Stake FIBT tokens for rewards (4 tiers)
4. **VIPTierManager** - VIP tier management and fee discounts

### Oracles & Verification
5. **PriceOracle** - Price feed aggregation
6. **MT5Oracle** - MT5 trading data verification
7. **PerformanceVerifier** - On-chain performance validation

### Core Protocol
8. **StrategyRegistry** - Strategy listing and management
9. **SignalEscrow** - Trustless signal payments with escrow
10. **RevenueDistributor** - Revenue sharing and token buyback
11. **GovernanceDAO** - Decentralized governance

---

## 🚀 Quick Start

### Install
```powershell
npm install
```

### Compile
```powershell
npm run compile
```

### Deploy to Testnet
```powershell
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your private key and API keys

# 3. Deploy
npm run deploy:testnet
```

### Verify Contracts
```powershell
npm run verify:testnet
```

---

## 📋 Available Scripts

```powershell
npm run compile         # Compile all contracts
npm run test           # Run tests
npm run deploy:testnet # Deploy to Arbitrum Sepolia
npm run deploy:mainnet # Deploy to Arbitrum One
npm run verify:testnet # Verify on Arbiscan (testnet)
npm run verify:mainnet # Verify on Arbiscan (mainnet)
npm run flatten        # Flatten contracts for verification
```

---

## 🏗️ Architecture

```
User
  │
  ├─→ FIBTToken (ERC20)
  │     └─→ StakingManager → RevenueDistributor
  │     └─→ GovernanceDAO
  │
  ├─→ StrategyNFT (ERC721)
  │     └─→ StrategyRegistry
  │           └─→ PerformanceVerifier
  │                 ├─→ PriceOracle
  │                 └─→ MT5Oracle
  │
  └─→ SignalEscrow
        ├─→ StrategyRegistry
        └─→ VIPTierManager
```

---

## 📊 Contract Details

### FIBTToken
- **Type**: ERC20 with burning
- **Supply**: 100M max (25M initial)
- **Features**: Trading toggle, whitelist, mintable

### StrategyNFT
- **Type**: ERC721 with URI storage
- **Tiers**: Basic, Premium, Elite
- **Features**: Metadata, enumeration, access control

### StakingManager
- **Tiers**: Bronze (5%), Silver (8%), Gold (12%), Platinum (15%)
- **Min Stakes**: 1K, 5K, 20K, 100K FIBT
- **Features**: Auto-compound, flexible unstaking

### SignalEscrow
- **Features**: Pay-per-performance, escrow, VIP discounts
- **Settlement**: Automated after TP/SL hit

### GovernanceDAO
- **Quorum**: 10% of total supply
- **Delay**: 1 day voting, 2 day execution
- **Features**: Proposals, voting, execution

---

## 🔐 Security

### Audited Patterns
- ✅ OpenZeppelin contracts (v5.0.0)
- ✅ ReentrancyGuard on all state-changing functions
- ✅ AccessControl for role management
- ✅ Ownable for admin functions

### Best Practices
- No external calls in loops
- Checks-Effects-Interactions pattern
- SafeERC20 for token transfers
- Gas-optimized storage

### Recommended Next Steps
- [ ] External security audit
- [ ] Bug bounty program
- [ ] Testnet deployment and testing
- [ ] Gradual mainnet rollout

---

## 🧪 Testing

```powershell
# Run all tests
npm test

# Run with gas report
REPORT_GAS=true npm test

# Run specific test
npx hardhat test test/FIBTToken.test.js
```

---

## 📁 File Structure

```
web3/
├── contracts/              # Solidity contracts
│   ├── FIBTToken.sol
│   ├── StrategyNFT.sol
│   ├── StakingManager.sol
│   ├── VIPTierManager.sol
│   ├── PriceOracle.sol
│   ├── MT5Oracle.sol
│   ├── PerformanceVerifier.sol
│   ├── StrategyRegistry.sol
│   ├── SignalEscrow.sol
│   ├── RevenueDistributor.sol
│   └── GovernanceDAO.sol
├── scripts/
│   ├── deploy.js          # Deployment script
│   └── verify.js          # Verification script
├── test/                  # Test files
├── deployments/           # Deployment records
├── hardhat.config.js      # Hardhat configuration
├── package.json
├── .env.example           # Environment template
├── .gitignore
├── DEPLOYMENT_GUIDE.md    # Detailed deployment guide
└── README.md              # This file
```

---

## 🌐 Networks

### Arbitrum Sepolia (Testnet)
- **Chain ID**: 421614
- **RPC**: https://sepolia-rollup.arbitrum.io/rpc
- **Explorer**: https://sepolia.arbiscan.io
- **Faucet**: https://bridge.arbitrum.io (bridge from Sepolia)

### Arbitrum One (Mainnet)
- **Chain ID**: 42161
- **RPC**: https://arb1.arbitrum.io/rpc
- **Explorer**: https://arbiscan.io
- **Bridge**: https://bridge.arbitrum.io

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:
```bash
# Wallet
PRIVATE_KEY=0x...

# RPC URLs
ARBITRUM_SEPOLIA_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc
ARBITRUM_ONE_RPC_URL=https://arb1.arbitrum.io/rpc

# Arbiscan (for verification)
ARBISCAN_API_KEY=...

# Optional
REPORT_GAS=false
COINMARKETCAP_API_KEY=...
```

### Hardhat Configuration

`hardhat.config.js` includes:
- Solidity 0.8.20 with optimizer
- Arbitrum Sepolia & One networks
- Etherscan verification
- Gas reporter

---

## 📈 Deployment Checklist

### Pre-Deployment
- [ ] Compile contracts: `npm run compile`
- [ ] Run tests (optional)
- [ ] Configure `.env` file
- [ ] Fund deployment wallet with ETH
- [ ] Review gas settings

### Testnet Deployment
- [ ] Deploy: `npm run deploy:testnet`
- [ ] Save contract addresses
- [ ] Verify: `npm run verify:testnet`
- [ ] Test all functions
- [ ] Update frontend with addresses

### Mainnet Deployment
- [ ] Security audit completed
- [ ] Team review and approval
- [ ] Sufficient ETH in wallet (~0.2 ETH)
- [ ] Deploy: `npm run deploy:mainnet`
- [ ] Verify: `npm run verify:mainnet`
- [ ] Transfer ownership to multisig
- [ ] Enable trading when ready

---

## 🔧 Post-Deployment

### 1. Update Frontend
```bash
# In frontend/.env.local
NEXT_PUBLIC_FIBT_TOKEN_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_NFT_ADDRESS=0x...
# ... etc
```

### 2. Enable Trading
```javascript
await FIBTToken.enableTrading();
```

### 3. Configure Oracles
```javascript
await PriceOracle.addPriceFeed("EURUSD", chainlinkFeed, 3600);
```

### 4. Set Up Monitoring
- Watch for unusual transactions
- Monitor gas usage
- Track user activity
- Set up alerts

---

## 🐛 Troubleshooting

**Compilation errors?**
- Delete `cache/` and `artifacts/`
- Run `npm install` again

**Deployment fails?**
- Check wallet has ETH for gas
- Verify RPC URL is accessible
- Review private key format

**Verification fails?**
- Wait 1-2 minutes after deployment
- Check Arbiscan API key
- Verify constructor args match

---

## 📚 Documentation

- **Deployment Guide**: See `DEPLOYMENT_GUIDE.md`
- **Architecture**: See `SMART_CONTRACT_ARCHITECTURE.md`
- **Frontend Integration**: See `frontend/README.md`

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open pull request

---

## 📞 Support

- **Issues**: GitHub Issues
- **Discord**: [Join Server]
- **Email**: dev@fibtool.io

---

## 📄 License

MIT License - see LICENSE file

---

## ⚠️ Disclaimer

These smart contracts are provided as-is. Use at your own risk. Always conduct thorough testing and security audits before mainnet deployment.

---

**Built with Hardhat, OpenZeppelin, and Solidity 0.8.20**

*Ready to revolutionize trading signal markets! 🚀*
