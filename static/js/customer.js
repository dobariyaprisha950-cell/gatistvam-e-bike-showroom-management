document.addEventListener("DOMContentLoaded", function () {
    // -------------------------------------------------------------
    // 🔍 1. Live Dynamic Filtering (Search, Date, Model, Payment)
    // -------------------------------------------------------------
    const searchInput = document.getElementById("searchInput");
    const dateInput = document.getElementById("dateInput");
    const modelSelect = document.getElementById("modelSelect");
    const paymentMethodSelect = document.getElementById("paymentMethodSelect");
    const resetBtn = document.getElementById("resetBtn");
    const customerTable = document.getElementById("customerTable");
    const tableRows = customerTable ? customerTable.querySelectorAll("tbody tr") : [];

    function filterTable() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
        const selectedDate = dateInput ? dateInput.value : "";
        const selectedModel = modelSelect ? modelSelect.value.toLowerCase().trim() : "";
        const selectedPayment = paymentMethodSelect ? paymentMethodSelect.value.toLowerCase().trim() : "";

        tableRows.forEach(row => {
            if (row.cells.length === 1) return;

            const name = (row.dataset.customerName || "").toLowerCase();
            const phone = (row.dataset.phone || "").toLowerCase();
            const invoice = (row.dataset.invoiceNo || "").toLowerCase();
            const model = (row.dataset.model || "").toLowerCase();
            const payment = (row.dataset.payment || "").toLowerCase().trim();
            const date = row.dataset.date || "";

            const matchesSearch = !query || name.includes(query) || phone.includes(query) || invoice.includes(query);
            const matchesDate = !selectedDate || date === selectedDate;
            const matchesModel = !selectedModel || model.includes(selectedModel);
            const matchesPayment = !selectedPayment || payment === selectedPayment;

            if (matchesSearch && matchesDate && matchesModel && matchesPayment) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    }

    if (searchInput) searchInput.addEventListener("keyup", filterTable);
    if (dateInput) dateInput.addEventListener("change", filterTable);
    if (modelSelect) modelSelect.addEventListener("change", filterTable);
    if (paymentMethodSelect) paymentMethodSelect.addEventListener("change", filterTable);

    if (resetBtn) {
        resetBtn.addEventListener("click", function () {
            if (searchInput) searchInput.value = "";
            if (dateInput) dateInput.value = "";
            if (modelSelect) modelSelect.value = "";
            if (paymentMethodSelect) paymentMethodSelect.value = "";
            filterTable();
        });
    }

    // -------------------------------------------------------------
    // 👁️ 2. Invoice Preview Modal Logic & AJAX Retrieval
    // -------------------------------------------------------------
    const invoiceModal = document.getElementById("invoiceModal");
    const closeInvoiceModal = document.getElementById("closeInvoiceModal");
    const closeInvoiceFooterBtn = document.getElementById("closeInvoiceFooterBtn");
    const printInvoiceBtn = document.getElementById("printInvoiceBtn");
    const whatsappModalBtn = document.getElementById("whatsappModalBtn");
    const editInvoiceBtn = document.getElementById("editInvoiceBtn");

    let currentSaleId = null;

    function formatAmount(val) {
        const num = parseFloat(val) || 0;
        return num.toFixed(2);
    }
    function formatInvoiceDate(value) {
        if (!value) return "-";
        const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
        return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
    }
    function showInvoicePopup(message) {
    const existingPopup = document.getElementById("invoiceMessagePopup");

    if (existingPopup) {
        existingPopup.remove();
    }

    const popup = document.createElement("div");
    popup.id = "invoiceMessagePopup";

    popup.innerHTML = `
        <div class="invoice-message-backdrop">
            <div class="invoice-message-box">
                <div class="invoice-message-icon">!</div>

                <div class="invoice-message-title">
                    Please Create Sales PDF first
                </div>

                <button type="button" id="invoiceMessageOk">
                    OK
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(popup);

    const okButton = document.getElementById("invoiceMessageOk");

    if (okButton) {
        okButton.addEventListener("click", function () {
            popup.remove();
        });
    }
}
    function maskAadhaarNumber(aadhaar) {
        if (!aadhaar) return "N/A";
        const digits = String(aadhaar).replace(/\D/g, "");
        if (digits.length < 4) return "XXXX";
        return `XXXX-XXXX-${digits.slice(-4)}`;
    }

    function populateModalData(data) {
        document.getElementById("invNo").textContent = data.invoice_no || "-";
        document.getElementById("invDate").textContent = formatInvoiceDate(data.invoice_date);

        

        document.getElementById("invCustName").textContent = data.customer_name || "-";
        document.getElementById("invCustPhone").textContent = data.mobile_number || "-";

        const invAadhaar = document.getElementById("invAadhaar");
        if (invAadhaar) {
            invAadhaar.textContent = maskAadhaarNumber(data.aadhar_number);
        }

        document.getElementById("invAddress").textContent = data.billing_address || "";

        document.getElementById("invModelName").textContent = `${data.model_name || "-"}${data.voltage ? ` ${data.voltage}` : ""}`;
        document.getElementById("invColor").textContent = data.color_name || "N/A";
        const accessoriesLine = document.getElementById("invAccessoriesLine");
        const accessoriesValue = document.getElementById("invAccessories");
        if (accessoriesValue) accessoriesValue.textContent = data.extra_accessories || "";
        if (accessoriesLine) accessoriesLine.style.display = (data.extra_accessories || "").trim() ? "" : "none";
        document.getElementById("invChassis").textContent = data.chassis_number || "N/A";
        document.getElementById("invBattery").textContent = data.battery_number || "N/A";
        document.getElementById("invMotor").textContent = data.motor_number || "N/A";
        document.getElementById("invController").textContent = data.controller_number || "N/A";

        const sellingPrice = parseFloat(data.selling_price ?? data.price) || 0;
        const subtotal = parseFloat(data.subtotal) || 0;
        const discount = parseFloat(data.discount) || 0;
        const cgst = parseFloat(data.cgst) || 0;
        const sgst = parseFloat(data.sgst) || 0;
        const grandTotal = parseFloat(data.grand_total) || 0;

        const totalGst = cgst + sgst;

        document.getElementById("invPriceUnit").textContent = formatAmount(sellingPrice);
        document.getElementById("invGstAmount").textContent = formatAmount(totalGst);
        document.getElementById("invTotalAmount").textContent = formatAmount(grandTotal);

        document.getElementById("invSumBase").textContent = formatAmount(subtotal);
        document.getElementById("invSumGst").textContent = formatAmount(totalGst);
        document.getElementById("invSumGrand").textContent = formatAmount(grandTotal);

        document.getElementById("invPaymentMode").textContent = data.payment_method || "Cash";
        document.getElementById("invPaymentAmount").textContent = formatAmount(grandTotal);

        document.getElementById("invSubtotal").textContent = formatAmount(subtotal);
        document.getElementById("invSgst").textContent = formatAmount(sgst);
        document.getElementById("invCgst").textContent = formatAmount(cgst);
        document.getElementById("invDiscount").textContent = formatAmount(discount);
        document.getElementById("invGrandTotal").textContent = formatAmount(grandTotal);
    }

    function openInvoiceModal(row) {
        if (!row) return;

        currentSaleId = row.dataset.saleId;
        if (!currentSaleId) {
            alert("Unable to identify this sale.");
            return;
        }

        populateModalData({
            invoice_no: row.dataset.invoiceNo || "-",
            // Use the Sale's stored invoice date only. data-date is the
            // Customer table's created-at filter value, not the bill date.
            invoice_date: row.dataset.invoiceDate || "-",
            customer_name: row.dataset.customerName || "-",
            mobile_number: row.dataset.phone || "-",
            aadhar_number: row.dataset.aadhar || "N/A",
            payment_method: row.dataset.payment || "Cash",

            model_name: row.dataset.model || "-",
            voltage: row.dataset.voltage || "",
            color_name: row.dataset.color || "N/A",
            extra_accessories: row.dataset.extraAccessories || "",

            chassis_number: row.dataset.chassis || "N/A",
            battery_number: row.dataset.battery || "N/A",
            motor_number: row.dataset.motor || "N/A",
            controller_number: row.dataset.controller || "N/A",

            selling_price: row.dataset.sellingPrice || 0,
            subtotal: row.dataset.subtotal || 0,
            discount: row.dataset.discount || 0,
            cgst: row.dataset.cgst || 0,
            sgst: row.dataset.sgst || 0,
            grand_total: row.dataset.grandTotal || 0,

            branch_name: row.dataset.branch || "Main Branch",
            billing_address: row.dataset.billingAddress || "",
            branch_address: row.dataset.branchAddress || "",
            branch_phone: row.dataset.branchPhone || "",
            branch_gst: row.dataset.branchGst || ""
        });

        fetch(`/customer/invoice-data/${currentSaleId}/`, {
            cache: "no-store",
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                populateModalData(data);
            }
        })
        .catch(err => {
            console.error("Invoice data fetch error:", err);
        });

        if (invoiceModal) invoiceModal.style.display = "flex";
    }

    function closeModal() {
        if (invoiceModal) invoiceModal.style.display = "none";
        currentSaleId = null;
    }

    document.addEventListener("click", function (e) {
        const viewBtn = e.target.closest(".view-invoice-btn");
        if (viewBtn) {
            const row = viewBtn.closest("tr");
            openInvoiceModal(row);
        }
    });

    if (closeInvoiceModal) closeInvoiceModal.addEventListener("click", closeModal);
    if (closeInvoiceFooterBtn) closeInvoiceFooterBtn.addEventListener("click", closeModal);

    if (invoiceModal) {
        invoiceModal.addEventListener("click", function (e) {
            if (e.target === invoiceModal) closeModal();
        });
    }

    // -------------------------------------------------------------
    // ✏️ 3. Edit Button Handler (Navigates to /sales/?edit=<sale_id>)
    // -------------------------------------------------------------
    if (editInvoiceBtn) {
        editInvoiceBtn.addEventListener("click", function () {
            if (!currentSaleId) {
                alert("Unable to identify this sale.");
                return;
            }
            const targetSaleId = currentSaleId;
            closeModal();
            window.location.href = `/sales/?edit=${targetSaleId}`;
        });
    }

    // -------------------------------------------------------------
    // 🖨️ 4. Print Invoice Handler
    // -------------------------------------------------------------
    if (printInvoiceBtn) {
        printInvoiceBtn.addEventListener("click", function () {
            const printableArea = document.getElementById("printable-invoice-container");
            if (!printableArea) {
                alert("Invoice area not found.");
                return;
            }

            const printClone = printableArea.cloneNode(true);
            const accessoriesRow = printClone.querySelector("#invAccessoriesLine");
            const vehicleSpecs = printClone.querySelector("#invVehicleSpecs");
            const showAccessories = accessoriesRow && accessoriesRow.style.display !== "none";
            if (showAccessories) {
                accessoriesRow.classList.add("print-accessories-row");
                vehicleSpecs?.classList.add("print-accessories-divider");
            } else {
                accessoriesRow?.classList.add("print-accessories-hidden");
            }

            const invoiceTable = printClone.querySelector("table");
            if (invoiceTable) {
                const tableWrapper = document.createElement("div");
                tableWrapper.className = "table-responsive-wrapper";
                invoiceTable.replaceWith(tableWrapper);
                tableWrapper.appendChild(invoiceTable);
            }

            // Adapt only this print clone to the Sales invoice structure/classes.
            const [header, customerSection, tableWrapper, specs, summary, footer, terms] = Array.from(printClone.children);
            printClone.className = "invoice-preview-wrapper";
            printClone.removeAttribute("style");

            if (header) {
                header.className = "bill-header";
                const [headerLeft, headerRight] = Array.from(header.children);
                if (headerLeft) {
                    headerLeft.className = "header-left";
                    headerLeft.querySelector("h2")?.classList.add("comp-title");
                }
                if (headerRight) {
                    headerRight.className = "header-right";
                    headerRight.querySelector("img")?.classList.add("bill-logo");
                    const metaInfo = document.createElement("div");
                    metaInfo.className = "meta-info";
                    Array.from(headerRight.querySelectorAll(":scope > p")).forEach((line) => metaInfo.appendChild(line));
                    headerRight.appendChild(metaInfo);
                }
            }

            if (customerSection) {
                customerSection.className = "bill-to-box";
                customerSection.children[0]?.classList.add("bill-to-row");
                customerSection.children[1]?.classList.add("customer-info-grid");
                const contactRow = customerSection.children[2];
                if (contactRow && customerSection.children[1]) {
                    customerSection.children[1].appendChild(contactRow);
                }
            }

            tableWrapper?.querySelector("table")?.classList.add("bill-table");
            specs?.classList.add("vehicle-specs-box");
            specs?.firstElementChild?.classList.add("vehicle-specs-content");
            summary?.classList.add("table-summary-bar");
            summary?.firstElementChild?.classList.add("sum-title");
            summary?.lastElementChild?.classList.add("sum-values");
            footer?.classList.add("bill-footer-flex");
            footer?.children[0]?.classList.add("payment-box");
            footer?.children[0]?.children[0]?.classList.add("payment-header-bar");
            footer?.children[0]?.children[1]?.classList.add("payment-val");
            footer?.children[1]?.classList.add("totals-calculation-box");
            footer?.children[1]?.lastElementChild?.classList.add("final-amount-text");
            terms?.classList.add("terms-sig-flex");
            terms?.children[0]?.classList.add("terms-box");
            terms?.children[1]?.classList.add("signature-box");

            // Remove preview-only inline styling so the Sales invoice CSS controls print appearance.
            printClone.querySelectorAll("[style]").forEach((element) => element.removeAttribute("style"));
            if (!showAccessories) accessoriesRow?.classList.add("print-accessories-hidden");

            const border = document.createElement("div");
            border.className = "bill-outer-border";
            while (printClone.firstChild) border.appendChild(printClone.firstChild);
            printClone.appendChild(border);

            const printWrapper = document.createElement("div");
            printWrapper.className = "print-wrapper";
            printWrapper.appendChild(printClone);

            const printWindow = window.open("", "_blank", "width=900,height=1200");
            if (!printWindow) {
                alert("Please allow popups for printing.");
                return;
            }

            const styleSheets = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
                .map((sheet) => sheet.outerHTML)
                .join("\n");
            const salesStylesheet = document.querySelector('link[rel="stylesheet"][href*="/css/sales.css"]')
                ? ""
                : '<link rel="stylesheet" href="/static/css/sales.css">';

            printWindow.document.open();
            printWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Invoice Print</title>
                    ${styleSheets}
                    ${salesStylesheet}
                    <style>
                        @page { size: A4 portrait; margin: 0; }
                        html, body { margin: 0; padding: 0; width: 210mm; height: 297mm; background: #fff; overflow: hidden; }
                        .print-wrapper { display: block !important; width: 210mm !important; height: 297mm !important; box-sizing: border-box !important; padding: 10mm 5mm 5mm 5mm !important; margin: 0 !important; }
                        #printable-invoice-container { box-sizing: border-box !important; width: 190mm !important; max-width: 190mm !important; min-width: 200mm !important; margin: 0 auto !important; display: block !important; transform-origin: top center !important; transform: scale(1, 1.35); }
                        table { width: 100%; max-width: 100%; border-collapse: collapse; table-layout: fixed; box-sizing: border-box; }
                        th, td { border: 1.5px solid #000000 !important; border-collapse: collapse !important; padding: 8px 5px; font-size: 10px !important; line-height: 1.3; vertical-align: middle; word-wrap: break-word; overflow-wrap: break-word; text-align: center; }
                        th { font-weight: 600; background: #f2f2f2; }
                        #printable-invoice-container .bill-logo { width: auto !important; height: 70px !important; max-height: none !important; object-fit: contain !important; transform: scale(1.43, 1.25); transform-origin: top right; position: relative; top: -14px; }
                        #printable-invoice-container tbody tr:first-child > td:nth-child(2) { text-align: left !important; }
                        .print-accessories-row > td { border-bottom: 0 !important; }
                        .print-accessories-hidden { display: none !important; }
                        .print-accessories-divider { border-top: 1.5px solid #000000 !important; }
                        .bill-header, .bill-to-box, .inv-payment-summary-flex{ margin: 8px 0 !important; page-break-inside: avoid; break-inside: avoid; }
                        .bill-table { margin: 8px 0 1px 0 !important; page-break-inside: avoid; break-inside: avoid; }
                        .bill-table th:nth-child(1) { width: 7% !important; }
                        .bill-table th:nth-child(2) { width: 32% !important; }
                        .bill-table th:nth-child(3) { width: 12% !important; }
                        .bill-table th:nth-child(4) { width: 9% !important; }
                        .bill-table th:nth-child(5) { width: 6% !important; }
                        .bill-table th:nth-child(6) { width: 12% !important; }
                        .bill-table th:nth-child(7) { width: 10% !important; }
                        .bill-table th:nth-child(8) { width: 12% !important; }
                        .table-summary-bar { width: 100% !important; border-top: 0.5px solid #000 !important; box-sizing: border-box !important; }
                        .vehicle-specs-box { margin: 0 !important; }
                        .vehicle-specs-content { display: flex !important; flex-direction: column !important; gap: 4px !important; }
                        .bill-outer-border { border: 1px solid #000; padding: 8mm; box-sizing: border-box; }
                        .grand-total { font-weight: 700; font-size: 11px; border-top: 1px solid #000; padding-top: 3px; }
                        .terms-sig-flex { display: flex !important; justify-content: space-between !important; align-items: flex-end !important; width: 100% !important; margin: 10px 0 0 0 !important; padding: 0 !important; text-align: left !important; page-break-inside: avoid !important; break-inside: avoid !important; }
                        .terms-box { width: 58% !important; flex: 0 0 58% !important; margin: 0 !important; padding: 0 !important; text-align: left !important; font-size: 10px !important; }
                        .terms-box strong { display: block !important; width: 100% !important; margin: 0 0 4px 0 !important; padding: 0 !important; text-align: left !important; }
                        .terms-box ul { display: block !important; width: 100% !important; margin: 0 !important; padding: 0 !important; text-align: left !important; list-style: none !important; }
                        .terms-box li, .terms-box ul > div { display: block !important; width: 100% !important; margin: 0 0 3px 0 !important; padding: 0 !important; text-align: left !important; white-space: normal !important; clear: both !important; }
                        .terms-box ul > div { white-space: pre-line !important; }
                        .terms-box li::before { content: "• " !important; }
                        .signature-box { width: 38% !important; flex: 0 0 38% !important; margin: 0 !important; padding: 0 !important; text-align: center !important; }
                        .signature-box > div:first-child { height: 45px !important; }
                        .signature-box > div:last-child { border-top: 1px solid #000 !important; padding-top: 3px !important; }
                        .popup-actions-v2, .invoice-modal-close-icon, .sales-page-container, .toast-notification, .modal-close, button, input, select, textarea, ::-webkit-scrollbar { display: none !important; }
                        * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                    </style>
                </head>
                <body>
                    ${printWrapper.outerHTML}
                </body>
                </html>
            `);

            printWindow.document.close();
            printWindow.focus();

            setTimeout(() => {
                const printLogo = printWindow.document.querySelector("#printable-invoice-container .bill-logo");
                const printInvoice = () => {
                    if (printLogo && printLogo.naturalWidth > 0) {
                        const currentVisualWidth = printLogo.getBoundingClientRect().width;
                        printLogo.style.width = `${(currentVisualWidth + 10) / 1.43}px`;
                        printLogo.style.objectFit = "fill";
                    }
                    printWindow.print();
                    setTimeout(() => {
                        printWindow.close();
                    }, 500);
                };

                if (printLogo && !printLogo.complete) {
                    printLogo.addEventListener("load", printInvoice, { once: true });
                    printLogo.addEventListener("error", printInvoice, { once: true });
                } else {
                    printInvoice();
                }
            }, 700);
        });
    }

    // -------------------------------------------------------------
    // 📱 5. WhatsApp Share Flow
    // -------------------------------------------------------------
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async function shareWhatsApp(saleId) {
        if (!saleId) {
            alert("Unable to identify this sale ID.");
            return;
        }

        try {
            const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfToken = csrfElement ? csrfElement.value : getCookie("csrftoken");

            const invoiceResponse = await fetch(`/customer/invoice-data/${saleId}/`, {
                method: "GET",
                cache: "no-store",
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });

            if (!invoiceResponse.ok) {
                throw new Error(`Invoice data request failed: ${invoiceResponse.status}`);
            }

            const invoiceData = await invoiceResponse.json();
            if (invoiceData.status !== "success") {
                throw new Error(invoiceData.message || "Unable to retrieve invoice data.");
            }

            const invoiceNo = invoiceData.invoice_no || `INV-${saleId}`;
            const customerName = invoiceData.customer_name || "Customer";
            const safeCustomerName = customerName.toString().trim().replace(/[^\w\-]+/g, "_");
            const pdfFileName = `${safeCustomerName}-${invoiceNo}.pdf`;

            const pdfResponse = await fetch(`/invoice/pdf/${saleId}/`, {
                method: "GET",
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });

            if (!pdfResponse.ok) {
                showInvoicePopup("Please Create Sales PDF first");
                return;
            }

            const pdfBlob = await pdfResponse.blob();
            if (!pdfBlob || pdfBlob.size === 0 || pdfBlob.type !== "application/pdf") {
                throw new Error("Generated PDF is empty or invalid.");
            }

            const formData = new FormData();
            formData.append("pdf_file", pdfBlob, pdfFileName);

            const uploadResponse = await fetch(`/sales/upload-pdf/${saleId}/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error("Invoice PDF upload failed.");
            }

            const uploadResult = await uploadResponse.json();
            if (uploadResult.status !== "success") {
                throw new Error(uploadResult.message || "Invoice PDF could not be saved.");
            }

            const whatsappResponse = await fetch(`/sales/whatsapp-share/${saleId}/`, {
                method: "GET",
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });

            if (!whatsappResponse.ok) {
                throw new Error("WhatsApp endpoint failed.");
            }

            const whatsappData = await whatsappResponse.json();
            if (whatsappData.status !== "success") {
                throw new Error(whatsappData.message || "Invoice PDF is not available.");
            }

            if (whatsappData.invoice_url) {
                const downloadLink = document.createElement("a");
                downloadLink.href = whatsappData.invoice_url;
                downloadLink.download = whatsappData.invoice_filename || pdfFileName;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
            }

            if (whatsappData.whatsapp_url) {
                setTimeout(() => {
                    window.open(whatsappData.whatsapp_url, "_blank");
                }, 500);
            }

        } catch (error) {
            console.error("CUSTOMER INVOICE ERROR:", error);

            showInvoicePopup(
                error.message || "Error generating or sharing invoice."
            );
        }
    }

    if (whatsappModalBtn) {
        whatsappModalBtn.addEventListener("click", function () {
            if (currentSaleId) {
                shareWhatsApp(currentSaleId);
            } else {
                alert("Unable to identify this sale.");
            }
        });
    }

    // -------------------------------------------------------------
    // 🗑️ 6. Delete Bill (Permanent) Flow
    // -------------------------------------------------------------
    const deleteBillModal = document.getElementById("deleteBillModal");
    const cancelDeleteBillBtn = document.getElementById("cancelDeleteBillBtn");
    const confirmDeleteBillBtn = document.getElementById("confirmDeleteBillBtn");
    const deleteInvoiceBtn = document.getElementById("deleteInvoiceBtn");

    let pendingDeleteSaleId = null;
    let pendingDeleteRow = null;

    function showResultPopup(message, isSuccess) {
        const existingPopup = document.getElementById("billResultPopup");
        if (existingPopup) existingPopup.remove();

        const popup = document.createElement("div");
        popup.id = "billResultPopup";

        popup.innerHTML = `
            <div class="invoice-message-backdrop">
                <div class="invoice-message-box">
                    <div class="invoice-message-icon" style="${isSuccess ? 'background:#dcfce7;color:#16a34a;' : ''}">${isSuccess ? '&#10003;' : '!'}</div>
                    <div class="invoice-message-title"></div>
                    <button type="button" id="billResultOk">OK</button>
                </div>
            </div>
        `;

        popup.querySelector(".invoice-message-title").textContent = message;

        document.body.appendChild(popup);

        const okButton = document.getElementById("billResultOk");
        if (okButton) {
            okButton.addEventListener("click", function () {
                popup.remove();
            });
        }
    }

    function openDeleteBillModal(saleId, rowEl) {
        if (!saleId) {
            alert("Unable to identify this bill.");
            return;
        }
        pendingDeleteSaleId = saleId;
        pendingDeleteRow = rowEl || (customerTable ? customerTable.querySelector(`tr[data-sale-id="${saleId}"]`) : null);
        if (deleteBillModal) deleteBillModal.style.display = "flex";
    }

    function closeDeleteBillModal() {
        if (deleteBillModal) deleteBillModal.style.display = "none";
        pendingDeleteSaleId = null;
        pendingDeleteRow = null;
    }

    async function confirmDeleteBill() {
        if (!pendingDeleteSaleId) {
            closeDeleteBillModal();
            return;
        }

        const saleId = pendingDeleteSaleId;
        const rowEl = pendingDeleteRow;

        if (confirmDeleteBillBtn) {
            confirmDeleteBillBtn.disabled = true;
            confirmDeleteBillBtn.textContent = "Deleting...";
        }

        try {
            const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfToken = csrfElement ? csrfElement.value : getCookie("csrftoken");

            const response = await fetch(`/customer/delete-bill/${saleId}/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            const result = await response.json();

            if (!response.ok || result.status !== "success") {
                throw new Error(result.message || "Unable to delete this bill.");
            }

            // Bill is gone -- remove its row so it no longer appears,
            // without needing a full page reload.
            if (rowEl && rowEl.parentNode) {
                rowEl.parentNode.removeChild(rowEl);
            }

            // If the invoice preview modal is open for the bill we just
            // deleted, close it too.
            if (currentSaleId && String(currentSaleId) === String(saleId)) {
                closeModal();
            }

            closeDeleteBillModal();
            showResultPopup(result.message || "Bill deleted successfully.", true);

        } catch (error) {
            console.error("DELETE BILL ERROR:", error);
            closeDeleteBillModal();
            showResultPopup(error.message || "Error deleting bill.", false);
        } finally {
            if (confirmDeleteBillBtn) {
                confirmDeleteBillBtn.disabled = false;
                confirmDeleteBillBtn.textContent = "Delete";
            }
        }
    }

    // Delete button on each row of the Customer Directory table.
    document.addEventListener("click", function (e) {
        const delBtn = e.target.closest(".delete-bill-btn");
        if (delBtn) {
            const row = delBtn.closest("tr");
            openDeleteBillModal(row ? row.dataset.saleId : delBtn.dataset.id, row);
        }
    });

    // Delete button inside the Invoice Preview modal footer.
    if (deleteInvoiceBtn) {
        deleteInvoiceBtn.addEventListener("click", function () {
            if (!currentSaleId) {
                alert("Unable to identify this sale.");
                return;
            }
            openDeleteBillModal(currentSaleId, null);
        });
    }

    if (cancelDeleteBillBtn) cancelDeleteBillBtn.addEventListener("click", closeDeleteBillModal);
    if (confirmDeleteBillBtn) confirmDeleteBillBtn.addEventListener("click", confirmDeleteBill);

    if (deleteBillModal) {
        deleteBillModal.addEventListener("click", function (e) {
            if (e.target === deleteBillModal) closeDeleteBillModal();
        });
    }
});
