import { useWriteContract, useWaitForTransaction } from 'wagmi';
import toast from 'react-hot-toast';
import { CONTRACTS, STRATEGY_NFT_ABI } from '@/contracts/abis';

export function useNFT() {
  const { writeContract, data: hash } = useWriteContract();
  const { isLoading: isConfirming } = useWaitForTransaction({ hash });

  const mintNFT = async (tier: number, metadata: string) => {
    try {
      writeContract({
        address: CONTRACTS.STRATEGY_NFT,
        abi: STRATEGY_NFT_ABI,
        functionName: 'mint',
        args: [tier, metadata],
      });

      toast.success('Minting NFT...');
      return true;
    } catch (error: any) {
      toast.error(error.message || 'Minting failed');
      return false;
    }
  };

  return {
    mintNFT,
    isConfirming,
  };
}
