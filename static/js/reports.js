document.addEventListener('DOMContentLoaded', function() {

    // Chart.js Default Config adjustments
    Chart.defaults.font.family = "inherit";
    Chart.defaults.color = '#6b778c';

    const chartData = window.chartData || {};

    /**
     * Helper function to dynamically scale X-Axis ticks based on date range length
     * keeps all daily data points intact while optimizing visual label density.
     */
    function getResponsiveXAxisTicks(labelsArray) {
        const count = labelsArray ? labelsArray.length : 0;
        return {
            autoSkip: true,
            maxTicksLimit: count > 60 ? 8 : (count > 30 ? 10 : 12),
            maxRotation: count > 30 ? 45 : 0,
            minRotation: 0,
            font: {
                size: count > 60 ? 10 : 11
            }
        };
    }

    // 1. Sales vs Purchase Line Chart
    const ctxSalesPurchase = document.getElementById('salesPurchaseChart');
    if (ctxSalesPurchase && chartData.salesPurchaseLabels && chartData.salesPurchaseLabels.length > 0) {
        new Chart(ctxSalesPurchase, {
            type: 'line',
            data: {
                labels: chartData.salesPurchaseLabels,
                datasets: [
                    {
                        label: 'Sales (₹)',
                        data: chartData.salesData || [],
                        borderColor: '#0052cc',
                        backgroundColor: 'rgba(0, 82, 204, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Purchase (₹)',
                        data: chartData.purchaseData || [],
                        borderColor: '#ffab00',
                        backgroundColor: 'rgba(255, 171, 0, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#dfe1e6' } },
                    x: {
                        grid: { display: false },
                        ticks: getResponsiveXAxisTicks(chartData.salesPurchaseLabels)
                    }
                }
            }
        });
    }

    // 2. Expense Distribution Donut Chart (Unchanged)
    const ctxExpense = document.getElementById('expenseChart');
    if (ctxExpense) {
        if (chartData.expenseValues && chartData.expenseValues.length > 0) {
            new Chart(ctxExpense, {
                type: 'doughnut',
                data: {
                    labels: chartData.expenseLabels || [],
                    datasets: [{
                        data: chartData.expenseValues || [],
                        backgroundColor: ['#0052cc', '#00b8d9', '#36b37e', '#ffab00', '#6554c0', '#de350b'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } }
                    },
                    cutout: '70%'
                }
            });
        } else {
            const container = ctxExpense.parentElement;
            container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#6b778c;font-size:12px;">No expense data available</div>';
        }
    }

    // 3. Monthly Profit Bar Chart
    const ctxProfit = document.getElementById('monthlyProfitChart');
    if (ctxProfit && chartData.profitLabels && chartData.profitLabels.length > 0) {
        new Chart(ctxProfit, {
            type: 'bar',
            data: {
                labels: chartData.profitLabels,
                datasets: [{
                    label: 'Net Profit (₹)',
                    data: chartData.profitValues || [],
                    backgroundColor: '#0052cc',
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#dfe1e6' } },
                    x: {
                        grid: { display: false },
                        ticks: getResponsiveXAxisTicks(chartData.profitLabels)
                    }
                }
            }
        });
    }

    // Filter Form Submit Spinner
    const filterForm = document.getElementById('reportFilterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', function() {
            const submitBtn = document.getElementById('generateReportBtn');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
                submitBtn.disabled = true;
            }
        });
    }

    // PDF Export Event Handler
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', function() {
            const dateFrom = document.getElementById('dateFrom') ? document.getElementById('dateFrom').value : '';
            const dateTo = document.getElementById('dateTo') ? document.getElementById('dateTo').value : '';
            const pdfUrl = `${window.pdfUrl || '/yakuza/reports/pdf/'}?date_from=${dateFrom}&date_to=${dateTo}`;
            window.location.href = pdfUrl;
        });
    }

    // Print Report Event Handler
    const printReportBtn = document.getElementById('printReportBtn');
    if (printReportBtn) {
        printReportBtn.addEventListener('click', function() {
            window.print();
        });
    }
});