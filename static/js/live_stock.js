document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('liveStockSearch');
    const colorSelect = document.getElementById('colorFilter');
    const resetBtn = document.getElementById('resetFiltersBtn');
    const vehicleRows = document.querySelectorAll('#vehicleList .vehicle-row');
    const noMatchMessage = document.getElementById('noMatchMessage');

    function applyFilters() {
        const searchTerm = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const selectedColorId = colorSelect ? colorSelect.value : '';
        let visibleCount = 0;

        vehicleRows.forEach(row => {
            const modelName = (row.getAttribute('data-model-name') || '').toLowerCase();
            const companyName = (row.getAttribute('data-company-name') || '').toLowerCase();
            const colorName = (row.getAttribute('data-color-name') || '').toLowerCase();
            const colorId = row.getAttribute('data-color-id') || '';

            const matchesSearch = !searchTerm || 
                modelName.includes(searchTerm) || 
                companyName.includes(searchTerm) || 
                colorName.includes(searchTerm);

            const matchesColor = !selectedColorId || colorId === selectedColorId;

            if (matchesSearch && matchesColor) {
                row.style.display = 'grid';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        if (noMatchMessage && vehicleRows.length > 0) {
            if (visibleCount === 0) {
                noMatchMessage.style.display = 'block';
            } else {
                noMatchMessage.style.display = 'none';
            }
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', applyFilters);
    }

    if (colorSelect) {
        colorSelect.addEventListener('change', applyFilters);
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (colorSelect) colorSelect.value = '';
            applyFilters();
        });
    }
});