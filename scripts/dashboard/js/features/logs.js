/**
 * Logs Feature
 * Log panel, source pagination, and controls
 */

import { state } from '../state.js';
import { api } from '../api.js';
import { colorizeLog, filterLogBySource } from '../utils.js';

/**
 * Toggle log panel expand/collapse
 */
export function toggleLogPanel() {
  state.logPanelExpanded = !state.logPanelExpanded;
  const mainGrid = document.getElementById('mainGrid');
  mainGrid.classList.toggle('logs-expanded', state.logPanelExpanded);

  // Save preference
  localStorage.setItem('logPanelExpanded', state.logPanelExpanded);
}

/**
 * Initialize log panel state from localStorage
 */
export function initLogPanel() {
  const saved = localStorage.getItem('logPanelExpanded');
  state.logPanelExpanded = saved === 'true';
  document.getElementById('mainGrid').classList.toggle('logs-expanded', state.logPanelExpanded);
}

/**
 * Toggle auto-refresh
 */
export function toggleAutoRefresh() {
  state.autoRefreshEnabled = !state.autoRefreshEnabled;
  const btn = document.getElementById('autoRefreshBtn');
  btn.classList.toggle('active', state.autoRefreshEnabled);
}

/**
 * Clear log display
 */
export function clearLogDisplay() {
  document.getElementById('logOutput').innerHTML = '<span class="info">Log cleared. Waiting for new data...</span>';
  state.sourceLogCache = {};
}

/**
 * Toggle auto-scroll
 */
export function toggleAutoScroll() {
  state.autoScrollEnabled = !state.autoScrollEnabled;
  const indicator = document.getElementById('autoScrollIndicator');
  if (indicator) {
    indicator.textContent = state.autoScrollEnabled ? '↓ Auto-scroll ON' : '↓ Auto-scroll OFF';
    indicator.style.opacity = state.autoScrollEnabled ? '1' : '0.5';
  }
}

/**
 * Update log source list for pagination
 * @param {Array} sources - Source data array
 */
export function updateLogSourceList(sources) {
  // Only show: running agents (in_progress) and sources with errors (blocked)
  const running = sources
    .filter(s => s.status === 'in_progress')
    .sort((a, b) => a.name.localeCompare(b.name));

  const errors = sources
    .filter(s => s.status === 'blocked')
    .sort((a, b) => a.name.localeCompare(b.name));

  // Combine: All Sources first, then running, then errors
  const activeSources = [...running, ...errors];

  if (activeSources.length > 0) {
    state.logSourceList = [
      { id: '_all', name: 'All Active', status: 'all' },
      ...activeSources
    ];
  } else {
    // No active sources
    state.logSourceList = [
      { id: '_all', name: 'No Active Ralphs', status: 'idle' }
    ];
  }

  // Reset to first item if current selection is no longer valid
  if (state.currentLogSourceIndex >= state.logSourceList.length) {
    state.currentLogSourceIndex = 0;
  }

  updateLogSourceUI();
}

/**
 * Update log source pagination UI
 */
function updateLogSourceUI() {
  const nameEl = document.getElementById('logSourceName');
  const counterEl = document.getElementById('logSourceCounter');
  const statusEl = document.getElementById('logSourceStatus');
  const prevBtn = document.getElementById('logPrevBtn');
  const nextBtn = document.getElementById('logNextBtn');

  if (state.logSourceList.length === 0) {
    nameEl.textContent = 'No Sources';
    counterEl.textContent = '0 of 0';
    statusEl.className = 'log-source-status';
    prevBtn.classList.add('disabled');
    nextBtn.classList.add('disabled');
    return;
  }

  // Clamp index
  state.currentLogSourceIndex = Math.max(0, Math.min(state.currentLogSourceIndex, state.logSourceList.length - 1));

  const current = state.logSourceList[state.currentLogSourceIndex];
  nameEl.textContent = current.name;

  // Style based on status
  if (current.status === 'idle') {
    nameEl.className = 'log-source-name';
    nameEl.style.color = 'var(--text-muted)';
  } else if (current.id === '_all') {
    nameEl.className = 'log-source-name all-sources';
    nameEl.style.color = '';
  } else {
    nameEl.className = 'log-source-name';
    nameEl.style.color = '';
  }

  // Counter
  if (state.logSourceList.length <= 1) {
    counterEl.textContent = 'idle';
    counterEl.style.color = 'var(--text-muted)';
  } else {
    counterEl.textContent = `${state.currentLogSourceIndex + 1} of ${state.logSourceList.length}`;
    counterEl.style.color = '';
  }

  // Status indicator
  if (current.id === '_all' || current.status === 'idle') {
    statusEl.className = 'log-source-status';
    statusEl.style.display = 'none';
  } else {
    statusEl.style.display = 'inline-block';
    statusEl.className = `log-source-status ${current.status === 'in_progress' ? 'running' : current.status}`;
  }

  // Arrow states
  const singleItem = state.logSourceList.length <= 1;
  prevBtn.classList.toggle('disabled', singleItem || state.currentLogSourceIndex === 0);
  nextBtn.classList.toggle('disabled', singleItem || state.currentLogSourceIndex >= state.logSourceList.length - 1);
}

/**
 * Navigate to previous log source
 */
export function prevLogSource() {
  if (state.currentLogSourceIndex > 0) {
    state.currentLogSourceIndex--;
    updateLogSourceUI();
    refreshLogNow();
  }
}

/**
 * Navigate to next log source
 */
export function nextLogSource() {
  if (state.currentLogSourceIndex < state.logSourceList.length - 1) {
    state.currentLogSourceIndex++;
    updateLogSourceUI();
    refreshLogNow();
  }
}

/**
 * Refresh log content
 */
export async function refreshLogNow() {
  try {
    const data = await api.getLog(200);

    if (data.log) {
      const logOutput = document.getElementById('logOutput');

      // Get current selected source
      const currentSource = state.logSourceList[state.currentLogSourceIndex];
      const sourceId = currentSource ? currentSource.id : '_all';

      // Filter log if a specific source is selected
      let displayLog = data.log;
      if (sourceId !== '_all') {
        displayLog = filterLogBySource(data.log, sourceId);
      }

      logOutput.innerHTML = colorizeLog(displayLog);
      if (state.autoScrollEnabled) {
        logOutput.scrollTop = logOutput.scrollHeight;
      }

      const sourceLabel = sourceId === '_all' ? 'All' : currentSource.name;
      document.getElementById('logRefresh').textContent = `${sourceLabel} · ${new Date().toLocaleTimeString()}`;
    }
  } catch (error) {
    console.error('Failed to refresh log:', error);
  }
}

// Make functions available globally for onclick handlers
window.toggleLogPanel = toggleLogPanel;
window.toggleAutoRefresh = toggleAutoRefresh;
window.toggleAutoScroll = toggleAutoScroll;
window.clearLogDisplay = clearLogDisplay;
window.prevLogSource = prevLogSource;
window.nextLogSource = nextLogSource;
window.refreshLogNow = refreshLogNow;

export default {
  toggleLogPanel,
  initLogPanel,
  toggleAutoRefresh,
  toggleAutoScroll,
  clearLogDisplay,
  updateLogSourceList,
  prevLogSource,
  nextLogSource,
  refreshLogNow
};
