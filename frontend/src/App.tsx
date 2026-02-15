import { useState, useEffect } from 'react'
import './App.css'

interface DashboardStats {
  total_revenue: number
  total_pending: number
  total_paid: number
  pending_invoices: number
  overdue_invoices: number
  low_stock_items: number
  pending_actions: number
}

interface Invoice {
  id: number
  invoice_number: string
  customer_name: string
  customer_phone: string
  amount: number
  gst_amount: number
  total: number
  status: string
  created_at: string
  days_pending?: number
}

interface PendingAction {
  id: number
  action_type: string
  confirmation_message: string
  status: string
  created_at: string
}

const API_BASE_URL = 'http://localhost:8000/api/v1'

export const App = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [overdueInvoices, setOverdueInvoices] = useState<Invoice[]>([])
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'invoices' | 'actions'>('overview')

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      
      // Fetch stats
      const statsRes = await fetch(`${API_BASE_URL}/dashboard/stats`)
      const statsData = await statsRes.json()
      setStats(statsData)

      // Fetch overdue invoices
      const invoicesRes = await fetch(`${API_BASE_URL}/dashboard/invoices/overdue`)
      const invoicesData = await invoicesRes.json()
      setOverdueInvoices(invoicesData)

      // Fetch pending actions
      const actionsRes = await fetch(`${API_BASE_URL}/dashboard/actions/pending`)
      const actionsData = await actionsRes.json()
      setPendingActions(actionsData)

    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmAction = async (actionId: number, confirmed: boolean) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/dashboard/actions/${actionId}/confirm?confirmed=${confirmed}`,
        { method: 'POST' }
      )
      
      if (response.ok) {
        alert(confirmed ? 'Action confirmed!' : 'Action cancelled!')
        fetchDashboardData()
      }
    } catch (error) {
      console.error('Error confirming action:', error)
      alert('Failed to process action')
    }
  }

  const formatCurrency = (amount: number) => `₹${amount.toFixed(2)}`

  if (loading) {
    return (
      <div className="app loading">
        <div className="spinner"></div>
        <p>Loading Bharat Biz-Agent Dashboard...</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>🤖 Bharat Biz-Agent</h1>
          <p className="tagline">Your AI-Powered Business Co-Pilot</p>
        </div>
        <div className="header-actions">
          <button className="btn-refresh" onClick={fetchDashboardData}>
            🔄 Refresh
          </button>
        </div>
      </header>

      <div className="tabs">
        <button 
          className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          📊 Overview
        </button>
        <button 
          className={`tab ${activeTab === 'invoices' ? 'active' : ''}`}
          onClick={() => setActiveTab('invoices')}
        >
          📄 Invoices
        </button>
        <button 
          className={`tab ${activeTab === 'actions' ? 'active' : ''}`}
          onClick={() => setActiveTab('actions')}
        >
          ⚡ Pending Actions
        </button>
      </div>

      <main className="main-content">
        {activeTab === 'overview' && stats && (
          <div className="overview">
            <div className="stats-grid">
              <div className="stat-card revenue">
                <div className="stat-icon">💰</div>
                <div className="stat-content">
                  <h3>Total Revenue</h3>
                  <p className="stat-value">{formatCurrency(stats.total_revenue)}</p>
                </div>
              </div>

              <div className="stat-card paid">
                <div className="stat-icon">✅</div>
                <div className="stat-content">
                  <h3>Collected</h3>
                  <p className="stat-value">{formatCurrency(stats.total_paid)}</p>
                </div>
              </div>

              <div className="stat-card pending">
                <div className="stat-icon">⏳</div>
                <div className="stat-content">
                  <h3>Pending</h3>
                  <p className="stat-value">{formatCurrency(stats.total_pending)}</p>
                  <p className="stat-subtitle">{stats.pending_invoices} invoices</p>
                </div>
              </div>

              <div className="stat-card overdue">
                <div className="stat-icon">⚠️</div>
                <div className="stat-content">
                  <h3>Overdue</h3>
                  <p className="stat-value">{stats.overdue_invoices}</p>
                  <p className="stat-subtitle">30+ days</p>
                </div>
              </div>

              <div className="stat-card stock">
                <div className="stat-icon">📦</div>
                <div className="stat-content">
                  <h3>Low Stock</h3>
                  <p className="stat-value">{stats.low_stock_items}</p>
                  <p className="stat-subtitle">items</p>
                </div>
              </div>

              <div className="stat-card actions">
                <div className="stat-icon">🔔</div>
                <div className="stat-content">
                  <h3>Pending Actions</h3>
                  <p className="stat-value">{stats.pending_actions}</p>
                  <p className="stat-subtitle">need confirmation</p>
                </div>
              </div>
            </div>

            <div className="quick-insights">
              <h2>Quick Insights</h2>
              <div className="insight-cards">
                <div className="insight-card">
                  <h4>💵 Collection Rate</h4>
                  <p className="insight-value">
                    {((stats.total_paid / stats.total_revenue) * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="insight-card">
                  <h4>🎯 Action Items</h4>
                  <p className="insight-text">
                    {stats.overdue_invoices > 0 && `${stats.overdue_invoices} overdue payments to chase`}
                    {stats.low_stock_items > 0 && ` • ${stats.low_stock_items} items need restocking`}
                    {stats.pending_actions > 0 && ` • ${stats.pending_actions} actions waiting`}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'invoices' && (
          <div className="invoices">
            <h2>⚠️ Overdue Invoices (30+ days)</h2>
            {overdueInvoices.length === 0 ? (
              <div className="empty-state">
                <p>🎉 Great! No overdue invoices.</p>
              </div>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Invoice #</th>
                      <th>Customer</th>
                      <th>Phone</th>
                      <th>Amount</th>
                      <th>Days Overdue</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overdueInvoices.map(invoice => (
                      <tr key={invoice.id}>
                        <td className="invoice-number">{invoice.invoice_number}</td>
                        <td>{invoice.customer_name}</td>
                        <td>{invoice.customer_phone}</td>
                        <td className="amount">{formatCurrency(invoice.total)}</td>
                        <td className="days-overdue">{invoice.days_pending} days</td>
                        <td>
                          <button className="btn-action">📱 Send Reminder</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'actions' && (
          <div className="pending-actions">
            <h2>⚡ Actions Awaiting Confirmation</h2>
            {pendingActions.length === 0 ? (
              <div className="empty-state">
                <p>✅ All caught up! No pending actions.</p>
              </div>
            ) : (
              <div className="actions-list">
                {pendingActions.map(action => (
                  <div key={action.id} className="action-card">
                    <div className="action-header">
                      <span className="action-type">{action.action_type}</span>
                      <span className="action-time">
                        {new Date(action.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="action-message">{action.confirmation_message}</p>
                    <div className="action-buttons">
                      <button 
                        className="btn-confirm"
                        onClick={() => handleConfirmAction(action.id, true)}
                      >
                        ✅ Confirm
                      </button>
                      <button 
                        className="btn-reject"
                        onClick={() => handleConfirmAction(action.id, false)}
                      >
                        ❌ Cancel
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Built for Indian Businesses with ❤️ | WhatsApp-First | Multilingual | AI-Powered</p>
      </footer>
    </div>
  )
}
