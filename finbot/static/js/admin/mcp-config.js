/**
 * FinBot Admin Portal - MCP Server Configuration & Tool Definition Editor
 */

// Inline fallback if utils.js hasn't been refreshed with showConfirmModal yet
if (typeof showConfirmModal !== 'function') {
    window.showConfirmModal = function({ title = 'Confirm', message = 'Are you sure?', confirmText = 'Confirm', cancelText = 'Cancel', danger = false } = {}) {
        return new Promise((resolve) => {
            const existing = document.getElementById('confirm-modal');
            if (existing) existing.remove();

            const modal = document.createElement('div');
            modal.id = 'confirm-modal';
            modal.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px);padding:1rem;';

            const c = danger ? ['#ef4444','rgba(239,68,68,'] : ['#f59e0b','rgba(245,158,11,'];
            modal.innerHTML = `
                <div style="background:#151520;border:1px solid rgba(255,255,255,0.1);border-radius:0.75rem;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);max-width:28rem;width:100%;overflow:hidden;">
                    <div style="padding:1rem 1.5rem;border-bottom:1px solid rgba(255,255,255,0.05);"><h3 style="font-size:1.125rem;font-weight:700;color:#fff;margin:0;">${title}</h3></div>
                    <div style="padding:1.25rem 1.5rem;"><p style="font-size:0.875rem;color:#94a3b8;line-height:1.625;margin:0;">${message}</p></div>
                    <div style="padding:1rem 1.5rem;border-top:1px solid rgba(255,255,255,0.05);display:flex;justify-content:flex-end;gap:0.75rem;">
                        <button id="confirm-modal-cancel" style="font-size:0.875rem;padding:0.5rem 1rem;border-radius:0.5rem;border:1px solid rgba(255,255,255,0.1);background:transparent;color:#94a3b8;cursor:pointer;">${cancelText}</button>
                        <button id="confirm-modal-confirm" style="font-size:0.875rem;padding:0.5rem 1rem;border-radius:0.5rem;border:1px solid ${c[1]}0.3);background:${c[1]}0.2);color:${c[0]};cursor:pointer;font-weight:500;">${confirmText}</button>
                    </div>
                </div>`;

            const cleanup = (result) => { modal.remove(); document.removeEventListener('keydown', esc); resolve(result); };
            const esc = (e) => { if (e.key === 'Escape') cleanup(false); };
            document.body.appendChild(modal);
            document.addEventListener('keydown', esc);
            modal.addEventListener('click', (e) => { if (e.target === modal) cleanup(false); });
            modal.querySelector('#confirm-modal-cancel').addEventListener('click', () => cleanup(false));
            modal.querySelector('#confirm-modal-confirm').addEventListener('click', () => cleanup(true));
            modal.querySelector('#confirm-modal-cancel').focus();
        });
    };
}

let serverData = null;
let pendingOverrides = {};

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('config-container');
    if (!container) return;
    const serverType = container.dataset.serverType;
    if (serverType) loadServerConfig(serverType);
});

async function loadServerConfig(serverType) {
    const container = document.getElementById('config-container');

    try {
        const response = await fetch(`/admin/api/v1/mcp/servers/${serverType}`);
        if (!response.ok) throw new Error('Failed to load server config');
        const data = await response.json();
        serverData = data.server;

        document.getElementById('config-page-title').textContent = serverData.display_name + ' Configuration';
        document.getElementById('config-page-subtitle').textContent = serverData.description || `Configure ${serverData.display_name} MCP server`;

        pendingOverrides = { ...(serverData.tool_overrides || {}) };

        container.innerHTML = renderConfig(serverData);
        attachConfigHandlers(serverType);
    } catch (error) {
        console.error('Error loading server config:', error);
        container.innerHTML = '<div class="text-center py-16 text-red-400">Failed to load server configuration.</div>';
    }
}

