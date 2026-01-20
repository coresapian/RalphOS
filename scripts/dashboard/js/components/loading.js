/**
 * Loading Screen Component
 * Manages the initial loading overlay
 */

import { state } from '../state.js';
import { CONFIG } from '../config.js';

/**
 * Update loading status text
 * @param {string} message - Status message to display
 */
export function updateLoadingStatus(message) {
  if (state.loadingHidden) return;
  const status = document.getElementById('loadingStatus');
  if (status) status.textContent = message;
}

/**
 * Hide loading screen with fade animation
 */
export function hideLoadingScreen() {
  if (state.loadingHidden) return;
  state.loadingHidden = true;

  const overlay = document.getElementById('loadingOverlay');
  if (!overlay) return;

  const status = document.getElementById('loadingStatus');
  if (status) status.textContent = 'Ready!';

  // Fade out
  overlay.style.transition = 'opacity 0.3s';
  overlay.style.opacity = '0';

  // Remove after fade
  setTimeout(() => {
    overlay.remove();
  }, 350);
}

/**
 * Initialize loading screen with failsafe timeout
 */
export function initLoadingScreen() {
  // Failsafe: Always hide loading screen after timeout
  setTimeout(() => {
    if (!state.loadingHidden) {
      console.log('Failsafe: hiding loading screen');
      hideLoadingScreen();
    }
  }, CONFIG.LOADING_FAILSAFE_TIMEOUT);
}

export default {
  updateLoadingStatus,
  hideLoadingScreen,
  initLoadingScreen
};
