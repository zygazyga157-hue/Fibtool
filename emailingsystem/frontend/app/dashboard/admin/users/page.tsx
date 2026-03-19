"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  payment_count: number;
  subscription_count: number;
}

export default function UsersManagement() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    loadUsers();
  }, [page, search]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const params: any = {
        skip: (page - 1) * limit,
        limit: limit,
      };
      if (search) params.search = search;

      const response = await api.get("/admin/users", { params });
      setUsers(response.data.users);
      setTotal(response.data.total);
    } catch (error: any) {
      if (error.response?.status === 403) {
        alert("Admin access required");
        router.push("/dashboard");
      }
      console.error("Failed to load users:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleUserStatus = async (userId: string, currentStatus: boolean) => {
    if (!confirm(`Are you sure you want to ${currentStatus ? "deactivate" : "activate"} this user?`)) {
      return;
    }

    try {
      await api.patch(`/admin/users/${userId}`, { is_active: !currentStatus });
      await loadUsers();
    } catch (error) {
      console.error("Failed to update user:", error);
      alert("Failed to update user status");
    }
  };

  const toggleAdminStatus = async (userId: string, currentStatus: boolean) => {
    if (!confirm(`Are you sure you want to ${currentStatus ? "revoke admin from" : "grant admin to"} this user?`)) {
      return;
    }

    try {
      await api.patch(`/admin/users/${userId}`, { is_admin: !currentStatus });
      await loadUsers();
    } catch (error) {
      console.error("Failed to update user:", error);
      alert("Failed to update admin status");
    }
  };

  const totalPages = Math.ceil(total / limit);

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
                <i className="fas fa-users text-blue-400 mr-3"></i>
                Users Management
              </h1>
              <p className="text-purple-200">
                Total: {total} users
              </p>
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

        {/* Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-6"
        >
          <div className="relative">
            <i className="fas fa-search absolute left-4 top-1/2 transform -translate-y-1/2 text-purple-300"></i>
            <input
              type="text"
              placeholder="Search by email or name..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-12 pr-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
        </motion.div>

        {/* Users Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white/10 backdrop-blur-lg rounded-xl border border-white/20 overflow-hidden"
        >
          {loading ? (
            <div className="p-12 text-center text-white">
              <i className="fas fa-spinner fa-spin text-3xl mb-4"></i>
              <p>Loading users...</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-purple-500/20 border-b border-purple-400/30">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-medium text-purple-200 uppercase tracking-wider">
                        User
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-purple-200 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-purple-200 uppercase tracking-wider">
                        Stats
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-purple-200 uppercase tracking-wider">
                        Joined
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-purple-200 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10">
                    {users.map((user) => (
                      <tr key={user.id} className="hover:bg-white/5 transition-colors">
                        <td className="px-6 py-4">
                          <div>
                            <div className="text-white font-semibold flex items-center">
                              {user.name}
                              {user.is_admin && (
                                <span className="ml-2 px-2 py-0.5 bg-yellow-500/20 text-yellow-300 text-xs rounded border border-yellow-500/30">
                                  <i className="fas fa-crown mr-1"></i>
                                  ADMIN
                                </span>
                              )}
                            </div>
                            <div className="text-sm text-purple-300">{user.email}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-semibold ${
                              user.is_active
                                ? "bg-green-500/20 text-green-300 border border-green-500/30"
                                : "bg-red-500/20 text-red-300 border border-red-500/30"
                            }`}
                          >
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-purple-200">
                          <div className="space-y-1">
                            <div>
                              <i className="fas fa-credit-card mr-2"></i>
                              {user.payment_count} payments
                            </div>
                            <div>
                              <i className="fas fa-star mr-2"></i>
                              {user.subscription_count} active subs
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-purple-200">
                          {new Date(user.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex space-x-2">
                            <button
                              onClick={() => router.push(`/dashboard/admin/users/${user.id}`)}
                              className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1.5 rounded text-sm transition-colors"
                              title="View Details"
                            >
                              <i className="fas fa-eye"></i>
                            </button>
                            <button
                              onClick={() => toggleUserStatus(user.id, user.is_active)}
                              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                                user.is_active
                                  ? "bg-red-500 hover:bg-red-600"
                                  : "bg-green-500 hover:bg-green-600"
                              } text-white`}
                              title={user.is_active ? "Deactivate" : "Activate"}
                            >
                              <i className={`fas fa-${user.is_active ? "ban" : "check"}`}></i>
                            </button>
                            <button
                              onClick={() => toggleAdminStatus(user.id, user.is_admin)}
                              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                                user.is_admin
                                  ? "bg-yellow-600 hover:bg-yellow-700"
                                  : "bg-yellow-500 hover:bg-yellow-600"
                              } text-white`}
                              title={user.is_admin ? "Revoke Admin" : "Grant Admin"}
                            >
                              <i className="fas fa-crown"></i>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="bg-purple-500/10 px-6 py-4 border-t border-purple-400/30">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-purple-200">
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
