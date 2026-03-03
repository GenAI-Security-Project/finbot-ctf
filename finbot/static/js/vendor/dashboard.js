/**
 * FinBot Vendor Portal - Dashboard with Vendor Context
 */

const DashboardState = {
    vendorContext: null,
    isLoading: false,
    isSwitchingVendor: false,
    sidebarOpen: false
};

document.addEventListener('DOMContentLoaded', function () {
    initializeDashboard();
});

async function initializeDashboard() {
    try {
        await loadVendorContext();
        initializeVendorSwitcher();
        initializeSidebar();
        await loadDashboardData();
    } catch (error) {
        console.error('Dashboard initialization failed:', error);
        showNotification('Failed to initialize dashboard', 'error');
    }
}

async function loadVendorContext() {
    try {
        showLoadingState();
        const response = await api.get('/vendor/api/v1/vendors/context');
        DashboardState.vendorContext = response.data;
        updateVendorSwitcherUI();
        hideLoadingState();
    } catch (error) {
        console.error('Error loading vendor context:', error);
        hideLoadingState();
        throw error;
    }
}

function initializeVendorSwitcher() {
    const switcherButton = document.getElementById('vendor-switcher');
    const dropdown = document.getElementById('vendor-dropdown');

    if (!switcherButton || !dropdown) return;

    switcherButton.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleVendorDropdown();
    });

    document.addEventListener('click', function (e) {
        if (!switcherButton.contains(e.target) && !dropdown.contains(e.target)) {
            closeVendorDropdown();
        }
    });

    dropdown.addEventListener('click', function (e) {
        const vendorOption = e.target.closest('.vendor-option');
        if (!vendorOption) return;

        if (vendorOption.dataset.action === 'add-vendor') {
            handleAddNewVendor();
            return;
        }

        if (!vendorOption.classList.contains('current') && vendorOption.dataset.vendorId) {
            const vendorId = parseInt(vendorOption.dataset.vendorId);
            switchVendor(vendorId);
        }
    });
}

