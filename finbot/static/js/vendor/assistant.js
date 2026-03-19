/**
 * FinBot AI Assistant - Chat interface with SSE streaming
 */

const MAX_DISPLAY_MESSAGES = 200;

function getStorageKey() {
    return `finbot_chat_${window.CTF_VENDOR_ID || 'default'}`;
}

let chatMessages = [];
let isStreaming = false;
let chatAttachments = [];
let chatPickerSelectedIds = new Set();
let chatDriveFiles = [];

document.addEventListener('DOMContentLoaded', () => {
    initAssistant();
});

async function initAssistant() {
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

    document.getElementById('chat-attach-btn')?.addEventListener('click', openChatPicker);
    document.getElementById('chat-picker-close')?.addEventListener('click', closeChatPicker);
    document.getElementById('chat-picker-done')?.addEventListener('click', confirmChatPicker);
    document.getElementById('chat-picker-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'chat-picker-modal') closeChatPicker();
    });

    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if (!isStreaming) sendMessage(chip.dataset.message);
        });
    });

    await syncHistory();

    const urlParams = new URLSearchParams(window.location.search);
    const prefillPrompt = urlParams.get('prompt');
    if (prefillPrompt && prefillPrompt.trim()) {
        window.history.replaceState({}, '', window.location.pathname);
        input.value = prefillPrompt.trim();
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        sendBtn.disabled = false;
        sendMessage(prefillPrompt.trim());
    }
}

async function syncHistory() {
    try {
        const res = await fetch('/vendor/api/v1/chat/history?limit=100', {
            credentials: 'same-origin',
        });
        if (!res.ok) return;

        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
            chatMessages = data.messages;
            localStorage.setItem(getStorageKey(), JSON.stringify(chatMessages));
            renderAllMessages();
        } else {
            const cached = localStorage.getItem(getStorageKey());
            if (cached) {
                try {
                    chatMessages = JSON.parse(cached);
                    if (chatMessages.length > 0) renderAllMessages();
                } catch (_) { /* ignore parse errors */ }
            }
        }
    } catch (_) {
        const cached = localStorage.getItem(getStorageKey());
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

function createMessageEl(role, content, attachments) {
    const bubble = document.createElement('div');
    bubble.className = `msg-bubble ${role}`;

    let displayContent = content;
    let resolvedAttachments = attachments || [];

    if (role === 'user' && !resolvedAttachments.length) {
        const parsed = parseAttachmentPrefix(content);
        if (parsed) {
            resolvedAttachments = parsed.attachments;
            displayContent = parsed.text;
        }
    }

    let attachHtml = '';
    if (resolvedAttachments.length > 0) {
        attachHtml = `<div class="msg-attachments">${resolvedAttachments.map(a => {
            const ft = a.file_type || guessFileType(a.filename);
            const color = ft === 'doc' ? '#60a5fa' : '#f87171';
            const label = ft.toUpperCase();
            return `<span class="msg-attach-tag"><span style="color:${color};font-weight:700;font-size:9px">${label}</span> ${escapeHtml(a.filename)}</span>`;
        }).join('')}</div>`;
    }

    if (role === 'system') {
        bubble.innerHTML = `<div class="msg-content">${escapeHtml(displayContent)}</div>`;
    } else if (role === 'user') {
        bubble.innerHTML = `
            <div class="msg-avatar user">You</div>
            <div class="msg-content">${attachHtml}${escapeHtml(displayContent)}</div>
        `;
    } else {
        bubble.innerHTML = `
            <div class="msg-avatar assistant"><img src="/static/images/common/finbot.png" alt="FinBot" class="w-full h-full rounded-full object-contain"></div>
            <div class="msg-content">${escapeHtml(displayContent)}</div>
        `;
    }

    return bubble;
}

function parseAttachmentPrefix(content) {
    const match = content.match(/^\[User attached FinDrive files: (.+?)\]\n\n([\s\S]*)$/);
    if (!match) return null;

    const fileRefs = match[1];
    const text = match[2];
    const attachments = fileRefs.split(', ').map(ref => {
        const m = ref.match(/^(.+?) \(file_id: (\d+)\)$/);
        if (!m) return { filename: ref, file_id: 0, file_type: guessFileType(ref) };
        return { filename: m[1], file_id: parseInt(m[2]), file_type: guessFileType(m[1]) };
    });

    return { attachments, text };
}

function guessFileType(filename) {
    if (!filename) return 'pdf';
    if (filename.endsWith('.doc') || filename.endsWith('.docx')) return 'doc';
    return 'pdf';
}

async function sendMessage(text) {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const container = document.getElementById('chat-messages');
    const welcome = document.getElementById('chat-welcome');

    if (welcome) welcome.style.display = 'none';

    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;
    isStreaming = true;

    const msgAttachments = [...chatAttachments];
    chatMessages.push({ role: 'user', content: text });
    container.appendChild(createMessageEl('user', text, msgAttachments));
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

        const payload = { message: text };
        if (chatAttachments.length > 0) {
            payload.attachments = chatAttachments.map(a => ({
                file_id: a.file_id, filename: a.filename, file_type: a.file_type,
            }));
        }

        chatAttachments = [];
        renderChatChips();

        const controller = new AbortController();
        const streamTimeout = setTimeout(() => controller.abort(), 5 * 60 * 1000);

        const res = await fetch('/vendor/api/v1/chat', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify(payload),
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
                        contentEl.textContent = fullResponse;
                        scrollToBottom();
                    } else if (event.type === 'status') {
                        if (thinkingEl && thinkingEl.parentNode) {
                            thinkingEl.querySelector('.thinking-text').textContent = event.content.replace(/\u2026$/, '');
                        }
                        scrollToBottom();
                    } else if (event.type === 'done') {
                        break;
                    }
                } catch (_) { /* skip malformed events */ }
            }
        }

        clearTimeout(streamTimeout);
    } catch (err) {
        const msg = err.name === 'AbortError'
            ? 'The request timed out. Please try again.'
            : 'Sorry, something went wrong. Please try again.';
        fullResponse = fullResponse || msg;
        contentEl.textContent = fullResponse;
    }

    contentEl.classList.remove('streaming-cursor');

    if (fullResponse) {
        chatMessages.push({ role: 'assistant', content: fullResponse });
    }

    saveToLocalStorage();
    isStreaming = false;
    sendBtn.disabled = !input.value.trim();
}

