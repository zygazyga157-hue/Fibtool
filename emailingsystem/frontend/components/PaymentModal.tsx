'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faTimes,
  faSpinner,
  faCheckCircle,
  faExclamationTriangle,
  faCreditCard
} from '@fortawesome/free-solid-svg-icons'
import { motion, AnimatePresence } from 'framer-motion'

interface Symbol {
  id: number
  symbol: string
  display_name: string
}

interface Plan {
  id: number
  name: string
  price: number
  billing_cycle: string
}

interface PaymentModalProps {
  plan: Plan
  selectedSymbols: number[]
  symbolDetails: Symbol[]
  onClose: () => void
  onSuccess: () => void
}

interface PaymentFormData {
  action_url: string
  poll_url: string
  reference: string
  amount: number
  email: string
  description: string
  demo_mode?: boolean
}

export default function PaymentModal({
  plan,
  selectedSymbols,
  symbolDetails,
  onClose,
  onSuccess
}: PaymentModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [paymentFormData, setPaymentFormData] = useState<PaymentFormData | null>(null)
  const [paymentStatus, setPaymentStatus] = useState<'pending' | 'processing' | 'success' | 'failed'>('pending')
  const [paymentId, setPaymentId] = useState<string | null>(null)

  const initiatePayment = async () => {
    setLoading(true)
    setError('')

    try {
      const token = localStorage.getItem('token')
      if (!token) {
        setError('Please login to continue')
        setLoading(false)
        return
      }

      // Save symbol preferences first
      await axios.post(
        'http://localhost:8000/api/v1/user/symbol-preferences',
        {
          symbol_ids: selectedSymbols,
          plan_id: plan.id
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )

      // Initiate payment
      const response = await axios.post(
        'http://localhost:8000/api/v1/checkout-inline',
        { plan_id: plan.id },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )

      setPaymentId(response.data.payment_id)
      setPaymentFormData(response.data.form_data)
      setPaymentStatus('processing')
      setLoading(false)

      // Start polling for payment status
      startPaymentPolling(response.data.payment_id, token)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to initiate payment')
      setLoading(false)
    }
  }

  const startPaymentPolling = (paymentId: string, token: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(
          `http://localhost:8000/api/v1/payment/${paymentId}`,
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        )

        const status = response.data.status

        if (status === 'completed' || status === 'paid') {
          clearInterval(pollInterval)
          setPaymentStatus('success')
          setTimeout(() => {
            onSuccess()
          }, 2000)
        } else if (status === 'failed' || status === 'cancelled') {
          clearInterval(pollInterval)
          setPaymentStatus('failed')
          setError('Payment was not completed. Please try again.')
        }
      } catch (err) {
        console.error('Error polling payment status:', err)
      }
    }, 3000) // Poll every 3 seconds

    // Stop polling after 5 minutes
    setTimeout(() => {
      clearInterval(pollInterval)
      if (paymentStatus === 'processing') {
        setError('Payment timeout. Please check your email for confirmation.')
      }
    }, 300000)
  }

  useEffect(() => {
    initiatePayment()
  }, [])

  const selectedSymbolNames = symbolDetails
    .filter(s => selectedSymbols.includes(s.id))
    .map(s => s.display_name)
    .join(', ')

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
        onClick={(e) => {
          if (e.target === e.currentTarget && paymentStatus !== 'processing') {
            onClose()
          }
        }}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white p-6 rounded-t-2xl relative">
            <button
              onClick={onClose}
              disabled={paymentStatus === 'processing'}
              className="absolute top-4 right-4 text-white hover:text-gray-200 disabled:opacity-50"
            >
              <FontAwesomeIcon icon={faTimes} className="text-2xl" />
            </button>
            <h2 className="text-2xl font-bold mb-2">Complete Your Payment</h2>
            <p className="text-primary-100">Secure checkout powered by PayNow</p>
          </div>

          {/* Order Summary */}
          <div className="p-6 border-b">
            <h3 className="font-semibold text-gray-900 mb-4 text-lg">Order Summary</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Plan</span>
                <span className="font-semibold text-gray-900">{plan.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Billing</span>
                <span className="font-semibold text-gray-900">
                  {plan.billing_cycle === 'one-time' ? 'One-time' : `${plan.billing_cycle.charAt(0).toUpperCase() + plan.billing_cycle.slice(1)}`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Symbols</span>
                <span className="font-semibold text-gray-900 text-right max-w-xs truncate">
                  {selectedSymbolNames}
                </span>
              </div>
              <div className="border-t pt-3 mt-3 flex justify-between text-lg">
                <span className="font-bold text-gray-900">Total</span>
                <span className="font-bold text-primary-600">${plan.price.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Payment Status */}
          <div className="p-6">
            {loading && (
              <div className="text-center py-8">
                <FontAwesomeIcon icon={faSpinner} className="text-primary-600 text-4xl animate-spin mb-4" />
                <p className="text-gray-600">Initializing payment...</p>
              </div>
            )}

            {error && !loading && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
                <FontAwesomeIcon icon={faExclamationTriangle} className="text-red-600 mt-1 mr-3" />
                <div>
                  <p className="text-red-800 font-semibold">Payment Error</p>
                  <p className="text-red-700 text-sm mt-1">{error}</p>
                  <button
                    onClick={initiatePayment}
                    className="btn-primary mt-3 text-sm"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            )}

            {paymentStatus === 'processing' && paymentFormData && (
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <FontAwesomeIcon icon={faCreditCard} className="text-blue-600 mt-1 mr-3" />
                    <div>
                      <p className="text-blue-800 font-semibold">Complete Payment</p>
                      <p className="text-blue-700 text-sm mt-1">
                        {paymentFormData.demo_mode
                          ? 'Demo Mode: Use any test card details to complete the payment.'
                          : 'Enter your payment details below to complete the transaction.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* PayNow Payment Form */}
                <div className="bg-gray-50 rounded-lg p-6">
                  <form
                    action={paymentFormData.action_url}
                    method="POST"
                    target="paynow-frame"
                    className="space-y-4"
                  >
                    <input type="hidden" name="reference" value={paymentFormData.reference} />
                    <input type="hidden" name="amount" value={paymentFormData.amount} />
                    <input type="hidden" name="email" value={paymentFormData.email} />
                    <input type="hidden" name="description" value={paymentFormData.description} />

                    <div className="text-center">
                      <button
                        type="submit"
                        className="btn-primary text-lg px-8 py-3"
                      >
                        Proceed to PayNow - ${plan.price.toFixed(2)}
                      </button>
                    </div>
                  </form>

                  {/* Payment iframe */}
                  <div className="mt-6 border rounded-lg overflow-hidden bg-white">
                    <iframe
                      name="paynow-frame"
                      className="w-full h-96 border-0"
                      title="PayNow Payment"
                    />
                  </div>
                </div>

                <div className="text-center text-sm text-gray-600 mt-4">
                  <FontAwesomeIcon icon={faSpinner} className="animate-spin mr-2" />
                  Waiting for payment confirmation...
                </div>
              </div>
            )}

            {paymentStatus === 'success' && (
              <div className="text-center py-8">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200 }}
                >
                  <FontAwesomeIcon icon={faCheckCircle} className="text-green-500 text-6xl mb-4" />
                </motion.div>
                <h3 className="text-2xl font-bold text-gray-900 mb-2">Payment Successful!</h3>
                <p className="text-gray-600 mb-4">
                  Your subscription is now active. You'll receive your first report shortly.
                </p>
                <button
                  onClick={onSuccess}
                  className="btn-primary"
                >
                  Go to Dashboard
                </button>
              </div>
            )}

            {paymentStatus === 'failed' && (
              <div className="text-center py-8">
                <FontAwesomeIcon icon={faExclamationTriangle} className="text-red-500 text-6xl mb-4" />
                <h3 className="text-2xl font-bold text-gray-900 mb-2">Payment Failed</h3>
                <p className="text-gray-600 mb-4">
                  Your payment could not be processed. Please try again.
                </p>
                <button
                  onClick={initiatePayment}
                  className="btn-primary"
                >
                  Retry Payment
                </button>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="bg-gray-50 p-4 rounded-b-2xl text-center text-sm text-gray-600">
            <p>🔒 Secure payment powered by PayNow Zimbabwe</p>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
