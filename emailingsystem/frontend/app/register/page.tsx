'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faEnvelope, faLock, faUser, faChartLine, faArrowRight, faCheck } from '@fortawesome/free-solid-svg-icons'
import { motion } from 'framer-motion'
import { authAPI } from '@/lib/api'

export default function RegisterPage() {
  const router = useRouter()
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await authAPI.register(formData)
      // Auto-login after registration
      const loginResponse = await authAPI.login({
        email: formData.email,
        password: formData.password,
      })
      localStorage.setItem('token', loginResponse.data.access_token)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-gradient-to-br from-secondary-50 via-white to-primary-50">
      {/* Right Side - Registration Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 order-2 lg:order-1">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="w-full max-w-md"
        >
          {/* Mobile Logo */}
          <Link href="/" className="lg:hidden flex items-center space-x-2 mb-8">
            <FontAwesomeIcon icon={faChartLine} className="text-primary-600 text-2xl" />
            <span className="text-2xl font-bold bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
              Fibtool
            </span>
          </Link>

          <div className="card">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">Create Account</h2>
            <p className="text-gray-600 mb-8">Start receiving professional trading analysis today</p>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex items-center"
              >
                <span className="text-sm">{error}</span>
              </motion.div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Full Name
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <FontAwesomeIcon icon={faUser} className="text-gray-400" />
                  </div>
                  <input
                    type="text"
                    className="input pl-10"
                    placeholder="John Doe"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Email Address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <FontAwesomeIcon icon={faEnvelope} className="text-gray-400" />
                  </div>
                  <input
                    type="email"
                    className="input pl-10"
                    placeholder="you@example.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <FontAwesomeIcon icon={faLock} className="text-gray-400" />
                  </div>
                  <input
                    type="password"
                    className="input pl-10"
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    required
                    minLength={6}
                  />
                </div>
                <p className="mt-2 text-xs text-gray-500">
                  Must be at least 6 characters long
                </p>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full text-lg group"
              >
                {loading ? (
                  <span>Creating account...</span>
                ) : (
                  <>
                    Create Account
                    <FontAwesomeIcon icon={faArrowRight} className="ml-2 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-gray-600">
                Already have an account?{' '}
                <Link href="/login" className="text-primary-600 hover:text-primary-700 font-semibold transition-colors">
                  Sign in instead
                </Link>
              </p>
            </div>

            <div className="mt-8 pt-6 border-t border-gray-200">
              <Link href="/" className="text-sm text-gray-500 hover:text-primary-600 transition-colors flex items-center justify-center">
                <FontAwesomeIcon icon={faArrowRight} className="mr-2 rotate-180" />
                Back to Home
              </Link>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Left Side - Branding */}
      <motion.div 
        initial={{ opacity: 0, x: 50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6 }}
        className="hidden lg:flex lg:w-1/2 gradient-bg p-12 flex-col justify-between order-1 lg:order-2"
      >
        <Link href="/" className="flex items-center space-x-3 text-white">
          <FontAwesomeIcon icon={faChartLine} className="text-3xl" />
          <span className="text-3xl font-bold">Fibtool</span>
        </Link>

        <div className="text-white">
          <h1 className="text-5xl font-bold mb-6 leading-tight">
            Join Thousands of<br />Smart Traders
          </h1>
          <p className="text-xl text-white/90 mb-8">
            Get started with Fibtool and receive professional analysis that helps you make better trading decisions.
          </p>
          <div className="space-y-4">
            <div className="flex items-start space-x-3">
              <div className="bg-white/20 rounded-full p-2 mt-1">
                <FontAwesomeIcon icon={faCheck} />
              </div>
              <div>
                <h3 className="font-semibold">Instant Access</h3>
                <p className="text-white/80">Start receiving reports immediately after signup</p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <div className="bg-white/20 rounded-full p-2 mt-1">
                <FontAwesomeIcon icon={faCheck} />
              </div>
              <div>
                <h3 className="font-semibold">No Credit Card Required</h3>
                <p className="text-white/80">Explore our plans without payment upfront</p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <div className="bg-white/20 rounded-full p-2 mt-1">
                <FontAwesomeIcon icon={faCheck} />
              </div>
              <div>
                <h3 className="font-semibold">Cancel Anytime</h3>
                <p className="text-white/80">Flexible subscriptions with no long-term commitment</p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-white/60 text-sm">
          © 2025 Fibtool. All rights reserved.
        </p>
      </motion.div>
    </div>
  )
}

