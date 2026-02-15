/**
 * Date Range Filters
 * ==================
 * Handles date range selection and filtering
 */

class DateRangeFilter {
    constructor() {
        this.startDate = null;
        this.endDate = null;
        this.currentRange = '30'; // Default to last 30 days
        
        this.initializeDefaultRange();
        this.initializeEventListeners();
        this.updateURLParams();
    }

    /**
     * Initialize default date range
     */
    initializeDefaultRange() {
        const urlParams = new URLSearchParams(window.location.search);
        const start = urlParams.get('start_date');
        const end = urlParams.get('end_date');
        const range = urlParams.get('range');
        
        if (start && end) {
            this.startDate = start;
            this.endDate = end;
            this.currentRange = 'custom';
        } else if (range) {
            this.currentRange = range;
            this.setDateRange(range);
        } else {
            this.setDateRange('30'); // Default to last 30 days
        }
    }

    /**
     * Set up event listeners for date range buttons
     */
    initializeEventListeners() {
        // Date range buttons
        document.querySelectorAll('.date-range-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const range = e.target.dataset.range;
                this.setDateRange(range);
                this.updateActiveButton(e.target);
                this.updateURLParams();
                
                // Trigger data reload
                if (window.dashboard) {
                    window.dashboard.loadAllData();
                }
            });
        });

        // Custom date range
        const applyBtn = document.getElementById('apply-custom-range');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyCustomRange();
            });
        }
    }

    /**
     * Set date range based on preset
     */
    setDateRange(range) {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        let start, end;
        
        switch(range) {
            case 'today':
                start = end = this.formatDate(today);
                break;
                
            case 'yesterday':
                start = end = this.formatDate(yesterday);
                break;
                
            case '7':
                end = this.formatDate(today);
                start = this.formatDate(new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000));
                break;
                
            case '30':
                end = this.formatDate(today);
                start = this.formatDate(new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000));
                break;
                
            case '90':
                end = this.formatDate(today);
                start = this.formatDate(new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000));
                break;
                
            case 'this-month':
                start = this.formatDate(new Date(today.getFullYear(), today.getMonth(), 1));
                end = this.formatDate(today);
                break;
                
            case 'last-month':
                const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                start = this.formatDate(lastMonth);
                end = this.formatDate(new Date(today.getFullYear(), today.getMonth(), 0));
                break;
                
            case 'this-year':
                start = this.formatDate(new Date(today.getFullYear(), 0, 1));
                end = this.formatDate(today);
                break;
                
            default:
                // Default to last 30 days
                end = this.formatDate(today);
                start = this.formatDate(new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000));
        }
        
        this.startDate = start;
        this.endDate = end;
        this.currentRange = range;
        
        // Update custom date inputs
        document.getElementById('custom-start').value = start;
        document.getElementById('custom-end').value = end;
    }

    /**
     * Apply custom date range
     */
    applyCustomRange() {
        const startInput = document.getElementById('custom-start');
        const endInput = document.getElementById('custom-end');
        
        if (startInput.value && endInput.value) {
            this.startDate = startInput.value;
            this.endDate = endInput.value;
            this.currentRange = 'custom';
            
            // Update active button
            document.querySelectorAll('.date-range-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            this.updateURLParams();
            
            // Trigger data reload
            if (window.dashboard) {
                window.dashboard.loadAllData();
            }
        } else {
            this.showError('Please select both start and end dates');
        }
    }
    
    /**
     * Show error message
     */
    showError(message) {
        // Create a toast notification
        const toast = document.createElement('div');
        toast.className = 'fixed bottom-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50';
        toast.style.animation = 'fadeIn 0.3s ease-out';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
        
        // Also log for debugging
        console.error('Filter error:', message);
    }

    /**
     * Update active button state
     */
    updateActiveButton(activeBtn) {
        document.querySelectorAll('.date-range-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        activeBtn.classList.add('active');
    }

    /**
     * Update URL parameters
     */
    updateURLParams() {
        const params = new URLSearchParams();
        params.set('start_date', this.startDate);
        params.set('end_date', this.endDate);
        params.set('range', this.currentRange);
        
        const newURL = `${window.location.pathname}?${params.toString()}`;
        window.history.replaceState({}, '', newURL);
    }

    /**
     * Format date as YYYY-MM-DD
     */
    formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    /**
     * Get current date range
     */
    getDateRange() {
        return {
            startDate: this.startDate,
            endDate: this.endDate,
            range: this.currentRange
        };
    }
}

// Export singleton instance
const dateFilter = new DateRangeFilter();
