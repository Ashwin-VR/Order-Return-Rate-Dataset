// ─── Utilities ─────────────────────────────────────────────────────────────────
const inr = n => '₹' + Number(n).toLocaleString('en-IN');
const pct = n => Number(n).toFixed(1) + '%';

const RISK_COLORS = {
    LOW: '#059669',
    MEDIUM: '#D97706',
    HIGH: '#DC2626'
};

function riskColor(rate) {
    if (rate > 30) return '#DC2626';
    if (rate > 20) return '#D97706';
    return '#059669';
}

function riskBadge(tier) {
    const cls = { LOW: 'badge-low', MEDIUM: 'badge-medium', HIGH: 'badge-high' }[tier] || 'badge-gray';
    return `<span class="badge ${cls}">${tier || 'N/A'}</span>`;
}

// ─── KPIs ──────────────────────────────────────────────────────────────────────
async function loadKPIs() {
    const res = await fetch('/api/dashboard/kpis');
    const d = await res.json();

    document.getElementById('kpi-total-orders').textContent = d.total_orders.toLocaleString('en-IN');
    document.getElementById('kpi-total-orders-sub').textContent = `${d.returned_count} returns recorded`;

    document.getElementById('kpi-return-rate').textContent = pct(d.overall_return_rate);
    document.getElementById('kpi-return-rate-sub').textContent = `${d.returned_count} of ${d.total_orders} orders`;

    document.getElementById('kpi-avg-delay').textContent = d.avg_delivery_delay + ' days';

    document.getElementById('kpi-cod-pct').textContent = pct(d.cod_pct);
    document.getElementById('kpi-cod-sub').textContent = 'Cash on delivery orders';

    document.getElementById('kpi-high-risk').textContent = d.high_risk_orders.toLocaleString('en-IN');

    
    // Heatmap segments
    loadHeatmap();
}

// ─── Heatmap (customer segments from /api/customers) ──────────────────────────
async function loadHeatmap() {
    // We compute segments client-side from customers API
    const res = await fetch('/api/customers?page=1');
    const data = await res.json();
    // Fetch all with large page is not ideal; use summary logic
    // Instead use separate calls with segment filter
    const segments = ['zero', 'low', 'medium', 'high'];
    for (const seg of segments) {
        const r = await fetch(`/api/customers?segment=${seg}&page=1`);
        const d = await r.json();
        document.getElementById(`seg-${seg}`).textContent = d.total + ' customers';
        const aov = d.rows.length > 0
            ? inr(Math.round(d.rows.reduce((a, c) => a + Number(c.avg_order_value || 0), 0) / d.rows.length))
            : '-';
        document.getElementById(`seg-${seg}-aov`).textContent = 'Avg OV: ' + aov;
    }
}

// ─── Model Report ──────────────────────────────────────────────────────────────
async function loadModelReport() {
    const res = await fetch('/api/model-report');
    const d = await res.json();
    document.getElementById('roi-auc').textContent = d['ROC-AUC'] || '-';
    document.getElementById('roi-recall').textContent = d['Recall'] || '-';
    document.getElementById('roi-precision').textContent = d['Precision'] || '-';
}

// ─── Chart Helpers ──────────────────────────────────────────────────────────────
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { labels: { color: '#94A3B8', font: { family: 'Inter', size: 11, weight: 500 } } }
    },
    scales: {
        x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
            ticks: { color: '#94A3B8', font: { family: 'Inter', size: 10 } }
        },
        y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
            ticks: { color: '#94A3B8', font: { family: 'Inter', size: 10 } }
        }
    }
};

