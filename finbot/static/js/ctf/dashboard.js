/**
 * FinBot CTF Dashboard
 */

// Category color mapping
const CATEGORY_COLORS = {
    'prompt_injection': 'cyan',
    'prompt-injection': 'cyan',
    'data_exfiltration': 'purple',
    'data-exfiltration': 'purple',
    'privilege_escalation': 'green',
    'privilege-escalation': 'green',
    'denial_of_service': 'yellow',
    'denial-of-service': 'yellow',
};

// Challenge category icons
const CATEGORY_ICONS = {
    'prompt_injection': '💉',
    'prompt-injection': '💉',
    'data_exfiltration': '📤',
    'data-exfiltration': '📤',
    'privilege_escalation': '🔓',
    'privilege-escalation': '🔓',
    'denial_of_service': '💥',
    'denial-of-service': '💥',
};

// Activity event icons
const EVENT_ICONS = {
    'agent': { icon: '🤖', class: 'agent' },
    'tool': { icon: '🔧', class: 'tool' },
    'business': { icon: '✅', class: 'success' },
    'llm': { icon: '💡', class: 'llm' },
    'challenge': { icon: '🎯', class: 'challenge' },
    'badge': { icon: '🏆', class: 'badge' },
};

// Badge rarity icons
const RARITY_ICONS = {
    'common': '⭐',
    'rare': '💎',
    'epic': '🌟',
    'legendary': '👑',
};

document.addEventListener('DOMContentLoaded', function () {
    loadDashboardData();
});

/**
 * Load all dashboard data in parallel
 */
