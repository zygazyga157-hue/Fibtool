'use client';

import { useState } from 'react';
import { useAccount } from 'wagmi';
import { StrategyCard } from '@/components/StrategyCard';
import { FiSearch, FiFilter } from 'react-icons/fi';

// Mock data - in production, fetch from subgraph or API
const MOCK_STRATEGIES = [
  {
    id: '1',
    name: 'Fibonacci Retracement Master',
    creator: '0x1234...5678',
    category: 0,
    totalSignals: 150,
    successfulSignals: 108,
    totalVolume: BigInt('2500000000000000000000'),
    rating: 4.5,
    price: BigInt('50000000000000000000'),
  },
  {
    id: '2',
    name: 'Gann Fan Pro Strategy',
    creator: '0xabcd...efgh',
    category: 1,
    totalSignals: 89,
    successfulSignals: 67,
    totalVolume: BigInt('1800000000000000000000'),
    rating: 4.2,
    price: BigInt('75000000000000000000'),
  },
  {
    id: '3',
    name: 'Harmonic Patterns Elite',
    creator: '0x9876...5432',
    category: 2,
    totalSignals: 203,
    successfulSignals: 156,
    totalVolume: BigInt('3200000000000000000000'),
    rating: 4.8,
    price: BigInt('100000000000000000000'),
  },
];

export default function MarketplacePage() {
  const { isConnected } = useAccount();
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<number | null>(null);

  const filteredStrategies = MOCK_STRATEGIES.filter((strategy) => {
    const matchesSearch = strategy.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = categoryFilter === null || strategy.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Strategy Marketplace</h1>
          <p className="text-gray-400">
            Browse verified trading strategies with on-chain performance tracking
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          {/* Search */}
          <div className="flex-1 relative">
            <FiSearch className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search strategies..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary-500"
            />
          </div>

          {/* Category Filter */}
          <select
            value={categoryFilter === null ? '' : categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value === '' ? null : parseInt(e.target.value))}
            className="px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary-500"
          >
            <option value="">All Categories</option>
            <option value="0">Fibonacci</option>
            <option value="1">Gann</option>
            <option value="2">Harmonic</option>
            <option value="3">Elliott Wave</option>
            <option value="4">Price Action</option>
            <option value="5">Other</option>
          </select>
        </div>

        {/* Strategy Grid */}
        {isConnected ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredStrategies.map((strategy) => (
              <StrategyCard key={strategy.id} strategy={strategy} />
            ))}
          </div>
        ) : (
          <div className="text-center py-20">
            <div className="glass rounded-xl p-12 max-w-md mx-auto">
              <h3 className="text-2xl font-bold text-white mb-4">
                Connect Your Wallet
              </h3>
              <p className="text-gray-400 mb-6">
                Connect your wallet to browse and purchase trading strategies
              </p>
            </div>
          </div>
        )}

        {filteredStrategies.length === 0 && isConnected && (
          <div className="text-center py-20">
            <p className="text-gray-400">No strategies found matching your criteria</p>
          </div>
        )}
      </div>
    </div>
  );
}
