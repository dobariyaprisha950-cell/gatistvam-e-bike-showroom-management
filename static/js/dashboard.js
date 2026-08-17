document.addEventListener('DOMContentLoaded', function() {
    
    // Check if Chart library is loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js library missing or failed to load.');
        return;
    }

    // ==========================================
    // 1. Sales Overview Chart Integration
    // ==========================================
    const salesCanvas = document.getElementById('salesChart');
    const noSalesMsg = document.getElementById('noSalesDataMessage');

    if (salesCanvas) {
        const labels = window.salesChartLabels || [];
        const data = window.salesChartData || [];

        if (labels.length === 0 || data.length === 0) {
            salesCanvas.style.display = 'none';
            if (noSalesMsg) noSalesMsg.style.display = 'block';
        } else {
            if (noSalesMsg) noSalesMsg.style.display = 'none';
            salesCanvas.style.display = 'block';

            const salesCtx = salesCanvas.getContext('2d');

            // Soft Blue Gradient Fill
            const gradient = salesCtx.createLinearGradient(0, 0, 0, 220);
            gradient.addColorStop(0, 'rgba(59, 130, 246, 0.35)');
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

            new Chart(salesCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Sales Revenue',
                        data: data,
                        borderColor: '#2563eb',
                        borderWidth: 2.5,
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.25,
                        pointBackgroundColor: '#ffffff',
                        pointBorderColor: '#2563eb',
                        pointBorderWidth: 2,
                        pointRadius: 4.5,
                        pointHoverRadius: 7
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    // Math.round થી Decimal પોઈન્ટ દૂર થશે
                                    const rawVal = context.parsed.y || 0;
                                    const roundedVal = Math.round(rawVal);
                                    return ' Revenue: ₹ ' + roundedVal.toLocaleString('en-IN');
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { 
                                color: '#64748b', 
                                font: { size: 11 } 
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f1f5f9' },
                            ticks: {
                                color: '#64748b',
                                font: { size: 11 },
                                callback: function(value) {
                                    if (value >= 1000) {
                                        return Math.round(value / 1000) + 'k';
                                    }
                                    return value;
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    // 2. Stock Overview Doughnut Chart
    const stockCanvas = document.getElementById('stockChart');
    if (stockCanvas) {
        const labels = window.stockModelLabels || [];
        const counts = window.stockModelCounts || [];
        const stockCtx = stockCanvas.getContext('2d');

        if (labels.length === 0 || counts.length === 0) {
            new Chart(stockCtx, {
                type: 'doughnut',
                data: {
                    labels: ['No Stock'],
                    datasets: [{
                        data: [1],
                        backgroundColor: ['#e2e8f0'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '72%',
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                }
            });
        } else {
            const colorPalette = [
                '#2563eb', '#10b981', '#f59e0b', '#8b5cf6', 
                '#ec4899', '#06b6d4', '#6366f1', '#14b8a6',
                '#f43f5e', '#84cc16'
            ];

            new Chart(stockCtx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: counts,
                        backgroundColor: colorPalette.slice(0, labels.length),
                        borderWidth: 2,
                        borderColor: '#ffffff',
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '72%',
                    layout: {
                        padding: 15
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            yAlign: 'bottom', // Popup ને હંમેશા પોઈન્ટની ઉપર બતાવશે જેથી નીચે કપાશે નહિ
                            displayColors: true,
                            boxPadding: 4,
                            callbacks: {
                                label: function(context) {
                                    const labelName = context.label || '';
                                    const val = context.parsed || 0;
                                    return ` ${labelName}: ${val} available`;
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    function fetchFilteredSales(filterType) {
    fetch(`/api/sales-chart/?filter=${filterType}`)
        .then(response => response.json())
        .then(resData => {
            renderSalesChart(resData.labels, resData.data);
        })
        .catch(err => console.error('Error fetching sales chart:', err));
}
});