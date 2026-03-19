'use client';

import Link from 'next/link';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import { NotificationBell } from './NotificationBell';
import { useNotificationSimulator } from '@/providers/NotificationProvider';
import { FiMenu, FiX } from 'react-icons/fi';
import { useState } from 'react';

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  // Enable notification simulator in development
  useNotificationSimulator();

  const navLinks = [
    { href: '/marketplace', label: 'Marketplace' },
    { href: '/staking', label: 'Staking' },
    { href: '/governance', label: 'Governance' },
    { href: '/nfts', label: 'NFTs' },
    { href: '/analytics', label: 'Analytics' },
    { href: '/profile', label: 'Profile' },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <div className="text-2xl font-bold text-white gradient-text">Fibtool</div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-gray-300 hover:text-white transition"
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Right Side */}
          <div className="flex items-center space-x-4">
            <NotificationBell />
            <ConnectButton />
            
            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-gray-300 hover:text-white"
            >
              {mobileMenuOpen ? <FiX className="text-2xl" /> : <FiMenu className="text-2xl" />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-2 text-gray-300 hover:text-white hover:bg-gray-800 rounded transition"
              >
                {link.label}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* PWA Install Banner */}
      <div
        id="pwa-install-banner"
        className="hidden bg-primary-600 text-white px-4 py-3 text-center"
      >
        <p className="text-sm">
          Install Fibtool app for faster access and offline support
          <button
            id="pwa-install-btn"
            className="ml-4 px-4 py-1 bg-white text-primary-600 rounded hover:bg-gray-100 transition"
          >
            Install
          </button>
        </p>
      </div>
    </nav>
  );
}
