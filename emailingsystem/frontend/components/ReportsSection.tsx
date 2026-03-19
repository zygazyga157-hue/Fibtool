'use client'

import { useState, useEffect } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faFileAlt,
  faDownload,
  faEye,
  faCalendar,
  faChartLine,
  faClock,
  faCheckCircle,
  faSpinner,
  faExclamationTriangle,
  faFilter
} from '@fortawesome/free-solid-svg-icons'
import { motion } from 'framer-motion'
import axios from 'axios'

interface Report {
  id: string
  symbol: string
  symbol_id: number | null
  timeframe: string | null
  status: string
  report_type: string
  report_content: string | null
  has_file: boolean
  file_path: string | null
  email_sent_at: string | null
  download_count: number
  last_downloaded_at: string | null
  created_at: string
  error_message: string | null
}

interface ReportsListResponse {
  reports: Report[]
  total: number
}

export default function ReportsSection() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSymbol, setSelectedSymbol] = useState<string>('all')
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  const [showContentModal, setShowContentModal] = useState(false)

  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get<ReportsListResponse>(
        'http://localhost:8000/api/v1/reports',
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )
      setReports(response.data.reports)
    } catch (error) {
      console.error('Failed to load reports:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async (reportId: string, symbol: string) => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get(
        `http://localhost:8000/api/v1/reports/${reportId}/download`,
        {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      )
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${symbol}_${new Date().toISOString().split('T')[0]}.png`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      
      // Reload reports to update download count
      loadReports()
    } catch (error) {
      console.error('Failed to download report:', error)
      alert('Failed to download report')
    }
  }

  const handleViewContent = async (report: Report) => {
    setSelectedReport(report)
    setShowContentModal(true)
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'sent': return 'bg-green-100 text-green-700'
      case 'processing': return 'bg-blue-100 text-blue-700'
      case 'pending': return 'bg-yellow-100 text-yellow-700'
      case 'failed': return 'bg-red-100 text-red-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const uniqueSymbols = ['all', ...Array.from(new Set(reports.map(r => r.symbol)))]
  const filteredReports = selectedSymbol === 'all' 
    ? reports 
    : reports.filter(r => r.symbol === selectedSymbol)

  if (loading) {
    return (
      <div className="text-center py-12">
        <FontAwesomeIcon icon={faSpinner} className="text-primary-600 text-4xl animate-spin mb-4" />
        <p className="text-gray-600">Loading reports...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center">
          <FontAwesomeIcon icon={faFileAlt} className="text-primary-600 mr-3" />
          My Reports
        </h2>
        
        {/* Symbol Filter */}
        {reports.length > 0 && (
          <div className="flex items-center space-x-2">
            <FontAwesomeIcon icon={faFilter} className="text-gray-500" />
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {uniqueSymbols.map(symbol => (
                <option key={symbol} value={symbol}>
                  {symbol === 'all' ? 'All Symbols' : symbol}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {filteredReports.length === 0 ? (
        <div className="card text-center py-12">
          <FontAwesomeIcon icon={faFileAlt} className="text-gray-300 text-6xl mb-4" />
          <h3 className="text-xl font-bold text-gray-900 mb-2">No Reports Yet</h3>
          <p className="text-gray-600 mb-4">
            Your confluence analysis reports will appear here after you make a purchase.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredReports.map((report, index) => (
            <motion.div
              key={report.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className="card hover:shadow-xl transition-shadow"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <FontAwesomeIcon icon={faChartLine} className="text-primary-600 text-xl" />
                  <span className="font-bold text-lg text-gray-900">{report.symbol}</span>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(report.status)}`}>
                  {report.status}
                </span>
              </div>

              {/* Timeframe & Type */}
              <div className="mb-4 space-y-2">
                {report.timeframe && (
                  <div className="flex items-center text-sm text-gray-600">
                    <FontAwesomeIcon icon={faClock} className="mr-2" />
                    <span>Timeframe: {report.timeframe}</span>
                  </div>
                )}
                <div className="flex items-center text-sm text-gray-600">
                  <FontAwesomeIcon icon={faFileAlt} className="mr-2" />
                  <span className="capitalize">{report.report_type} Analysis</span>
                </div>
                <div className="flex items-center text-sm text-gray-600">
                  <FontAwesomeIcon icon={faCalendar} className="mr-2" />
                  <span>{new Date(report.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Download Stats */}
              {report.download_count > 0 && (
                <div className="mb-4 text-sm text-gray-500">
                  <FontAwesomeIcon icon={faDownload} className="mr-2" />
                  Downloaded {report.download_count} time{report.download_count !== 1 ? 's' : ''}
                </div>
              )}

              {/* Error Message */}
              {report.error_message && report.status === 'FAILED' && (
                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3">
                  <div className="flex items-start">
                    <FontAwesomeIcon icon={faExclamationTriangle} className="text-red-600 mt-1 mr-2" />
                    <p className="text-red-700 text-xs">{report.error_message}</p>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex space-x-2">
                {report.has_file && (
                  <button
                    onClick={() => handleDownload(report.id, report.symbol)}
                    className="flex-1 bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg font-semibold transition-colors flex items-center justify-center space-x-2"
                  >
                    <FontAwesomeIcon icon={faDownload} />
                    <span>Download</span>
                  </button>
                )}
                {report.report_content && (
                  <button
                    onClick={() => handleViewContent(report)}
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg font-semibold transition-colors flex items-center justify-center space-x-2"
                  >
                    <FontAwesomeIcon icon={faEye} />
                    <span>View</span>
                  </button>
                )}
              </div>

              {/* Sent Status */}
              {report.email_sent_at && (
                <div className="mt-3 text-xs text-gray-500 flex items-center">
                  <FontAwesomeIcon icon={faCheckCircle} className="text-green-500 mr-1" />
                  Sent via email on {new Date(report.email_sent_at).toLocaleString()}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}

      {/* Report Content Modal */}
      {showContentModal && selectedReport && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowContentModal(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-2xl font-bold">{selectedReport.symbol} Analysis Report</h3>
                  <p className="text-primary-100 mt-1">
                    {new Date(selectedReport.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => setShowContentModal(false)}
                  className="text-white hover:text-gray-200 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
              <div className="prose max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-gray-700 leading-relaxed">
                  {selectedReport.report_content}
                </pre>
              </div>

              {selectedReport.has_file && (
                <div className="mt-6 pt-6 border-t">
                  <button
                    onClick={() => handleDownload(selectedReport.id, selectedReport.symbol)}
                    className="btn-primary w-full"
                  >
                    <FontAwesomeIcon icon={faDownload} className="mr-2" />
                    Download Chart
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
