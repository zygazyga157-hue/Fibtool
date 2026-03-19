'use client';

import { useAccount } from 'wagmi';
import { TokenBalance } from '@/components/TokenBalance';
import { FiTrendingUp, FiActivity, FiAward, FiClock } from 'react-icons/fi';
import { formatTokenAmount, formatRelativeTime, getVIPTierName, getVIPTierDiscount } from '@/utils/helpers';

interface Transaction {
  id: string;
  type: 'stake' | 'unstake' | 'buy' | 'claim';
  amount: bigint;
  timestamp: number;
  status: 'success' | 'pending' | 'failed';
}

interface ActiveSignal {
  id: string;
  strategy: string;
  entryPrice: string;
  currentPrice: string;
  pl: number;
  purchasedAt: number;
}

const MOCK_TRANSACTIONS: Transaction[] = [
  {
    id: '1',
    type: 'stake',
    amount: BigInt('5000000000000000000000'),
    timestamp: Date.now() / 1000 - 86400,
    status: 'success',
  },
  {
    id: '2',
    type: 'buy',
    amount: BigInt('100000000000000000000'),
    timestamp: Date.now() / 1000 - 86400 * 2,
    status: 'success',
  },
];

const MOCK_SIGNALS: ActiveSignal[] = [
  {
    id: '1',
    strategy: 'Fibonacci Retracement Master',
    entryPrice: '1.0850',
    currentPrice: '1.0920',
    pl: 6.45,
    purchasedAt: Date.now() / 1000 - 3600 * 4,
  },
  {
    id: '2',
    strategy: 'Harmonic Patterns Elite',
    entryPrice: '2150.50',
    currentPrice: '2145.30',
    pl: -0.24,
    purchasedAt: Date.now() / 1000 - 3600 * 2,
  },
];

