/**
 * Charts Module
 * =============
 * Handles all chart rendering using Chart.js
 */

class DashboardCharts {
    constructor() {
        this.charts = {};
        this.chartColors = {
            primary: '#ff9900',
            secondary: '#232f3e',
            success: '#10b981',
            warning: '#f59e0b',
            error: '#ef4444',
            info: '#3b82f6',
            purple: '#8b5cf6',
            pink: '#ec4899'
        };
    }

    /**
     * Initialize all charts
     */
    initializeCharts() {
        this.createRevenueChart();
        this.createOrderStatusChart();
        this.createTopProductsChart();
    }

    /**
     * Create revenue trend chart
     */
    createRevenueChart() {
        const ctx = document.getElementById('revenue-chart');
        if (!ctx) return;

        if (this.charts.revenue) {
            this.charts.revenue.destroy();
        }

        this.charts.revenue = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Revenue',
                    data: [],
                    borderColor: this.chartColors.primary,
                    backgroundColor: this.chartColors.primary + '20',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                return `Revenue: $${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Update revenue chart with data
     */
    updateRevenueChart(data) {
        if (!this.charts.revenue || !data.daily_breakdown) return;

        const labels = data.daily_breakdown.map(item => item.date || item.label);
        const values = data.daily_breakdown.map(item => item.revenue || item.value);

        this.charts.revenue.data.labels = labels;
        this.charts.revenue.data.datasets[0].data = values;
        this.charts.revenue.update();
    }

    /**
     * Create order status pie chart
     */
    createOrderStatusChart() {
        const ctx = document.getElementById('order-status-chart');
        if (!ctx) return;

        if (this.charts.orderStatus) {
            this.charts.orderStatus.destroy();
        }

        this.charts.orderStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Pending', 'Shipped', 'Delivered', 'Cancelled'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        this.chartColors.warning,
                        this.chartColors.info,
                        this.chartColors.success,
                        this.chartColors.error
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Update order status chart with data
     */
    updateOrderStatusChart(data) {
        if (!this.charts.orderStatus) return;

        this.charts.orderStatus.data.datasets[0].data = [
            data.pending || 0,
            data.shipped || 0,
            data.delivered || 0,
            data.cancelled || 0
        ];
        this.charts.orderStatus.update();
    }

    /**
     * Create top products bar chart
     */
    createTopProductsChart() {
        const ctx = document.getElementById('top-products-chart');
        if (!ctx) return;

        if (this.charts.topProducts) {
            this.charts.topProducts.destroy();
        }

        this.charts.topProducts = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Revenue',
                    data: [],
                    backgroundColor: this.chartColors.primary,
                    borderRadius: 6,
                    maxBarThickness: 50
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Revenue: $${context.parsed.x.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    /**
     * Update top products chart with data
     */
    updateTopProductsChart(data) {
        if (!this.charts.topProducts || !data.products) return;

        const labels = data.products.map(p => p.name || p.asin || 'Unknown');
        const values = data.products.map(p => p.revenue || 0);

        this.charts.topProducts.data.labels = labels;
        this.charts.topProducts.data.datasets[0].data = values;
        this.charts.topProducts.update();
    }

    /**
     * Destroy all charts
     */
    destroyAllCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }
}

// Export singleton instance
const dashboardCharts = new DashboardCharts();
