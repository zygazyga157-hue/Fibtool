// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@chainlink/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title PriceOracle
 * @dev Chainlink price feed integration for forex/crypto/commodities
 * 
 * Features:
 * - Multiple price feeds (EURUSD, GBPUSD, XAUUSD, BTCUSD, etc.)
 * - Staleness checks
 * - Fallback mechanism
 * - Heartbeat monitoring
 * 
 * Used by:
 * - SignalEscrow: Verify trade prices
 * - StrategyRegistry: Calculate performance
 * - MT5Oracle: Validate off-chain results
 */
contract PriceOracle is
    Initializable,
    AccessControlUpgradeable
{
    /// @notice Admin role
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Price feed struct
    struct PriceFeed {
        address feedAddress;
        uint256 heartbeat;  // Max time between updates
        uint8 decimals;
        bool active;
    }
    
    /// @notice Symbol to price feed
    mapping(string => PriceFeed) public priceFeeds;
    
    /// @notice Supported symbols
    string[] public symbols;
    
    /// @notice Maximum staleness (15 minutes)
    uint256 public constant MAX_STALENESS = 15 minutes;
    
    /// Events
    event PriceFeedAdded(string indexed symbol, address feedAddress);
    event PriceFeedUpdated(string indexed symbol, address feedAddress);
    event PriceFeedRemoved(string indexed symbol);
    event PriceQueried(string indexed symbol, int256 price, uint256 timestamp);
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize oracle
     */
    function initialize() external initializer {
        __AccessControl_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        
        // Note: Add default feeds in production
        // addPriceFeed("EURUSD", 0x..., 86400);
        // addPriceFeed("GBPUSD", 0x..., 86400);
        // etc.
    }
    
    /**
     * @dev Add price feed
     * @param symbol Trading symbol (e.g., "EURUSD")
     * @param feedAddress Chainlink aggregator address
     * @param heartbeat Expected update frequency (seconds)
     */
    function addPriceFeed(
        string memory symbol,
        address feedAddress,
        uint256 heartbeat
    ) public onlyRole(ADMIN_ROLE) {
        require(feedAddress != address(0), "Invalid feed address");
        require(heartbeat > 0, "Invalid heartbeat");
        require(!priceFeeds[symbol].active, "Feed already exists");
        
        // Verify feed is working
        AggregatorV3Interface feed = AggregatorV3Interface(feedAddress);
        uint8 decimals = feed.decimals();
        
        priceFeeds[symbol] = PriceFeed({
            feedAddress: feedAddress,
            heartbeat: heartbeat,
            decimals: decimals,
            active: true
        });
        
        symbols.push(symbol);
        
        emit PriceFeedAdded(symbol, feedAddress);
    }
    
    /**
     * @dev Update price feed
     * @param symbol Trading symbol
     * @param feedAddress New aggregator address
     * @param heartbeat New heartbeat
     */
    function updatePriceFeed(
        string memory symbol,
        address feedAddress,
        uint256 heartbeat
    ) external onlyRole(ADMIN_ROLE) {
        require(priceFeeds[symbol].active, "Feed doesn't exist");
        require(feedAddress != address(0), "Invalid feed address");
        require(heartbeat > 0, "Invalid heartbeat");
        
        // Verify feed
        AggregatorV3Interface feed = AggregatorV3Interface(feedAddress);
        uint8 decimals = feed.decimals();
        
        priceFeeds[symbol].feedAddress = feedAddress;
        priceFeeds[symbol].heartbeat = heartbeat;
        priceFeeds[symbol].decimals = decimals;
        
        emit PriceFeedUpdated(symbol, feedAddress);
    }
    
    /**
     * @dev Remove price feed
     * @param symbol Trading symbol
     */
    function removePriceFeed(string memory symbol) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        require(priceFeeds[symbol].active, "Feed doesn't exist");
        
        priceFeeds[symbol].active = false;
        
        emit PriceFeedRemoved(symbol);
    }
    
    /**
     * @dev Get latest price
     * @param symbol Trading symbol
     * @return price Latest price
     * @return timestamp Last update timestamp
     */
    function getLatestPrice(string memory symbol) 
        public 
        view 
        returns (int256 price, uint256 timestamp) 
    {
        PriceFeed memory feed = priceFeeds[symbol];
        require(feed.active, "Feed not active");
        
        AggregatorV3Interface aggregator = AggregatorV3Interface(feed.feedAddress);
        
        (
            uint80 roundId,
            int256 answer,
            ,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = aggregator.latestRoundData();
        
        require(answer > 0, "Invalid price");
        require(answeredInRound >= roundId, "Stale price");
        require(updatedAt > 0, "Invalid timestamp");
        require(
            block.timestamp - updatedAt <= MAX_STALENESS,
            "Price too stale"
        );
        
        return (answer, updatedAt);
    }
    
    /**
     * @dev Get latest price with staleness override
     * @param symbol Trading symbol
     * @param maxStaleness Maximum staleness allowed
     * @return price Latest price
     * @return timestamp Last update timestamp
     */
    function getLatestPriceWithStaleness(
        string memory symbol,
        uint256 maxStaleness
    ) 
        external 
        view 
        returns (int256 price, uint256 timestamp) 
    {
        PriceFeed memory feed = priceFeeds[symbol];
        require(feed.active, "Feed not active");
        
        AggregatorV3Interface aggregator = AggregatorV3Interface(feed.feedAddress);
        
        (
            uint80 roundId,
            int256 answer,
            ,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = aggregator.latestRoundData();
        
        require(answer > 0, "Invalid price");
        require(answeredInRound >= roundId, "Stale price");
        require(updatedAt > 0, "Invalid timestamp");
        require(
            block.timestamp - updatedAt <= maxStaleness,
            "Price too stale"
        );
        
        return (answer, updatedAt);
    }
    
    /**
     * @dev Get historical price at specific round
     * @param symbol Trading symbol
     * @param roundId Round identifier
     * @return price Price at round
     * @return timestamp Timestamp of round
     */
    function getHistoricalPrice(string memory symbol, uint80 roundId)
        external
        view
        returns (int256 price, uint256 timestamp)
    {
        PriceFeed memory feed = priceFeeds[symbol];
        require(feed.active, "Feed not active");
        
        AggregatorV3Interface aggregator = AggregatorV3Interface(feed.feedAddress);
        
        (
            ,
            int256 answer,
            ,
            uint256 updatedAt,
            
        ) = aggregator.getRoundData(roundId);
        
        require(answer > 0, "Invalid price");
        require(updatedAt > 0, "Invalid timestamp");
        
        return (answer, updatedAt);
    }
    
    /**
     * @dev Get price with USD conversion
     * @param symbol Trading symbol
     * @return price Price in USD (18 decimals)
     */
    function getPriceInUSD(string memory symbol) 
        external 
        view 
        returns (uint256 price) 
    {
        (int256 rawPrice, ) = getLatestPrice(symbol);
        require(rawPrice > 0, "Invalid price");
        
        PriceFeed memory feed = priceFeeds[symbol];
        
        // Convert to 18 decimals
        if (feed.decimals < 18) {
            return uint256(rawPrice) * (10 ** (18 - feed.decimals));
        } else {
            return uint256(rawPrice) / (10 ** (feed.decimals - 18));
        }
    }
    
    /**
     * @dev Check if price is stale
     * @param symbol Trading symbol
     * @return Whether price is stale
     */
    function isPriceStale(string memory symbol) external view returns (bool) {
        PriceFeed memory feed = priceFeeds[symbol];
        if (!feed.active) return true;
        
        AggregatorV3Interface aggregator = AggregatorV3Interface(feed.feedAddress);
        
        try aggregator.latestRoundData() returns (
            uint80,
            int256,
            uint256,
            uint256 updatedAt,
            uint80
        ) {
            return block.timestamp - updatedAt > feed.heartbeat;
        } catch {
            return true;
        }
    }
    
    /**
     * @dev Batch get prices
     * @param _symbols Array of symbols
     * @return prices Array of prices
     * @return timestamps Array of timestamps
     */
    function getBatchPrices(string[] memory _symbols)
        external
        view
        returns (int256[] memory prices, uint256[] memory timestamps)
    {
        prices = new int256[](_symbols.length);
        timestamps = new uint256[](_symbols.length);
        
        for (uint256 i = 0; i < _symbols.length; i++) {
            (prices[i], timestamps[i]) = getLatestPrice(_symbols[i]);
        }
    }
    
    /**
     * @dev Get all supported symbols
     * @return Array of symbols
     */
    function getSupportedSymbols() external view returns (string[] memory) {
        return symbols;
    }
    
    /**
     * @dev Get feed info
     * @param symbol Trading symbol
     * @return feedAddress Aggregator address
     * @return heartbeat Expected heartbeat
     * @return decimals Price decimals
     * @return active Whether feed is active
     */
    function getFeedInfo(string memory symbol)
        external
        view
        returns (
            address feedAddress,
            uint256 heartbeat,
            uint8 decimals,
            bool active
        )
    {
        PriceFeed memory feed = priceFeeds[symbol];
        return (
            feed.feedAddress,
            feed.heartbeat,
            feed.decimals,
            feed.active
        );
    }
}
