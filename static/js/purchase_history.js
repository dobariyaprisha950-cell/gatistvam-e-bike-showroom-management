document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const dateInput = document.getElementById('dateInput');
    const resetBtn = document.getElementById('resetBtn');
    const tableBody = document.getElementById('purchaseTableBody');
    const rows = tableBody ? tableBody.getElementsByTagName('tr') : [];
    const noResults = document.getElementById('noResults');

    const purchaseModal = document.getElementById('purchaseModal');
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const modalFooterCloseBtn = document.getElementById('modalFooterCloseBtn');
    
    const modalInvoiceNo = document.getElementById('modalInvoiceNo');
    const modalDate = document.getElementById('modalDate');
    const modalSupplier = document.getElementById('modalSupplier');
    const modalQty = document.getElementById('modalQty');
    const modalAmount = document.getElementById('modalAmount');
    const modalPreviewBox = document.getElementById('modalPreviewBox');

    function filterTable() {
        if (!searchInput || !dateInput) return;
        const query = searchInput.value.toLowerCase().trim();
        const selectedDate = dateInput.value;
        let visibleCount = 0;

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            if (!row.getAttribute('data-invoice')) continue; // skip non-data rows like empty state
            
            const invoiceText = row.getAttribute('data-invoice').toLowerCase();
            const supplierText = row.getAttribute('data-supplier').toLowerCase();
            const dateText = row.getAttribute('data-date');

            const matchesSearch = invoiceText.includes(query) || supplierText.includes(query);
            let matchesDate = true;
            if (selectedDate) {
                matchesDate = (dateText === selectedDate);
            }

            if (matchesSearch && matchesDate) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        }

        if (noResults) {
            noResults.style.display = (visibleCount === 0) ? 'block' : 'none';
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterTable);
    }

    if (dateInput) {
        dateInput.addEventListener('change', filterTable);
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (searchInput) searchInput.value = '';
            if (dateInput) dateInput.value = '';
            
            for (let i = 0; i < rows.length; i++) {
                if (!rows[i].getAttribute('data-invoice')) continue;
                rows[i].style.display = '';
            }
            if (noResults) noResults.style.display = 'none';
        });
    }

    document.addEventListener('click', function(e) {
        const viewBtn = e.target.closest('.view-btn');
        if (viewBtn) {
            if (modalInvoiceNo) modalInvoiceNo.textContent = viewBtn.getAttribute('data-invoiceno');
            if (modalDate) modalDate.textContent = viewBtn.getAttribute('data-date');
            if (modalSupplier) modalSupplier.textContent = viewBtn.getAttribute('data-supplier');
            if (modalQty) modalQty.textContent = viewBtn.getAttribute('data-qty');
            if (modalAmount) modalAmount.textContent = viewBtn.getAttribute('data-amount');

            const imgSrc = viewBtn.getAttribute('data-img');
            if (modalPreviewBox) {
                if (imgSrc) {
                    modalPreviewBox.innerHTML = `<img src="${imgSrc}" alt="Invoice Image">`;
                } else {
                    modalPreviewBox.innerHTML = `
                        <svg class="erp-preview-placeholder-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                        <span class="erp-preview-text">No Invoice Image Uploaded</span>
                    `;
                }
            }

            if (purchaseModal) purchaseModal.style.display = 'flex';
        }

        const thumbWrap = e.target.closest('.erp-thumbnail-wrap');
        if (thumbWrap) {
            const tr = thumbWrap.closest('tr');
            const rowViewBtn = tr ? tr.querySelector('.view-btn') : null;
            if (rowViewBtn) {
                rowViewBtn.click();
            }
        }
    });

    function closeModal() {
        if (purchaseModal) {
            purchaseModal.style.display = 'none';
        }
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
    if (modalFooterCloseBtn) modalFooterCloseBtn.addEventListener('click', closeModal);

    if (purchaseModal) {
        purchaseModal.addEventListener('click', function(e) {
            if (e.target === purchaseModal) {
                closeModal();
            }
        });
    }
});