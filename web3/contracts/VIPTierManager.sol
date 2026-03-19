// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title VIPTierManager
 * @dev Manage VIP tiers and fee discounts based on holdings
 * 
 * VIP Tiers:
 * - VIP 0: No FIBT held (baseline fees)
 * - VIP 1: 500+ FIBT held (10% discount)
 * - VIP 2: 2,000+ FIBT staked (20% discount)
 * - VIP 3: 10,000+ FIBT staked (40% discount)
 * - VIP 4: 50,000+ FIBT staked (60% discount)
 * - VIP 5: 100,000+ FIBT OR Elite NFT (80% discount)
 * 
 * Features:
 * - Dynamic tier calculation
 * - 30-day average holdings (anti-gaming)
 * - NFT-based tier boosting
 * - Fee discount calculation
 */
contract VIPTierManager is
    Initializable,
    AccessControlUpgradeable
{
    /// @notice FIBT token
    address public fibtToken;
    
    /// @notice Staking manager
    address public stakingManager;
    
    /// @notice Strategy NFT
    address public strategyNFT;
    
    /// @notice Admin role
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice VIP tier enum
    enum VIPTier { VIP0, VIP1, VIP2, VIP3, VIP4, VIP5 }
    
    /// @notice Tier requirements
    struct TierRequirement {
        uint256 minHoldings;   // Minimum holdings (not staked)
        uint256 minStaked;     // Minimum staked amount
        bool requiresNFT;      // Whether Elite NFT required
        uint256 feeDiscountBps; // Fee discount (in basis points)
    }
    
    /// @notice Tier to requirements
    mapping(VIPTier => TierRequirement) public tierRequirements;
    
    /// @notice User holdings history for 30-day average
    struct HoldingSnapshot {
        uint256 timestamp;
        uint256 holdings;
        uint256 staked;
    }
    
    /// @notice User to snapshots
    mapping(address => HoldingSnapshot[]) public holdingHistory;
    
    /// @notice Snapshot frequency (1 day)
    uint256 public constant SNAPSHOT_FREQUENCY = 1 days;
    
    /// @notice Average period (30 days)
    uint256 public constant AVERAGE_PERIOD = 30 days;
    
    /// @notice User to last snapshot time
    mapping(address => uint256) public lastSnapshotTime;
    
    /// Events
    event TierUpdated(address indexed user, VIPTier oldTier, VIPTier newTier);
    event TierRequirementUpdated(VIPTier tier, uint256 minHoldings, uint256 minStaked);
    event SnapshotRecorded(address indexed user, uint256 holdings, uint256 staked);
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize contract
     * @param _fibtToken FIBT token address
     * @param _stakingManager Staking manager address
     * @param _strategyNFT Strategy NFT address
     */
    function initialize(
        address _fibtToken,
        address _stakingManager,
        address _strategyNFT
    ) external initializer {
        __AccessControl_init();
        
        require(_fibtToken != address(0), "Invalid FIBT address");
        require(_stakingManager != address(0), "Invalid staking address");
        require(_strategyNFT != address(0), "Invalid NFT address");
        
        fibtToken = _fibtToken;
        stakingManager = _stakingManager;
        strategyNFT = _strategyNFT;
        
        // Set tier requirements
        tierRequirements[VIPTier.VIP0] = TierRequirement({
            minHoldings: 0,
            minStaked: 0,
            requiresNFT: false,
            feeDiscountBps: 0  // 0% discount
        });
        
        tierRequirements[VIPTier.VIP1] = TierRequirement({
            minHoldings: 500 * 10**18,
            minStaked: 0,
            requiresNFT: false,
            feeDiscountBps: 1000  // 10% discount
        });
        
        tierRequirements[VIPTier.VIP2] = TierRequirement({
            minHoldings: 0,
            minStaked: 2_000 * 10**18,
            requiresNFT: false,
            feeDiscountBps: 2000  // 20% discount
        });
        
        tierRequirements[VIPTier.VIP3] = TierRequirement({
            minHoldings: 0,
            minStaked: 10_000 * 10**18,
            requiresNFT: false,
            feeDiscountBps: 4000  // 40% discount
        });
        
        tierRequirements[VIPTier.VIP4] = TierRequirement({
            minHoldings: 0,
            minStaked: 50_000 * 10**18,
            requiresNFT: false,
            feeDiscountBps: 6000  // 60% discount
        });
        
        tierRequirements[VIPTier.VIP5] = TierRequirement({
            minHoldings: 0,
            minStaked: 100_000 * 10**18,
            requiresNFT: false,  // OR holds Elite NFT
            feeDiscountBps: 8000  // 80% discount
        });
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }
    
    /**
     * @dev Get user's current VIP tier
     * @param user User address
     * @return Current VIP tier
     */
    function getUserTier(address user) public view returns (VIPTier) {
        // Check if user holds Elite NFT (instant VIP5)
        if (_hasEliteNFT(user)) {
            return VIPTier.VIP5;
        }
        
        // Get 30-day average holdings
        (uint256 avgHoldings, uint256 avgStaked) = get30DayAverage(user);
        
        // Determine tier (check from highest to lowest)
        if (avgStaked >= tierRequirements[VIPTier.VIP5].minStaked) {
            return VIPTier.VIP5;
        }
        if (avgStaked >= tierRequirements[VIPTier.VIP4].minStaked) {
            return VIPTier.VIP4;
        }
        if (avgStaked >= tierRequirements[VIPTier.VIP3].minStaked) {
            return VIPTier.VIP3;
        }
        if (avgStaked >= tierRequirements[VIPTier.VIP2].minStaked) {
            return VIPTier.VIP2;
        }
        if (avgHoldings >= tierRequirements[VIPTier.VIP1].minHoldings) {
            return VIPTier.VIP1;
        }
        
        return VIPTier.VIP0;
    }
    
    /**
     * @dev Check if user holds Elite NFT
     * @param user User address
     * @return Whether user holds Elite NFT
     */
    function _hasEliteNFT(address user) internal view returns (bool) {
        // Check if user owns any NFT with Elite tier
        // Note: This requires StrategyNFT to have enumeration
        // For now, simplified check
        try IStrategyNFT(strategyNFT).balanceOf(user) returns (uint256 balance) {
            if (balance == 0) return false;
            
            // In production, iterate through user's NFTs and check tiers
            // For now, assume any NFT ownership gives bonus
            return balance > 0;
        } catch {
            return false;
        }
    }
    
    /**
     * @dev Get 30-day average holdings
     * @param user User address
     * @return avgHoldings Average holdings
     * @return avgStaked Average staked amount
     */
    function get30DayAverage(address user) 
        public 
        view 
        returns (uint256 avgHoldings, uint256 avgStaked) 
    {
        HoldingSnapshot[] storage snapshots = holdingHistory[user];
        if (snapshots.length == 0) {
            return (0, 0);
        }
        
        uint256 cutoffTime = block.timestamp - AVERAGE_PERIOD;
        uint256 totalHoldings = 0;
        uint256 totalStaked = 0;
        uint256 count = 0;
        
        // Sum recent snapshots
        for (uint256 i = snapshots.length; i > 0; i--) {
            uint256 idx = i - 1;
            if (snapshots[idx].timestamp < cutoffTime) {
                break;  // Too old
            }
            totalHoldings += snapshots[idx].holdings;
            totalStaked += snapshots[idx].staked;
            count++;
        }
        
        if (count == 0) {
            return (0, 0);
        }
        
        avgHoldings = totalHoldings / count;
        avgStaked = totalStaked / count;
    }
    
    /**
     * @dev Record holdings snapshot
     * @param user User address
     */
    function recordSnapshot(address user) external {
        require(
            block.timestamp >= lastSnapshotTime[user] + SNAPSHOT_FREQUENCY,
            "Too soon for snapshot"
        );
        
        // Get current holdings
        uint256 holdings = IERC20(fibtToken).balanceOf(user);
        
        // Get current stake
        uint256 staked = 0;
        try IStakingManager(stakingManager).stakes(user) returns (
            uint256 amount,
            uint256,
            uint256,
            uint8,
            bool
        ) {
            staked = amount;
        } catch {}
        
        // Store snapshot
        holdingHistory[user].push(HoldingSnapshot({
            timestamp: block.timestamp,
            holdings: holdings,
            staked: staked
        }));
        
        lastSnapshotTime[user] = block.timestamp;
        
        // Cleanup old snapshots (keep max 60 days)
        _cleanupOldSnapshots(user);
        
        emit SnapshotRecorded(user, holdings, staked);
    }
    
    /**
     * @dev Cleanup old snapshots
     * @param user User address
     */
    function _cleanupOldSnapshots(address user) internal {
        HoldingSnapshot[] storage snapshots = holdingHistory[user];
        uint256 cutoffTime = block.timestamp - (60 days);
        
        // Find first valid index
        uint256 firstValid = 0;
        for (uint256 i = 0; i < snapshots.length; i++) {
            if (snapshots[i].timestamp >= cutoffTime) {
                firstValid = i;
                break;
            }
        }
        
        // Remove old snapshots
        if (firstValid > 0) {
            for (uint256 i = firstValid; i < snapshots.length; i++) {
                snapshots[i - firstValid] = snapshots[i];
            }
            for (uint256 i = 0; i < firstValid; i++) {
                snapshots.pop();
            }
        }
    }
    
    /**
     * @dev Calculate fee discount for user
     * @param user User address
     * @param baseFee Base fee amount
     * @return Final fee after discount
     */
    function calculateFee(address user, uint256 baseFee) 
        external 
        view 
        returns (uint256) 
    {
        VIPTier tier = getUserTier(user);
        uint256 discountBps = tierRequirements[tier].feeDiscountBps;
        
        uint256 discount = (baseFee * discountBps) / 10000;
        return baseFee - discount;
    }
    
    /**
     * @dev Get fee discount percentage for tier
     * @param tier VIP tier
     * @return Discount in basis points
     */
    function getTierDiscount(VIPTier tier) external view returns (uint256) {
        return tierRequirements[tier].feeDiscountBps;
    }
    
    /**
     * @dev Update tier requirements (governance)
     * @param tier Tier to update
     * @param minHoldings New minimum holdings
     * @param minStaked New minimum staked
     * @param feeDiscountBps New fee discount
     */
    function updateTierRequirement(
        VIPTier tier,
        uint256 minHoldings,
        uint256 minStaked,
        uint256 feeDiscountBps
    ) external onlyRole(ADMIN_ROLE) {
        require(feeDiscountBps <= 9000, "Discount too high"); // Max 90%
        
        tierRequirements[tier].minHoldings = minHoldings;
        tierRequirements[tier].minStaked = minStaked;
        tierRequirements[tier].feeDiscountBps = feeDiscountBps;
        
        emit TierRequirementUpdated(tier, minHoldings, minStaked);
    }
}

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
}

interface IStakingManager {
    function stakes(address user) external view returns (
        uint256 amount,
        uint256 stakedAt,
        uint256 lastClaimAt,
        uint8 tier,
        bool autoCompound
    );
}

interface IStrategyNFT {
    function balanceOf(address owner) external view returns (uint256);
}
