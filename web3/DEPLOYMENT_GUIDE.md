# 🚀 Smart Contract Deployment Guide

Complete guide to deploy all 11 Fibtool smart contracts to Arbitrum.

---

## 📋 Prerequisites

### 1. Tools Required
- Node.js 18+ installed
- Git
- MetaMask wallet with private key
- ETH on Arbitrum (for gas fees)

### 2. Get Test ETH (Testnet Only)
For Arbitrum Sepolia testnet:
1. Get Sepolia ETH from https://sepoliafaucet.com
2. Bridge to Arbitrum Sepolia: https://bridge.arbitrum.io

For Mainnet:
- Purchase ETH and bridge to Arbitrum One

---

## ⚙️ Setup

### 1. Install Dependencies

```powershell
cd web3
npm install
```

This installs:
- Hardhat (deployment framework)
- OpenZeppelin Contracts (ERC20, ERC721, etc.)
- Hardhat plugins (verification, gas reporter)

### 2. Configure Environment

```powershell
cp .env.example .env
```

Edit `.env` file:

```bash
# Your wallet private key (NEVER COMMIT THIS!)
PRIVATE_KEY=0x1234567890abcdef...

# RPC URLs (use Alchemy/Infura for better reliability)
ARBITRUM_SEPOLIA_RPC_URL=https://sepolia-rollup.arbitrum.io/rpc
ARBITRUM_ONE_RPC_URL=https://arb1.arbitrum.io/rpc

# Get API key from https://arbiscan.io/myapikey
ARBISCAN_API_KEY=YOUR_ARBISCAN_API_KEY
```

**⚠️ SECURITY WARNING:**
- Never commit `.env` file
- Never share your private key
- Use a dedicated deployment wallet
- Test on testnet first!

---

## 🧪 Compile Contracts

```powershell
npm run compile
```

This compiles all 11 contracts:
1. FIBTToken.sol
2. StrategyNFT.sol
3. StakingManager.sol
4. VIPTierManager.sol
5. PriceOracle.sol
6. MT5Oracle.sol
7. PerformanceVerifier.sol
8. StrategyRegistry.sol
9. SignalEscrow.sol
10. RevenueDistributor.sol
11. GovernanceDAO.sol

**Expected output:**
```
Compiled 11 Solidity files successfully
```

---

## 🚀 Deploy to Testnet

### Deploy All Contracts

```powershell
npm run deploy:testnet
```

**What happens:**
1. ✅ Deploys FIBTToken (25M initial supply)
2. ✅ Deploys StrategyNFT
3. ✅ Deploys StakingManager (linked to FIBT)
4. ✅ Deploys VIPTierManager
5. ✅ Deploys PriceOracle
6. ✅ Deploys MT5Oracle
7. ✅ Deploys PerformanceVerifier
8. ✅ Deploys StrategyRegistry
9. ✅ Deploys SignalEscrow
10. ✅ Deploys RevenueDistributor
11. ✅ Deploys GovernanceDAO
12. ⚙️ Configures roles and permissions
13. 💾 Saves addresses to `deployments/`

**Expected time:** 5-10 minutes

**Gas cost estimate:**
- Testnet: ~0.05 ETH
- Mainnet: ~0.1 ETH (varies with gas price)

---

## 🔍 Verify Contracts

After deployment, verify on Arbiscan:

```powershell
npm run verify:testnet
```

**Why verify?**
- Users can read contract source code
- Better trust and transparency
- Easier debugging
- Arbiscan UI for contract interaction

**Expected output:**
```
✅ All contracts verified on Arbiscan
```

View on Arbiscan:
- Testnet: https://sepolia.arbiscan.io
- Mainnet: https://arbiscan.io

---

## 📊 Deployment Output

After successful deployment, you'll see:

```
=============================================================
📊 DEPLOYMENT SUMMARY
=============================================================
Network: arbitrumSepolia
Chain ID: 421614
Deployer: 0x1234...5678

📝 Contract Addresses:
=============================================================
1. FIBTToken              0xABC...DEF
2. StrategyNFT            0x123...456
3. StakingManager         0x789...ABC
4. VIPTierManager         0xDEF...123
5. PriceOracle            0x456...789
6. MT5Oracle              0xABC...DEF
7. PerformanceVerifier    0x123...456
8. StrategyRegistry       0x789...ABC
9. SignalEscrow           0xDEF...123
10. RevenueDistributor    0x456...789
11. GovernanceDAO         0xABC...DEF
=============================================================
```

**⚠️ SAVE THESE ADDRESSES!** You'll need them for:
1. Frontend configuration
2. Contract verification
3. Future interactions

---

## 🔄 Deploy to Mainnet

**⚠️ IMPORTANT: Only after thorough testing on testnet!**

### Pre-Mainnet Checklist
- [ ] All contracts tested on testnet
- [ ] Frontend tested with testnet contracts
- [ ] Security audit completed (recommended)
- [ ] Sufficient ETH in deployer wallet (~0.2 ETH)
- [ ] Backup of all private keys
- [ ] Team ready for monitoring

### Deploy

```powershell
npm run deploy:mainnet
```

### Verify

```powershell
npm run verify:mainnet
```

---

## 🔧 Post-Deployment Configuration

### 1. Update Frontend

Copy contract addresses to frontend:

```powershell
cd ../frontend
```

Edit `.env.local`:
```bash
NEXT_PUBLIC_FIBT_TOKEN_ADDRESS=0x...
NEXT_PUBLIC_STRATEGY_NFT_ADDRESS=0x...
NEXT_PUBLIC_STAKING_MANAGER_ADDRESS=0x...
# ... etc for all 11 contracts
```

### 2. Enable Trading

