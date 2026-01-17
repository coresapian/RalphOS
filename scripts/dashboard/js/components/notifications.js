/**
 * Notifications Component
 * Toast notifications and notification dropdown
 */

import { state } from '../state.js';
import { CONFIG } from '../config.js';
import { formatTimeAgo } from '../utils.js';
import { api } from '../api.js';

/**
 * Toggle notification dropdown visibility
 */
export function toggleNotifications() {
  const dropdown = document.getElementById('notifDropdown');
  dropdown.classList.toggle('visible');

  // Mark all as read when opened
  if (dropdown.classList.contains('visible')) {
    state.notifications.forEach(n => n.unread = false);
    updateNotificationBadge();
    renderNotifications();
  }
}

/**
 * Close notification dropdown
 */
export function closeNotifications() {
  document.getElementById('notifDropdown').classList.remove('visible');
}

/**
 * Update badge count
 */
export function updateNotificationBadge() {
  const badge = document.getElementById('notifBadge');
  const btn = document.getElementById('notifBtn');
  const unreadCount = state.notifications.filter(n => n.unread).length;

  badge.textContent = unreadCount > 0 ? (unreadCount > 9 ? '9+' : unreadCount) : '';
  btn.classList.toggle('has-alerts', unreadCount > 0);
}

/**
 * Add a notification
 * @param {Object} notification - Notification data
 */
export function addNotification(notification) {
  state.notifications.unshift({
    id: Date.now(),
    unread: true,
    timestamp: new Date(),
    ...notification
  });

  // Keep only last N notifications
  if (state.notifications.length > CONFIG.MAX_NOTIFICATIONS) {
    state.notifications = state.notifications.slice(0, CONFIG.MAX_NOTIFICATIONS);
  }

  updateNotificationBadge();
  renderNotifications();

  // Show toast for critical notifications
  if (notification.type === 'error') {
    showToast(`⚠ ${notification.source}: ${notification.message}`, 'error');
  }
}

/**
 * Render notification list
 */
export function renderNotifications() {
  const list = document.getElementById('notifList');

  if (state.notifications.length === 0) {
    list.innerHTML = `
      <div class="notif-empty">
        <div class="notif-empty-icon">🔔</div>
        <div>No alerts - all systems running smoothly</div>
      </div>
    `;
    return;
  }

  list.innerHTML = state.notifications.map(n => `
    <div class="notif-item ${n.unread ? 'unread' : ''}" onclick="window.viewNotificationDetails('${n.id}')">
      <div class="notif-item-header">
        <span class="notif-source">
          ${n.type === 'error' ? '🔴' : n.type === 'warning' ? '🟡' : '🔵'}
          ${n.source}
        </span>
        <span class="notif-time">${formatTimeAgo(n.timestamp)}</span>
      </div>
      <div class="notif-message">${n.message}</div>
      ${n.suggestion ? `
        <div class="notif-suggestion">
          <strong>💡 Suggested Fix:</strong>
          ${n.suggestion}
        </div>
      ` : ''}
      ${n.actions ? `
        <div class="notif-actions">
          ${n.actions.map(a => `
            <button class="notif-action-btn" onclick="event.stopPropagation(); ${a.action}">${a.label}</button>
          `).join('')}
        </div>
      ` : ''}
    </div>
  `).join('');
}

/**
 * Clear all notifications
 */
export function clearAllNotifications() {
  state.notifications = [];
  state.analyzedErrors.clear();
  updateNotificationBadge();
  renderNotifications();
}

/**
 * View notification details
 * @param {string} id - Notification ID
 */
export function viewNotificationDetails(id) {
  const notif = state.notifications.find(n => n.id == id);
  if (notif && notif.sourceId) {
    closeNotifications();
    // Import dynamically to avoid circular dependency
    import('../features/prd-editor.js').then(module => {
      module.openPrdModal(notif.sourceId, notif.source, notif.sourceUrl);
    });
  }
}

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', 'info'
 */
export function showToast(message, type = 'info') {
  const existing = document.querySelector('.notification');
  if (existing) existing.remove();

  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.innerHTML = message;
  document.body.appendChild(notification);

  setTimeout(() => notification.classList.add('visible'), 10);
  setTimeout(() => {
    notification.classList.remove('visible');
    setTimeout(() => notification.remove(), 300);
  }, CONFIG.NOTIFICATION_DURATION);
}

/**
 * Initialize notifications
 */
export function initNotifications() {
  // Any initialization logic
  renderNotifications();
}

// Make functions available globally for onclick handlers
window.viewNotificationDetails = viewNotificationDetails;
window.toggleNotifications = toggleNotifications;
window.clearAllNotifications = clearAllNotifications;

export default {
  toggleNotifications,
  closeNotifications,
  addNotification,
  clearAllNotifications,
  showToast,
  renderNotifications,
  initNotifications
};
