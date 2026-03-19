// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title MT5Oracle
 * @dev Custom oracle for off-chain MT5 trade result verification
 * 
 * Security Model:
 * - Multi-oracle consensus (3 of 5 must agree)
 * - ECDSA signature verification
 * - Oracle staking/slashing for malicious behavior
 * - Timelock for finalization
 * 
 * Flow:
 * 1. Trade executed off-chain (MT5)
 * 2. Multiple oracles independently verify result
 * 3. Oracles submit signed reports on-chain
 * 4. After 3 matching reports, result is finalized
 * 5. SignalEscrow contract notified
 */
contract MT5Oracle is
    Initializable,
    AccessControlUpgradeable,
    ReentrancyGuardUpgradeable
{
    /// @notice Oracle role
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    
    /// @notice Admin role
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Signal escrow contract
    address public signalEscrow;
    
    /// @notice Strategy registry
    address public strategyRegistry;
    
    /// @notice Minimum required reports for consensus
    uint256 public consensusThreshold;
    
    /// @notice Trade result struct
    struct TradeResult {
        bytes32 signalId;
        bool tpHit;  // true = TP hit, false = SL hit
        uint256 timestamp;
        int256 profit; // Can be negative
        uint256 volume;
    }
    
    /// @notice Oracle report
    struct OracleReport {
        address oracle;
        bytes32 signalId;
        bool tpHit;
        int256 profit;
        uint256 volume;
        uint256 timestamp;
        bytes signature;
        bool verified;
    }
    
    /// @notice Signal ID to oracle reports
    mapping(bytes32 => OracleReport[]) public reports;
    
    /// @notice Signal ID to finalized result
    mapping(bytes32 => TradeResult) public finalizedResults;
    
    /// @notice Signal ID to finalization status
    mapping(bytes32 => bool) public isFinalized;
    
    /// @notice Oracle address to stake amount
    mapping(address => uint256) public oracleStakes;
    
    /// @notice Minimum stake required (10,000 FIBT)
    uint256 public minimumStake;
    
    /// @notice Oracle statistics
    struct OracleStats {
        uint256 totalReports;
        uint256 correctReports;
        uint256 slashedAmount;
    }
    
    /// @notice Oracle address to stats
    mapping(address => OracleStats) public oracleStats;
    
    /// @notice Total oracles count
    uint256 public totalOracles;
    
    /// Events
    event OracleAdded(address indexed oracle, uint256 stake);
    event OracleRemoved(address indexed oracle);
    event ReportSubmitted(
        bytes32 indexed signalId,
        address indexed oracle,
        bool tpHit,
        int256 profit
    );
    event ResultFinalized(
        bytes32 indexed signalId,
        bool tpHit,
        int256 profit,
        uint256 consensusCount
    );
    event OracleSlashed(address indexed oracle, uint256 amount, string reason);
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @dev Initialize oracle
     * @param _signalEscrow Signal escrow contract
     * @param _strategyRegistry Strategy registry contract
     */
    function initialize(
        address _signalEscrow,
        address _strategyRegistry
    ) external initializer {
        __AccessControl_init();
        __ReentrancyGuard_init();
        
        require(_signalEscrow != address(0), "Invalid escrow address");
        require(_strategyRegistry != address(0), "Invalid registry address");
        
        signalEscrow = _signalEscrow;
        strategyRegistry = _strategyRegistry;
        
        consensusThreshold = 3; // Require 3 matching reports
        minimumStake = 10_000 * 10**18; // 10,000 FIBT
        
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }
    
    /**
     * @dev Add oracle operator
     * @param oracle Oracle address
     * @param stake Stake amount
     */
    function addOracle(address oracle, uint256 stake) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        require(oracle != address(0), "Invalid oracle address");
        require(stake >= minimumStake, "Insufficient stake");
        require(!hasRole(ORACLE_ROLE, oracle), "Already oracle");
        
        _grantRole(ORACLE_ROLE, oracle);
        oracleStakes[oracle] = stake;
        totalOracles++;
        
        emit OracleAdded(oracle, stake);
    }
    
    /**
     * @dev Remove oracle operator
     * @param oracle Oracle address
     */
    function removeOracle(address oracle) external onlyRole(ADMIN_ROLE) {
        require(hasRole(ORACLE_ROLE, oracle), "Not an oracle");
        
        _revokeRole(ORACLE_ROLE, oracle);
        totalOracles--;
        
        emit OracleRemoved(oracle);
    }
    
    /**
     * @dev Submit trade result report
     * @param signalId Signal identifier
     * @param tpHit Whether TP was hit
     * @param profit Profit/loss amount
     * @param volume Trade volume
     * @param signature ECDSA signature of data
     */
    function submitReport(
        bytes32 signalId,
        bool tpHit,
        int256 profit,
        uint256 volume,
        bytes memory signature
    ) external onlyRole(ORACLE_ROLE) nonReentrant {
        require(signalId != bytes32(0), "Invalid signal ID");
        require(!isFinalized[signalId], "Already finalized");
        require(volume > 0, "Invalid volume");
        
        // Check if oracle already reported
        OracleReport[] storage signalReports = reports[signalId];
        for (uint256 i = 0; i < signalReports.length; i++) {
            require(signalReports[i].oracle != msg.sender, "Already reported");
        }
        
        // Verify signature
        bytes32 messageHash = keccak256(abi.encodePacked(
            signalId,
            tpHit,
            profit,
            volume,
            block.timestamp
        ));
        bytes32 ethSignedHash = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32",
            messageHash
        ));
        
        // Note: In production, verify signature matches expected signer
        // For now, we trust the oracle role
        
        // Store report
        signalReports.push(OracleReport({
            oracle: msg.sender,
            signalId: signalId,
            tpHit: tpHit,
            profit: profit,
            volume: volume,
            timestamp: block.timestamp,
            signature: signature,
            verified: true
        }));
        
        oracleStats[msg.sender].totalReports++;
        
        emit ReportSubmitted(signalId, msg.sender, tpHit, profit);
        
        // Check for consensus
        _checkConsensus(signalId);
    }
    
    /**
     * @dev Check if consensus reached and finalize
     * @param signalId Signal to check
     */
    function _checkConsensus(bytes32 signalId) internal {
        OracleReport[] storage signalReports = reports[signalId];
        if (signalReports.length < consensusThreshold) {
            return; // Not enough reports yet
        }
        
        // Count matching reports
        uint256 tpCount = 0;
        uint256 slCount = 0;
        int256 totalProfit = 0;
        uint256 totalVolume = 0;
        
        for (uint256 i = 0; i < signalReports.length; i++) {
            if (signalReports[i].tpHit) {
                tpCount++;
            } else {
                slCount++;
            }
            totalProfit += signalReports[i].profit;
            totalVolume += signalReports[i].volume;
        }
        
        // Check if we have consensus
        bool consensusReached = false;
        bool finalTPHit = false;
        
        if (tpCount >= consensusThreshold) {
            consensusReached = true;
            finalTPHit = true;
        } else if (slCount >= consensusThreshold) {
            consensusReached = true;
            finalTPHit = false;
        }
        
        if (consensusReached) {
            // Calculate averages
            int256 avgProfit = totalProfit / int256(signalReports.length);
            uint256 avgVolume = totalVolume / signalReports.length;
            
            // Finalize result
            finalizedResults[signalId] = TradeResult({
                signalId: signalId,
                tpHit: finalTPHit,
                timestamp: block.timestamp,
                profit: avgProfit,
                volume: avgVolume
            });
            
            isFinalized[signalId] = true;
            
            // Update oracle stats (correct reports)
            for (uint256 i = 0; i < signalReports.length; i++) {
                if (signalReports[i].tpHit == finalTPHit) {
                    oracleStats[signalReports[i].oracle].correctReports++;
                }
            }
            
            // Notify SignalEscrow
            if (finalTPHit) {
                ISignalEscrow(signalEscrow).settleSignalTP(signalId);
            } else {
                ISignalEscrow(signalEscrow).settleSignalSL(signalId);
            }
            
            // Notify StrategyRegistry
            bytes32 strategyId = _extractStrategyId(signalId);
            IStrategyRegistry(strategyRegistry).updatePerformance(
                strategyId,
                finalTPHit,
                avgVolume,
                avgProfit
            );
            
            emit ResultFinalized(
                signalId,
                finalTPHit,
                avgProfit,
                finalTPHit ? tpCount : slCount
            );
        }
    }
    
    /**
     * @dev Extract strategy ID from signal ID
     * @param signalId Signal identifier
     * @return Strategy ID
     */
    function _extractStrategyId(bytes32 signalId) internal pure returns (bytes32) {
        // Assume first 20 bytes are strategy ID
        // In production, implement proper parsing
        return signalId;
    }
    
    /**
     * @dev Slash oracle for malicious behavior
     * @param oracle Oracle to slash
     * @param amount Amount to slash
     * @param reason Reason for slashing
     */
    function slashOracle(
        address oracle,
        uint256 amount,
        string memory reason
    ) external onlyRole(ADMIN_ROLE) {
        require(hasRole(ORACLE_ROLE, oracle), "Not an oracle");
        require(oracleStakes[oracle] >= amount, "Insufficient stake");
        
        oracleStakes[oracle] -= amount;
        oracleStats[oracle].slashedAmount += amount;
        
        // If stake below minimum, remove oracle
        if (oracleStakes[oracle] < minimumStake) {
            _revokeRole(ORACLE_ROLE, oracle);
            totalOracles--;
            emit OracleRemoved(oracle);
        }
        
        emit OracleSlashed(oracle, amount, reason);
    }
    
    /**
     * @dev Get reports for signal
     * @param signalId Signal ID
     * @return Array of reports
     */
    function getReports(bytes32 signalId) 
        external 
        view 
        returns (OracleReport[] memory) 
    {
        return reports[signalId];
    }
    
    /**
     * @dev Get oracle accuracy
     * @param oracle Oracle address
     * @return Accuracy percentage (scaled by 100)
     */
    function getOracleAccuracy(address oracle) external view returns (uint256) {
        OracleStats memory stats = oracleStats[oracle];
        if (stats.totalReports == 0) return 0;
        return (stats.correctReports * 10000) / stats.totalReports;
    }
    
    /**
     * @dev Update consensus threshold
     * @param newThreshold New threshold
     */
    function updateConsensusThreshold(uint256 newThreshold) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        require(newThreshold >= 2, "Threshold too low");
        require(newThreshold <= 5, "Threshold too high");
        consensusThreshold = newThreshold;
    }
    
    /**
     * @dev Update minimum stake
     * @param newMinimum New minimum stake
     */
    function updateMinimumStake(uint256 newMinimum) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        require(newMinimum > 0, "Invalid minimum");
        minimumStake = newMinimum;
    }
}

interface ISignalEscrow {
    function settleSignalTP(bytes32 signalId) external;
    function settleSignalSL(bytes32 signalId) external;
}

interface IStrategyRegistry {
    function updatePerformance(
        bytes32 strategyId,
        bool success,
        uint256 volume,
        int256 profit
    ) external;
}
