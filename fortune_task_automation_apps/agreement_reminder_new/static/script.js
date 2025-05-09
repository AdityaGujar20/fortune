document.addEventListener('DOMContentLoaded', () => {
    // Check if vizData exists and has the required properties
    if (!vizData || !vizData.status || !vizData.expiry_dates) {
        console.error('Invalid vizData:', vizData);
        return;
    }

    // Status Breakdown Pie Chart
    const statusCtx = document.getElementById('statusChart').getContext('2d');
    try {
        new Chart(statusCtx, {
            type: 'pie',
            data: {
                labels: ['Active', 'Renewed', 'Expired'],
                datasets: [{
                    data: [
                        vizData.status.active || 0,
                        vizData.status.renewed || 0,
                        vizData.status.expired || 0
                    ],
                    backgroundColor: ['#36A2EB', '#FFCE56', '#FF6384']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error rendering status chart:', error);
    }

    // Expiry Timeline Line Chart
    const timelineCtx = document.getElementById('timelineChart').getContext('2d');
    try {
        const dates = vizData.expiry_dates || [];
        const dateCounts = {};
        dates.forEach(date => {
            if (date) { // Ensure date is not null/undefined
                dateCounts[date] = (dateCounts[date] || 0) + 1;
            }
        });
        const sortedDates = Object.keys(dateCounts).sort();
        const counts = sortedDates.map(date => dateCounts[date]);

        new Chart(timelineCtx, {
            type: 'line',
            data: {
                labels: sortedDates.length ? sortedDates : ['No Data'], // Fallback if no dates
                datasets: [{
                    label: 'Agreements Expiring',
                    data: counts.length ? counts : [0],
                    borderColor: '#36A2EB',
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: 'Expiry Date' }
                    },
                    y: {
                        title: { display: true, text: 'Number of Agreements' },
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error rendering timeline chart:', error);
    }
});