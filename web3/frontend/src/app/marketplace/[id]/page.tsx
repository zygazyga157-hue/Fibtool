'use client';

import { useParams } from 'next/navigation';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { FiStar, FiTrendingUp, FiActivity, FiShield } from 'react-icons/fi';
import { formatPercent, formatTokenAmount, getStrategyCategoryName } from '@/utils/helpers';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const MOCK_STRATEGY = {
  id: '1',
  name: 'Fibonacci Retracement Master',
  creator: '0x1234...5678',
  category: 0,
  totalSignals: 150,
  successfulSignals: 108,
  totalVolume: BigInt('2500000000000000000000'),
  rating: 4.5,
  price: BigInt('50000000000000000000'),
  description:
    'Advanced Fibonacci retracement strategy using golden ratio levels for precision entries. Combines multiple timeframes for optimal signal accuracy.',
  createdAt: '2024-06-15',
  winRate: 72,
  avgReturn: 4.8,
  sharpeRatio: 2.3,
  maxDrawdown: 12.5,
};

const MOCK_SIGNALS = [
  {
    id: '1',
    pair: 'EURUSD',
    type: 'Buy',
    entryPrice: 1.085,
    tp: 1.092,
    sl: 1.081,
    result: 'TP Hit',
    profit: 6.5,
    timestamp: '2025-01-05 14:30',
  },
  {
    id: '2',
    pair: 'GBPUSD',
    type: 'Sell',
    entryPrice: 1.265,
    tp: 1.258,
    sl: 1.269,
    result: 'TP Hit',
    profit: 5.5,
    timestamp: '2025-01-04 10:15',
  },
  {
    id: '3',
    pair: 'USDJPY',
    type: 'Buy',
    entryPrice: 145.5,
    tp: 146.8,
    sl: 144.8,
    result: 'SL Hit',
    profit: -4.8,
    timestamp: '2025-01-03 08:45',
  },
];

const performanceData = {
  labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  datasets: [
    {
      label: 'Cumulative Return',
      data: [0, 3.2, 5.8, 12.5, 18.3, 22.1, 28.5, 32.4, 38.9, 42.1, 45.8, 52.3],
      borderColor: 'rgb(14, 165, 233)',
      backgroundColor: 'rgba(14, 165, 233, 0.1)',
      fill: true,
      tension: 0.4,
    },
  ],
};

const chartOptions = {
  responsive: true,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      titleColor: '#fff',
      bodyColor: '#fff',
      borderColor: 'rgba(14, 165, 233, 0.5)',
      borderWidth: 1,
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      grid: {
        color: 'rgba(255, 255, 255, 0.05)',
      },
      ticks: {
        color: '#9ca3af',
        callback: function (value: any) {
          return value + '%';
        },
      },
    },
    x: {
      grid: {
        display: false,
      },
      ticks: {
        color: '#9ca3af',
      },
    },
  },
};

