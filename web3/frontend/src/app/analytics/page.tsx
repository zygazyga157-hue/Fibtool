'use client';

import { Line, Doughnut, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { FiTrendingUp, FiDollarSign, FiActivity, FiUsers } from 'react-icons/fi';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const platformVolumeData = {
  labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov'],
  datasets: [
    {
      label: 'Trading Volume (FIBT)',
      data: [125000, 158000, 203000, 245000, 312000, 389000, 456000, 523000, 612000, 701000, 845000],
      borderColor: 'rgb(14, 165, 233)',
      backgroundColor: 'rgba(14, 165, 233, 0.1)',
      fill: true,
      tension: 0.4,
    },
  ],
};

const categoryDistribution = {
  labels: ['Fibonacci', 'Gann', 'Harmonic', 'Elliott Wave', 'Price Action', 'Other'],
  datasets: [
    {
      data: [35, 20, 25, 10, 8, 2],
      backgroundColor: [
        'rgba(14, 165, 233, 0.8)',
        'rgba(245, 158, 11, 0.8)',
        'rgba(16, 185, 129, 0.8)',
        'rgba(239, 68, 68, 0.8)',
        'rgba(139, 92, 246, 0.8)',
        'rgba(156, 163, 175, 0.8)',
      ],
      borderWidth: 0,
    },
  ],
};

const topStrategiesData = {
  labels: ['Fib Master', 'Gann Pro', 'Harmonic Elite', 'Wave Rider', 'PA Expert'],
  datasets: [
    {
      label: 'Win Rate (%)',
      data: [72, 68, 75, 65, 70],
      backgroundColor: 'rgba(16, 185, 129, 0.8)',
    },
  ],
};

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
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

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        color: '#fff',
        padding: 15,
      },
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      titleColor: '#fff',
      bodyColor: '#fff',
      borderColor: 'rgba(14, 165, 233, 0.5)',
      borderWidth: 1,
    },
  },
};

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
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
      max: 100,
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

export default function AnalyticsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Analytics Dashboard</h1>
          <p className="text-gray-400">Platform-wide statistics and insights</p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">Total Volume</div>
              <FiDollarSign className="text-primary-500 text-xl" />
            </div>
            <div className="text-3xl font-bold text-white">$2.5M</div>
            <div className="text-sm text-success mt-1">+18.2% vs last month</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">Active Strategies</div>
              <FiActivity className="text-accent-500 text-xl" />
            </div>
            <div className="text-3xl font-bold text-white">1,247</div>
            <div className="text-sm text-success mt-1">+8.5% vs last month</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">Total Users</div>
              <FiUsers className="text-success text-xl" />
            </div>
            <div className="text-3xl font-bold text-white">8,532</div>
            <div className="text-sm text-success mt-1">+12.3% vs last month</div>
          </div>

          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-gray-400 text-sm">Avg Win Rate</div>
              <FiTrendingUp className="text-success text-xl" />
            </div>
            <div className="text-3xl font-bold text-white">72.4%</div>
            <div className="text-sm text-success mt-1">+2.1% vs last month</div>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Platform Volume Chart */}
          <div className="glass rounded-xl p-6">
            <h2 className="text-2xl font-bold text-white mb-6">Platform Trading Volume</h2>
            <div className="h-80">
              <Line data={platformVolumeData} options={chartOptions} />
            </div>
          </div>

          {/* Category Distribution */}
          <div className="glass rounded-xl p-6">
            <h2 className="text-2xl font-bold text-white mb-6">Strategy Categories</h2>
            <div className="h-80">
              <Doughnut data={categoryDistribution} options={doughnutOptions} />
            </div>
          </div>
        </div>

        {/* Top Strategies */}
        <div className="glass rounded-xl p-6 mb-8">
          <h2 className="text-2xl font-bold text-white mb-6">Top Performing Strategies</h2>
          <div className="h-80">
            <Bar data={topStrategiesData} options={barOptions} />
          </div>
        </div>

        {/* Additional Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">Revenue Distribution</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Staking Rewards</span>
                  <span className="text-white">40%</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                  <div className="bg-primary-600 h-2 rounded-full" style={{ width: '40%' }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Buyback & Burn</span>
                  <span className="text-white">30%</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                  <div className="bg-accent-600 h-2 rounded-full" style={{ width: '30%' }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">DAO Treasury</span>
                  <span className="text-white">20%</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                  <div className="bg-success h-2 rounded-full" style={{ width: '20%' }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Development</span>
                  <span className="text-white">10%</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                  <div className="bg-error h-2 rounded-full" style={{ width: '10%' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">Token Metrics</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Total Supply</span>
                <span className="text-white font-semibold">100M FIBT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Circulating</span>
                <span className="text-white font-semibold">75M FIBT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Staked</span>
                <span className="text-white font-semibold">28M FIBT</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Burned</span>
                <span className="text-error font-semibold">2.5M FIBT</span>
              </div>
              <div className="flex justify-between pt-3 border-t border-gray-700">
                <span className="text-gray-400">Market Cap</span>
                <span className="text-white font-semibold">$5.2M</span>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">Recent Activity</h3>
            <div className="space-y-3">
              <div className="flex items-start space-x-3">
                <div className="w-2 h-2 bg-success rounded-full mt-2" />
                <div className="flex-1">
                  <div className="text-white text-sm">New strategy listed</div>
                  <div className="text-gray-400 text-xs">2 minutes ago</div>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="w-2 h-2 bg-primary-600 rounded-full mt-2" />
                <div className="flex-1">
                  <div className="text-white text-sm">250K FIBT staked</div>
                  <div className="text-gray-400 text-xs">15 minutes ago</div>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="w-2 h-2 bg-accent-600 rounded-full mt-2" />
                <div className="flex-1">
                  <div className="text-white text-sm">Governance proposal passed</div>
                  <div className="text-gray-400 text-xs">1 hour ago</div>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="w-2 h-2 bg-success rounded-full mt-2" />
                <div className="flex-1">
                  <div className="text-white text-sm">500 signals executed</div>
                  <div className="text-gray-400 text-xs">2 hours ago</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