function renderConfig(server) {
    const config = server.config || {};
    const defaultTools = server.default_tools || [];
    const overrides = server.tool_overrides || {};

    let configFieldsHtml = '';
    for (const [key, value] of Object.entries(config)) {
        if (typeof value === 'object' && value !== null) {
            const jsonStr = JSON.stringify(value, null, 2);
            configFieldsHtml += `
                <div class="py-3">
                    <label class="text-sm text-text-secondary font-medium block mb-2">${esc(key)}</label>
                    <textarea class="tool-textarea config-json-input" data-config-key="${esc(key)}"
                        rows="${Math.min(Math.max(jsonStr.split('\n').length, 3), 12)}">${esc(jsonStr)}</textarea>
                </div>
            `;
        } else {
            const type = typeof value === 'number' ? 'number' : 'text';
            configFieldsHtml += `
                <div class="flex items-center justify-between py-2">
                    <label class="text-sm text-text-secondary font-medium">${esc(key)}</label>
                    <input type="${type}" name="config-${key}" value="${esc(String(value))}"
                        class="config-input w-48 text-right" data-config-key="${esc(key)}">
                </div>
            `;
        }
    }

    let toolsHtml = '';
    if (defaultTools.length > 0) {
        toolsHtml = defaultTools.map(tool => {
            const override = overrides[tool.name] || {};
            const currentDesc = override.description || tool.description;
            const isModified = override.description && override.description !== tool.description;

            return `
                <div class="tool-card ${isModified ? 'modified' : ''} p-5 mb-4" data-tool-name="${esc(tool.name)}">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <code class="text-sm font-mono text-admin-primary bg-admin-primary/10 px-2 py-0.5 rounded">${esc(tool.name)}</code>
                            ${isModified
                                ? '<span class="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">Modified</span>'
                                : ''
                            }
                        </div>
                        ${isModified
                            ? `<button class="reset-tool-btn text-xs text-text-secondary hover:text-admin-accent transition-colors" data-tool-name="${esc(tool.name)}">Reset</button>`
                            : ''
                        }
                    </div>
                    <div class="space-y-2">
                        <label class="text-xs text-text-secondary font-medium">Tool Description (visible to LLM)</label>
                        <textarea class="tool-textarea tool-desc-input" data-tool-name="${esc(tool.name)}"
                            data-original-desc="${esc(tool.description)}" rows="3">${esc(currentDesc)}</textarea>
                        ${isModified
                            ? `<details class="mt-2">
                                <summary class="text-xs text-text-secondary cursor-pointer hover:text-text-primary">Show original</summary>
                                <p class="mt-1 text-xs text-text-secondary bg-black/20 rounded p-2 font-mono">${esc(tool.description)}</p>
                               </details>`
                            : ''
                        }
                    </div>
                </div>
            `;
        }).join('');
    } else {
        toolsHtml = '<p class="text-text-secondary text-sm py-4">No tools available for this server.</p>';
    }

    return `
        <!-- Server Status -->
        <div class="flex items-center gap-4 mb-8">
            <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full ${server.enabled ? 'bg-green-500' : 'bg-gray-500'}"></span>
                <span class="text-sm font-medium ${server.enabled ? 'text-green-400' : 'text-text-secondary'}">
                    ${server.enabled ? 'Enabled' : 'Disabled'}
                </span>
            </div>
            <span class="text-text-secondary text-sm">|</span>
            <span class="text-sm text-text-secondary font-mono">${esc(server.server_type)}</span>
        </div>

        <!-- Server Settings -->
        ${configFieldsHtml ? `
        <div class="bg-portal-bg-secondary border border-admin-primary/20 rounded-xl overflow-hidden mb-8">
            <div class="px-6 py-4 border-b border-admin-primary/10 flex items-center justify-between">
                <h2 class="text-lg font-bold text-text-bright">Server Settings</h2>
                <button id="save-config-btn" class="text-sm px-4 py-1.5 rounded-lg bg-admin-primary/20 text-admin-primary border border-admin-primary/30 hover:bg-admin-primary/30 transition-colors">
                    Save Settings
                </button>
            </div>
            <div class="px-6 py-4 divide-y divide-white/5">
                ${configFieldsHtml}
            </div>
        </div>
        ` : ''}

        <!-- Tool Definition Editor -->
        <div class="bg-portal-bg-secondary border border-admin-primary/20 rounded-xl overflow-hidden">
            <div class="px-6 py-4 border-b border-admin-primary/10 flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-bold text-text-bright">Tool Definitions</h2>
                    <p class="text-xs text-text-secondary mt-1">Modify tool descriptions to change what the LLM sees when deciding how to use each tool</p>
                </div>
                <div class="flex items-center gap-3">
                    <button id="reset-all-tools-btn" class="text-sm px-4 py-1.5 rounded-lg border border-white/10 text-text-secondary hover:text-text-bright hover:border-white/20 transition-colors">
                        Reset All
                    </button>
                    <button id="save-tools-btn" class="text-sm px-4 py-1.5 rounded-lg bg-admin-primary/20 text-admin-primary border border-admin-primary/30 hover:bg-admin-primary/30 transition-colors">
                        Save Overrides
                    </button>
                </div>
            </div>
            <div class="p-6">
                ${toolsHtml}
            </div>
        </div>
    `;
}

