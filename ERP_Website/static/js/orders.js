// ─── State ─────────────────────────────────────────────────────────────────────
const state = {
    page: 1,
    risk_tier: '',
    payment_method: '',
    category: '',
    city: '',
    returned: '',
    search: '',
    date_from: '',
    date_to: '',
    expandedRow: null
};

const pct = n => (n !== null && n !== undefined) ? Number(n).toFixed(1) + '%' : '—';

function riskBadge(tier) {
    if (!tier) return '<span class="badge badge-gray">N/A</span>';
    const cls = { LOW: 'badge-low', MEDIUM: 'badge-medium', HIGH: 'badge-high' }[tier] || 'badge-gray';
    return `<span class="badge ${cls}">${tier}</span>`;
}

// ─── Fetch & Render ────────────────────────────────────────────────────────────
async function fetchOrders() {
    const params = new URLSearchParams({
        page: state.page,
        risk_tier: state.risk_tier,
        payment_method: state.payment_method,
        category: state.category,
        city: state.city,
        returned: state.returned,
        search: state.search,
        date_from: state.date_from,
        date_to: state.date_to
    });

    const tbody = document.getElementById('ordersBody');
    tbody.innerHTML = '<tr><td colspan="14" style="text-align:center;padding:24px;color:var(--text-muted);">Loading...</td></tr>';

    const res = await fetch('/api/orders?' + params.toString());
    const data = await res.json();
    if (data.error) {
        tbody.innerHTML = `<tr><td colspan="14" style="color:var(--danger);padding:20px;">${data.error}</td></tr>`;
        return;
    }

    renderTable(data);
    renderPagination(data);
    renderSummary(data);
}

function renderTable(data) {
    const tbody = document.getElementById('ordersBody');
    if (!data.rows || data.rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" style="text-align:center;padding:40px;color:var(--text-muted);">No orders found for selected filters.</td></tr>';
        return;
    }

    tbody.innerHTML = data.rows.map((row, idx) => {
        const predicted = row.risk_tier === 'HIGH';
        const actualRet = !!row.is_returned;
        let rowClass = '';
        if (predicted && !actualRet) rowClass = 'false-alarm';
        else if (!predicted && actualRet && row.risk_tier) rowClass = 'missed';

        const retCell = row.is_returned
            ? '<span class="returned-yes">✓</span>'
            : '<span class="returned-no">✗</span>';

        return `
            <tr class="${rowClass}" data-idx="${idx}" style="cursor:pointer;" onclick="toggleExpand(${idx}, this)">
                <td><code>${row.order_id}</code></td>
                <td>${row.order_date || '—'}</td>
                <td><code>${row.customer_id}</code></td>
                <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${row.product_name}">${row.product_name}</td>
                <td>${row.category}</td>
                <td>${row.quantity}</td>
                <td>${pct(row.discount_percentage)}</td>
                <td>${row.payment_method}</td>
                <td>${row.courier_partner}</td>
                <td>${row.delivery_city}</td>
                <td>${row.predicted_pct !== null ? pct(row.predicted_pct) : '—'}</td>
                                <td>${retCell}</td>
                <td style="font-size:11px;color:var(--text-muted);">${row.return_reason || '—'}</td>
            </tr>
            <tr class="row-expand" id="expand-${idx}" style="display:none;">
                <td colspan="14">
                    <div class="expand-details">
                        <div class="expand-section">
                            <h4>Order Details</h4>
                            <div class="expand-row"><span class="expand-row-label">Order ID</span><span class="expand-row-value"><code>${row.order_id}</code></span></div>
                            <div class="expand-row"><span class="expand-row-label">Customer</span><span class="expand-row-value"><code>${row.customer_id}</code></span></div>
                            <div class="expand-row"><span class="expand-row-label">Product</span><span class="expand-row-value">${row.product_name}</span></div>
                            <div class="expand-row"><span class="expand-row-label">Category</span><span class="expand-row-value">${row.category}</span></div>
                            <div class="expand-row"><span class="expand-row-label">Quantity</span><span class="expand-row-value">${row.quantity}</span></div>
                            <div class="expand-row"><span class="expand-row-label">Discount</span><span class="expand-row-value">${pct(row.discount_percentage)}</span></div>
                            <div class="expand-row"><span class="expand-row-label">Payment</span><span class="expand-row-value">${row.payment_method}</span></div>
                        </div>
                        <div class="expand-section">
                            <h4>Logistics</h4>
                            <div class="expand-row"><span class="expand-row-label">Courier</span><span class="expand-row-value">${row.courier_partner}</span></div>
                            <div class="expand-row"><span class="expand-row-label">City</span><span class="expand-row-value">${row.delivery_city}</span></div>
                            <div class="expand-row"><span class="expand-row-label">Date</span><span class="expand-row-value">${row.order_date || '—'}</span></div>
                        </div>
                        <div class="expand-section">
                            <h4>ML Prediction</h4>
                            <div class="expand-row"><span class="expand-row-label">Predicted Risk</span><span class="expand-row-value">${pct(row.predicted_pct)}</span></div>
                            
                            <div class="expand-row"><span class="expand-row-label">Actual Returned</span><span class="expand-row-value">${row.is_returned ? '✓ Yes' : '✗ No'}</span></div>
                            <div class="expand-row"><span class="expand-row-label">Return Reason</span><span class="expand-row-value">${row.return_reason || '—'}</span></div>
                            ${rowClass === 'false-alarm' ? '<div style="color:var(--warning);font-size:11px;margin-top:6px;">False Alarm: Predicted HIGH but not returned</div>' : ''}
                            ${rowClass === 'missed' ? '<div style="color:var(--danger);font-size:11px;margin-top:6px;">Missed: Predicted LOW but returned</div>' : ''}
                        </div>
                    </div>
                </td>
            </tr>`;
    }).join('');

    // Store rows for expand
    window._ordersData = data.rows;
}

