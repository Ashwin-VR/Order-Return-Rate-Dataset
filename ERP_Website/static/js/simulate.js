// ─── Utilities ─────────────────────────────────────────────────────────────────
const inr = n => '₹' + Number(n).toLocaleString('en-IN');
const pct = n => Number(n).toFixed(1) + '%';

function riskBadge(tier, large = false) {
    let cls = 'badge-gray';
    if (!tier) return `<span class="badge ${cls}" style="${large ? 'font-size:18px;padding:8px 20px;' : ''}">N/A</span>`;
    
    if (tier.includes('Allow')) cls = 'badge-low';
    else if (tier.includes('Restrict') || tier.includes('Avoid') || tier.includes('Warning') || tier.includes('Standard')) cls = 'badge-medium';
    else if (tier.includes('Block') || tier.includes('Require')) cls = 'badge-high';
    
    const style = large ? 'font-size:18px;padding:8px 20px;' : '';
    return `<span class="badge ${cls}" style="${style}">${tier}</span>`;
}

function showToast(msg, type = 'success') {
    const tc = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span>${type === 'success' ? '' : ''}</span> ${msg}`;
    tc.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

const cityPincodePrefixes = {
    'Mumbai': '400',
    'Delhi': '110',
    'Bengaluru': '560',
    'Hyderabad': '500',
    'Chennai': '600',
    'Pune': '411',
    'Kolkata': '700',
    'Ahmedabad': '380'
};

function enforcePincode(cityInputId, pincodeInputId) {
    const city = document.getElementById(cityInputId).value;
    const pinInput = document.getElementById(pincodeInputId);
    const expectedPrefix = cityPincodePrefixes[city] || '';
    
    if (expectedPrefix && !pinInput.value.startsWith(expectedPrefix)) {
        pinInput.value = expectedPrefix + '001';
    }
}

// ─── Order Hour Label ──────────────────────────────────────────────────────────
const hourSlider = document.getElementById('orderHour');
const hourLabel = document.getElementById('orderHourLabel');

function getHourLabel(h) {
    h = parseInt(h);
    if (h >= 5 && h < 12) return `${h} (Morning)`;
    if (h >= 12 && h < 17) return `${h} (Afternoon)`;
    if (h >= 17 && h < 21) return `${h} (Evening)`;
    return `${h} (Night)`;
}

hourSlider.addEventListener('input', () => {
    hourLabel.textContent = getHourLabel(hourSlider.value);
    schedulePredict();
});

// ─── Gauge Update ──────────────────────────────────────────────────────────────
// Gauge UI removed in favor of structured text feedback

// ─── Load Dropdowns ────────────────────────────────────────────────────────────
async function loadDropdowns() {
    const pRes = await fetch('/api/products/dropdown');
    const products = await pRes.json();

    const pSel = document.getElementById('productId');
    products.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.product_id;
        opt.textContent = `${p.product_id} - ${p.product_name} (${p.category}, ₹${Number(p.price).toLocaleString('en-IN')})`;
        pSel.appendChild(opt);
    });
}

// ─── Form Data ─────────────────────────────────────────────────────────────────
function getFormData() {
    return {
        customer_id: document.getElementById('customerId').value,
        product_id: document.getElementById('productId').value,
        quantity: document.getElementById('quantity').value,
        discount_percentage: document.getElementById('discountPct').value,
        payment_method: document.getElementById('paymentMethod').value,
        shipping_mode: document.getElementById('shippingMode').value,
        courier_partner: document.getElementById('courierPartner').value,
        warehouse_city: document.getElementById('warehouseCity').value,
        delivery_city: document.getElementById('deliveryCity').value,
        source_pincode: document.getElementById('sourcePincode').value,
        dest_pincode: document.getElementById('destPincode').value,
        order_hour: document.getElementById('orderHour').value
    };
}

// ─── Live Prediction (debounced) ───────────────────────────────────────────────
let debounceTimer = null;

function schedulePredict() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runLivePredict, 400);
}

async function runLivePredict() {
    const form = getFormData();
    if (!form.customer_id || !form.product_id) return;
    try {
        const res = await fetch('/api/predict-live', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(form)
        });
        const d = await res.json();
        // Removed live predict gauge update
    } catch (e) {
        console.warn('Live predict error:', e);
    }
}

// Attach live update to all form fields
['customerId', 'productId', 'quantity', 'discountPct', 'paymentMethod',
    'shippingMode', 'courierPartner', 'deliveryCity', 'warehouseCity', 'sourcePincode', 'destPincode'].forEach(id => {
        document.getElementById(id).addEventListener('change', schedulePredict);
        document.getElementById(id).addEventListener('input', schedulePredict);
    });

document.getElementById('warehouseCity').addEventListener('change', () => enforcePincode('warehouseCity', 'sourcePincode'));
document.getElementById('deliveryCity').addEventListener('change', () => enforcePincode('deliveryCity', 'destPincode'));

// ─── Full Simulation ───────────────────────────────────────────────────────────
document.getElementById('simulateBtn').addEventListener('click', async () => {
    const form = getFormData();
    if (!form.customer_id || !form.product_id) {
        showToast('Please select a Customer and Product.', 'error');
        return;
    }

    const btn = document.getElementById('simulateBtn');
    const btnText = document.getElementById('simulateBtnText');
    btn.disabled = true;
    btnText.innerHTML = '<div class="spinner"></div> Running...';

    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(form)
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        renderResult(data, form);
    } catch (e) {
        showToast('Simulation error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Run Simulation →';
    }
});

// ─── Render Result ─────────────────────────────────────────────────────────────
function renderResult(data, form) {
    const pred = data.prediction;
    const history = data.customer_history;
    const actions = data.erp_actions;
    const cust = data.customer_data;
    const prod = data.product_data;

    

    const panel = document.getElementById('resultPanel');

    // Section A - Risk Summary
    const prob = pred.predicted_prob;
    const tierColor = prob > 0.50 ? 'var(--danger)' : prob > 0.20 ? 'var(--warning)' : 'var(--success)';
    
    // Qualitative Driver Rendering
    const driverHtml = pred.top_drivers.map(d => {
        let labelHtml = '';
        if (d.courier_label) {
            const labelCls = d.courier_label.includes('Low') ? 'badge-low' : d.courier_label.includes('Moderate') ? 'badge-medium' : 'badge-high';
            labelHtml = `<span class="badge ${labelCls}" style="margin-left:8px;font-size:10px;">${d.courier_label}</span>`;
        }
        if (d.is_long_distance) {
            labelHtml = `<span class="badge badge-high" style="margin-left:8px;font-size:10px;">Long Distance</span>`;
        }

        return `
            <div class="driver-card" style="border-left:3px solid var(--primary);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <div class="driver-name" style="margin-bottom:0;">${d.feature}</div>
                    ${labelHtml}
                </div>
                <div class="driver-bar-wrap">
                    <div class="driver-bar" style="width:${Math.min(d.importance * 100, 100)}%;"></div>
                </div>
                <div class="driver-explanation">${d.explanation}</div>
            </div>
        `;
    }).join('');

    // Section B - History
    let historyHtml = '';
    if (history && history.length > 0) {
        const rows = history.map(h => `
            <tr>
                <td><code>${h.order_id}</code></td>
                <td>${h.order_date ? String(h.order_date).slice(0, 10) : '-'}</td>
                <td>${h.quantity}</td>
                <td>${pct(h.discount_percentage)}</td>
                <td>${h.payment_method}</td>
                <td>${h.is_returned ? '<span class="returned-yes">Yes</span>' : '<span class="returned-no">No</span>'}</td>
                <td>${h.return_reason || '-'}</td>
            </tr>
        `).join('');
        historyHtml = `
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Order ID</th><th>Date</th><th>Qty</th><th>Disc%</th><th>Payment</th><th>Returned</th><th>Return Reason</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    } else {
        historyHtml = `<div style="padding:16px;color:var(--text-muted);font-size:13px;background:var(--canvas-bg);border-radius:8px;">
            No prior orders for this customer–product combination - using category-level patterns.
        </div>`;
    }

    // Section C - Actions
    const actionHtml = actions.map(a => `
        <div class="action-card">
            <div class="action-header">
                <span class="action-icon">${a.icon}</span>
                <span class="action-title">${a.title}</span>
            </div>
            <div class="action-rationale">${a.rationale}</div>
            <div class="action-trigger">${a.trigger}</div>
        </div>
    `).join('');

    // Save button payload
    const orderId = `SIM-${Date.now()}`;
    const savePayload = JSON.stringify({
        customer_id: form.customer_id,
        product_id: form.product_id,
        order_id: orderId,
        predicted_prob: pred.predicted_prob,
        risk_tier: pred.risk_tier,
        top_drivers: pred.top_drivers,
        action_flags: actions.map(a => a.title).join(', ')
    });

    panel.innerHTML = `
        <div class="risk-report">
            <!-- Section A -->
            <div class="card">
                <div class="risk-section-title">A - Risk Summary</div>
                <div style="display:flex;align-items:center;gap:20px;margin-bottom:16px;flex-wrap:wrap;">
                    <div style="font-size:48px;font-weight:700;color:${tierColor};line-height:1;">${pct(pred.predicted_pct)}</div>
                    ${riskBadge(pred.risk_tier, true)}
                </div>
                <div class="risk-section-title" style="margin-bottom:8px;">Top Return Risk Drivers</div>
                <div class="driver-cards">${driverHtml}</div>
            </div>

            <!-- Section B -->
            <div class="card">
                <div class="risk-section-title">B - Customer × Product History</div>
                ${historyHtml}
            </div>

            <!-- Section C -->
            <div class="card">
                <div class="risk-section-title">C - ERP Action Recommendations</div>
                ${actionHtml}
            </div>

            <!-- Section D -->
            <div class="card">
                <div class="risk-section-title">D - Log Prediction to Oracle</div>
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                    <div style="font-size:12px;color:var(--text-muted);">
                        Save this prediction to <code>order_predictions</code> table with ID <code>${orderId}</code>
                    </div>
                    <button class="btn btn-primary btn-sm" id="savePredBtn" data-payload='${savePayload}'>
                        Log Prediction
                    </button>
                </div>
            </div>
        </div>
    `;

    // Save handler
    document.getElementById('savePredBtn').addEventListener('click', async function () {
        const payload = JSON.parse(this.dataset.payload);
        this.disabled = true;
        this.textContent = 'Saving...';
        try {
            const res = await fetch('/api/save-prediction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if (d.success) {
                showToast('Prediction saved to Oracle successfully!');
                this.textContent = 'Saved';
            } else {
                throw new Error(d.error);
            }
        } catch (e) {
            showToast('Save failed: ' + e.message, 'error');
            this.disabled = false;
            this.textContent = 'Log Prediction';
        }
    });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
loadDropdowns();
