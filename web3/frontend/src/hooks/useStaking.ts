import { useWriteContract, useWaitForTransaction, useReadContract } from 'wagmi';
import { parseUnits } from 'viem';
import toast from 'react-hot-toast';
import { CONTRACTS, STAKING_MANAGER_ABI } from '@/contracts/abis';

export function useStaking(userAddress?: `0x${string}`) {
  const { writeContract, data: hash } = useWriteContract();
  const { isLoading: isConfirming } = useWaitForTransaction({ hash });

  // Get stake info
  const { data: stakeInfo, refetch: refetchStake } = useReadContract({
    address: CONTRACTS.STAKING_MANAGER,
    abi: STAKING_MANAGER_ABI,
    functionName: 'stakes',
    args: userAddress ? [userAddress] : undefined,
    enabled: !!userAddress,
  });

  // Get pending rewards
  const { data: pendingRewards, refetch: refetchRewards } = useReadContract({
    address: CONTRACTS.STAKING_MANAGER,
    abi: STAKING_MANAGER_ABI,
    functionName: 'calculateRewards',
    args: userAddress ? [userAddress] : undefined,
    enabled: !!userAddress,
  });

  const stake = async (amount: string, tier: number, autoCompound: boolean) => {
    try {
      const amountWei = parseUnits(amount, 18);

      writeContract({
        address: CONTRACTS.STAKING_MANAGER,
        abi: STAKING_MANAGER_ABI,
        functionName: 'stake',
        args: [amountWei, tier, autoCompound],
      });

      toast.success('Staking transaction submitted!');
      return true;
    } catch (error: any) {
      toast.error(error.message || 'Staking failed');
      return false;
    }
  };

  const unstake = async (amount: string) => {
    try {
      const amountWei = parseUnits(amount, 18);

      writeContract({
        address: CONTRACTS.STAKING_MANAGER,
        abi: STAKING_MANAGER_ABI,
        functionName: 'unstake',
        args: [amountWei],
      });

      toast.success('Unstaking transaction submitted!');
      return true;
    } catch (error: any) {
      toast.error(error.message || 'Unstaking failed');
      return false;
    }
  };

  const claimRewards = async () => {
    try {
      writeContract({
        address: CONTRACTS.STAKING_MANAGER,
        abi: STAKING_MANAGER_ABI,
        functionName: 'claimRewards',
      });

      toast.success('Claiming rewards!');
      return true;
    } catch (error: any) {
      toast.error(error.message || 'Claim failed');
      return false;
    }
  };

  return {
    stake,
    unstake,
    claimRewards,
    stakeInfo,
    pendingRewards: pendingRewards || BigInt(0),
    isConfirming,
    refetchStake,
    refetchRewards,
  };
}
