document.addEventListener("DOMContentLoaded", () => {
    // Input Elements Selection
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

    // Summary Labels
    const lblSubtotal = document.getElementById("lblSubtotal");
    const lblSgstAmount = document.getElementById("lblSgstAmount");
    const lblCgstAmount = document.getElementById("lblCgstAmount");
    const lblGrandTotal = document.getElementById("lblGrandTotal");

    // Modal & Buttons
    const modalOverlay = document.getElementById("invoiceModalOverlay");
    const btnSaveSale = document.getElementById("btnSaveSale");
    const btnClosePopupV2 = document.getElementById("btnClosePopupV2");
    const btnCloseIcon = document.getElementById("btnCloseIcon");
    const btnPrintInvoice = document.getElementById("btnPrintInvoice");
    const btnWhatsAppShare = document.getElementById("btnWhatsAppShare");
    const btnSubmitForm = document.getElementById("btnSubmitForm");
    const salesForm = document.getElementById("salesForm");

    // Mask Aadhaar: 12 digit -> XXXX XXXX 1234
    function getMaskedAadhaar(val) {
        if (!val || val.trim().length < 4) return "XXXX XXXX XXXX";
        const cleanVal = val.trim();
        return `XXXX XXXX ${cleanVal.slice(-4)}`;
    }

    // Date formatting (DD/MM/YYYY)
    function getFormattedDate() {
        const today = new Date();
        const d = String(today.getDate()).padStart(2, '0');
        const m = String(today.getMonth() + 1).padStart(2, '0');
        const y = today.getFullYear();
        return `${d}/${m}/${y}`;
    }

    // Billing Calculation (GST 5% = 2.5% SGST + 2.5% CGST)
    function calculateBilling() {
        const price = parseFloat(priceInput?.value) || 0;
        const discount = parseFloat(discountInput?.value) || 0;

        const sgst = price * 0.025; 
        const cgst = price * 0.025; 
        const totalGst = sgst + cgst;
        const subtotal = price;
        const grandTotal = Math.max(0, subtotal + totalGst - discount);

        if (lblSubtotal) lblSubtotal.textContent = `₹ ${subtotal.toFixed(2)}`;
        if (lblSgstAmount) lblSgstAmount.textContent = `₹ ${sgst.toFixed(2)}`;
        if (lblCgstAmount) lblCgstAmount.textContent = `₹ ${cgst.toFixed(2)}`;
        if (lblGrandTotal) lblGrandTotal.textContent = `₹ ${grandTotal.toFixed(2)}`;

        return { price, sgst, cgst, totalGst, subtotal, discount, grandTotal };
    }

    if (priceInput) priceInput.addEventListener("input", calculateBilling);
    if (discountInput) discountInput.addEventListener("input", calculateBilling);
    calculateBilling();

    // Fill Invoice Preview Modal Dynamically
    function populateInvoicePreview() {
        const calc = calculateBilling();

        const name = customerNameInput?.value?.trim() || "N/A";
        const contact = contactNumberInput?.value?.trim() || "N/A";
        const aadhaar = getMaskedAadhaar(aadharNumberInput?.value);

        const model = modelNameInput?.value?.trim() || "N/A";
        const color = vehicleColorInput?.value?.trim() || "N/A";
        const chassis = chassisNumberInput?.value?.trim() || "N/A";
        const battery = batteryNumberInput?.value?.trim() || "N/A";
        const motor = motorNumberInput?.value?.trim() || "N/A";
        const controller = controllerNumberInput?.value?.trim() || "N/A";
        const paymentMode = (paymentTypeSelect?.value || "CASH").toUpperCase();

        // Customer Details
        document.getElementById("previewCustomerName").textContent = name;
        document.getElementById("previewContactNo").textContent = contact;
        document.getElementById("previewAadhaar").textContent = aadhaar;
        document.getElementById("previewInvoiceDate").textContent = getFormattedDate();

        // Item Line
        document.getElementById("previewModelName").textContent = model;
        document.getElementById("previewColor").textContent = color;
        document.getElementById("previewPriceUnit").textContent = calc.price.toFixed(2);
        document.getElementById("previewGstUnit").textContent = calc.totalGst.toFixed(2);
        document.getElementById("previewTotalAmount").textContent = (calc.price + calc.totalGst).toFixed(2);

        // Vehicle Specs
        document.getElementById("previewChassis").textContent = chassis;
        document.getElementById("previewBattery").textContent = battery;
        document.getElementById("previewMotor").textContent = motor;
        document.getElementById("previewController").textContent = controller;

        // Summary Bar
        document.getElementById("previewTablePrice").textContent = `₹ ${calc.price.toFixed(2)}`;
        document.getElementById("previewTableGst").textContent = `₹ ${calc.totalGst.toFixed(2)}`;
        document.getElementById("previewTableGrand").textContent = `₹ ${(calc.price + calc.totalGst).toFixed(2)}`;

        // Footers
        document.getElementById("previewPaymentMode").textContent = paymentMode;
        document.getElementById("previewSubtotal").textContent = calc.subtotal.toFixed(2);
        document.getElementById("previewSgst").textContent = calc.sgst.toFixed(2);
        document.getElementById("previewCgst").textContent = calc.cgst.toFixed(2);
        document.getElementById("previewDiscount").textContent = calc.discount.toFixed(2);
        document.getElementById("previewFinalAmount").textContent = calc.grandTotal.toFixed(2);
    }

    // Open & Close Modal
    if (btnSaveSale) {
        btnSaveSale.addEventListener("click", (e) => {
            e.preventDefault();
            populateInvoicePreview();
            if (modalOverlay) modalOverlay.classList.add("active");
        });
    }

    function closeModal() {
        if (modalOverlay) modalOverlay.classList.remove("active");
    }

    if (btnClosePopupV2) btnClosePopupV2.addEventListener("click", closeModal);
    if (btnCloseIcon) btnCloseIcon.addEventListener("click", closeModal);

    // Save Form to Database
    if (btnSubmitForm && salesForm) {
        btnSubmitForm.addEventListener("click", () => {
            salesForm.submit();
        });
    }

    // Print Logic
    if (btnPrintInvoice) {
        btnPrintInvoice.addEventListener("click", () => window.print());
    }

    // WhatsApp PDF Auto Download + Open WhatsApp Chat Logic
    if (btnWhatsAppShare) {
        btnWhatsAppShare.addEventListener("click", () => {
            const contact = contactNumberInput?.value?.trim();
            const name = customerNameInput?.value?.trim() || "Customer";
            const invoiceNo = document.getElementById("previewInvoiceNo")?.textContent || "GEV_JND_0001";
            const grandTotalText = lblGrandTotal?.textContent || "₹ 0.00";

            if (!contact || contact.length !== 10) {
                alert("Please enter a valid 10-digit mobile number.");
                return;
            }

            // Target HTML Invoice Element
            const element = document.getElementById('printable-invoice-container');
            
            // PDF Generation Options
            const cleanInvoiceName = invoiceNo.replace(/[\/\\]/g, '_');
            const opt = {
                margin:       0.2,
                filename:     `Invoice_${cleanInvoiceName}_${name}.pdf`,
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2 },
                jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
            };

            // Download PDF first, then launch WhatsApp
            if (typeof html2pdf !== 'undefined') {
                html2pdf().set(opt).from(element).save().then(() => {
                    const message = encodeURIComponent(
                        `Hello ${name},\n\n` +
                        `Thank you for purchasing from *Gatistvam Electric Vehicle*! 🚲\n\n` +
                        `📄 *Invoice No:* ${invoiceNo}\n` +
                        `💰 *Total Amount:* ${grandTotalText}\n\n` +
                        `Your Tax Invoice PDF has been downloaded to your system. Please find it attached below!`
                    );
                    window.open(`https://api.whatsapp.com/send?phone=91${contact}&text=${message}`, "_blank");
                });
            } else {
                alert("PDF library is loading or failed to load. Please try again.");
            }
        });
    }

    // Form Validation (Enables Button only when required fields are filled)
    function validateRequiredFields() {
        const isNameValid = customerNameInput?.value?.trim().length > 0;
        const isContactValid = contactNumberInput?.value?.trim().length === 10;
        const isModelValid = modelNameInput?.value?.trim().length > 0;
        const isChassisValid = chassisNumberInput?.value?.trim().length > 0;
        const isPriceValid = parseFloat(priceInput?.value) > 0;

        if (isNameValid && isContactValid && isModelValid && isChassisValid && isPriceValid) {
            btnSaveSale.removeAttribute("disabled");
        } else {
            btnSaveSale.setAttribute("disabled", "true");
        }
    }

    const requiredFieldsList = [
        customerNameInput,
        contactNumberInput,
        modelNameInput,
        chassisNumberInput,
        priceInput
    ];

    requiredFieldsList.forEach((field) => {
        if (field) {
            field.addEventListener("input", validateRequiredFields);
            field.addEventListener("change", validateRequiredFields);
        }
    });

    validateRequiredFields();
});