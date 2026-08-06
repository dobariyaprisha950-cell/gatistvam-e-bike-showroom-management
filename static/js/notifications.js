/**
 * ==========================================================================
 * GATISTVAM E-BIKE SHOWROOM - NOTIFICATIONS MANAGER (Vanilla JS + Django API)
 * Fully connected with Django REST Framework backend API.
 * ==========================================================================
 */

function initNotificationsManager() {
    if (window.gatistvamNotificationsInitialized) return;
    window.gatistvamNotificationsInitialized = true;

    // State Variables
    let notifications = [];
    const container = document.getElementById('notificationsContainer');
    const API_URL = container ? container.dataset.apiUrl : '/yakuza/api/notifications/';

    // CSRF Token Helper
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

    // DOM Elements
    const listContainer = document.getElementById('notificationList');
    const emptyState = document.getElementById('emptyState');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const searchInput = document.getElementById('searchInput');
    const typeFilter = document.getElementById('typeFilter');
    const statusFilter = document.getElementById('statusFilter');
    const dateFilter = document.getElementById('dateFilter');
    const btnReset = document.getElementById('btnReset');
    const btnClearAll = document.getElementById('btnClearAll');

    // Counts
    const countUnread = document.getElementById('count-unread');
    const countToday = document.getElementById('count-today');
    const countLowStock = document.getElementById('count-lowstock');
    const countSystem = document.getElementById('count-system');

    if (!listContainer) return;

    // Map Notification Type to Icon & Color
    function getNotificationMetadata(type) {
        switch (type) {
            case 'Low Stock':
                return { icon: 'fas fa-exclamation-triangle', colorCode: 'orange' };
            case 'Sales Entry':
                return { icon: 'fas fa-shopping-cart', colorCode: 'green' };
            case 'Purchase Entry':
                return { icon: 'fas fa-box-open', colorCode: 'green' };
            case 'Expense Added':
                return { icon: 'fas fa-file-invoice-dollar', colorCode: 'blue' };
            case 'System Update':
                return { icon: 'fas fa-cogs', colorCode: 'blue' };
            case 'Daily Closing Reminder':
                return { icon: 'fas fa-clock', colorCode: 'red' };
            case 'Monthly Profit Reminder':
                return { icon: 'fas fa-chart-line', colorCode: 'blue' };
            default:
                return { icon: 'fas fa-bell', colorCode: 'blue' };
        }
    }

    // Format Date-Time String
    function formatDateTime(isoString) {
        if (!isoString) return '';
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return isoString;
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const mins = String(d.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${mins}`;
    }

    // API: Fetch All Notifications from Django Backend
    async function fetchNotifications() {
        if (loadingSpinner) loadingSpinner.classList.remove('hidden');
        if (emptyState) emptyState.classList.add('hidden');

        try {
            const response = await fetch(API_URL, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                }
            });

            if (!response.ok) throw new Error('Failed to fetch notifications');

            const data = await response.json();
            // DRF Paginated Response support
            notifications = Array.isArray(data) ? data : (data.results || []);
            renderNotifications();
        } catch (error) {
            console.error('Error loading notifications:', error);
            listContainer.innerHTML = `<div class="empty-state"><p class="text-danger">Failed to load notifications from server.</p></div>`;
        } finally {
            if (loadingSpinner) loadingSpinner.classList.add('hidden');
        }
    }

    // Update Summary Counters
    function updateSummaryCards() {
        const todayStr = new Date().toISOString().split('T')[0];

        const unreadCount = notifications.filter(n => !n.is_read).length;
        const todayCount = notifications.filter(n => n.created_at && n.created_at.startsWith(todayStr)).length;
        const lowStockCount = notifications.filter(n => n.notification_type === 'Low Stock').length;
        const systemCount = notifications.filter(n => n.notification_type === 'System Update').length;

        if (countUnread) countUnread.textContent = unreadCount;
        if (countToday) countToday.textContent = todayCount;
        if (countLowStock) countLowStock.textContent = lowStockCount;
        if (countSystem) countSystem.textContent = systemCount;
    }

    // Render Function
    function renderNotifications() {
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const selectedType = typeFilter ? typeFilter.value : 'ALL';
        const selectedStatus = statusFilter ? statusFilter.value : 'ALL';
        const selectedDate = dateFilter ? dateFilter.value : '';

        const filtered = notifications.filter(item => {
            const title = (item.title || '').toLowerCase();
            const message = (item.message || '').toLowerCase();
            const branch = (item.branch_name || '').toLowerCase();

            const matchesSearch = !query || title.includes(query) || message.includes(query) || branch.includes(query);
            const matchesType = selectedType === 'ALL' || item.notification_type === selectedType;
            
            const isRead = item.is_read;
            const matchesStatus = selectedStatus === 'ALL' || 
                (selectedStatus === 'read' && isRead) || 
                (selectedStatus === 'unread' && !isRead);

            const matchesDate = !selectedDate || (item.created_at && item.created_at.startsWith(selectedDate));

            return matchesSearch && matchesType && matchesStatus && matchesDate;
        });

        listContainer.innerHTML = '';

        if (filtered.length === 0) {
            if (emptyState) emptyState.classList.remove('hidden');
        } else {
            if (emptyState) emptyState.classList.add('hidden');

            filtered.forEach(item => {
                const isUnread = !item.is_read;
                const statusStr = isUnread ? 'unread' : 'read';
                const meta = getNotificationMetadata(item.notification_type);
                const formattedTime = formatDateTime(item.created_at);

                const card = document.createElement('div');
                card.className = `notification-card status-${statusStr} theme-${meta.colorCode}`;
                card.dataset.id = item.id;

                card.innerHTML = `
                    <div class="notification-icon-wrap">
                        <i class="${meta.icon}"></i>
                    </div>

                    <div class="notification-body">
                        <div class="notification-header">
                            <h4 class="notification-title">${item.title}</h4>
                            <span class="type-badge">${item.notification_type}</span>
                        </div>
                        <p class="notification-desc">${item.message}</p>
                        <div class="notification-meta">
                            <span class="meta-item">
                                <i class="fas fa-store"></i> ${item.branch_name || 'All Branches'}
                            </span>
                            <span class="meta-item">
                                <i class="fas fa-clock"></i> ${formattedTime}
                            </span>
                        </div>
                    </div>

                    <div class="notification-status-box">
                        <span class="status-badge ${statusStr}">
                            <i class="fas fa-circle" style="font-size: 6px;"></i>
                            ${isUnread ? 'Unread' : 'Read'}
                        </span>
                    </div>

                    <div class="notification-actions">
                        ${isUnread ? `
                            <button type="button" class="btn btn-outline btn-action-read" title="Mark as read">
                                <i class="fas fa-check"></i> Read
                            </button>
                        ` : ''}
                        <button type="button" class="btn btn-danger btn-action-delete" title="Delete notification">
                            <i class="fas fa-trash-alt"></i> Delete
                        </button>
                    </div>
                `;

                // Action Event Listeners
                const btnRead = card.querySelector('.btn-action-read');
                if (btnRead) {
                    btnRead.addEventListener('click', () => markAsRead(item.id));
                }

                const btnDelete = card.querySelector('.btn-action-delete');
                if (btnDelete) {
                    btnDelete.addEventListener('click', () => deleteNotification(item.id, card));
                }

                listContainer.appendChild(card);
            });
        }

        updateSummaryCards();
    }

    // API Action: Mark as Read
    async function markAsRead(id) {
        try {
            const response = await fetch(`${API_URL}${id}/mark_as_read/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                }
            });

            if (response.ok) {
                notifications = notifications.map(item =>
                    item.id === id ? { ...item, is_read: true } : item
                );
                renderNotifications();
            } else {
                console.error('Failed to mark notification as read');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    // API Action: Delete Notification
    async function deleteNotification(id, cardElement) {
        cardElement.classList.add('removing');

        try {
            const response = await fetch(`${API_URL}${id}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrftoken
                }
            });

            if (response.ok) {
                setTimeout(() => {
                    notifications = notifications.filter(item => item.id !== id);
                    renderNotifications();
                }, 280);
            } else {
                cardElement.classList.remove('removing');
                alert('Failed to delete notification.');
            }
        } catch (error) {
            cardElement.classList.remove('removing');
            console.error('Error:', error);
        }
    }

    // Filter Controls
    function resetFilters() {
        if (searchInput) searchInput.value = '';
        if (typeFilter) typeFilter.value = 'ALL';
        if (statusFilter) statusFilter.value = 'ALL';
        if (dateFilter) dateFilter.value = '';
        renderNotifications();
    }

    // Clear All Action
    async function clearAllNotifications() {
        if (!confirm('Are you sure you want to clear all notifications?')) return;

        try {
            // Sequential API Deletions
            const deletePromises = notifications.map(n => 
                fetch(`${API_URL}${n.id}/`, {
                    method: 'DELETE',
                    headers: { 'X-CSRFToken': csrftoken }
                })
            );
            await Promise.all(deletePromises);
            notifications = [];
            renderNotifications();
        } catch (error) {
            console.error('Error clearing notifications:', error);
            fetchNotifications(); // Refresh to original state if error occurs
        }
    }

    // Event Listeners for Filters
    if (searchInput) searchInput.addEventListener('input', renderNotifications);
    if (typeFilter) typeFilter.addEventListener('change', renderNotifications);
    if (statusFilter) statusFilter.addEventListener('change', renderNotifications);
    if (dateFilter) dateFilter.addEventListener('change', renderNotifications);
    if (btnReset) btnReset.addEventListener('click', resetFilters);
    if (btnClearAll) btnClearAll.addEventListener('click', clearAllNotifications);

    // Initial Fetch Call
    fetchNotifications();
}

// Global Trigger Initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotificationsManager);
} else {
    initNotificationsManager();
}