Trading is disabled by default. Enable when ready:

```javascript
// Using Hardhat console
npx hardhat console --network arbitrumSepolia

const FIBTToken = await ethers.getContractAt("FIBTToken", "0x...");
await FIBTToken.enableTrading();
```

### 3. Configure Oracles

Set up price feeds:

```javascript
const PriceOracle = await ethers.getContractAt("PriceOracle", "0x...");

// Add Chainlink price feeds
await PriceOracle.addPriceFeed(
  "EURUSD",
  "0x...", // Chainlink EUR/USD feed
  3600    // 1 hour staleness threshold
);
```

### 4. Grant Roles

Already configured in deployment script:
- ✅ MINTER_ROLE for StrategyRegistry on StrategyNFT
- ✅ Whitelisted SignalEscrow, RevenueDistributor, StakingManager

Additional roles as needed:
```javascript
const StrategyNFT = await ethers.getContractAt("StrategyNFT", "0x...");
await StrategyNFT.grantRole(MINTER_ROLE, "0xNewMinter...");
```

---

## 🧪 Testing Deployed Contracts

### Using Hardhat Console

```powershell
npx hardhat console --network arbitrumSepolia
```

**Test FIBT Token:**
```javascript
const FIBTToken = await ethers.getContractAt("FIBTToken", "0x...");
const [deployer] = await ethers.getSigners();

// Check balance
const balance = await FIBTToken.balanceOf(deployer.address);
console.log("Balance:", ethers.formatEther(balance), "FIBT");

// Transfer
await FIBTToken.transfer("0xRecipient...", ethers.parseEther("100"));
```

**Test Staking:**
```javascript
const StakingManager = await ethers.getContractAt("StakingManager", "0x...");

// Approve
await FIBTToken.approve(stakingManagerAddress, ethers.parseEther("1000"));

// Stake (Gold tier = 2)
await StakingManager.stake(ethers.parseEther("1000"), 2, true);
```

### Using Arbiscan

1. Go to Arbiscan
2. Find your contract
3. Click "Contract" tab
4. Click "Write Contract"
5. Connect MetaMask
6. Call functions directly

---

## 📁 File Structure

```
web3/
├── contracts/              # Solidity contracts
│   ├── FIBTToken.sol
│   ├── StrategyNFT.sol
│   ├── StakingManager.sol
│   └── ... (11 total)
├── scripts/
│   ├── deploy.js          # Main deployment script
│   └── verify.js          # Verification script
├── deployments/           # Deployment records (auto-generated)
│   └── arbitrumSepolia-*.json
├── hardhat.config.js      # Hardhat configuration
├── package.json           # Dependencies
├── .env                   # Environment variables (DO NOT COMMIT)
└── .env.example           # Environment template
```

---

## 🐛 Troubleshooting

### "Insufficient funds for gas"
- Check wallet balance: need ETH for gas
- Testnet: Get from faucet
- Mainnet: Purchase and bridge ETH

### "Nonce too high"
- Reset MetaMask account in Settings > Advanced > Reset Account
- Or wait a few minutes

### "Contract deployment failed"
- Check RPC URL is correct
- Verify private key format (starts with 0x)
- Ensure sufficient gas

### "Verification failed"
- Wait 1-2 minutes after deployment
- Check Arbiscan API key is valid
- Verify constructor arguments match deployment

### "Cannot find module '@openzeppelin/contracts'"
- Run `npm install` again
- Delete `node_modules` and reinstall

---

## 📊 Gas Optimization

Current settings (in hardhat.config.js):
```javascript
optimizer: {
  enabled: true,
  runs: 200,
}
```

**Runs: 200** = Balanced approach
- Lower deployment cost
- Higher execution cost
- Good for most use cases

For mainnet, consider:
- **Runs: 1** = Cheapest deployment, highest execution
- **Runs: 10000** = Expensive deployment, cheapest execution

---

## 🔐 Security Best Practices

### Before Deployment
- [ ] Audit all contracts
- [ ] Test thoroughly on testnet
- [ ] Use multisig for owner role
- [ ] Set up monitoring and alerts
- [ ] Prepare emergency pause mechanism

### During Deployment
- [ ] Use dedicated deployment wallet
- [ ] Double-check all addresses
- [ ] Verify all constructor arguments
- [ ] Monitor transaction status

### After Deployment
- [ ] Transfer ownership to multisig
- [ ] Verify all contracts on Arbiscan
- [ ] Test all functions
- [ ] Monitor for unusual activity
- [ ] Set up automated alerts

---

## 📞 Support

**Issues during deployment?**

1. Check deployment logs in `deployments/` folder
2. Verify transaction on Arbiscan
3. Review Hardhat console output
4. Check wallet has sufficient ETH

**Common fixes:**
- Increase gas limit in hardhat.config.js
- Use different RPC endpoint (Alchemy, Infura)
- Wait for network congestion to clear

---

## 📈 Next Steps After Deployment

1. ✅ Deploy contracts
2. ✅ Verify on Arbiscan
3. ⏭️ Update frontend with addresses
4. ⏭️ Test frontend with deployed contracts
5. ⏭️ Enable trading when ready
6. ⏭️ Configure oracles and roles
7. ⏭️ Deploy frontend to production
8. ⏭️ Announce to community!

---

## 🎉 Success!

Your Fibtool smart contracts are now live on Arbitrum! 🚀

**View your contracts:**
- Testnet: `https://sepolia.arbiscan.io/address/YOUR_TOKEN_ADDRESS`
- Mainnet: `https://arbiscan.io/address/YOUR_TOKEN_ADDRESS`

**Ready to integrate with frontend!**

---

*For detailed contract documentation, see SMART_CONTRACT_ARCHITECTURE.md*
