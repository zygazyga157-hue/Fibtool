// Contract Addresses
export const CONTRACTS = {
  FIBT_TOKEN: process.env.NEXT_PUBLIC_FIBT_TOKEN_ADDRESS as `0x${string}`,
  STRATEGY_NFT: process.env.NEXT_PUBLIC_STRATEGY_NFT_ADDRESS as `0x${string}`,
  STAKING_MANAGER: process.env.NEXT_PUBLIC_STAKING_MANAGER_ADDRESS as `0x${string}`,
  SIGNAL_ESCROW: process.env.NEXT_PUBLIC_SIGNAL_ESCROW_ADDRESS as `0x${string}`,
  STRATEGY_REGISTRY: process.env.NEXT_PUBLIC_STRATEGY_REGISTRY_ADDRESS as `0x${string}`,
  REVENUE_DISTRIBUTOR: process.env.NEXT_PUBLIC_REVENUE_DISTRIBUTOR_ADDRESS as `0x${string}`,
  GOVERNANCE_DAO: process.env.NEXT_PUBLIC_GOVERNANCE_DAO_ADDRESS as `0x${string}`,
  PRICE_ORACLE: process.env.NEXT_PUBLIC_PRICE_ORACLE_ADDRESS as `0x${string}`,
  MT5_ORACLE: process.env.NEXT_PUBLIC_MT5_ORACLE_ADDRESS as `0x${string}`,
  PERFORMANCE_VERIFIER: process.env.NEXT_PUBLIC_PERFORMANCE_VERIFIER_ADDRESS as `0x${string}`,
  VIP_TIER_MANAGER: process.env.NEXT_PUBLIC_VIP_TIER_MANAGER_ADDRESS as `0x${string}`,
};

// FIBT Token ABI (Essential functions)
export const FIBT_TOKEN_ABI = [
  {
    inputs: [{ name: 'account', type: 'address' }],
    name: 'balanceOf',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [
      { name: 'spender', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    name: 'approve',
    outputs: [{ name: '', type: 'bool' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [
      { name: 'owner', type: 'address' },
      { name: 'spender', type: 'address' },
    ],
    name: 'allowance',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    name: 'transfer',
    outputs: [{ name: '', type: 'bool' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [],
    name: 'totalSupply',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// Staking Manager ABI
export const STAKING_MANAGER_ABI = [
  {
    inputs: [
      { name: 'amount', type: 'uint256' },
      { name: 'tier', type: 'uint8' },
      { name: 'autoCompound', type: 'bool' },
    ],
    name: 'stake',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'amount', type: 'uint256' }],
    name: 'unstake',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [],
    name: 'claimRewards',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'user', type: 'address' }],
    name: 'stakes',
    outputs: [
      { name: 'amount', type: 'uint256' },
      { name: 'stakedAt', type: 'uint256' },
      { name: 'lastClaimAt', type: 'uint256' },
      { name: 'tier', type: 'uint8' },
      { name: 'autoCompound', type: 'bool' },
    ],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [{ name: 'user', type: 'address' }],
    name: 'calculateRewards',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// Strategy NFT ABI
export const STRATEGY_NFT_ABI = [
  {
    inputs: [
      { name: 'tier', type: 'uint8' },
      { name: 'metadata', type: 'string' },
    ],
    name: 'mint',
    outputs: [{ name: 'tokenId', type: 'uint256' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'owner', type: 'address' }],
    name: 'balanceOf',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    name: 'ownerOf',
    outputs: [{ name: '', type: 'address' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    name: 'tokenURI',
    outputs: [{ name: '', type: 'string' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// Signal Escrow ABI
export const SIGNAL_ESCROW_ABI = [
  {
    inputs: [
      { name: 'signalId', type: 'bytes32' },
      { name: 'creator', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    name: 'buySignal',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'signalId', type: 'bytes32' }],
    name: 'getSignalDetails',
    outputs: [
      { name: 'buyer', type: 'address' },
      { name: 'creator', type: 'address' },
      { name: 'amount', type: 'uint256' },
      { name: 'purchasedAt', type: 'uint256' },
      { name: 'settled', type: 'bool' },
    ],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// Strategy Registry ABI
export const STRATEGY_REGISTRY_ABI = [
  {
    inputs: [{ name: 'strategyId', type: 'bytes32' }],
    name: 'getStrategy',
    outputs: [
      { name: 'creator', type: 'address' },
      { name: 'nftTokenId', type: 'uint256' },
      { name: 'category', type: 'uint8' },
      { name: 'status', type: 'uint8' },
      { name: 'totalSignals', type: 'uint256' },
      { name: 'successfulSignals', type: 'uint256' },
      { name: 'totalVolume', type: 'uint256' },
      { name: 'totalProfit', type: 'int256' },
    ],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [],
    name: 'getActiveStrategies',
    outputs: [{ name: '', type: 'bytes32[]' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// Governance DAO ABI
export const GOVERNANCE_DAO_ABI = [
  {
    inputs: [
      { name: 'targets', type: 'address[]' },
      { name: 'values', type: 'uint256[]' },
      { name: 'calldatas', type: 'bytes[]' },
      { name: 'description', type: 'string' },
      { name: 'category', type: 'uint8' },
    ],
    name: 'proposeWithMetadata',
    outputs: [{ name: 'proposalId', type: 'uint256' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [
      { name: 'proposalId', type: 'uint256' },
      { name: 'support', type: 'uint8' },
    ],
    name: 'castVote',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'proposalId', type: 'uint256' }],
    name: 'state',
    outputs: [{ name: '', type: 'uint8' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;

// VIP Tier Manager ABI
export const VIP_TIER_MANAGER_ABI = [
  {
    inputs: [{ name: 'user', type: 'address' }],
    name: 'getUserTier',
    outputs: [{ name: '', type: 'uint8' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [
      { name: 'user', type: 'address' },
      { name: 'baseFee', type: 'uint256' },
    ],
    name: 'calculateFee',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;
