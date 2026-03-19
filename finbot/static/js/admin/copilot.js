/**
 * FinBot Finance Co-Pilot - Chat interface with SSE streaming, workflow chips, and report artifacts
 */

const STORAGE_KEY = 'finbot_copilot_history';
const MAX_DISPLAY_MESSAGES = 200;

let chatMessages = [];
let isStreaming = false;

document.addEventListener('DOMContentLoaded', () => {
    initCoPilot();
});

async function initCoPilot() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const clearBtn = document.getElementById('clear-chat-btn');

    if (!input || !sendBtn) return;

    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        sendBtn.disabled = !input.value.trim() || isStreaming;
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            const dropdown = document.getElementById('autocomplete-dropdown');
            const hasAutocomplete = dropdown && !dropdown.classList.contains('hidden');
            if (hasAutocomplete) return;
            e.preventDefault();
            if (input.value.trim() && !isStreaming) sendMessage(input.value.trim());
        }
    });

    sendBtn.addEventListener('click', () => {
        if (input.value.trim() && !isStreaming) sendMessage(input.value.trim());
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', clearHistory);
    }

    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if (!isStreaming) sendMessage(chip.dataset.message);
        });
    });

    initCollapsibleCategories();
    initWorkflowSearch();
    initWorkflowsToggle();
    initAutocomplete(input);
    await Promise.all([syncHistory(), loadRecentReports()]);
}

// -- Collapsible categories --

function initCollapsibleCategories() {
    document.querySelectorAll('.workflow-category-header').forEach(header => {
        header.addEventListener('click', () => {
            const category = header.closest('.workflow-category');
            const chips = category.querySelector('.workflow-chips');
            const chevron = header.querySelector('.chevron');
            const isExpanded = header.dataset.expanded === 'true';

            if (isExpanded) {
                chips.classList.add('hidden');
                chevron.classList.add('-rotate-90');
                header.dataset.expanded = 'false';
            } else {
                chips.classList.remove('hidden');
                chevron.classList.remove('-rotate-90');
                header.dataset.expanded = 'true';
            }
        });
    });
}

// -- Workflow search --

function initWorkflowSearch() {
    const searchInput = document.getElementById('workflow-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.trim().toLowerCase();
        const categories = document.querySelectorAll('.workflow-category');

        if (!query) {
            categories.forEach(cat => {
                cat.style.display = '';
                const chips = cat.querySelector('.workflow-chips');
                chips.querySelectorAll('.suggestion-chip').forEach(c => c.style.display = '');
                const header = cat.querySelector('.workflow-category-header');
                if (header.dataset.expanded === 'false') {
                    chips.classList.add('hidden');
                }
            });
            return;
        }

        categories.forEach(cat => {
            const chips = cat.querySelector('.workflow-chips');
            const allChips = chips.querySelectorAll('.suggestion-chip');
            let hasMatch = false;

            allChips.forEach(chip => {
                const text = (chip.dataset.message || chip.textContent).toLowerCase();
                if (text.includes(query)) {
                    chip.style.display = '';
                    hasMatch = true;
                } else {
                    chip.style.display = 'none';
                }
            });

            if (hasMatch) {
                cat.style.display = '';
                chips.classList.remove('hidden');
            } else {
                cat.style.display = 'none';
            }
        });
    });
}

// -- Workflows toggle (show chips during active chat) --

function initWorkflowsToggle() {
    const toggleBtn = document.getElementById('workflows-toggle');
    if (!toggleBtn) return;

    toggleBtn.addEventListener('click', () => {
        const welcome = document.getElementById('chat-welcome');
        if (!welcome) return;

        const isVisible = welcome.style.display !== 'none';
        if (isVisible && chatMessages.length > 0) {
            welcome.style.display = 'none';
            toggleBtn.classList.remove('active');
        } else {
            welcome.style.display = '';
            toggleBtn.classList.add('active');
            const container = document.getElementById('chat-messages');
            container.scrollTop = 0;
        }
    });
}

// -- Autocomplete (chip suggestions in chat input) --

