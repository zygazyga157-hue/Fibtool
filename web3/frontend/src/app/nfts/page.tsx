'use client';

import { useAccount } from 'wagmi';
import { FiImage } from 'react-icons/fi';

interface NFT {
  id: number;
  tier: number;
  name: string;
  image: string;
  mintedAt: string;
  performance: {
    totalSignals: number;
    winRate: number;
    volume: string;
  };
}

const MOCK_NFTS: NFT[] = [
  {
    id: 1,
    tier: 1,
    name: 'Premium Strategy #001',
    image: 'https://via.placeholder.com/300',
    mintedAt: '2025-01-15',
    performance: {
      totalSignals: 45,
      winRate: 73.3,
      volume: '1,250',
    },
  },
  {
    id: 2,
    tier: 0,
    name: 'Basic Strategy #042',
    image: 'https://via.placeholder.com/300',
    mintedAt: '2024-12-20',
    performance: {
      totalSignals: 28,
      winRate: 67.9,
      volume: '580',
    },
  },
];

const TIER_COLORS = {
  0: 'from-orange-700 to-orange-500', // Basic
  1: 'from-gray-400 to-gray-200', // Premium
  2: 'from-cyan-400 to-blue-500', // Elite
};

const TIER_NAMES = ['Basic', 'Premium', 'Elite'];

export default function NFTGalleryPage() {
  const { address, isConnected } = useAccount();

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
        <div className="max-w-7xl mx-auto text-center py-20">
          <div className="glass rounded-xl p-12 max-w-md mx-auto">
            <h3 className="text-2xl font-bold text-white mb-4">Connect Your Wallet</h3>
            <p className="text-gray-400 mb-6">Connect your wallet to view your NFT collection</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">NFT Gallery</h1>
            <p className="text-gray-400">Your strategy NFT collection</p>
          </div>
          <button className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition">
            Mint New NFT
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Total NFTs</div>
            <div className="text-3xl font-bold text-white">{MOCK_NFTS.length}</div>
          </div>
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Floor Value</div>
            <div className="text-3xl font-bold text-white">1,000 FIBT</div>
          </div>
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Total Volume</div>
            <div className="text-3xl font-bold text-white">1,830 FIBT</div>
          </div>
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Avg Win Rate</div>
            <div className="text-3xl font-bold text-success">70.6%</div>
          </div>
        </div>

        {/* NFT Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {MOCK_NFTS.map((nft) => (
            <div key={nft.id} className="glass rounded-xl overflow-hidden card-hover">
              {/* NFT Image */}
              <div className="relative h-64 bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center">
                <FiImage className="text-6xl text-gray-700" />
                <div className="absolute top-4 right-4">
                  <div
                    className={`px-3 py-1 bg-gradient-to-r ${
                      TIER_COLORS[nft.tier as keyof typeof TIER_COLORS]
                    } rounded-full text-white text-sm font-semibold`}
                  >
                    {TIER_NAMES[nft.tier]}
                  </div>
                </div>
              </div>

              {/* NFT Info */}
              <div className="p-6">
                <h3 className="text-xl font-bold text-white mb-2">{nft.name}</h3>
                <div className="text-sm text-gray-400 mb-4">Minted {nft.mintedAt}</div>

                {/* Performance Stats */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-700">
                  <div>
                    <div className="text-gray-400 text-xs mb-1">Signals</div>
                    <div className="text-white font-semibold">
                      {nft.performance.totalSignals}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400 text-xs mb-1">Win Rate</div>
                    <div className="text-success font-semibold">
                      {nft.performance.winRate}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400 text-xs mb-1">Volume</div>
                    <div className="text-white font-semibold">
                      {nft.performance.volume}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex space-x-2 mt-4">
                  <button className="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold transition">
                    View Details
                  </button>
                  <button className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-semibold transition">
                    Transfer
                  </button>
                </div>
              </div>
            </div>
          ))}

          {/* Mint New NFT Card */}
          <div className="glass rounded-xl overflow-hidden flex items-center justify-center min-h-[400px] border-2 border-dashed border-gray-700 hover:border-primary-600 transition cursor-pointer">
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-primary-600/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <FiImage className="text-3xl text-primary-500" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Mint New Strategy NFT</h3>
              <p className="text-gray-400 text-sm mb-4">
                Create a new strategy NFT to start earning
              </p>
              <button className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition">
                Get Started
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
