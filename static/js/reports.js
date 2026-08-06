document.addEventListener('DOMContentLoaded', function() {
    
    // Set default dates for filters (Current month range)
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    
    const formatDate = (date) => {
        let d = new Date(date),
            month = '' + (d.getMonth() + 1),
            day = '' + d.getDate(),
            year = d.getFullYear();

        if (month.length < 2) month = '0' + month;
        if (day.length < 2) day = '0' + day;

        return [year, month, day].join('-');
    };

    const dateFromEl = document.getElementById('dateFrom');
    const dateToEl = document.getElementById('dateTo');

    if (dateFromEl && !dateFromEl.value) {
        dateFromEl.value = formatDate(firstDay);
    }
    if (dateToEl && !dateToEl.value) {
        dateToEl.value = formatDate(today);
    }

    // Chart.js Default Config adjustments
    Chart.defaults.font.family = "inherit";
    Chart.defaults.color = '#6b778c';

    // 1. Sales vs Purchase Line Chart
    const ctxSalesPurchase = document.getElementById('salesPurchaseChart');
    if (ctxSalesPurchase) {
        // જો તમારી પાસે window.chartData હોય તો તેનો ઉપયોગ કરો, નહિતર ડિફોલ્ટ ડમી ડેટા રહેશે
        const spLabels = window.chartData && window.chartData.salesPurchaseLabels ? window.chartData.salesPurchaseLabels : ['W1', 'W2', 'W3', 'W4'];
        const spSalesData = window.chartData && window.chartData.salesData ? window.chartData.salesData : [320000, 410000, 390000, 485000];
        const spPurchaseData = window.chartData && window.chartData.purchaseData ? window.chartData.purchaseData : [250000, 300000, 220000, 210000];

        new Chart(ctxSalesPurchase, {
            type: 'line',
            data: {
                labels: spLabels,
                datasets: [
                    {
                        label: 'Sales (₹)',
                        data: spSalesData,
                        borderColor: '#0052cc',
                        backgroundColor: 'rgba(0, 82, 204, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Purchase (₹)',
                        data: spPurchaseData,
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
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 10, font: { size: 10 } }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#dfe1e6' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 2. Expense Distribution Donut Chart
    const ctxExpense = document.getElementById('expenseChart');
    if (ctxExpense) {
        const expLabels = window.chartData && window.chartData.expenseLabels ? window.chartData.expenseLabels : ['Salaries', 'Rent', 'Mktg', 'Maint', 'Logistics'];
        const expValues = window.chartData && window.chartData.expenseValues ? window.chartData.expenseValues : [65000, 30000, 20000, 18000, 12000];

        new Chart(ctxExpense, {
            type: 'doughnut',
            data: {
                labels: expLabels,
                datasets: [{
                    data: expValues,
                    backgroundColor: [
                        '#0052cc',
                        '#00b8d9',
                        '#36b37e',
                        '#ffab00',
                        '#6554c0'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 10, font: { size: 10 } }
                    }
                },
                cutout: '70%'
            }
        });
    }

    // 3. Monthly Profit Bar Chart
    const ctxProfit = document.getElementById('monthlyProfitChart');
    if (ctxProfit) {
        const profitLabels = window.chartData && window.chartData.profitLabels ? window.chartData.profitLabels : ['Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'];
        const profitValues = window.chartData && window.chartData.profitValues ? window.chartData.profitValues : [210000, 240000, 190000, 280000, 260000, 300000];

        new Chart(ctxProfit, {
            type: 'bar',
            data: {
                labels: profitLabels,
                datasets: [{
                    label: 'Net Profit (₹)',
                    data: profitValues,
                    backgroundColor: '#0052cc',
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#dfe1e6' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // Filter Form Submission Handler (Generate Report without alerts)
    const filterForm = document.getElementById('reportFilterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            const submitBtn = document.getElementById('generateReportBtn');
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                submitBtn.disabled = true;
            }
        });

        // Reset Form Handler (Resets inputs and restores default date range natively)
        filterForm.addEventListener('reset', function() {
            setTimeout(() => {
                if (dateFromEl) dateFromEl.value = formatDate(firstDay);
                if (dateToEl) dateToEl.value = formatDate(today);
            }, 10);
        });
    }

    // PDF Export Event Handler
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', function() {
            console.log("Generating PDF file...");
        });
    }

    // Print Report Event Handler
    const printReportBtn = document.getElementById('printReportBtn');
    if (printReportBtn) {
        printReportBtn.addEventListener('click', function() {
            window.print();
        });
    }

    // Recent Report Download Event Handlers
    const downloadButtons = document.querySelectorAll('.download-report-btn');
    downloadButtons.forEach((btn, index) => {
        btn.addEventListener('click', function() {
            console.log(`Downloading report item #${index + 1}...`);
        });
    });

});