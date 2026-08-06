document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('vehicleSearch');
    const branchFilter = document.getElementById('branchFilter');
    const statusFilter = document.getElementById('statusFilter');

    function filterVehicles() {
        const vehicleRows = document.querySelectorAll('.vehicle-row');
        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const selectedBranch = branchFilter ? branchFilter.value : '';
        const selectedStatus = statusFilter ? statusFilter.value : '';

        vehicleRows.forEach(row => {
            const nameEl = row.querySelector('.vehicle-name-text');
            const modelEl = row.querySelector('.vehicle-model-text');

            const name = nameEl ? nameEl.textContent.toLowerCase() : '';
            const model = modelEl ? modelEl.textContent.toLowerCase() : '';

            const rowStatus = row.getAttribute('data-status') || '';
            const rowBranch = row.getAttribute('data-branch') || '';

            const matchesSearch = name.includes(searchTerm) || model.includes(searchTerm);
            const matchesBranch = !selectedBranch || rowBranch === selectedBranch;
            const matchesStatus = !selectedStatus || rowStatus === selectedStatus;

            if (matchesSearch && matchesBranch && matchesStatus) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    if (searchInput) searchInput.addEventListener('input', filterVehicles);
    if (branchFilter) branchFilter.addEventListener('change', filterVehicles);
    if (statusFilter) statusFilter.addEventListener('change', filterVehicles);
});