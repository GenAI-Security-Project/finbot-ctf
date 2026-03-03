/**
 * FinBot Admin Portal - MCP Activity Log
 */

document.addEventListener('DOMContentLoaded', () => {
    loadActivity();

    const refreshBtn = document.getElementById('refresh-activity-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => loadActivity());

    const filterServer = document.getElementById('filter-server');
    if (filterServer) filterServer.addEventListener('change', () => loadActivity());
});

async function loadActivity() {
    const tableBody = document.getElementById('activity-table-body');
    const countEl = document.getElementById('activity-count');
    if (!tableBody) return;

    const serverType = document.getElementById('filter-server')?.value || '';

    let url = '/admin/api/v1/mcp/activity?limit=200';
    if (serverType) url += `&server_type=${encodeURIComponent(serverType)}`;

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load activity');
        const data = await response.json();
        const entries = data.entries || [];

        if (countEl) countEl.textContent = `${entries.length} of ${data.total_count} entries`;

        if (entries.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-text-secondary">No activity found.</td></tr>';
            return;
        }

        tableBody.innerHTML = entries.map(e => renderActivityRow(e)).join('');

        tableBody.querySelectorAll('.payload-preview').forEach(el => {
            el.addEventListener('click', () => {
                const full = el.dataset.fullPayload;
                if (full) {
                    try {
                        const formatted = JSON.stringify(JSON.parse(full), null, 2);
                        showPayloadModal(formatted);
                    } catch {
                        showPayloadModal(full);
                    }
                }
            });
        });
    } catch (error) {
        console.error('Error loading activity:', error);
        tableBody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-red-400">Failed to load activity.</td></tr>';
    }
}

function renderActivityRow(entry) {
    const time = formatActivityTime(entry.created_at);
    const dirClass = entry.direction === 'request' ? 'request' : 'response';
    const duration = entry.duration_ms ? `${Math.round(entry.duration_ms)}ms` : '-';
    const payloadStr = entry.payload ? JSON.stringify(entry.payload) : '';
    const payloadPreview = payloadStr.length > 60 ? payloadStr.substring(0, 60) + '...' : payloadStr;

    return `
        <tr class="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
            <td class="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">${esc(time)}</td>
            <td class="px-4 py-3 text-sm">
                <span class="font-mono text-xs text-admin-primary">${esc(entry.server_type)}</span>
            </td>
            <td class="px-4 py-3">
                <span class="dir-badge ${dirClass}">${entry.direction}</span>
            </td>
            <td class="px-4 py-3 text-sm text-text-primary font-mono">${esc(entry.method)}</td>
            <td class="px-4 py-3 text-sm text-text-primary">${esc(entry.tool_name || '-')}</td>
            <td class="px-4 py-3 text-xs text-text-secondary">${duration}</td>
            <td class="px-4 py-3">
                ${payloadStr
                    ? `<span class="payload-preview" data-full-payload="${escAttr(payloadStr)}" title="Click to expand">${esc(payloadPreview)}</span>`
                    : '<span class="text-xs text-text-secondary">-</span>'
                }
            </td>
        </tr>
    `;
}

function showPayloadModal(content) {
    const existing = document.getElementById('payload-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'payload-modal';
    modal.className = 'fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4';
    modal.innerHTML = `
        <div class="bg-portal-bg-secondary border border-admin-primary/30 rounded-xl shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden">
            <div class="px-6 py-4 border-b border-admin-primary/10 flex items-center justify-between">
                <h3 class="text-lg font-bold text-text-bright">Payload Details</h3>
                <button id="close-payload-modal" class="text-text-secondary hover:text-text-bright transition-colors">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="p-6 overflow-auto max-h-[calc(80vh-80px)]">
                <pre class="text-sm text-text-primary font-mono whitespace-pre-wrap break-words">${esc(content)}</pre>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
    modal.querySelector('#close-payload-modal').addEventListener('click', () => modal.remove());
    document.addEventListener('keydown', function handler(e) {
        if (e.key === 'Escape') { modal.remove(); document.removeEventListener('keydown', handler); }
    });
}

function formatActivityTime(dateString) {
    if (!dateString) return '-';
    try {
        const d = new Date(dateString);
        return d.toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: false,
        });
    } catch { return dateString; }
}

function esc(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escAttr(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
