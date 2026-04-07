// ─── Utilities ─────────────────────────────────────────────────────────────────
const inr = n => '₹' + Number(n).toLocaleString('en-IN');
const pct = n => Number(n).toFixed(1) + '%';

const RISK_COLORS = {
    LOW: '#10B981',    // Vibrant Emerald
    MEDIUM: '#F59E0B', // Vibrant Amber
    HIGH: '#EF4444'    // Vibrant Crimson
};

function riskColor(rate) {
    if (rate > 25) return RISK_COLORS.HIGH;
    if (rate > 10) return RISK_COLORS.MEDIUM;
    return RISK_COLORS.LOW;
}

function riskBadge(tier) {
    const cls = { LOW: 'badge-low', MEDIUM: 'badge-medium', HIGH: 'badge-high' }[tier] || 'badge-gray';
    return `<span class="badge ${cls}">${tier || 'N/A'}</span>`;
}

// ─── ApexCharts Globals ────────────────────────────────────────────────────────
const apexDefaults = {
    chart: {
        fontFamily: 'Inter, sans-serif',
        toolbar: { show: false },
        zoom: { enabled: true },
        background: 'transparent'
    },
    colors: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'],
    grid: {
        borderColor: '#F1F5F9',
        strokeDashArray: 4
    },
    stroke: {
        curve: 'smooth',
        width: 2
    },
    dataLabels: {
        enabled: false
    },
    tooltip: {
        theme: 'dark',
        style: {
            fontSize: '12px',
            fontFamily: 'Inter, sans-serif'
        },
        y: {
            formatter: (val) => val.toLocaleString('en-IN')
        }
    }
};

// ─── KPIs ──────────────────────────────────────────────────────────────────────
async function loadKPIs() {
    try {
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
        
        loadHeatmap();
    } catch (e) { console.error("KPI Load Error:", e); }
}

// ─── Heatmap ───────────────────────────────────────────────────────────────────
async function loadHeatmap() {
    const segments = ['zero', 'low', 'medium', 'high'];
    for (const seg of segments) {
        try {
            const r = await fetch(`/api/customers?segment=${seg}&page=1`);
            const d = await r.json();
            document.getElementById(`seg-${seg}`).textContent = d.total + ' customers';
            const aov = d.rows.length > 0
                ? inr(Math.round(d.rows.reduce((a, c) => a + Number(c.avg_order_value || 0), 0) / d.rows.length))
                : '-';
            document.getElementById(`seg-${seg}-aov`).textContent = 'Avg OV: ' + aov;
        } catch (e) { console.error(`Segment ${seg} Load Error:`, e); }
    }
}

// ─── Model Report ──────────────────────────────────────────────────────────────
async function loadModelReport() {
    try {
        const res = await fetch('/api/model-report');
        const d = await res.json();
        document.getElementById('roi-auc').textContent = d['ROC-AUC'] || '-';
        document.getElementById('roi-recall').textContent = d['Recall'] || '-';
        document.getElementById('roi-precision').textContent = d['Precision'] || '-';
    } catch (e) { console.error("Model Report Load Error:", e); }
}

// ─── Charts ────────────────────────────────────────────────────────────────────

// Chart 1 - Return Overview (Donut)
async function loadChartReturnOverview() {
    const res = await fetch('/api/charts/return-overview');
    const d = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [d.returned, d.not_returned],
        chart: { ...apexDefaults.chart, type: 'donut', height: 280 },
        labels: ['Returned', 'Not Returned'],
        colors: [RISK_COLORS.HIGH, RISK_COLORS.LOW],
        plotOptions: {
            pie: {
                donut: {
                    size: '70%',
                    labels: {
                        show: true,
                        total: {
                            show: true,
                            label: 'Total Orders',
                            formatter: () => (d.returned + d.not_returned).toLocaleString('en-IN')
                        }
                    }
                }
            }
        },
        legend: { position: 'bottom' }
    };

    const chart = new ApexCharts(document.querySelector("#chartReturnOverview"), options);
    chart.render();
}

// Chart 2 - Return by Payment (Bar)
async function loadChartReturnByPayment() {
    const res = await fetch('/api/charts/return-by-payment');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [{
            name: 'Return Rate %',
            data: data.map(d => d.rate)
        }],
        chart: { ...apexDefaults.chart, type: 'bar', height: 280 },
        plotOptions: {
            bar: {
                borderRadius: 4,
                distributed: true,
                columnWidth: '50%'
            }
        },
        xaxis: {
            categories: data.map(d => d.method)
        },
        yaxis: {
            labels: { formatter: v => v + '%' },
            max: 100
        },
        colors: data.map(d => riskColor(d.rate)),
        legend: { show: false }
    };

    const chart = new ApexCharts(document.querySelector("#chartReturnByPayment"), options);
    chart.render();
}

