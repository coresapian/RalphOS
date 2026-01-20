/**
 * Ralph Dashboard - Main Entry Point
 * Initializes all modules and starts the dashboard
 */

// Core imports
import { CONFIG } from './config.js';
import { state } from './state.js';

// Component imports
import { hideLoadingScreen, updateLoadingStatus } from './components/loading.js';
import { initNotifications, showToast, toggleNotifications, clearAllNotifications } from './components/notifications.js';
import { initSettingsPanel, toggleSettingsPanel, closeSettingsPanel } from './components/settings.js';
import { initMenu, showSourceMenu, startRalphForSource, generatePrdForSource, viewSourceData } from './components/menu.js';

// Feature imports
import { startDashboardRefresh } from './features/dashboard.js';
import { initSourcesControls, loadMoreSources } from './features/sources.js';
import { initLogPanel, toggleLogPanel, refreshLogNow, toggleAutoRefresh, toggleAutoScroll, clearLogDisplay, prevLogSource, nextLogSource } from './features/logs.js';
import { startRalph, stopRalph, killAllRalphs, updateRalphStatus, generatePRD } from './features/ralph.js';
import { initPrdModal, openPrdModal, closePrdModal, switchPrdTab, runDomainAnalysis, runPrdGeneration, clearPrdEditor, savePrdToFile, savePrdToRalph, usePrdAndStartRalph } from './features/prd-editor.js';
import { startBrowserSession, stopBrowserSession, browserNavigate, browserBack, browserForward, browserRefresh, browserSnapshot, browserExecuteJS, browserExtractDOM } from './features/browser.js';

/**
 * Initialize the dashboard
 */
function initDashboard() {
  console.log('🚀 Initializing Ralph Dashboard...');

  // Initialize components
  initNotifications();
  initSettingsPanel();
  initMenu();
  initPrdModal();

  // Initialize features
  initSourcesControls();
  initLogPanel();

  // Set up global event listeners
  setupEventListeners();

  // Start the dashboard refresh loop
  startDashboardRefresh();

  console.log('✓ Dashboard initialized');
}

/**
 * Set up global event listeners
 */
function setupEventListeners() {
  // URL bar enter key
  const urlBar = document.getElementById('browserUrlBar');
  if (urlBar) {
    urlBar.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        browserNavigate();
      }
    });
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + L to toggle log panel
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
      e.preventDefault();
      toggleLogPanel();
    }
  });
}

/**
 * Make functions available globally for onclick handlers in HTML
 * This is needed because the HTML uses inline onclick attributes
 * Note: Many modules already expose their functions to window,
 * but we consolidate here for clarity and to catch any missing exports
 */
function exposeGlobalFunctions() {
  // Dashboard controls
  window.startRalph = startRalph;
  window.stopRalph = stopRalph;
  window.killAllRalphs = killAllRalphs;
  window.generatePRD = generatePRD;

  // Log controls
  window.toggleLogPanel = toggleLogPanel;
  window.refreshLogNow = refreshLogNow;
  window.toggleAutoRefresh = toggleAutoRefresh;
  window.toggleAutoScroll = toggleAutoScroll;
  window.clearLogDisplay = clearLogDisplay;
  window.prevLogSource = prevLogSource;
  window.nextLogSource = nextLogSource;

  // PRD controls
  window.openPrdModal = openPrdModal;
  window.closePrdModal = closePrdModal;
  window.switchPrdTab = switchPrdTab;
  window.runDomainAnalysis = runDomainAnalysis;
  window.runPrdGeneration = runPrdGeneration;
  window.clearPrdEditor = clearPrdEditor;
  window.savePrdToFile = savePrdToFile;
  window.savePrdToRalph = savePrdToRalph;
  window.usePrdAndStartRalph = usePrdAndStartRalph;

  // Browser controls
  window.startBrowserSession = startBrowserSession;
  window.stopBrowserSession = stopBrowserSession;
  window.browserNavigate = browserNavigate;
  window.browserBack = browserBack;
  window.browserForward = browserForward;
  window.browserRefresh = browserRefresh;
  window.browserSnapshot = browserSnapshot;
  window.browserExecuteJS = browserExecuteJS;
  window.browserExtractDOM = browserExtractDOM;

  // Source controls
  window.loadMoreSources = loadMoreSources;
  window.showSourceMenu = showSourceMenu;
  window.startRalphForSource = startRalphForSource;
  window.generatePrdForSource = generatePrdForSource;
  window.viewSourceData = viewSourceData;

  // Settings controls
  window.toggleSettingsPanel = toggleSettingsPanel;
  window.closeSettingsPanel = closeSettingsPanel;

  // Notifications
  window.showToast = showToast;
  window.toggleNotifications = toggleNotifications;
  window.clearAllNotifications = clearAllNotifications;
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  exposeGlobalFunctions();
  initDashboard();
});

// Export for potential external use
export {
  initDashboard,
  exposeGlobalFunctions
};
