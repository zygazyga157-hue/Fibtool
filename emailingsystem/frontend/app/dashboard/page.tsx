'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { 
  faChartLine, 
  faSignOutAlt, 
  faCreditCard, 
  faCheckCircle,
  faEnvelope,
  faClock,
  faSpinner,
  faUser,
  faDollarSign,
  faBox,
  faStar,
  faEdit
} from '@fortawesome/free-solid-svg-icons'
import { motion } from 'framer-motion'
import { dashboardAPI, paymentsAPI, plansAPI } from '@/lib/api'
import ReportsSection from '@/components/ReportsSection'

interface DashboardData {
  user: any
  payments: any[]
  subscriptions: any[]
  deliveries: any[]
}

interface SymbolPreference {
  id: number
  symbol_id: number
  symbol: string
  display_name: string
  description: string
  group_name: string
  group_display_name: string
  is_active: boolean
  created_at: string
}

interface SymbolGroup {
  [key: string]: SymbolPreference[]
}

export default function DashboardPage() {
  const router = useRouter()
  const [data, setData] = useState<DashboardData | null>(null)
  const [plans, setPlans] = useState<any[]>([])
  const [symbolPreferences, setSymbolPreferences] = useState<SymbolPreference[]>([])
  const [loading, setLoading] = useState(true)
  const [checkoutLoading, setCheckoutLoading] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/login')
      return
    }
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const token = localStorage.getItem('token')
      const [dashboardResponse, plansResponse, preferencesResponse] = await Promise.all([
        dashboardAPI.get(),
        plansAPI.getAll(),
        fetch('http://localhost:8000/api/v1/user/symbol-preferences', {
          headers: { Authorization: `Bearer ${token}` }
        }).then(res => res.json())
      ])
      setData(dashboardResponse.data)
      setPlans(plansResponse.data)
      setSymbolPreferences(preferencesResponse.preferences || [])
    } catch (error) {
      console.error('Failed to load dashboard:', error)
      localStorage.removeItem('token')
      router.push('/login')
    } finally {
      setLoading(false)
    }
  }

  const handleCheckout = async (planId: string) => {
    setCheckoutLoading(true)
    try {
      const response = await paymentsAPI.checkout({
        plan_id: planId,
        return_url: `${window.location.origin}/dashboard`,
      })
      
      alert(`Payment created! Payment ID: ${response.data.payment_id}\nIn production, you would be redirected to: ${response.data.payment_url}`)
      await loadData() // Reload data after purchase
    } catch (error: any) {
      alert('Checkout failed: ' + (error.response?.data?.detail || 'Unknown error'))
    } finally {
      setCheckoutLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    router.push('/')
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active': return 'bg-green-100 text-green-700'
      case 'completed': return 'bg-green-100 text-green-700'
      case 'pending': return 'bg-yellow-100 text-yellow-700'
      case 'processing': return 'bg-blue-100 text-blue-700'
      case 'failed': return 'bg-red-100 text-red-700'
      case 'cancelled': return 'bg-gray-100 text-gray-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-secondary-50">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <FontAwesomeIcon icon={faSpinner} className="text-primary-600 text-5xl animate-spin mb-4" />
          <p className="text-gray-600 text-lg">Loading your dashboard...</p>
        </motion.div>
      </div>
    )
  }

  const fadeIn = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  }

  const staggerContainer = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-primary-50">
      {/* Navigation */}
      <nav className="bg-white shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center space-x-2">
              <FontAwesomeIcon icon={faChartLine} className="text-primary-600 text-2xl" />
              <span className="text-2xl font-bold bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
                Fibtool
              </span>
            </Link>
            
            <div className="flex items-center space-x-4">
              {data?.user?.is_admin && (
                <Link
                  href="/dashboard/admin"
                  className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-yellow-400 to-orange-500 text-white rounded-lg hover:from-yellow-500 hover:to-orange-600 transition-all shadow-md hover:shadow-lg"
                >
                  <i className="fas fa-crown"></i>
                  <span className="font-semibold">Admin Panel</span>
                </Link>
              )}
              <button 
                onClick={handleLogout}
                className="flex items-center space-x-2 text-gray-700 hover:text-red-600 transition-colors"
              >
                <FontAwesomeIcon icon={faSignOutAlt} />
                <span className="font-semibold">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeIn}
          className="gradient-bg rounded-2xl p-8 mb-8 text-white shadow-2xl"
        >
          <div className="flex items-center space-x-3 mb-2">
            <FontAwesomeIcon icon={faUser} className="text-3xl" />
            <h1 className="text-3xl font-bold">Welcome back!</h1>
          </div>
          <p className="text-xl text-white/90">{data?.user?.name || data?.user?.email}</p>
          <p className="text-white/80 mt-2">
            <FontAwesomeIcon icon={faEnvelope} className="mr-2" />
            {data?.user?.email}
          </p>
        </motion.div>

        {/* Stats Overview */}
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
        >
          <motion.div variants={fadeIn} className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm font-semibold mb-1">Active Subscriptions</p>
                <p className="text-3xl font-bold text-primary-600">
                  {data?.subscriptions?.filter(s => s.status === 'active').length || 0}
                </p>
              </div>
              <div className="bg-primary-100 p-4 rounded-full">
                <FontAwesomeIcon icon={faCheckCircle} className="text-primary-600 text-2xl" />
              </div>
            </div>
          </motion.div>

          <motion.div variants={fadeIn} className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm font-semibold mb-1">Total Deliveries</p>
                <p className="text-3xl font-bold text-secondary-600">
                  {data?.deliveries?.length || 0}
                </p>
              </div>
              <div className="bg-secondary-100 p-4 rounded-full">
                <FontAwesomeIcon icon={faBox} className="text-secondary-600 text-2xl" />
              </div>
            </div>
          </motion.div>

          <motion.div variants={fadeIn} className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm font-semibold mb-1">Total Payments</p>
                <p className="text-3xl font-bold text-green-600">
                  {data?.payments?.length || 0}
                </p>
              </div>
              <div className="bg-green-100 p-4 rounded-full">
                <FontAwesomeIcon icon={faDollarSign} className="text-green-600 text-2xl" />
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Symbol Preferences Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center">
              <FontAwesomeIcon icon={faStar} className="text-yellow-500 mr-3" />
              My Selected Symbols
            </h2>
            <Link href="/pricing">
              <button className="btn-secondary flex items-center space-x-2">
                <FontAwesomeIcon icon={faEdit} />
                <span>Manage Symbols</span>
              </button>
            </Link>
          </div>

          {symbolPreferences.length > 0 ? (
            <div className="bg-white rounded-xl shadow-lg p-6">
              {(() => {
                // Group symbols by category
                const grouped: SymbolGroup = {}
                symbolPreferences.forEach(pref => {
                  if (!grouped[pref.group_display_name]) {
                    grouped[pref.group_display_name] = []
                  }
                  grouped[pref.group_display_name].push(pref)
                })

                return (
                  <div className="space-y-6">
                    {Object.entries(grouped).map(([groupName, symbols]) => (
                      <div key={groupName}>
                        <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center">
                          <span className="bg-primary-100 text-primary-700 px-3 py-1 rounded-full text-sm mr-2">
                            {symbols.length}
                          </span>
                          {groupName}
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {symbols.map(symbol => (
                            <div
                              key={symbol.id}
                              className="bg-gradient-to-br from-primary-50 to-secondary-50 border-2 border-primary-200 rounded-lg p-4 hover:shadow-md transition-all"
                            >
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-bold text-gray-900 text-lg">
                                  {symbol.display_name}
                                </span>
                                <FontAwesomeIcon icon={faStar} className="text-yellow-500" />
                              </div>
                              <p className="text-gray-600 text-sm">{symbol.description}</p>
                              <div className="mt-3 flex items-center text-xs text-gray-500">
                                <FontAwesomeIcon icon={faClock} className="mr-1" />
                                <span>Added {new Date(symbol.created_at).toLocaleDateString()}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              })()}

              <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start">
                  <FontAwesomeIcon icon={faEnvelope} className="text-blue-600 mt-1 mr-3" />
                  <div>
                    <p className="text-blue-800 font-semibold">Daily Delivery Schedule</p>
                    <p className="text-blue-700 text-sm mt-1">
                      You'll receive confluence analysis reports for these symbols daily via email and in your dashboard.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card text-center py-12">
              <FontAwesomeIcon icon={faStar} className="text-gray-300 text-6xl mb-4" />
              <h3 className="text-xl font-bold text-gray-900 mb-2">No Symbols Selected</h3>
              <p className="text-gray-600 mb-4">
                Select a plan and choose your preferred trading symbols to start receiving daily analysis reports.
              </p>
              <Link href="/pricing">
                <button className="btn-primary">
                  <FontAwesomeIcon icon={faChartLine} className="mr-2" />
                  Browse Plans & Select Symbols
                </button>
              </Link>
            </div>
          )}
        </motion.div>

        {/* Subscriptions Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mb-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <FontAwesomeIcon icon={faCheckCircle} className="text-primary-600 mr-3" />
            Your Subscriptions
          </h2>
          {data?.subscriptions && data.subscriptions.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.subscriptions.map((sub: any, index: number) => (
                <motion.div
                  key={sub.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="card"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getStatusColor(sub.status)}`}>
                      {sub.status.toUpperCase()}
                    </span>
                    <FontAwesomeIcon icon={faClock} className="text-gray-400" />
                  </div>
                  <p className="text-gray-700">
                    <strong>Started:</strong> {new Date(sub.started_at).toLocaleDateString()}
                  </p>
                  {sub.ended_at && (
                    <p className="text-gray-700 mt-1">
                      <strong>Ended:</strong> {new Date(sub.ended_at).toLocaleDateString()}
                    </p>
                  )}
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="card text-center py-8">
              <FontAwesomeIcon icon={faCheckCircle} className="text-gray-300 text-5xl mb-4" />
              <p className="text-gray-600">No active subscriptions yet</p>
              <p className="text-gray-500 text-sm mt-2">Purchase a plan below to get started!</p>
            </div>
          )}
        </motion.div>

        {/* Available Plans */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <FontAwesomeIcon icon={faCreditCard} className="text-secondary-600 mr-3" />
            Available Plans
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map((plan, index) => (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
                className="card text-center hover:-translate-y-2 relative overflow-hidden"
              >
                {plan.name.includes('Ultimate') && (
                  <div className="absolute top-0 right-0 bg-gradient-to-r from-secondary-500 to-primary-500 text-white px-4 py-1 text-xs font-bold transform rotate-45 translate-x-8 translate-y-2">
                    POPULAR
                  </div>
                )}
                <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-5xl font-bold bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
                    ${(plan.price / 100).toFixed(2)}
                  </span>
                </div>
                <p className="text-gray-600 mb-6 min-h-[48px]">{plan.description}</p>
                <button
                  onClick={() => handleCheckout(plan.id)}
                  disabled={checkoutLoading}
                  className="btn-primary w-full"
                >
                  {checkoutLoading ? (
                    <>
                      <FontAwesomeIcon icon={faSpinner} className="animate-spin mr-2" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <FontAwesomeIcon icon={faCreditCard} className="mr-2" />
                      Purchase Now
                    </>
                  )}
                </button>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Reports Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-8"
        >
          <ReportsSection />
        </motion.div>

        {/* Recent Deliveries */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="mb-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <FontAwesomeIcon icon={faBox} className="text-green-600 mr-3" />
            Recent Deliveries
          </h2>
          {data?.deliveries && data.deliveries.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.deliveries.slice(0, 6).map((delivery: any, index: number) => (
                <motion.div
                  key={delivery.id}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.05 }}
                  className="card"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-gray-900">{delivery.symbol}</span>
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${getStatusColor(delivery.status)}`}>
                      {delivery.status}
                    </span>
                  </div>
                  <p className="text-gray-600 text-sm">
                    <FontAwesomeIcon icon={faClock} className="mr-2" />
                    {new Date(delivery.created_at).toLocaleString()}
                  </p>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="card text-center py-8">
              <FontAwesomeIcon icon={faBox} className="text-gray-300 text-5xl mb-4" />
              <p className="text-gray-600">No deliveries yet</p>
              <p className="text-gray-500 text-sm mt-2">Your analysis reports will appear here</p>
            </div>
          )}
        </motion.div>

        {/* Payment History */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center">
            <FontAwesomeIcon icon={faDollarSign} className="text-blue-600 mr-3" />
            Payment History
          </h2>
          {data?.payments && data.payments.length > 0 ? (
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Amount</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {data.payments.map((payment: any, index: number) => (
                      <motion.tr
                        key={payment.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="hover:bg-gray-50 transition-colors"
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="text-lg font-semibold text-gray-900">
                            ${(payment.amount / 100).toFixed(2)}
                          </span>
                          <span className="text-gray-500 ml-2 text-sm">{payment.currency?.toUpperCase()}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(payment.status)}`}>
                            {payment.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                          {new Date(payment.created_at).toLocaleString()}
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="card text-center py-8">
              <FontAwesomeIcon icon={faDollarSign} className="text-gray-300 text-5xl mb-4" />
              <p className="text-gray-600">No payment history</p>
              <p className="text-gray-500 text-sm mt-2">Your transactions will be listed here</p>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}

