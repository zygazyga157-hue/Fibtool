// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title RevenueDistributor
 * @dev Automatically distribute platform revenue to stakeholders
 * 
 * Revenue Split:
 * - 40% → Staking rewards pool
 * - 30% → Buyback & burn
 * - 20% → DAO treasury
 * - 10% → Development fund
 * 
 * Features:
 * - Automatic monthly distributions
 * - Configurable split percentages (governance)
 * - Transparent accounting
 * - Emergency withdraw protection
 */
contract RevenueDistributor is
    Initializable,
    ReentrancyGuardUpgradeable,
    AccessControlUpgradeable
{
    /// @notice FIBT token
    address public fibtToken;
    
    /// @notice Staking manager
    address public stakingManager;
    
    /// @notice DAO treasury
    address public daoTreasury;
    
    /// @notice Development fund
    address public devFund;
    
    /// @notice Buyback executor
    address public buybackExecutor;
    
    /// @notice Admin role
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Distributor role (can trigger distributions)
    bytes32 public constant DISTRIBUTOR_ROLE = keccak256("DISTRIBUTOR_ROLE");
    
    /// @notice Revenue allocation (in basis points, must sum to 10000)
    struct RevenueAllocation {
        uint256 stakingBps;     // 4000 = 40%
        uint256 buybackBps;     // 3000 = 30%
        uint256 daoTreasuryBps; // 2000 = 20%
        uint256 devFundBps;     // 1000 = 10%
    }
    
    /// @notice Current allocation
    RevenueAllocation public allocation;
    
    /// @notice Distribution period (30 days)
    uint256 public distributionPeriod;
    
    /// @notice Last distribution timestamp
    uint256 public lastDistribution;
    
    /// @notice Total revenue collected
    uint256 public totalRevenueCollected;
    
    /// @notice Total distributed
    uint256 public totalDistributed;
    
    /// @notice Distribution history
    struct DistributionEvent {
        uint256 timestamp;
        uint256 totalAmount;
        uint256 stakingAmount;
        uint256 buybackAmount;
        uint256 treasuryAmount;
        uint256 devAmount;
    }
    
    /// @notice Distribution history array
    DistributionEvent[] public distributions;
    
    /// Events
    event RevenueReceived(address indexed from, uint256 amount, uint256 timestamp);
    
    event RevenueDistributed(
        uint256 indexed distributionId,
        uint256 totalAmount,
        uint256 stakingAmount,
        uint256 buybackAmount,
        uint256 treasuryAmount,
        uint256 devAmount
    );
    
    event AllocationUpdated(
        uint256 stakingBps,
        uint256 buybackBps,
        uint256 treasuryBps,
        uint256 devBps
    );
    
    event BuybackExecuted(uint256 amount, uint256 fibtBought);
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize contract
     * @param _fibtToken FIBT token address
     * @param _stakingManager Staking manager address
     * @param _daoTreasury DAO treasury address
     * @param _devFund Development fund address
     * @param _buybackExecutor Buyback executor address
     */
    function initialize(
        address _fibtToken,
        address _stakingManager,
        address _daoTreasury,
        address _devFund,
        address _buybackExecutor
    ) external initializer {
        __ReentrancyGuard_init();
        __AccessControl_init();
        
        require(_fibtToken != address(0), "Invalid FIBT address");
        require(_stakingManager != address(0), "Invalid staking address");
        require(_daoTreasury != address(0), "Invalid treasury address");
        require(_devFund != address(0), "Invalid dev fund address");
        require(_buybackExecutor != address(0), "Invalid buyback address");
        
        fibtToken = _fibtToken;
        stakingManager = _stakingManager;
        daoTreasury = _daoTreasury;
        devFund = _devFund;
        buybackExecutor = _buybackExecutor;
        
        // Set default allocation
        allocation = RevenueAllocation({
            stakingBps: 4000,      // 40%
            buybackBps: 3000,      // 30%
            daoTreasuryBps: 2000,  // 20%
            devFundBps: 1000       // 10%
        });
        
        // Set distribution period to 30 days
        distributionPeriod = 30 days;
        lastDistribution = block.timestamp;
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(DISTRIBUTOR_ROLE, msg.sender);
    }
    
    /**
     * @dev Receive revenue (from platform fees, signal sales, etc.)
     */
    function receiveRevenue(uint256 amount) external nonReentrant {
        require(amount > 0, "Amount must be > 0");
        
        require(
            IERC20(fibtToken).transferFrom(msg.sender, address(this), amount),
            "Transfer failed"
        );
        
        totalRevenueCollected += amount;
        
        emit RevenueReceived(msg.sender, amount, block.timestamp);
    }
    
    /**
     * @dev Distribute accumulated revenue
     * Can be called by anyone after distribution period
     */
    function distribute() external nonReentrant {
        require(
            block.timestamp >= lastDistribution + distributionPeriod ||
            hasRole(DISTRIBUTOR_ROLE, msg.sender),
            "Distribution period not reached"
        );
        
        uint256 balance = IERC20(fibtToken).balanceOf(address(this));
        require(balance > 0, "No revenue to distribute");
        
        // Calculate amounts
        uint256 stakingAmount = (balance * allocation.stakingBps) / 10000;
        uint256 buybackAmount = (balance * allocation.buybackBps) / 10000;
        uint256 treasuryAmount = (balance * allocation.daoTreasuryBps) / 10000;
        uint256 devAmount = balance - stakingAmount - buybackAmount - treasuryAmount;
        
        // Transfer to staking rewards pool
        require(
            IERC20(fibtToken).transfer(stakingManager, stakingAmount),
            "Staking transfer failed"
        );
        
        // Transfer to buyback executor
        require(
            IERC20(fibtToken).transfer(buybackExecutor, buybackAmount),
            "Buyback transfer failed"
        );
        
        // Transfer to DAO treasury
        require(
            IERC20(fibtToken).transfer(daoTreasury, treasuryAmount),
            "Treasury transfer failed"
        );
        
        // Transfer to dev fund
        require(
            IERC20(fibtToken).transfer(devFund, devAmount),
            "Dev fund transfer failed"
        );
        
        // Record distribution
        distributions.push(DistributionEvent({
            timestamp: block.timestamp,
            totalAmount: balance,
            stakingAmount: stakingAmount,
            buybackAmount: buybackAmount,
            treasuryAmount: treasuryAmount,
            devAmount: devAmount
        }));
        
        totalDistributed += balance;
        lastDistribution = block.timestamp;
        
        emit RevenueDistributed(
            distributions.length - 1,
            balance,
            stakingAmount,
            buybackAmount,
            treasuryAmount,
            devAmount
        );
    }
    
    /**
     * @dev Update revenue allocation (governance)
     * @param stakingBps Staking allocation (basis points)
     * @param buybackBps Buyback allocation (basis points)
     * @param treasuryBps Treasury allocation (basis points)
     * @param devBps Dev fund allocation (basis points)
     */
    function updateAllocation(
        uint256 stakingBps,
        uint256 buybackBps,
        uint256 treasuryBps,
        uint256 devBps
    ) external onlyRole(ADMIN_ROLE) {
        require(
            stakingBps + buybackBps + treasuryBps + devBps == 10000,
            "Must sum to 100%"
        );
        require(stakingBps >= 2000, "Staking must be >= 20%");
        
        allocation = RevenueAllocation({
            stakingBps: stakingBps,
            buybackBps: buybackBps,
            daoTreasuryBps: treasuryBps,
            devFundBps: devBps
        });
        
        emit AllocationUpdated(stakingBps, buybackBps, treasuryBps, devBps);
    }
    
    /**
     * @dev Update distribution period
     * @param newPeriod New period in seconds
     */
    function updateDistributionPeriod(uint256 newPeriod) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        require(newPeriod >= 7 days, "Period too short");
        require(newPeriod <= 90 days, "Period too long");
        distributionPeriod = newPeriod;
    }
    
    /**
     * @dev Get current revenue balance
     * @return Current balance available for distribution
     */
    function getCurrentBalance() external view returns (uint256) {
        return IERC20(fibtToken).balanceOf(address(this));
    }
    
    /**
     * @dev Get distribution history count
     * @return Number of distributions
     */
    function getDistributionCount() external view returns (uint256) {
        return distributions.length;
    }
    
    /**
     * @dev Get specific distribution event
     * @param index Distribution index
     * @return Distribution event
     */
    function getDistribution(uint256 index) 
        external 
        view 
        returns (DistributionEvent memory) 
    {
        require(index < distributions.length, "Invalid index");
        return distributions[index];
    }
    
    /**
     * @dev Get time until next distribution
     * @return Seconds until next distribution (0 if ready)
     */
    function timeUntilNextDistribution() external view returns (uint256) {
        uint256 nextDistribution = lastDistribution + distributionPeriod;
        if (block.timestamp >= nextDistribution) {
            return 0;
        }
        return nextDistribution - block.timestamp;
    }
    
    /**
     * @dev Emergency withdraw (governance only, for contract upgrade)
     * @param token Token to withdraw
     * @param recipient Recipient address
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(
        address token,
        address recipient,
        uint256 amount
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(recipient != address(0), "Invalid recipient");
        IERC20(token).transfer(recipient, amount);
    }
}

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}
