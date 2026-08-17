/**
 * EXPENSES MODULE - GATISTVAM / YAKUZA SHOWROOM MANAGEMENT
 * Handles AJAX database saves, live record fetching, summary calculations,
 * and responsive table UI.
 */

document.addEventListener('DOMContentLoaded', function () {
    let allExpenses = [];

    // DOM Elements
    const expenseForm = document.getElementById('expenseForm');
    const saveExpenseBtn = document.getElementById('saveExpenseBtn');
    const editExpenseForm = document.getElementById('editExpenseForm');
    const updateExpenseBtn = document.getElementById('updateExpenseBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const expenseTableBody = document.getElementById('expenseTableBody');
    const searchInput = document.getElementById('searchInput');
    const fromDateInput = document.getElementById('fromDateInput');
    const toDateInput = document.getElementById('toDateInput');
    const resetFilterBtn = document.getElementById('resetFilterBtn');
    const summaryMonthFilter = document.getElementById('summaryMonthFilter');
    const alertBanner = document.getElementById('expenseAlert');

    // Radios & Containers
    const typeRadios = document.querySelectorAll('input[name="expense_type"]');
    const dateFieldContainer = document.getElementById('dateFieldContainer');
    const monthFieldContainer = document.getElementById('monthFieldContainer');
    const expenseDateInput = document.getElementById('expenseDateInput');
    const expenseMonthInput = document.getElementById('expenseMonthInput');

    // Initialize Default Date Values
    const today = new Date();
    if (expenseDateInput) {
        const yr = today.getFullYear();
        const mo = String(today.getMonth() + 1).padStart(2, '0');
        const da = String(today.getDate()).padStart(2, '0');
        expenseDateInput.value = `${yr}-${mo}-${da}`;
    }
    
    // Populate Month Dropdowns immediately on load
    populateMonthOptions();
    populateSummaryMonthFilter();
    updateSummaryMetrics();

    // Toggle Date/Month Inputs on Expense Type Change
    typeRadios.forEach(radio => {
        radio.addEventListener('change', function () {
            if (this.value === 'Monthly Expense') {
                dateFieldContainer.classList.add('hidden');
                monthFieldContainer.classList.remove('hidden');
            } else {
                dateFieldContainer.classList.remove('hidden');
                monthFieldContainer.classList.add('hidden');
            }
        });
    });

    // ----------------------------------------------------
    // HELPER: GENERATE MONTHS FROM JUNE 2026 TO CURRENT MONTH
    // ----------------------------------------------------
    function getAvailableMonths() {
        const months = [];
        const now = new Date();
        const startYear = 2026;
        const startMonth = 5; // June (0-indexed)

        let targetYear = now.getFullYear();
        let targetMonth = now.getMonth();

        const lastDayOfCurrentMonth = new Date(targetYear, targetMonth + 1, 0).getDate();
        if (now.getDate() === lastDayOfCurrentMonth) {
            targetMonth += 1;
            if (targetMonth > 11) {
                targetMonth = 0;
                targetYear += 1;
            }
        }

        let curY = startYear;
        let curM = startMonth;

        while (curY < targetYear || (curY === targetYear && curM <= targetMonth)) {
            const d = new Date(curY, curM, 1);
            const val = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            const text = d.toLocaleString('default', { month: 'long', year: 'numeric' });

            months.push({ val, text });

            curM++;
            if (curM > 11) {
                curM = 0;
                curY++;
            }
        }
        return months;
    }

    // ----------------------------------------------------
    // FETCH REAL EXPENSES FROM DJANGO DATABASE
    // ----------------------------------------------------
    function fetchExpenses() {
        fetch('/expenses/?format=json', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                allExpenses = data.expenses;
                populateSummaryMonthFilter();
                renderExpensesTable();
                updateSummaryMetrics();
            } else {
                showAlert(data.error || 'Failed to load expense records.', 'error');
            }
        })
        .catch(error => {
            console.error('Error fetching expenses:', error);
            showAlert('Database connection error while fetching expenses.', 'error');
        });
    }

    // ----------------------------------------------------
    // HANDLE SAVE BUTTON / CREATE FORM SUBMISSION
    // ----------------------------------------------------
    if (expenseForm) {
        expenseForm.addEventListener('submit', function (e) {
            e.preventDefault(); 

            const name = document.getElementById('expenseNameInput').value.trim();
            const amount = document.getElementById('expenseAmountInput').value;
            const typeRadio = document.querySelector('input[name="expense_type"]:checked');
            const type = typeRadio ? typeRadio.value : 'Daily Expense';
            const date = document.getElementById('expenseDateInput').value;
            const month = document.getElementById('expenseMonthInput').value;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            if (!name || !amount || parseFloat(amount) <= 0) {
                showAlert('Please provide a valid expense name and amount.', 'error');
                return;
            }

            saveExpenseBtn.disabled = true;
            saveExpenseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

            const payload = {
                expense_name: name,
                amount: amount,
                expense_type: type,
                expense_date: date,
                expense_month: month,
                description: ''
            };

            fetch('/expenses/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert(data.message || 'Expense saved successfully!', 'success');
                    expenseForm.reset();
                    if (expenseDateInput) {
                        const yr = today.getFullYear();
                        const mo = String(today.getMonth() + 1).padStart(2, '0');
                        const da = String(today.getDate()).padStart(2, '0');
                        expenseDateInput.value = `${yr}-${mo}-${da}`;
                    }
                    fetchExpenses();
                } else {
                    showAlert(data.error || 'Failed to save expense.', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showAlert('An unexpected server error occurred.', 'error');
            })
            .finally(() => {
                saveExpenseBtn.disabled = false;
                saveExpenseBtn.innerHTML = '<i class="fas fa-check-circle"></i> Save';
            });
        });
    }

    // ----------------------------------------------------
    // HANDLE EDIT FORM SUBMISSION (UPDATE FLOW)
    // ----------------------------------------------------
    if (editExpenseForm) {
        editExpenseForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const expenseId = document.getElementById('editExpenseId').value;
            const name = document.getElementById('editNameInput').value.trim();
            const amount = document.getElementById('editAmountInput').value;
            const date = document.getElementById('editDateInput').value;
            const description = document.getElementById('editDescriptionInput').value.trim();
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            if (!expenseId || !name || !amount || parseFloat(amount) <= 0) {
                showAlert('Please provide valid details for the expense.', 'error');
                return;
            }

            if (updateExpenseBtn) {
                updateExpenseBtn.disabled = true;
                updateExpenseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
            }

            const payload = {
                expense_name: name,
                amount: amount,
                expense_date: date,
                description: description
            };

            fetch(`/expenses/edit/${expenseId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert(data.message || 'Expense updated successfully!', 'success');
                    closeModal('editModal');
                    fetchExpenses();
                } else {
                    showAlert(data.error || 'Failed to update expense.', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showAlert('An unexpected server error occurred.', 'error');
            })
            .finally(() => {
                if (updateExpenseBtn) {
                    updateExpenseBtn.disabled = false;
                    updateExpenseBtn.innerHTML = 'Save Changes';
                }
            });
        });
    }

    // ----------------------------------------------------
    // HANDLE DELETE CONFIRMATION BUTTON
    // ----------------------------------------------------
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function () {
            const id = document.getElementById('deleteExpenseId').value;
            if (!id) return;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            confirmDeleteBtn.disabled = true;
            confirmDeleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...';

            fetch(`/expenses/delete/${id}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showAlert(data.message || 'Expense deleted successfully!', 'success');
                    closeModal('deleteModal');
                    fetchExpenses();
                } else {
                    showAlert(data.error || 'Could not delete record.', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showAlert('An unexpected server error occurred.', 'error');
            })
            .finally(() => {
                confirmDeleteBtn.disabled = false;
                confirmDeleteBtn.innerHTML = 'Delete';
            });
        });
    }

    // ----------------------------------------------------
    // RENDER TABLE & METRICS
    // ----------------------------------------------------
    function renderExpensesTable() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const fromDate = fromDateInput ? fromDateInput.value : '';
        const toDate = toDateInput ? toDateInput.value : '';

        let filtered = allExpenses.filter(exp => {
            const matchesSearch = !query || 
                exp.expense_name.toLowerCase().includes(query) ||
                exp.display_date.toLowerCase().includes(query) ||
                exp.amount.includes(query);

            const matchesFrom = !fromDate || exp.expense_date >= fromDate;
            const matchesTo = !toDate || exp.expense_date <= toDate;

            return matchesSearch && matchesFrom && matchesTo;
        });

        expenseTableBody.innerHTML = '';
        let total = 0;

        if (filtered.length === 0) {
            document.getElementById('noDataMessage').classList.remove('hidden');
        } else {
            document.getElementById('noDataMessage').classList.add('hidden');
            filtered.forEach(exp => {
                total += parseFloat(exp.amount);
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="col-name"><strong>${escapeHtml(exp.expense_name)}</strong></td>
                    <td class="col-date">${escapeHtml(exp.display_date)}</td>
                    <td class="col-amount">₹${escapeHtml(exp.amount)}</td>
                    <td class="col-action">
                        <div class="action-btn-group">
                            <button class="btn-icon view-btn" onclick="viewExpense(${exp.id})" title="View"><i class="fas fa-eye"></i></button>
                            <button class="btn-icon edit-btn" onclick="openEditModal(${exp.id})" title="Edit"><i class="fas fa-edit"></i></button>
                            <button class="btn-icon delete-btn" onclick="deleteExpense(${exp.id})" title="Delete"><i class="fas fa-trash"></i></button>
                        </div>
                    </td>
                `;
                expenseTableBody.appendChild(tr);
            });
        }

        document.getElementById('visibleRecordCount').innerText = filtered.length;
        document.getElementById('visibleTotalAmount').innerText = '₹' + total.toFixed(2);
    }

    function updateSummaryMetrics() {
        if (!summaryMonthFilter) return;

        const selectedMonthKey = summaryMonthFilter.value;
        let monthTotal = 0;
        let dailyTotal = 0;

        allExpenses.forEach(exp => {
            if (exp.month_key === selectedMonthKey) {
                monthTotal += parseFloat(exp.amount);
                dailyTotal += parseFloat(exp.amount);
            }
        });

        document.getElementById('summaryTotalAmount').innerText = '₹' + monthTotal.toFixed(2);
        document.getElementById('summaryDailyAmount').innerText = '₹' + dailyTotal.toFixed(2);
        document.getElementById('summaryMonthlyAmount').innerText = '₹' + monthTotal.toFixed(2);
        
        const selOption = summaryMonthFilter.options[summaryMonthFilter.selectedIndex];
        if (selOption) {
            document.getElementById('summaryMonthName').innerText = selOption.text;
        }
    }

    // ----------------------------------------------------
    // POPULATE DROPDOWNS DYNAMICALLY (CHRONOLOGICAL ORDER)
    // ----------------------------------------------------
    function populateMonthOptions() {
        if (!expenseMonthInput) return;
        const currentVal = expenseMonthInput.value;
        expenseMonthInput.innerHTML = '';

        const now = new Date();
        const currentMonthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        const months = getAvailableMonths();

        months.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.val;
            opt.textContent = m.text;
            if (m.val === (currentVal || currentMonthKey)) {
                opt.selected = true;
            }
            expenseMonthInput.appendChild(opt);
        });

        if (!expenseMonthInput.value && expenseMonthInput.options.length > 0) {
            expenseMonthInput.selectedIndex = expenseMonthInput.options.length - 1;
        }
    }

    function populateSummaryMonthFilter() {
        if (!summaryMonthFilter) return;
        
        const currentVal = summaryMonthFilter.value;
        summaryMonthFilter.innerHTML = '';

        const monthMap = {};
        const today = new Date();
        const currYear = today.getFullYear();
        const currMonth = String(today.getMonth() + 1).padStart(2, '0');
        const currKey = `${currYear}-${currMonth}`;

        const availableMonths = getAvailableMonths();
        availableMonths.forEach(m => {
            monthMap[m.val] = m.text;
        });

        allExpenses.forEach(exp => {
            if (exp.month_key && exp.month_key >= '2026-06') {
                const parts = exp.month_key.split('-');
                const d = new Date(parts[0], parts[1] - 1, 1);
                monthMap[exp.month_key] = d.toLocaleString('default', { month: 'long', year: 'numeric' });
            }
        });

        Object.keys(monthMap).sort().forEach(key => {
            const opt = document.createElement('option');
            opt.value = key;
            opt.textContent = monthMap[key];
            if (key === currentVal || (!currentVal && key === currKey)) {
                opt.selected = true;
            }
            summaryMonthFilter.appendChild(opt);
        });
    }

    // ----------------------------------------------------
    // HELPERS & MODAL ACTIONS
    // ----------------------------------------------------
    window.viewExpense = function (id) {
        const exp = allExpenses.find(e => e.id === id);
        if (!exp) return;
        document.getElementById('viewName').innerText = exp.expense_name;
        
        const typeEl = document.getElementById('viewType');
        if (typeEl) {
            typeEl.innerText = exp.month_display ? 'Monthly Expense' : 'Daily Expense';
        }

        document.getElementById('viewDateMonth').innerText = exp.display_date;
        document.getElementById('viewAmount').innerText = '₹' + exp.amount;
        document.getElementById('viewDescription').innerText = exp.description || 'N/A';
        document.getElementById('viewModal').classList.remove('hidden');
    };

    window.openEditModal = function (id) {
        const exp = allExpenses.find(e => e.id === id);
        if (!exp) return;
        document.getElementById('editExpenseId').value = exp.id;
        document.getElementById('editNameInput').value = exp.expense_name;
        document.getElementById('editAmountInput').value = exp.amount;
        document.getElementById('editDateInput').value = exp.expense_date;
        document.getElementById('editDescriptionInput').value = exp.description || '';
        document.getElementById('editModal').classList.remove('hidden');
    };

    window.deleteExpense = function (id) {
        const exp = allExpenses.find(e => e.id === id);
        if (!exp) return;
        document.getElementById('deleteExpenseId').value = exp.id;
        document.getElementById('deleteModal').classList.remove('hidden');
    };

    window.closeModal = function (modalId) {
        document.getElementById(modalId).classList.add('hidden');
    };

    function showAlert(msg, type) {
        if (!alertBanner) return;
        alertBanner.innerText = msg;
        alertBanner.className = `alert-banner ${type}`;
        alertBanner.classList.remove('hidden');
        setTimeout(() => alertBanner.classList.add('hidden'), 4000);
    }

    function escapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Filter listeners
    [searchInput, fromDateInput, toDateInput].forEach(el => {
        if (el) el.addEventListener('input', renderExpensesTable);
    });

    if (resetFilterBtn) {
        resetFilterBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (fromDateInput) fromDateInput.value = '';
            if (toDateInput) toDateInput.value = '';
            renderExpensesTable();
        });
    }

    if (summaryMonthFilter) {
        summaryMonthFilter.addEventListener('change', updateSummaryMetrics);
    }

    // Initial Fetch on load
    fetchExpenses();
});