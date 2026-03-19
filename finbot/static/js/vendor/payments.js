/**
 * FinBot Vendor Portal - Payments Management
 */

const PaymentState = {
    transactions: [],
    summary: null,
    isLoading: false,
};

ready(function () {
    initializePayments();
});

async function initializePayments() {
    console.log('Initializing Payments...');

    try {
        initializeRequestPayment();

        await Promise.all([
            loadPaymentSummary(),
            loadTransactions(),
        ]);

        console.log('Payments initialized');
    } catch (error) {
        console.error('Payment initialization failed:', error);
        showNotification('Failed to load payment data', 'error');
    }
}

function initializeRequestPayment() {
    const btn = document.getElementById('request-payment-btn');
    if (btn) {
        btn.addEventListener('click', async () => {
            try {
                const response = await api.get('/vendor/api/v1/invoices');
                const data = response.data || response;
                const invoices = (data.invoices || []).filter(inv => inv.status === 'approved');

                let prompt;
                if (invoices.length === 0) {
                    prompt = 'I would like to check if I have any invoices ready for payment processing.';
                } else if (invoices.length === 1) {
                    const inv = invoices[0];
                    prompt = `Please process payment for my approved invoice ${inv.invoice_number} (ID: ${inv.id}, amount: $${inv.amount.toFixed(2)}).`;
                } else {
                    const list = invoices.map(inv => `${inv.invoice_number} (ID: ${inv.id}, $${inv.amount.toFixed(2)})`).join(', ');
                    prompt = `I have ${invoices.length} approved invoices ready for payment: ${list}. Please process the payments.`;
                }

                window.location.href = '/vendor/assistant?prompt=' + encodeURIComponent(prompt);
            } catch (error) {
                console.error('Error fetching invoices:', error);
                window.location.href = '/vendor/assistant?prompt=' +
                    encodeURIComponent('Please process payments for my approved invoices.');
            }
        });
    }
}

async function loadPaymentSummary() {
    try {
        const response = await api.get('/vendor/api/v1/payments/summary');
        const data = response.data || response;
        PaymentState.summary = data;
        updatePaymentStats(data);
    } catch (error) {
        console.error('Error loading payment summary:', error);
    }
}

function updatePaymentStats(data) {
    const summary = data.summary;

    const totalPaidEl = document.getElementById('stat-total-paid');
    if (totalPaidEl) {
        totalPaidEl.textContent = formatPaymentCurrency(summary.total_paid);
    }

    const pendingEl = document.getElementById('stat-pending-amount');
    if (pendingEl) {
        pendingEl.textContent = formatPaymentCurrency(summary.total_pending);
    }

    const txnCountEl = document.getElementById('stat-txn-count');
    if (txnCountEl) {
        txnCountEl.textContent = summary.transaction_count;
    }

    const failedEl = document.getElementById('stat-failed-count');
    if (failedEl) {
        failedEl.textContent = summary.failed_count;
    }
}

async function loadTransactions() {
    const tableBody = document.getElementById('transactions-table-body');
    const emptyState = document.getElementById('transactions-empty-state');

    PaymentState.isLoading = true;

    try {
        const response = await api.get('/vendor/api/v1/payments/transactions');
        const data = response.data || response;
        const transactions = data.transactions || [];

        PaymentState.transactions = transactions;

        tableBody.innerHTML = '';

        if (transactions.length === 0) {
            document.querySelector('.neural-table').classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }

        document.querySelector('.neural-table').classList.remove('hidden');
        emptyState.classList.add('hidden');

        transactions.forEach(txn => {
            const row = createTransactionRow(txn);
            tableBody.appendChild(row);
        });

        tableBody.querySelectorAll('.description-preview').forEach(el => {
            el.addEventListener('click', () => {
                const full = el.dataset.fullDescription;
                if (full) showDescriptionModal(full);
            });
        });

    } catch (error) {
        console.error('Error loading transactions:', error);
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-8 text-text-secondary">
                    Failed to load transactions. Please try again.
                </td>
            </tr>
        `;
    } finally {
        PaymentState.isLoading = false;
    }
}

function createTransactionRow(txn) {
    const row = document.createElement('tr');

    const amount = formatPaymentCurrency(txn.amount);
    const date = formatPaymentDate(txn.created_at);
    const method = formatMethod(txn.payment_method);
    const statusConfig = getTransactionStatusConfig(txn.status);
    const transferId = txn.transfer_id;
    const rawDesc = txn.description || '';
    const descPreview = rawDesc.length > 40 ? rawDesc.substring(0, 40) + '...' : rawDesc;
    const isTruncated = rawDesc.length > 40;

    row.innerHTML = `
        <td>
            <span class="transfer-id break-all">${escapePaymentHtml(transferId)}</span>
        </td>
        <td>
            <span class="font-semibold text-vendor-accent">${amount}</span>
            <span class="text-xs text-text-secondary ml-1">${txn.currency ? txn.currency.toUpperCase() : 'USD'}</span>
        </td>
        <td>
            <span class="method-badge">${method}</span>
        </td>
        <td>
            <span class="txn-status ${statusConfig.class}">${statusConfig.label}</span>
        </td>
        <td>
            ${rawDesc
                ? `<span class="text-text-secondary text-sm${isTruncated ? ' description-preview cursor-pointer hover:text-text-primary transition-colors' : ''}"
                         ${isTruncated ? `data-full-description="${escapePaymentHtml(rawDesc)}" title="Click to view full description"` : ''}
                   >${escapePaymentHtml(descPreview)}</span>`
                : '<span class="text-text-secondary text-sm">-</span>'
            }
        </td>
        <td>
            <span class="text-text-primary text-sm">${date}</span>
        </td>
    `;

    return row;
}

function getTransactionStatusConfig(status) {
    const configs = {
        'completed': { class: 'completed', label: 'Completed' },
        'pending': { class: 'pending', label: 'Pending' },
        'failed': { class: 'failed', label: 'Failed' },
    };
    return configs[status] || { class: 'pending', label: status };
}

function formatMethod(method) {
    if (!method) return 'N/A';
    return method.replace(/_/g, ' ');
}

function formatPaymentCurrency(amount) {
    if (amount === null || amount === undefined) return '$0.00';
    try {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
        }).format(amount);
    } catch (error) {
        return `$${parseFloat(amount).toFixed(2)}`;
    }
}

function formatPaymentDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
        });
    } catch (error) {
        return 'Invalid Date';
    }
}

function escapePaymentHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showDescriptionModal(content) {
    const existing = document.getElementById('desc-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'desc-modal';
    modal.className = 'fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4';
    modal.innerHTML = `
        <div class="bg-portal-bg-secondary border border-vendor-primary/30 rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div class="px-6 py-4 border-b border-vendor-primary/10 flex items-center justify-between">
                <h3 class="text-lg font-bold text-text-bright">Transaction Description</h3>
                <button id="close-desc-modal" class="text-text-secondary hover:text-text-bright transition-colors">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="p-6 overflow-auto max-h-[calc(80vh-80px)]">
                <p class="text-sm text-text-primary whitespace-pre-wrap break-words">${escapePaymentHtml(content)}</p>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
    modal.querySelector('#close-desc-modal').addEventListener('click', () => modal.remove());
    document.addEventListener('keydown', function handler(e) {
        if (e.key === 'Escape') { modal.remove(); document.removeEventListener('keydown', handler); }
    });
}