async function clearHistory() {
    const confirmed = await showConfirmModal({
        title: 'Clear Chat History',
        message: 'All chat messages will be permanently deleted. This action cannot be undone.',
        confirmText: 'Clear History',
        danger: true,
    });
    if (!confirmed) return;

    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const headers = {};
        if (csrfMeta) headers['X-CSRF-Token'] = csrfMeta.content;

        await fetch('/vendor/api/v1/chat/history', {
            method: 'DELETE',
            headers,
            credentials: 'same-origin',
        });
    } catch (_) { /* best effort */ }

    chatMessages = [];
    localStorage.removeItem(getStorageKey());

    const container = document.getElementById('chat-messages');
    container.querySelectorAll('.msg-bubble').forEach(el => el.remove());

    const welcome = document.getElementById('chat-welcome');
    if (welcome) welcome.style.display = '';
}

function saveToLocalStorage() {
    const toStore = chatMessages.slice(-MAX_DISPLAY_MESSAGES);
    localStorage.setItem(getStorageKey(), JSON.stringify(toStore));
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

// =====================================================================
// FinDrive Attachment Picker
// =====================================================================

async function openChatPicker() {
    const modal = document.getElementById('chat-picker-modal');
    const grid = document.getElementById('chat-picker-grid');
    modal.classList.remove('hidden');

    chatPickerSelectedIds = new Set(chatAttachments.map(a => a.file_id));

    try {
        const res = await fetch('/vendor/api/v1/findrive', { credentials: 'same-origin' });
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        chatDriveFiles = data.files || [];

        if (chatDriveFiles.length === 0) {
            grid.innerHTML = '<p class="col-span-full text-center text-text-secondary py-8">No files in FinDrive.</p>';
            return;
        }

        grid.innerHTML = chatDriveFiles.map(f => {
            const sel = chatPickerSelectedIds.has(f.id);
            const ft = f.file_type || 'pdf';
            return `<div class="cpicker-card ${sel ? 'selected' : ''}" data-fid="${f.id}" data-fname="${escapeHtml(f.filename)}" data-ftype="${ft}">
                <div style="filter:drop-shadow(0 2px 4px rgba(0,0,0,0.2))">${_chatPickerIcon(ft)}</div>
                <div class="cpicker-card-name">${escapeHtml(f.filename)}</div>
            </div>`;
        }).join('');

        grid.querySelectorAll('.cpicker-card').forEach(card => {
            card.addEventListener('click', () => {
                const fid = parseInt(card.dataset.fid);
                if (chatPickerSelectedIds.has(fid)) {
                    chatPickerSelectedIds.delete(fid);
                    card.classList.remove('selected');
                } else {
                    chatPickerSelectedIds.add(fid);
                    card.classList.add('selected');
                }
            });
        });
    } catch (err) {
        console.error('Error loading FinDrive:', err);
        grid.innerHTML = '<p class="col-span-full text-center text-red-400 py-8">Failed to load files.</p>';
    }
}

function closeChatPicker() {
    document.getElementById('chat-picker-modal').classList.add('hidden');
}

function confirmChatPicker() {
    chatAttachments = chatDriveFiles
        .filter(f => chatPickerSelectedIds.has(f.id))
        .map(f => ({ file_id: f.id, filename: f.filename, file_type: f.file_type || 'pdf' }));
    renderChatChips();
    closeChatPicker();

    const sendBtn = document.getElementById('chat-send');
    const input = document.getElementById('chat-input');
    if (sendBtn) sendBtn.disabled = !(input?.value?.trim() || chatAttachments.length > 0) || isStreaming;
}

function renderChatChips() {
    const container = document.getElementById('chat-attach-chips');
    if (!container) return;

    if (chatAttachments.length === 0) {
        container.classList.add('hidden');
        container.innerHTML = '';
        return;
    }

    container.classList.remove('hidden');
    container.innerHTML = chatAttachments.map(a => `
        <span class="chat-chip">
            <span style="color:${a.file_type === 'doc' ? '#60a5fa' : '#f87171'};font-weight:700;font-size:9px">${(a.file_type || 'pdf').toUpperCase()}</span>
            ${escapeHtml(a.filename)}
            <button type="button" class="chat-chip-x" data-fid="${a.file_id}">&times;</button>
        </span>
    `).join('');

    container.querySelectorAll('.chat-chip-x').forEach(btn => {
        btn.addEventListener('click', () => {
            const fid = parseInt(btn.dataset.fid);
            chatAttachments = chatAttachments.filter(a => a.file_id !== fid);
            renderChatChips();
        });
    });
}

function _chatPickerIcon(type) {
    const c = type === 'doc'
        ? { page: '#eff6ff', border: 'rgba(96,165,250,0.45)', fold: '#bfdbfe', badge: '#4285f4', label: 'DOC' }
        : { page: '#fff5f5', border: 'rgba(248,113,113,0.45)', fold: '#fecaca', badge: '#ef4444', label: 'PDF' };
    return `<svg viewBox="0 0 48 64" width="36" height="48" fill="none">
        <path d="M4 2C4 .9 4.9 0 6 0H30L44 14V60C44 61.1 43.1 62 42 62H6C4.9 62 4 61.1 4 60V2Z" fill="${c.page}" stroke="${c.border}" stroke-width="1"/>
        <path d="M30 0L44 14H34C31.8 14 30 12.2 30 10V0Z" fill="${c.fold}"/>
        <rect x="8" y="46" width="22" height="11" rx="2" fill="${c.badge}"/>
        <text x="19" y="54.5" text-anchor="middle" fill="#fff" font-size="7" font-weight="bold" font-family="Inter,system-ui,sans-serif">${c.label}</text>
    </svg>`;
}
