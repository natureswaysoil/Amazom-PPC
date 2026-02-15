/**
 * API Client
 * ==========
 * Handles all API communication with the backend
 */

const API_BASE_URL = window.location.origin;

class APIClient {
    constructor() {
        this.baseURL = API_BASE_URL;
    }

    /**
     * Make API request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'Request failed' }));
                throw new Error(error.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    }

    /**
     * Get revenue data
     */
    async getRevenue(startDate, endDate) {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        return this.request(`/api/dashboard/revenue?${params}`);
    }

    /**
     * Get orders data
     */
    async getOrders(startDate, endDate) {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        return this.request(`/api/dashboard/orders?${params}`);
    }

    /**
     * Get top products
     */
    async getTopProducts(limit = 10, metric = 'revenue', startDate = null, endDate = null) {
        const params = new URLSearchParams();
        params.append('limit', limit);
        params.append('metric', metric);
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        return this.request(`/api/dashboard/products/top?${params}`);
    }

    /**
     * Get inventory data
     */
    async getInventory() {
        return this.request('/api/dashboard/inventory');
    }

    /**
     * Get customer metrics
     */
    async getCustomers(startDate, endDate) {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        return this.request(`/api/dashboard/customers?${params}`);
    }

    /**
     * Get system status
     */
    async getStatus() {
        return this.request('/api/dashboard/status');
    }

    /**
     * Clear cache
     */
    async clearCache() {
        return this.request('/api/dashboard/cache/clear', {
            method: 'POST'
        });
    }
}

// Export singleton instance
const apiClient = new APIClient();
