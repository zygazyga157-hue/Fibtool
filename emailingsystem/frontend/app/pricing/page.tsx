'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import axios from 'axios'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faChartLine,
  faCheck,
  faTimes,
  faCrown,
  faRocket,
  faCalendar,
  faInfinity,
  faChevronDown,
  faChevronUp,
  faInfoCircle
} from '@fortawesome/free-solid-svg-icons'
import { motion, AnimatePresence } from 'framer-motion'
import PaymentModal from '@/components/PaymentModal'

interface Symbol {
  id: number
  symbol: string
  display_name: string
  description: string
}

interface SymbolGroup {
  id: number
  name: string
  display_name: string
  description: string
  icon: string
  symbols: Symbol[]
}

interface Plan {
  id: number
  name: string
  description: string
  price: number
  billing_cycle: string
  symbol_limit: number | null
  allowed_groups: string[]
  features: string[]
}

export default function PricingPage() {
  const router = useRouter()
  const [symbolGroups, setSymbolGroups] = useState<SymbolGroup[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null)
  const [selectedSymbols, setSelectedSymbols] = useState<number[]>([])
  const [expandedGroups, setExpandedGroups] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showPaymentModal, setShowPaymentModal] = useState(false)

  // Get all symbol details for selected symbols
  const getAllSymbols = () => {
    const allSymbols: Symbol[] = []
    symbolGroups.forEach(group => {
      allSymbols.push(...group.symbols)
    })
    return allSymbols
  }

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [groupsRes, plansRes] = await Promise.all([
        axios.get('http://localhost:8000/api/v1/symbol-groups'),
        axios.get('http://localhost:8000/api/v1/plans-detailed')
      ])
      
      setSymbolGroups(groupsRes.data.symbol_groups)
      setPlans(plansRes.data.plans)
      setLoading(false)
    } catch (err: any) {
      setError('Failed to load pricing information')
      setLoading(false)
    }
  }

  const handlePlanSelect = (plan: Plan) => {
    setSelectedPlan(plan)
    setSelectedSymbols([])
    // Auto-expand first group
    if (symbolGroups.length > 0) {
      setExpandedGroups([symbolGroups[0].name])
    }
  }

  const toggleGroup = (groupName: string) => {
    setExpandedGroups(prev =>
      prev.includes(groupName)
        ? prev.filter(g => g !== groupName)
        : [...prev, groupName]
    )
  }

  const handleSymbolToggle = (symbolId: number) => {
    if (!selectedPlan) return

    const newSelection = selectedSymbols.includes(symbolId)
      ? selectedSymbols.filter(id => id !== symbolId)
      : [...selectedSymbols, symbolId]

    // Check symbol limit
    if (selectedPlan.symbol_limit !== null && newSelection.length > selectedPlan.symbol_limit) {
      alert(`This plan allows maximum ${selectedPlan.symbol_limit} symbol(s)`)
      return
    }

    setSelectedSymbols(newSelection)
  }

  const canProceedToPayment = () => {
    if (!selectedPlan) return false
    if (selectedPlan.symbol_limit === 1 && selectedSymbols.length !== 1) return false
    if (selectedSymbols.length === 0) return false
    return true
  }

  const handleProceedToPayment = () => {
    if (!canProceedToPayment()) return
    setShowPaymentModal(true)
  }

  const getIconClass = (iconName: string) => {
    switch(iconName) {
      case 'gold': return 'text-amber-500'
      case 'chart-line': return 'text-blue-500'
      case 'bolt': return 'text-purple-500'
      case 'dollar-sign': return 'text-green-500'
      case 'coins': return 'text-orange-500'
      case 'bitcoin': return 'text-orange-400'
      default: return 'text-gray-500'
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading pricing...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Choose Your Plan
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Select a plan and customize your symbol preferences to start receiving daily confluence reports
          </p>
        </div>

        {error && (
          <div className="mb-8 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Step 1: Plan Selection */}
        <div className="mb-12">
          <div className="flex items-center mb-6">
            <div className="bg-primary-600 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold mr-3">
              1
            </div>
            <h2 className="text-2xl font-bold text-gray-900">Select Your Plan</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {plans.map((plan) => (
              <motion.div
                key={plan.id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => handlePlanSelect(plan)}
                className={`bg-white rounded-xl shadow-lg p-6 cursor-pointer transition-all border-4 ${
                  selectedPlan?.id === plan.id
                    ? 'border-primary-600 shadow-xl'
                    : 'border-transparent hover:border-gray-200'
                }`}
              >
                {plan.billing_cycle === 'monthly' && (
                  <div className="text-center mb-2">
                    <span className="bg-gradient-to-r from-primary-500 to-secondary-600 text-white px-3 py-1 rounded-full text-xs font-bold">
                      MOST POPULAR
                    </span>
                  </div>
                )}

                <div className="text-center mb-4">
                  <FontAwesomeIcon
                    icon={plan.billing_cycle === 'yearly' ? faCrown : plan.billing_cycle === 'monthly' ? faCalendar : faRocket}
                    className="text-4xl text-primary-600 mb-3"
                  />
                  <h3 className="text-2xl font-bold text-gray-900">{plan.name}</h3>
                  <p className="text-gray-600 text-sm mt-2">{plan.description}</p>
                </div>

                <div className="text-center mb-6">
                  <div className="text-4xl font-bold text-gray-900">
                    ${plan.price.toFixed(2)}
                  </div>
                  <div className="text-gray-600">
                    {plan.billing_cycle === 'one-time' ? 'one-time' : `/${plan.billing_cycle}`}
                  </div>
                </div>

                <div className="border-t pt-4 mb-4">
                  <div className="flex items-center justify-center text-sm font-semibold text-gray-700 mb-2">
                    {plan.symbol_limit === null ? (
                      <>
                        <FontAwesomeIcon icon={faInfinity} className="mr-2 text-primary-600" />
                        Unlimited Symbols
                      </>
                    ) : (
                      <>
                        <span className="text-2xl font-bold text-primary-600 mr-2">{plan.symbol_limit}</span>
                        Symbol{plan.symbol_limit > 1 ? 's' : ''}
                      </>
                    )}
                  </div>
                </div>

                <ul className="space-y-3 mb-6">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start text-sm">
                      <FontAwesomeIcon icon={faCheck} className="text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>

                {selectedPlan?.id === plan.id && (
                  <div className="bg-primary-50 text-primary-700 px-4 py-2 rounded-lg text-center font-semibold text-sm">
                    ✓ Selected
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* Step 2: Symbol Selection */}
        {selectedPlan && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-12"
          >
            <div className="flex items-center mb-6">
              <div className="bg-primary-600 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold mr-3">
                2
              </div>
              <h2 className="text-2xl font-bold text-gray-900">Select Symbols</h2>
              {selectedPlan.symbol_limit !== null && (
                <span className="ml-4 text-sm text-gray-600">
                  ({selectedSymbols.length} of {selectedPlan.symbol_limit} selected)
                </span>
              )}
              {selectedPlan.symbol_limit === null && (
                <span className="ml-4 text-sm text-gray-600">
                  ({selectedSymbols.length} selected)
                </span>
              )}
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6">
              {selectedPlan.symbol_limit === 1 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 flex items-start">
                  <FontAwesomeIcon icon={faInfoCircle} className="text-blue-600 mt-1 mr-3" />
                  <p className="text-blue-800 text-sm">
                    This plan allows <strong>1 symbol only</strong>. Select the instrument you want to track.
                  </p>
                </div>
              )}

              <div className="space-y-4">
                {symbolGroups.map((group) => (
                  <div key={group.id} className="border rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleGroup(group.name)}
                      className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex items-center">
                        <FontAwesomeIcon
                          icon={faChartLine}
                          className={`mr-3 text-xl ${getIconClass(group.icon)}`}
                        />
                        <div className="text-left">
                          <div className="font-bold text-gray-900">{group.display_name}</div>
                          <div className="text-sm text-gray-600">{group.description}</div>
                        </div>
                      </div>
                      <FontAwesomeIcon
                        icon={expandedGroups.includes(group.name) ? faChevronUp : faChevronDown}
                        className="text-gray-400"
                      />
                    </button>

                    <AnimatePresence>
                      {expandedGroups.includes(group.name) && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <div className="p-4 grid md:grid-cols-2 gap-3">
                            {group.symbols.map((symbol) => (
                              <label
                                key={symbol.id}
                                className={`flex items-center p-3 rounded-lg cursor-pointer transition-all ${
                                  selectedSymbols.includes(symbol.id)
                                    ? 'bg-primary-50 border-2 border-primary-600'
                                    : 'bg-gray-50 border-2 border-gray-200 hover:border-gray-300'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedSymbols.includes(symbol.id)}
                                  onChange={() => handleSymbolToggle(symbol.id)}
                                  className="mr-3 h-5 w-5 text-primary-600 rounded"
                                />
                                <div>
                                  <div className="font-semibold text-gray-900">
                                    {symbol.display_name}
                                  </div>
                                  <div className="text-xs text-gray-600">{symbol.description}</div>
                                </div>
                              </label>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* Proceed Button */}
        {selectedPlan && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-center"
          >
            <button
              onClick={handleProceedToPayment}
              disabled={!canProceedToPayment()}
              className={`btn-primary text-lg px-12 py-4 ${
                !canProceedToPayment() ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              Proceed to Payment - ${selectedPlan.price.toFixed(2)}
            </button>
          </motion.div>
        )}
      </div>

      {/* Payment Modal */}
      {showPaymentModal && selectedPlan && (
        <PaymentModal
          plan={selectedPlan}
          selectedSymbols={selectedSymbols}
          symbolDetails={getAllSymbols()}
          onClose={() => setShowPaymentModal(false)}
          onSuccess={() => router.push('/dashboard')}
        />
      )}
    </div>
  )
}
