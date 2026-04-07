// ─── State & Utilities ────────────────────────────────────────────────────────
const state = { page: 1, search: '', segment: '', city: '', sort_by: 'customer_id' };
const inr = n => '₹' + Number(n).toLocaleString('en-IN');
const pct = n => Number(n !== null && n !== undefined ? n : 0).toFixed(1) + '%';
let analysisCharts = [];

function segmentBadge(seg) {
    const map = { Zero: 'badge-blue', Low: 'badge-low', Medium: 'badge-medium', High: 'badge-high' };
    return `<span class="badge ${map[seg] || 'badge-gray'}">${seg}</span>`;
}

function rateColor(rate) {
    const r = parseFloat(rate);
    if (r > 0.25) return 'var(--danger)';
    if (r > 0.10) return 'var(--warning)';
    return 'var(--success)';
}

// ─── Fetch & Render Customers Grid ────────────────────────────────────────────
async function fetchCustomers() {
    const params = new URLSearchParams({
        page: state.page,
        search: state.search,
        segment: state.segment,
        city: state.city,
        sort_by: state.sort_by
    });

    const grid = document.getElementById('customerGrid');
    grid.innerHTML = Array(8).fill(`
        <div class="customer-card">
            <div class="skeleton" style="height:20px;margin-bottom:12px;"></div>
            <div class="skeleton" style="height:40px;margin-bottom:12px;"></div>
            <div class="skeleton" style="height:12px;"></div>
        </div>`).join('');

    const res = await fetch('/api/customers?' + params.toString());
    const data = await res.json();
    if (data.error) { grid.innerHTML = `<div style="color:var(--danger)">${data.error}</div>`; return; }

    document.getElementById('custSummary').textContent =
        `Showing ${data.rows.length} of ${data.total} customers`;

    grid.innerHTML = data.rows.map(c => {
        const rate = parseFloat(c.overall_return_rate || 0);
        const ratePct = (rate * 100).toFixed(1);
        const fillColor = rate > 0.25 ? '#DC2626' : rate > 0.10 ? '#D97706' : '#059669';
        
        // Dynamic Card Background Tint
        let cardBg = 'rgba(148, 163, 184, 0.05)'; // Neutral/Zero
        if (rate > 0.25) cardBg = 'rgba(220, 38, 38, 0.08)'; // High
        else if (rate > 0.10) cardBg = 'rgba(212, 175, 55, 0.1)';   // Medium (Gold)
        else if (rate > 0.0) cardBg = 'rgba(16, 185, 129, 0.08)';  // Low

        return `
        <div class="customer-card" onclick="openModal('${c.customer_id}')" style="background:${cardBg};">
            <div class="customer-card-header">
                <div class="customer-id">${c.customer_id}</div>
                <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;">
                    <span class="badge badge-blue">${c.city || '-'}</span>
                    ${segmentBadge(c.segment)}
                </div>
            </div>
            <div class="customer-stats-row">
                <div class="customer-stat">
                    <span class="customer-stat-val">${c.total_orders}</span>
                    <span class="customer-stat-lbl">Orders</span>
                </div>
                <div class="customer-stat">
                    <span class="customer-stat-val">${c.total_returns}</span>
                    <span class="customer-stat-lbl">Returns</span>
                </div>
                <div class="customer-stat">
                    <span class="customer-stat-val" style="color:${color};font-size:18px;">${ratePct}%</span>
                    <span class="customer-stat-lbl">Return Rate</span>
                </div>
            </div>
            <div class="return-rate-bar">
                <div class="return-rate-fill" style="width:${fillWidth}%;background:${fillColor};"></div>
            </div>
            <div class="customer-card-footer">
                <span>AOV: <strong style="color:var(--primary)">${inr(Math.round(c.avg_order_value || 0))}</strong></span>
                <span>Tenure: <strong>${c.customer_tenure_days}d</strong></span>
                <span>Last Order: <strong>${c.last_order_days_ago}d ago</strong></span>
            </div>
        </div>`;
    }).join('');

    renderCustPagination(data);
}

