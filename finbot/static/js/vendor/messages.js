/**
 * FinBot Vendor Portal - Inbox / Messages
 */

const InboxState = {
    messages: [],
    stats: {},
    selectedId: null,
    activeFilter: 'all',
    isLoading: false,
};

const TYPE_LABELS = {
    status_update: 'Status',
    payment_update: 'Payment',
    payment_confirmation: 'Confirmed',
    compliance_alert: 'Compliance',
    action_required: 'Action',
    general: 'General',
    reminder: 'Reminder',
};

const TYPE_ICONS = {
    status_update: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>',
    payment_update: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1"/>',
    payment_confirmation: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>',
    compliance_alert: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>',
    action_required: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>',
    general: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>',
    reminder: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>',
};

ready(function () {
    initializeInbox();
});

async function initializeInbox() {
    bindToolbarEvents();
    await loadMessages();
}

function bindToolbarEvents() {
    document.querySelectorAll('.inbox-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.inbox-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            InboxState.activeFilter = btn.dataset.filter;
            renderMessageList();
        });
    });

    const refreshBtn = document.getElementById('refresh-inbox-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => loadMessages());

    const markAllBtn = document.getElementById('mark-all-read-btn');
    if (markAllBtn) markAllBtn.addEventListener('click', markAllRead);

    const backBtn = document.getElementById('detail-back-btn');
    if (backBtn) backBtn.addEventListener('click', clearSelection);
}

async function loadMessages() {
    InboxState.isLoading = true;
    showLoading(true);

    try {
        const resp = await api.get('/vendor/api/v1/messages');
        const data = resp.data || resp;
        InboxState.messages = data.messages || [];
        InboxState.stats = data.stats || {};
        updateStats();
        renderMessageList();
    } catch (err) {
        console.error('Failed to load messages:', err);
        showNotification('Failed to load messages', 'error');
    } finally {
        InboxState.isLoading = false;
        showLoading(false);
    }
}

function updateStats() {
    const s = InboxState.stats;
    setText('stat-total', s.total ?? 0);
    setText('stat-unread', s.unread ?? 0);

    const byType = s.by_type || {};
    const paymentCount = (byType.payment_update || 0) + (byType.payment_confirmation || 0);
    const alertCount = (byType.compliance_alert || 0) + (byType.action_required || 0);
    setText('stat-payment', paymentCount);
    setText('stat-alerts', alertCount);
}

function getFilteredMessages() {
    const filter = InboxState.activeFilter;
    if (filter === 'all') return InboxState.messages;
    if (filter === 'unread') return InboxState.messages.filter(m => !m.is_read);
    return InboxState.messages.filter(m => m.message_type === filter);
}

function renderMessageList() {
    const list = document.getElementById('inbox-list');
    const emptyEl = document.getElementById('inbox-empty');
    const filtered = getFilteredMessages();

    // Remove old message rows
    list.querySelectorAll('.msg-row').forEach(el => el.remove());

    const showingEl = document.getElementById('inbox-showing');
    if (showingEl) {
        showingEl.textContent = `${filtered.length} message${filtered.length !== 1 ? 's' : ''}`;
    }

    if (filtered.length === 0) {
        emptyEl?.classList.remove('hidden');
        return;
    }
    emptyEl?.classList.add('hidden');

    const fragment = document.createDocumentFragment();
    filtered.forEach(msg => {
        fragment.appendChild(createMessageRow(msg));
    });
    list.appendChild(fragment);
}

function createMessageRow(msg) {
    const row = document.createElement('div');
    row.className = 'msg-row';
    if (!msg.is_read) row.classList.add('unread');
    if (msg.id === InboxState.selectedId) row.classList.add('selected');
    row.dataset.id = msg.id;

    const typeLabel = TYPE_LABELS[msg.message_type] || msg.message_type;
    const iconSvg = TYPE_ICONS[msg.message_type] || TYPE_ICONS.general;
    const preview = (msg.body || '').substring(0, 80).replace(/\n/g, ' ');
    const timeStr = formatMessageTime(msg.created_at);

    row.innerHTML = `
        <div class="msg-icon ${msg.message_type}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">${iconSvg}</svg>
        </div>
        <div class="msg-content">
            <div class="msg-subject">${escapeHtml(msg.subject)}</div>
            <div class="msg-preview">${escapeHtml(preview)}</div>
        </div>
        <div class="msg-meta">
            <span class="msg-time">${timeStr}</span>
            <span class="msg-type-dot ${msg.message_type}">${typeLabel}</span>
        </div>
    `;

    row.addEventListener('click', () => selectMessage(msg));
    return row;
}

