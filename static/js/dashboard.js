document.addEventListener('DOMContentLoaded', function() {
    
    // Dynamic Doughnut Chart using Backend Data
    const stockCanvas = document.getElementById('stockChart');
    if (stockCanvas && window.dashboardData) {
        const ctx = stockCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Available', 'Sold', 'Reserved', 'Other'],
                datasets: [{
                    data: [
                        window.dashboardData.available,
                        window.dashboardData.sold,
                        window.dashboardData.reserved,
                        window.dashboardData.other
                    ],
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
});