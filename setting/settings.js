/**
 * ERP Settings Module - Pure UI Interactivity Script
 */

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // State Management
    let isFormDirty = false;
    let pendingNavTarget = null;
    let currentRole = 'superuser';

    // DOM Elements
    const navItems = document.querySelectorAll('.erp-nav-item');
    const sections = document.querySelectorAll('.erp-section');
    const roleSimulator = document.getElementById('role-simulator');
    const globalSaveBtn = document.getElementById('global-save-btn');
    const globalDiscardBtn = document.getElementById('global-discard-btn');
    const toastContainer = document.getElementById('erp-toast-container');

    // Modals
    const modalUser = document.getElementById('modal-user');
    const modalRestore = document.getElementById('modal-restore-confirm');
    const modalUnsaved = document.getElementById('modal-unsaved-changes');

    /* ==========================================================================
       1. SECTION / TAB NAVIGATION & UNSAVED CHANGES LOGIC
       ========================================================================== */

    navItems.forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-target');

            if (this.classList.contains('active')) return;

            if (isFormDirty) {
                pendingNavTarget = targetId;
                showModal(modalUnsaved);
            } else {
                switchTab(targetId);
            }
        });
    });

    function switchTab(targetId) {
        navItems.forEach(nav => {
            if (nav.getAttribute('data-target') === targetId) {
                nav.classList.add('active');
                nav.setAttribute('aria-selected', 'true');
            } else {
                nav.classList.remove('active');
                nav.setAttribute('aria-selected', 'false');
            }
        });

        sections.forEach(sec => {
            if (sec.id === targetId) {
                sec.classList.add('active');
            } else {
                sec.classList.remove('active');
            }
        });

        // Reset dirty state on tab switch
        setDirtyState(false);
    }

    // Dirty Form Change Detection
    const allForms = document.querySelectorAll('.erp-form');
    allForms.forEach(form => {
        form.addEventListener('input', () => setDirtyState(true));
        form.addEventListener('change', () => setDirtyState(true));
    });

    function setDirtyState(dirty) {
        isFormDirty = dirty;
        if (globalDiscardBtn) {
            globalDiscardBtn.style.display = dirty ? 'inline-flex' : 'none';
        }
    }

    // Unsaved Changes Modal Actions
    document.getElementById('btn-unsaved-cancel').addEventListener('click', () => {
        hideModal(modalUnsaved);
        pendingNavTarget = null;
    });

    document.getElementById('btn-unsaved-discard').addEventListener('click', () => {
        hideModal(modalUnsaved);
        setDirtyState(false);
        if (pendingNavTarget) {
            switchTab(pendingNavTarget);
            pendingNavTarget = null;
        }
    });

    document.getElementById('btn-unsaved-save').addEventListener('click', () => {
        hideModal(modalUnsaved);
        triggerGlobalSave().then(() => {
            if (pendingNavTarget) {
                switchTab(pendingNavTarget);
                pendingNavTarget = null;
            }
        });
    });

    /* ==========================================================================
       2. ROLE BASED UI DEMO TOGGLE
       ========================================================================== */

    if (roleSimulator) {
        roleSimulator.addEventListener('change', function () {
            currentRole = this.value;
            applyRolePermissions(currentRole);
            showToast(`Switched view to ${currentRole === 'superuser' ? 'Super User' : 'Branch Admin'} mode`);
        });
    }

    function applyRolePermissions(role) {
        const superuserElements = document.querySelectorAll('.erp-superuser-only');
        superuserElements.forEach(el => {
            if (role === 'branch_admin') {
                el.style.display = 'none';
                // If currently on a hidden section, default back to profile
                if (el.classList.contains('active')) {
                    switchTab('section-profile');
                }
            } else {
                el.style.display = '';
            }
        });
    }

    /* ==========================================================================
       3. MODAL CONTROLS (GENERIC & SPECIFIC)
       ========================================================================== */

    function showModal(modalEl) {
        if (modalEl) modalEl.removeAttribute('hidden');
    }

    function hideModal(modalEl) {
        if (modalEl) modalEl.setAttribute('hidden', 'true');
    }

    document.querySelectorAll('[data-dismiss="modal"]').forEach(btn => {
        btn.addEventListener('click', function () {
            const modal = this.closest('.erp-modal-backdrop');
            hideModal(modal);
        });
    });

    // User Management Modal Triggers
    const btnOpenUserModal = document.getElementById('btn-open-user-modal');
    if (btnOpenUserModal) {
        btnOpenUserModal.addEventListener('click', () => {
            document.getElementById('form-user-modal').reset();
            document.getElementById('modal-user-title').textContent = 'Add New System User';
            showModal(modalUser);
        });
    }

    // User Form Submit (UI Only)
    document.getElementById('form-user-modal').addEventListener('submit', function (e) {
        e.preventDefault();
        hideModal(modalUser);
        showToast('User account successfully created.');
    });

    // Restore Confirmation Modal Triggers
    const btnTriggerRestore = document.getElementById('btn-trigger-restore');
    if (btnTriggerRestore) {
        btnTriggerRestore.addEventListener('click', () => showModal(modalRestore));
    }

    document.getElementById('btn-confirm-restore-action').addEventListener('click', () => {
        const fileInput = document.getElementById('restore_file');
        if (!fileInput.files.length) {
            showToast('Please select a backup file first.', 'danger');
            return;
        }
        hideModal(modalRestore);
        showToast('Database restore initiated successfully.');
    });

    /* ==========================================================================
       4. GLOBAL SAVE & FORM SUBMISSIONS
       ========================================================================== */

    if (globalSaveBtn) {
        globalSaveBtn.addEventListener('click', () => triggerGlobalSave());
    }

    if (globalDiscardBtn) {
        globalDiscardBtn.addEventListener('click', () => {
            allForms.forEach(form => form.reset());
            setDirtyState(false);
            showToast('Changes discarded.');
        });
    }

    function triggerGlobalSave() {
        return new Promise((resolve) => {
            const spinner = globalSaveBtn.querySelector('.erp-spinner');
            const btnText = globalSaveBtn.querySelector('.erp-btn-text');

            if (spinner) spinner.removeAttribute('hidden');
            if (btnText) btnText.textContent = 'Saving...';
            globalSaveBtn.disabled = true;

            setTimeout(() => {
                if (spinner) spinner.setAttribute('hidden', 'true');
                if (btnText) btnText.textContent = 'Save All Changes';
                globalSaveBtn.disabled = false;

                setDirtyState(false);
                showToast('Settings Updated Successfully');
                resolve();
            }, 800);
        });
    }

    allForms.forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            triggerGlobalSave();
        });
    });

    /* ==========================================================================
       5. FILE PREVIEW HANDLERS (LOGO & SEALS)
       ========================================================================== */

    function bindImagePreview(inputId, previewBoxId) {
        const input = document.getElementById(inputId);
        const box = document.getElementById(previewBoxId);
        if (!input || !box) return;

        input.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    box.innerHTML = `<img src="${e.target.result}" style="max-height: 100%; max-width: 100%; object-fit: contain;">`;
                    setDirtyState(true);
                };
                reader.readAsDataURL(file);
            }
        });
    }

    bindImagePreview('inv_logo', 'logo-preview-box');
    bindImagePreview('inv_sig', 'sig-preview-box');
    bindImagePreview('inv_seal', 'seal-preview-box');

    // Profile photo preview
    const profileInput = document.getElementById('profile_photo');
    const profileImg = document.getElementById('profile-img-preview');
    const profilePlaceholder = document.querySelector('.erp-avatar-placeholder');

    if (profileInput) {
        profileInput.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    profileImg.src = e.target.result;
                    profileImg.removeAttribute('hidden');
                    if (profilePlaceholder) profilePlaceholder.style.display = 'none';
                    setDirtyState(true);
                };
                reader.readAsDataURL(file);
            }
        });
    }

    /* ==========================================================================
       6. BACKUP BUTTON ACTION HANDLERS
       ========================================================================== */

    const btnBackupNow = document.getElementById('btn-backup-now');
    if (btnBackupNow) {
        btnBackupNow.addEventListener('click', function () {
            showToast('Generating database backup snapshot...');
            setTimeout(() => {
                const now = new Date().toISOString().replace('T', ' ').substring(0, 19);
                document.getElementById('last-backup-date').textContent = now;
                document.getElementById('last-backup-size').textContent = '42.8 MB';
                document.getElementById('about-last-backup').textContent = now;
                showToast('Backup completed successfully.');
            }, 1200);
        });
    }

    const btnDownloadBackup = document.getElementById('btn-download-backup');
    if (btnDownloadBackup) {
        btnDownloadBackup.addEventListener('click', function () {
            showToast('Backup download started.');
        });
    }

    /* ==========================================================================
       7. TOAST NOTIFICATION SYSTEM
       ========================================================================== */

    function showToast(message, type = 'success') {
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `erp-toast erp-toast-${type}`;
        toast.innerHTML = `
            <span>${type === 'success' ? '✓' : '⚠️'}</span>
            <span>${message}</span>
        `;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
});