// Chart 3 - Return by Delay
async function loadChartReturnByDelay() {
    const res = await fetch('/api/charts/return-by-delay');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [
            { name: 'Returned', data: data.map(d => d.returned) },
            { name: 'Not Returned', data: data.map(d => d.not_returned) }
        ],
        chart: { ...apexDefaults.chart, type: 'bar', height: 280, stacked: true },
        xaxis: {
            categories: data.map(d => `Delay: ${d.delivery_delay}d`)
        },
        colors: [RISK_COLORS.HIGH, RISK_COLORS.LOW],
        legend: { position: 'top' }
    };

    const chart = new ApexCharts(document.querySelector("#chartReturnByDelay"), options);
    chart.render();
}

// Chart 4 - Return by Category
async function loadChartReturnByCategory() {
    const res = await fetch('/api/charts/return-by-category');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [{
            name: 'Return Rate %',
            data: data.map(d => d.rate)
        }],
        chart: { ...apexDefaults.chart, type: 'bar', height: 280 },
        plotOptions: {
            bar: {
                borderRadius: 4,
                horizontal: true,
                distributed: true,
                barHeight: '60%'
            }
        },
        xaxis: {
            categories: data.map(d => d.category),
            labels: { formatter: v => v + '%' },
            max: 100
        },
        colors: data.map(d => riskColor(d.rate)),
        legend: { show: false }
    };

    const chart = new ApexCharts(document.querySelector("#chartReturnByCategory"), options);
    chart.render();
}

// Chart 5 - Orders by City
async function loadChartOrdersByCity() {
    const res = await fetch('/api/charts/orders-by-city');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [{
            name: 'Order Count',
            data: data.map(d => d.total)
        }],
        chart: { ...apexDefaults.chart, type: 'bar', height: 280 },
        plotOptions: {
            bar: { borderRadius: 4, columnWidth: '50%' }
        },
        xaxis: {
            categories: data.map(d => d.delivery_city),
            labels: { rotate: -45, hideOverlappingLabels: false }
        },
        colors: ['#3B82F6']
    };

    const chart = new ApexCharts(document.querySelector("#chartOrdersByCity"), options);
    chart.render();
}

// Chart 6 - City Stacked
async function loadChartCityStacked() {
    const res = await fetch('/api/charts/city-stacked');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [
            { name: 'Returned', data: data.map(d => d.returned) },
            { name: 'Not Returned', data: data.map(d => d.not_returned) }
        ],
        chart: { ...apexDefaults.chart, type: 'bar', height: 280, stacked: true },
        xaxis: {
            categories: data.map(d => d.delivery_city),
            labels: { rotate: -45, hideOverlappingLabels: false }
        },
        colors: [RISK_COLORS.HIGH, RISK_COLORS.LOW],
        legend: { position: 'top' }
    };

    const chart = new ApexCharts(document.querySelector("#chartCityStacked"), options);
    chart.render();
}

// Chart 7 - Product Return Rate
async function loadChartProductReturnRate() {
    const res = await fetch('/api/charts/product-return-rate');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: [{
            name: 'Return Rate %',
            data: data.map(d => d.rate)
        }],
        chart: { ...apexDefaults.chart, type: 'bar', height: 280 },
        plotOptions: {
            bar: { borderRadius: 4, distributed: true }
        },
        xaxis: {
            categories: data.map(d => d.product_name.length > 16 ? d.product_name.substring(0, 16) + '…' : d.product_name),
            labels: { rotate: -45, hideOverlappingLabels: false, style: { fontSize: '10px' } },
            tooltip: { enabled: true }
        },
        yaxis: { max: 100, labels: { formatter: v => v + '%' } },
        colors: data.map(d => riskColor(d.rate)),
        legend: { show: false }
    };

    const chart = new ApexCharts(document.querySelector("#chartProductReturnRate"), options);
    chart.render();
}

// Chart 8 - Return Reasons
async function loadChartReturnReasons() {
    const res = await fetch('/api/charts/return-reasons');
    const data = await res.json();
    
    const options = {
        ...apexDefaults,
        series: data.map(d => d.cnt),
        chart: { ...apexDefaults.chart, type: 'pie', height: 280 },
        labels: data.map(d => d.return_reason),
        colors: ['#EF4444', '#F59E0B', '#3B82F6', '#10B981', '#8B5CF6', '#EC4899'],
        legend: { position: 'bottom' }
    };

    const chart = new ApexCharts(document.querySelector("#chartReturnReasons"), options);
    chart.render();
}

// ─── Courier Performance ───────────────────────────────────────────────────────
async function loadCourierTable() {
    try {
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
    } catch (e) { console.error("Courier Table Error:", e); }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
(async () => {
    await loadKPIs();
    await loadModelReport();
    await Promise.all([
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
