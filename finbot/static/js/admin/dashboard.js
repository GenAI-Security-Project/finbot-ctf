/**
 * FinBot Admin Portal - Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardServers();
});

async function loadDashboardServers() {
    const container = document.getElementById('dashboard-servers');
    if (!container) return;

    try {
        const response = await fetch('/admin/api/v1/mcp/servers');
        if (!response.ok) throw new Error('Failed to load servers');
        const data = await response.json();
        const servers = data.servers || [];

        if (servers.length === 0) {
            container.innerHTML = '<p class="text-text-secondary text-center py-4">No MCP servers configured.</p>';
            return;
        }

        container.innerHTML = '<div class="grid grid-cols-1 md:grid-cols-3 gap-4">' +
            servers.map(s => {
                const statusColor = s.enabled ? 'bg-green-500' : 'bg-gray-500';
                const statusText = s.enabled ? 'Enabled' : 'Disabled';
                const toolCount = Object.keys(s.tool_overrides || {}).length;
                const overrideBadge = toolCount > 0
                    ? `<span class="text-xs text-amber-400">${toolCount} override(s)</span>`
                    : '';

                return `
                    <a href="/admin/mcp-servers/${s.server_type}" class="block p-4 rounded-lg border border-white/5 hover:border-admin-primary/30 transition-colors bg-portal-bg-primary/50">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="font-semibold text-text-bright">${escapeAdminHtml(s.display_name)}</h3>
                            <div class="flex items-center gap-1.5">
                                <span class="w-2 h-2 rounded-full ${statusColor}"></span>
                                <span class="text-xs text-text-secondary">${statusText}</span>
                            </div>
                        </div>
                        <p class="text-xs text-text-secondary mb-2">${escapeAdminHtml(s.server_type)}</p>
                        ${overrideBadge}
                    </a>
                `;
            }).join('') +
            '</div>';
    } catch (error) {
        console.error('Error loading dashboard servers:', error);
        container.innerHTML = '<p class="text-red-400 text-center py-4">Failed to load servers.</p>';
    }
}

function escapeAdminHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
