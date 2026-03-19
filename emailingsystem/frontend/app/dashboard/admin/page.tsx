"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

interface DashboardStats {
  users: {
    total: number;
    active: number;
    new_today: number;
    new_this_week: number;
  };
  payments: {
    total: number;
    paid: number;
    pending: number;
    failed: number;
    success_rate: string;
  };
  revenue: {
    total: number;
    today: number;
    this_week: number;
    this_month: number;
    currency: string;
  };
  subscriptions: {
    total: number;
    active: number;
    inactive: number;
  };
  deliveries: {
    total: number;
    pending: number;
    processing: number;
    sent: number;
    failed: number;
    success_rate: string;
  };
  plans: Array<{
    name: string;
    purchases: number;
    revenue: number;
  }>;
  recent_activity: {
    payments: Array<{
      id: string;
      amount: number;
      status: string;
      user_id: string;
      created_at: string;
    }>;
    deliveries: Array<{
      id: string;
      symbol: string;
      status: string;
      user_id: string;
      created_at: string;
    }>;
  };
}

interface Delivery {
  id: string;
  payment_id: string;
  user_id: string;
  user_email: string | null;
  symbol: string;
  status: string;
  error_message: string | null;
  created_at: string;
}

export default function AdminDashboard() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [failedDeliveries, setFailedDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [statsData, failedData] = await Promise.all([
        api.get("/admin/dashboard"),
        api.get("/admin/deliveries/failed?limit=10"),
      ]);
      
      setStats(statsData.data);
      setFailedDeliveries(failedData.data.deliveries || []);
    } catch (error: any) {
      if (error.response?.status === 403) {
        alert("Admin access required");
        router.push("/dashboard");
      } else {
        console.error("Failed to load admin dashboard:", error);
        alert("Failed to load admin dashboard. Check console for details.");
      }
    } finally {
      setLoading(false);
    }
  };

  const retryDelivery = async (deliveryId: string) => {
    setRetrying(deliveryId);
    try {
      await api.post(`/admin/deliveries/${deliveryId}/retry`);
      alert("Delivery retry triggered successfully");
      await loadDashboard();
    } catch (error) {
      console.error("Failed to retry delivery:", error);
      alert("Failed to retry delivery");
    } finally {
      setRetrying(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-white text-xl">
          <i className="fas fa-spinner fa-spin mr-2"></i>
          Loading admin dashboard...
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

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
                <i className="fas fa-crown text-yellow-400 mr-3"></i>
                Admin Dashboard
              </h1>
              <p className="text-purple-200">
                System monitoring and management
              </p>
            </div>
            <div className="flex space-x-3">
              <Link
                href="/dashboard"
                className="bg-white/10 hover:bg-white/20 text-white px-6 py-3 rounded-lg transition-colors border border-white/20"
              >
                <i className="fas fa-arrow-left mr-2"></i>
                User Dashboard
              </Link>
            </div>
          </div>
        </motion.div>

        {/* Quick Links */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-8"
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              href="/dashboard/admin/users"
              className="bg-gradient-to-br from-blue-500/20 to-blue-600/20 backdrop-blur-lg rounded-xl p-6 border border-blue-400/30 hover:border-blue-400/50 transition-all group"
            >
              <div className="flex items-center justify-between">
                <div>
                  <i className="fas fa-users text-3xl text-blue-400 mb-2"></i>
                  <div className="text-white font-bold text-lg">Users Management</div>
                  <div className="text-blue-200 text-sm">View and manage all users</div>
                </div>
                <i className="fas fa-arrow-right text-blue-400 text-xl opacity-0 group-hover:opacity-100 transition-opacity"></i>
              </div>
            </Link>

            <Link
              href="/dashboard/admin/payments"
              className="bg-gradient-to-br from-green-500/20 to-green-600/20 backdrop-blur-lg rounded-xl p-6 border border-green-400/30 hover:border-green-400/50 transition-all group"
            >
              <div className="flex items-center justify-between">
                <div>
                  <i className="fas fa-credit-card text-3xl text-green-400 mb-2"></i>
                  <div className="text-white font-bold text-lg">Payments Overview</div>
                  <div className="text-green-200 text-sm">Monitor all transactions</div>
                </div>
                <i className="fas fa-arrow-right text-green-400 text-xl opacity-0 group-hover:opacity-100 transition-opacity"></i>
              </div>
            </Link>

            <button
              onClick={() => loadDashboard()}
              className="bg-gradient-to-br from-purple-500/20 to-purple-600/20 backdrop-blur-lg rounded-xl p-6 border border-purple-400/30 hover:border-purple-400/50 transition-all group text-left"
            >
              <div className="flex items-center justify-between">
                <div>
                  <i className="fas fa-sync text-3xl text-purple-400 mb-2"></i>
                  <div className="text-white font-bold text-lg">Refresh Data</div>
                  <div className="text-purple-200 text-sm">Reload dashboard stats</div>
                </div>
                <i className="fas fa-redo text-purple-400 text-xl opacity-0 group-hover:opacity-100 transition-opacity"></i>
              </div>
            </button>
          </div>
        </motion.div>

        {/* Revenue Overview */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8"
        >
          <h2 className="text-2xl font-bold text-white mb-4">
            <i className="fas fa-dollar-sign text-green-400 mr-2"></i>
            Revenue Overview
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
              <div className="text-purple-300 text-sm mb-1">Total Revenue</div>
              <div className="text-3xl font-bold text-white">
                ${stats.revenue.total.toFixed(2)}
              </div>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
              <div className="text-purple-300 text-sm mb-1">Today</div>
              <div className="text-3xl font-bold text-green-400">
                ${stats.revenue.today.toFixed(2)}
              </div>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
              <div className="text-purple-300 text-sm mb-1">This Week</div>
              <div className="text-3xl font-bold text-blue-400">
                ${stats.revenue.this_week.toFixed(2)}
              </div>
            </div>
            <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
              <div className="text-purple-300 text-sm mb-1">This Month</div>
              <div className="text-3xl font-bold text-purple-400">
                ${stats.revenue.this_month.toFixed(2)}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Key Metrics */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8"
        >
          <h2 className="text-2xl font-bold text-white mb-4">
            <i className="fas fa-chart-line text-blue-400 mr-2"></i>
            Key Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Users */}
            <div className="bg-gradient-to-br from-blue-500/20 to-blue-600/20 backdrop-blur-lg rounded-xl p-6 border border-blue-400/30">
              <div className="flex items-center justify-between mb-4">
                <i className="fas fa-users text-3xl text-blue-400"></i>
                <div className="text-right">
                  <div className="text-sm text-blue-200">Total Users</div>
                  <div className="text-2xl font-bold text-white">
                    {stats.users.total}
                  </div>
                </div>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between text-blue-200">
                  <span>Active:</span>
                  <span className="font-semibold">{stats.users.active}</span>
                </div>
                <div className="flex justify-between text-blue-200">
                  <span>New Today:</span>
                  <span className="font-semibold">{stats.users.new_today}</span>
                </div>
                <div className="flex justify-between text-blue-200">
                  <span>New This Week:</span>
                  <span className="font-semibold">{stats.users.new_this_week}</span>
                </div>
              </div>
            </div>

            {/* Payments */}
            <div className="bg-gradient-to-br from-green-500/20 to-green-600/20 backdrop-blur-lg rounded-xl p-6 border border-green-400/30">
              <div className="flex items-center justify-between mb-4">
                <i className="fas fa-credit-card text-3xl text-green-400"></i>
                <div className="text-right">
                  <div className="text-sm text-green-200">Total Payments</div>
                  <div className="text-2xl font-bold text-white">
                    {stats.payments.total}
                  </div>
                </div>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between text-green-200">
                  <span>Paid:</span>
                  <span className="font-semibold text-green-300">{stats.payments.paid}</span>
                </div>
                <div className="flex justify-between text-green-200">
                  <span>Pending:</span>
                  <span className="font-semibold text-yellow-300">{stats.payments.pending}</span>
                </div>
                <div className="flex justify-between text-green-200">
                  <span>Success Rate:</span>
                  <span className="font-semibold">{stats.payments.success_rate}</span>
                </div>
              </div>
            </div>

            {/* Subscriptions */}
            <div className="bg-gradient-to-br from-purple-500/20 to-purple-600/20 backdrop-blur-lg rounded-xl p-6 border border-purple-400/30">
              <div className="flex items-center justify-between mb-4">
                <i className="fas fa-star text-3xl text-purple-400"></i>
                <div className="text-right">
                  <div className="text-sm text-purple-200">Subscriptions</div>
                  <div className="text-2xl font-bold text-white">
                    {stats.subscriptions.total}
                  </div>
                </div>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between text-purple-200">
                  <span>Active:</span>
                  <span className="font-semibold text-green-300">{stats.subscriptions.active}</span>
                </div>
                <div className="flex justify-between text-purple-200">
                  <span>Inactive:</span>
                  <span className="font-semibold text-gray-300">{stats.subscriptions.inactive}</span>
                </div>
              </div>
            </div>

            {/* Deliveries */}
            <div className="bg-gradient-to-br from-orange-500/20 to-orange-600/20 backdrop-blur-lg rounded-xl p-6 border border-orange-400/30">
              <div className="flex items-center justify-between mb-4">
                <i className="fas fa-paper-plane text-3xl text-orange-400"></i>
                <div className="text-right">
                  <div className="text-sm text-orange-200">Deliveries</div>
                  <div className="text-2xl font-bold text-white">
                    {stats.deliveries.total}
                  </div>
                </div>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between text-orange-200">
                  <span>Sent:</span>
                  <span className="font-semibold text-green-300">{stats.deliveries.sent}</span>
                </div>
                <div className="flex justify-between text-orange-200">
                  <span>Failed:</span>
                  <span className="font-semibold text-red-300">{stats.deliveries.failed}</span>
                </div>
                <div className="flex justify-between text-orange-200">
                  <span>Success Rate:</span>
                  <span className="font-semibold">{stats.deliveries.success_rate}</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Plans Performance */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mb-8"
        >
          <h2 className="text-2xl font-bold text-white mb-4">
            <i className="fas fa-chart-pie text-purple-400 mr-2"></i>
            Plans Performance
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {stats.plans.map((plan, index) => (
              <div
                key={index}
                className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20"
              >
                <div className="text-xl font-bold text-white mb-2">
                  {plan.name}
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-purple-200">
                    <span>Purchases:</span>
                    <span className="font-semibold text-white">{plan.purchases}</span>
                  </div>
                  <div className="flex justify-between text-purple-200">
                    <span>Revenue:</span>
                    <span className="font-semibold text-green-400">
                      ${plan.revenue.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Failed Deliveries */}
        {failedDeliveries.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mb-8"
          >
            <h2 className="text-2xl font-bold text-white mb-4">
              <i className="fas fa-exclamation-triangle text-red-400 mr-2"></i>
              Failed Deliveries
              <span className="ml-2 text-sm font-normal text-red-300">
                ({failedDeliveries.length} failed)
              </span>
            </h2>
            <div className="bg-white/10 backdrop-blur-lg rounded-xl border border-red-400/30 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-red-500/20 border-b border-red-400/30">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-red-200 uppercase tracking-wider">
                        User
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-red-200 uppercase tracking-wider">
                        Symbol
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-red-200 uppercase tracking-wider">
                        Error
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-red-200 uppercase tracking-wider">
                        Created
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-red-200 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10">
                    {failedDeliveries.map((delivery) => (
                      <tr key={delivery.id} className="hover:bg-white/5 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                          {delivery.user_email || delivery.user_id}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-white font-mono">
                          {delivery.symbol}
                        </td>
                        <td className="px-6 py-4 text-sm text-red-300 max-w-xs truncate">
                          {delivery.error_message || "Unknown error"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-purple-200">
                          {new Date(delivery.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <button
                            onClick={() => retryDelivery(delivery.id)}
                            disabled={retrying === delivery.id}
                            className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {retrying === delivery.id ? (
                              <>
                                <i className="fas fa-spinner fa-spin mr-2"></i>
                                Retrying...
                              </>
                            ) : (
                              <>
                                <i className="fas fa-redo mr-2"></i>
                                Retry
                              </>
                            )}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )}

        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          {/* Recent Payments */}
          <div>
            <h2 className="text-2xl font-bold text-white mb-4">
              <i className="fas fa-history text-green-400 mr-2"></i>
              Recent Payments
            </h2>
            <div className="bg-white/10 backdrop-blur-lg rounded-xl border border-white/20 p-6">
              <div className="space-y-3">
                {stats.recent_activity.payments.map((payment) => (
                  <div
                    key={payment.id}
                    className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                  >
                    <div>
                      <div className="text-white font-semibold">
                        ${payment.amount.toFixed(2)}
                      </div>
                      <div className="text-sm text-purple-300">
                        {new Date(payment.created_at).toLocaleString()}
                      </div>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold ${
                        payment.status === "paid"
                          ? "bg-green-500/20 text-green-300 border border-green-500/30"
                          : payment.status === "pending"
                          ? "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
                          : "bg-red-500/20 text-red-300 border border-red-500/30"
                      }`}
                    >
                      {payment.status.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent Deliveries */}
          <div>
            <h2 className="text-2xl font-bold text-white mb-4">
              <i className="fas fa-history text-orange-400 mr-2"></i>
              Recent Deliveries
            </h2>
            <div className="bg-white/10 backdrop-blur-lg rounded-xl border border-white/20 p-6">
              <div className="space-y-3">
                {stats.recent_activity.deliveries.map((delivery) => (
                  <div
                    key={delivery.id}
                    className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                  >
                    <div>
                      <div className="text-white font-semibold font-mono">
                        {delivery.symbol}
                      </div>
                      <div className="text-sm text-purple-300">
                        {new Date(delivery.created_at).toLocaleString()}
                      </div>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold ${
                        delivery.status === "sent"
                          ? "bg-green-500/20 text-green-300 border border-green-500/30"
                          : delivery.status === "processing"
                          ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                          : delivery.status === "failed"
                          ? "bg-red-500/20 text-red-300 border border-red-500/30"
                          : "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
                      }`}
                    >
                      {delivery.status.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