async function loadDashboardData() {
    try {
        const [stats, challenges, badges, activity] = await Promise.all([
            fetchStats(),
            fetchChallenges(),
            fetchBadges(),
            fetchActivity(),
        ]);

        renderStats(stats);
        renderActiveChallenges(challenges);
        renderRecentBadges(badges);
        renderActivityFeed(activity);
        renderCategoryProgress(stats.category_progress);

        // Calculate and render activity streak
        renderActivityStreak(activity);

        // Calculate and render points earned today
        renderPointsToday(activity, challenges);

        // Render badge rarity breakdown
        renderBadgeRarityBreakdown(badges);

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

/**
 * Fetch user stats
 */
async function fetchStats() {
    const response = await fetch('/ctf/api/v1/stats');
    if (!response.ok) throw new Error('Failed to fetch stats');
    return response.json();
}

/**
 * Fetch challenges
 */
async function fetchChallenges() {
    const response = await fetch('/ctf/api/v1/challenges');
    if (!response.ok) throw new Error('Failed to fetch challenges');
    return response.json();
}

/**
 * Fetch badges
 */
async function fetchBadges() {
    const response = await fetch('/ctf/api/v1/badges');
    if (!response.ok) throw new Error('Failed to fetch badges');
    return response.json();
}

/**
 * Fetch activity
 */
async function fetchActivity() {
    const response = await fetch('/ctf/api/v1/activity?page_size=5');
    if (!response.ok) throw new Error('Failed to fetch activity');
    return response.json();
}

/**
 * Render stats cards
 */
function renderStats(stats) {
    // Update sidebar points
    const sidebarPoints = document.getElementById('sidebar-points');
    if (sidebarPoints) {
        sidebarPoints.textContent = `${stats.total_points.toLocaleString()} pts`;
    }

    // Progress ring
    const progressPercent = stats.challenges_total > 0
        ? Math.round((stats.challenges_completed / stats.challenges_total) * 100)
        : 0;

    document.getElementById('progress-percent').textContent = `${progressPercent}%`;
    document.getElementById('challenges-completed').textContent = stats.challenges_completed;
    document.getElementById('challenges-total').textContent = stats.challenges_total;

    // Animate progress ring
    const circle = document.getElementById('progress-circle');
    const circumference = 2 * Math.PI * 35; // radius = 35
    const offset = circumference - (progressPercent / 100) * circumference;
    circle.style.strokeDasharray = circumference;
    circle.style.strokeDashoffset = offset;

    // Points
    document.getElementById('total-points').textContent = stats.total_points.toLocaleString();

    // Points earned today - will be calculated from activity or provided by API
    const pointsToday = document.getElementById('points-today');
    const pointsTodayLabel = document.getElementById('points-today-label');

    if (stats.points_today !== undefined && stats.points_today > 0) {
        pointsToday.textContent = `+${stats.points_today}`;
        pointsTodayLabel.textContent = 'today';
    } else {
        // Placeholder - will be updated after activity loads
        pointsToday.textContent = '';
        pointsTodayLabel.textContent = '';
    }

    // Badges - count only, rarity breakdown is rendered separately
    document.getElementById('badges-earned').textContent = stats.badges_earned;

    // Activity Streak - calculated separately in renderActivityStreak()
}

/**
 * Render active challenges
 */
function renderActiveChallenges(challenges) {
    const container = document.getElementById('active-challenges');

    // Filter to show in-progress first, then available, limit to 4
    const active = challenges
        .filter(c => c.status !== 'completed')
        .sort((a, b) => {
            if (a.status === 'in_progress' && b.status !== 'in_progress') return -1;
            if (b.status === 'in_progress' && a.status !== 'in_progress') return 1;
            return 0;
        })
        .slice(0, 4);

    if (active.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8">
                <div class="text-4xl mb-3">🎉</div>
                <p class="text-text-secondary text-sm">All challenges completed!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = active.map(challenge => {
        const icon = CATEGORY_ICONS[challenge.category] || '🎯';
        const iconClass = getCategoryIconClass(challenge.category);

        return `
            <a href="/ctf/challenges/${challenge.id}" class="challenge-mini">
                <div class="challenge-icon ${iconClass}">
                    ${icon}
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1 flex-wrap">
                        <span class="font-semibold text-text-bright truncate">${escapeHtml(challenge.title)}</span>
                        <span class="diff-${challenge.difficulty}">${challenge.difficulty}</span>
                    </div>
                    <div class="text-sm text-text-secondary truncate">${formatCategoryName(challenge.category)}</div>
                </div>
                <div class="text-right flex-shrink-0">
                    <div class="text-lg font-bold text-ctf-primary font-mono">${challenge.points} pts</div>
                    ${challenge.attempts !== undefined ? `<div class="text-xs text-text-secondary">${challenge.attempts} attempts</div>` : ''}
                </div>
            </a>
        `;
    }).join('');
}

/**
 * Render recent badges
 */
function renderRecentBadges(badges) {
    const container = document.getElementById('recent-badges');
    const noBadges = document.getElementById('no-badges');

    // Filter earned badges and sort by earned_at
    const earnedBadges = badges
        .filter(b => b.earned)
        .sort((a, b) => new Date(b.earned_at) - new Date(a.earned_at))
        .slice(0, 3);

    if (earnedBadges.length === 0) {
        container.classList.add('hidden');
        noBadges.classList.remove('hidden');
        return;
    }

    noBadges.classList.add('hidden');
    container.classList.remove('hidden');

    container.innerHTML = earnedBadges.map((badge, index) => {
        const rarityClass = `badge-rarity-${badge.rarity}`;
        const isRecent = index === 0;

        return `
            <div class="badge-item ${rarityClass} ${isRecent ? 'earned' : ''}">
                <div class="badge-icon">${badge.icon_url || RARITY_ICONS[badge.rarity] || '🏆'}</div>
                <div class="flex-1 min-w-0">
                    <div class="font-semibold text-text-bright truncate">${escapeHtml(badge.title)}</div>
                    <div class="text-xs text-text-secondary truncate">${escapeHtml(badge.description)}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render activity feed
 */
function renderActivityFeed(activityResponse) {
    const container = document.getElementById('activity-feed');
    const noActivity = document.getElementById('no-activity');
    const items = activityResponse.items || [];

    if (items.length === 0) {
        container.classList.add('hidden');
        noActivity.classList.remove('hidden');
        return;
    }

    noActivity.classList.add('hidden');
    container.classList.remove('hidden');

    container.innerHTML = items.map(item => {
        const eventConfig = EVENT_ICONS[item.event_category] || EVENT_ICONS['tool'];
        const timeAgo = getTimeAgo(item.timestamp);

        return `
            <div class="activity-item">
                <div class="activity-icon ${eventConfig.class}">
                    ${eventConfig.icon}
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="font-medium text-text-bright">${formatEventType(item.event_type)}</span>
                        ${item.agent_name ? `<span class="activity-tag bg-purple-500/20 text-purple-300">${escapeHtml(item.agent_name)}</span>` : ''}
                        ${item.tool_name ? `<span class="activity-tag bg-cyan-500/20 text-cyan-300 font-mono text-xs">${escapeHtml(item.tool_name)}</span>` : ''}
                    </div>
                    <div class="text-sm text-text-secondary mt-1 truncate">${escapeHtml(item.summary)}</div>
                </div>
                <div class="text-xs text-text-secondary font-mono flex-shrink-0">${timeAgo}</div>
            </div>
        `;
    }).join('');
}

/**
 * Render category progress
 */
function renderCategoryProgress(categories) {
    const container = document.getElementById('category-progress');
    const noCategories = document.getElementById('no-categories');

    if (!categories || categories.length === 0) {
        container.classList.add('hidden');
        noCategories.classList.remove('hidden');
        return;
    }

    noCategories.classList.add('hidden');
    container.classList.remove('hidden');

    container.innerHTML = categories.map(cat => {
        const colorClass = CATEGORY_COLORS[cat.category] || 'cyan';

        return `
            <div class="category-progress">
                <div class="flex justify-between text-sm mb-2">
                    <span class="text-text-primary">${formatCategoryName(cat.category)}</span>
                    <span class="font-mono text-${colorClass === 'cyan' ? 'ctf-primary' : colorClass === 'purple' ? 'ctf-secondary' : colorClass === 'green' ? 'ctf-accent' : 'ctf-warning'}">${cat.completed}/${cat.total}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill ${colorClass}" style="width: ${cat.percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render badge rarity breakdown (e.g., "3 rare • 1 epic")
 */
function renderBadgeRarityBreakdown(badges) {
    const container = document.getElementById('badges-rarity-breakdown');

    // Count earned badges by rarity
    const earnedBadges = badges.filter(b => b.earned);
    const rarityCounts = {};

    earnedBadges.forEach(badge => {
        const rarity = badge.rarity || 'common';
        rarityCounts[rarity] = (rarityCounts[rarity] || 0) + 1;
    });

    if (earnedBadges.length === 0) {
        container.innerHTML = '<span class="text-text-secondary">none yet</span>';
        return;
    }

    // Define rarity order and colors
    const rarityConfig = {
        'legendary': { color: 'text-yellow-400', order: 1 },
        'epic': { color: 'text-purple-400', order: 2 },
        'rare': { color: 'text-blue-400', order: 3 },
        'common': { color: 'text-gray-400', order: 4 }
    };

    // Build breakdown string, sorted by rarity (most rare first)
    const parts = Object.entries(rarityCounts)
        .sort((a, b) => (rarityConfig[a[0]]?.order || 99) - (rarityConfig[b[0]]?.order || 99))
        .map(([rarity, count]) => {
            const config = rarityConfig[rarity] || { color: 'text-gray-400' };
            return `<span class="${config.color}">${count} ${rarity}</span>`;
        });

    container.innerHTML = parts.join(' <span class="text-text-secondary">•</span> ');
}

/**
 * Calculate and render points earned today
 */
function renderPointsToday(activityResponse, challenges) {
    const pointsToday = document.getElementById('points-today');
    const pointsTodayLabel = document.getElementById('points-today-label');
    const items = activityResponse.items || [];

    // Get today's date
    const today = new Date().toLocaleDateString();

    // Look for challenge completions and badge earnings today
    let earnedToday = 0;

    items.forEach(item => {
        const itemDate = new Date(item.timestamp).toLocaleDateString();
        if (itemDate === today) {
            // Check for challenge completion events
            if (item.event_type === 'challenge_completed' && item.challenge_id) {
                // Find the challenge to get its points
                const challenge = challenges.find(c => c.id === item.challenge_id);
                if (challenge) {
                    earnedToday += challenge.points;
                }
            }
            // Check for badge earned events
            if (item.event_type === 'badge_earned') {
                // Badges typically give bonus points - estimate or get from activity
                earnedToday += 50; // Default badge points
            }
        }
    });

    if (earnedToday > 0) {
        pointsToday.textContent = `+${earnedToday}`;
        pointsTodayLabel.textContent = 'today';
    } else {
        // Show encouraging message if active today but no points yet
        const wasActiveToday = items.some(item =>
            new Date(item.timestamp).toLocaleDateString() === today
        );

        if (wasActiveToday) {
            pointsToday.textContent = '';
            pointsTodayLabel.textContent = 'active today';
        }
    }
}

/**
 * Calculate and render activity streak (consecutive days of portal usage)
 */
function renderActivityStreak(activityResponse) {
    const streakEl = document.getElementById('current-streak');
    const streakStatus = document.getElementById('streak-status');
    const items = activityResponse.items || [];

    if (items.length === 0) {
        streakEl.textContent = '0';
        streakStatus.textContent = 'Start exploring!';
        return;
    }

    // Get unique dates from activity (in local timezone)
    const activityDates = new Set();
    items.forEach(item => {
        const date = new Date(item.timestamp);
        const dateKey = date.toLocaleDateString();
        activityDates.add(dateKey);
    });

    // Check if user was active today
    const today = new Date().toLocaleDateString();
    const wasActiveToday = activityDates.has(today);

    // Calculate streak - for now, if active today, show 1+ based on recent activity
    // Full streak calculation would require fetching more activity history
    let streak = 0;

    if (wasActiveToday) {
        streak = 1;

        // Check yesterday
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        if (activityDates.has(yesterday.toLocaleDateString())) {
            streak = 2;
        }

        // Check day before
        const dayBefore = new Date();
        dayBefore.setDate(dayBefore.getDate() - 2);
        if (streak === 2 && activityDates.has(dayBefore.toLocaleDateString())) {
            streak = 3;
        }
    } else {
        // Check if was active yesterday (streak not broken yet today)
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        if (activityDates.has(yesterday.toLocaleDateString())) {
            streak = 1;
        }
    }

    streakEl.textContent = streak;

    if (streak === 0) {
        streakStatus.textContent = 'Start exploring!';
    } else if (streak === 1) {
        streakStatus.textContent = wasActiveToday ? '🔥 Active today!' : '⏰ Log in to continue!';
    } else if (streak < 7) {
        streakStatus.textContent = '🔥 Keep it going!';
    } else {
        streakStatus.textContent = '🔥 On fire!';
    }
}

/**
 * Get category icon class
 */
function getCategoryIconClass(category) {
    const mapping = {
        'prompt_injection': 'injection',
        'prompt-injection': 'injection',
        'data_exfiltration': 'exfiltration',
        'data-exfiltration': 'exfiltration',
        'privilege_escalation': 'escalation',
        'privilege-escalation': 'escalation',
        'denial_of_service': 'dos',
        'denial-of-service': 'dos',
    };
    return mapping[category] || 'injection';
}

/**
 * Format category name for display
 */
function formatCategoryName(category) {
    return category
        .replace(/[-_]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Format event type for display
 */
function formatEventType(eventType) {
    return eventType
        .replace(/[-_]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Get human-readable time ago string
 */
function getTimeAgo(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
