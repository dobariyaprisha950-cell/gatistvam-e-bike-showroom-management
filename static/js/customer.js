document.addEventListener('DOMContentLoaded', function () {
    const invoiceModal = document.getElementById('invoiceModal');
    const closeInvoiceModalBtn = document.getElementById('closeInvoiceModal');
    const printInvoiceBtn = document.getElementById('printInvoiceBtn');
    const shareWhatsAppBtn = document.getElementById('shareWhatsAppBtn');
    const resetBtn = document.getElementById('resetBtn');

    // Filter Logic
    function filterTable() {
        const query = document.getElementById('searchInput').value.toLowerCase().trim();
        const fromDate = document.getElementById('dateFrom').value;
        const toDate = document.getElementById('dateTo').value;
        const selectedModel = document.getElementById('modelSelect').value.toLowerCase();
        const selectedBranch = document.getElementById('branchSelect').value.toLowerCase();
        const selectedPayment = document.getElementById('paymentMethodSelect').value.toLowerCase();

        const rows = document.querySelectorAll('#customerTable tbody tr');

        rows.forEach(row => {
            if (row.cells.length < 8) return;

            const name = row.cells[0].textContent.toLowerCase();
            const phone = row.cells[1].textContent.toLowerCase();
            const email = row.cells[2].textContent.toLowerCase();
            const model = row.cells[3].textContent.toLowerCase();
            const branch = row.cells[4].textContent.toLowerCase();
            const payment = row.cells[5].textContent.toLowerCase();
            const date = row.cells[6].textContent.trim();

            let matchesSearch = query === '' || name.includes(query) || phone.includes(query) || email.includes(query);
            let matchesModel = selectedModel === '' || model.includes(selectedModel);
            let matchesBranch = selectedBranch === '' || branch.includes(selectedBranch);
            let matchesPayment = selectedPayment === '' || payment.includes(selectedPayment);

            let matchesDate = true;
            if (fromDate && date < fromDate) matchesDate = false;
            if (toDate && date > toDate) matchesDate = false;

            row.style.display = (matchesSearch && matchesModel && matchesBranch && matchesPayment && matchesDate) ? '' : 'none';
        });
    }

    ['searchInput', 'dateFrom', 'dateTo', 'modelSelect', 'branchSelect', 'paymentMethodSelect'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', filterTable);
            el.addEventListener('change', filterTable);
        }
    });

    // Dynamic Row Selection
    document.addEventListener('click', function (e) {
        if (e.target && e.target.classList.contains('view-invoice-btn')) {
            const row = e.target.closest('tr');
            if (!row) return;

            const name = row.dataset.customerName || row.cells[0].textContent.trim();
            const phone = row.dataset.phone || row.cells[1].textContent.trim();
            const model = row.dataset.model || row.cells[3].textContent.trim();
            const branch = row.dataset.branch || row.cells[4].textContent.trim();
            const paymentMode = row.dataset.payment || row.cells[5].textContent.trim();
            const date = row.dataset.date || row.cells[6].textContent.trim();
            const invoiceId = e.target.getAttribute('data-id') || '0001';
            
            const price = parseFloat(row.dataset.price) || 50000;
            const gst = price * 0.05;
            const grandTotal = price + gst;

            document.getElementById('invNo').textContent = `GEV/JND/${invoiceId}`;
            document.getElementById('invDate').textContent = date;
            document.getElementById('invBranch').textContent = branch.toUpperCase();
            document.getElementById('invCustName').textContent = name;
            document.getElementById('invCustPhone').textContent = phone;
            document.getElementById('invModelName').textContent = model;

            document.getElementById('invPriceUnit').textContent = price.toFixed(2);
            document.getElementById('invGstUnit').textContent = gst.toFixed(2);
            document.getElementById('invTotalAmount').textContent = grandTotal.toFixed(2);

            document.getElementById('invSubtotal').textContent = price.toFixed(2);
            document.getElementById('invSgst').textContent = (gst / 2).toFixed(2);
            document.getElementById('invCgst').textContent = (gst / 2).toFixed(2);
            document.getElementById('invGrandTotal').textContent = grandTotal.toFixed(2);
            document.getElementById('invPaymentMode').textContent = `${paymentMode.toUpperCase()} = ₹${grandTotal.toFixed(2)}`;

            if (invoiceModal) invoiceModal.style.display = 'flex';
        }
    });

    if (closeInvoiceModalBtn) {
        closeInvoiceModalBtn.addEventListener('click', () => invoiceModal.style.display = 'none');
    }

    if (printInvoiceBtn) {
        printInvoiceBtn.addEventListener('click', () => window.print());
    }

    if (shareWhatsAppBtn) {
        shareWhatsAppBtn.addEventListener('click', function () {
            const custName = document.getElementById('invCustName').textContent;
            const grandTotal = document.getElementById('invGrandTotal').textContent;
            const phone = document.getElementById('invCustPhone').textContent.replace(/[^0-9]/g, '');
            const message = encodeURIComponent(`Hello ${custName}, your invoice total is ₹${grandTotal}. Thank you!`);
            window.open(`https://api.whatsapp.com/send?phone=${phone}&text=${message}`, '_blank');
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            document.getElementById('searchInput').value = '';
            document.getElementById('dateFrom').value = '';
            document.getElementById('dateTo').value = '';
            document.getElementById('modelSelect').value = '';
            document.getElementById('branchSelect').value = '';
            document.getElementById('paymentMethodSelect').value = '';
            filterTable();
        });
    }
});