async function selectMessage(msg) {
    InboxState.selectedId = msg.id;

    // Highlight in list
    document.querySelectorAll('.msg-row').forEach(r => r.classList.remove('selected'));
    const row = document.querySelector(`.msg-row[data-id="${msg.id}"]`);
    if (row) row.classList.add('selected');

    // Mobile: show reading pane
    document.querySelector('.inbox-panes')?.classList.add('detail-open');

    // Populate reading pane
    document.getElementById('reading-pane-empty')?.classList.add('hidden');
    const content = document.getElementById('reading-pane-content');
    content?.classList.remove('hidden');

    setText('detail-subject', msg.subject);
    setText('detail-sender', msg.sender_name || 'CineFlow Productions - FinBot');
    setText('detail-date', formatMessageDate(msg.created_at));

    const typeBadge = document.getElementById('detail-type-badge');
    if (typeBadge) {
        typeBadge.className = `notification-badge ${msg.message_type}`;
        typeBadge.textContent = TYPE_LABELS[msg.message_type] || msg.message_type;
    }

    const channelEl = document.getElementById('detail-channel');
    if (channelEl) {
        channelEl.textContent = `via ${msg.channel || 'email'}`;
    }

    const bodyEl = document.getElementById('detail-body');
    if (bodyEl) bodyEl.textContent = msg.body || '';

    // Invoice link
    const invoiceLink = document.getElementById('detail-invoice-link');
    if (invoiceLink) {
        if (msg.related_invoice_id) {
            invoiceLink.classList.remove('hidden');
            const anchor = invoiceLink.querySelector('a');
            if (anchor) anchor.href = `/vendor/invoices#invoice-${msg.related_invoice_id}`;
        } else {
            invoiceLink.classList.add('hidden');
        }
    }

    // Mark as read if unread
    if (!msg.is_read) {
        await markAsRead(msg);
    }
}

async function markAsRead(msg) {
    try {
        await api.post(`/vendor/api/v1/messages/${msg.id}/read`);
        msg.is_read = true;
        msg.read_at = new Date().toISOString();

        // Update list row
        const row = document.querySelector(`.msg-row[data-id="${msg.id}"]`);
        if (row) row.classList.remove('unread');

        // Update stats locally
        if (InboxState.stats.unread > 0) {
            InboxState.stats.unread--;
            updateStats();
        }
    } catch (err) {
        console.error('Failed to mark as read:', err);
    }
}

async function markAllRead() {
    try {
        const resp = await api.post('/vendor/api/v1/messages/read-all');
        const data = resp.data || resp;
        const count = data.messages_updated || 0;

        InboxState.messages.forEach(m => {
            m.is_read = true;
            m.read_at = new Date().toISOString();
        });
        InboxState.stats.unread = 0;
        updateStats();
        renderMessageList();

        if (InboxState.selectedId) {
            const msg = InboxState.messages.find(m => m.id === InboxState.selectedId);
            if (msg) selectMessage(msg);
        }

        if (count > 0) {
            showNotification(`${count} message${count !== 1 ? 's' : ''} marked as read`, 'success');
        }
    } catch (err) {
        console.error('Failed to mark all as read:', err);
        showNotification('Failed to mark all as read', 'error');
    }
}

function clearSelection() {
    InboxState.selectedId = null;
    document.querySelectorAll('.msg-row').forEach(r => r.classList.remove('selected'));
    document.querySelector('.inbox-panes')?.classList.remove('detail-open');
    document.getElementById('reading-pane-empty')?.classList.remove('hidden');
    document.getElementById('reading-pane-content')?.classList.add('hidden');
}

// ===== Helpers =====

function showLoading(show) {
    const el = document.getElementById('inbox-loading');
    if (el) el.classList.toggle('hidden', !show);
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatMessageTime(isoStr) {
    if (!isoStr) return '';
    const date = new Date(isoStr);
    const now = new Date();
    const diff = now - date;
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m`;
    if (hours < 24) return `${hours}h`;
    if (days < 7) return `${days}d`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatMessageDate(isoStr) {
    if (!isoStr) return '';
    const date = new Date(isoStr);
    return date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    });
}
