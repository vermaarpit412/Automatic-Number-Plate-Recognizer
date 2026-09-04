document.addEventListener('DOMContentLoaded', function() {
    loadVehicles();

    function loadVehicles() {
        fetch('/api/vehicles')
            .then(response => response.json())
            .then(data => {
                updateStats(data);
                populateTable(data);
            })
            .catch(error => console.error('Error loading vehicles:', error));
    }

    function updateStats(vehicles) {
        const totalEntries = vehicles.length;
        const totalExits = vehicles.filter(v => v.exit_time !== 'Still Inside').length;
        const currentlyInside = totalEntries - totalExits;
        const uniquePlates = new Set(vehicles.map(v => v.plate)).size;

        document.getElementById('total-entries').textContent = totalEntries;
        document.getElementById('total-exits').textContent = totalExits;
        document.getElementById('currently-inside').textContent = currentlyInside;
        document.getElementById('total-vehicles').textContent = uniquePlates;
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        }[char]));
    }

    function imageButton(url) {
        if (!url) {
            return 'N/A';
        }
        return `<a href="${escapeHtml(url)}" target="_blank" class="btn btn-sm btn-info">View</a>`;
    }

    function populateTable(vehicles) {
        const tbody = document.getElementById('vehicle-tbody');
        tbody.innerHTML = '';

        if (vehicles.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No vehicles recorded yet</td></tr>';
            return;
        }

        vehicles.forEach(vehicle => {
            const row = document.createElement('tr');

            row.innerHTML = `
                <td><strong>${escapeHtml(vehicle.plate)}</strong></td>
                <td>${escapeHtml(vehicle.entry_time)}</td>
                <td>${escapeHtml(vehicle.exit_time)}</td>
                <td>${escapeHtml(vehicle.duration)}</td>
                <td>${imageButton(vehicle.entry_image_url)}</td>
                <td>${imageButton(vehicle.exit_image_url)}</td>
            `;

            tbody.appendChild(row);
        });
    }

    // Refresh data every 10 seconds
    setInterval(loadVehicles, 10000);
});
