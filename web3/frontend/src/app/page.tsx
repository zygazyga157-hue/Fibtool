'use client';

import { ConnectButton } from '@rainbow-me/rainbowkit';
import Link from 'next/link';
import { useAccount } from 'wagmi';
import { FiArrowRight, FiTrendingUp, FiShield, FiZap } from 'react-icons/fi';

export default function HomePage() {
  const { isConnected } = useAccount();

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 glass">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-accent-500 rounded-lg" />
              <span className="text-xl font-bold text-white">Fibtool</span>
            </Link>

            <div className="hidden md:flex items-center space-x-8">
              <Link href="/marketplace" className="text-gray-300 hover:text-white transition">
                Marketplace
              </Link>
              <Link href="/staking" className="text-gray-300 hover:text-white transition">
                Staking
              </Link>
              <Link href="/governance" className="text-gray-300 hover:text-white transition">
                Governance
              </Link>
              <Link href="/docs" className="text-gray-300 hover:text-white transition">
                Docs
              </Link>
            </div>

            <ConnectButton />
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-bold text-white mb-6">
            Trade with{' '}
            <span className="gradient-text">Confidence</span>
          </h1>
          <p className="text-xl text-gray-400 mb-8 max-w-2xl mx-auto">
            Decentralized trading signal marketplace. Verify performance on-chain.
            Pay only for profitable signals.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            {isConnected ? (
              <Link
                href="/marketplace"
                className="inline-flex items-center px-8 py-4 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition"
              >
                Browse Marketplace
                <FiArrowRight className="ml-2" />
              </Link>
            ) : (
              <ConnectButton.Custom>
                {({ openConnectModal }) => (
                  <button
                    onClick={openConnectModal}
                    className="inline-flex items-center px-8 py-4 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition"
                  >
                    Get Started
                    <FiArrowRight className="ml-2" />
                  </button>
                )}
              </ConnectButton.Custom>
            )}
            <Link
              href="/docs"
              className="inline-flex items-center px-8 py-4 bg-gray-800 hover:bg-gray-700 text-white rounded-lg font-semibold transition"
            >
              Learn More
            </Link>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-20">
            <div className="glass rounded-xl p-6">
              <div className="text-4xl font-bold text-primary-500 mb-2">$2.5M+</div>
              <div className="text-gray-400">Trading Volume</div>
            </div>
            <div className="glass rounded-xl p-6">
              <div className="text-4xl font-bold text-primary-500 mb-2">1,200+</div>
              <div className="text-gray-400">Active Strategies</div>
            </div>
            <div className="glass rounded-xl p-6">
              <div className="text-4xl font-bold text-primary-500 mb-2">72%</div>
              <div className="text-gray-400">Avg Win Rate</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-white text-center mb-16">
            Why Choose Fibtool?
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="glass rounded-xl p-8 card-hover">
              <div className="w-12 h-12 bg-primary-600 rounded-lg flex items-center justify-center mb-4">
                <FiShield className="text-2xl text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">
                Verified Performance
              </h3>
              <p className="text-gray-400">
                All trading results verified on-chain by decentralized oracles.
                No fake track records, no manipulation.
              </p>
            </div>

            <div className="glass rounded-xl p-8 card-hover">
              <div className="w-12 h-12 bg-accent-600 rounded-lg flex items-center justify-center mb-4">
                <FiTrendingUp className="text-2xl text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">
                Pay Per Performance
              </h3>
              <p className="text-gray-400">
                Only pay when signals hit take profit. Automatic refunds if stop loss hit.
                Completely trustless.
              </p>
            </div>

            <div className="glass rounded-xl p-8 card-hover">
              <div className="w-12 h-12 bg-success rounded-lg flex items-center justify-center mb-4">
                <FiZap className="text-2xl text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">
                Instant Settlement
              </h3>
              <p className="text-gray-400">
                Smart contract escrow ensures instant, automatic payouts.
                No waiting, no disputes.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto glass rounded-2xl p-12 text-center">
          <h2 className="text-4xl font-bold text-white mb-6">
            Ready to Start Trading?
          </h2>
          <p className="text-xl text-gray-400 mb-8">
            Join thousands of traders using Fibtool for verified trading signals
          </p>
          {isConnected ? (
            <Link
              href="/marketplace"
              className="inline-flex items-center px-8 py-4 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition"
            >
              Browse Strategies
              <FiArrowRight className="ml-2" />
            </Link>
          ) : (
            <ConnectButton.Custom>
              {({ openConnectModal }) => (
                <button
                  onClick={openConnectModal}
                  className="inline-flex items-center px-8 py-4 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition"
                >
                  Connect Wallet
                  <FiArrowRight className="ml-2" />
                </button>
              )}
            </ConnectButton.Custom>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-accent-500 rounded-lg" />
                <span className="text-xl font-bold text-white">Fibtool</span>
              </div>
              <p className="text-gray-400 text-sm">
                Decentralized trading signal marketplace built on Arbitrum
              </p>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-gray-400 text-sm">
                <li><Link href="/marketplace">Marketplace</Link></li>
                <li><Link href="/staking">Staking</Link></li>
                <li><Link href="/governance">Governance</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-gray-400 text-sm">
                <li><Link href="/docs">Documentation</Link></li>
                <li><Link href="/docs/api">API</Link></li>
                <li><Link href="/support">Support</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-gray-400 text-sm">
                <li><Link href="/legal/terms">Terms of Service</Link></li>
                <li><Link href="/legal/privacy">Privacy Policy</Link></li>
                <li><Link href="/legal/risk">Risk Disclosure</Link></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-gray-800 mt-12 pt-8 text-center text-gray-400 text-sm">
            © 2025 Fibtool. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