function renderCustPagination(data) {
    const totalPages = Math.ceil(data.total / data.per_page);
    const container = document.getElementById('custPagination');
    let pages = [];
    pages.push(`<button class="page-btn" ${data.page === 1 ? 'disabled' : ''} onclick="goPage(${data.page - 1})">‹ Prev</button>`);
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || Math.abs(i - data.page) <= 2)
            pages.push(`<button class="page-btn ${i === data.page ? 'active' : ''}" onclick="goPage(${i})">${i}</button>`);
        else if (Math.abs(i - data.page) === 3)
            pages.push('<span class="page-info">…</span>');
    }
    pages.push(`<button class="page-btn" ${data.page === totalPages ? 'disabled' : ''} onclick="goPage(${data.page + 1})">Next ›</button>`);
    container.innerHTML = pages.join('');
}

function goPage(p) { state.page = p; fetchCustomers(); }

// ─── Filter Events ────────────────────────────────────────────────────────────
let searchTimer = null;
document.getElementById('custSearch').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = e.target.value; state.page = 1; fetchCustomers(); }, 400);
});

document.getElementById('custCity').addEventListener('change', e => { state.city = e.target.value; state.page = 1; fetchCustomers(); });
document.getElementById('custSort').addEventListener('change', e => { state.sort_by = e.target.value; state.page = 1; fetchCustomers(); });

document.getElementById('segPillGroup').addEventListener('click', e => {
    const pill = e.target.closest('.pill');
    if (!pill) return;
    document.querySelectorAll('#segPillGroup .pill').forEach(p => p.classList.remove('active', 'active-low', 'active-medium', 'active-high'));
    pill.classList.add('active');
    const val = pill.dataset.value;
    if (val && val !== 'zero') pill.classList.add(`active-${val}`);
    state.segment = val;
    state.page = 1;
    fetchCustomers();
});

// ─── Modal ─────────────────────────────────────────────────────────────────────
let modalCharts = [];

async function openModal(customerId) {
    document.getElementById('customerModal').style.display = 'flex';
    document.getElementById('modalTitle').textContent = `Customer Profile - ${customerId}`;
    document.body.style.overflow = 'hidden';

    // Reset tabs
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="overview"]').classList.add('active');
    document.getElementById('tab-overview').classList.add('active');

    // Destroy old charts
    modalCharts.forEach(c => c.destroy());
    modalCharts = [];

    const res = await fetch(`/api/customers/${customerId}`);
    const data = await res.json();
    if (data.error) { document.getElementById('overviewContent').innerHTML = `<div style="color:var(--danger);padding:20px">${data.error}</div>`; return; }

    renderOverviewTab(data);
    renderOrdersTab(data);
    renderAnalysisTab(data, customerId);
    renderPredictionsTab(data);
}

function closeModal() {
    document.getElementById('customerModal').style.display = 'none';
    document.body.style.overflow = '';
    modalCharts.forEach(c => c.destroy());
    modalCharts = [];
}

// Click outside to close
document.getElementById('customerModal').addEventListener('click', e => {
    if (e.target === document.getElementById('customerModal')) closeModal();
});

// Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
});

