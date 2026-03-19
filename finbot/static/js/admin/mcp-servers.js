/**
 * FinBot Admin Portal - MCP Servers Registry
 */

document.addEventListener('DOMContentLoaded', () => {
    loadMCPServers();
});

async function loadMCPServers() {
    const container = document.getElementById('servers-container');
    if (!container) return;

    try {
        const response = await fetch('/admin/api/v1/mcp/servers');
        if (!response.ok) throw new Error('Failed to load servers');
        const data = await response.json();
        const servers = data.servers || [];

        container.innerHTML = servers.map(s => renderServerCard(s)).join('');

        container.querySelectorAll('.toggle-server-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleServer(btn.dataset.serverType);
            });
        });
    } catch (error) {
        console.error('Error loading MCP servers:', error);
        container.innerHTML = '<div class="col-span-full text-center py-16 text-red-400">Failed to load MCP servers.</div>';
    }
}

function renderServerCard(server) {
    const isEnabled = server.enabled;
    const statusDot = isEnabled ? 'bg-green-500' : 'bg-gray-500';
    const statusText = isEnabled ? 'Enabled' : 'Disabled';
    const overrideCount = Object.keys(server.tool_overrides || {}).length;
    const borderColor = isEnabled ? 'border-admin-primary/20 hover:border-admin-primary/40' : 'border-white/5 hover:border-white/10';

    return `
        <div class="bg-portal-bg-secondary border ${borderColor} rounded-xl overflow-hidden transition-colors">
            <a href="/admin/mcp-servers/${server.server_type}" class="block p-6">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-admin-primary/20 to-admin-secondary/20 flex items-center justify-center">
                            <svg class="w-6 h-6 text-admin-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/>
                            </svg>
                        </div>
                        <div>
                            <h3 class="text-lg font-bold text-text-bright">${esc(server.display_name)}</h3>
                            <span class="text-xs text-text-secondary font-mono">${esc(server.server_type)}</span>
                        </div>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="w-2.5 h-2.5 rounded-full ${statusDot}"></span>
                        <span class="text-xs text-text-secondary">${statusText}</span>
                    </div>
                </div>

                <p class="text-sm text-text-secondary mb-4">${esc(server.description || '')}</p>

                <div class="flex items-center gap-4 text-xs text-text-secondary">
                    ${overrideCount > 0
                        ? `<span class="inline-flex items-center gap-1 text-amber-400">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                            </svg>
                            ${overrideCount} tool override(s)
                          </span>`
                        : '<span>No overrides</span>'
                    }
                </div>
            </a>

            <div class="px-6 py-3 border-t border-white/5 flex items-center justify-between">
                <button class="toggle-server-btn text-xs px-3 py-1.5 rounded-lg border transition-colors
                    ${isEnabled
                        ? 'border-red-500/30 text-red-400 hover:bg-red-500/10'
                        : 'border-green-500/30 text-green-400 hover:bg-green-500/10'
                    }"
                    data-server-type="${server.server_type}">
                    ${isEnabled ? 'Disable' : 'Enable'}
                </button>
                <a href="/admin/mcp-servers/${server.server_type}" class="text-xs text-admin-primary hover:text-admin-accent transition-colors">
                    Configure &rarr;
                </a>
            </div>
        </div>
    `;
}

async function toggleServer(serverType) {
    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        const response = await fetch(`/admin/api/v1/mcp/servers/${serverType}/toggle`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
            },
        });
        if (!response.ok) throw new Error('Toggle failed');
        await loadMCPServers();
        showNotification('Server toggled successfully.', 'success');
    } catch (error) {
        console.error('Error toggling server:', error);
        showNotification('Failed to toggle server. Please try again.', 'error');
    }
}

function esc(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
