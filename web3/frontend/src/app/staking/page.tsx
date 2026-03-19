'use client';

import { useAccount } from 'wagmi';
import { StakingWidget } from '@/components/StakingWidget';
import { TokenBalance } from '@/components/TokenBalance';
import { FiTrendingUp, FiDollarSign, FiClock } from 'react-icons/fi';

export default function StakingPage() {
  const { address, isConnected } = useAccount();

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
        <div className="max-w-7xl mx-auto text-center py-20">
          <div className="glass rounded-xl p-12 max-w-md mx-auto">
            <h3 className="text-2xl font-bold text-white mb-4">
              Connect Your Wallet
            </h3>
            <p className="text-gray-400 mb-6">
              Connect your wallet to start staking FIBT tokens
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Staking</h1>
          <p className="text-gray-400">
            Stake FIBT to earn rewards and unlock VIP benefits
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Stats Column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Balance Card */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-lg text-gray-400 mb-2">Your FIBT Balance</h3>
              <div className="text-4xl font-bold text-white">
                <TokenBalance address={address as `0x${string}`} />
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="glass rounded-xl p-6">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
                    <FiTrendingUp className="text-white" />
                  </div>
                  <div className="text-gray-400 text-sm">Total Staked</div>
                </div>
                <div className="text-2xl font-bold text-white">0 FIBT</div>
              </div>

              <div className="glass rounded-xl p-6">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-success rounded-lg flex items-center justify-center">
                    <FiDollarSign className="text-white" />
                  </div>
                  <div className="text-gray-400 text-sm">Rewards Earned</div>
                </div>
                <div className="text-2xl font-bold text-white">0 FIBT</div>
              </div>

              <div className="glass rounded-xl p-6">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-accent-600 rounded-lg flex items-center justify-center">
                    <FiClock className="text-white" />
                  </div>
                  <div className="text-gray-400 text-sm">Current APY</div>
                </div>
                <div className="text-2xl font-bold text-white">0%</div>
              </div>
            </div>

            {/* Staking Info */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">How Staking Works</h3>
              <ul className="space-y-3 text-gray-400">
                <li className="flex items-start">
                  <span className="text-primary-500 mr-2">•</span>
                  <span>Stake FIBT to earn passive rewards (5-15% APY based on tier)</span>
                </li>
                <li className="flex items-start">
                  <span className="text-primary-500 mr-2">•</span>
                  <span>Unlock VIP benefits including fee discounts up to 80%</span>
                </li>
                <li className="flex items-start">
                  <span className="text-primary-500 mr-2">•</span>
                  <span>No lock-up period - unstake anytime (rewards stop accruing)</span>
                </li>
                <li className="flex items-start">
                  <span className="text-primary-500 mr-2">•</span>
                  <span>Auto-compound option to maximize your returns</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Staking Widget */}
          <div className="lg:col-span-1">
            <StakingWidget />
          </div>
        </div>
      </div>
    </div>
  );
}
