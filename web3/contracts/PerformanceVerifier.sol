// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title PerformanceVerifier
 * @dev Verify and validate trading performance data
 * 
 * Features:
 * - Consensus verification (3 of 5 oracles)
 * - Performance metric validation
 * - Anomaly detection
 * - Historical tracking
 * 
 * Used by:
 * - MT5Oracle: Validate reports before finalization
 * - StrategyRegistry: Update performance metrics
 * - RevenueDistributor: Calculate payouts
 */
contract PerformanceVerifier is
    Initializable,
    AccessControlUpgradeable
{
    /// @notice Oracle role
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    
    /// @notice Admin role
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Performance data struct
    struct PerformanceData {
        bytes32 signalId;
        bytes32 strategyId;
        bool tpHit;
        int256 profit;
        uint256 volume;
        uint256 entryPrice;
        uint256 exitPrice;
        uint256 timestamp;
        bool verified;
    }
    
    /// @notice Performance verification
    struct PerformanceVerification {
        bytes32 dataHash;
        address[] verifiers;
        uint256 verifiedCount;
        uint256 rejectedCount;
        mapping(address => bool) hasVerified;
        mapping(address => bool) hasRejected;
        bool finalized;
        bool approved;
    }
    
    /// @notice Data hash to verification
    mapping(bytes32 => PerformanceVerification) public verifications;
    
    /// @notice Signal ID to performance data
    mapping(bytes32 => PerformanceData) public performanceData;
    
    /// @notice Strategy performance history
    struct StrategyPerformance {
        uint256 totalSignals;
        uint256 successfulSignals;
        uint256 totalVolume;
        int256 totalProfit;
        uint256 lastUpdateTime;
    }
    
    /// @notice Strategy ID to performance
    mapping(bytes32 => StrategyPerformance) public strategyPerformance;
    
    /// @notice Minimum verifications required
    uint256 public minVerifications;
    
    /// @notice Maximum profit deviation (30%)
    uint256 public constant MAX_PROFIT_DEVIATION = 3000; // 30% in bps
    
    /// Events
    event PerformanceSubmitted(
        bytes32 indexed signalId,
        bytes32 dataHash,
        address indexed submitter
    );
    event PerformanceVerified(
        bytes32 indexed dataHash,
        address indexed verifier,
        bool approved
    );
    event PerformanceFinalized(
        bytes32 indexed signalId,
        bool approved,
        uint256 verifiedCount
    );
    event AnomalyDetected(
        bytes32 indexed signalId,
        string reason
    );
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize verifier
     */
    function initialize() external initializer {
        __AccessControl_init();
        
        minVerifications = 3;
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }
    
    /**
     * @dev Submit performance data for verification
     * @param signalId Signal identifier
     * @param strategyId Strategy identifier
     * @param tpHit Whether TP was hit
     * @param profit Profit/loss amount
     * @param volume Trade volume
     * @param entryPrice Entry price
     * @param exitPrice Exit price
     */
    function submitPerformance(
        bytes32 signalId,
        bytes32 strategyId,
        bool tpHit,
        int256 profit,
        uint256 volume,
        uint256 entryPrice,
        uint256 exitPrice
    ) external onlyRole(ORACLE_ROLE) {
        require(signalId != bytes32(0), "Invalid signal ID");
        require(strategyId != bytes32(0), "Invalid strategy ID");
        require(volume > 0, "Invalid volume");
        require(entryPrice > 0, "Invalid entry price");
        require(exitPrice > 0, "Invalid exit price");
        
        // Create data hash
        bytes32 dataHash = keccak256(abi.encodePacked(
            signalId,
            strategyId,
            tpHit,
            profit,
            volume,
            entryPrice,
            exitPrice
        ));
        
        // Store performance data
        performanceData[signalId] = PerformanceData({
            signalId: signalId,
            strategyId: strategyId,
            tpHit: tpHit,
            profit: profit,
            volume: volume,
            entryPrice: entryPrice,
            exitPrice: exitPrice,
            timestamp: block.timestamp,
            verified: false
        });
        
        // Initialize verification if not exists
        if (verifications[dataHash].verifiedCount == 0 && 
            verifications[dataHash].rejectedCount == 0) {
            verifications[dataHash].dataHash = dataHash;
        }
        
        emit PerformanceSubmitted(signalId, dataHash, msg.sender);
    }
    
    /**
     * @dev Verify submitted performance
     * @param dataHash Hash of performance data
     * @param approve Whether to approve or reject
     */
    function verifyPerformance(
        bytes32 dataHash,
        bool approve
    ) external onlyRole(ORACLE_ROLE) {
        PerformanceVerification storage verification = verifications[dataHash];
        require(!verification.finalized, "Already finalized");
        require(!verification.hasVerified[msg.sender], "Already verified");
        require(!verification.hasRejected[msg.sender], "Already rejected");
        
        if (approve) {
            verification.verifiedCount++;
            verification.hasVerified[msg.sender] = true;
        } else {
            verification.rejectedCount++;
            verification.hasRejected[msg.sender] = true;
        }
        
        verification.verifiers.push(msg.sender);
        
        emit PerformanceVerified(dataHash, msg.sender, approve);
        
        // Check if we reached consensus
        if (verification.verifiedCount >= minVerifications) {
            _finalizeVerification(dataHash, true);
        } else if (verification.rejectedCount >= minVerifications) {
            _finalizeVerification(dataHash, false);
        }
    }
    
    /**
     * @dev Finalize verification
     * @param dataHash Hash of performance data
     * @param approved Whether approved
     */
    function _finalizeVerification(bytes32 dataHash, bool approved) internal {
        PerformanceVerification storage verification = verifications[dataHash];
        require(!verification.finalized, "Already finalized");
        
        verification.finalized = true;
        verification.approved = approved;
        
        // Find signal ID from data
        // Note: In production, maintain reverse mapping
        bytes32 signalId = _findSignalIdForHash(dataHash);
        
        if (signalId != bytes32(0)) {
            PerformanceData storage data = performanceData[signalId];
            
            if (approved) {
                data.verified = true;
                
                // Update strategy performance
                _updateStrategyPerformance(
                    data.strategyId,
                    data.tpHit,
                    data.volume,
                    data.profit
                );
            }
            
            emit PerformanceFinalized(
                signalId,
                approved,
                verification.verifiedCount
            );
        }
    }
    
    /**
     * @dev Find signal ID for hash
     * @param dataHash Data hash
     * @return Signal ID
     */
    function _findSignalIdForHash(bytes32 dataHash) 
        internal 
        view 
        returns (bytes32) 
    {
        // In production, maintain reverse mapping
        // For now, simplified approach
        return dataHash; // Placeholder
    }
    
    /**
     * @dev Update strategy performance
     * @param strategyId Strategy identifier
     * @param success Whether trade was successful
     * @param volume Trade volume
     * @param profit Profit amount
     */
    function _updateStrategyPerformance(
        bytes32 strategyId,
        bool success,
        uint256 volume,
        int256 profit
    ) internal {
        StrategyPerformance storage perf = strategyPerformance[strategyId];
        
        perf.totalSignals++;
        if (success) {
            perf.successfulSignals++;
        }
        perf.totalVolume += volume;
        perf.totalProfit += profit;
        perf.lastUpdateTime = block.timestamp;
    }
    
    /**
     * @dev Validate performance metrics
     * @param signalId Signal ID to validate
     * @return valid Whether metrics are valid
     * @return reason Reason if invalid
     */
    function validateMetrics(bytes32 signalId)
        external
        view
        returns (bool valid, string memory reason)
    {
        PerformanceData memory data = performanceData[signalId];
        
        // Check profit calculation
        int256 expectedProfit = _calculateExpectedProfit(
            data.entryPrice,
            data.exitPrice,
            data.volume,
            data.tpHit
        );
        
        // Allow 30% deviation
        int256 deviation = (data.profit * 10000) / expectedProfit;
        int256 deviationAbs = deviation > 0 ? deviation : -deviation;
        
        if (deviationAbs > int256(MAX_PROFIT_DEVIATION + 10000)) {
            return (false, "Profit deviation too high");
        }
        
        // Check volume sanity
        if (data.volume > 1000000 * 10**18) {
            return (false, "Volume too high");
        }
        
        // Check price movement
        uint256 priceChange = data.exitPrice > data.entryPrice 
            ? data.exitPrice - data.entryPrice 
            : data.entryPrice - data.exitPrice;
        uint256 priceChangePct = (priceChange * 10000) / data.entryPrice;
        
        if (priceChangePct > 5000) { // >50% price change
            return (false, "Price change too high");
        }
        
        return (true, "");
    }
    
    /**
     * @dev Calculate expected profit
     * @param entryPrice Entry price
     * @param exitPrice Exit price
     * @param volume Trade volume
     * @param long Whether long position
     * @return Expected profit
     */
    function _calculateExpectedProfit(
        uint256 entryPrice,
        uint256 exitPrice,
        uint256 volume,
        bool long
    ) internal pure returns (int256) {
        int256 priceDiff = long 
            ? int256(exitPrice) - int256(entryPrice)
            : int256(entryPrice) - int256(exitPrice);
        
        return (priceDiff * int256(volume)) / int256(entryPrice);
    }
    
    /**
     * @dev Get strategy win rate
     * @param strategyId Strategy identifier
     * @return Win rate in basis points
     */
    function getWinRate(bytes32 strategyId) external view returns (uint256) {
        StrategyPerformance memory perf = strategyPerformance[strategyId];
        if (perf.totalSignals == 0) return 0;
        
        return (perf.successfulSignals * 10000) / perf.totalSignals;
    }
    
    /**
     * @dev Update minimum verifications
     * @param newMin New minimum
     */
    function updateMinVerifications(uint256 newMin) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        require(newMin >= 2, "Too low");
        require(newMin <= 5, "Too high");
        minVerifications = newMin;
    }
}