function initAutocomplete(input) {
    const dropdown = document.getElementById('autocomplete-dropdown');
    if (!input || !dropdown) return;

    const allWorkflows = [];
    document.querySelectorAll('.workflow-category').forEach(cat => {
        const headerEl = cat.querySelector('.workflow-category-header .text-sm');
        const category = headerEl ? headerEl.textContent.trim() : '';
        cat.querySelectorAll('.suggestion-chip').forEach(chip => {
            allWorkflows.push({
                message: chip.dataset.message,
                category,
            });
        });
    });

    let selectedIndex = -1;

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        if (query.length < 2) {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
            return;
        }

        const matches = allWorkflows.filter(w =>
            w.message.toLowerCase().includes(query)
        ).slice(0, 8);

        if (matches.length === 0) {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
            return;
        }

        selectedIndex = -1;
        dropdown.innerHTML = matches.map((m, i) => `
            <div class="autocomplete-item" data-index="${i}" data-message="${escapeHtml(m.message)}">
                <span class="ac-icon">⚡</span>
                <span class="flex-1">${highlightMatch(escapeHtml(m.message), query)}</span>
                <span class="ac-category">${escapeHtml(m.category)}</span>
            </div>
        `).join('');
        dropdown.classList.remove('hidden');

        dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                sendMessage(item.dataset.message);
                dropdown.classList.add('hidden');
                input.value = '';
            });
        });
    });

    input.addEventListener('keydown', (e) => {
        if (dropdown.classList.contains('hidden')) return;
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            updateAutocompleteSelection(items, selectedIndex);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, 0);
            updateAutocompleteSelection(items, selectedIndex);
        } else if (e.key === 'Tab' || (e.key === 'Enter' && selectedIndex >= 0)) {
            e.preventDefault();
            const selected = items[selectedIndex];
            if (selected) {
                sendMessage(selected.dataset.message);
                dropdown.classList.add('hidden');
                input.value = '';
            }
        } else if (e.key === 'Escape') {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }
    });

    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && e.target !== input) {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }
    });
}

function updateAutocompleteSelection(items, index) {
    items.forEach((item, i) => {
        item.classList.toggle('selected', i === index);
    });
    if (items[index]) {
        items[index].scrollIntoView({ block: 'nearest' });
    }
}

function highlightMatch(text, query) {
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return text;
    return text.slice(0, idx) +
        '<span class="text-admin-primary font-semibold">' + text.slice(idx, idx + query.length) + '</span>' +
        text.slice(idx + query.length);
}

// -- Recent reports --

async function loadRecentReports() {
    const container = document.getElementById('reports-list');
    if (!container) return;

    try {
        const res = await fetch('/admin/api/v1/findrive?file_type=report', { credentials: 'same-origin' });
        if (!res.ok) return;

        const data = await res.json();
        const reports = (data.files || []).slice(0, 10);

        if (reports.length === 0) return;

        container.innerHTML = reports.map(r => {
            const typeName = (r.filename || '').split('_')[0].replace(/-/g, ' ');
            const date = r.created_at ? new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
            return `
                <a href="/admin/findrive?from=copilot#file-${r.id}" class="report-card">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="report-type-badge">${escapeHtml(typeName)}</span>
                        <span class="text-xs text-text-secondary">${escapeHtml(date)}</span>
                    </div>
                    <div class="text-sm text-text-bright truncate">${escapeHtml(r.filename || 'Report')}</div>
                </a>
            `;
        }).join('');
    } catch (_) { /* best effort */ }
}

// -- Chat history sync --

async function syncHistory() {
    try {
        const res = await fetch('/admin/api/v1/copilot/history?limit=100', {
            credentials: 'same-origin',
        });
        if (!res.ok) return;

        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
            chatMessages = data.messages;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(chatMessages));
            renderAllMessages();
        } else {
            const cached = localStorage.getItem(STORAGE_KEY);
            if (cached) {
                try {
                    chatMessages = JSON.parse(cached);
                    if (chatMessages.length > 0) renderAllMessages();
                } catch (_) { /* ignore */ }
            }
        }
    } catch (_) {
        const cached = localStorage.getItem(STORAGE_KEY);
        if (cached) {
            try {
                chatMessages = JSON.parse(cached);
                if (chatMessages.length > 0) renderAllMessages();
            } catch (_) { /* ignore */ }
        }
    }
}

function renderAllMessages() {
    const container = document.getElementById('chat-messages');
    const welcome = document.getElementById('chat-welcome');
    if (welcome) welcome.style.display = 'none';

    const existing = container.querySelectorAll('.msg-bubble');
    existing.forEach(el => el.remove());

    const toShow = chatMessages.slice(-MAX_DISPLAY_MESSAGES);
    toShow.forEach(msg => {
        container.appendChild(createMessageEl(msg.role, msg.content));
    });

    scrollToBottom();
}

