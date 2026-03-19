// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title StrategyRegistry
 * @dev Central registry for trading strategies with performance tracking
 * 
 * Features:
 * - Strategy listing/delisting
 * - Performance metrics (on-chain)
 * - Creator verification
 * - Strategy categories/tags
 * - Rating system
 */
contract StrategyRegistry is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable
{
    /// @notice Strategy NFT contract
    address public strategyNFT;
    
    /// @notice Oracle contract
    address public mt5Oracle;
    
    /// @notice Verifier role
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    
    /// @notice Oracle role
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    
    /// @notice Strategy status
    enum StrategyStatus { PENDING, ACTIVE, PAUSED, DELISTED }
    
    /// @notice Strategy category
    enum StrategyCategory { 
        FIBONACCI, 
        GANN, 
        HARMONIC, 
        INDICATOR_BASED, 
        PRICE_ACTION,
        HYBRID 
    }
    
    /// @notice Strategy metadata
    struct Strategy {
        bytes32 strategyId;
        uint256 nftTokenId;
        address creator;
        string name;
        string description;
        StrategyCategory category;
        StrategyStatus status;
        uint256 listedAt;
        uint256 totalSignals;
        uint256 successfulSignals;
        uint256 totalVolume;
        uint256 totalProfit;
        uint256 averageWinRate; // In basis points (7500 = 75%)
        uint256 sharpeRatio; // Scaled by 100 (150 = 1.50)
        uint256 maxDrawdown; // In basis points
    }
    
    /// @notice Strategy rating
    struct Rating {
        uint256 totalRatings;
        uint256 sumRatings; // Sum of all ratings (1-5 stars)
        mapping(address => uint256) userRatings; // User => rating
    }
    
    /// @notice Strategy ID to strategy data
    mapping(bytes32 => Strategy) public strategies;
    
    /// @notice Strategy ID to rating data
    mapping(bytes32 => Rating) private ratings;
    
    /// @notice Creator to strategy IDs
    mapping(address => bytes32[]) public creatorStrategies;
    
    /// @notice NFT token ID to strategy ID
    mapping(uint256 => bytes32) public nftToStrategy;
    
    /// @notice Active strategies list
    bytes32[] public activeStrategies;
    
    /// @notice Total strategies count
    uint256 public totalStrategies;
    
    /// Events
    event StrategyListed(
        bytes32 indexed strategyId,
        address indexed creator,
        uint256 nftTokenId,
        string name
    );
    
    event StrategyUpdated(
        bytes32 indexed strategyId,
        StrategyStatus status
    );
    
    event StrategyDelisted(
        bytes32 indexed strategyId,
        uint256 timestamp
    );
    
    event PerformanceUpdated(
        bytes32 indexed strategyId,
        uint256 totalSignals,
        uint256 successfulSignals,
        uint256 winRate
    );
    
    event StrategyRated(
        bytes32 indexed strategyId,
        address indexed rater,
        uint256 rating
    );
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize contract
     * @param _strategyNFT Strategy NFT contract address
     * @param _mt5Oracle Oracle contract address
     */
    function initialize(
        address _strategyNFT,
        address _mt5Oracle
    ) external initializer {
        __AccessControl_init();
        __Pausable_init();
        
        require(_strategyNFT != address(0), "Invalid NFT address");
        require(_mt5Oracle != address(0), "Invalid oracle address");
        
        strategyNFT = _strategyNFT;
        mt5Oracle = _mt5Oracle;
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }
    
    /**
     * @dev List a new strategy
     * @param strategyId Unique strategy identifier
     * @param nftTokenId NFT token ID representing ownership
     * @param name Strategy name
     * @param description Strategy description
     * @param category Strategy category
     * @return Success boolean
     */
    function listStrategy(
        bytes32 strategyId,
        uint256 nftTokenId,
        string memory name,
        string memory description,
        StrategyCategory category
    ) external whenNotPaused returns (bool) {
        require(strategyId != bytes32(0), "Invalid strategy ID");
        require(strategies[strategyId].creator == address(0), "Strategy already listed");
        require(bytes(name).length > 0, "Name required");
        
        // Verify NFT ownership
        require(
            IStrategyNFT(strategyNFT).ownerOf(nftTokenId) == msg.sender,
            "Not NFT owner"
        );
        require(nftToStrategy[nftTokenId] == bytes32(0), "NFT already used");
        
        // Create strategy
        strategies[strategyId] = Strategy({
            strategyId: strategyId,
            nftTokenId: nftTokenId,
            creator: msg.sender,
            name: name,
            description: description,
            category: category,
            status: StrategyStatus.PENDING,
            listedAt: block.timestamp,
            totalSignals: 0,
            successfulSignals: 0,
            totalVolume: 0,
            totalProfit: 0,
            averageWinRate: 0,
            sharpeRatio: 0,
            maxDrawdown: 0
        });
        
        // Link NFT to strategy
        nftToStrategy[nftTokenId] = strategyId;
        
        // Add to creator's list
        creatorStrategies[msg.sender].push(strategyId);
        
        totalStrategies++;
        
        emit StrategyListed(strategyId, msg.sender, nftTokenId, name);
        
        return true;
    }
    
    /**
     * @dev Activate strategy (after verification)
     * @param strategyId Strategy to activate
     */
    function activateStrategy(bytes32 strategyId) 
        external 
        onlyRole(VERIFIER_ROLE) 
    {
        Strategy storage strategy = strategies[strategyId];
        require(strategy.creator != address(0), "Strategy not found");
        require(strategy.status == StrategyStatus.PENDING, "Not pending");
        
        strategy.status = StrategyStatus.ACTIVE;
        activeStrategies.push(strategyId);
        
        emit StrategyUpdated(strategyId, StrategyStatus.ACTIVE);
    }
    
    /**
     * @dev Pause strategy
     * @param strategyId Strategy to pause
     */
    function pauseStrategy(bytes32 strategyId) external {
        Strategy storage strategy = strategies[strategyId];
        require(
            strategy.creator == msg.sender || hasRole(VERIFIER_ROLE, msg.sender),
            "Not authorized"
        );
        require(strategy.status == StrategyStatus.ACTIVE, "Not active");
        
        strategy.status = StrategyStatus.PAUSED;
        
        emit StrategyUpdated(strategyId, StrategyStatus.PAUSED);
    }
    
    /**
     * @dev Unpause strategy
     * @param strategyId Strategy to unpause
     */
    function unpauseStrategy(bytes32 strategyId) external {
        Strategy storage strategy = strategies[strategyId];
        require(strategy.creator == msg.sender, "Not creator");
        require(strategy.status == StrategyStatus.PAUSED, "Not paused");
        
        strategy.status = StrategyStatus.ACTIVE;
        
        emit StrategyUpdated(strategyId, StrategyStatus.ACTIVE);
    }
    
    /**
     * @dev Delist strategy (governance only)
     * @param strategyId Strategy to delist
     */
    function delistStrategy(bytes32 strategyId) 
        external 
        onlyRole(DEFAULT_ADMIN_ROLE) 
    {
        Strategy storage strategy = strategies[strategyId];
        require(strategy.creator != address(0), "Strategy not found");
        
        strategy.status = StrategyStatus.DELISTED;
        
        emit StrategyDelisted(strategyId, block.timestamp);
    }
    
    /**
     * @dev Update strategy performance (called by oracle)
     * @param strategyId Strategy to update
     * @param signalSuccess Whether signal was successful
     * @param volume Volume of the signal
     * @param profit Profit from the signal (can be negative)
     */
    function updatePerformance(
        bytes32 strategyId,
        bool signalSuccess,
        uint256 volume,
        int256 profit
    ) external onlyRole(ORACLE_ROLE) {
        Strategy storage strategy = strategies[strategyId];
        require(strategy.creator != address(0), "Strategy not found");
        
        strategy.totalSignals++;
        strategy.totalVolume += volume;
        
        if (signalSuccess) {
            strategy.successfulSignals++;
        }
        
        // Update profit (handle negative profits)
        if (profit >= 0) {
            strategy.totalProfit += uint256(profit);
        } else {
            uint256 loss = uint256(-profit);
            if (loss > strategy.totalProfit) {
                strategy.totalProfit = 0;
            } else {
                strategy.totalProfit -= loss;
            }
        }
        
        // Calculate win rate
        strategy.averageWinRate = (strategy.successfulSignals * 10000) / strategy.totalSignals;
        
        // Update NFT performance score
        IStrategyNFT(strategyNFT).updatePerformanceScore(
            strategy.nftTokenId, 
            strategy.averageWinRate
        );
        
        emit PerformanceUpdated(
            strategyId,
            strategy.totalSignals,
            strategy.successfulSignals,
            strategy.averageWinRate
        );
    }
    
    /**
     * @dev Update advanced metrics (Sharpe ratio, max drawdown)
     * @param strategyId Strategy to update
     * @param sharpeRatio Sharpe ratio (scaled by 100)
     * @param maxDrawdown Max drawdown (in basis points)
     */
    function updateAdvancedMetrics(
        bytes32 strategyId,
        uint256 sharpeRatio,
        uint256 maxDrawdown
    ) external onlyRole(ORACLE_ROLE) {
        Strategy storage strategy = strategies[strategyId];
        require(strategy.creator != address(0), "Strategy not found");
        
        strategy.sharpeRatio = sharpeRatio;
        strategy.maxDrawdown = maxDrawdown;
    }
    
    /**
     * @dev Rate a strategy (1-5 stars)
     * @param strategyId Strategy to rate
     * @param rating Rating value (1-5)
     */
    function rateStrategy(bytes32 strategyId, uint256 rating) external {
        require(rating >= 1 && rating <= 5, "Rating must be 1-5");
        Strategy storage strategy = strategies[strategyId];
        require(strategy.creator != address(0), "Strategy not found");
        require(strategy.status == StrategyStatus.ACTIVE, "Not active");
        
        Rating storage ratingData = ratings[strategyId];
        
        // If user already rated, update
        if (ratingData.userRatings[msg.sender] > 0) {
            ratingData.sumRatings = ratingData.sumRatings - ratingData.userRatings[msg.sender] + rating;
        } else {
            ratingData.totalRatings++;
            ratingData.sumRatings += rating;
        }
        
        ratingData.userRatings[msg.sender] = rating;
        
        emit StrategyRated(strategyId, msg.sender, rating);
    }
    
    /**
     * @dev Get strategy average rating
     * @param strategyId Strategy ID
     * @return Average rating (scaled by 100, e.g., 450 = 4.50 stars)
     */
    function getAverageRating(bytes32 strategyId) external view returns (uint256) {
        Rating storage ratingData = ratings[strategyId];
        if (ratingData.totalRatings == 0) return 0;
        return (ratingData.sumRatings * 100) / ratingData.totalRatings;
    }
    
    /**
     * @dev Get user's rating for strategy
     * @param strategyId Strategy ID
     * @param user User address
     * @return User's rating (0 if not rated)
     */
    function getUserRating(bytes32 strategyId, address user) 
        external 
        view 
        returns (uint256) 
    {
        return ratings[strategyId].userRatings[user];
    }
    
    /**
     * @dev Get strategy details
     * @param strategyId Strategy ID
     * @return Strategy struct
     */
    function getStrategy(bytes32 strategyId) 
        external 
        view 
        returns (Strategy memory) 
    {
        return strategies[strategyId];
    }
    
    /**
     * @dev Get all strategies by creator
     * @param creator Creator address
     * @return Array of strategy IDs
     */
    function getCreatorStrategies(address creator) 
        external 
        view 
        returns (bytes32[] memory) 
    {
        return creatorStrategies[creator];
    }
    
    /**
     * @dev Get all active strategies
     * @return Array of strategy IDs
     */
    function getActiveStrategies() external view returns (bytes32[] memory) {
        return activeStrategies;
    }
    
    /**
     * @dev Get top strategies by win rate
     * @param limit Number of strategies to return
     * @return Array of strategy IDs
     */
    function getTopStrategiesByWinRate(uint256 limit) 
        external 
        view 
        returns (bytes32[] memory) 
    {
        // Note: In production, this should use a sorted data structure
        // For now, returning first N active strategies
        require(limit > 0, "Limit must be > 0");
        
        uint256 count = limit > activeStrategies.length ? activeStrategies.length : limit;
        bytes32[] memory topStrategies = new bytes32[](count);
        
        for (uint256 i = 0; i < count; i++) {
            topStrategies[i] = activeStrategies[i];
        }
        
        return topStrategies;
    }
    
    /**
     * @dev Pause contract
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }
    
    /**
     * @dev Unpause contract
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}

interface IStrategyNFT {
    function ownerOf(uint256 tokenId) external view returns (address);
    function updatePerformanceScore(uint256 tokenId, uint256 score) external;
}
