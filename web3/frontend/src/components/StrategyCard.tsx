'use client';

import Link from 'next/link';
import { FiTrendingUp, FiStar, FiActivity } from 'react-icons/fi';
import { formatPercent, formatTokenAmount, getStrategyCategoryName } from '@/utils/helpers';

interface Strategy {
  id: string;
  name: string;
  creator: string;
  category: number;
  totalSignals: number;
  successfulSignals: number;
  totalVolume: bigint;
  rating: number;
  price: bigint;
}

interface StrategyCardProps {
  strategy: Strategy;
}

export function StrategyCard({ strategy }: StrategyCardProps) {
  const winRate = strategy.totalSignals > 0
    ? (strategy.successfulSignals / strategy.totalSignals) * 100
    : 0;

  return (
    <Link href={`/marketplace/${strategy.id}`}>
      <div className="glass rounded-xl p-6 card-hover cursor-pointer">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-white mb-1">{strategy.name}</h3>
            <p className="text-sm text-gray-400">
              {getStrategyCategoryName(strategy.category)}
            </p>
          </div>
          <div className="flex items-center space-x-1 bg-yellow-500/20 px-2 py-1 rounded">
            <FiStar className="text-yellow-500" />
            <span className="text-yellow-500 text-sm font-semibold">
              {strategy.rating.toFixed(1)}
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <div className="text-2xl font-bold text-primary-500">
              {formatPercent(winRate, 0)}
            </div>
            <div className="text-xs text-gray-400">Win Rate</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {strategy.totalSignals}
            </div>
            <div className="text-xs text-gray-400">Signals</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-success">
              {formatTokenAmount(strategy.totalVolume, 18, 0)}
            </div>
            <div className="text-xs text-gray-400">Volume</div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-700">
          <div className="text-sm text-gray-400">
            Price per signal
          </div>
          <div className="text-lg font-bold text-white">
            {formatTokenAmount(strategy.price)} FIBT
          </div>
        </div>
      </div>
    </Link>
  );
}