// Chart 1 - Return Overview (Donut)
async function loadChartReturnOverview() {
    const res = await fetch('/api/charts/return-overview');
    const d = await res.json();
    const total = d.returned + d.not_returned;
    new Chart(document.getElementById('chartReturnOverview'), {
        type: 'doughnut',
        data: {
            labels: ['Returned', 'Not Returned'],
            datasets: [{ data: [d.returned, d.not_returned], backgroundColor: ['#DC2626', '#059669'], borderWidth: 0 }]
        },
        options: {
            ...chartDefaults,
            plugins: {
                ...chartDefaults.plugins,
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.label}: ${ctx.parsed.toLocaleString('en-IN')} (${pct(ctx.parsed / total * 100)})`
                    }
                }
            },
            cutout: '60%'
        },
        plugins: [{
            id: 'centerText',
            beforeDraw(chart) {
                const { ctx, chartArea: { top, bottom, left, right } } = chart;
                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                const cx = (left + right) / 2;
                const cy = (top + bottom) / 2;
                ctx.font = 'bold 22px Outfit, sans-serif';
                ctx.fillStyle = '#0F172A';
                ctx.fillText(total.toLocaleString('en-IN'), cx, cy - 8);
                ctx.font = '600 11px Inter, sans-serif';
                ctx.fillStyle = '#64748B';
                ctx.fillText('Total Orders', cx, cy + 12);
                ctx.restore();
            }
        }]
    });
}

// Chart 2 - Return by Payment (Vertical Bar)
async function loadChartReturnByPayment() {
    const res = await fetch('/api/charts/return-by-payment');
    const data = await res.json();
    new Chart(document.getElementById('chartReturnByPayment'), {
        type: 'bar',
        data: {
            labels: data.map(d => d.method),
            datasets: [{
                label: 'Return Rate %',
                data: data.map(d => d.rate),
                backgroundColor: data.map(d => riskColor(d.rate)),
                borderRadius: 6
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: { min: 0, max: 100, ticks: { callback: v => v + '%' }, grid: { color: '#F1F5F9' } }
            },
            plugins: { ...chartDefaults.plugins, tooltip: { callbacks: { label: ctx => pct(ctx.parsed.y) } } }
        }
    });
}

// Chart 3 - Return by Delay (Grouped Bar)
async function loadChartReturnByDelay() {
    const res = await fetch('/api/charts/return-by-delay');
    const data = await res.json();
    new Chart(document.getElementById('chartReturnByDelay'), {
        type: 'bar',
        data: {
            labels: data.map(d => `Delay: ${d.delivery_delay}d`),
            datasets: [
                { label: 'Returned', data: data.map(d => d.returned), backgroundColor: '#DC2626', borderRadius: 4 },
                { label: 'Not Returned', data: data.map(d => d.not_returned), backgroundColor: '#059669', borderRadius: 4 }
            ]
        },
        options: {
            ...chartDefaults,
            scales: { y: { grid: { color: '#F1F5F9' } } }
        }
    });
}

// Chart 4 - Return by Category (Horizontal Bar)
async function loadChartReturnByCategory() {
    const res = await fetch('/api/charts/return-by-category');
    const data = await res.json();
    new Chart(document.getElementById('chartReturnByCategory'), {
        type: 'bar',
        data: {
            labels: data.map(d => d.category),
            datasets: [{
                label: 'Return Rate %',
                data: data.map(d => d.rate),
                backgroundColor: data.map(d => riskColor(d.rate)),
                borderRadius: 6
            }]
        },
        options: {
            ...chartDefaults,
            indexAxis: 'y',
            scales: {
                x: { min: 0, max: 100, ticks: { callback: v => v + '%' }, grid: { color: '#F1F5F9' } }
            },
            plugins: { ...chartDefaults.plugins, tooltip: { callbacks: { label: ctx => pct(ctx.parsed.x) } } }
        }
    });
}

// Chart 5 - Orders by City (Vertical Bar)
async function loadChartOrdersByCity() {
    const res = await fetch('/api/charts/orders-by-city');
    const data = await res.json();
    new Chart(document.getElementById('chartOrdersByCity'), {
        type: 'bar',
        data: {
            labels: data.map(d => d.delivery_city),
            datasets: [{
                label: 'Order Count',
                data: data.map(d => d.total),
                backgroundColor: '#0F172A',
                borderRadius: 8
            }]
        },
        options: {
            ...chartDefaults,
            scales: { y: { grid: { color: '#F1F5F9' } } }
        }
    });
}

// Chart 6 - City Stacked
async function loadChartCityStacked() {
    const res = await fetch('/api/charts/city-stacked');
    const data = await res.json();
    new Chart(document.getElementById('chartCityStacked'), {
        type: 'bar',
        data: {
            labels: data.map(d => d.delivery_city),
            datasets: [
                { label: 'Not Returned', data: data.map(d => d.not_returned), backgroundColor: '#059669', borderRadius: 0 },
                { label: 'Returned', data: data.map(d => d.returned), backgroundColor: '#DC2626', borderRadius: 0 }
            ]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: { stacked: true, grid: { color: '#F1F5F9' } },
                x: { stacked: true }
            }
        }
    });
}

// Chart 7 - Product Return Rate
async function loadChartProductReturnRate() {
    const res = await fetch('/api/charts/product-return-rate');
    const data = await res.json();
    const labels = data.map(d => d.product_name.length > 16 ? d.product_name.substring(0, 16) + '…' : d.product_name);
    new Chart(document.getElementById('chartProductReturnRate'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Return Rate %',
                data: data.map(d => d.rate),
                backgroundColor: data.map(d => riskColor(d.rate)),
                borderRadius: 6
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: { min: 0, max: 100, ticks: { callback: v => v + '%' }, grid: { color: '#F1F5F9' } }
            },
            plugins: {
                ...chartDefaults.plugins, tooltip: {
                    callbacks: {
                        title: (items) => data[items[0].dataIndex].product_name,
                        label: ctx => pct(ctx.parsed.y)
                    }
                }
            }
        }
    });
}

// Chart 8 - Return Reasons (Pie)
async function loadChartReturnReasons() {
    const res = await fetch('/api/charts/return-reasons');
    const data = await res.json();
    const palette = ['#DC2626', '#D97706', '#0F172A', '#D4AF37', '#059669', '#6366F1'];
    const total = data.reduce((a, d) => a + d.cnt, 0);
    new Chart(document.getElementById('chartReturnReasons'), {
        type: 'pie',
        data: {
            labels: data.map(d => d.return_reason),
            datasets: [{ data: data.map(d => d.cnt), backgroundColor: palette, borderWidth: 2 }]
        },
        options: {
            ...chartDefaults,
            plugins: {
                ...chartDefaults.plugins,
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.label}: ${ctx.parsed} (${pct(ctx.parsed / total * 100)})`
                    }
                }
            }
        }
    });
}

// ─── Courier Performance Table ─────────────────────────────────────────────────
async function loadCourierTable() {
    const res = await fetch('/api/charts/courier-performance');
    const data = await res.json();
    const tbody = document.getElementById('courierTableBody');
    tbody.innerHTML = data.map(row => `
        <tr>
            <td><strong>${row.courier_partner}</strong></td>
            <td>${Number(row.total_shipments).toLocaleString('en-IN')}</td>
            <td>${pct(row.avg_delay_rate * 100)}</td>
            <td>${row.avg_delivery_days} days</td>
            <td>${pct(row.on_time_pct)}</td>
            <td>${riskBadge(row.risk_level)}</td>
        </tr>
    `).join('');
}

// ─── Init ─────────────────────────────────────────────────────────────────────
(async () => {
    await Promise.all([
        loadKPIs(),
        loadModelReport(),
        loadChartReturnOverview(),
        loadChartReturnByPayment(),
        loadChartReturnByDelay(),
        loadChartReturnByCategory(),
        loadChartOrdersByCity(),
        loadChartCityStacked(),
        loadChartProductReturnRate(),
        loadChartReturnReasons(),
        loadCourierTable()
    ]);
})();
