// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title StakingManager
 * @dev Manages FIBT token staking with 4 tiers and auto-compound
 */
contract StakingManager is Ownable, ReentrancyGuard {
    IERC20 public immutable fibtToken;
    
    // Tier enum
    enum Tier { Bronze, Silver, Gold, Platinum }
    
    // Tier requirements and APY
    struct TierInfo {
        uint256 minAmount;
        uint256 apyBasisPoints; // APY in basis points (1% = 100)
    }
    
    // Stake info
    struct StakeInfo {
        uint256 amount;
        uint256 stakedAt;
        uint256 lastClaimAt;
        Tier tier;
        bool autoCompound;
    }
    
    // Tier configurations
    mapping(Tier => TierInfo) public tierInfo;
    
    // User stakes
    mapping(address => StakeInfo) public stakes;
    
    // Total staked
    uint256 public totalStaked;
    
    // Reward rate per second (basis points)
    uint256 public constant SECONDS_PER_YEAR = 365 days;
    
    event Staked(address indexed user, uint256 amount, Tier tier, bool autoCompound);
    event Unstaked(address indexed user, uint256 amount);
    event RewardsClaimed(address indexed user, uint256 rewards);
    event TierUpdated(Tier tier, uint256 minAmount, uint256 apyBasisPoints);
    
    constructor(address _fibtToken) Ownable(msg.sender) {
        fibtToken = IERC20(_fibtToken);
        
        // Initialize tiers
        tierInfo[Tier.Bronze] = TierInfo(1_000 * 10**18, 500);    // 1K FIBT, 5% APY
        tierInfo[Tier.Silver] = TierInfo(5_000 * 10**18, 800);    // 5K FIBT, 8% APY
        tierInfo[Tier.Gold] = TierInfo(20_000 * 10**18, 1200);    // 20K FIBT, 12% APY
        tierInfo[Tier.Platinum] = TierInfo(100_000 * 10**18, 1500); // 100K FIBT, 15% APY
    }
    
    /**
     * @dev Stake tokens
     */
    function stake(uint256 amount, Tier tier, bool autoCompound) external nonReentrant {
        require(amount >= tierInfo[tier].minAmount, "Amount below tier minimum");
        
        // If already staking, claim pending rewards first
        if (stakes[msg.sender].amount > 0) {
            _claimRewards();
        }
        
        // Transfer tokens
        require(
            fibtToken.transferFrom(msg.sender, address(this), amount),
            "Transfer failed"
        );
        
        // Update stake
        stakes[msg.sender] = StakeInfo({
            amount: stakes[msg.sender].amount + amount,
            stakedAt: block.timestamp,
            lastClaimAt: block.timestamp,
            tier: tier,
            autoCompound: autoCompound
        });
        
        totalStaked += amount;
        
        emit Staked(msg.sender, amount, tier, autoCompound);
    }
    
    /**
     * @dev Unstake tokens
     */
    function unstake(uint256 amount) external nonReentrant {
        StakeInfo storage stakeInfo = stakes[msg.sender];
        require(stakeInfo.amount >= amount, "Insufficient stake");
        
        // Claim pending rewards
        _claimRewards();
        
        // Update stake
        stakeInfo.amount -= amount;
        totalStaked -= amount;
        
        // Transfer tokens back
        require(fibtToken.transfer(msg.sender, amount), "Transfer failed");
        
        emit Unstaked(msg.sender, amount);
    }
    
    /**
     * @dev Claim rewards
     */
    function claimRewards() external nonReentrant {
        _claimRewards();
    }
    
    /**
     * @dev Internal claim rewards
     */
    function _claimRewards() internal {
        uint256 rewards = calculatePendingRewards(msg.sender);
        if (rewards == 0) return;
        
        StakeInfo storage stakeInfo = stakes[msg.sender];
        stakeInfo.lastClaimAt = block.timestamp;
        
        if (stakeInfo.autoCompound) {
            // Add to stake
            stakeInfo.amount += rewards;
            totalStaked += rewards;
        } else {
            // Transfer to user
            require(fibtToken.transfer(msg.sender, rewards), "Transfer failed");
        }
        
        emit RewardsClaimed(msg.sender, rewards);
    }
    
    /**
     * @dev Calculate pending rewards
     */
    function calculatePendingRewards(address user) public view returns (uint256) {
        StakeInfo memory stakeInfo = stakes[user];
        if (stakeInfo.amount == 0) return 0;
        
        uint256 timeStaked = block.timestamp - stakeInfo.lastClaimAt;
        TierInfo memory tier = tierInfo[stakeInfo.tier];
        
        // Rewards = (amount * APY * timeStaked) / (10000 * SECONDS_PER_YEAR)
        return (stakeInfo.amount * tier.apyBasisPoints * timeStaked) / (10000 * SECONDS_PER_YEAR);
    }
    
    /**
     * @dev Update tier configuration
     */
    function updateTier(
        Tier tier,
        uint256 minAmount,
        uint256 apyBasisPoints
    ) external onlyOwner {
        tierInfo[tier] = TierInfo(minAmount, apyBasisPoints);
        emit TierUpdated(tier, minAmount, apyBasisPoints);
    }
    
    /**
     * @dev Get user stake info
     */
    function getStakeInfo(address user) external view returns (StakeInfo memory) {
        return stakes[user];
    }
}
