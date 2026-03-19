// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title FIBTToken
 * @dev ERC20 token for the Fibtool platform
 * Features: Burnable, Mintable (only owner), Transfer restrictions
 */
contract FIBTToken is ERC20, ERC20Burnable, Ownable {
    // Maximum supply: 100 million tokens
    uint256 public constant MAX_SUPPLY = 100_000_000 * 10**18;
    
    // Minting tracker
    uint256 public totalMinted;
    
    // Trading enabled flag
    bool public tradingEnabled;
    
    // Whitelist for transfers before trading enabled
    mapping(address => bool) public isWhitelisted;
    
    event TradingEnabled(uint256 timestamp);
    event WhitelistUpdated(address indexed account, bool status);
    
    constructor() ERC20("Fibtool Token", "FIBT") Ownable(msg.sender) {
        // Mint initial supply to deployer (25% of max supply)
        uint256 initialSupply = 25_000_000 * 10**18;
        _mint(msg.sender, initialSupply);
        totalMinted = initialSupply;
        
        // Whitelist deployer
        isWhitelisted[msg.sender] = true;
    }
    
    /**
     * @dev Mint new tokens (only owner, up to MAX_SUPPLY)
     */
    function mint(address to, uint256 amount) external onlyOwner {
        require(totalMinted + amount <= MAX_SUPPLY, "Exceeds max supply");
        totalMinted += amount;
        _mint(to, amount);
    }
    
    /**
     * @dev Enable trading permanently
     */
    function enableTrading() external onlyOwner {
        require(!tradingEnabled, "Trading already enabled");
        tradingEnabled = true;
        emit TradingEnabled(block.timestamp);
    }
    
    /**
     * @dev Update whitelist status
     */
    function updateWhitelist(address account, bool status) external onlyOwner {
        isWhitelisted[account] = status;
        emit WhitelistUpdated(account, status);
    }
    
    /**
     * @dev Batch update whitelist
     */
    function batchUpdateWhitelist(address[] calldata accounts, bool status) external onlyOwner {
        for (uint256 i = 0; i < accounts.length; i++) {
            isWhitelisted[accounts[i]] = status;
            emit WhitelistUpdated(accounts[i], status);
        }
    }
    
    /**
     * @dev Override transfer to enforce trading restrictions
     */
    function _update(
        address from,
        address to,
        uint256 value
    ) internal virtual override {
        // Allow minting and burning
        if (from == address(0) || to == address(0)) {
            super._update(from, to, value);
            return;
        }
        
        // If trading not enabled, only whitelisted addresses can transfer
        if (!tradingEnabled) {
            require(
                isWhitelisted[from] || isWhitelisted[to],
                "Trading not enabled"
            );
        }
        
        super._update(from, to, value);
    }
}
