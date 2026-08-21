document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    let pendingNavTarget = null;

    // Profile original state tracking
    let profileOriginalState = {};
    let tempObjectUrl = null;
    const formProfile = document.getElementById('form-profile');

    function getProfileFormState() {
        if (!formProfile) return {};
        const profileImg = document.getElementById('profile-img-preview');
        const placeholder = document.querySelector('.erp-avatar-placeholder');
        
        return {
            full_name: document.getElementById('full_name')?.value || '',
            username: document.getElementById('username')?.value || '',
            mobile: document.getElementById('profile_mobile')?.value || '',
            curr_password: document.getElementById('curr_password')?.value || '',
            new_password: document.getElementById('new_password')?.value || '',
            confirm_password: document.getElementById('confirm_password')?.value || '',
            imgSrc: profileImg ? profileImg.getAttribute('src') || '' : '',
            imgHidden: profileImg ? profileImg.hasAttribute('hidden') : true,
            placeholderDisplay: placeholder ? placeholder.style.display || '' : ''
        };
    }

    function initProfileOriginalState() {
        profileOriginalState = getProfileFormState();
    }

    function revokeTempObjectUrl() {
        if (tempObjectUrl) {
            URL.revokeObjectURL(tempObjectUrl);
            tempObjectUrl = null;
        }
    }

    function isProfileFormDirty() {
        if (!formProfile) return false;
        
        const currentState = getProfileFormState();
        for (let key in profileOriginalState) {
            if (key !== 'imgSrc' && key !== 'imgHidden' && key !== 'placeholderDisplay') {
                if (currentState[key] !== profileOriginalState[key]) {
                    return true;
                }
            }
        }
        
        const photoInput = document.getElementById('profile_photo');
        if (photoInput && photoInput.files && photoInput.files.length > 0) {
            return true;
        }
        
        return false;
    }

    function restoreProfileFormState() {
        if (!formProfile) return;
        
        if (document.getElementById('full_name')) document.getElementById('full_name').value = profileOriginalState.full_name;
        if (document.getElementById('username')) document.getElementById('username').value = profileOriginalState.username;
        if (document.getElementById('profile_mobile')) document.getElementById('profile_mobile').value = profileOriginalState.mobile;
        if (document.getElementById('curr_password')) document.getElementById('curr_password').value = profileOriginalState.curr_password;
        if (document.getElementById('new_password')) document.getElementById('new_password').value = profileOriginalState.new_password;
        if (document.getElementById('confirm_password')) document.getElementById('confirm_password').value = profileOriginalState.confirm_password;
        
        // Restore Photo state
        const photoInput = document.getElementById('profile_photo');
        if (photoInput) photoInput.value = '';

        revokeTempObjectUrl();

        const profileImg = document.getElementById('profile-img-preview');
        const placeholder = document.querySelector('.erp-avatar-placeholder');

        if (profileImg) {
            profileImg.src = profileOriginalState.imgSrc;
            if (profileOriginalState.imgHidden) {
                profileImg.setAttribute('hidden', 'true');
            } else {
                profileImg.removeAttribute('hidden');
            }
        }

        if (placeholder) {
            placeholder.style.display = profileOriginalState.placeholderDisplay;
        }
    }

    initProfileOriginalState();

    // ==========================================
    // 1. CSRF TOKEN & HELPERS
    // ==========================================
    function getCsrfToken() {
        const tokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (tokenInput && tokenInput.value) return tokenInput.value;
        const name = 'csrftoken';
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

    function showModal(modalEl) { if (modalEl) modalEl.removeAttribute('hidden'); }
    function hideModal(modalEl) { if (modalEl) modalEl.setAttribute('hidden', 'true'); }

    document.querySelectorAll('[data-dismiss="modal"]').forEach(btn => {
        btn.addEventListener('click', function () {
            hideModal(this.closest('.erp-modal-backdrop'));
        });
    });

    function showToast(message, type = 'success') {
        const container = document.getElementById('erp-toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `erp-toast erp-toast-${type}`;
        toast.style.cssText = `
            padding: 12px 20px;
            margin-bottom: 10px;
            border-radius: 6px;
            color: #fff;
            background-color: ${type === 'success' ? '#10b981' : '#ef4444'};
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 10px;
            transition: opacity 0.3s ease;
        `;
        toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠️'}</span><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ==========================================
    // 2. TABS NAVIGATION & UNSAVED POPUP HANDLING
    // ==========================================
    const navItems = document.querySelectorAll('.erp-nav-item');
    const sections = document.querySelectorAll('.erp-section');
    const modalUnsaved = document.getElementById('modal-unsaved-changes');
    const btnUnsavedSave = document.getElementById('btn-unsaved-save');
    const btnUnsavedDiscard = document.getElementById('btn-unsaved-discard');
    const btnUnsavedCancel = document.getElementById('btn-unsaved-cancel');
    const btnUnsavedClose = document.getElementById('btn-unsaved-close');

    navItems.forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-target');
            if (this.classList.contains('active')) return;

            const activeSection = document.querySelector('.erp-section.active');
            if (activeSection && activeSection.id === 'section-profile' && isProfileFormDirty()) {
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
            } else {
                nav.classList.remove('active');
            }
        });
        sections.forEach(sec => {
            if (sec.id === targetId) sec.classList.add('active');
            else sec.classList.remove('active');
        });
        
        // Update URL hash without jumping page to keep active tab state on page refresh
        if (history.replaceState) {
            history.replaceState(null, null, '#' + targetId);
        } else {
            window.location.hash = targetId;
        }
    }

    // Unsaved Modal Actions
    if (btnUnsavedSave) {
        btnUnsavedSave.addEventListener('click', function () {
            if (formProfile) {
                submitProfileForm().then(success => {
                    if (success) {
                        hideModal(modalUnsaved);
                        if (pendingNavTarget) {
                            switchTab(pendingNavTarget);
                            pendingNavTarget = null;
                        }
                    }
                });
            }
        });
    }

    if (btnUnsavedDiscard) {
        btnUnsavedDiscard.addEventListener('click', function () {
            restoreProfileFormState();
            hideModal(modalUnsaved);
            if (pendingNavTarget) {
                switchTab(pendingNavTarget);
                pendingNavTarget = null;
            }
        });
    }

    if (btnUnsavedCancel) {
        btnUnsavedCancel.addEventListener('click', function () {
            hideModal(modalUnsaved);
            pendingNavTarget = null;
        });
    }

    if (btnUnsavedClose) {
        btnUnsavedClose.addEventListener('click', function () {
            hideModal(modalUnsaved);
            pendingNavTarget = null;
        });
    }

    // Initialize Active Tab from URL Hash on Page Load / Refresh
    function loadInitialTab() {
        let hash = window.location.hash.replace('#', '');
        if (!hash) return;

        // Map short alias hashes if present
        if (hash === 'profile' || hash === 'security') {
            hash = 'section-profile';
        } else if (hash === 'branch') {
            hash = 'section-branch';
        } else if (hash === 'stock' || hash === 'stock-management') {
            hash = 'section-stock';
        } else if (hash === 'users' || hash === 'user-management') {
            hash = 'section-users';
        } else if (hash === 'invoice') {
            hash = 'section-invoice';
        } else if (hash === 'notifications') {
            hash = 'section-notifications';
        } else if (hash === 'audit') {
            hash = 'section-audit';
        } else if (hash === 'backup') {
            hash = 'section-backup';
        }

        const targetSection = document.getElementById(hash);
        if (targetSection) {
            switchTab(hash);
        }
    }

    loadInitialTab();

    // ==========================================
    // STOCK MANAGEMENT REAL-TIME GLOBAL SEARCH (ALL BRANCHES)
    // ==========================================
    const stockSearchInput = document.getElementById('stock-global-search');
    if (stockSearchInput) {
        stockSearchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            const branchCards = document.querySelectorAll('.erp-stock-card');
            let visibleBranchCount = 0;

            branchCards.forEach(card => {
                const stockItems = card.querySelectorAll('.erp-stock-item');
                const branchTitle = card.querySelector('.erp-stock-card-header, h3, h4')?.textContent.toLowerCase() || '';
                let matchInBranch = false;

                // Check if search query matches the Branch Name directly
                const isBranchMatch = branchTitle.includes(query);

                stockItems.forEach(item => {
                    const modelName = (item.getAttribute('data-model') || item.textContent).toLowerCase();
                    if (query === '' || isBranchMatch || modelName.includes(query)) {
                        item.style.display = 'flex';
                        matchInBranch = true;
                    } else {
                        item.style.display = 'none';
                    }
                });

                if (matchInBranch || query === '' || isBranchMatch) {
                    card.style.display = 'flex';
                    visibleBranchCount++;
                } else {
                    card.style.display = 'none';
                }
            });

            const noResultsMsg = document.getElementById('stock-no-results');
            if (noResultsMsg) {
                noResultsMsg.style.display = (visibleBranchCount === 0) ? 'block' : 'none';
            }
        });
    }

    // ==========================================
    // 3. PASSWORD SHOW / HIDE TOGGLE
    // ==========================================
    document.querySelectorAll('.toggle-password').forEach(toggleBtn => {
        toggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-target');
            const input = document.getElementById(targetId);
            const icon = this.querySelector('i');
            
            if (input) {
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                
                if (icon) {
                    if (isPassword) {
                        icon.classList.remove('fa-eye');
                        icon.classList.add('fa-eye-slash');
                    } else {
                        icon.classList.remove('fa-eye-slash');
                        icon.classList.add('fa-eye');
                    }
                }
            }
        });
    });

    // ==========================================
    // 4. LIVE PROFILE PHOTO PREVIEW
    // ==========================================
    const profileInput = document.getElementById('profile_photo');
    const profileImg = document.getElementById('profile-img-preview');
    const placeholder = document.querySelector('.erp-avatar-placeholder');

    if (profileInput) {
        profileInput.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                revokeTempObjectUrl();
                tempObjectUrl = URL.createObjectURL(file);
                if (profileImg) {
                    profileImg.src = tempObjectUrl;
                    profileImg.removeAttribute('hidden');
                    if (placeholder) placeholder.style.display = 'none';
                }
            }
        });
    }

    // ==========================================
    // 5. DATABASE FORM SUBMIT HANDLERS
    // ==========================================

    function submitProfileForm() {
        return new Promise((resolve) => {
            const currPass = document.getElementById('curr_password')?.value.trim() || '';
            const newPass = document.getElementById('new_password')?.value.trim() || '';
            const confirmPass = document.getElementById('confirm_password')?.value.trim() || '';

            if (newPass !== '' || confirmPass !== '' || currPass !== '') {
                if (currPass === '') {
                    showToast('વર્તમાન પાસવર્ડ (Current Password) નાખવો ફરજિયાત છે!', 'danger');
                    document.getElementById('curr_password')?.focus();
                    resolve(false);
                    return;
                }

                if (newPass !== confirmPass) {
                    showToast('નવો પાસવર્ડ અને કન્ફર્મ પાસવર્ડ સરખા નથી!', 'danger');
                    document.getElementById('confirm_password')?.focus();
                    resolve(false);
                    return;
                }

                if (newPass.length < 6) {
                    showToast('નવો પાસવર્ડ ઓછામાં ઓછો 6 અક્ષરનો હોવો જોઈએ!', 'danger');
                    document.getElementById('new_password')?.focus();
                    resolve(false);
                    return;
                }
            }

            const formData = new FormData(formProfile);

            fetch('/settings/update-profile/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast(data.message || 'Profile updated successfully!', 'success');
                    if (document.getElementById('curr_password')) document.getElementById('curr_password').value = '';
                    if (document.getElementById('new_password')) document.getElementById('new_password').value = '';
                    if (document.getElementById('confirm_password')) document.getElementById('confirm_password').value = '';
                    
                    const profilePhotoInput = document.getElementById('profile_photo');
                    if (profilePhotoInput) profilePhotoInput.value = '';

                    if (data.profile_photo_url && profileImg) {
                        profileImg.src = data.profile_photo_url;
                        profileImg.removeAttribute('hidden');
                        if (placeholder) placeholder.style.display = 'none';
                    }
                    revokeTempObjectUrl();
                    initProfileOriginalState();
                    resolve(true);
                } else {
                    showToast(data.message || 'Error updating profile', 'danger');
                    resolve(false);
                }
            })
            .catch(() => {
                showToast('Network or server error updating profile', 'danger');
                resolve(false);
            });
        });
    }

    // A. Profile Form Submit
    if (formProfile) {
        formProfile.addEventListener('submit', function (e) {
            e.preventDefault();
            submitProfileForm();
        });
    }

    // B. Branch Form Submit
    const formBranch = document.getElementById('form-branch');
    if (formBranch) {
        formBranch.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch('/settings/update-branch/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast(data.message || 'Branch details updated successfully!', 'success');
                } else {
                    showToast(data.message || 'Error updating branch', 'danger');
                }
            })
            .catch(() => showToast('Failed to update branch details', 'danger'));
        });
    }

    // C. Invoice Form Submit
    const formInvoice = document.getElementById('form-invoice');
    if (formInvoice) {
        formInvoice.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch('/settings/update-invoice/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast(data.message || 'Invoice settings saved successfully!', 'success');
                } else {
                    showToast(data.message || 'Error saving invoice settings', 'danger');
                }
            })
            .catch(() => showToast('Error connecting to database', 'danger'));
        });
    }

    // D. Notifications Form Submit
    const formNotifications = document.getElementById('form-notifications');
    if (formNotifications) {
        formNotifications.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch('/settings/update-notifications/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast(data.message || 'Notification preferences saved!', 'success');
                } else {
                    showToast(data.message || 'Failed to save notifications', 'danger');
                }
            })
            .catch(() => showToast('Database submission failed', 'danger'));
        });
    }

    // ==========================================
    // 6. USER MANAGEMENT & MODALS
    // ==========================================
    const btnOpenUserModal = document.getElementById('btn-open-user-modal');
    const modalUser = document.getElementById('modal-user');

    if (btnOpenUserModal && modalUser) {
        btnOpenUserModal.addEventListener('click', function () {
            showModal(modalUser);
        });
    }
    const formUserModal = document.getElementById('form-user-modal');

    if (formUserModal) {
        formUserModal.addEventListener('submit', async function (event) {
            event.preventDefault();

            const password = document.getElementById('u_password')?.value || '';
            const confirmPassword = document.getElementById('u_confirm_password')?.value || '';

            if (password !== confirmPassword) {
                alert('Password and Confirm Password must match.');
                return;
            }

            const formData = new FormData(formUserModal);

            try {
                const response = await fetch('/settings/save-user/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const data = await response.json();

                if (!response.ok || data.status !== 'success') {
                    alert(data.message || 'Unable to create Super Admin.');
                    return;
                }

                alert(data.message || 'Super User added successfully!');

                formUserModal.reset();

                if (typeof hideModal === 'function' && modalUser) {
                    hideModal(modalUser);
                } else if (modalUser) {
                    modalUser.hidden = true;
                }

            } catch (error) {
                console.error('Super Admin creation error:', error);
                alert('Something went wrong while creating Super Admin.');
            }
        });
    }

    // ==========================================
    // 8. BACKUP & RESTORE
    // ==========================================
    const backupNowBtn = document.getElementById('btn-backup-now');
    const restoreBtn = document.getElementById('btn-trigger-restore');
    const restoreModal = document.getElementById('modal-confirm-restore');
    const confirmRestoreBtn = document.getElementById('btn-confirm-restore');
    const backupFileInput = document.getElementById('backup-file-input');

    // Backup Database
    if (backupNowBtn) {
        backupNowBtn.addEventListener('click', function () {
            backupNowBtn.disabled = true;
            fetch('/settings/create-backup/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
            .then(async response => {
                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error || 'Backup failed.');
                }
                const disposition = response.headers.get('Content-Disposition') || '';
                const match = disposition.match(/filename="?([^"]+)"?/);
                const filename = match ? match[1] : 'backup.json';
                return response.blob().then(blob => ({ blob, filename }));
            })
            .then(({ blob, filename }) => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showToast('Backup created and downloaded successfully.', 'success');
                setTimeout(() => location.reload(), 800);
            })
            .catch(error => {
                showToast(error.message || 'An unexpected error occurred during backup.', 'danger');
            })
            .finally(() => {
                backupNowBtn.disabled = false;
            });
        });
    }

    // Restore Database
    if (restoreBtn && backupFileInput) {
        restoreBtn.addEventListener('click', function (e) {
            e.preventDefault();
            backupFileInput.value = '';
            backupFileInput.click();
        });

        backupFileInput.addEventListener('change', function () {
            if (this.files && this.files.length > 0) {
                showModal(restoreModal);
            }
        });
    }

    if (restoreModal) {
        restoreModal.querySelectorAll('[data-dismiss="modal"]').forEach(btn => {
            btn.addEventListener('click', function () {
                if (backupFileInput) backupFileInput.value = '';
            });
        });
    }

    if (confirmRestoreBtn) {
        confirmRestoreBtn.addEventListener('click', function () {
            hideModal(restoreModal);

            if (!backupFileInput || !backupFileInput.files.length) {
                showToast('Please select a backup file to restore.', 'danger');
                if (backupFileInput) backupFileInput.value = '';
                return;
            }

            const formData = new FormData();
            formData.append('backup_file', backupFileInput.files[0]);

            fetch('/settings/restore-backup/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (backupFileInput) backupFileInput.value = '';
                if (data.success) {
                    showToast(data.message || 'Backup restored successfully.', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showToast(data.error || 'Restore failed.', 'danger');
                }
            })
            .catch(error => {
                if (backupFileInput) backupFileInput.value = '';
                console.error('Restore error:', error);
                showToast('An unexpected error occurred during restore.', 'danger');
            });
        });
    }
});