'use client';

import { useState } from 'react';
import { useAccount, useReadContract, useWriteContract } from 'wagmi';
import { FiCheck, FiX, FiClock, FiTrendingUp } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { CONTRACTS, GOVERNANCE_DAO_ABI } from '@/contracts/abis';
import { formatRelativeTime, getProposalStatusName } from '@/utils/helpers';

interface Proposal {
  id: number;
  title: string;
  description: string;
  category: number;
  proposer: string;
  forVotes: bigint;
  againstVotes: bigint;
  abstainVotes: bigint;
  status: number;
  createdAt: number;
  deadline: number;
}

const MOCK_PROPOSALS: Proposal[] = [
  {
    id: 1,
    title: 'Reduce Platform Fees by 25%',
    description: 'Proposal to reduce platform fees from 20% to 15% to increase competitiveness',
    category: 0,
    proposer: '0x1234...5678',
    forVotes: BigInt('500000000000000000000000'),
    againstVotes: BigInt('150000000000000000000000'),
    abstainVotes: BigInt('50000000000000000000000'),
    status: 1,
    createdAt: Date.now() / 1000 - 86400 * 3,
    deadline: Date.now() / 1000 + 86400 * 4,
  },
  {
    id: 2,
    title: 'Add Support for MT4 Integration',
    description: 'Extend oracle support to include MetaTrader 4 alongside MT5',
    category: 5,
    proposer: '0xabcd...efgh',
    forVotes: BigInt('300000000000000000000000'),
    againstVotes: BigInt('100000000000000000000000'),
    abstainVotes: BigInt('25000000000000000000000'),
    status: 1,
    createdAt: Date.now() / 1000 - 86400 * 2,
    deadline: Date.now() / 1000 + 86400 * 5,
  },
];

const CATEGORIES = [
  'Fee Changes',
  'Treasury Spending',
  'Smart Contract Upgrades',
  'Strategy Delisting',
  'Emergency Actions',
  'Parameters',
];

export default function GovernancePage() {
  const { address, isConnected } = useAccount();
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { writeContract } = useWriteContract();

  const castVote = async (proposalId: number, support: number) => {
    try {
      writeContract({
        address: CONTRACTS.GOVERNANCE_DAO,
        abi: GOVERNANCE_DAO_ABI,
        functionName: 'castVote',
        args: [BigInt(proposalId), support],
      });

      toast.success('Vote cast successfully!');
    } catch (error: any) {
      toast.error(error.message || 'Failed to cast vote');
    }
  };

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 pt-24 px-4 pb-20">
        <div className="max-w-7xl mx-auto text-center py-20">
          <div className="glass rounded-xl p-12 max-w-md mx-auto">
            <h3 className="text-2xl font-bold text-white mb-4">Connect Your Wallet</h3>
            <p className="text-gray-400 mb-6">
              Connect your wallet to participate in governance
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
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Governance</h1>
            <p className="text-gray-400">Shape the future of Fibtool through on-chain voting</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition"
          >
            Create Proposal
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Total Proposals</div>
            <div className="text-3xl font-bold text-white">24</div>
          </div>
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Active Votes</div>
            <div className="text-3xl font-bold text-primary-500">2</div>
          </div>
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Your Voting Power</div>
            <div className="text-3xl font-bold text-white">0 FIBT</div>
          </div>
          <div className="glass rounded-xl p-6">
            <div className="text-gray-400 text-sm mb-2">Quorum Required</div>
            <div className="text-3xl font-bold text-white">10%</div>
          </div>
        </div>

        {/* Proposals List */}
        <div className="space-y-6">
          {MOCK_PROPOSALS.map((proposal) => {
            const totalVotes = proposal.forVotes + proposal.againstVotes + proposal.abstainVotes;
            const forPercentage = totalVotes > 0
              ? Number((proposal.forVotes * BigInt(100)) / totalVotes)
              : 0;
            const againstPercentage = totalVotes > 0
              ? Number((proposal.againstVotes * BigInt(100)) / totalVotes)
              : 0;

            return (
              <div key={proposal.id} className="glass rounded-xl p-6">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="text-xl font-bold text-white">{proposal.title}</h3>
                      <span className="px-3 py-1 bg-primary-600/20 text-primary-500 rounded-full text-sm">
                        {CATEGORIES[proposal.category]}
                      </span>
                      <span className="px-3 py-1 bg-success/20 text-success rounded-full text-sm">
                        {getProposalStatusName(proposal.status)}
                      </span>
                    </div>
                    <p className="text-gray-400 mb-4">{proposal.description}</p>
                    <div className="flex items-center space-x-6 text-sm text-gray-400">
                      <div className="flex items-center space-x-2">
                        <FiClock />
                        <span>Ends {formatRelativeTime(proposal.deadline)}</span>
                      </div>
                      <div>Proposer: {proposal.proposer}</div>
                    </div>
                  </div>
                </div>

                {/* Vote Results */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-400">Voting Results</span>
                    <span className="text-gray-400">
                      {(Number(totalVotes) / 1e18).toLocaleString()} FIBT
                    </span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden flex">
                    <div
                      className="bg-success"
                      style={{ width: `${forPercentage}%` }}
                    />
                    <div
                      className="bg-error"
                      style={{ width: `${againstPercentage}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-sm mt-2">
                    <span className="text-success">For: {forPercentage}%</span>
                    <span className="text-error">Against: {againstPercentage}%</span>
                  </div>
                </div>

                {/* Vote Buttons */}
                {proposal.status === 1 && (
                  <div className="flex space-x-4">
                    <button
                      onClick={() => castVote(proposal.id, 1)}
                      className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-success hover:bg-green-600 text-white rounded-lg font-semibold transition"
                    >
                      <FiCheck />
                      <span>Vote For</span>
                    </button>
                    <button
                      onClick={() => castVote(proposal.id, 0)}
                      className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-error hover:bg-red-600 text-white rounded-lg font-semibold transition"
                    >
                      <FiX />
                      <span>Vote Against</span>
                    </button>
                    <button
                      onClick={() => castVote(proposal.id, 2)}
                      className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold transition"
                    >
                      Abstain
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Create Proposal Modal */}
      {showCreateModal && (
        <CreateProposalModal onClose={() => setShowCreateModal(false)} />
      )}
    </div>
  );
}

function CreateProposalModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState(0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
      <div className="glass rounded-xl p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold text-white mb-6">Create Proposal</h2>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-primary-500"
              placeholder="Proposal title..."
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(parseInt(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-primary-500"
            >
              {CATEGORIES.map((cat, idx) => (
                <option key={idx} value={idx}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-primary-500"
              placeholder="Detailed description of your proposal..."
            />
          </div>
        </div>

        <div className="flex space-x-4">
          <button
            onClick={onClose}
            className="flex-1 px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold transition"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              toast.success('Proposal creation submitted!');
              onClose();
            }}
            className="flex-1 px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-semibold transition"
          >
            Create Proposal
          </button>
        </div>
      </div>
    </div>
  );
}
