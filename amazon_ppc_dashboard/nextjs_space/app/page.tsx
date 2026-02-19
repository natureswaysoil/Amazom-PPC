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

interface HourlyMetric {
  hour: number;
  spend: number;
  sales: number;
  clicks: number;
  conversions: number;
  acos: number;
  performance_score: number;
}

interface SearchTerm {
  search_term: string;
  keyword_matched: string;
  match_type: string;
  impressions: number;
  clicks: number;
  spend: number;
  sales: number;
  orders: number;
  acos: number;
  conversion_rate: number;
  ctr: number;
}

type NavigationTab = 'overview' | 'campaigns' | 'automation' | 'discovery' | 'budget' | 'dayparting' | 'reports' | 'analytics' | 'performance' | 'hourly' | 'searchterms' | 'datatable' | 'settings';

type LiveSection = 'campaigns' | 'automation' | 'discovery' | 'budget' | 'dayparting' | 'reports';

type LiveSectionState = {
  loading: boolean;
  error: string | null;
  data: any | null;
  loadedAt?: number;
};

// Constants for demo data generation and analysis
const ASSUMED_CPC = 0.85; // Average cost per click assumption
const ASSUMED_CVR = 0.08; // Average conversion rate assumption (8%)
const ASSUMED_ACOS = 0.35; // Average ACOS assumption (35%)
const MIN_IMPRESSIONS_THRESHOLD = 100; // Minimum impressions for opportunity analysis
const LOW_CTR_THRESHOLD = 1.0; // CTR below this is considered low (1%)
const HIGH_ACOS_THRESHOLD = 0.5; // ACOS above this is considered high (50%)

const generateDemoData = () => {
  const today = new Date();
  const demoSummary: SummaryData[] = [];
  const demoResults: OptimizationResult[] = [];
  
  // Generate 14 days of summary data
  for (let i = 0; i < 14; i++) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    const dayFactor = 0.8 + Math.random() * 0.4; // 0.8-1.2
    
    demoSummary.push({
      date: date.toISOString().split('T')[0],
      optimization_runs: Math.floor(1 + Math.random() * 3),
      total_keywords_optimized: Math.floor(800 * dayFactor + Math.random() * 400),
      avg_acos: 0.30 + Math.random() * 0.15,
      total_spend: 450 * dayFactor + Math.random() * 200,
      total_sales: 1200 * dayFactor + Math.random() * 400,
    });
  }
  
  // Generate 2 recent optimization results
  for (let i = 0; i < 2; i++) {
    const runDate = new Date(today);
    runDate.setHours(runDate.getHours() - (i * 12));
    
    const campaigns: Campaign[] = [
      { campaign_id: 'c1', campaign_name: 'Product Campaign A', spend: 234.56, sales: 567.89, acos: 0.413, keywords_count: 45, changes_made: 12 },
      { campaign_id: 'c2', campaign_name: 'Brand Campaign', spend: 189.23, sales: 489.12, acos: 0.387, keywords_count: 32, changes_made: 8 },
      { campaign_id: 'c3', campaign_name: 'Seasonal Promotion', spend: 156.78, sales: 401.23, acos: 0.391, keywords_count: 28, changes_made: 6 },
      { campaign_id: 'c4', campaign_name: 'Category Keywords', spend: 123.45, sales: 298.76, acos: 0.413, keywords_count: 38, changes_made: 10 },
    ];
    
    const topPerformers: TopPerformer[] = [
      { keyword_text: 'organic potting soil', clicks: 145, sales: 389.45, acos: 0.28, bid_change: 0.15 },
      { keyword_text: 'premium garden soil', clicks: 132, sales: 356.78, acos: 0.31, bid_change: 0.12 },
      { keyword_text: 'natural fertilizer', clicks: 118, sales: 312.34, acos: 0.33, bid_change: -0.05 },
      { keyword_text: 'compost mix', clicks: 98, sales: 267.89, acos: 0.29, bid_change: 0.10 },
      { keyword_text: 'raised bed soil', clicks: 87, sales: 234.56, acos: 0.35, bid_change: 0.08 },
    ];
    
    demoResults.push({
      timestamp: runDate.toISOString(),
      run_id: `demo-run-${i + 1}`,
      status: 'success',
      keywords_optimized: 1250 + Math.floor(Math.random() * 300),
      bids_increased: 720 + Math.floor(Math.random() * 150),
      bids_decreased: 530 + Math.floor(Math.random() * 100),
      average_acos: 0.35 + Math.random() * 0.10,
      total_spend: 704.02 + Math.random() * 200,
      total_sales: 1857.96 + Math.random() * 400,
      duration_seconds: 45.5 + Math.random() * 20,
      campaigns_analyzed: campaigns.length,
      negative_keywords_added: Math.floor(15 + Math.random() * 10),
      budget_changes: Math.floor(2 + Math.random() * 4),
      campaigns,
      top_performers: topPerformers,
      features: {
        bid_optimization: { enabled: true, changes: 1250 },
        dayparting: { enabled: true, rules: 24 },
        campaign_management: { enabled: true, changes: 6 },
        keyword_discovery: { enabled: true, new_keywords: 23 },
        negative_keywords: { enabled: true, added: 18 }
      },
      errors: [],
      warnings: [],
      config_snapshot: {
        target_acos: 0.35,
        lookback_days: 14,
        enabled_features: ['bid_optimization', 'dayparting', 'campaign_management', 'keyword_discovery', 'negative_keywords']
      }
    });
  }
  
  return { summary: demoSummary, results: demoResults };
};

