/**
 * Global State Management
 * Centralized state for the Ralph Dashboard
 */

export const state = {
  // Loading state
  isInitialLoad: true,
  loadingHidden: false,

  // Data
  lastLogLines: [],
  allSources: [],
  allSourcesData: [],
  notifications: [],

  // Log pagination
  logSourceList: [],
  currentLogSourceIndex: 0,
  sourceLogCache: {},

  // Error tracking
  analyzedErrors: new Set(),
  previousSourceStatuses: {},

  // Filter/Sort
  currentFilter: '',
  currentSort: 'progress',

  // UI State
  logPanelExpanded: false,
  autoRefreshEnabled: true,
  autoScrollEnabled: true,

  // Browser preview
  browserWs: null,
  browserSessionId: null,
  screencastEnabled: false,
  browserConnected: false,
  screenshotPollingInterval: null,
  cdpCommandId: 1,
  cdpCallbacks: {},

  // PRD Editor
  currentPrdSource: null,
  prdGenerationAbort: null,
  currentPrdContent: '',

  // Source menu
  activeSourceMenu: null,

  // Kill operation
  killCheckInterval: null,

  // Pagination
  _filteredSources: [],
  _loadedCount: 0,
};

/**
 * Update state and optionally trigger callbacks
 */
export function updateState(updates) {
  Object.assign(state, updates);
}

/**
 * Reset state to defaults
 */
export function resetState() {
  state.isInitialLoad = true;
  state.loadingHidden = false;
  state.allSources = [];
  state.allSourcesData = [];
  state.notifications = [];
  state.logSourceList = [];
  state.currentLogSourceIndex = 0;
  state.sourceLogCache = {};
  state.analyzedErrors.clear();
  state.previousSourceStatuses = {};
}

export default state;
