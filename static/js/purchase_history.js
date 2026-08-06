/* ==========================================
   Purchase History Page Logic (Dynamic DB)
   ========================================== */

document.addEventListener('DOMContentLoaded', () => {

    // --- Modal DOM Elements ---
    const viewModal = document.getElementById('viewModal');
    const closeModalX = document.getElementById('closeModalX');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const modalInvoiceNo = document.getElementById('modalInvoiceNo');
    const modalDate = document.getElementById('modalDate');
    const modalSupplier = document.getElementById('modalSupplier');
    const modalGrandTotal = document.getElementById('modalGrandTotal');
    const modalPrintBtn = document.getElementById('modalPrintBtn');
    const modalPdfBtn = document.getElementById('modalPdfBtn');

    // --- Helpers ---
    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }).format(amount);
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        const options = { day: '2-digit', month: 'short', year: 'numeric' };
        return new Date(dateStr).toLocaleDateString('en-GB', options);
    }

    // --- Generate Real PDF Download Function ---
    function downloadInvoicePDF() {
        const element = document.querySelector('.modal-container');
        if (!element) return;

        const closeX = document.getElementById('closeModalX');
        const footer = document.querySelector('.modal-footer');

        if (closeX) closeX.style.visibility = 'hidden';
        if (footer) footer.style.display = 'none';

        const opt = {
            margin:       [10, 10, 10, 10],
            filename:     `Invoice_${modalInvoiceNo.innerText || 'Document'}.pdf`,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, logging: false },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };

        if (typeof html2pdf !== 'undefined') {
            html2pdf().set(opt).from(element).save().then(() => {
                if (closeX) closeX.style.visibility = 'visible';
                if (footer) footer.style.display = 'flex';
            });
        } else {
            alert('PDF library not loaded!');
            if (closeX) closeX.style.visibility = 'visible';
            if (footer) footer.style.display = 'flex';
        }
    }

    // --- Modal Logic ---
    function closeModal() {
        if (viewModal) viewModal.classList.add('hidden');
    }

    if (closeModalX) closeModalX.addEventListener('click', closeModal);
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
    
    if (viewModal) {
        viewModal.addEventListener('click', (e) => {
            if (e.target === viewModal) closeModal();
        });
    }

    // Modal Action Buttons
    if (modalPrintBtn) modalPrintBtn.addEventListener('click', () => window.print());
    if (modalPdfBtn) modalPdfBtn.addEventListener('click', downloadInvoicePDF);
});