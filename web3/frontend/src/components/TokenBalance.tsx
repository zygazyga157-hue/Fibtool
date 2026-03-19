'use client';

import { useReadContract } from 'wagmi';
import { CONTRACTS, FIBT_TOKEN_ABI } from '@/contracts/abis';
import { formatTokenAmount } from '@/utils/helpers';

interface TokenBalanceProps {
  address: `0x${string}`;
  showSymbol?: boolean;
}

export function TokenBalance({ address, showSymbol = true }: TokenBalanceProps) {
  const { data: balance, isLoading } = useReadContract({
    address: CONTRACTS.FIBT_TOKEN,
    abi: FIBT_TOKEN_ABI,
    functionName: 'balanceOf',
    args: [address],
  });

  if (isLoading) {
    return <div className="animate-shimmer h-6 w-24 rounded" />;
  }

  return (
    <span className="font-semibold">
      {formatTokenAmount(balance || BigInt(0))}
      {showSymbol && ' FIBT'}
    </span>
  );
}
