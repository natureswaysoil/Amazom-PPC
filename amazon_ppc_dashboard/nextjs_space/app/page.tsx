'use client';

import { useEffect, useState } from 'react';

interface OptimizationResult {
  timestamp: string;
  run_id: string;
  status: string;
  keywords_optimized: number;
  bids_increased: number;
  bids_decreased: number;
  average_acos: number;
  total_spend: number;
  total_sales: number;
  duration_seconds: number;
}

interface SummaryData {
  date: string;
  optimization_runs: number;
  total_keywords_optimized: number;
  avg_acos: number;
  total_spend: number;
  total_sales: number;
}

export default function Home() {
  const [recentResults, setRecentResults] = useState<OptimizationResult[]>([]);
  const [summary, setSummary] = useState<SummaryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchDashboardData, 300000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch recent optimization results
      const resultsResponse = await fetch('/api/bigquery-data?table=optimization_results&limit=5&days=7');
      const resultsData = await resultsResponse.json();
      
      if (!resultsResponse.ok) {
        // Extract detailed error message from the response body
        const errorMsg = resultsData.message || resultsData.error || resultsResponse.statusText || 'Unknown error';
        throw new Error(`Failed to fetch optimization results: ${errorMsg}`);
      }

      // Fetch summary data
      const summaryResponse = await fetch('/api/bigquery-data?table=summary&days=7');
      const summaryData = await summaryResponse.json();
      
      if (!summaryResponse.ok) {
        // Extract detailed error message from the response body
        const errorMsg = summaryData.message || summaryData.error || summaryResponse.statusText || 'Unknown error';
        throw new Error(`Failed to fetch summary data: ${errorMsg}`);
      }

      if (resultsData.success) {
        setRecentResults(resultsData.data);
      } else {
        setError(resultsData.message || resultsData.error || 'Failed to fetch data');
      }

      if (summaryData.success) {
        setSummary(summaryData.data);
      } else if (!resultsData.success) {
        // Only set error from summaryData if resultsData didn't already set an error
        setError(summaryData.message || summaryData.error || 'Failed to fetch summary data');
      }

      setLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch dashboard data');
      setLoading(false);
    }
  };

  const formatDate = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return (value * 100).toFixed(2) + '%';
  };

  if (loading && recentResults.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingCard}>
          <h1 style={styles.title}>🚀 Amazon PPC Optimizer Dashboard</h1>
          <p>Loading optimization data from BigQuery...</p>
        </div>
      </div>
    );
  }

  if (error && recentResults.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.errorCard}>
          <h1 style={styles.title}>🚀 Amazon PPC Optimizer Dashboard</h1>
          <div style={styles.errorBox}>
            <p><strong>⚠️ Error Loading Data:</strong></p>
            <p>{error}</p>
            {error.includes('Not found') && (
              <div style={styles.setupInstructions}>
                <p><strong>Setup Required:</strong></p>
                <ol style={{ textAlign: 'left', lineHeight: '1.8' }}>
                  <li>Run: <code>./setup-bigquery.sh</code></li>
                  <li>Grant permissions to service account</li>
                  <li>Trigger an optimization run</li>
                </ol>
                <p style={{ fontSize: '14px', marginTop: '10px' }}>
                  See BIGQUERY_INTEGRATION.md for details
                </p>
              </div>
            )}
          </div>
          <button onClick={fetchDashboardData} style={styles.retryButton}>
            🔄 Retry
          </button>
        </div>
      </div>
    );
  }

  const totalOptimizationRuns = summary.reduce((sum, s) => sum + s.optimization_runs, 0);
  const totalKeywordsOptimized = summary.reduce((sum, s) => sum + s.total_keywords_optimized, 0);
  const avgAcos = summary.length > 0
    ? summary.reduce((sum, s) => sum + s.avg_acos, 0) / summary.length
    : 0;
  const totalSpend = summary.reduce((sum, s) => sum + s.total_spend, 0);
  const totalSales = summary.reduce((sum, s) => sum + s.total_sales, 0);

  return (
    <div style={styles.dashboardContainer}>
      <header style={styles.header}>
        <h1 style={styles.headerTitle}>🚀 Amazon PPC Optimizer Dashboard</h1>
        <p style={styles.headerSubtitle}>Real-time data from BigQuery</p>
        <button onClick={fetchDashboardData} style={styles.refreshButton}>
          🔄 Refresh
        </button>
      </header>

      <div style={styles.statsGrid}>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>Optimization Runs (7d)</div>
          <div style={styles.statValue}>{totalOptimizationRuns}</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>Keywords Optimized</div>
          <div style={styles.statValue}>{totalKeywordsOptimized}</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>Average ACOS</div>
          <div style={styles.statValue}>{formatPercent(avgAcos)}</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>Total Spend (7d)</div>
          <div style={styles.statValue}>{formatCurrency(totalSpend)}</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>Total Sales (7d)</div>
          <div style={styles.statValue}>{formatCurrency(totalSales)}</div>
        </div>
      </div>

      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>📊 Recent Optimization Runs</h2>
        {recentResults.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            No optimization runs found. Trigger an optimization to see data here.
          </p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Timestamp</th>
                <th style={styles.th}>Status</th>
                <th style={styles.th}>Keywords</th>
                <th style={styles.th}>Bids ↑</th>
                <th style={styles.th}>Bids ↓</th>
                <th style={styles.th}>ACOS</th>
                <th style={styles.th}>Spend</th>
                <th style={styles.th}>Sales</th>
                <th style={styles.th}>Duration</th>
              </tr>
            </thead>
            <tbody>
              {recentResults.map((result, index) => (
                <tr key={result.run_id} style={index % 2 === 0 ? styles.evenRow : styles.oddRow}>
                  <td style={styles.td}>{formatDate(result.timestamp)}</td>
                  <td style={styles.td}>
                    <span style={result.status === 'success' ? styles.successBadge : styles.errorBadge}>
                      {result.status}
                    </span>
                  </td>
                  <td style={styles.td}>{result.keywords_optimized}</td>
                  <td style={styles.td}>{result.bids_increased}</td>
                  <td style={styles.td}>{result.bids_decreased}</td>
                  <td style={styles.td}>{formatPercent(result.average_acos)}</td>
                  <td style={styles.td}>{formatCurrency(result.total_spend)}</td>
                  <td style={styles.td}>{formatCurrency(result.total_sales)}</td>
                  <td style={styles.td}>{result.duration_seconds.toFixed(1)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={styles.footer}>
        <p>Data refreshes automatically every 5 minutes</p>
        <p style={{ fontSize: '12px', marginTop: '5px' }}>
          Powered by BigQuery | Last updated: {new Date().toLocaleString()}
        </p>
      </div>
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    padding: '20px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  loadingCard: {
    background: 'white',
    padding: '40px',
    borderRadius: '15px',
    boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
    textAlign: 'center',
    maxWidth: '500px',
  },
  errorCard: {
    background: 'white',
    padding: '40px',
    borderRadius: '15px',
    boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
    textAlign: 'center',
    maxWidth: '600px',
  },
  errorBox: {
    background: '#fff3cd',
    border: '1px solid #ffc107',
    padding: '20px',
    borderRadius: '8px',
    marginTop: '20px',
    marginBottom: '20px',
  },
  setupInstructions: {
    marginTop: '15px',
    padding: '15px',
    background: 'white',
    borderRadius: '5px',
  },
  retryButton: {
    background: '#667eea',
    color: 'white',
    border: 'none',
    padding: '12px 30px',
    borderRadius: '25px',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: 'bold',
  },
  dashboardContainer: {
    minHeight: '100vh',
    background: '#f5f5f5',
    padding: '20px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  header: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    padding: '30px',
    borderRadius: '15px',
    marginBottom: '20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '15px',
  },
  headerTitle: {
    margin: 0,
    fontSize: '28px',
  },
  headerSubtitle: {
    margin: '5px 0 0 0',
    opacity: 0.9,
  },
  refreshButton: {
    background: 'white',
    color: '#667eea',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '20px',
    fontSize: '14px',
    cursor: 'pointer',
    fontWeight: 'bold',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '15px',
    marginBottom: '20px',
  },
  statCard: {
    background: 'white',
    padding: '20px',
    borderRadius: '10px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
  },
  statLabel: {
    fontSize: '12px',
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '10px',
  },
  statValue: {
    fontSize: '28px',
    fontWeight: 'bold',
    color: '#667eea',
  },
  tableCard: {
    background: 'white',
    padding: '25px',
    borderRadius: '10px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
    overflowX: 'auto',
  },
  tableTitle: {
    margin: '0 0 20px 0',
    color: '#333',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  th: {
    textAlign: 'left',
    padding: '12px',
    borderBottom: '2px solid #e0e0e0',
    fontWeight: 'bold',
    color: '#666',
  },
  td: {
    padding: '12px',
    borderBottom: '1px solid #f0f0f0',
  },
  evenRow: {
    background: '#fafafa',
  },
  oddRow: {
    background: 'white',
  },
  successBadge: {
    background: '#d4edda',
    color: '#155724',
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 'bold',
  },
  errorBadge: {
    background: '#f8d7da',
    color: '#721c24',
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 'bold',
  },
  footer: {
    textAlign: 'center',
    marginTop: '30px',
    color: '#666',
    fontSize: '14px',
  },
  title: {
    color: '#667eea',
    marginBottom: '20px',
  },
};
