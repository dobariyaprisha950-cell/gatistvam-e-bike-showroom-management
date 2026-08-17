/**
 * Purchase Page Controller
 * Strictly Database-Driven with Real Django Backend REST APIs & Views
 */

document.addEventListener('DOMContentLoaded', function () {
    // ==========================================
    // CSRF & API UTILITIES
    // ==========================================
    function getCsrfToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === 'csrftoken=') {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        if (!cookieValue) {
            const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
            if (csrfInput) cookieValue = csrfInput.value;
        }
        return cookieValue || '';
    }

    async function apiRequest(url, options = {}) {
        options.headers = options.headers || {};
        const csrfToken = getCsrfToken();
        if (csrfToken && !options.headers['X-CSRFToken']) {
            options.headers['X-CSRFToken'] = csrfToken;
        }

        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                let errorMsg = `Server error (${response.status})`;
                try {
                    const errData = await response.json();
                    if (errData.detail) {
                        errorMsg = errData.detail;
                    } else if (errData.error) {
                        errorMsg = errData.error;
                    } else if (typeof errData === 'object') {
                        errorMsg = Object.entries(errData)
                            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
                            .join(' | ');
                    }
                } catch (e) {
                    // Fallback if not JSON
                }
                throw new Error(errorMsg);
            }
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            return await response.text();
        } catch (error) {
            throw error;
        }
    }

    // ==========================================
    // STATE STORES (Strictly Database-Driven)
    // ==========================================
    let availableSuppliers = [];
    let availableModels = [];
    let availableColors = [];

    // Vehicle Entries Working Array
    let vehicleEntries = [];
    let editingEntryId = null;
    let pendingDeleteEntryId = null;
    let activeColorAllocEntryId = null;

    // Temporary working array inside Color Allocation Modal
    let currentModalColorRows = [];

    // ==========================================
    // DOM ELEMENTS
    // ==========================================
    const supplierSelect = document.getElementById('id_supplier');
    const invoiceNumberInput = document.getElementById('id_invoice_number');
    const invoiceDateInput = document.getElementById('id_invoice_date');

    const entryModelSelect = document.getElementById('entry_model');
    const entryQuantityInput = document.getElementById('entry_quantity');
    const entryUnitPriceInput = document.getElementById('entry_unit_price');
    const btnAddVehicleRow = document.getElementById('btnAddVehicleRow');
    const btnAddVehicleBtnText = document.getElementById('btnAddVehicleBtnText');
    const vehicleEntryError = document.getElementById('vehicleEntryError');

    const vehicleItemsTbody = document.getElementById('vehicleItemsTbody');
    const vehicleCardsMobile = document.getElementById('vehicleCardsMobile');

    const summaryTotalQty = document.getElementById('summaryTotalQty');
    const summaryTotalAmount = document.getElementById('summaryTotalAmount');
    const btnSavePurchase = document.getElementById('btnSavePurchase');
    const submitValidationError = document.getElementById('submitValidationError');
    const idVehicleItemsJson = document.getElementById('id_vehicle_items_json');

    // Modals
    const modalColorAllocation = document.getElementById('modalColorAllocation');
    const modalAddColor = document.getElementById('modalAddColor');
    const modalAddModel = document.getElementById('modalAddModel');
    const modalAddSupplier = document.getElementById('modalAddSupplier');
    const modalConfirmDelete = document.getElementById('modalConfirmDelete');
    const modalPurchaseSuccess = document.getElementById('modalPurchaseSuccess');

    // Color Modal Elements
    const modalAllocModelName = document.getElementById('modalAllocModelName');
    const modalAllocTotalQty = document.getElementById('modalAllocTotalQty');
    const modalAllocatedCount = document.getElementById('modalAllocatedCount');
    const modalRemainingCount = document.getElementById('modalRemainingCount');
    const colorRowsContainer = document.getElementById('colorRowsContainer');
    const colorModalError = document.getElementById('colorModalError');
    const btnAddColorRow = document.getElementById('btnAddColorRow');
    const btnSaveColorAllocation = document.getElementById('btnSaveColorAllocation');
    const btnCancelColorAllocation = document.getElementById('btnCancelColorAllocation');
    const btnCloseColorAllocationModal = document.getElementById('btnCloseColorAllocationModal');
    const btnOpenNewColorModal = document.getElementById('btnOpenNewColorModal');

    // ==========================================
    // INITIAL DATA LOADING
    // ==========================================
    async function loadInitialData() {
        // 1. Parse initial embedded database data if provided by Django template
        loadEmbeddedJsonData();

        // 2. Fetch real database records from REST API
        await Promise.all([
            fetchSuppliers(),
            fetchModels(),
            fetchColors()
        ]);

        renderVehicleTable();
        updateSummary();
    }

    function loadEmbeddedJsonData() {
        try {
            const modelsElem = document.getElementById('django-models-data');
            if (modelsElem && modelsElem.textContent.trim()) {
                const parsed = JSON.parse(modelsElem.textContent);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    availableModels = parsed;
                    populateModelSelect();
                }
            }
        } catch (e) {
            console.warn('Could not parse django-models-data:', e);
        }

        try {
            const colorsElem = document.getElementById('django-colors-data');
            if (colorsElem && colorsElem.textContent.trim()) {
                const parsed = JSON.parse(colorsElem.textContent);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    availableColors = parsed;
                }
            }
        } catch (e) {
            console.warn('Could not parse django-colors-data:', e);
        }
    }

    async function fetchSuppliers() {
        try {
            const data = await apiRequest('/yakuza/api/suppliers/');
            availableSuppliers = Array.isArray(data) ? data : (data.results || []);
            populateSupplierSelect();
        } catch (err) {
            try {
                const data = await apiRequest('/api/suppliers/');
                availableSuppliers = Array.isArray(data) ? data : (data.results || []);
                populateSupplierSelect();
            } catch (e) {
                console.error('Failed to fetch suppliers from database:', e);
            }
        }
    }

    async function fetchModels() {
        try {
            const data = await apiRequest('/yakuza/api/vehicle-models/');
            availableModels = Array.isArray(data) ? data : (data.results || []);
            populateModelSelect();
        } catch (err) {
            try {
                const data = await apiRequest('/api/vehicle-models/');
                availableModels = Array.isArray(data) ? data : (data.results || []);
                populateModelSelect();
            } catch (e) {
                console.error('Failed to fetch vehicle models from database:', e);
            }
        }
    }

    async function fetchColors() {
        try {
            const data = await apiRequest('/yakuza/api/vehicle-colors/');
            availableColors = Array.isArray(data) ? data : (data.results || []);
        } catch (err) {
            try {
                const data = await apiRequest('/api/vehicle-colors/');
                availableColors = Array.isArray(data) ? data : (data.results || []);
            } catch (e) {
                console.error('Failed to fetch vehicle colors from database:', e);
            }
        }
    }

    loadInitialData();

    // ==========================================
    // POPULATE DROPDOWNS DYNAMICALLY
    // ==========================================
    function populateSupplierSelect() {
        if (!supplierSelect) return;
        const currentVal = supplierSelect.value;
        supplierSelect.innerHTML = '<option value="">Select Supplier</option>';

        availableSuppliers.forEach(s => {
            const sName = s.supplier_name || s.name || s.company_name;
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = sName;
            supplierSelect.appendChild(opt);
        });

        const addNewOpt = document.createElement('option');
        addNewOpt.value = '__add_new__';
        addNewOpt.className = 'add-new-option-style';
        addNewOpt.textContent = '+ Add New Supplier';
        supplierSelect.appendChild(addNewOpt);

        if (currentVal && currentVal !== '__add_new__') {
            supplierSelect.value = currentVal;
        }
    }

    function populateModelSelect() {
        if (!entryModelSelect) return;
        const currentVal = entryModelSelect.value;
        entryModelSelect.innerHTML = '<option value="">Select Model</option>';

        availableModels.forEach(m => {
            const name = m.model_name || m.name;
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = name;
            entryModelSelect.appendChild(opt);
        });

        const addNewOpt = document.createElement('option');
        addNewOpt.value = '__add_new__';
        addNewOpt.className = 'add-new-option-style';
        addNewOpt.textContent = '+ Add New Model';
        entryModelSelect.appendChild(addNewOpt);

        if (currentVal && currentVal !== '__add_new__') {
            entryModelSelect.value = currentVal;
        }
    }

    // ==========================================
    // INVOICE PHOTO UPLOAD
    // ==========================================
    const dropzoneBox = document.getElementById('dropzoneBox');
    const fileInput = document.getElementById('id_invoice_photo');
    const uploadedFileBar = document.getElementById('uploadedFileBar');
    const fileNameText = document.getElementById('fileNameText');
    const fileSizeText = document.getElementById('fileSizeText');
    const btnDeletePhoto = document.getElementById('btnDeletePhoto');
    const btnViewPhoto = document.getElementById('btnViewPhoto');
    const btnDownloadPhoto = document.getElementById('btnDownloadPhoto');
    const photoViewModal = document.getElementById('photoViewModal');
    const modalPreviewImage = document.getElementById('modalPreviewImage');

    if (dropzoneBox && fileInput) {
        dropzoneBox.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', function () {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                fileNameText.textContent = file.name;
                fileSizeText.textContent = (file.size / 1024).toFixed(1) + ' KB';

                dropzoneBox.classList.add('d-none');
                uploadedFileBar.classList.remove('d-none');

                const reader = new FileReader();
                reader.onload = function (e) {
                    if (modalPreviewImage) modalPreviewImage.src = e.target.result;
                    if (btnDownloadPhoto) btnDownloadPhoto.href = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });

        if (btnDeletePhoto) {
            btnDeletePhoto.addEventListener('click', function () {
                fileInput.value = '';
                dropzoneBox.classList.remove('d-none');
                uploadedFileBar.classList.add('d-none');
                if (modalPreviewImage) modalPreviewImage.src = '';
            });
        }

        if (btnViewPhoto) {
            btnViewPhoto.addEventListener('click', function () {
                if (modalPreviewImage && modalPreviewImage.src) {
                    photoViewModal.classList.remove('d-none');
                }
            });
        }
    }

    // Modal Close Triggers
    document.querySelectorAll('.close-modal, .btn-secondary').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.custom-modal').forEach(m => m.classList.add('d-none'));
        });
    });

    // Dynamic Select Triggers
    if (supplierSelect) {
        supplierSelect.addEventListener('change', function () {
            if (this.value === '__add_new__') {
                if (modalAddSupplier) modalAddSupplier.classList.remove('d-none');
                this.value = '';
            }
        });
    }

    if (entryModelSelect) {
        entryModelSelect.addEventListener('change', function () {
            if (this.value === '__add_new__') {
                if (modalAddModel) modalAddModel.classList.remove('d-none');
                this.value = '';
            }
        });
    }

    // ==========================================
    // REAL DATABASE AJAX ADD SUPPLIER
    // ==========================================
    const btnSaveNewSupplier = document.getElementById('btnSaveNewSupplier');
    if (btnSaveNewSupplier) {
        btnSaveNewSupplier.addEventListener('click', async function () {
            const nameInput = document.getElementById('new_supplier_name');
            const errDiv = document.getElementById('supplierModalError');

            if (errDiv) errDiv.classList.add('d-none');

            const supplierName = nameInput ? nameInput.value.trim() : '';
            if (!supplierName) {
                if (errDiv) {
                    errDiv.textContent = 'Please enter a supplier name.';
                    errDiv.classList.remove('d-none');
                }
                return;
            }

            const payload = { supplier_name: supplierName, name: supplierName };

            try {
                let result = null;
                try {
                    result = await apiRequest('/yakuza/ajax/add-supplier/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } catch (e) {
                    result = await apiRequest('/ajax/add-supplier/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                await fetchSuppliers();
                const createdId = result.id || (result.supplier ? result.supplier.id : null);
                if (createdId) {
                    supplierSelect.value = createdId;
                } else if (availableSuppliers.length > 0) {
                    supplierSelect.value = availableSuppliers[availableSuppliers.length - 1].id;
                }

                if (nameInput) nameInput.value = '';
                if (modalAddSupplier) modalAddSupplier.classList.add('d-none');
            } catch (err) {
                if (errDiv) {
                    errDiv.textContent = err.message || 'Failed to add supplier to database.';
                    errDiv.classList.remove('d-none');
                }
            }
        });
    }

    // ==========================================
    // REAL DATABASE AJAX ADD MODEL
    // ==========================================
    const btnSaveNewModel = document.getElementById('btnSaveNewModel');
    if (btnSaveNewModel) {
        btnSaveNewModel.addEventListener('click', async function () {
            const input = document.getElementById('new_model_name');
            const errDiv = document.getElementById('modelModalError');

            if (errDiv) errDiv.classList.add('d-none');

            const modelName = input ? input.value.trim() : '';
            if (!modelName) {
                if (errDiv) {
                    errDiv.textContent = 'Please enter a vehicle model name.';
                    errDiv.classList.remove('d-none');
                }
                return;
            }

            const payload = { model_name: modelName, name: modelName };

            try {
                let result = null;
                try {
                    result = await apiRequest('/yakuza/ajax/add-model/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } catch (e) {
                    result = await apiRequest('/ajax/add-model/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                await fetchModels();
                const createdId = result.id || (result.model ? result.model.id : null);
                if (createdId) {
                    entryModelSelect.value = createdId;
                } else if (availableModels.length > 0) {
                    entryModelSelect.value = availableModels[availableModels.length - 1].id;
                }

                if (input) input.value = '';
                if (modalAddModel) modalAddModel.classList.add('d-none');
            } catch (err) {
                if (errDiv) {
                    errDiv.textContent = err.message || 'Failed to add vehicle model to database.';
                    errDiv.classList.remove('d-none');
                }
            }
        });
    }

    // ==========================================
    // REAL DATABASE AJAX ADD COLOR
    // ==========================================
    if (btnOpenNewColorModal) {
        btnOpenNewColorModal.addEventListener('click', function () {
            const colorInput = document.getElementById('new_color_name');
            const errDiv = document.getElementById('newColorError');
            if (colorInput) colorInput.value = '';
            if (errDiv) errDiv.classList.add('d-none');
            if (modalAddColor) modalAddColor.classList.remove('d-none');
        });
    }

    const btnSaveNewColor = document.getElementById('btnSaveNewColor');
    if (btnSaveNewColor) {
        btnSaveNewColor.addEventListener('click', async function () {
            const nameInput = document.getElementById('new_color_name');
            const hexInput = document.getElementById('new_color_hex');
            const errDiv = document.getElementById('newColorError');

            if (errDiv) errDiv.classList.add('d-none');

            const colorName = nameInput ? nameInput.value.trim() : '';
            if (!colorName) {
                if (errDiv) {
                    errDiv.textContent = 'Please enter a color name.';
                    errDiv.classList.remove('d-none');
                }
                return;
            }

            const payload = {
                color_name: colorName,
                color_hex: hexInput ? hexInput.value : '#2563eb'
            };

            try {
                let result = null;
                try {
                    result = await apiRequest('/yakuza/ajax/add-color/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } catch (e) {
                    result = await apiRequest('/ajax/add-color/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                await fetchColors();

                if (nameInput) nameInput.value = '';
                if (modalAddColor) modalAddColor.classList.add('d-none');

                renderModalColorRows();
            } catch (err) {
                if (errDiv) {
                    errDiv.textContent = err.message || 'Failed to add color to database.';
                    errDiv.classList.remove('d-none');
                }
            }
        });
    }

    const btnCancelAddColor = document.getElementById('btnCancelAddColor');
    const btnCloseAddColorModal = document.getElementById('btnCloseAddColorModal');
    if (btnCancelAddColor) btnCancelAddColor.addEventListener('click', () => modalAddColor.classList.add('d-none'));
    if (btnCloseAddColorModal) btnCloseAddColorModal.addEventListener('click', () => modalAddColor.classList.add('d-none'));

    // ==========================================
    // VEHICLE ENTRIES LOGIC
    // ==========================================
    if (btnAddVehicleRow) {
        btnAddVehicleRow.addEventListener('click', handleAddOrUpdateVehicle);
    }

    function handleAddOrUpdateVehicle() {
        if (vehicleEntryError) {
            vehicleEntryError.classList.add('d-none');
            vehicleEntryError.textContent = '';
        }

        const selectedModelId = entryModelSelect.value;
        const qtyVal = parseInt(entryQuantityInput.value, 10);
        const priceVal = parseFloat(entryUnitPriceInput.value);

        if (!selectedModelId || selectedModelId === '__add_new__') {
            showVehicleError('Please select a vehicle model.');
            return;
        }
        if (isNaN(qtyVal) || qtyVal < 1) {
            showVehicleError('Quantity must be at least 1.');
            return;
        }
        if (isNaN(priceVal) || priceVal <= 0) {
            showVehicleError('Purchase price must be greater than 0.');
            return;
        }

        const modelObj = availableModels.find(m => String(m.id) === String(selectedModelId));
        const modelName = modelObj ? (modelObj.model_name || modelObj.name) : 'Vehicle Model';
        const totalAmount = qtyVal * priceVal;

        if (editingEntryId !== null) {
            const entry = vehicleEntries.find(e => e.id === editingEntryId);
            if (entry) {
                entry.modelId = selectedModelId;
                entry.modelName = modelName;
                entry.quantity = qtyVal;
                entry.unitPrice = priceVal;
                entry.totalAmount = totalAmount;
            }
            editingEntryId = null;
            if (btnAddVehicleBtnText) btnAddVehicleBtnText.textContent = 'Add Vehicle Entry';
            btnAddVehicleRow.classList.remove('btn-editing');
        } else {
            vehicleEntries.push({
                id: 've_' + Date.now(),
                modelId: selectedModelId,
                modelName: modelName,
                quantity: qtyVal,
                unitPrice: priceVal,
                totalAmount: totalAmount,
                colorAllocations: []
            });
        }

        entryModelSelect.value = '';
        entryQuantityInput.value = '';
        entryUnitPriceInput.value = '';

        renderVehicleTable();
        updateSummary();
        syncHiddenJson();
    }

    function showVehicleError(msg) {
        if (vehicleEntryError) {
            vehicleEntryError.textContent = msg;
            vehicleEntryError.classList.remove('d-none');
        }
    }

    function formatINR(val) {
        return '₹ ' + Number(val).toLocaleString('en-IN', { maximumFractionDigits: 2 });
    }

    function renderVehicleTable() {
        if (!vehicleItemsTbody || !vehicleCardsMobile) return;

        vehicleItemsTbody.innerHTML = '';
        vehicleCardsMobile.innerHTML = '';

        if (vehicleEntries.length === 0) {
            vehicleItemsTbody.innerHTML = `
                <tr id="emptyRow">
                    <td colspan="6" class="empty-table-text">
                        No vehicle entries added yet. Select a model, quantity, and purchase price above.
                    </td>
                </tr>`;
            vehicleCardsMobile.innerHTML = `
                <div class="empty-card-text">
                    No vehicle entries added yet. Select a model, quantity, and purchase price above.
                </div>`;
            return;
        }

        vehicleEntries.forEach((entry, idx) => {
            const isAllocated = isColorAllocationComplete(entry);

            // Desktop Row
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align: center; font-weight: 600; color: #64748b;">${idx + 1}</td>
                <td><strong>${escapeHtml(entry.modelName)}</strong></td>
                <td style="text-align: center;"><strong>${entry.quantity}</strong></td>
                <td style="text-align: right;">${formatINR(entry.unitPrice)}</td>
                <td style="text-align: right; font-weight: 600; color: #0f172a;">${formatINR(entry.totalAmount)}</td>
                <td style="text-align: center;">
                    <div class="action-icon-group">
                        <button type="button" class="btn-icon-action btn-color-alloc ${isAllocated ? 'alloc-done' : ''}" data-id="${entry.id}" title="Color Allocation">
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"></circle><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"></circle><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"></circle><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"></circle><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.92 0 1.7-.71 1.7-1.63 0-.44-.18-.85-.47-1.16-.29-.3-.47-.72-.47-1.21 0-.92.72-1.63 1.63-1.63H16c3.31 0 6-2.69 6-6 0-4.97-4.48-9-10-9z"></path></svg>
                            ${isAllocated ? '<span class="alloc-badge-dot">✓</span>' : ''}
                        </button>
                        <button type="button" class="btn-icon-action btn-edit-action" data-id="${entry.id}" title="Edit Entry">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        </button>
                        <button type="button" class="btn-icon-action btn-delete-action" data-id="${entry.id}" title="Delete Entry">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </td>
            `;
            vehicleItemsTbody.appendChild(tr);

            // Mobile Card
            const card = document.createElement('div');
            card.className = 'vehicle-entry-card-item';
            card.innerHTML = `
                <div class="v-card-header">
                    <span class="v-card-title">#${idx + 1} ${escapeHtml(entry.modelName)}</span>
                    <div class="action-icon-group">
                        <button type="button" class="btn-icon-action btn-color-alloc ${isAllocated ? 'alloc-done' : ''}" data-id="${entry.id}" title="Color Allocation">
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"></circle><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"></circle><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"></circle><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"></circle><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.92 0 1.7-.71 1.7-1.63 0-.44-.18-.85-.47-1.16-.29-.3-.47-.72-.47-1.21 0-.92.72-1.63 1.63-1.63H16c3.31 0 6-2.69 6-6 0-4.97-4.48-9-10-9z"></path></svg>
                            ${isAllocated ? '<span class="alloc-badge-dot">✓</span>' : ''}
                        </button>
                        <button type="button" class="btn-icon-action btn-edit-action" data-id="${entry.id}" title="Edit Entry">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        </button>
                        <button type="button" class="btn-icon-action btn-delete-action" data-id="${entry.id}" title="Delete Entry">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
                <div class="v-card-body-grid">
                    <div>
                        <span class="v-card-metric-label">Quantity</span>
                        <span class="v-card-metric-val">${entry.quantity} Units</span>
                    </div>
                    <div>
                        <span class="v-card-metric-label">Purchase Price</span>
                        <span class="v-card-metric-val">${formatINR(entry.unitPrice)}</span>
                    </div>
                    <div>
                        <span class="v-card-metric-label">Total Amount</span>
                        <span class="v-card-metric-val green-text">${formatINR(entry.totalAmount)}</span>
                    </div>
                    <div>
                        <span class="v-card-metric-label">Color Allocation</span>
                        <span class="v-card-metric-val ${isAllocated ? 'green-text' : 'text-amber'}">
                            ${isAllocated ? 'Complete ✓' : 'Pending 🎨'}
                        </span>
                    </div>
                </div>
            `;
            vehicleCardsMobile.appendChild(card);
        });

        // Attach listeners
        document.querySelectorAll('.btn-color-alloc').forEach(b => {
            b.addEventListener('click', () => openColorAllocationModal(b.dataset.id));
        });

        document.querySelectorAll('.btn-edit-action').forEach(b => {
            b.addEventListener('click', () => editVehicleEntry(b.dataset.id));
        });

        document.querySelectorAll('.btn-delete-action').forEach(b => {
            b.addEventListener('click', () => triggerDeleteModal(b.dataset.id));
        });
    }

    function isColorAllocationComplete(entry) {
        if (!entry.colorAllocations || entry.colorAllocations.length === 0) return false;
        const totalAllocated = entry.colorAllocations.reduce((sum, item) => sum + (parseInt(item.quantity, 10) || 0), 0);
        return totalAllocated === entry.quantity;
    }

    function editVehicleEntry(id) {
        const entry = vehicleEntries.find(e => e.id === id);
        if (!entry) return;

        editingEntryId = id;
        entryModelSelect.value = entry.modelId;
        entryQuantityInput.value = entry.quantity;
        entryUnitPriceInput.value = entry.unitPrice;

        if (btnAddVehicleBtnText) btnAddVehicleBtnText.textContent = 'Update Entry';
        btnAddVehicleRow.classList.add('btn-editing');
        entryModelSelect.focus();
    }

    function triggerDeleteModal(id) {
        pendingDeleteEntryId = id;
        if (modalConfirmDelete) modalConfirmDelete.classList.remove('d-none');
    }

    const btnConfirmDeleteAction = document.getElementById('btnConfirmDeleteAction');
    const btnCancelDelete = document.getElementById('btnCancelDelete');
    const btnCloseConfirmDelete = document.getElementById('btnCloseConfirmDelete');

    if (btnConfirmDeleteAction) {
        btnConfirmDeleteAction.addEventListener('click', function () {
            if (pendingDeleteEntryId !== null) {
                vehicleEntries = vehicleEntries.filter(e => e.id !== pendingDeleteEntryId);
                if (editingEntryId === pendingDeleteEntryId) {
                    editingEntryId = null;
                    if (btnAddVehicleBtnText) btnAddVehicleBtnText.textContent = 'Add Vehicle Entry';
                    btnAddVehicleRow.classList.remove('btn-editing');
                    entryModelSelect.value = '';
                    entryQuantityInput.value = '';
                    entryUnitPriceInput.value = '';
                }
                pendingDeleteEntryId = null;
                if (modalConfirmDelete) modalConfirmDelete.classList.add('d-none');
                renderVehicleTable();
                updateSummary();
                syncHiddenJson();
            }
        });
    }

    if (btnCancelDelete) btnCancelDelete.addEventListener('click', () => modalConfirmDelete && modalConfirmDelete.classList.add('d-none'));
    if (btnCloseConfirmDelete) btnCloseConfirmDelete.addEventListener('click', () => modalConfirmDelete && modalConfirmDelete.classList.add('d-none'));

    // ==========================================
    // COLOR ALLOCATION MODAL LOGIC
    // ==========================================
    function openColorAllocationModal(entryId) {
        const entry = vehicleEntries.find(e => e.id === entryId);
        if (!entry) return;

        activeColorAllocEntryId = entryId;
        if (modalAllocModelName) modalAllocModelName.textContent = entry.modelName;
        if (modalAllocTotalQty) modalAllocTotalQty.textContent = entry.quantity;
        if (colorModalError) colorModalError.classList.add('d-none');

        currentModalColorRows = (entry.colorAllocations && entry.colorAllocations.length > 0)
            ? JSON.parse(JSON.stringify(entry.colorAllocations))
            : [{ colorId: '', quantity: 1 }];

        renderModalColorRows();
        if (modalColorAllocation) modalColorAllocation.classList.remove('d-none');
    }

    function renderModalColorRows() {
        if (!colorRowsContainer) return;
        colorRowsContainer.innerHTML = '';

        currentModalColorRows.forEach((row, idx) => {
            const rowDiv = document.createElement('div');
            rowDiv.className = 'color-row-item';

            const selectedColorObj = availableColors.find(c => String(c.id) === String(row.colorId));
            const swatchHex = selectedColorObj ? (selectedColorObj.color_hex || '#cbd5e1') : '#cbd5e1';

            let optionsHtml = '<option value="">Select Color ▼</option>';
            availableColors.forEach(c => {
                const cName = c.color_name || c.name;
                const isSelected = String(c.id) === String(row.colorId) ? 'selected' : '';
                optionsHtml += `<option value="${c.id}" ${isSelected}>${escapeHtml(cName)}</option>`;
            });

            rowDiv.innerHTML = `
                <div class="color-row-select-wrap">
                    <span class="color-swatch-dot" style="background-color: ${swatchHex};"></span>
                    <select class="form-input color-row-select" data-index="${idx}">
                        ${optionsHtml}
                    </select>
                </div>
                <div class="color-row-qty-wrap">
                    <input type="number" class="form-input color-row-qty" data-index="${idx}" min="1" value="${row.quantity || 1}" placeholder="Qty">
                </div>
                <button type="button" class="btn-remove-color-row" data-index="${idx}" title="Remove Row">&times;</button>
            `;

            colorRowsContainer.appendChild(rowDiv);
        });

        document.querySelectorAll('.color-row-select').forEach(sel => {
            sel.addEventListener('change', function () {
                const index = parseInt(this.dataset.index, 10);
                currentModalColorRows[index].colorId = this.value;
                const cObj = availableColors.find(c => String(c.id) === String(this.value));
                if (cObj) currentModalColorRows[index].colorName = cObj.color_name || cObj.name;
                renderModalColorRows();
            });
        });

        document.querySelectorAll('.color-row-qty').forEach(inp => {
            inp.addEventListener('input', function () {
                const index = parseInt(this.dataset.index, 10);
                let val = parseInt(this.value, 10);
                if (isNaN(val) || val < 0) val = 0;
                currentModalColorRows[index].quantity = val;
                calculateLiveAllocations();
            });
        });

        document.querySelectorAll('.btn-remove-color-row').forEach(btn => {
            btn.addEventListener('click', function () {
                const index = parseInt(this.dataset.index, 10);
                currentModalColorRows.splice(index, 1);
                renderModalColorRows();
            });
        });

        calculateLiveAllocations();
    }

    function calculateLiveAllocations() {
        const entry = vehicleEntries.find(e => e.id === activeColorAllocEntryId);
        if (!entry) return;

        const totalAllowed = entry.quantity;
        const totalAllocated = currentModalColorRows.reduce((sum, r) => sum + (parseInt(r.quantity, 10) || 0), 0);
        const remaining = totalAllowed - totalAllocated;

        if (modalAllocatedCount) modalAllocatedCount.textContent = `${totalAllocated} / ${totalAllowed}`;
        if (modalRemainingCount) {
            modalRemainingCount.textContent = remaining;
            if (remaining === 0) {
                modalRemainingCount.className = 'text-green';
            } else if (remaining < 0) {
                modalRemainingCount.className = 'text-red';
            } else {
                modalRemainingCount.className = 'text-amber';
            }
        }
    }

    if (btnAddColorRow) {
        btnAddColorRow.addEventListener('click', function () {
            currentModalColorRows.push({ colorId: '', quantity: 1 });
            renderModalColorRows();
        });
    }

    if (btnSaveColorAllocation) {
        btnSaveColorAllocation.addEventListener('click', function () {
            if (colorModalError) {
                colorModalError.classList.add('d-none');
                colorModalError.textContent = '';
            }

            const entry = vehicleEntries.find(e => e.id === activeColorAllocEntryId);
            if (!entry) return;

            const totalAllowed = entry.quantity;
            let totalAllocated = 0;

            for (let i = 0; i < currentModalColorRows.length; i++) {
                const r = currentModalColorRows[i];
                if (!r.colorId) {
                    showColorModalError(`Please select a color for Row #${i + 1}.`);
                    return;
                }
                const q = parseInt(r.quantity, 10);
                if (isNaN(q) || q <= 0) {
                    showColorModalError(`Row #${i + 1} must have a quantity greater than 0.`);
                    return;
                }
                totalAllocated += q;
            }

            if (totalAllocated !== totalAllowed) {
                showColorModalError(`Allocation incomplete: Total allocated (${totalAllocated}) must equal vehicle quantity (${totalAllowed}). Remaining: ${totalAllowed - totalAllocated}.`);
                return;
            }

            entry.colorAllocations = JSON.parse(JSON.stringify(currentModalColorRows));
            if (modalColorAllocation) modalColorAllocation.classList.add('d-none');

            renderVehicleTable();
            syncHiddenJson();
        });
    }

    function showColorModalError(msg) {
        if (colorModalError) {
            colorModalError.textContent = msg;
            colorModalError.classList.remove('d-none');
        }
    }

    if (btnCancelColorAllocation) btnCancelColorAllocation.addEventListener('click', () => modalColorAllocation && modalColorAllocation.classList.add('d-none'));
    if (btnCloseColorAllocationModal) btnCloseColorAllocationModal.addEventListener('click', () => modalColorAllocation && modalColorAllocation.classList.add('d-none'));

    // ==========================================
    // SUMMARY CALCULATIONS & HIDDEN INPUT
    // ==========================================
    function updateSummary() {
        const totalQty = vehicleEntries.reduce((sum, e) => sum + e.quantity, 0);
        const totalAmt = vehicleEntries.reduce((sum, e) => sum + e.totalAmount, 0);

        if (summaryTotalQty) summaryTotalQty.textContent = totalQty;
        if (summaryTotalAmount) summaryTotalAmount.textContent = formatINR(totalAmt);
    }

    function syncHiddenJson() {
        if (idVehicleItemsJson) {
            idVehicleItemsJson.value = JSON.stringify(vehicleEntries);
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ==========================================
    // MAIN SAVE PURCHASE - BACKEND SUBMISSION
    // ==========================================
    if (btnSavePurchase) {
        btnSavePurchase.addEventListener('click', async function (e) {
            e.preventDefault();
            if (submitValidationError) {
                submitValidationError.classList.add('d-none');
                submitValidationError.innerHTML = '';
            }

            const supplierVal = supplierSelect ? supplierSelect.value : '';
            const invoiceNum = invoiceNumberInput ? invoiceNumberInput.value.trim() : '';
            const invoiceDate = invoiceDateInput ? invoiceDateInput.value.trim() : '';
            
            // 1. Frontend Validations
            if (!invoiceNum) {
                showSubmitError('Invoice Number is required in Purchase Information.');
                if (invoiceNumberInput) invoiceNumberInput.focus();
                return;
            }
            if (!invoiceDate) {
                showSubmitError('Invoice Date is required in Purchase Information.');
                if (invoiceDateInput) invoiceDateInput.focus();
                return;
            }
            if (!supplierVal || supplierVal === '__add_new__') {
                showSubmitError('Please select a Supplier in Purchase Information.');
                if (supplierSelect) supplierSelect.focus();
                return;
            }
            if (vehicleEntries.length === 0) {
                showSubmitError('Please add at least one vehicle entry.');
                return;
            }

            for (const entry of vehicleEntries) {
                if (!entry.modelId) {
                    showSubmitError(`Invalid model selected for entry "${entry.modelName}".`);
                    return;
                }
                if (entry.quantity <= 0) {
                    showSubmitError(`Quantity must be greater than 0 for model "${entry.modelName}".`);
                    return;
                }
                if (entry.unitPrice <= 0) {
                    showSubmitError(`Purchase Price must be greater than 0 for model "${entry.modelName}".`);
                    return;
                }
                if (!isColorAllocationComplete(entry)) {
                    showSubmitError(`Color Allocation incomplete for model "${entry.modelName}". Click the 🎨 icon to allocate colors.`);
                    return;
                }
            }

            // 2. Prepare Form Payload (Single FormData POST)
            const formData = new FormData();
            formData.append('supplier', supplierVal);
            formData.append('supplier_id', supplierVal);
            formData.append('invoice_number', invoiceNum);
            formData.append('invoice_date', invoiceDate);
            

            const itemsPayload = vehicleEntries.map(e => ({
                vehicle_model: e.modelId,
                model_id: e.modelId,
                quantity: e.quantity,
                unit_price: e.unitPrice,
                purchase_price: e.unitPrice,
                total_amount: e.totalAmount,
                color_allocations: e.colorAllocations.map(c => ({
                    color: c.colorId,
                    color_id: c.colorId,
                    quantity: c.quantity
                }))
            }));

            formData.append('items', JSON.stringify(itemsPayload));
            formData.append('vehicle_items', JSON.stringify(itemsPayload));
            formData.append('vehicle_items_json', JSON.stringify(itemsPayload));

            if (fileInput && fileInput.files && fileInput.files[0]) {
                formData.append('invoice_photo', fileInput.files[0]);
            }

            btnSavePurchase.disabled = true;

            try {
                const csrfToken = getCsrfToken();
                const response = await fetch(window.location.pathname, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken
                    },
                    body: formData
                });

                let result;
                try {
                    result = await response.json();
                } catch (jsonErr) {
                    throw new Error(`Server returned error status (${response.status})`);
                }

                if (response.ok && result.success) {
                    // Redirect on success directly without resetting form state prematurely
                    if (result.redirect_url) {
                        window.location.href = result.redirect_url;
                    } else {
                        window.location.href = '/yakuza/purchase-history/';
                    }
                } else {
                    const errorMsg = result.error || result.detail || result.message || `Server error (${response.status})`;
                    showSubmitError(errorMsg);
                }

            } catch (err) {
                showSubmitError(err.message || 'Failed to save purchase. Please check input values and try again.');
            } finally {
                btnSavePurchase.disabled = false;
            }
        });
    }

    function resetPurchasePageForm() {
        if (supplierSelect) supplierSelect.value = '';
        if (invoiceNumberInput) invoiceNumberInput.value = '';
        if (invoiceDateInput) invoiceDateInput.value = '';
         
        if (fileInput) fileInput.value = '';
        if (dropzoneBox) dropzoneBox.classList.remove('d-none');
        if (uploadedFileBar) uploadedFileBar.classList.add('d-none');
        if (modalPreviewImage) modalPreviewImage.src = '';

        if (entryModelSelect) entryModelSelect.value = '';
        if (entryQuantityInput) entryQuantityInput.value = '';
        if (entryUnitPriceInput) entryUnitPriceInput.value = '';

        vehicleEntries = [];
        editingEntryId = null;
        pendingDeleteEntryId = null;
        activeColorAllocEntryId = null;
        currentModalColorRows = [];

        if (btnAddVehicleBtnText) btnAddVehicleBtnText.textContent = 'Add Vehicle Entry';
        if (btnAddVehicleRow) btnAddVehicleRow.classList.remove('btn-editing');

        renderVehicleTable();
        updateSummary();
        syncHiddenJson();
    }

    function showSubmitError(msg) {
        if (submitValidationError) {
            submitValidationError.innerHTML = `<strong>Validation Error:</strong> ${escapeHtml(msg)}`;
            submitValidationError.classList.remove('d-none');
            submitValidationError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    const btnCloseSuccessModal = document.getElementById('btnCloseSuccessModal');
    if (btnCloseSuccessModal) {
        btnCloseSuccessModal.addEventListener('click', function () {
            if (modalPurchaseSuccess) modalPurchaseSuccess.classList.add('d-none');
        });
    }
});