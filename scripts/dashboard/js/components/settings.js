/**
 * Settings Panel Component
 * Settings overlay and configuration
 */

/**
 * Toggle settings panel visibility
 */
export function toggleSettingsPanel() {
  const overlay = document.getElementById('settingsOverlay');
  overlay.classList.toggle('visible');
}

/**
 * Close settings panel
 */
export function closeSettingsPanel() {
  const overlay = document.getElementById('settingsOverlay');
  overlay.classList.remove('visible');
}

/**
 * Initialize settings panel
 */
export function initSettingsPanel() {
  // Close settings on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('settingsOverlay').classList.contains('visible')) {
      closeSettingsPanel();
    }
  });
}

// Make functions available globally for onclick handlers
window.toggleSettingsPanel = toggleSettingsPanel;
window.closeSettingsPanel = closeSettingsPanel;

export default {
  toggleSettingsPanel,
  closeSettingsPanel,
  initSettingsPanel
};