function createMessageEl(role, content) {
    const bubble = document.createElement('div');
    bubble.className = `msg-bubble ${role}`;

    if (role === 'system') {
        bubble.innerHTML = `<div class="msg-content">${escapeHtml(content)}</div>`;
    } else if (role === 'user') {
        bubble.innerHTML = `
            <div class="msg-avatar user">You</div>
            <div class="msg-content">${escapeHtml(content)}</div>
        `;
    } else {
        const rendered = renderReportLinks(escapeHtml(content));
        bubble.innerHTML = `
            <div class="msg-avatar assistant"><img src="/static/images/common/finbot.png" alt="FinBot" class="w-full h-full rounded-full object-contain"></div>
            <div class="msg-content">${rendered}</div>
        `;
    }

    return bubble;
}

function renderReportLinks(text) {
    return text.replace(
        /\/admin\/findrive#file-(\d+)/g,
        '<a href="/admin/findrive?from=copilot#file-$1" class="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 transition-colors text-xs font-medium no-underline">📄 View Report</a>'
    );
}

// -- Send message --

async function sendMessage(text) {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const container = document.getElementById('chat-messages');
    const welcome = document.getElementById('chat-welcome');

    if (welcome) welcome.style.display = 'none';

    const dropdown = document.getElementById('autocomplete-dropdown');
    if (dropdown) dropdown.classList.add('hidden');

    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;
    isStreaming = true;

    chatMessages.push({ role: 'user', content: text });
    container.appendChild(createMessageEl('user', text));
    scrollToBottom();

    const assistantBubble = document.createElement('div');
    assistantBubble.className = 'msg-bubble assistant';
    assistantBubble.innerHTML = `
        <div class="msg-avatar assistant"><img src="/static/images/common/finbot.png" alt="FinBot" class="w-full h-full rounded-full object-contain"></div>
        <div class="msg-content"><span class="thinking-indicator"><span class="thinking-text">Thinking</span><span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span></span></div>
    `;
    container.appendChild(assistantBubble);
    const contentEl = assistantBubble.querySelector('.msg-content');
    const thinkingEl = assistantBubble.querySelector('.thinking-indicator');
    scrollToBottom();

    let fullResponse = '';

    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const headers = { 'Content-Type': 'application/json' };
        if (csrfMeta) headers['X-CSRF-Token'] = csrfMeta.content;

        const controller = new AbortController();
        const streamTimeout = setTimeout(() => controller.abort(), 5 * 60 * 1000);

        const res = await fetch('/admin/api/v1/copilot/chat', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify({ message: text }),
            signal: controller.signal,
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;

                try {
                    const event = JSON.parse(jsonStr);
                    if (event.type === 'token') {
                        if (thinkingEl && thinkingEl.parentNode) {
                            thinkingEl.remove();
                            contentEl.classList.add('streaming-cursor');
                        }
                        fullResponse += event.content;
                        contentEl.innerHTML = renderReportLinks(escapeHtml(fullResponse));
                        scrollToBottom();
                    } else if (event.type === 'status') {
                        if (thinkingEl && thinkingEl.parentNode) {
                            thinkingEl.querySelector('.thinking-text').textContent = event.content.replace(/\u2026$/, '');
                        }
                        scrollToBottom();
                    } else if (event.type === 'done') {
                        break;
                    }
                } catch (_) { /* skip */ }
            }
        }

        clearTimeout(streamTimeout);
    } catch (err) {
        const msg = err.name === 'AbortError'
            ? 'The request timed out. Please try again.'
            : 'Sorry, something went wrong. Please try again.';
        fullResponse = fullResponse || msg;
        contentEl.innerHTML = renderReportLinks(escapeHtml(msg));
    }

    contentEl.classList.remove('streaming-cursor');

    if (fullResponse) {
        chatMessages.push({ role: 'assistant', content: fullResponse });
    }

    saveToLocalStorage();
    isStreaming = false;
    sendBtn.disabled = !input.value.trim();

    if (fullResponse.includes('/admin/findrive#file-')) {
        loadRecentReports();
    }
}

async function clearHistory() {
    if (!confirm('Clear all chat history? This action cannot be undone.')) return;

    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const headers = {};
        if (csrfMeta) headers['X-CSRF-Token'] = csrfMeta.content;

        await fetch('/admin/api/v1/copilot/history', {
            method: 'DELETE',
            headers,
            credentials: 'same-origin',
        });
    } catch (_) { /* best effort */ }

    chatMessages = [];
    localStorage.removeItem(STORAGE_KEY);

    const container = document.getElementById('chat-messages');
    container.querySelectorAll('.msg-bubble').forEach(el => el.remove());

    const welcome = document.getElementById('chat-welcome');
    if (welcome) welcome.style.display = '';
}

function saveToLocalStorage() {
    const toStore = chatMessages.slice(-MAX_DISPLAY_MESSAGES);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
