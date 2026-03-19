"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

interface Payment {
  id: string;
  user_id: string;
  user_email: string | null;
  amount: number;
  currency: string;
  status: string;
  provider_reference: string | null;
  created_at: string;
  paid_at: string | null;
}

export default function PaymentsManagement() {
  const router = useRouter();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    loadPayments();
  }, [page, statusFilter]);

  const loadPayments = async () => {
    setLoading(true);
    try {
      const params: any = {
        skip: (page - 1) * limit,
        limit: limit,
      };
      if (statusFilter) params.status_filter = statusFilter;

      const response = await api.get("/admin/payments", { params });
      setPayments(response.data.payments);
      setTotal(response.data.total);
    } catch (error: any) {
      if (error.response?.status === 403) {
        alert("Admin access required");
        router.push("/dashboard");
      }
      console.error("Failed to load payments:", error);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "paid":
        return "bg-green-500/20 text-green-300 border-green-500/30";
      case "pending":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
      case "failed":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      case "cancelled":
        return "bg-gray-500/20 text-gray-300 border-gray-500/30";
      default:
        return "bg-blue-500/20 text-blue-300 border-blue-500/30";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">
                <i className="fas fa-credit-card text-green-400 mr-3"></i>
                Payments Management
              </h1>
              <p className="text-purple-200">Total: {total} payments</p>
            </div>
            <Link
              href="/dashboard/admin"
              className="bg-white/10 hover:bg-white/20 text-white px-6 py-3 rounded-lg transition-colors border border-white/20"
            >
              <i className="fas fa-arrow-left mr-2"></i>
              Back to Dashboard
            </Link>
          </div>
        </motion.div>

        {/* Filters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-6"
        >
          <div className="flex space-x-2">
            <button
              onClick={() => {
                setStatusFilter("");
                setPage(1);
              }}
              className={`px-4 py-2 rounded-lg transition-colors ${
                statusFilter === ""
                  ? "bg-purple-500 text-white"
                  : "bg-white/10 text-purple-200 hover:bg-white/20"
              }`}
            >
              All
            </button>
            <button
              onClick={() => {
                setStatusFilter("paid");
                setPage(1);
              }}
              className={`px-4 py-2 rounded-lg transition-colors ${
                statusFilter === "paid"
                  ? "bg-green-500 text-white"
                  : "bg-white/10 text-purple-200 hover:bg-white/20"
              }`}
            >
              <i className="fas fa-check-circle mr-2"></i>
              Paid
            </button>
            <button
              onClick={() => {
                setStatusFilter("pending");
                setPage(1);
              }}
              className={`px-4 py-2 rounded-lg transition-colors ${
                statusFilter === "pending"
                  ? "bg-yellow-500 text-white"
                  : "bg-white/10 text-purple-200 hover:bg-white/20"
              }`}
            >
              <i className="fas fa-clock mr-2"></i>
              Pending
            </button>
            <button
              onClick={() => {
                setStatusFilter("failed");
                setPage(1);
              }}
              className={`px-4 py-2 rounded-lg transition-colors ${
                statusFilter === "failed"
                  ? "bg-red-500 text-white"
                  : "bg-white/10 text-purple-200 hover:bg-white/20"
              }`}
            >
              <i className="fas fa-times-circle mr-2"></i>
              Failed
            </button>
          </div>
        </motion.div>

        {/* Payments Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white/10 backdrop-blur-lg rounded-xl border border-white/20 overflow-hidden"
        >
          {loading ? (
            <div className="p-12 text-center text-white">
              <i className="fas fa-spinner fa-spin text-3xl mb-4"></i>
              <p>Loading payments...</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-green-500/20 border-b border-green-400/30">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        Payment ID
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        User
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        Amount
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        Provider Ref
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        Created
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-green-200 uppercase tracking-wider">
                        Paid
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10">
                    {payments.map((payment) => (
                      <tr key={payment.id} className="hover:bg-white/5 transition-colors">
                        <td className="px-6 py-4 text-sm font-mono text-purple-200">
                          {payment.id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm text-white">
                          {payment.user_email || payment.user_id.substring(0, 8) + "..."}
                        </td>
                        <td className="px-6 py-4 text-sm font-bold text-green-400">
                          ${payment.amount.toFixed(2)} {payment.currency}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(
                              payment.status
                            )}`}
                          >
                            {payment.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm font-mono text-purple-200">
                          {payment.provider_reference || "-"}
                        </td>
                        <td className="px-6 py-4 text-sm text-purple-200">
                          {new Date(payment.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 text-sm text-purple-200">
                          {payment.paid_at
                            ? new Date(payment.paid_at).toLocaleString()
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="bg-green-500/10 px-6 py-4 border-t border-green-400/30">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-green-200">
                      Page {page} of {totalPages}
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setPage(Math.max(1, page - 1))}
                        disabled={page === 1}
                        className="px-4 py-2 bg-white/10 text-white rounded hover:bg-white/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <i className="fas fa-chevron-left"></i>
                      </button>
                      <button
                        onClick={() => setPage(Math.min(totalPages, page + 1))}
                        disabled={page === totalPages}
                        className="px-4 py-2 bg-white/10 text-white rounded hover:bg-white/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <i className="fas fa-chevron-right"></i>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}