function toggleExpand(idx, tr) {
    const expandRow = document.getElementById(`expand-${idx}`);
    if (!expandRow) return;
    const isOpen = expandRow.style.display !== 'none';
    // Close all
    document.querySelectorAll('.row-expand').forEach(r => r.style.display = 'none');
    if (!isOpen) {
        expandRow.style.display = 'table-row';
    }
}

function renderPagination(data) {
    const totalPages = Math.ceil(data.total / data.per_page);
    const container = document.getElementById('paginationContainer');
    const info = document.getElementById('paginationInfo');

    const start = (data.page - 1) * data.per_page + 1;
    const end = Math.min(data.page * data.per_page, data.total);
    info.textContent = `Showing ${start}–${end} of ${data.total.toLocaleString('en-IN')} orders`;

    let pages = [];
    pages.push(`<button class="page-btn" ${data.page === 1 ? 'disabled' : ''} onclick="goPage(${data.page - 1})">‹ Prev</button>`);

    const maxShown = 7;
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= data.page - 2 && i <= data.page + 2)) {
            pages.push(`<button class="page-btn ${i === data.page ? 'active' : ''}" onclick="goPage(${i})">${i}</button>`);
        } else if (i === data.page - 3 || i === data.page + 3) {
            pages.push('<span class="page-info">…</span>');
        }
    }

    pages.push(`<button class="page-btn" ${data.page === totalPages ? 'disabled' : ''} onclick="goPage(${data.page + 1})">Next ›</button>`);
    container.innerHTML = pages.join('');
}

function renderSummary(data) {
    const rows = data.rows || [];
    const highRisk = rows.filter(r => r.risk_tier === 'HIGH').length;
    const returned = rows.filter(r => r.is_returned).length;
    const risks = rows.filter(r => r.predicted_pct !== null).map(r => r.predicted_pct);
    const avgRisk = risks.length ? (risks.reduce((a, b) => a + b, 0) / risks.length).toFixed(1) : '—';

    document.getElementById('statTotal').textContent = data.total.toLocaleString('en-IN');
    document.getElementById('statHighRisk').textContent = highRisk;
    document.getElementById('statReturned').textContent = returned;
    document.getElementById('statAvgRisk').textContent = avgRisk !== '—' ? avgRisk + '%' : '—';
}

function goPage(p) {
    state.page = p;
    fetchOrders();
}

// ─── Filter Events ─────────────────────────────────────────────────────────────
let searchTimer = null;
document.getElementById('filterSearch').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        state.search = e.target.value;
        state.page = 1;
        fetchOrders();
    }, 400);
});

['filterPayment', 'filterCategory', 'filterCity', 'filterReturned', 'filterDateFrom', 'filterDateTo'].forEach(id => {
    document.getElementById(id).addEventListener('change', e => {
        const key = {
            filterPayment: 'payment_method',
            filterCategory: 'category',
            filterCity: 'city',
            filterReturned: 'returned',
            filterDateFrom: 'date_from',
            filterDateTo: 'date_to'
        }[id];
        state[key] = e.target.value;
        state.page = 1;
        fetchOrders();
    });
});

// Risk Tier Pills
document.getElementById('riskPillGroup')?.addEventListener('click', e => {
    const pill = e.target.closest('.pill');
    if (!pill) return;
    document.querySelectorAll('#riskPillGroup .pill').forEach(p => p.classList.remove('active', 'active-low', 'active-medium', 'active-high'));
    const val = pill.dataset.value;
    pill.classList.add('active');
    if (val) pill.classList.add(`active-${val.toLowerCase()}`);
    state.risk_tier = val;
    state.page = 1;
    fetchOrders();
});

// Reset
document.getElementById('resetFilters').addEventListener('click', () => {
    Object.assign(state, { page: 1, risk_tier: '', payment_method: '', category: '', city: '', returned: '', search: '', date_from: '', date_to: '' });
    document.getElementById('filterSearch').value = '';
    document.getElementById('filterPayment').value = '';
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterCity').value = '';
    document.getElementById('filterReturned').value = '';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    document.querySelectorAll('#riskPillGroup .pill').forEach((p, i) => {
        p.classList.remove('active', 'active-low', 'active-medium', 'active-high');
        if (i === 0) p.classList.add('active');
    });
    fetchOrders();
});

// CSV Export
document.getElementById('exportFilteredCsvBtn').addEventListener('click', e => {
    e.preventDefault();
    const params = new URLSearchParams({
        risk_tier: state.risk_tier,
        payment_method: state.payment_method,
        category: state.category,
        city: state.city,
        date_from: state.date_from,
        date_to: state.date_to
    });
    window.location.href = '/api/orders/export?' + params.toString();
});

// ─── Init ─────────────────────────────────────────────────────────────────────
fetchOrders();