// ─── Tab 1: Overview ──────────────────────────────────────────────────────────
function renderOverviewTab(data) {
    const c = data.customer;
    const rate = parseFloat(c.overall_return_rate || 0);
    const color = rate > 0.25 ? 'var(--danger)' : rate > 0.10 ? 'var(--warning)' : 'var(--success)';
    const pctVal = (rate * 100).toFixed(1);

    const rows = [
        ['Customer ID', `<code>${c.customer_id}</code>`],
        ['City', c.city], ['State', c.state], ['Pincode', c.pincode],
        ['Tenure', `${c.customer_tenure_days} days`],
        ['Total Orders', c.total_orders], ['Total Returns', c.total_returns],
        ['Return Rate', `<strong style="color:${color}">${pctVal}%</strong>`],
        ['Avg Order Value', inr(Math.round(c.avg_order_value || 0))],
        ['Avg Days Between Orders', `${c.avg_days_between_orders} days`],
        ['Last Order', `${c.last_order_days_ago} days ago`],
        ['Preferred Category', c.preferred_category],
        ['Frequent Return Flag', c.frequent_return_flag ? '<span class="badge badge-high">YES</span>' : '<span class="badge badge-low">✓ NO</span>']
    ];

    document.getElementById('overviewContent').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 220px;gap:24px;align-items:start;">
            <div class="table-wrap">
                <table>
                    <tbody>
                        ${rows.map(([k, v]) => `<tr><td style="color:var(--text-muted);font-weight:500;">${k}</td><td>${v}</td></tr>`).join('')}
                    </tbody>
                </table>
            </div>
            <div style="text-align:center;">
                <div style="font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Return Rate</div>
                <svg viewBox="0 0 200 110" width="200" height="110">
                    <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#E2E8F0" stroke-width="12" stroke-linecap="round"/>
                    <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="${color}" stroke-width="12" stroke-linecap="round"
                          stroke-dasharray="251" stroke-dashoffset="${251 - (rate * 251)}"/>
                    <text x="100" y="88" text-anchor="middle" font-size="22" font-weight="700" fill="${color}">${pctVal}%</text>
                    <text x="100" y="104" text-anchor="middle" font-size="10" fill="#94A3B8">Return Rate</text>
                </svg>
                <div style="margin-top:8px;">${c.preferred_category ? `<span class="badge badge-blue">${c.preferred_category}</span>` : ''}</div>
                ${c.frequent_return_flag ? '<div class="badge badge-high" style="margin-top:8px;">High Frequency Returner</div>' : ''}
            </div>
        </div>`;
}

// ─── Tab 2: Order History ─────────────────────────────────────────────────────
function renderOrdersTab(data) {
    const orders = data.order_history;
    if (!orders || orders.length === 0) {
        document.getElementById('ordersContent').innerHTML = '<div style="padding:20px;color:var(--text-muted);">No orders found.</div>';
        return;
    }
    const rows = orders.map(o => `
        <tr>
            <td><code>${o.order_id}</code></td>
            <td>${o.order_date || '-'}</td>
            <td>${o.quantity}</td>
            <td>${pct(o.discount_percentage)}</td>
            <td>${o.payment_method}</td>
            <td>${o.product_name}</td>
            <td>${o.category}</td>
            <td>${o.is_returned ? '<span class="returned-yes">✓</span>' : '<span class="returned-no">✗</span>'}</td>
            <td style="font-size:11px;color:var(--text-muted);">${o.return_reason || '-'}</td>
        </tr>`).join('');

    document.getElementById('ordersContent').innerHTML = `
        <div class="table-wrap">
            <table>
                <thead><tr><th>Order ID</th><th>Date</th><th>Qty</th><th>Disc%</th><th>Payment</th><th>Product</th><th>Category</th><th>Returned</th><th>Reason</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

// ─── Tab 3: Return Analysis ────────────────────────────────────────────────────
function renderAnalysisTab(data, customerId) {
    const reasons = data.return_reasons || [];
    const catReturns = data.category_returns || [];
    const orders = data.order_history || [];
    const totalOrders = orders.length;
    const totalReturns = orders.filter(o => o.is_returned).length;
    
    // Check if cleanly no returns
    if (totalReturns === 0 || catReturns.length === 0) {
        document.getElementById('analysisContent').innerHTML = `
            <div style="padding:40px;text-align:center;color:var(--text-muted);">
                <div style="font-size:16px;font-weight:600;color:var(--text-primary);letter-spacing:0.5px;">NO RETURNS RECORED</div>
                <div style="margin-top:8px;font-size:13px;line-height:1.6;">This profile has maintained a 100% success rate across all ${totalOrders} historical orders.</div>
            </div>`;
        return;
    }

    const topReason = reasons.length > 0 ? reasons.reduce((a, b) => a.cnt > b.cnt ? a : b).return_reason : 'N/A';
    const topCat = catReturns.length > 0 ? catReturns.reduce((a, b) => a.returns > b.returns ? a : b).category : 'N/A';

    document.getElementById('analysisContent').innerHTML = `
        <div style="padding:16px;background:var(--canvas-bg);border-radius:8px;margin-bottom:16px;font-size:13px;color:var(--text-muted);line-height:1.8;">
            This customer has returned <strong>${totalReturns}</strong> of <strong>${totalOrders}</strong> orders.
            Most common reason: <strong>${topReason}</strong>.
            Highest-frequency returned category: <strong class="badge badge-high">${topCat}</strong>.
        </div>
        <div>
            <div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase;">Volume of Returns by Category</div>
            <div style="position:relative;height:300px;">
                <canvas id="modalCatChart"></canvas>
            </div>
        </div>`;

    // Category volume bar with custom tooltip parsing
    const ctx = document.getElementById('modalCatChart');
    if (ctx) {
        modalCharts.push(new Chart(ctx, {
            type: 'bar',
            data: {
                labels: catReturns.map(r => r.category),
                datasets: [{
                    label: 'Items Returned',
                    data: catReturns.map(r => r.returns),
                    backgroundColor: catReturns.map(r => r.returns >= 3 ? '#DC2626' : r.returns === 2 ? '#D97706' : '#059669'),
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true, 
                maintainAspectRatio: false,
                scales: { 
                    y: { 
                        beginAtZero: true, 
                        ticks: { stepSize: 1 }, 
                        grid: { color: '#F1F5F9' } 
                    } 
                },
                plugins: { 
                    legend: { display: false }, 
                    tooltip: { 
                        callbacks: { 
                            afterBody: (context) => {
                                const idx = context[0].dataIndex;
                                const items = catReturns[idx].products;
                                let lines = ['\nProducts Returned:'];
                                for (const [product, count] of Object.entries(items)) {
                                    lines.push(`• ${product} (x${count})`);
                                }
                                return lines;
                            }
                        } 
                    } 
                }
            }
        }));
    }
}

// ─── Tab 4: Predictions ────────────────────────────────────────────────────────
function renderPredictionsTab(data) {
    const preds = data.predictions || [];
    if (preds.length === 0) {
        document.getElementById('predictionsContent').innerHTML = '<div style="padding:20px;color:var(--text-muted);">No predictions saved for this customer.</div>';
        return;
    }

    const realPreds = preds.filter(p => p.correct !== 'N/A');
    const correct = realPreds.filter(p => p.correct === true).length;
    const accuracy = realPreds.length > 0 ? ((correct / realPreds.length) * 100).toFixed(1) : '-';

    const rows = preds.map(p => {
        const correctBadge = p.correct === 'N/A' 
            ? '<span class="badge badge-gray">-</span>'
            : (p.correct ? '<span class="badge badge-low">✓ Correct</span>' : '<span class="badge badge-high">✗ Wrong</span>');
            
        const isRetBadge = p.actual_shipped === 'Simulation Log'
            ? '<span class="badge badge-gray" style="font-size:11px;">Simulated</span>'
            : (p.actual_shipped === 'Yes' ? '<span class="returned-yes">✓</span>' : '<span class="returned-no">✗</span>');
            
        // Risk tier badge parsing mapped dynamically based on new english names
        let tierClass = 'badge-gray';
        const t = p.risk_tier || '';
        if (t.includes('Allow')) tierClass = 'badge-low';
        else if (t.includes('Restrict') || t.includes('Avoid') || t.includes('Warning') || t.includes('Standard')) tierClass = 'badge-medium';
        else if (t.includes('Block') || t.includes('Require')) tierClass = 'badge-high';
            
        return `<tr>
            <td><code>${p.order_id}</code></td>
            <td>${p.product_name}</td>
            <td>${p.predicted_pct !== null ? p.predicted_pct + '%' : '-'}</td>
            <td>${t ? `<span class="badge ${tierClass}">${t}</span>` : '-'}</td>
            <td>${isRetBadge}</td>
            <td>${correctBadge}</td>
        </tr>`;
    }).join('');

    document.getElementById('predictionsContent').innerHTML = `
        <div style="padding:12px 16px;background:var(--canvas-bg);border-radius:8px;margin-bottom:16px;font-size:13px;color:var(--text-muted);">
            Real Order Historical Accuracy: <strong>${correct}</strong> correct of <strong>${realPreds.length}</strong> real predictions - <strong style="color:var(--primary)">${accuracy}% accuracy</strong>.
            <br><span style="color:var(--text-muted);font-size:11px;margin-top:4px;display:inline-block;">Showing ${preds.length - realPreds.length} Simulated logs.</span>
        </div>
        <div class="table-wrap">
            <table>
                <thead><tr><th>Order ID</th><th>Product</th><th>Predicted %</th><th>Risk Tier</th><th>Returned</th><th>Prediction</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

// ─── Init ─────────────────────────────────────────────────────────────────────
fetchCustomers();
