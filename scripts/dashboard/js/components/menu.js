/**
 * Context Menu Component
 * Source action menu
 */

import { state } from '../state.js';
import { api } from '../api.js';
import { showToast } from './notifications.js';

/**
 * Show source action menu
 * @param {Event} event - Click event
 * @param {HTMLElement} element - Clicked element
 */
export function showSourceMenu(event, element) {
  event.stopPropagation();

  const sourceId = element.dataset.sourceId;
  const sourceName = element.dataset.sourceName;
  const sourceUrl = element.dataset.sourceUrl;
  const sourceStatus = element.dataset.sourceStatus;

  const menu = document.getElementById('sourceActionMenu');
  state.activeSourceMenu = { id: sourceId, name: sourceName, url: sourceUrl, status: sourceStatus };

  // Update menu content
  document.getElementById('menuSourceName').textContent = sourceName;
  document.getElementById('menuSourceUrl').textContent = sourceUrl || 'No URL';

  // Show/hide actions based on status
  const startBtn = document.getElementById('menuStartRalph');
  const stopBtn = document.getElementById('menuStopRalph');

  // Check if Ralph is currently running
  const statusText = document.getElementById('statusText')?.textContent || '';
  const ralphRunning = statusText.toLowerCase().includes('running');
  const isCurrentSource = sourceStatus === 'in_progress';

  // Always enable both buttons
  startBtn.classList.remove('disabled');
  stopBtn.classList.remove('disabled');

  if (ralphRunning && isCurrentSource) {
    startBtn.querySelector('.label').textContent = '▶ Restart Ralph';
    stopBtn.querySelector('.label').textContent = '⏹ Stop Ralph (running)';
  } else if (ralphRunning) {
    startBtn.querySelector('.label').textContent = '▶ Start Ralph';
    stopBtn.querySelector('.label').textContent = '⏹ Stop Ralph (running)';
  } else {
    startBtn.querySelector('.label').textContent = '▶ Start Ralph';
    stopBtn.querySelector('.label').textContent = '⏹ Stop Ralph';
  }

  // Position menu near the clicked element
  const rect = element.getBoundingClientRect();
  menu.style.left = `${rect.left + 20}px`;
  menu.style.top = `${rect.top - 10}px`;

  // Ensure menu stays within viewport
  const menuRect = menu.getBoundingClientRect();
  if (menuRect.right > window.innerWidth) {
    menu.style.left = `${window.innerWidth - 220}px`;
  }
  if (menuRect.bottom > window.innerHeight) {
    menu.style.top = `${rect.top - menuRect.height - 10}px`;
  }

  menu.classList.add('visible');
}

/**
 * Hide source action menu
 */
export function hideSourceMenu() {
  const menu = document.getElementById('sourceActionMenu');
  menu.classList.remove('visible');
  state.activeSourceMenu = null;
}

/**
 * Start Ralph for selected source
 */
export async function startRalphForSource() {
  if (!state.activeSourceMenu) return;

  const { id, name } = state.activeSourceMenu;
  hideSourceMenu();

  showToast(`🚀 Starting Ralph for ${name}...`, 'info');

  try {
    const data = await api.startRalph({
      iterations: 25,
      sources: [id]
    });

    if (data.success) {
      showToast(`✓ Ralph started for ${name}`, 'success');
      // Refresh will be handled by main dashboard loop
    } else {
      showToast(`✗ Failed: ${data.error}`, 'error');
    }
  } catch (err) {
    showToast(`✗ Error: ${err.message}`, 'error');
  }
}

/**
 * Stop Ralph
 */
export async function stopRalphFromMenu() {
  hideSourceMenu();

  showToast('⏹ Stopping Ralph...', 'info');

  try {
    const data = await api.stopRalph();

    if (data.success) {
      showToast(`✓ ${data.message || 'Ralph stopped'}`, 'success');
    } else {
      // If normal stop fails, try kill-all
      showToast('⏹ Trying force stop...', 'info');
      const killData = await api.killAllRalphs();

      if (killData.success) {
        showToast(`✓ ${killData.message || 'Processes killed'}`, 'success');
      } else {
        showToast(`✗ Failed: ${killData.error || 'Unknown error'}`, 'error');
      }
    }
  } catch (err) {
    showToast(`✗ Error: ${err.message}`, 'error');
  }
}

/**
 * Generate PRD for selected source
 */
export function generatePrdForSource() {
  if (!state.activeSourceMenu) return;

  const { id, name, url } = state.activeSourceMenu;
  hideSourceMenu();

  // Import dynamically to avoid circular dependency
  import('../features/prd-editor.js').then(module => {
    module.openPrdModal(id, name, url);
  });
}

/**
 * View source website
 */
export function viewSourceData() {
  if (!state.activeSourceMenu) return;

  const { url } = state.activeSourceMenu;
  hideSourceMenu();

  if (url) {
    window.open(url, '_blank');
  }
}

/**
 * Initialize menu event listeners
 */
export function initMenu() {
  // Close menus when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.source-action-menu') && !e.target.closest('.source-status')) {
      hideSourceMenu();
    }
  });

  // Close menus on escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideSourceMenu();
    }
  });
}

// Make functions available globally for onclick handlers
window.showSourceMenu = showSourceMenu;
window.hideSourceMenu = hideSourceMenu;
window.startRalphForSource = startRalphForSource;
window.stopRalphFromMenu = stopRalphFromMenu;
window.generatePrdForSource = generatePrdForSource;
window.viewSourceData = viewSourceData;

export default {
  showSourceMenu,
  hideSourceMenu,
  startRalphForSource,
  stopRalphFromMenu,
  generatePrdForSource,
  viewSourceData,
  initMenu
};
