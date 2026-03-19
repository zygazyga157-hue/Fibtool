// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract GovernanceDAO is Ownable {
    IERC20 public immutable fibtToken;
    
    enum ProposalState { Pending, Active, Succeeded, Defeated, Executed, Canceled }
    enum VoteType { Against, For, Abstain }
    
    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string description;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 abstainVotes;
        uint256 startBlock;
        uint256 endBlock;
        bool executed;
        bool canceled;
        mapping(address => bool) hasVoted;
    }
    
    uint256 public proposalCount;
    uint256 public constant VOTING_PERIOD = 50400;
    uint256 public constant QUORUM_PERCENTAGE = 10;
    mapping(uint256 => Proposal) public proposals;
    
    event ProposalCreated(uint256 indexed proposalId, address indexed proposer, string title, uint256 startBlock, uint256 endBlock);
    event VoteCast(address indexed voter, uint256 indexed proposalId, VoteType support, uint256 weight);
    event ProposalExecuted(uint256 indexed proposalId);
    event ProposalCanceled(uint256 indexed proposalId);
    
    constructor(address _fibtToken) Ownable(msg.sender) { 
        fibtToken = IERC20(_fibtToken); 
    }
    
    function propose(string memory title, string memory description) external returns (uint256) {
        require(fibtToken.balanceOf(msg.sender) >= 1000 * 10**18, "Insufficient FIBT");
        uint256 proposalId = proposalCount++;
        Proposal storage p = proposals[proposalId];
        p.id = proposalId;
        p.proposer = msg.sender;
        p.title = title;
        p.description = description;
        p.startBlock = block.number;
        p.endBlock = block.number + VOTING_PERIOD;
        emit ProposalCreated(proposalId, msg.sender, title, p.startBlock, p.endBlock);
        return proposalId;
    }
    
    function castVote(uint256 proposalId, VoteType support) external {
        Proposal storage proposal = proposals[proposalId];
        require(state(proposalId) == ProposalState.Active, "Voting not active");
        require(!proposal.hasVoted[msg.sender], "Already voted");
        uint256 weight = fibtToken.balanceOf(msg.sender);
        require(weight > 0, "No voting power");
        proposal.hasVoted[msg.sender] = true;
        if (support == VoteType.For) proposal.forVotes += weight;
        else if (support == VoteType.Against) proposal.againstVotes += weight;
        else proposal.abstainVotes += weight;
        emit VoteCast(msg.sender, proposalId, support, weight);
    }
    
    function state(uint256 proposalId) public view returns (ProposalState) {
        Proposal storage p = proposals[proposalId];
        if (p.canceled) return ProposalState.Canceled;
        if (p.executed) return ProposalState.Executed;
        if (block.number < p.startBlock) return ProposalState.Pending;
        if (block.number <= p.endBlock) return ProposalState.Active;
        uint256 totalVotes = p.forVotes + p.againstVotes + p.abstainVotes;
        uint256 quorumVotes = (fibtToken.totalSupply() * QUORUM_PERCENTAGE) / 100;
        if (totalVotes < quorumVotes) return ProposalState.Defeated;
        if (p.forVotes > p.againstVotes) return ProposalState.Succeeded;
        return ProposalState.Defeated;
    }
    
    function execute(uint256 proposalId) external {
        require(state(proposalId) == ProposalState.Succeeded, "Not succeeded");
        proposals[proposalId].executed = true;
        emit ProposalExecuted(proposalId);
    }
    
    function cancel(uint256 proposalId) external {
        Proposal storage p = proposals[proposalId];
        require(msg.sender == p.proposer || msg.sender == owner(), "Not authorized");
        require(!p.executed, "Already executed");
        p.canceled = true;
        emit ProposalCanceled(proposalId);
    }
    
    function getProposal(uint256 proposalId) external view returns (
        uint256 id, address proposer, string memory title, string memory description,
        uint256 forVotes, uint256 againstVotes, uint256 abstainVotes,
        uint256 startBlock, uint256 endBlock, bool executed, bool canceled
    ) {
        Proposal storage p = proposals[proposalId];
        return (p.id, p.proposer, p.title, p.description, p.forVotes, p.againstVotes, 
                p.abstainVotes, p.startBlock, p.endBlock, p.executed, p.canceled);
    }
    
    function hasVoted(uint256 proposalId, address voter) external view returns (bool) {
        return proposals[proposalId].hasVoted[voter];
    }
}