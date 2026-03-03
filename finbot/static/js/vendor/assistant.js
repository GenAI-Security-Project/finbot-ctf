/**
 * FinBot AI Assistant - Chat interface with SSE streaming
 */

const STORAGE_KEY = 'finbot_chat_history';
const MAX_DISPLAY_MESSAGES = 200;

let chatMessages = [];
let isStreaming = false;

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
            localStorage.setItem(STORAGE_KEY, JSON.stringify(chatMessages));
            renderAllMessages();
        } else {
            const cached = localStorage.getItem(STORAGE_KEY);
            if (cached) {
                try {
                    chatMessages = JSON.parse(cached);
                    if (chatMessages.length > 0) renderAllMessages();
                } catch (_) { /* ignore parse errors */ }
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
        bubble.innerHTML = `
            <div class="msg-avatar assistant"><img src="/static/images/common/finbot.png" alt="FinBot" class="w-full h-full rounded-full object-contain"></div>
            <div class="msg-content">${escapeHtml(content)}</div>
        `;
    }

    return bubble;
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

    chatMessages.push({ role: 'user', content: text });
    container.appendChild(createMessageEl('user', text));
    scrollToBottom();

    const assistantBubble = document.createElement('div');
    assistantBubble.className = 'msg-bubble assistant';
    assistantBubble.innerHTML = `
        <div class="msg-avatar assistant"><img src="/static/images/common/finbot.png" alt="FinBot" class="w-full h-full rounded-full object-contain"></div>
        <div class="msg-content streaming-cursor"></div>
    `;
    container.appendChild(assistantBubble);
    const contentEl = assistantBubble.querySelector('.msg-content');
    scrollToBottom();

    let fullResponse = '';

    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const headers = { 'Content-Type': 'application/json' };
        if (csrfMeta) headers['X-CSRF-Token'] = csrfMeta.content;

        const res = await fetch('/vendor/api/v1/chat', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify({ message: text }),
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
                        fullResponse += event.content;
                        contentEl.textContent = fullResponse;
                        scrollToBottom();
                    } else if (event.type === 'done') {
                        break;
                    }
                } catch (_) { /* skip malformed events */ }
            }
        }
    } catch (err) {
        fullResponse = fullResponse || 'Sorry, something went wrong. Please try again.';
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
