/**
 * CTF Sidecar Controller
 * Handles the slide-out CTF panel in the vendor portal
 */

class CTFSidecar {
    constructor() {
        this.sidecar = document.getElementById('ctf-sidecar');
        this.overlay = document.getElementById('ctf-sidecar-overlay');
        this.closeBtn = document.getElementById('ctf-sidecar-close');
        this.loading = document.getElementById('ctf-sidecar-loading');
        this.mainContent = document.getElementById('ctf-sidecar-main');

        this.isOpen = false;
        this.ws = null;
        this.wsReconnectTimer = null;

        this.init();
    }

    init() {
        // Close button
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }

        // Overlay click
        if (this.overlay) {
            this.overlay.addEventListener('click', () => this.close());
        }

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });

        // Open button (from footer)
        const openBtn = document.querySelector('[data-ctf-sidecar-toggle]');
        if (openBtn) {
            openBtn.addEventListener('click', () => this.toggle());
        }
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        if (!this.sidecar) return;

        this.sidecar.classList.remove('closed');
        this.sidecar.classList.add('open');
        this.sidecar.setAttribute('aria-hidden', 'false');

        if (this.overlay) {
            this.overlay.classList.remove('hidden');
            setTimeout(() => this.overlay.classList.add('visible'), 10);
        }

        this.isOpen = true;
        document.body.style.overflow = 'hidden';

        // Load data
        this.loadData();

        // Connect WebSocket
        this.connectWebSocket();
    }

    close() {
        if (!this.sidecar) return;

        this.sidecar.classList.remove('open');
        this.sidecar.classList.add('closed');
        this.sidecar.setAttribute('aria-hidden', 'true');

        if (this.overlay) {
            this.overlay.classList.remove('visible');
            setTimeout(() => this.overlay.classList.add('hidden'), 300);
        }

        this.isOpen = false;
        document.body.style.overflow = '';

        // Disconnect WebSocket when closed
        this.disconnectWebSocket();
    }

    async loadData() {
        this.showLoading(true);

        try {
            const response = await fetch('/ctf/api/v1/sidecar');
            if (!response.ok) throw new Error('Failed to load CTF data');

            const data = await response.json();
            this.renderData(data);
        } catch (error) {
            console.error('CTF Sidecar: Failed to load data', error);
            this.showError('Failed to load CTF data');
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        if (this.loading) {
            this.loading.classList.toggle('hidden', !show);
        }
        if (this.mainContent) {
            this.mainContent.classList.toggle('hidden', show);
        }
    }

    showError(message) {
        if (this.mainContent) {
            this.mainContent.innerHTML = `
                <div class="ctf-section text-center py-8">
                    <span class="text-4xl">⚠️</span>
                    <p class="text-gray-400 mt-2">${message}</p>
                    <button onclick="window.ctfSidecar.loadData()" class="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">
                        Retry
                    </button>
                </div>
            `;
            this.mainContent.classList.remove('hidden');
        }
    }

    renderData(data) {
        // Points
        const pointsEl = document.getElementById('ctf-points');
        if (pointsEl) pointsEl.textContent = data.points || 0;

        // Completed / Total
        const completedEl = document.getElementById('ctf-completed');
        const totalEl = document.getElementById('ctf-total');
        if (completedEl) completedEl.textContent = data.completed || 0;
        if (totalEl) totalEl.textContent = data.total || 0;

        // Progress
        const progressFill = document.getElementById('ctf-progress-fill');
        const percentageEl = document.getElementById('ctf-percentage');
        const pct = data.completion_percentage || 0;
        if (progressFill) progressFill.style.width = `${pct}%`;
        if (percentageEl) percentageEl.textContent = pct;

        // Badges
        this.renderBadges(data.badges || [], data.badges_count || 0);

        // Active Challenges
        this.renderActiveChallenges(data.active_challenges || []);

        // Activity Stream
        this.renderActivity(data.recent_activity || []);
    }

    renderBadges(badges, totalCount) {
        const grid = document.getElementById('ctf-badges-grid');
        const countEl = document.getElementById('ctf-badges-count');

        if (countEl) countEl.textContent = totalCount;

        if (!grid) return;

        if (badges.length === 0) {
            grid.innerHTML = `
                <div class="ctf-badge-empty">
                    <span class="text-gray-600">No badges earned yet</span>
                </div>
            `;
            return;
        }

        grid.innerHTML = badges.map(badge => `
            <div class="ctf-badge-item rarity-${badge.rarity}" title="${badge.title}">
                <img src="static/images/ctf/badges/${badge.icon_url}" alt="${badge.title}" class="w-6 h-6">
            </div>
        `).join('');
    }

    renderActiveChallenges(challenges) {
        const container = document.getElementById('ctf-active-challenges');
        if (!container) return;

        if (challenges.length === 0) {
            container.innerHTML = `
                <div class="ctf-empty-state">
                    <p class="text-gray-500 text-sm">Start exploring to discover challenges!</p>
                </div>
            `;
            return;
        }

        container.innerHTML = challenges.map(c => `
            <div class="ctf-challenge-card">
                <div class="ctf-challenge-title">${this.escapeHtml(c.title)}</div>
                <div class="ctf-challenge-meta">
                    <span class="ctf-challenge-points">${c.points} pts</span>
                    <span class="ctf-difficulty-badge ctf-difficulty-${c.difficulty}">${c.difficulty}</span>
                    <span>${c.category}</span>
                    ${c.attempts > 0 ? `<span>• ${c.attempts} attempts</span>` : ''}
                </div>
            </div>
        `).join('');
    }

    renderActivity(activities) {
        const container = document.getElementById('ctf-activity-stream');
        if (!container) return;

        if (activities.length === 0) {
            container.innerHTML = `
                <div class="ctf-empty-state">
                    <p class="text-gray-500 text-sm">No activity yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = activities.map(a => this.createActivityItem(a)).join('');
    }

    createActivityItem(activity) {
        const icon = this.getActivityIcon(activity.category);
        const timeAgo = this.formatTimeAgo(activity.timestamp);

        return `
            <div class="ctf-activity-item">
                <div class="ctf-activity-icon ${activity.category}">${icon}</div>
                <div class="ctf-activity-content">
                    <div class="ctf-activity-summary">${this.escapeHtml(activity.summary || activity.type)}</div>
                    <div class="ctf-activity-time">${timeAgo}</div>
                </div>
            </div>
        `;
    }

    getActivityIcon(category) {
        switch (category) {
            case 'agent': return '🤖';
            case 'business': return '📊';
            case 'ctf': return '🎯';
            default: return '📌';
        }
    }

    formatTimeAgo(timestamp) {
        if (!timestamp) return '';

        const now = new Date();
        const then = new Date(timestamp);
        const seconds = Math.floor((now - then) / 1000);

        if (seconds < 60) return `${seconds}s ago`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // WebSocket for live updates
    connectWebSocket() {
        // Get namespace and user_id from session (you'll need to expose these)
        const namespace = window.CTF_NAMESPACE || 'default';
        const userId = window.CTF_USER_ID || 'anonymous';

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/connect?namespace=${namespace}&user_id=${userId}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('CTF Sidecar: WebSocket connected');
                this.updateWsStatus('Connected', true);

                // Subscribe to activity topic (server auto-subscribes, but explicit is fine)
                this.ws.send(JSON.stringify({
                    action: 'subscribe',
                    topic: `activity:${namespace}:${userId}`
                }));
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWsMessage(data);
                } catch (e) {
                    console.error('CTF Sidecar: Invalid WS message', e);
                }
            };

            this.ws.onclose = () => {
                console.log('CTF Sidecar: WebSocket disconnected');
                this.updateWsStatus('Disconnected', false);

                // Reconnect if sidecar is still open
                if (this.isOpen) {
                    this.wsReconnectTimer = setTimeout(() => this.connectWebSocket(), 5000);
                }
            };

            this.ws.onerror = (error) => {
                console.error('CTF Sidecar: WebSocket error', error);
                this.updateWsStatus('Error', false);
            };

        } catch (error) {
            console.error('CTF Sidecar: Failed to connect WebSocket', error);
            this.updateWsStatus('Failed', false);
        }
    }

    disconnectWebSocket() {
        if (this.wsReconnectTimer) {
            clearTimeout(this.wsReconnectTimer);
            this.wsReconnectTimer = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    updateWsStatus(status, connected) {
        const statusEl = document.getElementById('ctf-ws-status');
        if (statusEl) {
            statusEl.textContent = status;
            statusEl.className = `text-xs ${connected ? 'text-green-500' : 'text-gray-500'}`;
        }
    }

    handleWsMessage(data) {
        if (!data.type) return;

        switch (data.type) {
            case 'connected':
                console.log('CTF Sidecar: Server confirmed connection', data.data);
                break;
            case 'subscribed':
                console.log('CTF Sidecar: Subscribed to', data.data?.topic);
                break;
            case 'pong':
                // Heartbeat response
                break;
            case 'error':
                console.warn('CTF Sidecar: Server error', data.data?.message);
                break;
            case 'activity':
                this.prependActivity(data.data);
                break;
            case 'challenge_completed':
                this.showNotification('🎯 Challenge Completed!', data.data.title);
                this.loadData(); // Refresh data
                break;
            case 'badge_earned':
                this.showNotification('🎖️ Badge Earned!', data.data.title);
                this.loadData(); // Refresh data
                break;
            default:
                console.log('CTF Sidecar: Unknown message type', data.type);
        }
    }

    prependActivity(activity) {
        const container = document.getElementById('ctf-activity-stream');
        if (!container) return;

        // Remove empty state if present
        const emptyState = container.querySelector('.ctf-empty-state');
        if (emptyState) emptyState.remove();

        // Add new activity at top
        const html = this.createActivityItem(activity);
        container.insertAdjacentHTML('afterbegin', html);

        // Limit to 10 items
        const items = container.querySelectorAll('.ctf-activity-item');
        if (items.length > 10) {
            items[items.length - 1].remove();
        }
    }

    showNotification(title, message) {
        // Simple notification - you could enhance this
        console.log(`CTF: ${title} - ${message}`);

        // Could use browser notifications if permission granted
        if (Notification.permission === 'granted') {
            new Notification(title, { body: message, icon: '/static/images/common/finbot.png' });
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.ctfSidecar = new CTFSidecar();
});
