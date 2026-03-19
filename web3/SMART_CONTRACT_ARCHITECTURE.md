# 🏗️ FIBTOOL WEB3 - SMART CONTRACT ARCHITECTURE

**Project:** Fibtool Decentralized Trading Signal Marketplace  
**Blockchain:** Ethereum Layer 2 (Arbitrum One)  
**Language:** Solidity ^0.8.20  
**Framework:** Hardhat + OpenZeppelin  
**Audit Status:** Pre-Audit (Target: CertiK + OpenZeppelin)  

---

## 📋 TABLE OF CONTENTS

1. [System Overview](#system-overview)
2. [Contract Architecture](#contract-architecture)
3. [Core Contracts](#core-contracts)
4. [Contract Interactions](#contract-interactions)
5. [Security Features](#security-features)
6. [Gas Optimization](#gas-optimization)
7. [Deployment Strategy](#deployment-strategy)
8. [Testing Strategy](#testing-strategy)

---

## 🎯 SYSTEM OVERVIEW

### **Architecture Philosophy**

```
┌─────────────────────────────────────────────────────────────────┐
│                    FIBTOOL WEB3 ECOSYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   $FIBT      │◄───│  Staking     │◄───│  Governance  │      │
│  │   Token      │    │  Manager     │    │     DAO      │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Strategy    │◄───│   Signal     │◄───│   Oracle     │      │
│  │  Registry    │    │   Escrow     │    │   (MT5)      │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  NFT Minting │    │   Revenue    │    │  Liquidity   │      │
│  │  (ERC-721)   │    │Distribution  │    │   Rewards    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### **Design Principles**

1. **Modularity:** Each contract has single responsibility
2. **Upgradeability:** Use proxy patterns for critical contracts
3. **Security:** Defense in depth, multiple validation layers
4. **Gas Efficiency:** Optimize storage, batch operations
5. **Decentralization:** Minimize admin controls, time-locks on critical functions

---

## 🏛️ CONTRACT ARCHITECTURE

### **Contract Hierarchy**

```
FibtoolEcosystem
│
├── Core Contracts (Immutable)
│   ├── FIBTToken.sol                 [ERC-20 Token]
│   ├── StrategyNFT.sol               [ERC-721 NFT]
│   └── FibtoolTimelock.sol           [Governance Timelock]
│
├── Logic Contracts (Upgradeable via Proxy)
│   ├── StakingManager.sol            [Token Staking]
│   ├── SignalEscrow.sol              [Pay-per-Signal]
│   ├── StrategyRegistry.sol          [Strategy Listing]
│   ├── RevenueDistributor.sol        [Profit Sharing]
│   └── GovernanceDAO.sol             [Voting System]
│
├── Oracle Contracts
│   ├── PriceOracle.sol               [Chainlink Integration]
│   ├── MT5Oracle.sol                 [Custom Off-Chain Oracle]
│   └── PerformanceVerifier.sol       [Trade Result Validation]
│
├── Utility Contracts
│   ├── FeeManager.sol                [Dynamic Fee Calculation]
│   ├── VIPTierManager.sol            [Tier Access Control]
│   ├── TokenBurner.sol               [Burn Mechanisms]
│   └── EmergencyPause.sol            [Circuit Breaker]
│
└── Libraries
    ├── SignalValidation.sol          [Signal Data Structures]
    ├── MathUtils.sol                 [Safe Math Operations]
    └── AccessControl.sol             [Role Management]
```

---

## 📝 CORE CONTRACTS

### **1. FIBTToken.sol - ERC-20 Token**

**Purpose:** Native utility token with burn capabilities

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title FIBTToken
 * @dev Fibtool native token with burn, permit, and role-based minting
 * 
 * Features:
 * - Fixed supply of 100M tokens (no inflation)
 * - Burnable by anyone (deflationary)
 * - Permit (EIP-2612) for gasless approvals
 * - Role-based access for initial distribution
 * - 2% transaction tax (optional, governance-controlled)
 */
contract FIBTToken is ERC20, ERC20Burnable, ERC20Permit, AccessControl {
    /// @notice Maximum supply cap (100 million tokens)
    uint256 public constant MAX_SUPPLY = 100_000_000 * 10**18;
    
    /// @notice Transaction tax rate (in basis points, 200 = 2%)
    uint256 public transactionTaxBps = 200;
    
    /// @notice Maximum tax rate (cannot exceed 5%)
    uint256 public constant MAX_TAX_BPS = 500;
    
    /// @notice Address that receives transaction taxes
    address public taxRecipient;
    
    /// @notice Addresses exempt from transaction tax
    mapping(address => bool) public taxExempt;
    
    /// @notice Role for managing tax settings
    bytes32 public constant TAX_MANAGER_ROLE = keccak256("TAX_MANAGER_ROLE");
    
    /// @notice Role for managing exemptions
    bytes32 public constant EXEMPTION_MANAGER_ROLE = keccak256("EXEMPTION_MANAGER_ROLE");
    
    /// Events
    event TaxRateUpdated(uint256 oldRate, uint256 newRate);
    event TaxRecipientUpdated(address oldRecipient, address newRecipient);
    event TaxExemptionUpdated(address indexed account, bool exempt);
    event TokensBurned(address indexed burner, uint256 amount);
    
    /**
     * @dev Constructor mints initial supply to deployer
     * @param _initialRecipient Address to receive initial token supply
     * @param _taxRecipient Address to receive transaction taxes
     */
    constructor(
        address _initialRecipient,
        address _taxRecipient
    ) ERC20("Fibonacci Trading Token", "FIBT") ERC20Permit("Fibonacci Trading Token") {
        require(_initialRecipient != address(0), "Invalid recipient");
        require(_taxRecipient != address(0), "Invalid tax recipient");
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(TAX_MANAGER_ROLE, msg.sender);
        _grantRole(EXEMPTION_MANAGER_ROLE, msg.sender);
        
        taxRecipient = _taxRecipient;
        
        // Exempt key addresses from tax
        taxExempt[_initialRecipient] = true;
        taxExempt[_taxRecipient] = true;
        taxExempt[address(this)] = true;
        
        // Mint initial supply
        _mint(_initialRecipient, MAX_SUPPLY);
    }
    
    /**
     * @dev Override transfer to apply transaction tax
     */
    function _transfer(
        address from,
        address to,
        uint256 amount
    ) internal virtual override {
        require(from != address(0), "Transfer from zero address");
        require(to != address(0), "Transfer to zero address");
        
        // Calculate tax if applicable
        uint256 taxAmount = 0;
        if (!taxExempt[from] && !taxExempt[to] && transactionTaxBps > 0) {
            taxAmount = (amount * transactionTaxBps) / 10000;
        }
        
        if (taxAmount > 0) {
            // Transfer tax to recipient
            super._transfer(from, taxRecipient, taxAmount);
            // Transfer remaining to recipient
            super._transfer(from, to, amount - taxAmount);
        } else {
            super._transfer(from, to, amount);
        }
    }
    
    /**
     * @dev Update transaction tax rate
     * @param _newTaxBps New tax rate in basis points
     */
    function setTransactionTax(uint256 _newTaxBps) external onlyRole(TAX_MANAGER_ROLE) {
        require(_newTaxBps <= MAX_TAX_BPS, "Tax rate too high");
        uint256 oldRate = transactionTaxBps;
        transactionTaxBps = _newTaxBps;
        emit TaxRateUpdated(oldRate, _newTaxBps);
    }
    
    /**
     * @dev Update tax recipient address
     * @param _newRecipient New recipient address
     */
    function setTaxRecipient(address _newRecipient) external onlyRole(TAX_MANAGER_ROLE) {
        require(_newRecipient != address(0), "Invalid recipient");
        address oldRecipient = taxRecipient;
        taxRecipient = _newRecipient;
        taxExempt[_newRecipient] = true;
        emit TaxRecipientUpdated(oldRecipient, _newRecipient);
    }
    
    /**
     * @dev Set tax exemption for an address
     * @param _account Address to update
     * @param _exempt Exemption status
     */
    function setTaxExemption(address _account, bool _exempt) 
        external 
        onlyRole(EXEMPTION_MANAGER_ROLE) 
    {
        taxExempt[_account] = _exempt;
        emit TaxExemptionUpdated(_account, _exempt);
    }
    
    /**
     * @dev Burn tokens and emit event
     * @param amount Amount to burn
     */
    function burn(uint256 amount) public virtual override {
        super.burn(amount);
        emit TokensBurned(msg.sender, amount);
    }
    
    /**
     * @dev Burn tokens from account (requires approval)
     * @param account Account to burn from
     * @param amount Amount to burn
     */
    function burnFrom(address account, uint256 amount) public virtual override {
        super.burnFrom(account, amount);
        emit TokensBurned(account, amount);
    }
}
```

**Key Features:**
- ✅ Fixed 100M supply (no minting after deployment)
- ✅ Optional 2% transaction tax (governance-controlled)
- ✅ Burnable by anyone (deflationary mechanism)
- ✅ EIP-2612 Permit (gasless approvals)
- ✅ Role-based access control
- ✅ Tax exemptions for key addresses (DEX, staking contracts)

**Gas Cost Estimates:**
- Deploy: ~2.5M gas (~$5 on Arbitrum)
- Transfer (no tax): ~50K gas
- Transfer (with tax): ~80K gas
- Burn: ~40K gas

---

### **2. StrategyNFT.sol - ERC-721 NFT**

**Purpose:** Represents ownership of trading strategies

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/**
 * @title StrategyNFT
 * @dev NFT representing trading strategy ownership
 * 
 * NFT Tiers:
 * - Basic (1-9999): 1,000 FIBT to mint
 * - Premium (10000-19999): 5,000 FIBT to mint
 * - Elite (20000-20099): 50,000 FIBT to mint (limited 100)
 * 
 * Features:
 * - Metadata stored on IPFS
 * - Performance data tracked on-chain
 * - Transferable (secondary market)
 * - Upgradeable tier (burn old, mint new)
 */
contract StrategyNFT is ERC721, ERC721URIStorage, ERC721Enumerable, Ownable {
    using Counters for Counters.Counter;
    
    /// @notice Token ID counter
    Counters.Counter private _tokenIdCounter;
    
    /// @notice FIBT token contract
    address public fibtToken;
    
    /// @notice Strategy registry contract
    address public strategyRegistry;
    
    /// @notice NFT tier definitions
    enum Tier { BASIC, PREMIUM, ELITE }
    
    /// @notice Mint costs per tier (in FIBT wei)
    mapping(Tier => uint256) public mintCost;
    
    /// @notice Maximum supply per tier
    mapping(Tier => uint256) public maxSupply;
    
    /// @notice Current supply per tier
    mapping(Tier => uint256) public currentSupply;
    
    /// @notice NFT metadata
    struct NFTMetadata {
        Tier tier;
        address creator;
        uint256 mintedAt;
        string strategyId;
        uint256 performanceScore; // Updated by oracle
    }
    
    /// @notice Token ID to metadata
    mapping(uint256 => NFTMetadata) public nftMetadata;
    
    /// @notice Address to burn wallet (for upgrade burns)
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;
    
    /// Events
    event StrategyNFTMinted(
        uint256 indexed tokenId, 
        address indexed creator, 
        Tier tier, 
        string strategyId
    );
    event StrategyNFTUpgraded(
        uint256 indexed oldTokenId, 
        uint256 indexed newTokenId, 
        Tier newTier
    );
    event PerformanceScoreUpdated(uint256 indexed tokenId, uint256 newScore);
    
    /**
     * @dev Constructor
     * @param _fibtToken Address of FIBT token
     */
    constructor(address _fibtToken) ERC721("Fibtool Strategy NFT", "FBTSTRAT") {
        require(_fibtToken != address(0), "Invalid FIBT address");
        fibtToken = _fibtToken;
        
        // Set mint costs (in FIBT wei: 18 decimals)
        mintCost[Tier.BASIC] = 1_000 * 10**18;      // 1,000 FIBT
        mintCost[Tier.PREMIUM] = 5_000 * 10**18;    // 5,000 FIBT
        mintCost[Tier.ELITE] = 50_000 * 10**18;     // 50,000 FIBT
        
        // Set max supplies
        maxSupply[Tier.BASIC] = 10_000;
        maxSupply[Tier.PREMIUM] = 10_000;
        maxSupply[Tier.ELITE] = 100;
        
        // Initialize counter at 1
        _tokenIdCounter.increment();
    }
    
    /**
     * @dev Mint a new strategy NFT
     * @param tier Tier of NFT to mint
     * @param strategyId Unique strategy identifier
     * @param metadataURI IPFS URI for metadata
     * @return tokenId Minted token ID
     */
    function mintStrategyNFT(
        Tier tier,
        string memory strategyId,
        string memory metadataURI
    ) external returns (uint256) {
        require(currentSupply[tier] < maxSupply[tier], "Tier sold out");
        require(bytes(strategyId).length > 0, "Invalid strategy ID");
        
        // Transfer FIBT from user to this contract (will be burned)
        uint256 cost = mintCost[tier];
        require(
            IERC20(fibtToken).transferFrom(msg.sender, address(this), cost),
            "FIBT transfer failed"
        );
        
        // Burn the FIBT (permanent supply reduction)
        IERC20Burnable(fibtToken).burn(cost);
        
        // Mint NFT
        uint256 tokenId = _tokenIdCounter.current();
        _tokenIdCounter.increment();
        _safeMint(msg.sender, tokenId);
        _setTokenURI(tokenId, metadataURI);
        
        // Store metadata
        nftMetadata[tokenId] = NFTMetadata({
            tier: tier,
            creator: msg.sender,
            mintedAt: block.timestamp,
            strategyId: strategyId,
            performanceScore: 0
        });
        
        currentSupply[tier]++;
        
        emit StrategyNFTMinted(tokenId, msg.sender, tier, strategyId);
        return tokenId;
    }
    
    /**
     * @dev Upgrade NFT to higher tier (burn old, mint new)
     * @param tokenId Token to upgrade
     * @param newTier New tier
     * @param newMetadataURI New metadata URI
     * @return newTokenId New token ID
     */
    function upgradeNFT(
        uint256 tokenId,
        Tier newTier,
        string memory newMetadataURI
    ) external returns (uint256) {
        require(ownerOf(tokenId) == msg.sender, "Not token owner");
        
        NFTMetadata memory oldMetadata = nftMetadata[tokenId];
        require(uint8(newTier) > uint8(oldMetadata.tier), "Not an upgrade");
        require(currentSupply[newTier] < maxSupply[newTier], "New tier sold out");
        
        // Calculate upgrade cost (discount from full price)
        uint256 oldCost = mintCost[oldMetadata.tier];
        uint256 newCost = mintCost[newTier];
        uint256 upgradeCost = newCost - oldCost;
        
        // Transfer upgrade cost
        require(
            IERC20(fibtToken).transferFrom(msg.sender, address(this), upgradeCost),
            "FIBT transfer failed"
        );
        
        // Burn the upgrade cost
        IERC20Burnable(fibtToken).burn(upgradeCost);
        
        // Burn old NFT
        _burn(tokenId);
        currentSupply[oldMetadata.tier]--;
        
        // Mint new NFT
        uint256 newTokenId = _tokenIdCounter.current();
        _tokenIdCounter.increment();
        _safeMint(msg.sender, newTokenId);
        _setTokenURI(newTokenId, newMetadataURI);
        
        // Copy and update metadata
        nftMetadata[newTokenId] = NFTMetadata({
            tier: newTier,
            creator: msg.sender,
            mintedAt: block.timestamp,
            strategyId: oldMetadata.strategyId,
            performanceScore: oldMetadata.performanceScore
        });
        
        currentSupply[newTier]++;
        
        emit StrategyNFTUpgraded(tokenId, newTokenId, newTier);
        return newTokenId;
    }
    
    /**
     * @dev Update performance score (only callable by oracle)
     * @param tokenId Token to update
     * @param newScore New performance score
     */
    function updatePerformanceScore(uint256 tokenId, uint256 newScore) 
        external 
    {
        require(msg.sender == strategyRegistry, "Only registry");
        require(_exists(tokenId), "Token does not exist");
        
        nftMetadata[tokenId].performanceScore = newScore;
        emit PerformanceScoreUpdated(tokenId, newScore);
    }
    
    /**
     * @dev Set strategy registry address
     * @param _registry Registry contract address
     */
    function setStrategyRegistry(address _registry) external onlyOwner {
        require(_registry != address(0), "Invalid registry");
        strategyRegistry = _registry;
    }
    
    /**
     * @dev Get NFT metadata for token
     * @param tokenId Token ID
     * @return Metadata struct
     */
    function getMetadata(uint256 tokenId) external view returns (NFTMetadata memory) {
        require(_exists(tokenId), "Token does not exist");
        return nftMetadata[tokenId];
    }
    
    // Required overrides
    function _burn(uint256 tokenId) 
        internal 
        override(ERC721, ERC721URIStorage) 
    {
        super._burn(tokenId);
    }
    
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }
    
    function _beforeTokenTransfer(
        address from,
        address to,
        uint256 tokenId,
        uint256 batchSize
    ) internal override(ERC721, ERC721Enumerable) {
        super._beforeTokenTransfer(from, to, tokenId, batchSize);
    }
    
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721Enumerable, ERC721URIStorage)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}

/**
 * @dev Interface for FIBT token burn function
 */
interface IERC20Burnable {
    function burn(uint256 amount) external;
}

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}
```

**Key Features:**
- ✅ 3 tiers (Basic, Premium, Elite) with different supplies
- ✅ Minting burns FIBT (deflationary)
- ✅ Upgradeable (burn old, mint new at discounted price)
- ✅ Performance scores tracked on-chain
- ✅ Metadata on IPFS
- ✅ Enumerable (easy to query all NFTs)

**Gas Cost Estimates:**
- Deploy: ~4M gas (~$8 on Arbitrum)
- Mint Basic: ~200K gas
- Mint Elite: ~220K gas
- Upgrade: ~250K gas

---

### **3. StakingManager.sol - Token Staking**

**Purpose:** Manage staking for tier access and rewards

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/security/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title StakingManager
 * @dev Manage FIBT staking for tier access and rewards
 * 
 * Features:
 * - 4 staking tiers (Basic, Pro, Elite, Institutional)
 * - Rewards distributed from revenue pool
 * - No lock-up period (liquid staking)
 * - Auto-compounding option
 * - Emergency withdraw function
 */
contract StakingManager is 
    Initializable, 
    ReentrancyGuardUpgradeable, 
    OwnableUpgradeable 
{
    /// @notice FIBT token
    address public fibtToken;
    
    /// @notice Staking tiers
    enum Tier { NONE, BASIC, PROFESSIONAL, ELITE, INSTITUTIONAL }
    
    /// @notice Minimum stake per tier
    mapping(Tier => uint256) public minimumStake;
    
    /// @notice Base APY per tier (in basis points, 1000 = 10%)
    mapping(Tier => uint256) public baseAPY;
    
    /// @notice User stake information
    struct StakeInfo {
        uint256 amount;
        uint256 stakedAt;
        uint256 lastClaimAt;
        Tier tier;
        bool autoCompound;
    }
    
    /// @notice User address to stake info
    mapping(address => StakeInfo) public stakes;
    
    /// @notice Total staked across all users
    uint256 public totalStaked;
    
    /// @notice Rewards pool balance
    uint256 public rewardsPool;
    
    /// @notice Total rewards claimed
    uint256 public totalRewardsClaimed;
    
    /// Events
    event Staked(address indexed user, uint256 amount, Tier tier);
    event Unstaked(address indexed user, uint256 amount);
    event RewardsClaimed(address indexed user, uint256 amount);
    event RewardsDeposited(uint256 amount);
    event AutoCompoundToggled(address indexed user, bool enabled);
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize contract
     * @param _fibtToken FIBT token address
     */
    function initialize(address _fibtToken) external initializer {
        __ReentrancyGuard_init();
        __Ownable_init();
        
        require(_fibtToken != address(0), "Invalid FIBT address");
        fibtToken = _fibtToken;
        
        // Set minimum stakes (in FIBT wei)
        minimumStake[Tier.BASIC] = 1_000 * 10**18;          // 1,000 FIBT
        minimumStake[Tier.PROFESSIONAL] = 5_000 * 10**18;   // 5,000 FIBT
        minimumStake[Tier.ELITE] = 20_000 * 10**18;         // 20,000 FIBT
        minimumStake[Tier.INSTITUTIONAL] = 100_000 * 10**18; // 100,000 FIBT
        
        // Set base APYs (in basis points)
        baseAPY[Tier.BASIC] = 500;            // 5%
        baseAPY[Tier.PROFESSIONAL] = 800;     // 8%
        baseAPY[Tier.ELITE] = 1200;           // 12%
        baseAPY[Tier.INSTITUTIONAL] = 1500;   // 15%
    }
    
    /**
     * @dev Stake FIBT tokens
     * @param amount Amount to stake
     */
    function stake(uint256 amount) external nonReentrant {
        require(amount > 0, "Cannot stake 0");
        
        // Transfer tokens from user
        require(
            IERC20(fibtToken).transferFrom(msg.sender, address(this), amount),
            "Transfer failed"
        );
        
        StakeInfo storage userStake = stakes[msg.sender];
        
        // If already staked, claim pending rewards first
        if (userStake.amount > 0) {
            _claimRewards(msg.sender);
        }
        
        // Update stake
        userStake.amount += amount;
        userStake.stakedAt = block.timestamp;
        userStake.lastClaimAt = block.timestamp;
        
        // Determine tier
        userStake.tier = _calculateTier(userStake.amount);
        
        totalStaked += amount;
        
        emit Staked(msg.sender, amount, userStake.tier);
    }
    
    /**
     * @dev Unstake FIBT tokens
     * @param amount Amount to unstake
     */
    function unstake(uint256 amount) external nonReentrant {
        StakeInfo storage userStake = stakes[msg.sender];
        require(userStake.amount >= amount, "Insufficient stake");
        
        // Claim pending rewards first
        _claimRewards(msg.sender);
        
        // Update stake
        userStake.amount -= amount;
        
        // Recalculate tier
        if (userStake.amount == 0) {
            userStake.tier = Tier.NONE;
            userStake.stakedAt = 0;
        } else {
            userStake.tier = _calculateTier(userStake.amount);
        }
        
        totalStaked -= amount;
        
        // Transfer tokens back to user
        require(IERC20(fibtToken).transfer(msg.sender, amount), "Transfer failed");
        
        emit Unstaked(msg.sender, amount);
    }
    
    /**
     * @dev Claim staking rewards
     */
    function claimRewards() external nonReentrant {
        _claimRewards(msg.sender);
    }
    
    /**
     * @dev Internal reward claim logic
     * @param user User address
     */
    function _claimRewards(address user) internal {
        StakeInfo storage userStake = stakes[user];
        require(userStake.amount > 0, "No stake");
        
        uint256 rewards = calculateRewards(user);
        if (rewards == 0) return;
        
        require(rewardsPool >= rewards, "Insufficient rewards pool");
        
        userStake.lastClaimAt = block.timestamp;
        rewardsPool -= rewards;
        totalRewardsClaimed += rewards;
        
        if (userStake.autoCompound) {
            // Auto-compound: add rewards to stake
            userStake.amount += rewards;
            totalStaked += rewards;
            userStake.tier = _calculateTier(userStake.amount);
            emit Staked(user, rewards, userStake.tier);
        } else {
            // Transfer rewards to user
            require(IERC20(fibtToken).transfer(user, rewards), "Transfer failed");
        }
        
        emit RewardsClaimed(user, rewards);
    }
    
    /**
     * @dev Calculate pending rewards for user
     * @param user User address
     * @return Pending rewards amount
     */
    function calculateRewards(address user) public view returns (uint256) {
        StakeInfo memory userStake = stakes[user];
        if (userStake.amount == 0) return 0;
        
        uint256 timeStaked = block.timestamp - userStake.lastClaimAt;
        uint256 apy = baseAPY[userStake.tier];
        
        // Calculate rewards: (amount * APY * timeStaked) / (365 days * 10000)
        uint256 rewards = (userStake.amount * apy * timeStaked) / (365 days * 10000);
        
        return rewards;
    }
    
    /**
     * @dev Calculate tier based on stake amount
     * @param amount Stake amount
     * @return Tier
     */
    function _calculateTier(uint256 amount) internal view returns (Tier) {
        if (amount >= minimumStake[Tier.INSTITUTIONAL]) return Tier.INSTITUTIONAL;
        if (amount >= minimumStake[Tier.ELITE]) return Tier.ELITE;
        if (amount >= minimumStake[Tier.PROFESSIONAL]) return Tier.PROFESSIONAL;
        if (amount >= minimumStake[Tier.BASIC]) return Tier.BASIC;
        return Tier.NONE;
    }
    
    /**
     * @dev Get user's current tier
     * @param user User address
     * @return Current tier
     */
    function getUserTier(address user) external view returns (Tier) {
        return stakes[user].tier;
    }
    
    /**
     * @dev Toggle auto-compound for rewards
     */
    function setAutoCompound(bool enabled) external {
        stakes[msg.sender].autoCompound = enabled;
        emit AutoCompoundToggled(msg.sender, enabled);
    }
    
    /**
     * @dev Deposit rewards to pool (called by RevenueDistributor)
     * @param amount Amount to deposit
     */
    function depositRewards(uint256 amount) external {
        require(msg.sender == owner(), "Only owner"); // In production, use RevenueDistributor
        require(
            IERC20(fibtToken).transferFrom(msg.sender, address(this), amount),
            "Transfer failed"
        );
        rewardsPool += amount;
        emit RewardsDeposited(amount);
    }
    
    /**
     * @dev Emergency withdraw (no rewards, just principal)
     * Only use in case of contract upgrade or emergency
     */
    function emergencyWithdraw() external nonReentrant {
        StakeInfo storage userStake = stakes[msg.sender];
        require(userStake.amount > 0, "No stake");
        
        uint256 amount = userStake.amount;
        
        userStake.amount = 0;
        userStake.tier = Tier.NONE;
        userStake.stakedAt = 0;
        
        totalStaked -= amount;
        
        require(IERC20(fibtToken).transfer(msg.sender, amount), "Transfer failed");
        emit Unstaked(msg.sender, amount);
    }
    
    /**
     * @dev Update minimum stake for tier (governance)
     * @param tier Tier to update
     * @param newMinimum New minimum stake
     */
    function updateMinimumStake(Tier tier, uint256 newMinimum) external onlyOwner {
        require(tier != Tier.NONE, "Invalid tier");
        minimumStake[tier] = newMinimum;
    }
    
    /**
     * @dev Update base APY for tier (governance)
     * @param tier Tier to update
     * @param newAPY New APY in basis points
     */
    function updateBaseAPY(Tier tier, uint256 newAPY) external onlyOwner {
        require(tier != Tier.NONE, "Invalid tier");
        require(newAPY <= 5000, "APY too high"); // Max 50%
        baseAPY[tier] = newAPY;
    }
}

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}
```

**Key Features:**
- ✅ 4 staking tiers with different APYs
- ✅ No lock-up period (fully liquid)
- ✅ Auto-compound option
- ✅ Rewards calculated per-second for accuracy
- ✅ Emergency withdraw function
- ✅ Upgradeable via proxy pattern

**Gas Cost Estimates:**
- Deploy: ~3.5M gas
- Stake: ~120K gas
- Unstake: ~150K gas
- Claim rewards: ~80K gas

---

## 🔗 CONTRACT INTERACTIONS

### **Signal Purchase Flow (Pay-Per-Signal)**

```
User                SignalEscrow           MT5Oracle            StrategyRegistry
 │                       │                      │                        │
 │ 1. buySignal()        │                      │                        │
 │──────────────────────>│                      │                        │
 │                       │ 2. Lock FIBT         │                        │
 │                       │    (escrow)          │                        │
 │                       │                      │                        │
 │                       │ 3. Emit SignalBought │                        │
 │                       │                      │                        │
 │                       │                  4. Trade Executed (off-chain)│
 │                       │                      │                        │
 │                       │    5. reportResult() │                        │
 │                       │<─────────────────────│                        │
 │                       │                      │                        │
 │                       │ 6. Verify signature  │                        │
 │                       │                      │                        │
 │   IF TP HIT:          │ 7. Distribute FIBT   │                        │
 │                       │    - 70% to creator──┼───────────────────────>│
 │                       │    - 20% to platform │                        │
 │                       │    - 10% burned      │                        │
 │                       │                      │                        │
 │   IF SL HIT:          │ 8. Refund user       │                        │
 │<──────────────────────│    - 100% to user    │                        │
 │                       │    - Burn creator fee│                        │
```

---

### **Staking → Tier Access Flow**

```
User              StakingManager      VIPTierManager      StrategyRegistry
 │                      │                    │                    │
 │ 1. stake(5000 FIBT)  │                    │                    │
 │─────────────────────>│                    │                    │
 │                      │ 2. Update tier     │                    │
 │                      │    (PROFESSIONAL)  │                    │
 │                      │                    │                    │
 │ 3. requestSignals()  │                    │                    │
 │──────────────────────┼───────────────────>│                    │
 │                      │                    │ 4. Check tier      │
 │                      │<───────────────────┼────────────────────│
 │                      │    getUserTier()   │                    │
 │                      │                    │                    │
 │                      │ 5. Return tier     │                    │
 │                      │───────────────────>│                    │
 │                      │                    │ 6. Grant access    │
 │<─────────────────────┼────────────────────│    (H1, H4, 10 symbols)
```

---

### **Revenue Distribution Flow**

```
Platform Revenue    RevenueDistributor   StakingManager    TokenBurner    DAO Treasury
      │                    │                    │               │               │
      │ 1. Collect fees    │                    │               │               │
      │───────────────────>│                    │               │               │
      │                    │ 2. Split revenue   │               │               │
      │                    │    - 40% staking───┼──────────────>│               │
      │                    │    - 30% buyback───┼───────────────┼──────────────>│
      │                    │    - 20% DAO───────┼───────────────┼──────────────>│
      │                    │    - 10% burn──────┼──────────────>│               │
      │                    │                    │               │               │
      │                    │ 3. depositRewards()│               │               │
      │                    │───────────────────>│               │               │
      │                    │                    │               │               │
      │                    │               4. Users claim       │               │
      │                    │                    │               │               │
      Users<───────────────┼────────────────────│               │               │
            claimRewards()                                      │               │
```

---

## 🔒 SECURITY FEATURES

### **1. Access Control Hierarchy**

```solidity
// Multi-sig governance (3 of 5)
address public governanceMultisig;

// Emergency pause guardian (1 of 3, can only pause)
address public emergencyGuardian;

// Oracle operators (verified nodes)
mapping(address => bool) public oracleOperators;

// Contract roles (via AccessControl)
bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
```

### **2. Circuit Breaker Pattern**

```solidity
// Pausable contracts for emergency stops
import "@openzeppelin/contracts/security/Pausable.sol";

contract SignalEscrow is Pausable {
    function buySignal() external whenNotPaused {
        // ...
    }
    
    function emergencyPause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }
    
    function unpause() external onlyRole(ADMIN_ROLE) {
        require(block.timestamp > pausedAt + 48 hours, "Timelock");
        _unpause();
    }
}
```

### **3. Reentrancy Guards**

```solidity
// All external functions with token transfers use ReentrancyGuard
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract SignalEscrow is ReentrancyGuard {
    function claimRewards() external nonReentrant {
        // Safe from reentrancy attacks
        _transferRewards(msg.sender);
    }
}
```

### **4. Oracle Security (Chainlink + Custom)**

```solidity
/**
 * @title MT5Oracle
 * @dev Custom oracle for off-chain MT5 trade verification
 * 
 * Security:
 * - Multi-oracle consensus (3 of 5 must agree)
 * - Signed reports (ECDSA verification)
 * - Slashing for malicious reports
 * - Timelock for data updates
 */
contract MT5Oracle {
    struct TradeReport {
        bytes32 signalId;
        bool tpHit;
        uint256 timestamp;
        bytes signature;
    }
    
    mapping(bytes32 => TradeReport[]) public reports;
    
    function submitReport(bytes32 signalId, bool tpHit, bytes memory signature) 
        external 
        onlyOracle 
    {
        // Verify signature
        require(_verifySignature(signalId, tpHit, signature), "Invalid signature");
        
        reports[signalId].push(TradeReport({
            signalId: signalId,
            tpHit: tpHit,
            timestamp: block.timestamp,
            signature: signature
        }));
        
        // Check consensus (3 of 5)
        if (_checkConsensus(signalId)) {
            // Finalize result
            _finalizeTradeResult(signalId, tpHit);
        }
    }
    
    function _checkConsensus(bytes32 signalId) internal view returns (bool) {
        TradeReport[] memory allReports = reports[signalId];
        if (allReports.length < 3) return false;
        
        uint256 tpCount = 0;
        uint256 slCount = 0;
        
        for (uint256 i = 0; i < allReports.length; i++) {
            if (allReports[i].tpHit) {
                tpCount++;
            } else {
                slCount++;
            }
        }
        
        return (tpCount >= 3 || slCount >= 3);
    }
}
```

---

## ⚡ GAS OPTIMIZATION

### **1. Storage Packing**

```solidity
// BAD: 3 slots (expensive)
struct UserData {
    uint256 amount;      // slot 0
    uint128 timestamp;   // slot 1
    address user;        // slot 2
}

// GOOD: 2 slots (cheaper)
struct UserData {
    uint128 amount;      // slot 0 (first 128 bits)
    uint128 timestamp;   // slot 0 (last 128 bits)
    address user;        // slot 1 (160 bits)
}
```

### **2. Batch Operations**

```solidity
// Batch claim for multiple users (save gas)
function batchClaimRewards(address[] calldata users) external {
    for (uint256 i = 0; i < users.length; i++) {
        _claimRewards(users[i]);
    }
}
```

### **3. Events Over Storage**

```solidity
// Use events for historical data (cheaper than storage)
event SignalPurchased(
    bytes32 indexed signalId,
    address indexed buyer,
    uint256 amount,
    uint256 timestamp
);

// Query events off-chain instead of storing in contract
```

### **4. Immutable Variables**

```solidity
// Use immutable for constructor-set values (cheaper reads)
address public immutable fibtToken;
address public immutable strategyNFT;

constructor(address _fibt, address _nft) {
    fibtToken = _fibt;
    strategyNFT = _nft;
}
```

---

## 🚀 DEPLOYMENT STRATEGY

### **Phase 1: Testnet Deployment (Week 1-2)**

```javascript
// Arbitrum Sepolia Testnet
const deploymentOrder = [
    "1. FIBTToken",
    "2. StrategyNFT", 
    "3. StakingManager (proxy)",
    "4. SignalEscrow (proxy)",
    "5. MT5Oracle",
    "6. RevenueDistributor",
    "7. GovernanceDAO"
];

// Hardhat deployment script
async function deployTestnet() {
    // Deploy FIBT token
    const FIBTToken = await ethers.getContractFactory("FIBTToken");
    const fibt = await FIBTToken.deploy(deployer.address, treasury.address);
    await fibt.deployed();
    
    // Deploy upgradeable contracts via proxy
    const StakingManager = await ethers.getContractFactory("StakingManager");
    const staking = await upgrades.deployProxy(
        StakingManager, 
        [fibt.address],
        { initializer: 'initialize' }
    );
    
    // ... deploy remaining contracts
}
```

### **Phase 2: Audit & Security (Week 3-6)**

```
Week 3-4: CertiK Audit
  - Smart contract security review
  - Economic model analysis
  - Oracle security assessment
  
Week 5: OpenZeppelin Audit (optional second audit)
  - Upgrade safety review
  - Access control verification
  
Week 6: Bug Bounty Program
  - $100K total rewards
  - Critical: $50K
  - High: $25K
  - Medium: $15K
  - Low: $10K
```

### **Phase 3: Mainnet Deployment (Week 7)**

```javascript
// Arbitrum One Mainnet
const mainnetDeployment = {
    network: "arbitrum-mainnet",
    gasPrice: "0.1 gwei", // Arbitrum is cheap
    
    steps: [
        "1. Deploy FIBTToken with timelock",
        "2. Transfer ownership to multisig (3/5)",
        "3. Deploy all contracts",
        "4. Verify on Arbiscan",
        "5. Renounce deployer ownership",
        "6. Transfer control to governance"
    ]
};
```

### **Phase 4: Liquidity Launch (Week 8)**

```
Uniswap V3 (Arbitrum):
  - Pair: FIBT/USDC
  - Initial Liquidity: 2.5M FIBT + $300K USDC
  - Price Range: $0.08 - $0.18 (concentrated)
  - Lock Duration: 24 months
  
Camelot DEX (Arbitrum):
  - Pair: FIBT/USDC
  - Liquidity: 1M FIBT + $120K USDC
  - Incentives: 500K FIBT over 6 months
```

---

## 🧪 TESTING STRATEGY

### **Unit Tests (95%+ Coverage)**

```javascript
// Example: StakingManager tests
describe("StakingManager", function() {
    it("Should allow users to stake", async function() {
        await fibt.approve(staking.address, ethers.utils.parseEther("5000"));
        await staking.stake(ethers.utils.parseEther("5000"));
        
        const userStake = await staking.stakes(user.address);
        expect(userStake.amount).to.equal(ethers.utils.parseEther("5000"));
        expect(userStake.tier).to.equal(2); // PROFESSIONAL
    });
    
    it("Should calculate rewards correctly", async function() {
        await staking.stake(ethers.utils.parseEther("5000"));
        
        // Fast forward 30 days
        await ethers.provider.send("evm_increaseTime", [30 * 24 * 60 * 60]);
        await ethers.provider.send("evm_mine");
        
        const rewards = await staking.calculateRewards(user.address);
        // Expected: (5000 * 800 * 30 days) / (365 days * 10000) ≈ 32.87 FIBT
        expect(rewards).to.be.closeTo(
            ethers.utils.parseEther("32.87"), 
            ethers.utils.parseEther("0.1")
        );
    });
});
```

### **Integration Tests**

```javascript
// Example: Full signal purchase flow
describe("Signal Purchase Flow", function() {
    it("Should handle complete signal lifecycle", async function() {
        // 1. User buys signal
        await escrow.buySignal(signalId, creator.address, 10);
        
        // 2. Oracle reports TP hit
        await oracle.submitReport(signalId, true, signature1);
        await oracle.submitReport(signalId, true, signature2);
        await oracle.submitReport(signalId, true, signature3);
        
        // 3. Verify distributions
        const creatorBalance = await fibt.balanceOf(creator.address);
        expect(creatorBalance).to.equal(ethers.utils.parseEther("7")); // 70%
        
        const burned = await fibt.balanceOf(BURN_ADDRESS);
        expect(burned).to.equal(ethers.utils.parseEther("1")); // 10%
    });
});
```

### **Fuzz Testing (Echidna)**

```solidity
// Property-based testing
contract StakingManagerEchidna {
    StakingManager staking;
    
    // Invariant: Total staked should never exceed token supply
    function echidna_total_staked_invariant() public returns (bool) {
        return staking.totalStaked() <= fibtToken.totalSupply();
    }
    
    // Invariant: Rewards pool should never go negative
    function echidna_rewards_pool_positive() public returns (bool) {
        return staking.rewardsPool() >= 0;
    }
}
```

---

## 📦 CONTRACT DEPLOYMENT ADDRESSES (Placeholder)

### **Arbitrum Sepolia Testnet**

```
FIBT Token:             0x... (to be deployed)
Strategy NFT:           0x... (to be deployed)
Staking Manager:        0x... (proxy)
Signal Escrow:          0x... (proxy)
MT5 Oracle:             0x... (to be deployed)
Revenue Distributor:    0x... (proxy)
Governance DAO:         0x... (proxy)
```

### **Arbitrum One Mainnet**

```
TBD after testnet validation
```

---

## 🔐 SECURITY CHECKLIST

### **Pre-Audit**
- [ ] All contracts use OpenZeppelin libraries (latest version)
- [ ] Reentrancy guards on all external functions
- [ ] Access control properly implemented
- [ ] No floating pragma versions (use ^0.8.20)
- [ ] Events emitted for all state changes
- [ ] Input validation on all public functions
- [ ] Integer overflow protection (Solidity 0.8+)
- [ ] No tx.origin authentication (use msg.sender)
- [ ] Proper error messages for requires

### **Audit Phase**
- [ ] CertiK audit scheduled (4 weeks)
- [ ] OpenZeppelin audit (optional, 2 weeks)
- [ ] Address all audit findings (Critical/High priority)
- [ ] Re-audit after fixes

### **Pre-Mainnet**
- [ ] Bug bounty program live ($100K pool)
- [ ] Multisig setup (3 of 5 for governance)
- [ ] Timelock deployed (48 hours minimum)
- [ ] Emergency pause guardian assigned
- [ ] Insurance coverage obtained (Nexus Mutual)

### **Post-Launch**
- [ ] Continuous monitoring (Forta, OpenZeppelin Defender)
- [ ] Quarterly security reviews
- [ ] Incident response plan documented
- [ ] Bug bounty ongoing

---

## 📚 ADDITIONAL CONTRACT FILES

### **File Structure**

```
contracts/
├── core/
│   ├── FIBTToken.sol
│   ├── StrategyNFT.sol
│   └── FibtoolTimelock.sol
│
├── logic/
│   ├── StakingManager.sol
│   ├── SignalEscrow.sol
│   ├── StrategyRegistry.sol
│   ├── RevenueDistributor.sol
│   └── GovernanceDAO.sol
│
├── oracles/
│   ├── PriceOracle.sol
│   ├── MT5Oracle.sol
│   └── PerformanceVerifier.sol
│
├── utils/
│   ├── FeeManager.sol
│   ├── VIPTierManager.sol
│   ├── TokenBurner.sol
│   └── EmergencyPause.sol
│
├── libraries/
│   ├── SignalValidation.sol
│   ├── MathUtils.sol
│   └── AccessControl.sol
│
└── interfaces/
    ├── IFIBTToken.sol
    ├── IStakingManager.sol
    └── ISignalEscrow.sol
```

---

## 🎯 NEXT STEPS

1. **Implement Remaining Contracts** (SignalEscrow, StrategyRegistry, etc.)
2. **Write Comprehensive Tests** (target 95%+ coverage)
3. **Deploy to Testnet** (Arbitrum Sepolia)
4. **Frontend Integration** (Web3.js/Ethers.js)
5. **Audit Preparation** (documentation, threat models)
6. **Mainnet Launch** (Q2 2026 target)

---

**Document Version:** 1.0  
**Last Updated:** November 10, 2025  
**Author:** Siga Saint  
**Status:** Design Phase (Pre-Implementation)  

---

**© 2025 Siga Saint. All Rights Reserved.**  
**Fibtool™ Smart Contracts - Proprietary & Confidential**

---

*Next Document: WHITEPAPER.md (Technical & Tokenomics Overview)*