export default function ProfilePage() {
  const { address, isConnected } = useAccount();

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
        <div className="max-w-7xl mx-auto text-center py-20">
          <div className="glass rounded-xl p-12 max-w-md mx-auto">
            <h3 className="text-2xl font-bold text-white mb-4">Connect Your Wallet</h3>
            <p className="text-gray-400 mb-6">Connect your wallet to view your profile</p>
          </div>
        </div>
      </div>
    );
  }

  const vipTier = 2; // Mock VIP tier
  const totalPL = 4500; // Mock total P/L in USD

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Portfolio</h1>
          <p className="text-gray-400">Track your investments and performance</p>
        </div>

        {/* Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">FIBT Balance</div>
              <FiActivity className="text-primary-500" />
            </div>
            <div className="text-3xl font-bold text-white">
              <TokenBalance address={address as `0x${string}`} showSymbol={false} />
            </div>
            <div className="text-sm text-gray-400 mt-1">FIBT</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">Total Staked</div>
              <FiTrendingUp className="text-success" />
            </div>
            <div className="text-3xl font-bold text-white">5,000</div>
            <div className="text-sm text-gray-400 mt-1">FIBT</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">Total P/L</div>
              <FiTrendingUp className={totalPL >= 0 ? 'text-success' : 'text-error'} />
            </div>
            <div className={`text-3xl font-bold ${totalPL >= 0 ? 'text-success' : 'text-error'}`}>
              {totalPL >= 0 ? '+' : ''}{totalPL.toFixed(2)}
            </div>
            <div className="text-sm text-gray-400 mt-1">USD</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">VIP Tier</div>
              <FiAward className="text-accent-500" />
            </div>
            <div className="text-3xl font-bold gradient-text">
              {getVIPTierName(vipTier)}
            </div>
            <div className="text-sm text-gray-400 mt-1">
              {getVIPTierDiscount(vipTier)}% Fee Discount
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Active Signals */}
            <div className="glass rounded-xl p-6">
              <h2 className="text-2xl font-bold text-white mb-6">Active Signals</h2>
              <div className="space-y-4">
                {MOCK_SIGNALS.map((signal) => (
                  <div
                    key={signal.id}
                    className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h3 className="text-white font-semibold mb-1">{signal.strategy}</h3>
                        <div className="text-sm text-gray-400">
                          {formatRelativeTime(signal.purchasedAt)}
                        </div>
                      </div>
                      <div
                        className={`text-lg font-bold ${
                          signal.pl >= 0 ? 'text-success' : 'text-error'
                        }`}
                      >
                        {signal.pl >= 0 ? '+' : ''}{signal.pl.toFixed(2)}%
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <div className="text-gray-400">Entry Price</div>
                        <div className="text-white font-semibold">{signal.entryPrice}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">Current Price</div>
                        <div className="text-white font-semibold">{signal.currentPrice}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Transaction History */}
            <div className="glass rounded-xl p-6">
              <h2 className="text-2xl font-bold text-white mb-6">Transaction History</h2>
              <div className="space-y-3">
                {MOCK_TRANSACTIONS.map((tx) => (
                  <div
                    key={tx.id}
                    className="flex justify-between items-center bg-gray-800 rounded-lg p-4"
                  >
                    <div className="flex items-center space-x-4">
                      <div
                        className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          tx.type === 'stake' || tx.type === 'buy'
                            ? 'bg-primary-600'
                            : 'bg-accent-600'
                        }`}
                      >
                        <FiActivity className="text-white" />
                      </div>
                      <div>
                        <div className="text-white font-semibold capitalize">{tx.type}</div>
                        <div className="text-sm text-gray-400">
                          {formatRelativeTime(tx.timestamp)}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white font-semibold">
                        {formatTokenAmount(tx.amount)} FIBT
                      </div>
                      <div
                        className={`text-sm ${
                          tx.status === 'success'
                            ? 'text-success'
                            : tx.status === 'pending'
                            ? 'text-warning'
                            : 'text-error'
                        }`}
                      >
                        {tx.status}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Staking Info */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">Staking</h3>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-400">Amount Staked</span>
                  <span className="text-white font-semibold">5,000 FIBT</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Current APY</span>
                  <span className="text-success font-semibold">8%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Pending Rewards</span>
                  <span className="text-white font-semibold">42.5 FIBT</span>
                </div>
                <button className="w-full px-4 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition">
                  Claim Rewards
                </button>
              </div>
            </div>

            {/* VIP Benefits */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">VIP Benefits</h3>
              <div className="space-y-3">
                <div className="flex items-start space-x-3">
                  <div className="w-6 h-6 bg-primary-600 rounded-full flex items-center justify-center mt-0.5">
                    <FiTrendingUp className="text-white text-sm" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">20% Fee Discount</div>
                    <div className="text-sm text-gray-400">On all signal purchases</div>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-6 h-6 bg-success rounded-full flex items-center justify-center mt-0.5">
                    <FiAward className="text-white text-sm" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">Priority Access</div>
                    <div className="text-sm text-gray-400">To new strategies</div>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="w-6 h-6 bg-accent-600 rounded-full flex items-center justify-center mt-0.5">
                    <FiClock className="text-white text-sm" />
                  </div>
                  <div>
                    <div className="text-white font-semibold">Early Signals</div>
                    <div className="text-sm text-gray-400">Before public release</div>
                  </div>
                </div>
              </div>
              <div className="mt-6 p-4 bg-primary-600/10 border border-primary-600/20 rounded-lg">
                <div className="text-sm text-gray-400 mb-2">Next Tier: VIP 3</div>
                <div className="text-white font-semibold mb-2">
                  Stake 5,000 more FIBT
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{ width: '50%' }}
                  />
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">Stats</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Total Signals</span>
                  <span className="text-white font-semibold">12</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Win Rate</span>
                  <span className="text-success font-semibold">75%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Total Volume</span>
                  <span className="text-white font-semibold">$45,200</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Member Since</span>
                  <span className="text-white font-semibold">Jan 2025</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