export default function StrategyDetailPage() {
  const params = useParams();

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="glass rounded-xl p-8 mb-8">
          <div className="flex justify-between items-start mb-6">
            <div className="flex-1">
              <div className="flex items-center space-x-4 mb-3">
                <h1 className="text-4xl font-bold text-white">{MOCK_STRATEGY.name}</h1>
                <div className="flex items-center space-x-1 bg-yellow-500/20 px-3 py-1 rounded-full">
                  <FiStar className="text-yellow-500" />
                  <span className="text-yellow-500 font-semibold">
                    {MOCK_STRATEGY.rating.toFixed(1)}
                  </span>
                </div>
              </div>
              <div className="flex items-center space-x-6 text-gray-400 mb-4">
                <span>{getStrategyCategoryName(MOCK_STRATEGY.category)}</span>
                <span>•</span>
                <span>By {MOCK_STRATEGY.creator}</span>
                <span>•</span>
                <span>Since {MOCK_STRATEGY.createdAt}</span>
              </div>
              <p className="text-gray-400 max-w-3xl">{MOCK_STRATEGY.description}</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-400 mb-2">Price per Signal</div>
              <div className="text-3xl font-bold text-white mb-4">
                {formatTokenAmount(MOCK_STRATEGY.price)} FIBT
              </div>
              <button className="w-full px-8 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition">
                Subscribe
              </button>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="glass rounded-xl p-6">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-10 h-10 bg-success rounded-lg flex items-center justify-center">
                <FiTrendingUp className="text-white" />
              </div>
              <div className="text-gray-400 text-sm">Win Rate</div>
            </div>
            <div className="text-3xl font-bold text-white">{MOCK_STRATEGY.winRate}%</div>
            <div className="text-sm text-success mt-1">
              {MOCK_STRATEGY.successfulSignals}/{MOCK_STRATEGY.totalSignals} signals
            </div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
                <FiActivity className="text-white" />
              </div>
              <div className="text-gray-400 text-sm">Avg Return</div>
            </div>
            <div className="text-3xl font-bold text-white">+{MOCK_STRATEGY.avgReturn}%</div>
            <div className="text-sm text-gray-400 mt-1">Per signal</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-10 h-10 bg-accent-600 rounded-lg flex items-center justify-center">
                <FiShield className="text-white" />
              </div>
              <div className="text-gray-400 text-sm">Sharpe Ratio</div>
            </div>
            <div className="text-3xl font-bold text-white">{MOCK_STRATEGY.sharpeRatio}</div>
            <div className="text-sm text-gray-400 mt-1">Risk-adjusted</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-10 h-10 bg-error rounded-lg flex items-center justify-center">
                <FiTrendingUp className="text-white rotate-180" />
              </div>
              <div className="text-gray-400 text-sm">Max Drawdown</div>
            </div>
            <div className="text-3xl font-bold text-white">-{MOCK_STRATEGY.maxDrawdown}%</div>
            <div className="text-sm text-gray-400 mt-1">Peak to trough</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Performance Chart */}
            <div className="glass rounded-xl p-6">
              <h2 className="text-2xl font-bold text-white mb-6">Performance History</h2>
              <div className="h-80">
                <Line data={performanceData} options={chartOptions} />
              </div>
            </div>

            {/* Signal History */}
            <div className="glass rounded-xl p-6">
              <h2 className="text-2xl font-bold text-white mb-6">Recent Signals</h2>
              <div className="space-y-3">
                {MOCK_SIGNALS.map((signal) => (
                  <div
                    key={signal.id}
                    className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="flex items-center space-x-3 mb-1">
                          <span className="text-white font-bold text-lg">{signal.pair}</span>
                          <span
                            className={`px-2 py-1 rounded text-sm font-semibold ${
                              signal.type === 'Buy'
                                ? 'bg-success/20 text-success'
                                : 'bg-error/20 text-error'
                            }`}
                          >
                            {signal.type}
                          </span>
                          <span
                            className={`px-2 py-1 rounded text-sm ${
                              signal.result === 'TP Hit'
                                ? 'bg-success/20 text-success'
                                : 'bg-error/20 text-error'
                            }`}
                          >
                            {signal.result}
                          </span>
                        </div>
                        <div className="text-sm text-gray-400">{signal.timestamp}</div>
                      </div>
                      <div className="text-right">
                        <div
                          className={`text-2xl font-bold ${
                            signal.profit >= 0 ? 'text-success' : 'text-error'
                          }`}
                        >
                          {signal.profit >= 0 ? '+' : ''}
                          {signal.profit.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-gray-400">Entry</div>
                        <div className="text-white font-semibold">{signal.entryPrice}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">TP</div>
                        <div className="text-success font-semibold">{signal.tp}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">SL</div>
                        <div className="text-error font-semibold">{signal.sl}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Monthly Performance */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">Monthly Performance</h3>
              <div className="space-y-3">
                {[
                  { month: 'November', return: 8.2 },
                  { month: 'October', return: 6.5 },
                  { month: 'September', return: 12.1 },
                  { month: 'August', return: -2.3 },
                ].map((item, idx) => (
                  <div key={idx} className="flex justify-between items-center">
                    <span className="text-gray-400">{item.month}</span>
                    <span
                      className={`font-semibold ${
                        item.return >= 0 ? 'text-success' : 'text-error'
                      }`}
                    >
                      {item.return >= 0 ? '+' : ''}
                      {item.return}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk Metrics */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">Risk Metrics</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-400">Volatility</span>
                    <span className="text-white">15.2%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2">
                    <div className="bg-warning h-2 rounded-full" style={{ width: '35%' }} />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-400">Consistency</span>
                    <span className="text-white">82%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2">
                    <div className="bg-success h-2 rounded-full" style={{ width: '82%' }} />
                  </div>
                </div>
                <div className="pt-4 border-t border-gray-700">
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-400">Total Volume</span>
                    <span className="text-white font-semibold">
                      {formatTokenAmount(MOCK_STRATEGY.totalVolume, 18, 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Signals</span>
                    <span className="text-white font-semibold">
                      {MOCK_STRATEGY.totalSignals}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Strategy Info */}
            <div className="glass rounded-xl p-6">
              <h3 className="text-xl font-bold text-white mb-4">Strategy Details</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Category</span>
                  <span className="text-white">
                    {getStrategyCategoryName(MOCK_STRATEGY.category)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Timeframe</span>
                  <span className="text-white">H1, H4</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Pairs</span>
                  <span className="text-white">Major Forex</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Signals/Week</span>
                  <span className="text-white">5-8</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
