'use client';

import { useEffect, useState } from 'react';

interface Campaign {
  campaign_id: string;
  campaign_name: string;
  spend: number;
  sales: number;
  acos: number;
  keywords_count?: number;
  changes_made?: number;
}

interface TopPerformer {
  keyword_text: string;
  clicks: number;
  sales: number;
  acos: number;
  bid_change?: number;
}

interface ConfigSnapshot {
  target_acos?: number;
  lookback_days?: number;
  enabled_features?: string[];
}

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
  campaigns_analyzed?: number;
  negative_keywords_added?: number;
  budget_changes?: number;
  // Enhanced fields from DATA_FLOW_SUMMARY.md
  campaigns?: Campaign[];
  top_performers?: TopPerformer[];
  features?: any;
  errors?: string[];
  warnings?: string[];
  config_snapshot?: ConfigSnapshot;
}

interface SummaryData {
  date: string;
  optimization_runs: number;
  total_keywords_optimized: number;
  avg_acos: number;
  total_spend: number;
  total_sales: number;
}

type NavigationTab = 'overview' | 'campaigns' | 'automation' | 'discovery' | 'budget' | 'dayparting' | 'reports' | 'analytics' | 'performance' | 'hourly' | 'searchterms' | 'datatable' | 'settings';

export default function Home() {
  const [activeTab, setActiveTab] = useState<NavigationTab>('overview');
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

      // Fetch recent optimization results with increased limit and time range
      const resultsResponse = await fetch('/api/bigquery-data?table=optimization_results&limit=50&days=30');
      
      // Try to parse response body for detailed error message
      let resultsData;
      try {
        resultsData = await resultsResponse.json();
      } catch (jsonErr) {
        // If JSON parsing fails, throw error with status code
        if (!resultsResponse.ok) {
          throw new Error(`Failed to fetch optimization results: ${resultsResponse.status} ${resultsResponse.statusText}`);
        }
        throw jsonErr;
      }
      
      if (!resultsResponse.ok) {
        // Extract detailed error message from the response body
        const errorMsg = resultsData.message || resultsData.error || resultsResponse.statusText || 'Unknown error';
        throw new Error(`Failed to fetch optimization results: ${errorMsg}`);
      }

      // Fetch summary data with increased time range
      const summaryResponse = await fetch('/api/bigquery-data?table=summary&days=30');
      
      // Try to parse response body for detailed error message
      let summaryData;
      try {
        summaryData = await summaryResponse.json();
      } catch (jsonErr) {
        // If JSON parsing fails, throw error with status code
        if (!summaryResponse.ok) {
          throw new Error(`Failed to fetch summary data: ${summaryResponse.status} ${summaryResponse.statusText}`);
        }
        throw jsonErr;
      }
      
      if (!summaryResponse.ok) {
        // Extract detailed error message from the response body
        const errorMsg = summaryData.message || summaryData.error || summaryResponse.statusText || 'Unknown error';
        throw new Error(`Failed to fetch summary data: ${errorMsg}`);
      }

      if (resultsData.success) {
        const results = resultsData.data;
        
        // Log all keys in the first result object for debugging
        if (results && results.length > 0) {
          console.log('📊 Dashboard: Received optimization results');
          console.log('First result keys:', Object.keys(results[0]));
          console.log('First result sample:', results[0]);
          
          // Check for missing expected fields and warn
          const expectedFields = ['campaigns', 'top_performers', 'features', 'config_snapshot', 'errors', 'warnings'];
          const missingFields = expectedFields.filter(field => !(field in results[0]));
          
          if (missingFields.length > 0) {
            console.warn('⚠️ Missing expected fields in results:', missingFields);
            const warningMsg = `Some optimization data is incomplete. Missing fields: ${missingFields.join(', ')}. This may indicate the optimizer is not sending full payloads or the database schema needs updating.`;
            setError(warningMsg);
          }
        }
        
        setRecentResults(results);
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
            <p style={{ marginBottom: '15px' }}>{error}</p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginBottom: '15px' }}>
              <a href="/api/setup-guide" target="_blank" style={styles.helpLink}>
                📖 Setup Guide
              </a>
              <a href="/api/config-check" target="_blank" style={styles.helpLink}>
                🔍 Config Check
              </a>
              <a href="/api/bigquery-data?limit=1" target="_blank" style={styles.helpLink}>
                🧪 Test Connection
              </a>
            </div>
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
            {(error.includes('Missing Google Cloud credentials') || 
              error.includes('Configuration error') || 
              error.includes('not valid JSON') ||
              error.includes('base64') ||
              error.includes('BigQuery initialization failed')) && (
              <div style={styles.setupInstructions}>
                <p><strong>📋 Quick Fix:</strong></p>
                <p style={{ textAlign: 'left', marginBottom: '15px' }}>
                  The dashboard needs valid Google Cloud credentials to display live data from BigQuery.
                  This is a one-time setup that takes about 2 minutes.
                </p>
                <ol style={{ textAlign: 'left', lineHeight: '1.8' }}>
                  <li><strong>Get your service account key:</strong> Download the JSON file from Google Cloud Console → IAM & Admin → Service Accounts</li>
                  <li><strong>Set the credential:</strong> In your deployment platform (Vercel, etc.), set <code>GCP_SERVICE_ACCOUNT_KEY</code> to the contents of the JSON file</li>
                  <li><strong>Alternative (simpler):</strong> Or encode it as base64: <code>cat service-account.json | base64 | tr -d '\n'</code></li>
                  <li>Redeploy the dashboard</li>
                </ol>
                <p style={{ fontSize: '14px', marginTop: '15px', padding: '10px', background: '#e8f4f8', borderRadius: '5px' }}>
                  <strong>💡 Tip:</strong> If you're running in Google Cloud (Cloud Run, Cloud Functions), 
                  the dashboard can use Application Default Credentials automatically - no manual setup needed!
                </p>
                <p style={{ fontSize: '12px', marginTop: '10px', color: '#666' }}>
                  Need help? Check <code>/api/config-check</code> for detailed diagnostics or see README.md
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

  const navItems: { id: NavigationTab; label: string; icon: string; badge?: string }[] = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'campaigns', label: 'Campaigns', icon: '🎯' },
    { id: 'automation', label: 'Automation', icon: '⚙️', badge: 'New' },
    { id: 'discovery', label: 'Discovery', icon: '🔍', badge: 'New' },
    { id: 'budget', label: 'Budget Manager', icon: '💰', badge: 'New' },
    { id: 'dayparting', label: 'Dayparting', icon: '🕐', badge: 'New' },
    { id: 'reports', label: 'Reports', icon: '📈', badge: 'New' },
    { id: 'analytics', label: 'Analytics', icon: '📉' },
    { id: 'performance', label: 'Performance', icon: '⚡' },
    { id: 'hourly', label: 'Hourly Analysis', icon: '⏰' },
    { id: 'searchterms', label: 'Search Terms', icon: '🔎' },
    { id: 'datatable', label: 'Data Table', icon: '📋' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverviewTab();
      case 'campaigns':
        return renderCampaignsTab();
      case 'automation':
        return renderAutomationTab();
      case 'discovery':
        return renderDiscoveryTab();
      case 'budget':
        return renderBudgetTab();
      case 'dayparting':
        return renderDaypartingTab();
      case 'reports':
        return renderReportsTab();
      case 'analytics':
        return renderAnalyticsTab();
      case 'performance':
        return renderPerformanceTab();
      case 'hourly':
        return renderHourlyTab();
      case 'searchterms':
        return renderSearchTermsTab();
      case 'datatable':
        return renderDataTableTab();
      case 'settings':
        return renderSettingsTab();
      default:
        return renderOverviewTab();
    }
  };

  const renderOverviewTab = () => (
    <>
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
    </>
  );

  const renderCampaignsTab = () => {
    const latestResult = recentResults[0];
    const campaigns = latestResult?.campaigns || [];
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🎯 Campaign Performance</h2>
        {campaigns.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            No campaign data available. Run an optimization to see campaign details.
          </p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Campaign Name</th>
                <th style={styles.th}>Campaign ID</th>
                <th style={styles.th}>Spend</th>
                <th style={styles.th}>Sales</th>
                <th style={styles.th}>ACOS</th>
                <th style={styles.th}>Keywords</th>
                <th style={styles.th}>Changes Made</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign, index) => (
                <tr key={campaign.campaign_id} style={index % 2 === 0 ? styles.evenRow : styles.oddRow}>
                  <td style={styles.td}>{campaign.campaign_name}</td>
                  <td style={styles.td}>{campaign.campaign_id}</td>
                  <td style={styles.td}>{formatCurrency(campaign.spend)}</td>
                  <td style={styles.td}>{formatCurrency(campaign.sales)}</td>
                  <td style={styles.td}>{formatPercent(campaign.acos)}</td>
                  <td style={styles.td}>{campaign.keywords_count || 0}</td>
                  <td style={styles.td}>{campaign.changes_made || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  };

  const renderAutomationTab = () => {
    const latestResult = recentResults[0];
    const features = latestResult?.features || {};
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>⚙️ Automation Features</h2>
        <div style={{ padding: '20px' }}>
          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>✅ Bid Optimization</h3>
            <div style={styles.featureStats}>
              <div>Keywords Analyzed: {features.bid_optimization?.keywords_analyzed || 0}</div>
              <div>Bids Increased: {features.bid_optimization?.bids_increased || 0}</div>
              <div>Bids Decreased: {features.bid_optimization?.bids_decreased || 0}</div>
              <div>No Change: {features.bid_optimization?.no_change || 0}</div>
            </div>
          </div>

          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>🕐 Dayparting</h3>
            <div style={styles.featureStats}>
              <div>Current Day: {features.dayparting?.current_day || 'N/A'}</div>
              <div>Current Hour: {features.dayparting?.current_hour || 'N/A'}</div>
              <div>Keywords Updated: {features.dayparting?.keywords_updated || 0}</div>
              <div>Multiplier: {features.dayparting?.multiplier?.toFixed(2) || 'N/A'}</div>
            </div>
          </div>

          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>🎯 Campaign Management</h3>
            <div style={styles.featureStats}>
              <div>Campaigns Analyzed: {features.campaign_management?.campaigns_analyzed || 0}</div>
              <div>Campaigns Paused: {features.campaign_management?.campaigns_paused || 0}</div>
              <div>Campaigns Activated: {features.campaign_management?.campaigns_activated || 0}</div>
              <div>No Change: {features.campaign_management?.no_change || 0}</div>
            </div>
          </div>

          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>🔍 Keyword Discovery</h3>
            <div style={styles.featureStats}>
              <div>Keywords Discovered: {features.keyword_discovery?.keywords_discovered || 0}</div>
              <div>Keywords Added: {features.keyword_discovery?.keywords_added || 0}</div>
            </div>
          </div>

          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>🚫 Negative Keywords</h3>
            <div style={styles.featureStats}>
              <div>Negative Keywords Added: {features.negative_keywords?.negative_keywords_added || 0}</div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderDiscoveryTab = () => {
    const latestResult = recentResults[0];
    const topPerformers = latestResult?.top_performers || [];
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🔍 Top Performing Keywords</h2>
        {topPerformers.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            No top performer data available. Run an optimization to see keyword insights.
          </p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Keyword</th>
                <th style={styles.th}>Clicks</th>
                <th style={styles.th}>Sales</th>
                <th style={styles.th}>ACOS</th>
                <th style={styles.th}>Bid Change</th>
              </tr>
            </thead>
            <tbody>
              {topPerformers.map((keyword, index) => (
                <tr key={index} style={index % 2 === 0 ? styles.evenRow : styles.oddRow}>
                  <td style={styles.td}><strong>{keyword.keyword_text}</strong></td>
                  <td style={styles.td}>{keyword.clicks}</td>
                  <td style={styles.td}>{formatCurrency(keyword.sales)}</td>
                  <td style={styles.td}>{formatPercent(keyword.acos)}</td>
                  <td style={styles.td}>
                    {keyword.bid_change !== undefined ? (
                      <span style={keyword.bid_change > 0 ? { color: '#28a745' } : { color: '#dc3545' }}>
                        {keyword.bid_change > 0 ? '+' : ''}{formatCurrency(keyword.bid_change)}
                      </span>
                    ) : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  };

  const renderBudgetTab = () => (
    <div style={styles.tableCard}>
      <h2 style={styles.tableTitle}>💰 Budget Manager</h2>
      <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
        <p>Budget management features coming soon...</p>
        <p style={{ fontSize: '14px', marginTop: '10px' }}>
          Track campaign budgets, budget utilization, and get recommendations for budget optimization.
        </p>
      </div>
    </div>
  );

  const renderDaypartingTab = () => {
    const latestResult = recentResults[0];
    const daypartingData = latestResult?.features?.dayparting || {};
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🕐 Dayparting Analysis</h2>
        <div style={{ padding: '20px' }}>
          <div style={styles.statsGrid}>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Current Day</div>
              <div style={styles.statValue}>{daypartingData.current_day || 'N/A'}</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Current Hour</div>
              <div style={styles.statValue}>{daypartingData.current_hour || 'N/A'}</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Current Multiplier</div>
              <div style={styles.statValue}>{daypartingData.multiplier?.toFixed(2) || 'N/A'}</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Keywords Updated</div>
              <div style={styles.statValue}>{daypartingData.keywords_updated || 0}</div>
            </div>
          </div>
          <p style={{ textAlign: 'center', color: '#666', marginTop: '20px' }}>
            Dayparting automatically adjusts bids based on time of day and day of week performance.
          </p>
        </div>
      </div>
    );
  };

  const renderReportsTab = () => (
    <div style={styles.tableCard}>
      <h2 style={styles.tableTitle}>📈 Reports</h2>
      <div style={{ padding: '20px' }}>
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Total Runs</div>
            <div style={styles.statValue}>{recentResults.length}</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Success Rate</div>
            <div style={styles.statValue}>
              {recentResults.length > 0
                ? ((recentResults.filter(r => r.status === 'success').length / recentResults.length) * 100).toFixed(1) + '%'
                : 'N/A'}
            </div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Avg Duration</div>
            <div style={styles.statValue}>
              {recentResults.length > 0
                ? (recentResults.reduce((sum, r) => sum + r.duration_seconds, 0) / recentResults.length).toFixed(1) + 's'
                : 'N/A'}
            </div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Total Keywords</div>
            <div style={styles.statValue}>{totalKeywordsOptimized}</div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAnalyticsTab = () => (
    <div style={styles.tableCard}>
      <h2 style={styles.tableTitle}>📉 Analytics</h2>
      <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
        <p>Advanced analytics and insights coming soon...</p>
        <p style={{ fontSize: '14px', marginTop: '10px' }}>
          View trends, patterns, and predictive analytics for your campaigns.
        </p>
      </div>
    </div>
  );

  const renderPerformanceTab = () => (
    <div style={styles.tableCard}>
      <h2 style={styles.tableTitle}>⚡ Performance Metrics</h2>
      <div style={{ padding: '20px' }}>
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Avg ACOS</div>
            <div style={styles.statValue}>{formatPercent(avgAcos)}</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Total Spend</div>
            <div style={styles.statValue}>{formatCurrency(totalSpend)}</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>Total Sales</div>
            <div style={styles.statValue}>{formatCurrency(totalSales)}</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statLabel}>ROI</div>
            <div style={styles.statValue}>
              {totalSpend > 0 ? (((totalSales - totalSpend) / totalSpend) * 100).toFixed(1) + '%' : 'N/A'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderHourlyTab = () => (
    <div style={styles.tableCard}>
      <h2 style={styles.tableTitle}>⏰ Hourly Analysis</h2>
      <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
        <p>Hourly performance breakdown coming soon...</p>
        <p style={{ fontSize: '14px', marginTop: '10px' }}>
          View hour-by-hour performance metrics to optimize dayparting strategy.
        </p>
      </div>
    </div>
  );

  const renderSearchTermsTab = () => (
    <div style={styles.tableCard}>
      <h2 style={styles.tableTitle}>🔎 Search Terms Report</h2>
      <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
        <p>Search term analysis coming soon...</p>
        <p style={{ fontSize: '14px', marginTop: '10px' }}>
          View actual search terms that triggered your ads and identify new keyword opportunities.
        </p>
      </div>
    </div>
  );

  const renderDataTableTab = () => (
    <>
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>📋 Complete Data Table</h2>
        {recentResults.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            No data available.
          </p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Timestamp</th>
                <th style={styles.th}>Run ID</th>
                <th style={styles.th}>Status</th>
                <th style={styles.th}>Campaigns</th>
                <th style={styles.th}>Keywords</th>
                <th style={styles.th}>Bids ↑</th>
                <th style={styles.th}>Bids ↓</th>
                <th style={styles.th}>Negatives</th>
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
                  <td style={{ ...styles.td, fontSize: '11px' }}>{result.run_id.substring(0, 8)}...</td>
                  <td style={styles.td}>
                    <span style={result.status === 'success' ? styles.successBadge : styles.errorBadge}>
                      {result.status}
                    </span>
                  </td>
                  <td style={styles.td}>{result.campaigns_analyzed || 0}</td>
                  <td style={styles.td}>{result.keywords_optimized}</td>
                  <td style={styles.td}>{result.bids_increased}</td>
                  <td style={styles.td}>{result.bids_decreased}</td>
                  <td style={styles.td}>{result.negative_keywords_added || 0}</td>
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
    </>
  );

  const renderSettingsTab = () => {
    const latestResult = recentResults[0];
    const config = latestResult?.config_snapshot || {};
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>⚙️ Configuration Settings</h2>
        <div style={{ padding: '20px' }}>
          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>Optimization Settings</h3>
            <div style={styles.featureStats}>
              <div>Target ACOS: {config.target_acos ? formatPercent(config.target_acos) : 'N/A'}</div>
              <div>Lookback Days: {config.lookback_days || 'N/A'}</div>
              <div>Enabled Features: {config.enabled_features?.length || 0}</div>
            </div>
          </div>
          
          {config.enabled_features && config.enabled_features.length > 0 && (
            <div style={styles.featureSection}>
              <h3 style={styles.featureTitle}>Enabled Features</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '10px' }}>
                {config.enabled_features.map((feature, index) => (
                  <span key={index} style={styles.successBadge}>
                    {feature}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          <div style={{ marginTop: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '8px' }}>
            <p style={{ fontSize: '14px', color: '#666', margin: 0 }}>
              <strong>Note:</strong> Configuration settings are captured from the most recent optimization run.
              Modify settings in your config.json or environment variables.
            </p>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div style={styles.dashboardContainer}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.headerTitle}>🚀 Amazon PPC Optimizer Dashboard</h1>
          <p style={styles.headerSubtitle}>Real-time data from BigQuery</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <a href="/api/setup-guide" target="_blank" style={styles.headerLink} title="View setup guide">
            📖 Setup
          </a>
          <a href="/api/config-check" target="_blank" style={styles.headerLink} title="Check configuration">
            🔍 Config
          </a>
          <button onClick={fetchDashboardData} style={styles.refreshButton}>
            🔄 Refresh
          </button>
        </div>
      </header>

      {/* Navigation Bar */}
      <div style={styles.navContainer}>
        <div style={styles.navScroll}>
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                ...styles.navButton,
                ...(activeTab === item.id ? styles.navButtonActive : {}),
              }}
            >
              <span>{item.icon} {item.label}</span>
              {item.badge && <span style={styles.navBadge}>{item.badge}</span>}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {renderTabContent()}

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


      {/* Footer */}
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
  helpLink: {
    display: 'inline-block',
    padding: '8px 16px',
    background: '#667eea',
    color: 'white',
    textDecoration: 'none',
    borderRadius: '5px',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  headerLink: {
    padding: '8px 16px',
    background: 'rgba(255, 255, 255, 0.2)',
    color: 'white',
    textDecoration: 'none',
    borderRadius: '20px',
    fontSize: '14px',
    fontWeight: 'bold',
    border: '1px solid rgba(255, 255, 255, 0.3)',
  },
  navContainer: {
    background: 'white',
    borderRadius: '10px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
    marginBottom: '20px',
    padding: '10px',
    overflowX: 'auto',
  },
  navScroll: {
    display: 'flex',
    gap: '8px',
    minWidth: 'fit-content',
  },
  navButton: {
    background: 'transparent',
    border: '1px solid #e0e0e0',
    padding: '10px 16px',
    borderRadius: '8px',
    fontSize: '14px',
    cursor: 'pointer',
    fontWeight: '500',
    color: '#666',
    whiteSpace: 'nowrap',
    transition: 'all 0.2s',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  navButtonActive: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: '1px solid transparent',
    fontWeight: 'bold',
  },
  navBadge: {
    background: '#28a745',
    color: 'white',
    padding: '2px 6px',
    borderRadius: '10px',
    fontSize: '10px',
    fontWeight: 'bold',
    marginLeft: '4px',
  },
  featureSection: {
    marginBottom: '25px',
    padding: '20px',
    background: '#f8f9fa',
    borderRadius: '8px',
  },
  featureTitle: {
    margin: '0 0 15px 0',
    color: '#333',
    fontSize: '18px',
  },
  featureStats: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '10px',
    fontSize: '14px',
    color: '#666',
  },
};
