document.addEventListener('DOMContentLoaded', function () {
    // CSRF Helper for Django AJAX
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
    const csrftoken = getCookie('csrftoken');

    let modelsData = [];
    let colorsData = [];

    try {
        const modelsEl = document.getElementById('django-models-data');
        if (modelsEl) modelsData = JSON.parse(modelsEl.textContent);

        const colorsEl = document.getElementById('django-colors-data');
        if (colorsEl) colorsData = JSON.parse(colorsEl.textContent);
    } catch (err) {
        console.error("Error reading JSON from server:", err);
    }

    const supplierSelect = document.getElementById('id_supplier');
    const contactPersonInput = document.getElementById('id_contact_person');
    const phoneInput = document.getElementById('id_phone');

    const companySelect = document.getElementById('entry_company');
    const modelSelect = document.getElementById('entry_model');
    const qtyInput = document.getElementById('entry_quantity');
    const amountInput = document.getElementById('entry_total_amount');
    const btnAddVehicle = document.getElementById('btnAddVehicleRow');

    const vehicleItemsTbody = document.getElementById('vehicleItemsTbody');
    const emptyRow = document.getElementById('emptyRow');
    const hiddenJsonInput = document.getElementById('id_vehicle_items_json');

    const summaryTotalQty = document.getElementById('summaryTotalQty');
    const summaryTotalAmount = document.getElementById('summaryTotalAmount');
    const btnSavePurchase = document.getElementById('btnSavePurchase');

    // Modals & Triggers
    const modalAddSupplier = document.getElementById('modalAddSupplier');
    const modalAddCompany = document.getElementById('modalAddCompany');
    const modalAddModel = document.getElementById('modalAddModel');
    const modalAddColor = document.getElementById('modalAddColor');

    let vehicleItems = [];
    let activeItemForNewColor = null;

    // --- Modal Logic Helper ---
    function openModal(modal) { if(modal) modal.style.display = 'block'; }
    function closeModal(modal) { if(modal) modal.style.display = 'none'; }

    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', function() {
            this.closest('.custom-modal').style.display = 'none';
        });
    });

    // 1. Supplier Auto-fill & +Add New Supplier Trigger
    if (supplierSelect) {
        supplierSelect.addEventListener('change', function () {
            if (this.value === '__add_new__') {
                this.value = '';
                openModal(modalAddSupplier);
                return;
            }
            const selectedOpt = this.options[this.selectedIndex];
            if (selectedOpt && selectedOpt.value) {
                contactPersonInput.value = selectedOpt.getAttribute('data-contact') || '';
                phoneInput.value = selectedOpt.getAttribute('data-phone') || '';
            } else {
                contactPersonInput.value = '';
                phoneInput.value = '';
            }
        });
    }

    // Save New Supplier AJAX
    document.getElementById('btnSaveNewSupplier')?.addEventListener('click', function() {
        const name = document.getElementById('new_supplier_name').value.trim();
        const contact = document.getElementById('new_supplier_contact').value.trim();
        const phone = document.getElementById('new_supplier_phone').value.trim();

        if (!name) return alert('Please enter Supplier Name.');

        fetch('/ajax/add-supplier/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrftoken
            },
            body: `supplier_name=${encodeURIComponent(name)}&contact_person=${encodeURIComponent(contact)}&phone=${encodeURIComponent(phone)}`
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const opt = document.createElement('option');
                opt.value = data.id;
                opt.textContent = data.name;
                opt.setAttribute('data-contact', data.contact);
                opt.setAttribute('data-phone', data.phone);
                
                supplierSelect.appendChild(opt);
                supplierSelect.value = data.id;
                supplierSelect.dispatchEvent(new Event('change'));
                
                closeModal(modalAddSupplier);
                document.getElementById('new_supplier_name').value = '';
                document.getElementById('new_supplier_contact').value = '';
                document.getElementById('new_supplier_phone').value = '';
            } else {
                alert(data.error || 'Failed to save supplier.');
            }
        });
    });

    // 2. Company Change & +Add New Company Trigger
    if (companySelect) {
        companySelect.addEventListener('change', function () {
            if (this.value === '__add_new__') {
                this.value = '';
                openModal(modalAddCompany);
                return;
            }

            const selectedCompanyId = parseInt(this.value);
            modelSelect.innerHTML = '<option value="">Select Model</option><option value="__add_new__" class="add-new-option-style">+ Add New Model</option>';

            if (selectedCompanyId) {
                const filteredModels = modelsData.filter(m => m.company_id === selectedCompanyId);
                filteredModels.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.model_name;
                    modelSelect.appendChild(opt);
                });
                modelSelect.disabled = false;
            } else {
                modelSelect.disabled = true;
            }
        });
    }

    // Save New Company AJAX
    document.getElementById('btnSaveNewCompany')?.addEventListener('click', function() {
        const name = document.getElementById('new_company_name').value.trim();
        if (!name) return alert('Please enter Company Name.');

        fetch('/ajax/add-company/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrftoken
            },
            body: `company_name=${encodeURIComponent(name)}`
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const opt = document.createElement('option');
                opt.value = data.id;
                opt.textContent = data.name;
                
                companySelect.appendChild(opt);
                companySelect.value = data.id;
                companySelect.dispatchEvent(new Event('change'));
                
                closeModal(modalAddCompany);
                document.getElementById('new_company_name').value = '';
            } else {
                alert(data.error || 'Failed to save company.');
            }
        });
    });

    // 3. Model Change & +Add New Model Trigger
    if (modelSelect) {
        modelSelect.addEventListener('change', function() {
            if (this.value === '__add_new__') {
                this.value = '';
                const compText = companySelect.options[companySelect.selectedIndex]?.text;
                document.getElementById('new_model_company_display').value = compText || '';
                openModal(modalAddModel);
            }
        });
    }

    // Save New Model AJAX
    document.getElementById('btnSaveNewModel')?.addEventListener('click', function() {
        const name = document.getElementById('new_model_name').value.trim();
        const companyId = companySelect.value;

        if (!name || !companyId) return alert('Model name & company selection required.');

        fetch('/ajax/add-model/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrftoken
            },
            body: `company_id=${companyId}&model_name=${encodeURIComponent(name)}`
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                modelsData.push({ id: data.id, model_name: data.name, company_id: parseInt(data.company_id) });

                const opt = document.createElement('option');
                opt.value = data.id;
                opt.textContent = data.name;
                
                modelSelect.appendChild(opt);
                modelSelect.value = data.id;
                
                closeModal(modalAddModel);
                document.getElementById('new_model_name').value = '';
            } else {
                alert(data.error || 'Failed to save model.');
            }
        });
    });

    // 4. Color Add AJAX
    document.getElementById('btnSaveNewColor')?.addEventListener('click', function() {
        const name = document.getElementById('new_color_name').value.trim();
        const hex = document.getElementById('new_color_hex').value;

        if (!name) return alert('Please enter Color Name.');

        fetch('/ajax/add-color/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrftoken
            },
            body: `color_name=${encodeURIComponent(name)}&color_hex=${encodeURIComponent(hex)}`
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const newColorObj = { id: data.id, color_name: data.name, color_hex: data.hex };
                colorsData.push(newColorObj);

                // Add to existing table items
                vehicleItems.forEach(item => {
                    item.color_allocations.push({
                        color_id: data.id,
                        color_name: data.name,
                        color_hex: data.hex,
                        quantity: 0
                    });
                });

                renderVehicleTable();
                closeModal(modalAddColor);
                document.getElementById('new_color_name').value = '';
            } else {
                alert(data.error || 'Failed to save color.');
            }
        });
    });

    // Add Vehicle to List
    if (btnAddVehicle) {
        btnAddVehicle.addEventListener('click', function () {
            const companyId = companySelect.value;
            const companyText = companySelect.options[companySelect.selectedIndex]?.text || '';
            const modelId = modelSelect.value;
            const modelText = modelSelect.options[modelSelect.selectedIndex]?.text || '';
            const totalQty = parseInt(qtyInput.value);
            const totalAmount = parseFloat(amountInput.value);

            if (!companyId || !modelId || isNaN(totalQty) || totalQty <= 0 || isNaN(totalAmount) || totalAmount < 0) {
                alert('Please select Company, Model, Total Quantity, and Total Amount.');
                return;
            }

            let initialColors = colorsData.map(c => ({
                color_id: c.id,
                color_name: c.color_name,
                color_hex: c.color_hex,
                quantity: 0
            }));

            const item = {
                id: Date.now(),
                company_id: companyId,
                company_name: companyText,
                model_id: modelId,
                model_name: modelText,
                total_qty: totalQty,
                total_amount: totalAmount,
                color_allocations: initialColors
            };

            vehicleItems.push(item);

            companySelect.value = '';
            modelSelect.value = '';
            modelSelect.disabled = true;
            qtyInput.value = '';
            amountInput.value = '';

            renderVehicleTable();
        });
    }

    function renderVehicleTable() {
        if (vehicleItems.length === 0) {
            emptyRow.style.display = '';
            vehicleItemsTbody.innerHTML = '';
            vehicleItemsTbody.appendChild(emptyRow);
            summaryTotalQty.textContent = '0';
            summaryTotalAmount.textContent = '₹ 0';
            btnSavePurchase.disabled = true;
            hiddenJsonInput.value = '[]';
            return;
        }

        emptyRow.style.display = 'none';
        vehicleItemsTbody.innerHTML = '';

        let grandTotalQty = 0;
        let grandTotalAmount = 0;

        vehicleItems.forEach((item, index) => {
            grandTotalQty += item.total_qty;
            grandTotalAmount += item.total_amount;

            const allocatedCount = item.color_allocations.reduce((sum, c) => sum + (parseInt(c.quantity) || 0), 0);
            const activeColorsCount = item.color_allocations.filter(c => c.quantity > 0).length;
            const remainingQty = item.total_qty - allocatedCount;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${index + 1}</td>
                <td>${item.company_name}</td>
                <td>${item.model_name}</td>
                <td>${item.total_qty}</td>
                <td>${item.total_amount.toLocaleString('en-IN')}</td>
                <td><span class="color-pill-badge">${activeColorsCount} Colors</span></td>
                <td class="text-center">
                    <button type="button" class="btn-action-icon text-danger btn-delete-item" data-id="${item.id}" title="Delete Row">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </td>
            `;
            vehicleItemsTbody.appendChild(tr);

            const nestedTr = document.createElement('tr');
            const nestedTd = document.createElement('td');
            nestedTd.colSpan = 7;
            nestedTd.style.padding = '0 12px 10px 12px';

            let colorsRowsHtml = '';
            item.color_allocations.forEach((colorObj) => {
                colorsRowsHtml += `
                    <tr>
                        <td>
                            <div class="color-name-group">
                                <span class="color-dot-circle" style="background-color: ${colorObj.color_hex || '#000'};"></span>
                                <span>${colorObj.color_name}</span>
                            </div>
                        </td>
                        <td>
                            <input type="number" class="form-input sm-qty-input color-qty-input" 
                                   data-item-id="${item.id}" data-color-id="${colorObj.color_id}" 
                                   value="${colorObj.quantity}" min="0" max="${item.total_qty}">
                        </td>
                        <td>
                            <button type="button" class="btn-action-icon text-danger btn-clear-color" data-item-id="${item.id}" data-color-id="${colorObj.color_id}">
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                        </td>
                    </tr>
                `;
            });

            nestedTd.innerHTML = `
                <div class="nested-color-container">
                    <div class="nested-color-header">
                        <span class="nested-header-title">Color Wise Quantity (Total Qty: ${item.total_qty})</span>
                        <div class="nested-header-stats">
                            <button type="button" class="btn-add-color-inline btn-trigger-add-color">+ Add New Color</button>
                            <span>Allocated: <strong>${allocatedCount}</strong></span>
                            <span>Remaining: <strong class="${remainingQty === 0 ? 'text-green' : 'text-danger-bold'}">${remainingQty}</strong></span>
                        </div>
                    </div>
                    <table class="nested-color-table">
                        <thead>
                            <tr>
                                <th>Color</th>
                                <th>Quantity</th>
                                <th style="width: 40px;">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${colorsRowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
            nestedTr.appendChild(nestedTd);
            vehicleItemsTbody.appendChild(nestedTr);
        });

        summaryTotalQty.textContent = grandTotalQty;
        summaryTotalAmount.textContent = '₹ ' + grandTotalAmount.toLocaleString('en-IN');
        hiddenJsonInput.value = JSON.stringify(vehicleItems);
        btnSavePurchase.disabled = false;

        attachEvents();
    }

    function attachEvents() {
        document.querySelectorAll('.btn-delete-item').forEach(btn => {
            btn.addEventListener('click', function () {
                const itemId = parseInt(this.getAttribute('data-id'));
                vehicleItems = vehicleItems.filter(i => i.id !== itemId);
                renderVehicleTable();
            });
        });

        document.querySelectorAll('.btn-trigger-add-color').forEach(btn => {
            btn.addEventListener('click', function () {
                openModal(modalAddColor);
            });
        });

        document.querySelectorAll('.color-qty-input').forEach(input => {
            input.addEventListener('input', function () {
                const itemId = parseInt(this.getAttribute('data-item-id'));
                const colorId = parseInt(this.getAttribute('data-color-id'));
                const newQty = parseInt(this.value) || 0;

                const item = vehicleItems.find(i => i.id === itemId);
                if (item) {
                    const colorObj = item.color_allocations.find(c => c.color_id === colorId);
                    if (colorObj) colorObj.quantity = newQty;
                    renderVehicleTable();
                }
            });
        });

        document.querySelectorAll('.btn-clear-color').forEach(btn => {
            btn.addEventListener('click', function () {
                const itemId = parseInt(this.getAttribute('data-item-id'));
                const colorId = parseInt(this.getAttribute('data-color-id'));

                const item = vehicleItems.find(i => i.id === itemId);
                if (item) {
                    const colorObj = item.color_allocations.find(c => c.color_id === colorId);
                    if (colorObj) colorObj.quantity = 0;
                    renderVehicleTable();
                }
            });
        });
    }

    // Photo Dropzone Handling
    const dropzoneBox = document.getElementById('dropzoneBox');
    const photoInput = document.getElementById('id_invoice_photo');
    const uploadedFileBar = document.getElementById('uploadedFileBar');
    const fileNameText = document.getElementById('fileNameText');
    const fileSizeText = document.getElementById('fileSizeText');
    const btnViewPhoto = document.getElementById('btnViewPhoto');
    const btnDownloadPhoto = document.getElementById('btnDownloadPhoto');
    const btnDeletePhoto = document.getElementById('btnDeletePhoto');
    const photoModal = document.getElementById('photoViewModal');
    const modalPreviewImage = document.getElementById('modalPreviewImage');

    if (dropzoneBox && photoInput) {
        dropzoneBox.addEventListener('click', () => photoInput.click());

        photoInput.addEventListener('change', function () {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                fileNameText.textContent = file.name;
                fileSizeText.textContent = (file.size / 1024).toFixed(1) + ' KB';

                const reader = new FileReader();
                reader.onload = function (e) {
                    modalPreviewImage.src = e.target.result;
                    if (btnDownloadPhoto) btnDownloadPhoto.href = e.target.result;
                };
                reader.readAsDataURL(file);

                uploadedFileBar.classList.remove('d-none');
            }
        });

        if (btnDeletePhoto) {
            btnDeletePhoto.addEventListener('click', function (e) {
                e.stopPropagation();
                photoInput.value = '';
                fileNameText.textContent = '';
                fileSizeText.textContent = '';
                modalPreviewImage.src = '';
                uploadedFileBar.classList.add('d-none');
            });
        }

        if (btnViewPhoto && photoModal) {
            btnViewPhoto.addEventListener('click', function (e) {
                e.stopPropagation();
                openModal(photoModal);
            });
        }
    }
});