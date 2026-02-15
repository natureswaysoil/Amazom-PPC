/**
 * Dashboard Main Controller
 * =========================
 * Orchestrates the dashboard functionality
 */

class Dashboard {
    constructor() {
        this.isLoading = false;
        this.autoRefreshInterval = null;
        this.autoRefreshEnabled = true;
        this.autoRefreshMinutes = 5;
        
        this.initialize();
    }

    /**
     * Initialize dashboard
     */
    initialize() {
        console.log('Initializing Amazon Sales Dashboard...');
        
        // Initialize charts
        dashboardCharts.initializeCharts();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Load initial data
        this.loadAllData();
        
        // Start auto-refresh
        this.startAutoRefresh();
        
        console.log('Dashboard initialized successfully');
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadAllData();
            });
        }
    }

    /**
     * Load all dashboard data
     */
    async loadAllData() {
        if (this.isLoading) {
            console.log('Already loading data, skipping...');
            return;
        }

        this.isLoading = true;
        this.showLoading();

        try {
            const { startDate, endDate } = dateFilter.getDateRange();
            
            console.log(`Loading data for ${startDate} to ${endDate}`);

            // Load all data in parallel
            const [revenue, orders, products, inventory, customers, status] = await Promise.all([
                apiClient.getRevenue(startDate, endDate).catch(e => {
                    console.error('Failed to load revenue:', e);
                    return null;
                }),
                apiClient.getOrders(startDate, endDate).catch(e => {
                    console.error('Failed to load orders:', e);
                    return null;
                }),
                apiClient.getTopProducts(10, 'revenue', startDate, endDate).catch(e => {
                    console.error('Failed to load products:', e);
                    return null;
                }),
                apiClient.getInventory().catch(e => {
                    console.error('Failed to load inventory:', e);
                    return null;
                }),
                apiClient.getCustomers(startDate, endDate).catch(e => {
                    console.error('Failed to load customers:', e);
                    return null;
                }),
                apiClient.getStatus().catch(e => {
                    console.error('Failed to load status:', e);
                    return null;
                })
            ]);

            // Update UI with loaded data
            this.updateKPIs(revenue, orders);
            this.updateCharts(revenue, orders, products);
            this.updateCustomerMetrics(customers);
            this.updateInventoryTable(inventory);
            this.updateLastUpdated();

            console.log('All data loaded successfully');
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data. Please try again.');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }

    /**
     * Update KPI cards
     */
    updateKPIs(revenueData, ordersData) {
        // Revenue
        if (revenueData) {
            const revenueValue = document.getElementById('revenue-value');
            const revenueChange = document.getElementById('revenue-change');
            
            if (revenueValue) {
                revenueValue.textContent = this.formatCurrency(revenueData.total || 0);
            }
            
            if (revenueChange) {
                const change = revenueData.change_percent || 0;
                revenueChange.innerHTML = this.formatChange(change);
            }
        }

        // Orders
        if (ordersData) {
            const ordersValue = document.getElementById('orders-value');
            const ordersChange = document.getElementById('orders-change');
            
            if (ordersValue) {
                ordersValue.textContent = (ordersData.total || 0).toLocaleString();
            }
            
            // Calculate change (mock for now)
            if (ordersChange) {
                ordersChange.innerHTML = this.formatChange(0);
            }
        }

        // Average Order Value
        if (ordersData) {
            const aovValue = document.getElementById('aov-value');
            const aovChange = document.getElementById('aov-change');
            
            if (aovValue) {
                aovValue.textContent = this.formatCurrency(ordersData.average_order_value || 0);
            }
            
            if (aovChange) {
                aovChange.innerHTML = this.formatChange(0);
            }
        }

        // Conversion Rate (mock data)
        const conversionValue = document.getElementById('conversion-value');
        const conversionChange = document.getElementById('conversion-change');
        
        if (conversionValue) {
            conversionValue.textContent = '15.0%'; // Mock data
        }
        
        if (conversionChange) {
            conversionChange.innerHTML = this.formatChange(2.5);
        }
    }

    /**
     * Update charts
     */
    updateCharts(revenueData, ordersData, productsData) {
        if (revenueData) {
            dashboardCharts.updateRevenueChart(revenueData);
        }

        if (ordersData) {
            dashboardCharts.updateOrderStatusChart(ordersData);
        }

        if (productsData) {
            dashboardCharts.updateTopProductsChart(productsData);
        }
    }

    /**
     * Update customer metrics
     */
    updateCustomerMetrics(data) {
        if (!data) return;

        this.updateElement('total-customers', (data.total_customers || 0).toLocaleString());
        this.updateElement('new-customers', (data.new_customers || 0).toLocaleString());
        this.updateElement('returning-customers', (data.returning_customers || 0).toLocaleString());
        this.updateElement('avg-clv', this.formatCurrency(data.clv || 0));
        this.updateElement('avg-rating', `${(data.avg_rating || 0).toFixed(1)} ⭐`);
    }

    /**
     * Update inventory table
     */
    updateInventoryTable(data) {
        const tbody = document.getElementById('inventory-table-body');
        if (!tbody) return;

        if (!data || !data.items || data.items.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-gray-500 py-8">
                        No inventory data available
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = data.items.map(item => {
            const statusBadge = this.getStatusBadge(item.status || 'unknown');
            return `
                <tr>
                    <td>${statusBadge}</td>
                    <td class="font-mono">${item.asin || 'N/A'}</td>
                    <td>${item.name || 'Unknown Product'}</td>
                    <td>${(item.qty || 0).toLocaleString()}</td>
                    <td>${item.days_in_inventory || 0} days</td>
                    <td>
                        <button class="btn-secondary text-xs py-1 px-2">View Details</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    /**
     * Get status badge HTML
     */
    getStatusBadge(status) {
        const badges = {
            'in_stock': '<span class="status-badge status-badge-success">✅ In Stock</span>',
            'low_stock': '<span class="status-badge status-badge-warning">⚠️ Low Stock</span>',
            'out_of_stock': '<span class="status-badge status-badge-error">❌ Out of Stock</span>',
            'unknown': '<span class="status-badge">❓ Unknown</span>'
        };
        return badges[status] || badges.unknown;
    }

    /**
     * Update last updated timestamp
     */
    updateLastUpdated() {
        const element = document.getElementById('last-updated');
        if (!element) return;

        const now = new Date();
        const time = now.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        element.textContent = time;
    }

    /**
     * Format currency
     */
    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }

    /**
     * Format change percentage
     */
    formatChange(percent) {
        const isPositive = percent >= 0;
        const isNeutral = percent === 0;
        const arrow = isPositive ? '↑' : '↓';
        const className = isNeutral ? 'change-neutral' : (isPositive ? 'change-positive' : 'change-negative');
        
        return `<span class="change-indicator ${className}">${arrow} ${Math.abs(percent).toFixed(1)}%</span>`;
    }

    /**
     * Update element text content
     */
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    /**
     * Show loading overlay
     */
    showLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
        }
        
        // Animate refresh icon
        const refreshIcon = document.getElementById('refresh-icon');
        if (refreshIcon) {
            refreshIcon.style.animation = 'spin 1s linear infinite';
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
        
        // Stop refresh icon animation
        const refreshIcon = document.getElementById('refresh-icon');
        if (refreshIcon) {
            refreshIcon.style.animation = '';
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        alert(message); // Simple alert for now, can be enhanced with a toast notification
    }

    /**
     * Start auto-refresh
     */
    startAutoRefresh() {
        if (!this.autoRefreshEnabled) return;

        this.autoRefreshInterval = setInterval(() => {
            console.log('Auto-refreshing dashboard...');
            this.loadAllData();
        }, this.autoRefreshMinutes * 60 * 1000);

        console.log(`Auto-refresh enabled (every ${this.autoRefreshMinutes} minutes)`);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
            console.log('Auto-refresh disabled');
        }
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});

// Add spin animation for refresh icon
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
