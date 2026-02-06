/**
 * FinBot CTF API Client
 * Wrapper for CTF-specific API calls
 */

const CTF = {
    /**
     * Base URL for CTF API
     */
    baseURL: '/ctf/api/v1',

    /**
     * Make a fetch request to the CTF API
     */
    async fetch(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Add CSRF token for non-GET requests
        if (options.method && options.method !== 'GET') {
            const csrfToken = this.getCSRFToken();
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken;
            }
        }

        const config = {
            credentials: 'same-origin',
            ...options,
            headers
        };

        const response = await fetch(url, config);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`);
        }

        return response.json();
    },

    /**
     * Get CSRF token from meta tag
     */
    getCSRFToken() {
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }
        return null;
    },

    /**
     * Get user stats
     */
    async getStats() {
        return this.fetch('/stats');
    },

    /**
     * Get all challenges with optional filters
     */
    async getChallenges(filters = {}) {
        const params = new URLSearchParams();
        if (filters.category) params.append('category', filters.category);
        if (filters.difficulty) params.append('difficulty', filters.difficulty);
        if (filters.status) params.append('status', filters.status);

        const queryString = params.toString();
        const endpoint = queryString ? `/challenges?${queryString}` : '/challenges';
        return this.fetch(endpoint);
    },

    /**
     * Get single challenge details
     */
    async getChallenge(challengeId) {
        return this.fetch(`/challenges/${challengeId}`);
    },

    /**
     * Check challenge completion
     */
    async checkChallenge(challengeId) {
        return this.fetch(`/challenges/${challengeId}/check`, {
            method: 'POST'
        });
    },

    /**
     * Use a hint for a challenge
     */
    async useHint(challengeId) {
        return this.fetch(`/challenges/${challengeId}/hint`, {
            method: 'POST'
        });
    },

    /**
     * Get all badges
     */
    async getBadges(filters = {}) {
        const params = new URLSearchParams();
        if (filters.category) params.append('category', filters.category);
        if (filters.earned_only) params.append('earned_only', 'true');

        const queryString = params.toString();
        const endpoint = queryString ? `/badges?${queryString}` : '/badges';
        return this.fetch(endpoint);
    },

    /**
     * Get badge details
     */
    async getBadge(badgeId) {
        return this.fetch(`/badges/${badgeId}`);
    },

    /**
     * Get activity stream
     */
    async getActivity(options = {}) {
        const params = new URLSearchParams();
        if (options.page) params.append('page', options.page);
        if (options.page_size) params.append('page_size', options.page_size);
        if (options.category) params.append('category', options.category);
        if (options.workflow_id) params.append('workflow_id', options.workflow_id);
        if (options.vendor_id) params.append('vendor_id', options.vendor_id);

        const queryString = params.toString();
        const endpoint = queryString ? `/activity?${queryString}` : '/activity';
        return this.fetch(endpoint);
    }
};

/**
 * Get CSS class for difficulty badge
 */
function getDifficultyClass(difficulty) {
    const classes = {
        'beginner': 'diff-beginner',
        'intermediate': 'diff-intermediate',
        'advanced': 'diff-advanced',
        'expert': 'diff-expert'
    };
    return classes[difficulty] || 'diff-beginner';
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    // Check if showNotification exists (from utils.js)
    if (typeof showNotification === 'function') {
        showNotification(message, type);
        return;
    }

    // Fallback simple toast
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg z-50 transition-all transform translate-y-0 opacity-100`;

    // Type-specific styling
    const styles = {
        'success': 'bg-ctf-accent/90 text-portal-bg-primary',
        'error': 'bg-ctf-danger/90 text-white',
        'warning': 'bg-ctf-warning/90 text-portal-bg-primary',
        'info': 'bg-ctf-primary/90 text-portal-bg-primary'
    };
    toast.className += ` ${styles[type] || styles.info}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * Update sidebar points display (runs on all pages)
 */
async function updateSidebarPoints() {
    const sidebarPoints = document.getElementById('sidebar-points');
    if (!sidebarPoints) return;

    try {
        const stats = await CTF.getStats();
        if (stats && typeof stats.total_points === 'number') {
            sidebarPoints.textContent = `${stats.total_points.toLocaleString()} pts`;
        }
    } catch (error) {
        console.warn('Failed to load sidebar points:', error);
        // Leave as default "-- pts"
    }
}

// Update sidebar points on page load
document.addEventListener('DOMContentLoaded', updateSidebarPoints);

// Export globally
window.CTF = CTF;
window.getDifficultyClass = getDifficultyClass;
window.showToast = showToast;
window.updateSidebarPoints = updateSidebarPoints;
