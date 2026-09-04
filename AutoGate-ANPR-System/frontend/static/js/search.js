document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    function performSearch() {
        const plate = searchInput.value.trim();
        if (!plate) {
            alert('Please enter a plate number to search.');
            return;
        }

        fetch(`/api/search?plate=${encodeURIComponent(plate)}`)
            .then(response => response.json())
            .then(data => {
                populateTable(data);
            })
            .catch(error => console.error('Error searching vehicles:', error));
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
        const tbody = document.getElementById('search-tbody');
        tbody.innerHTML = '';

        if (vehicles.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No vehicles found.</td></tr>';
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
});
