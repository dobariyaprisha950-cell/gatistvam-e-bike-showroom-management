document.addEventListener("DOMContentLoaded", function () {
    initializeDefaultDates();
    calculateTotalAmount();
});

function initializeDefaultDates() {
    const todayStr = new Date().toISOString().split("T")[0];
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.value) {
            input.value = todayStr;
        }
    });
}

function calculateTotalAmount() {
    let total = 0;
    const rows = document.querySelectorAll("#expenseTableBody tr[data-id]");
    rows.forEach(row => {
        const amount = parseFloat(row.getAttribute("data-amount")) || 0;
        total += amount;
    });

    const totalEl = document.getElementById("visibleTotalAmount");
    if (totalEl) {
        totalEl.textContent = "₹" + total.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }
}

function openModal(modalId) {
    document.getElementById(modalId).classList.remove("hidden");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add("hidden");
}

function openEditModal(id) {
    const row = document.querySelector(`tr[data-id='${id}']`);
    if (!row) return;

    const form = document.getElementById("editExpenseForm");
    form.action = `/expenses/edit/${id}/`;
    
    openModal("editModal");
}

function openDeleteModal(id, name) {
    const form = document.getElementById("deleteExpenseForm");
    form.action = `/expenses/delete/${id}/`;
    document.getElementById("deleteExpenseName").textContent = name;
    openModal("deleteModal");
}

document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
        document.querySelectorAll(".modal-overlay:not(.hidden)").forEach(modal => {
            modal.classList.add("hidden");
        });
    }
});