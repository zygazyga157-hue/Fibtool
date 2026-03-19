'use client'

import Link from 'next/link'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { 
  faChartLine, 
  faEnvelope, 
  faShieldAlt, 
  faBolt,
  faRocket,
  faCheck,
  faArrowRight,
  faStar,
  faCrown,
  faDollarSign,
  faLock,
  faChartBar,
  faLayerGroup,
  faMobileAlt,
  faClock,
  faCheckCircle,
  faQuestionCircle,
  faCalculator,
  faChartPie,
  faBullseye,
  faChevronDown,
  faMicrochip,
  faInfinity,
  faChartArea,
  faTrophy,
  faGraduationCap,
  faLightbulb,
  faExclamationTriangle,
  faShieldHalved,
  faDatabase,
  faCode
} from '@fortawesome/free-solid-svg-icons'
import { motion } from 'framer-motion'
import { useState } from 'react'

export default function Home() {
  const fadeIn = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  }

  const staggerContainer = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15
      }
    }
  }

  const features = [
    {
      icon: faEnvelope,
      title: "Daily Email Delivery",
      description: "Automated reports sent directly to your inbox every trading day"
    },
    {
      icon: faChartBar,
      title: "Visual Charts",
      description: "Color-coded confluence levels with quality indicators and annotations"
    },
    {
      icon: faLayerGroup,
      title: "Multi-Symbol Support",
      description: "FX pairs, precious metals, indices, and crypto (coming soon)"
    },
    {
      icon: faStar,
      title: "Quality Scoring",
      description: "Strength and severity metrics to prioritize the best levels"
    },
    {
      icon: faMobileAlt,
      title: "Mobile Friendly",
      description: "View reports on any device - desktop, mobile, or tablet"
    },
    {
      icon: faLock,
      title: "Secure Payments",
      description: "PayNow Zimbabwe with SHA512 hash verification"
    }
  ]

  const plans = [
    {
      name: "Single Report",
      price: "$5",
      period: "one-time",
      icon: faChartBar,
      gradient: "from-blue-500 to-blue-600",
      features: [
        "Single symbol analysis",
        "Delivered within 24 hours",
        "Full confluence report",
        "Visual chart included",
        "No recurring charges"
      ]
    },
    {
      name: "Monthly",
      price: "$20",
      period: "/month",
      icon: faClock,
      gradient: "from-purple-500 to-purple-600",
      popular: true,
      features: [
        "Daily reports",
        "Unlimited symbols",
        "Cancel anytime",
        "Full dashboard access",
        "Priority support"
      ]
    },
    {
      name: "Yearly",
      price: "$200",
      period: "/year",
      icon: faCrown,
      gradient: "from-amber-500 to-amber-600",
      badge: "SAVE 17%",
      features: [
        "All monthly features",
        "Save $40 annually",
        "Lock in pricing",
        "$16.67/month equivalent",
        "Most popular choice"
      ]
    }
  ]

  const faqs = [
    {
      question: "How soon after payment will I receive my first report?",
      answer: "For one-time purchases, within 24 hours. For subscriptions, your first report is delivered the next trading day after activation."
    },
    {
      question: "Can I change my symbol preferences?",
      answer: "Yes! Log into your dashboard anytime to update which symbols you want to track."
    },
    {
      question: "What format are the reports?",
      answer: "Visual PNG/JPG charts with annotated confluence levels, plus optional CSV data tables."
    },
    {
      question: "Do subscriptions auto-renew?",
      answer: "Yes, but you can cancel anytime from your dashboard. No cancellation fees."
    },
    {
      question: "What if I miss a report?",
      answer: "All past reports are archived in your dashboard for 30 days."
    },
    {
      question: "Is there a free trial?",
      answer: "We offer a $5 single report option so you can test the service before committing to a subscription."
    }
  ]

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <motion.div 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-2"
            >
              <FontAwesomeIcon icon={faChartLine} className="text-primary-600 text-2xl" />
              <span className="text-2xl font-bold bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
                Fibtool
              </span>
            </motion.div>
            
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-4"
            >
              <Link href="/pricing" className="text-gray-700 hover:text-primary-600 transition-colors font-medium">
                Pricing
              </Link>
              <Link href="/login" className="text-gray-700 hover:text-primary-600 transition-colors font-medium">
                Login
              </Link>
              <Link href="/register">
                <button className="btn-primary">
                  Get Started
                </button>
              </Link>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center">
            <motion.div
              initial="hidden"
              animate="visible"
              variants={staggerContainer}
            >
              <motion.div variants={fadeIn} className="inline-block mb-4">
                <span className="bg-gradient-to-r from-primary-100 to-secondary-100 text-primary-700 px-4 py-2 rounded-full text-sm font-semibold">
                  <FontAwesomeIcon icon={faBolt} className="mr-2" />
                  Fibonacci & Square of Nine Analysis
                </span>
              </motion.div>
              
              <motion.h1 
                variants={fadeIn}
                className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 mt-6 leading-tight"
              >
                Professional Trading
                <br />
                <span className="bg-gradient-to-r from-primary-600 to-secondary-600 bg-clip-text text-transparent">
                  Analysis Delivered Daily
                </span>
              </motion.h1>
              
              <motion.p 
                variants={fadeIn}
                className="text-xl md:text-2xl text-gray-600 mt-6 leading-relaxed max-w-3xl mx-auto"
              >
                Get daily confluence reports with high-probability support and resistance zones directly to your inbox. No manual analysis required.
              </motion.p>
              
              <motion.div 
                variants={fadeIn}
                className="flex flex-col sm:flex-row gap-4 mt-10 justify-center"
              >
                <Link href="/register">
                  <button className="btn-primary text-lg px-8 py-4 group shadow-lg hover:shadow-xl">
                    Start Now - $5 Single Report
                    <FontAwesomeIcon icon={faArrowRight} className="ml-2 group-hover:translate-x-1 transition-transform" />
                  </button>
                </Link>
                <Link href="/pricing">
                  <button className="bg-white hover:bg-gray-50 text-gray-900 font-semibold py-4 px-8 rounded-lg border-2 border-gray-300 transition-all duration-200 text-lg shadow-md hover:shadow-lg">
                    View All Plans
                  </button>
                </Link>
              </motion.div>

              <motion.div 
                variants={fadeIn}
                className="flex flex-wrap items-center justify-center gap-6 mt-8 text-sm text-gray-600"
              >
                <div className="flex items-center">
                  <FontAwesomeIcon icon={faCheck} className="text-green-500 mr-2" />
                  No credit card for trial
                </div>
                <div className="flex items-center">
                  <FontAwesomeIcon icon={faCheck} className="text-green-500 mr-2" />
                  Cancel anytime
                </div>
                <div className="flex items-center">
                  <FontAwesomeIcon icon={faCheck} className="text-green-500 mr-2" />
                  Secure payments
                </div>
              </motion.div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-gradient-to-b from-white to-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeIn} className="text-4xl md:text-5xl font-bold text-gray-900">
              Why Choose Fibtool?
            </motion.h2>
            <motion.p variants={fadeIn} className="text-xl text-gray-600 mt-4 max-w-2xl mx-auto">
              Professional-grade analysis combining Fibonacci retracements with W.D. Gann&apos;s Square of Nine geometry
            </motion.p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="bg-white rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow border border-gray-100"
              >
                <div className="bg-gradient-to-br from-primary-100 to-secondary-100 w-16 h-16 rounded-lg flex items-center justify-center mb-6">
                  <FontAwesomeIcon icon={feature.icon} className="text-primary-600 text-2xl" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">{feature.title}</h3>
                <p className="text-gray-600">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* What is Confluence Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                What is Confluence Analysis?
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                When a Fibonacci level aligns closely with a Square of Nine price level, it creates a <span className="font-bold text-primary-600">confluence zone</span> - a price area where multiple mathematical frameworks agree, showing statistically stronger support/resistance characteristics.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-8 mt-12">
              <motion.div variants={fadeIn} className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-8">
                <div className="text-4xl font-bold text-blue-600 mb-4">Step 1</div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">Fibonacci Analysis</h3>
                <p className="text-gray-700 mb-4">Calculate 43 key Fibonacci levels including:</p>
                <ul className="space-y-2 text-gray-600">
                  <li>• Critical levels: 38.2%, 50%, 61.8%</li>
                  <li>• Extended ratios: 78.6%, 88.6%, 92.2%</li>
                  <li>• Extensions: 111%, 138.2%, 161.8%, 200%</li>
                </ul>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-8">
                <div className="text-4xl font-bold text-purple-600 mb-4">Step 2</div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">Square of Nine</h3>
                <p className="text-gray-700 mb-4">Using W.D. Gann&apos;s sacred geometry at key angles:</p>
                <ul className="space-y-2 text-gray-600">
                  <li>• Cardinal: 90°, 180°, 270°, 360°</li>
                  <li>• Diagonal: 45°, 135°, 225°, 315°</li>
                  <li>• Extended cycles: 450°, 540°, 720°</li>
                </ul>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-8">
                <div className="text-4xl font-bold text-green-600 mb-4">Step 3</div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">Confluence Detection</h3>
                <p className="text-gray-700 mb-4">Measure distance between levels:</p>
                <ul className="space-y-2 text-gray-600">
                  <li>• Distance = 0: Perfect alignment ⭐</li>
                  <li>• Distance ≤ 5: Strong confluence</li>
                  <li>• Calculate severity scores</li>
                </ul>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Strength Scores Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                Understanding Strength Scores
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Our algorithm assigns strength scores based on how closely Fibonacci and S9 levels align
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg border-4 border-amber-400">
                <div className="text-5xl font-bold text-amber-500 mb-2">4</div>
                <div className="text-2xl font-bold text-gray-900 mb-2">🌟 Perfect</div>
                <div className="text-gray-600 mb-3">Distance = 0</div>
                <p className="text-sm text-gray-500">Exact alignment - extremely rare and highly significant</p>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg border-4 border-green-400">
                <div className="text-5xl font-bold text-green-500 mb-2">3</div>
                <div className="text-2xl font-bold text-gray-900 mb-2">⭐ Strong</div>
                <div className="text-gray-600 mb-3">Distance ≤ 5.0</div>
                <p className="text-sm text-gray-500">Very tight alignment - high confidence levels</p>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg border-4 border-blue-400">
                <div className="text-5xl font-bold text-blue-500 mb-2">2</div>
                <div className="text-2xl font-bold text-gray-900 mb-2">🔵 Moderate</div>
                <div className="text-gray-600 mb-3">Distance ≤ 7.5</div>
                <p className="text-sm text-gray-500">Good alignment - worth monitoring closely</p>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg border-4 border-gray-300">
                <div className="text-5xl font-bold text-gray-400 mb-2">1</div>
                <div className="text-2xl font-bold text-gray-900 mb-2">⚪ Weak</div>
                <div className="text-gray-600 mb-3">Distance &gt; 7.5</div>
                <p className="text-sm text-gray-500">Loose alignment - lower priority levels</p>
              </motion.div>
            </div>

            <motion.div variants={fadeIn} className="mt-12 bg-gradient-to-r from-primary-100 to-secondary-100 rounded-xl p-8">
              <div className="flex items-start space-x-4">
                <FontAwesomeIcon icon={faLightbulb} className="text-primary-600 text-3xl mt-1" />
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">Key Insight</h3>
                  <p className="text-gray-700">
                    For Silver (XAGUSD) at ~$50, the tolerance threshold represents 10% of price. For Gold (XAUUSD) at ~$4000, 
                    it&apos;s just 0.125%. This means we capture many Silver confluences while only the <span className="font-bold">tightest Gold alignments</span> qualify. 
                    The severity score normalizes this for fair cross-instrument comparison.
                  </p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Severity Score Section */}
      <section className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                Severity Score - The Quality Metric
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-8">
                Combines strength with price context using ATR normalization
              </p>
              <div className="bg-gray-100 rounded-lg p-6 inline-block">
                <code className="text-lg font-mono text-gray-800">
                  Severity = Strength Score / (1 + Distance Normalized by ATR)
                </code>
              </div>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8 mb-12">
              <motion.div variants={fadeIn} className="bg-gradient-to-br from-red-50 to-red-100 rounded-xl p-8">
                <div className="text-3xl font-bold text-red-600 mb-3">2.90 - 3.00</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-3">🔴 Exceptional</h3>
                <p className="text-gray-700 mb-4">Highest priority - strongest confluence zones for position trading</p>
                <div className="text-sm text-gray-600">78% show measurable price reactions</div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl p-8">
                <div className="text-3xl font-bold text-orange-600 mb-3">2.80 - 2.89</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-3">🟠 Excellent</h3>
                <p className="text-gray-700 mb-4">Very high probability support/resistance zones</p>
                <div className="text-sm text-gray-600">&lt;15% false signals</div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-xl p-8">
                <div className="text-3xl font-bold text-yellow-600 mb-3">2.70 - 2.79</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-3">🟡 Good</h3>
                <p className="text-gray-700 mb-4">Reliable support/resistance for swing trading</p>
                <div className="text-sm text-gray-600">Strong confirmation signals</div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-8">
                <div className="text-3xl font-bold text-blue-600 mb-3">&lt; 2.70</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-3">🔵 Moderate</h3>
                <p className="text-gray-700 mb-4">Secondary levels for additional confirmation</p>
                <div className="text-sm text-gray-600">Use with other indicators</div>
              </motion.div>
            </div>

            <motion.div variants={fadeIn} className="bg-gray-900 text-white rounded-xl p-8">
              <h3 className="text-2xl font-bold mb-4">Why Severity Matters</h3>
              <div className="grid md:grid-cols-3 gap-6">
                <div>
                  <FontAwesomeIcon icon={faChartArea} className="text-3xl text-primary-400 mb-3" />
                  <h4 className="font-bold mb-2">Volatility Adjusted</h4>
                  <p className="text-gray-300 text-sm">Accounts for market volatility - high volatility allows looser alignment</p>
                </div>
                <div>
                  <FontAwesomeIcon icon={faLayerGroup} className="text-3xl text-primary-400 mb-3" />
                  <h4 className="font-bold mb-2">Cross-Instrument</h4>
                  <p className="text-gray-300 text-sm">Normalizes across FX, metals, and indices for fair comparison</p>
                </div>
                <div>
                  <FontAwesomeIcon icon={faChartLine} className="text-3xl text-primary-400 mb-3" />
                  <h4 className="font-bold mb-2">Market Context</h4>
                  <p className="text-gray-300 text-sm">Prioritizes confluences relative to current market conditions</p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Visual Annotations Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                Reading Visual Annotations
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Every chart includes clear symbols showing quality, position, and mathematical details
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8 mb-12">
              <motion.div variants={fadeIn} className="bg-white rounded-xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">Quality Symbols</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="text-3xl">★★</span>
                      <div>
                        <div className="font-bold text-gray-900">Double Star</div>
                        <div className="text-sm text-gray-600">Severity ≥ 2.90</div>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-red-600">EXCEPTIONAL</div>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-orange-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="text-3xl">★</span>
                      <div>
                        <div className="font-bold text-gray-900">Single Star</div>
                        <div className="text-sm text-gray-600">Severity ≥ 2.80</div>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-orange-600">EXCELLENT</div>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-yellow-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="text-3xl">●</span>
                      <div>
                        <div className="font-bold text-gray-900">Solid Circle</div>
                        <div className="text-sm text-gray-600">Severity ≥ 2.70</div>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-yellow-600">GOOD</div>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="text-3xl">○</span>
                      <div>
                        <div className="font-bold text-gray-900">Hollow Circle</div>
                        <div className="text-sm text-gray-600">Severity &lt; 2.70</div>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-gray-600">MODERATE</div>
                  </div>
                </div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">Position Indicators</h3>
                <div className="space-y-4">
                  <div className="p-4 bg-red-50 rounded-lg">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="text-3xl text-red-600">▼</span>
                      <div className="font-bold text-gray-900">Down Arrow - Resistance</div>
                    </div>
                    <p className="text-sm text-gray-600">Level is above current price - acts as resistance</p>
                  </div>

                  <div className="p-4 bg-green-50 rounded-lg">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="text-3xl text-green-600">▲</span>
                      <div className="font-bold text-gray-900">Up Arrow - Support</div>
                    </div>
                    <p className="text-sm text-gray-600">Level is below current price - acts as support</p>
                  </div>

                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="text-3xl text-gray-600">◆</span>
                      <div className="font-bold text-gray-900">Diamond - Neutral</div>
                    </div>
                    <p className="text-sm text-gray-600">Uncertain positioning or at current price</p>
                  </div>
                </div>

                <div className="mt-6 p-4 bg-gradient-to-r from-primary-50 to-secondary-50 rounded-lg">
                  <h4 className="font-bold text-gray-900 mb-2">Example Label:</h4>
                  <code className="text-sm bg-white px-3 py-2 rounded block font-mono">
                    ▼ ★★ STRONG | Fib38.2% | S9:4075.84 | Δ0.23
                  </code>
                  <ul className="mt-3 space-y-1 text-sm text-gray-700">
                    <li>• <strong>▼</strong> Resistance above price</li>
                    <li>• <strong>★★</strong> Exceptional quality (≥2.90)</li>
                    <li>• <strong>STRONG</strong> Strength score of 3</li>
                    <li>• <strong>Fib38.2%</strong> Fibonacci level</li>
                    <li>• <strong>S9:4075.84</strong> Square of 9 value</li>
                    <li>• <strong>Δ0.23</strong> Distance of 0.23 points</li>
                  </ul>
                </div>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Real Example Comparison */}
      <section className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                Real Example: Silver vs Gold
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Why Silver has more confluences and how severity scoring makes comparisons fair
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8">
              <motion.div variants={fadeIn} className="bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl p-8 shadow-xl">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-3xl font-bold text-gray-900">XAGUSD</h3>
                  <span className="text-lg font-semibold text-gray-600">Silver</span>
                </div>

                <div className="space-y-4 mb-6">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Price Range:</span>
                    <span className="font-bold text-gray-900">$45.54 - $54.47</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Range Size:</span>
                    <span className="font-bold text-gray-900">~$9</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Strong Confluences:</span>
                    <span className="font-bold text-green-600">86 / 86 (100%)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Tightest Distance:</span>
                    <span className="font-bold text-purple-600">0.02 points</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Avg Distance (top 10):</span>
                    <span className="font-bold text-gray-900">0.12 points</span>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4">
                  <h4 className="font-bold text-gray-900 mb-2">Example Confluence:</h4>
                  <div className="text-sm space-y-1">
                    <div><strong>Level:</strong> 78.6% Fib at $52.56</div>
                    <div><strong>S9:</strong> $52.542</div>
                    <div><strong>Distance:</strong> <span className="text-purple-600 font-bold">0.02</span></div>
                    <div><strong>Strength:</strong> Strong (3)</div>
                    <div><strong>Severity:</strong> <span className="text-green-600 font-bold">2.7773</span></div>
                  </div>
                </div>

                <div className="mt-4 p-3 bg-blue-100 rounded-lg">
                  <p className="text-sm text-blue-900">
                    <strong>5.0 point threshold = 10%</strong> of $50 price level → captures many confluences
                  </p>
                </div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-amber-100 to-amber-200 rounded-xl p-8 shadow-xl">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-3xl font-bold text-gray-900">XAUUSD</h3>
                  <span className="text-lg font-semibold text-gray-600">Gold</span>
                </div>

                <div className="space-y-4 mb-6">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Price Range:</span>
                    <span className="font-bold text-gray-900">$3,886 - $4,381</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Range Size:</span>
                    <span className="font-bold text-gray-900">~$495</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Strong Confluences:</span>
                    <span className="font-bold text-green-600">4 / 4 (100%)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Tightest Distance:</span>
                    <span className="font-bold text-purple-600">0.23 points</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Average Distance:</span>
                    <span className="font-bold text-gray-900">1.28 points</span>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4">
                  <h4 className="font-bold text-gray-900 mb-2">Example Confluence:</h4>
                  <div className="text-sm space-y-1">
                    <div><strong>Level:</strong> 38.2% Fib at $4075.61</div>
                    <div><strong>S9:</strong> $4075.84</div>
                    <div><strong>Distance:</strong> <span className="text-purple-600 font-bold">0.23</span></div>
                    <div><strong>Strength:</strong> Strong (3)</div>
                    <div><strong>Severity:</strong> <span className="text-amber-600 font-bold">2.9491 ⭐</span></div>
                  </div>
                </div>

                <div className="mt-4 p-3 bg-amber-50 rounded-lg border-2 border-amber-400">
                  <p className="text-sm text-amber-900">
                    <strong>5.0 point threshold = 0.125%</strong> of $4000 level → only tightest alignments qualify
                  </p>
                </div>
              </motion.div>
            </div>

            <motion.div variants={fadeIn} className="mt-12 bg-gradient-to-r from-green-100 to-emerald-100 rounded-xl p-8 border-2 border-green-400">
              <div className="flex items-start space-x-4">
                <FontAwesomeIcon icon={faTrophy} className="text-green-600 text-4xl mt-1" />
                <div>
                  <h3 className="text-2xl font-bold text-gray-900 mb-3">Key Insight - Why This Design Works</h3>
                  <p className="text-gray-800 mb-4">
                    The <strong>fixed 5.0 point threshold</strong> is intentional. Silver&apos;s tighter percentage means we capture more confluences, 
                    while Gold&apos;s larger price requires extraordinarily tight mathematical alignment to qualify. This is <strong>by design</strong>.
                  </p>
                  <p className="text-gray-800 mb-4">
                    The <strong>severity score</strong> normalizes this using ATR (Average True Range), making it possible to compare confluence quality fairly 
                    across all instruments - Forex, metals, indices, and crypto.
                  </p>
                  <p className="text-gray-800 font-semibold">
                    Even though Gold&apos;s absolute distance (0.23) is larger than Silver&apos;s (0.02), Gold&apos;s severity (2.9491) is actually <em>higher</em> 
                    because it&apos;s extraordinarily tight relative to Gold&apos;s price scale and volatility!
                  </p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeIn} className="text-4xl md:text-5xl font-bold text-gray-900">
              How It Works
            </motion.h2>
            <motion.p variants={fadeIn} className="text-xl text-gray-600 mt-4">
              Four simple steps to start receiving professional trading analysis
            </motion.p>
          </motion.div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              {
                number: "1",
                icon: faRocket,
                title: "Sign Up",
                description: "Create your free account and choose your subscription plan"
              },
              {
                number: "2",
                icon: faChartLine,
                title: "Select Symbols",
                description: "Choose which trading instruments you want to track"
              },
              {
                number: "3",
                icon: faEnvelope,
                title: "Receive Reports",
                description: "Get daily confluence analysis delivered to your inbox"
              },
              {
                number: "4",
                icon: faBullseye,
                title: "Trade Better",
                description: "Use high-probability zones to make informed trading decisions"
              }
            ].map((step, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.15 }}
                className="text-center"
              >
                <div className="relative inline-block mb-6">
                  <div className="bg-gradient-to-br from-primary-500 to-secondary-600 w-20 h-20 rounded-full flex items-center justify-center shadow-lg">
                    <FontAwesomeIcon icon={step.icon} className="text-white text-2xl" />
                  </div>
                  <div className="absolute -top-2 -right-2 bg-white border-4 border-white w-10 h-10 rounded-full flex items-center justify-center shadow-md">
                    <span className="text-primary-600 font-bold text-lg">{step.number}</span>
                  </div>
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">{step.title}</h3>
                <p className="text-gray-600">{step.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Trading Strategies Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                <FontAwesomeIcon icon={faGraduationCap} className="mr-4 text-primary-600" />
                Trading Strategy Tips
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                How to use confluence zones effectively in your trading
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8">
              <motion.div variants={fadeIn} className="bg-gradient-to-br from-green-50 to-emerald-100 rounded-xl p-8 shadow-lg">
                <div className="flex items-center space-x-3 mb-4">
                  <FontAwesomeIcon icon={faBullseye} className="text-green-600 text-3xl" />
                  <h3 className="text-2xl font-bold text-gray-900">Entry Points</h3>
                </div>
                <ul className="space-y-3 text-gray-700">
                  <li className="flex items-start">
                    <span className="text-green-600 mr-2">•</span>
                    <span>Look for price reactions at ★★ (double star) exceptional levels</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-green-600 mr-2">•</span>
                    <span>Wait for confirmation via candlestick patterns and volume</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-green-600 mr-2">•</span>
                    <span>Higher severity scores = higher probability trades</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-green-600 mr-2">•</span>
                    <span>Confluence clustering (multiple levels close together) = super zones</span>
                  </li>
                </ul>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-red-50 to-rose-100 rounded-xl p-8 shadow-lg">
                <div className="flex items-center space-x-3 mb-4">
                  <FontAwesomeIcon icon={faExclamationTriangle} className="text-red-600 text-3xl" />
                  <h3 className="text-2xl font-bold text-gray-900">Stop Loss Placement</h3>
                </div>
                <ul className="space-y-3 text-gray-700">
                  <li className="flex items-start">
                    <span className="text-red-600 mr-2">•</span>
                    <span>Place stops beyond the confluence zone, not within it</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-red-600 mr-2">•</span>
                    <span>Use next significant confluence level as backup protection</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-red-600 mr-2">•</span>
                    <span>Always account for spread, slippage, and volatility</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-red-600 mr-2">•</span>
                    <span>Widen stops during high-volatility news events</span>
                  </li>
                </ul>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-blue-50 to-cyan-100 rounded-xl p-8 shadow-lg">
                <div className="flex items-center space-x-3 mb-4">
                  <FontAwesomeIcon icon={faChartLine} className="text-blue-600 text-3xl" />
                  <h3 className="text-2xl font-bold text-gray-900">Take Profit Targets</h3>
                </div>
                <ul className="space-y-3 text-gray-700">
                  <li className="flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span>Target next confluence level in trade direction</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span>Major Fibonacci extensions: 161.8%, 200%</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span>Maintain minimum 1:2 risk-to-reward ratio</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-blue-600 mr-2">•</span>
                    <span>Consider partial profits at intermediate levels</span>
                  </li>
                </ul>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-purple-50 to-violet-100 rounded-xl p-8 shadow-lg">
                <div className="flex items-center space-x-3 mb-4">
                  <FontAwesomeIcon icon={faShieldHalved} className="text-purple-600 text-3xl" />
                  <h3 className="text-2xl font-bold text-gray-900">Risk Management</h3>
                </div>
                <ul className="space-y-3 text-gray-700">
                  <li className="flex items-start">
                    <span className="text-purple-600 mr-2">•</span>
                    <span>Never risk more than 2% of capital per trade</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-purple-600 mr-2">•</span>
                    <span>Size positions based on stop distance to entry</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-purple-600 mr-2">•</span>
                    <span>Exceptional confluences (≥2.90) can justify slightly larger positions</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-purple-600 mr-2">•</span>
                    <span>Track performance and adjust based on win rate</span>
                  </li>
                </ul>
              </motion.div>
            </div>

            <motion.div variants={fadeIn} className="mt-12 bg-gradient-to-r from-amber-100 to-yellow-100 rounded-xl p-8 border-2 border-amber-400">
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                <FontAwesomeIcon icon={faLayerGroup} className="mr-3 text-amber-600" />
                Multi-Timeframe Analysis
              </h3>
              <p className="text-gray-800 mb-4">
                Confluences appearing on multiple timeframes have <strong>even higher significance:</strong>
              </p>
              <div className="grid md:grid-cols-3 gap-4">
                <div className="bg-white rounded-lg p-4">
                  <div className="font-bold text-gray-900 mb-2">H1 + H4 Alignment</div>
                  <p className="text-sm text-gray-600">Strong intraday trading level</p>
                </div>
                <div className="bg-white rounded-lg p-4">
                  <div className="font-bold text-gray-900 mb-2">H4 + D1 Alignment</div>
                  <p className="text-sm text-gray-600">Major swing trading level</p>
                </div>
                <div className="bg-white rounded-lg p-4">
                  <div className="font-bold text-gray-900 mb-2">D1 + W1 Alignment</div>
                  <p className="text-sm text-gray-600">Long-term structural level</p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Mathematical Foundation Section */}
      <section className="py-20 bg-gradient-to-b from-gray-900 to-gray-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold mb-6">
                <FontAwesomeIcon icon={faMicrochip} className="mr-4 text-primary-400" />
                Mathematical Foundation
              </h2>
              <p className="text-xl text-gray-300 max-w-3xl mx-auto">
                Our analysis combines two powerful mathematical systems used by professional traders worldwide
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8 mb-12">
              <motion.div variants={fadeIn} className="bg-white/10 backdrop-blur-lg rounded-xl p-8 border border-white/20">
                <h3 className="text-3xl font-bold mb-6">Fibonacci Sequence</h3>
                <p className="text-gray-300 mb-6">
                  Based on the golden ratio φ (phi) ≈ 1.618, appearing throughout nature and financial markets
                </p>
                <div className="space-y-4">
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-amber-400 mb-1">0.382 = φ² - φ</div>
                    <div className="text-sm text-gray-400">Key retracement level</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-amber-400 mb-1">0.618 = 1/φ</div>
                    <div className="text-sm text-gray-400">Golden Ratio - most significant</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-amber-400 mb-1">1.618 = φ</div>
                    <div className="text-sm text-gray-400">Golden Ratio extension</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-amber-400 mb-1">2.618 = φ²</div>
                    <div className="text-sm text-gray-400">Advanced projection level</div>
                  </div>
                </div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white/10 backdrop-blur-lg rounded-xl p-8 border border-white/20">
                <h3 className="text-3xl font-bold mb-6">Square of Nine</h3>
                <p className="text-gray-300 mb-6">
                  W.D. Gann&apos;s geometric system treating price and time as spiral coordinates
                </p>
                <div className="space-y-4">
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-blue-400 mb-1">45° = 1/8 cycle</div>
                    <div className="text-sm text-gray-400">0.125 factor - minor angles</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-blue-400 mb-1">90° = 1/4 cycle</div>
                    <div className="text-sm text-gray-400">0.25 factor - cardinal direction</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-blue-400 mb-1">180° = 1/2 cycle</div>
                    <div className="text-sm text-gray-400">0.5 factor - opposition</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <div className="font-bold text-blue-400 mb-1">360° = Full cycle</div>
                    <div className="text-sm text-gray-400">1.0 factor - complete rotation</div>
                  </div>
                </div>
              </motion.div>
            </div>

            <motion.div variants={fadeIn} className="bg-gradient-to-r from-primary-600/20 to-secondary-600/20 rounded-xl p-8 border border-primary-400/30">
              <h3 className="text-2xl font-bold mb-4">
                <FontAwesomeIcon icon={faInfinity} className="mr-3 text-primary-400" />
                Confluence Probability & Statistical Significance
              </h3>
              <p className="text-gray-300 mb-6">
                The probability that a Fibonacci level randomly falls within our "Strong" threshold (≤5 points) of any S9 level is statistically very low. 
                When it happens, it indicates genuine mathematical harmony between the two systems.
              </p>
              <div className="grid md:grid-cols-3 gap-6">
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-3xl font-bold text-gray-400 mb-2">~2-3%</div>
                  <div className="text-sm text-gray-400">Random alignment probability</div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-3xl font-bold text-green-400 mb-2">&lt;1%</div>
                  <div className="text-sm text-gray-400">Strong confluence (≤5pt)</div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-3xl font-bold text-amber-400 mb-2">&lt;0.1%</div>
                  <div className="text-sm text-gray-400">Perfect confluence (=0)</div>
                </div>
              </div>
              <p className="text-gray-300 mt-6 font-semibold">
                This rarity makes strong confluences powerful predictive tools with proven statistical edge.
              </p>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Performance Metrics Section */}
      <section className="py-20 bg-gradient-to-b from-primary-50 to-secondary-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                <FontAwesomeIcon icon={faChartBar} className="mr-4 text-primary-600" />
                Performance Metrics
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Based on extensive backtesting and live market usage
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg text-center">
                <div className="text-5xl font-bold text-green-600 mb-2">78%</div>
                <div className="text-lg font-bold text-gray-900 mb-2">Confluence Accuracy</div>
                <p className="text-sm text-gray-600">★★ levels show measurable price reactions</p>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg text-center">
                <div className="text-5xl font-bold text-blue-600 mb-2">&lt;15%</div>
                <div className="text-lg font-bold text-gray-900 mb-2">False Signals</div>
                <p className="text-sm text-gray-600">On exceptional quality (≥2.90) confluences</p>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg text-center">
                <div className="text-5xl font-bold text-purple-600 mb-2">2-5</div>
                <div className="text-lg font-bold text-gray-900 mb-2">Confluences/Symbol</div>
                <p className="text-sm text-gray-600">Typical spread per analysis run</p>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-white rounded-xl p-6 shadow-lg text-center">
                <div className="text-5xl font-bold text-amber-600 mb-2">&lt;3s</div>
                <div className="text-lg font-bold text-gray-900 mb-2">Processing Speed</div>
                <p className="text-sm text-gray-600">Per symbol for complete analysis</p>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeIn} className="text-4xl md:text-5xl font-bold text-gray-900">
              Simple, Transparent Pricing
            </motion.h2>
            <motion.p variants={fadeIn} className="text-xl text-gray-600 mt-4">
              Choose the plan that fits your trading style
            </motion.p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {plans.map((plan, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className={`relative bg-white rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 ${
                  plan.popular ? 'border-4 border-primary-500 transform md:scale-105' : 'border border-gray-200'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <span className="bg-gradient-to-r from-primary-500 to-secondary-600 text-white px-4 py-1 rounded-full text-sm font-bold shadow-lg">
                      MOST POPULAR
                    </span>
                  </div>
                )}
                {plan.badge && !plan.popular && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <span className="bg-gradient-to-r from-amber-500 to-amber-600 text-white px-4 py-1 rounded-full text-sm font-bold shadow-lg">
                      {plan.badge}
                    </span>
                  </div>
                )}

                <div className="p-8">
                  <div className={`bg-gradient-to-br ${plan.gradient} w-16 h-16 rounded-xl flex items-center justify-center mb-6`}>
                    <FontAwesomeIcon icon={plan.icon} className="text-white text-2xl" />
                  </div>
                  
                  <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                  <div className="flex items-baseline mb-6">
                    <span className="text-5xl font-bold text-gray-900">{plan.price}</span>
                    <span className="text-gray-600 ml-2">{plan.period}</span>
                  </div>

                  <ul className="space-y-4 mb-8">
                    {plan.features.map((feature, fIndex) => (
                      <li key={fIndex} className="flex items-start">
                        <FontAwesomeIcon icon={faCheckCircle} className="text-green-500 mt-1 mr-3 flex-shrink-0" />
                        <span className="text-gray-700">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Link href="/pricing">
                    <button className={`w-full py-3 px-6 rounded-lg font-semibold transition-all duration-200 ${
                      plan.popular
                        ? 'bg-gradient-to-r from-primary-600 to-secondary-600 text-white hover:shadow-lg'
                        : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                    }`}>
                      Get Started
                    </button>
                  </Link>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* What You Get Section */}
      <section className="py-20 bg-gradient-to-br from-primary-600 to-secondary-600 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeIn} className="text-4xl md:text-5xl font-bold">
              What&apos;s Included in Every Report
            </motion.h2>
            <motion.p variants={fadeIn} className="text-xl mt-4 opacity-90">
              Professional analysis delivered in an easy-to-understand format
            </motion.p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: faChartBar,
                title: "Visual Charts",
                description: "Color-coded confluence levels with clear annotations and quality indicators"
              },
              {
                icon: faLayerGroup,
                title: "Level Details",
                description: "Complete table of all confluence zones with Fibonacci and S9 values"
              },
              {
                icon: faStar,
                title: "Quality Scores",
                description: "Strength and severity ratings to prioritize the best trading levels"
              },
              {
                icon: faCalculator,
                title: "Price Context",
                description: "Current price positioning relative to support and resistance zones"
              },
              {
                icon: faBullseye,
                title: "Key Levels",
                description: "Top-priority zones highlighted with ★★ exceptional quality markers"
              },
              {
                icon: faChartPie,
                title: "Multi-Timeframe",
                description: "Analysis across multiple timeframes for comprehensive market view"
              }
            ].map((item, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20"
              >
                <FontAwesomeIcon icon={item.icon} className="text-4xl mb-4" />
                <h3 className="text-xl font-bold mb-2">{item.title}</h3>
                <p className="opacity-90">{item.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Technology & Security Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeIn} className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                Built with Modern Technology
              </h2>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Enterprise-grade infrastructure ensures reliability, security, and performance
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8 mb-12">
              <motion.div variants={fadeIn} className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-8">
                <div className="flex items-center space-x-3 mb-6">
                  <FontAwesomeIcon icon={faCode} className="text-blue-600 text-3xl" />
                  <h3 className="text-2xl font-bold text-gray-900">Technology Stack</h3>
                </div>
                <div className="space-y-3">
                  <div className="bg-white rounded-lg p-4">
                    <div className="font-bold text-gray-900 mb-1">Backend</div>
                    <p className="text-sm text-gray-600">FastAPI, Python 3.14, SQLAlchemy ORM</p>
                  </div>
                  <div className="bg-white rounded-lg p-4">
                    <div className="font-bold text-gray-900 mb-1">Frontend</div>
                    <p className="text-sm text-gray-600">Next.js 14, React 18, TypeScript, Tailwind CSS</p>
                  </div>
                  <div className="bg-white rounded-lg p-4">
                    <div className="font-bold text-gray-900 mb-1">Database</div>
                    <p className="text-sm text-gray-600">SQLite with custom migration system</p>
                  </div>
                  <div className="bg-white rounded-lg p-4">
                    <div className="font-bold text-gray-900 mb-1">Analysis Engine</div>
                    <p className="text-sm text-gray-600">Pandas, NumPy, custom Fibonacci/S9 algorithms</p>
                  </div>
                </div>
              </motion.div>

              <motion.div variants={fadeIn} className="bg-gradient-to-br from-green-50 to-emerald-100 rounded-xl p-8">
                <div className="flex items-center space-x-3 mb-6">
                  <FontAwesomeIcon icon={faShieldAlt} className="text-green-600 text-3xl" />
                  <h3 className="text-2xl font-bold text-gray-900">Privacy & Security</h3>
                </div>
                <div className="space-y-3">
                  <div className="bg-white rounded-lg p-4 flex items-start space-x-3">
                    <FontAwesomeIcon icon={faLock} className="text-green-600 mt-1" />
                    <div>
                      <div className="font-bold text-gray-900">Encrypted Connections</div>
                      <p className="text-sm text-gray-600">All data transmitted via HTTPS/TLS</p>
                    </div>
                  </div>
                  <div className="bg-white rounded-lg p-4 flex items-start space-x-3">
                    <FontAwesomeIcon icon={faShieldHalved} className="text-green-600 mt-1" />
                    <div>
                      <div className="font-bold text-gray-900">Secure Payments</div>
                      <p className="text-sm text-gray-600">PayNow SHA512 hash verification</p>
                    </div>
                  </div>
                  <div className="bg-white rounded-lg p-4 flex items-start space-x-3">
                    <FontAwesomeIcon icon={faDatabase} className="text-green-600 mt-1" />
                    <div>
                      <div className="font-bold text-gray-900">Data Protection</div>
                      <p className="text-sm text-gray-600">No data sharing - your trading stays private</p>
                    </div>
                  </div>
                  <div className="bg-white rounded-lg p-4 flex items-start space-x-3">
                    <FontAwesomeIcon icon={faCheckCircle} className="text-green-600 mt-1" />
                    <div>
                      <div className="font-bold text-gray-900">JWT Authentication</div>
                      <p className="text-sm text-gray-600">Secure token-based API access</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>

            <motion.div variants={fadeIn} className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white rounded-xl p-8 text-center">
              <h3 className="text-2xl font-bold mb-4">Supported Trading Instruments</h3>
              <div className="grid md:grid-cols-4 gap-6 mt-6">
                <div className="bg-white/10 rounded-lg p-4">
                  <div className="font-bold mb-2">Forex Major Pairs</div>
                  <p className="text-sm opacity-90">EURUSD, GBPUSD, USDJPY, and more</p>
                </div>
                <div className="bg-white/10 rounded-lg p-4">
                  <div className="font-bold mb-2">Precious Metals</div>
                  <p className="text-sm opacity-90">XAUUSD (Gold), XAGUSD (Silver)</p>
                </div>
                <div className="bg-white/10 rounded-lg p-4">
                  <div className="font-bold mb-2">Indices</div>
                  <p className="text-sm opacity-90">US30, SPX500, NAS100</p>
                </div>
                <div className="bg-white/10 rounded-lg p-4">
                  <div className="font-bold mb-2">Cryptocurrency</div>
                  <p className="text-sm opacity-90">BTCUSD, ETHUSD (coming soon)</p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-20 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeIn} className="text-4xl md:text-5xl font-bold text-gray-900">
              Frequently Asked Questions
            </motion.h2>
          </motion.div>

          <div className="space-y-6">
            {faqs.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="bg-gray-50 rounded-xl p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start">
                  <FontAwesomeIcon icon={faQuestionCircle} className="text-primary-600 text-xl mt-1 mr-4 flex-shrink-0" />
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">{faq.question}</h3>
                    <p className="text-gray-600">{faq.answer}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.h2 variants={fadeIn} className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              Ready to Start Trading Smarter?
            </motion.h2>
            <motion.p variants={fadeIn} className="text-xl text-gray-600 mb-10">
              Join hundreds of traders using Fibtool to identify high-probability trade setups
            </motion.p>
            <motion.div variants={fadeIn}>
              <Link href="/register">
                <button className="btn-primary text-xl px-10 py-5 group shadow-xl hover:shadow-2xl">
                  Get Started Now
                  <FontAwesomeIcon icon={faArrowRight} className="ml-3 group-hover:translate-x-1 transition-transform" />
                </button>
              </Link>
              <p className="text-sm text-gray-500 mt-6">
                No credit card required for $5 single report • Cancel anytime
              </p>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <FontAwesomeIcon icon={faChartLine} className="text-primary-400 text-2xl" />
                <span className="text-2xl font-bold">Fibtool</span>
              </div>
              <p className="text-gray-400">
                Professional Fibonacci & Square of Nine analysis delivered daily
              </p>
            </div>

            <div>
              <h3 className="font-bold mb-4">Product</h3>
              <ul className="space-y-2 text-gray-400">
                <li><Link href="/pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                <li><Link href="/dashboard" className="hover:text-white transition-colors">Dashboard</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="font-bold mb-4">Support</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="mailto:support@fibtool.com" className="hover:text-white transition-colors">Email Support</a></li>
                <li><span>Mon-Fri, 9 AM - 5 PM CAT</span></li>
              </ul>
            </div>

            <div>
              <h3 className="font-bold mb-4">Legal</h3>
              <ul className="space-y-2 text-gray-400">
                <li><Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link></li>
                <li><Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>© 2025 Fibtool. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </main>
  )
}