function attachConfigHandlers(serverType) {
    // Save server settings
    const saveConfigBtn = document.getElementById('save-config-btn');
    if (saveConfigBtn) {
        saveConfigBtn.addEventListener('click', () => saveConfig(serverType));
    }

    // Save tool overrides
    const saveToolsBtn = document.getElementById('save-tools-btn');
    if (saveToolsBtn) {
        saveToolsBtn.addEventListener('click', () => saveToolOverrides(serverType));
    }

    // Reset all tools
    const resetAllBtn = document.getElementById('reset-all-tools-btn');
    if (resetAllBtn) {
        resetAllBtn.addEventListener('click', () => {
            resetAllTools(serverType).catch(err => {
                console.error('Reset all tools error:', err);
                showNotification('An unexpected error occurred.', 'error');
            });
        });
    }

    // Individual tool reset buttons
    document.querySelectorAll('.reset-tool-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const toolName = btn.dataset.toolName;
            const textarea = document.querySelector(`.tool-desc-input[data-tool-name="${toolName}"]`);
            if (textarea) {
                textarea.value = textarea.dataset.originalDesc;
                delete pendingOverrides[toolName];
                const card = textarea.closest('.tool-card');
                if (card) card.classList.remove('modified');
            }
        });
    });

    // Track changes in tool descriptions
    document.querySelectorAll('.tool-desc-input').forEach(textarea => {
        textarea.addEventListener('input', () => {
            const toolName = textarea.dataset.toolName;
            const originalDesc = textarea.dataset.originalDesc;
            const currentDesc = textarea.value;
            const card = textarea.closest('.tool-card');

            if (currentDesc !== originalDesc) {
                pendingOverrides[toolName] = { description: currentDesc };
                if (card) card.classList.add('modified');
            } else {
                delete pendingOverrides[toolName];
                if (card) card.classList.remove('modified');
            }
        });
    });
}

async function saveConfig(serverType) {
    const inputs = document.querySelectorAll('[data-config-key]');
    const config = {};
    let parseError = null;
    inputs.forEach(input => {
        const key = input.dataset.configKey;
        if (input.classList.contains('config-json-input')) {
            try {
                config[key] = JSON.parse(input.value);
            } catch (e) {
                parseError = `Invalid JSON in "${key}": ${e.message}`;
            }
        } else {
            const value = input.type === 'number' ? parseFloat(input.value) : input.value;
            config[key] = value;
        }
    });

    if (parseError) {
        showNotification(parseError, 'error');
        return;
    }

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        const response = await fetch(`/admin/api/v1/mcp/servers/${serverType}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
            },
            body: JSON.stringify({ config }),
        });
        if (!response.ok) throw new Error('Save failed');
        showNotification('Server settings saved successfully.', 'success');
    } catch (error) {
        console.error('Error saving config:', error);
        showNotification('Failed to save settings. Please try again.', 'error');
    }
}

async function saveToolOverrides(serverType) {
    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        const response = await fetch(`/admin/api/v1/mcp/servers/${serverType}/tools`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
            },
            body: JSON.stringify({ tool_overrides: pendingOverrides }),
        });
        if (!response.ok) throw new Error('Save failed');
        showNotification('Tool overrides saved. Changes take effect on the next agent run.', 'success');
        await loadServerConfig(serverType);
    } catch (error) {
        console.error('Error saving tool overrides:', error);
        showNotification('Failed to save tool overrides. Please try again.', 'error');
    }
}

async function resetAllTools(serverType) {
    const confirmed = await showConfirmModal({
        title: 'Reset Tool Definitions',
        message: 'Reset all tool definitions to defaults? This removes all your modifications.',
        confirmText: 'Reset All',
        cancelText: 'Cancel',
        danger: true,
    });
    if (!confirmed) return;

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        const response = await fetch(`/admin/api/v1/mcp/servers/${serverType}/reset-tools`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
            },
        });
        if (!response.ok) throw new Error('Reset failed');
        pendingOverrides = {};
        showNotification('Tool definitions reset to defaults.', 'success');
        await loadServerConfig(serverType);
    } catch (error) {
        console.error('Error resetting tools:', error);
        showNotification('Failed to reset tools. Please try again.', 'error');
    }
}

function esc(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