export default function Home() {
  const [activeTab, setActiveTab] = useState<NavigationTab>('overview');
  const [recentResults, setRecentResults] = useState<OptimizationResult[]>([]);
  const [summary, setSummary] = useState<SummaryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(false);

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
    const sectionsNeedingFetch: LiveSection[] = ['campaigns', 'automation', 'discovery', 'budget', 'dayparting', 'reports'];
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
        proxyPayload?.message ||
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
    // has not elapsed, or status=unavailable when the optimizer service
    // cannot be reached. These are not dashboard errors; the dashboard should
    // still render whatever recent/aggregated data is returned.
    if (liveData?.status !== 'success' && liveData?.status !== 'skipped' && liveData?.status !== 'unavailable') {
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
          livePayload?.message ||
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
      // status=skipped ("Run interval not met") or status=unavailable (optimizer
      // unreachable) should not block the dashboard.
      if (liveData?.status !== 'success' && liveData?.status !== 'skipped' && liveData?.status !== 'unavailable') {
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
      
      // If API fails, load demo data to showcase dashboard functionality
      console.log('⚠️ API unavailable, loading demo data for preview...');
      const demoData = generateDemoData();
      setRecentResults(demoData.results);
      setSummary(demoData.summary);
      setIsDemoMode(true);
      setError(msg + ' - Showing demo data for preview');
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

  if (error && recentResults.length === 0 && !isRunIntervalSkipMessage && !isDemoMode) {
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
  // Calculate ACOS as weighted average (total spend / total sales) for the entire period
  // This is more accurate than averaging daily ACOS values
  const totalSpend = summary.reduce((sum, s) => sum + s.total_spend, 0);
  const totalSales = summary.reduce((sum, s) => sum + s.total_sales, 0);
  const avgAcos = totalSales > 0 ? totalSpend / totalSales : 0;

  // Data quality: count days with actual spend/sales data
  const daysWithData = summary.filter(s => s.total_spend > 0 || s.total_sales > 0).length;
  const expectedDays = 7; // Dashboard shows 7-day metrics

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
        {recentResults.length > 0 && (() => {
          const latestRun = new Date(recentResults[0].timestamp);
          const hoursAgo = (Date.now() - latestRun.getTime()) / (1000 * 60 * 60);
          
          const getBorderColor = () => {
            if (hoursAgo < 24) return '2px solid #4caf50';
            if (hoursAgo < 48) return '2px solid #ff9800';
            return '2px solid #f44336';
          };
          
          const getTimeDisplay = () => {
            const hoursAgoFloor = Math.floor(hoursAgo);
            if (hoursAgoFloor < 1) return 'Less than 1 hour ago';
            if (hoursAgoFloor < 24) return `${hoursAgoFloor} hour${hoursAgoFloor > 1 ? 's' : ''} ago`;
            const daysAgo = Math.floor(hoursAgoFloor / 24);
            return `${daysAgo} day${daysAgo > 1 ? 's' : ''} ago`;
          };
          
          return (
            <div style={{
              ...styles.statCard,
              border: getBorderColor()
            }}>
              <div style={styles.statLabel}>Data Freshness</div>
              <div style={{ ...styles.statValue, fontSize: '16px' }}>
                {getTimeDisplay()}
              </div>
              <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
                Last run: {formatDate(recentResults[0].timestamp)}
              </div>
            </div>
          );
        })()}
      </div>

      {daysWithData < expectedDays && daysWithData > 0 && (
        <div style={{
          background: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '8px',
          padding: '12px 16px',
          margin: '16px 0',
          fontSize: '14px',
          color: '#856404'
        }}>
          ℹ️ <strong>Data Quality Note:</strong> Showing metrics from {daysWithData} day{daysWithData !== 1 ? 's' : ''} out of {expectedDays} days requested. 
          Some days may not have optimization run data yet.
        </div>
      )}

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
    const discoveryLive = liveSections.discovery.data?.data;
    const discoveryFallback = latestResult?.features?.keyword_discovery || {};
    const discoveryData = (discoveryLive && typeof discoveryLive === 'object') ? discoveryLive : discoveryFallback;
    // Prefer top_performing_keywords from the live discovery response, then fall
    // back to the top_performers list stored on the latest optimization result.
    const topPerformers: TopPerformer[] =
      (Array.isArray(discoveryLive?.top_performing_keywords) && discoveryLive.top_performing_keywords.length > 0)
        ? discoveryLive.top_performing_keywords
        : (latestResult?.top_performers || []);
    const isUnavailable = liveSections.discovery.data?.status === 'unavailable';

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
            {isUnavailable && !liveSections.discovery.error && (
              <p style={{ color: '#888', margin: 0 }}>Optimizer service temporarily unavailable — showing cached data.</p>
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
    // Calculate trends from summary data
    const recentDays = summary.slice(0, 7);
    const olderDays = summary.slice(7, 14);
    
    const calculateTrend = (recent: number, older: number) => {
      if (older === 0) return recent > 0 ? 100 : 0;
      return ((recent - older) / older) * 100;
    };
    
    const recentSpend = recentDays.reduce((sum, d) => sum + d.total_spend, 0);
    const olderSpend = olderDays.reduce((sum, d) => sum + d.total_spend, 0);
    const spendTrend = calculateTrend(recentSpend, olderSpend);
    
    const recentSales = recentDays.reduce((sum, d) => sum + d.total_sales, 0);
    const olderSales = olderDays.reduce((sum, d) => sum + d.total_sales, 0);
    const salesTrend = calculateTrend(recentSales, olderSales);
    
    const recentAcos = recentDays.length > 0 
      ? recentDays.reduce((sum, d) => sum + d.avg_acos, 0) / recentDays.length
      : 0;
    const olderAcos = olderDays.length > 0
      ? olderDays.reduce((sum, d) => sum + d.avg_acos, 0) / olderDays.length
      : 0;
    const acosTrend = calculateTrend(recentAcos, olderAcos);
    
    const recentOptimizations = recentDays.reduce((sum, d) => sum + d.total_keywords_optimized, 0);
    const olderOptimizations = olderDays.reduce((sum, d) => sum + d.total_keywords_optimized, 0);
    const optimizationsTrend = calculateTrend(recentOptimizations, olderOptimizations);

    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>📉 Analytics & Trends</h2>
        <div style={{ padding: '20px' }}>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            7-day trends compared to previous 7 days
          </p>
          
          <div style={styles.statsGrid}>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Spend Trend</div>
              <div style={styles.statValue}>{formatCurrency(recentSpend)}</div>
              <div style={{ 
                fontSize: '14px', 
                color: spendTrend > 0 ? '#f44336' : '#4caf50',
                marginTop: '8px'
              }}>
                {spendTrend > 0 ? '↑' : '↓'} {Math.abs(spendTrend).toFixed(1)}%
              </div>
            </div>
            
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Sales Trend</div>
              <div style={styles.statValue}>{formatCurrency(recentSales)}</div>
              <div style={{ 
                fontSize: '14px', 
                color: salesTrend > 0 ? '#4caf50' : '#f44336',
                marginTop: '8px'
              }}>
                {salesTrend > 0 ? '↑' : '↓'} {Math.abs(salesTrend).toFixed(1)}%
              </div>
            </div>
            
            <div style={styles.statCard}>
              <div style={styles.statLabel}>ACOS Trend</div>
              <div style={styles.statValue}>{formatPercent(recentAcos)}</div>
              <div style={{ 
                fontSize: '14px', 
                color: acosTrend < 0 ? '#4caf50' : '#f44336',
                marginTop: '8px'
              }}>
                {acosTrend > 0 ? '↑' : '↓'} {Math.abs(acosTrend).toFixed(1)}%
              </div>
            </div>
            
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Optimizations</div>
              <div style={styles.statValue}>{recentOptimizations.toLocaleString()}</div>
              <div style={{ 
                fontSize: '14px', 
                color: optimizationsTrend > 0 ? '#4caf50' : '#666',
                marginTop: '8px'
              }}>
                {optimizationsTrend > 0 ? '↑' : '↓'} {Math.abs(optimizationsTrend).toFixed(1)}%
              </div>
            </div>
          </div>

          <div style={{ marginTop: '30px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '15px', color: '#333' }}>
              Daily Performance (Last 14 Days)
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Date</th>
                    <th style={styles.th}>Spend</th>
                    <th style={styles.th}>Sales</th>
                    <th style={styles.th}>ACOS</th>
                    <th style={styles.th}>ROI</th>
                    <th style={styles.th}>Optimizations</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.slice(0, 14).map((day, idx) => {
                    const roi = day.total_spend > 0 
                      ? ((day.total_sales - day.total_spend) / day.total_spend * 100)
                      : 0;
                    return (
                      <tr key={idx}>
                        <td style={styles.td}>{day.date}</td>
                        <td style={styles.td}>{formatCurrency(day.total_spend)}</td>
                        <td style={styles.td}>{formatCurrency(day.total_sales)}</td>
                        <td style={styles.td}>{formatPercent(day.avg_acos)}</td>
                        <td style={styles.td}>{roi.toFixed(1)}%</td>
                        <td style={styles.td}>{day.total_keywords_optimized}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
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

  const renderHourlyTab = () => {
    // Extract hourly data from dayparting section if available
    const daypartingData = liveSections.dayparting?.data;
    const hourlyMetrics = daypartingData?.hourly_performance || [];
    
    // If no hourly data, generate sample structure based on summary data
    const generateHourlyEstimates = (): HourlyMetric[] => {
      const hours = Array.from({ length: 24 }, (_, i) => i);
      const totalDailySpend = summary.length > 0 
        ? summary.reduce((sum, d) => sum + d.total_spend, 0) / summary.length
        : 0;
      
      // Typical patterns: higher during business hours
      const hourlyFactors = [
        0.3, 0.2, 0.2, 0.2, 0.3, 0.4, 0.6, 0.8,  // 0-7 AM
        1.2, 1.5, 1.6, 1.5, 1.3, 1.2, 1.3, 1.4,  // 8-3 PM
        1.2, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4   // 4-11 PM
      ];
      
      return hours.map(hour => {
        const factor = hourlyFactors[hour];
        const avgHourlySpend = (totalDailySpend / 24) * factor;
        const avgHourlySales = avgHourlySpend * (1 / ASSUMED_ACOS);
        const clicks = Math.floor(avgHourlySpend / ASSUMED_CPC);
        
        return {
          hour,
          spend: avgHourlySpend,
          sales: avgHourlySales,
          clicks,
          conversions: Math.floor(clicks * ASSUMED_CVR),
          acos: ASSUMED_ACOS,
          performance_score: factor
        };
      });
    };
    
    const hourlyData: HourlyMetric[] = hourlyMetrics.length > 0 ? hourlyMetrics : generateHourlyEstimates();
    
    // Find best and worst performing hours
    const sortedByPerformance = [...hourlyData].sort((a, b) => 
      (b.sales - b.spend) - (a.sales - a.spend)
    );
    const bestHours = sortedByPerformance.slice(0, 3);
    const worstHours = sortedByPerformance.slice(-3).reverse();

    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>⏰ Hourly Analysis</h2>
        <div style={{ padding: '20px' }}>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            {hourlyMetrics.length > 0 
              ? 'Hour-by-hour performance breakdown' 
              : 'Estimated hourly patterns based on available data'}
          </p>
          
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '15px', color: '#333' }}>
              Top Performing Hours
            </h3>
            <div style={styles.statsGrid}>
              {bestHours.map((hour, idx) => (
                <div key={idx} style={styles.statCard}>
                  <div style={styles.statLabel}>
                    {hour.hour}:00 - {hour.hour + 1}:00
                  </div>
                  <div style={styles.statValue}>{formatCurrency(hour.sales)}</div>
                  <div style={{ fontSize: '14px', color: '#666', marginTop: '4px' }}>
                    Spend: {formatCurrency(hour.spend)}
                  </div>
                  <div style={{ fontSize: '14px', color: '#4caf50', marginTop: '4px' }}>
                    ROI: {hour.spend > 0 ? (((hour.sales - hour.spend) / hour.spend * 100).toFixed(0)) : '0'}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '15px', color: '#333' }}>
              Lowest Performing Hours
            </h3>
            <div style={styles.statsGrid}>
              {worstHours.map((hour, idx) => (
                <div key={idx} style={styles.statCard}>
                  <div style={styles.statLabel}>
                    {hour.hour}:00 - {hour.hour + 1}:00
                  </div>
                  <div style={styles.statValue}>{formatCurrency(hour.sales)}</div>
                  <div style={{ fontSize: '14px', color: '#666', marginTop: '4px' }}>
                    Spend: {formatCurrency(hour.spend)}
                  </div>
                  <div style={{ fontSize: '14px', color: '#f44336', marginTop: '4px' }}>
                    ROI: {hour.spend > 0 ? (((hour.sales - hour.spend) / hour.spend * 100).toFixed(0)) : '0'}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 style={{ fontSize: '18px', marginBottom: '15px', color: '#333' }}>
              24-Hour Performance Breakdown
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Hour</th>
                    <th style={styles.th}>Spend</th>
                    <th style={styles.th}>Sales</th>
                    <th style={styles.th}>Clicks</th>
                    <th style={styles.th}>Conv.</th>
                    <th style={styles.th}>ACOS</th>
                    <th style={styles.th}>ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {hourlyData.map((hour, idx) => {
                    const roi = hour.spend > 0 
                      ? ((hour.sales - hour.spend) / hour.spend * 100)
                      : 0;
                    return (
                      <tr key={idx}>
                        <td style={styles.td}>{hour.hour}:00 - {hour.hour + 1}:00</td>
                        <td style={styles.td}>{formatCurrency(hour.spend)}</td>
                        <td style={styles.td}>{formatCurrency(hour.sales)}</td>
                        <td style={styles.td}>{hour.clicks}</td>
                        <td style={styles.td}>{hour.conversions}</td>
                        <td style={styles.td}>{formatPercent(hour.acos)}</td>
                        <td style={styles.td}>{roi.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderSearchTermsTab = () => {
    // Try to get search term data from discovery section or generate from top performers
    const discoveryData = liveSections.discovery?.data;
    const topPerformersFromResults = recentResults.length > 0 && recentResults[0].top_performers 
      ? recentResults[0].top_performers 
      : [];
    
    // Use top performers as proxy for search terms if no dedicated search term data
    const searchTerms = discoveryData?.search_terms || topPerformersFromResults.map((kw, idx) => ({
      search_term: kw.keyword_text,
      keyword_matched: kw.keyword_text,
      match_type: idx % 3 === 0 ? 'EXACT' : idx % 3 === 1 ? 'PHRASE' : 'BROAD',
      impressions: kw.clicks * 12, // Estimate
      clicks: kw.clicks,
      spend: kw.clicks * ASSUMED_CPC,
      sales: kw.sales,
      orders: Math.ceil(kw.sales / 45), // Assume $45 AOV
      acos: kw.acos,
      conversion_rate: (Math.ceil(kw.sales / 45) / kw.clicks * 100),
      ctr: (kw.clicks / (kw.clicks * 12) * 100) // CTR estimate
    }));
    
    // Calculate metrics
    const totalImpressions = searchTerms.reduce((sum: number, t: SearchTerm) => sum + (t.impressions || 0), 0);
    const totalClicks = searchTerms.reduce((sum: number, t: SearchTerm) => sum + (t.clicks || 0), 0);
    const totalSpend = searchTerms.reduce((sum: number, t: SearchTerm) => sum + (t.spend || 0), 0);
    const totalSales = searchTerms.reduce((sum: number, t: SearchTerm) => sum + (t.sales || 0), 0);
    const avgCTR = totalImpressions > 0 ? (totalClicks / totalImpressions * 100) : 0;
    const avgAcos = totalSpend > 0 ? (totalSpend / totalSales) : 0;
    
    // Find opportunity keywords (high impressions, low CTR or high ACOS)
    const opportunities = searchTerms
      .filter((t: SearchTerm) => t.impressions > MIN_IMPRESSIONS_THRESHOLD && (t.ctr < LOW_CTR_THRESHOLD || t.acos > HIGH_ACOS_THRESHOLD))
      .slice(0, 5);

    return (
      <div style={styles.tableCard}>
        <h2 style={styles.tableTitle}>🔎 Search Terms Report</h2>
        <div style={{ padding: '20px' }}>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            {discoveryData?.search_terms 
              ? 'Customer search terms that triggered your ads' 
              : 'Top performing keywords (search term data when available)'}
          </p>
          
          <div style={styles.statsGrid}>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Total Impressions</div>
              <div style={styles.statValue}>{totalImpressions.toLocaleString()}</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Total Clicks</div>
              <div style={styles.statValue}>{totalClicks.toLocaleString()}</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Avg CTR</div>
              <div style={styles.statValue}>{avgCTR.toFixed(2)}%</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Avg ACOS</div>
              <div style={styles.statValue}>{formatPercent(avgAcos)}</div>
            </div>
          </div>

          {opportunities.length > 0 && (
            <div style={{ marginTop: '30px', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '18px', marginBottom: '10px', color: '#ff9800' }}>
                ⚠️ Optimization Opportunities
              </h3>
              <p style={{ fontSize: '14px', color: '#666', marginBottom: '15px' }}>
                Terms with high impressions but low performance - consider refining bids or adding as negative keywords
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Search Term</th>
                      <th style={styles.th}>Impressions</th>
                      <th style={styles.th}>CTR</th>
                      <th style={styles.th}>ACOS</th>
                      <th style={styles.th}>Recommendation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opportunities.map((term: any, idx: number) => (
                      <tr key={idx}>
                        <td style={styles.td}>{term.search_term}</td>
                        <td style={styles.td}>{term.impressions.toLocaleString()}</td>
                        <td style={styles.td}>{term.ctr.toFixed(2)}%</td>
                        <td style={styles.td}>{formatPercent(term.acos)}</td>
                        <td style={styles.td}>
                          {term.ctr < 1 ? 'Improve ad relevance' : 'Review profitability'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div style={{ marginTop: '30px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '15px', color: '#333' }}>
              All Search Terms
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Search Term</th>
                    <th style={styles.th}>Match Type</th>
                    <th style={styles.th}>Impressions</th>
                    <th style={styles.th}>Clicks</th>
                    <th style={styles.th}>CTR</th>
                    <th style={styles.th}>Spend</th>
                    <th style={styles.th}>Sales</th>
                    <th style={styles.th}>Orders</th>
                    <th style={styles.th}>ACOS</th>
                    <th style={styles.th}>CVR</th>
                  </tr>
                </thead>
                <tbody>
                  {searchTerms.slice(0, 50).map((term: any, idx: number) => (
                    <tr key={idx}>
                      <td style={styles.td}>{term.search_term}</td>
                      <td style={styles.td}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          fontSize: '12px',
                          backgroundColor: 
                            term.match_type === 'EXACT' ? '#e3f2fd' : 
                            term.match_type === 'PHRASE' ? '#f3e5f5' : '#fff3e0',
                          color: 
                            term.match_type === 'EXACT' ? '#1976d2' : 
                            term.match_type === 'PHRASE' ? '#7b1fa2' : '#f57c00'
                        }}>
                          {term.match_type}
                        </span>
                      </td>
                      <td style={styles.td}>{term.impressions.toLocaleString()}</td>
                      <td style={styles.td}>{term.clicks}</td>
                      <td style={styles.td}>{term.ctr.toFixed(2)}%</td>
                      <td style={styles.td}>{formatCurrency(term.spend)}</td>
                      <td style={styles.td}>{formatCurrency(term.sales)}</td>
                      <td style={styles.td}>{term.orders}</td>
                      <td style={styles.td}>{formatPercent(term.acos)}</td>
                      <td style={styles.td}>{term.conversion_rate.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  };

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

      {/* Demo Mode Banner */}
      {isDemoMode && (
        <div style={{
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '8px',
          padding: '15px',
          margin: '20px',
          textAlign: 'center',
        }}>
          <p style={{ margin: 0, color: '#856404', fontWeight: 'bold' }}>
            🎭 Demo Mode: Displaying sample data for preview
          </p>
          <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#856404' }}>
            Configure backend services to see live optimization data
          </p>
        </div>
      )}

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
        {recentResults.length > 0 && (
          <p style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
            Most recent optimization run: {formatDate(recentResults[0].timestamp)}
          </p>
        )}
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
