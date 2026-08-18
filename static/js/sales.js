document.addEventListener("DOMContentLoaded", () => {
    // 1. Form and Input Elements
    const contactNumberInput = document.getElementById("contactNumber");
    const customerNameInput = document.getElementById("customerName");
    const aadharNumberInput = document.getElementById("aadharNumber");

    const modelNameInput = document.getElementById("modelName");
    const vehicleColorInput = document.getElementById("vehicleColor");
    const chassisNumberInput = document.getElementById("chassisNumber");
    const priceInput = document.getElementById("price");
    const batteryNumberInput = document.getElementById("batteryNumber");
    const motorNumberInput = document.getElementById("motorNumber");
    const controllerNumberInput = document.getElementById("controllerNumber");

    const paymentTypeSelect = document.getElementById("paymentType");
    const discountInput = document.getElementById("discountInput");

    const lblSubtotal = document.getElementById("lblSubtotal");
    const lblSgstAmount = document.getElementById("lblSgstAmount");
    const lblCgstAmount = document.getElementById("lblCgstAmount");
    const lblGrandTotal = document.getElementById("lblGrandTotal");

    // Toast Element
    const toast = document.getElementById("toastNotification");
    const toastMessage = document.getElementById("toastMessage");

    // 2. Buttons & Modal Elements
    const modalOverlay = document.getElementById("invoiceModalOverlay");
    const btnSaveSale = document.getElementById("btnSaveSale");
    const btnCloseIcon = document.getElementById("btnCloseIcon");
    const btnPrintInvoice = document.getElementById("btnPrintInvoice");
    const btnWhatsAppShare = document.getElementById("btnWhatsAppShare");
    const btnEditSale = document.getElementById("btnEditSale");
    const btnOkInvoice = document.getElementById("btnOkInvoice");
    const salesForm = document.getElementById("salesForm");
    const currentSaleIdInput = document.getElementById("current_sale_id");

    // Preview elements
    const previewInvoiceNo = document.getElementById("previewInvoiceNo");
    const previewInvoiceDate = document.getElementById("previewInvoiceDate");
    const previewCustomerName = document.getElementById("previewCustomerName");
    const previewContactNo = document.getElementById("previewContactNo");
    const previewAadhaar = document.getElementById("previewAadhaar");
    const previewModelName = document.getElementById("previewModelName");
    const previewColor = document.getElementById("previewColor");
    const previewPriceUnit = document.getElementById("previewPriceUnit");
    const previewGstUnit = document.getElementById("previewGstUnit");
    const previewTotalAmount = document.getElementById("previewTotalAmount");
    const previewChassis = document.getElementById("previewChassis");
    const previewBattery = document.getElementById("previewBattery");
    const previewMotor = document.getElementById("previewMotor");
    const previewController = document.getElementById("previewController");
    const previewTablePrice = document.getElementById("previewTablePrice");
    const previewTableGst = document.getElementById("previewTableGst");
    const previewTableGrand = document.getElementById("previewTableGrand");
    const previewPaymentMode = document.getElementById("previewPaymentMode");
    const previewPaymentAmount = document.getElementById("previewPaymentAmount");
    const previewSubtotal = document.getElementById("previewSubtotal");
    const previewSgst = document.getElementById("previewSgst");
    const previewCgst = document.getElementById("previewCgst");
    const previewDiscount = document.getElementById("previewDiscount");
    const previewFinalAmount = document.getElementById("previewFinalAmount");

    function showToast(msg) {
        if (!toast || !toastMessage) {
            alert(msg);
            return;
        }
        toastMessage.textContent = msg;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3500);
    }

    function maskAadhaarNumber(num) {
        if (!num) return "N/A";
        const cleanNum = num.toString().replace(/\D/g, '');
        if (cleanNum.length === 12) {
            return `XXXX-XXXX-${cleanNum.slice(-4)}`;
        }
        return "[Aadhaar Redacted]";
    }

    function closeModal() {
        if (modalOverlay) {
            modalOverlay.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    function openModal() {
        if (modalOverlay) {
            modalOverlay.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    function validateForm() {
        const custName = customerNameInput?.value.trim() || "";
        const contact = contactNumberInput?.value.trim() || "";
        const model = modelNameInput?.value.trim() || "";
        const price = parseFloat(priceInput?.value) || 0;
        const chassis = chassisNumberInput?.value.trim() || "";

        if (!custName) { 
            showToast("Please enter customer name!");
            customerNameInput?.focus(); 
            return false; 
        }
        if (contact.length !== 10) { 
            showToast("Please enter a valid 10-digit mobile number!");
            contactNumberInput?.focus(); 
            return false; 
        }
        if (!model) { 
            showToast("Please select a model!");
            modelNameInput?.focus(); 
            return false; 
        }
        if (price <= 0) { 
            showToast("Please enter a valid base price!");
            priceInput?.focus(); 
            return false; 
        }
        if (!chassis) { 
            showToast("Please enter chassis number!");
            chassisNumberInput?.focus(); 
            return false; 
        }

        return true; 
    }

    function getFormattedDate() {
        const today = new Date();
        const d = String(today.getDate()).padStart(2, '0');
        const m = String(today.getMonth() + 1).padStart(2, '0');
        const y = today.getFullYear();
        return `${d}/${m}/${y}`;
    }

    function calculateBilling() {
        const price = parseFloat(priceInput?.value) || 0;
        const discount = parseFloat(discountInput?.value) || 0;

        const discounted = Math.max(0, price - discount);
        const sgst = Math.round(discounted * 0.025 * 100) / 100;
        const cgst = Math.round(discounted * 0.025 * 100) / 100;
        const subtotal = discounted;
        const grandTotal = discounted + sgst + cgst;

        if (lblSubtotal) lblSubtotal.textContent = `₹ ${subtotal.toFixed(2)}`;
        if (lblSgstAmount) lblSgstAmount.textContent = `₹ ${sgst.toFixed(2)}`;
        if (lblCgstAmount) lblCgstAmount.textContent = `₹ ${cgst.toFixed(2)}`;
        if (lblGrandTotal) lblGrandTotal.textContent = `₹ ${grandTotal.toFixed(2)}`;

        return { subtotal, sgst, cgst, grandTotal, discount };
    }

    if (priceInput) priceInput.addEventListener("input", calculateBilling);
    if (discountInput) discountInput.addEventListener("input", calculateBilling);
    
    // Automatically recalculate summary on page load (preserves prefilled values in edit mode)
    calculateBilling();

    // 3. MODEL -> COLOR -> CHASSIS CASCADING (branch-scoped, stock-driven)
    const chassisOptionsDatalist = document.getElementById("chassisOptions");

    function getCsrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    async function fetchStockOptions(selectedModelName, selectedColorName) {
        if (!selectedModelName) return null;
        const params = new URLSearchParams({ model_name: selectedModelName });
        if (selectedColorName) params.set('color_name', selectedColorName);
        const saleId = currentSaleIdInput ? currentSaleIdInput.value : '';
        if (saleId) params.set('edit_sale_id', saleId);

        try {
            const response = await fetch(`/ajax/sales/stock-options/?${params.toString()}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) return null;
            const data = await response.json();
            return data.status === 'success' ? data : null;
        } catch (err) {
            console.error("Failed to fetch stock options:", err);
            return null;
        }
    }

    function populateColorSelect(colors, keepValue) {
        if (!vehicleColorInput) return;
        const previousValue = keepValue !== undefined ? keepValue : vehicleColorInput.value;
        vehicleColorInput.innerHTML = '<option value="">-- Select Color --</option>';
        (colors || []).forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.color_name;
            opt.textContent = c.color_name;
            if (c.color_name === previousValue) opt.selected = true;
            vehicleColorInput.appendChild(opt);
        });
    }

    function populateChassisDatalist(chassisList) {
        if (!chassisOptionsDatalist) return;
        chassisOptionsDatalist.innerHTML = '';
        (chassisList || []).forEach(cn => {
            const opt = document.createElement('option');
            opt.value = cn;
            chassisOptionsDatalist.appendChild(opt);
        });
    }

    async function onModelChanged() {
        const selectedModel = modelNameInput?.value || '';
        if (!selectedModel) {
            populateColorSelect([]);
            populateChassisDatalist([]);
            return;
        }
        const data = await fetchStockOptions(selectedModel, vehicleColorInput?.value || '');
        if (data) {
            populateColorSelect(data.colors);
            populateChassisDatalist(data.chassis);
        }
    }

    async function onColorChanged() {
        const selectedModel = modelNameInput?.value || '';
        const selectedColor = vehicleColorInput?.value || '';
        if (!selectedModel || !selectedColor) {
            populateChassisDatalist([]);
            return;
        }
        const data = await fetchStockOptions(selectedModel, selectedColor);
        if (data) populateChassisDatalist(data.chassis);
    }

    if (modelNameInput) modelNameInput.addEventListener("change", onModelChanged);
    if (vehicleColorInput) vehicleColorInput.addEventListener("change", onColorChanged);

    // Prime the chassis suggestions on load if a model/color is already selected (edit mode)
    if (modelNameInput?.value && vehicleColorInput?.value) {
        onColorChanged();
    }

    async function generateAndUploadPdf(saleId, invoiceNo, customerName) {
        const element = document.getElementById("printable-invoice-container");
        if (!element) {
            throw new Error("Printable invoice container not found");
        }

        const safeCustomerName = (customerName || 'Customer').trim().replace(/\s+/g, '_');
        const pdfFileName = `${safeCustomerName}-${invoiceNo}.pdf`;

        const opt = {
            margin:       [4, 4, 4, 4],
            filename:     pdfFileName,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true, logging: false },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };

        const pdfBlob = await html2pdf().set(opt).from(element).outputPdf('blob');
        const formData = new FormData();
        formData.append('pdf_file', pdfBlob, pdfFileName);

        const csrfTokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
        const csrfToken = csrfTokenElement ? csrfTokenElement.value : '';

        const response = await fetch(`/sales/upload-pdf/${saleId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("PDF upload failed:", response.status, errorText);
            throw new Error("PDF upload failed");
        }

        const result = await response.json();
        if (result.status !== "success") {
            throw new Error(result.message || "PDF upload failed");
        }

        return result;
    }

    if (btnSaveSale && salesForm) {
        btnSaveSale.addEventListener("click", async (e) => {
            e.preventDefault();
            if (!validateForm()) {
                return;
            }

            const formData = new FormData(salesForm);
            const csrfTokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfToken = csrfTokenElement ? csrfTokenElement.value : '';

            try {
                const response = await fetch(salesForm.action, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                });

                const result = await response.json();

                if (result.status === 'success') {
                    const billCalc = calculateBilling();

                    if (currentSaleIdInput) currentSaleIdInput.value = result.sale_id;
                    if (previewInvoiceNo) previewInvoiceNo.textContent = result.invoice_no;
                    if (previewInvoiceDate) previewInvoiceDate.textContent = getFormattedDate();
                    if (previewCustomerName) previewCustomerName.textContent = customerNameInput?.value || '';
                    if (previewContactNo) previewContactNo.textContent = contactNumberInput?.value || '';
                    if (previewAadhaar) previewAadhaar.textContent = maskAadhaarNumber(aadharNumberInput?.value);
                    if (previewModelName) previewModelName.textContent = modelNameInput?.options ? modelNameInput.options[modelNameInput.selectedIndex]?.text : (modelNameInput?.value || '');
                    if (previewColor) previewColor.textContent = vehicleColorInput?.value || 'N/A';
                    
                    if (previewPriceUnit) previewPriceUnit.textContent = billCalc.subtotal.toFixed(2);
                    if (previewGstUnit) previewGstUnit.textContent = (billCalc.sgst + billCalc.cgst).toFixed(2);
                    if (previewTotalAmount) previewTotalAmount.textContent = billCalc.grandTotal.toFixed(2);

                    if (previewChassis) previewChassis.textContent = chassisNumberInput?.value || '';
                    if (previewBattery) previewBattery.textContent = batteryNumberInput?.value || 'N/A';
                    if (previewMotor) previewMotor.textContent = motorNumberInput?.value || 'N/A';
                    if (previewController) previewController.textContent = controllerNumberInput?.value || 'N/A';

                    if (previewTablePrice) previewTablePrice.textContent = `₹ ${billCalc.subtotal.toFixed(2)}`;
                    if (previewTableGst) previewTableGst.textContent = `₹ ${(billCalc.sgst + billCalc.cgst).toFixed(2)}`;
                    if (previewTableGrand) previewTableGrand.textContent = `₹ ${billCalc.grandTotal.toFixed(2)}`;

                    if (previewPaymentMode) previewPaymentMode.textContent = paymentTypeSelect?.value || 'Cash';
                    if (previewPaymentAmount) previewPaymentAmount.textContent = billCalc.grandTotal.toFixed(2);

                    if (previewSubtotal) previewSubtotal.textContent = billCalc.subtotal.toFixed(2);
                    if (previewSgst) previewSgst.textContent = billCalc.sgst.toFixed(2);
                    if (previewCgst) previewCgst.textContent = billCalc.cgst.toFixed(2);
                    if (previewDiscount) previewDiscount.textContent = billCalc.discount.toFixed(2);
                    if (previewFinalAmount) previewFinalAmount.textContent = billCalc.grandTotal.toFixed(2);

                    openModal();
                } else {
                    showToast(result.message || "Failed to save sale into database.");
                }
            } catch (err) {
                console.error("Database save error:", err);
                showToast("An error occurred while saving sale.");
            }
        });
    }

    if (btnCloseIcon) btnCloseIcon.addEventListener("click", closeModal);
    if (btnEditSale) btnEditSale.addEventListener("click", closeModal);

    if (btnOkInvoice) {
        btnOkInvoice.addEventListener("click", (e) => {
            e.preventDefault();
            closeModal();
            window.location.href = "/customer/";
        });
    }

    if (btnPrintInvoice) {
        btnPrintInvoice.addEventListener("click", (e) => {
            e.preventDefault();
            const printableArea = document.getElementById("printable-invoice-container");
            if (!printableArea) {
                alert("Invoice area not found.");
                return;
            }

            const printClone = printableArea.cloneNode(true);

            // Terms & Conditions section ne print-specific classes aapo
            const termsSection = printClone.querySelector(".terms-sig-flex");

            if (termsSection) {
                termsSection.classList.add("terms-sig-flex");

                const termsBox = termsSection.firstElementChild;
                const signatureBox = termsSection.lastElementChild;

                if (termsBox) {
                    termsBox.classList.add("terms-box");
                }

                if (signatureBox) {
                    signatureBox.classList.add("signature-box");
                }
            }

            const printWindow = window.open("", "_blank", "width=900,height=1200");
            if (!printWindow) {
                alert("Please allow popups for printing.");
                return;
            }

            const styleSheets = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
                .map(s => s.outerHTML)
                .join("\n");

            printWindow.document.open();
            printWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Invoice Print</title>
                    ${styleSheets}
                    <style>
                        @page { size: A4 portrait; margin: 0; }
                        html, body { margin: 0; padding: 0; width: 210mm; height: 297mm; background: #fff; overflow: hidden; }
                        .print-wrapper {
    display: block !important;
    width: 210mm !important;
    height: 297mm !important;
    box-sizing: border-box !important;
    padding: 10mm 5mm 5mm 5mm !important;
    margin: 0 !important;
}

#printable-invoice-container {
    box-sizing: border-box !important;
    width: 190mm !important;
    max-width: 190mm !important;
    min-width: 200mm !important;
    margin: 0 auto !important;
    display: block !important;
    transform-origin: top center !important;
    transform: scale(1, 1.35);
}
                        table { width: 100%; max-width: 100%; border-collapse: collapse; table-layout: fixed; box-sizing: border-box; }
                        th, td { border: 1.5px solid #000000 !important; border-collapse: collapse !important; padding: 8px 5px; font-size: 10px !important; line-height: 1.3; vertical-align: middle; word-wrap: break-word; overflow-wrap: break-word; text-align: center; }
                        th { font-weight: 600; background: #f2f2f2; }
                        .bill-header, .bill-to-box, .inv-payment-summary-flex{ margin: 8px 0 !important; page-break-inside: avoid; break-inside: avoid; }
                        .bill-table { margin: 8px 0 1px 0 !important; page-break-inside: avoid; break-inside: avoid; }
                        .table-summary-bar {width: 100% !important; border-top: 0.5px solid #000 !important; box-sizing: border-box !important;}
                        .vehicle-specs-box { margin: 0px !important; }
                        .bill-outer-border { border: 1px solid #000; padding: 8mm; box-sizing: border-box; }
                        .grand-total { font-weight: 700; font-size: 11px; border-top: 1px solid #000; padding-top: 3px; }
                        .terms-sig-flex {
    display: flex !important;
    justify-content: space-between !important;
    align-items: flex-end !important;
    width: 100% !important;
    margin: 10px 0 0 0 !important;
    padding: 0 !important;
    text-align: left !important;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

.terms-box {
    width: 58% !important;
    flex: 0 0 58% !important;
    margin: 0 !important;
    padding: 0 !important;
    text-align: left !important;
    font-size: 10px !important;
}

.terms-box strong {
    display: block !important;
    width: 100% !important;
    margin: 0 0 4px 0 !important;
    padding: 0 !important;
    text-align: left !important;
}

.terms-box ul {
    display: block !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    text-align: left !important;
    list-style: none !important;
}

.terms-box li {
    display: block !important;
    width: 100% !important;
    margin: 0 0 3px 0 !important;
    padding: 0 !important;
    text-align: left !important;
    white-space: normal !important;
    clear: both !important;
}

.terms-box li::before {
    content: "• " !important;
}
    
.signature-box {
    width: 38% !important;
    flex: 0 0 38% !important;
    margin: 0 !important;
    padding: 0 !important;
    text-align: center !important;
}
                        .popup-actions-v2, .invoice-modal-close-icon, .sales-page-container, .toast-notification, .modal-close, button, input, select, textarea, ::-webkit-scrollbar { display: none !important; }
                        * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                        
                    </style>
                </head>
                <body>
                    <div class="print-wrapper">
                        ${printClone.outerHTML}
                    </div>
                </body>
                </html>
            `);

            printWindow.document.close();
            printWindow.focus();

            setTimeout(() => {
                printWindow.print();
                setTimeout(() => {
                    printWindow.close();
                }, 500);
            }, 700);
        });
    }

    if (btnWhatsAppShare) {
        btnWhatsAppShare.addEventListener("click", async (e) => {
            e.preventDefault();

            const saleId = currentSaleIdInput ? currentSaleIdInput.value : null;
            if (!saleId) {
                showToast("Sale ID not found. Please save sale first.");
                return;
            }

            const invoiceNo = previewInvoiceNo ? previewInvoiceNo.textContent : 'INV';
            const customerName = previewCustomerName ? previewCustomerName.textContent : 'Customer';

            try {
                await generateAndUploadPdf(saleId, invoiceNo, customerName);

                const response = await fetch(`/sales/whatsapp-share/${saleId}/`, {
                    method: 'GET',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });

                if (!response.ok) {
                    showToast("Failed to retrieve WhatsApp share link.");
                    return;
                }

                const data = await response.json();
                if (data.status === "success") {
                    if (data.invoice_url) {
                        const link = document.createElement('a');
                        link.href = data.invoice_url;
                        link.download = data.invoice_filename || `${customerName}-${invoiceNo}.pdf`;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }
                    if (data.whatsapp_url) {
                        window.open(data.whatsapp_url, '_blank');
                    }
                } else {
                    showToast(data.message || "Failed to generate WhatsApp share link.");
                }
            } catch (err) {
                console.error("WhatsApp process error:", err);
                showToast("Failed to process WhatsApp share. Please check console.");
            }
        });
    }
});