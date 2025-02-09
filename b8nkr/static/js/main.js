// Bot Status Management
function toggleBot() {
    fetch('/toggle_bot', {
        method: 'POST',
    })
        .then(response => response.json())
        .then(data => {
            const statusIndicator = document.getElementById('status-indicator');
            const toggleButton = document.querySelector('.btn.btn-primary');

            if (data.status === 'running') {
                statusIndicator.classList.remove('bg-danger');
                statusIndicator.classList.add('bg-success');
                toggleButton.textContent = 'Stop Bot';
            } else {
                statusIndicator.classList.remove('bg-success');
                statusIndicator.classList.add('bg-danger');
                toggleButton.textContent = 'Start Bot';
            }
        });
}

// Command Usage Chart
function initializeCommandChart() {
    const ctx = document.getElementById('commandChart');
    if (!ctx) return;

    fetch('/command_stats')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Command Usage',
                        data: data.values,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        }
                    }
                }
            });
        });
}

// Configuration Management
function saveConfig(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch('/save_config', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Configuration saved successfully!', 'success');
            } else {
                showAlert('Error saving configuration', 'danger');
            }
        });
}

// Alert System
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);

    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Real-time Log Updates
function initializeLogStream() {
    const logContainer = document.getElementById('logContainer');
    if (!logContainer) return;

    const eventSource = new EventSource('/log_stream');

    eventSource.onmessage = function (event) {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.textContent = event.data;
        logContainer.appendChild(logEntry);

        // Auto-scroll to bottom
        logContainer.scrollTop = logContainer.scrollHeight;

        // Limit number of visible logs
        while (logContainer.children.length > 100) {
            logContainer.removeChild(logContainer.firstChild);
        }
    };
}

// Initialize components when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    initializeCommandChart();
    initializeLogStream();

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
