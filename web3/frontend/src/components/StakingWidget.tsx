'use client';

import { useState } from 'react';
import { useWriteContract, useWaitForTransaction } from 'wagmi';
import { parseUnits } from 'viem';
import toast from 'react-hot-toast';
import { CONTRACTS, STAKING_MANAGER_ABI } from '@/contracts/abis';

const STAKING_TIERS = [
  { tier: 0, name: 'Bronze', minAmount: 1000, apy: 5, color: 'from-orange-700 to-orange-500' },
  { tier: 1, name: 'Silver', minAmount: 5000, apy: 8, color: 'from-gray-400 to-gray-200' },
  { tier: 2, name: 'Gold', minAmount: 20000, apy: 12, color: 'from-yellow-600 to-yellow-400' },
  { tier: 3, name: 'Platinum', minAmount: 100000, apy: 15, color: 'from-cyan-400 to-blue-500' },
];

export function StakingWidget() {
  const [amount, setAmount] = useState('');
  const [selectedTier, setSelectedTier] = useState(0);
  const [autoCompound, setAutoCompound] = useState(true);

  const { writeContract, data: hash } = useWriteContract();
  const { isLoading: isConfirming } = useWaitForTransaction({ hash });

  const handleStake = async () => {
    if (!amount || parseFloat(amount) < STAKING_TIERS[selectedTier].minAmount) {
      toast.error(`Minimum stake: ${STAKING_TIERS[selectedTier].minAmount} FIBT`);
      return;
    }

    try {
      const amountWei = parseUnits(amount, 18);

      writeContract({
        address: CONTRACTS.STAKING_MANAGER,
        abi: STAKING_MANAGER_ABI,
        functionName: 'stake',
        args: [amountWei, selectedTier, autoCompound],
      });

      toast.success('Staking transaction submitted!');
    } catch (error: any) {
      toast.error(error.message || 'Failed to stake');
    }
  };

  return (
    <div className="glass rounded-xl p-6">
      <h3 className="text-2xl font-bold text-white mb-6">Stake FIBT</h3>

      {/* Tier Selection */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {STAKING_TIERS.map((tier) => (
          <button
            key={tier.tier}
            onClick={() => setSelectedTier(tier.tier)}
            className={`p-4 rounded-lg border-2 transition ${
              selectedTier === tier.tier
                ? 'border-primary-500 bg-primary-500/10'
                : 'border-gray-700 hover:border-gray-600'
            }`}
          >
            <div className={`text-lg font-bold bg-gradient-to-r ${tier.color} bg-clip-text text-transparent mb-1`}>
              {tier.name}
            </div>
            <div className="text-sm text-gray-400">
              Min: {tier.minAmount.toLocaleString()} FIBT
            </div>
            <div className="text-primary-500 font-semibold mt-1">
              {tier.apy}% APY
            </div>
          </button>
        ))}
      </div>

      {/* Amount Input */}
      <div className="mb-6">
        <label className="block text-sm text-gray-400 mb-2">
          Amount to Stake
        </label>
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-primary-500"
        />
        <div className="text-xs text-gray-400 mt-1">
          Minimum: {STAKING_TIERS[selectedTier].minAmount.toLocaleString()} FIBT
        </div>
      </div>

      {/* Auto Compound */}
      <div className="flex items-center justify-between mb-6 p-4 bg-gray-800 rounded-lg">
        <div>
          <div className="text-white font-semibold">Auto-Compound</div>
          <div className="text-sm text-gray-400">
            Automatically reinvest rewards
          </div>
        </div>
        <button
          onClick={() => setAutoCompound(!autoCompound)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
            autoCompound ? 'bg-primary-600' : 'bg-gray-600'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
              autoCompound ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* Stake Button */}
      <button
        onClick={handleStake}
        disabled={isConfirming || !amount}
        className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-700 text-white font-semibold py-3 rounded-lg transition"
      >
        {isConfirming ? 'Confirming...' : 'Stake FIBT'}
      </button>
    </div>
  );
}
