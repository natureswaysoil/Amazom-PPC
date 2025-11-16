// Amazon PPC Dashboard JavaScript

let currentTable = null;
let currentPage = 0;
let totalCount = 0;
let dailyChart = null;
let campaignChart = null;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    loadSummary();
    loadTables();
    loadCharts();
    updateLastUpdateTime();
    
    // Auto-refresh every 5 minutes
    setInterval(() => {
        loadSummary();
        loadCharts();
        if (currentTable) {
            refreshTableData();
        }
    }, 300000);
});

// Load summary statistics
async function loadSummary() {
    try {
        const response = await fetch('/api/summary');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading summary:', data.error);
            return;
        }
        
        const summary = data.summary || {};
        
        document.getElementById('total-runs').textContent = 
            formatNumber(summary.total_runs || 0);
        document.getElementById('total-keywords').textContent = 
            formatNumber(summary.total_keywords_optimized || 0);
        document.getElementById('avg-acos').textContent = 
            formatPercent(summary.avg_acos || 0);
        document.getElementById('total-spend').textContent = 
            formatCurrency(summary.total_spend || 0);
        document.getElementById('total-sales').textContent = 
            formatCurrency(summary.total_sales || 0);
        
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

// Load available tables
async function loadTables() {
    try {
        const response = await fetch('/api/tables');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading tables:', data.error);
            return;
        }
        
        const tablesList = document.getElementById('tables-list');
        tablesList.innerHTML = '';
        
        data.tables.forEach(table => {
            const tableItem = document.createElement('div');
            tableItem.className = 'table-item';
            tableItem.onclick = () => viewTable(table.table_id);
            
            tableItem.innerHTML = `
                <h3>${table.table_id}</h3>
                <div class="table-info">
                    <p>Rows: ${formatNumber(table.num_rows)}</p>
                    <p>Size: ${formatBytes(table.size_bytes)}</p>
                    <p>Last Modified: ${formatDate(table.modified)}</p>
                </div>
            `;
            
            tablesList.appendChild(tableItem);
        });
        
    } catch (error) {
        console.error('Error loading tables:', error);
    }
}

// Load charts
async function loadCharts() {
    try {
        // Load daily performance chart
        const dailyResponse = await fetch('/api/chart-data/daily_performance?days=30');
        const dailyData = await dailyResponse.json();
        
        if (!dailyData.error) {
            renderDailyChart(dailyData.data);
        }
        
        // Load campaign performance chart
        const campaignResponse = await fetch('/api/chart-data/campaign_performance?days=30');
        const campaignData = await campaignResponse.json();
        
        if (!campaignData.error) {
            renderCampaignChart(campaignData.data);
        }
        
    } catch (error) {
        console.error('Error loading charts:', error);
    }
}

// Render daily performance chart
function renderDailyChart(data) {
    const ctx = document.getElementById('daily-chart');
    
    if (dailyChart) {
        dailyChart.destroy();
    }
    
    const labels = data.map(d => d.date).reverse();
    const spendData = data.map(d => d.total_spend || 0).reverse();
    const salesData = data.map(d => d.total_sales || 0).reverse();
    
    dailyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Spend ($)',
                    data: spendData,
                    borderColor: '#d13212',
                    backgroundColor: 'rgba(209, 50, 18, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Sales ($)',
                    data: salesData,
                    borderColor: '#00a650',
                    backgroundColor: 'rgba(0, 166, 80, 0.1)',
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top',
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Render campaign performance chart
function renderCampaignChart(data) {
    const ctx = document.getElementById('campaign-chart');
    
    if (campaignChart) {
        campaignChart.destroy();
    }
    
    const labels = data.map(d => d.campaign_name);
    const spendData = data.map(d => d.total_spend || 0);
    
    campaignChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Spend ($)',
                data: spendData,
                backgroundColor: '#146eb4'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// View table data
async function viewTable(tableName) {
    currentTable = tableName;
    currentPage = 0;
    
    document.getElementById('current-table-name').textContent = tableName;
    document.getElementById('table-viewer').style.display = 'block';
    
    // Scroll to table viewer
    document.getElementById('table-viewer').scrollIntoView({ behavior: 'smooth' });
    
    await loadTableData();
}

// Load table data
async function loadTableData() {
    if (!currentTable) return;
    
    const days = document.getElementById('filter-days').value;
    const limit = document.getElementById('filter-limit').value;
    const offset = currentPage * limit;
    
    try {
        const response = await fetch(
            `/api/table/${currentTable}?limit=${limit}&offset=${offset}&days=${days}`
        );
        const data = await response.json();
        
        if (data.error) {
            alert('Error loading table data: ' + data.error);
            return;
        }
        
        totalCount = data.total_count;
        renderTable(data.rows);
        updatePagination();
        
    } catch (error) {
        console.error('Error loading table data:', error);
        alert('Error loading table data: ' + error.message);
    }
}

// Render table data
function renderTable(rows) {
    const thead = document.getElementById('table-header');
    const tbody = document.getElementById('table-body');
    
    thead.innerHTML = '';
    tbody.innerHTML = '';
    
    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="100">No data available</td></tr>';
        return;
    }
    
    // Create header
    const headerRow = document.createElement('tr');
    Object.keys(rows[0]).forEach(key => {
        const th = document.createElement('th');
        th.textContent = key;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    
    // Create body rows
    rows.forEach(row => {
        const tr = document.createElement('tr');
        Object.values(row).forEach(value => {
            const td = document.createElement('td');
            td.textContent = formatValue(value);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

// Update pagination controls
function updatePagination() {
    const limit = parseInt(document.getElementById('filter-limit').value);
    const totalPages = Math.ceil(totalCount / limit);
    const currentPageNum = currentPage + 1;
    
    document.getElementById('page-info').textContent = 
        `Page ${currentPageNum} of ${totalPages}`;
    document.getElementById('pagination-info').textContent = 
        `Showing ${currentPage * limit + 1} - ${Math.min((currentPage + 1) * limit, totalCount)} of ${totalCount}`;
    
    document.getElementById('prev-page').disabled = currentPage === 0;
    document.getElementById('next-page').disabled = currentPageNum >= totalPages;
}

// Pagination functions
function previousPage() {
    if (currentPage > 0) {
        currentPage--;
        loadTableData();
    }
}

function nextPage() {
    const limit = parseInt(document.getElementById('filter-limit').value);
    const totalPages = Math.ceil(totalCount / limit);
    if (currentPage < totalPages - 1) {
        currentPage++;
        loadTableData();
    }
}

function refreshTableData() {
    currentPage = 0;
    loadTableData();
}

function closeTableViewer() {
    document.getElementById('table-viewer').style.display = 'none';
    currentTable = null;
}

// Export to CSV
function exportToCSV() {
    if (!currentTable) return;
    
    const table = document.getElementById('data-table');
    let csv = [];
    
    // Get headers
    const headers = Array.from(table.querySelectorAll('thead th'))
        .map(th => th.textContent);
    csv.push(headers.join(','));
    
    // Get rows
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    rows.forEach(row => {
        const cells = Array.from(row.querySelectorAll('td'))
            .map(td => `"${td.textContent}"`);
        csv.push(cells.join(','));
    });
    
    // Download
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentTable}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

// Utility functions
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return new Intl.NumberFormat('en-US').format(num);
}

function formatCurrency(num) {
    if (num === null || num === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(num);
}

function formatPercent(num) {
    if (num === null || num === undefined) return '0%';
    return (num * 100).toFixed(2) + '%';
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
}

function formatValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
}

function updateLastUpdateTime() {
    document.getElementById('last-update').textContent = new Date().toLocaleString();
}
