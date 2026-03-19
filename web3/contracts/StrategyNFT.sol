// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title StrategyNFT
 * @dev NFT representing ownership of trading strategies
 * Each NFT has a tier (Basic, Premium, Elite) and associated metadata
 */
contract StrategyNFT is ERC721, ERC721URIStorage, ERC721Enumerable, AccessControl {
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    
    uint256 private _tokenIdCounter;
    
    // Tier enum
    enum Tier { Basic, Premium, Elite }
    
    // NFT metadata
    struct NFTMetadata {
        Tier tier;
        uint256 strategyId;
        uint256 mintedAt;
        address originalCreator;
    }
    
    // Token ID => Metadata
    mapping(uint256 => NFTMetadata) public nftMetadata;
    
    // Strategy ID => Token IDs
    mapping(uint256 => uint256[]) public strategyTokens;
    
    event NFTMinted(
        uint256 indexed tokenId,
        address indexed to,
        Tier tier,
        uint256 strategyId
    );
    
    constructor() ERC721("Fibtool Strategy NFT", "FSTRAT") {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(MINTER_ROLE, msg.sender);
    }
    
    /**
     * @dev Mint new strategy NFT
     */
    function mintStrategyNFT(
        address to,
        Tier tier,
        uint256 strategyId,
        string memory tokenURI_
    ) external onlyRole(MINTER_ROLE) returns (uint256) {
        uint256 tokenId = _tokenIdCounter++;
        
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenURI_);
        
        nftMetadata[tokenId] = NFTMetadata({
            tier: tier,
            strategyId: strategyId,
            mintedAt: block.timestamp,
            originalCreator: to
        });
        
        strategyTokens[strategyId].push(tokenId);
        
        emit NFTMinted(tokenId, to, tier, strategyId);
        
        return tokenId;
    }
    
    /**
     * @dev Get all token IDs for a strategy
     */
    function getStrategyTokens(uint256 strategyId) external view returns (uint256[] memory) {
        return strategyTokens[strategyId];
    }
    
    /**
     * @dev Get tokens owned by an address
     */
    function tokensOfOwner(address owner) external view returns (uint256[] memory) {
        uint256 balance = balanceOf(owner);
        uint256[] memory tokens = new uint256[](balance);
        
        for (uint256 i = 0; i < balance; i++) {
            tokens[i] = tokenOfOwnerByIndex(owner, i);
        }
        
        return tokens;
    }
    
    /**
     * @dev Get NFT metadata
     */
    function getMetadata(uint256 tokenId) external view returns (NFTMetadata memory) {
        require(ownerOf(tokenId) != address(0), "Token does not exist");
        return nftMetadata[tokenId];
    }
    
    // Required overrides
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }
    
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721Enumerable, ERC721URIStorage, AccessControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
    
    function _update(address to, uint256 tokenId, address auth)
        internal
        override(ERC721, ERC721Enumerable)
        returns (address)
    {
        return super._update(to, tokenId, auth);
    }
    
    function _increaseBalance(address account, uint128 value)
        internal
        override(ERC721, ERC721Enumerable)
    {
        super._increaseBalance(account, value);
    }
}
