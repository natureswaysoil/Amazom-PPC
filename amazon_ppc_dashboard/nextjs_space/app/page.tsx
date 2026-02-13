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

type LiveSection = 'campaigns' | 'automation' | 'discovery' | 'budget' | 'dayparting' | 'reports' | 'analytics';

type LiveSectionState = {
  loading: boolean;
  error: string | null;
  data: any | null;
  loadedAt?: number;
};

export default function Home() {
  const [activeTab, setActiveTab] = useState<NavigationTab>('overview');
  const [recentResults, setRecentResults] = useState<OptimizationResult[]>([]);
  const [summary, setSummary] = useState<SummaryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isRunIntervalSkipMessage =
    typeof error === 'string' &&
    error.toLowerCase().includes('run interval not met');

  const [liveSections, setLiveSections] = useState<Record<LiveSection, LiveSectionState>>({
    campaigns: { loading: false, error: null, data: null },
    automation: { loading: false, error: null, data: null },
    discovery: { loading: false, error: null, data: null },
    budget: { loading: false, error: null, data: null },
    dayparting: { loading: false, error: null, data: null },
    reports: { loading: false, error: null, data: null },
    analytics: { loading: false, error: null, data: null },
  });

  const pickMostRecentMeaningfulResult = () => {
    if (!Array.isArray(recentResults) || recentResults.length === 0) return undefined;
    return (
      recentResults.find(r => {
        const keywordsOptimized = Number((r as any)?.keywords_optimized) || 0;
        const bidsIncreased = Number((r as any)?.bids_increased) || 0;
        const bidsDecreased = Number((r as any)?.bids_decreased) || 0;
        const campaignsAnalyzed = Number((r as any)?.campaigns_analyzed) || 0;
        const negativeKeywordsAdded = Number((r as any)?.negative_keywords_added) || 0;
        const budgetChanges = Number((r as any)?.budget_changes) || 0;
        return (
          keywordsOptimized > 0 ||
          bidsIncreased > 0 ||
          bidsDecreased > 0 ||
          campaignsAnalyzed > 0 ||
          negativeKeywordsAdded > 0 ||
          budgetChanges > 0
        );
      }) || recentResults[0]
    );
  };

  useEffect(() => {
    fetchDashboardData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchDashboardData, 300000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const sectionsNeedingFetch: LiveSection[] = ['campaigns', 'automation', 'discovery', 'budget', 'dayparting', 'reports', 'analytics'];
    if (!sectionsNeedingFetch.includes(activeTab as LiveSection)) return;

    const section = activeTab as LiveSection;
    const state = liveSections[section];
    if (state?.loading || state?.data) return;

    void loadLiveSection(section);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const fetchLiveSection = async (section: LiveSection, params?: { days?: number; limit?: number }) => {
    const days = params?.days ?? 30;
    const limit = params?.limit ?? 200;
    const query = new URLSearchParams({ section, days: String(days), limit: String(limit) });

    const resp = await fetch(`/api/optimizer-live?${query.toString()}`);

    let proxyPayload: any;
    try {
      proxyPayload = await resp.json();
    } catch (jsonErr) {
      if (!resp.ok) {
        throw new Error(`Failed to fetch ${section} live data: ${resp.status} ${resp.statusText}`);
      }
      throw jsonErr;
    }

    if (!resp.ok || !proxyPayload?.ok) {
      const msg =
        proxyPayload?.data?.message ||
        proxyPayload?.data?.error ||
        proxyPayload?.error ||
        resp.statusText ||
        'Unknown error';

      // "Run interval not met" is an expected optimizer behavior and should not be
      // treated as a fatal dashboard error (even if it is returned non-OK).
      if (String(msg).toLowerCase().includes('run interval not met')) {
        return {
          status: 'skipped',
          message: msg,
          recent_results: [],
          daily: [],
        };
      }

      throw new Error(`Failed to fetch ${section} live data: ${msg}`);
    }

    const liveData = proxyPayload.data;
    // The optimizer may return status=skipped when the min run interval
    // has not elapsed. This is not a dashboard error; the dashboard should
    // still render whatever recent/aggregated data is returned.
    if (liveData?.status !== 'success' && liveData?.status !== 'skipped') {
      throw new Error(liveData?.message || `Live ${section} endpoint returned an error`);
    }

    return liveData;
  };

  const loadLiveSection = async (section: LiveSection) => {
    try {
      setLiveSections(prev => ({
        ...prev,
        [section]: { ...prev[section], loading: true, error: null },
      }));

      const data = await fetchLiveSection(section, {
        days: section === 'automation' ? 14 : 30,
        limit: section === 'automation' ? 100 : 200,
      });

      setLiveSections(prev => ({
        ...prev,
        [section]: { loading: false, error: null, data, loadedAt: Date.now() },
      }));
    } catch (err: any) {
      setLiveSections(prev => ({
        ...prev,
        [section]: {
          loading: false,
          error: err?.message || `Failed to load ${section} data`,
          data: null,
          loadedAt: Date.now(),
        },
      }));
    }
  };

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Overview cards are explicitly labeled "(7d)"; request 7 calendar days.
      const liveResponse = await fetch('/api/optimizer-live?section=overview&limit=50&days=7');

      let livePayload;
      try {
        livePayload = await liveResponse.json();
      } catch (jsonErr) {
        if (!liveResponse.ok) {
          throw new Error(`Failed to fetch live optimizer data: ${liveResponse.status} ${liveResponse.statusText}`);
        }
        throw jsonErr;
      }

      if (!liveResponse.ok || !livePayload?.ok) {
        const msg =
          livePayload?.data?.message ||
          livePayload?.data?.error ||
          livePayload?.error ||
          liveResponse.statusText ||
          'Unknown error';

        // "Run interval not met" should not show as a fatal page-level error.
        if (String(msg).toLowerCase().includes('run interval not met')) {
          setLoading(false);
          // Keep showing whatever data we already have.
          return;
        }

        throw new Error(`Failed to fetch live optimizer data: ${msg}`);
      }

      const liveData = livePayload.data;
      // status=skipped ("Run interval not met") should not block the dashboard.
      if (liveData?.status !== 'success' && liveData?.status !== 'skipped') {
        throw new Error(liveData?.message || 'Live optimizer endpoint returned an error');
      }

      const results = liveData.recent_results || [];

      if (results && results.length > 0) {
        console.log('📊 Dashboard: Received optimizer live results');
        console.log('First result keys:', Object.keys(results[0]));

        const expectedFields = ['campaigns', 'top_performers', 'features', 'config_snapshot', 'errors', 'warnings'];
        const missingFields = expectedFields.filter(field => !(field in results[0]));
        if (missingFields.length > 0) {
          console.warn('⚠️ Missing expected fields in results:', missingFields);
          const warningMsg = `Some optimization data is incomplete. Missing fields: ${missingFields.join(', ')}. This may indicate the optimizer is not sending full payloads or the database schema needs updating.`;
          setError(warningMsg);
        }
      }

      // If the optimizer skipped due to min-interval and returned no rows,
      // preserve the last known data instead of wiping the UI.
      if (!(liveData?.status === 'skipped' && (!results || results.length === 0))) {
        setRecentResults(results);
      }

      const daily = liveData.daily || [];
      const mappedSummary: SummaryData[] = daily.map((d: any) => ({
        date: d.day,
        optimization_runs: d.runs ?? 0,
        total_keywords_optimized: d.keywords_optimized ?? 0,
        avg_acos: d.blended_acos ?? 0,
        total_spend: d.total_spend ?? 0,
        total_sales: d.total_sales ?? 0,
      }));
      if (!(liveData?.status === 'skipped' && (!mappedSummary || mappedSummary.length === 0))) {
        setSummary(mappedSummary);
      }

      setLoading(false);
    } catch (err: any) {
      const msg = err?.message || 'Failed to fetch dashboard data';
      if (String(msg).toLowerCase().includes('run interval not met')) {
        setLoading(false);
        return;
      }
      setError(msg);
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

  if (error && recentResults.length === 0 && !isRunIntervalSkipMessage) {
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
            {(error.includes('Not found') ||
              error.toLowerCase().includes('setup-bigquery') ||
              error.toLowerCase().includes('dataset or table not found')) && (
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
                  <li><strong>Alternative (simpler):</strong> Or encode it as base64: <code>cat service-account.json | base64 | tr -d &apos;\n&apos;</code></li>
                  <li>Redeploy the dashboard</li>
                </ol>
                <p style={{ fontSize: '14px', marginTop: '15px', padding: '10px', background: '#e8f4f8', borderRadius: '5px' }}>
                  <strong>💡 Tip:</strong> If you&apos;re running in Google Cloud (Cloud Run, Cloud Functions), 
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
        {recentResults.slice(0, 2).length === 0 ? (
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
              {recentResults.slice(0, 2).map((result, index) => (
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
    const latestResult = pickMostRecentMeaningfulResult() || recentResults[0];
    const campaignsLive = liveSections.campaigns.data?.campaigns;
    const campaigns = Array.isArray(campaignsLive) && campaignsLive.length > 0
      ? campaignsLive
      : (latestResult?.campaigns || []);
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🎯 Campaign Performance</h2>
        {liveSections.campaigns.loading && (
          <p style={{ textAlign: 'center', color: '#666', padding: '10px' }}>Loading live campaign data...</p>
        )}
        {liveSections.campaigns.error && (
          <p style={{ textAlign: 'center', color: '#b00020', padding: '10px' }}>{liveSections.campaigns.error}</p>
        )}
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
    const latestResult = pickMostRecentMeaningfulResult() || recentResults[0];
    const fallbackFeatures = (() => {
      const keywordsOptimized = Number((latestResult as any)?.keywords_optimized || 0);
      const bidsIncreased = Number((latestResult as any)?.bids_increased || 0);
      const bidsDecreased = Number((latestResult as any)?.bids_decreased || 0);
      const campaignsAnalyzed = Number((latestResult as any)?.campaigns_analyzed || 0);
      const budgetChanges = Number((latestResult as any)?.budget_changes || 0);
      const negativeKeywordsAdded = Number((latestResult as any)?.negative_keywords_added || 0);

      const computedNoChange = Math.max(0, keywordsOptimized - bidsIncreased - bidsDecreased);

      const now = new Date();
      const dayNames = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];

      return {
        bid_optimization: {
          keywords_analyzed: keywordsOptimized,
          bids_increased: bidsIncreased,
          bids_decreased: bidsDecreased,
          no_change: computedNoChange,
        },
        dayparting: {
          current_day: dayNames[now.getDay()] || 'N/A',
          current_hour: now.getHours(),
          keywords_updated: 0,
          multiplier: 1.0,
        },
        campaign_management: {
          campaigns_analyzed: campaignsAnalyzed,
          campaigns_paused: 0,
          campaigns_activated: 0,
          no_change: campaignsAnalyzed,
        },
        keyword_discovery: {
          keywords_discovered: 0,
          keywords_added: 0,
        },
        negative_keywords: {
          negative_keywords_added: negativeKeywordsAdded,
        },
        budget_optimization: {
          budget_changes: budgetChanges,
        },
      };
    })();

    const rawFeatures = (latestResult as any)?.features;
    const features =
      rawFeatures && typeof rawFeatures === 'object' && Object.keys(rawFeatures).length > 0
        ? rawFeatures
        : fallbackFeatures;
    const events = Array.isArray(liveSections.automation.data?.events) ? liveSections.automation.data.events : [];

    // Only show the last 2 unique runs (sessions) in the events table.
    // Events come back in descending timestamp order from BigQuery.
    const lastTwoRunIds: string[] = [];
    for (const ev of events) {
      const runId = (ev as any)?.run_id;
      if (typeof runId !== 'string' || !runId.trim()) continue;
      if (!lastTwoRunIds.includes(runId)) {
        lastTwoRunIds.push(runId);
      }
      if (lastTwoRunIds.length >= 2) break;
    }
    const filteredEvents = lastTwoRunIds.length > 0
      ? events.filter((ev: any) => lastTwoRunIds.includes(ev?.run_id))
      : events;
    
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

          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>🧾 Recent Automation Events</h3>
            {liveSections.automation.loading && (
              <p style={{ color: '#666', margin: 0 }}>Loading live automation events...</p>
            )}
            {liveSections.automation.error && (
              <p style={{ color: '#b00020', margin: 0 }}>{liveSections.automation.error}</p>
            )}
            {!liveSections.automation.loading && !liveSections.automation.error && events.length === 0 && (
              <p style={{ color: '#666', margin: 0 }}>No recent run events found.</p>
            )}
            {events.length > 0 && (
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Timestamp</th>
                    <th style={styles.th}>Run ID</th>
                    <th style={styles.th}>Status</th>
                    <th style={styles.th}>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEvents.slice(0, 50).map((ev: any, idx: number) => (
                    <tr key={`${ev.run_id || 'run'}-${idx}`} style={idx % 2 === 0 ? styles.evenRow : styles.oddRow}>
                      <td style={styles.td}>{ev.timestamp ? formatDate(ev.timestamp) : 'N/A'}</td>
                      <td style={styles.td}>{ev.run_id || 'N/A'}</td>
                      <td style={styles.td}>{ev.status || 'N/A'}</td>
                      <td style={styles.td}>
                        {ev.details ? (
                          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(ev.details, null, 2)}</pre>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderDiscoveryTab = () => {
    const latestResult = pickMostRecentMeaningfulResult() || recentResults[0];
    const topPerformers = latestResult?.top_performers || [];
    const discoveryLive = liveSections.discovery.data?.data;
    const discoveryFallback = latestResult?.features?.keyword_discovery || {};
    const discoveryData = (discoveryLive && typeof discoveryLive === 'object') ? discoveryLive : discoveryFallback;
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🔍 Top Performing Keywords</h2>
        <div style={{ padding: '0 20px 10px' }}>
          <div style={styles.featureSection}>
            <h3 style={styles.featureTitle}>🧠 Discovery Summary</h3>
            {liveSections.discovery.loading && (
              <p style={{ color: '#666', margin: 0 }}>Loading live discovery data...</p>
            )}
            {liveSections.discovery.error && (
              <p style={{ color: '#b00020', margin: 0 }}>{liveSections.discovery.error}</p>
            )}
            <div style={styles.featureStats}>
              <div>Keywords Discovered: {discoveryData?.keywords_discovered || 0}</div>
              <div>Keywords Added: {discoveryData?.keywords_added || 0}</div>
            </div>
          </div>
        </div>
        {topPerformers.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            No top performer list available yet. Run a full optimization that writes keyword insights to BigQuery.
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
      <div style={{ padding: '20px' }}>
        {liveSections.budget.loading && (
          <p style={{ textAlign: 'center', color: '#666', padding: '10px' }}>Loading live budget data...</p>
        )}
        {liveSections.budget.error && (
          <p style={{ textAlign: 'center', color: '#b00020', padding: '10px' }}>{liveSections.budget.error}</p>
        )}

        {(() => {
          const latestResult = pickMostRecentMeaningfulResult() || recentResults[0];
          const budgetLive = liveSections.budget.data?.data;
          const budgetFallback = latestResult?.features?.budget_optimization || {};
          const budgetData = (budgetLive && typeof budgetLive === 'object') ? budgetLive : budgetFallback;
          const budgetChanges = budgetData?.budget_changes ?? latestResult?.budget_changes ?? 0;

          return (
            <>
              <div style={styles.statsGrid}>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Budget Changes</div>
                  <div style={styles.statValue}>{budgetChanges}</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Spend (7d)</div>
                  <div style={styles.statValue}>{formatCurrency(totalSpend)}</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Sales (7d)</div>
                  <div style={styles.statValue}>{formatCurrency(totalSales)}</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Avg ACOS</div>
                  <div style={styles.statValue}>{formatPercent(avgAcos)}</div>
                </div>
              </div>
              <p style={{ textAlign: 'center', color: '#666', marginTop: '20px' }}>
                Budget optimization uses spend and performance signals to recommend adjustments.
              </p>
            </>
          );
        })()}
      </div>
    </div>
  );

  const renderDaypartingTab = () => {
    const latestResult = pickMostRecentMeaningfulResult() || recentResults[0];
    const daypartingLive = liveSections.dayparting.data?.data;
    const daypartingFallback = latestResult?.features?.dayparting || {};
    const daypartingData = (daypartingLive && typeof daypartingLive === 'object') ? daypartingLive : daypartingFallback;
    
    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🕐 Dayparting Analysis</h2>
        <div style={{ padding: '20px' }}>
          {liveSections.dayparting.loading && (
            <p style={{ textAlign: 'center', color: '#666', padding: '10px' }}>Loading live dayparting data...</p>
          )}
          {liveSections.dayparting.error && (
            <p style={{ textAlign: 'center', color: '#b00020', padding: '10px' }}>{liveSections.dayparting.error}</p>
          )}
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
        {liveSections.reports.loading && (
          <p style={{ textAlign: 'center', color: '#666', padding: '10px' }}>Loading live reports data...</p>
        )}
        {liveSections.reports.error && (
          <p style={{ textAlign: 'center', color: '#b00020', padding: '10px' }}>{liveSections.reports.error}</p>
        )}

        {(() => {
          const reportsRecent = Array.isArray(liveSections.reports.data?.recent_results)
            ? liveSections.reports.data.recent_results
            : recentResults;
          const runs = reportsRecent.length;
          const successCount = reportsRecent.filter((r: any) => r.status === 'success').length;
          const successRate = runs > 0 ? ((successCount / runs) * 100).toFixed(1) + '%' : 'N/A';
          const avgDuration = runs > 0
            ? (reportsRecent.reduce((sum: number, r: any) => sum + (Number(r.duration_seconds) || 0), 0) / runs).toFixed(1) + 's'
            : 'N/A';

          return (
            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Total Runs</div>
                <div style={styles.statValue}>{runs}</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Success Rate</div>
                <div style={styles.statValue}>{successRate}</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Avg Duration</div>
                <div style={styles.statValue}>{avgDuration}</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Total Keywords</div>
                <div style={styles.statValue}>{totalKeywordsOptimized}</div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );

  const renderAnalyticsTab = () => {
    const analyticsState = liveSections.analytics;
    const analyticsData = analyticsState.data?.data?.data;

    // Helper function to format trend indicator
    const formatTrend = (value: number) => {
      if (!value || value === 0) return '—';
      const color = value > 0 ? '#28a745' : '#dc3545';
      const arrow = value > 0 ? '↑' : '↓';
      return <span style={{ color }}>{arrow} {Math.abs(value).toFixed(1)}%</span>;
    };

    // Helper function to format currency
    const formatCurrency = (value: number) => {
      return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value || 0);
    };

    // Helper function to format number
    const formatNumber = (value: number) => {
      return new Intl.NumberFormat('en-US').format(Math.round(value || 0));
    };

    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>📉 Analytics Dashboard</h2>
        
        {analyticsState.loading && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
            <p>Loading analytics data...</p>
          </div>
        )}

        {analyticsState.error && !analyticsState.loading && (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <p style={{ color: '#b00020', margin: 0 }}>{analyticsState.error}</p>
            <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
              Unable to fetch analytics data. Please ensure BigQuery is configured and contains optimization results.
            </p>
          </div>
        )}

        {!analyticsState.loading && !analyticsState.error && !analyticsData && (
          <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
            <p>No analytics data available yet.</p>
            <p style={{ fontSize: '14px', marginTop: '10px' }}>
              Run optimizations to populate the analytics dashboard with trends and insights.
            </p>
          </div>
        )}

        {!analyticsState.loading && analyticsData && (
          <div style={{ padding: '20px' }}>
            {/* Key Metrics Cards */}
            <div style={styles.featureSection}>
              <h3 style={styles.featureTitle}>📊 Key Metrics (Last 30 Days)</h3>
              <div style={styles.statsGrid}>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Total Runs</div>
                  <div style={styles.statValue}>{formatNumber(analyticsData.metrics?.total_runs || 0)}</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Keywords Optimized</div>
                  <div style={styles.statValue}>{formatNumber(analyticsData.metrics?.total_keywords || 0)}</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Average ACOS</div>
                  <div style={styles.statValue}>{(analyticsData.metrics?.avg_acos || 0).toFixed(2)}%</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Success Rate</div>
                  <div style={styles.statValue}>{(analyticsData.metrics?.success_rate || 0).toFixed(1)}%</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Avg Run Duration</div>
                  <div style={styles.statValue}>{(analyticsData.metrics?.avg_duration || 0).toFixed(0)}s</div>
                </div>
                <div style={styles.statCard}>
                  <div style={styles.statLabel}>Campaigns Analyzed</div>
                  <div style={styles.statValue}>{formatNumber(analyticsData.metrics?.total_campaigns || 0)}</div>
                </div>
              </div>
            </div>

            {/* Comparative Analysis */}
            {analyticsData.comparative?.wow && (
              <div style={styles.featureSection}>
                <h3 style={styles.featureTitle}>📈 Week-over-Week Changes</h3>
                <div style={styles.statsGrid}>
                  <div style={styles.statCard}>
                    <div style={styles.statLabel}>Spend Change</div>
                    <div style={styles.statValue}>{formatTrend(analyticsData.comparative.wow.spend_change)}</div>
                  </div>
                  <div style={styles.statCard}>
                    <div style={styles.statLabel}>Sales Change</div>
                    <div style={styles.statValue}>{formatTrend(analyticsData.comparative.wow.sales_change)}</div>
                  </div>
                  <div style={styles.statCard}>
                    <div style={styles.statLabel}>ACOS Change</div>
                    <div style={styles.statValue}>{formatTrend(analyticsData.comparative.wow.acos_change)}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Predictive Indicators */}
            {analyticsData.predictions && (
              <div style={styles.featureSection}>
                <h3 style={styles.featureTitle}>🔮 Predictive Indicators</h3>
                <div style={styles.statsGrid}>
                  <div style={styles.statCard}>
                    <div style={styles.statLabel}>Optimization Velocity</div>
                    <div style={styles.statValue}>{(analyticsData.predictions.runs_per_week || 0).toFixed(1)} runs/week</div>
                  </div>
                  <div style={styles.statCard}>
                    <div style={styles.statLabel}>Keyword Optimization Rate</div>
                    <div style={styles.statValue}>{(analyticsData.predictions.keywords_per_run || 0).toFixed(0)} keywords/run</div>
                  </div>
                  <div style={styles.statCard}>
                    <div style={styles.statLabel}>Efficiency Score</div>
                    <div style={styles.statValue}>{formatCurrency(analyticsData.predictions.efficiency_score || 0)}/keyword</div>
                  </div>
                </div>
              </div>
            )}

            {/* Performance Trends */}
            {analyticsData.trends?.daily && analyticsData.trends.daily.length > 0 && (
              <div style={styles.featureSection}>
                <h3 style={styles.featureTitle}>📊 Performance Trends</h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Date</th>
                        <th style={styles.th}>Runs</th>
                        <th style={styles.th}>Keywords</th>
                        <th style={styles.th}>Spend</th>
                        <th style={styles.th}>Sales</th>
                        <th style={styles.th}>ACOS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analyticsData.trends.daily.slice(-14).reverse().map((day: any, idx: number) => (
                        <tr key={day.date || idx} style={idx % 2 === 0 ? styles.evenRow : styles.oddRow}>
                          <td style={styles.td}>{day.date}</td>
                          <td style={styles.td}>{day.runs || 0}</td>
                          <td style={styles.td}>{formatNumber(day.keywords || 0)}</td>
                          <td style={styles.td}>{formatCurrency(day.spend || 0)}</td>
                          <td style={styles.td}>{formatCurrency(day.sales || 0)}</td>
                          <td style={styles.td}>{(day.acos || 0).toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Campaign Analytics */}
            {analyticsData.campaigns && analyticsData.campaigns.length > 0 && (
              <div style={styles.featureSection}>
                <h3 style={styles.featureTitle}>🎯 Top Campaigns by Spend</h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Campaign</th>
                        <th style={styles.th}>Spend</th>
                        <th style={styles.th}>Sales</th>
                        <th style={styles.th}>ACOS</th>
                        <th style={styles.th}>ROAS</th>
                        <th style={styles.th}>Changes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analyticsData.campaigns.slice(0, 10).map((campaign: any, idx: number) => {
                        const roas = campaign.spend > 0 ? campaign.sales / campaign.spend : 0;
                        return (
                          <tr key={campaign.campaign_id || idx} style={idx % 2 === 0 ? styles.evenRow : styles.oddRow}>
                            <td style={styles.td}>{campaign.campaign_name || 'Unknown'}</td>
                            <td style={styles.td}>{formatCurrency(campaign.spend || 0)}</td>
                            <td style={styles.td}>{formatCurrency(campaign.sales || 0)}</td>
                            <td style={styles.td}>{((campaign.acos || 0) * 100).toFixed(2)}%</td>
                            <td style={styles.td}>{roas.toFixed(2)}x</td>
                            <td style={styles.td}>{campaign.changes || 0}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Simple Trend Visualization */}
            {analyticsData.trends?.daily && analyticsData.trends.daily.length > 5 && (
              <div style={styles.featureSection}>
                <h3 style={styles.featureTitle}>📈 Spend vs Sales Trend</h3>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-end', height: '200px', padding: '10px' }}>
                  {analyticsData.trends.daily.slice(-14).map((day: any, idx: number) => {
                    const maxSpend = Math.max(...analyticsData.trends.daily.map((d: any) => d.spend || 0));
                    const maxSales = Math.max(...analyticsData.trends.daily.map((d: any) => d.sales || 0));
                    const spendHeight = maxSpend > 0 ? (day.spend / maxSpend) * 150 : 0;
                    const salesHeight = maxSales > 0 ? (day.sales / maxSales) * 150 : 0;
                    
                    return (
                      <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px' }}>
                        <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end', height: '150px' }}>
                          <div
                            style={{
                              width: '12px',
                              height: `${spendHeight}px`,
                              backgroundColor: '#ff6b6b',
                              borderRadius: '2px 2px 0 0',
                            }}
                            title={`Spend: ${formatCurrency(day.spend || 0)}`}
                          />
                          <div
                            style={{
                              width: '12px',
                              height: `${salesHeight}px`,
                              backgroundColor: '#51cf66',
                              borderRadius: '2px 2px 0 0',
                            }}
                            title={`Sales: ${formatCurrency(day.sales || 0)}`}
                          />
                        </div>
                        <div style={{ fontSize: '10px', color: '#666', transform: 'rotate(-45deg)', whiteSpace: 'nowrap' }}>
                          {day.date?.split('-').slice(1).join('/')}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ display: 'flex', gap: '20px', justifyContent: 'center', marginTop: '20px', fontSize: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <div style={{ width: '12px', height: '12px', backgroundColor: '#ff6b6b', borderRadius: '2px' }} />
                    <span>Spend</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <div style={{ width: '12px', height: '12px', backgroundColor: '#51cf66', borderRadius: '2px' }} />
                    <span>Sales</span>
                  </div>
                </div>
              </div>
            )}

            {/* Data Timestamp */}
            {analyticsState.loadedAt && (
              <div style={{ textAlign: 'center', fontSize: '12px', color: '#999', marginTop: '20px' }}>
                Last updated: {new Date(analyticsState.loadedAt).toLocaleString()}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

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
        {recentResults.slice(0, 2).length === 0 ? (
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
              {recentResults.slice(0, 2).map((result, index) => (
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
