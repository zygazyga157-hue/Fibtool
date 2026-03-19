import { useWriteContract, useWaitForTransaction, useReadContract } from 'wagmi';
import { parseUnits } from 'viem';
import toast from 'react-hot-toast';
import { CONTRACTS, FIBT_TOKEN_ABI, SIGNAL_ESCROW_ABI } from '@/contracts/abis';

export function useTokenApproval() {
  const { writeContract, data: hash } = useWriteContract();
  const { isLoading } = useWaitForTransaction({ hash });

  const approve = async (spender: `0x${string}`, amount: string) => {
    try {
      const amountWei = parseUnits(amount, 18);
      
      writeContract({
        address: CONTRACTS.FIBT_TOKEN,
        abi: FIBT_TOKEN_ABI,
        functionName: 'approve',
        args: [spender, amountWei],
      });

      toast.success('Approval submitted!');
      return true;
    } catch (error: any) {
      toast.error(error.message || 'Approval failed');
      return false;
    }
  };

  return { approve, isApproving: isLoading };
}

export function useTokenBalance(address?: `0x${string}`) {
  const { data: balance, isLoading, refetch } = useReadContract({
    address: CONTRACTS.FIBT_TOKEN,
    abi: FIBT_TOKEN_ABI,
    functionName: 'balanceOf',
    args: address ? [address] : undefined,
    enabled: !!address,
  });

  return {
    balance: balance || BigInt(0),
    isLoading,
    refetch,
  };
}

export function useAllowance(owner?: `0x${string}`, spender?: `0x${string}`) {
  const { data: allowance, isLoading, refetch } = useReadContract({
    address: CONTRACTS.FIBT_TOKEN,
    abi: FIBT_TOKEN_ABI,
    functionName: 'allowance',
    args: owner && spender ? [owner, spender] : undefined,
    enabled: !!(owner && spender),
  });

  return {
    allowance: allowance || BigInt(0),
    isLoading,
    refetch,
  };
}