async function switchVendor(vendorId) {
    if (DashboardState.isSwitchingVendor) return;

    const currentVendorId = DashboardState.vendorContext?.current_vendor?.id;
    if (vendorId === currentVendorId) return;

    try {
        DashboardState.isSwitchingVendor = true;
        showLoadingState();

        const response = await api.post(`/vendor/api/v1/vendors/switch/${vendorId}`);

        if (response.data.success) {
            DashboardState.vendorContext.current_vendor = response.data.current_vendor;
            showNotification(`Switched to ${response.data.current_vendor.company_name}`, 'success');
            closeVendorDropdown();
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (error) {
        console.error('Error switching vendor:', error);
        showNotification('Failed to switch vendor', 'error');
        DashboardState.isSwitchingVendor = false;
        hideLoadingState();
    }
}

function updateVendorSwitcherUI() {
    const switcherButton = document.getElementById('vendor-switcher');
    const dropdown = document.getElementById('vendor-dropdown');

    if (!switcherButton || !dropdown || !DashboardState.vendorContext) return;

    const { current_vendor, available_vendors } = DashboardState.vendorContext;

    if (current_vendor) {
        const avatar = current_vendor.company_name.substring(0, 2).toUpperCase();
        switcherButton.innerHTML = `
            <div class="flex items-center space-x-3">
                <div class="w-8 h-8 rounded-full bg-gradient-to-r from-vendor-accent to-vendor-primary flex items-center justify-center text-xs font-bold text-portal-bg-primary">
                    ${avatar}
                </div>
                <div class="text-left">
                    <div class="text-sm font-medium text-text-bright">${current_vendor.company_name}</div>
                    <div class="text-xs text-text-secondary">${current_vendor.industry}</div>
                </div>
            </div>
            <svg class="w-4 h-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
        `;
    }

    const vendorOptions = available_vendors.map(vendor => {
        const avatar = vendor.company_name.substring(0, 2).toUpperCase();
        const isCurrent = vendor.id === current_vendor?.id;

        return `
            <div class="vendor-option ${isCurrent ? 'current' : ''}" data-vendor-id="${vendor.id}">
                <div class="flex items-center space-x-3 p-3 rounded-lg ${isCurrent ? 'bg-vendor-primary/10 border border-vendor-primary/30' : 'hover:bg-portal-surface'} transition-colors cursor-pointer">
                    <div class="w-8 h-8 rounded-full bg-gradient-to-r from-vendor-accent to-vendor-primary flex items-center justify-center text-xs font-bold text-portal-bg-primary">
                        ${avatar}
                    </div>
                    <div class="flex-1">
                        <div class="text-sm font-medium text-text-bright">${vendor.company_name}</div>
                        <div class="text-xs ${isCurrent ? 'text-vendor-primary' : 'text-text-secondary'}">
                            ${isCurrent ? 'Current' : vendor.industry}
                        </div>
                    </div>
                    ${isCurrent ? `
                        <svg class="w-4 h-4 text-vendor-primary" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                        </svg>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');

    const addNewVendorOption = `
        <div class="vendor-option add-new-vendor" data-action="add-vendor">
            <div class="flex items-center space-x-3 p-3 rounded-lg hover:bg-portal-surface transition-colors cursor-pointer mt-2 border-t border-vendor-primary/20 pt-3">
                <div class="w-8 h-8 rounded-full bg-gradient-to-r from-vendor-secondary to-vendor-warning flex items-center justify-center text-xs font-bold text-text-bright">
                    +
                </div>
                <div class="flex-1">
                    <div class="text-sm font-medium text-text-secondary">Add New Vendor</div>
                    <div class="text-xs text-text-secondary">Register another company</div>
                </div>
            </div>
        </div>
    `;

    dropdown.innerHTML = `<div class="p-2">${vendorOptions}${addNewVendorOption}</div>`;
}

function handleAddNewVendor() {
    closeVendorDropdown();
    showNotification('Redirecting to vendor registration...', 'info');
    setTimeout(() => { window.location.href = '/vendor/onboarding'; }, 500);
}

function toggleVendorDropdown() {
    const dropdown = document.getElementById('vendor-dropdown');
    if (!dropdown) return;

    if (dropdown.classList.contains('hidden')) {
        dropdown.classList.remove('hidden');
        dropdown.style.opacity = '0';
        dropdown.style.transform = 'translateY(-10px)';
        requestAnimationFrame(() => {
            dropdown.style.transition = 'all 0.2s ease-out';
            dropdown.style.opacity = '1';
            dropdown.style.transform = 'translateY(0)';
        });
    } else {
        closeVendorDropdown();
    }
}

function closeVendorDropdown() {
    const dropdown = document.getElementById('vendor-dropdown');
    if (!dropdown) return;
    dropdown.style.opacity = '0';
    dropdown.style.transform = 'translateY(-10px)';
    setTimeout(() => { dropdown.classList.add('hidden'); }, 200);
}

async function loadDashboardData() {
    try {
        showLoadingState();

        const metricsResponse = await api.get('/vendor/api/v1/dashboard/metrics');
        renderDashboard(metricsResponse.data);

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showNotification('Failed to load dashboard data', 'error');
    } finally {
        hideLoadingState();
    }
}

function renderDashboard(data) {
    const { vendor_context, metrics, recent_invoices, recent_messages } = data;

    renderVendorStatusBanner(vendor_context);
    renderMetrics(metrics);
    renderRecentInvoices(recent_invoices || []);
    renderRecentMessages(recent_messages || []);
}

function renderVendorStatusBanner(vendor) {
    const banner = document.getElementById('vendor-status-banner');
    if (!banner || !vendor) return;

    const statusConfig = {
        active: {
            bg: 'bg-vendor-accent/5',
            border: 'border-vendor-accent/20',
            iconBg: 'bg-vendor-accent/20',
            iconColor: 'text-vendor-accent',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>',
            title: 'Active & Verified',
            description: 'Your vendor account is in good standing',
        },
        approved: {
            bg: 'bg-vendor-accent/5',
            border: 'border-vendor-accent/20',
            iconBg: 'bg-vendor-accent/20',
            iconColor: 'text-vendor-accent',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>',
            title: 'Approved',
            description: 'Your vendor account has been approved',
        },
        pending: {
            bg: 'bg-vendor-warning/5',
            border: 'border-vendor-warning/20',
            iconBg: 'bg-vendor-warning/20',
            iconColor: 'text-vendor-warning',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>',
            title: 'Pending Review',
            description: 'Your vendor account is being reviewed by our AI system',
        },
        rejected: {
            bg: 'bg-vendor-danger/5',
            border: 'border-vendor-danger/20',
            iconBg: 'bg-vendor-danger/20',
            iconColor: 'text-vendor-danger',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>',
            title: 'Requires Attention',
            description: 'Your vendor account was not approved. Update your profile and request a re-review.',
            action: { text: 'Request Review', href: '/vendor/profile' },
        },
        suspended: {
            bg: 'bg-vendor-danger/5',
            border: 'border-vendor-danger/20',
            iconBg: 'bg-vendor-danger/20',
            iconColor: 'text-vendor-danger',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>',
            title: 'Account Suspended',
            description: 'Your vendor account has been suspended. Contact support for assistance.',
        },
    };

    const status = (vendor.status || 'pending').toLowerCase();
    const config = statusConfig[status] || statusConfig.pending;

    const bannerInner = banner.querySelector('div');
    bannerInner.className = `rounded-xl border p-4 flex items-center justify-between ${config.bg} ${config.border}`;

    document.getElementById('status-icon').className = `w-10 h-10 rounded-full flex items-center justify-center ${config.iconBg}`;
    document.getElementById('status-icon').innerHTML = `<svg class="w-5 h-5 ${config.iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">${config.icon}</svg>`;
    document.getElementById('status-title').textContent = config.title;
    document.getElementById('status-description').textContent = config.description;

    const actionLink = document.getElementById('status-action-link');
    if (config.action) {
        actionLink.textContent = config.action.text;
        actionLink.href = config.action.href;
        actionLink.classList.remove('hidden');
    } else {
        actionLink.classList.add('hidden');
    }

    banner.classList.remove('hidden');
}

function renderMetrics(metrics) {
    if (!metrics) return;

    const inv = metrics.invoices || {};
    const pay = metrics.payments || {};
    const msg = metrics.messages || {};
    const files = metrics.files || {};

    setText('val-total-invoiced', formatCurrency(inv.total_amount || 0));
    setText('val-invoice-count', inv.total_count || 0);

    setText('val-paid-amount', formatCurrency(inv.paid_amount || 0));
    setText('val-paid-count', inv.paid_count || 0);

    setText('val-pending-amount', formatCurrency(inv.pending_amount || 0));
    setText('val-pending-count', inv.pending_count || 0);

    const rate = metrics.completion_rate || 0;
    setText('val-completion-rate', rate.toFixed(0) + '%');
    const bar = document.getElementById('completion-bar');
    if (bar) {
        setTimeout(() => { bar.style.width = Math.min(rate, 100) + '%'; }, 200);
    }

    setText('val-txn-count', pay.transaction_count || 0);
    setText('val-msg-count', msg.total || 0);
    setText('val-file-count', files.total_count || 0);
    setText('val-overdue-count', inv.overdue_count || 0);

    const unreadBadge = document.getElementById('unread-badge');
    if (unreadBadge && msg.unread > 0) {
        unreadBadge.textContent = msg.unread > 9 ? '9+' : msg.unread;
        unreadBadge.classList.remove('hidden');
    }
}

function renderRecentInvoices(invoices) {
    const container = document.getElementById('recent-invoices-list');
    if (!container) return;

    if (invoices.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8">
                <svg class="w-12 h-12 mx-auto text-text-secondary/40 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <p class="text-sm text-text-secondary mb-3">No invoices yet</p>
                <a href="/vendor/invoices" class="text-xs text-vendor-primary hover:text-vendor-accent transition-colors font-medium">
                    Create your first invoice &rarr;
                </a>
            </div>
        `;
        return;
    }

    container.innerHTML = invoices.map(inv => {
        const statusClass = inv.status || 'pending';
        const dueStr = inv.due_date ? formatDate(inv.due_date, { month: 'short', day: 'numeric' }) : '--';
        return `
            <a href="/vendor/invoices" class="invoice-row">
                <div class="flex items-center space-x-3 min-w-0">
                    <div class="flex-shrink-0">
                        <span class="text-sm font-mono font-medium text-vendor-primary">${escapeHtml(inv.invoice_number)}</span>
                    </div>
                    <div class="min-w-0 hidden sm:block">
                        <p class="text-xs text-text-secondary truncate max-w-[200px]">${escapeHtml(inv.description || '')}</p>
                    </div>
                </div>
                <div class="flex items-center space-x-4 flex-shrink-0">
                    <span class="text-xs text-text-secondary">${dueStr}</span>
                    <span class="status-dot ${statusClass}">${statusClass}</span>
                    <span class="text-sm font-semibold text-text-bright">${formatCurrency(inv.amount)}</span>
                </div>
            </a>
        `;
    }).join('');
}

function renderRecentMessages(messages) {
    const container = document.getElementById('recent-messages-list');
    if (!container) return;

    if (messages.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8">
                <svg class="w-12 h-12 mx-auto text-text-secondary/40 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                <p class="text-sm text-text-secondary">No messages yet</p>
            </div>
        `;
        return;
    }

    container.innerHTML = messages.map(msg => {
        const isUnread = !msg.is_read;
        const timeAgo = msg.created_at ? formatRelativeTime(msg.created_at) : '';
        const msgType = msg.message_type || 'notification';
        const iconMap = {
            notification: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>',
            alert: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
            system: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
        };
        const icon = iconMap[msgType] || iconMap.notification;

        return `
            <a href="/vendor/messages" class="msg-row block ${isUnread ? 'unread' : ''}">
                <div class="flex items-start space-x-3">
                    <div class="msg-type-icon ${msgType}">
                        ${icon}
                    </div>
                    <div class="min-w-0 flex-1">
                        <p class="text-sm ${isUnread ? 'text-text-bright font-medium' : 'text-text-secondary'} truncate">${escapeHtml(msg.subject || 'Message')}</p>
                        <p class="text-xs text-text-secondary truncate mt-0.5">${escapeHtml((msg.body || '').substring(0, 80))}</p>
                        <p class="text-[10px] text-text-secondary/60 mt-1">${timeAgo}</p>
                    </div>
                    ${isUnread ? '<div class="w-2 h-2 rounded-full bg-vendor-primary flex-shrink-0 mt-1.5"></div>' : ''}
                </div>
            </a>
        `;
    }).join('');
}

// Helpers
function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function initializeSidebar() {
    if (typeof sidebar !== 'undefined' && sidebar.init) {
        sidebar.init();
    }
}

function showLoadingState() {
    DashboardState.isLoading = true;
    const loadingIndicator = document.querySelector('.loading-indicator');
    if (loadingIndicator) loadingIndicator.classList.remove('hidden');
}

function hideLoadingState() {
    DashboardState.isLoading = false;
    const loadingIndicator = document.querySelector('.loading-indicator');
    if (loadingIndicator) loadingIndicator.classList.add('hidden');
}

window.VendorDashboard = {
    switchVendor,
    handleAddNewVendor,
    loadDashboardData,
    state: DashboardState
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.VendorDashboard;
}
