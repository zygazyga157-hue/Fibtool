import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { formatUnits, parseUnits } from 'viem';

/**
 * Merge Tailwind CSS classes
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format token amount to human-readable string
 */
export function formatTokenAmount(
  amount: bigint | string | number,
  decimals: number = 18,
  maxDecimals: number = 4
): string {
  const formatted = formatUnits(BigInt(amount), decimals);
  const num = parseFloat(formatted);
  
  if (num === 0) return '0';
  if (num < 0.0001) return '< 0.0001';
  
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDecimals,
  });
}

/**
 * Parse token amount from human-readable string
 */
export function parseTokenAmount(amount: string, decimals: number = 18): bigint {
  try {
    return parseUnits(amount, decimals);
  } catch {
    return BigInt(0);
  }
}

/**
 * Shorten wallet address
 */
export function shortenAddress(address: string, chars: number = 4): string {
  if (!address) return '';
  return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`;
}

/**
 * Format USD amount
 */
export function formatUSD(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format percentage
 */
export function formatPercent(value: number, decimals: number = 2): string {
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format date
 */
export function formatDate(timestamp: number | bigint): string {
  const date = new Date(Number(timestamp) * 1000);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

/**
 * Format relative time
 */
export function formatRelativeTime(timestamp: number | bigint): string {
  const date = new Date(Number(timestamp) * 1000);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return 'just now';
}

/**
 * Calculate win rate
 */
export function calculateWinRate(wins: number, total: number): number {
  if (total === 0) return 0;
  return (wins / total) * 100;
}

/**
 * Calculate APY
 */
export function calculateAPY(
  principal: bigint,
  rewards: bigint,
  durationSeconds: bigint
): number {
  if (principal === BigInt(0) || durationSeconds === BigInt(0)) return 0;
  
  const rewardsNum = Number(formatUnits(rewards, 18));
  const principalNum = Number(formatUnits(principal, 18));
  const durationYears = Number(durationSeconds) / (365 * 24 * 60 * 60);
  
  return (rewardsNum / principalNum / durationYears) * 100;
}

/**
 * Get VIP tier name
 */
export function getVIPTierName(tier: number): string {
  const tiers = ['VIP 0', 'VIP 1', 'VIP 2', 'VIP 3', 'VIP 4', 'VIP 5'];
  return tiers[tier] || 'Unknown';
}

/**
 * Get VIP tier discount
 */
export function getVIPTierDiscount(tier: number): number {
  const discounts = [0, 10, 20, 40, 60, 80];
  return discounts[tier] || 0;
}

/**
 * Get strategy category name
 */
export function getStrategyCategoryName(category: number): string {
  const categories = [
    'Fibonacci',
    'Gann',
    'Harmonic',
    'Elliott Wave',
    'Price Action',
    'Other',
  ];
  return categories[category] || 'Unknown';
}

/**
 * Get proposal status name
 */
export function getProposalStatusName(status: number): string {
  const statuses = [
    'Pending',
    'Active',
    'Canceled',
    'Defeated',
    'Succeeded',
    'Queued',
    'Expired',
    'Executed',
  ];
  return statuses[status] || 'Unknown';
}

/**
 * Copy to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Generate random color for charts
 */
export function generateColor(index: number): string {
  const colors = [
    '#0ea5e9', // primary
    '#f59e0b', // accent
    '#10b981', // success
    '#ef4444', // error
    '#8b5cf6', // purple
    '#ec4899', // pink
  ];
  return colors[index % colors.length];
}

/**
 * Validate Ethereum address
 */
export function isValidAddress(address: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test(address);
}

/**
 * Sleep utility
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
