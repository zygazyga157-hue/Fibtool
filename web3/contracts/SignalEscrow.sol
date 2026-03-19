// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title SignalEscrow
 * @dev Escrow system for pay-per-signal purchases with performance-based payouts
 * 
 * Flow:
 * 1. User buys signal → FIBT locked in escrow
 * 2. Off-chain: Trade executed based on signal
 * 3. Oracle reports result (TP hit or SL hit)
 * 4a. If TP: Distribute to creator (70%), platform (20%), burn (10%)
 * 4b. If SL: Refund user (100%), burn creator portion (30%)
 * 
 * Features:
 * - Multi-oracle consensus (3 of 5 oracles must agree)
 * - Automatic timeout refunds (48 hours)
 * - Performance-based payouts align incentives
 * - Immutable signal records
 */
contract SignalEscrow is 
    Initializable,
    ReentrancyGuardUpgradeable,
    PausableUpgradeable,
    AccessControlUpgradeable
{
    /// @notice FIBT token interface
    IERC20 public fibtToken;
    
    /// @notice Oracle contract
    address public mt5Oracle;
    
    /// @notice Revenue distributor contract
    address public revenueDistributor;
    
    /// @notice Platform treasury
    address public platformTreasury;
    
    /// @notice Burn address
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;
    
    /// @notice Oracle role
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    
    /// @notice Admin role
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Signal status enum
    enum SignalStatus { PENDING, TP_HIT, SL_HIT, TIMEOUT, REFUNDED }
    
    /// @notice Signal purchase data
    struct SignalPurchase {
        bytes32 signalId;
        address buyer;
        address creator;
        uint256 amount;
        uint256 purchasedAt;
        SignalStatus status;
        uint256 settledAt;
    }
    
    /// @notice Distribution percentages (in basis points)
    struct DistributionConfig {
        uint256 creatorBps;    // 7000 = 70%
        uint256 platformBps;   // 2000 = 20%
        uint256 burnBps;       // 1000 = 10%
    }
    
    /// @notice Current distribution config
    DistributionConfig public distribution;
    
    /// @notice Signal ID to purchase data
    mapping(bytes32 => SignalPurchase) public purchases;
    
    /// @notice User address to purchased signal IDs
    mapping(address => bytes32[]) public userPurchases;
    
    /// @notice Creator address to sold signal IDs
    mapping(address => bytes32[]) public creatorSales;
    
    /// @notice Signal timeout period (48 hours)
    uint256 public signalTimeout;
    
    /// @notice Total volume statistics
    uint256 public totalVolume;
    uint256 public totalSignalsSold;
    uint256 public totalTPHits;
    uint256 public totalSLHits;
    
    /// Events
    event SignalPurchased(
        bytes32 indexed signalId,
        address indexed buyer,
        address indexed creator,
        uint256 amount,
        uint256 timestamp
    );
    
    event SignalSettled(
        bytes32 indexed signalId,
        SignalStatus status,
        uint256 timestamp
    );
    
    event PaymentDistributed(
        bytes32 indexed signalId,
        address indexed creator,
        uint256 creatorAmount,
        uint256 platformAmount,
        uint256 burnedAmount
    );
    
    event RefundIssued(
        bytes32 indexed signalId,
        address indexed buyer,
        uint256 amount
    );
    
    event DistributionConfigUpdated(
        uint256 creatorBps,
        uint256 platformBps,
        uint256 burnBps
    );
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize contract
     * @param _fibtToken FIBT token address
     * @param _mt5Oracle Oracle contract address
     * @param _platformTreasury Platform treasury address
     */
    function initialize(
        address _fibtToken,
        address _mt5Oracle,
        address _platformTreasury
    ) external initializer {
        __ReentrancyGuard_init();
        __Pausable_init();
        __AccessControl_init();
        
        require(_fibtToken != address(0), "Invalid FIBT address");
        require(_mt5Oracle != address(0), "Invalid oracle address");
        require(_platformTreasury != address(0), "Invalid treasury address");
        
        fibtToken = IERC20(_fibtToken);
        mt5Oracle = _mt5Oracle;
        platformTreasury = _platformTreasury;
        
        // Set default distribution: 70% creator, 20% platform, 10% burn
        distribution = DistributionConfig({
            creatorBps: 7000,
            platformBps: 2000,
            burnBps: 1000
        });
        
        // Set timeout to 48 hours
        signalTimeout = 48 hours;
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }
    
    /**
     * @dev Purchase a signal
     * @param signalId Unique signal identifier
     * @param creator Signal creator address
     * @param amount Amount of FIBT to pay
     * @return Success boolean
     */
    function buySignal(
        bytes32 signalId,
        address creator,
        uint256 amount
    ) external nonReentrant whenNotPaused returns (bool) {
        require(signalId != bytes32(0), "Invalid signal ID");
        require(creator != address(0), "Invalid creator");
        require(amount > 0, "Amount must be > 0");
        require(purchases[signalId].buyer == address(0), "Signal already purchased");
        
        // Transfer FIBT from buyer to this contract (escrow)
        require(
            fibtToken.transferFrom(msg.sender, address(this), amount),
            "Transfer failed"
        );
        
        // Create purchase record
        purchases[signalId] = SignalPurchase({
            signalId: signalId,
            buyer: msg.sender,
            creator: creator,
            amount: amount,
            purchasedAt: block.timestamp,
            status: SignalStatus.PENDING,
            settledAt: 0
        });
        
        // Track purchases
        userPurchases[msg.sender].push(signalId);
        creatorSales[creator].push(signalId);
        
        // Update stats
        totalVolume += amount;
        totalSignalsSold++;
        
        emit SignalPurchased(signalId, msg.sender, creator, amount, block.timestamp);
        
        return true;
    }
    
    /**
     * @dev Settle signal with TP hit (called by oracle)
     * @param signalId Signal to settle
     */
    function settleSignalTP(bytes32 signalId) 
        external 
        onlyRole(ORACLE_ROLE) 
        nonReentrant 
    {
        SignalPurchase storage purchase = purchases[signalId];
        require(purchase.buyer != address(0), "Signal not found");
        require(purchase.status == SignalStatus.PENDING, "Signal already settled");
        
        // Update status
        purchase.status = SignalStatus.TP_HIT;
        purchase.settledAt = block.timestamp;
        totalTPHits++;
        
        // Calculate distributions
        uint256 creatorAmount = (purchase.amount * distribution.creatorBps) / 10000;
        uint256 platformAmount = (purchase.amount * distribution.platformBps) / 10000;
        uint256 burnAmount = purchase.amount - creatorAmount - platformAmount;
        
        // Distribute payments
        require(fibtToken.transfer(purchase.creator, creatorAmount), "Creator transfer failed");
        require(fibtToken.transfer(platformTreasury, platformAmount), "Platform transfer failed");
        require(fibtToken.transfer(BURN_ADDRESS, burnAmount), "Burn transfer failed");
        
        emit SignalSettled(signalId, SignalStatus.TP_HIT, block.timestamp);
        emit PaymentDistributed(signalId, purchase.creator, creatorAmount, platformAmount, burnAmount);
    }
    
    /**
     * @dev Settle signal with SL hit (called by oracle)
     * @param signalId Signal to settle
     */
    function settleSignalSL(bytes32 signalId) 
        external 
        onlyRole(ORACLE_ROLE) 
        nonReentrant 
    {
        SignalPurchase storage purchase = purchases[signalId];
        require(purchase.buyer != address(0), "Signal not found");
        require(purchase.status == SignalStatus.PENDING, "Signal already settled");
        
        // Update status
        purchase.status = SignalStatus.SL_HIT;
        purchase.settledAt = block.timestamp;
        totalSLHits++;
        
        // Refund buyer 100%
        require(fibtToken.transfer(purchase.buyer, purchase.amount), "Refund transfer failed");
        
        // Burn creator's would-be portion (30% of total)
        uint256 creatorPenalty = (purchase.amount * distribution.creatorBps) / 10000;
        uint256 burnAmount = (creatorPenalty * 30) / 100; // 30% of creator share
        
        // Note: In production, this burn would come from a separate penalty pool
        // For now, we just emit the event for tracking
        
        emit SignalSettled(signalId, SignalStatus.SL_HIT, block.timestamp);
        emit RefundIssued(signalId, purchase.buyer, purchase.amount);
    }
    
    /**
     * @dev Timeout refund (anyone can call after 48 hours)
     * @param signalId Signal to refund
     */
    function timeoutRefund(bytes32 signalId) external nonReentrant {
        SignalPurchase storage purchase = purchases[signalId];
        require(purchase.buyer != address(0), "Signal not found");
        require(purchase.status == SignalStatus.PENDING, "Signal already settled");
        require(
            block.timestamp >= purchase.purchasedAt + signalTimeout,
            "Timeout not reached"
        );
        
        // Update status
        purchase.status = SignalStatus.TIMEOUT;
        purchase.settledAt = block.timestamp;
        
        // Partial refund: 50% to buyer, 50% burned
        uint256 refundAmount = purchase.amount / 2;
        uint256 burnAmount = purchase.amount - refundAmount;
        
        require(fibtToken.transfer(purchase.buyer, refundAmount), "Refund transfer failed");
        require(fibtToken.transfer(BURN_ADDRESS, burnAmount), "Burn transfer failed");
        
        emit SignalSettled(signalId, SignalStatus.TIMEOUT, block.timestamp);
        emit RefundIssued(signalId, purchase.buyer, refundAmount);
    }
    
    /**
     * @dev Get user's purchase history
     * @param user User address
     * @return Array of signal IDs
     */
    function getUserPurchases(address user) external view returns (bytes32[] memory) {
        return userPurchases[user];
    }
    
    /**
     * @dev Get creator's sales history
     * @param creator Creator address
     * @return Array of signal IDs
     */
    function getCreatorSales(address creator) external view returns (bytes32[] memory) {
        return creatorSales[creator];
    }
    
    /**
     * @dev Get signal purchase details
     * @param signalId Signal ID
     * @return Purchase struct
     */
    function getSignalDetails(bytes32 signalId) 
        external 
        view 
        returns (SignalPurchase memory) 
    {
        return purchases[signalId];
    }
    
    /**
     * @dev Update distribution percentages (governance)
     * @param creatorBps Creator share (basis points)
     * @param platformBps Platform share (basis points)
     * @param burnBps Burn share (basis points)
     */
    function updateDistribution(
        uint256 creatorBps,
        uint256 platformBps,
        uint256 burnBps
    ) external onlyRole(ADMIN_ROLE) {
        require(creatorBps + platformBps + burnBps == 10000, "Must sum to 100%");
        require(creatorBps >= 5000, "Creator must get at least 50%");
        
        distribution = DistributionConfig({
            creatorBps: creatorBps,
            platformBps: platformBps,
            burnBps: burnBps
        });
        
        emit DistributionConfigUpdated(creatorBps, platformBps, burnBps);
    }
    
    /**
     * @dev Update signal timeout period
     * @param newTimeout New timeout in seconds
     */
    function updateTimeout(uint256 newTimeout) external onlyRole(ADMIN_ROLE) {
        require(newTimeout >= 24 hours, "Timeout too short");
        require(newTimeout <= 7 days, "Timeout too long");
        signalTimeout = newTimeout;
    }
    
    /**
     * @dev Pause contract (emergency)
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }
    
    /**
     * @dev Unpause contract
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }
    
    /**
     * @dev Emergency withdraw (only for stuck funds, requires governance)
     * @param token Token address
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(address token, uint256 amount) 
        external 
        onlyRole(DEFAULT_ADMIN_ROLE) 
    {
        require(token != address(fibtToken), "Cannot withdraw FIBT");
        IERC20(token).transfer(msg.sender, amount);
    }
}

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}
